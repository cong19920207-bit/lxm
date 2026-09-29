# -*- coding: utf-8 -*-
"""Realtime voice capability state, evidence validation and internal import.

Evidence writes are deliberately internal service operations.  No public
import route is exposed: Phase0 uses a controlled command and the admin test
runner delegates one already-sanitised record to this service.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol, Sequence

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CAPABILITY_KEYS,
)
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCapabilityEvidence


EVIDENCE_FINGERPRINT_FIELDS = (
    "provider_profile",
    "model_version",
    "protocol_profile",
    "adapter_version",
    "sdk_version",
    "evidence_suite_version",
)

CAPABILITY_EVIDENCE_READ_ROLES = frozenset(
    {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
)
CAPABILITY_EVIDENCE_PAYLOAD_ROLES = frozenset({"super_admin", "tech_ops"})

CAPABILITY_EVIDENCE_NOT_FOUND = "VOICE_CAPABILITY_EVIDENCE_NOT_FOUND"

_CAPABILITY_STATUSES = frozenset({"verified", "unverified", "failed", "stale"})
_NON_VERIFIED_STATUSES = frozenset({"unverified", "failed", "stale"})
_EVIDENCE_TTL_MIN_DAYS = 7
_EVIDENCE_TTL_MAX_DAYS = 90

_PHASE0_RECORD_SCHEMA = "phase0-capability-evidence/v3"
_PHASE0_CONTEXT_RECORD_SCHEMA = "phase0-capability-evidence/v4"
_PHASE0_PROTOCOL_RECORD_SCHEMA = "phase0-capability-evidence/v5"
_PHASE0_BUNDLE_SCHEMA = "phase0-evidence-bundle/v1"
_EVIDENCE_WRITE_ROLES = frozenset({"super_admin", "tech_ops"})
_EVIDENCE_RESULTS = frozenset({"passed", "failed", "error"})
_PHASE0_IMPORT_RESULTS = frozenset({"passed", "failed"})
_RESULT_STATUS = {
    "passed": "verified",
    "failed": "failed",
    "error": "unverified",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,95}$")
_SAFE_DIMENSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]*$")
_HMAC_TOKEN_RE = re.compile(r"^hmac256:[0-9a-f]{24}$")
_DYNAMIC_KEY_RE = re.compile(r"^dynamic_[0-9a-f]{16}$")
_PATH_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$|^[0-9]{1,9}$")
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"bearer\s+[A-Za-z0-9._~-]+", re.I),
    re.compile(r"(?:access|api|secret)[_-]?key", re.I),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"(?:https?|wss?)://[^\s/@:]+:[^\s/@]+@", re.I),
    re.compile(r"\b1[3-9][0-9]{9}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
)

_BUNDLE_FIELDS = frozenset(
    {
        "schema_version",
        "evidence_run_id",
        "record_count",
        "production_source_of_truth",
        "records",
        "bundle_sha256",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "evidence_report_id",
        "evidence_run_id",
        "capability_key",
        "verification_result",
        "source_type",
        *EVIDENCE_FINGERPRINT_FIELDS,
        "evidence_fingerprint",
        "evidence_payload",
        "tested_at",
        "verified_at",
        "evidence_ttl_days_snapshot",
        "expires_at",
        "report_sha256",
    }
)
_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "capability_status",
        "reason_code",
        "degradation_mode",
        "event_evidence",
        "action_evidence",
        "runtime_conditions",
        "production_import_ready",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "ordinal",
        "received_at_ms",
        "event_id",
        "event_name",
        "target_event",
        "message_type",
        "payload_kind",
        "payload_size",
        "is_audio",
        "parse_error",
        "correlation_tokens",
        "payload_shape",
        "probe_match",
    }
)
_EVENT_REQUIRED_FIELDS = _EVENT_FIELDS - {"probe_match"}
_EVENT_NAMES = {
    50: "ConnectionStarted",
    52: "ConnectionFinished",
    150: "SessionStarted",
    152: "SessionFinished",
    153: "SessionFailed",
    154: "UsageResponse",
    350: "TTSSentenceStart",
    351: "TTSSentenceEnd",
    352: "TTSResponse",
    359: "TTSEnded",
    450: "ASRInfo",
    451: "ASRResponse",
    459: "ASREnded",
    550: "ChatResponse",
    559: "ChatEnded",
    567: "ConversationCreated",
}
_TARGET_EVENT_NAMES = frozenset(
    {
        "ChatResponse",
        "ChatEnded",
        "TTSSentenceStart",
        "TTSSentenceEnd",
        "TTSEnded",
        "ConversationTruncated",
        "SessionFailed",
        "UsageResponse",
    }
)
_MESSAGE_TYPES = frozenset(
    {"SERVER_FULL_RESPONSE", "SERVER_ACK", "SERVER_ERROR", "UNKNOWN"}
)
_PAYLOAD_KINDS = frozenset(
    {"binary", "object", "list", "text", "none", "scalar"}
)
_PAYLOAD_SHAPE_FIELDS = frozenset(
    {
        "object_keys",
        "list_lengths",
        "numeric_fields",
        "boolean_fields",
        "text_fields",
        "binary_fields",
        "redacted_key_classes",
    }
)
_REDACTED_KEY_CLASSES = frozenset(
    {"sensitive", "invalid_key", "unsupported_value", "projection_limit"}
)
_PAYLOAD_PATH_PARTS = frozenset(
    {
        "payload",
        "event",
        "event_name",
        "type",
        "results",
        "result",
        "is_interim",
        "confidence",
        "reply_id",
        "question_id",
        "sentence_id",
        "session_id",
        "conversation_id",
        "dialog_id",
        "task_id",
        "round_id",
        "member_id",
        "uid",
        "age",
        "content",
        "text",
        "message",
        "answer",
        "reason",
        "audio",
        "pcm",
        "duration_ms",
        "input_duration_ms",
        "output_duration_ms",
        "enabled",
        "count",
        "extra",
        "items",
        "item_id",
        "role",
        "timestamp",
    }
)
_MAX_SHAPE_ENTRIES = 512
_RUNTIME_FIELDS = frozenset(
    {
        "real_provider",
        "chrome_desktop",
        "microphone_permission",
        "speaker_output",
        "aec_enabled",
        "bluetooth_tested",
        "background_resume_tested",
        "network_profile",
    }
)
_NETWORK_PROFILES = frozenset({"baseline", "light", "medium", "outage_3s"})
_ADMIN_RUNTIME_FIELDS = frozenset({"real_provider", "network_profile"})

_ACTION_COMMON_FIELDS = frozenset(
    {
        "action",
        "at_ms",
        "reply_active",
        "sentence_token",
        "stop_token",
        "session_token",
        "success",
        "reason_code",
        "local_stop_at_ms",
        "provider_ordinal_after_send",
        "provider_ordinal_after_ack",
        "provider_ordinal_before_attempt",
        "provider_ordinal_after_reconnect",
        "provider_event_ordinal",
        "source_asr_ordinal",
        "context_ack_ordinal",
        "target_tts_start_ordinal",
        "target_reply_generation",
        "sentence_boundary_ordinal",
        "correlation_tokens",
    }
)
_ACTION_ALLOWED_FIELDS = {
    "provider_reconnect_context_written": frozenset({
        "action", "at_ms", "success", "provider_ordinal_after_send",
        "session_token", "correlation_tokens",
    }),
    "rag_probe_injected": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_ordinal_after_send",
            "source_asr_ordinal",
            "correlation_tokens",
        }
    ),
    "client_interrupt_sent": frozenset(
        {
            "action",
            "at_ms",
            "reply_active",
            "success",
            "stop_token",
            "local_stop_at_ms",
            "provider_ordinal_after_send",
            "target_tts_start_ordinal",
            "target_reply_generation",
            "correlation_tokens",
        }
    ),
    "client_stop_playback_applied": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "stop_token",
            "target_reply_generation",
            "provider_ordinal_after_ack",
            "correlation_tokens",
        }
    ),
    "client_sentence_played": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "sentence_token",
            "sentence_boundary_ordinal",
            "provider_ordinal_after_ack",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_seed_injected": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_ordinal_after_send",
            "context_ack_ordinal",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_seed_exposed": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "reason_code",
            "provider_event_ordinal",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_attempt": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_ordinal_before_attempt",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_succeeded": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_ordinal_after_reconnect",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_failed": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "reason_code",
            "provider_ordinal_after_reconnect",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_question_observed": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_event_ordinal",
            "session_token",
            "correlation_tokens",
        }
    ),
    "provider_reconnect_context_confirmed": frozenset(
        {
            "action",
            "at_ms",
            "success",
            "provider_ordinal_after_ack",
            "session_token",
            "correlation_tokens",
        }
    ),
}
_ACTION_CORRELATION_PATHS = frozenset(
    {
        "frame.session_id",
        "payload.session_id",
        "payload.question_id",
        "payload.reply_id",
        "payload.sentence_id",
        "phase0.asr_question",
        "phase0.reconnect_seed",
        "phase0.reconnect_question",
    }
)

_EVIDENCE_PUBLIC_FIELDS = (
    "id",
    "evidence_report_id",
    "evidence_run_id",
    "capability_key",
    "verification_result",
    "source_type",
    "provider_profile",
    "model_version",
    "protocol_profile",
    "adapter_version",
    "sdk_version",
    "evidence_suite_version",
    "evidence_fingerprint",
    "report_sha256",
    "tested_at",
    "verified_at",
    "evidence_ttl_days_snapshot",
    "expires_at",
    "created_at",
)


class CapabilityStateError(ValueError):
    """A frozen capability-state field is missing or outside its contract."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message


