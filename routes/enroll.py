"""
FingerPay — Enroll Routes
==========================
POST /enroll/session          - kiosk creates a new session + gets QR link
GET  /enroll/status/{id}      - kiosk polls for form completion
POST /enroll/start/{id}       - phone submits form data + Stripe payment method
POST /enroll/complete/{id}    - kiosk submits fingerprint scan to finish enrollment
"""

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import shutil

from pipeline.extractor import extract_descriptor
from pipeline.database import (
    enroll_user,
    check_email_exists,
    create_session,
    save_session_form,
    get_session,
    complete_session,
    get_user_by_id,
    find_user_by_fingerprint,
)
from utils.stripe_client import create_customer

router = APIRouter(prefix="/enroll")

UPLOAD_FOLDER = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


# ── Step 1: Kiosk creates a session ──────────────────────────────────────────
@router.post("/session")
async def create_enrollment_session():
    """
    Kiosk calls this to start a new enrollment.
    Returns a session_id and the URL to encode as a QR code.
    """
    session_id = str(uuid.uuid4())
    create_session(session_id)
    return {
        "session_id": session_id,
        "enroll_url": f"/static/enroll.html?session={session_id}",
    }


# ── Step 2: Kiosk polls for form completion ───────────────────────────────────
@router.get("/status/{session_id}")
async def get_enrollment_status(session_id: str):
    """
    Kiosk polls this to know when the customer has submitted the form on their phone.
    Statuses: pending_form → pending_scan → complete
    """
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": session["status"]}


# ── Step 3: Phone submits form data ───────────────────────────────────────────
class EnrollFormData(BaseModel):
    session_id: str
    full_name: str
    email: str
    phone: str | None = None
    stripe_payment_method_id: str


@router.post("/start")
async def start_enrollment(body: EnrollFormData):
    """
    Customer's phone submits name, email, phone, and Stripe payment method.
    Creates Stripe customer and saves to session.
    Kiosk will detect status change to 'pending_scan' and prompt finger scan.
    """
    if check_email_exists(body.email):
        raise HTTPException(status_code=400, detail="This email is already enrolled.")

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


# ── Step 4: Kiosk submits fingerprint to complete enrollment ──────────────────
@router.post("/complete/{session_id}")
async def complete_enrollment(session_id: str, file: UploadFile = File(...)):
    """
    Kiosk sends the fingerprint scan to complete enrollment.
    Looks up session data, creates user in DB, marks session complete.
    """
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session["status"] != "pending_scan":
        raise HTTPException(
            status_code=400,
            detail="Customer has not submitted their details yet." if session["status"] == "pending_form"
            else "Enrollment already complete.",
        )

    temp_path = UPLOAD_FOLDER / f"{uuid.uuid4()}.png"
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


# ── Step 5: Kiosk submits second scan to confirm enrollment ───────────────────
@router.post("/verify/{session_id}")
async def verify_enrollment(session_id: str, file: UploadFile = File(...)):
    """
    Kiosk sends a second fingerprint scan right after enrollment to confirm it works.
    Matches against the just-enrolled user only.
    """
    try:
        session = get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Enrollment not complete yet.")

    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User not found in session.")

    temp_path = UPLOAD_FOLDER / f"{uuid.uuid4()}.png"
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

    return {"success": True, "message": "Fingerprint confirmed!", "name": result["user"]["full_name"]}
