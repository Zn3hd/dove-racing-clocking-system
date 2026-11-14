# Pigeon Racing Clocking System — User Guide

Updated: 7 November 2026. Covers the current local `develop` code, including the Race Workspace dashboard, member dashboard, guest QR page and Python reader gateway.

The latest local changes have not been committed, pushed or deployed as part of this audit. Render may show an earlier layout until an approved deployment. A local synthetic preview is a read-only demonstration; it is not the connected production service.

This is a development pilot. Standings are provisional, and official result finalization is disabled. Use clearly named test races while validating equipment and procedures. This guide describes implemented behavior; it is not certification of physical hardware or confirmation of a particular deployment's migration logs.

## 1. Open the app

| Page | Link | Who uses it |
| --- | --- | --- |
| Club administration | https://dove-racing-clocking-system.onrender.com/dashboard/ | Authorized chairman/president administrators |
| Member dashboard | https://dove-racing-clocking-system.onrender.com/dashboard/member.html | Member accounts; own pigeons, entries and provisional race standings |
| Guest QR clocking | https://dove-racing-clocking-system.onrender.com/dashboard/scan.html | Guests with accounts and QR race entries |
| Technical API documentation | https://dove-racing-clocking-system.onrender.com/docs | Developers and authorized technical operators |

Use the administrator dashboard for routine administration. The API documentation is not required for the workflows below. If the service is starting, allow it time to load before retrying.

Accounts are issued by an authorized administrator; there is no public self-registration screen. Ask your club administrator for access. Do not share an administrator login with a hardware tester.

## 2. Understand the roles and screens

| Role | Main responsibilities |
| --- | --- |
| Club administrator | Manage participants, lofts, pigeons, races, readers, QR labels, evidence reviews and standings within the authorized club |
| Member | Own registered pigeons/lofts; use the configured RFID workflow through the loft gateway |
| Guest | Sign in to the guest page and submit QR evidence for their own eligible entries |
| Reader operator | Run the gateway at the loft, scan rings, monitor delivery and report equipment issues; a device credential does not grant administrator access |

The administrator sidebar contains three areas:

- **Members:** participants, contact details, loft addresses and GPS verification.
- **Race operations:** pigeon/ring registration, race setup and release, QR labels, evidence review, reader setup and monitoring.
- **Live race:** provisional standings and arrival validation.

Administrator permissions are limited by club access. Being an administrator does not automatically grant access to another club's records.

## 3. Sign in and protect your account

1. Open the club administration link.
2. Enter your administrator email and password.
3. Choose **Sign in**.
4. Use **Change password** in the top bar when needed. Follow the current/new password fields in the dialog.
5. Choose **Sign out** when finished, especially on a shared computer.

Login sessions are kept in page memory. Reloading or closing the page requires signing in again. If the app reports an expired session, sign in again before continuing.

Guest accounts sign in on the separate guest QR page. A member account is not a guest QR account.

## 4. Set up your club and participants

### Create a club

If no club is assigned and the setup card is displayed:

1. Open **Members**.
2. Choose **Create racing club**.
3. Enter the club name and optional description.
4. Choose **Create club**.

The current pilot workspace supports one club per administrator. If the club already exists, ask its administrator to resolve access instead of creating a duplicate.

### Add a member or guest

1. Choose **Add member**. The dialog is titled **Add participant**.
2. Enter the person's name, email and optional phone number.
3. Select **Member** for the current RFID workflow, or **Guest** for QR clocking.
4. Create an initial password of at least 12 characters.
5. Choose **Add participant**.
6. Send the person's credentials privately.

Use the search box and role filter to find participants. **Edit** updates the available name/phone fields; email, role and credentials are managed separately.

Use **Link existing account** only when the participant already has an active account and the administrator has their account ID. Enter that account ID, not an email address.

## 5. Record and verify the loft location

Distances depend on the release point and the participant's loft. An address helps identify the place; the coordinates determine the distance.

