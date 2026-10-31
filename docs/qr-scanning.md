# Guest USB and camera QR clocking

Open `/dashboard/scan.html` on the same FastAPI host; the dashboard sign-in page
links to it. Sign in with a **guest** account. Only that guest's released,
active QR entries are listed. Existing ownership, club membership, expected
method, race/release, token expiry/revocation and review rules remain enforced
by FastAPI, not by the page alone. The administrator dashboard is unchanged.

## Scan methods

- USB QR keyboard scanner: choose an entry, focus the Clocking QR field and
  scan. Configure the scanner to type the QR text followed by Enter. USB
  proprietary binary-report QR devices need their own decoder; the new page
  supports keyboard-emulation scanners.
- Phone/laptop camera: choose Use camera and grant camera access over HTTPS.
  The vendored jsQR 1.4.0 library decodes frames locally, including in browsers
  without BarcodeDetector. No image is uploaded. Only one code is captured;
  the camera stops after detection, signout, page hide or Stop camera. A denied
  permission leaves USB/paste submission available.
- Paste: choose Paste clocking token and submit the club-issued token.

The administrator's existing `POST /clocking/qr/tokens` response now includes a
`qr_payload` string, ready to encode as a QR label with a local QR generator:

```json
{"version":1,"entry_id":"<entry UUID>","token":"<issued clocking token>"}
```

Existing QR labels encoding only the raw URL-safe clocking token still work.
Versioned codes must match the selected entry. Arbitrary URLs are rejected and
never opened. No clocking token belongs in a URL, log, RFID queue or telemetry.
The issuance response reveals the token once; store/share labels privately.
This change does not provide label-printing or an admin token-management UI.

## Retry and timing

The page assigns one UUID per entry/token within the signed-in page session.
Network failures and invalid acknowledgements reuse the identical body and ID;
repeated successful scans in that session do not create additional requests.
It keeps tokens and retry state **only in memory** (up to 100 distinct scans).
Signing out/reloading/closing clears them. There is no browser offline spool;
if delivery is unconfirmed, keep the page open and retry the same scan. Closing
the page loses the retry key, so consult your club before resubmitting after an
uncertain response. RFID's SQLite queue is separate and unchanged.

The endpoint records operator capture, declared `capture_source` (`usb_qr`,
`web_camera`, `manual`) and untrusted timing metadata, never the raw QR token.
The previous QR insert supplied an unused metadata parameter; it did not
persist the claimed simulated flag. This change makes QR operator provenance
explicit without changing any existing event or removing any simulator flag.
RFID/firmware simulator paths retain their simulated markers and blocks.

Server receipt time remains authoritative; camera timestamps are not accepted
as arrival times. Every new QR event is pending and
`official_result_created=false`. Human review and independent guest verification
remain necessary under current rules; official finalization remains disabled.

## Checks

`node --test backend/tests/qr-core.test.cjs` checks parsing, entry matching,
concurrency and stable retry/deduplication. For real browser tests, install
`backend/requirements-browser-test.txt`, run `python -m playwright install chromium`,
then `python -m pytest backend/browser_tests/qr_browser.py`. An installed Chromium
can be selected with `BROWSER_EXECUTABLE`. Tests mock accounts/API and a camera
stream containing a generated QR image: they exercise the actual decoder, USB
Enter submission, network retry, permission-denied fallback and track cleanup.
They do not certify a physical scanner/camera or a live race. PostgreSQL tests
cover source persistence, owned-entry listing and replay when a test DB is set.

Upstream decoder and license: [jsQR](https://github.com/cozmo/jsQR).
