# Universal RFID gateway

One Python 3.11+ application for Windows/Linux laptops and Raspberry Pi OS.
The backend remains FastAPI/PostgreSQL on Render. Hardware communication runs
locally at the loft; it does not run in the cloud API or dashboard browser.

## Supported foundation

- Simulator: queue known tag IDs without hardware or network access.
- USB keyboard emulation: newline-terminated tags into a **focused console**.
  Other keyboard input must not be entered into the console.
- Direct USB HID: optional hidapi userspace transport, explicitly selected
  interface and report format. See the raw HID configuration below.
- USB serial/COM: ASCII lines, newline-terminated, configurable port/baudrate,
  default 8N1. Binary framing, checksums, and vendor commands need a dedicated
  protocol adapter. Install the optional `serial` dependency for this mode.
- Network: TCP ASCII newline client with configured `network_host`,
  `network_port`, and optional `network_timeout` (default 10 seconds).
  Vendor binary protocols still require a dedicated `Adapter` implementation.

Matching frequency does not establish ring/reader compatibility. Test the
actual protocol and emitted IDs before assigning hardware. No hardware model
or frequency is hardcoded. Raspberry Pi physical-reader testing is pending.

## Install

From this directory, create/activate a Python virtual environment, then:

```sh
python -m pip install -e ".[test]"
# For compatible serial readers:
python -m pip install -e ".[serial]"
```

Copy `config.example.json` to ignored `config.local.json`. Fill in the actual
registered `device_id`, active `race_id`, backend origin, protocol label, and
adapter. Relative queue paths are resolved against the configuration directory.
For serial, add `serial_port` (`COM3` on Windows or `/dev/ttyUSB0` on Linux/Pi)
and `baudrate`. The account running the gateway needs access to that port.

`normalization` is explicit: `preserve` trims line endings only; `upper`
uppercases; `hex` accepts hexadecimal characters with optional colon/hyphen
separators and removes those separators. Leading zeros are always retained.
There is no automatic decimal/hex conversion. Register the exact normalized ID
in the backend. Distinct readers/protocols can produce colliding IDs; the pilot
uses globally unique active tag IDs and needs a namespace policy before mixing
incompatible tag namespaces in one installation.

## Register through the administrator API

1. Create the club, member, verified loft, and pigeon as usual.
2. `POST /pigeons/{pigeon_id}/rfid` with `{"uid":"00001234"}`. Ring assignment
   requires an active pigeon/owner and verified loft. Existing active mappings
   are never silently replaced. Guests still use QR under current race rules.
3. `POST /devices` with `loft_id`, a unique `device_identifier`, `reader_adapter`
   (`simulator`, `usb_hid`, `serial`, or declared `network`), and
   `reader_protocol`. One active reader per loft remains the current limit.
   `GET /devices` lists readers owned by the administrator's club participants.
4. `POST /devices/{device_id}/provision` returns the device token once.
5. Register the pigeon in an RFID race, open/activate the race, and set its ID
   in the local gateway config. Match adapter/protocol labels exactly.

Keep credentials out of config, command arguments, source control, screenshots,
and logs. Supply the token through `PIGEON_DEVICE_TOKEN` in the gateway process
environment (a local service manager can inject it). Use a separately provisioned
simulator device during testing. Never simulate against a real race.

## Run

```sh
# Offline simulator; does not require a token or contact the backend:
python -m pigeon_gateway --config config.local.json simulate --tag 00001234
python -m pigeon_gateway --config config.local.json status
python -m pigeon_gateway --config config.local.json diagnostics

# After injecting PIGEON_DEVICE_TOKEN into the process environment:
python -m pigeon_gateway --config config.local.json sync --once
python -m pigeon_gateway --config config.local.json sync

# Capture compatible keyboard/serial hardware and sync in the background:
python -m pigeon_gateway --config config.local.json run
```

Stop with Ctrl+C. Unacknowledged scans remain queued. `sync --once` processes a
batch of at most 100 due events. Continuous synchronization checks every five
seconds; failed deliveries have exponential backoff up to five minutes.

## Delivery and timing contract

SQLite stores each immutable payload before upload, using WAL and full
synchronous commits. Payloads include a UUID `message_id`, original race ID,
normalized `ring_uid`, timezone-aware observation time, and adapter/protocol.
Every event is locally buffered (`offline_buffered=true`). The queue binds it
to its original backend and reader; changing the config cannot redirect old
records or move them into a later race. Use a separate queue/config per reader.

