# Changelog

All notable changes to FingerPay will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **65-test suite**: 40 unit tests (crypto, JWT, biometrics, stripe, config) +
  25 integration tests (enrollment, merchant lifecycle, customer portal, health).
- `docs/DEFERRED.md` — 8 consciously deferred items with unblock criteria.
- Engineering documentation suite under `docs/`.
- Root governance files (`CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`,
  GitHub issue/PR templates, CI workflow, dependabot config).
- Repo scaffolding: `.editorconfig`, `.env.example`, `Makefile`,
  `pyproject.toml` (alongside existing `requirements.txt`),
  `.pre-commit-config.yaml`.
- Architecture Decision Records (`docs/adr/`) with seed ADRs covering the
  current architecture and the planned hardening direction.
- Stripe webhook endpoint (`POST /webhooks/stripe`) with signature
  verification. Handles `account.updated`, `payment_intent.payment_failed`,
  `charge.dispute.created`, `charge.refunded`.
- Health endpoints: `/healthz` (liveness) and `/readyz` (DB check).
- Rate limiting on all auth endpoints: `/merchants/login` (5/min),
  `/merchants/signup` (3/min), `/merchants/forgot-password` (3/min),
  `/customers/request-access` (3/min), `/customers/verify-code` (5/min).
- JWT type check: `verify_access_token` now rejects non-customer tokens
  with a clean 401 instead of a 500 KeyError.
- `merchant` field removed from `/pay` request body — name derived
  server-side from JWT's `merchant_id`.
- Email enumeration fixed on `/enroll/start` — generic error message.
- PII scrubbed from email service logs.
- Email sending moved from daemon threads to FastAPI `BackgroundTasks`.
- WebSocket terminal auth moved from URL query string to first-message
  pattern — API key no longer leaks into URL logs.
- Stripe idempotency key now derived from transaction row ID — retries
  won't create duplicate charges.
- Upload size middleware improved: validates `Content-Length` header
  presence and value; documents reverse-proxy reliance for chunked uploads.
- Merchant JWT moved from `localStorage` to HttpOnly Secure SameSite=Strict
  cookie. Eliminates XSS token theft surface. `POST /merchants/logout` added.
- Postgres connection pool: `psycopg2.pool.ThreadedConnectionPool`
  (min=1, max=10). No more fresh connection per request.
- DB indexes via Alembic migration: `transactions(merchant_id, created_at)`,
  `transactions(user_id)`, `merchants(api_key_hash)`,
  `customer_verification_codes(email, code, used)`, `fingerprints(user_id)`.
- FK constraints: `fingerprints.user_id`, `transactions.user_id`,
  `transactions.merchant_id`.
- All timestamps standardized to UTC (`datetime.now(timezone.utc)`).
- Pagination: `get_merchant_customers` and `get_merchant_recent_transactions`
  accept `limit`/`offset` params.
- Cleanup service: stale enrollment sessions, expired tokens/codes,
  orphan temp uploads — runs on startup.
- Structured logging via `structlog` (JSON output). Request-ID middleware
  generates per-request trace ID, returned in `X-Request-ID` header.

### Changed
- README rewritten to point at `docs/`.
- Restructured codebase from flat `pipeline/`, `routes/`, `utils/` to
  `app/` package with `db/`, `routes/`, `services/` subpackages.
- Consolidated three deploy configs to a single `Dockerfile`.

### Fixed
- **P0 #4:** Monthly $29 terminal fee no longer bundled into per-transaction
  `application_fee_amount`. Stripe would reject small transactions where
  fee > amount. Fee is now per-transaction only (0.5% + $0.05). Monthly
  billing deferred to out-of-band mechanism. (ADR-0006)
- **P0 #6:** Pay route now inserts a `pending` transaction row before
  calling Stripe, then updates it with the result. Eliminates the gap where
  money was charged but no local record existed.
- **P0 #2:** Connect status sync fixed. Return URL now carries the Stripe
  account ID. Dashboard self-heals by re-fetching from Stripe when local
  status is `pending`. Inline sqlite3 hack removed.

### Security
- **P0 #7:** Fixed stored XSS in merchant dashboard and customer portal.
  All user-controlled fields now HTML-escaped via `escapeHtml()`.
- Added security headers middleware: CSP, X-Frame-Options DENY,
  X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin.
- **P0 #1/#3/#8:** Env validation proven with 8 unit tests. App refuses to
  boot without required secrets.
- The known-issue catalog in
  [`docs/ISSUES.md`](./docs/ISSUES.md) lists the remaining P0–P3 items being worked
  on.

---

## How to add an entry

When you open a PR, add a bullet under `[Unreleased]` in the section that
matches your change:

- **Added** — new features.
- **Changed** — behavioral changes to existing features.
- **Deprecated** — features that will be removed in a future release.
- **Removed** — features removed in this release.
- **Fixed** — bug fixes.
- **Security** — vulnerabilities, hardening, key rotations.

At release time, the `[Unreleased]` section is renamed to
`[X.Y.Z] - YYYY-MM-DD` and a fresh `[Unreleased]` is created at the top.
See [`docs/RELEASE_PROCESS.md`](./docs/RELEASE_PROCESS.md).
