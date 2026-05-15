# Release Process

We continuously deploy `main` to production. "Releasing" is the act of
**tagging** a known-good commit so we have a stable rollback target and a
human-readable summary in `CHANGELOG.md`.

## When we cut a release

- Weekly on Tuesdays (low-risk day).
- Ad-hoc whenever a meaningful chunk of work merges.
- Always after a hotfix.

A release is **never** a deploy gate — `main` is always deployable. Tags
record what shipped, not what's about to ship.

## Versioning

[SemVer](https://semver.org): `MAJOR.MINOR.PATCH`.

| Bump | When |
|---|---|
| MAJOR | Breaking change to a public contract: HTTP endpoint shape, JWT claims, env var renamed/removed, webhook payload change |
| MINOR | New endpoint, new field on a response, new env var (with safe default), new config option |
| PATCH | Bug fix, security patch, dependency bump, doc-only release |

Pre-release tags: `1.2.0-rc.1`, `1.2.0-beta.1`. Use these when staging a
risky change behind a feature flag.

## Cut a release

1. Verify CI is green on `main`.
2. Run a manual smoke pass:
   - `/` loads
   - `/business` loads
   - `/kiosk` loads + WebSocket connects
   - One real Stripe test-mode `/pay` end-to-end
3. Update `CHANGELOG.md`:
   - Rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`.
   - Insert a fresh empty `[Unreleased]` block at the top.
   - Group entries under Added / Changed / Deprecated / Removed / Fixed /
     Security.
   - Sanity-check that every PR merged since the last tag is represented.
4. Open a PR titled `release: vX.Y.Z`. Single-purpose PR. CI must pass.
5. Squash-merge.
6. Tag `main`:
   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
7. Create a GitHub Release from the tag, paste the relevant section of
   `CHANGELOG.md` as the body.
8. Announce in the team channel: tag, summary, and any operator-facing
   notes.

## Rollback

Render allows rollback to any previous deploy in the dashboard. Three
options, in order of preference:

1. **Forward-fix.** Identify root cause, write a small revert PR, merge.
   This preserves history and is auditable.
2. **Render rollback.** From the Render dashboard, "Roll back to previous
   deploy." Document the rollback in the incident channel and open an
   issue to track the forward-fix.
3. **Git revert + redeploy.** `git revert <sha> && git push`. Use when
   the bad commit is identifiable but the Render rollback target is older
   than you want.

After any rollback:

- File a postmortem within 48 hours
  (see [`POSTMORTEM_TEMPLATE.md`](./POSTMORTEM_TEMPLATE.md))
- Tag a new PATCH release once the forward-fix is in
- Update `CHANGELOG.md` Security section if the rollback was for a
  vulnerability

## Hotfix flow

See `docs/GIT_WORKFLOW.md` "Hotfixes" — same flow, plus:

- Always cut a PATCH release immediately after the hotfix merges, even if
  it's been < 1 week since the last release.
- Add an entry under `Security` if applicable.

## Database migrations and releases

Migrations are decoupled from releases:

- Migrations run on app startup (today, via `init_db()`; future, via
  Alembic in a Render pre-deploy hook).
- A code release that depends on a new column must ship the migration
  **first**, then the code that uses it. This means a two-deploy sequence
  for non-additive changes:
  1. Release N: add the column with a safe default; old code continues to
     ignore it.
  2. Release N+1: code starts reading/writing the new column.

## Stripe API version pinning

Stripe sends webhook events in your account's API version. When we upgrade
the Stripe Python SDK across a major version, we cut a MAJOR FingerPay
release and document the API-version transition.

## Release checklist (paste into the release PR description)

```
- [ ] CI green on main
- [ ] Manual smoke pass complete (paste evidence)
- [ ] CHANGELOG.md updated with this version
- [ ] No new env vars OR docs/OPERATIONS.md updated
- [ ] No schema changes OR migration shipped in a prior release
- [ ] Stripe webhook handlers tested in test mode (if touched)
- [ ] Operator-facing changes communicated
- [ ] Rollback plan: <one sentence>
```
