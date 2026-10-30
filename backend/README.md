# Dove Racing Backend — authentication and participant management (development)

This branch implements PostgreSQL-backed race management, authenticated chairman/president routes, and participant registration. It is **not production ready**; no RFID/QR official clocking endpoints are active.

## Local setup
1. Create a dedicated PostgreSQL database and apply `sql/001_schema.sql`, then `sql/002_seed.sql`.
2. Set `DATABASE_URL` and a randomly generated `JWT_SECRET_KEY` (48+ characters) in your environment. Copy `.env.example` to local `.env` if useful; environment variables must be loaded into the process before running.
3. Bootstrap the first chairman using environment variables `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` (12+ characters), then run from `backend/`: `python -m scripts.bootstrap_admin`. This script refuses to run if any administrator already exists. Unset bootstrap credentials afterward.
4. Install requirements: `python -m pip install -r requirements.txt`
5. Start: `uvicorn app.main:app --host 127.0.0.1 --reload`
6. Run tests: `python -m pytest -q`

## API flow
- `POST /auth/login` with email/password returns a 30-minute bearer JWT.
- `GET /auth/me` returns the current account.
- Admin bearer token required for `POST /participants`, `POST /lofts`, `POST /lofts/{id}/verify`, `POST /pigeons`, and all `/races` endpoints.
- Accounts can be created only by an administrator. Loft coordinates require explicit administrator verification before pigeon registration.
- For race registration, an RFID pigeon needs an active ring; QR entries must belong to a guest.

## Remaining security and reliability work
- Integration tests with real PostgreSQL, including rollback and concurrent registration.
- Login rate limiting, password reset, account lockout, secure HTTPS and token revocation.
- Permissions scoped to each participant's own data; club/multi-club tenancy.
- Stronger loft verification process, RFID ring assignment, QR token issuance and clocking review.
- Alembic migrations, schema versioning, and validated deployment configuration.

Do not deploy this development API to the public internet yet.
