"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9o_pet_budget_001'
down_revision = 'v9n_pet_activity_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_budget_mutex',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_request_attempt',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('request_key', sa.String(length=160), nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('debug_owner', sa.Integer(), nullable=True),
        sa.Column('origin', sa.String(length=16), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('absence_id', sa.String(length=36), nullable=True),
        sa.Column('return_id', sa.String(length=36), nullable=True),
        sa.Column('content_date', sa.Date(), nullable=True),
        sa.Column('reserved_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('submission_date', sa.Date(), nullable=True),
        sa.Column('sent_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('concurrent_until', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('concurrent_active', sa.Boolean(), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=96), nullable=True),
        sa.Column('config_id', sa.String(length=36), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['config_id'], ['pet_config_version.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['absence_id'], ['pet_absence.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('request_key'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_budget_entry',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('attempt_id', sa.String(length=36), nullable=False),
        sa.Column('layer', sa.String(length=16), nullable=False),
        sa.Column('bucket', sa.String(length=128), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('limit_at_reserve', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['attempt_id'], ['pet_request_attempt.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('attempt_id', 'layer', 'bucket', name='uq_pet_budget_entry'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_budget_entry')
    op.drop_table('pet_request_attempt')
    op.drop_table('pet_budget_mutex')
