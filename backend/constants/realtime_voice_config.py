# -*- coding: utf-8 -*-
"""实时语音两套配置的唯一规范 seed manifest（STEP-005）。

这里只保存非敏感配置和已经由 PRD / 后台设计冻结的默认值。调用方必须通过
``build_canonical_voice_seed_manifest`` 取得深拷贝，避免运行时或测试修改规范源。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL, DEFAULT_VOICE_SUMMARY_PROMPT


VOICE_CALL_MASTER_SWITCH_KEY = "voice_call_master_switch"
VOICE_CALL_CONFIG_KEY = "voice_call_config"
VOICE_CALL_SCRIPT_KEY = "voice_call_script"
CRISIS_KEYWORDS_CONFIG_KEY = "crisis_keywords"

VOICE_CONFIG_SCHEMA_VERSION = 1
# Approved test-stage compatibility defaults; not production load-test claims.
VOICE_CONNECTION_DEFAULTS = {
    "heartbeat_interval_ms": 5000,
    "user_lock_ttl_ms": 15000,
    "reconnect_timeout_ms": 15000,
    "call_ticket_ttl_ms": 30000,
}
# Approved M3 test defaults; VAD still requires device calibration.
VOICE_INTERACTION_DEFAULTS = {
    "vad_rms_threshold": 0.015,
    "candidate_ms": 200,
    "sustained_ms": 600,
    "goodbye_timeout_ms": 10000,
    "post_playback_buffer_ms": 800,
    "time_low_seconds": 60,
}
VOICE_CONFIG_ALIASES = {
    "config": VOICE_CALL_CONFIG_KEY,
    "script": VOICE_CALL_SCRIPT_KEY,
}

RELATIONSHIP_STAGES = ("stranger", "friend", "intimate", "soulmate")

VOICE_CAPABILITY_KEYS = (
    "supports_current_turn_rag_gate",
    "supports_reply_cancel",
    "supports_context_truncate",
    "supports_playback_text_mapping",
    "supports_sentence_playback_ack",
    "supports_session_reconnect",
)

DEFAULT_MISSED_EXPLANATION_TEMPLATE = "刚刚没接到你的电话，晚一点我们再聊呀。"

# 后台设计把以下 S2S/并发参数明确标为“待技术定值”。它们只是为了让首个
# ``global.enabled=false`` 的规范 seed 具备完整、可校验结构；不能作为生产冻结值
# 对外宣称，启用语音前必须经后续 STEP 的真实联调/压测发布覆盖。
_DISABLED_ONLY_IMPLEMENTATION_DEFAULTS = {
    "connect_timeout_ms": 10000,
    "start_session_timeout_ms": 10000,
    "max_retries": 2,
    "retry_backoff_ms": [500, 1000],
    "global_concurrency_limit": 1,
}

# DESIGN 6.7 明确这些值仅是 P0 seed、仍待真实样本验证。把来源状态留在唯一
# manifest 附近，避免后续把这些数值误写成已确认的生产默认。
_UNVERIFIED_PHASE0_RECALL_SEED = {
    "max_query_chars": 200,
    "top_k": 3,
    "score_threshold": 0.7,
    "timeout_ms": 1000,
    "embedding_timeout_ms": 800,
    "vector_timeout_ms": 800,
}

DEFAULT_FOLLOWUP_SCHEDULE: dict[str, Any] = {
    "timezone": "Asia/Shanghai",
    "jitter_min_minutes": 0,
    "jitter_max_minutes": 20,
    "max_delay_hours": 24,
    "stages": {
        "stranger": {"windows": [{"start": "10:00", "end": "21:00"}]},
        "friend": {"windows": [{"start": "09:30", "end": "22:00"}]},
        "intimate": {"windows": [{"start": "09:00", "end": "22:30"}]},
        "soulmate": {"windows": [{"start": "09:00", "end": "23:00"}]},
    },
}

_DEFAULT_CAPABILITY = {
    "verification_status": "unverified",
    "enabled": False,
    "forced_enabled": False,
    "effective_scope": "off",
    "fallback_mode": "next_turn",
    "provider_profile": None,
    "model_version": None,
    "protocol_profile": None,
    "adapter_version": None,
    "sdk_version": None,
    "evidence_suite_version": None,
    "evidence_fingerprint": None,
    "evidence_ttl_days": 30,
    "verified_at": None,
    "expires_at": None,
    "evidence_report_id": None,
    "last_test_result": "not_run",
}

_PHASE0_VOICE_CANDIDATES = (
    "S_5kGC1Z212",
    "S_7fDYUZia2",
    "saturn_zh_female_keainvsheng_tob",
    "saturn_zh_female_nuanxinxuejie_tob",
    "saturn_zh_female_wenrouwenya_tob",
    "saturn_zh_female_tiexinnvyou_tob",
)

_VOICE_CALL_CONFIG_TEMPLATE: dict[str, Any] = {
    "schema_version": VOICE_CONFIG_SCHEMA_VERSION,
    "global": {
        "enabled": False,
        "maintenance_mode": False,
        "maintenance_message": "语音通话暂时不可用，请稍后再试",
        "soft_stop": False,
        "rollout": {"mode": "allowlist", "user_ids": []},
        "test_user_ids": [],
    },
    "persona_ref": {
        "config_key": "persona",
        "version": 0,
        "content_sha256": "",
    },
    "s2s": {
        "provider": "doubao",
        "endpoint": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
        "resource_id": "volc.speech.dialog",
        "model_version": "2.2.0.0",
        "adapter_version": "voice_adapter_v1",
        "protocol_profile": "doubao_dialog_v3_pcm",
        "credential_ref": "DOUBAO_S2S_ACCESS_KEY",
        "credential_revision_ref": None,
        "connect_timeout_ms": _DISABLED_ONLY_IMPLEMENTATION_DEFAULTS["connect_timeout_ms"],
        "start_session_timeout_ms": _DISABLED_ONLY_IMPLEMENTATION_DEFAULTS[
            "start_session_timeout_ms"
        ],
        "max_retries": _DISABLED_ONLY_IMPLEMENTATION_DEFAULTS["max_retries"],
        "retry_backoff_ms": deepcopy(
            _DISABLED_ONLY_IMPLEMENTATION_DEFAULTS["retry_backoff_ms"]
        ),
    },
    "voice": {
        "voice_id": "saturn_zh_female_keainvsheng_tob",
        "voice_version": "phase0-v1",
        "candidates": [
            {"voice_id": voice_id, "voice_version": "phase0-v1", "enabled": True}
            for voice_id in _PHASE0_VOICE_CANDIDATES
        ],
        "persona_mapping": {},
        "speech_rate": 0,
        "loudness_rate": 0,
        "expressive": False,
        "tone_instruction": "",
    },
    "capabilities": {
        key: deepcopy(_DEFAULT_CAPABILITY) for key in VOICE_CAPABILITY_KEYS
    },
    "quota": {
        "daily_free_seconds": 300,
        "grace_seconds": 30,
        "hard_limit_seconds": 3600,
        "timezone": "Asia/Shanghai",
    },
    "growth": {
        "segment_seconds": 30,
        "points_per_segment": 5,
        "daily_limit_points": 100,
        "timezone": "Asia/Shanghai",
    },
    "interaction": dict(VOICE_INTERACTION_DEFAULTS),
    "concurrency": {
        **VOICE_CONNECTION_DEFAULTS,
        "global_limit": _DISABLED_ONLY_IMPLEMENTATION_DEFAULTS[
            "global_concurrency_limit"
        ],
    },
    "summary": {"model": DEFAULT_VOICE_SUMMARY_MODEL},
    "followup": {
        "summary_min_effective_seconds": 15,
        "schedule": deepcopy(DEFAULT_FOLLOWUP_SCHEDULE),
    },
    "retention": {
        "effective_transcript_days": 180,
        "generated_debug_days": 30,
        "reasoning_days": 30,
        "crisis_raw_days": 30,
        "job_log_days": 90,
    },
}

_VOICE_CALL_SCRIPT_TEMPLATE: dict[str, Any] = {
    "schema_version": VOICE_CONFIG_SCHEMA_VERSION,
    "context_pack": {
        "voice_instruction_template": "",
        "fallback_template_sections": ["persona", "relationship", "salutation", "current_time"],
        "persona_max_chars": 5000,
        "dynamic_max_chars": 2000,
        "recent_dialog_max_chars": 800,
        "memory_max_items": 5,
        "memory_lookback_days": 30,
        "build_budget_ms": 3000,
        "ready_barrier_enabled": True,
    },
    "call_answer": {
        "prompt_template": "",
        "failure_fallback": "answer",
        "min_ring_seconds": 4,
        "max_wait_seconds": 12,
        "fallback_delay_min_seconds": 4,
        "fallback_delay_max_seconds": 8,
    },
    "recall": {
        "prompt_template": "",
        "trigger_rules": [
            "上次",
            "你还记得",
            "我之前说过",
            "我之前告诉过你",
            "那个朋友",
            "继续说",
            "我们之前",
        ],
        **deepcopy(_UNVERIFIED_PHASE0_RECALL_SEED),
    },
    "summary": {"prompt_template": DEFAULT_VOICE_SUMMARY_PROMPT},
    "memory": {"prompt_template": "", "max_items_per_turn": 5,
               "max_retries": 2, "retry_backoff_ms": [1000, 5000]},
    "barge_in": {
        "weak_acknowledgements": ["嗯", "嗯嗯", "啊", "哦", "对", "对对", "好", "好的", "是", "是的", "哈哈"],
        "strong_interruptions": ["等等", "等一下", "停一下", "不是", "不对", "等会儿", "先别说", "让我说", "你听我说"],
        "upgrade_connectors": ["但是", "可是", "不过", "其实", "我是说", "我的意思是"],
    },
    "silence_and_exit": {
        "exit_intent_template": "好，那我们先聊到这",
        "silence_timeout_template": "好像暂时听不到你，我们下次再聊",
        "silence_confirm_seconds": 6,
        "silence_hangup_seconds": 12,
        "user_resume_cancels_exit": True,
    },
    "followup": {
        "missed_explanation_template": DEFAULT_MISSED_EXPLANATION_TEMPLATE,
    },
    "end_reason": {
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
    },
    "reconnect_bridge": {
        "success_template": "刚刚好像断了一下。你刚才说到哪儿了？",
    },
    "crisis": {
        "region": "CN-mainland",
        "in_call_banner": "如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。",
        "post_call_resource_card": "如果你可能马上伤害自己，请立即拨打 110/120，并请一位可信任的人来到你身边；也可以拨打 12356 心理援助热线。",
    },
}


def build_canonical_voice_seed_manifest(
    persona_ref: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """返回两 key 的规范 seed 深拷贝，并写入已发布人格锚点。"""

    config = deepcopy(_VOICE_CALL_CONFIG_TEMPLATE)
    config["persona_ref"] = deepcopy(persona_ref)
    return {
        VOICE_CALL_CONFIG_KEY: config,
        VOICE_CALL_SCRIPT_KEY: deepcopy(_VOICE_CALL_SCRIPT_TEMPLATE),
    }


def get_default_voice_call_script() -> dict[str, Any]:
    """返回 script 规范默认深拷贝，供后续运行时回退复用。"""

    return deepcopy(_VOICE_CALL_SCRIPT_TEMPLATE)


def get_default_voice_call_config(persona_ref: dict[str, Any]) -> dict[str, Any]:
    """返回 config 规范默认深拷贝，和首次发布共用唯一 manifest 源。"""

    return build_canonical_voice_seed_manifest(persona_ref)[VOICE_CALL_CONFIG_KEY]


def get_default_followup_schedule() -> dict[str, Any]:
    """返回 follow-up 规范默认深拷贝。"""

    return deepcopy(DEFAULT_FOLLOWUP_SCHEDULE)


__all__ = [
    "CRISIS_KEYWORDS_CONFIG_KEY",
    "DEFAULT_FOLLOWUP_SCHEDULE",
    "DEFAULT_MISSED_EXPLANATION_TEMPLATE",
    "RELATIONSHIP_STAGES",
    "VOICE_CALL_CONFIG_KEY",
    "VOICE_CALL_SCRIPT_KEY",
    "VOICE_CAPABILITY_KEYS",
    "VOICE_CONFIG_ALIASES",
    "VOICE_CONFIG_SCHEMA_VERSION",
    "build_canonical_voice_seed_manifest",
    "get_default_followup_schedule",
    "get_default_voice_call_config",
    "get_default_voice_call_script",
]
