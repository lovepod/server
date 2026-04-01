from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
    UnsupportedMediaTypeError,
)
from app.services.message_service import MessageService, _effective_stored_content_type, _sniff_image_mime


class ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def make_settings(max_upload_bytes: int = 1024):
    return SimpleNamespace(
        max_upload_bytes=max_upload_bytes,
        allowed_upload_mime_type_set=lambda: {
            "image/png",
            "image/jpeg",
            "image/gif",
            "text/plain",
            "application/octet-stream",
            "binary/octet-stream",
        },
    )


def make_service(db: Mock, max_upload_bytes: int = 1024) -> MessageService:
    return MessageService(db=db, app_settings=make_settings(max_upload_bytes=max_upload_bytes))


def make_message(**kwargs):
    defaults = {
        "id": 7,
        "file_type": "image/png",
        "file_name": "message.png",
        "message_uuid": "msg-1",
        "data": b"compressed",
        "delivery_attempts": 0,
        "first_delivered_at": None,
        "last_delivered_at": None,
        "acknowledged_at": None,
        "consumed_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_token(**kwargs):
    defaults = {
        "box_id": 9,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "revoked_at": None,
        "last_used_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_sniff_image_mime_detects_supported_headers() -> None:
    assert _sniff_image_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert _sniff_image_mime(b"\xff\xd8\xffrest") == "image/jpeg"
    assert _sniff_image_mime(b"GIF89arest") == "image/gif"
    assert _sniff_image_mime(b"plain-text") is None


def test_effective_stored_content_type_normalizes_common_values() -> None:
    assert _effective_stored_content_type(b"data", "image/x-png") == "image/png"
    assert _effective_stored_content_type(b"data", "image/pjpeg") == "image/jpeg"
    assert _effective_stored_content_type(b"GIF89a...", "application/octet-stream") == "image/gif"
    assert _effective_stored_content_type(b"hello", None) == "application/octet-stream"


def test_upload_rejects_missing_api_key() -> None:
    with pytest.raises(BadRequestError, match="Missing x-api-key"):
        make_service(Mock()).upload(None, b"hello", "hello.txt", "text/plain")


def test_upload_rejects_unknown_token() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(None)

    with pytest.raises(UnauthorizedError, match="Invalid API token"):
        make_service(db).upload("bad-token", b"hello", "hello.txt", "text/plain")


def test_upload_rejects_large_payloads() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(make_token(box_id=1))

    with pytest.raises(PayloadTooLargeError, match="File too large"):
        make_service(db, max_upload_bytes=3).upload("good-token", b"hello", "hello.txt", "text/plain")


def test_upload_rejects_missing_box() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(make_token(box_id=1))
    db.get.return_value = None

    with pytest.raises(NotFoundError, match="Box not found"):
        make_service(db).upload("good-token", b"hello", "hello.txt", "text/plain")


def test_upload_persists_compressed_message_and_sanitizes_filename() -> None:
    db = Mock()
    token = make_token(box_id=9)
    db.execute.return_value = ScalarResult(token)
    db.get.return_value = SimpleNamespace(id=9)
    service = make_service(db)

    with patch("app.services.message_service.compress_image", return_value=b"zip"), patch(
        "app.services.message_service.uuid.uuid4", return_value="fixed-uuid"
    ):
        response = service.upload("good-token", b"\x89PNG\r\n\x1a\nraw", "../secret.png", "application/octet-stream")

    assert response.uuid is None
    db.add.assert_called_once()
    db.commit.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.file_name == "secret.png"
    assert added.file_type == "image/png"
    assert added.size == len(b"\x89PNG\r\n\x1a\nraw")
    assert added.data == b"zip"
    assert added.message_uuid == "fixed-uuid"
    assert token.last_used_at is not None


def test_upload_wraps_compression_failures() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(make_token(box_id=9))
    db.get.return_value = SimpleNamespace(id=9)
    service = make_service(db)

    with patch("app.services.message_service.compress_image", side_effect=RuntimeError("boom")):
        with pytest.raises(BadRequestError, match="Could not process image"):
            service.upload("good-token", b"abc", "x.bin", "application/octet-stream")


def test_upload_base64_decodes_and_delegates() -> None:
    service = make_service(Mock())

    with patch.object(service, "upload", return_value=SimpleNamespace()) as upload:
        service.upload_base64("token", base64.b64encode(b"hello").decode("ascii"), "hello.txt", "text/plain")

    upload.assert_called_once_with(
        api_token="token",
        raw=b"hello",
        filename="hello.txt",
        content_type="text/plain",
    )


def test_upload_base64_rejects_invalid_payload() -> None:
    with pytest.raises(BadRequestError, match="Invalid base64 payload"):
        make_service(Mock()).upload_base64("token", "not-base64", "x.bin", "application/octet-stream")


def test_upload_rejects_expired_token() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(make_token(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))

    with pytest.raises(UnauthorizedError, match="Expired API token"):
        make_service(db).upload("expired-token", b"hello", "hello.txt", "text/plain")

    db.commit.assert_called_once()


def test_upload_rejects_disallowed_content_type() -> None:
    db = Mock()
    db.execute.return_value = ScalarResult(make_token())
    db.get.return_value = SimpleNamespace(id=9)

    with pytest.raises(UnsupportedMediaTypeError, match="Unsupported content type"):
        make_service(db).upload("good-token", b"<svg/>", "vector.svg", "image/svg+xml")


def test_upload_text_uses_default_filename_and_plain_text_mime() -> None:
    service = make_service(Mock())

    with patch.object(service, "upload", return_value=SimpleNamespace()) as upload:
        service.upload_text("token", "Hello love", None)

    upload.assert_called_once_with(
        api_token="token",
        raw=b"Hello love",
        filename="message.txt",
        content_type="text/plain; charset=utf-8",
    )


def test_read_latest_jpeg_normalizes_secret_and_decompresses() -> None:
    db = Mock()
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(make_message())]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value=b"jpeg-bytes") as decompress:
        payload = service.read_latest_jpeg("ab12-cd34")

    assert payload == b"jpeg-bytes"
    decompress.assert_called_once_with(b"compressed")


