"""Tests for app.services.stripe — subscription fee model."""

from app.services.stripe import MONTHLY_FEE


class TestFeeModel:
    def test_monthly_fee_is_correct(self):
        assert MONTHLY_FEE == 99.00

    def test_no_per_transaction_fee(self):
        """FingerPay is subscription-only. No calculate_platform_fee function should exist."""
        import app.services.stripe as stripe_module

        assert not hasattr(
            stripe_module, "calculate_platform_fee"
        ), "Per-transaction fee function must not exist"

    def test_no_transaction_rate(self):
        import app.services.stripe as stripe_module

        assert not hasattr(stripe_module, "TRANSACTION_RATE")

    def test_no_scan_fee(self):
        import app.services.stripe as stripe_module

        assert not hasattr(stripe_module, "SCAN_FEE")
