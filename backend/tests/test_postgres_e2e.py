"""End-to-end API tests against a real disposable PostgreSQL database.

CI provisions PostgreSQL and applies the actual schema before this suite.
Tests use unique UUIDs and remove their own rows in FK-safe order.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app.main import app
from app.auth import hash_password, issue_token

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required for PostgreSQL integration tests"
)

@pytest.fixture
def scenario(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-only-secret-" + "x"*64)
    from app import database
    database._engine = None
    database._factory = None
    engine = create_engine(url)
    admin, guest, other, member = [uuid4() for _ in range(4)]
    loft_guest, loft_other, loft_member = [uuid4() for _ in range(3)]
    pigeon_guest, pigeon_other, pigeon_member = [uuid4() for _ in range(3)]
    device, ring = uuid4(), uuid4()
    with engine.begin() as db:
        for uid, role in [(admin,"chairman"),(guest,"guest"),(other,"guest"),(member,"member")]:
            db.execute(text("""INSERT INTO users(id,role_code,full_name,email,password_hash)
                VALUES (:id,:role,'Test Account',:email,:password)"""),
                {"id":uid,"role":role,"email":f"{uid}@example.test","password":hash_password("integration-password-123")})
        for loft, uid in [(loft_guest,guest),(loft_other,other),(loft_member,member)]:
            db.execute(text("""INSERT INTO lofts(id,user_id,name,latitude,longitude,verified_at,verified_by)
                VALUES (:id,:uid,'Test Loft',9.8,125.5,now(),:admin)"""),
                {"id":loft,"uid":uid,"admin":admin})
        for pid, loft in [(pigeon_guest,loft_guest),(pigeon_other,loft_other),(pigeon_member,loft_member)]:
            db.execute(text("""INSERT INTO pigeons(id,loft_id,official_ring_number,status)
                VALUES (:id,:loft,:ring,'active')"""),
                {"id":pid,"loft":loft,"ring":f"TEST-{pid}"})
        db.execute(text("""INSERT INTO rfid_rings(id,pigeon_id,uid)
            VALUES (:id,:pigeon,:uid)"""),{"id":ring,"pigeon":pigeon_member,"uid":f"RFID-{ring}"})
        db.execute(text("""INSERT INTO devices(id,loft_id,device_identifier)
            VALUES (:id,:loft,:identifier)"""),
            {"id":device,"loft":loft_member,"identifier":f"SIM-{device}"})
    data = locals().copy()
    data["engine"] = engine
    data["client"] = TestClient(app)
    data["headers"] = lambda uid: {"Authorization":f"Bearer {issue_token(uid)}"}
    data["extra_user_ids"] = []
    yield data
    # Remove all test-created rows, including audited events, before accounts.
    with engine.begin() as db:
        ids = [admin,guest,other,member] + data["extra_user_ids"]
        pigeon_ids = db.execute(text("""SELECT p.id FROM pigeons p JOIN lofts l ON l.id=p.loft_id
            WHERE l.user_id=ANY(:ids)"""), {"ids": ids}).scalars().all()
        db.execute(text("DELETE FROM audit_logs WHERE actor_id = ANY(:ids)"), {"ids":ids})
        db.execute(text("DELETE FROM messenger_account_links WHERE user_id = ANY(:ids)"), {"ids":ids})
        db.execute(text("""DELETE FROM guest_arrival_verifications WHERE verified_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("DELETE FROM device_gateway_messages WHERE device_id=:device"), {"device":device})
        db.execute(text("DELETE FROM device_gateway_credentials WHERE device_id=:device"), {"device":device})
        db.execute(text("""DELETE FROM clocking_reviews WHERE reviewed_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("""DELETE FROM clocking_event_sources WHERE event_id IN (SELECT id FROM clocking_events WHERE submitted_by = ANY(:ids) OR device_id=:device)"""), {"ids":ids,"device":device})
        db.execute(text("""DELETE FROM clocking_events WHERE submitted_by = ANY(:ids) OR device_id=:device"""), {"ids":ids,"device":device})
        db.execute(text("""DELETE FROM qr_tokens WHERE pigeon_id = ANY(:ids)"""),
                   {"ids":pigeon_ids})
        db.execute(text("""DELETE FROM race_entries WHERE pigeon_id = ANY(:ids)"""),
                   {"ids":pigeon_ids})
        db.execute(text("DELETE FROM races WHERE created_by = :id"), {"id":admin})
        db.execute(text("DELETE FROM club_memberships WHERE club_id IN (SELECT id FROM clubs WHERE created_by=:id)"), {"id":admin})
        db.execute(text("DELETE FROM clubs WHERE created_by=:id"), {"id":admin})
        db.execute(text("DELETE FROM devices WHERE id=:id"), {"id":device})
        db.execute(text("DELETE FROM rfid_rings WHERE id=:id"), {"id":ring})
        db.execute(text("DELETE FROM pigeons WHERE id = ANY(:ids)"),
                   {"ids":pigeon_ids})
        db.execute(text("DELETE FROM lofts WHERE user_id = ANY(:ids)"), {"ids":ids})
        db.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids":ids})
    engine.dispose()
    database._engine = None
    database._factory = None

def test_club_creation_membership_and_access(scenario):
    s = scenario
    client = s["client"]
    admin = s["headers"](s["admin"])
    guest = s["headers"](s["guest"])
    assert client.get("/clubs").status_code == 401
    assert client.get("/clubs", headers=guest).status_code == 403
    assert client.post("/clubs", headers=admin, json={"name": "  "}).status_code == 422
    created = client.post("/clubs", headers=admin, json={"name": "  Test Club  "})
    assert created.status_code == 201, created.text
    club = created.json()["id"]
    assert created.json()["name"] == "Test Club"
    assert client.post("/clubs", headers=admin, json={"name": "Second Club"}).status_code == 409
    listed = client.get("/clubs", headers=admin)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [club]
    path = f"/clubs/{club}/members"
    initial = client.get(path, headers=admin)
    assert initial.status_code == 200
    assert [(row["id"], row["club_role"]) for row in initial.json()] == [(str(s["admin"]), "admin")]
    for user, role in [(s["member"], "member"), (s["guest"], "guest")]:
        payload = {"user_id": str(user)}
        added = client.post(path, headers=admin, json=payload)
        assert added.status_code == 201, added.text
        assert added.json()["role"] == role
        assert client.post(path, headers=admin, json=payload).status_code == 409
    assert client.get(path, headers=guest).status_code == 403
    assert client.post(path, headers=guest, json={"user_id": str(s["other"])}).status_code == 403
    assert client.post(path, headers=admin, json={"user_id": str(uuid4())}).status_code == 422
    assert client.post(path, headers=admin, json={"user_id": str(s["admin"])}).status_code == 422
    def add_same_guest(_):
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(path, headers=admin,
                                          json={"user_id": str(s["other"])}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(add_same_guest, range(2))) == [201, 409]
    # Global administrator privileges alone do not grant another club's access.
    with s["engine"].begin() as db:
        db.execute(text("UPDATE users SET role_code='president' WHERE id=:id"), {"id": s["other"]})
        db.execute(text("UPDATE users SET status='inactive' WHERE id=:id"), {"id": s["member"]})
    outsider = s["headers"](s["other"])
    assert client.get("/clubs", headers=outsider).json() == []
    assert client.get(path, headers=outsider).status_code == 403
    assert client.post(path, headers=outsider, json={"user_id": str(s["guest"])}).status_code == 403
    assert client.post(path, headers=admin, json={"user_id": str(s["member"])}).status_code == 422
    with s["engine"].connect() as db:
        actions = db.execute(text("SELECT action FROM audit_logs WHERE actor_id=:id AND entity_type='club'"),
                             {"id": s["admin"]}).scalars().all()
    assert sorted(actions) == ["club.created"] + ["club.member_added"] * 3


def test_race_club_isolation_and_legacy_ownership(scenario):
    s = scenario
    client = s["client"]
    admin = s["headers"](s["admin"])
    outsider = s["headers"](s["other"])
    with s["engine"].begin() as db:
        db.execute(text("UPDATE users SET role_code='president' WHERE id=:id"), {"id": s["other"]})
    legacy = make_race(s)
    assert client.post(f"/races/{legacy}/activate", headers=outsider).status_code == 403
    created = client.post("/clubs", headers=admin, json={"name": "Race Test Club"})
    assert created.status_code == 201, created.text
    club = created.json()["id"]
    race_payload = {"name": "Scoped race", "release_latitude": 10, "release_longitude": 125.6}
    assert client.post("/races", headers=outsider, json=race_payload).status_code == 403
    scoped = client.post("/races", headers=admin, json=race_payload)
    assert scoped.status_code == 201, scoped.text
    race = scoped.json()["id"]
    assert scoped.json()["club_id"] == club
    assert client.get("/races", headers=outsider).json() == []
    assert {r["id"] for r in client.get("/races", headers=admin).json()} == {legacy, race}
    for suffix in ("open", "activate", "close", "finalize"):
        assert client.post(f"/races/{race}/{suffix}", headers=outsider).status_code == 403
    for path in (f"/races/{race}/entries", f"/races/{race}/leaderboard-preview",
                 f"/clocking/events?race_id={race}"):
        assert client.get(path, headers=outsider).status_code == 403
    assert client.post(f"/races/{race}/open", headers=admin).status_code == 200
    entry_payload = {"pigeon_id": str(s["pigeon_guest"]), "expected_method": "QR"}
    assert client.post(f"/races/{race}/entries", headers=outsider, json=entry_payload).status_code == 403
    assert client.post(f"/races/{race}/entries", headers=admin, json=entry_payload).status_code == 422
    assert client.post(f"/clubs/{club}/members", headers=admin,
                       json={"user_id": str(s["guest"])}).status_code == 201
    entry = register(s, race, s["pigeon_guest"], "QR")
    assert client.post("/clocking/qr/tokens", headers=outsider,
                       json={"entry_id": entry}).status_code == 403
    token = client.post("/clocking/qr/tokens", headers=admin, json={"entry_id": entry})
    assert token.status_code == 201, token.text
    assert client.post(f"/races/{race}/activate", headers=admin).status_code == 200
    scan = client.post("/clocking/qr/scans", headers=s["headers"](s["guest"]), json={
        "entry_id": entry, "token": token.json()["token"], "idempotency_key": str(uuid4())})
    assert scan.status_code == 202, scan.text
    event = scan.json()["event_id"]
    assert client.get(f"/clocking/events/{event}/source", headers=outsider).status_code == 403
    assert client.get(f"/clocking/events/{event}/source", headers=admin).status_code == 200
    assert client.post(f"/clocking/events/{event}/review", headers=outsider,
                       json={"decision": "approve", "reason": "Test review evidence"}).status_code == 403
    assert client.post(f"/clocking/events/{event}/guest-verification", headers=outsider, json={
        "decision": "confirmed", "ring_number_seen": "TEST", "evidence_note": "Test physical evidence"
    }).status_code == 403
    assert client.post("/clocking/rfid/simulate", headers=outsider, json={
        "race_id": race, "device_id": str(s["device"]), "rfid_uid": "TEST",
        "idempotency_key": str(uuid4())}).status_code == 403


def test_club_participant_asset_management(scenario):
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    outsider = s["headers"](s["other"])
    with s["engine"].begin() as db:
        db.execute(text("UPDATE users SET role_code='president' WHERE id=:id"), {"id": s["other"]})
    club = c.post("/clubs", headers=admin, json={"name": "Asset Test Club"}).json()["id"]
    for uid in (s["member"], s["guest"]):
        assert c.post(f"/clubs/{club}/members", headers=admin,
                      json={"user_id": str(uid)}).status_code == 201
    payload = {"full_name": "New Member", "email": f"{uuid4()}@example.test",
               "password": "test-member-password", "role": "member"}
    assert c.post("/participants", headers=outsider, json=payload).status_code == 403
    created = c.post("/participants", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    uid = created.json()["id"]
    s["extra_user_ids"].append(UUID(uid))
    for path in ("/participants", "/lofts", "/pigeons"):
        assert c.get(path, headers=outsider).status_code == 403
        listed = c.get(path, headers=admin)
        assert listed.status_code == 200, listed.text
        assert all("password_hash" not in row for row in listed.json())
    assert uid in [row["id"] for row in c.get("/participants", headers=admin).json()]
    edit_user = {"full_name": "Updated Member", "phone": "+639000000001"}
    assert c.put(f"/participants/{uid}", headers=outsider, json=edit_user).status_code == 403
    assert c.put(f"/participants/{uid}", headers=admin, json=edit_user).status_code == 200
    loft = c.post("/lofts", headers=admin, json={"user_id": uid, "name": "New Loft",
                  "latitude": 9.7, "longitude": 125.4})
    assert loft.status_code == 201, loft.text
    loft_id = loft.json()["id"]
    pigeon_payload = {"loft_id": loft_id, "official_ring_number": f"TEST-{uuid4()}"}
    assert c.post("/pigeons", headers=admin, json=pigeon_payload).status_code == 422
    assert c.post(f"/lofts/{loft_id}/verify", headers=outsider).status_code == 403
    assert c.post(f"/lofts/{loft_id}/verify", headers=admin).status_code == 200
    assert c.post("/pigeons", headers=outsider, json=pigeon_payload).status_code == 403
    pigeon = c.post("/pigeons", headers=admin, json=pigeon_payload)
    assert pigeon.status_code == 201, pigeon.text
    pid = pigeon.json()["id"]
    pigeon_edit = {"name": "Test Bird", "status": "active"}
    assert c.put(f"/pigeons/{pid}", headers=outsider, json=pigeon_edit).status_code == 403
    assert c.put(f"/pigeons/{pid}", headers=admin, json=pigeon_edit).status_code == 200
    loft_edit = {"name": "Moved Loft", "latitude": 9.6, "longitude": 125.4}
    assert c.put(f"/lofts/{loft_id}", headers=outsider, json=loft_edit).status_code == 403
    changed = c.put(f"/lofts/{loft_id}", headers=admin, json=loft_edit)
    assert changed.status_code == 200, changed.text
    assert changed.json()["verified"] is False
    assert c.post(f"/lofts/{loft_id}/verify", headers=admin).status_code == 200
    race = make_race(s)
    register(s, race, s["pigeon_guest"], "QR")
    busy_loft = {"name": "Busy Loft", "latitude": 9.5, "longitude": 125.5}
    assert c.put(f"/lofts/{s['loft_guest']}", headers=admin, json=busy_loft).status_code == 409
    assert c.put(f"/pigeons/{s['pigeon_guest']}", headers=admin,
                 json={"name": "Busy Bird", "status": "retired"}).status_code == 409
    assert c.post(f"/devices/{s['device']}/provision", headers=outsider).status_code == 403
    assert c.post(f"/devices/{s['device']}/provision", headers=admin).status_code == 200
    link = {"page_id": "test-page", "sender_psid": str(uuid4()), "user_id": str(s["guest"])}
    assert c.post("/clocking/messenger/links", headers=outsider, json=link).status_code == 403
    assert c.post("/clocking/messenger/links", headers=admin, json=link).status_code == 201
    issued = c.post("/clocking/qr/tokens", headers=admin, json={"entry_id":
        c.get(f"/races/{race}/entries", headers=admin).json()[0]["id"]})
    assert issued.status_code == 201
    assert c.post(f"/races/{race}/activate", headers=admin).status_code == 200
    with s["engine"].begin() as db:
        db.execute(text("DELETE FROM club_memberships WHERE club_id=:club AND user_id=:user"),
                   {"club": club, "user": s["guest"]})
    scan = c.post("/clocking/qr/scans", headers=s["headers"](s["guest"]), json={
        "entry_id": issued.json()["entry_id"], "token": issued.json()["token"],
        "idempotency_key": str(uuid4())})
    assert scan.status_code == 403


def test_complete_club_guest_race_with_physical_review(scenario):
    """API workflow on disposable data; finalization deliberately fails closed."""
    s = scenario
    c = s["client"]
    admin = s["headers"](s["admin"])
    created = c.post("/clubs", headers=admin, json={"name": "Full Workflow Club"})
    assert created.status_code == 201, created.text
    club = created.json()["id"]
    birds = []
    for index in range(2):
        user = c.post("/participants", headers=admin, json={
            "club_id": club, "full_name": f"Workflow Guest {index}",
            "email": f"{uuid4()}@example.test", "password": "workflow-test-password",
            "role": "guest"})
        assert user.status_code == 201, user.text
        uid = UUID(user.json()["id"])
        s["extra_user_ids"].append(uid)
        loft = c.post("/lofts", headers=admin, json={"user_id": str(uid),
            "name": f"Workflow Loft {index}", "latitude": 9.8 - index * .1,
            "longitude": 125.5})
        assert loft.status_code == 201, loft.text
        loft_id = loft.json()["id"]
        ring = f"WORKFLOW-{uuid4()}"
        bird_payload = {"loft_id": loft_id, "official_ring_number": ring}
        assert c.post("/pigeons", headers=admin, json=bird_payload).status_code == 422
        assert c.post(f"/lofts/{loft_id}/verify", headers=admin).status_code == 200
        bird = c.post("/pigeons", headers=admin, json=bird_payload)
        assert bird.status_code == 201, bird.text
        birds.append((uid, bird.json()["id"], ring))
    race_response = c.post("/races", headers=admin, json={"club_id": club,
        "name": "Complete Guest Workflow", "release_latitude": 10,
        "release_longitude": 125.6, "minimum_speed_mpm": 0})
    assert race_response.status_code == 201, race_response.text
    race = race_response.json()["id"]
    assert c.post(f"/races/{race}/open", headers=admin).status_code == 200
    entries = [register(s, race, bird, "QR") for _, bird, _ in birds]
    tokens = []
    for entry in entries:
        issued = c.post("/clocking/qr/tokens", headers=admin, json={"entry_id": entry})
        assert issued.status_code == 201, issued.text
        tokens.append(issued.json()["token"])
    assert c.post(f"/races/{race}/activate", headers=admin).status_code == 200
    # Only the disposable fixture is backdated to avoid an hour-long test.
    with s["engine"].begin() as db:
        db.execute(text("UPDATE races SET actual_release_at=now()-interval '1 hour' WHERE id=:id"),
                   {"id": race})
    events = []
    for (uid, _, _), entry, token in zip(birds, entries, tokens):
        arrival = c.post("/clocking/qr/scans", headers=s["headers"](uid), json={
            "entry_id": entry, "token": token, "idempotency_key": str(uuid4())})
        assert arrival.status_code == 202, arrival.text
        events.append(arrival.json()["event_id"])
    preview_url = f"/races/{race}/leaderboard-preview"
    assert c.get(preview_url, headers=admin).json()["entries"] == []
    for event in events:
        assert c.post(f"/clocking/events/{event}/review", headers=admin, json={
            "decision": "approve", "reason": "Workflow evidence reviewed"}).status_code == 200
    provisional = c.get(preview_url, headers=admin)
    assert provisional.status_code == 200, provisional.text
    rows = provisional.json()["entries"]
    assert len(rows) == 2
    assert [row["rank"] for row in rows] == [1, 2]
    assert rows[0]["speed_mpm"] > rows[1]["speed_mpm"]
    assert all(row["physical_verification"] == "not_recorded" for row in rows)
    for index, (event, (_, _, ring)) in enumerate(zip(events, birds)):
        result = c.post(f"/clocking/events/{event}/guest-verification", headers=admin, json={
            "decision": "confirmed" if index == 0 else "rejected",
            "ring_number_seen": ring, "evidence_note": "Physical inspection recorded by test official"})
        assert result.status_code == 201, result.text
    reviewed = c.get(preview_url, headers=admin).json()
    assert reviewed["official"] is False
    assert len(reviewed["entries"]) == 1
    row = reviewed["entries"][0]
    assert row["event_id"] == events[0]
    assert row["rank"] == 1
    assert row["physical_verification"] == "confirmed"
    assert row["physically_verified_at"] is not None
    assert row["verification_status"] == "provisional"
    assert row["speed_mpm"] == pytest.approx(row["distance_meters"] /
        (row["flight_duration_seconds"] / 60), abs=.00001)
    assert c.post(f"/races/{race}/close", headers=admin).status_code == 200
    assert c.post(f"/races/{race}/finalize", headers=admin).status_code == 409
    with s["engine"].connect() as db:
        assert db.execute(text("""SELECT count(*) FROM race_results rr JOIN race_entries e
            ON e.id=rr.entry_id WHERE e.race_id=:race"""), {"race": race}).scalar_one() == 0


def make_race(s):
    c=s["client"]
    headers=s["headers"](s["admin"])
    race=c.post("/races",headers=headers,json={
        "name":"Postgres Integration Race","release_latitude":10.0,
        "release_longitude":125.6})
    assert race.status_code==201, race.text
    race_id=race.json()["id"]
    opened=c.post(f"/races/{race_id}/open",headers=headers)
    assert opened.status_code==200, opened.text
    return race_id

def register(s,race_id,pigeon,method):
    r=s["client"].post(f"/races/{race_id}/entries",
        headers=s["headers"](s["admin"]),
        json={"pigeon_id":str(pigeon),"expected_method":method})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_race_registration_and_duplicate(scenario):
    s=scenario
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    again=s["client"].post(f"/races/{race}/entries",
        headers=s["headers"](s["admin"]),
        json={"pigeon_id":str(s["pigeon_guest"]),"expected_method":"QR"})
    assert again.status_code==409
    listed=s["client"].get(f"/races/{race}/entries",headers=s["headers"](s["admin"]))
    assert listed.status_code==200
    assert any(row["id"]==entry for row in listed.json())

def test_qr_ownership_replay_revocation_and_review(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    token1=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert token1.status_code==201,token1.text
    token2=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert token2.status_code==201,token2.text
    activated=c.post(f"/races/{race}/activate",headers=admin)
    assert activated.status_code==200,activated.text
    key=str(uuid4())
    payload={"entry_id":entry,"token":token2.json()["token"],"idempotency_key":key}
    stolen=c.post("/clocking/qr/scans",headers=s["headers"](s["other"]),json=payload)
    assert stolen.status_code==403
    expired=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),
        json={**payload,"token":token1.json()["token"]})
    assert expired.status_code==401
    first=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),json=payload)
    assert first.status_code==202,first.text
    second=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),json=payload)
    assert second.status_code==202,second.text
    assert second.json()["event_id"]==first.json()["event_id"]
    assert second.json()["duplicate_request"] is True
    review=c.post(f"/clocking/events/{first.json()['event_id']}/review",
        headers=admin,json={"decision":"reject","reason":"Unverifiable guest submission"})
    assert review.status_code==200,review.text
    assert review.json()["event_status"]=="invalid"
    replay_after_rejection=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),json=payload)
    assert replay_after_rejection.status_code==202,replay_after_rejection.text
    assert replay_after_rejection.json()["status"]=="invalid"
    repeated=c.post(f"/clocking/events/{first.json()['event_id']}/review",
        headers=admin,json={"decision":"approve","reason":"Second review attempt"})
    assert repeated.status_code==409

def test_rfid_simulator_idempotency_and_wrong_device(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    register(s,race,s["pigeon_member"],"RFID")
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    key=str(uuid4())
    payload={"race_id":race,"device_id":str(s["device"]),
             "rfid_uid":f"RFID-{s['ring']}","idempotency_key":key}
    invalid=c.post("/clocking/rfid/simulate",headers=admin,
                   json={**payload,"device_id":str(uuid4())})
    assert invalid.status_code==404
    first=c.post("/clocking/rfid/simulate",headers=admin,json=payload)
    assert first.status_code==202,first.text
    repeated=c.post("/clocking/rfid/simulate",headers=admin,json=payload)
    assert repeated.status_code==202,repeated.text
    assert repeated.json()["event_id"]==first.json()["event_id"]
    events=c.get("/clocking/events",headers=admin,params={"race_id":race})
    assert events.status_code==200
    assert len(events.json())==1


def test_approved_guest_arrival_appears_in_provisional_leaderboard(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    issued=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert issued.status_code==201,issued.text
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    arrival=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),json={
        "entry_id":entry,"token":issued.json()["token"],"idempotency_key":str(uuid4())
    })
    assert arrival.status_code==202,arrival.text
    before=c.get(f"/races/{race}/leaderboard-preview",headers=admin)
    assert before.status_code==200,before.text
    assert before.json()["entries"]==[]
    reviewed=c.post(f"/clocking/events/{arrival.json()['event_id']}/review",
        headers=admin,json={"decision":"approve","reason":"Verified supporting arrival evidence"})
    assert reviewed.status_code==200,reviewed.text
    preview=c.get(f"/races/{race}/leaderboard-preview",headers=admin)
    assert preview.status_code==200,preview.text
    assert preview.json()["official"] is False
    assert len(preview.json()["entries"])==1
    assert preview.json()["entries"][0]["entry_id"]==entry
    assert preview.json()["entries"][0]["clocking_method"]=="QR"
    assert preview.json()["entries"][0]["verification_status"]=="provisional"


def test_close_and_finalization_fail_closed(scenario):
    s=scenario
    client=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    # No race may be finalized while registration remains open.
    premature=client.post(f"/races/{race}/finalize",headers=admin)
    assert premature.status_code==409
    assert client.post(f"/races/{race}/activate",headers=admin).status_code==200
    closed=client.post(f"/races/{race}/close",headers=admin)
    assert closed.status_code==200,closed.text
    assert closed.json()["official"] is False
    assert client.post(f"/races/{race}/close",headers=admin).status_code==409
    blocked=client.post(f"/races/{race}/finalize",headers=admin)
    assert blocked.status_code==409
    assert "disabled" in blocked.json()["detail"]
    with s["engine"].connect() as db:
        assert db.execute(text("SELECT status FROM races WHERE id=:id"),
                          {"id":race}).scalar_one()=="closed"
        assert db.execute(text("SELECT count(*) FROM race_results")).scalar_one()==0


def test_official_guest_verification_requires_matching_ring_and_is_one_time(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    issued=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert issued.status_code==201,issued.text
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    scan=c.post("/clocking/qr/scans",headers=s["headers"](s["guest"]),json={
        "entry_id":entry,"token":issued.json()["token"],"idempotency_key":str(uuid4())
    })
    assert scan.status_code==202,scan.text
    url=f"/clocking/events/{scan.json()['event_id']}/guest-verification"
    payload={"decision":"confirmed","ring_number_seen":"WRONG",
             "evidence_note":"Observed pigeon and ring in person at loft"}
    assert c.post(url,headers=s["headers"](s["guest"]),json=payload).status_code==403
    assert c.post(url,headers=admin,json=payload).status_code==422
    payload["ring_number_seen"]=f"TEST-{s['pigeon_guest']}"
    verified=c.post(url,headers=admin,json=payload)
    assert verified.status_code==201,verified.text
    assert verified.json()["ring_matched"] is True
    assert verified.json()["official_result_created"] is False
    assert c.post(url,headers=admin,json=payload).status_code==409
    assert c.post(f"/races/{race}/close",headers=admin).status_code==200
    assert c.post(f"/races/{race}/finalize",headers=admin).status_code==409


def test_esp32_gateway_auth_replay_and_untrusted_offline_clock(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    register(s,race,s["pigeon_member"],"RFID")
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    endpoint=f"/devices/{s['device']}/arrivals"
    payload={"message_id":str(uuid4()),"race_id":race,
             "ring_uid":f"RFID-{s['ring']}","offline_buffered":True,
             "device_recorded_at":"2026-01-01T00:00:00Z"}
    assert c.post(endpoint,json=payload).status_code==401
    provision=c.post(f"/devices/{s['device']}/provision",headers=admin)
    assert provision.status_code==200,provision.text
    token=provision.json()["device_token"]
    assert c.post(endpoint,headers={"X-Device-Token":"invalid"},json=payload).status_code==401
    first=c.post(endpoint,headers={"X-Device-Token":token},json=payload)
    assert first.status_code==202,first.text
    assert first.json()["official_result_created"] is False
    again=c.post(endpoint,headers={"X-Device-Token":token},json=payload)
    assert again.status_code==202,again.text
    assert again.json()["duplicate_request"] is True
    assert again.json()["event_id"]==first.json()["event_id"]
    assert c.post(endpoint,headers={"X-Device-Token":token},
                  json={**payload,"ring_uid":"different"}).status_code==409
    with s["engine"].connect() as db:
        row=db.execute(text("SELECT recorded_at,metadata FROM clocking_events WHERE id=:id"),
                       {"id":first.json()["event_id"]}).mappings().one()
        assert row["recorded_at"].year != 2026 or row["recorded_at"].month != 1
        assert row["metadata"]["timestamp_trusted"] is False
    rotated=c.post(f"/devices/{s['device']}/provision",headers=admin)
    assert rotated.status_code==200
    assert c.post(endpoint,headers={"X-Device-Token":token},
                  json={**payload,"message_id":str(uuid4())}).status_code==401


def test_web_mobile_arrival_provenance_and_replay(scenario):
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    issued=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert issued.status_code==201,issued.text
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    payload={"entry_id":entry,"token":issued.json()["token"],
             "idempotency_key":str(uuid4()),"channel":"web"}
    url="/clocking/manual/arrivals"
    assert c.post(url,json=payload).status_code==401
    assert c.post(url,headers=s["headers"](s["other"]),json=payload).status_code==403
    first=c.post(url,headers=s["headers"](s["guest"]),json=payload)
    assert first.status_code==202,first.text
    assert first.json()["official_result_created"] is False
    repeated=c.post(url,headers=s["headers"](s["guest"]),json=payload)
    assert repeated.status_code==202,repeated.text
    assert repeated.json()["duplicate_request"] is True
    assert repeated.json()["event_id"]==first.json()["event_id"]
    changed=c.post(url,headers=s["headers"](s["guest"]),json={**payload,"channel":"mobile"})
    assert changed.status_code==409,changed.text
    source=c.get(f"/clocking/events/{first.json()['event_id']}/source",headers=admin)
    assert source.status_code==200,source.text
    assert source.json()["channel"]=="web"
    assert source.json()["clock_integrity_verified"] is False
    assert c.get(f"/clocking/events/{first.json()['event_id']}/source",
                 headers=s["headers"](s["guest"])).status_code==403


def test_signed_sms_webhook_auth_sender_replay_and_provenance(scenario, monkeypatch):
    import hashlib
    import hmac
    import json
    s=scenario
    c=s["client"]
    admin=s["headers"](s["admin"])
    race=make_race(s)
    entry=register(s,race,s["pigeon_guest"],"QR")
    issued=c.post("/clocking/qr/tokens",headers=admin,json={"entry_id":entry})
    assert issued.status_code==201,issued.text
    assert c.post(f"/races/{race}/activate",headers=admin).status_code==200
    sender="+639171234567"
    with s["engine"].begin() as db:
        db.execute(text("UPDATE users SET phone=:phone WHERE id=:id"),
                   {"phone":sender,"id":s["guest"]})
    secret="sms-integration-test-secret-"+"x"*48
    monkeypatch.setenv("SMS_WEBHOOK_SECRET",secret)
    payload={"provider":"testgateway","message_id":str(uuid4()),
             "sender":sender,"entry_id":entry,"token":issued.json()["token"]}
    raw=json.dumps(payload,separators=(",",":")).encode()
    sig=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    url="/clocking/sms/webhook"
    assert c.post(url,content=raw,headers={"Content-Type":"application/json"}).status_code==401
    assert c.post(url,content=raw,headers={"X-Dove-SMS-Signature":"bad"}).status_code==401
    first=c.post(url,content=raw,headers={"X-Dove-SMS-Signature":sig,
                                          "Content-Type":"application/json"})
    assert first.status_code==202,first.text
    assert first.json()["official_result_created"] is False
    repeated=c.post(url,content=raw,headers={"X-Dove-SMS-Signature":sig})
    assert repeated.status_code==202,repeated.text
    assert repeated.json()["duplicate_request"] is True
    assert repeated.json()["event_id"]==first.json()["event_id"]
    source=c.get(f"/clocking/events/{first.json()['event_id']}/source",headers=admin)
    assert source.status_code==200,source.text
    assert source.json()["channel"]=="sms"
    assert source.json()["clock_integrity_verified"] is False
    wrong={**payload,"sender":"+639170000000","message_id":str(uuid4())}
    wrong_raw=json.dumps(wrong).encode()
    wrong_sig=hmac.new(secret.encode(),wrong_raw,hashlib.sha256).hexdigest()
    denied=c.post(url,content=wrong_raw,headers={"X-Dove-SMS-Signature":wrong_sig})
    assert denied.status_code==403,denied.text


def test_messenger_verification_and_unsigned_rejection(scenario, monkeypatch):
    s=scenario
    c=s["client"]
    monkeypatch.setenv("META_VERIFY_TOKEN","verification-test-value-"+"x"*40)
    monkeypatch.setenv("META_APP_SECRET","application-test-value-"+"x"*40)
    monkeypatch.setenv("META_PAGE_ID","test-page")
    url="/clocking/messenger/webhook"
    assert c.get(url,params={"hub.mode":"subscribe","hub.verify_token":"incorrect",
                             "hub.challenge":"challenge"}).status_code==403
    valid=c.get(url,params={"hub.mode":"subscribe",
        "hub.verify_token":"verification-test-value-"+"x"*40,
        "hub.challenge":"challenge"})
    assert valid.status_code==200
    assert valid.text=="challenge"
    assert c.post(url,json={"object":"page","entry":[]}).status_code==401


def test_messenger_signed_arrival_replay_and_provenance(scenario, monkeypatch):
    import hashlib
    import hmac
    import json
    s = scenario
    client = s["client"]
    admin = s["headers"](s["admin"])
    monkeypatch.setenv("META_APP_SECRET", "integration-secret-" + "x" * 40)
    monkeypatch.setenv("META_PAGE_ID", "test-page")
    race = make_race(s)
    entry = register(s, race, s["pigeon_guest"], "QR")
    token_response = client.post("/clocking/qr/tokens", headers=admin,
                                 json={"entry_id": entry})
    assert token_response.status_code == 201
    assert client.post(f"/races/{race}/activate", headers=admin).status_code == 200
    link = client.post("/clocking/messenger/links", headers=admin,
                       json={"page_id": "test-page", "sender_psid": "test-psid",
                             "user_id": str(s["guest"])})
    assert link.status_code == 201, link.text
    message = {"object": "page", "entry": [{"id": "test-page", "messaging": [{
        "sender": {"id": "test-psid"},
        "message": {"mid": str(uuid4()),
                    "text": "CLOCK " + str(entry) + " " + token_response.json()["token"]}
    }]}]}
    raw = json.dumps(message).encode()
    signature = "sha256=" + hmac.new(
        ("integration-secret-" + "x" * 40).encode(), raw, hashlib.sha256
    ).hexdigest()
    headers = {"X-Hub-Signature-256": signature}
    first = client.post("/clocking/messenger/webhook", content=raw, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["processed"] == 1
    second = client.post("/clocking/messenger/webhook", content=raw, headers=headers)
    assert second.status_code == 200, second.text
    with s["engine"].connect() as db:
        sources = db.execute(text("""
            SELECT src.channel, src.clock_integrity_verified
            FROM clocking_event_sources src
            JOIN clocking_events ev ON ev.id = src.event_id
            WHERE ev.entry_id = :entry
        """), {"entry": entry}).mappings().all()
    assert len(sources) == 1
    assert sources[0]["channel"] == "messenger"
    assert sources[0]["clock_integrity_verified"] is False


def test_messenger_rejects_unlinked_sender_and_wrong_page(scenario, monkeypatch):
    import hashlib
    import hmac
    import json
    s = scenario
    client = s["client"]
    monkeypatch.setenv("META_APP_SECRET", "integration-secret-" + "y" * 40)
    monkeypatch.setenv("META_PAGE_ID", "allowed-page")
    race = make_race(s)
    entry = register(s, race, s["pigeon_guest"], "QR")
    issued = client.post("/clocking/qr/tokens",
                         headers=s["headers"](s["admin"]), json={"entry_id": entry})
    assert issued.status_code == 201
    assert client.post(f"/races/{race}/activate",
                       headers=s["headers"](s["admin"])).status_code == 200
    for page in ("allowed-page", "wrong-page"):
        message = {"object": "page", "entry": [{"id": page, "messaging": [{
            "sender": {"id": "unlinked-psid"},
            "message": {"mid": str(uuid4()),
                        "text": "CLOCK " + str(entry) + " " + issued.json()["token"]}
        }]}]}
        raw = json.dumps(message).encode()
        signature = "sha256=" + hmac.new(
            ("integration-secret-" + "y" * 40).encode(), raw, hashlib.sha256
        ).hexdigest()
        response = client.post("/clocking/messenger/webhook", content=raw,
                               headers={"X-Hub-Signature-256": signature})
        assert response.status_code == 200, response.text
        assert response.json()["processed"] == 0
    with s["engine"].connect() as db:
        count = db.execute(text("""
            SELECT count(*) FROM clocking_events WHERE entry_id = :entry
        """), {"entry": entry}).scalar_one()
    assert count == 0
