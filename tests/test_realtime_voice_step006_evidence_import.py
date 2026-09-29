# -*- coding: utf-8 -*-
"""STEP-006 Phase0 v3 evidence validation and atomic import RED tests.

These tests intentionally describe the production-only import boundary before
the implementation exists.  They exercise the internal service directly; no
public import route is part of the contract.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import backend.models  # noqa: F401  register the complete ORM metadata
import backend.services.realtime_voice_capability_service as capability_module
from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CAPABILITY_KEYS,
    build_canonical_voice_seed_manifest,
)
from backend.database import Base
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.services.realtime_voice_capability_service import (
    CapabilityEvidenceAccessError,
    CapabilityStateError,
    EVIDENCE_FINGERPRINT_FIELDS,
    realtime_voice_capability_service,
)
from backend.services.realtime_voice_config_service import canonical_json


PHASE0_RECORD_SCHEMA = "phase0-capability-evidence/v3"
PHASE0_BUNDLE_SCHEMA = "phase0-evidence-bundle/v1"
RUN_ID = "22222222-2222-4222-8222-222222222222"
SECOND_RUN_ID = "33333333-3333-4333-8333-333333333333"
_REFERENCE_NOW = datetime.now(timezone.utc).replace(microsecond=0)
TESTED_AT = _REFERENCE_NOW.isoformat().replace("+00:00", "Z")
VERIFIED_AT = TESTED_AT
EXPIRES_AT = (_REFERENCE_NOW + timedelta(days=30)).isoformat().replace("+00:00", "Z")
TTL_DAYS = 30
MYSQL_DATABASE_ENV = "REALTIME_VOICE_STEP006_IMPORT_DATABASE"

RESULT_BY_CAPABILITY = {
    VOICE_CAPABILITY_KEYS[0]: "passed",
    VOICE_CAPABILITY_KEYS[1]: "failed",
    VOICE_CAPABILITY_KEYS[2]: "failed",
    VOICE_CAPABILITY_KEYS[3]: "passed",
    VOICE_CAPABILITY_KEYS[4]: "failed",
    VOICE_CAPABILITY_KEYS[5]: "failed",
}
STATUS_BY_RESULT = {
    "passed": "verified",
    "failed": "failed",
    "error": "unverified",
}

_TABLES = (
    AdminUser.__table__,
    AdminConfig.__table__,
    AdminOperationLog.__table__,
    VoiceCapabilityEvidence.__table__,
)

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class _FakeRedis:
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


fake_redis = _FakeRedis()
role_ids: dict[str, int] = {}


def _canonical_sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dimensions() -> dict[str, str]:
    return {
        "provider_profile": "doubao-s2s-strong-character",
        "model_version": "2.2.0.0",
        "protocol_profile": "dialogue-v3-binary-gzip-json-pcm16",
        "adapter_version": "b937a78-step004-evidence-v3",
        "sdk_version": "websockets-16.1",
        "evidence_suite_version": "step004-o01-v3",
    }


def _fingerprint(dimensions: dict[str, str] | None = None) -> str:
    values = dimensions or _dimensions()
    exact = {field: values[field] for field in EVIDENCE_FINGERPRINT_FIELDS}
    return _canonical_sha256(exact)


def _safe_event(
    *,
    event_id: int = 559,
    ordinal: int = 7,
    received_at_ms: int | None = None,
    probe_match: bool = False,
    audio: bool = False,
    sentence_boundary: bool = False,
) -> dict:
    event_names = {
        150: "SessionStarted",
        153: "SessionFailed",
        152: "SessionFinished",
        350: "TTSSentenceStart",
        351: "TTSSentenceEnd",
        352: "TTSResponse",
        359: "TTSEnded",
        451: "ASRResponse",
        550: "ChatResponse",
        559: "ChatEnded",
    }
    correlations = {
        "frame.session_id": "hmac256:111111111111111111111111",
        "payload.question_id": "hmac256:222222222222222222222222",
        "payload.reply_id": "hmac256:333333333333333333333333",
    }
    object_keys = ["payload.question_id", "payload.reply_id"]
    if sentence_boundary:
        correlations.update(
            {
                "payload.sentence_id": "hmac256:555555555555555555555555",
                "phase0.sentence_boundary": "hmac256:444444444444444444444444",
            }
        )
        object_keys.append("payload.sentence_id")
    return {
        "ordinal": ordinal,
        "received_at_ms": received_at_ms or 1788310923000 + ordinal * 100,
        "event_id": event_id,
        "event_name": event_names[event_id],
        "target_event": event_names[event_id]
        in {
            "ChatResponse",
            "ChatEnded",
            "TTSSentenceStart",
            "TTSSentenceEnd",
            "TTSEnded",
            "SessionFailed",
        },
        "message_type": "SERVER_FULL_RESPONSE",
        "payload_kind": "binary" if audio else "object",
        "payload_size": 24,
        "is_audio": audio,
        "parse_error": False,
        "correlation_tokens": correlations,
        "payload_shape": {
            "object_keys": object_keys,
            "list_lengths": {},
            "numeric_fields": {},
            "boolean_fields": {},
            "text_fields": {},
            "binary_fields": {},
            "redacted_key_classes": [],
        },
        **({"probe_match": True} if probe_match else {}),
    }


def _safe_action() -> dict:
    return {
        "action": "client_sentence_played",
        "at_ms": 1788310923010,
        "success": True,
        "sentence_token": "hmac256:444444444444444444444444",
        "sentence_boundary_ordinal": 7,
        "provider_ordinal_after_ack": 8,
        "correlation_tokens": {
            "payload.reply_id": "hmac256:333333333333333333333333",
        },
    }


def _causal_payload(capability_key: str, result: str) -> tuple[str, list[dict], list[dict]]:
    if capability_key == "supports_current_turn_rag_gate":
        return (
            "same_turn_probe_matched_single_reply",
            [
                _safe_event(event_id=451, ordinal=1),
                _safe_event(event_id=550, ordinal=2, probe_match=True),
                _safe_event(event_id=559, ordinal=3),
            ],
            [
                {
                    "action": "rag_probe_injected",
                    "at_ms": 1788310923150,
                    "success": True,
                    "provider_ordinal_after_send": 1,
                    "source_asr_ordinal": 1,
                    "correlation_tokens": {
                        "frame.session_id": "hmac256:111111111111111111111111",
                        "payload.question_id": "hmac256:222222222222222222222222",
                        "payload.reply_id": "hmac256:333333333333333333333333",
                    },
                }
            ],
        )
    if capability_key in {"supports_reply_cancel", "supports_context_truncate"}:
        reason = (
            "provider_cancel_or_local_stop_exceeded_grace"
            if capability_key == "supports_reply_cancel"
            else "conversation_truncated_event_id_not_authoritative"
        )
        return (
            reason,
            [
                _safe_event(event_id=350, ordinal=1, sentence_boundary=True),
                _safe_event(
                    event_id=359,
                    ordinal=2,
                    received_at_ms=1788310924000,
                    sentence_boundary=True,
                ),
            ],
            [
                {
                    "action": "client_interrupt_sent",
                    "at_ms": 1788310923300,
                    "reply_active": True,
                    "success": True,
                    "stop_token": "hmac256:666666666666666666666666",
                    "local_stop_at_ms": 1788310923250,
                    "provider_ordinal_after_send": 1,
                    "target_tts_start_ordinal": 1,
                    "target_reply_generation": 1,
                    "correlation_tokens": {
                        "frame.session_id": "hmac256:111111111111111111111111",
                        "payload.question_id": "hmac256:222222222222222222222222",
                        "payload.reply_id": "hmac256:333333333333333333333333",
                    },
                },
                {
                    "action": "client_stop_playback_applied",
                    "at_ms": 1788310923350,
                    "success": False,
                    "stop_token": "hmac256:666666666666666666666666",
                    "target_reply_generation": 1,
                    "provider_ordinal_after_ack": 1,
                    "correlation_tokens": {
                        "payload.reply_id": "hmac256:333333333333333333333333"
                    },
                },
            ],
        )
    if capability_key in {
        "supports_playback_text_mapping",
        "supports_sentence_playback_ack",
    }:
        events = [
            _safe_event(event_id=350, ordinal=1, sentence_boundary=True),
            _safe_event(event_id=352, ordinal=2, audio=True, sentence_boundary=True),
            _safe_event(event_id=351, ordinal=3, sentence_boundary=True),
        ]
        if capability_key == "supports_playback_text_mapping":
            return (
                "sentence_identity_reply_session_boundaries_correlate_with_audio",
                events,
                [],
            )
        return (
            "client_sentence_ack_failed_for_correlated_boundary",
            events,
            [
                {
                    "action": "client_sentence_played",
                    "at_ms": 1788310923400,
                    "success": False,
                    "sentence_token": "hmac256:444444444444444444444444",
                    "sentence_boundary_ordinal": 3,
                    "provider_ordinal_after_ack": 3,
                    "correlation_tokens": {
                        "payload.reply_id": "hmac256:333333333333333333333333"
                    },
                }
            ],
        )
    assert capability_key == "supports_session_reconnect" and result == "failed"
    return (
        "reconnect_seed_exposed_before_disconnect",
        [_safe_event(event_id=451, ordinal=1)],
        [
            {
                "action": "provider_reconnect_seed_exposed",
                "at_ms": 1788310923200,
                "success": False,
                "reason_code": "seed_visible",
                "provider_event_ordinal": 1,
                "session_token": "hmac256:111111111111111111111111",
                "correlation_tokens": {
                    "frame.session_id": "hmac256:111111111111111111111111"
                },
            }
        ],
    )


def _reconnect_causal_slice(*, failed: bool = False) -> tuple[list[dict], list[dict]]:
    events = [
        _safe_event(event_id=150, ordinal=1),
        _safe_event(event_id=451, ordinal=2),
        _safe_event(event_id=550, ordinal=3),
        _safe_event(event_id=559, ordinal=4),
        _safe_event(event_id=150, ordinal=5),
        _safe_event(event_id=451, ordinal=6),
        _safe_event(event_id=550, ordinal=7),
        _safe_event(event_id=559, ordinal=8),
    ]
    for event in (events[0], events[4]):
        event["correlation_tokens"]["payload.dialog_id"] = (
            "hmac256:aaaaaaaaaaaaaaaaaaaaaaaa"
        )
    events[1]["correlation_tokens"]["phase0.reconnect_seed"] = (
        "hmac256:777777777777777777777777"
    )
    events[5]["correlation_tokens"]["phase0.reconnect_question"] = (
        "hmac256:888888888888888888888888"
    )
    events[6]["probe_match"] = True
    session_token = "hmac256:111111111111111111111111"
    common = {"frame.session_id": session_token}
    actions = [
        {
            "action": "provider_reconnect_seed_injected",
            "at_ms": 1788310923250,
            "success": True,
            "provider_ordinal_after_send": 2,
            "session_token": session_token,
            "correlation_tokens": {
                **common,
                "payload.question_id": "hmac256:222222222222222222222222",
                "payload.reply_id": "hmac256:333333333333333333333333",
                "phase0.reconnect_seed": "hmac256:777777777777777777777777",
            },
        },
        {
            "action": "provider_reconnect_attempt",
            "at_ms": 1788310923450,
            "success": True,
            "provider_ordinal_before_attempt": 4,
            "session_token": session_token,
            "correlation_tokens": common,
        },
    ]
    if failed:
        events.append(_safe_event(event_id=153, ordinal=9))
        actions.append(
            {
                "action": "provider_reconnect_failed",
                "at_ms": 1788310924000,
                "success": False,
                "reason_code": "context_restore_failed",
                "provider_ordinal_after_reconnect": 9,
                "session_token": session_token,
                "correlation_tokens": common,
            }
        )
        return events, actions
    actions.extend(
        [
            {
                "action": "provider_reconnect_succeeded",
                "at_ms": 1788310923550,
                "success": True,
                "provider_ordinal_after_reconnect": 5,
                "session_token": session_token,
                "correlation_tokens": common,
            },
            {
                "action": "provider_reconnect_question_observed",
                "at_ms": 1788310923650,
                "success": True,
                "provider_event_ordinal": 6,
                "session_token": session_token,
                "correlation_tokens": {
                    **common,
                    "phase0.reconnect_question": "hmac256:888888888888888888888888",
                },
            },
            {
                "action": "provider_reconnect_context_confirmed",
                "at_ms": 1788310923900,
                "success": True,
                "provider_ordinal_after_ack": 8,
                "session_token": session_token,
                "correlation_tokens": {
                    **common,
                    "payload.question_id": "hmac256:222222222222222222222222",
                    "payload.reply_id": "hmac256:333333333333333333333333",
                },
            },
        ]
    )
    return events, actions


def _runtime_conditions() -> dict:
    return {
        "aec_enabled": True,
        "background_resume_tested": False,
        "bluetooth_tested": False,
        "chrome_desktop": True,
        "microphone_permission": True,
        "network_profile": "baseline",
        "real_provider": True,
        "speaker_output": True,
    }


def _report_id(run_id: str, capability_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"step006:{run_id}:{capability_key}"))


def _record(run_id: str, capability_key: str) -> dict:
    result = RESULT_BY_CAPABILITY[capability_key]
    status = STATUS_BY_RESULT[result]
    dimensions = _dimensions()
    reason_code, events, actions = _causal_payload(capability_key, result)
    payload = {
        "schema_version": PHASE0_RECORD_SCHEMA,
        "capability_status": status,
        "reason_code": reason_code,
        "degradation_mode": "next_turn",
        "event_evidence": events,
        "action_evidence": actions,
        "runtime_conditions": _runtime_conditions(),
        # A production validator must derive readiness itself rather than trust
        # this Phase0 diagnostic assertion.
        "production_import_ready": False,
    }
    without_hash = {
        "evidence_report_id": _report_id(run_id, capability_key),
        "evidence_run_id": run_id,
        "capability_key": capability_key,
        "verification_result": result,
        "source_type": "phase0_import",
        **dimensions,
        "evidence_fingerprint": _fingerprint(dimensions),
        "evidence_payload": payload,
        "tested_at": TESTED_AT,
        "verified_at": VERIFIED_AT if result == "passed" else None,
        "evidence_ttl_days_snapshot": TTL_DAYS,
        "expires_at": EXPIRES_AT if result == "passed" else None,
    }
    return {
        **without_hash,
        "report_sha256": _canonical_sha256(without_hash),
    }


def _bundle(run_id: str = RUN_ID) -> dict:
    without_hash = {
        "schema_version": PHASE0_BUNDLE_SCHEMA,
        "evidence_run_id": run_id,
        "record_count": len(VOICE_CAPABILITY_KEYS),
        "production_source_of_truth": False,
        "records": [_record(run_id, key) for key in VOICE_CAPABILITY_KEYS],
    }
    return {
        **without_hash,
        "bundle_sha256": _canonical_sha256(without_hash),
    }


def _rehash(bundle: dict) -> dict:
    for record in bundle.get("records", []):
        record["report_sha256"] = _canonical_sha256(
            {key: value for key, value in record.items() if key != "report_sha256"}
        )
    bundle["bundle_sha256"] = _canonical_sha256(
        {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    )
    return bundle


def _validator():
    # The attribute is intentionally absent before the production GREEN step.
    return getattr(capability_module, "validate_phase0_evidence_bundle")


def _importer():
    # The method is intentionally absent before the production GREEN step.
    return getattr(
        realtime_voice_capability_service,
        "import_phase0_evidence_bundle",
    )


def _seed_config_pair() -> tuple[dict, dict]:
    persona_ref = {
        "config_key": "persona",
        "version": 1,
        "content_sha256": "sha256:" + "1" * 64,
    }
    active = build_canonical_voice_seed_manifest(persona_ref)[VOICE_CALL_CONFIG_KEY]
    draft = deepcopy(active)
    draft["global"]["test_user_ids"] = [101]
    for capability in draft["capabilities"].values():
        capability["enabled"] = True
        capability["forced_enabled"] = True
        capability["effective_scope"] = "test"
    return active, draft


async def _seed_database(factory) -> dict[str, int]:
    active, draft = _seed_config_pair()
    fixed_now = datetime(2026, 9, 2, 1, 0, 0)
    ids: dict[str, int] = {}
    async with factory() as session:
        for role in (
            "super_admin",
            "tech_ops",
            "ai_trainer",
            "ops_admin",
            "observer",
        ):
            admin = AdminUser(
                username=f"step006-import-{role}",
                password_hash="not-used",
                role=role,
                is_active=True,
                is_locked=False,
                token_version=0,
            )
            session.add(admin)
            await session.flush()
            ids[role] = admin.id
        session.add_all(
            [
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(active),
                    version=7,
                    draft_revision=None,
                    is_active=True,
                    is_draft=False,
                    updated_by="existing-operator",
                    updated_at=fixed_now,
                ),
                AdminConfig(
                    config_key=VOICE_CALL_CONFIG_KEY,
                    config_value=canonical_json(draft),
                    version=0,
                    draft_revision=3,
                    is_active=False,
                    is_draft=True,
                    updated_by="existing-operator",
                    updated_at=fixed_now,
                ),
            ]
        )
        await session.commit()
    return ids


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch: pytest.MonkeyPatch):
    fake_redis.values.clear()
    fake_redis.ttls.clear()
    role_ids.clear()

    async def redis_provider():
        return fake_redis

    monkeypatch.setattr(capability_module, "get_redis", redis_provider, raising=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=list(_TABLES),
            )
        )
    role_ids.update(await _seed_database(session_factory))
    active, _ = _seed_config_pair()
    redis_key = f"active_config:{VOICE_CALL_CONFIG_KEY}"
    fake_redis.values[redis_key] = canonical_json(active)
    fake_redis.ttls[redis_key] = 611
    yield
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.drop_all(
                sync_connection,
                tables=list(reversed(_TABLES)),
            )
        )


def _set_unknown_bundle_field(bundle: dict) -> None:
    bundle["operator_id"] = 999


def _set_unknown_record_field(bundle: dict) -> None:
    bundle["records"][0]["created_at"] = TESTED_AT


def _set_unknown_payload_field(bundle: dict) -> None:
    bundle["records"][0]["evidence_payload"]["raw_report"] = "forbidden"


def _set_unknown_event_field(bundle: dict) -> None:
    bundle["records"][0]["evidence_payload"]["event_evidence"][0][
        "provider_raw"
    ] = "forbidden"


def _set_unknown_action_field(bundle: dict) -> None:
    bundle["records"][0]["evidence_payload"]["action_evidence"][0][
        "transcript"
    ] = "forbidden"


def _set_unknown_runtime_field(bundle: dict) -> None:
    bundle["records"][0]["evidence_payload"]["runtime_conditions"][
        "device_user_id"
    ] = 1


@pytest.mark.parametrize(
    "mutate",
    [
        _set_unknown_bundle_field,
        _set_unknown_record_field,
        _set_unknown_payload_field,
        _set_unknown_event_field,
        _set_unknown_action_field,
        _set_unknown_runtime_field,
    ],
    ids=["bundle", "record", "payload", "event", "action", "runtime"],
)
def test_phase0_v3_uses_strict_recursive_allowlists(mutate):
    validator = _validator()
    candidate = _bundle()
    mutate(candidate)
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        validator(candidate)


@pytest.mark.parametrize('location', ['record', 'payload', 'event', 'action', 'runtime'])
def test_raw_audio_field_rejected_even_with_valid_recomputed_hashes(location):
    candidate = _bundle()
    record = candidate['records'][0]
    payload = record['evidence_payload']
    target = {
        'record': record,
        'payload': payload,
        'event': payload['event_evidence'][0],
        'action': payload['action_evidence'][0],
        'runtime': payload['runtime_conditions'],
    }[location]
    target['audio_base64'] = 'U1lOVEhFVElDLUFVRElPLVNFTlRJTkVM'
    _rehash(candidate)
    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


def test_phase0_v3_recomputes_record_and_bundle_canonical_hashes():
    validator = _validator()
    valid = _bundle()
    normalized = validator(valid)
    assert normalized["bundle_sha256"] == valid["bundle_sha256"]
    assert [record["report_sha256"] for record in normalized["records"]] == [
        record["report_sha256"] for record in valid["records"]
    ]

    record_tampered = _bundle()
    record_tampered["records"][0]["evidence_payload"]["reason_code"] = (
        "tampered_without_report_rehash"
    )
    with pytest.raises(CapabilityStateError):
        validator(record_tampered)

    bundle_tampered = _bundle()
    bundle_tampered["records"][0]["evidence_payload"]["reason_code"] = (
        "tampered_without_bundle_rehash"
    )
    record = bundle_tampered["records"][0]
    record["report_sha256"] = _canonical_sha256(
        {key: value for key, value in record.items() if key != "report_sha256"}
    )
    with pytest.raises(CapabilityStateError):
        validator(bundle_tampered)


def _drop_last_record(bundle: dict) -> None:
    bundle["records"].pop()
    bundle["record_count"] = 5


def _duplicate_capability(bundle: dict) -> None:
    bundle["records"][-1]["capability_key"] = bundle["records"][0]["capability_key"]


def _duplicate_report_id(bundle: dict) -> None:
    bundle["records"][-1]["evidence_report_id"] = bundle["records"][0][
        "evidence_report_id"
    ]


def _mix_run_ids(bundle: dict) -> None:
    bundle["records"][-1]["evidence_run_id"] = SECOND_RUN_ID


@pytest.mark.parametrize(
    "mutate",
    [_drop_last_record, _duplicate_capability, _duplicate_report_id, _mix_run_ids],
    ids=["missing-capability", "duplicate-capability", "duplicate-report", "mixed-run"],
)
def test_phase0_bundle_requires_exactly_six_capabilities_in_one_run(mutate):
    validator = _validator()
    candidate = _bundle()
    mutate(candidate)
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        validator(candidate)


def _invalid_run_uuid(bundle: dict) -> None:
    bundle["evidence_run_id"] = "not-a-uuid"
    for record in bundle["records"]:
        record["evidence_run_id"] = "not-a-uuid"


def _invalid_report_uuid(bundle: dict) -> None:
    bundle["records"][0]["evidence_report_id"] = "not-a-uuid"


def _invalid_verification_result(bundle: dict) -> None:
    bundle["records"][0]["verification_result"] = "verified"


def _invalid_phase0_source(bundle: dict) -> None:
    bundle["records"][0]["source_type"] = "admin_capability_test"


def _invalid_payload_status_mapping(bundle: dict) -> None:
    bundle["records"][0]["evidence_payload"]["capability_status"] = "failed"


def _missing_dimension(bundle: dict) -> None:
    bundle["records"][0].pop("sdk_version")


def _fingerprint_mismatch(bundle: dict) -> None:
    bundle["records"][0]["evidence_fingerprint"] = "0" * 64


def _mixed_valid_dimensions(bundle: dict) -> None:
    record = bundle["records"][0]
    record["sdk_version"] = "websockets-99.0"
    record["evidence_fingerprint"] = _fingerprint(
        {field: record[field] for field in EVIDENCE_FINGERPRINT_FIELDS}
    )


def _ttl_below_minimum(bundle: dict) -> None:
    bundle["records"][0]["evidence_ttl_days_snapshot"] = 6


def _ttl_boolean(bundle: dict) -> None:
    bundle["records"][0]["evidence_ttl_days_snapshot"] = True


def _invalid_tested_at(bundle: dict) -> None:
    bundle["records"][0]["tested_at"] = "2026-09-02 01:02:03"


def _passed_without_verified_at(bundle: dict) -> None:
    bundle["records"][0]["verified_at"] = None
    bundle["records"][0]["expires_at"] = None


def _failed_with_verified_at(bundle: dict) -> None:
    record = bundle["records"][1]
    record["verified_at"] = VERIFIED_AT
    record["expires_at"] = EXPIRES_AT


def _incorrect_expiry(bundle: dict) -> None:
    bundle["records"][0]["expires_at"] = "2026-10-03T01:02:03Z"


@pytest.mark.parametrize(
    "mutate",
    [
        _invalid_run_uuid,
        _invalid_report_uuid,
        _invalid_verification_result,
        _invalid_phase0_source,
        _invalid_payload_status_mapping,
        _missing_dimension,
        _fingerprint_mismatch,
        _mixed_valid_dimensions,
        _ttl_below_minimum,
        _ttl_boolean,
        _invalid_tested_at,
        _passed_without_verified_at,
        _failed_with_verified_at,
        _incorrect_expiry,
    ],
    ids=[
        "run-uuid",
        "report-uuid",
        "result-enum",
        "source-enum",
        "status-result-map",
        "missing-dimension",
        "fingerprint-mismatch",
        "mixed-six-dimensions",
        "ttl-low",
        "ttl-bool",
        "tested-at",
        "passed-time",
        "failed-time",
        "expiry",
    ],
)
def test_phase0_v3_rejects_invalid_ids_enums_dimensions_ttl_and_times(mutate):
    validator = _validator()
    candidate = _bundle()
    mutate(candidate)
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        validator(candidate)


@pytest.mark.parametrize(
    ("path", "unsafe_value"),
    [
        ("reason_code", "sk-production-secret-1234567890"),
        ("reason_code", "Bearer abcdefghijklmnopqrstuvwxyz"),
        ("sentence_token", "用户手机号13800138000"),
        ("correlation_token", "raw-provider-session-id"),
        ("text_token", "用户真实转写正文"),
    ],
)
def test_phase0_v3_rejects_secret_raw_id_audio_transcript_and_pii_shapes(
    path: str,
    unsafe_value: str,
):
    validator = _validator()
    candidate = _bundle()
    payload = candidate["records"][0]["evidence_payload"]
    if path == "reason_code":
        payload["reason_code"] = unsafe_value
    elif path == "sentence_token":
        payload["action_evidence"][0]["sentence_token"] = unsafe_value
    elif path == "correlation_token":
        payload["event_evidence"][0]["correlation_tokens"][
            "frame.session_id"
        ] = unsafe_value
    else:
        payload["event_evidence"][0]["payload_shape"]["text_fields"] = {
            "payload.text": {"chars": 8, "token": unsafe_value}
        }
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        validator(candidate)


def test_production_flags_are_assertions_not_import_authority():
    validator = _validator()

    # False diagnostic flags cannot veto a bundle that the production
    # validator independently proves canonical and importable.
    normalized = validator(_bundle())
    assert len(normalized["records"]) == 6

    # Conversely, true flags cannot bless a bad fingerprint.
    forged = _bundle()
    forged["production_source_of_truth"] = True
    for record in forged["records"]:
        record["evidence_payload"]["production_import_ready"] = True
    forged["records"][0]["evidence_fingerprint"] = "f" * 64
    _rehash(forged)
    with pytest.raises(CapabilityStateError):
        validator(forged)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record["evidence_payload"].update(
            {
                "event_evidence": [_safe_event()],
                "action_evidence": [_safe_action()],
            }
        ),
        lambda record: record["evidence_payload"]["event_evidence"].pop(0),
    ],
    ids=["generic-unrelated-anchors", "missing-source-asr-anchor"],
)
def test_phase0_passed_recomputes_capability_specific_causality(mutate):
    """Hash-correct but irrelevant/incomplete evidence must not self-certify passed."""

    candidate = _bundle()
    record = candidate["records"][0]
    assert record["verification_result"] == "passed"
    mutate(record)
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


def test_rag_passed_allows_multiple_chunks_of_one_reply_but_one_terminal():
    candidate = _bundle()
    record = candidate["records"][0]
    events = record["evidence_payload"]["event_evidence"]
    second_chunk = deepcopy(events[1])
    second_chunk["ordinal"] = 3
    second_chunk["received_at_ms"] += 10
    second_chunk.pop("probe_match", None)
    events[-1]["ordinal"] = 4
    events[-1]["received_at_ms"] += 20
    events.insert(2, second_chunk)
    _rehash(candidate)

    assert _validator()(candidate)["records"][0]["verification_result"] == "passed"


def test_cancel_rejects_conflicting_stop_acks_for_same_token_and_generation():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_reply_cancel"
    )
    stop_ack = deepcopy(record["evidence_payload"]["action_evidence"][1])
    stop_ack["success"] = True
    record["evidence_payload"]["action_evidence"].append(stop_ack)
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


def test_mapping_accepts_adjacent_end_text_identity_without_sentence_id():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_playback_text_mapping"
    )
    events = record["evidence_payload"]["event_evidence"]
    for event in events:
        event["correlation_tokens"].pop("payload.sentence_id", None)
    start, _, end = events
    start["payload_shape"]["text_fields"] = {
        "payload.text": {
            "chars": 0,
            "token": "hmac256:999999999999999999999999",
        }
    }
    end["payload_shape"]["text_fields"] = {
        "payload.text": {
            "chars": 5,
            "token": "hmac256:aaaaaaaaaaaaaaaaaaaaaaaa",
        }
    }
    record["evidence_payload"]["reason_code"] = (
        "adjacent_provider_sentence_end_text_reply_session_correlates_with_audio"
    )
    _rehash(candidate)

    assert _validator()(candidate)["records"][3]["verification_result"] == "passed"


def test_mapping_failed_without_a_correlated_boundary_probe_is_not_trustworthy():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_playback_text_mapping"
    )
    record["verification_result"] = "failed"
    record["evidence_payload"]["capability_status"] = "failed"
    record["evidence_payload"]["reason_code"] = "correlated_sentence_window_contains_no_audio"
    record["evidence_payload"]["event_evidence"] = []
    record["verified_at"] = None
    record["expires_at"] = None
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


@pytest.mark.parametrize(
    "field",
    ["real_provider", "chrome_desktop", "microphone_permission", "aec_enabled"],
)
def test_phase0_passed_requires_core_real_runtime_conditions(field: str):
    candidate = _bundle()
    candidate["records"][0]["evidence_payload"]["runtime_conditions"][field] = False
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


def test_phase0_passed_rejects_evidence_already_expired_at_import_time():
    candidate = _bundle()
    expired_tested_at = "2020-01-01T00:00:00Z"
    for record in candidate["records"]:
        record["tested_at"] = expired_tested_at
        if record["verification_result"] == "passed":
            record["verified_at"] = expired_tested_at
            record["expires_at"] = "2020-01-31T00:00:00Z"
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


@pytest.mark.parametrize(
    ("result", "reason", "failed"),
    [
        ("passed", "hidden_seed_preserved_across_same_session_reconnect", False),
        (
            "failed",
            "same_session_reconnect_or_hidden_context_restore_failed",
            True,
        ),
    ],
)
def test_reconnect_accepts_only_complete_phase0_causal_slice(
    result: str,
    reason: str,
    failed: bool,
):
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_session_reconnect"
    )
    events, actions = _reconnect_causal_slice(failed=failed)
    record["verification_result"] = result
    record["evidence_payload"]["capability_status"] = STATUS_BY_RESULT[result]
    record["evidence_payload"]["reason_code"] = reason
    record["evidence_payload"]["event_evidence"] = events
    record["evidence_payload"]["action_evidence"] = actions
    record["verified_at"] = VERIFIED_AT if result == "passed" else None
    record["expires_at"] = EXPIRES_AT if result == "passed" else None
    _rehash(candidate)

    normalized = _validator()(candidate)
    stored = next(
        item
        for item in normalized["records"]
        if item["capability_key"] == "supports_session_reconnect"
    )
    assert stored["verification_result"] == result


def test_phase0_accepts_real_segmented_rag_and_action_shapes():
    candidate = _bundle()
    rag = candidate["records"][0]
    source = rag["evidence_payload"]["event_evidence"][0]
    action = rag["evidence_payload"]["action_evidence"][0]
    source["correlation_tokens"].pop("payload.reply_id")
    source["correlation_tokens"]["phase0.asr_question"] = (
        "hmac256:999999999999999999999999"
    )
    action["correlation_tokens"]["phase0.asr_question"] = (
        source["correlation_tokens"]["phase0.asr_question"]
    )

    for capability in {"supports_reply_cancel", "supports_context_truncate"}:
        record = next(
            item for item in candidate["records"] if item["capability_key"] == capability
        )
        interrupt = next(
            item
            for item in record["evidence_payload"]["action_evidence"]
            if item["action"] == "client_interrupt_sent"
        )
        interrupt["correlation_tokens"].pop("frame.session_id")

    ack = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_sentence_playback_ack"
    )
    ack_action = next(
        item
        for item in ack["evidence_payload"]["action_evidence"]
        if item["action"] == "client_sentence_played"
    )
    ack_action.pop("correlation_tokens")
    _rehash(candidate)

    normalized = _validator()(candidate)
    assert len(normalized["records"]) == len(VOICE_CAPABILITY_KEYS)


def test_mapping_no_audio_reason_is_precise():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_playback_text_mapping"
    )
    record["verification_result"] = "failed"
    record["evidence_payload"]["capability_status"] = "failed"
    record["evidence_payload"]["reason_code"] = (
        "correlated_sentence_window_contains_no_audio"
    )
    record["evidence_payload"]["event_evidence"] = [
        event
        for event in record["evidence_payload"]["event_evidence"]
        if event["event_name"] != "TTSResponse"
    ]
    record["verified_at"] = None
    record["expires_at"] = None
    _rehash(candidate)
    assert _validator()(candidate)["records"][3]["verification_result"] == "failed"

    forged = deepcopy(candidate)
    forged_record = forged["records"][3]
    forged_record["evidence_payload"]["event_evidence"].append(
        _safe_event(event_id=352, ordinal=2, audio=True, sentence_boundary=True)
    )
    forged_record["evidence_payload"]["event_evidence"][1]["ordinal"] = 4
    _rehash(forged)
    with pytest.raises(CapabilityStateError):
        _validator()(forged)


def test_truncate_failed_reason_tracks_current_authoritative_event_map():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_context_truncate"
    )
    record["evidence_payload"]["reason_code"] = (
        "conversation_truncated_event_id_not_authoritative"
    )
    _rehash(candidate)
    assert _validator()(candidate)["records"][2]["verification_result"] == "failed"

    forged = deepcopy(candidate)
    forged["records"][2]["evidence_payload"]["reason_code"] = (
        "conversation_truncated_event_not_observed"
    )
    _rehash(forged)
    with pytest.raises(CapabilityStateError):
        _validator()(forged)


@pytest.mark.parametrize("failure_anchor", ["action_only", "event_only"])
def test_reconnect_transport_failure_accepts_one_real_anchor(failure_anchor: str):
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_session_reconnect"
    )
    events, actions = _reconnect_causal_slice(failed=True)
    if failure_anchor == "action_only":
        events = [event for event in events if event["event_name"] != "SessionFailed"]
    else:
        actions = [
            action for action in actions if action["action"] != "provider_reconnect_failed"
        ]
    record["verification_result"] = "failed"
    record["evidence_payload"]["capability_status"] = "failed"
    record["evidence_payload"]["reason_code"] = (
        "same_session_reconnect_or_hidden_context_restore_failed"
    )
    record["evidence_payload"]["event_evidence"] = events
    record["evidence_payload"]["action_evidence"] = actions
    record["verified_at"] = None
    record["expires_at"] = None
    _rehash(candidate)
    assert _validator()(candidate)["records"][5]["verification_result"] == "failed"


def test_reconnect_accepts_false_context_confirmation_and_lifecycle_boundary():
    candidate = _bundle()
    record = next(
        item
        for item in candidate["records"]
        if item["capability_key"] == "supports_session_reconnect"
    )
    events, actions = _reconnect_causal_slice()
    actions[-1]["success"] = False
    record["verification_result"] = "failed"
    record["evidence_payload"]["capability_status"] = "failed"
    record["evidence_payload"]["reason_code"] = (
        "same_session_reconnect_or_hidden_context_restore_failed"
    )
    record["evidence_payload"]["event_evidence"] = events
    record["evidence_payload"]["action_evidence"] = actions
    record["verified_at"] = None
    record["expires_at"] = None
    _rehash(candidate)
    assert _validator()(candidate)["records"][5]["verification_result"] == "failed"

    lifecycle = deepcopy(candidate)
    lifecycle_record = lifecycle["records"][5]
    lifecycle_record["evidence_payload"]["reason_code"] = (
        "same_session_reconnect_lifecycle_changed_after_handshake"
    )
    lifecycle_record["evidence_payload"]["action_evidence"][-1]["success"] = True
    lifecycle_events = lifecycle_record["evidence_payload"]["event_evidence"]
    for event in lifecycle_events[5:]:
        event["ordinal"] += 1
    boundary = _safe_event(event_id=152, ordinal=6)
    lifecycle_events.insert(5, boundary)
    question = lifecycle_record["evidence_payload"]["action_evidence"][-2]
    confirmation = lifecycle_record["evidence_payload"]["action_evidence"][-1]
    question["provider_event_ordinal"] = 7
    confirmation["provider_ordinal_after_ack"] = 9
    _rehash(lifecycle)
    assert _validator()(lifecycle)["records"][5]["verification_result"] == "failed"


def test_reconnect_seed_exposure_uses_failure_action_semantics():
    candidate = _bundle()
    record = candidate["records"][5]
    record["evidence_payload"]["action_evidence"][0]["success"] = False
    _rehash(candidate)
    assert _validator()(candidate)["records"][5]["verification_result"] == "failed"


@pytest.mark.parametrize("unsafe_dimension", ["用户真实转写正文", "sdk version with spaces"])
def test_phase0_dimensions_use_frozen_safe_code_syntax(unsafe_dimension: str):
    candidate = _bundle()
    for record in candidate["records"]:
        record["sdk_version"] = unsafe_dimension
        record["evidence_fingerprint"] = _fingerprint(
            {field: record[field] for field in EVIDENCE_FINGERPRINT_FIELDS}
        )
    _rehash(candidate)

    with pytest.raises(CapabilityStateError):
        _validator()(candidate)


def test_phase0_error_unverified_is_diagnostic_only_and_never_import_ready():
    validator = _validator()
    diagnostic = _bundle()
    record = diagnostic["records"][0]
    record["verification_result"] = "error"
    record["evidence_payload"]["capability_status"] = "unverified"
    record["verified_at"] = None
    record["expires_at"] = None
    _rehash(diagnostic)

    with pytest.raises(CapabilityStateError):
        validator(diagnostic)


async def _config_rows(factory=session_factory) -> tuple[AdminConfig, AdminConfig]:
    async with factory() as session:
        rows = (
            await session.execute(
                select(AdminConfig)
                .where(AdminConfig.config_key == VOICE_CALL_CONFIG_KEY)
                .order_by(AdminConfig.is_draft.asc())
            )
        ).scalars().all()
        active = next(row for row in rows if row.is_active and not row.is_draft)
        draft = next(row for row in rows if row.is_draft and not row.is_active)
        return active, draft


async def _stable_state(factory=session_factory) -> dict:
    async with factory() as session:
        config_rows = (
            await session.execute(
                select(AdminConfig)
                .where(AdminConfig.config_key == VOICE_CALL_CONFIG_KEY)
                .order_by(AdminConfig.id.asc())
            )
        ).scalars().all()
        evidence_rows = (
            await session.execute(
                select(VoiceCapabilityEvidence).order_by(
                    VoiceCapabilityEvidence.evidence_report_id.asc()
                )
            )
        ).scalars().all()
        audit_rows = (
            await session.execute(
                select(AdminOperationLog).order_by(AdminOperationLog.id.asc())
            )
        ).scalars().all()
        return {
            "configs": [
                (
                    row.id,
                    row.config_key,
                    row.version,
                    row.draft_revision,
                    row.is_active,
                    row.is_draft,
                    row.config_value,
                    row.updated_by,
                )
                for row in config_rows
            ],
            "evidence": [
                (
                    row.id,
                    row.evidence_report_id,
                    row.evidence_run_id,
                    row.capability_key,
                    row.verification_result,
                    row.report_sha256,
                    canonical_json(row.evidence_payload),
                    row.operator_id,
                )
                for row in evidence_rows
            ],
            "audit": [
                (
                    row.id,
                    row.admin_user_id,
                    row.admin_username,
                    row.module,
                    row.action,
                    row.target_description,
                    row.before_value,
                    row.after_value,
                )
                for row in audit_rows
            ],
        }


def _redis_state() -> tuple[dict[str, str], dict[str, int]]:
    return deepcopy(fake_redis.values), deepcopy(fake_redis.ttls)


async def _import(
    bundle: dict,
    *,
    operator_role: str = "super_admin",
    factory=session_factory,
):
    importer = _importer()
    async with factory() as session:
        result = await importer(
            session,
            bundle=bundle,
            operator_id=role_ids[operator_role],
        )
        assert not session.in_transaction(), "import service must own and close its transaction"
        return result


@pytest.mark.asyncio
@pytest.mark.parametrize("operator_role", ["super_admin", "tech_ops"])
async def test_import_projects_passed_failed_and_atomically_appends_six_rows_draft_and_audit(
    operator_role: str,
):
    bundle = _bundle()
    active_before, draft_before = await _config_rows()
    active_projection_before = (
        active_before.id,
        active_before.version,
        active_before.config_value,
        active_before.updated_by,
    )
    redis_before = _redis_state()

    result = await _import(bundle, operator_role=operator_role)
    assert isinstance(result, dict)

    async with session_factory() as session:
        evidence_rows = (
            await session.execute(
                select(VoiceCapabilityEvidence).order_by(
                    VoiceCapabilityEvidence.capability_key.asc()
                )
            )
        ).scalars().all()
        audits = (
            await session.execute(select(AdminOperationLog))
        ).scalars().all()
    active_after, draft_after = await _config_rows()

    assert len(evidence_rows) == 6
    expected_by_key = {record["capability_key"]: record for record in bundle["records"]}
    for row in evidence_rows:
        expected = expected_by_key[row.capability_key]
        assert row.evidence_report_id == expected["evidence_report_id"]
        assert row.evidence_run_id == RUN_ID
        assert row.verification_result == expected["verification_result"]
        assert row.source_type == "phase0_import"
        assert {
            field: getattr(row, field) for field in EVIDENCE_FINGERPRINT_FIELDS
        } == _dimensions()
        assert row.evidence_fingerprint == expected["evidence_fingerprint"]
        assert row.report_sha256 == expected["report_sha256"]
        assert row.evidence_payload == expected["evidence_payload"]
        assert row.evidence_ttl_days_snapshot == TTL_DAYS
        assert row.operator_id == role_ids[operator_role]

    draft_config = json.loads(draft_after.config_value)
    for capability_key, result_name in RESULT_BY_CAPABILITY.items():
        capability = draft_config["capabilities"][capability_key]
        expected = expected_by_key[capability_key]
        assert capability["verification_status"] == STATUS_BY_RESULT[result_name]
        assert capability["last_test_result"] == result_name
        assert capability["enabled"] is False
        assert capability["forced_enabled"] is False
        assert capability["effective_scope"] == "off"
        assert {
            field: capability[field] for field in EVIDENCE_FINGERPRINT_FIELDS
        } == _dimensions()
        assert capability["evidence_fingerprint"] == expected["evidence_fingerprint"]
        assert capability["evidence_report_id"] == expected["evidence_report_id"]
        assert capability["evidence_ttl_days"] == TTL_DAYS
        if result_name == "passed":
            assert capability["verified_at"] == VERIFIED_AT
            assert capability["expires_at"] == EXPIRES_AT
        else:
            assert capability["verified_at"] is None
            assert capability["expires_at"] is None

    assert draft_after.id == draft_before.id
    assert draft_after.draft_revision == draft_before.draft_revision + 1
    assert (
        active_after.id,
        active_after.version,
        active_after.config_value,
        active_after.updated_by,
    ) == active_projection_before
    assert _redis_state() == redis_before
    assert len(audits) == 1
    assert audits[0].admin_user_id == role_ids[operator_role]
    assert audits[0].admin_username == f"step006-import-{operator_role}"
    assert audits[0].module == "voice_config"
    assert audits[0].action == "import_evidence"


@pytest.mark.asyncio
async def test_admin_capability_error_appends_one_record_and_projects_only_target_unverified_off():
    record = _record(SECOND_RUN_ID, VOICE_CAPABILITY_KEYS[0])
    record["source_type"] = "admin_capability_test"
    record["verification_result"] = "error"
    record["evidence_payload"]["capability_status"] = "unverified"
    record["evidence_payload"]["runtime_conditions"] = {
        "real_provider": True,
        "network_profile": "admin_test",
    }
    record["verified_at"] = None
    record["expires_at"] = None
    record["report_sha256"] = _canonical_sha256(
        {key: value for key, value in record.items() if key != "report_sha256"}
    )
    append = getattr(
        realtime_voice_capability_service,
        "append_admin_capability_evidence",
    )
    _, draft_before = await _config_rows()
    before_config = json.loads(draft_before.config_value)

    async with session_factory() as session:
        result = await append(
            session,
            record=record,
            operator_id=role_ids["tech_ops"],
        )
        assert isinstance(result, dict)
        assert not session.in_transaction()

    async with session_factory() as session:
        evidence_rows = (
            await session.execute(select(VoiceCapabilityEvidence))
        ).scalars().all()
    _, draft_after = await _config_rows()
    after_config = json.loads(draft_after.config_value)

    assert len(evidence_rows) == 1
    assert evidence_rows[0].verification_result == "error"
    assert evidence_rows[0].source_type == "admin_capability_test"
    target = after_config["capabilities"][VOICE_CAPABILITY_KEYS[0]]
    assert target["verification_status"] == "unverified"
    assert target["last_test_result"] == "error"
    assert target["enabled"] is False
    assert target["forced_enabled"] is False
    assert target["effective_scope"] == "off"
    for capability_key in VOICE_CAPABILITY_KEYS[1:]:
        assert after_config["capabilities"][capability_key] == before_config[
            "capabilities"
        ][capability_key]


@pytest.mark.asyncio
async def test_new_report_ids_cannot_duplicate_existing_run_capabilities():
    bundle = _bundle()
    await _import(bundle)
    before, redis_before = await _stable_state(), _redis_state()
    changed = deepcopy(bundle)
    for record in changed['records']:
        record['evidence_report_id'] = str(uuid.uuid4())
    _rehash(changed)
    # Prove this reaches duplicate identity checking, rather than failing syntax.
    _validator()(changed)
    async with session_factory() as session:
        with pytest.raises(CapabilityStateError) as caught:
            await _importer()(session, bundle=changed, operator_id=role_ids['tech_ops'])
        assert not session.in_transaction()
    assert caught.value.code == 'VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT'
    assert await _stable_state() == before
    assert _redis_state() == redis_before


@pytest.mark.asyncio
async def test_complete_bundle_replay_is_idempotent_without_duplicate_rows_or_draft_revision():
    bundle = _bundle()
    await _import(bundle)
    first = await _stable_state()
    redis_before = _redis_state()

    replay_result = await _import(deepcopy(bundle))
    assert isinstance(replay_result, dict)
    second = await _stable_state()

    assert second["evidence"] == first["evidence"]
    assert second["configs"] == first["configs"]
    assert _redis_state() == redis_before


@pytest.mark.asyncio
async def test_replay_requires_the_exact_canonical_bundle_not_only_identical_records():
    bundle = _bundle()
    await _import(bundle)
    before = await _stable_state()

    conflicting = deepcopy(bundle)
    conflicting["production_source_of_truth"] = True
    conflicting["bundle_sha256"] = _canonical_sha256(
        {
            key: value
            for key, value in conflicting.items()
            if key != "bundle_sha256"
        }
    )

    importer = _importer()
    async with session_factory() as session:
        with pytest.raises(CapabilityStateError) as caught:
            await importer(
                session,
                bundle=conflicting,
                operator_id=role_ids["tech_ops"],
            )
        assert not session.in_transaction()

    assert caught.value.code == "VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT"
    assert await _stable_state() == before


@pytest.mark.asyncio
async def test_same_id_with_different_canonical_content_is_conflict_without_state_change():
    bundle = _bundle()
    await _import(bundle)
    before = await _stable_state()
    redis_before = _redis_state()

    conflicting = deepcopy(bundle)
    conflicting["records"][0]["evidence_payload"]["reason_code"] = (
        "different_but_well_formed_content"
    )
    _rehash(conflicting)
    importer = _importer()
    async with session_factory() as session:
        with pytest.raises(CapabilityStateError):
            await importer(
                session,
                bundle=conflicting,
                operator_id=role_ids["super_admin"],
            )
        assert not session.in_transaction()

    after = await _stable_state()
    assert after["evidence"] == before["evidence"]
    assert after["configs"] == before["configs"]
    assert _redis_state() == redis_before


@pytest.mark.asyncio
@pytest.mark.parametrize("operator_role", ["ai_trainer", "ops_admin", "observer"])
async def test_import_requeries_operator_from_db_and_accepts_only_super_admin_or_tech_ops(
    operator_role: str,
):
    importer = _importer()
    before = await _stable_state()
    async with session_factory() as session:
        with pytest.raises((CapabilityStateError, PermissionError)):
            await importer(
                session,
                bundle=_bundle(),
                operator_id=role_ids[operator_role],
            )
        assert not session.in_transaction()
    after = await _stable_state()
    assert after["evidence"] == before["evidence"]
    assert after["configs"] == before["configs"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operator_field", "operator_value"),
    [("is_active", False), ("is_locked", True)],
)
@pytest.mark.parametrize("write_path", ["phase0_import", "admin_append"])
async def test_disabled_or_locked_operator_cannot_import_or_append_evidence(
    operator_field: str,
    operator_value: bool,
    write_path: str,
):
    operator_id = role_ids["tech_ops"]
    async with session_factory() as session:
        operator = await session.get(AdminUser, operator_id)
        setattr(operator, operator_field, operator_value)
        await session.commit()

    before = await _stable_state()
    redis_before = _redis_state()
    async with session_factory() as session:
        with pytest.raises(CapabilityEvidenceAccessError):
            if write_path == "phase0_import":
                await _importer()(
                    session,
                    bundle=_bundle(),
                    operator_id=operator_id,
                )
            else:
                record = _record(SECOND_RUN_ID, VOICE_CAPABILITY_KEYS[0])
                record["source_type"] = "admin_capability_test"
                record["verification_result"] = "error"
                record["evidence_payload"]["capability_status"] = "unverified"
                record["evidence_payload"]["runtime_conditions"] = {
                    "real_provider": True,
                    "network_profile": "admin_test",
                }
                record["verified_at"] = None
                record["expires_at"] = None
                record["report_sha256"] = _canonical_sha256(
                    {
                        key: value
                        for key, value in record.items()
                        if key != "report_sha256"
                    }
                )
                await realtime_voice_capability_service.append_admin_capability_evidence(
                    session,
                    record=record,
                    operator_id=operator_id,
                )
        assert not session.in_transaction()

    assert await _stable_state() == before
    assert _redis_state() == redis_before


async def _install_sqlite_failure_trigger(stage: str) -> None:
    sql_by_stage = {
        "evidence": """
            CREATE TRIGGER step006_abort_evidence
            BEFORE INSERT ON voice_capability_evidence
            WHEN NEW.capability_key = 'supports_context_truncate'
            BEGIN
                SELECT RAISE(ABORT, 'controlled evidence append failure');
            END
        """,
        "projection": """
            CREATE TRIGGER step006_abort_projection
            BEFORE UPDATE ON admin_config
            WHEN NEW.config_key = 'voice_call_config' AND NEW.is_draft = 1
            BEGIN
                SELECT RAISE(ABORT, 'controlled draft projection failure');
            END
        """,
        "audit": """
            CREATE TRIGGER step006_abort_audit
            BEFORE INSERT ON admin_operation_logs
            BEGIN
                SELECT RAISE(ABORT, 'controlled audit failure');
            END
        """,
    }
    async with engine.begin() as connection:
        await connection.execute(text(sql_by_stage[stage]))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["evidence", "projection", "audit"])
async def test_any_transaction_stage_failure_rolls_back_six_rows_draft_projection_and_audit(
    failure_stage: str,
):
    await _install_sqlite_failure_trigger(failure_stage)
    before = await _stable_state()
    redis_before = _redis_state()
    importer = _importer()

    async with session_factory() as session:
        with pytest.raises(Exception):
            await importer(
                session,
                bundle=_bundle(),
                operator_id=role_ids["super_admin"],
            )
        assert not session.in_transaction(), "failed import must rollback its transaction"

    assert await _stable_state() == before
    assert _redis_state() == redis_before


def _mysql_async_url(database_name: str) -> str:
    user = quote_plus(os.getenv("MYSQL_USER", "lxm"))
    password = quote_plus(os.getenv("MYSQL_PASSWORD", "lxm123456"))
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    return f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database_name}"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv(MYSQL_DATABASE_ENV),
    reason=f"需要设置空的隔离 MySQL 8 库名 {MYSQL_DATABASE_ENV}",
)
async def test_mysql_import_commits_six_rows_draft_projection_and_audit_in_one_transaction():
    database_name = os.environ[MYSQL_DATABASE_ENV]
    mysql_engine = create_async_engine(_mysql_async_url(database_name))
    mysql_factory = async_sessionmaker(
        mysql_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    created_test_tables = False
    try:
        async with mysql_engine.begin() as connection:
            existing = await connection.run_sync(
                lambda sync_connection: set(
                    __import__("sqlalchemy").inspect(sync_connection).get_table_names()
                )
            )
            assert not existing, "隔离 MySQL 库必须为空库"
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=list(_TABLES),
                )
            )
            created_test_tables = True

        mysql_role_ids = await _seed_database(mysql_factory)
        importer = _importer()
        async with mysql_factory() as session:
            await importer(
                session,
                bundle=_bundle(),
                operator_id=mysql_role_ids["super_admin"],
            )
            assert not session.in_transaction()

        state = await _stable_state(mysql_factory)
        assert len(state["evidence"]) == 6
        assert len(state["audit"]) == 1
        draft = next(row for row in state["configs"] if row[5] is True)
        assert draft[3] == 4
        active = next(row for row in state["configs"] if row[4] is True)
        assert active[2] == 7
    finally:
        if created_test_tables:
            async with mysql_engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: Base.metadata.drop_all(
                        sync_connection,
                        tables=list(reversed(_TABLES)),
                    )
                )
        await mysql_engine.dispose()


async def _create_empty_mysql_test_schema():
    database_name = os.environ[MYSQL_DATABASE_ENV]
    mysql_engine = create_async_engine(_mysql_async_url(database_name))
    mysql_factory = async_sessionmaker(
        mysql_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with mysql_engine.begin() as connection:
        existing = await connection.run_sync(
            lambda sync_connection: set(
                __import__("sqlalchemy").inspect(sync_connection).get_table_names()
            )
        )
        assert not existing, "隔离 MySQL 库必须为空库"
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=list(_TABLES),
            )
        )
    mysql_role_ids = await _seed_database(mysql_factory)
    return mysql_engine, mysql_factory, mysql_role_ids


async def _drop_mysql_test_schema(mysql_engine) -> None:
    async with mysql_engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.drop_all(
                sync_connection,
                tables=list(reversed(_TABLES)),
            )
        )
    await mysql_engine.dispose()


class _ControlledMySqlStageFailure(RuntimeError):
    pass


def _install_mysql_statement_failure(mysql_engine, stage: str):
    prefix_by_stage = {
        "evidence": "insert into voice_capability_evidence",
        "projection": "update admin_config set",
        "audit": "insert into admin_operation_logs",
    }
    expected_prefix = prefix_by_stage[stage]
    state = {"fired": False}

    def fail_matching_statement(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        normalized = " ".join(statement.lower().replace("`", "").split())
        if not state["fired"] and normalized.startswith(expected_prefix):
            state["fired"] = True
            raise _ControlledMySqlStageFailure(
                f"controlled {stage} statement failure"
            )

    event.listen(
        mysql_engine.sync_engine,
        "before_cursor_execute",
        fail_matching_statement,
    )
    return fail_matching_statement, state


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv(MYSQL_DATABASE_ENV),
    reason=f"需要设置空的隔离 MySQL 8 库名 {MYSQL_DATABASE_ENV}",
)
@pytest.mark.parametrize("failure_stage", ["evidence", "projection", "audit"])
async def test_mysql_each_import_stage_failure_rolls_back_evidence_projection_and_audit(
    failure_stage: str,
):
    mysql_engine, mysql_factory, mysql_role_ids = (
        await _create_empty_mysql_test_schema()
    )
    listener, listener_state = _install_mysql_statement_failure(
        mysql_engine,
        failure_stage,
    )
    try:
        before = await _stable_state(mysql_factory)
        importer = _importer()
        async with mysql_factory() as session:
            with pytest.raises(_ControlledMySqlStageFailure):
                await importer(
                    session,
                    bundle=_bundle(),
                    operator_id=mysql_role_ids["super_admin"],
                )
            assert not session.in_transaction()

        assert listener_state["fired"] is True
        assert await _stable_state(mysql_factory) == before
    finally:
        event.remove(
            mysql_engine.sync_engine,
            "before_cursor_execute",
            listener,
        )
        await _drop_mysql_test_schema(mysql_engine)


async def _mysql_import_once(mysql_factory, *, bundle: dict, operator_id: int):
    async with mysql_factory() as session:
        result = await _importer()(
            session,
            bundle=deepcopy(bundle),
            operator_id=operator_id,
        )
        assert not session.in_transaction()
        return result


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv(MYSQL_DATABASE_ENV),
    reason=f"需要设置空的隔离 MySQL 8 库名 {MYSQL_DATABASE_ENV}",
)
async def test_mysql_different_operators_concurrently_import_exact_bundle_once():
    mysql_engine, mysql_factory, mysql_role_ids = (
        await _create_empty_mysql_test_schema()
    )
    try:
        bundle = _bundle()
        results = await asyncio.gather(
            _mysql_import_once(
                mysql_factory,
                bundle=bundle,
                operator_id=mysql_role_ids["super_admin"],
            ),
            _mysql_import_once(
                mysql_factory,
                bundle=bundle,
                operator_id=mysql_role_ids["tech_ops"],
            ),
        )

        assert sorted(result["idempotent"] for result in results) == [False, True]
        state = await _stable_state(mysql_factory)
        assert len(state["evidence"]) == 6
        assert len(state["audit"]) == 1
        draft = next(row for row in state["configs"] if row[5] is True)
        active = next(row for row in state["configs"] if row[4] is True)
        assert draft[3] == 4
        assert active[2] == 7
    finally:
        await _drop_mysql_test_schema(mysql_engine)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv(MYSQL_DATABASE_ENV),
    reason=f"需要设置空的隔离 MySQL 8 库名 {MYSQL_DATABASE_ENV}",
)
async def test_mysql_same_run_different_canonical_bundles_concurrently_conflict_cleanly():
    mysql_engine, mysql_factory, mysql_role_ids = (
        await _create_empty_mysql_test_schema()
    )
    try:
        first_bundle = _bundle()
        second_bundle = deepcopy(first_bundle)
        second_bundle["production_source_of_truth"] = True
        second_bundle["bundle_sha256"] = _canonical_sha256(
            {
                key: value
                for key, value in second_bundle.items()
                if key != "bundle_sha256"
            }
        )

        outcomes = await asyncio.gather(
            _mysql_import_once(
                mysql_factory,
                bundle=first_bundle,
                operator_id=mysql_role_ids["super_admin"],
            ),
            _mysql_import_once(
                mysql_factory,
                bundle=second_bundle,
                operator_id=mysql_role_ids["tech_ops"],
            ),
            return_exceptions=True,
        )

        successes = [outcome for outcome in outcomes if isinstance(outcome, dict)]
        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        assert len(successes) == 1
        assert successes[0]["idempotent"] is False
        assert len(failures) == 1
        assert isinstance(failures[0], CapabilityStateError)
        assert failures[0].code == "VOICE_CAPABILITY_EVIDENCE_IMPORT_CONFLICT"

        state = await _stable_state(mysql_factory)
        assert len(state["evidence"]) == 6
        assert len(state["audit"]) == 1
        draft = next(row for row in state["configs"] if row[5] is True)
        active = next(row for row in state["configs"] if row[4] is True)
        assert draft[3] == 4
        assert active[2] == 7
    finally:
        await _drop_mysql_test_schema(mysql_engine)
