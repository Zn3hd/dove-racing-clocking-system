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
- Backend JWTs expire in 30 minutes; no refresh endpoint exists. Re-login is required.
- GET /clubs currently requires administrator privileges.
- No official race clocking, offline timestamp capture, or hardware reader integration in Phase 1.
- Render free tier may sleep; not suitable for official race timing.
- Never screenshot passwords, bearer tokens, or Swagger curl examples.
- Flutter SDK analysis and device tests are still required.
