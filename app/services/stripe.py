"""
FingerPay — Stripe Utilities
=============================
Wraps Stripe API calls for customer creation and payment processing.
"""

import uuid

import stripe

from app.config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY


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


MONTHLY_FEE = 99.00  # $99/month flat subscription — FingerPay's only revenue from merchants


def charge_customer(
    stripe_customer_id: str,
    stripe_payment_method_id: str,
    amount_usd: float,
    merchant: str,
    idempotency_key: str = None,
    stripe_connect_id: str = None,
) -> dict:
    """
    Charge a saved customer off-session (no phone/card present).
    amount_usd is in dollars (e.g. 12.50).
    idempotency_key should be stable per logical operation (e.g., tx row ID)
    so retries don't create duplicate charges.
    If stripe_connect_id is provided, the full amount is routed to the
    merchant's Connect account — FingerPay takes no per-transaction cut.
    Returns the PaymentIntent object as a dict.
    """
    params = dict(
        amount=round(amount_usd * 100),
        currency="usd",
        customer=stripe_customer_id,
        payment_method=stripe_payment_method_id,
        confirm=True,
        off_session=True,
        description=f"FingerPay purchase at {merchant}",
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )

    if stripe_connect_id:
        params["transfer_data"] = {"destination": stripe_connect_id}

    intent = stripe.PaymentIntent.create(**params)
    return {
        "stripe_payment_intent_id": intent.id,
        "status": intent.status,
        "amount": amount_usd,
        "merchant": merchant,
    }


def create_connect_account(email: str, business_name: str) -> str:
    """Create a Stripe Express account for a merchant. Returns the account ID."""
    account = stripe.Account.create(
        type="express",
        email=email,
        business_profile={"name": business_name},
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
    )
    return account.id


def create_onboarding_link(account_id: str, return_url: str, refresh_url: str) -> str:
    """Generate a Stripe Connect onboarding URL for a merchant. Returns the URL."""
    link = stripe.AccountLink.create(
        account=account_id,
        return_url=return_url,
        refresh_url=refresh_url,
        type="account_onboarding",
    )
    return link.url


def get_connect_account_status(account_id: str) -> str:
    """Returns 'active' if merchant has completed onboarding, else 'pending'."""
    account = stripe.Account.retrieve(account_id)
    if account.details_submitted and account.charges_enabled:
        return "active"
    return "pending"
