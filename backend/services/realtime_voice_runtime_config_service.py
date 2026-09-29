# -*- coding: utf-8 -*-
"""实时语音 STEP-006A 运行时配置读取与不可变快照。

本模块只实现 O-01 开放期间不依赖真实 Provider 证据的运行时底座：

* 两个语音 key 分别按 Redis -> MySQL -> 规范代码默认值解析；
* 任一候选值必须通过完整 STEP-005 schema，绝不按字段拼补；
* 独立总开关只读 MySQL；关闭或状态不可用均阻止新通话；
  旧 ``global.enabled`` 保留在历史整包中，不再控制运行时；
* 快照只包含已冻结的非敏感字段，且在内存中递归不可变；
* 危机关键词独立按 Redis -> 已发布 MySQL 读取，无可信配置时疑似命中。

该模块不提供管理 API，也不会创建/升级 ``verified``；只消费证据服务已经
写入的可信投影，并在通话快照前再次执行失效判定。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from backend.services.realtime_voice_master_switch_service import VoiceMasterSwitchState, parse_master_switch_rows

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_MASTER_SWITCH_KEY,
    VOICE_CALL_SCRIPT_KEY,
    VOICE_CAPABILITY_KEYS,
    VOICE_CONFIG_SCHEMA_VERSION,
    get_default_voice_call_config,
    get_default_voice_call_script,
)
from backend.database import async_session_maker
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.redis_client import get_redis
from backend.services.realtime_voice_crisis_config_service import CrisisConfigReader, CrisisKeywordLoadResult
from backend.services.realtime_voice_capability_service import (
    EVIDENCE_FINGERPRINT_FIELDS,
    CapabilityStateError,
    compute_evidence_fingerprint,
    evidence_expires_at,
    resolve_runtime_capability,
)
from backend.services.realtime_voice_config_service import (
    VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY,
    VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
    canonical_json,
    content_sha256,
    validate_voice_bundle,
)


logger = logging.getLogger(__name__)

# AC77 独立指标只保存冻结的低基数维度，不复用业务缓存或自由异常文本。

_VOICE_KEYS = (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY)
_CACHE_PREFIX = "active_config:"
_PERSONA_CONFIG_KEY = "persona"
_SHA256_HEX_LENGTH = 64
_PUBLISHED_ENVELOPE_SCHEMA_VERSION = 1
_PUBLISHED_ENVELOPE_FIELDS = frozenset(
    {
        "envelope_schema_version",
        "config_key",
        "config_version",
        "config_schema_version",
        "config_content_sha256",
        "published_at",
        "config",
    }
)
_FALLBACK_METRIC_NAMESPACE = "voice.config.fallback.v1"
_FALLBACK_METRIC_TTL_SECONDS = 172800
_FALLBACK_METRIC_DEADLINE_SECONDS = 0.1
_FALLBACK_METRIC_INCREMENT_SCRIPT = """
-- AC77_FALLBACK_METRIC_INCREMENT_V1
local state = {}
local type_reply = redis.call('TYPE', KEYS[1])
local key_type = type(type_reply) == 'table' and type_reply.ok or type_reply
if key_type == 'string' then
  local raw = redis.call('GET', KEYS[1])
  if raw then
    local ok, decoded = pcall(cjson.decode, raw)
    if ok and type(decoded) == 'table' then
      state = decoded
    end
  end
elseif key_type == 'hash' then
  local legacy = redis.call('HGETALL', KEYS[1])
  for index = 1, #legacy, 2 do
    state[legacy[index]] = tonumber(legacy[index + 1]) or 0
  end
