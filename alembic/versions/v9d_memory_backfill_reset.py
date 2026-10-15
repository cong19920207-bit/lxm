"""Frozen STEP-008 reset/backfill schema and RESTRICT activation/tombstone references."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
revision = 'v9d_memory_backfill_reset_001'
down_revision = 'v9c_memory_maintenance_001'
branch_labels = None
depends_on = None

def upgrade():
    uid = sa.String(36).with_variant(mysql.CHAR(36, charset='ascii', collation='ascii_bin'), 'mysql')
    u64 = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql')
    instant = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql')
    digest = sa.LargeBinary(32).with_variant(mysql.BINARY(32), 'mysql')
    op.create_table('memory_reset_run',
        sa.Column('run_id', uid, nullable=False, primary_key=True),
        sa.Column('environment_id', sa.String(64).with_variant(mysql.VARCHAR(64, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('reset_key', sa.String(16).with_variant(mysql.VARCHAR(16, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('manifest_hash', digest, nullable=False),
        sa.Column('protocol_version', sa.String(32).with_variant(mysql.VARCHAR(32, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('target_epoch', u64, nullable=False),
        sa.Column('target_fingerprint', digest, nullable=False),
        sa.Column('t0', instant, nullable=True),
        sa.Column('phase', sa.String(32).with_variant(mysql.VARCHAR(32, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('state', sa.String(24).with_variant(mysql.VARCHAR(24, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('baseline_digest', digest, nullable=True),
        sa.Column('completed_at', instant, nullable=True),
        sa.Column('opened_at', instant, nullable=True),
        sa.Column('operator_id', u64, nullable=False),
        sa.Column('last_error_code', sa.String(64).with_variant(mysql.VARCHAR(64, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=True),
        sa.Column('created_at', instant, nullable=False),
        sa.Column('updated_at', instant, nullable=False),
        sa.Column('revision', u64, nullable=False, server_default='1'),
        sa.CheckConstraint("state IN ('planned','maintenance','running','unknown','failed','completed','opened')", name='ck_memory_reset_state'),
        sa.CheckConstraint("reset_key = 'S15'", name='ck_memory_reset_key'),
        sa.UniqueConstraint('environment_id', 'reset_key', name='uq_memory_reset_environment_key'),
        mysql_engine='InnoDB')
    op.create_table('memory_reset_item',
        sa.Column('run_id', uid, nullable=False, primary_key=True),
        sa.Column('kind', sa.String(16).with_variant(mysql.VARCHAR(16, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False, primary_key=True),
        sa.Column('resource_key', sa.String(191).with_variant(mysql.VARCHAR(191, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False, primary_key=True),
        sa.Column('state', sa.String(24).with_variant(mysql.VARCHAR(24, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('fixed_scope', sa.JSON(), nullable=False),
        sa.Column('cursor', sa.JSON(), nullable=True),
        sa.Column('before_count', u64, nullable=True),
        sa.Column('after_count', u64, nullable=True),
        sa.Column('preserve_digest_before', digest, nullable=True),
        sa.Column('preserve_digest_after', digest, nullable=True),
        sa.Column('result_digest', digest, nullable=True),
        sa.Column('error_code', sa.String(64).with_variant(mysql.VARCHAR(64, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=True),
        sa.Column('created_at', instant, nullable=False),
        sa.Column('updated_at', instant, nullable=False),
        sa.Column('revision', u64, nullable=False, server_default='1'),
        sa.CheckConstraint("kind IN ('phase','resource')", name='ck_memory_reset_item_kind'),
        sa.ForeignKeyConstraint(['run_id'], ['memory_reset_run.run_id'], name='fk_memory_reset_item_run', ondelete="RESTRICT"),
        mysql_engine='InnoDB')
    op.create_index('ix_memory_reset_item_state', 'memory_reset_item', ['state', 'run_id'])
    op.create_table('memory_backfill_run',
        sa.Column('run_id', uid, nullable=False, primary_key=True),
        sa.Column('mode', sa.String(16).with_variant(mysql.VARCHAR(16, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('execution_state', sa.String(24).with_variant(mysql.VARCHAR(24, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('stage', sa.String(16).with_variant(mysql.VARCHAR(16, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('source_scope', sa.JSON(), nullable=False),
        sa.Column('frozen_versions', sa.JSON(), nullable=False),
        sa.Column('scope_digest', digest, nullable=False),
        sa.Column('baseline', sa.JSON(), nullable=False),
        sa.Column('high_water', sa.JSON(), nullable=True),
        sa.Column('checkpoint_summary', sa.JSON(), nullable=True),
        sa.Column('cutoff', sa.JSON(), nullable=True),
        sa.Column('scanned_records', u64, nullable=False, server_default='0'),
        sa.Column('unique_source_ids', u64, nullable=False, server_default='0'),
        sa.Column('attempt_count', u64, nullable=False, server_default='0'),
        sa.Column('total_known', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('total_source_ids', u64, nullable=True),
        sa.Column('source_class_counts', sa.JSON(), nullable=False),
        sa.Column('reconcile_counts', sa.JSON(), nullable=False),
        sa.Column('unresolved_count', u64, nullable=False, server_default='0'),
        sa.Column('report_complete', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('started_at', instant, nullable=True),
        sa.Column('ended_at', instant, nullable=True),
        sa.Column('lease_owner', uid, nullable=True),
        sa.Column('lease_version', u64, nullable=False, server_default='0'),
        sa.Column('lease_until', instant, nullable=True),
        sa.Column('created_at', instant, nullable=False),
        sa.Column('updated_at', instant, nullable=False),
        sa.Column('revision', u64, nullable=False, server_default='1'),
        sa.CheckConstraint('scanned_records >= 0 AND unique_source_ids >= 0 AND attempt_count >= 0 AND unresolved_count >= 0', name='ck_memory_backfill_counts'),
        sa.CheckConstraint("stage IN ('scan','index','reconcile','catchup')", name='ck_memory_backfill_stage'),
        sa.CheckConstraint("mode IN ('isolated','actual')", name='ck_memory_backfill_mode'),
        sa.CheckConstraint("execution_state IN ('pending','running','interrupted','manual_required','completed')", name='ck_memory_backfill_state'),
        mysql_engine='InnoDB')
    op.create_table('memory_backfill_item',
        sa.Column('id', u64.with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('run_id', uid, nullable=False),
        sa.Column('item_seq', u64, nullable=False),
        sa.Column('identity_id', u64, nullable=True),
        sa.Column('identity_key', sa.JSON(), nullable=False),
        sa.Column('identity_digest', digest, nullable=False),
        sa.Column('source_class', sa.String(32).with_variant(mysql.VARCHAR(32, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('current_generation', u64, nullable=True),
        sa.Column('content_digest', digest, nullable=True),
        sa.Column('index_result', sa.String(24).with_variant(mysql.VARCHAR(24, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('reconcile_state', sa.String(24).with_variant(mysql.VARCHAR(24, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False),
        sa.Column('task_id', uid, nullable=True),
        sa.Column('attempt_count', u64, nullable=False, server_default='0'),
        sa.Column('observed_at', instant, nullable=False),
        sa.Column('reason', sa.String(64).with_variant(mysql.VARCHAR(64, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=True),
        sa.Column('created_at', instant, nullable=False),
        sa.Column('updated_at', instant, nullable=False),
        sa.Column('revision', u64, nullable=False, server_default='1'),
        sa.UniqueConstraint('run_id', 'item_seq', name='uq_memory_backfill_item_seq'),
        sa.ForeignKeyConstraint(['run_id'], ['memory_backfill_run.run_id'], name='fk_memory_backfill_item_run', ondelete="RESTRICT"),
        sa.UniqueConstraint('run_id', 'identity_digest', name='uq_memory_backfill_item_identity'),
        mysql_engine='InnoDB')
    op.create_index('ix_memory_backfill_item_run', 'memory_backfill_item', ['run_id', 'item_seq'])
    with op.batch_alter_table('voice_call') as batch:
        batch.add_column(sa.Column('cleared_run_id', uid, nullable=True))
        batch.create_foreign_key('fk_voice_call_cleared_run', 'memory_reset_run', ['cleared_run_id'], ['run_id'], ondelete='RESTRICT')
        batch.create_index('ix_voice_call_cleared_run', ['cleared_run_id'])
    with op.batch_alter_table('memory_runtime_fence') as batch:
        batch.create_foreign_key('fk_memory_fence_reset', 'memory_reset_run', ['reset_run_id'], ['run_id'], ondelete='RESTRICT')

def downgrade():
    with op.batch_alter_table('memory_runtime_fence') as batch:
        batch.drop_constraint('fk_memory_fence_reset', type_='foreignkey')
    with op.batch_alter_table('voice_call') as batch:
        batch.drop_constraint('fk_voice_call_cleared_run', type_='foreignkey')
        batch.drop_index('ix_voice_call_cleared_run')
        batch.drop_column('cleared_run_id')
    for name in ('memory_backfill_item','memory_backfill_run','memory_reset_item','memory_reset_run'):
        op.drop_table(name)
