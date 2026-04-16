"""
FingerPay — JWT Utility
========================
Creates and verifies short-lived access tokens.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import FINGERPAY_SECRET

ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 2


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
    return jwt.encode(payload, FINGERPAY_SECRET, algorithm=ALGORITHM)


def create_merchant_token(merchant_id: int) -> str:
    """Issue a long-lived JWT for a merchant dashboard session (24 hours)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {
        "merchant_id": merchant_id,
        "exp": expire,
        "type": "merchant",
    }
    return jwt.encode(payload, FINGERPAY_SECRET, algorithm=ALGORITHM)


def verify_merchant_token(token: str) -> dict:
    """Decode and validate a merchant JWT. Raises ValueError if invalid."""
    try:
        payload = jwt.decode(token, FINGERPAY_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "merchant":
            raise ValueError("Not a merchant token.")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")


def verify_access_token(token: str) -> dict:
    """
    Decode and validate a customer access token.
    Rejects merchant tokens — a merchant JWT used on /pay should be a
    clean 401, not a KeyError 500.
    Raises ValueError if the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(token, FINGERPAY_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "customer":
            raise ValueError("Not a customer access token.")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")
