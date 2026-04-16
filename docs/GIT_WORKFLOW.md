# Git Workflow

Trunk-based, short-lived branches, squash-merge to `main`, semantic
versioning on releases.

## Branches

- **`main`** — protected. Always deployable. Never push directly.
- **Feature branches** — created from `main`, merged back into `main` via
  squash. Naming:
  - `feat/<short-desc>` — new features
  - `fix/<short-desc>` — bug fixes
  - `chore/<short-desc>` — non-functional cleanup
  - `docs/<short-desc>` — docs only
  - `refactor/<short-desc>` — internal refactor, no behavior change
  - `perf/<short-desc>` — performance
  - `ci/<short-desc>` — CI / build config
  - `security/<short-desc>` — security fixes (private branches if
    pre-disclosure)

Keep branches small and short-lived (< 1 week). Long branches get stale and
merge-conflict.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary, lowercase, no period>

<body — what and why, wrap at 72>

<footer — Refs/Closes/BREAKING CHANGE>
```

Examples:

```
feat(merchants): add Stripe Connect status webhook

Webhook handles account.updated and refreshes merchants.stripe_connect_status
authoritatively. Replaces the broken in-band update path on /connect/return.

Closes: #2
```

```
fix(pay): cap application_fee_amount at amount-1

Stripe rejects PaymentIntents where application_fee_amount > amount.
The monthly $29 fee was bundled per-transaction, breaking every first
small purchase of the month for new-month merchants.

Defer the unbilled portion to a monthly invoice (see ADR-0007).

Closes: #4
BREAKING CHANGE: monthly_fee field removed from /pay response
```

### Allowed types

`feat`, `fix`, `chore`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`,
`security`, `revert`.

### Allowed scopes

Match top-level packages: `enroll`, `auth`, `pay`, `merchants`, `customers`,
`pos`, `db`, `crypto`, `jwt`, `stripe`, `frontend`, `infra`, `docs`,
`deps`.

## Pull requests

- One logical change per PR. < 400 lines diff is the goal.
- Open as **draft** until CI is green.
- Fill out the PR template — every section.
- Self-review the diff before requesting review.
- Required: 1 approval (2 for security-sensitive surfaces — see
  `CODEOWNERS`).
- Required: all CI gates green.
- Squash-merge. The squash commit subject is the PR title; the body is
  auto-collapsed from commits.

### What blocks merge

- Failing CI (lint, format, tests, security scan, docker build)
- Missing test plan in PR template
- Unresolved review comments
- Missing `CODEOWNERS` approval
- Missing `CHANGELOG.md` entry under `[Unreleased]`
- Missing docs update for endpoints/schema changes

### What doesn't block (but should be considered)

- Soft mypy warnings (until baseline passes)
- pip-audit findings on transitive deps with no fix available

## Releases

Semantic versioning: `MAJOR.MINOR.PATCH`.

- **MAJOR** — breaking changes to a public contract (HTTP endpoints,
  webhook payloads, env vars).
- **MINOR** — backwards-compatible feature additions.
- **PATCH** — bug fixes, security patches, dependency updates.

See [`docs/RELEASE_PROCESS.md`](./RELEASE_PROCESS.md) for the cut + deploy
sequence.

## Hotfixes

Critical production bugs:

1. Branch from `main`: `fix/hotfix-<incident-id>`.
2. Smallest possible diff. No drive-by cleanup.
3. PR with `[hotfix]` in the title.
4. Two approvals (or one approval + on-call sign-off).
5. Squash to `main`.
6. Tag a PATCH release.
7. Postmortem opened within 48 hours.

## Reverts

If something broke production and the fix isn't immediate, revert first:

```bash
git revert <sha>
git push
```

Open a PR with the revert. Mark `[revert]` in the title. Reverts skip the
test-plan section but require a "what went wrong" note.

## Things that are forbidden

- `git push --force` to `main`
- `git rebase -i` of merged history
- Committing with `--no-verify` (skip pre-commit hooks)
- Committing `.env` or any file containing a secret
- Long-lived branches (> 2 weeks) that diverge significantly from `main`
- Merge commits to `main` (squash only)
