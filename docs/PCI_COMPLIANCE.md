# PCI Compliance

How FingerPay stays out of PCI scope by leveraging Stripe.

## Scope claim

We claim **SAQ A** (Self-Assessment Questionnaire A): the simplest level
of PCI DSS compliance, applicable when:

> "All payment acceptance and processing are entirely outsourced to PCI
> DSS validated third-party service providers, and the merchant retains
> only paper reports or receipts of cardholder data, neither stores,
> processes, nor transmits any cardholder data on its systems or
> premises."

This is justifiable today because:

1. **Cardholder data is collected by Stripe Elements**, not by our code.
   The customer's phone loads `https://js.stripe.com/v3/` directly. The
   PAN, expiry, and CVV are POSTed from the browser to Stripe; FingerPay
   only receives the `payment_method_id` reference.
2. **We never touch PAN.** No card numbers in logs, DB, or any server-side
   path.
3. **Charges are made via Stripe APIs** using a `customer` + `payment
   _method_id` reference; we never resubmit PAN.
4. **Stripe is PCI DSS Level 1 certified**, which is the highest level.

## What you must NOT do

Doing any of the following pulls us into a higher SAQ scope (likely
SAQ A-EP or SAQ D), with significantly more obligations:

- Build a card form in our own HTML inputs instead of Stripe Elements.
- Proxy card data through our backend before sending to Stripe.
- Log or store PAN, expiry, CVV, magnetic stripe data, or PIN block.
- Tokenize or hash PAN ourselves.
- Receive raw card data from a third-party POS without going through
  Stripe's PCI-validated path.

## What you must do

- All new card-collection surfaces use Stripe Elements (or another
  Stripe PCI-validated method).
- Confirm Subresource Integrity is **not** required for `js.stripe.com/v3/`
  (per Stripe's documentation; SRI on the Stripe loader breaks future
  versions). Other CDN scripts must use SRI.
- Annual SAQ A self-assessment, signed by CTO. Stored under
  `docs/runbooks/compliance/SAQ-A-YYYY.pdf`.
- Quarterly external vulnerability scan (ASV scan) on the production
  domain. Required by SAQ A under PCI DSS 4.0.

## Architecture confirmations

| Path | Cardholder data exposure? |
|---|---|
| `static/enroll.html` | None — Stripe Elements isolates the iframe |
| `app/routes/enroll.py` `/start` | None — only `payment_method_id` received |
| `app/services/stripe.py:create_customer` | None — passes `payment_method_id` |
| `app/services/stripe.py:charge_customer` | None — passes `customer` + `payment_method_id` |
| Logs | None — we never log card data |
| Database | None — `users.stripe_customer_id` and `users.stripe_payment_method_id` are Stripe references, not card data |

If a future change introduces a path where cardholder data passes through
our servers, **stop and consult the CTO**. PCI scope is binary: you're in
or you're out, and getting out again is expensive.

## Stripe responsibilities

Stripe maintains:

- The PCI DSS Level 1 attestation.
- Tokenization infrastructure.
- Card-on-file storage.
- 3D Secure / SCA flows.

Stripe's Attestation of Compliance (AoC) is available in the Stripe
dashboard. Pull and store annually under `docs/runbooks/compliance/`.

## Our responsibilities (SAQ A)

Even at SAQ A, we have a small but real set of obligations:

| Requirement | Our control |
|---|---|
| Don't store cardholder data | Architectural — see above |
| Use a PCI-compliant service provider | Stripe |
| Maintain an Information Security Policy | This `docs/` directory |
| Train personnel on security | Onboarding includes `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, this file |
| Implement strong access controls | `CODEOWNERS`, branch protection, Render least-privilege |
| Restrict who has access to environments handling card data | Stripe dashboard access list reviewed quarterly |
| Maintain a vulnerability management program | `pip-audit`, `gitleaks`, dependabot in CI |
| Quarterly ASV scan | Engage an Approved Scanning Vendor; record results |
| Annual SAQ A signed by management | CTO signs |
| Incident response plan | `docs/INCIDENT_RESPONSE.md` |

## When SAQ A might no longer apply

- Direct integration with a non-Stripe PSP.
- Acceptance of card-present transactions via a hardware reader we own
  (would likely require SAQ B or P2PE).
- Storing receipts that include partial PAN.

If any of these come up, schedule a PCI scoping review **before** writing
code.

## Testing card data in dev/test

Use Stripe test cards only:
https://docs.stripe.com/testing#cards

A list of canonical test cards lives in `tests/fixtures/cards.py` once
the test suite exists.

Do not use real card numbers in any environment, even your own. If you
ever paste a real PAN into a test, treat it as a security incident: notify
the security owner, rotate any environment that may have logged it, and
document it.

## Audit trail (Stripe-side)

Stripe retains a full event log per Stripe account:

- Every API call (idempotency key, request body summary).
- Every webhook event sent.
- Every PaymentIntent state transition.
- Every Connect onboarding step.

This is the source of truth for any reconciliation. Our `transactions`
table is a denormalized convenience copy; Stripe wins ties.

## Vendor management

| Sub-processor | PCI scope they introduce | Our action |
|---|---|---|
| Stripe | They handle PAN; we are SAQ A by virtue of using them | Maintain Stripe DPA, annual AoC review |
| Render | Hosts our app; never sees card data | Verify Render's SOC 2 |
| Resend | Sends emails; never sees card data | Verify Resend's compliance posture |
| GitHub | Source control; no production cardholder data | n/a |

Adding a new sub-processor that could touch card data requires a PCI
scoping review.
