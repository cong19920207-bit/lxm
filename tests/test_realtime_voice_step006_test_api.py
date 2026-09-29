# -*- coding: utf-8 -*-
"""STEP-006 admin test APIs and public force-test RED acceptance tests.

These tests intentionally describe the confirmed public behaviour before the
production routes and runner port exist.  The Provider boundary is replaced by
one injected short-lived runner; database, routing, RBAC, projections and audit
rows remain real.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401  register the complete ORM metadata
from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CAPABILITY_KEYS,
    build_canonical_voice_seed_manifest,
)
from backend.database import Base, get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.routers.admin import voice_config as voice_router_module
from backend.routers.admin.voice_config import router as voice_router
from backend.services.realtime_voice_config_service import (
    VOICE_CAPABILITY_FORCE_FORBIDDEN,
    VOICE_CAPABILITY_FORCE_CONFIRM_INVALID,
    VOICE_CAPABILITY_FORCE_STATUS_INVALID,
    VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED,
    canonical_json,
    content_sha256,
)
from backend.utils.admin_auth import create_admin_token, get_current_admin


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

TEST_VERSION = "admin-voice-test/v1"
_REFERENCE_NOW = datetime.now(timezone.utc).replace(microsecond=0)
TESTED_AT = _REFERENCE_NOW.isoformat().replace("+00:00", "Z")
CAPABILITY_KEY = "supports_reply_cancel"
EVIDENCE_RUN_ID = "22222222-2222-4222-8222-222222222222"
EVIDENCE_REPORT_ID = "11111111-1111-4111-8111-111111111111"
SECRET_REF = "DOUBAO_S2S_ACCESS_KEY"
SECRET_SENTINEL = "step006-test-api-secret-SENTINEL"
role_ids: dict[str, int] = {}

PERSONA_VALUE = canonical_json(
    {
        "background": "林小梦",
        "personality": "温柔",
        "emotion_preference": "共情",
        "language_style": "自然",
        "behavior_pattern": "倾听",
    }
)
PERSONA_REF = {
    "config_key": "persona",
    "version": 1,
    "content_sha256": "sha256:"
    + hashlib.sha256(PERSONA_VALUE.encode("utf-8")).hexdigest(),
}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dimensions() -> dict[str, str]:
    return {
        "provider_profile": "doubao-admin-test-profile",
        "model_version": "2.2.0.0",
        "protocol_profile": "doubao_dialog_v3_pcm",
        "adapter_version": "voice_adapter_v1",
        "sdk_version": "doubao-sdk-v1",
        "evidence_suite_version": "step006-admin-test-v1",
    }


def _causal_event(event_id: int, event_name: str, ordinal: int, received_at_ms: int) -> dict:
    return {
        "ordinal": ordinal,
        "received_at_ms": received_at_ms,
        "event_id": event_id,
        "event_name": event_name,
        "target_event": True,
        "message_type": "SERVER_FULL_RESPONSE",
        "payload_kind": "object",
        "payload_size": 24,
        "is_audio": False,
        "parse_error": False,
        "correlation_tokens": {
            "frame.session_id": "hmac256:111111111111111111111111",
            "payload.question_id": "hmac256:222222222222222222222222",
            "payload.reply_id": "hmac256:333333333333333333333333",
            "payload.sentence_id": "hmac256:555555555555555555555555",
        },
        "payload_shape": {
            "object_keys": [
                "payload.question_id",
                "payload.reply_id",
                "payload.sentence_id",
            ],
            "list_lengths": {},
            "numeric_fields": {},
            "boolean_fields": {},
            "text_fields": {},
            "binary_fields": {},
            "redacted_key_classes": [],
        },
    }


def _capability_record() -> dict[str, Any]:
    dimensions = _dimensions()
    payload = {
        "schema_version": "phase0-capability-evidence/v3",
        "capability_status": "verified",
        "reason_code": "active_reply_cancelled_and_local_stop_applied_within_grace",
        "degradation_mode": "next_turn",
        "event_evidence": [
            _causal_event(350, "TTSSentenceStart", 1, 1_000),
            _causal_event(359, "TTSEnded", 2, 1_400),
        ],
        "action_evidence": [
            {
                "action": "client_interrupt_sent",
                "at_ms": 1_200,
                "reply_active": True,
                "success": True,
                "stop_token": "hmac256:666666666666666666666666",
                "local_stop_at_ms": 1_150,
                "provider_ordinal_after_send": 1,
                "target_tts_start_ordinal": 1,
                "target_reply_generation": 1,
                "correlation_tokens": {
                    "frame.session_id": "hmac256:111111111111111111111111",
                    "payload.question_id": "hmac256:222222222222222222222222",
                    "payload.reply_id": "hmac256:333333333333333333333333",
                },
            },
            {
                "action": "client_stop_playback_applied",
                "at_ms": 1_200,
                "success": True,
                "stop_token": "hmac256:666666666666666666666666",
                "target_reply_generation": 1,
                "provider_ordinal_after_ack": 1,
                "correlation_tokens": {
                    "payload.reply_id": "hmac256:333333333333333333333333"
                },
            },
        ],
        "runtime_conditions": {
            "real_provider": True,
            "network_profile": "admin_test",
        },
        "production_import_ready": True,
    }
    verified_at = TESTED_AT
    expires_at = (
        datetime.fromisoformat(TESTED_AT.replace("Z", "+00:00"))
        + timedelta(days=30)
    ).isoformat().replace("+00:00", "Z")
    record_without_hash = {
        "evidence_report_id": EVIDENCE_REPORT_ID,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "capability_key": CAPABILITY_KEY,
        "verification_result": "passed",
        "source_type": "admin_capability_test",
        **dimensions,
        "evidence_fingerprint": _canonical_sha256(dimensions),
        "evidence_payload": payload,
        "tested_at": TESTED_AT,
        "verified_at": verified_at,
        "evidence_ttl_days_snapshot": 30,
        "expires_at": expires_at,
    }
    return {
        **record_without_hash,
        "report_sha256": _canonical_sha256(record_without_hash),
    }


class ControlledVoiceTestRunner:
    """Complete fake of the confirmed short-lived Provider runner port."""

    def __init__(self) -> None:
        self.connection_calls = 0
        self.capability_calls = 0
        self.close_calls = 0
        self.close_cancelled_calls = 0
        self.cancelled_calls = 0
        self.block = False
        self.block_close = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.close_started = asyncio.Event()
        self.close_release = asyncio.Event()

    async def _maybe_block(self) -> None:
        self.started.set()
        if not self.block:
            return
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled_calls += 1
            raise

    async def run_connection(self, *args, **kwargs) -> dict[str, Any]:
        self.connection_calls += 1
        await self._maybe_block()
        return {
            "status": "passed",
            "latency_ms": 17,
            "failure_category": "none",
            "tested_at": TESTED_AT,
        }

    async def run_capability(self, *args, **kwargs) -> dict[str, Any]:
        self.capability_calls += 1
        await self._maybe_block()
        return {
            "status": "passed",
            "latency_ms": 23,
            "failure_category": "none",
            "tested_at": TESTED_AT,
            "evidence_record": _capability_record(),
        }

    async def aclose(self) -> None:
        self.close_calls += 1
        self.close_started.set()
        if not self.block_close:
            return
        try:
            await self.close_release.wait()
        except asyncio.CancelledError:
            self.close_cancelled_calls += 1
            raise


async def override_get_db():
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def override_current_admin(request: Request):
    role = request.headers.get("x-admin-role", "observer")
    return SimpleNamespace(
        id=role_ids[role],
        username=f"step006-test-api-{role}",
        role=role,
    )


app = FastAPI()
app.include_router(voice_router, prefix="/api/admin/voice")
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_admin] = override_current_admin

real_auth_app = FastAPI()
real_auth_app.include_router(voice_router, prefix="/api/admin/voice")
real_auth_app.dependency_overrides[get_db] = override_get_db


def _runner_dependency():
    """Return the production runner dependency once the RED port is added."""

    return getattr(voice_router_module, "get_voice_test_runner", None)


@pytest.fixture
def runner() -> ControlledVoiceTestRunner:
    return ControlledVoiceTestRunner()


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch: pytest.MonkeyPatch, runner: ControlledVoiceTestRunner):
    role_ids.clear()
    monkeypatch.setenv(SECRET_REF, SECRET_SENTINEL)

    dependency = _runner_dependency()
    if dependency is not None:
        app.dependency_overrides[dependency] = lambda: runner
        real_auth_app.dependency_overrides[dependency] = lambda: runner

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
            admin = AdminUser(
                username=f"step006-test-api-{role}",
                password_hash="not-used",
                role=role,
                is_active=True,
                is_locked=False,
                token_version=0,
            )
            session.add(admin)
            await session.flush()
            role_ids[role] = admin.id
        session.add(
            AdminConfig(
                config_key="persona",
                config_value=PERSONA_VALUE,
                version=1,
                is_draft=False,
                is_active=True,
                updated_by="step006-test-api-super_admin",
            )
        )
        await session.commit()

    yield

    if dependency is not None:
        app.dependency_overrides.pop(dependency, None)
        real_auth_app.dependency_overrides.pop(dependency, None)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://step006-test-api",
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def real_auth_client():
    async with AsyncClient(
        transport=ASGITransport(app=real_auth_app),
        base_url="http://step006-test-api-real-auth",
    ) as http_client:
        yield http_client


def _headers(role: str) -> dict[str, str]:
    return {"x-admin-role": role}


def _real_auth_headers(role: str) -> dict[str, str]:
    token = create_admin_token(role_ids[role], role, token_version=0)
    return {"Authorization": f"Bearer {token}"}


def _default_config(*, test_user_ids: list[int] | None = None) -> dict[str, Any]:
    config = build_canonical_voice_seed_manifest(PERSONA_REF)[VOICE_CALL_CONFIG_KEY]
    config["global"]["test_user_ids"] = (
        [101] if test_user_ids is None else deepcopy(test_user_ids)
    )
    return config


def _config_with_status(status: str) -> dict[str, Any]:
    config = _default_config()
    capability = config["capabilities"][CAPABILITY_KEY]
    if status == "failed":
        capability["verification_status"] = "failed"
        capability["last_test_result"] = "failed"
        return config
    if status == "verified":
        dimensions = _dimensions()
        capability.update(
            {
                "verification_status": "verified",
                **dimensions,
                "evidence_fingerprint": _canonical_sha256(dimensions),
                "verified_at": TESTED_AT,
                "expires_at": (
                    datetime.fromisoformat(TESTED_AT.replace("Z", "+00:00"))
                    + timedelta(days=30)
                ).isoformat(),
                "evidence_report_id": EVIDENCE_REPORT_ID,
                "last_test_result": "passed",
            }
        )
        return config
    raise AssertionError(f"unsupported fixture status: {status}")


async def _insert_voice_config(
    *,
    active: dict[str, Any] | None = None,
    draft: dict[str, Any] | None = None,
    draft_revision: int = 3,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_config = deepcopy(active or _default_config())
    draft_config = deepcopy(draft or active_config)
    async with session_factory() as session:
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(active_config),
                    version=1,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-test-api-super_admin",
                ),
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(draft_config),
                    version=0,
                    draft_revision=draft_revision,
                    is_draft=True,
                    is_active=False,
                    updated_by="step006-test-api-super_admin",
                ),
            ]
        )
        await session.commit()
    return active_config, draft_config


async def _voice_rows_projection() -> list[tuple[Any, ...]]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig)
                .where(AdminConfig.config_key == VOICE_CALL_CONFIG_KEY)
                .order_by(AdminConfig.id.asc())
            )
        ).scalars().all()
        return [
            (
                row.id,
                row.config_value,
                row.version,
                row.draft_revision,
                row.is_active,
                row.is_draft,
                row.updated_by,
            )
            for row in rows
        ]


async def _evidence_rows() -> list[VoiceCapabilityEvidence]:
    async with session_factory() as session:
        return (
            await session.execute(
                select(VoiceCapabilityEvidence).order_by(
                    VoiceCapabilityEvidence.id.asc()
                )
            )
        ).scalars().all()


async def _operation_logs() -> list[AdminOperationLog]:
    async with session_factory() as session:
        return (
            await session.execute(
                select(AdminOperationLog).order_by(AdminOperationLog.id.asc())
            )
        ).scalars().all()


def _connection_data() -> dict[str, Any]:
    return {
        "status": "passed",
        "latency_ms": 17,
        "failure_category": "none",
        "test_version": TEST_VERSION,
        "tested_draft_revision": 3,
        "tested_at": TESTED_AT,
    }


def _capability_data() -> dict[str, Any]:
    return {
        "status": "passed",
        "latency_ms": 23,
        "failure_category": "none",
        "test_version": TEST_VERSION,
        "tested_draft_revision": 3,
        "tested_at": TESTED_AT,
        "capability_key": CAPABILITY_KEY,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "evidence_report_id": EVIDENCE_REPORT_ID,
    }


def _assert_success_response(response, expected_data: dict[str, Any]) -> None:
    assert response.status_code == 200, response.text
    assert response.json() == {
        "code": 0,
        "data": expected_data,
        "message": "success",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("json_body", [None, {}])
async def test_connection_accepts_omitted_or_empty_body_and_returns_exact_contract(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    json_body,
):
    """捕获连接端点错误要求 body，或返回多字段、错枚举/版本/草稿 revision。"""

    await _insert_voice_config()
    kwargs = {} if json_body is None else {"json": json_body}
    response = await client.post(
        "/api/admin/voice/config/test-connection",
        headers=_headers("tech_ops"),
        **kwargs,
    )

    _assert_success_response(response, _connection_data())
    assert runner.connection_calls == 1
    assert runner.capability_calls == 0


@pytest.mark.asyncio
async def test_connection_rejects_non_empty_body_before_runner_or_state_change(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
):
    """捕获连接 API 宽松吞掉未知字段并在 422 前读取 Secret 或启动 runner。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    response = await client.post(
        "/api/admin/voice/config/test-connection",
        headers=_headers("tech_ops"),
        json={"provider": "caller-must-not-override"},
    )

    assert response.status_code == 422, response.text
    assert runner.connection_calls == runner.capability_calls == 0
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == []


