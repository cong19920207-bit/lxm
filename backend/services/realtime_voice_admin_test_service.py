# -*- coding: utf-8 -*-
"""STEP-006 synchronous admin voice test orchestration.

The runner is a short-lived injected port.  This module owns the 60-second
deadline, server-side credential resolution, normalized public result and
cleanup; it never exposes Provider exceptions or credentials.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.schemas.realtime_voice_config import (
    VoiceCapabilityTestData,
    VoiceConnectionTestData,
)
from backend.services.realtime_voice_capability_service import (
    realtime_voice_capability_service,
)
from backend.services.realtime_voice_config_service import (
    content_sha256,
    validate_trusted_voice_bundle,
)
from backend.utils.admin_auth import log_operation


logger = logging.getLogger(__name__)

VOICE_TEST_VERSION = "admin-voice-test/v1"
VOICE_TEST_DEADLINE_SECONDS = 60
VOICE_TEST_CLEANUP_DEADLINE_SECONDS = 5

_TEST_STATUSES = frozenset({"passed", "failed", "error"})
_FAILURE_CATEGORIES = frozenset(
    {
        "none",
        "invalid_config",
        "credential_missing",
        "authentication_failed",
        "timeout",
        "upstream_unavailable",
        "protocol_error",
        "evidence_invalid",
        "internal_error",
    }
)


class VoiceTestRunnerPort(Protocol):
    """Short-lived Provider runner shared by both synchronous admin tests."""

    async def run_connection(
        self,
        *,
        draft_snapshot: Mapping[str, Any],
        secret: str,
    ) -> Mapping[str, Any]: ...

    async def run_capability(
        self,
        *,
        capability_key: str,
        draft_snapshot: Mapping[str, Any],
        secret: str,
    ) -> Mapping[str, Any]: ...

    async def aclose(self) -> None: ...


class UnavailableVoiceTestRunner:
    """Safe default until a real STEP-004/007 runner factory is wired."""

    async def run_connection(self, **_kwargs) -> Mapping[str, Any]:
        return _normalized_runner_error("internal_error")

    async def run_capability(self, **_kwargs) -> Mapping[str, Any]:
        return _normalized_runner_error("internal_error")

    async def aclose(self) -> None:
        return None


def get_voice_test_runner() -> VoiceTestRunnerPort:
    """FastAPI dependency and stable injection seam for one request runner."""
    from backend.services.realtime_voice_provider_service import ProviderAdminTestRunner

    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    return ProviderAdminTestRunner(capability_probe=BuiltinCapabilityProbe())


@dataclass(frozen=True, slots=True)
class _DraftSnapshot:
    config: dict[str, Any] | None
    revision: int
    failure_category: str | None = None
    row_id: int | None = None
    content_sha256: str | None = None


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalized_runner_error(category: str) -> dict[str, Any]:
    return {
        "status": "error",
        "latency_ms": None,
        "failure_category": category,
        "tested_at": _utc_now_text(),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _valid_tested_at(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("tested_at invalid")
    datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return value.strip()


def _same_test_instant(left: Any, right: Any) -> bool:
    try:
        left_value = datetime.fromisoformat(str(left).replace("Z", "+00:00"))
        right_value = datetime.fromisoformat(str(right).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if left_value.tzinfo is None or right_value.tzinfo is None:
        return False
    return left_value.astimezone(timezone.utc) == right_value.astimezone(timezone.utc)


def _normalize_runner_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("runner result must be an object")
    status = value.get("status")
    category = value.get("failure_category")
    latency_ms = value.get("latency_ms")
    if status not in _TEST_STATUSES or category not in _FAILURE_CATEGORIES:
        raise ValueError("runner result enum invalid")
    if latency_ms is not None and (
        type(latency_ms) is not int or latency_ms < 0
    ):
        raise ValueError("runner latency invalid")
    if status == "passed" and category != "none":
        raise ValueError("passed runner result must use none")
    if status != "passed" and category == "none":
        raise ValueError("non-passed runner result needs failure category")
    return {
        "status": status,
        "latency_ms": latency_ms,
        "failure_category": category,
        "tested_at": _valid_tested_at(value.get("tested_at")),
    }


async def _load_draft_snapshot(db: AsyncSession) -> _DraftSnapshot:
    row = (
        await db.execute(
            select(AdminConfig)
            .where(
                AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                AdminConfig.is_draft == True,  # noqa: E712
                AdminConfig.is_active == False,  # noqa: E712
            )
            .order_by(AdminConfig.id.desc())
        )
    ).scalars().first()
    if row is None or type(row.draft_revision) is not int or row.draft_revision < 1:
        return _DraftSnapshot(None, 0, "invalid_config")
    try:
        config = json.loads(row.config_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _DraftSnapshot(None, row.draft_revision, "invalid_config")
    if not isinstance(config, dict) or validate_trusted_voice_bundle(
        VOICE_CALL_CONFIG_KEY,
        config,
    ):
        return _DraftSnapshot(None, row.draft_revision, "invalid_config")
    return _DraftSnapshot(
        deepcopy(config),
        row.draft_revision,
        row_id=row.id,
        content_sha256=content_sha256(config),
    )


async def _frozen_draft_matches_locked(
    db: AsyncSession,
    snapshot: _DraftSnapshot,
) -> bool:
    """Lock and recheck the exact draft that was handed to the runner."""

    if (
        snapshot.row_id is None
        or snapshot.revision < 1
        or snapshot.content_sha256 is None
    ):
        return False
    row = (
        await db.execute(
            select(
                AdminConfig.id,
                AdminConfig.draft_revision,
                AdminConfig.config_value,
            )
            .where(
                AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
                AdminConfig.is_draft == True,  # noqa: E712
                AdminConfig.is_active == False,  # noqa: E712
            )
            .order_by(AdminConfig.id.desc())
            .with_for_update()
        )
    ).first()
    if row is None:
        return False
    row_id, draft_revision, config_value = row
    if row_id != snapshot.row_id or draft_revision != snapshot.revision:
        return False
    try:
        current_config = json.loads(config_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(current_config, dict) and (
        content_sha256(current_config) == snapshot.content_sha256
    )


def _resolve_server_secret(snapshot: _DraftSnapshot) -> tuple[str | None, str | None]:
    config = snapshot.config
    if not isinstance(config, dict):
        return None, snapshot.failure_category or "invalid_config"
    s2s = config.get("s2s")
    credential_ref = s2s.get("credential_ref") if isinstance(s2s, dict) else None
    if not isinstance(credential_ref, str) or not credential_ref:
        return None, "invalid_config"
    secret = os.getenv(credential_ref)
    if not isinstance(secret, str) or not secret:
        return None, "credential_missing"
    return secret, None


async def _safe_close(runner: VoiceTestRunnerPort) -> None:
    try:
        async with asyncio.timeout(VOICE_TEST_CLEANUP_DEADLINE_SECONDS):
            await runner.aclose()
    except TimeoutError:
        logger.error("语音后台测试 runner 清理超时")
    except BaseException:
        # Provider cleanup failures can carry raw response/credential text.
        logger.error("语音后台测试 runner 清理失败")


async def _write_test_audit(
    db: AsyncSession,
    *,
    admin_user: AdminUser,
    request,
    action: str,
    data: Mapping[str, Any],
) -> None:
    safe_data = {
        key: value
        for key, value in data.items()
        if key
        in {
            "status",
            "latency_ms",
            "failure_category",
            "test_version",
            "tested_draft_revision",
            "tested_at",
            "capability_key",
            "evidence_run_id",
            "evidence_report_id",
            "test_id",
        }
    }
    await log_operation(
        db,
        admin_user,
        "voice_config",
        action,
        "实时语音后台连接测试" if action == "test_connection" else "实时语音后台能力测试",
        before_value=None,
        after_value=_canonical_json(safe_data),
        request=request,
    )


class RealtimeVoiceAdminTestService:
    async def test_connection(
        self,
        db: AsyncSession,
        *,
        runner: VoiceTestRunnerPort,
        admin_user: AdminUser,
        request=None,
    ) -> VoiceConnectionTestData:
        snapshot = await _load_draft_snapshot(db)
        result: dict[str, Any]
        try:
            secret, preflight_error = _resolve_server_secret(snapshot)
            if preflight_error is not None:
                result = _normalized_runner_error(preflight_error)
            else:
                try:
                    async with asyncio.timeout(VOICE_TEST_DEADLINE_SECONDS):
                        raw = await runner.run_connection(
                            draft_snapshot=deepcopy(snapshot.config),
                            secret=secret,
                        )
                    result = _normalize_runner_result(raw)
                except TimeoutError:
                    result = _normalized_runner_error("timeout")
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error("语音后台连接测试 runner 失败")
                    result = _normalized_runner_error("internal_error")
        finally:
            await _safe_close(runner)

        data = VoiceConnectionTestData(
            **result,
            test_version=VOICE_TEST_VERSION,
            tested_draft_revision=snapshot.revision,
        )
        await _write_test_audit(
            db,
            admin_user=admin_user,
            request=request,
            action="test_connection",
            data=data.model_dump(mode="json"),
        )
        return data

    async def test_capability(
        self,
        db: AsyncSession,
        *,
        capability_key: str,
        runner: VoiceTestRunnerPort,
        admin_user: AdminUser,
        request=None,
    ) -> VoiceCapabilityTestData:
        snapshot = await _load_draft_snapshot(db)
        evidence_record: Mapping[str, Any] | None = None
        runner_completed = False
        result: dict[str, Any]
        try:
            secret, preflight_error = _resolve_server_secret(snapshot)
            if preflight_error is not None:
                result = _normalized_runner_error(preflight_error)
            else:
                try:
                    async with asyncio.timeout(VOICE_TEST_DEADLINE_SECONDS):
                        raw = await runner.run_capability(
                            capability_key=capability_key,
                            draft_snapshot=deepcopy(snapshot.config),
                            secret=secret,
                        )
                    runner_completed = True
                    result = _normalize_runner_result(raw)
                    candidate = raw.get("evidence_record") if isinstance(raw, Mapping) else None
                    if isinstance(candidate, Mapping):
                        evidence_record = deepcopy(dict(candidate))
                except TimeoutError:
                    result = _normalized_runner_error("timeout")
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error("语音后台能力测试 runner 失败")
                    result = _normalized_runner_error("internal_error")
        finally:
            await _safe_close(runner)

        evidence_run_id: str | None = None
        evidence_report_id: str | None = None
        if runner_completed:
            if (
                not isinstance(evidence_record, Mapping)
                or evidence_record.get("capability_key") != capability_key
                or evidence_record.get("source_type") != "admin_capability_test"
                or evidence_record.get("verification_result") != result["status"]
                or not _same_test_instant(
                    evidence_record.get("tested_at"),
                    result["tested_at"],
                )
            ):
                result = _normalized_runner_error("evidence_invalid")
            else:
                try:
                    if not await _frozen_draft_matches_locked(db, snapshot):
                        result = _normalized_runner_error("evidence_invalid")
                    else:
                        await realtime_voice_capability_service.append_admin_capability_evidence(
                            db,
                            record=deepcopy(dict(evidence_record)),
                            operator_id=admin_user.id,
                        )
                        evidence_run_id = str(evidence_record["evidence_run_id"])
                        evidence_report_id = str(evidence_record["evidence_report_id"])
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # A caught append error must not leave a half-staged evidence row.
                    await db.rollback()
                    logger.error("语音后台能力证据追加失败")
                    result = _normalized_runner_error("evidence_invalid")

        data = VoiceCapabilityTestData(
            **result,
            test_version=VOICE_TEST_VERSION,
            tested_draft_revision=snapshot.revision,
            capability_key=capability_key,
            evidence_run_id=evidence_run_id,
            evidence_report_id=evidence_report_id,
        )
        await _write_test_audit(
            db,
            admin_user=admin_user,
            request=request,
            action="test_capability",
            data={**data.model_dump(mode="json"), **({"test_id": runner.test_target_id} if getattr(runner,"test_target_id",None) else {})},
        )
        return data


realtime_voice_admin_test_service = RealtimeVoiceAdminTestService()


__all__ = [
    "RealtimeVoiceAdminTestService",
    "UnavailableVoiceTestRunner",
    "VOICE_TEST_DEADLINE_SECONDS",
    "VOICE_TEST_VERSION",
    "VoiceTestRunnerPort",
    "get_voice_test_runner",
    "realtime_voice_admin_test_service",
]
