"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9k_pet_config_001'
down_revision = 'v9j_pet_admin_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_config_head',
        sa.Column('domain', sa.String(length=24), nullable=False, primary_key=True),
        sa.Column('active_version', sa.BigInteger(), nullable=False),
        sa.Column('draft_revision', sa.BigInteger(), nullable=False),
        sa.Column('draft_base_version', sa.BigInteger(), nullable=False),
        sa.Column('draft', sa.JSON(), nullable=True),
        sa.Column('validated_digest', sa.String(length=64), nullable=True),
        sa.Column('validated_revision', sa.BigInteger(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_resource',
        sa.Column('id', sa.String(length=128), nullable=False, primary_key=True),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('uri', sa.String(length=512), nullable=False),
        sa.Column('identity_key', sa.String(length=64), nullable=False),
        sa.Column('stages', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('available', sa.Boolean(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_config_version',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('domain', sa.String(length=24), nullable=False),
        sa.Column('version', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('content_digest', sa.String(length=64), nullable=False),
        sa.Column('diff', sa.JSON(), nullable=False),
        sa.Column('effective_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('action', sa.String(length=24), nullable=False),
        sa.Column('operation_id', sa.String(length=64), nullable=False),
        sa.Column('snapshot_id', sa.String(length=36), nullable=False),
        sa.Column('growth_snapshot_id', sa.String(length=36), nullable=True),
        sa.Column('state_snapshot_id', sa.String(length=36), nullable=True),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['growth_snapshot_id'], ['pet_rule_snapshot.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['pet_rule_snapshot.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['operation_id'], ['pet_admin_operation.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['state_snapshot_id'], ['pet_rule_snapshot.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('operation_id'),
        sa.UniqueConstraint('domain', 'version', name='uq_pet_config_version'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_config_version')
    op.drop_table('pet_resource')
    op.drop_table('pet_config_head')
