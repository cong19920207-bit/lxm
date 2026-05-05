# -*- coding: utf-8 -*-
"""STEP-001：relationship 表新增 9 个扩展字段（记忆写回 + Future 槽）

Revision ID: v4a_step001_001
Revises: v3a_td020_001
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v4a_step001_001"
down_revision: Union[str, None] = "v3a_td020_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 需要新增的列定义
_NEW_COLUMNS = [
    ("relation_description", sa.Text(), None),
    ("user_real_name", sa.String(50), None),
    ("user_hobby_name", sa.String(50), None),
    ("user_description", sa.Text(), None),
    ("character_purpose", sa.Text(), None),
    ("character_attitude", sa.Text(), None),
    ("future_timestamp", sa.Integer(), None),
    ("future_action", sa.String(200), None),
    ("proactive_times", sa.Integer(), "0"),
]


def upgrade() -> None:
    if context.is_offline_mode():
        for col_name, col_type, server_default in _NEW_COLUMNS:
            op.add_column(
                "relationship",
                sa.Column(col_name, col_type, nullable=True, server_default=server_default),
            )
        return

    bind = op.get_bind()
    insp = inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("relationship")}

    for col_name, col_type, server_default in _NEW_COLUMNS:
        if col_name not in existing_columns:
            op.add_column(
                "relationship",
                sa.Column(col_name, col_type, nullable=True, server_default=server_default),
            )


def downgrade() -> None:
    if context.is_offline_mode():
        for col_name, _, _ in reversed(_NEW_COLUMNS):
            op.drop_column("relationship", col_name)
        return

    bind = op.get_bind()
    insp = inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("relationship")}

    for col_name, _, _ in reversed(_NEW_COLUMNS):
        if col_name in existing_columns:
            op.drop_column("relationship", col_name)
