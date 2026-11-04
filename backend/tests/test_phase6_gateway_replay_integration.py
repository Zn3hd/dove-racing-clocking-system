"""Phase 6 gateway replay contract against disposable PostgreSQL."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL required"
)


def test_lost_gateway_acknowledgement_creates_only_one_backend_event(scenario):
    s = scenario
    client = s["client"]
    admin = s["headers"](s["admin"])
    race = make_race(s)
    register(s, race, s["pigeon_member"], "RFID")
    provision = client.post(f"/devices/{s['device']}/provision", headers=admin)
    assert provision.status_code == 200, provision.text
    assert client.post(f"/races/{race}/activate", headers=admin).status_code == 200

    endpoint = f"/devices/{s['device']}/arrivals"
    headers = {"X-Device-Token": provision.json()["device_token"]}
    message_id = str(uuid4())
    payload = {
        "message_id": message_id,
        "race_id": race,
        "ring_uid": f"RFID-{s['ring']}",
        "offline_buffered": True,
        "device_recorded_at": "2026-01-01T00:00:00Z",
        "adapter_type": "serial",
        "capture_mode": "automatic",
        "protocol": "line_ascii",
        "original_scan": f"RFID-{s['ring']}",
    }
    first = client.post(endpoint, headers=headers, json=payload)
    assert first.status_code == 202, first.text
    assert first.json()["duplicate_request"] is False
    assert first.json()["official_result_created"] is False

    # Simulate a lost HTTP response: the same durable envelope is sent again.
    for _ in range(2):
        replay = client.post(endpoint, headers=headers, json=payload)
        assert replay.status_code == 202, replay.text
        assert replay.json()["duplicate_request"] is True
        assert replay.json()["event_id"] == first.json()["event_id"]
        assert replay.json()["official_result_created"] is False

    changed = client.post(endpoint, headers=headers,
                          json={**payload, "original_scan": "TAMPERED"})
    assert changed.status_code == 409, changed.text

    with s["engine"].connect() as db:
        event_count = db.execute(text("""
            SELECT count(*) FROM clocking_events
            WHERE device_id=:device AND id=:event
        """), {"device": s["device"], "event": first.json()["event_id"]}).scalar_one()
        message_count = db.execute(text("""
            SELECT count(*) FROM device_gateway_messages
            WHERE device_id=:device AND message_id=:message
        """), {"device": s["device"], "message": message_id}).scalar_one()
        total_events = db.execute(text("""
            SELECT count(*) FROM clocking_events WHERE device_id=:device
        """), {"device": s["device"]}).scalar_one()
    assert event_count == 1
    assert message_count == 1
    assert total_events == 1
