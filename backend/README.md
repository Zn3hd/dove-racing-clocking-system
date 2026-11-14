# Dove Racing Backend — authentication and participant management (development)

This branch implements PostgreSQL-backed club/race management, guest QR capture, a hardware-independent RFID gateway, evidence review and provisional standings. **Official result finalization remains disabled.** Use the [current user guide](../docs/user-guide.md) for the supported workflow and the [functionality audit](../docs/functionality-audit-2026-11-07.md) for verified coverage and limits.

Some phase-history notes below describe earlier milestones. They do not replace the current user guide or indicate that a local revision has been deployed.

## Local setup
1. Create a dedicated PostgreSQL database. After installing requirements and setting the environment below, run `python -m scripts.run_migrations` to apply migrations `001` through `014`. The runner requires a fresh database or its existing migration ledger; see `../docs/render-postgres-migrations.md` for existing databases.
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

## Current boundaries

- Club-scoped permissions, verified lofts, RFID mapping, device credentials, guest QR labels, evidence review and shared rate budgets are implemented and tested. See the current audit for the exact scope.
- Physical reader/ring compatibility and automatic antenna detection still need field acceptance.
- Reader clocks are untrusted; offline arrival speed uses server receipt, not backdated device observation time.
- Official finalization remains disabled. Preview ranks and human evidence approval are not official results.
- Password reset/account recovery, broader user-session revocation and production operational hardening remain separate work. Device credential rotation/revocation is already supported.
- Local test success does not establish the currently deployed Render revision or live provider integration status.

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

**Limitations:** Static QR labels are copyable and are operator evidence. The gateway authenticates a device credential but does not attest an antenna or clock. The Python gateway supports configured HID/serial/network adapters; actual reader protocols and matching tags still need field testing. Idempotent transport retries return the original event; changed replay content conflicts, while distinct physical scans can remain separate evidence. Blocking validation prevents ranking despite approval. Official finalization remains disabled.

## PostgreSQL end-to-end integration tests

GitHub Actions starts a disposable PostgreSQL 16 service, applies migrations `001`–`014`, and runs the full pytest suite. `tests/test_postgres_e2e.py` exercises real API requests and persistent data for race creation, opening, registration, activation, guest ownership, QR token rotation, idempotency, RFID simulation, and review rejection. The CI database uses **test-only credentials** and is destroyed after the job.

To run locally, use a **dedicated disposable database**, apply migrations `001` through `014`, install the gateway for cross-component tests with `python -m pip install -e ../gateway`, set `DATABASE_URL` and `TEST_DATABASE_URL` to that database and a 48+ character `JWT_SECRET_KEY`, then run `python -m pytest -q`. Never point integration tests at production or a database containing real club records.

The [current functionality audit](../docs/functionality-audit-2026-11-07.md) records the latest local PostgreSQL and browser results. GitHub Actions status must be checked separately. Tests cover concurrency, expiry, first-eligible selection and software offline/replay behavior; physical offline hardware and official timing/finalization remain outside that proof.

## Hardware-independent RFID gateway

Clocking validation requires migration `010`. Race creation accepts a configurable
`maximum_speed_mpm` (default 3000) and `clock_tolerance_seconds` (default 5).
Only draft races can update these through `PUT /races/{id}/validation-policy`.
`GET /races/{id}/validation` and the live dashboard show suspicious-event flags.
Flagged evidence is retained but cannot enter either ranking preview, even with
an approval. Repeat scans are warnings; one first eligible event ranks per entry.
Simulator promotion is additionally blocked at the database level. See
`../docs/clocking-validation.md` for exact rules and remaining timing limitations.

The separate `../gateway/` Python application supports laptop and Raspberry Pi
deployment with pluggable readers, explicit tag normalization, a simulator, and
durable offline delivery. See `../gateway/README.md`. Apply migration `009`
before deploying the updated reader API. `POST /devices` registers a reader;
`GET /devices` lists club-scoped readers; `POST /pigeons/{id}/rfid` assigns an
exact normalized tag. Provisioning and arrival paths remain compatible with
existing devices. New arrivals can include `adapter_type` and `protocol`, which
must match explicitly configured readers. Local observation timestamps must be
timezone-aware and remain untrusted. Official finalization remains disabled.

## Dashboard access

The Members **GPS** action records or updates each participant's loft location,
supports click-to-capture browser location, and offers separate saved-location
verification. Migration `011` records coordinate source, reported GPS accuracy,
and capture time. Sison town-reference coordinates are examples only and cannot
be verified for racing. Location changes clear verification and preserve race
entry snapshots. See `../docs/member-gps.md` for setup, limits, and API fields.

The **Live race** tab polls club-authorized `GET /races/{race_id}/live` every
three seconds and displays first eligible arrival, distance, speed, arrival
order, and provisional rank. Automatic/simulated RFID may appear without review;
operator/manual/unknown evidence requires approval. Rejected evidence is
excluded. Reader capture mode is a declaration, not verified timing. No official
results are written. See `../docs/universal-clocking-status.md` for limits.

Open `/dashboard/` on the backend host (or `/`, which redirects there). The
dashboard uses the existing administrator login and same-origin API. No frontend
build or additional service is required. The first milestone supports creating
the club, searching/filtering participants, creating member/guest accounts,
linking existing accounts by ID, editing names/phone numbers, and changing the
signed-in administrator's password. JWTs are held only in page memory; refreshing
or closing the page signs out. The server still enforces all club permissions.
Directory totals cover at most the first 1000 returned participants. Members supports loft location management; Race operations supports pigeon/ring setup, race controls, readers, QR labels and evidence review. The member-only page is `/dashboard/member.html`.
Password changes do not revoke existing JWTs; the UI signs out after success.

## Club API

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

Migration `012` adds an optional loft `address` (500 characters), editable in the Members GPS dialog and shown with the coordinates. It is a user-entered place label; GPS capture does not automatically look up an address.

## Reliability and Race operations

Apply migration `013` before running this local revision. The new Race operations tab supports pigeon/ring registration, race setup/registration/release/close, private QR PNG issuance and revocation, evidence review and physical guest verification. The guest page has a durable no-secret recovery ledger and an authenticated receipt lookup. PostgreSQL rate budgets are shared across instances. See `../docs/clocking-reliability.md` for configuration, policy, tests and limitations. Confirm the approved revision and migration ledger before deploying local changes.

Reader setup and live gateway monitoring require migration `014`. See [reader monitoring](../docs/reader-monitoring.md) for provisioning, credentials, configuration and heartbeat semantics.
