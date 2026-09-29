"""Internal, playback-only review of an already observed admin test.

A review does not rerun a Provider request or upgrade the original error report.
It appends an unverified admin diagnostic and a separate playback review audit.
No public route, new storage fields, or production capability grant is involved.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.services import realtime_voice_capability_service as evidence

ACK_KEY = "supports_sentence_playback_ack"
REVIEW_REASON = "admin_playback_review_only"
REVIEW_SCHEMA = "m1-admin-playback-review/v1"
_SOURCE_FIELDS = frozenset({
    "bundle", "session", "consumed_attempt", "user_start", "human_confirmation",
    "failed_test", "ack_report_id", "events_report_id",
})


# This is a one-off recovery for the user-confirmed 2026-09-09 admin playback.
# Hashes are pinned from the immutable captured sources before DB import; they
# are NOT supplied by the caller. Future tests need their own approved review.
# Authority: execution/实时语音通话开发执行记录.md §28.18, eighth manual playback.
_AUTHORIZED_SOURCE_HASHES = {
    "bundle": "7cd5df47e27fe22ce37273f319c87f8f6329830f655d4a4843ba18814a4b90e9",
    "session": "9df11a15970867ec8195a8bed78f2a20a10b3980a8544aac4c3a0af8d89ddaff",
    "consumed_attempt": "299518fc2cd0bf84cb5bad7ba73683a6b8155251e0d7e03c97f15be7d65ce52f",
    "user_start": "884f438d99e4aa9bc744fba19615e069f4c5a8a2ab2b2edfd2d8df623227a15c",
    "human_confirmation": "4a2672f8e2b84d7d37b77be0d6be01baff9437c3da2a272d5f514eba4d1d1912",
    "failed_test": "8909831168e29f4d034fc3296a3f12b408b5fcb619db50efe726f723a61adf8b",
    "ack_report_id": "5290e107e06be59d149b3cd7ba943fe4d29449d4f1cc6437a6344c08e7c0cb7f",
    "events_report_id": "a4bc37258346d48405684348f3c9ae6c6ef86d95be5c4014dafb4287fbd7036a"
}


def _hash(value: Any) -> str:
    return evidence._canonical_sha256(value, path="admin_playback_review")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Review timestamps require a timezone")
    return parsed.astimezone(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_admin_playback_review(sources: Mapping[str, Any]) -> dict[str, Any]:
    """Check source hashes, exact session/ACK causality and human confirmation.

    Original microphone/AEC conditions remain untouched. The causal assessment
    below is a new *playback review*, not a replacement capability conclusion.
    """
    _require(isinstance(sources, Mapping) and set(sources) == _SOURCE_FIELDS,
             "Review requires the exact original source set")
    _require({name: _hash(value) for name, value in sources.items()} == _AUTHORIZED_SOURCE_HASHES,
             "Sources differ from the user-confirmed original admin playback")
    bundle = sources["bundle"]
    selected = evidence.validate_phase0_evidence_selection(
        bundle, report_ids=[sources["ack_report_id"], sources["events_report_id"]],
    )
    by_id = {r["evidence_report_id"]: r for r in selected["records"]}
    original = by_id[sources["ack_report_id"]]
    events_report = by_id[sources["events_report_id"]]
    _require(original["capability_key"] == ACK_KEY
             and original["verification_result"] == "error"
             and original["evidence_payload"]["reason_code"] == "real_provider_device_runtime_not_proven",
             "Only the original runtime-unproven admin playback diagnostic can be reviewed")
    session = sources["session"]
    human = sources["human_confirmation"]
    attempt = sources["consumed_attempt"]
    failed = sources["failed_test"]
    _require(str(UUID(session["session_id"])) == session["session_id"]
             and session["evidence_run_id"] == bundle["evidence_run_id"],
             "Original session and run must match")
    _require(human.get("source") == "user_conversation" and human.get("heard") is True
             and human.get("session_id") == session["session_id"]
             and isinstance(human.get("statement"), str) and bool(human["statement"].strip()),
             "Missing same-session human hearing confirmation")
    _require(attempt.get("schema_version") == "m1-campaign-provider-attempt-receipt/v1"
             and attempt.get("attempt_kind") == "admin_ack"
             and type(attempt.get("attempt_ordinal")) is int and attempt["attempt_ordinal"] > 0,
             "Must reference a consumed admin ACK attempt")
    UUID(attempt["attempt_id"])
    _require(failed.get("code") == 0 and isinstance(failed.get("data"), dict),
             "Missing original admin API envelope")
    result = failed["data"]
    _require(result.get("status") == "error" and result.get("failure_category") == "evidence_invalid"
             and result.get("capability_key") == ACK_KEY
             and result.get("evidence_run_id") is None and result.get("evidence_report_id") is None
             and result.get("test_version") == "admin-voice-test/v1"
             and type(result.get("tested_draft_revision")) is int,
             "Original admin failure must target this playback test")
    start = _time(sources["user_start"]["started_at"])
    consumed = _time(attempt["consumed_at"])
    tested = _time(original["tested_at"])
    finished = _time(result["tested_at"])
    _require(start <= consumed <= tested <= finished and 0 < (finished-start).total_seconds() <= 70,
             "Source timestamps are outside the original single test window")
    for report in (original, events_report):
        runtime = report["evidence_payload"]["runtime_conditions"]
        _require(runtime.get("real_provider") is True and runtime.get("network_profile") == "baseline",
                 "Playback requires an actual Provider baseline observation")
    events = deepcopy(events_report["evidence_payload"]["event_evidence"])
    actions = deepcopy(original["evidence_payload"]["action_evidence"])
    _require(bool(events) and len([e for e in events if e["event_name"] == "SessionStarted"]) == 1,
             "Fresh admin playback requires exactly one Provider session")
    _require(not any(e["parse_error"] or e["event_name"] == "SessionFailed" for e in events),
             "Provider evidence contains an error")
    _require(all(tested.timestamp()*1000 <= e["received_at_ms"] <= finished.timestamp()*1000 for e in events),
             "Provider events fall outside the original run")
    acks = [a for a in actions if a["action"] == "client_sentence_played"]
    _require(len(acks) == 1 and acks[0]["success"] is True
             and tested.timestamp()*1000 <= acks[0]["at_ms"] <= finished.timestamp()*1000,
             "Requires one successful browser ACK inside the original window")
    # Reuse the independent consumer's mapping/audio/boundary/token checks.
    assessment = {**original["evidence_payload"], "event_evidence": events,
                  "schema_version": "phase0-capability-evidence/v4",
                  "reason_code": "client_confirmed_exact_provider_sentence_played"}
    evidence._validate_capability_conclusion(
        capability_key=ACK_KEY, result="passed", payload=assessment, path="admin_playback_review",
    )
    ends = [e for e in events if e["event_name"] == "TTSEnded"]
    boundary = next(e for e in events if e["ordinal"] == acks[0]["sentence_boundary_ordinal"])
    _require(len(ends) == 1 and ends[0]["ordinal"] > boundary["ordinal"]
             and evidence._same_correlation(ends[0], boundary, "frame.session_id", "payload.question_id", "payload.reply_id")
             and acks[0]["provider_ordinal_after_ack"] >= ends[0]["ordinal"]
             and acks[0]["at_ms"] >= ends[0]["received_at_ms"],
             "Playback review requires the same reply's TTS terminal and later browser ACK")

    record = deepcopy(original)
    record["evidence_report_id"] = str(uuid5(NAMESPACE_URL, REVIEW_SCHEMA + ":" + original["evidence_report_id"]))
    record["source_type"] = "admin_capability_test"
    record["evidence_payload"].update(
        reason_code=REVIEW_REASON, event_evidence=events,
        runtime_conditions={"real_provider": True, "network_profile": "admin_test"},
        production_import_ready=False,
    )
    # Preserve error/unverified and null verification/expiry times deliberately.
    record["report_sha256"] = _hash({k: v for k, v in record.items() if k != "report_sha256"})
    record = evidence._validate_evidence_record(
        record, expected_source="admin_capability_test", allow_error=True, path="review_diagnostic",
    )
    summary = {
        "schema_version": REVIEW_SCHEMA, "review_status": "passed", "scope": "admin_playback_only",
        "review_sha256": _hash(dict(sources)),
        "source_hashes": {name: _hash(value) for name, value in sources.items()},
        "source_bundle_sha256": bundle["bundle_sha256"],
        "original_report_id": original["evidence_report_id"],
        "original_report_sha256": original["report_sha256"],
        "original_verification_result": original["verification_result"],
        "original_reason_code": original["evidence_payload"]["reason_code"],
        "events_report_id": events_report["evidence_report_id"],
        "events_report_sha256": events_report["report_sha256"],
        "evidence_run_id": bundle["evidence_run_id"], "session_id": session["session_id"],
        "attempt_id": attempt["attempt_id"], "attempt_ordinal": attempt["attempt_ordinal"],
        "sentence_boundary_ordinal": boundary["ordinal"], "browser_ack": acks[0],
        "human_confirmed_heard": True, "microphone_aec_claimed": False,
        "capability_result": "error", "capability_enabled": False,
        "derived_report_id": record["evidence_report_id"], "derived_report_sha256": record["report_sha256"],
    }
    return {"record": record, "summary": summary}


def _review_audit(operator, summary: dict[str, Any]) -> AdminOperationLog:
    return AdminOperationLog(
        admin_user_id=operator.id, admin_username=operator.username, module="voice_config",
        action="review_playback", target_description="复核既有管理播放；保留原 error，能力仍未验证/关闭",
        after_value=evidence._canonical_json(summary),
    )


async def append_admin_playback_review(
    db: AsyncSession, *, sources: Mapping[str, Any], failure_audit_id: int, operator_id: int,
) -> dict[str, Any]:
    review = validate_admin_playback_review(sources)
    record, summary = review["record"], review["summary"]
    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    async with transaction:
        await evidence._lock_phase0_import_anchor(db)
        operator = await evidence._verified_operator(db, operator_id=operator_id)
        failed_audit = await db.get(AdminOperationLog, failure_audit_id)
        _require(failed_audit is not None and failed_audit.module == "voice_config"
                 and failed_audit.action == "test_capability" and failed_audit.admin_user_id == operator.id
                 and json.loads(failed_audit.after_value) == sources["failed_test"]["data"],
                 "Stored original admin failure audit does not match")
        previous = (await db.execute(select(AdminOperationLog).where(
            AdminOperationLog.module == "voice_config", AdminOperationLog.action == "review_playback",
        ))).scalars().all()
        for log in previous:
            saved = json.loads(log.after_value)
            if saved.get("derived_report_id") != record["evidence_report_id"]:
                continue
            _require(saved.get("review_sha256") == summary["review_sha256"]
                     and saved.get("failure_audit_id") == failure_audit_id,
                     "Conflicting reuse of an existing playback review")
            existing = await evidence._existing_admin_row(db, record)
            _require(len(existing) == 1 and evidence._stored_record_projection(existing[0]) == record,
                     "Stored diagnostic differs from its review")
            return {"review_status": "passed", "idempotent": True,
                    "evidence_report_id": record["evidence_report_id"],
                    "draft_revision": saved["draft_revision"], "review_audit_id": log.id}
        _require(not await evidence._existing_admin_row(db, record),
                 "Existing report/run capability cannot be relabelled as a review")
        draft = (await db.execute(select(AdminConfig).where(
            AdminConfig.config_key == "voice_call_config", AdminConfig.is_draft.is_(True),
        ).with_for_update())).scalars().one()
        _require(draft.draft_revision == sources["failed_test"]["data"]["tested_draft_revision"],
                 "Draft changed since the original admin test")
        # Keep the complete append under this transaction, including the review
        # audit. Reuse the normal evidence writer's projection/audit helpers.
        stored = evidence._new_evidence_row(record, operator_id=operator.id)
        db.add(stored)
        await db.flush()
        await db.refresh(stored)
        _require(evidence._stored_record_projection(stored) == record,
                 "Stored review diagnostic lost original precision")
        draft, config = await evidence._locked_draft_config(db, operator=operator)
        config["capabilities"][ACK_KEY] = evidence._project_record_to_capability(
            config["capabilities"][ACK_KEY], record,
        )
        revision = evidence._advance_draft(draft, config, operator=operator)
        db.add(evidence._evidence_audit(
            operator=operator, action="append_evidence", source_type="admin_capability_test",
            records=[record], draft_revision=revision,
        ))
        summary.update(failure_audit_id=failure_audit_id, draft_revision=revision)
        audit = _review_audit(operator, summary)
        db.add(audit)
        await db.flush()
        return {"review_status": "passed", "idempotent": False,
                "evidence_report_id": record["evidence_report_id"],
                "draft_revision": revision, "review_audit_id": audit.id}
