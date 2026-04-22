# Development Plan

Execution plan for bringing FingerPay from prototype to production-grade.
Each phase builds on the previous. No phase starts until the prior one is
complete and verified.

This is the CTO's committed plan of attack, not a wishlist.

---

## Guiding principles

1. **Fix what charges money first.** The monthly fee bug (#4) and the
   charge-without-record gap (#6) can cost real dollars from day one.
2. **Fix what leaks data second.** The stored XSS (#7) and the JWT
   default secret (#1) are full-compromise paths.
3. **Every fix ships with a test.** No "I'll add the test later." If it's
   worth fixing, it's worth proving the fix works.
4. **Every fix updates the docs.** If the API shape changes, `docs/API.md`
   changes in the same commit. If the architecture changes, write an ADR.
5. **Small, focused commits.** One fix per commit. Conventional Commits
   format. Each should be independently revertable.
6. **Verify before claiming done.** Run the import check, run the test,
   smoke-test the UI. Don't trust "it should work."

---

## Phase 1 — P0 Ship-blockers

**Goal:** Eliminate every defect that would cause a production incident on
day one.

### 1.1 Monthly fee exceeds transaction amount (ISSUES #4)

**The problem:** `calculate_platform_fee` adds $29 to the per-transaction
`application_fee_amount`. Stripe rejects when fee > amount. Every
merchant's first small transaction of the month fails.

**The fix:** Separate the monthly fee from per-transaction fees entirely.
The monthly fee should never be part of `application_fee_amount`.

**Approach:**
- Remove `include_monthly` from `calculate_platform_fee`
- Remove `MONTHLY_FEE` from the per-transaction fee calculation
- `calculate_platform_fee` returns only: `amount * 0.005 + 0.05`
- Monthly billing becomes a separate concern (out-of-band Stripe Invoice
  or future cron — tracked but not built in this phase)
- Update `app/routes/pay.py` to stop passing `include_monthly`
- Remove `update_merchant_monthly_fee_month` call from pay flow
- Write ADR-0006 documenting the decision

**Files touched:**
- `app/services/stripe.py` — simplify `calculate_platform_fee`
- `app/routes/pay.py` — remove monthly fee logic from pay flow
- `app/db/merchants.py` — keep `update_merchant_monthly_fee_month` (will
  be used by future monthly billing cron)
- `tests/unit/test_stripe.py` — new: test fee calculation edge cases
- `docs/adr/0006-*.md` — new ADR

**Test:**
- `test_platform_fee_is_half_percent_plus_scan_fee`
- `test_platform_fee_never_exceeds_amount` (property-based: for any
  amount > 0, fee < amount)

### 1.2 Connect status sync (ISSUES #2)

**The problem:** `connect_return` doesn't update status properly. Stripe
doesn't pass `?account=` on return. Even if it did, the old code used
raw sqlite3.

**The fix (multi-step):**
1. Move `update_merchant_connect_by_account` to `app/db/merchants.py`
   as a proper public function.
2. Change `start_connect` to pass the merchant's Connect account ID in
   the return URL as a query param we control.
3. `connect_return` reads that param and calls
   `get_connect_account_status` + `update_merchant_connect`.
4. Also: make `/merchants/me` re-fetch Connect status from Stripe if
   local status is `pending` — self-healing on dashboard load.

**Files touched:**
- `app/db/merchants.py` — new `update_merchant_connect_by_stripe_account`
- `app/routes/merchants.py` — fix `start_connect` return URL, fix
  `connect_return`, add status refresh in `dashboard`
- `app/services/stripe.py` — no change (already has
  `get_connect_account_status`)
- `tests/integration/test_merchant_lifecycle.py` — new

### 1.3 Stored XSS in dashboard (ISSUES #7)

**The problem:** `full_name` and `email` rendered via `innerHTML` in
`merchant-dashboard.html` and `customer-portal.html`.

**The fix:**
1. Add an `escapeHtml()` JS helper function at the top of each page.
2. Replace every template literal interpolation of user data with
   `escapeHtml(value)`.
3. Add CSP middleware in `app/main.py`:
   `Content-Security-Policy: default-src 'self'; script-src 'self' https://js.stripe.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`

**Files touched:**
- `static/merchant-dashboard.html` — escape all user data in templates
- `static/customer-portal.html` — escape all user data
- `app/main.py` — add security headers middleware

### 1.4 Pre-charge transaction row (ISSUES #6)

**The problem:** If `record_transaction` fails after Stripe charges the
customer, money moves but no DB row exists.

**The fix:**
1. Add a `create_pending_transaction` function in `app/db/transactions.py`
   that inserts a row with `stripe_status='pending'` and no intent ID.
2. Add an `update_transaction_result` function that sets the intent ID
   and status.
3. In `app/routes/pay.py`: insert pending row BEFORE calling Stripe,
   update it after, log CRITICAL if the update fails.

**Files touched:**
- `app/db/transactions.py` — new functions
- `app/routes/pay.py` — restructure the charge flow
- `tests/integration/test_auth_and_pay.py` — new

### 1.5 Env validation verification (ISSUES #1/#3/#8)

**The problem:** `validate_env()` exists but we haven't proven it works.

**The fix:** Write the test.

**Files touched:**
- `tests/unit/test_config.py` — new

### 1.6 POS single-worker documentation (ISSUES #5, partial)

**The problem:** The in-memory POS state constraint isn't enforced or
documented in the deploy config.

**The fix:**
- Add a comment in `Dockerfile` explaining the single-worker constraint
- Add a startup log warning if someone sets `WEB_CONCURRENCY > 1`
- Add graceful-shutdown logging for in-flight POS transactions

**Files touched:**
- `Dockerfile` — comment
- `app/main.py` — startup warning + shutdown handler
- `app/routes/pos.py` — expose in-flight count for shutdown log

---

## Phase 2 — P1 Pilot-readiness

**Goal:** Close every gap that would embarrass us in a merchant pilot.

### 2.1 Rate limiting everywhere (ISSUES #11/#12)

Add `@limiter.limit` decorators to:
- `/merchants/login` — 5/min
- `/merchants/signup` — 3/min
- `/merchants/forgot-password` — 3/min
- `/customers/request-access` — 3/min
- `/customers/verify-code` — 5/min

Requires passing `request: Request` as first arg to each handler (slowapi
requirement).

### 2.2 JWT type check (ISSUES #17)

Add `if payload.get("type") != "customer": raise ValueError` to
`verify_access_token`. Single-line fix + test.

### 2.3 Stripe webhooks (ISSUES #16)

New file: `app/routes/webhooks.py`. Handle:
- `account.updated` — update Connect status
- `payment_intent.payment_failed` — mark transaction failed
- `charge.dispute.created` — flag for dashboard
- `charge.refunded` — update transaction status

Add `STRIPE_WEBHOOK_SECRET` to config.

### 2.4 Remove client-controlled merchant field (ISSUES #19)

In `/pay`, derive merchant name from `merchant_id` in the JWT. Remove
`merchant` from `PayRequest`.

### 2.5 Email enumeration fix (ISSUES #14)

`/enroll/start` should return 200 with a generic message even if email
exists.

### 2.6 Health endpoints (ISSUES #36)

Add `/healthz` and `/readyz` to `app/main.py`.

### 2.7 PII scrub from logs (ISSUES #23)

Remove the email log in `app/routes/customers.py`. Audit all other log
calls.

### 2.8 Fix os.environ usage in customers.py

Replace `os.environ.get("STRIPE_SECRET_KEY")` with
`app.config.STRIPE_SECRET_KEY` in delete-account handler.

### 2.9 Remove unused imports

Clean up `import os` in `app/routes/merchants.py` and
`app/routes/customers.py`.

---

## Phase 3 — Security hardening

### 3.1 Security headers middleware

`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, HSTS.

### 3.2 WebSocket auth via first message (ISSUES #13)

Move API key out of the URL query string.

### 3.3 Merchant JWT to HttpOnly cookie

Eliminate localStorage XSS surface.

### 3.4 Idempotency key fix (ISSUES #21)

Derive from `(user_id, merchant_id, amount, timestamp)` hash.

---

## Phase 4 — Infrastructure

### 4.1 Alembic migrations (ISSUES #29)
### 4.2 DB indexes (ISSUES #28)
### 4.3 Connection pool (ISSUES #27)
### 4.4 Pagination (ISSUES #30)
### 4.5 Cleanup jobs (ISSUES #31/#32)
### 4.6 Pin dependencies (ISSUES #26)
### 4.7 Structured logging + Sentry

---

## Phase 5 — Test suite

### 5.1 Unit tests for services (crypto, jwt, biometrics, stripe)
### 5.2 Integration tests for all flows
### 5.3 CI enforcement (coverage gates)

---

## Execution order within Phase 1

I'll work through Phase 1 items in this exact order because each builds
on the previous:

1. **1.1 Monthly fee fix** — most impactful business-logic bug, standalone
2. **1.5 Env validation test** — quick win, proves config works
3. **1.3 XSS fix + security headers** — high-impact security, frontend-only
4. **1.2 Connect status sync** — Stripe integration, needs careful testing
5. **1.4 Pre-charge transaction row** — changes the pay flow, most complex
6. **1.6 POS documentation** — lowest risk, documentation + logging

After each item: verify imports, run any existing tests, update TODO.md
checkboxes, add CHANGELOG entry.

---

## What success looks like at each phase

| Phase | Metric |
|---|---|
| 1 complete | No P0s. App boots cleanly, refuses to start without secrets. Fee math correct. No XSS. Stripe charges always have a DB row. |
| 2 complete | All auth endpoints rate-limited. Stripe webhooks live. Health endpoints exist. No PII in logs. Clean JWT type separation. |
| 3 complete | Security headers on every response. API key out of URLs. Merchant JWT in HttpOnly cookie. Idempotency keys meaningful. |
| 4 complete | Alembic migrations. Connection pool. DB indexes. Paginated lists. Scheduled cleanup jobs. Pinned deps. |
| 5 complete | 70%+ coverage. CI enforces tests. All flows have integration tests. |

---

## Constraints and non-goals

- **No biometric SDK swap in this plan.** ORB stays for now (ADR needed
  for the replacement decision — that's a separate RFC).
- **No Redis migration in this plan.** Single-worker pilot constraint
  stays (ADR-0005). Redis is Phase 3+ in the TODO.
- **No frontend framework adoption.** Vanilla JS stays. Escape properly
  instead of reaching for React.
- **No ORM adoption.** Raw SQL with the PH pattern stays. Alembic for
  migrations, not SQLAlchemy for queries.
