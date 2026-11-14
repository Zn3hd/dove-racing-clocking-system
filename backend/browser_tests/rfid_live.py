"""Reading -> real gateway SQLite queue -> HTTP API -> PostgreSQL -> browser.

No RFID hardware is attached. Reader output and transport outages are synthetic;
gateway parsing/storage/synchronization, authentication, API and SQL are real.
"""
import io
import json
import os
from datetime import datetime, timezone

import httpx
import psycopg
import pytest
from playwright.sync_api import expect, sync_playwright

from pigeon_gateway.adapters import KeyboardLines, Simulator
from pigeon_gateway.config import Config
from pigeon_gateway.queue import Queue
from pigeon_gateway.sync import send_heartbeat, synchronize
from qr_live import live_server, login_ui, ok

pytestmark = pytest.mark.skipif(not os.getenv('QR_AUDIT_DATABASE_URL'),
                              reason='Disposable localhost PostgreSQL required')


class LoseAcknowledgement(httpx.BaseTransport):
    """Commit to the real server, then discard one arrival acknowledgement."""
    def __init__(self):
        self.transport = httpx.HTTPTransport(trust_env=False)

    def handle_request(self, request):
        response = self.transport.handle_request(request)
        response.read()
        assert response.status_code == 202
        response.close()
        raise httpx.ReadError('Synthetic lost acknowledgement after commit', request=request)

    def close(self):
        self.transport.close()


