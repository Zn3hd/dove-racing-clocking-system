from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_is_not_official():
    r=client.get("/health")
    assert r.status_code == 200
    assert r.json()["official_clocking_enabled"] is False

def test_calculate_flight():
    payload={"release_latitude":0,"release_longitude":0,"loft_latitude":0,
             "loft_longitude":1,"release_at":"2026-10-30T06:00:00+00:00",
             "arrival_at":"2026-10-30T08:00:00+00:00"}
    r=client.post("/calculations/flight",json=payload)
    assert r.status_code==200
    assert 900 < r.json()["speed_mpm"] < 940
    assert r.json()["qualifies_minimum_speed"] is True

def test_rejects_invalid_duration():
    payload={"release_latitude":0,"release_longitude":0,"loft_latitude":0,
             "loft_longitude":1,"release_at":"2026-10-30T08:00:00+00:00",
             "arrival_at":"2026-10-30T06:00:00+00:00"}
    assert client.post("/calculations/flight",json=payload).status_code==422
