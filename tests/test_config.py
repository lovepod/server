from __future__ import annotations

import pytest

from app.config import Settings


def test_settings_normalize_postgres_driver() -> None:
    settings = Settings(_env_file=None, database_url="postgresql://user:pass@db.example.com/app")
    assert settings.database_url == "postgresql+psycopg://user:pass@db.example.com/app"


def test_settings_reject_placeholder_database_host() -> None:
    with pytest.raises(ValueError, match="placeholder hostname"):
        Settings(_env_file=None, database_url="postgresql://user:pass@HOST/app")


def test_settings_uppercases_log_level_and_parses_lists() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///./tests.db",
        log_level="debug",
        cors_origins="https://a.example.com, https://b.example.com",
        trusted_hosts="api.example.com, localhost",
    )

    assert settings.log_level == "DEBUG"
    assert settings.cors_origin_list() == ["https://a.example.com", "https://b.example.com"]
    assert settings.trusted_host_list() == ["api.example.com", "localhost"]
    assert "image/png" in settings.allowed_upload_mime_type_set()
    assert settings.message_lease_seconds == 180


def test_settings_defaults_cors_to_wildcard() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///./tests.db", cors_origins=" ")
    assert settings.cors_origin_list() == ["*"]


def test_allowed_upload_mime_type_set_normalizes_parameters() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///./tests.db",
        allowed_upload_mime_types="text/plain; charset=utf-8, image/png",
    )
    assert settings.allowed_upload_mime_type_set() == {"text/plain", "image/png"}
