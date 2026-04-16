"""Tests for app.services.biometrics — ORB extraction and matching."""

import numpy as np
import pytest
from pathlib import Path

from app.services.biometrics import (
    extract_descriptor,
    match_score,
    desc_to_blob,
    blob_to_desc,
    MATCH_THRESHOLD,
)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "images"
TEST_IMAGE = FIXTURES_DIR / "test_fingerprint.png"


class TestExtractDescriptor:
    def test_extracts_from_valid_image(self):
        if not TEST_IMAGE.exists():
            pytest.skip("test_fingerprint.png not in fixtures")
        desc = extract_descriptor(str(TEST_IMAGE))
        assert isinstance(desc, np.ndarray)
        assert desc.dtype == np.uint8
        assert desc.shape[1] == 32  # ORB descriptors are 32 bytes wide
        assert desc.shape[0] >= 10  # minimum keypoints

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            extract_descriptor("/nonexistent/path.png")

    def test_raises_on_bad_image(self, tmp_path):
        bad_file = tmp_path / "garbage.png"
        bad_file.write_bytes(b"this is not an image")
        with pytest.raises((FileNotFoundError, ValueError)):
            extract_descriptor(str(bad_file))


class TestMatchScore:
    def test_self_match_is_high(self):
        if not TEST_IMAGE.exists():
            pytest.skip("test_fingerprint.png not in fixtures")
        desc = extract_descriptor(str(TEST_IMAGE))
        score = match_score(desc, desc)
        assert score >= MATCH_THRESHOLD

    def test_random_descriptors_score_low(self):
        # Random noise should not match
        d1 = np.random.randint(0, 256, (100, 32), dtype=np.uint8)
        d2 = np.random.randint(0, 256, (100, 32), dtype=np.uint8)
        score = match_score(d1, d2)
        assert score < MATCH_THRESHOLD

    def test_empty_descriptors_score_zero(self):
        d1 = np.zeros((1, 32), dtype=np.uint8)
        d2 = np.zeros((1, 32), dtype=np.uint8)
        assert match_score(d1, d2) == 0

    def test_threshold_is_reasonable(self):
        assert MATCH_THRESHOLD == 40
        assert isinstance(MATCH_THRESHOLD, int)


class TestBlobConversion:
    def test_round_trip(self):
        original = np.random.randint(0, 256, (50, 32), dtype=np.uint8)
        blob = desc_to_blob(original)
        restored = blob_to_desc(blob)
        np.testing.assert_array_equal(original, restored)

    def test_corrupt_blob_raises(self):
        # Not a multiple of 32 bytes
        with pytest.raises(ValueError, match="Corrupt descriptor"):
            blob_to_desc(b"x" * 33)

    def test_blob_type_is_bytes(self):
        desc = np.zeros((10, 32), dtype=np.uint8)
        blob = desc_to_blob(desc)
        assert isinstance(blob, bytes)
        assert len(blob) == 10 * 32
