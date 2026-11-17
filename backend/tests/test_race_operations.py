"""Real PostgreSQL checks for command-center summaries and review events."""
import os
from uuid import uuid4
import pytest
from test_postgres_e2e import scenario, make_race, register

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Disposable PostgreSQL required')


def test_pending_counts_replay_review_history_and_race_isolation(scenario):
    s = scenario
    c = s['client']; admin = s['headers'](s['admin'])
    race = make_race(s); other_race = make_race(s)
    entry = register(s, race, s['pigeon_guest'], 'QR')
    token = c.post('/clocking/qr/tokens', headers=admin, json={'entry_id': entry}).json()['token']
    assert c.post(f'/races/{race}/activate', headers=admin).status_code == 200
    payload = {'entry_id': entry, 'token': token, 'capture_source': 'web_camera', 'idempotency_key': str(uuid4())}
    scan = c.post('/clocking/qr/scans', headers=s['headers'](s['guest']), json=payload)
    assert scan.status_code == 202, scan.text
    event = scan.json()['event_id']
    assert c.post('/clocking/qr/scans', headers=s['headers'](s['guest']), json=payload).json()['duplicate_request']
    before = c.get(f'/races/{race}/live', headers=admin)
    assert before.status_code == 200, before.text
    data = before.json()
    assert data['pending_reviews'] == 1
    assert data['oldest_pending_at'] is not None
    assert data['arrived_entries'] == 0  # Unreviewed QR must not be ranked.
    assert len(data['recent_activity']) == 1
    assert data['recent_activity'][0]['event_id'] == event
    isolated = c.get(f'/races/{other_race}/live', headers=admin).json()
    assert isolated['pending_reviews'] == 0 and isolated['recent_activity'] == []
    assert c.get(f'/races/{race}/live', headers=s['headers'](s['guest'])).status_code == 403
    review = c.post(f'/clocking/events/{event}/review', headers=admin,
                    json={'decision': 'reject', 'reason': 'Synthetic command-center rejection'})
    assert review.status_code == 200, review.text
    after = c.get(f'/races/{race}/live', headers=admin).json()
    assert after['pending_reviews'] == 0 and after['oldest_pending_at'] is None
    reviews = [item for item in after['recent_activity'] if item['kind'] == 'review']
    assert len(reviews) == 1 and reviews[0]['decision'] == 'reject'
    assert reviews[0]['reviewer'] == 'Test Account'
    assert after['official'] is False and after['arrival_rate_per_minute'] == 0
