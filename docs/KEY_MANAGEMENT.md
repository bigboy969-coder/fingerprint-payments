# Key Management

How we handle every cryptographic key and secret used by FingerPay. The
goal is "no secret in source, no secret unrotatable, no secret without an
owner."

## Inventory

| Secret | Purpose | Algorithm | Length | Rotation today | Rotation target |
|---|---|---|---|---|---|
| `BIOMETRIC_ENCRYPTION_KEY` | Encrypts fingerprint descriptors | AES-256-GCM | 256-bit | None | Annual + on suspected compromise |
| `FINGERPAY_SECRET` | Signs all JWTs (customer + merchant) | HMAC-SHA-256 | ≥ 256-bit | None | Quarterly + on compromise |
| `STRIPE_SECRET_KEY` | Stripe API auth | Stripe-issued | n/a | Manual via Stripe dashboard | Annual + on compromise |
| `STRIPE_PUBLISHABLE_KEY` | Public, served by `/config` | Stripe-issued | n/a | Stripe-managed | Pair with secret rotation |
| Stripe webhook signing secret | Verify inbound webhooks | HMAC-SHA-256 | Stripe-managed | Per-webhook in Stripe dashboard | On webhook re-creation |
| `RESEND_API_KEY` | Email sending | Resend-issued | n/a | Manual via Resend dashboard | Annual + on compromise |
| `DATABASE_URL` | Postgres connection (with embedded password) | Random | n/a | Render-managed | Quarterly + on compromise |
| Merchant API keys | Per-merchant POS auth | `secrets.token_urlsafe(32)` | 256-bit entropy | Self-service via dashboard | On compromise (merchant-initiated) |
| Per-merchant API key hash | Stored in DB | SHA-256 | 256-bit | Recomputed on rotation | n/a |
| Bcrypt cost factor | Password hashing | bcrypt | default `gensalt()` (12 rounds) | n/a | Increase as hardware improves |
| Reset tokens | Password reset | `secrets.token_urlsafe(32)` | 256-bit entropy | Single-use, 1h TTL | n/a |
| Customer verification codes | Portal access | 6-digit numeric | ~20-bit entropy | Single-use, 10min TTL | Move to longer alphanumeric |
| TLS certificates | Public site | LetsEncrypt via Render | 2048-bit RSA / ECDSA | Auto-renewed | n/a |

## Storage

| Where | What | Acceptable? |
|---|---|---|
| Source code | Nothing. Ever. | No |
| `.env` (gitignored, local dev) | Dev-mode values only | Yes |
| `.env.example` (committed) | Placeholder names + format hints, no values | Yes |
| Render environment variables | All production secrets | Yes today; better target = secrets manager |
| GitHub Actions secrets | CI-only credentials (none for app secrets today) | Yes |
| Browser localStorage | **Merchant JWT** (currently) | No, see migration plan below |
| Browser cookies | Future home of merchant session | Yes (HttpOnly, Secure, SameSite=Strict) |
| Logs | None | No |
| Stack traces | None | No |
| Bug reports | None — redact before paste | No |

## Generation

