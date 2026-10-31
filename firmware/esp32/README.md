# ESP32 UART evidence gateway

Default target: ESP32 DevKit / ESP32-WROOM-32, 4 MB flash (`esp32dev`).
This firmware reads a **3.3 V TTL UART** ASCII reader; it is not a USB host.
The RDM582 USB reader should use the Python gateway on Windows/Linux/Pi.
Do not connect USB, RS-232 voltage levels or a 5 V signal directly to GPIO.
Check the chosen reader's electrical interface and use an appropriate level
converter when needed. Default reader RX is GPIO16, TX GPIO17, 9600 baud 8N1,
with common ground. RX connects to reader TX. Pins and baud are configurable.

## Provision and build

1. Install PlatformIO Core 6.1.18. From this directory run `pio run`.
   The project pins the ESP32 platform and ArduinoJson library.
2. Copy `config.example.json` to `data/config.json` (ignored by git). Set Wi-Fi,
   backend HTTPS **origin without trailing slash**, provisioned device ID/token,
   race ID, and the actual trusted backend root CA PEM. Do not use `setInsecure`.
   Example credentials intentionally fail validation. Keep this flash/config
   private: it contains Wi-Fi/device credentials and is not encrypted at rest.
3. Register the device through FastAPI with adapter `serial`, matching protocol
   (default `site-ascii-lines-v1`). Assign normalized ring IDs exactly. Use
   capture_mode `operator` until an unattended installation has been checked.
4. With a **new board**, provision LittleFS using `pio run -t uploadfs`, then
   flash firmware using `pio run -t upload`. Select the actual board's port in
   PlatformIO if it cannot be discovered. No board is flashed by the tests.
   **Uploading a filesystem image replaces stored configuration and evidence.**
   Do not run uploadfs on an operating gateway until its evidence is exported.
5. `pio device monitor -b 115200` shows generic capture/delivery state. It never
   prints credentials or tag IDs during ordinary operation. Send newline-ended
   `status` for queue capacity and network state. Wi-Fi reconnect is automatic;
   NTP is needed for certificate validity, never for official arrival timing.

The profile uses `uid_prefix`, `uid_suffix`, `uid_format` (`ascii`, `decimal`,
`hex`), optional exact `uid_length` (0 means variable, up to 200), and
`normalization` (`preserve`, `upper`, `hex`). It preserves leading zeros and
does not guess decimal/hex conversions. Hex mode here accepts contiguous hex;
vendor separators/checksums require a protocol decoder. `terminator` can be 10
(LF) or 13 (CR). Oversized frames are discarded through their terminator so
their tails cannot become fake scans. No RDM582 command or UID width is assumed.

## Evidence and recovery

Each scan is written and flushed to LittleFS, then atomically renamed from
`.tmp` to `.pending` before transmission. Startup recovers complete temporary
JSON and preserves incomplete files as `.corrupt`. Upload retries reuse the
same UUID and payload, bound to the original origin/device/race. Changing the
current origin/device skips older envelopes instead of redirecting them.
Offline/time claims cannot backdate arrivals. The server uses receipt time,
keeps events pending and never creates official results. `simulated=true`
forces adapter `simulator` and capture mode `simulated` and requires a separately
registered simulator device/test race. It cannot claim physical capture.

Only a bounded, valid 202 acknowledgement with pending status, UUID event ID and
`official_result_created=false` marks a record `.sent`. 404/409/422 mark it
`.rejected`; all other responses, redirects and TLS/auth failures retain the
pending payload and back off up to 300 seconds. No automatic deletion occurs.
There is no credential in event files. Rejected evidence must be inspected,
not rewritten with a fresh ID to bypass race rules.

The limit of 128 records includes sent/rejected/corrupt files. Storage failure
or capacity exhaustion latches a capture fault and logs `CAPTURE STOPPED`.
`export` prints filenames and raw evidence JSON over the local USB console;
save that output privately. It excludes config and secrets but includes ring
IDs. After saving acknowledged evidence, `prune-sent CONFIRM` removes only
`.sent` files. Pending/rejected/corrupt evidence is retained. Check capacity
and reboot to clear the fault. Do not silently format the board to recover.

This is a pilot firmware, not a certified racing clock. HTTPS upload can block
for several seconds; the UART buffer is 4096 bytes and high-rate traffic can
overflow it. Hardware acceptance must include actual scan bursts, unplugging,
Wi-Fi loss, power-cut/reboot recovery, invalid certificates, retries and storage
full behavior. Flash-level durability and physical passage detection cannot be
proven by compilation. No secure boot, encrypted flash, OTA, clock attestation,
USB-host support or vendor binary protocol is claimed.
