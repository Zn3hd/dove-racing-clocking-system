"""Optional hidapi transport with explicitly selected report formats.

This is a userspace reader, not an OS kernel driver or vendor protocol guesser.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from .adapters import Adapter, Reading


@dataclass(frozen=True)
class HIDConfig:
    vendor_id: int
    product_id: int
    serial_number: str | None = None
    interface_number: int | None = None
    report_size: int = 64
    report_id: int | None = None
    payload_offset: int = 0
    payload_length: int | None = None
    padding_byte: int | None = None
    format: str = "ascii_lines"

    def __post_init__(self):
        if not all(isinstance(v, int) and 1 <= v <= 65535 for v in (self.vendor_id, self.product_id)):
            raise ValueError("HID vendor_id/product_id must be integers 1-65535")
        if self.format not in ("ascii_lines", "hex_report", "boot_keyboard"):
            raise ValueError("Unsupported HID report format")
        if not 1 <= self.report_size <= 4096 or not 0 <= self.payload_offset < self.report_size:
            raise ValueError("Invalid HID report size/offset")
        if self.payload_length is not None and not 1 <= self.payload_length <= self.report_size - self.payload_offset:
            raise ValueError("Invalid HID payload length")
        for byte in (self.report_id, self.padding_byte):
            if byte is not None and not 0 <= byte <= 255:
                raise ValueError("HID report ID/padding must be bytes")


class ReportDecoder:
    def __init__(self, config: HIDConfig):
        self.config = config
        self.buffer = ""
        self.held = set()

    def feed(self, report: bytes) -> list[str]:
        cfg = self.config
        if len(report) > cfg.report_size:
            raise ValueError("Oversized HID report")
        if cfg.report_id is not None:
            if not report or report[0] != cfg.report_id:
                return []  # Other report IDs on the same interface are not scans.
            report = report[1:]
        end = None if cfg.payload_length is None else cfg.payload_offset + cfg.payload_length
        if end is not None and len(report) < end:
            raise ValueError("Truncated HID payload")
        payload = report[cfg.payload_offset:end]
        if cfg.padding_byte is not None:
            payload = payload.rstrip(bytes([cfg.padding_byte]))
        if cfg.format == "hex_report":
            if not payload:
                raise ValueError("Empty HID payload")
            return [payload.hex().upper()]
        if cfg.format == "boot_keyboard":
            if len(payload) != 8 or payload[1] != 0 or payload[0] & ~0x22:
                raise ValueError("Expected an unmodified or shifted 8-byte boot keyboard report")
            keys = payload[2:]
            if any(key in (1, 2, 3) for key in keys):
                raise ValueError("HID keyboard rollover/error")
            held = {key for key in keys if key}
            text = ""
            shifted = bool(payload[0] & 0x22)
            for key in keys:
                if not key or key in self.held:
                    continue
                if 4 <= key <= 29:
                    char = chr(ord('a') + key - 4)
                    text += char.upper() if shifted else char
                elif 30 <= key <= 39:
                    text += ("!@#$%^&*()" if shifted else "1234567890")[key - 30]
                elif key == 40:
                    text += "\n"
                elif key in (44, 45, 46, 51, 54, 55, 56):
                    normal, shift = {44: (' ', ' '), 45: ('-', '_'), 46: ('=', '+'),
                                     51: (';', ':'), 54: (',', '<'), 55: ('.', '>'), 56: ('/', '?')}[key]
                    text += shift if shifted else normal
                else:
                    raise ValueError("Unsupported key in configured US boot keyboard format")
            self.held = held
        else:
            text = payload.decode("ascii", errors="strict")
        scans = []
        for char in text:
            self.buffer += char
            if len(self.buffer) > 1024:
                raise ValueError("Oversized HID scan")
            if char == '\n':
                scans.append(self.buffer)
                self.buffer = ""
        return scans


def hid_module():
    try:
        import hid
    except ImportError as exc:
        raise RuntimeError("Install the gateway hid extra to use raw USB HID") from exc
    return hid


class RawHID(Adapter):
    def __init__(self, config: HIDConfig):
        self.config = config

    def readings(self):
        hid = hid_module()
        cfg = self.config
        matches = [item for item in hid.enumerate(cfg.vendor_id, cfg.product_id)
                   if (cfg.serial_number is None or item.get('serial_number') == cfg.serial_number)
                   and (cfg.interface_number is None or item.get('interface_number') == cfg.interface_number)]
        if len(matches) != 1:
            raise ValueError("HID selection must match exactly one interface; configure serial/interface")
        device = hid.device()
        try:
            device.open_path(matches[0]['path'])
            decoder = ReportDecoder(cfg)
            while True:
                report = device.read(cfg.report_size, 1000)
                if not report:
                    continue
                for tag in decoder.feed(bytes(report)):
                    yield Reading(tag, datetime.now(timezone.utc))
        finally:
            device.close()
