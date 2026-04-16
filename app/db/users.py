"""
FingerPay — User & Fingerprint Queries
========================================
"""

from datetime import datetime, timezone

from app.config import DATABASE_URL
from app.db.connection import _get_conn, _fetchone, _fetchall, PH, binary_wrap
from app.services.crypto import encrypt_descriptor, decrypt_descriptor
from app.services.biometrics import desc_to_blob, blob_to_desc, match_score, MATCH_THRESHOLD


def enroll_user(
    full_name: str,
    email: str,
    phone: str,
    descriptor,
    stripe_customer_id: str,
    stripe_payment_method_id: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    with _get_conn() as conn:
        c = conn.cursor()

        c.execute(f"SELECT id FROM users WHERE email = {PH}", (email,))
        if _fetchone(c):
            raise ValueError(f"User with email {email} already enrolled.")

        if DATABASE_URL:
            c.execute("""
                INSERT INTO users (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, enrolled_at)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, now))
            user_id = c.fetchone()[0]
        else:
            c.execute("""
                INSERT INTO users (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, enrolled_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, now))
            user_id = c.lastrowid

        encrypted = encrypt_descriptor(desc_to_blob(descriptor))
        c.execute(
            f"INSERT INTO fingerprints (user_id, descriptor, enrolled_at) VALUES ({PH}, {PH}, {PH})",
            (user_id, binary_wrap(encrypted), now),
        )

        c.execute(f"SELECT * FROM users WHERE id = {PH}", (user_id,))
        return _fetchone(c)


def find_user_by_fingerprint(probe) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, descriptor FROM fingerprints")
        rows = _fetchall(c)

    best_id = None
    best_score = 0

    for row in rows:
        raw = bytes(row["descriptor"])
        score = match_score(probe, blob_to_desc(decrypt_descriptor(raw)))
        if score > best_score:
            best_score = score
            best_id = row["user_id"]

    matched = best_score >= MATCH_THRESHOLD

    if matched and best_id:
        with _get_conn() as conn:
            c = conn.cursor()
            c.execute(f"SELECT * FROM users WHERE id = {PH}", (best_id,))
            row = _fetchone(c)
        return {"matched": True, "score": best_score, "user": row}

    return {"matched": False, "score": best_score, "user": None}


def check_email_exists(email: str) -> bool:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT id FROM users WHERE email = {PH}", (email,))
        return _fetchone(c) is not None


def get_user_by_id(user_id: int) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM users WHERE id = {PH}", (user_id,))
        row = _fetchone(c)
    if row is None:
        raise ValueError(f"User {user_id} not found.")
    return row


def get_user_by_email(email: str) -> dict | None:
    """Return user dict or None. Public alternative to raw SQL in routes."""
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM users WHERE email = {PH}", (email,))
        return _fetchone(c)


def delete_customer_by_email(email: str) -> bool:
    """Delete all customer data — user record, fingerprints, and transactions."""
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT id, stripe_customer_id FROM users WHERE email={PH}", (email,))
        user = _fetchone(c)
        if not user:
            return False
        user_id = user["id"]
        c.execute(f"DELETE FROM fingerprints WHERE user_id={PH}", (user_id,))
        c.execute(f"DELETE FROM transactions WHERE user_id={PH}", (user_id,))
        c.execute(f"DELETE FROM users WHERE id={PH}", (user_id,))
        return True
