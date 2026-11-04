"""Phase 4 clocking authorization, replay, and race-state integration tests.

Uses disposable PostgreSQL and the established scenario fixture.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL required"
)


def test_qr_replay_does_not_create_second_event_and_changed_evidence_conflicts(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    guest = s["headers"](s["guest"])
    race = make_race(s)
    entry = register(s, race, s["pigeon_guest"], "QR")
    token = c.post("/clocking/qr/tokens", headers=admin,
                   json={"entry_id": entry})
    assert token.status_code == 201, token.text
    assert c.post(f"/races/{race}/activate", headers=admin).status_code == 200
    payload = {"entry_id": entry, "token": token.json()["token"],
               "idempotency_key": str(uuid4()), "capture_source": "web_camera"}
    assert c.post("/clocking/qr/scans", json=payload).status_code == 401
    assert c.post("/clocking/qr/scans",
                  headers=s["headers"](s["other"]), json=payload).status_code == 403
    first = c.post("/clocking/qr/scans", headers=guest, json=payload)
    assert first.status_code == 202, first.text
    assert first.json()["official_result_created"] is False
    replay = c.post("/clocking/qr/scans", headers=guest, json=payload)
    assert replay.status_code == 202, replay.text
    assert replay.json()["duplicate_request"] is True
    assert replay.json()["event_id"] == first.json()["event_id"]
    changed = c.post("/clocking/qr/scans", headers=guest,
                     json={**payload, "capture_source": "manual"})
    assert changed.status_code == 409, changed.text
    with s["engine"].begin() as db:
        count = db.execute(text("""
            SELECT count(*) FROM clocking_events
            WHERE idempotency_key=:key
        """), {"key": payload["idempotency_key"]}).scalar_one()
    assert count == 1


def test_qr_new_submission_rejected_after_race_close(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    guest = s["headers"](s["guest"])
    race = make_race(s)
    entry = register(s, race, s["pigeon_guest"], "QR")
    issued = c.post("/clocking/qr/tokens", headers=admin,
                    json={"entry_id": entry})
    assert issued.status_code == 201, issued.text
    assert c.post(f"/races/{race}/activate", headers=admin).status_code == 200
    assert c.post(f"/races/{race}/close", headers=admin).status_code == 200
    response = c.post("/clocking/qr/scans", headers=guest, json={
        "entry_id": entry, "token": issued.json()["token"],
        "idempotency_key": str(uuid4()),
    })
    assert response.status_code == 409, response.text


def test_gateway_requires_credentials_and_active_race(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    club = c.post("/clubs", headers=admin,
                  json={"name": "Gateway phase 4 validation club"})
    assert club.status_code == 201, club.text
    joined = c.post(f"/clubs/{club.json()['id']}/members", headers=admin,
                    json={"user_id": str(s["member"])})
    assert joined.status_code == 201, joined.text
    issued = c.post(f"/devices/{s['device']}/provision", headers=admin)
    assert issued.status_code == 200, issued.text
    race = make_race(s)  # Open, not active.
    register(s, race, s["pigeon_member"], "RFID")
    payload = {"message_id": str(uuid4()), "race_id": race,
               "ring_uid": f"RFID-{s['ring']}"}
    url = f"/devices/{s['device']}/arrivals"
    assert c.post(url, json=payload).status_code == 401
    assert c.post(url, headers={"X-Device-Token": "invalid"},
                  json=payload).status_code == 401
    response = c.post(url, headers={"X-Device-Token": issued.json()["device_token"]},
                      json=payload)
    assert response.status_code == 409, response.text
    with s["engine"].begin() as db:
        count = db.execute(text("""
            SELECT count(*) FROM clocking_events WHERE device_id=:device
        """), {"device": s["device"]}).scalar_one()
    assert count == 0
