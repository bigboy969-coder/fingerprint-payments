# Contributing to FingerPay

Thanks for working on FingerPay. Read this in full before your first PR.

## Ground rules

1. **This is a payments + biometrics codebase.** Defects can charge real cards
   or leak real biometric data. Treat every change accordingly.
2. **Read [`docs/SECURITY.md`](./docs/SECURITY.md), [`docs/THREAT_MODEL.md`](./docs/THREAT_MODEL.md), and [`docs/ISSUES.md`](./docs/ISSUES.md) before writing code.**
   Don't reintroduce a known issue.
3. **No secrets in commits.** Ever. Use `.env` locally; it's gitignored. If
   you commit a key by accident, rotate it immediately and notify the
   security owner in `CODEOWNERS`.

## Local setup

See [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) for the full setup. Short
form:

```bash
make setup       # creates venv, installs deps, installs pre-commit hooks
cp .env.example .env  # fill in values
make dev         # runs uvicorn with reload
```

If `make` is not available, see the `Makefile` for the underlying commands.

## Branching

See [`docs/GIT_WORKFLOW.md`](./docs/GIT_WORKFLOW.md). Short form:

- `main` is protected and always deployable.
- Feature branches: `feat/<short-desc>`, `fix/<short-desc>`,
  `chore/<short-desc>`, `docs/<short-desc>`.
- Open a draft PR early. Mark ready-for-review when CI is green.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): short imperative summary

Optional body — what and why, not how.

Refs: #123  (or "Closes: #123")
```

Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`,
`build`, `ci`, `revert`. Allowed scopes match the top-level package: `enroll`,
`auth`, `pay`, `merchants`, `customers`, `pos`, `db`, `crypto`, `jwt`,
`stripe`, `frontend`, `infra`, `docs`.

## Pull requests

- One logical change per PR. If you find unrelated bugs, open separate PRs.
- Fill out the PR template completely. The "Test plan" section is mandatory.
- All CI checks must be green before review.
- At least one approval from a `CODEOWNERS` entry is required.
- Squash-merge into `main`. The squash commit subject must follow
  Conventional Commits.

### What a good PR looks like

- Small (< 400 lines diff if possible).
- Includes tests for new logic, regression tests for fixes.
- Updates docs touched by the change (`docs/API.md` if endpoints changed,
  `docs/DATABASE.md` if schema changed, `CHANGELOG.md` always).
- No commented-out code, no debug prints, no TODOs without an issue link.

### What gets blocked at review

- Adding a new external dependency without an entry in
  [`docs/TECH_RADAR.md`](./docs/TECH_RADAR.md) (or an ADR).
- Schema changes without an Alembic migration (once Alembic is adopted).
- New endpoints without rate limiting or auth.
- Logging that contains PII.
- New `innerHTML` writes in the static frontend.
- Direct imports from `app/db/connection.py` internals (`_get_conn`, `_fetchone`, `PH`) — use the public API in `app/db/__init__.py`.

## Security-sensitive changes

Changes to any of the following require **two** reviewers, one of whom must
be a security owner (see `CODEOWNERS`):

- `app/services/crypto.py`, `app/services/jwt.py`, `app/services/stripe.py`
- Anything under `app/db/` (database access) or `app/services/biometrics.py`
- `app/routes/authenticate.py`, `app/routes/pay.py`, `app/routes/merchants.py` (Connect),
  `app/routes/customers.py` (deletion), `app/routes/deps.py` (auth helpers)
- `app/config.py` (env-var handling)
- Any change to env-var handling
- Any new route added without auth

## Reporting a vulnerability

Do **not** open a public issue. See [`SECURITY.md`](./SECURITY.md) for the
disclosure process.

## Style

- Python: ruff + black, enforced via pre-commit (see
  `.pre-commit-config.yaml`).
- Type hints: required on public functions, encouraged on private. mypy in
  `pyproject.toml`.
- Docstrings: short, one-line summary unless WHY is non-obvious. Don't
  restate what well-named code already says.
- Frontend (vanilla JS): keep functions small, no inline event handlers in
  new code, prefer `textContent` over `innerHTML`.

See [`docs/CODING_STANDARDS.md`](./docs/CODING_STANDARDS.md) for the full
detail.

## Documentation

If your change touches behavior visible to a user (customer, merchant,
operator, or another engineer), update the corresponding doc in the same
PR. Docs and code drift the moment they're allowed to.

## Code of conduct

Be kind. Disagreements about code are welcome; disagreements about people
are not.
