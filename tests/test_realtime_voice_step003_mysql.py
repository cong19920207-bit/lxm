# -*- coding: utf-8 -*-
"""实时语音 STEP-003 的 opt-in MySQL 8 Alembic 集成验证。"""

from __future__ import annotations

import os
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

from backend.config import get_mysql_sync_migration_url
from backend.database import Base
import backend.models  # noqa: F401  # 注册完整既有 ORM 元数据
from backend.models.realtime_voice import (
    VOICE_TABLE_NAMES,
    VoiceCall,
    VoiceCallCreateIdempotency,
    VoiceCallTurn,
    VoiceCapabilityEvidence,
    VoiceCrisisRecord,
    VoiceFollowupJob,
    VoiceMemoryJob,
    VoiceMemoryTrace,
    VoiceMetricDaily,
    VoicePostprocessJob,
    VoiceQuotaAccount,
    VoiceUsageLedger,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVISION = "v8c_voice_schema_001"
DOWN_REVISION = "v8b_voice_growth_src_001"
INTEGRATION_DATABASE_ENV = "REALTIME_VOICE_STEP003_DATABASE"


def _legacy_tables() -> tuple[sa.Table, ...]:
    """v8b 既有对象：完整 ORM 表集合减去 STEP-003 的 12 张语音表。"""

    return tuple(
        table
        for name, table in sorted(Base.metadata.tables.items())
        if name not in VOICE_TABLE_NAMES
    )


def _project(engine: sa.Engine, table: sa.Table) -> Counter[tuple[object, ...]]:
    primary_key = tuple(table.primary_key.columns)
    assert primary_key, f"既有表 {table.name} 必须有稳定主键以冻结全列投影"
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(*table.columns).order_by(*primary_key)
        ).all()
    return Counter(tuple(row) for row in rows)


def _legacy_projection(
    engine: sa.Engine, tables: tuple[sa.Table, ...]
) -> dict[str, tuple[tuple[str, ...], tuple[str, ...], Counter[tuple[object, ...]]]]:
    """冻结每张既有表的完整列序、主键序与全行多重集。"""

    return {
        table.name: (
            tuple(column.name for column in table.columns),
            tuple(column.name for column in table.primary_key.columns),
            _project(engine, table),
        )
        for table in tables
    }


