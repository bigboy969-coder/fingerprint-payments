"""
FingerPay — Customer Routes
=============================
POST /customers/request-access  - send verification code to customer email
POST /customers/verify-code     - verify code, return customer info
DELETE /customers/delete-account - delete all customer data
"""

import os
import random
import logging
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.database import (
    get_user_by_id,
    check_email_exists,
    create_customer_verification_code,
    verify_customer_code,
    delete_customer_by_email,
)
from pipeline.database import _get_conn, _fetchone, PH

logger = logging.getLogger("fingerpay")
router = APIRouter(prefix="/customers")


# ── Email helper ──────────────────────────────────────────────────────────────
def _send_verification_email(to_email: str, code: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — verification email not sent to %s", to_email)
        return
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": "FingerPay <onboarding@resend.dev>",
            "to": to_email,
            "subject": "FingerPay — Your verification code",
            "text": f"""Hello,

Your FingerPay verification code is:

{code}

This code expires in 10 minutes. If you did not request this, you can ignore this email.

— FingerPay
""",
        })
        logger.info("Verification email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)


# ── Request access ────────────────────────────────────────────────────────────
class RequestAccess(BaseModel):
    email: str


@router.post("/request-access")
async def request_access(body: RequestAccess):
    # Always return success to avoid leaking which emails are enrolled
    if check_email_exists(body.email):
        from datetime import datetime, timedelta
        code = str(random.randint(100000, 999999))
        expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        create_customer_verification_code(body.email, code, expires_at)
        threading.Thread(
            target=_send_verification_email,
            args=(body.email, code),
            daemon=True
        ).start()

    return {"success": True, "message": "If that email is enrolled, a verification code has been sent."}


# ── Verify code ───────────────────────────────────────────────────────────────
class VerifyCode(BaseModel):
    email: str
    code: str


@router.post("/verify-code")
async def verify_code(body: VerifyCode):
    ok = verify_customer_code(body.email, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM users WHERE email={PH}", (body.email,))
        user = _fetchone(c)

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
    ok = verify_customer_code(body.email, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    # Cancel Stripe customer if exists
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT stripe_customer_id FROM users WHERE email={PH}", (body.email,))
        user = _fetchone(c)

    if user and user.get("stripe_customer_id"):
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            stripe.Customer.delete(user["stripe_customer_id"])
        except Exception as e:
            logger.warning("Could not delete Stripe customer: %s", e)

    deleted = delete_customer_by_email(body.email)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found.")

    return {"success": True, "message": "Your account and all associated data have been permanently deleted."}
