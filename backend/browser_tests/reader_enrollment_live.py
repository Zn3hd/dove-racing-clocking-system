"""Administrator issues a private invitation in the real browser; owner redeems."""
import os
import re
import pytest
from playwright.sync_api import expect, sync_playwright
from qr_live import live_server, login_ui, ok

pytestmark = pytest.mark.skipif(not os.getenv('QR_AUDIT_DATABASE_URL'),
                              reason='Disposable localhost PostgreSQL required')


def test_browser_invitation_is_owner_bound_one_use_and_cleared(live_server):
    api = live_server['api']
    admin = ok(api.post('/auth/login', json={'email': 'chairman@qr-audit.example.test',
              'password': 'Audit-chairman-password-2026'}))['access_token']
    headers = {'Authorization': 'Bearer ' + admin}
    ok(api.post('/clubs', headers=headers, json={'name': 'Owner enrollment browser test'}), 201)
    member = ok(api.post('/participants', headers=headers, json={
        'full_name': 'Synthetic reader owner', 'email': 'reader-owner@example.test',
        'password': 'Synthetic-owner-password-2026', 'role': 'member'}), 201)
    loft = ok(api.post('/lofts', headers=headers, json={
        'user_id': member['id'], 'name': 'Synthetic verified loft',
        'latitude': 9.65881, 'longitude': 125.52861}), 201)
    ok(api.post(f"/lofts/{loft['id']}/verify", headers=headers))
    reader = ok(api.post('/devices', headers=headers, json={
        'loft_id': loft['id'], 'device_identifier': 'Owner browser reader',
        'reader_adapter': 'usb_hid', 'reader_protocol': 'ascii-newline-v1'}), 201)
    member_jwt = ok(api.post('/auth/login', json={'email': 'reader-owner@example.test',
                  'password': 'Synthetic-owner-password-2026'}))['access_token']
    with sync_playwright() as tool:
        options = {'headless': True}
        if os.getenv('BROWSER_EXECUTABLE'):
            options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
        browser = tool.chromium.launch(**options)
        try:
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(live_server['origin'] + '/dashboard/')
            login_ui(page, '#login-form', 'chairman@qr-audit.example.test', 'Audit-chairman-password-2026')
            page.locator('#operations-nav').click()
            page.get_by_role('button', name='Create owner invitation', exact=True).click()
            expect(page.locator('#reader-secret-kind')).to_have_text('Private owner invitation')
            expect(page.locator('#reader-secret-help')).to_contain_text('Redeeming rotates')
            code = page.locator('#reader-secret-value').input_value()
            assert re.fullmatch(r'[A-Za-z0-9_-]{43}', code)
            assert ok(api.get('/devices', headers=headers))[0]['enrollment_status'] == 'pending'
            response = ok(api.post('/member/reader-enrollments/redeem',
                headers={'Authorization': 'Bearer ' + member_jwt}, json={'code': code}))
            assert response['device_id'] == reader['id']
            assert api.post('/member/reader-enrollments/redeem',
                headers={'Authorization': 'Bearer ' + member_jwt}, json={'code': code}).status_code == 404
            page.locator('#reader-secret-close').click()
            expect(page.locator('#reader-secret')).not_to_be_visible()
            expect(page.locator('#reader-secret-value')).to_have_value('')
            page.get_by_role('button', name='Create owner invitation', exact=True).click()
            expect(page.locator('#reader-secret')).to_be_visible()
            replacement = page.locator('#reader-secret-value').input_value()
            page.locator('#reader-secret-close').click()
            page.get_by_role('button', name='Revoke credential / invitation', exact=True).click()
            expect(page.locator('#reader-list')).to_contain_text('Invitation: none')
            assert api.post('/member/reader-enrollments/redeem',
                headers={'Authorization': 'Bearer ' + member_jwt}, json={'code': replacement}).status_code == 404
            assert errors == []
        finally:
            browser.close()