HTTPS certificate verification stays enabled. Redirects are not followed;
environment proxies are not used. Plain HTTP is available only for explicitly
enabled loopback testing (`allow_local_http=true`). No credential is stored in
SQLite. Queue records contain club evidence and require local filesystem access
controls and backups; encryption, signed evidence, automatic retention cleanup,
hardware clock attestation, and tamper resistance are not implemented.

Network failures, invalid acknowledgements, rate limiting and server errors
retain events for retry. Lost responses are retried with identical IDs/payloads;
the backend deduplicates by reader/message. Authentication/authorization failures
retain records and stop the batch. HTTP 404/409/422 quarantine records as
`rejected` for administrator inspection; they are not silently deleted or
rewritten. Late uploads to a closed race are rejected under current API policy.
Do not retry by changing message IDs or backdating into another race.

Reader time is **untrusted evidence**. Server receipt time remains the arrival
used by the backend; offline claims are not automatically backdated. Simulator
provenance is explicit. These events remain pending and never automatically
become official results. Reader registration is a configuration declaration,
not proof that a device or clock is authentic.

## Automatic versus operator capture

Set `capture_mode` to `automatic` only for an installation intended to detect
passages without operator presentation. Its default is `operator`. Simulator
events always use `simulated`, regardless of this setting. Events preserve the
original scan as well as the normalized tag; neither is printed by diagnostics.
Passive diagnostics show configured identity, queue counts/ages, and attempt
counts, with `hardware_connection=not_probed`; they do not claim a reader is
connected. Active connection monitoring is a future milestone.

Open the dashboard's **Live race** view to see first eligible RFID events and
provisional speed rankings refresh automatically. Operator/manual/unknown scans
require review before entering these rankings. Automatic mode is declared by
the configured gateway, not verified by the server. See
`../docs/universal-clocking-status.md` for exact selection and timing rules.

## Tests

```sh
python -m pytest -q
```

CI runs the gateway suite on Windows and Linux. Mock transports exercise
offline/restart, duplicate response recovery, rejection retention, origin/device
binding, and token handling. Backend PostgreSQL integration tests cover
registration, club access, mapping, provenance, replay, and legacy compatibility.
Real USB/serial/Pi/network hardware needs a separate compatibility acceptance run.

## Reader profiles and remaining adapters

See [reader adapter plan](../docs/reader-adapter-plan.md) for the RDM582 /
EM4100/EM4200 reference, configurable `uid_profile` fields, example configuration,
and implemented USB/web QR, ESP32 firmware and remaining hardware acceptance work. QR scans must use the
QR API; never route QR tokens into the RFID queue.

## Raw USB HID

Install `python -m pip install -e ".[hid]"`. Keep `adapter="usb_hid"` and add
a `hid` object to select direct capture; omitting it keeps console input.
Configure the actual integer `vendor_id` and `product_id`, and, if necessary,
`serial_number` and `interface_number`. Selection must match exactly one HID
interface; ambiguous selections fail before reading. Inspect IDs with
`python -c "import hid; print(hid.enumerate())"` locally. No IDs are inferred
from a manufacturer name or radio frequency.

Example shape (replace IDs and layout from your reader documentation):

```json
{
  "vendor_id": 1234,
  "product_id": 5678,
  "interface_number": 0,
  "report_size": 64,
  "format": "ascii_lines",
  "padding_byte": 0
}
```

`ascii_lines` buffers newline-terminated ASCII across reports. `hex_report`
emits an uppercase hex UID per selected report. `boot_keyboard` decodes strict
8-byte US boot keyboard reports, shift, key release and Enter; other keyboard
layouts need a dedicated decoder. Optional `report_id` selects and removes the
first report-ID byte. `payload_offset` and `payload_length` then slice the
remaining report. `padding_byte` removes only configured trailing padding.
UID profiles run afterward and the immutable queue preserves the decoded scan.

The operating system must allow interface access. Windows often reserves
keyboard HID interfaces; use focused keyboard capture for those, or a documented
vendor interface. Linux/Pi may need a narrow vendor/product-specific udev rule.
Do not replace system keyboard drivers or run a global keyboard hook. This
adapter uses hidapi; it is not a new kernel driver, vendor command implementation,
or promise that every proprietary HID report is supported. See upstream
[hidapi Python API](https://trezor.github.io/cython-hidapi/api.html).

HTTP 429 now pauses all pending events for the configured reader/origin until the server's numeric Retry-After deadline (bounded to one hour, default 60 seconds). Payloads and message IDs are retained. Shared API rate-budget settings and browser recovery are documented in `../docs/clocking-reliability.md`.
