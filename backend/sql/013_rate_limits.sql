BEGIN;
CREATE TABLE request_rate_buckets (
 scope text NOT NULL, identity_hash text NOT NULL, bucket bigint NOT NULL,
 attempts bigint NOT NULL CHECK (attempts>0),
 PRIMARY KEY(scope,identity_hash,bucket)
);
CREATE INDEX ix_request_rate_bucket_cleanup ON request_rate_buckets(bucket);
COMMIT;
