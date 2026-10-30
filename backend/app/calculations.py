"""Pure race calculations; no hardware dependency."""
from datetime import datetime
from math import radians, sin, cos, asin, sqrt


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError('Invalid geographic coordinates')
    a = sin(radians(lat2-lat1)/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(radians(lon2-lon1)/2)**2
    return 6371008.8 * 2 * asin(min(1.0, sqrt(a)))


def speed_mpm(distance: float, release: datetime, arrival: datetime) -> float:
    if release.tzinfo is None or arrival.tzinfo is None:
        raise ValueError('Timezone-aware timestamps required')
    elapsed = (arrival-release).total_seconds()
    if elapsed <= 0 or distance <= 0:
        raise ValueError('Arrival must follow release; distance must be positive')
    return distance / (elapsed/60)


def convert_speed(mpm: float, unit: str) -> float:
    if unit == 'm/min': return mpm
    if unit == 'm/s': return mpm/60
    if unit == 'km/h': return mpm*0.06
    raise ValueError('Unsupported speed unit')


def leaderboard(rows: list[dict], mode: str = 'separate') -> list[dict]:
    if mode not in ('combined','separate'):
        raise ValueError('Unsupported leaderboard mode')
    groups = {}
    for row in rows:
        if row['qualifying_status'] != 'qualified' or row['verification_status'] not in ('approved','provisional'):
            continue
        group = 'combined' if mode == 'combined' else ('guest' if row['clocking_method'] == 'QR' else 'member')
        groups.setdefault(group, []).append(row)
    result=[]
    for group, entries in groups.items():
        entries.sort(key=lambda r: (-float(r['speed_mpm']), r['arrival_at'], str(r['entry_id'])))
        rank=0; prev=None
        for pos, row in enumerate(entries, 1):
            velocity=round(float(row['speed_mpm']),4)
            if velocity != prev: rank=pos
            result.append({**row,'leaderboard':group,'rank':rank})
            prev=velocity
    return sorted(result,key=lambda r:(r['leaderboard'],r['rank']))