@pytest.mark.asyncio
async def test_connection_rejects_explicit_json_null_before_runner(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
):
    """Only an omitted body or an exact empty object is part of the contract."""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    response = await client.post(
        "/api/admin/voice/config/test-connection",
        headers={**_headers("tech_ops"), "content-type": "application/json"},
        content="null",
    )

    assert response.status_code == 422, response.text
    assert runner.connection_calls == runner.capability_calls == 0
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == []


@pytest.mark.asyncio
async def test_connection_never_changes_capability_or_writes_evidence(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
):
    """捕获握手成功被误当成能力 verified，或连接测试误写 evidence 事实行。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    response = await client.post(
        "/api/admin/voice/config/test-connection",
        headers=_headers("super_admin"),
        json={},
    )

    _assert_success_response(response, _connection_data())
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == []
    assert runner.close_calls == 1


@pytest.mark.asyncio
async def test_capability_accepts_one_key_writes_one_admin_test_evidence_and_only_target_projection(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
):
    """捕获单能力测试未写事实、写错来源、批量改六项、修改 active 或保留旧强制态。"""

    active, draft = await _insert_voice_config()
    response = await client.post(
        "/api/admin/voice/config/test-capability",
        headers=_headers("super_admin"),
        json={"capability_key": CAPABILITY_KEY},
    )

    _assert_success_response(response, _capability_data())
    assert runner.capability_calls == 1
    assert runner.connection_calls == 0
    assert runner.close_calls == 1

    evidence_rows = await _evidence_rows()
    assert len(evidence_rows) == 1
    evidence = evidence_rows[0]
    assert (
        evidence.evidence_report_id,
        evidence.evidence_run_id,
        evidence.capability_key,
        evidence.verification_result,
        evidence.source_type,
        evidence.operator_id,
    ) == (
        EVIDENCE_REPORT_ID,
        EVIDENCE_RUN_ID,
        CAPABILITY_KEY,
        "passed",
        "admin_capability_test",
        role_ids["super_admin"],
    )

    rows = await _voice_rows_projection()
    active_row = next(row for row in rows if row[4] is True)
    draft_row = next(row for row in rows if row[5] is True)
    assert json.loads(active_row[1]) == active
    assert draft_row[3] == 4
    stored_draft = json.loads(draft_row[1])
    for capability_key in VOICE_CAPABILITY_KEYS:
        if capability_key != CAPABILITY_KEY:
            assert stored_draft["capabilities"][capability_key] == draft["capabilities"][
                capability_key
            ]
    projected = stored_draft["capabilities"][CAPABILITY_KEY]
    assert projected["verification_status"] == "verified"
    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"
    assert projected["last_test_result"] == "passed"
    assert projected["evidence_report_id"] == EVIDENCE_REPORT_ID
    serialized = canonical_json([response.json(), stored_draft, evidence.evidence_payload])
    assert SECRET_SENTINEL not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "draft_mutation",
    ["revision_and_content", "same_revision_content", "replace_row"],
)
async def test_capability_rejects_evidence_when_frozen_draft_drifts_during_runner(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    draft_mutation: str,
):
    """Provider 结论只能追加到启动测试时冻结的同一份草稿。"""

    await _insert_voice_config()
    runner.block = True
    request_task = asyncio.create_task(
        client.post(
            "/api/admin/voice/config/test-capability",
            headers=_headers("super_admin"),
            json={"capability_key": CAPABILITY_KEY},
        )
    )
    try:
        await asyncio.wait_for(runner.started.wait(), timeout=1)
        async with session_factory() as mutation_db:
            draft = (
                await mutation_db.execute(
                    select(AdminConfig).where(
                        AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                        AdminConfig.is_draft == True,  # noqa: E712
                        AdminConfig.is_active == False,  # noqa: E712
                    )
                )
            ).scalars().one()
            if draft_mutation == "replace_row":
                replacement_id = draft.id + 100
                replacement = AdminConfig(
                    id=replacement_id,
                    config_key=draft.config_key,
                    config_value=draft.config_value,
                    version=draft.version,
                    draft_revision=draft.draft_revision,
                    is_active=draft.is_active,
                    is_draft=draft.is_draft,
                    updated_by="concurrent-replacement",
                )
                await mutation_db.delete(draft)
                await mutation_db.flush()
                mutation_db.add(replacement)
            else:
                changed = json.loads(draft.config_value)
                changed["global"]["test_user_ids"] = [202]
                draft.config_value = canonical_json(changed)
                draft.updated_by = "concurrent-editor"
                if draft_mutation == "revision_and_content":
                    draft.draft_revision += 1
            await mutation_db.commit()
        concurrent_projection = await _voice_rows_projection()
    finally:
        runner.release.set()

    response = await asyncio.wait_for(request_task, timeout=1)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "error"
    assert data["failure_category"] == "evidence_invalid"
    assert data["tested_draft_revision"] == 3
    assert data["evidence_run_id"] is None
    assert data["evidence_report_id"] is None
    assert await _voice_rows_projection() == concurrent_projection
    assert await _evidence_rows() == []
    logs = await _operation_logs()
    assert len(logs) == 1
    assert logs[0].action == "test_capability"
    audit = json.loads(logs[0].after_value)
    assert audit["status"] == "error"
    assert audit["failure_category"] == "evidence_invalid"
    assert audit["tested_draft_revision"] == 3
    assert SECRET_SENTINEL not in logs[0].after_value


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["status", "tested_at"])
async def test_capability_runner_conclusion_and_evidence_must_match_or_fail_closed(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    mismatch: str,
):
    """A runner envelope cannot contradict the immutable evidence it asks us to store."""

    await _insert_voice_config()
    before = await _voice_rows_projection()

    async def mismatched_result(*args, **kwargs):
        del args, kwargs
        runner.capability_calls += 1
        record = _capability_record()
        status = "passed"
        failure_category = "none"
        if mismatch == "status":
            status = "failed"
            failure_category = "protocol_error"
        else:
            mismatched_time = _REFERENCE_NOW + timedelta(seconds=1)
            record["tested_at"] = mismatched_time.isoformat().replace("+00:00", "Z")
            record["verified_at"] = record["tested_at"]
            record["expires_at"] = (mismatched_time + timedelta(days=30)).isoformat().replace(
                "+00:00", "Z"
            )
            record["report_sha256"] = _canonical_sha256(
                {key: value for key, value in record.items() if key != "report_sha256"}
            )
        return {
            "status": status,
            "latency_ms": 23,
            "failure_category": failure_category,
            "tested_at": TESTED_AT,
            "evidence_record": record,
        }

    runner.run_capability = mismatched_result
    response = await client.post(
        "/api/admin/voice/config/test-capability",
        headers=_headers("super_admin"),
        json={"capability_key": CAPABILITY_KEY},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "error"
    assert data["failure_category"] == "evidence_invalid"
    assert data["evidence_run_id"] is None
    assert data["evidence_report_id"] is None
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"capability_key": CAPABILITY_KEY, "extra": True},
        {"capability_key": "not-a-frozen-capability"},
    ],
)
async def test_capability_request_schema_rejects_missing_extra_or_unknown_key_before_runner(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    body: dict[str, Any],
):
    """捕获 capability body 非精确键集，或未知能力仍触发 Provider/证据副作用。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    response = await client.post(
        "/api/admin/voice/config/test-capability",
        headers=_headers("tech_ops"),
        json=body,
    )

    assert response.status_code == 422, response.text
    assert runner.connection_calls == runner.capability_calls == 0
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["super_admin", "tech_ops"])
@pytest.mark.parametrize(
    ("path", "body", "expected_evidence"),
    [
        ("/api/admin/voice/config/test-connection", {}, 0),
        (
            "/api/admin/voice/config/test-capability",
            {"capability_key": CAPABILITY_KEY},
            1,
        ),
    ],
)
async def test_both_test_apis_allow_exactly_the_two_test_roles(
    client: AsyncClient,
    role: str,
    path: str,
    body: dict[str, Any],
    expected_evidence: int,
):
    """捕获任一测试端点漏挂统一 test-role dependency，导致两个合法角色行为分裂。"""

    await _insert_voice_config()
    response = await client.post(path, headers=_headers(role), json=body)

    assert response.status_code == 200, response.text
    assert response.json()["code"] == 0
    assert len(await _evidence_rows()) == expected_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ai_trainer", "ops_admin", "observer"])
