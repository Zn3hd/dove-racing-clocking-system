# Reader profiles and adapter roadmap

## Initial hardware reference

Use the RDM582 USB dual-frequency reader with 125 kHz EM4100/EM4200 pigeon
rings as the initial candidate supplied by the project owner. This is a reference,
not a hardware allowlist or a verified compatibility claim. No physical reader
or ring has been tested here. Confirm the exact purchased variant supports those
chips and capture its actual output before assigning rings. A shared frequency
alone is insufficient. No manufacturer-specific driver or binary command set
is assumed.

`gateway/config.rdm582.example.json` illustrates keyboard-emulation operation.
Its ten-digit decimal format is a site configuration EXAMPLE, not an asserted
RDM582 specification. Adjust prefix, suffix, pattern, and normalization from real
scan samples. Other decimal, hex, and text readers use the same configurable
`uid_profile`; omit it to retain legacy normalization. Profile names never select
parsing automatically. Leading zeros are retained; decimal/hex conversion and
UID namespace merging are deliberately absent. Register the normalized identity
exactly. Changing profiles must not rewrite queued evidence or existing mappings.

## Adapter boundaries

| Input | Current implementation | Next acceptance work |
| --- | --- | --- |
| USB RFID HID keyboard | Focused console, newline scans | Verify actual reader suffix and repeated scans; raw HID transport supports configured ASCII, hex and US boot keyboard reports; verify OS access and actual layout |
| Serial / USB COM | ASCII newline, configurable port/baud, 8N1 | Add a dedicated framed/checksummed decoder for binary vendor protocols; test hardware disconnects |
| Network | Explicit TCP ASCII newline client, bounded frames and timeout | Verify documented reader protocol; TLS/vendor commands require dedicated adapters |
| Raspberry Pi | Same Python gateway, keyboard/serial/network | Physical reader permissions, service restart, offline/reconnect and power loss tests |
| ESP32 | Buildable UART firmware with TLS, LittleFS evidence, UUID retries and forced simulator labeling | Flash/configure real hardware; test reconnect, power loss, burst throughput and capacity |
| USB QR keyboard | Guest scan page submits keyboard scans through QR API with stable session retries | Verify scanner Enter suffix; never submit QR text as `ring_uid` |
| Web QR | Guest camera page with local jsQR decoding, entry matching, auth and camera lifecycle controls | Test real phones, camera lighting and live guest/token scenarios |
| Simulator | Explicit simulated readings and simulator configuration | Separate test devices/races; simulated readings rejected under physical configurations |

Network capture is a TCP client, not an open listener. Only configure a trusted
local reader endpoint: this adapter has no transport encryption or device
attestation. EOF ends capture; timeout/connection failure exits with queued
evidence retained. A supervisor may restart it; automatic reconnect is not yet
implemented. Vendor binary protocols must implement `Adapter.readings()` rather
than being guessed from frequency or product name.

See [QR scanning](qr-scanning.md), [ESP32 setup](../firmware/esp32/README.md)
and [raw HID setup](../gateway/README.md#raw-usb-hid) for operating instructions.
QR tokens remain outside the RFID evidence queue. QR source metadata is
operator-declared, not hardware attestation; simulator markers are unchanged.

## Trust contract

FastAPI, existing device registration, adapter/protocol matching and immutable
SQLite envelopes are preserved. All gateway uploads remain pending evidence;
server receipt time is authoritative and reader/offline timestamps remain
untrusted. Simulator provenance is retained even if capture_mode is automatic,
and a simulated Reading cannot be queued under a physical adapter. This is a
software safeguard, not hardware attestation: a modified client can still lie.
Human review does not create or certify official results. No new automatic
finalization or backdating path is introduced.

## Validation

Gateway tests cover three reader profiles (decimal, framed hex, text), invalid
framing/configuration, raw-scan retention, simulator misconfiguration and mocked
network resource cleanup and raw HID report decoding/selection, alongside the existing offline/retry suite. Browser tests use a generated QR image and mock camera/API; ESP32 firmware is compile-checked. Physical
RDM582, EM4100/EM4200, serial, network, Pi, ESP32 and camera acceptance remain
pending. No deployment is performed by this change.
