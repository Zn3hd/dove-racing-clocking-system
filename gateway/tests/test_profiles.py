import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pigeon_gateway.adapters import NetworkLines, Reading, Simulator
from pigeon_gateway.profiles import UIDProfile
from pigeon_gateway.queue import Queue
from test_gateway import config


@pytest.mark.parametrize("profile,raw,expected", [
    ({"name": "rdm582-site-decimal", "pattern": r"[0-9]{10}"}, "0000123456\r\n", "0000123456"),
    ({"name": "other-hex-reader", "prefix": "UID:", "suffix": ";", "pattern": r"[0-9a-f:]+", "normalization": "hex"}, "UID:00:ab:12;\n", "00AB12"),
    ({"name": "other-text-reader", "normalization": "upper"}, "ring-0001\n", "RING-0001"),
])
def test_profiles_reach_immutable_queue(tmp_path, profile, raw, expected):
    cfg = config(tmp_path, adapter="usb_hid", uid_profile=profile)
    queue = Queue(cfg.queue_path)
    try:
        queue.enqueue(cfg, Reading(raw, datetime.now(timezone.utc)))
        payload = json.loads(queue.due(cfg, 10**12)[0]["payload"])
        assert payload["ring_uid"] == expected
        assert payload["original_scan"] == raw.rstrip("\r\n")
    finally:
        queue.close()


@pytest.mark.parametrize("raw", ["123", "UID:zz;", " UID:00ab;", "UID:00ab", "UID:00ab;extra"])
def test_wrong_framing_is_rejected(raw):
    profile = UIDProfile(prefix="UID:", suffix=";", pattern=r"[0-9a-f]{4}")
    with pytest.raises(ValueError):
        profile.parse(raw)


def test_simulator_cannot_claim_physical_reader(tmp_path):
    cfg = config(tmp_path, adapter="usb_hid", capture_mode="automatic")
    queue = Queue(cfg.queue_path)
    try:
        with pytest.raises(ValueError, match="Simulated"):
            queue.enqueue(cfg, next(Simulator(["0001"]).readings()))
        assert queue.counts() == {}
    finally:
        queue.close()


@pytest.mark.parametrize("complete", [True, False])
def test_network_lines_closes_resources(monkeypatch, complete):
    import socket
    connection = MagicMock()
    connection.__enter__.return_value = connection
    stream = io.StringIO("0001\r\n0002\n" if complete else "0001")
    connection.makefile.return_value = stream
    def connect(address, timeout):
        assert address == ("reader.local", 9000)
        assert timeout == 3
        return connection
    monkeypatch.setattr(socket, "create_connection", connect)
    if complete:
        assert [r.tag.rstrip("\r\n") for r in NetworkLines("reader.local", 9000, 3).readings()] == ["0001", "0002"]
    else:
        with pytest.raises(ValueError, match="Incomplete"):
            list(NetworkLines("reader.local", 9000, 3).readings())
    assert stream.closed
    connection.__exit__.assert_called_once()


@pytest.mark.parametrize("overrides", [
    {"adapter": "network"},
    {"adapter": "network", "network_host": "reader.local", "network_port": 0},
    {"uid_profile": {"normalization": "guess"}},
    {"uid_profile": {"name": ""}},
])
def test_invalid_configuration_fails_before_capture(tmp_path, overrides):
    with pytest.raises(ValueError):
        config(tmp_path, **overrides)
