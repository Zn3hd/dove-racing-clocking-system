import io
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from pigeon_gateway.adapters import KeyboardLines, Reading, SerialLines, Simulator, normalize_tag
from pigeon_gateway.config import Config
from pigeon_gateway.queue import Queue
from pigeon_gateway.sync import synchronize
from pigeon_gateway.sync import send_heartbeat


def test_heartbeat_scopes_counts_and_preserves_evidence(tmp_path):
    cfg=config(tmp_path); q=Queue(cfg.queue_path)
    other=config(tmp_path,device_id=str(uuid4()))
    q.enqueue(cfg,Reading('TEST',datetime.now(timezone.utc),simulated=True))
    q.enqueue(other,Reading('OTHER',datetime.now(timezone.utc),simulated=True))
    def handler(request):
        assert request.url.path==f'/devices/{cfg.device_id}/heartbeat'
        assert json.loads(request.content)=={'reader_state':'not_probed','pending_count':1,'rejected_count':0}
        assert request.headers['X-Device-Token']=='private-token'
        return httpx.Response(200,json={'device_id':cfg.device_id,'received_at':'2026-10-31T00:00:00Z'})
    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            assert send_heartbeat(q,cfg,'private-token',client)['heartbeat']=='received'
        assert q.counts()=={'pending':2}
    finally:q.close()


@pytest.mark.parametrize('status',[302,401,429,500])
def test_unconfirmed_heartbeat_does_not_follow_redirect_or_leak_token(tmp_path,status):
    cfg=config(tmp_path);q=Queue(cfg.queue_path)
    try:
        with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(status))) as client:
            result=send_heartbeat(q,cfg,'private-token',client)
        assert result=={'heartbeat':'unconfirmed','http_status':status}
        assert 'private-token' not in str(result)
    finally:q.close()


def config(tmp_path, **overrides):
    return Config(**{'backend_url': 'https://backend.example.test', 'device_id': str(uuid4()),
        'race_id': str(uuid4()), 'protocol': 'test-text-v1', 'queue_path': str(tmp_path / 'queue.sqlite3'),
        **overrides})


def test_normalization_is_explicit_and_preserves_identity():
    assert normalize_tag('00012ab\r\n', 'preserve') == '00012ab'
    assert normalize_tag('00:12-ab', 'hex') == '0012AB'
    assert normalize_tag('tag-a', 'upper') == 'TAG-A'
    for raw in ('', ' ABC', 'ABC ', 'AB\x00C', 'x' * 201):
        with pytest.raises(ValueError):
            normalize_tag(raw, 'preserve')
    with pytest.raises(ValueError):
        normalize_tag('a tag', 'hex')


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:secret@example.com',
    'https://example.com?token=abc', 'https://example.com/path', 'ftp://example.com'])
def test_invalid_or_insecure_origins_are_rejected(tmp_path, url):
    with pytest.raises(ValueError):
        config(tmp_path, backend_url=url)


def test_loopback_http_requires_opt_in(tmp_path):
    with pytest.raises(ValueError):
        config(tmp_path, backend_url='http://127.0.0.1:8000')
    config(tmp_path, backend_url='http://127.0.0.1:8000', allow_local_http=True)


def test_line_adapters_and_simulator():
    assert [r.tag.rstrip('\r\n') for r in KeyboardLines(io.StringIO('0001\n0002\r\n')).readings()] == ['0001', '0002']
    assert next(Simulator(['0001']).readings()).observed_at.tzinfo is not None


def test_serial_adapter_buffers_partial_lines_and_closes(monkeypatch):
    import sys
    from types import SimpleNamespace
    chunks = iter([b'0', b'', b'0', b'1', b'\r', b'\n'])
    closed = []
    class Port:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            closed.append(True)
        def read(self, count):
            return next(chunks)
    def serial_port(port, baudrate, timeout):
        assert (port, baudrate, timeout) == ('test-port', 9600, 1)
        return Port()
    monkeypatch.setitem(sys.modules, 'serial', SimpleNamespace(Serial=serial_port))
    stream = SerialLines('test-port', 9600).readings()
    assert next(stream).tag == '001\r\n'
    stream.close()
    assert closed == [True]


