"""Force credential/race transitions to win before blocked device requests resume."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.routers.device_gateway import digest
from test_postgres_e2e import scenario, make_race, register

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Disposable PostgreSQL required')


def wait_device_lock(engine):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        with engine.connect() as db:
            if db.execute(text("""SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()
                AND wait_event_type='Lock' AND query LIKE '%devices%'""")).scalar_one(): return
        time.sleep(.02)
    pytest.fail('Device request did not reach expected lock wait')


@pytest.mark.parametrize('request_kind',['heartbeat','arrival'])
@pytest.mark.parametrize('transition',['rotate','revoke'])
def test_waiting_device_request_observes_latest_credential(scenario,request_kind,transition):
    s=scenario;c=s['client'];admin=s['headers'](s['admin'])
    race=make_race(s);register(s,race,s['pigeon_member'],'RFID')
    assert c.post(f'/races/{race}/activate',headers=admin).status_code==200
    token=c.post(f"/devices/{s['device']}/provision",headers=admin).json()['device_token']
    path=f"/devices/{s['device']}/"+('heartbeat' if request_kind=='heartbeat' else 'arrivals')
    body=({'pending_count':0,'rejected_count':0} if request_kind=='heartbeat' else
          {'message_id':str(uuid4()),'race_id':race,'ring_uid':f"RFID-{s['ring']}"})
    def send():
        with TestClient(app) as client:return client.post(path,headers={'X-Device-Token':token},json=body)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with s['engine'].connect() as db:
            txn=db.begin()
            try:
                db.execute(text('SELECT id FROM devices WHERE id=:id FOR UPDATE'),{'id':s['device']})
                future=pool.submit(send);wait_device_lock(s['engine'])
                if transition=='rotate':
                    db.execute(text('UPDATE device_gateway_credentials SET secret_hash=:hash WHERE device_id=:id'),
                               {'hash':digest('replacement-credential'),'id':s['device']})
                else:
                    db.execute(text('UPDATE device_gateway_credentials SET revoked_at=clock_timestamp() WHERE device_id=:id'),{'id':s['device']})
                db.execute(text('UPDATE devices SET heartbeat_at=NULL WHERE id=:id'),{'id':s['device']})
                txn.commit()
            finally:
                if txn.is_active:txn.rollback()
        result=future.result(timeout=10)
    assert result.status_code==401,result.text


def test_member_api_responses_prevent_caching(scenario):
    s=scenario;headers=s['headers'](s['member'])
    response=s['client'].get('/member/overview',headers=headers)
    assert response.status_code==200
    assert response.headers.get('cache-control')=='no-store'


def test_race_close_wins_before_waiting_gateway_arrival(scenario):
    s=scenario;c=s['client'];admin=s['headers'](s['admin'])
    race=make_race(s);register(s,race,s['pigeon_member'],'RFID')
    assert c.post(f'/races/{race}/activate',headers=admin).status_code==200
    token=c.post(f"/devices/{s['device']}/provision",headers=admin).json()['device_token']
    def send():
        with TestClient(app) as client:
            return client.post(f"/devices/{s['device']}/arrivals",headers={'X-Device-Token':token},
                json={'race_id':race,'message_id':str(uuid4()),'ring_uid':f"RFID-{s['ring']}"})
    with ThreadPoolExecutor(max_workers=1) as pool:
        with s['engine'].connect() as db:
            txn=db.begin()
            try:
                db.execute(text('SELECT id FROM races WHERE id=:id FOR UPDATE'),{'id':race})
                future=pool.submit(send)
                deadline=time.monotonic()+5
                waiting=False
                while time.monotonic()<deadline and not future.done():
                    with s['engine'].connect() as observer:
                        waiting=bool(observer.execute(text("""SELECT count(*) FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                            AND query LIKE '%races%' AND query LIKE '%FOR SHARE%'""")).scalar_one())
                    if waiting:break
                    time.sleep(.02)
                assert waiting,'Gateway accepted a new arrival without serializing against race close'
                db.execute(text("UPDATE races SET status='closed' WHERE id=:id"),{'id':race})
                txn.commit()
            finally:
                if txn.is_active:txn.rollback()
        assert future.result(timeout=10).status_code==409
