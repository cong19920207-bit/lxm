# -*- coding: utf-8 -*-
"""朋友圈连续回复展示：feed_comment.reply_to_lxm

- 扩展：feed_comment.reply_to_lxm TINYINT(1) DEFAULT 0
  · 0=普通发评（💬）；1=用户点击林小梦回复后发出
  · 仅影响 H5 评论区落款「我回复 林小梦：」；LLM-05 语义不变

Revision ID: v6d_reply_to_lxm_001
Revises: v6c_step034_001
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v6d_reply_to_lxm_001"
down_revision: Union[str, None] = "v6c_step034_001"
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
    if cols and "reply_to_lxm" not in cols:
        op.add_column(
            "feed_comment",
            sa.Column(
                "reply_to_lxm",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
                comment="是否回复林小梦（0=普通发评/1=点小梦回复发出）；H5 展示「我回复 林小梦」",
            ),
        )


def downgrade() -> None:
    cols = _existing_columns("feed_comment")
    if "reply_to_lxm" in cols:
        op.drop_column("feed_comment", "reply_to_lxm")
