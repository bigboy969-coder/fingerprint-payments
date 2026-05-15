# Data Flows

Sequence walkthroughs of the five user-visible flows. Step numbers refer to
the actual code paths.

---

## 1. Enrollment (two-device QR flow)

Goal: bind a fingerprint to a Stripe customer + payment method.

```
Kiosk (tablet)              FingerPay              Customer's phone           Stripe
      │                          │                         │                       │
      │ POST /enroll/session     │                         │                       │
      ├─────────────────────────►│ create row, status=     │                       │
      │                          │ pending_form            │                       │
      │ ◄────────────────────────┤ {session_id, enroll_url}│                       │
      │                          │                         │                       │
      │ render QR with enroll_url│                         │                       │
      │                          │                         │                       │
      │                          │            scan QR ◄────┤                       │
      │                          │ GET /static/enroll.html?session=...             │
      │                          │ ◄───────────────────────┤                       │
      │                          │                         │                       │
      │                          │ POST /config            │                       │
      │                          │ ◄───────────────────────┤                       │
      │                          │ ─{publishable_key}─────►│                       │
      │                          │                         │ stripe.create         │
      │                          │                         │ PaymentMethod         │
      │                          │                         ├──────────────────────►│
      │                          │                         │ ◄─{payment_method_id}─┤
      │                          │ POST /enroll/start      │                       │
      │                          │ ◄───────────────────────┤                       │
      │                          │ check email exists      │                       │
      │                          │ Stripe Customer.create  │                       │
      │                          │ + SetupIntent confirm   │                       │
      │                          ├────────────────────────────────────────────────►│
      │                          │ ◄─{customer_id}────────────────────────────────┤
      │                          │ status=pending_scan     │                       │
      │                          │ ─{success}─────────────►│                       │
      │                          │                         │                       │
      │ poll GET /enroll/status/{id} every 2s              │                       │
      ├─────────────────────────►│                         │                       │
      │ ◄────{pending_scan}──────┤                         │                       │
      │                          │                         │                       │
      │ show "scan finger" view  │                         │                       │
      │ POST /enroll/complete/{id} (multipart fingerprint) │                       │
      ├─────────────────────────►│ extract ORB descriptor  │                       │
      │                          │ AES-256-GCM encrypt     │                       │
      │                          │ INSERT users + finger   │                       │
      │                          │ status=complete         │                       │
      │ ◄────{success, user}─────┤                         │                       │
      │                          │                         │                       │
      │ POST /enroll/verify/{id} (second scan)             │                       │
      ├─────────────────────────►│ match against just-     │                       │
      │                          │ enrolled user only      │                       │
      │ ◄────{success, name}─────┤                         │                       │
```

### Notes
- The session table holds the form data temporarily, decoupling phone and
  kiosk in time.
- The kiosk polls every 2 s — no WebSocket, no SSE.
- A second confirmation scan (`/enroll/verify`) hardens against bad first
  enrollments.
- Email uniqueness is enforced at INSERT time; a race between two phones
  using the same email under different sessions could 500 instead of 400.

### Failure paths
- Stripe failure during `/enroll/start` → 402, session stays `pending_form`,
  customer can retry with a different card.
- ORB extraction failure (poor quality) → 400, session stays `pending_scan`.
- The second-scan failure does not roll back the user record — if confirm
  fails, the user is enrolled but cannot pay reliably.

---

## 2. Authenticate

```
Kiosk                     FingerPay                                     DB
  │                            │                                          │
  │ POST /authenticate         │                                          │
  │  Header: x-api-key         │                                          │
  │  Body: multipart image     │                                          │
  ├───────────────────────────►│ verify_merchant_api_key (sha256 lookup)  │
  │                            ├─────────────────────────────────────────►│
  │                            │ ◄────────merchant─────────────────────── │
  │                            │ rate limit: 10/min/IP                    │
  │                            │ extract ORB descriptor (OpenCV)          │
  │                            │ SELECT user_id, descriptor FROM          │
  │                            │ fingerprints  (full table scan)          │
  │                            ├─────────────────────────────────────────►│
  │                            │ ◄──────all rows───────────────────────── │
  │                            │ for each: AES-GCM decrypt + ORB match    │
  │                            │ pick best score; threshold = 40          │
  │                            │ create_access_token(user_id, merchant_id)│
  │ ◄─{access_token, user_id}──┤                                          │
```

### Notes
- O(N) over **all** enrolled users on every authentication. There is no
  fingerprint index, no clustering, no biometric template hashing.
- All descriptors are decrypted into RAM on every request — CPU + memory cost.
- Match is "best score above threshold." False positives WILL happen at scale
  (see SECURITY.md).
- Token TTL is 2 minutes.

---

## 3. Pay (customer JWT → Stripe charge)

