"""
FingerPay — Authenticate Route
================================
POST /authenticate
Accepts a base64-encoded verification feature blob from the POS terminal,
matches it server-side via BFMatcher, and returns a short-lived JWT.
Requires a valid merchant API key.
"""

import base64

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import find_user_by_fingerprint
from app.routes.deps import verify_merchant_api_key
from app.services.jwt import create_access_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


class AuthenticateBody(BaseModel):
    features: str  # base64-encoded 318-byte verification feature blob from the terminal


@router.post("/authenticate")
@limiter.limit("10/minute")
async def authenticate(
    request: Request,
    body: AuthenticateBody,
    x_api_key: str = Header(..., description="Merchant API key"),
):
    """
    Accepts a verification feature blob captured by the POS terminal via DP SDK.
    Matches server-side using BFMatcher — no DLL dependency on the server.
    Returns a short-lived JWT on match.
    """
    try:
        merchant = verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    try:
        features = base64.b64decode(body.features)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid features encoding.")

    try:
        result = find_user_by_fingerprint(features)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not result["matched"]:
        raise HTTPException(status_code=401, detail="Fingerprint not recognized.")

    user = result["user"]
    token = create_access_token(user_id=user["id"], merchant_id=merchant["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 120,
        "user_id": user["id"],
    }
