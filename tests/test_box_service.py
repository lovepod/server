from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.schemas import RegisterBoxRequest, ValidateBoxRequest
from app.services.box_service import BoxService


class ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self._value


def make_settings():
    return SimpleNamespace(box_secret_key_length=8, token_ttl_hours=24)


def test_register_box_returns_generated_secret() -> None:
    db = Mock()
    created_box = SimpleNamespace(secret_key="AB12CD34")
    db.add.side_effect = lambda row: setattr(created_box, "row", row)
    db.refresh.side_effect = lambda row: setattr(row, "secret_key", "AB12CD34")

    service = BoxService(db=db, app_settings=make_settings())

    with patch("app.services.box_service.generate_box_secret_key", return_value="AB12CD34"):
        result = service.register(RegisterBoxRequest(email="test@example.com", name="Living Room"))

    assert result.secret_key == "AB12CD34"
    db.commit.assert_called_once()
    added_box = db.add.call_args[0][0]
    assert added_box.email == "test@example.com"
    assert added_box.name == "Living Room"


def test_register_box_retries_on_integrity_error() -> None:
    db = Mock()
    db.commit.side_effect = [IntegrityError("stmt", "params", "orig"), None]
    db.refresh.side_effect = lambda row: setattr(row, "secret_key", "ZXCV1234")
    service = BoxService(db=db, app_settings=make_settings())

    with patch("app.services.box_service.generate_box_secret_key", side_effect=["DUPL1111", "ZXCV1234"]):
        result = service.register(RegisterBoxRequest(email="test@example.com", name="Kitchen"))

    assert result.secret_key == "ZXCV1234"
    assert db.rollback.call_count == 1
    assert db.commit.call_count == 2


def test_register_box_raises_when_unique_secret_cannot_be_allocated() -> None:
    db = Mock()
    db.commit.side_effect = IntegrityError("stmt", "params", "orig")
    service = BoxService(db=db, app_settings=make_settings())

    with patch("app.services.box_service.generate_box_secret_key", return_value="DUPL1111"):
        with pytest.raises(ServiceUnavailableError, match="Could not allocate unique secret key"):
            service.register(RegisterBoxRequest(email="test@example.com", name="Kitchen"))

    assert db.rollback.call_count == 5


def test_validate_box_reuses_latest_token_and_normalizes_secret() -> None:
    db = Mock()
    box = SimpleNamespace(id=42)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    token = SimpleNamespace(token_uuid="existing-token", expires_at=expires_at, revoked_at=None)
    db.execute.side_effect = [ScalarResult(box), ScalarResult(token)]
    service = BoxService(db=db, app_settings=make_settings())

    result = service.validate(ValidateBoxRequest(secret_key="ab12-cd34"))

    assert result.token == "existing-token"
    assert result.expiresAt == expires_at.isoformat()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_validate_box_creates_token_when_missing() -> None:
    db = Mock()
    box = SimpleNamespace(id=42)
    db.execute.side_effect = [ScalarResult(box), ScalarResult(None), ScalarResult([])]
    db.refresh.side_effect = lambda row: (setattr(row, "token_uuid", "new-token"), setattr(row, "expires_at", datetime.now(timezone.utc) + timedelta(hours=24)))
    service = BoxService(db=db, app_settings=make_settings())

    result = service.validate(ValidateBoxRequest(secret_key="AB12CD34"))

    assert result.token == "new-token"
    assert result.expiresAt is not None
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_validate_box_revokes_expired_tokens_before_issuing_new_one() -> None:
    db = Mock()
    box = SimpleNamespace(id=42)
    expired = SimpleNamespace(
        token_uuid="old-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        revoked_at=None,
    )
    db.execute.side_effect = [ScalarResult(box), ScalarResult(None), ScalarResult([expired])]
    db.refresh.side_effect = lambda row: setattr(row, "expires_at", datetime.now(timezone.utc) + timedelta(hours=24))
    service = BoxService(db=db, app_settings=make_settings())

    service.validate(ValidateBoxRequest(secret_key="AB12CD34"))

    assert expired.revoked_at is not None


def test_validate_box_raises_for_unknown_secret() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(None)
    service = BoxService(db=db, app_settings=make_settings())

    with pytest.raises(NotFoundError, match="Unknown secret key"):
        service.validate(ValidateBoxRequest(secret_key="AB12CD34"))
