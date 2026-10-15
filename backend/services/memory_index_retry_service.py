"""SQL-only manual maintenance retry admission; STEP017 owns API/role wiring.

The receipt and round advancement share a transaction. Existing request IDs
always replay their original outcome, including no-ops and definite rejections.
A manual round never releases a remote fence or creates a remote write intent.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.models.memory_control import MemoryIdentity, MemoryIndexTask, MemoryOperation
from backend.services.memory_maintenance_service import record_index_event
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence

ROUND_SECONDS = 120
MANUAL_ROUNDS_PER_DAY = 3
SUMMARY_FIELDS = frozenset({"code", "task_id", "task_revision", "round_no", "accepted_new_round",
    "read_only_reconciliation", "maintenance_state", "reason", "latest_task_id", "latest_task_revision",
    "retry_after", "observed_at"})


def _utc(now):
    if not isinstance(now, datetime):
        raise ValueError("clock_invalid")
    return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now


def _time(now):
    return now.isoformat(timespec="microseconds") + "Z"


def _failure(code, reason, now, **values):
    return dict(values, code=code, reason=reason, server_time=_time(now))


def _uuid(value, version):
    parsed = UUID(value)
    if type(value) is not str or str(parsed) != value or parsed.version != version:
        raise ValueError("identity_invalid")
    return parsed


def _request_hash(environment, task_id, revision, actor_type, actor_id):
    body = {"operation": "retry", "environment_id": environment, "task_id": task_id,
            "expected_revision": revision, "actor_type": actor_type, "actor_id": actor_id}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).digest()


async def _find_receipt(db, actor_type, actor_id, client_request_id, *, lock=False):
    query = select(MemoryOperation).where(
        MemoryOperation.owner_actor_type == actor_type, MemoryOperation.owner_actor_id == actor_id,
        MemoryOperation.idempotency_hash == hashlib.sha256(client_request_id.encode()).digest(),
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query.execution_options(populate_existing=True))


async def _current_operation(db, operation_id):
    return await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == operation_id)
                           .with_for_update().execution_options(populate_existing=True))


def _receipt(op, client_request_id, request_hash, now):
    if (op.client_request_id != client_request_id or op.operation_kind != "retry"
            or not hmac.compare_digest(op.request_hash, request_hash)):
        return _failure(20121, "retry_identity_conflict", now, operation_id=client_request_id)
    identity = {"operation_id": client_request_id, "internal_operation_id": op.operation_id}
    if op.receipt_until is not None and now >= op.receipt_until:
        return _failure(20123, "retry_receipt_expired", now, **identity,
                        receipt_state="expired" if op.receipt_summary else "tombstone")
    if not isinstance(op.receipt_summary, dict):
        return _failure(20129, "retry_receipt_unavailable", now, **identity, receipt_state="unavailable")
    return dict({key: value for key, value in op.receipt_summary.items() if key in SUMMARY_FIELDS},
                **identity, receipt_state="full", server_time=_time(now))


async def _latest_task(db, identity):
    return await db.scalar(select(MemoryIndexTask).where(
        MemoryIndexTask.identity_id == identity.id, MemoryIndexTask.generation == identity.generation,
        MemoryIndexTask.encoder_version == identity.encoder_version, MemoryIndexTask.body_hash == identity.body_hash,
        MemoryIndexTask.state != "superseded",
    ).order_by(MemoryIndexTask.created_at.desc(), MemoryIndexTask.task_id).limit(1).with_for_update())


async def _decide(db, identity, task, fence_error, expected_revision, now, *, dry_run=False):
    result = {"code": 0, "task_id": task.task_id, "task_revision": task.revision, "round_no": task.round_no,
        "accepted_new_round": False, "read_only_reconciliation": False,
        "maintenance_state": "manual_required" if task.state == "manual" else task.state,
        "reason": "task_already_active", "observed_at": _time(now)}
    if fence_error:
        result.update(code=fence_error.code, reason=fence_error.reason)
        return result
    if (task.state == "superseded" or task.generation != identity.generation
            or task.body_hash != identity.body_hash or task.encoder_version != identity.encoder_version):
        latest = await _latest_task(db, identity)
        result.update(code=20127, reason="task_superseded", maintenance_state="superseded",
                      latest_task_id=latest.task_id if latest else None,
                      latest_task_revision=latest.revision if latest else None)
        return result
    if identity.source_state != "live":
        result.update(code=20128 if identity.source_state == "unknown" else 20126,
                      reason="memory_source_unverified" if identity.source_state == "unknown" else "source_deleted",
                      maintenance_state="source_unverified" if identity.source_state == "unknown" else result["maintenance_state"])
        return result
    source = await _current_operation(db, task.operation_id)
    if (source is None or source.source_result != "confirmed" or source.identity_id != identity.id
            or source.generation != identity.generation or source.target_epoch != identity.target_epoch
            or identity.current_operation_id != source.operation_id):
        result.update(code=20128, reason="memory_source_unverified", maintenance_state="source_unverified")
        return result
    inflight = None
    if identity.inflight_operation_id:
        inflight = await _current_operation(db, identity.inflight_operation_id)
        if (inflight is None or inflight.operation_kind != "index" or inflight.task_id != task.task_id
                or inflight.identity_id != identity.id or inflight.generation != task.generation
                or inflight.target_epoch != identity.target_epoch or inflight.source_result != "confirmed"):
            result.update(code=20128, reason="memory_source_unverified", maintenance_state="source_unverified")
            return result
    if task.state in {"pending", "running", "retry_wait", "completed"}:
        if task.state == "completed":
            result["reason"] = "task_already_completed"
        return result
    if task.state != "manual":
        result.update(code=20126, reason="task_not_retryable")
        return result
    if expected_revision != task.revision:
        result.update(code=20127, reason="task_revision_conflict",
                      latest_task_id=task.task_id, latest_task_revision=task.revision)
        return result
    if inflight is not None:
        if inflight.dispatch_state not in {"dispatching", "unknown"}:
            result.update(code=20128, reason="memory_source_unverified", maintenance_state="source_unverified")
            return result
        result["read_only_reconciliation"] = True
    rounds = (await db.scalars(select(MemoryOperation.created_at).where(
        MemoryOperation.identity_id == identity.id, MemoryOperation.operation_kind == "retry",
        MemoryOperation.attempt == 0, MemoryOperation.created_at > now - timedelta(days=1),
    ).order_by(MemoryOperation.created_at).with_for_update())).all()
    if len(rounds) >= MANUAL_ROUNDS_PER_DAY:
        result.update(code=20126, reason="manual_round_limit", retry_after=_time(rounds[0] + timedelta(days=1)))
        return result
    if dry_run:
        result.update(accepted_new_round=True, reason="retry_eligible")
        return result
    task.round_no += 1
    task.attempt, task.state = 0, "pending"
    task.round_started_at, task.round_deadline_at = now, now + timedelta(seconds=ROUND_SECONDS)
    task.next_attempt_at, task.error_code = now, None
    task.worker_id, task.lease_until = None, None
    task.worker_epoch += 1
    task.revision, task.updated_at = task.revision + 1, now
    identity.index_state = "repairing"
    identity.revision, identity.updated_at = identity.revision + 1, now
    result.update(accepted_new_round=True, task_revision=task.revision, round_no=task.round_no,
                  maintenance_state="pending", reason="reconciliation_queued" if result["read_only_reconciliation"] else "retry_queued")
    return result


async def retry_task(session_factory, environment_id, task_id, *, actor_type, actor_id,
                     client_request_id, task_revision, allow_isolated=False, clock=None):
    """Trusted admin actor only; this component performs no network/model calls.

    017 must supply its authenticated actor after role checks. Results are safe
    internal DTOs; revision and U64 rendering for external JSON belongs there.
    """
    try:
        now = _utc((clock or datetime.utcnow)())
    except Exception:
        return _failure(20120, "clock_invalid", datetime.utcnow())
    try:
        parsed_request = _uuid(client_request_id, 7)
        _uuid(task_id, 4)
        if (actor_type != "admin" or type(actor_id) is not int or not 0 < actor_id < 2**63
                or type(task_revision) is not int or not 0 < task_revision < 2**64
                or not isinstance(environment_id, str) or not 1 <= len(environment_id) <= 64):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        return _failure(20120, "retry_request_invalid", now)
    digest = _request_hash(environment_id, task_id, task_revision, actor_type, actor_id)
    commit_started = False
    try:
        async with asyncio.timeout(2):
            async with session_factory() as db:
                prior = await _find_receipt(db, actor_type, actor_id, client_request_id)
                if prior:
                    return _receipt(prior, client_request_id, digest, now)
                age = int(now.replace(tzinfo=timezone.utc).timestamp() * 1000) - (parsed_request.int >> 80)
                if age > 120000 or age < -30000:
                    return _failure(20123, "retry_id_outside_window", now, operation_id=client_request_id)
                # Locate only. All mutation decisions reread under fence→identity→task.
                task = await db.get(MemoryIndexTask, task_id)
                if task is None:
                    return _failure(20125, "task_unavailable", now, operation_id=client_request_id)
                identity = await db.get(MemoryIdentity, task.identity_id)
                if identity is None:
                    return _failure(20129, "memory_identity_unavailable", now)
                identity_id, fence_error = identity.id, None
                try:
                    fence = await require_active_fence(db, environment_id, identity.target_epoch,
                                                       identity.target_fingerprint, allow_isolated)
                except MemoryControlError as error:
                    if error.code == 20129:
                        raise
                    fence_error = error
                identity = await db.scalar(select(MemoryIdentity).where(MemoryIdentity.id == identity_id)
                    .with_for_update().execution_options(populate_existing=True))
                task = await db.scalar(select(MemoryIndexTask).where(MemoryIndexTask.task_id == task_id)
                    .with_for_update().execution_options(populate_existing=True))
                prior = await _find_receipt(db, actor_type, actor_id, client_request_id, lock=True)
                if prior:
                    return _receipt(prior, client_request_id, digest, now)
                if identity is None or task is None or task.identity_id != identity_id:
                    return _failure(20129, "memory_identity_unavailable", now)
                # Compare with the already locked, current fence, never an old
                # REPEATABLE READ snapshot opened by the first receipt lookup.
                if fence_error is None and (identity.target_epoch != fence.target_epoch
                                            or identity.target_fingerprint != fence.target_fingerprint):
                    fence_error = MemoryControlError(20127, "runtime_target_changed")
                result = await _decide(db, identity, task, fence_error, task_revision, now)
                accepted = result["accepted_new_round"]
                op = MemoryOperation(operation_id=str(uuid4()), identity_id=identity.id, generation=task.generation,
                    operation_kind="retry", task_id=task_id, round_no=task.round_no, attempt=0 if accepted else None,
                    source_generation_key=None, parent_operation_id=None, owner_actor_type=actor_type, owner_actor_id=actor_id,
                    client_request_id=client_request_id, idempotency_hash=hashlib.sha256(client_request_id.encode()).digest(),
                    request_hash=digest, target_epoch=identity.target_epoch,
                    source_result="confirmed" if identity.source_state == "live" else "unknown",
                    index_result="pending" if accepted else "not_required", dispatch_state="confirmed",
                    pending_payload=None, payload_hash=None, remote_tag=str(uuid4()),
                    reconcile_until=now, terminal_at=now, receipt_summary=result,
                    receipt_until=now + timedelta(days=7), tombstone_until=now + timedelta(days=30),
                    created_at=now, updated_at=now, revision=1, worker_epoch=0)
                db.add(op)
                await db.flush()
                await record_index_event(db, task, op, "manual_retry" if accepted else "retry_noop" if result["code"] == 0 else "retry_rejected", result["reason"], now)
                commit_started = True
                await db.commit()
        # An ORM object after commit is not proof of durable acknowledgement.
        async with asyncio.timeout(2):
            async with session_factory() as verify:
                saved = await _find_receipt(verify, actor_type, actor_id, client_request_id)
                if saved:
                    return _receipt(saved, client_request_id, digest, now)
    except Exception:
        # Never stringify SQL/driver exceptions. A lost commit only reads back.
        try:
            async with asyncio.timeout(2):
                async with session_factory() as verify:
                    saved = await _find_receipt(verify, actor_type, actor_id, client_request_id)
                    if saved:
                        return _receipt(saved, client_request_id, digest, now)
        except Exception:
            pass
    return _failure(20122 if commit_started else 20129,
                    "retry_commit_unconfirmed" if commit_started else "retry_persistence_unavailable", now,
                    operation_id=client_request_id, task_id=task_id, receipt_state="unavailable")
