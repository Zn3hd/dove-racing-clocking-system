# Design QA — Race Workspace (2026-11-07)

final result: passed

## Scope and visual truth

Administrator dashboard and member Race Command Center. Selected direction is displayed option 2 with option 3 evidence labels; refined visual target:
C:/Users/admin/.codex/generated_images/01a18dce-3216-7b80-b410-d6d6c06e653d/exec-beab1cbf-b9f0-4bbb-a6b7-4700753f2f76.png.

Source dimensions: 1487 x 1058 pixels. Normalized to 1440 x 1024 for comparison with Edge captures at 1440 x 1024 CSS pixels and deviceScaleFactor 1. The near-identical aspect ratio requires only negligible resampling. No browser chrome is included. State: active selected race, populated provisional standings, disclosures initially closed, synthetic data. Fixture counts/rings differ from illustrative mock data to remain internally consistent with the API contract.

Full-view comparison: .pytest-tmp-design/comparison-desktop.png (source left, implementation right).
Focused table/typography comparison: .pytest-tmp-design/comparison-table.png.
Both combined images were inspected after the final changes. Separate source/capture views were not treated as a side-by-side comparison.

Implementation evidence: .pytest-tmp-design/admin-1440.png, admin-1024.png, admin-390.png, admin-320.png; corresponding *-full.png captures; member-1440.png, member-1024.png, member-390.png, member-320.png and full-page captures. Console and viewport measurements: .pytest-tmp-design/browser-evidence.json.

## Findings and accepted adaptations

No remaining actionable P0/P1/P2 issues in the reviewed local scope.

- Desktop keeps the navy navigation, lavender metric rail, selected-race toolbar and dominant standings table. Compact header and stronger pigeon/rank typography now maintain hierarchy.
- Real evidence includes capture declaration, review state, method, buffered upload and server-receipt details. Rows are therefore taller than the illustrative single-badge mock. This is intentional; hiding audit information to match row height would misrepresent the existing product.
- Backend-supported simulated test-preview ranks retain their calculations and show Test # and Simulated. Flagged records remain outside standings in the existing Arrival validation workflow. This preserves the API semantics; no official-result behavior changed.
- On phones, standings use labeled rows showing speed, distance and evidence within the viewport; no sideways scrolling is required. On intermediate widths the table remains scrollable inside its own labeled/focusable region, with an explicit scroll hint. Persistent navigation/account controls remain reachable.
- Original app branding is reused; new decorative images/icons are not introduced. Source image navigation icons are omitted to remain consistent with the existing app.

## Required fidelity surfaces

- Typography: existing Inter/Segoe UI fallback stacks retained. Main body/table text 14px, supporting evidence 12–13px, desktop heading 34px, phone heading 28px. Actual browser computed font stacks recorded in browser-evidence.json. Long unbroken race names tested without page overflow.
- Spacing/layout: desktop rail and wide table, grouped flat rows, compact toolbar and working disclosures. Phone header and statistics spacing tightened. Phone results adapted to labeled rows. Full and focused visual comparisons inspected.
- Colors/tokens: navy #122447, blue #326dd1, white, lavender summary. Calculated contrast ratios: muted #53627a on white 6.18:1; white on primary blue 4.95:1; purple simulation 6.76:1; amber pending 5.91:1; provisional blue 6.85:1; reviewed green 6.73:1. These spot checks do not certify whole-app accessibility.
- Asset fidelity: supplied existing P brand treatment retained. No external images, placeholder illustrations or new custom icon artwork.
- Copy/content: speed and arrival order remain distinct, automatic mode is explicitly declared, simulated evidence is visible, and official finalization remains disabled. Synthetic preview is identified in the sidebar; its HTTP server rejects writes.

## Comparison history

1. Earlier native-only QA was blocked: browser chrome/viewport mismatch and no phone or console checks. User approved local Playwright/Edge testing. Replaced native captures with content-only, measured desktop/tablet/phone captures.
2. Initial browser comparison found [P2] excess desktop header/row overhead and [P2] phone speed/evidence hidden behind horizontal scrolling. Fixed compact desktop header, shorter declared-auto badge, stronger identity text, compact phone stats and labeled responsive result rows. Preserved table/row/cell semantics. Recaptured and inspected admin-1440.png, admin-390-full.png and admin-320-full.png.
3. Follow-up comparison found [P2] narrow club-label wrapping and intermediate table-scroll discoverability. Fixed phone club-label sizing and added intermediate-width scroll guidance. Also guarded long race names with min-width:0 and overflow-wrap:anywhere. Final captures and combined comparisons inspected after these fixes.
4. First automated run: 4 failures caused by a test selector matching both a summary and heading. Scoped the selector to the summary. Subsequent runs passed. Final run includes non-first selected-race handoff and long-name stress coverage.

## Verification

Final command (from backend, using installed Microsoft Edge):
BROWSER_EXECUTABLE=<installed Edge executable> python -m pytest browser_tests/workspace_browser.py browser_tests/member_security.py -q -p no:cacheprovider

Result: **12 passed in 63.72 seconds**.

Coverage: four administrator viewport sizes; mobile speed/evidence visibility; semantic cells; member details and sign-out at desktop/two phone widths; navigation; telemetry mode selector; flagged evidence disclosure; selected-race review shortcut where the active race is not first; stale feed/error recovery; no-races state; safe text rendering; disabled preview writes; failed identity validation; delayed prior-session 401 isolation; sign-out data cleanup.

Eight rendered view combinations (admin/member at 1440x1024, 1024x768, 390x844, 320x740): no page-width overflow, no JavaScript exceptions or console errors. Browser fixture enforces page-error assertions. Existing frontend syntax checks and static ID/hook checks passed. git diff --check passes (unrelated existing documentation CRLF notice only).

## Limits and follow-up

- Synthetic local browser/API fixtures, not a new PostgreSQL end-to-end or production hardware test.
- Camera/USB/offline gateway reliability is a separate next milestone.
- No full screen-reader or physical-phone certification claimed.
- P3: optional typography/icon polish and shorter supporting text after real tester feedback. No blocking visual issues remain.

Local preview: http://127.0.0.1:8000/dashboard/ and /dashboard/member.html. Loopback-only and read-only, no production connections. Existing unrelated local changes preserved. No commit, push or deployment performed.

## Functional audit follow-up — 7 November 2026

Real QR/RFID workflow captures exposed a live-view success-notice/account overlap that the earlier synthetic preview did not reproduce. Live-view notice spacing was corrected and an end-to-end bounding-box regression added. View switches now reset scroll position. Final real-flow/browser regression: 25 passed; strengthened navigation rerun: 9 passed. Evidence and complete scope are in docs/functionality-audit-2026-11-07.md. No API calculation or official-result policy changed.
