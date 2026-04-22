# Threat Model

A STRIDE pass over FingerPay. This document enumerates threats by trust
boundary; each threat is classified, assessed, and mapped to either an
existing mitigation or a planned one (linked to `docs/ISSUES.md`).

Refresh this document when you add a new endpoint, new external
integration, or new trust boundary.

## Assets

| Asset | Why it matters |
|---|---|
| Customer biometric descriptors | Cannot be revoked. Regulated under BIPA, GDPR Art. 9 |
| Customer payment methods (Stripe customer + payment_method IDs) | Direct path to fund movement |
| Customer PII (name, email, phone, transaction history) | Privacy + GDPR |
| Merchant API keys | Auth bypass to the entire merchant tenant |
| Merchant JWT (24h) | Dashboard takeover, API key rotation |
| Merchant Stripe Connect ID + payouts | Direct path to merchant funds |
| `BIOMETRIC_ENCRYPTION_KEY` | Compromise = mass biometric exposure |
| `FINGERPAY_SECRET` | Compromise = forge any JWT (customer or merchant) |
| `STRIPE_SECRET_KEY` | Compromise = full Stripe account access |
| Reputation | Loss of trust = business death in payments |

## Trust boundaries

```
[ Customer phone ] ──── enrollment ────►  [ FingerPay app ] ──► [ Stripe ]
                                              │
[ Kiosk tablet ] ─── auth + WS ────────►      │
                                              ▼
[ Merchant POS ]   ── /pos/charge ────►  [ DB (SQLite/PG) ]
                                              │
[ Merchant browser ] ─ dashboard ──────►      │
                                              ▼
[ Customer browser ] ─ portal ────────►  [ Resend (email) ]
```

Five external actors. Each is a trust boundary.

## STRIDE per actor

