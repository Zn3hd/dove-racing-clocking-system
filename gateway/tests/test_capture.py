import io
from datetime import datetime, timezone
from uuid import uuid4
import httpx
import pytest
from pigeon_gateway.adapters import Reading, KeyboardLines
from pigeon_gateway.capture import capture, ReaderStatus
from pigeon_gateway.config import Config
from pigeon_gateway.queue import Queue
from pigeon_gateway.sync import send_heartbeat


class Stop:
    def __init__(self, attempts=3):self.delays=[];self.attempts=attempts;self.stopped=False
    def is_set(self):return self.stopped
    def wait(self,delay):
        self.delays.append(delay)
        self.stopped=len(self.delays)>=self.attempts
        return self.stopped


def config(tmp_path):
    return Config(backend_url='https://example.test',device_id=str(uuid4()),race_id=str(uuid4()),
        adapter='network',protocol='ascii-line',network_host='127.0.0.1',network_port=9000,
        queue_path=str(tmp_path/'events.sqlite3'))


def test_reconnect_retains_prior_envelopes_and_resets_backoff(tmp_path):
    cfg=config(tmp_path);queue=Queue(cfg.queue_path);status=ReaderStatus();stop=Stop(4)
    class Reader:
        attempts=0
        def readings(self):
            self.attempts+=1
            if self.attempts==3:
                yield Reading('000012',datetime.now(timezone.utc))
            raise OSError('Disconnected with private vendor details')
    reader=Reader();messages=[]
    try:
        prior=queue.enqueue(cfg,Reading('000011',datetime.now(timezone.utc)))
        original=dict(queue.due(cfg,0)[0])
        capture(lambda:reader,queue,cfg,stop,status,notify=messages.append)
        assert stop.delays==[5,10,5,10]
        rows=queue.due(cfg,0)
        assert len(rows)==2 and dict(next(r for r in rows if r['id']==prior))==original
        assert status.snapshot()=='error'
        assert 'private vendor' not in str(messages) and '000012' not in str(messages)
    finally:queue.close()


def test_reconnect_backoff_is_bounded():
    class Broken:
        def readings(self):raise OSError('unavailable')
    stop=Stop(8)
    capture(Broken,None,None,stop,ReaderStatus(),notify=lambda _:None)
    assert stop.delays==[5,10,20,40,60,60,60,60]


def test_keyboard_eof_does_not_reconnect():
    stop=Stop();status=ReaderStatus()
    capture(lambda:KeyboardLines(io.StringIO('')),None,None,stop,status,reconnect=False)
    assert stop.delays==[] and status.snapshot()=='not_probed'


def test_bad_framing_fails_closed_and_closes_stream():
    closed=[]
    class Bad:
        def readings(self):
            try:
                raise ValueError('bad framing')
                yield
            finally:closed.append(True)
    stop=Stop();status=ReaderStatus()
    with pytest.raises(ValueError):capture(Bad,None,None,stop,status)
    assert closed==[True] and stop.delays==[] and status.snapshot()=='error'


def test_stop_closes_reader_without_enqueueing(tmp_path):
    cfg=config(tmp_path);queue=Queue(cfg.queue_path);stop=Stop();closed=[]
    class Reader:
        def readings(self):
            try:
                stop.stopped=True
                yield Reading('000012',datetime.now(timezone.utc))
            finally:closed.append(True)
    try:
        capture(Reader,queue,cfg,stop,ReaderStatus())
        assert closed==[True] and queue.counts()=={}
    finally:queue.close()


def test_heartbeat_reports_capture_error_without_creating_arrival(tmp_path):
    cfg=config(tmp_path);queue=Queue(cfg.queue_path)
    def handler(request):
        import json
        assert request.url.path.endswith('/heartbeat')
        assert json.loads(request.content)['reader_state']=='error'
        return httpx.Response(200,json={'device_id':cfg.device_id,'received_at':'2026-11-07T00:00:00Z'})
    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            assert send_heartbeat(queue,cfg,'test-token',client,'error')['reader_state']=='error'
        assert queue.counts()=={}
    finally:queue.close()
