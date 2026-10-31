"""Durable immutable event envelopes, bound to their original backend/device."""
import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from .adapters import Reading, normalize_tag
from .config import Config


class Queue:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, origin TEXT NOT NULL, device TEXT NOT NULL,
            payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
            last_error TEXT, backend_event_id TEXT, created REAL NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def enqueue(self, config: Config, reading: Reading) -> str:
        if reading.observed_at.tzinfo is None or reading.observed_at.utcoffset() is None:
            raise ValueError("Reader timestamp must include a timezone")
        message_id = str(uuid4())
        payload = {"message_id": message_id, "race_id": config.race_id,
                   "ring_uid": normalize_tag(reading.tag, config.normalization),
                   "device_recorded_at": reading.observed_at.isoformat(),
                   "offline_buffered": True, "adapter_type": config.adapter,
                   "protocol": config.protocol}
        with self.db:
            self.db.execute("INSERT INTO events(id,origin,device,payload,created) VALUES (?,?,?,?,?)",
                (message_id, config.backend_url.rstrip("/"), config.device_id,
                 json.dumps(payload, sort_keys=True), time.time()))
        return message_id

    def due(self, config: Config, now: float):
        return self.db.execute("""SELECT * FROM events WHERE status='pending'
            AND origin=? AND device=? AND next_attempt<=? ORDER BY created,id LIMIT 100""",
            (config.backend_url.rstrip("/"), config.device_id, now)).fetchall()

    def retry(self, row, reason: str, now: float):
        delay = min(300, 2 ** min(row["attempts"] + 1, 9))
        with self.db:
            self.db.execute("""UPDATE events SET attempts=attempts+1,next_attempt=?,last_error=?
                WHERE id=? AND status='pending'""", (now + delay, reason, row["id"]))

    def acknowledge(self, row, event_id: str):
        with self.db:
            self.db.execute("""UPDATE events SET status='sent',backend_event_id=?,last_error=NULL
                WHERE id=?""", (event_id, row["id"]))

    def reject(self, row, reason: str):
        with self.db:
            self.db.execute("UPDATE events SET status='rejected',last_error=? WHERE id=?",
                            (reason, row["id"]))

    def counts(self):
        return dict(self.db.execute("SELECT status,count(*) FROM events GROUP BY status").fetchall())
