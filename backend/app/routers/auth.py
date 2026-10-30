"""Login for existing accounts. Public self-registration is intentionally disabled."""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import current_user, issue_token, verify_password, hash_password
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    row = db.execute(text("""SELECT id,password_hash,status FROM users
        WHERE lower(email)=lower(:email)"""), {"email": payload.email.strip()}).mappings().first()
    # Avoid revealing whether an email address exists.
    if not row or row["status"] != "active" or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": issue_token(row["id"]), "token_type": "bearer", "expires_in": 1800}

@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "role": user["role_code"],
            "full_name": user["full_name"], "email": user["email"]}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=256)

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change the signed-in user's password after verifying the current password."""
    # Lock the account row so concurrent changes cannot overwrite one another.
    row = db.execute(
        text("SELECT password_hash FROM users WHERE id=:id AND status='active' FOR UPDATE"),
        {"id": user["id"]},
    ).mappings().first()
    if not row or not verify_password(payload.current_password, row["password_hash"]):
        db.rollback()
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        db.rollback()
        raise HTTPException(status_code=422, detail="New password must differ from current password")
    db.execute(
        text("UPDATE users SET password_hash=:password_hash WHERE id=:id"),
        {"password_hash": hash_password(payload.new_password), "id": user["id"]},
    )
    db.commit()
    return {"message": "Password changed successfully"}