def test_read_latest_blob_returns_bytes_and_mime() -> None:
    db = Mock()
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(make_message(file_type="image/gif"))]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value=b"gif-bytes"):
        payload, mime = service.read_latest_blob("AB12-CD34")

    assert payload == b"gif-bytes"
    assert mime == "image/gif"
    db.commit.assert_called_once()


def test_read_latest_blob_wraps_decompression_failures() -> None:
    db = Mock()
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(make_message())]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", side_effect=RuntimeError("boom")):
        with pytest.raises(InternalError, match="Could not read stored message"):
            service.read_latest_blob("AB12CD34")


def test_read_latest_blob_base64_returns_metadata() -> None:
    db = Mock()
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(make_message(message_uuid="msg-42"))]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value=b"hello"):
        mime, data_base64, file_name, message_uuid = service.read_latest_blob_base64("AB12CD34")

    assert mime == "image/png"
    assert data_base64 == base64.b64encode(b"hello").decode("ascii")
    assert file_name == "message.png"
    assert message_uuid == "msg-42"
    db.commit.assert_called_once()


def test_read_latest_text_message_returns_utf8_text() -> None:
    db = Mock()
    message = make_message(file_type="text/plain; charset=utf-8", file_name="message.txt")
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(message)]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value="Volim te".encode("utf-8")):
        mime, text, file_name, message_uuid = service.read_latest_text_message("ab12-cd34")

    assert mime == "text/plain; charset=utf-8"
    assert text == "Volim te"
    assert file_name == "message.txt"
    assert message_uuid == "msg-1"
    assert message.delivery_attempts == 1
    db.commit.assert_called_once()


def test_read_latest_text_message_rejects_binary_latest_message() -> None:
    db = Mock()
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(make_message(file_type="image/jpeg"))]
    service = make_service(db)

    with pytest.raises(NotFoundError, match="No text message"):
        service.read_latest_text_message("AB12CD34")


def test_consume_latest_blob_base64_marks_message_consumed() -> None:
    db = Mock()
    message = make_message(message_uuid="msg-99")
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(message)]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value=b"hello"):
        mime, data_base64, _, message_uuid = service.consume_latest_blob_base64("AB12CD34")

    assert mime == "image/png"
    assert data_base64 == base64.b64encode(b"hello").decode("ascii")
    assert message_uuid == "msg-99"
    assert message.consumed_at is not None
    db.commit.assert_called_once()


def test_acknowledge_message_marks_specific_message_acknowledged() -> None:
    db = Mock()
    message = make_message(message_uuid="msg-77")
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(message)]
    service = make_service(db)

    service.acknowledge_message("AB12-CD34", "msg-77")

    assert message.acknowledged_at is not None
    db.commit.assert_called_once()


def test_acknowledge_message_rejects_missing_uuid() -> None:
    with pytest.raises(BadRequestError, match="Missing messageUuid"):
        make_service(Mock()).acknowledge_message("AB12CD34", "")


def test_reads_use_fifo_order_not_latest_order() -> None:
    db = Mock()
    older = make_message(id=1, message_uuid="older")
    db.execute.side_effect = [ScalarResult(SimpleNamespace(id=1)), ScalarResult(older)]
    service = make_service(db)

    with patch("app.services.message_service.decompress_image", return_value=b"hello"):
        _, _, _, message_uuid = service.read_latest_blob_base64("AB12CD34")

    assert message_uuid == "older"
    assert older.delivery_attempts == 1
