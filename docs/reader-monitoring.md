# Reader setup and live gateway monitoring

Apply migration `014_reader_monitoring.sql` with the existing migration runner before running this revision. This work does not apply migrations to Render or deploy code.

In **Race operations**, register the reader against the participant's loft using its actual adapter and documented protocol. The existing one-active-reader-per-loft restriction remains. Provision its credential, copy the one-time value privately into `PIGEON_DEVICE_TOKEN` on the gateway host, and close the dialog to clear it. Rotation immediately invalidates the old token; revocation blocks both heartbeat and arrival ingestion. Both actions are audited and club-authorized. Tokens and token hashes are absent from device lists and configuration previews.

Select a reader and race to prepare non-secret JSON for `gateway/config.local.json`. Configure the actual local serial port/baud rate or network host/port before running. Default capture is operator-assisted; only configure automatic capture after validating the physical reader installation. Simulator readings remain simulated evidence. The browser does not discover or connect to USB devices.

Run from the gateway installation:

```sh
python -m pigeon_gateway --config config.local.json heartbeat
python -m pigeon_gateway --config config.local.json diagnostics
python -m pigeon_gateway --config config.local.json run
```

For simulator testing, use `simulate --tag TEST-ID`, followed by `sync` (continuous) or `sync --once`. Continuous run/sync sends a heartbeat about every 30 seconds. One-shot sync does not start monitoring; use the heartbeat command separately. Heartbeats report queue counts only for the configured backend and device, without ring IDs, raw scans or credentials. Network failures do not discard evidence. Transport redirects are never followed with the device credential. Heartbeat failure is reported independently of arrival synchronization.

The dashboard polls every 15 seconds while Race operations is visible. Server receipt time determines heartbeat freshness: **recent** means within 90 seconds; **stale** means older; **never_seen**, **unprovisioned**, **revoked** and **inactive** are distinct states. A failed dashboard request warns that displayed data may be stale. Queue counts are self-reported snapshots and may lag. Last accepted arrival is displayed separately and is never advanced by a heartbeat.

The Python gateway currently reports **not_probed** for hardware state. A recent heartbeat proves gateway-to-server communication only. It cannot prove a USB antenna is connected, detect every hardware failure, attest timestamps, or establish an official arrival. Hardware-specific diagnostics and physical-reader acceptance tests remain necessary. Other clients may explicitly report waiting/error, but these remain untrusted reports, not hardware attestation.

`POST /devices/{id}/heartbeat` requires the active device token and enforces a shared per-device budget (default 6/minute; `DEVICE_HEARTBEAT_DEVICE_LIMIT`) plus the existing device IP budget. Payload queue counts must be bounded nonnegative integers. Heartbeats use server timestamps and cannot create clocking events. Registration, provisioning, revocation and listing retain existing administrator/club isolation. Rotation clears the prior heartbeat snapshot so a new credential must establish reachability again.

Local verification covers PostgreSQL authentication/isolation, freshness, rotation/revocation, input validation and rate limits; gateway count isolation, redirect/error behavior and evidence preservation; and a real Chromium/FastAPI/PostgreSQL workflow for registration, private token display/clearing, config preview, heartbeat and revocation, followed by the QR arrival/review workflow. Physical reader compatibility and production migration remain separate acceptance steps.