@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/admin/voice/config/test-connection", {}),
        (
            "/api/admin/voice/config/test-capability",
            {"capability_key": CAPABILITY_KEY},
        ),
    ],
)
async def test_denied_roles_stop_before_secret_runner_or_evidence(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    path: str,
    body: dict[str, Any],
):
    """捕获低权角色虽最终 403，却已读取 Secret、启动 Provider 或写入证据。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    secret_reads: list[str] = []
    original_getenv = os.getenv

    def guarded_getenv(key: str, default=None):
        if key == SECRET_REF:
            secret_reads.append(key)
            raise AssertionError("RBAC 必须先于 Secret 解析")
        return original_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)
    response = await client.post(path, headers=_headers(role), json=body)

    assert response.status_code == 403, response.text
    assert secret_reads == []
    assert runner.connection_calls == runner.capability_calls == 0
    assert await _evidence_rows() == []
    assert await _voice_rows_projection() == before


@pytest.mark.asyncio
async def test_real_observer_force_reaches_service_denial_and_writes_one_safe_audit(
    real_auth_client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    """捕获真实 observer 被全局 POST 总闸抢先拒绝，导致 force 失败审计缺失。"""

    await _insert_voice_config()
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows()
    headers = _real_auth_headers("observer")
    reason = f"observer 不得强制 {SECRET_SENTINEL}"
    credential_reads: list[str] = []
    original_getenv = os.getenv

    def guarded_getenv(key: str, default=None):
        if key == SECRET_REF:
            credential_reads.append(key)
            raise AssertionError("force 角色拒绝必须先于 Secret 解析")
        return original_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)
    response = await real_auth_client.post(
        f"/api/admin/voice/config/capabilities/{CAPABILITY_KEY}/force-test",
        headers=headers,
        json={
            "effective_scope": "test",
            "confirm_text": "CONFIRM",
            "reason": reason,
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["data"]["error_code"] == VOICE_CAPABILITY_FORCE_FORBIDDEN
    assert credential_reads == []
    assert runner.connection_calls == runner.capability_calls == 0
    assert runner.close_calls == 0
    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows() == before_evidence
    logs = await _operation_logs()
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "force_enable"
    assert log.admin_user_id == role_ids["observer"]
    after = json.loads(log.after_value)
    assert after["permission"] == "observer"
    assert after["result"] == "failed"
    assert after["failure_category"] == VOICE_CAPABILITY_FORCE_FORBIDDEN
    assert "force_source" not in after
    serialized_log = canonical_json(
        [log.target_description, log.before_value, log.after_value]
    )
    assert reason not in serialized_log
    assert SECRET_SENTINEL not in serialized_log


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/admin/voice/config/test-connection", {}),
        (
            "/api/admin/voice/config/test-capability",
            {"capability_key": CAPABILITY_KEY},
        ),
    ],
)
async def test_real_observer_test_apis_stay_behind_global_write_gate(
    real_auth_client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    body: dict[str, Any],
):
    """捕获 force 精确例外外溢到两个测试 POST，提前读取 Secret 或产生副作用。"""

    await _insert_voice_config()
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows()
    headers = _real_auth_headers("observer")
    credential_reads: list[str] = []
    original_getenv = os.getenv

    def guarded_getenv(key: str, default=None):
        if key == SECRET_REF:
            credential_reads.append(key)
            raise AssertionError("observer 测试 API 必须在 Secret 解析前拒绝")
        return original_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)
    response = await real_auth_client.post(path, headers=headers, json=body)

    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "观察者仅允许只读操作"}
    assert credential_reads == []
    assert runner.connection_calls == runner.capability_calls == 0
    assert runner.close_calls == 0
    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows() == before_evidence
    assert await _operation_logs() == []


@pytest.mark.asyncio
async def test_sixty_second_deadline_returns_normalized_timeout_and_cleans_runner(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    """捕获 deadline 非 60 秒、TimeoutError 变 500，或超时后短连接 runner 泄漏。"""

    await _insert_voice_config()
    if _runner_dependency() is None:
        pytest.fail("缺少可注入的 get_voice_test_runner 短生命周期端口")
    runner.block = True
    runner.block_close = True
    requested_deadlines: list[float | None] = []
    real_timeout = asyncio.timeout

    def accelerated_timeout(delay: float | None):
        requested_deadlines.append(delay)
        return real_timeout(0.01 if delay in {60, 5} else delay)

    monkeypatch.setattr(asyncio, "timeout", accelerated_timeout)
    response = await asyncio.wait_for(
        client.post(
            "/api/admin/voice/config/test-connection",
            headers=_headers("tech_ops"),
            json={},
        ),
        timeout=0.5,
    )

    assert 60 in requested_deadlines
    assert 5 in requested_deadlines
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) == {
        "status",
        "latency_ms",
        "failure_category",
        "test_version",
        "tested_draft_revision",
        "tested_at",
    }
    assert data["status"] == "error"
    assert data["latency_ms"] is None
    assert data["failure_category"] == "timeout"
    assert data["test_version"] == TEST_VERSION
    assert data["tested_draft_revision"] == 3
    datetime.fromisoformat(data["tested_at"].replace("Z", "+00:00"))
    assert runner.cancelled_calls == 1
    assert runner.close_calls == 1
    assert runner.close_cancelled_calls == 1
    assert await _evidence_rows() == []


@pytest.mark.asyncio
async def test_client_cancellation_propagates_and_still_cleans_runner(
    client: AsyncClient,
    runner: ControlledVoiceTestRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    """捕获客户端断开只取消 HTTP task，却遗留 Provider session 或半条证据。"""

    await _insert_voice_config()
    if _runner_dependency() is None:
        pytest.fail("缺少可注入的 get_voice_test_runner 短生命周期端口")
    runner.block = True
    runner.block_close = True
    requested_deadlines: list[float | None] = []
    real_timeout = asyncio.timeout

    def accelerated_cleanup_timeout(delay: float | None):
        requested_deadlines.append(delay)
        return real_timeout(0.01 if delay == 5 else delay)

    monkeypatch.setattr(asyncio, "timeout", accelerated_cleanup_timeout)
    request_task = asyncio.create_task(
        client.post(
            "/api/admin/voice/config/test-capability",
            headers=_headers("tech_ops"),
            json={"capability_key": CAPABILITY_KEY},
        )
    )
    await asyncio.wait_for(runner.started.wait(), timeout=1)
    request_task.cancel()

    await asyncio.sleep(0.05)
    completed_after_cleanup_deadline = request_task.done()
    if not request_task.done():
        runner.close_release.set()
    with pytest.raises(asyncio.CancelledError):
        await request_task
    assert completed_after_cleanup_deadline is True
    assert 5 in requested_deadlines
    assert runner.cancelled_calls == 1
    assert runner.close_calls == 1
    assert runner.close_cancelled_calls == 1
    assert await _evidence_rows() == []


@pytest.mark.asyncio
async def test_public_force_test_writes_draft_and_complete_immutable_log_anchor(
    client: AsyncClient,
):
    """捕获公开强制成功却无可重查 source/reason/operator/time/hash 锚，或扩展 capability schema。"""

    _, original_draft = await _insert_voice_config()
    reason = "M1 人工强制 test 验证"
    response = await client.post(
        f"/api/admin/voice/config/capabilities/{CAPABILITY_KEY}/force-test",
        headers=_headers("super_admin"),
        json={
            "effective_scope": "test",
            "confirm_text": "CONFIRM",
            "reason": reason,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["code"] == 0
    result = response.json()["data"]
    assert set(result) == {
        "config_key",
        "capability_key",
        "base_version",
        "draft_revision",
        "content_sha256",
    }
    assert result["config_key"] == VOICE_CALL_CONFIG_KEY
    assert result["capability_key"] == CAPABILITY_KEY
    assert result["draft_revision"] == 4

    rows = await _voice_rows_projection()
    stored_draft = json.loads(next(row for row in rows if row[5] is True)[1])
    forced = stored_draft["capabilities"][CAPABILITY_KEY]
    assert forced["enabled"] is True
    assert forced["forced_enabled"] is True
    assert forced["effective_scope"] == "test"
    assert set(forced) == set(original_draft["capabilities"][CAPABILITY_KEY])
    assert result["content_sha256"] == content_sha256(stored_draft)

    logs = await _operation_logs()
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "force_enable"
    assert log.admin_user_id == role_ids["super_admin"]
    after = json.loads(log.after_value)
    anchor = after["force_source"]
    assert set(anchor) == {
        "source",
        "capability_key",
        "draft_revision",
        "config_content_sha256",
        "operator_id",
        "forced_at",
        "reason_length",
        "reason_sha256",
    }
    assert anchor == {
        "source": "admin_force_test",
        "capability_key": CAPABILITY_KEY,
        "draft_revision": 4,
        "config_content_sha256": result["content_sha256"],
        "operator_id": role_ids["super_admin"],
        "forced_at": anchor["forced_at"],
        "reason_length": len(reason),
        "reason_sha256": "sha256:"
        + hashlib.sha256(reason.encode("utf-8")).hexdigest(),
    }
    forced_at = datetime.fromisoformat(anchor["forced_at"].replace("Z", "+00:00"))
    if forced_at.tzinfo is None:
        forced_at = forced_at.replace(tzinfo=timezone.utc)
    assert abs((forced_at - datetime.now(timezone.utc)).total_seconds()) < 10
    serialized_log = canonical_json(
        [log.target_description, log.before_value, log.after_value]
    )
    assert reason not in serialized_log
    assert SECRET_SENTINEL not in serialized_log


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"effective_scope": "test", "confirm_text": "CONFIRM"},
        {
            "effective_scope": "test",
            "confirm_text": "CONFIRM",
            "reason": "ok",
            "capability_key": CAPABILITY_KEY,
        },
        {"effective_scope": "test", "confirm_text": "CONFIRM", "reason": "   "},
        {"effective_scope": "test", "confirm_text": "CONFIRM", "reason": "x" * 501},
        {"effective_scope": "all", "confirm_text": "CONFIRM", "reason": "ok"},
    ],
)
async def test_force_test_request_model_is_strict_before_any_config_or_audit_write(
    client: AsyncClient,
    body: dict[str, Any],
):
    """捕获 force body 缺/多字段、空白/超长原因或 all scope 穿过 schema 边界。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    response = await client.post(
        f"/api/admin/voice/config/capabilities/{CAPABILITY_KEY}/force-test",
        headers=_headers("super_admin"),
        json=body,
    )

    assert response.status_code == 422, response.text
    assert await _voice_rows_projection() == before
    assert await _operation_logs() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["tech_ops", "ai_trainer", "ops_admin", "observer"])
