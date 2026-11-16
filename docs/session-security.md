# Password-change session revocation

Local development checkpoint: 14 November 2026. Not deployed.

Migration `015_user_session_version.sql` adds a nonnegative account session
version, initially zero. Login embeds that version in the signed JWT. Every
authenticated request compares it with the current database value and rejects
missing, malformed or superseded versions with HTTP 401.

Changing a password locks the active account, verifies the current password,
then updates its hash and increments the session version in the same transaction.
All tokens from earlier versions are rejected on their next authenticated
request, including the token used to change the password. Failed changes do not
increment the version or invalidate sessions. Concurrent changes using the same
old password have one winner. Other accounts are unaffected.

The dashboard clears its current session after success. Other browser sessions
return to sign-in when their next authenticated request receives HTTP 401.
Reauthentication with the new password returns a token for the latest version.

## Deployment requirements

- Back up the database, then apply migration 015 before starting this backend.
  The existing migration runner now expects ordered migrations 001–015.
- Plan for everyone to sign in again. Tokens issued by older releases have no
  session-version claim and are rejected by this release.
- Run one backend version consistently during cutover. Old backend processes
  do not enforce revocation; stop them before claiming that it is active.
- If reverting the application, the additive database column may remain, but
  older code will no longer enforce session revocation. Do not present that
  rollback as preserving this protection.

This does not cancel requests that already passed authentication, revoke
independent reader credentials, implement forgotten-password recovery, or verify
production credential rotation/bootstrap settings. Device credentials retain
their separate existing rotation and revocation workflow.

## Local verification

Tested against a fresh, loopback-only PostgreSQL 16 container. Migrations 001–015
applied successfully; a second startup verified their checksums and skipped
already-applied files.

- Full backend suite: 130 passed, including nine new session-version cases.
  Report: `backend/.pytest-tmp-session-20261114/results.xml`.
- Focused session-security follow-up: all ten cases passed, including the
  additional concurrent-password-change test. These overlap the full suite.
  Report: `backend/.pytest-tmp-session-followup-20261114/results.xml` also
  records an initial browser assertion failure; it is not an all-green report.
- Corrected real Edge browser test: one passed. Two independent browser
  contexts logged in, one changed the password, the other received HTTP 401
  and returned to sign-in, then successfully logged in with the new password.
  Report: `backend/.pytest-tmp-session-browser-final-20261114/results.xml`.

The browser assertion initially attempted to read a variable outside its module
scope. The corrected check observes the actual `/clubs` response and UI; no
application behavior was changed to make the assertion pass.

CI now applies migration 015 and includes the new browser regression. No
production database, Render settings, commit or deployment was changed here.
