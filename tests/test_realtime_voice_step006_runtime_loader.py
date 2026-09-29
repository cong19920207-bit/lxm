# -*- coding: utf-8 -*-
"""实时语音 P1 M1 STEP-006A 运行时 loader/快照专项验收。"""

from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.constants.realtime_voice_config import (
    CRISIS_KEYWORDS_CONFIG_KEY,
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
    VOICE_CAPABILITY_KEYS,
    build_canonical_voice_seed_manifest,
    get_default_voice_call_config,
    get_default_voice_call_script,
)
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.services.realtime_voice_capability_service import (
    EVIDENCE_FINGERPRINT_FIELDS,
    compute_evidence_fingerprint,
)
from backend.services.realtime_voice_config_service import (
    VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
    canonical_json,
    content_sha256,
    validate_voice_bundle,
)
from backend.services.realtime_voice_runtime_config_service import (
    LoadedVoiceConfig,
    RealtimeVoiceRuntimeConfigService,
    RuntimeConfigResolutionError,
    RuntimeConfigSource,
    VoiceRuntimeBundle,
)


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

PERSONA_VALUE = canonical_json(
    {"schema_version": 1, "system_prompt": "step006 runtime persona anchor"}
)
PERSONA_REF = {
    "config_key": "persona",
    "version": 9,
    "content_sha256": "sha256:"
    + hashlib.sha256(PERSONA_VALUE.encode("utf-8")).hexdigest(),
}
LOG_SENTINEL = "STEP006-SENSITIVE-EXCEPTION-SENTINEL"
PUBLISHED_AT = datetime(2026, 8, 31, 9, 30, 0)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.get_calls: list[str] = []
        self.fail_all = False
        self.fail_keys: set[str] = set()

    async def get(self, key: str):
        self.get_calls.append(key)
        if self.fail_all or key in self.fail_keys:
            raise RuntimeError(LOG_SENTINEL)
        return self.values.get(key)


class BrokenSessionFactory:
    def __call__(self):
        raise RuntimeError(LOG_SENTINEL)


class FailSecondSessionFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError(LOG_SENTINEL)
        return session_factory()


fake_redis = FakeRedis()


async def redis_provider():
    return fake_redis


def service(*, broken_mysql: bool = False) -> RealtimeVoiceRuntimeConfigService:
    return RealtimeVoiceRuntimeConfigService(
        redis_provider=redis_provider,
        session_factory=BrokenSessionFactory() if broken_mysql else session_factory,
    )


def manifest() -> dict[str, dict]:
    return build_canonical_voice_seed_manifest(PERSONA_REF)


def cache_key(config_key: str) -> str:
    return f"active_config:{config_key}"


async def replace_active_rows(
    values: dict[str, tuple[object, int]],
) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(AdminConfig).where(
                AdminConfig.config_key.in_(
                    (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY)
                )
            )
        )
        for key, (value, version) in values.items():
            encoded = value if isinstance(value, str) else canonical_json(value)
            session.add(
                AdminConfig(
                    config_key=key,
                    config_value=encoded,
                    version=version,
                    is_active=True,
                    is_draft=False,
                    updated_by="step006-runtime-test",
                    updated_at=PUBLISHED_AT,
                )
            )
        await session.commit()


async def replace_persona_rows(
    rows: list[tuple[str, int, bool]],
) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(AdminConfig).where(AdminConfig.config_key == "persona")
        )
        for value, version, is_active in rows:
            session.add(
                AdminConfig(
                    config_key="persona",
                    config_value=value,
                    version=version,
                    is_active=is_active,
                    is_draft=False,
                    updated_by="step006-runtime-test",
                    updated_at=PUBLISHED_AT,
                )
            )
        await session.commit()


async def insert_evidence(
    projected_capability_key: str,
    capability: dict,
    **overrides,
) -> None:
    dimensions = {
        field_name: capability[field_name]
        for field_name in EVIDENCE_FINGERPRINT_FIELDS
    }
    verified_at = datetime.fromisoformat(capability["verified_at"])
    expires_at = datetime.fromisoformat(capability["expires_at"])
    values = {
        "evidence_report_id": capability["evidence_report_id"],
        "evidence_run_id": "22222222-2222-4222-8222-222222222222",
        "capability_key": projected_capability_key,
        "verification_result": "passed",
        "source_type": "admin_capability_test",
        **dimensions,
        "evidence_fingerprint": capability["evidence_fingerprint"],
        "evidence_payload": {"events": [{"result": "passed"}]},
        "report_sha256": "b" * 64,
        "tested_at": verified_at - timedelta(minutes=1),
        "verified_at": verified_at,
        "evidence_ttl_days_snapshot": capability["evidence_ttl_days"],
        "expires_at": expires_at,
        "operator_id": 42,
        "created_at": verified_at,
    }
    values.update(overrides)
    async with session_factory() as session:
        session.add(VoiceCapabilityEvidence(**values))
        await session.commit()