async def test_force_test_denies_non_super_admin_without_business_write_and_audits(
    client: AsyncClient,
    role: str,
):
    """捕获入口 RBAC 抢先 403，导致 service 脱敏失败审计随异常回滚。"""

    await _insert_voice_config()
    before = await _voice_rows_projection()
    before_evidence = await _evidence_rows()
    reason = f"{role} 不得强制 {SECRET_SENTINEL}"
    response = await client.post(
        f"/api/admin/voice/config/capabilities/{CAPABILITY_KEY}/force-test",
        headers=_headers(role),
        json={
            "effective_scope": "test",
            "confirm_text": "CONFIRM",
            "reason": reason,
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["data"]["error_code"] == VOICE_CAPABILITY_FORCE_FORBIDDEN
    assert await _voice_rows_projection() == before
    assert await _evidence_rows() == before_evidence
    logs = await _operation_logs()
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "force_enable"
    assert log.admin_user_id == role_ids[role]
    after = json.loads(log.after_value)
    assert after["permission"] == role
    assert after["result"] == "failed"
    assert after["failure_category"] == VOICE_CAPABILITY_FORCE_FORBIDDEN
    assert "force_source" not in after
    serialized_log = canonical_json(
        [log.target_description, log.before_value, log.after_value]
    )
    assert reason not in serialized_log
    assert SECRET_SENTINEL not in serialized_log


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_status", "confirm_text", "test_user_ids", "expected_error"),
    [
        ("unverified", "confirm", [101], VOICE_CAPABILITY_FORCE_CONFIRM_INVALID),
        ("unverified", "CONFIRM", [], VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED),
        ("failed", "CONFIRM", [101], VOICE_CAPABILITY_FORCE_STATUS_INVALID),
        ("verified", "CONFIRM", [101], VOICE_CAPABILITY_FORCE_STATUS_INVALID),
    ],
)
async def test_force_test_business_negatives_never_create_success_source_anchor(
    client: AsyncClient,
    fixture_status: str,
    confirm_text: str,
    test_user_ids: list[int],
    expected_error: str,
):
    """捕获错误确认、空测试名单、failed/verified 状态仍被强制并生成可信锚。"""

    config = (
        _default_config(test_user_ids=test_user_ids)
        if fixture_status == "unverified"
        else _config_with_status(fixture_status)
    )
    config["global"]["test_user_ids"] = deepcopy(test_user_ids)
    await _insert_voice_config(active=config, draft=config)
    before = await _voice_rows_projection()
    response = await client.post(
        f"/api/admin/voice/config/capabilities/{CAPABILITY_KEY}/force-test",
        headers=_headers("super_admin"),
        json={
            "effective_scope": "test",
            "confirm_text": confirm_text,
            "reason": "负例不得形成可信来源锚",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["data"]["error_code"] == expected_error
    assert await _voice_rows_projection() == before
    for log in await _operation_logs():
        after = json.loads(log.after_value) if log.after_value else {}
        assert "force_source" not in after
