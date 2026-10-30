"""Phase 6C: administrator-only visibility into clocking channel provenance.

This is an inspection API, not a clocking submission API. External providers
must use authenticated adapters with replay protection before writing events.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/clocking", tags=["clocking-provenance"])


@router.get("/events/{event_id}/source")
def get_clocking_source(event_id: UUID, actor: dict = Depends(require_admin),
                        db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT c.id AS event_id, c.method AS legacy_method, c.recorded_at,
               c.received_at, c.status, s.channel, s.evidence_type,
               s.provider, s.provider_message_id, s.external_reference,
               s.claimed_arrival_at, s.device_recorded_at,
               s.clock_integrity_verified, s.provenance
        FROM clocking_events c
        LEFT JOIN clocking_event_sources s ON s.event_id=c.id
        WHERE c.id=:event
    """), {"event": event_id}).mappings().first()
    if row is None:
        raise HTTPException(404, "Clocking event not found")
    return {**dict(row), "official_result_created": False,
            "note": "Source metadata is evidence, not proof of arrival or clock integrity"}
