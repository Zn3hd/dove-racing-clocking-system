"""Provider-neutral SMS gateway adapter (Phase 6E).

An SMS gateway must POST the exact JSON body and an HMAC-SHA256 hex digest
in X-Dove-SMS-Signature. This is not a public unauthenticated SMS endpoint.
The SMS body must contain a previously issued race-bound QR token; SMS sender
numbers alone are not trusted. Every event remains provisional.
"""
import hashlib
import hmac
import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from .clocking import QRScanRequest, submit_qr_scan

router = APIRouter(prefix="/clocking/sms", tags=["sms-clocking"])


class SMSArrival(BaseModel):
    provider: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    message_id: str = Field(min_length=1, max_length=200)
    sender: str = Field(min_length=7, max_length=24)
    entry_id: UUID
    token: str = Field(min_length=32, max_length=256)


@router.post("/webhook", status_code=202)
async def sms_webhook(request: Request,
                      x_dove_sms_signature: str | None = Header(default=None),
                      db: Session = Depends(get_db)):
    secret = os.getenv("SMS_WEBHOOK_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(503, "SMS gateway not configured")
    raw = await request.body()
    if len(raw) > 8192:
        raise HTTPException(413, "SMS webhook payload too large")
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not x_dove_sms_signature or not hmac.compare_digest(
            x_dove_sms_signature.lower(), expected):
        raise HTTPException(401, "Invalid gateway signature")
    try:
        payload = SMSArrival.model_validate_json(raw)
    except ValueError:
        raise HTTPException(422, "Invalid SMS payload") from None

    fingerprint = hashlib.sha256(raw).hexdigest()
    # One phone number may be shared across users; refuse ambiguous matches.
    with db.begin():
        rows = db.execute(text("""
            SELECT u.id,u.role_code,u.status FROM race_entries e
            JOIN lofts l ON l.id=e.loft_id
            JOIN users u ON u.id=l.user_id
            WHERE e.id=:entry AND u.phone=:sender
        """), {"entry":payload.entry_id,"sender":payload.sender}).mappings().all()
        if len(rows) != 1 or rows[0]["role_code"] != "guest" or rows[0]["status"] != "active":
            raise HTTPException(403, "SMS sender does not match an active guest entry")
        actor = dict(rows[0])
        existing = db.execute(text("""
            SELECT s.event_id, c.entry_id, s.provenance->>'payload_sha256' AS payload_sha256 FROM clocking_event_sources s
            JOIN clocking_events c ON c.id=s.event_id
            WHERE s.provider=:provider AND s.provider_message_id=:message
        """), {"provider":payload.provider,"message":payload.message_id}).mappings().first()
        if existing:
            if existing["entry_id"] != payload.entry_id or existing["payload_sha256"] != fingerprint:
                raise HTTPException(409, "Provider message ID already assigned")
            return {"event_id":existing["event_id"],"duplicate_request":True,
                    "status":"pending","official_result_created":False}

    # Deterministic key is scoped by provider + message ID.
    key = UUID(bytes=hashlib.sha256(
        f"sms:{payload.provider}:{payload.message_id}".encode()).digest()[:16])
    result = submit_qr_scan(
        QRScanRequest(entry_id=payload.entry_id, token=payload.token,
                      idempotency_key=key), actor=actor, db=db)
    with db.begin():
        source = db.execute(text("""
            SELECT channel,provider,provider_message_id,
                   provenance->>'payload_sha256' AS payload_sha256
            FROM clocking_event_sources WHERE event_id=:id FOR UPDATE
        """), {"id":result["event_id"]}).mappings().first()
        if source is not None:
            if (source["channel"] != "sms" or source["provider"] != payload.provider
                    or source["provider_message_id"] != payload.message_id
                    or source["payload_sha256"] != fingerprint):
                raise HTTPException(409, "Event already attributed to another source")
        else:
            db.execute(text("""
                INSERT INTO clocking_event_sources
                (event_id,channel,evidence_type,provider,provider_message_id,provenance)
                VALUES (:id,'sms','manual_claim',:provider,:message,
                        jsonb_build_object('gateway_signature_verified',true,
                                           'clock_integrity_verified',false,
                                           'payload_sha256',:fingerprint))
            """), {"id":result["event_id"],"provider":payload.provider,
                   "message":payload.message_id,"fingerprint":fingerprint})
    return {"event_id":result["event_id"],"duplicate_request":result["duplicate_request"],
            "status":"pending","official_result_created":False,
            "note":"SMS arrival claim only; in-person verification required"}
