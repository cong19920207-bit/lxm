"""Deletable maintenance display projections, separate from durable controls."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.memory_control import U64, UUID, INSTANT, ascii_string

MEMORY_MAINTENANCE_TABLE_NAMES = frozenset({'memory_maintenance_event'})


class MemoryMaintenanceEvent(Base):
    __tablename__ = 'memory_maintenance_event'
    __table_args__ = (
        CheckConstraint("record_kind IN ('task','backfill')", name='ck_memory_event_kind'),
        CheckConstraint('task_id IS NOT NULL OR run_id IS NOT NULL', name='ck_memory_event_origin'),
        Index('ix_memory_event_task_created', 'task_id', 'created_at', 'id'),
        Index('ix_memory_event_run_created', 'run_id', 'created_at', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), 'sqlite'), primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(UUID, unique=True)
    record_kind: Mapped[str] = mapped_column(ascii_string(16))
    task_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    run_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    identity_id: Mapped[int | None] = mapped_column(U64, nullable=True)
    generation: Mapped[int | None] = mapped_column(U64, nullable=True)
    event_type: Mapped[str] = mapped_column(ascii_string(32))
    source_state: Mapped[str | None] = mapped_column(ascii_string(16), nullable=True)
    index_state: Mapped[str | None] = mapped_column(ascii_string(24), nullable=True)
    maintenance_state: Mapped[str | None] = mapped_column(ascii_string(24), nullable=True)
    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
    controlled_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    display_deleted_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
