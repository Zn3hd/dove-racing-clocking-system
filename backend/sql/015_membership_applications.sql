BEGIN;
CREATE TABLE membership_applications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id uuid NOT NULL REFERENCES clubs(id),
  full_name text NOT NULL,
  email text NOT NULL,
  phone text,
  password_hash text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','declined')),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by uuid REFERENCES users(id),
  decision_reason text,
  member_id uuid REFERENCES users(id),
  CHECK ((status='pending' AND reviewed_at IS NULL AND reviewed_by IS NULL AND member_id IS NULL)
    OR (status='approved' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL AND member_id IS NOT NULL)
    OR (status='declined' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL AND member_id IS NULL))
);
CREATE UNIQUE INDEX uq_membership_pending_email ON membership_applications(lower(email))
  WHERE status='pending';
CREATE INDEX ix_membership_applications_club_status ON membership_applications(club_id,status,submitted_at);
COMMIT;
