"""
FingerPay — Pay Route
======================
POST /pay
Verifies a JWT, charges the user via Stripe, records the transaction.

Flow:
  1. Verify JWT -> get user_id + merchant_id
  2. Look up user's Stripe customer + payment method
  3. Insert a pending transaction row (so a DB record exists before money moves)
  4. Charge via Stripe PaymentIntent (off-session)
  5. Update the transaction row with the Stripe result
"""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.db import (
    create_pending_transaction,
    get_merchant_by_id,
    get_user_by_id,
    update_transaction_result,
)
from app.services.jwt import verify_access_token
from app.services.stripe import charge_customer

logger = logging.getLogger("fingerpay.pay")
router = APIRouter()


class PayRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in USD (e.g. 12.50)")


@router.post("/pay")
async def pay(
    body: PayRequest,
    authorization: str = Header(...),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must be: Bearer <token>",
        )

    raw_token = authorization.removeprefix("Bearer ")

    try:
        payload = verify_access_token(raw_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id: int = payload["user_id"]

    try:
        user = get_user_by_id(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not user.get("stripe_customer_id") or not user.get("stripe_payment_method_id"):
        raise HTTPException(
            status_code=400,
            detail="No payment method on file. User must re-enroll with a payment method.",
        )

    # ── Look up merchant ──────────────────────────────────────────────────
    merchant_id = payload.get("merchant_id")
    merchant = get_merchant_by_id(merchant_id) if merchant_id else None
    merchant_name = merchant["business_name"] if merchant else "FingerPay"

    # ── Step 1: Insert pending transaction BEFORE charging ────────────────
    pending_tx = create_pending_transaction(
        user_id=user_id,
        amount=body.amount,
        merchant=merchant_name,
        merchant_id=merchant_id,
    )

    # ── Step 2: Charge via Stripe ─────────────────────────────────────────
    # Use the pending tx ID as idempotency key — retries won't double-charge.
    try:
        charge = charge_customer(
            stripe_customer_id=user["stripe_customer_id"],
            stripe_payment_method_id=user["stripe_payment_method_id"],
            amount_usd=body.amount,
            merchant=merchant_name,
            idempotency_key=f"fingerpay-tx-{pending_tx['id']}",
            stripe_connect_id=merchant.get("stripe_connect_id") if merchant else None,
        )
    except Exception as e:
        # Stripe rejected — update the pending row to failed
        try:
            update_transaction_result(pending_tx["id"], None, "failed")
        except Exception:
            logger.error("Failed to mark tx %s as failed after Stripe error", pending_tx["id"])
        raise HTTPException(status_code=402, detail=f"Payment failed: {e}")

    # ── Step 3: Update transaction with Stripe result ─────────────────────
    try:
        transaction = update_transaction_result(
            transaction_id=pending_tx["id"],
            stripe_payment_intent_id=charge["stripe_payment_intent_id"],
            stripe_status=charge["status"],
        )
    except Exception as e:
        # CRITICAL: money moved at Stripe but we can't record it locally.
        # The pending row still exists with status='pending' — reconciliation
        # can find it. Log loudly.
        logger.critical(
            "PAYMENT RECORDED AT STRIPE BUT DB UPDATE FAILED. "
            "tx_id=%s stripe_pi=%s amount=%s error=%s",
            pending_tx["id"],
            charge["stripe_payment_intent_id"],
            body.amount,
            e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Payment processed but transaction record failed: {e}",
        )

    return {
        "success": True,
        "transaction": transaction,
        "stripe_status": charge["status"],
    }
