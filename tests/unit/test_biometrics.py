"""Tests for app.services.biometrics — DP SDK integration."""

import platform

import pytest

from app.services.biometrics import (
    SCANS_NEEDED,
    TEMPLATE_SIZE,
    VERIFY_FEATURE_SIZE,
    blob_to_desc,
    desc_to_blob,
    enrollment_features_needed,
)

_WINDOWS = platform.system() == "Windows"


class TestBlobHelpers:
    def test_desc_to_blob_roundtrip(self):
        data = b"\x01\x02\x03" * 100
        assert blob_to_desc(desc_to_blob(data)) == data

    def test_desc_to_blob_returns_bytes(self):
        assert isinstance(desc_to_blob(b"abc"), bytes)

    def test_blob_to_desc_returns_bytes(self):
        assert isinstance(blob_to_desc(b"abc"), bytes)


class TestEnrollmentFeaturesNeeded:
    def test_starts_at_scans_needed(self):
        assert enrollment_features_needed([]) == SCANS_NEEDED

    def test_decrements_per_scan(self):
        blobs = [b"x" * 10] * 2
        assert enrollment_features_needed(blobs) == max(0, SCANS_NEEDED - 2)

    def test_zero_when_complete(self):
        blobs = [b"x" * 10] * SCANS_NEEDED
        assert enrollment_features_needed(blobs) == 0

    def test_never_negative(self):
        blobs = [b"x" * 10] * (SCANS_NEEDED + 5)
        assert enrollment_features_needed(blobs) == 0


class TestConstants:
    def test_scans_needed_is_positive(self):
        assert SCANS_NEEDED > 0

    def test_template_size_is_positive(self):
        assert TEMPLATE_SIZE > 0

    def test_verify_feature_size_is_positive(self):
        assert VERIFY_FEATURE_SIZE > 0


class TestWindowsOnlyFunctions:
    def test_capture_raises_on_non_windows(self):
        if _WINDOWS:
            pytest.skip("Windows — capture would attempt real hardware")
        from app.services.biometrics import capture_enrollment_features

        with pytest.raises(NotImplementedError):
            capture_enrollment_features()

    def test_build_template_raises_on_non_windows(self):
        if _WINDOWS:
            pytest.skip("Windows — would attempt real SDK call")
        from app.services.biometrics import build_template

        with pytest.raises(NotImplementedError):
            build_template([b"x" * 10])

    def test_verify_raises_on_non_windows(self):
        if _WINDOWS:
            pytest.skip("Windows — would attempt real SDK call")
        from app.services.biometrics import verify

        with pytest.raises(NotImplementedError):
            verify(b"features", b"template")
