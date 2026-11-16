"""Real browser password change and revocation of a second browser session."""
import os

import pytest
from playwright.sync_api import expect, sync_playwright
from qr_live import live_server, login_ui, ok

pytestmark = pytest.mark.skipif(not os.getenv('QR_AUDIT_DATABASE_URL'),
                              reason='Disposable localhost browser database required')


def test_password_change_signs_out_other_browser(live_server):
    server = live_server
    email = 'chairman@qr-audit.example.test'
    password = 'Audit-chairman-password-2026'
    access = ok(server['api'].post('/auth/login', json={
        'email': email, 'password': password}))['access_token']
    ok(server['api'].post('/clubs', headers={'Authorization': 'Bearer ' + access},
                         json={'name': 'Session Revocation Test Club'}), 201)
    with sync_playwright() as tool:
        options = {'headless': True}
        if os.getenv('BROWSER_EXECUTABLE'):
            options['executable_path'] = os.environ['BROWSER_EXECUTABLE']
        browser = tool.chromium.launch(**options)
        try:
            first, second = browser.new_context(), browser.new_context()
            a, b = first.new_page(), second.new_page()
            for page in (a, b):
                page.goto(server['origin'] + '/dashboard/')
                login_ui(page, '#login-form', email, password)
                expect(page.locator('#refresh-button')).to_be_visible()
            a.locator('#password-button').click()
            form = a.locator('#password-form')
            form.locator('[name=current_password]').fill(password)
            form.locator('[name=new_password]').fill('Browser-replacement-password-2026')
            form.locator('[name=confirmation]').fill('Browser-replacement-password-2026')
            form.get_by_role('button', name='Change password', exact=True).click()
            expect(a.locator('#login-form')).to_be_visible()
            with b.expect_response(lambda response: response.url.endswith('/clubs')) as revoked:
                b.locator('#refresh-button').click()
            assert revoked.value.status == 401
            expect(b.locator('#login-form')).to_be_visible()
            login_ui(b, '#login-form', email, 'Browser-replacement-password-2026')
            expect(b.locator('#refresh-button')).to_be_visible()
        finally:
            browser.close()
