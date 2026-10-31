import argparse
import json
import os
import sys
import threading
import time

import httpx

from .adapters import KeyboardLines, SerialLines, Simulator, NetworkLines
from .config import Config
from .queue import Queue
from .sync import synchronize, validate_token, send_heartbeat


def sync_worker(config, token, stop):
    queue = Queue(config.queue_path)
    try:
        with httpx.Client(trust_env=False) as client:
            next_heartbeat = 0
            while not stop.is_set():
                if time.monotonic() >= next_heartbeat:
                    print(json.dumps(send_heartbeat(queue, config, token, client)), flush=True)
                    next_heartbeat = time.monotonic() + 30
                result = synchronize(queue, config, token, client, stop=stop)
                if any(result.values()):
                    print(json.dumps(result), flush=True)
                stop.wait(5)
    finally:
        queue.close()


def main():
    parser = argparse.ArgumentParser(description="Pigeon Racing universal RFID evidence gateway")
    parser.add_argument("--config", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    simulator = commands.add_parser("simulate", help="Queue test scans without a reader or network")
    simulator.add_argument("--tag", action="append", required=True)
    commands.add_parser("status", help="Show local queue counts without printing tag IDs")
    commands.add_parser("diagnostics", help="Show configured reader and queue health without probing hardware")
    commands.add_parser("heartbeat", help="Report gateway reachability without creating an arrival")
    sync = commands.add_parser("sync", help="Deliver queued evidence")
    sync.add_argument("--once", action="store_true")
    commands.add_parser("run", help="Capture configured keyboard/serial reader and synchronize")
    args = parser.parse_args()
    queue = None
    stop = threading.Event()
    worker = None
    try:
        config = Config.load(args.config)
        queue = Queue(config.queue_path)
        if args.command == "status":
            print(json.dumps(queue.counts()))
            return
        if args.command == "diagnostics":
            print(json.dumps(queue.diagnostics(config)))
            return
        if args.command == "simulate":
            if config.adapter != "simulator":
                raise ValueError("Use a simulator device/configuration for simulated evidence")
            for reading in Simulator(args.tag).readings():
                queue.enqueue(config, reading)
            print(json.dumps({"queued": len(args.tag)}))
            return
        token = os.environ.get("PIGEON_DEVICE_TOKEN", "")
        if not token:
            raise ValueError("Set PIGEON_DEVICE_TOKEN in the environment; do not put it in configuration files")
        validate_token(token)
        if args.command == 'heartbeat':
            with httpx.Client(trust_env=False) as client:
                print(json.dumps(send_heartbeat(queue, config, token, client)))
            return
        if args.command == "sync" and args.once:
            with httpx.Client(trust_env=False) as client:
                print(json.dumps(synchronize(queue, config, token, client)))
            return
        if args.command == "sync":
            sync_worker(config, token, stop)
            return
        if config.adapter == "usb_hid":
            if config.hid is not None:
                from .hid_reader import HIDConfig, RawHID
                adapter = RawHID(HIDConfig(**config.hid))
            else:
                adapter = KeyboardLines(sys.stdin)
        elif config.adapter == "network":
            adapter = NetworkLines(config.network_host, config.network_port, config.network_timeout)
        elif config.adapter == "serial":
            adapter = SerialLines(config.serial_port, config.baudrate)
        else:
            raise ValueError("Use 'simulate --tag ...' to queue simulator scans")
        worker = threading.Thread(target=sync_worker, args=(config, token, stop), daemon=True)
        worker.start()
        print("Reader ready. Console keyboard capture requires this console to stay focused.", flush=True)
        for reading in adapter.readings():
            queue.enqueue(config, reading)
            print("Scan queued locally.", flush=True)
    except KeyboardInterrupt:
        print("Stopped. Unacknowledged scans remain in the local queue.")
    except (ValueError, OSError, RuntimeError) as exc:
        # Configuration errors do not contain the token; transport errors are
        # deliberately reduced to generic categories by the synchronizer.
        print(f"Gateway error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        stop.set()
        if worker:
            worker.join(timeout=20)
        if queue:
            queue.close()


if __name__ == "__main__":
    main()
