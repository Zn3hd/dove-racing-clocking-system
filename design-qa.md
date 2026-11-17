# Design QA — Flight Deck race command center

final result: passed

17 November 2026. Exact selected target: second displayed generated image, saved as docs/images/race-command-center/selected-flight-deck.png. Earlier QA is preserved in docs/design-qa-race-workspace-20261107.md.

## Evidence

Opened the selected source before implementation. Its 1487 × 1058 pixels were normalized to 1440 × 1024, an essentially identical aspect ratio. Edge captures use deviceScaleFactor 1. The desktop full-page capture at 1440 × 1000 was cropped to 1440 × 1024 for comparison; the additional 24 pixels do not affect viewport-height-dependent geometry. No browser chrome is present.

Inspected the combined source/implementation image at docs/images/race-command-center/comparison.jpg after the final spacing corrections. Both depict the selected active race, populated provisional standings, activity, pending queue and collapsed supporting sections. Synthetic preview counts are 7/120 arrivals and 3 pending versus the illustration's 48/120 and 12 pending; calculations use actual fixture values. No invented trends were inserted. The fixture includes simulator and below-minimum rows to check evidence semantics.

Final screenshots: docs/images/race-command-center/admin-live-1440.jpg and admin-live-390.jpg. Eighteen captured desktop/phone states had no document overflow or JavaScript page errors. Browser tests also cover 320/390/1024/1440 widths.

## Iterations and fixes

1. First capture: P1 duplicate legacy KPI IDs/panel displaced the 70/30 layout; P2 account actions overlapped the selector. Removed the legacy vertical panel and restored non-overlapping account placement.
2. Second capture: P2 excess header/row space pushed review below the monitoring area. Shortened repeated metadata, explicitly formatted arrival times in PHT, bounded internal table scrolling and increased body text readability.
3. Combined comparison: account/header overhead remained. Moved account actions to the desktop navigation footer, retaining the normal phone header. Fixed the fifth KPI border and sample dates. Standardized speed precision to two decimals.
4. Recaptured delivery states and inspected the combined comparison again. The review action is visible within the 1024px desktop monitoring view; supporting disclosures can continue below. No remaining actionable P0/P1/P2 visual findings. Final semantic state-badge and textual New-marker rules leave the captured active/default appearance unchanged.

## Fidelity and intentional adaptations

White hero with blue edge, navy navigation, five horizontal KPIs, progress strip, 70/30 standings/feed, amber review panel and collapsed supporting sections match the chosen hierarchy. Existing Feather icons and P brand are reused. Generated extra Reports/Settings/Races routes were not invented.

Table/body values are 14px, secondary values 12px, numeric rank 23px, race title 28px and KPIs 30px. Dense desktop table/badge labels at 10–11px are a P3 follow-up opportunity; phone evidence labels increase to 12px. This is not a complete accessibility certification.

Both source and review state remain visible instead of the mockup's sometimes ambiguous Automatic-only badge, so evidence rows are taller. Internal scrolling retains every row with sticky headers. Non-simulated top-three entries receive medal accents; simulated rows keep Test ranks and never receive medals. Official finalization remains disabled. The primary action opens the existing race-preserving evidence-review workflow rather than pretending a new priority drawer exists.

## Verification

- 142 backend/PostgreSQL cases passed, including replay, pending count, review history and race isolation.
- 22 frontend/workspace browser cases passed: responsive views, same-origin CSP/icons, navigation, row identity, one-time highlights, delayed state, safe text, unknown metrics and reset cleanup. The three new update-state cases also passed after final speed formatting; these are not additional unique cases.
- Three real browser → FastAPI → disposable PostgreSQL QR cases passed: camera, USB lost acknowledgment and offline recovery. They verify pending before review, zero pending after review, activity, provisional speed and no official result.
- One initial timing-sensitive guest test inspected controls before login completed. Added an explicit workspace-visible wait; the frontend/workspace suite then passed.
- JavaScript syntax and git diff --check passed. No new migration is required.

## Limits and release

Existing three-second polling drives the interface. No SSE, background reader changes or hardware certification is claimed. Activity is latest 24 without pagination. Rate and last-arrival are unavailable for the 1000-entry truncated preview. Keyed rows retain scroll offsets; pause/apply-update controls and focus-aware reorder queues remain future refinements. Hardware acceptance and official timing remain separate.

This implementation is local. No commit, push or deployment was performed; Render still serves the earlier release.
