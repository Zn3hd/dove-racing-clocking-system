"""One-use, owner-bound enrollment; no reusable secret in an invitation."""
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..club_access import check_loft_admin
from ..database import get_db
from ..rate_limits import consume, scan_ip
from .device_gateway import digest
from .member_dashboard import require_member

router = APIRouter(tags=['reader-enrollment'])


def enrollment_authorized(db, issuer, owner):
    return db.execute(text('''SELECT EXISTS(
      SELECT 1 FROM users a JOIN club_memberships am ON am.user_id=a.id
      JOIN club_memberships m ON m.club_id=am.club_id
      JOIN users u ON u.id=m.user_id
      WHERE a.id=:issuer AND a.status='active' AND a.role_code IN ('chairman','president')
        AND am.club_role='admin' AND u.id=:owner AND u.status='active'
        AND u.role_code='member' AND m.club_role='member')'''),
      {'issuer': issuer, 'owner': owner}).scalar_one()


@router.post('/devices/{device_id}/enrollment', status_code=201)
def issue_enrollment(device_id: UUID, actor=Depends(require_admin), db: Session=Depends(get_db)):
    consume('reader_enrollment_issue', actor['id'], 10)
    code = secrets.token_urlsafe(32)
    with db.begin():
        device = db.execute(text('''SELECT d.loft_id,d.status,l.user_id AS owner_id,l.verified_at
          FROM devices d JOIN lofts l ON l.id=d.loft_id WHERE d.id=:id FOR UPDATE OF d'''),
          {'id': device_id}).mappings().first()
        if not device:
            raise HTTPException(404, 'Reader not found')
        check_loft_admin(db, actor, device['loft_id'])
        if (device['status'] != 'active' or not device['verified_at'] or
                not enrollment_authorized(db, actor['id'], device['owner_id'])):
            raise HTTPException(409, 'Active member, club membership and verified loft required')
        expiry = db.execute(text('''INSERT INTO reader_enrollments
          (device_id,owner_id,issued_by,code_hash,expires_at)
          VALUES (:id,:owner,:actor,:hash,clock_timestamp()+interval '10 minutes')
          ON CONFLICT(device_id) DO UPDATE SET owner_id=excluded.owner_id,
          issued_by=excluded.issued_by,code_hash=excluded.code_hash,
          expires_at=excluded.expires_at,consumed_at=NULL,created_at=clock_timestamp()
          RETURNING expires_at'''), {'id': device_id, 'owner': device['owner_id'],
            'actor': actor['id'], 'hash': digest(code)}).scalar_one()
        db.execute(text('''INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
          VALUES (:actor,'device.enrollment_issued','device',:id)'''),
          {'actor': actor['id'], 'id': device_id})
    return {'device_id': device_id, 'enrollment_code': code, 'expires_at': expiry,
            'warning': 'One-use invitation for this owner only. Share privately; no gateway credential is included.'}


class RedeemEnrollment(BaseModel):
    code: str = Field(min_length=20, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')


@router.post('/member/reader-enrollments/redeem', dependencies=[Depends(scan_ip)])
def redeem_enrollment(payload: RedeemEnrollment, actor=Depends(require_member), db: Session=Depends(get_db)):
    consume('reader_enrollment_redeem', actor['id'], 10)
    secret = secrets.token_urlsafe(48)
    with db.begin():
        identity = db.execute(text('SELECT device_id FROM reader_enrollments WHERE code_hash=:hash'),
                              {'hash': digest(payload.code)}).scalar_one_or_none()
        if identity is None:
            raise HTTPException(404, 'Invitation unavailable')
        # All issuance, consumption, rotation and revocation lock the device first.
        device = db.execute(text('''SELECT d.id,d.status,d.reader_adapter,d.reader_protocol,
          l.user_id,l.verified_at FROM devices d JOIN lofts l ON l.id=d.loft_id
          WHERE d.id=:id FOR UPDATE OF d'''), {'id': identity}).mappings().first()
        invite = db.execute(text('''SELECT *,expires_at>clock_timestamp() AS unexpired
          FROM reader_enrollments WHERE device_id=:id AND code_hash=:hash FOR UPDATE'''),
          {'id': identity, 'hash': digest(payload.code)}).mappings().first()
        if (not device or not invite or invite['owner_id'] != actor['id'] or
            device['user_id'] != actor['id'] or device['status'] != 'active' or
            not device['verified_at'] or not invite['unexpired'] or invite['consumed_at'] or
            not enrollment_authorized(db, invite['issued_by'], actor['id'])):
            raise HTTPException(404, 'Invitation unavailable')
        db.execute(text('UPDATE reader_enrollments SET consumed_at=clock_timestamp() WHERE device_id=:id'),
                   {'id': identity})
        db.execute(text('''INSERT INTO device_gateway_credentials(device_id,secret_hash,provisioned_by)
          VALUES (:id,:hash,:issuer) ON CONFLICT(device_id) DO UPDATE
          SET secret_hash=excluded.secret_hash,provisioned_by=excluded.provisioned_by,
              provisioned_at=clock_timestamp(),revoked_at=NULL'''),
          {'id': identity, 'hash': digest(secret), 'issuer': invite['issued_by']})
        db.execute(text('''UPDATE devices SET heartbeat_at=NULL,reported_reader_state=NULL,
          reported_pending_count=NULL,reported_rejected_count=NULL WHERE id=:id'''), {'id': identity})
        db.execute(text('''INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
          VALUES (:actor,'device.enrollment_redeemed','device',:id)'''), {'actor': actor['id'], 'id': identity})
    return {'device_id': identity, 'device_token': secret,
            'reader_adapter': device['reader_adapter'], 'reader_protocol': device['reader_protocol'],
            'warning': 'Credential returned once. Previous reader credential was rotated.'}


@router.get('/member/readers')
def owner_readers(actor=Depends(require_member), db: Session=Depends(get_db)):
    rows = db.execute(text('''SELECT d.id,d.loft_id,d.device_identifier,d.reader_adapter,d.reader_protocol,
      l.name AS loft_name,races.race_id,races.race_name
      FROM devices d JOIN lofts l ON l.id=d.loft_id
      LEFT JOIN LATERAL (
        SELECT DISTINCT r.id AS race_id,r.name AS race_name
        FROM race_entries e JOIN races r ON r.id=e.race_id
        WHERE e.loft_id=l.id AND r.status='active' AND e.status='registered'
          AND e.expected_method='RFID' AND EXISTS(SELECT 1 FROM club_memberships m
              WHERE m.user_id=:owner AND m.club_role='member' AND m.club_id=r.club_id)
      ) races ON TRUE
      WHERE l.user_id=:owner AND l.verified_at IS NOT NULL AND d.status='active'
        AND EXISTS(SELECT 1 FROM club_memberships m WHERE m.user_id=:owner AND m.club_role='member')
      ORDER BY d.device_identifier,races.race_name LIMIT 500'''),
      {'owner': actor['id']}).mappings().all()
    return [dict(row) for row in rows]
