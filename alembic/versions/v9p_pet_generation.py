"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9p_pet_generation_001'
down_revision = 'v9o_pet_budget_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_generation_task',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('origin', sa.String(length=16), nullable=False),
        sa.Column('absence_id', sa.String(length=36), nullable=True),
        sa.Column('return_id', sa.String(length=36), nullable=True),
        sa.Column('source_ids', sa.JSON(), nullable=False),
        sa.Column('coverage_start', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('coverage_end', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('expires_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('pet_data_version', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('owner', sa.String(length=96), nullable=True),
        sa.Column('lease_until', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('attempt_id', sa.String(length=36), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('reason', sa.String(length=96), nullable=True),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['attempt_id'], ['pet_request_attempt.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['absence_id'], ['pet_absence.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('pet_id', 'business_key', name='uq_pet_generation_business'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_generation_task')
