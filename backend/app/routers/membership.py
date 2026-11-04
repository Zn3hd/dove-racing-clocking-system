"""Public applications and club-admin review; no active account until approval."""
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import hash_password, verify_password, require_admin
from ..club_access import managed_club
from ..database import get_db
from ..rate_limits import consume

router = APIRouter(prefix="/membership", tags=["membership"])


class ApplicationCreate(BaseModel):
    club_id: UUID
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=250)
    phone: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("full_name", "email")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Required field")
        return value


class ApplicationLookup(BaseModel):
    email: str
    password: str


class Decision(BaseModel):
    decision: Literal["approve", "decline"]
    reason: str | None = Field(default=None, max_length=500)


@router.get("/clubs")
def public_clubs(db: Session = Depends(get_db)):
    return [dict(row) for row in db.execute(text(
        "SELECT id,name FROM clubs ORDER BY name LIMIT 100"
    )).mappings()]


@router.post("/applications", status_code=202)
def apply(payload: ApplicationCreate, request: Request, db: Session = Depends(get_db)):
    consume("membership_apply_ip", request.client.host if request.client else "unknown", 10)
    email = payload.email.strip().lower()
    consume("membership_apply_email", email, 5)
    application_id = uuid4()
    try:
        with db.begin():
            if db.execute(text("SELECT 1 FROM clubs WHERE id=:club"), {"club":payload.club_id}).first() is None:
                raise HTTPException(404, "Club not found")
            if db.execute(text("SELECT 1 FROM users WHERE lower(email)=:email"), {"email":email}).first():
                raise HTTPException(409, "Email already registered")
            db.execute(text("""INSERT INTO membership_applications
                (id,club_id,full_name,email,phone,password_hash)
                VALUES (:id,:club,:name,:email,:phone,:password)"""),
                {"id":application_id,"club":payload.club_id,"name":payload.full_name,
                 "email":email,"phone":payload.phone,
                 "password":hash_password(payload.password)})
    except IntegrityError as exc:
        raise HTTPException(409, "An application for this email is already pending") from exc
    return {"application_id":application_id,"status":"pending",
            "message":"Application received. You cannot sign in until approved."}


@router.post("/status")
def application_status(payload: ApplicationLookup, request: Request, db: Session = Depends(get_db)):
    consume("membership_status_ip", request.client.host if request.client else "unknown", 20)
    consume("membership_status_email", payload.email.strip().lower(), 10)
    row = db.execute(text("""SELECT status,password_hash,decision_reason,reviewed_at
        FROM membership_applications WHERE lower(email)=:email
        ORDER BY submitted_at DESC LIMIT 1"""), {"email":payload.email.strip().lower()}).mappings().first()
    if not row or not verify_password(payload.password,row["password_hash"]):
        raise HTTPException(401, "Invalid application credentials")
    return {"status":row["status"],"reason":row["decision_reason"],
            "reviewed_at":row["reviewed_at"]}


@router.get("/applications")
def pending_applications(club_id: UUID, status: Literal["pending","approved","declined"] = "pending",
                         actor: dict = Depends(require_admin), db: Session = Depends(get_db)):
    managed_club(db,actor,club_id)
    return [dict(row) for row in db.execute(text("""SELECT id,club_id,full_name,email,phone,
        status,submitted_at,reviewed_at,decision_reason FROM membership_applications
        WHERE club_id=:club AND status=:status ORDER BY submitted_at LIMIT 200"""),
        {"club":club_id,"status":status}).mappings()]


@router.post("/applications/{application_id}/decision")
def decide(application_id: UUID, payload: Decision, actor: dict = Depends(require_admin),
           db: Session = Depends(get_db)):
    with db.begin():
        row = db.execute(text("""SELECT id,club_id,full_name,email,phone,password_hash,status
            FROM membership_applications WHERE id=:id FOR UPDATE"""),
            {"id":application_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "Application not found")
        managed_club(db,actor,row["club_id"])
        if row["status"] != "pending":
            raise HTTPException(409, "Application already reviewed")
        member_id = None
        if payload.decision == "approve":
            if db.execute(text("SELECT 1 FROM users WHERE lower(email)=:email"),
                          {"email":row["email"]}).first():
                raise HTTPException(409, "Email already registered")
            member_id = uuid4()
            db.execute(text("""INSERT INTO users(id,role_code,full_name,email,phone,password_hash)
                VALUES (:id,'member',:name,:email,:phone,:password)"""),
                {"id":member_id,"name":row["full_name"],"email":row["email"],
                 "phone":row["phone"],"password":row["password_hash"]})
            db.execute(text("""INSERT INTO club_memberships(club_id,user_id,club_role)
                VALUES (:club,:member,'member')"""),
                {"club":row["club_id"],"member":member_id})
        db.execute(text("""UPDATE membership_applications SET status=:status,
            reviewed_at=now(),reviewed_by=:actor,decision_reason=:reason,member_id=:member
            WHERE id=:id"""), {"id":application_id,"status":"approved" if member_id else "declined",
            "actor":actor["id"],"reason":payload.reason,"member":member_id})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,:action,'membership_application',:id)"""),
            {"actor":actor["id"],"action":"membership.approved" if member_id else "membership.declined",
             "id":application_id})
    return {"application_id":application_id,
            "status":"approved" if member_id else "declined","member_id":member_id}
