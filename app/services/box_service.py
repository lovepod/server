from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.models import Box, Token
from app.schemas import RegisterBoxRequest, RegisterBoxResponse, ValidateBoxRequest, ValidateBoxResponse
from app.secret_key_util import generate_box_secret_key


class BoxService:
    def __init__(self, db: Session, app_settings: Settings) -> None:
        self._db = db
        self._settings = app_settings

    def register(self, body: RegisterBoxRequest) -> RegisterBoxResponse:
        email = str(body.email)
        name = body.name
        length = self._settings.box_secret_key_length

        for _ in range(5):
            secret = generate_box_secret_key(length)
            row = Box(name=name, email=email, secret_key=secret)
            self._db.add(row)
            try:
                self._db.commit()
                self._db.refresh(row)
                return RegisterBoxResponse(secret_key=row.secret_key)
            except IntegrityError:
                self._db.rollback()

        raise ServiceUnavailableError("Could not allocate unique secret key")

    def validate(self, body: ValidateBoxRequest) -> ValidateBoxResponse:
        q = select(Box).where(Box.secret_key == _normalize_secret_key(body.secret_key))
        box = self._db.execute(q).scalar_one_or_none()
        if box is None:
            raise NotFoundError("Unknown secret key")

        now = datetime.now(timezone.utc)
        q_token = (
            select(Token)
            .where(
                Token.box_id == box.id,
                Token.revoked_at.is_(None),
                Token.expires_at > now,
            )
            .order_by(Token.expires_at.desc(), Token.created_at.desc())
            .limit(1)
        )
        tok = self._db.execute(q_token).scalar_one_or_none()
        if tok is not None:
            return ValidateBoxResponse(token=tok.token_uuid, expiresAt=tok.expires_at.isoformat())

        q_old_tokens = select(Token).where(Token.box_id == box.id, Token.revoked_at.is_(None))
        for old_token in self._db.execute(q_old_tokens).scalars():
            if old_token.expires_at <= now:
                old_token.revoked_at = now

        token = Token(
            box_id=box.id,
            token_uuid=str(uuid.uuid4()),
            expires_at=now + timedelta(hours=self._settings.token_ttl_hours),
        )
        self._db.add(token)
        self._db.commit()
        self._db.refresh(token)
        return ValidateBoxResponse(token=token.token_uuid, expiresAt=token.expires_at.isoformat())


def _normalize_secret_key(value: str) -> str:
    return value.strip().replace("-", "").upper()
