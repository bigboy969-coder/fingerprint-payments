"""Tests for app.config — env validation and defaults."""

import importlib
import os

import pytest


class TestValidateEnv:
    def test_raises_on_missing_fingerpay_secret(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test")

        # Reimport to pick up new env
        import app.config as cfg
        importlib.reload(cfg)

        with pytest.raises(RuntimeError, match="FINGERPAY_SECRET"):
            cfg.validate_env()

    def test_raises_on_missing_biometric_key(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "test-secret")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test")

        import app.config as cfg
        importlib.reload(cfg)

        with pytest.raises(RuntimeError, match="BIOMETRIC_ENCRYPTION_KEY"):
            cfg.validate_env()

    def test_raises_on_missing_stripe_secret(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "test-secret")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test")

        import app.config as cfg
        importlib.reload(cfg)

        with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
            cfg.validate_env()

    def test_raises_on_missing_stripe_publishable(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "test-secret")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "")

        import app.config as cfg
        importlib.reload(cfg)

        with pytest.raises(RuntimeError, match="STRIPE_PUBLISHABLE_KEY"):
            cfg.validate_env()

    def test_raises_lists_all_missing(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "")

        import app.config as cfg
        importlib.reload(cfg)

        with pytest.raises(RuntimeError, match="FINGERPAY_SECRET.*BIOMETRIC_ENCRYPTION_KEY.*STRIPE_SECRET_KEY.*STRIPE_PUBLISHABLE_KEY"):
            cfg.validate_env()

    def test_passes_when_all_set(self, monkeypatch):
        monkeypatch.setenv("FINGERPAY_SECRET", "test-secret")
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test")

        import app.config as cfg
        importlib.reload(cfg)

        # Should not raise
        cfg.validate_env()


class TestConfigDefaults:
    def test_no_dangerous_jwt_default(self):
        """The old code had SECRET_KEY defaulting to 'dev-secret-change-in-prod'.
        Config must default to empty string, which validate_env will catch."""
        import app.config as cfg
        # If the env var is unset, should be empty, not a hardcoded secret
        original = os.environ.get("FINGERPAY_SECRET", "")
        if not original:
            assert cfg.FINGERPAY_SECRET == "" or cfg.FINGERPAY_SECRET == original

    def test_app_base_url_has_safe_default(self):
        import app.config as cfg
        # Default should be localhost for dev, not a production URL
        if not os.environ.get("APP_BASE_URL"):
            assert "localhost" in cfg.APP_BASE_URL
