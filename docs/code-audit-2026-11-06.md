# Code audit — 6 November 2026

## Scope and baseline

Updated local `develop` from `5bd132b` to remote `b2029f4` using a fast-forward. Preserved the existing uncommitted README edit and `docs/user-guide.md`. Reviewed the intervening backend, member dashboard, gateway, Flutter client and workflow changes (46 files, approximately 3,550 added lines), with executable regression work focused on authorization, clocking transactions and browser account isolation. This is a bounded review, not a claim that every possible defect has been excluded.

## Confirmed findings and local fixes

| Priority | Finding | Reproduction and correction |
| --- | --- | --- |
| High | Revoked/rotated device credentials could still authorize requests already waiting for the device lock. | Four PostgreSQL schedules covered heartbeat/arrival against rotation/revocation. All returned success with the old token before the fix. The joined credential/device read retained an old snapshot across the lock wait. Authentication now locks the device first, then reads the current credential in a separate statement. Both ingestion and heartbeat use this shared helper. |
| High | Removing club membership did not revoke shared member standings access. | A member with a registered race entry received HTTP 200 after their club membership was removed. The standings authorization query now requires current member membership for club races; legacy club-less race ownership behavior is retained. The regression expects HTTP 404 after removal. |
| Medium | RFID arrivals did not serialize against race closure. | An arrival was accepted while a competing transaction held the race lock for closure. The gateway now acquires race SHARE before its device lock, matching the QR lock order. A close that wins prevents new evidence; exact previously accepted message recovery still occurs before active-state rejection. |
| Medium | Old member requests could terminate a newer browser session, and unsuccessful identity validation retained a token. | Chromium delayed one account's overview until another account logged in, then returned HTTP 401. The old request cleared the new session. A separate identity-check failure left a login token in memory. Requests now bind response handling to token and session generation; failed login verification clears the session. Pending refreshes resume correctly after an old request finishes. |
| Medium | Member responses lacked the authenticated API cache policy; signout retained rendered private data. | `/member/overview` lacked `Cache-Control: no-store`. Middleware now covers `/member` as well as existing authenticated routes. Member signout clears identity, pigeon/entry lists, race choices, standings and metrics from the DOM. |

These issues span both the newly added member code and previously introduced gateway code still used by the additions. No credentials or production data were used in reproductions.

## Verification

Regression tests were written and run against the original behavior before fixes. The first credential/cache run failed all five cases as expected. All three browser isolation tests failed before fixes. Race-close and removed-member tests also reproduced their original failures independently.

Tests use a disposable localhost PostgreSQL 16 instance with real migrations 001–014. Member integration uses real Chromium, FastAPI and a separately generated disposable database. Browser session race tests use synthetic credentials and controlled API delays; they do not connect to production.

- Full backend suite after fixes: 121 passed (including real PostgreSQL regressions).
- Gateway suite: 66 passed.
- Member browser tests: 4 passed (3 session/privacy regressions and 1 real API/database integration).
- JavaScript syntax and Git whitespace checks passed.
- CI configuration includes the new browser security regressions. The workflow has not been pushed or triggered by this audit.

## Remaining acceptance and limits

Follow-up, 7 November: Flutter 3.47.9 / Dart 3.13.7 were installed locally. An isolated source copy passed analysis with no issues and all 27 Flutter tests. The original SDK limitation below describes the 6 November audit environment; Android/native Windows toolchains and device acceptance remain outstanding. See [local Flutter setup](flutter-local-setup.md).

- Flutter/Dart executables were not available on this workstation. Flutter sources and workflow boundaries were reviewed statically, but local `flutter analyze`, `flutter test`, Android compilation, secure-storage behavior on devices and redirect/transport behavior remain unverified here. Do not interpret the backend/browser results as mobile build acceptance.
- Physical RFID compatibility, antenna behavior, gateway endurance and certified timing remain hardware acceptance tasks. The monitor still honestly reports gateway reachability rather than hardware attestation.
- Automatic capture and offline observation times remain device-declared evidence; official finalization remains disabled. This audit does not enable official results or backdate offline records.
- No schema change was required for these fixes. No production migration, commit, push or deployment was performed.

## Files to review

- `backend/app/routers/device_gateway.py`: fresh credential snapshots and race-close serialization.
- `backend/app/routers/member_dashboard.py`: current membership gate for shared standings.
- `backend/app/main.py`: member response cache policy.
- `backend/dashboard/member.js`: session response isolation, failed login cleanup and rendered-data cleanup.
- `backend/tests/test_audit_concurrency.py`, `backend/tests/test_member_dashboard.py`, `backend/browser_tests/member_security.py`: reproductions and regressions.
