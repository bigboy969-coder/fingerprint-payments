"""
FingerPay — Merchant Routes
=============================
POST /merchants/signup         - create a merchant account
POST /merchants/login          - get a merchant JWT
GET  /merchants/me             - dashboard data (requires merchant JWT)
POST /merchants/connect        - start Stripe Connect onboarding
GET  /merchants/connect/return - after Stripe Connect onboarding completes
POST /merchants/regenerate-key - generate a new API key
"""

import os
import secrets
import hashlib
import logging
import threading
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from pipeline.database import (
    create_merchant,
    get_merchant_by_email,
    get_merchant_by_id,
    get_merchant_by_api_key_hash,
    update_merchant_connect,
    update_merchant_api_key,
    get_merchant_stats,
    get_merchant_recent_transactions,
    get_merchant_customers,
    create_reset_token,
    get_reset_token,
    consume_reset_token,
)
from utils.jwt import create_merchant_token, verify_merchant_token
from utils.stripe_client import (
    create_connect_account,
    create_onboarding_link,
    get_connect_account_status,
)

logger = logging.getLogger("fingerpay")

router = APIRouter(prefix="/merchants")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _get_merchant_from_token(authorization: str) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be: Bearer <token>")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = verify_merchant_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    merchant = get_merchant_by_id(payload["merchant_id"])
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")
    return merchant


def verify_merchant_api_key(api_key: str) -> dict:
    """Verify an API key — returns merchant record or raises ValueError."""
    key_hash = _hash_api_key(api_key)
    merchant = get_merchant_by_api_key_hash(key_hash)
    if not merchant:
        raise ValueError("Invalid API key.")
    return merchant


# ── Signup ────────────────────────────────────────────────────────────────────
class MerchantSignup(BaseModel):
    business_name: str
    name: str
    email: str
    password: str


@router.post("/signup")
async def signup(body: MerchantSignup):
    if get_merchant_by_email(body.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    api_key = secrets.token_urlsafe(32)
    api_key_hash = _hash_api_key(api_key)

    merchant = create_merchant(
        business_name=body.business_name,
        name=body.name,
        email=body.email,
        password_hash=password_hash,
        api_key_hash=api_key_hash,
    )

    token = create_merchant_token(merchant["id"])

    return {
        "success": True,
        "token": token,
        "api_key": api_key,
        "warning": "Save your API key now — it will not be shown again.",
    }


# ── Login ─────────────────────────────────────────────────────────────────────
class MerchantLogin(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: MerchantLogin):
    merchant = get_merchant_by_email(body.email)
    if not merchant or not merchant.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not bcrypt.checkpw(body.password.encode(), merchant["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_merchant_token(merchant["id"])
    return {"success": True, "token": token}


# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/me")
async def dashboard(authorization: str = Header(...)):
    merchant = _get_merchant_from_token(authorization)
    stats = get_merchant_stats(merchant["id"])
    recent = get_merchant_recent_transactions(merchant["id"])

    return {
        "business_name": merchant["business_name"],
        "name": merchant["name"],
        "email": merchant["email"],
        "stripe_connect_status": merchant.get("stripe_connect_status", "pending"),
        "stats": stats,
        "recent_transactions": recent,
    }


# ── Customers ─────────────────────────────────────────────────────────────────
@router.get("/customers")
async def merchant_customers(authorization: str = Header(...)):
    merchant = _get_merchant_from_token(authorization)
    customers = get_merchant_customers(merchant["id"])
    return {"customers": customers}


# ── Stripe Connect ────────────────────────────────────────────────────────────
@router.post("/connect")
async def start_connect(authorization: str = Header(...)):
    merchant = _get_merchant_from_token(authorization)

    if merchant.get("stripe_connect_id") and merchant.get("stripe_connect_status") == "active":
        raise HTTPException(status_code=400, detail="Bank account already connected.")

    try:
        if not merchant.get("stripe_connect_id"):
            connect_id = create_connect_account(
                email=merchant["email"],
                business_name=merchant["business_name"],
            )
            update_merchant_connect(merchant["id"], connect_id, "pending")
        else:
            connect_id = merchant["stripe_connect_id"]

        import os
        base_url = os.environ.get("APP_BASE_URL", "https://fingerprint-payments.onrender.com")
        onboarding_url = create_onboarding_link(
            account_id=connect_id,
            return_url=f"{base_url}/merchants/connect/return",
            refresh_url=f"{base_url}/static/merchant-dashboard.html",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe Connect error: {e}")

    return {"onboarding_url": onboarding_url}


@router.get("/connect/return")
async def connect_return(account: str = None):
    """Stripe redirects here after the merchant completes onboarding."""
    if account:
        try:
            status = get_connect_account_status(account)
            from pipeline.database import DB_PATH
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE merchants SET stripe_connect_status=? WHERE stripe_connect_id=?",
                (status, account)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
    return RedirectResponse(url="/static/merchant-dashboard.html")


# ── Regenerate API key ────────────────────────────────────────────────────────
@router.post("/regenerate-key")
async def regenerate_key(authorization: str = Header(...)):
    merchant = _get_merchant_from_token(authorization)

    new_key = secrets.token_urlsafe(32)
    new_hash = _hash_api_key(new_key)
    update_merchant_api_key(merchant["id"], new_hash)

    return {
        "success": True,
        "api_key": new_key,
        "warning": "Save your new API key now — it will not be shown again.",
    }


# ── Forgot / Reset Password ───────────────────────────────────────────────────
def _send_reset_email(to_email: str, reset_url: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — reset email not sent to %s", to_email)
        return

    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": "FingerPay <onboarding@resend.dev>",
            "to": to_email,
            "subject": "FingerPay — Reset your password",
            "text": f"""Hello,

Someone requested a password reset for your FingerPay merchant account.

Click the link below to set a new password (valid for 1 hour):

{reset_url}

If you did not request this, you can ignore this email — your password will not change.

— FingerPay
""",
        })
        logger.info("Reset email sent successfully to %s", to_email)
    except Exception as e:
        logger.error("Failed to send reset email to %s: %s", to_email, e)


class ForgotPassword(BaseModel):
    email: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotPassword):
    merchant = get_merchant_by_email(body.email)
    # Always return success to avoid leaking which emails are registered
    if merchant:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        create_reset_token(merchant["id"], token, expires_at)

        base_url = os.environ.get("APP_BASE_URL", "https://fingerprint-payments.onrender.com")
        reset_url = f"{base_url}/business/reset-password?token={token}"
        threading.Thread(target=_send_reset_email, args=(merchant["email"], reset_url), daemon=True).start()

    return {"success": True, "message": "If that email is registered, a reset link has been sent."}


class ResetPassword(BaseModel):
    token: str
    new_password: str


@router.post("/reset-password")
async def reset_password(body: ResetPassword):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    record = get_reset_token(body.token)
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    from datetime import datetime
    if record["expires_at"] < datetime.utcnow().isoformat():
        raise HTTPException(status_code=400, detail="Reset link has expired.")

    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    ok = consume_reset_token(body.token, new_hash)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    return {"success": True, "message": "Password updated. You can now sign in."}


# ── Legacy register (kept for backwards compatibility) ────────────────────────
class MerchantRegister(BaseModel):
    name: str
    email: str


@router.post("/register")
async def register_merchant(body: MerchantRegister):
    """Legacy endpoint — use /merchants/signup instead."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use POST /merchants/signup instead."
    )
