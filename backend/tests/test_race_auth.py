"""API authorization smoke checks: database routes fail closed without token."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_races_requires_token():
    response = client.get("/races")
    assert response.status_code in (401, 503)

def test_create_race_requires_token():
    response = client.post("/races", json={
        "name":"Test Race", "release_latitude":9.8,"release_longitude":125.5
    })
    assert response.status_code in (401, 503)