async def insert_force_source(
    config: dict,
    *,
    capability_key: str | None = None,
    draft_revision: int = 4,
    anchor_overrides: dict | None = None,
    projection_overrides: dict | None = None,
) -> dict:
    """写入与公开 force-test 相同的不可变成功审计锚。"""

    selected_key = capability_key or VOICE_CAPABILITY_KEYS[0]
    forced_at = datetime.now(timezone.utc).replace(microsecond=0)
    reason = "STEP006 runtime force source"
    anchor = {
        "source": "admin_force_test",
        "capability_key": selected_key,
        "draft_revision": draft_revision,
        "config_content_sha256": content_sha256(config),
        "operator_id": 42,
        "forced_at": forced_at.isoformat().replace("+00:00", "Z"),
        "reason_length": len(reason),
        "reason_sha256": "sha256:"
        + hashlib.sha256(reason.encode("utf-8")).hexdigest(),
    }
    anchor.update(anchor_overrides or {})
    projection = {
        "action": "force_enable",
        "config_key": VOICE_CALL_CONFIG_KEY,
        "draft_revision": draft_revision,
        "verification_status": {
            key: item["verification_status"]
            for key, item in config["capabilities"].items()
        },
        "forced_enabled": {
            key: item["forced_enabled"]
            for key, item in config["capabilities"].items()
        },
        "effective_scope": {
            key: item["effective_scope"]
            for key, item in config["capabilities"].items()
        },
        "change_note": {
            "present": True,
            "length": len(reason),
            "sha256": "sha256:"
            + hashlib.sha256(reason.encode("utf-8")).hexdigest(),
        },
        "result": "success",
        "content_sha256": content_sha256(config),
        "force_source": anchor,
    }
    projection.update(projection_overrides or {})
    async with session_factory() as session:
        session.add(
            AdminOperationLog(
                admin_user_id=42,
                admin_username="step006-runtime-super-admin",
                module="voice_config",
                action="force_enable",
                target_description=f"强制语音能力进入 test {selected_key}",
                after_value=canonical_json(projection),
                created_at=forced_at.replace(tzinfo=None),
            )
        )
        await session.commit()
    return anchor


def set_cache(config_key: str, value: object) -> None:
    fake_redis.values[cache_key(config_key)] = (
        value if isinstance(value, str) else canonical_json(value)
    )


def enabled_for_all(config: dict) -> dict:
    result = deepcopy(config)
    result["global"]["enabled"] = True
    result["global"]["soft_stop"] = False
    result["global"]["rollout"] = {"mode": "all", "user_ids": []}
    return result


def verified_capability(config: dict, *, now: datetime) -> tuple[dict, dict[str, str]]:
    dimensions = {
        "provider_profile": "doubao-prod-profile",
        "model_version": config["s2s"]["model_version"],
        "protocol_profile": config["s2s"]["protocol_profile"],
        "adapter_version": config["s2s"]["adapter_version"],
        "sdk_version": "doubao-sdk-1.2.3",
        "evidence_suite_version": "voice-suite-2026-08-31",
    }
    verified_at = now - timedelta(days=1)
    capability = deepcopy(config["capabilities"][VOICE_CAPABILITY_KEYS[0]])
    capability.update(
        {
            "verification_status": "verified",
            "enabled": True,
            "forced_enabled": False,
            "effective_scope": "all",
            **dimensions,
            "evidence_fingerprint": compute_evidence_fingerprint(dimensions),
            "evidence_ttl_days": 30,
            "verified_at": verified_at.isoformat(),
            "expires_at": (verified_at + timedelta(days=30)).isoformat(),
            "evidence_report_id": "report-step006-runtime-001",
            "last_test_result": "passed",
        }
    )
    return capability, dimensions


