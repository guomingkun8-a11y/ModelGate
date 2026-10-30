"""Key hashing and verification helpers for virtual API keys.

Virtual API keys are stored as a salted SHA-256 hash, never in plaintext.
These functions are shared by the production repository and any future admin
flows. (Extracted from the former demo store so the demo could be removed.)
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_key(key: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + key).encode()).hexdigest()


def verify_key(key: str, digest: str) -> bool:
    try:
        return hmac.compare_digest(hash_key(key, digest.split(":", 1)[0]), digest)
    except (ValueError, IndexError):
        return False


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
