# Local Flutter setup — 7 November 2026

The app source is in `mobile/`. The separately installed SDK is at `C:\Users\admin\develop\flutter` (Flutter 3.47.9, Dart 3.13.7). Flutter/Dart VS Code extensions are installed. The SDK's `bin` folder is on the user PATH; reopen a terminal for that change to take effect. Workspace settings point to this SDK. If VS Code asks to download/clone again, select this existing SDK folder instead.

Verify in a new PowerShell terminal:

```powershell
flutter --no-version-check --version
flutter --no-version-check doctor
```

The optional remote version check stalled on a Git tag fetch during installation. The supported `--no-version-check` flag avoids that check for these commands; it does not disable TLS verification or change SDK source.

Chrome/web tooling is available. Follow-up Android setup installed SDK platform 36, build-tools 36.0.0, platform-tools, NDK 28.2.13676358 and Temurin JDK 21.0.13; Flutter is configured to use them. See [Android build and testing](android-testing.md) for the separate APK acceptance milestone. Visual Studio desktop C++ tooling is still unavailable. Dart ran a minimal program successfully.

The repository's `mobile/lib`, `mobile/test` and `mobile/pubspec.yaml` were copied into the ignored `.pytest-tmp-flutter-local/` directory. A web scaffold was generated there and the generated template widget test was removed. Existing mobile source was preserved.

Validation of that source copy:

- `flutter analyze`: no issues found.
- `flutter test --reporter expanded`: all 27 baseline tests passed; subsequent API origin/redirect hardening added four regression tests, bringing the passing total to 31. Analysis also passed after those changes.
- Flutter Doctor: Flutter, Chrome and network checks passed; Android and native Windows toolchains remain unavailable.

To run the isolated demo from the repository root:

```powershell
cd .pytest-tmp-flutter-local
flutter --no-version-check run -d chrome --dart-define=WEB_PREVIEW=true
```

The demo uses in-memory sample data and does not send changes to Render. The generated workspace is a source snapshot, not a live link: recopy `mobile/lib` and `mobile/test` before validating later edits. No backend server was restarted and no deployment was made.
