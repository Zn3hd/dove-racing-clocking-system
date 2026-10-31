# Clocking reliability and administrator workflows

Local implementation for review. Nothing has been committed, pushed or deployed.
Apply migration `013_rate_limits.sql` before starting this version; previous
migrations are unchanged. The FastAPI/PostgreSQL, gateway and buildless dashboard
architecture is preserved. Official finalization remains disabled.

## 1. Transaction safety

QR issuance/submission/revocation acquire race SHARE, then entry/token locks in
consistent order. Submissions also serialize the same idempotency key through a
transaction advisory lock. Race close acquires the conflicting race UPDATE lock.
When close/rotation wins, no new arrival using the obsolete state is accepted.
Token expiry uses the database's actual clock after any lock wait, rather than
the transaction start time. Cross-entry key collisions return 409, not 500.

An already-received, byte-consistent logical submission is acknowledged before
new-arrival eligibility checks. Its original token hash, actor, entry, capture
source, and queue-observation timestamp must match. Expiry, revocation or race
closure therefore cannot hide an existing acknowledgement or create another
event. New identifiers still undergo all current eligibility checks. Ownership,
account status and current club membership remain required for submission.

`GET /clocking/qr/receipts/{submission_id}` lets an authenticated guest reconcile
only their own previously submitted QR evidence, including after race closure.
It returns current review/validation status without requiring or revealing the
QR secret. Another guest receives 404. Historical own receipts remain readable
for active accounts even after membership changes; new scans do not bypass club
membership rules.

## 2. Browser recovery without saved QR secrets

IndexedDB stores a per-account, per-entry/token-digest record before the browser
sends a scan: immutable UUID, capture source, queue time and receipt state.
It does **not** store the raw QR token, QR image, password or bearer JWT. The
token digest is not an upload credential. Multiple tabs serialize record
creation using IndexedDB's read/write transaction, preserving the original ID.

The guest page shows `queued`, `sending`, `received`, `needs review` or
`rejected` and provides **Recover receipts**. After reload/signout, authenticate
again and reconcile. If the event was committed, the original receipt is shown
without resubmitting. If nothing was committed, rescan the original label to
reuse the saved ID/source/time. An expired code or closed race requiring a new
arrival is sent to club review, not silently backdated or assigned a new UUID.

This deliberately does not provide unattended delivery after closing the page:
there is no stored QR secret to upload. The page/assets are not a service-worker
offline application; reload while disconnected requires connectivity to load
and sign in again. Already-open pages can queue intent and resume after a
connection returns. Disabled/quota-exhausted storage prevents sending a new
unrecoverable scan. Clearing browser site data deletes local recovery metadata;
resolve uncertain submissions with the club before doing so. No automatic
outbox deletion/retention policy has been introduced.

`client_queued_at` is retained as untrusted observation evidence and mapped into
the existing timestamp assessment; it never replaces server receipt for speed.
Future or pre-release clock observations may require investigation. Review does
not override validation blocks. Recovering rejected evidence also refreshes the
session's cached acknowledgement, so it is not later displayed as still pending.

## 3. Shared rate limits

Budgets are atomic PostgreSQL counters shared across application instances,
using a fixed 60-second window. Raw IP/email values are not stored; identities
are HMAC-pseudonymized with the JWT signing key. All instances must already use
the same strong signing key. Rotating it also changes rate-limit identities.
Stale buckets are removed on subsequent requests after two windows.

| Environment variable | Default requests/minute | Scope |
| --- | ---: | --- |
| `LOGIN_IP_LIMIT` | 120 | Login source IP |
| `LOGIN_ACCOUNT_LIMIT` | 10 | Normalized login email, including failed attempts |
| `QR_SCAN_IP_LIMIT` | 600 | Bearer-present QR submission source IP |
| `QR_SCAN_ACCOUNT_LIMIT` | 120 | Authenticated guest, including retries/provider QR delegates |
| `QR_ISSUE_ACCOUNT_LIMIT` | 30 | Administrator QR issuance/rotation |
| `QR_RECEIPT_ACCOUNT_LIMIT` | 300 | Authenticated guest receipt lookup |
| `DEVICE_SCAN_IP_LIMIT` | 1200 | Device arrival source IP |
| `DEVICE_SCAN_DEVICE_LIMIT` | 600 | Authenticated reader identity |

Limits are configurable from 1 to 100000. Invalid configuration or unavailable
shared protection fails closed with 503. Exceeded budgets return 429 plus
`Retry-After`; rejected attempts do not insert events. Fixed windows can allow
bursts around a boundary, so these are request budgets, not a strict sliding
window. Tune against real club traffic and shared-NAT use before production.
The application uses the framework's client address, not untrusted forwarded
headers; configure trusted proxies correctly in the deployment server.

Browser retries keep their ID and display the wait period. The Python gateway
pauses all pending delivery for that reader/origin on 429 until Retry-After,
retaining every queued payload and ID. No credential is placed in limiter rows.

## 4. Administrator Race operations

The new tab provides:

- Pigeon registration against a verified loft and RFID ring assignment.
- Draft race creation with release coordinates, speed limits and ranking mode.
- Entry registration, opening registration, actual release and closing.
- Private QR issuance/rotation with locally generated PNG display/download,
  expiry history and token revocation. Plaintext codes are not stored on the
  server or returned by history. Closing/signout clears the displayed canvas;
  user-downloaded labels must be handled privately.
- Evidence review with validation flags, and independent physical guest
  verification. Operators must record only inspections actually performed.
- Reader last-receipt/status listing and guidance for guest-side recovery.

State-changing controls wait for confirmed race transitions. The complete guest
QR operation is now possible without Swagger. Live provisional standings remain
the separate existing tab. Race operations, receipt and private token responses
are no-store. Device last receipt is not an active connectivity probe.

## Verification and remaining acceptance

New PostgreSQL tests force lock waits for close, rotation and expiry, exercise
simultaneous same/cross-entry IDs, ownership-protected recovery, token image
privacy, shared atomic budgets and retry after throttling. Real Chromium tests
perform administrator setup, label generation/decoding, guest arrival, review,
physical-verification recording, closing and recovered receipts through the UI.
They cover both pre-send loss and lost acknowledgement, reload/rescan with the
same ID, no QR secret in IndexedDB, rate-limit UI and storage failure.

The proposed CI workflow runs these against disposable PostgreSQL; it has not
been pushed or triggered. Local tests use synthetic camera frames/keyboard text
and synthetic accounts. A physical camera/scanner, Raspberry Pi endurance,
deployment proxy configuration, production rate tuning, credential rotation,
and certified offline timing still need their own acceptance checks. This is
not authorization to deploy or enable official results.
