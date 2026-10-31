"""Explicit text profiles; hardware names never select parsing implicitly."""
from dataclasses import dataclass
import re
from .adapters import normalize_tag


@dataclass(frozen=True)
class UIDProfile:
    name: str = "generic"
    prefix: str = ""
    suffix: str = ""
    pattern: str = r"[!-~]{1,200}"
    normalization: str = "preserve"

    def __post_init__(self):
        if not self.name.strip() or len(self.name) > 120:
            raise ValueError("Profile name must contain 1-120 characters")
        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise ValueError("Invalid UID pattern") from exc
        if self.normalization not in ("preserve", "upper", "hex"):
            raise ValueError("Unknown profile normalization")

    def parse(self, raw: str) -> str:
        if len(raw) > 1024:
            raise ValueError("Oversized scan")
        value = raw.rstrip("\r\n")
        if not value.startswith(self.prefix) or not value.endswith(self.suffix):
            raise ValueError("Scan does not match configured framing")
        value = value[len(self.prefix):]
        if self.suffix:
            value = value[:-len(self.suffix)]
        if re.fullmatch(self.pattern, value) is None:
            raise ValueError("Scan does not match configured UID format")
        return normalize_tag(value, self.normalization)