@pytest_asyncio.fixture(autouse=True)
async def database():
    fake_redis.values.clear()
    fake_redis.get_calls.clear()
    fake_redis.fail_all = False
    fake_redis.fail_keys.clear()
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AdminConfig.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: VoiceCapabilityEvidence.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: AdminOperationLog.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )
    async with session_factory() as session:
        await session.execute(delete(AdminConfig))
        session.add(AdminConfig(config_key="voice_call_master_switch", config_value='{"enabled":true}',
            version=1, is_active=True, is_draft=False, updated_at=PUBLISHED_AT))
        session.add(
            AdminConfig(
                config_key="persona",
                config_value=PERSONA_VALUE,
                version=PERSONA_REF["version"],
                is_active=True,
                is_draft=False,
                updated_by="step006-runtime-test",
                updated_at=PUBLISHED_AT,
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AdminOperationLog.__table__.drop(
                sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: VoiceCapabilityEvidence.__table__.drop(
                sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: AdminConfig.__table__.drop(
                sync_connection,
                checkfirst=True,
            )
        )


@pytest.mark.asyncio
async def test_missing_two_keys_uses_whole_canonical_fallback_without_reopening_capabilities():
    runtime = await service().load_bundle(
        fallback_persona_ref={
            "config_key": "persona",
            "version": 999,
            "content_sha256": "sha256:" + "b" * 64,
        }
    )

    assert runtime.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.config.version == runtime.script.version == 0
    assert runtime.config.technical_fallback is True
    assert runtime.script.technical_fallback is True

    # 保留唯一 canonical 的 false；AC77 通过 provenance 消歧，不篡改默认值。
    assert runtime.config.payload["global"]["enabled"] is False
    assert runtime.should_block_new_call(user_id=123) is False
    assert runtime.config.mutable_payload() == get_default_voice_call_config(PERSONA_REF)
    assert runtime.script.mutable_payload() == get_default_voice_call_script()

    assert set(runtime.config.payload["capabilities"]) == set(VOICE_CAPABILITY_KEYS)
    for capability in runtime.config.payload["capabilities"].values():
        assert capability["verification_status"] == "unverified"
        assert capability["enabled"] is False
        assert capability["forced_enabled"] is False
        assert capability["effective_scope"] == "off"
    snapshot = runtime.build_snapshot()
    assert snapshot.config_snapshot["config_published_at"] is None
    assert snapshot.config_snapshot["script_published_at"] is None


@pytest.mark.asyncio
async def test_config_fallback_refuses_to_invent_persona_reference():
    await replace_persona_rows([])
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        await service().load_bundle()


@pytest.mark.asyncio
async def test_config_fallback_accepts_external_ref_only_when_existing_persona_hash_matches():
    historical_value = canonical_json(
        {"schema_version": 1, "system_prompt": "retained persona version"}
    )
    historical_ref = {
        "config_key": "persona",
        "version": 4,
        "content_sha256": "sha256:"
        + hashlib.sha256(historical_value.encode("utf-8")).hexdigest(),
    }
    await replace_persona_rows([(historical_value, 4, False)])

    runtime = await service().load_bundle(fallback_persona_ref=historical_ref)

    assert runtime.config.payload["persona_ref"] == historical_ref
    runtime.build_snapshot()

    bad_ref = {**historical_ref, "content_sha256": "sha256:" + "c" * 64}
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        await service().load_bundle(fallback_persona_ref=bad_ref)


@pytest.mark.asyncio
async def test_config_fallback_accepts_exact_published_voice_history_persona_anchor():
    historical_ref = {
        "config_key": "persona",
        "version": 2,
        "content_sha256": "sha256:" + "d" * 64,
    }
    retained_value = canonical_json(
        {"schema_version": 1, "system_prompt": "newer retained persona"}
    )
    await replace_persona_rows([(retained_value, 5, False)])
    async with session_factory() as session:
        session.add(
            AdminConfig(
                config_key=VOICE_CALL_CONFIG_KEY,
                config_value=canonical_json(get_default_voice_call_config(historical_ref)),
                version=3,
                is_active=False,
                is_draft=False,
                updated_by="step006-runtime-test",
                updated_at=PUBLISHED_AT,
            )
        )
        await session.commit()

    runtime = await service().load_bundle(fallback_persona_ref=historical_ref)

    assert runtime.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.config.payload["persona_ref"] == historical_ref
    runtime.build_snapshot()


@pytest.mark.asyncio
async def test_config_fallback_rejects_format_only_external_persona_ref():
    await replace_persona_rows([])
    format_only = {
        "config_key": "persona",
        "version": 88,
        "content_sha256": "sha256:" + "e" * 64,
    }
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        await service().load_bundle(fallback_persona_ref=format_only)


@pytest.mark.asyncio
async def test_script_only_fallback_does_not_require_persona_reference():
    values = manifest()
    await replace_active_rows({VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 3)})
    set_cache(VOICE_CALL_CONFIG_KEY, values[VOICE_CALL_CONFIG_KEY])

    runtime = await service().load_bundle()

    assert runtime.config.source is RuntimeConfigSource.REDIS
    assert runtime.config.version == 3
    assert runtime.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.script.version == 0


@pytest.mark.asyncio
async def test_matching_redis_and_mysql_use_cache_payload_with_mysql_version_anchor():
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 7),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 4),
        }
    )
    for key, payload in values.items():
        set_cache(key, payload)

    runtime = await service().load_bundle()

    assert fake_redis.get_calls[:2] == [
        cache_key(VOICE_CALL_CONFIG_KEY),
        cache_key(VOICE_CALL_SCRIPT_KEY),
    ]
    assert runtime.config.source is RuntimeConfigSource.REDIS
    assert runtime.script.source is RuntimeConfigSource.REDIS
    assert runtime.config.version == 7
    assert runtime.script.version == 4
    # 成功读取的 active false 是显式发布意图，必须优先于 AC77。
    assert runtime.config.technical_fallback is False
    assert runtime.should_block_new_call(user_id=123) is True


@pytest.mark.asyncio
async def test_bad_redis_falls_back_to_valid_mysql_whole_payload():
    values = manifest()
    live_config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (live_config, 11),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 6),
        }
    )
    set_cache(VOICE_CALL_CONFIG_KEY, "{not-json")
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])

    runtime = await service().load_bundle()

    assert runtime.config.source is RuntimeConfigSource.MYSQL
    assert runtime.config.version == 11
    assert runtime.config.mutable_payload() == live_config
    assert runtime.should_block_new_call(user_id=123) is False


@pytest.mark.asyncio
async def test_snapshot_rejects_normal_published_config_with_unanchored_persona_ref():
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["persona_ref"] = {
        "config_key": "persona",
        "version": 99,
        "content_sha256": "sha256:" + "9" * 64,
    }
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 11),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 11),
        }
    )

    bundle = await service().load_bundle()
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        bundle.build_snapshot()


@pytest.mark.asyncio
async def test_snapshot_accepts_normal_config_with_matching_retained_persona_anchor():
    values = manifest()
    retained_value = canonical_json(
        {"schema_version": 1, "system_prompt": "normal retained persona"}
    )
    retained_ref = {
        "config_key": "persona",
        "version": 4,
        "content_sha256": "sha256:"
        + hashlib.sha256(retained_value.encode("utf-8")).hexdigest(),
    }
    await replace_persona_rows([(retained_value, 4, False)])
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["persona_ref"] = retained_ref
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 11),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 11),
        }
    )

    snapshot = (await service().load_bundle()).build_snapshot()

    assert snapshot.config_snapshot["resolved_config"]["persona_ref"] == retained_ref


@pytest.mark.asyncio
async def test_redis_mysql_hash_mismatch_treats_cache_as_inconsistent_and_uses_mysql_anchor():
    values = manifest()
    cached_config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    mysql_config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (mysql_config, 12),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 5),
        }
    )
    set_cache(VOICE_CALL_CONFIG_KEY, cached_config)
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])

    runtime = await service().load_bundle()

    assert runtime.config.source is RuntimeConfigSource.MYSQL
    assert runtime.config.version == 12
    assert runtime.config.published_at == PUBLISHED_AT
    assert runtime.config.mutable_payload() == mysql_config
    assert "redis_mysql_hash_mismatch" in runtime.config.diagnostics


@pytest.mark.asyncio
async def test_valid_published_maintenance_mode_blocks_new_calls():
    values = manifest()
    config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["maintenance_mode"] = True
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 4),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 4),
        }
    )

    runtime = await service().load_bundle()

    assert runtime.config.technical_fallback is False
    assert runtime.should_block_new_call(user_id=123) is True