1. In **Members**, locate the participant and open their loft location action.
2. Enter the loft name and address/place name.
3. Enter the actual latitude and longitude, or choose **Use this device's location** while physically at the loft.
4. Review the coordinates and choose **Save location**.
5. After independently checking the saved location, reopen it, select the confirmation checkbox and choose **Verify saved loft location**.

**For Taguig–Surigao testing:** store the Surigao loft's coordinates. Using your phone/computer's location in Taguig would record your location, not the remote loft.

The **Sison town example** is a municipal reference, not the exact loft. It cannot be used as verified racing coordinates. The address field is entered manually; GPS does not automatically fill the address name.

Changing a loft location clears its verification. Locations cannot change while entered in an unfinished race. Race entries retain coordinate snapshots, so resolve location mistakes before registering/releasing the race.

## 6. Register pigeons and RFID rings

1. Open **Race operations**.
2. In **Register a pigeon**, select the verified loft.
3. Enter the official ring number and optional pigeon name.
4. Choose **Register pigeon**.

For an RFID pigeon:

1. Expand **Assign an RFID ring**.
2. Select the pigeon.
3. Enter the exact normalized RFID ID emitted by the reader.
4. Choose **Assign ring**.

The official ring number and electronic RFID ID can be different identifiers. Preserve leading zeros. Do not convert decimal/hexadecimal IDs or change capitalization unless the gateway's explicit normalization policy requires it. Existing active ring mappings are not silently replaced.

## 7. Create, register and release a race

Follow this order:

**Create draft → Open registration → Register entries → Prepare labels/readers → Record release → Receive/review evidence → Close race**

### Create the draft

1. In **Create a race**, enter a clear name, such as `TEST — Surigao reader check`.
2. Enter the actual release latitude and longitude.
3. Set the minimum and maximum speed limits in **meters per minute**. The maximum must exceed the minimum. Use the club's agreed validation policy.
4. Select **Separate guest/member** or **Combined provisional** ranking.
5. Choose **Create draft race**.

The form initially displays 500 and 3000 m/min; these are software defaults, not a recommendation or certified competition standard. Do not relax validation merely to make a suspicious test scan appear valid.

### Register entries

1. Select the race in **Race registration and release**.
2. Choose **Open registration** and wait for the status to become `open`.
3. Select a pigeon.
4. Select **Guest QR** or **Member RFID**, matching the participant and setup.
5. Choose **Register entry**.
6. Check the listed entry, method and distance.

Prepare guest QR labels and reader configurations before release. Entry registration is available while registration is open, not after the race becomes active.

### Release and close

Choose **Record release now** only at the actual release. It records server time and changes the race to `active`; it is not a scheduling control or a way to enter a past release time.

After arrivals and pending gateway uploads have been checked, choose **Close race**. Closing stops new arrivals. Do not close a test race while testing offline synchronization. The dashboard does not provide a reopen control; check carefully before closing.

## 8. Issue private guest QR labels

1. Select the correct race in **Race operations**.
2. In **Private QR labels**, select the guest's QR entry.
3. Set validity in minutes (1–1440).
4. Choose **Issue / rotate QR label**.
5. Use **Download PNG** if needed, and send the label privately to the intended guest.
6. Close the dialog to clear its displayed QR image.

Issuing a replacement revokes earlier labels for that entry. The history shows expiry/revocation information and lets an administrator **Revoke** a label. A lost label should be rotated; history cannot reveal its original secret.

Do not post labels in a public group. Anyone holding a label has sensitive clocking information, although account/entry checks still apply. Closing the dialog does not delete a PNG you downloaded.

## 9. Guest: submit a QR scan

### Sign in and select your entry

1. Open the guest QR link.
2. Sign in using your guest email and password.
3. Select **Your race entry**. Use **Reload entries** if an expected active entry is missing.
4. Confirm the race and pigeon match the label.

### Use a camera

1. Select the entry first, then choose **Use camera**.
2. Allow camera access when your browser asks.
3. Point the camera at the private QR label.
4. Wait for the submission outcome. One code is captured per camera session.
5. Choose **Use camera** again for another scan.

Hiding the page or signing out stops the camera. Use another screen or a printed label if the phone cannot view and scan the same image simultaneously.

