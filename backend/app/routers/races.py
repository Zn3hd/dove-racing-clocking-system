"""Development-only race management routes. All writes require admin token."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import RaceCreate
from ..auth import require_admin
from ..club_access import require_race_admin

router = APIRouter(prefix="/races", tags=["races"], )

@router.post("", status_code=201)
def create_race(payload: RaceCreate, db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    rid = uuid4()
    with db.begin():
        # Serialize the transition from historical races to the first club.
        db.execute(text("SELECT pg_advisory_xact_lock(7462091323)"))
        club_id = payload.club_id
        if club_id is None:
            club_id = db.execute(text("SELECT id FROM clubs LIMIT 1")).scalar_one_or_none()
        if club_id is not None:
            allowed = db.execute(text("""SELECT EXISTS(SELECT 1 FROM club_memberships
                WHERE club_id=:club AND user_id=:actor AND club_role='admin')"""),
                {"club": club_id, "actor": actor["id"]}).scalar()
            if not allowed:
                raise HTTPException(403, "Club administrator required")
        db.execute(text("""
            INSERT INTO races(id,club_id,name,release_latitude,release_longitude,scheduled_release_at,
              minimum_speed_mpm,display_speed_unit,guest_ranking_mode,status,created_by)
            VALUES (:id,:club,:name,:lat,:lon,:scheduled,:minimum,:unit,:mode,'draft',:actor)
        """), {"id":rid,"club":club_id,"name":payload.name,"lat":payload.release_latitude,
                 "lon":payload.release_longitude,"scheduled":payload.scheduled_release_at,
                 "minimum":payload.minimum_speed_mpm,"unit":payload.display_speed_unit,
                 "mode":payload.guest_ranking_mode,"actor":actor["id"]})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id,after_state)
            VALUES (:actor,'race.created','race',:id, jsonb_build_object('name',CAST(:name AS text)))"""),
            {"actor":actor["id"],"id":rid,"name":payload.name})
    return {"id":rid,"club_id":club_id,"name":payload.name,"status":"draft","guest_ranking_mode":payload.guest_ranking_mode}

@router.get("")
def list_races(db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    rows = db.execute(text("""SELECT r.id,r.club_id,r.name,r.status,r.guest_ranking_mode,
        r.minimum_speed_mpm,r.display_speed_unit FROM races r
        WHERE (r.club_id IS NULL AND r.created_by=:actor)
           OR EXISTS(SELECT 1 FROM club_memberships m WHERE m.club_id=r.club_id
                     AND m.user_id=:actor AND m.club_role='admin')
        ORDER BY r.created_at DESC LIMIT 100"""), {"actor": actor["id"]})
    return [dict(row._mapping) for row in rows]

@router.post("/{race_id}/open")
def open_race(race_id: UUID, db: Session = Depends(get_db), actor: dict = Depends(require_race_admin)):
    with db.begin():
        row = db.execute(text("SELECT status FROM races WHERE id=:id FOR UPDATE"), {"id":race_id}).scalar_one_or_none()
        if row is None: raise HTTPException(404,"Race not found")
        if row != "draft": raise HTTPException(409,"Only draft races can be opened")
        db.execute(text("UPDATE races SET status='open' WHERE id=:id"), {"id":race_id})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'race.opened','race',:id)"""), {"actor":actor["id"],"id":race_id})
    return {"id":race_id,"status":"open"}


@router.post("/{race_id}/activate")
def activate_race(race_id: UUID, db: Session = Depends(get_db),
                  actor: dict = Depends(require_race_admin)):
    """Record actual release time on the server and begin provisional clocking."""
    with db.begin():
        race = db.execute(text("SELECT status FROM races WHERE id=:id FOR UPDATE"),
                          {"id":race_id}).scalar_one_or_none()
        if race is None:
            raise HTTPException(404, "Race not found")
        if race != "open":
            raise HTTPException(409, "Only open races can be activated")
        db.execute(text("""
            UPDATE races SET status='active',actual_release_at=now() WHERE id=:id
        """), {"id":race_id})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'race.activated','race',:id)
        """), {"actor":actor["id"],"id":race_id})
    return {"id":race_id,"status":"active"}
