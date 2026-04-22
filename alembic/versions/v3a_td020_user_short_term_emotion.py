# -*- coding: utf-8 -*-
"""TD-020 V3-A：user_short_term_emotion 表（用户短期情绪 DB 真相源）

Revision ID: v3a_td020_001
Revises: td016_v2a_001
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v3a_td020_001"
down_revision: Union[str, None] = "td016_v2a_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "user_short_term_emotion",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("emotion_label", sa.String(length=50), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        return

    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("user_short_term_emotion"):
        op.create_table(
            "user_short_term_emotion",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("emotion_label", sa.String(length=50), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_table("user_short_term_emotion")
        return

    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("user_short_term_emotion"):
        op.drop_table("user_short_term_emotion")
