# Disaster Recovery

How we recover from things going badly wrong. RTO/RPO targets, backup
strategy, restore procedures, and failure scenarios with concrete plans.

## Targets

| Metric | Target | Today's reality |
|---|---|---|
| **RTO** (recovery time objective) — max time to restore service | 1 hour for SEV-1 | Untested |
| **RPO** (recovery point objective) — max acceptable data loss | 1 hour | Depends on Render's backup cadence |
| **MTTD** (mean time to detect) | < 5 min for SEV-1 | Currently customer-driven; need monitoring |
| **MTTR** (mean time to repair) | < 30 min once detected | Untested |

These are **target** numbers. Today, with no monitoring and no DR drill,
they are aspirational. They become real once we test them.

## Failure scenarios and recovery plans

### Scenario 1: App process dies (single deploy fails)

**Impact:** All requests fail until restart.
**Detection:** Render's healthcheck triggers redeploy automatically.
**Recovery:** Render auto-restarts. ETA: 1-2 min.
**Manual override:** Roll back to previous deploy in Render dashboard.

### Scenario 2: Bad code reaches production

**Impact:** Some endpoints fail; payment success rate drops.
**Detection:** Error rate alert (once metrics ship); customer report;
manual smoke after deploy.
**Recovery:** Render rollback to previous deploy. ETA: 2-3 min.
**Long-term:** Forward-fix PR + new release. See
[`RELEASE_PROCESS.md`](./RELEASE_PROCESS.md).

### Scenario 3: Database corruption

**Impact:** Data inconsistency, possibly silent.
**Detection:** Hard — needs reconciliation against Stripe to detect.
**Recovery:**
1. Snapshot the corrupted DB before doing anything.
2. Identify the corruption window using application logs.
3. Restore the most recent backup taken **before** the corruption window.
4. Replay any transactions known to have happened after the backup
   (cross-reference Stripe).
5. Notify affected merchants.

### Scenario 4: Database host loss

**Impact:** All DB-backed endpoints 5xx.
**Detection:** `/readyz` (once it exists); error rate spike.
**Recovery:**
1. Provision new Postgres instance on Render.
2. Restore latest snapshot to the new instance.
3. Update `DATABASE_URL` in app env.
4. Redeploy app to pick up the new connection string.
5. Verify with smoke test.

ETA: 30 min if rehearsed, 2+ hours if not. **We have not rehearsed this.**

### Scenario 5: Stripe outage

**Impact:** `/pay` returns 402; enrollment fails at the SetupIntent step.
**Detection:** Stripe status page; spike in 402 responses.
**Recovery:**
1. No action required from us. Stripe will recover.
2. Reconcile any `requires_action` PaymentIntents that were stranded.
3. Communicate to merchants that this is a Stripe outage, not us.

### Scenario 6: `BIOMETRIC_ENCRYPTION_KEY` lost (not leaked)

**Impact:** All existing fingerprint descriptors are unusable. No one can
authenticate.
**Detection:** Authentication endpoint fails on first call.
**Recovery:**
1. **There is no recovery for the existing data.** Descriptors are
   permanently inaccessible.
2. Force re-enrollment for all customers. Generate a new key, store it
   safely, never lose it again.
3. Communicate honestly: "due to a technical issue, we need you to
   re-enroll your fingerprint at your next visit."

**Prevention:** Store the key in a secrets manager (AWS Secrets Manager,
GCP Secret Manager, Vault) with a backup off-host. Today the key lives
only in Render env. **This is a ticking bomb.** Tracked as P1.

### Scenario 7: `BIOMETRIC_ENCRYPTION_KEY` leaked

See [`INCIDENT_RESPONSE.md`](./INCIDENT_RESPONSE.md) "Suspected
compromise of `BIOMETRIC_ENCRYPTION_KEY`" and
[`BIOMETRIC_DATA_POLICY.md`](./BIOMETRIC_DATA_POLICY.md) "Breach
response."

This is the worst-case scenario. Plan accordingly.

### Scenario 8: GitHub repo loss / source code lost

**Impact:** Cannot deploy new versions.
**Detection:** GitHub down or repo deleted.
**Recovery:**
1. Every developer's local clone is a full backup.
2. Push to a new remote (GitLab / Bitbucket / self-hosted Git).
3. Update Render's source connection.

ETA: 1 hour.

**Prevention:** Mirror to a second Git host weekly.

### Scenario 9: Render goes away

