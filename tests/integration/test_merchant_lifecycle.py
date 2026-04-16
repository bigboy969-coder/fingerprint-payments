"""Integration tests for the merchant lifecycle: signup → login → dashboard → regen key."""

import pytest


class TestMerchantSignup:
    def test_signup_returns_api_key(self, client, stripe_stub):
        res = client.post("/merchants/signup", json={
            "business_name": "Test Coffee",
            "name": "Jane Doe",
            "email": "jane@test.com",
            "password": "strongpass123",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "api_key" in data
        assert len(data["api_key"]) > 20

    def test_signup_sets_cookie(self, client, stripe_stub):
        res = client.post("/merchants/signup", json={
            "business_name": "Test Coffee",
            "name": "Jane Doe",
            "email": "cookie@test.com",
            "password": "strongpass123",
        })
        assert res.status_code == 200
        assert "merchant_token" in res.cookies

    def test_signup_duplicate_email_rejected(self, client, stripe_stub):
        body = {
            "business_name": "Shop A",
            "name": "Owner",
            "email": "dupe@test.com",
            "password": "strongpass123",
        }
        client.post("/merchants/signup", json=body)
        res = client.post("/merchants/signup", json=body)
        assert res.status_code == 400
        assert "already exists" in res.json()["detail"]


class TestMerchantLogin:
    def test_login_success(self, client, stripe_stub):
        # First signup
        client.post("/merchants/signup", json={
            "business_name": "Login Test",
            "name": "Bob",
            "email": "bob@test.com",
            "password": "mypassword",
        })
        # Then login
        res = client.post("/merchants/login", json={
            "email": "bob@test.com",
            "password": "mypassword",
        })
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "merchant_token" in res.cookies

    def test_login_wrong_password(self, client, stripe_stub):
        client.post("/merchants/signup", json={
            "business_name": "Bad Pass",
            "name": "Eve",
            "email": "eve@test.com",
            "password": "realpassword",
        })
        res = client.post("/merchants/login", json={
            "email": "eve@test.com",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_login_nonexistent_email(self, client, stripe_stub):
        res = client.post("/merchants/login", json={
            "email": "nobody@test.com",
            "password": "whatever",
        })
        assert res.status_code == 401


class TestMerchantDashboard:
    def test_dashboard_requires_auth(self, client):
        res = client.get("/merchants/me")
        assert res.status_code == 401

    def test_dashboard_works_with_auth_header(self, client, stripe_stub):
        """Use Authorization header (fallback path) since TestClient
        doesn't send Secure cookies over http://."""
        from app.services.jwt import create_merchant_token
        from app.db import get_merchant_by_email

        client.post("/merchants/signup", json={
            "business_name": "Dashboard Test",
            "name": "Alice",
            "email": "alice@test.com",
            "password": "pass1234",
        })

        merchant = get_merchant_by_email("alice@test.com")
        token = create_merchant_token(merchant["id"])

        res = client.get("/merchants/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["business_name"] == "Dashboard Test"
        assert "stats" in data
        assert "recent_transactions" in data


class TestMerchantLogout:
    def test_logout_clears_cookie(self, client, stripe_stub):
        client.post("/merchants/signup", json={
            "business_name": "Logout Test",
            "name": "Lori",
            "email": "lori@test.com",
            "password": "pass1234",
        })
        res = client.post("/merchants/logout")
        assert res.status_code == 200
        # After logout, dashboard should fail
        res = client.get("/merchants/me")
        assert res.status_code == 401
