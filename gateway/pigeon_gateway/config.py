"""Explicit reader configuration; never infer protocol from frequency."""
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
from .profiles import UIDProfile


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
    capture_mode: str = "operator"

    uid_profile: dict | None = None
    network_host: str | None = None
    network_port: int | None = None
    network_timeout: float = 10.0
    hid: dict | None = None

    def parse_uid(self, raw: str) -> str:
        if self.uid_profile is not None:
            return UIDProfile(**self.uid_profile).parse(raw)
        from .adapters import normalize_tag
        return normalize_tag(raw, self.normalization)

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
        if self.adapter not in ("simulator", "usb_hid", "serial", "network"):
            raise ValueError("Unsupported adapter; network readers require a documented protocol adapter")
        if self.uid_profile is not None:
            UIDProfile(**self.uid_profile)
        if self.hid is not None:
            from .hid_reader import HIDConfig
            HIDConfig(**self.hid)
            if self.adapter != "usb_hid":
                raise ValueError("Raw HID configuration requires adapter usb_hid")
        if self.adapter == "network" and (not self.network_host or not isinstance(self.network_port, int) or not 1 <= self.network_port <= 65535):
            raise ValueError("Network adapter requires a host and port 1-65535")
        if not 0 < self.network_timeout <= 300:
            raise ValueError("Network timeout must be between 0 and 300 seconds")
        if self.normalization not in ("preserve", "upper", "hex"):
            raise ValueError("Unknown tag normalization policy")
        if self.capture_mode not in ('operator', 'automatic'):
            raise ValueError("capture_mode must be operator or automatic")
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
