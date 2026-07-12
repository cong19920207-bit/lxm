# -*- coding: utf-8 -*-
"""朋友圈评论展示假数：feed_post.base_comments / comment_multiplier

- 展示评论数 = base_comments × comment_multiplier + 当前用户可见评论条数
- 与点赞 display_likes 同公式；范围复用 feed_base_likes_* / feed_like_multiplier_*
- 历史帖不回填：列默认 base_comments=0、comment_multiplier=1（展示=真实条数）

Revision ID: v6e_display_comments_001
Revises: v6d_reply_to_lxm_001
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v6e_display_comments_001"
down_revision: Union[str, None] = "v6d_reply_to_lxm_001"
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
    cols = _existing_columns("feed_post")
    if cols and "base_comments" not in cols:
        op.add_column(
            "feed_post",
            sa.Column(
                "base_comments",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="默认虚拟评论数（新帖 1–8），固定不变；历史帖默认 0",
            ),
        )
    if cols and "comment_multiplier" not in cols:
        op.add_column(
            "feed_post",
            sa.Column(
                "comment_multiplier",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment=(
                    "评论放大倍率（新帖 1–3），固定不变；仅放大 base_comments；"
                    "展示评论数 = base_comments × comment_multiplier + 真实可见评论条数"
                ),
            ),
        )


def downgrade() -> None:
    cols = _existing_columns("feed_post")
    if "comment_multiplier" in cols:
        op.drop_column("feed_post", "comment_multiplier")
    if "base_comments" in cols:
        op.drop_column("feed_post", "base_comments")
