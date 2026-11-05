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


def test_finalization_readiness_requires_admin_token():
    from uuid import uuid4
    response = client.get(f"/races/{uuid4()}/finalization-readiness")
    assert response.status_code in (401, 503)


def test_finalization_readiness_never_certifies_untrusted_evidence():
    from app.routers.finalization import finalization_readiness, FINALIZATION_BLOCKERS

    for status in ("draft", "open", "active", "closed", "finalized"):
        result = finalization_readiness(status)
        assert result["ready"] is False
        assert result["official"] is False
        assert result["race_status"] == status
        assert all(blocker in result["blockers"] for blocker in FINALIZATION_BLOCKERS)
        if status != "closed":
            assert any("must be closed" in item for item in result["blockers"])
