# -*- coding: utf-8 -*-
"""实时语音 M1 / STEP-003：ORM、迁移声明与应用层约束。"""

from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, call

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.database as database_module
from backend.database import Base
from backend.models.admin_user import AdminUser
from backend.models.agent_message import AgentMessage
from backend.models.realtime_voice import (
    VOICE_CALL_INITIATORS,
    VOICE_CALL_STATUSES,
    VOICE_CAPABILITY_KEYS,
    VOICE_CONTENT_CLEAR_REASONS,
    VOICE_CONTENT_SAFETY_STATUSES,
    VOICE_CRISIS_STATUSES,
    VOICE_EFFECTIVE_TEXT_EVIDENCE,
    VOICE_EVIDENCE_RESULTS,
    VOICE_EVIDENCE_SOURCE_TYPES,
    VOICE_FOLLOWUP_CONTENT_TYPES,
    VOICE_FOLLOWUP_STATUSES,
    VOICE_MEMORY_STATUSES,
    VOICE_MEMORY_TYPES,
    VOICE_POSTPROCESS_STATUSES,
    VOICE_RELATIONSHIP_STAGES,
    VOICE_SUMMARY_STATUSES,
    VOICE_TABLE_NAMES,
    VOICE_TURN_STATUSES,
    VoiceCall,
    VoiceCallCreateIdempotency,
    VoiceCallTurn,
    VoiceCapabilityEvidence,
    VoiceCrisisRecord,
    VoiceFollowupJob,
    VoiceMemoryJob,
    VoiceMemoryTrace,
    VoicePostprocessJob,
    VoiceUsageLedger,
)
from backend.models.user import User
from backend.services.voice_schema_validation_service import (
    VoiceReferenceValidationError,
    validate_voice_application_references,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = PROJECT_ROOT / "alembic/versions/v8c_voice_schema_baseline.py"
REVISION = "v8c_voice_schema_001"
DOWN_REVISION = "v8b_voice_growth_src_001"


EXPECTED_COLUMNS = {
    "voice_call": {
        "id", "call_id", "user_id", "initiated_by", "status", "end_reason",
        "provider", "provider_session_id", "provider_dialog_id", "connected_at",
        "ended_at", "duration_seconds", "free_seconds_used", "extra_seconds_used",
        "grace_seconds", "growth_eligible_seconds", "growth_points", "sort_seq",
        "summary_status", "call_summary", "user_emotion", "assistant_emotion",
        "unfinished_topics", "summary_reasoning", "config_snapshot",
        "capability_snapshot", "transcript_retention_days",
        "generated_retention_days", "transcript_expires_at",
        "generated_text_expires_at", "reasoning_expires_at", "deletion_fence_at",
        "deleted_at", "deleted_by", "created_at", "updated_at",
    },
    "voice_call_create_idempotency": {
        "id", "user_id", "idempotency_key", "request_payload_sha256", "call_id",
        "ticket_jti", "ticket_expires_at", "ticket_consumed_at",
        "replay_expires_at", "created_at", "updated_at",
    },
    "voice_call_turn": {
        "id", "call_id", "turn_index", "question_id", "reply_id", "user_text_final",
        "user_asr_confidence", "assistant_text_generated", "assistant_text_effective",
        "effective_text_evidence", "assistant_interrupted", "played_audio_ms",
        "playback_completed_at", "turn_status", "memory_status",
        "user_content_safety_status", "assistant_content_safety_status",
        "user_crisis_status", "assistant_crisis_status", "started_at", "finalized_at",
        "effective_text_expires_at", "generated_text_expires_at",
        "effective_text_cleared_at", "generated_text_cleared_at",
        "content_clear_reason", "created_at", "updated_at",
    },
    "voice_quota_account": {
        "id", "user_id", "free_quota_date", "free_remaining_seconds",
        "extra_remaining_seconds", "version", "created_at", "updated_at",
    },
    "voice_usage_ledger": {
        "id", "call_id", "segment_seq", "free_seconds_used", "extra_seconds_used",
        "usage_type", "created_at", "updated_at",
    },
    "voice_memory_job": {
        "id", "call_id", "turn_id", "turn_index", "pipeline_version", "status",
        "attempt_count", "next_retry_at", "fail_reason", "lease_owner",
        "lease_expires_at", "created_at", "updated_at",
    },
    "voice_postprocess_job": {
        "id", "call_id", "job_type", "status", "attempt_count", "next_retry_at",
        "fail_reason", "lease_owner", "lease_expires_at", "created_at", "updated_at",
    },
    "voice_followup_job": {
        "id", "call_id", "user_id", "candidate_due_at", "due_at", "latest_due_at",
        "content", "content_type", "status", "cancel_reason", "agent_message_id",
        "relationship_stage_snapshot", "schedule_config_version", "timezone_snapshot",
        "allowed_window_snapshot", "jitter_minutes", "attempt_count", "next_retry_at",
        "fail_reason", "lease_owner", "lease_expires_at", "created_at", "updated_at",
    },
    "voice_memory_trace": {
        "id", "call_id", "turn_index", "doc_id", "memory_type", "stable_key",
        "pipeline_version", "written_at", "created_at", "updated_at",
    },
    "voice_capability_evidence": {
        "id", "evidence_report_id", "evidence_run_id", "capability_key",
        "verification_result", "source_type", "provider_profile", "model_version",
        "protocol_profile", "adapter_version", "sdk_version", "evidence_suite_version",
        "evidence_fingerprint", "evidence_payload", "report_sha256", "tested_at",
        "verified_at", "evidence_ttl_days_snapshot", "expires_at", "operator_id",
        "created_at",
    },
    "voice_crisis_record": {
        "id", "call_id", "turn_index", "direction", "matched_keyword",
        "content_plaintext", "match_status", "is_persona_incident", "expires_at",
        "cleared_at", "created_at", "updated_at",
    },
    "voice_metric_daily": {
        "id", "business_date", "metric_name", "dimension_hash", "dimension_json",
        "metric_value", "created_at", "updated_at",
    },
}

EXPECTED_UNIQUES = {
    "voice_call": {"uk_voice_call_call_id": ("call_id",)},
    "voice_call_create_idempotency": {
        "uk_voice_call_idem_user_key": ("user_id", "idempotency_key"),
        "uk_voice_call_idem_call": ("call_id",),
        "uk_voice_call_idem_ticket_jti": ("ticket_jti",),
    },
    "voice_call_turn": {
        "uk_voice_turn_call_index": ("call_id", "turn_index"),
        "uk_voice_turn_call_question": ("call_id", "question_id"),
    },
    "voice_quota_account": {"uk_voice_quota_user": ("user_id",)},
    "voice_usage_ledger": {
        "uk_voice_usage_call_segment": ("call_id", "segment_seq"),
    },
    "voice_memory_job": {
        "uk_voice_memory_job_turn_pipeline": ("turn_id", "pipeline_version"),
    },
    "voice_postprocess_job": {
        "uk_voice_postprocess_call_type": ("call_id", "job_type"),
    },
    "voice_followup_job": {
        "uk_voice_followup_call_type": ("call_id", "content_type"),
    },
    "voice_memory_trace": {
        "uk_voice_memory_trace_call_turn_doc_pipeline": (
            "call_id", "turn_index", "doc_id", "pipeline_version",
        ),
    },
    "voice_capability_evidence": {
        "uk_voice_evidence_report": ("evidence_report_id",),
        "uk_voice_evidence_run_capability": ("evidence_run_id", "capability_key"),
    },
    "voice_crisis_record": {
        "uk_voice_crisis_call_turn_direction": ("call_id", "turn_index", "direction"),
    },
    "voice_metric_daily": {
        "uk_voice_metric_day_name_dimension": (
            "business_date", "metric_name", "dimension_hash",
        ),
    },
}

EXPECTED_INDEXES = {
    "voice_call": {
        "ix_voice_call_user_ended": ("user_id", "ended_at"),
        "ix_voice_call_status_ended": ("status", "ended_at"),
        "ix_voice_call_sort_seq": ("sort_seq",),
        "ix_voice_call_transcript_expires": ("transcript_expires_at",),
        "ix_voice_call_generated_expires": ("generated_text_expires_at",),
        "ix_voice_call_reasoning_expires": ("reasoning_expires_at",),
    },
    "voice_call_create_idempotency": {
        "ix_voice_call_idem_replay_expires": ("replay_expires_at",),
    },
    "voice_call_turn": {
        "ix_voice_turn_call_finalized": ("call_id", "finalized_at"),
        "ix_voice_turn_effective_expires": ("effective_text_expires_at",),
        "ix_voice_turn_generated_expires": ("generated_text_expires_at",),
    },
    "voice_quota_account": {"ix_voice_quota_free_date": ("free_quota_date",)},
    "voice_usage_ledger": {
        "ix_voice_usage_call_created": ("call_id", "created_at"),
    },
    "voice_memory_job": {
        "ix_voice_memory_job_status_retry": ("status", "next_retry_at"),
        "ix_voice_memory_job_call_turn": ("call_id", "turn_index"),
    },
    "voice_postprocess_job": {
        "ix_voice_postprocess_status_retry": ("status", "next_retry_at"),
    },
    "voice_followup_job": {
        "ix_voice_followup_status_due": ("status", "due_at"),
        "ix_voice_followup_status_retry": ("status", "next_retry_at"),
        "ix_voice_followup_user_due": ("user_id", "due_at"),
    },
    "voice_memory_trace": {
        "ix_voice_memory_trace_doc": ("doc_id",),
        "ix_voice_memory_trace_call_turn": ("call_id", "turn_index"),
    },
    "voice_capability_evidence": {
        "ix_voice_evidence_run": ("evidence_run_id",),
        "ix_voice_evidence_capability_created": ("capability_key", "created_at"),
        "ix_voice_evidence_fingerprint_result_expires": (
            "evidence_fingerprint", "verification_result", "expires_at",
        ),
    },
    "voice_crisis_record": {
        "ix_voice_crisis_expires": ("expires_at",),
        "ix_voice_crisis_call_created": ("call_id", "created_at"),
    },
    "voice_metric_daily": {
        "ix_voice_metric_name_day": ("metric_name", "business_date"),
    },
}

EXPECTED_FKS = {
    ("fk_voice_call_user", "voice_call", "user_id", "users", "id", "RESTRICT"),
    (
        "fk_voice_call_idem_user", "voice_call_create_idempotency", "user_id",
        "users", "id", "RESTRICT",
    ),
    (
        "fk_voice_quota_user", "voice_quota_account", "user_id",
        "users", "id", "RESTRICT",
    ),
    (
        "fk_voice_memory_job_turn", "voice_memory_job", "turn_id",
        "voice_call_turn", "id", "RESTRICT",
    ),
    (
        "fk_voice_followup_user", "voice_followup_job", "user_id",
        "users", "id", "RESTRICT",
    ),
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("voice_step003_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _orm_uniques(table: sa.Table) -> dict[str, tuple[str, ...]]:
    return {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def _orm_indexes(table: sa.Table) -> dict[str, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    }


def _column_declaration_contract(table: sa.Table) -> dict[str, tuple]:
    """按生产 MySQL 口径比较 ORM 与 migration 的列声明。"""

    return {
        column.name: (
            str(column.type.compile(dialect=mysql.dialect())),
            column.nullable,
        )
        for column in table.columns
    }


def test_voice_orm_exact_columns_uniques_indexes_and_contract_exceptions():
    assert set(VOICE_TABLE_NAMES) == set(EXPECTED_COLUMNS)
    for table_name in sorted(VOICE_TABLE_NAMES):
        table = Base.metadata.tables[table_name]
        additions = {"duration_seconds", "quota_date"} if table_name == "voice_usage_ledger" else set()
        if table_name == 'voice_call':
            additions = {'call01_fallback'}
        if table_name == 'voice_memory_job':
            additions = {'extraction_snapshot'}
        assert {column.name for column in table.columns} == EXPECTED_COLUMNS[table_name] | additions
        assert tuple(column.name for column in table.primary_key.columns) == ("id",)
        assert _orm_uniques(table) == EXPECTED_UNIQUES[table_name]
        assert _orm_indexes(table) == EXPECTED_INDEXES[table_name]

    evidence = Base.metadata.tables["voice_capability_evidence"]
    assert isinstance(evidence.c.id.type, sa.BigInteger)
    assert isinstance(evidence.c.evidence_payload.type, sa.JSON)
    assert "updated_at" not in evidence.c
    assert Base.metadata.tables["voice_crisis_record"].c.content_plaintext.nullable is True
    assert Base.metadata.tables["voice_call_create_idempotency"].c.idempotency_key.type.length == 64


def test_voice_orm_has_exactly_five_restrict_fks_and_zero_db_enums_or_checks():
    actual_fks = {
        (
            fk.constraint.name,
            fk.parent.table.name,
            fk.parent.name,
            fk.column.table.name,
            fk.column.name,
            fk.ondelete,
        )
        for table_name in VOICE_TABLE_NAMES
        for fk in Base.metadata.tables[table_name].foreign_keys
    }
    assert actual_fks == EXPECTED_FKS
    assert not [
        constraint
        for table_name in VOICE_TABLE_NAMES
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    assert not [
        column
        for table_name in VOICE_TABLE_NAMES
        for column in Base.metadata.tables[table_name].columns
        if isinstance(column.type, sa.Enum)
    ]


def test_migration_exact_tables_constraints_indexes_and_downgrade(monkeypatch):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()
    assert migration.revision == REVISION
    assert migration.down_revision == DOWN_REVISION

    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    created_tables: dict[str, sa.Table] = {}
    for create_call in fake_op.create_table.call_args_list:
        table = sa.Table(create_call.args[0], metadata, *create_call.args[1:])
        created_tables[table.name] = table
    assert set(created_tables) == set(VOICE_TABLE_NAMES)
    for table_name, table in created_tables.items():
        assert {column.name for column in table.columns} == EXPECTED_COLUMNS[table_name]
        assert tuple(column.name for column in table.primary_key.columns) == ("id",)
        assert _orm_uniques(table) == EXPECTED_UNIQUES[table_name]
        current = _column_declaration_contract(Base.metadata.tables[table_name])
        if table_name == "voice_usage_ledger":
            # v8c baseline remains immutable; v8d extensions have their own migration test.
            current = {k: v for k, v in current.items() if k not in {"duration_seconds", "quota_date"}}
        if table_name == 'voice_call':
            current = {k: v for k, v in current.items() if k != 'call01_fallback'}
        if table_name == 'voice_memory_job':
            current = {k: v for k, v in current.items() if k != 'extraction_snapshot'}
        assert _column_declaration_contract(table) == current

    migration_fks = {
        (
            fk.constraint.name,
            fk.parent.table.name,
            fk.parent.name,
            fk.column.table.name,
            fk.column.name,
            fk.ondelete,
        )
        for table in created_tables.values()
        for fk in table.foreign_keys
    }
    assert migration_fks == EXPECTED_FKS
    assert not [
        constraint
        for table in created_tables.values()
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    assert not [
        column
        for table in created_tables.values()
        for column in table.columns
        if isinstance(column.type, sa.Enum)
    ]

    migration_indexes = {
        table_name: {} for table_name in VOICE_TABLE_NAMES
    }
    for index_call in fake_op.create_index.call_args_list:
        index_name, table_name, columns = index_call.args[:3]
        assert not index_call.kwargs.get("unique", False)
        migration_indexes[table_name][index_name] = tuple(columns)
    assert migration_indexes == EXPECTED_INDEXES

    migration.downgrade()
    assert fake_op.drop_table.call_args_list == [
        call(table_name)
        for table_name in (
            "voice_metric_daily",
            "voice_crisis_record",
            "voice_capability_evidence",
            "voice_memory_trace",
            "voice_followup_job",
            "voice_postprocess_job",
            "voice_memory_job",
            "voice_usage_ledger",
            "voice_quota_account",
            "voice_call_turn",
            "voice_call_create_idempotency",
            "voice_call",
        )
    ]


@pytest.mark.parametrize("value", sorted(VOICE_CALL_INITIATORS))
def test_call_initiator_closed_values(value):
    assert VoiceCall(initiated_by=value).initiated_by == value


@pytest.mark.parametrize("value", sorted(VOICE_CALL_STATUSES))
def test_call_status_closed_values(value):
    assert VoiceCall(status=value).status == value


@pytest.mark.parametrize("value", sorted(VOICE_SUMMARY_STATUSES))
def test_summary_status_closed_values(value):
    assert VoiceCall(summary_status=value).summary_status == value


@pytest.mark.parametrize("field", ["initiated_by", "status", "summary_status"])
def test_call_closed_values_reject_unknown(field):
    with pytest.raises(ValueError):
        setattr(VoiceCall(), field, "not_in_contract")


@pytest.mark.parametrize(
    ("field", "allowed"),
    [
        ("effective_text_evidence", VOICE_EFFECTIVE_TEXT_EVIDENCE),
        ("turn_status", VOICE_TURN_STATUSES),
        ("memory_status", VOICE_MEMORY_STATUSES),
        ("user_content_safety_status", VOICE_CONTENT_SAFETY_STATUSES),
        ("assistant_content_safety_status", VOICE_CONTENT_SAFETY_STATUSES),
        ("user_crisis_status", VOICE_CRISIS_STATUSES),
        ("assistant_crisis_status", VOICE_CRISIS_STATUSES),
        ("content_clear_reason", VOICE_CONTENT_CLEAR_REASONS | {None}),
    ],
)
def test_turn_closed_values(field, allowed):
    for value in allowed:
        turn = VoiceCallTurn()
        setattr(turn, field, value)
        assert getattr(turn, field) == value
    with pytest.raises(ValueError):
        setattr(VoiceCallTurn(), field, "not_in_contract")


def test_job_trace_and_evidence_closed_values_and_invalid_values():
    cases = [
        (VoiceMemoryJob, "status", VOICE_MEMORY_STATUSES),
        (VoicePostprocessJob, "status", VOICE_POSTPROCESS_STATUSES),
        (VoiceFollowupJob, "content_type", VOICE_FOLLOWUP_CONTENT_TYPES),
        (VoiceFollowupJob, "status", VOICE_FOLLOWUP_STATUSES),
        (VoiceFollowupJob, "relationship_stage_snapshot", VOICE_RELATIONSHIP_STAGES),
        (VoiceMemoryTrace, "memory_type", VOICE_MEMORY_TYPES),
        (VoiceCapabilityEvidence, "capability_key", VOICE_CAPABILITY_KEYS),
        (VoiceCapabilityEvidence, "verification_result", VOICE_EVIDENCE_RESULTS),
        (VoiceCapabilityEvidence, "source_type", VOICE_EVIDENCE_SOURCE_TYPES),
    ]
    for model, field, allowed in cases:
        for value in allowed:
            row = model()
            setattr(row, field, value)
            assert getattr(row, field) == value
        with pytest.raises(ValueError):
            setattr(model(), field, "not_in_contract")
    for value in (7, 30, 90):
        assert VoiceCapabilityEvidence(evidence_ttl_days_snapshot=value).evidence_ttl_days_snapshot == value
    for value in (6, 91):
        with pytest.raises(ValueError):
            VoiceCapabilityEvidence(evidence_ttl_days_snapshot=value)


def test_non_closed_fields_remain_open_strings():
    for end_reason in (
        "user_hangup",
        "user_cancel",
        "exit_intent",
        "silence_timeout",
        "quota_exhausted",
        "hard_limit",
        "reconnect_timeout",
        "provider_error",
        "system_error",
    ):
        assert VoiceCall(end_reason=end_reason).end_reason == end_reason
    assert VoiceCall(end_reason="future_provider_reason").end_reason == "future_provider_reason"
    assert VoiceUsageLedger(usage_type="grace").usage_type == "grace"
    assert VoiceUsageLedger(usage_type="future_usage").usage_type == "future_usage"
    assert VoicePostprocessJob(job_type="future_job").job_type == "future_job"
    followup = VoiceFollowupJob(cancel_reason="future_cancel", fail_reason="future_fail")
    assert (followup.cancel_reason, followup.fail_reason) == ("future_cancel", "future_fail")
    crisis = VoiceCrisisRecord(
        direction="future_direction",
        match_status="future_match_status",
        content_plaintext=None,
    )
    assert crisis.content_plaintext is None


def _voice_call(
    call_id: str = "call-1",
    user_id: int = 1,
    deleted_by: int | None = None,
) -> VoiceCall:
    return VoiceCall(
        call_id=call_id,
        user_id=user_id,
        initiated_by="user",
        status="connected",
        duration_seconds=0,
        free_seconds_used=0,
        extra_seconds_used=0,
        grace_seconds=0,
        growth_eligible_seconds=0,
        growth_points=0,
        summary_status="pending",
        config_snapshot={},
        capability_snapshot={},
        transcript_retention_days=180,
        generated_retention_days=30,
        deleted_by=deleted_by,
    )


def _turn(call_id: str = "call-1", turn_index: int = 1) -> VoiceCallTurn:
    return VoiceCallTurn(
        call_id=call_id,
        turn_index=turn_index,
        question_id=f"q-{turn_index}",
        effective_text_evidence="none",
        assistant_interrupted=False,
        turn_status="collecting",
        memory_status="pending",
        user_content_safety_status="pending",
        assistant_content_safety_status="pending",
        user_crisis_status="pending",
        assistant_crisis_status="pending",
        started_at=datetime.utcnow(),
    )


@pytest_asyncio.fixture
async def voice_reference_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add_all(
            [
                User(id=1, username="voice-ref-1", password_hash="x"),
                User(id=2, username="voice-ref-2", password_hash="x"),
                AdminUser(
                    id=10,
                    username="voice-ref-admin",
                    password_hash="x",
                    role="super_admin",
                ),
                AgentMessage(
                    id=20,
                    user_id=1,
                    trigger_type="FUTURE",
                    content="voice follow-up",
                    action_score=1.0,
                    sort_seq=1,
                ),
                AgentMessage(
                    id=21,
                    user_id=2,
                    trigger_type="FUTURE",
                    content="other user follow-up",
                    action_score=1.0,
                    sort_seq=2,
                ),
            ]
        )
        call_row = _voice_call()
        turn_row = _turn()
        session.add_all([call_row, turn_row])
        await session.flush()
        yield session, turn_row.id
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_application_level_references_accept_valid_and_reject_dangling_or_mismatch(
    voice_reference_db,
):
    session, turn_id = voice_reference_db
    valid_records = [
        _voice_call(deleted_by=None),
        _voice_call(deleted_by=10),
        VoiceCallCreateIdempotency(user_id=1, call_id="call-1"),
        _turn(),
        VoiceUsageLedger(call_id="call-1"),
        VoiceMemoryJob(call_id="call-1", turn_id=turn_id, turn_index=1),
        VoicePostprocessJob(call_id="call-1"),
        VoiceFollowupJob(call_id="call-1", user_id=1, agent_message_id=None),
        VoiceFollowupJob(call_id="call-1", user_id=1, agent_message_id=20),
        VoiceMemoryTrace(call_id="call-1", turn_index=1),
        VoiceCrisisRecord(call_id="call-1", turn_index=1),
        VoiceCapabilityEvidence(operator_id=None),
        VoiceCapabilityEvidence(operator_id=10),
    ]
    for record in valid_records:
        await validate_voice_application_references(session, record)
    await validate_voice_application_references(
        session,
        VoiceCallCreateIdempotency(user_id=1, call_id=None),
    )

    invalid_records = [
        _voice_call(deleted_by=999999),
        _turn("missing-call"),
        VoiceCallCreateIdempotency(user_id=2, call_id="call-1"),
        VoiceUsageLedger(call_id="missing-call"),
        VoiceMemoryJob(call_id="wrong-call", turn_id=turn_id, turn_index=1),
        VoiceMemoryJob(call_id="call-1", turn_id=999999, turn_index=1),
        VoicePostprocessJob(call_id="missing-call"),
        VoiceFollowupJob(call_id="call-1", user_id=2),
        VoiceFollowupJob(call_id="call-1", user_id=1, agent_message_id=999999),
        VoiceFollowupJob(call_id="call-1", user_id=1, agent_message_id=21),
        VoiceMemoryTrace(call_id="call-1", turn_index=999),
        VoiceCrisisRecord(call_id="missing-call", turn_index=1),
        VoiceCapabilityEvidence(operator_id=999999),
    ]
    for record in invalid_records:
        with pytest.raises(VoiceReferenceValidationError):
            await validate_voice_application_references(session, record)
    with pytest.raises(TypeError):
        await validate_voice_application_references(session, object())


@pytest.mark.asyncio
async def test_runtime_create_all_does_not_create_voice_tables_and_fails_closed(monkeypatch):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database_module, "engine", test_engine)
    try:
        with pytest.raises(RuntimeError, match="实时语音数据库迁移未完成") as error:
            await database_module.create_all_tables()
        assert set(VOICE_TABLE_NAMES) <= set(str(error.value).split(": ", 1)[1].split(", "))
        async with test_engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names())
            )
        assert set(VOICE_TABLE_NAMES).isdisjoint(table_names)
    finally:
        await test_engine.dispose()
