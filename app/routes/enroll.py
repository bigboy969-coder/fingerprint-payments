"""
FingerPay — Enroll Routes
==========================
POST /enroll/session          - kiosk creates a new session + gets QR link
GET  /enroll/status/{id}      - kiosk polls for form completion
POST /enroll/start/{id}       - phone submits form data + Stripe payment method
POST /enroll/complete/{id}    - kiosk triggers fingerprint capture to finish enrollment
POST /enroll/verify/{id}      - kiosk captures a second scan to confirm enrollment
"""

import base64
import uuid

from fastapi import APIRouter, HTTPException
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
from app.services.biometrics import ENROLL_FEATURE_SIZE
from app.services.stripe import create_customer

router = APIRouter(prefix="/enroll")


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


class EnrollCompleteBody(BaseModel):
    feature_blobs: list[str]  # 4 base64-encoded 318-byte pre-reg feature blobs from the terminal


@router.post("/complete/{session_id}")
async def complete_enrollment(session_id: str, body: EnrollCompleteBody):
    """
    Accepts 4 base64-encoded pre-reg feature blobs from the POS terminal.
    The terminal captures and extracts features locally via DP SDK; matching
    happens server-side via BFMatcher.
    """
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

    if len(body.feature_blobs) != 4:
        raise HTTPException(status_code=400, detail="Exactly 4 feature blobs required.")

    try:
        feature_blobs = [base64.b64decode(b) for b in body.feature_blobs]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid blob encoding.")

    if any(len(b) != ENROLL_FEATURE_SIZE for b in feature_blobs):
        raise HTTPException(
            status_code=400,
            detail=f"Each feature blob must be {ENROLL_FEATURE_SIZE} bytes.",
        )

    try:
        user = enroll_user(
            full_name=session["full_name"],
            email=session["email"],
            phone=session["phone"],
            feature_blobs=feature_blobs,
            stripe_customer_id=session["stripe_customer_id"],
            stripe_payment_method_id=session["stripe_payment_method_id"],
        )
        complete_session(session_id, user_id=user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "user": user}


class VerifyBody(BaseModel):
    features: str  # base64-encoded 318-byte verification feature blob from the terminal


@router.post("/verify/{session_id}")
async def verify_enrollment(session_id: str, body: VerifyBody):
    """
    Accepts a base64-encoded verification feature blob from the terminal and
    confirms the newly enrolled fingerprint matches server-side via BFMatcher.
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

    try:
        features = base64.b64decode(body.features)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid features encoding.")

    try:
        result = find_user_by_fingerprint(features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not result["matched"] or result["user"]["id"] != user_id:
        raise HTTPException(status_code=401, detail="Fingerprint did not match. Try again.")

    return {
        "success": True,
        "message": "Fingerprint confirmed!",
        "name": result["user"]["full_name"],
    }