**Impact:** Whole platform offline.
**Detection:** Render status page; full outage.
**Recovery:**
1. Use the Dockerfile to deploy to an alternative (Fly.io, Railway,
   AWS Fargate, GCP Cloud Run).
2. Restore Postgres backup to the new platform.
3. Update DNS to point at the new host.

ETA: 4 hours if the alternative is set up in advance, much longer
otherwise.

**Prevention:** Quarterly drill of deploying to a second platform.

### Scenario 10: Compromised admin / merchant account doing damage

**Impact:** Fraudulent charges, mass deletions, data exfil.
**Detection:** Anomalous activity (once monitoring exists), customer
complaints, Stripe dispute spike.
**Recovery:**
1. Disable the affected account: set `is_active=0` (once enforcement
   exists; for now manual DB edit), invalidate API keys, expire JWTs by
   rotating `FINGERPAY_SECRET`.
2. Audit all actions taken by the compromised account.
3. Reverse fraudulent charges via Stripe.
4. Notify affected customers.
5. Postmortem + harden.

## Backups

### Database

- Render-managed Postgres provides automatic daily snapshots.
- **Verify the schedule and retention** in the Render dashboard. Document
  the actual numbers here. As of writing, this is unconfirmed.
- Recommended target: daily snapshots for 30 days, weekly for 12 weeks,
  monthly for 12 months.
- **Off-platform backup:** weekly `pg_dump` to S3 (or equivalent),
  encrypted at rest with a key separate from `BIOMETRIC_ENCRYPTION_KEY`.
  Not implemented today.

### Source code

- GitHub is the primary; every clone is a backup.
- Recommended: scheduled mirror to a second Git host.

### Secrets

- Render env is the primary store.
- **Recommended:** secrets exported to an encrypted offline vault
  (1Password, Bitwarden, AWS Secrets Manager backup) updated every
  rotation.

### Static assets

- Versioned in Git; no separate backup needed.

## Restore procedures

### Restore Postgres from Render snapshot

1. Render dashboard → Postgres service → Backups.
2. Choose snapshot, click "Restore."
3. Render creates a new database. **It does not overwrite the existing
   one** by default — verify before redirecting traffic.
4. Update `DATABASE_URL` in the app service to point at the restored DB.
5. Redeploy app.
6. Run smoke test.
7. Once verified, decommission the old DB.

### Restore from off-platform `pg_dump` (when implemented)

```bash
# Verify the dump is intact
gunzip -t fingerpay-YYYY-MM-DD.sql.gz

# Restore to a new database
createdb fingerpay_restore
gunzip -c fingerpay-YYYY-MM-DD.sql.gz | psql fingerpay_restore

# Verify row counts vs. expected
psql fingerpay_restore -c "SELECT COUNT(*) FROM users, transactions, merchants;"
```

## Drills

We will run a DR drill **quarterly**. The drill exercises one scenario at
a time:

| Quarter | Scenario | Outcome to verify |
|---|---|---|
| Q1 | Bad code reaches production | Rollback in < 5 min, forward-fix in < 1h |
| Q2 | DB host loss | New DB provisioned + restored in < 1h |
| Q3 | Render outage | Failover deploy to alternative platform |
| Q4 | `BIOMETRIC_ENCRYPTION_KEY` lost (simulated) | Communication plan executed; re-enrollment flow ready |

Drills are scheduled, announced, and documented in
`docs/runbooks/dr-drill-YYYY-QN.md`.

## Things that are NOT in our DR plan today

- Multi-region active-active. Single-region is the pilot constraint.
- Read replicas for the database.
- Hot standby for the app process.
- Geographic failover for DNS.

These are pilot trade-offs. Document the decision in an ADR if/when they
change.

## Recovery responsibilities

| Scenario | Owner |
|---|---|
| App-level outage | On-call engineer |
| DB outage | On-call engineer + platform owner |
| Stripe / Resend / external | On-call engineer (mostly observe) |
| Key compromise | CTO + security owner + outside counsel |
| Source code loss | CTO + any senior engineer |

## What "recovered" means

A recovery is complete only when:

1. `/healthz` and `/readyz` are green.
2. A test transaction flows end-to-end (`/pos/charge` → kiosk scan →
   `/authenticate` → `/pay`).
3. Affected customers/merchants are notified (if SEV-1).
4. Postmortem is opened.
5. The action items from the postmortem are tracked.
