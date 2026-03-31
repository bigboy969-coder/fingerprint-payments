"""
FingerPay — Authenticate Route
================================
POST /authenticate
Matches a fingerprint and returns a short-lived JWT.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import uuid

from pipeline.extractor import extract_descriptor
from pipeline.database import find_user_by_fingerprint
from utils.jwt import create_access_token

router = APIRouter()

UPLOAD_FOLDER = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


@router.post("/authenticate")
async def authenticate(file: UploadFile = File(...)):
    """
    Accept a fingerprint image.
    Returns a JWT access token if the fingerprint matches an enrolled user.
    """
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
    token = create_access_token(user_id=user["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 120,
        "user_id": user["id"],
    }
