"""Shared authorization for races and their clocking evidence.

Historical races without a club remain accessible only to their creator.
No historical ownership is assigned implicitly.
"""
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import require_admin
from .database import get_db


def managed_club(db: Session, actor: dict, club_id: UUID | None = None) -> UUID:
    if club_id is None:
        club_id = db.execute(text("SELECT id FROM clubs LIMIT 1")).scalar_one_or_none()
    allowed = db.execute(text("""SELECT EXISTS(SELECT 1 FROM club_memberships
        WHERE club_id=:club AND user_id=:actor AND club_role='admin')"""),
        {"club": club_id, "actor": actor["id"]}).scalar()
    if not allowed:
        raise HTTPException(403, "Club administrator required")
    return club_id


def check_user_admin(db: Session, actor: dict, user_id: UUID) -> None:
    # Preserve pre-club pilot workflows until the first club is created.
    if not db.execute(text("SELECT EXISTS(SELECT 1 FROM clubs)")).scalar():
        return
    allowed = db.execute(text("""SELECT EXISTS(
        SELECT 1 FROM club_memberships a JOIN club_memberships m ON m.club_id=a.club_id
        WHERE a.user_id=:actor AND a.club_role='admin' AND m.user_id=:user
          AND m.club_role IN ('member','guest'))"""),
        {"actor": actor["id"], "user": user_id}).scalar()
    if not allowed:
        raise HTTPException(403, "Participant club administrator required")


def check_loft_admin(db: Session, actor: dict, loft_id: UUID) -> None:
    owner = db.execute(text("SELECT user_id FROM lofts WHERE id=:id"),
                       {"id": loft_id}).scalar_one_or_none()
    if owner is None:
        raise HTTPException(404, "Loft not found")
    check_user_admin(db, actor, owner)


def check_entry_membership(db: Session, entry_id: UUID) -> None:
    allowed = db.execute(text("""SELECT EXISTS(
        SELECT 1 FROM race_entries e JOIN races r ON r.id=e.race_id
        JOIN lofts l ON l.id=e.loft_id JOIN users u ON u.id=l.user_id
        WHERE e.id=:entry AND u.status='active'
          AND (r.club_id IS NULL OR EXISTS(SELECT 1 FROM club_memberships m
               WHERE m.club_id=r.club_id AND m.user_id=u.id
                 AND m.club_role IN ('member','guest'))))"""),
        {"entry": entry_id}).scalar()
    if not allowed:
        raise HTTPException(403, "Active race club membership required")


def check_race_admin(db: Session, actor: dict, race_id: UUID) -> None:
    race = db.execute(text("""
        SELECT r.club_id,r.created_by,
               EXISTS (SELECT 1 FROM club_memberships m
                       WHERE m.club_id=r.club_id AND m.user_id=:actor
                         AND m.club_role='admin') AS club_admin
        FROM races r WHERE r.id=:race
    """), {"actor": actor["id"], "race": race_id}).mappings().first()
    if race is None:
        raise HTTPException(404, "Race not found")
    allowed = (race["created_by"] == actor["id"] if race["club_id"] is None
               else race["club_admin"])
    if not allowed:
        raise HTTPException(403, "Race administrator required")


def require_race_admin(race_id: UUID, actor: dict = Depends(require_admin),
                       db: Session = Depends(get_db)) -> dict:
    try:
        check_race_admin(db, actor, race_id)
    finally:
        # End the dependency's read transaction before endpoint writes begin.
        db.rollback()
    return actor


def require_event_admin(event_id: UUID, actor: dict = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict:
    try:
        race_id = db.execute(text("""
            SELECT e.race_id FROM clocking_events c
            JOIN race_entries e ON e.id=c.entry_id WHERE c.id=:event
        """), {"event": event_id}).scalar_one_or_none()
        if race_id is None:
            raise HTTPException(404, "Clocking event not found")
        check_race_admin(db, actor, race_id)
    finally:
        db.rollback()
    return actor
