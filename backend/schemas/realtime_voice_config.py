# -*- coding: utf-8 -*-
"""实时语音配置管理 API 请求模型（STEP-005）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VoiceDraftSectionRequest(_StrictModel):
    base_version: int = Field(..., ge=0)
    draft_revision: int | None = Field(default=None, ge=1)
    content: dict[str, Any]


class FollowupPreviewRequest(_StrictModel):
    # 具体类型与范围由服务层统一收敛为 FOLLOWUP_PREVIEW_INPUT_INVALID，
    # 避免 Pydantic 先把不同非法输入拆成另一套 422 口径。
    stage: Any
    candidate_at: Any
    jitter_minutes: Any


class VoiceValidateRequest(_StrictModel):
    # 整个嵌套值交给服务层做精确键集/类型校验，确保缺字段、多字段、错误类型等
    # 都统一返回 FOLLOWUP_PREVIEW_INPUT_INVALID，而不是分裂成框架 422。
    followup_preview: Any | None = None


class VoicePublishRequest(_StrictModel):
    confirm_text: str
    change_note: str = Field(..., min_length=1, max_length=500)

    @field_validator("change_note")
    @classmethod
    def reject_blank_change_note(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("change_note 不得为空白")
        return stripped


class VoiceRollbackRequest(_StrictModel):
    version: int = Field(..., ge=1)
    confirm_text: str
    change_note: str = Field(..., min_length=1, max_length=500)

    @field_validator("change_note")
    @classmethod
    def reject_blank_change_note(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("change_note 不得为空白")
        return stripped


class VoiceConnectionTestRequest(_StrictModel):
    """连接测试不接受调用方覆盖草稿中的任何 Provider 参数。"""


VoiceCapabilityKey = Literal[
    "supports_current_turn_rag_gate",
    "supports_reply_cancel",
    "supports_context_truncate",
    "supports_playback_text_mapping",
    "supports_sentence_playback_ack",
    "supports_session_reconnect",
]


class VoiceCapabilityTestRequest(_StrictModel):
    capability_key: VoiceCapabilityKey


class VoiceForceTestRequest(_StrictModel):
    effective_scope: Literal["test"]
    confirm_text: str
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason 不得为空白")
        return stripped


VoiceTestStatus = Literal["passed", "failed", "error"]
VoiceTestFailureCategory = Literal[
    "none",
    "invalid_config",
    "credential_missing",
    "authentication_failed",
    "timeout",
    "upstream_unavailable",
    "protocol_error",
    "evidence_invalid",
    "internal_error",
]


class VoiceConnectionTestData(_StrictModel):
    status: VoiceTestStatus
    latency_ms: int | None = Field(..., ge=0)
    failure_category: VoiceTestFailureCategory
    test_version: Literal["admin-voice-test/v1"]
    tested_draft_revision: int = Field(..., ge=0)
    tested_at: str


class VoiceCapabilityTestData(VoiceConnectionTestData):
    capability_key: VoiceCapabilityKey
    evidence_run_id: str | None
    evidence_report_id: str | None


__all__ = [
    "FollowupPreviewRequest",
    "VoiceCapabilityKey",
    "VoiceCapabilityTestData",
    "VoiceCapabilityTestRequest",
    "VoiceConnectionTestData",
    "VoiceConnectionTestRequest",
    "VoiceDraftSectionRequest",
    "VoiceForceTestRequest",
    "VoicePublishRequest",
    "VoiceRollbackRequest",
    "VoiceTestFailureCategory",
    "VoiceTestStatus",
    "VoiceValidateRequest",
]
