# API Reference

Authoritative as of the current code. Status codes are what the handlers
actually return (a few "should-be-401" paths are noted).

---

## Public / Top-level

### `GET /`
Redirects to `/static/index.html`.

### `GET /config`
Returns the public Stripe key for the enrollment page.
```json
{ "publishable_key": "pk_test_..." }
```

### `GET /kiosk`
Redirects to `/static/kiosk.html`.

### `GET /business`, `/business/login`, `/business/dashboard`, `/business/reset-password?token=`, `/my-account`
Redirects to the corresponding static HTML page.

---

## Enrollment — `/enroll/*`

### `POST /enroll/session`
Kiosk creates a new enrollment session.
```json
// 200
{
  "session_id": "uuid",
  "enroll_url": "/static/enroll.html?session=uuid"
}
```

### `GET /enroll/status/{session_id}`
Kiosk polls for state transitions.
```json
{ "status": "pending_form" | "pending_scan" | "complete" }
```
Errors: `404` Session not found.

### `POST /enroll/start`
Phone submits form data. Server creates the Stripe customer.
```json
// request
{
  "session_id": "uuid",
  "full_name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+1...",          // optional
  "stripe_payment_method_id": "pm_..."
}
```
Errors:
- `400` "This email is already enrolled" (**email-enumeration leak**)
- `400` "Session already used"
- `402` "Card setup failed: ..."
- `404` "Session not found"

### `POST /enroll/complete/{session_id}` (multipart)
Kiosk uploads the fingerprint image. Persists user + descriptor.
- `200` `{ "success": true, "user": { ... } }`
- `400` Bad image / image quality / customer hasn't submitted form
- `500` ORB extraction error

### `POST /enroll/verify/{session_id}` (multipart)
Second-scan confirmation right after enrollment.
- `200` `{ "success": true, "message": "...", "name": "Jane Doe" }`
- `401` Fingerprint did not match.

---

## Authenticate — `/authenticate`

### `POST /authenticate` (multipart, rate-limited 10/min/IP)
Headers: `x-api-key: <merchant api key>`
Body: `file=<fingerprint image>`
```json
// 200
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 120,
  "user_id": 7
}
```
Errors:
- `401` Invalid merchant API key
- `400` Image read / quality failure
- `401` Fingerprint not recognized

---

## Pay — `/pay`

### `POST /pay`
Headers: `Authorization: Bearer <access_token>`
```json
// request
{ "amount": 12.50, "merchant": "Joe's Coffee" }
```
```json
// 200
{
  "success": true,
  "transaction": { ...row... },
  "stripe_status": "succeeded"
}
```
Errors:
- `401` Bad/expired bearer
- `404` User not found (orphaned JWT)
- `400` No payment method on file
- `402` Stripe rejected (e.g. `application_fee_amount > amount`)
- `500` Charge succeeded but record_transaction failed (**money charged, no DB row**)

### Notes
- `merchant` field is client-supplied and stored unsanitized in
  `transactions.merchant`. The actual merchant for fee accounting comes from
  the JWT's `merchant_id`.

---

## Merchants — `/merchants/*`

### `POST /merchants/signup`
```json
// request
{ "business_name": "...", "name": "...", "email": "...", "password": "..." }
// 200
{
  "success": true,
  "token": "<merchant_jwt>",
  "api_key": "<plaintext, shown once>",
  "warning": "Save your API key now ..."
}
```
- `400` Email already exists.
- **No password complexity validation.**

### `POST /merchants/login`
```json
{ "email": "...", "password": "..." }
// 200
{ "success": true, "token": "<merchant_jwt>" }
// 401 Invalid email or password
```
- **Not rate-limited.**

### `GET /merchants/me`
Headers: `Authorization: Bearer <merchant_jwt>`
```json
{
  "business_name": "...",
  "name": "...",
  "email": "...",
  "stripe_connect_status": "pending" | "active",
  "stats": {
    "tx_count": 0,
    "total_processed": 0,
    "total_fees": 0
  },
  "recent_transactions": [...]
}
```

### `GET /merchants/customers`
Headers: `Authorization: Bearer <merchant_jwt>`
Returns **all** distinct customers who transacted with this merchant. No
pagination.

### `POST /merchants/connect`
Returns Stripe Express onboarding URL.
- `400` already active.
- `500` Stripe Connect error.

### `GET /merchants/connect/return?account=`
Stripe redirects here after onboarding. **Currently a no-op in production**
because (a) Stripe doesn't append `account` and (b) the update code path
imports `DB_PATH` which doesn't exist when Postgres is configured.

### `POST /merchants/regenerate-key`
Generates and returns a new plaintext API key, invalidates old.

### `POST /merchants/forgot-password`
Always returns 200 (no enumeration). Sends reset email asynchronously.

### `POST /merchants/reset-password`
```json
{ "token": "...", "new_password": "..." }
```
- `400` Invalid/expired/short password.

### `POST /merchants/register`
Always 410 — deprecated stub.

---

## Customers — `/customers/*`

### `POST /customers/request-access`
```json
{ "email": "..." }
// 200 always (no enumeration)
```
Sends 6-digit code (10-min TTL) via email.

### `POST /customers/verify-code`
```json
{ "email": "...", "code": "123456" }
// 200
{
  "success": true,
  "customer": { "full_name": "...", "email": "...", "phone": "...", "enrolled_at": "..." }
}
// 400 Invalid/expired code
// 404 Account not found
```
The code is **not consumed** here; it remains usable until expiry. This is
intentional so the customer can call `/delete-account` next.

### `DELETE /customers/delete-account`
```json
{ "email": "...", "code": "123456" }
// 200 deletes user row, fingerprints, transactions; attempts Stripe Customer.delete
```
Consumes the verification code.

---

## POS — `/pos/*`

### `WS /ws/terminal?api_key=...`
Persistent WebSocket from the kiosk tablet. The merchant's `api_key` goes in
the query string (**logged everywhere; leak risk**).

Server → client messages:
```json
{ "type": "payment_request", "amount": 12.50, "transaction_id": "uuid" }
```

Client → server:
```json
{ "type": "payment_complete", "transaction_id": "uuid", "amount": 12.50 }
{ "type": "payment_failed",   "transaction_id": "uuid", "reason": "..." }
{ "type": "ping" }
```
Server replies to ping with `{"type":"pong"}`.

A second connection silently replaces the first.

### `POST /pos/charge`
```json
{ "api_key": "...", "amount": 12.50, "description": "" }
// 200
{ "success": true, "transaction_id": "uuid", "message": "..." }
// 401 Invalid API key
// 503 Terminal is not connected
```

### `GET /pos/status/{transaction_id}`
Returns the in-memory transaction status dict, or 404.
**State is lost on process restart.**

### `GET /pos/terminal/status?api_key=...`
```json
{ "connected": true | false }
```

---

## Authorization summary

| Endpoint | Credential |
|---|---|
| `/enroll/*` | None (rate-limited only via global middleware? No.) |
| `/authenticate` | `x-api-key` header (merchant) + 10/min/IP rate limit |
| `/pay` | `Authorization: Bearer <customer JWT>` (2-min TTL) |
| `/merchants/me`, `/customers`, `/connect`, `/regenerate-key` | `Authorization: Bearer <merchant JWT>` (24h TTL) |
| `/customers/*` | Email + 6-digit code (10-min TTL) |
| `/ws/terminal`, `/pos/charge`, `/pos/terminal/status` | `api_key` (query string or body) |
