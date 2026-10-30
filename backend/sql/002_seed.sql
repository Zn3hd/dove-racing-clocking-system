-- Safe example category definitions; no personal or credential data.
INSERT INTO category_definitions(name) VALUES
  ('Open'), ('Young Bird'), ('Old Bird')
ON CONFLICT (name) DO NOTHING;
