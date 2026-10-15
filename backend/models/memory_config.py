"""Alembic-owned configuration publication anchors (STEP-003)."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BINARY, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

MEMORY_CONFIG_TABLE_NAMES = frozenset({"memory_config_head", "memory_config_publish"})
_time = DateTime().with_variant(DATETIME(fsp=6), "mysql")
_uuid = String(36).with_variant(CHAR(36, charset="ascii", collation="ascii_bin"), "mysql")
_digest = LargeBinary(32).with_variant(BINARY(32), "mysql")


class MemoryConfigHead(Base):
    __tablename__ = "memory_config_head"
    __table_args__ = (
        CheckConstraint("active_version >= 0 AND revision >= 0", name="ck_memory_config_head_nonnegative"),
    )

    config_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    active_admin_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    revision: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)


class MemoryConfigPublish(Base):
    __tablename__ = "memory_config_publish"
    __table_args__ = (
        UniqueConstraint("admin_id", "publish_id", name="uq_memory_config_publish_actor_id"),
        CheckConstraint("commit_state IN ('accepted','validating','committed','rejected','unknown')",
                        name="ck_memory_config_publish_state"),
        CheckConstraint("record_revision >= 1 AND lease_version >= 0",
                        name="ck_memory_config_publish_revision"),
        CheckConstraint("(commit_state = 'committed' AND committed_admin_config_id IS NOT NULL "
                        "AND committed_version IS NOT NULL) OR (commit_state <> 'committed' "
                        "AND committed_admin_config_id IS NULL AND committed_version IS NULL)",
                        name="ck_memory_config_publish_commit"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    publish_id: Mapped[str] = mapped_column(_uuid)
    admin_id: Mapped[int] = mapped_column(Integer)
    source_entry: Mapped[str] = mapped_column(String(64))
    canonical_key: Mapped[str] = mapped_column(String(100), index=True)
    request_digest: Mapped[bytes] = mapped_column(_digest)
    validated_digest: Mapped[bytes | None] = mapped_column(_digest, nullable=True)
    expected_head_revision: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    commit_state: Mapped[str] = mapped_column(String(16))
    committed_admin_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    committed_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)
    observed_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(_time, nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(_time, nullable=True)
    receipt_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
    tombstone_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    lease_owner: Mapped[str | None] = mapped_column(_uuid, nullable=True)
    lease_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
