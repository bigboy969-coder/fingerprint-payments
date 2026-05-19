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
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
DATA_DIR = os.environ.get("DATA_DIR", "")


def validate_env() -> None:
    """Raise RuntimeError if required env vars are missing or malformed.
    Called at app startup (lifespan), not at import time, so tests can
    set env vars before this runs.
    """
    errors = []

    if not FINGERPAY_SECRET:
        errors.append("FINGERPAY_SECRET is not set")
    elif len(FINGERPAY_SECRET) < 32:
        errors.append(
            f"FINGERPAY_SECRET is too short ({len(FINGERPAY_SECRET)} chars) — "
            'generate with: python3 -c "import secrets; print(secrets.token_hex(32))"'
        )

    if not BIOMETRIC_ENCRYPTION_KEY:
        errors.append("BIOMETRIC_ENCRYPTION_KEY is not set")
    else:
        key = BIOMETRIC_ENCRYPTION_KEY.strip()
        if len(key) != 64:
            errors.append(
                f"BIOMETRIC_ENCRYPTION_KEY must be 64 hex chars (got {len(key)}) — "
                'generate with: python3 -c "import secrets; print(secrets.token_hex(32))"'
            )
        elif not all(c in "0123456789abcdefABCDEF" for c in key):
            errors.append("BIOMETRIC_ENCRYPTION_KEY must contain only hex characters (0-9, a-f)")

    if not STRIPE_SECRET_KEY:
        errors.append("STRIPE_SECRET_KEY is not set")
    if not STRIPE_PUBLISHABLE_KEY:
        errors.append("STRIPE_PUBLISHABLE_KEY is not set")

    # In production (Postgres), APP_BASE_URL must be explicitly set —
    # it's used in password reset emails and Stripe Connect return URLs.
    if DATABASE_URL and APP_BASE_URL == "http://localhost:8000":
        errors.append(
            "APP_BASE_URL is still set to localhost but DATABASE_URL is set (production mode). "
            "Set APP_BASE_URL to your deployed URL."
        )

    # STRIPE_PRICE_ID is required in production for merchant billing.
    if DATABASE_URL and not STRIPE_PRICE_ID:
        errors.append(
            "STRIPE_PRICE_ID is not set. Create a $99/month recurring price in the Stripe "
            "Dashboard and set this to the price_... ID."
        )

    if errors:
        raise RuntimeError(
            "FingerPay cannot start — fix the following environment issues:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )
