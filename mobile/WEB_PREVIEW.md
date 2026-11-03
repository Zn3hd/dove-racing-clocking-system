# Flutter Web PR previews

This project builds a **read-only demonstration preview** of the Flutter UI on every PR touching mobile code. The preview does **not** contact Render or any production database, and it does not support login or writes. It uses `WEB_PREVIEW=true` with a local mock HTTP client. The Android application continues to use the real API by default.

## Automatic checks

The `Flutter web preview` GitHub Actions workflow generates web scaffolding, runs `flutter analyze` and `flutter test`, builds Flutter Web, and uploads the `dove-racing-web-preview` artifact. The existing `Flutter mobile checks` workflow still builds an Android debug APK.

## Enable browser links with Cloudflare Pages (one-time setup)

1. Create a Cloudflare account and a Pages project named, for example, `dove-racing-preview`. Choose **Direct Upload**, not a Git-integrated project.
2. In GitHub repository **Settings → Secrets and variables → Actions**, set:
   - Repository secret `CLOUDFLARE_API_TOKEN`: a Cloudflare token with Pages edit permissions scoped to the project/account.
   - Repository secret `CLOUDFLARE_ACCOUNT_ID`: the Cloudflare account ID.
   - Repository variable `CLOUDFLARE_PAGES_PROJECT`: your exact Pages project name.
3. Open or update a pull request touching `mobile/**`. After checks succeed, the workflow publishes the web demo to a Cloudflare Pages preview branch named `pr-N`. The workflow log reports the deployment URL. Use that URL in your phone browser.

For security, deployment is disabled for forked PRs. Without Cloudflare configuration, analysis, tests and the downloadable web build artifact still run; there will be **no public preview link**.

## Local web demo

```sh
cd mobile
flutter create --project-name dove_racing_mobile --platforms web .
flutter pub get
flutter run -d chrome --dart-define=WEB_PREVIEW=true
```

Do not use `WEB_PREVIEW=true` for production Android builds. The web preview is a UI demonstration, not an integration test of FastAPI, CORS, secure browser token storage, QR camera permissions, or RFID hardware. Use a separate staging backend for real browser integration testing. Do not expose production credentials in PR previews.

## Test sequence

1. PR checks: static analysis, unit tests, web build, Android build.
2. Review Cloudflare Pages browser preview (once configured).
3. Merge only after review.
4. Install Android debug APK for final on-device authentication and hardware testing.

Once GitHub secrets and variables are configured, push a new commit to the PR branch to re-evaluate the Cloudflare deployment condition. A successful web build alone does not mean the deployment step ran.
