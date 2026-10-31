import os
import pytest
from sqlalchemy import text
from test_postgres_e2e import scenario

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def setup(s):
    c=s['client']; admin=s['headers'](s['admin'])
    club=c.post('/clubs',headers=admin,json={'name':'Reader monitoring club'}).json()['id']
    assert c.post(f'/clubs/{club}/members',headers=admin,json={'user_id':str(s['member'])}).status_code==201
    token=c.post(f"/devices/{s['device']}/provision",headers=admin).json()['device_token']
    return c,admin,{'X-Device-Token':token}


def test_heartbeat_is_authenticated_isolated_and_never_an_arrival(scenario):
    s=scenario; c,admin,headers=setup(s); path=f"/devices/{s['device']}/heartbeat"
    body={'reader_state':'not_probed','pending_count':3,'rejected_count':1}
    assert c.post(path,json=body).status_code==401
    assert c.post(path,headers={'X-Device-Token':'wrong'},json=body).status_code==401
    result=c.post(path,headers=headers,json=body)
    assert result.status_code==200,result.text
    assert result.headers['cache-control']=='no-store'
    row=c.get('/devices',headers=admin).json()[0]
    assert row['gateway_status']=='recent' and row['reported_pending_count']==3
    assert row['reported_reader_state']=='not_probed' and row['last_seen_at'] is None
    assert 'secret_hash' not in row and 'device_token' not in row
    with s['engine'].begin() as db:
        assert db.execute(text('SELECT count(*) FROM clocking_events WHERE device_id=:id'),{'id':s['device']}).scalar_one()==0
        db.execute(text("UPDATE devices SET heartbeat_at=now()-interval '91 seconds' WHERE id=:id"),{'id':s['device']})
        db.execute(text("UPDATE users SET role_code='president' WHERE id=:id"),{'id':s['other']})
    assert c.get('/devices',headers=admin).json()[0]['gateway_status']=='stale'
    outsider=s['headers'](s['other'])
    assert c.get('/devices',headers=outsider).json()==[]
    assert c.post(f"/devices/{s['device']}/revoke",headers=outsider).status_code==403


def test_rotation_and_revocation_invalidate_monitoring_credentials(scenario):
    s=scenario; c,admin,old=setup(s); base=f"/devices/{s['device']}"
    body={'pending_count':0,'rejected_count':0}
    assert c.post(base+'/heartbeat',headers=old,json=body).status_code==200
    fresh=c.post(base+'/provision',headers=admin).json()['device_token']
    assert c.get('/devices',headers=admin).json()[0]['gateway_status']=='never_seen'
    assert c.post(base+'/heartbeat',headers=old,json=body).status_code==401
    headers={'X-Device-Token':fresh}
    assert c.post(base+'/heartbeat',headers=headers,json=body).status_code==200
    assert c.post(base+'/revoke',headers=admin).status_code==200
    assert c.post(base+'/heartbeat',headers=headers,json=body).status_code==401
    row=c.get('/devices',headers=admin).json()[0]
    assert row['gateway_status']=='revoked' and row['heartbeat_at'] is None


def test_heartbeat_limits_and_input_validation(scenario,monkeypatch):
    s=scenario;c,admin,headers=setup(s);path=f"/devices/{s['device']}/heartbeat"
    monkeypatch.setenv('DEVICE_HEARTBEAT_DEVICE_LIMIT','1')
    for body in ({'pending_count':-1,'rejected_count':0},{'pending_count':True,'rejected_count':0},
                 {'pending_count':0,'rejected_count':0,'reader_state':'connected'}):
        assert c.post(path,headers=headers,json=body).status_code==422
    body={'pending_count':0,'rejected_count':0}
    assert c.post(path,headers=headers,json=body).status_code==200
    limited=c.post(path,headers=headers,json=body)
    assert limited.status_code==429 and int(limited.headers['Retry-After'])>0
