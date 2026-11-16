# Mobile RFID simulator pilot

Initial simulator implementation: 16 November 2026. The later
[owner reader milestone](mobile-owner-reader-guide.md) supersedes this checkpoint's
statements about missing enrollment, keyboard capture, heartbeat and export/cleanup.
Its original simulator APK remains preserved for reproducibility. Physical reader
acceptance is still pending.

## Available functionality

The Flutter app has an administrator-only **RFID simulator pilot** screen on
Android/iOS targets. It is hidden from the read-only web demo and member accounts.
Platform visibility does not establish iPhone build or hardware support.

Synthetic scans commit to SQLite before upload. The worker uses the existing
device-authenticated arrival API and retains receipt/rejection history. This is
a foreground test tool, not an automatic loft clock.

## Test setup

Use a dedicated test loft, simulator device and test race on an authorized test
backend. Prefer staging. The pilot UI accepts only the HTTPS backend origin
selected at build time. Loopback HTTP is enabled only by the separate test harness.

1. Create the member, verify their loft and register the pigeon/ring ID.
2. Register a **separate simulator device** for that loft: adapter `simulator`,
   protocol `mobile-simulator-v1`. Do not repurpose an operational reader. The
   backend currently permits one active reader per loft.
3. Provision its credential privately. Keep it out of chat, screenshots, public
   QR labels, source control and build arguments.
4. Open/register/release a test race with an RFID entry for this pigeon.
   Very early scans can legitimately be flagged for impossible speed; do not
   backdate a real race to bypass validation.
5. Sign in as an authorized chairman/president and open **RFID simulator pilot**.
6. Enter the device UUID, race UUID and device credential; confirm test resources,
   then choose **Open pilot queue**.
7. Enter the exact synthetic ring ID and choose **Save simulated scan**.
8. Choose **Start foreground upload**. Pending scans are attempted automatically
   while the page stays open in the foreground. New scans join that same queue.

Leading zeros are preserved. This screen cannot declare physical automatic or
operator capture. Backend validation, simulation labeling and official guards apply.

## Status and recovery

- **Saved on phone:** committed locally, no acknowledged receipt yet.
- **Received:** server acknowledged pending evidence; not proof of physical
  arrival, review approval or an official result.
- **Rejected:** HTTP 404/409/422; retained for inspection, never rewritten under a
  fresh ID to bypass validation.
- Network/TLS failures, redirects, server errors and invalid/oversized receipts
  retain the exact envelope and retry with bounded exponential backoff.
- HTTP 429 pauses the selected scope for a bounded Retry-After interval and
  survives restart. Re-entering credentials does not bypass rate limits.
- HTTP 401/403 pauses uploads. Correct the credential, close/reopen setup and
  explicitly enter it to resume. A blank credential field reuses secure storage
  but does not clear an authorization pause.

The screen shows scoped counts and recent safe receipt/rejection details. Reader
heartbeat telemetry and physical connection health are not included yet.

## Identity, storage and lifecycle

Every record stays bound to its original signed-in account, backend, device and
race. Reopen with the same assignment to recover it; changing setup cannot move
it. SQLite triggers reject updates to envelope identity/content. This does not
provide tamper resistance against someone controlling the phone.

Device credentials use Flutter secure storage and never enter queue records.
Account JWTs and device tokens have separate lifecycles. Forgetting a local
credential does not revoke it on the server or erase evidence. Use the existing
administrator device revocation/rotation operation when needed.

The evidence database is not encrypted by this feature. Use device access
protection. Local/CI Android builds disable app backup and cleartext networking;
iOS backup/privacy policy still needs native platform and device acceptance work.
There is no evidence export, pruning or retention cleanup yet. The global cap of
10,000 records includes received/rejected evidence; reaching it stops capture.
Do not uninstall or clear app data as a recovery procedure without preserving
required evidence through a reviewed support process.

Leaving the page stops its worker. Screen lock/backgrounding stops scheduled
uploads. An in-flight request may already have committed; stable IDs recover its
receipt. Restart requires explicit setup/start. No USB/Bluetooth adapter,
background service, boot startup or unattended physical capture is included.

Speed still uses server receipt time. Offline observation time is untrusted.
New uploads after closure are rejected; exact received-message replays can
recover receipts. Official finalization remains disabled.

## Verification

Local analysis passed with the same lint rules as generated builds. The normal
Flutter suite passed 50 tests, with the one opt-in live test skipped. The final
live harness passed separately in 21.57 seconds; its report is
`backend/.pytest-tmp-mobile-live-bounded-20261116/results.xml`. These are software
tests on Windows, not physical Android/iPhone/reader acceptance.

In `mobile/`, run `flutter pub get`, `flutter analyze`, then `flutter test`.
Tests cover real SQLite file reopen/recovery, immutable envelopes, account/race
isolation, capacity, lost acknowledgements, token/rate pauses, rejection,
malformed/oversized receipts and concurrent-worker exclusion.

Windows persistence tests use the installed `winsqlite3` OS library through the
package's documented build-hook configuration. Android/iOS use native sqflite;
other desktop test platforms use the normal package test library.

The opt-in harness `backend/browser_tests/mobile_live.py` requires backend and
browser-test Python dependencies, Flutter dependencies and the existing disposable
localhost `pigeon_qr_test` PostgreSQL server. Set `QR_AUDIT_DATABASE_URL` privately
to that test server and optionally `MOBILE_FLUTTER_EXECUTABLE` to the SDK command.
From `backend/`:

```sh
python -m pytest -q browser_tests/mobile_live.py --basetemp=.pytest-tmp-mobile-live
```

It creates/drops its own database, applies migrations, creates synthetic API
resources and runs Flutter's actual queue/HTTP worker. After a real server commit,
it loses the acknowledgement, reopens/retries, and verifies one backend event,
one message and no official results. The standalone Flutter live case is skipped
unless the harness provides its environment. Never use production infrastructure.

Mobile CI includes the integration job and normal analysis/tests/APK compilation.
Local results do not establish a successful GitHub run or a Render deployment.

## Build artifacts — 16 November 2026

The isolated Android ARM64 debug build succeeded, with all 50 mobile tests passing
and the opt-in live case skipped inside the build helper. APK signature verified;
packaged settings confirm INTERNET permission, backup disabled and cleartext
networking disabled. The minimum SDK is 24 (Android 7.0), target/compile SDK 36.
Package ID remains `com.example.dove_racing_mobile`, version 0.1.0/code 1; this is
debug signing and not a store-distribution identity. Flutter engine target is
ARM64; other dependency ABIs in the package do not establish other engine support.

- Preserved test artifact: `dist/android/pigeon-racing-rfid-simulator-20261116-arm64.apk`.
- Latest helper artifact: `dist/android/pigeon-racing-debug-arm64.apk`.
- Size: 86,669,707 bytes.
- SHA-256: `023a93546f7caf14d7da8897ef8420a562db0d4ecd29ee290baaa86fb5036fd8`.

The existing read-only JavaScript web preview also compiled successfully from an
isolated scaffold. Its dry-run warnings identify existing secure-storage web
dependencies as incompatible with WebAssembly; no Wasm support is claimed. Native
build warnings about SDK XML/tool versions and obsolete Java source/target levels
did not block compilation. These builds do not prove physical phone behavior.

## Next acceptance

Choose an exact reader/ring pair and pilot phone. Validate protocol, power and
passage detection before adding an adapter. Owner enrollment, background capture,
heartbeat reporting, retention/export, iOS build/device work and Surigao physical
acceptance remain subsequent milestones. See the [full plan](mobile-rfid-plan.md).
