"""
FingerPay — Biometric Encryption
==================================
AES-256-GCM encryption for fingerprint descriptors.
The raw biometric data is never stored unencrypted.
"""

import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import BIOMETRIC_ENCRYPTION_KEY


def _get_key() -> bytes:
    """Load the 32-byte AES-256 key from config."""
    hex_key = BIOMETRIC_ENCRYPTION_KEY
    if not hex_key:
        raise RuntimeError("BIOMETRIC_ENCRYPTION_KEY is not set in environment.")
    key = bytes.fromhex(hex_key)
    if len(key) != 32:
        raise RuntimeError("BIOMETRIC_ENCRYPTION_KEY must be exactly 32 bytes (64 hex chars).")
    return key


def encrypt_descriptor(descriptor_bytes: bytes) -> bytes:
    """
    Encrypt fingerprint descriptor bytes using AES-256-GCM.
    Returns nonce + ciphertext (nonce is prepended for storage).
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, descriptor_bytes, None)
    return nonce + ciphertext  # prepend nonce so we can decrypt later


def decrypt_descriptor(encrypted_bytes: bytes) -> bytes:
    """
    Decrypt fingerprint descriptor bytes using AES-256-GCM.
    Expects nonce prepended to ciphertext (as stored by encrypt_descriptor).
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    return aesgcm.decrypt(nonce, ciphertext, None)
