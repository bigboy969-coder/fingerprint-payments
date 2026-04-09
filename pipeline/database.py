"""
FingerPay — Database Layer
===========================
Handles all SQLite storage for users, fingerprints, and transactions.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from pipeline.extractor import desc_to_blob, blob_to_desc, match_score, MATCH_THRESHOLD
from utils.crypto import encrypt_descriptor, decrypt_descriptor


# ── Config ────────────────────────────────────────────────────────────────────
import os as _os
_DATA_DIR = Path(_os.environ.get("DATA_DIR", Path(__file__).parent.parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH           = _DATA_DIR / "fingerpay.db"   # identity + payments
BIOMETRIC_DB_PATH = _DATA_DIR / "biometric.db"   # fingerprints only


# ── Setup ─────────────────────────────────────────────────────────────────────
def init_db():
    """Create tables and run safe schema migrations."""

    # ── Identity + payments DB ────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

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
        CREATE TABLE IF NOT EXISTS transactions (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                  INTEGER NOT NULL REFERENCES users(id),
            amount                   REAL    NOT NULL,
            merchant                 TEXT    NOT NULL,
            stripe_payment_intent_id TEXT,
            stripe_status            TEXT,
            created_at               TEXT    NOT NULL
        )
    """)

    conn.commit()

    # Safe migrations for existing databases
    _safe_add_column(c, "users", "stripe_customer_id", "TEXT")
    _safe_add_column(c, "users", "stripe_payment_method_id", "TEXT")
    _safe_add_column(c, "transactions", "stripe_payment_intent_id", "TEXT")
    _safe_add_column(c, "transactions", "stripe_status", "TEXT")
    _safe_add_column(c, "enrollment_sessions", "user_id", "INTEGER")

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

    # Migrations for existing merchants table
    _safe_add_column(c, "merchants", "business_name", "TEXT")
    _safe_add_column(c, "merchants", "password_hash", "TEXT")
    _safe_add_column(c, "merchants", "stripe_connect_id", "TEXT")
    _safe_add_column(c, "merchants", "stripe_connect_status", "TEXT")
    _safe_add_column(c, "merchants", "last_monthly_fee_month", "TEXT")
    _safe_add_column(c, "merchants", "is_active", "INTEGER")

    # Add merchant_id and platform_fee to transactions
    _safe_add_column(c, "transactions", "merchant_id", "INTEGER")
    _safe_add_column(c, "transactions", "platform_fee", "REAL")

    c.execute("""
        CREATE TABLE IF NOT EXISTS enrollment_sessions (
            session_id               TEXT    PRIMARY KEY,
            full_name                TEXT,
            email                    TEXT,
            phone                    TEXT,
            stripe_customer_id       TEXT,
            stripe_payment_method_id TEXT,
            status                   TEXT    NOT NULL DEFAULT 'pending_form',
            created_at               TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    # ── Biometric DB (separate file — encrypted fingerprints only) ────────────
    bio_conn = sqlite3.connect(BIOMETRIC_DB_PATH)
    bio_conn.execute("""
        CREATE TABLE IF NOT EXISTS fingerprints (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            descriptor  BLOB    NOT NULL,
            enrolled_at TEXT    NOT NULL
        )
    """)
    bio_conn.commit()
    bio_conn.close()


def _safe_add_column(cursor, table: str, column: str, col_type: str):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # Column already exists


# ── Enroll ────────────────────────────────────────────────────────────────────
def enroll_user(
    full_name: str,
    email: str,
    phone: str,
    descriptor,
    stripe_customer_id: str,
    stripe_payment_method_id: str,
) -> dict:
    """
    Save a new user and their fingerprint to the database.
    Returns the created user record.
    """
    now = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    existing = c.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()

    if existing:
        conn.close()
        raise ValueError(f"User with email {email} already enrolled.")

    c.execute("""
        INSERT INTO users (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, enrolled_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, now))

    user_id = c.lastrowid

    bio_conn = sqlite3.connect(BIOMETRIC_DB_PATH)
    bio_conn.execute("""
        INSERT INTO fingerprints (user_id, descriptor, enrolled_at)
        VALUES (?, ?, ?)
    """, (user_id, encrypt_descriptor(desc_to_blob(descriptor)), now))
    bio_conn.commit()
    bio_conn.close()

    conn.commit()

    row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return _row_to_dict(row)


# ── Find user by fingerprint ──────────────────────────────────────────────────
def find_user_by_fingerprint(probe) -> dict:
    """
    Compare probe descriptor against all enrolled fingerprints.
    Reads from biometric DB, then fetches identity from identity DB.
    """
    bio_conn = sqlite3.connect(BIOMETRIC_DB_PATH)
    bio_conn.row_factory = sqlite3.Row
    try:
        rows = bio_conn.execute(
            "SELECT user_id, descriptor FROM fingerprints"
        ).fetchall()

        best_id = None
        best_score = 0

        for row in rows:
            score = match_score(probe, blob_to_desc(decrypt_descriptor(bytes(row["descriptor"]))))
            if score > best_score:
                best_score = score
                best_id = row["user_id"]

        matched = best_score >= MATCH_THRESHOLD
    finally:
        bio_conn.close()

    if matched and best_id:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (best_id,)
            ).fetchone()
            return {"matched": True, "score": best_score, "user": _row_to_dict(row)}
        finally:
            conn.close()

    return {"matched": False, "score": best_score, "user": None}


