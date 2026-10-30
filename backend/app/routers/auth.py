"""Login for existing accounts. Public self-registration is intentionally disabled."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import current_user, issue_token, verify_password
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
