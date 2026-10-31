# Development roadmap

The owner's planning estimate is 60% overall. Percentages are not acceptance
criteria and have not been validated by a full repository and deployment audit.

## Current foundation audit

- Architecture: FastAPI, PostgreSQL, SQL migrations, and CI exist.
- Security: JWT login, protected administrator endpoints, password changes,
  and guarded first-admin setup exist. Password changes do not revoke existing
  JWTs. Rotation of exposed credentials and removal of the Render
  `ADMIN_BOOTSTRAP_SECRET` variable have not been verified.
- Clubs: creation, administrator membership, listing, and member assignment
  exist. Duplicate assignments are handled atomically. Migration 008 adds a
  nullable race club relationship. Race administration and evidence access now
  enforce club administrator membership; historical races remain creator-only.
  Club race entries require active owners who belong to the club. The new
  PostgreSQL isolation scenarios passed in GitHub Actions for commit `6a024fc`
  (46 tests passed across the complete suite).
- Participants: member/guest creation, loft creation/verification, and pigeon
  registration exist. Club-scoped listing/editing, atomic account membership,
  coordinate verification reset, and unfinished-race editing guards are added.
  Assets inherit club scope through owner membership. Legacy global asset
  access remains only before the first club is created.
- Races and clocking: registration, activation, provisional arrivals, review,
  and guarded closing exist. Physically rejected arrivals are excluded from
  previews; physical confirmation is displayed separately from timing trust.
  A full club-to-guest-race integration scenario is added. Official finalization
  deliberately remains disabled, including after physical guest confirmation.
- Dashboard: the first same-origin web administration milestone is implemented
  at `/dashboard/`: login, club creation, member/guest directory and creation,
  account linking, contact editing, and password changes. Loft, pigeon, race,
  and evidence screens remain outstanding. Browser visual QA is unavailable in
  the current environment; API workflow and static delivery tests are included.
- QA: unit/API tests and disposable PostgreSQL CI exist. Local PostgreSQL
  integration execution remains unavailable in the current environment.
- Deployment: Render health, Swagger, and club route presence were checked;
  this does not prove database migrations or race workflows succeed.

## Next milestones, in order

1. Complete security cleanup: rotate the exposed administrator password and JWT
   secret privately, remove bootstrap environment credentials, verify setup is
   disabled, and test token invalidation behavior. Never put secrets in this file.
2. Finish club ownership: scope race creation, listing, reads, and every write
   path to club administrators. Include entries, review, results, finalization,
   device administration, and clocking source routes in the permission audit.
   Race/evidence checks, device provisioning, Messenger account administration,
   participant management, and membership checks during guest/provider ingestion
   are implemented and passed PostgreSQL CI in commit `6a024fc`.
3. Connect participants and assets: define club membership requirements for
   lofts/pigeons, enforce them during registration, and add scoped management
   and editing workflows. Preserve historical race coordinate snapshots.
4. Test one complete race against disposable PostgreSQL: create club, assign
   accounts, verify lofts, register pigeons, open/register/release, record arrival,
   verify evidence, calculate/rank, finalize, and reject unauthorized changes.
5. Build the dashboard around the completed workflows.
6. Complete reliability, hardware integration, operational monitoring, backup
   recovery, and production acceptance checks before launch.

## Club migration acceptance criteria

- Define an explicit reviewed policy for existing races with null club IDs;
  do not silently attach historical records to the first club.
- Deny unrelated administrators and members access to club-owned records.
- Require the pigeon owner to belong to the race's club.
- Apply the same policy to direct UUID lookups and alternate clocking routes.
- Test permission failures and successful flows against real PostgreSQL.
- Do not mark tenant isolation complete based only on the `/clubs` endpoints.
