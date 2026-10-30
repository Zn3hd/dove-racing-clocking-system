"""Initial single-club administration endpoints (development stage)."""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/clubs", tags=["clubs"])


class ClubCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)


class ClubMemberAdd(BaseModel):
    user_id: UUID


@router.post("", status_code=201)
def create_club(payload: ClubCreate, db: Session = Depends(get_db),
                actor: dict = Depends(require_admin)):
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(422, "Club name must contain at least two characters")
    club_id = uuid4()
    with db.begin():
        # One club in this prototype, preventing accidental parallel club creation.
        db.execute(text("SELECT pg_advisory_xact_lock(7462091323)"))
        if db.execute(text("SELECT EXISTS(SELECT 1 FROM clubs)")).scalar():
            raise HTTPException(409, "A club already exists in this single-club prototype")
        db.execute(text(
            """INSERT INTO clubs(id,name,description,created_by)
               VALUES (:id,:name,:description,:actor)"""
        ), {"id":club_id,"name":name,"description":payload.description,"actor":actor["id"]})
        db.execute(text(
            """INSERT INTO club_memberships(club_id,user_id,club_role)
               VALUES (:club,:user,'admin')"""
        ), {"club":club_id,"user":actor["id"]})
        db.execute(text(
            """INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
               VALUES (:actor,'club.created','club',:id)"""
        ), {"actor":actor["id"],"id":club_id})
    return {"id":club_id,"name":name,"description":payload.description}


@router.get("")
def list_clubs(db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    rows = db.execute(text(
        """SELECT c.id,c.name,c.description,c.created_at
           FROM clubs c JOIN club_memberships m ON m.club_id=c.id
           WHERE m.user_id=:user AND m.club_role='admin'"""
    ), {"user":actor["id"]}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{club_id}/members", status_code=201)
def add_member(club_id: UUID, payload: ClubMemberAdd,
               db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    with db.begin():
        allowed = db.execute(text(
            """SELECT EXISTS(SELECT 1 FROM club_memberships
               WHERE club_id=:club AND user_id=:actor AND club_role='admin')"""
        ), {"club":club_id,"actor":actor["id"]}).scalar()
        if not allowed:
            raise HTTPException(403, "Club administrator required")
        role = db.execute(text(
            "SELECT role_code FROM users WHERE id=:id AND status='active'"
        ), {"id":payload.user_id}).scalar_one_or_none()
        if role not in ("member", "guest"):
            raise HTTPException(422, "User must be an active member or guest")
        added = db.execute(text(
            """INSERT INTO club_memberships(club_id,user_id,club_role)
               VALUES (:club,:user,:role)
               ON CONFLICT (club_id,user_id) DO NOTHING
               RETURNING user_id"""
        ), {"club":club_id,"user":payload.user_id,"role":role}).scalar_one_or_none()
        if added is None:
            raise HTTPException(409, "User is already in the club")
        db.execute(text(
            """INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
               VALUES (:actor,'club.member_added','club',:club)"""
        ), {"actor":actor["id"],"club":club_id})
    return {"club_id":club_id,"user_id":payload.user_id,"role":role}


@router.get("/{club_id}/members")
def list_members(club_id: UUID, db: Session = Depends(get_db),
                 actor: dict = Depends(require_admin)):
    allowed = db.execute(text(
        """SELECT EXISTS(SELECT 1 FROM club_memberships
           WHERE club_id=:club AND user_id=:actor AND club_role='admin')"""
    ), {"club":club_id,"actor":actor["id"]}).scalar()
    if not allowed:
        raise HTTPException(403, "Club administrator required")
    rows = db.execute(text(
        """SELECT u.id,u.full_name,u.email,m.club_role,m.joined_at
           FROM club_memberships m JOIN users u ON u.id=m.user_id
           WHERE m.club_id=:club ORDER BY m.joined_at"""
    ), {"club":club_id}).mappings().all()
    return [dict(r) for r in rows]