@pytest.mark.parametrize('mode', ['operator', 'automatic', 'simulated'])
def test_reader_queue_restart_retry_and_browser_arrival(live_server, mode):
    server = live_server
    api = server['api']
    password = 'Synthetic-member-password-2026'
    token = ok(api.post('/auth/login', json={
        'email': 'chairman@qr-audit.example.test',
        'password': 'Audit-chairman-password-2026'}))['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    ok(api.post('/clubs', headers=headers, json={'name': 'RFID audit club'}), 201)
    member = ok(api.post('/participants', headers=headers, json={
        'full_name': 'Synthetic RFID Member', 'email': 'member@rfid.example.test',
        'password': password, 'role': 'member'}), 201)
    loft = ok(api.post('/lofts', headers=headers, json={
        'user_id': member['id'], 'name': 'Synthetic Sison loft',
        'address': 'Synthetic location — not a verified physical loft',
        'latitude': 9.65881, 'longitude': 125.52861}), 201)
    ok(api.post(f"/lofts/{loft['id']}/verify", headers=headers))
    pigeon = ok(api.post('/pigeons', headers=headers, json={
        'loft_id': loft['id'], 'official_ring_number': 'RFID-AUDIT-' + mode}), 201)
    # Leading zeros must survive parsing, persistence and delivery.
    ring = '000012340056'
    ok(api.post(f"/pigeons/{pigeon['id']}/rfid", headers=headers, json={'uid': ring}), 201)
    adapter = 'simulator' if mode == 'simulated' else 'usb_hid'
    device = ok(api.post('/devices', headers=headers, json={
        'loft_id': loft['id'], 'device_identifier': 'Audit reader ' + mode,
        'reader_adapter': adapter, 'reader_protocol': 'ascii-newline-v1'}), 201)
    device_token = ok(api.post(f"/devices/{device['id']}/provision", headers=headers))['device_token']
    race = ok(api.post('/races', headers=headers, json={
        'name': 'RFID end-to-end ' + mode, 'release_latitude': 10,
        'release_longitude': 125.6}), 201)['id']
    ok(api.post(f'/races/{race}/open', headers=headers))
    entry = ok(api.post(f'/races/{race}/entries', headers=headers, json={
        'pigeon_id': pigeon['id'], 'expected_method': 'RFID'}), 201)
    ok(api.post(f'/races/{race}/activate', headers=headers))
    # Fixture clock only: keep realistic speed without a 30-minute test wait.
    with psycopg.connect(server['pg']) as db:
        db.execute("UPDATE races SET actual_release_at=now()-interval '30 minutes' WHERE id=%s", (race,))
    config = Config(backend_url=server['origin'], allow_local_http=True,
                    device_id=device['id'], race_id=race, adapter=adapter,
                    protocol='ascii-newline-v1', capture_mode='operator' if mode == 'simulated' else mode,
                    queue_path=str(server['artifacts'] / 'gateway.sqlite3'))
    queue = Queue(config.queue_path)
    try:
        reader = Simulator([ring]) if mode == 'simulated' else KeyboardLines(io.StringIO(ring + '\r\n'))
        message = queue.enqueue(config, next(reader.readings()))
        original = queue.db.execute('SELECT payload FROM events WHERE id=?', (message,)).fetchone()[0]
        assert json.loads(original)['ring_uid'] == ring
        def disconnected(request):
            raise httpx.ConnectError('Synthetic offline transport', request=request)
        with httpx.Client(transport=httpx.MockTransport(disconnected)) as offline:
            assert synchronize(queue, config, device_token, offline, now=100)['retry'] == 1
        assert ok(api.get('/clocking/events', headers=headers, params={'race_id': race})) == []
        queue.close()
        queue = Queue(config.queue_path)
        assert queue.db.execute('SELECT payload FROM events WHERE id=?', (message,)).fetchone()[0] == original
        with httpx.Client(transport=LoseAcknowledgement()) as unreliable:
            assert synchronize(queue, config, device_token, unreliable, now=110)['retry'] == 1
        assert queue.counts() == {'pending': 1}
        queue.close()
        queue = Queue(config.queue_path)
        with httpx.Client(trust_env=False) as network:
            assert synchronize(queue, config, device_token, network, now=120)['sent'] == 1
            assert send_heartbeat(queue, config, device_token, network, 'waiting')['heartbeat'] == 'received'
        assert queue.counts() == {'sent': 1}
        events = ok(api.get('/clocking/events', headers=headers, params={'race_id': race}))
        assert len(events) == 1
        event = events[0]
        assert event['metadata']['original_scan'] == ring
        assert event['metadata']['capture_mode'] == mode
        assert event['metadata']['offline_buffered'] is True
        assert not event['blocking_flags']
        assert device_token not in json.dumps(event)
        data = ok(api.get(f'/races/{race}/live', headers=headers))
        assert len(data['entries']) == (0 if mode == 'operator' else 1)
        errors = []
        with sync_playwright() as tool:
            options = {'headless': True}
            if os.getenv('BROWSER_EXECUTABLE'):
                options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
            browser = tool.chromium.launch(**options)
            try:
                admin = browser.new_page(viewport={'width': 1440, 'height': 1024})
                admin.on('pageerror', lambda error: errors.append(str(error)))
                admin.goto(server['origin'] + '/dashboard/')
                login_ui(admin, '#login-form', 'chairman@qr-audit.example.test', 'Audit-chairman-password-2026')
                admin.locator('#operations-nav').click()
                expect(admin.locator('#reader-list')).to_contain_text('Gateway: recent')
                expect(admin.locator('#reader-list')).to_contain_text('Pending: 0')
                admin.locator('#ops-event').select_option(event['id'])
                admin.locator('#ops-review [name=reason]').fill('Synthetic end-to-end evidence reviewed; not official')
                with admin.expect_response(lambda r: r.url.endswith('/review') and r.request.method == 'POST') as reply:
                    admin.locator('#ops-review button[type=submit]').click()
                assert reply.value.status == 200
                admin.locator('#live-nav').click()
                expect(admin.locator('#live-rows')).to_contain_text('RFID-AUDIT-' + mode)
                expect(admin.locator('#live-arrived')).to_have_text('1')
                expected_label = {'operator': 'Operator scan', 'automatic': 'Auto (declared)', 'simulated': 'Simulated'}[mode]
                expect(admin.locator('#live-rows')).to_contain_text(expected_label)
                notice_box = admin.locator('#notice').bounding_box()
                account_box = admin.locator('.topbar').bounding_box()
                assert notice_box and account_box
                assert notice_box['y'] >= account_box['y'] + account_box['height']
                admin.screenshot(path=str(server['artifacts'] / (mode + '-admin-arrival.png')), full_page=True)
                member_page = browser.new_page(viewport={'width': 390, 'height': 844})
                member_page.on('pageerror', lambda error: errors.append(str(error)))
                member_page.goto(server['origin'] + '/dashboard/member.html')
                login_ui(member_page, '#login-form', 'member@rfid.example.test', password)
                expect(member_page.locator('#speed-ranking')).to_contain_text('RFID-AUDIT-' + mode)
                member_page.screenshot(path=str(server['artifacts'] / (mode + '-member-arrival.png')), full_page=True)
                assert not errors
            finally:
                browser.close()
        row = ok(api.get(f'/races/{race}/live', headers=headers))['entries'][0]
        assert row['entry_id'] == entry['id'] and row['rank'] == 1
        assert row['speed_mpm'] == pytest.approx(row['distance_meters'] / (row['flight_duration_seconds'] / 60))
        assert 500 <= row['speed_mpm'] <= 3000
        # New unknown rings are retained as rejected locally, without a backend event.
        queue.enqueue(config, next(KeyboardLines(io.StringIO('000099990000\n')).readings()))
        with httpx.Client(trust_env=False) as network:
            assert synchronize(queue, config, device_token, network, now=130)['rejected'] == 1
        ok(api.post(f'/races/{race}/close', headers=headers))
        replay = ok(api.post(f"/devices/{device['id']}/arrivals", headers={'X-Device-Token': device_token},
                             json=json.loads(original)), 202)
        assert replay['duplicate_request'] is True and replay['event_id'] == event['id']
        assert api.post(f'/races/{race}/finalize', headers=headers).status_code == 409
        with psycopg.connect(server['pg']) as db:
            assert db.execute('SELECT count(*) FROM clocking_events').fetchone()[0] == 1
            assert db.execute('SELECT count(*) FROM race_results').fetchone()[0] == 0
        (server['artifacts'] / 'rfid-summary.json').write_text(json.dumps({
            'capture_mode': mode, 'real_gateway_queue': True, 'real_api': True,
            'real_postgresql': True, 'physical_hardware_tested': False,
            'offline_restart': True, 'lost_ack_retry': True, 'stored_events': 1,
            'unknown_ring_rejected_locally': True, 'provisional_arrival': 1,
            'official_results': 0}), encoding='utf-8')
    finally:
        queue.close()
