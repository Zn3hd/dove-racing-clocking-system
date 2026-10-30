"""Development-only race management routes. All writes require admin token."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import RaceCreate
from ..auth import require_admin

router = APIRouter(prefix="/races", tags=["races"], )

@router.post("", status_code=201)
def create_race(payload: RaceCreate, db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    rid = uuid4()
    with db.begin():
        db.execute(text("""
            INSERT INTO races(id,name,release_latitude,release_longitude,scheduled_release_at,
              minimum_speed_mpm,display_speed_unit,guest_ranking_mode,status,created_by)
            VALUES (:id,:name,:lat,:lon,:scheduled,:minimum,:unit,:mode,'draft',:actor)
        """), {"id":rid,"name":payload.name,"lat":payload.release_latitude,
                 "lon":payload.release_longitude,"scheduled":payload.scheduled_release_at,
                 "minimum":payload.minimum_speed_mpm,"unit":payload.display_speed_unit,
                 "mode":payload.guest_ranking_mode,"actor":actor["id"]})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id,after_state)
            VALUES (:actor,'race.created','race',:id, jsonb_build_object('name',CAST(:name AS text)))"""),
            {"actor":actor["id"],"id":rid,"name":payload.name})
    return {"id":rid,"name":payload.name,"status":"draft","guest_ranking_mode":payload.guest_ranking_mode}

@router.get("")
def list_races(db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    rows = db.execute(text("""SELECT id,name,status,guest_ranking_mode,
        minimum_speed_mpm,display_speed_unit FROM races ORDER BY created_at DESC LIMIT 100"""))
    return [dict(row._mapping) for row in rows]

@router.post("/{race_id}/open")
def open_race(race_id: UUID, db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
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
                  actor: dict = Depends(require_admin)):
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
