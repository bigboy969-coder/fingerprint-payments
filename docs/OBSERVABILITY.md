# Observability

How we know what's happening in production. Today this is mostly stdout
logs and the Render dashboard. This document defines the target state and
the conventions to use as we get there.

## Three pillars

### 1. Logs

**Today:** Python `logging` to stdout, format `%(asctime)s | %(levelname)s | %(message)s`, plus a request-log middleware emitting `METHOD PATH → STATUS`.

**Target:** structured JSON logs (via `structlog`), shipped from Render's
log drain to a search backend (Better Stack / Datadog / Grafana Loki — TBD
in an ADR).

**Mandatory log fields once structured:**
- `timestamp` (ISO 8601 UTC)
- `level`
- `event` — the event name in `kebab-case`
- `request_id` — generated in middleware, returned via response header
- `route` — `/pay`, `/enroll/start`, etc.
- `method`
- `status`
- `duration_ms`
- `merchant_id`, `user_id` — when known (numeric IDs only)

**Forbidden in logs:** PII (email, phone, full name), secrets, JWTs, API
keys, bcrypt hashes, raw biometric data.

### 2. Metrics

**Today:** none.

**Target:** Prometheus-compatible metrics endpoint (`prometheus-fastapi-instrumentator`) scraped by the host or a sidecar.

**RED metrics per route:**
- **R**ate — requests/sec
- **E**rrors — 4xx, 5xx
- **D**uration — histogram, p50/p95/p99

**Domain-specific counters:**
- `fingerpay_enrollments_total{status}`
- `fingerpay_authentications_total{result=match|no_match}`
- `fingerpay_payments_total{status=succeeded|failed|requires_action}`
- `fingerpay_payments_amount_usd_sum`
- `fingerpay_platform_fee_usd_sum`
- `fingerpay_stripe_errors_total{operation, error_type}`
- `fingerpay_websocket_connections{merchant_id}` (gauge)
- `fingerpay_match_score` (histogram)
- `fingerpay_descriptors_in_db` (gauge, sampled per minute)

### 3. Traces

**Today:** none.

**Target:** OpenTelemetry spans for HTTP request → DB query → Stripe call.
Send to the same backend that holds metrics.

**Span attributes that must be present:**
- `http.method`, `http.route`, `http.status_code`
- `db.statement` (parameterized — no user values)
- `stripe.operation` (`PaymentIntent.create`, etc.)
- `merchant.id`, `user.id` — when in scope

## Health endpoints

To be added (see `docs/ROADMAP.md` and `docs/ISSUES.md` #36):

- `GET /healthz` — process is up. Returns 200 with `{"status": "ok"}`.
- `GET /readyz` — dependencies are reachable. `SELECT 1` against DB; cheap
  Stripe call (cached). Returns 200 if all green, 503 otherwise.

Render and any future load balancer should target `/readyz`.

## Alerting

Alerts go to the on-call rotation. Two tiers:

| Tier | Examples | SLA |
|---|---|---|
| Page (P1) | `/healthz` failing, error rate > 5% over 5 min, payment failure rate > 1%, DB connection pool exhausted, biometric encryption key error | Acknowledge 5 min, mitigate 30 min |
| Ticket (P2) | Slow request p95 > 2s for 15 min, Stripe API latency > 1s p95, dependency CVE published, dashboard load errors | Within next business day |

Alerts must be **actionable**. Every alert has a runbook in
`docs/runbooks/<alert-name>.md`. Alerts without runbooks get deleted.

## Dashboards

Recommended initial dashboards (build once metrics ship):

1. **Service health** — request rate, error rate, latency p50/p95/p99 per
   route.
2. **Payments** — successful payment rate, total volume processed, average
   transaction value, platform fee revenue, failed payment reasons.
3. **Biometric matching** — auth attempts, match rate, no-match rate,
   match-score histogram.
4. **POS terminal** — connected terminals (gauge), WebSocket reconnects,
   pending POS transactions.
5. **Database** — query duration, connection count, deadlock count.
6. **Stripe** — calls per operation, error rate, retry rate.

## Incident timeline reconstruction

When something breaks, we need to be able to ask:
- What happened to merchant_id=42 between 14:00 and 14:05?
- How many successful payments completed at 14:03?
- Did the deploy at 13:55 correlate with the spike?

To answer these, we need:
- Logs searchable by `merchant_id` and `user_id`.
- Metrics with deploy-marker annotations.
- Stripe dashboard cross-reference (Stripe is the financial source of
  truth).

## What we will NOT log

- Full request bodies on POST endpoints (may contain PII).
- Response bodies (may contain payment details).
- Stack traces in 4xx responses (these are user errors, not system errors).
- Repeated identical errors (rate-limit log emission per error class).

## Privacy controls in observability

- Logs retain for 30 days, then delete (PII safety + compliance).
- Metrics retain forever (no PII in metrics labels — never label by email).
- Traces retain 7 days.
- Customer-portal-related events: log with hashed-email instead of plain
  email if we ever need to retain.

## Rollout plan

1. **Sprint 1:** structured logging via `structlog`; `/healthz`, `/readyz`.
2. **Sprint 2:** Prometheus metrics endpoint + first dashboard.
3. **Sprint 3:** OpenTelemetry traces + alerting wired to PagerDuty.
4. **Sprint 4:** synthetic monitoring (scheduled smoke test against
   `/healthz` from outside the network).
