"""Phase 4 provisional clocking ingestion.

This is NOT a trusted hardware gateway or official results processor.
QR submissions use server receipt time and remain pending human review.
RFID simulation is administrator-only and remains pending.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import current_user, require_admin
from ..database import get_db

router = APIRouter(prefix="/clocking", tags=["clocking"])


class QRTokenRequest(BaseModel):
    entry_id: UUID
    expires_in_minutes: int = Field(default=120, ge=1, le=1440)


class QRScanRequest(BaseModel):
    entry_id: UUID
    token: str = Field(min_length=32, max_length=256)
    idempotency_key: UUID


class RFIDSimulatorRequest(BaseModel):
    race_id: UUID
    device_id: UUID
    rfid_uid: str = Field(min_length=1, max_length=200)
    idempotency_key: UUID
    # Device clocks cannot be trusted until hardware protocol and clock attestation exist.
    # This endpoint uses the server time, not a user-supplied timestamp.


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/qr/tokens", status_code=201)
def issue_qr_token(payload: QRTokenRequest, actor: dict = Depends(require_admin),
                   db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(48)
    token_id = uuid4()
    with db.begin():
        entry = db.execute(text("""
            SELECT e.pigeon_id,e.race_id,e.expected_method,e.status,r.status AS race_status,
                   u.role_code
            FROM race_entries e JOIN races r ON r.id=e.race_id
            JOIN lofts l ON l.id=e.loft_id JOIN users u ON u.id=l.user_id
            WHERE e.id=:entry FOR UPDATE OF e
        """), {"entry": payload.entry_id}).mappings().first()
        if not entry:
            raise HTTPException(404, "Entry not found")
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
                "expiry":datetime.now(timezone.utc)+timedelta(minutes=payload.expires_in_minutes)})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'qr_token.issued','qr_token',:id)
        """), {"actor":actor["id"],"id":token_id})
    # Returned once; do not log or store this raw token.
    return {"token_id":token_id,"token":token,"entry_id":payload.entry_id,
            "expires_in_minutes":payload.expires_in_minutes,
            "warning":"Bearer-style QR token; possession alone is insufficient for clocking"}


@router.post("/qr/scans", status_code=202)
def submit_qr_scan(payload: QRScanRequest, actor: dict = Depends(current_user),
                   db: Session = Depends(get_db)):
    if actor["role_code"] != "guest":
        raise HTTPException(403, "Guest account required")
    event_id = uuid4()
    with db.begin():
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
        if (entry["expected_method"] != "QR" or entry["status"] != "registered"
                or entry["race_status"] != "active" or entry["actual_release_at"] is None):
            raise HTTPException(409, "Entry is not accepting guest clocking scans")
        qr = db.execute(text("""
            SELECT id FROM qr_tokens
            WHERE token_hash=:hash AND pigeon_id=:pigeon AND race_id=:race
              AND purpose='clocking' AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at>now())
        """), {"hash":token_hash(payload.token),"pigeon":entry["pigeon_id"],
               "race":entry["race_id"]}).scalar_one_or_none()
        if qr is None:
            raise HTTPException(401, "Invalid or expired clocking token")
        existing = db.execute(text("""
            SELECT id,entry_id,method FROM clocking_events WHERE idempotency_key=:key
        """), {"key":str(payload.idempotency_key)}).mappings().first()
        if existing:
            if existing["entry_id"] != payload.entry_id or existing["method"] != "QR":
                raise HTTPException(409, "Idempotency key already used")
            return {"event_id":existing["id"],"status":"pending","duplicate_request":True}
        now = datetime.now(timezone.utc)
        if now <= entry["actual_release_at"]:
            raise HTTPException(409, "Race has not been released")
        db.execute(text("""
            INSERT INTO clocking_events(id,entry_id,method,qr_token_id,submitted_by,
                idempotency_key,recorded_at,status)
            VALUES (:id,:entry,'QR',:qr,:actor,:key,:recorded,'pending')
        """), {"id":event_id,"entry":payload.entry_id,"qr":qr,"actor":actor["id"],
                "key":str(payload.idempotency_key),"recorded":now})
    return {"event_id":event_id,"status":"pending","duplicate_request":False,
            "note":"Submission requires admin review; not an official arrival"}


@router.post("/rfid/simulate", status_code=202)
def simulate_rfid(payload: RFIDSimulatorRequest, actor: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    event_id = uuid4()
    with db.begin():
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
        existing = db.execute(text("""
            SELECT id,entry_id,method FROM clocking_events WHERE idempotency_key=:key
        """), {"key":str(payload.idempotency_key)}).mappings().first()
        if existing:
            if existing["entry_id"] != row["entry_id"] or existing["method"] != "RFID":
                raise HTTPException(409, "Idempotency key already used")
            return {"event_id":existing["id"],"status":"pending","duplicate_request":True}
        now = datetime.now(timezone.utc)
        if now <= race["actual_release_at"]:
            raise HTTPException(409, "Race has not been released")
        db.execute(text("""
            INSERT INTO clocking_events(id,entry_id,method,device_id,submitted_by,
                idempotency_key,recorded_at,status,metadata)
            VALUES (:id,:entry,'RFID',:device,:actor,:key,:recorded,'pending',
                    '{"simulated":true}'::jsonb)
        """), {"id":event_id,"entry":row["entry_id"],"device":payload.device_id,
                "actor":actor["id"],"key":str(payload.idempotency_key),"recorded":now})
    return {"event_id":event_id,"status":"pending","duplicate_request":False,
            "note":"Simulator event only; not trusted hardware evidence"}


@router.get("/events")
def list_pending_events(race_id: UUID, actor: dict = Depends(require_admin),
                        db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT c.id,c.entry_id,c.method,c.recorded_at,c.received_at,c.status,
               c.metadata FROM clocking_events c
        JOIN race_entries e ON e.id=c.entry_id
        WHERE e.race_id=:race ORDER BY c.received_at DESC LIMIT 500
    """), {"race":race_id})
    return [dict(row._mapping) for row in rows]
