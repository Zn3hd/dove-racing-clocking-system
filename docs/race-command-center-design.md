# Pigeon Racing — Live Race Command Center

Design proposal · 17 November 2026 · Desktop-first, 1440 × 1024 baseline.

This specification began as the proposed redesign. The second displayed visual direction (Flight Deck) is now implemented locally; see implementation status below for delivered behavior and remaining refinements. Generated screens contain illustrative data. No deployment is part of this work.

## Product intent and hierarchy

An official should answer three questions within five seconds: Is the race feed current? Who leads and who just arrived? What needs my attention?

The primary task is monitoring the selected race; the primary decision action is **Review next**. Club administration remains accessible through the existing navigation but does not compete with the monitoring surface. Keep only the actual existing routes: Members, Race operations and Live race. Any additional navigation or invented data shown in generated concepts is illustrative and must not be implemented without a real workflow.

Race state, connection state and evidence state are separate dimensions. An active race can have stale data. A received scan can still be pending review. A fast pigeon can be provisionally ranked without an official result.

## Complete desktop layout

At 1440px, use a 176px sidebar and 24px main gutters, leaving 1216px of usable content. Use a fluid content area up to 1920px rather than scaling type indefinitely.

| Zone | Height/width target | Contents and purpose |
| --- | --- | --- |
| Left navigation | 176px wide, fixed | Brand, club, existing three routes, official account controls. Live race selected. |
| Race banner | 120px high | Race name, selector, active state, connection freshness, release and last eligible arrival, compact registered/arrived/transit summary. |
| KPI row | Five equal columns, 96px high | Registered, Arrived, In Transit, Top Speed, Pending Reviews. |
| Progress strip | 48px high | Arrival percentage and fraction, remaining registered entries, observed arrival rate and active participants. |
| Main monitoring area | Approximately 430px high; 70/30 split with 20px gap | Dominant standings, supporting activity feed. Table roughly 837px and feed 359px at baseline. |
| Review queue | 80–96px initial height | Pending count, flagged count, oldest age and Review next. Expand or open a review drawer for individual evidence. |
| Supporting sections | 44–48px each, initially collapsed | Race details and Arrival validation, with concise meaningful summaries. |

Use 16px between major zones. Keep headings and context within the available height instead of forcing equal card heights everywhere. At 1440 × 1024, the banner, KPIs, six standings rows, activity feed and review action should be visible; supporting sections can continue below. The page scrolls naturally. The standings header sticks below the persistent race context; avoid several competing sticky bars.

## Race banner

Show a strong race title, with the selector grouped beside it. Race state uses a labeled badge: Draft, Registration open, Active or Closed. Separately show Connected, Updating, Delayed, Reconnecting or Offline, plus the last successful refresh time. Avoid using a Wi-Fi icon to imply the antenna is connected; this indicator describes the dashboard-to-server connection only.

Secondary line: release date/time, last eligible arrival date/time and timezone. Show the selected race's compact registered/arrived/transit summary. Use **Asia/Manila · PHT (UTC+08)** consistently; store timestamps in UTC and format them for the selected display timezone. Include the date where events may cross midnight. Never substitute last submission time for last eligible arrival time.

Before release show “Not released”; before any arrival show “No eligible arrivals yet.” Long race names wrap to two lines without hiding status or selector. Switching races clears prior race-specific activity/deltas, cancels or ignores obsolete responses and presents the new race's loading state.

## KPI cards

| Card | Main value | Supporting value | Icon and interpretation |
| --- | --- | --- | --- |
| Registered | Registered entry count | Registration state or snapshot time | Grid/users. No fabricated trend. |
| Arrived | Count of entries with eligible arrivals | Percentage; optional “+6 in last 5 min” | Check-circle, emerald. Count entries, not scans. |
| In Transit | Registered minus eligible arrived | “No eligible arrival recorded” | Send, racing blue. This does not certify that every pigeon is physically flying. |
| Top Speed | Maximum qualifying eligible speed | `m/min · provisional` | Zap/gauge. Exclude blocked/rejected records and identify test data separately. |
| Pending Reviews | Distinct currently pending review events | Flagged count and oldest pending age | Clipboard, amber. Click opens the queue for this race. |

