# Operations

## Local development

```bash
# 1. Python 3.11 (matches Dockerfile). Other versions may work; cv2/numpy can be picky.
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 2. Required env vars (put in .env, dotenv is loaded by app/main.py)
cat > .env <<EOF
FINGERPAY_SECRET=<generate: openssl rand -hex 32>
BIOMETRIC_ENCRYPTION_KEY=<generate: openssl rand -hex 32>
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
RESEND_API_KEY=re_...                 # optional in dev — emails will be skipped
APP_BASE_URL=http://localhost:8000
# DATABASE_URL=postgres://...         # optional, omit for SQLite
EOF

# 3. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# or
python -m app.main
```

The app listens on `:8000`. Open http://localhost:8000/ for the marketing
page, http://localhost:8000/kiosk for the kiosk, http://localhost:8000/business
for the merchant signup.

## Environment variables (full list)

| Var | Required? | Notes |
|---|---|---|
| `FINGERPAY_SECRET` | **Yes (prod)** | HMAC key for JWTs. Falls back to a known dev value if unset — **never deploy without setting** |
| `BIOMETRIC_ENCRYPTION_KEY` | **Yes** | 32-byte hex (64 chars). Loss = unrecoverable biometrics |
| `STRIPE_SECRET_KEY` | **Yes** | Stripe API secret |
| `STRIPE_PUBLISHABLE_KEY` | Yes (for enrollment UI) | Returned by `/config` |
| `RESEND_API_KEY` | Yes (for prod) | Otherwise emails are dropped |
| `DATABASE_URL` | Yes (prod) | Postgres DSN. SQLite fallback for dev |
| `APP_BASE_URL` | Yes | Used in reset/onboarding URLs. Defaults to `https://fingerprint-payments.onrender.com` |
| `DATA_DIR` | No | SQLite file location (default = repo root) |
| `PORT` | Set by host | Used by `Dockerfile` CMD |

## Generating secrets

```bash
python -c "import secrets; print(secrets.token_hex(32))"   # for FINGERPAY_SECRET, BIOMETRIC_ENCRYPTION_KEY
```

## Deploy targets

The repo uses a single `Dockerfile` (Python 3.11-slim). Previous `Procfile`
and `nixpacks.toml` files were removed during the restructure.

The default `APP_BASE_URL` in `app/config.py` defaults to
`http://localhost:8000` for local dev. Production should set it to the
Render URL (e.g., `https://fingerprint-payments.onrender.com`).

## Process model in production

The Dockerfile starts:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
Single worker, no `--workers`. **This is required** by the in-memory
WebSocket state in `app/routes/pos.py` (see ISSUES #5). Adding `--workers > 1`
without first moving WebSocket state to Redis will silently break payments.

Recommended runtime flags to add:
- `--proxy-headers --forwarded-allow-ips=*` so the rate limiter sees real
  client IPs (currently it sees the LB IP).
- `--access-log` is on by default — combined with the in-app request logger
  this duplicates output. Pick one.

## Database

### SQLite (dev)
Single file: `fingerpay.db` in the repo root, gitignored. `init_db()` runs at
startup and uses `CREATE TABLE IF NOT EXISTS` plus a handful of best-effort
`ALTER TABLE` migrations.

### Postgres (prod)
- DSN in `DATABASE_URL`.
- `init_db()` uses only `CREATE TABLE IF NOT EXISTS`. **No migrations.**
  When you add a column to a table, it will not be added to an existing
  Postgres database. You must run the ALTER manually.
- No connection pool — every request opens a new connection.

### Backups
There is no backup script in the repo. Render-managed Postgres has its own
backup scheme; document and verify the RPO/RTO with the host.

## Observability

### Logging
- `logging.basicConfig(level=INFO)` to stdout.
- Format: `%(asctime)s | %(levelname)s | %(message)s`.
- The `log_requests` middleware logs `METHOD PATH → STATUS` for every
  request.
- A few `logger.warning`/`logger.error` calls in `app/routes/customers.py` and
  `app/routes/merchants.py`.

### Metrics
None. No Prometheus, no StatsD, no Datadog hooks.

### Tracing
None.

### Error reporting
None. Exceptions become 500 responses; the stack trace lives in stdout if
the host shows it.

### Recommended additions
- Sentry for unhandled exceptions and PII-redacted breadcrumbs.
- Structured JSON logs (`structlog`) so the host's log search is useful.
- Stripe dashboard is the source of truth for payments; reconcile against
  `transactions` table on a daily cron.

## Health & readiness

There are no `/healthz` or `/readyz` endpoints. The closest thing is `GET /`
(which redirects to the static site). For Render this works (HTTP 200/302
on the root counts as healthy), but probes can't distinguish "process up but
DB down."

**Recommended:**
```python
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    # Try a SELECT 1 to verify DB; ping Stripe; return 503 on failure.
    ...
```

## Scaling caveats

| Scale axis | Today's ceiling | Why |
|---|---|---|
| Concurrent users | ~50 req/s | Single worker, blocking OpenCV in the asyncio loop |
| Enrolled fingerprints | ~5,000 | O(N) decrypt + ORB on every authenticate |
| Concurrent merchants on POS | 1 worker can hold all WS | Memory + asyncio event loop |
| Multiple processes/workers | **0** | In-memory POS state |
| DB connections | 1 per request | No pool |

Roughly: this is a 1-store pilot architecture. Don't promise Y combinator-
scale demos with the current code path.

## Disaster recovery

| Failure | Today's behavior | Should be |
|---|---|---|
| DB host outage | All endpoints 500 | Graceful degradation, retry banner |
| Lost `BIOMETRIC_ENCRYPTION_KEY` | All fingerprints permanently inaccessible | Backed-up KMS, key rotation procedure |
| Lost `FINGERPAY_SECRET` | All sessions invalidated; users re-login; merchants need to log in again | Same — but document the recovery |
| Stripe outage | `/pay` returns 402; enrollment 402 | Add retry-with-backoff for Connect/setup operations |
| Process restart with in-flight POS payment | Charge happens at Stripe, customer sees success on kiosk, POS times out | Persistent state in Redis |

## Day-2 runbooks (TODO)

There are none. Suggested first set:
- "Merchant says payouts aren't working" → check `merchants.stripe_connect_status`,
  re-trigger Connect onboarding (note: status update is broken — see ISSUES #2).
- "Customer says they can't enroll, says email already used" → query users
  table; if exists, advise customer portal to delete and re-enroll.
- "Reconcile a missing transaction" → query Stripe by PaymentIntent vs.
  `transactions` table; surface mismatches.
