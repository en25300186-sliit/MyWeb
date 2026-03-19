"""
Encryption utilities for storing API keys securely.

Derives a Fernet symmetric-encryption key from Django's SECRET_KEY using
SHA-256, so no extra secret material needs to be managed separately.
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    """Return a Fernet instance derived from the Django SECRET_KEY."""
    secret = settings.SECRET_KEY.encode('utf-8')
    # SHA-256 produces 32 bytes, which is exactly the key size Fernet needs
    raw_key = hashlib.sha256(secret).digest()
    return Fernet(base64.urlsafe_b64encode(raw_key))


def encrypt_value(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64-encoded ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_value(ciphertext: str) -> str:
    """Decrypt *ciphertext* and return the original plaintext string."""
    return _get_fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