class CapabilityEvidenceAccessError(PermissionError):
    """A caller outside the five voice-config read roles requested evidence."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def evidence_dimensions(value: Mapping[str, Any]) -> dict[str, str]:
    """Project and validate the exact six dimensions used by the fingerprint."""

    if not isinstance(value, Mapping):
        raise CapabilityStateError(
            "VOICE_CAPABILITY_EVIDENCE_DIMENSION_INVALID",
            "dimensions",
            "能力证据维度必须是对象",
        )
    projected: dict[str, str] = {}
    for field in EVIDENCE_FINGERPRINT_FIELDS:
        field_value = value.get(field)
        if (
            not isinstance(field_value, str)
            or _SAFE_DIMENSION_RE.fullmatch(field_value) is None
        ):
            raise CapabilityStateError(
                "VOICE_CAPABILITY_EVIDENCE_DIMENSION_INVALID",
                field,
                f"{field} 必须符合冻结安全 code 语法",
            )
        projected[field] = field_value
    return projected


def compute_evidence_fingerprint(value: Mapping[str, Any]) -> str:
    """Return lowercase SHA-256 hex over canonical JSON of the six dimensions."""

    canonical = _canonical_json(evidence_dimensions(value))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_evidence_ttl_days(value: Any) -> int:
    """Validate the frozen inclusive evidence TTL range of 7..90 days."""

    if (
        type(value) is not int
        or value < _EVIDENCE_TTL_MIN_DAYS
        or value > _EVIDENCE_TTL_MAX_DAYS
    ):
        raise CapabilityStateError(
            "VOICE_CAPABILITY_EVIDENCE_TTL_INVALID",
            "evidence_ttl_days",
            "evidence_ttl_days 必须是 7–90 的整数",
        )
    return value


def evidence_expires_at(verified_at: datetime, ttl_days: Any) -> datetime:
    """Calculate the immutable expiry instant from verification time and TTL."""

    if not isinstance(verified_at, datetime):
        raise CapabilityStateError(
            "VOICE_CAPABILITY_VERIFIED_AT_INVALID",
            "verified_at",
            "verified_at 必须是 datetime",
        )
    return verified_at + timedelta(days=validate_evidence_ttl_days(ttl_days))


def _evidence_error(code: str, field: str, message: str) -> CapabilityStateError:
    return CapabilityStateError(code, field, message)


def _require_exact_dict(value: Any, fields: frozenset[str], *, path: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            path,
            f"{path} 键集必须严格匹配冻结契约",
        )
    return value


def _require_uuid(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_UUID_INVALID",
            path,
            f"{path} 必须是 UUID 字符串",
        )
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_UUID_INVALID",
            path,
            f"{path} 必须是合法 UUID",
        ) from exc
    if str(parsed) != value.lower():
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_UUID_INVALID",
            path,
            f"{path} 必须使用规范小写 UUID",
        )
    return value


def _require_sha256(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_HASH_INVALID",
            path,
            f"{path} 必须是 64 位小写 SHA-256",
        )
    return value


def _canonical_sha256(value: Any, *, path: str) -> str:
    try:
        canonical = _canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            path,
            f"{path} 必须是可规范化的 JSON",
        ) from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_evidence_datetime(value: Any, *, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
            path,
            f"{path} 必须是规范 UTC ISO-8601 Z 时间",
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
            path,
            f"{path} 不是合法时间",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
            path,
            f"{path} 必须是 UTC 时间",
        )
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
            path,
            f"{path} 必须使用规范 UTC 表示",
        )
    return parsed


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _reject_unsafe_values(value: Any, *, path: str) -> None:
    try:
        text = _canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            path,
            f"{path} 必须是安全 JSON",
        ) from exc
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_SENSITIVE_DATA_REJECTED",
                path,
                f"{path} 包含密钥、明文标识或可推断个人信息",
            )


def _valid_payload_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 256:
        return False
    parts = value.split(".")
    if not parts or parts[0] != "payload":
        return False
    return all(
        part in _PAYLOAD_PATH_PARTS
        or _DYNAMIC_KEY_RE.fullmatch(part) is not None
        or (_PATH_SEGMENT_RE.fullmatch(part) is not None and part.isdigit())
        for part in parts
    )


def _valid_correlation_path(value: Any) -> bool:
    if value in {
        "frame.session_id",
        "phase0.sentence_boundary",
        "phase0.asr_question",
        "phase0.reconnect_seed",
        "phase0.reconnect_question",
    }:
        return True
    return _valid_payload_path(value)


def _validate_payload_shape(value: Any, *, path: str) -> None:
    shape = _require_exact_dict(value, _PAYLOAD_SHAPE_FIELDS, path=path)
    object_keys = shape["object_keys"]
    if (
        type(object_keys) is not list
        or len(object_keys) > _MAX_SHAPE_ENTRIES
        or len(object_keys) != len(set(object_keys))
        or not all(_valid_payload_path(item) for item in object_keys)
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.object_keys",
            "Provider payload object key 投影非法",
        )
    redacted = shape["redacted_key_classes"]
    if (
        type(redacted) is not list
        or len(redacted) != len(set(redacted))
        or not all(item in _REDACTED_KEY_CLASSES for item in redacted)
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.redacted_key_classes",
            "Provider payload 脱敏类别非法",
        )
    maps = {
        field: shape[field]
        for field in (
            "list_lengths",
            "numeric_fields",
            "boolean_fields",
            "text_fields",
            "binary_fields",
        )
    }
    if any(type(items) is not dict for items in maps.values()):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            path,
            "Provider payload shape map 非法",
        )
    if sum(len(items) for items in maps.values()) > _MAX_SHAPE_ENTRIES:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            path,
            "Provider payload shape 超过上限",
        )
    if not all(_valid_payload_path(key) for items in maps.values() for key in items):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            path,
            "Provider payload path 非法",
        )
    if not all(
        type(item) is int and 0 <= item <= 1_000_000_000
        for field in ("list_lengths", "binary_fields")
        for item in shape[field].values()
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            path,
            "Provider payload 长度投影非法",
        )
    if not all(
        type(item) is dict
        and set(item) == {"kind"}
        and item["kind"] in {"integer", "float"}
        for item in shape["numeric_fields"].values()
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.numeric_fields",
            "Provider numeric 只能保存类型投影",
        )
    if not all(
        type(item) is dict
        and set(item) == {"kind"}
        and item["kind"] == "boolean"
        for item in shape["boolean_fields"].values()
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.boolean_fields",
            "Provider boolean 只能保存类型投影",
        )
    if not all(
        type(item) is dict
        and set(item) == {"chars", "token"}
        and type(item["chars"]) is int
        and 0 <= item["chars"] <= 1_000_000_000
        and isinstance(item["token"], str)
        and _HMAC_TOKEN_RE.fullmatch(item["token"]) is not None
        for item in shape["text_fields"].values()
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.text_fields",
            "Provider text 只能保存长度和 HMAC token",
        )


def _validate_event(value: Any, *, path: str, schema_version: str = _PHASE0_RECORD_SCHEMA) -> None:
    if type(value) is not dict or set(value) - _EVENT_FIELDS or _EVENT_REQUIRED_FIELDS - set(value):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            path,
            "Provider event 键集非法",
        )
    if type(value["ordinal"]) is not int or value["ordinal"] < 1:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.ordinal",
            "event ordinal 非法",
        )
    if type(value["received_at_ms"]) is not int or value["received_at_ms"] < 0:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.received_at_ms",
            "event timestamp 非法",
        )
    event_id = value["event_id"]
    if event_id is not None and type(event_id) is not int:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.event_id",
            "event_id 非法",
        )
    expected_name = _EVENT_NAMES.get(event_id, "ProviderEvent")
    if schema_version == _PHASE0_RECORD_SCHEMA and event_id == 567:
        expected_name = "ProviderEvent"
    if value["event_name"] != expected_name:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.event_name",
            "event_name 未由权威 event_id 证明",
        )
    if type(value["target_event"]) is not bool or value["target_event"] != (
        expected_name in _TARGET_EVENT_NAMES
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.target_event",
            "target_event 投影非法",
        )
    if value["message_type"] not in _MESSAGE_TYPES:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.message_type",
            "message_type 非法",
        )
    if value["payload_kind"] not in _PAYLOAD_KINDS:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.payload_kind",
            "payload_kind 非法",
        )
    if type(value["payload_size"]) is not int or value["payload_size"] < 0:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.payload_size",
            "payload_size 非法",
        )
    for field in ("is_audio", "parse_error"):
        if type(value[field]) is not bool:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
                f"{path}.{field}",
                f"{field} 必须是 bool",
            )
    if "probe_match" in value and not (
        value["probe_match"] is True and expected_name == "ChatResponse"
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.probe_match",
            "probe_match 非法",
        )
    correlations = value["correlation_tokens"]
    if (
        type(correlations) is not dict
        or len(correlations) > _MAX_SHAPE_ENTRIES
        or not all(_valid_correlation_path(key) for key in correlations)
        or not all(
            isinstance(token, str) and _HMAC_TOKEN_RE.fullmatch(token) is not None
            for token in correlations.values()
        )
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.correlation_tokens",
            "event correlation token 非法",
        )
    _validate_payload_shape(value["payload_shape"], path=f"{path}.payload_shape")


def _validate_action(value: Any, *, path: str) -> None:
    if type(value) is not dict or set(value) - _ACTION_COMMON_FIELDS:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            path,
            "action 键集非法",
        )
    name = value.get("action")
    allowed = _ACTION_ALLOWED_FIELDS.get(name)
    if allowed is None or set(value) - allowed:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            f"{path}.action",
            "action 类型或字段非法",
        )
    if type(value.get("at_ms")) is not int or value["at_ms"] < 0:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            f"{path}.at_ms",
            "action timestamp 非法",
        )
    for field in ("reply_active", "success"):
        if field in value and type(value[field]) is not bool:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
                f"{path}.{field}",
                f"{field} 必须是 bool",
            )
    if "local_stop_at_ms" in value and (
        type(value["local_stop_at_ms"]) is not int or value["local_stop_at_ms"] < 0
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            f"{path}.local_stop_at_ms",
            "local stop timestamp 非法",
        )
    for field in ("sentence_token", "stop_token", "session_token"):
        if field in value and (
            not isinstance(value[field], str)
            or _HMAC_TOKEN_RE.fullmatch(value[field]) is None
        ):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
                f"{path}.{field}",
                f"{field} 必须是 HMAC token",
            )
    if "reason_code" in value and (
        not isinstance(value["reason_code"], str)
        or _SAFE_CODE_RE.fullmatch(value["reason_code"]) is None
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            f"{path}.reason_code",
            "action reason_code 非法",
        )
    for field in (
        "provider_ordinal_after_send",
        "provider_ordinal_after_ack",
        "provider_ordinal_before_attempt",
        "provider_ordinal_after_reconnect",
    ):
        if field in value and (type(value[field]) is not int or value[field] < 0):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
                f"{path}.{field}",
                f"{field} 非法",
            )
    for field in (
        "provider_event_ordinal",
        "source_asr_ordinal",
        "context_ack_ordinal",
        "target_tts_start_ordinal",
        "target_reply_generation",
        "sentence_boundary_ordinal",
    ):
        if field in value and (type(value[field]) is not int or value[field] < 1):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
                f"{path}.{field}",
                f"{field} 非法",
            )
    if "correlation_tokens" in value:
        correlations = value["correlation_tokens"]
        if (
            type(correlations) is not dict
            or not correlations
            or set(correlations) - _ACTION_CORRELATION_PATHS
            or not all(
                isinstance(token, str)
                and _HMAC_TOKEN_RE.fullmatch(token) is not None
                for token in correlations.values()
            )
        ):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
                f"{path}.correlation_tokens",
                "action correlation token 非法",
            )


def _correlations(value: Mapping[str, Any]) -> Mapping[str, Any]:
    correlations = value.get("correlation_tokens")
    return correlations if isinstance(correlations, Mapping) else {}


def _same_correlation(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *fields: str,
) -> bool:
    left_tokens = _correlations(left)
    right_tokens = _correlations(right)
    return all(
        isinstance(left_tokens.get(field), str)
        and left_tokens.get(field) == right_tokens.get(field)
        for field in fields
    )


def _event_named(events: Sequence[Mapping[str, Any]], name: str) -> list[Mapping[str, Any]]:
    return [event for event in events if event.get("event_name") == name]


def _action_named(
    actions: Sequence[Mapping[str, Any]], name: str
) -> list[Mapping[str, Any]]:
    return [action for action in actions if action.get("action") == name]


def _causal_failure(path: str, message: str) -> CapabilityStateError:
    return _evidence_error(
        "VOICE_CAPABILITY_EVIDENCE_CAUSALITY_UNPROVEN",
        path,
        message,
    )


def _validate_reconnect_context_write(seed, events, actions, *, path: str) -> None:
    """Validate v4 preparation independently of the Phase0 producer."""
    writes = _action_named(actions, "provider_reconnect_context_written")
    if len(writes) != 1 or writes[0].get("success") is not True:
        raise _causal_failure(path, "重连缺少唯一成功上下文写入")
    write = writes[0]
    before = write.get("provider_ordinal_after_send")
    ack_ordinal = seed.get("context_ack_ordinal")
    seed_ordinal = seed.get("provider_ordinal_after_send")
    session = seed.get("session_token")
    nonce = _correlations(seed).get("phase0.reconnect_seed")
    if not (
        all(type(v) is int for v in (before, ack_ordinal, seed_ordinal))
        and 0 <= before < ack_ordinal < seed_ordinal
        and isinstance(session, str) and write.get("session_token") == session
        and isinstance(nonce, str) and _HMAC_TOKEN_RE.fullmatch(nonce)
        and _correlations(write).get("phase0.reconnect_seed") == nonce
    ):
        raise _causal_failure(path, "上下文写入与 seed 的 session/标记/时序不匹配")
    window = [e for e in events if before < e["ordinal"] < seed_ordinal
              and _correlations(e).get("frame.session_id") == session]
    acks = [e for e in window if e.get("event_id") == 567]
    if len(acks) != 1:
        raise _causal_failure(path, "上下文写入缺少唯一 ConversationCreated")
    ack = acks[0]
    if not (
        ack["ordinal"] == ack_ordinal and ack["event_name"] == "ConversationCreated"
        and ack["message_type"] == "SERVER_FULL_RESPONSE" and ack["parse_error"] is False
        and ack["is_audio"] is False and ack["payload_kind"] == "object"
        and write["at_ms"] <= ack["received_at_ms"] <= seed["at_ms"]
        and _correlations(ack).get("phase0.reconnect_seed") == nonce
    ):
        raise _causal_failure(path, "ConversationCreated 未确认完整且匹配的上下文对")
    shape = ack["payload_shape"]
    required = {"payload.items"} | {
        f"payload.items.{i}.{field}" for i in (0, 1)
        for field in ("item_id", "role", "text", "timestamp")
    }
    if shape["list_lengths"].get("payload.items") != 2 or not required.issubset(shape["object_keys"]):
        raise _causal_failure(path, "ConversationCreated 缺少完整 QA 字段")
    for i, role_length in ((0, 4), (1, 9)):
        prefix = f"payload.items.{i}"
        role = shape["text_fields"].get(prefix + ".role", {})
        body = shape["text_fields"].get(prefix + ".text", {})
        item_id = _correlations(ack).get(prefix + ".item_id")
        if not (
            role.get("chars") == role_length
            and isinstance(role.get("token"), str) and _HMAC_TOKEN_RE.fullmatch(role["token"])
            and type(body.get("chars")) is int and body["chars"] > 0
            and isinstance(body.get("token"), str) and _HMAC_TOKEN_RE.fullmatch(body["token"])
            and isinstance(item_id, str) and _HMAC_TOKEN_RE.fullmatch(item_id)
            and shape["numeric_fields"].get(prefix + ".timestamp") == {"kind": "integer"}
        ):
            raise _causal_failure(path, "ConversationCreated 的 QA 类型或安全投影不完整")
    if any(
        e.get("event_name") in {"SessionStarted", "SessionFailed", "SessionFinished",
                                "ChatResponse", "ChatEnded", "TTSSentenceStart"}
        or (e["ordinal"] < ack_ordinal and e.get("event_name") in {"ASRInfo", "ASRResponse"})
        for e in window
    ):
        raise _causal_failure(path, "上下文准备期间出现会话或回合变化")


def _validate_mapping_window(
    events: Sequence[Mapping[str, Any]],
    *,
    path: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    def boundary_identity(
        start: Mapping[str, Any], end: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        start_tokens = _correlations(start)
        end_tokens = _correlations(end)
        sentence_id = start_tokens.get("payload.sentence_id")
        if (
            isinstance(sentence_id, str)
            and _HMAC_TOKEN_RE.fullmatch(sentence_id) is not None
            and sentence_id == end_tokens.get("payload.sentence_id")
        ):
            return "sentence_id", sentence_id
        start_text = (
            (start.get("payload_shape") or {}).get("text_fields") or {}
        ).get("payload.text", {})
        end_text = ((end.get("payload_shape") or {}).get("text_fields") or {}).get(
            "payload.text", {}
        )
        start_token = start_text.get("token")
        end_token = end_text.get("token")
        if (
            isinstance(start_token, str)
            and _HMAC_TOKEN_RE.fullmatch(start_token) is not None
            and start_text.get("chars", 0) > 0
            and start_token == end_token
        ):
            return "exact_text", start_token
        if (
            isinstance(start_token, str)
            and _HMAC_TOKEN_RE.fullmatch(start_token) is not None
            and start_text.get("chars") == 0
            and isinstance(end_token, str)
            and _HMAC_TOKEN_RE.fullmatch(end_token) is not None
            and end_text.get("chars", 0) > 0
        ):
            return "adjacent_end_text", end_token
        return None

    starts = _event_named(events, "TTSSentenceStart")
    ends = _event_named(events, "TTSSentenceEnd")
    audio_events = [
        event
        for event in _event_named(events, "TTSResponse")
        if event.get("is_audio") is True and event.get("payload_kind") == "binary"
    ]
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for boundary in sorted([*starts, *ends], key=lambda item: int(item["ordinal"])):
        tokens = _correlations(boundary)
        key = (
            str(tokens.get("frame.session_id") or ""),
            str(tokens.get("payload.question_id") or ""),
            str(tokens.get("payload.reply_id") or ""),
        )
        if not all(key):
            continue
        groups.setdefault(key, []).append(boundary)
    valid_windows: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for boundaries in groups.values():
        # Provider text/sequence identities are local to one session/question/reply.
        identities: set[tuple[str, str]] = set()
        names = {event["event_name"] for event in boundaries}
        if not {"TTSSentenceStart", "TTSSentenceEnd"}.issubset(names):
            continue
        if len(boundaries) % 2:
            raise _causal_failure(path, "sentence boundary 数量不成对")
        for index in range(0, len(boundaries), 2):
            start = boundaries[index]
            end = boundaries[index + 1]
            identity = boundary_identity(start, end)
            if (
                start["event_name"] != "TTSSentenceStart"
                or end["event_name"] != "TTSSentenceEnd"
                or int(start["ordinal"]) >= int(end["ordinal"])
                or int(start["received_at_ms"]) > int(end["received_at_ms"])
                or identity is None
                or identity in identities
            ):
                raise _causal_failure(path, "sentence boundary 顺序或 identity 存在歧义")
            identities.add(identity)
            if not any(
                int(start["ordinal"]) < int(audio["ordinal"]) < int(end["ordinal"])
                and int(start["received_at_ms"])
                <= int(audio["received_at_ms"])
                <= int(end["received_at_ms"])
                and _same_correlation(start, audio, "frame.session_id")
                for audio in audio_events
            ):
                raise _causal_failure(path, "correlated sentence window 内没有音频")
            valid_windows.append((start, end))
    if valid_windows:
        return valid_windows[0]
    raise _causal_failure(path, "缺少同 session/reply/sentence 的 start/audio/end 映射窗口")


def _validate_interrupt_window(
    events: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    *,
    expect_success: bool | None,
    path: str,
) -> None:
    interrupts = _action_named(actions, "client_interrupt_sent")
    stop_acks = _action_named(actions, "client_stop_playback_applied")
    if len(interrupts) != 1 or not stop_acks:
        raise _causal_failure(path, "缺少唯一 interrupt 与本地 stop ack")
    interrupt = interrupts[0]
    if (
        interrupt.get("success") is not True
        or interrupt.get("reply_active") is not True
        or type(interrupt.get("target_tts_start_ordinal")) is not int
        or type(interrupt.get("provider_ordinal_after_send")) is not int
        or type(interrupt.get("target_reply_generation")) is not int
        or type(interrupt.get("local_stop_at_ms")) is not int
    ):
        raise _causal_failure(path, "interrupt 动作缺少活动 reply、generation 或 Provider 水位锚")
    start = next(
        (
            event
            for event in _event_named(events, "TTSSentenceStart")
            if int(event["ordinal"]) == interrupt["target_tts_start_ordinal"]
            and int(event["ordinal"]) <= interrupt["provider_ordinal_after_send"]
            and int(event["received_at_ms"]) <= interrupt["at_ms"]
            and _same_correlation(
                event,
                interrupt,
                "payload.question_id",
                "payload.reply_id",
            )
            and isinstance(_correlations(event).get("frame.session_id"), str)
        ),
        None,
    )
    if start is None or not (
        int(start["received_at_ms"])
        <= interrupt["local_stop_at_ms"]
        <= interrupt["at_ms"]
    ):
        raise _causal_failure(path, "interrupt 未绑定目标 TTS start 或本地停止时序")
    matching_stop_acks = [
        action
        for action in stop_acks
        if action.get("stop_token") == interrupt.get("stop_token")
        and action.get("target_reply_generation")
        == interrupt["target_reply_generation"]
        and type(action.get("provider_ordinal_after_ack")) is int
        and action["provider_ordinal_after_ack"] >= int(start["ordinal"])
        and action["at_ms"] >= interrupt["local_stop_at_ms"]
    ]
    if len(matching_stop_acks) != 1:
        raise _causal_failure(path, "本地 stop ack 未绑定同一 stop token/reply generation")
    stop_ack = matching_stop_acks[0]
    terminals = [
        event
        for event in _event_named(events, "TTSEnded")
        if int(event["ordinal"]) > interrupt["provider_ordinal_after_send"]
        and int(event["received_at_ms"]) > interrupt["at_ms"]
        and _same_correlation(
            event,
            interrupt,
            "payload.question_id",
            "payload.reply_id",
        )
        and _same_correlation(event, start, "frame.session_id")
    ]
    if not terminals:
        raise _causal_failure(path, "缺少 interrupt 后同 reply 的 Provider 终止锚")
    terminal_in_grace = min(event["received_at_ms"] for event in terminals) <= (
        interrupt["at_ms"] + 350
    )
    ack_in_grace = stop_ack["at_ms"] <= interrupt["local_stop_at_ms"] + 350
    late_audio = any(
        event.get("event_name") == "TTSResponse"
        and event.get("is_audio") is True
        and int(event["received_at_ms"]) > interrupt["at_ms"] + 350
        and _same_correlation(event, start, "frame.session_id")
        for event in events
    )
    proven_success = (
        stop_ack.get("success") is True
        and terminal_in_grace
        and ack_in_grace
        and not late_audio
    )
    proven_failure = (
        stop_ack.get("success") is False
        or not terminal_in_grace
        or not ack_in_grace
        or late_audio
    )
    if expect_success is True and not proven_success:
        raise _causal_failure(path, "cancel passed 缺少 350ms 内终止与本地 stop 成功锚")
    if expect_success is False and not proven_failure:
        raise _causal_failure(path, "cancel failed 缺少超时、迟到音频或 stop 失败锚")


def _validate_capability_conclusion(
    *,
    capability_key: str,
    result: str,
    payload: Mapping[str, Any],
    path: str,
) -> None:
    events = payload["event_evidence"]
    actions = payload["action_evidence"]
    ordinals = [event["ordinal"] for event in events]
    if len(ordinals) != len(set(ordinals)):
        raise _causal_failure(path, "Provider event ordinal 必须唯一")
    reason = payload["reason_code"]

    if capability_key == "supports_current_turn_rag_gate":
        expected_reason = {
            "passed": "same_turn_probe_matched_single_reply",
            "failed": "same_turn_probe_not_confirmed_or_double_reply",
        }[result]
        if reason != expected_reason:
            raise _causal_failure(path, "RAG reason 与 Phase0 v3 评估结论不一致")
        attempts = _action_named(actions, "rag_probe_injected")
        if len(attempts) != 1:
            raise _causal_failure(path, "RAG 必须包含唯一 probe injection")
        action = attempts[0]
        source = next(
            (
                event
                for event in _event_named(events, "ASRResponse")
                if action.get("success") is True
                and event["ordinal"] == action.get("source_asr_ordinal")
                and event["ordinal"] == action.get("provider_ordinal_after_send")
                and event["received_at_ms"] <= action.get("at_ms", -1)
                and _same_correlation(event, action, "frame.session_id")
                and any(
                    isinstance(_correlations(event).get(field), str)
                    and _correlations(event).get(field)
                    == _correlations(action).get(field)
                    for field in (
                        "phase0.asr_question",
                        "payload.question_id",
                    )
                )
            ),
            None,
        )
        if source is None:
            raise _causal_failure(path, "RAG 缺少 injection 前的精确 source ASR 水位锚")
        responses = [
            event
            for event in _event_named(events, "ChatResponse")
            if event["ordinal"] > source["ordinal"]
            and _same_correlation(event, action, "frame.session_id")
            and _same_correlation(
                event, action, "payload.question_id", "payload.reply_id"
            )
        ]
        endings = [
            event
            for event in _event_named(events, "ChatEnded")
            if responses
            and event["ordinal"] > responses[-1]["ordinal"]
            and _same_correlation(event, action, "frame.session_id")
            and _same_correlation(
                event, action, "payload.question_id", "payload.reply_id"
            )
        ]
        reply_window = [
            event
            for event in events
            if event.get("event_name") in {"ChatResponse", "ChatEnded"}
            and event["ordinal"] > source["ordinal"]
        ]
        window_has_other_reply = any(
            not (
                _same_correlation(event, action, "frame.session_id")
                and _same_correlation(
                    event,
                    action,
                    "payload.question_id",
                    "payload.reply_id",
                )
            )
            for event in reply_window
        )
        passed = (
            bool(responses)
            and any(response.get("probe_match") is True for response in responses)
            and len(endings) == 1
            and not window_has_other_reply
        )
        failed = bool(endings) and not passed
        if (result == "passed" and not passed) or (result == "failed" and not failed):
            raise _causal_failure(path, "RAG reply/probe/end 因果链不能支持声明结论")
        return

    if capability_key == "supports_reply_cancel":
        expected_reason = {
            "passed": "active_reply_cancelled_and_local_stop_applied_within_grace",
            "failed": "provider_cancel_or_local_stop_exceeded_grace",
        }[result]
        if reason != expected_reason:
            raise _causal_failure(path, "cancel reason 与 Phase0 v3 评估结论不一致")
        _validate_interrupt_window(
            events,
            actions,
            expect_success=result == "passed",
            path=path,
        )
        return

    if capability_key == "supports_context_truncate":
        truncate_id_is_authoritative = "ConversationTruncated" in _EVENT_NAMES.values()
        allowed_reasons = (
            {"conversation_truncated_event_observed"}
            if result == "passed"
            else (
                {"conversation_truncated_event_not_observed"}
                if truncate_id_is_authoritative
                else {"conversation_truncated_event_id_not_authoritative"}
            )
        )
        if reason not in allowed_reasons:
            raise _causal_failure(path, "truncate reason 与 Phase0 v3 评估结论不一致")
        # A completed interrupt window is the probe boundary.  The authoritative
        # truncate event must then distinguish passed from a trustworthy NO-GO.
        _validate_interrupt_window(
            events,
            actions,
            expect_success=None,
            path=path,
        )
        has_truncate = bool(_event_named(events, "ConversationTruncated"))
        if (result == "passed") != has_truncate:
            raise _causal_failure(path, "truncate event presence 与声明结论不一致")
        return

    if capability_key == "supports_playback_text_mapping":
        passed_reasons = {
            "adjacent_provider_sentence_end_text_reply_session_correlates_with_audio",
            "sentence_identity_reply_session_boundaries_correlate_with_audio",
        }
        failed_reasons = {
            "provider_sentence_boundary_sequence_is_ambiguous",
            "correlated_sentence_window_contains_no_audio",
        }
        if reason not in (passed_reasons if result == "passed" else failed_reasons):
            raise _causal_failure(path, "mapping reason 与 Phase0 v3 评估结论不一致")
        if result == "passed":
            _validate_mapping_window(events, path=path)
        else:
            starts = _event_named(events, "TTSSentenceStart")
            ends = _event_named(events, "TTSSentenceEnd")
            has_correlated_probe = any(
                start["ordinal"] < end["ordinal"]
                and _same_correlation(
                    start,
                    end,
                    "frame.session_id",
                    "payload.question_id",
                    "payload.reply_id",
                )
                for start in starts
                for end in ends
            )
            if not has_correlated_probe:
                raise _causal_failure(path, "mapping failed 缺少相关 sentence boundary 探针")
            failure: CapabilityStateError | None = None
            try:
                _validate_mapping_window(events, path=path)
            except CapabilityStateError as exc:
                failure = exc
            if failure is not None:
                no_audio = "没有音频" in failure.message
                if (
                    reason == "correlated_sentence_window_contains_no_audio"
                    and not no_audio
                ):
                    raise _causal_failure(path, "mapping no-audio reason 缺少精确无音频锚")
                if (
                    reason == "provider_sentence_boundary_sequence_is_ambiguous"
                    and no_audio
                ):
                    raise _causal_failure(path, "mapping ambiguous reason 实际仅缺少音频")
                return
            raise _causal_failure(path, "mapping failed 却存在完整无歧义映射窗口")
        return

    if capability_key == "supports_sentence_playback_ack":
        expected_reason = {
            "passed": "client_confirmed_exact_provider_sentence_played",
            "failed": "client_sentence_ack_failed_for_correlated_boundary",
        }[result]
        if reason != expected_reason:
            raise _causal_failure(path, "sentence ack reason 与 Phase0 v3 评估结论不一致")
        _, end = _validate_mapping_window(events, path=path)
        acks = _action_named(actions, "client_sentence_played")
        matched = [
            action
            for action in acks
            if action.get("sentence_boundary_ordinal") == end["ordinal"]
            and action.get("provider_ordinal_after_ack", -1) >= end["ordinal"]
            and action.get("at_ms", -1) >= end["received_at_ms"]
            and action.get("sentence_token")
            == _correlations(end).get("phase0.sentence_boundary")
        ]
        expected_success = result == "passed"
        if len(matched) != 1 or matched[0].get("success") is not expected_success:
            raise _causal_failure(path, "sentence ack 未绑定精确 boundary/token/watermark")
        return

    if capability_key == "supports_session_reconnect":
        if result == "failed" and reason == "reconnect_seed_exposed_before_disconnect":
            exposures = _action_named(actions, "provider_reconnect_seed_exposed")
            if len(exposures) != 1:
                raise _causal_failure(path, "reconnect seed exposure 缺少唯一动作锚")
            exposure = exposures[0]
            event = next(
                (
                    event
                    for event in events
                    if event["ordinal"] == exposure.get("provider_event_ordinal")
                    and event["received_at_ms"] <= exposure.get("at_ms", -1)
                    and _same_correlation(event, exposure, "frame.session_id")
                ),
                None,
            )
            if event is None or exposure.get("success") is not False:
                raise _causal_failure(path, "reconnect seed exposure 未绑定 Provider 事件/session")
            return
        seeds = _action_named(actions, "provider_reconnect_seed_injected")
        attempts = _action_named(actions, "provider_reconnect_attempt")
        if len(seeds) != 1 or len(attempts) != 1:
            raise _causal_failure(path, "reconnect 缺少唯一 seed injection/attempt")
        seed = seeds[0]
        attempt = attempts[0]
        session_token = seed.get("session_token")
        if (
            seed.get("success") is not True
            or attempt.get("success") is not True
            or not isinstance(session_token, str)
            or attempt.get("session_token") != session_token
        ):
            raise _causal_failure(path, "reconnect seed/attempt 未绑定同一 session")
        seed_asr = next(
            (
                event
                for event in _event_named(events, "ASRResponse")
                if event["ordinal"] == seed.get("provider_ordinal_after_send")
                and event["received_at_ms"] <= seed.get("at_ms", -1)
                and _correlations(event).get("frame.session_id") == session_token
            ),
            None,
        )
        if seed_asr is None or attempt.get("provider_ordinal_before_attempt", -1) < seed_asr[
            "ordinal"
        ]:
            raise _causal_failure(path, "reconnect seed ASR/attempt Provider 水位链缺失")

        if payload["schema_version"] == _PHASE0_CONTEXT_RECORD_SCHEMA:
            _validate_reconnect_context_write(seed, events, actions, path=path)

        seed_responses = [
            event
            for event in _event_named(events, "ChatResponse")
            if seed_asr["ordinal"] < event["ordinal"]
            <= attempt.get("provider_ordinal_before_attempt", -1)
            and _correlations(event).get("frame.session_id") == session_token
            and _same_correlation(
                event, seed, "payload.question_id", "payload.reply_id"
            )
        ]
        seed_endings = [
            event
            for event in _event_named(events, "ChatEnded")
            if seed_responses
            and seed_responses[-1]["ordinal"] < event["ordinal"]
            <= attempt.get("provider_ordinal_before_attempt", -1)
            and _correlations(event).get("frame.session_id") == session_token
            and _same_correlation(
                event, seed, "payload.question_id", "payload.reply_id"
            )
        ]
        if not seed_responses or len(seed_endings) != 1:
            raise _causal_failure(path, "reconnect seed 缺少完整 reply/end 因果链")

        successes = _action_named(actions, "provider_reconnect_succeeded")
        questions = _action_named(actions, "provider_reconnect_question_observed")
        confirmations = _action_named(actions, "provider_reconnect_context_confirmed")
        failed_context_confirmation = bool(
            result == "failed"
            and reason == "same_session_reconnect_or_hidden_context_restore_failed"
            and len(confirmations) == 1
            and confirmations[0].get("success") is False
        )
        if result == "passed" or failed_context_confirmation:
            if (
                result == "passed"
                and reason != "hidden_seed_preserved_across_same_session_reconnect"
            ):
                raise _causal_failure(path, "reconnect passed reason 不匹配")
            if not (
                len(successes) == len(questions) == len(confirmations) == 1
                and all(
                    action.get("success") is True
                    and action.get("session_token") == session_token
                    for action in (successes[0], questions[0])
                )
                and confirmations[0].get("success") is (result == "passed")
                and confirmations[0].get("session_token") == session_token
            ):
                raise _causal_failure(path, "reconnect 缺少 success/question/context 动作链")
            success = successes[0]
            question = questions[0]
            confirmation = confirmations[0]
            starts = [
                event
                for event in _event_named(events, "SessionStarted")
                if _correlations(event).get("frame.session_id") == session_token
            ]
            post_start = next(
                (
                    event
                    for event in starts
                    if event["ordinal"]
                    == success.get("provider_ordinal_after_reconnect")
                    and event["ordinal"] > attempt.get("provider_ordinal_before_attempt", -1)
                ),
                None,
            )
            question_asr = next(
                (
                    event
                    for event in _event_named(events, "ASRResponse")
                    if event["ordinal"] == question.get("provider_event_ordinal")
                    and post_start is not None
                    and event["ordinal"] > post_start["ordinal"]
                    and _correlations(event).get("frame.session_id") == session_token
                ),
                None,
            )
            responses = [
                event
                for event in _event_named(events, "ChatResponse")
                if question_asr is not None
                and event["ordinal"] > question_asr["ordinal"]
                and _correlations(event).get("frame.session_id") == session_token
                and _same_correlation(
                    event,
                    confirmation,
                    "payload.question_id",
                    "payload.reply_id",
                )
            ]
            endings = [
                event
                for event in _event_named(events, "ChatEnded")
                if responses
                and event["ordinal"] > responses[-1]["ordinal"]
                and _correlations(event).get("frame.session_id") == session_token
                and _same_correlation(
                    event,
                    confirmation,
                    "payload.question_id",
                    "payload.reply_id",
                )
            ]
            if (
                len(starts) < 2
                or post_start is None
                or question_asr is None
                or not responses
                or len(endings) != 1
                or confirmation.get("provider_ordinal_after_ack", -1)
                < endings[0]["ordinal"]
                or confirmation.get("at_ms", -1) < endings[0]["received_at_ms"]
            ):
                raise _causal_failure(path, "reconnect 缺少完整同 session 重连问答/确认因果链")
            if result == "passed" and not any(
                response.get("probe_match") is True for response in responses
            ):
                raise _causal_failure(path, "reconnect passed 缺少隐藏 seed 命中锚")
            prefix = sorted([
                event for event in events
                if post_start['ordinal'] < event['ordinal'] < question_asr['ordinal']
                and (event.get('parse_error') is not False or event.get('event_name') in {
                    'ASRInfo', 'ASRResponse', 'ASREnded', 'ChatResponse', 'ChatEnded',
                    'TTSSentenceStart', 'TTSSentenceEnd', 'TTSResponse', 'TTSEnded',
                })
            ], key=lambda event: event['ordinal'])
            question_identity = (
                _correlations(question_asr).get('payload.question_id')
                or _correlations(question_asr).get('phase0.asr_question')
            )
            if prefix and not (
                prefix[0].get('event_name') == 'ASRInfo'
                and all(event.get('event_name') == 'ASRResponse' for event in prefix[1:])
                and question_identity
                and all(
                    event.get('parse_error') is False
                    and event.get('message_type') == 'SERVER_FULL_RESPONSE'
                    and _correlations(event).get('frame.session_id') == session_token
                    and (_correlations(event).get('payload.question_id')
                         or _correlations(event).get('phase0.asr_question')) == question_identity
                    and success['at_ms'] <= event['received_at_ms'] <= question_asr['received_at_ms']
                    for event in prefix
                )
            ):
                raise _causal_failure(path, "reconnect 受控问题前存在额外输入/回复或识别归属不明")
            initial_dialog = _correlations(starts[0]).get("payload.dialog_id")
            post_dialog = _correlations(post_start).get("payload.dialog_id")
            if not initial_dialog or initial_dialog != post_dialog:
                raise _causal_failure(path, "reconnect 缺少同 dialog 生命周期锚")
            if result == "passed" and any(
                event.get("event_name")
                in {"SessionStarted", "SessionFinished", "SessionFailed"}
                and post_start["ordinal"] < event["ordinal"]
                <= confirmation.get("provider_ordinal_after_ack", -1)
                for event in events
            ):
                raise _causal_failure(path, "reconnect passed 存在握手后 lifecycle boundary")
            return

        failed_reasons = {
            "same_session_reconnect_lifecycle_changed_after_handshake",
            "same_session_reconnect_dialog_id_changed",
            "same_session_reconnect_or_hidden_context_restore_failed",
        }
        if reason not in failed_reasons:
            raise _causal_failure(path, "reconnect failed reason 不匹配")
        if reason == "same_session_reconnect_or_hidden_context_restore_failed":
            failures = _action_named(actions, "provider_reconnect_failed")
            failed_events = [
                event
                for event in _event_named(events, "SessionFailed")
                if event["ordinal"] > attempt.get("provider_ordinal_before_attempt", -1)
                and event["received_at_ms"] >= attempt.get("at_ms", -1)
                and _correlations(event).get("frame.session_id") == session_token
            ]
            action_proven = bool(
                len(failures) == 1
                and failures[0].get("success") is False
                and failures[0].get("session_token") == session_token
                and failures[0].get("provider_ordinal_after_reconnect", -1)
                >= attempt.get("provider_ordinal_before_attempt", -1)
                and failures[0].get("at_ms", -1) >= attempt.get("at_ms", -1)
            )
            event_proven = len(failed_events) == 1
            if len(failures) > 1 or not (action_proven or event_proven):
                raise _causal_failure(path, "reconnect restore failed 缺少失败动作/事件锚")
            return
        starts = _event_named(events, "SessionStarted")
        if len(starts) < 2:
            raise _causal_failure(path, "reconnect lifecycle/dialog failed 缺少前后 SessionStarted")
        if reason == "same_session_reconnect_lifecycle_changed_after_handshake":
            confirmations = _action_named(actions, "provider_reconnect_context_confirmed")
            successes = _action_named(actions, "provider_reconnect_succeeded")
            if len(confirmations) != 1 or len(successes) != 1:
                raise _causal_failure(path, "lifecycle changed 缺少重连确认动作")
            post_start = next(
                (
                    event
                    for event in starts
                    if event["ordinal"]
                    == successes[0].get("provider_ordinal_after_reconnect")
                ),
                None,
            )
            boundary = next(
                (
                    event
                    for event in events
                    if post_start is not None
                    and event.get("event_name")
                    in {"SessionStarted", "SessionFinished", "SessionFailed"}
                    and post_start["ordinal"] < event["ordinal"]
                    <= confirmations[0].get("provider_ordinal_after_ack", -1)
                    and event["received_at_ms"] <= confirmations[0].get("at_ms", -1)
                ),
                None,
            )
            if boundary is None:
                raise _causal_failure(path, "lifecycle changed 结论缺少握手后 boundary")
            return
        first_dialog = _correlations(starts[0]).get("payload.dialog_id")
        last_dialog = _correlations(starts[-1]).get("payload.dialog_id")
        if not first_dialog or not last_dialog or first_dialog == last_dialog:
            raise _causal_failure(path, "dialog changed 结论缺少前后 dialog token 变化锚")
        return

    raise _causal_failure(path, "未知能力不能形成生产证据结论")


def _validate_runtime_conditions(
    value: Any,
    *,
    expected_source: str,
    path: str,
    admin_protocol: bool = False,
) -> dict:
    fields = (
        _RUNTIME_FIELDS
        if expected_source == "phase0_import"
        else _ADMIN_RUNTIME_FIELDS
    )
    if admin_protocol and expected_source == "admin_capability_test":
        fields = fields | {"speaker_output"}
    runtime = _require_exact_dict(value, fields, path=path)
    for field in fields - {"network_profile"}:
        if runtime[field] is not None and type(runtime[field]) is not bool:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_RUNTIME_INVALID",
                f"{path}.{field}",
                f"{field} 必须是 bool 或 null",
            )
    allowed_profiles = (
        _NETWORK_PROFILES
        if expected_source == "phase0_import"
        else frozenset({"admin_test"})
    )
    if runtime["network_profile"] not in allowed_profiles | {None}:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUNTIME_INVALID",
            f"{path}.network_profile",
            "network_profile 非法",
        )
    return runtime


def _validate_m1_protocol_shape(value: Any, *, path: str) -> dict:
    container = _require_exact_dict(value, frozenset({'truncate'}), path=path)
    proof = container['truncate']
    fields = {'status','reason','operations','target_token','item_token','prefix_token','session_token',
              'stop_token','reply_generation','played_ms','received_samples','progress_at_ms',
              'progress_ordinal','before_chars','after_chars','retained_prefix'}
    if (type(proof) is not dict or not {'status','reason','operations'} <= set(proof)
        or set(proof) - fields or proof.get('status') not in ('unverified','verified','failed')):
        raise _causal_failure(path, 'M1 protocol proof 字段或状态非法')
    if not isinstance(proof['reason'], str) or _SAFE_CODE_RE.fullmatch(proof['reason']) is None:
        raise _causal_failure(path, 'M1 protocol reason 非法')
    if proof['status'] != 'unverified' and set(proof) != fields:
        raise _causal_failure(path, 'M1 truncate 完整结论缺字段')
    for key, val in proof.items():
        if key.endswith('_token') and (not isinstance(val,str) or not _HMAC_TOKEN_RE.fullmatch(val)):
            raise _causal_failure(path, 'M1 protocol 标识必须为 HMAC')
        if key in {'reply_generation','played_ms','received_samples','progress_at_ms','progress_ordinal','before_chars','after_chars'}:
            if type(val) is not int or val < 0:
                raise _causal_failure(path, 'M1 protocol 数值非法')
    if 'retained_prefix' in proof and type(proof['retained_prefix']) is not bool:
        raise _causal_failure(path, 'M1 retained_prefix 必须为 bool')
    if type(proof['operations']) is not list or len(proof['operations']) > 3:
        raise _causal_failure(path, 'M1 protocol 操作数量非法')
    request_fields = {'request_event','before_ordinal','after_ordinal','sent_at_ms'}
    ack_fields = {'ack_event','ack_ordinal','ack_at_ms'}
    for op in proof['operations']:
        if (type(op) is not dict or set(op) not in (request_fields, request_fields | ack_fields)
            or any(type(v) is not int or v < 0 for v in op.values())):
            raise _causal_failure(path, 'M1 protocol 操作字段非法')
    return proof


def _validate_m1_truncate(payload: Mapping[str, Any], *, result: str, path: str) -> None:
    proof = payload['protocol_evidence']['truncate']
    status = 'verified' if result == 'passed' else 'failed'
    reason = 'truncate_target_prefix_retained' if result == 'passed' else 'truncate_readback_not_shortened'
    if (proof['status'] != status or proof['reason'] != reason or payload['reason_code'] != reason
        or payload['runtime_conditions'].get('speaker_output') is not True
        or proof['target_token'] != proof['item_token']):
        raise _causal_failure(path, 'M1 truncate 结论或实播条件不匹配')
    events = payload['event_evidence']
    by_ordinal = {e['ordinal']:e for e in events}
    if len(by_ordinal) != len(events):
        raise _causal_failure(path, 'M1 truncate ordinal 重复')
    operations = proof['operations']
    if len(operations) != 3:
        raise _causal_failure(path, 'M1 truncate 缺查询/截断/查询完整序列')
    prev_ordinal, prev_time = proof['progress_ordinal'], proof['progress_at_ms']
    acknowledgements = []
    for op, (request, ack) in zip(operations, ((512,569),(513,570),(512,569))):
        event = by_ordinal.get(op.get('ack_ordinal'))
        if (op.get('request_event') != request or op.get('ack_event') != ack
            or not prev_ordinal <= op['before_ordinal'] <= op['after_ordinal'] < op.get('ack_ordinal', -1)
            or not prev_time <= op['sent_at_ms'] <= op.get('ack_at_ms', -1)
            or event is None or event['event_id'] != ack or event['parse_error']
            or event['message_type'] != 'SERVER_FULL_RESPONSE'
            or event['received_at_ms'] != op['ack_at_ms']
            or event['correlation_tokens'].get('frame.session_id') != proof['session_token']):
            raise _causal_failure(path, 'M1 truncate request/ACK 因果链失效')
        acknowledgements.append(event)
        prev_ordinal, prev_time = op['ack_ordinal'], op['ack_at_ms']
    for index, name in ((0,'before_chars'),(2,'after_chars')):
        event = acknowledgements[index]
        shape = event['payload_shape']
        body = shape['text_fields'].get('payload.items.0.text', {})
        role = shape['text_fields'].get('payload.items.0.role', {})
        if (event['correlation_tokens'].get('payload.items.0.item_id') != proof['item_token']
            or shape['list_lengths'].get('payload.items') != 1 or body.get('chars') != proof[name]
            or role.get('chars') != 9):
            raise _causal_failure(path, 'M1 truncate 查询目标或正文长度不匹配')
    prefix_matches = proof['prefix_token'] == acknowledgements[2]['payload_shape']['text_fields']['payload.items.0.text']['token']
    shortened = prefix_matches and 0 < proof['after_chars'] < proof['before_chars']
    if (proof['retained_prefix'] != (prefix_matches and proof['after_chars'] > 0)
        or (result == 'passed') != shortened):
        raise _causal_failure(path, 'M1 truncate 未能证明目标上下文保留已播前缀')
    starts = [e for e in events if e['event_id'] == 350 and e['ordinal'] <= proof['progress_ordinal']
              and e['correlation_tokens'].get('payload.reply_id') == proof['target_token']]
    ends = [e for e in events if e['event_id'] == 359 and e['ordinal'] <= proof['progress_ordinal']
            and e['correlation_tokens'].get('payload.reply_id') == proof['target_token']]
    if not starts or len(ends) != 1:
        raise _causal_failure(path, 'M1 truncate 缺完整目标音频生成窗口')
    first, end = min(e['ordinal'] for e in starts), ends[0]['ordinal']
    target_window = [e for e in events if first <= e['ordinal'] <= end]
    if any(e['parse_error'] or e['correlation_tokens'].get('frame.session_id') != proof['session_token']
           or (e['correlation_tokens'].get('payload.reply_id') not in (None, proof['target_token'])) for e in target_window):
        raise _causal_failure(path, 'M1 truncate 音频窗口不唯一')
    received_bytes = sum(e['payload_shape']['binary_fields'].get('payload', 0) for e in target_window
                         if e['event_id'] == 352 and e['is_audio'])
    if (received_bytes != proof['received_samples'] * 2
        or not 0 < proof['played_ms'] < received_bytes * 1000 // 48000):
        raise _causal_failure(path, 'M1 truncate 播放进度与完整接收量不一致')
    stop = [a for a in payload['action_evidence'] if a['action'] == 'client_stop_playback_applied'
            and a.get('stop_token') == proof['stop_token'] and a.get('success') is True
            and a.get('target_reply_generation') == proof['reply_generation']
            and a.get('provider_ordinal_after_ack') == proof['progress_ordinal']
            and a['at_ms'] <= proof['progress_at_ms']]
    if len(stop) != 1:
        raise _causal_failure(path, 'M1 truncate 缺实际且唯一的浏览器停止回执')
    ack_ordinals = {op['ack_ordinal'] for op in operations}
    for event in events:
        if (event['ordinal'] > proof['progress_ordinal'] and event['event_id'] in {569,570}
            and event['ordinal'] not in ack_ordinals):
            raise _causal_failure(path, 'M1 truncate 存在迟到或重复的额外回执')
        if proof['progress_ordinal'] < event['ordinal'] <= prev_ordinal and (
            event['parse_error'] or event['event_id'] in {450,451,150,152,153,599}
            or (event['event_id'] in {569,570} and event['ordinal'] not in ack_ordinals)):
            raise _causal_failure(path, 'M1 truncate 窗口混入新问题、错误或额外回执')


def _validate_evidence_payload(
    value: Any,
    *,
    result: str,
    capability_key: str,
    expected_source: str,
    path: str,
) -> dict:
    is_m1 = isinstance(value, dict) and value.get('schema_version') == _PHASE0_PROTOCOL_RECORD_SCHEMA
    payload = _require_exact_dict(value, _PAYLOAD_FIELDS | ({'protocol_evidence'} if is_m1 else set()), path=path)
    if is_m1:
        _validate_m1_protocol_shape(payload['protocol_evidence'], path=f'{path}.protocol_evidence')
    if payload["schema_version"] not in (_PHASE0_RECORD_SCHEMA, _PHASE0_CONTEXT_RECORD_SCHEMA, _PHASE0_PROTOCOL_RECORD_SCHEMA):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            f"{path}.schema_version",
            "evidence payload schema_version 非法",
        )
    if payload["capability_status"] != _RESULT_STATUS[result]:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RESULT_INVALID",
            f"{path}.capability_status",
            "capability_status 与 verification_result 不一致",
        )
    for field in ("reason_code", "degradation_mode"):
        if (
            not isinstance(payload[field], str)
            or _SAFE_CODE_RE.fullmatch(payload[field]) is None
        ):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
                f"{path}.{field}",
                f"{field} 必须是安全受限代码",
            )
    if type(payload["event_evidence"]) is not list:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_EVENT_INVALID",
            f"{path}.event_evidence",
            "event_evidence 必须是数组",
        )
    if type(payload["action_evidence"]) is not list:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_ACTION_INVALID",
            f"{path}.action_evidence",
            "action_evidence 必须是数组",
        )
    for index, event in enumerate(payload["event_evidence"]):
        _validate_event(event, path=f"{path}.event_evidence[{index}]",
                        schema_version=payload["schema_version"])
    for index, action in enumerate(payload["action_evidence"]):
        _validate_action(action, path=f"{path}.action_evidence[{index}]")
    if payload["schema_version"] == _PHASE0_RECORD_SCHEMA and (
        any(a.get("action") == "provider_reconnect_context_written" or "context_ack_ordinal" in a
               for a in payload["action_evidence"])
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID", path,
            "新的上下文准备证据必须使用 v4 schema，旧 v3 语义保持不变",
        )
    runtime = _validate_runtime_conditions(
        payload["runtime_conditions"],
        expected_source=expected_source,
        path=f"{path}.runtime_conditions",
        admin_protocol=is_m1,
    )
    if type(payload["production_import_ready"]) is not bool:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            f"{path}.production_import_ready",
            "production_import_ready 必须是 bool，但不作为导入授权",
        )
    required_runtime = {"real_provider"}
    if expected_source == "phase0_import":
        required_runtime.update(
            {"chrome_desktop", "microphone_permission", "aec_enabled"}
        )
        if capability_key in {
            "supports_reply_cancel",
            "supports_playback_text_mapping",
            "supports_sentence_playback_ack",
            "supports_session_reconnect",
        }:
            required_runtime.add("speaker_output")
    if result in {"passed", "failed"} and any(
        runtime.get(field) is not True for field in required_runtime
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUNTIME_UNPROVEN",
            f"{path}.runtime_conditions",
            "passed/failed 结论缺少该能力所需的真实 Provider 运行条件",
        )
    if result in {"passed", "failed"} and runtime.get("network_profile") is None:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUNTIME_UNPROVEN",
            f"{path}.runtime_conditions.network_profile",
            "passed/failed 结论必须固定 network_profile",
        )
    _reject_unsafe_values(payload, path=path)
    return payload


def _validate_v6_reconnect_playback(payload: Mapping[str, Any], *, path: str) -> None:
    """Independently check the v6 playback seal; legacy evidence is unchanged."""
    actions = payload['action_evidence']
    confirmation = _action_named(actions, 'provider_reconnect_context_confirmed')[0]
    question = _action_named(actions, 'provider_reconnect_question_observed')[0]
    tail = sorted([event for event in payload['event_evidence']
                   if event['ordinal'] > question['provider_event_ordinal']],
                  key=lambda event: event['ordinal'])
    if not tail or any(
        event.get('parse_error') is not False
        or event['received_at_ms'] > confirmation['at_ms']
        or event['event_name'] in {'SessionStarted', 'SessionFailed', 'ASRInfo', 'ASRResponse'}
        for event in tail
    ):
        raise _causal_failure(path, 'v6 reconnect 确认窗口存在异常或新的输入')
    replies = [event for event in tail if event['event_name'] in {'ChatResponse', 'ChatEnded'}]
    tts = [event for event in tail if event['event_name'] in {'TTSSentenceStart', 'TTSSentenceEnd', 'TTSEnded'}]
    if (
        not replies or replies[-1]['event_name'] != 'ChatEnded'
        or any(event['event_name'] != 'ChatResponse' for event in replies[:-1])
        or not tts or tts[-1]['event_name'] != 'TTSEnded'
        or sum(event['event_name'] == 'TTSEnded' for event in tts) != 1
        or any(event['message_type'] != 'SERVER_FULL_RESPONSE'
               or _correlations(event).get('frame.session_id') != confirmation['session_token']
               or not _same_correlation(event, confirmation, 'payload.question_id', 'payload.reply_id')
               for event in replies + tts)
    ):
        raise _causal_failure(path, 'v6 reconnect 缺少单条完整回复及 TTS 终止')
    boundaries = [event for event in tts if event['event_name'] == 'TTSSentenceEnd']
    audio = [event for event in tail if event.get('is_audio')]
    if not audio or not boundaries or max(e['ordinal'] for e in audio) >= boundaries[-1]['ordinal']:
        raise _causal_failure(path, 'v6 reconnect 音频缺少已播放的末尾句子边界')
    # Playback completion is independent of text/audio mapping. A provider may
    # omit start text or speak identical sentences; each boundary still owns
    # its own audio window and exact browser receipt.
    sentence_edges = [event for event in tts if event['event_name'] != 'TTSEnded']
    if len(sentence_edges) % 2:
        raise _causal_failure(path, 'v6 reconnect 句子播放边界不成对')
    covered_audio = set()
    for start, end in zip(sentence_edges[::2], sentence_edges[1::2]):
        if start['event_name'] != 'TTSSentenceStart' or end['event_name'] != 'TTSSentenceEnd':
            raise _causal_failure(path, 'v6 reconnect 句子播放边界顺序错误')
        window_audio = [event for event in audio
                        if start['ordinal'] < event['ordinal'] < end['ordinal']
                        and start['received_at_ms'] <= event['received_at_ms'] <= end['received_at_ms']
                        and event['event_name'] == 'TTSResponse' and event['payload_kind'] == 'binary'
                        and _correlations(event).get('frame.session_id') == confirmation['session_token']]
        if not window_audio:
            raise _causal_failure(path, 'v6 reconnect 句子边界内缺少同 Session 音频')
        covered_audio.update(event['ordinal'] for event in window_audio)
    if covered_audio != {event['ordinal'] for event in audio}:
        raise _causal_failure(path, 'v6 reconnect 存在未被播放边界覆盖的音频')
    watermark = max(replies[-1]['ordinal'], tts[-1]['ordinal'])
    proof_time = max(replies[-1]['received_at_ms'], tts[-1]['received_at_ms'])
    for boundary in boundaries:
        receipts = [action for action in _action_named(actions, 'client_sentence_played')
                    if action.get('sentence_boundary_ordinal') == boundary['ordinal']]
        if len(receipts) != 1 or not (
            receipts[0].get('success') is True
            and receipts[0].get('sentence_token') == _correlations(boundary).get('phase0.sentence_boundary')
            and receipts[0].get('provider_ordinal_after_ack', -1) >= boundary['ordinal']
            and boundary['received_at_ms'] <= receipts[0]['at_ms'] <= confirmation['at_ms']
        ):
            raise _causal_failure(path, 'v6 reconnect 缺少唯一真实句子播放 ACK')
        watermark = max(watermark, receipts[0]['provider_ordinal_after_ack'])
        proof_time = max(proof_time, receipts[0]['at_ms'])
    finishes = [event for event in tail if event['event_name'] == 'SessionFinished']
    if (
        confirmation['provider_ordinal_after_ack'] != watermark
        or len(finishes) > 1
        or any(event['message_type'] != 'SERVER_FULL_RESPONSE'
               or _correlations(event).get('frame.session_id') != confirmation['session_token']
               or event['ordinal'] <= watermark or event['received_at_ms'] < proof_time
               for event in finishes)
        or any(event['ordinal'] > watermark and event['event_name'] != 'SessionFinished' for event in tail)
    ):
        raise _causal_failure(path, 'v6 reconnect 播放截止点或正常结束边界不成立')


def _validate_evidence_record(
    value: Any,
    *,
    expected_source: str,
    allow_error: bool,
    path: str,
) -> dict:
    record = _require_exact_dict(value, _RECORD_FIELDS, path=path)
    _require_uuid(record["evidence_report_id"], path=f"{path}.evidence_report_id")
    _require_uuid(record["evidence_run_id"], path=f"{path}.evidence_run_id")
    if record["capability_key"] not in VOICE_CAPABILITY_KEYS:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_CAPABILITY_INVALID",
            f"{path}.capability_key",
            "capability_key 不在冻结六能力中",
        )
    result = record["verification_result"]
    allowed_results = _EVIDENCE_RESULTS if allow_error else _PHASE0_IMPORT_RESULTS
    if result not in allowed_results:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RESULT_INVALID",
            f"{path}.verification_result",
            "Phase0 error/unverified 仅是诊断，不可导入生产事实",
        )
    if record["source_type"] != expected_source:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SOURCE_INVALID",
            f"{path}.source_type",
            "source_type 与导入入口不匹配",
        )
    dimensions = evidence_dimensions(record)
    length_limits = {
        "provider_profile": 255,
        "model_version": 128,
        "protocol_profile": 128,
        "adapter_version": 128,
        "sdk_version": 128,
        "evidence_suite_version": 128,
    }
    for field, limit in length_limits.items():
        if len(dimensions[field]) > limit:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_DIMENSION_INVALID",
                f"{path}.{field}",
                f"{field} 超过存储上限",
            )
    expected_fingerprint = compute_evidence_fingerprint(dimensions)
    if record["evidence_fingerprint"] != expected_fingerprint:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_FINGERPRINT_INVALID",
            f"{path}.evidence_fingerprint",
            "evidence_fingerprint 与六维 canonical hash 不一致",
        )
    payload = _validate_evidence_payload(
        record["evidence_payload"],
        result=result,
        capability_key=record["capability_key"],
        expected_source=expected_source,
        path=f"{path}.evidence_payload",
    )
    is_m1 = payload['schema_version'] == _PHASE0_PROTOCOL_RECORD_SCHEMA
    m1_version_pairs = {
        ('b937a78-step004-evidence-v7', 'step004-o01-v7'),
        ('b937a78-step004-evidence-v8', 'step004-o01-v8'),
        ('b937a78-step004-evidence-v9', 'step004-o01-v9'),
    }
    version_pair = (dimensions['adapter_version'], dimensions['evidence_suite_version'])
    claims_m1_version = any(version_pair[0] == adapter or version_pair[1] == suite
                            for adapter, suite in m1_version_pairs)
    current_admin_protocol = (
        expected_source == 'admin_capability_test' and is_m1
        and version_pair == ('voice_adapter_v1', 'voice-admin-probe-v1')
        and record['capability_key'] == 'supports_context_truncate'
        and dimensions['provider_profile'] == 'doubao'
        and dimensions['protocol_profile'] == 'doubao_dialog_v3_pcm'
    )
    if (is_m1 or claims_m1_version) and not current_admin_protocol:
        if not (is_m1 and version_pair in m1_version_pairs
                and dimensions['model_version'] == '2.2.0.0'):
            raise _causal_failure(path, 'v7/v8 adapter/suite/v5 schema/SC2.0 必须配套')
    if result != "error":
        if is_m1 and record['capability_key'] == 'supports_context_truncate':
            _validate_m1_truncate(payload, result=result, path=f'{path}.evidence_payload')
        elif is_m1 and record['capability_key'] == 'supports_current_turn_rag_gate' and result == 'passed':
            raise _causal_failure(path, 'v7 单次 502 采用未证明生成等待门，不能声明 passed')
        else:
            _validate_capability_conclusion(
                capability_key=record["capability_key"], result=result,
                payload={**payload, 'schema_version':_PHASE0_CONTEXT_RECORD_SCHEMA} if is_m1 else payload,
                path=f"{path}.evidence_payload",
            )
        if is_m1 and record['capability_key'] == 'supports_session_reconnect' and (
            result == 'passed' or _action_named(payload['action_evidence'], 'provider_reconnect_context_confirmed')
        ):
            _validate_v6_reconnect_playback(payload, path=f'{path}.evidence_payload')
        if record['capability_key'] == 'supports_session_reconnect' and (
            dimensions['adapter_version'] == 'b937a78-step004-evidence-v6'
            or dimensions['evidence_suite_version'] == 'step004-o01-v6'
        ):
            if not (
                dimensions['adapter_version'] == 'b937a78-step004-evidence-v6'
                and dimensions['evidence_suite_version'] == 'step004-o01-v6'
                and payload['schema_version'] == _PHASE0_CONTEXT_RECORD_SCHEMA
            ):
                raise _causal_failure(path, 'v6 reconnect adapter/suite/schema 必须配套')
            if result == 'passed' or (
                payload['reason_code'] == 'same_session_reconnect_or_hidden_context_restore_failed'
                and _action_named(payload['action_evidence'], 'provider_reconnect_context_confirmed')
            ):
                _validate_v6_reconnect_playback(payload, path=f'{path}.evidence_payload')
    tested_at = _parse_evidence_datetime(record["tested_at"], path=f"{path}.tested_at")
    ttl_days = validate_evidence_ttl_days(record["evidence_ttl_days_snapshot"])
    if result == "passed":
        verified_at = _parse_evidence_datetime(
            record["verified_at"],
            path=f"{path}.verified_at",
        )
        expires_at = _parse_evidence_datetime(
            record["expires_at"],
            path=f"{path}.expires_at",
        )
        if verified_at != tested_at:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
                f"{path}.verified_at",
                "Phase0 verified_at 必须等于 tested_at",
            )
        if expires_at != verified_at + timedelta(days=ttl_days):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
                f"{path}.expires_at",
                "expires_at 必须由 verified_at + TTL 得出",
            )
        if expires_at <= datetime.now(timezone.utc):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_EXPIRED",
                f"{path}.expires_at",
                "passed 证据在导入/追加时已过期",
            )
    elif record["verified_at"] is not None or record["expires_at"] is not None:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_TIME_INVALID",
            f"{path}.verified_at",
            "failed/error 证据不得伪造 verified_at/expires_at",
        )
    report_hash = _require_sha256(
        record["report_sha256"],
        path=f"{path}.report_sha256",
    )
    without_hash = {
        key: record[key] for key in record if key != "report_sha256"
    }
    if report_hash != _canonical_sha256(without_hash, path=path):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_HASH_INVALID",
            f"{path}.report_sha256",
            "report_sha256 与 canonical record 不一致",
        )
    _reject_unsafe_values(record, path=path)
    return deepcopy(record)


def validate_phase0_evidence_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate one canonical, importable six-capability Phase0 run.

    The two production flags are shape-checked but never used as authority.
    Import readiness is derived from every other frozen assertion here.
    """

    value = _require_exact_dict(bundle, _BUNDLE_FIELDS, path="bundle")
    if value["schema_version"] != _PHASE0_BUNDLE_SCHEMA:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            "bundle.schema_version",
            "Phase0 bundle schema_version 非法",
        )
    run_id = _require_uuid(value["evidence_run_id"], path="bundle.evidence_run_id")
    if type(value["record_count"]) is not int or value["record_count"] != len(
        VOICE_CAPABILITY_KEYS
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_INCOMPLETE",
            "bundle.record_count",
            "Phase0 bundle 必须声明恰好六条记录",
        )
    if type(value["production_source_of_truth"]) is not bool:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID",
            "bundle.production_source_of_truth",
            "production_source_of_truth 必须是 bool，但不作为事实授权",
        )
    records_value = value["records"]
    if type(records_value) is not list or len(records_value) != len(
        VOICE_CAPABILITY_KEYS
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_INCOMPLETE",
            "bundle.records",
            "Phase0 bundle 必须包含六能力各一条",
        )
    records = [
        _validate_evidence_record(
            record,
            expected_source="phase0_import",
            allow_error=False,
            path=f"bundle.records[{index}]",
        )
        for index, record in enumerate(records_value)
    ]
    if any(record["evidence_run_id"] != run_id for record in records):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT",
            "bundle.records.evidence_run_id",
            "六条记录必须属于同一 evidence_run_id",
        )
    capability_keys = [record["capability_key"] for record in records]
    if set(capability_keys) != set(VOICE_CAPABILITY_KEYS) or len(
        capability_keys
    ) != len(set(capability_keys)):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_INCOMPLETE",
            "bundle.records.capability_key",
            "六能力必须各出现一次",
        )
    report_ids = [record["evidence_report_id"] for record in records]
    if len(report_ids) != len(set(report_ids)):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT",
            "bundle.records.evidence_report_id",
            "evidence_report_id 必须逐能力唯一",
        )
    first_dimensions = {
        field: records[0][field] for field in EVIDENCE_FINGERPRINT_FIELDS
    }
    first_ttl = records[0]["evidence_ttl_days_snapshot"]
    first_tested_at = records[0]["tested_at"]
    if any(
        {field: record[field] for field in EVIDENCE_FINGERPRINT_FIELDS}
        != first_dimensions
        or record["evidence_ttl_days_snapshot"] != first_ttl
        or record["tested_at"] != first_tested_at
        for record in records[1:]
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT",
            "bundle.records",
            "同一轮六条证据必须共用六维、TTL 与 tested_at",
        )
    bundle_hash = _require_sha256(
        value["bundle_sha256"],
        path="bundle.bundle_sha256",
    )
    without_hash = {key: value[key] for key in value if key != "bundle_sha256"}
    if bundle_hash != _canonical_sha256(without_hash, path="bundle"):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_HASH_INVALID",
            "bundle.bundle_sha256",
            "bundle_sha256 与 canonical bundle 不一致",
        )
    _reject_unsafe_values(value, path="bundle")
    return deepcopy(value)