### Use a USB QR scanner

1. Connect a compatible keyboard-style QR scanner to the computer.
2. Select **USB QR scanner**.
3. Click the **Clocking QR** input.
4. Scan the label. The scanner must type its content and finish with Enter.
5. Wait for confirmation.

### Paste a token

Select **Paste clocking token**, enter the administrator-provided token and choose **Submit scan**. This is a separately identified manual capture source. Do not substitute an RFID ring ID for a QR token.

Accepted submissions remain pending review; they are not official results. A visible success acknowledgement is different from merely reading a code with the camera/scanner.

## 10. Guest: recover an uncertain submission

If the connection fails or the page reloads before you know whether a scan arrived:

1. Keep using the same browser profile and device.
2. Reconnect, open the guest page and sign in again.
3. Choose **Recover receipts**.
4. Inspect the recorded state. If the server did not receive the scan and the entry/label are still valid, select the same entry and rescan the original code.

The page saves a submission ID, source, client observation time and a token digest in IndexedDB before sending. It does not save the raw QR secret, password or login token. Rescanning the same entry/code reuses that submission identity instead of inventing another arrival after a lost acknowledgement.

| Recovery state | Meaning/action |
| --- | --- |
| `queued` | Stored locally; server receipt is not confirmed. Reconnect and recover/rescan as appropriate. |
| `sending` | Delivery began; the outcome may be uncertain. Recover receipts before assuming success or failure. |
| `received` | A server receipt was confirmed. Review may still be pending. |
| `needs review` | Flags or an uncertain state need administrator attention. |
| `rejected` | Recovered evidence was rejected; ask the administrator for the reason. |

Do not clear site storage during recovery. Another device or browser does not have this local record. Fully disconnected page reloads and unattended submission without the original code are not supported. Browser storage failure prevents a new scan being sent safely; do not repeatedly bypass or clear records to force submission.

Previously received receipts can be recovered after token expiry/revocation or race closure. That does not permit a new late arrival. Client observation times do not backdate speed calculations.

## 11. Set up a physical RFID reader

The website is accessible remotely, but a USB RFID reader needs a gateway on the computer beside it:

**Surigao reader → Surigao computer/Python gateway → deployed backend → Taguig administrator dashboard**

### Administrator steps

1. Confirm the reader model, tag compatibility and actual output protocol with the tester. Frequency alone does not establish compatibility.
2. In **Reader setup and live gateway monitoring**, choose the correct loft, unique reader name, adapter and documented protocol label.
3. Choose **Register reader**. Only one active reader per loft is currently supported.
4. Choose **Provision / rotate token** and privately supply the one-time credential to the gateway operator. Close the dialog after copying it.
5. Under **Gateway configuration**, select the reader and test race, then choose **Prepare configuration**.
6. Send this non-secret configuration to the operator. They must fill any serial/network connection placeholders with actual values.

Keep the initial capture mode `operator` for handheld scans. Use `automatic` only after validating an installation that detects arrivals without operator presentation. Simulator evidence must stay separate from physical tests.

Rotating a credential immediately invalidates the old one. **Revoke credential** blocks new device heartbeats and arrivals; queued evidence remains on the gateway. Neither action deletes previous arrivals. Never send the tester your administrator password or database credentials.

### Windows gateway operator steps

Obtain the project files from the administrator or download and extract the repository's [develop ZIP](https://github.com/Zn3hd/dove-racing-clocking-system/archive/refs/heads/develop.zip). Open PowerShell in the extracted **gateway** folder. These commands assume Python 3.11 or newer is installed:

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

