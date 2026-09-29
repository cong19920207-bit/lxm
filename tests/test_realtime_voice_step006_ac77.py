# -*- coding: utf-8 -*-
"""STEP-006 / AC77 离线发布锚、整 key 回退与独立指标红测。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401  注册完整 ORM
import backend.services.admin_config_service as admin_config_service_module
import backend.services.realtime_voice_config_service as voice_config_service_module
import backend.services.realtime_voice_runtime_config_service as runtime_config_module
from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
    build_canonical_voice_seed_manifest,
    get_default_voice_call_config,
    get_default_voice_call_script,
)
from backend.database import Base
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.services.realtime_voice_config_service import (
    RealtimeVoiceConfigService,
    canonical_json,
    content_sha256,
)
from backend.services.realtime_voice_runtime_config_service import (
    RealtimeVoiceRuntimeConfigService,
    RuntimeConfigResolutionError,
    RuntimeConfigSource,
)


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

PUBLISHED_AT = datetime(2026, 9, 2, 9, 30, 0)
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

ENVELOPE_FIELDS = {
    "envelope_schema_version",
    "config_key",
    "config_version",
    "config_schema_version",
    "config_content_sha256",
    "published_at",
    "config",
}
FALLBACK_METRIC_NAMESPACE = "voice.config.fallback.v1"
FALLBACK_METRIC_TTL_SECONDS = 172800
REDIS_STATUS_VALUES = {
    "ok",
    "missing",
    "invalid_json",
    "invalid_shape",
    "schema_invalid",
    "unavailable",
}
MYSQL_STATUS_VALUES = REDIS_STATUS_VALUES | {
    "invalid_version",
    "invalid_published_at",
}
OUTCOME_VALUES = {"continued", "gate_blocked", "anchor_fail_closed"}
SHARED_METRIC_PREFIXES = (
    "llm_stats",
    "llm_response_times",
    "content_block_count",
)


class FakeRedis:
    """保留真实可观察副作用，同时允许精确故障注入。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, int]] = {}
        self.ttls: dict[str, int] = {}
        self.operations: list[tuple[Any, ...]] = []
        self.fail_delete_keys: set[str] = set()
        self.fail_persistent_set_once = False
        self.fail_metric_writes = False
        self.fail_metric_expire_once = False
        self.block_metric_writes = False

    async def get(self, key: str):
        self.operations.append(("get", key))
        return self.values.get(key)

    async def ttl(self, key: str):
        self.operations.append(("ttl", key))
        exists = key in self.values or key in self.hashes
        return self.ttls.get(key, -2 if not exists else -1)

    async def setex(self, key: str, ttl: int, value: str):
        self.operations.append(("setex", key, ttl, value))
        self.values[key] = value
        self.ttls[key] = ttl
        return True

    async def set(self, key: str, value: str):
        self.operations.append(("set", key, value))
        if self.fail_persistent_set_once:
            self.fail_persistent_set_once = False
            raise RuntimeError("AC77_POST_COMMIT_ANCHOR_WRITE_FAILED")
        self.values[key] = value
        self.ttls[key] = -1
        return True

    async def delete(self, key: str):
        self.operations.append(("delete", key))
        if key in self.fail_delete_keys:
            raise RuntimeError("AC77_ANCHOR_INVALIDATION_FAILED")
        existed = key in self.values or key in self.hashes
        self.values.pop(key, None)
        self.hashes.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)

    async def hincrby(self, key: str, field: str, amount: int):
        self.operations.append(("hincrby", key, field, amount))
        if self.block_metric_writes:
            await asyncio.Event().wait()
        if self.fail_metric_writes:
            raise RuntimeError("AC77_FALLBACK_METRIC_FAILED")
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = bucket.get(field, 0) + amount
        return bucket[field]

    async def expire(self, key: str, ttl: int):
        self.operations.append(("expire", key, ttl))
        if self.fail_metric_expire_once:
            self.fail_metric_expire_once = False
            raise RuntimeError("AC77_FALLBACK_METRIC_EXPIRE_FAILED")
        self.ttls[key] = ttl
        return True

    async def eval(self, script: str, numkeys: int, *args):
        """按生产 Lua helper 的语义模拟单 Redis 原子命令。"""

        assert numkeys == 1
        key = args[0]
        if "AC77_ANCHOR_TAKE_V1" in script:
            max_version = int(args[1])
            self.operations.append(("anchor_take", key, max_version))
            if key in self.fail_delete_keys:
                raise RuntimeError("AC77_ANCHOR_INVALIDATION_FAILED")
            value = self.values.get(key)
            if value is None:
                return [0, None]
            try:
                current_version = json.loads(value)["config_version"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                self.values.pop(key, None)
                self.ttls.pop(key, None)
                return [2, None]
            if type(current_version) is not int:
                self.values.pop(key, None)
                self.ttls.pop(key, None)
                return [2, None]
            if current_version > max_version:
                return [-1, value]
            self.values.pop(key, None)
            self.ttls.pop(key, None)
            return [1, value]
        if "AC77_ANCHOR_SET_IF_NEWER_V1" in script:
            desired_version = int(args[1])
            desired = args[2]
            self.operations.append(("anchor_cas", key, desired_version, desired))
            if self.fail_persistent_set_once:
                self.fail_persistent_set_once = False
                raise RuntimeError("AC77_POST_COMMIT_ANCHOR_WRITE_FAILED")
            current = self.values.get(key)
            if current is not None:
                try:
                    current_version = json.loads(current)["config_version"]
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    return -2
                if type(current_version) is not int:
                    return -2
                if current_version > desired_version:
                    return 0
                if current_version == desired_version:
                    return 2 if current == desired else -3
            self.values[key] = desired
            self.ttls[key] = -1
            return 1
        if "AC77_ANCHOR_RESTORE_IF_ABSENT_V1" in script:
            previous = args[1]
            self.operations.append(("anchor_restore", key, previous))
            if key in self.values:
                return 0
            self.values[key] = previous
            self.ttls[key] = -1
            return 1
        if "AC77_ANCHOR_DELETE_IF_MATCH_V1" in script:
            expected = args[1]
            self.operations.append(("anchor_delete_if_match", key, expected))
            if self.values.get(key) != expected:
                return 0
            self.values.pop(key, None)
            self.ttls.pop(key, None)
            return 1
        if "AC77_FALLBACK_METRIC_INCREMENT_V1" in script:
            field, amount, ttl = args[1], int(args[2]), int(args[3])
            self.operations.append(("metric_atomic_increment", key, field, amount, ttl))
            if self.block_metric_writes:
                await asyncio.Event().wait()
            if self.fail_metric_writes:
                raise RuntimeError("AC77_FALLBACK_METRIC_FAILED")
            if self.fail_metric_expire_once:
                self.fail_metric_expire_once = False
                raise RuntimeError("AC77_FALLBACK_METRIC_EXPIRE_FAILED")
            bucket = self.hashes.setdefault(key, {})
            bucket[field] = bucket.get(field, 0) + amount
            self.ttls[key] = ttl
            return bucket[field]
        raise AssertionError("未知 AC77 Lua helper")


class BrokenSessionFactory:
    def __call__(self):
        raise RuntimeError("AC77_MYSQL_UNAVAILABLE")


class CommitFailingSession:
    """仅让控制面事务 commit 失败，其余真实 SQL/rollback 保持不变。"""

    def __init__(self, delegate: AsyncSession) -> None:
        self._delegate = delegate
        self._failed = False

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)

    async def commit(self) -> None:
        if not self._failed:
            self._failed = True
            raise RuntimeError("AC77_DB_COMMIT_FAILED")
        await self._delegate.commit()


