"""
FingerPay — Token & Verification Code Queries
================================================
Password reset tokens and customer verification codes.
"""

from datetime import UTC, datetime

from app.db.connection import PH, _fetchone, _get_conn

# ── Password Reset Tokens ───────────────────────────────────────────────────


def create_reset_token(merchant_id: int, token: str, expires_at: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE password_reset_tokens SET used=1 WHERE merchant_id={PH} AND used=0
        """,
            (merchant_id,),
        )
        c.execute(
            f"""
            INSERT INTO password_reset_tokens (token, merchant_id, expires_at) VALUES ({PH}, {PH}, {PH})
        """,
            (token, merchant_id, expires_at),
        )


def get_reset_token(token: str) -> dict | None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM password_reset_tokens WHERE token={PH} AND used=0", (token,))
        return _fetchone(c)


def consume_reset_token(token: str, new_password_hash: str) -> bool:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM password_reset_tokens WHERE token={PH} AND used=0", (token,))
        row = _fetchone(c)
        if not row:
            return False
        now = datetime.now(UTC).isoformat()
        if row["expires_at"] < now:
            return False
        c.execute(f"UPDATE password_reset_tokens SET used=1 WHERE token={PH}", (token,))
        c.execute(
            f"UPDATE merchants SET password_hash={PH} WHERE id={PH}",
            (new_password_hash, row["merchant_id"]),
        )
        return True


# ── Customer Verification Codes ─────────────────────────────────────────────


def create_customer_verification_code(email: str, code: str, expires_at: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE customer_verification_codes SET used=1 WHERE email={PH} AND used=0", (email,)
        )
        c.execute(
            f"""
            INSERT INTO customer_verification_codes (email, code, expires_at)
            VALUES ({PH}, {PH}, {PH})
        """,
            (email, code, expires_at),
        )


def verify_customer_code(email: str, code: str, consume: bool = False) -> bool:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(
            f"""
            SELECT * FROM customer_verification_codes
            WHERE email={PH} AND code={PH} AND used=0
        """,
            (email, code),
        )
        row = _fetchone(c)
        if not row:
            return False
        if row["expires_at"] < datetime.now(UTC).isoformat():
            return False
        if consume:
            c.execute(
                f"UPDATE customer_verification_codes SET used=1 WHERE email={PH} AND code={PH}",
                (email, code),
            )
        return True
