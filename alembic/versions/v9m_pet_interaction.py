"""Frozen pet-domain increment; application startup never creates these tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9m_pet_interaction_001'
down_revision = 'v9l_pet_rule_job_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_interaction',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('request_key', sa.String(length=96), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        sa.Column('config_id', sa.String(length=36), nullable=False),
        sa.Column('pet_data_version', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('expires_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('event_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['config_id'], ['pet_config_version.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['event_id'], ['pet_fact_event.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('pet_id', 'request_key', name='uq_pet_interaction_request'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_interaction')
