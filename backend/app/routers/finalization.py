"""Race closing and conservative official finalization.

Simulated RFID and QR-only evidence are not sufficient for official
certification in V1: trusted arrival verification is still outstanding.
This module implements safe state transitions and blocks premature publishing.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..club_access import require_race_admin
from ..database import get_db

router = APIRouter(prefix="/races", tags=["finalization"])

@router.post("/{race_id}/close")
def close_race(race_id: UUID, db: Session = Depends(get_db),
               actor: dict = Depends(require_race_admin)):
    with db.begin():
        status = db.execute(text("SELECT status FROM races WHERE id=:id FOR UPDATE"),
                            {"id":race_id}).scalar_one_or_none()
        if status is None:
            raise HTTPException(404, "Race not found")
        if status != "active":
            raise HTTPException(409, "Only active races may be closed")
        db.execute(text("UPDATE races SET status='closed' WHERE id=:id"), {"id":race_id})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'race.closed','race',:race)
        """), {"actor":actor["id"],"race":race_id})
    return {"race_id":race_id,"status":"closed","official":False}

@router.post("/{race_id}/finalize")
def finalize_race(race_id: UUID, db: Session = Depends(get_db),
                  actor: dict = Depends(require_race_admin)):
    """Fail closed until trustworthy hardware/guest evidence is implemented.

    The current RFID route is explicitly a simulator and QR scan is a
    self-submitted event. Human approval alone cannot establish an
    independently verified arrival. Never publish these as official.
    """
    with db.begin():
        race = db.execute(text("SELECT status FROM races WHERE id=:id FOR UPDATE"),
                          {"id":race_id}).scalar_one_or_none()
        if race is None:
            raise HTTPException(404, "Race not found")
        if race != "closed":
            raise HTTPException(409, "Only closed races may be finalized")
        raise HTTPException(
            409,
            "Official finalization is disabled until trusted RFID ingestion, "
            "independent guest arrival verification, and acceptance rules "
            "have been implemented and tested."
        )
