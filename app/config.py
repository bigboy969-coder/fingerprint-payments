"""
FingerPay — Configuration
==========================
Centralized env-var loading and validation.
Every secret and config value flows through here.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Read from environment ────────────────────────────────────────────────────

FINGERPAY_SECRET = os.environ.get("FINGERPAY_SECRET", "")
BIOMETRIC_ENCRYPTION_KEY = os.environ.get("BIOMETRIC_ENCRYPTION_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
DATA_DIR = os.environ.get("DATA_DIR", "")


def validate_env() -> None:
    """Raise RuntimeError if required env vars are missing.
    Call this at app startup (lifespan), not at import time,
    so tests can set env vars before validation runs.
    """
    missing = []
    if not FINGERPAY_SECRET:
        missing.append("FINGERPAY_SECRET")
    if not BIOMETRIC_ENCRYPTION_KEY:
        missing.append("BIOMETRIC_ENCRYPTION_KEY")
    if not STRIPE_SECRET_KEY:
        missing.append("STRIPE_SECRET_KEY")
    if not STRIPE_PUBLISHABLE_KEY:
        missing.append("STRIPE_PUBLISHABLE_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"See .env.example for the full list."
        )
