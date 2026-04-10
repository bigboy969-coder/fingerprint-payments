"""
FingerPay — Database Layer
===========================
Handles all PostgreSQL storage for users, fingerprints, and transactions.
Falls back to SQLite when DATABASE_URL is not set (local dev only).
"""

import os
from datetime import datetime
from contextlib import contextmanager

from pipeline.extractor import desc_to_blob, blob_to_desc, match_score, MATCH_THRESHOLD
from utils.crypto import encrypt_descriptor, decrypt_descriptor

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Connection ─────────────────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2

    @contextmanager
    def _get_conn():
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _fetchone(cursor):
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def _fetchall(cursor):
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    PH = "%s"   # PostgreSQL placeholder

else:
    # ── SQLite fallback for local dev ─────────────────────────────────────────
    import sqlite3
    from pathlib import Path

    _DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent))
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = _DATA_DIR / "fingerpay.db"

    @contextmanager
    def _get_conn():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _fetchone(cursor):
        row = cursor.fetchone()
        return dict(row) if row else None

    def _fetchall(cursor):
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    PH = "?"    # SQLite placeholder


# ── Setup ─────────────────────────────────────────────────────────────────────
def init_db():
    with _get_conn() as conn:
        c = conn.cursor()

        if DATABASE_URL:
            # PostgreSQL
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                        SERIAL PRIMARY KEY,
                    full_name                 TEXT    NOT NULL,
                    email                     TEXT    NOT NULL UNIQUE,
                    phone                     TEXT,
                    stripe_customer_id        TEXT,
                    stripe_payment_method_id  TEXT,
                    enrolled_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    descriptor  BYTEA   NOT NULL,
                    enrolled_at TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id                       SERIAL PRIMARY KEY,
                    user_id                  INTEGER NOT NULL,
                    amount                   REAL    NOT NULL,
                    merchant                 TEXT    NOT NULL,
                    stripe_payment_intent_id TEXT,
                    stripe_status            TEXT,
                    merchant_id              INTEGER,
                    platform_fee             REAL    DEFAULT 0,
                    balance_after            REAL    DEFAULT 0,
                    created_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS merchants (
                    id                     SERIAL PRIMARY KEY,
                    business_name          TEXT    NOT NULL,
                    name                   TEXT    NOT NULL,
                    email                  TEXT    NOT NULL UNIQUE,
                    password_hash          TEXT    NOT NULL,
                    api_key_hash           TEXT,
                    stripe_connect_id      TEXT,
                    stripe_connect_status  TEXT    DEFAULT 'pending',
                    last_monthly_fee_month TEXT,
                    is_active              INTEGER DEFAULT 1,
                    created_at             TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS enrollment_sessions (
                    session_id               TEXT    PRIMARY KEY,
                    full_name                TEXT,
                    email                    TEXT,
                    phone                    TEXT,
                    stripe_customer_id       TEXT,
                    stripe_payment_method_id TEXT,
                    user_id                  INTEGER,
                    status                   TEXT    NOT NULL DEFAULT 'pending_form',
                    created_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token       TEXT    PRIMARY KEY,
                    merchant_id INTEGER NOT NULL,
                    expires_at  TEXT    NOT NULL,
                    used        INTEGER DEFAULT 0
                )
            """)

        else:
            # SQLite — original schema
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name                 TEXT    NOT NULL,
                    email                     TEXT    NOT NULL UNIQUE,
                    phone                     TEXT,
                    stripe_customer_id        TEXT,
                    stripe_payment_method_id  TEXT,
                    enrolled_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    descriptor  BLOB    NOT NULL,
                    enrolled_at TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id                  INTEGER NOT NULL,
                    amount                   REAL    NOT NULL,
                    merchant                 TEXT    NOT NULL,
                    stripe_payment_intent_id TEXT,
                    stripe_status            TEXT,
                    merchant_id              INTEGER,
                    platform_fee             REAL    DEFAULT 0,
                    balance_after            REAL    DEFAULT 0,
                    created_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS merchants (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name          TEXT    NOT NULL,
                    name                   TEXT    NOT NULL,
                    email                  TEXT    NOT NULL UNIQUE,
                    password_hash          TEXT    NOT NULL,
                    api_key_hash           TEXT,
                    stripe_connect_id      TEXT,
                    stripe_connect_status  TEXT    DEFAULT 'pending',
                    last_monthly_fee_month TEXT,
                    is_active              INTEGER DEFAULT 1,
                    created_at             TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS enrollment_sessions (
                    session_id               TEXT    PRIMARY KEY,
                    full_name                TEXT,
                    email                    TEXT,
                    phone                    TEXT,
                    stripe_customer_id       TEXT,
                    stripe_payment_method_id TEXT,
                    user_id                  INTEGER,
                    status                   TEXT    NOT NULL DEFAULT 'pending_form',
                    created_at               TEXT    NOT NULL
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token       TEXT    PRIMARY KEY,
                    merchant_id INTEGER NOT NULL,
                    expires_at  TEXT    NOT NULL,
                    used        INTEGER DEFAULT 0
                )
            """)

            # Safe migrations
            for col, typ in [
                ("stripe_customer_id", "TEXT"),
                ("stripe_payment_method_id", "TEXT"),
            ]:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
                except Exception:
                    pass

            for col, typ in [
                ("stripe_payment_intent_id", "TEXT"),
                ("stripe_status", "TEXT"),
                ("merchant_id", "INTEGER"),
                ("platform_fee", "REAL"),
                ("balance_after", "REAL"),
            ]:
                try:
                    c.execute(f"ALTER TABLE transactions ADD COLUMN {col} {typ}")
                except Exception:
                    pass

            for col, typ in [
                ("business_name", "TEXT"),
                ("password_hash", "TEXT"),
                ("stripe_connect_id", "TEXT"),
                ("stripe_connect_status", "TEXT"),
                ("last_monthly_fee_month", "TEXT"),
                ("is_active", "INTEGER"),
            ]:
                try:
                    c.execute(f"ALTER TABLE merchants ADD COLUMN {col} {typ}")
                except Exception:
                    pass

            try:
                c.execute("ALTER TABLE enrollment_sessions ADD COLUMN user_id INTEGER")
            except Exception:
                pass


