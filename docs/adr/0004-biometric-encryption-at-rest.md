# ADR-0004: Encrypt biometric descriptors at rest with AES-256-GCM

## Status

Accepted — key management improvements tracked in `docs/KEY_MANAGEMENT.md`.

## Date

2026-04-16 (backfilled from existing code)

## Context

FingerPay stores fingerprint feature descriptors (ORB keypoint vectors,
`numpy.uint8`, shape `(N, 32)`) in the database. Biometric data is
classified as special-category under GDPR Art. 9 and is regulated by BIPA
(Illinois), TIPA (Texas), and similar state laws. A database breach
exposing plaintext descriptors would be catastrophic — fingerprints cannot
be revoked or reissued.

We need encryption at rest that is:

- Strong enough to withstand a full database dump exfiltration.
- Decryptable at query time for matching (we run 1:N comparison in
  application code).
- Transparent to the database (it stores opaque bytes).

## Decision

Encrypt each descriptor with **AES-256-GCM** using a 32-byte key
(`BIOMETRIC_ENCRYPTION_KEY`) stored in the environment. Each descriptor
gets a unique random 96-bit nonce. The stored blob is `nonce || ciphertext
|| tag` (GCM appends the 16-byte tag to the ciphertext).

Implementation: `app/services/crypto.py`, using `cryptography.hazmat.primitives
.ciphers.aead.AESGCM`.

## Consequences

### Positive

- Standard, audited, FIPS-approved algorithm.
- Per-descriptor nonce means identical descriptors produce different
  ciphertexts — no equality leakage.
- GCM provides authentication — tampered ciphertexts are rejected.
- Simple implementation: 40 lines of code, no external KMS dependency.

### Negative

- **Single static key.** Loss = all biometrics permanently inaccessible.
  Compromise = full biometric DB exposure. No rotation mechanism today.
- **Key in env var.** Not in a secrets manager / HSM / KMS. A Render
  operator or anyone with env access can read it.
- **No envelope encryption.** Rotating the key requires decrypting and
  re-encrypting every descriptor (O(N) over the full table). With
  envelope encryption, we'd only re-encrypt the per-row data keys.
- **Decryption in application memory.** Every `/authenticate` call
  decrypts all descriptors into RAM for matching. A core dump or memory
  scrape during matching exposes plaintext.

### Neutral

- The encryption layer is independent of the matching algorithm. When we
  replace ORB with a real biometric SDK, the storage format stays the
  same (encrypt whatever the SDK outputs as its template).

## Alternatives considered

### A. Database-level encryption (TDE / pgcrypto)

Postgres Transparent Data Encryption or `pgcrypto` column-level encryption.
Rejected because:
- TDE protects at-rest disk only; a DB connection leak still sees
  plaintext.
- `pgcrypto` moves the key management to the DB, which we don't want
  (key should be in the application layer, not the data layer).
- Neither works for SQLite dev path.

### B. Vault / AWS KMS envelope encryption

Each descriptor encrypted with a per-row DEK; DEK encrypted with the
master key in Vault/KMS. Rotation re-encrypts only DEKs.

This is the **target state** (see `docs/KEY_MANAGEMENT.md`). Rejected for
v1 because it requires a Vault/KMS account and adds latency per
decrypt (network call). Planned for sprint 3+.

### C. Store only a non-reversible hash of the descriptor

If we could use a locality-sensitive hash (e.g., SimHash), we wouldn't
need to decrypt at match time. Rejected because ORB matching needs the
full descriptor for `BFMatcher.knnMatch`; a hash loses the information
needed for the ratio test. A future biometric SDK may support
template-level hashing (e.g., ISO 19795 BioAPI), which would revisit
this option.

### D. Don't encrypt — rely on DB access controls

Rejected outright. A single SQL injection, backup leak, or admin-account
compromise exposes every enrolled user's biometric data permanently.
Encryption at the application layer is a non-negotiable second line of
defense.

## References

- `app/services/crypto.py` — implementation
- `docs/KEY_MANAGEMENT.md` — rotation plans, compromise procedures
- `docs/BIOMETRIC_DATA_POLICY.md` — regulatory obligations
- `docs/SECURITY.md` — biometric data handling section
- `docs/ISSUES.md` — key rotation gap
