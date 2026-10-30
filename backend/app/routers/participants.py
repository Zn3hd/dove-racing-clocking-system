"""Administrator-created accounts, loft verification and pigeon registration."""
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..auth import hash_password, require_admin
from ..database import get_db

router = APIRouter(tags=["participants"])

class ParticipantCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=250)
    phone: str | None = None
    password: str = Field(min_length=12, max_length=256)
    role: Literal["member","guest"]

class LoftCreate(BaseModel):
    user_id: UUID
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class PigeonCreate(BaseModel):
    loft_id: UUID
    official_ring_number: str = Field(min_length=1, max_length=100)
    name: str | None = None

@router.post("/participants", status_code=201)
def create_participant(payload: ParticipantCreate, db: Session = Depends(get_db),
                       actor: dict = Depends(require_admin)):
    uid = uuid4()
    try:
        with db.begin():
            db.execute(text("""INSERT INTO users(id,role_code,full_name,email,phone,password_hash)
                VALUES (:id,:role,:name,:email,:phone,:password)"""),
                {"id":uid,"role":payload.role,"name":payload.full_name.strip(),
                 "email":payload.email.strip().lower(),"phone":payload.phone,
                 "password":hash_password(payload.password)})
            db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
                VALUES (:actor,'participant.created','user',:id)"""),
                {"actor":actor["id"],"id":uid})
    except IntegrityError as exc:
        raise HTTPException(409,"Participant email already registered") from exc
    return {"id":uid,"role":payload.role,"full_name":payload.full_name}

@router.post("/lofts", status_code=201)
def create_loft(payload: LoftCreate, db: Session = Depends(get_db),
                actor: dict = Depends(require_admin)):
    loft_id = uuid4()
    try:
        with db.begin():
            role = db.execute(text("SELECT role_code FROM users WHERE id=:id AND status='active'"),
                              {"id":payload.user_id}).scalar_one_or_none()
            if role not in ("member","guest"):
                raise HTTPException(422,"Loft owner must be an active member or guest")
            db.execute(text("""INSERT INTO lofts(id,user_id,name,latitude,longitude)
                VALUES (:id,:user,:name,:lat,:lon)"""),
                {"id":loft_id,"user":payload.user_id,"name":payload.name,
                 "lat":payload.latitude,"lon":payload.longitude})
            db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
                VALUES (:actor,'loft.created','loft',:id)"""),
                {"actor":actor["id"],"id":loft_id})
    except IntegrityError as exc:
        raise HTTPException(409,"Owner already has a loft") from exc
    return {"id":loft_id,"verified":False}

@router.post("/lofts/{loft_id}/verify")
def verify_loft(loft_id: UUID, db: Session = Depends(get_db),
                actor: dict = Depends(require_admin)):
    with db.begin():
        row = db.execute(text("SELECT verified_at FROM lofts WHERE id=:id FOR UPDATE"),
                         {"id":loft_id}).first()
        if row is None: raise HTTPException(404,"Loft not found")
        if row[0] is not None: raise HTTPException(409,"Loft already verified")
        db.execute(text("""UPDATE lofts SET verified_at=now(),verified_by=:actor WHERE id=:id"""),
                   {"id":loft_id,"actor":actor["id"]})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'loft.verified','loft',:id)"""), {"actor":actor["id"],"id":loft_id})
    return {"id":loft_id,"verified":True}

@router.post("/pigeons", status_code=201)
def create_pigeon(payload: PigeonCreate, db: Session = Depends(get_db),
                  actor: dict = Depends(require_admin)):
    pid = uuid4()
    try:
        with db.begin():
            verified = db.execute(text("SELECT verified_at FROM lofts WHERE id=:id"),
                                  {"id":payload.loft_id}).scalar_one_or_none()
            if verified is None: raise HTTPException(422,"Loft must exist and be verified")
            db.execute(text("""INSERT INTO pigeons(id,loft_id,official_ring_number,name,status)
                VALUES (:id,:loft,:ring,:name,'active')"""),
                {"id":pid,"loft":payload.loft_id,"ring":payload.official_ring_number.strip(),
                 "name":payload.name})
            db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
                VALUES (:actor,'pigeon.created','pigeon',:id)"""),
                {"actor":actor["id"],"id":pid})
    except IntegrityError as exc:
        raise HTTPException(409,"Official ring number already registered") from exc
    return {"id":pid,"loft_id":payload.loft_id,"official_ring_number":payload.official_ring_number}
