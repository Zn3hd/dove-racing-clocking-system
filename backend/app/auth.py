"""Password authentication and short-lived signed bearer tokens."""
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import get_db

hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return hasher.hash(password)

def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(password, encoded)
    except (ValueError, TypeError):
        return False

def signing_key() -> str:
    key = os.getenv("JWT_SECRET_KEY", "")
    if len(key) < 48 or key.startswith("REPLACE"):
        raise HTTPException(503, "JWT_SECRET_KEY must be set to a strong random value (48+ characters)")
    return key

def issue_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=30),
                       "iss": "dove-racing"}, signing_key(), algorithm=ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required")
    try:
        claims = jwt.decode(credentials.credentials, signing_key(), algorithms=[ALGORITHM],
                            issuer="dove-racing", options={"require": ["sub", "exp", "iat", "iss"]})
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Invalid or expired token") from exc
    row = db.execute(text("SELECT id,role_code,status,full_name,email FROM users WHERE id=:id"),
                     {"id": user_id}).mappings().first()
    if not row or row["status"] != "active":
        raise HTTPException(401, "Account inactive or unavailable")
    result = dict(row)
    db.rollback()  # close read-only implicit transaction before write endpoints begin
    return result

def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role_code"] not in ("chairman", "president"):
        raise HTTPException(403, "Administrator role required")
    return user
