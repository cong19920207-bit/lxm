# -*- coding: utf-8 -*-
"""实时语音配置控制面服务（STEP-005 / STEP-006 内部能力控制）。

本模块只负责两套配置的草稿、校验、发布、回滚、seed 与 follow-up 预览；
另提供不暴露路由的 STEP-006 强制 test 状态机。它不负责页面、运行时 loader、
能力取证或真实连接测试。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import parse_qsl, urlparse
from weakref import WeakKeyDictionary
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.realtime_voice_config import (
    CRISIS_KEYWORDS_CONFIG_KEY,
    RELATIONSHIP_STAGES,
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
    VOICE_CAPABILITY_KEYS,
    VOICE_CONFIG_ALIASES,
    VOICE_CONFIG_SCHEMA_VERSION,
    VOICE_CONNECTION_DEFAULTS,
    VOICE_INTERACTION_DEFAULTS,
    build_canonical_voice_seed_manifest,
)
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import (
    VOICE_EVIDENCE_SOURCE_TYPES,
    VoiceCapabilityEvidence,
)
from backend.redis_client import get_redis
from backend.services.admin_config_service import admin_config_service
from backend.services.realtime_voice_capability_service import (
    CapabilityStateError,
    compute_evidence_fingerprint,
    evidence_expires_at,
    validate_evidence_ttl_days,
)
from backend.utils.admin_auth import log_operation


logger = logging.getLogger(__name__)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_ENV_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_RAW_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_VALUE_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|\bsk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)
_SECRET_FIELD_NAMES = frozenset(
    {
        "app_id",
        "app_key",
        "access_key",
        "access_key_secret",
        "api_key",
        "api_secret",
        "authorization",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "secret_key",
        "token",
    }
)
_EXPERIMENTAL_FIELD_NAMES = frozenset(
    {
        "capability_gray",
        "mock_s2s",
        "net_profile",
        "preamble_memory_doc_ids",
        "percentage",
        "weak_network_profile",
    }
)

FOLLOWUP_WINDOW_RANGE_INVALID = "FOLLOWUP_WINDOW_RANGE_INVALID"
FOLLOWUP_WINDOW_OVERLAP = "FOLLOWUP_WINDOW_OVERLAP"
FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER = "FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER"
FOLLOWUP_PREVIEW_INPUT_INVALID = "FOLLOWUP_PREVIEW_INPUT_INVALID"

VOICE_CONFIG_SCHEMA_INVALID = "VOICE_CONFIG_SCHEMA_INVALID"
VOICE_CONFIG_FIELD_RANGE_INVALID = "VOICE_CONFIG_FIELD_RANGE_INVALID"
VOICE_CONFIG_FORBIDDEN_FIELD = "VOICE_CONFIG_FORBIDDEN_FIELD"
VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN = "VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN"
VOICE_CONFIG_SECRET_FORBIDDEN = "VOICE_CONFIG_SECRET_FORBIDDEN"
VOICE_CONFIG_REVISION_CONFLICT = "VOICE_CONFIG_REVISION_CONFLICT"
VOICE_CONFIG_BASE_VERSION_CONFLICT = "VOICE_CONFIG_BASE_VERSION_CONFLICT"
VOICE_CONFIG_NO_DRAFT = "VOICE_CONFIG_NO_DRAFT"
VOICE_CONFIG_VERSION_NOT_FOUND = "VOICE_CONFIG_VERSION_NOT_FOUND"
VOICE_CONFIG_CREDENTIAL_MISSING = "VOICE_CONFIG_CREDENTIAL_MISSING"
VOICE_CONFIG_PERSONA_REQUIRED = "VOICE_CONFIG_PERSONA_REQUIRED"
VOICE_CONFIG_PERSONA_REF_INVALID = "VOICE_CONFIG_PERSONA_REF_INVALID"
VOICE_CAPABILITY_PROJECTION_FORGED = "VOICE_CAPABILITY_PROJECTION_FORGED"
VOICE_CAPABILITY_TRUSTED_STATE_INVALID = "VOICE_CAPABILITY_TRUSTED_STATE_INVALID"
VOICE_CAPABILITY_FORCE_FORBIDDEN = "VOICE_CAPABILITY_FORCE_FORBIDDEN"
VOICE_CAPABILITY_FORCE_CONFIRM_INVALID = "VOICE_CAPABILITY_FORCE_CONFIRM_INVALID"
VOICE_CAPABILITY_FORCE_REASON_REQUIRED = "VOICE_CAPABILITY_FORCE_REASON_REQUIRED"
VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED = "VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED"
VOICE_CAPABILITY_FORCE_STATUS_INVALID = "VOICE_CAPABILITY_FORCE_STATUS_INVALID"
VOICE_CAPABILITY_FORCE_SCOPE_INVALID = "VOICE_CAPABILITY_FORCE_SCOPE_INVALID"
VOICE_CAPABILITY_ALL_EVIDENCE_INVALID = "VOICE_CAPABILITY_ALL_EVIDENCE_INVALID"
VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE = (
    "VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE"
)
CRISIS_KEYWORDS_EMPTY = "CRISIS_KEYWORDS_EMPTY"

# AC77 仅供服务端读写的最后确认发布锚。该 key 不是管理 API 契约；值为
# 无 TTL、完整校验且不含 Secret 的 voice_call_config 发布 envelope。
VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY = (
    "published_config_anchor:v1:voice_call_config"
)
_PUBLISHED_ENVELOPE_SCHEMA_VERSION = 1
_PUBLISHED_ANCHOR_TAKE_SCRIPT = """
-- AC77_ANCHOR_TAKE_V1
local current = redis.call('GET', KEYS[1])
if not current then
  return {0, false}
end
local ok, decoded = pcall(cjson.decode, current)
if ok and type(decoded) == 'table' and type(decoded.config_version) == 'number' then
  if decoded.config_version > tonumber(ARGV[1]) then
    return {-1, current}
  end
else
  redis.call('DEL', KEYS[1])
  return {2, false}
end
redis.call('DEL', KEYS[1])
return {1, current}
"""
_PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT = """
-- AC77_ANCHOR_SET_IF_NEWER_V1
local current = redis.call('GET', KEYS[1])
if current then
  local ok, decoded = pcall(cjson.decode, current)
  if not ok or type(decoded) ~= 'table' or type(decoded.config_version) ~= 'number' then
    return -2
  end
  local desired_version = tonumber(ARGV[1])
  if decoded.config_version > desired_version then
    return 0
  end
  if decoded.config_version == desired_version then
    if current == ARGV[2] then
      return 2
    end
    return -3
  end
end
redis.call('SET', KEYS[1], ARGV[2])
return 1
"""
_PUBLISHED_ANCHOR_RESTORE_IF_ABSENT_SCRIPT = """
-- AC77_ANCHOR_RESTORE_IF_ABSENT_V1
if redis.call('EXISTS', KEYS[1]) == 1 then
  return 0
end
redis.call('SET', KEYS[1], ARGV[1])
return 1
"""
_PUBLISHED_ANCHOR_DELETE_IF_MATCH_SCRIPT = """
-- AC77_ANCHOR_DELETE_IF_MATCH_V1
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call('DEL', KEYS[1])
return 1
"""

_CAPABILITY_EVIDENCE_DIMENSION_FIELDS = (
    "provider_profile",
    "model_version",
    "protocol_profile",
    "adapter_version",
    "sdk_version",
    "evidence_suite_version",
)
_CAPABILITY_SERVER_OWNED_FIELDS = frozenset(
    {
        "verification_status",
        "forced_enabled",
        *_CAPABILITY_EVIDENCE_DIMENSION_FIELDS,
        "evidence_fingerprint",
        "verified_at",
        "expires_at",
        "evidence_report_id",
        "last_test_result",
    }
)

CurrentDimensionsProvider = Callable[
    [str, Mapping[str, Any]],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]

_LOOP_OPERATION_MUTEXES: WeakKeyDictionary[Any, dict[str, asyncio.Lock]] = (
    WeakKeyDictionary()
)


class VoiceConfigError(Exception):
    """可安全返回给管理 API 的语音配置业务错误。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []
        self.status_code = status_code


def _operation_mutex(name: str) -> asyncio.Lock:
    """单实例内串行同一发布单元；数据库行锁仍承担持久层并发保护。"""

    loop = asyncio.get_running_loop()
    mutexes = _LOOP_OPERATION_MUTEXES.setdefault(loop, {})
    return mutexes.setdefault(name, asyncio.Lock())