@pytest.mark.asyncio
async def test_valid_redis_cannot_claim_publish_intent_when_mysql_is_unavailable():
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["enabled"] = True
    config["global"]["soft_stop"] = True
    config["global"]["rollout"] = {"mode": "all", "user_ids": []}
    set_cache(VOICE_CALL_CONFIG_KEY, config)
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])

    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        await service(broken_mysql=True).load_bundle(
            fallback_persona_ref=PERSONA_REF
        )


@pytest.mark.asyncio
async def test_valid_redis_with_missing_db_active_rows_uses_canonical_fallback_not_version_zero():
    values = manifest()
    cached_config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    cached_config["global"]["soft_stop"] = True
    set_cache(VOICE_CALL_CONFIG_KEY, cached_config)
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])

    runtime = await service().load_bundle()

    assert runtime.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.config.version == runtime.script.version == 0
    assert runtime.config.technical_fallback is True
    assert runtime.config.payload["global"]["soft_stop"] is False
    assert runtime.should_block_new_call(user_id=123) is False


@pytest.mark.asyncio
async def test_valid_published_allowlist_is_enforced_but_technical_fallback_allowlist_is_not():
    values = manifest()
    published = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    published["global"]["enabled"] = True
    published["global"]["rollout"] = {"mode": "allowlist", "user_ids": [7]}
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (published, 2),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 2),
        }
    )

    explicit = await service().load_bundle()
    assert explicit.should_block_new_call(user_id=7) is False
    assert explicit.should_block_new_call(user_id=8) is True
    assert explicit.should_block_new_call(user_id=None) is True

    await replace_active_rows({})
    fallback = await service().load_bundle(fallback_persona_ref=PERSONA_REF)
    assert fallback.config.payload["global"]["rollout"]["user_ids"] == ()
    assert fallback.should_block_new_call(user_id=8) is False


def invalid_config_cases() -> list[tuple[str, object]]:
    values = manifest()

    unknown_schema = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    unknown_schema["schema_version"] = 999

    missing_section = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    missing_section.pop("quota")

    p0_field = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    p0_field["preamble_memory_doc_ids"] = ["legacy-id"]

    mock_field = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    mock_field["s2s"]["mock_s2s"] = True

    weak_network_field = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    weak_network_field["s2s"]["weak_network_profile"] = "bad-network"

    secret_value = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    secret_value["voice"]["tone_instruction"] = "step006-secret-SENTINEL-value"

    capability_extra = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability_extra["capabilities"][VOICE_CAPABILITY_KEYS[0]]["mock_s2s"] = True

    capability_secret = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability_secret["capabilities"][VOICE_CAPABILITY_KEYS[0]][
        "provider_profile"
    ] = "step006-secret-SENTINEL-value"

    return [
        ("bad_json", "{bad-json"),
        ("unknown_schema", unknown_schema),
        ("missing_section", missing_section),
        ("p0_field", p0_field),
        ("mock_field", mock_field),
        ("weak_network_field", weak_network_field),
        ("secret_value", secret_value),
        ("capability_extra", capability_extra),
        ("capability_secret", capability_secret),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("_case", "invalid_value"), invalid_config_cases())
async def test_invalid_config_never_field_merges_and_falls_back_as_a_whole(
    monkeypatch,
    _case: str,
    invalid_value: object,
):
    monkeypatch.setenv("STEP006_RUNTIME_SECRET", "step006-secret-SENTINEL-value")
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (invalid_value, 8),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 8),
        }
    )
    set_cache(VOICE_CALL_CONFIG_KEY, invalid_value)
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])

    runtime = await service().load_bundle(fallback_persona_ref=PERSONA_REF)

    assert runtime.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.config.mutable_payload() == get_default_voice_call_config(PERSONA_REF)
    serialized = canonical_json(runtime.config.mutable_payload())
    assert "legacy-id" not in serialized
    assert "mock_s2s" not in serialized
    assert "weak_network_profile" not in serialized
    assert "step006-secret-SENTINEL-value" not in serialized


@pytest.mark.asyncio
async def test_invalid_script_falls_back_as_a_whole_without_touching_valid_config():
    values = manifest()
    live_config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    invalid_script = deepcopy(values[VOICE_CALL_SCRIPT_KEY])
    invalid_script["call_answer"].pop("max_wait_seconds")
    invalid_script["followup"]["missed_explanation_template"] = "不得保留的部分值"
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (live_config, 3),
            VOICE_CALL_SCRIPT_KEY: (invalid_script, 4),
        }
    )

    runtime = await service().load_bundle()

    assert runtime.config.source is RuntimeConfigSource.MYSQL
    assert runtime.config.mutable_payload() == live_config
    assert runtime.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert runtime.script.mutable_payload() == get_default_voice_call_script()
    assert "不得保留的部分值" not in canonical_json(runtime.script.mutable_payload())


