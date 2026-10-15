"""STEP-004 durable mutation and input handoff controls (Alembic owned)."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, BINARY, CHAR, DATETIME, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.memory_payload import ExactJSONDocument

MEMORY_CONTROL_TABLE_NAMES = frozenset({"memory_runtime_fence", "memory_identity", "memory_operation",
                                       "memory_index_task", "memory_use_claim", "memory_use_item"})
U64 = BigInteger().with_variant(BIGINT(unsigned=True), "mysql")
U32 = Integer().with_variant(INTEGER(unsigned=True), "mysql")
UUID = String(36).with_variant(CHAR(36, charset="ascii", collation="ascii_bin"), "mysql")
DIGEST = LargeBinary(32).with_variant(BINARY(32), "mysql")
INSTANT = DateTime().with_variant(DATETIME(fsp=6), "mysql")


def ascii_string(length):
    return String(length).with_variant(VARCHAR(length, charset="ascii", collation="ascii_bin"), "mysql")


def ref(target, name, *, later=False):
    return ForeignKey(target, name=name, ondelete="RESTRICT", use_alter=later)


class ControlColumns:
    created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
    revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")


class MemoryRuntimeFence(ControlColumns, Base):
    __tablename__ = "memory_runtime_fence"
    __table_args__ = (CheckConstraint("mode IN ('maintenance','active')", name="ck_memory_fence_mode"),)
    environment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_epoch: Mapped[int] = mapped_column(U64)
    target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
    mode: Mapped[str] = mapped_column(ascii_string(16))
    # S15 is a durable activation prerequisite.
    reset_run_id: Mapped[str | None] = mapped_column(UUID, ref("memory_reset_run.run_id", "fk_memory_fence_reset", later=True), nullable=True)


class MemoryIdentity(ControlColumns, Base):
    __tablename__ = "memory_identity"
    __table_args__ = (
        UniqueConstraint("target_fingerprint", "partition_name", "doc_id", name="uq_memory_identity_target_doc"),
        Index("ix_memory_identity_states_id", "source_state", "index_state", "id"),
        CheckConstraint("source_state IN ('unknown','live','deleted')", name="ck_memory_identity_source"),
        CheckConstraint("index_state IN ('not_ready','ready','repairing','manual','deleted')", name="ck_memory_identity_index"),
        CheckConstraint("generation >= 0 AND allocated_generation >= generation", name="ck_memory_identity_generation"),
        CheckConstraint("(memory_type IN ('character_global','character_knowledge') AND owner_user_id = 0) OR "
                        "(memory_type IN ('user','character_private') AND owner_user_id > 0)", name="ck_memory_identity_owner"),
    )
    id: Mapped[int] = mapped_column(U64.with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    target_epoch: Mapped[int] = mapped_column(U64)
    target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
    partition_name: Mapped[str] = mapped_column(ascii_string(64))
    doc_id: Mapped[str] = mapped_column(ascii_string(64))
    memory_type: Mapped[str] = mapped_column(String(32))
    owner_user_id: Mapped[int] = mapped_column(BigInteger)
    generation: Mapped[int] = mapped_column(U64, default=0, server_default="0")
    allocated_generation: Mapped[int] = mapped_column(U64, default=0, server_default="0")
    body_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
    source_state: Mapped[str] = mapped_column(ascii_string(24), default="unknown")
    index_state: Mapped[str] = mapped_column(ascii_string(24), default="not_ready")
    encoder_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    inflight_operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)


class MemoryOperation(ControlColumns, Base):
    __tablename__ = "memory_operation"
    __table_args__ = (
        UniqueConstraint("source_generation_key", name="uq_memory_operation_source_generation"),
        UniqueConstraint("task_id", "round_no", "attempt", name="uq_memory_operation_task_attempt"),
        UniqueConstraint("parent_operation_id", "identity_id", name="uq_memory_operation_parent_identity"),
        UniqueConstraint("owner_actor_type", "owner_actor_id", "idempotency_hash", name="uq_memory_operation_actor_request"),
        Index("ix_memory_operation_dispatch_lease", "dispatch_state", "lease_until"),
        Index("ix_memory_operation_source_reconcile", "source_result", "reconcile_until"),
        CheckConstraint("operation_kind IN ('create','update','delete','index','retry','baseline','batch')", name="ck_memory_operation_kind"),
        CheckConstraint("operation_kind = 'batch' OR (identity_id IS NOT NULL AND generation IS NOT NULL)", name="ck_memory_operation_identity"),
        CheckConstraint("source_result IN ('pending','confirmed','failed','unknown','superseded')", name="ck_memory_operation_source"),
        CheckConstraint("index_result IN ('pending','ready','failed','unknown','manual','not_required','superseded')", name="ck_memory_operation_index"),
        CheckConstraint("dispatch_state IN ('prepared','claimed','dispatching','confirmed','unknown','not_sent','superseded')", name="ck_memory_operation_dispatch"),
        CheckConstraint("operation_kind <> 'index' OR (task_id IS NOT NULL AND round_no IS NOT NULL AND attempt IS NOT NULL AND attempt >= 1)", name="ck_memory_operation_index_attempt"),
        CheckConstraint("(operation_kind IN ('create','update','delete') AND source_generation_key IS NOT NULL) OR "
                        "(operation_kind NOT IN ('create','update','delete') AND source_generation_key IS NULL)", name="ck_memory_operation_generation_key"),
    )
    operation_id: Mapped[str] = mapped_column(UUID, primary_key=True)
    identity_id: Mapped[int | None] = mapped_column(U64, ref("memory_identity.id", "fk_memory_operation_identity"), nullable=True)
    generation: Mapped[int | None] = mapped_column(U64, nullable=True)
    parent_operation_id: Mapped[str | None] = mapped_column(UUID, ref("memory_operation.operation_id", "fk_memory_operation_parent"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(UUID, ref("memory_index_task.task_id", "fk_memory_operation_task", later=True), nullable=True)
    round_no: Mapped[int | None] = mapped_column(U32, nullable=True)
    attempt: Mapped[int | None] = mapped_column(U32, nullable=True)
    source_generation_key: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
    operation_kind: Mapped[str] = mapped_column(ascii_string(24))
    owner_actor_type: Mapped[str] = mapped_column(ascii_string(16))
    owner_actor_id: Mapped[int] = mapped_column(BigInteger)
    client_request_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    idempotency_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
    request_hash: Mapped[bytes] = mapped_column(DIGEST)
    target_epoch: Mapped[int] = mapped_column(U64)
    source_result: Mapped[str] = mapped_column(ascii_string(24))
    index_result: Mapped[str] = mapped_column(ascii_string(24))
    dispatch_state: Mapped[str] = mapped_column(ascii_string(24))
    pending_payload: Mapped[dict | None] = mapped_column(ExactJSONDocument(), nullable=True)
    payload_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
    remote_tag: Mapped[str] = mapped_column(UUID)
    worker_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    worker_epoch: Mapped[int] = mapped_column(U64, default=0, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    reconcile_until: Mapped[datetime] = mapped_column(INSTANT)
    terminal_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    receipt_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    receipt_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    tombstone_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)


class MemoryIndexTask(ControlColumns, Base):
    __tablename__ = "memory_index_task"
    __table_args__ = (
        UniqueConstraint("identity_id", "generation", "encoder_version", name="uq_memory_index_task_generation_encoder"),
        Index("ix_memory_index_task_due", "state", "next_attempt_at", "task_id"),
        CheckConstraint("state IN ('pending','running','retry_wait','manual','completed','superseded')", name="ck_memory_index_task_state"),
    )
    task_id: Mapped[str] = mapped_column(UUID, primary_key=True)
    identity_id: Mapped[int] = mapped_column(U64, ref("memory_identity.id", "fk_memory_index_task_identity"))
    operation_id: Mapped[str] = mapped_column(UUID, ref("memory_operation.operation_id", "fk_memory_index_task_source"))
    generation: Mapped[int] = mapped_column(U64)
    encoder_version: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[bytes] = mapped_column(DIGEST)
    state: Mapped[str] = mapped_column(ascii_string(24))
    round_no: Mapped[int] = mapped_column(U32, default=0, server_default="0")
    attempt: Mapped[int] = mapped_column(U32, default=0, server_default="0")
    round_started_at: Mapped[datetime] = mapped_column(INSTANT)
    round_deadline_at: Mapped[datetime] = mapped_column(INSTANT)
    next_attempt_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
    worker_epoch: Mapped[int] = mapped_column(U64, default=0, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MemoryUseClaim(ControlColumns, Base):
    __tablename__ = "memory_use_claim"
    __table_args__ = (
        UniqueConstraint("consumer_kind", "execution_id", name="uq_memory_use_claim_execution"),
        CheckConstraint("state IN ('reserved','dispatching','handed_off','aborted','unknown')", name="ck_memory_use_claim_state"),
    )
    claim_id: Mapped[str] = mapped_column(UUID, primary_key=True)
    request_hash: Mapped[bytes] = mapped_column(DIGEST)
    consumer_kind: Mapped[str] = mapped_column(ascii_string(24))
    execution_id: Mapped[str] = mapped_column(UUID)
    target_epoch: Mapped[int] = mapped_column(U64)
    owner_id: Mapped[str] = mapped_column(UUID)
    state: Mapped[str] = mapped_column(ascii_string(24))
    created_deadline_at: Mapped[datetime] = mapped_column(INSTANT)
    handoff_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MemoryUseItem(ControlColumns, Base):
    __tablename__ = "memory_use_item"
    __table_args__ = (Index("ix_memory_use_item_identity_claim", "identity_id", "claim_id"),)
    claim_id: Mapped[str] = mapped_column(UUID, ref("memory_use_claim.claim_id", "fk_memory_use_item_claim"), primary_key=True)
    identity_id: Mapped[int] = mapped_column(U64, ref("memory_identity.id", "fk_memory_use_item_identity"), primary_key=True)
    generation: Mapped[int] = mapped_column(U64)
    body_hash: Mapped[bytes] = mapped_column(DIGEST)
    route: Mapped[str] = mapped_column(ascii_string(4))
    ordinal: Mapped[int] = mapped_column(U32)
