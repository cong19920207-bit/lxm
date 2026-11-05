"""Pet-domain storage. Facts, projections, presentation and diagnostics have separate owners.

Rules and archived evidence use restrictive references, never cascading cleanup.
All stored timestamps are UTC without tzinfo; business dates use Asia/Shanghai.
"""
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


UTC_TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"}
PET_TABLE_NAMES = frozenset({
    "pet_rule_snapshot", "pet_profile", "pet_state", "pet_fact_event", "pet_snapshot",
    "pet_display_entry", "pet_formal_text", "pet_text_source", "pet_task_candidate",
    "pet_diagnostic_payload",
    "pet_fact_request",
})


class PetRuleSnapshot(Base):
    __tablename__ = "pet_rule_snapshot"
    __table_args__ = (UniqueConstraint("kind", "version", name="uq_pet_rule_version"), TABLE_OPTIONS)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)


class PetProfile(Base):
    __tablename__ = "pet_profile"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_pet_profile_owner"), TABLE_OPTIONS)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    adopted_at: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    template: Mapped[dict] = mapped_column(JSON, nullable=False)
    stable_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    preference_discoveries: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    growth_rule_id: Mapped[str] = mapped_column(ForeignKey("pet_rule_snapshot.id", ondelete="RESTRICT"), nullable=False)
    data_version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)


class PetState(Base):
    __tablename__ = "pet_state"
    __table_args__ = (
        CheckConstraint("record_version >= 1", name="ck_pet_state_version"),
        CheckConstraint("closeness >= 0", name="ck_pet_state_closeness"),
        TABLE_OPTIONS,
    )
    pet_id: Mapped[str] = mapped_column(ForeignKey("pet_profile.id", ondelete="RESTRICT"), primary_key=True)
    record_version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    closeness: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unlocked_behaviors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    appearance_rule_id: Mapped[str | None] = mapped_column(ForeignKey("pet_rule_snapshot.id", ondelete="RESTRICT"))
    active_activity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settled_at: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)


class PetFactEvent(Base):
    __tablename__ = "pet_fact_event"
    __table_args__ = (
        ForeignKeyConstraint(["pet_id", "user_id"], ["pet_profile.id", "pet_profile.user_id"], ondelete="RESTRICT"),
        UniqueConstraint("pet_id", "request_key", name="uq_pet_fact_request"),
        UniqueConstraint("pet_id", "business_key", name="uq_pet_fact_business"),
        UniqueConstraint("id", "pet_id", name="uq_pet_fact_owner"),
        CheckConstraint("source IN ('actual_execution','rule_settlement','delegation_policy','admin_correction')", name="ck_pet_fact_source"),
        CheckConstraint("version_after = version_before + 1", name="ck_pet_fact_version"),
        Index("ix_pet_fact_day", "pet_id", "business_date", "occurred_at"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    business_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    participants: Mapped[list] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    reaction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state_before: Mapped[dict] = mapped_column(JSON, nullable=False)
    state_after: Mapped[dict] = mapped_column(JSON, nullable=False)
    closeness_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    closeness_delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule_snapshot_id: Mapped[str] = mapped_column(ForeignKey("pet_rule_snapshot.id", ondelete="RESTRICT"), nullable=False)


class PetSnapshot(Base):
    __tablename__ = "pet_snapshot"
    __table_args__ = (
        UniqueConstraint("pet_id", "business_key", name="uq_pet_snapshot_business"),
        ForeignKeyConstraint(["source_event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(ForeignKey("pet_profile.id", ondelete="RESTRICT"), nullable=False)
    business_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(36))
    captured_at: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    resources: Mapped[dict] = mapped_column(JSON, nullable=False)
    rule_snapshot_id: Mapped[str] = mapped_column(ForeignKey("pet_rule_snapshot.id", ondelete="RESTRICT"), nullable=False)


class PetFactRequest(Base):
    """Every accepted transport key, including business-key replays, stays bound."""
    __tablename__ = "pet_fact_request"
    __table_args__ = (
        ForeignKeyConstraint(["event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        TABLE_OPTIONS,
    )
    pet_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)


class PetDisplayEntry(Base):
    __tablename__ = "pet_display_entry"
    __table_args__ = (
        ForeignKeyConstraint(["source_event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        UniqueConstraint("pet_id", "surface", "source_event_id", name="uq_pet_display_source"),
        CheckConstraint("surface IN ('daily','album')", name="ck_pet_display_surface"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    surface: Mapped[str] = mapped_column(String(16), nullable=False)
    presentation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PetFormalText(Base):
    __tablename__ = "pet_formal_text"
    __table_args__ = (
        UniqueConstraint("pet_id", "business_key", "version", name="uq_pet_text_version"),
        UniqueConstraint("id", "pet_id", name="uq_pet_text_owner"),
        CheckConstraint("version >= 1", name="ck_pet_text_version"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(ForeignKey("pet_profile.id", ondelete="RESTRICT"), nullable=False)
    business_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_start: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    coverage_end: Mapped[datetime] = mapped_column(UTC_TIME, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)


class PetTextSource(Base):
    __tablename__ = "pet_text_source"
    __table_args__ = (
        ForeignKeyConstraint(["event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["text_id", "pet_id"], ["pet_formal_text.id", "pet_formal_text.pet_id"], ondelete="RESTRICT"),
        TABLE_OPTIONS,
    )
    text_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pet_id: Mapped[str] = mapped_column(String(36), nullable=False)


class PetTaskCandidate(Base):
    """Transactional outbox only; claiming and execution belong to later STEPs."""
    __tablename__ = "pet_task_candidate"
    __table_args__ = (
        ForeignKeyConstraint(["source_event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        UniqueConstraint("pet_id", "business_key", name="uq_pet_candidate_business"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    business_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)


class PetDiagnosticPayload(Base):
    """Only this table is eligible for short-lived diagnostic payload cleanup."""
    __tablename__ = "pet_diagnostic_payload"
    __table_args__ = (
        ForeignKeyConstraint(["event_id", "pet_id"], ["pet_fact_event.id", "pet_fact_event.pet_id"], ondelete="RESTRICT"),
        Index("ix_pet_diagnostic_retention", "recorded_at"),
        TABLE_OPTIONS,
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pet_id: Mapped[str] = mapped_column(ForeignKey("pet_profile.id", ondelete="RESTRICT"), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)
