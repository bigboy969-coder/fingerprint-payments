# Roadmap

Prioritized work, in the order I'd actually do it. Each item references the
ISSUES.md entry that motivates it.

## Sprint 1 — Stop the bleeding (1 week)

Ship-blockers that any production traffic will hit immediately.

1. **Fail boot if critical env vars are unset** (#1, #3, #8)
   - Add `validate_env()` called from `lifespan`. Raise on missing
     `FINGERPAY_SECRET`, `BIOMETRIC_ENCRYPTION_KEY`, `STRIPE_SECRET_KEY`.
   - Remove the `"dev-secret-change-in-prod"` fallback.

2. **Fix the monthly-fee math** (#4)
   - Stop bundling the monthly fee into `application_fee_amount`. Either:
     a) Bill it via a Stripe Invoice on the Connect account on the 1st of
        each month (cron); or
     b) Cap `application_fee_amount` at `amount - 1` and accumulate the
        deferred portion until next charge.
   - Until this ships, **the first small transaction of every month will
     fail** for every merchant.

3. **Fix Connect status sync** (#2, #16)
   - Stop using `DB_PATH`/raw `sqlite3` in `connect_return`. Call
     `update_merchant_connect()`.
   - Add `/webhooks/stripe` with signature verification. Handle
     `account.updated` to set status authoritatively.
   - Re-fetch status from Stripe on every dashboard load until webhook is
     deployed.

4. **Patch the dashboard XSS** (#7)
   - Replace `innerHTML` interpolation in `merchant-dashboard.html` with
     either `textContent` writes or an HTML-escape helper.
   - Add a strict CSP header.

5. **Add `--proxy-headers` to the uvicorn command** (#37)
   - Trivial but blocks rate limiting from working in production.

6. **Apply rate limiting to login + verify-code + forgot-password** (#11, #12)
   - One-line decorators per route.

## Sprint 2 — Pilot-readiness (2 weeks)

7. **Move POS state out of memory** (#5)
   - Redis pub/sub for `terminals` (presence) and `transactions` (status).
   - Or, document and enforce single-worker single-instance.

8. **Pre-charge transaction record** (#6)
   - Insert `transactions` row with `status=pending` before calling Stripe.
     Update status after. On record failure mid-flow, log + alert.

9. **Stripe webhooks** (full pass) (#16, #20)
   - `account.updated`, `payment_intent.payment_failed`,
     `payment_intent.requires_action`, `charge.dispute.created`,
     `charge.refunded`.
   - Surface dispute and refund into the dashboard.

10. **JWT type check on `/pay`** (#17)

11. **Move email send to FastAPI BackgroundTasks** (#18)
    - Eliminates the daemon-thread footgun while you decide on a real queue.

12. **Verify Resend domain + custom from-address** (#15)

13. **Schema migrations: adopt Alembic** (#29)
    - Generate the initial migration from the current Postgres schema.
    - Add a Render pre-deploy command to run `alembic upgrade head`.

14. **Add `/healthz` and `/readyz`** (#36)

15. **Pin dependencies** (#26)
    - Use `uv pip compile` to lock from `requirements.in`.

16. **Drop `merchant` field from `/pay` request; derive server-side** (#19)

## Sprint 3 — Hardening (2-3 weeks)

17. **Biometric matcher rebuild** (#9, #10)
    - Decision point: 1-to-1 (customer enters phone or scans NFC, then
      fingerprint matches against ONE template) vs. 1-to-N with a real
      biometric SDK + bucketing.
    - Add liveness or anti-spoofing if 1-to-N is the path.
    - This is a multi-month effort that may demand a third-party SDK or
      partnership — start the procurement conversation now.

18. **Stored-XSS sweep across all rendered fields** (#7)
    - Audit every `innerHTML` in `static/`. Add a `safe()` helper.

19. **Add CSP, X-Frame-Options, HSTS via middleware**

20. **Move API key out of WebSocket query string** (#13)
    - Auth via first message after connect.

21. **Connection pool for Postgres** (#27)

22. **Index migrations** (#28)

23. **Pagination for customers + transactions** (#30)

24. **Cleanup jobs for `enrollment_sessions`, `temp_uploads/`,
    `password_reset_tokens`, `customer_verification_codes`** (#31, #32)

25. **Time zone normalization** (#33)
    - Migrate timestamp columns to TIMESTAMPTZ; standardize on UTC in code.

26. **Sentry + structured logging**

27. **First test suite**
    - Unit tests for `app/db/`, `app/services/crypto.py`, `app/services/jwt.py`.
    - Integration test against `/enroll/*` and `/pay` with Stripe test mode
      and a stubbed fingerprint matcher.

## Sprint 4+ — Scale prep

28. **Replace ORB / consider hardware fingerprint readers**

29. **Move to async DB driver (asyncpg + SQLAlchemy 2.0)**

30. **Multi-worker / multi-instance** (after #7)

31. **CDN + cache for static pages**

32. **PCI scope review with Stripe — confirm SAQ-A applies**
    - Card data passes from browser to Stripe Elements directly. We never
      touch PAN. Verify the assumption holds end-to-end.

33. **SOC2 / GDPR groundwork**
    - Data retention, customer deletion (already shipped — verify Stripe
      cascade), audit logging, key rotation procedure for
      `BIOMETRIC_ENCRYPTION_KEY`.

## Things to actively NOT build

- A "second factor" on the JWT — keep TTL short and the single-factor
  fingerprint posture; adding more friction defeats the product.
- A custom biometric matcher in-house. Buy or partner.
- A multi-tenant payment ledger. Stripe is the ledger.
