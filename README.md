# Dove Racing Clocking System

Single-club pigeon racing platform. Software development in progress; RFID hardware details pending.

## Local configuration
Copy `.env.example` to `.env` and supply real values locally. Never commit `.env`, credentials, private club/member data, or production secrets. For deployments, use protected environment secrets.

## Status
The FastAPI backend is in `backend/`, including race registration, provisional clocking, results review, and initial club administration. See [backend setup](backend/README.md) and [migration instructions](docs/render-postgres-migrations.md). Development continues on `develop`.
