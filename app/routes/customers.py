"""
FingerPay — Customer Routes
=============================
POST /customers/request-access  - send verification code to customer email
POST /customers/verify-code     - verify code, return customer info
DELETE /customers/delete-account - delete all customer data
"""

import random
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from app.db import (
    check_email_exists,
    get_user_by_email,
    create_customer_verification_code,
    verify_customer_code,
    delete_customer_by_email,
)
from app.services.email import send_verification_email

logger = logging.getLogger("fingerpay.customers")
router = APIRouter(prefix="/customers")


# ── Request access ────────────────────────────────────────────────────────────

class RequestAccess(BaseModel):
    email: str


@router.post("/request-access")
@limiter.limit("3/minute")
async def request_access(request: Request, body: RequestAccess, bg: BackgroundTasks = None):
    exists = check_email_exists(body.email)
    if exists:
        code = str(random.randint(100000, 999999))
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        create_customer_verification_code(body.email, code, expires_at)
        send_verification_email(bg, body.email, code)

    # Always return success to avoid leaking which emails are enrolled
    return {"success": True, "message": "If that email is enrolled, a verification code has been sent."}


# ── Verify code ───────────────────────────────────────────────────────────────

class VerifyCode(BaseModel):
    email: str
    code: str


@router.post("/verify-code")
@limiter.limit("5/minute")
async def verify_code(request: Request, body: VerifyCode):
    ok = verify_customer_code(body.email, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")

    return {
        "success": True,
        "customer": {
            "full_name": user["full_name"],
            "email": user["email"],
            "phone": user.get("phone"),
            "enrolled_at": user["enrolled_at"],
        },
    }


# ── Delete account ────────────────────────────────────────────────────────────

class DeleteAccount(BaseModel):
    email: str
    code: str


@router.delete("/delete-account")
async def delete_account(body: DeleteAccount):
    ok = verify_customer_code(body.email, body.code, consume=True)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    # Cancel Stripe customer if exists
    user = get_user_by_email(body.email)
    if user and user.get("stripe_customer_id"):
        try:
            import stripe
            from app.config import STRIPE_SECRET_KEY
            stripe.api_key = STRIPE_SECRET_KEY
            stripe.Customer.delete(user["stripe_customer_id"])
        except Exception as e:
            logger.warning("Could not delete Stripe customer: %s", e)

    deleted = delete_customer_by_email(body.email)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found.")

    return {"success": True, "message": "Your account and all associated data have been permanently deleted."}
