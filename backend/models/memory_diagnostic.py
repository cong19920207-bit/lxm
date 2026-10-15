"""Permanent diagnostic history. Only explicit deletion removes snapshots."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.memory_control import U64, UUID, DIGEST, INSTANT, ascii_string

class MemoryDiagnosticRun(Base):
    __tablename__='memory_diagnostic_run'
    __table_args__=(UniqueConstraint('admin_id','request_id',name='uq_memory_diagnostic_request'),
        Index('ix_memory_diagnostic_user_created','user_id','created_at','run_id'),
        Index('ix_memory_diagnostic_active','environment_id','execution_state','deadline_at'),
        CheckConstraint("source IS NULL OR source IN ('main','openapi','step8')",name='ck_memory_diagnostic_source'),
        CheckConstraint("execution_state IN ('accepted','running','completed','degraded','failed','budget_blocked','interrupted','manual_required')",name='ck_memory_diagnostic_execution'),
        CheckConstraint("history_state IN ('pending','saved','failed','unknown','deleted')",name='ck_memory_diagnostic_history'),
        CheckConstraint('result_revision >= 1',name='ck_memory_diagnostic_revision'))
    run_id: Mapped[str]=mapped_column(UUID,primary_key=True)
    admin_id: Mapped[int]=mapped_column(Integer)
    user_id: Mapped[int|None]=mapped_column(Integer)
    environment_id: Mapped[str]=mapped_column(ascii_string(64))
    request_id: Mapped[str]=mapped_column(UUID)
    request_digest: Mapped[bytes]=mapped_column(DIGEST)
    source: Mapped[str|None]=mapped_column(ascii_string(8))
    parent_run_id: Mapped[str|None]=mapped_column(UUID)
    input_text: Mapped[str|None]=mapped_column(Text)
    execution_state: Mapped[str]=mapped_column(ascii_string(24))
    history_state: Mapped[str]=mapped_column(ascii_string(16))
    result_revision: Mapped[int]=mapped_column(U64,default=1,server_default='1')
    created_at: Mapped[datetime]=mapped_column(INSTANT)
    observed_at: Mapped[datetime]=mapped_column(INSTANT)
    deadline_at: Mapped[datetime]=mapped_column(INSTANT)
    persist_deadline_at: Mapped[datetime]=mapped_column(INSTANT)
    started_at: Mapped[datetime|None]=mapped_column(INSTANT)
    finished_at: Mapped[datetime|None]=mapped_column(INSTANT)
    terminal_at: Mapped[datetime|None]=mapped_column(INSTANT)
    stage: Mapped[str|None]=mapped_column(ascii_string(32))
    controlled_reason: Mapped[str|None]=mapped_column(ascii_string(64))
    frozen_versions: Mapped[dict|None]=mapped_column(JSON)
    context_sources: Mapped[dict|None]=mapped_column(JSON)
    candidate_snapshots: Mapped[list|None]=mapped_column(JSON)
    selection_result: Mapped[dict|None]=mapped_column(JSON)
    metrics: Mapped[dict|None]=mapped_column(JSON)
    snapshot_available: Mapped[bool]=mapped_column(Boolean,default=False,server_default='0')
    lease_owner: Mapped[str|None]=mapped_column(UUID)
    lease_version: Mapped[int]=mapped_column(U64,default=0,server_default='0')
    lease_until: Mapped[datetime|None]=mapped_column(INSTANT)
    deleted_at: Mapped[datetime|None]=mapped_column(INSTANT)
    tombstone_until: Mapped[datetime|None]=mapped_column(INSTANT)
