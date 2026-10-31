"""ESP32-compatible prototype ingestion gateway.

Uses a per-device opaque bearer token over TLS (hashed at rest), not an
attested clock. Arrival time is server receipt time. Offline buffered events
are accepted as evidence only, never automatically backdated or finalized.
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_db
from ..club_access import check_loft_admin, check_entry_membership

router=APIRouter(prefix="/devices",tags=["device-gateway"])

def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

class GatewayArrival(BaseModel):
    message_id: UUID
    race_id: UUID
    ring_uid: str = Field(min_length=1,max_length=200)
    offline_buffered: bool = False
    device_recorded_at: datetime | None = None

@router.post("/{device_id}/provision")
def provision(device_id: UUID, actor: dict=Depends(require_admin),
              db: Session=Depends(get_db)):
    secret=secrets.token_urlsafe(48)
    with db.begin():
        loft = db.execute(text("SELECT loft_id FROM devices WHERE id=:id"),
                          {"id": device_id}).scalar_one_or_none()
        if loft is None:
            raise HTTPException(404, "Active device not found")
        check_loft_admin(db, actor, loft)
        device=db.execute(text("SELECT id FROM devices WHERE id=:id AND status='active' FOR UPDATE"),
                          {"id":device_id}).scalar_one_or_none()
        if device is None:
            raise HTTPException(404,"Active device not found")
        db.execute(text("""
            INSERT INTO device_gateway_credentials(device_id,secret_hash,provisioned_by)
            VALUES (:device,:hash,:actor)
            ON CONFLICT(device_id) DO UPDATE
            SET secret_hash=excluded.secret_hash,provisioned_by=excluded.provisioned_by,
                provisioned_at=now(),revoked_at=NULL
        """),{"device":device_id,"hash":digest(secret),"actor":actor["id"]})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'device.gateway_credentials_rotated','device',:device)
        """),{"actor":actor["id"],"device":device_id})
    return {"device_id":device_id,"device_token":secret,
            "warning":"Token displayed once. Store securely; HTTPS required. Prototype only."}

@router.post("/{device_id}/arrivals",status_code=202)
def receive_arrival(device_id: UUID,payload: GatewayArrival,
                    x_device_token: str | None=Header(default=None),
                    db: Session=Depends(get_db)):
    if not x_device_token or len(x_device_token)>256:
        raise HTTPException(401,"Device token required")
    event_id=uuid4()
    fingerprint=digest(json.dumps(payload.model_dump(mode="json"),sort_keys=True))
    with db.begin():
        device=db.execute(text("""
            SELECT d.loft_id,d.status,g.secret_hash,g.revoked_at
            FROM devices d JOIN device_gateway_credentials g ON g.device_id=d.id
            WHERE d.id=:id FOR UPDATE OF d
        """),{"id":device_id}).mappings().first()
        if not device or device["status"]!="active" or device["revoked_at"] is not None or not hmac.compare_digest(device["secret_hash"],digest(x_device_token)):
            raise HTTPException(401,"Device authentication failed")
        prior=db.execute(text("""
            SELECT payload_hash,event_id FROM device_gateway_messages
            WHERE device_id=:device AND message_id=:message
        """),{"device":device_id,"message":payload.message_id}).mappings().first()
        if prior:
            if prior["payload_hash"]!=fingerprint:
                raise HTTPException(409,"Message identifier reused with different content")
            prior_entry = db.execute(text("SELECT entry_id FROM clocking_events WHERE id=:id"),
                                     {"id": prior["event_id"]}).scalar_one()
            check_entry_membership(db, prior_entry)
            return {"event_id":prior["event_id"],"duplicate_request":True,
                    "status":"pending","official_result_created":False}
        race=db.execute(text("""
            SELECT status,actual_release_at FROM races WHERE id=:id
        """),{"id":payload.race_id}).mappings().first()
        if not race or race["status"]!="active" or race["actual_release_at"] is None:
            raise HTTPException(409,"Race not active")
        entry=db.execute(text("""
            SELECT e.id FROM race_entries e
            JOIN rfid_rings ring ON ring.pigeon_id=e.pigeon_id AND ring.revoked_at IS NULL
            WHERE e.race_id=:race AND e.loft_id=:loft AND e.status='registered'
              AND e.expected_method='RFID' AND ring.uid=:ring
        """),{"race":payload.race_id,"loft":device["loft_id"],"ring":payload.ring_uid}).scalar_one_or_none()
        if entry is None:
            raise HTTPException(404,"Registered ring not found at device loft")
        check_entry_membership(db, entry)
        now=datetime.now(timezone.utc)
        if now<=race["actual_release_at"]:
            raise HTTPException(409,"Race has not been released")
        metadata=json.dumps({"gateway":"esp32-prototype","offline_buffered":payload.offline_buffered,
                             "device_recorded_at":payload.device_recorded_at.isoformat() if payload.device_recorded_at else None,
                             "timestamp_trusted":False})
        db.execute(text("""
            INSERT INTO clocking_events(id,entry_id,method,device_id,idempotency_key,
                                        recorded_at,status,metadata)
            VALUES (:id,:entry,'RFID',:device,:key,:time,'pending',CAST(:meta AS jsonb))
        """),{"id":event_id,"entry":entry,"device":device_id,
              "key":f"gateway:{device_id}:{payload.message_id}","time":now,"meta":metadata})
        db.execute(text("""
            INSERT INTO device_gateway_messages(device_id,message_id,payload_hash,event_id)
            VALUES (:device,:message,:hash,:event)
        """),{"device":device_id,"message":payload.message_id,"hash":fingerprint,"event":event_id})
        db.execute(text("UPDATE devices SET last_seen_at=now() WHERE id=:device"),{"device":device_id})
    return {"event_id":event_id,"duplicate_request":False,
            "status":"pending","official_result_created":False,
            "timestamp_policy":"server_receipt; offline time untrusted"}
