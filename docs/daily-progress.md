
## 2026-10-31 (Asia/Manila)

- 5d371fb Implement ESP32 UART firmware, direct HID capture and guest QR scanning
- 2539ece Add configurable reader profiles and TCP gateway adapter
- 5c422c1 Add loft address labels alongside member GPS coordinates
- 5b5ca6d Add member loft GPS capture and independently verified location workflow
- 26d6db4 Fix validation boundary fixture JSON construction
- b853ec8 Validate suspicious arrivals and enforce simulator result guards
- f22f4c6 Add live provisional race standings and explicit capture provenance
- 6a5df32 Add hardware-independent RFID gateway with durable offline evidence
- d5cc7ee Rename dashboard branding to Pigeon Racing Clocking System
- a01fc1b Add same-origin club administration dashboard and member workflows
- 1245aac Exclude physically rejected arrivals and test complete guest race workflow
- 6a024fc Scope club assets and race administration with guarded management workflows
- 245f575 Harden club membership creation and cover club administration
- 42e7a4e Register club management routes
- d215e04 Enable safe migration 008 for clubs
- f33b289 Implement guarded single-club creation and membership endpoints
- a4cefba Add club and membership schema without changing existing race records
- b6d75c9 Add authenticated password change with current-password verification
- 243aac1 Register one-time admin bootstrap route
- d56a356 Add guarded first-admin bootstrap endpoint
- a9a8cdf docs(deploy): document safe Render migration rollout and recovery
- 5f84915 feat(deploy): add locked, checksum-verified PostgreSQL migration runner

## 2026-11-01 (Asia/Manila)

- 5bd132b Add reader setup and live gateway monitoring
- 703b614 Complete QR clocking reliability and race administration workflows
- 5d371fb Implement ESP32 UART firmware, direct HID capture and guest QR scanning
- 2539ece Add configurable reader profiles and TCP gateway adapter
- 5c422c1 Add loft address labels alongside member GPS coordinates
- 5b5ca6d Add member loft GPS capture and independently verified location workflow
- 26d6db4 Fix validation boundary fixture JSON construction
- b853ec8 Validate suspicious arrivals and enforce simulator result guards
- f22f4c6 Add live provisional race standings and explicit capture provenance
- 6a5df32 Add hardware-independent RFID gateway with durable offline evidence
- d5cc7ee Rename dashboard branding to Pigeon Racing Clocking System
- a01fc1b Add same-origin club administration dashboard and member workflows
- 1245aac Exclude physically rejected arrivals and test complete guest race workflow
- 6a024fc Scope club assets and race administration with guarded management workflows

## 2026-11-04 (Asia/Manila)

- 1f27377 Cover pigeon edits, validation, duplicates, isolation and reset
- 6e01a41 Open pigeon edit screen from demo club list
- bbd94be Add pigeon edit form and confirmation for browser sandbox
- 842500f Add pigeon preview update API helper
- fb6bcf9 Add validated preview-only pigeon update with duplicate ring checks
- 8d13d28 Flutter Web: edit demo participants with confirmation and validation (#6)
- f8d6d4c Flutter Web: interactive isolated club-management sandbox (#5)
- 22c6e71 Flutter Web: safe read-only PR previews with optional Cloudflare Pages deployment (#4)
- 417a3c8 Test authenticated management requests and club scoping
- 8f3b693 Add club management navigation and refresh after registration
- a2ccdee Prefill race validation speed defaults
- 298671b Implement authenticated participant, pigeon and draft race forms
- 7b0a147 Add authenticated club management create APIs and loft listing
- 3cf60df Test chairman permissions and scoped dashboard API requests
- 35e42ad Support chairman and president dashboards with read-only club records
- 99dccc3 Expose authorized participant, pigeon and race listing API calls
- a0d0315 Remove generated MyApp template test before Flutter analysis
- 4d7748d Fix Dart interpolation analyzer lint
- 4d3c715 Remove unused Flutter test import
- d0603b9 Flutter Phase 1: add API/session tests and Android build CI
- 8f4b117 Flutter Phase 1: add API/session tests and Android build CI
- 35d84f5 Flutter Phase 1: add API/session tests and Android build CI
- 7da0b29 Fix session cleanup after failed account verification and unauthorized dashboard
- d0d45fc Allow configurable HTTPS API URL for Flutter builds
- 2c85688 Flutter Phase 1: implement sign-in and club dashboard
- f77a9ad Flutter Phase 1: add mobile/README.md
- bcd8e07 Flutter Phase 1: add mobile/lib/session.dart
- 2b73bf1 Flutter Phase 1: add mobile/lib/api.dart
- f7918bc Flutter Phase 1: add mobile/pubspec.yaml
