from __future__ import annotations

import logging
import base64
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UnauthorizedError,
)
from app.image_utils import compress_image, decompress_image, optimize_for_embedded_display
from app.models import Box, Message, Token
from app.schemas import MessageUploadResponse
from app.utils.file_utils import sanitize_upload_filename

logger = logging.getLogger(__name__)


def _normalize_secret_key(value: str) -> str:
    return value.strip().replace("-", "").upper()


def _sniff_image_mime(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(raw) >= 3 and raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return None


def _effective_stored_content_type(raw: bytes, content_type: str | None) -> str:
    """
    Normalize MIME for storage so clients that omit or mislabel types (e.g. PNG as octet-stream)
    still get a correct Content-Type when the box reads the message.
    """
    ct = (content_type or "").strip()
    low = ct.lower()
    if low in ("image/x-png", "image/png"):
        return "image/png"
    if low in ("image/jpg", "image/pjpeg", "image/jpeg"):
        return "image/jpeg"
    if low == "image/gif":
        return "image/gif"
    if not ct or low in (
        "application/octet-stream",
        "binary/octet-stream",
    ):
        sniffed = _sniff_image_mime(raw)
        if sniffed:
            return sniffed
    return ct or "application/octet-stream"


class MessageService:
    def __init__(self, db: Session, app_settings: Settings) -> None:
        self._db = db
        self._settings = app_settings

    def upload(
        self,
        api_token: str | None,
        raw: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> MessageUploadResponse:
        if not api_token or not api_token.strip():
            raise BadRequestError("Missing x-api-key")

        now = datetime.now(timezone.utc)
        tok = self._require_active_token(api_token.strip(), now)

        if len(raw) > self._settings.max_upload_bytes:
            raise PayloadTooLargeError("File too large")

        box = self._db.get(Box, tok.box_id)
        if box is None:
            raise NotFoundError("Box not found")

        stored_content_type = _effective_stored_content_type(raw, content_type)
        if not self._is_allowed_content_type(stored_content_type):
            raise UnsupportedMediaTypeError(f"Unsupported content type: {stored_content_type}")

        # Embedded clients poll via JSON/base64; keep images small enough to parse safely on-device.
        # This also ensures image dimensions fit the display (firmware PNG path does not scale).
        try:
            optimized_raw, optimized_type = optimize_for_embedded_display(
                raw,
                stored_content_type,
                max_w=320,
                max_h=240,
                target_max_bytes=60_000,
            )
            if optimized_raw is not raw:
                raw = optimized_raw
                stored_content_type = optimized_type
        except Exception:
            logger.exception("optimize_for_embedded_display failed; storing original bytes")

        try:
            compressed = compress_image(raw)
        except Exception:
            logger.exception("compress_image failed")
            # This is usually an unexpected runtime dependency issue; avoid a generic 500.
            raise BadRequestError("Could not process payload") from None

        msg = Message(
            box_id=box.id,
            file_name=sanitize_upload_filename(filename),
            file_type=stored_content_type,
            message_uuid=str(uuid.uuid4()),
            size=len(raw),
            data=compressed,
        )
        tok.last_used_at = now
        self._db.add(msg)
        self._db.commit()
        return MessageUploadResponse()

    def upload_base64(
        self,
        api_token: str | None,
        data_base64: str,
        filename: str | None,
        content_type: str | None,
    ) -> MessageUploadResponse:
        try:
            raw = base64.b64decode(data_base64, validate=True)
        except Exception:
            raise BadRequestError("Invalid base64 payload") from None
        return self.upload(
            api_token=api_token,
            raw=raw,
            filename=filename,
            content_type=content_type,
        )

    def upload_text(
        self,
        api_token: str | None,
        text: str,
        filename: str | None,
    ) -> MessageUploadResponse:
        raw = text.encode("utf-8")
        name = (filename or "").strip() or "message.txt"
        return self.upload(
            api_token=api_token,
            raw=raw,
            filename=name,
            content_type="text/plain; charset=utf-8",
        )

    def read_latest_jpeg(self, secret_key: str | None) -> bytes:
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_pending_message(box.id)

        try:
            return decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

    def read_latest_blob(self, secret_key: str | None) -> tuple[bytes, str]:
        """
        Returns decompressed stored bytes + stored MIME type.
        Works for JPEG, GIF, text, and any other binary we store in the `message` table.
        """
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_pending_message(box.id)
        self._mark_message_delivered(msg)

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None
        self._db.commit()
        return blob, msg.file_type

    def lease_next_message(
        self, secret_key: str | None
    ) -> tuple[str, str, str, str | None, str | None, str | None, str | None]:
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        now = datetime.now(timezone.utc)
        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_available_message_for_lease(box.id, now)

        lease_uuid = str(uuid.uuid4())
        lease_expires_at = now + timedelta(seconds=self._settings.message_lease_seconds)
        msg.lease_uuid = lease_uuid
        msg.leased_at = now
        msg.lease_expires_at = lease_expires_at

        ft = (msg.file_type or "").strip().lower()
        text_payload: str | None = None
        data_base64: str | None = None

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        if ft.startswith("text/"):
            try:
                text_payload = blob.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise BadRequestError("Text message is not valid UTF-8") from exc
        else:
            data_base64 = base64.b64encode(blob).decode("ascii")

        self._mark_message_delivered(msg, now)
        self._db.commit()
        return (
            msg.message_uuid,
            lease_uuid,
            lease_expires_at.isoformat(),
            msg.file_type,
            msg.file_name,
            data_base64,
            text_payload,
        )

    def read_latest_blob_base64(
        self, secret_key: str | None
    ) -> tuple[str, str, str | None, str | None]:
        """
        Returns (file_type, data_base64, file_name, message_uuid).
        - file_type is used by firmware to decide what to do (JPEG/GIF/event).
        """
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_pending_message(box.id)
        self._mark_message_delivered(msg)

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        self._db.commit()
        file_type = msg.file_type
        data_base64 = base64.b64encode(blob).decode("ascii")
        return file_type, data_base64, msg.file_name, msg.message_uuid

    def read_latest_text_message(
        self, secret_key: str | None
    ) -> tuple[str, str, str | None, str | None]:
        """
        Peek at the latest message: if it is text/*, return UTF-8 text and metadata.
        If the queue is empty → NotFoundError('No message for this box').
        If the latest message is not text → NotFoundError('No text message').
        """
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_pending_message(box.id)

        ft = (msg.file_type or "").strip().lower()
        if not ft.startswith("text/"):
            raise NotFoundError("No text message")

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BadRequestError("Text message is not valid UTF-8") from exc

        self._mark_message_delivered(msg)
        self._db.commit()
        return msg.file_type or "text/plain", text, msg.file_name, msg.message_uuid

    def consume_latest_blob_base64(
        self, secret_key: str | None
    ) -> tuple[str, str, str | None, str | None]:
        """
        Read the latest message for the given box and DELETE it.
        This enables "single display" semantics: after a successful read,
        the same message won't be returned on next polls.
        """
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)
        msg = self._get_next_pending_message(box.id)
        self._mark_message_delivered(msg)

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        file_type = msg.file_type
        data_base64 = base64.b64encode(blob).decode("ascii")
        file_name = msg.file_name
        message_uuid = msg.message_uuid

        msg.consumed_at = datetime.now(timezone.utc)
        self._db.commit()

        return file_type, data_base64, file_name, message_uuid

    def acknowledge_message(self, secret_key: str | None, message_uuid: str, lease_id: str | None = None) -> None:
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")
        if not message_uuid or not message_uuid.strip():
            raise BadRequestError("Missing messageUuid")

        sk = _normalize_secret_key(secret_key)
        box = self._get_box_by_secret(sk)

        q_msg = (
            select(Message)
            .where(
                Message.box_id == box.id,
                Message.message_uuid == message_uuid.strip(),
                Message.consumed_at.is_(None),
                Message.acknowledged_at.is_(None),
            )
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("Message not found")

        active_lease = msg.lease_uuid and msg.lease_expires_at and msg.lease_expires_at > datetime.now(timezone.utc)
        if active_lease and (not lease_id or lease_id.strip() != msg.lease_uuid):
            raise UnauthorizedError("Lease mismatch")

        msg.acknowledged_at = datetime.now(timezone.utc)
        msg.lease_uuid = None
        msg.leased_at = None
        msg.lease_expires_at = None
        self._db.commit()

    def _is_allowed_content_type(self, content_type: str) -> bool:
        normalized = content_type.split(";", 1)[0].strip().lower()
        return normalized in self._settings.allowed_upload_mime_type_set()

    def _require_active_token(self, token_value: str, now: datetime) -> Token:
        q = select(Token).where(Token.token_uuid == token_value)
        tok = self._db.execute(q).scalar_one_or_none()
        if tok is None or tok.revoked_at is not None:
            raise UnauthorizedError("Invalid API token")
        if tok.expires_at <= now:
            tok.revoked_at = now
            self._db.commit()
            raise UnauthorizedError("Expired API token")
        return tok

    def _get_box_by_secret(self, secret_key: str) -> Box:
        q_box = select(Box).where(Box.secret_key == secret_key)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")
        return box

    def _get_next_pending_message(self, box_id: int) -> Message:
        q_msg = (
            select(Message)
            .where(
                Message.box_id == box_id,
                Message.acknowledged_at.is_(None),
                Message.consumed_at.is_(None),
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")
        return msg

    def _get_next_available_message_for_lease(self, box_id: int, now: datetime) -> Message:
        q_msg = (
            select(Message)
            .where(
                Message.box_id == box_id,
                Message.acknowledged_at.is_(None),
                Message.consumed_at.is_(None),
                ((Message.lease_expires_at.is_(None)) | (Message.lease_expires_at <= now)),
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")
        return msg

    def _mark_message_delivered(self, msg: Message, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        msg.delivery_attempts = (msg.delivery_attempts or 0) + 1
        if msg.first_delivered_at is None:
            msg.first_delivered_at = now
        msg.last_delivered_at = now
