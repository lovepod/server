from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, func
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(ForeignKey("box.id", ondelete="CASCADE"), nullable=False)
    # stupac u bazi ostaje "uuid" (kompatibilno s postojećom shemom)
    token_uuid: Mapped[str] = mapped_column("uuid", String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    box: Mapped[Box] = relationship(back_populates="tokens")


class Message(Base):
    __tablename__ = "message"

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

    box: Mapped[Box] = relationship(back_populates="messages")