fake_redis = FakeRedis()


async def redis_provider():
    return fake_redis


def _published_envelope_key() -> str:
    """生产实现必须导出内部常量；测试不硬编码 Redis 私有 key。"""

    values = {
        value
        for module in (voice_config_service_module, runtime_config_module)
        if isinstance(
            value := getattr(
                module,
                "VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY",
                None,
            ),
            str,
        )
        and value
    }
    assert len(values) == 1, "缺少唯一的已发布 voice_call_config envelope key 常量"
    return values.pop()


def _enabled_config() -> dict[str, Any]:
    config = build_canonical_voice_seed_manifest(PERSONA_REF)[VOICE_CALL_CONFIG_KEY]
    config["global"].update(
        {
            "enabled": True,
            "maintenance_mode": False,
            "soft_stop": False,
            "rollout": {"mode": "all", "user_ids": []},
            "test_user_ids": [7],
        }
    )
    return config


def _default_script() -> dict[str, Any]:
    return build_canonical_voice_seed_manifest(PERSONA_REF)[VOICE_CALL_SCRIPT_KEY]


async def _admin(session: AsyncSession, role: str = "tech_ops") -> AdminUser:
    return (
        await session.execute(select(AdminUser).where(AdminUser.role == role))
    ).scalars().one()


