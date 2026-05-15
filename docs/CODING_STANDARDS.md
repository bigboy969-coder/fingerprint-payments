# Coding Standards

These are enforceable rules. Style debates belong in PR comments only when
the rule itself is unclear.

## Python

### Versions

- **Runtime:** Python 3.11 (matches Dockerfile).
- **Local dev:** 3.11 strongly preferred. 3.12 acceptable. Other versions
  may fail on OpenCV.

### Tools (configured in `pyproject.toml`)

| Tool | Purpose | CI gate |
|---|---|---|
| `ruff` | Lint + import sort | Yes |
| `black` | Format | Yes |
| `mypy` | Type check | Soft (warn) until baseline passes; then hard |
| `pytest` | Tests | Yes (once `tests/` exists) |
| `pip-audit` | Dependency CVEs | Yes (advisory) |
| `gitleaks` | Secret scan | Yes |
| `pre-commit` | Local enforcement before commit | Local |

### Style

- Line length: **100**. Black is the source of truth.
- Imports: group `stdlib`, third-party, local. Ruff `isort` enforces.
- No wildcard imports.
- No mutable default args.
- No bare `except:` — use `except Exception:` at most, and only at trust
  boundaries (HTTP handler, background task entry).

### Type hints

- Required on every public function (anything not prefixed `_`).
- Required on dataclass / Pydantic field.
- Encouraged on private functions.
- Use `from __future__ import annotations` in new modules.

### Docstrings

- One-line summary unless a non-obvious WHY exists.
- For HTTP handlers, the docstring should describe the user-facing behavior
  in plain language (what the response means, when 4xx vs 5xx applies).
- No "Args/Returns/Raises" rituals on simple functions.

### Error handling

- Validate at the boundary (HTTP handler, WebSocket entry, queue consumer).
  Internal functions trust their callers.
- Convert domain errors to HTTP errors at the route layer, not in the
  pipeline layer. Pipeline raises `ValueError` / custom domain exceptions;
  route maps them.
- Never swallow exceptions silently. If a `try/except: pass` is the right
  call, write the comment that explains why.

### Async

- All HTTP handlers are `async def`.
- Blocking I/O inside an async handler must run via
  `asyncio.to_thread(...)` or `loop.run_in_executor(...)`. Today, OpenCV
  ORB extraction and bcrypt hashing run on the event loop — this is a
  known violation that needs fixing in a dedicated PR (see ROADMAP.md).
- No new uses of `requests`. Use `httpx.AsyncClient`.

### Logging

- Use `logger = logging.getLogger("fingerpay.<module>")`.
- **Never** log:
  - PII (email, phone, full name)
  - JWTs, API keys, password hashes
  - Stripe customer/payment-method IDs
  - Fingerprint descriptors
- Acceptable: HTTP method, path, status, request_id, merchant_id (numeric),
  user_id (numeric), Stripe PaymentIntent IDs (these are not PII per Stripe
  docs but redact in screenshots).
- For structured fields, use `logger.info("event-name", extra={...})` once
  structlog is in place.

### SQL

- Until Alembic is adopted, schema changes go through `app/db/schema.py`
  + a documented `ALTER` script in the PR description.
- Always use the `PH` placeholder for compatibility with both SQLite and
  Postgres.
- f-strings around table/column names are acceptable; **never** f-string
  user input. Always parameterize values.
- For new modules, do not import `_get_conn`, `_fetchone`, `_fetchall`, or
  `PH` from outside `app/db/`. Add a public function instead.

### File layout

```
app/routes/<resource>.py   HTTP / WebSocket handlers, FastAPI router
app/db/<concern>.py        Database (schema, connection, queries)
app/services/<concern>.py  Biometrics, crypto, JWT, third-party API wrappers
static/<page>.html         Self-contained pages (no build step)
tests/<resource>/...       Mirror app/routes/ structure
```

A new top-level package needs an ADR.

### Naming

- Modules: `snake_case`.
- Classes: `PascalCase`.
- Functions / variables: `snake_case`.
- Constants: `SCREAMING_SNAKE`.
- HTTP handler functions: name them after the verb-noun, not the route
  (`signup`, not `merchants_signup`).

### Comments

Default to writing none. Only add when the WHY isn't obvious from the code.
Do not add comments that summarize the next 3 lines, or that say "TODO"
without an issue link.

## Frontend (vanilla JS)

- One file per page. No build step. No framework.
- New code: never `innerHTML` user-controlled data. Use `textContent` or an
  HTML escape helper.
- No inline `onclick=` in new code; prefer `addEventListener`.
- No CDN scripts without SRI hashes (Stripe.js is the documented
  exception).
- Always `await` fetch + handle non-2xx explicitly.
- Don't store anything sensitive in `localStorage` beyond what's already
  there (the merchant JWT). When that JWT moves to a HttpOnly cookie, the
  `localStorage` reference goes too.

## Documentation

- Every new public endpoint goes in `docs/API.md` in the same PR.
- Every schema change goes in `docs/DATABASE.md` in the same PR.
- Every architecture decision worth remembering gets an ADR in
  `docs/adr/`.

## Configuration

- All config from env vars. No hardcoded URLs (use `APP_BASE_URL`).
- New env vars: documented in `.env.example`, `docs/OPERATIONS.md`, and
  validated at boot in `app/main.py` (once the `validate_env()` helper lands).

## Dependencies

- Adding a runtime dependency requires:
  1. An entry in `pyproject.toml`.
  2. A note in `docs/TECH_RADAR.md` (or an ADR).
  3. CTO/CODEOWNERS approval.
- Pin major versions at minimum. Prefer compatible-release (`~=`).
- Audit new deps for license (no GPL/AGPL in runtime), maintenance status,
  and CVE history.
