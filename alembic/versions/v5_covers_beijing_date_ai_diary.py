# -*- coding: utf-8 -*-
"""ai_diary 增加 covers_beijing_date（日记覆盖的北京日历日）

Revision ID: v5_covers_beijing_001
Revises: v4b_step002_001
Create Date: 2026-05-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "v5_covers_beijing_001"
down_revision: Union[str, None] = "v4b_step002_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        insp = sa.inspect(bind)
        cols = [c["name"] for c in insp.get_columns("ai_diary")] if "ai_diary" in insp.get_table_names() else []
        if "covers_beijing_date" in cols:
            return

    op.add_column(
        "ai_diary",
        sa.Column("covers_beijing_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_ai_diary_user_covers_date",
        "ai_diary",
        ["user_id", "covers_beijing_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_diary_user_covers_date", table_name="ai_diary")
    op.drop_column("ai_diary", "covers_beijing_date")
