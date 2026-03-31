"""
FingerPay — Pay Route
======================
POST /pay
Verifies a JWT, checks balance, deducts amount, records transaction.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from pipeline.database import deduct_balance, record_transaction
from utils.jwt import verify_access_token

router = APIRouter()


class PayRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to deduct (must be positive)")
    merchant: str = Field(..., min_length=1, description="Merchant name or ID")


@router.post("/pay")
async def pay(
    body: PayRequest,
    authorization: str = Header(...),
):
    """
    Deduct a payment from the authenticated user's wallet.

    Requires Authorization: Bearer <token> header.
    Token must be obtained from POST /authenticate.
    Returns transaction details and updated balance.
    """
    # ── Extract and verify token ──────────────────────────────────────────────
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

    # ── Deduct balance ────────────────────────────────────────────────────────
    try:
        new_balance = deduct_balance(user_id=user_id, amount=body.amount)
    except ValueError as e:
        error_msg = str(e)
        if "Insufficient balance" in error_msg:
            raise HTTPException(status_code=402, detail=error_msg)
        raise HTTPException(status_code=404, detail=error_msg)

    # ── Record transaction ────────────────────────────────────────────────────
    try:
        transaction = record_transaction(
            user_id=user_id,
            amount=body.amount,
            merchant=body.merchant,
            balance_after=new_balance,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Payment processed but transaction record failed: {e}",
        )

    return {
        "success": True,
        "transaction": transaction,
        "balance_remaining": new_balance,
    }
