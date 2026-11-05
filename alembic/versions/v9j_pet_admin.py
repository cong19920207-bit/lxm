"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9j_pet_admin_001'
down_revision = 'v9i_pet_foundation_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_admin_operation',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('actor_role', sa.String(length=20), nullable=False),
        sa.Column('token_version', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=48), nullable=False),
        sa.Column('domain', sa.String(length=24), nullable=False),
        sa.Column('target', sa.String(length=128), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('request_digest', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        sa.Column('stop_reason', sa.String(length=64), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('finished_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_index('ix_pet_admin_operation_actor', 'pet_admin_operation', ['admin_id', 'recorded_at'])
    op.create_table('pet_admin_audit',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('operation_id', sa.String(length=64), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('actor_role', sa.String(length=20), nullable=False),
        sa.Column('action', sa.String(length=48), nullable=False),
        sa.Column('domain', sa.String(length=24), nullable=False),
        sa.Column('target', sa.String(length=128), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['operation_id'], ['pet_admin_operation.id'], ondelete='RESTRICT'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_index('ix_pet_audit_scope', 'pet_admin_audit', ['domain', 'recorded_at'])


def downgrade():
    op.drop_table('pet_admin_audit')
    op.drop_table('pet_admin_operation')
