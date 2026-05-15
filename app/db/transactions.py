"""
FingerPay — Transaction Queries
=================================
"""

from datetime import UTC, datetime

from app.config import DATABASE_URL
from app.db.connection import PH, _fetchall, _fetchone, _get_conn


def create_pending_transaction(
    user_id: int,
    amount: float,
    merchant: str,
    merchant_id: int = None,
) -> dict:
    """Insert a transaction row with status='pending' BEFORE calling Stripe.
    This ensures a DB record exists even if the Stripe call succeeds but the
    subsequent update fails."""
    now = datetime.now(UTC).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        if DATABASE_URL:
            c.execute(
                """
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, 0, %s) RETURNING id
            """,
                (user_id, amount, merchant, None, "pending", merchant_id, now),
            )
            tx_id = c.fetchone()[0]
        else:
            c.execute(
                """
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?)
            """,
                (user_id, amount, merchant, None, "pending", merchant_id, now),
            )
            tx_id = c.lastrowid
        c.execute(f"SELECT * FROM transactions WHERE id = {PH}", (tx_id,))
        return _fetchone(c)


def update_transaction_result(
    transaction_id: int,
    stripe_payment_intent_id: str,
    stripe_status: str,
) -> dict:
    """Update a pending transaction with the Stripe result."""
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE transactions
            SET stripe_payment_intent_id={PH}, stripe_status={PH}
            WHERE id={PH}
        """,
            (stripe_payment_intent_id, stripe_status, transaction_id),
        )
        c.execute(f"SELECT * FROM transactions WHERE id = {PH}", (transaction_id,))
        return _fetchone(c)


def record_transaction(
    user_id: int,
    amount: float,
    merchant: str,
    stripe_payment_intent_id: str,
    stripe_status: str,
    merchant_id: int = None,
) -> dict:
    """Legacy single-step insert. Prefer create_pending + update_transaction_result."""
    now = datetime.now(UTC).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        if DATABASE_URL:
            c.execute(
                """
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, 0, %s) RETURNING id
            """,
                (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, merchant_id, now),
            )
            tx_id = c.fetchone()[0]
        else:
            c.execute(
                """
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?)
            """,
                (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, merchant_id, now),
            )
            tx_id = c.lastrowid
        c.execute(f"SELECT * FROM transactions WHERE id = {PH}", (tx_id,))
        return _fetchone(c)


def get_merchant_stats(merchant_id: int) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        current_month = datetime.now(UTC).strftime("%Y-%m")
        if DATABASE_URL:
            c.execute(
                """
                SELECT
                    COUNT(*) as tx_count,
                    COALESCE(SUM(amount), 0) as total_processed
                FROM transactions
                WHERE merchant_id = %s AND LEFT(created_at, 7) = %s
            """,
                (merchant_id, current_month),
            )
        else:
            c.execute(
                """
                SELECT
                    COUNT(*) as tx_count,
                    COALESCE(SUM(amount), 0) as total_processed
                FROM transactions
                WHERE merchant_id = ? AND strftime('%Y-%m', created_at) = ?
            """,
                (merchant_id, current_month),
            )
        row = _fetchone(c)
        return row if row else {"tx_count": 0, "total_processed": 0.0}


def get_merchant_recent_transactions(merchant_id: int, limit: int = 20, offset: int = 0) -> list:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            SELECT t.id, t.amount, t.stripe_status, t.created_at,
                   u.full_name as customer_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.merchant_id = {PH}
            ORDER BY t.created_at DESC
            LIMIT {PH} OFFSET {PH}
        """,
            (merchant_id, limit, offset),
        )
        return _fetchall(c)
