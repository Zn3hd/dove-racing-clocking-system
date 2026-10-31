"""Administrator-created accounts, loft verification and pigeon registration."""
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..auth import hash_password, require_admin
from ..database import get_db
from ..club_access import managed_club, check_user_admin, check_loft_admin

router = APIRouter(tags=["participants"])

class ParticipantCreate(BaseModel):
    club_id: UUID | None = None
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=250)
    phone: str | None = None
    password: str = Field(min_length=12, max_length=256)
    role: Literal["member","guest"]

    @field_validator("full_name", "email")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

class LoftCreate(BaseModel):
    user_id: UUID
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()

class PigeonCreate(BaseModel):
    loft_id: UUID
    official_ring_number: str = Field(min_length=1, max_length=100)
    name: str | None = None

    @field_validator("official_ring_number")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ring number must not be blank")
        return value.strip()

@router.post("/participants", status_code=201)
def create_participant(payload: ParticipantCreate, db: Session = Depends(get_db),
                       actor: dict = Depends(require_admin)):
    uid = uuid4()
    try:
        with db.begin():
            club = managed_club(db, actor, payload.club_id)
            db.execute(text("""INSERT INTO users(id,role_code,full_name,email,phone,password_hash)
                VALUES (:id,:role,:name,:email,:phone,:password)"""),
                {"id":uid,"role":payload.role,"name":payload.full_name.strip(),
                 "email":payload.email.strip().lower(),"phone":payload.phone,
                 "password":hash_password(payload.password)})
            db.execute(text("""INSERT INTO club_memberships(club_id,user_id,club_role)
                VALUES (:club,:user,:role)"""), {"club": club, "user": uid, "role": payload.role})
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
            check_user_admin(db, actor, payload.user_id)
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
        check_loft_admin(db, actor, loft_id)
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
            check_loft_admin(db, actor, payload.loft_id)
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


