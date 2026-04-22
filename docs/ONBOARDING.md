# Engineering Onboarding

You're shipping changes to a payments and biometrics system. The bar is
high. This guide gets you to your first merged PR safely.

## Day 1 — set up

1. Read, in order:
   - This file.
   - [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
   - [`docs/DATA_FLOW.md`](./DATA_FLOW.md)
   - [`docs/SECURITY.md`](./SECURITY.md)
   - [`docs/ISSUES.md`](./ISSUES.md) — current known defects
2. Get repo access. Confirm you're added to `CODEOWNERS`.
3. Local setup:
   ```bash
   git clone <repo> && cd fingerprint-payments
   make setup
   cp .env.example .env   # ask the team for test values
   make dev
   ```
4. Walk through every user-visible flow on your local machine:
   - Marketing landing page (`/`)
   - Merchant signup → dashboard (`/business`)
   - Kiosk enrollment with `test_fingerprint.png` (`/kiosk`)
   - Customer self-service portal (`/my-account`)
   - POS charge from curl: `POST /pos/charge` with your test API key

## Day 2 — orient

5. Read [`docs/API.md`](./API.md) and [`docs/DATABASE.md`](./DATABASE.md).
6. Read [`docs/CODING_STANDARDS.md`](./CODING_STANDARDS.md) and
   [`docs/GIT_WORKFLOW.md`](./GIT_WORKFLOW.md).
7. Skim every file in `app/routes/`, `app/db/`, `app/services/`. Don't try to retain
   it all — just learn the shape.
8. Read the seed ADRs in [`docs/adr/`](./adr/).

## Day 3 — first PR

Pick a small task from [`docs/ISSUES.md`](./ISSUES.md) tagged P3, or a docs
typo. Open a draft PR. Walk through the PR template. Get one approval. Merge.

This proves your environment, CI, and review path work end-to-end before you
touch anything sensitive.

## Week 1

- Pair with a `CODEOWNERS` security entry on one Stripe-touching change.
- Read [`docs/THREAT_MODEL.md`](./THREAT_MODEL.md),
  [`docs/PRIVACY.md`](./PRIVACY.md),
  [`docs/BIOMETRIC_DATA_POLICY.md`](./BIOMETRIC_DATA_POLICY.md),
  [`docs/PCI_COMPLIANCE.md`](./PCI_COMPLIANCE.md),
  [`docs/KEY_MANAGEMENT.md`](./KEY_MANAGEMENT.md).
- Get added to PagerDuty (or whatever the on-call rotation is) as a
  shadow.
- Do one customer-portal flow with a real Resend email; confirm verification
  code arrives.

## Month 1

- Take primary on a P1 from `docs/ISSUES.md`.
- Sit through one incident as an observer (or read the most recent
  postmortem in `docs/runbooks/`).
- Write your first ADR or RFC for any non-trivial design choice you make.

## Permissions checklist

| Service | Why | Who grants |
|---|---|---|
| GitHub repo | Read + write to your branches | CTO / org admin |
| Stripe (test mode) | Local development | Stripe team admin |
| Stripe (live mode) | **Read-only by default**; write needs justification | CTO |
| Render dashboard | View deploys, logs | Platform owner |
| Resend | Sender domain config | Platform owner |
| PostgreSQL prod console | **Last resort only**; use logs and APIs first | CTO |

## Things you should never do

- Commit a secret. Rotate immediately if you do; tell the security owner.
- `git push --force` to `main`, ever.
- Run anything against the production database directly without a paired
  reviewer watching.
- Bypass `--no-verify` on commit hooks.
- Test production with a real customer's email or fingerprint without
  written consent.
- Add a new dependency without an entry in
  [`docs/TECH_RADAR.md`](./TECH_RADAR.md) or a one-paragraph ADR.

## Asking for help

Default to async (PR comments, repo discussions). For blocking questions,
ping in the team channel. For security-sensitive questions, **never** post
in a public channel — DM a `CODEOWNERS` security entry.

## Glossary

- **Kiosk** — the in-store tablet running `/kiosk`. Has the fingerprint
  scanner. Holds a persistent WebSocket to the server.
- **POS** — the merchant's existing point-of-sale system. Calls
  `/pos/charge` to start a payment.
- **Merchant** — the business using FingerPay. Has a dashboard, an API key,
  and a Stripe Connect account.
- **Customer** — the end user paying with a fingerprint. Has a Stripe
  Customer + saved PaymentMethod.
- **Connect** — Stripe Connect Express. Routes funds to the merchant's
  bank with `application_fee_amount` retained by FingerPay.
- **Descriptor** — the ORB feature vector extracted from a fingerprint
  image. Encrypted at rest with `BIOMETRIC_ENCRYPTION_KEY`.
- **Session** (enrollment) — the row in `enrollment_sessions` that ties a
  kiosk QR scan to a phone form submission.
