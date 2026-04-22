# ADR-0005: Single-process deployment as a pilot constraint

## Status

Accepted — will be superseded when POS state moves to Redis.

## Date

2026-04-16 (backfilled from existing code)

## Context

The POS integration (`app/routes/pos.py`) uses a persistent WebSocket between
the merchant's kiosk tablet and the FingerPay server. The connection map
(`TerminalManager.terminals`) and the in-flight transaction status map
(`TerminalManager.transactions`) are Python dicts living in process memory.

This means:

- Only one uvicorn worker can hold the WebSocket for a given merchant.
- A second worker receiving a `/pos/charge` request will report "Terminal
  is not connected" even though it is.
- A process restart (deploy, OOM kill, scale event) drops all connections
  and loses all pending transaction state.

## Decision

For the pilot phase (single-store, single-kiosk deployments), we
**accept the single-process constraint** and run uvicorn with one worker.

This is explicitly a temporary trade-off. We document it as a known
limitation and defer the Redis migration to sprint 2 (ROADMAP #7).

Concrete rules while this ADR is in effect:

- `Procfile`, `Dockerfile`, and any deploy config must **not** set
  `--workers > 1`.
- The POS flow documentation must note that in-flight transactions are
  lost on restart.
- Any PR that introduces shared state across requests must add it to the
  `TerminalManager` or a new in-memory structure with an explicit comment
  referencing this ADR.
- Horizontal scaling (multiple instances behind a load balancer) is
  **not supported**. If the host auto-scales, configure a max of 1
  instance.

## Consequences

### Positive

- Zero additional infrastructure. No Redis, no pub/sub, no external
  message broker.
- Simpler to debug: one process, one event loop, one set of dicts.
- Adequate for a pilot with 1–5 merchants, each with 1 terminal.

### Negative

- **No horizontal scaling.** Throughput ceiling is one Python process.
  Blocking calls (OpenCV, bcrypt) on the asyncio thread compound this.
- **Restart = data loss** for in-flight POS transactions. Customer may
  see "Payment successful" on the kiosk while the POS times out.
- **No failover.** If the process dies, everything is down until Render
  restarts it (typically 30–60 s).
- Marketing and investor demos must not promise multi-store or high-
  availability capabilities.

### Neutral

- The migration path to Redis is well-understood: replace the dicts with
  Redis hashes, replace WebSocket direct-send with Redis pub/sub (each
  worker subscribes to a channel per merchant_id), and add reconnection
  logic on the kiosk side.

## Alternatives considered

### A. Redis from day one

Use Redis for connection presence and transaction state. Each worker
subscribes to a pub/sub channel; `/pos/charge` publishes to the channel
and the worker holding the WebSocket relays.

This is the **right long-term answer**. Rejected for v1 because it
requires provisioning and paying for a Redis instance (Upstash, Render
Redis, or self-hosted), plus additional code complexity, before we have a
single paying merchant.

### B. Sticky sessions at the load-balancer level

Route all requests for a given `api_key` to the same worker. Rejected
because:
- Render's load balancer doesn't support arbitrary sticky-session keys
  (only cookie-based).
- WebSocket upgrade and REST calls would need to land on the same
  instance, which is fragile.
- Doesn't solve the restart problem.

### C. Database-backed transaction status

Write POS transaction status to Postgres instead of the in-memory dict.
Solves durability but not the WebSocket routing problem (still need to
know which worker holds the socket). Also adds DB write latency to every
status poll.

## References

- `app/routes/pos.py` — `TerminalManager`
- `docs/ISSUES.md` #5 — in-memory state breaks on restart / multi-worker
- `docs/ROADMAP.md` sprint 2 item 7 — planned Redis migration
- `docs/OPERATIONS.md` — scaling caveats table