### S — Spoofing

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| S1 | Forged customer JWT to call `/pay` | Money | HS256 signature with `FINGERPAY_SECRET` | **At risk** if env defaults to `dev-secret-...` (ISSUES #1) |
| S2 | Forged merchant JWT to access dashboard | Merchant data | Same as S1 | **At risk** as above |
| S3 | API key reuse from a logged URL (WebSocket) | Merchant API | None | **Open** (ISSUES #13) |
| S4 | Stolen merchant JWT via XSS | Merchant takeover | None | **Open** (ISSUES #7) |
| S5 | Spoofed fingerprint (photo / mold) | Money | None — no liveness | **Open** (ISSUES #9) |
| S6 | Spoofed Stripe webhook | Connect status, payment events | No webhook handler exists yet | Will need signature verification (ROADMAP S2) |
| S7 | Spoofed customer at portal (email enumeration not relevant; code brute force) | Customer data | None — no rate limit on verify-code | **Open** (ISSUES #11, #12) |

### T — Tampering

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| T1 | Man-in-the-middle on `/pay` | Charge amount, merchant routing | TLS only (assumed at host); no certificate pinning | Acceptable for browser/Render |
| T2 | Tampered request body to `/pay` (`merchant` field is client-controlled) | Stored merchant string | None | **Open** (ISSUES #19) — derive server-side |
| T3 | Tampered fingerprint image | Auth match | Image is processed deterministically; no mutation | OK |
| T4 | DB tampering by privileged operator | Everything | Render-managed Postgres, no audit log | **Gap**: add change-data audit trail |
| T5 | Tampered JWT claims | Auth elevation | HS256 detects tampering | OK provided S1 is fixed |

### R — Repudiation

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| R1 | Customer denies a charge | Stripe + DB transaction record | Stripe retains evidence; we store stripe_payment_intent_id | OK |
| R2 | Merchant denies an API key was issued | Account ownership | `created_at` + `api_key_hash` on `merchants` row | OK |
| R3 | Merchant claims they never deleted a customer | Account changes | No audit log on deletion | **Gap**: log user-initiated destructive actions to a separate append-only table |
| R4 | Operator denies running a manual SQL fix | DB integrity | None | **Gap**: same audit log |

### I — Information disclosure

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| I1 | Email enumeration via `/enroll/start` | Privacy | None — distinct error | **Open** (ISSUES #14) |
| I2 | Stored fingerprint descriptor exposure (DB leak) | Biometrics | AES-256-GCM at rest with `BIOMETRIC_ENCRYPTION_KEY` | OK at rest, but key rotation absent (ISSUES — KEY_MANAGEMENT plan) |
| I3 | API key exposure via URL logs | Auth bypass | None | **Open** (ISSUES #13) |
| I4 | PII (email) in application logs | Privacy | None | **Open** (ISSUES #23) |
| I5 | Stack traces in 4xx responses | Internal info | FastAPI doesn't include trace by default; we don't override | OK |
| I6 | Stripe key in `/config` response | Payment auth | Only the publishable key is returned | OK |
| I7 | Full customer list returned to merchant | Cross-tenant leak | Query filters by `merchant_id` from JWT | OK |
| I8 | Reflected customer name on dashboard | XSS-driven exfil | None | **Open** (ISSUES #7) |

### D — Denial of service

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| D1 | Brute-force `/authenticate` | Service availability + auth | 10/min/IP via slowapi | OK for `/authenticate` only |
| D2 | Brute-force `/login`, `/customers/verify-code` | Auth + accounts | None | **Open** (ISSUES #11, #12) |
| D3 | Large image upload | Memory | 5 MB cap via middleware | Bypassable via chunked encoding (ISSUES #22) |
| D4 | Many concurrent enrollments | DB connections | No pooling | **Gap** (ISSUES #27) |
| D5 | WebSocket connection flood | Memory | None — no per-IP limit on WS | **Gap** |
| D6 | Slow-loris on long-poll endpoints | Workers | None — single uvicorn worker | **Gap** |

### E — Elevation of privilege

| # | Threat | Asset | Mitigation today | Status |
|---|---|---|---|---|
| E1 | Customer JWT used as merchant JWT | Cross-tenant access | `verify_merchant_token` checks `type=="merchant"` | OK |
| E2 | Merchant JWT used as customer JWT | Pay as anyone | `verify_access_token` does NOT check `type` | **Open** (ISSUES #17) |
| E3 | `/pos/charge` cross-merchant | Money to wrong merchant | `verify_merchant_api_key` returns merchant; routes use that merchant_id | OK |
| E4 | Customer deletes another customer's account | Data loss | Code is per-email; verifying access requires the code sent to that email | OK |
| E5 | Operator escalates via direct DB | Everything | Limited DB access policy (`docs/ONBOARDING.md`) | Policy-only; not technically enforced |

## Threats by attacker class

### Drive-by attacker (no credentials, just internet access)

- D1, D5, D6 (DoS)
- I1 (enumeration)
- D3 (large upload)

### Compromised customer device (XSS in customer portal page)

- Limited; portal stores no long-lived auth.
- Could send `/customers/delete-account` if attacker also has the email +
  fresh code.

### Compromised merchant device (XSS in dashboard)

- I8 → S4 → full merchant takeover.
- Action: rotate API key, replace with new one (attacker's now-stolen one
  becomes authoritative until detected).
- This is the highest-impact non-server compromise scenario.

### Malicious customer (enrolling intentionally with payloads)

- I8: stored XSS via `full_name`.
- T2: tampered POST bodies.

### Malicious merchant

- Can call `/pos/charge` arbitrarily on their own terminal — but the
  fingerprint match still gates the actual charge.
- Could collude with a fingerprint-spoof attack on a stranger.
- Cannot read other merchants' data (verified via merchant_id scoping).

### Insider (operator with prod DB access)

- E5; today policy-only.
- Future: enforced via least-privilege DB roles + audit log.

## Risk register summary

| ID | Threat | Severity | Likelihood | Mitigation status |
|---|---|---|---|---|
| S5 | Fingerprint spoof | Critical | High at scale | Open — biometric SDK rebuild required |
| S1/S2 | Forged JWT (default secret) | Critical | Medium | Open — env validation needed |
| I8 / S4 | Stored XSS → merchant takeover | Critical | Easy to demonstrate | Open — render-time escape |
| S3 / I3 | API key in WS URL | High | Constant | Open — first-message auth |
| E2 | Token-type confusion on `/pay` | High | Easy | Open — type check |
| T2 | Client-controlled `merchant` string | Medium | Constant | Open — derive server-side |
| R3 / R4 | No deletion / operator audit log | Medium | Constant | Gap — audit table |
| D2 | Login + verify-code brute force | High | Easy | Open — rate limits everywhere |
| D5 | WebSocket flood | Medium | Easy | Gap |
| I4 / I1 | PII in logs / email enumeration | Medium | Constant | Open |

## Out of scope (explicit non-goals)

- DDoS mitigation at the edge — relies on the host (Render / Cloudflare in
  front).
- Defense against state actors. We protect against opportunistic and
  organized fraud, not nation-state threat models.
- Physical attacks on a kiosk tablet (tablet theft, USB attacks, screen
  scraping). Merchants are responsible for their hardware.

## Process

- This document is reviewed quarterly by a CODEOWNERS security entry.
- Every new endpoint / external integration triggers an update.
- Significant changes to the threat surface trigger an ADR.
