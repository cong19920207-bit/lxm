# -*- coding: utf-8 -*-
"""M1 campaign-only real Provider runner harness.

This module is never imported by the production application.  The CLI installs
one temporary FastAPI dependency override for ``get_voice_test_runner`` and
keeps production authentication, database dependencies and the fail-closed
``UnavailableVoiceTestRunner`` default unchanged.

No Provider call happens on import or during unit tests.  A real campaign must
be started explicitly from an isolated ``lxm_step006_*`` MySQL environment.
"""

from __future__ import annotations

import asyncio
import argparse
import ast
import fcntl
import hashlib
import io
import inspect
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from dotenv import dotenv_values


# ``python scripts/...py`` otherwise exposes only ``scripts/`` on sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


ACK_CAPABILITY_KEY = "supports_sentence_playback_ack"
PHASE0_PROVIDER_PROFILE = "doubao-s2s-strong-character"
PHASE0_PROTOCOL_PROFILE = "dialogue-v3-binary-gzip-json-pcm16"
PHASE0_ADAPTER_VERSION = "b937a78-step004-evidence-v5"
CAMPAIGN_NETWORK_PROFILE = "admin_test"
DEFAULT_USER_WINDOW_SECONDS = 45.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_PHASE0_PORT = 18765
DEFAULT_PHASE0_STARTUP_SECONDS = 10.0
CAMPAIGN_DATABASE_NAME = "lxm_step006_m1_campaign_20260902"
CAMPAIGN_REDIS_DB = "15"
PHASE0_EVIDENCE_SUITE_VERSION = "step004-o01-v5"
CAMPAIGN_ALEMBIC_REVISION = "v8c_voice_schema_001"
CAMPAIGN_ROUTE_DEADLINE_SECONDS = 70.0
CAMPAIGN_CREDENTIAL_REF = "PHASE0_DOUBAO_S2S_ACCESS_KEY"
CAMPAIGN_ATTEMPT_LIMIT = 15
AUTHORIZED_FOURTH_ROUND_LIMIT = 16
AUTHORIZED_FIFTH_ROUND_LIMIT = 18
AUTHORIZED_TEN_MINUTE_LIMIT = 16
TEN_MINUTE_AMENDMENT_SCOPE = "s06_ten_minute_only"
BASELINE_BATCHES = {
    1: "initial", 2: "final", 3: "authorized_retest",
    4: "authorized_retest", 5: "authorized_retest", 6: "duration_amendment",
}
PHASE0_RELATIVE_ROOT = Path("tmp/phase0-step004-s01-fix-20260906")
M1_PROTOCOL_ROOT = Path("tmp/phase0-step004-m1-acceptance-20260907")
M1_PROTOCOL_PROFILE = False
M1_RECOVERY_PROFILE = False
M1_CANCEL_ONLY_PROFILE = False
M1_CANCEL_RETRY_PROFILE = False
_M1_PROTOCOL_AUTHORIZATION: tuple[str, str, str] | None = None
ATTEMPT_LEDGER_SCHEMA = "m1-campaign-provider-attempt-ledger/v2"
ATTEMPT_RECEIPT_SCHEMA = "m1-campaign-provider-attempt-receipt/v1"
FINAL_BATCH_RECEIPT_SCHEMA = "m1-campaign-final-batch-receipt/v1"
CAMPAIGN_BASELINE_SCHEMA = "m1-campaign-baseline/v1"
RUNTIME_MANIFEST_SCHEMA = "m1-campaign-runtime-manifest/v2"
WORKER_CLIENT_CLOSE_SECONDS = 1.0
WORKER_TERMINATE_WAIT_SECONDS = 1.5
WORKER_KILL_WAIT_SECONDS = 1.0
CAMPAIGNS_RELATIVE_ROOT = Path(
    "docs/design/realtime_voice/P1/execution/evidence/step004/"
    "campaigns"
)
CAMPAIGN_ATTEMPT_KINDS = frozenset(
    {
        "admin_connection",
        "admin_ack",
        "s01_start_session",
        "s01_reconnect",
        "s02_start_session",
        "s03_start_session",
        "s04_start_session",
        "s05_start_session",
        "s06_start_session",
    }
)
DIRECT_PHASE0_ATTEMPT_KINDS = CAMPAIGN_ATTEMPT_KINDS - {
    "admin_connection",
    "admin_ack",
}
CAMPAIGN_RUNTIME_EXACT_PATHS = (
    "scripts/realtime_voice_m1_campaign_runner.py",
    "admin/pages/voice-config.html",
    "admin/static/js/voice-config-admin.js",
    str(PHASE0_RELATIVE_ROOT / "frontend/pages/phase0_realtime_voice.html"),
    str(PHASE0_RELATIVE_ROOT / "requirements.txt"),
)
CAMPAIGN_RUNTIME_PACKAGE_NAMES = (
    "asyncmy",
    "bcrypt",
    "fastapi",
    "httpx",
    "PyJWT",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "redis",
    "SQLAlchemy",
    "starlette",
    "uvicorn",
    "websockets",
)
CAMPAIGN_REQUIRED_TABLES = frozenset(
    {
        "admin_config",
        "admin_operation_logs",
        "admin_users",
        "voice_capability_evidence",
    }
)

_PHASE0_PUBLIC_SETTING_SOURCES = {
    "endpoint": ("PHASE0_DOUBAO_S2S_ENDPOINT", "DEFAULT_S2S_ENDPOINT"),
    "resource_id": ("PHASE0_DOUBAO_S2S_RESOURCE_ID", "DEFAULT_RESOURCE_ID"),
    "model_version": ("PHASE0_DOUBAO_S2S_MODEL", "DEFAULT_S2S_MODEL"),
    "voice_id": ("PHASE0_DOUBAO_S2S_SPEAKER", "DEFAULT_S2S_SPEAKER"),
}

_BUSINESS_ENV_KEYS = (
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "REDIS_DB",
)

