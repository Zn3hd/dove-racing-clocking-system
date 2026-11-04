"""Phase 8 approval workflow on disposable PostgreSQL."""
import os
from uuid import uuid4

import pytest
from test_postgres_e2e import scenario

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL required")


def test_public_application_requires_admin_approval(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    club_response = c.post("/clubs", headers=admin, json={"name": "Application Test Club"})
    assert club_response.status_code == 201, club_response.text
    club = club_response.json()["id"]
    email = f"applicant-{uuid4()}@example.test"
    password = "secure-test-application-password"
    application = {"club_id":club,"full_name":"Prospective Member",
                   "email":email,"password":password}
    assert c.get("/membership/clubs").status_code == 200
    response = c.post("/membership/applications", json=application)
    assert response.status_code == 202, response.text
    application_id = response.json()["application_id"]
    assert c.post("/auth/login", json={"email":email,"password":password}).status_code == 401
    assert c.post("/membership/applications", json=application).status_code == 409
    status = c.post("/membership/status", json={"email":email,"password":password})
    assert status.status_code == 200 and status.json()["status"] == "pending"
    assert c.post("/membership/status", json={"email":email,"password":"wrong"}).status_code == 401
    assert c.get("/membership/applications", params={"club_id":club}).status_code == 401
    assert c.get("/membership/applications", params={"club_id":club},
                 headers=s["headers"](s["member"])).status_code == 403
    pending = c.get("/membership/applications", params={"club_id":club}, headers=admin)
    assert pending.status_code == 200 and any(a["id"] == application_id for a in pending.json())
    assert "password_hash" not in pending.text
    approved = c.post(f"/membership/applications/{application_id}/decision",
                      headers=admin, json={"decision":"approve"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    s["extra_user_ids"].append(approved.json()["member_id"])
    assert c.post("/auth/login", json={"email":email,"password":password}).status_code == 200
    assert c.post(f"/membership/applications/{application_id}/decision",
                  headers=admin,json={"decision":"decline"}).status_code == 409
    assert c.post("/membership/status", json={"email":email,"password":password}).json()["status"] == "approved"


def test_declined_application_never_activates_account(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    club = c.post("/clubs",headers=admin,json={"name":"Decline Test Club"}).json()["id"]
    email = f"declined-{uuid4()}@example.test"
    password = "secure-test-declined-password"
    created = c.post("/membership/applications",json={"club_id":club,
        "full_name":"Declined Applicant","email":email,"password":password})
    assert created.status_code == 202
    response = c.post("/membership/applications/" + created.json()["application_id"] + "/decision",
        headers=admin,json={"decision":"decline","reason":"Membership requirements not met"})
    assert response.status_code == 200 and response.json()["member_id"] is None
    assert c.post("/auth/login",json={"email":email,"password":password}).status_code == 401
    status = c.post("/membership/status",json={"email":email,"password":password}).json()
    assert status["status"] == "declined"
    assert status["reason"] == "Membership requirements not met"
