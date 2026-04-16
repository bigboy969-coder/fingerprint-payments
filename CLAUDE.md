# CLAUDE.md — Project Instructions

## What this is

FingerPay — a fingerprint-based payment system. FastAPI backend, Stripe
payments, OpenCV biometric matching, vanilla HTML frontend. Deployed on
Render.

## Quick commands

```bash
make setup          # create venv, install deps, install pre-commit hooks
make dev            # uvicorn on :8000 with hot reload
make lint           # ruff check
make format         # black + ruff --fix
make test           # pytest (tests/ directory)
make docker-build   # build the Docker image locally
```

## Project structure

```
app/                    Python application package
  config.py             Env-var loading + validation (read FIRST on any config question)
  main.py               FastAPI app, middleware, lifespan, top-level routes
  db/                   Database layer (split from a single 670-line file)
    connection.py       _get_conn, PH, binary_wrap — internals, don't import from routes
    schema.py           init_db() — all CREATE TABLE DDL
    users.py            User + fingerprint queries
    merchants.py        Merchant queries
    transactions.py     Transaction queries
    sessions.py         Enrollment session queries
    tokens.py           Reset tokens + verification codes
    __init__.py         Re-exports the public API — import from here
  routes/               HTTP + WebSocket handlers
    deps.py             Shared auth helpers (verify_merchant_api_key, get_merchant_from_token)
    enroll.py           Two-device enrollment flow
    authenticate.py     Fingerprint → JWT (rate-limited)
    pay.py              JWT → Stripe charge
    merchants.py        Signup, login, dashboard, Connect, password reset
    customers.py        Self-service portal
    pos.py              WebSocket terminal + POS bridge
  services/             External integrations + domain logic
    biometrics.py       OpenCV ORB extraction + matching
    crypto.py           AES-256-GCM for fingerprint descriptors
    jwt.py              HS256 JWT create/verify
    stripe.py           Stripe API wrappers
    email.py            Resend email sending
static/                 Vanilla HTML/JS pages (no build step)
tests/                  Test scaffold (conftest, fixtures, unit/, integration/)
docs/                   Engineering documentation (25 docs + ADRs + RFCs)
main.py                 Thin entry point — `from app.main import app`
```

## Key conventions

- **Import from `app.db` (the package), not from `app.db.connection` or submodules directly.** The `__init__.py` re-exports everything public.
- **Auth helpers live in `app/routes/deps.py`**, not scattered across route files.
- **All config comes from `app/config.py`**, not from `os.environ` in individual modules.
- **Email sending goes through `app/services/email.py`**, not inline in routes.
- **Conventional Commits** for all commit messages: `feat(scope):`, `fix(scope):`, etc.
- **No `innerHTML` with user-controlled data** in static HTML. Use `textContent`.
- **No PII in logs** (no emails, names, phones, JWTs, API keys).
- **No bare `except:`** — use `except Exception:` at most, and only at boundaries.

## Database

- Dual-backend: SQLite (dev, no `DATABASE_URL`) / PostgreSQL (prod, `DATABASE_URL` set).
- `PH` variable handles placeholder differences (`?` vs `%s`).
- No ORM. Raw SQL with parameterized queries.
- No migration tool yet — schema changes go in `app/db/schema.py`.

## Auth model

Three credential types:
1. **Merchant API key** — SHA-256 hashed at rest. Used for POS/kiosk endpoints.
2. **Merchant JWT** — HS256, 24h TTL, `type=merchant`. Used for dashboard.
3. **Customer JWT** — HS256, 2-min TTL, `type=customer`. Used for `/pay`.

All signed with `FINGERPAY_SECRET`.

## What to read before making changes

1. `docs/ISSUES.md` — known bugs and gaps, prioritized P0–P3
2. `docs/CODING_STANDARDS.md` — style rules
3. `docs/SECURITY.md` + `docs/THREAT_MODEL.md` — what's at risk
4. `docs/ARCHITECTURE.md` — system overview
5. `docs/API.md` — endpoint reference

## What NOT to do

- Don't add dependencies without an ADR or entry in the PR.
- Don't commit `.env` or any file with secrets.
- Don't bypass pre-commit hooks (`--no-verify`).
- Don't add new routes without rate limiting.
- Don't use `innerHTML` with user data in the frontend.
- Don't import `_get_conn`, `_fetchone`, `_fetchall`, or `PH` from outside `app/db/`. Add a public function to the appropriate `app/db/*.py` module instead.
- Don't read env vars directly with `os.environ.get()` in new code. Use `app.config`.
- Don't hard-delete transaction rows on customer deletion — they need pseudonymization for financial records compliance.

## Known critical issues (P0)

These are tracked in `docs/ISSUES.md` and `docs/TODO.md`:

1. **Monthly fee > transaction amount** — Stripe rejects. Decouple the $29 monthly fee from per-transaction `application_fee_amount`.
2. **Connect status sync broken** — `connect_return` path doesn't update status properly. Needs Stripe webhook.
3. **Stored XSS in dashboard** — `full_name` rendered via `innerHTML`. Escape it.
4. **In-memory POS state** — lost on restart. Needs Redis or durable store.
5. **Charge-then-record gap** — if DB write fails after Stripe charge, money is "lost" from the local ledger.

## Environment variables

See `.env.example` for the full list. Critical ones:
- `FINGERPAY_SECRET` — JWT signing key (required, no default)
- `BIOMETRIC_ENCRYPTION_KEY` — 64 hex chars (required)
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` — Stripe keys (required)
- `DATABASE_URL` — Postgres DSN (omit for SQLite dev)
- `APP_BASE_URL` — used in emails and Connect return URLs
- `RESEND_API_KEY` — for transactional email

## Running tests

```bash
make test           # quick: pytest -x -q
make test-cov       # with coverage
```

Tests use SQLite and stub env vars (set in `tests/conftest.py`).

## Documentation

Update docs in the same PR as code changes:
- Endpoint changes → `docs/API.md`
- Schema changes → `docs/DATABASE.md`
- Architecture decisions → new file in `docs/adr/`
- All changes → `CHANGELOG.md` under `[Unreleased]`