# ── Enroll ────────────────────────────────────────────────────────────────────
def enroll_user(
    full_name: str,
    email: str,
    phone: str,
    descriptor,
    stripe_customer_id: str,
    stripe_payment_method_id: str,
) -> dict:
    now = datetime.now().isoformat()

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
        if DATABASE_URL:
            c.execute(
                "INSERT INTO fingerprints (user_id, descriptor, enrolled_at) VALUES (%s, %s, %s)",
                (user_id, psycopg2.Binary(encrypted), now)
            )
        else:
            c.execute(
                "INSERT INTO fingerprints (user_id, descriptor, enrolled_at) VALUES (?, ?, ?)",
                (user_id, encrypted, now)
            )

        c.execute(f"SELECT * FROM users WHERE id = {PH}", (user_id,))
        return _fetchone(c)


# ── Find user by fingerprint ──────────────────────────────────────────────────
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


# ── Check email ───────────────────────────────────────────────────────────────
def check_email_exists(email: str) -> bool:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT id FROM users WHERE email = {PH}", (email,))
        return _fetchone(c) is not None


# ── Get user by ID ────────────────────────────────────────────────────────────
def get_user_by_id(user_id: int) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM users WHERE id = {PH}", (user_id,))
        row = _fetchone(c)
    if row is None:
        raise ValueError(f"User {user_id} not found.")
    return row


