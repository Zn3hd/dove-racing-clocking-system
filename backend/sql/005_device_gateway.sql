-- Phase 6B: prototype gateway credentials and replay-safe messages.
BEGIN;
CREATE TABLE device_gateway_credentials (
 device_id uuid PRIMARY KEY REFERENCES devices(id),
 secret_hash text NOT NULL,
 provisioned_by uuid NOT NULL REFERENCES users(id),
 provisioned_at timestamptz NOT NULL DEFAULT now(),
 revoked_at timestamptz
);
CREATE TABLE device_gateway_messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 device_id uuid NOT NULL REFERENCES devices(id),
 message_id uuid NOT NULL,
 payload_hash text NOT NULL,
 event_id uuid REFERENCES clocking_events(id),
 received_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(device_id,message_id)
);
COMMIT;
