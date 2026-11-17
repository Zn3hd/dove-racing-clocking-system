"""Read-only, race-scoped operational summaries; no result certification."""
from sqlalchemy import text


def operations_summary(db, race_id):
    pending = db.execute(text('''
        SELECT count(*) AS pending_reviews,
            count(*) FILTER (WHERE cardinality(v.blocking_flags)>0) AS pending_flagged_reviews,
            min(c.received_at) AS oldest_pending_at
        FROM clocking_events c JOIN race_entries e ON e.id=c.entry_id
        JOIN clocking_event_validation v ON v.event_id=c.id
        WHERE e.race_id=:race AND c.status='pending'
          AND NOT EXISTS(SELECT 1 FROM clocking_reviews r WHERE r.event_id=c.id)
    '''), {'race': race_id}).mappings().one()
    activity = db.execute(text('''
        SELECT * FROM (
            SELECT 'submission:'||c.id::text AS activity_id, c.id AS event_id,
                c.received_at AS occurred_at,
                CASE WHEN cardinality(v.blocking_flags)>0 THEN 'validation' ELSE 'submission' END AS kind,
                p.official_ring_number, c.method, c.status,
                CASE WHEN v.is_simulated THEN 'simulated' ELSE c.metadata->>'capture_mode' END AS capture_mode,
                v.blocking_flags, NULL::text AS decision, NULL::text AS reviewer
            FROM clocking_events c JOIN race_entries e ON e.id=c.entry_id
            JOIN pigeons p ON p.id=e.pigeon_id JOIN clocking_event_validation v ON v.event_id=c.id
            WHERE e.race_id=:race
            UNION ALL
            SELECT 'review:'||r.id::text, c.id, r.reviewed_at, 'review',
                p.official_ring_number, c.method, c.status,
                CASE WHEN v.is_simulated THEN 'simulated' ELSE c.metadata->>'capture_mode' END,
                v.blocking_flags, r.decision, u.full_name
            FROM clocking_reviews r JOIN clocking_events c ON c.id=r.event_id
            JOIN race_entries e ON e.id=c.entry_id JOIN pigeons p ON p.id=e.pigeon_id
            JOIN users u ON u.id=r.reviewed_by JOIN clocking_event_validation v ON v.event_id=c.id
            WHERE e.race_id=:race
        ) activity ORDER BY occurred_at DESC, activity_id DESC LIMIT 24
    '''), {'race': race_id}).mappings().all()
    return {**dict(pending), 'recent_activity': [dict(row) for row in activity],
            'activity_limit': 24}
