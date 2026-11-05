"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9r_pet_lifecycle_001'
down_revision = 'v9q_pet_return_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_account_lifecycle',
        sa.Column('user_id', sa.BigInteger(), nullable=False, primary_key=True),
        sa.Column('operation_id', sa.String(length=96), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_account_lifecycle')
