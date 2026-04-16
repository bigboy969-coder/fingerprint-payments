# ADR-0006: Decouple the monthly terminal fee from per-transaction charges

## Status

Accepted

## Date

2026-04-16

## Context

FingerPay charges merchants a $29/month terminal fee plus a per-transaction
fee (0.5% + $0.05). The original code bundled both fees into Stripe's
`application_fee_amount` on every PaymentIntent. The monthly fee was added
to the first transaction of each month.

This caused a P0 bug: Stripe requires `application_fee_amount <= amount`.
If the first transaction of the month was less than ~$29 (extremely common
for a coffee shop), Stripe rejected the PaymentIntent with HTTP 400. Every
merchant was unable to take their first small purchase of each month.

## Decision

**Remove the monthly fee from per-transaction `application_fee_amount`
entirely.** The per-transaction fee is now only:

```
fee = amount * 0.005 + $0.05
```

The $29 monthly terminal fee will be billed separately, out-of-band.
Options for the billing mechanism (to be decided in a future ADR):

1. Stripe Invoice on the merchant's Connect account, charged on the 1st.
2. Deducted from the merchant's Stripe Connect balance.
3. Billed via a separate Stripe Subscription.

Until out-of-band billing is implemented, the monthly fee is **not
collected**. This is an acceptable revenue gap for the pilot — better to
under-collect than to block every merchant's first small transaction.

## Consequences

### Positive

- Per-transaction fees can never exceed the transaction amount (the fee
  is always < 1% of amount for amounts > $5.56).
- No more Stripe rejections on small transactions.
- Simpler code: `calculate_platform_fee` has one parameter, not two.
- The `include_monthly` logic and `update_merchant_monthly_fee_month`
  call are removed from the hot path (`/pay`).

### Negative

- The $29/month fee is not collected until out-of-band billing is built.
  Revenue impact during pilot: $29/merchant/month.
- `merchants.last_monthly_fee_month` column is now unused (keep it for
  the future billing job).

### Neutral

- `MONTHLY_FEE` constant remains in `app/services/stripe.py` for the
  future billing job to reference.
- `update_merchant_monthly_fee_month` remains in `app/db/merchants.py`
  for the same reason.

## Alternatives considered

### A. Cap `application_fee_amount` at `amount - 1`

Defer the un-billed portion. Rejected: complex tracking of deferred
amounts, weird merchant statements ("why did I get charged $28.50 extra
on this $30 sandwich?"), and the monthly fee accumulates as debt.

### B. Only charge monthly on transactions > $30

Use the bundled approach but skip the monthly fee on small transactions.
Rejected: this creates unpredictable merchant billing and a perverse
incentive (merchants encourage small transactions to avoid the fee).

### C. Build the Stripe Invoice mechanism now

Correct long-term answer but not needed for pilot. We don't even have
Stripe webhooks yet. Build it in Phase 2-3.

## References

- `app/services/stripe.py` — `calculate_platform_fee` (simplified)
- `app/routes/pay.py` — monthly logic removed from charge flow
- `docs/ISSUES.md` #4 — the original bug report
- `tests/unit/test_stripe.py` — regression tests
