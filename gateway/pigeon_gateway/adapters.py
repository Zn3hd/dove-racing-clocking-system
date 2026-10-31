"""Line-oriented adapters. Vendor binary protocols need their own adapter."""
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import TextIO


@dataclass(frozen=True)
class Reading:
    tag: str
    observed_at: datetime
    simulated: bool = False


def normalize_tag(raw: str, policy: str) -> str:
    # Trim only line framing. Leading zeros and punctuation are IDs, not noise.
    tag = raw.rstrip("\r\n")
    if policy == "upper":
        tag = tag.upper()
    elif policy == "hex":
        if not re.fullmatch(r"[0-9A-Fa-f]+(?:[:-][0-9A-Fa-f]+)*", tag):
            raise ValueError("Tag does not match the configured hexadecimal format")
        tag = tag.replace(":", "").replace("-", "").upper()
    elif policy != "preserve":
        raise ValueError("Unknown normalization policy")
    if not tag or len(tag) > 200 or not tag.isprintable() or tag != tag.strip():
        raise ValueError("Tag must contain 1–200 printable characters without surrounding whitespace")
    return tag


class Adapter(ABC):
    @abstractmethod
    def readings(self) -> Iterator[Reading]:
        """Connect and yield scans; release resources on generator close."""


class Simulator(Adapter):
    def __init__(self, tags: Iterable[str]):
        self.tags = tags

    def readings(self):
        for tag in self.tags:
            yield Reading(tag, datetime.now(timezone.utc), simulated=True)


class KeyboardLines(Adapter):
    """Focused console input for keyboard-emulation USB readers; not raw HID."""
    def __init__(self, stream: TextIO):
        self.stream = stream

    def readings(self):
        while line := self.stream.readline(1024):
            if len(line) > 1024:
                raise ValueError("Oversized reader line; check the framing configuration")
            yield Reading(line, datetime.now(timezone.utc))


class SerialLines(Adapter):
    def __init__(self, port: str, baudrate: int):
        self.port, self.baudrate = port, baudrate

    def readings(self):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Install the gateway's serial extra to use serial readers") from exc
        with serial.Serial(self.port, self.baudrate, timeout=1) as port:
            buffer = bytearray()
            while True:
                chunk = port.read(1)
                if not chunk:
                    continue
                buffer.extend(chunk)
                if len(buffer) > 1024:
                    raise ValueError("Oversized serial frame; expected newline-terminated ASCII tags")
                if chunk == b"\n":
                    yield Reading(buffer.decode("ascii", errors="strict"), datetime.now(timezone.utc))
                    buffer.clear()


class NetworkLines(Adapter):
    """TCP client for explicitly configured ASCII newline protocols only.

    EOF/timeout fails closed; run under a supervisor to reconnect. No vendor
    discovery, commands, TLS, or binary decoding is implied.
    """
    def __init__(self, host: str, port: int, timeout: float = 10):
        self.host, self.port, self.timeout = host, port, timeout

    def readings(self):
        import socket
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as connection:
            with connection.makefile("r", encoding="ascii", errors="strict", newline="") as stream:
                for reading in KeyboardLines(stream).readings():
                    if not reading.tag.endswith("\n"):
                        raise ValueError("Incomplete network frame")
                    yield reading
