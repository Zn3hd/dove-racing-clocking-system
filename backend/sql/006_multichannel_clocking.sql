-- Phase 6C: preserve channel and evidence provenance without changing legacy RFID/QR method constraints.
-- Every new channel must still use a dedicated validated ingestion adapter.
BEGIN;
CREATE TABLE clocking_event_sources (
  event_id uuid PRIMARY KEY REFERENCES clocking_events(id) ON DELETE RESTRICT,
  channel text NOT NULL CHECK (channel IN ('sms','web','mobile','qr','messenger','nfc','ets')),
  evidence_type text NOT NULL CHECK (evidence_type IN ('manual_claim','qr_token','nfc_scan','device_record')),
  external_reference text,
  provider text,
  provider_message_id text,
  claimed_arrival_at timestamptz,
  device_recorded_at timestamptz,
  clock_integrity_verified boolean NOT NULL DEFAULT false,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (channel <> 'ets' OR evidence_type='device_record'),
  CHECK (channel <> 'qr' OR evidence_type='qr_token'),
  CHECK (channel <> 'nfc' OR evidence_type='nfc_scan'),
  CHECK (channel NOT IN ('sms','web','mobile','messenger') OR evidence_type='manual_claim'),
  CHECK (clock_integrity_verified=false OR evidence_type='device_record'),
  CHECK (provider_message_id IS NULL OR provider IS NOT NULL)
);
CREATE UNIQUE INDEX uq_clocking_source_provider_message
 ON clocking_event_sources(provider,provider_message_id)
 WHERE provider IS NOT NULL AND provider_message_id IS NOT NULL;
CREATE INDEX ix_clocking_event_sources_channel ON clocking_event_sources(channel,created_at DESC);
-- Backfill existing events as evidence with no implied trusted clock attestation.
INSERT INTO clocking_event_sources(event_id,channel,evidence_type,provenance)
SELECT id,
       CASE WHEN method='QR' THEN 'qr' ELSE 'ets' END,
       CASE WHEN method='QR' THEN 'qr_token' ELSE 'device_record' END,
       jsonb_build_object('legacy_backfill',true,'hardware_trust_unverified',true)
FROM clocking_events
ON CONFLICT(event_id) DO NOTHING;
COMMIT;
