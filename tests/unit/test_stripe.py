"""Tests for app.services.stripe — fee calculation."""

from app.services.stripe import MONTHLY_FEE, SCAN_FEE, TRANSACTION_RATE, calculate_platform_fee


class TestCalculatePlatformFee:
    def test_basic_fee(self):
        # $100 transaction: 100 * 0.005 + 0.05 = 0.55
        assert calculate_platform_fee(100.0) == 0.55

    def test_small_transaction(self):
        # $1 transaction: 1 * 0.005 + 0.05 = 0.055 → rounds to 0.06
        assert calculate_platform_fee(1.0) == 0.06

    def test_large_transaction(self):
        # $10,000 transaction: 10000 * 0.005 + 0.05 = 50.05
        assert calculate_platform_fee(10000.0) == 50.05

    def test_fee_never_exceeds_amount_for_realistic_transactions(self):
        """For any transaction >= $1 (realistic minimum), the per-transaction
        fee must be less than the amount. This was the P0 bug — the old code
        added $29 monthly fee which exceeded small amounts like $5."""
        test_amounts = [1.00, 2.00, 5.00, 10.00, 25.00, 28.95, 29.00, 50.00, 100.00, 500.00]
        for amount in test_amounts:
            fee = calculate_platform_fee(amount)
            assert fee < amount, f"Fee {fee} >= amount {amount}"

    def test_old_monthly_bundling_is_gone(self):
        """The critical fix: a $5 transaction must NOT have a $29+ fee.
        Before the fix, the first tx of the month would get $29 + $0.05 +
        $0.025 = $29.075, which Stripe would reject."""
        fee = calculate_platform_fee(5.00)
        assert (
            fee < 1.00
        ), f"Fee {fee} is suspiciously high for $5 — monthly fee may still be bundled"

    def test_minimum_possible_fee(self):
        # Even the smallest transaction gets the scan fee
        fee = calculate_platform_fee(0.01)
        # 0.01 * 0.005 = 0.00005, rounds to 0.0, + 0.05 = 0.05
        assert fee == 0.05

    def test_fee_components_are_correct(self):
        assert TRANSACTION_RATE == 0.005
        assert SCAN_FEE == 0.05
        assert MONTHLY_FEE == 29.00  # exists but not used in per-tx calculation

    def test_no_include_monthly_parameter(self):
        """Verify the old include_monthly parameter no longer exists."""
        import inspect

        sig = inspect.signature(calculate_platform_fee)
        param_names = list(sig.parameters.keys())
        assert param_names == ["amount_usd"], f"Unexpected params: {param_names}"
