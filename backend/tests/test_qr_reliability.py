"""Real transaction schedules, recovery boundaries, and shared request budgets."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.main import app
from app.rate_limits import consume, identity_digest
from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def setup_scan(s, extra=None):
    race = make_race(s)
    entries = [register(s, race, s['pigeon_guest'], 'QR')]
    if extra:
        entries.append(register(s, race, extra, 'QR'))
    admin = s['headers'](s['admin'])
    labels = [s['client'].post('/clocking/qr/tokens', headers=admin, json={'entry_id': entry}).json() for entry in entries]
    assert s['client'].post(f'/races/{race}/activate', headers=admin).status_code == 200
    return race, [{'entry_id': entry, 'token': label['token'], 'idempotency_key': str(uuid4()),
                   'capture_source':'usb_qr'} for entry, label in zip(entries, labels)], labels


def request(s, path, body, actor='guest'):
    with TestClient(app) as client:
        return client.post(path, headers=s['headers'](s[actor]), json=body)


def wait_for_locks(engine, count=1):
    deadline = time.monotonic()+10
    while time.monotonic()<deadline:
        with engine.connect() as connection:
            waiting = connection.execute(text("""SELECT count(*) FROM pg_stat_activity
                WHERE datname=current_database() AND wait_event_type='Lock'
                AND query LIKE '%race%' AND query LIKE '%FOR %'""")).scalar_one()
        if waiting>=count:
            return
        time.sleep(.02)
    pytest.fail('Expected API transaction did not reach its lock wait')


def test_identical_simultaneous_qr_submissions_create_one_event(scenario):
    s=scenario
    _, payloads, _ = setup_scan(s)
    gate=Barrier(8)
    def send(_):
        gate.wait(timeout=10)
        return request(s, '/clocking/qr/scans', payloads[0])
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses=list(pool.map(send, range(8)))
    assert {r.status_code for r in responses} == {202}
    assert len({r.json()['event_id'] for r in responses}) == 1
    assert sum(not r.json()['duplicate_request'] for r in responses) == 1


def test_cross_entry_simultaneous_key_collision_is_409(scenario):
    s=scenario
    pigeon=s['client'].post('/pigeons', headers=s['headers'](s['admin']), json={
        'loft_id':str(s['loft_guest']), 'official_ring_number':f'CONCURRENT-{uuid4()}'}).json()['id']
    _, payloads, _ = setup_scan(s, pigeon)
    payloads[1]['idempotency_key']=payloads[0]['idempotency_key']
    gate=Barrier(2)
    def send(payload):
        gate.wait(timeout=10)
        return request(s, '/clocking/qr/scans', payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(send, payloads))
    assert sorted(r.status_code for r in responses) == [202,409]


@pytest.mark.parametrize('operation', ['scan','issue'])
def test_close_wins_against_waiting_qr_transaction(scenario, operation):
    s=scenario
    race, payloads, _ = setup_scan(s)
    pool=ThreadPoolExecutor(max_workers=1)
    try:
        with s['engine'].begin() as connection:
            connection.execute(text('SELECT id FROM races WHERE id=:id FOR UPDATE'), {'id':race})
            future=pool.submit(request, s, '/clocking/qr/scans' if operation=='scan' else '/clocking/qr/tokens',
                payloads[0] if operation=='scan' else {'entry_id':payloads[0]['entry_id']},
                'guest' if operation=='scan' else 'admin')
            wait_for_locks(s['engine'])
            connection.execute(text("UPDATE races SET status='closed' WHERE id=:id"), {'id':race})
        assert future.result(timeout=15).status_code == 409
    finally:
        pool.shutdown(wait=True)


def test_token_rotation_wins_against_waiting_scan(scenario):
    s=scenario
    _, payloads, _ = setup_scan(s)
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        with s['engine'].begin() as connection:
            connection.execute(text('SELECT id FROM race_entries WHERE id=:id FOR UPDATE'), {'id':payloads[0]['entry_id']})
            rotate=pool.submit(request,s,'/clocking/qr/tokens',{'entry_id':payloads[0]['entry_id']},'admin')
            wait_for_locks(s['engine'])
            scan=pool.submit(request,s,'/clocking/qr/scans',payloads[0])
            wait_for_locks(s['engine'],2)
        assert rotate.result(timeout=15).status_code == 201
        assert scan.result(timeout=15).status_code == 401
    finally:
        pool.shutdown(wait=True)


def test_expiry_is_checked_after_waiting_not_at_transaction_start(scenario):
    s=scenario
    _, payloads, labels = setup_scan(s)
    pool=ThreadPoolExecutor(max_workers=1)
    try:
        with s['engine'].begin() as connection:
            connection.execute(text('SELECT id FROM race_entries WHERE id=:id FOR UPDATE'), {'id':payloads[0]['entry_id']})
            scan=pool.submit(request,s,'/clocking/qr/scans',payloads[0])
            wait_for_locks(s['engine'])
            connection.execute(text("UPDATE qr_tokens SET expires_at=clock_timestamp()+interval '100 milliseconds' WHERE id=:id"), {'id':labels[0]['token_id']})
            time.sleep(.2)
        assert scan.result(timeout=15).status_code == 401
    finally:
        pool.shutdown(wait=True)


def test_receipt_and_exact_replay_survive_close_and_revocation(scenario):
    s=scenario
    race, payloads, labels=setup_scan(s)
    from datetime import datetime, timezone, timedelta
    payloads[0]['client_queued_at']=datetime.now(timezone.utc).isoformat()
    first=request(s,'/clocking/qr/scans',payloads[0])
    assert first.status_code==202
    assert request(s,f'/races/{race}/close',{},'admin').status_code==200
    assert request(s,f"/clocking/qr/tokens/{labels[0]['token_id']}/revoke",{},'admin').status_code==200
    replay=request(s,'/clocking/qr/scans',payloads[0])
    assert replay.status_code==202 and replay.json()['event_id']==first.json()['event_id']
    assert request(s,'/clocking/qr/scans',{**payloads[0],
        'client_queued_at':(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat()}).status_code==409
    path=f"/clocking/qr/receipts/{payloads[0]['idempotency_key']}"
    assert s['client'].get(path,headers=s['headers'](s['guest'])).json()['event_id']==first.json()['event_id']
    assert s['client'].get(path,headers=s['headers'](s['other'])).status_code==404
    assert request(s,'/clocking/qr/scans',{**payloads[0],'idempotency_key':str(uuid4())}).status_code==409


def test_scan_rate_limit_retains_original_retry_key(scenario, monkeypatch):
    s=scenario
    _, payloads, _=setup_scan(s)
    monkeypatch.setenv('QR_SCAN_ACCOUNT_LIMIT','2')
    assert request(s,'/clocking/qr/scans',payloads[0]).status_code==202
    assert request(s,'/clocking/qr/scans',payloads[0]).status_code==202
    blocked=request(s,'/clocking/qr/scans',payloads[0])
    assert blocked.status_code==429 and 1<=int(blocked.headers['Retry-After'])<=60
    identity=identity_digest(s['guest'])
    with s['engine'].begin() as connection:
        connection.execute(text("UPDATE request_rate_buckets SET bucket=bucket-1 WHERE scope='qr_scan_account' AND identity_hash=:identity"), {'identity':identity})
    assert request(s,'/clocking/qr/scans',payloads[0]).json()['duplicate_request'] is True


def test_shared_rate_budget_is_atomic(scenario):
    identity=str(uuid4())
    gate=Barrier(8)
    def take(_):
        gate.wait(timeout=10)
        try:
            consume('audit_budget',identity,3)
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(take,range(8)))
    assert results.count(200)==3 and results.count(429)==5


def test_login_and_issuance_budgets_are_enforced(scenario, monkeypatch):
    s=scenario
    monkeypatch.setenv('LOGIN_ACCOUNT_LIMIT','1')
    credentials={'email':f"{s['guest']}@example.test",'password':'integration-password-123'}
    assert s['client'].post('/auth/login',json=credentials).status_code==200
    blocked=s['client'].post('/auth/login',json=credentials)
    assert blocked.status_code==429 and 'Retry-After' in blocked.headers
    monkeypatch.setenv('QR_ISSUE_ACCOUNT_LIMIT','1')
    _, payloads, _=setup_scan(s)
    assert request(s,'/clocking/qr/tokens',{'entry_id':payloads[0]['entry_id']},'admin').status_code==429


def test_private_qr_image_and_history_do_not_expose_secret(scenario):
    import base64
    s=scenario
    race,payloads,_=setup_scan(s)
    response=request(s,'/clocking/qr/tokens',{'entry_id':payloads[0]['entry_id'],'include_image':True},'admin')
    assert response.status_code==201
    assert response.headers['Cache-Control']=='no-store'
    assert base64.b64decode(response.json()['qr_png_base64']).startswith(b'\x89PNG')
    history=s['client'].get(f'/clocking/qr/tokens/race/{race}',headers=s['headers'](s['admin']))
    assert history.status_code==200
    assert response.json()['token'] not in history.text
    assert 'token_hash' not in history.text and 'qr_payload' not in history.text
