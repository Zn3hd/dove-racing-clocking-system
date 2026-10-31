BEGIN;
ALTER TABLE devices
 ADD COLUMN heartbeat_at timestamptz,
 ADD COLUMN reported_reader_state text CHECK (reported_reader_state IN ('not_probed','waiting','error')),
 ADD COLUMN reported_pending_count integer CHECK (reported_pending_count BETWEEN 0 AND 1000000000),
 ADD COLUMN reported_rejected_count integer CHECK (reported_rejected_count BETWEEN 0 AND 1000000000);
COMMIT;
