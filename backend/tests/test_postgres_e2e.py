"""End-to-end API tests against a real disposable PostgreSQL database.

CI provisions PostgreSQL and applies the actual schema before this suite.
Tests use unique UUIDs and remove their own rows in FK-safe order.
"""
import os
from uuid import uuid4
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
    yield data
    # Remove all test-created rows, including audited events, before accounts.
    with engine.begin() as db:
        ids = [admin,guest,other,member]
        db.execute(text("DELETE FROM audit_logs WHERE actor_id = ANY(:ids)"), {"ids":ids})
        db.execute(text("""DELETE FROM guest_arrival_verifications WHERE verified_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("DELETE FROM device_gateway_messages WHERE device_id=:device"), {"device":device})
        db.execute(text("DELETE FROM device_gateway_credentials WHERE device_id=:device"), {"device":device})
        db.execute(text("""DELETE FROM clocking_reviews WHERE reviewed_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("""DELETE FROM clocking_events WHERE submitted_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("""DELETE FROM qr_tokens WHERE pigeon_id = ANY(:ids)"""),
                   {"ids":[pigeon_guest,pigeon_other,pigeon_member]})
        db.execute(text("""DELETE FROM race_entries WHERE pigeon_id = ANY(:ids)"""),
                   {"ids":[pigeon_guest,pigeon_other,pigeon_member]})
        db.execute(text("DELETE FROM races WHERE created_by = :id"), {"id":admin})
        db.execute(text("DELETE FROM devices WHERE id=:id"), {"id":device})
        db.execute(text("DELETE FROM rfid_rings WHERE id=:id"), {"id":ring})
        db.execute(text("DELETE FROM pigeons WHERE id = ANY(:ids)"),
                   {"ids":[pigeon_guest,pigeon_other,pigeon_member]})
        db.execute(text("DELETE FROM lofts WHERE id = ANY(:ids)"),
                   {"ids":[loft_guest,loft_other,loft_member]})
        db.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids":ids})
    engine.dispose()
    database._engine = None
    database._factory = None

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