```bash
# 32-byte hex (for AES key, JWT secret)
python -c "import secrets; print(secrets.token_hex(32))"

# URL-safe (for tokens)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never use `random.random()`, `uuid.uuid4()` (for crypto), or
hand-typed strings.

## Rotation procedures

### `FINGERPAY_SECRET`

JWTs signed with the old secret will be invalidated immediately on
rotation. All merchants will be logged out and must re-login. Customer JWTs
have a 2-min TTL so impact is minimal.

1. Generate new secret.
2. Update Render env var.
3. Trigger redeploy.
4. Notify merchants of forced re-login (banner on dashboard).

### `BIOMETRIC_ENCRYPTION_KEY`

**This is the hard one.** Today, rotation requires:

1. Decrypting every existing descriptor with the old key.
2. Re-encrypting with the new key.
3. Atomic swap (transactional).
4. Old key destroyed.

This is not implemented. Any rotation today requires a maintenance window
and a rotation script — write it before you need it.

**Better long-term design:** envelope encryption.
- Each descriptor encrypted with a per-row data key.
- Data keys encrypted with the master key.
- Rotation re-encrypts only the data keys, not the descriptors. O(rows)
  becomes O(1) for the actual descriptor data.

Tracked as a P2 in ROADMAP.

### `STRIPE_SECRET_KEY`

Stripe supports **rolling keys**:

1. In Stripe dashboard, "Roll API keys."
2. Stripe issues a new key. Old key remains valid for a configurable
   window (default 12h).
3. Update Render env var with new key. Redeploy.
4. Verify new key is in use (one successful charge in test mode → live).
5. Cancel the old key in Stripe.

### Merchant API keys

Self-service via `/merchants/regenerate-key`. Old key invalidated
immediately. Merchant must update their POS configuration.

A "soft rotate" pattern (old key valid for N hours after new key issued)
is not implemented — added complexity vs. operator-friendly atomic swap.
For pilot scale, operator-friendly is the right trade.

### `RESEND_API_KEY`

Issue new key in Resend, swap env var, deploy, revoke old key. Standard.

### `DATABASE_URL`

Render-managed. To rotate the embedded password:

1. Render dashboard → Postgres → Rotate password.
2. Render auto-updates the env var on the linked service.
3. Redeploy.
4. Verify with one DB-touching request.

## Compromise procedures

See [`INCIDENT_RESPONSE.md`](./INCIDENT_RESPONSE.md) for the operational
flow. Key-specific notes:

| Compromise | Recovery |
|---|---|
| `FINGERPAY_SECRET` | Rotate immediately. All sessions invalid. Ask merchants to confirm any suspicious dashboard activity. |
| `BIOMETRIC_ENCRYPTION_KEY` | **No technical mitigation.** Plaintext descriptors are extractable from any DB snapshot the attacker has. Force re-enrollment on a new system; legally notify per BIOMETRIC_DATA_POLICY. |
| `STRIPE_SECRET_KEY` | Roll in Stripe immediately. Audit Stripe activity for unauthorized API calls. Notify Stripe security. |
| `RESEND_API_KEY` | Rotate. Audit sent emails for impersonation attempts. |
| `DATABASE_URL` | Rotate. If the attacker had read access, treat all DB contents as exposed (proceed to merchant + customer notification). |
| Merchant API key | Rotate via dashboard. Review the merchant's recent transactions for fraudulent charges. |
| Merchant JWT | 24h max blast radius. No revocation today — rotate `FINGERPAY_SECRET` if the takeover is confirmed and material. |

## Access control

| Role | Can read | Can rotate |
|---|---|---|
| CTO | All | All |
| Security owner (in `CODEOWNERS`) | All | All |
| Senior engineer | None directly; Render dashboard for env names only | None |
| Engineer | None | None |
| On-call (during incident) | Whatever's needed to mitigate, with a paired observer | Yes for the affected secret |

The principle is: secrets live in Render's env config; humans don't copy
them around. If you find yourself emailing or Slack-ing a secret, stop.

## Merchant JWT migration plan (recap)

Today: stored in `localStorage`. Vulnerable to XSS.

Target:
- HttpOnly, Secure, SameSite=Strict cookie set on `/merchants/login`.
- Backend reads cookie, not Authorization header.
- CSRF protection via double-submit cookie or SameSite=Strict (the latter
  is sufficient for a non-iframe app).
- `localStorage` no longer touched.

Tracked as P1. Requires a coordinated frontend + backend change.

## Audit

- Annual key inventory review (CTO + security owner).
- Confirm every secret in this document still exists, still has an
  owner, still has a documented rotation procedure.
- Verify Render env list matches this document — no orphaned secrets.

## Things we will not do

- Roll our own crypto. Always use `cryptography.hazmat.primitives` or
  Stripe's primitives.
- Reuse a secret across environments.
- Store secrets in Git, even encrypted.
- Hardcode any value listed in this inventory.
