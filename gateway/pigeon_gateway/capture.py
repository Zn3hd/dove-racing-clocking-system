"""Reconnect transport failures without discarding or rewriting stored evidence."""
from threading import Lock


class ReaderStatus:
    def __init__(self):
        self._lock = Lock()
        self._state = 'not_probed'

    def set(self, value):
        if value not in ('not_probed', 'waiting', 'error'):
            raise ValueError('Unknown reader state')
        with self._lock:
            self._state = value

    def snapshot(self):
        with self._lock:
            return self._state


def capture(factory, queue, config, stop, status, *, reconnect=True, notify=print):
    delay = 5
    while not stop.is_set():
        readings = None
        try:
            readings = factory().readings()
            for reading in readings:
                if stop.is_set():
                    return
                queue.enqueue(config, reading)
                status.set('waiting')
                delay = 5
                notify('Scan queued locally.')
            if not reconnect:
                return  # Console EOF must not become a reconnect hot loop.
            raise OSError('Reader stream ended')
        except OSError:
            status.set('error')
            if not reconnect:
                raise
        except (ValueError, RuntimeError):
            status.set('error')
            raise  # Framing/configuration failures require operator intervention.
        finally:
            if readings is not None:
                readings.close()
        notify(f'Reader unavailable. Retrying in {delay} seconds; queued evidence retained.')
        if stop.wait(delay):
            return
        delay = min(60, delay * 2)
