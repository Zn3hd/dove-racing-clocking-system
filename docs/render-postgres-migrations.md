# Render PostgreSQL deployment (development only)

The Render web service uses `backend` as Root Directory and connects to the
Render PostgreSQL database through the private `DATABASE_URL` environment
variable. Keep all credentials in Render; never commit or paste them in chat.

## One-time startup command change

Once the database is backed up and confirmed to be new/empty, set the Render
**Start Command** to:

```sh
python scripts/run_migrations.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Keep the Build Command as `pip install -r requirements.txt`. This will trigger
a redeployment. Watch the Render logs for `Applied: 001_schema.sql` through
`Applied: 013_rate_limits.sql` and `Migrations complete`. On subsequent
starts it verifies the recorded checksums and skips applied files.

The runner uses a PostgreSQL session advisory lock to prevent simultaneous
migration attempts and records each migration atomically with its SQL changes.
It refuses to run against a schema that already has `roles` but no migration
ledger. Never delete the ledger or edit previously applied SQL migrations.
When changing the schema later, create a new numbered migration and update
the runner's expected migration count.

**Important:** Render's free Postgres and sleeping free web service are not
suitable for production timing, official clocking, or durable race records.
Confirm the `/health` endpoint after redeployment. A healthy API does not
mean official clocking is enabled.

## Recovery

If deployment fails, inspect Render logs; do not repeatedly reset the database.
The runner leaves completed migrations recorded and rolls back a failed file's
SQL transaction. Restore the previous Start Command to bring back the API
without running migrations, then investigate. If a database was initialized
manually, review its schema before deciding how to establish a migration ledger.
