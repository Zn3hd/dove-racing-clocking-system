BEGIN;
ALTER TABLE lofts ADD COLUMN coordinate_source text NOT NULL DEFAULT 'manual'
 CHECK (coordinate_source IN ('manual','browser_gps','town_reference'));
ALTER TABLE lofts ADD COLUMN gps_accuracy_m double precision
 CHECK (gps_accuracy_m>=0 AND gps_accuracy_m<'Infinity'::float8);
ALTER TABLE lofts ADD COLUMN gps_captured_at timestamptz;
ALTER TABLE lofts ADD CONSTRAINT browser_gps_evidence CHECK
 (coordinate_source<>'browser_gps' OR (gps_accuracy_m IS NOT NULL AND gps_captured_at IS NOT NULL));
ALTER TABLE lofts ADD CONSTRAINT town_reference_not_verified CHECK
 (coordinate_source<>'town_reference' OR verified_at IS NULL);
COMMIT;
