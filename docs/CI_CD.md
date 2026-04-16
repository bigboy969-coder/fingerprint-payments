# CI / CD

## CI (every PR + every push to main)

Defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

| Job | What it does | Gate |
|---|---|---|
| `lint` | ruff, black --check, mypy | Hard (mypy soft until baseline) |
| `test` | pytest with seeded test env vars | Hard once tests exist |
| `security` | pip-audit, gitleaks | Soft (advisory) |
| `docker-build` | Build the Dockerfile, no push | Hard |

CI runs on Ubuntu, Python 3.11, with caching for pip and Docker layers.

### Concurrency

`concurrency.group: ci-${ref}` with `cancel-in-progress: true`. Pushing a
new commit cancels the in-flight CI for the same branch — no wasted minutes.

### Required checks (set in GitHub branch protection)

- `lint`
- `test`
- `docker-build`
- At least one `CODEOWNERS` approval
- All conversations resolved

### Things CI does NOT do today

- Run E2E tests against a deployed environment.
- Deploy on merge — Render watches `main` and deploys itself.
- Push the Docker image to a registry. The image is built for verification,
  then discarded.
- Tag releases. See [`docs/RELEASE_PROCESS.md`](./RELEASE_PROCESS.md).

## CD

The hosted production deployment is **Render**. Render watches the `main`
branch on GitHub and auto-deploys on every push.

### Deploy pipeline (current)

```
PR merged to main
  ↓
GitHub webhooks → Render
  ↓
Render builds the Dockerfile
  ↓
Render rolls the new image into the web service
  ↓
Health check passes → traffic cut over
  ↓
Old instance drained
```

There is **no preview deploy per PR** today.

### Recommended next iterations

| Step | Why |
|---|---|
| Push Docker image to GHCR with each main build | Reproducible deploy artifact, rollback by tag |
| Per-PR preview environment | Catch regressions before merge |
| Smoke-test job that hits the preview URL | Block merge if `/healthz` fails |
| Scheduled production smoke run (every 15 min) | Independent uptime signal |
| Deploy notifications to a team channel | Visibility |

## Branch protection (required settings)

In the GitHub repo settings, `main` should have:

- Require a pull request before merging
- Require approvals: 1 (2 for security paths via `CODEOWNERS`)
- Dismiss stale reviews when new commits are pushed
- Require review from `CODEOWNERS`
- Require status checks to pass: `lint`, `test`, `docker-build`
- Require branches to be up to date before merging
- Require conversation resolution before merging
- Require signed commits: optional but recommended
- Require linear history (squash-merge enforces this)
- Restrict who can push to matching branches: only the deploy bot, no
  humans

## Secrets in CI

- `GITHUB_TOKEN` — auto-provisioned, used by gitleaks and dependabot.
- No `STRIPE_SECRET_KEY`, no `BIOMETRIC_ENCRYPTION_KEY`, no
  `FINGERPAY_SECRET` in CI. Tests use deterministic stubs.
- If CI ever needs production-like secrets (e.g., for an E2E job),
  store them in GitHub Environments with required reviewers, not in repo
  secrets.

## Troubleshooting CI

**`lint` fails with import-order issues**
Run `ruff check --fix .` locally and commit.

**`black --check` fails**
Run `black .` locally and commit. Pre-commit usually catches this before
push.

**`docker-build` fails**
Almost always a missing apt package or Python dep. Reproduce locally with
`docker build -t fingerpay:test .`.

**`security` job flags a CVE**
Check if a fixed version exists. If yes, bump in `requirements.txt` /
`pyproject.toml`. If no, comment in the PR with the CVSS score and a risk
acceptance rationale; CTO sign-off required to merge.

## Backstage / observability of CI

- GitHub Actions tab is the source of truth.
- Failing main-branch CI pages the on-call (once that's wired).
- Weekly review: check median CI duration, flake rate, and the security
  job's findings.
