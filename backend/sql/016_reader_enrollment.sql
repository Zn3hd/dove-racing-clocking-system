BEGIN;
CREATE TABLE reader_enrollments (
 device_id uuid PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 issued_by uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 code_hash text NOT NULL UNIQUE,
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
COMMIT;
