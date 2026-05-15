# Server-Side Matching Refactor

Branch: `server-side-matching`

## What changed and why

Previously, the POS terminal downloaded all enrolled fingerprint templates from the server,
performed matching locally using `dpHMatch.dll`, then told the server which user matched.
This had two critical flaws:

1. **Biometric data left the server** — encrypted templates were transmitted to the terminal
   and decrypted there, exposing raw feature data outside the trust boundary.
2. **The server trusted the terminal's claim** — `POST /pos/identify` accepted a `user_id`
   from the terminal with no server-side verification. Any caller with a valid API key could
   impersonate any enrolled user.

The refactor moves matching authority to the server. The terminal now only captures and
extracts features; it never sees another user's biometric data.

---

## Architecture before

```
Terminal (Windows)
  GET /pos/templates          ← server sends ALL stored templates to terminal
  capture_verification_features()   [DP SDK]
  verify(ver_features, template)    [dpHMatch.dll — local match]
  POST /pos/identify {user_id: X}   ← server trusts this unconditionally
  POST /pay
```

## Architecture after

```
Terminal (Windows)
  capture_verification_features()   [DP SDK — local capture + extraction only]
  POST /authenticate {features: base64}   ← 318-byte blob, no templates leave server

Server (Linux/Render)
  find_user_by_fingerprint(features)
    decrypt each stored blob individually
    match_features(ver_features, enrollment_blobs)   [OpenCV BFMatcher]
  → returns JWT directly on match
```

---

## Files changed

### New file
- `alembic/versions/c3e7f2a9b1d4_replace_fingerprint_descriptor_with_per_blob_storage.py`

### Modified files

| File | Summary |
|---|---|
| `app/db/schema.py` | `fingerprints` table: dropped `descriptor`, added `descriptor_0..3` (both Postgres + SQLite) |
| `app/services/biometrics.py` | Added `match_features()` — OpenCV BFMatcher, no DLL dependency, runs on Linux |
| `app/db/users.py` | `enroll_user` accepts `feature_blobs: list[bytes]`; `find_user_by_fingerprint` uses `match_features()` instead of `verify()` |
| `app/routes/enroll.py` | `POST /enroll/complete` accepts `{feature_blobs: [base64, ...]}` (4 items); `POST /enroll/verify` accepts `{features: base64}` in body |
| `app/routes/authenticate.py` | Accepts `{features: base64}` in request body; removed `capture_verification_features()` call |
| `pos_enroll.py` | Sends 4 raw pre-reg feature blobs; `build_template()` removed |
| `pos_authenticate.py` | Sends verification blob to `/authenticate`, receives JWT directly; template download and local matching removed |

---

## Database migration

**Revision:** `c3e7f2a9b1d4`  
**Revises:** `4305639accaa`

The migration deletes all existing `fingerprints` rows (old 1632-byte DP enrollment templates
cannot be decomposed into 4 × 318-byte pre-reg feature blobs), drops the `descriptor` column,
and adds `descriptor_0`, `descriptor_1`, `descriptor_2`, `descriptor_3` as `NOT NULL` binary
columns. Any users enrolled before this migration must re-enroll.

To apply:
```bash
alembic upgrade head
```

To roll back (data is not recoverable — `descriptor` is restored as nullable):
```bash
alembic downgrade 4305639accaa
```

---

## Enrollment storage format

During enrollment the terminal captures 4 scans. Each scan produces a 318-byte
pre-registration feature blob via `dpHFtrEx.dll FX_extractFeatures`. These 4 blobs are
sent to `POST /enroll/complete/{session_id}` as a JSON array of base64 strings.

The server encrypts each blob individually with AES-256-GCM before storing:

```
feature_blob  →  encrypt_descriptor()  →  descriptor_0..3 columns (BYTEA/BLOB)
```

Each column stores: `12-byte nonce || ciphertext` (output of AES-256-GCM).

---

## Server-side matching

`app/services/biometrics.match_features(verification_features, enrollment_blobs)`

- **Input:** 318-byte verification feature blob (from terminal) + list of 4 × 318-byte
  enrollment blobs (decrypted from DB).
- **Method:** OpenCV `BFMatcher(NORM_HAMMING)`. Query shape `(1, 318)` matched against
  train shape `(4, 318)`. Returns the single nearest match.
- **Decision:** `match.distance < _HAMMING_THRESHOLD` (default: `80`).
- **Platform:** Linux-safe — no `dpHMatch.dll` dependency.

### Threshold tuning

`_HAMMING_THRESHOLD = 80` is a conservative starting value. It should be calibrated
empirically against real DP feature vectors by measuring FAR (False Accept Rate) and
FRR (False Reject Rate) across a sample population. Adjust in
`app/services/biometrics.py`.

---

## What is now obsolete

- `GET /pos/templates` endpoint (`app/routes/pos_auth.py`) — the terminal no longer
  downloads templates. This endpoint can be removed in a follow-up PR.
- `POST /pos/identify` endpoint — replaced by the JWT return from `POST /authenticate`.
- `build_template()` in `app/services/biometrics.py` — no longer called by any server
  or terminal code. Still present for reference; can be removed once confirmed unused.
- `verify()` in `app/services/biometrics.py` — Windows-only `dpHMatch.dll` wrapper.
  Replaced by `match_features()` for all server-side matching.
