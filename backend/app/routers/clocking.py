"""Phase 4 provisional clocking ingestion.

This is NOT a trusted hardware gateway or official results processor.
QR submissions use server receipt time and remain pending human review.
RFID simulation is administrator-only and remains pending.
"""
import hashlib
import hmac
import base64
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import current_user, require_admin
from ..database import get_db
from ..rate_limits import consume, scan_ip
from ..club_access import check_race_admin, require_race_admin, require_event_admin, check_entry_membership

router = APIRouter(prefix="/clocking", tags=["clocking"])


class QRTokenRequest(BaseModel):
    entry_id: UUID
    expires_in_minutes: int = Field(default=120, ge=1, le=1440)
    include_image: bool = False


class QRScanRequest(BaseModel):
    entry_id: UUID
    token: str = Field(min_length=32, max_length=256)
    idempotency_key: UUID
    capture_source: Literal['manual', 'usb_qr', 'web_camera'] = 'manual'
    client_queued_at: datetime | None = None

    @field_validator('client_queued_at')
    @classmethod
    def aware_queue_time(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('Queue observation time must include a timezone')
        return value


class RFIDSimulatorRequest(BaseModel):
    race_id: UUID
    device_id: UUID
    rfid_uid: str = Field(min_length=1, max_length=200)
    idempotency_key: UUID
    # Device clocks cannot be trusted until hardware protocol and clock attestation exist.
    # This endpoint uses the server time, not a user-supplied timestamp.


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def lock_qr_race(db, entry_id):
    race_id = db.execute(text('SELECT race_id FROM race_entries WHERE id=:id'), {'id': entry_id}).scalar_one_or_none()
    if race_id is None:
        raise HTTPException(404, 'Entry not found')
    # All QR writers acquire race -> idempotency key -> entry -> token locks.
    # SHARE serializes acceptance against close/release without serializing readers.
    db.execute(text('SELECT id FROM races WHERE id=:id FOR SHARE'), {'id': race_id})
    return race_id


@router.post("/qr/tokens", status_code=201)
def issue_qr_token(payload: QRTokenRequest, actor: dict = Depends(require_admin),
                   db: Session = Depends(get_db)):
    consume('qr_issue_account', actor['id'], 30)
    token = secrets.token_urlsafe(48)
    token_id = uuid4()
    expiry = datetime.now(timezone.utc)+timedelta(minutes=payload.expires_in_minutes)
    with db.begin():
        lock_qr_race(db, payload.entry_id)
        entry = db.execute(text("""
            SELECT e.pigeon_id,e.race_id,e.expected_method,e.status,r.status AS race_status,
                   u.role_code
            FROM race_entries e JOIN races r ON r.id=e.race_id
            JOIN lofts l ON l.id=e.loft_id JOIN users u ON u.id=l.user_id
            WHERE e.id=:entry FOR UPDATE OF e
        """), {"entry": payload.entry_id}).mappings().first()
        if not entry:
            raise HTTPException(404, "Entry not found")
        check_race_admin(db, actor, entry["race_id"])
        check_entry_membership(db, payload.entry_id)
        if (entry["expected_method"] != "QR" or entry["role_code"] != "guest"
                or entry["status"] != "registered" or entry["race_status"] not in ("open", "active")):
            raise HTTPException(409, "Entry is not eligible for a guest clocking token")
        db.execute(text("""
            UPDATE qr_tokens SET revoked_at=now()
            WHERE pigeon_id=:pigeon AND race_id=:race AND purpose='clocking' AND revoked_at IS NULL
        """), {"pigeon":entry["pigeon_id"],"race":entry["race_id"]})
        db.execute(text("""
            INSERT INTO qr_tokens(id,pigeon_id,race_id,token_hash,purpose,expires_at)
            VALUES (:id,:pigeon,:race,:hash,'clocking',:expiry)
        """), {"id":token_id,"pigeon":entry["pigeon_id"],"race":entry["race_id"],
                "hash":token_hash(token),
                "expiry":expiry})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'qr_token.issued','qr_token',:id)
        """), {"actor":actor["id"],"id":token_id})
    # Returned once; do not log or store this raw token.
    qr_payload = json.dumps({"version": 1, "entry_id": str(payload.entry_id), "token": token}, separators=(',', ':'))
    result = {"token_id":token_id,"token":token,"entry_id":payload.entry_id,"expires_at":expiry,
            "qr_payload": qr_payload,
            "expires_in_minutes":payload.expires_in_minutes,
            "warning":"Bearer-style QR token; possession alone is insufficient for clocking"}
    if payload.include_image:
        import qrcode
        output = io.BytesIO()
        qrcode.make(qr_payload).save(output, format='PNG')
        result['qr_png_base64'] = base64.b64encode(output.getvalue()).decode('ascii')
    return result


@router.get("/qr/entries")
def guest_qr_entries(actor: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Only the signed-in guest's currently released QR entries."""
    if actor['role_code'] != 'guest':
        raise HTTPException(403, 'Guest account required')
    rows = db.execute(text('''SELECT e.id AS entry_id,r.name AS race_name,p.official_ring_number
        FROM race_entries e JOIN races r ON r.id=e.race_id
        JOIN pigeons p ON p.id=e.pigeon_id JOIN lofts l ON l.id=e.loft_id
        WHERE l.user_id=:actor AND e.expected_method='QR' AND e.status='registered'
        AND r.status='active' AND r.actual_release_at IS NOT NULL AND r.actual_release_at<now()
        AND (r.club_id IS NULL OR EXISTS(SELECT 1 FROM club_memberships m
            WHERE m.club_id=r.club_id AND m.user_id=:actor AND m.club_role IN ('member','guest')))
        ORDER BY r.name,p.official_ring_number LIMIT 1000'''), {'actor': actor['id']}).mappings().all()
    return [dict(row) for row in rows]