Use a 12px label, 30–34px tabular value, 12–13px secondary text and a 20px icon. Keep units smaller but attached to their value. Display “— / Not available” when a measure cannot be computed; zero means an actual measured zero.

Only show trends when a complete, defined observation window exists. Use “Since this view opened” for session-only deltas; do not call them five-minute trends. Do not infer speed trends from a new race's snapshot. Avoid random sparklines, continuous number animations and red downward arrows for naturally falling in-transit counts.

## Provisional standings

Heading: **Live standings**, with a persistent **Provisional speed ranking** label. Speed rank and arrival order remain distinct.

Columns: Rank/group, Ring/owner, Arrival time/order, Distance (km), Speed (m/min), Evidence. Right-align measurements; use consistent precision, such as 187.000km and 1,284.50m/min. Support user resizing or internal horizontal scrolling at intermediate widths rather than silently dropping evidence.

Use semantic tables with a sticky header, 56–64px rows, subtle separators, 14px body text, 13px supporting text and 24px rank numerals. Rank 1 gets a muted gold token; rank 2 silver; rank 3 bronze. Show rank text as well as color. These treatments denote provisional speed position, never an official medal or final award. Ties share the backend-supplied rank; do not invent a client-side tie-breaker. Separate member/guest groups follow the configured race mode; show the group and count when a filter is active.

Eligible automatic evidence can be displayed as **Auto (declared)** with Reviewed/Unreviewed alongside it. QR/operator evidence does not enter the ranking until eligible under the backend's review rules. Put simulated entries in a separate, explicit test view with Test rank labels and no podium treatment. Blocking validation records stay outside competitive standings. Never “fix” this by promoting pending QR records just to animate the table.

### Stable row updates

Key rows by entry ID and update cells in place. A new eligible arrival receives a pale emerald background and textual **New** marker for 8 seconds; animate only a short background transition, with a static marker under reduced-motion preferences. Subsequent polling must not restart the highlight. A record loaded for the first time on page load is not automatically a new arrival.

Apply ranking changes without rebuilding the table or resetting scroll. Preserve focused row and selection. When an official is reading an older viewport, queue repositioning and show “3 updates available”; applying updates restores the visible entry as the scroll anchor. The feed and connection status continue updating. “Pause table updates” freezes presentation only, with a visible banner; it never stops backend clocking.

Row selection opens a details drawer: ring, owner, entry, source/device, received timestamp, observed timestamp when supplied, trust/validation flags and review history. Keep the underlying table's context and return focus when the drawer closes.

## Activity feed

Use a compact chronological list, latest first, with a 16px icon, timestamp, one-line event description and two lines maximum of metadata. Suggested event types:

- **Eligible arrival:** ring/loft, provisional speed and receipt time.
- **Submission received:** RFID/QR source and pending status. A submission is not an arrival announcement.
- **Review recorded:** approve/reject, authorized official and time; link to the evidence.
- **Validation flag:** specific rule, severity and affected evidence; link to Arrival validation.

Use stable event IDs to deduplicate retry/reconnect events. Order by server event sequence when available; otherwise use server timestamps with a deterministic tie-break. Events remain bound to their race. Announce a short, throttled summary through a polite live region rather than reading every cell. Do not enable sound by default.

At the top of a scrolled feed, show “4 new events” rather than jumping the list. Keep its scrollbar visually quiet. The concept's four sample events are illustrative; a complete review-action feed requires actual server audit events. Do not manufacture review notifications from a changed snapshot.

## Progress and arrival rate

Progress = eligible arrived entries / registered entries × 100. Example: 48 / 120 = **40%**, with **72 remaining**. Show registered minus arrived as an exact remainder, not an estimated return forecast. Zero registration gives “No registered entries,” not a division result.

Observed rate = newly eligible arrivals in the last complete five-minute window / 5. Example: 6 arrivals gives **1.2 arrivals/min · last 5 min**. Define whether the window is based on server receipt time; the current system uses receipt timing. Six records becoming eligible through review now are eligibility changes, not necessarily six physical arrivals now. Prefer arrival receipt timestamps for the arrival-rate calculation and label reviewed late evidence appropriately. Rate is unavailable when history is incomplete or truncated. No ETA or prediction is shown until a validated model exists.

