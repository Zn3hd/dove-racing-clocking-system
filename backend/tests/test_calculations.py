from datetime import datetime, timezone, timedelta
import pytest
from app.calculations import distance_meters, speed_mpm, convert_speed, leaderboard

def test_distance():
    assert distance_meters(0,0,0,0)==0
    assert 110000 < distance_meters(0,0,0,1) < 112000

def test_speed():
    start=datetime(2026,10,30,6,tzinfo=timezone.utc)
    assert speed_mpm(120000,start,start+timedelta(hours=2))==1000
    with pytest.raises(ValueError): speed_mpm(120000,start,start)

def test_units():
    assert convert_speed(500,'m/s')==pytest.approx(8.3333333)
    assert convert_speed(500,'km/h')==30

def test_leaderboard_modes():
    base={'qualifying_status':'qualified','verification_status':'approved','arrival_at':datetime.now(timezone.utc)}
    rows=[{**base,'entry_id':'1','clocking_method':'RFID','speed_mpm':1000},{**base,'entry_id':'2','clocking_method':'QR','speed_mpm':1200}]
    assert [r['leaderboard'] for r in leaderboard(rows,'combined')]==['combined','combined']
    assert {r['leaderboard'] for r in leaderboard(rows,'separate')}=={'guest','member'}


def test_near_equal_speeds_do_not_tie_after_display_rounding():
    base = {'qualifying_status': 'qualified', 'verification_status': 'provisional',
            'clocking_method': 'RFID', 'arrival_at': datetime(2026, 11, 4, tzinfo=timezone.utc)}
    rows = [{**base, 'entry_id': 'slow', 'speed_mpm': 1000.00001},
            {**base, 'entry_id': 'fast', 'speed_mpm': 1000.00002}]
    ranked = leaderboard(rows, 'combined')
    assert [(row['entry_id'], row['rank']) for row in ranked] == [('fast', 1), ('slow', 2)]


def test_exact_ties_skip_following_rank_and_do_not_mutate_inputs():
    base = {'qualifying_status': 'qualified', 'verification_status': 'approved',
            'clocking_method': 'RFID', 'arrival_at': datetime(2026, 11, 4, tzinfo=timezone.utc)}
    rows = [{**base, 'entry_id': 'b', 'speed_mpm': 1200},
            {**base, 'entry_id': 'a', 'speed_mpm': 1200},
            {**base, 'entry_id': 'c', 'speed_mpm': 1100}]
    original = [dict(row) for row in rows]
    ranked = leaderboard(rows, 'combined')
    assert [(row['entry_id'], row['rank']) for row in ranked] == [
        ('a', 1), ('b', 1), ('c', 3)]
    assert rows == original


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), -1])
def test_nonfinite_or_negative_speeds_never_enter_rankings(invalid):
    row = {'entry_id': 'invalid', 'clocking_method': 'RFID',
           'qualifying_status': 'qualified', 'verification_status': 'provisional',
           'speed_mpm': invalid, 'arrival_at': datetime.now(timezone.utc)}
    with pytest.raises(ValueError):
        leaderboard([row], 'combined')
    with pytest.raises(ValueError):
        convert_speed(invalid, 'm/min')


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), float('-inf')])
def test_invalid_distance_rejected(invalid):
    start = datetime(2026, 11, 4, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        speed_mpm(invalid, start, start + timedelta(minutes=5))


def test_nonqualifying_and_unreviewed_entries_are_excluded_from_ranks():
    base = {'clocking_method': 'RFID', 'arrival_at': datetime.now(timezone.utc),
            'speed_mpm': 1000}
    rows = [{**base, 'entry_id': 'valid', 'qualifying_status': 'qualified',
             'verification_status': 'approved'},
            {**base, 'entry_id': 'slow', 'qualifying_status': 'below_minimum',
             'verification_status': 'approved'},
            {**base, 'entry_id': 'unreviewed', 'qualifying_status': 'qualified',
             'verification_status': 'pending'}]
    assert [row['entry_id'] for row in leaderboard(rows)] == ['valid']
