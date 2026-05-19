"""Tests for app.config — env validation and defaults."""

import importlib
import os

import pytest

VALID_SECRET = "a" * 32
VALID_BIOMETRIC_KEY = "0" * 64
VALID_STRIPE_SECRET = "sk_test"
VALID_STRIPE_PUB = "pk_test"


def _reload_with(monkeypatch, **overrides):
    defaults = {
        "FINGERPAY_SECRET": VALID_SECRET,
        "BIOMETRIC_ENCRYPTION_KEY": VALID_BIOMETRIC_KEY,
        "STRIPE_SECRET_KEY": VALID_STRIPE_SECRET,
        "STRIPE_PUBLISHABLE_KEY": VALID_STRIPE_PUB,
        "DATABASE_URL": "",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    import app.config as cfg
    importlib.reload(cfg)
    return cfg


class TestValidateEnv:
    def test_passes_when_all_valid(self, monkeypatch):
        cfg = _reload_with(monkeypatch)
        cfg.validate_env()  # must not raise

    def test_raises_on_missing_fingerpay_secret(self, monkeypatch):
        cfg = _reload_with(monkeypatch, FINGERPAY_SECRET="")
        with pytest.raises(RuntimeError, match="FINGERPAY_SECRET"):
            cfg.validate_env()

    def test_raises_on_short_fingerpay_secret(self, monkeypatch):
        cfg = _reload_with(monkeypatch, FINGERPAY_SECRET="tooshort")
        with pytest.raises(RuntimeError, match="too short"):
            cfg.validate_env()

    def test_raises_on_missing_biometric_key(self, monkeypatch):
        cfg = _reload_with(monkeypatch, BIOMETRIC_ENCRYPTION_KEY="")
        with pytest.raises(RuntimeError, match="BIOMETRIC_ENCRYPTION_KEY"):
            cfg.validate_env()

    def test_raises_on_wrong_length_biometric_key(self, monkeypatch):
        cfg = _reload_with(monkeypatch, BIOMETRIC_ENCRYPTION_KEY="0" * 32)
        with pytest.raises(RuntimeError, match="64 hex chars"):
            cfg.validate_env()

    def test_raises_on_non_hex_biometric_key(self, monkeypatch):
        cfg = _reload_with(monkeypatch, BIOMETRIC_ENCRYPTION_KEY="z" * 64)
        with pytest.raises(RuntimeError, match="hex characters"):
            cfg.validate_env()

    def test_raises_on_missing_stripe_secret(self, monkeypatch):
        cfg = _reload_with(monkeypatch, STRIPE_SECRET_KEY="")
        with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
            cfg.validate_env()

    def test_raises_on_missing_stripe_publishable(self, monkeypatch):
        cfg = _reload_with(monkeypatch, STRIPE_PUBLISHABLE_KEY="")
        with pytest.raises(RuntimeError, match="STRIPE_PUBLISHABLE_KEY"):
            cfg.validate_env()

    def test_raises_lists_all_errors(self, monkeypatch):
        cfg = _reload_with(
            monkeypatch,
            FINGERPAY_SECRET="",
            BIOMETRIC_ENCRYPTION_KEY="",
            STRIPE_SECRET_KEY="",
            STRIPE_PUBLISHABLE_KEY="",
        )
        with pytest.raises(RuntimeError) as exc_info:
            cfg.validate_env()
        msg = str(exc_info.value)
        assert "FINGERPAY_SECRET" in msg
        assert "BIOMETRIC_ENCRYPTION_KEY" in msg
        assert "STRIPE_SECRET_KEY" in msg
        assert "STRIPE_PUBLISHABLE_KEY" in msg

    def test_raises_on_localhost_base_url_in_production(self, monkeypatch):
        cfg = _reload_with(
            monkeypatch,
            DATABASE_URL="postgres://user:pass@host/db",
            APP_BASE_URL="http://localhost:8000",
        )
        with pytest.raises(RuntimeError, match="APP_BASE_URL"):
            cfg.validate_env()

    def test_allows_localhost_base_url_in_dev(self, monkeypatch):
        cfg = _reload_with(monkeypatch, DATABASE_URL="", APP_BASE_URL="http://localhost:8000")
        cfg.validate_env()  # must not raise in dev (no DATABASE_URL)


class TestConfigDefaults:
    def test_no_dangerous_jwt_default(self):
        """Config must default to empty string, not a hardcoded secret."""
        import app.config as cfg
        original = os.environ.get("FINGERPAY_SECRET", "")
        if not original:
            assert cfg.FINGERPAY_SECRET == "" or original == cfg.FINGERPAY_SECRET

    def test_app_base_url_has_safe_default(self):
        import app.config as cfg
        if not os.environ.get("APP_BASE_URL"):
            assert "localhost" in cfg.APP_BASE_URL
