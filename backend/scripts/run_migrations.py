"""Apply SQL migrations once with checksum verification and atomic bookkeeping.

Run before Uvicorn on the Render service. Requires a fresh database or an
existing schema_migrations ledger; do not bootstrap against untracked tables.
"""
import hashlib
import os
import re
from pathlib import Path

import psycopg

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
LOCK_ID = 7462091321


def migration_sql(text: str) -> str:
    # Existing migration files wrap statements in BEGIN; ... COMMIT;.
    # Remove only the outermost statements so our transaction also includes
    # the ledger INSERT; PL/pgSQL BEGIN inside function bodies is untouched.
    text = re.sub(r"(?im)^BEGIN;\s*$", "", text, count=1)
    text = re.sub(r"(?im)^COMMIT;\s*$", "", text, count=1)
    return text


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        raise SystemExit("DATABASE_URL must be a PostgreSQL connection string")
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    paths = sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if len(paths) != 8 or [p.name[:3] for p in paths] != [f"{i:03}" for i in range(1, 9)]:
        raise RuntimeError("Expected ordered migrations 001 through 008")

    with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            # Refuse to claim ownership of an already-created schema that
            # predates the migration ledger.
            ledger_exists = conn.execute(
                "SELECT to_regclass('public.schema_migrations')"
            ).fetchone()[0] is not None
            if not ledger_exists and conn.execute(
                "SELECT to_regclass('public.roles')"
            ).fetchone()[0] is not None:
                raise RuntimeError("Existing schema without migration ledger; manual review required")
            with conn.transaction():
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename text PRIMARY KEY,
                        sha256 text NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )"""
                )
            applied = dict(conn.execute(
                "SELECT filename, sha256 FROM schema_migrations"
            ).fetchall())
            if set(applied) - {p.name for p in paths}:
                raise RuntimeError("Database contains unknown applied migrations")
            missing_seen = False
            for path in paths:
                raw = path.read_text(encoding="utf-8")
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if path.name in applied:
                    if missing_seen:
                        raise RuntimeError("Migration ledger has a gap")
                    if applied[path.name] != digest:
                        raise RuntimeError(f"Migration checksum mismatch: {path.name}")
                    print(f"Verified: {path.name}", flush=True)
                    continue
                missing_seen = True
                print(f"Applying: {path.name}", flush=True)
                with conn.transaction():
                    conn.execute(migration_sql(raw))
                    conn.execute(
                        "INSERT INTO schema_migrations(filename, sha256) VALUES (%s, %s)",
                        (path.name, digest),
                    )
                print(f"Applied: {path.name}", flush=True)
            print("Migrations complete", flush=True)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


if __name__ == "__main__":
    main()
