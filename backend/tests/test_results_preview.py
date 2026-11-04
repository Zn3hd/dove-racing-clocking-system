"""Leaderboard preview unit and access tests."""
from fastapi.testclient import TestClient
from app.main import app
from app.calculations import leaderboard

client=TestClient(app)

def test_preview_requires_authentication():
    response=client.get("/races/00000000-0000-0000-0000-000000000001/leaderboard-preview")
    assert response.status_code==401

def test_separate_rankings_and_ties():
    rows=[
        {"entry_id":"a","clocking_method":"RFID","qualifying_status":"qualified",
         "verification_status":"provisional","speed_mpm":1000,
         "arrival_at":"2026-01-01T10:00:00"},
        {"entry_id":"b","clocking_method":"QR","qualifying_status":"qualified",
         "verification_status":"provisional","speed_mpm":1000,
         "arrival_at":"2026-01-01T10:01:00"},
        {"entry_id":"c","clocking_method":"RFID","qualifying_status":"below_minimum",
         "verification_status":"provisional","speed_mpm":100,
         "arrival_at":"2026-01-01T10:02:00"},
    ]
    separate=leaderboard(rows,"separate")
    assert len(separate)==2
    assert {r["leaderboard"] for r in separate}=={"member","guest"}
    assert all(r["rank"]==1 for r in separate)
    combined=leaderboard(rows,"combined")
    assert len(combined)==2
    assert all(r["rank"]==1 for r in combined)


def test_combined_ranking_ignores_nonqualifying_evidence_and_preserves_ties():
    rows = [
        {"entry_id": "rfid-1", "clocking_method": "RFID", "qualifying_status": "qualified",
         "verification_status": "provisional", "speed_mpm": 1200, "arrival_at": "2026-01-01T10:00:00"},
        {"entry_id": "qr-1", "clocking_method": "QR", "qualifying_status": "qualified",
         "verification_status": "approved", "speed_mpm": 1200, "arrival_at": "2026-01-01T10:01:00"},
        {"entry_id": "rfid-2", "clocking_method": "RFID", "qualifying_status": "qualified",
         "verification_status": "provisional", "speed_mpm": 1100, "arrival_at": "2026-01-01T10:02:00"},
        {"entry_id": "qr-slow", "clocking_method": "QR", "qualifying_status": "below_minimum",
         "verification_status": "approved", "speed_mpm": 400, "arrival_at": "2026-01-01T10:03:00"},
        {"entry_id": "unreviewed", "clocking_method": "QR", "qualifying_status": "qualified",
         "verification_status": "pending", "speed_mpm": 1300, "arrival_at": "2026-01-01T10:04:00"},
    ]
    combined = leaderboard(rows, "combined")
    assert [(r["entry_id"], r["rank"]) for r in combined] == [
        ("rfid-1", 1), ("qr-1", 1), ("rfid-2", 3)]
    separate = leaderboard(rows, "separate")
    assert [(r["entry_id"], r["leaderboard"], r["rank"]) for r in separate] == [
        ("qr-1", "guest", 1), ("rfid-1", "member", 1), ("rfid-2", "member", 2)]
