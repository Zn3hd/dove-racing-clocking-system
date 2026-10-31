# Guest QR workflow audit — local, uncommitted

Baseline: `develop` at `5d371fb`. No commits, pushes, deployments, live accounts,
or production database changes were performed for this audit.

Follow-up: `clocking-reliability.md` records the subsequent local implementation.
Its transaction/recovery/rate-limit and administrator-screen work supersedes
the corresponding outstanding items below. The browser test now has three cases
and performs all normal administrator operations through the new UI.

## Immediate milestone: software browser test completed

Two real Chromium tests passed against a local FastAPI server and disposable
PostgreSQL 16 databases with migrations 001–012. API replies were not mocked.
Camera pixels were supplied from a generated QR image; USB-style input was
supplied as keyboard text. These are software integration tests, not physical
camera/scanner certification. A fixture backdated only the synthetic race's
release by 30 minutes to avoid waiting; event receipt times came from the API.

| Stage | What was exercised |
| --- | --- |
| Administrator login | Real browser login and JWT authentication |
| Club/guest account | Created through the administrator dashboard |
| Guest loft | Created and independently marked verified through the existing GPS dialog, using synthetic coordinates |
| Pigeon | Registered through the real administrator API; no pigeon-management screen exists yet |
| Race/entry | Created, opened, guest QR entry registered, and released through the real API |
| QR issuance | Real API generated a race-bound token/versioned QR payload; local QR encoder generated the camera image |
| Guest login/listing | Separate browser context authenticated the guest and listed their released entry |
| Camera path | Actual vendored jsQR decoded the synthetic video frame; real HTTP request inserted evidence |
| USB-style path | Keyboard Enter submitted the QR text; a transport fault dropped the first real server acknowledgement |
| Retry | Identical message/body was retried after commit; PostgreSQL still held exactly one event |
| Review | Real administrator API approved the event; no review screen exists yet |
| Standings | Actual administrator Live race view polled and displayed guest rank 1, distance, speed and reviewed/operator evidence |
| Finalization | Close succeeded, official finalize returned 409, and no official result row was written |
| Session/device cleanup | Camera track stopped, signout cleared the QR input/session, and browser storage remained empty |

The camera test produced approximately 38.737 km and 1,290 m/min from the
synthetic release/loft setup; assertions verify the distance/duration formula,
not a fixed wall-clock-dependent speed. Screenshots and non-secret summaries
are in the ignored `backend/.pytest-tmp-qr-live/` test directories.

## Local fixes made

1. **Retry identity binding:** a QR idempotency key previously checked only
   entry/method/actor, allowing a valid new token or altered capture source to
   receive an older event's acknowledgement. Matching now also requires the
   original QR token identity and capture source. Legacy missing source is
   treated as `manual`. Mismatches return 409, and evidence remains unchanged.
2. **Strict browser acknowledgement:** the scan session now requires explicit
   `official_result_created=false` and `pending`/`invalid` status. Missing flags,
   an unexpected `valid` status, or an official-result claim no longer count as
   confirmed delivery. The original retry key is preserved.

Regression coverage adds source/token mismatch checks, genuine expiration
(distinct from revocation), and missing/unexpected acknowledgement fields.
Existing ownership, QR rotation, role, club, race, evidence-review and validation
checks remain in place. Capture source is a client declaration, not hardware proof.

## Remaining functionality and security work

### Before an unattended/offline pilot

- Browser retry state is in memory only. Refresh/close loses an unconfirmed
  request's key. There is no durable browser spool or authenticated guest receipt
  reconciliation screen/API. Define recovery before adding automatic offline
  resubmission; never silently invent a new idempotency key after uncertainty.
- Expired/revoked tokens and closed races currently block even an otherwise
  identical retry, because eligibility/token checks precede acknowledgement
  lookup. That is the current fail-closed policy, but needs an explicit recovery
  design for a lost response across those boundaries.
- Audit concurrent scan/close and scan/token-rotation behavior. The current QR
  query locks the entry, not the race or token row. A race-state/token change
  racing the scan is a potential validation gap; this audit has not exercised
  those concurrent schedules. Add transaction-level tests before claiming them
  serialized. Cross-entry reuse of a key under simultaneous requests also needs
  an explicit 409 regression rather than an uncaught uniqueness error.
- Add deployment-appropriate login and submission rate limits. They are absent
  from the current application; this audit did not inspect external proxy rules.
- Expose receipt/review status to the guest. Repeated successful scans currently
  return an in-memory cached acknowledgement; that is not a live status lookup.

### To finish the browser-only administration flow

- Add pigeon management, race setup/registration/release, QR label generation/
  rotation/expiry management, and evidence-review screens. These remain API
  operations, so the current test deliberately does not claim an all-GUI flow.
- Provide private label handling/printing without putting raw tokens in URLs,
  logs, analytics, public storage, or third-party QR generation services.
- Physical guest verification is available through the API but was not a
  physical action in this software test. QR possession/camera decode does not
  prove pigeon arrival, ring identity, position or time. Official finalization
  remains disabled.

### Hardware and further coverage

- Test a real phone camera and actual USB QR keyboard scanner (focus, Enter
  framing, keyboard layout, glare, low light, page hide and disconnect).
- Test long-lived sessions, camera permission revocation/startup cancellation,
  multiple entries, rotation while scanning, and reload after uncertain delivery.
- The existing four mocked-browser tests remain useful component coverage,
  but cannot replace the new real API/database cases.
- Production password/JWT rotation and bootstrap configuration were not
  inspected or changed. All audit credentials and coordinates were synthetic.

## Re-run locally

Install `backend/requirements.txt`, `backend/requirements-browser-test.txt`, and
the editable gateway package. Supply `QR_AUDIT_DATABASE_URL` pointing to the
disposable **localhost** server's `pigeon_qr_test` database. The opt-in test
refuses other hosts/database names, creates a fresh generated database for each
case, migrates it, starts a loopback-only API, then removes its own databases.
The database user therefore needs permission to create/drop disposable databases.

From `backend/`:

```text
python -m pytest -v --tb=short browser_tests/qr_live.py --basetemp=.pytest-tmp-qr-live
```

Set `BROWSER_EXECUTABLE` to an installed Chromium executable, or install the
repository's pinned Playwright Chromium. Do not point this test at Render or
any database containing club records. No CI workflow was changed or triggered
for these uncommitted local changes.
