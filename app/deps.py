"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db import get_db
from app.services.box_service import BoxService
from app.services.message_service import MessageService


def get_settings() -> Settings:
    """Singleton settings instance (suitable for `Depends`)."""
    return settings


def get_box_service(
    db: Session = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> BoxService:
    return BoxService(db=db, app_settings=app_settings)


def get_message_service(
    db: Session = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> MessageService:
    return MessageService(db=db, app_settings=app_settings)
