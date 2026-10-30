-- Phase 6F: explicit Facebook Page-scoped Messenger account linking.
BEGIN;
CREATE TABLE messenger_account_links (
  page_id text NOT NULL,
  sender_psid text NOT NULL,
  user_id uuid NOT NULL REFERENCES users(id),
  linked_by uuid NOT NULL REFERENCES users(id),
  linked_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (page_id, sender_psid),
  UNIQUE (page_id, user_id)
);
CREATE INDEX ix_messenger_links_user ON messenger_account_links(user_id);
COMMIT;