async def _insert_active_bundle(
    config: dict[str, Any],
    *,
    script: dict[str, Any] | None = None,
    config_version: int = 1,
    script_version: int = 1,
) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(config),
                    version=config_version,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-tech_ops",
                    updated_at=PUBLISHED_AT,
                ),
                AdminConfig(
                    config_key=VOICE_CALL_SCRIPT_KEY,
                    config_value=canonical_json(script or _default_script()),
                    version=script_version,
                    is_draft=False,
                    is_active=True,
                    updated_by="step006-ai_trainer",
                    updated_at=PUBLISHED_AT,
                ),
            ]
        )
        await session.commit()


async def _bootstrap_existing(config: dict[str, Any]) -> dict[str, Any]:
    await _insert_active_bundle(config)
    service = RealtimeVoiceConfigService()
    async with session_factory() as session:
        return await service.initialize_defaults(
            session,
            admin_user=await _admin(session, "super_admin"),
        )


def _read_envelope() -> dict[str, Any]:
    raw = fake_redis.values.get(_published_envelope_key())
    assert isinstance(raw, str), "bootstrap/publish 未写入可信离线 envelope"
    value = json.loads(raw)
    assert isinstance(value, dict)
    return value


def _assert_exact_envelope(
    envelope: dict[str, Any],
    *,
    config: dict[str, Any],
    version: int,
) -> None:
    assert set(envelope) == ENVELOPE_FIELDS
    assert envelope["envelope_schema_version"] == 1
    assert envelope["config_key"] == VOICE_CALL_CONFIG_KEY
    assert envelope["config_version"] == version
    assert envelope["config_schema_version"] == config["schema_version"]
    assert envelope["config_content_sha256"] == content_sha256(config)
    assert envelope["published_at"]
    datetime.fromisoformat(envelope["published_at"].replace("Z", "+00:00"))
    assert envelope["config"] == config
    assert envelope["config"]["persona_ref"] == PERSONA_REF
    assert fake_redis.ttls[_published_envelope_key()] == -1


async def _save_global_draft(next_global: dict[str, Any]) -> None:
    service = RealtimeVoiceConfigService()
    async with session_factory() as session:
        await service.save_draft_section(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="global",
            base_version=1,
            draft_revision=None,
            content=next_global,
            admin_user=await _admin(session),
        )
        await session.commit()


async def _publish_config(
    *,
    session: AsyncSession | CommitFailingSession | None = None,
) -> dict[str, Any]:
    service = RealtimeVoiceConfigService()
    if session is not None:
        return await service.publish(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="AC77 发布锚红测",
            admin_user=await _admin(session),
        )
    async with session_factory() as owned_session:
        return await service.publish(
            owned_session,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="AC77 发布锚红测",
            admin_user=await _admin(owned_session),
        )


def _remove_runtime_payloads(*, invalid: bool = False) -> None:
    for config_key in (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY):
        key = f"active_config:{config_key}"
        if invalid:
            fake_redis.values[key] = "{invalid-json"
            fake_redis.ttls[key] = 3600
        else:
            fake_redis.values.pop(key, None)
            fake_redis.ttls.pop(key, None)


def _runtime_with_broken_mysql() -> RealtimeVoiceRuntimeConfigService:
    return RealtimeVoiceRuntimeConfigService(
        redis_provider=redis_provider,
        session_factory=BrokenSessionFactory(),
    )


def _metric_records() -> list[tuple[str, dict[str, str], int]]:
    records: list[tuple[str, dict[str, str], int]] = []
    for key, bucket in fake_redis.hashes.items():
        if key != FALLBACK_METRIC_NAMESPACE and not key.startswith(
            f"{FALLBACK_METRIC_NAMESPACE}:"
        ):
            continue
        for field, value in bucket.items():
            dimensions = json.loads(field)
            assert isinstance(dimensions, dict)
            records.append((key, dimensions, value))
    return records


