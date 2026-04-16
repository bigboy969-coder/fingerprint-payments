"""
FingerPay — Database Schema
=============================
Idempotent table creation. Called once at app startup via init_db().
"""

from app.config import DATABASE_URL
from app.db.connection import _get_conn


def init_db() -> None:
    with _get_conn() as conn:
        c = conn.cursor()

        if DATABASE_URL:
            _create_tables_postgres(c)
        else:
            _create_tables_sqlite(c)
            _migrate_sqlite(c)


# ── PostgreSQL ───────────────────────────────────────────────────────────────

def _create_tables_postgres(c) -> None:
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS customer_verification_codes (
            id          SERIAL PRIMARY KEY,
            email       TEXT    NOT NULL,
            code        TEXT    NOT NULL,
            expires_at  TEXT    NOT NULL,
            used        INTEGER DEFAULT 0
        )
    """)


# ── SQLite ───────────────────────────────────────────────────────────────────

def _create_tables_sqlite(c) -> None:
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS customer_verification_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL,
            code        TEXT    NOT NULL,
            expires_at  TEXT    NOT NULL,
            used        INTEGER DEFAULT 0
        )
    """)


def _migrate_sqlite(c) -> None:
    """Best-effort column additions for older SQLite databases."""
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
