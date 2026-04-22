# Data Retention

What we keep, how long, and what triggers deletion.

## Retention table

| Data | Default retention | Trigger for deletion |
|---|---|---|
| **Customer account** (`users` row) | While account exists | Customer "Delete my account" via portal |
| **Fingerprint descriptor** (`fingerprints`) | While account exists | Same as account; cascade |
| **Transaction history** (`transactions`) | 7 years from creation | After 7 years, pseudonymize (drop user_id, retain financial fields) |
| **Stripe customer object** | While account exists | Customer deletion attempts Stripe `Customer.delete` |
| **Merchant account** (`merchants`) | While account exists | Merchant request |
| **Merchant API key (hash)** | Until rotated | Rotation creates new hash, drops old |
| **Stripe Connect account** | While account exists | Merchant-initiated Stripe deactivation |
| **Enrollment session** (`enrollment_sessions`) | 24 hours | Cron sweep — **not yet implemented** |
| **Password reset token** (`password_reset_tokens`) | 1 hour or until used | Used flag; cron sweep monthly |
| **Customer verification code** (`customer_verification_codes`) | 10 minutes or until used | Used flag; cron sweep daily |
| **Application logs** | 30 days | Log host's auto-rotation |
| **Metrics** | Indefinite (no PII) | n/a |
| **Traces** | 7 days | Tracing backend |
| **Database backups** | 30 days for daily; 12 months for monthly snapshots | Backup retention policy |
| **Temp upload files** (`temp_uploads/`) | Seconds (request lifecycle) | `try/finally` cleanup; cron sweep for orphans — **not yet implemented** |
| **CI artifacts** | 90 days | GitHub default |

## Why these numbers

- **7 years for transactions:** Standard financial-records retention in
  most jurisdictions (US, UK, EU). Stripe's own retention is independent.
- **30 days for logs:** Long enough for incident reconstruction; short
  enough to limit PII exposure.
- **30 days for daily backups:** Standard RPO horizon for SaaS.
- **24 hours for enrollment sessions:** A user who started enrollment but
  abandoned has no expectation of resumption. Holds session form data
  with PII (name, email).
- **1 hour for reset tokens:** Long enough for slow email delivery, short
  enough to limit replay window.
- **10 minutes for verification codes:** Industry standard.

## Pseudonymization for "deleted" customers

When a customer deletes their account, we hard-delete:

- `users` row.
- `fingerprints` row(s).
- `transactions` rows tied to that user (today; this is too aggressive
  for financial-records compliance).

**Recommended change** (P1, in ROADMAP):

- Hard-delete `users`, `fingerprints`, and any free-text PII fields.
- Pseudonymize `transactions`: set `user_id = NULL`, retain
  `merchant_id`, `amount`, `platform_fee`, `stripe_payment_intent_id`,
  `created_at`. The Stripe PaymentIntent ID is still a pointer to Stripe,
  but Stripe's customer linkage will also be deleted (we call
  `stripe.Customer.delete`).

This keeps the merchant's books accurate while erasing the personal
linkage.

## Backup retention vs. erasure requests

When a customer requests deletion (GDPR Art. 17 / "right to be
forgotten"):

1. Live DB row deleted within the request.
2. Confirmation sent to customer.
3. Backup snapshots taken before the deletion still contain the data.
4. Snapshots age out per the 30-day daily / 12-month monthly schedule.
5. Full erasure is complete after all snapshots containing the data have
   aged out (max 12 months).

If a customer demands immediate hard erasure including backups, this is
operationally expensive (restore each snapshot, delete row, re-snapshot)
and is rarely required. Our default response: explain the backup window
in the confirmation email.

## Operator data

- **Action logs** (deploys, env changes, manual DB edits): retain
  indefinitely, append-only. Today: GitHub commit history + Render
  dashboard log. Future: dedicated audit table for in-app
  operator actions (see `docs/THREAT_MODEL.md` R3/R4).

## Stripe-side retention

We don't control Stripe's retention. Headlines:

- Stripe retains transaction records for at least 7 years to meet financial
  reporting obligations.
- `stripe.Customer.delete` removes most customer data immediately, but some
  records (PaymentIntents) persist with pseudonymized references.
- Disputes have their own retention requirements.

For full detail, see Stripe's privacy and compliance documentation.

## Cleanup jobs (need to be built)

| Job | Frequency | Target |
|---|---|---|
| Expire stale enrollment sessions | Hourly | `enrollment_sessions WHERE created_at < NOW() - 24h` |
| Expire used/old reset tokens | Daily | `password_reset_tokens WHERE used=1 OR expires_at < NOW()` |
| Expire used/old verification codes | Hourly | `customer_verification_codes WHERE used=1 OR expires_at < NOW()` |
| Sweep orphan temp uploads | Hourly | `temp_uploads/*` older than 1h |
| Pseudonymize transactions of deleted customers | After deletion | One-shot per deletion |
| Inactive-account purge (1y no activity) | Monthly | `users WHERE last_seen_at < NOW() - 1y` (`last_seen_at` doesn't exist yet) |

These are tracked as P2 in `docs/ISSUES.md` #31, #32. Implement as
scheduled jobs (Render cron, or a periodic task in the app).

## Verification

Quarterly:

- Pull a random sample of "deleted" customer emails from past 90 days;
  verify no live row exists.
- Check that `enrollment_sessions` table size is bounded (no growth >
  expected).
- Check log retention on the host matches this document.
- Spot-check that backup snapshots older than the retention window are
  gone.

## Customer-facing copy

The Privacy Policy presented to customers must reflect this document.
When this document changes, update the Privacy Policy in the same PR (or
explicitly note that policy text needs revision). Do not let policy and
implementation diverge.
