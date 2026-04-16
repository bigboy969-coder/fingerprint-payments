"""
FingerPay — Merchant Queries
==============================
"""

from datetime import datetime, timezone

from app.config import DATABASE_URL
from app.db.connection import _get_conn, _fetchone, _fetchall, PH


def create_merchant(business_name: str, name: str, email: str, password_hash: str, api_key_hash: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            INSERT INTO merchants (business_name, name, email, password_hash, api_key_hash, created_at)
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH})
        """, (business_name, name, email, password_hash, api_key_hash, now))
        c.execute(f"SELECT * FROM merchants WHERE email = {PH}", (email,))
        return _fetchone(c)


def get_merchant_by_email(email: str) -> dict | None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM merchants WHERE email = {PH}", (email,))
        return _fetchone(c)


def get_merchant_by_id(merchant_id: int) -> dict | None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM merchants WHERE id = {PH}", (merchant_id,))
        return _fetchone(c)


def get_merchant_by_api_key_hash(key_hash: str) -> dict | None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM merchants WHERE api_key_hash = {PH}", (key_hash,))
        return _fetchone(c)


def update_merchant_connect(merchant_id: int, stripe_connect_id: str, status: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            UPDATE merchants SET stripe_connect_id={PH}, stripe_connect_status={PH} WHERE id={PH}
        """, (stripe_connect_id, status, merchant_id))


def update_merchant_connect_status_by_account(stripe_account_id: str, status: str) -> bool:
    """Update connect status by Stripe account ID. Returns True if a row was updated."""
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE merchants SET stripe_connect_status={PH} WHERE stripe_connect_id={PH}",
            (status, stripe_account_id),
        )
        return c.rowcount > 0 if hasattr(c, "rowcount") else True


def update_merchant_api_key(merchant_id: int, api_key_hash: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE merchants SET api_key_hash={PH} WHERE id={PH}", (api_key_hash, merchant_id))


def update_merchant_monthly_fee_month(merchant_id: int, month: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE merchants SET last_monthly_fee_month={PH} WHERE id={PH}", (month, merchant_id))


def get_merchant_customers(merchant_id: int, limit: int = 50, offset: int = 0) -> list:
    """Return distinct customers who have transacted with this merchant."""
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            SELECT
                u.id,
                u.full_name,
                u.email,
                u.phone,
                u.enrolled_at,
                COUNT(t.id)   as total_transactions,
                COALESCE(SUM(t.amount), 0) as total_spent,
                MAX(t.created_at) as last_transaction
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.merchant_id = {PH}
            GROUP BY u.id, u.full_name, u.email, u.phone, u.enrolled_at
            ORDER BY last_transaction DESC
            LIMIT {PH} OFFSET {PH}
        """, (merchant_id, limit, offset))
        return _fetchall(c)
