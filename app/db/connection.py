"""
FingerPay — Database Connection
================================
Provides _get_conn, _fetchone, _fetchall, PH, and binary_wrap.
All other db modules import from here — never from stdlib directly.
"""

from contextlib import contextmanager

from app.config import DATABASE_URL


# ── PostgreSQL ───────────────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    from psycopg2 import pool as pg_pool

    _pool = pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)

    @contextmanager
    def _get_conn():
        conn = _pool.getconn()
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pool.putconn(conn)

    def _fetchone(cursor):
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def _fetchall(cursor):
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def binary_wrap(data: bytes):
        """Wrap bytes for INSERT into a BYTEA column."""
        return psycopg2.Binary(data)

    PH = "%s"  # PostgreSQL placeholder

# ── SQLite (local dev) ───────────────────────────────────────────────────────
else:
    import sqlite3
    from pathlib import Path

    from app.config import DATA_DIR

    _DATA_DIR = Path(DATA_DIR) if DATA_DIR else Path(__file__).parent.parent.parent
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

    def binary_wrap(data: bytes):
        """No-op for SQLite BLOB columns."""
        return data

    PH = "?"  # SQLite placeholder
