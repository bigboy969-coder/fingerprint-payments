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
def create_access_token(user_id: int) -> str:
    """
    Issue a JWT for the given user_id.
    Token expires in TOKEN_TTL_MINUTES minutes.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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
