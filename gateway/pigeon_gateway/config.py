"""Explicit reader configuration; never infer protocol from frequency."""
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID


@dataclass(frozen=True)
class Config:
    backend_url: str
    device_id: str
    race_id: str
    protocol: str
    adapter: str = "simulator"
    normalization: str = "preserve"
    queue_path: str = "gateway-queue.sqlite3"
    serial_port: str | None = None
    baudrate: int = 9600
    allow_local_http: bool = False

    def __post_init__(self):
        url = urlsplit(self.backend_url)
        if (url.username or url.password or url.query or url.fragment or url.path not in ("", "/")
                or not url.hostname):
            raise ValueError("backend_url must be an origin without credentials, query, or path")
        local = self.allow_local_http and url.hostname in ("127.0.0.1", "localhost", "::1")
        if url.scheme != "https" and not (local and url.scheme == "http"):
            raise ValueError("HTTPS required; HTTP is allowed only for explicitly enabled loopback tests")
        UUID(self.device_id)
        UUID(self.race_id)
        if self.adapter not in ("simulator", "usb_hid", "serial"):
            raise ValueError("Unsupported adapter; network readers require a documented protocol adapter")
        if self.normalization not in ("preserve", "upper", "hex"):
            raise ValueError("Unknown tag normalization policy")
        if not self.protocol.strip() or len(self.protocol) > 120:
            raise ValueError("Configure a nonblank protocol label (maximum 120 characters)")
        if self.adapter == "serial" and not self.serial_port:
            raise ValueError("serial_port is required for the serial adapter")
        if not 1 <= self.baudrate <= 4000000:
            raise ValueError("Invalid serial baudrate")

    @classmethod
    def load(cls, path: str):
        source = Path(path).resolve()
        data = json.loads(source.read_text(encoding="utf-8"))
        queue = Path(data.get("queue_path", "gateway-queue.sqlite3"))
        data["queue_path"] = str(queue if queue.is_absolute() else source.parent / queue)
        return cls(**data)
