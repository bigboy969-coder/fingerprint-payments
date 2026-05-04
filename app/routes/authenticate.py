"""
FingerPay — Authenticate Route
================================
POST /authenticate
Captures a fingerprint from the reader, matches it against enrolled users,
and returns a short-lived JWT. Requires a valid merchant API key.
"""

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import find_user_by_fingerprint
from app.routes.deps import verify_merchant_api_key
from app.services.biometrics import capture_verification_features
from app.services.jwt import create_access_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/authenticate")
@limiter.limit("10/minute")
async def authenticate(
    request: Request,
    x_api_key: str = Header(..., description="Merchant API key"),
):
    """
    Capture a fingerprint from the reader at the merchant terminal.
    Returns a JWT access token if the fingerprint matches an enrolled user.
    """
    try:
        merchant = verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    try:
        features = capture_verification_features(timeout=15)
        result = find_user_by_fingerprint(features)
    except TimeoutError:
        raise HTTPException(status_code=408, detail="No finger detected. Please try again.")
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