# ── Check email ───────────────────────────────────────────────────────────────
def check_email_exists(email: str) -> bool:
    """Return True if a user with this email is already enrolled."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ── Get user by ID ────────────────────────────────────────────────────────────
def get_user_by_id(user_id: int) -> dict:
    """Fetch a single user record by ID. Raises ValueError if not found."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"User {user_id} not found.")
        return _row_to_dict(row)
    finally:
        conn.close()


# ── Enrollment Sessions ───────────────────────────────────────────────────────
def create_session(session_id: str) -> dict:
    """Create a blank enrollment session for the kiosk QR code."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            INSERT INTO enrollment_sessions (session_id, status, created_at)
            VALUES (?, 'pending_form', ?)
        """, (session_id, now))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM enrollment_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def save_session_form(
    session_id: str,
    full_name: str,
    email: str,
    phone: str,
    stripe_customer_id: str,
    stripe_payment_method_id: str,
) -> dict:
    """Save customer form data to session after phone submission."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            UPDATE enrollment_sessions
            SET full_name=?, email=?, phone=?, stripe_customer_id=?,
                stripe_payment_method_id=?, status='pending_scan'
            WHERE session_id=?
        """, (full_name, email, phone, stripe_customer_id, stripe_payment_method_id, session_id))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM enrollment_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Session not found.")
        return dict(row)
    finally:
        conn.close()


def get_session(session_id: str) -> dict:
    """Fetch a session by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM enrollment_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Session not found.")
        return dict(row)
    finally:
        conn.close()


def complete_session(session_id: str, user_id: int) -> None:
    """Mark a session as complete after fingerprint scan, storing the enrolled user_id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE enrollment_sessions SET status='complete', user_id=? WHERE session_id=?",
            (user_id, session_id)
        )
        conn.commit()
    finally:
        conn.close()


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
    """
    Persist a completed Stripe transaction.
    Returns the saved transaction record as a dict.
    """
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            INSERT INTO transactions (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, balance_after, merchant_id, platform_fee, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (user_id, amount, merchant, stripe_payment_intent_id, stripe_status, merchant_id, platform_fee, now))
        conn.commit()
        tx_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ── Merchants ─────────────────────────────────────────────────────────────────
def create_merchant(business_name: str, name: str, email: str, password_hash: str, api_key_hash: str) -> dict:
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            INSERT INTO merchants (business_name, name, email, password_hash, api_key_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (business_name, name, email, password_hash, api_key_hash, now))
        conn.commit()
        row = conn.execute("SELECT * FROM merchants WHERE email = ?", (email,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_merchant_by_email(email: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM merchants WHERE email = ?", (email,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_merchant_by_id(merchant_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_merchant_by_api_key_hash(key_hash: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM merchants WHERE api_key_hash = ?", (key_hash,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_merchant_connect(merchant_id: int, stripe_connect_id: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE merchants SET stripe_connect_id=?, stripe_connect_status=? WHERE id=?",
            (stripe_connect_id, status, merchant_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_merchant_api_key(merchant_id: int, api_key_hash: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE merchants SET api_key_hash=? WHERE id=?", (api_key_hash, merchant_id))
        conn.commit()
    finally:
        conn.close()


def update_merchant_monthly_fee_month(merchant_id: int, month: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE merchants SET last_monthly_fee_month=? WHERE id=?", (month, merchant_id))
        conn.commit()
    finally:
        conn.close()


def get_merchant_stats(merchant_id: int) -> dict:
    """Returns this month's transaction count, total processed, and total fees."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current_month = datetime.now().strftime("%Y-%m")
        row = conn.execute("""
            SELECT
                COUNT(*) as tx_count,
                COALESCE(SUM(amount), 0) as total_processed,
                COALESCE(SUM(platform_fee), 0) as total_fees
            FROM transactions
            WHERE merchant_id = ? AND strftime('%Y-%m', created_at) = ?
        """, (merchant_id, current_month)).fetchone()
        return dict(row) if row else {"tx_count": 0, "total_processed": 0.0, "total_fees": 0.0}
    finally:
        conn.close()


def get_merchant_recent_transactions(merchant_id: int, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT t.id, t.amount, t.platform_fee, t.stripe_status, t.created_at,
                   u.full_name as customer_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.merchant_id = ?
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (merchant_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Helper ────────────────────────────────────────────────────────────────────
def _row_to_dict(row) -> dict:
    return dict(row)
