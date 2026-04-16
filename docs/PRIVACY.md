# Privacy

How FingerPay handles personal data. This document is the engineering
counterpart to the public Privacy Policy and is the source of truth for
what we collect, why, where it lives, and how long we keep it.

## Data we collect

### Customer (end user paying with a fingerprint)

| Data | Where | Why | Retention |
|---|---|---|---|
| Full name | `users.full_name`, Stripe Customer | Receipts, dashboards, support | While account exists |
| Email | `users.email`, Stripe Customer | Identity, customer portal access, support | While account exists |
| Phone | `users.phone` (optional) | Future SMS notifications, support | While account exists |
| Card details (PAN, expiry, CVV) | **Never on our servers** — collected by Stripe Elements directly | Payment | Stripe's retention; we hold only the `payment_method_id` reference |
| Stripe customer ID | `users.stripe_customer_id` | Charge linkage | While account exists |
| Stripe payment method ID | `users.stripe_payment_method_id` | Off-session charges | While account exists |
| Fingerprint descriptor (ORB feature vector) | `fingerprints.descriptor`, AES-256-GCM encrypted | Authentication | While account exists |
| Fingerprint image | **Not stored**; written to `temp_uploads/` then deleted | Feature extraction | Seconds (subject to ISSUES #32 cleanup gap) |
| Transaction history (amount, merchant, status, timestamp) | `transactions` | Customer & merchant dashboards, reconciliation | 7 years (financial records); see DATA_RETENTION.md |
| Verification codes | `customer_verification_codes` | Self-service portal access | 10 minutes |
| IP address | Logs only (currently — no DB) | Rate limiting, abuse | Log retention (target: 30 days) |

### Merchant (business owner)

| Data | Where | Why | Retention |
|---|---|---|---|
| Business name | `merchants.business_name` | Display | While account exists |
| Contact name | `merchants.name` | Display, support | While account exists |
| Email | `merchants.email` | Login, support, password reset | While account exists |
| Password hash (bcrypt) | `merchants.password_hash` | Login | While account exists |
| API key hash (sha256) | `merchants.api_key_hash` | Auth | While account exists |
| Stripe Connect account ID | `merchants.stripe_connect_id` | Payouts | While account exists |
| Stripe Connect onboarding data (legal name, bank, ID, etc.) | **Stripe only** | KYC | Stripe's retention |
| Reset tokens | `password_reset_tokens` | Password reset | 1 hour |

### Operator (us)

- Application logs (request lines, errors, warnings) on stdout, currently
  visible to whoever has Render access.

## Special-category data

The fingerprint descriptor is **biometric data** — a special category
under GDPR Art. 9 and regulated under the Illinois Biometric Information
Privacy Act (BIPA) and similar laws elsewhere.

Treated as a separate data class with stricter handling. See
[`docs/BIOMETRIC_DATA_POLICY.md`](./BIOMETRIC_DATA_POLICY.md) for the full
policy.

## Lawful basis (GDPR)

| Processing | Basis |
|---|---|
| Card storage / charges | Performance of contract (Art. 6(1)(b)) |
| Biometric storage / matching | Explicit consent (Art. 9(2)(a)) — must be obtained at enrollment |
| Marketing | Not currently performed; would require consent (Art. 6(1)(a)) |
| Fraud detection / abuse prevention | Legitimate interest (Art. 6(1)(f)) |
| Logging IPs | Legitimate interest (Art. 6(1)(f)) |

## Data subject rights

We implement these via the customer portal (`/my-account`) and by request:

| Right | How |
|---|---|
| Access (Art. 15) | Customer portal "view info" + on-request transaction export |
| Rectification (Art. 16) | On-request — no in-product editor today |
| Erasure (Art. 17) | Customer portal "Delete my account" — wipes user, fingerprints, transactions, attempts Stripe customer delete |
| Restriction (Art. 18) | On-request manual flag (no `is_active` enforcement today — ISSUES #38) |
| Portability (Art. 20) | On-request JSON export |
| Object (Art. 21) | On-request |

**Erasure caveat:** financial records have a 7-year retention requirement
in many jurisdictions. We pseudonymize transaction rows on deletion (today
we hard-delete; this is not yet compliant — see ROADMAP). Stripe also
retains its own copy.

## Data minimization

Designed to keep the smallest possible footprint:

- We do not store card PAN, expiry, or CVV. Ever.
- We do not store fingerprint images.
- We do not log the request body of POSTs.
- We do not collect data we don't use (no birth date, no address — except
  the postal code Stripe asks for during card setup, which goes to
  Stripe, not us).

## Cross-border transfers

- Stripe is a US company; Stripe handles its own cross-border compliance
  (SCCs, DPF where applicable).
- Resend is US-based.
- Render hosts in the region you select; default is US.
- For any EU-based customer enrollment, we rely on the EU-US Data Privacy
  Framework being valid + Standard Contractual Clauses with vendors.
  Verify before launching in the EU.

## Vendor list (sub-processors)

| Vendor | Purpose | Data sent | DPA |
|---|---|---|---|
| Stripe | Payments, KYC | Customer name, email, payment data, merchant business + bank details | Stripe DPA accepted at signup |
| Resend | Transactional email | Customer/merchant email, code/reset link | Verify on Resend account |
| Render | Hosting | All of the above transit through Render | Verify Render DPA |
| GitHub | Source code, logs of operator actions | None customer-facing | Standard DPA |

## Children

We do not knowingly collect data from anyone under 13 (US) / 16 (EU). If
discovered, the account is deleted. Practically: a fingerprint payments
service has no plausible reason to be used by a minor.

## Logging policy (PII safety)

Mandatory rules for any code path that calls `logger`:

- **Never** log full email; if needed for debugging, use a hash or
  partial mask (`u***@example.com`).
- **Never** log full name, phone number, postal code.
- **Never** log fingerprint descriptors, even encrypted bytes.
- **Never** log JWTs, API keys, password hashes.
- **OK** to log numeric IDs (`merchant_id`, `user_id`), Stripe IDs
  (`pi_...`, `cus_...`, `acct_...`).

The current code violates this rule in `app/routes/customers.py:67`. Tracked
in `docs/ISSUES.md` #23.

## Backups

Backups inherit the production retention rules. When we delete a customer,
backup snapshots taken before the deletion still contain the data. A
deletion request is fully satisfied when:

1. Live DB row is deleted.
2. The next full backup snapshot is taken (without the row).
3. All snapshots that contained the row are aged out per retention.

For users who request immediate hard erasure (right to be forgotten,
strong form), document the backup window in the response. Currently 30
days post-deletion.

## Privacy review

Every new feature that touches customer or merchant data requires a
privacy checklist completed in the PR:

- [ ] What data is collected, where is it stored, why?
- [ ] Is there a less-invasive alternative?
- [ ] Does this require consent renewal?
- [ ] Is this logged? If yes, is it PII-safe?
- [ ] Does this affect retention?
- [ ] Does this introduce a new sub-processor?

CTO sign-off required for any "yes" beyond logging.

## Out of scope

- Cookie banners (no first-party cookies set today).
- CCPA "Do Not Sell" (we don't sell data).
- Marketing-tracking pixels (none used).
