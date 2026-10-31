-- Conservative ranking validation. Thresholds are operational review policy.
BEGIN;
ALTER TABLE races ADD COLUMN maximum_speed_mpm numeric(12,4) NOT NULL DEFAULT 3000;
UPDATE races SET maximum_speed_mpm=greatest(maximum_speed_mpm,minimum_speed_mpm+1);
ALTER TABLE races ADD CONSTRAINT race_speed_range CHECK
 (maximum_speed_mpm>minimum_speed_mpm AND maximum_speed_mpm<'Infinity'::numeric);
ALTER TABLE races ADD COLUMN clock_tolerance_seconds integer NOT NULL DEFAULT 5
 CHECK (clock_tolerance_seconds BETWEEN 0 AND 300);
CREATE INDEX ix_clocking_repeat_scan ON clocking_events(entry_id,method,recorded_at,id);

CREATE FUNCTION parse_reader_observation(value text) RETURNS timestamptz
LANGUAGE plpgsql STABLE AS $$
BEGIN
 IF value IS NULL OR value !~ 'T.*(Z|[+-][0-9]{2}:[0-9]{2})$' THEN RETURN NULL; END IF;
 RETURN value::timestamptz;
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END;
$$;

CREATE VIEW clocking_event_validation AS
WITH evidence AS (
 SELECT c.*,e.race_id,e.distance_meters,r.actual_release_at,r.maximum_speed_mpm,
 r.clock_tolerance_seconds,parse_reader_observation(c.metadata->>'device_recorded_at') AS observed_at,
 (coalesce(c.metadata->>'simulated','false')='true'
  OR c.metadata->>'adapter_type'='simulator' OR c.metadata->>'capture_mode'='simulated'
  OR d.reader_adapter='simulator') IS TRUE AS is_simulated,
 CASE WHEN c.recorded_at>r.actual_release_at THEN
  e.distance_meters/(extract(epoch FROM (c.recorded_at-r.actual_release_at))/60) END AS speed_mpm
 FROM clocking_events c JOIN race_entries e ON e.id=c.entry_id
 JOIN races r ON r.id=e.race_id LEFT JOIN devices d ON d.id=c.device_id
)
SELECT id AS event_id,entry_id,race_id,speed_mpm,is_simulated,
 array_remove(ARRAY[
  CASE WHEN actual_release_at IS NULL THEN 'race_not_released' END,
  CASE WHEN recorded_at<=actual_release_at THEN 'arrival_not_after_release' END,
  CASE WHEN recorded_at>received_at+make_interval(secs=>clock_tolerance_seconds) THEN 'arrival_after_receipt' END,
  CASE WHEN recorded_at<received_at-make_interval(secs=>clock_tolerance_seconds) THEN 'arrival_before_receipt' END,
  CASE WHEN speed_mpm>maximum_speed_mpm THEN 'speed_above_maximum' END,
  CASE WHEN metadata->>'device_recorded_at' IS NOT NULL AND observed_at IS NULL THEN 'invalid_observed_timestamp' END,
  CASE WHEN observed_at<=actual_release_at THEN 'observation_not_after_release' END,
  CASE WHEN observed_at>received_at+make_interval(secs=>clock_tolerance_seconds) THEN 'observation_in_future' END
 ]::text[],NULL) AS blocking_flags,
 array_remove(ARRAY[
  CASE WHEN is_simulated THEN 'simulated_evidence' END,
  CASE WHEN coalesce(metadata->>'offline_buffered','false')='true' THEN 'buffered_evidence' END,
  CASE WHEN observed_at<received_at-interval '5 minutes' THEN 'delayed_observation' END,
  CASE WHEN EXISTS(SELECT 1 FROM clocking_events prior WHERE prior.entry_id=evidence.entry_id
    AND prior.method=evidence.method AND (prior.recorded_at,prior.id)<(evidence.recorded_at,evidence.id))
   THEN 'repeat_scan' END
 ]::text[],NULL) AS warnings
FROM evidence;

-- Repair the existing trigger's UPDATE return: returning OLD silently discarded
-- all review rejections even for races that were not finalized.
CREATE OR REPLACE FUNCTION protect_finalized_race_events()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE race_state text;
BEGIN
 SELECT r.status INTO race_state FROM race_entries e JOIN races r ON r.id=e.race_id WHERE e.id=OLD.entry_id;
 IF race_state='finalized' THEN RAISE EXCEPTION 'Finalized race clocking evidence is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
$$;

CREATE FUNCTION guard_simulated_clocking() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE simulated boolean;
BEGIN
 IF TG_OP='UPDATE' AND (coalesce(OLD.metadata->>'simulated','false')='true'
   OR OLD.metadata->>'adapter_type'='simulator' OR OLD.metadata->>'capture_mode'='simulated') THEN
  NEW.metadata=NEW.metadata || jsonb_build_object('simulated',true);
 END IF;
 simulated=(coalesce(NEW.metadata->>'simulated','false')='true'
   OR NEW.metadata->>'adapter_type'='simulator' OR NEW.metadata->>'capture_mode'='simulated'
   OR EXISTS(SELECT 1 FROM devices WHERE id=NEW.device_id AND reader_adapter='simulator')) IS TRUE;
 IF simulated THEN
  NEW.metadata=NEW.metadata || jsonb_build_object('simulated',true);
  IF NEW.status='valid' THEN RAISE EXCEPTION 'Simulated evidence cannot become valid official evidence'; END IF;
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER guard_simulated_clocking BEFORE INSERT OR UPDATE ON clocking_events
FOR EACH ROW EXECUTE FUNCTION guard_simulated_clocking();

CREATE FUNCTION guard_official_clocking_result() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE evidence clocking_event_validation%ROWTYPE;
BEGIN
 SELECT * INTO evidence FROM clocking_event_validation WHERE event_id=NEW.accepted_event_id;
 IF evidence.entry_id IS DISTINCT FROM NEW.entry_id THEN RAISE EXCEPTION 'Result must match event entry'; END IF;
 IF EXISTS(SELECT 1 FROM races WHERE id=evidence.race_id AND status='finalized') THEN
  RAISE EXCEPTION 'Finalized race results are immutable';
 END IF;
 IF NEW.verification_status='approved' OR NEW.finalized_at IS NOT NULL THEN
  IF evidence.is_simulated OR cardinality(evidence.blocking_flags)>0 THEN
   RAISE EXCEPTION 'Simulated or suspicious evidence cannot become official results';
  END IF;
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER guard_official_clocking_result BEFORE INSERT OR UPDATE ON race_results
FOR EACH ROW EXECUTE FUNCTION guard_official_clocking_result();
COMMIT;
