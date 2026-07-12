# -*- coding: utf-8 -*-
"""STEP-019 / STEP-026：感知队列 Prompt 快照列 + 朋友圈 SSE 广播去重列

- 扩展：agent_aware_queue.{prompt_key, extra_context}
  · prompt_key VARCHAR(32) NULL —— 入队时确定的 Prompt config_key（LIKE_AWARE=prompt_p07；
    READ_AWARE 特殊档=prompt_p14 / 常规档=prompt_p08~p11），消费时直接使用不重算档位
  · extra_context JSON NULL —— 入队附加上下文快照（is_special / snapshot_summary 等）
- 扩展：feed_post.sse_broadcasted TINYINT(1) DEFAULT 0 —— SSE 新帖广播去重标记

Revision ID: v6b_step019_026_001
Revises: v6a_step001_001
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v6b_step019_026_001"
down_revision: Union[str, None] = "v6a_step001_001"
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
    # agent_aware_queue 扩展列
    aware_cols = _existing_columns("agent_aware_queue")
    if aware_cols:  # 表存在才处理（离线模式返回空集则跳过检测）
        if "prompt_key" not in aware_cols:
            op.add_column(
                "agent_aware_queue",
                sa.Column(
                    "prompt_key",
                    sa.String(32),
                    nullable=True,
                    comment="生成使用的 Prompt config_key（入队时确定）",
                ),
            )
        if "extra_context" not in aware_cols:
            op.add_column(
                "agent_aware_queue",
                sa.Column(
                    "extra_context",
                    sa.JSON(),
                    nullable=True,
                    comment="入队附加上下文快照（is_special / snapshot_summary 等）",
                ),
            )

    # feed_post 扩展列
    feed_cols = _existing_columns("feed_post")
    if feed_cols and "sse_broadcasted" not in feed_cols:
        op.add_column(
            "feed_post",
            sa.Column(
                "sse_broadcasted",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
                comment="SSE 新帖广播去重标记（0=未广播/1=已广播），STEP-026 使用",
            ),
        )


def downgrade() -> None:
    feed_cols = _existing_columns("feed_post")
    if "sse_broadcasted" in feed_cols:
        op.drop_column("feed_post", "sse_broadcasted")

    aware_cols = _existing_columns("agent_aware_queue")
    if "extra_context" in aware_cols:
        op.drop_column("agent_aware_queue", "extra_context")
    if "prompt_key" in aware_cols:
        op.drop_column("agent_aware_queue", "prompt_key")
