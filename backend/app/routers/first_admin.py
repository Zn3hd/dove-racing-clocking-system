"""One-time bootstrap for the initial club chairman.

Enabled only while ADMIN_BOOTSTRAP_SECRET is configured.
Remove that variable from Render after creating the first account.
"""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..database import get_db

router = APIRouter(prefix="/setup", tags=["setup"])


class FirstAdminRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)


@router.post("/first-admin", status_code=201)
def first_admin(
    payload: FirstAdminRequest,
    x_setup_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    secret = os.getenv("ADMIN_BOOTSTRAP_SECRET", "")
    if len(secret) < 48 or not x_setup_secret or not hmac.compare_digest(secret, x_setup_secret):
        raise HTTPException(status_code=404, detail="Not found")

    name = payload.full_name.strip()
    email = payload.email.strip().lower()
    if len(name) < 2 or "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid account details")

    try:
        db.execute(text("SELECT pg_advisory_xact_lock(7462091322)"))
        exists = db.execute(text(
            "SELECT EXISTS (SELECT 1 FROM users WHERE role_code IN ('chairman', 'president'))"
        )).scalar()
        if exists:
            raise HTTPException(status_code=409, detail="Administrator already exists")
        db.execute(
            text("""INSERT INTO users(role_code, full_name, email, password_hash)
                    VALUES ('chairman', :name, :email, :password_hash)"""),
            {"name": name, "email": email, "password_hash": hash_password(payload.password)},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Administrator created; remove ADMIN_BOOTSTRAP_SECRET from Render."}
