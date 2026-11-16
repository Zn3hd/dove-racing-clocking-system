"""Flutter's actual SQLite queue and HTTP worker against disposable PostgreSQL.

No phone hardware or production backend is used. Token travels only in the child
process environment; do not print that environment or production secrets.
"""
import os
from pathlib import Path
import shutil
import subprocess

import psycopg
import pytest
from qr_live import live_server, ok

pytestmark = pytest.mark.skipif(not os.getenv('QR_AUDIT_DATABASE_URL'),
                              reason='Disposable localhost PostgreSQL required')


@pytest.mark.parametrize('mode', ['simulated', 'operator'])
def test_mobile_queue_lost_ack_to_real_backend(live_server, mode):
    flutter = os.getenv('MOBILE_FLUTTER_EXECUTABLE') or shutil.which('flutter')
    if not flutter:
        pytest.fail('Set MOBILE_FLUTTER_EXECUTABLE to the local Flutter command')
    api = live_server['api']
    jwt = ok(api.post('/auth/login', json={'email': 'chairman@qr-audit.example.test',
              'password': 'Audit-chairman-password-2026'}))['access_token']
    headers = {'Authorization': 'Bearer ' + jwt}
    ok(api.post('/clubs', headers=headers, json={'name': 'Mobile RFID test club'}), 201)
    member = ok(api.post('/participants', headers=headers, json={
        'full_name': 'Synthetic mobile member', 'email': 'mobile@example.test',
        'password': 'Synthetic-mobile-password-2026', 'role': 'member'}), 201)
    loft = ok(api.post('/lofts', headers=headers, json={
        'user_id': member['id'], 'name': 'Synthetic test loft',
        'latitude': 9.65881, 'longitude': 125.52861}), 201)
    ok(api.post(f"/lofts/{loft['id']}/verify", headers=headers))
    pigeon = ok(api.post('/pigeons', headers=headers, json={
        'loft_id': loft['id'], 'official_ring_number': 'MOBILE-SIM-TEST'}), 201)
    ok(api.post(f"/pigeons/{pigeon['id']}/rfid", headers=headers,
                json={'uid': '000012340056'}), 201)
    reader = ok(api.post('/devices', headers=headers, json={
        'loft_id': loft['id'], 'device_identifier': 'Mobile simulator pilot',
        'reader_adapter': 'simulator' if mode == 'simulated' else 'usb_hid',
        'reader_protocol': 'mobile-simulator-v1' if mode == 'simulated' else 'ascii-newline-v1'}), 201)
    member_jwt = ok(api.post('/auth/login', json={'email': 'mobile@example.test',
        'password': 'Synthetic-mobile-password-2026'}))['access_token']
    member_headers = {'Authorization': 'Bearer ' + member_jwt}
    invitation = ok(api.post(f"/devices/{reader['id']}/enrollment", headers=headers), 201)['enrollment_code']
    credential = ok(api.post('/member/reader-enrollments/redeem', headers=member_headers,
        json={'code': invitation}))['device_token']
    race = ok(api.post('/races', headers=headers, json={
        'name': 'Mobile simulator test', 'release_latitude': 10, 'release_longitude': 125.6}), 201)['id']
    ok(api.post(f'/races/{race}/open', headers=headers))
    ok(api.post(f'/races/{race}/entries', headers=headers, json={
        'pigeon_id': pigeon['id'], 'expected_method': 'RFID'}), 201)
    ok(api.post(f'/races/{race}/activate', headers=headers))
    assignments = ok(api.get('/member/readers', headers=member_headers))
    assert len(assignments) == 1 and assignments[0]['id'] == reader['id']
    with psycopg.connect(live_server['pg']) as db:
        db.execute("UPDATE races SET actual_release_at=now()-interval '30 minutes' WHERE id=%s", (race,))
    env = {**os.environ, 'MOBILE_RFID_TEST_ORIGIN': live_server['origin'],
           'MOBILE_RFID_TEST_OWNER': member['id'], 'MOBILE_RFID_TEST_DEVICE': reader['id'],
           'MOBILE_RFID_TEST_MODE': mode,
           'MOBILE_RFID_TEST_RACE': race, 'MOBILE_RFID_TEST_TOKEN': credential}
    mobile = Path(__file__).resolve().parents[2] / 'mobile'
    result = subprocess.run([flutter, '--no-version-check', 'test', '--no-pub',
                             'test/rfid_live_test.dart', '--reporter', 'expanded'],
                            cwd=mobile, env=env, capture_output=True, text=True, timeout=180)
    # Avoid surfacing raw HTTP payload/credential information from test internals.
    if result.returncode:
        safe = (result.stdout + result.stderr).replace(credential, '[redacted]').replace(jwt, '[redacted]')
        pytest.fail('Mobile live test failed:\n' + safe[-10000:])
    events = ok(api.get('/clocking/events', headers=headers, params={'race_id': race}))
    assert len(events) == 1
    event = events[0]
    assert event['metadata']['capture_mode'] == mode
    assert event['metadata']['simulated'] == (mode == 'simulated')
    assert event['metadata']['original_scan'] == '000012340056'
    live = ok(api.get(f'/races/{race}/live', headers=headers))
    if mode == 'operator':
        assert live['arrived_entries'] == 0
        ok(api.post(f"/clocking/events/{event['id']}/review", headers=headers,
            json={'decision': 'approve', 'reason': 'Synthetic mobile operator evidence reviewed; not official'}))
        live = ok(api.get(f'/races/{race}/live', headers=headers))
    assert live['arrived_entries'] == 1
    arrival = live['entries'][0]
    assert arrival['rank'] == 1 and arrival['distance_meters'] > 0 and arrival['speed_mpm'] > 0
    assert arrival['speed_mpm'] == pytest.approx(
        arrival['distance_meters'] / (arrival['flight_duration_seconds'] / 60))
    with psycopg.connect(live_server['pg']) as db:
        assert db.execute('SELECT count(*) FROM device_gateway_messages WHERE device_id=%s',
                          (reader['id'],)).fetchone()[0] == 1
        assert db.execute('''SELECT count(*) FROM race_results r
            JOIN race_entries e ON e.id=r.entry_id WHERE e.race_id=%s''', (race,)).fetchone()[0] == 0
        heartbeat = db.execute('SELECT reported_reader_state,reported_pending_count FROM devices WHERE id=%s',
                              (reader['id'],)).fetchone()
        assert heartbeat == ('not_probed', 0)
