# Testing Strategy

There are zero tests in the repo today. This document is the plan to fix
that and the standard for tests added going forward.

## Pyramid

```
              ┌─────────────┐
              │   E2E (5%)  │   playwright against a staged deploy
              ├─────────────┤
              │ Integration │   FastAPI TestClient + dockerized Postgres
              │   (25%)     │   + Stripe test mode (or stripe-mock)
              ├─────────────┤
              │    Unit     │   pure functions, db, services
              │   (70%)     │
              └─────────────┘
```

Inverted pyramids (mostly E2E) are fragile. We aim for many fast unit tests,
a focused band of integration tests covering each user flow end-to-end
inside the process, and a small E2E suite that asserts the deploy is
healthy.

## Layout

```
tests/
├── conftest.py                 shared fixtures (db, client, stripe stub)
├── unit/
│   ├── db/
│   │   ├── test_connection.py
│   │   ├── test_schema.py
│   │   └── test_queries.py
│   ├── services/
│   │   ├── test_biometrics.py
│   │   ├── test_crypto.py
│   │   ├── test_jwt.py
│   │   └── test_stripe.py
│   └── routes/                 thin handlers — most logic is in services
├── integration/
│   ├── test_enroll_flow.py     POST session → form → scan → verify
│   ├── test_auth_and_pay.py    image → /authenticate → /pay
│   ├── test_pos_websocket.py   ws handshake, payment_request, complete
│   ├── test_merchant_lifecycle.py  signup → login → connect → regen
│   └── test_customer_portal.py     request → verify → delete
└── e2e/
    └── test_smoke.py           hit prod health, public pages, /config
```

## Fixtures

`conftest.py` provides:

- `db()` — fresh SQLite-backed DB per test (transactional rollback if we
  add Postgres-backed tests).
- `client()` — FastAPI `TestClient` bound to that DB.
- `merchant()` — pre-created merchant with API key in plaintext.
- `enrolled_user()` — pre-enrolled user with descriptor + Stripe IDs.
- `stripe_stub()` — replaces `app/services/stripe` calls with a recorder.

## What to test

### Must

- Every route's happy path.
- Every route's auth-failure path (missing token, wrong type, expired).
- Every route's input-validation error path (bad body, missing field,
  size limit).
- Every route's rate-limit path once limits are universal.
- `enroll_user` rejects duplicate email.
- `find_user_by_fingerprint` returns no match for an unknown probe and the
  correct match for an enrolled user.
- `encrypt_descriptor` / `decrypt_descriptor` round-trip.
- JWT expiry behavior (expired tokens reject).
- Stripe wrapper passes the right args (mocked).
- Webhook signature verification (once webhooks land).
- Schema migrations apply forward and roll back.

### Should

- Concurrent `/enroll/start` for the same email — last writer should not
  overwrite, second caller should get a clear error.
- Stripe failure during `/pay` does not leave a `succeeded` row.
- Stripe success but DB write failure surfaces a recoverable state (once
  the pre-charge row pattern lands).

### Nice

- Property-based tests on `calculate_platform_fee` (hypothesis).
- Fuzz the image upload endpoint with garbage bytes.

## What NOT to test

- Pydantic's own validation. Trust the framework.
- That Stripe charges a card. That's Stripe's job; we test we called Stripe
  with the right args.
- That bcrypt hashes correctly. Same.
- HTML rendering. Test the JSON contract; let Playwright cover the HTML.

## Mocking policy

- Unit tests: mock anything that crosses a process boundary (Stripe HTTP,
  Resend HTTP, OpenCV file read where appropriate).
- Integration tests: use real SQLite (or test Postgres), real
  `extract_descriptor` against `test_fingerprint.png`, mocked Stripe via
  the `stripe_stub` fixture or `stripe-mock`.
- E2E: real services in test mode. No mocks.

Per-team rule: **never mock the database in integration tests**. We've
been bitten by this before in other projects — mocks pass, prod migrations
fail.

## Coverage

- Aim for 80% line + branch coverage on `app/db/` and `app/services/`.
- 70% on `app/routes/`.
- Coverage is a smell detector, not a quality bar. A 100%-covered codebase
  with no edge-case tests is still bad.

## CI integration

`pytest --cov=. --cov-report=term-missing --cov-fail-under=70` once the
suite exists. Until then, the `test` job in `.github/workflows/ci.yml`
no-ops with a friendly message.

## Performance

- Each unit test < 50ms.
- Each integration test < 500ms.
- Full suite < 60 s.

If a test is slow, mark it `@pytest.mark.slow` and exclude from the
default run.

## Test data

- Use the `Faker` library only for fuzz-style tests. Hand-write fixtures
  for everything else; reading "user_id=42, email=jane@example.com" in a
  failing test is much easier than chasing a random value.
- `test_fingerprint.png` is the canonical happy-path image. Add a small
  set of additional images for edge cases (low quality, very small, very
  large) under `tests/fixtures/images/`.
- Stripe test card numbers from
  https://docs.stripe.com/testing — keep a list in `tests/fixtures/cards.py`.

## Frontend testing

Manual until we add Playwright. Manual smoke before any deploy:

- Marketing landing page renders.
- Merchant signup → API key shown → dashboard loads.
- Kiosk QR generates → scan link opens enrollment form.
- Customer portal: request code → enter code → see info → delete.

## Adding a test

1. Find the right file under `tests/`.
2. Use existing fixtures from `conftest.py`.
3. Name the test `test_<what>_<when>_<then>` —
   `test_pay_returns_402_when_stripe_rejects`.
4. One assertion concept per test (multiple `assert` lines per concept is
   fine).
5. If your test needs a new fixture, put it in the nearest `conftest.py`,
   not inline.
