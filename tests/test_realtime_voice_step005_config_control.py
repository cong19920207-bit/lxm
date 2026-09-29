# -*- coding: utf-8 -*-
"""实时语音 P1 M1 STEP-005 配置控制面验收。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401  注册完整 ORM
from backend.constants.realtime_voice_config import (
    DEFAULT_MISSED_EXPLANATION_TEMPLATE,
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
    VOICE_CAPABILITY_KEYS,
    build_canonical_voice_seed_manifest,
    get_default_followup_schedule,
    get_default_voice_call_config,
    get_default_voice_call_script,
)
from backend.database import Base, get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceFollowupJob
from backend.routers.admin.safety_rules import router as safety_router
from backend.routers.admin.voice_config import router as voice_router
from backend.services.realtime_voice_config_service import (
    CRISIS_KEYWORDS_EMPTY,
    FOLLOWUP_PREVIEW_INPUT_INVALID,
    FOLLOWUP_WINDOW_OVERLAP,
    FOLLOWUP_WINDOW_RANGE_INVALID,
    FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER,
    VOICE_CONFIG_FORBIDDEN_FIELD,
    VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
    VOICE_CONFIG_BASE_VERSION_CONFLICT,
    VOICE_CONFIG_PERSONA_REF_INVALID,
    VOICE_CONFIG_REVISION_CONFLICT,
    VOICE_CONFIG_SECRET_FORBIDDEN,
    VoiceConfigError,
    canonical_json,
    content_sha256,
    followup_delay_within_limit,
    publish_crisis_keywords_atomically,
    realtime_voice_config_service,
    resolve_followup_preview,
    rollback_crisis_keywords_atomically,
    validate_followup_schedule,
    validate_voice_bundle,
)
from backend.utils.admin_auth import get_current_admin


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail_setex_once_for: str | None = None

    async def get(self, key: str):
        return self.values.get(key)

    async def ttl(self, key: str):
        return self.ttls.get(key, -2 if key not in self.values else -1)

    async def setex(self, key: str, ttl: int, value: str):
        if self.fail_setex_once_for == key:
            self.fail_setex_once_for = None
            raise RuntimeError("controlled redis failure")
        self.values[key] = value
        self.ttls[key] = ttl
        return True

    async def set(self, key: str, value: str):
        self.values[key] = value
        self.ttls[key] = -1
        return True

    async def delete(self, key: str):
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return 1


fake_redis = FakeRedis()
role_ids: dict[str, int] = {}


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
    if role not in role_ids:
        role = "observer"
    return SimpleNamespace(
        id=role_ids[role],
        username=f"step005-{role}",
        role=role,
    )


app = FastAPI()
app.include_router(voice_router, prefix="/api/admin/voice")
app.include_router(safety_router, prefix="/api/admin")
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_admin] = override_current_admin


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    import backend.services.admin_config_service as admin_service_module
    import backend.services.realtime_voice_config_service as voice_service_module
    import backend.routers.admin.safety_rules as safety_router_module

    fake_redis.values.clear()
    fake_redis.ttls.clear()
    fake_redis.fail_setex_once_for = None

    async def redis_provider():
        return fake_redis

    monkeypatch.setattr(admin_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(voice_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(safety_router_module, "get_redis", redis_provider)
    monkeypatch.setattr(admin_service_module, "async_session_maker", session_factory)
    monkeypatch.setenv("DOUBAO_S2S_ACCESS_KEY", "step005-secret-SENTINEL-value")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
            row = AdminUser(
                username=f"step005-{role}",
                password_hash="not-used",
                role=role,
                is_active=True,
                is_locked=False,
                token_version=0,
            )
            session.add(row)
            await session.flush()
            role_ids[role] = row.id
        session.add(
            AdminConfig(
                config_key="persona",
                config_value=canonical_json(
                    {
                        "background": "林小梦",
                        "personality": "温柔",
                        "emotion_preference": "共情",
                        "language_style": "自然",
                        "behavior_pattern": "倾听",
                    }
                ),
                version=1,
                is_draft=False,
                is_active=True,
                updated_by="step005-super_admin",
            )
        )
        await session.commit()
    yield
    role_ids.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://step005",
    ) as http_client:
        yield http_client


async def _admin(session: AsyncSession, role: str) -> AdminUser:
    return (
        await session.execute(
            select(AdminUser).where(AdminUser.role == role)
        )
    ).scalars().first()


async def _seed() -> dict:
    async with session_factory() as session:
        return await realtime_voice_config_service.initialize_defaults(
            session,
            admin_user=await _admin(session, "super_admin"),
        )


def _headers(role: str) -> dict[str, str]:
    return {"x-admin-role": role}


def _row_status(row: AdminConfig) -> str:
    if row.is_draft:
        return "draft"
    return "active" if row.is_active else "history"


async def _config_row_projection() -> list[tuple]:
    async with session_factory() as session:
        rows = (
            await session.execute(select(AdminConfig).order_by(AdminConfig.id.asc()))
        ).scalars().all()
    projection = []
    for row in rows:
        try:
            content = json.loads(row.config_value) if row.config_value is not None else None
        except json.JSONDecodeError:
            content = row.config_value
        projection.append(
            (
                row.id,
                row.config_key,
                _row_status(row),
                row.version,
                row.draft_revision,
                content_sha256(content) if content is not None else None,
                canonical_json(content),
                row.updated_by,
                row.updated_at.isoformat() if row.updated_at else None,
            )
        )
    return projection


async def _followup_job_projection() -> list[tuple]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(VoiceFollowupJob).order_by(VoiceFollowupJob.id.asc())
            )
        ).scalars().all()
    return [
        (
            row.id,
            row.call_id,
            row.user_id,
            row.candidate_due_at.isoformat(),
            row.due_at.isoformat(),
            row.latest_due_at.isoformat(),
            row.content,
            row.content_type,
            row.status,
            row.cancel_reason,
            row.agent_message_id,
            row.relationship_stage_snapshot,
            row.schedule_config_version,
            row.timezone_snapshot,
            canonical_json(row.allowed_window_snapshot),
            row.jitter_minutes,
            row.attempt_count,
            row.next_retry_at.isoformat() if row.next_retry_at else None,
            row.fail_reason,
            row.lease_owner,
            row.lease_expires_at.isoformat() if row.lease_expires_at else None,
            row.created_at.isoformat(),
            row.updated_at.isoformat(),
        )
        for row in rows
    ]


def _redis_projection(*keys: str) -> dict[str, tuple[str | None, int]]:
    return {
        key: (fake_redis.values.get(key), fake_redis.ttls.get(key, -2))
        for key in keys
    }


async def _audit_text() -> str:
    async with session_factory() as session:
        rows = (await session.execute(select(AdminOperationLog))).scalars().all()
    return json.dumps(
        [
            [row.target_description, row.before_value, row.after_value]
            for row in rows
        ],
        ensure_ascii=False,
    )


async def _save_changed_section(
    *,
    config_key: str,
    section: str,
    role: str,
    mutate,
) -> dict:
    async with session_factory() as session:
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == config_key,
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().first()
        payload = json.loads(active.config_value)
        changed = deepcopy(payload[section])
        mutate(changed)
        result = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=config_key,
            section=section,
            base_version=active.version,
            draft_revision=None,
            content=changed,
            admin_user=await _admin(session, role),
        )
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_canonical_seed_is_complete_idempotent_and_per_key():
    first = await _seed()
    assert first[VOICE_CALL_CONFIG_KEY]["status"] == "published"
    assert first[VOICE_CALL_SCRIPT_KEY]["status"] == "published"

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key.in_(
                        (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY)
                    ),
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().all()
        by_key = {row.config_key: row for row in rows}
        assert set(by_key) == {VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY}
        assert all(row.version == 1 for row in rows)

    config = json.loads(by_key[VOICE_CALL_CONFIG_KEY].config_value)
    script = json.loads(by_key[VOICE_CALL_SCRIPT_KEY].config_value)
    assert config["global"] == {
        "enabled": False,
        "maintenance_mode": False,
        "maintenance_message": "语音通话暂时不可用，请稍后再试",
        "rollout": {"mode": "allowlist", "user_ids": []},
        "soft_stop": False,
        "test_user_ids": [],
    }
    for capability_key in VOICE_CAPABILITY_KEYS:
        capability = config["capabilities"][capability_key]
        assert (
            capability["enabled"],
            capability["verification_status"],
            capability["effective_scope"],
        ) == (False, "unverified", "off")
    assert set(config["followup"]["schedule"]["stages"]) == {
        "stranger", "friend", "intimate", "soulmate"
    }
    assert all(
        config["followup"]["schedule"]["stages"][stage]["windows"]
        for stage in config["followup"]["schedule"]["stages"]
    )
    assert script["followup"]["missed_explanation_template"] == DEFAULT_MISSED_EXPLANATION_TEMPLATE
    assert script["reconnect_bridge"]["success_template"] == "刚刚好像断了一下。你刚才说到哪儿了？"
    assert script["context_pack"] == {
        "voice_instruction_template": "",
        "fallback_template_sections": [
            "persona", "relationship", "salutation", "current_time"
        ],
        "persona_max_chars": 5000,
        "dynamic_max_chars": 2000,
        "recent_dialog_max_chars": 800,
        "memory_max_items": 5,
        "memory_lookback_days": 30,
        "build_budget_ms": 3000,
        "ready_barrier_enabled": True,
    }
    assert script["call_answer"] == {
        "prompt_template": "",
        "failure_fallback": "answer",
        "min_ring_seconds": 4,
        "max_wait_seconds": 12,
        "fallback_delay_min_seconds": 4,
        "fallback_delay_max_seconds": 8,
    }
    assert {
        key: script["recall"][key]
        for key in (
            "max_query_chars",
            "top_k",
            "score_threshold",
            "timeout_ms",
            "embedding_timeout_ms",
            "vector_timeout_ms",
        )
    } == {
        "max_query_chars": 200,
        "top_k": 3,
        "score_threshold": 0.7,
        "timeout_ms": 1000,
        "embedding_timeout_ms": 800,
        "vector_timeout_ms": 800,
    }
    assert script["memory"]["max_items_per_turn"] == 5
    assert script["silence_and_exit"] == {
        "exit_intent_template": "好，那我们先聊到这",
        "silence_timeout_template": "好像暂时听不到你，我们下次再聊",
        "silence_confirm_seconds": 6,
        "silence_hangup_seconds": 12,
        "user_resume_cancels_exit": True,
    }
    assert script["end_reason"] == {
        "user_hangup": "就先聊到这",
        "user_cancel": {"show_end_page": False, "action": "return_to_chat"},
        "exit_intent": "好，那我们先聊到这",
        "silence_timeout": "好像暂时听不到你，我们下次再聊",
        "quota_exhausted": "今天能聊的时间用完啦，我们下次再聊",
        "hard_limit": "这次聊得有点久，我们先休息一下",
        "reconnect_timeout": "网络没有恢复，我们下次再接着聊",
        "provider_error": {
            "before_connected": "暂时无法接通",
            "after_connected": "通话暂时中断，请稍后再试",
        },
        "system_error": {
            "before_connected": "暂时无法接通",
            "after_connected": "通话暂时中断，请稍后再试",
        },
    }
    assert script["crisis"] == {
        "region": "CN-mainland",
        "in_call_banner": "如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。",
        "post_call_resource_card": "如果你可能马上伤害自己，请立即拨打 110/120，并请一位可信任的人来到你身边；也可以拨打 12356 心理援助热线。",
    }

    # 两类后续 runtime fallback 必须复用和首次发布相同的唯一 manifest 源。
    persona_ref = config["persona_ref"]
    assert get_default_voice_call_config(persona_ref) == config
    assert get_default_voice_call_script() == script

    # 待技术定值的 S2S/并发安全占位只存在于显式关闭的 seed 中。
    assert config["global"]["enabled"] is False
    assert config["s2s"]["connect_timeout_ms"] == 10000
    assert config["s2s"]["start_session_timeout_ms"] == 10000
    assert config["concurrency"]["global_limit"] == 1

    for key, payload in ((VOICE_CALL_CONFIG_KEY, config), (VOICE_CALL_SCRIPT_KEY, script)):
        assert json.loads(fake_redis.values[f"active_config:{key}"]) == payload
        assert fake_redis.ttls[f"publish_monitor:{key}"] == 300

    second = await _seed()
    assert second[VOICE_CALL_CONFIG_KEY] == {"status": "skipped", "version": 1}
    assert second[VOICE_CALL_SCRIPT_KEY] == {"status": "skipped", "version": 1}

    async with session_factory() as session:
        await session.execute(
            delete(AdminConfig).where(
                AdminConfig.config_key == VOICE_CALL_SCRIPT_KEY
            )
        )
        await session.commit()
    third = await _seed()
    assert third[VOICE_CALL_CONFIG_KEY] == {"status": "skipped", "version": 1}
    assert third[VOICE_CALL_SCRIPT_KEY]["status"] == "published"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "existing_key",
    [VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY],
)
async def test_initialization_skips_each_existing_key_without_overwrite(existing_key):
    # AC77 can only bootstrap a durable offline envelope from an existing
    # voice config whose persona anchor still matches the published row.
    async with session_factory() as session:
        persona = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == "persona",
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().one()
    persona_ref = {
        "config_key": "persona",
        "version": persona.version,
        "content_sha256": "sha256:"
        + hashlib.sha256(persona.config_value.encode("utf-8")).hexdigest(),
    }
    manifest = build_canonical_voice_seed_manifest(persona_ref)
    existing_payload = manifest[existing_key]
    if existing_key == VOICE_CALL_CONFIG_KEY:
        existing_payload["global"]["maintenance_message"] = "既有运营配置不得覆盖"
    else:
        existing_payload["followup"]["missed_explanation_template"] = "既有运营脚本不得覆盖"
    async with session_factory() as session:
        row = AdminConfig(
            config_key=existing_key,
            config_value=canonical_json(existing_payload),
            version=7,
            is_draft=False,
            is_active=True,
            updated_by="existing-operator",
        )
        session.add(row)
        await session.commit()
        existing_id = row.id
    existing_cache_key = f"active_config:{existing_key}"
    await fake_redis.setex(existing_cache_key, 321, canonical_json(existing_payload))

    result = await _seed()
    missing_key = (
        VOICE_CALL_SCRIPT_KEY
        if existing_key == VOICE_CALL_CONFIG_KEY
        else VOICE_CALL_CONFIG_KEY
    )
    assert result[existing_key] == {"status": "skipped", "version": 7}
    assert result[missing_key]["status"] == "published"
    assert _redis_projection(existing_cache_key)[existing_cache_key] == (
        canonical_json(existing_payload),
        321,
    )
    async with session_factory() as session:
        existing_rows = (
            await session.execute(
                select(AdminConfig).where(AdminConfig.config_key == existing_key)
            )
        ).scalars().all()
        missing_rows = (
            await session.execute(
                select(AdminConfig).where(AdminConfig.config_key == missing_key)
            )
        ).scalars().all()
    assert [(row.id, row.version, row.config_value) for row in existing_rows] == [
        (existing_id, 7, canonical_json(existing_payload))
    ]
    assert [(row.version, row.is_active) for row in missing_rows] == [(1, True)]


@pytest.mark.asyncio
async def test_initialization_requires_active_persona_not_only_history():
    async with session_factory() as session:
        persona = await realtime_voice_config_service._active(session, "persona")
        persona.is_active = False
        await session.commit()
    before = await _config_row_projection()
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await realtime_voice_config_service.initialize_defaults(
                session,
                admin_user=await _admin(session, "super_admin"),
            )
        assert exc_info.value.code == "VOICE_CONFIG_PERSONA_REQUIRED"
        await session.rollback()
    assert await _config_row_projection() == before
    assert f"active_config:{VOICE_CALL_CONFIG_KEY}" not in fake_redis.values
    assert f"active_config:{VOICE_CALL_SCRIPT_KEY}" not in fake_redis.values


@pytest.mark.asyncio
async def test_initialization_persona_reference_uses_active_history_boundary_version_and_hash():
    active_value = canonical_json({"background": "第20版人格", "personality": "稳定"})
    async with session_factory() as session:
        active = await realtime_voice_config_service._active(session, "persona")
        active.version = 20
        active.config_value = active_value
        for version in range(1, 20):
            session.add(
                AdminConfig(
                    config_key="persona",
                    config_value=canonical_json({"background": f"历史人格{version}"}),
                    version=version,
                    is_draft=False,
                    is_active=False,
                    updated_by="history-fixture",
                )
            )
        await session.commit()
    await _seed()
    async with session_factory() as session:
        config = json.loads(
            (await realtime_voice_config_service._active(session, VOICE_CALL_CONFIG_KEY)).config_value
        )
        persona_count = len(
            (
                await session.execute(
                    select(AdminConfig).where(AdminConfig.config_key == "persona")
                )
            ).scalars().all()
        )
    assert persona_count == 20
    assert config["persona_ref"] == {
        "config_key": "persona",
        "version": 20,
        "content_sha256": "sha256:"
        + hashlib.sha256(active_value.encode("utf-8")).hexdigest(),
    }


@pytest.mark.asyncio
async def test_concurrent_initialization_is_idempotent_with_one_v1_per_key():
    async def initialize_once():
        async with session_factory() as session:
            return await realtime_voice_config_service.initialize_defaults(
                session,
                admin_user=await _admin(session, "super_admin"),
            )

    first, second = await asyncio.gather(initialize_once(), initialize_once())
    for key in (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY):
        assert {first[key]["status"], second[key]["status"]} == {"published", "skipped"}
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key.in_((VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY)),
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().all()
    assert sorted((row.config_key, row.version, row.is_active) for row in rows) == [
        (VOICE_CALL_CONFIG_KEY, 1, True),
        (VOICE_CALL_SCRIPT_KEY, 1, True),
    ]


@pytest.mark.asyncio
async def test_voice_publish_history_retains_latest_twenty_versions_at_boundary():
    await _seed()
    async with session_factory() as session:
        active = await realtime_voice_config_service._active(
            session, VOICE_CALL_SCRIPT_KEY
        )
        base_payload = json.loads(active.config_value)
        active.version = 20
        for version in range(1, 20):
            historical = deepcopy(base_payload)
            historical["followup"]["missed_explanation_template"] = f"历史版本 {version}"
            session.add(
                AdminConfig(
                    config_key=VOICE_CALL_SCRIPT_KEY,
                    config_value=canonical_json(historical),
                    version=version,
                    is_draft=False,
                    is_active=False,
                    updated_by="history-boundary-fixture",
                )
            )
        await session.commit()
    await _save_changed_section(
        config_key=VOICE_CALL_SCRIPT_KEY,
        section="followup",
        role="ai_trainer",
        mutate=lambda value: value.update({"missed_explanation_template": "第21版"}),
    )
    async with session_factory() as session:
        result = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            confirm_text="CONFIRM",
            change_note="验证20版本历史边界",
            admin_user=await _admin(session, "ai_trainer"),
        )
    assert result["version"] == 21
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig)
                .where(
                    AdminConfig.config_key == VOICE_CALL_SCRIPT_KEY,
                    AdminConfig.is_draft == False,  # noqa: E712
                )
                .order_by(AdminConfig.version.asc())
            )
        ).scalars().all()
    assert len(rows) == 20
    assert [row.version for row in rows] == list(range(2, 22))
    assert sum(row.is_active for row in rows) == 1
    assert rows[-1].is_active is True


def test_schema_rejects_percentage_experiments_manual_verified_and_bad_ttl():
    manifest = build_canonical_voice_seed_manifest(
        {
            "config_key": "persona",
            "version": 3,
            "content_sha256": "sha256:" + "a" * 64,
        }
    )
    config = manifest[VOICE_CALL_CONFIG_KEY]
    assert validate_voice_bundle(VOICE_CALL_CONFIG_KEY, config) == []

    invalid = deepcopy(config)
    invalid["global"]["rollout"]["percentage"] = 50
    invalid["global"]["rollout"]["mode"] = "percentage"
    invalid["global"]["capability_gray"] = {"1": True}
    invalid["preamble_memory_doc_ids"] = ["fixed-doc"]
    invalid["mock_s2s"] = True
    capability = invalid["capabilities"][VOICE_CAPABILITY_KEYS[0]]
    capability["verification_status"] = "verified"
    capability["enabled"] = True
    capability["effective_scope"] = "all"
    capability["evidence_ttl_days"] = 91

    issues = validate_voice_bundle(VOICE_CALL_CONFIG_KEY, invalid)
    codes = {issue["code"] for issue in issues}
    assert VOICE_CONFIG_FORBIDDEN_FIELD in codes
    assert VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN in codes
    assert any(issue["field"].endswith("evidence_ttl_days") for issue in issues)


@pytest.mark.parametrize(
    ("mutate", "expected_field"),
    [
        (
            lambda script: script["context_pack"].update({"persona_max_chars": 0}),
            "context_pack.persona_max_chars",
        ),
        (
            lambda script: script["context_pack"].update(
                {"dynamic_max_chars": 500, "recent_dialog_max_chars": 800}
            ),
            "context_pack.recent_dialog_max_chars",
        ),
        (
            lambda script: script["call_answer"].update(
                {"min_ring_seconds": 12, "max_wait_seconds": 12}
            ),
            "call_answer.min_ring_seconds",
        ),
        (
            lambda script: script["call_answer"].update(
                {"fallback_delay_min_seconds": 9, "fallback_delay_max_seconds": 8}
            ),
            "call_answer.fallback_delay_min_seconds",
        ),
        (
            lambda script: script["recall"].update({"score_threshold": 1.01}),
            "recall.score_threshold",
        ),
        (
            lambda script: script["recall"].update({"timeout_ms": 0}),
            "recall.timeout_ms",
        ),
        (
            lambda script: script["memory"].update({"max_items_per_turn": 0}),
            "memory.max_items_per_turn",
        ),
        (
            lambda script: script["silence_and_exit"].update(
                {"silence_confirm_seconds": 12, "silence_hangup_seconds": 12}
            ),
            "silence_and_exit.silence_confirm_seconds",
        ),
    ],
)
def test_frozen_seed_sections_have_range_and_cross_field_schema(mutate, expected_field):
    script = get_default_voice_call_script()
    mutate(script)
    issues = validate_voice_bundle(VOICE_CALL_SCRIPT_KEY, script)
    assert any(issue["field"] == expected_field for issue in issues), issues


def test_followup_window_validation_and_preview_boundaries():
    schedule = get_default_followup_schedule()
    assert validate_followup_schedule(schedule) == []

    adjacent = deepcopy(schedule)
    adjacent["stages"]["friend"]["windows"] = [
        {"start": "09:00", "end": "10:00"},
        {"start": "10:00", "end": "11:00"},
    ]
    assert validate_followup_schedule(adjacent) == []

    overlap = deepcopy(adjacent)
    overlap["stages"]["friend"]["windows"][1]["start"] = "09:59"
    assert FOLLOWUP_WINDOW_OVERLAP in {
        item["code"] for item in validate_followup_schedule(overlap)
    }

    too_short = deepcopy(schedule)
    too_short["stages"]["friend"]["windows"] = [
        {"start": "09:00", "end": "09:20"}
    ]
    assert FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER in {
        item["code"] for item in validate_followup_schedule(too_short)
    }

    invalid_range = deepcopy(schedule)
    invalid_range["stages"]["friend"]["windows"] = []
    assert FOLLOWUP_WINDOW_RANGE_INVALID in {
        item["code"] for item in validate_followup_schedule(invalid_range)
    }

    in_window = resolve_followup_preview(
        schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T09:30:00+08:00",
            "jitter_minutes": 20,
        },
    )
    assert in_window["resolution"] == "in_window"
    assert in_window["jitter_applied_minutes"] == 0
    assert in_window["delay_seconds"] == 0
    assert in_window["resolved_window"]["start_at"] == "2026-08-30T09:30:00+08:00"

    left_boundary = resolve_followup_preview(
        schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T09:30:00+08:00",
            "jitter_minutes": 20,
        },
    )
    assert left_boundary["resolution"] == "in_window"
    assert left_boundary["resolved_due_at"] == "2026-08-30T09:30:00+08:00"

    after_last = resolve_followup_preview(
        schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T23:30:00+08:00",
            "jitter_minutes": 20,
        },
    )
    assert after_last["resolution"] == "next_window"
    assert after_last["resolved_due_at"] == "2026-08-31T09:50:00+08:00"

    right_boundary = resolve_followup_preview(
        schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T22:00:00+08:00",
            "jitter_minutes": 0,
        },
    )
    assert right_boundary["resolution"] == "next_window"
    assert right_boundary["resolved_due_at"] == "2026-08-31T09:30:00+08:00"

    adjacent_preview = resolve_followup_preview(
        adjacent,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": 20,
        },
    )
    assert adjacent_preview["resolution"] == "in_window"
    assert adjacent_preview["resolved_window"]["start_at"] == "2026-08-30T10:00:00+08:00"

    candidate = datetime(2026, 8, 30, 10, tzinfo=timezone.utc)
    assert followup_delay_within_limit(candidate, candidate + timedelta(hours=24), 24)
    assert not followup_delay_within_limit(
        candidate,
        candidate + timedelta(hours=24, seconds=1),
        24,
    )

    # 对真实 resolver 覆盖 <=24h 分支。该构造专门隔离最大延迟边界；生产调用会
    # 先执行窗口时长 > jitter 的 schema 校验。
    boundary_schedule = deepcopy(schedule)
    boundary_schedule["stages"]["friend"]["windows"] = [
        {"start": "10:00", "end": "10:01"}
    ]
    exactly_24h = resolve_followup_preview(
        boundary_schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:01:00+08:00",
            "jitter_minutes": 1,
        },
    )
    assert exactly_24h["resolution"] == "next_window"
    assert exactly_24h["delay_seconds"] == 24 * 60 * 60
    over_24h = resolve_followup_preview(
        boundary_schedule,
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:01:59+08:00",
            "jitter_minutes": 2,
        },
    )
    assert over_24h["resolution"] == "cancelled"
    assert over_24h["delay_seconds"] == 24 * 60 * 60 + 1
    assert over_24h["cancel_reason"] == "max_delay_exceeded"

    with pytest.raises(VoiceConfigError) as exc_info:
        resolve_followup_preview(
            schedule,
            {"stage": "unknown", "candidate_at": "bad", "jitter_minutes": "20"},
        )
    assert exc_info.value.code == FOLLOWUP_PREVIEW_INPUT_INVALID


@pytest.mark.parametrize(
    "preview",
    [
        None,
        [],
        {},
        {"stage": "friend", "candidate_at": "2026-08-30T10:00:00+08:00"},
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": 0,
            "extra": True,
        },
        {
            "stage": "unknown",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": 0,
        },
        {"stage": "friend", "candidate_at": "bad", "jitter_minutes": 0},
        {"stage": "friend", "candidate_at": "2026-08-30T10:00:00", "jitter_minutes": 0},
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": True,
        },
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": "0",
        },
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": -1,
        },
        {
            "stage": "friend",
            "candidate_at": "2026-08-30T10:00:00+08:00",
            "jitter_minutes": 21,
        },
    ],
)
def test_followup_preview_invalid_inputs_use_one_error_code(preview):
    with pytest.raises(VoiceConfigError) as exc_info:
        resolve_followup_preview(get_default_followup_schedule(), preview)
    assert exc_info.value.code == FOLLOWUP_PREVIEW_INPUT_INVALID
    assert {item["code"] for item in exc_info.value.errors} == {
        FOLLOWUP_PREVIEW_INPUT_INVALID
    }


@pytest.mark.asyncio
async def test_validate_preview_api_preserves_config_redis_and_full_job_projection(
    client: AsyncClient,
):
    await _seed()
    now = datetime(2026, 8, 30, 8, 0, 0)
    async with session_factory() as session:
        session.add(
            VoiceFollowupJob(
                call_id="step005-preview-stable-call",
                user_id=999001,
                candidate_due_at=now,
                due_at=now + timedelta(hours=1),
                latest_due_at=now + timedelta(hours=24),
                content="稳定投影内容",
                content_type="topic_continuation",
                status="pending",
                cancel_reason=None,
                agent_message_id=None,
                relationship_stage_snapshot="friend",
                schedule_config_version="1",
                timezone_snapshot="Asia/Shanghai",
                allowed_window_snapshot={"start": "09:30", "end": "22:00"},
                jitter_minutes=7,
                attempt_count=2,
                next_retry_at=now + timedelta(minutes=5),
                fail_reason="previous_transient",
                lease_owner="worker-1",
                lease_expires_at=now + timedelta(minutes=1),
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    cache_key = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    before = (
        await _config_row_projection(),
        _redis_projection(cache_key),
        await _followup_job_projection(),
    )
    response = await client.post(
        "/api/admin/voice/config/config/validate",
        headers=_headers("tech_ops"),
        json={
            "followup_preview": {
                "stage": "friend",
                "candidate_at": "2026-08-30T23:30:00+08:00",
                "jitter_minutes": 20,
            }
        },
    )
    assert response.status_code == 200, response.text
    preview = response.json()["data"]["followup_preview"]
    assert preview == {
        "stage": "friend",
        "candidate_at": "2026-08-30T23:30:00+08:00",
        "resolution": "next_window",
        "in_window": False,
        "resolved_window": {
            "start_at": "2026-08-31T09:30:00+08:00",
            "end_at": "2026-08-31T22:00:00+08:00",
        },
        "jitter_applied_minutes": 20,
        "resolved_due_at": "2026-08-31T09:50:00+08:00",
        "delay_seconds": 37200,
        "cancel_reason": None,
    }
    after = (
        await _config_row_projection(),
        _redis_projection(cache_key),
        await _followup_job_projection(),
    )
    assert after == before

    # 嵌套形状也统一由服务返回 FOLLOWUP_PREVIEW_INPUT_INVALID，不泄漏为框架 422。
    for invalid in ({}, {"stage": "friend"}, {"stage": "friend", "candidate_at": "bad", "jitter_minutes": 0, "extra": 1}):
        invalid_response = await client.post(
            "/api/admin/voice/config/config/validate",
            headers=_headers("tech_ops"),
            json={"followup_preview": invalid},
        )
        assert invalid_response.status_code == 200, invalid_response.text
        data = invalid_response.json()["data"]
        assert data["valid"] is False
        assert {item["code"] for item in data["errors"]} == {
            FOLLOWUP_PREVIEW_INPUT_INVALID
        }

    explicit_null = await client.post(
        "/api/admin/voice/config/config/validate",
        headers=_headers("tech_ops"),
        json={"followup_preview": None},
    )
    assert explicit_null.status_code == 200
    assert explicit_null.json()["data"]["valid"] is False
    assert {
        item["code"] for item in explicit_null.json()["data"]["errors"]
    } == {FOLLOWUP_PREVIEW_INPUT_INVALID}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_code",
    [
        FOLLOWUP_WINDOW_RANGE_INVALID,
        FOLLOWUP_WINDOW_OVERLAP,
        FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER,
        FOLLOWUP_PREVIEW_INPUT_INVALID,
    ],
)
async def test_validate_api_maps_all_followup_voice_errors_instead_of_500(
    client: AsyncClient,
    monkeypatch,
    error_code: str,
):
    async def raise_followup_error(*args, **kwargs):
        raise VoiceConfigError(
            error_code,
            "受控 follow-up 校验错误",
            errors=[{"code": error_code, "field": "followup.schedule", "message": "invalid"}],
        )

    monkeypatch.setattr(
        realtime_voice_config_service,
        "validate_current",
        raise_followup_error,
    )
    response = await client.post(
        "/api/admin/voice/config/config/validate",
        headers=_headers("tech_ops"),
        json={},
    )
    assert response.status_code == 400, response.text
    data = response.json()["data"]
    assert data["error_code"] == error_code
    assert data["errors"][0]["code"] == error_code


@pytest.mark.asyncio
async def test_optimistic_draft_publish_hash_monitor_and_audit_secret_boundary():
    await _seed()
    async with session_factory() as session:
        admin = await _admin(session, "tech_ops")
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()
        active_config = json.loads(active.config_value)
        changed_global = deepcopy(active_config["global"])
        changed_global["soft_stop"] = True
        saved = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="global",
            base_version=1,
            draft_revision=None,
            content=changed_global,
            admin_user=admin,
        )
        await session.commit()
        assert saved["draft_revision"] == 1
        assert json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"])["global"]["soft_stop"] is False

    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as conflict:
            await realtime_voice_config_service.save_draft_section(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                section="global",
                base_version=1,
                draft_revision=None,
                content=changed_global,
                admin_user=await _admin(session, "tech_ops"),
            )
        assert conflict.value.code == VOICE_CONFIG_REVISION_CONFLICT

    async with session_factory() as session:
        result = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="开启软停",
            admin_user=await _admin(session, "tech_ops"),
        )
        assert result["version"] == 2
        assert result["content_sha256"].startswith("sha256:")

    assert fake_redis.ttls[f"publish_monitor:{VOICE_CALL_CONFIG_KEY}"] == 300
    stored = json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"])
    assert stored["global"]["soft_stop"] is True
    assert content_sha256(stored) == result["content_sha256"]

    async with session_factory() as session:
        logs = (await session.execute(select(AdminOperationLog))).scalars().all()
        serialized_logs = json.dumps(
            [
                [row.target_description, row.before_value, row.after_value]
                for row in logs
            ],
            ensure_ascii=False,
        )
    assert "step005-secret-SENTINEL-value" not in serialized_logs
    assert "DOUBAO_S2S_ACCESS_KEY" not in serialized_logs


@pytest.mark.asyncio
async def test_both_optimistic_conflicts_and_discard_section_then_all():
    await _seed()
    async with session_factory() as session:
        admin = await _admin(session, "tech_ops")
        active = await realtime_voice_config_service._active(
            session, VOICE_CALL_CONFIG_KEY
        )
        payload = json.loads(active.config_value)
        changed_global = deepcopy(payload["global"])
        changed_global["soft_stop"] = True
        first = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="global",
            base_version=1,
            draft_revision=None,
            content=changed_global,
            admin_user=admin,
        )
        await session.commit()
    assert first["draft_revision"] == 1

    before_conflicts = await _config_row_projection()
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as base_conflict:
            await realtime_voice_config_service.save_draft_section(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                section="global",
                base_version=0,
                draft_revision=1,
                content=changed_global,
                admin_user=await _admin(session, "tech_ops"),
            )
        assert base_conflict.value.code == VOICE_CONFIG_BASE_VERSION_CONFLICT
        await session.rollback()
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as revision_conflict:
            await realtime_voice_config_service.save_draft_section(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                section="global",
                base_version=1,
                draft_revision=None,
                content=changed_global,
                admin_user=await _admin(session, "tech_ops"),
            )
        assert revision_conflict.value.code == VOICE_CONFIG_REVISION_CONFLICT
        await session.rollback()
    assert await _config_row_projection() == before_conflicts

    async with session_factory() as session:
        active = await realtime_voice_config_service._active(
            session, VOICE_CALL_CONFIG_KEY
        )
        changed_quota = deepcopy(json.loads(active.config_value)["quota"])
        changed_quota["daily_free_seconds"] = 600
        second = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="quota",
            base_version=1,
            draft_revision=1,
            content=changed_quota,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()
    assert second["draft_revision"] == 2
    assert set(second["changed_sections"]) == {"global", "quota"}

    async with session_factory() as session:
        discarded = await realtime_voice_config_service.discard_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="global",
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()
    assert discarded == {"draft_revision": 3, "changed_sections": ["quota"]}

    async with session_factory() as session:
        draft = await realtime_voice_config_service._draft(
            session, VOICE_CALL_CONFIG_KEY
        )
        draft_config = json.loads(draft.config_value)
        assert draft_config["global"]["soft_stop"] is False
        assert draft_config["quota"]["daily_free_seconds"] == 600
        all_discarded = await realtime_voice_config_service.discard_draft(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()
    assert all_discarded == {"discarded": True}
    async with session_factory() as session:
        assert await realtime_voice_config_service._draft(
            session, VOICE_CALL_CONFIG_KEY
        ) is None
        active = await realtime_voice_config_service._active(
            session, VOICE_CALL_CONFIG_KEY
        )
        assert json.loads(active.config_value)["quota"]["daily_free_seconds"] == 300


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_key", "section", "role", "mutate"),
    [
        (
            VOICE_CALL_CONFIG_KEY,
            "global",
            "tech_ops",
            lambda value: value.update({"soft_stop": True}),
        ),
        (
            VOICE_CALL_SCRIPT_KEY,
            "followup",
            "ai_trainer",
            lambda value: value.update(
                {"missed_explanation_template": "已发布的测试未接文案"}
            ),
        ),
    ],
)
async def test_each_voice_key_publish_history_detail_and_rollback_new_version_hash(
    config_key, section, role, mutate
):
    await _seed()
    async with session_factory() as session:
        v1 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=config_key,
            version=1,
            role=role,
        )
    await _save_changed_section(
        config_key=config_key,
        section=section,
        role=role,
        mutate=mutate,
    )

    async with session_factory() as session:
        published = await realtime_voice_config_service.publish(
            session,
            config_key=config_key,
            confirm_text="CONFIRM",
            change_note="STEP-005 双 key 发布验收",
            admin_user=await _admin(session, role),
        )
    assert published["version"] == 2
    assert published["content_sha256"] != v1["content_sha256"]

    async with session_factory() as session:
        history = await realtime_voice_config_service.get_history(
            session,
            config_key=config_key,
            page=1,
            page_size=20,
        )
        v2 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=config_key,
            version=2,
            role=role,
        )
        stored_v2 = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == config_key,
                    AdminConfig.version == 2,
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().one()
    assert history["total"] == 2
    assert [item["version"] for item in history["list"]] == [2, 1]
    assert v2["content_sha256"] == published["content_sha256"]
    if config_key == VOICE_CALL_CONFIG_KEY:
        assert "credential_revision_ref" not in v2["config"]["s2s"]
    assert content_sha256(json.loads(stored_v2.config_value)) == v2["content_sha256"]

    async with session_factory() as session:
        rollback = await realtime_voice_config_service.rollback(
            session,
            config_key=config_key,
            version=1,
            confirm_text="CONFIRM",
            change_note="回滚到规范初始值",
            admin_user=await _admin(session, role),
        )
    assert rollback["version"] == 3
    assert rollback["rolled_back_from_version"] == 1
    assert rollback["content_sha256"] == v1["content_sha256"]
    assert fake_redis.ttls[f"publish_monitor:{config_key}"] == 300
    assert content_sha256(json.loads(fake_redis.values[f"active_config:{config_key}"])) == v1[
        "content_sha256"
    ]

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig)
                .where(
                    AdminConfig.config_key == config_key,
                    AdminConfig.is_draft == False,  # noqa: E712
                )
                .order_by(AdminConfig.version.asc())
            )
        ).scalars().all()
    assert [row.version for row in rows] == [1, 2, 3]
    assert sum(row.is_active for row in rows) == 1
    assert rows[-1].is_active is True
    assert content_sha256(json.loads(rows[-1].config_value)) == v1["content_sha256"]


@pytest.mark.asyncio
async def test_publish_and_rollback_confirm_variants_and_blank_note_are_zero_side_effect(
    client: AsyncClient,
):
    await _seed()
    await _save_changed_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section="global",
        role="tech_ops",
        mutate=lambda value: value.update({"soft_stop": True}),
    )
    cache_key = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    monitor_key = f"publish_monitor:{VOICE_CALL_CONFIG_KEY}"
    before_publish = (
        await _config_row_projection(),
        _redis_projection(cache_key, monitor_key),
    )
    for confirm_text in ("", "confirm", "CONFIRm", " CONFIRM", "CONFIRM "):
        response = await client.post(
            "/api/admin/voice/config/config/publish",
            headers=_headers("tech_ops"),
            json={"confirm_text": confirm_text, "change_note": "不应发布"},
        )
        assert response.status_code == 400, (confirm_text, response.text)
        assert response.json()["data"]["error_code"] == "VOICE_CONFIG_CONFIRM_TEXT_INVALID"
    blank_note = await client.post(
        "/api/admin/voice/config/config/publish",
        headers=_headers("tech_ops"),
        json={"confirm_text": "CONFIRM", "change_note": "   "},
    )
    assert blank_note.status_code == 422
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError):
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="   ",
                admin_user=await _admin(session, "tech_ops"),
            )
        await session.rollback()
    assert (
        await _config_row_projection(),
        _redis_projection(cache_key, monitor_key),
    ) == before_publish
    audit_text = await _audit_text()
    async with session_factory() as session:
        failure_logs = (
            await session.execute(
                select(AdminOperationLog).where(AdminOperationLog.action == "publish")
            )
        ).scalars().all()
    failure_payloads = [
        json.loads(row.after_value)
        for row in failure_logs
        if row.after_value and json.loads(row.after_value).get("result") == "failed"
    ]
    assert len(failure_payloads) >= 5
    assert "VOICE_CONFIG_CONFIRM_TEXT_INVALID" in audit_text
    assert "不应发布" not in audit_text

    # 建立 V2 后，对 rollback 重复同一严格确认与空白说明门禁。
    async with session_factory() as session:
        published = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="建立回滚前版本",
            admin_user=await _admin(session, "tech_ops"),
        )
    assert published["version"] == 2
    before_rollback = (
        await _config_row_projection(),
        _redis_projection(cache_key, monitor_key),
    )
    for confirm_text in ("", "confirm", " CONFIRM", "CONFIRM "):
        response = await client.post(
            "/api/admin/voice/config/config/rollback",
            headers=_headers("tech_ops"),
            json={"version": 1, "confirm_text": confirm_text, "change_note": "不应回滚"},
        )
        assert response.status_code == 400, (confirm_text, response.text)
    rollback_blank_note = await client.post(
        "/api/admin/voice/config/config/rollback",
        headers=_headers("tech_ops"),
        json={"version": 1, "confirm_text": "CONFIRM", "change_note": "\t  "},
    )
    assert rollback_blank_note.status_code == 422
    assert (
        await _config_row_projection(),
        _redis_projection(cache_key, monitor_key),
    ) == before_rollback
    rollback_audit_text = await _audit_text()
    assert "VOICE_CONFIG_CONFIRM_TEXT_INVALID" in rollback_audit_text
    assert "不应回滚" not in rollback_audit_text


@pytest.mark.asyncio
async def test_redis_failure_rolls_back_db_draft_and_cache_state():
    await _seed()
    cache_key = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    old_cache = fake_redis.values[cache_key]
    async with session_factory() as session:
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()
        config = json.loads(active.config_value)
        updated = deepcopy(config["global"])
        updated["maintenance_mode"] = True
        await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="global",
            base_version=1,
            draft_revision=None,
            content=updated,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    fake_redis.fail_setex_once_for = cache_key
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="controlled redis failure"):
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="受控失败",
                admin_user=await _admin(session, "tech_ops"),
            )

    async with session_factory() as session:
        active_rows = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().all()
        draft = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_draft == True,  # noqa: E712
                )
            )
        ).scalars().first()
    assert [(row.version, row.is_active) for row in active_rows] == [(1, True)]
    assert draft is not None and draft.draft_revision == 1
    assert fake_redis.values[cache_key] == old_cache


@pytest.mark.asyncio
async def test_redis_failure_compensates_voice_rollback_and_crisis_publish_rollback():
    await _seed()
    await _save_changed_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section="global",
        role="tech_ops",
        mutate=lambda value: value.update({"soft_stop": True}),
    )
    async with session_factory() as session:
        await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="建立 V2",
            admin_user=await _admin(session, "tech_ops"),
        )

    voice_cache = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    voice_monitor = f"publish_monitor:{VOICE_CALL_CONFIG_KEY}"
    before_voice_rollback = (
        await _config_row_projection(),
        _redis_projection(voice_cache, voice_monitor),
        await _audit_text(),
    )
    fake_redis.fail_setex_once_for = voice_cache
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="controlled redis failure"):
            await realtime_voice_config_service.rollback(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                version=1,
                confirm_text="CONFIRM",
                change_note="受控回滚失败",
                admin_user=await _admin(session, "tech_ops"),
            )
    assert (
        await _config_row_projection(),
        _redis_projection(voice_cache, voice_monitor),
        await _audit_text(),
    ) == before_voice_rollback

    async with session_factory() as session:
        await publish_crisis_keywords_atomically(
            session,
            keywords=["自杀", "伤害自己"],
            admin_user=await _admin(session, "ai_trainer"),
        )
    crisis_cache = "active_config:crisis_keywords"
    crisis_monitor = "publish_monitor:crisis_keywords"
    before_crisis_publish = (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
        await _audit_text(),
    )
    fake_redis.fail_setex_once_for = crisis_cache
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="controlled redis failure"):
            await publish_crisis_keywords_atomically(
                session,
                keywords=["绝望"],
                admin_user=await _admin(session, "ai_trainer"),
            )
    assert (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
        await _audit_text(),
    ) == before_crisis_publish

    async with session_factory() as session:
        published = await publish_crisis_keywords_atomically(
            session,
            keywords=["绝望"],
            admin_user=await _admin(session, "ai_trainer"),
        )
    assert published["version"] == 2
    before_crisis_rollback = (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
        await _audit_text(),
    )
    fake_redis.fail_setex_once_for = crisis_cache
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="controlled redis failure"):
            await rollback_crisis_keywords_atomically(
                session,
                version=1,
                admin_user=await _admin(session, "ai_trainer"),
            )
    assert (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
        await _audit_text(),
    ) == before_crisis_rollback


@pytest.mark.asyncio
async def test_api_infrastructure_failures_compensate_state_and_commit_safe_failure_audit(
    client: AsyncClient,
):
    await _seed()
    await _save_changed_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section="global",
        role="tech_ops",
        mutate=lambda value: value.update({"soft_stop": True}),
    )
    voice_cache = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    voice_monitor = f"publish_monitor:{VOICE_CALL_CONFIG_KEY}"
    before_voice = (
        await _config_row_projection(),
        _redis_projection(voice_cache, voice_monitor),
    )
    fake_redis.fail_setex_once_for = voice_cache
    voice_response = await client.post(
        "/api/admin/voice/config/config/publish",
        headers=_headers("tech_ops"),
        json={"confirm_text": "CONFIRM", "change_note": "受控基础设施失败"},
    )
    assert voice_response.status_code == 503
    assert (
        await _config_row_projection(),
        _redis_projection(voice_cache, voice_monitor),
    ) == before_voice

    async with session_factory() as session:
        voice_failure = (
            await session.execute(
                select(AdminOperationLog)
                .where(
                    AdminOperationLog.action == "publish",
                    AdminOperationLog.after_value.contains(
                        "VOICE_CONFIG_PUBLISH_FAILED"
                    ),
                )
                .order_by(AdminOperationLog.id.desc())
            )
        ).scalars().first()
    assert voice_failure is not None
    assert "受控基础设施失败" not in voice_failure.after_value
    assert json.loads(voice_failure.after_value)["result"] == "failed"

    async with session_factory() as session:
        await publish_crisis_keywords_atomically(
            session,
            keywords=["自杀", "伤害自己"],
            admin_user=await _admin(session, "ai_trainer"),
        )
    crisis_cache = "active_config:crisis_keywords"
    crisis_monitor = "publish_monitor:crisis_keywords"
    before_crisis = (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
    )
    fake_redis.fail_setex_once_for = crisis_cache
    crisis_response = await client.put(
        "/api/admin/safety-rules/crisis-keywords",
        headers=_headers("ai_trainer"),
        json={"keywords": ["绝望"]},
    )
    assert crisis_response.status_code == 503
    assert (
        await _config_row_projection(),
        _redis_projection(crisis_cache, crisis_monitor),
    ) == before_crisis
    async with session_factory() as session:
        crisis_failure = (
            await session.execute(
                select(AdminOperationLog)
                .where(
                    AdminOperationLog.action == "publish",
                    AdminOperationLog.after_value.contains(
                        "VOICE_CRISIS_KEYWORDS_PUBLISH_FAILED"
                    ),
                )
                .order_by(AdminOperationLog.id.desc())
            )
        ).scalars().first()
    assert crisis_failure is not None
    assert json.loads(crisis_failure.after_value)["result"] == "failed"


@pytest.mark.asyncio
async def test_crisis_keywords_normalize_history_rollback_and_empty_rejection(
    client: AsyncClient,
):
    async with session_factory() as session:
        admin = await _admin(session, "ai_trainer")
        first = await publish_crisis_keywords_atomically(
            session,
            keywords=[" 自杀 ", "", "伤害自己", "自杀"],
            admin_user=admin,
        )
        assert first["keywords"] == ["伤害自己", "自杀"]
    assert json.loads(fake_redis.values["active_config:crisis_keywords"]) == ["伤害自己", "自杀"]

    async with session_factory() as session:
        await publish_crisis_keywords_atomically(
            session,
            keywords=["绝望"],
            admin_user=await _admin(session, "ai_trainer"),
        )
    async with session_factory() as session:
        rollback = await rollback_crisis_keywords_atomically(
            session,
            version=1,
            admin_user=await _admin(session, "ai_trainer"),
        )
        assert rollback["version"] == 3
        assert rollback["rolled_back_from_version"] == 1
    assert json.loads(fake_redis.values["active_config:crisis_keywords"]) == ["伤害自己", "自杀"]
    assert fake_redis.ttls["publish_monitor:crisis_keywords"] == 300

    async with session_factory() as session:
        logs = (
            await session.execute(
                select(AdminOperationLog)
                .where(AdminOperationLog.target_description.contains("危机关键词"))
                .order_by(AdminOperationLog.id.asc())
            )
        ).scalars().all()
    assert [row.action for row in logs] == ["publish", "publish", "rollback"]
    second_before = json.loads(logs[1].before_value)
    assert second_before["keyword_count"] == 2
    assert second_before["content_sha256"] == content_sha256(["伤害自己", "自杀"])

    wrong_confirm = await client.post(
        "/api/admin/safety-rules/crisis-keywords/rollback",
        headers=_headers("ai_trainer"),
        json={"version": 1, "confirm_text": "confirm"},
    )
    assert wrong_confirm.status_code == 400
    async with session_factory() as session:
        failed_rollback = (
            await session.execute(
                select(AdminOperationLog)
                .where(
                    AdminOperationLog.action == "rollback",
                    AdminOperationLog.after_value.contains(
                        "VOICE_CONFIG_CONFIRM_TEXT_INVALID"
                    ),
                )
                .order_by(AdminOperationLog.id.desc())
            )
        ).scalars().first()
    assert failed_rollback is not None
    assert json.loads(failed_rollback.after_value)["result"] == "failed"

    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await publish_crisis_keywords_atomically(
                session,
                keywords=[" ", ""],
                admin_user=await _admin(session, "ai_trainer"),
            )
        assert exc_info.value.code == CRISIS_KEYWORDS_EMPTY

    async with session_factory() as session:
        session.add(
            AdminConfig(
                config_key="crisis_keywords",
                config_value="[]",
                version=4,
                is_draft=False,
                is_active=False,
                updated_by="invalid-history-fixture",
            )
        )
        await session.commit()
    before_invalid_rollback = (
        await _config_row_projection(),
        _redis_projection(
            "active_config:crisis_keywords",
            "publish_monitor:crisis_keywords",
        ),
    )
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as rollback_error:
            await rollback_crisis_keywords_atomically(
                session,
                version=4,
                admin_user=await _admin(session, "ai_trainer"),
            )
        assert rollback_error.value.code == CRISIS_KEYWORDS_EMPTY
        await session.rollback()
    assert (
        await _config_row_projection(),
        _redis_projection(
            "active_config:crisis_keywords",
            "publish_monitor:crisis_keywords",
        ),
    ) == before_invalid_rollback


@pytest.mark.asyncio
async def test_concurrent_voice_rollbacks_and_crisis_publishes_keep_monotonic_unique_active():
    await _seed()
    await _save_changed_section(
        config_key=VOICE_CALL_SCRIPT_KEY,
        section="followup",
        role="ai_trainer",
        mutate=lambda value: value.update({"missed_explanation_template": "并发前 V2"}),
    )
    async with session_factory() as session:
        await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            confirm_text="CONFIRM",
            change_note="建立并发回滚前 V2",
            admin_user=await _admin(session, "ai_trainer"),
        )

    async def rollback_once(note: str):
        async with session_factory() as session:
            return await realtime_voice_config_service.rollback(
                session,
                config_key=VOICE_CALL_SCRIPT_KEY,
                version=1,
                confirm_text="CONFIRM",
                change_note=note,
                admin_user=await _admin(session, "ai_trainer"),
            )

    rollback_results = await asyncio.gather(
        rollback_once("并发回滚 A"),
        rollback_once("并发回滚 B"),
    )
    assert {item["version"] for item in rollback_results} == {3, 4}
    async with session_factory() as session:
        script_rows = (
            await session.execute(
                select(AdminConfig)
                .where(
                    AdminConfig.config_key == VOICE_CALL_SCRIPT_KEY,
                    AdminConfig.is_draft == False,  # noqa: E712
                )
                .order_by(AdminConfig.version.asc())
            )
        ).scalars().all()
    assert [row.version for row in script_rows] == [1, 2, 3, 4]
    assert sum(row.is_active for row in script_rows) == 1
    assert script_rows[-1].is_active is True

    async def publish_crisis_once(words: list[str]):
        async with session_factory() as session:
            return await publish_crisis_keywords_atomically(
                session,
                keywords=words,
                admin_user=await _admin(session, "ai_trainer"),
            )

    crisis_results = await asyncio.gather(
        publish_crisis_once(["自杀"]),
        publish_crisis_once(["伤害自己"]),
    )
    assert {item["version"] for item in crisis_results} == {1, 2}
    async with session_factory() as session:
        crisis_rows = (
            await session.execute(
                select(AdminConfig)
                .where(
                    AdminConfig.config_key == "crisis_keywords",
                    AdminConfig.is_draft == False,  # noqa: E712
                )
                .order_by(AdminConfig.version.asc())
            )
        ).scalars().all()
    assert [row.version for row in crisis_rows] == [1, 2]
    assert sum(row.is_active for row in crisis_rows) == 1
    assert crisis_rows[-1].is_active is True
    assert json.loads(fake_redis.values["active_config:crisis_keywords"]) == json.loads(
        crisis_rows[-1].config_value
    )


@pytest.mark.asyncio
async def test_direct_and_nested_secret_submission_is_rejected_without_any_sentinel_residue(
    client: AsyncClient,
):
    await _seed()
    sentinel = "step005-secret-SENTINEL-value"
    async with session_factory() as session:
        active = await realtime_voice_config_service._active(
            session, VOICE_CALL_CONFIG_KEY
        )
        original_s2s = json.loads(active.config_value)["s2s"]

    cache_keys = (
        f"active_config:{VOICE_CALL_CONFIG_KEY}",
        f"publish_monitor:{VOICE_CALL_CONFIG_KEY}",
    )
    before_state = (
        await _config_row_projection(),
        _redis_projection(*cache_keys),
    )
    before_audit = await _audit_text()
    payloads = []
    direct = deepcopy(original_s2s)
    direct["credential_ref"] = sentinel
    payloads.append(direct)
    explicit_secret_field = deepcopy(original_s2s)
    explicit_secret_field["access_key"] = sentinel
    payloads.append(explicit_secret_field)
    nested = deepcopy(original_s2s)
    nested["credential_revision_ref"] = {
        "metadata": {"token": sentinel}
    }
    payloads.append(nested)

    for content in payloads:
        response = await client.patch(
            "/api/admin/voice/config/config/draft/s2s",
            headers=_headers("tech_ops"),
            json={"base_version": 1, "draft_revision": None, "content": content},
        )
        assert response.status_code == 400, response.text
        response_text = response.text
        assert sentinel not in response_text
        errors = response.json()["data"]["errors"]
        assert VOICE_CONFIG_SECRET_FORBIDDEN in {item["code"] for item in errors}

    assert (
        await _config_row_projection(),
        _redis_projection(*cache_keys),
    ) == before_state
    after_audit = await _audit_text()
    assert after_audit != before_audit
    async with session_factory() as session:
        failed_save_logs = (
            await session.execute(
                select(AdminOperationLog).where(
                    AdminOperationLog.action == "save_draft"
                )
            )
        ).scalars().all()
    failed_payloads = [
        json.loads(row.after_value)
        for row in failed_save_logs
        if row.after_value and json.loads(row.after_value).get("result") == "failed"
    ]
    assert len(failed_payloads) >= 3
    assert VOICE_CONFIG_SECRET_FORBIDDEN in after_audit
    all_persistent_text = canonical_json(await _config_row_projection()) + canonical_json(
        _redis_projection(*cache_keys)
    ) + await _audit_text()
    assert sentinel not in all_persistent_text
    async with session_factory() as session:
        assert await realtime_voice_config_service._draft(
            session, VOICE_CALL_CONFIG_KEY
        ) is None


@pytest.mark.asyncio
async def test_api_five_role_matrix_credential_projection_and_crisis_roles(client: AsyncClient):
    await _seed()
    for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
        response = await client.get(
            "/api/admin/voice/config/config",
            headers=_headers(role),
        )
        assert response.status_code == 200, (role, response.text)
        config = response.json()["data"]["config"]
        assert "step005-secret-SENTINEL-value" not in json.dumps(config, ensure_ascii=False)
        assert config["s2s"]["credential_configured"] is True
        if role in {"super_admin", "tech_ops"}:
            assert config["s2s"]["credential_ref"] == "DOUBAO_S2S_ACCESS_KEY"
        else:
            assert "credential_ref" not in config["s2s"]
            assert "credential_revision_ref" not in config["s2s"]
        for path in (
            "/api/admin/voice/config/script",
            "/api/admin/voice/config/config/history",
            "/api/admin/voice/config/script/history",
            "/api/admin/voice/config/config/history/1",
            "/api/admin/voice/config/script/history/1",
        ):
            read_response = await client.get(path, headers=_headers(role))
            assert read_response.status_code == 200, (role, path, read_response.text)

    config_body = {
        "base_version": 1,
        "draft_revision": None,
        "content": {
            "enabled": False,
            "maintenance_mode": False,
            "maintenance_message": "维护中",
            "soft_stop": True,
            "rollout": {"mode": "allowlist", "user_ids": []},
            "test_user_ids": [],
        },
    }
    assert (
        await client.patch(
            "/api/admin/voice/config/config/draft/global",
            headers=_headers("ai_trainer"),
            json=config_body,
        )
    ).status_code == 403
    assert (
        await client.patch(
            "/api/admin/voice/config/config/draft/global",
            headers=_headers("tech_ops"),
            json=config_body,
        )
    ).status_code == 200

    config_write_requests = (
        (
            "PATCH",
            "/api/admin/voice/config/config/draft/global",
            config_body,
        ),
        ("DELETE", "/api/admin/voice/config/config/draft/global", None),
        ("DELETE", "/api/admin/voice/config/config/draft", None),
        ("POST", "/api/admin/voice/config/config/validate", {}),
        (
            "POST",
            "/api/admin/voice/config/config/publish",
            {"confirm_text": "CONFIRM", "change_note": "无权发布"},
        ),
        (
            "POST",
            "/api/admin/voice/config/config/rollback",
            {"version": 1, "confirm_text": "CONFIRM", "change_note": "无权回滚"},
        ),
    )
    for role in ("ai_trainer", "ops_admin", "observer"):
        for method, path, body in config_write_requests:
            forbidden = await client.request(
                method,
                path,
                headers=_headers(role),
                json=body,
            )
            assert forbidden.status_code == 403, (role, method, path, forbidden.text)

    script_followup = {
        "base_version": 1,
        "draft_revision": None,
        "content": {"missed_explanation_template": DEFAULT_MISSED_EXPLANATION_TEMPLATE},
    }
    assert (
        await client.patch(
            "/api/admin/voice/config/script/draft/followup",
            headers=_headers("tech_ops"),
            json=script_followup,
        )
    ).status_code == 403
    assert (
        await client.patch(
            "/api/admin/voice/config/script/draft/followup",
            headers=_headers("ai_trainer"),
            json=script_followup,
        )
    ).status_code == 200

    script_write_requests = (
        (
            "PATCH",
            "/api/admin/voice/config/script/draft/followup",
            script_followup,
        ),
        ("DELETE", "/api/admin/voice/config/script/draft/followup", None),
        ("DELETE", "/api/admin/voice/config/script/draft", None),
        ("POST", "/api/admin/voice/config/script/validate", {}),
        (
            "POST",
            "/api/admin/voice/config/script/publish",
            {"confirm_text": "CONFIRM", "change_note": "无权发布"},
        ),
        (
            "POST",
            "/api/admin/voice/config/script/rollback",
            {"version": 1, "confirm_text": "CONFIRM", "change_note": "无权回滚"},
        ),
    )
    for role in ("tech_ops", "ops_admin", "observer"):
        for method, path, body in script_write_requests:
            forbidden = await client.request(
                method,
                path,
                headers=_headers(role),
                json=body,
            )
            assert forbidden.status_code == 403, (role, method, path, forbidden.text)

    for role in ("super_admin", "ai_trainer", "observer"):
        assert (
            await client.get("/api/admin/safety-rules", headers=_headers(role))
        ).status_code == 200
        assert (
            await client.get(
                "/api/admin/safety-rules/crisis-keywords/history",
                headers=_headers(role),
            )
        ).status_code == 200
    for role in ("tech_ops", "ops_admin"):
        assert (
            await client.get("/api/admin/safety-rules", headers=_headers(role))
        ).status_code == 403
        assert (
            await client.get(
                "/api/admin/safety-rules/crisis-keywords/history",
                headers=_headers(role),
            )
        ).status_code == 403
    assert (
        await client.put(
            "/api/admin/safety-rules/crisis-keywords",
            headers=_headers("observer"),
            json={"keywords": ["自杀"]},
        )
    ).status_code == 403
    response = await client.put(
        "/api/admin/safety-rules/crisis-keywords",
        headers=_headers("ai_trainer"),
        json={"keywords": [" 自杀 ", "自杀", "伤害自己"]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["keywords"] == ["伤害自己", "自杀"]

    for role in ("tech_ops", "ops_admin", "observer"):
        forbidden_put = await client.put(
            "/api/admin/safety-rules/crisis-keywords",
            headers=_headers(role),
            json={"keywords": ["无权危机词"]},
        )
        assert forbidden_put.status_code == 403
        forbidden_rollback = await client.post(
            "/api/admin/safety-rules/crisis-keywords/rollback",
            headers=_headers(role),
            json={"version": 1, "confirm_text": "CONFIRM"},
        )
        assert forbidden_rollback.status_code == 403

    super_update = await client.put(
        "/api/admin/safety-rules/crisis-keywords",
        headers=_headers("super_admin"),
        json={"keywords": ["绝望"]},
    )
    assert super_update.status_code == 200
    ai_rollback = await client.post(
        "/api/admin/safety-rules/crisis-keywords/rollback",
        headers=_headers("ai_trainer"),
        json={"version": 1, "confirm_text": "CONFIRM"},
    )
    assert ai_rollback.status_code == 200


@pytest.mark.asyncio
async def test_config_schema_rejects_invalid_nested_value_shapes():
    persona_ref = {
        "config_key": "persona",
        "version": 1,
        "content_sha256": "sha256:" + "1" * 64,
    }
    base = build_canonical_voice_seed_manifest(persona_ref)[VOICE_CALL_CONFIG_KEY]
    mutations = (
        ("global.maintenance_message", lambda value: value["global"].update({"maintenance_message": "  "})),
        ("global.rollout.mode", lambda value: value["global"]["rollout"].update({"mode": {}})),
        ("s2s.credential_revision_ref", lambda value: value["s2s"].update({"credential_revision_ref": {}})),
        ("voice.candidates[0].enabled", lambda value: value["voice"]["candidates"][0].pop("enabled")),
        ("voice.candidates[0].extra", lambda value: value["voice"]["candidates"][0].update({"extra": True})),
        ("voice.candidates[0].voice_version", lambda value: value["voice"]["candidates"][0].update({"voice_version": 1})),
        ("voice.persona_mapping", lambda value: value["voice"].update({"persona_mapping": []})),
        ("voice.tone_instruction", lambda value: value["voice"].update({"tone_instruction": 7})),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.enabled",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update({"enabled": "false"}),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.forced_enabled",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update({"forced_enabled": 0}),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.provider_profile",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update({"provider_profile": 3}),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.last_test_result",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update({"last_test_result": "unknown"}),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.verification_status",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"verification_status": "failed"}
            ),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.verification_status",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"verification_status": {}}
            ),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.effective_scope",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"effective_scope": "test"}
            ),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.effective_scope",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"effective_scope": {}}
            ),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.last_test_result",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"last_test_result": {}}
            ),
        ),
        (
            f"capabilities.{VOICE_CAPABILITY_KEYS[0]}.evidence_report_id",
            lambda value: value["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
                {"evidence_report_id": "00000000-0000-4000-8000-000000000001"}
            ),
        ),
        (
            "s2s.endpoint",
            lambda value: value["s2s"].update(
                {"endpoint": "wss://user:plaincredential@example.com/dialogue"}
            ),
        ),
        (
            "s2s.endpoint",
            lambda value: value["s2s"].update({"endpoint": "wss://[::1"}),
        ),
        (
            "s2s.endpoint",
            lambda value: value["s2s"].update(
                {"endpoint": "wss://example.com:bad/dialogue"}
            ),
        ),
        (
            "s2s.endpoint",
            lambda value: value["s2s"].update(
                {"endpoint": "wss://example.com/dialogue?auth=plaincredential"}
            ),
        ),
        (
            "s2s.endpoint",
            lambda value: value["s2s"].update(
                {
                    "endpoint": (
                        "wss://example.com/dialogue?opaque="
                        "step005-secret-SENTINEL-value"
                    )
                }
            ),
        ),
    )
    for expected_field, mutate in mutations:
        candidate = deepcopy(base)
        mutate(candidate)
        issues = validate_voice_bundle(VOICE_CALL_CONFIG_KEY, candidate)
        assert expected_field in {issue["field"] for issue in issues}, expected_field


@pytest.mark.asyncio
async def test_crisis_secret_and_empty_inputs_are_rejected_audited_and_never_persisted(
    client: AsyncClient,
):
    sentinel = "step005-secret-SENTINEL-value"
    before_state = (
        await _config_row_projection(),
        _redis_projection(
            "active_config:crisis_keywords",
            "publish_monitor:crisis_keywords",
        ),
    )

    secret_response = await client.put(
        "/api/admin/safety-rules/crisis-keywords",
        headers=_headers("ai_trainer"),
        json={"keywords": [sentinel]},
    )
    assert secret_response.status_code == 400
    assert secret_response.json()["data"]["error_code"] == VOICE_CONFIG_SECRET_FORBIDDEN
    assert sentinel not in secret_response.text

    empty_response = await client.put(
        "/api/admin/safety-rules/crisis-keywords",
        headers=_headers("ai_trainer"),
        json={"keywords": []},
    )
    assert empty_response.status_code == 400
    assert empty_response.json()["data"]["error_code"] == CRISIS_KEYWORDS_EMPTY

    assert (
        await _config_row_projection(),
        _redis_projection(
            "active_config:crisis_keywords",
            "publish_monitor:crisis_keywords",
        ),
    ) == before_state
    audit_text = await _audit_text()
    assert sentinel not in audit_text
    assert VOICE_CONFIG_SECRET_FORBIDDEN in audit_text
    assert CRISIS_KEYWORDS_EMPTY in audit_text


def test_script_and_followup_schema_reject_undeclared_or_invalid_nested_shapes():
    persona_ref = {
        "config_key": "persona",
        "version": 1,
        "content_sha256": "sha256:" + "1" * 64,
    }
    manifest = build_canonical_voice_seed_manifest(persona_ref)
    script = manifest[VOICE_CALL_SCRIPT_KEY]
    script_mutations = (
        (
            "context_pack.voice_instruction_template",
            lambda value: value["context_pack"].update(
                {"voice_instruction_template": {"unexpected": True}}
            ),
        ),
        (
            "call_answer.prompt_template",
            lambda value: value["call_answer"].update({"prompt_template": []}),
        ),
        (
            "recall.prompt_template",
            lambda value: value["recall"].update({"prompt_template": 7}),
        ),
        (
            "memory.prompt_template",
            lambda value: value["memory"].update({"prompt_template": False}),
        ),
        (
            "silence_and_exit.exit_intent_template",
            lambda value: value["silence_and_exit"].update(
                {"exit_intent_template": "   "}
            ),
        ),
        (
            "end_reason.user_hangup",
            lambda value: value["end_reason"].update({"user_hangup": []}),
        ),
        (
            "end_reason.user_cancel.show_end_page",
            lambda value: value["end_reason"].update(
                {"user_cancel": {"show_end_page": True, "action": "return_to_chat"}}
            ),
        ),
        (
            "end_reason.user_cancel.action",
            lambda value: value["end_reason"].update(
                {"user_cancel": {"show_end_page": False, "action": "show_end_page"}}
            ),
        ),
        (
            "end_reason.provider_error.extra",
            lambda value: value["end_reason"]["provider_error"].update(
                {"extra": "not allowed"}
            ),
        ),
        (
            "end_reason.system_error.after_connected",
            lambda value: value["end_reason"]["system_error"].update(
                {"after_connected": ""}
            ),
        ),
    )
    for expected_field, mutate in script_mutations:
        candidate = deepcopy(script)
        mutate(candidate)
        issues = validate_voice_bundle(VOICE_CALL_SCRIPT_KEY, candidate)
        assert expected_field in {issue["field"] for issue in issues}, expected_field

    schedule = get_default_followup_schedule()
    schedule["unexpected"] = True
    assert "followup.schedule.unexpected" in {
        issue["field"] for issue in validate_followup_schedule(schedule)
    }

    stage_schedule = get_default_followup_schedule()
    stage_schedule["stages"]["friend"]["unexpected"] = True
    assert "followup.schedule.stages.friend.unexpected" in {
        issue["field"] for issue in validate_followup_schedule(stage_schedule)
    }


@pytest.mark.asyncio
async def test_persona_ref_requires_published_version_and_sha_but_keeps_pruned_anchor():
    await _seed()
    async with session_factory() as session:
        persona_v1 = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == "persona",
                    AdminConfig.version == 1,
                )
            )
        ).scalars().one()
        persona_v1.is_active = False
        persona_v2_value = canonical_json({"background": "V2", "personality": "温柔"})
        persona_v2 = AdminConfig(
            config_key="persona",
            config_value=persona_v2_value,
            version=2,
            is_draft=False,
            is_active=True,
            updated_by="step005-super_admin",
        )
        session.add(persona_v2)
        await session.commit()
        v1_sha = "sha256:" + hashlib.sha256(persona_v1.config_value.encode("utf-8")).hexdigest()
        v2_sha = "sha256:" + hashlib.sha256(persona_v2_value.encode("utf-8")).hexdigest()

    async def save_persona_ref(version: int, sha: str) -> None:
        async with session_factory() as session:
            active = await realtime_voice_config_service._active(session, VOICE_CALL_CONFIG_KEY)
            draft = await realtime_voice_config_service._draft(session, VOICE_CALL_CONFIG_KEY)
            await realtime_voice_config_service.save_draft_section(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                section="persona_ref",
                base_version=active.version,
                draft_revision=draft.draft_revision if draft else None,
                content={"config_key": "persona", "version": version, "content_sha256": sha},
                admin_user=await _admin(session, "tech_ops"),
            )
            await session.commit()

    # 当前 persona 版本与历史 persona 版本均按原始已发布正文 sha 精确核验。
    await save_persona_ref(2, v2_sha)
    async with session_factory() as session:
        assert (
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="切换当前 persona V2",
                admin_user=await _admin(session, "tech_ops"),
            )
        )["version"] == 2
    await save_persona_ref(1, v1_sha)
    async with session_factory() as session:
        assert (
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="切回历史 persona V1",
                admin_user=await _admin(session, "tech_ops"),
            )
        )["version"] == 3

    # 存在的 persona 版本必须匹配真实 sha；未来/空洞版本同样拒绝。
    await save_persona_ref(2, "sha256:" + "0" * 64)
    async with session_factory() as session:
        validation = await realtime_voice_config_service.validate_current(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            preview=None,
            admin_user=await _admin(session, "tech_ops"),
        )
        assert validation["valid"] is False
        assert VOICE_CONFIG_PERSONA_REF_INVALID in {item["code"] for item in validation["errors"]}
        with pytest.raises(VoiceConfigError) as wrong_sha:
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="伪造 hash",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert wrong_sha.value.code == VOICE_CONFIG_PERSONA_REF_INVALID
        await session.rollback()
    async with session_factory() as session:
        await realtime_voice_config_service.discard_draft(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    await save_persona_ref(999, "sha256:" + "9" * 64)
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as future_ref:
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="伪造未来版本",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert future_ref.value.code == VOICE_CONFIG_PERSONA_REF_INVALID
        await session.rollback()
    async with session_factory() as session:
        await realtime_voice_config_service.discard_draft(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    # persona V1 被历史裁剪后，已发布 voice config 保存的 V1+sha 仍可发布/回滚。
    async with session_factory() as session:
        await session.execute(
            delete(AdminConfig).where(
                AdminConfig.config_key == "persona",
                AdminConfig.version == 1,
            )
        )
        await session.commit()
    await save_persona_ref(1, v1_sha)
    async with session_factory() as session:
        pruned_publish = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="复用已保存的裁剪锚",
            admin_user=await _admin(session, "tech_ops"),
        )
        assert pruned_publish["version"] == 4
        pruned_rollback = await realtime_voice_config_service.rollback(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="回滚裁剪 persona 锚",
            admin_user=await _admin(session, "tech_ops"),
        )
        assert pruned_rollback["version"] == 5

    await save_persona_ref(1, "sha256:" + "8" * 64)
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as forged_pruned:
            await realtime_voice_config_service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="伪造裁剪锚",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert forged_pruned.value.code == VOICE_CONFIG_PERSONA_REF_INVALID


@pytest.mark.asyncio
async def test_audit_projection_is_complete_and_change_note_never_leaks_secret():
    await _seed()
    await _save_changed_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section="global",
        role="tech_ops",
        mutate=lambda value: value.update({"soft_stop": True}),
    )
    sentinel = "step005-secret-SENTINEL-value"
    async with session_factory() as session:
        await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note=sentinel,
            admin_user=await _admin(session, "tech_ops"),
        )
        rows = (await session.execute(select(AdminOperationLog))).scalars().all()

    required = {
        "permission",
        "config_version",
        "base_version",
        "draft_revision",
        "changed_sections",
        "change_note",
        "verification_status",
        "forced_enabled",
        "effective_scope",
        "result",
        "failure_category",
    }
    config_payloads = []
    for row in rows:
        if row.after_value and row.after_value.startswith("{"):
            payload = json.loads(row.after_value)
            if payload.get("config_key") == VOICE_CALL_CONFIG_KEY:
                config_payloads.append(payload)
                assert required <= set(payload)
                assert "credential_ref" not in row.after_value
                assert "maintenance_message" not in row.after_value
                assert sentinel not in row.after_value
    publish_payload = next(item for item in config_payloads if item["action"] == "publish")
    assert publish_payload["permission"] == "tech_ops"
    assert publish_payload["result"] == "success"
    assert publish_payload["failure_category"] is None
    assert publish_payload["change_note"] == {
        "present": True,
        "length": len(sentinel),
        "sha256": "sha256:" + hashlib.sha256(sentinel.encode("utf-8")).hexdigest(),
    }
    assert sentinel not in await _audit_text()
    assert sentinel not in canonical_json(await _config_row_projection())
    assert sentinel not in canonical_json(_redis_projection(f"active_config:{VOICE_CALL_CONFIG_KEY}"))


@pytest.mark.asyncio
async def test_crisis_health_read_does_not_repair_cache_and_reports_active_version(client):
    path = '/api/admin/safety-rules'
    result = await client.get(path, headers=_headers('observer'))
    assert result.status_code == 200
    assert result.json()['data']['crisis_keywords_status']['publication_status'] == 'unpublished'
    async with session_factory() as db:
        db.add(AdminConfig(config_key='crisis_keywords', config_value='["fixture-policy"]',
                           version=7, is_active=True, is_draft=False))
        await db.commit()
    result = await client.get(path, headers=_headers('observer'))
    data = result.json()['data']
    assert data['crisis_keywords'] == ['fixture-policy']
    assert data['crisis_keywords_status'] == dict(publication_status='published', active_version=7,
        keyword_count=1, cache_status='missing', fallback_ready=True)
    assert 'active_config:crisis_keywords' not in fake_redis.values


@pytest.mark.asyncio
async def test_crisis_health_distinguishes_invalid_publication_and_cache(client):
    path = '/api/admin/safety-rules'
    cache_key = 'active_config:crisis_keywords'
    async with session_factory() as db:
        row = AdminConfig(config_key='crisis_keywords', config_value='[]',
                          version=9, is_active=True, is_draft=False)
        db.add(row)
        await db.commit()

    fake_redis.values[cache_key] = '["old-policy"]'
    result = await client.get(path, headers=_headers('observer'))
    assert result.status_code == 200
    status = result.json()['data']['crisis_keywords_status']
    assert status == dict(publication_status='invalid', active_version=9,
                          keyword_count=0, cache_status='out_of_sync', fallback_ready=False)

    async with session_factory() as db:
        row = await db.scalar(select(AdminConfig).where(AdminConfig.config_key == 'crisis_keywords'))
        row.config_value = '["current-policy"]'
        await db.commit()
    fake_redis.values[cache_key] = '{invalid-json'
    result = await client.get(path, headers=_headers('observer'))
    assert result.json()['data']['crisis_keywords_status']['cache_status'] == 'invalid'
    fake_redis.values[cache_key] = '["current-policy"]'
    result = await client.get(path, headers=_headers('observer'))
    assert result.json()['data']['crisis_keywords_status'] == dict(
        publication_status='published', active_version=9, keyword_count=1,
        cache_status='healthy', fallback_ready=True)
