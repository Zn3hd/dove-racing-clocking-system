# Dove Racing Backend — Phase 3 development

FastAPI prototype with PostgreSQL-backed race creation, opening, listing, and pigeon registration. **Development only.** The endpoints require a temporary development administrator token and an existing active chairman/president database user. This is not production authentication.

## Local setup
1. Install PostgreSQL 14+ and create a dedicated development database/user.
2. Apply `sql/001_schema.sql` then `sql/002_seed.sql` using psql. The migration is intended for a new empty database and has not been tested against a live instance.
3. Create a chairman/president user with a securely hashed password in the database through an authorized bootstrap procedure (not yet provided). Set its UUID as `DEV_ADMIN_USER_ID`.
4. Copy `.env.example` to `.env`, supply `DATABASE_URL`, `DEV_ADMIN_TOKEN` (32+ random characters), and `DEV_ADMIN_USER_ID`. Load those variables into your shell or use a trusted environment loader; FastAPI does not automatically read `.env`.
5. Run:
```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --host 127.0.0.1 --reload
```

For protected development requests send `X-Dev-Admin-Token`. Do not expose this API to the public internet. When `APP_ENV` is not `development`, protected routes refuse requests.

## Endpoints
- `GET /health` — prototype health
- `POST /calculations/flight` — unverified calculation
- `POST /races` — create draft race
- `GET /races` — list races
- `POST /races/{race_id}/open` — open a draft race
- `POST /races/{race_id}/entries` — register eligible pigeon while race open
- `GET /races/{race_id}/entries` — list race entries

## Remaining
- Live PostgreSQL integration tests, Alembic migrations and admin bootstrap
- Real JWT/role authorization, registration/loft verification UI, secure QR and RFID ingestion
- Entry category selection, transactional official result validation and finalization
- Admin-only changes to release time with audit trail

No official clocking endpoints are enabled.
