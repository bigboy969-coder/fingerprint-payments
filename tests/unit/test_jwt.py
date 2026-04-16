"""Tests for app.services.jwt — token creation and verification."""

import pytest

from app.services.jwt import (
    TOKEN_TTL_MINUTES,
    create_access_token,
    create_merchant_token,
    verify_access_token,
    verify_merchant_token,
)


class TestAccessToken:
    def test_create_and_verify(self):
        token = create_access_token(user_id=42, merchant_id=7)
        payload = verify_access_token(token)
        assert payload["user_id"] == 42
        assert payload["merchant_id"] == 7
        assert payload["type"] == "customer"

    def test_rejects_merchant_token(self):
        """A merchant JWT used on /pay should be a clean ValueError, not a KeyError."""
        merchant_token = create_merchant_token(merchant_id=99)
        with pytest.raises(ValueError, match="Not a customer access token"):
            verify_access_token(merchant_token)

    def test_rejects_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid or expired"):
            verify_access_token("garbage.token.here")

    def test_token_ttl_is_short(self):
        assert TOKEN_TTL_MINUTES == 2


class TestMerchantToken:
    def test_create_and_verify(self):
        token = create_merchant_token(merchant_id=99)
        payload = verify_merchant_token(token)
        assert payload["merchant_id"] == 99
        assert payload["type"] == "merchant"

    def test_rejects_customer_token(self):
        customer_token = create_access_token(user_id=42)
        with pytest.raises(ValueError, match="Not a merchant token"):
            verify_merchant_token(customer_token)

    def test_rejects_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid or expired"):
            verify_merchant_token("garbage.token.here")
