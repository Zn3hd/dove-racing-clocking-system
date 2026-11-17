# Web frontend finalization — 17 November 2026

Baseline released on develop as `f6ad4f6`. The styling follow-up below is local and awaits release.

## Design baseline

Preserved the approved navy sidebar, blue actions, lavender race statistics and white standings workspace. This is a finishing pass on the existing FastAPI-served web application, not a replacement frontend. Existing form IDs, API contracts, session handling and evidence rules remain in place.

## Findings and changes

| Finding from current screenshots | Change | Verification |
| --- | --- | --- |
| Member directory expanded a 390px phone page to 736px, placing loft details and actions outside the viewport. | Phone directory rows become labeled cards; identity and addresses wrap; actions remain reachable. Desktop retains its table. | Real Edge viewport checks at 320, 390 and 1440px, including opening the loft dialog. |
| Guest recovery instructions appeared before the primary arrival controls. | Entry selection, camera control and QR submission appear first. Recovery remains available below; its explanation is a disclosure. | Capture ordering and masked token checks; existing camera decoder, retry and durable-submission tests. |
| Member sign-in fields spanned most of a desktop window. | A bounded sign-in panel uses the shared spacing, color and typography. | Desktop and phone screenshot review. |
| Sign-in pages lacked consistent routes between administrator, member and guest workspaces. | Shared workspace links, current-page indication and an optional Show password checkbox. | All three sign-in pages tested; resetting a form clears and remasks its password. The checkbox is excluded from submitted form data. |
| Race operations presents a long sequence of forms. | Added shortcuts to registration, pigeons, race creation, evidence review and readers. Simulator tools use a closed, explicitly labeled test disclosure. | Every shortcut resolves; simulator can be opened; existing review shortcut preserves race selection and focus. |

Shared focus indicators, skip links, reduced-motion support and phone-sized form text complete the pass. These checks do not constitute a full accessibility certification.

## Visual evidence

Current-run screenshots use synthetic race/member records. Sign-in pages contain no credentials. No production records were edited.

- [Administrator race workspace](images/frontend-final-20261117/after-admin-live-1440.jpg)
- [Phone member directory](images/frontend-final-20261117/after-members-390.jpg)
- [Phone QR arrival](images/frontend-final-20261117/after-guest-clock-390.jpg)
- [Member sign-in](images/frontend-final-20261117/after-member-signin-1440.jpg)
- [Before/after at the same 390 × 844 viewport](images/frontend-final-20261117/mobile-comparison.jpg)

Inspected desktop/phone contact sheets and the same-viewport mobile comparison. The 18 captured states at 1440 × 1000 and 390 × 844 had no document overflow or JavaScript page errors. The screenshot server is loopback-only and rejects writes. Guest QR screenshots use mocked API responses.

## Automated validation

26 unique Edge browser cases passed across:

- `frontend_polish.py`: 8 cases, including narrow member cards, sign-in privacy/navigation, QR layout and operation shortcuts.
- `workspace_browser.py`: 9 existing cases, including 320/390/1024/1440 layouts, provisional evidence labels, empty/error recovery and safe text rendering.
- `member_security.py`: 3 existing session isolation and sign-out cases.
- `qr_browser.py`: 6 existing cases, including generated QR camera frames, retry behavior, rate limits and storage failure.

The first run exposed an incorrect URL pattern in the new directory test fixture: it omitted query strings. Corrected the fixture and reran all 8 new cases successfully. The other 18 cases passed in the initial run. JavaScript syntax checks and `git diff --check` also passed. Added the new browser suite to the existing CI workflow; no remote CI run is claimed before pushing.

No backend or database behavior changed. PostgreSQL end-to-end tests were not rerun for this pass; the local Docker engine was unavailable. Camera/browser tests use generated QR frames, not a physical camera or RFID reader.

## Release boundary

This pass finalizes the web pilot's presentation for review. Flutter screens were not redesigned or device-validated in this task. Final acceptance still requires the selected phone, rings and reader, foreground/background behavior checks, and the separate trusted-timing/official-result work. The interface continues to distinguish declared automatic, operator, simulated and reviewed evidence; official finalization remains disabled.

Next: review the web screens, approve the release, then commit/push and verify the Render deployment before hardware acceptance testing.

## Styling follow-up

Added a soft neutral page background, white bordered cards, subtle shadows, a navy sidebar gradient, stronger heading/button weights, rounded race panels, refined evidence badges and hover/focus feedback. Applied the same treatment to member standings, sign-in and guest arrival pages. Evidence meanings and colors remain intact. Reduced-motion preferences still suppress transitions.

Reviewed a same-state, 1440 × 1000 before/after comparison and phone screenshots. Corrected a dark heading on the navy sign-in panel and missing spacing where its desktop line break is hidden on phones. All 18 captured desktop/phone states had no page overflow or JavaScript errors. The 17 frontend/workspace regression cases passed at widths including 320, 390, 1024 and 1440px; no backend changes or hardware testing are claimed.

- [Styled administrator workspace](images/frontend-final-20261117/styled-admin-live-1440.jpg)
- [Styled phone sign-in](images/frontend-final-20261117/styled-signin-390.jpg)

This follow-up changes CSS and the sign-in heading spacing only. It is not committed or deployed yet.

## Icon and visual detail follow-up

Added self-hosted Feather 4.29.2 icons to navigation, statistics, operation shortcuts, QR camera/upload/recovery controls and key actions. Decorative icons retain the existing text labels and accessible names. Updated the race panel accents, lavender statistic surfaces, heading separators and brand mark. Phone navigation stacks icons above labels. The legacy sign-in arrow illustration now uses the actual Feather send asset.

Upstream SVGs are copied unmodified with their MIT license and a SHA-256 manifest under `backend/dashboard/vendor/feather/`. No CDN, inline SVG, inline style or icon font is required. Attribution: [Feather 4.29.2](https://github.com/feathericons/feather/tree/v4.29.2).

25 unique browser cases passed across frontend polish (10), responsive workspace (9) and QR capture (6). The new checks decode the SVG in the browser and verify navigation and no policy violations at 320/1440px with a strict same-origin content security policy. The initial two failures were the demo fixture's inline login being correctly blocked; removing that helper and initializing demo state through the test driver corrected the fixture. Both security cases then passed. All other 23 cases passed on the initial run. JavaScript syntax and diff whitespace checks passed.

Reviewed a same-state desktop before/after comparison and desktop/phone screen contact sheet. All 18 captured states had no page overflow or JavaScript page errors. Minor follow-up changes replaced the remaining sign-in button text arrow and removed the redundant add-member plus symbol.

- [Dashboard with icons](images/frontend-final-20261117/icons-admin-live-1440.jpg)
- [Phone dashboard with icons](images/frontend-final-20261117/icons-admin-live-390.jpg)
- [QR controls with icons](images/frontend-final-20261117/icons-guest-clock-390.jpg)

These additions are local, not committed or deployed. No hardware, database or official timing changes were made.