@router.post("/qr/scans", status_code=202, dependencies=[Depends(scan_ip)])
def submit_qr_scan(payload: QRScanRequest, actor: dict = Depends(current_user),
                   db: Session = Depends(get_db)):
    if actor["role_code"] != "guest":
        raise HTTPException(403, "Guest account required")
    consume('qr_scan_account', actor['id'], 120)
    event_id = uuid4()
    with db.begin():
        lock_qr_race(db, payload.entry_id)
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': str(payload.idempotency_key)})
        entry = db.execute(text("""
            SELECT e.id,e.pigeon_id,e.race_id,e.expected_method,e.status,
                   r.status AS race_status,r.actual_release_at,l.user_id
            FROM race_entries e JOIN races r ON r.id=e.race_id
            JOIN lofts l ON l.id=e.loft_id WHERE e.id=:entry FOR UPDATE OF e
        """), {"entry":payload.entry_id}).mappings().first()
        if not entry:
            raise HTTPException(404, "Entry not found")
        if entry["user_id"] != actor["id"]:
            raise HTTPException(403, "This entry belongs to another account")
        check_entry_membership(db, payload.entry_id)
        existing = db.execute(text("""
            SELECT c.id,c.entry_id,c.method,c.submitted_by,c.qr_token_id,c.metadata,
                   CASE WHEN EXISTS (
                     SELECT 1 FROM clocking_reviews cr
                     WHERE cr.event_id=c.id AND cr.decision='reject'
                   ) THEN 'invalid' ELSE c.status END AS status
            FROM clocking_events c WHERE c.idempotency_key=:key
        """), {"key":str(payload.idempotency_key)}).mappings().first()
        if existing:
            original_hash = db.execute(text('SELECT token_hash FROM qr_tokens WHERE id=:id'),
                                       {'id': existing['qr_token_id']}).scalar_one_or_none()
            if (existing["entry_id"] != payload.entry_id or existing["method"] != "QR"
                    or existing["submitted_by"] != actor["id"]
                    or original_hash is None or not hmac.compare_digest(original_hash, token_hash(payload.token))
                    or existing["metadata"].get('capture_source', 'manual') != payload.capture_source):
                raise HTTPException(409, "Idempotency key already used")
            queued_at = payload.client_queued_at.isoformat() if payload.client_queued_at else None
            if existing['metadata'].get('client_queued_at') != queued_at:
                raise HTTPException(409, 'Submission timestamp does not match original evidence')
            return {"event_id":existing["id"],"status":existing["status"],"duplicate_request":True,
                    "official_result_created":False}
        if (entry['expected_method'] != 'QR' or entry['status'] != 'registered'
                or entry['race_status'] != 'active' or entry['actual_release_at'] is None):
            raise HTTPException(409, 'Entry is not accepting guest clocking scans')
        qr = db.execute(text('''SELECT id FROM qr_tokens WHERE token_hash=:hash
            AND pigeon_id=:pigeon AND race_id=:race AND purpose='clocking' AND revoked_at IS NULL
            AND (expires_at IS NULL OR expires_at>clock_timestamp()) FOR SHARE'''),
            {'hash': token_hash(payload.token), 'pigeon': entry['pigeon_id'], 'race': entry['race_id']}).scalar_one_or_none()
        if qr is None:
            raise HTTPException(401, 'Invalid or expired clocking token')
        now = datetime.now(timezone.utc)
        if now <= entry["actual_release_at"]:
            raise HTTPException(409, "Race has not been released")
        try:
            db.execute(text("""INSERT INTO clocking_events(id,entry_id,method,qr_token_id,submitted_by,
                idempotency_key,recorded_at,status,metadata) VALUES (:id,:entry,'QR',:qr,:actor,:key,:recorded,
                'pending',CAST(:metadata AS jsonb))"""), {'id':event_id,'entry':payload.entry_id,'qr':qr,
                'actor':actor['id'],'key':str(payload.idempotency_key),'recorded':now,
                'metadata':json.dumps({'capture_source':payload.capture_source,'capture_mode':'operator','timestamp_trusted':False,
                    'client_queued_at':payload.client_queued_at.isoformat() if payload.client_queued_at else None,
                    'device_recorded_at':payload.client_queued_at.isoformat() if payload.client_queued_at else None})})
        except IntegrityError as exc:
            if getattr(exc.orig, 'sqlstate', None) == '23505':
                raise HTTPException(409, 'Submission identifier already used') from exc
            raise
    return {"event_id":event_id,"status":"pending","duplicate_request":False,"official_result_created":False,
            "note":"Submission requires admin review; not an official arrival"}


