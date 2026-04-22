"""
FingerPay — Enroll Routes
==========================
POST /enroll/session          - kiosk creates a new session + gets QR link
GET  /enroll/status/{id}      - kiosk polls for form completion
POST /enroll/start/{id}       - phone submits form data + Stripe payment method
POST /enroll/complete/{id}    - kiosk submits fingerprint scan to finish enrollment
"""

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.db import (
    check_email_exists,
    complete_session,
    create_session,
    enroll_user,
    find_user_by_fingerprint,
    get_session,
    save_session_form,
)
from app.services.biometrics import extract_descriptor
from app.services.stripe import create_customer

router = APIRouter(prefix="/enroll")

UPLOAD_DIR = Path(tempfile.gettempdir()) / "fingerpay_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/session")
async def create_enrollment_session():
    session_id = str(uuid.uuid4())
    create_session(session_id)
    return {
        "session_id": session_id,
        "enroll_url": f"/static/enroll.html?session={session_id}",
    }


@router.get("/status/{session_id}")
async def get_enrollment_status(session_id: str):
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": session["status"]}


class EnrollFormData(BaseModel):
    session_id: str
    full_name: str
    email: str
    phone: str | None = None
    stripe_payment_method_id: str


@router.post("/start")
async def start_enrollment(body: EnrollFormData):
    if check_email_exists(body.email):
        # Generic message to avoid leaking which emails are enrolled (ISSUES #14)
        raise HTTPException(
            status_code=400,
            detail="Unable to complete enrollment. Please try again or contact support.",
        )

    try:
        session = get_session(body.session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session["status"] != "pending_form":
        raise HTTPException(status_code=400, detail="Session already used.")

    try:
        stripe_customer_id = create_customer(
            full_name=body.full_name,
            email=body.email,
            payment_method_id=body.stripe_payment_method_id,
        )
    except Exception as e:
        raise HTTPException(status_code=402, detail=f"Card setup failed: {e}")

    save_session_form(
        session_id=body.session_id,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        stripe_customer_id=stripe_customer_id,
        stripe_payment_method_id=body.stripe_payment_method_id,
    )

    return {"success": True, "message": "Please go to the kiosk to scan your finger."}


@router.post("/complete/{session_id}")
async def complete_enrollment(session_id: str, file: UploadFile = File(...)):
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session["status"] != "pending_scan":
        raise HTTPException(
            status_code=400,
            detail=(
                "Customer has not submitted their details yet."
                if session["status"] == "pending_form"
                else "Enrollment already complete."
            ),
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}.png"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        descriptor = extract_descriptor(str(temp_path))
        user = enroll_user(
            full_name=session["full_name"],
            email=session["email"],
            phone=session["phone"],
            descriptor=descriptor,
            stripe_customer_id=session["stripe_customer_id"],
            stripe_payment_method_id=session["stripe_payment_method_id"],
        )
        complete_session(session_id, user_id=user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)

    return {"success": True, "user": user}


@router.post("/verify/{session_id}")
async def verify_enrollment(session_id: str, file: UploadFile = File(...)):
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Enrollment not complete yet.")

    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User not found in session.")

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}.png"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        descriptor = extract_descriptor(str(temp_path))
        result = find_user_by_fingerprint(descriptor)
        if not result["matched"] or result["user"]["id"] != user_id:
            raise HTTPException(status_code=401, detail="Fingerprint did not match. Try again.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "success": True,
        "message": "Fingerprint confirmed!",
        "name": result["user"]["full_name"],
    }
