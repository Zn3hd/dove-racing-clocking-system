# Dove Racing Backend — authentication and participant management (development)

This branch implements PostgreSQL-backed race management, authenticated chairman/president routes, and participant registration. It is **not production ready**; no RFID/QR official clocking endpoints are active.

## Local setup
1. Create a dedicated PostgreSQL database. After installing requirements and setting the environment below, run `python -m scripts.run_migrations` to apply migrations `001` through `008`. The runner requires a fresh database or its existing migration ledger; see `../docs/render-postgres-migrations.md` for existing databases.
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

To run locally, use a **dedicated disposable database**, apply migrations `001` through `008`, set `DATABASE_URL` and `TEST_DATABASE_URL` to that database and a 48+ character `JWT_SECRET_KEY`, then run `python -m pytest -q`. Never point integration tests at production or a database containing real club records.

Integration suite status must be verified in GitHub Actions; committed tests are not evidence of passing tests. Remaining scenarios include concurrency races, expired tokens, offline hardware, race finalization, and first-valid-arrival selection.

## Single-club administration

Leaderboard previews exclude physically rejected arrivals, even if a prior evidence review approved them. Each preview row includes `physical_verification` (`not_recorded` or `confirmed`), `physically_verified_at`, and `source_channel`. Confirmed physical identity alone does not certify the submitted arrival time: every preview remains provisional and official finalization remains disabled.

- `POST /clubs`: a chairman or president creates the single club and becomes its club administrator. Further creation requests return `409`.
- `GET /clubs`: lists clubs where the caller has a club administrator membership.
- `POST /clubs/{club_id}/members`: a club administrator adds an active member or guest using `{"user_id":"USER_UUID"}`. Duplicate additions, including concurrent requests, return `409`.
- `GET /clubs/{club_id}/members`: lists club members for that club's administrators.

All club routes require a chairman or president account. Club membership alone does not grant API administration rights. Successful creation and membership additions are audited.

New races accept an optional `club_id`; when omitted, the existing single club is selected. Creation requires administrator membership in that club. Before the first club exists, races may be created without a club. Historical races with no club remain accessible only to their creator and are never silently reassigned. Race listings, transitions, entries, leaderboard previews, QR token issuance, RFID simulation, event listings, reviews, provenance, and physical guest verification enforce this race ownership policy. Pigeon registration into a club race requires an active owner with member/guest membership in that club.

Participant creation requires a managed club (optional `club_id`, defaulting to the single club) and atomically adds membership. Existing members and guests can be assigned through `/clubs/{club_id}/members`. Loft creation, verification, pigeon creation, device provisioning, and Messenger account linking require administration of the owner's club once a club exists. Before any club exists, legacy asset administration retains its global administrator behavior. Unassigned historical participants must be explicitly added to the club before their assets can be managed after club creation. Assets inherit club scope through their owner's membership; this remains a single-club prototype, not a multi-club tenancy model.

`GET /participants`, `GET /lofts`, and `GET /pigeons` list up to 1000 club-scoped records and accept an optional `club_id`. `PUT /participants/{id}` updates `full_name` and `phone`; `PUT /lofts/{id}` updates `name`, `latitude`, and `longitude`; `PUT /pigeons/{id}` updates `name` and `status`. These replace the listed editable fields. Account credentials, roles, loft ownership, and official ring numbers cannot be changed through these routes. Coordinate changes clear loft verification and are blocked while registered in open, active, or closed races; pigeon status changes have the same race guard. Historical entry coordinate snapshots remain unchanged. Updates are audited.

QR, web/mobile, SMS, Messenger, simulated RFID, and device gateway ingestion check the active owner's membership in the race club, including provider replay paths. Existing token, signature, ownership, and device validation still apply. Official finalization remains disabled; these changes do not establish trusted arrival timing.

CI applies migration `008` and includes PostgreSQL tests for creation, membership, duplicate requests, concurrent additions, audit records, and access denial. Without `TEST_DATABASE_URL`, those integration tests are skipped. For database-free checks, set `DATABASE_URL` to a placeholder PostgreSQL URL (for example `postgresql+psycopg://test:test@127.0.0.1/dove_test`) and run `python -m pytest -q`; this does not verify database behavior.
