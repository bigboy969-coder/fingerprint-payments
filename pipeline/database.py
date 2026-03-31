"""
FingerPay — Database Layer
===========================
Handles all SQLite storage for users, fingerprints, and transactions.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from pipeline.extractor import desc_to_blob, blob_to_desc, match_score, MATCH_THRESHOLD


# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "fingerpay.db"


# ── Setup ─────────────────────────────────────────────────────────────────────
def init_db():
    """Create tables and run safe schema migrations."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name    TEXT    NOT NULL,
            email        TEXT    NOT NULL UNIQUE,
            phone        TEXT,
            enrolled_at  TEXT    NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fingerprints (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            descriptor  BLOB    NOT NULL,
            enrolled_at TEXT    NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            amount        REAL    NOT NULL,
            merchant      TEXT    NOT NULL,
            balance_after REAL    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

    conn.commit()

    # Safe migration: add balance column to existing users table
    try:
        c.execute("ALTER TABLE users ADD COLUMN balance REAL NOT NULL DEFAULT 0.0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists — safe to ignore

    conn.close()


# ── Enroll ────────────────────────────────────────────────────────────────────
def enroll_user(full_name: str, email: str, phone: str, descriptor) -> dict:
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
        INSERT INTO users (full_name, email, phone, enrolled_at)
        VALUES (?, ?, ?, ?)
    """, (full_name, email, phone, now))

    user_id = c.lastrowid

    c.execute("""
        INSERT INTO fingerprints (user_id, descriptor, enrolled_at)
        VALUES (?, ?, ?)
    """, (user_id, desc_to_blob(descriptor), now))

    conn.commit()

    row = c.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    return _row_to_dict(row)


# ── Find user by fingerprint ──────────────────────────────────────────────────
def find_user_by_fingerprint(probe) -> dict:
    """
    Compare probe descriptor against all enrolled fingerprints.
    Returns best matching user or None.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()

        rows = c.execute("""
            SELECT f.user_id, f.descriptor
            FROM fingerprints f
        """).fetchall()

        best_id = None
        best_score = 0

        for row in rows:
            score = match_score(probe, blob_to_desc(row["descriptor"]))
            if score > best_score:
                best_score = score
                best_id = row["user_id"]

        matched = best_score >= MATCH_THRESHOLD

        if matched and best_id:
            row = c.execute(
                "SELECT * FROM users WHERE id = ?", (best_id,)
            ).fetchone()
            return {"matched": True, "score": best_score, "user": _row_to_dict(row)}

        return {"matched": False, "score": best_score, "user": None}
    finally:
        conn.close()


# ── Balance ───────────────────────────────────────────────────────────────────
def get_balance(user_id: int) -> float:
    """Return current balance for the given user_id."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"User {user_id} not found.")
        return row["balance"]
    finally:
        conn.close()


def deduct_balance(user_id: int, amount: float) -> float:
    """
    Atomically deduct amount from user balance.
    Raises ValueError if balance is insufficient.
    Returns new balance after deduction.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"User {user_id} not found.")

        current = row["balance"]
        if current < amount:
            raise ValueError(
                f"Insufficient balance: have {current:.2f}, need {amount:.2f}."
            )

        new_balance = round(current - amount, 10)
        conn.execute(
            "UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id)
        )
        conn.commit()
        return new_balance
    finally:
        conn.close()


def record_transaction(user_id: int, amount: float, merchant: str, balance_after: float) -> dict:
    """
    Persist a completed transaction.
    Returns the saved transaction record as a dict.
    """
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            INSERT INTO transactions (user_id, amount, merchant, balance_after, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, merchant, balance_after, now))
        conn.commit()
        tx_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ── Helper ────────────────────────────────────────────────────────────────────
def _row_to_dict(row) -> dict:
    return dict(row)
