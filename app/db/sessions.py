"""
FingerPay — Enrollment Session Queries
========================================
"""

from datetime import UTC, datetime

from app.db.connection import PH, _fetchone, _get_conn


def create_session(session_id: str) -> dict:
    now = datetime.now(UTC).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            INSERT INTO enrollment_sessions (session_id, status, created_at)
            VALUES ({PH}, 'pending_form', {PH})
        """,
            (session_id, now),
        )
        c.execute(f"SELECT * FROM enrollment_sessions WHERE session_id = {PH}", (session_id,))
        return _fetchone(c)


def save_session_form(
    session_id: str,
    full_name: str,
    email: str,
    phone: str,
    stripe_customer_id: str,
    stripe_payment_method_id: str,
) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE enrollment_sessions
            SET full_name={PH}, email={PH}, phone={PH}, stripe_customer_id={PH},
                stripe_payment_method_id={PH}, status='pending_scan'
            WHERE session_id={PH}
        """,
            (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, session_id),
        )
        c.execute(f"SELECT * FROM enrollment_sessions WHERE session_id = {PH}", (session_id,))
        row = _fetchone(c)
    if row is None:
        raise ValueError("Session not found.")
    return row


def get_session(session_id: str) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM enrollment_sessions WHERE session_id = {PH}", (session_id,))
        row = _fetchone(c)
    if row is None:
        raise ValueError("Session not found.")
    return row


def complete_session(session_id: str, user_id: int) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE enrollment_sessions SET status='complete', user_id={PH} WHERE session_id={PH}
        """,
            (user_id, session_id),
        )