def _revision(engine: sa.Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _orm_unique_contract(table_name: str) -> dict[str, tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def _orm_index_contract(table_name: str) -> dict[str, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in Base.metadata.tables[table_name].indexes
    }


def _expect_integrity_error(
    engine: sa.Engine,
    table: sa.Table,
    values: dict,
    mysql_error_code: int,
) -> None:
    with pytest.raises(sa.exc.IntegrityError) as error:
        with engine.begin() as connection:
            connection.execute(table.insert(), values)
    assert error.value.orig.args[0] == mysql_error_code


def _call_values(call_id: str, user_id: int = 1, **overrides) -> dict:
    values = {
        "call_id": call_id,
        "user_id": user_id,
        "initiated_by": "user",
        "status": "connected",
        "summary_status": "pending",
        "config_snapshot": {},
        "capability_snapshot": {},
        "transcript_retention_days": 180,
        "generated_retention_days": 30,
    }
    values.update(overrides)
    return values


def _turn_values(call_id: str, turn_index: int, question_id: str, **overrides) -> dict:
    values = {
        "call_id": call_id,
        "turn_index": turn_index,
        "question_id": question_id,
        "effective_text_evidence": "none",
        "turn_status": "collecting",
        "memory_status": "pending",
        "user_content_safety_status": "pending",
        "assistant_content_safety_status": "pending",
        "user_crisis_status": "pending",
        "assistant_crisis_status": "pending",
        "started_at": datetime(2026, 8, 31, 1, 0, 0),
    }
    values.update(overrides)
    return values


def _evidence_values(report_id: str, run_id: str, capability: str, **overrides) -> dict:
    values = {
        "evidence_report_id": report_id,
        "evidence_run_id": run_id,
        "capability_key": capability,
        "verification_result": "passed",
        "source_type": "phase0_import",
        "provider_profile": "provider@sha256:test",
        "model_version": "model-v1",
        "protocol_profile": "protocol-v1",
        "adapter_version": "adapter-v1",
        "sdk_version": "sdk-v1",
        "evidence_suite_version": "suite-v1",
        "evidence_fingerprint": "a" * 64,
        "evidence_payload": {"events": []},
        "report_sha256": "b" * 64,
        "tested_at": datetime(2026, 8, 31, 1, 0, 0),
        "verified_at": datetime(2026, 8, 31, 1, 1, 0),
        "evidence_ttl_days_snapshot": 30,
        "expires_at": datetime(2026, 9, 30, 1, 1, 0),
    }
    values.update(overrides)
    return values


EXPECTED_FKS = {
    (
        "fk_voice_call_user",
        "voice_call",
        ("user_id",),
        "users",
        ("id",),
        "RESTRICT",
    ),
    (
        "fk_voice_call_idem_user",
        "voice_call_create_idempotency",
        ("user_id",),
        "users",
        ("id",),
        "RESTRICT",
    ),
    (
        "fk_voice_quota_user",
        "voice_quota_account",
        ("user_id",),
        "users",
        ("id",),
        "RESTRICT",
    ),
    (
        "fk_voice_memory_job_turn",
        "voice_memory_job",
        ("turn_id",),
        "voice_call_turn",
        ("id",),
        "RESTRICT",
    ),
    (
        "fk_voice_followup_user",
        "voice_followup_job",
        ("user_id",),
        "users",
        ("id",),
        "RESTRICT",
    ),
}


def _assert_voice_schema(engine: sa.Engine) -> None:
    """以 MySQL 8 反射对象验证 STEP-003 的精确对象集。"""

    inspector = sa.inspect(engine)
    actual_voice_tables = set(inspector.get_table_names()) & set(VOICE_TABLE_NAMES)
    assert actual_voice_tables == set(VOICE_TABLE_NAMES)

    total_columns = total_uniques = total_indexes = 0
    actual_fks = set()
    for table_name in sorted(VOICE_TABLE_NAMES):
        columns = inspector.get_columns(table_name)
        assert {column["name"] for column in columns} == {
            column.name for column in Base.metadata.tables[table_name].columns
        }
        assert inspector.get_pk_constraint(table_name)["constrained_columns"] == ["id"]
        total_columns += len(columns)

        uniques = {
            item["name"]: tuple(item["column_names"])
            for item in inspector.get_unique_constraints(table_name)
        }
        assert uniques == _orm_unique_contract(table_name)
        total_uniques += len(uniques)

        ordinary_indexes = {
            item["name"]: tuple(item["column_names"])
            for item in inspector.get_indexes(table_name)
            if not item["unique"]
        }
        assert ordinary_indexes == _orm_index_contract(table_name)
        total_indexes += len(ordinary_indexes)

        assert inspector.get_check_constraints(table_name) == []
        assert not any(type(column["type"]).__name__ == "ENUM" for column in columns)
        for fk in inspector.get_foreign_keys(table_name):
            ondelete = fk.get("options", {}).get("ondelete", "RESTRICT").upper()
            actual_fks.add(
                (
                    fk["name"],
                    table_name,
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                    ondelete,
                )
            )

    assert (total_columns, total_uniques, total_indexes) == (189, 16, 26)
    assert actual_fks == EXPECTED_FKS

    evidence_columns = {
        column["name"]: column
        for column in inspector.get_columns("voice_capability_evidence")
    }
    assert "updated_at" not in evidence_columns
    assert "created_at" in evidence_columns
    assert isinstance(evidence_columns["id"]["type"], sa.BigInteger)
    assert isinstance(evidence_columns["evidence_payload"]["type"], sa.JSON)
    for required_text in (
        "provider_profile",
        "model_version",
        "protocol_profile",
        "adapter_version",
        "sdk_version",
        "evidence_suite_version",
    ):
        assert evidence_columns[required_text]["nullable"] is False

    crisis_columns = {
        column["name"]: column
        for column in inspector.get_columns("voice_crisis_record")
    }
    assert crisis_columns["content_plaintext"]["nullable"] is True


@pytest.mark.skipif(
    not os.getenv(INTEGRATION_DATABASE_ENV),
    reason=f"需要设置隔离 MySQL 库名 {INTEGRATION_DATABASE_ENV}",
)
def test_mysql8_schema_constraints_negative_matrix_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
):
    database_name = os.environ[INTEGRATION_DATABASE_ENV]
    assert database_name.startswith("lxm_step003_"), "只允许使用 STEP-003 隔离测试库"
    monkeypatch.setenv("MYSQL_DATABASE", database_name)
    engine = sa.create_engine(get_mysql_sync_migration_url(), poolclass=sa.pool.NullPool)
    assert sa.inspect(engine).get_table_names() == [], "隔离测试库必须为空库"

    legacy_tables = _legacy_tables()
    legacy_table_names = {table.name for table in legacy_tables}
    assert legacy_table_names == set(Base.metadata.tables) - set(VOICE_TABLE_NAMES)
    assert len(legacy_tables) == 26
    users = Base.metadata.tables["users"]
    admin_config = Base.metadata.tables["admin_config"]
    growth = Base.metadata.tables["relationship_growth_log"]
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    baseline_before: dict[
        str,
        tuple[tuple[str, ...], tuple[str, ...], Counter[tuple[object, ...]]],
    ] = {}

    try:
        Base.metadata.create_all(engine, tables=list(legacy_tables))
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names()) == legacy_table_names
        assert set(VOICE_TABLE_NAMES).isdisjoint(inspector.get_table_names())
        with engine.begin() as connection:
            version = connection.execute(sa.text("SELECT VERSION()"))
            assert str(version.scalar_one()).startswith("8.")

        # 空数据的 v8b 既有 schema / 空 voice schema 先独立完成一次往返。
        empty_baseline = _legacy_projection(engine, legacy_tables)
        assert all(not projection[2] for projection in empty_baseline.values())
        command.stamp(config, DOWN_REVISION)
        command.upgrade(config, REVISION)
        assert _revision(engine) == REVISION
        _assert_voice_schema(engine)
        assert _legacy_projection(engine, legacy_tables) == empty_baseline
        command.downgrade(config, DOWN_REVISION)
        assert _revision(engine) == DOWN_REVISION
        assert set(VOICE_TABLE_NAMES).isdisjoint(sa.inspect(engine).get_table_names())
        assert _legacy_projection(engine, legacy_tables) == empty_baseline

        # 再放入代表性既有行，验证存量库全表/全列/全行投影不漂移。
        with engine.begin() as connection:
            connection.execute(
                users.insert(),
                [
                    {
                        "id": 1,
                        "username": "existing-user-1",
                        "password_hash": "hash-1",
                    },
                    {
                        "id": 2,
                        "username": "existing-user-2",
                        "password_hash": "hash-2",
                    },
                ],
            )
            connection.execute(
                admin_config.insert(),
                {
                    "id": 11,
                    "config_key": "persona",
                    "config_value": "{}",
                    "version": 3,
                    "draft_revision": 7,
                },
            )
            connection.execute(
                growth.insert(),
                [
                    {
                        "id": 21,
                        "user_id": 1,
                        "action_type": "dialog",
                        "points": 2,
                        "created_at": datetime(2026, 8, 30, 1, 0, 0),
                    },
                    {
                        "id": 22,
                        "user_id": 1,
                        "action_type": "daily_login",
                        "points": 5,
                        "created_at": datetime(2026, 8, 30, 2, 0, 0),
                    },
                ],
            )
        baseline_before = _legacy_projection(engine, legacy_tables)

        command.upgrade(config, REVISION)
        assert _revision(engine) == REVISION
        _assert_voice_schema(engine)
        assert _legacy_projection(engine, legacy_tables) == baseline_before

        now = datetime(2026, 8, 31, 1, 0, 0)
        call_table = VoiceCall.__table__
        idem_table = VoiceCallCreateIdempotency.__table__
        turn_table = VoiceCallTurn.__table__
        quota_table = VoiceQuotaAccount.__table__
        usage_table = VoiceUsageLedger.__table__
        memory_job_table = VoiceMemoryJob.__table__
        post_table = VoicePostprocessJob.__table__
        followup_table = VoiceFollowupJob.__table__
        trace_table = VoiceMemoryTrace.__table__
        evidence_table = VoiceCapabilityEvidence.__table__
        crisis_table = VoiceCrisisRecord.__table__
        metric_table = VoiceMetricDaily.__table__

        with engine.begin() as connection:
            call_id = connection.execute(
                call_table.insert(), _call_values("call-1")
            ).inserted_primary_key[0]
            connection.execute(
                idem_table.insert(),
                {
                    "user_id": 1,
                    "idempotency_key": "idem-1",
                    "request_payload_sha256": "c" * 64,
                    "call_id": "call-1",
                    "ticket_jti": "ticket-1",
                    "replay_expires_at": now + timedelta(hours=24),
                },
            )
            turn_id = connection.execute(
                turn_table.insert(), _turn_values("call-1", 1, "question-1")
            ).inserted_primary_key[0]
            connection.execute(
                quota_table.insert(),
                {
                    "user_id": 1,
                    "free_quota_date": date(2026, 8, 31),
                    "free_remaining_seconds": 300,
                    "extra_remaining_seconds": 0,
                    "version": 1,
                },
            )
            connection.execute(
                usage_table.insert(),
                {
                    "call_id": "call-1",
                    "segment_seq": 1,
                    "free_seconds_used": 30,
                    "extra_seconds_used": 0,
                    "usage_type": "normal",
                },
            )
            connection.execute(
                memory_job_table.insert(),
                {
                    "call_id": "call-1",
                    "turn_id": turn_id,
                    "turn_index": 1,
                    "pipeline_version": "voice_memory_v1",
                    "status": "pending",
                },
            )
            connection.execute(
                post_table.insert(),
                {"call_id": "call-1", "job_type": "summary", "status": "pending"},
            )
            connection.execute(
                followup_table.insert(),
                {
                    "call_id": "call-1",
                    "user_id": 1,
                    "candidate_due_at": now,
                    "due_at": now,
                    "latest_due_at": now + timedelta(hours=24),
                    "content": "follow-up",
                    "content_type": "topic_continuation",
                    "status": "pending",
                    "relationship_stage_snapshot": "friend",
                    "schedule_config_version": "v1",
                    "timezone_snapshot": "Asia/Shanghai",
                    "allowed_window_snapshot": {"windows": [[9, 22]]},
                    "jitter_minutes": 0,
                },
            )
            connection.execute(
                trace_table.insert(),
                {
                    "call_id": "call-1",
                    "turn_index": 1,
                    "doc_id": "doc-1",
                    "memory_type": "user",
                    "stable_key": "用户-旅行-日本",
                    "pipeline_version": "voice_memory_v1",
                    "written_at": now,
                },
            )
            connection.execute(
                evidence_table.insert(),
                _evidence_values(
                    "00000000-0000-0000-0000-000000000001",
                    "10000000-0000-0000-0000-000000000001",
                    "supports_reply_cancel",
                ),
            )
            connection.execute(
                crisis_table.insert(),
                {
                    "call_id": "call-1",
                    "turn_index": 1,
                    "direction": "user",
                    "matched_keyword": "keyword",
                    "content_plaintext": "isolated",
                    "match_status": "matched",
                    "is_persona_incident": False,
                    "expires_at": now + timedelta(days=30),
                },
            )
            connection.execute(
                metric_table.insert(),
                {
                    "business_date": date(2026, 8, 31),
                    "metric_name": "voice.call.count",
                    "dimension_hash": "d" * 64,
                    "dimension_json": {"result": "ok"},
                    "metric_value": 1.0,
                },
            )
            # DB 没有 CHECK/native ENUM；未知状态只允许被应用层拦截。
            connection.execute(
                call_table.insert(),
                _call_values(
                    "call-db-open-string",
                    status="future_state",
                    summary_status="future_summary",
                ),
            )

        duplicate_cases = [
            (call_table, _call_values("call-1", user_id=2)),
            (
                idem_table,
                {
                    "user_id": 1, "idempotency_key": "idem-1",
                    "request_payload_sha256": "e" * 64, "call_id": "call-idem-new-1",
                    "ticket_jti": "ticket-new-1", "replay_expires_at": now,
                },
            ),
            (
                idem_table,
                {
                    "user_id": 1, "idempotency_key": "idem-new-2",
                    "request_payload_sha256": "e" * 64, "call_id": "call-1",
                    "ticket_jti": "ticket-new-2", "replay_expires_at": now,
                },
            ),
            (
                idem_table,
                {
                    "user_id": 1, "idempotency_key": "idem-new-3",
                    "request_payload_sha256": "e" * 64, "call_id": "call-idem-new-3",
                    "ticket_jti": "ticket-1", "replay_expires_at": now,
                },
            ),
            (turn_table, _turn_values("call-1", 1, "question-new")),
            (turn_table, _turn_values("call-1", 2, "question-1")),
            (
                quota_table,
                {
                    "user_id": 1, "free_quota_date": date(2026, 8, 31),
                    "free_remaining_seconds": 1, "extra_remaining_seconds": 0, "version": 2,
                },
            ),
            (
                usage_table,
                {
                    "call_id": "call-1", "segment_seq": 1,
                    "free_seconds_used": 0, "extra_seconds_used": 0,
                    "usage_type": "grace",
                },
            ),
            (
                memory_job_table,
                {
                    "call_id": "call-1", "turn_id": turn_id, "turn_index": 1,
                    "pipeline_version": "voice_memory_v1", "status": "failed",
                },
            ),
            (
                post_table,
                {"call_id": "call-1", "job_type": "summary", "status": "failed"},
            ),
            (
                followup_table,
                {
                    "call_id": "call-1", "user_id": 1,
                    "candidate_due_at": now, "due_at": now,
                    "latest_due_at": now, "content": "duplicate",
                    "content_type": "topic_continuation", "status": "pending",
                    "relationship_stage_snapshot": "friend",
                    "schedule_config_version": "v1", "timezone_snapshot": "Asia/Shanghai",
                    "allowed_window_snapshot": {}, "jitter_minutes": 0,
                },
            ),
            (
                trace_table,
                {
                    "call_id": "call-1", "turn_index": 1, "doc_id": "doc-1",
                    "memory_type": "user", "stable_key": "different",
                    "pipeline_version": "voice_memory_v1", "written_at": now,
                },
            ),
            (
                evidence_table,
                _evidence_values(
                    "00000000-0000-0000-0000-000000000001",
                    "10000000-0000-0000-0000-000000000002",
                    "supports_reply_cancel",
                ),
            ),
            (
                evidence_table,
                _evidence_values(
                    "00000000-0000-0000-0000-000000000002",
                    "10000000-0000-0000-0000-000000000001",
                    "supports_reply_cancel",
                ),
            ),
            (
                crisis_table,
                {
                    "call_id": "call-1", "turn_index": 1, "direction": "user",
                    "content_plaintext": None, "match_status": "cleared",
                    "is_persona_incident": False, "expires_at": now,
                },
            ),
            (
                metric_table,
                {
                    "business_date": date(2026, 8, 31),
                    "metric_name": "voice.call.count", "dimension_hash": "d" * 64,
                    "dimension_json": {}, "metric_value": 2.0,
                },
            ),
        ]
        for table, values in duplicate_cases:
            _expect_integrity_error(engine, table, values, 1062)

        fk_cases = [
            (call_table, _call_values("fk-call", user_id=999999)),
            (
                idem_table,
                {
                    "user_id": 999999, "idempotency_key": "fk-idem",
                    "request_payload_sha256": "f" * 64,
                    "replay_expires_at": now,
                },
            ),
            (
                quota_table,
                {
                    "user_id": 999999, "free_quota_date": date(2026, 8, 31),
                    "free_remaining_seconds": 0, "extra_remaining_seconds": 0,
                    "version": 1,
                },
            ),
            (
                memory_job_table,
                {
                    "call_id": "call-1", "turn_id": 999999, "turn_index": 1,
                    "pipeline_version": "fk-test", "status": "pending",
                },
            ),
            (
                followup_table,
                {
                    "call_id": "call-1", "user_id": 999999,
                    "candidate_due_at": now, "due_at": now, "latest_due_at": now,
                    "content": "fk", "content_type": "emotional_followup",
                    "status": "pending", "relationship_stage_snapshot": "friend",
                    "schedule_config_version": "v1", "timezone_snapshot": "Asia/Shanghai",
                    "allowed_window_snapshot": {}, "jitter_minutes": 0,
                },
            ),
        ]
        for table, values in fk_cases:
            _expect_integrity_error(engine, table, values, 1452)

        with pytest.raises(sa.exc.IntegrityError) as restricted_delete:
            with engine.begin() as connection:
                connection.execute(users.delete().where(users.c.id == 1))
        assert restricted_delete.value.orig.args[0] == 1451

        command.upgrade(config, REVISION)
        assert _revision(engine) == REVISION
        command.downgrade(config, DOWN_REVISION)
        assert _revision(engine) == DOWN_REVISION
        downgraded_tables = set(sa.inspect(engine).get_table_names())
        assert set(VOICE_TABLE_NAMES).isdisjoint(downgraded_tables)
        assert _legacy_projection(engine, legacy_tables) == baseline_before
    finally:
        with engine.begin() as connection:
            connection.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
            for table_name in sorted(VOICE_TABLE_NAMES, reverse=True):
                connection.execute(sa.text(f"DROP TABLE IF EXISTS `{table_name}`"))
            connection.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
        sa.Table("alembic_version", sa.MetaData()).drop(engine, checkfirst=True)
        Base.metadata.drop_all(engine, tables=list(reversed(legacy_tables)))
        engine.dispose()
