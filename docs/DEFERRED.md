# Deferred Work

Items explicitly scoped out of the Phase 1–3 production-readiness push.
Each entry documents what, why it was deferred, what unblocks it, and who
owns the unblock.

This is not a backlog — it's a contract. These items were reviewed,
prioritized, and consciously delayed. Don't reopen them without reading
the rationale.

---

## Code / architecture

### D1. Biometric matcher replacement (ISSUES #9/#10)

**What:** Replace ORB feature extraction + linear scan matching with a
production-grade biometric SDK (Innovatrics, NEC, Fingerprint Cards, or
similar). Add liveness detection and anti-spoofing.

**Why deferred:** This is a multi-month effort that requires vendor
evaluation, procurement, integration, and re-enrollment of all users. It
doesn't block a controlled pilot with trusted merchants, but it blocks
any public launch.

**Unblock criteria:**
- Write RFC under `docs/rfc/` with vendor comparison, cost, integration
  effort, and re-enrollment plan.
- CTO approval on vendor + budget.
- Pilot data on false-accept/reject rates with the current ORB matcher
  to quantify urgency.

**Owner:** CTO (vendor decision), then engineering for integration.

**Risk if left unaddressed:** False accepts at scale (certain above ~5k
enrolled users). Spoofing via fingerprint photos (trivial today). Neither
is acceptable for a public product.

---

### D2. Redis for POS WebSocket state (ISSUES #5)

**What:** Move `TerminalManager.terminals` (connection map) and
`TerminalManager.transactions` (in-flight POS tx status) from in-process
Python dicts to Redis. Enable multi-worker deployment.

**Why deferred:** The pilot operates with 1–5 merchants, each with 1
terminal. A single process handles this. Redis adds cost, operational
complexity (a new dependency to provision, monitor, back up), and code
complexity (pub/sub for WebSocket relay) that isn't justified until we
need horizontal scaling.

**Unblock criteria:**
- More than ~10 concurrent merchants.
- Or: Render restarts are causing visible payment failures for POS users.
- Write ADR superseding ADR-0005.
- Provision Redis (Render Redis or Upstash).

**Owner:** Engineering.

**Current mitigation:** Documented single-worker constraint in Dockerfile.
Startup warning if `WEB_CONCURRENCY != 1`. Graceful-shutdown logging for
in-flight POS transactions.

---

### D3. SCA / 3DS recovery for off-session charges (ISSUES #20)

**What:** When a European cardholder's bank requires Strong Customer
Authentication, Stripe returns `requires_action` on the PaymentIntent.
The current code does not detect this or surface a recovery URL.

**Why deferred:** Requires testing with Stripe EU test cards
(`pm_card_authenticationRequired`) and building a customer-facing recovery
flow (email with a Stripe-hosted link). The pilot market is US-based;
European cards are not expected in the pilot.

**Unblock criteria:**
- First merchant with EU customers.
- Or: pre-launch compliance review identifies SCA as a blocker.
- Implementation: detect `requires_action` in `charge_customer` response,
  email the customer a recovery link via `payment_intent.next_action.url`.

**Owner:** Engineering.

---

## Operations / infrastructure

### D4. Resend domain verification (ISSUES #15)

**What:** Register a custom domain in Resend (e.g., `mail.fingerpay.com`)
so emails come from `noreply@fingerpay.com` instead of
`onboarding@resend.dev`.

**Why deferred:** Requires DNS access to the FingerPay domain and a
Resend paid plan. The sandbox sender works for internal testing but lands
in spam for external recipients.

**Unblock criteria:**
- DNS access to the production domain.
- Resend account upgraded from free tier.

**Owner:** CTO (DNS + billing), then update `app/services/email.py`
`"from"` address.

**Risk if left unaddressed:** Password reset and verification code emails
land in spam. Customers can't access the portal. Merchants can't reset
passwords.

---

### D5. Sentry error reporting

**What:** Add Sentry SDK for automatic exception capture, breadcrumbs,
and alerting.

**Why deferred:** Requires a Sentry account (free tier is sufficient).
Code-side integration is trivial (~10 lines), but the account setup is
an ops task.

**Unblock criteria:**
- Sentry account created.
- `SENTRY_DSN` added to env vars.
- `pip install sentry-sdk[fastapi]`, initialize in `app/main.py` lifespan.

**Owner:** CTO (account), then engineering (integration).

---

### D6. HSTS header

**What:** Add `Strict-Transport-Security: max-age=31536000;
includeSubDomains` to force HTTPS.

**Why deferred:** HSTS is dangerous to enable before confirming the
production domain has valid TLS and will keep it. Render provides TLS
automatically on `.onrender.com` subdomains, but a custom domain needs
explicit certificate setup.

**Unblock criteria:**
- Custom domain configured with TLS verified.
- Add one line to the `security_headers` middleware in `app/main.py`.

**Owner:** CTO (domain + TLS), then engineering (one-line change).

---

### D7. Alembic pre-deploy hook on Render

**What:** Add `alembic upgrade head` as a Render pre-deploy command so
migrations run automatically before the new code starts.

**Why deferred:** The production Postgres database needs to be stamped
with the baseline migration first (`alembic stamp head`) to avoid
re-creating tables that already exist.

**Unblock criteria:**
- SSH / CLI access to the production database.
- Run `alembic stamp 9db10166ac38` once.
- Add pre-deploy command in Render dashboard: `alembic upgrade head`.

**Owner:** CTO (Render access), then it's self-maintaining.

---

### D8. Postgres TIMESTAMPTZ migration

**What:** Migrate all `TEXT` timestamp columns to `TIMESTAMPTZ` in
Postgres for proper date math and indexing.

**Why deferred:** Requires a careful migration (ALTER COLUMN with data
conversion) on a live database. The application code is already
standardized on UTC (Phase 3 fix), so TEXT-ISO with UTC is functionally
correct. TIMESTAMPTZ is a correctness improvement, not a bug fix.

**Unblock criteria:**
- Alembic pre-deploy hook is in place (D7).
- Write migration, test on a staging database.
- Deploy during low-traffic window.

**Owner:** Engineering.

---

## Summary

| ID | Item | Blocks | Unblocked by |
|---|---|---|---|
| D1 | Biometric SDK | Public launch | Vendor selection + RFC |
| D2 | Redis for POS | Horizontal scaling | >10 merchants or restart-induced failures |
| D3 | SCA/3DS | EU cardholders | First EU merchant |
| D4 | Resend domain | Reliable email delivery | DNS access + paid plan |
| D5 | Sentry | Error visibility | Sentry account |
| D6 | HSTS | Full transport security | Custom domain + TLS |
| D7 | Alembic pre-deploy | Auto-migrations | One-time DB stamp |
| D8 | TIMESTAMPTZ | Proper date columns | D7 in place |

None of these block a controlled US-based pilot with trusted merchants.
All of them should be resolved before a public launch.
