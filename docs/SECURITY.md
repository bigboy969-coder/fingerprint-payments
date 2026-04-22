# Security Model

This document describes the **actual** security posture of the codebase, not
its aspirations. The headline: this is a prototype that handles real money
and real biometrics. Several issues here are blockers for a production
deployment.

## Trust boundaries

| Boundary | Crosses | Trust level |
|---|---|---|
| Customer phone → `/enroll/*` | Public internet | Untrusted client |
| Kiosk tablet → `/authenticate`, WebSocket | Public internet (in-store WiFi) | Authenticated by API key |
| POS → `/pos/charge` | Public internet | Authenticated by API key |
| FastAPI → Stripe API | TLS to api.stripe.com | Trusted |
| FastAPI → Resend | TLS to api.resend.com | Trusted |
| FastAPI → Postgres | Should be TLS over private network | Trusted |

## Secrets

| Env var | Purpose | Failure mode |
|---|---|---|
| `BIOMETRIC_ENCRYPTION_KEY` | 32-byte hex, AES-256-GCM key for fingerprint blobs | If missing → app boots, **first** enrollment/auth raises `RuntimeError` |
| `FINGERPAY_SECRET` | HMAC key for all JWTs | If missing → falls back to `"dev-secret-change-in-prod"` (**catastrophic in prod**) |
| `STRIPE_SECRET_KEY` | Stripe API key | If missing → silently `None`, every Stripe call fails with cryptic error |
| `STRIPE_PUBLISHABLE_KEY` | Public Stripe key, served by `/config` | If missing → enrollment page silently breaks |
| `RESEND_API_KEY` | Email sending | If missing → emails dropped, `logger.warning` |
| `DATABASE_URL` | Postgres DSN | If missing → falls back to SQLite |
| `APP_BASE_URL` | Used in reset/onboarding URLs | Defaults to `https://fingerprint-payments.onrender.com` |

**There is no startup validation.** Boot succeeds with empty env. Recommend
a `validate_env()` call in `lifespan` that fails fast.

## Biometric data handling

### What is stored
- ORB keypoint descriptors (`numpy.uint8`, shape `(N, 32)` per fingerprint).
- Encrypted with AES-256-GCM, nonce prepended.
- Stored in `fingerprints.descriptor` (BLOB / BYTEA).

### What is NOT stored
- The original fingerprint image. Saved to `temp_uploads/` during processing,
  unlinked in a `finally` block. **If the process crashes between write and
  unlink, image leaks to disk.** No background sweep for orphans.

### Biometric matcher quality
- ORB is a **generic computer-vision feature extractor**, not a biometric
  matcher. NIST does not certify it.
- `MATCH_THRESHOLD = 40` good matches. There is no published study supporting
  this threshold for fingerprint identification at scale.
- The matcher returns the **best score above threshold** — it does not check
  for ambiguity (two users above threshold). At any non-trivial enrollment
  count, false acceptance is statistically guaranteed.
- There is **no liveness detection, no anti-spoofing**. Anyone with a photo
  of a finger can authenticate.
- The kiosk page accepts arbitrary file uploads via `<input type=file>`.
  There is no hardware sensor today.

This is fine as a demo. As a production payments system it is a fraud
event waiting to happen.

### Key management
- Single static `BIOMETRIC_ENCRYPTION_KEY` in env.
- No rotation strategy. No envelope encryption. No KMS integration.
- Lose the key → all biometrics permanently inaccessible. Leak the key →
  full biometric database compromise.

## Authentication

### Customer fingerprint → JWT
- 2-minute TTL JWT with `user_id`, optional `merchant_id`, and `type=customer`.
- HS256 signed with `FINGERPAY_SECRET`.
- `/pay` does not check `payload["type"]`. A `merchant`-typed token would
  KeyError on `payload["user_id"]` and bubble a 500 instead of a clean 401.

### Merchant API key
- 32-byte url-safe random, returned once at signup, SHA-256 hashed at rest.
- No expiry. Manual rotation only via `/merchants/regenerate-key`.
- **Sent in URL query string** for `/ws/terminal` and `/pos/terminal/status`
  — leaks into request logs, browser history, proxy logs.
- Per-IP rate-limited (10/min) **only** on `/authenticate`. Other endpoints
  using the API key (POS charge, terminal status) are unbounded.