@router.get('/qr/receipts/{submission_id}')
def qr_receipt(submission_id: UUID, actor: dict = Depends(current_user), db: Session = Depends(get_db)):
    if actor['role_code'] != 'guest':
        raise HTTPException(403, 'Guest account required')
    consume('qr_receipt_account', actor['id'], 300)
    row = db.execute(text('''SELECT c.id AS event_id,c.entry_id,c.status,c.recorded_at,
        v.blocking_flags,cr.decision AS review_decision,r.status AS race_status
        FROM clocking_events c JOIN race_entries e ON e.id=c.entry_id JOIN races r ON r.id=e.race_id
        JOIN lofts l ON l.id=e.loft_id JOIN clocking_event_validation v ON v.event_id=c.id
        LEFT JOIN LATERAL(SELECT decision FROM clocking_reviews WHERE event_id=c.id ORDER BY reviewed_at DESC LIMIT 1) cr ON true
        WHERE c.idempotency_key=:key AND c.method='QR' AND c.submitted_by=:actor AND l.user_id=:actor'''),
        {'key':str(submission_id),'actor':actor['id']}).mappings().first()
    if row is None:
        raise HTTPException(404, 'No received submission found for this account')
    return {**dict(row),'official_result_created':False}


@router.get('/qr/tokens/race/{race_id}')
def list_qr_tokens(race_id: UUID, actor: dict = Depends(require_race_admin), db: Session = Depends(get_db)):
    rows = db.execute(text('''SELECT q.id,q.expires_at,q.revoked_at,e.id AS entry_id,p.official_ring_number
        FROM qr_tokens q JOIN race_entries e ON e.race_id=q.race_id AND e.pigeon_id=q.pigeon_id
        JOIN pigeons p ON p.id=e.pigeon_id WHERE q.race_id=:race AND q.purpose='clocking'
        ORDER BY q.created_at DESC LIMIT 1000'''), {'race':race_id}).mappings().all()
    return [dict(row) for row in rows]


@router.post('/qr/tokens/{token_id}/revoke')
def revoke_qr_token(token_id: UUID, actor: dict = Depends(require_admin), db: Session = Depends(get_db)):
    with db.begin():
        entry = db.execute(text('''SELECT e.id FROM qr_tokens q JOIN race_entries e
            ON e.race_id=q.race_id AND e.pigeon_id=q.pigeon_id WHERE q.id=:id AND q.purpose='clocking' '''),
            {'id':token_id}).scalar_one_or_none()
        if entry is None:
            raise HTTPException(404, 'Clocking token not found')
        race = lock_qr_race(db, entry)
        check_race_admin(db, actor, race)
        db.execute(text('SELECT id FROM race_entries WHERE id=:id FOR UPDATE'), {'id':entry})
        db.execute(text('UPDATE qr_tokens SET revoked_at=coalesce(revoked_at,clock_timestamp()) WHERE id=:id'), {'id':token_id})
        db.execute(text("INSERT INTO audit_logs(actor_id,action,entity_type,entity_id) VALUES (:actor,'qr_token.revoked','qr_token',:id)"),
                   {'actor':actor['id'],'id':token_id})
    return {'token_id':token_id,'revoked':True}