@pytest.mark.asyncio
async def test_trusted_runtime_consumes_verified_projection_without_opening_management_write():
    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, dimensions = verified_capability(config, now=now)
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability

    management_issues = validate_voice_bundle(VOICE_CALL_CONFIG_KEY, config)
    assert any(
        issue["code"] == VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN
        for issue in management_issues
    )
    await insert_evidence(VOICE_CAPABILITY_KEYS[0], capability)
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 5),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 5),
        }
    )

    bundle = await service().load_bundle()
    assert bundle.config.payload["capabilities"][VOICE_CAPABILITY_KEYS[0]][
        "verification_status"
    ] == "verified"

    snapshot = bundle.build_snapshot(
        current_capability_dimensions={VOICE_CAPABILITY_KEYS[0]: dimensions},
        now=now,
    )
    projected = snapshot.capability_snapshot[VOICE_CAPABILITY_KEYS[0]]
    assert projected["verification_status"] == "verified"
    assert projected["enabled"] is True
    assert projected["effective_scope"] == "all"
    assert snapshot.config_snapshot["config_content_sha256"] == content_sha256(config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mismatch",
    [
        "missing",
        "failed_result",
        "wrong_capability",
        "dimension",
        "fingerprint",
        "ttl",
        "verified_at",
        "expires_at",
        "future_time",
        "last_test_result",
    ],
)
async def test_verified_all_requires_matching_passed_mysql_evidence_anchor(
    mismatch: str,
):
    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, dimensions = verified_capability(config, now=now)
    if mismatch == "last_test_result":
        capability["last_test_result"] = "failed"
    elif mismatch == "future_time":
        future_verified_at = now + timedelta(hours=1)
        capability["verified_at"] = future_verified_at.isoformat()
        capability["expires_at"] = (
            future_verified_at + timedelta(days=30)
        ).isoformat()
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability

    if mismatch != "missing":
        overrides: dict[str, object] = {}
        if mismatch == "failed_result":
            overrides["verification_result"] = "failed"
        elif mismatch == "wrong_capability":
            overrides["capability_key"] = VOICE_CAPABILITY_KEYS[1]
        elif mismatch == "dimension":
            overrides["provider_profile"] = "different-provider-profile"
        elif mismatch == "fingerprint":
            overrides["evidence_fingerprint"] = "c" * 64
        elif mismatch == "ttl":
            overrides["evidence_ttl_days_snapshot"] = 29
        elif mismatch == "verified_at":
            overrides["verified_at"] = now - timedelta(hours=23)
        elif mismatch == "expires_at":
            overrides["expires_at"] = now + timedelta(days=29, minutes=1)
        await insert_evidence(
            VOICE_CAPABILITY_KEYS[0],
            capability,
            **overrides,
        )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 5),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 5),
        }
    )

    projected = (await service().load_bundle()).build_snapshot(
        current_capability_dimensions={VOICE_CAPABILITY_KEYS[0]: dimensions},
        now=now,
    ).capability_snapshot[VOICE_CAPABILITY_KEYS[0]]

    assert projected["verification_status"] == "stale"
    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
async def test_verified_projection_fails_closed_without_all_six_live_dimensions():
    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, _dimensions = verified_capability(config, now=now)
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability
    await insert_evidence(VOICE_CAPABILITY_KEYS[0], capability)
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 5),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 5),
        }
    )

    projected = (await service().load_bundle()).build_snapshot(now=now).capability_snapshot[
        VOICE_CAPABILITY_KEYS[0]
    ]

    assert projected["verification_status"] == "stale"
    assert projected["enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_dimension", EVIDENCE_FINGERPRINT_FIELDS)
async def test_snapshot_marks_verified_projection_stale_for_each_dimension_change(
    changed_dimension: str,
):
    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, dimensions = verified_capability(config, now=now)
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability
    await insert_evidence(VOICE_CAPABILITY_KEYS[0], capability)
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 6),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 6),
        }
    )
    current = deepcopy(dimensions)
    current[changed_dimension] = current[changed_dimension] + "-changed"

    snapshot = (await service().load_bundle()).build_snapshot(
        current_capability_dimensions={VOICE_CAPABILITY_KEYS[0]: current},
        now=now,
    )

    projected = snapshot.capability_snapshot[VOICE_CAPABILITY_KEYS[0]]
    assert projected["verification_status"] == "stale"
    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
async def test_snapshot_marks_verified_projection_stale_when_ttl_projection_changes():
    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, dimensions = verified_capability(config, now=now)
    capability["evidence_ttl_days"] = 31
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability
    await insert_evidence(
        VOICE_CAPABILITY_KEYS[0],
        capability,
        evidence_ttl_days_snapshot=30,
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 7),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 7),
        }
    )

    snapshot = (await service().load_bundle()).build_snapshot(
        current_capability_dimensions={VOICE_CAPABILITY_KEYS[0]: dimensions},
        now=now,
    )

    projected = snapshot.capability_snapshot[VOICE_CAPABILITY_KEYS[0]]
    assert projected["verification_status"] == "stale"
    assert projected["enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["unverified", "failed", "stale"])
async def test_snapshot_forces_every_nonverified_server_projection_off(status: str):
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability = config["capabilities"][VOICE_CAPABILITY_KEYS[0]]
    capability.update(
        {
            "verification_status": status,
            "enabled": True,
            "forced_enabled": True,
            "effective_scope": "all",
        }
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 8),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 8),
        }
    )

    projected = (await service().load_bundle()).build_snapshot().capability_snapshot[
        VOICE_CAPABILITY_KEYS[0]
    ]

    assert projected["verification_status"] == status
    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["unverified", "stale"])
