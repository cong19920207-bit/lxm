"""Frozen STEP-001 pet persistence foundation; no business data is seeded.

Application startup must not implicitly create these tables.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "v9i_pet_foundation_001"
down_revision = "v9h_bgm_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pet_rule_snapshot',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('effective_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.UniqueConstraint('kind', 'version', name='uq_pet_rule_version'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_profile',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=False),
        sa.Column('adopted_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('template', sa.JSON(), nullable=False),
        sa.Column('stable_preferences', sa.JSON(), nullable=False),
        sa.Column('preference_discoveries', sa.JSON(), nullable=False),
        sa.Column('growth_rule_id', sa.String(length=36), nullable=False),
        sa.Column('data_version', sa.BigInteger(), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['growth_rule_id'], ['pet_rule_snapshot.id'], ondelete="RESTRICT"),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('id', 'user_id', name='uq_pet_profile_owner'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_fact_event',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(length=128), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('request_digest', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=48), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('participants', sa.JSON(), nullable=False),
        sa.Column('occurred_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('reaction', sa.JSON(), nullable=True),
        sa.Column('state_before', sa.JSON(), nullable=False),
        sa.Column('state_after', sa.JSON(), nullable=False),
        sa.Column('closeness_before', sa.BigInteger(), nullable=False),
        sa.Column('closeness_delta', sa.BigInteger(), nullable=False),
        sa.Column('version_before', sa.BigInteger(), nullable=False),
        sa.Column('version_after', sa.BigInteger(), nullable=False),
        sa.Column('rule_snapshot_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['pet_id', 'user_id'], ['pet_profile.id', 'pet_profile.user_id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['rule_snapshot_id'], ['pet_rule_snapshot.id'], ondelete="RESTRICT"),
        sa.CheckConstraint("source IN ('actual_execution','rule_settlement','delegation_policy','admin_correction')", name='ck_pet_fact_source'),
        sa.CheckConstraint('version_after = version_before + 1', name='ck_pet_fact_version'),
        sa.UniqueConstraint('pet_id', 'business_key', name='uq_pet_fact_business'),
        sa.UniqueConstraint('id', 'pet_id', name='uq_pet_fact_owner'),
        sa.UniqueConstraint('pet_id', 'request_key', name='uq_pet_fact_request'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_index('ix_pet_fact_day', 'pet_fact_event', ['pet_id', 'business_date', 'occurred_at'])
    op.create_table('pet_formal_text',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('coverage_start', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('coverage_end', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('config_snapshot', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete="RESTRICT"),
        sa.CheckConstraint('version >= 1', name='ck_pet_text_version'),
        sa.UniqueConstraint('id', 'pet_id', name='uq_pet_text_owner'),
        sa.UniqueConstraint('pet_id', 'business_key', 'version', name='uq_pet_text_version'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_state',
        sa.Column('pet_id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('record_version', sa.BigInteger(), nullable=False),
        sa.Column('stage', sa.String(length=24), nullable=False),
        sa.Column('values', sa.JSON(), nullable=False),
        sa.Column('closeness', sa.BigInteger(), nullable=False),
        sa.Column('unlocked_behaviors', sa.JSON(), nullable=False),
        sa.Column('appearance_rule_id', sa.String(length=36), nullable=True),
        sa.Column('active_activity', sa.JSON(), nullable=True),
        sa.Column('settled_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['appearance_rule_id'], ['pet_rule_snapshot.id'], ondelete="RESTRICT"),
        sa.CheckConstraint('closeness >= 0', name='ck_pet_state_closeness'),
        sa.CheckConstraint('record_version >= 1', name='ck_pet_state_version'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_diagnostic_payload',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete="RESTRICT"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_index('ix_pet_diagnostic_retention', 'pet_diagnostic_payload', ['recorded_at'])
    op.create_table('pet_display_entry',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('source_event_id', sa.String(length=36), nullable=False),
        sa.Column('surface', sa.String(length=16), nullable=False),
        sa.Column('presentation', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['source_event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        sa.CheckConstraint("surface IN ('daily','album')", name='ck_pet_display_surface'),
        sa.UniqueConstraint('pet_id', 'surface', 'source_event_id', name='uq_pet_display_source'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_fact_request',
        sa.Column('pet_id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('request_key', sa.String(length=128), primary_key=True, nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_snapshot',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('source_event_id', sa.String(length=36), nullable=True),
        sa.Column('captured_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column('profile', sa.JSON(), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('resources', sa.JSON(), nullable=False),
        sa.Column('rule_snapshot_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profile.id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['source_event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['rule_snapshot_id'], ['pet_rule_snapshot.id'], ondelete="RESTRICT"),
        sa.UniqueConstraint('pet_id', 'business_key', name='uq_pet_snapshot_business'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_task_candidate',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.Column('source_event_id', sa.String(length=36), nullable=False),
        sa.Column('business_key', sa.String(length=128), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.ForeignKeyConstraint(['source_event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        sa.UniqueConstraint('pet_id', 'business_key', name='uq_pet_candidate_business'),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )
    op.create_table('pet_text_source',
        sa.Column('text_id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('event_id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('pet_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['event_id', 'pet_id'], ['pet_fact_event.id', 'pet_fact_event.pet_id'], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(['text_id', 'pet_id'], ['pet_formal_text.id', 'pet_formal_text.pet_id'], ondelete="RESTRICT"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_bin",
    )


def downgrade():
    op.drop_table('pet_text_source')
    op.drop_table('pet_task_candidate')
    op.drop_table('pet_snapshot')
    op.drop_table('pet_fact_request')
    op.drop_table('pet_display_entry')
    op.drop_table('pet_diagnostic_payload')
    op.drop_table('pet_state')
    op.drop_table('pet_formal_text')
    op.drop_table('pet_fact_event')
    op.drop_table('pet_profile')
    op.drop_table('pet_rule_snapshot')
