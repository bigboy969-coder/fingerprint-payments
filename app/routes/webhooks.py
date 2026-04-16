"""
FingerPay — Stripe Webhook Handler
=====================================
POST /webhooks/stripe

Handles inbound Stripe events with signature verification.
Events handled:
  - account.updated         → refresh Connect status
  - payment_intent.payment_failed → mark transaction failed
  - charge.dispute.created  → log warning for manual review
  - charge.refunded         → update transaction status
"""

import logging

import stripe
from fastapi import APIRouter, Request, HTTPException

from app.config import STRIPE_WEBHOOK_SECRET, STRIPE_SECRET_KEY
from app.db import update_merchant_connect_status_by_account
from app.db.connection import _get_conn, PH

logger = logging.getLogger("fingerpay.webhooks")
router = APIRouter()

stripe.api_key = STRIPE_SECRET_KEY


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Receive and verify Stripe webhook events."""
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — webhook rejected")
        raise HTTPException(status_code=500, detail="Webhook not configured.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "account.updated":
        _handle_account_updated(data)
    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(data)
    elif event_type == "charge.dispute.created":
        _handle_dispute_created(data)
    elif event_type == "charge.refunded":
        _handle_charge_refunded(data)
    else:
        logger.info("Unhandled webhook event: %s", event_type)

    return {"received": True}


def _handle_account_updated(account: dict) -> None:
    """Stripe Connect account status changed."""
    account_id = account.get("id", "")
    details_submitted = account.get("details_submitted", False)
    charges_enabled = account.get("charges_enabled", False)

    status = "active" if details_submitted and charges_enabled else "pending"
    updated = update_merchant_connect_status_by_account(account_id, status)
    if updated:
        logger.info("Connect status updated to %s for account %s", status, account_id)
    else:
        logger.warning("No merchant found for Connect account %s", account_id)


def _handle_payment_failed(payment_intent: dict) -> None:
    """A PaymentIntent we created has failed (e.g., card declined async)."""
    pi_id = payment_intent.get("id", "")
    logger.warning("PaymentIntent failed: %s", pi_id)

    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE transactions SET stripe_status='failed' WHERE stripe_payment_intent_id={PH}",
            (pi_id,),
        )


def _handle_dispute_created(dispute: dict) -> None:
    """A charge has been disputed. Log for manual review."""
    charge_id = dispute.get("charge", "")
    amount = dispute.get("amount", 0)
    logger.warning(
        "DISPUTE created: charge=%s amount=%d cents. Manual review required.",
        charge_id,
        amount,
    )


def _handle_charge_refunded(charge: dict) -> None:
    """A charge was refunded (full or partial)."""
    pi_id = charge.get("payment_intent", "")
    if not pi_id:
        return

    refunded = charge.get("refunded", False)
    new_status = "refunded" if refunded else "partially_refunded"
    logger.info("Charge refunded: pi=%s status=%s", pi_id, new_status)

    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE transactions SET stripe_status={PH} WHERE stripe_payment_intent_id={PH}",
            (new_status, pi_id),
        )
