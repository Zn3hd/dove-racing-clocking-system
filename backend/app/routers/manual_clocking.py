"""Phase 6D web/mobile guest arrival adapter.

Uses the existing ownership-checked, race-bound, expiring QR token ingestion.
A channel label is evidence provenance, not an independent arrival proof.
"""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from .clocking import QRScanRequest, submit_qr_scan

router = APIRouter(prefix="/clocking", tags=["clocking-channels"])

class ManualArrival(BaseModel):
    entry_id: UUID
    token: str = Field(min_length=32, max_length=256)
    idempotency_key: UUID
    channel: Literal["web", "mobile"]

@router.post("/manual/arrivals", status_code=202)
def submit_manual_arrival(payload: ManualArrival,
                          actor: dict = Depends(current_user),
                          db: Session = Depends(get_db)):
    """Guest web/mobile clocking, pending in-person club verification.

    Delegates authentication, ownership, active-race checks, token validation,
    and idempotency to the existing QR ingestion path. Does not accept user
    arrival timestamps or GPS coordinates.
    """
    if actor["role_code"] != "guest":
        raise HTTPException(403, "Guest account required")
    result = submit_qr_scan(
        QRScanRequest(entry_id=payload.entry_id, token=payload.token,
                      idempotency_key=payload.idempotency_key),
        actor=actor, db=db
    )
    # Source metadata is committed after the validated event. Retry is safe;
    # a competing channel may not relabel an already recorded submission.
    with db.begin():
        existing = db.execute(text("""
            SELECT channel FROM clocking_event_sources WHERE event_id=:id FOR UPDATE
        """), {"id": result["event_id"]}).scalar_one_or_none()
        if existing is not None and existing != payload.channel:
            # Legacy QR events are intentionally not reclassified.
            if existing != "qr":
                raise HTTPException(409, "Submission already recorded through another channel")
            # A QR scan from another route cannot be silently relabeled.
            prior = db.execute(text("""
                SELECT provenance->>'manual_adapter' FROM clocking_event_sources
                WHERE event_id=:id
            """), {"id": result["event_id"]}).scalar_one_or_none()
            if prior != "true":
                if result["duplicate_request"]:
                    raise HTTPException(409, "Existing QR event is not a manual submission")
            db.execute(text("""
                UPDATE clocking_event_sources
                SET channel=:channel,evidence_type='manual_claim',
                    provenance=jsonb_build_object('manual_adapter', true, 'clock_integrity_verified', false)
                WHERE event_id=:id
            """), {"id": result["event_id"], "channel": payload.channel})
        elif existing is None:
            db.execute(text("""
                INSERT INTO clocking_event_sources(event_id,channel,evidence_type,provenance)
                VALUES (:id,:channel,'manual_claim',
                        jsonb_build_object('manual_adapter', true, 'clock_integrity_verified', false))
            """), {"id":result["event_id"],"channel":payload.channel})
    return {**result, "channel": payload.channel, "official_result_created": False,
            "note": "Manual arrival claim; requires in-person club verification"}
