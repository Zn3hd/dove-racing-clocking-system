# Live Messenger clocking: deployment checklist

The Messenger adapter is implemented but is NOT live until the Meta app,
Facebook Page, HTTPS backend, and secrets are configured.

## Prerequisites
- A Facebook Page managed by the club and a Meta developer app with the
  required Messenger product and permissions (check current Meta requirements).
- A publicly reachable HTTPS FastAPI backend with PostgreSQL migrations
  001 through 007 applied. GitHub Actions CI is not a production host.
- A unique, strong `META_APP_SECRET` from the Meta app settings.
- A separate random `META_VERIFY_TOKEN` (at least 32 characters).
- The Page's numeric ID in `META_PAGE_ID`.
- Never commit tokens, Page access tokens, or app secrets to GitHub.

## Backend configuration
Set these **server-side** environment variables in the hosting provider:
```text
META_APP_SECRET=<from Meta app dashboard>
META_VERIFY_TOKEN=<random secret >= 32 chars>
META_PAGE_ID=<Facebook Page ID>
```
Do not add a Page access token until an outbound reply feature is implemented;
the current adapter only ingests incoming webhook events.

## Meta webhook configuration
- Callback URL: `https://YOUR_BACKEND_HOST/clocking/messenger/webhook`
- Verification token: exactly the value of `META_VERIFY_TOKEN`
- Subscribe the app/Page to the applicable Messenger message event.
- GET verifies the Meta challenge; POST verifies the raw-body
  `X-Hub-Signature-256` before reading a message.
- Meta app mode, permissions and Page subscription determine whether
  messages from real club members can reach the webhook.

## Controlled pilot
1. Create a guest account, loft, pigeon and race entry in the backend.
2. Club official issues a race-bound QR token and activates the race.
3. Club official explicitly links the guest's Page-scoped sender ID (PSID)
   using authenticated `POST /clocking/messenger/links` with
   `page_id`, `sender_psid`, and `user_id`.
   **Never treat a Facebook display name as proof of identity.**
4. From the linked account send exactly:
   ```text
   CLOCK <entry_uuid> <qr_token>
   ```
5. Inspect the provisional clocking event and its source metadata using
   `GET /clocking/events/{event_id}/source` as an administrator.
6. Confirm the arrival is NOT official without the club's in-person
   verification workflow. Repeat the webhook delivery and confirm no
   second clocking event is created.

## Security and operational limitations
- QR tokens are bearer credentials; avoid publishing them in group chats.
- The adapter has no automated Messenger reply or PSID self-enrollment.
- Real Meta messages and permissions must be tested on a deployed HTTPS host.
- For production readiness add a durable webhook inbox, event-level
  processing/retry isolation, request-rate limits, monitoring and retention
  policy. Do not assume all Meta retries are harmless.
- A Facebook message timestamp is not a trusted pigeon-arrival time.
