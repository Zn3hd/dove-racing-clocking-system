"""Password changes revoke every older bearer token, across account roles."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import ALGORITHM, signing_key
from app.main import app
from test_postgres_e2e import scenario

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),
                              reason='Disposable PostgreSQL required')


def login(s, uid, password='integration-password-123'):
    response = s['client'].post('/auth/login', json={
        'email': f'{uid}@example.test', 'password': password})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


@pytest.mark.parametrize('account', ['admin', 'member', 'guest'])
def test_password_change_revokes_all_old_sessions(scenario, account):
    s = scenario
    c = s['client']
    uid = s[account]
    first, second = login(s, uid), login(s, uid)
    other = login(s, s['other'])
    assert c.get('/auth/me', headers=second).status_code == 200
    response = c.post('/auth/change-password', headers=first, json={
        'current_password': 'integration-password-123',
        'new_password': 'replacement-password-2026'})
    assert response.status_code == 200, response.text
    for old in (first, second):
        assert c.get('/auth/me', headers=old).status_code == 401
        assert c.get('/member/overview', headers=old).status_code == 401
    assert c.get('/auth/me', headers=other).status_code == 200
    assert c.post('/auth/login', json={'email': f'{uid}@example.test',
        'password': 'integration-password-123'}).status_code == 401
    fresh = login(s, uid, 'replacement-password-2026')
    assert c.get('/auth/me', headers=fresh).status_code == 200
    # A second change also revokes version-1 sessions, not only legacy tokens.
    assert c.post('/auth/change-password', headers=fresh, json={
        'current_password': 'replacement-password-2026',
        'new_password': 'another-replacement-2026'}).status_code == 200
    assert c.get('/auth/me', headers=fresh).status_code == 401
    assert c.get('/auth/me', headers=login(s, uid, 'another-replacement-2026')).status_code == 200
    with s['engine'].connect() as db:
        assert db.execute(text('SELECT session_version FROM users WHERE id=:id'),
                          {'id': uid}).scalar_one() == 2


def test_unsuccessful_password_changes_preserve_sessions(scenario):
    s = scenario
    headers = login(s, s['member'])
    for current, new, status in (
        ('wrong-password', 'replacement-password-2026', 401),
        ('integration-password-123', 'integration-password-123', 422),
        ('integration-password-123', 'short', 422),
    ):
        response = s['client'].post('/auth/change-password', headers=headers,
            json={'current_password': current, 'new_password': new})
        assert response.status_code == status, response.text
        assert s['client'].get('/auth/me', headers=headers).status_code == 200


def test_concurrent_password_changes_have_one_winner(scenario):
    s = scenario
    headers = login(s, s['member'])

    def change(password):
        with TestClient(app) as client:
            return client.post('/auth/change-password', headers=headers, json={
                'current_password': 'integration-password-123',
                'new_password': password}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(change, ['first-replacement-2026', 'second-replacement-2026']))
    assert sorted(statuses) == [200, 401]
    assert s['client'].get('/auth/me', headers=headers).status_code == 401
    with s['engine'].connect() as db:
        assert db.execute(text('SELECT session_version FROM users WHERE id=:id'),
                          {'id': s['member']}).scalar_one() == 1


@pytest.mark.parametrize('version', [None, '0', True, -1, 1])
def test_missing_malformed_or_future_session_version_is_rejected(scenario, version):
    s = scenario
    now = datetime.now(timezone.utc)
    claims = {'sub': str(s['member']), 'iat': now,
              'exp': now + timedelta(minutes=30), 'iss': 'dove-racing'}
    if version is not None:
        claims['sv'] = version
    token = jwt.encode(claims, signing_key(), algorithm=ALGORITHM)
    assert s['client'].get('/auth/me', headers={
        'Authorization': 'Bearer ' + token}).status_code == 401