_RECORD_FIELDS = frozenset(
    {
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


class CampaignWorkerPort(Protocol):
    async def start(self) -> None: ...

    async def create_connection_session(self, *, user_id: int) -> Mapping[str, Any]: ...

    async def get_session(self, session_id: str) -> Mapping[str, Any]: ...

    async def fetch_evidence(self, session_id: str) -> Mapping[str, Any]: ...

    async def end_session(self, session_id: str) -> None: ...

    async def stop(self) -> None: ...


class ConsumedEvidenceRegistry:
    """Process-local replay fence shared by every campaign dependency instance."""

    def __init__(self) -> None:
        self._runs: set[str] = set()
        self._reports: set[str] = set()

    def contains(self, run_id: str, report_id: str) -> bool:
        return run_id in self._runs or report_id in self._reports

    def consume(self, run_id: str, report_id: str) -> None:
        if self.contains(run_id, report_id):
            raise ValueError("campaign evidence UUID 已消费")
        self._runs.add(run_id)
        self._reports.add(report_id)


def _dotenv_allowlisted(path: Path, allowed_keys: set[str]) -> dict[str, str | None]:
    """Parse only explicitly named .env assignments; discard credential lines otherwise."""

    selected: list[str] = []
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            for raw_line in stream:
                candidate = raw_line.lstrip()
                if candidate.startswith("export "):
                    candidate = candidate[7:].lstrip()
                key = candidate.split("=", 1)[0].strip() if "=" in candidate else ""
                if key in allowed_keys:
                    selected.append(candidate)
    except (OSError, UnicodeError):
        raise ValueError("项目 .env 不可读") from None
    return dict(dotenv_values(stream=io.StringIO("".join(selected))))


def load_phase0_public_provider_settings(
    *,
    project_env_path: Path,
    phase0_root: Path,
) -> dict[str, str]:
    """Read four public settings without importing Phase0 or returning secrets."""

    source_path = (
        Path(phase0_root).resolve()
        / "backend"
        / "phase0_realtime_voice"
        / "s2s_client.py"
    )
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError):
        raise ValueError("Phase0 v3 Provider 配置源不可读") from None
    wanted_defaults = {
        default_name
        for _env_name, default_name in _PHASE0_PUBLIC_SETTING_SOURCES.values()
    }
    defaults: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in wanted_defaults
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            defaults[node.targets[0].id] = node.value.value.strip()
    if set(defaults) != wanted_defaults:
        raise ValueError("Phase0 v3 Provider 默认值不完整")

    values = _dotenv_allowlisted(
        Path(project_env_path).resolve(),
        {env_name for env_name, _default in _PHASE0_PUBLIC_SETTING_SOURCES.values()},
    )
    settings: dict[str, str] = {}
    for field, (env_name, default_name) in _PHASE0_PUBLIC_SETTING_SOURCES.items():
        env_value = values.get(env_name)
        value = str(env_value).strip() if env_value is not None else defaults[default_name]
        if not value:
            raise ValueError(f"Phase0 公共配置 {field} 为空")
        settings[field] = value
    if not settings["endpoint"].startswith("wss://"):
        raise ValueError("Phase0 endpoint 必须为 wss")
    return settings


def _assert_draft_public_settings(
    draft_snapshot: Mapping[str, Any],
    settings: Mapping[str, str],
) -> None:
    s2s = draft_snapshot.get("s2s")
    voice = draft_snapshot.get("voice")
    if not isinstance(s2s, Mapping) or not isinstance(voice, Mapping):
        raise ValueError("draft 缺少 s2s/voice")
    actual = {
        "endpoint": s2s.get("endpoint"),
        "resource_id": s2s.get("resource_id"),
        "model_version": s2s.get("model_version"),
        "voice_id": voice.get("voice_id"),
    }
    if actual != dict(settings):
        raise ValueError("draft 与 project-env/Phase0 v3 公共配置不一致")


def build_phase0_child_environment(
    *,
    project_env_path: Path,
    phase0_root: Path,
    draft_snapshot: Mapping[str, Any],
    secret: str,
    parent_environ: Mapping[str, str] | None = None,
    campaign_attempt: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Build a strict child env without inheriting the campaign DB/Redis."""

    validate_phase0_draft(draft_snapshot)
    root_values = _dotenv_allowlisted(
        project_env_path,
        set(_BUSINESS_ENV_KEYS) | {"PHASE0_DOUBAO_S2S_APP_ID"},
    )
    parent = parent_environ if parent_environ is not None else os.environ
    child: dict[str, str] = {}
    for key in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"):
        value = parent.get(key)
        if isinstance(value, str) and value:
            child[key] = value
    missing: list[str] = []
    for key in _BUSINESS_ENV_KEYS:
        value = root_values.get(key)
        if value is None or (key != "REDIS_PASSWORD" and not str(value).strip()):
            missing.append(key)
        else:
            child[key] = str(value)
    app_id = root_values.get("PHASE0_DOUBAO_S2S_APP_ID")
    if not isinstance(app_id, str) or not app_id.strip():
        missing.append("PHASE0_DOUBAO_S2S_APP_ID")
    if missing:
        raise ValueError("项目根 .env 缺少 Phase0 必需项: " + ", ".join(sorted(missing)))
    if (
        child.get("MYSQL_DATABASE") == CAMPAIGN_DATABASE_NAME
        or child.get("REDIS_DB") == CAMPAIGN_REDIS_DB
    ):
        raise ValueError("Phase0 child 禁止使用 campaign MySQL/Redis")
    if not isinstance(secret, str) or not secret:
        raise ValueError("Provider credential 为空")

    s2s = draft_snapshot["s2s"]
    voice = draft_snapshot["voice"]
    child.update(
        {
            # Docker service names from the root .env are intentionally not
            # usable by a host-side Phase0 subprocess.
            "MYSQL_HOST": "127.0.0.1",
            "REDIS_HOST": "127.0.0.1",
            "PHASE0_DOUBAO_S2S_APP_ID": app_id.strip(),
            "PHASE0_DOUBAO_S2S_ACCESS_KEY": secret,
            "PHASE0_DOUBAO_S2S_RESOURCE_ID": str(s2s["resource_id"]),
            "PHASE0_DOUBAO_S2S_ENDPOINT": str(s2s["endpoint"]),
            "PHASE0_DOUBAO_S2S_MODEL": str(s2s["model_version"]),
            "PHASE0_DOUBAO_S2S_SPEAKER": str(voice["voice_id"]),
            "PHASE0_SETTINGS_PATH": str(
                phase0_root
                / "backend"
                / "phase0_realtime_voice"
                / "settings.local.json"
            ),
            "PYTHONPATH": str(phase0_root),
            "PYTHONUNBUFFERED": "1",
        }
    )
    if M1_PROTOCOL_PROFILE:
        child['PHASE0_M1_PROTOCOL_PROBES'] = '1'
    if M1_RECOVERY_PROFILE:
        child['PHASE0_M1_MISSING_PROBES_ONLY'] = '1'
    if M1_CANCEL_ONLY_PROFILE:
        child['PHASE0_M1_CANCEL_ONLY_PROBE'] = '1'
    if M1_CANCEL_RETRY_PROFILE:
        child['PHASE0_M1_CANCEL_RETRY'] = '1'
    if campaign_attempt is not None:
        attempt = _validate_worker_campaign_attempt(campaign_attempt)
        child.update(
            {
                "PHASE0_M1_ATTEMPT_DIR": str(attempt["attempt_directory"]),
                "PHASE0_M1_CAMPAIGN_ID": attempt["campaign_id"],
                "PHASE0_M1_MATRIX_SHA256": attempt["matrix_sha256"],
                "PHASE0_M1_RUNTIME_MANIFEST_SHA256": attempt[
                    "runtime_manifest_sha256"
                ],
                "PHASE0_M1_BASELINE_EPOCH": str(attempt["baseline_epoch"]),
                "PHASE0_M1_EXPECTED_START_ATTEMPT_KIND": attempt["attempt_kind"],
                "PHASE0_M1_EXPECTED_START_ATTEMPT_ORDINAL": str(
                    attempt["attempt_ordinal"]
                ),
            }
        )
        reconnect_ordinal = attempt.get("expected_reconnect_ordinal")
        if reconnect_ordinal is not None:
            child["PHASE0_M1_EXPECTED_RECONNECT_ATTEMPT_ORDINAL"] = str(
                reconnect_ordinal
            )
        if attempt["fresh_admin_worker"]:
            child["PHASE0_M1_FRESH_ADMIN_WORKER"] = "1"
    return child


M1_ADMIN_ACK_PROFILE = False
M1_ADMIN_ACK_ORDINAL = 7


def configure_m1_protocol_profile(*, recovery: bool = False, cancel_only: bool = False, cancel_retry: bool = False) -> None:
    """Select the isolated v7/v8 profile in this process; no reservation."""
    global M1_PROTOCOL_PROFILE, PHASE0_RELATIVE_ROOT, PHASE0_ADAPTER_VERSION
    global M1_RECOVERY_PROFILE, M1_CANCEL_ONLY_PROFILE, M1_CANCEL_RETRY_PROFILE, M1_ADMIN_ACK_PROFILE
    M1_ADMIN_ACK_PROFILE = False
    global PHASE0_EVIDENCE_SUITE_VERSION, CAMPAIGN_RUNTIME_EXACT_PATHS
    global CAMPAIGN_ATTEMPT_LIMIT, BASELINE_BATCHES, CAMPAIGN_ATTEMPT_KINDS, DIRECT_PHASE0_ATTEMPT_KINDS
    if cancel_retry and not (cancel_only and recovery):
        raise ValueError("cancel retry requires cancel-only recovery")
    M1_CANCEL_RETRY_PROFILE = cancel_retry
    if cancel_only and not recovery:
        raise ValueError("cancel-only requires recovery profile")
    old_root = str(PHASE0_RELATIVE_ROOT)
    M1_CANCEL_ONLY_PROFILE = cancel_only
    M1_PROTOCOL_PROFILE = True
    M1_RECOVERY_PROFILE = recovery
    PHASE0_RELATIVE_ROOT = Path('tmp/phase0-step004-m1-recovery-20260908') if recovery else M1_PROTOCOL_ROOT
    if cancel_only:
        PHASE0_RELATIVE_ROOT = Path('tmp/phase0-step004-m1-cancel-20260909')
    if cancel_retry:
        PHASE0_RELATIVE_ROOT = Path('tmp/phase0-step004-m1-cancel-retry-20260909')
    version = 'v9' if cancel_only else 'v8' if recovery else 'v7'
    PHASE0_ADAPTER_VERSION = 'b937a78-step004-evidence-' + version
    PHASE0_EVIDENCE_SUITE_VERSION = 'step004-o01-' + version
    CAMPAIGN_RUNTIME_EXACT_PATHS = tuple(p.replace(old_root, str(PHASE0_RELATIVE_ROOT)) for p in CAMPAIGN_RUNTIME_EXACT_PATHS)
    # Capacity only. A matching user authorization is required before reservation.
    CAMPAIGN_ATTEMPT_LIMIT = 6 if cancel_retry else 5
    BASELINE_BATCHES = {1:'m1_protocol'}
    if recovery:
        BASELINE_BATCHES[2] = 'm1_tool_recovery'
    if cancel_only:
        BASELINE_BATCHES[3] = 'm1_cancel_only'
    if cancel_retry:
        BASELINE_BATCHES[4] = 'm1_cancel_retry'
    CAMPAIGN_ATTEMPT_KINDS = frozenset({'s01_start_session','s01_reconnect','admin_ack'})
    DIRECT_PHASE0_ATTEMPT_KINDS = CAMPAIGN_ATTEMPT_KINDS - {'admin_ack'}


def validate_admin_playback_stimulus(path: Path) -> dict[str, Any]:
    """Fail before any reservation/session if preset PCM is empty or silent."""
    import struct
    import wave

    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 16000):
            raise ValueError("管理播放输入必须是 16kHz 单声道 PCM16")
        frames = stream.getnframes()
        if not 16000 <= frames <= 240000:
            raise ValueError("管理播放输入必须包含 1～15 秒非空音频")
        pcm = stream.readframes(frames)
    if len(pcm) != frames * 2:
        raise ValueError("管理播放输入音频已截断")
    peak = max(abs(sample[0]) for sample in struct.iter_unpack("<h", pcm))
    if peak < 100:
        raise ValueError("管理播放输入为静音或无有效信号")
    return {"pcm_bytes": len(pcm), "duration_ms": frames * 1000 // 16000,
            "peak": peak, "sha256": _file_sha256(path)}


def configure_m1_admin_ack_profile(*, manual_retry: bool = False) -> None:
    """One explicitly authorized successor attempt; preserve original v9 source.

    The local coordinator owns the immutable parent-ledger reference and single
    reservation. This profile admits only the selected number (7, or user-confirmed 8).
    """
    global M1_ADMIN_ACK_PROFILE, M1_RECOVERY_PROFILE, M1_CANCEL_ONLY_PROFILE, M1_ADMIN_ACK_ORDINAL
    global M1_CANCEL_RETRY_PROFILE, BASELINE_BATCHES, CAMPAIGN_ATTEMPT_LIMIT
    global CAMPAIGN_ATTEMPT_KINDS, DIRECT_PHASE0_ATTEMPT_KINDS
    configure_m1_protocol_profile(recovery=True, cancel_only=True, cancel_retry=True)
    M1_ADMIN_ACK_PROFILE = True
    M1_RECOVERY_PROFILE = M1_CANCEL_ONLY_PROFILE = M1_CANCEL_RETRY_PROFILE = False
    BASELINE_BATCHES = {5: "m1_restricted_admin_ack"}
    M1_ADMIN_ACK_ORDINAL = 8 if manual_retry else 7
    CAMPAIGN_ATTEMPT_LIMIT = M1_ADMIN_ACK_ORDINAL
    CAMPAIGN_ATTEMPT_KINDS = frozenset({"admin_ack"})
    DIRECT_PHASE0_ATTEMPT_KINDS = frozenset()


def authorize_m1_protocol_campaign(path: Path, frozen: FrozenCampaign) -> None:
    """Consume the recorded user decision only for its exact frozen run."""
    global _M1_PROTOCOL_AUTHORIZATION
    value = json.loads(path.read_text(encoding='utf-8'))
    expected = {
        'schema_version':'m1-protocol-user-authorization/v1',
        'campaign_id':frozen.campaign_id, 'matrix_sha256':frozen.matrix_sha256,
        'runtime_manifest_sha256':frozen.runtime_manifest_sha256,
        'max_provider_attempts':CAMPAIGN_ATTEMPT_LIMIT, 'automatic_retries':0,
        'scope':('m1_reply_cancel_only' if M1_CANCEL_ONLY_PROFILE else 'm1_missing_cancel_truncate_only' if M1_RECOVERY_PROFILE else 'm1_protocol_reconnect_admin_ack'), 'authorized_by':'user',
    }
    if (type(value) is not dict or set(value) != set(expected) | {'confirmed_at'}
        or any(value.get(k) != v or type(value.get(k)) is not type(v) for k,v in expected.items())
        or not frozen.campaign_id.startswith('m1-protocol-')):
        raise ValueError('M1 专项授权与冻结范围不一致')
    _validated_utc_timestamp(value['confirmed_at'])
    _M1_PROTOCOL_AUTHORIZATION = (frozen.campaign_id, frozen.matrix_sha256, frozen.runtime_manifest_sha256)


def _attempt_limit_for_epoch(epoch: Any) -> int:
    if M1_ADMIN_ACK_PROFILE:
        return M1_ADMIN_ACK_ORDINAL if epoch == 5 else 0
    if M1_PROTOCOL_PROFILE:
        return 6 if M1_CANCEL_RETRY_PROFILE and epoch == 4 else 5
    if epoch == 6:
        return AUTHORIZED_TEN_MINUTE_LIMIT
    if epoch == 5:
        return AUTHORIZED_FIFTH_ROUND_LIMIT
    if epoch == 4:
        return AUTHORIZED_FOURTH_ROUND_LIMIT
    return CAMPAIGN_ATTEMPT_LIMIT


def _validate_worker_campaign_attempt(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "attempt_directory",
        "campaign_id",
        "matrix_sha256",
        "runtime_manifest_sha256",
        "baseline_epoch",
        "attempt_id",
        "attempt_ordinal",
        "attempt_kind",
        "fresh_admin_worker",
    }
    if (
        not isinstance(value, Mapping)
        or not required <= set(value)
        or not (set(value) - required) <= {"expected_reconnect_ordinal"}
    ):
        raise ValueError("Phase0 campaign attempt context 非法")
    attempt = deepcopy(dict(value))
    attempt["campaign_id"] = _validate_campaign_id(attempt["campaign_id"])
    try:
        attempt["attempt_id"] = str(uuid.UUID(attempt["attempt_id"]))
    except (TypeError, ValueError):
        raise ValueError("Phase0 campaign attempt_id 非法") from None
    if (
        not _valid_hash(attempt.get("matrix_sha256"))
        or not _valid_hash(attempt.get("runtime_manifest_sha256"))
        or type(attempt.get("baseline_epoch")) is not int
        or attempt["baseline_epoch"] not in BASELINE_BATCHES
        or type(attempt.get("attempt_ordinal")) is not int
        or not 1 <= attempt["attempt_ordinal"] <= _attempt_limit_for_epoch(attempt["baseline_epoch"])
        or attempt.get("attempt_kind") not in CAMPAIGN_ATTEMPT_KINDS
        or type(attempt.get("fresh_admin_worker")) is not bool
    ):
        raise ValueError("Phase0 campaign attempt context 非法")
    reconnect = attempt.get("expected_reconnect_ordinal")
    if M1_ADMIN_ACK_PROFILE and (
        attempt["baseline_epoch"] != 5 or attempt["attempt_ordinal"] != M1_ADMIN_ACK_ORDINAL
        or attempt["attempt_kind"] != "admin_ack" or not attempt["fresh_admin_worker"]
        or reconnect is not None
    ):
        raise ValueError("管理播放专项仅允许当前绑定的一次 fresh admin ACK，禁止其他场景与重连")
    if M1_RECOVERY_PROFILE and (attempt['attempt_kind'] != 's01_start_session'
        or reconnect is not None or attempt['fresh_admin_worker']):
        raise ValueError('本轮 M1 恢复仅允许打断和截断，不允许重连或管理实播')
    if attempt["baseline_epoch"] == 6 and (
        attempt["attempt_kind"] != "s06_start_session"
        or attempt["attempt_ordinal"] != AUTHORIZED_TEN_MINUTE_LIMIT
        or attempt["fresh_admin_worker"]
        or reconnect is not None
    ):
        raise ValueError("10分钟调整仅允许一次 S06，不允许重连或管理端调用")
    if reconnect is not None and (type(reconnect) is not int or not 1 <= reconnect <= _attempt_limit_for_epoch(attempt["baseline_epoch"])):
        raise ValueError("Phase0 reconnect attempt ordinal 非法")
    if attempt["fresh_admin_worker"] and attempt["attempt_kind"] not in {
        "admin_connection",
        "admin_ack",
    }:
        raise ValueError("fresh admin worker attempt kind 非法")
    attempt["attempt_directory"] = Path(attempt["attempt_directory"]).resolve()
    return attempt


class Phase0SubprocessWorker:
    """Fresh, silent Phase0 process owned by exactly one admin request."""

    def __init__(
        self,
        *,
        phase0_root: Path,
        project_env_path: Path,
        draft_snapshot: Mapping[str, Any],
        secret: str,
        port: int = DEFAULT_PHASE0_PORT,
        process_factory: Callable[..., Any] | None = None,
        http_client: Any | None = None,
        parent_environ: Mapping[str, str] | None = None,
        startup_timeout_seconds: float = DEFAULT_PHASE0_STARTUP_SECONDS,
        campaign_attempt: Mapping[str, Any] | None = None,
    ) -> None:
        if not 1024 <= int(port) <= 65535:
            raise ValueError("Phase0 port 非法")
        self._phase0_root = Path(phase0_root).resolve()
        self._project_env_path = Path(project_env_path).resolve()
        self._draft = deepcopy(dict(draft_snapshot))
        self._secret: str | None = secret
        self._port = int(port)
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._client = http_client
        self._parent_environ = parent_environ
        self._startup_timeout_seconds = startup_timeout_seconds
        self._campaign_attempt = (
            _validate_worker_campaign_attempt(campaign_attempt)
            if campaign_attempt is not None
            else None
        )
        self._process: Any | None = None

    def __repr__(self) -> str:
        return f"Phase0SubprocessWorker(port={self._port}, redacted=True)"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body=None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        if self._client is None:
            raise RuntimeError("Phase0 HTTP client 未启动")
        try:
            response = await self._client.request(
                method,
                path,
                json=json_body,
                headers=dict(headers) if headers is not None else None,
            )
            response.raise_for_status()
            return response.json()
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("Phase0 HTTP 请求失败") from None

    async def _envelope(
        self,
        method: str,
        path: str,
        *,
        json_body=None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        payload = await self._request(
            method,
            path,
            json_body=json_body,
            headers=headers,
        )
        if not isinstance(payload, Mapping) or payload.get("code") != 0:
            raise RuntimeError("Phase0 返回非成功状态")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise RuntimeError("Phase0 返回结构非法")
        return data

    async def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("Phase0 worker 已启动")
        public_settings = load_phase0_public_provider_settings(
            project_env_path=self._project_env_path,
            phase0_root=self._phase0_root,
        )
        _assert_draft_public_settings(self._draft, public_settings)
        secret = self._secret
        self._secret = None
        child_env = build_phase0_child_environment(
            project_env_path=self._project_env_path,
            phase0_root=self._phase0_root,
            draft_snapshot=self._draft,
            secret=secret or "",
            parent_environ=self._parent_environ,
            campaign_attempt=self._campaign_attempt,
        )
        try:
            self._process = await self._process_factory(
                sys.executable,
                "-m",
                "uvicorn",
                "backend.phase0_realtime_voice.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self._port),
                cwd=str(self._phase0_root),
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            for key in list(child_env):
                child_env[key] = ""
            child_env.clear()
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{self._port}",
                timeout=5.0,
            )
        deadline = time.monotonic() + self._startup_timeout_seconds
        while True:
            if self._process.returncode is not None:
                raise RuntimeError("Phase0 worker 启动失败")
            try:
                await self._envelope("GET", "/api/phase0/realtime-voice/health")
                return
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Phase0 worker 启动超时") from None
                await asyncio.sleep(0.05)

    async def create_connection_session(self, *, user_id: int) -> Mapping[str, Any]:
        headers = None
        if self._campaign_attempt is not None:
            headers = {
                "X-LXM-M1-Attempt-Id": self._campaign_attempt["attempt_id"]
            }
        return await self._envelope(
            "POST",
            "/api/phase0/realtime-voice/sessions",
            json_body={
                "user_id": int(user_id),
                "voice": str(self._draft["voice"]["voice_id"]),
                "persona_label": "active",
                "net_profile": "baseline",
                "mock_s2s": False,
                **({'m1_protocol_probes':True} if M1_PROTOCOL_PROFILE else {}),
            },
            headers=headers,
        )

    async def get_session(self, session_id: str) -> Mapping[str, Any]:
        return await self._envelope(
            "GET", f"/api/phase0/realtime-voice/sessions/{session_id}"
        )

    async def fetch_evidence(self, session_id: str) -> Mapping[str, Any]:
        payload = await self._request(
            "GET",
            f"/api/phase0/realtime-voice/sessions/{session_id}/evidence.json",
        )
        if not isinstance(payload, Mapping):
            raise RuntimeError("Phase0 evidence 结构非法")
        return payload

    async def end_session(self, session_id: str) -> None:
        await self._envelope(
            "DELETE", f"/api/phase0/realtime-voice/sessions/{session_id}"
        )

    async def stop(self) -> None:
        client, self._client = self._client, None
        process, self._process = self._process, None
        cleanup = asyncio.create_task(_cleanup_worker_resources(client, process))
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError


async def _cleanup_worker_resources(client: Any, process: Any) -> None:
    if client is not None:
        try:
            async with asyncio.timeout(WORKER_CLIENT_CLOSE_SECONDS):
                await client.aclose()
        except BaseException:
            pass
    if process is None or process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        async with asyncio.timeout(WORKER_TERMINATE_WAIT_SECONDS):
            await process.wait()
        return
    except (TimeoutError, ProcessLookupError):
        pass
    try:
        process.kill()
    except ProcessLookupError:
        return
    try:
        async with asyncio.timeout(WORKER_KILL_WAIT_SECONDS):
            await process.wait()
    except (TimeoutError, ProcessLookupError):
        pass


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenCampaign:
    campaign_id: str
    matrix_sha256: str
    runtime_manifest_sha256: str
    ledger_path: Path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise ValueError("冻结文件不可读") from None
    return digest.hexdigest()


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_campaign_id(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value
    ) is None:
        raise ValueError("campaign_id 非法")
    return value


def campaign_ledger_path(
    campaign_id: str,
    *,
    project_root: Path = _PROJECT_ROOT,
) -> Path:
    """Return the only ledger path accepted for one campaign identifier."""

    campaign = _validate_campaign_id(campaign_id)
    return (
        Path(project_root).resolve()
        / CAMPAIGNS_RELATIVE_ROOT
        / campaign
        / "attempt-ledger.json"
    )


def current_runtime_identity() -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    for distribution in CAMPAIGN_RUNTIME_PACKAGE_NAMES:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            raise ValueError("runtime 关键 package 缺失") from None
        packages.append({"distribution": distribution, "version": version})
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "packages": packages,
    }


def discover_runtime_closure_paths(project_root: Path) -> tuple[str, ...]:
    """Recompute the full M1/Phase0 executable closure on every verification."""

    root = Path(project_root).resolve()
    phase0_root = root / PHASE0_RELATIVE_ROOT
    paths = set(CAMPAIGN_RUNTIME_EXACT_PATHS)
    for source_root in (root / "backend", phase0_root / "backend"):
        if not source_root.is_dir() or source_root.is_symlink():
            raise ValueError("runtime closure 根目录缺失或非法")
        for candidate in source_root.rglob("*.py"):
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if candidate.is_symlink() or not resolved.is_relative_to(root):
                raise ValueError("runtime closure path 非法")
            paths.add(resolved.relative_to(root).as_posix())
    for relative_text in CAMPAIGN_RUNTIME_EXACT_PATHS:
        candidate = root / relative_text
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError("runtime closure 固定文件缺失或非法")
    return tuple(sorted(paths))


def _runtime_manifest_sha256(
    path: Path,
    *,
    project_root: Path,
    required_paths: tuple[str, ...] | None = None,
) -> str:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("runtime manifest 不可读") from None
    if type(manifest) is not dict or set(manifest) != {
        "schema_version",
        "files",
        "python",
        "packages",
    }:
        raise ValueError("runtime manifest schema 非法")
    files = manifest.get("files")
    if manifest.get("schema_version") != RUNTIME_MANIFEST_SCHEMA or type(files) is not list:
        raise ValueError("runtime manifest schema 非法")
    expected_paths = (
        tuple(sorted(required_paths))
        if required_paths is not None
        else discover_runtime_closure_paths(project_root)
    )
    manifest_paths = tuple(
        item.get("path") if type(item) is dict else None for item in files
    )
    if manifest_paths != expected_paths:
        raise ValueError("runtime manifest closure 文件集合漂移")
    identity = current_runtime_identity()
    if manifest.get("python") != identity["python"]:
        raise ValueError("runtime manifest Python 版本漂移")
    if manifest.get("packages") != identity["packages"]:
        raise ValueError("runtime manifest package 版本漂移")
    root = Path(project_root).resolve()
    for item in files:
        if type(item) is not dict or set(item) != {"path", "sha256"}:
            raise ValueError("runtime manifest schema 非法")
        relative = Path(item["path"])
        unresolved_target = root / relative
        target = unresolved_target.resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or unresolved_target.is_symlink()
            or not target.is_relative_to(root)
        ):
            raise ValueError("runtime manifest path 非法")
        if not _valid_hash(item["sha256"]) or _file_sha256(target) != item["sha256"]:
            raise ValueError("runtime manifest 文件 hash 漂移")
    return _canonical_sha256(manifest)


def resolve_frozen_campaign(
    *,
    campaign_id: str,
    matrix_path: Path,
    runtime_manifest_path: Path,
    ledger_path: Path | None = None,
    project_root: Path = _PROJECT_ROOT,
    required_runtime_paths: tuple[str, ...] | None = None,
) -> FrozenCampaign:
    root = Path(project_root).resolve()
    campaign = _validate_campaign_id(campaign_id)
    matrix = Path(matrix_path).resolve()
    manifest = Path(runtime_manifest_path).resolve()
    expected_ledger = campaign_ledger_path(campaign, project_root=root)
    ledger = expected_ledger if ledger_path is None else Path(ledger_path).resolve()
    if ledger != expected_ledger:
        raise ValueError("campaign ledger 必须使用固定 campaigns/<id>/attempt-ledger.json")
    if any(not path.is_relative_to(root) for path in (matrix, manifest, ledger)):
        raise ValueError("campaign 冻结文件必须位于项目目录")
    return FrozenCampaign(
        campaign_id=campaign,
        matrix_sha256=_file_sha256(matrix),
        runtime_manifest_sha256=_runtime_manifest_sha256(
            manifest,
            project_root=root,
            required_paths=required_runtime_paths,
        ),
        ledger_path=ledger,
    )


def resolve_frozen_campaign_from_args(args: argparse.Namespace) -> FrozenCampaign:
    missing = [
        name
        for name in ("campaign_id", "matrix_path", "runtime_manifest")
        if not getattr(args, name, None)
    ]
    if missing:
        raise ValueError("Provider 模式缺少冻结 campaign 参数")
    return resolve_frozen_campaign(
        campaign_id=args.campaign_id,
        matrix_path=args.matrix_path,
        runtime_manifest_path=args.runtime_manifest,
        ledger_path=getattr(args, "ledger_path", None),
    )


_LEDGER_FIELDS = {
    "schema_version",
    "campaign_id",
    "max_provider_attempts",
    "active_baseline_epoch",
    "baseline_epochs",
    "attempts",
}
_ATTEMPT_FIELDS = {
    "attempt_id",
    "attempt_ordinal",
    "baseline_epoch",
    "attempt_kind",
    "reserved_at",
}
_BASELINE_FIELDS = {
    "schema_version",
    "public_provider_settings_sha256",
    "voice_draft_sha256",
    "evidence_dimensions",
    "evidence_fingerprint",
}
_BASELINE_DIMENSION_FIELDS = (
    "provider_profile",
    "model_version",
    "protocol_profile",
    "adapter_version",
    "sdk_version",
    "evidence_suite_version",
)
_BASELINE_EPOCH_FIELDS = {
    "baseline_epoch",
    "batch",
    "matrix_sha256",
    "runtime_manifest_sha256",
    "baseline",
    "regression_evidence",
    "registered_at",
    "previous_epoch_sha256",
    "epoch_sha256",
}
_REGRESSION_EVIDENCE_FIELDS = {"path", "sha256"}


def _validate_campaign_baseline(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _BASELINE_FIELDS:
        raise ValueError("campaign baseline schema 非法")
    dimensions = value.get("evidence_dimensions")
    if (
        value.get("schema_version") != CAMPAIGN_BASELINE_SCHEMA
        or not _valid_hash(value.get("public_provider_settings_sha256"))
        or not _valid_hash(value.get("voice_draft_sha256"))
        or type(dimensions) is not dict
        or set(dimensions) != set(_BASELINE_DIMENSION_FIELDS)
    ):
        raise ValueError("campaign baseline schema 非法")
    safe_dimension = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@+-]*")
    if any(
        not isinstance(dimensions.get(field), str)
        or safe_dimension.fullmatch(dimensions[field]) is None
        for field in _BASELINE_DIMENSION_FIELDS
    ):
        raise ValueError("campaign baseline 六维非法")
    if (
        not _valid_hash(value.get("evidence_fingerprint"))
        or value["evidence_fingerprint"] != _canonical_sha256(dimensions)
    ):
        raise ValueError("campaign baseline fingerprint 非法")
    return deepcopy(value)


def build_campaign_baseline_snapshot(
    *,
    public_settings: Mapping[str, str],
    voice_draft: Mapping[str, Any],
) -> dict[str, Any]:
    if set(public_settings) != {"endpoint", "resource_id", "model_version", "voice_id"}:
        raise ValueError("campaign public settings 非法")
    validate_phase0_draft(voice_draft)
    _assert_draft_public_settings(voice_draft, public_settings)
    try:
        sdk_version = f"websockets-{metadata.version('websockets')}"
    except metadata.PackageNotFoundError:
        raise ValueError("campaign SDK 版本不可用") from None
    dimensions = {
        "provider_profile": PHASE0_PROVIDER_PROFILE,
        "model_version": str(voice_draft["s2s"]["model_version"]),
        "protocol_profile": PHASE0_PROTOCOL_PROFILE,
        "adapter_version": PHASE0_ADAPTER_VERSION,
        "sdk_version": sdk_version,
        "evidence_suite_version": PHASE0_EVIDENCE_SUITE_VERSION,
    }
    return _validate_campaign_baseline(
        {
            "schema_version": CAMPAIGN_BASELINE_SCHEMA,
            "public_provider_settings_sha256": _canonical_sha256(public_settings),
            "voice_draft_sha256": _canonical_sha256(voice_draft),
            "evidence_dimensions": dimensions,
            "evidence_fingerprint": _canonical_sha256(dimensions),
        }
    )


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("campaign 时间必须带时区")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validated_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("attempt ledger schema 非法")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("attempt ledger schema 非法") from None
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("attempt ledger schema 非法")
    return parsed


def _epoch_sha256(epoch: Mapping[str, Any]) -> str:
    return _canonical_sha256({key: value for key, value in epoch.items() if key != "epoch_sha256"})


def _new_baseline_epoch(
    *,
    baseline_epoch: int,
    matrix_sha256: str,
    runtime_manifest_sha256: str,
    baseline: Mapping[str, Any],
    regression_evidence: Mapping[str, str] | None,
    registered_at: datetime,
    previous_epoch_sha256: str | None,
) -> dict[str, Any]:
    epoch = {
        "baseline_epoch": baseline_epoch,
        "batch": BASELINE_BATCHES[baseline_epoch],
        "matrix_sha256": matrix_sha256,
        "runtime_manifest_sha256": runtime_manifest_sha256,
        "baseline": _validate_campaign_baseline(dict(baseline)),
        "regression_evidence": deepcopy(regression_evidence),
        "registered_at": _utc_timestamp(registered_at),
        "previous_epoch_sha256": previous_epoch_sha256,
    }
    epoch["epoch_sha256"] = _epoch_sha256(epoch)
    return epoch


def _validate_attempt_ledger(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _LEDGER_FIELDS:
        raise ValueError("attempt ledger schema 非法")
    if (
        value.get("schema_version") != ATTEMPT_LEDGER_SCHEMA
        or value.get("max_provider_attempts") != _attempt_limit_for_epoch(value.get("active_baseline_epoch"))
    ):
        raise ValueError("attempt ledger schema 非法")
    _validate_campaign_id(value.get("campaign_id"))
    epochs = value.get("baseline_epochs")
    active_epoch = value.get("active_baseline_epoch")
    if (
        type(epochs) is not list
        or len(epochs) not in BASELINE_BATCHES
        or active_epoch != len(epochs)
    ):
        raise ValueError("attempt ledger schema 非法")
    previous_hash: str | None = None
    for ordinal, epoch in enumerate(epochs, 1):
        if type(epoch) is not dict or set(epoch) != _BASELINE_EPOCH_FIELDS:
            raise ValueError("attempt ledger schema 非法")
        regression = epoch.get("regression_evidence")
        if ordinal == 1:
            regression_valid = regression is None
        else:
            regression_valid = (
                type(regression) is dict
                and set(regression) == _REGRESSION_EVIDENCE_FIELDS
                and isinstance(regression.get("path"), str)
                and bool(regression["path"])
                and _valid_hash(regression.get("sha256"))
            )
        if (
            epoch.get("baseline_epoch") != ordinal
            or epoch.get("batch") != BASELINE_BATCHES[ordinal]
            or not _valid_hash(epoch.get("matrix_sha256"))
            or not _valid_hash(epoch.get("runtime_manifest_sha256"))
            or epoch.get("previous_epoch_sha256") != previous_hash
            or not _valid_hash(epoch.get("epoch_sha256"))
            or epoch["epoch_sha256"] != _epoch_sha256(epoch)
            or not regression_valid
        ):
            raise ValueError("attempt ledger schema 非法")
        _validate_campaign_baseline(epoch.get("baseline"))
        _validated_utc_timestamp(epoch.get("registered_at"))
        previous_hash = epoch["epoch_sha256"]
    attempts = value.get("attempts")
    if type(attempts) is not list or len(attempts) > value["max_provider_attempts"]:
        raise ValueError("attempt ledger schema 非法")
    ids: set[str] = set()
    previous_attempt_epoch = 1
    sealed_epochs: set[int] = set()
    for ordinal, attempt in enumerate(attempts, 1):
        if type(attempt) is not dict or set(attempt) != _ATTEMPT_FIELDS:
            raise ValueError("attempt ledger schema 非法")
        try:
            reserved_text = str(attempt["reserved_at"])
            attempt_id = str(uuid.UUID(attempt["attempt_id"]))
            reserved_at = _validated_utc_timestamp(reserved_text)
        except (KeyError, TypeError, ValueError):
            raise ValueError("attempt ledger schema 非法") from None
        if (
            attempt_id != attempt["attempt_id"]
            or attempt_id in ids
            or attempt.get("attempt_ordinal") != ordinal
            or type(attempt.get("baseline_epoch")) is not int
            or not 1 <= attempt["baseline_epoch"] <= active_epoch
            or attempt["baseline_epoch"] < previous_attempt_epoch
            or attempt["baseline_epoch"] in sealed_epochs
            or attempt.get("attempt_kind") not in CAMPAIGN_ATTEMPT_KINDS
            or reserved_at.tzinfo is None
        ):
            raise ValueError("attempt ledger schema 非法")
        ids.add(attempt_id)
        if attempt["baseline_epoch"] == 6 and (
            attempt["attempt_kind"] != "s06_start_session"
            or attempt["attempt_ordinal"] != AUTHORIZED_TEN_MINUTE_LIMIT
        ):
            raise ValueError("10分钟调整仅允许第16次 S06")
        previous_attempt_epoch = attempt["baseline_epoch"]
        if attempt["attempt_kind"] == "admin_ack":
            sealed_epochs.add(attempt["baseline_epoch"])
    return deepcopy(value)


def _read_attempt_ledger(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as stream:
            return _validate_attempt_ledger(json.load(stream))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("attempt ledger schema 非法") from None


def _atomic_write_ledger(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_attempt_reservation(
    *,
    ledger_path: Path,
    campaign_id: str,
    matrix_sha256: str,
    runtime_manifest_sha256: str,
    attempt: Mapping[str, Any],
) -> Path:
    """Atomically publish one exact, one-shot Phase0 gate authorization."""

    directory = ledger_path.parent / "attempt-reservations"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    reservation = {
        "schema_version": ATTEMPT_RECEIPT_SCHEMA,
        "campaign_id": campaign_id,
        "matrix_sha256": matrix_sha256,
        "runtime_manifest_sha256": runtime_manifest_sha256,
        "baseline_epoch": attempt["baseline_epoch"],
        "attempt_id": attempt["attempt_id"],
        "attempt_ordinal": attempt["attempt_ordinal"],
        "attempt_kind": attempt["attempt_kind"],
        "reserved_at": attempt["reserved_at"],
    }
    target = directory / f"{attempt['attempt_id']}.reserved.json"
    encoded = json.dumps(
        reservation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return target
    finally:
        if temporary.exists():
            temporary.unlink()


def reserve_provider_attempt(
    *,
    ledger_path: Path | None,
    project_root: Path = _PROJECT_ROOT,
    campaign_id: str,
    matrix_sha256: str,
    runtime_manifest_sha256: str,
    baseline: Mapping[str, Any],
    attempt_kind: str,
    now: Callable[[], datetime] | None = None,
    attempt_id_factory: Callable[[], uuid.UUID] | None = None,
) -> dict[str, Any]:
    if M1_PROTOCOL_PROFILE and _M1_PROTOCOL_AUTHORIZATION != (campaign_id, matrix_sha256, runtime_manifest_sha256):
        raise ValueError('M1 专项尚无匹配的用户授权，不能预约或复用旧额度')
    if M1_RECOVERY_PROFILE and attempt_kind != 's01_start_session':
        raise ValueError('本轮 M1 恢复仅允许打断和截断，不允许重连或管理实播')
    campaign_id = _validate_campaign_id(campaign_id)
    if not _valid_hash(matrix_sha256) or not _valid_hash(runtime_manifest_sha256):
        raise ValueError("campaign hash 非法")
    if attempt_kind not in CAMPAIGN_ATTEMPT_KINDS:
        raise ValueError("attempt_kind 非法")
    baseline_snapshot = _validate_campaign_baseline(dict(baseline))
    if M1_PROTOCOL_PROFILE and any(
        baseline_snapshot['evidence_dimensions'].get(k) != v for k,v in {
            'adapter_version':PHASE0_ADAPTER_VERSION,
            'evidence_suite_version':PHASE0_EVIDENCE_SUITE_VERSION,
            'model_version':'2.2.0.0', 'protocol_profile':PHASE0_PROTOCOL_PROFILE,
            'provider_profile':PHASE0_PROVIDER_PROFILE,
        }.items()
    ):
        raise ValueError('M1 专项 baseline 版本不匹配')
    ledger = campaign_ledger_path(campaign_id, project_root=project_root)
    if ledger_path is not None and Path(ledger_path).resolve() != ledger:
        raise ValueError("campaign ledger 必须使用固定路径，禁止换 ledger 重置")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger.with_name(ledger.name + ".lock")
    lock_flags = (
        os.O_CREAT
        | os.O_RDWR
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    lock_fd = os.open(lock_path, lock_flags, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        value = _read_attempt_ledger(ledger)
        if value is None:
            if M1_RECOVERY_PROFILE:
                raise ValueError('M1 恢复必须续接原账本，禁止创建新额度')
            registered_at = (now or (lambda: datetime.now(timezone.utc)))()
            value = {
                "schema_version": ATTEMPT_LEDGER_SCHEMA,
                "campaign_id": campaign_id,
                "max_provider_attempts": CAMPAIGN_ATTEMPT_LIMIT,
                "active_baseline_epoch": 1,
                "baseline_epochs": [
                    _new_baseline_epoch(
                        baseline_epoch=1,
                        matrix_sha256=matrix_sha256,
                        runtime_manifest_sha256=runtime_manifest_sha256,
                        baseline=baseline_snapshot,
                        regression_evidence=None,
                        registered_at=registered_at,
                        previous_epoch_sha256=None,
                    )
                ],
                "attempts": [],
            }
        elif value["campaign_id"] != campaign_id:
            raise ValueError("attempt ledger 与冻结 campaign 绑定冲突")
        current_epoch = value["baseline_epochs"][value["active_baseline_epoch"] - 1]
        if (
            current_epoch["matrix_sha256"] != matrix_sha256
            or current_epoch["runtime_manifest_sha256"] != runtime_manifest_sha256
            or current_epoch["baseline"] != baseline_snapshot
        ):
            raise ValueError("attempt ledger 与当前冻结 baseline 绑定冲突，禁止回退")
        attempts = value["attempts"]
        if value["active_baseline_epoch"] == 6 and attempt_kind != "s06_start_session":
            raise ValueError("10分钟调整仅允许 S06")
        if len(attempts) >= value["max_provider_attempts"]:
            raise RuntimeError(f"Provider attempt 已达到 {value['max_provider_attempts']} 次上限")
        attempt_id = str((attempt_id_factory or uuid.uuid4)())
        reserved_at = (now or (lambda: datetime.now(timezone.utc)))()
        if reserved_at.tzinfo is None:
            raise ValueError("attempt 时间必须带时区")
        attempt = {
            "attempt_id": attempt_id,
            "attempt_ordinal": len(attempts) + 1,
            "baseline_epoch": value["active_baseline_epoch"],
            "attempt_kind": attempt_kind,
            "reserved_at": _utc_timestamp(reserved_at),
        }
        attempts.append(attempt)
        _validate_attempt_ledger(value)
        _atomic_write_ledger(ledger, value)
        _write_attempt_reservation(
            ledger_path=ledger,
            campaign_id=campaign_id,
            matrix_sha256=matrix_sha256,
            runtime_manifest_sha256=runtime_manifest_sha256,
            attempt=attempt,
        )
        return {
            "schema_version": ATTEMPT_RECEIPT_SCHEMA,
            "campaign_id": campaign_id,
            **{key: attempt[key] for key in ("attempt_id", "attempt_ordinal", "attempt_kind")},
            "baseline_epoch": attempt["baseline_epoch"],
            "remaining_attempts": value["max_provider_attempts"] - len(attempts),
        }
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def advance_campaign_to_final_batch(
    *,
    ledger_path: Path | None,
    project_root: Path = _PROJECT_ROOT,
    campaign_id: str,
    matrix_sha256: str,
    runtime_manifest_sha256: str,
    baseline: Mapping[str, Any],
    regression_evidence_path: Path,
    authorized_retest: bool = False,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    campaign_id = _validate_campaign_id(campaign_id)
    if not _valid_hash(matrix_sha256) or not _valid_hash(runtime_manifest_sha256):
        raise ValueError("campaign hash 非法")
    baseline_snapshot = _validate_campaign_baseline(dict(baseline))
    root = Path(project_root).resolve()
    ledger = campaign_ledger_path(campaign_id, project_root=root)
    if ledger_path is not None and Path(ledger_path).resolve() != ledger:
        raise ValueError("campaign ledger 必须使用固定路径，禁止换 ledger 重置")
    evidence = Path(regression_evidence_path).resolve()
    if (
        not evidence.is_relative_to(root)
        or not evidence.is_file()
        or evidence.is_symlink()
    ):
        raise ValueError("自动回归 evidence 文件非法")
    regression_evidence = {
        "path": evidence.relative_to(root).as_posix(),
        "sha256": _file_sha256(evidence),
    }
    if authorized_retest:
        try:
            approval = json.loads(evidence.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError("续测授权及回归证据不可读") from None
        if (
            not isinstance(approval, dict)
            or approval.get("authorized_additional_round") is not True
            or approval.get("passed") is not True
        ):
            raise ValueError("续测需要用户授权和通过的回归证据")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger.with_name(ledger.name + ".lock")
    lock_flags = (
        os.O_CREAT
        | os.O_RDWR
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    lock_fd = os.open(lock_path, lock_flags, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        value = _read_attempt_ledger(ledger)
        if value is None or value.get("campaign_id") != campaign_id:
            raise RuntimeError("initial batch 尚未登记")
        if M1_PROTOCOL_PROFILE:
            if not M1_RECOVERY_PROFILE or _M1_PROTOCOL_AUTHORIZATION != (
                campaign_id, matrix_sha256, runtime_manifest_sha256
            ):
                raise ValueError('M1 恢复需要匹配新基线的原额度授权')
            proof = json.loads(evidence.read_text(encoding='utf-8'))
            required = {
                'passed': True, 'authorization_scope': ('m1_reply_cancel_only' if M1_CANCEL_ONLY_PROFILE else 'm1_missing_cancel_truncate_only'),
                'prior_ledger_sha256': _file_sha256(ledger), 'max_provider_attempts': CAMPAIGN_ATTEMPT_LIMIT,
                'automatic_retries': 0, 'target_baseline_epoch': 4 if M1_CANCEL_RETRY_PROFILE else 3 if M1_CANCEL_ONLY_PROFILE else 2,
            }
            if (type(proof) is not dict or authorized_retest
                or any(type(proof.get(k)) is not type(v) or proof.get(k) != v for k, v in required.items())
                or value['max_provider_attempts'] != 5
                or value['active_baseline_epoch'] != (3 if M1_CANCEL_RETRY_PROFILE else 2 if M1_CANCEL_ONLY_PROFILE else 1)
                or any(a['attempt_kind'] == 'admin_ack' for a in value['attempts'])):
                raise ValueError('M1 恢复证据、原账本或五次额度不匹配')
            dimensions = baseline_snapshot['evidence_dimensions']
            prior_dimensions = value['baseline_epochs'][-1]['baseline']['evidence_dimensions']
            expected_dimensions = {**prior_dimensions,
                'adapter_version': PHASE0_ADAPTER_VERSION,
                'evidence_suite_version': PHASE0_EVIDENCE_SUITE_VERSION}
            if (dimensions != expected_dimensions or prior_dimensions['adapter_version'] != ('b937a78-step004-evidence-v9' if M1_CANCEL_RETRY_PROFILE else 'b937a78-step004-evidence-v8' if M1_CANCEL_ONLY_PROFILE else 'b937a78-step004-evidence-v7')
                or prior_dimensions['evidence_suite_version'] != ('step004-o01-v9' if M1_CANCEL_RETRY_PROFILE else 'step004-o01-v8' if M1_CANCEL_ONLY_PROFILE else 'step004-o01-v7')
                or baseline_snapshot['public_provider_settings_sha256'] != value['baseline_epochs'][-1]['baseline']['public_provider_settings_sha256']):
                raise ValueError('M1 恢复只允许对应的相邻工具版本续接')
        expected_epoch = 3 if M1_CANCEL_RETRY_PROFILE else 2 if (authorized_retest or M1_CANCEL_ONLY_PROFILE) else 1
        if authorized_retest and approval.get("target_baseline_epoch") in (4, 5, 6):
            target_epoch = approval["target_baseline_epoch"]
            expected_epoch = target_epoch - 1
            if (
                approval.get("max_provider_attempts") != _attempt_limit_for_epoch(target_epoch)
                or approval.get("prior_ledger_sha256") != _file_sha256(ledger)
            ):
                raise ValueError("续测须绑定当前账本与明确批准的调用上限")
            if target_epoch == 6 and (
                approval.get("authorization_scope") != TEN_MINUTE_AMENDMENT_SCOPE
                or approval.get("required_minutes") != 10
            ):
                raise ValueError("时长调整须明确授权仅 S06 10分钟")
        if value["active_baseline_epoch"] != expected_epoch or len(value["baseline_epochs"]) != expected_epoch:
            raise RuntimeError("final batch 已登记，最多只允许两个 baseline epoch")
        if not value["attempts"]:
            raise RuntimeError("initial batch 尚无 attempt，禁止提前 advance")
        previous = value["baseline_epochs"][-1]
        if expected_epoch == 5 and (
            len(value["attempts"]) != 15
            or any(a["attempt_kind"] == "s06_start_session" for a in value["attempts"])
            or previous["baseline"] != baseline_snapshot
        ):
            raise ValueError("时长调整须保留原 Provider/草稿基线，且第16次 S06 尚未登记")
        if (
            previous["matrix_sha256"] == matrix_sha256
            and previous["runtime_manifest_sha256"] == runtime_manifest_sha256
            and previous["baseline"] == baseline_snapshot
        ):
            raise ValueError("final batch 必须登记新的冻结 baseline")
        value["baseline_epochs"].append(
            _new_baseline_epoch(
                baseline_epoch=expected_epoch + 1,
                matrix_sha256=matrix_sha256,
                runtime_manifest_sha256=runtime_manifest_sha256,
                baseline=baseline_snapshot,
                regression_evidence=regression_evidence,
                registered_at=(now or (lambda: datetime.now(timezone.utc)))(),
                previous_epoch_sha256=previous["epoch_sha256"],
            )
        )
        value["active_baseline_epoch"] = expected_epoch + 1
        if M1_CANCEL_RETRY_PROFILE:
            value["max_provider_attempts"] = 6
        if expected_epoch in (3, 4, 5):
            value["max_provider_attempts"] = _attempt_limit_for_epoch(expected_epoch + 1)
        _validate_attempt_ledger(value)
        _atomic_write_ledger(ledger, value)
        return {
            "schema_version": FINAL_BATCH_RECEIPT_SCHEMA,
            "campaign_id": campaign_id,
            "active_baseline_epoch": expected_epoch + 1,
            "remaining_attempts": value["max_provider_attempts"] - len(value["attempts"]),
        }
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _expected_attempt_reservation(
    *,
    campaign_id: str,
    epoch: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_RECEIPT_SCHEMA,
        "campaign_id": campaign_id,
        "matrix_sha256": epoch["matrix_sha256"],
        "runtime_manifest_sha256": epoch["runtime_manifest_sha256"],
        "baseline_epoch": attempt["baseline_epoch"],
        "attempt_id": attempt["attempt_id"],
        "attempt_ordinal": attempt["attempt_ordinal"],
        "attempt_kind": attempt["attempt_kind"],
        "reserved_at": attempt["reserved_at"],
    }


def load_active_reserved_attempt(
    *,
    frozen: FrozenCampaign,
    baseline: Mapping[str, Any],
    attempt_kind: str,
    attempt_ordinal: int,
) -> dict[str, Any]:
    """Validate the active epoch and return one still-unconsumed direct receipt."""

    baseline_snapshot = _validate_campaign_baseline(dict(baseline))
    if attempt_kind not in DIRECT_PHASE0_ATTEMPT_KINDS:
        raise ValueError("serve-direct attempt kind 非法")
    if type(attempt_ordinal) is not int or not 1 <= attempt_ordinal <= AUTHORIZED_FIFTH_ROUND_LIMIT:
        raise ValueError("serve-direct attempt ordinal 非法")
    ledger = frozen.ledger_path
    lock_path = ledger.with_name(ledger.name + ".lock")
    lock_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(lock_path, lock_flags)
    except OSError:
        raise RuntimeError("campaign ledger lock 不存在") from None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        value = _read_attempt_ledger(ledger)
        if value is None or value["campaign_id"] != frozen.campaign_id:
            raise RuntimeError("campaign ledger 不存在")
        epoch = value["baseline_epochs"][value["active_baseline_epoch"] - 1]
        if (
            epoch["matrix_sha256"] != frozen.matrix_sha256
            or epoch["runtime_manifest_sha256"] != frozen.runtime_manifest_sha256
            or epoch["baseline"] != baseline_snapshot
        ):
            raise ValueError("serve-direct 当前 baseline 与 active epoch 漂移")
        matches = [
            attempt
            for attempt in value["attempts"]
            if attempt["attempt_ordinal"] == attempt_ordinal
            and attempt["baseline_epoch"] == value["active_baseline_epoch"]
            and attempt["attempt_kind"] == attempt_kind
        ]
        if len(matches) != 1:
            raise RuntimeError("serve-direct 找不到 active reserved attempt")
        attempt = matches[0]
        reserved_path = (
            ledger.parent
            / "attempt-reservations"
            / f"{attempt['attempt_id']}.reserved.json"
        )
        try:
            reservation = json.loads(reserved_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise RuntimeError("serve-direct reserved attempt 不可用") from None
        if reservation != _expected_attempt_reservation(
            campaign_id=frozen.campaign_id,
            epoch=epoch,
            attempt=attempt,
        ):
            raise RuntimeError("serve-direct reserved attempt 绑定非法")
        return deepcopy(attempt)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("evidence tested_at 非法")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("evidence tested_at 必须带时区")
    return parsed.astimezone(timezone.utc)


def _require_uuid(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} 非法")
    uuid.UUID(value)
    return value


def validate_phase0_draft(draft_snapshot: Mapping[str, Any]) -> None:
    """Reject a draft that does not describe the isolated Phase0 implementation."""

    if not isinstance(draft_snapshot, Mapping):
        raise ValueError("draft 非法")
    s2s = draft_snapshot.get("s2s")
    voice = draft_snapshot.get("voice")
    if not isinstance(s2s, Mapping) or not isinstance(voice, Mapping):
        raise ValueError("draft 缺少 s2s/voice")
    expected = {
        "provider": "doubao",
        "protocol_profile": PHASE0_PROTOCOL_PROFILE,
        "adapter_version": PHASE0_ADAPTER_VERSION,
    }
    if any(s2s.get(key) != value for key, value in expected.items()):
        raise ValueError("draft 与 Phase0 provider/protocol/adapter 不一致")
    for field in ("endpoint", "resource_id", "model_version"):
        if not isinstance(s2s.get(field), str) or not str(s2s[field]).strip():
            raise ValueError(f"draft s2s.{field} 非法")
    endpoint = str(s2s["endpoint"])
    if not endpoint.startswith("wss://"):
        raise ValueError("draft s2s.endpoint 必须为 wss")
    if not isinstance(voice.get("voice_id"), str) or not voice["voice_id"].strip():
        raise ValueError("draft voice.voice_id 非法")


def convert_phase0_ack_record(
    record: Mapping[str, Any],
    *,
    draft_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert only one freshly finalized Phase0 ACK record to the admin source."""

    if not isinstance(record, Mapping) or set(record) != _RECORD_FIELDS:
        raise ValueError("Phase0 record 键集非法")
    if record.get("source_type") != "phase0_import":
        raise ValueError("Phase0 record source 非法")
    if record.get("capability_key") != ACK_CAPABILITY_KEY:
        raise ValueError("campaign 只接受 sentence playback ACK")
    if record.get("verification_result") not in {"passed", "failed"}:
        raise ValueError("ACK 尚未形成可信 passed/failed")
    payload = record.get("evidence_payload")
    expected_fields = _PAYLOAD_FIELDS | ({'protocol_evidence'} if M1_PROTOCOL_PROFILE else set())
    if not isinstance(payload, Mapping) or set(payload) != expected_fields:
        raise ValueError("Phase0 evidence payload 键集非法")
    if M1_PROTOCOL_PROFILE and payload.get('schema_version') != 'phase0-capability-evidence/v5':
        raise ValueError('M1 专项需要 v5 payload')
    if payload.get("capability_status") not in {"verified", "failed"}:
        raise ValueError("Phase0 ACK 状态尚未收口")
    validate_phase0_draft(draft_snapshot)
    try:
        sdk_version = f"websockets-{metadata.version('websockets')}"
    except metadata.PackageNotFoundError:
        sdk_version = "websockets-unknown"
    expected_dimensions = {
        "provider_profile": PHASE0_PROVIDER_PROFILE,
        "model_version": str(draft_snapshot["s2s"]["model_version"]),
        "protocol_profile": PHASE0_PROTOCOL_PROFILE,
        "adapter_version": PHASE0_ADAPTER_VERSION,
        "sdk_version": sdk_version,
        "evidence_suite_version": PHASE0_EVIDENCE_SUITE_VERSION,
    }
    if any(record.get(key) != value for key, value in expected_dimensions.items()):
        raise ValueError("Phase0 record 与冻结 draft/P0 六维不一致")

    converted = deepcopy(dict(record))
    converted["source_type"] = "admin_capability_test"
    converted_payload = deepcopy(dict(payload))
    converted_payload["runtime_conditions"] = {
        "real_provider": True,
        "network_profile": CAMPAIGN_NETWORK_PROFILE,
    }
    # This diagnostic bit is never an authorization input.  Keep it false so
    # the campaign output cannot be mistaken for a Phase0 bundle import.
    converted_payload["production_import_ready"] = False
    converted["evidence_payload"] = converted_payload
    converted_without_hash = {
        key: value for key, value in converted.items() if key != "report_sha256"
    }
    converted["report_sha256"] = _canonical_sha256(converted_without_hash)
    return converted


def _normalized_result(category: str, *, tested_at: datetime) -> dict[str, Any]:
    return {
        "status": "error",
        "latency_ms": None,
        "failure_category": category,
        "tested_at": tested_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
    }


class CampaignVoiceTestRunner:
    """One-request runner; a new isolated Phase0 worker is mandatory."""

    def __init__(
        self,
        *,
        worker_factory: Callable[..., CampaignWorkerPort],
        validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        read_session_id: Callable[[], Any],
        registry: ConsumedEvidenceRegistry,
        user_id: int,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        user_window_seconds: float = DEFAULT_USER_WINDOW_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._worker_factory = worker_factory
        self._validator = validator
        self._read_session_id = read_session_id
        self._registry = registry
        self._user_id = user_id
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._user_window_seconds = user_window_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._worker: CampaignWorkerPort | None = None
        self._session_id: str | None = None
        self._used = False

    def __repr__(self) -> str:
        return "CampaignVoiceTestRunner(redacted=True)"

    async def _new_worker(
        self,
        *,
        draft_snapshot: Mapping[str, Any],
        secret: str,
    ) -> CampaignWorkerPort:
        if self._used or self._worker is not None:
            raise RuntimeError("campaign runner 为单次使用")
        validate_phase0_draft(draft_snapshot)
        self._used = True
        worker = self._worker_factory(
            draft_snapshot=deepcopy(dict(draft_snapshot)),
            secret=secret,
        )
        self._worker = worker
        await worker.start()
        return worker

    async def run_connection(
        self,
        *,
        draft_snapshot: Mapping[str, Any],
        secret: str,
    ) -> Mapping[str, Any]:
        started_at = self._now().astimezone(timezone.utc)
        started_clock = self._monotonic()
        try:
            worker = await self._new_worker(
                draft_snapshot=draft_snapshot,
                secret=secret,
            )
            created = await worker.create_connection_session(user_id=self._user_id)
            self._session_id = _require_uuid(
                created.get("session_id"),
                field="session_id",
            )
            await worker.end_session(self._session_id)
            self._session_id = None
            return {
                "status": "passed",
                "latency_ms": max(
                    0,
                    int((self._monotonic() - started_clock) * 1000),
                ),
                "failure_category": "none",
                "tested_at": started_at.isoformat().replace("+00:00", "Z"),
            }
        except asyncio.CancelledError:
            raise
        except ValueError:
            return _normalized_result("invalid_config", tested_at=started_at)
        except TimeoutError:
            return _normalized_result("timeout", tested_at=started_at)
        except Exception:
            return _normalized_result("upstream_unavailable", tested_at=started_at)

    async def _read_session(self) -> str:
        value = self._read_session_id()
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, str):
            raise ValueError("session_id 非法")
        return _require_uuid(value.strip(), field="session_id")

    @staticmethod
    def _target_record(bundle: Mapping[str, Any]) -> Mapping[str, Any] | None:
        records = bundle.get("records") if isinstance(bundle, Mapping) else None
        if not isinstance(records, list):
            return None
        matches = [
            record
            for record in records
            if isinstance(record, Mapping)
            and record.get("capability_key") == ACK_CAPABILITY_KEY
        ]
        return matches[0] if len(matches) == 1 else None

    def _assert_fresh(
        self,
        *,
        record: Mapping[str, Any],
        session_run_id: str,
        attempt_started_at: datetime,
    ) -> tuple[str, str]:
        run_id = _require_uuid(record.get("evidence_run_id"), field="evidence_run_id")
        report_id = _require_uuid(
            record.get("evidence_report_id"),
            field="evidence_report_id",
        )
        if run_id != session_run_id:
            raise ValueError("session/run UUID 不一致")
        if _parse_utc(record.get("tested_at")) < attempt_started_at:
            raise ValueError("拒绝调用开始前生成的 evidence")
        if self._registry.contains(run_id, report_id):
            raise ValueError("拒绝已消费 evidence")
        return run_id, report_id

    async def run_capability(
        self,
        *,
        capability_key: str,
        draft_snapshot: Mapping[str, Any],
        secret: str,
    ) -> Mapping[str, Any]:
        attempt_started_at = self._now().astimezone(timezone.utc)
        started_clock = self._monotonic()
        if capability_key != ACK_CAPABILITY_KEY:
            return _normalized_result("invalid_config", tested_at=attempt_started_at)
        try:
            worker = await self._new_worker(
                draft_snapshot=draft_snapshot,
                secret=secret,
            )
            async with asyncio.timeout(self._user_window_seconds):
                self._session_id = await self._read_session()
                session = await worker.get_session(self._session_id)
                session_run_id = _require_uuid(
                    session.get("evidence_run_id"),
                    field="session.evidence_run_id",
                )
                live_record: Mapping[str, Any] | None = None
                while live_record is None:
                    candidate = self._target_record(
                        await worker.fetch_evidence(self._session_id)
                    )
                    if candidate is not None and candidate.get(
                        "verification_result"
                    ) in {"passed", "failed"}:
                        self._assert_fresh(
                            record=candidate,
                            session_run_id=session_run_id,
                            attempt_started_at=attempt_started_at,
                        )
                        live_record = candidate
                        break
                    await asyncio.sleep(self._poll_interval_seconds)

            # Freeze the Provider timeline before exporting the record that can
            # reach MySQL.  Late/terminal frames therefore cannot mutate the
            # causal window after validation.
            await worker.end_session(self._session_id)
            self._session_id = None
            final_record = self._target_record(
                await worker.fetch_evidence(
                    _require_uuid(session.get("session_id"), field="session.session_id")
                )
            )
            if final_record is None:
                raise ValueError("final ACK evidence 缺失")
            run_id, report_id = self._assert_fresh(
                record=final_record,
                session_run_id=session_run_id,
                attempt_started_at=attempt_started_at,
            )
            if (
                live_record is None
                or live_record.get("evidence_run_id") != run_id
                or live_record.get("evidence_report_id") != report_id
                or final_record.get("verification_result") not in {"passed", "failed"}
            ):
                raise ValueError("final ACK evidence 与 live window 不一致")
            converted = convert_phase0_ack_record(
                final_record,
                draft_snapshot=draft_snapshot,
            )
            validated = deepcopy(dict(self._validator(converted)))
            self._registry.consume(run_id, report_id)
            status = str(validated["verification_result"])
            return {
                "status": status,
                "latency_ms": max(
                    0,
                    int((self._monotonic() - started_clock) * 1000),
                ),
                "failure_category": "none" if status == "passed" else "protocol_error",
                "tested_at": validated["tested_at"],
                "evidence_record": validated,
            }
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return _normalized_result("timeout", tested_at=attempt_started_at)
        except ValueError:
            return _normalized_result("evidence_invalid", tested_at=attempt_started_at)
        except Exception:
            return _normalized_result("upstream_unavailable", tested_at=attempt_started_at)

    async def aclose(self) -> None:
        worker = self._worker
        if worker is None:
            return
        try:
            if self._session_id is not None:
                try:
                    await worker.end_session(self._session_id)
                finally:
                    self._session_id = None
        finally:
            await worker.stop()
            self._worker = None


@contextmanager
def campaign_runner_override(app: Any, dependency: Any, factory: Callable[[], Any]):
    """Override exactly the runner dependency and restore prior app state."""

    overrides = app.dependency_overrides
    sentinel = object()
    previous = overrides.get(dependency, sentinel)
    overrides[dependency] = factory
    try:
        yield
    finally:
        if previous is sentinel:
            overrides.pop(dependency, None)
        else:
            overrides[dependency] = previous


async def call_admin_test_route(
    *,
    app: Any,
    runner_dependency: Any,
    runner_factory: Callable[[], Any] | None,
    jwt: str,
    mode: str,
    http_client: Any,
    request_timeout_seconds: float = CAMPAIGN_ROUTE_DEADLINE_SECONDS,
) -> Mapping[str, Any]:
    if mode == "connection":
        path = "/api/admin/voice/config/test-connection"
        body: dict[str, Any] = {}
    elif mode == "ack":
        path = "/api/admin/voice/config/test-capability"
        body = {"capability_key": ACK_CAPABILITY_KEY}
    else:
        raise ValueError("campaign mode 非法")
    override_scope = (
        campaign_runner_override(app, runner_dependency, runner_factory)
        if runner_factory is not None
        else nullcontext()
    )
    with override_scope:
        try:
            async with asyncio.timeout(request_timeout_seconds):
                response = await http_client.post(
                    path,
                    json=body,
                    headers={"Authorization": f"Bearer {jwt}"},
                )
            response.raise_for_status()
            payload = response.json()
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("admin route 调用失败") from None
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise RuntimeError("admin route 返回非成功状态")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise RuntimeError("admin route 返回结构非法")
    return payload


def assert_campaign_state_unchanged(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    if before != after:
        raise RuntimeError("campaign 测试改变了 active/Redis 状态")


def assert_campaign_state_transition(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    mode: str,
    route_result: Mapping[str, Any],
) -> None:
    status = route_result.get("status")
    if mode == "ack" and status == "error" and any(
        route_result.get(field) is not None
        for field in ("evidence_run_id", "evidence_report_id")
    ):
        raise RuntimeError("ADM-ACK error 回执禁止携带 evidence 标识")
    if mode == "ack" and status == "error":
        if before != after:
            raise RuntimeError("ADM-ACK error 产生非预期配置/证据/Redis 变化")
        return
    if mode != "ack":
        assert_campaign_state_unchanged(before, after)
        return
    if status not in {"passed", "failed"}:
        raise RuntimeError("campaign route 状态非法")
    immutable_fields = ("database", "active_rows", "redis")
    if any(before.get(field) != after.get(field) for field in immutable_fields):
        raise RuntimeError("campaign 测试改变了 active/Redis 状态")

    before_evidence = {row["id"]: row for row in before.get("evidence_rows", [])}
    after_evidence = {row["id"]: row for row in after.get("evidence_rows", [])}
    if any(after_evidence.get(key) != value for key, value in before_evidence.items()):
        raise RuntimeError("ADM-ACK 改写既有 evidence")
    new_evidence_ids = set(after_evidence) - set(before_evidence)
    if len(new_evidence_ids) != 1:
        raise RuntimeError("ADM-ACK 必须且只能新增一条 evidence")
    new_evidence = after_evidence[new_evidence_ids.pop()]
    expected_evidence = {
        "evidence_report_id": route_result.get("evidence_report_id"),
        "evidence_run_id": route_result.get("evidence_run_id"),
        "capability_key": ACK_CAPABILITY_KEY,
        "verification_result": status,
        "source_type": "admin_capability_test",
    }
    if any(new_evidence.get(key) != value for key, value in expected_evidence.items()):
        raise RuntimeError("ADM-ACK evidence 与路由回执不匹配")

    before_configs = {row["id"]: row for row in before.get("config_rows", [])}
    after_configs = {row["id"]: row for row in after.get("config_rows", [])}
    if set(before_configs) != set(after_configs):
        raise RuntimeError("ADM-ACK 配置行集合发生变化")
    changed_ids = [
        row_id
        for row_id in before_configs
        if before_configs[row_id] != after_configs[row_id]
    ]
    if len(changed_ids) != 1:
        raise RuntimeError("ADM-ACK 必须且只能推进目标 voice draft")
    previous = before_configs[changed_ids[0]]
    current = after_configs[changed_ids[0]]
    stable_fields = ("id", "config_key", "version", "is_draft", "is_active")
    if (
        any(previous.get(field) != current.get(field) for field in stable_fields)
        or current.get("config_key") != "voice_call_config"
        or current.get("is_draft") is not True
        or current.get("is_active") is not False
        or type(previous.get("draft_revision")) is not int
        or current.get("draft_revision") != previous["draft_revision"] + 1
    ):
        raise RuntimeError("ADM-ACK 目标 voice draft 元数据变化非法")
    previous_content = deepcopy(previous.get("content"))
    current_content = deepcopy(current.get("content"))
    if not isinstance(previous_content, dict) or not isinstance(current_content, dict):
        raise RuntimeError("ADM-ACK voice draft 内容非法")
    previous_capabilities = previous_content.get("capabilities")
    current_capabilities = current_content.get("capabilities")
    if not isinstance(previous_capabilities, dict) or not isinstance(
        current_capabilities, dict
    ):
        raise RuntimeError("ADM-ACK capabilities 非法")
    previous_ack = previous_capabilities.get(ACK_CAPABILITY_KEY)
    current_ack = current_capabilities.get(ACK_CAPABILITY_KEY)
    previous_capabilities[ACK_CAPABILITY_KEY] = None
    current_capabilities[ACK_CAPABILITY_KEY] = None
    if previous_content != current_content:
        raise RuntimeError("ADM-ACK 改变了目标 ACK 以外的配置/能力")
    from backend.services.realtime_voice_capability_service import (
        _project_record_to_capability,
    )

    if not isinstance(previous_ack, dict) or not isinstance(current_ack, dict):
        raise RuntimeError("ADM-ACK capability 投影与 evidence 不匹配")
    try:
        expected_ack = _project_record_to_capability(previous_ack, new_evidence)
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("ADM-ACK evidence 无法形成生产 projection") from None
    if current_ack != expected_ack:
        raise RuntimeError("ADM-ACK capability projection 与 evidence 不匹配")


def validate_campaign_environment(
    environ: Mapping[str, str],
    *,
    require_external_jwt: bool = True,
) -> None:
    database_name = str(environ.get("MYSQL_DATABASE", ""))
    if database_name != CAMPAIGN_DATABASE_NAME:
        raise ValueError(f"MYSQL_DATABASE 必须为 {CAMPAIGN_DATABASE_NAME}")
    if str(environ.get("REDIS_DB", "")) != CAMPAIGN_REDIS_DB:
        raise ValueError(f"REDIS_DB 必须为 {CAMPAIGN_REDIS_DB}")
    if require_external_jwt and not str(
        environ.get("REALTIME_VOICE_M1_ADMIN_JWT", "")
    ).strip():
        raise ValueError("REALTIME_VOICE_M1_ADMIN_JWT 必须由真实管理员登录签发")


async def preflight_campaign_dependencies(
    *,
    session_maker: Callable[[], Any] | None = None,
    redis_getter: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Read-only proof of the exact campaign schema and selected Redis DB."""

    from sqlalchemy import text

    if session_maker is None:
        from backend.database import async_session_maker

        session_maker = async_session_maker
    if redis_getter is None:
        from backend.redis_client import get_redis

        redis_getter = get_redis

    async with session_maker() as db:
        database_name = str(await db.scalar(text("SELECT DATABASE()")) or "")
        revision = str(
            await db.scalar(text("SELECT version_num FROM alembic_version")) or ""
        )
        result = await db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
        )
        tables = {str(value) for value in result.scalars().all()}
    if database_name != CAMPAIGN_DATABASE_NAME:
        raise RuntimeError("实际 MySQL 未连接 campaign 隔离库")
    if revision != CAMPAIGN_ALEMBIC_REVISION:
        raise RuntimeError("campaign Alembic revision 非 v8c")
    missing = CAMPAIGN_REQUIRED_TABLES - tables
    if missing:
        raise RuntimeError("campaign 必需表缺失")

    redis = redis_getter()
    if inspect.isawaitable(redis):
        redis = await redis
    if await redis.ping() is not True:
        raise RuntimeError("campaign Redis ping 失败")
    info = await redis.client_info()
    try:
        selected_db = int(info["db"])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("campaign Redis DB 无法核实") from None
    if selected_db != int(CAMPAIGN_REDIS_DB):
        raise RuntimeError("实际 Redis 未选择 DB15")
    return {
        "database": database_name,
        "alembic_revision": revision,
        "required_table_count": len(CAMPAIGN_REQUIRED_TABLES),
        "redis_db": selected_db,
    }


def _phase0_business_coordinates(project_env_path: Path) -> tuple[str, str]:
    values = _dotenv_allowlisted(
        project_env_path,
        {"MYSQL_DATABASE", "REDIS_DB"},
    )
    database_name = str(values.get("MYSQL_DATABASE") or "")
    redis_db = str(values.get("REDIS_DB") or "")
    if not database_name or not redis_db:
        raise ValueError("项目根 .env 缺少 Phase0 MySQL/Redis 坐标")
    if database_name == CAMPAIGN_DATABASE_NAME or redis_db == CAMPAIGN_REDIS_DB:
        raise ValueError("Phase0 child 禁止使用 campaign MySQL/Redis")
    return database_name, redis_db


def _build_campaign_voice_draft(
    *,
    persona_ref: Mapping[str, Any],
    public_settings: Mapping[str, str],
) -> dict[str, Any]:
    from backend.constants.realtime_voice_config import (
        VOICE_CALL_CONFIG_KEY,
        build_canonical_voice_seed_manifest,
    )

    voice_draft = build_canonical_voice_seed_manifest(persona_ref)[
        VOICE_CALL_CONFIG_KEY
    ]
    voice_draft["s2s"].update(
        {
            "credential_ref": CAMPAIGN_CREDENTIAL_REF,
            "endpoint": public_settings["endpoint"],
            "resource_id": public_settings["resource_id"],
            "model_version": public_settings["model_version"],
            "protocol_profile": PHASE0_PROTOCOL_PROFILE,
            "adapter_version": PHASE0_ADAPTER_VERSION,
        }
    )
    voice_draft["voice"]["voice_id"] = public_settings["voice_id"]
    candidate_ids = {
        candidate.get("voice_id")
        for candidate in voice_draft["voice"]["candidates"]
        if isinstance(candidate, Mapping)
    }
    if public_settings["voice_id"] not in candidate_ids:
        voice_draft["voice"]["candidates"].append(
            {
                "voice_id": public_settings["voice_id"],
                "voice_version": "phase0-v1",
                "enabled": True,
            }
        )
    validate_phase0_draft(voice_draft)
    _assert_draft_public_settings(voice_draft, public_settings)
    return voice_draft


def _hash_campaign_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def validate_existing_campaign_draft(
    existing: Mapping[str, Any],
    *,
    expected_base: Mapping[str, Any],
) -> None:
    """Allow only server-owned, production-valid capability projection evolution."""

    from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY
    from backend.services.realtime_voice_config_service import (
        validate_trusted_voice_bundle,
    )

    validate_phase0_draft(existing)
    issues = validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, existing)
    if issues:
        raise ValueError("campaign draft capabilities 非生产合法状态")
    existing_static = deepcopy(dict(existing))
    expected_static = deepcopy(dict(expected_base))
    existing_static.pop("capabilities", None)
    expected_static.pop("capabilities", None)
    if existing_static != expected_static:
        raise ValueError("campaign draft 发生非 capability 漂移")


async def load_current_campaign_voice_draft() -> dict[str, Any]:
    """Read the one mutable campaign voice draft used by the next attempt."""

    from sqlalchemy import select

    from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY
    from backend.database import async_session_maker
    from backend.models.admin_config import AdminConfig

    async with async_session_maker() as db:
        rows = (
            await db.execute(
                select(AdminConfig.config_value)
                .where(
                    AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                    AdminConfig.is_draft.is_(True),
                    AdminConfig.is_active.is_(False),
                )
                .order_by(AdminConfig.id.desc())
            )
        ).scalars().all()
    if len(rows) != 1:
        raise RuntimeError("campaign voice draft 数量异常")
    try:
        draft = json.loads(str(rows[0]))
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError("campaign voice draft JSON 非法") from None
    validate_phase0_draft(draft)
    return draft


async def capture_current_campaign_baseline(
    *,
    project_env_path: Path,
    phase0_root: Path,
    draft_loader: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Recompute every mutable runtime fact immediately before a reservation."""

    public_settings = load_phase0_public_provider_settings(
        project_env_path=project_env_path,
        phase0_root=phase0_root,
    )
    loaded = (draft_loader or load_current_campaign_voice_draft)()
    voice_draft = await loaded if inspect.isawaitable(loaded) else loaded
    if not isinstance(voice_draft, Mapping):
        raise RuntimeError("campaign voice draft 非法")
    return build_campaign_baseline_snapshot(
        public_settings=public_settings,
        voice_draft=voice_draft,
    )


async def _seed_campaign_database(
    *,
    username: str,
    password_hash: str,
    persona_value: str,
    voice_draft: Mapping[str, Any],
) -> None:
    from sqlalchemy import select

    from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY
    from backend.database import async_session_maker
    from backend.models.admin_config import AdminConfig
    from backend.models.admin_user import AdminUser

    persona_value = json.dumps(
        json.loads(persona_value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    validate_phase0_draft(voice_draft)

    async with async_session_maker() as db:
        async with db.begin():
            admin = (
                await db.execute(
                    select(AdminUser)
                    .where(AdminUser.username == username)
                    .with_for_update()
                )
            ).scalars().first()
            if admin is None:
                admin = AdminUser(
                    username=username,
                    password_hash=password_hash,
                    role="super_admin",
                    remark="M1 campaign-only temporary administrator",
                    is_active=True,
                    is_locked=False,
                    login_fail_count=0,
                    token_version=0,
                    created_by="m1-campaign-harness",
                )
                db.add(admin)
            else:
                if admin.role != "super_admin":
                    raise RuntimeError("campaign 管理员角色异常")
                admin.password_hash = password_hash
                admin.is_active = True
                admin.is_locked = False
                admin.login_fail_count = 0
                admin.token_version += 1

            persona_rows = (
                await db.execute(
                    select(AdminConfig)
                    .where(AdminConfig.config_key == "persona")
                    .with_for_update()
                )
            ).scalars().all()
            if not persona_rows:
                db.add(
                    AdminConfig(
                        config_key="persona",
                        config_value=persona_value,
                        version=1,
                        is_draft=False,
                        is_active=True,
                        updated_by=username,
                    )
                )
            elif not any(
                row.is_active
                and not row.is_draft
                and row.version == 1
                and row.config_value == persona_value
                for row in persona_rows
            ):
                raise RuntimeError("campaign persona 已存在非 harness 数据")

            drafts = (
                await db.execute(
                    select(AdminConfig)
                    .where(
                        AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                        AdminConfig.is_draft.is_(True),
                        AdminConfig.is_active.is_(False),
                    )
                    .order_by(AdminConfig.id.desc())
                    .with_for_update()
                )
            ).scalars().all()
            if not drafts:
                db.add(
                    AdminConfig(
                        config_key=VOICE_CALL_CONFIG_KEY,
                        config_value=json.dumps(
                            voice_draft,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        version=0,
                        draft_revision=1,
                        is_draft=True,
                        is_active=False,
                        updated_by=username,
                    )
                )
            elif len(drafts) != 1:
                raise RuntimeError("campaign voice draft 数量异常")
            else:
                try:
                    existing = json.loads(str(drafts[0].config_value))
                    validate_existing_campaign_draft(
                        existing,
                        expected_base=voice_draft,
                    )
                except Exception:
                    raise RuntimeError("campaign voice draft 非 Phase0 冻结配置") from None


async def bootstrap_campaign_prerequisites(
    *,
    project_env_path: Path,
    phase0_root: Path,
    seed_database: Callable[..., Any] | None = None,
    password_factory: Callable[[], str] | None = None,
    password_hasher: Callable[[str], str] | None = None,
) -> tuple[str, str]:
    """Seed the isolated DB from public project/Phase0 facts; return memory credentials."""

    public_settings = load_phase0_public_provider_settings(
        project_env_path=project_env_path,
        phase0_root=phase0_root,
    )
    persona_value = json.dumps(
        {"background": "M1 campaign isolated persona", "personality": "stable"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    persona_sha = "sha256:" + hashlib.sha256(
        persona_value.encode("utf-8")
    ).hexdigest()
    voice_draft = _build_campaign_voice_draft(
        persona_ref={
            "config_key": "persona",
            "version": 1,
            "content_sha256": persona_sha,
        },
        public_settings=public_settings,
    )
    username = "m1_campaign_admin"
    password = (password_factory or (lambda: "M1!" + secrets.token_urlsafe(32)))()
    if not isinstance(password, str) or not password:
        raise ValueError("campaign 临时密码生成失败")
    password_hash = (password_hasher or _hash_campaign_password)(password)
    if not isinstance(password_hash, str) or not password_hash:
        raise ValueError("campaign 临时密码哈希失败")
    seeder = seed_database or _seed_campaign_database
    seeded = seeder(
        username=username,
        password_hash=password_hash,
        persona_value=persona_value,
        voice_draft=deepcopy(voice_draft),
    )
    if inspect.isawaitable(seeded):
        await seeded
    return username, password


async def login_campaign_admin(http_client: Any, username: str, password: str) -> str:
    try:
        response = await http_client.post(
            "/api/admin/auth/login",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        payload = response.json()
    except asyncio.CancelledError:
        raise
    except Exception:
        raise RuntimeError("campaign 管理员真实登录失败") from None
    data = payload.get("data") if isinstance(payload, Mapping) else None
    token = data.get("token") if isinstance(data, Mapping) else None
    if payload.get("code") != 0 or not isinstance(token, str) or not token:
        raise RuntimeError("campaign 管理员真实登录失败")
    return token


async def probe_campaign_admin_auth(http_client: Any, jwt: str) -> None:
    """Exercise real JWT, live account state, role gate and a read-only DB route."""

    try:
        response = await http_client.get(
            "/api/admin/voice/config/config",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        response.raise_for_status()
        payload = response.json()
    except asyncio.CancelledError:
        raise
    except Exception:
        raise RuntimeError("campaign 管理员认证探针失败") from None
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise RuntimeError("campaign 管理员认证探针失败")


@contextmanager
def project_provider_secret_scope(project_env_path: Path):
    """Temporarily expose only the named credential to the production resolver."""

    values = _dotenv_allowlisted(
        Path(project_env_path).resolve(),
        {CAMPAIGN_CREDENTIAL_REF},
    )
    secret_value = values.get(CAMPAIGN_CREDENTIAL_REF)
    values.clear()
    if not isinstance(secret_value, str) or not secret_value:
        raise ValueError("项目根 .env 缺少 campaign Provider credential")
    sentinel = object()
    previous: object | str = os.environ.get(CAMPAIGN_CREDENTIAL_REF, sentinel)
    os.environ[CAMPAIGN_CREDENTIAL_REF] = secret_value
    try:
        yield
    finally:
        if previous is sentinel:
            os.environ.pop(CAMPAIGN_CREDENTIAL_REF, None)
        else:
            os.environ[CAMPAIGN_CREDENTIAL_REF] = str(previous)
        secret_value = ""


@contextmanager
def no_provider_canary_secret_scope():
    """Satisfy credential preflight without reading or dispatching a real secret."""

    sentinel = object()
    previous: object | str = os.environ.get(CAMPAIGN_CREDENTIAL_REF, sentinel)
    canary = "m1-no-provider-canary-" + secrets.token_urlsafe(16)
    os.environ[CAMPAIGN_CREDENTIAL_REF] = canary
    try:
        yield
    finally:
        if previous is sentinel:
            os.environ.pop(CAMPAIGN_CREDENTIAL_REF, None)
        else:
            os.environ[CAMPAIGN_CREDENTIAL_REF] = str(previous)
        canary = ""


def _snapshot_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("campaign snapshot 时间非法")
    if value.tzinfo is not None and value.utcoffset() is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def snapshot_admin_config_rows(rows: Any) -> list[dict[str, Any]]:
    """Snapshot every config row while retaining plaintext only for the target draft."""

    snapshots: list[dict[str, Any]] = []
    for row in rows:
        raw_value = row.config_value
        value_kind = "null" if raw_value is None else "text"
        raw_content = "" if raw_value is None else str(raw_value)
        content: Any = None
        if str(row.config_key) == "voice_call_config" and raw_value is not None:
            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = None
        snapshots.append(
            {
                "id": int(row.id),
                "config_key": str(row.config_key),
                "version": int(row.version),
                "draft_revision": row.draft_revision,
                "is_draft": bool(row.is_draft),
                "is_active": bool(row.is_active),
                "updated_by": row.updated_by,
                "updated_at": _snapshot_datetime(row.updated_at),
                "value_kind": value_kind,
                "content_sha256": hashlib.sha256(
                    (value_kind + "\0" + raw_content).encode("utf-8")
                ).hexdigest(),
                "content": content,
            }
        )
    return snapshots


async def capture_campaign_state() -> dict[str, Any]:
    """Capture config/evidence plus Redis facts, excluding expected audit/login writes."""

    from sqlalchemy import select, text

    from backend.database import async_session_maker
    from backend.models.admin_config import AdminConfig
    from backend.models.realtime_voice import VoiceCapabilityEvidence
    from backend.services.realtime_voice_capability_service import (
        _stored_record_projection,
    )

    async with async_session_maker() as db:
        database_name = str(await db.scalar(text("SELECT DATABASE()")) or "")
        if database_name != CAMPAIGN_DATABASE_NAME:
            raise RuntimeError("实际 MySQL 未连接 campaign 隔离库")
        result = await db.execute(
            select(AdminConfig).order_by(AdminConfig.config_key, AdminConfig.id)
        )
        config_rows = snapshot_admin_config_rows(result.scalars().all())
        active_rows = [
            deepcopy(row)
            for row in config_rows
            if row["is_active"] is True and row["is_draft"] is False
        ]
        evidence_result = await db.execute(
            select(VoiceCapabilityEvidence).order_by(VoiceCapabilityEvidence.id)
        )
        evidence_rows = [
            {
                "id": int(row.id),
                **_stored_record_projection(row),
                "operator_id": row.operator_id,
                "created_at": _snapshot_datetime(row.created_at),
            }
            for row in evidence_result.scalars().all()
        ]

    import redis.asyncio as aioredis

    from backend.config import get_redis_url

    redis = aioredis.from_url(get_redis_url(), decode_responses=False)
    try:
        redis_state = await capture_redis_dump_state(redis)
    finally:
        await redis.close()
    return {
        "database": database_name,
        "active_rows": active_rows,
        "config_rows": config_rows,
        "evidence_rows": evidence_rows,
        "redis": redis_state,
    }


async def capture_redis_dump_state(
    redis: Any,
) -> dict[str, tuple[str, str | None, str]]:
    """Hash Redis DUMP bytes, so strings and arbitrary container types are covered."""

    state: dict[str, tuple[str, str | None, str]] = {}
    async for raw_key in redis.scan_iter(match="*"):
        key_bytes = raw_key if isinstance(raw_key, bytes) else str(raw_key).encode("utf-8")
        raw_type = await redis.type(raw_key)
        value_type = (
            raw_type.decode("ascii", "strict")
            if isinstance(raw_type, bytes)
            else str(raw_type)
        )
        dumped = await redis.dump(raw_key)
        if dumped is not None and not isinstance(dumped, bytes):
            dumped = bytes(dumped)
        ttl = int(await redis.ttl(raw_key))
        ttl_mode = "missing" if ttl == -2 else "persistent" if ttl == -1 else "expiring"
        key_hash = hashlib.sha256(key_bytes).hexdigest()
        state[key_hash] = (
            value_type,
            hashlib.sha256(dumped).hexdigest() if dumped is not None else None,
            ttl_mode,
        )
    return dict(sorted(state.items()))


def _public_route_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping):
        raise RuntimeError("admin route data 非法")
    allowed = {
        "status",
        "latency_ms",
        "failure_category",
        "tested_at",
        "test_version",
        "tested_draft_revision",
        "capability_key",
        "evidence_run_id",
        "evidence_report_id",
    }
    return {key: data[key] for key in allowed if key in data}


async def _read_human_session_id(
    port: int,
    *,
    fd: int = 0,
    event_loop: Any | None = None,
    attempt_id: str | None = None,
) -> str:
    print(
        "Phase0 worker 已启动。请打开 "
        f"http://127.0.0.1:{port}/pages/phase0_realtime_voice.html，"
        "新建本次真人会话并完成 sentence ACK；窗口约 45 秒。"
    )
    if attempt_id is not None:
        try:
            normalized_attempt_id = str(uuid.UUID(attempt_id))
        except (TypeError, ValueError):
            raise ValueError("ACK attempt_id 非法") from None
        print(
            "页面开始会话前执行 "
            f'window.setM1CampaignAttemptId("{normalized_attempt_id}")。'
        )
    print("粘贴本次 session_id（不重试）: ", end="", flush=True)
    loop = event_loop or asyncio.get_running_loop()
    future = loop.create_future()
    buffer = bytearray()
    was_blocking = os.get_blocking(fd)

    def readable() -> None:
        try:
            chunk = os.read(fd, 4096)
        except BlockingIOError:
            return
        except OSError as exc:
            if not future.done():
                future.set_exception(exc)
            return
        if not chunk:
            if not future.done():
                future.set_exception(EOFError("stdin 已关闭"))
            return
        buffer.extend(chunk)
        if b"\n" in buffer and not future.done():
            future.set_result(bytes(buffer).split(b"\n", 1)[0])

    os.set_blocking(fd, False)
    try:
        loop.add_reader(fd, readable)
        raw = await future
        try:
            return raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise ValueError("session_id 输入编码非法") from None
    finally:
        loop.remove_reader(fd)
        os.set_blocking(fd, was_blocking)


async def serve_direct_worker(
    worker: Phase0SubprocessWorker,
    *,
    port: int,
    attempt_id: str,
    reconnect_attempt_id: str | None = None,
    wait_for_shutdown: Callable[[], Any] | None = None,
) -> None:
    """Host one gate-enabled Phase0 server without creating a Provider session."""

    attempt_id = str(uuid.UUID(attempt_id))
    if reconnect_attempt_id is not None:
        reconnect_attempt_id = str(uuid.UUID(reconnect_attempt_id))
    await worker.start()
    try:
        print(
            f"direct Phase0: http://127.0.0.1:{port}/pages/phase0_realtime_voice.html"
        )
        print(f'首次 StartSession 前执行 window.setM1CampaignAttemptId("{attempt_id}")。')
        if reconnect_attempt_id is not None:
            print(
                "S01 reconnect 前改为执行 "
                f'window.setM1CampaignAttemptId("{reconnect_attempt_id}")。'
            )
        waiter = wait_for_shutdown or (lambda: asyncio.Event().wait())
        waited = waiter()
        if inspect.isawaitable(waited):
            await waited
    finally:
        await worker.stop()


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="M1 campaign-only 真人验证；不会替换生产默认 runner。",
        epilog=(
            "connection 会程序化创建并结束一次真实握手；ack 会启动全新 Phase0 "
            "worker，提示粘贴当次真人 session_id，45 秒内只检查 sentence ACK。"
        ),
    )
    parser.add_argument('--m1-protocol', action='store_true', help='选择隔离 v7 专项，不增加真实调用额度')
    parser.add_argument('--m1-cancel-retry', action='store_true', help='仅增加一次自动打断补测，原五次保留')
    parser.add_argument('--m1-cancel-only', action='store_true', help='v9 仅补测自动打断，保留原五次额度')
    parser.add_argument('--m1-recovery', action='store_true', help='选择修复后的 v8，续接原专项账本和五次总额度')
    parser.add_argument('--m1-authorization', type=Path, help='已确认且绑定本次冻结版本的授权记录')
    parser.add_argument(
        "mode",
        choices=(
            "preflight",
            "verify-no-provider",
            "reserve-attempt",
            "advance-to-final-batch",
            "serve-direct",
            "connection",
            "ack",
        ),
    )
    parser.add_argument(
        "--phase0-root",
        type=Path,
        default=PHASE0_RELATIVE_ROOT,
    )
    parser.add_argument("--project-env", type=Path, default=Path(".env"))
    parser.add_argument("--port", type=int, default=DEFAULT_PHASE0_PORT)
    parser.add_argument("--phase0-user-id", type=int, default=1)
    parser.add_argument("--campaign-id")
    parser.add_argument("--matrix-path", type=Path)
    parser.add_argument("--runtime-manifest", type=Path)
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="兼容参数；若提供也必须等于固定 campaigns/<id>/attempt-ledger.json",
    )
    parser.add_argument(
        "--attempt-kind",
        choices=tuple(sorted(DIRECT_PHASE0_ATTEMPT_KINDS)),
        help="reserve-attempt 专用；每次 direct Phase0 StartSession/reconnect 前调用",
    )
    parser.add_argument("--regression-evidence", type=Path)
    parser.add_argument(
        "--authorized-retest", action="store_true",
        help="仅用户明确要求继续人工验收时，凭绑定账本的授权及回归回执追加续测；默认15次，第四/五轮须分别明确批准16/18次",
    )
    parser.add_argument(
        "--expected-start-kind",
        choices=tuple(
            sorted(kind for kind in DIRECT_PHASE0_ATTEMPT_KINDS if kind.endswith("_start_session"))
        ),
    )
    parser.add_argument("--expected-start-ordinal", type=int)
    parser.add_argument("--expected-reconnect-ordinal", type=int)
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="仅在 campaign 隔离库幂等创建临时 admin/persona/draft，并经真实登录路由取 JWT",
    )
    return parser


@dataclass(frozen=True, slots=True)
class CampaignRuntime:
    app: Any
    runner_dependency: Any
    unavailable_runner_type: type
    validator: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    close_redis: Callable[[], Any]
    engine: Any


def load_campaign_runtime() -> CampaignRuntime:
    """Import backend state only after the caller pins campaign env values."""

    from backend.database import engine
    from backend.main import app
    from backend.redis_client import close_redis
    from backend.routers.admin.voice_config import get_voice_test_runner
    from backend.services.realtime_voice_admin_test_service import (
        UnavailableVoiceTestRunner,
    )
    from backend.services.realtime_voice_capability_service import (
        _validate_evidence_record,
    )

    def validator(value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _validate_evidence_record(
            value,
            expected_source="admin_capability_test",
            allow_error=True,
            path="record",
        )

    return CampaignRuntime(
        app=app,
        runner_dependency=get_voice_test_runner,
        unavailable_runner_type=UnavailableVoiceTestRunner,
        validator=validator,
        close_redis=close_redis,
        engine=engine,
    )


def campaign_http_client(app: Any):
    import httpx

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://m1-campaign.local",
        timeout=CAMPAIGN_ROUTE_DEADLINE_SECONDS,
    )


async def _run_cli(args: argparse.Namespace) -> int:
    if getattr(args, 'm1_cancel_retry', False) and not getattr(args, 'm1_cancel_only', False):
        raise ValueError('M1 retry requires cancel-only')
    if getattr(args, 'm1_cancel_only', False) and not getattr(args, 'm1_recovery', False):
        raise ValueError('M1 cancel-only 必须显式选择 recovery profile')
    if getattr(args, 'm1_recovery', False) and not getattr(args, 'm1_protocol', False):
        raise ValueError('M1 recovery 必须显式选择专项 profile')
    if getattr(args, 'm1_protocol', False):
        provider_modes = {'reserve-attempt','serve-direct','connection','ack','advance-to-final-batch'}
        if args.mode in provider_modes and not getattr(args, 'm1_authorization', None):
            raise ValueError('M1 专项真实操作需要明确用户授权')
        previous_root = PHASE0_RELATIVE_ROOT
        configure_m1_protocol_profile(recovery=getattr(args, 'm1_recovery', False), cancel_only=getattr(args, 'm1_cancel_only', False), cancel_retry=getattr(args, 'm1_cancel_retry', False))
        if M1_RECOVERY_PROFILE and (args.mode in {'connection', 'ack'}
            or getattr(args, 'expected_reconnect_ordinal', None) is not None):
            raise ValueError('本轮 M1 恢复仅允许打断和截断，不允许重连或管理实播')
        if args.phase0_root == previous_root:
            args.phase0_root = PHASE0_RELATIVE_ROOT
        if args.mode == 'connection' or (args.mode == 'advance-to-final-batch' and not M1_RECOVERY_PROFILE):
            raise ValueError('M1 专项不重复连接测试或追加旧批次')
    frozen = None
    if args.mode in {
        "reserve-attempt",
        "advance-to-final-batch",
        "serve-direct",
        "connection",
        "ack",
    }:
        expected_root = _PROJECT_ROOT / PHASE0_RELATIVE_ROOT
        if args.phase0_root.resolve() != expected_root.resolve():
            raise ValueError("Phase0 worktree 必须与 runtime closure 一致")
        frozen = resolve_frozen_campaign_from_args(args)
        if M1_PROTOCOL_PROFILE:
            authorize_m1_protocol_campaign(args.m1_authorization, frozen)
    validate_campaign_environment(
        os.environ,
        require_external_jwt=(
            args.mode in {"verify-no-provider", "connection", "ack"}
            and not args.bootstrap
        ),
    )
    project_env_path = args.project_env.resolve()
    phase0_root = args.phase0_root.resolve()
    phase0_database, phase0_redis_db = _phase0_business_coordinates(project_env_path)
    if not phase0_root.is_dir():
        raise ValueError("Phase0 隔离 worktree 不存在")
    public_settings = load_phase0_public_provider_settings(
        project_env_path=project_env_path,
        phase0_root=phase0_root,
    )
    settings_sha256 = _canonical_sha256(public_settings)
    runtime = load_campaign_runtime()
    try:
        await preflight_campaign_dependencies()
        print(
            "预检通过: "
            f"admin MySQL={CAMPAIGN_DATABASE_NAME}, admin Redis DB={CAMPAIGN_REDIS_DB}; "
            f"Phase0 MySQL={phase0_database}, Phase0 Redis DB={phase0_redis_db}, "
            f"public_settings_sha256={settings_sha256}, host=127.0.0.1"
        )
        if args.mode == "preflight":
            return 0

        if args.bootstrap and args.mode not in {
            "verify-no-provider",
            "connection",
            "ack",
        }:
            raise ValueError("该 campaign mode 禁止 bootstrap")

        login_pair: tuple[str, str] | None = None
        if args.bootstrap:
            login_pair = await bootstrap_campaign_prerequisites(
                project_env_path=project_env_path,
                phase0_root=phase0_root,
            )

        if args.mode in {
            "reserve-attempt",
            "advance-to-final-batch",
            "serve-direct",
        }:
            if frozen is None:
                raise RuntimeError("campaign 冻结参数缺失")
            baseline = await capture_current_campaign_baseline(
                project_env_path=project_env_path,
                phase0_root=phase0_root,
            )
            if args.mode == "reserve-attempt":
                if args.attempt_kind not in DIRECT_PHASE0_ATTEMPT_KINDS:
                    raise ValueError("reserve-attempt 必须声明 direct Phase0 attempt_kind")
                receipt = reserve_provider_attempt(
                    ledger_path=frozen.ledger_path,
                    campaign_id=frozen.campaign_id,
                    matrix_sha256=frozen.matrix_sha256,
                    runtime_manifest_sha256=frozen.runtime_manifest_sha256,
                    baseline=baseline,
                    attempt_kind=args.attempt_kind,
                )
                print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
                return 0
            if args.mode == "advance-to-final-batch":
                regression_evidence = getattr(args, "regression_evidence", None)
                if regression_evidence is None:
                    raise ValueError("advance-to-final-batch 缺少 regression evidence")
                receipt = advance_campaign_to_final_batch(
                    ledger_path=frozen.ledger_path,
                    campaign_id=frozen.campaign_id,
                    matrix_sha256=frozen.matrix_sha256,
                    runtime_manifest_sha256=frozen.runtime_manifest_sha256,
                    baseline=baseline,
                    regression_evidence_path=regression_evidence,
                    authorized_retest=getattr(args, "authorized_retest", False),
                )
                print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
                return 0

            start_kind = getattr(args, "expected_start_kind", None)
            start_ordinal = getattr(args, "expected_start_ordinal", None)
            if start_kind is None or start_ordinal is None:
                raise ValueError("serve-direct 缺少 expected start kind/ordinal")
            start_attempt = load_active_reserved_attempt(
                frozen=frozen,
                baseline=baseline,
                attempt_kind=start_kind,
                attempt_ordinal=start_ordinal,
            )
            reconnect_ordinal = getattr(args, "expected_reconnect_ordinal", None)
            reconnect_attempt = None
            if reconnect_ordinal is not None:
                if start_kind != "s01_start_session":
                    raise ValueError("仅 S01 可声明 reconnect attempt")
                reconnect_attempt = load_active_reserved_attempt(
                    frozen=frozen,
                    baseline=baseline,
                    attempt_kind="s01_reconnect",
                    attempt_ordinal=reconnect_ordinal,
                )
            voice_draft = await load_current_campaign_voice_draft()
            if _canonical_sha256(voice_draft) != baseline["voice_draft_sha256"]:
                raise RuntimeError("serve-direct draft 在启动前漂移")
            with project_provider_secret_scope(project_env_path):
                secret = os.environ[CAMPAIGN_CREDENTIAL_REF]
                worker = Phase0SubprocessWorker(
                    phase0_root=phase0_root,
                    project_env_path=project_env_path,
                    draft_snapshot=voice_draft,
                    secret=secret,
                    port=args.port,
                    campaign_attempt={
                        "attempt_directory": frozen.ledger_path.parent
                        / "attempt-reservations",
                        "campaign_id": frozen.campaign_id,
                        "matrix_sha256": frozen.matrix_sha256,
                        "runtime_manifest_sha256": frozen.runtime_manifest_sha256,
                        "baseline_epoch": start_attempt["baseline_epoch"],
                        "attempt_id": start_attempt["attempt_id"],
                        "attempt_ordinal": start_attempt["attempt_ordinal"],
                        "attempt_kind": start_attempt["attempt_kind"],
                        "fresh_admin_worker": False,
                        **(
                            {"expected_reconnect_ordinal": reconnect_ordinal}
                            if reconnect_ordinal is not None
                            else {}
                        ),
                    },
                )
                secret = ""
            await serve_direct_worker(
                worker,
                port=args.port,
                attempt_id=start_attempt["attempt_id"],
                reconnect_attempt_id=(
                    reconnect_attempt["attempt_id"]
                    if reconnect_attempt is not None
                    else None
                ),
            )
            return 0

        registry = ConsumedEvidenceRegistry()
        attempt_context: dict[str, Any] = {}
        runner_factory: Callable[[], Any] | None = None
        route_mode = "connection" if args.mode == "verify-no-provider" else args.mode
        if args.mode == "verify-no-provider":
            default_runner = runtime.runner_dependency()
            try:
                if type(default_runner) is not runtime.unavailable_runner_type:
                    raise RuntimeError("生产默认 runner 不再是 UnavailableVoiceTestRunner")
            finally:
                closed_default = default_runner.aclose()
                if inspect.isawaitable(closed_default):
                    await closed_default
        if args.mode in {"connection", "ack"}:

            def real_runner_factory() -> CampaignVoiceTestRunner:
                def worker_factory(**kwargs) -> Phase0SubprocessWorker:
                    receipt = attempt_context.get("receipt")
                    if not isinstance(receipt, Mapping) or frozen is None:
                        raise RuntimeError("admin worker 缺少 reserved attempt")
                    return Phase0SubprocessWorker(
                        phase0_root=phase0_root,
                        project_env_path=project_env_path,
                        draft_snapshot=kwargs["draft_snapshot"],
                        secret=kwargs["secret"],
                        port=args.port,
                        campaign_attempt={
                            "attempt_directory": frozen.ledger_path.parent
                            / "attempt-reservations",
                            "campaign_id": frozen.campaign_id,
                            "matrix_sha256": frozen.matrix_sha256,
                            "runtime_manifest_sha256": frozen.runtime_manifest_sha256,
                            "baseline_epoch": receipt["baseline_epoch"],
                            "attempt_id": receipt["attempt_id"],
                            "attempt_ordinal": receipt["attempt_ordinal"],
                            "attempt_kind": receipt["attempt_kind"],
                            "fresh_admin_worker": True,
                        },
                    )

                return CampaignVoiceTestRunner(
                    worker_factory=worker_factory,
                    validator=runtime.validator,
                    read_session_id=lambda: _read_human_session_id(
                        args.port,
                        attempt_id=attempt_context["receipt"]["attempt_id"],
                    ),
                    registry=registry,
                    user_id=args.phase0_user_id,
                )

            runner_factory = real_runner_factory

        before = await capture_campaign_state()
        async with campaign_http_client(runtime.app) as client:
            if login_pair is not None:
                username, password = login_pair
                jwt = await login_campaign_admin(client, username, password)
                password = ""
                login_pair = None
            else:
                jwt = os.environ["REALTIME_VOICE_M1_ADMIN_JWT"]
            await probe_campaign_admin_auth(client, jwt)
            secret_scope = (
                no_provider_canary_secret_scope()
                if args.mode == "verify-no-provider"
                else project_provider_secret_scope(project_env_path)
            )
            with secret_scope:
                if frozen is not None:
                    baseline = await capture_current_campaign_baseline(
                        project_env_path=project_env_path,
                        phase0_root=phase0_root,
                    )
                    receipt = reserve_provider_attempt(
                        ledger_path=frozen.ledger_path,
                        campaign_id=frozen.campaign_id,
                        matrix_sha256=frozen.matrix_sha256,
                        runtime_manifest_sha256=frozen.runtime_manifest_sha256,
                        baseline=baseline,
                        attempt_kind=(
                            "admin_connection" if args.mode == "connection" else "admin_ack"
                        ),
                    )
                    attempt_context["receipt"] = receipt
                    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
                payload = await call_admin_test_route(
                    app=runtime.app,
                    runner_dependency=runtime.runner_dependency,
                    runner_factory=runner_factory,
                    jwt=jwt,
                    mode=route_mode,
                    http_client=client,
                )
        after = await capture_campaign_state()
        public = _public_route_result(payload)
        assert_campaign_state_transition(
            before,
            after,
            mode=args.mode,
            route_result=public,
        )
        jwt = ""
        print(json.dumps(public, ensure_ascii=False, sort_keys=True))
        if args.mode == "verify-no-provider":
            if public.get("failure_category") != "internal_error":
                raise RuntimeError("no-Provider route 未按安全默认失败")
            return 0
        return 0 if public.get("status") in {"passed", "failed"} else 2
    finally:
        closed = runtime.close_redis()
        if inspect.isawaitable(closed):
            await closed
        await runtime.engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _build_argument_parser().parse_args(argv)
    try:
        return asyncio.run(_run_cli(args))
    except KeyboardInterrupt:
        print("campaign 已取消，未重试。", file=sys.stderr)
        return 130
    except Exception as exc:
        # No dynamic exception string crosses this boundary; it could contain
        # a credential, provider response, URL, or database DSN.
        del exc
        print("campaign 失败：已规范化并停止，未重试。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
