# Incident Response

What to do when production breaks. Calm, structured, blameless.

## Definitions

**Incident** — anything that materially impacts users, money, or trust:
outage, payment failures spiking, biometric data exposure, fraudulent
charges, leaked secret.

**Severity:**

| Sev | Definition | Examples | Response |
|---|---|---|---|
| SEV-1 | Customer-visible critical impact, money or biometric data at risk | Total outage, charges happening without consent, biometric DB exposed, JWT secret leaked, Stripe Connect payouts wrong, mass auth bypass | Page on-call immediately; CTO + security owner notified; all-hands until mitigated |
| SEV-2 | Significant degradation, no immediate financial/security harm | Dashboard down for all merchants, enrollment broken, p95 latency > 5s, single merchant locked out | Page on-call; mitigate in business hours if outside normal |
| SEV-3 | Partial degradation, workaround exists | One endpoint flaky, intermittent email failures, slow customer portal | Ticket; fix in next sprint |
| SEV-4 | Minor / cosmetic | Typo on dashboard, wrong amount formatting | Backlog |

**On-call** — single named person on a rotation. Picks up the page,
drives the incident.

**Incident commander (IC)** — for SEV-1, the on-call becomes IC by
default. IC owns coordination, not the keyboard.

**Scribe** — captures decisions and timestamps in the incident channel.
For SEV-1, IC appoints a scribe.

## Response flow

```
Page fires
   │
   ▼
On-call ACKs within 5 minutes (SEV-1) / 15 minutes (SEV-2)
   │
   ▼
Open incident channel: #inc-YYYYMMDD-<short-name>
Post the alert + a one-line summary
   │
   ▼
Triage:
  - What's broken? (symptom)
  - Who's affected? (blast radius)
  - When did it start? (correlate with deploys)
   │
   ▼
Mitigate first (rollback, feature flag, traffic shift). Diagnose later.
   │
   ▼
Communicate:
  - Internal: incident channel
  - External: status page (if public; once we have one)
  - Affected merchants: direct outreach for SEV-1
   │
   ▼
Resolve. Mark incident "monitoring" then "resolved" in channel.
   │
   ▼
Postmortem within 48 hours (mandatory for SEV-1, SEV-2; encouraged for SEV-3)
```

## Mitigation playbook

In order of preference (least-to-most disruptive):

1. **Rollback in Render dashboard.** Fastest path. ~2 min.
2. **Feature flag off.** If the broken code path is flagged.
3. **`git revert` + push.** When you can identify the bad commit and Render
   rollback isn't granular enough.
4. **Disable an endpoint** by returning 503 from a middleware shim.
5. **Stripe Restricted Key swap.** If a Stripe key is compromised: rotate
   in Stripe dashboard, push the new key as an env var update on Render,
   redeploy. **The old key remains valid until rotated** — this is a race.
6. **Biometric encryption key** — if leaked, you cannot rotate without
   re-enrolling all users. Document it as such; legal notification probably
   required (see `docs/BIOMETRIC_DATA_POLICY.md`).

## Communication templates

### Initial internal post (SEV-1 / SEV-2)

```
SEV-<n> declared
Title: <one-line summary>
Symptom: <what's broken>
Started: <UTC timestamp>
Impact: <who/what is affected, rough scale>
On-call IC: @<handle>
Scribe: @<handle>
Channel: #inc-YYYYMMDD-<short>
```

### Mitigation post

```
MITIGATED at <UTC timestamp>
Action: <what we did — e.g., "rolled back to deploy abc123">
Verification: <how we confirmed — e.g., "/healthz green, payment success
rate back to 99.5%">
Customer impact window: <start UTC> → <mitigation UTC>, ~<count> affected
Next: monitoring for <N> hours, postmortem to follow within 48h
```

### Postmortem-published post

```
RESOLVED. Postmortem: <link>
Action items: <count>, owners assigned, due <date>
```

### External (merchant-facing) for SEV-1 affecting payments

```
Subject: FingerPay payment service degradation — <date> <UTC>

Between <start> and <end>, customers attempting to pay via FingerPay
experienced <symptom>. <count> transactions were affected.

We have restored normal service and are <doing X> to prevent recurrence.

If you believe a transaction was incorrectly processed, please reply to
this email with the date, amount, and customer email. We will reconcile
against Stripe and refund any erroneous charges within <N> business days.

— FingerPay
```

## Special incident types

### Suspected compromise of `BIOMETRIC_ENCRYPTION_KEY`

This is the worst-case scenario. Fingerprints, once leaked, cannot be
"changed" by the user.

1. Page CTO and security lead. Skip business hours.
2. Engage outside counsel before any external communication.
3. Snapshot logs + access records.
4. Determine scope: how many user descriptors were potentially exposed?
5. **Do not "rotate" the key by re-encrypting.** That doesn't help —
   any actor with the old key already has plaintext. Plan for forced
   re-enrollment of all affected users with a new key + key-derived
   identifier, and decommission the leaked database.
6. Notification timelines per `docs/BIOMETRIC_DATA_POLICY.md` (BIPA: as
   soon as practicable; GDPR: 72h to supervisory authority).
7. Postmortem + public disclosure.

### Suspected fraud (a merchant or customer)

1. Freeze the merchant's API key (set `is_active = 0` in DB; today this is
   not enforced — see `docs/ISSUES.md` #38; do it manually as a stopgap).
2. Cap or pause the merchant's Stripe Connect payouts via the Stripe
   dashboard.
3. Preserve evidence: full transaction history, IP logs, dashboard access
   logs.
4. Escalate to CTO + legal.

### Stripe outage

Stripe publishes status at https://status.stripe.com. If they're red and we
mirror their failure, post in incident channel and wait. Customers get a
clear 402 already — no panic mitigation needed. Reconcile any
"requires_action" PaymentIntents once Stripe recovers.

## Escalation

If on-call is unreachable within 10 minutes (SEV-1) / 30 minutes (SEV-2),
escalate to:

1. Backup on-call (next in rotation).
2. CTO.
3. Anyone listed in `CODEOWNERS` for the affected surface.

## Things we never do during an incident

- Blame.
- Long debate about root cause before mitigating.
- Ad-hoc database edits in production without a paired observer.
- Email customers without checking with leadership first (SEV-1 only).
- Tweet about it.

## Postmortem

See [`POSTMORTEM_TEMPLATE.md`](./POSTMORTEM_TEMPLATE.md). Mandatory within
48 hours of SEV-1/SEV-2 resolution. Stored under
`docs/runbooks/postmortems/YYYY-MM-DD-<slug>.md`.
