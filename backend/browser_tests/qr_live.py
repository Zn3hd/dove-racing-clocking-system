"""Opt-in real Chromium -> FastAPI -> disposable PostgreSQL QR audit.

Only the camera device is synthetic; API responses are never mocked. The USB
case drops an acknowledgement after a real server commit, then retries.
"""
import io
import base64
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not os.getenv('QR_AUDIT_DATABASE_URL'),
    reason='QR_AUDIT_DATABASE_URL must name the disposable localhost audit database')


@pytest.fixture
def live_server(tmp_path):
    source = make_url(os.environ['QR_AUDIT_DATABASE_URL'])
    if source.host not in ('127.0.0.1', 'localhost') or source.database != 'pigeon_qr_test':
        pytest.fail('Refusing database outside the disposable localhost pigeon_qr_test server')
    database_name = 'pigeon_qr_browser_' + uuid4().hex
    assert re.fullmatch(r'pigeon_qr_browser_[a-f0-9]{32}', database_name)
    maintenance = source.set(drivername='postgresql').render_as_string(hide_password=False)
    with psycopg.connect(maintenance, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
    database_url = source.set(drivername='postgresql+psycopg', database=database_name).render_as_string(hide_password=False)
    pg_url = source.set(drivername='postgresql', database=database_name).render_as_string(hide_password=False)
    env = {**os.environ, 'DATABASE_URL': database_url, 'JWT_SECRET_KEY': secrets.token_urlsafe(64)}
    env.pop('ADMIN_BOOTSTRAP_SECRET', None)
    process = None
    log = (tmp_path / 'api.log').open('w', encoding='utf-8')
    try:
        subprocess.run([sys.executable, '-m', 'scripts.run_migrations'], cwd=BACKEND,
                       env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
        from app.auth import hash_password
        with psycopg.connect(pg_url) as connection:
            connection.execute("""INSERT INTO users(role_code,full_name,email,password_hash)
                VALUES ('chairman','QR Audit Chairman','chairman@qr-audit.example.test',%s)""",
                (hash_password('Audit-chairman-password-2026'),))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host',
            '127.0.0.1', '--port', str(port), '--no-access-log'], cwd=BACKEND, env=env,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        origin = f'http://127.0.0.1:{port}'
        with httpx.Client(base_url=origin, trust_env=False, timeout=10) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail('Local API exited; inspect the test api.log')
                try:
                    if client.get('/health').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.1)
            else:
                pytest.fail('Local API did not become ready')
            yield {'origin': origin, 'api': client, 'pg': pg_url, 'artifacts': tmp_path}
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.close()
        # The generated database name is constrained above; no existing DB is used.
        with psycopg.connect(maintenance, autocommit=True) as connection:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database_name)))


def ok(response, status=200):
    assert response.status_code == status, f'Unexpected API status {response.status_code} for {response.request.url.path}'
    return response.json()


def login_ui(page, form_id, email, password):
    form = page.locator(form_id)
    form.locator('[name=email]').fill(email)
    form.locator('[name=password]').fill(password)
    form.get_by_role('button', name='Sign in', exact=True).click()


