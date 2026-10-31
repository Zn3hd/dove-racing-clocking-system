"""Authenticated delivery with at-least-once retries and stable message IDs."""
import json
import time
from uuid import UUID

import httpx

from .config import Config
from .queue import Queue


def validate_token(token: str):
    if not token or len(token) > 256 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError("Set PIGEON_DEVICE_TOKEN to the device credential")


def synchronize(queue: Queue, config: Config, token: str, client: httpx.Client, now=None, stop=None):
    validate_token(token)
    now = time.time() if now is None else now
    result = {"sent": 0, "retry": 0, "rejected": 0, "auth_blocked": False}
    for row in queue.due(config, now):
        if stop is not None and stop.is_set():
            break
        try:
            response = client.post(f"{row['origin']}/devices/{row['device']}/arrivals",
                json=json.loads(row["payload"]), headers={"X-Device-Token": token},
                follow_redirects=False, timeout=15)
        except httpx.TransportError:
            queue.retry(row, "Network or TLS failure", now)
            result["retry"] += 1
            continue
        if response.status_code in (401, 403):
            queue.retry(row, f"Authorization blocked (HTTP {response.status_code})", now)
            result["auth_blocked"] = True
            break
        if response.status_code == 202:
            try:
                data = response.json()
                event_id = str(UUID(data["event_id"]))
                if data.get("status") != "pending" or data.get("official_result_created") is not False:
                    raise ValueError("Unexpected acknowledgement")
            except (ValueError, KeyError, TypeError):
                queue.retry(row, "Invalid server acknowledgement", now)
                result["retry"] += 1
                continue
            queue.acknowledge(row, event_id)
            result["sent"] += 1
        elif response.status_code in (404, 409, 422):
            queue.reject(row, f"Server validation rejected evidence (HTTP {response.status_code})")
            result["rejected"] += 1
        else:
            # Includes rate limiting, server failures and redirects. Never forward
            # the credential to another origin or delete unacknowledged evidence.
            queue.retry(row, f"Delivery unavailable (HTTP {response.status_code})", now)
            result["retry"] += 1
    return result
