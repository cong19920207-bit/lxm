# -*- coding: utf-8 -*-
"""实时语音 STEP-003：12 张语音表、索引与约束基线。

Revision ID: v8c_voice_schema_001
Revises: v8b_voice_growth_src_001
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v8c_voice_schema_001"
down_revision: Union[str, None] = "v8b_voice_growth_src_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps(*, include_updated_at: bool = True) -> list[sa.Column]:
    columns = [sa.Column("created_at", sa.DateTime(), nullable=False)]
    if include_updated_at:
        columns.append(sa.Column("updated_at", sa.DateTime(), nullable=False))
    return columns


def upgrade() -> None:
    op.create_table(
        "voice_call",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("initiated_by", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("end_reason", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("provider_dialog_id", sa.String(length=255), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("free_seconds_used", sa.Integer(), nullable=False),
        sa.Column("extra_seconds_used", sa.Integer(), nullable=False),
        sa.Column("grace_seconds", sa.Integer(), nullable=False),
        sa.Column("growth_eligible_seconds", sa.Integer(), nullable=False),
        sa.Column("growth_points", sa.Integer(), nullable=False),
        sa.Column("sort_seq", sa.BigInteger(), nullable=True),
        sa.Column("summary_status", sa.String(length=24), nullable=False),
        sa.Column("call_summary", sa.Text(), nullable=True),
        sa.Column("user_emotion", sa.String(length=64), nullable=True),
        sa.Column("assistant_emotion", sa.String(length=64), nullable=True),
        sa.Column("unfinished_topics", sa.JSON(), nullable=True),
        sa.Column("summary_reasoning", sa.Text(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("transcript_retention_days", sa.Integer(), nullable=False),
        sa.Column("generated_retention_days", sa.Integer(), nullable=False),
        sa.Column("transcript_expires_at", sa.DateTime(), nullable=True),
        sa.Column("generated_text_expires_at", sa.DateTime(), nullable=True),
        sa.Column("reasoning_expires_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_fence_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_voice_call_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uk_voice_call_call_id"),
    )
    op.create_index("ix_voice_call_user_ended", "voice_call", ["user_id", "ended_at"])
    op.create_index("ix_voice_call_status_ended", "voice_call", ["status", "ended_at"])
    op.create_index("ix_voice_call_sort_seq", "voice_call", ["sort_seq"])
    op.create_index(
        "ix_voice_call_transcript_expires",
        "voice_call",
        ["transcript_expires_at"],
    )
    op.create_index(
        "ix_voice_call_generated_expires",
        "voice_call",
        ["generated_text_expires_at"],
    )
    op.create_index(
        "ix_voice_call_reasoning_expires",
        "voice_call",
        ["reasoning_expires_at"],
    )

    op.create_table(
        "voice_call_create_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("request_payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=True),
        sa.Column("ticket_jti", sa.String(length=64), nullable=True),
        sa.Column("ticket_expires_at", sa.DateTime(), nullable=True),
        sa.Column("ticket_consumed_at", sa.DateTime(), nullable=True),
        sa.Column("replay_expires_at", sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_voice_call_idem_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uk_voice_call_idem_user_key",
        ),
        sa.UniqueConstraint("call_id", name="uk_voice_call_idem_call"),
        sa.UniqueConstraint("ticket_jti", name="uk_voice_call_idem_ticket_jti"),
    )
    op.create_index(
        "ix_voice_call_idem_replay_expires",
        "voice_call_create_idempotency",
        ["replay_expires_at"],
    )

    op.create_table(
        "voice_call_turn",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=True),
        sa.Column("reply_id", sa.String(length=64), nullable=True),
        sa.Column("user_text_final", sa.Text(), nullable=True),
        sa.Column("user_asr_confidence", sa.Float(), nullable=True),
        sa.Column("assistant_text_generated", sa.Text(), nullable=True),
        sa.Column("assistant_text_effective", sa.Text(), nullable=True),
        sa.Column("effective_text_evidence", sa.String(length=32), nullable=False),
        sa.Column("assistant_interrupted", sa.Boolean(), nullable=False),
        sa.Column("played_audio_ms", sa.Integer(), nullable=True),
        sa.Column("playback_completed_at", sa.DateTime(), nullable=True),
        sa.Column("turn_status", sa.String(length=24), nullable=False),
        sa.Column("memory_status", sa.String(length=24), nullable=False),
        sa.Column("user_content_safety_status", sa.String(length=24), nullable=False),
        sa.Column("assistant_content_safety_status", sa.String(length=24), nullable=False),
        sa.Column("user_crisis_status", sa.String(length=24), nullable=False),
        sa.Column("assistant_crisis_status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("effective_text_expires_at", sa.DateTime(), nullable=True),
        sa.Column("generated_text_expires_at", sa.DateTime(), nullable=True),
        sa.Column("effective_text_cleared_at", sa.DateTime(), nullable=True),
        sa.Column("generated_text_cleared_at", sa.DateTime(), nullable=True),
        sa.Column("content_clear_reason", sa.String(length=32), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "turn_index",
            name="uk_voice_turn_call_index",
        ),
        sa.UniqueConstraint(
            "call_id",
            "question_id",
            name="uk_voice_turn_call_question",
        ),
    )
    op.create_index(
        "ix_voice_turn_call_finalized",
        "voice_call_turn",
        ["call_id", "finalized_at"],
    )
    op.create_index(
        "ix_voice_turn_effective_expires",
        "voice_call_turn",
        ["effective_text_expires_at"],
    )
    op.create_index(
        "ix_voice_turn_generated_expires",
        "voice_call_turn",
        ["generated_text_expires_at"],
    )

    op.create_table(
        "voice_quota_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("free_quota_date", sa.Date(), nullable=False),
        sa.Column("free_remaining_seconds", sa.Integer(), nullable=False),
        sa.Column("extra_remaining_seconds", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_voice_quota_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uk_voice_quota_user"),
    )
    op.create_index(
        "ix_voice_quota_free_date",
        "voice_quota_account",
        ["free_quota_date"],
    )

    op.create_table(
        "voice_usage_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("segment_seq", sa.Integer(), nullable=False),
        sa.Column("free_seconds_used", sa.Integer(), nullable=False),
        sa.Column("extra_seconds_used", sa.Integer(), nullable=False),
        sa.Column("usage_type", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "segment_seq",
            name="uk_voice_usage_call_segment",
        ),
    )
    op.create_index(
        "ix_voice_usage_call_created",
        "voice_usage_ledger",
        ["call_id", "created_at"],
    )

    op.create_table(
        "voice_memory_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("fail_reason", sa.String(length=255), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["turn_id"],
            ["voice_call_turn.id"],
            name="fk_voice_memory_job_turn",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "turn_id",
            "pipeline_version",
            name="uk_voice_memory_job_turn_pipeline",
        ),
    )
    op.create_index(
        "ix_voice_memory_job_status_retry",
        "voice_memory_job",
        ["status", "next_retry_at"],
    )
    op.create_index(
        "ix_voice_memory_job_call_turn",
        "voice_memory_job",
        ["call_id", "turn_index"],
    )

    op.create_table(
        "voice_postprocess_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("fail_reason", sa.String(length=255), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "job_type",
            name="uk_voice_postprocess_call_type",
        ),
    )
    op.create_index(
        "ix_voice_postprocess_status_retry",
        "voice_postprocess_job",
        ["status", "next_retry_at"],
    )

    op.create_table(
        "voice_followup_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_due_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("latest_due_at", sa.DateTime(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("agent_message_id", sa.Integer(), nullable=True),
        sa.Column("relationship_stage_snapshot", sa.String(length=24), nullable=False),
        sa.Column("schedule_config_version", sa.String(length=64), nullable=False),
        sa.Column("timezone_snapshot", sa.String(length=64), nullable=False),
        sa.Column("allowed_window_snapshot", sa.JSON(), nullable=False),
        sa.Column("jitter_minutes", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("fail_reason", sa.String(length=255), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_voice_followup_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "content_type",
            name="uk_voice_followup_call_type",
        ),
    )
    op.create_index(
        "ix_voice_followup_status_due",
        "voice_followup_job",
        ["status", "due_at"],
    )
    op.create_index(
        "ix_voice_followup_status_retry",
        "voice_followup_job",
        ["status", "next_retry_at"],
    )
    op.create_index(
        "ix_voice_followup_user_due",
        "voice_followup_job",
        ["user_id", "due_at"],
    )

    op.create_table(
        "voice_memory_trace",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("doc_id", sa.String(length=100), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("stable_key", sa.String(length=255), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("written_at", sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "turn_index",
            "doc_id",
            "pipeline_version",
            name="uk_voice_memory_trace_call_turn_doc_pipeline",
        ),
    )
    op.create_index("ix_voice_memory_trace_doc", "voice_memory_trace", ["doc_id"])
    op.create_index(
        "ix_voice_memory_trace_call_turn",
        "voice_memory_trace",
        ["call_id", "turn_index"],
    )

    op.create_table(
        "voice_capability_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("evidence_report_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_run_id", sa.String(length=36), nullable=False),
        sa.Column("capability_key", sa.String(length=64), nullable=False),
        sa.Column("verification_result", sa.String(length=16), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("provider_profile", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("protocol_profile", sa.String(length=128), nullable=False),
        sa.Column("adapter_version", sa.String(length=128), nullable=False),
        sa.Column("sdk_version", sa.String(length=128), nullable=False),
        sa.Column("evidence_suite_version", sa.String(length=128), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("report_sha256", sa.String(length=64), nullable=False),
        sa.Column("tested_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_ttl_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        *_timestamps(include_updated_at=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_report_id", name="uk_voice_evidence_report"),
        sa.UniqueConstraint(
            "evidence_run_id",
            "capability_key",
            name="uk_voice_evidence_run_capability",
        ),
    )
    op.create_index(
        "ix_voice_evidence_run",
        "voice_capability_evidence",
        ["evidence_run_id"],
    )
    op.create_index(
        "ix_voice_evidence_capability_created",
        "voice_capability_evidence",
        ["capability_key", "created_at"],
    )
    op.create_index(
        "ix_voice_evidence_fingerprint_result_expires",
        "voice_capability_evidence",
        ["evidence_fingerprint", "verification_result", "expires_at"],
    )

    op.create_table(
        "voice_crisis_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("matched_keyword", sa.String(length=255), nullable=True),
        sa.Column("content_plaintext", sa.Text(), nullable=True),
        sa.Column("match_status", sa.String(length=32), nullable=False),
        sa.Column("is_persona_incident", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id",
            "turn_index",
            "direction",
            name="uk_voice_crisis_call_turn_direction",
        ),
    )
    op.create_index("ix_voice_crisis_expires", "voice_crisis_record", ["expires_at"])
    op.create_index(
        "ix_voice_crisis_call_created",
        "voice_crisis_record",
        ["call_id", "created_at"],
    )

    op.create_table(
        "voice_metric_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("dimension_hash", sa.String(length=64), nullable=False),
        sa.Column("dimension_json", sa.JSON(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_date",
            "metric_name",
            "dimension_hash",
            name="uk_voice_metric_day_name_dimension",
        ),
    )
    op.create_index(
        "ix_voice_metric_name_day",
        "voice_metric_daily",
        ["metric_name", "business_date"],
    )


def downgrade() -> None:
    op.drop_table("voice_metric_daily")
    op.drop_table("voice_crisis_record")
    op.drop_table("voice_capability_evidence")
    op.drop_table("voice_memory_trace")
    op.drop_table("voice_followup_job")
    op.drop_table("voice_postprocess_job")
    op.drop_table("voice_memory_job")
    op.drop_table("voice_usage_ledger")
    op.drop_table("voice_quota_account")
    op.drop_table("voice_call_turn")
    op.drop_table("voice_call_create_idempotency")
    op.drop_table("voice_call")
