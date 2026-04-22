# FingerPay — Engineering Documentation

A CTO/full-stack walkthrough of the FingerPay codebase. These docs are
descriptive of *what is*, not aspirational. Where the code is wrong,
risky, or incomplete, that is called out plainly.

**New here?** Start with [ONBOARDING.md](./ONBOARDING.md).
**Triaging?** Start with [ISSUES.md](./ISSUES.md).

---

## System overview

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | High-level system, components, runtime topology |
| [DATA_FLOW.md](./DATA_FLOW.md) | Sequence walkthroughs: enroll, authenticate, pay, POS, Connect |
| [API.md](./API.md) | Every HTTP / WebSocket endpoint, request/response shapes |
| [DATABASE.md](./DATABASE.md) | Schema, columns, queries, migration story |

## Security, compliance, and privacy

| Doc | Purpose |
|---|---|
| [SECURITY.md](./SECURITY.md) | Trust boundaries, secrets, biometrics, risk register |
| [THREAT_MODEL.md](./THREAT_MODEL.md) | STRIDE threat analysis per actor and boundary |
| [PRIVACY.md](./PRIVACY.md) | What data we collect, lawful basis, data subject rights |
| [BIOMETRIC_DATA_POLICY.md](./BIOMETRIC_DATA_POLICY.md) | Fingerprint handling: BIPA, GDPR Art. 9, consent, breach |
| [KEY_MANAGEMENT.md](./KEY_MANAGEMENT.md) | Every secret, rotation procedures, compromise playbook |
| [PCI_COMPLIANCE.md](./PCI_COMPLIANCE.md) | SAQ A scope, what keeps us out of PCI scope |
| [DATA_RETENTION.md](./DATA_RETENTION.md) | Retention periods, deletion, pseudonymization |

## Engineering process

| Doc | Purpose |
|---|---|
| [ONBOARDING.md](./ONBOARDING.md) | New engineer day 1 through month 1 |
| [CODING_STANDARDS.md](./CODING_STANDARDS.md) | Python style, frontend rules, logging, SQL |
| [GIT_WORKFLOW.md](./GIT_WORKFLOW.md) | Branching, commits, PRs, hotfixes |
| [TESTING.md](./TESTING.md) | Test pyramid, layout, fixtures, coverage |
| [CI_CD.md](./CI_CD.md) | GitHub Actions pipeline, branch protection |
| [RELEASE_PROCESS.md](./RELEASE_PROCESS.md) | Versioning, tagging, rollback, checklist |
| [OBSERVABILITY.md](./OBSERVABILITY.md) | Logs, metrics, traces, alerting plan |

## Operations and incidents

| Doc | Purpose |
|---|---|
| [OPERATIONS.md](./OPERATIONS.md) | Local dev setup, env vars, deploy targets, scaling |
| [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) | Severity definitions, response flow, communication |
| [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md) | RTO/RPO, failure scenarios, backup, restore, drills |
| [POSTMORTEM_TEMPLATE.md](./POSTMORTEM_TEMPLATE.md) | Blameless postmortem template |

## Planning and tracking

| Doc | Purpose |
|---|---|
| [ISSUES.md](./ISSUES.md) | **All known bugs, gaps, and risks (P0–P3)** |
| [ROADMAP.md](./ROADMAP.md) | Prioritized fix plan, sprint-by-sprint |
| [TODO.md](./TODO.md) | Development checklist with checkboxes |
| [DEFERRED.md](./DEFERRED.md) | Items consciously deferred with unblock criteria |

## Architecture Decision Records

Decisions with rationale, captured as they're made. See
[ADR-0001](./adr/0001-record-architecture-decisions.md) for why we do this.

| ADR | Decision |
|---|---|
| [0000](./adr/0000-template.md) | Template |
| [0001](./adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [0002](./adr/0002-dual-database-sqlite-postgres.md) | Dual-database layer (SQLite dev / PostgreSQL prod) |
| [0003](./adr/0003-stripe-as-system-of-record.md) | Stripe is the system of record for money |
| [0004](./adr/0004-biometric-encryption-at-rest.md) | Encrypt biometric descriptors with AES-256-GCM |
| [0005](./adr/0005-single-process-pilot-constraint.md) | Single-process deployment as a pilot constraint |

## RFC process

For non-trivial proposals that need design review before implementation.
Template: [`rfc/TEMPLATE.md`](./rfc/TEMPLATE.md).

---

## TL;DR for a new engineer

- **Stack:** FastAPI (Python 3.11) + SQLite (dev) / PostgreSQL (prod) + Stripe + Resend.
- **Single process.** All state besides the DB lives in process memory. Multi-worker deploys break POS.
- **Biometric matching is demo-grade.** ORB descriptors, linear scan, no liveness. Suitable for prototype only.
- **Known P0s exist.** See [ISSUES.md](./ISSUES.md) — Connect sync broken, monthly fee math, XSS, JWT default secret.

## Repo map

```
fingerprint-payments/
├── app/
│   ├── main.py              FastAPI app, middleware, route registration
│   ├── db/
│   │   ├── __init__.py      Public API re-exports
│   │   ├── connection.py    Connection management
│   │   ├── schema.py        Schema DDL
│   │   ├── users.py         User queries
│   │   ├── merchants.py     Merchant queries
│   │   ├── transactions.py  Transaction queries
│   │   ├── sessions.py      Session queries
│   │   └── tokens.py        Token/code queries
│   ├── routes/
│   │   ├── enroll.py        Two-device enrollment (kiosk QR <-> phone)
│   │   ├── authenticate.py  Fingerprint -> JWT
│   │   ├── pay.py           JWT -> Stripe charge
│   │   ├── merchants.py     Signup, login, dashboard, Connect, password reset
│   │   ├── customers.py     Self-service portal (verify code -> view/delete)
│   │   └── pos.py           WebSocket terminal + POS-driven charge requests
│   └── services/
│       ├── biometrics.py    OpenCV ORB feature extraction + matching
│       ├── crypto.py        AES-256-GCM for fingerprint descriptors
│       ├── jwt.py           HS256 access + merchant tokens
│       └── stripe.py        Stripe wrappers (Customer, PaymentIntent, Connect)
├── static/                  Vanilla HTML/JS pages (kiosk, enroll, dashboard, etc.)
├── docs/                    This documentation suite
│   ├── adr/                 Architecture Decision Records
│   └── rfc/                 Request for Comment proposals
├── .github/
│   ├── workflows/ci.yml     CI pipeline
│   ├── dependabot.yml       Automated dependency updates
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/      Bug report, feature request
├── Dockerfile               Single-stage Python 3.11-slim
├── Makefile                 Dev commands: setup, dev, lint, test, etc.
├── pyproject.toml           Tool config (ruff, black, mypy, pytest)
├── .pre-commit-config.yaml  Pre-commit hooks
├── .env.example             Env var template
├── requirements.txt         Runtime dependencies (unpinned — pin next)
├── CONTRIBUTING.md          How to contribute
├── SECURITY.md              Vulnerability disclosure policy
├── CHANGELOG.md             Keep-a-changelog
└── CODEOWNERS               GitHub review routing
```