def _serialized_operation(name: str):
    def decorator(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            async with _operation_mutex(name):
                return await function(*args, **kwargs)

        return wrapped

    return decorator


def canonical_json(value: Any) -> str:
    """稳定 JSON：UTF-8 语义、键排序、无展示空白。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _issue(
    code: str,
    field: str,
    message: str,
    *,
    allowed: Any = None,
) -> dict[str, Any]:
    issue = {"code": code, "field": field, "message": message}
    if allowed is not None:
        issue["allowed"] = allowed
    return issue


def _credential_env_values() -> set[str]:
    """仅取看起来像凭据的环境变量值，用于阻止值误入配置。"""

    result: set[str] = set()
    for name, value in os.environ.items():
        upper_name = name.upper()
        if not any(token in upper_name for token in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            continue
        if isinstance(value, str) and len(value) >= 8:
            result.add(value)
    return result


def _scan_forbidden_fields(value: Any) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    credential_values = _credential_env_values()

    def walk(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for raw_key, child in item.items():
                key = str(raw_key)
                normalized = key.casefold()
                child_path = f"{path}.{key}" if path else key
                if normalized in _EXPERIMENTAL_FIELD_NAMES:
                    issues.append(
                        _issue(
                            VOICE_CONFIG_FORBIDDEN_FIELD,
                            child_path,
                            "生产配置禁止实验或百分比灰度字段",
                        )
                    )
                if normalized in _SECRET_FIELD_NAMES or (
                    normalized.endswith("_secret")
                    or normalized.endswith("_token")
                ):
                    issues.append(
                        _issue(
                            VOICE_CONFIG_SECRET_FORBIDDEN,
                            child_path,
                            "配置只能保存非敏感 credential_ref，禁止凭据字段",
                        )
                    )
                walk(child, child_path)
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(item, str) and (
            _SECRET_VALUE_RE.search(item) or item in credential_values
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_SECRET_FORBIDDEN,
                    path,
                    "检测到疑似凭据值，配置只允许环境变量名引用",
                )
            )

    walk(value, "")
    return issues


def _check_exact_keys(
    value: Any,
    field: str,
    *,
    required: set[str],
    allowed: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return [_issue(VOICE_CONFIG_SCHEMA_INVALID, field, "必须是对象")]
    actual = set(value)
    allowed_keys = allowed or required
    issues = [
        _issue(VOICE_CONFIG_SCHEMA_INVALID, f"{field}.{key}", "缺少必填字段")
        for key in sorted(required - actual)
    ]
    issues.extend(
        _issue(VOICE_CONFIG_SCHEMA_INVALID, f"{field}.{key}", "schema 不接受该字段")
        for key in sorted(actual - allowed_keys)
    )
    return issues


def _check_int_range(
    value: Any,
    field: str,
    minimum: int,
    maximum: int | None = None,
) -> list[dict[str, Any]]:
    if type(value) is not int or value < minimum or (
        maximum is not None and value > maximum
    ):
        allowed = {"min": minimum}
        if maximum is not None:
            allowed["max"] = maximum
        return [
            _issue(
                VOICE_CONFIG_FIELD_RANGE_INVALID,
                field,
                "整数参数超出允许区间",
                allowed=allowed,
            )
        ]
    return []


def _check_number_range(
    value: Any,
    field: str,
    minimum: float,
    maximum: float | None = None,
) -> list[dict[str, Any]]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum or (
        maximum is not None and value > maximum
    ):
        allowed: dict[str, float] = {"min": minimum}
        if maximum is not None:
            allowed["max"] = maximum
        return [
            _issue(
                VOICE_CONFIG_FIELD_RANGE_INVALID,
                field,
                "数值参数超出允许区间",
                allowed=allowed,
            )
        ]
    return []


def _window_minutes(value: Any) -> int | None:
    if not isinstance(value, str) or not _HHMM_RE.fullmatch(value):
        return None
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def validate_followup_schedule(schedule: Any) -> list[dict[str, Any]]:
    """校验 ADM-C32 的多窗口 schema，并返回精确错误码。"""

    issues: list[dict[str, Any]] = []
    if not isinstance(schedule, dict):
        return [
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                "followup.schedule",
                "followup.schedule 必须是对象",
            )
        ]

    schedule_fields = {
        "timezone",
        "jitter_min_minutes",
        "jitter_max_minutes",
        "max_delay_hours",
        "stages",
    }
    for field in sorted(schedule_fields - set(schedule)):
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                f"followup.schedule.{field}",
                "缺少必填字段",
            )
        )
    for field in sorted(set(schedule) - schedule_fields):
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                f"followup.schedule.{field}",
                "窗口 schema 不接受该字段",
            )
        )

    timezone_name = schedule.get("timezone")
    jitter_min = schedule.get("jitter_min_minutes")
    jitter_max = schedule.get("jitter_max_minutes")
    max_delay = schedule.get("max_delay_hours")
    stages = schedule.get("stages")
    if timezone_name != "Asia/Shanghai":
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                "followup.schedule.timezone",
                "本期只允许 Asia/Shanghai",
                allowed=["Asia/Shanghai"],
            )
        )
    if type(jitter_min) is not int or type(jitter_max) is not int or not (
        0 <= jitter_min <= jitter_max <= 20
    ):
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                "followup.schedule.jitter",
                "jitter 必须满足 0 <= min <= max <= 20",
                allowed={"min": 0, "max": 20},
            )
        )
    if type(max_delay) is not int or max_delay != 24:
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                "followup.schedule.max_delay_hours",
                "最大顺延必须为 24 小时",
                allowed=[24],
            )
        )
    if not isinstance(stages, dict):
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                "followup.schedule.stages",
                "stages 必须包含四个关系阶段",
            )
        )
        return issues

    for stage in RELATIONSHIP_STAGES:
        stage_value = stages.get(stage)
        if isinstance(stage_value, dict):
            for field in sorted(set(stage_value) - {"windows"}):
                issues.append(
                    _issue(
                        FOLLOWUP_WINDOW_RANGE_INVALID,
                        f"followup.schedule.stages.{stage}.{field}",
                        "关系阶段只接受 windows 字段",
                    )
                )
        windows = stage_value.get("windows") if isinstance(stage_value, dict) else None
        field = f"followup.schedule.stages.{stage}.windows"
        if not isinstance(windows, list) or not windows:
            issues.append(
                _issue(
                    FOLLOWUP_WINDOW_RANGE_INVALID,
                    field,
                    "每个关系阶段必须配置非空 windows",
                )
            )
            continue

        normalized: list[tuple[int, int, int]] = []
        for index, window in enumerate(windows):
            window_field = f"{field}[{index}]"
            if not isinstance(window, dict) or set(window) != {"start", "end"}:
                issues.append(
                    _issue(
                        FOLLOWUP_WINDOW_RANGE_INVALID,
                        window_field,
                        "窗口只接受 start/end 分钟精度字段",
                    )
                )
                continue
            start = _window_minutes(window.get("start"))
            end = _window_minutes(window.get("end"))
            if start is None or end is None or start >= end:
                issues.append(
                    _issue(
                        FOLLOWUP_WINDOW_RANGE_INVALID,
                        window_field,
                        "窗口必须为 HH:mm、start < end 且不跨日",
                    )
                )
                continue
            normalized.append((start, end, index))
            if type(jitter_max) is int and end - start <= jitter_max:
                issues.append(
                    _issue(
                        FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER,
                        window_field,
                        "窗口时长必须严格大于 jitter_max_minutes",
                        allowed={"strictly_greater_than_minutes": jitter_max},
                    )
                )

        normalized.sort()
        for previous, current in zip(normalized, normalized[1:]):
            if current[0] < previous[1]:
                issues.append(
                    _issue(
                        FOLLOWUP_WINDOW_OVERLAP,
                        field,
                        "同一关系阶段窗口不得重叠；首尾相邻合法",
                    )
                )
                break

    extra_stages = set(stages) - set(RELATIONSHIP_STAGES)
    for stage in sorted(extra_stages):
        issues.append(
            _issue(
                FOLLOWUP_WINDOW_RANGE_INVALID,
                f"followup.schedule.stages.{stage}",
                "未知关系阶段",
                allowed=list(RELATIONSHIP_STAGES),
            )
        )
    return issues


def _validate_voice_call_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required_top = {
        "schema_version",
        "global",
        "persona_ref",
        "s2s",
        "voice",
        "capabilities",
        "quota",
        "growth",
        "concurrency",
        "followup",
        "retention",
    }
    issues.extend(_check_exact_keys(config, "config", required=required_top, allowed=required_top | {"interaction", "summary"}))
    if "summary" in config:
        field = "model" if "s2s" in required_top else "prompt_template"
        value = config["summary"]
        issues.extend(_check_exact_keys(value, "summary", required={field}))
        if isinstance(value, dict):
            content = value.get(field)
            if not isinstance(content, str) or not content.strip():
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "summary." + field, "不得为空"))
            elif field == "model" and (len(content) > 128 or not re.fullmatch(r"deepseek-[A-Za-z0-9._-]+", content)):
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "summary.model", "必须为 DeepSeek 模型标识，不能填写 URL 或密钥"))
    if config.get("schema_version") != VOICE_CONFIG_SCHEMA_VERSION:
        issues.append(
            _issue(
                VOICE_CONFIG_SCHEMA_INVALID,
                "schema_version",
                "未知或不兼容 schema_version",
                allowed=[VOICE_CONFIG_SCHEMA_VERSION],
            )
        )

    global_config = config.get("global")
    global_required = {
        "enabled",
        "maintenance_mode",
        "maintenance_message",
        "soft_stop",
        "rollout",
        "test_user_ids",
    }
    issues.extend(_check_exact_keys(global_config, "global", required=global_required))
    if isinstance(global_config, dict):
        for field in ("enabled", "maintenance_mode", "soft_stop"):
            if type(global_config.get(field)) is not bool:
                issues.append(
                    _issue(VOICE_CONFIG_SCHEMA_INVALID, f"global.{field}", "必须是布尔值")
                )
        if not isinstance(global_config.get("maintenance_message"), str) or not global_config.get(
            "maintenance_message"
        ).strip():
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "global.maintenance_message",
                    "必须是非空字符串",
                )
            )
        rollout = global_config.get("rollout")
        issues.extend(
            _check_exact_keys(rollout, "global.rollout", required={"mode", "user_ids"})
        )
        if isinstance(rollout, dict):
            rollout_mode = rollout.get("mode")
            if not isinstance(rollout_mode, str) or rollout_mode not in (
                "off",
                "allowlist",
                "all",
            ):
                issues.append(
                    _issue(
                        VOICE_CONFIG_FORBIDDEN_FIELD,
                        "global.rollout.mode",
                        "rollout mode 只接受 off/allowlist/all",
                        allowed=["off", "allowlist", "all"],
                    )
                )
            user_ids = rollout.get("user_ids")
            if not isinstance(user_ids, list) or any(type(item) is not int for item in user_ids):
                issues.append(
                    _issue(VOICE_CONFIG_SCHEMA_INVALID, "global.rollout.user_ids", "必须是整数数组")
                )
        test_user_ids = global_config.get("test_user_ids")
        if not isinstance(test_user_ids, list) or any(
            type(item) is not int for item in test_user_ids
        ):
            issues.append(
                _issue(VOICE_CONFIG_SCHEMA_INVALID, "global.test_user_ids", "必须是整数数组")
            )

    persona_ref = config.get("persona_ref")
    issues.extend(
        _check_exact_keys(
            persona_ref,
            "persona_ref",
            required={"config_key", "version", "content_sha256"},
        )
    )
    if isinstance(persona_ref, dict):
        if persona_ref.get("config_key") != "persona":
            issues.append(
                _issue(VOICE_CONFIG_SCHEMA_INVALID, "persona_ref.config_key", "必须引用 persona")
            )
        issues.extend(_check_int_range(persona_ref.get("version"), "persona_ref.version", 1))
        if not isinstance(persona_ref.get("content_sha256"), str) or not _SHA256_RE.fullmatch(
            persona_ref.get("content_sha256", "")
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "persona_ref.content_sha256",
                    "必须是已发布人格正文的 sha256",
                )
            )

    s2s = config.get("s2s")
    s2s_required = {
        "provider",
        "endpoint",
        "resource_id",
        "model_version",
        "adapter_version",
        "protocol_profile",
        "credential_ref",
        "credential_revision_ref",
        "connect_timeout_ms",
        "start_session_timeout_ms",
        "max_retries",
        "retry_backoff_ms",
    }
    issues.extend(_check_exact_keys(s2s, "s2s", required=s2s_required))
    if isinstance(s2s, dict):
        for field in (
            "provider",
            "endpoint",
            "resource_id",
            "model_version",
            "adapter_version",
            "protocol_profile",
            "credential_ref",
        ):
            if not isinstance(s2s.get(field), str) or not s2s.get(field):
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"s2s.{field}", "必须是非空字符串"))
        credential_ref = s2s.get("credential_ref")
        if isinstance(credential_ref, str) and not _ENV_REF_RE.fullmatch(credential_ref):
            issues.append(
                _issue(
                    VOICE_CONFIG_SECRET_FORBIDDEN,
                    "s2s.credential_ref",
                    "credential_ref 只能是环境变量名，不能是凭据值",
                )
            )
        credential_revision_ref = s2s.get("credential_revision_ref")
        if credential_revision_ref is not None and (
            not isinstance(credential_revision_ref, str)
            or not credential_revision_ref.strip()
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "s2s.credential_revision_ref",
                    "只能是非空字符串或 null",
                )
            )
        endpoint = s2s.get("endpoint")
        if isinstance(endpoint, str):
            try:
                parsed = urlparse(endpoint)
                parsed_host = parsed.hostname
                parsed.port
            except ValueError:
                parsed = None
                parsed_host = None
            if (
                parsed is None
                or parsed.scheme not in {"wss", "https"}
                or not parsed.netloc
                or not parsed_host
            ):
                issues.append(
                    _issue(VOICE_CONFIG_SCHEMA_INVALID, "s2s.endpoint", "必须是 wss/https URL")
                )
            if parsed is not None and (
                parsed.username is not None or parsed.password is not None
            ):
                issues.append(
                    _issue(
                        VOICE_CONFIG_SECRET_FORBIDDEN,
                        "s2s.endpoint",
                        "endpoint 禁止在 URL userinfo 中携带认证信息",
                    )
                )
            sensitive_query_names = {
                "access_key",
                "access_token",
                "api_key",
                "api_secret",
                "app_key",
                "auth",
                "authorization",
                "credential",
                "id_token",
                "jwt",
                "password",
                "refresh_token",
                "secret",
                "sign",
                "signature",
                "token",
            }
            query_items = (
                parse_qsl(parsed.query, keep_blank_values=True)
                if parsed is not None
                else []
            )
            sensitive_query = {
                key.casefold()
                for key, _ in query_items
                if re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
                in sensitive_query_names
            }
            query_values = [
                value for _, value in query_items
            ]
            known_credential_values = _credential_env_values()
            contains_known_credential = any(
                secret in endpoint
                for secret in known_credential_values
            )
            contains_sensitive_query_value = any(
                value in known_credential_values or _SECRET_VALUE_RE.search(value)
                for value in query_values
            )
            if sensitive_query or contains_known_credential or contains_sensitive_query_value:
                issues.append(
                    _issue(
                        VOICE_CONFIG_SECRET_FORBIDDEN,
                        "s2s.endpoint",
                        "endpoint 禁止携带 Token、签名或认证查询参数",
                    )
                )
        issues.extend(_check_int_range(s2s.get("connect_timeout_ms"), "s2s.connect_timeout_ms", 5000, 30000))
        issues.extend(
            _check_int_range(
                s2s.get("start_session_timeout_ms"),
                "s2s.start_session_timeout_ms",
                5000,
                30000,
            )
        )
        issues.extend(_check_int_range(s2s.get("max_retries"), "s2s.max_retries", 0, 10))
        backoff = s2s.get("retry_backoff_ms")
        if not isinstance(backoff, list) or not backoff or any(
            type(item) is not int or item < 0 for item in backoff
        ):
            issues.append(
                _issue(VOICE_CONFIG_FIELD_RANGE_INVALID, "s2s.retry_backoff_ms", "必须是非负整数数组")
            )

    voice = config.get("voice")
    voice_required = {
        "voice_id",
        "voice_version",
        "candidates",
        "persona_mapping",
        "speech_rate",
        "loudness_rate",
        "expressive",
        "tone_instruction",
    }
    issues.extend(_check_exact_keys(voice, "voice", required=voice_required))
    if isinstance(voice, dict):
        for field in ("voice_id", "voice_version"):
            if not isinstance(voice.get(field), str) or not voice.get(field):
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"voice.{field}", "必须是非空字符串"))
        issues.extend(_check_int_range(voice.get("speech_rate"), "voice.speech_rate", -50, 100))
        issues.extend(_check_int_range(voice.get("loudness_rate"), "voice.loudness_rate", -50, 100))
        if type(voice.get("expressive")) is not bool:
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "voice.expressive", "必须是布尔值"))
        candidates = voice.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "voice.candidates", "必须是非空数组"))
        else:
            candidate_ids: list[str] = []
            for index, item in enumerate(candidates):
                field = f"voice.candidates[{index}]"
                issues.extend(
                    _check_exact_keys(
                        item,
                        field,
                        required={"voice_id", "voice_version", "enabled"},
                    )
                )
                if not isinstance(item, dict):
                    continue
                for name in ("voice_id", "voice_version"):
                    if not isinstance(item.get(name), str) or not item.get(name).strip():
                        issues.append(
                            _issue(
                                VOICE_CONFIG_SCHEMA_INVALID,
                                f"{field}.{name}",
                                "必须是非空字符串",
                            )
                        )
                if type(item.get("enabled")) is not bool:
                    issues.append(
                        _issue(
                            VOICE_CONFIG_SCHEMA_INVALID,
                            f"{field}.enabled",
                            "必须是布尔值",
                        )
                    )
                if isinstance(item.get("voice_id"), str):
                    candidate_ids.append(item["voice_id"])
            if len(set(candidate_ids)) != len(candidate_ids):
                issues.append(
                    _issue(VOICE_CONFIG_SCHEMA_INVALID, "voice.candidates", "voice_id 必须唯一")
                )
        if not isinstance(voice.get("persona_mapping"), dict):
            issues.append(
                _issue(VOICE_CONFIG_SCHEMA_INVALID, "voice.persona_mapping", "必须是对象")
            )
        if not isinstance(voice.get("tone_instruction"), str):
            issues.append(
                _issue(VOICE_CONFIG_SCHEMA_INVALID, "voice.tone_instruction", "必须是字符串")
            )

    capabilities = config.get("capabilities")
    if not isinstance(capabilities, dict):
        issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "capabilities", "必须是对象"))
    else:
        actual = set(capabilities)
        for key in sorted(set(VOICE_CAPABILITY_KEYS) - actual):
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"capabilities.{key}", "缺少六能力初始态"))
        for key in sorted(actual - set(VOICE_CAPABILITY_KEYS)):
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"capabilities.{key}", "未知能力位"))
        capability_fields = {
            "verification_status",
            "enabled",
            "forced_enabled",
            "effective_scope",
            "fallback_mode",
            "provider_profile",
            "model_version",
            "protocol_profile",
            "adapter_version",
            "sdk_version",
            "evidence_suite_version",
            "evidence_fingerprint",
            "evidence_ttl_days",
            "verified_at",
            "expires_at",
            "evidence_report_id",
            "last_test_result",
        }
        for capability_key in VOICE_CAPABILITY_KEYS:
            item = capabilities.get(capability_key)
            issues.extend(
                _check_exact_keys(
                    item,
                    f"capabilities.{capability_key}",
                    required=capability_fields,
                )
            )
            if not isinstance(item, dict):
                continue
            status = item.get("verification_status")
            scope = item.get("effective_scope")
            for boolean_field in ("enabled", "forced_enabled"):
                if type(item.get(boolean_field)) is not bool:
                    issues.append(
                        _issue(
                            VOICE_CONFIG_SCHEMA_INVALID,
                            f"capabilities.{capability_key}.{boolean_field}",
                            "必须是布尔值",
                        )
                    )
            if not isinstance(item.get("fallback_mode"), str) or not item.get(
                "fallback_mode"
            ).strip():
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"capabilities.{capability_key}.fallback_mode",
                        "必须是非空字符串",
                    )
                )
            for optional_string_field in (
                "provider_profile",
                "model_version",
                "protocol_profile",
                "adapter_version",
                "sdk_version",
                "evidence_suite_version",
                "evidence_fingerprint",
                "verified_at",
                "expires_at",
                "evidence_report_id",
            ):
                field_value = item.get(optional_string_field)
                if field_value is not None and (
                    not isinstance(field_value, str) or not field_value.strip()
                ):
                    issues.append(
                        _issue(
                            VOICE_CONFIG_SCHEMA_INVALID,
                            f"capabilities.{capability_key}.{optional_string_field}",
                            "只能是非空字符串或 null",
                        )
                    )
            last_test_result = item.get("last_test_result")
            if not isinstance(last_test_result, str) or last_test_result not in (
                "not_run",
                "passed",
                "failed",
                "error",
            ):
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"capabilities.{capability_key}.last_test_result",
                        "测试结果枚举无效",
                        allowed=["not_run", "passed", "failed", "error"],
                    )
                )
            if status == "verified":
                issues.append(
                    _issue(
                        VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                        f"capabilities.{capability_key}.verification_status",
                        "STEP-005 禁止管理员手工提交 verified；只能由证据链投影",
                    )
                )
            elif not isinstance(status, str) or status not in (
                "unverified",
                "failed",
                "stale",
            ):
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"capabilities.{capability_key}.verification_status",
                        "能力状态无效",
                    )
                )
            if not isinstance(scope, str) or scope not in ("off", "test", "all"):
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"capabilities.{capability_key}.effective_scope",
                        "effective_scope 只接受 off/test/all",
                    )
                )
            if isinstance(status, str) and status in ("failed", "stale"):
                issues.append(
                    _issue(
                        VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                        f"capabilities.{capability_key}.verification_status",
                        "STEP-005 的能力状态只能保持 unverified；failed/stale 由证据服务投影",
                    )
                )
            if isinstance(scope, str) and scope in ("test", "all"):
                issues.append(
                    _issue(
                        VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                        f"capabilities.{capability_key}.effective_scope",
                        "本 STEP 无有效证据，effective_scope 必须保持 off",
                    )
                )
            for boolean_field in ("enabled", "forced_enabled"):
                if item.get(boolean_field) is True:
                    issues.append(
                        _issue(
                            VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                            f"capabilities.{capability_key}.{boolean_field}",
                            "本 STEP 无有效证据，能力启用字段必须保持 false",
                        )
                    )
            for projection_field in (
                "provider_profile",
                "model_version",
                "protocol_profile",
                "adapter_version",
                "sdk_version",
                "evidence_suite_version",
                "evidence_fingerprint",
                "verified_at",
                "expires_at",
                "evidence_report_id",
            ):
                if item.get(projection_field) is not None:
                    issues.append(
                        _issue(
                            VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                            f"capabilities.{capability_key}.{projection_field}",
                            "能力证据投影为服务端只读字段，STEP-005 必须保持 null",
                        )
                    )
            if isinstance(last_test_result, str) and last_test_result in (
                "passed",
                "failed",
                "error",
            ):
                issues.append(
                    _issue(
                        VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN,
                        f"capabilities.{capability_key}.last_test_result",
                        "能力测试结果为服务端只读字段，STEP-005 必须保持 not_run",
                    )
                )
            issues.extend(
                _check_int_range(
                    item.get("evidence_ttl_days"),
                    f"capabilities.{capability_key}.evidence_ttl_days",
                    7,
                    90,
                )
            )

    quota = config.get("quota")
    issues.extend(
        _check_exact_keys(
            quota,
            "quota",
            required={"daily_free_seconds", "grace_seconds", "hard_limit_seconds", "timezone"},
        )
    )
    if isinstance(quota, dict):
        issues.extend(_check_int_range(quota.get("daily_free_seconds"), "quota.daily_free_seconds", 0))
        issues.extend(_check_int_range(quota.get("grace_seconds"), "quota.grace_seconds", 0, 30))
        issues.extend(_check_int_range(quota.get("hard_limit_seconds"), "quota.hard_limit_seconds", 1))
        if quota.get("timezone") != "Asia/Shanghai":
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "quota.timezone", "必须是 Asia/Shanghai"))

    growth = config.get("growth")
    issues.extend(
        _check_exact_keys(
            growth,
            "growth",
            required={"segment_seconds", "points_per_segment", "daily_limit_points", "timezone"},
        )
    )
    if isinstance(growth, dict):
        for field in ("segment_seconds", "points_per_segment"):
            issues.extend(_check_int_range(growth.get(field), f"growth.{field}", 1))
        issues.extend(_check_int_range(growth.get("daily_limit_points"), "growth.daily_limit_points", 0))
        if growth.get("timezone") != "Asia/Shanghai":
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "growth.timezone", "必须是 Asia/Shanghai"))

    if "interaction" in config:
        interaction = config["interaction"]
        issues.extend(_check_exact_keys(interaction, "interaction", required=set(),
                                        allowed=set(VOICE_INTERACTION_DEFAULTS)))
        if isinstance(interaction, dict):
            effective = {**VOICE_INTERACTION_DEFAULTS, **interaction}
            rms = effective["vad_rms_threshold"]
            # A positive bounded comparison also rejects NaN.
            if isinstance(rms, bool) or not isinstance(rms, (int, float)) or not 0.001 <= rms <= 0.2:
                issues.append(_issue(VOICE_CONFIG_FIELD_RANGE_INVALID, "interaction.vad_rms_threshold",
                                     "RMS 阈值必须为 0.001～0.2 的有限数值"))
            for field, lower, upper in (
                ("candidate_ms", 180, 250), ("sustained_ms", 250, 2000),
                ("post_playback_buffer_ms", 0, 3000), ("goodbye_timeout_ms", 1000, 30000), ("time_low_seconds", 1, 300),
            ):
                issues.extend(_check_int_range(effective[field], f"interaction.{field}", lower, upper))
            candidate, sustained = effective["candidate_ms"], effective["sustained_ms"]
            if type(candidate) is int and type(sustained) is int and sustained <= candidate:
                issues.append(_issue(VOICE_CONFIG_FIELD_RANGE_INVALID, "interaction.sustained_ms",
                                     "持续表达阈值必须大于候选窗口"))

    concurrency = config.get("concurrency")
    issues.extend(_check_exact_keys(concurrency, "concurrency", required={"global_limit"},
                                    allowed={"global_limit", *VOICE_CONNECTION_DEFAULTS}))
    if isinstance(concurrency, dict):
        issues.extend(_check_int_range(concurrency.get("global_limit"), "concurrency.global_limit", 1))
        effective = {**VOICE_CONNECTION_DEFAULTS, **concurrency}
        for field, lower, upper in (
            ("heartbeat_interval_ms", 1000, 10000),
            ("user_lock_ttl_ms", 10000, 60000),
            ("reconnect_timeout_ms", 1000, 60000),
            ("call_ticket_ttl_ms", 5000, 60000),
        ):
            issues.extend(_check_int_range(effective[field], f"concurrency.{field}", lower, upper))
        heartbeat, ttl = effective["heartbeat_interval_ms"], effective["user_lock_ttl_ms"]
        if type(heartbeat) is int and type(ttl) is int and ttl < 3 * heartbeat:
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "concurrency.user_lock_ttl_ms",
                                 "用户锁 TTL 必须至少为心跳间隔的 3 倍"))

    followup = config.get("followup")
    issues.extend(
        _check_exact_keys(
            followup,
            "followup",
            required={"summary_min_effective_seconds", "schedule"},
        )
    )
    if isinstance(followup, dict):
        issues.extend(
            _check_int_range(
                followup.get("summary_min_effective_seconds"),
                "followup.summary_min_effective_seconds",
                1,
            )
        )
        issues.extend(validate_followup_schedule(followup.get("schedule")))

    retention = config.get("retention")
    retention_fields = {
        "effective_transcript_days",
        "generated_debug_days",
        "reasoning_days",
        "crisis_raw_days",
        "job_log_days",
    }
    issues.extend(_check_exact_keys(retention, "retention", required=retention_fields))
    if isinstance(retention, dict):
        for field in retention_fields:
            issues.extend(_check_int_range(retention.get(field), f"retention.{field}", 1))
    return issues


def _validate_voice_call_script(config: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required_top = {
        "schema_version",
        "context_pack",
        "call_answer",
        "recall",
        "memory",
        "barge_in",
        "silence_and_exit",
        "followup",
        "end_reason",
        "reconnect_bridge",
        "crisis",
    }
    issues.extend(_check_exact_keys(config, "script", required=required_top, allowed=required_top | {"summary"}))
    if "summary" in config:
        field = "model" if "s2s" in required_top else "prompt_template"
        value = config["summary"]
        issues.extend(_check_exact_keys(value, "summary", required={field}))
        if isinstance(value, dict):
            content = value.get(field)
            if not isinstance(content, str) or not content.strip():
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "summary." + field, "不得为空"))
            elif field == "model" and (len(content) > 128 or not re.fullmatch(r"deepseek-[A-Za-z0-9._-]+", content)):
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "summary.model", "必须为 DeepSeek 模型标识，不能填写 URL 或密钥"))
    if config.get("schema_version") != VOICE_CONFIG_SCHEMA_VERSION:
        issues.append(
            _issue(
                VOICE_CONFIG_SCHEMA_INVALID,
                "schema_version",
                "未知或不兼容 schema_version",
                allowed=[VOICE_CONFIG_SCHEMA_VERSION],
            )
        )
    section_fields = {
        "context_pack": {
            "voice_instruction_template",
            "fallback_template_sections",
            "persona_max_chars",
            "dynamic_max_chars",
            "recent_dialog_max_chars",
            "memory_max_items",
            "memory_lookback_days",
            "build_budget_ms",
            "ready_barrier_enabled",
        },
        "call_answer": {
            "prompt_template",
            "failure_fallback",
            "min_ring_seconds",
            "max_wait_seconds",
            "fallback_delay_min_seconds",
            "fallback_delay_max_seconds",
        },
        "recall": {
            "prompt_template",
            "trigger_rules",
            "max_query_chars",
            "top_k",
            "score_threshold",
            "timeout_ms",
            "embedding_timeout_ms",
            "vector_timeout_ms",
        },
        "memory": {"prompt_template", "max_items_per_turn"},
        "barge_in": {"weak_acknowledgements", "strong_interruptions", "upgrade_connectors"},
        "silence_and_exit": {
            "exit_intent_template",
            "silence_timeout_template",
            "silence_confirm_seconds",
            "silence_hangup_seconds",
            "user_resume_cancels_exit",
        },
        "followup": {"missed_explanation_template"},
        "end_reason": {
            "user_hangup",
            "user_cancel",
            "exit_intent",
            "silence_timeout",
            "quota_exhausted",
            "hard_limit",
            "reconnect_timeout",
            "provider_error",
            "system_error",
        },
        "reconnect_bridge": {"success_template"},
        "crisis": {"region", "in_call_banner", "post_call_resource_card"},
    }
    for section, fields in section_fields.items():
        allowed = fields | {'max_retries', 'retry_backoff_ms'} if section == 'memory' else fields
        issues.extend(_check_exact_keys(config.get(section), section, required=fields, allowed=allowed))

    context_pack = config.get("context_pack")
    if isinstance(context_pack, dict):
        if not isinstance(context_pack.get("voice_instruction_template"), str):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "context_pack.voice_instruction_template",
                    "必须是字符串",
                )
            )
        for field in (
            "persona_max_chars",
            "dynamic_max_chars",
            "recent_dialog_max_chars",
            "memory_max_items",
            "memory_lookback_days",
            "build_budget_ms",
        ):
            issues.extend(_check_int_range(context_pack.get(field), f"context_pack.{field}", 1))
        if type(context_pack.get("ready_barrier_enabled")) is not bool:
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "context_pack.ready_barrier_enabled",
                    "必须是布尔值",
                )
            )
        fallback_sections = context_pack.get("fallback_template_sections")
        if not isinstance(fallback_sections, list) or not fallback_sections or any(
            not isinstance(item, str) or not item.strip() for item in fallback_sections
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "context_pack.fallback_template_sections",
                    "必须是非空字符串数组",
                )
            )
        dynamic_max = context_pack.get("dynamic_max_chars")
        recent_max = context_pack.get("recent_dialog_max_chars")
        if type(dynamic_max) is int and type(recent_max) is int and recent_max > dynamic_max:
            issues.append(
                _issue(
                    VOICE_CONFIG_FIELD_RANGE_INVALID,
                    "context_pack.recent_dialog_max_chars",
                    "最近对话预算不得大于动态小包总预算",
                    allowed={"max_field": "context_pack.dynamic_max_chars"},
                )
            )

    call_answer = config.get("call_answer")
    if isinstance(call_answer, dict):
        if not isinstance(call_answer.get("prompt_template"), str):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "call_answer.prompt_template",
                    "必须是字符串",
                )
            )
        for field in (
            "min_ring_seconds",
            "max_wait_seconds",
            "fallback_delay_min_seconds",
            "fallback_delay_max_seconds",
        ):
            issues.extend(_check_int_range(call_answer.get(field), f"call_answer.{field}", 1))
        if call_answer.get("failure_fallback") != "answer":
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "call_answer.failure_fallback",
                    "CALL-01 失败兜底必须为 answer",
                    allowed=["answer"],
                )
            )
        min_ring = call_answer.get("min_ring_seconds")
        max_wait = call_answer.get("max_wait_seconds")
        fallback_min = call_answer.get("fallback_delay_min_seconds")
        fallback_max = call_answer.get("fallback_delay_max_seconds")
        if type(min_ring) is int and type(max_wait) is int and min_ring >= max_wait:
            issues.append(
                _issue(
                    VOICE_CONFIG_FIELD_RANGE_INVALID,
                    "call_answer.min_ring_seconds",
                    "最短响铃必须小于最大等待",
                    allowed={"strictly_less_than_field": "call_answer.max_wait_seconds"},
                )
            )
        if (
            type(fallback_min) is int
            and type(fallback_max) is int
            and fallback_min > fallback_max
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_FIELD_RANGE_INVALID,
                    "call_answer.fallback_delay_min_seconds",
                    "兜底延迟下界不得大于上界",
                    allowed={"max_field": "call_answer.fallback_delay_max_seconds"},
                )
            )

    recall = config.get("recall")
    if isinstance(recall, dict):
        if not isinstance(recall.get("prompt_template"), str):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "recall.prompt_template",
                    "必须是字符串",
                )
            )
        for field in (
            "max_query_chars",
            "top_k",
            "timeout_ms",
            "embedding_timeout_ms",
            "vector_timeout_ms",
        ):
            issues.extend(_check_int_range(recall.get(field), f"recall.{field}", 1))
        issues.extend(
            _check_number_range(
                recall.get("score_threshold"),
                "recall.score_threshold",
                0.0,
                1.0,
            )
        )

    memory = config.get("memory")
    if isinstance(memory, dict):
        retries = memory.get('max_retries', 2)
        delays = memory.get('retry_backoff_ms', [1000, 5000])
        if (type(retries) is not int or not 0 <= retries <= 5 or
                not isinstance(delays, list) or len(delays) != retries or
                any(type(delay) is not int or not 100 <= delay <= 60000 for delay in delays) or
                delays != sorted(delays)):
            issues.append(_issue(VOICE_CONFIG_FIELD_RANGE_INVALID, 'memory.retry_backoff_ms',
                'max_retries为0～5；退避数组与次数等长、非递减，每项100～60000毫秒'))
        if not isinstance(memory.get("prompt_template"), str):
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "memory.prompt_template",
                    "必须是字符串",
                )
            )
        issues.extend(
            _check_int_range(
                memory.get("max_items_per_turn"),
                "memory.max_items_per_turn",
                1,
            )
        )

    silence = config.get("silence_and_exit")
    if isinstance(silence, dict):
        for field in ("exit_intent_template", "silence_timeout_template"):
            value = silence.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"silence_and_exit.{field}",
                        "必须是非空字符串",
                    )
                )
        issues.extend(
            _check_int_range(
                silence.get("silence_confirm_seconds"),
                "silence_and_exit.silence_confirm_seconds",
                1,
            )
        )
        issues.extend(
            _check_int_range(
                silence.get("silence_hangup_seconds"),
                "silence_and_exit.silence_hangup_seconds",
                1,
            )
        )
        if type(silence.get("user_resume_cancels_exit")) is not bool:
            issues.append(
                _issue(
                    VOICE_CONFIG_SCHEMA_INVALID,
                    "silence_and_exit.user_resume_cancels_exit",
                    "必须是布尔值",
                )
            )
        confirm_seconds = silence.get("silence_confirm_seconds")
        hangup_seconds = silence.get("silence_hangup_seconds")
        if (
            type(confirm_seconds) is int
            and type(hangup_seconds) is int
            and confirm_seconds >= hangup_seconds
        ):
            issues.append(
                _issue(
                    VOICE_CONFIG_FIELD_RANGE_INVALID,
                    "silence_and_exit.silence_confirm_seconds",
                    "静音确认必须早于静音挂断",
                    allowed={
                        "strictly_less_than_field": "silence_and_exit.silence_hangup_seconds"
                    },
                )
            )

    if isinstance(config.get("followup"), dict):
        missed = config["followup"].get("missed_explanation_template")
        if not isinstance(missed, str) or not missed.strip():
            issues.append(
                _issue(VOICE_CONFIG_SCHEMA_INVALID, "followup.missed_explanation_template", "不得为空")
            )
    if isinstance(config.get("reconnect_bridge"), dict):
        bridge = config["reconnect_bridge"].get("success_template")
        if not isinstance(bridge, str) or not bridge.strip():
            issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "reconnect_bridge.success_template", "不得为空"))

    end_reason = config.get("end_reason")
    if isinstance(end_reason, dict):
        for field in (
            "user_hangup",
            "exit_intent",
            "silence_timeout",
            "quota_exhausted",
            "hard_limit",
            "reconnect_timeout",
        ):
            value = end_reason.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        f"end_reason.{field}",
                        "必须是非空字符串",
                    )
                )

        user_cancel = end_reason.get("user_cancel")
        issues.extend(
            _check_exact_keys(
                user_cancel,
                "end_reason.user_cancel",
                required={"show_end_page", "action"},
            )
        )
        if isinstance(user_cancel, dict):
            if user_cancel.get("show_end_page") is not False:
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        "end_reason.user_cancel.show_end_page",
                        "用户取消不得展示结束页",
                        allowed=[False],
                    )
                )
            if user_cancel.get("action") != "return_to_chat":
                issues.append(
                    _issue(
                        VOICE_CONFIG_SCHEMA_INVALID,
                        "end_reason.user_cancel.action",
                        "用户取消必须直接返回聊天",
                        allowed=["return_to_chat"],
                    )
                )

        for category in ("provider_error", "system_error"):
            value = end_reason.get(category)
            issues.extend(
                _check_exact_keys(
                    value,
                    f"end_reason.{category}",
                    required={"before_connected", "after_connected"},
                )
            )
            if isinstance(value, dict):
                for phase in ("before_connected", "after_connected"):
                    message = value.get(phase)
                    if not isinstance(message, str) or not message.strip():
                        issues.append(
                            _issue(
                                VOICE_CONFIG_SCHEMA_INVALID,
                                f"end_reason.{category}.{phase}",
                                "必须是非空字符串",
                            )
                        )

    if isinstance(config.get("crisis"), dict):
        for field in ("region", "in_call_banner", "post_call_resource_card"):
            value = config["crisis"].get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"crisis.{field}", "不得为空"))
    for section, fields in (
        ("barge_in", ("weak_acknowledgements", "strong_interruptions", "upgrade_connectors")),
        ("recall", ("trigger_rules",)),
    ):
        value = config.get(section)
        if not isinstance(value, dict):
            continue
        for field in fields:
            items = value.get(field)
            if not isinstance(items, list) or not items or any(
                not isinstance(item, str) or not item.strip() for item in items
            ):
                issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, f"{section}.{field}", "必须是非空字符串数组"))
    return issues


def validate_voice_bundle(config_key: str, config: Any) -> list[dict[str, Any]]:
    """校验完整两-key bundle；返回结构化错误，不修改输入。"""

    if not isinstance(config, dict):
        return [_issue(VOICE_CONFIG_SCHEMA_INVALID, "config", "整包必须是 JSON 对象")]
    issues = _scan_forbidden_fields(config)
    if config_key == VOICE_CALL_CONFIG_KEY:
        issues.extend(_validate_voice_call_config(config))
    elif config_key == VOICE_CALL_SCRIPT_KEY:
        issues.extend(_validate_voice_call_script(config))
    else:
        issues.append(_issue(VOICE_CONFIG_SCHEMA_INVALID, "config_key", "未知语音配置 key"))
    return issues


def _trusted_capability_state_issues(config: Any) -> list[dict[str, Any]]:
    """校验服务端证据投影的运行状态组合，不授予管理员投影写权。"""

    if not isinstance(config, dict) or not isinstance(config.get("capabilities"), dict):
        return []

    issues: list[dict[str, Any]] = []
    for capability_key in VOICE_CAPABILITY_KEYS:
        capability = config["capabilities"].get(capability_key)
        if not isinstance(capability, dict):
            continue
        field_prefix = f"capabilities.{capability_key}"
        status = capability.get("verification_status")
        enabled = capability.get("enabled")
        forced = capability.get("forced_enabled")
        scope = capability.get("effective_scope")

        if status in {"unverified", "stale"}:
            valid_state = (
                enabled is False and forced is False and scope == "off"
            ) or (
                enabled is True and forced is True and scope == "test"
            )
            if not valid_state:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_TRUSTED_STATE_INVALID,
                        field_prefix,
                        "unverified/stale 只能关闭，或由内部受审计流程强制到 test",
                        allowed=[
                            {"enabled": False, "forced_enabled": False, "effective_scope": "off"},
                            {"enabled": True, "forced_enabled": True, "effective_scope": "test"},
                        ],
                    )
                )
        elif status == "failed":
            if not (enabled is False and forced is False and scope == "off"):
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_TRUSTED_STATE_INVALID,
                        field_prefix,
                        "failed 能力必须保持关闭，且禁止强制启用",
                        allowed={
                            "enabled": False,
                            "forced_enabled": False,
                            "effective_scope": "off",
                        },
                    )
                )
        elif status == "verified":
            valid_state = forced is False and (
                (enabled is False and scope == "off")
                or (enabled is True and scope in {"test", "all"})
            )
            if not valid_state:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_TRUSTED_STATE_INVALID,
                        field_prefix,
                        "verified 能力只能关闭或启用到 test/all，且不得保留强制标记",
                    )
                )
            required_projection = (
                *_CAPABILITY_EVIDENCE_DIMENSION_FIELDS,
                "evidence_fingerprint",
                "verified_at",
                "expires_at",
                "evidence_report_id",
            )
            missing_projection = [
                field
                for field in required_projection
                if not isinstance(capability.get(field), str)
                or not capability[field].strip()
            ]
            if missing_projection or capability.get("last_test_result") != "passed":
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_TRUSTED_STATE_INVALID,
                        field_prefix,
                        "verified 投影必须包含完整证据引用、六维、时间与 passed 结果",
                    )
                )
    return issues


def validate_trusted_voice_bundle(config_key: str, config: Any) -> list[dict[str, Any]]:
    """校验已经由服务端持久化的配置，并接受合法的只读能力投影。

    默认的 :func:`validate_voice_bundle` 仍是管理员输入边界，会拒绝所有服务端
    证据字段。只有数据库既有配置、发布/回滚和内部能力状态机可以调用本函数。
    """

    issues = [
        issue
        for issue in validate_voice_bundle(config_key, config)
        if issue.get("code") != VOICE_CONFIG_MANUAL_VERIFIED_FORBIDDEN
    ]
    if config_key == VOICE_CALL_CONFIG_KEY:
        issues.extend(_trusted_capability_state_issues(config))
    return issues


def _capability_projection_forgery_issues(
    previous: Any,
    submitted: Any,
) -> list[dict[str, Any]]:
    """拒绝普通 capabilities PATCH 改写服务端拥有的证据投影字段。"""

    if not isinstance(previous, dict) or not isinstance(submitted, dict):
        return []
    issues: list[dict[str, Any]] = []
    for capability_key in VOICE_CAPABILITY_KEYS:
        old_capability = previous.get(capability_key)
        new_capability = submitted.get(capability_key)
        if not isinstance(old_capability, dict) or not isinstance(new_capability, dict):
            continue
        for field in sorted(_CAPABILITY_SERVER_OWNED_FIELDS):
            if new_capability.get(field) != old_capability.get(field):
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_PROJECTION_FORGED,
                        f"capabilities.{capability_key}.{field}",
                        "该能力字段由服务端证据链拥有，普通草稿保存不得修改",
                    )
                )
    return issues


def _parse_json_value(row: AdminConfig | None) -> Any:
    if row is None or not row.config_value:
        return None
    try:
        return json.loads(row.config_value)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_config_value(row: AdminConfig | None) -> dict[str, Any] | None:
    parsed = _parse_json_value(row)
    return parsed if isinstance(parsed, dict) else None


def _normalized_evidence_datetime(value: Any) -> datetime | None:
    """把证据行/JSON 时间统一为 UTC naive，兼容数据库无时区 DateTime。"""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _changed_sections(active: dict[str, Any] | None, draft: dict[str, Any] | None) -> list[str]:
    if draft is None:
        return []
    active = active or {}
    return sorted(
        key
        for key in set(active) | set(draft)
        if key != "schema_version" and active.get(key) != draft.get(key)
    )


def _project_credential(config: dict[str, Any], role: str) -> dict[str, Any]:
    projected = deepcopy(config)
    if "s2s" not in projected or not isinstance(projected["s2s"], dict):
        return projected
    ref = projected["s2s"].get("credential_ref")
    configured = bool(ref and isinstance(ref, str) and os.getenv(ref))
    projected["s2s"]["credential_configured"] = configured
    projected["s2s"].pop("credential_revision_ref", None)
    if role not in {"super_admin", "tech_ops"}:
        projected["s2s"].pop("credential_ref", None)
    return projected


def project_voice_snapshot_for_role(snapshot: Any, role: str) -> Any:
    """Project frozen call snapshots without changing their stored contents.

    Credential status describes the current environment, not historical call
    connectivity. Reuse the config role policy at every credential-bearing node.
    """
    from backend.utils.credential_redaction import redact_credentials

    def project(value: Any, *, is_s2s: bool = False) -> Any:
        if isinstance(value, dict):
            if is_s2s or "credential_ref" in value or "credential_revision_ref" in value:
                value = _project_credential({"s2s": value}, role)["s2s"]
            return {key: project(item, is_s2s=key == "s2s") for key, item in value.items()}
        if isinstance(value, list):
            return [project(item) for item in value]
        return value

    return redact_credentials(project(deepcopy(snapshot)))


def _validate_preview_input(value: Any) -> tuple[str, datetime, int] | None:
    if not isinstance(value, dict) or set(value) != {"stage", "candidate_at", "jitter_minutes"}:
        return None
    stage = value.get("stage")
    candidate_at = value.get("candidate_at")
    jitter = value.get("jitter_minutes")
    if stage not in RELATIONSHIP_STAGES or type(jitter) is not int or not 0 <= jitter <= 20:
        return None
    if not isinstance(candidate_at, str):
        return None
    try:
        parsed = datetime.fromisoformat(candidate_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return stage, parsed.astimezone(_SHANGHAI), jitter


def followup_delay_within_limit(
    candidate: datetime,
    resolved_due_at: datetime,
    max_delay_hours: int,
) -> bool:
    """24h 边界使用 ``<=``；单独保留为可直接验证的稳定规则。"""

    return resolved_due_at - candidate <= timedelta(hours=max_delay_hours)


def resolve_followup_preview(
    schedule: dict[str, Any],
    preview: Any,
) -> dict[str, Any]:
    """纯计算解析 follow-up 发送时刻；调用者应先校验 schedule。"""

    parsed_input = _validate_preview_input(preview)
    if parsed_input is None:
        raise VoiceConfigError(
            FOLLOWUP_PREVIEW_INPUT_INVALID,
            "follow-up 预览输入不合法",
            errors=[
                _issue(
                    FOLLOWUP_PREVIEW_INPUT_INVALID,
                    "followup_preview",
                    "stage、带时区 candidate_at 或 0–20 整数 jitter_minutes 不合法",
                )
            ],
        )
    stage, candidate, jitter = parsed_input
    candidate_text = preview["candidate_at"]
    windows = schedule["stages"][stage]["windows"]
    normalized = sorted(
        (_window_minutes(window["start"]), _window_minutes(window["end"]))
        for window in windows
    )

    def bounds(day, start_minute: int, end_minute: int) -> tuple[datetime, datetime]:
        start = datetime(day.year, day.month, day.day, tzinfo=_SHANGHAI) + timedelta(minutes=start_minute)
        end = datetime(day.year, day.month, day.day, tzinfo=_SHANGHAI) + timedelta(minutes=end_minute)
        return start, end

    for start_minute, end_minute in normalized:
        start, end = bounds(candidate.date(), start_minute, end_minute)
        if start <= candidate < end:
            return {
                "stage": stage,
                "candidate_at": candidate_text,
                "resolution": "in_window",
                "in_window": True,
                "resolved_window": {"start_at": start.isoformat(), "end_at": end.isoformat()},
                "jitter_applied_minutes": 0,
                "resolved_due_at": candidate.isoformat(),
                "delay_seconds": 0,
                "cancel_reason": None,
            }

    future_windows: list[tuple[datetime, datetime]] = []
    for day_offset in range(0, 3):
        day = candidate.date() + timedelta(days=day_offset)
        for start_minute, end_minute in normalized:
            start, end = bounds(day, start_minute, end_minute)
            if start > candidate:
                future_windows.append((start, end))
    future_windows.sort(key=lambda item: item[0])
    if future_windows:
        start, end = future_windows[0]
        due = start + timedelta(minutes=jitter)
        delay_seconds = int((due - candidate).total_seconds())
        if followup_delay_within_limit(candidate, due, schedule["max_delay_hours"]):
            return {
                "stage": stage,
                "candidate_at": candidate_text,
                "resolution": "next_window",
                "in_window": False,
                "resolved_window": {"start_at": start.isoformat(), "end_at": end.isoformat()},
                "jitter_applied_minutes": jitter,
                "resolved_due_at": due.isoformat(),
                "delay_seconds": delay_seconds,
                "cancel_reason": None,
            }
        return {
            "stage": stage,
            "candidate_at": candidate_text,
            "resolution": "cancelled",
            "in_window": False,
            "resolved_window": {"start_at": start.isoformat(), "end_at": end.isoformat()},
            "jitter_applied_minutes": jitter,
            "resolved_due_at": None,
            "delay_seconds": delay_seconds,
            "cancel_reason": "max_delay_exceeded",
        }
    return {
        "stage": stage,
        "candidate_at": candidate_text,
        "resolution": "cancelled",
        "in_window": False,
        "resolved_window": None,
        "jitter_applied_minutes": jitter,
        "resolved_due_at": None,
        "delay_seconds": None,
        "cancel_reason": "max_delay_exceeded",
    }


async def _redis_snapshot(redis, key: str) -> tuple[str | None, int]:
    value = await redis.get(key)
    ttl_method = getattr(redis, "ttl", None)
    ttl = await ttl_method(key) if callable(ttl_method) else -1
    return value, int(ttl) if type(ttl) is int else -1


async def _restore_redis(redis, key: str, snapshot: tuple[str | None, int]) -> None:
    value, ttl = snapshot
    if value is None:
        delete_method = getattr(redis, "delete", None)
        if callable(delete_method):
            await delete_method(key)
        return
    if ttl > 0:
        await redis.setex(key, ttl, value)
    else:
        await redis.set(key, value)


def _published_voice_config_envelope(
    *,
    config: Mapping[str, Any],
    version: int,
    published_at: str,
) -> str:
    """构造 AC77 精确 envelope；只接受已通过发布校验的整包输入。"""

    if type(version) is not int or version < 1:
        raise RuntimeError("语音配置发布锚拒绝非法版本")
    if not isinstance(published_at, str) or not published_at:
        raise RuntimeError("语音配置发布锚拒绝非法发布时间")
    try:
        datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("语音配置发布锚拒绝非法发布时间") from exc

    payload = deepcopy(dict(config))
    issues = validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, payload)
    if issues:
        raise RuntimeError("语音配置发布锚拒绝非法整包")
    return canonical_json(
        {
            "envelope_schema_version": _PUBLISHED_ENVELOPE_SCHEMA_VERSION,
            "config_key": VOICE_CALL_CONFIG_KEY,
            "config_version": version,
            "config_schema_version": payload["schema_version"],
            "config_content_sha256": content_sha256(payload),
            "published_at": published_at,
            "config": payload,
        }
    )


async def _write_published_voice_config_envelope(
    redis,
    *,
    config: Mapping[str, Any],
    version: int,
    published_at: str,
) -> str:
    encoded = _published_voice_config_envelope(
        config=config,
        version=version,
        published_at=published_at,
    )
    eval_method = getattr(redis, "eval", None)
    if callable(eval_method):
        result = await eval_method(
            _PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY,
            version,
            encoded,
        )
    else:
        # 仅兼容仓库内不实现 Lua 的旧 Redis 测试替身；生产 redis.asyncio
        # 必须走上面的服务端原子脚本。
        current = await redis.get(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY)
        if current is None:
            await redis.set(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY, encoded)
            result = 1
        else:
            try:
                current_version = json.loads(current)["config_version"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                result = -2
            else:
                if type(current_version) is not int:
                    result = -2
                elif current_version > version:
                    result = 0
                elif current_version == version:
                    result = 2 if current == encoded else -3
                else:
                    await redis.set(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY, encoded)
                    result = 1
    if result not in (0, 1, 2):
        # 不携带 Redis 正文或动态错误；非法/同版本冲突均保持 fail-closed。
        raise RuntimeError("语音配置发布锚原子版本校验失败")
    return encoded


async def _take_published_voice_config_envelope(
    redis,
    *,
    max_version: int,
) -> str | None:
    """原子读取并失效不高于目标版本的旧锚，拒绝删除更新版本。"""

    eval_method = getattr(redis, "eval", None)
    if callable(eval_method):
        result = await eval_method(
            _PUBLISHED_ANCHOR_TAKE_SCRIPT,
            1,
            VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY,
            max_version,
        )
    else:
        current = await redis.get(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY)
        if current is None:
            result = (0, None)
        else:
            try:
                current_version = json.loads(current)["config_version"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                await redis.delete(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY)
                result = (2, None)
            else:
                if type(current_version) is int and current_version > max_version:
                    result = (-1, current)
                else:
                    await redis.delete(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY)
                    result = (1, current) if type(current_version) is int else (2, None)
    if not isinstance(result, (list, tuple)) or len(result) != 2:
        raise RuntimeError("语音配置发布锚原子失效返回非法")
    code, snapshot = result
    if code == -1:
        raise RuntimeError("语音配置发布锚拒绝删除更新版本")
    if code not in (0, 1, 2):
        raise RuntimeError("语音配置发布锚原子失效失败")
    return snapshot if code == 1 and isinstance(snapshot, str) else None


async def _restore_published_voice_config_envelope_if_absent(
    redis,
    snapshot: str | None,
) -> None:
    if snapshot is None:
        return
    eval_method = getattr(redis, "eval", None)
    if callable(eval_method):
        await eval_method(
            _PUBLISHED_ANCHOR_RESTORE_IF_ABSENT_SCRIPT,
            1,
            VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY,
            snapshot,
        )
    elif await redis.get(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY) is None:
        await redis.set(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY, snapshot)


async def _delete_published_voice_config_envelope_if_match(
    redis,
    expected: str,
) -> None:
    eval_method = getattr(redis, "eval", None)
    if callable(eval_method):
        await eval_method(
            _PUBLISHED_ANCHOR_DELETE_IF_MATCH_SCRIPT,
            1,
            VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY,
            expected,
        )
    elif await redis.get(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY) == expected:
        await redis.delete(VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY)


async def _execute_publish_with_compensation(
    db: AsyncSession,
    config_key: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    *,
    published_config: Mapping[str, Any] | None = None,
    published_version: int | None = None,
) -> dict[str, Any]:
    """执行 DB+Redis 发布，并按 AC77 顺序维护最后确认发布锚。"""

    async with _operation_mutex(f"publish:{config_key}"):
        redis = await get_redis()
        cache_key = f"active_config:{config_key}"
        monitor_key = f"publish_monitor:{config_key}"
        cache_snapshot = await _redis_snapshot(redis, cache_key)
        monitor_snapshot = await _redis_snapshot(redis, monitor_key)
        anchor_snapshot: str | None = None
        writes_published_anchor = (
            config_key == VOICE_CALL_CONFIG_KEY and published_config is not None
        )
        if writes_published_anchor and (
            type(published_version) is not int or published_version < 1
        ):
            raise RuntimeError("语音配置发布锚缺少合法预期版本")
        if writes_published_anchor:
            anchor_snapshot = await _take_published_voice_config_envelope(
                redis,
                max_version=published_version - 1,
            )
        try:
            result = await operation()
            if writes_published_anchor and result.get("version") != published_version:
                raise RuntimeError("语音配置发布版本与预期不一致")
            await db.commit()
        except Exception:
            await db.rollback()
            snapshots: list[tuple[str, tuple[str | None, int]]] = [
                (cache_key, cache_snapshot),
                (monitor_key, monitor_snapshot),
            ]
            for key, snapshot in snapshots:
                try:
                    await _restore_redis(redis, key, snapshot)
                except Exception:
                    # Redis 客户端异常可能携带凭据、URL 或响应正文；补偿失败日志
                    # 只发固定摘要，不附异常对象、堆栈或动态 key。
                    logger.error("语音配置发布补偿 Redis 失败")
            if writes_published_anchor:
                try:
                    await _restore_published_voice_config_envelope_if_absent(
                        redis,
                        anchor_snapshot,
                    )
                except Exception:
                    logger.error("语音配置发布补偿 Redis 失败")
            raise

        if writes_published_anchor:
            # commit 成功后才允许发布新锚。这里失败不得恢复旧锚，也不得回滚已
            # 提交 DB；调用方收到失败，同时 runtime 在锚缺失时 fail-closed。
            expected_envelope = _published_voice_config_envelope(
                config=published_config,
                version=published_version,
                published_at=result["published_at"],
            )
            try:
                await _write_published_voice_config_envelope(
                    redis,
                    config=published_config,
                    version=published_version,
                    published_at=result["published_at"],
                )
            except Exception:
                try:
                    await _delete_published_voice_config_envelope_if_match(
                        redis,
                        expected_envelope,
                    )
                except Exception:
                    logger.error("语音配置发布锚清理失败")
                raise
        return result


def _audit_projection(
    *,
    action: str,
    config_key: str,
    config: dict[str, Any],
    version: int | None = None,
    base_version: int | None = None,
    draft_revision: int | None = None,
    changed_sections: list[str] | None = None,
    change_note: str | None = None,
    permission: str | None = None,
    result: str = "success",
    failure_category: str | None = None,
    force_source: Mapping[str, Any] | None = None,
    capability_audit: Mapping[str, Any] | None = None,
) -> str:
    """不含正文和 credential_ref 的审计稳定摘要。"""

    capabilities = config.get("capabilities") if isinstance(config, dict) else None
    if isinstance(capabilities, dict):
        verification_status = {
            key: item.get("verification_status") if isinstance(item, dict) else None
            for key, item in sorted(capabilities.items())
        }
        forced_enabled = {
            key: item.get("forced_enabled") if isinstance(item, dict) else None
            for key, item in sorted(capabilities.items())
        }
        effective_scope = {
            key: item.get("effective_scope") if isinstance(item, dict) else None
            for key, item in sorted(capabilities.items())
        }
    else:
        verification_status = None
        forced_enabled = None
        effective_scope = None
    change_note_summary = None
    if change_note is not None:
        encoded = change_note.encode("utf-8")
        change_note_summary = {
            "present": True,
            "length": len(change_note),
            "sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        }
    projection = {
        "action": action,
        "config_key": config_key,
        "permission": permission,
        "config_version": version,
        "base_version": base_version,
        "draft_revision": draft_revision,
        "changed_sections": changed_sections or [],
        "change_note": change_note_summary,
        "verification_status": verification_status,
        "forced_enabled": forced_enabled,
        "effective_scope": effective_scope,
        "result": result,
        "failure_category": failure_category,
        "content_sha256": content_sha256(config),
    }
    if force_source is not None:
        projection["force_source"] = deepcopy(dict(force_source))
    if capability_audit is not None:
        projection["capability_audit"] = deepcopy(dict(capability_audit))
    return canonical_json(projection)


def _crisis_audit_projection(
    *,
    action: str,
    version: int | None,
    base_version: int | None,
    keyword_count: int,
    keyword_hash: str,
    permission: str,
    target_version: int | None = None,
    result: str = "success",
    failure_category: str | None = None,
) -> str:
    """危机词审计只保存集合计数和哈希，不保存任何词条正文。"""

    return canonical_json(
        {
            "action": action,
            "config_key": CRISIS_KEYWORDS_CONFIG_KEY,
            "permission": permission,
            "config_version": version,
            "base_version": base_version,
            "draft_revision": None,
            "changed_sections": ["keywords"],
            "change_note": None,
            "verification_status": None,
            "forced_enabled": None,
            "effective_scope": None,
            "result": result,
            "failure_category": failure_category,
            "target_version": target_version,
            "keyword_count": keyword_count,
            "content_sha256": keyword_hash,
        }
    )


async def _lock_publish_anchor(
    db: AsyncSession,
    config_key: str,
) -> AdminConfig | None:
    """锁当前 active；首发无行时锁稳定锚点后重新查询，封住 V1 竞态。"""

    active_stmt = (
        select(AdminConfig)
        .where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_active == True,  # noqa: E712
            AdminConfig.is_draft == False,  # noqa: E712
        )
        .with_for_update()
    )
    active = (await db.execute(active_stmt)).scalars().first()
    if active is not None:
        return active

    # persona 是部署初始化必需、长期稳定的配置行；极端情况下再用首个管理员行作
    # 同库互斥锚，避免 crisis_keywords 首发时因“无行可锁”并发生成两个 V1。
    persona_stmt = (
        select(AdminConfig)
        .where(
            AdminConfig.config_key == "persona",
            AdminConfig.is_active == True,  # noqa: E712
            AdminConfig.is_draft == False,  # noqa: E712
        )
        .with_for_update()
    )
    persona = (await db.execute(persona_stmt)).scalars().first()
    if persona is None:
        admin_anchor_stmt = select(AdminUser).order_by(AdminUser.id.asc()).limit(1).with_for_update()
        await db.execute(admin_anchor_stmt)

    # 另一个事务可能在等待锚点期间完成了首发，必须在持锁后重查。
    return (await db.execute(active_stmt)).scalars().first()


async def _validate_published_persona_ref(
    db: AsyncSession,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """验证已发布人格锚；只对明确早于保留窗口的版本按“已裁剪”放行。"""

    persona_ref = config.get("persona_ref")
    if not isinstance(persona_ref, dict):
        return None
    version = persona_ref.get("version")
    expected_sha = persona_ref.get("content_sha256")
    if type(version) is not int or version < 1 or not isinstance(expected_sha, str):
        return None
    rows = (
        await db.execute(
            select(AdminConfig)
            .where(
                AdminConfig.config_key == "persona",
                AdminConfig.is_draft == False,  # noqa: E712
            )
            .order_by(AdminConfig.version.asc())
        )
    ).scalars().all()
    if not rows:
        return _issue(
            VOICE_CONFIG_PERSONA_REF_INVALID,
            "persona_ref",
            "不存在任何已发布 persona 版本",
        )
    matching_rows = [row for row in rows if row.version == version]
    normalized_expected = expected_sha.removeprefix("sha256:")
    if matching_rows:
        actual_hashes = {
            hashlib.sha256((row.config_value or "").encode("utf-8")).hexdigest()
            for row in matching_rows
            if row.config_value is not None
        }
        if normalized_expected not in actual_hashes:
            return _issue(
                VOICE_CONFIG_PERSONA_REF_INVALID,
                "persona_ref.content_sha256",
                "persona_ref 哈希与目标已发布版本不一致",
            )
        return None

    retained_min_version = min(row.version for row in rows)
    retained_max_version = max(row.version for row in rows)
    if version < retained_min_version:
        # AdminConfig 只保留最近 20 版；早于保留窗口的 persona 正文行可能已
        # 物理裁剪。只接受此前已发布 voice_call_config 保存过的同一 version+sha
        # 锚点；不能把“已裁剪”当成任意旧版本/任意哈希的放行旁路。
        voice_rows = (
            await db.execute(
                select(AdminConfig).where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_draft == False,  # noqa: E712
                )
            )
        ).scalars().all()
        for row in voice_rows:
            saved_config = _parse_config_value(row)
            saved_ref = (
                saved_config.get("persona_ref")
                if isinstance(saved_config, dict)
                else None
            )
            if not isinstance(saved_ref, dict):
                continue
            saved_sha = saved_ref.get("content_sha256")
            if (
                saved_ref.get("version") == version
                and isinstance(saved_sha, str)
                and saved_sha.removeprefix("sha256:") == normalized_expected
            ):
                return None
        return _issue(
            VOICE_CONFIG_PERSONA_REF_INVALID,
            "persona_ref.content_sha256",
            "已裁剪 persona 版本只接受已发布语音配置保存过的 version+sha 锚点",
        )
    return _issue(
        VOICE_CONFIG_PERSONA_REF_INVALID,
        "persona_ref.version",
        "persona_ref 未指向现存已发布版本，也不属于已裁剪历史窗口",
        allowed={
            "retained_min_version": retained_min_version,
            "retained_max_version": retained_max_version,
        },
    )


class RealtimeVoiceConfigService:
    """两套语音整包控制面。"""

    def __init__(
        self,
        *,
        current_dimensions_provider: CurrentDimensionsProvider | None = None,
    ) -> None:
        # 三个非配置维度尚无冻结的生产可信来源，因此生产单例保持 None，
        # verified/all 会 fail-closed；受控测试可显式注入真实六维读取器。
        self._current_dimensions_provider = current_dimensions_provider

    @staticmethod
    def resolve_config_key(alias: str) -> str:
        try:
            return VOICE_CONFIG_ALIASES[alias]
        except KeyError as exc:
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "key 只接受 config/script") from exc

    @staticmethod
    def allowed_sections(config_key: str) -> set[str]:
        if config_key == VOICE_CALL_CONFIG_KEY:
            return {
                "global",
                "persona_ref",
                "s2s",
                "voice",
                "capabilities",
                "quota",
                "growth",
                "concurrency",
                "interaction",
                "summary",
                "followup",
                "retention",
            }
        if config_key == VOICE_CALL_SCRIPT_KEY:
            return {
                "context_pack",
                "call_answer",
                "recall",
                "memory",
                "summary",
                "barge_in",
                "silence_and_exit",
                "followup",
                "end_reason",
                "reconnect_bridge",
                "crisis",
            }
        return set()

    @staticmethod
    def summary_defaults(config_key):
        from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL, DEFAULT_VOICE_SUMMARY_PROMPT
        return ({"model": DEFAULT_VOICE_SUMMARY_MODEL} if config_key == VOICE_CALL_CONFIG_KEY
                else {"prompt_template": DEFAULT_VOICE_SUMMARY_PROMPT})

    async def _active(
        self,
        db: AsyncSession,
        config_key: str,
        *,
        lock: bool = False,
    ) -> AdminConfig | None:
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_active == True,  # noqa: E712
            AdminConfig.is_draft == False,  # noqa: E712
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def _draft(
        self,
        db: AsyncSession,
        config_key: str,
        *,
        lock: bool = False,
    ) -> AdminConfig | None:
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == True,  # noqa: E712
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def _log_failed_config_operation(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        action: str,
        error: VoiceConfigError,
        admin_user: AdminUser,
        request=None,
        change_note: str | None = None,
        target_version: int | None = None,
    ) -> None:
        """为被拒绝的配置写操作记录无正文失败摘要。"""

        active = await self._active(db, config_key)
        draft = await self._draft(db, config_key)
        active_config = _parse_config_value(active)
        draft_config = _parse_config_value(draft)
        selected = draft_config or active_config or {}
        nested_categories = sorted(
            {
                item.get("code")
                for item in error.errors
                if isinstance(item, dict) and isinstance(item.get("code"), str)
            }
        )
        failure_category = ",".join(nested_categories) or error.code
        await log_operation(
            db,
            admin_user,
            "voice_config",
            action,
            f"拒绝语音配置{action} {config_key}"
            + (f"/V{target_version}" if target_version is not None else ""),
            after_value=_audit_projection(
                action=action,
                config_key=config_key,
                config=selected,
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=draft.draft_revision if draft else None,
                changed_sections=_changed_sections(active_config, draft_config),
                change_note=change_note,
                permission=admin_user.role,
                result="failed",
                failure_category=failure_category,
            ),
            request=request,
        )

    async def get_bundle(
        self,
        db: AsyncSession,
        alias: str,
        role: str,
    ) -> dict[str, Any] | None:
        config_key = self.resolve_config_key(alias)
        active = await self._active(db, config_key)
        draft = await self._draft(db, config_key)
        active_config = _parse_config_value(active)
        draft_config = _parse_config_value(draft)
        selected = draft_config or active_config
        if selected is None:
            return None
        return {
            "_meta": {
                "config_key": config_key,
                "base_version": active.version if active else 0,
                "draft_revision": draft.draft_revision if draft else None,
                "content_sha256": content_sha256(selected),
                "active_content_sha256": content_sha256(active_config) if active_config else None,
                "has_draft": draft is not None,
                "changed_sections": _changed_sections(active_config, draft_config),
                "section_defaults": {"summary": self.summary_defaults(config_key)},
            },
            "config": _project_credential(selected, role),
        }

    async def save_draft_section(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        section: str,
        base_version: int,
        draft_revision: int | None,
        content: dict[str, Any],
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        try:
            return await self._save_draft_section_checked(
                db,
                config_key=config_key,
                section=section,
                base_version=base_version,
                draft_revision=draft_revision,
                content=content,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=config_key,
                action="save_draft",
                error=exc,
                admin_user=admin_user,
                request=request,
            )
            raise

    async def _save_draft_section_checked(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        section: str,
        base_version: int,
        draft_revision: int | None,
        content: dict[str, Any],
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        if section not in self.allowed_sections(config_key):
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, f"section {section} 不可编辑")
        active = await self._active(db, config_key, lock=True)
        current_version = active.version if active else 0
        if base_version != current_version:
            raise VoiceConfigError(
                VOICE_CONFIG_BASE_VERSION_CONFLICT,
                "生效版本已变化，请重新加载草稿",
                status_code=409,
            )
        draft = await self._draft(db, config_key, lock=True)
        current_revision = draft.draft_revision if draft else None
        if draft_revision != current_revision:
            raise VoiceConfigError(
                VOICE_CONFIG_REVISION_CONFLICT,
                "草稿已被其他管理员更新，请重新加载差异",
                status_code=409,
            )
        base_config = _parse_config_value(draft) if draft else _parse_config_value(active)
        if base_config is None:
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "无可编辑的生效配置，请先执行规范初始化")
        if config_key == VOICE_CALL_CONFIG_KEY and section == "global":
            legacy_enabled = base_config.get("global", {}).get("enabled")
            if type(content.get("enabled")) is not bool or content["enabled"] != legacy_enabled:
                raise VoiceConfigError("VOICE_MASTER_SWITCH_MANAGED", "总开关请在独立的「总开关」页面操作")
        next_config = deepcopy(base_config)
        next_config[section] = deepcopy(content)
        if config_key == VOICE_CALL_CONFIG_KEY:
            issues = validate_trusted_voice_bundle(config_key, next_config)
            if section == "capabilities":
                issues = _capability_projection_forgery_issues(
                    base_config.get("capabilities"),
                    content,
                ) + issues
        else:
            issues = validate_voice_bundle(config_key, next_config)
        if issues:
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "配置校验失败", errors=issues)

        next_revision = (current_revision or 0) + 1
        now = datetime.utcnow()
        if draft is None:
            draft = AdminConfig(
                config_key=config_key,
                config_value=canonical_json(next_config),
                version=0,
                draft_revision=next_revision,
                is_draft=True,
                is_active=False,
                updated_by=admin_user.username,
                updated_at=now,
            )
            db.add(draft)
        else:
            draft.config_value = canonical_json(next_config)
            draft.draft_revision = next_revision
            draft.updated_by = admin_user.username
            draft.updated_at = now
        await db.flush()
        changed = _changed_sections(_parse_config_value(active), next_config)
        await log_operation(
            db=db,
            admin_user=admin_user,
            module="voice_config",
            action="save_draft",
            target_description=f"保存语音配置草稿 {config_key}/{section}",
            before_value=None,
            after_value=_audit_projection(
                action="save_draft",
                config_key=config_key,
                config=next_config,
                version=current_version,
                base_version=current_version,
                draft_revision=next_revision,
                changed_sections=changed,
                permission=admin_user.role,
            ),
            request=request,
        )
        return {
            "config_key": config_key,
            "base_version": current_version,
            "draft_revision": next_revision,
            "content_sha256": content_sha256(next_config),
            "changed_sections": changed,
        }

    async def discard_draft_section(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        section: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        try:
            return await self._discard_draft_section_checked(
                db,
                config_key=config_key,
                section=section,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=config_key,
                action="discard_section",
                error=exc,
                admin_user=admin_user,
                request=request,
            )
            raise

    async def _discard_draft_section_checked(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        section: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        if section not in self.allowed_sections(config_key):
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, f"section {section} 不可编辑")
        active = await self._active(db, config_key, lock=True)
        draft = await self._draft(db, config_key, lock=True)
        if draft is None:
            raise VoiceConfigError(VOICE_CONFIG_NO_DRAFT, "无草稿可丢弃")
        active_config = _parse_config_value(active) or {}
        draft_config = _parse_config_value(draft) or {}
        if section in active_config:
            draft_config[section] = deepcopy(active_config[section])
        else:
            draft_config.pop(section, None)
        if draft_config == active_config:
            await db.delete(draft)
            next_revision = None
            changed: list[str] = []
        else:
            next_revision = (draft.draft_revision or 0) + 1
            draft.config_value = canonical_json(draft_config)
            draft.draft_revision = next_revision
            draft.updated_by = admin_user.username
            draft.updated_at = datetime.utcnow()
            changed = _changed_sections(active_config, draft_config)
        await db.flush()
        await log_operation(
            db,
            admin_user,
            "voice_config",
            "discard_section",
            f"丢弃语音配置分区草稿 {config_key}/{section}",
            after_value=_audit_projection(
                action="discard_draft_section",
                config_key=config_key,
                config=draft_config,
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=next_revision,
                changed_sections=changed,
                permission=admin_user.role,
            ),
            request=request,
        )
        return {"draft_revision": next_revision, "changed_sections": changed}

    async def discard_draft(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, bool]:
        try:
            return await self._discard_draft_checked(
                db,
                config_key=config_key,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=config_key,
                action="discard_draft",
                error=exc,
                admin_user=admin_user,
                request=request,
            )
            raise

    async def _discard_draft_checked(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, bool]:
        active = await self._active(db, config_key, lock=True)
        draft = await self._draft(db, config_key, lock=True)
        if draft is None:
            raise VoiceConfigError(VOICE_CONFIG_NO_DRAFT, "无草稿可丢弃")
        active_config = _parse_config_value(active) or {}
        draft_config = _parse_config_value(draft) or {}
        discarded_sections = _changed_sections(active_config, draft_config)
        await db.delete(draft)
        await db.flush()
        await log_operation(
            db,
            admin_user,
            "voice_config",
            "discard_draft",
            f"丢弃全部语音配置草稿 {config_key}",
            after_value=_audit_projection(
                action="discard_draft",
                config_key=config_key,
                config=active_config,
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=draft.draft_revision,
                changed_sections=discarded_sections,
                permission=admin_user.role,
            ),
            request=request,
        )
        return {"discarded": True}

    async def validate_current(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        preview: dict[str, Any] | None,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        draft = await self._draft(db, config_key)
        active = await self._active(db, config_key)
        config = _parse_config_value(draft) or _parse_config_value(active)
        if config is None:
            issues = [_issue(VOICE_CONFIG_SCHEMA_INVALID, "config", "无可校验配置")]
        else:
            issues = (
                validate_trusted_voice_bundle(config_key, config)
                if config_key == VOICE_CALL_CONFIG_KEY
                else validate_voice_bundle(config_key, config)
            )
            if config_key == VOICE_CALL_CONFIG_KEY and not issues:
                persona_issue = await _validate_published_persona_ref(db, config)
                if persona_issue is not None:
                    issues.append(persona_issue)
                else:
                    try:
                        await self._ensure_all_scope_evidence(db, config)
                    except VoiceConfigError as exc:
                        issues.extend(
                            exc.errors
                            or [
                                _issue(
                                    exc.code,
                                    "capabilities",
                                    exc.message,
                                )
                            ]
                        )
        result: dict[str, Any] = {"valid": not issues, "errors": issues}
        if preview is not None:
            if config_key != VOICE_CALL_CONFIG_KEY:
                preview_error = _issue(
                    FOLLOWUP_PREVIEW_INPUT_INVALID,
                    "followup_preview",
                    "只有 voice_call_config 支持 follow-up 预览",
                )
                result["valid"] = False
                result["errors"].append(preview_error)
            elif not issues:
                try:
                    result["followup_preview"] = resolve_followup_preview(
                        config["followup"]["schedule"], preview
                    )
                except VoiceConfigError as exc:
                    result["valid"] = False
                    result["errors"].extend(exc.errors)
        failure_categories = sorted({item["code"] for item in result["errors"]})
        await log_operation(
            db,
            admin_user,
            "voice_config",
            "validate",
            f"校验语音配置 {config_key}",
            after_value=_audit_projection(
                action="validate",
                config_key=config_key,
                config=config or {},
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=draft.draft_revision if draft else None,
                changed_sections=_changed_sections(
                    _parse_config_value(active),
                    _parse_config_value(draft),
                ),
                permission=admin_user.role,
                result="success" if result["valid"] else "failed",
                failure_category=",".join(failure_categories) if failure_categories else None,
            ),
            request=request,
        )
        return result

    @staticmethod
    def _ensure_credential_configured(config: dict[str, Any]) -> None:
        if "s2s" not in config:
            return
        ref = config["s2s"].get("credential_ref")
        if not isinstance(ref, str) or not os.getenv(ref):
            raise VoiceConfigError(
                VOICE_CONFIG_CREDENTIAL_MISSING,
                "credential_ref 指向的环境变量未配置",
            )

    async def _current_dimensions_for_publish(
        self,
        *,
        capability_key: str,
        s2s: Mapping[str, Any],
    ) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
        """读取可信当前六维；缺失、异常或形状漂移均按不可发布处理。"""

        field = f"capabilities.{capability_key}.effective_scope"
        provider = self._current_dimensions_provider
        if provider is None:
            return None, _issue(
                VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE,
                field,
                "当前六维可信来源未配置，禁止发布到 all",
            )
        try:
            provided = provider(capability_key, deepcopy(dict(s2s)))
            if isawaitable(provided):
                provided = await provided
            if not isinstance(provided, Mapping) or set(provided) != set(
                _CAPABILITY_EVIDENCE_DIMENSION_FIELDS
            ):
                raise CapabilityStateError(
                    VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE,
                    field,
                    "当前六维必须精确包含冻结字段",
                )
            dimensions = {
                dimension: provided[dimension]
                for dimension in _CAPABILITY_EVIDENCE_DIMENSION_FIELDS
            }
            # 同时验证每一维均为非空字符串；不允许 provider 用证据投影自锚。
            compute_evidence_fingerprint(dimensions)
        except Exception:
            return None, _issue(
                VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE,
                field,
                "当前六维可信读取失败，禁止发布到 all",
            )
        return dimensions, None

    async def _ensure_all_scope_evidence(
        self,
        db: AsyncSession,
        config: dict[str, Any],
    ) -> None:
        """发布/回滚前重查 verified/all 的证据行与当前六维。"""

        capabilities = config.get("capabilities")
        s2s = config.get("s2s")
        if not isinstance(capabilities, dict) or not isinstance(s2s, dict):
            raise VoiceConfigError(
                VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                "语音能力或 S2S 配置不完整，禁止发布",
            )

        issues: list[dict[str, Any]] = []
        reference_now = datetime.now(timezone.utc).replace(tzinfo=None)
        for capability_key in VOICE_CAPABILITY_KEYS:
            capability = capabilities.get(capability_key)
            if not isinstance(capability, dict) or not (
                capability.get("enabled") is True
                and capability.get("effective_scope") == "all"
            ):
                continue

            prefix = f"capabilities.{capability_key}"
            report_id = capability.get("evidence_report_id")
            if not isinstance(report_id, str) or not report_id.strip():
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "all 范围必须引用非空证据报告",
                    )
                )
                continue

            evidence = (
                await db.execute(
                    select(VoiceCapabilityEvidence)
                    .where(VoiceCapabilityEvidence.evidence_report_id == report_id)
                    .with_for_update()
                )
            ).scalars().first()
            if evidence is None:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "引用的能力证据不存在",
                    )
                )
                continue

            if evidence.source_type not in VOICE_EVIDENCE_SOURCE_TYPES:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "证据来源类型不在冻结枚举中",
                        allowed=sorted(VOICE_EVIDENCE_SOURCE_TYPES),
                    )
                )
            # canonical evidence_payload 尚未冻结，当前只校验报告摘要的冻结格式，
            # 不以任何临时 JSON 规范重算 report_sha256。
            if not isinstance(evidence.report_sha256, str) or not _RAW_SHA256_RE.fullmatch(
                evidence.report_sha256
            ):
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "证据 report_sha256 必须是 64 位小写十六进制",
                    )
                )
            if evidence.capability_key != capability_key:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "证据报告与能力位不匹配",
                    )
                )
            if evidence.verification_result != "passed":
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.last_test_result",
                        "只有 passed 证据可发布到 all",
                    )
                )

            row_dimensions = {
                dimension: getattr(evidence, dimension)
                for dimension in _CAPABILITY_EVIDENCE_DIMENSION_FIELDS
            }
            try:
                recomputed_fingerprint = compute_evidence_fingerprint(row_dimensions)
            except CapabilityStateError:
                recomputed_fingerprint = None
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_fingerprint",
                        "证据行六维不完整，无法重算 fingerprint",
                    )
                )
            if (
                recomputed_fingerprint is None
                or evidence.evidence_fingerprint != recomputed_fingerprint
            ):
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_fingerprint",
                        "证据行 fingerprint 与六维重算结果不一致",
                    )
                )

            for dimension in _CAPABILITY_EVIDENCE_DIMENSION_FIELDS:
                if capability.get(dimension) != row_dimensions[dimension]:
                    issues.append(
                        _issue(
                            VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                            f"{prefix}.{dimension}",
                            "配置投影与证据行不一致",
                        )
                    )
            if capability.get("evidence_fingerprint") != evidence.evidence_fingerprint:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_fingerprint",
                        "配置 fingerprint 与证据行不一致",
                    )
                )
            if capability.get("evidence_report_id") != evidence.evidence_report_id:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "配置报告引用与证据行不一致",
                    )
                )
            if capability.get("last_test_result") != evidence.verification_result:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.last_test_result",
                        "配置测试结果与证据行不一致",
                    )
                )

            try:
                row_ttl_days = validate_evidence_ttl_days(
                    evidence.evidence_ttl_days_snapshot
                )
            except CapabilityStateError:
                row_ttl_days = None
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_ttl_days",
                        "证据行 TTL 不在冻结区间",
                    )
                )
            if capability.get("evidence_ttl_days") != row_ttl_days:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_ttl_days",
                        "配置 TTL 与证据行快照不一致",
                    )
                )

            row_tested_at = _normalized_evidence_datetime(evidence.tested_at)
            row_verified_at = _normalized_evidence_datetime(evidence.verified_at)
            row_expires_at = _normalized_evidence_datetime(evidence.expires_at)
            config_verified_at = _normalized_evidence_datetime(
                capability.get("verified_at")
            )
            config_expires_at = _normalized_evidence_datetime(
                capability.get("expires_at")
            )
            if row_verified_at is None or config_verified_at != row_verified_at:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.verified_at",
                        "配置 verified_at 与有效证据行不一致",
                    )
                )
            if row_tested_at is None:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.evidence_report_id",
                        "证据 tested_at 必须是有效时间",
                    )
                )
            elif row_verified_at is not None and row_tested_at > row_verified_at:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.verified_at",
                        "证据时间必须满足 tested_at <= verified_at",
                    )
                )
            if row_verified_at is not None and row_verified_at > reference_now:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.verified_at",
                        "verified_at 不得晚于当前时间",
                    )
                )
            if row_expires_at is None or config_expires_at != row_expires_at:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.expires_at",
                        "配置 expires_at 与有效证据行不一致",
                    )
                )
            if row_verified_at is not None and row_ttl_days is not None:
                expected_expires_at = _normalized_evidence_datetime(
                    evidence_expires_at(row_verified_at, row_ttl_days)
                )
                if row_expires_at != expected_expires_at:
                    issues.append(
                        _issue(
                            VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                            f"{prefix}.expires_at",
                            "expires_at 必须精确等于 verified_at 加证据 TTL",
                        )
                    )
            if row_expires_at is None or reference_now >= row_expires_at:
                issues.append(
                    _issue(
                        VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                        f"{prefix}.expires_at",
                        "能力证据已过期或过期时间无效",
                    )
                )

            for dimension in ("model_version", "protocol_profile", "adapter_version"):
                if row_dimensions[dimension] != s2s.get(dimension):
                    issues.append(
                        _issue(
                            VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                            f"{prefix}.{dimension}",
                            "能力证据维度与当前 S2S 配置不一致",
                        )
                    )

            current_dimensions, current_issue = await self._current_dimensions_for_publish(
                capability_key=capability_key,
                s2s=s2s,
            )
            if current_issue is not None:
                issues.append(current_issue)
            elif current_dimensions is not None:
                current_fingerprint = compute_evidence_fingerprint(current_dimensions)
                for dimension in _CAPABILITY_EVIDENCE_DIMENSION_FIELDS:
                    if current_dimensions[dimension] != row_dimensions[dimension]:
                        issues.append(
                            _issue(
                                VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                                f"{prefix}.{dimension}",
                                "当前可信六维与证据行不一致",
                            )
                        )
                if current_fingerprint != evidence.evidence_fingerprint:
                    issues.append(
                        _issue(
                            VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                            f"{prefix}.evidence_fingerprint",
                            "当前可信六维 fingerprint 与证据行不一致",
                        )
                    )

        if issues:
            raise VoiceConfigError(
                VOICE_CAPABILITY_ALL_EVIDENCE_INVALID,
                "存在未通过发布重查的 all 范围能力",
                errors=issues,
            )

    async def force_capability_test(
        self,
        db: AsyncSession,
        *,
        capability_key: str,
        effective_scope: str,
        confirm_text: str,
        reason: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        """内部强制 test 状态机；本方法没有且不得自行增加公开路由。"""

        try:
            return await self._force_capability_test_checked(
                db,
                capability_key=capability_key,
                effective_scope=effective_scope,
                confirm_text=confirm_text,
                reason=reason,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=VOICE_CALL_CONFIG_KEY,
                action="force_enable",
                error=exc,
                admin_user=admin_user,
                request=request,
                # 审计仅保留长度与 hash，不保存可能包含正文或 Secret 的原因。
                change_note=reason if isinstance(reason, str) else None,
            )
            raise

    async def _force_capability_test_checked(
        self,
        db: AsyncSession,
        *,
        capability_key: str,
        effective_scope: str,
        confirm_text: str,
        reason: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        if admin_user.role != "super_admin":
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_FORBIDDEN,
                "仅 super_admin 可强制启用未验证或已过期能力",
                status_code=403,
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_FORBIDDEN,
                        "permission",
                        "当前角色无强制启用权限",
                    )
                ],
            )
        if confirm_text != "CONFIRM":
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_CONFIRM_INVALID,
                "必须精确输入 CONFIRM",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_CONFIRM_INVALID,
                        "confirm_text",
                        "必须精确输入 CONFIRM",
                        allowed=["CONFIRM"],
                    )
                ],
            )
        if not isinstance(reason, str) or not reason.strip():
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_REASON_REQUIRED,
                "强制启用原因不得为空",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_REASON_REQUIRED,
                        "reason",
                        "必须填写非空原因",
                    )
                ],
            )
        if capability_key not in VOICE_CAPABILITY_KEYS:
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_STATUS_INVALID,
                "未知能力位",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_STATUS_INVALID,
                        "capability_key",
                        "只能选择六个冻结能力位",
                        allowed=list(VOICE_CAPABILITY_KEYS),
                    )
                ],
            )
        if effective_scope != "test":
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_SCOPE_INVALID,
                "强制启用只允许 effective_scope=test",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_SCOPE_INVALID,
                        "effective_scope",
                        "未验证或已过期能力禁止进入 all",
                        allowed=["test"],
                    )
                ],
            )

        active = await self._active(db, VOICE_CALL_CONFIG_KEY, lock=True)
        draft = await self._draft(db, VOICE_CALL_CONFIG_KEY, lock=True)
        active_config = _parse_config_value(active)
        draft_config = _parse_config_value(draft)
        selected = draft_config or active_config
        if selected is None:
            raise VoiceConfigError(
                VOICE_CONFIG_SCHEMA_INVALID,
                "无可强制启用的语音配置",
            )

        current_issues = validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, selected)
        if current_issues:
            raise VoiceConfigError(
                VOICE_CONFIG_SCHEMA_INVALID,
                "当前语音配置不满足可信投影约束",
                errors=current_issues,
            )
        test_user_ids = selected["global"]["test_user_ids"]
        if not test_user_ids:
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED,
                "强制启用前必须配置非空 global.test_user_ids",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED,
                        "global.test_user_ids",
                        "测试用户列表不得为空",
                    )
                ],
            )

        current_capability = selected["capabilities"][capability_key]
        report_id = current_capability.get("evidence_report_id")
        if report_id:
            evidence = (await db.execute(select(VoiceCapabilityEvidence).where(
                VoiceCapabilityEvidence.evidence_report_id == report_id,
            ))).scalars().first()
            if (evidence is not None and evidence.verification_result == "error"
                and (evidence.source_type == "phase0_import"
                     or (isinstance(evidence.evidence_payload, dict)
                         and evidence.evidence_payload.get("reason_code") == "admin_playback_review_only"))):
                raise VoiceConfigError(
                    VOICE_CAPABILITY_FORCE_STATUS_INVALID,
                    "诊断/播放复核记录只用于审计，不能强制启用；需新的可信能力证据",
                )
        status = current_capability["verification_status"]
        if status not in {"unverified", "stale"}:
            raise VoiceConfigError(
                VOICE_CAPABILITY_FORCE_STATUS_INVALID,
                "只有 unverified/stale 能力可强制到 test",
                errors=[
                    _issue(
                        VOICE_CAPABILITY_FORCE_STATUS_INVALID,
                        f"capabilities.{capability_key}.verification_status",
                        "failed 禁止启用；verified 不使用强制路径",
                        allowed=["unverified", "stale"],
                    )
                ],
            )

        next_config = deepcopy(selected)
        next_capability = next_config["capabilities"][capability_key]
        next_capability["enabled"] = True
        next_capability["forced_enabled"] = True
        next_capability["effective_scope"] = "test"
        next_issues = validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, next_config)
        if next_issues:
            raise VoiceConfigError(
                VOICE_CONFIG_SCHEMA_INVALID,
                "强制 test 后配置不满足可信投影约束",
                errors=next_issues,
            )

        previous_revision = draft.draft_revision if draft else None
        next_revision = (previous_revision or 0) + 1
        force_time = datetime.now(timezone.utc)
        now = force_time.replace(tzinfo=None)
        if draft is None:
            draft = AdminConfig(
                config_key=VOICE_CALL_CONFIG_KEY,
                config_value=canonical_json(next_config),
                version=0,
                draft_revision=next_revision,
                is_draft=True,
                is_active=False,
                updated_by=admin_user.username,
                updated_at=now,
            )
            db.add(draft)
        else:
            draft.config_value = canonical_json(next_config)
            draft.draft_revision = next_revision
            draft.updated_by = admin_user.username
            draft.updated_at = now
        await db.flush()

        trimmed_reason = reason.strip()
        force_source = {
            "source": "admin_force_test",
            "capability_key": capability_key,
            "draft_revision": next_revision,
            "config_content_sha256": content_sha256(next_config),
            "operator_id": admin_user.id,
            "forced_at": force_time.isoformat().replace("+00:00", "Z"),
            "reason_length": len(trimmed_reason),
            "reason_sha256": "sha256:"
            + hashlib.sha256(trimmed_reason.encode("utf-8")).hexdigest(),
        }

        await log_operation(
            db,
            admin_user,
            "voice_config",
            "force_enable",
            f"强制语音能力进入 test {capability_key}",
            before_value=_audit_projection(
                action="force_enable_before",
                config_key=VOICE_CALL_CONFIG_KEY,
                config=selected,
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=previous_revision,
                changed_sections=[],
                permission=admin_user.role,
            ),
            after_value=_audit_projection(
                action="force_enable",
                config_key=VOICE_CALL_CONFIG_KEY,
                config=next_config,
                version=active.version if active else 0,
                base_version=active.version if active else 0,
                draft_revision=next_revision,
                changed_sections=["capabilities"],
                change_note=trimmed_reason,
                permission=admin_user.role,
                force_source=force_source,
                capability_audit={
                    "capability_key": capability_key,
                    "fallback_mode": next_capability.get("fallback_mode"),
                    "effective_scope": next_capability["effective_scope"],
                    "evidence_report_id": next_capability.get("evidence_report_id"),
                    "evidence_suite_version": next_capability.get("evidence_suite_version"),
                    "evidence_fingerprint": next_capability.get("evidence_fingerprint"),
                },
            ),
            request=request,
        )
        return {
            "config_key": VOICE_CALL_CONFIG_KEY,
            "capability_key": capability_key,
            "base_version": active.version if active else 0,
            "draft_revision": next_revision,
            "content_sha256": content_sha256(next_config),
        }

    async def publish(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        confirm_text: str,
        change_note: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        try:
            return await self._publish_checked(
                db,
                config_key=config_key,
                confirm_text=confirm_text,
                change_note=change_note,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=config_key,
                action="publish",
                error=exc,
                admin_user=admin_user,
                request=request,
                change_note=change_note if isinstance(change_note, str) else None,
            )
            raise
        except Exception:
            failure = VoiceConfigError(
                "VOICE_CONFIG_PUBLISH_FAILED",
                "语音配置发布失败，已执行补偿",
            )
            try:
                await self._log_failed_config_operation(
                    db,
                    config_key=config_key,
                    action="publish",
                    error=failure,
                    admin_user=admin_user,
                    request=request,
                    change_note=change_note if isinstance(change_note, str) else None,
                )
            except Exception:
                logger.error("语音配置发布失败审计不可用: %s", config_key)
            raise

    async def _publish_checked(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        confirm_text: str,
        change_note: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        if confirm_text != "CONFIRM":
            raise VoiceConfigError("VOICE_CONFIG_CONFIRM_TEXT_INVALID", "必须精确输入 CONFIRM")
        if not isinstance(change_note, str) or not change_note.strip():
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "change_note 不得为空白")
        change_note = change_note.strip()
        active = await self._active(db, config_key, lock=True)
        draft = await self._draft(db, config_key, lock=True)
        config = _parse_config_value(draft)
        if config is None:
            raise VoiceConfigError(VOICE_CONFIG_NO_DRAFT, "无待发布草稿")
        issues = (
            validate_trusted_voice_bundle(config_key, config)
            if config_key == VOICE_CALL_CONFIG_KEY
            else validate_voice_bundle(config_key, config)
        )
        if issues:
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "配置校验失败", errors=issues)
        if config_key == VOICE_CALL_CONFIG_KEY:
            persona_issue = await _validate_published_persona_ref(db, config)
            if persona_issue is not None:
                raise VoiceConfigError(
                    VOICE_CONFIG_PERSONA_REF_INVALID,
                    "persona_ref 未指向可验证的已发布人格锚点",
                    errors=[persona_issue],
                )
            await self._ensure_all_scope_evidence(db, config)
        self._ensure_credential_configured(config)
        before_config = _parse_config_value(active) or {}
        changed = _changed_sections(before_config, config)
        audit_before = _audit_projection(
            action="publish_before",
            config_key=config_key,
            config=before_config,
            version=active.version if active else 0,
            permission=admin_user.role,
        )
        audit_after = _audit_projection(
            action="publish",
            config_key=config_key,
            config=config,
            version=(active.version if active else 0) + 1,
            base_version=active.version if active else 0,
            draft_revision=draft.draft_revision,
            changed_sections=changed,
            change_note=change_note,
            permission=admin_user.role,
        )

        async def operation() -> dict[str, Any]:
            return await admin_config_service.publish_config(
                db=db,
                config_key=config_key,
                config_value=canonical_json(config),
                admin_user=admin_user,
                before_value=audit_before,
                request=request,
                target_description=f"发布语音配置 {config_key}",
                audit_after_value=audit_after,
            )

        result = await _execute_publish_with_compensation(
            db,
            config_key,
            operation,
            published_config=(
                config if config_key == VOICE_CALL_CONFIG_KEY else None
            ),
            published_version=(
                (active.version if active else 0) + 1
                if config_key == VOICE_CALL_CONFIG_KEY
                else None
            ),
        )
        result.update(
            {
                "config_key": config_key,
                "schema_version": config["schema_version"],
                "content_sha256": content_sha256(config),
                "changed_sections": changed,
            }
        )
        return result

    async def get_history(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        count_stmt = select(func.count(AdminConfig.id)).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == False,  # noqa: E712
        )
        total = (await db.execute(count_stmt)).scalar() or 0
        stmt = (
            select(AdminConfig)
            .where(
                AdminConfig.config_key == config_key,
                AdminConfig.is_draft == False,  # noqa: E712
            )
            .order_by(AdminConfig.version.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        items = []
        for row in rows:
            config = _parse_config_value(row)
            items.append(
                {
                    "version": row.version,
                    "schema_version": config.get("schema_version") if config else None,
                    "content_sha256": content_sha256(config) if config else None,
                    "is_active": row.is_active,
                    "updated_by": row.updated_by,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )
        return {"total": total, "page": page, "page_size": page_size, "list": items}

    async def get_history_detail(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        version: int,
        role: str,
    ) -> dict[str, Any]:
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.version == version,
            AdminConfig.is_draft == False,  # noqa: E712
        )
        row = (await db.execute(stmt)).scalars().first()
        config = _parse_config_value(row)
        if row is None or config is None:
            raise VoiceConfigError(VOICE_CONFIG_VERSION_NOT_FOUND, f"版本 V{version} 不存在", status_code=404)
        return {
            "version": row.version,
            "schema_version": config.get("schema_version"),
            "content_sha256": content_sha256(config),
            "is_active": row.is_active,
            "updated_by": row.updated_by,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "config": _project_credential(config, role),
        }

    async def rollback(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        version: int,
        confirm_text: str,
        change_note: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        try:
            return await self._rollback_checked(
                db,
                config_key=config_key,
                version=version,
                confirm_text=confirm_text,
                change_note=change_note,
                admin_user=admin_user,
                request=request,
            )
        except VoiceConfigError as exc:
            await self._log_failed_config_operation(
                db,
                config_key=config_key,
                action="rollback",
                error=exc,
                admin_user=admin_user,
                request=request,
                change_note=change_note if isinstance(change_note, str) else None,
                target_version=version,
            )
            raise
        except Exception:
            failure = VoiceConfigError(
                "VOICE_CONFIG_ROLLBACK_FAILED",
                "语音配置回滚失败，已执行补偿",
            )
            try:
                await self._log_failed_config_operation(
                    db,
                    config_key=config_key,
                    action="rollback",
                    error=failure,
                    admin_user=admin_user,
                    request=request,
                    change_note=change_note if isinstance(change_note, str) else None,
                    target_version=version,
                )
            except Exception:
                logger.error("语音配置回滚失败审计不可用: %s", config_key)
            raise

    async def _rollback_checked(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        version: int,
        confirm_text: str,
        change_note: str,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        if confirm_text != "CONFIRM":
            raise VoiceConfigError("VOICE_CONFIG_CONFIRM_TEXT_INVALID", "必须精确输入 CONFIRM")
        if not isinstance(change_note, str) or not change_note.strip():
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "change_note 不得为空白")
        change_note = change_note.strip()
        active = await self._active(db, config_key, lock=True)
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.version == version,
            AdminConfig.is_draft == False,  # noqa: E712
        ).with_for_update()
        target = (await db.execute(stmt)).scalars().first()
        config = _parse_config_value(target)
        if target is None or config is None:
            raise VoiceConfigError(VOICE_CONFIG_VERSION_NOT_FOUND, f"版本 V{version} 不存在", status_code=404)
        issues = (
            validate_trusted_voice_bundle(config_key, config)
            if config_key == VOICE_CALL_CONFIG_KEY
            else validate_voice_bundle(config_key, config)
        )
        if issues:
            raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "目标历史版本不再满足发布约束", errors=issues)
        if config_key == VOICE_CALL_CONFIG_KEY:
            persona_issue = await _validate_published_persona_ref(db, config)
            if persona_issue is not None:
                raise VoiceConfigError(
                    VOICE_CONFIG_PERSONA_REF_INVALID,
                    "目标版本的 persona_ref 无法验证",
                    errors=[persona_issue],
                )
            await self._ensure_all_scope_evidence(db, config)
        self._ensure_credential_configured(config)
        before_config = _parse_config_value(active) or {}
        changed = _changed_sections(before_config, config)
        audit_before = _audit_projection(
            action="rollback_before",
            config_key=config_key,
            config=before_config,
            version=active.version if active else 0,
            base_version=active.version if active else 0,
            changed_sections=changed,
            permission=admin_user.role,
        )
        audit_after = _audit_projection(
            action="rollback",
            config_key=config_key,
            config=config,
            version=(active.version if active else 0) + 1,
            base_version=active.version if active else 0,
            changed_sections=changed,
            change_note=change_note,
            permission=admin_user.role,
        )

        async def operation() -> dict[str, Any]:
            return await admin_config_service.rollback_config(
                db=db,
                config_key=config_key,
                version=version,
                admin_user=admin_user,
                request=request,
                audit_before_value=audit_before,
                audit_after_value=audit_after,
            )

        result = await _execute_publish_with_compensation(
            db,
            config_key,
            operation,
            published_config=(
                config if config_key == VOICE_CALL_CONFIG_KEY else None
            ),
            published_version=(
                (active.version if active else 0) + 1
                if config_key == VOICE_CALL_CONFIG_KEY
                else None
            ),
        )
        result.update(
            {
                "config_key": config_key,
                "rolled_back_from_version": version,
                "schema_version": config["schema_version"],
                "content_sha256": content_sha256(config),
            }
        )
        return result

    @_serialized_operation("initialize:realtime_voice_defaults")
    async def initialize_defaults(
        self,
        db: AsyncSession,
        *,
        admin_user: AdminUser,
        request=None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for config_key in (VOICE_CALL_CONFIG_KEY, VOICE_CALL_SCRIPT_KEY):
            # 对每个 key 在稳定锚锁之后重查，且每次 publish commit 后重新获取下一
            # 个锚；否则两个并发初始化都可能基于“尚无 active”各自发布 V1。
            existing = await _lock_publish_anchor(db, config_key)
            if existing is not None:
                existing_version = existing.version
                existing_config = (
                    _parse_config_value(existing)
                    if config_key == VOICE_CALL_CONFIG_KEY
                    else None
                )
                existing_published_at = (
                    existing.updated_at.isoformat()
                    if isinstance(existing.updated_at, datetime)
                    else ""
                )
                if existing_config is not None:
                    persona_issue = await _validate_published_persona_ref(
                        db,
                        existing_config,
                    )
                    if persona_issue is not None:
                        raise VoiceConfigError(
                            VOICE_CONFIG_PERSONA_REF_INVALID,
                            "现有 voice_call_config 的 persona_ref 无法建立可信发布锚",
                            errors=[persona_issue],
                        )
                result[config_key] = {
                    "status": "skipped",
                    "version": existing_version,
                }
                redis = None
                expected_envelope = None
                if config_key == VOICE_CALL_CONFIG_KEY:
                    if existing_config is None:
                        raise VoiceConfigError(
                            VOICE_CONFIG_SCHEMA_INVALID,
                            "现有 voice_call_config 无法建立可信发布锚",
                        )
                    expected_envelope = _published_voice_config_envelope(
                        config=existing_config,
                        version=existing_version,
                        published_at=existing_published_at,
                    )
                    redis = await get_redis()
                    await _take_published_voice_config_envelope(
                        redis,
                        max_version=existing_version,
                    )
                await db.commit()
                if config_key == VOICE_CALL_CONFIG_KEY:
                    try:
                        await _write_published_voice_config_envelope(
                            redis,
                            config=existing_config,
                            version=existing_version,
                            published_at=existing_published_at,
                        )
                    except Exception:
                        try:
                            await _delete_published_voice_config_envelope_if_match(
                                redis,
                                expected_envelope,
                            )
                        except Exception:
                            logger.error("语音配置发布锚清理失败")
                        raise
                continue
            if config_key == VOICE_CALL_CONFIG_KEY:
                persona = await self._active(db, "persona", lock=True)
                if persona is None or not persona.config_value:
                    raise VoiceConfigError(
                        VOICE_CONFIG_PERSONA_REQUIRED,
                        "初始化 voice_call_config 前必须存在已发布 persona",
                    )
                persona_ref = {
                    "config_key": "persona",
                    "version": persona.version,
                    "content_sha256": "sha256:"
                    + hashlib.sha256(persona.config_value.encode("utf-8")).hexdigest(),
                }
            else:
                # script seed 不消费 persona_ref；占位值只满足统一 manifest builder
                # 的入参形状，不会进入 voice_call_script JSON。
                persona_ref = {
                    "config_key": "persona",
                    "version": 1,
                    "content_sha256": "sha256:" + "0" * 64,
                }
            manifest = build_canonical_voice_seed_manifest(persona_ref)
            config = manifest[config_key]
            issues = validate_voice_bundle(config_key, config)
            if issues:
                raise VoiceConfigError(VOICE_CONFIG_SCHEMA_INVALID, "规范 seed 校验失败", errors=issues)
            audit_after = _audit_projection(
                action="canonical_seed",
                config_key=config_key,
                config=config,
                version=1,
                base_version=0,
                changed_sections=sorted(self.allowed_sections(config_key)),
                change_note="STEP-005 canonical initial publish",
                permission=admin_user.role,
            )

            async def operation(key=config_key, payload=config, audit=audit_after):
                return await admin_config_service.publish_config(
                    db=db,
                    config_key=key,
                    config_value=canonical_json(payload),
                    admin_user=admin_user,
                    before_value=None,
                    request=request,
                    target_description=f"初始化语音规范配置 {key}",
                    audit_after_value=audit,
                )

            published = await _execute_publish_with_compensation(
                db,
                config_key,
                operation,
                published_config=(
                    config if config_key == VOICE_CALL_CONFIG_KEY else None
                ),
                published_version=(
                    1 if config_key == VOICE_CALL_CONFIG_KEY else None
                ),
            )
            result[config_key] = {
                "status": "published",
                "version": published["version"],
                "schema_version": config["schema_version"],
                "content_sha256": content_sha256(config),
            }
        return result


def normalize_crisis_keywords(keywords: Any) -> list[str]:
    if not isinstance(keywords, list) or any(
        not isinstance(item, str) for item in keywords
    ):
        raise VoiceConfigError(CRISIS_KEYWORDS_EMPTY, "crisis_keywords 必须是字符串数组")
    normalized = sorted(
        {
            item.strip()
            for item in keywords
            if isinstance(item, str) and item.strip()
        }
    )
    if not normalized:
        raise VoiceConfigError(CRISIS_KEYWORDS_EMPTY, "crisis_keywords 规范化后不得为空")
    secret_issues = _scan_forbidden_fields(normalized)
    if secret_issues:
        raise VoiceConfigError(
            VOICE_CONFIG_SECRET_FORBIDDEN,
            "crisis_keywords 禁止包含凭据或疑似 Secret",
            errors=secret_issues,
        )
    return normalized


async def _log_failed_crisis_operation(
    db: AsyncSession,
    *,
    action: str,
    error: VoiceConfigError,
    admin_user: AdminUser,
    request=None,
    target_version: int | None = None,
) -> None:
    active = (
        await db.execute(
            select(AdminConfig).where(
                AdminConfig.config_key == CRISIS_KEYWORDS_CONFIG_KEY,
                AdminConfig.is_active == True,  # noqa: E712
                AdminConfig.is_draft == False,  # noqa: E712
            )
        )
    ).scalars().first()
    current_keywords = _parse_json_value(active)
    if not isinstance(current_keywords, list):
        current_keywords = []
    await log_operation(
        db,
        admin_user,
        "ai_config",
        action,
        f"拒绝{action}危机关键词"
        + (f"/V{target_version}" if target_version is not None else ""),
        after_value=_crisis_audit_projection(
            action=action,
            version=active.version if active else 0,
            base_version=active.version if active else 0,
            keyword_count=len(current_keywords),
            keyword_hash=content_sha256(current_keywords),
            permission=admin_user.role,
            target_version=target_version,
            result="failed",
            failure_category=error.code,
        ),
        request=request,
    )


async def audit_crisis_operation_failure(
    db: AsyncSession,
    *,
    action: str,
    error: VoiceConfigError,
    admin_user: AdminUser,
    request=None,
    target_version: int | None = None,
) -> None:
    """供请求层记录在进入发布服务前即被拒绝的危机词操作。"""

    await _log_failed_crisis_operation(
        db,
        action=action,
        error=error,
        admin_user=admin_user,
        request=request,
        target_version=target_version,
    )


async def _publish_crisis_keywords_checked(
    db: AsyncSession,
    *,
    keywords: list[str],
    admin_user: AdminUser,
    request=None,
    action: str = "publish",
    target_version: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_crisis_keywords(keywords)
    active = await _lock_publish_anchor(db, CRISIS_KEYWORDS_CONFIG_KEY)
    config_value = canonical_json(normalized)
    current_keywords = _parse_json_value(active)
    if not isinstance(current_keywords, list):
        current_keywords = []
    audit_before = _crisis_audit_projection(
        action=f"{action}_before",
        version=active.version if active else 0,
        base_version=active.version if active else 0,
        keyword_count=len(current_keywords),
        keyword_hash=content_sha256(current_keywords),
        permission=admin_user.role,
        target_version=target_version,
    )
    audit_after = _crisis_audit_projection(
        action=action,
        version=(active.version if active else 0) + 1,
        base_version=active.version if active else 0,
        keyword_count=len(normalized),
        keyword_hash=content_sha256(normalized),
        permission=admin_user.role,
        target_version=target_version,
    )

    async def operation() -> dict[str, Any]:
        return await admin_config_service.publish_config(
            db=db,
            config_key=CRISIS_KEYWORDS_CONFIG_KEY,
            config_value=config_value,
            admin_user=admin_user,
            before_value=audit_before,
            request=request,
            target_description=f"{action} 危机关键词",
            audit_after_value=audit_after,
            audit_action=action,
        )

    result = await _execute_publish_with_compensation(
        db, CRISIS_KEYWORDS_CONFIG_KEY, operation
    )
    result.update(
        {
            "keywords": normalized,
            "content_sha256": content_sha256(normalized),
        }
    )
    return result


async def publish_crisis_keywords_atomically(
    db: AsyncSession,
    *,
    keywords: list[str],
    admin_user: AdminUser,
    request=None,
    action: str = "publish",
    target_version: int | None = None,
) -> dict[str, Any]:
    try:
        return await _publish_crisis_keywords_checked(
            db,
            keywords=keywords,
            admin_user=admin_user,
            request=request,
            action=action,
            target_version=target_version,
        )
    except Exception as exc:
        error = (
            exc
            if isinstance(exc, VoiceConfigError)
            else VoiceConfigError(
                "VOICE_CRISIS_KEYWORDS_PUBLISH_FAILED",
                "危机词发布失败，已执行补偿",
            )
        )
        try:
            await _log_failed_crisis_operation(
                db,
                action=action,
                error=error,
                admin_user=admin_user,
                request=request,
                target_version=target_version,
            )
        except Exception:
            logger.error("危机词%s失败审计不可用", action)
        raise


async def rollback_crisis_keywords_atomically(
    db: AsyncSession,
    *,
    version: int,
    admin_user: AdminUser,
    request=None,
) -> dict[str, Any]:
    try:
        await _lock_publish_anchor(db, CRISIS_KEYWORDS_CONFIG_KEY)
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == CRISIS_KEYWORDS_CONFIG_KEY,
            AdminConfig.version == version,
            AdminConfig.is_draft == False,  # noqa: E712
        )
        target = (await db.execute(stmt)).scalars().first()
        if target is None:
            raise VoiceConfigError(
                VOICE_CONFIG_VERSION_NOT_FOUND,
                f"版本 V{version} 不存在",
                status_code=404,
            )
        try:
            keywords = json.loads(target.config_value)
        except (json.JSONDecodeError, TypeError) as exc:
            raise VoiceConfigError(CRISIS_KEYWORDS_EMPTY, "目标版本不是合法关键词数组") from exc
        result = await _publish_crisis_keywords_checked(
            db,
            keywords=keywords,
            admin_user=admin_user,
            request=request,
            action="rollback",
            target_version=version,
        )
        result["rolled_back_from_version"] = version
        return result
    except Exception as exc:
        error = (
            exc
            if isinstance(exc, VoiceConfigError)
            else VoiceConfigError(
                "VOICE_CRISIS_KEYWORDS_ROLLBACK_FAILED",
                "危机词回滚失败，已执行补偿",
            )
        )
        try:
            await _log_failed_crisis_operation(
                db,
                action="rollback",
                error=error,
                admin_user=admin_user,
                request=request,
                target_version=version,
            )
        except Exception:
            logger.error("危机词回滚失败审计不可用")
        raise


realtime_voice_config_service = RealtimeVoiceConfigService()


__all__ = [
    "CRISIS_KEYWORDS_EMPTY",
    "FOLLOWUP_PREVIEW_INPUT_INVALID",
    "FOLLOWUP_WINDOW_OVERLAP",
    "FOLLOWUP_WINDOW_RANGE_INVALID",
    "FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER",
    "RealtimeVoiceConfigService",
    "VOICE_CAPABILITY_ALL_EVIDENCE_INVALID",
    "VOICE_CAPABILITY_CURRENT_DIMENSIONS_UNAVAILABLE",
    "VOICE_CAPABILITY_FORCE_CONFIRM_INVALID",
    "VOICE_CAPABILITY_FORCE_FORBIDDEN",
    "VOICE_CAPABILITY_FORCE_REASON_REQUIRED",
    "VOICE_CAPABILITY_FORCE_SCOPE_INVALID",
    "VOICE_CAPABILITY_FORCE_STATUS_INVALID",
    "VOICE_CAPABILITY_FORCE_TEST_USERS_REQUIRED",
    "VOICE_CAPABILITY_PROJECTION_FORGED",
    "VOICE_CAPABILITY_TRUSTED_STATE_INVALID",
    "VOICE_CALL_CONFIG_PUBLISHED_ENVELOPE_KEY",
    "VoiceConfigError",
    "audit_crisis_operation_failure",
    "canonical_json",
    "content_sha256",
    "followup_delay_within_limit",
    "normalize_crisis_keywords",
    "publish_crisis_keywords_atomically",
    "realtime_voice_config_service",
    "resolve_followup_preview",
    "rollback_crisis_keywords_atomically",
    "validate_followup_schedule",
    "validate_trusted_voice_bundle",
    "validate_voice_bundle",
]
