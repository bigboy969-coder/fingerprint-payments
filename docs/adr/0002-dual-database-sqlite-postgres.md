# ADR-0002: Dual-database layer (SQLite dev / PostgreSQL prod)

## Status

Accepted — will be superseded once Alembic migration tooling lands.

## Date

2026-04-16 (backfilled from existing code)

## Context

We need a database for users, fingerprints, transactions, and merchants.
Development should be zero-friction (no Docker, no external DB process).
Production needs durability, concurrent access, and backups.

The `app/db/` package currently implements both backends,
toggled by the presence of the `DATABASE_URL` env var. SQL strings use a
`PH` variable (`%s` for Postgres, `?` for SQLite) and raw `psycopg2` /
`sqlite3` calls. Schema is created idempotently on startup via
`CREATE TABLE IF NOT EXISTS`. SQLite gets best-effort `ALTER TABLE`
migrations inside `try/except`.

## Decision

Keep the dual-database approach for the pilot phase. Accept the following
trade-offs:

- One module, two code paths. Every query must be placeholder-aware.
- No ORM. SQL is hand-written. Fast to prototype, slow to evolve.
- No migration tool. Schema changes must be manually applied to production
  Postgres.
- No connection pool. Fresh connection per request.

## Consequences

### Positive

- Local dev starts with `uvicorn app.main:app --reload` and nothing else.
- No ORM lock-in while the schema is still churning.
- Raw SQL keeps the codebase small and debuggable.

### Negative

- Dual code paths are a constant source of bugs (see ISSUES #2 where
  `connect_return` imports `DB_PATH` which only exists in the SQLite
  branch).
- No migration tool means production schema drift is silent and invisible.
- No connection pool bottlenecks under concurrent load.
- Date-handling differences between SQLite (`strftime`) and Postgres
  (`LEFT()`) are already baked into queries.

### Neutral

- Adding Alembic later is straightforward — it can adopt the existing
  Postgres schema as its baseline migration.

## Alternatives considered

### A. SQLAlchemy ORM + Alembic from day one

Full ORM, declarative models, auto-generated migrations. Rejected for pilot
because the schema was still changing daily and the overhead of writing
models + migrations felt premature for a 7-table schema.

### B. Postgres everywhere (docker-compose for dev)

Eliminates dual paths. Rejected because it adds a Docker dependency to local
dev, which was a friction point for a solo founder iterating quickly.

### C. Supabase / managed Postgres with local tunnel

Similar to B but with a cloud DB. Rejected for cost and latency during rapid
local iteration.

## References

- `app/db/` — the dual-path implementation
- `docs/DATABASE.md` — schema and query documentation
- `docs/ISSUES.md` #29 — schema drift risk
- `docs/ROADMAP.md` sprint 2 item 13 — planned Alembic adoption
