"""Local UI review fixture. Synthetic data only; never connects to a database.

Run from any directory: python workspace_preview.py --port 8765
The demo bootstrap is injected by this loopback-only server, never shipped in app assets.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parents[1] / 'dashboard'
RACE = '00000000-0000-0000-0000-000000000001'
RACES = [dict(id=RACE, name='Surigao Training Race', status='active',
              minimum_speed_mpm=500, maximum_speed_mpm=3000)]
ENTRIES = [dict(entry_id=f'entry-{i}', pigeon_id=f'pigeon-{i}', loft_id=f'loft-{i}',
                loft_name=name, owner_name=name, official_ring_number=f'PH-26-{135700+i}',
                capture_mode='simulated' if i == 6 else 'automatic',
                clocking_method='RFID', reviewed=i < 4, offline_buffered=i == 5,
                qualifying_status='below_minimum' if i == 7 else 'qualified',
                verification_status='provisional', leaderboard='member',
                rank=None if i == 7 else i, arrival_order=i+2,
                arrival_at=f'2026-11-17T00:{26+i:02}:10+00:00',
                distance_meters=187000, display_speed=speed, speed_mpm=speed)
           for i, (name, speed) in enumerate([
               ('Amihan Loft', 1284.50), ('Northern Loft', 1282.36),
               ('Baybay Loft', 1279.71), ('Amihan Loft', 1276.92),
               ('Coastline Loft', 1274.38), ('Trial Loft', 1218.63),
               ('Northern Loft', 480.12)], 1)]


def live_data():
    return dict(race_id=RACE, race_name=RACES[0]['name'], race_status='active',
                release_at='2026-11-16T22:00:00+00:00', official=False,
                registered_entries=120, arrived_entries=len(ENTRIES), active_participants=24,
                speed_unit='m/min', updated_at=datetime.now(timezone.utc).isoformat(),
                pending_reviews=3, pending_flagged_reviews=1, oldest_pending_at=(datetime.now(timezone.utc)-timedelta(minutes=14)).isoformat(),
                last_eligible_arrival_at='2026-11-17T00:32:10+00:00', arrival_rate_per_minute=0.0,
                recent_activity=[
                    dict(activity_id='submission-demo',event_id='event-1',occurred_at='2026-11-17T00:32:10+00:00',kind='submission',official_ring_number='PH-26-135705',method='RFID',status='pending',capture_mode='automatic',blocking_flags=[]),
                    dict(activity_id='review-demo',event_id='event-2',occurred_at='2026-11-17T00:31:20+00:00',kind='review',official_ring_number='PH-26-135702',method='RFID',decision='approve',reviewer='Demo official',blocking_flags=[]),
                    dict(activity_id='flag-demo',event_id='event-3',occurred_at='2026-11-17T00:25:06+00:00',kind='validation',official_ring_number='PH-26-135952',method='RFID',blocking_flags=['exceeds_maximum_speed'])],
                entries=ENTRIES, suspicious_events=1, repeat_scans=1, simulated_events=3,
                maximum_speed_mpm=3000, possibly_truncated=False,
                flagged_events=[dict(official_ring_number='PH-26-135952',
                                     blocking_flags=['exceeds_maximum_speed'], speed_mpm=3540,
                                     received_at='2026-11-17T00:25:06+00:00')])


class PreviewHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_body(self, body, kind='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith('/dashboard/'):
            file = (ASSETS / (path.removeprefix('/dashboard/') or 'index.html')).resolve()
            if not file.is_relative_to(ASSETS) or not file.is_file():
                self.send_error(404)
                return
            body = file.read_bytes()
            if file.name in ('index.html', 'member.html'):
                admin = file.name == 'index.html'
                bootstrap = ("state.token='synthetic-demo'; state.club={id:'club-demo',name:'Demo racing club'};"
                             "document.querySelector('#login-screen').hidden=true;"
                             "document.querySelector('#workspace').hidden=false;"
                             "document.querySelector('.club-label .eyebrow').textContent='LOCAL SYNTHETIC PREVIEW';"
                             "document.querySelector('#sidebar-club').textContent='Demo racing club';showView('live');"
                             if admin else
                             "token='synthetic-demo';document.querySelector('#login-panel').hidden=true;"
                             "document.querySelector('#workspace').hidden=false;document.querySelector('#signout').hidden=false;refresh();")
                demo = "<script>window.addEventListener('load',()=>{" + bootstrap + "});</script>"
                body = body.replace(b'</body>', (demo + '</body>').encode())
            self.send_body(body, self.guess_type(str(file)) + '; charset=utf-8')
            return
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard/')
            self.end_headers()
            return
        if path == '/races':
            data = RACES
        elif path == f'/races/{RACE}/live' or path == f'/member/races/{RACE}/standings':
            data = live_data()
        elif path == '/member/overview':
            data = dict(full_name='Demo member', pigeons=[], race_entries=[dict(
                race_id=RACE, race_name=RACES[0]['name'], race_status='active',
                official_ring_number='PH-26-135701', first_unrejected_scan_at=None)])
        elif path == '/clubs':
            data = [dict(id='club-demo', name='Demo racing club')]
        elif path in ('/participants', '/lofts', '/pigeons', '/devices', '/clocking/events') or path.startswith('/races/') or path.startswith('/clocking/qr/tokens/race/'):
            data = []
        elif path == '/favicon.ico':
            self.send_body(b'', 'image/x-icon', 204)
            return
        else:
            self.send_error(404)
            return
        self.send_body(json.dumps(data).encode())

    def do_POST(self):
        self.send_body(b'{"detail":"Read-only synthetic preview: writes are disabled."}', status=405)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    print(f'Synthetic UI preview: http://127.0.0.1:{args.port}/dashboard/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler).serve_forever()
