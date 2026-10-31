-- Reader capabilities are declared configuration, not hardware attestation.
BEGIN;
ALTER TABLE devices ADD COLUMN reader_adapter text NOT NULL DEFAULT 'unspecified'
 CHECK (reader_adapter IN ('unspecified','simulator','usb_hid','serial','network'));
ALTER TABLE devices ADD COLUMN reader_protocol text
 CHECK (reader_protocol IS NULL OR length(trim(reader_protocol)) BETWEEN 1 AND 120);
COMMIT;
