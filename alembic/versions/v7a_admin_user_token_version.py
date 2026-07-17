# -*- coding: utf-8 -*-
"""为 admin_users 增加管理员会话版本字段。

Revision ID: v7a_admin_token_ver_001
Revises: v6e_display_comments_001
Create Date: 2026-07-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v7a_admin_token_ver_001"
down_revision: Union[str, None] = "v6e_display_comments_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="管理员会话版本",
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "token_version")
