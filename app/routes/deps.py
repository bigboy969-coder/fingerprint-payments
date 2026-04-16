"""
FingerPay — Shared Route Dependencies
========================================
Auth helpers used by multiple route modules.
"""

import hashlib

from fastapi import HTTPException, Request

from app.db import get_merchant_by_api_key_hash, get_merchant_by_id
from app.services.jwt import verify_merchant_token


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_merchant_api_key(api_key: str) -> dict:
    """Verify an API key — returns merchant record or raises ValueError."""
    key_hash = hash_api_key(api_key)
    merchant = get_merchant_by_api_key_hash(key_hash)
    if not merchant:
        raise ValueError("Invalid API key.")
    return merchant


def get_merchant_from_token(authorization: str = None, request: Request = None) -> dict:
    """Extract and validate a merchant JWT.
    Reads from the HttpOnly cookie first, then falls back to the
    Authorization header for backwards compatibility and API clients.
    """
    token = None

    # Try cookie first (set by /merchants/login)
    if request:
        token = request.cookies.get("merchant_token")

    # Fall back to Authorization header
    if not token and authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="Authorization header must be: Bearer <token>"
            )
        token = authorization.removeprefix("Bearer ")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        payload = verify_merchant_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    merchant = get_merchant_by_id(payload["merchant_id"])
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")
    return merchant
