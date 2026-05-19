"""
FingerPay — Test Configuration
================================
Shared fixtures for all tests. See docs/TESTING.md for the full strategy.
"""

import os

import pytest

# Set test env vars BEFORE any app imports
os.environ.setdefault("FINGERPAY_SECRET", "test-secret-do-not-use-in-prod-xx")
os.environ.setdefault("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unused")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_unused")
os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
# DATABASE_URL intentionally unset — tests use SQLite

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"
IMAGES_DIR = FIXTURES_DIR / "images"


@pytest.fixture(scope="session")
def test_fingerprint_path() -> Path:
    """Path to the sample fingerprint image for testing."""
    return IMAGES_DIR / "test_fingerprint.png"


@pytest.fixture()
def client(tmp_path):
    """FastAPI test client with a fresh SQLite DB per test."""
    # Point SQLite at a temp directory so tests are isolated
    db_path = tmp_path / "fingerpay.db"
    with patch("app.db.connection.DB_PATH", db_path):
        from app.db.schema import init_db
        from app.main import app, limiter

        init_db()
        # Disable ALL rate limiters in tests
        limiter.enabled = False
        from app.routes import authenticate as auth_mod
        from app.routes import customers as customers_mod
        from app.routes import merchants as merchants_mod

        merchants_mod.limiter.enabled = False
        customers_mod.limiter.enabled = False
        auth_mod.limiter.enabled = False
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        limiter.enabled = True
        merchants_mod.limiter.enabled = True
        customers_mod.limiter.enabled = True
        auth_mod.limiter.enabled = True


@pytest.fixture()
def stripe_stub():
    """Mock all Stripe API calls so integration tests don't hit Stripe."""
    with patch("app.services.stripe.stripe") as mock_stripe:
        # Customer.create
        mock_customer = MagicMock()
        mock_customer.id = "cus_test_123"
        mock_stripe.Customer.create.return_value = mock_customer

        # SetupIntent.create
        mock_stripe.SetupIntent.create.return_value = MagicMock()

        # PaymentIntent.create
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_456"
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        # Account.create (Connect)
        mock_account = MagicMock()
        mock_account.id = "acct_test_789"
        mock_stripe.Account.create.return_value = mock_account

        # AccountLink.create
        mock_link = MagicMock()
        mock_link.url = "https://connect.stripe.com/test"
        mock_stripe.AccountLink.create.return_value = mock_link

        # Customer.delete
        mock_stripe.Customer.delete.return_value = MagicMock()

        yield mock_stripe
