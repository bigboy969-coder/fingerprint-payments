"""
FingerPay — Authenticate Route
================================
POST /authenticate
Matches a fingerprint and returns a short-lived JWT.
Requires a valid merchant API key.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Request
from pathlib import Path
import shutil
import uuid

from pipeline.extractor import extract_descriptor
from pipeline.database import find_user_by_fingerprint
from utils.jwt import create_access_token
from routes.merchants import verify_merchant_api_key
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

UPLOAD_FOLDER = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


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
    # Verify merchant API key
    try:
        merchant = verify_merchant_api_key(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid merchant API key.")

    temp_path = UPLOAD_FOLDER / f"{uuid.uuid4()}.png"
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
