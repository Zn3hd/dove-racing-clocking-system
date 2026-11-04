"""Member dashboard access and owner-scoping integration checks."""
import os
import pytest
from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL required"
)


def test_member_overview_requires_member_role_and_scopes_private_data(scenario):
    s = scenario
    c = s["client"]
    endpoint = "/member/overview"
    assert c.get(endpoint).status_code == 401
    assert c.get(endpoint, headers=s["headers"](s["admin"])).status_code == 403
    assert c.get(endpoint, headers=s["headers"](s["guest"])).status_code == 403

    race = make_race(s)
    member_entry = register(s, race, s["pigeon_member"], "RFID")
    guest_entry = register(s, race, s["pigeon_guest"], "QR")
    response = c.get(endpoint, headers=s["headers"](s["member"]))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["official"] is False
    assert data["refresh_after_seconds"] == 15
    assert {p["id"] for p in data["pigeons"]} == {str(s["pigeon_member"])}
    assert {e["entry_id"] for e in data["race_entries"]} == {member_entry}
    assert guest_entry not in str(data)
    assert str(s["pigeon_guest"]) not in str(data)


def test_member_dashboard_static_assets_are_served_without_admin_access(scenario):
    client = scenario["client"]
    for path, expected in (
        ("/dashboard/member.html", "Race Command Center"),
        ("/dashboard/member.css", ".shell"),
        ("/dashboard/member.js", "/member/overview"),
    ):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert expected in response.text
        assert "no-store" in response.headers["cache-control"]
        assert "default-src 'self'" in response.headers["content-security-policy"]


def test_member_standings_are_scoped_and_do_not_expose_private_identifiers(scenario):
    s = scenario
    c = s["client"]
    race = make_race(s)
    register(s, race, s["pigeon_member"], "RFID")
    endpoint = f"/member/races/{race}/standings"
    assert c.get(endpoint).status_code == 401
    assert c.get(endpoint, headers=s["headers"](s["admin"])).status_code == 403
    assert c.get(endpoint, headers=s["headers"](s["guest"])).status_code == 403
    response = c.get(endpoint, headers=s["headers"](s["member"]))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["official"] is False
    assert result["entries"] == []
    assert "device_id" not in response.text
    assert "rfid_uid" not in response.text
