# -*- coding: utf-8 -*-
"""实时语音 STEP-001：admin配置草稿乐观锁修订号。

Revision ID: v8a_voice_draft_rev_001
Revises: v7a_admin_token_ver_001
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v8a_voice_draft_rev_001"
down_revision: Union[str, None] = "v7a_admin_token_ver_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_config",
        sa.Column(
            "draft_revision",
            sa.Integer(),
            nullable=True,
            comment="语音配置草稿乐观锁修订号",
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_config", "draft_revision")
