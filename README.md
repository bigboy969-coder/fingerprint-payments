# FingerPay

Pay with your finger. No phone, no wallet. Just you.

A FastAPI service that pairs fingerprint authentication with Stripe payments,
designed for in-store use via a kiosk tablet alongside an existing POS.

## Quick start

```bash
make setup                # creates venv, installs deps + pre-commit hooks
cp .env.example .env      # fill in your keys — see docs/OPERATIONS.md
make dev                  # runs uvicorn on :8000 with hot reload
```

If `make` is not available:

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open:
- http://localhost:8000/ — marketing landing page
- http://localhost:8000/kiosk — in-store kiosk (enrollment + payment)
- http://localhost:8000/business — merchant signup
- http://localhost:8000/business/dashboard — merchant dashboard
- http://localhost:8000/my-account — customer self-service portal

## Documentation

Full engineering documentation lives in [`docs/`](./docs/README.md).

| Area | Key docs |
|---|---|
| **Start here** | [Onboarding](./docs/ONBOARDING.md), [Architecture](./docs/ARCHITECTURE.md) |
| **System** | [API](./docs/API.md), [Data flow](./docs/DATA_FLOW.md), [Database](./docs/DATABASE.md) |
| **Security** | [Security](./docs/SECURITY.md), [Threat model](./docs/THREAT_MODEL.md), [Biometric policy](./docs/BIOMETRIC_DATA_POLICY.md) |
| **Compliance** | [PCI](./docs/PCI_COMPLIANCE.md), [Privacy](./docs/PRIVACY.md), [Data retention](./docs/DATA_RETENTION.md), [Key management](./docs/KEY_MANAGEMENT.md) |
| **Process** | [Contributing](./CONTRIBUTING.md), [Coding standards](./docs/CODING_STANDARDS.md), [Git workflow](./docs/GIT_WORKFLOW.md), [Testing](./docs/TESTING.md) |
| **Ops** | [Operations](./docs/OPERATIONS.md), [CI/CD](./docs/CI_CD.md), [Releases](./docs/RELEASE_PROCESS.md), [Observability](./docs/OBSERVABILITY.md) |
| **Incidents** | [Incident response](./docs/INCIDENT_RESPONSE.md), [DR](./docs/DISASTER_RECOVERY.md), [Postmortem template](./docs/POSTMORTEM_TEMPLATE.md) |
| **Decisions** | [ADRs](./docs/adr/), [RFCs](./docs/rfc/), [Issues](./docs/ISSUES.md), [Roadmap](./docs/ROADMAP.md) |

**Triaging? Start with [`docs/ISSUES.md`](./docs/ISSUES.md).**

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Security

See [`SECURITY.md`](./SECURITY.md) for the vulnerability disclosure policy.

## License

See [LICENSE](./LICENSE).
