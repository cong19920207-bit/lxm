"""Create memory source/dispatch/use controls; never activates a runtime fence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "v9b_memory_control_001"
down_revision = "v9a_memory_config_publication_001"
branch_labels = None
depends_on = None

U64 = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
U32 = sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql")
UUID = sa.String(36).with_variant(mysql.CHAR(36, charset="ascii", collation="ascii_bin"), "mysql")
DIGEST = sa.LargeBinary(32).with_variant(mysql.BINARY(32), "mysql")
INSTANT = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")

def _ascii(length):
    return sa.String(length).with_variant(mysql.VARCHAR(length, charset="ascii", collation="ascii_bin"), "mysql")


def upgrade():
    op.create_table('memory_runtime_fence',
        sa.Column('environment_id', sa.String(64), nullable=False, primary_key=True),
        sa.Column('target_epoch', U64, nullable=False),
        sa.Column('target_fingerprint', DIGEST, nullable=False),
        sa.Column('mode', _ascii(16), nullable=False),
        sa.Column('reset_run_id', UUID, nullable=True),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        sa.CheckConstraint("mode IN ('maintenance','active')", name='ck_memory_fence_mode'),
        mysql_engine="InnoDB",
    )
    op.create_table('memory_identity',
        sa.Column('id', U64.with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('target_epoch', U64, nullable=False),
        sa.Column('target_fingerprint', DIGEST, nullable=False),
        sa.Column('partition_name', _ascii(64), nullable=False),
        sa.Column('doc_id', _ascii(64), nullable=False),
        sa.Column('memory_type', sa.String(32), nullable=False),
        sa.Column('owner_user_id', sa.BigInteger(), nullable=False),
        sa.Column('generation', U64, nullable=False, server_default='0'),
        sa.Column('allocated_generation', U64, nullable=False, server_default='0'),
        sa.Column('body_hash', DIGEST, nullable=True),
        sa.Column('source_state', _ascii(24), nullable=False),
        sa.Column('index_state', _ascii(24), nullable=False),
        sa.Column('encoder_version', sa.String(128), nullable=True),
        sa.Column('current_operation_id', UUID, nullable=True),
        sa.Column('inflight_operation_id', UUID, nullable=True),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        sa.CheckConstraint('generation >= 0 AND allocated_generation >= generation', name='ck_memory_identity_generation'),
        sa.CheckConstraint("index_state IN ('not_ready','ready','repairing','manual','deleted')", name='ck_memory_identity_index'),
        sa.CheckConstraint("(memory_type IN ('character_global','character_knowledge') AND owner_user_id = 0) OR (memory_type IN ('user','character_private') AND owner_user_id > 0)", name='ck_memory_identity_owner'),
        sa.CheckConstraint("source_state IN ('unknown','live','deleted')", name='ck_memory_identity_source'),
        sa.UniqueConstraint('target_fingerprint', 'partition_name', 'doc_id', name='uq_memory_identity_target_doc'),
        mysql_engine="InnoDB",
    )
    op.create_index('ix_memory_identity_states_id', 'memory_identity', ['source_state', 'index_state', 'id'])
    op.create_table('memory_operation',
        sa.Column('operation_id', UUID, nullable=False, primary_key=True),
        sa.Column('identity_id', U64, nullable=True),
        sa.Column('generation', U64, nullable=True),
        sa.Column('parent_operation_id', UUID, nullable=True),
        sa.Column('task_id', UUID, nullable=True),
        sa.Column('round_no', U32, nullable=True),
        sa.Column('attempt', U32, nullable=True),
        sa.Column('source_generation_key', DIGEST, nullable=True),
        sa.Column('operation_kind', _ascii(24), nullable=False),
        sa.Column('owner_actor_type', _ascii(16), nullable=False),
        sa.Column('owner_actor_id', sa.BigInteger(), nullable=False),
        sa.Column('client_request_id', UUID, nullable=True),
        sa.Column('idempotency_hash', DIGEST, nullable=True),
        sa.Column('request_hash', DIGEST, nullable=False),
        sa.Column('target_epoch', U64, nullable=False),
        sa.Column('source_result', _ascii(24), nullable=False),
        sa.Column('index_result', _ascii(24), nullable=False),
        sa.Column('dispatch_state', _ascii(24), nullable=False),
        sa.Column('pending_payload', sa.JSON(), nullable=True),
        sa.Column('payload_hash', DIGEST, nullable=True),
        sa.Column('remote_tag', UUID, nullable=False),
        sa.Column('worker_id', UUID, nullable=True),
        sa.Column('worker_epoch', U64, nullable=False, server_default='0'),
        sa.Column('lease_until', INSTANT, nullable=True),
        sa.Column('dispatched_at', INSTANT, nullable=True),
        sa.Column('reconcile_until', INSTANT, nullable=False),
        sa.Column('terminal_at', INSTANT, nullable=True),
        sa.Column('receipt_summary', sa.JSON(), nullable=True),
        sa.Column('receipt_until', INSTANT, nullable=True),
        sa.Column('tombstone_until', INSTANT, nullable=True),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        sa.CheckConstraint("dispatch_state IN ('prepared','claimed','dispatching','confirmed','unknown','not_sent','superseded')", name='ck_memory_operation_dispatch'),
        sa.CheckConstraint("(operation_kind IN ('create','update','delete') AND source_generation_key IS NOT NULL) OR (operation_kind NOT IN ('create','update','delete') AND source_generation_key IS NULL)", name='ck_memory_operation_generation_key'),
        sa.CheckConstraint("operation_kind = 'batch' OR (identity_id IS NOT NULL AND generation IS NOT NULL)", name='ck_memory_operation_identity'),
        sa.CheckConstraint("index_result IN ('pending','ready','failed','unknown','manual','not_required','superseded')", name='ck_memory_operation_index'),
        sa.CheckConstraint("operation_kind <> 'index' OR (task_id IS NOT NULL AND round_no IS NOT NULL AND attempt IS NOT NULL AND attempt >= 1)", name='ck_memory_operation_index_attempt'),
        sa.CheckConstraint("operation_kind IN ('create','update','delete','index','retry','baseline','batch')", name='ck_memory_operation_kind'),
        sa.CheckConstraint("source_result IN ('pending','confirmed','failed','unknown','superseded')", name='ck_memory_operation_source'),
        sa.UniqueConstraint('owner_actor_type', 'owner_actor_id', 'idempotency_hash', name='uq_memory_operation_actor_request'),
        sa.UniqueConstraint('parent_operation_id', 'identity_id', name='uq_memory_operation_parent_identity'),
        sa.UniqueConstraint('source_generation_key', name='uq_memory_operation_source_generation'),
        sa.UniqueConstraint('task_id', 'round_no', 'attempt', name='uq_memory_operation_task_attempt'),
        mysql_engine="InnoDB",
    )
    op.create_index('ix_memory_operation_dispatch_lease', 'memory_operation', ['dispatch_state', 'lease_until'])
    op.create_index('ix_memory_operation_source_reconcile', 'memory_operation', ['source_result', 'reconcile_until'])
    op.create_table('memory_index_task',
        sa.Column('task_id', UUID, nullable=False, primary_key=True),
        sa.Column('identity_id', U64, nullable=False),
        sa.Column('operation_id', UUID, nullable=False),
        sa.Column('generation', U64, nullable=False),
        sa.Column('encoder_version', sa.String(128), nullable=False),
        sa.Column('body_hash', DIGEST, nullable=False),
        sa.Column('state', _ascii(24), nullable=False),
        sa.Column('round_no', U32, nullable=False, server_default='0'),
        sa.Column('attempt', U32, nullable=False, server_default='0'),
        sa.Column('round_started_at', INSTANT, nullable=False),
        sa.Column('round_deadline_at', INSTANT, nullable=False),
        sa.Column('next_attempt_at', INSTANT, nullable=True),
        sa.Column('worker_id', UUID, nullable=True),
        sa.Column('worker_epoch', U64, nullable=False, server_default='0'),
        sa.Column('lease_until', INSTANT, nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        sa.CheckConstraint("state IN ('pending','running','retry_wait','manual','completed','superseded')", name='ck_memory_index_task_state'),
        sa.UniqueConstraint('identity_id', 'generation', 'encoder_version', name='uq_memory_index_task_generation_encoder'),
        mysql_engine="InnoDB",
    )
    op.create_index('ix_memory_index_task_due', 'memory_index_task', ['state', 'next_attempt_at', 'task_id'])
    op.create_table('memory_use_claim',
        sa.Column('claim_id', UUID, nullable=False, primary_key=True),
        sa.Column('request_hash', DIGEST, nullable=False),
        sa.Column('consumer_kind', _ascii(24), nullable=False),
        sa.Column('execution_id', UUID, nullable=False),
        sa.Column('target_epoch', U64, nullable=False),
        sa.Column('owner_id', UUID, nullable=False),
        sa.Column('state', _ascii(24), nullable=False),
        sa.Column('created_deadline_at', INSTANT, nullable=False),
        sa.Column('handoff_at', INSTANT, nullable=True),
        sa.Column('closed_at', INSTANT, nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        sa.CheckConstraint("state IN ('reserved','dispatching','handed_off','aborted','unknown')", name='ck_memory_use_claim_state'),
        sa.UniqueConstraint('consumer_kind', 'execution_id', name='uq_memory_use_claim_execution'),
        mysql_engine="InnoDB",
    )
    op.create_table('memory_use_item',
        sa.Column('claim_id', UUID, nullable=False, primary_key=True),
        sa.Column('identity_id', U64, nullable=False, primary_key=True),
        sa.Column('generation', U64, nullable=False),
        sa.Column('body_hash', DIGEST, nullable=False),
        sa.Column('route', _ascii(4), nullable=False),
        sa.Column('ordinal', U32, nullable=False),
        sa.Column('created_at', INSTANT, nullable=False),
        sa.Column('updated_at', INSTANT, nullable=False),
        sa.Column('revision', U64, nullable=False, server_default='1'),
        mysql_engine="InnoDB",
    )
    op.create_index('ix_memory_use_item_identity_claim', 'memory_use_item', ['identity_id', 'claim_id'])
    # Add the operation/task cycle only after both tables exist.
    with op.batch_alter_table('memory_operation') as batch:
        batch.create_foreign_key('fk_memory_operation_identity', 'memory_identity', ['identity_id'], ['id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_operation') as batch:
        batch.create_foreign_key('fk_memory_operation_parent', 'memory_operation', ['parent_operation_id'], ['operation_id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_operation') as batch:
        batch.create_foreign_key('fk_memory_operation_task', 'memory_index_task', ['task_id'], ['task_id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_index_task') as batch:
        batch.create_foreign_key('fk_memory_index_task_identity', 'memory_identity', ['identity_id'], ['id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_index_task') as batch:
        batch.create_foreign_key('fk_memory_index_task_source', 'memory_operation', ['operation_id'], ['operation_id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_use_item') as batch:
        batch.create_foreign_key('fk_memory_use_item_claim', 'memory_use_claim', ['claim_id'], ['claim_id'], ondelete="RESTRICT")
    with op.batch_alter_table('memory_use_item') as batch:
        batch.create_foreign_key('fk_memory_use_item_identity', 'memory_identity', ['identity_id'], ['id'], ondelete="RESTRICT")


def downgrade():
    with op.batch_alter_table('memory_use_item') as batch:
        batch.drop_constraint('fk_memory_use_item_identity', type_="foreignkey")
    with op.batch_alter_table('memory_use_item') as batch:
        batch.drop_constraint('fk_memory_use_item_claim', type_="foreignkey")
    with op.batch_alter_table('memory_index_task') as batch:
        batch.drop_constraint('fk_memory_index_task_source', type_="foreignkey")
    with op.batch_alter_table('memory_index_task') as batch:
        batch.drop_constraint('fk_memory_index_task_identity', type_="foreignkey")
    with op.batch_alter_table('memory_operation') as batch:
        batch.drop_constraint('fk_memory_operation_task', type_="foreignkey")
    with op.batch_alter_table('memory_operation') as batch:
        batch.drop_constraint('fk_memory_operation_parent', type_="foreignkey")
    with op.batch_alter_table('memory_operation') as batch:
        batch.drop_constraint('fk_memory_operation_identity', type_="foreignkey")
    op.drop_table('memory_use_item')
    op.drop_table('memory_use_claim')
    op.drop_table('memory_index_task')
    op.drop_table('memory_operation')
    op.drop_table('memory_identity')
    op.drop_table('memory_runtime_fence')
