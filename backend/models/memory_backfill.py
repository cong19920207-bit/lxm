"""Alembic-owned S15 and complete-source reconciliation evidence. No source text."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Index, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.memory_control import ControlColumns, U64, UUID, DIGEST, INSTANT, ascii_string, ref

MEMORY_BACKFILL_TABLE_NAMES = frozenset({'memory_reset_run','memory_reset_item','memory_backfill_run','memory_backfill_item'})


class MemoryResetRun(ControlColumns, Base):
    __tablename__ = 'memory_reset_run'
    __table_args__ = (UniqueConstraint('environment_id','reset_key',name='uq_memory_reset_environment_key'),
        CheckConstraint("reset_key = 'S15'",name='ck_memory_reset_key'),
        CheckConstraint("state IN ('planned','maintenance','running','unknown','failed','completed','opened')",name='ck_memory_reset_state'))
    run_id: Mapped[str] = mapped_column(UUID,primary_key=True)
    environment_id: Mapped[str] = mapped_column(ascii_string(64))
    reset_key: Mapped[str] = mapped_column(ascii_string(16),default='S15')
    manifest_hash: Mapped[bytes] = mapped_column(DIGEST)
    protocol_version: Mapped[str] = mapped_column(ascii_string(32))
    target_epoch: Mapped[int] = mapped_column(U64)
    target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
    t0: Mapped[datetime | None] = mapped_column(INSTANT)
    phase: Mapped[str] = mapped_column(ascii_string(32))
    state: Mapped[str] = mapped_column(ascii_string(24))
    baseline_digest: Mapped[bytes | None] = mapped_column(DIGEST)
    completed_at: Mapped[datetime | None] = mapped_column(INSTANT)
    opened_at: Mapped[datetime | None] = mapped_column(INSTANT)
    operator_id: Mapped[int] = mapped_column(U64)
    last_error_code: Mapped[str | None] = mapped_column(ascii_string(64))


class MemoryResetItem(ControlColumns, Base):
    __tablename__ = 'memory_reset_item'
    __table_args__ = (CheckConstraint("kind IN ('phase','resource')",name='ck_memory_reset_item_kind'),Index('ix_memory_reset_item_state','state','run_id'))
    run_id: Mapped[str] = mapped_column(UUID,ref('memory_reset_run.run_id','fk_memory_reset_item_run'),primary_key=True)
    kind: Mapped[str] = mapped_column(ascii_string(16),primary_key=True)
    resource_key: Mapped[str] = mapped_column(ascii_string(191),primary_key=True)
    state: Mapped[str] = mapped_column(ascii_string(24))
    fixed_scope: Mapped[dict] = mapped_column(JSON)
    cursor: Mapped[dict | None] = mapped_column(JSON)
    before_count: Mapped[int | None] = mapped_column(U64)
    after_count: Mapped[int | None] = mapped_column(U64)
    preserve_digest_before: Mapped[bytes | None] = mapped_column(DIGEST)
    preserve_digest_after: Mapped[bytes | None] = mapped_column(DIGEST)
    result_digest: Mapped[bytes | None] = mapped_column(DIGEST)
    error_code: Mapped[str | None] = mapped_column(ascii_string(64))


class MemoryBackfillRun(ControlColumns, Base):
    __tablename__ = 'memory_backfill_run'
    __table_args__ = (CheckConstraint("mode IN ('isolated','actual')",name='ck_memory_backfill_mode'),
        CheckConstraint("execution_state IN ('pending','running','interrupted','manual_required','completed')",name='ck_memory_backfill_state'),
        CheckConstraint("stage IN ('scan','index','reconcile','catchup')",name='ck_memory_backfill_stage'),
        CheckConstraint('scanned_records >= 0 AND unique_source_ids >= 0 AND attempt_count >= 0 AND unresolved_count >= 0',name='ck_memory_backfill_counts'))
    run_id: Mapped[str] = mapped_column(UUID,primary_key=True)
    mode: Mapped[str] = mapped_column(ascii_string(16))
    execution_state: Mapped[str] = mapped_column(ascii_string(24),default='pending')
    stage: Mapped[str] = mapped_column(ascii_string(16),default='scan')
    source_scope: Mapped[dict] = mapped_column(JSON)
    frozen_versions: Mapped[dict] = mapped_column(JSON)
    scope_digest: Mapped[bytes] = mapped_column(DIGEST)
    baseline: Mapped[dict] = mapped_column(JSON)
    high_water: Mapped[dict | None] = mapped_column(JSON)
    checkpoint_summary: Mapped[dict | None] = mapped_column(JSON)
    cutoff: Mapped[dict | None] = mapped_column(JSON)
    scanned_records: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    unique_source_ids: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    attempt_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    total_known: Mapped[bool] = mapped_column(Boolean,default=False,server_default='0')
    total_source_ids: Mapped[int | None] = mapped_column(U64)
    source_class_counts: Mapped[dict] = mapped_column(JSON,default=dict)
    reconcile_counts: Mapped[dict] = mapped_column(JSON,default=dict)
    unresolved_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    report_complete: Mapped[bool] = mapped_column(Boolean,default=False,server_default='0')
    started_at: Mapped[datetime | None] = mapped_column(INSTANT)
    ended_at: Mapped[datetime | None] = mapped_column(INSTANT)
    lease_owner: Mapped[str | None] = mapped_column(UUID)
    lease_version: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    lease_until: Mapped[datetime | None] = mapped_column(INSTANT)


class MemoryBackfillItem(ControlColumns, Base):
    __tablename__ = 'memory_backfill_item'
    __table_args__ = (UniqueConstraint('run_id','item_seq',name='uq_memory_backfill_item_seq'),
        UniqueConstraint('run_id','identity_digest',name='uq_memory_backfill_item_identity'),Index('ix_memory_backfill_item_run','run_id','item_seq'))
    id: Mapped[int] = mapped_column(U64.with_variant(Integer,'sqlite'),primary_key=True,autoincrement=True)
    run_id: Mapped[str] = mapped_column(UUID,ref('memory_backfill_run.run_id','fk_memory_backfill_item_run'))
    item_seq: Mapped[int] = mapped_column(U64)
    identity_id: Mapped[int | None] = mapped_column(U64)
    identity_key: Mapped[dict] = mapped_column(JSON)
    identity_digest: Mapped[bytes] = mapped_column(DIGEST)
    source_class: Mapped[str] = mapped_column(ascii_string(32))
    current_generation: Mapped[int | None] = mapped_column(U64)
    content_digest: Mapped[bytes | None] = mapped_column(DIGEST)
    index_result: Mapped[str] = mapped_column(ascii_string(24))
    reconcile_state: Mapped[str] = mapped_column(ascii_string(24))
    task_id: Mapped[str | None] = mapped_column(UUID)
    attempt_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    observed_at: Mapped[datetime] = mapped_column(INSTANT)
    reason: Mapped[str | None] = mapped_column(ascii_string(64))
