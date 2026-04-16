"""
FingerPay — Authenticate Route
================================
POST /authenticate
Matches a fingerprint and returns a short-lived JWT.
Requires a valid merchant API key.
"""

import uuid
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.biometrics import extract_descriptor
from app.db import find_user_by_fingerprint
from app.services.jwt import create_access_token
from app.routes.deps import verify_merchant_api_key

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

UPLOAD_DIR = Path(tempfile.gettempdir()) / "fingerpay_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/authenticate")
@limiter.limit("10/minute")
async def authenticate(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str = Header(..., description="Merchant API key"),
):
    """
    Accept a fingerprint image from a verified merchant terminal.
    Returns a JWT access token if the fingerprint matches an enrolled user.
    """
    try:
        merchant = verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}.png"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        descriptor = extract_descriptor(str(temp_path))
        result = find_user_by_fingerprint(descriptor)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)

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