def validate_phase0_evidence_selection(
    bundle: Mapping[str, Any], *, report_ids: Sequence[str]
) -> dict[str, Any]:
    """Validate an original envelope, then only the explicitly selected facts.

    This is not a new six-capability run. Diagnostics remain unverified and
    original identities/hashes survive selection without being reissued.
    """
    value = _require_exact_dict(bundle, _BUNDLE_FIELDS, path="bundle")
    run_id = _require_uuid(value["evidence_run_id"], path="bundle.evidence_run_id")
    if (value["schema_version"] != _PHASE0_BUNDLE_SCHEMA
        or type(value["record_count"]) is not int or value["record_count"] != 6
        or type(value["production_source_of_truth"]) is not bool
        or type(value["records"]) is not list or len(value["records"]) != 6):
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_SCHEMA_INVALID", "bundle", "必须输入完整原始六记录文件")
    bundle_hash = _require_sha256(value["bundle_sha256"], path="bundle.bundle_sha256")
    if bundle_hash != _canonical_sha256({k: v for k, v in value.items() if k != "bundle_sha256"}, path="bundle"):
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_HASH_INVALID", "bundle", "原始整包哈希不匹配")
    if not isinstance(report_ids, (list, tuple)) or not 1 <= len(report_ids) <= 6:
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_SELECTION_INVALID", "report_ids", "必须显式选择 1–6 条报告")
    ids = [_require_uuid(item, path="report_ids") for item in report_ids]
    if len(set(ids)) != len(ids):
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_SELECTION_INVALID", "report_ids", "报告选择重复")
    records = []
    for index, raw in enumerate(value["records"]):
        path = f"bundle.records[{index}]"
        record = _require_exact_dict(raw, _RECORD_FIELDS, path=path)
        _require_uuid(record["evidence_report_id"], path=f"{path}.evidence_report_id")
        if record["evidence_run_id"] != run_id or record["source_type"] != "phase0_import":
            raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT", path, "原始记录来源或运行身份不一致")
        if record["report_sha256"] != _canonical_sha256({k: v for k, v in record.items() if k != "report_sha256"}, path=path):
            raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_HASH_INVALID", path, "原始记录哈希不匹配")
        if record["verification_result"] not in _EVIDENCE_RESULTS:
            raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_RESULT_INVALID", path, "原始结果非法")
        records.append(record)
    if (len({r["evidence_report_id"] for r in records}) != 6
        or {r["capability_key"] for r in records} != set(VOICE_CAPABILITY_KEYS)):
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT", "bundle.records", "原始报告/能力标识重复或缺失")
    first = records[0]
    if any(evidence_dimensions(r) != evidence_dimensions(first)
           or r["tested_at"] != first["tested_at"]
           or r["evidence_ttl_days_snapshot"] != first["evidence_ttl_days_snapshot"] for r in records[1:]):
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_RUN_CONFLICT", "bundle.records", "原始运行六维/时间/TTL 不一致")
    if not set(ids) <= {r["evidence_report_id"] for r in records}:
        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_SELECTION_INVALID", "report_ids", "选中报告不在原文件中")
    selected, excluded = [], []
    for record in records:
        if record["evidence_report_id"] in ids:
            selected.append(_validate_evidence_record(record, expected_source="phase0_import", allow_error=True, path="record"))
        else:
            excluded.append({**{k: record[k] for k in ("evidence_report_id", "capability_key", "verification_result", "report_sha256")}, "reason": "not_selected"})
    _reject_unsafe_values(value, path="bundle")
    return {"evidence_run_id": run_id, "bundle_sha256": bundle_hash,
            "record_count": len(selected), "records": selected, "excluded_records": excluded}


