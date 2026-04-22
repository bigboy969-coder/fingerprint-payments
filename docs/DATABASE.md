# Database

`app/db/` is the database package, with two parallel implementations
selected at import time by the presence of `DATABASE_URL`:
- **PostgreSQL** (psycopg2, `%s` placeholders)
- **SQLite** (file in repo root by default, `?` placeholders)

The placeholder is exposed as `PH` and used in every f-string SQL — keep this
in mind when adding queries.

## Connection lifecycle

`_get_conn()` is a context manager that:
- Opens a fresh connection per call (no pool).
- `commit()` on normal exit, `rollback()` on exception, always `close()`.

There is **no connection pool**. Each request opens a new connection. At any
non-trivial concurrency this becomes a bottleneck (Postgres TCP handshake +
auth on every query). Use `psycopg2.pool.SimpleConnectionPool` or migrate to
`asyncpg` + SQLAlchemy.

## Schema

All timestamps are stored as ISO 8601 **TEXT**. Mixed time zones — see
"Time-zone inconsistencies" below.

### `users`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL / AUTOINCREMENT | PK |
| full_name | TEXT NOT NULL | |
| email | TEXT NOT NULL UNIQUE | |
| phone | TEXT | optional |
| stripe_customer_id | TEXT | populated at enroll |
| stripe_payment_method_id | TEXT | populated at enroll |
| enrolled_at | TEXT NOT NULL | `datetime.now().isoformat()` (local time) |

### `fingerprints`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL | PK |
| user_id | INTEGER NOT NULL | **No FK constraint** |
| descriptor | BYTEA / BLOB NOT NULL | AES-256-GCM(nonce \|\| ciphertext) of ORB descriptor bytes |
| enrolled_at | TEXT NOT NULL | local time |

A user can have multiple fingerprint rows in principle (no UNIQUE). In
practice only one is inserted per enrollment.

### `transactions`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL | PK |
| user_id | INTEGER NOT NULL | **No FK** |
| amount | REAL NOT NULL | USD, two decimals expected |
| merchant | TEXT NOT NULL | **client-supplied string**, not validated |
| stripe_payment_intent_id | TEXT | added via migration |
| stripe_status | TEXT | `succeeded`, etc. |
| merchant_id | INTEGER | nullable, set when JWT carries it |
| platform_fee | REAL DEFAULT 0 | |
| balance_after | REAL DEFAULT 0 | unused — always 0 |
| created_at | TEXT NOT NULL | local time |

### `merchants`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL | PK |
| business_name | TEXT NOT NULL | |
| name | TEXT NOT NULL | the contact's personal name |
| email | TEXT NOT NULL UNIQUE | |
| password_hash | TEXT NOT NULL | bcrypt |
| api_key_hash | TEXT | sha256 hex |
| stripe_connect_id | TEXT | acct_... |
| stripe_connect_status | TEXT DEFAULT 'pending' | `pending` or `active` |
| last_monthly_fee_month | TEXT | `YYYY-MM` of the last month the $29 was billed |
| is_active | INTEGER DEFAULT 1 | **never read anywhere** |
| created_at | TEXT NOT NULL | local time |

### `enrollment_sessions`
| Column | Type | Notes |
|---|---|---|
| session_id | TEXT PRIMARY KEY | uuid4 |
| full_name, email, phone | TEXT | populated by phone form |
| stripe_customer_id, stripe_payment_method_id | TEXT | populated after Stripe success |
| user_id | INTEGER | populated after `complete_session` |
| status | TEXT NOT NULL DEFAULT 'pending_form' | `pending_form` → `pending_scan` → `complete` |
| created_at | TEXT NOT NULL | local time |

No expiry. No cleanup job. Sessions accumulate forever.

### `password_reset_tokens`
| Column | Type | Notes |
|---|---|---|
| token | TEXT PRIMARY KEY | url-safe random |
| merchant_id | INTEGER NOT NULL | no FK |
| expires_at | TEXT NOT NULL | UTC iso |
| used | INTEGER DEFAULT 0 | |

`create_reset_token` flips all previous unused tokens for the merchant to
`used=1` before inserting the new one.

### `customer_verification_codes`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL | PK |
| email | TEXT NOT NULL | |
| code | TEXT NOT NULL | 6-digit numeric string |
| expires_at | TEXT NOT NULL | UTC iso |
| used | INTEGER DEFAULT 0 | |

Old codes for the same email are flipped to `used=1` on each new request.

## Indexes

Only the implicit PK + UNIQUE-email indexes exist. **Missing indexes** that
will hurt at scale:

- `transactions(merchant_id, created_at)` — drives dashboard queries.
- `transactions(user_id)` — drives `delete_customer_by_email`.
- `merchants(api_key_hash)` — every `/authenticate` call.
- `customer_verification_codes(email, code, used)` — every verify call.
- `password_reset_tokens(used, expires_at)` — for cleanup jobs.

## Migrations

There is no migration tool. The SQLite branch hand-rolls best-effort
`ALTER TABLE ADD COLUMN` calls inside `try/except: pass`. The Postgres branch
**has no equivalent** — it relies on `CREATE TABLE IF NOT EXISTS` matching
the latest schema. **A live Postgres database that pre-dates the current
schema will silently keep its old columns.** New columns added to existing
tables in code will not be added in production.

### Recommendation
Adopt Alembic (or pgmate, yoyo-migrations) and version the schema. The
hand-rolled idempotent CREATE pattern is acceptable for v0 but is a foot-gun
the moment a column needs to be added.

## Time-zone inconsistencies

| Table | Column | Source |
|---|---|---|
| users | enrolled_at | `datetime.now()` — **local server time** |
| transactions | created_at | `datetime.now()` — local |
| merchants | created_at | `datetime.now()` — local |
| enrollment_sessions | created_at | `datetime.now()` — local |
| password_reset_tokens | expires_at | `datetime.utcnow()` — UTC |
| customer_verification_codes | expires_at | `datetime.utcnow()` — UTC |

Comparisons in `verify_customer_code` and `consume_reset_token` use
`datetime.utcnow().isoformat()`. Since the source values were also UTC, this
is internally consistent — but the user-visible `enrolled_at` and `created_at`
are local time on the host (which on Render/Heroku is usually UTC, so it
"works", but is implicit and dangerous).

**Fix:** Use `datetime.now(timezone.utc)` everywhere, or migrate columns to
`TIMESTAMPTZ` in Postgres.

## Query patterns of note

### `find_user_by_fingerprint` — full table scan + decrypt
```python
SELECT user_id, descriptor FROM fingerprints   # all rows
# Python loop: AES-GCM decrypt each, ORB match against probe
```
At 10k enrolled users this is roughly 10k AES-GCM + 10k ORB matches per
authentication. CPU- and memory-bound. There is no biometric
pre-filter (no clustering, no Bloom filter, no template hashing).

### `get_merchant_stats` uses dialect-specific date slicing
```python
# Postgres
LEFT(created_at, 7) = '2026-04'
# SQLite
strftime('%Y-%m', created_at) = '2026-04'
```
Works because `created_at` is text-ISO. Will break if the column type ever
changes.

### `delete_customer_by_email` cascades manually
Three separate DELETEs in a single transaction. Stripe customer is deleted
**outside** the transaction (in `app/routes/customers.py`) — if Stripe fails the
local rows still go away, but the Stripe customer record is orphaned.
