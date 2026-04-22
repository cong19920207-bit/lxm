# -*- coding: utf-8 -*-
"""TD-016 V2-A：conversation_log / emotion_log 增加可空 round_id

增量迁移：仅 ADD 可空列，无数据回填；不删除、不重命名 emotion_label。
回滚：downgrade 按列存在性 DROP（先 emotion_log 后 conversation_log）。

若已通过 scripts/migrate_td016_round_id.sql 手工加列，可执行：
  alembic stamp td016_v2a_001
本 revision 的 upgrade 对已存在 round_id 的表会跳过 ADD，避免重复报错。

Revision ID: td016_v2a_001
Revises:
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "td016_v2a_001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 离线生成 SQL（alembic upgrade --sql）无 connection，直接输出 ADD
    if context.is_offline_mode():
        op.add_column(
            "conversation_log",
            sa.Column(
                "round_id",
                sa.String(length=36),
                nullable=True,
                comment="TD-016：一轮多 user+assistant 共享 UUID",
            ),
        )
        op.add_column(
            "emotion_log",
            sa.Column(
                "round_id",
                sa.String(length=36),
                nullable=True,
                comment="TD-016：与本轮 conversation_log 相同 round_id",
            ),
        )
        return

    bind = op.get_bind()
    insp = inspect(bind)

    if insp.has_table("conversation_log"):
        cols = {c["name"] for c in insp.get_columns("conversation_log")}
        if "round_id" not in cols:
            op.add_column(
                "conversation_log",
                sa.Column(
                    "round_id",
                    sa.String(length=36),
                    nullable=True,
                    comment="TD-016：一轮多 user+assistant 共享 UUID",
                ),
            )

    if insp.has_table("emotion_log"):
        cols = {c["name"] for c in insp.get_columns("emotion_log")}
        if "round_id" not in cols:
            op.add_column(
                "emotion_log",
                sa.Column(
                    "round_id",
                    sa.String(length=36),
                    nullable=True,
                    comment="TD-016：与本轮 conversation_log 相同 round_id",
                ),
            )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_column("emotion_log", "round_id")
        op.drop_column("conversation_log", "round_id")
        return

    bind = op.get_bind()
    insp = inspect(bind)

    if insp.has_table("emotion_log"):
        cols = {c["name"] for c in insp.get_columns("emotion_log")}
        if "round_id" in cols:
            op.drop_column("emotion_log", "round_id")

    if insp.has_table("conversation_log"):
        cols = {c["name"] for c in insp.get_columns("conversation_log")}
        if "round_id" in cols:
            op.drop_column("conversation_log", "round_id")
