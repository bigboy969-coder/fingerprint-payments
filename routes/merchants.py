"""
FingerPay — Merchant Routes
=============================
POST /merchants/register  - register a new merchant, get an API key
"""

import secrets
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/merchants")

DB_PATH = Path(__file__).parent.parent / "fingerpay.db"


def _init_merchants_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS merchants (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    NOT NULL UNIQUE,
            api_key_hash TEXT  NOT NULL,
            created_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def verify_merchant_api_key(api_key: str) -> dict:
    """Verify an API key — returns merchant record or raises ValueError."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM merchants WHERE api_key_hash = ?", (key_hash,)
        ).fetchone()
        if row is None:
            raise ValueError("Invalid API key.")
        return dict(row)
    finally:
        conn.close()


class MerchantRegister(BaseModel):
    name: str
    email: str


@router.post("/register")
async def register_merchant(body: MerchantRegister):
    """
    Register a new merchant. Returns a one-time API key.
    Store this key securely — it won't be shown again.
    """
    _init_merchants_table()

    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    now = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO merchants (name, email, api_key_hash, created_at)
            VALUES (?, ?, ?, ?)
        """, (body.name, body.email, key_hash, now))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Merchant with this email already exists.")
    finally:
        conn.close()

    return {
        "success": True,
        "api_key": api_key,
        "warning": "Save this key now — it will not be shown again.",
    }
