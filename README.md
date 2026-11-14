# Pigeon Racing Clocking System

Single-club pigeon racing platform. Software development in progress; RFID hardware details pending.

## User documentation

See the [app user guide](docs/user-guide.md) for administrator setup, members and loft GPS, races, guest QR clocking, RFID gateway installation, remote testing, live standings and troubleshooting.

For the operator in Surigao, use the [hardware test instructions](docs/surigao-hardware-test-guide.md). The [scan-to-arrival audit](docs/functionality-audit-2026-11-07.md) records current local test results and remaining physical/timing limitations.

## Local configuration
Copy `.env.example` to `.env` and supply real values locally. Never commit `.env`, credentials, private club/member data, or production secrets. For deployments, use protected environment secrets.

## Status
The FastAPI backend is in `backend/`, including race registration, provisional clocking, results review, and initial club administration. See [backend setup](backend/README.md) and [migration instructions](docs/render-postgres-migrations.md). Development continues on `develop`.
