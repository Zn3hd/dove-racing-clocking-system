# Development roadmap

The owner's planning estimate is 60% overall. Percentages are not acceptance
criteria and have not been validated by a full repository and deployment audit.

## Current delivery checkpoint — 7 November 2026

This checkpoint supersedes older statements below about missing screens, PostgreSQL execution, network adapters and heartbeat monitoring. The remaining text also contains historical planning context.

| Track | Implemented and verified locally | Next acceptance |
| --- | --- | --- |
| Web/backend | Administrator/member dashboards, Race operations, QR scan/recovery, validation, rankings and reader provisioning/monitoring; 121 backend tests and 4 member browser checks passed after audit fixes | Review/publish the uncommitted fixes, then verify the deployed version and migrations |
| Gateway | USB keyboard/serial, configured raw HID, newline TCP, durable queue and heartbeat; 66 gateway tests passed | Physical reader/ring compatibility, disconnect/restart/endurance and Raspberry Pi tests |
| Flutter | Authentication/session and club workflows, isolated demo, API origin/redirect protections; analysis and all 31 tests passed; first debug APK compiled | Physical phone authentication/permission/session checks against the intended test backend |
| Android tooling | Flutter/Dart, Java 21, SDKs, build tools, platform tools, CMake and NDK installed; isolated build helper; first ARM64 debug APK built and signature/manifest verified | Install and exercise the test APK on a compatible phone; package ID/release signing remain future distribution work |
| Official results/launch | Provisional calculations and validation exist; official finalization stays disabled | Trusted timing and offline policy, backup/restore, operational acceptance and certification |

See [code audit](code-audit-2026-11-06.md), [Flutter local setup](flutter-local-setup.md) and [Android testing](android-testing.md). Mobile demo changes remain in memory and do not establish Render integration. No production writes, commits, pushes or deployments are implied by local tests or tool installation.

Follow-up: the owner reports the Android phone test completed. Phone model, Android version and individual test evidence have not been recorded here, so this remains user-reported acceptance. Reader transport recovery is now implemented locally (capped reconnect backoff, preserved queue envelopes and capture-state heartbeat reporting), with 73 gateway tests passing. Next acceptance is a physical reader disconnect/reconnect and offline synchronization test in Surigao; software tests do not establish ring/reader compatibility.

## Current foundation audit

- Architecture: FastAPI, PostgreSQL, SQL migrations, and CI exist.
- Security: JWT login, protected administrator endpoints, password changes,
  and guarded first-admin setup exist. Password changes do not revoke existing
  JWTs. Rotation of exposed credentials and removal of the Render
  `ADMIN_BOOTSTRAP_SECRET` variable have not been verified.
- Clubs: creation, administrator membership, listing, and member assignment
  exist. Duplicate assignments are handled atomically. Migration 008 adds a
  nullable race club relationship. Race administration and evidence access now
  enforce club administrator membership; historical races remain creator-only.
  Club race entries require active owners who belong to the club. The new
  PostgreSQL isolation scenarios passed in GitHub Actions for commit `6a024fc`
  (46 tests passed across the complete suite).
- Participants: member/guest creation, loft creation/verification, and pigeon
  registration exist. Club-scoped listing/editing, atomic account membership,
  coordinate verification reset, and unfinished-race editing guards are added.
  Assets inherit club scope through owner membership. Legacy global asset
  access remains only before the first club is created.
- Races and clocking: registration, activation, provisional arrivals, review,
  and guarded closing exist. Physically rejected arrivals are excluded from
  previews; physical confirmation is displayed separately from timing trust.
  A full club-to-guest-race integration scenario is added. Official finalization
  deliberately remains disabled, including after physical guest confirmation.
- Dashboard: the first same-origin web administration milestone is implemented
  at `/dashboard/`: login, club creation, member/guest directory and creation,
  account linking, contact editing, and password changes. Loft, pigeon, race,
  and evidence screens remain outstanding. Browser visual QA is unavailable in
  the current environment; API workflow and static delivery tests are included.
- QA: unit/API tests and disposable PostgreSQL CI exist. Local PostgreSQL
  integration execution remains unavailable in the current environment.
- Deployment: Render health, Swagger, and club route presence were checked;
  this does not prove database migrations or race workflows succeed.

## Next milestones, in order

### Member/loft GPS

