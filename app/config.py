"""Application settings loaded from environment and optional `.env` in project root."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All runtime configuration; override via `.env` or process environment."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production"] = Field(
        default="development",
        description="Controls docs, reload defaults, and optional hardening.",
    )

    database_url: str = Field(
        ...,
        description="SQLAlchemy URL; use postgresql+psycopg:// (or plain postgresql:// — auto-normalized).",
    )

    api_prefix: str = Field(default="/api", description="Global URL prefix for all routers.")

    max_upload_bytes: int = Field(default=1_048_576, ge=1, description="Max multipart body size per upload.")

    box_secret_key_length: int = Field(default=8, ge=4, le=32, description="Alphanumeric secret length for new boxes.")

    cors_origins: str = Field(
        default="*",
        description='Comma-separated origins, or "*" for any.',
    )

    trusted_hosts: str | None = Field(
        default=None,
        description="Comma-separated hostnames for TrustedHostMiddleware; unset = disabled.",
    )

    log_level: str = Field(default="INFO", description="Standard logging level name.")

    docs_enabled: bool = Field(
        default=True,
        description="Expose /docs and /redoc (set false in production if desired).",
    )

    auto_create_tables: bool = Field(
        default=True,
        description="Run SQLAlchemy create_all on startup; prefer migrations in production.",
    )

    sqlalchemy_pool_size: int = Field(default=5, ge=1, le=50)
    sqlalchemy_max_overflow: int = Field(default=10, ge=0, le=100)
    sqlalchemy_pool_timeout: int = Field(default=30, ge=1)

    uvicorn_host: str = Field(
        default="0.0.0.0",
        description="Bind address for `python -m app`.",
        validation_alias=AliasChoices("UVICORN_HOST", "HOST"),
    )
    uvicorn_port: int = Field(
        default=9017,
        ge=1,
        le=65535,
        description="Bind port for `python -m app`.",
        validation_alias=AliasChoices("UVICORN_PORT", "PORT"),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_driver(cls, v: object) -> object:
        """Use psycopg v3 (package `psycopg`); plain postgresql:// defaults to missing psycopg2."""
        if not isinstance(v, str):
            return v
        s = v.strip()
        if s.startswith("postgresql://") and not s.startswith("postgresql+psycopg"):
            return "postgresql+psycopg://" + s[len("postgresql://") :]
        return s

    @field_validator("database_url", mode="after")
    @classmethod
    def reject_placeholder_database_url(cls, v: str) -> str:
        """Catch unchanged .env.example hostnames before a cryptic DNS error."""
        parsed = urlparse(v)
        host = (parsed.hostname or "").strip()
        if host.upper() in {"HOST", "DBNAME"}:
            msg = (
                "DATABASE_URL still contains a placeholder hostname (%r). "
                "Paste the full host from Neon (e.g. ep-xxx.region.aws.neon.tech), not the word HOST."
            ) % host
            raise ValueError(msg)
        return v

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        parts = [o.strip() for o in raw.split(",") if o.strip()]
        return parts if parts else ["*"]

    def trusted_host_list(self) -> list[str] | None:
        if not self.trusted_hosts or not self.trusted_hosts.strip():
            return None
        hosts = [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]
        return hosts or None


settings = Settings()
