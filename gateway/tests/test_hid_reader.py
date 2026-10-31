from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from pigeon_gateway.hid_reader import HIDConfig, RawHID, ReportDecoder
from pigeon_gateway.queue import Queue
from test_gateway import config


def profile(**kwargs):
    return HIDConfig(vendor_id=123, product_id=456, **kwargs)


def test_ascii_reports_buffer_frames_and_preserve_uid():
    decoder = ReportDecoder(profile(report_id=7, payload_offset=1, padding_byte=0))
    assert decoder.feed(b'\x08ignored') == []
    assert decoder.feed(b'\x07\xff000\x00\x00') == []
    assert decoder.feed(b'\x07\xff012\r\nnext\n\x00') == ['000012\r\n', 'next\n']


def test_binary_reports_require_explicit_slice():
    decoder = ReportDecoder(profile(format='hex_report', report_id=2, payload_offset=1, payload_length=4))
    assert decoder.feed(bytes([2, 99, 0, 0, 171, 18, 88])) == ['0000AB12']
    with pytest.raises(ValueError, match='Truncated'):
        decoder.feed(bytes([2, 99, 0]))


def boot(*keys, modifier=0):
    return bytes([modifier, 0, *keys, *([0] * (6 - len(keys)))])


def test_boot_keyboard_suppresses_held_keys_but_accepts_repeated_digits():
    decoder = ReportDecoder(profile(format='boot_keyboard', report_size=8))
    assert decoder.feed(boot(39)) == []  # 0
    assert decoder.feed(boot(39)) == []  # held, not a second 0
    assert decoder.feed(boot()) == []
    assert decoder.feed(boot(39)) == []
    decoder.feed(boot())
    decoder.feed(boot(4, modifier=2))  # A
    decoder.feed(boot())
    assert decoder.feed(boot(40)) == ['00A\n']
    with pytest.raises(ValueError, match='rollover'):
        decoder.feed(boot(1))
    with pytest.raises(ValueError):
        decoder.feed(boot(4, modifier=1))  # Ctrl+A is never an ID


def test_oversized_and_non_ascii_frames_fail_closed():
    decoder = ReportDecoder(profile())
    for _ in range(16):
        decoder.feed(b'a' * 64)
    with pytest.raises(ValueError, match='Oversized'):
        decoder.feed(b'b')
    with pytest.raises(UnicodeDecodeError):
        ReportDecoder(profile()).feed(b'\xff')


def test_raw_hid_selects_one_interface_and_closes(monkeypatch, tmp_path):
    import json
    import sys
    reports = iter([[], list(b'000012\n')])
    closed = []
    class Device:
        def open_path(self, path): assert path == b'reader-two'
        def read(self, size, timeout):
            assert (size, timeout) == (64, 1000)
            return next(reports)
        def close(self): closed.append(True)
    devices = [{'path': b'reader-one', 'interface_number': 0},
               {'path': b'reader-two', 'interface_number': 1}]
    monkeypatch.setitem(sys.modules, 'hid', SimpleNamespace(enumerate=lambda *args: devices, device=Device))
    with pytest.raises(ValueError, match='exactly one'):
        next(RawHID(profile()).readings())
    stream = RawHID(profile(interface_number=1)).readings()
    cfg = config(tmp_path, adapter='usb_hid', hid={'vendor_id': 123, 'product_id': 456, 'interface_number': 1})
    queue = Queue(cfg.queue_path)
    try:
        reading = next(stream)
        assert reading.observed_at.tzinfo == timezone.utc
        queue.enqueue(cfg, reading)
        assert json.loads(queue.due(cfg, 10**12)[0]['payload'])['ring_uid'] == '000012'
    finally:
        stream.close()
        queue.close()
    assert closed == [True]


@pytest.mark.parametrize('overrides', [
    {'vendor_id': 0}, {'format': 'guess'}, {'report_size': 0},
    {'payload_offset': 65}, {'payload_length': 100}, {'report_id': 256},
])
def test_invalid_hid_profiles(overrides):
    with pytest.raises(ValueError):
        HIDConfig(**{'vendor_id': 123, 'product_id': 456, **overrides})
