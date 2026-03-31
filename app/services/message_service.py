from __future__ import annotations

import logging
import base64
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
)
from app.image_utils import compress_image, decompress_image
from app.models import Box, Message, Token
from app.schemas import MessageUploadResponse
from app.utils.file_utils import sanitize_upload_filename

logger = logging.getLogger(__name__)


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

        token_value = api_token.strip()
        q = select(Token).where(Token.token_uuid == token_value)
        tok = self._db.execute(q).scalar_one_or_none()
        if tok is None:
            raise UnauthorizedError("Invalid API token")

        if len(raw) > self._settings.max_upload_bytes:
            raise PayloadTooLargeError("File too large")

        box = self._db.get(Box, tok.box_id)
        if box is None:
            raise NotFoundError("Box not found")

        try:
            compressed = compress_image(raw)
        except Exception:
            logger.exception("compress_image failed")
            raise BadRequestError("Could not process image") from None

        msg = Message(
            box_id=box.id,
            file_name=sanitize_upload_filename(filename),
            file_type=content_type or "application/octet-stream",
            message_uuid=str(uuid.uuid4()),
            size=len(raw),
            data=compressed,
        )
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

    def read_latest_jpeg(self, secret_key: str | None) -> bytes:
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = secret_key.strip()
        q_box = select(Box).where(Box.secret_key == sk)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")

        q_msg = (
            select(Message)
            .where(Message.box_id == box.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")

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

        sk = secret_key.strip()
        q_box = select(Box).where(Box.secret_key == sk)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")

        q_msg = (
            select(Message)
            .where(Message.box_id == box.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")

        try:
            return decompress_image(msg.data), msg.file_type
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

    def read_latest_blob_base64(
        self, secret_key: str | None
    ) -> tuple[str, str, str | None, str | None]:
        """
        Returns (file_type, data_base64, file_name, message_uuid).
        - file_type is used by firmware to decide what to do (JPEG/GIF/event).
        """
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")

        sk = secret_key.strip()
        q_box = select(Box).where(Box.secret_key == sk)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")

        q_msg = (
            select(Message)
            .where(Message.box_id == box.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        file_type = msg.file_type
        data_base64 = base64.b64encode(blob).decode("ascii")
        return file_type, data_base64, msg.file_name, msg.message_uuid

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

        sk = secret_key.strip()
        q_box = select(Box).where(Box.secret_key == sk)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")

        q_msg = (
            select(Message)
            .where(Message.box_id == box.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("No message for this box")

        try:
            blob = decompress_image(msg.data)
        except Exception:
            logger.exception("decompress_image failed for message id=%s", msg.id)
            raise InternalError("Could not read stored message") from None

        file_type = msg.file_type
        data_base64 = base64.b64encode(blob).decode("ascii")
        file_name = msg.file_name
        message_uuid = msg.message_uuid

        # Consume: delete row so subsequent reads/polls don't show it again.
        self._db.delete(msg)
        self._db.commit()

        return file_type, data_base64, file_name, message_uuid

    def acknowledge_message(self, secret_key: str | None, message_uuid: str) -> None:
        if not secret_key or not secret_key.strip():
            raise BadRequestError("Missing secret-key")
        if not message_uuid or not message_uuid.strip():
            raise BadRequestError("Missing messageUuid")

        sk = secret_key.strip()
        q_box = select(Box).where(Box.secret_key == sk)
        box = self._db.execute(q_box).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown box")

        q_msg = (
            select(Message)
            .where(Message.box_id == box.id, Message.message_uuid == message_uuid.strip())
            .limit(1)
        )
        msg = self._db.execute(q_msg).scalar_one_or_none()
        if msg is None:
            raise NotFoundError("Message not found")

        self._db.delete(msg)
        self._db.commit()