def _assert_metric_dimensions(dimensions: dict[str, str]) -> None:
    assert set(dimensions) == {
        "config_key",
        "redis_status",
        "mysql_status",
        "outcome",
    }
    assert dimensions["config_key"] in {
        VOICE_CALL_CONFIG_KEY,
        VOICE_CALL_SCRIPT_KEY,
    }
    assert dimensions["redis_status"] in REDIS_STATUS_VALUES
    assert dimensions["mysql_status"] in MYSQL_STATUS_VALUES
    assert dimensions["outcome"] in OUTCOME_VALUES


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    fake_redis.values.clear()
    fake_redis.hashes.clear()
    fake_redis.ttls.clear()
    fake_redis.operations.clear()
    fake_redis.fail_delete_keys.clear()
    fake_redis.fail_persistent_set_once = False
    fake_redis.fail_metric_writes = False
    fake_redis.fail_metric_expire_once = False
    fake_redis.block_metric_writes = False

    monkeypatch.setattr(admin_config_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(voice_config_service_module, "get_redis", redis_provider)
    monkeypatch.setattr(
        admin_config_service_module,
        "async_session_maker",
        session_factory,
    )
    monkeypatch.setenv("DOUBAO_S2S_ACCESS_KEY", "step006-ac77-test-secret")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role in ("super_admin", "tech_ops", "ai_trainer"):
            session.add(
                AdminUser(
                    username=f"step006-ac77-{role}",
                    password_hash="not-used",
                    role=role,
                    is_active=True,
                    is_locked=False,
                    token_version=0,
                )
            )
        session.add(
            AdminConfig(
                config_key="persona",
                config_value=PERSONA_VALUE,
                version=PERSONA_REF["version"],
                is_draft=False,
                is_active=True,
                updated_by="step006-ac77-super_admin",
                updated_at=PUBLISHED_AT,
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_initialize_defaults_writes_exact_non_expiring_published_envelope():
    service = RealtimeVoiceConfigService()
    async with session_factory() as session:
        result = await service.initialize_defaults(
            session,
            admin_user=await _admin(session, "super_admin"),
        )

    config = build_canonical_voice_seed_manifest(PERSONA_REF)[VOICE_CALL_CONFIG_KEY]
    assert result[VOICE_CALL_CONFIG_KEY]["status"] == "published"
    _assert_exact_envelope(_read_envelope(), config=config, version=1)


@pytest.mark.asyncio
async def test_existing_active_config_is_idempotently_bootstrapped_into_envelope():
    config = _enabled_config()
    result = await _bootstrap_existing(config)

    assert result[VOICE_CALL_CONFIG_KEY] == {"status": "skipped", "version": 1}
    _assert_exact_envelope(_read_envelope(), config=config, version=1)


@pytest.mark.asyncio
async def test_existing_active_bootstrap_write_failure_leaves_no_stale_anchor():
    config = _enabled_config()
    await _insert_active_bundle(config)
    anchor_key = _published_envelope_key()
    fake_redis.values[anchor_key] = canonical_json(
        {
            "envelope_schema_version": 1,
            "config_key": VOICE_CALL_CONFIG_KEY,
            "config_version": 1,
            "config_schema_version": config["schema_version"],
            "config_content_sha256": content_sha256(config),
            "published_at": PUBLISHED_AT.isoformat(),
            "config": config,
        }
    )
    fake_redis.ttls[anchor_key] = -1
    fake_redis.fail_persistent_set_once = True

    service = RealtimeVoiceConfigService()
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="AC77_POST_COMMIT_ANCHOR_WRITE_FAILED"):
            await service.initialize_defaults(
                session,
                admin_user=await _admin(session, "super_admin"),
            )

    assert anchor_key not in fake_redis.values


@pytest.mark.asyncio
async def test_lower_version_anchor_cannot_overwrite_newer_committed_anchor():
    config_v2 = _enabled_config()
    config_v3 = deepcopy(config_v2)
    config_v3["global"]["soft_stop"] = True
    anchor_key = _published_envelope_key()

    await voice_config_service_module._write_published_voice_config_envelope(
        fake_redis,
        config=config_v3,
        version=3,
        published_at="2026-09-02T09:33:00",
    )
    await voice_config_service_module._write_published_voice_config_envelope(
        fake_redis,
        config=config_v2,
        version=2,
        published_at="2026-09-02T09:32:00",
    )

    assert json.loads(fake_redis.values[anchor_key])["config_version"] == 3
    assert json.loads(fake_redis.values[anchor_key])["config"] == config_v3


@pytest.mark.asyncio
async def test_delayed_compensation_cannot_restore_old_anchor_over_newer_version():
    config_v1 = _enabled_config()
    config_v3 = deepcopy(config_v1)
    config_v3["global"]["soft_stop"] = True
    anchor_key = _published_envelope_key()
    await voice_config_service_module._write_published_voice_config_envelope(
        fake_redis,
        config=config_v1,
        version=1,
        published_at="2026-09-02T09:31:00",
    )
    snapshot = await voice_config_service_module._take_published_voice_config_envelope(
        fake_redis,
        max_version=1,
    )
    await voice_config_service_module._write_published_voice_config_envelope(
        fake_redis,
        config=config_v3,
        version=3,
        published_at="2026-09-02T09:33:00",
    )

    await voice_config_service_module._restore_published_voice_config_envelope_if_absent(
        fake_redis,
        snapshot,
    )

    assert json.loads(fake_redis.values[anchor_key])["config_version"] == 3
    assert json.loads(fake_redis.values[anchor_key])["config"] == config_v3


@pytest.mark.asyncio
async def test_publish_invalidates_old_anchor_before_writing_committed_version():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    anchor_key = _published_envelope_key()
    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])
    operation_offset = len(fake_redis.operations)

    published = await _publish_config()

    relevant = [
        operation
        for operation in fake_redis.operations[operation_offset:]
        if len(operation) >= 2 and operation[1] == anchor_key
    ]
    assert [operation[0] for operation in relevant] == ["anchor_take", "anchor_cas"]
    assert published["version"] == 2
    _assert_exact_envelope(_read_envelope(), config=config_v2, version=2)


