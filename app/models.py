from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Box(Base):
    __tablename__ = "box"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    tokens: Mapped[list[Token]] = relationship(back_populates="box")
    messages: Mapped[list[Message]] = relationship(back_populates="box")


class Token(Base):
    __tablename__ = "token"
    __table_args__ = (
        Index("ix_token_box_id_expires_at", "box_id", "expires_at"),
        Index("ix_token_uuid_active", "uuid", "revoked_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(ForeignKey("box.id", ondelete="CASCADE"), nullable=False)
    # stupac u bazi ostaje "uuid" (kompatibilno s postojećom shemom)
    token_uuid: Mapped[str] = mapped_column("uuid", String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    box: Mapped[Box] = relationship(back_populates="tokens")


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("ix_message_box_queue", "box_id", "acknowledged_at", "consumed_at", "created_at"),
        Index("ix_message_uuid", "uuid", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(ForeignKey("box.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(255), nullable=False)
    message_uuid: Mapped[str] = mapped_column("uuid", String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    box: Mapped[Box] = relationship(back_populates="messages")
