"""Integration tests for the customer self-service portal."""

import pytest


class TestRequestAccess:
    def test_always_returns_success(self, client):
        """Should return 200 regardless of whether email exists (no enumeration)."""
        res = client.post("/customers/request-access", json={
            "email": "nobody@test.com",
        })
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_returns_success_for_existing_email(self, client, stripe_stub):
        """Same response for enrolled email — no enumeration leak."""
        # Enroll a user first (simplified — just insert via DB)
        from app.db import init_db
        from app.db.connection import _get_conn, PH
        from datetime import datetime, timezone

        init_db()
        with _get_conn() as conn:
            c = conn.cursor()
            c.execute(f"""
                INSERT INTO users (full_name, email, phone, enrolled_at)
                VALUES ({PH}, {PH}, {PH}, {PH})
            """, ("Portal User", "portal@test.com", None, datetime.now(timezone.utc).isoformat()))

        res = client.post("/customers/request-access", json={
            "email": "portal@test.com",
        })
        assert res.status_code == 200
        assert res.json()["success"] is True


class TestVerifyCode:
    def test_invalid_code_rejected(self, client):
        res = client.post("/customers/verify-code", json={
            "email": "test@test.com",
            "code": "000000",
        })
        assert res.status_code == 400
        assert "Invalid" in res.json()["detail"]


class TestDeleteAccount:
    def test_invalid_code_rejected(self, client):
        res = client.request("DELETE", "/customers/delete-account", json={
            "email": "test@test.com",
            "code": "000000",
        })
        assert res.status_code == 400