Migration 011 and the Members GPS dialog add exact manual/device coordinates,
reported accuracy, capture time, and source. Sison is a town-reference example
only, blocked from loft verification. Changed location evidence clears
verification; existing race snapshots and unfinished-race guards are preserved.
See `member-gps.md`. Browser capture requires a physical device acceptance run.

### Clocking validation and reliability

Migration 010 introduces configurable race speed/timestamp policy, shared
suspicious-event assessments, duplicate-scan warnings, ranking exclusion before
first-arrival selection, and database-level simulator/official-result guards.
The live dashboard shows flagged evidence separately. See `clocking-validation.md`.
Physical reader connection remains a later hardware acceptance milestone.

### Updated RFID architecture

Confirmed direction: a separate hardware-independent Python gateway for
Windows/Linux laptops and Raspberry Pi, preserving the FastAPI/PostgreSQL backend.
The `gateway/` component implements the adapter interface, explicit normalization,
simulator, focused keyboard-emulation input, line-oriented serial input, durable
SQLite offline evidence, and authenticated replay-safe synchronization. Reader
registration and tag assignment are club-authorized backend APIs. Migration 009
adds declared adapter/protocol metadata to readers. Existing gateways retain
their API contract and replay hashes when optional fields are omitted.

Remaining hardware milestones: protocol-specific network/binary adapters, reader
discovery, real reader/ring compatibility runs, Raspberry Pi hardware validation,
tag namespace policy, signed/tamper-resistant offline evidence, and trusted timing
acceptance rules. Dynamic integration does not imply universal hardware support.
See `../gateway/README.md` for setup and current constraints.

Live provisional standings and gateway capture provenance are now implemented;
see `universal-clocking-status.md` for the checklist, eligibility policy, and
remaining hardware/monitoring milestones. The gateway foundation already exists;
do not restart it merely to match a planning folder sketch.

1. Complete security cleanup: rotate the exposed administrator password and JWT
   secret privately, remove bootstrap environment credentials, verify setup is
   disabled, and test token invalidation behavior. Never put secrets in this file.
2. Finish club ownership: scope race creation, listing, reads, and every write
   path to club administrators. Include entries, review, results, finalization,
   device administration, and clocking source routes in the permission audit.
   Race/evidence checks, device provisioning, Messenger account administration,
   participant management, and membership checks during guest/provider ingestion
   are implemented and passed PostgreSQL CI in commit `6a024fc`.
3. Connect participants and assets: define club membership requirements for
   lofts/pigeons, enforce them during registration, and add scoped management
   and editing workflows. Preserve historical race coordinate snapshots.
4. Test one complete race against disposable PostgreSQL: create club, assign
   accounts, verify lofts, register pigeons, open/register/release, record arrival,
   verify evidence, calculate/rank, finalize, and reject unauthorized changes.
5. Build the dashboard around the completed workflows.
6. Complete reliability, hardware integration, operational monitoring, backup
   recovery, and production acceptance checks before launch.

## Club migration acceptance criteria

- Define an explicit reviewed policy for existing races with null club IDs;
  do not silently attach historical records to the first club.
- Deny unrelated administrators and members access to club-owned records.
- Require the pigeon owner to belong to the race's club.
- Apply the same policy to direct UUID lookups and alternate clocking routes.
- Test permission failures and successful flows against real PostgreSQL.
- Do not mark tenant isolation complete based only on the `/clubs` endpoints.

## Local reliability follow-up (awaiting approval)

The four planned milestones are implemented locally: QR transaction serialization, durable no-secret browser receipt recovery, shared PostgreSQL rate limits (migration 013), and administrator Race operations. See `clocking-reliability.md`. Browser tests now exercise the full administration path and reload recovery with real APIs/database. Do not interpret this local status as deployment or physical hardware acceptance.

## Scan-to-arrival audit — 7 November 2026 (local, not deployed)

Completed a local software audit with 121 backend/PostgreSQL tests, 73 gateway tests, 25 Edge browser cases and 6 QR-core checks passing. Added real gateway queue/restart/lost-ack-to-browser tests for operator, declared automatic and simulated modes, with administrator/member arrival verification. Fixed notice overlap and view scroll behavior; strengthened navigation rerun passed nine cases.

See [audit evidence and remaining gaps](functionality-audit-2026-11-07.md), [user guide](user-guide.md) and [Surigao acceptance script](surigao-hardware-test-guide.md). Physical reader/ring/antenna acceptance, trusted offline timing and official finalization remain outstanding. These results do not establish the current Render deployment or change phase estimates.
