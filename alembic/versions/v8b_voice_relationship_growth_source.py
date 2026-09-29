# -*- coding: utf-8 -*-
"""实时语音 STEP-002：成长记录来源幂等字段。

Revision ID: v8b_voice_growth_src_001
Revises: v8a_voice_draft_rev_001
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v8b_voice_growth_src_001"
down_revision: Union[str, None] = "v8a_voice_draft_rev_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "relationship_growth_log",
        sa.Column("source_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "relationship_growth_log",
        sa.Column("source_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "relationship_growth_log",
        sa.Column("eligible_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "relationship_growth_log",
        sa.Column("business_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "uk_growth_source",
        "relationship_growth_log",
        ["source_type", "source_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uk_growth_source", table_name="relationship_growth_log")
    op.drop_column("relationship_growth_log", "business_date")
    op.drop_column("relationship_growth_log", "eligible_seconds")
    op.drop_column("relationship_growth_log", "source_id")
    op.drop_column("relationship_growth_log", "source_type")
