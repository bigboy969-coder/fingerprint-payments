"""
FingerPay — Enroll Route
=========================
POST /enroll
Registers a new user with their fingerprint.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import shutil
import uuid

from pipeline.extractor import extract_descriptor
from pipeline.database import enroll_user

router = APIRouter()

UPLOAD_FOLDER = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


@router.post("/enroll")
async def enroll(
    file: UploadFile = File(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
):
    """
    Enroll a new user.
    Accepts a fingerprint image + user details.
    Returns the created user record.
    """

    # Save uploaded image temporarily
    temp_path = UPLOAD_FOLDER / f"{uuid.uuid4()}.png"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Extract fingerprint descriptor
        descriptor = extract_descriptor(str(temp_path))

        # Save user + fingerprint to database
        user = enroll_user(
            full_name=full_name,
            email=email,
            phone=phone,
            descriptor=descriptor,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)  # delete temp file

    return {"success": True, "user": user}