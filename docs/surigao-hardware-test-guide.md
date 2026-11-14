# Surigao tester — scanning and arrival test

Updated: 7 November 2026. Use with the current [full user guide](user-guide.md).

This is a practical acceptance script for the operator beside the reader in Surigao and the administrator monitoring from Taguig. The software audit uses synthetic readings; the physical steps below still need to be performed with your actual equipment.

## 1. Choose the correct test

| What you have | What you can test |
| --- | --- |
| Phone and a private guest QR label | Guest login, camera scan, server receipt, evidence review and provisional standings |
| Keyboard-style USB QR scanner and computer | Guest QR submission through the browser's scanner input |
| USB RFID reader, matching electronic leg ring and computer | RFID reading through a configured local Python gateway, delivery, review and standings |
| Installed loft antenna/reader that detects a ring without hand presentation | Automatic capture, after a separate physical installation test |

An RFID reader does not read a QR image. A QR scanner does not identify an electronic RFID ring. A generic short-range USB reader may require presenting a ring by hand; that is an operator scan. The website alone cannot make that hardware detect a pigeon arriving at the loft.

The system uses saved release/loft GPS coordinates to calculate distance. It does not track the pigeon's current GPS position.

## 2. Open the correct page

- Administrator in Taguig: [Club administration](https://dove-racing-clocking-system.onrender.com/dashboard/).
- Guest with QR entry: [Guest QR scanning](https://dove-racing-clocking-system.onrender.com/dashboard/scan.html).
- Member: [Member dashboard](https://dove-racing-clocking-system.onrender.com/dashboard/member.html).

The latest local dashboard changes require an approved deployment before they appear on Render. These links identify the service; this guide does not certify its currently deployed revision. The localhost synthetic preview is a demonstration and does not record production arrivals.

## 3. Agree on the test before starting

Administrator and operator should confirm by call/chat:

1. A clearly named test race, for example `TEST — Surigao reader acceptance`.
2. The test participant, pigeon ring number and loft name.
3. The exact normalized electronic RFID ID, including leading zeros, or the guest's private QR label.
4. The clocking method: QR or RFID; and capture mode: operator, declared automatic, or simulated test.
5. Which person will review evidence. The operator must not use the administrator's login.
6. A shared test log with the date/time and timezone. Philippine local time is UTC+08:00; record that explicitly when reporting results.

Do not send passwords, QR secrets, device credentials or database connection strings in the shared log.

## 4. Administrator: prepare the race

1. In **Members**, create the member/guest account and share its credentials privately.
2. Save the **actual Surigao loft's** address and coordinates. Do not capture the administrator's Taguig location for a Surigao loft. Independently verify the saved location before marking it verified.
3. In **Race operations**, register the pigeon under that loft.
4. For RFID, assign the exact electronic ring ID read by the configured hardware. The official ring number can differ from that ID.
5. Create the test race with its release coordinates and agreed minimum/maximum speed policy.
6. Select the race, choose **Open registration**, then register the pigeon using the matching method.
7. Check the registered distance. Resolve coordinate mistakes before release.
8. For QR, issue a private label with sufficient validity for the agreed test window.
9. For RFID, register/provision the reader and prepare its gateway configuration. Supply its device token separately and privately.
10. Choose **Record release now** at the agreed test release. Confirm the status is `active` before asking the operator to scan.

### A bench scan can legitimately be blocked

Scanning immediately after releasing a race with a distant release point produces an impossible calculated speed. The correct outcome can be **received evidence with a speed flag and no ranking**. This demonstrates receipt and validation, not a failed reader.

Do not backdate a real release, change saved evidence or weaken validation to force a bench scan into standings. Test reception/flagging first. Test realistic speed/ranking with a properly timed test flight and agreed release/loft coordinates. Automated software fixtures use a controlled test clock; that is not an administrator workflow.

## 5. Guest: test camera or USB QR scanning

1. Open **Guest QR scanning** and sign in with the guest account.
2. Select **Your race entry**. Confirm the race and pigeon.
3. For a camera, choose **Use camera**, allow access, then point at a printed label or a label on another screen.
4. For a compatible USB QR scanner, choose **USB QR scanner**, focus **Clocking QR**, and scan. The scanner must finish with Enter.
5. Wait for **Scan received.** Reading/decoding an image without that acknowledgement is not confirmed server receipt.
6. Tell the administrator the test time and pigeon. Do not send the QR secret.

Expected: pending evidence appears for the correct entry. It does not become a live arrival until review and validation permit it.

If the network fails, keep the same browser profile/device. Reconnect and sign in, choose **Recover receipts**, and inspect the record. Rescan the same valid entry/code if necessary. The browser reuses its submission identity; do not clear its storage or assume a new device can recover that local record. Fully offline page loading and unattended upload without the original QR code are not supported.

## 6. RFID operator: prepare the local computer

1. Obtain the approved project revision from the administrator. Confirm the reader/ring protocol is compatible; frequency alone is insufficient.
2. Install/configure the Python gateway using [User Guide section 11](user-guide.md#11-set-up-a-physical-rfid-reader). Run it on the computer physically connected to the reader.
3. Save the administrator's non-secret JSON as `gateway/config.local.json`. Confirm backend origin, device ID, race ID, adapter, protocol, normalization and any COM/network settings.
4. Set `PIGEON_DEVICE_TOKEN` privately in that gateway process. Do not store it in JSON or screenshots.
5. Use `capture_mode: operator` for hand scans. Declare automatic mode only for a physically validated automatic installation.
6. From the gateway directory, run:

```powershell
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json diagnostics
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json heartbeat
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json run
```

7. Keep the terminal focused for a keyboard-emulation RFID reader. Do not type other text into it. A serial/raw-HID reader uses its configured adapter instead.

For serial/network/raw-HID transport errors, continuous capture retries supported transport failures while retaining evidence. Malformed frames or configuration errors require correction. Keyboard mode cannot reliably detect a disconnected reader. Stop normally with Ctrl+C; do not delete the queue.

## 7. RFID operator: perform an online scan

1. Confirm the administrator says the race is active.
2. Present the registered test ring once, or pass it through the validated antenna installation.
3. Wait for **Scan queued locally.** This confirms local storage, not delivery.
4. Wait for synchronization. A positive `sent` result confirms an API acknowledgement, not evidence approval.
5. Tell the administrator the scan time and the public pigeon ring number.

Administrator checks:

- The correct device/race/entry received one event.
- Capture mode and original scan match the intended test.
- Reader monitoring shows recent gateway contact and appropriate queue counts.
- Blocking flags are investigated.
- Operator scans stay out of live standings until reviewed. Declared automatic/simulated scans can appear in the provisional preview when validation permits.

## 8. Administrator: review and inspect the arrival

1. Select the race in **Race operations**. Choose **Refresh**.
2. Under **Arrival evidence review**, select the event and inspect its method, capture mode, timestamps, warnings and blocking flags.
3. Approve or reject with a specific reason. Approval cannot bypass blocking flags.
4. If recording physical guest verification, do so only after someone actually performs the inspection. Remote observation from Taguig is not a physical inspection in Surigao.
5. Open **Live race** and select the same race. Allow about 3 seconds for a successful refresh.
6. Check pigeon, owner, arrival order/time, distance, speed, group/rank and evidence labels. The updated **Review arrival evidence** shortcut returns to the selected race's review workflow.
7. On the member page, allow about 15 seconds or choose **Refresh**. Expand a result for details.

Expected: one first eligible event per pigeon entry, a provisional speed rank when above the minimum and within validation limits, and **zero official results**. A rejected/blocked/unreviewed operator scan may be stored without counting as an arrived pigeon.

## 9. Repeat and recovery checks

| Test | Expected result |
| --- | --- |
| Retry an uncertain delivery using its original queue/browser record | Same received event; no second event from that exact replay |
| Physically scan the same ring again | Separate retained evidence may have a repeat warning; one ranked row per entry |
| Use an unregistered ring | No matching arrival; gateway evidence is rejected/quarantined locally for inspection |
| Disconnect internet while leaving the gateway running, then scan | Local pending queue grows; server receipt is not yet confirmed |
| Stop/restart the gateway with the same config and queue | Pending evidence survives |
| Restore internet while race remains active | Retry eventually delivers; backoff can take up to 5 minutes |
| Gateway says recent but no valid ring reading occurs | Proves server reachability only, not reader or antenna health |
| New queued upload reaches the server after race closure | Rejected; do not change its identity/race to force acceptance |

Offline time is not backdated into speed. The gateway marks durable queued readings as buffered even during online delivery. That label does not prove an outage or certify the local clock.

## 10. Record the outcome

Copy this checklist into your test log:

```text
Test date/time + timezone:
App/repository revision or Render deployment:
Race name / method:
Tester / location label:
Reader model / adapter / documented protocol:
Public pigeon ring number:
Online reading captured: PASS / FAIL / NOT TESTED
Server receipt confirmed: PASS / FAIL / NOT TESTED
Expected review policy enforced: PASS / FAIL / NOT TESTED
Blocking flags and reason:
Distance / speed / arrival order checked: PASS / FAIL / NOT TESTED
Member view checked: PASS / FAIL / NOT TESTED
Exact delivery retry deduplicated: PASS / FAIL / NOT TESTED
Offline restart recovery: PASS / FAIL / NOT TESTED
Physical automatic detection: PASS / FAIL / NOT TESTED
Pending/rejected queue counts at end:
Sanitized error / screenshot reference:
```

Never mark physical automatic detection passed from the simulator, a hand scan or a heartbeat. Keep a test open until queued evidence is accounted for, then close the race and sign out. Retain the gateway queue for review.

For failures, report the step, time, expected/actual outcome and sanitized message. Do not reset the database, delete the queue, share credentials, or change real evidence to make a test pass.