async def test_audited_forced_test_projection_only_applies_to_matching_test_user(
    status: str,
):
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["test_user_ids"] = [7]
    capability = config["capabilities"][VOICE_CAPABILITY_KEYS[0]]
    capability.update(
        {
            "verification_status": status,
            "enabled": True,
            "forced_enabled": True,
            "effective_scope": "test",
        }
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 9),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 9),
        }
    )
    expected_source = await insert_force_source(config)
    bundle = await service().load_bundle()

    matching = bundle.build_snapshot(user_id=7).capability_snapshot[
        VOICE_CAPABILITY_KEYS[0]
    ]
    missing_context = bundle.build_snapshot().capability_snapshot[
        VOICE_CAPABILITY_KEYS[0]
    ]
    other_user = bundle.build_snapshot(user_id=8).capability_snapshot[
        VOICE_CAPABILITY_KEYS[0]
    ]

    assert matching["verification_status"] == status
    assert matching["enabled"] is True
    assert matching["forced_enabled"] is True
    assert matching["effective_scope"] == "test"
    assert dict(matching["force_source"]) == expected_source
    assert "force_source" not in bundle.build_snapshot(
        user_id=7
    ).config_snapshot["resolved_config"]["capabilities"][VOICE_CAPABILITY_KEYS[0]]
    for projected in (missing_context, other_user):
        assert projected["enabled"] is False
        assert projected["forced_enabled"] is False
        assert projected["effective_scope"] == "off"
        assert "force_source" not in projected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("anchor_overrides", "projection_overrides"),
    [
        ({"source": "forged"}, {}),
        ({"capability_key": VOICE_CAPABILITY_KEYS[1]}, {}),
        ({"draft_revision": 99}, {}),
        ({"config_content_sha256": "sha256:" + "f" * 64}, {}),
        ({"operator_id": 99}, {}),
        ({"reason_sha256": "sha256:" + "f" * 64}, {}),
        ({}, {"draft_revision": 99}),
        ({}, {"content_sha256": "sha256:" + "f" * 64}),
    ],
)
async def test_forced_test_requires_complete_log_source_matching_current_content(
    anchor_overrides: dict,
    projection_overrides: dict,
):
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["test_user_ids"] = [7]
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
        {
            "verification_status": "unverified",
            "enabled": True,
            "forced_enabled": True,
            "effective_scope": "test",
        }
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 9),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 9),
        }
    )
    await insert_force_source(
        config,
        anchor_overrides=anchor_overrides,
        projection_overrides=projection_overrides,
    )

    projected = (await service().load_bundle()).build_snapshot(
        user_id=7
    ).capability_snapshot[VOICE_CAPABILITY_KEYS[0]]

    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"
    assert "force_source" not in projected


@pytest.mark.asyncio
async def test_forced_test_without_immutable_source_log_is_always_off():
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["test_user_ids"] = [7]
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
        {
            "verification_status": "unverified",
            "enabled": True,
            "forced_enabled": True,
            "effective_scope": "test",
        }
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 9),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 9),
        }
    )

    projected = (await service().load_bundle()).build_snapshot(
        user_id=7
    ).capability_snapshot[VOICE_CAPABILITY_KEYS[0]]

    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"
    assert "force_source" not in projected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "enabled", "forced_enabled", "scope", "test_user_ids", "user_id"),
    [
        ("failed", True, True, "test", [7], 7),
        ("unverified", False, True, "test", [7], 7),
        ("unverified", True, False, "test", [7], 7),
        ("unverified", True, True, "all", [7], 7),
        ("unverified", True, True, "test", [], 7),
        ("unverified", True, True, "test", [7], 8),
        ("stale", True, True, "all", [7], 7),
    ],
)
async def test_forced_projection_never_bypasses_frozen_test_scope_guards(
    status: str,
    enabled: bool,
    forced_enabled: bool,
    scope: str,
    test_user_ids: list[int],
    user_id: int,
):
    values = manifest()
    config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    config["global"]["test_user_ids"] = test_user_ids
    config["capabilities"][VOICE_CAPABILITY_KEYS[0]].update(
        {
            "verification_status": status,
            "enabled": enabled,
            "forced_enabled": forced_enabled,
            "effective_scope": scope,
        }
    )
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config, 10),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 10),
        }
    )

    projected = (await service().load_bundle()).build_snapshot(
        user_id=user_id
    ).capability_snapshot[VOICE_CAPABILITY_KEYS[0]]

    assert projected["enabled"] is False
    assert projected["forced_enabled"] is False
    assert projected["effective_scope"] == "off"


@pytest.mark.asyncio
async def test_snapshot_is_deeply_immutable_and_new_publish_does_not_mutate_old_call():
    values_v1 = manifest()
    config_v1 = enabled_for_all(values_v1[VOICE_CALL_CONFIG_KEY])
    script_v1 = deepcopy(values_v1[VOICE_CALL_SCRIPT_KEY])
    script_v1["followup"]["missed_explanation_template"] = "V1"
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config_v1, 1),
            VOICE_CALL_SCRIPT_KEY: (script_v1, 1),
        }
    )
    set_cache(VOICE_CALL_CONFIG_KEY, config_v1)
    set_cache(VOICE_CALL_SCRIPT_KEY, script_v1)

    first_bundle = await service().load_bundle()
    first = first_bundle.build_snapshot()
    first_config_json, first_capability_json = first.persistence_values()

    assert set(first.config_snapshot) == {
        "master_switch_enabled",
        "master_switch_version",
        "config_version",        "config_content_sha256",
        "config_schema_version",
        "config_published_at",
        "script_version",
        "script_content_sha256",
        "script_schema_version",
        "script_published_at",
        "resolved_config",
        "resolved_script",
    }
    assert first.config_snapshot["config_version"] == 1
    assert first.config_snapshot["script_version"] == 1
    assert first.config_snapshot["config_content_sha256"] == content_sha256(config_v1)
    assert first.config_snapshot["script_content_sha256"] == content_sha256(script_v1)
    assert first.config_snapshot["config_published_at"] == PUBLISHED_AT.isoformat()
    assert first.config_snapshot["script_published_at"] == PUBLISHED_AT.isoformat()
    assert first_config_json["resolved_config"] == config_v1
    assert first_config_json["resolved_script"] == script_v1
    assert first_capability_json == config_v1["capabilities"]

    with pytest.raises(TypeError):
        first.config_snapshot["config_version"] = 99
    with pytest.raises(TypeError):
        first.config_snapshot["resolved_config"]["global"]["enabled"] = False
    with pytest.raises(TypeError):
        first.capability_snapshot[VOICE_CAPABILITY_KEYS[0]]["enabled"] = True

    # persistence_values 也是深拷贝，调用方修改返回值不会污染锁定快照。
    first_config_json["resolved_config"]["global"]["enabled"] = False
    again_config_json, _ = first.persistence_values()
    assert again_config_json["resolved_config"]["global"]["enabled"] is True

    config_v2 = deepcopy(config_v1)
    config_v2["quota"]["daily_free_seconds"] = 120
    script_v2 = deepcopy(script_v1)
    script_v2["followup"]["missed_explanation_template"] = "V2"
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (config_v2, 2),
            VOICE_CALL_SCRIPT_KEY: (script_v2, 2),
        }
    )
    set_cache(VOICE_CALL_CONFIG_KEY, config_v2)
    set_cache(VOICE_CALL_SCRIPT_KEY, script_v2)

    second = (await service().load_bundle()).build_snapshot()
    second_config_json, _ = second.persistence_values()
    old_config_json, _ = first.persistence_values()

    assert second.config_snapshot["config_version"] == 2
    assert second.config_snapshot["script_version"] == 2
    assert second_config_json["resolved_config"]["quota"]["daily_free_seconds"] == 120
    assert second_config_json["resolved_script"]["followup"]["missed_explanation_template"] == "V2"
    assert old_config_json["config_version"] == 1
    assert old_config_json["resolved_config"]["quota"]["daily_free_seconds"] == 300
    assert old_config_json["resolved_script"]["followup"]["missed_explanation_template"] == "V1"


