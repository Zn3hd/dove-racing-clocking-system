"""Phase 4 smoke tests that do not require a running database."""
from fastapi.testclient import TestClient
from app.main import app
from app.routers.clocking import token_hash

client = TestClient(app)

def test_token_hash_is_deterministic_and_not_plaintext():
    raw = "example-token-value"
    assert token_hash(raw) == token_hash(raw)
    assert token_hash(raw) != raw
    assert len(token_hash(raw)) == 64

def test_guest_scan_requires_bearer_token():
    response = client.post("/clocking/qr/scans", json={
        "entry_id": "00000000-0000-0000-0000-000000000001",
        "token": "a" * 48,
        "idempotency_key": "00000000-0000-0000-0000-000000000002",
    })
    assert response.status_code == 401

def test_rfid_simulator_requires_admin_token():
    response = client.post("/clocking/rfid/simulate", json={
        "race_id": "00000000-0000-0000-0000-000000000001",
        "device_id": "00000000-0000-0000-0000-000000000002",
        "rfid_uid": "SIM-123",
        "idempotency_key": "00000000-0000-0000-0000-000000000003",
    })
    assert response.status_code == 401

def test_qr_token_issuance_requires_admin():
    response = client.post("/clocking/qr/tokens", json={
        "entry_id": "00000000-0000-0000-0000-000000000001"
    })
    assert response.status_code == 401

def test_event_review_requires_admin():
    response = client.post(
        "/clocking/events/00000000-0000-0000-0000-000000000001/review",
        json={"decision":"reject","reason":"Invalid clocking evidence"},
    )
    assert response.status_code == 401
