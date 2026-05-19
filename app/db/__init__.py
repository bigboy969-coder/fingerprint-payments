"""
FingerPay — Database Package
==============================
Public API re-exported here so callers can do:
    from app.db import enroll_user, find_user_by_fingerprint, ...
"""

from app.db.merchants import (
    create_merchant,
    get_merchant_by_api_key_hash,
    get_merchant_by_billing_customer_id,
    get_merchant_by_email,
    get_merchant_by_id,
    get_merchant_customers,
    update_merchant_api_key,
    update_merchant_billing,
    update_merchant_connect,
    update_merchant_connect_status_by_account,
    update_merchant_monthly_fee_month,
)
from app.db.schema import init_db
from app.db.sessions import (
    complete_session,
    create_session,
    get_session,
    save_session_form,
)
from app.db.tokens import (
    consume_reset_token,
    create_customer_verification_code,
    create_reset_token,
    get_reset_token,
    verify_customer_code,
)
from app.db.transactions import (
    create_pending_transaction,
    get_merchant_recent_transactions,
    get_merchant_stats,
    record_transaction,
    update_transaction_result,
    update_transaction_status_by_stripe_pi,
)
from app.db.users import (
    check_email_exists,
    delete_customer_by_email,
    enroll_user,
    find_user_by_fingerprint,
    get_all_fingerprints,
    get_user_by_email,
    get_user_by_id,
)

__all__ = [
    "init_db",
    # users
    "enroll_user",
    "find_user_by_fingerprint",
    "get_all_fingerprints",
    "check_email_exists",
    "get_user_by_id",
    "get_user_by_email",
    "delete_customer_by_email",
    # sessions
    "create_session",
    "save_session_form",
    "get_session",
    "complete_session",
    # transactions
    "create_pending_transaction",
    "update_transaction_result",
    "update_transaction_status_by_stripe_pi",
    "record_transaction",
    "get_merchant_stats",
    "get_merchant_recent_transactions",
    # merchants
    "create_merchant",
    "get_merchant_by_email",
    "get_merchant_by_id",
    "get_merchant_by_api_key_hash",
    "update_merchant_connect",
    "update_merchant_connect_status_by_account",
    "update_merchant_api_key",
    "update_merchant_billing",
    "update_merchant_monthly_fee_month",
    "get_merchant_customers",
    "get_merchant_by_billing_customer_id",
    # tokens
    "create_reset_token",
    "get_reset_token",
    "consume_reset_token",
    "create_customer_verification_code",
    "verify_customer_code",
]
