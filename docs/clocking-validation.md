# Clocking validation and reliability

Migration `010_clocking_validation.sql` adds a shared evidence-validation view,
race policy, and database guards. Apply it before deploying these routes.

## Policy

Each race has `maximum_speed_mpm` (default 3000 m/min) and
`clock_tolerance_seconds` (default 5, range 0–300). The speed limit is an
operational review threshold, not a claim about a universal biological maximum.
Club officials should choose it for their race before registration opens.
It must exceed `minimum_speed_mpm`. `POST /races` accepts these fields;
`PUT /races/{id}/validation-policy` replaces them only while the race is draft,
under the same club permissions as race administration. Updates are audited.
Existing races receive the default ceiling, or minimum speed plus one when
their minimum is already at least 3000. Their historical evidence is retained;
current provisional rankings can change as validation is applied.

## Blocking flags

- Race not released, arrival at/before release, or server arrival outside the
  configured tolerance around the stored receipt time.
- Calculated speed above the race maximum. Equality is permitted.
- Malformed/naive original observation timestamps in imported historical data,
  observation at/before release, or observation later than receipt plus tolerance.
  New gateway submissions already reject naive/malformed timestamp syntax.

Evidence is not deleted or rewritten when flagged. The view recomputes flags
from stored evidence and race policy. Both live and reviewed previews filter
blocking flags **before** selecting the first eligible arrival, so a later valid
event can qualify. Review approval does not override blocking flags. A below-
minimum arrival is excluded from rank under the existing qualification rule.

`GET /races/{id}/validation` returns counts and the latest 50 flagged events.
The Live race dashboard displays this panel and current policy. Raw clocking
event listings include flags and warnings for administrator inspection. Flags
are not proof of fraud: investigate hardware placement, timing, mapping and
configuration with the retained evidence.

## Duplicate and offline evidence

An identical idempotency key/message retry returns its original event. Reusing
an identifier with a changed payload remains a conflict. Separate scans with
new identifiers are retained and marked `repeat_scan` after the first stored
scan of that entry/method; they never create multiple ranked rows per entry.
Repeat scans, buffered evidence, delayed observations, and simulations are
warnings, distinct from blocking flags. A duplicate may be the first eligible
arrival when an earlier event was suspicious or explicitly rejected.

Reader time remains untrusted. Valid local observation time is checked for
consistency but is never substituted for server receipt to improve speed.
Offline observations older than five minutes receive a delay warning; they are
not promoted into official order. Offline acceptance and signed timekeeping
remain outstanding. These rules cannot detect every bad or tampered clock.

## Official-result guards

Simulator evidence is labeled persistently. An ordinary evidence update cannot
strip its simulated designation or promote it to `valid`. A database trigger
rejects approval/finalization of simulator or suspicious evidence in
`race_results`, checks the event belongs to the result entry, and prevents result
insertion into finalized races. These are additional safeguards; the API still
disables **all** official finalization pending trusted timing and acceptance rules.
Simulator scans may appear in explicitly provisional development rankings when
their timestamps/speed pass the same validation checks.

Migration 010 also repairs the previous event-immutability trigger: it now
returns `NEW` on allowed updates rather than silently discarding every review
rejection. Updates/deletes on finalized races remain blocked. Existing rejected
review records already exclude evidence from live rankings regardless of its
historical event status; no past evidence is silently deleted.

## Verification

PostgreSQL tests cover excessive and exact-ceiling speed, zero duration,
malformed/past/future observation timestamps, first eligible fallback,
idempotent retry, review-approval non-bypass, and simulator promotion attempts.
Software checks do not establish physical reader reliability or official timing.
