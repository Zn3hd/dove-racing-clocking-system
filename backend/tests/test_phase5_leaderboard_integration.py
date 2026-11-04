"""Phase 5 leaderboard selection regression tests on disposable PostgreSQL."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL required"
)


def test_rejected_first_arrival_falls_back_to_next_reviewed_event(scenario):
    s = scenario
    client = s["client"]
    admin = s["headers"](s["admin"])
    guest = s["headers"](s["guest"])
    race = make_race(s)
    entry = register(s, race, s["pigeon_guest"], "QR")
    issued = client.post("/clocking/qr/tokens", headers=admin, json={"entry_id": entry})
    assert issued.status_code == 201, issued.text
    assert client.post(f"/races/{race}/activate", headers=admin).status_code == 200
    with s["engine"].begin() as db:
        db.execute(text(
            "UPDATE races SET actual_release_at=now()-interval '30 minutes' WHERE id=:id"
        ), {"id": race})

    def scan():
        response = client.post("/clocking/qr/scans", headers=guest, json={
            "entry_id": entry, "token": issued.json()["token"],
            "idempotency_key": str(uuid4()),
        })
        assert response.status_code == 202, response.text
        return response.json()["event_id"]

    first = scan()
    second = scan()
    assert first != second
    preview_url = f"/races/{race}/leaderboard-preview"
    live_url = f"/races/{race}/live"
    assert client.get(preview_url, headers=admin).json()["entries"] == []
    assert client.get(live_url, headers=admin).json()["entries"] == []

    rejected = client.post(f"/clocking/events/{first}/review", headers=admin,
                           json={"decision": "reject", "reason": "First scan rejected"})
    assert rejected.status_code == 200, rejected.text
    approved = client.post(f"/clocking/events/{second}/review", headers=admin,
                           json={"decision": "approve", "reason": "Second scan verified"})
    assert approved.status_code == 200, approved.text

    for url in (preview_url, live_url):
        response = client.get(url, headers=admin)
        assert response.status_code == 200, response.text
        assert response.json()["official"] is False
        entries = response.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["entry_id"] == entry
        assert entries[0]["event_id"] == second
        assert entries[0]["rank"] == 1

    replay = client.post("/clocking/qr/scans", headers=guest, json={
        "entry_id": entry, "token": issued.json()["token"],
        "idempotency_key": str(uuid4()),
    })
    assert replay.status_code == 202, replay.text
    for url in (preview_url, live_url):
        entries = client.get(url, headers=admin).json()["entries"]
        assert len(entries) == 1
        assert entries[0]["event_id"] == second
