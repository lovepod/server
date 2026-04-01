"""prod hardening baseline

Revision ID: 20260401_0001
Revises:
Create Date: 2026-04-01 00:00:00
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "box"):
        op.create_table(
            "box",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("secret_key", sa.String(length=255), nullable=False, unique=True),
        )

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "token"):
        op.create_table(
            "token",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("box_id", sa.BigInteger(), sa.ForeignKey("box.id", ondelete="CASCADE"), nullable=False),
            sa.Column("uuid", sa.String(length=255), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )
    else:
        with op.batch_alter_table("token") as batch_op:
            if not _has_column(inspector, "token", "expires_at"):
                batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "token", "last_used_at"):
                batch_op.add_column(sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "token", "revoked_at"):
                batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

        token_table = sa.table(
            "token",
            sa.column("expires_at", sa.DateTime(timezone=True)),
        )
        bind.execute(
            token_table.update()
            .where(token_table.c.expires_at.is_(None))
            .values(expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "token", "ix_token_box_id_expires_at"):
        op.create_index("ix_token_box_id_expires_at", "token", ["box_id", "expires_at"], unique=False)
    if not _has_index(inspector, "token", "ix_token_uuid_active"):
        op.create_index("ix_token_uuid_active", "token", ["uuid", "revoked_at", "expires_at"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "message"):
        op.create_table(
            "message",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("box_id", sa.BigInteger(), sa.ForeignKey("box.id", ondelete="CASCADE"), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_type", sa.String(length=255), nullable=False),
            sa.Column("uuid", sa.String(length=255), nullable=False),
            sa.Column("size", sa.BigInteger(), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        )
    else:
        with op.batch_alter_table("message") as batch_op:
            if not _has_column(inspector, "message", "delivery_attempts"):
                batch_op.add_column(
                    sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0")
                )
            if not _has_column(inspector, "message", "first_delivered_at"):
                batch_op.add_column(sa.Column("first_delivered_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "message", "last_delivered_at"):
                batch_op.add_column(sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "message", "acknowledged_at"):
                batch_op.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "message", "consumed_at"):
                batch_op.add_column(sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "message", "ix_message_box_queue"):
        op.create_index(
            "ix_message_box_queue",
            "message",
            ["box_id", "acknowledged_at", "consumed_at", "created_at"],
            unique=False,
        )
    if not _has_index(inspector, "message", "ix_message_uuid"):
        op.create_index("ix_message_uuid", "message", ["uuid"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "message"):
        if _has_index(inspector, "message", "ix_message_uuid"):
            op.drop_index("ix_message_uuid", table_name="message")
        if _has_index(inspector, "message", "ix_message_box_queue"):
            op.drop_index("ix_message_box_queue", table_name="message")
        op.drop_table("message")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "token"):
        if _has_index(inspector, "token", "ix_token_uuid_active"):
            op.drop_index("ix_token_uuid_active", table_name="token")
        if _has_index(inspector, "token", "ix_token_box_id_expires_at"):
            op.drop_index("ix_token_box_id_expires_at", table_name="token")
        op.drop_table("token")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "box"):
        op.drop_table("box")
