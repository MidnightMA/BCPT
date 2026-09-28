"""Initial database schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_settings table
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, index=True, nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), default=True, nullable=False),
        sa.Column("notify_favorites_only", sa.Boolean(), default=False, nullable=False),
        sa.Column("messages_per_page", sa.Integer(), default=10, nullable=False),
        sa.Column("auto_refresh", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # favorite_chats table
    op.create_table(
        "favorite_chats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("chat_type", sa.String(length=50), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "chat_id", name="uq_user_chat_favorite"),
    )

    # cached_chats table
    op.create_table(
        "cached_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True, index=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("chat_type", sa.String(length=50), nullable=False),
        sa.Column("unread_count", sa.Integer(), default=0, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("cached_chats")
    op.drop_table("favorite_chats")
    op.drop_table("user_settings")
