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


## Phase 4: provisional clocking endpoints
- `POST /races/{race_id}/activate` — admin records actual release time and activates an open race.
- `POST /clocking/qr/tokens` — admin issues a short-lived secret for a registered guest entry; revokes earlier matching tokens.
- `POST /clocking/qr/scans` — authenticated guest submits their own entry and secret, with a UUID idempotency key.
- `POST /clocking/rfid/simulate` — admin-only simulator uses registered device ID and active RFID UID.
- `GET /clocking/events?race_id=...` — admin lists stored clocking evidence.
- `POST /clocking/events/{event_id}/review` — admin records approval or rejection; approval remains pending and does not create an official result.

Example guest scan JSON:
```json
{
  "entry_id": "ENTRY_UUID",
  "token": "ISSUED_SECRET",
  "idempotency_key": "RANDOM_UUID"
}
```

**Limitations:** No physical RFID protocol, device authentication, clock attestation, offline signature verification, rate limiting, official first-valid-arrival selection, result finalization, or live database integration verification yet. A static QR secret is copyable, so QR evidence is never automatically official. Reusing an idempotency key is supported only for the same entry/method; distinct requests still produce separate pending evidence. Human approvals are stored but not automatically promoted to valid clockings. Do not deploy publicly.


## PostgreSQL end-to-end integration tests

GitHub Actions now starts a disposable PostgreSQL 16 service, applies the actual `sql/001_schema.sql` and `sql/002_seed.sql` files, and runs the full pytest suite. `tests/test_postgres_e2e.py` exercises real API requests and persistent data for race creation, opening, registration, activation, guest ownership, QR token rotation, idempotency, RFID simulation, and review rejection. The CI database uses **test-only credentials** and is destroyed after the job.

To run locally, use a **dedicated disposable database**, apply both SQL scripts, set `DATABASE_URL` and `TEST_DATABASE_URL` to that database and a 48+ character `JWT_SECRET_KEY`, then run `python -m pytest -q`. Never point integration tests at production or a database containing real club records.

Integration suite status must be verified in GitHub Actions; committed tests are not evidence of passing tests. Remaining scenarios include concurrency races, expired tokens, offline hardware, race finalization, and first-valid-arrival selection.
