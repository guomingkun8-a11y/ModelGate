"""Production settings loaded from environment variables and a local .env file.

All secrets stay out of source control: the .env file is gitignored and only
.env.example is committed. Settings are typed and validated at startup so a
misconfigured environment fails fast instead of at first request.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import secrets
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is two levels up from this file (app/config.py -> backend/ -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL and real upstreams; Redis shared limits are not connected yet.
    mode: Literal["demo", "prod"] = "prod"

    # --- Storage ---
    database_url: str = "postgresql+asyncpg://modelgate:modelgate@127.0.0.1:15435/modelgate"
    redis_url: str = "redis://127.0.0.1:16381/0"

    # --- Upstream key encryption ---
    # Fernet key used to encrypt upstream API keys at rest. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    master_key: str = Field(default="", description="Fernet key for encrypting upstream keys")

    # --- Administrator credentials ---
    admin_username: str = "admin"
    admin_password: str = "admin123456"
    admin_token: str = Field(default_factory=lambda: secrets.token_urlsafe(48))

    # --- Gateway behaviour ---
    max_attempts: int = 3
    request_timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
    @property
    def is_prod(self) -> bool:
        return self.mode == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
