-- Database-enforced immutability of finalized race results.
BEGIN;
CREATE OR REPLACE FUNCTION protect_finalized_race_results()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE race_state text;
BEGIN
  SELECT r.status INTO race_state
  FROM race_entries e JOIN races r ON r.id=e.race_id
  WHERE e.id=COALESCE(NEW.entry_id,OLD.entry_id);
  IF race_state='finalized' THEN
    RAISE EXCEPTION 'Finalized race results are immutable';
  END IF;
  RETURN COALESCE(NEW,OLD);
END;
$$;
DROP TRIGGER IF EXISTS prevent_finalized_result_changes ON race_results;
CREATE TRIGGER prevent_finalized_result_changes
BEFORE UPDATE OR DELETE ON race_results
FOR EACH ROW EXECUTE FUNCTION protect_finalized_race_results();
CREATE OR REPLACE FUNCTION protect_finalized_race_events()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE race_state text;
BEGIN
  SELECT r.status INTO race_state FROM race_entries e
  JOIN races r ON r.id=e.race_id WHERE e.id=OLD.entry_id;
  IF race_state='finalized' THEN
    RAISE EXCEPTION 'Finalized race clocking evidence is immutable';
  END IF;
  RETURN OLD;
END;
$$;
DROP TRIGGER IF EXISTS prevent_finalized_event_changes ON clocking_events;
CREATE TRIGGER prevent_finalized_event_changes
BEFORE UPDATE OR DELETE ON clocking_events
FOR EACH ROW EXECUTE FUNCTION protect_finalized_race_events();
COMMIT;