end
local value = (tonumber(state[ARGV[1]]) or 0) + tonumber(ARGV[2])
state[ARGV[1]] = value
-- 唯一写命令同时携带 TTL；写失败时不会留下“已计数但无 TTL”的新状态。
redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[3])
return value
"""
_FORCE_SOURCE_FIELDS = frozenset(
    {
        "source",
        "capability_key",
        "draft_revision",
        "config_content_sha256",
        "operator_id",
        "forced_at",
        "reason_length",
        "reason_sha256",
    }
)


def _trusted_runtime_issues(config_key: str, value: Any) -> list[dict[str, Any]]:
    """复用完整 schema，只放行证据服务拥有的只读投影字段。

    管理端 validator 必须继续拒绝管理员手写 ``verified/failed/stale``、
    ``all`` 和证据字段；运行时只过滤这个精确错误码。未知字段、P0/mock、
    弱网字段、Secret、缺字段及其他类型/范围错误仍会整 key 拒绝。
    """

    return [
        issue
        for issue in validate_voice_bundle(config_key, value)
        if issue.get("code") != VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN
    ]


class RuntimeConfigResolutionError(RuntimeError):
    """无法在不伪造权威字段的前提下生成规范运行时配置。"""


class RuntimeConfigSource(str, Enum):
    """仅供服务内部判定配置来源；不会写入 API 或通话快照。"""

    REDIS = "redis"
    MYSQL = "mysql"
    CANONICAL_FALLBACK = "canonical_fallback"


def _deep_freeze(value: Any) -> Any:
    """递归冻结 JSON 值，阻止进行中通话被后来修改热切。"""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(child) for key, child in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _deep_thaw(value: Any) -> Any:
    """把冻结 JSON 转为全新、可持久化的普通 dict/list。"""

    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class LoadedVoiceConfig:
    """单个语音 key 的已解析、不可变运行时值。"""

    config_key: str
    version: int
    schema_version: int
    content_sha256: str
    published_at: datetime | None
    payload: Mapping[str, Any]
    source: RuntimeConfigSource
    technical_fallback: bool
    diagnostics: tuple[str, ...] = ()

    def mutable_payload(self) -> dict[str, Any]:
        return _deep_thaw(self.payload)


def _validate_loaded_metadata(
    loaded: LoadedVoiceConfig,
    *,
    expected_key: str,
) -> dict[str, Any]:
    """验证 loader 元数据与内容自身一致，拒绝手工伪造的快照输入。"""

    payload = loaded.mutable_payload()
    if not isinstance(payload, dict):
        raise RuntimeConfigResolutionError("运行时快照拒绝非对象 payload")
    if loaded.config_key != expected_key:
        raise RuntimeConfigResolutionError("运行时快照拒绝 config_key 元数据不一致")
    if type(loaded.version) is not int or loaded.version < 0:
        raise RuntimeConfigResolutionError("运行时快照拒绝非法 version 元数据")
    if (
        type(loaded.schema_version) is not int
        or loaded.schema_version != VOICE_CONFIG_SCHEMA_VERSION
        or payload.get("schema_version") != loaded.schema_version
    ):
        raise RuntimeConfigResolutionError("运行时快照拒绝 schema_version 元数据不一致")
    if loaded.content_sha256 != content_sha256(payload):
        raise RuntimeConfigResolutionError("运行时快照拒绝 content_sha256 元数据不一致")
    if not isinstance(loaded.source, RuntimeConfigSource):
        raise RuntimeConfigResolutionError("运行时快照拒绝非法 source 元数据")
    if type(loaded.technical_fallback) is not bool:
        raise RuntimeConfigResolutionError("运行时快照拒绝非法 fallback 元数据")

    is_canonical = loaded.source is RuntimeConfigSource.CANONICAL_FALLBACK
    if loaded.technical_fallback is not is_canonical:
        raise RuntimeConfigResolutionError("运行时快照拒绝 source/fallback 元数据矛盾")
    if is_canonical:
        if loaded.version != 0 or loaded.published_at is not None:
            raise RuntimeConfigResolutionError("运行时快照拒绝伪造的回退发布元数据")
        if expected_key == VOICE_CALL_CONFIG_KEY:
            persona_ref = payload.get("persona_ref")
            expected_payload = (
                get_default_voice_call_config(_deep_thaw(persona_ref))
                if isinstance(persona_ref, Mapping)
                else None
            )
        else:
            expected_payload = get_default_voice_call_script()
        if payload != expected_payload:
            raise RuntimeConfigResolutionError("运行时快照拒绝非规范 canonical fallback")
    elif loaded.version < 1:
        raise RuntimeConfigResolutionError("运行时快照拒绝无真实发布版本的非回退元数据")

    if loaded.version == 0:
        if loaded.published_at is not None:
            raise RuntimeConfigResolutionError("运行时快照拒绝无版本却带发布时间")
    elif not isinstance(loaded.published_at, datetime):
        raise RuntimeConfigResolutionError("运行时快照拒绝缺失或非法 published_at")
    return payload


def _published_at_value(loaded: LoadedVoiceConfig) -> str | None:
    return loaded.published_at.isoformat() if loaded.published_at is not None else None


def _missing_current_dimensions() -> dict[str, None]:
    """缺少显式适配器六维时 fail-closed；绝不从配置/证据自我锚定。"""

    return {field_name: None for field_name in EVIDENCE_FINGERPRINT_FIELDS}


def _disabled_capability_projection(
    capability: Mapping[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    projected = _deep_thaw(capability)
    projected["verification_status"] = status
    projected["enabled"] = False
    projected["forced_enabled"] = False
    projected["effective_scope"] = "off"
    return projected


def _scope_capability_for_call(
    original: Mapping[str, Any],
    resolved: Mapping[str, Any],
    *,
    user_id: int | None,
    test_user_ids: list[Any],
    allow_forced_test: bool = True,
) -> dict[str, Any]:
    """应用单次通话的 test 范围，不猜测缺失的用户上下文。"""

    status = resolved.get("verification_status")
    if not isinstance(status, str):  # trusted validator/resolver 的防御分支
        raise RuntimeConfigResolutionError("运行时快照拒绝缺失能力状态")
    is_test_user = (
        bool(test_user_ids)
        and type(user_id) is int
        and user_id in test_user_ids
    )

    # 冻结例外：已审计的强制位只允许 unverified/stale 在 test 用户单次
    # 快照内生效。failed 永远 off；任何非 verified 状态都不得进入 all。
    forced_test = (
        allow_forced_test
        and status in ("unverified", "stale")
        and original.get("enabled") is True
        and original.get("forced_enabled") is True
        and original.get("effective_scope") == "test"
    )
    if forced_test and is_test_user:
        projected = _deep_thaw(resolved)
        projected["enabled"] = True
        projected["forced_enabled"] = True
        projected["effective_scope"] = "test"
        return projected

    if status in ("unverified", "failed", "stale"):
        return _disabled_capability_projection(resolved, status=status)

    # verified/test 也必须按当前通话用户收窄；缺 user_id 或未命中均 off。
    if resolved.get("effective_scope") == "test" and not is_test_user:
        return _disabled_capability_projection(resolved, status=status)
    return _deep_thaw(resolved)


def _parse_projected_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _persona_ref_shape(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or set(value) != {
        "config_key",
        "version",
        "content_sha256",
    }:
        return None
    version = value.get("version")
    digest = value.get("content_sha256")
    if (
        value.get("config_key") != _PERSONA_CONFIG_KEY
        or type(version) is not int
        or version < 1
        or not isinstance(digest, str)
    ):
        return None
    normalized = digest.removeprefix("sha256:")
    if len(normalized) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        return None
    return {
        "config_key": _PERSONA_CONFIG_KEY,
        "version": version,
        "content_sha256": f"sha256:{normalized}",
    }


def _persona_ref_is_anchored(
    persona_ref: Mapping[str, Any],
    *,
    persona_anchors: tuple[Mapping[str, Any], ...],
    voice_persona_anchors: tuple[Mapping[str, Any], ...],
) -> bool:
    normalized_persona_anchors = tuple(
        normalized
        for anchor in persona_anchors
        if (normalized := _persona_ref_shape(anchor)) is not None
    )
    normalized_voice_anchors = tuple(
        normalized
        for anchor in voice_persona_anchors
        if (normalized := _persona_ref_shape(anchor)) is not None
    )
    if persona_ref in normalized_persona_anchors:
        return True
    if not normalized_persona_anchors:
        return False
    retained_min_version = min(
        int(anchor["version"]) for anchor in normalized_persona_anchors
    )
    return (
        int(persona_ref["version"]) < retained_min_version
        and persona_ref in normalized_voice_anchors
    )


@dataclass(frozen=True, slots=True)
class _EvidenceAnchor:
    evidence_report_id: str
    capability_key: str
    verification_result: str
    dimensions: Mapping[str, Any]
    evidence_fingerprint: str
    tested_at: datetime
    verified_at: datetime | None
    evidence_ttl_days_snapshot: int
    expires_at: datetime | None


def _verified_anchor_matches(
    capability_key: str,
    capability: Mapping[str, Any],
    anchor: _EvidenceAnchor | None,
    *,
    now: datetime | None,
) -> bool:
    """核验 verified 投影确实来自同一条 passed 证据记录。"""

    report_id = capability.get("evidence_report_id")
    if (
        anchor is None
        or capability.get("last_test_result") != "passed"
        or not isinstance(report_id, str)
        or report_id != anchor.evidence_report_id
        or anchor.capability_key != capability_key
        or anchor.verification_result != "passed"
    ):
        return False

    projection_dimensions = {
        field_name: capability.get(field_name)
        for field_name in EVIDENCE_FINGERPRINT_FIELDS
    }
    anchor_dimensions = dict(anchor.dimensions)
    if projection_dimensions != anchor_dimensions:
        return False
    try:
        expected_fingerprint = compute_evidence_fingerprint(anchor_dimensions)
    except CapabilityStateError:
        return False
    if (
        anchor.evidence_fingerprint != expected_fingerprint
        or capability.get("evidence_fingerprint") != expected_fingerprint
    ):
        return False

    ttl_days = capability.get("evidence_ttl_days")
    if (
        type(ttl_days) is not int
        or ttl_days != anchor.evidence_ttl_days_snapshot
        or not isinstance(anchor.tested_at, datetime)
        or not isinstance(anchor.verified_at, datetime)
        or not isinstance(anchor.expires_at, datetime)
    ):
        return False
    projected_verified_at = _parse_projected_datetime(capability.get("verified_at"))
    projected_expires_at = _parse_projected_datetime(capability.get("expires_at"))
    if projected_verified_at is None or projected_expires_at is None:
        return False
    if (
        _utc_naive(projected_verified_at) != _utc_naive(anchor.verified_at)
        or _utc_naive(projected_expires_at) != _utc_naive(anchor.expires_at)
        or _utc_naive(anchor.tested_at) > _utc_naive(anchor.verified_at)
        or _utc_naive(anchor.verified_at)
        > _utc_naive(now or datetime.now(timezone.utc))
    ):
        return False
    try:
        expected_expires_at = evidence_expires_at(anchor.verified_at, ttl_days)
    except CapabilityStateError:
        return False
    return _utc_naive(expected_expires_at) == _utc_naive(anchor.expires_at)


@dataclass(frozen=True, slots=True)
class VoiceRuntimeSnapshot:
    """分别对应 ``voice_call`` 两个 JSON 列的递归不可变值。"""

    config_snapshot: Mapping[str, Any]
    capability_snapshot: Mapping[str, Any]

    def persistence_values(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """每次返回新深拷贝，供 ORM JSON 列持久化。"""

        return _deep_thaw(self.config_snapshot), _deep_thaw(self.capability_snapshot)


def _published_gate_blocks_call(
    global_config: Mapping[str, Any],
    user_id: int | None,
) -> bool:
    """按冻结优先级应用已发布门禁；只消费已通过整包 schema 的字段。"""

    if global_config["maintenance_mode"] is True:
        return True
    if global_config["soft_stop"] is True:
        return True
    rollout = global_config["rollout"]
    if rollout["mode"] == "off":
        return True
    if rollout["mode"] == "allowlist":
        return type(user_id) is not int or user_id not in rollout["user_ids"]
    return False


@dataclass(frozen=True, slots=True)
class VoiceRuntimeBundle:
    """同一通话开始时解析出的两套语音配置。"""

    config: LoadedVoiceConfig
    script: LoadedVoiceConfig
    persona_anchors: tuple[Mapping[str, Any], ...] = ()
    voice_persona_anchors: tuple[Mapping[str, Any], ...] = ()
    mysql_anchors_available: bool = False
    evidence_anchors: Mapping[str, _EvidenceAnchor] = field(
        default_factory=lambda: MappingProxyType({})
    )
    evidence_anchors_available: bool = False
    force_sources: Mapping[str, Mapping[str, Any]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    force_sources_available: bool = False
    fallback_persona_anchor: Mapping[str, Any] | None = None
    fallback_gate_global: Mapping[str, Any] | None = None
    fallback_gate_user_id: int | None = None
    fallback_gate_blocked: bool = False
    master_switch_enabled: bool | None = None
    master_switch_version: int | None = None

    def should_block_new_call(self, user_id: int | None) -> bool:
        """独立总开关状态不可用或关闭时拒绝新通话，再应用其他发布门禁。"""
        if self.master_switch_enabled is not True:
            return True

        if self.config.technical_fallback:
            if self.fallback_gate_global is None:
                return False
            if user_id == self.fallback_gate_user_id:
                return self.fallback_gate_blocked
            return _published_gate_blocks_call(self.fallback_gate_global, user_id)

        global_config = self.config.payload["global"]
        return _published_gate_blocks_call(global_config, user_id)

    def build_snapshot(
        self,
        *,
        current_capability_dimensions: Mapping[str, Mapping[str, Any]] | None = None,
        now: datetime | None = None,
        user_id: int | None = None,
    ) -> VoiceRuntimeSnapshot:
        """按冻结字段构建深不可变配置/能力快照。"""

        resolved_config = _validate_loaded_metadata(
            self.config,
            expected_key=VOICE_CALL_CONFIG_KEY,
        )
        resolved_script = _validate_loaded_metadata(
            self.script,
            expected_key=VOICE_CALL_SCRIPT_KEY,
        )

        # 加载时已校验；快照前再次全量校验，防止绕过 loader 手工构造实例后
        # 把 P0/mock/弱网/Secret 或不完整对象写入生产投影。这里只放行已有的
        # 服务端证据投影，绝不改变管理端 validator 的禁止手写规则。
        config_issues = _trusted_runtime_issues(VOICE_CALL_CONFIG_KEY, resolved_config)
        script_issues = _trusted_runtime_issues(VOICE_CALL_SCRIPT_KEY, resolved_script)
        if config_issues or script_issues:
            raise RuntimeConfigResolutionError("运行时快照拒绝不完整或含禁用字段的配置")
        from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL, DEFAULT_VOICE_SUMMARY_PROMPT
        resolved_config.setdefault('summary', {'model': DEFAULT_VOICE_SUMMARY_MODEL})
        resolved_script.setdefault('summary', {'prompt_template': DEFAULT_VOICE_SUMMARY_PROMPT})
        resolved_script['memory'] = {'max_retries': 2, 'retry_backoff_ms': [1000, 5000],
                                     **resolved_script['memory']}

        # Validate the original published hash first. Resolve legacy defaults only
        # into this new call's private snapshot, never into active rows/cache.
        from backend.constants.realtime_voice_config import VOICE_CONNECTION_DEFAULTS, VOICE_INTERACTION_DEFAULTS
        resolved_config["concurrency"] = {
            **VOICE_CONNECTION_DEFAULTS, **resolved_config["concurrency"],
        }

        resolved_config["interaction"] = {
            **VOICE_INTERACTION_DEFAULTS, **resolved_config.get("interaction", {}),
        }

        persona_ref = _persona_ref_shape(resolved_config.get("persona_ref"))
        mysql_persona_anchored = (
            self.mysql_anchors_available is True
            and persona_ref is not None
            and _persona_ref_is_anchored(
                persona_ref,
                persona_anchors=self.persona_anchors,
                voice_persona_anchors=self.voice_persona_anchors,
            )
        )
        offline_persona_anchored = (
            self.config.technical_fallback is True
            and persona_ref is not None
            and _persona_ref_shape(self.fallback_persona_anchor) == persona_ref
        )
        if not mysql_persona_anchored and not offline_persona_anchored:
            raise RuntimeConfigResolutionError(
                "运行时快照拒绝无法由可信发布锚核验的 persona_ref"
            )

        if current_capability_dimensions is not None:
            if not isinstance(current_capability_dimensions, Mapping):
                raise RuntimeConfigResolutionError("当前能力维度必须是对象")
            unknown = set(current_capability_dimensions) - set(VOICE_CAPABILITY_KEYS)
            if unknown:
                raise RuntimeConfigResolutionError("当前能力维度包含未知能力位")

        capabilities = resolved_config["capabilities"]
        test_user_ids = resolved_config["global"]["test_user_ids"]
        runtime_capabilities: dict[str, Any] = {}
        runtime_force_sources: dict[str, Mapping[str, Any]] = {}
        for capability_key in VOICE_CAPABILITY_KEYS:
            capability = capabilities[capability_key]
            dimensions: Mapping[str, Any] = _missing_current_dimensions()
            if (
                current_capability_dimensions is not None
                and capability_key in current_capability_dimensions
            ):
                dimensions = current_capability_dimensions[capability_key]
            if not isinstance(dimensions, Mapping) or set(dimensions) != set(
                EVIDENCE_FINGERPRINT_FIELDS
            ):
                raise RuntimeConfigResolutionError("当前能力维度必须精确包含六个冻结字段")
            try:
                resolved_capability = resolve_runtime_capability(
                    capability,
                    current_dimensions=dimensions,
                    now=now,
                )
            except CapabilityStateError as exc:
                raise RuntimeConfigResolutionError(
                    "运行时快照拒绝非法能力状态或当前维度"
                ) from exc
            evidence_anchor_valid = True
            if capability.get("verification_status") == "verified":
                report_id = capability.get("evidence_report_id")
                anchor = (
                    self.evidence_anchors.get(report_id)
                    if isinstance(report_id, str)
                    and isinstance(self.evidence_anchors, Mapping)
                    else None
                )
                evidence_anchor_valid = (
                    self.evidence_anchors_available is True
                    and _verified_anchor_matches(
                        capability_key,
                        capability,
                        anchor,
                        now=now,
                    )
                )
                if not evidence_anchor_valid:
                    resolved_capability = _disabled_capability_projection(
                        resolved_capability,
                        status="stale",
                    )
            force_source = (
                self.force_sources.get(capability_key)
                if self.force_sources_available is True
                and isinstance(self.force_sources, Mapping)
                else None
            )
            scoped_capability = _scope_capability_for_call(
                capability,
                resolved_capability,
                user_id=user_id,
                test_user_ids=test_user_ids,
                allow_forced_test=(
                    evidence_anchor_valid and isinstance(force_source, Mapping)
                ),
            )
            runtime_capabilities[capability_key] = scoped_capability
            if (
                isinstance(force_source, Mapping)
                and scoped_capability.get("enabled") is True
                and scoped_capability.get("forced_enabled") is True
                and scoped_capability.get("effective_scope") == "test"
            ):
                runtime_force_sources[capability_key] = force_source
        resolved_config["capabilities"] = runtime_capabilities

        # resolver 之后再跑一次可信运行时 schema，防止输出结构漂移。
        if _trusted_runtime_issues(VOICE_CALL_CONFIG_KEY, resolved_config):
            raise RuntimeConfigResolutionError("运行时快照拒绝非法能力投影")

        config_snapshot = {
            "master_switch_enabled": self.master_switch_enabled,
            "master_switch_version": self.master_switch_version,
            "config_version": self.config.version,
            "config_content_sha256": self.config.content_sha256,
            "config_schema_version": self.config.schema_version,
            "config_published_at": _published_at_value(self.config),
            "script_version": self.script.version,
            "script_content_sha256": self.script.content_sha256,
            "script_schema_version": self.script.schema_version,
            "script_published_at": _published_at_value(self.script),
            "resolved_config": resolved_config,
            "resolved_script": resolved_script,
        }
        capability_snapshot = deepcopy(resolved_config["capabilities"])
        for capability_key, force_source in runtime_force_sources.items():
            capability_snapshot[capability_key]["force_source"] = _deep_thaw(
                force_source
            )
        return VoiceRuntimeSnapshot(
            config_snapshot=_deep_freeze(config_snapshot),
            capability_snapshot=_deep_freeze(capability_snapshot),
        )


@dataclass(frozen=True, slots=True)
class _ParsedCandidate:
    payload: dict[str, Any]
    content_hash: str


@dataclass(frozen=True, slots=True)
class _PublishedVoiceConfigEnvelope:
    config: Mapping[str, Any]
    persona_ref: Mapping[str, Any]
    gate_global: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ResolvedKey:
    loaded: LoadedVoiceConfig
    redis_status: str
    mysql_status: str


@dataclass(frozen=True, slots=True)
class _MysqlContext:
    active_voice_rows: Mapping[str, AdminConfig]
    persona_rows: tuple[AdminConfig, ...]
    voice_config_history: tuple[AdminConfig, ...]
    available: bool
    evidence_anchors: Mapping[str, _EvidenceAnchor]
    evidence_available: bool
    force_sources: Mapping[str, Mapping[str, Any]]
    force_sources_available: bool
    master_switch: VoiceMasterSwitchState | None = None


RedisProvider = Callable[[], Awaitable[Any]]
SessionFactory = Callable[[], Any]


class RealtimeVoiceRuntimeConfigService:
    """STEP-006A 两 key loader、快照 builder 与危机词 fail-closed loader。"""

    def __init__(
        self,
        *,
        redis_provider: RedisProvider = get_redis,
        session_factory: SessionFactory = async_session_maker,
    ) -> None:
        self._redis_provider = redis_provider
        self._session_factory = session_factory

    @staticmethod
    def _parse_candidate(config_key: str, raw: Any) -> tuple[_ParsedCandidate | None, str]:
        if raw is None:
            return None, "missing"
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None, "invalid_json"
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError, ValueError):
            return None, "invalid_json"
        if not isinstance(value, dict):
            return None, "invalid_shape"
        # 完整 schema 一次性判定；缺字段、未知字段、未知 schema 或 Secret
        # 均使整个 key 失效，禁止用默认值补一个字段后继续。
        if _trusted_runtime_issues(config_key, value):
            return None, "schema_invalid"
        payload = _deep_thaw(_deep_freeze(value))
        return _ParsedCandidate(payload=payload, content_hash=content_sha256(payload)), "ok"

    @classmethod
    def _mysql_source_status(
        cls,
        config_key: str,
        row: AdminConfig | None,
        *,
        available: bool,
    ) -> str:
        if not available:
            return "unavailable"
        if row is None:
            return "missing"
        candidate, status = cls._parse_candidate(config_key, row.config_value)
        if type(row.version) is not int or row.version < 1:
            return "invalid_version"
        if candidate is not None and not isinstance(row.updated_at, datetime):
            return "invalid_published_at"
        return status

    @staticmethod
    def _parse_published_envelope(
        raw: Any,
    ) -> _PublishedVoiceConfigEnvelope | None:
        """严格解析服务端离线锚；任何字段漂移都整包拒绝。"""

        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(value, dict) or set(value) != _PUBLISHED_ENVELOPE_FIELDS:
            return None
        if value.get("envelope_schema_version") != _PUBLISHED_ENVELOPE_SCHEMA_VERSION:
            return None
        if value.get("config_key") != VOICE_CALL_CONFIG_KEY:
            return None
        if type(value.get("config_version")) is not int or value["config_version"] < 1:
            return None
        published_at = value.get("published_at")
        if not isinstance(published_at, str) or not published_at:
            return None
        try:
            datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return None

        config = value.get("config")
        if not isinstance(config, dict):
            return None
        if (
            type(value.get("config_schema_version")) is not int
            or value["config_schema_version"] != VOICE_CONFIG_SCHEMA_VERSION
            or config.get("schema_version") != value["config_schema_version"]
            or value.get("config_content_sha256") != content_sha256(config)
            or _trusted_runtime_issues(VOICE_CALL_CONFIG_KEY, config)
        ):
            return None
        persona_ref = _persona_ref_shape(config.get("persona_ref"))
        global_config = config.get("global")
        if persona_ref is None or not isinstance(global_config, dict):
            return None
        return _PublishedVoiceConfigEnvelope(
            config=_deep_freeze(config),
            persona_ref=_deep_freeze(persona_ref),
            gate_global=_deep_freeze(global_config),
        )

    @staticmethod
    def _parse_force_source_log(
        log: AdminOperationLog,
        *,
        active_config: Mapping[str, Any],
        active_content_hash: str,
    ) -> tuple[str, Mapping[str, Any]] | None:
        """只信任不可变日志中可交叉核验的完整 force-test 成功锚。"""

        if (
            log.module != "voice_config"
            or log.action != "force_enable"
            or not isinstance(log.after_value, str)
            or not log.after_value
        ):
            return None
        try:
            projection = json.loads(log.after_value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(projection, dict):
            return None
        source = projection.get("force_source")
        if not isinstance(source, dict) or set(source) != _FORCE_SOURCE_FIELDS:
            return None
        capability_key = source.get("capability_key")
        draft_revision = source.get("draft_revision")
        operator_id = source.get("operator_id")
        reason_length = source.get("reason_length")
        reason_sha256 = source.get("reason_sha256")
        forced_at_raw = source.get("forced_at")
        if (
            source.get("source") != "admin_force_test"
            or capability_key not in VOICE_CAPABILITY_KEYS
            or type(draft_revision) is not int
            or draft_revision < 1
            or type(operator_id) is not int
            or operator_id != log.admin_user_id
            or type(reason_length) is not int
            or not 1 <= reason_length <= 500
            or not isinstance(reason_sha256, str)
            or not reason_sha256.startswith("sha256:")
            or len(reason_sha256) != 71
            or any(
                character not in "0123456789abcdef"
                for character in reason_sha256.removeprefix("sha256:")
            )
            or not isinstance(forced_at_raw, str)
            or not forced_at_raw
        ):
            return None
        try:
            forced_at = datetime.fromisoformat(
                forced_at_raw.replace("Z", "+00:00")
            )
        except ValueError:
            return None
        if forced_at.tzinfo is None or forced_at.utcoffset() is None:
            return None
        if isinstance(log.created_at, datetime) and abs(
            (
                _utc_naive(forced_at)
                - _utc_naive(log.created_at)
            ).total_seconds()
        ) > 5:
            return None

        change_note = projection.get("change_note")
        capabilities = active_config.get("capabilities")
        capability = (
            capabilities.get(capability_key)
            if isinstance(capabilities, Mapping)
            else None
        )
        if (
            projection.get("action") != "force_enable"
            or projection.get("config_key") != VOICE_CALL_CONFIG_KEY
            or projection.get("result") != "success"
            or projection.get("draft_revision") != draft_revision
            or projection.get("content_sha256") != active_content_hash
            or source.get("config_content_sha256") != active_content_hash
            or not isinstance(change_note, dict)
            or change_note.get("present") is not True
            or change_note.get("length") != reason_length
            or change_note.get("sha256") != reason_sha256
            or not isinstance(capability, Mapping)
            or capability.get("verification_status") not in {"unverified", "stale"}
            or capability.get("enabled") is not True
            or capability.get("forced_enabled") is not True
            or capability.get("effective_scope") != "test"
        ):
            return None
        verification_status = projection.get("verification_status")
        forced_enabled = projection.get("forced_enabled")
        effective_scope = projection.get("effective_scope")
        if (
            not isinstance(verification_status, dict)
            or verification_status.get(capability_key)
            != capability.get("verification_status")
            or not isinstance(forced_enabled, dict)
            or forced_enabled.get(capability_key) is not True
            or not isinstance(effective_scope, dict)
            or effective_scope.get(capability_key) != "test"
        ):
            return None
        return capability_key, _deep_freeze(deepcopy(source))

    async def _read_redis(
        self,
    ) -> tuple[dict[str, Any], dict[str, str], Any]:
        raw_values: dict[str, Any] = {key: None for key in _VOICE_KEYS}
        diagnostics: dict[str, str] = {}
        try:
            redis = await self._redis_provider()
        except Exception:
            logger.warning("实时语音运行时 Redis 获取失败，尝试 MySQL")
            return (
                raw_values,
                {key: "redis_unavailable" for key in _VOICE_KEYS},
                None,
            )

        for key in _VOICE_KEYS:
            try:
                raw_values[key] = await redis.get(f"{_CACHE_PREFIX}{key}")
            except Exception:
                diagnostics[key] = "redis_unavailable"
                logger.warning("实时语音运行时 Redis key 读取失败: %s", key)
        try:
            published_envelope_raw = await redis.get(
                VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY
            )
        except Exception:
            published_envelope_raw = None
            logger.warning("实时语音离线发布锚读取失败")
        return raw_values, diagnostics, published_envelope_raw

    async def _read_mysql_context(self) -> _MysqlContext:
        try:
            async with self._session_factory() as session:
                session: AsyncSession
                rows = (
                    await session.execute(
                        select(AdminConfig)
                        .where(
                            AdminConfig.config_key.in_(
                                (*_VOICE_KEYS, _PERSONA_CONFIG_KEY, VOICE_CALL_MASTER_SWITCH_KEY)
                            ),
                            AdminConfig.is_draft == False,  # noqa: E712
                        )
                        .order_by(
                            AdminConfig.config_key.asc(),
                            AdminConfig.version.desc(),
                            AdminConfig.id.desc(),
                        )
                    )
                ).scalars().all()
        except Exception:
            logger.warning("实时语音运行时 MySQL 读取失败")
            return _MysqlContext({}, (), (), False, {}, False, {}, False)

        active_voice_rows: dict[str, AdminConfig] = {}
        persona_rows: list[AdminConfig] = []
        voice_config_history: list[AdminConfig] = []
        for row in rows:
            if row.config_key == _PERSONA_CONFIG_KEY:
                persona_rows.append(row)
            elif row.config_key == VOICE_CALL_CONFIG_KEY:
                voice_config_history.append(row)
            if row.config_key in _VOICE_KEYS and row.is_active is True:
                # 异常重复 active 时确定性选最高 version/id；正常库每 key 只有一行。
                active_voice_rows.setdefault(row.config_key, row)
        report_ids: set[str] = set()
        config_row = active_voice_rows.get(VOICE_CALL_CONFIG_KEY)
        config_payload: dict[str, Any] | None = None
        if config_row is not None:
            try:
                config_payload = json.loads(config_row.config_value)
            except (json.JSONDecodeError, TypeError, ValueError):
                config_payload = None
            capabilities = (
                config_payload.get("capabilities")
                if isinstance(config_payload, dict)
                else None
            )
            if isinstance(capabilities, dict):
                for capability_key in VOICE_CAPABILITY_KEYS:
                    capability = capabilities.get(capability_key)
                    report_id = (
                        capability.get("evidence_report_id")
                        if isinstance(capability, dict)
                        else None
                    )
                    if isinstance(report_id, str) and report_id.strip():
                        report_ids.add(report_id)

        evidence_anchors: dict[str, _EvidenceAnchor] = {}
        evidence_available = True
        if report_ids:
            try:
                async with self._session_factory() as evidence_session:
                    evidence_session: AsyncSession
                    evidence_rows = (
                        await evidence_session.execute(
                            select(VoiceCapabilityEvidence).where(
                                VoiceCapabilityEvidence.evidence_report_id.in_(
                                    tuple(sorted(report_ids))
                                )
                            )
                        )
                    ).scalars().all()
            except Exception:
                logger.warning("实时语音能力证据 MySQL 锚读取失败")
                evidence_available = False
            else:
                for evidence in evidence_rows:
                    evidence_anchors.setdefault(
                        evidence.evidence_report_id,
                        _EvidenceAnchor(
                            evidence_report_id=evidence.evidence_report_id,
                            capability_key=evidence.capability_key,
                            verification_result=evidence.verification_result,
                            dimensions=MappingProxyType(
                                {
                                    field_name: getattr(evidence, field_name)
                                    for field_name in EVIDENCE_FINGERPRINT_FIELDS
                                }
                            ),
                            evidence_fingerprint=evidence.evidence_fingerprint,
                            tested_at=evidence.tested_at,
                            verified_at=evidence.verified_at,
                            evidence_ttl_days_snapshot=(
                                evidence.evidence_ttl_days_snapshot
                            ),
                            expires_at=evidence.expires_at,
                        ),
                    )

        force_sources: dict[str, Mapping[str, Any]] = {}
        force_sources_available = True
        forced_capability_keys = {
            capability_key
            for capability_key in VOICE_CAPABILITY_KEYS
            if isinstance(config_payload, dict)
            and isinstance(config_payload.get("capabilities"), dict)
            and isinstance(
                config_payload["capabilities"].get(capability_key),
                dict,
            )
            and config_payload["capabilities"][capability_key].get(
                "forced_enabled"
            )
            is True
        }
        if forced_capability_keys and isinstance(config_payload, dict):
            active_content_hash = content_sha256(config_payload)
            try:
                async with self._session_factory() as force_session:
                    force_session: AsyncSession
                    force_logs = (
                        await force_session.execute(
                            select(AdminOperationLog)
                            .where(
                                AdminOperationLog.module == "voice_config",
                                AdminOperationLog.action == "force_enable",
                                AdminOperationLog.after_value.is_not(None),
                                AdminOperationLog.after_value.contains(
                                    active_content_hash
                                ),
                            )
                            .order_by(AdminOperationLog.id.desc())
                            .limit(128)
                        )
                    ).scalars().all()
            except Exception:
                logger.warning("实时语音强制来源 MySQL 锚读取失败")
                force_sources_available = False
            else:
                for force_log in force_logs:
                    parsed_force_source = self._parse_force_source_log(
                        force_log,
                        active_config=config_payload,
                        active_content_hash=active_content_hash,
                    )
                    if parsed_force_source is None:
                        continue
                    capability_key, force_source = parsed_force_source
                    if capability_key in forced_capability_keys:
                        force_sources.setdefault(capability_key, force_source)

        return _MysqlContext(
            active_voice_rows,
            tuple(persona_rows),
            tuple(voice_config_history),
            True,
            MappingProxyType(evidence_anchors),
            evidence_available,
            MappingProxyType(force_sources),
            force_sources_available,
            parse_master_switch_rows([row for row in rows if row.config_key == VOICE_CALL_MASTER_SWITCH_KEY and row.is_active is True]),
        )

    @staticmethod
    def _row_persona_ref(row: AdminConfig) -> dict[str, Any] | None:
        if (
            row.config_key != _PERSONA_CONFIG_KEY
            or type(row.version) is not int
            or row.version < 1
            or not isinstance(row.config_value, str)
            or not row.config_value
        ):
            return None
        digest = hashlib.sha256(row.config_value.encode("utf-8")).hexdigest()
        return {
            "config_key": _PERSONA_CONFIG_KEY,
            "version": row.version,
            "content_sha256": f"sha256:{digest}",
        }

    @staticmethod
    def _persona_ref_shape(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
        return _persona_ref_shape(value)

    @classmethod
    def _voice_history_persona_refs(
        cls,
        rows: tuple[AdminConfig, ...],
    ) -> tuple[Mapping[str, Any], ...]:
        result: list[Mapping[str, Any]] = []
        for row in rows:
            if type(row.version) is not int or row.version < 1:
                continue
            try:
                payload = json.loads(row.config_value)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            saved = (
                cls._persona_ref_shape(payload.get("persona_ref"))
                if isinstance(payload, dict)
                else None
            )
            if saved is not None and saved not in result:
                result.append(MappingProxyType(saved))
        return tuple(result)

    @classmethod
    def _voice_history_has_persona_ref(
        cls,
        rows: tuple[AdminConfig, ...],
        expected: Mapping[str, Any],
    ) -> bool:
        for row in rows:
            if type(row.version) is not int or row.version < 1:
                continue
            try:
                payload = json.loads(row.config_value)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            saved = (
                cls._persona_ref_shape(payload.get("persona_ref"))
                if isinstance(payload, dict)
                else None
            )
            if saved == expected:
                return True
        return False

    @classmethod
    def _resolve_fallback_persona_ref(
        cls,
        mysql_context: _MysqlContext,
        external_ref: Mapping[str, Any] | None,
        published_envelope: _PublishedVoiceConfigEnvelope | None,
    ) -> dict[str, Any]:
        if mysql_context.available:
            for row in mysql_context.persona_rows:
                if row.is_active is not True:
                    continue
                generated = cls._row_persona_ref(row)
                if generated is not None:
                    return generated

        candidate = cls._persona_ref_shape(external_ref)
        if candidate is not None and mysql_context.available:
            for row in mysql_context.persona_rows:
                if row.version != candidate["version"]:
                    continue
                generated = cls._row_persona_ref(row)
                if generated == candidate:
                    return candidate
            retained_versions = [
                row.version
                for row in mysql_context.persona_rows
                if type(row.version) is int and row.version >= 1
            ]
            if (
                retained_versions
                and candidate["version"] < min(retained_versions)
                and cls._voice_history_has_persona_ref(
                    mysql_context.voice_config_history,
                    candidate,
                )
            ):
                return candidate

        if published_envelope is not None:
            return _deep_thaw(published_envelope.persona_ref)

        raise RuntimeConfigResolutionError(
            "voice_call_config 技术回退需要可核验的已发布 persona_ref/envelope 锚"
        )

    @classmethod
    def _canonical_payload(
        cls,
        config_key: str,
        fallback_persona_ref: Mapping[str, Any] | None,
        mysql_context: _MysqlContext,
        published_envelope: _PublishedVoiceConfigEnvelope | None,
    ) -> dict[str, Any]:
        if config_key == VOICE_CALL_CONFIG_KEY:
            persona_ref = cls._resolve_fallback_persona_ref(
                mysql_context,
                fallback_persona_ref,
                published_envelope,
            )
            payload = get_default_voice_call_config(persona_ref)
        elif config_key == VOICE_CALL_SCRIPT_KEY:
            payload = get_default_voice_call_script()
        else:  # pragma: no cover - 仅防内部误用
            raise RuntimeConfigResolutionError(f"未知语音配置 key: {config_key}")

        if _trusted_runtime_issues(config_key, payload):
            raise RuntimeConfigResolutionError("规范默认配置或 persona_ref 不满足冻结 schema")
        return payload

    def _resolve_key(
        self,
        *,
        config_key: str,
        redis_raw: Any,
        redis_diagnostic: str | None,
        mysql_row: AdminConfig | None,
        mysql_available: bool,
        mysql_context: _MysqlContext,
        fallback_persona_ref: Mapping[str, Any] | None,
        published_envelope: _PublishedVoiceConfigEnvelope | None,
    ) -> _ResolvedKey:
        redis_candidate, parsed_redis_status = self._parse_candidate(
            config_key,
            redis_raw,
        )
        redis_status = (
            "unavailable"
            if redis_diagnostic == "redis_unavailable"
            else parsed_redis_status
        )

        mysql_candidate: _ParsedCandidate | None = None
        mysql_status = "unavailable" if not mysql_available else "missing"
        mysql_version = 0
        mysql_published_at: datetime | None = None
        if mysql_row is not None:
            mysql_candidate, parsed_status = self._parse_candidate(
                config_key,
                mysql_row.config_value,
            )
            mysql_status = parsed_status
            if type(mysql_row.version) is int and mysql_row.version >= 1:
                mysql_version = mysql_row.version
            else:
                mysql_candidate = None
                mysql_status = "invalid_version"
            if mysql_candidate is not None and isinstance(mysql_row.updated_at, datetime):
                mysql_published_at = mysql_row.updated_at
            elif mysql_candidate is not None:
                mysql_candidate = None
                mysql_status = "invalid_published_at"

        diagnostics = [redis_diagnostic or f"redis_{redis_status}"]
        diagnostics.append(f"mysql_{mysql_status}")

        def resolved(loaded: LoadedVoiceConfig) -> _ResolvedKey:
            return _ResolvedKey(
                loaded=loaded,
                redis_status=redis_status,
                mysql_status=mysql_status,
            )

        if redis_candidate is not None:
            if mysql_candidate is not None:
                if redis_candidate.content_hash == mysql_candidate.content_hash:
                    return resolved(
                        self._loaded(
                            config_key,
                            redis_candidate,
                            version=mysql_version,
                            published_at=mysql_published_at,
                            source=RuntimeConfigSource.REDIS,
                            technical_fallback=False,
                            diagnostics=tuple(diagnostics),
                        )
                    )
                # 两侧都完整但 hash 不同表示 Redis 缓存不一致；MySQL active
                # row 是可信版本锚，必须采用 DB 整包，不能把缓存伪装成 version=0。
                diagnostics.append("redis_mysql_hash_mismatch")
                return resolved(
                    self._loaded(
                        config_key,
                        mysql_candidate,
                        version=mysql_version,
                        published_at=mysql_published_at,
                        source=RuntimeConfigSource.MYSQL,
                        technical_fallback=False,
                        diagnostics=tuple(diagnostics),
                    )
                )

            # Redis 不能独立证明发布版本；DB active 缺失/非法/不可用时，缓存
            # 只能作为不可信候选，绝不能以 version=0 表达运营开关意图。
            diagnostics.append("redis_without_mysql_publish_anchor")

        if mysql_candidate is not None:
            return resolved(
                self._loaded(
                    config_key,
                    mysql_candidate,
                    version=mysql_version,
                    published_at=mysql_published_at,
                    source=RuntimeConfigSource.MYSQL,
                    technical_fallback=False,
                    diagnostics=tuple(diagnostics),
                )
            )

        payload = self._canonical_payload(
            config_key,
            fallback_persona_ref,
            mysql_context,
            published_envelope,
        )
        fallback = _ParsedCandidate(payload=payload, content_hash=content_sha256(payload))
        logger.warning(
            "实时语音配置整 key 使用规范回退: key=%s redis=%s mysql=%s",
            config_key,
            redis_diagnostic or redis_status,
            mysql_status,
        )
        return resolved(
            self._loaded(
                config_key,
                fallback,
                version=0,
                published_at=None,
                source=RuntimeConfigSource.CANONICAL_FALLBACK,
                technical_fallback=True,
                diagnostics=tuple(diagnostics),
            )
        )

    @staticmethod
    def _loaded(
        config_key: str,
        candidate: _ParsedCandidate,
        *,
        version: int,
        published_at: datetime | None,
        source: RuntimeConfigSource,
        technical_fallback: bool,
        diagnostics: tuple[str, ...],
    ) -> LoadedVoiceConfig:
        schema_version = candidate.payload["schema_version"]
        return LoadedVoiceConfig(
            config_key=config_key,
            version=version,
            schema_version=schema_version,
            content_sha256=candidate.content_hash,
            published_at=published_at,
            payload=_deep_freeze(candidate.payload),
            source=source,
            technical_fallback=technical_fallback,
            diagnostics=diagnostics,
        )

    async def _increment_fallback_metric(
        self,
        *,
        config_key: str,
        redis_status: str,
        mysql_status: str,
        outcome: str,
    ) -> None:
        """写入独立低基数计数器；sink 失败不得改变加载或门禁结果。"""

        dimensions = canonical_json(
            {
                "config_key": config_key,
                "redis_status": redis_status,
                "mysql_status": mysql_status,
                "outcome": outcome,
            }
        )
        try:
            async with asyncio.timeout(_FALLBACK_METRIC_DEADLINE_SECONDS):
                redis = await self._redis_provider()
                await redis.eval(
                    _FALLBACK_METRIC_INCREMENT_SCRIPT,
                    1,
                    _FALLBACK_METRIC_NAMESPACE,
                    dimensions,
                    1,
                    _FALLBACK_METRIC_TTL_SECONDS,
                )
        except Exception:
            # 不记录异常对象、动态 key 或正文，避免 Secret/自由错误进入日志。
            logger.warning("实时语音 fallback 独立指标写入失败")

    async def load_bundle(
        self,
        *,
        fallback_persona_ref: Mapping[str, Any] | None = None,
        user_id: int | None = None,
    ) -> VoiceRuntimeBundle:
        """同时解析两个 key；只有 config 真正回退时才要求真实 persona_ref。"""

        redis_values, redis_diagnostics, envelope_raw = await self._read_redis()
        published_envelope = self._parse_published_envelope(envelope_raw)
        mysql_context = await self._read_mysql_context()

        resolved: dict[str, _ResolvedKey] = {}
        for key in _VOICE_KEYS:
            try:
                resolved[key] = self._resolve_key(
                    config_key=key,
                    redis_raw=redis_values.get(key),
                    redis_diagnostic=redis_diagnostics.get(key),
                    mysql_row=mysql_context.active_voice_rows.get(key),
                    mysql_available=mysql_context.available,
                    mysql_context=mysql_context,
                    fallback_persona_ref=fallback_persona_ref,
                    published_envelope=published_envelope,
                )
            except RuntimeConfigResolutionError:
                if key == VOICE_CALL_CONFIG_KEY:
                    _, parsed_redis_status = self._parse_candidate(
                        key,
                        redis_values.get(key),
                    )
                    await self._increment_fallback_metric(
                        config_key=key,
                        redis_status=(
                            "unavailable"
                            if redis_diagnostics.get(key) == "redis_unavailable"
                            else parsed_redis_status
                        ),
                        mysql_status=(
                            self._mysql_source_status(
                                key,
                                mysql_context.active_voice_rows.get(key),
                                available=mysql_context.available,
                            )
                        ),
                        outcome="anchor_fail_closed",
                    )
                raise

        fallback_gate_global = (
            published_envelope.gate_global
            if resolved[VOICE_CALL_CONFIG_KEY].loaded.technical_fallback
            and published_envelope is not None
            else None
        )
        fallback_gate_blocked = (
            _published_gate_blocks_call(fallback_gate_global, user_id)
            if fallback_gate_global is not None
            else False
        )
        bundle = VoiceRuntimeBundle(
            master_switch_enabled=mysql_context.master_switch.enabled if mysql_context.master_switch else None,
            master_switch_version=mysql_context.master_switch.version if mysql_context.master_switch else None,
            config=resolved[VOICE_CALL_CONFIG_KEY].loaded,
            script=resolved[VOICE_CALL_SCRIPT_KEY].loaded,
            persona_anchors=tuple(
                MappingProxyType(persona_ref)
                for row in mysql_context.persona_rows
                if (persona_ref := self._row_persona_ref(row)) is not None
            ),
            voice_persona_anchors=self._voice_history_persona_refs(
                mysql_context.voice_config_history
            ),
            mysql_anchors_available=mysql_context.available,
            evidence_anchors=mysql_context.evidence_anchors,
            evidence_anchors_available=mysql_context.evidence_available,
            force_sources=mysql_context.force_sources,
            force_sources_available=mysql_context.force_sources_available,
            fallback_persona_anchor=(
                published_envelope.persona_ref
                if resolved[VOICE_CALL_CONFIG_KEY].loaded.technical_fallback
                and published_envelope is not None
                else None
            ),
            fallback_gate_global=fallback_gate_global,
            fallback_gate_user_id=user_id,
            fallback_gate_blocked=fallback_gate_blocked,
        )
        outcome = (
            "gate_blocked" if bundle.should_block_new_call(user_id) else "continued"
        )
        for key in _VOICE_KEYS:
            resolution = resolved[key]
            if resolution.loaded.technical_fallback:
                await self._increment_fallback_metric(
                    config_key=key,
                    redis_status=resolution.redis_status,
                    mysql_status=resolution.mysql_status,
                    outcome=outcome,
                )
        return bundle

    async def load_crisis_keywords(self, *, db=None) -> CrisisKeywordLoadResult:
        """缓存失效时读取已发布配置；允许逐轮写入复用当前事务。"""
        return await CrisisConfigReader(session_factory=self._session_factory,
            redis_provider=self._redis_provider).load(db=db)


realtime_voice_runtime_config_service = RealtimeVoiceRuntimeConfigService()


__all__ = [
    "CrisisKeywordLoadResult",
    "LoadedVoiceConfig",
    "RealtimeVoiceRuntimeConfigService",
    "RuntimeConfigResolutionError",
    "RuntimeConfigSource",
    "VoiceRuntimeBundle",
    "VoiceRuntimeSnapshot",
    "realtime_voice_runtime_config_service",
]
