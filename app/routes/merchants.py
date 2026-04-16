"""
FingerPay — Merchant Routes
=============================
POST /merchants/signup         - create a merchant account
POST /merchants/login          - get a merchant JWT
GET  /merchants/me             - dashboard data (requires merchant JWT)
GET  /merchants/customers      - customers who transacted with this merchant
POST /merchants/connect        - start Stripe Connect onboarding
GET  /merchants/connect/return - after Stripe Connect onboarding completes
POST /merchants/regenerate-key - generate a new API key
POST /merchants/forgot-password
POST /merchants/reset-password
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from app.config import APP_BASE_URL
from app.db import (
    consume_reset_token,
    create_merchant,
    create_reset_token,
    get_merchant_by_email,
    get_merchant_customers,
    get_merchant_recent_transactions,
    get_merchant_stats,
    get_reset_token,
    update_merchant_api_key,
    update_merchant_connect,
    update_merchant_connect_status_by_account,
)
from app.routes.deps import get_merchant_from_token, hash_api_key
from app.services.email import send_reset_email
from app.services.jwt import create_merchant_token
from app.services.stripe import (
    create_connect_account,
    create_onboarding_link,
    get_connect_account_status,
)

logger = logging.getLogger("fingerpay.merchants")

router = APIRouter(prefix="/merchants")


# ── Signup ────────────────────────────────────────────────────────────────────


class MerchantSignup(BaseModel):
    business_name: str
    name: str
    email: str
    password: str


@router.post("/signup")
@limiter.limit("3/minute")
async def signup(request: Request, body: MerchantSignup):
    if get_merchant_by_email(body.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hash_api_key(api_key)

    merchant = create_merchant(
        business_name=body.business_name,
        name=body.name,
        email=body.email,
        password_hash=password_hash,
        api_key_hash=api_key_hash,
    )

    token = create_merchant_token(merchant["id"])

    response = JSONResponse(
        content={
            "success": True,
            "api_key": api_key,
            "warning": "Save your API key now — it will not be shown again.",
        }
    )
    response.set_cookie(
        key="merchant_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=24 * 3600,
        path="/",
    )
    return response


# ── Login ─────────────────────────────────────────────────────────────────────


class MerchantLogin(BaseModel):
    email: str
    password: str


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: MerchantLogin):
    merchant = get_merchant_by_email(body.email)
    if not merchant or not merchant.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not bcrypt.checkpw(body.password.encode(), merchant["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_merchant_token(merchant["id"])

    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key="merchant_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=24 * 3600,
        path="/",
    )
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────


@router.get("/me")
async def dashboard(request: Request, authorization: str = Header(None)):
    merchant = get_merchant_from_token(authorization, request)

    # Self-healing: if Connect status is locally stale, re-fetch from Stripe
    connect_status = merchant.get("stripe_connect_status", "pending")
    connect_id = merchant.get("stripe_connect_id")
    if connect_id and connect_status == "pending":
        try:
            fresh_status = get_connect_account_status(connect_id)
            if fresh_status != connect_status:
                update_merchant_connect_status_by_account(connect_id, fresh_status)
                connect_status = fresh_status
        except Exception:
            pass  # Stripe may be down — show stale status rather than error

    stats = get_merchant_stats(merchant["id"])
    recent = get_merchant_recent_transactions(merchant["id"])

    return {
        "business_name": merchant["business_name"],
        "name": merchant["name"],
        "email": merchant["email"],
        "stripe_connect_status": connect_status,
        "stats": stats,
        "recent_transactions": recent,
    }


# ── Customers ─────────────────────────────────────────────────────────────────


@router.get("/customers")
async def merchant_customers(request: Request, authorization: str = Header(None)):
    merchant = get_merchant_from_token(authorization, request)
    customers = get_merchant_customers(merchant["id"])
    return {"customers": customers}


# ── Stripe Connect ────────────────────────────────────────────────────────────


@router.post("/connect")
async def start_connect(request: Request, authorization: str = Header(None)):
    merchant = get_merchant_from_token(authorization, request)

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

        # Pass our own account param in the return URL — Stripe doesn't append it.
        onboarding_url = create_onboarding_link(
            account_id=connect_id,
            return_url=f"{APP_BASE_URL}/merchants/connect/return?account={connect_id}",
            refresh_url=f"{APP_BASE_URL}/static/merchant-dashboard.html",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe Connect error: {e}")

    return {"onboarding_url": onboarding_url}


@router.get("/connect/return")
async def connect_return(account: str = None):
    """Stripe redirects here after the merchant completes onboarding.
    We pass ?account=<connect_id> ourselves in the return URL."""
    if account:
        try:
            status = get_connect_account_status(account)
            update_merchant_connect_status_by_account(account, status)
        except Exception as e:
            logger.warning("Failed to update Connect status for %s: %s", account, e)
    return RedirectResponse(url="/static/merchant-dashboard.html")


# ── Regenerate API key ────────────────────────────────────────────────────────


@router.post("/regenerate-key")
async def regenerate_key(request: Request, authorization: str = Header(None)):
    merchant = get_merchant_from_token(authorization, request)

    new_key = secrets.token_urlsafe(32)
    new_hash = hash_api_key(new_key)
    update_merchant_api_key(merchant["id"], new_hash)

    return {
        "success": True,
        "api_key": new_key,
        "warning": "Save your new API key now — it will not be shown again.",
    }


# ── Forgot / Reset Password ──────────────────────────────────────────────────


class ForgotPassword(BaseModel):
    email: str


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: ForgotPassword, bg: BackgroundTasks = None):
    merchant = get_merchant_by_email(body.email)
    if merchant:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        create_reset_token(merchant["id"], token, expires_at)

        reset_url = f"{APP_BASE_URL}/business/reset-password?token={token}"
        send_reset_email(bg, merchant["email"], reset_url)

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

    if record["expires_at"] < datetime.now(UTC).isoformat():
        raise HTTPException(status_code=400, detail="Reset link has expired.")

    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    ok = consume_reset_token(body.token, new_hash)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    return {"success": True, "message": "Password updated. You can now sign in."}


# ── Logout ────────────────────────────────────────────────────────────────────


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"success": True})
    response.delete_cookie(key="merchant_token", path="/")
    return response


# ── Legacy ────────────────────────────────────────────────────────────────────


class MerchantRegister(BaseModel):
    name: str
    email: str


@router.post("/register")
async def register_merchant(body: MerchantRegister):
    """Legacy endpoint — use /merchants/signup instead."""
    raise HTTPException(
        status_code=410, detail="This endpoint is deprecated. Use POST /merchants/signup instead."
    )