def _parse_datetime(value: Any) -> datetime | None:
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


def _disabled_runtime_projection(
    capability: Mapping[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    projected = deepcopy(dict(capability))
    projected["verification_status"] = status
    projected["enabled"] = False
    projected["forced_enabled"] = False
    projected["effective_scope"] = "off"
    return projected


def resolve_runtime_capability(
    capability: Mapping[str, Any],
    *,
    current_dimensions: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve one capability without upgrading evidence or mutating its input.

    This read-only resolver never changes a non-verified state into ``verified``
    and never expands scope.  A previously verified projection becomes stale
    when any fingerprint dimension changes, its TTL is invalid, its stored
    expiry is inconsistent, or the expiry instant has been reached.
    """

    if not isinstance(capability, Mapping):
        raise CapabilityStateError(
            "VOICE_CAPABILITY_STATE_INVALID",
            "capability",
            "capability 必须是对象",
        )
    status = capability.get("verification_status")
    if not isinstance(status, str) or status not in _CAPABILITY_STATUSES:
        raise CapabilityStateError(
            "VOICE_CAPABILITY_STATUS_INVALID",
            "verification_status",
            "verification_status 非法",
        )
    if status in _NON_VERIFIED_STATUSES:
        return _disabled_runtime_projection(capability, status=status)

    stale = False
    try:
        current_fingerprint = compute_evidence_fingerprint(current_dimensions)
        projected_fingerprint = compute_evidence_fingerprint(capability)
        ttl_days = validate_evidence_ttl_days(capability.get("evidence_ttl_days"))
    except CapabilityStateError:
        stale = True
        current_fingerprint = None
        projected_fingerprint = None
        ttl_days = None

    saved_fingerprint = capability.get("evidence_fingerprint")
    if (
        current_fingerprint is None
        or projected_fingerprint is None
        or not isinstance(saved_fingerprint, str)
        or saved_fingerprint.casefold() != current_fingerprint
        or saved_fingerprint.casefold() != projected_fingerprint
    ):
        stale = True
    if (
        not isinstance(capability.get("evidence_report_id"), str)
        or not capability["evidence_report_id"].strip()
    ):
        stale = True

    verified_at = _parse_datetime(capability.get("verified_at"))
    stored_expires_at = _parse_datetime(capability.get("expires_at"))
    if verified_at is None or stored_expires_at is None or ttl_days is None:
        stale = True
    else:
        expected_expires_at = evidence_expires_at(verified_at, ttl_days)
        if _utc_naive(expected_expires_at) != _utc_naive(stored_expires_at):
            stale = True
        reference_now = now or datetime.now(timezone.utc)
        if _utc_naive(reference_now) >= _utc_naive(stored_expires_at):
            stale = True

    enabled = capability.get("enabled")
    forced_enabled = capability.get("forced_enabled")
    effective_scope = capability.get("effective_scope")
    if (
        type(enabled) is not bool
        or type(forced_enabled) is not bool
        or not isinstance(effective_scope, str)
        or effective_scope not in ("off", "test", "all")
    ):
        stale = True

    if stale:
        return _disabled_runtime_projection(capability, status="stale")

    # A matching pre-existing verified projection may be consumed, but this
    # slice never creates or upgrades one.  Disabled verified configurations
    # remain off rather than carrying a contradictory effective scope.
    projected = deepcopy(dict(capability))
    if enabled is not True:
        projected["enabled"] = False
        projected["effective_scope"] = "off"
    return projected


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return deepcopy(value)


def project_capability_evidence(
    evidence: VoiceCapabilityEvidence,
    role: str,
) -> dict[str, Any]:
    """Apply the frozen five-role evidence projection to one stored row."""

    if role not in CAPABILITY_EVIDENCE_READ_ROLES:
        raise CapabilityEvidenceAccessError("当前角色无能力证据读取权限")
    projected = {
        field: _json_value(getattr(evidence, field))
        for field in _EVIDENCE_PUBLIC_FIELDS
    }
    if role in CAPABILITY_EVIDENCE_PAYLOAD_ROLES:
        projected["evidence_payload"] = deepcopy(evidence.evidence_payload)
        projected["operator_id"] = evidence.operator_id
    return projected


def _record_without_hash(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in record.items() if key != "report_sha256"}


def _stored_record_projection(row: VoiceCapabilityEvidence) -> dict[str, Any]:
    return {
        "evidence_report_id": row.evidence_report_id,
        "evidence_run_id": row.evidence_run_id,
        "capability_key": row.capability_key,
        "verification_result": row.verification_result,
        "source_type": row.source_type,
        **{
            field: getattr(row, field) for field in EVIDENCE_FINGERPRINT_FIELDS
        },
        "evidence_fingerprint": row.evidence_fingerprint,
        "evidence_payload": deepcopy(row.evidence_payload),
        "tested_at": _iso_utc(row.tested_at),
        "verified_at": _iso_utc(row.verified_at),
        "evidence_ttl_days_snapshot": row.evidence_ttl_days_snapshot,
        "expires_at": _iso_utc(row.expires_at),
        "report_sha256": row.report_sha256,
    }


def _new_evidence_row(
    record: Mapping[str, Any],
    *,
    operator_id: int,
) -> VoiceCapabilityEvidence:
    return VoiceCapabilityEvidence(
        evidence_report_id=record["evidence_report_id"],
        evidence_run_id=record["evidence_run_id"],
        capability_key=record["capability_key"],
        verification_result=record["verification_result"],
        source_type=record["source_type"],
        **{
            field: record[field] for field in EVIDENCE_FINGERPRINT_FIELDS
        },
        evidence_fingerprint=record["evidence_fingerprint"],
        evidence_payload=deepcopy(record["evidence_payload"]),
        report_sha256=record["report_sha256"],
        tested_at=_utc_naive(
            _parse_evidence_datetime(record["tested_at"], path="record.tested_at")
        ),
        verified_at=(
            _utc_naive(
                _parse_evidence_datetime(
                    record["verified_at"],
                    path="record.verified_at",
                )
            )
            if record["verified_at"] is not None
            else None
        ),
        evidence_ttl_days_snapshot=record["evidence_ttl_days_snapshot"],
        expires_at=(
            _utc_naive(
                _parse_evidence_datetime(
                    record["expires_at"],
                    path="record.expires_at",
                )
            )
            if record["expires_at"] is not None
            else None
        ),
        operator_id=operator_id,
    )


def _project_record_to_capability(
    capability: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    projected = deepcopy(dict(capability))
    result = record["verification_result"]
    projected.update(
        {
            "verification_status": _RESULT_STATUS[result],
            "enabled": False,
            "forced_enabled": False,
            "effective_scope": "off",
            **{
                field: record[field] for field in EVIDENCE_FINGERPRINT_FIELDS
            },
            "evidence_fingerprint": record["evidence_fingerprint"],
            "evidence_ttl_days": record["evidence_ttl_days_snapshot"],
            "verified_at": record["verified_at"],
            "expires_at": record["expires_at"],
            "evidence_report_id": record["evidence_report_id"],
            "last_test_result": result,
        }
    )
    return projected


async def _verified_operator(
    db: AsyncSession,
    *,
    operator_id: int,
) -> AdminUser:
    if type(operator_id) is not int or operator_id < 1:
        raise CapabilityEvidenceAccessError("能力证据写入操作者不存在或无权限")
    operator = (
        await db.execute(
            select(AdminUser)
            .where(AdminUser.id == operator_id)
            .with_for_update()
        )
    ).scalars().first()
    if (
        operator is None
        or operator.role not in _EVIDENCE_WRITE_ROLES
        or not operator.is_active
        or operator.is_locked
    ):
        raise CapabilityEvidenceAccessError("能力证据写入仅限 super_admin/tech_ops")
    return operator


async def _lock_phase0_import_anchor(db: AsyncSession) -> None:
    """Serialize Phase0 absence checks on rows shared by every operator."""

    configs = (
        await db.execute(
            select(AdminConfig)
            .where(AdminConfig.config_key == VOICE_CALL_CONFIG_KEY)
            .order_by(AdminConfig.id.asc())
            .with_for_update()
        )
    ).scalars().all()
    if not configs:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_DRAFT_UNAVAILABLE",
            "voice_call_config",
            "不存在可串行化能力证据导入的 active/draft 配置",
        )


async def _locked_draft_config(
    db: AsyncSession,
    *,
    operator: AdminUser,
) -> tuple[AdminConfig, dict[str, Any]]:
    draft = (
        await db.execute(
            select(AdminConfig)
            .where(
                AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                AdminConfig.is_draft == True,  # noqa: E712
                AdminConfig.is_active == False,  # noqa: E712
            )
            .with_for_update()
        )
    ).scalars().first()
    if draft is None:
        active = (
            await db.execute(
                select(AdminConfig)
                .where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_draft == False,  # noqa: E712
                    AdminConfig.is_active == True,  # noqa: E712
                )
                .with_for_update()
            )
        ).scalars().first()
        if active is None or not isinstance(active.config_value, str):
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_DRAFT_UNAVAILABLE",
                "voice_call_config",
                "不存在可投影能力证据的 active/draft 配置",
            )
        try:
            config = json.loads(active.config_value)
        except (TypeError, ValueError) as exc:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_DRAFT_INVALID",
                "voice_call_config",
                "active 语音配置不是合法 JSON",
            ) from exc
        draft = AdminConfig(
            config_key=VOICE_CALL_CONFIG_KEY,
            config_value=_canonical_json(config),
            version=0,
            draft_revision=0,
            is_active=False,
            is_draft=True,
            updated_by=operator.username,
            updated_at=datetime.utcnow(),
        )
        db.add(draft)
        await db.flush()
    elif not isinstance(draft.config_value, str):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_DRAFT_INVALID",
            "voice_call_config",
            "语音配置草稿为空",
        )
    try:
        config = json.loads(draft.config_value)
    except (TypeError, ValueError) as exc:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_DRAFT_INVALID",
            "voice_call_config",
            "语音配置草稿不是合法 JSON",
        ) from exc
    capabilities = config.get("capabilities") if isinstance(config, dict) else None
    if (
        type(capabilities) is not dict
        or set(capabilities) != set(VOICE_CAPABILITY_KEYS)
        or not all(type(item) is dict for item in capabilities.values())
    ):
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_DRAFT_INVALID",
            "voice_call_config.capabilities",
            "语音配置草稿缺少冻结六能力结构",
        )
    return draft, config


def _advance_draft(
    draft: AdminConfig,
    config: Mapping[str, Any],
    *,
    operator: AdminUser,
) -> int:
    current_revision = draft.draft_revision
    if current_revision is None:
        current_revision = 0
    if type(current_revision) is not int or current_revision < 0:
        raise _evidence_error(
            "VOICE_CAPABILITY_EVIDENCE_DRAFT_INVALID",
            "voice_call_config.draft_revision",
            "语音配置草稿 revision 非法",
        )
    next_revision = current_revision + 1
    draft.config_value = _canonical_json(config)
    draft.draft_revision = next_revision
    draft.updated_by = operator.username
    draft.updated_at = datetime.utcnow()
    return next_revision


def _evidence_audit(
    *,
    operator: AdminUser,
    action: str,
    source_type: str,
    records: Sequence[Mapping[str, Any]],
    draft_revision: int,
    bundle_sha256: str | None = None,
) -> AdminOperationLog:
    summary = {
        "source_type": source_type,
        "evidence_run_id": records[0]["evidence_run_id"],
        "record_count": len(records),
        "capability_results": {
            record["capability_key"]: record["verification_result"]
            for record in sorted(records, key=lambda item: item["capability_key"])
        },
        "report_sha256": {
            record["capability_key"]: record["report_sha256"]
            for record in sorted(records, key=lambda item: item["capability_key"])
        },
        "bundle_sha256": bundle_sha256,
        "draft_revision": draft_revision,
    }
    return AdminOperationLog(
        admin_user_id=operator.id,
        admin_username=operator.username,
        module="voice_config",
        action=action,
        target_description="追加实时语音能力证据并更新草稿只读投影",
        before_value=None,
        after_value=_canonical_json(summary),
        ip_address=None,
    )


async def _existing_phase0_rows(
    db: AsyncSession,
    records: Sequence[Mapping[str, Any]],
) -> list[VoiceCapabilityEvidence]:
    run_id = records[0]["evidence_run_id"]
    report_ids = [record["evidence_report_id"] for record in records]
    return (
        await db.execute(
            select(VoiceCapabilityEvidence)
            .where(
                or_(
                    VoiceCapabilityEvidence.evidence_run_id == run_id,
                    VoiceCapabilityEvidence.evidence_report_id.in_(report_ids),
                )
            )
            .with_for_update()
        )
    ).scalars().all()


async def _existing_phase0_bundle_hashes(
    db: AsyncSession,
    *,
    evidence_run_id: str,
) -> list[str]:
    rows = (
        await db.execute(
            select(AdminOperationLog)
            .where(
                AdminOperationLog.module == "voice_config",
                AdminOperationLog.action == "import_evidence",
            )
            .order_by(AdminOperationLog.id.asc())
            .with_for_update()
        )
    ).scalars().all()
    hashes: list[str] = []
    for row in rows:
        try:
            summary = json.loads(row.after_value)
        except (TypeError, ValueError):
            continue
        if (
            type(summary) is dict
            and summary.get("evidence_run_id") == evidence_run_id
            and isinstance(summary.get("bundle_sha256"), str)
        ):
            hashes.append(summary["bundle_sha256"])
    return hashes


def _phase0_rows_are_identical(
    existing: Sequence[VoiceCapabilityEvidence],
    records: Sequence[Mapping[str, Any]],
) -> bool:
    if len(existing) != len(records):
        return False
    expected = {
        record["capability_key"]: deepcopy(dict(record)) for record in records
    }
    actual = {
        row.capability_key: _stored_record_projection(row) for row in existing
    }
    return actual == expected


async def _existing_admin_row(
    db: AsyncSession,
    record: Mapping[str, Any],
) -> list[VoiceCapabilityEvidence]:
    return (
        await db.execute(
            select(VoiceCapabilityEvidence)
            .where(
                or_(
                    VoiceCapabilityEvidence.evidence_report_id
                    == record["evidence_report_id"],
                    (
                        VoiceCapabilityEvidence.evidence_run_id
                        == record["evidence_run_id"]
                    )
                    & (
                        VoiceCapabilityEvidence.capability_key
                        == record["capability_key"]
                    ),
                )
            )
            .with_for_update()
        )
    ).scalars().all()


class RealtimeVoiceCapabilityService:
    """Capability evidence read access plus tightly scoped internal writers."""

    async def get_evidence(
        self,
        db: AsyncSession,
        *,
        evidence_report_id: str,
        role: str,
    ) -> dict[str, Any] | None:
        if role not in CAPABILITY_EVIDENCE_READ_ROLES:
            raise CapabilityEvidenceAccessError("当前角色无能力证据读取权限")
        row = (
            await db.execute(
                select(VoiceCapabilityEvidence).where(
                    VoiceCapabilityEvidence.evidence_report_id
                    == evidence_report_id
                )
            )
        ).scalars().first()
        if row is None:
            return None
        return project_capability_evidence(row, role)

    async def import_phase0_evidence_bundle(
        self,
        db: AsyncSession,
        *,
        bundle: Mapping[str, Any],
        operator_id: int,
    ) -> dict[str, Any]:
        """Atomically import one canonical six-record Phase0 bundle.

        A complete byte-equivalent stable projection is idempotent.  Any
        partial run, reused identifier or changed record is a conflict; it is
        never repaired by overwriting an immutable evidence row.
        """

        validated = validate_phase0_evidence_bundle(bundle)
        records = validated["records"]
        result: dict[str, Any]
        transaction = db.begin_nested() if db.in_transaction() else db.begin()
        try:
            async with transaction:
                await _lock_phase0_import_anchor(db)
                operator = await _verified_operator(db, operator_id=operator_id)
                existing = await _existing_phase0_rows(db, records)
                if existing:
                    bundle_hashes = await _existing_phase0_bundle_hashes(
                        db,
                        evidence_run_id=validated["evidence_run_id"],
                    )
                    if (
                        not _phase0_rows_are_identical(existing, records)
                        or bundle_hashes != [validated["bundle_sha256"]]
                    ):
                        raise _evidence_error(
                            "VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT",
                            "bundle",
                            "同 run/report 标识已存在不同、不完整或非 exact bundle 证据",
                        )
                    result = {
                        "evidence_run_id": validated["evidence_run_id"],
                        "record_count": len(records),
                        "bundle_sha256": validated["bundle_sha256"],
                        "idempotent": True,
                    }
                else:
                    db.add_all(
                        [
                            _new_evidence_row(record, operator_id=operator.id)
                            for record in records
                        ]
                    )
                    # Force all six immutable rows to be accepted before touching
                    # the draft projection, so every subsequent failure rolls the
                    # same database transaction back to the original multiset.
                    await db.flush()

                    draft, config = await _locked_draft_config(db, operator=operator)
                    for record in records:
                        capability_key = record["capability_key"]
                        config["capabilities"][capability_key] = (
                            _project_record_to_capability(
                                config["capabilities"][capability_key],
                                record,
                            )
                        )
                    draft_revision = _advance_draft(draft, config, operator=operator)
                    await db.flush()

                    db.add(
                        _evidence_audit(
                            operator=operator,
                            action="import_evidence",
                            source_type="phase0_import",
                            records=records,
                            draft_revision=draft_revision,
                            bundle_sha256=validated["bundle_sha256"],
                        )
                    )
                    await db.flush()
                    result = {
                        "evidence_run_id": validated["evidence_run_id"],
                        "record_count": len(records),
                        "bundle_sha256": validated["bundle_sha256"],
                        "draft_revision": draft_revision,
                        "idempotent": False,
                    }
        except IntegrityError:
            raise _evidence_error(
                "VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT",
                "bundle",
                "同 run/report 标识发生并发冲突",
            ) from None
        return result

    async def import_phase0_evidence_selection(
        self, db: AsyncSession, *, bundle: Mapping[str, Any],
        report_ids: Sequence[str], operator_id: int,
    ) -> dict[str, Any]:
        """Append selected immutable facts atomically; never enable them."""
        selected = validate_phase0_evidence_selection(bundle, report_ids=report_ids)
        records = selected["records"]
        transaction = db.begin_nested() if db.in_transaction() else db.begin()
        try:
            async with transaction:
                await _lock_phase0_import_anchor(db)
                operator = await _verified_operator(db, operator_id=operator_id)
                # All selections from a run must retain the same original file.
                audit_rows = (await db.execute(select(AdminOperationLog).where(
                    AdminOperationLog.module == "voice_config",
                    AdminOperationLog.action.in_(["import_evidence", "import_selection"]),
                ))).scalars().all()
                for audit_row in audit_rows:
                    try:
                        audit = json.loads(audit_row.after_value)
                    except (TypeError, ValueError):
                        continue
                    if (isinstance(audit, dict) and audit.get("evidence_run_id") == selected["evidence_run_id"]
                        and audit.get("bundle_sha256") != selected["bundle_sha256"]):
                        raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT", "bundle", "同 run 原始文件哈希已变化")
                pending = []
                for record in records:
                    existing = await _existing_admin_row(db, record)
                    if existing:
                        if len(existing) != 1 or _stored_record_projection(existing[0]) != record:
                            raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT", "record", "原报告或 run/能力身份冲突")
                    else:
                        pending.append(record)
                result = {"evidence_run_id": selected["evidence_run_id"],
                          "bundle_sha256": selected["bundle_sha256"],
                          "record_count": len(records), "inserted_count": len(pending),
                          "idempotent": not pending}
                if pending:
                    inserted_rows = [_new_evidence_row(r, operator_id=operator.id) for r in pending]
                    db.add_all(inserted_rows)
                    await db.flush()
                    for row, original in zip(inserted_rows, pending):
                        await db.refresh(row)
                        if _stored_record_projection(row) != original:
                            raise _evidence_error(
                                "VOICE_CAPABILITY_EVIDENCE_STORAGE_MISMATCH",
                                "record", "数据库回读与原报告不一致，整次导入已拒绝",
                            )
                    draft, config = await _locked_draft_config(db, operator=operator)
                    for record in pending:
                        key = record["capability_key"]
                        config["capabilities"][key] = _project_record_to_capability(config["capabilities"][key], record)
                    revision = _advance_draft(draft, config, operator=operator)
                    await db.flush()
                    audit_row = _evidence_audit(operator=operator, action="import_selection",
                        source_type="phase0_import", records=records, draft_revision=revision,
                        bundle_sha256=selected["bundle_sha256"])
                    audit = json.loads(audit_row.after_value)
                    audit.update(excluded_records=selected["excluded_records"],
                                 selected_report_ids=sorted(report_ids),
                                 inserted_report_ids=sorted(r["evidence_report_id"] for r in pending),
                                 acceptance_scope="m1_restricted", enables_capabilities=False)
                    audit_row.after_value = _canonical_json(audit)
                    db.add(audit_row)
                    await db.flush()
                    result["draft_revision"] = revision
        except IntegrityError:
            raise _evidence_error("VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT", "record", "报告并发唯一键冲突") from None
        return result

    async def append_admin_capability_evidence(
        self,
        db: AsyncSession,
        *,
        record: Mapping[str, Any],
        operator_id: int,
    ) -> dict[str, Any]:
        """Append one real admin test result and project only its capability."""

        validated = _validate_evidence_record(
            record,
            expected_source="admin_capability_test",
            allow_error=True,
            path="record",
        )
        result: dict[str, Any]
        transaction = db.begin_nested() if db.in_transaction() else db.begin()
        async with transaction:
            operator = await _verified_operator(db, operator_id=operator_id)
            existing = await _existing_admin_row(db, validated)
            if existing:
                if len(existing) != 1 or _stored_record_projection(existing[0]) != validated:
                    raise _evidence_error(
                        "VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT",
                        "record",
                        "admin evidence 标识已存在不同证据",
                    )
                result = {
                    "evidence_run_id": validated["evidence_run_id"],
                    "evidence_report_id": validated["evidence_report_id"],
                    "capability_key": validated["capability_key"],
                    "idempotent": True,
                }
            else:
                db.add(_new_evidence_row(validated, operator_id=operator.id))
                await db.flush()

                draft, config = await _locked_draft_config(db, operator=operator)
                capability_key = validated["capability_key"]
                config["capabilities"][capability_key] = (
                    _project_record_to_capability(
                        config["capabilities"][capability_key],
                        validated,
                    )
                )
                draft_revision = _advance_draft(draft, config, operator=operator)
                await db.flush()

                db.add(
                    _evidence_audit(
                        operator=operator,
                        action="append_evidence",
                        source_type="admin_capability_test",
                        records=[validated],
                        draft_revision=draft_revision,
                    )
                )
                await db.flush()
                result = {
                    "evidence_run_id": validated["evidence_run_id"],
                    "evidence_report_id": validated["evidence_report_id"],
                    "capability_key": capability_key,
                    "draft_revision": draft_revision,
                    "idempotent": False,
                }
        return result


class FixtureEvidenceTransactionPort(Protocol):
    """Test-only transaction port; STEP-006A provides no production adapter."""

    async def begin(self) -> None: ...

    async def stage_fixture_evidence(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> None: ...

    async def stage_fixture_projection(
        self,
        projection: Mapping[str, Any],
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


async def run_fixture_evidence_transaction(
    port: FixtureEvidenceTransactionPort,
    *,
    rows: Sequence[Mapping[str, Any]],
    projection: Mapping[str, Any],
) -> None:
    """Exercise all-or-nothing orchestration using only an injected fixture port."""

    await port.begin()
    try:
        await port.stage_fixture_evidence(deepcopy(list(rows)))
        await port.stage_fixture_projection(deepcopy(dict(projection)))
        await port.commit()
    except BaseException:
        await port.rollback()
        raise


realtime_voice_capability_service = RealtimeVoiceCapabilityService()


async def append_admin_capability_evidence(
    db: AsyncSession,
    *,
    record: Mapping[str, Any],
    operator_id: int,
) -> dict[str, Any]:
    """Internal API-runner adapter for one real admin capability result."""

    return await realtime_voice_capability_service.append_admin_capability_evidence(
        db,
        record=record,
        operator_id=operator_id,
    )


__all__ = [
    "CAPABILITY_EVIDENCE_NOT_FOUND",
    "CAPABILITY_EVIDENCE_PAYLOAD_ROLES",
    "CAPABILITY_EVIDENCE_READ_ROLES",
    "EVIDENCE_FINGERPRINT_FIELDS",
    "CapabilityEvidenceAccessError",
    "CapabilityStateError",
    "FixtureEvidenceTransactionPort",
    "RealtimeVoiceCapabilityService",
    "append_admin_capability_evidence",
    "compute_evidence_fingerprint",
    "evidence_dimensions",
    "evidence_expires_at",
    "project_capability_evidence",
    "realtime_voice_capability_service",
    "resolve_runtime_capability",
    "run_fixture_evidence_transaction",
    "validate_phase0_evidence_bundle",
    "validate_evidence_ttl_days",
]
