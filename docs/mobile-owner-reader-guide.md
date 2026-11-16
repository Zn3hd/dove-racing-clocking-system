# Owner phone reader pilot

Local software checkpoint: 16 November 2026. Backend migration 016 and Flutter
0.2.0/code 2. Physical Android/iPhone reader compatibility is not accepted yet.

## What the owner needs

- A club-issued member account, verified loft and assigned active reader.
- A supported phone with our test app and internet for enrollment/live upload.
- For keyboard capture: a reader connection the phone recognizes as a keyboard,
  with complete printable ring IDs followed by Enter. Actual USB OTG, Bluetooth
  keyboard support, power and detection range require hardware testing.
- For simulation: a separately registered simulator and named test race.

This is a foreground operator pilot. Keep the phone at the loft, the app open,
and the ring field focused. Typing the ID is indistinguishable from keyboard
reader output; both are operator evidence requiring administrator review.
No automatic entrance detection, direct USB/serial driver or BLE protocol adapter
is claimed. Simulator evidence always stays labeled simulated.

## Administrator setup

1. Create/link the member to the club, register/verify their loft and register
   each pigeon and exact electronic ring ID. Preserve leading zeros.
2. Register the reader at the member's loft. Keyboard profile: `usb_hid` /
   `ascii-newline-v1`. Simulator profile: `simulator` / `mobile-simulator-v1`.
   Other profiles remain unavailable in this phone pilot.
3. Open **Race operations -> Reader setup**, locate the reader and choose
   **Create owner invitation**. It is a private one-use code, valid for 10 minutes.
4. Share the code privately with that member. It is not a pigeon arrival QR label
   or reusable device credential. Creating a replacement invalidates the old code;
   the current gateway credential changes only when the invitation is redeemed.
5. **Revoke credential / invitation** invalidates the gateway credential and
   cancels any outstanding invitation. Rotation also cancels pending invitations.
   A revoked invitation cannot reenable a gateway. The dashboard shows pending,
   consumed, expired or no invitation; raw codes are not returned by monitoring.
6. Create/open the race, register the pigeons as RFID entries and release it.
   Owners can enroll before a race; capture selection appears when an authorized
   active RFID race exists for their loft.

Close or leave the one-time dialog to clear its displayed value. It also clears
when the document becomes hidden. If the code or redemption response is lost,
issue a new invitation; there is no plaintext credential-recovery endpoint.

## Owner enrollment

1. Sign in using the member account, then open **My loft reader**.
2. Enter the private owner invitation and choose **Enroll reader**.
3. The backend rechecks active member/loft/club authorization and atomically
   consumes the invitation and rotates the device credential. The credential is
   returned once and saved in phone secure storage, never displayed or queued.
4. Choose your assigned reader and active race, then **Open reader session**.
5. Read/confirm the operator-evidence or simulator notice and open the queue.
   Owner assignments are prefilled/read-only; owners cannot choose another loft
   by entering its UUID in this workflow. Backend authorization remains decisive.

If enrollment committed but credential storage failed or the response was lost,
ask for a fresh invitation. Repeating a consumed code does not reveal its token.
Enrollment rotates prior gateway credentials, so coordinate replacement phones
with the club; this does not create a multi-phone shared credential service.

## Capturing and uploading

For keyboard mode, focus the ring field. A complete ID and Enter queues operator
evidence. The app immediately separates that frame from the next input and
serializes commits. Up to 100 in-memory frames can wait; overflow or storage
failure visibly stops capture rather than silently claiming a saved reading.
Only the SQLite commit establishes durable local capture. Sudden power loss can
still lose a frame not yet committed. Physical burst handling needs field tests.

Choose **Start foreground upload** to retry pending evidence every five seconds.
The device client uses a separate credential, HTTPS, no redirects, bounded
acknowledgements and backoff. Restart retries the exact same message/envelope.
Received events are evidence, not automatic review approval or official results.
Unknown rings/closed races/validation failures are retained as rejected records.
Do not change message IDs or move records to another race to bypass rejection.

