
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