@router.post("/rfid/simulate", status_code=202)
def simulate_rfid(payload: RFIDSimulatorRequest, actor: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    event_id = uuid4()
    with db.begin():
        check_race_admin(db, actor, payload.race_id)
        race = db.execute(text("""
            SELECT status,actual_release_at FROM races WHERE id=:race FOR UPDATE
        """), {"race":payload.race_id}).mappings().first()
        if not race or race["status"] != "active" or race["actual_release_at"] is None:
            raise HTTPException(409, "Race is not active")
        row = db.execute(text("""
            SELECT e.id AS entry_id FROM race_entries e
            JOIN rfid_rings ring ON ring.pigeon_id=e.pigeon_id AND ring.revoked_at IS NULL
            JOIN devices d ON d.loft_id=e.loft_id AND d.status='active'
            WHERE e.race_id=:race AND e.status='registered'
              AND e.expected_method='RFID' AND d.id=:device AND ring.uid=:uid
        """), {"race":payload.race_id,"device":payload.device_id,
               "uid":payload.rfid_uid}).mappings().first()
        if not row:
            raise HTTPException(404, "No matching active device/ring/race entry")
        check_entry_membership(db, row["entry_id"])
        existing = db.execute(text("""
            SELECT c.id,c.entry_id,c.method,c.submitted_by,
                   CASE WHEN EXISTS (
                     SELECT 1 FROM clocking_reviews cr
                     WHERE cr.event_id=c.id AND cr.decision='reject'
                   ) THEN 'invalid' ELSE c.status END AS status
            FROM clocking_events c WHERE c.idempotency_key=:key
        """), {"key":str(payload.idempotency_key)}).mappings().first()
        if existing:
            if (existing["entry_id"] != row["entry_id"] or existing["method"] != "RFID"
                    or existing["submitted_by"] != actor["id"]):
                raise HTTPException(409, "Idempotency key already used")
            return {"event_id":existing["id"],"status":existing["status"],"duplicate_request":True}
        now = datetime.now(timezone.utc)
        if now <= race["actual_release_at"]:
            raise HTTPException(409, "Race has not been released")
        db.execute(text("""
            INSERT INTO clocking_events(id,entry_id,method,device_id,submitted_by,
                idempotency_key,recorded_at,status,metadata)
            VALUES (:id,:entry,'RFID',:device,:actor,:key,:recorded,'pending',
                    CAST(:metadata AS jsonb))
        """), {"id":event_id,"entry":row["entry_id"],"device":payload.device_id,
                "actor":actor["id"],"key":str(payload.idempotency_key),"recorded":now,
                "metadata":'{"simulated":true}'})
    return {"event_id":event_id,"status":"pending","duplicate_request":False,
            "note":"Simulator event only; not trusted hardware evidence"}


@router.get("/events")
def list_pending_events(race_id: UUID, actor: dict = Depends(require_race_admin),
                        db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT c.id,c.entry_id,c.method,c.recorded_at,c.received_at,c.status,
               v.blocking_flags,v.warnings AS validation_warnings,v.is_simulated,
               c.metadata FROM clocking_events c
        JOIN clocking_event_validation v ON v.event_id=c.id
        JOIN race_entries e ON e.id=c.entry_id
        WHERE e.race_id=:race ORDER BY c.received_at DESC LIMIT 500
    """), {"race":race_id})
    return [dict(row._mapping) for row in rows]


class EventReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=8, max_length=1000)


@router.post("/events/{event_id}/review")
def review_event(event_id: UUID, payload: EventReviewRequest,
                 actor: dict = Depends(require_event_admin), db: Session = Depends(get_db)):
    """Record human review, but do not produce or certify official results."""
    with db.begin():
        event = db.execute(text("""
            SELECT c.id,c.status,r.status AS race_status
            FROM clocking_events c JOIN race_entries e ON e.id=c.entry_id
            JOIN races r ON r.id=e.race_id
            WHERE c.id=:id FOR UPDATE OF c
        """), {"id":event_id}).mappings().first()
        if event is None:
            raise HTTPException(404, "Event not found")
        if event["race_status"] == "finalized":
            raise HTTPException(409, "Finalized races cannot be reviewed")
        if event["status"] != "pending":
            raise HTTPException(409, "Only pending events can be reviewed")
        previous = db.execute(text("""
            SELECT id FROM clocking_reviews WHERE event_id=:id LIMIT 1
        """), {"id":event_id}).scalar_one_or_none()
        if previous:
            raise HTTPException(409, "Event has already been reviewed")
        review_id = uuid4()
        db.execute(text("""
            INSERT INTO clocking_reviews(id,event_id,reviewed_by,decision,reason)
            VALUES (:id,:event,:actor,:decision,:reason)
        """), {"id":review_id,"event":event_id,"actor":actor["id"],
                "decision":payload.decision,"reason":payload.reason})
        if payload.decision == "reject":
            db.execute(text("""
                UPDATE clocking_events SET status='invalid',rejection_reason=:reason WHERE id=:id
            """), {"id":event_id,"reason":payload.reason})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'clocking_event.reviewed','clocking_event',:id)
        """), {"actor":actor["id"],"id":event_id})
    return {"event_id":event_id,"review_id":review_id,"decision":payload.decision,
            "event_status":"invalid" if payload.decision=="reject" else "pending",
            "official_result_created":False}
