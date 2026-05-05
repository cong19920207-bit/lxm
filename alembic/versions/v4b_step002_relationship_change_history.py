# -*- coding: utf-8 -*-
"""STEP-002：创建 relationship_change_history 表（R-L1L3-05 append-only 变更历史）

Revision ID: v4b_step002_001
Revises: v4a_step001_001
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "v4b_step002_001"
down_revision: Union[str, None] = "v4a_step001_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        insp = sa.inspect(bind)
        if "relationship_change_history" in insp.get_table_names():
            return

    op.create_table(
        "relationship_change_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("relationship_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("trigger_source", sa.String(20), nullable=False, server_default="step6"),
        sa.Column("round_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationship.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_relationship_change_history_relationship_id", "relationship_change_history", ["relationship_id"])
    op.create_index("ix_relationship_change_history_user_id", "relationship_change_history", ["user_id"])
    op.create_index("ix_rel_change_user_created", "relationship_change_history", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("relationship_change_history")
