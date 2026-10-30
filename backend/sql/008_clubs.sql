-- Club foundation. Existing accounts and races remain valid during transition.
BEGIN;
CREATE TABLE clubs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 name text NOT NULL CHECK (length(trim(name)) >= 2),
 description text,
 created_by uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE club_memberships (
 club_id uuid NOT NULL REFERENCES clubs(id) ON DELETE RESTRICT,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 club_role text NOT NULL CHECK (club_role IN ('admin','member','guest')),
 joined_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (club_id,user_id)
);
CREATE INDEX ix_club_memberships_user ON club_memberships(user_id);
ALTER TABLE races ADD COLUMN club_id uuid REFERENCES clubs(id);
CREATE INDEX ix_races_club_id ON races(club_id);
COMMIT;
