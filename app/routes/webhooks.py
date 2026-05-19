"""
FingerPay — Stripe Webhook Handler
=====================================
POST /webhooks/stripe

Handles inbound Stripe events with signature verification.
Events handled:
  - payment_intent.succeeded         → mark transaction succeeded (async payments)
  - payment_intent.payment_failed    → mark transaction failed
  - account.updated                  → refresh Connect status
  - account.application.deauthorized → mark merchant Connect as deauthorized
  - charge.dispute.created           → log warning for manual review
  - charge.refunded                  → update transaction status
"""

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request

from app.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from app.db import (
    update_merchant_connect_status_by_account,
    update_transaction_status_by_stripe_pi,
)

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
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        _handle_payment_succeeded(data)
    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(data)
    elif event_type == "account.updated":
        _handle_account_updated(data)
    elif event_type == "account.application.deauthorized":
        # account ID is at the event level, not in data.object (which is the Application)
        _handle_account_deauthorized(event.get("account", ""))
    elif event_type == "charge.dispute.created":
        _handle_dispute_created(data)
    elif event_type == "charge.refunded":
        _handle_charge_refunded(data)
    else:
        logger.info("Unhandled webhook event: %s", event_type)

    return {"received": True}


def _handle_payment_succeeded(payment_intent: dict) -> None:
    """A PaymentIntent succeeded asynchronously (e.g. after 3DS or delayed confirmation)."""
    pi_id = payment_intent.get("id", "")
    updated = update_transaction_status_by_stripe_pi(pi_id, "succeeded")
    if updated:
        logger.info("PaymentIntent succeeded (async): %s", pi_id)
    else:
        # Normal for PaymentIntents created outside FingerPay (e.g. Stripe test events)
        logger.info("PaymentIntent %s succeeded but no matching local transaction", pi_id)


def _handle_payment_failed(payment_intent: dict) -> None:
    """A PaymentIntent failed (e.g. card declined asynchronously)."""
    pi_id = payment_intent.get("id", "")
    updated = update_transaction_status_by_stripe_pi(pi_id, "failed")
    logger.warning("PaymentIntent failed: pi=%s matched_local=%s", pi_id, updated)


def _handle_account_updated(account: dict) -> None:
    """Stripe Connect account details or capabilities changed."""
    account_id = account.get("id", "")
    details_submitted = account.get("details_submitted", False)
    charges_enabled = account.get("charges_enabled", False)

    status = "active" if details_submitted and charges_enabled else "pending"
    updated = update_merchant_connect_status_by_account(account_id, status)
    if updated:
        logger.info("Connect status updated to %s for account %s", status, account_id)
    else:
        logger.info("No merchant found for Connect account %s (possibly external)", account_id)


def _handle_account_deauthorized(account_id: str) -> None:
    """Merchant disconnected their Stripe account from FingerPay."""
    if not account_id:
        logger.warning("account.application.deauthorized received with no account ID")
        return
    updated = update_merchant_connect_status_by_account(account_id, "deauthorized")
    if updated:
        logger.warning(
            "Connect account %s deauthorized — merchant can no longer receive payouts",
            account_id,
        )
    else:
        logger.warning("No merchant found for deauthorized account %s", account_id)


def _handle_dispute_created(dispute: dict) -> None:
    """A charge has been disputed — requires manual review."""
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
    updated = update_transaction_status_by_stripe_pi(pi_id, new_status)
    logger.info("Charge refunded: pi=%s status=%s matched_local=%s", pi_id, new_status, updated)