@pytest.mark.asyncio
async def test_rollback_invalidates_old_anchor_and_publishes_new_version_envelope():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])
    await _publish_config()
    anchor_key = _published_envelope_key()
    operation_offset = len(fake_redis.operations)

    service = RealtimeVoiceConfigService()
    async with session_factory() as session:
        rolled_back = await service.rollback(
            session,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="AC77 回滚锚红测",
            admin_user=await _admin(session),
        )

    relevant = [
        operation
        for operation in fake_redis.operations[operation_offset:]
        if len(operation) >= 2 and operation[1] == anchor_key
    ]
    assert [operation[0] for operation in relevant] == ["anchor_take", "anchor_cas"]
    assert rolled_back["version"] == 3
    _assert_exact_envelope(_read_envelope(), config=config_v1, version=3)


@pytest.mark.asyncio
async def test_commit_failure_restores_previous_published_envelope():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    anchor_key = _published_envelope_key()
    old_envelope = fake_redis.values[anchor_key]
    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])

    async with session_factory() as real_session:
        failing_session = CommitFailingSession(real_session)
        with pytest.raises(RuntimeError, match="AC77_DB_COMMIT_FAILED"):
            await _publish_config(session=failing_session)

    assert fake_redis.values[anchor_key] == old_envelope
    async with session_factory() as session:
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().one()
    assert active.version == 1
    assert json.loads(active.config_value) == config_v1


@pytest.mark.asyncio
async def test_anchor_invalidation_failure_rejects_publish_before_db_change():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    anchor_key = _published_envelope_key()
    old_envelope = fake_redis.values[anchor_key]
    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])
    fake_redis.fail_delete_keys.add(anchor_key)

    with pytest.raises(RuntimeError, match="AC77_ANCHOR_INVALIDATION_FAILED"):
        await _publish_config()

    assert fake_redis.values[anchor_key] == old_envelope
    async with session_factory() as session:
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().one()
    assert active.version == 1


