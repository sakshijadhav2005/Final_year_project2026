"""Encrypt social media tokens at rest.

The key is derived from SECRET_KEY, so rotating SECRET_KEY disconnects every account
(users reconnect; nothing else breaks).
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(b"eventai-social-tokens:" + secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(value: str) -> str:
    return _fernet(get_settings().secret_key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_token(value: str) -> str | None:
    """None when the token can't be decrypted (SECRET_KEY changed): treat as disconnected."""
    try:
        return _fernet(get_settings().secret_key).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
