# Universal clocking implementation status

The hardware-independent architecture is confirmed. This checklist reflects
code and software tests, not universal reader compatibility or official timing.

| Milestone | Current implementation |
| --- | --- |
| Common event format | Immutable UUID message, reader/race identity, normalized tag, original scan, observation time, adapter/protocol, capture mode |
| Adapter interface | Separate Python gateway with a shared adapter contract |
| Simulator | Offline generation and end-to-end queue/API replay tests |
| USB HID / serial | Focused keyboard-emulation console and newline ASCII serial; raw HID/vendor protocols pending |
| Network adapters | Interface ready; implementation requires documented protocols |
| Reader registration/config | Club-authorized reader registry and local per-reader config |
| Offline delivery | SQLite queue, backoff, stable retries, rejection retention |
| Backend integration | Device authentication, active entry/membership checks, tag mapping, audit, replay protection |
| Diagnostics/monitoring | Passive queue/config diagnostics; active connection probes/heartbeats pending |
| Platform tests | Windows/Linux software CI; Raspberry Pi physical testing pending |

## Live arrival milestone

The dashboard's **Live race** view reads `GET /races/{race_id}/live` every three
seconds while open. It shows ring, owner, distance, arrival order, speed, rank,
capture mode, and review status. Only club-authorized races are visible. Ranks
use speed, so the first physical arrival is not necessarily rank one when loft
distances differ. Arrival order is the order of eligible server receipt times.

Each registered entry contributes its first eligible event after release.
Later scans are retained as evidence but do not replace that event. An explicit
review rejection or physical rejection removes an event from eligibility, so a
later eligible event may then become first. Disqualified/withdrawn entries are
excluded. Operator/manual/unknown captures require approval before ranking.
Declared automatic RFID and simulated RFID can appear immediately, always as
provisional evidence; simulations are labeled. These rules do not write official
results or enable finalization. Existing reviewed-only preview remains available.

Gateway `capture_mode` defaults to `operator`; configure `automatic` only for a
reader installation intended to capture passages without operator presentation.
Simulators always send `simulated`. Configuration is a declaration, not proof
that a pigeon passed an entrance. Physical detection range, framing, reliability,
multi-tag behavior, and clock integrity need hardware acceptance tests.

All live calculations currently use server receipt time. Local observation time
and buffering remain visible evidence, not trusted arrival time. An offline scan
can therefore appear much later; it must not establish official finishing order.
The live view is capped at 1000 eligible entries and reports possible truncation.

Existing queue records omit the new optional fields and remain deliverable with
their original payloads. Unknown older captures require review (except explicitly
marked simulator evidence). Missing capture mode is never inferred as automatic.

## Next acceptance work

1. Validate a specific reader's protocol and detection zone with real rings.
2. Add documented network/raw-HID/vendor adapters as needed.
3. Validate Raspberry Pi ports, long-running capture, reconnect, and queue recovery.
4. Implement monitored reader health, secure time synchronization, signed evidence,
   reviewed offline acceptance, and official certification policy.
5. Add race setup and evidence-review screens to the dashboard.