@pytest.mark.asyncio
async def test_post_commit_anchor_write_failure_keeps_new_db_version_but_no_anchor():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    anchor_key = _published_envelope_key()
    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])
    fake_redis.fail_persistent_set_once = True

    with pytest.raises(RuntimeError, match="AC77_POST_COMMIT_ANCHOR_WRITE_FAILED"):
        await _publish_config()

    assert anchor_key not in fake_redis.values
    async with session_factory() as session:
        active = (
            await session.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_active == True,  # noqa: E712
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().one()
    assert active.version == 2
    assert json.loads(active.config_value) == config_v2

    _remove_runtime_payloads()
    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref|envelope|锚"):
        await _runtime_with_broken_mysql().load_bundle(user_id=7)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_raw", [False, True], ids=["missing", "invalid_json"])
async def test_db_unavailable_uses_published_envelope_for_version_zero_canonical_snapshot(
    invalid_raw: bool,
):
    config = _enabled_config()
    await _bootstrap_existing(config)
    _remove_runtime_payloads(invalid=invalid_raw)

    bundle = await _runtime_with_broken_mysql().load_bundle(user_id=7)
    snapshot = bundle.build_snapshot(user_id=7)
    snapshot_values, _ = snapshot.persistence_values()

    assert bundle.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.config.version == bundle.script.version == 0
    assert bundle.config.published_at is bundle.script.published_at is None
    assert bundle.config.mutable_payload() == get_default_voice_call_config(PERSONA_REF)
    assert bundle.script.mutable_payload() == get_default_voice_call_script()
    assert snapshot_values["config_version"] == snapshot_values["script_version"] == 0
    assert snapshot_values["config_published_at"] is None
    assert snapshot_values["script_published_at"] is None
    assert snapshot_values["resolved_config"] == get_default_voice_call_config(PERSONA_REF)
    assert snapshot_values["resolved_script"] == get_default_voice_call_script()
    assert bundle.should_block_new_call(7) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda envelope: envelope.update({"extra": True}),
        lambda envelope: envelope.update({"config_content_sha256": "0" * 64}),
        lambda envelope: envelope.update({"envelope_schema_version": 999}),
        lambda envelope: envelope.update({"config_schema_version": 999}),
        lambda envelope: envelope.pop("published_at"),
        lambda envelope: (
            envelope["config"]["persona_ref"].update(
                {"content_sha256": "sha256:not-a-sha256"}
            ),
            envelope.update(
                {"config_content_sha256": content_sha256(envelope["config"])}
            ),
        ),
    ],
    ids=[
        "extra_key",
        "bad_hash",
        "unknown_envelope_schema",
        "config_schema_mismatch",
        "missing_key",
        "invalid_persona",
    ],
)
async def test_untrusted_envelope_is_rejected_without_field_salvage(mutate):
    await _bootstrap_existing(_enabled_config())
    envelope = _read_envelope()
    mutate(envelope)
    fake_redis.values[_published_envelope_key()] = canonical_json(envelope)
    _remove_runtime_payloads()

    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref|envelope|锚"):
        await _runtime_with_broken_mysql().load_bundle(user_id=7)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "user_id"),
    [
        ("disabled", 7),
        ("maintenance", 7),
        ("soft_stop", 7),
        ("allowlist_miss", 8),
    ],
)
async def test_published_gate_remains_prior_to_canonical_fallback(case: str, user_id: int):
    config = _enabled_config()
    if case == "disabled":
        config["global"]["enabled"] = False
    elif case == "maintenance":
        config["global"]["maintenance_mode"] = True
    elif case == "soft_stop":
        config["global"]["soft_stop"] = True
    else:
        config["global"]["rollout"] = {"mode": "allowlist", "user_ids": [7]}
    await _bootstrap_existing(config)
    _remove_runtime_payloads()

    bundle = await _runtime_with_broken_mysql().load_bundle(user_id=user_id)

    assert bundle.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.config.payload["global"]["enabled"] is False
    assert bundle.should_block_new_call(user_id) is True
    config_metrics = [
        dimensions
        for _, dimensions, _ in _metric_records()
        if dimensions["config_key"] == VOICE_CALL_CONFIG_KEY
    ]
    assert config_metrics == [
        {
            "config_key": VOICE_CALL_CONFIG_KEY,
            "redis_status": "missing",
            "mysql_status": "unavailable",
            "outcome": "gate_blocked",
        }
    ]


@pytest.mark.asyncio
async def test_caller_persona_cannot_replace_missing_mysql_and_published_envelope():
    _remove_runtime_payloads()

    with pytest.raises(RuntimeConfigResolutionError, match="persona_ref|envelope|锚"):
        await _runtime_with_broken_mysql().load_bundle(
            fallback_persona_ref=PERSONA_REF,
            user_id=7,
        )

    records = _metric_records()
    assert len(records) == 1
    key, dimensions, value = records[0]
    assert key.startswith(FALLBACK_METRIC_NAMESPACE)
    assert dimensions == {
        "config_key": VOICE_CALL_CONFIG_KEY,
        "redis_status": "missing",
        "mysql_status": "unavailable",
        "outcome": "anchor_fail_closed",
    }
    assert value == 1


