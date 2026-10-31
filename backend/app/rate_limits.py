"""Shared PostgreSQL fixed-minute budgets. Raw IPs/emails are never stored."""
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import get_engine
from .auth import require_bearer, signing_key


def identity_digest(identity):
    return hmac.new(signing_key().encode('utf-8'), str(identity).encode('utf-8'), hashlib.sha256).hexdigest()


def consume(scope, identity, default):
    try:
        limit = int(os.getenv(scope.upper() + '_LIMIT', str(default)))
        if not 1 <= limit <= 100000:
            raise ValueError()
    except ValueError as exc:
        raise HTTPException(503, 'Invalid rate-limit configuration') from exc
    identity_hash = identity_digest(identity)
    try:
        with get_engine().begin() as connection:
            second = int(connection.execute(text('SELECT extract(epoch FROM clock_timestamp())')).scalar_one())
            bucket = second // 60
            count = connection.execute(text('''INSERT INTO request_rate_buckets(scope,identity_hash,bucket,attempts)
                VALUES (:scope,:identity,:bucket,1) ON CONFLICT(scope,identity_hash,bucket)
                DO UPDATE SET attempts=request_rate_buckets.attempts+1 RETURNING attempts'''),
                {'scope':scope,'identity':identity_hash,'bucket':bucket}).scalar_one()
            connection.execute(text('DELETE FROM request_rate_buckets WHERE bucket<:old'), {'old':bucket-2})
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Request protection temporarily unavailable') from exc
    if count > limit:
        raise HTTPException(429, 'Too many requests. Retry with the same submission ID.',
                            headers={'Retry-After': str(60-second % 60)})


def login_ip(request: Request):
    consume('login_ip', request.client.host if request.client else 'unknown', 120)


def scan_ip(request: Request, credentials=Depends(require_bearer)):
    consume('qr_scan_ip', request.client.host if request.client else 'unknown', 600)


def device_ip(request: Request):
    consume('device_scan_ip', request.client.host if request.client else 'unknown', 1200)
