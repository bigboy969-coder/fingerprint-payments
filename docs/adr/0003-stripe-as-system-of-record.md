# ADR-0003: Stripe is the system of record for money

## Status

Accepted

## Date

2026-04-16 (backfilled from existing code)

## Context

FingerPay processes real USD through Stripe. We store a `transactions`
table locally with `stripe_payment_intent_id`, `amount`, `stripe_status`,
and `platform_fee`. The question is: when Stripe and our database disagree,
who wins?

## Decision

**Stripe is the authoritative source of truth for all financial data.**

Our `transactions` table is a denormalized convenience copy used for
dashboard queries and quick lookups. If there is ever a discrepancy between
our local record and Stripe's record (amount, status, payout state), Stripe
wins.

This means:

- We never "invent" a transaction locally. A `transactions` row is only
  created after Stripe returns a PaymentIntent ID.
- We never "correct" a Stripe charge by editing our DB. If a charge needs
  reversal, we issue a Stripe refund.
- Reconciliation runs from Stripe → local, not the other way.
- Merchant payout questions are answered by the Stripe Connect dashboard,
  not by our stats queries.

## Consequences

### Positive

- We never build or maintain a financial ledger. Stripe does this for us.
- Dispute/refund handling is Stripe's problem at the infrastructure level;
  we just react to webhooks.
- PCI scope stays minimal (SAQ A).
- Audit trail lives in Stripe, which is SOC 2 + PCI Level 1 certified.

### Negative

- If `record_transaction` fails after a successful Stripe charge, the local
  DB is missing a row but money moved. This is a known gap (ISSUES #6)
  mitigated by the pre-charge row pattern (ROADMAP sprint 2).
- Dashboard stats may temporarily lag Stripe reality (no real-time webhook
  sync today — ISSUES #16).
- We cannot answer "how much has merchant X earned?" purely from our DB;
  Stripe's Connect balance is authoritative.

### Neutral

- We will build a daily reconciliation job that pulls from Stripe and
  surfaces mismatches, rather than trying to keep the local table perfectly
  in sync.

## Alternatives considered

### A. Build a double-entry ledger locally

Full accounting — credits, debits, journal entries. Rejected because:
(a) massive complexity for a payments startup, (b) Stripe already does
this, (c) regulatory burden of maintaining our own financial records.

### B. Event-sourced transaction log

Append-only event stream, replay to derive state. Overkill for pilot
scale. Could revisit if we move to Vercel Queues or Kafka in the future.

## References

- `app/services/stripe.py` — Stripe API wrapper
- `app/db/transactions.py` — `record_transaction`
- `docs/PCI_COMPLIANCE.md` — SAQ A justification
- `docs/ISSUES.md` #6 — charge-success / DB-failure gap
- `docs/ISSUES.md` #16 — no Stripe webhooks