Use a semantic progressbar with value, max and text equivalent. Count correction after a rejection can legitimately reduce progress; briefly explain the correction in the feed rather than silently showing a misleading positive trend.

## Evidence review and urgency

Keep a compact queue below monitoring with a persistent Review next action and a count on the KPI above. Default order: blocking validation needing attention, then oldest pending. Filter by source and review status. Flagged does not mean proven fraudulent; label the specific reason.

Amber denotes pending attention. Red is reserved for blocking conditions or critical system errors. Age is shown as elapsed time; avoid invented urgency thresholds. If the club later configures a review target, label the threshold and show overdue separately.

Review opens a drawer with evidence details, device/source, server-received time, untrusted observed time, duplicates/flags, reason field and Approve provisional evidence / Reject controls. Both actions require a reason and authorized server acceptance. Disable only the in-flight decision, preserve written reasons on recoverable failures and show success only after acknowledgment. On a conflict show “Already reviewed by another official” and refresh the record. Rejections and approvals remain audited; approval does not erase validation flags or certify official timing.

## Visual system

| Token | Value | Use |
| --- | --- | --- |
| Racing navy | `#122447` | Sidebar, banner, important headings |
| Action blue | `#245FC4` | Selected navigation, primary action, links |
| Emerald | `#147D57` | Eligible arrival, connected state |
| Emerald surface | `#E9F6EF` | Recent-arrival highlight |
| Amber | `#9A5B00` | Pending and attention labels |
| Amber surface | `#FFF4DB` | Pending count and queue accents |
| Critical red | `#BC3038` | Blocking/error labels |
| Critical surface | `#FDECEE` | Error/flag background |
| Page gray | `#F3F6FA` | App canvas |
| Surface | `#FFFFFF` | Table, cards and drawers |
| Divider | `#DFE6EF` | Sections and row separation |
| Secondary text | `#526178` | Metadata on light surfaces |
| Podium accents | `#8A6200`, `#5B6779`, `#945B35` | Provisional first/second/third; use pale matching fills |

Validate actual rendered text contrast at implementation, including badges, disabled controls and dark-banner text. Never rely on color alone. Use existing self-hosted Feather line icons, with text labels for actions and accessible names for any icon-only controls. Decorative icons are hidden from assistive technology.

Typography: existing Inter/Segoe UI/system sans stack; tabular numerals for measurements and timestamps. Race name 28px/34px semibold; page title 30px/36px; KPI value 32px/36px bold; section heading 18px/24px semibold; body/table 14px/20px; metadata 12–13px/18px; major rank 24px/28px. Avoid an all-uppercase terminal aesthetic for ordinary content.

Spacing: 4px base, with 4/8/12/16/24/32px steps. Card padding 16–20px, page gutters 24px, grid gaps 16–20px, inline icon gap 8px. Radius 8–12px, thin borders, minimal elevation. Drawers may use stronger shadows; routine rows should not.

## Live and alert states

| State | Presentation | Behavior |
| --- | --- | --- |
| Initial load | Skeletons only where data is unknown | Do not briefly show zero counts or old-race data. |
| Connected | Green dot plus last successful refresh time | Existing polling is acceptable; do not claim streaming/SSE without implementation. |
| Refresh in progress | Quiet “Updating” text | Keep the last good snapshot; avoid full-screen spinners. |
| Delayed | Amber “Updates delayed” and snapshot age | Suggested policy: >10s since last successful refresh for the existing 3s poll. Final threshold must be explicit and testable. |
| Offline/reconnecting | Banner plus stale timestamp | Keep data readable; do not imply that clocking stopped everywhere. Retry with backoff. |
| New arrival | Pale emerald row and New label | Highlight once; do not change keyboard focus or scroll. |
| Validation block | Red labeled flag with rule and action | Exclude from competitive ranking according to server rules. |
| Empty active race | “Waiting for first eligible arrival” | Keep progress at zero and expose pending submissions separately. |
| No pending reviews | Neutral “Review queue clear” | No urgent styling or unnecessary review action. |
| Race closed | Neutral Closed badge | Server controls allowed actions; received-submission recovery remains distinct. |
| Partial history | “Showing latest 500 submissions” or equivalent | Do not label partial counts/rates as complete race totals. |
| Session expired | Reauthentication prompt | Preserve no sensitive cross-account state; restore authorized race context after login. |