### Merchant JWT
- 24-hour TTL HS256.
- Stored in `localStorage` — **vulnerable to XSS**. The dashboard uses no
  CSP, no SRI on its CDN scripts.
- No revocation. Logout only clears `localStorage`. Stolen tokens valid for
  up to 24 h.
- No password complexity check at signup. Reset enforces ≥ 8 chars.

### Customer self-service
- Email-then-code flow. 6-digit code, 10-min TTL.
- `request-access` always returns 200 (no email enumeration). Good.
- `verify-code` does NOT consume the code, allowing repeated reads + a
  subsequent delete. Trade-off: a sniffed code is reusable for the full TTL.
- `delete-account` consumes the code.

### Email enumeration leaks
- `POST /enroll/start` returns a 400 with body `"This email is already
  enrolled."` — leaks enrollment status of any email.
- `POST /merchants/login` distinguishes only "Invalid email or password" —
  good (no enumeration), but is **not rate-limited**.
- `POST /merchants/forgot-password` always returns 200 — good.

## Transport / network

- No CORS configuration in `main.py`. FastAPI defaults to permissive for
  same-origin only; cross-origin calls are blocked, which is the intent.
  However, if FingerPay is ever embedded in a merchant site (iframe, etc.),
  the lack of `Content-Security-Policy` headers leaves it open to clickjacking.
- No `X-Frame-Options`, no CSP, no HSTS, no referrer policy headers.
- WebSocket bears no origin check. A page hosted anywhere with a stolen API
  key can connect.

## Input validation

- Pydantic on all JSON bodies — basic type validation only.
- Email field is plain `str`, not `EmailStr`. Invalid emails accepted into
  Stripe (which will reject), users (where they will block future
  re-enrollment), and the customer portal (where they go nowhere).
- Phone field is freeform string.
- `amount` in `/pay` is `> 0` only — no upper bound, no currency check.
- Upload size middleware limits POSTs to 5MB but only reads `Content-Length`.
  A request with `Transfer-Encoding: chunked` and no `Content-Length`
  bypasses it.

## CSRF / XSS

- All session-bearing requests use `Authorization: Bearer ...` with tokens
  from `localStorage`. No cookies, so classic CSRF is N/A — but XSS is a full
  account takeover (extract token → POST `/regenerate-key` → take over the
  merchant's terminal API key).
- Inline JS in static pages, no Content-Security-Policy. Any HTML injection
  in user-controlled data rendered in the dashboard is a token theft.
- Dashboard renders `customer.full_name`, `customer.email` directly via
  `innerHTML`. **`full_name` is fully customer-controlled at enrollment time
  and goes through `innerHTML` — stored XSS in the merchant dashboard.**

## Stripe / financial

- All charges are off-session. No SCA fallback for `requires_action`
  PaymentIntents.
- No idempotency on `/pay` retries (Stripe-level idempotency_key uses a
  fresh UUID every call, defeating its purpose for retries).
- No webhook handler — disputes, async failures, refunds, Connect events all
  invisible to FingerPay.
- `application_fee_amount` in `/pay` includes the monthly fee, which can
  exceed the transaction amount → Stripe rejects the call. See ISSUES.md #4.

## Logging & PII

- Request logger emits method, path, status. Path can contain `session_id`
  (UUID) — low PII risk.
- `customers.py` logs `"Customer access request for %s — found: %s"` with
  the email. **PII in logs.**
- No log redaction, no log retention policy documented.

## Summary risk register

| Risk | Severity | Likelihood | Mitigation present? |
|---|---|---|---|
| Forged JWT (default secret) | Critical | Medium | No |
| Biometric false-accept | High | Certain at scale | No |
| Biometric spoof attack | Critical | Easy | No |
| Stored XSS via dashboard `innerHTML` | High | Easy | No |
| API key in URL → log leak | Medium | High | No |
| Stripe reject due to fee > amount | High | Certain on first small tx of month | No |
| Connect status sync broken | High | 100% in production | No |
| In-memory POS state lost on restart | High | Every deploy | No |
| Money charged but DB write failed | Medium | Rare | No |
| Email PII in logs | Medium | Constant | No |
| Credential stuffing on `/login` | High | Likely | No (no rate limit) |
