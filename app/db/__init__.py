"""
FingerPay — Database Package
==============================
Public API re-exported here so callers can do:
    from app.db import enroll_user, find_user_by_fingerprint, ...
"""

from app.db.schema import init_db

from app.db.users import (
    enroll_user,
    find_user_by_fingerprint,
    check_email_exists,
    get_user_by_id,
    get_user_by_email,
    delete_customer_by_email,
)

from app.db.sessions import (
    create_session,
    save_session_form,
    get_session,
    complete_session,
)

from app.db.transactions import (
    create_pending_transaction,
    update_transaction_result,
    record_transaction,
    get_merchant_stats,
    get_merchant_recent_transactions,
)

from app.db.merchants import (
    create_merchant,
    get_merchant_by_email,
    get_merchant_by_id,
    get_merchant_by_api_key_hash,
    update_merchant_connect,
    update_merchant_connect_status_by_account,
    update_merchant_api_key,
    update_merchant_monthly_fee_month,
    get_merchant_customers,
)

from app.db.tokens import (
    create_reset_token,
    get_reset_token,
    consume_reset_token,
    create_customer_verification_code,
    verify_customer_code,
)

__all__ = [
    "init_db",
    # users
    "enroll_user",
    "find_user_by_fingerprint",
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
    "update_merchant_monthly_fee_month",
    "get_merchant_customers",
    # tokens
    "create_reset_token",
    "get_reset_token",
    "consume_reset_token",
    "create_customer_verification_code",
    "verify_customer_code",
]
