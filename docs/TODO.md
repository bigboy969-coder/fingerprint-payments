# Development TODO

Master checklist for bringing FingerPay to production. Each item maps to an
issue in `ISSUES.md` and/or a ROADMAP sprint. Check off as completed, with
the PR number.

---

## Phase 1 — Stop the bleeding (P0s)

These are ship-blockers. Nothing else starts until these are done.

- [x] **#1/#3/#8 — Env validation at boot** `app/config.py` *(fixed)*
  - [x] `validate_env()` exists and is called in lifespan *(done in restructure)*
  - [x] JWT no longer defaults to `"dev-secret-change-in-prod"` *(done — reads from config, empty string if unset)*
  - [x] Verify: app refuses to start with empty `.env` *(tested)*
  - [x] Add test: 8 tests in `tests/unit/test_config.py`

- [x] **#4 — Monthly fee exceeds transaction amount** *(fixed)*
  - [x] Decouple $29 monthly fee from per-transaction `application_fee_amount`
  - [x] Write ADR for the chosen approach → `docs/adr/0006-decouple-monthly-fee-from-transactions.md`
  - [x] Add test: 8 tests in `tests/unit/test_stripe.py`
  - [ ] Future: build out-of-band monthly billing (Stripe Invoice or cron)

- [x] **#2 — Connect status sync broken in production** *(fixed)*
  - [x] `connect_return` no longer imports `DB_PATH` or uses raw `sqlite3` *(done in restructure)*
  - [x] Pass merchant Connect account ID in the return URL query param
  - [x] `connect_return` calls `update_merchant_connect_status_by_account()` via proper DB API
  - [x] Dashboard `/me` re-fetches Connect status from Stripe when local is `pending` (self-healing)
  - [x] `update_merchant_connect_by_account` inline function removed, replaced by `app/db/merchants.py` function
  - [ ] Add Stripe webhook for `account.updated` (Phase 2 — tracked in #16)
  - [ ] Add test: `test_connect_return_updates_status` (Phase 4)

- [x] **#7 — Stored XSS in merchant dashboard** *(fixed)*
  - [x] Add `escapeHtml()` helper + escape all user data in `merchant-dashboard.html`
  - [x] Add `escapeHtml()` helper + escape all user data in `customer-portal.html`
  - [x] Add CSP + X-Frame-Options + X-Content-Type-Options + Referrer-Policy headers via middleware
  - [x] Audited all `static/*.html` — `kiosk.html` innerHTML is QR container only (safe)

- [x] **#5 — POS state in-memory (pilot constraint)** *(documented)*
  - [x] Dockerfile comment explaining single-worker constraint + ADR-0005 reference
  - [x] Startup warning if `WEB_CONCURRENCY != 1`
  - [x] Graceful-shutdown handler logs pending POS transactions + disconnecting terminals
  - [ ] *(Deferred to Phase 3: Redis migration for horizontal scaling)*

- [x] **#6 — Money charged but no DB row** *(fixed)*
  - [x] `create_pending_transaction` inserts row with `status=pending` BEFORE Stripe call
  - [x] `update_transaction_result` updates with Stripe intent ID + status after
  - [x] On Stripe failure: pending row marked `failed`
  - [x] On post-charge DB failure: `CRITICAL` log with tx ID + Stripe PI ID for reconciliation
  - [ ] Add test: `test_transaction_row_exists_before_charge` (Phase 4)

---

## Phase 2 — Pilot-readiness (P1s)

- [x] **#11/#12 — Rate limiting on all auth endpoints** *(done)*
  - [x] `/merchants/login` — 5/min
  - [x] `/merchants/signup` — 3/min
  - [x] `/merchants/forgot-password` — 3/min
  - [x] `/customers/request-access` — 3/min
  - [x] `/customers/verify-code` — 5/min

- [x] **#17 — JWT type check on `/pay`** *(done)*
  - [x] `verify_access_token` checks `type == "customer"`, rejects merchant tokens with ValueError
  - [x] 7 tests in `tests/unit/test_jwt.py` covering type separation

- [x] **#16 — Stripe webhooks (full pass)** *(done)*
  - [x] Created `app/routes/webhooks.py`
  - [x] `STRIPE_WEBHOOK_SECRET` in config + `.env.example`
  - [x] `account.updated` → refresh Connect status
  - [x] `payment_intent.payment_failed` → mark tx failed
  - [x] `charge.dispute.created` → log warning
  - [x] `charge.refunded` → update tx status
  - [x] Signature verification via `stripe.Webhook.construct_event`
  - [ ] Add test: `test_webhook_rejects_bad_signature` (Phase 4)

- [x] **#14 — Email enumeration on `/enroll/start`** *(done)*
  - [x] Returns 400 with generic message (no email leak)

- [x] **#19 — Client-controlled `merchant` field in `/pay`** *(done)*
  - [x] Removed `merchant` from `PayRequest` body
  - [x] Merchant name derived server-side from `merchant_id` via JWT

- [x] **#18 — Move email send to BackgroundTasks** *(done)*
  - [x] Replaced daemon threads with FastAPI `BackgroundTasks`
  - [x] `send_reset_email` and `send_verification_email` accept `bg: BackgroundTasks`

- [ ] **#15 — Verify Resend domain + custom from-address**
  - [ ] Register domain in Resend (ops task — not code)
  - [ ] Update from-address in `app/services/email.py`

- [x] **#13 — API key out of WebSocket URL** *(done)*
  - [x] First-message auth: client sends `{"type":"auth","api_key":"..."}` within 5s
  - [x] Server responds `{"type":"auth_ok"}` on success, closes on failure
  - [x] Updated `static/kiosk.html` WebSocket client

- [ ] **#20 — SCA / 3DS recovery for off-session charges**
  - [ ] Detect `requires_action` PaymentIntent status
  - [ ] Return actionable error with recovery URL
  - [ ] *(Deferred — requires Stripe test-mode validation with European test cards)*

- [x] **#21 — Fix idempotency key** *(done)*
  - [x] `charge_customer` accepts `idempotency_key` param
  - [x] Pay route passes `f"fingerpay-tx-{pending_tx['id']}"` — stable per logical operation

- [x] **#22 — Upload size middleware bypass** *(done)*
  - [x] Content-Length validated when present (including invalid value check)
  - [x] Documented reliance on reverse proxy for chunked uploads
  - [x] Comment directs route handlers to validate file size after reading

- [x] **#23 — PII in application logs** *(done)*
  - [x] Email removed from email service log
  - [x] Audited all `logger.*` calls — no PII remains

- [x] **Pin dependencies** (#26) *(done)*
  - [x] All deps pinned with compatible-release (`~=`) in `requirements.txt`

- [x] **Add `/healthz` and `/readyz`** (#36) *(done)*
  - [x] `/healthz` returns `{"status": "ok"}`
  - [x] `/readyz` pings DB with `SELECT 1`, returns 503 on failure

- [x] **Alembic adoption** (#29) *(done)*
  - [x] `alembic` installed and added to requirements.txt
  - [x] `alembic init` run, `env.py` configured to read `DATABASE_URL` from env
  - [x] Baseline migration created: `9db10166ac38_baseline_schema.py`
  - [ ] Add `alembic upgrade head` to Render pre-deploy hook (ops task)
  - [ ] Write ADR (track separately)

---

## Phase 3 — Hardening (P2s)

- [ ] **#9/#10 — Biometric matcher decision** *(deferred — requires vendor evaluation, see PLAN.md)*
- [ ] **Move POS state to Redis** (#5, full) *(deferred — requires infra provisioning, see ADR-0005)*

- [x] **Connection pool for Postgres** (#27) *(done)*
  - [x] `psycopg2.pool.ThreadedConnectionPool` (minconn=1, maxconn=10)

- [x] **DB indexes** (#28) *(done)*
  - [x] Alembic migration `4305639accaa`: indexes on `transactions(merchant_id, created_at)`, `transactions(user_id)`, `merchants(api_key_hash)`, `customer_verification_codes(email, code, used)`, `fingerprints(user_id)`

- [x] **Pagination** (#30) *(done)*
  - [x] `get_merchant_customers` — limit=50, offset=0 params
  - [x] `get_merchant_recent_transactions` — limit=20, offset=0 params

- [x] **Cleanup jobs** (#31, #32) *(done)*
  - [x] `app/services/cleanup.py` — stale sessions, expired tokens, expired codes, orphan uploads
  - [x] Runs on startup via lifespan

- [x] **Time zone normalization** (#33) *(done)*
  - [x] All 12 `datetime.now()` / `datetime.utcnow()` calls → `datetime.now(timezone.utc)`
  - [ ] Migrate Postgres columns to `TIMESTAMPTZ` (future Alembic migration when DB is live)

- [x] **FK constraints** (#34) *(done)*
  - [x] Alembic migration `4305639accaa`: FK on `fingerprints.user_id`, `transactions.user_id`, `transactions.merchant_id`

- [x] **Structured logging + request ID** *(done)*
  - [x] `structlog` with JSON output
  - [x] Request-ID middleware: generates 8-char ID, binds to structlog context, returns in `X-Request-ID` header
  - [ ] Sentry SDK (ops task — needs account)

- [x] **Security headers** *(done in Phase 1)*
  - [x] CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
  - [ ] HSTS (ops task — needs custom domain with TLS)

- [x] **Merchant JWT → HttpOnly cookie** *(done)*
  - [x] Login/signup set `merchant_token` cookie (HttpOnly, Secure, SameSite=Strict, 24h)
  - [x] `get_merchant_from_token` reads cookie first, header fallback
  - [x] `POST /merchants/logout` clears cookie
  - [x] Dashboard, login, signup pages — `localStorage` usage removed

---

## Phase 4 — Test suite

- [x] **Unit tests (40 tests)** *(done)*
  - [x] `tests/unit/test_crypto.py` — 7 tests: round-trip, nonce uniqueness, tampering, missing key
  - [x] `tests/unit/test_jwt.py` — 7 tests: create/verify, type check, expiry, cross-type rejection
  - [x] `tests/unit/test_biometrics.py` — 10 tests: extract, match, self-match, blob round-trip
  - [x] `tests/unit/test_stripe.py` — 8 tests: fee calculation, edge cases, old-monthly-bundling-gone
  - [x] `tests/unit/test_config.py` — 8 tests: validate_env raises per missing var, no dangerous defaults

- [x] **Integration tests (25 tests)** *(done)*
  - [x] `tests/integration/test_enroll_flow.py` — 7 tests: session, status poll, form submit, scan, duplicate rejection
  - [x] `tests/integration/test_merchant_lifecycle.py` — 9 tests: signup, cookie, duplicate, login, wrong password, dashboard, logout
  - [x] `tests/integration/test_customer_portal.py` — 4 tests: request-access, verify-code, delete
  - [x] `tests/integration/test_health.py` — 5 tests: healthz, readyz, request-id header, security headers, config
  - [ ] `tests/integration/test_auth_and_pay.py` — deferred (needs Stripe mock for PaymentIntent flow)
  - [ ] `tests/integration/test_pos_websocket.py` — deferred (WebSocket testing needs async client)

- [ ] **CI enforcement**
  - [ ] `pytest --cov-fail-under=70` in CI once coverage is measured
  - [ ] mypy strict mode once baseline passes

---

## Phase 5 — Scale prep

- [ ] Replace ORB with production biometric SDK
- [ ] Async DB driver (`asyncpg` + SQLAlchemy 2.0)
- [ ] Multi-worker / multi-instance deployment
- [ ] CDN + cache for static pages
- [ ] PCI SAQ-A annual self-assessment
- [ ] SOC 2 / GDPR readiness audit
- [ ] Biometric consent checkbox on enrollment page (BIPA compliance)

---

## Done (completed during restructure)

- [x] Env validation function (`app/config.py`)
- [x] JWT default secret removed (reads from config, no fallback)
- [x] Connect return no longer uses raw `sqlite3`/`DB_PATH`
- [x] Private imports removed from `customers.py`
- [x] Email logic extracted to `app/services/email.py`
- [x] Auth helpers centralized in `app/routes/deps.py`
- [x] `database.py` split into 7 focused modules
- [x] Three deploy configs → single Dockerfile
- [x] `--proxy-headers` added to Dockerfile CMD
- [x] `test_fingerprint.png` moved to `tests/fixtures/images/`
- [x] `__pycache__` cleaned from tracking
- [x] Tests scaffold created
- [x] CI pipeline (`.github/workflows/ci.yml`)
- [x] Pre-commit hooks configured
- [x] Full documentation suite (25 docs + ADRs + RFC template)
- [x] CLAUDE.md project instructions
