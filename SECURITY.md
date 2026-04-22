# Security Policy

## Reporting a vulnerability

If you believe you've found a security issue in FingerPay, **do not open a
public GitHub issue**.

Email **security@fingerpay.example** (replace with the real address before
publishing) with:

- A description of the issue and its potential impact.
- Steps to reproduce, or a proof-of-concept.
- Your name and how you'd like to be credited (or "anonymous").

You will receive an acknowledgement within **2 business days** and a status
update within **7 days**.

## Scope

In scope:

- This repository's source code.
- The hosted production deployment at `fingerprint-payments.onrender.com` (or
  whichever host is current — see `APP_BASE_URL`).
- The customer-facing static pages served from `/static/*`.

Out of scope:

- Third-party services we depend on (Stripe, Resend, Render). Report those
  to the vendor.
- Social engineering of FingerPay employees.
- Denial-of-service via volumetric attack.
- Vulnerabilities requiring physical access to a kiosk tablet.
- Self-XSS that requires the user to paste attacker-controlled content into
  their own browser console.

## Safe harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations, data destruction,
  and service interruption.
- Test only on accounts they own or have explicit permission to test.
- Disclose privately first and give us reasonable time to fix.
- Do not exfiltrate customer data beyond what is necessary to demonstrate
  the issue.

## Severity & response targets

| Severity | Examples | Triage SLA | Patch SLA |
|---|---|---|---|
| Critical | Auth bypass, fund movement without consent, biometric data exposure, key disclosure | 4 hours | 48 hours |
| High | Privilege escalation, stored XSS in dashboards, Stripe Connect bypass | 1 business day | 7 days |
| Medium | Reflected XSS, CSRF, info disclosure not involving PII | 3 business days | 30 days |
| Low | Missing security headers, version disclosure, best-practice deviations | 7 business days | 90 days |

## Disclosure

We follow a **90-day disclosure window** by default. After a fix is
deployed, you may publish details. We may request an extension for
particularly complex issues, with reasonable justification.

## Recognition

We don't yet run a paid bounty program. Verified reports are credited in
`CHANGELOG.md` and on a public security page once we publish one.

## Known weaknesses

The current codebase has a documented set of known security issues — see
[`docs/ISSUES.md`](./docs/ISSUES.md). Reports of items already in that list
are welcome but won't trigger the SLAs above.
