"""Maintenance display projections. Never used to acquire/release a control lock."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v9c_memory_maintenance_001'
down_revision = 'v9b_memory_control_001'
branch_labels = None
depends_on = None


def upgrade():
    uid = sa.String(36).with_variant(mysql.CHAR(36, charset='ascii', collation='ascii_bin'), 'mysql')
    instant = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql')
    u64 = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql')
    columns = [sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
               sa.Column('event_id', uid, nullable=False), sa.Column('record_kind', sa.String(16), nullable=False)]
    columns += [sa.Column(name, uid, nullable=True) for name in ('task_id', 'run_id', 'operation_id')]
    columns += [sa.Column(name, u64, nullable=True) for name in ('identity_id', 'generation')]
    columns += [sa.Column('event_type', sa.String(32), nullable=False),
                sa.Column('source_state', sa.String(16), nullable=True),
                sa.Column('index_state', sa.String(24), nullable=True),
                sa.Column('maintenance_state', sa.String(24), nullable=True),
                sa.Column('attempt_number', sa.Integer(), nullable=True)]
    columns += [sa.Column(name, instant, nullable=name != 'created_at') for name in ('started_at', 'ended_at', 'created_at', 'display_deleted_at')]
    columns += [sa.Column('controlled_reason', sa.String(64), nullable=True), sa.Column('details', sa.JSON(), nullable=True),
                sa.UniqueConstraint('event_id', name='uq_memory_event_id'),
                sa.CheckConstraint("record_kind IN ('task','backfill')", name='ck_memory_event_kind'),
                sa.CheckConstraint('task_id IS NOT NULL OR run_id IS NOT NULL', name='ck_memory_event_origin')]
    op.create_table('memory_maintenance_event', *columns, mysql_engine='InnoDB')
    op.create_index('ix_memory_event_task_created', 'memory_maintenance_event', ['task_id','created_at','id'])
    op.create_index('ix_memory_event_run_created', 'memory_maintenance_event', ['run_id','created_at','id'])


def downgrade():
    op.drop_table('memory_maintenance_event')
