"""
FingerPay — Email Service
===========================
Transactional email sending via Resend.
Uses FastAPI BackgroundTasks — emails are sent after the response, before
the connection closes. No daemon threads.
"""

import logging

from fastapi import BackgroundTasks

from app.config import RESEND_API_KEY

logger = logging.getLogger("fingerpay.email")


def _send(to_email: str, subject: str, text: str) -> None:
    """Low-level send. Called by BackgroundTasks — do not call directly from routes."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — email not sent")
        return
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": "FingerPay <onboarding@resend.dev>",
            "to": to_email,
            "subject": subject,
            "text": text,
        })
        logger.info("Email sent: subject=%s", subject)
    except Exception as e:
        logger.error("Failed to send email: %s", e)


def send_reset_email(bg: BackgroundTasks, to_email: str, reset_url: str) -> None:
    """Queue a password-reset email for background delivery."""
    bg.add_task(
        _send,
        to_email=to_email,
        subject="FingerPay — Reset your password",
        text=f"""Hello,

Someone requested a password reset for your FingerPay merchant account.

Click the link below to set a new password (valid for 1 hour):

{reset_url}

If you did not request this, you can ignore this email — your password will not change.

— FingerPay
""",
    )


def send_verification_email(bg: BackgroundTasks, to_email: str, code: str) -> None:
    """Queue a verification-code email for background delivery."""
    bg.add_task(
        _send,
        to_email=to_email,
        subject="FingerPay — Your verification code",
        text=f"""Hello,

Your FingerPay verification code is:

{code}

This code expires in 10 minutes. If you did not request this, you can ignore this email.

— FingerPay
""",
    )
