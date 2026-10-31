"""Read-only, explicitly non-official leaderboard preview.

Only human-approved clocking evidence is considered. The first approved
arrival per entry wins; unreviewed and rejected events are excluded.
This endpoint never writes to race_results or finalizes a race.
"""
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..club_access import require_race_admin
from ..database import get_db
from ..calculations import speed_mpm, convert_speed, leaderboard

router = APIRouter(prefix="/races", tags=["results-preview"])


@router.get('/{race_id}/live')
def live_race(race_id: UUID, db: Session = Depends(get_db),
              actor: dict = Depends(require_race_admin)):
    """Live provisional standings from first eligible server-received evidence.

    Automatic is a device's declared capture mode, never hardware attestation.
    Unreviewed operator/unknown captures and manual claims are not auto-ranked.
    """
    race = db.execute(text('''SELECT id,name,status,actual_release_at,minimum_speed_mpm,maximum_speed_mpm,
        guest_ranking_mode,display_speed_unit FROM races WHERE id=:id'''),
        {'id': race_id}).mappings().one()
    total = db.execute(text("SELECT count(*) FROM race_entries WHERE race_id=:id AND status='registered'"),
                       {'id': race_id}).scalar_one()
    rows = []
    if race['actual_release_at'] is not None:
        events = db.execute(text('''SELECT DISTINCT ON (e.id)
            e.id AS entry_id,e.pigeon_id,e.loft_id,e.distance_meters,e.expected_method AS clocking_method,
            p.official_ring_number,u.full_name AS owner_name,c.id AS event_id,c.recorded_at AS arrival_at,
            c.device_id,c.metadata,gv.decision AS physical_verification,
            v.warnings AS validation_warnings,v.is_simulated,
            EXISTS(SELECT 1 FROM clocking_reviews cr WHERE cr.event_id=c.id AND cr.decision='approve') AS reviewed
            FROM race_entries e JOIN clocking_events c ON c.entry_id=e.id
            JOIN clocking_event_validation v ON v.event_id=c.id AND cardinality(v.blocking_flags)=0
            JOIN pigeons p ON p.id=e.pigeon_id JOIN lofts l ON l.id=e.loft_id JOIN users u ON u.id=l.user_id
            LEFT JOIN guest_arrival_verifications gv ON gv.event_id=c.id
            WHERE e.race_id=:race AND e.status='registered' AND c.status IN ('pending','valid')
              AND c.recorded_at>:release AND (gv.decision IS NULL OR gv.decision='confirmed')
              AND NOT EXISTS(SELECT 1 FROM clocking_reviews cr WHERE cr.event_id=c.id AND cr.decision='reject')
              AND ((c.method='RFID' AND (
                    c.metadata->>'capture_mode'='automatic' OR c.metadata->>'simulated'='true'))
                   OR EXISTS(SELECT 1 FROM clocking_reviews cr WHERE cr.event_id=c.id AND cr.decision='approve'))
            ORDER BY e.id,c.recorded_at,c.id LIMIT 1000'''),
            {'race': race_id, 'release': race['actual_release_at']}).mappings().all()
        for event in events:
            velocity = speed_mpm(float(event['distance_meters']), race['actual_release_at'], event['arrival_at'])
            metadata = event['metadata'] or {}
            rows.append({key: event[key] for key in ('entry_id','pigeon_id','loft_id','clocking_method',
                'official_ring_number','owner_name','event_id','arrival_at','device_id','reviewed')})
            rows[-1].update({
                'distance_meters': float(event['distance_meters']), 'speed_mpm': velocity,
                'display_speed': round(convert_speed(velocity, race['display_speed_unit']), 4),
                'flight_duration_seconds': (event['arrival_at'] - race['actual_release_at']).total_seconds(),
                'qualifying_status': 'qualified' if velocity >= float(race['minimum_speed_mpm']) else 'below_minimum',
                'verification_status': 'provisional', 'timestamp_policy': 'server_receipt',
                'capture_mode': 'simulated' if event['is_simulated'] else metadata.get('capture_mode', 'unknown'),
                'offline_buffered': bool(metadata.get('offline_buffered', False)),
                'device_recorded_at': metadata.get('device_recorded_at'),
                'validation_warnings': event['validation_warnings'],
                'physical_verification': event['physical_verification'] or 'not_recorded'})
    ranked = leaderboard(rows, race['guest_ranking_mode'])
    ranks = {row['entry_id']: (row['rank'], row['leaderboard']) for row in ranked}
    for order, row in enumerate(sorted(rows, key=lambda r: (r['arrival_at'], str(r['entry_id']))), 1):
        row['arrival_order'] = order
        row['rank'], row['leaderboard'] = ranks.get(row['entry_id'], (None,
            'combined' if race['guest_ranking_mode'] == 'combined' else
            ('guest' if row['clocking_method'] == 'QR' else 'member')))
    rows.sort(key=lambda row: (row['leaderboard'], row['rank'] is None, row['rank'] or 0, row['arrival_order']))
    validation = validation_summary(db, race_id)
    return {'race_id': race_id, 'race_name': race['name'], 'race_status': race['status'],
            'maximum_speed_mpm': float(race['maximum_speed_mpm']), **validation,
            'release_at': race['actual_release_at'], 'official': False,
            'updated_at': datetime.now(timezone.utc), 'speed_unit': race['display_speed_unit'],
            'registered_entries': total, 'arrived_entries': len(rows), 'limit': 1000,
            'possibly_truncated': len(rows) == 1000, 'entries': rows,
            'note': 'Provisional server-receipt timing. Automatic mode is declared, not verified. '
                    'Operator/manual captures require review; simulator scans are labeled. Official finalization is disabled.'}


def validation_summary(db, race_id):
    counts = db.execute(text('''SELECT count(*) FILTER(WHERE cardinality(blocking_flags)>0) AS suspicious_events,
        count(*) FILTER(WHERE 'repeat_scan'=ANY(warnings)) AS repeat_scans,
        count(*) FILTER(WHERE is_simulated) AS simulated_events
        FROM clocking_event_validation WHERE race_id=:id'''), {'id': race_id}).mappings().one()
    flagged = db.execute(text('''SELECT v.event_id,v.entry_id,v.speed_mpm,v.blocking_flags,v.warnings,
        c.recorded_at,c.received_at,p.official_ring_number FROM clocking_event_validation v
        JOIN clocking_events c ON c.id=v.event_id JOIN race_entries e ON e.id=v.entry_id
        JOIN pigeons p ON p.id=e.pigeon_id
        WHERE v.race_id=:id AND cardinality(v.blocking_flags)>0
        ORDER BY c.received_at DESC,c.id LIMIT 50'''), {'id': race_id}).mappings().all()
    return {**dict(counts), 'flagged_events': [dict(row) for row in flagged], 'flagged_event_limit': 50}


@router.get('/{race_id}/validation')
def race_validation(race_id: UUID, db: Session = Depends(get_db),
                    actor: dict = Depends(require_race_admin)):
    return {'race_id': race_id, 'official': False, **validation_summary(db, race_id)}

@router.get("/{race_id}/leaderboard-preview")
def preview_leaderboard(race_id: UUID, db: Session = Depends(get_db),
                        actor: dict = Depends(require_race_admin)):
    race = db.execute(text("""
        SELECT id,name,status,actual_release_at,minimum_speed_mpm,
               guest_ranking_mode,display_speed_unit
        FROM races WHERE id=:race
    """), {"race":race_id}).mappings().first()
    if race is None:
        raise HTTPException(404, "Race not found")
    if race["actual_release_at"] is None:
        return {"race_id":race_id,"official":False,"entries":[],
                "note":"Race has not been released"}
    # Approval is explicit review evidence; the event itself remains pending
    # until a separate trusted acceptance/finalization process is implemented.
    events = db.execute(text("""
        SELECT DISTINCT ON (e.id)
               e.id AS entry_id,e.pigeon_id,e.loft_id,e.distance_meters,
               e.expected_method AS clocking_method,c.id AS event_id,
               c.recorded_at AS arrival_at,
               gv.decision AS physical_verification,
               gv.verified_at AS physically_verified_at,
               src.channel AS source_channel
        FROM race_entries e
        JOIN clocking_events c ON c.entry_id=e.id
        JOIN clocking_event_validation v ON v.event_id=c.id AND cardinality(v.blocking_flags)=0
        LEFT JOIN guest_arrival_verifications gv ON gv.event_id=c.id
        LEFT JOIN clocking_event_sources src ON src.event_id=c.id
        WHERE e.race_id=:race AND e.status='registered'
          AND c.status='pending'
          AND (gv.decision IS NULL OR gv.decision='confirmed')
          AND EXISTS (
              SELECT 1 FROM clocking_reviews cr
              WHERE cr.event_id=c.id AND cr.decision='approve'
          )
          AND c.recorded_at > :released
        ORDER BY e.id,c.recorded_at ASC,c.id ASC
    """), {"race":race_id,"released":race["actual_release_at"]}).mappings().all()
    rows = []
    for event in events:
        velocity = speed_mpm(float(event["distance_meters"]),
                             race["actual_release_at"],event["arrival_at"])
        rows.append({
            "entry_id":event["entry_id"],"pigeon_id":event["pigeon_id"],
            "loft_id":event["loft_id"],"event_id":event["event_id"],
            "clocking_method":event["clocking_method"],
            "arrival_at":event["arrival_at"],
            "distance_meters":float(event["distance_meters"]),
            "flight_duration_seconds":(event["arrival_at"]-race["actual_release_at"]).total_seconds(),
            "speed_mpm":round(velocity,5),
            "display_speed":round(convert_speed(velocity,race["display_speed_unit"]),4),
            "qualifying_status":"qualified" if velocity>=float(race["minimum_speed_mpm"]) else "below_minimum",
            "verification_status":"provisional",
            "physical_verification":event["physical_verification"] or "not_recorded",
            "physically_verified_at":event["physically_verified_at"],
            "source_channel":event["source_channel"] or (
                "qr" if event["clocking_method"] == "QR" else "rfid"),
        })
    # Only qualifying entries receive a rank; below-minimum entries remain visible.
    ranked = leaderboard(rows, race["guest_ranking_mode"])
    ranks = {r["entry_id"]:(r["rank"],r["leaderboard"]) for r in ranked}
    for row in rows:
        rank = ranks.get(row["entry_id"])
        row["rank"] = rank[0] if rank else None
        row["leaderboard"] = rank[1] if rank else (
            "combined" if race["guest_ranking_mode"]=="combined" else
            ("guest" if row["clocking_method"]=="QR" else "member"))
    rows.sort(key=lambda r:(r["leaderboard"],r["rank"] is None,
                             r["rank"] if r["rank"] is not None else 999999,
                             r["arrival_at"],str(r["entry_id"])))
    return {"race_id":race_id,"race_name":race["name"],"race_status":race["status"],
            "official":False,"ranking_mode":race["guest_ranking_mode"],
            "speed_unit":race["display_speed_unit"],
            "entries":rows,
            "note":"Preview from reviewed evidence only; not official or finalized"}