class ParticipantEdit(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=100)

    @field_validator("full_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class LoftEdit(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class PigeonEdit(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    status: Literal["active", "retired", "disqualified"]


class RingAssign(BaseModel):
    uid: str = Field(min_length=1, max_length=200)

    @field_validator('uid')
    @classmethod
    def exact_tag(cls, value):
        if not value.isprintable() or value != value.strip():
            raise ValueError('Use the exact normalized, printable tag identifier')
        return value


@router.post('/pigeons/{pigeon_id}/rfid', status_code=201)
def assign_ring(pigeon_id: UUID, payload: RingAssign,
                 db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    ring_id = uuid4()
    try:
        with db.begin():
            pigeon = db.execute(text('''SELECT p.loft_id,p.status,l.verified_at,u.status AS owner_status
                FROM pigeons p JOIN lofts l ON l.id=p.loft_id JOIN users u ON u.id=l.user_id
                WHERE p.id=:id FOR UPDATE OF p'''), {'id': pigeon_id}).mappings().first()
            if pigeon is None:
                raise HTTPException(404, 'Pigeon not found')
            check_loft_admin(db, actor, pigeon['loft_id'])
            if pigeon['status'] != 'active' or pigeon['owner_status'] != 'active' or pigeon['verified_at'] is None:
                raise HTTPException(422, 'Active pigeon/owner and verified loft required')
            db.execute(text('INSERT INTO rfid_rings(id,pigeon_id,uid) VALUES (:id,:pigeon,:uid)'),
                       {'id': ring_id, 'pigeon': pigeon_id, 'uid': payload.uid})
            audit_edit(db, actor, 'rfid_ring.assigned', 'pigeon', pigeon_id)
    except IntegrityError as exc:
        raise HTTPException(409, 'Pigeon or RFID identifier already has an active ring assignment') from exc
    return {'id': ring_id, 'pigeon_id': pigeon_id, 'uid': payload.uid}


def audit_edit(db: Session, actor: dict, action: str, entity: str, entity_id: UUID):
    db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
        VALUES (:actor,:action,:entity,:id)"""),
        {"actor": actor["id"], "action": action, "entity": entity, "id": entity_id})


@router.get("/participants")
def list_participants(club_id: UUID | None = None, db: Session = Depends(get_db),
                      actor: dict = Depends(require_admin)):
    club = managed_club(db, actor, club_id)
    rows = db.execute(text("""SELECT u.id,u.full_name,u.email,u.phone,u.role_code,u.status
        FROM users u JOIN club_memberships m ON m.user_id=u.id
        WHERE m.club_id=:club AND m.club_role IN ('member','guest')
        ORDER BY u.full_name,u.id LIMIT 1000"""), {"club": club}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/lofts")
def list_lofts(club_id: UUID | None = None, db: Session = Depends(get_db),
               actor: dict = Depends(require_admin)):
    club = managed_club(db, actor, club_id)
    rows = db.execute(text("""SELECT l.id,l.user_id,l.name,l.latitude,l.longitude,
        l.verified_at,l.verified_by FROM lofts l
        JOIN club_memberships m ON m.user_id=l.user_id
        WHERE m.club_id=:club AND m.club_role IN ('member','guest')
        ORDER BY l.name,l.id LIMIT 1000"""), {"club": club}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/pigeons")
def list_pigeons(club_id: UUID | None = None, db: Session = Depends(get_db),
                 actor: dict = Depends(require_admin)):
    club = managed_club(db, actor, club_id)
    rows = db.execute(text("""SELECT p.id,p.loft_id,p.official_ring_number,p.name,p.status
        FROM pigeons p JOIN lofts l ON l.id=p.loft_id
        JOIN club_memberships m ON m.user_id=l.user_id
        WHERE m.club_id=:club AND m.club_role IN ('member','guest')
        ORDER BY p.official_ring_number,p.id LIMIT 1000"""), {"club": club}).mappings().all()
    return [dict(row) for row in rows]


@router.put("/participants/{user_id}")
def edit_participant(user_id: UUID, payload: ParticipantEdit,
                     db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    with db.begin():
        check_user_admin(db, actor, user_id)
        updated = db.execute(text("""UPDATE users SET full_name=:name,phone=:phone
            WHERE id=:id AND role_code IN ('member','guest') RETURNING id"""),
            {"id": user_id, "name": payload.full_name, "phone": payload.phone}).scalar_one_or_none()
        if updated is None:
            raise HTTPException(404, "Participant not found")
        audit_edit(db, actor, "participant.updated", "user", user_id)
    return {"id": user_id, **payload.model_dump()}


@router.put("/lofts/{loft_id}")
def edit_loft(loft_id: UUID, payload: LoftEdit,
              db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    with db.begin():
        check_loft_admin(db, actor, loft_id)
        loft = db.execute(text("SELECT latitude,longitude,verified_at FROM lofts WHERE id=:id FOR UPDATE"),
                          {"id": loft_id}).mappings().one()
        changed = (float(loft["latitude"]) != payload.latitude
                   or float(loft["longitude"]) != payload.longitude)
        if changed:
            busy = db.execute(text("""SELECT EXISTS(SELECT 1 FROM race_entries e
                JOIN races r ON r.id=e.race_id WHERE e.loft_id=:id
                AND e.status='registered' AND r.status IN ('open','active','closed'))"""),
                {"id": loft_id}).scalar()
            if busy:
                raise HTTPException(409, "Loft coordinates cannot change during an unfinished race")
        db.execute(text("""UPDATE lofts SET name=:name,latitude=:lat,longitude=:lon,
            verified_at=CASE WHEN :changed THEN NULL ELSE verified_at END,
            verified_by=CASE WHEN :changed THEN NULL ELSE verified_by END WHERE id=:id"""),
            {"id": loft_id, "name": payload.name, "lat": payload.latitude,
             "lon": payload.longitude, "changed": changed})
        audit_edit(db, actor, "loft.updated", "loft", loft_id)
    return {"id": loft_id, **payload.model_dump(),
            "verified": not changed and loft["verified_at"] is not None}


@router.put("/pigeons/{pigeon_id}")
def edit_pigeon(pigeon_id: UUID, payload: PigeonEdit,
                db: Session = Depends(get_db), actor: dict = Depends(require_admin)):
    with db.begin():
        pigeon = db.execute(text("SELECT loft_id,status FROM pigeons WHERE id=:id FOR UPDATE"),
                            {"id": pigeon_id}).mappings().first()
        if pigeon is None:
            raise HTTPException(404, "Pigeon not found")
        check_loft_admin(db, actor, pigeon["loft_id"])
        if pigeon["status"] != payload.status:
            busy = db.execute(text("""SELECT EXISTS(SELECT 1 FROM race_entries e
                JOIN races r ON r.id=e.race_id WHERE e.pigeon_id=:id
                AND e.status='registered' AND r.status IN ('open','active','closed'))"""),
                {"id": pigeon_id}).scalar()
            if busy:
                raise HTTPException(409, "Pigeon status cannot change during an unfinished race")
        db.execute(text("UPDATE pigeons SET name=:name,status=:status WHERE id=:id"),
                   {"id": pigeon_id, **payload.model_dump()})
        audit_edit(db, actor, "pigeon.updated", "pigeon", pigeon_id)
    return {"id": pigeon_id, **payload.model_dump()}
