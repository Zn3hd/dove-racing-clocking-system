# Phone-based RFID clocking plan

Planning checkpoint: 16 November 2026. No reader/phone combination selected yet.
The owner's phrase "Android or bios" is interpreted as Android or iOS/iPhone;
confirm this interpretation before finalizing platform requirements.

## Goal and first release

Owner follow-up: migration 016, owner-bound one-use enrollment, member reader/race
selection, focused keyboard operator capture, serialized keyboard frames,
heartbeat and confirmed-backup cleanup are implemented locally. Physical reader
compatibility and background/iPhone acceptance remain gated. See the
[current owner guide](mobile-owner-reader-guide.md).

Implementation checkpoint (16 November): the shared queue/sync simulator and
administrator pilot screen are now implemented locally. A real Flutter-to-API
test proves lost-acknowledgement replay into disposable PostgreSQL. This is a
foreground simulator milestone, not hardware or owner-rollout acceptance.
See [pilot setup and boundaries](mobile-rfid-pilot.md).

Use a compatible phone at the loft to capture reader output, durably save events,
securely upload to the existing backend, and update provisional standings.

Ring -> entrance reader/antenna -> phone -> HTTPS -> FastAPI/PostgreSQL -> dashboard.

Preserve Flutter, FastAPI, PostgreSQL and the existing gateway event contract.
QR arrival scanning remains a separate browser workflow for guest race entries;
verify it on the intended Render version before a user rollout. This plan does
not replace RFID race entries with QR entries automatically.

Target both Android and iOS with shared capture-independent logic. First deliver
one tested Android/reader combination; then validate an iPhone-compatible reader
connection. Do not advertise arbitrary-phone or arbitrary-reader compatibility.
Bluetooth and USB describe transports, not a complete protocol specification.

## Existing components to reuse

- Signed-in app sessions and secure credential storage.
- Club-authorized reader provisioning, rotation/revocation and ring assignment.
- Device-authenticated arrivals and heartbeat endpoints.
- Immutable message identity, backend duplicate protection and validation.
- Existing provisional rankings and administrator review workflows.

The Flutter HTTP client currently sends account bearer tokens, not device-token
headers. Add a dedicated device client rather than treating a reader credential
as a user JWT. Mobile currently exposes administrator workflows; owner-facing
setup and permissions require design and endpoint authorization review.

## Phase 1: Compatibility proof (hardware gate)

Record phone model/OS, reader model/firmware, ring protocol/frequency, connection,
USB IDs or Bluetooth service/characteristic details, frame examples, terminator,
power requirements and manufacturer documentation. Keep tag examples synthetic
in public logs. Verify identifiers preserve leading zeros and map exactly.

For Android, check USB host/OTG, permission handling and the actual reader output.
Distinguish keyboard-emulation input from direct HID or serial transfers. A
keyboard-style scan into a focused field is an attended proof, not proof of
reliable screen-off capture. Test simultaneous charging and reader power with
the actual adapter; do not assume any OTG adapter supports it.

For iPhone, investigate documented BLE or manufacturer-supported accessory
integration. Do not assume Android USB or Bluetooth code will work on iOS.
Confirm the manufacturer's SDK/protocol, app access permissions and distribution
requirements before selecting a library or committing to that hardware.

Exit: an actual phone reads an actual ring consistently; read zone, framing,
leading zeros and device disconnect are documented. Unattended passage detection
must be independently demonstrated at the loft entrance.

## Phase 2: Shared event and durable queue foundation

Build an adapter interface and a clearly marked simulator, independent of physical
hardware. Persist events before attempting upload. Store stable message ID,
ring ID, original backend/reader/race, capture provenance and observation time.
Retry the exact original envelope after network failure or restart. Never
retarget existing events when the selected race, account or backend changes.

Use transactional local storage and explicit pending/received/rejected states.
Keep credentials outside event records and ordinary logs. Handle storage-full
and write failures by visibly stopping capture; do not silently lose evidence.
Decide local retention, privacy, backup/exclusion and diagnostics-export policies.
Do not let clearing app data appear to be a safe queue-recovery procedure.

Exit: tests prove commit-before-send, restart recovery, lost acknowledgement
replay, immutable envelopes, rejected-record retention and simulator labeling.

## Phase 3: Secure owner setup and synchronization

