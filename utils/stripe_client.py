"""
FingerPay — Stripe Utilities
=============================
Wraps Stripe API calls for customer creation and payment processing.
"""

import os
import uuid
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


def create_customer(full_name: str, email: str, payment_method_id: str) -> str:
    """
    Create a Stripe Customer, attach their payment method, and confirm it
    for future off-session charges via a SetupIntent.
    Returns the Stripe customer_id.
    """
    customer = stripe.Customer.create(
        name=full_name,
        email=email,
        payment_method=payment_method_id,
        invoice_settings={"default_payment_method": payment_method_id},
    )

    # Confirm the card for future off-session use (required for /pay)
    stripe.SetupIntent.create(
        customer=customer.id,
        payment_method=payment_method_id,
        usage="off_session",
        confirm=True,
        automatic_payment_methods={
            "enabled": True,
            "allow_redirects": "never",
        },
    )

    return customer.id


def charge_customer(
    stripe_customer_id: str,
    stripe_payment_method_id: str,
    amount_usd: float,
    merchant: str,
) -> dict:
    """
    Charge a saved customer off-session (no phone/card present).
    amount_usd is in dollars (e.g. 12.50).
    Returns the PaymentIntent object as a dict.
    """
    intent = stripe.PaymentIntent.create(
        amount=round(amount_usd * 100),  # Stripe uses cents
        currency="usd",
        customer=stripe_customer_id,
        payment_method=stripe_payment_method_id,
        confirm=True,
        off_session=True,  # terminal charge — no customer interaction
        description=f"FingerPay purchase at {merchant}",
        idempotency_key=str(uuid.uuid4()),  # prevents double charges on retries
    )
    return {
        "stripe_payment_intent_id": intent.id,
        "status": intent.status,
        "amount": amount_usd,
        "merchant": merchant,
    }
