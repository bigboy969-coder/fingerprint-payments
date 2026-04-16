"""Tests for app.services.crypto — AES-256-GCM encrypt/decrypt."""

import os

import pytest


class TestEncryptDecrypt:
    def test_round_trip(self):
        from app.services.crypto import decrypt_descriptor, encrypt_descriptor

        plaintext = b"hello world" * 10  # arbitrary bytes
        encrypted = encrypt_descriptor(plaintext)
        decrypted = decrypt_descriptor(encrypted)
        assert decrypted == plaintext

    def test_nonce_is_unique(self):
        """Each encryption should produce a different ciphertext due to random nonce."""
        from app.services.crypto import encrypt_descriptor

        plaintext = b"same data"
        a = encrypt_descriptor(plaintext)
        b = encrypt_descriptor(plaintext)
        assert a != b  # different nonces → different ciphertexts

    def test_ciphertext_is_longer_than_plaintext(self):
        """Nonce (12 bytes) + GCM tag (16 bytes) add overhead."""
        from app.services.crypto import encrypt_descriptor

        plaintext = b"x" * 100
        encrypted = encrypt_descriptor(plaintext)
        assert len(encrypted) > len(plaintext)
        # Exact: 12 (nonce) + 100 (data) + 16 (tag) = 128
        assert len(encrypted) == 128

    def test_tampered_ciphertext_raises(self):
        from app.services.crypto import decrypt_descriptor, encrypt_descriptor

        encrypted = encrypt_descriptor(b"secret data")
        # Flip a byte in the ciphertext portion (after the 12-byte nonce)
        tampered = encrypted[:20] + bytes([encrypted[20] ^ 0xFF]) + encrypted[21:]
        with pytest.raises(Exception):  # InvalidTag from cryptography
            decrypt_descriptor(tampered)

    def test_empty_plaintext(self):
        from app.services.crypto import decrypt_descriptor, encrypt_descriptor

        encrypted = encrypt_descriptor(b"")
        decrypted = decrypt_descriptor(encrypted)
        assert decrypted == b""

    def test_large_plaintext(self):
        from app.services.crypto import decrypt_descriptor, encrypt_descriptor

        # ORB descriptors are typically ~500*32 = 16,000 bytes
        plaintext = os.urandom(16000)
        encrypted = encrypt_descriptor(plaintext)
        decrypted = decrypt_descriptor(encrypted)
        assert decrypted == plaintext

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "")
        # Need to reimport to pick up the empty key
        import importlib

        import app.config

        importlib.reload(app.config)
        import app.services.crypto as crypto

        importlib.reload(crypto)

        with pytest.raises(RuntimeError, match="BIOMETRIC_ENCRYPTION_KEY"):
            crypto.encrypt_descriptor(b"test")

        # Restore
        monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", "0" * 64)
        importlib.reload(app.config)
        importlib.reload(crypto)
