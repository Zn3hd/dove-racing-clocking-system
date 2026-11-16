"""Owner-only one-use pairing, revocation and concurrent redemption."""
import os
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from app.main import app
from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def setup(s):
    admin = s['headers'](s['admin'])
    club = s['client'].post('/clubs', headers=admin, json={'name': 'Enrollment test club'})
    assert club.status_code == 201, club.text
    assert s['client'].post(f"/clubs/{club.json()['id']}/members", headers=admin,
                           json={'user_id': str(s['member'])}).status_code == 201
    race = make_race(s)
    register(s, race, s['pigeon_member'], 'RFID')
    assert s['client'].post(f'/races/{race}/activate', headers=s['headers'](s['admin'])).status_code == 200
    return race


def invite(s):
    response = s['client'].post(f"/devices/{s['device']}/enrollment", headers=s['headers'](s['admin']))
    assert response.status_code == 201, response.text
    return response.json()['enrollment_code']


def redeem(s, code, who='member'):
    return s['client'].post('/member/reader-enrollments/redeem',
        headers=s['headers'](s[who]), json={'code': code})


def test_owner_enrollment_rotates_credential_and_is_one_use(scenario):
    s = scenario
    setup(s)
    admin = s['headers'](s['admin'])
    old = s['client'].post(f"/devices/{s['device']}/provision", headers=admin).json()['device_token']
    code = invite(s)
    assert redeem(s, code, 'other').status_code == 403
    result = redeem(s, code)
    assert result.status_code == 200, result.text
    token = result.json()['device_token']
    assert token != old
    assert redeem(s, code).status_code == 404
    heartbeat = f"/devices/{s['device']}/heartbeat"
    for value, status in [(old, 401), (token, 200)]:
        assert s['client'].post(heartbeat, headers={'X-Device-Token': value},
            json={'pending_count': 0, 'rejected_count': 0}).status_code == status
    with s['engine'].connect() as db:
        row = db.execute(text('SELECT code_hash,consumed_at FROM reader_enrollments WHERE device_id=:id'),
                         {'id': s['device']}).mappings().one()
        assert code not in row['code_hash'] and row['consumed_at'] is not None
    assert code not in s['client'].get('/member/readers', headers=s['headers'](s['member'])).text


@pytest.mark.parametrize('transition', ['expire', 'reissue', 'revoke', 'rotate', 'membership', 'issuer'])
def test_invalidated_invitations_cannot_reenable_gateway(scenario, transition):
    s = scenario
    setup(s)
    code = invite(s)
    admin = s['headers'](s['admin'])
    if transition in ('expire', 'membership', 'issuer'):
        with s['engine'].begin() as db:
            if transition == 'expire':
                db.execute(text("UPDATE reader_enrollments SET expires_at=now()-interval '1 minute' WHERE device_id=:id"), {'id': s['device']})
            elif transition == 'membership':
                db.execute(text('DELETE FROM club_memberships WHERE user_id=:id'), {'id': s['member']})
            else:
                db.execute(text('UPDATE users SET status=\'inactive\' WHERE id=:id'), {'id': s['admin']})
    elif transition == 'reissue':
        invite(s)
    else:
        assert s['client'].post(f"/devices/{s['device']}/{'revoke' if transition == 'revoke' else 'provision'}", headers=admin).status_code == 200
    assert redeem(s, code).status_code == 404


def test_unrelated_member_cannot_redeem_or_list_owner_readers(scenario):
    s = scenario
    race = setup(s)
    with s['engine'].begin() as db:
        db.execute(text("UPDATE users SET role_code='member' WHERE id=:id"), {'id': s['other']})
    code = invite(s)
    assert redeem(s, code, 'other').status_code == 404
    assert s['client'].get('/member/readers', headers=s['headers'](s['other'])).json() == []
    rows = s['client'].get('/member/readers', headers=s['headers'](s['member'])).json()
    assert len(rows) == 1
    assert rows[0]['id'] == str(s['device']) and rows[0]['race_id'] == race
    assert not any('secret' in key or 'token' in key for key in rows[0])
    assert redeem(s, code).status_code == 200


def test_concurrent_redemption_has_one_winner(scenario):
    s = scenario
    setup(s)
    code = invite(s)
    headers = s['headers'](s['member'])
    def send(_):
        with TestClient(app) as c:
            return c.post('/member/reader-enrollments/redeem', headers=headers, json={'code': code}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, range(2))) == [200, 404]


def test_unauthorized_issuance_and_member_only_endpoints(scenario):
    s = scenario
    setup(s)
    path = f"/devices/{s['device']}/enrollment"
    for actor in ('member', 'other'):
        assert s['client'].post(path, headers=s['headers'](s[actor])).status_code == 403
    assert s['client'].post(path).status_code == 401
    assert s['client'].get('/member/readers', headers=s['headers'](s['admin'])).status_code == 403