```
Kiosk                     FingerPay                                  Stripe
  │ POST /pay                  │                                       │
  │  Header: Authorization:    │                                       │
  │   Bearer <access_token>    │                                       │
  │  Body: {amount, merchant}  │                                       │
  ├───────────────────────────►│ verify_access_token                   │
  │                            │ get_user_by_id                        │
  │                            │ get_merchant_by_id                    │
  │                            │ calculate_platform_fee:               │
  │                            │   amount*0.005 + $0.05                │
  │                            │   + $29 if first tx of month          │
  │                            │ stripe.PaymentIntent.create:          │
  │                            │   off_session, confirm                │
  │                            │   destination=connect_id (if any)     │
  │                            │   application_fee_amount = fee*100    │
  │                            ├──────────────────────────────────────►│
  │                            │ ◄────────PaymentIntent───────────────┤
  │                            │ if include_monthly: mark month        │
  │                            │ INSERT transactions row               │
  │ ◄──{success, transaction}──┤                                       │
```

### Notes
- The `merchant` string in the request body is whatever the kiosk sends
  ("POS Terminal" by default). It is stored verbatim in `transactions.merchant`
  next to the authoritative `merchant_id`. **Server should derive merchant
  name from the JWT's merchant_id, not trust the client.**
- `application_fee_amount` includes the monthly fee. If this is a small
  transaction in a new month, `application_fee_amount > amount` and Stripe
  rejects the call with a 4xx — the merchant cannot transact until a tx large
  enough to cover the $29 fee. **See ISSUES.md #4.**
- If `record_transaction` fails *after* Stripe charges the customer, the
  customer is charged but no DB row exists. There is no compensating action.

---

## 4. POS-driven payment

```
Cashier presses "Charge $25.00" on POS:

POS                  FingerPay                  Kiosk (over WS)
 │                       │                            │
 │ POST /pos/charge      │                            │
 │  {api_key, amount}    │                            │
 ├──────────────────────►│ verify api key             │
 │                       │ check terminal connected   │
 │                       │ create transaction_id      │
 │                       │ ws.send_json:              │
 │                       │   payment_request          │
 │                       ├───────────────────────────►│
 │                       │                            │ kiosk shows
 │ ◄──{transaction_id}───┤                            │ "$25.00 / scan"
 │                       │                            │
 │ poll /pos/status/{id} │                            │
 │ every Xs              │                            │
 ├──────────────────────►│                            │
 │ ◄─{status: pending}───┤                            │
 │                       │                            │
 │                       │                            │ customer scans
 │                       │ POST /authenticate         │
 │                       │ ◄──────────────────────────┤
 │                       │ POST /pay                  │
 │                       │ ◄──────────────────────────┤
 │                       │                            │ ws.send_json:
 │                       │ ws.receive_json:           │   payment_complete
 │                       │ ◄──────────────────────────┤
 │                       │ in-memory transactions[id] │
 │                       │   = success                │
 │ poll /pos/status/{id} │                            │
 ├──────────────────────►│                            │
 │ ◄─{status: success}───┤                            │
```

### Notes
- The transaction status map is **in-memory** (`TerminalManager.transactions`).
  On a restart, all pending transactions are lost. POS will poll and 404.
- Connection map is also in-memory. With multiple workers, only one worker
  receives the WS connection — `/pos/charge` on a different worker errors out
  with "Terminal is not connected" even though it is.
- A second WebSocket connection from the same merchant **silently displaces**
  the first (`self.terminals[merchant_id] = ws`). No notification.
- API key passed as `?api_key=...` query string on the WebSocket — leaks into
  any URL-logging proxy / browser history.

---

## 5. Stripe Connect onboarding

```
Merchant (logged in)         FingerPay                       Stripe
       │                          │                              │
       │ POST /merchants/connect  │                              │
       ├─────────────────────────►│ if no connect_id yet:        │
       │                          │   stripe.Account.create      │
       │                          ├─────────────────────────────►│
       │                          │ ◄────acct_id────────────────┤
       │                          │ UPDATE merchants            │
       │                          │ stripe.AccountLink.create   │
       │                          ├─────────────────────────────►│
       │                          │ ◄────onboarding_url─────────┤
       │ ◄────{onboarding_url}────┤                              │
       │                          │                              │
       │ window.location =        │                              │
       │   onboarding_url         │                              │
       │ ─────────────────────────────────────────────────────►  │
       │                          │   merchant fills KYC         │
       │                          │   (on stripe.com)            │
       │                          │                              │
       │  redirect back to        │                              │
       │  /merchants/connect/return                              │
       │ ◄───────────────────────────────────────────────────────┤
       │                          │                              │
       │ GET /merchants/connect/return  (no query params!)       │
       ├─────────────────────────►│ account = None               │
       │                          │ → no-op                      │
       │                          │ redirect to /dashboard       │
       │ ◄────────────────────────┤                              │
```

### Critical defects
- Stripe's `AccountLink` `return_url` is hit **without** the account ID. The
  current code reads `?account=` which Stripe never sends.
- Even if `account` were present, the update path imports `DB_PATH` from
  `pipeline.database`, which only exists in the SQLite branch. In Postgres
  (production), this raises `ImportError`, which is silently swallowed by the
  `except Exception: pass`. **Connect status is never marked active in
  production.**
- There is no Stripe webhook (`account.updated`) handler. The only way to
  refresh status today is to call `start_connect` again, which short-circuits
  if status is already "active" — meaning the merchant is permanently stuck
  on "pending."