Administrator provisions a reader bound to the correct loft; owner can configure
only authorized assignments and races. Choose a short-lived one-use enrollment
flow or controlled pilot provisioning after reviewing existing API permissions.
Do not embed administrator passwords or reusable device secrets in public QR
labels. Any new owner endpoints must enforce club/loft membership server-side.

Device uploads use HTTPS with certificate verification, no redirects, bounded
timeouts and the existing device-token contract. Keep user-login and device
session lifecycles distinct: account logout must have an explicit capture/queue
policy; a reader may not silently move to the next signed-in owner. Stop capture
on owner logout in the pilot, retain old queued evidence under its original
assignment, and require authorized re-entry before resuming.

Retry network/server failures with backoff. Respect rate-limit pauses. Quarantine
permanent errors and pause on revoked/unauthorized credentials for operator action.
Verify heartbeat states mean the same thing as the existing backend. A successful
heartbeat does not establish that the antenna can detect pigeons.

Exit: real disposable PostgreSQL tests prove authorized delivery, duplicate
protection, token rotation/revocation, isolation and pending-review behavior.

## Phase 4: Phone reader screen and first Android adapter

Provide reader/loft/race selection, Start/Stop capture, visible connection state,
last scan, queued count, server receipt, rejection reason and diagnostic actions.
Distinguish "captured", "received", "needs review" and "eligible arrival".
Use operator mode by default; enable declared automatic mode only after the
installation has passed unattended entrance testing. Simulation stays separate.

Add only the selected hardware protocol first. For background-capable transport,
evaluate a native Android connected-device foreground service with notification
and required permissions. Test screen lock, navigation away, permission denial,
USB reconnect, phone restart and explicit force-stop. Do not promise continuous
capture after force-stop or process death. A lost-connection warning must remain
visible when capture cannot resume.

Exit: test APK captures and uploads using actual selected hardware; QR browser
and existing member/admin workflows continue working.

## Phase 5: iOS reader adapter and lifecycle acceptance

Reuse queue, payload, sync policy and user-facing states. Implement only a
confirmed compatible BLE/accessory protocol, with iOS permission and background
behavior verified separately. Test on physical iPhones with appropriate Apple
build/signing tooling; local Windows Android builds do not validate iOS.

Exit: publish a tested compatibility matrix and clearly state foreground-only
or background limitations per hardware/OS combination. Other readers remain
unsupported until their adapters and acceptance tests are complete.

## Phase 6: Surigao field pilot and owner kit

Use named test races and real verified loft locations. Test one known ring,
unknown ring, repeated scans, scan bursts/multiple birds, internet loss,
lost acknowledgement, unplug/reconnect, low power, screen lock, app restart,
permission refusal, storage-full behavior and reader credential revocation.
Compare physical scans, local records, backend receipts and displayed arrivals.
Record actual counts/times instead of claiming zero loss without measurements.

Verify power arrangements and detection coverage over an agreed race-duration
endurance test. Provide a compatibility-specific ring/reader/adapter/power kit,
owner instructions, privacy guidance, enrollment/replacement procedure and
support checklist. Budget and schedule follow hardware selection and this proof.

Exit: Taguig administrator and Surigao tester approve the documented pilot
results. Commit, push and deployment still need the owner's approval.

## Timing and official results boundary

Existing backend speed calculations use server receipt time. Durable offline
capture prevents some data loss but does not establish a trusted arrival time;
late uploads can change apparent timing, and new uploads after closure are
rejected. Signed/trusted offline timing and an acceptance policy are a separate
milestone. Official finalization remains disabled. A ring scan does not by itself
prove passage, physical identity, location or certified race timing.

## Platform references

- [Android USB host and user permission](https://developer.android.com/develop/connectivity/usb/host)
- [Android foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types)
- [Apple accessory integration](https://developer.apple.com/accessories/)
- [Apple Core Bluetooth](https://developer.apple.com/documentation/corebluetooth)

References inform platform feasibility; they do not certify any particular reader.

## Immediate next step

The hardware-independent queue/sync foundation, owner enrollment, focused keyboard
operator path, heartbeat and backup-confirmed cleanup are now implemented and
locally tested. Select one pilot reader/ring/phone pair next. Direct protocol
adapters, native background capture, iPhone builds, procurement and automatic
passage claims stay gated on actual hardware/platform acceptance. Do not mark
the complete hardware plan finished from software tests alone.
