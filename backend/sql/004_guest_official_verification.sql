-- Phase 6: independently recorded physical guest verification.
BEGIN;
CREATE TABLE guest_arrival_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL UNIQUE REFERENCES clocking_events(id),
  verified_by uuid NOT NULL REFERENCES users(id),
  verified_at timestamptz NOT NULL DEFAULT now(),
  ring_number_seen text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('confirmed','rejected')),
  evidence_note text NOT NULL CHECK (length(trim(evidence_note)) >= 12)
);
CREATE INDEX ix_guest_verifications_official ON guest_arrival_verifications(decision,event_id);
COMMIT;