@pytest.mark.parametrize('capture', ['web_camera', 'usb_qr', 'usb_offline'])
def test_real_browser_guest_qr_to_reviewed_standings(live_server, capture):
    server = live_server
    api = server['api']
    jwt = ok(api.post('/auth/login', json={'email': 'chairman@qr-audit.example.test',
                                         'password': 'Audit-chairman-password-2026'}))['access_token']
    headers = {'Authorization': f'Bearer {jwt}'}
    errors = []
    with sync_playwright() as tool:
        options = {'headless': True}
        if os.getenv('BROWSER_EXECUTABLE'):
            options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
        browser = tool.chromium.launch(**options)
        admin_context = browser.new_context(viewport={'width': 1440, 'height': 1100})
        guest_context = browser.new_context(viewport={'width': 390, 'height': 844})
        try:
            admin = admin_context.new_page()
            admin.on('pageerror', lambda error: errors.append(str(error)))
            admin.goto(server['origin'] + '/dashboard/')
            login_ui(admin, '#login-form', 'chairman@qr-audit.example.test', 'Audit-chairman-password-2026')
            admin.locator('#create-club-button').click()
            admin.locator('#club-form [name=name]').fill('QR Browser Audit Club')
            admin.locator('#club-form button[type=submit]').click()
            expect(admin.locator('#club-dialog')).not_to_be_visible()
            admin.locator('#add-member-button').click()
            form = admin.locator('#member-form')
            form.locator('[name=full_name]').fill('QR Audit Guest')
            form.locator('[name=email]').fill('guest@qr-audit.example.test')
            form.locator('[name=role]').select_option('guest')
            form.locator('[name=password]').fill('Audit-guest-password-2026')
            form.locator('button[type=submit]').click()
            expect(admin.locator('#member-dialog')).not_to_be_visible()
            expect(admin.locator('#member-rows')).to_contain_text('QR Audit Guest')
            admin.get_by_role('button', name='Manage loft location for QR Audit Guest', exact=True).click()
            location = admin.locator('#location-form')
            location.locator('[name=name]').fill('QR Audit Synthetic Loft')
            location.locator('[name=latitude]').fill('9.6588100')
            location.locator('[name=longitude]').fill('125.5286100')
            location.locator('button[type=submit]').click()
            expect(admin.locator('#location-dialog')).not_to_be_visible()
            admin.get_by_role('button', name='Manage loft location for QR Audit Guest', exact=True).click()
            admin.locator('#location-confirmed').check()
            admin.locator('#verify-location').click()
            expect(admin.locator('#location-dialog')).not_to_be_visible()
            person = next(p for p in ok(api.get('/participants', headers=headers)) if p['email'] == 'guest@qr-audit.example.test')
            loft = next(l for l in ok(api.get('/lofts', headers=headers)) if l['user_id'] == person['id'])
            ring = f'QR-AUDIT-{capture.upper()}'
            admin.locator('#operations-nav').click()
            admin.locator('#ops-pigeon [name=loft_id]').select_option(loft['id'])
            admin.locator('#ops-pigeon [name=official_ring_number]').fill(ring)
            with admin.expect_response(lambda r: r.url.endswith('/pigeons') and r.request.method=='POST') as reply:
                admin.locator('#ops-pigeon button[type=submit]').click()
            assert reply.value.status == 201
            pigeon = reply.value.json()
            create = admin.locator('#ops-race-create')
            create.locator('[name=name]').fill(f'QR browser {capture}')
            create.locator('[name=release_latitude]').fill('10')
            create.locator('[name=release_longitude]').fill('125.6')
            with admin.expect_response(lambda r: r.url.endswith('/races') and r.request.method=='POST') as reply:
                create.locator('button[type=submit]').click()
            assert reply.value.status == 201
            race = reply.value.json()['id']
            admin.locator('#ops-open').click()
            admin.locator('#ops-entry [name=pigeon_id]').select_option(pigeon['id'])
            with admin.expect_response(lambda r: r.url.endswith('/entries') and r.request.method=='POST') as reply:
                admin.locator('#ops-entry button[type=submit]').click()
            assert reply.value.status == 201
            entry = reply.value.json()['id']
            admin.locator('#ops-qr [name=entry_id]').select_option(entry)
            with admin.expect_response(lambda r: r.url.endswith('/clocking/qr/tokens') and r.request.method=='POST') as reply:
                admin.locator('#ops-qr button[type=submit]').click()
            assert reply.value.status == 201
            issued = reply.value.json()
            assert issued['qr_png_base64']
            expect(admin.locator('#ops-label')).to_be_visible()
            assert admin.locator('#ops-label-canvas').evaluate('(canvas)=>canvas.width') > 0
            admin.locator('#ops-label-close').click()
            assert admin.locator('#ops-label-canvas').evaluate('(canvas)=>canvas.width') == 0
            admin.locator('#ops-release').click()
            expect(admin.locator('#ops-race-status')).to_contain_text('active')
            # Fixture clock only: avoid a 30-minute wall-clock wait. Event receipt is real.
            with psycopg.connect(server['pg']) as connection:
                connection.execute("UPDATE races SET actual_release_at=now()-interval '30 minutes' WHERE id=%s", (race,))
            admin.locator('#live-nav').click()
            expect(admin.locator('#live-race')).to_have_value(race)
            expect(admin.locator('#live-arrived')).to_have_text('0')
            image_bytes = io.BytesIO(base64.b64decode(issued['qr_png_base64']))
            if capture == 'web_camera':
                # Actual jsQR decoding and real networking; only camera pixels are injected.
                guest_context.route('**/audit-camera-frame.png', lambda route:
                    route.fulfill(status=200, content_type='image/png', body=image_bytes.getvalue()))
                guest_context.add_init_script('''
                    window.auditStoppedTracks=0;
                    Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>{
                      const img=new Image(); img.src='/audit-camera-frame.png'; await img.decode();
                      const canvas=document.createElement('canvas'); canvas.width=img.width; canvas.height=img.height;
                      canvas.getContext('2d').drawImage(img,0,0);
                      const stream=canvas.captureStream(5);
                      for(const track of stream.getTracks()){
                        const stop=track.stop.bind(track);
                        track.stop=()=>{window.auditStoppedTracks++;stop();};
                      }
                      return stream;
                    }}});
                ''')
            guest = guest_context.new_page()
            guest.on('pageerror', lambda error: errors.append(str(error)))
            deliveries = []
            if capture != 'web_camera':
                def lose_first_ack(route):
                    deliveries.append(route.request.post_data_json)
                    if capture == 'usb_offline' and len(deliveries) == 1:
                        route.abort('connectionfailed')
                        return
                    response = route.fetch()  # Real API; only the designated transport failure is injected.
                    assert response.status == 202
                    if len(deliveries) == 1:
                        route.abort('connectionfailed')
                    else:
                        route.fulfill(response=response)
                guest.route('**/clocking/qr/scans', lose_first_ack)
            guest.goto(server['origin'] + '/dashboard/scan.html')
            login_ui(guest, '#scan-login-form', 'guest@qr-audit.example.test', 'Audit-guest-password-2026')
            expect(guest.locator('#scan-entry')).to_have_value(entry)
            if capture == 'web_camera':
                guest.locator('#scan-camera-start').click()
            else:
                guest.locator('#scan-token').fill(issued['qr_payload'])
                guest.locator('#scan-token').press('Enter')
                expect(guest.locator('#scan-status')).to_have_text('Connection failed. Retry the same scan.')
                guest.reload()
                login_ui(guest, '#scan-login-form', 'guest@qr-audit.example.test', 'Audit-guest-password-2026')
                expect(guest.locator('#scan-entry')).to_have_value(entry)
                guest.locator('#scan-recover').click()
                expect(guest.locator('#scan-status')).to_contain_text('Receipts checked.')
                expect(guest.locator('#scan-outbox')).to_contain_text('queued' if capture == 'usb_offline' else 'received')
                guest.locator('#scan-token').fill(issued['qr_payload'])
                guest.locator('#scan-token').press('Enter')
            expect(guest.locator('#scan-status')).to_contain_text('Scan received.', timeout=20000)
            if capture == 'web_camera':
                assert guest.evaluate('window.auditStoppedTracks') == 1
                expect(guest.locator('#scan-video')).not_to_be_visible()
            else:
                assert len(deliveries) == 2 and deliveries[0] == deliveries[1]
            events = ok(api.get('/clocking/events', headers=headers, params={'race_id': race}))
            assert len(events) == 1
            event = events[0]
            assert event['status'] == 'pending' and event['metadata']['capture_source'] == ('web_camera' if capture == 'web_camera' else 'usb_qr')
            assert event['metadata']['capture_mode'] == 'operator'
            assert not event['blocking_flags']
            assert issued['token'] not in json.dumps(event['metadata'])
            assert ok(api.get(f'/races/{race}/live', headers=headers))['entries'] == []
            admin.locator('#operations-nav').click()
            admin.locator('#ops-event').select_option(event['id'])
            admin.locator('#ops-review [name=reason]').fill('Synthetic browser audit evidence reviewed')
            with admin.expect_response(lambda r: r.url.endswith('/review') and r.request.method=='POST') as reply:
                admin.locator('#ops-review button[type=submit]').click()
            assert reply.value.status == 200
            admin.get_by_text('Independent physical guest verification',exact=True).click()
            admin.locator('#ops-physical [name=ring_number_seen]').fill(ring)
            admin.locator('#ops-physical [name=evidence_note]').fill('Synthetic test only: independent physical inspection fixture')
            with admin.expect_response(lambda r: r.url.endswith('/guest-verification') and r.request.method=='POST') as reply:
                admin.locator('#ops-physical button[type=submit]').click()
            assert reply.value.status == 201
            admin.locator('#live-nav').click()
            expect(admin.locator('#live-rows')).to_contain_text(ring, timeout=10000)
            expect(admin.locator('#live-arrived')).to_have_text('1')
            standings = ok(api.get(f'/races/{race}/live', headers=headers))
            row = standings['entries'][0]
            assert standings['official'] is False and row['rank'] == 1 and row['leaderboard'] == 'guest'
            assert row['distance_meters'] > 0 and 500 <= row['speed_mpm'] <= 3000
            assert row['verification_status'] == 'provisional'
            assert row['speed_mpm'] == pytest.approx(row['distance_meters'] / (row['flight_duration_seconds'] / 60))
            admin.screenshot(path=str(server['artifacts'] / f'{capture}-standings.png'), full_page=True)
            ledger = guest.evaluate('(owner)=>QROutbox.records(owner)', person['id'])
            assert len(ledger) == 1
            assert issued['token'] not in json.dumps(ledger)
            assert 'token' not in ledger[0] and 'password' not in ledger[0]
            assert ledger[0]['state'] == 'received'
            assert guest.evaluate('localStorage.length+sessionStorage.length') == 0
            guest.locator('#scan-signout').click()
            expect(guest.locator('#scan-workspace')).not_to_be_visible()
            assert guest.locator('#scan-token').input_value() == ''
            admin.locator('#operations-nav').click()
            with admin.expect_response(lambda r: r.url.endswith('/close') and r.request.method=='POST') as reply:
                admin.locator('#ops-close').click()
            assert reply.value.status == 200
            # Receipt recovery is available even when the race no longer appears in active entries.
            guest.reload()
            login_ui(guest, '#scan-login-form', 'guest@qr-audit.example.test', 'Audit-guest-password-2026')
            guest.locator('#scan-recover').click()
            expect(guest.locator('#scan-status')).to_contain_text('Receipts checked.')
            expect(guest.locator('#scan-outbox')).to_contain_text('received')
            admin.locator('#logout-button').click()
            expect(admin.locator('#workspace')).not_to_be_visible()
            login_ui(admin, '#login-form', 'chairman@qr-audit.example.test', 'Audit-chairman-password-2026')
            admin.locator('#operations-nav').click()
            assert admin.locator('#ops-entry [name=expected_method] option').count() == 2
            assert api.post(f'/races/{race}/finalize' , headers=headers).status_code == 409
            with psycopg.connect(server['pg']) as connection:
                assert connection.execute('SELECT count(*) FROM race_results').fetchone()[0] == 0
            assert not errors
            (server['artifacts'] / 'summary.json').write_text(json.dumps({
                'capture': capture, 'real_api': True, 'real_postgresql': True, 'stored_events': 1,
                'review_required': True, 'provisional_rank': 1, 'official_results': 0,
                'synthetic_camera': capture == 'web_camera', 'lost_ack_retry': capture == 'usb_qr', 'offline_reload_retry': capture == 'usb_offline', 'admin_ui': True}), encoding='utf-8')
        finally:
            guest_context.close()
            admin_context.close()
            browser.close()