# ── Enrollment Sessions ───────────────────────────────────────────────────────
def create_session(session_id: str) -> dict:
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            INSERT INTO enrollment_sessions (session_id, status, created_at)
            VALUES ({PH}, 'pending_form', {PH})
        """, (session_id, now))
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
        c.execute(f"""
            UPDATE enrollment_sessions
            SET full_name={PH}, email={PH}, phone={PH}, stripe_customer_id={PH},
                stripe_payment_method_id={PH}, status='pending_scan'
            WHERE session_id={PH}
        """, (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, session_id))
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
        c.execute(f"""
            UPDATE enrollment_sessions SET status='complete', user_id={PH} WHERE session_id={PH}
        """, (user_id, session_id))


# ── Transactions ──────────────────────────────────────────────────────────────
def record_transaction(
    user_id: int,
    amount: float,
    merchant: str,
    stripe_payment_intent_id: str,
    stripe_status: str,
    merchant_id: int = None,
    platform_fee: float = 0.0,
) -> dict:
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        if DATABASE_URL:
            c.execute("""
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s) RETURNING id
            """, (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, merchant_id, platform_fee, now))
            tx_id = c.fetchone()[0]
        else:
            c.execute("""
                INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, merchant_id, platform_fee, now))
            tx_id = c.lastrowid
        c.execute(f"SELECT * FROM transactions WHERE id = {PH}", (tx_id,))
        return _fetchone(c)


# ── Merchants ─────────────────────────────────────────────────────────────────
def create_merchant(business_name: str, name: str, email: str, password_hash: str, api_key_hash: str) -> dict:
    now = datetime.now().isoformat()
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


def update_merchant_api_key(merchant_id: int, api_key_hash: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE merchants SET api_key_hash={PH} WHERE id={PH}", (api_key_hash, merchant_id))


def update_merchant_monthly_fee_month(merchant_id: int, month: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE merchants SET last_monthly_fee_month={PH} WHERE id={PH}", (month, merchant_id))


def get_merchant_stats(merchant_id: int) -> dict:
    with _get_conn() as conn:
        c = conn.cursor()
        current_month = datetime.now().strftime("%Y-%m")
        if DATABASE_URL:
            c.execute("""
                SELECT
                    COUNT(*) as tx_count,
                    COALESCE(SUM(amount), 0) as total_processed,
                    COALESCE(SUM(platform_fee), 0) as total_fees
                FROM transactions
                WHERE merchant_id = %s AND LEFT(created_at, 7) = %s
            """, (merchant_id, current_month))
        else:
            c.execute("""
                SELECT
                    COUNT(*) as tx_count,
                    COALESCE(SUM(amount), 0) as total_processed,
                    COALESCE(SUM(platform_fee), 0) as total_fees
                FROM transactions
                WHERE merchant_id = ? AND strftime('%Y-%m', created_at) = ?
            """, (merchant_id, current_month))
        row = _fetchone(c)
        return row if row else {"tx_count": 0, "total_processed": 0.0, "total_fees": 0.0}


def get_merchant_recent_transactions(merchant_id: int, limit: int = 10) -> list:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            SELECT t.id, t.amount, t.platform_fee, t.stripe_status, t.created_at,
                   u.full_name as customer_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.merchant_id = {PH}
            ORDER BY t.created_at DESC
            LIMIT {PH}
        """, (merchant_id, limit))
        return _fetchall(c)


# ── Password Reset Tokens ─────────────────────────────────────────────────────
def create_reset_token(merchant_id: int, token: str, expires_at: str) -> None:
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"""
            UPDATE password_reset_tokens SET used=1 WHERE merchant_id={PH} AND used=0
        """, (merchant_id,))
        c.execute(f"""
            INSERT INTO password_reset_tokens (token, merchant_id, expires_at) VALUES ({PH}, {PH}, {PH})
        """, (token, merchant_id, expires_at))


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
        now = datetime.utcnow().isoformat()
        if row["expires_at"] < now:
            return False
        c.execute(f"UPDATE password_reset_tokens SET used=1 WHERE token={PH}", (token,))
        c.execute(f"UPDATE merchants SET password_hash={PH} WHERE id={PH}", (new_password_hash, row["merchant_id"]))
        return True
