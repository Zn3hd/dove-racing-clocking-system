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
        db.execute(text("DELETE FROM messenger_account_links WHERE user_id = ANY(:ids)"), {"ids":ids})
        db.execute(text("""DELETE FROM guest_arrival_verifications WHERE verified_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("DELETE FROM device_gateway_messages WHERE device_id=:device"), {"device":device})
        db.execute(text("DELETE FROM device_gateway_credentials WHERE device_id=:device"), {"device":device})
        db.execute(text("""DELETE FROM clocking_reviews WHERE reviewed_by = ANY(:ids)"""), {"ids":ids})
        db.execute(text("""DELETE FROM clocking_event_sources WHERE event_id IN (SELECT id FROM clocking_events WHERE submitted_by = ANY(:ids) OR device_id=:device)"""), {"ids":ids,"device":device})
        db.execute(text("""DELETE FROM clocking_events WHERE submitted_by = ANY(:ids) OR device_id=:device"""), {"ids":ids,"device":device})
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
