"""
FingerPay — Pay Route
======================
POST /pay
Verifies a JWT, charges the user via Stripe, records the transaction.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from pipeline.database import get_user_by_id, get_merchant_by_id, record_transaction, update_merchant_monthly_fee_month
from utils.jwt import verify_access_token
from utils.stripe_client import charge_customer, calculate_platform_fee, MONTHLY_FEE

router = APIRouter()


class PayRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in USD (e.g. 12.50)")
    merchant: str = Field(..., min_length=1, description="Merchant name or ID")


@router.post("/pay")
async def pay(
    body: PayRequest,
    authorization: str = Header(...),
):
    """
    Charge the authenticated user via Stripe.

    Requires Authorization: Bearer <token> header.
    Token must be obtained from POST /authenticate.

    Flow:
      1. Verify JWT → get user_id
      2. Look up user's Stripe customer + payment method
      3. Charge via Stripe PaymentIntent (off-session)
      4. Record transaction
    """
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

    # ── Look up merchant and calculate fees ───────────────────────────────────
    merchant_id = payload.get("merchant_id")
    merchant = get_merchant_by_id(merchant_id) if merchant_id else None

    from datetime import datetime
    current_month = datetime.now().strftime("%Y-%m")
    include_monthly = (
        merchant is not None and
        merchant.get("last_monthly_fee_month") != current_month
    )
    platform_fee = calculate_platform_fee(body.amount, include_monthly=include_monthly)

    # ── Charge via Stripe ─────────────────────────────────────────────────────
    try:
        charge = charge_customer(
            stripe_customer_id=user["stripe_customer_id"],
            stripe_payment_method_id=user["stripe_payment_method_id"],
            amount_usd=body.amount,
            merchant=body.merchant,
            stripe_connect_id=merchant.get("stripe_connect_id") if merchant else None,
            platform_fee_usd=platform_fee if merchant and merchant.get("stripe_connect_id") else None,
        )
    except Exception as e:
        raise HTTPException(status_code=402, detail=f"Payment failed: {e}")

    # Mark monthly fee as collected this month
    if include_monthly and merchant:
        update_merchant_monthly_fee_month(merchant["id"], current_month)

    # ── Record transaction ────────────────────────────────────────────────────
    try:
        transaction = record_transaction(
            user_id=user_id,
            amount=body.amount,
            merchant=body.merchant,
            stripe_payment_intent_id=charge["stripe_payment_intent_id"],
            stripe_status=charge["status"],
            merchant_id=merchant_id,
            platform_fee=platform_fee,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Payment processed but transaction record failed: {e}",
        )

    return {
        "success": True,
        "transaction": transaction,
        "stripe_status": charge["status"],
    }
