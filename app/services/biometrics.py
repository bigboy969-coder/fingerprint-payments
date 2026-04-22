"""
FingerPay — Fingerprint Feature Extractor
==========================================
Handles all fingerprint image processing.
Extracts ORB descriptors and matches them.
"""

import cv2
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
MATCH_THRESHOLD = 40  # minimum good matches to confirm identity


def extract_descriptor(image_path: str) -> np.ndarray:
    """
    Takes a fingerprint image path.
    Returns ORB descriptors as a numpy array.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # Enhance image quality
    img = cv2.equalizeHist(img)
    img = cv2.GaussianBlur(img, (3, 3), 0)

    # Extract ORB keypoints and descriptors
    orb = cv2.ORB_create(nfeatures=500)
    _, descriptors = orb.detectAndCompute(img, None)

    if descriptors is None or len(descriptors) < 10:
        raise ValueError("Poor image quality — not enough keypoints detected.")

    return descriptors


def match_score(d1: np.ndarray, d2: np.ndarray) -> int:
    """
    Compares two descriptors.
    Returns number of good matches (higher = more similar).
    """
    if len(d1) < 2 or len(d2) < 2:
        return 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(d1, d2, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    return len(good)


def desc_to_blob(d: np.ndarray) -> bytes:
    """Convert descriptor to bytes for database storage."""
    return d.tobytes()


def blob_to_desc(b: bytes) -> np.ndarray:
    """Convert bytes from database back to descriptor."""
    if len(b) % 32 != 0:
        raise ValueError(f"Corrupt descriptor blob: {len(b)} bytes is not a multiple of 32.")
    return np.frombuffer(b, dtype=np.uint8).reshape(-1, 32)
