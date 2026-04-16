# Architecture

## One-paragraph summary

FingerPay is a single-process FastAPI service that acts as an authentication
layer in front of Stripe. Customers enroll a fingerprint (ORB descriptor,
AES-256-GCM encrypted at rest) plus a Stripe payment method. At checkout, a
merchant's POS asks the in-store FingerPay kiosk (over a persistent
WebSocket) to collect a fingerprint scan; the scan is matched against the
descriptor store, a short-lived JWT is issued, and the JWT is exchanged for an
off-session Stripe PaymentIntent (optionally routed via Stripe Connect to the
merchant).

## Components

```
┌─────────────────┐        ┌──────────────────────┐        ┌──────────────┐
│   Customer's    │  HTTPS │   FingerPay (this)   │  HTTPS │   Stripe     │
│   phone         ├───────►│                      ├───────►│   API        │
│   (enroll page) │        │   FastAPI on Render  │        │              │
└─────────────────┘        │   ┌────────────────┐ │        └──────────────┘
                           │   │ SQLite (dev)   │ │
                           │   │ Postgres (prod)│ │
                           │   └────────────────┘ │        ┌──────────────┐
┌─────────────────┐  WSS   │                      │  HTTPS │  Resend      │
│   Kiosk tablet  ├───────►│   /ws/terminal       ├───────►│  (email)     │
│   (browser)     │        │                      │        └──────────────┘
└─────────────────┘        └──────────────────────┘
        ▲                              ▲
        │ HTTPS scan upload            │ HTTP /pos/charge
        │                              │
┌───────┴─────────┐                    │
│  Same kiosk:    │           ┌────────┴──────────┐
│  fingerprint    │           │   Merchant POS    │
│  upload control │           │   (existing       │
└─────────────────┘           │    register)      │
                              └───────────────────┘
```

### Process model

- One Python process, one ASGI worker.
- All HTTP routes are async; OpenCV and bcrypt calls are blocking and run on
  the asyncio thread (no executor offload). At low scale this is fine.
- WebSocket connections and the in-flight POS-transaction map live in module-
  global dicts inside `app/routes/pos.py:TerminalManager`. **Cannot be scaled
  horizontally without a shared message bus** (see ISSUES.md #5).

### Data stores

- **SQLite** when `DATABASE_URL` is unset. File `fingerpay.db` in repo root
  (or `DATA_DIR` if set). Dev only.
- **PostgreSQL** when `DATABASE_URL` is set. Used in production. The same
  `app/db/` switches dialect via a `PH` placeholder and
  conditional `psycopg2`/`sqlite3` imports.
- No ORM. No migration tool. Schema is created idempotently in `init_db()`
  on app startup.

### External services

| Service | Purpose | Failure mode |
|---|---|---|
| Stripe API | Customer creation, off-session PaymentIntents, Connect Express, AccountLinks | Hard fail — payment route returns 402 |
| Stripe Connect | Merchant bank payouts via destination charges | Status sync is broken in Postgres |
| Resend | Password reset + customer verification emails | Soft fail — logged warning, not surfaced |

## Routing topology

| Prefix | Owner | Notes |
|---|---|---|
| `/enroll/*` | enroll.py | Two-device session-based enrollment |
| `/authenticate` | authenticate.py | Rate-limited 10/min |
| `/pay` | pay.py | Requires customer JWT from `/authenticate` |
| `/merchants/*` | merchants.py | Signup, login, dashboard, Connect, reset |
| `/customers/*` | customers.py | Self-service portal |
| `/pos/*`, `/ws/terminal` | pos.py | POS↔kiosk WebSocket bridge |
| `/static/*` | StaticFiles | Vanilla HTML/JS pages |
| Top-level redirects | main.py | `/business`, `/kiosk`, `/my-account`, etc. |

## Authentication model

Three distinct credentials live in this system:

1. **Merchant API key** — `secrets.token_urlsafe(32)`, SHA-256 hashed at rest.
   Plaintext shown once at signup. Used for `/authenticate`, `/pos/charge`,
   `/pos/terminal/status`, `/ws/terminal`. No expiry, manual rotation only.
2. **Merchant JWT** — HS256, 24h TTL, `type=merchant`, used for dashboard
   endpoints (`/merchants/me`, `/customers`, `/connect`, `/regenerate-key`).
   Stored in `localStorage`.
3. **Customer access token** — HS256, 2-min TTL, `type=customer`, used only
   for a single `/pay` call. Issued by `/authenticate` after a successful
   fingerprint match.

All three use the same `FINGERPAY_SECRET` HMAC key.

## Frontend

Pure static HTML+CSS+vanilla JS, no build step, no framework.

| Page | Purpose |
|---|---|
| `index.html` | Marketing landing page |
| `enroll.html` | Customer's phone enrollment form (Stripe Elements) |
| `kiosk.html` | The in-store tablet — QR display + fingerprint upload + WebSocket client |
| `merchant-signup.html` | Business signup |
| `merchant-login.html` | Business login |
| `merchant-dashboard.html` | Stats, API key, Connect status, customer list, recent tx |
| `merchant-reset-password.html` | Password reset form |
| `customer-portal.html` | Customer self-service: verify email → view/delete account |

Stripe Elements are loaded directly from `https://js.stripe.com/v3/`.
QRCode.js is loaded from a CDN. **No Subresource Integrity hashes.**

## What is NOT in this repo (yet)

- No test implementations (scaffold exists in `tests/`; CI exists in
  `.github/workflows/ci.yml`).
- No webhook handlers (Stripe webhooks for payment failures, disputes,
  Connect account updates — none exist).
- No background job runner. Email sends use a daemon thread
  (`app/services/email.py`).
- No structured logging, no error reporter (Sentry/etc.), no tracing.
- No infrastructure-as-code (Terraform/Pulumi). Single `Dockerfile` for
  deploys.
- No actual fingerprint hardware integration. The kiosk uploads images via a
  hidden `<input type="file">`. ORB matching on uploaded JPEGs/PNGs is the
  current authentication.
