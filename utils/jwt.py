"""
FingerPay — JWT Utility
========================
Creates and verifies short-lived access tokens.
"""

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("FINGERPAY_SECRET", "dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 2


# ── Create ────────────────────────────────────────────────────────────────────
def create_access_token(user_id: int, merchant_id: int = None) -> str:
    """
    Issue a JWT for the given user_id.
    Token expires in TOKEN_TTL_MINUTES minutes.
    Optionally includes merchant_id so pay.py knows which merchant to pay out.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "type": "customer",
    }
    if merchant_id is not None:
        payload["merchant_id"] = merchant_id
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_merchant_token(merchant_id: int) -> str:
    """Issue a long-lived JWT for a merchant dashboard session (24 hours)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {
        "merchant_id": merchant_id,
        "exp": expire,
        "type": "merchant",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_merchant_token(token: str) -> dict:
    """Decode and validate a merchant JWT. Raises ValueError if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "merchant":
            raise ValueError("Not a merchant token.")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")


# ── Verify ────────────────────────────────────────────────────────────────────
def verify_access_token(token: str) -> dict:
    """
    Decode and validate a JWT.
    Returns the decoded payload on success.
    Raises ValueError if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")
