-- Dove Racing V1: initial PostgreSQL schema (development migration).
-- Apply once to a NEW database. Requires PostgreSQL 14+.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE roles (
  code text PRIMARY KEY CHECK (code IN ('chairman','president','member','guest'))
);
INSERT INTO roles(code) VALUES ('chairman'),('president'),('member'),('guest');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_code text NOT NULL REFERENCES roles(code),
  full_name text NOT NULL,
  email text UNIQUE NOT NULL,
  phone text,
  password_hash text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','inactive')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lofts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE REFERENCES users(id),
  name text NOT NULL,
  latitude numeric(10,7) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude numeric(10,7) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  verified_at timestamptz,
  verified_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pigeons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loft_id uuid NOT NULL REFERENCES lofts(id),
  official_ring_number text NOT NULL UNIQUE,
  name text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired','disqualified'))
);

CREATE TABLE rfid_rings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pigeon_id uuid NOT NULL REFERENCES pigeons(id),
  uid text NOT NULL,
  activated_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  CHECK (revoked_at IS NULL OR revoked_at >= activated_at)
);
CREATE UNIQUE INDEX uq_active_rfid_uid ON rfid_rings(uid) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_active_rfid_pigeon ON rfid_rings(pigeon_id) WHERE revoked_at IS NULL;

CREATE TABLE devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loft_id uuid NOT NULL REFERENCES lofts(id),
  device_identifier text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  last_seen_at timestamptz
);
CREATE UNIQUE INDEX uq_active_device_per_loft ON devices(loft_id) WHERE status='active';

CREATE TABLE category_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  active boolean NOT NULL DEFAULT true
);

CREATE TABLE races (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  release_latitude numeric(10,7) NOT NULL CHECK (release_latitude BETWEEN -90 AND 90),
  release_longitude numeric(10,7) NOT NULL CHECK (release_longitude BETWEEN -180 AND 180),
  scheduled_release_at timestamptz,
  actual_release_at timestamptz,
  minimum_speed_mpm numeric(12,4) NOT NULL DEFAULT 500 CHECK (minimum_speed_mpm >= 0),
  display_speed_unit text NOT NULL DEFAULT 'm/min' CHECK (display_speed_unit IN ('m/min','m/s','km/h')),
  guest_ranking_mode text NOT NULL DEFAULT 'separate' CHECK (guest_ranking_mode IN ('separate','combined')),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','active','closed','finalized')),
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE race_categories (
  race_id uuid NOT NULL REFERENCES races(id),
  category_id uuid NOT NULL REFERENCES category_definitions(id),
  PRIMARY KEY (race_id,category_id)
);

CREATE TABLE race_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id uuid NOT NULL REFERENCES races(id),
  pigeon_id uuid NOT NULL REFERENCES pigeons(id),
  loft_id uuid NOT NULL REFERENCES lofts(id),
  -- Immutable registration-time coordinate snapshot.
  loft_latitude numeric(10,7) NOT NULL CHECK (loft_latitude BETWEEN -90 AND 90),
  loft_longitude numeric(10,7) NOT NULL CHECK (loft_longitude BETWEEN -180 AND 180),
  distance_meters numeric(15,3) NOT NULL CHECK (distance_meters > 0),
  expected_method text NOT NULL CHECK (expected_method IN ('RFID','QR')),
  status text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','withdrawn','disqualified')),
  registered_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(race_id,pigeon_id),
  UNIQUE(id,race_id)
);
CREATE INDEX ix_race_entries_race ON race_entries(race_id);

CREATE TABLE entry_categories (
  entry_id uuid NOT NULL REFERENCES race_entries(id),
  race_id uuid NOT NULL,
  category_id uuid NOT NULL,
  PRIMARY KEY (entry_id,category_id),
  FOREIGN KEY (entry_id,race_id) REFERENCES race_entries(id,race_id),
  FOREIGN KEY (race_id,category_id) REFERENCES race_categories(race_id,category_id)
);

-- Only opaque hashes of QR secrets are stored, never the secret printed on a sticker.
CREATE TABLE qr_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pigeon_id uuid REFERENCES pigeons(id),
  race_id uuid REFERENCES races(id),
  loft_id uuid REFERENCES lofts(id),
  token_hash text NOT NULL UNIQUE,
  purpose text NOT NULL CHECK (purpose IN ('clocking','profile','race_view','loft_view')),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  revoked_at timestamptz,
  CHECK (num_nonnulls(pigeon_id,race_id,loft_id) >= 1)
);
CREATE INDEX ix_qr_tokens_pigeon ON qr_tokens(pigeon_id);

CREATE TABLE clocking_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_id uuid NOT NULL REFERENCES race_entries(id),
  method text NOT NULL CHECK (method IN ('RFID','QR')),
  device_id uuid REFERENCES devices(id),
  qr_token_id uuid REFERENCES qr_tokens(id),
  submitted_by uuid REFERENCES users(id),
  idempotency_key text UNIQUE,
  recorded_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','valid','invalid')),
  rejection_reason text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK ((method='RFID' AND device_id IS NOT NULL AND qr_token_id IS NULL)
      OR (method='QR' AND qr_token_id IS NOT NULL AND device_id IS NULL AND submitted_by IS NOT NULL))
);
CREATE INDEX ix_clocking_events_entry_time ON clocking_events(entry_id,recorded_at);

CREATE TABLE clocking_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES clocking_events(id),
  reviewed_by uuid NOT NULL REFERENCES users(id),
  decision text NOT NULL CHECK (decision IN ('approve','reject')),
  reason text NOT NULL,
  reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE race_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_id uuid NOT NULL UNIQUE REFERENCES race_entries(id),
  accepted_event_id uuid NOT NULL UNIQUE REFERENCES clocking_events(id),
  arrival_at timestamptz NOT NULL,
  flight_duration_seconds numeric(15,3) NOT NULL CHECK (flight_duration_seconds > 0),
  distance_meters numeric(15,3) NOT NULL CHECK (distance_meters > 0),
  speed_mpm numeric(15,5) NOT NULL CHECK (speed_mpm > 0),
  qualifying_status text NOT NULL CHECK (qualifying_status IN ('qualified','below_minimum')),
  verification_status text NOT NULL DEFAULT 'provisional' CHECK (verification_status IN ('provisional','approved')),
  finalized_at timestamptz
);

CREATE TABLE audit_logs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  before_state jsonb,
  after_state jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_entity ON audit_logs(entity_type,entity_id,created_at DESC);

-- No UPDATE/DELETE privilege for ordinary API roles should be granted on clocking_events or audit_logs.
-- Service-layer transactions must verify ownership, race state, QR purpose/expiry,
-- cross-table entry/device/QR consistency, and prevent finalized-result mutation.
COMMIT;
