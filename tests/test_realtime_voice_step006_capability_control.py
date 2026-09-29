# -*- coding: utf-8 -*-
"""STEP-006 内部强制 test 状态机与可信能力投影边界。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401  注册完整 ORM
import backend.services.realtime_voice_config_service as voice_config_service_module
from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
    VOICE_CAPABILITY_KEYS,
    build_canonical_voice_seed_manifest,
)
from backend.database import Base, get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.routers.admin.voice_config import router as voice_router
from backend.services.realtime_voice_capability_service import (
    compute_evidence_fingerprint,
)
from backend.services.realtime_voice_config_service import (
    RealtimeVoiceConfigService,
    VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
    VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE,
    VOICE_CAPABILITY_FORCE_CONFIRM_INVALID,
    VOICE_CAPABILITY_FORCE_FORBIDDEN,
    VOICE_CAPABILITY_FORCE_REASON_REQUIRED,
    VOICE_CAPABILITY_FORCE_SCOPE_INVALID,
    VOICE_CAPABILITY_FORCE_STATUS_INVALID,
    VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED,
    VOICE_CAPABILITY_PROJECTION_FORGED,
    VOICE_CAPABILITY_TRUSTED_STATE_INVALID,
    VoiceConfigError,
    _execute_publish_with_compensation,
    canonical_json,
    content_sha256,
    realtime_voice_config_service,
    validate_trusted_voice_bundle,
    validate_voice_bundle,
)
from backend.services.realtime_voice_runtime_config_service import (
    RealtimeVoiceRuntimeConfigService,
    RuntimeConfigSource,
)
from backend.utils.admin_auth import get_current_admin


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

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
SECRET_SENTINEL = "step006-force-secret-SENTINEL-value"
CAPABILITY_KEY = VOICE_CAPABILITY_KEYS[0]
EVIDENCE_REPORT_ID = "11111111-1111-4111-8111-111111111111"
EVIDENCE_RUN_ID = "22222222-2222-4222-8222-222222222222"
VERIFIED_AT = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
EVIDENCE_TTL_DAYS = 30
EXPIRES_AT = VERIFIED_AT + timedelta(days=EVIDENCE_TTL_DAYS)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def ttl(self, key: str):
        return self.ttls.get(key, -2 if key not in self.values else -1)

    async def setex(self, key: str, ttl: int, value: str):
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
    role = request.headers.get("x-admin-role", "tech_ops")
    return SimpleNamespace(
        id=role_ids[role],
        username=f"step006-{role}",
        role=role,
    )


app = FastAPI()
app.include_router(voice_router, prefix="/api/admin/voice")
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_admin] = override_current_admin


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    import backend.services.admin_config_service as admin_service_module
    import backend.services.realtime_voice_config_service as voice_service_module

    fake_redis.values.clear()
    fake_redis.ttls.clear()
    role_ids.clear()

    async def redis_provider():
        return fake_redis

    monkeypatch.setattr(admin_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(voice_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(admin_service_module, "async_session_maker", session_factory)
    monkeypatch.setenv("DOUBAO_S2S_ACCESS_KEY", SECRET_SENTINEL)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
            admin = AdminUser(
                username=f"step006-{role}",
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
                updated_by="step006-super_admin",
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://step006",
    ) as http_client:
        yield http_client


def _default_config(*, test_user_ids: list[int] | None = None) -> dict:
    config = build_canonical_voice_seed_manifest(PERSONA_REF)[VOICE_CALL_CONFIG_KEY]
    config["global"]["test_user_ids"] = (
        [101] if test_user_ids is None else deepcopy(test_user_ids)
    )
    return config


def _dimensions(config: dict) -> dict[str, str]:
    return {
        "provider_profile": "doubao-prod-profile",
        "model_version": config["s2s"]["model_version"],
        "protocol_profile": config["s2s"]["protocol_profile"],
        "adapter_version": config["s2s"]["adapter_version"],
        "sdk_version": "doubao-sdk-v1",
        "evidence_suite_version": "voice-suite-v1",
    }


def _projected_dimensions(config: dict) -> dict[str, str]:
    capability = config["capabilities"][CAPABILITY_KEY]
    return {
        field: capability[field]
        for field in (
            "provider_profile",
            "model_version",
            "protocol_profile",
            "adapter_version",
            "sdk_version",
            "evidence_suite_version",
        )
    }


def _trusted_projection(
    config: dict,
    status: str,
    *,
    forced: bool = False,
    all_scope: bool = False,
) -> dict:
    projected = deepcopy(config)
    capability = projected["capabilities"][CAPABILITY_KEY]
    dimensions = _dimensions(projected)
    capability.update(
        {
            "verification_status": status,
            "enabled": forced or all_scope,
            "forced_enabled": forced,
            "effective_scope": "test" if forced else ("all" if all_scope else "off"),
            **dimensions,
            "evidence_fingerprint": compute_evidence_fingerprint(dimensions),
            "verified_at": VERIFIED_AT.isoformat() if status != "failed" else None,
            "expires_at": EXPIRES_AT.isoformat() if status != "failed" else None,
            "evidence_report_id": EVIDENCE_REPORT_ID,
            "last_test_result": "failed" if status == "failed" else "passed",
        }
    )
    return projected


def _verified_all_config(config: dict | None = None) -> dict:
    return _trusted_projection(
        config or _default_config(),
        "verified",
        all_scope=True,
    )


def _evidence_from_config(config: dict) -> VoiceCapabilityEvidence:
    capability = config["capabilities"][CAPABILITY_KEY]
    return VoiceCapabilityEvidence(
        evidence_report_id=capability["evidence_report_id"],
        evidence_run_id=EVIDENCE_RUN_ID,
        capability_key=CAPABILITY_KEY,
        verification_result="passed",
        source_type="admin_capability_test",
        **{
            field: capability[field]
            for field in (
                "provider_profile",
                "model_version",
                "protocol_profile",
                "adapter_version",
                "sdk_version",
                "evidence_suite_version",
            )
        },
        evidence_fingerprint=capability["evidence_fingerprint"],
        evidence_payload={"summary": "passed"},
        report_sha256="b" * 64,
        tested_at=VERIFIED_AT,
        verified_at=VERIFIED_AT,
        evidence_ttl_days_snapshot=capability["evidence_ttl_days"],
        expires_at=EXPIRES_AT,
        operator_id=role_ids["super_admin"],
        created_at=VERIFIED_AT,
    )


async def _insert_voice_config(
    config: dict,
    *,
    draft: dict | None = None,
    draft_revision: int = 1,
) -> None:
    async with session_factory() as session:
        session.add(
            AdminConfig(
                config_key=VOICE_CALL_CONFIG_KEY,
                config_value=canonical_json(config),
                version=1,
                is_draft=False,
                is_active=True,
                updated_by="step006-super_admin",
            )
        )
        if draft is not None:
            session.add(
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(draft),
                    version=0,
                    draft_revision=draft_revision,
                    is_draft=True,
                    is_active=False,
                    updated_by="step006-super_admin",
                )
            )
        await session.commit()


async def _insert_evidence(evidence: VoiceCapabilityEvidence) -> None:
    async with session_factory() as session:
        session.add(evidence)
        await session.commit()


@pytest.mark.asyncio
async def test_step006_credential_revision_ref_is_hidden_in_draft_and_active_projections(
    client: AsyncClient,
):
    active = _default_config()
    active["s2s"]["credential_revision_ref"] = "credential-revision-active"
    draft = deepcopy(active)
    draft["s2s"]["credential_revision_ref"] = "credential-revision-draft"
    await _insert_voice_config(active, draft=draft)

    for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
        draft_response = await client.get(
            "/api/admin/voice/config/config",
            headers={"x-admin-role": role},
        )
        assert draft_response.status_code == 200, (role, draft_response.text)
        active_response = await client.get(
            "/api/admin/voice/config/config/history/1",
            headers={"x-admin-role": role},
        )
        assert active_response.status_code == 200, (role, active_response.text)

        for config in (
            draft_response.json()["data"]["config"],
            active_response.json()["data"]["config"],
        ):
            assert "credential_revision_ref" not in config["s2s"]
            assert config["s2s"]["credential_configured"] is True
            if role in {"super_admin", "tech_ops"}:
                assert config["s2s"]["credential_ref"] == "DOUBAO_S2S_ACCESS_KEY"
            else:
                assert "credential_ref" not in config["s2s"]


async def _insert_rollback_target(target: dict, active: dict) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(target),
                    version=1,
                    is_draft=False,
                    is_active=False,
                    updated_by="step006-super_admin",
                ),
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(active),
                    version=2,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-super_admin",
                ),
            ]
        )
        await session.commit()


async def _admin(session: AsyncSession, role: str) -> AdminUser:
    return (
        await session.execute(select(AdminUser).where(AdminUser.role == role))
    ).scalars().one()


async def _voice_rows_projection() -> list[tuple]:
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


async def _operation_logs() -> list[AdminOperationLog]:
    async with session_factory() as session:
        return (
            await session.execute(select(AdminOperationLog).order_by(AdminOperationLog.id.asc()))
        ).scalars().all()


async def _evidence_rows_projection() -> list[tuple]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(VoiceCapabilityEvidence).order_by(VoiceCapabilityEvidence.id.asc())
            )
        ).scalars().all()
        return [
            (
                row.id,
                row.evidence_report_id,
                row.evidence_run_id,
                row.capability_key,
                row.verification_result,
                row.source_type,
                row.provider_profile,
                row.model_version,
                row.protocol_profile,
                row.adapter_version,
                row.sdk_version,
                row.evidence_suite_version,
                row.evidence_fingerprint,
                canonical_json(row.evidence_payload),
                row.report_sha256,
                row.tested_at,
                row.verified_at,
                row.evidence_ttl_days_snapshot,
                row.expires_at,
                row.operator_id,
                row.created_at,
            )
            for row in rows
        ]


def _trusted_service(dimensions: dict[str, str]) -> RealtimeVoiceConfigService:
    return RealtimeVoiceConfigService(
        current_dimensions_provider=lambda _capability_key, _s2s: deepcopy(dimensions)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("verification_status", "stale"),
        ("forced_enabled", True),
        ("provider_profile", "forged-profile"),
        ("model_version", "forged-model"),
        ("protocol_profile", "forged-protocol"),
        ("adapter_version", "forged-adapter"),
        ("sdk_version", "forged-sdk"),
        ("evidence_suite_version", "forged-suite"),
        ("evidence_fingerprint", "b" * 64),
        ("verified_at", "2026-08-01T00:00:00+00:00"),
        ("expires_at", "2026-09-01T00:00:00+00:00"),
        ("evidence_report_id", "22222222-2222-4222-8222-222222222222"),
        ("last_test_result", "failed"),
    ],
)
async def test_public_capabilities_patch_cannot_forge_server_projection(
    client: AsyncClient,
    field: str,
    forged_value,
):
    config = _default_config()
    await _insert_voice_config(config)
    submitted = deepcopy(config["capabilities"])
    submitted[CAPABILITY_KEY][field] = forged_value

    response = await client.patch(
        "/api/admin/voice/config/config/draft/capabilities",
        headers={"x-admin-role": "tech_ops"},
        json={"base_version": 1, "draft_revision": None, "content": submitted},
    )

    assert response.status_code == 400, response.text
    errors = response.json()["data"]["errors"]
    assert any(
        item["code"] == VOICE_CAPABILITY_PROJECTION_FORGED
        and item["field"] == f"capabilities.{CAPABILITY_KEY}.{field}"
        for item in errors
    )
    rows = await _voice_rows_projection()
    assert len(rows) == 1
    assert json.loads(rows[0][1]) == config


@pytest.mark.asyncio
async def test_public_patch_cannot_bypass_force_path_with_enabled_and_scope_only(
    client: AsyncClient,
):
    config = _default_config()
    await _insert_voice_config(config)
    submitted = deepcopy(config["capabilities"])
    submitted[CAPABILITY_KEY]["enabled"] = True
    submitted[CAPABILITY_KEY]["effective_scope"] = "test"

    response = await client.patch(
        "/api/admin/voice/config/config/draft/capabilities",
        headers={"x-admin-role": "tech_ops"},
        json={"base_version": 1, "draft_revision": None, "content": submitted},
    )

    assert response.status_code == 400, response.text
    assert any(
        item["code"] == VOICE_CAPABILITY_TRUSTED_STATE_INVALID
        for item in response.json()["data"]["errors"]
    )
    assert len(await _voice_rows_projection()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "forced"),
    [("failed", False), ("stale", True), ("verified", False)],
)
async def test_trusted_projection_survives_other_section_save_and_publish(
    status: str,
    forced: bool,
):
    config = _trusted_projection(_default_config(), status, forced=forced)
    assert validate_voice_bundle(VOICE_CALL_CONFIG_KEY, config)
    assert validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, config) == []
    await _insert_voice_config(config)

    async with session_factory() as session:
        quota = deepcopy(config["quota"])
        quota["daily_free_seconds"] += 60
        saved = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="quota",
            base_version=1,
            draft_revision=None,
            content=quota,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()
        assert saved["draft_revision"] == 1

    async with session_factory() as session:
        published = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="调整配额",
            admin_user=await _admin(session, "tech_ops"),
        )
        assert published["version"] == 2

    active_payload = json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"])
    assert active_payload["capabilities"][CAPABILITY_KEY] == config["capabilities"][
        CAPABILITY_KEY
    ]
    assert active_payload["quota"]["daily_free_seconds"] == config["quota"][
        "daily_free_seconds"
    ] + 60


@pytest.mark.asyncio
async def test_real_publish_loader_snapshots_keep_old_call_frozen_and_trace_v1_v2():
    """防止发布链未驱动 loader，或 V2 热切已开始通话的冻结配置。"""

    active = _default_config()
    await _insert_voice_config(active)

    async def runtime_redis_provider():
        return fake_redis

    runtime_service = RealtimeVoiceRuntimeConfigService(
        redis_provider=runtime_redis_provider,
        session_factory=session_factory,
    )

    first = (await runtime_service.load_bundle()).build_snapshot()
    first_values, _ = first.persistence_values()

    assert first.config_snapshot["config_version"] == 1
    assert first.config_snapshot["config_content_sha256"] == content_sha256(active)
    assert first_values["resolved_config"]["s2s"] == active["s2s"]
    assert first_values["resolved_config"]["voice"] == active["voice"]

    next_s2s = deepcopy(active["s2s"])
    next_s2s.update(
        {
            "provider": "doubao",
            "model_version": "2.3.1.0",
            "protocol_profile": "doubao_dialog_v3_pcm_revision2",
            "adapter_version": "voice_adapter_v2",
        }
    )
    async with session_factory() as session:
        saved_s2s = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="s2s",
            base_version=1,
            draft_revision=None,
            content=next_s2s,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    next_voice = deepcopy(active["voice"])
    next_voice["voice_id"] = "S_5kGC1Z212"
    next_voice["voice_version"] = "phase0-v2"
    next_voice["candidates"][0]["voice_version"] = "phase0-v2"
    async with session_factory() as session:
        saved_voice = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="voice",
            base_version=1,
            draft_revision=saved_s2s["draft_revision"],
            content=next_voice,
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    async with session_factory() as session:
        draft_bundle = await realtime_voice_config_service.get_bundle(
            session,
            alias="config",
            role="tech_ops",
        )

    assert draft_bundle is not None
    assert saved_voice["draft_revision"] == 2
    assert draft_bundle["_meta"]["content_sha256"] != draft_bundle["_meta"][
        "active_content_sha256"
    ]
    assert draft_bundle["_meta"]["changed_sections"] == ["s2s", "voice"]
    for field in (
        "provider",
        "model_version",
        "protocol_profile",
        "adapter_version",
    ):
        assert draft_bundle["config"]["s2s"][field] == next_s2s[field]
    assert "credential_revision_ref" not in draft_bundle["config"]["s2s"]
    assert draft_bundle["config"]["s2s"]["credential_configured"] is True
    assert draft_bundle["config"]["voice"] == next_voice

    async with session_factory() as session:
        published = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="发布 S2S 与当前音色 V2",
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    second_bundle = await runtime_service.load_bundle()
    second = second_bundle.build_snapshot()
    second_values, _ = second.persistence_values()

    assert published["version"] == 2
    assert second_bundle.config.source is RuntimeConfigSource.REDIS
    assert second.config_snapshot["config_version"] == 2
    assert second.config_snapshot["config_content_sha256"] == published["content_sha256"]
    assert second_values["resolved_config"]["s2s"] == next_s2s
    assert second_values["resolved_config"]["voice"] == next_voice

    async with session_factory() as session:
        history_v1 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            role="tech_ops",
        )
        history_v2 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=2,
            role="tech_ops",
        )

    for projection, expected_s2s, expected_voice in (
        (history_v1["config"], active["s2s"], active["voice"]),
        (history_v2["config"], next_s2s, next_voice),
    ):
        assert projection["s2s"]["provider"] == "doubao"
        assert projection["s2s"]["model_version"] == expected_s2s["model_version"]
        assert projection["s2s"]["protocol_profile"] == expected_s2s["protocol_profile"]
        assert projection["s2s"]["adapter_version"] == expected_s2s["adapter_version"]
        assert projection["voice"]["voice_id"] == expected_voice["voice_id"]
        assert projection["voice"]["voice_version"] == expected_voice["voice_version"]
    assert history_v1["content_sha256"] == first.config_snapshot["config_content_sha256"]
    assert history_v2["content_sha256"] == second.config_snapshot["config_content_sha256"]

    first_again, _ = first.persistence_values()
    assert first_again == first_values
    assert first_again["config_version"] == 1
    assert first_again["config_content_sha256"] == history_v1["content_sha256"]
    assert first_again["resolved_config"]["s2s"] == active["s2s"]
    assert first_again["resolved_config"]["voice"] == active["voice"]

    serialized_values = [
        canonical_json(first_values),
        canonical_json(second_values),
        canonical_json(history_v1),
        canonical_json(history_v2),
        *fake_redis.values.values(),
    ]
    assert all(SECRET_SENTINEL not in value for value in serialized_values)


@pytest.mark.asyncio
async def test_real_rollback_loader_keeps_two_keys_and_old_snapshots_independent():
    """回滚一个 key 必须只推进该 key 的版本，且不能热切既有通话快照。"""

    seed = build_canonical_voice_seed_manifest(PERSONA_REF)
    config_v1 = seed[VOICE_CALL_CONFIG_KEY]
    script_v1 = seed[VOICE_CALL_SCRIPT_KEY]
    config_v1["global"]["test_user_ids"] = [101]
    async with session_factory() as session:
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(config_v1),
                    version=1,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-super_admin",
                ),
                AdminConfig(
                    config_key=VOICE_CALL_SCRIPT_KEY,
                    config_value=canonical_json(script_v1),
                    version=1,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-super_admin",
                ),
            ]
        )
        await session.commit()

    async def runtime_redis_provider():
        return fake_redis

    runtime_service = RealtimeVoiceRuntimeConfigService(
        redis_provider=runtime_redis_provider,
        session_factory=session_factory,
    )

    def assert_unverified_capability_snapshot(
        capability_snapshot: dict,
        expected_capabilities: dict,
    ) -> None:
        assert set(capability_snapshot) == set(VOICE_CAPABILITY_KEYS)
        assert capability_snapshot == expected_capabilities
        assert all(
            capability["verification_status"] == "unverified"
            and capability["enabled"] is False
            and capability["effective_scope"] == "off"
            for capability in capability_snapshot.values()
        )

    def expected_tech_ops_history_projection(expected_config: dict) -> dict:
        projected = deepcopy(expected_config)
        projected["s2s"]["credential_configured"] = True
        projected["s2s"].pop("credential_revision_ref", None)
        return projected

    config_v2 = deepcopy(config_v1)
    config_v2["quota"]["daily_free_seconds"] += 60
    async with session_factory() as session:
        saved_config = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="quota",
            base_version=1,
            draft_revision=None,
            content=config_v2["quota"],
            admin_user=await _admin(session, "tech_ops"),
        )
        config_published = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="发布配额 V2",
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    script_v2 = deepcopy(script_v1)
    script_v2["call_answer"]["prompt_template"] = "这是 V2 接听话术。"
    async with session_factory() as session:
        saved_script = await realtime_voice_config_service.save_draft_section(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            section="call_answer",
            base_version=1,
            draft_revision=None,
            content=script_v2["call_answer"],
            admin_user=await _admin(session, "ai_trainer"),
        )
        script_published = await realtime_voice_config_service.publish(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            confirm_text="CONFIRM",
            change_note="发布接听话术 V2",
            admin_user=await _admin(session, "ai_trainer"),
        )
        await session.commit()

    bundle_v2 = await runtime_service.load_bundle()
    snapshot_v2 = bundle_v2.build_snapshot()
    snapshot_v2_values, snapshot_v2_capabilities = snapshot_v2.persistence_values()
    assert saved_config["draft_revision"] == saved_script["draft_revision"] == 1
    assert config_published["version"] == script_published["version"] == 2
    assert snapshot_v2_values["config_version"] == 2
    assert snapshot_v2_values["script_version"] == 2
    assert config_published["content_sha256"] == content_sha256(config_v2)
    assert script_published["content_sha256"] == content_sha256(script_v2)
    assert snapshot_v2_values["config_content_sha256"] == content_sha256(config_v2)
    assert snapshot_v2_values["script_content_sha256"] == content_sha256(script_v2)
    assert bundle_v2.config.source is bundle_v2.script.source is RuntimeConfigSource.REDIS
    assert snapshot_v2_values["resolved_config"] == config_v2
    assert snapshot_v2_values["resolved_script"] == script_v2
    assert_unverified_capability_snapshot(
        snapshot_v2_capabilities,
        config_v2["capabilities"],
    )

    async with session_factory() as session:
        config_rolled_back = await realtime_voice_config_service.rollback(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="回滚配额至 V1",
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    bundle_config_v3 = await runtime_service.load_bundle()
    snapshot_config_v3 = bundle_config_v3.build_snapshot()
    snapshot_config_v3_values, snapshot_config_v3_capabilities = (
        snapshot_config_v3.persistence_values()
    )
    assert config_rolled_back["version"] == 3
    assert config_rolled_back["content_sha256"] == content_sha256(config_v1)
    assert snapshot_config_v3_values["config_version"] == 3
    assert snapshot_config_v3_values["script_version"] == 2
    assert snapshot_config_v3_values["config_content_sha256"] == content_sha256(config_v1)
    assert snapshot_config_v3_values["script_content_sha256"] == content_sha256(script_v2)
    assert bundle_config_v3.config.source is bundle_config_v3.script.source is RuntimeConfigSource.REDIS
    assert snapshot_config_v3_values["resolved_config"] == config_v1
    assert snapshot_config_v3_values["resolved_script"] == script_v2
    assert_unverified_capability_snapshot(
        snapshot_config_v3_capabilities,
        config_v1["capabilities"],
    )
    assert snapshot_v2.persistence_values() == (
        snapshot_v2_values,
        snapshot_v2_capabilities,
    )

    async with session_factory() as session:
        script_rolled_back = await realtime_voice_config_service.rollback(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="回滚接听话术至 V1",
            admin_user=await _admin(session, "ai_trainer"),
        )
        await session.commit()

    bundle_v3 = await runtime_service.load_bundle()
    snapshot_v3 = bundle_v3.build_snapshot()
    snapshot_v3_values, snapshot_v3_capabilities = snapshot_v3.persistence_values()
    assert script_rolled_back["version"] == 3
    assert script_rolled_back["content_sha256"] == content_sha256(script_v1)
    assert snapshot_v3_values["config_version"] == snapshot_v3_values["script_version"] == 3
    assert snapshot_v3_values["config_content_sha256"] == content_sha256(config_v1)
    assert snapshot_v3_values["script_content_sha256"] == content_sha256(script_v1)
    assert bundle_v3.config.source is bundle_v3.script.source is RuntimeConfigSource.REDIS
    assert snapshot_v3_values["resolved_config"] == config_v1
    assert snapshot_v3_values["resolved_script"] == script_v1
    assert_unverified_capability_snapshot(
        snapshot_v3_capabilities,
        config_v1["capabilities"],
    )
    assert snapshot_v2.persistence_values() == (
        snapshot_v2_values,
        snapshot_v2_capabilities,
    )
    assert snapshot_config_v3.persistence_values() == (
        snapshot_config_v3_values,
        snapshot_config_v3_capabilities,
    )

    async with session_factory() as session:
        config_history_v1 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            role="tech_ops",
        )
        config_history_v2 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=2,
            role="tech_ops",
        )
        config_history_v3 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=3,
            role="tech_ops",
        )
        script_history_v2 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            version=2,
            role="tech_ops",
        )
        script_history_v1 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            version=1,
            role="tech_ops",
        )
        script_history_v3 = await realtime_voice_config_service.get_history_detail(
            session,
            config_key=VOICE_CALL_SCRIPT_KEY,
            version=3,
            role="tech_ops",
        )

    for history, version, expected_config, expected_hash in (
        (config_history_v1, 1, config_v1, content_sha256(config_v1)),
        (config_history_v2, 2, config_v2, content_sha256(config_v2)),
        (config_history_v3, 3, config_v1, content_sha256(config_v1)),
    ):
        assert history["version"] == version
        assert history["content_sha256"] == expected_hash
        assert history["config"] == expected_tech_ops_history_projection(expected_config)
    for history, version, expected_script, expected_hash in (
        (script_history_v1, 1, script_v1, content_sha256(script_v1)),
        (script_history_v2, 2, script_v2, content_sha256(script_v2)),
        (script_history_v3, 3, script_v1, content_sha256(script_v1)),
    ):
        assert history["version"] == version
        assert history["content_sha256"] == expected_hash
        assert history["config"] == expected_script
    assert json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"]) == config_v1
    assert json.loads(fake_redis.values[f"active_config:{VOICE_CALL_SCRIPT_KEY}"]) == script_v1
    serialized_values = [
        canonical_json(value)
        for value in (
            snapshot_v2_values,
            snapshot_config_v3_values,
            snapshot_v3_values,
            config_history_v1,
            config_history_v2,
            config_history_v3,
            script_history_v1,
            script_history_v2,
            script_history_v3,
            *fake_redis.values.values(),
        )
    ]
    assert all(SECRET_SENTINEL not in value for value in serialized_values)


@pytest.mark.asyncio
async def test_fabricated_verified_all_without_evidence_is_rejected_and_stable():
    active = _default_config()
    draft = _verified_all_config()
    await _insert_voice_config(active, draft=draft)
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows_projection()

    service = _trusted_service(_projected_dimensions(draft))
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note="不得发布伪造 verified/all",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert exc_info.value.code == VOICE_CAPABILITY_ALL_EVIDENCE_INVALID
        assert any(
            item["field"].endswith(".evidence_report_id")
            for item in exc_info.value.errors
        )
        await session.commit()

    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows_projection() == before_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "row_failed",
        "row_error",
        "capability_key_mismatch",
        "row_fingerprint_mismatch",
        "config_provider_profile_mismatch",
        "config_model_version_mismatch",
        "config_protocol_profile_mismatch",
        "config_adapter_version_mismatch",
        "config_sdk_version_mismatch",
        "config_evidence_suite_version_mismatch",
        "config_fingerprint_mismatch",
        "config_verified_at_mismatch",
        "config_expires_at_mismatch",
        "config_ttl_mismatch",
        "derived_expiry_mismatch",
        "expired",
        "s2s_mismatch",
        "current_dimensions_mismatch",
        "current_dimensions_invalid",
        "no_current_dimensions_provider",
    ],
)
async def test_verified_all_publish_gate_fail_closed_and_preserves_rows(case: str):
    active = _default_config()
    draft = _verified_all_config()
    evidence = _evidence_from_config(draft)
    current_dimensions = _projected_dimensions(draft)

    if case == "row_failed":
        evidence.verification_result = "failed"
    elif case == "row_error":
        evidence.verification_result = "error"
    elif case == "capability_key_mismatch":
        evidence.capability_key = VOICE_CAPABILITY_KEYS[1]
    elif case == "row_fingerprint_mismatch":
        evidence.evidence_fingerprint = "c" * 64
    elif case.startswith("config_") and case.endswith("_mismatch"):
        field = case.removeprefix("config_").removesuffix("_mismatch")
        capability = draft["capabilities"][CAPABILITY_KEY]
        if field == "fingerprint":
            capability["evidence_fingerprint"] = "d" * 64
        elif field == "verified_at":
            capability["verified_at"] = (VERIFIED_AT + timedelta(seconds=1)).isoformat()
        elif field == "expires_at":
            capability["expires_at"] = (EXPIRES_AT + timedelta(seconds=1)).isoformat()
        elif field == "ttl":
            capability["evidence_ttl_days"] = EVIDENCE_TTL_DAYS + 1
        else:
            capability[field] += "-mismatch"
    elif case == "derived_expiry_mismatch":
        mismatched_expiry = EXPIRES_AT + timedelta(days=1)
        evidence.expires_at = mismatched_expiry
        draft["capabilities"][CAPABILITY_KEY]["expires_at"] = (
            mismatched_expiry.isoformat()
        )
    elif case == "expired":
        expired_verified_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=EVIDENCE_TTL_DAYS + 1
        )
        expired_at = expired_verified_at + timedelta(days=EVIDENCE_TTL_DAYS)
        evidence.verified_at = expired_verified_at
        evidence.expires_at = expired_at
        capability = draft["capabilities"][CAPABILITY_KEY]
        capability["verified_at"] = expired_verified_at.isoformat()
        capability["expires_at"] = expired_at.isoformat()
    elif case == "s2s_mismatch":
        draft["s2s"]["model_version"] += "-mismatch"
    elif case == "current_dimensions_mismatch":
        current_dimensions["provider_profile"] += "-mismatch"

    await _insert_voice_config(active, draft=draft)
    await _insert_evidence(evidence)
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows_projection()

    if case == "no_current_dimensions_provider":
        service = realtime_voice_config_service
    elif case == "current_dimensions_invalid":
        service = RealtimeVoiceConfigService(
            current_dimensions_provider=lambda _capability_key, _s2s: {}
        )
    else:
        service = _trusted_service(current_dimensions)

    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note=f"拒绝 {case}",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert exc_info.value.code == VOICE_CAPABILITY_ALL_EVIDENCE_INVALID
        if case in {"current_dimensions_invalid", "no_current_dimensions_provider"}:
            assert any(
                item["code"] == VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE
                for item in exc_info.value.errors
            )
        await session.commit()

    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows_projection() == before_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_field_suffix"),
    [
        ("tested_after_verified", ".verified_at"),
        ("future_verified", ".verified_at"),
        ("source_type", ".evidence_report_id"),
        ("report_sha_uppercase", ".evidence_report_id"),
        ("report_sha_prefixed", ".evidence_report_id"),
        ("report_sha_short", ".evidence_report_id"),
        ("report_sha_non_hex", ".evidence_report_id"),
    ],
)
async def test_verified_all_rejects_invalid_evidence_time_and_metadata_stably(
    case: str,
    expected_field_suffix: str,
):
    active = _default_config()
    draft = _verified_all_config()
    evidence = _evidence_from_config(draft)
    if case == "tested_after_verified":
        evidence.tested_at = VERIFIED_AT + timedelta(seconds=1)
    elif case == "future_verified":
        future_verified_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=1
        )
        future_expires_at = future_verified_at + timedelta(days=EVIDENCE_TTL_DAYS)
        evidence.tested_at = future_verified_at
        evidence.verified_at = future_verified_at
        evidence.expires_at = future_expires_at
        capability = draft["capabilities"][CAPABILITY_KEY]
        capability["verified_at"] = future_verified_at.isoformat()
        capability["expires_at"] = future_expires_at.isoformat()
    elif case == "source_type":
        # 绕过 ORM validator 模拟数据库中已存在的非法历史元数据。
        evidence.__dict__["source_type"] = "fixture_import"
    elif case == "report_sha_uppercase":
        evidence.report_sha256 = "B" * 64
    elif case == "report_sha_prefixed":
        evidence.report_sha256 = "sha256:" + "b" * 64
    elif case == "report_sha_short":
        evidence.report_sha256 = "b" * 63
    elif case == "report_sha_non_hex":
        evidence.report_sha256 = "g" * 64

    await _insert_voice_config(active, draft=draft)
    await _insert_evidence(evidence)
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows_projection()
    service = _trusted_service(_projected_dimensions(draft))

    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await service.publish(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                confirm_text="CONFIRM",
                change_note=f"拒绝非法证据元数据 {case}",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert exc_info.value.code == VOICE_CAPABILITY_ALL_EVIDENCE_INVALID
        assert any(
            item["field"].endswith(expected_field_suffix)
            for item in exc_info.value.errors
        )
        await session.commit()

    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows_projection() == before_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["missing_evidence", "no_current_dimensions_provider", "valid_evidence"],
)
async def test_validate_and_followup_preview_apply_all_scope_gate_without_mutation(
    case: str,
):
    config = _verified_all_config()
    await _insert_voice_config(config)
    if case != "missing_evidence":
        await _insert_evidence(_evidence_from_config(config))

    if case == "no_current_dimensions_provider":
        service = realtime_voice_config_service
    else:
        service = _trusted_service(_projected_dimensions(config))

    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows_projection()
    before_redis = (deepcopy(fake_redis.values), deepcopy(fake_redis.ttls))
    async with session_factory() as session:
        result = await service.validate_current(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            preview={
                "stage": "friend",
                "candidate_at": "2026-08-30T09:30:00+08:00",
                "jitter_minutes": 0,
            },
            admin_user=await _admin(session, "tech_ops"),
        )
        await session.commit()

    if case == "valid_evidence":
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["followup_preview"]["stage"] == "friend"
    else:
        assert result["valid"] is False
        assert "followup_preview" not in result
        expected_suffix = (
            ".evidence_report_id"
            if case == "missing_evidence"
            else ".effective_scope"
        )
        assert any(
            item["code"]
            in {
                VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE,
            }
            and item["field"].endswith(expected_suffix)
            for item in result["errors"]
        )

    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows_projection() == before_evidence
    assert (fake_redis.values, fake_redis.ttls) == before_redis


@pytest.mark.asyncio
async def test_verified_all_publish_succeeds_only_with_rechecked_evidence_and_dimensions():
    active = _default_config()
    draft = _verified_all_config()
    evidence = _evidence_from_config(draft)
    await _insert_voice_config(active, draft=draft, draft_revision=3)
    await _insert_evidence(evidence)
    before_evidence = await _evidence_rows_projection()
    seen: list[tuple[str, dict]] = []

    async def current_dimensions_provider(capability_key: str, s2s: dict):
        seen.append((capability_key, deepcopy(s2s)))
        return _projected_dimensions(draft)

    service = RealtimeVoiceConfigService(
        current_dimensions_provider=current_dimensions_provider
    )
    async with session_factory() as session:
        result = await service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="证据重查通过",
            admin_user=await _admin(session, "tech_ops"),
        )

    assert result["version"] == 2
    assert seen == [(CAPABILITY_KEY, draft["s2s"])]
    active_payload = json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"])
    assert active_payload["capabilities"][CAPABILITY_KEY]["effective_scope"] == "all"
    assert await _evidence_rows_projection() == before_evidence


@pytest.mark.asyncio
async def test_verified_all_rollback_rechecks_gate_and_keeps_evidence_immutable():
    target = _verified_all_config()
    active = _default_config()
    await _insert_rollback_target(target, active)
    await _insert_evidence(_evidence_from_config(target))
    before_config = await _voice_rows_projection()
    before_evidence = await _evidence_rows_projection()

    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await realtime_voice_config_service.rollback(
                session,
                config_key=VOICE_CALL_CONFIG_KEY,
                version=1,
                confirm_text="CONFIRM",
                change_note="生产单例不得自锚",
                admin_user=await _admin(session, "tech_ops"),
            )
        assert exc_info.value.code == VOICE_CAPABILITY_ALL_EVIDENCE_INVALID
        await session.commit()
    assert await _voice_rows_projection() == before_config
    assert await _evidence_rows_projection() == before_evidence

    service = _trusted_service(_projected_dimensions(target))
    async with session_factory() as session:
        result = await service.rollback(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="可信六维回滚",
            admin_user=await _admin(session, "tech_ops"),
        )
    assert result["version"] == 3
    assert json.loads(fake_redis.values[f"active_config:{VOICE_CALL_CONFIG_KEY}"])[
        "capabilities"
    ][CAPABILITY_KEY]["effective_scope"] == "all"
    assert await _evidence_rows_projection() == before_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["unverified", "stale"])
async def test_internal_force_test_writes_only_draft_increments_revision_and_redacts_audit(
    status: str,
):
    active = _default_config()
    if status == "stale":
        active = _trusted_projection(active, "stale", forced=False)
    existing_draft = deepcopy(active)
    existing_draft["quota"]["daily_free_seconds"] += 1
    await _insert_voice_config(active, draft=existing_draft, draft_revision=4)
    before_active = canonical_json(active)

    async with session_factory() as session:
        result = await realtime_voice_config_service.force_capability_test(
            session,
            capability_key=CAPABILITY_KEY,
            effective_scope="test",
            confirm_text="CONFIRM",
            reason=SECRET_SENTINEL,
            admin_user=await _admin(session, "super_admin"),
        )
        await session.commit()

    assert result["draft_revision"] == 5
    assert SECRET_SENTINEL not in json.dumps(result, ensure_ascii=False)
    rows = await _voice_rows_projection()
    active_row = next(row for row in rows if row[4] is True)
    draft_row = next(row for row in rows if row[5] is True)
    assert active_row[1] == before_active
    assert draft_row[2] == 0
    assert draft_row[3] == 5
    draft_payload = json.loads(draft_row[1])
    forced = draft_payload["capabilities"][CAPABILITY_KEY]
    assert forced["verification_status"] == status
    assert forced["enabled"] is True
    assert forced["forced_enabled"] is True
    assert forced["effective_scope"] == "test"

    logs = await _operation_logs()
    assert len(logs) == 1
    assert logs[0].action == "force_enable"
    serialized = json.dumps(
        [logs[0].target_description, logs[0].before_value, logs[0].after_value],
        ensure_ascii=False,
    )
    assert SECRET_SENTINEL not in serialized
    assert "DOUBAO_S2S_ACCESS_KEY" not in serialized
    assert json.loads(logs[0].after_value)["result"] == "success"
    assert json.loads(logs[0].after_value)["change_note"]["length"] == len(
        SECRET_SENTINEL
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("role", VOICE_CAPABILITY_FORCE_FORBIDDEN),
        ("confirm", VOICE_CAPABILITY_FORCE_CONFIRM_INVALID),
        ("reason", VOICE_CAPABILITY_FORCE_REASON_REQUIRED),
        ("test_users", VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED),
        ("failed", VOICE_CAPABILITY_FORCE_STATUS_INVALID),
        ("verified", VOICE_CAPABILITY_FORCE_STATUS_INVALID),
        ("all", VOICE_CAPABILITY_FORCE_SCOPE_INVALID),
    ],
)
async def test_internal_force_negative_cases_audit_and_leave_config_unchanged(
    case: str,
    expected_code: str,
):
    config = _default_config(test_user_ids=[] if case == "test_users" else [101])
    if case == "failed":
        config = _trusted_projection(config, "failed", forced=False)
    elif case == "verified":
        config = _trusted_projection(config, "verified", forced=False)
    await _insert_voice_config(config)
    before = await _voice_rows_projection()

    role = "tech_ops" if case == "role" else "super_admin"
    confirm_text = "confirm" if case == "confirm" else "CONFIRM"
    reason = "   " if case == "reason" else SECRET_SENTINEL
    scope = "all" if case == "all" else "test"
    async with session_factory() as session:
        with pytest.raises(VoiceConfigError) as exc_info:
            await realtime_voice_config_service.force_capability_test(
                session,
                capability_key=CAPABILITY_KEY,
                effective_scope=scope,
                confirm_text=confirm_text,
                reason=reason,
                admin_user=await _admin(session, role),
            )
        assert exc_info.value.code == expected_code
        await session.commit()

    assert await _voice_rows_projection() == before
    logs = await _operation_logs()
    assert len(logs) == 1
    assert logs[0].action == "force_enable"
    serialized = json.dumps(
        [logs[0].target_description, logs[0].before_value, logs[0].after_value],
        ensure_ascii=False,
    )
    assert SECRET_SENTINEL not in serialized
    assert "DOUBAO_S2S_ACCESS_KEY" not in serialized
    failed_audit = json.loads(logs[0].after_value)
    assert failed_audit["result"] == "failed"
    assert expected_code in failed_audit["failure_category"]


@pytest.mark.asyncio
async def test_redis_restore_failure_log_never_contains_exception_secret(
    monkeypatch,
    caplog,
):
    restore_secret = f"redis-restore-{SECRET_SENTINEL}"

    class RestoreFailureRedis:
        async def get(self, _key: str):
            return "safe-snapshot"

        async def ttl(self, _key: str):
            return 60

        async def setex(self, _key: str, _ttl: int, _value: str):
            raise RuntimeError(restore_secret)

    async def redis_provider():
        return RestoreFailureRedis()

    async def failing_operation():
        raise RuntimeError("primary publish failure")

    monkeypatch.setattr(voice_config_service_module, "get_redis", redis_provider)
    caplog.set_level("ERROR", logger=voice_config_service_module.__name__)
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="primary publish failure"):
            await _execute_publish_with_compensation(
                session,
                VOICE_CALL_CONFIG_KEY,
                failing_operation,
            )

    assert "语音配置发布补偿 Redis 失败" in caplog.text
    assert restore_secret not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
