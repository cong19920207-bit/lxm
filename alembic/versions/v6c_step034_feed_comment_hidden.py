# -*- coding: utf-8 -*-
"""STEP-034：评论后台软删标记列 feed_comment.is_hidden

- 扩展：feed_comment.is_hidden TINYINT(1) DEFAULT 0 —— 后台评论软删/隐藏标记
  · 0=正常/1=已隐藏；隐藏后不在用户端 Feed 展示，DB 记录保留，可后台恢复
  · DELETE /api/admin/feed/comments/{id} 走软删（置 1），非物理删除

Revision ID: v6c_step034_001
Revises: v6b_step019_026_001
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v6c_step034_001"
down_revision: Union[str, None] = "v6b_step019_026_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    """幂等辅助：返回目标表已有列集合；离线模式返回空集（不做检测）"""
    if context.is_offline_mode():
        return set()
    bind = op.get_bind()
    insp = inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    cols = _existing_columns("feed_comment")
    if cols and "is_hidden" not in cols:
        op.add_column(
            "feed_comment",
            sa.Column(
                "is_hidden",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
                comment="后台软删标记（0=正常/1=已隐藏），STEP-034 使用",
            ),
        )


def downgrade() -> None:
    cols = _existing_columns("feed_comment")
    if "is_hidden" in cols:
        op.drop_column("feed_comment", "is_hidden")
