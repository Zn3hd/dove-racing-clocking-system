"""Final web pilot checks: narrow-screen controls and sign-in privacy."""
import re
import pytest
from playwright.sync_api import expect
from qr_browser import page, ASSETS, serve
from workspace_browser import preview


@pytest.mark.parametrize('width', [320, 390, 1440])
def test_directory_keeps_location_and_actions_inside_viewport(page, preview, width):
    page.set_viewport_size({'width': width, 'height': 844})
    page.route('**/participants*', lambda r: r.fulfill(json=[{
        'id': 'person-1', 'full_name': 'Synthetic member', 'email': 'long-member-address@example.test',
        'role_code': 'member', 'status': 'active', 'phone': '+63 900 000 0000'}]))
    page.route('**/lofts*', lambda r: r.fulfill(json=[{
        'id': 'loft-1', 'user_id': 'person-1', 'name': 'Synthetic loft',
        'latitude': 9.65881, 'longitude': 125.52861,
        'address': 'Synthetic address, Sison, Surigao del Norte', 'coordinate_source': 'manual',
        'verified_at': '2026-11-01T00:00:00Z'}]))
    page.goto(preview)
    page.get_by_role('button', name='Members', exact=True).click()
    page.locator('#refresh-button').click()
    row = page.locator('#member-rows tr').first
    expect(row).to_contain_text('Synthetic member')
    expect(row).to_contain_text('Sison')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for cell in row.locator('td').all():
        box = cell.bounding_box()
        assert box and box['x'] >= 0 and box['x'] + box['width'] <= width
    row.get_by_role('button', name='Manage loft location for Synthetic member', exact=True).click()
    expect(page.locator('#location-dialog')).to_be_visible()


@pytest.mark.parametrize('filename,form_id', [
    ('index.html', 'login-form'), ('member.html', 'login-form'), ('scan.html', 'scan-login-form')])
def test_signin_navigation_and_password_visibility_reset(page, filename, form_id):
    page.route('http://localhost:8123/dashboard/**', lambda r: r.fulfill(
        path=str(ASSETS / r.request.url.split('/dashboard/')[-1])))
    page.goto('http://localhost:8123/dashboard/' + filename)
    form = page.locator('#' + form_id)
    password = form.locator('[name=password]')
    password.fill('synthetic-password')
    page.get_by_role('checkbox', name='Show password', exact=True).check()
    expect(password).to_have_attribute('type', 'text')
    assert page.locator('.role-links a').count() == 3
    assert page.locator('.role-links [aria-current=page]').count() == 1
    assert page.evaluate('(id) => Array.from(new FormData(document.getElementById(id)).keys())', form_id) == ['email', 'password']
    form.evaluate('(form) => form.reset()')
    expect(password).to_have_attribute('type', 'password')
    expect(password).to_have_value('')
    expect(page.get_by_role('checkbox', name='Show password', exact=True)).not_to_be_checked()


def test_guest_capture_precedes_recovery_and_token_stays_masked(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    serve(page)
    expect(page.locator('#scan-workspace')).to_be_visible()
    camera = page.locator('#scan-camera-start').bounding_box()
    recovery = page.locator('#scan-recover').bounding_box()
    submit = page.locator('#scan-submit').bounding_box()
    assert camera['y'] < submit['y'] < recovery['y']
    expect(page.locator('#scan-token')).to_have_attribute('type', 'password')
    expect(page.locator('#scan-recover')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_operations_shortcuts_and_separate_test_tools(page, preview):
    page.route('**/clocking/rfid/simulator-options*', lambda r: r.fulfill(json={'devices': [], 'rings': []}))
    page.goto(preview)
    page.get_by_role('button', name='Race operations', exact=True).click()
    for link in page.locator('.operations-nav a').all():
        assert page.locator(link.get_attribute('href')).count() == 1
    expect(page.locator('#ops-simulate')).to_be_hidden()
    page.get_by_text('RFID simulator · test tools', exact=True).click()
    expect(page.locator('#ops-simulate')).to_be_visible()


@pytest.mark.parametrize('width', [320, 1440])
def test_icons_load_locally_under_content_security_policy(page, preview, width):
    page.set_viewport_size({'width': width, 'height': 844})
    # Match the deployed policy: no CDN, inline scripts or inline styles.
    def policy(route):
        response = route.fetch()
        # The preview normally injects an inline demo login. Remove that fixture
        # helper so this check exercises the production script policy faithfully.
        body = re.sub(r'<script>window.addEventListener.*?</script>', '', response.text(), flags=re.S)
        route.fulfill(response=response, body=body, headers={**response.headers,
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'"})
    page.route('**/dashboard/', policy)
    page.add_init_script("window.policyViolations=[];document.addEventListener('securitypolicyviolation',e=>window.policyViolations.push(e.violatedDirective));")
    page.goto(preview)
    page.evaluate("""() => {
        state.token='synthetic-demo'; state.club={id:'club-demo',name:'Demo racing club'};
        document.querySelector('#login-screen').hidden=true;
        document.querySelector('#workspace').hidden=false; showView('live');
    }""")
    expect(page.locator('#live-rows tr')).to_have_count(7)
    button = page.get_by_role('button', name='Live race', exact=True)
    expect(button).to_have_class(re.compile(r'icon-activity'))
    mask = button.evaluate("el => getComputedStyle(el, '::before').maskImage")
    assert '/dashboard/vendor/feather/activity.svg' in mask
    # Decode the asset in the browser, rather than checking only its CSS URL.
    assert page.evaluate("""async () => {
        const image = new Image(); image.src = '/dashboard/vendor/feather/activity.svg';
        await image.decode(); return image.naturalWidth === 24;
    }""")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='Members', exact=True).click()
    expect(page.get_by_role('heading', name='Club members')).to_be_visible()
    assert page.evaluate('window.policyViolations') == []
