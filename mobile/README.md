# Dove Racing Mobile — Phase 1

Flutter client for the existing FastAPI prototype. No backend migrations or new API routes.

## Features
- Email/password login via POST /auth/login
- Secure token storage via flutter_secure_storage
- Session expiry with a 30-second margin
- Session validation via GET /auth/me
- Administrator club listing via GET /clubs
- Logout and HTTP 401 handling

## Setup

Windows Android pilot builds can use [the isolated build helper](tool/build_android.ps1); see [Android testing](../docs/android-testing.md) for prerequisites, network recovery and phone acceptance. This generates platform scaffolding outside `mobile/` and preserves app source.
Install Flutter stable and Android SDK (Xcode for iOS on macOS). From repository root:

```sh
cd mobile
flutter create --project-name dove_racing_mobile --platforms android,ios .
flutter pub get
flutter analyze
flutter test
flutter run
```

The generated Android/iOS platform scaffolds are not yet committed. Review platform permissions and signing settings before distributing.

## Limitations

Local validation update (7 November 2026): Flutter 3.47.9 / Dart 3.13.7 analysis passed with no issues and all 31 tests passed using an isolated source copy. Android SDK/device builds remain outstanding. See [local SDK setup](../docs/flutter-local-setup.md).

The API client validates `API_BASE_URL` as an HTTPS origin (HTTP is allowed only for explicit localhost/127.0.0.1 testing). Credentials, query strings, fragments and application paths are not accepted in the base URL. Request paths must remain on that origin. Automatic redirects are disabled so authentication requests are not silently redirected; configure the canonical API URL instead. Browser/platform transport behavior still needs device acceptance tests.
- Backend JWTs expire in 30 minutes; no refresh endpoint exists. Re-login is required.
- GET /clubs currently requires administrator privileges.
- No official race clocking, offline timestamp capture, or hardware reader integration in Phase 1.
- Render free tier may sleep; not suitable for official race timing.
- Never screenshot passwords, bearer tokens, or Swagger curl examples.
- Android/device acceptance tests are still required; local analysis and unit tests passed as recorded above.
