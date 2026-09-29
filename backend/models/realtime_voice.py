# -*- coding: utf-8 -*-
"""实时语音 P1 的迁移专属 ORM 基线。

这些表必须由 Alembic 创建；应用启动时的 ``create_all_tables`` 会显式排除它们。
PRD 尚未冻结 call_id 的物理长度/排序规则，本基线统一使用 String(64) 作为
应用存储上限，不据此建立 call_id 物理外键。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime

from backend.database import Base


VOICE_TABLE_NAMES = frozenset(
    {
        "voice_call",
        "voice_call_create_idempotency",
        "voice_call_turn",
        "voice_quota_account",
        "voice_usage_ledger",
        "voice_memory_job",
        "voice_postprocess_job",
        "voice_followup_job",
        "voice_memory_trace",
        "voice_capability_evidence",
        "voice_crisis_record",
        "voice_metric_daily",
    }
)

VOICE_CALL_INITIATORS = frozenset({"user", "character"})
VOICE_CALL_STATUSES = frozenset(
    {
        "deciding",
        "ringing",
        "connected",
        "reconnecting",
        "ending",
        "ended",
        "missed",
        "failed",
        "cancelled",
    }
)
VOICE_SUMMARY_STATUSES = frozenset(
    {"pending", "ready", "failed", "not_applicable"}
)
VOICE_EFFECTIVE_TEXT_EVIDENCE = frozenset(
    {"full", "exact_played", "confirmed_sentences", "none"}
)
VOICE_TURN_STATUSES = frozenset(
    {"collecting", "finalized", "interrupted", "aborted"}
)
VOICE_MEMORY_STATUSES = frozenset(
    {"skipped", "pending", "processing", "success", "failed", "cancelled"}
)
VOICE_CONTENT_SAFETY_STATUSES = frozenset(
    {"pending", "passed", "matched", "error_allowed"}
)
VOICE_CRISIS_STATUSES = frozenset(
    {"pending", "passed", "matched", "suspected", "isolation_failed"}
)
VOICE_CONTENT_CLEAR_REASONS = frozenset({"expired", "admin_deleted"})
VOICE_POSTPROCESS_STATUSES = frozenset(
    {"pending", "processing", "success", "partial_success", "failed", "cancelled"}
)
VOICE_FOLLOWUP_CONTENT_TYPES = frozenset(
    {"topic_continuation", "emotional_followup", "missed_explanation"}
)
VOICE_FOLLOWUP_STATUSES = frozenset(
    {"pending", "processing", "sent", "cancelled", "failed"}
)
VOICE_RELATIONSHIP_STAGES = frozenset(
    {"stranger", "friend", "intimate", "soulmate"}
)
VOICE_MEMORY_TYPES = frozenset({"user", "character_private"})
VOICE_CAPABILITY_KEYS = frozenset(
    {
        "supports_current_turn_rag_gate",
        "supports_reply_cancel",
        "supports_context_truncate",
        "supports_playback_text_mapping",
        "supports_sentence_playback_ack",
        "supports_session_reconnect",
    }
)
VOICE_EVIDENCE_RESULTS = frozenset({"passed", "failed", "error"})
VOICE_EVIDENCE_SOURCE_TYPES = frozenset(
    {"phase0_import", "admin_capability_test"}
)


def _choice(field: str, value: str | None, allowed: frozenset[str]) -> str:
    if value not in allowed:
        raise ValueError(f"{field} 非法: {value!r}; allowed={sorted(allowed)!r}")
    return value


def _optional_choice(
    field: str,
    value: str | None,
    allowed: frozenset[str],
) -> str | None:
    if value is None:
        return None
    return _choice(field, value, allowed)


class VoiceCall(Base):
    __tablename__ = "voice_call"
    __table_args__ = (
        UniqueConstraint("call_id", name="uk_voice_call_call_id"),
        Index("ix_voice_call_user_ended", "user_id", "ended_at"),
        Index("ix_voice_call_status_ended", "status", "ended_at"),
        Index("ix_voice_call_sort_seq", "sort_seq"),
        Index("ix_voice_call_transcript_expires", "transcript_expires_at"),
        Index("ix_voice_call_generated_expires", "generated_text_expires_at"),
        Index("ix_voice_call_reasoning_expires", "reasoning_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_voice_call_user"),
        nullable=False,
    )
    initiated_by: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    call01_fallback: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_dialog_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    free_seconds_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_seconds_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grace_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    growth_eligible_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    growth_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    summary_status: Mapped[str] = mapped_column(String(24), nullable=False)
    call_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_emotion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assistant_emotion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unfinished_topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    capability_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    transcript_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generated_text_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reasoning_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deletion_fence_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("initiated_by")
    def _validate_initiated_by(self, _key: str, value: str) -> str:
        return _choice("initiated_by", value, VOICE_CALL_INITIATORS)

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        return _choice("status", value, VOICE_CALL_STATUSES)

    @validates("summary_status")
    def _validate_summary_status(self, _key: str, value: str) -> str:
        return _choice("summary_status", value, VOICE_SUMMARY_STATUSES)


class VoiceCallCreateIdempotency(Base):
    __tablename__ = "voice_call_create_idempotency"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uk_voice_call_idem_user_key"),
        UniqueConstraint("call_id", name="uk_voice_call_idem_call"),
        UniqueConstraint("ticket_jti", name="uk_voice_call_idem_ticket_jti"),
        Index("ix_voice_call_idem_replay_expires", "replay_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_voice_call_idem_user"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticket_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ticket_consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replay_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class VoiceCallTurn(Base):
    __tablename__ = "voice_call_turn"
    __table_args__ = (
        UniqueConstraint("call_id", "turn_index", name="uk_voice_turn_call_index"),
        UniqueConstraint("call_id", "question_id", name="uk_voice_turn_call_question"),
        Index("ix_voice_turn_call_finalized", "call_id", "finalized_at"),
        Index("ix_voice_turn_effective_expires", "effective_text_expires_at"),
        Index("ix_voice_turn_generated_expires", "generated_text_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reply_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_text_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_asr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    assistant_text_generated: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_text_effective: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_text_evidence: Mapped[str] = mapped_column(String(32), nullable=False)
    assistant_interrupted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    played_audio_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playback_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    turn_status: Mapped[str] = mapped_column(String(24), nullable=False)
    memory_status: Mapped[str] = mapped_column(String(24), nullable=False)
    user_content_safety_status: Mapped[str] = mapped_column(String(24), nullable=False)
    assistant_content_safety_status: Mapped[str] = mapped_column(String(24), nullable=False)
    user_crisis_status: Mapped[str] = mapped_column(String(24), nullable=False)
    assistant_crisis_status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_text_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generated_text_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_text_cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generated_text_cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content_clear_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("effective_text_evidence")
    def _validate_evidence(self, _key: str, value: str) -> str:
        return _choice("effective_text_evidence", value, VOICE_EFFECTIVE_TEXT_EVIDENCE)

    @validates("turn_status")
    def _validate_turn_status(self, _key: str, value: str) -> str:
        return _choice("turn_status", value, VOICE_TURN_STATUSES)

    @validates("memory_status")
    def _validate_memory_status(self, _key: str, value: str) -> str:
        return _choice("memory_status", value, VOICE_MEMORY_STATUSES)

    @validates("user_content_safety_status", "assistant_content_safety_status")
    def _validate_content_safety(self, key: str, value: str) -> str:
        return _choice(key, value, VOICE_CONTENT_SAFETY_STATUSES)

    @validates("user_crisis_status", "assistant_crisis_status")
    def _validate_crisis_status(self, key: str, value: str) -> str:
        return _choice(key, value, VOICE_CRISIS_STATUSES)

    @validates("content_clear_reason")
    def _validate_content_clear_reason(self, _key: str, value: str | None) -> str | None:
        return _optional_choice("content_clear_reason", value, VOICE_CONTENT_CLEAR_REASONS)


class VoiceQuotaAccount(Base):
    __tablename__ = "voice_quota_account"
    __table_args__ = (
        UniqueConstraint("user_id", name="uk_voice_quota_user"),
        Index("ix_voice_quota_free_date", "free_quota_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_voice_quota_user"),
        nullable=False,
    )
    free_quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    free_remaining_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_remaining_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class VoiceUsageLedger(Base):
    __tablename__ = "voice_usage_ledger"
    __table_args__ = (
        UniqueConstraint("call_id", "segment_seq", name="uk_voice_usage_call_segment"),
        Index("ix_voice_usage_call_created", "call_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    segment_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    free_seconds_used: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_seconds_used: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # M2: NULL means legacy evidence did not record this fact; never backfill it.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class VoiceMemoryJob(Base):
    __tablename__ = "voice_memory_job"
    __table_args__ = (
        UniqueConstraint(
            "turn_id",
            "pipeline_version",
            name="uk_voice_memory_job_turn_pipeline",
        ),
        Index("ix_voice_memory_job_status_retry", "status", "next_retry_at"),
        Index("ix_voice_memory_job_call_turn", "call_id", "turn_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "voice_call_turn.id",
            ondelete="RESTRICT",
            name="fk_voice_memory_job_turn",
        ),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extraction_snapshot: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        return _choice("status", value, VOICE_MEMORY_STATUSES)


class VoicePostprocessJob(Base):
    __tablename__ = "voice_postprocess_job"
    __table_args__ = (
        UniqueConstraint("call_id", "job_type", name="uk_voice_postprocess_call_type"),
        Index("ix_voice_postprocess_status_retry", "status", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        return _choice("status", value, VOICE_POSTPROCESS_STATUSES)


class VoiceFollowupJob(Base):
    __tablename__ = "voice_followup_job"
    __table_args__ = (
        UniqueConstraint("call_id", "content_type", name="uk_voice_followup_call_type"),
        Index("ix_voice_followup_status_due", "status", "due_at"),
        Index("ix_voice_followup_status_retry", "status", "next_retry_at"),
        Index("ix_voice_followup_user_due", "user_id", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_voice_followup_user"),
        nullable=False,
    )
    candidate_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latest_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relationship_stage_snapshot: Mapped[str] = mapped_column(String(24), nullable=False)
    schedule_config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    timezone_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_window_snapshot: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    jitter_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("content_type")
    def _validate_content_type(self, _key: str, value: str) -> str:
        return _choice("content_type", value, VOICE_FOLLOWUP_CONTENT_TYPES)

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        return _choice("status", value, VOICE_FOLLOWUP_STATUSES)

    @validates("relationship_stage_snapshot")
    def _validate_relationship_stage(self, _key: str, value: str) -> str:
        return _choice("relationship_stage_snapshot", value, VOICE_RELATIONSHIP_STAGES)


class VoiceMemoryTrace(Base):
    __tablename__ = "voice_memory_trace"
    __table_args__ = (
        UniqueConstraint(
            "call_id",
            "turn_index",
            "doc_id",
            "pipeline_version",
            name="uk_voice_memory_trace_call_turn_doc_pipeline",
        ),
        Index("ix_voice_memory_trace_doc", "doc_id"),
        Index("ix_voice_memory_trace_call_turn", "call_id", "turn_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(255), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    written_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @validates("memory_type")
    def _validate_memory_type(self, _key: str, value: str) -> str:
        return _choice("memory_type", value, VOICE_MEMORY_TYPES)


class VoiceCapabilityEvidence(Base):
    __tablename__ = "voice_capability_evidence"
    __table_args__ = (
        UniqueConstraint("evidence_report_id", name="uk_voice_evidence_report"),
        UniqueConstraint(
            "evidence_run_id",
            "capability_key",
            name="uk_voice_evidence_run_capability",
        ),
        Index("ix_voice_evidence_run", "evidence_run_id"),
        Index("ix_voice_evidence_capability_created", "capability_key", "created_at"),
        Index(
            "ix_voice_evidence_fingerprint_result_expires",
            "evidence_fingerprint",
            "verification_result",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    evidence_report_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evidence_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_result: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_profile: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(128), nullable=False)
    sdk_version: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_suite_version: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    report_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tested_at: Mapped[datetime] = mapped_column(DateTime().with_variant(MySQLDateTime(fsp=6), "mysql"), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime().with_variant(MySQLDateTime(fsp=6), "mysql"), nullable=True)
    evidence_ttl_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime().with_variant(MySQLDateTime(fsp=6), "mysql"), nullable=True)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    @validates("capability_key")
    def _validate_capability_key(self, _key: str, value: str) -> str:
        return _choice("capability_key", value, VOICE_CAPABILITY_KEYS)

    @validates("verification_result")
    def _validate_verification_result(self, _key: str, value: str) -> str:
        return _choice("verification_result", value, VOICE_EVIDENCE_RESULTS)

    @validates("source_type")
    def _validate_source_type(self, _key: str, value: str) -> str:
        return _choice("source_type", value, VOICE_EVIDENCE_SOURCE_TYPES)

    @validates("evidence_ttl_days_snapshot")
    def _validate_ttl(self, _key: str, value: int) -> int:
        if not 7 <= value <= 90:
            raise ValueError("evidence_ttl_days_snapshot 必须在 7..90")
        return value


class VoiceCrisisRecord(Base):
    __tablename__ = "voice_crisis_record"
    __table_args__ = (
        UniqueConstraint(
            "call_id",
            "turn_index",
            "direction",
            name="uk_voice_crisis_call_turn_direction",
        ),
        Index("ix_voice_crisis_expires", "expires_at"),
        Index("ix_voice_crisis_call_created", "call_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_plaintext: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_persona_incident: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class VoiceMetricDaily(Base):
    __tablename__ = "voice_metric_daily"
    __table_args__ = (
        UniqueConstraint(
            "business_date",
            "metric_name",
            "dimension_hash",
            name="uk_voice_metric_day_name_dimension",
        ),
        Index("ix_voice_metric_name_day", "metric_name", "business_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
