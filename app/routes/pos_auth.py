"""
FingerPay — POS Authentication Routes
=======================================
GET  /pos/templates        - POS downloads all templates for local matching
POST /pos/identify         - POS reports matched user_id, server issues JWT
"""

import base64

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db import get_all_fingerprints, get_user_by_id
from app.routes.deps import verify_merchant_api_key
from app.services.crypto import decrypt_descriptor
from app.services.jwt import create_access_token

router = APIRouter(prefix="/pos")


@router.get("/templates")
async def get_templates(x_api_key: str = Header(...)):
    """
    Returns all enrolled fingerprint templates (decrypted) for local 1:N matching.
    Only accessible to verified merchants. Transmitted over HTTPS.
    """
    try:
        verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    rows = get_all_fingerprints()
    return [
        {
            "user_id": row["user_id"],
            "template": base64.b64encode(decrypt_descriptor(bytes(row["descriptor"]))).decode(),
        }
        for row in rows
    ]


class IdentifyBody(BaseModel):
    user_id: int


@router.post("/identify")
async def identify(body: IdentifyBody, x_api_key: str = Header(...)):
    """
    Called by POS after local fingerprint matching succeeds.
    Returns a short-lived JWT to authorize a payment.
    """
    try:
        merchant = verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    try:
        user = get_user_by_id(body.user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found.")

    token = create_access_token(user_id=user["id"], merchant_id=merchant["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 120,
        "user_id": user["id"],
        "user_name": user["full_name"],
    }
