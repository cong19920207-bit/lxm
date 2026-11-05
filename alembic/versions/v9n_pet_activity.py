"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9n_pet_activity_001'
down_revision = 'v9m_pet_interaction_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_absence',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('started_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('ended_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('last_narrative_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('pet_id', 'started_at', name='uq_pet_absence_anchor'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_activity',
        sa.Column('pet_id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('last_active_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('session_until', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('previous_absence_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_view_session',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('started_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('heartbeat_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('seconds', sa.Float(), nullable=False),
        sa.Column('foreground', sa.Boolean(), nullable=False),
        sa.Column('qualified_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=True),
        sa.Column('absence_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['absence_id'], ['pet_absence.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_view_session')
    op.drop_table('pet_activity')
    op.drop_table('pet_absence')
