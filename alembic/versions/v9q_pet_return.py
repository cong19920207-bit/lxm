"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9q_pet_return_001'
down_revision = 'v9p_pet_generation_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_return',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('absence_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('coverage_start', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('coverage_end', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('confirmed_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('presented_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('source_ids', sa.JSON(), nullable=False),
        sa.Column('growth_ids', sa.JSON(), nullable=False),
        sa.Column('highlights', sa.JSON(), nullable=False),
        sa.Column('last_snapshot_id', sa.String(length=36), nullable=True),
        sa.Column('current_event_id', sa.String(length=36), nullable=True),
        sa.Column('task_id', sa.String(length=36), nullable=True),
        sa.Column('reused_text_id', sa.String(length=36), nullable=True),
        sa.Column('reason', sa.String(length=96), nullable=True),
        sa.ForeignKeyConstraint(['current_event_id'], ['pet_fact_event.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['task_id'], ['pet_generation_task.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['last_snapshot_id'], ['pet_snapshot.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reused_text_id'], ['pet_formal_text.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['absence_id'], ['pet_absence.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('absence_id'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_return')
