# Biometric Data Policy

Fingerprints are different from every other data class we touch. They
cannot be revoked, rotated, or reissued. This policy is non-negotiable.

## What we treat as biometric data

- Raw fingerprint images (transient — never persisted).
- ORB feature descriptors derived from those images
  (`fingerprints.descriptor`).
- Any metric or hash derived from the descriptor that could be used to
  link a person across systems.

If you are unsure whether something counts as biometric data, treat it as
biometric data and ask in review.

## Regulatory landscape

| Regime | Relevance | Key obligations |
|---|---|---|
| **GDPR Art. 9** (EU/EEA, UK) | Biometric data used to uniquely identify a person is a special category | Explicit consent, narrow purpose, retention limits, breach notification 72h |
| **BIPA** (Illinois, US) | Captures, stores, or uses biometric identifiers | Written informed consent, written retention/destruction policy, no sale, **private right of action** with statutory damages ($1,000–$5,000 per violation) |
| **TIPA** (Texas) | Similar to BIPA | Consent, no sale, destroy when purpose fulfilled or 1 year inactive |
| **CCPA / CPRA** (California) | Treats biometric data as sensitive personal information | Right to limit use, disclosure, retention |
| **Washington, NY, etc.** | State-level laws are growing rapidly | Reassess annually |

## Consent

At enrollment, the customer must explicitly consent to:

1. Collection of their fingerprint.
2. Conversion of the fingerprint to a derived feature vector (descriptor).
3. Storage of the encrypted descriptor.
4. Use of the descriptor to authenticate them at the merchants where
   they have transacted.
5. Retention period (as documented below).

This consent must be:

- **Affirmative** — pre-checked boxes do not count.
- **Granular** — separate from the payment terms checkbox.
- **Documented** — store consent timestamp, version of the policy text
  consented to, IP, and the user_id.
- **Revocable** — the customer portal "Delete my account" satisfies this.

### Action item

The current enrollment page (`static/enroll.html`) does **not** present
a biometric consent checkbox or store consent metadata. This is a P0
compliance gap. Tracked in the roadmap; do not deploy to production
markets with biometric privacy laws (Illinois, Texas, Washington, EU)
without fixing.

## Storage

- Descriptors are encrypted at rest with AES-256-GCM.
- Encryption key (`BIOMETRIC_ENCRYPTION_KEY`) is loaded from env at
  process start.
- Key length: 32 bytes (256 bits), validated at load time.
- Nonce: 96 bits, randomly generated per descriptor.
- Storage location: same database as application data today. Recommended
  long-term: a separate, more-restricted database with no direct app
  account.

### Key management

See [`KEY_MANAGEMENT.md`](./KEY_MANAGEMENT.md) for the full policy.
Headlines:

- Single static key today.
- No KMS integration today.
- Key rotation is **not implemented**. A rotation requires re-encrypting
  every descriptor in place (envelope-encryption pattern would solve
  this; tracked in ROADMAP).
- Key compromise procedure documented in `INCIDENT_RESPONSE.md`.

## Use

- The descriptor is read only by `find_user_by_fingerprint` for
  authentication during a payment, and by `enroll_user` when stored.
- Descriptors are decrypted into RAM only for the duration of a match
  operation, then freed.
- Descriptors are **never** logged, transmitted to third parties, or
  exported.

## Retention

| Trigger | Action |
|---|---|
| Customer enrolled | Descriptor stored, encrypted |
| Customer initiates "Delete my account" via portal | Descriptor row deleted within the request |
| Customer inactive for 1 year (no transactions, no portal access) | Descriptor and account deleted; transaction history pseudonymized — **not yet implemented**, P1 |
| Service shutdown | All descriptors destroyed in primary + backups |

## Sale or transfer

We do not sell biometric data. We do not transfer biometric data to any
third party for any purpose. If we are acquired or wind down, the
descriptors are destroyed before any data transfer; new owners do not
receive them.

## Breach response

If `BIOMETRIC_ENCRYPTION_KEY` is compromised, or descriptors are
exfiltrated:

1. Treat as SEV-1 immediately. CTO + outside counsel engaged before any
   external communication.
2. Notification timelines:
   - **GDPR:** 72h to supervisory authority; affected individuals "without
     undue delay" if high risk.
   - **BIPA / state laws (US):** "as soon as practicable" to affected
     individuals; specific timelines vary by state.
3. Affected accounts: forced re-enrollment with a new key; old key
   permanently retired; old database decommissioned.
4. Public disclosure post-mitigation.

See [`INCIDENT_RESPONSE.md`](./INCIDENT_RESPONSE.md) for the full
playbook.

## What we won't do

- Use the descriptor for anything other than authentication at FingerPay
  merchants.
- Re-enroll a returning user without their consent re-affirmation if the
  consent text has changed.
- Build a "biometric search" feature ("look up this fingerprint across
  all customers") for merchants. Auth is 1:N internally; search is not a
  product feature.
- Train ML models on descriptors.
- Sell, share, or offer descriptors as a feature to a third-party SDK
  vendor.

## Operational disciplines

- Code that touches `app/services/biometrics.py`, `app/services/crypto.py`, or
  `app/db/` (fingerprint paths) requires two reviewers per
  `CODEOWNERS`, one of whom is a security entry.
- Quarterly review of this policy by CTO + legal.
- Annual penetration test focused on the biometric storage path.

## Limitations of the current implementation

To be transparent:

- The matcher is ORB feature comparison, not a NIST-certified biometric
  algorithm. False acceptance is statistically expected at scale.
- There is no liveness detection; a high-resolution photograph could be
  accepted as a real fingerprint.
- These limitations are **incompatible with claiming a biometric grade
  authentication system in marketing**. Public claims about security must
  match the implementation. See ROADMAP.md sprint 3 for the rebuild path.
