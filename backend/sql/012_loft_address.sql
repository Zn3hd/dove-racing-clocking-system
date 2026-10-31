BEGIN;
ALTER TABLE lofts ADD COLUMN address text
 CHECK (address IS NULL OR length(btrim(address)) BETWEEN 1 AND 500);
COMMIT;
