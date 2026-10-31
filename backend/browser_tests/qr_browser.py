"""Real Chromium tests with local QR frames and mocked API responses; no camera/DB required."""
import base64
import io
import json
import os
from pathlib import Path

import pytest
import qrcode
from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / 'dashboard'
ENTRY = '00000000-0000-0000-0000-000000000001'
EVENT = '00000000-0000-0000-0000-000000000003'
TOKEN = 'Ab_0-' * 10


@pytest.fixture
def page():
    with sync_playwright() as browser_tool:
        options = {'headless': True}
        if os.getenv('BROWSER_EXECUTABLE'):
            options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
        browser = browser_tool.chromium.launch(**options)
        context = browser.new_context()
        page = context.new_page()
        page.errors = []
        page.on('pageerror', lambda error: page.errors.append(str(error)))
        yield page
        assert not page.errors
        context.close()
        browser.close()


def serve(page, *, lost_response=False, guest=True, rate_limited=False):
    attempts = []
    def route_request(route):
        path = route.request.url.split('http://localhost:8123')[-1]
        payload = None
        if path == '/auth/login':
            payload = {'access_token': 'test-guest-session'}
        elif path == '/auth/me':
            payload = {'id':'00000000-0000-0000-0000-000000000009','role': 'guest' if guest else 'member', 'full_name': 'Test guest'}
        elif path == '/clocking/qr/entries':
            payload = [{'entry_id': ENTRY, 'race_name': 'Test race', 'official_ring_number': 'PH-0001'}]
        elif path == '/clocking/qr/scans':
            assert route.request.headers['authorization'] == 'Bearer test-guest-session'
            attempts.append(route.request.post_data_json)
            if rate_limited and len(attempts) == 1:
                route.fulfill(status=429, headers={'Retry-After':'1'}, json={'detail':'Too many requests'})
                return
            if lost_response and len(attempts) == 1:
                route.abort('connectionfailed')
                return
            payload = {'event_id': EVENT, 'status': 'pending', 'official_result_created': False}
        elif path.startswith('/dashboard/'):
            file = (ASSETS / path.removeprefix('/dashboard/')).resolve()
            assert file.is_relative_to(ASSETS)
            kind = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'}.get(file.suffix, 'text/plain')
            route.fulfill(status=200, content_type=kind, body=file.read_bytes())
            return
        else:
            route.fulfill(status=404)
            return
        route.fulfill(status=202 if path.endswith('/scans') else 200, json=payload)
    page.route('**/*', route_request)
    page.goto('http://localhost:8123/dashboard/scan.html')
    page.locator('[name=email]').fill('guest@example.test')
    page.locator('[name=password]').fill('test-password')
    page.get_by_role('button', name='Sign in', exact=True).click()
    return attempts


def test_usb_qr_retries_identically_and_clears_session(page):
    attempts = serve(page, lost_response=True)
    page.locator('#scan-token').fill(TOKEN)
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Connection failed. Retry the same scan.', exact=True).wait_for()
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Scan received.', exact=False).wait_for()
    assert attempts[0] == attempts[1]
    assert attempts[0]['capture_source'] == 'usb_qr'
    page.locator('#scan-token').fill(TOKEN)
    page.locator('#scan-token').press('Enter')
    page.wait_for_timeout(100)
    assert len(attempts) == 2
    assert page.evaluate('localStorage.length + sessionStorage.length') == 0
    page.get_by_role('button', name='Sign out', exact=True).click()
    assert page.locator('#scan-workspace').is_hidden()
    assert page.locator('#scan-token').input_value() == ''


def test_camera_decodes_real_qr_frame_and_stops_track(page):
    image = qrcode.make(json.dumps({'version': 1, 'entry_id': ENTRY, 'token': TOKEN}, separators=(',', ':')))
    output = io.BytesIO(); image.save(output, format='PNG')
    image_url = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
    page.add_init_script('''
      window.stoppedTracks = 0;
      Object.defineProperty(navigator, 'mediaDevices', {value: {getUserMedia: async () => {
        const image = new Image(); image.src = IMAGE_URL;
        await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
        canvas.getContext('2d').drawImage(image, 0, 0);
        const stream = canvas.captureStream(5);
        for (const track of stream.getTracks()) {
          const stop = track.stop.bind(track);
          track.stop = () => { window.stoppedTracks++; stop(); };
        }
        return stream;
      }}});
    '''.replace('IMAGE_URL', json.dumps(image_url)))
    attempts = serve(page)
    page.get_by_role('button', name='Use camera', exact=True).click()
    page.get_by_text('Scan received.', exact=False).wait_for(timeout=20000)
    assert attempts[0]['capture_source'] == 'web_camera'
    assert attempts[0]['token'] == TOKEN
    assert page.evaluate('window.stoppedTracks') == 1
    assert page.locator('#scan-video').is_hidden()


def test_camera_denial_keeps_usb_path_available(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.add_init_script("Object.defineProperty(navigator, 'mediaDevices', {value: {getUserMedia: async () => {throw new Error('denied');}}});")
    attempts = serve(page)
    page.get_by_role('button', name='Use camera', exact=True).click()
    page.get_by_text('Camera unavailable or permission denied.', exact=False).wait_for()
    page.locator('#scan-token').fill(TOKEN)
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Scan received.', exact=False).wait_for()
    assert len(attempts) == 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if os.getenv('QR_SCREENSHOT'):
        page.screenshot(path=os.environ['QR_SCREENSHOT'], full_page=True)


def test_non_guest_cannot_open_scanning_workspace(page):
    attempts = serve(page, guest=False)
    page.get_by_text('Use your guest account', exact=False).wait_for()
    assert page.locator('#scan-workspace').is_hidden()
    assert attempts == []


def test_rate_limit_retries_keep_durable_submission_id(page):
    attempts = serve(page, rate_limited=True)
    page.locator('#scan-token').fill(TOKEN)
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Too many requests. Retry in 1 seconds using the same code.', exact=True).wait_for()
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Scan received.', exact=False).wait_for()
    assert attempts[0] == attempts[1]


def test_storage_failure_prevents_unrecoverable_submission(page):
    page.add_init_script("Object.defineProperty(window,'indexedDB',{value:{open:()=>{throw new Error('Storage disabled');}}});")
    attempts = serve(page)
    page.locator('#scan-token').fill(TOKEN)
    page.locator('#scan-token').press('Enter')
    page.get_by_text('Recovery storage is unavailable.', exact=False).wait_for()
    assert attempts == []
