"""Browser session isolation under delayed and failed member API responses."""
from qr_browser import page, ASSETS
from playwright.sync_api import expect


def serve(page, *, fail_me=False, delay_first=False):
    held=[]
    def route(r):
        path=r.request.url.split('http://localhost:8123')[-1]
        auth=r.request.headers.get('authorization','')
        if path=='/auth/login':r.fulfill(json={'access_token':r.request.post_data_json['email']});return
        if path=='/auth/me':
            r.fulfill(status=503 if fail_me else 200,json={'role':'member','full_name':'Test member'});return
        if path=='/member/overview':
            if delay_first and 'first@' in auth:held.append(r);return
            r.fulfill(json={'full_name':'Second member','pigeons':[], 'race_entries':[]});return
        if path.startswith('/dashboard/'):
            file=ASSETS/path.removeprefix('/dashboard/')
            if file.is_file():r.fulfill(path=str(file));return
        r.fulfill(status=404,json={'detail':'Not found'})
    page.route('http://localhost:8123/**',route)
    page.goto('http://localhost:8123/dashboard/member.html')
    return held


def login(page,email):
    page.locator('[name=email]').fill(email)
    page.locator('[name=password]').fill('synthetic-password')
    page.locator('#login-form button').click()


def test_delayed_old_401_cannot_sign_out_new_member(page):
    held=serve(page,delay_first=True)
    login(page,'first@example.test')
    expect(page.locator('#workspace')).to_be_visible()
    page.wait_for_function('busy === true')
    page.locator('#signout').click()
    login(page,'second@example.test')
    expect(page.locator('#workspace')).to_be_visible()
    assert len(held)==1
    held[0].fulfill(status=401,json={'detail':'Expired old session'})
    expect(page.locator('#welcome')).to_have_text('Welcome, Second member')
    expect(page.locator('#workspace')).to_be_visible()


def test_failed_identity_validation_discards_token(page):
    serve(page,fail_me=True)
    login(page,'first@example.test')
    expect(page.locator('#login-error')).not_to_have_text('')
    assert page.evaluate('token') is None


def test_signout_clears_prior_member_information(page):
    serve(page)
    login(page,'second@example.test')
    expect(page.locator('#welcome')).to_have_text('Welcome, Second member')
    page.locator('#signout').click()
    expect(page.locator('#welcome')).to_have_text('')