For a confirmed compatible serial/COM reader, also install:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[serial]"
```

Save the administrator's JSON as `config.local.json` in the gateway folder, not `config.local.json.txt`. Match device/race IDs and adapter/protocol exactly. For serial readers, configure the actual COM port and baud rate; for network readers, configure the actual host/port. Custom binary protocols require a suitable adapter; do not assume they work with the text adapters.

Enter the credential without displaying it or placing its literal value in command history:

```powershell
$deviceSecret = Read-Host "Paste your device token" -AsSecureString
$env:PIGEON_DEVICE_TOKEN = [System.Net.NetworkCredential]::new("", $deviceSecret).Password
Remove-Variable deviceSecret
```

This sets the credential for this PowerShell session. Enter it again in a new terminal. Do not put it in JSON, screenshots or shared logs.

Check gateway reachability, then start capture:

```powershell
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json heartbeat
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json run
```

For keyboard-style capture, keep the terminal focused and do not type unrelated text into it. Scan only after the administrator confirms the test race is active. `Scan queued locally.` means local storage succeeded; a positive `sent` result indicates confirmed delivery. Neither is approval of the evidence.

Stop with **Ctrl+C**. To inspect the configured device's queue or synchronize existing evidence without capturing more scans:

```powershell
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json diagnostics
.\.venv\Scripts\python.exe -m pigeon_gateway --config config.local.json sync
```

The `sync` command above runs continuously; stop it with Ctrl+C. Add `--once` for one batch (at most 100 due events). One-shot sync does not maintain monitoring. See [gateway instructions](../gateway/README.md) for raw HID and advanced configurations.

## 12. Read device monitoring correctly

The monitor refreshes every 15 seconds while Race operations is visible. Continuous gateway `run`/`sync` reports about every 30 seconds.

| Gateway status | Meaning |
| --- | --- |
| `unprovisioned` | No device credential has been provisioned. |
| `never_seen` | No heartbeat since provisioning/rotation. |
| `recent` | Server received a heartbeat within 90 seconds. |
| `stale` | Last heartbeat is older than 90 seconds. |
| `revoked` | Credential has been revoked; new device requests are blocked. |
| `inactive` | Device is not active. |

**Recent does not prove the physical reader is connected.** In continuous capture, reader state starts as `not_probed`, becomes `waiting` after a reading is queued, and becomes `error` after a detected transport/framing failure. A `waiting` report is not continuous proof of antenna health. Sync-only operation and diagnostics do not probe hardware. Compatible serial/network/raw-HID transport failures are retried at 5–60 second intervals; malformed/configuration input stops capture for correction. Keyboard-console input cannot reliably detect an unplugged reader.

Queue counts are self-reported snapshots, not instantaneous server counts. A heartbeat never creates an arrival or changes **Last arrival**. If monitoring fails to refresh, previously displayed information may be stale.

## 13. Review arrival evidence

1. In **Race operations**, select the race and choose **Refresh**.
2. Under **Arrival evidence review**, select the event.
3. Read its blocking flags and warnings.
4. Select **Approve provisional evidence** or **Reject evidence**.
5. Enter a specific review reason (at least 8 characters) and choose **Record review**.

Operator/manual/unknown capture requires review before eligibility in provisional rankings. Approval cannot override blocking validation flags such as impossible speed or invalid timing. Evidence remains auditable; do not change coordinates or timestamps to make an invalid event appear legitimate.

The separate **Independent physical guest verification** panel records an actual in-person inspection, including observed ring number and an evidence note. Complete it only if that verification really happened. Remote monitoring from Taguig is not an in-person inspection in Surigao. Physical verification does not attest the clock or enable official results.

## 14. Read Live race standings

1. Choose **Live race** and select a race. Use **Reload races** if needed.
2. Keep this view open. Rankings refresh approximately every 3 seconds while visible.
3. Read the feed/update indicator; a failed refresh is not evidence that no new scans occurred.
4. Expand **Arrival validation** for evidence excluded by blocking flags.
5. Expand **Race details and top competitors** for supporting telemetry and qualifying loft/pigeon/owner comparisons.
6. Choose **Review arrival evidence** to open Race operations for the selected race. This opens the review workflow; it does not approve an event.

The updated desktop workspace places the statistics rail beside standings. On phones, each result groups its rank, pigeon, arrival time, speed, distance and evidence with labels. Intermediate widths may use a horizontally scrollable table. Check the selected race and units before comparing entries.

**Received scans and arrived pigeons are different counts.** A pending operator/QR/manual scan is visible in evidence review but excluded from live arrivals until approval and validation. Below-minimum eligible arrivals can be counted as arrived without receiving a speed rank. A flagged scan remains evidence and is excluded. A stale feed can temporarily show older totals.

**Test rankings are not official:** qualifying simulator data can appear in the test preview and is labeled **Test #…** / **Simulated**. The badge **Auto (declared)** records the device claim; it is not independent proof of an automatic arrival. **Reviewed** records evidence review, not certified timing.

| Field | Interpretation |
| --- | --- |
| Rank / group | Provisional position in the selected combined or separate ranking mode |
| Arrival order / time | Order and time of eligible arrivals; first arrival is not necessarily fastest |
| Distance | Release-to-loft distance using stored race-entry coordinates |
| Speed | Distance divided by elapsed time from actual release to server receipt; check displayed units |
| Evidence | Capture provenance, review information and simulation indicators |

The preview selects one first eligible event per entry. Distinct repeated physical scans may remain as evidence without creating multiple ranking positions. Transport retries with the same message ID are separately deduplicated. Review approval and the database event status are distinct; a provisional receipt is not an official result.

## 15. Member: view your pigeons and arrivals

1. Open the **Member dashboard** link and sign in with a member account.
2. Confirm your pigeons and race entries. The guest QR page and administrator page use different roles.
3. Select your race. The page refreshes approximately every 15 seconds; **Refresh** requests an update now.
4. Read **Speed ranking** for qualifying provisional entries. Select a row or **Details** to expand owner, distance, capture mode and qualification information.
5. Expand **Arrival order and below-minimum arrivals** to inspect eligible arrival sequence independently from speed rank.
6. Read **My race entries** for scan detection. A detected scan is not necessarily qualified or official.
7. Choose **Sign out**. Reloading or closing the page also loses its in-memory login.

Members see their own asset/entry cards and permitted race standings. The member page does not issue QR labels, provision readers, edit participants or approve evidence. Administrator credentials do not unlock this member-only page.

## 16. Offline and remote testing checklist

Coordinate by call/chat so the administrator and operator know when each step starts:

1. Confirm an online scan is received for the correct pigeon.
2. Scan the ring repeatedly and inspect duplicate/ranking behavior.
3. Disconnect only the gateway computer's internet, leaving capture running.
4. Scan a known test ring and confirm local queueing.
5. Stop normally with Ctrl+C and restart using the same config and queue.
6. Restore connectivity while the test race remains active. Retry backoff can take up to five minutes.
7. Check scoped diagnostics, received evidence and rejection reasons. Verify evidence was retained across restart and delivery retries did not create duplicate events.
8. Close the test race only after outstanding evidence is accounted for.

Do not delete `gateway-queue.sqlite3` or its associated files while testing. Do not copy live queue files while the process is writing them, rewrite message IDs, move old records to another race, or backdate timestamps. Queue files contain private club evidence and should be kept on the authorized gateway computer.

The gateway labels every durable queued reading as buffered, including online delivery; this label alone does not prove an outage. New gateway uploads after race closure are rejected under current policy. Buffered observation times are untrusted: speed still uses server receipt, so offline tests do not establish official timing accuracy. A short bench test may legitimately produce speed validation blocks. Simulated tests do not establish physical hardware compatibility.

## 17. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot sign in | Correct page/account role, email/password, active account and club access; contact administrator rather than sharing another login. |
| Too many requests | Wait for the retry interval; retain the original submission ID/queue. Repeated login/scanning can extend throttling. |
| Missing loft/pigeon option | Participant membership, active assets, saved/verified loft coordinates, correct selected race; refresh. |
| Race control disabled | State order: draft → open → active → closed. Wait for the previous operation's acknowledgement. |
| No guest entries | Guest account, QR entry ownership, active/released race and current registration; reload entries. |
| QR invalid/expired | Correct entry and current label; ask administrator to check expiry/rotation. Recover an uncertain prior receipt before creating new evidence. |
| Camera unavailable | Browser camera permission, another app using the camera, or unsupported device; use a compatible USB QR scanner or approved paste workflow. |
| USB RFID types nothing | Check actual ring compatibility and reader mode. A serial reader does not type into Notepad. Identify the protocol before changing settings. |
| Local scan queued but not received | Internet/TLS connection, device token, config, active race, ring mapping and registration; inspect diagnostics. |
| Gateway HTTP 401/403 | Missing/rotated/revoked credential or authorization. Retain queue, contact administrator and update credential privately. |
| Gateway HTTP 404 | Ring/entry/device mapping may be unavailable. Administrator should inspect the rejection. |
| Gateway HTTP 409 | Race state or reused message content conflict; inspect instead of inventing a new ID. |
| Gateway HTTP 422 | Configuration or payload validation mismatch; check adapter/protocol and documented reader format. |
| Gateway queue rejected | Evidence is quarantined for inspection, not silently deleted. Do not force it into another race. |
| No standings row | Confirm server receipt, review requirements, blocking flags, simulated provenance, selected race and successful feed refresh. |
| Monitor stale but hardware seems fine | Gateway stopped, network unavailable or token blocked; heartbeat reachability is independent of USB behavior. |
| Website error after an update | Report time, page/action and error. A deployment/migration issue needs administrator/developer investigation; do not reset the database. |

## 18. Before ending a test or race session

- Account for pending and rejected evidence before closing the race.
- Confirm the displayed race status and most recent successful refresh.
- Close private QR/device-token dialogs; handle downloaded labels privately.
- Stop local capture with Ctrl+C when appropriate and retain its queue.
- Sign out on shared computers.
- Report the test race, device name, date/time with timezone, action, expected/actual result and sanitized error message. Never send passwords, device tokens, QR secrets or database credentials in screenshots or public reports.

## 19. Follow one scan all the way through

1. **Capture:** the camera decodes a QR label, or the local gateway reads an electronic RFID ID. A read alone is not server receipt.
2. **Local recovery:** the gateway stores an immutable event envelope; the QR browser stores a no-secret recovery record. Keep the same queue/browser profile when retrying.
3. **Delivery:** the authenticated API validates the entry, race, account/device and replay identity, then stores pending evidence. Acknowledgement confirms receipt only.
4. **Validation:** timestamps and maximum-speed checks can block the event. Repeated physical scans are retained as evidence; an identical transport retry returns the same event.
5. **Review:** QR/operator/manual/unknown evidence needs approval for provisional eligibility. Declared automatic and simulator records can appear without review when validation passes.
6. **Arrival:** the first eligible event per entry supplies the arrival time. Blocking flags, rejection and review policy can change which event is eligible. Other retained scans do not create additional pigeon ranking positions.
7. **Calculation:** distance is calculated from the release/loft coordinate snapshots. Speed = distance in meters ÷ elapsed minutes from release to **server receipt**. Offline observation time does not backdate that speed.
8. **Display:** administrator live standings poll about every 3 seconds; member standings refresh about every 15 seconds. Rank follows speed within the configured group, not scan order.
9. **Close:** account for unsent records before closing. Previously received identical requests can recover their receipts after closure; new late uploads are rejected.
10. **Official results:** disabled. Successful receipt, evidence approval and provisional rank do not finalize a race.

Example: a pigeon flying 120 km in 120 minutes has 1,000 m/min; another flying 100 km in 110 minutes has about 909.09 m/min. The second can arrive sooner while the first has the higher speed. Compare only eligible entries in the applicable ranking group.

For a remote acceptance session, use the [Surigao tester instructions](surigao-hardware-test-guide.md). For the software evidence and remaining limitations, see the [7 November functionality audit](functionality-audit-2026-11-07.md).

## Related documentation

- [Reader monitoring and credential behavior](reader-monitoring.md)
- [QR scanning technical details](qr-scanning.md)
- [Clocking reliability and recovery boundaries](clocking-reliability.md)
- [Gateway installation and adapter configuration](../gateway/README.md)
- [Render migrations — administrator/developer operations](render-postgres-migrations.md)
