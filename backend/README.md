# Dove Racing Backend — development prototype

Implemented: GPS Haversine distance, flight speed, unit conversion, leaderboard grouping, and FastAPI `/health` and `/calculations/flight` endpoints. **The earlier full race-management API and 18-table PostgreSQL draft have not yet been imported into this repository.** No official RFID/QR clocking is enabled.

## Run locally

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
python -m pytest -q
```

Use `.env.example` to create a local `.env`; never commit real credentials. Production work remaining: PostgreSQL migrations, role-based authentication, secure QR submissions, RFID ingestion, review workflows, immutable results, and integration tests.
