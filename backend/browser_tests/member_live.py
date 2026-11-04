"""Real Chromium -> FastAPI -> disposable PostgreSQL member dashboard integration.

Uses qr_live's isolated database/server fixture; no mocked login or overview API.
"""
import os
from uuid import uuid4

import psycopg
import pytest
from playwright.sync_api import expect, sync_playwright

from qr_live import live_server, ok

pytestmark = pytest.mark.skipif(
    not os.getenv("QR_AUDIT_DATABASE_URL"),
    reason="Requires disposable localhost browser audit PostgreSQL",
)
PASSWORD = "Member-browser-test-password-2026"


def test_member_login_private_pigeons_and_expired_session(live_server):
    from app.auth import hash_password

    server = live_server
    own_ring = "MEMBER-OWN-" + uuid4().hex[:8]
    other_ring = "MEMBER-OTHER-" + uuid4().hex[:8]
    own_email = "member-" + uuid4().hex + "@example.test"
    other_email = "member-" + uuid4().hex + "@example.test"
    own_pigeon_id = None
    with psycopg.connect(server["pg"]) as db:
        for email, ring in ((own_email, own_ring), (other_email, other_ring)):
            uid, loft_id = uuid4(), uuid4()
            db.execute("""INSERT INTO users(id,role_code,full_name,email,password_hash)
                VALUES (%s,'member','Browser Test Member',%s,%s)""",
                (uid, email, hash_password(PASSWORD)))
            db.execute("""INSERT INTO lofts(id,user_id,name,latitude,longitude,verified_at)
                VALUES (%s,%s,'Browser Test Loft',9.8,125.5,now())""",
                (loft_id, uid))
            pigeon_id = uuid4()
            db.execute("""INSERT INTO pigeons(id,loft_id,official_ring_number,status)
                VALUES (%s,%s,%s,'active')""", (pigeon_id, loft_id, ring))
            if email == own_email:
                own_pigeon_id = pigeon_id
                db.execute("INSERT INTO rfid_rings(pigeon_id,uid) VALUES (%s,%s)",
                           (pigeon_id, "RFID-" + own_ring))

    api = server["api"]
    admin_token = ok(api.post("/auth/login", json={
        "email": "chairman@qr-audit.example.test",
        "password": "Audit-chairman-password-2026",
    }))["access_token"]
    headers = {"Authorization": "Bearer " + admin_token}
    race_id = ok(api.post("/races", headers=headers, json={
        "name": "Member Browser Race", "release_latitude": 10,
        "release_longitude": 125.6,
    }), 201)["id"]
    assert api.post(f"/races/{race_id}/open", headers=headers).status_code == 200
    entry = api.post(f"/races/{race_id}/entries", headers=headers, json={
        "pigeon_id": str(own_pigeon_id), "expected_method": "RFID",
    })
    assert entry.status_code == 201, entry.text

    errors = []
    with sync_playwright() as tool:
        options = {"headless": True}
        if os.getenv("BROWSER_EXECUTABLE"):
            options["executable_path"] = os.environ["BROWSER_EXECUTABLE"]
        browser = tool.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        try:
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(server["origin"] + "/dashboard/member.html")
            expect(page.get_by_role("heading", name="Member sign in")).to_be_visible()
            page.locator("#login-form [name=email]").fill(own_email)
            page.locator("#login-form [name=password]").fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#workspace")).to_be_visible()
            expect(page.locator("#pigeons")).to_contain_text(own_ring)
            assert other_ring not in page.locator("body").inner_text()
            expect(page.locator("#pigeon-count")).to_have_text("1")
            expect(page.locator("#entries")).to_contain_text("Member Browser Race")
            expect(page.locator("#entries")).to_contain_text("No scan recorded")
            assert page.evaluate("localStorage.length + sessionStorage.length") == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("#workspace button").all_text_contents() == ["Refresh"]

            # A real API 401 invalidates the browser's in-memory session.
            page.route("**/member/overview", lambda route: route.fulfill(
                status=401, json={"detail": "Session expired"}))
            page.get_by_role("button", name="Refresh", exact=True).click()
            expect(page.locator("#workspace")).to_be_hidden()
            expect(page.locator("#login-error")).to_contain_text("Session expired")
            assert page.evaluate("localStorage.length + sessionStorage.length") == 0
            assert not errors, errors

            # Admin credentials must not unlock the member-only interface.
            page.unroute("**/member/overview")
            page.locator("#login-form [name=email]").fill("chairman@qr-audit.example.test")
            page.locator("#login-form [name=password]").fill("Audit-chairman-password-2026")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#login-error")).to_contain_text("member accounts only")
            expect(page.locator("#workspace")).to_be_hidden()
            assert not errors, errors
        finally:
            context.close()
            browser.close()
