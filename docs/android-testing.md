# Android test build and device acceptance

This milestone prepares a debug ARM64 APK from `mobile/` using an isolated generated project. It is a pilot build, not a store release or proof of physical clocking accuracy.

## Build locally

The Windows helper requires Flutter, a configured Android SDK, Java and the Android SDK package licenses. From the repository root:

```powershell
& .\mobile\tool\build_android.ps1
```

If your PowerShell policy blocks scripts, inspect the file and run it using a process-only policy override; changing the machine's execution policy is unnecessary:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\mobile\tool\build_android.ps1
```

The helper copies `lib`, `test`, `pubspec.yaml`, `pubspec.lock` and analysis settings into a new ignored workspace, generates Android scaffolding, restores and enforces the reviewed lockfile, configures internet access, disables application backup and cleartext networking, analyzes the app, runs tests and builds an ARM64 debug APK. It prints the output path and SHA-256 checksum. Existing repository platform files and source are not overwritten.

The default build uses the Render API origin, but building does not log in or modify production data. `-ApiUrl` may select an HTTPS staging origin. `-Preview` builds the in-memory demo that bypasses live authentication; demo results do not establish API integration. No API key, device token or administrator password belongs in build arguments.

If the Gradle wrapper download fails, obtain the matching official Gradle binary ZIP and its publisher SHA-256, then pass `-GradleArchive` and `-GradleSha256`. The helper verifies the archive before configuring the generated wrapper to use that local file. Match the distribution version to the generated Android project's Gradle requirements. The first local Gradle 9.3.1 download suffered a connection reset; the binary archive was recovered and verified against the publisher checksum before retrying.

Debug signing and the generated example application ID are for testing only. Use a separate reviewed application ID and release signing process before distribution. Android ARM64 hardware is required for this artifact; it is not an x86 emulator build. The generated platform's minimum Android SDK must also be satisfied by the phone.

## Physical phone acceptance

Latest owner-reader follow-up: version 0.2.0/code 2,
`dist/android/pigeon-racing-owner-reader-20261116-arm64.apk`, SHA-256
`19a2028ef004618096d32b7a7448b989c8085c3ce26f15556ed62ba281a2608d`.
Its signature and packaged network/backup settings were verified. Follow the
[owner reader guide](mobile-owner-reader-guide.md); backend migration 016 is
required. This is a foreground operator/simulator pilot, not certified automatic
arrival capture. Install/use only with an approved test backend and resources.

Latest local RFID simulator build (16 November 2026):
`dist/android/pigeon-racing-rfid-simulator-20261116-arm64.apk`, SHA-256
`023a93546f7caf14d7da8897ef8420a562db0d4ecd29ee290baaa86fb5036fd8`.
Signature and manifest verified; 50 mobile tests passed and the actual
Flutter/FastAPI/PostgreSQL lost-acknowledgement test passed separately. See
[pilot instructions](mobile-rfid-pilot.md). This adds only a foreground simulator;
it does not enable a physical USB/Bluetooth reader or establish iPhone support.

Use an authorized test account and approved test club/race. Do not experiment with another club's live records. Install only the APK supplied by the administrator and verify its checksum before installation. Device-side installation prompts are handled by the tester.

1. Launch the app and confirm the expected build/server with the administrator.
2. Log in using the intended account. Confirm wrong passwords show a useful error and do not retain a session.
3. Confirm an administrator sees only authorized club records. Check member/guest role rejection where management requires administrator privileges.
4. Register one clearly marked test participant, pigeon and draft race, if the test session authorizes these writes. Confirm they appear after refresh and on the web dashboard.
5. Sign out, reopen and confirm private records are no longer displayed. Sign in again, restart the app and verify secure session restoration.
6. Let the session expire and confirm protected actions require reauthentication. There is no refresh-token endpoint.
7. Disconnect internet and confirm the app reports failed requests without claiming a write succeeded. This mobile phase does not provide an offline write queue; inspect server records before retrying an uncertain creation.
8. Test a different account and confirm the prior account's data is not displayed.
9. Record phone model, Android version, APK checksum, API origin, action, expected/actual result and sanitized errors. Never include credentials or bearer tokens in screenshots.

QR camera, physical RFID, offline timestamp acceptance and official results need their own workflows and tests. Installing an APK does not add these capabilities to the Flutter client.

## Current environment

### First completed APK — 7 November 2026

- Build: succeeded (`assembleDebug`, 562.6 seconds after resolving the Gradle archive download issue).
- Local artifact: `dist/android/pigeon-racing-debug-arm64.apk` (84,637,351 bytes; generated and ignored by Git).
- SHA-256: `d698408eae04b07065b03f28fc75214288627d2b2428b27d28b05fae9395d4d7`.
- Package: `com.example.dove_racing_mobile`, version `0.1.0` / code `1`, displayed as **Pigeon Racing (Test)**.
- Minimum SDK 24; target and compile SDK 36. Flutter engine target: ARM64.
- APK signature verified successfully (v2 debug signing).
- Packaged manifest confirms INTERNET permission, application backup disabled and cleartext traffic disabled.
- No phone was connected; installation, real-account sign-in, secure-storage behavior across device restarts and Render integration are not yet physically verified.
- Some dependency native libraries also contain other ABIs; those do not establish Flutter engine support for other architectures in this ARM64 build.

Before sending the file, recheck its checksum. The artifact is a test build and contains the local API safety changes; it does not deploy the separate backend audit fixes to Render. APK compilation does not establish that the live backend contains those fixes.

Local Flutter analysis and 31 unit/API/session/demo tests passed again in the generated Android project. Java 21, Android command-line tools, SDK platforms 34/35/36, build-tools 36.0.0, platform-tools, CMake 3.22.1 and NDK 28.2.13676358 were installed under the user's `develop` directory. JDK and command-line archive checksums were verified; SDK package licenses were accepted during setup. Flutter Doctor passes the Android toolchain check. APK acceptance is recorded above; physical device acceptance remains separate.
