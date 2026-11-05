"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9l_pet_rule_job_001'
down_revision = 'v9k_pet_config_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_rule_job',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('covered_until', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('pet_data_version', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        sa.Column('generation', sa.BigInteger(), nullable=False),
        sa.Column('owner', sa.String(length=64), nullable=True),
        sa.Column('lease_until', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('last_error', sa.String(length=64), nullable=True),
        sa.Column('last_success_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('pet_id', 'business_key', name='uq_pet_rule_job_business'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_index('ix_pet_rule_job_health', 'pet_rule_job', ['kind', 'state', 'lease_until'])


def downgrade():
    op.drop_table('pet_rule_job')
