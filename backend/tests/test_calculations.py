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
