"""
FingerPay — Cleanup Service
==============================
Periodic cleanup of stale data. Called from lifespan background task.
"""

import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db.connection import _get_conn, PH

logger = logging.getLogger("fingerpay.cleanup")

UPLOAD_DIR = Path(tempfile.gettempdir()) / "fingerpay_uploads"


def cleanup_stale_sessions(max_age_hours: int = 24) -> int:
    """Delete enrollment sessions older than max_age_hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM enrollment_sessions WHERE created_at < {PH}", (cutoff,))
        count = c.rowcount if hasattr(c, "rowcount") else 0
    if count:
        logger.info("Cleaned up %d stale enrollment sessions", count)
    return count


def cleanup_expired_tokens() -> int:
    """Delete used or expired password reset tokens."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM password_reset_tokens WHERE used=1 OR expires_at < {PH}", (now,))
        count = c.rowcount if hasattr(c, "rowcount") else 0
    if count:
        logger.info("Cleaned up %d expired reset tokens", count)
    return count


def cleanup_expired_verification_codes() -> int:
    """Delete used or expired customer verification codes."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM customer_verification_codes WHERE used=1 OR expires_at < {PH}", (now,))
        count = c.rowcount if hasattr(c, "rowcount") else 0
    if count:
        logger.info("Cleaned up %d expired verification codes", count)
    return count


def cleanup_orphan_uploads(max_age_minutes: int = 60) -> int:
    """Delete temp upload files older than max_age_minutes."""
    if not UPLOAD_DIR.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    count = 0
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < cutoff:
            f.unlink(missing_ok=True)
            count += 1
    if count:
        logger.info("Cleaned up %d orphan temp uploads", count)
    return count


def run_all_cleanups() -> None:
    """Run all cleanup tasks. Called periodically from app lifespan."""
    cleanup_stale_sessions()
    cleanup_expired_tokens()
    cleanup_expired_verification_codes()
    cleanup_orphan_uploads()
