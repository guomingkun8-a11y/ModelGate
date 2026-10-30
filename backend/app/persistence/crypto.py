"""Encryption helpers for upstream API keys.

Upstream keys are encrypted at rest with a Fernet master key. The plaintext
never appears in logs or the database. A missing or invalid master key fails
fast at startup rather than silently storing keys in plaintext.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class KeyCipher:
    def __init__(self, master_key: str):
        if not master_key:
            raise ValueError(
                "MASTER_KEY 未设置。请先运行 "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
                "生成并写入 .env。"
            )
        try:
            self._fernet = Fernet(master_key.encode())
        except Exception as exc:  # noqa: BLE001 - surface a clear config error
            raise ValueError("MASTER_KEY 不是合法的 Fernet 密钥。") from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("上游 Key 解密失败，MASTER_KEY 可能已更换。") from exc