Heartbeat reports run at most every 30 seconds while the foreground worker is
enabled. Counts are scoped to this account/reader/race. Reader state remains
`not_probed`: a focused keyboard field cannot independently prove a reader or
antenna is connected. Recent heartbeat establishes gateway reachability only.
Device authorization failures pause the queue; re-enroll a corrected credential.
Rate-limit deadlines persist and cannot be cleared by re-enrollment.

Screen lock/backgrounding stops scheduling. Leaving the page stops the session
and drains already accepted keyboard frames before closing storage. An in-flight
upload may already have committed; stable message IDs recover its receipt later.
On return/restart, reopen the same assignment and explicitly start upload.
No background service, boot capture or unattended continuity is promised.

## Export and safe cleanup

1. Stop uploads, wait for current captures/uploads to finish and choose
   **Export evidence / clean backed-up receipts**.
2. Confirm copying private evidence. A scoped JSON export includes at most 500
   records and contains ring IDs, timestamps, immutable envelopes and receipts;
   it excludes credentials. Treat it as private club evidence.
3. Paste/save it in a private file. The clipboard alone is not a backup.
4. Confirm **I saved a backup; clean received** only after that save.
5. Cleanup deletes only received records from that exact exported snapshot.
   Pending, rejected, another owner's records and receipts received after the
   snapshot are excluded. Repeat export for another batch if needed.

There is no automatic deletion or evidence-import feature. Keep the phone locked
against unauthorized access; evidence SQLite is not encrypted by this feature.
The global 10,000-record cap includes all accounts/statuses; protected evidence
cannot be silently discarded to free space. Never uninstall or clear app data
as a recovery shortcut.

## Software validation and remaining gates

- Full backend/PostgreSQL suite: 141 passed after migration 016.
- Mobile analysis passed; 58 tests passed, with one opt-in case skipped normally.
- Both opt-in Flutter/API/PostgreSQL paths passed: owner enrollment, simulated
  or operator capture, real commit/lost acknowledgement, reopen/retry, one stored
  message, heartbeat and no official result. Operator evidence remains unranked
  before review.
- A real Edge browser invitation issuance/redemption/clearing test passed;
  the final status/cancellation follow-up passed as part of 14 targeted checks.

Saved evidence reports:

- `backend/.pytest-tmp-owner-full-20261116/results.xml` — 141 backend tests.
- `backend/.pytest-tmp-owner-monitor-final-20261116/results.xml` — 14 targeted
  enrollment, monitoring and browser checks (overlap the backend suite).
- `backend/.pytest-tmp-mobile-owner-arrival-final-20261116/results.xml` — two
  actual mobile upload/review/ranking flows; 43.73 seconds.

Android debug artifact: `dist/android/pigeon-racing-owner-reader-20261116-arm64.apk`,
86,685,071 bytes, SHA-256
`19a2028ef004618096d32b7a7448b989c8085c3ce26f15556ed62ba281a2608d`.
Signature verified; manifest confirms version 0.2.0/code 2, minimum SDK 24,
target/compile SDK 36, internet permission, backup disabled and cleartext disabled.
The generated example package ID and debug signing remain test-only.

The final JavaScript web preview compiled successfully in an isolated scaffold
after these owner changes. Existing secure-storage dependencies still produce
WebAssembly dry-run warnings; no Wasm support or web-based reader capture is
claimed. Local Docker testing was stopped after validation.

No GitHub CI, Render deployment, production migration, actual phone/ring/reader
test, iOS build, power-loss hardware guarantee or official certification follows
from these local software checks. Next hardware work requires the exact reader,
ring protocol and at least one phone model. iPhone builds require suitable Apple
build/signing tooling; this Windows test run does not supply that validation.

See [phone gateway plan](mobile-rfid-plan.md) and [earlier simulator milestone](mobile-rfid-pilot.md).