@pytest.mark.asyncio
async def test_new_anchor_changes_new_gate_without_hot_switching_old_snapshot():
    config_v1 = _enabled_config()
    await _bootstrap_existing(config_v1)
    _remove_runtime_payloads()
    first_bundle = await _runtime_with_broken_mysql().load_bundle(user_id=7)
    first_snapshot = first_bundle.build_snapshot(user_id=7)
    first_values = first_snapshot.persistence_values()

    config_v2 = deepcopy(config_v1)
    config_v2["global"]["soft_stop"] = True
    await _save_global_draft(config_v2["global"])
    await _publish_config()
    _remove_runtime_payloads()
    second_bundle = await _runtime_with_broken_mysql().load_bundle(user_id=7)

    assert first_bundle.should_block_new_call(7) is False
    assert second_bundle.should_block_new_call(7) is True
    assert first_snapshot.persistence_values() == first_values


@pytest.mark.asyncio
async def test_each_canonical_fallback_key_increments_one_low_cardinality_counter():
    await _bootstrap_existing(_enabled_config())
    _remove_runtime_payloads()

    await _runtime_with_broken_mysql().load_bundle(user_id=7)

    records = _metric_records()
    assert len(records) == 2
    by_config_key = {
        dimensions["config_key"]: (key, dimensions, value)
        for key, dimensions, value in records
    }
    assert set(by_config_key) == {VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY}
    for key, dimensions, value in by_config_key.values():
        assert key.startswith(FALLBACK_METRIC_NAMESPACE)
        _assert_metric_dimensions(dimensions)
        assert dimensions["redis_status"] == "missing"
        assert dimensions["mysql_status"] == "unavailable"
        assert dimensions["outcome"] == "continued"
        assert value == 1
        assert fake_redis.ttls[key] == FALLBACK_METRIC_TTL_SECONDS

    touched_keys = {
        operation[1]
        for operation in fake_redis.operations
        if len(operation) >= 2 and isinstance(operation[1], str)
    }
    assert not any(
        key.startswith(prefix)
        for key in touched_keys
        for prefix in SHARED_METRIC_PREFIXES
    )


@pytest.mark.asyncio
async def test_one_parse_increments_each_key_once_without_duplicate_source_counts():
    await _bootstrap_existing(_enabled_config())
    _remove_runtime_payloads(invalid=True)

    await _runtime_with_broken_mysql().load_bundle(user_id=7)

    records = _metric_records()
    assert len(records) == 2
    for _, dimensions, value in records:
        assert dimensions["redis_status"] == "invalid_json"
        assert dimensions["mysql_status"] == "unavailable"
        assert value == 1


@pytest.mark.asyncio
async def test_metric_sink_failure_does_not_change_fallback_or_gate_result():
    await _bootstrap_existing(_enabled_config())
    _remove_runtime_payloads()
    fake_redis.fail_metric_writes = True

    bundle = await _runtime_with_broken_mysql().load_bundle(user_id=7)
    snapshot = bundle.build_snapshot(user_id=7)

    assert bundle.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.script.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.should_block_new_call(7) is False
    assert snapshot.config_snapshot["config_version"] == 0
    assert snapshot.config_snapshot["script_version"] == 0
    assert _metric_records() == []


@pytest.mark.asyncio
async def test_metric_atomic_expire_failure_cannot_leave_permanent_counter():
    fake_redis.fail_metric_expire_once = True
    runtime = RealtimeVoiceRuntimeConfigService(
        redis_provider=redis_provider,
        session_factory=BrokenSessionFactory(),
    )

    await runtime._increment_fallback_metric(
        config_key=VOICE_CALL_CONFIG_KEY,
        redis_status="missing",
        mysql_status="unavailable",
        outcome="continued",
    )

    assert not any(
        key.startswith(FALLBACK_METRIC_NAMESPACE)
        and fake_redis.ttls.get(key) != FALLBACK_METRIC_TTL_SECONDS
        for key in fake_redis.hashes
    )


@pytest.mark.asyncio
async def test_blocked_metric_sink_has_short_deadline_and_does_not_block_load():
    await _bootstrap_existing(_enabled_config())
    _remove_runtime_payloads()
    fake_redis.block_metric_writes = True

    bundle = await asyncio.wait_for(
        _runtime_with_broken_mysql().load_bundle(user_id=7),
        timeout=1.0,
    )

    assert bundle.config.source is RuntimeConfigSource.CANONICAL_FALLBACK
    assert bundle.should_block_new_call(7) is False