## Responsive and accessibility rules

At 1200–1439px, narrow the sidebar and feed, preserving table legibility. Below approximately 1100px, stack the feed below standings and use a 3+2 KPI grid. On phones use a compact race header, 2-column KPIs with a full-width review card, and labeled standings rows. Do not shrink the desktop table to unreadable text. Keep review access near the top as well as beside the queue.

All controls work by keyboard, selected filters expose their state, status updates do not steal focus, and the drawer traps focus with an Escape/close route. Support 200% zoom, reduced motion, forced colors and minimum 44px touch targets. Pause auto-reordering while keyboard focus is inside the table. Expose the selected timezone and include readable source/evidence labels in every compact row.

## Existing architecture and implementation needs

Preserve FastAPI, PostgreSQL, the existing dashboard routes, protected APIs, review authorization and gateway separation. Implement this in the existing web frontend after a visual direction is selected; no framework migration is required.

Use the live race snapshot for registered/arrived counts, race state, speed, participants, entries and validation summaries. Derive in-transit from the same snapshot. Compute last eligible arrival only over complete authoritative data; a truncated list cannot guarantee it. Review count and oldest age need race-wide aggregates, not just the latest 500 events returned by the current event-list endpoint.

The current `/clocking/events` endpoint exposes event source, received/recorded times, pending status, flags and metadata, limited to 500 events. It does not by itself supply a complete chronological review-action audit feed or an authoritative race-wide rate. Add a club-authorized race activity endpoint with stable event IDs and cursor pagination, plus aggregate counts/window metadata. Server aggregates should describe eligible-arrival timing and exclude duplicates. Display unavailable measures honestly until those contracts exist.

Start with the existing three-second dashboard polling and stable DOM updates. SSE/WebSocket delivery is optional later; if added, support ordered replay/cursors, reconnect recovery and polling fallback. Coalesce burst updates into a small rendering batch. Hide/offscreen presentation may pause, but never claim this affects hardware ingestion.

## Why this layout

Horizontal KPIs free the vertical rail for the table and place the five primary race measures in one scan. A compact banner anchors which race and snapshot the official is viewing. The 70/30 split puts evidence-rich ranking at the center while the feed answers what changed. A persistent review entry point connects observation to action. Progress provides race context without pretending to predict future arrivals. Stable updates protect the official's place during bursts, while semantic color and restrained highlights make genuine changes noticeable.

## Acceptance before release

Review the selected design at 1440/1920 desktop widths, 200% zoom and phone breakpoints. Exercise initial/empty/partial/error states, duplicate and delayed events, >100 rapid submissions, race switching during requests, sorting with keyboard focus, concurrent reviews, expired sessions and reconnect gaps. Verify counts and speeds against server evidence, including rejected, operator and simulated records. Preserve official finalization as disabled until the separate timing and hardware acceptance requirements are met.

## Implementation status — selected Flight Deck

Implemented the white race banner, horizontal KPIs, progress/rate strip, 70/30 standings/activity layout, top-three rank accents, recent-arrival highlights, sticky table header, pending panel and existing review navigation. Desktop account controls sit in the navigation footer; phone layouts retain readable labeled rows. Rows reuse entry IDs and retain table scroll offsets and one-time highlight timestamps. Connection failures retain the last snapshot with a delayed warning; the header also marks polling stale after ten seconds without success. Server-facing timestamps are labeled PHT.

The protected existing live endpoint now returns race-wide pending/flagged counts and oldest pending time, plus the latest 24 real submissions, validation flags and review decisions. No metadata secrets are returned. Arrival rate uses eligible non-simulated receipt timestamps over five minutes; it and last-arrival are unavailable for truncated previews. No schema migration or change to official result rules was made.

The 142 backend/PostgreSQL cases, 22 frontend/workspace browser cases and 3 real QR browser/database paths passed. See [design QA](../design-qa.md) and [desktop preview](images/race-command-center/admin-live-1440.jpg).

Future refinements: priority-specific review drawer/next-item selection, activity pagination, presentation pause and focus-aware queued reorder controls. Existing evidence review remains functional and race-preserving. No SSE or hardware acceptance is claimed. This local implementation has not been committed, pushed or deployed.
