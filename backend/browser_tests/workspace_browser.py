"""Responsive workspace interactions against a loopback-only synthetic fixture.

Run: python -m pytest browser_tests/workspace_browser.py -q
Set BROWSER_EXECUTABLE to the installed Microsoft Edge executable.
"""
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest
from playwright.sync_api import expect
from qr_browser import page
from workspace_preview import PreviewHandler, RACE, RACES


@pytest.fixture
def preview():
    server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/dashboard/'
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


@pytest.mark.parametrize('width,height', [(1440, 1024), (1024, 768), (390, 844), (320, 740)])
def test_admin_layout_navigation_and_evidence(page, preview, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    # The active race is deliberately not first: review must preserve selection.
    page.route('**/races', lambda route: route.fulfill(json=[
        {'id': 'other-race', 'name': 'Other draft race', 'status': 'draft',
         'minimum_speed_mpm': 500, 'maximum_speed_mpm': 3000}, *RACES]))
    page.goto(preview)
    expect(page.locator('#live-rows tr')).to_have_count(7)
    expect(page.locator('.simulated-row')).to_contain_text('Test #6')
    expect(page.locator('.simulated-row')).to_contain_text('Simulated')
    expect(page.locator('.simulated-row')).to_contain_text('Unreviewed')
    expect(page.locator('#live-rows')).to_contain_text('Below minimum')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page overflows viewport'
    if width <= 390:
        speed_cell = page.locator('#live-rows tr').first.locator('[data-label="Speed"]')
        evidence_cell = page.locator('#live-rows tr').first.locator('[data-label="Evidence"]')
        for cell in (speed_cell, evidence_cell):
            box = cell.bounding_box()
            assert box and box['x'] >= 0 and box['x'] + box['width'] <= width
        expect(page.get_by_role('cell').filter(has_text='Auto (declared)').first).to_be_visible()
    page.evaluate("renderLive({...insightSnapshot, race_name: 'LongRaceName'.repeat(30)})")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    page.get_by_role('button', name='Members', exact=True).click()
    expect(page.get_by_role('heading', name='Club members')).to_be_visible()
    assert page.evaluate('scrollY') == 0
    page.get_by_role('button', name='Live race', exact=True).click()
    expect(page.locator('#live-rows tr')).to_have_count(7)
    page.locator('summary').filter(has_text='Race details and top competitors').click()
    page.locator('#insight-leader-mode').select_option('pigeon')
    expect(page.locator('#insight-leaders')).to_contain_text('PH-26-135701')
    page.locator('summary').filter(has_text='Arrival validation').click()
    expect(page.locator('#validation-rows')).to_contain_text('exceeds maximum speed')
    page.get_by_role('button', name='Review arrival evidence', exact=True).click()
    expect(page.locator('#ops-race')).to_have_value(RACE)
    expect(page.locator('#ops-evidence')).to_be_focused()


@pytest.mark.parametrize('width,height', [(1440, 1024), (390, 844), (320, 740)])
def test_member_details_and_signout(page, preview, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(preview + 'member.html')
    expect(page.locator('#speed-ranking .leader-main')).to_have_count(6)
    expect(page.locator('#speed-ranking')).to_contain_text('Simulated')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    first = page.locator('#speed-ranking .leader-main').first
    first.click()
    expect(first).to_have_attribute('aria-expanded', 'true')
    expect(page.locator('#speed-ranking .leader-details').first).to_contain_text('Distance')
    page.get_by_text('Arrival order and below-minimum arrivals', exact=True).click()
    expect(page.locator('#arrival-order .leader-main')).to_have_count(7)
    page.locator('#signout').click()
    expect(page.locator('#workspace')).to_be_hidden()
    expect(page.locator('#speed-ranking')).to_have_text('')


def test_live_error_recovery_and_empty_state(page, preview):
    page.goto(preview)
    expect(page.locator('#live-rows tr')).to_have_count(7)
    page.route('**/races/*/live', lambda route: route.fulfill(status=503, json={'detail': 'Synthetic outage'}))
    expect(page.locator('#live-feed-state')).to_contain_text('Not synchronized', timeout=7000)
    expect(page.locator('#live-rows tr')).to_have_count(7)
    page.unroute('**/races/*/live')
    expect(page.locator('#live-feed-state')).to_contain_text('Connected', timeout=7000)
    page.route('**/races', lambda route: route.fulfill(json=[]))
    page.get_by_role('button', name='Reload races', exact=True).click()
    expect(page.locator('#live-rows tr')).to_have_count(0)
    expect(page.locator('#live-state')).to_contain_text('No races are available')


def test_untrusted_evidence_is_text_and_writes_are_disabled(page, preview):
    page.goto(preview)
    expect(page.locator('#live-rows tr')).to_have_count(7)
    page.evaluate("""() => {
      const sample = {...insightSnapshot, entries: [{...insightSnapshot.entries[0],
        official_ring_number: '<img src=x onerror=alert(1)>', owner_name: '<script>bad()</script>'}]};
      renderLive(sample);
    }""")
    expect(page.locator('#live-rows img, #live-rows script')).to_have_count(0)
    expect(page.locator('#live-rows')).to_contain_text('<img src=x onerror=alert(1)>')
    response = page.request.post(preview.replace('/dashboard/', '/races'), data={})
    assert response.status == 405