@pytest.mark.asyncio
async def test_snapshot_defensively_rejects_instance_constructed_with_forbidden_projection():
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 1),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 1),
        }
    )
    bundle = await service().load_bundle()

    # 冻结 payload 本身不可修改；这也证明生产调用不能在 loader 后注入字段。
    with pytest.raises(TypeError):
        bundle.config.payload["mock_s2s"] = True

    # 即使内部调用方绕开 loader 手工构造 LoadedVoiceConfig，快照 builder 也会
    # 再做一次完整 schema 检查，而不是删除单个字段后继续。
    unsafe_payload = bundle.config.mutable_payload()
    unsafe_payload["mock_s2s"] = True
    unsafe_config = LoadedVoiceConfig(
        config_key=VOICE_CALL_CONFIG_KEY,
        version=bundle.config.version,
        schema_version=bundle.config.schema_version,
        content_sha256=content_sha256(unsafe_payload),
        published_at=bundle.config.published_at,
        payload=unsafe_payload,
        source=bundle.config.source,
        technical_fallback=bundle.config.technical_fallback,
    )
    unsafe_bundle = VoiceRuntimeBundle(config=unsafe_config, script=bundle.script)
    with pytest.raises(RuntimeConfigResolutionError, match="拒绝"):
        unsafe_bundle.build_snapshot()


@pytest.mark.asyncio
async def test_snapshot_recomputes_hash_and_rejects_forged_loaded_metadata():
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 4),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 4),
        }
    )
    bundle = await service().load_bundle()
    forged_configs = [
        replace(bundle.config, config_key=VOICE_CALL_SCRIPT_KEY),
        replace(bundle.config, version=-1),
        replace(bundle.config, schema_version=999),
        replace(bundle.config, content_sha256="sha256:" + "f" * 64),
        replace(bundle.config, published_at=None),
        replace(bundle.config, published_at="2026-08-31T09:30:00"),
        replace(bundle.config, source="mysql"),
        replace(bundle.config, technical_fallback=True),
    ]

    for forged in forged_configs:
        with pytest.raises(RuntimeConfigResolutionError, match="拒绝"):
            VoiceRuntimeBundle(config=forged, script=bundle.script).build_snapshot()


@pytest.mark.asyncio
async def test_mysql_query_uses_only_active_non_draft_rows():
    values = manifest()
    active = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    draft = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    draft["global"]["maintenance_message"] = "草稿绝不能进入运行时"
    history = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    history["global"]["maintenance_message"] = "历史绝不能进入运行时"
    async with session_factory() as session:
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(active),
                    version=3,
                    is_active=True,
                    is_draft=False,
                ),
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(draft),
                    version=0,
                    is_active=False,
                    is_draft=True,
                ),
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(history),
                    version=2,
                    is_active=False,
                    is_draft=False,
                ),
                AdminConfig(
                    config_key=VOICE_CALL_SCRIPT_KEY,
                    config_value=canonical_json(values[VOICE_CALL_SCRIPT_KEY]),
                    version=3,
                    is_active=True,
                    is_draft=False,
                ),
            ]
        )
        await session.commit()

    runtime = await service().load_bundle()
    assert runtime.config.version == 3
    assert runtime.config.payload["global"]["maintenance_message"] not in {
        "草稿绝不能进入运行时",
        "历史绝不能进入运行时",
    }


@pytest.mark.asyncio
async def test_crisis_loader_returns_normalized_valid_keywords_without_db_access():
    set_cache(CRISIS_KEYWORDS_CONFIG_KEY, [" 自杀 ", "伤害自己", "自杀"])

    result = await service(broken_mysql=True).load_crisis_keywords()

    assert result.suspected_hit is False
    assert result.failure_reason is None
    assert result.keywords == ("伤害自己", "自杀")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (None, "missing"),
        ("{bad-json", "invalid_json"),
        ({"keywords": ["自杀"]}, "invalid_or_empty"),
        ([], "invalid_or_empty"),
        (["  "], "invalid_or_empty"),
        (["自杀", 1], "invalid_or_empty"),
    ],
)
async def test_crisis_loader_is_fail_closed_for_missing_invalid_or_empty(raw, reason):
    if raw is not None:
        set_cache(CRISIS_KEYWORDS_CONFIG_KEY, raw)

    result = await service().load_crisis_keywords()

    assert result.suspected_hit is True
    assert result.keywords == ()
    assert result.failure_reason == reason