def test_offline_restart_retry_keeps_exact_envelope(tmp_path):
    cfg = config(tmp_path)
    queue = Queue(cfg.queue_path)
    scan = Reading('00001234', datetime.now(timezone.utc))
    queued = queue.enqueue(cfg, scan)
    bodies = []
    def offline(request):
        bodies.append(request.content)
        raise httpx.ConnectError('Offline', request=request)
    now = 100000000000
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert synchronize(queue, cfg, 'test-device-secret', client, now)['retry'] == 1
    queue.close()
    queue = Queue(cfg.queue_path)
    event_id = str(uuid4())
    def online(request):
        bodies.append(request.content)
        assert request.headers['X-Device-Token'] == 'test-device-secret'
        return httpx.Response(202, json={'event_id': event_id, 'status': 'pending',
                                        'official_result_created': False, 'duplicate_request': True})
    with httpx.Client(transport=httpx.MockTransport(online)) as client:
        assert synchronize(queue, cfg, 'test-device-secret', client, now)['sent'] == 0
        assert synchronize(queue, cfg, 'test-device-secret', client, now + 3)['sent'] == 1
        assert synchronize(queue, cfg, 'test-device-secret', client, now + 4)['sent'] == 0
    assert bodies[0] == bodies[1]
    assert json.loads(bodies[1])['message_id'] == queued
    assert json.loads(bodies[1])['ring_uid'] == '00001234'
    assert queue.counts() == {'sent': 1}
    queue.close()


@pytest.mark.parametrize('status,expected', [(401, 'pending'), (403, 'pending'), (404, 'rejected'),
    (409, 'rejected'), (422, 'rejected'), (429, 'pending'), (500, 'pending'), (302, 'pending')])
def test_delivery_failures_retain_evidence(tmp_path, status, expected):
    cfg = config(tmp_path)
    queue = Queue(cfg.queue_path)
    queue.enqueue(cfg, next(Simulator(['001']).readings()))
    def response(request):
        return httpx.Response(status, headers={'Location': 'https://other.example.test'})
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        synchronize(queue, cfg, 'test-token', client, 100000000000)
    assert queue.counts() == {expected: 1}
    assert 'test-token' not in queue.db.execute('SELECT last_error FROM events').fetchone()[0]
    queue.close()


def test_queue_is_bound_to_backend_and_device(tmp_path):
    cfg = config(tmp_path)
    queue = Queue(cfg.queue_path)
    queue.enqueue(cfg, next(Simulator(['001']).readings()))
    other = config(tmp_path, device_id=str(uuid4()))
    assert not queue.due(other, 100000000000)
    other = config(tmp_path, device_id=cfg.device_id, backend_url='https://other.example.test')
    assert not queue.due(other, 100000000000)
    assert len(queue.due(cfg, 100000000000)) == 1
    queue.close()


def test_malformed_acknowledgement_does_not_drop_evidence(tmp_path):
    cfg = config(tmp_path)
    queue = Queue(cfg.queue_path)
    queue.enqueue(cfg, next(Simulator(['001']).readings()))
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(202, json={}))) as client:
        assert synchronize(queue, cfg, 'test-token', client, 100000000000)['retry'] == 1
    assert queue.counts() == {'pending': 1}
    queue.close()


def test_capture_mode_raw_scan_and_safe_diagnostics(tmp_path):
    cfg = config(tmp_path, adapter='usb_hid', capture_mode='automatic', normalization='hex')
    queue = Queue(cfg.queue_path)
    try:
        queue.enqueue(cfg, Reading('00:ab-12', datetime.now(timezone.utc)))
        row = queue.due(cfg, 100000000000)[0]
        payload = json.loads(row['payload'])
        assert payload['ring_uid'] == '00AB12'
        assert payload['original_scan'] == '00:ab-12'
        assert payload['capture_mode'] == 'automatic'
        diagnostic = queue.diagnostics(cfg)
        assert diagnostic['hardware_connection'] == 'not_probed'
        assert diagnostic['queue']['pending']['count'] == 1
        assert '00:ab-12' not in json.dumps(diagnostic)
        simulator_cfg = config(tmp_path, capture_mode='automatic')
        queue.enqueue(simulator_cfg, next(Simulator(['001']).readings()))
        payload = json.loads(queue.due(simulator_cfg, 100000000000)[0]['payload'])
        assert payload['capture_mode'] == 'simulated'
    finally:
        queue.close()


def test_rate_limit_pauses_entire_reader_scope(tmp_path):
    cfg = config(tmp_path)
    queue = Queue(cfg.queue_path)
    try:
        queue.enqueue(cfg, next(Simulator(['001']).readings()))
        queue.enqueue(cfg, next(Simulator(['002']).readings()))
        attempts = []
        def rate_limit(request):
            attempts.append(request)
            return httpx.Response(429, headers={'Retry-After':'60'})
        with httpx.Client(transport=httpx.MockTransport(rate_limit)) as client:
            assert synchronize(queue,cfg,'test-token',client,100000000000)['retry'] == 1
            assert synchronize(queue,cfg,'test-token',client,100000000030)['retry'] == 0
        assert len(attempts) == 1
        assert queue.counts() == {'pending':2}
        assert len(queue.due(cfg,100000000060)) == 2
    finally:
        queue.close()
