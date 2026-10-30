"""Facebook Messenger inbound clocking (Phase 6F).

Meta POST requests are authenticated with X-Hub-Signature-256 over the raw
request bytes. A PSID is Page-scoped and must be linked by a club official.
Supported message: CLOCK <entry_uuid> <race-bound-qr-token>
Messages are claims only, never official timing evidence.
"""
import hashlib
import hmac
import os
import re
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_db
from .clocking import QRScanRequest, submit_qr_scan

router = APIRouter(prefix="/clocking/messenger", tags=["messenger-clocking"])
COMMAND = re.compile(r"^CLOCK\s+([0-9a-fA-F-]{36})\s+([A-Za-z0-9_-]{32,256})$", re.ASCII)


class LinkMessengerAccount(BaseModel):
    page_id: str = Field(min_length=1, max_length=120)
    sender_psid: str = Field(min_length=1, max_length=120)
    user_id: UUID


@router.post("/links", status_code=201)
def link_account(payload: LinkMessengerAccount, actor: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    with db.begin():
        user = db.execute(text("SELECT role_code,status FROM users WHERE id=:id"),
                          {"id":payload.user_id}).mappings().first()
        if not user or user["role_code"] != "guest" or user["status"] != "active":
            raise HTTPException(422, "Only active guest accounts may be linked")
        existing = db.execute(text("""
            SELECT user_id FROM messenger_account_links
            WHERE page_id=:page AND sender_psid=:psid
        """), {"page":payload.page_id,"psid":payload.sender_psid}).scalar_one_or_none()
        if existing:
            raise HTTPException(409, "Messenger identity already linked")
        db.execute(text("""
            INSERT INTO messenger_account_links(page_id,sender_psid,user_id,linked_by)
            VALUES (:page,:psid,:user,:admin)
        """), {"page":payload.page_id,"psid":payload.sender_psid,
                "user":payload.user_id,"admin":actor["id"]})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:admin,'messenger.account_linked','user',:user)
        """), {"admin":actor["id"],"user":payload.user_id})
    return {"linked":True,"page_id":payload.page_id,"user_id":payload.user_id}


@router.get("/webhook")
def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    from fastapi.responses import PlainTextResponse
    configured = os.getenv("META_VERIFY_TOKEN", "")
    if (len(configured) < 32 or mode != "subscribe" or verify_token is None
            or not hmac.compare_digest(configured, verify_token)):
        raise HTTPException(403, "Webhook verification failed")
    return PlainTextResponse(challenge or "")


@router.post("/webhook")
async def messenger_webhook(request: Request, db: Session = Depends(get_db),
                            x_hub_signature_256: str | None = Header(default=None)):
    secret = os.getenv("META_APP_SECRET", "")
    if len(secret) < 16:
        raise HTTPException(503, "Messenger webhook not configured")
    raw = await request.body()
    if len(raw) > 65536:
        raise HTTPException(413, "Webhook too large")
    expected = "sha256=" + hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(expected,x_hub_signature_256):
        raise HTTPException(401, "Invalid Meta signature")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid JSON") from None
    if not isinstance(body,dict) or body.get("object") != "page":
        raise HTTPException(400, "Unexpected webhook object")
    allowed_page = os.getenv("META_PAGE_ID", "")
    if not allowed_page:
        raise HTTPException(503, "Meta Page not configured")
    processed = 0
    ignored = 0
    # Never trust sender IDs without explicit admin-approved account linking.
    for item in body.get("entry",[])[:20]:
        if not isinstance(item,dict) or str(item.get("id")) != allowed_page:
            ignored += 1
            continue
        for event in item.get("messaging",[])[:30]:
            if not isinstance(event,dict):
                ignored += 1
                continue
            msg = event.get("message")
            sender = event.get("sender") or {}
            if (not isinstance(msg,dict) or msg.get("is_echo")
                    or not isinstance(sender,dict) or not msg.get("mid")):
                ignored += 1
                continue
            match = COMMAND.fullmatch(msg.get("text","")) if isinstance(msg.get("text"),str) else None
            if not match:
                ignored += 1
                continue
            try:
                entry_id = UUID(match.group(1))
            except ValueError:
                ignored += 1
                continue
            psid = str(sender.get("id",""))
            mid = str(msg["mid"])
            if not psid or not mid or len(mid) > 200:
                ignored += 1
                continue
            with db.begin():
                actor = db.execute(text("""
                    SELECT u.id,u.role_code,u.status FROM messenger_account_links l
                    JOIN users u ON u.id=l.user_id
                    WHERE l.page_id=:page AND l.sender_psid=:psid
                """), {"page":allowed_page,"psid":psid}).mappings().first()
                if not actor or actor["status"] != "active" or actor["role_code"] != "guest":
                    ignored += 1
                    continue
                prior = db.execute(text("""
                    SELECT s.event_id,c.entry_id,s.provenance->>'message_sha256' AS fingerprint
                    FROM clocking_event_sources s JOIN clocking_events c ON c.id=s.event_id
                    WHERE s.provider='meta_messenger' AND s.provider_message_id=:mid
                """), {"mid":mid}).mappings().first()
                fingerprint = hashlib.sha256((allowed_page+"|"+psid+"|"+msg["text"]).encode()).hexdigest()
                if prior:
                    if prior["entry_id"] != entry_id or prior["fingerprint"] != fingerprint:
                        raise HTTPException(409,"Messenger message ID reused")
                    processed += 1
                    continue
            key = UUID(bytes=hashlib.sha256(("messenger:"+allowed_page+":"+mid).encode()).digest()[:16])
            try:
                result = submit_qr_scan(QRScanRequest(
                    entry_id=entry_id,token=match.group(2),idempotency_key=key),
                    actor=dict(actor),db=db)
            except HTTPException:
                # Invalid user-submitted commands must not prevent other events
                # in the same Meta batch from being processed.
                ignored += 1
                continue
            with db.begin():
                source = db.execute(text("""
                    SELECT channel,provider_message_id FROM clocking_event_sources
                    WHERE event_id=:id FOR UPDATE
                """), {"id":result["event_id"]}).mappings().first()
                if source:
                    if source["channel"] != "messenger" or source["provider_message_id"] != mid:
                        raise HTTPException(409,"Event belongs to another channel")
                else:
                    db.execute(text("""
                        INSERT INTO clocking_event_sources
                        (event_id,channel,evidence_type,provider,provider_message_id,provenance)
                        VALUES (:id,'messenger','manual_claim','meta_messenger',:mid,
                                jsonb_build_object('meta_signature_verified',true,
                                                   'clock_integrity_verified',false,
                                                   'message_sha256',CAST(:fingerprint AS text)))
                    """), {"id":result["event_id"],"mid":mid,"fingerprint":fingerprint})
            processed += 1
    return {"accepted":True,"processed":processed,"ignored":ignored,
            "official_result_created":False}
