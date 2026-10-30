"""Temporary local development gate; replace with real authentication before deployment."""
import hmac
import os
from fastapi import Header, HTTPException

def require_dev_admin(x_dev_admin_token: str | None = Header(default=None)) -> None:
    secret = os.getenv("DEV_ADMIN_TOKEN")
    if os.getenv("APP_ENV", "development") != "development":
        raise HTTPException(503, "Development authentication is disabled outside development")
    if not secret or len(secret) < 32:
        raise HTTPException(503, "DEV_ADMIN_TOKEN must be configured (32+ characters)")
    if not x_dev_admin_token or not hmac.compare_digest(x_dev_admin_token, secret):
        raise HTTPException(401, "Unauthorized")