@pytest.mark.asyncio
async def test_crisis_loader_is_fail_closed_for_redis_exception():
    fake_redis.fail_keys.add(cache_key(CRISIS_KEYWORDS_CONFIG_KEY))

    result = await service().load_crisis_keywords()

    assert result.suspected_hit is True
    assert result.keywords == ()
    assert result.failure_reason == "redis_unavailable"


@pytest.mark.asyncio
async def test_dependency_exception_logs_never_expose_exception_text_or_stack(caplog):
    caplog.set_level(
        logging.WARNING,
        logger="backend.services.realtime_voice_runtime_config_service",
    )
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 2),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 2),
        }
    )

    fake_redis.fail_all = True
    from_mysql = await service().load_bundle()
    assert from_mysql.config.source is RuntimeConfigSource.MYSQL

    fake_redis.fail_all = False
    set_cache(VOICE_CALL_CONFIG_KEY, values[VOICE_CALL_CONFIG_KEY])
    set_cache(VOICE_CALL_SCRIPT_KEY, values[VOICE_CALL_SCRIPT_KEY])
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref"):
        await service(broken_mysql=True).load_bundle(
            fallback_persona_ref=PERSONA_REF
        )

    fake_redis.fail_keys.add(cache_key(CRISIS_KEYWORDS_CONFIG_KEY))
    crisis = await service().load_crisis_keywords()
    assert crisis.suspected_hit is True

    now = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    verified_config = deepcopy(values[VOICE_CALL_CONFIG_KEY])
    capability, dimensions = verified_capability(verified_config, now=now)
    verified_config["capabilities"][VOICE_CAPABILITY_KEYS[0]] = capability
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (verified_config, 3),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 3),
        }
    )
    evidence_failure_service = RealtimeVoiceRuntimeConfigService(
        redis_provider=redis_provider,
        session_factory=FailSecondSessionFactory(),
    )
    evidence_failure_bundle = await evidence_failure_service.load_bundle()
    evidence_projection = evidence_failure_bundle.build_snapshot(
        current_capability_dimensions={VOICE_CAPABILITY_KEYS[0]: dimensions},
        now=now,
    ).capability_snapshot[VOICE_CAPABILITY_KEYS[0]]
    assert evidence_projection["verification_status"] == "stale"
    assert evidence_projection["enabled"] is False

    assert LOG_SENTINEL not in caplog.text
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_loader_does_not_write_redis_or_database():
    values = manifest()
    await replace_active_rows(
        {
            VOICE_CALL_CONFIG_KEY: (values[VOICE_CALL_CONFIG_KEY], 1),
            VOICE_CALL_SCRIPT_KEY: (values[VOICE_CALL_SCRIPT_KEY], 1),
        }
    )
    before_redis = dict(fake_redis.values)
    async with session_factory() as session:
        before_rows = (
            await session.execute(select(AdminConfig).order_by(AdminConfig.id.asc()))
        ).scalars().all()
        before_projection = [
            (row.id, row.config_key, row.config_value, row.version, row.is_active, row.is_draft)
            for row in before_rows
        ]

    await service().load_bundle()

    assert fake_redis.values == before_redis
    async with session_factory() as session:
        after_rows = (
            await session.execute(select(AdminConfig).order_by(AdminConfig.id.asc()))
        ).scalars().all()
        after_projection = [
            (row.id, row.config_key, row.config_value, row.version, row.is_active, row.is_draft)
            for row in after_rows
        ]
    assert after_projection == before_projection

@pytest.mark.asyncio
async def test_independent_switch_blocks_even_with_stale_enabled_cache_and_preserves_snapshot():
    values = manifest()
    config = enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    # Historical embedded flag is deliberately opposite to the authoritative switch.
    config['global']['enabled'] = False
    await replace_active_rows({VOICE_CALL_CONFIG_KEY:(config,1),VOICE_CALL_SCRIPT_KEY:(values[VOICE_CALL_SCRIPT_KEY],1)})
    set_cache(VOICE_CALL_CONFIG_KEY,config)
    first = await service().load_bundle(user_id=123)
    assert first.should_block_new_call(123) is False
    snapshot = first.build_snapshot(user_id=123)
    original = snapshot.persistence_values()
    async with session_factory() as db:
        row = (await db.execute(select(AdminConfig).where(AdminConfig.config_key=='voice_call_master_switch'))).scalars().one()
        row.config_value='{"enabled":false}';row.version=2
        await db.commit()
    second = await service().load_bundle(user_id=123)
    assert second.master_switch_enabled is False
    assert second.should_block_new_call(123) is True
    assert first.should_block_new_call(123) is False
    assert snapshot.persistence_values() == original
    assert original[0]['master_switch_enabled'] is True
    assert original[0]['master_switch_version'] == 1
    assert original[0]['resolved_config']['global']['enabled'] is False
    assert not any('master_switch' in key for key in fake_redis.get_calls)

@pytest.mark.asyncio
async def test_missing_and_unavailable_independent_switch_fail_closed():
    values=manifest();config=enabled_for_all(values[VOICE_CALL_CONFIG_KEY])
    await replace_active_rows({VOICE_CALL_CONFIG_KEY:(config,1),VOICE_CALL_SCRIPT_KEY:(values[VOICE_CALL_SCRIPT_KEY],1)})
    for key,value in values.items():set_cache(key,value)
    async with session_factory() as db:
        await db.execute(delete(AdminConfig).where(AdminConfig.config_key=='voice_call_master_switch'))
        await db.commit()
    assert (await service().load_bundle()).should_block_new_call(123) is True
    with pytest.raises(RuntimeConfigResolutionError):
        await service(broken_mysql=True).load_bundle()
