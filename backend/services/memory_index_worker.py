"""Explicitly started, finite SQL-backed memory index executor.

A lease never permits repeating a dispatch. A prepared intent can be reclaimed
only before its SQL send-permission transition has committed.
"""
import asyncio
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import inspect
import logging
import time
from uuid import uuid4

from sqlalchemy import func, or_, select

from backend.models.memory_control import MemoryIdentity, MemoryIndexTask, MemoryOperation
from backend.services.memory_maintenance_service import record_index_event
from backend.services.memory_mutation_service import _hash, _json, body_hash
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence
from backend.utils.character_knowledge_validate import build_doc_id, parse_doc_id, parse_key_from_content, parse_value_from_content
from backend.utils.memory_vector import normalize_dense, validate_sparse

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexTicket:
    task_id: str
    identity_id: int
    worker_epoch: int
    round_no: int
    round_deadline_at: datetime
    mode: str
    operation_id: str | None = None
    operation_worker_epoch: int | None = None


class MemoryIndexWorker:
    MAX_CONCURRENCY = 4
    MAX_ATTEMPTS = 3
    MAX_PROBES = 24
    LEASE_SECONDS = 15
    RENEW_SECONDS = 5
    SCAN_SECONDS = 5
    WRITE_TIMEOUT = 10
    READ_TIMEOUT = 3

    def __init__(self, session_factory, remote, encoder, environment_id, target_epoch, target_fingerprint,
                 *, clock=None, allow_isolated=False, worker_id=None, event_recorder=None):
        version = getattr(encoder, 'encoder_version', None)
        if not isinstance(version, str) or not version or len(version) > 128:
            raise MemoryControlError(20120, 'encoder_version_invalid')
        if (not isinstance(environment_id, str) or not environment_id or len(environment_id) > 64
                or type(target_epoch) is not int or target_epoch < 1
                or not isinstance(target_fingerprint, bytes) or len(target_fingerprint) != 32):
            raise MemoryControlError(20120, 'runtime_target_invalid')
        self.sessions, self.remote, self.encoder = session_factory, remote, encoder
        self.environment_id, self.target_epoch, self.target_fingerprint = environment_id, target_epoch, target_fingerprint
        self.encoder_version, self.clock = version, clock or datetime.utcnow
        self.allow_isolated, self.worker_id = allow_isolated, worker_id or str(uuid4())
        self._event = event_recorder or record_index_event
        self._loop_task, self._active = None, set()
        self._stopping = False

    def _now(self):
        now = self.clock()
        return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now

    @asynccontextmanager
    async def _session(self):
        async with asyncio.timeout(2):
            async with self.sessions() as db:
                yield db

    async def _fence(self, db):
        return await require_active_fence(db, self.environment_id, self.target_epoch,
                                         self.target_fingerprint, self.allow_isolated)

    async def _locked(self, db, task_id, *, skip_locked=False):
        # Caller always acquires the environment fence first. This lookup does
        # not lock a task: identity precedes task, then operations, everywhere.
        identity_id = await db.scalar(select(MemoryIndexTask.identity_id).where(MemoryIndexTask.task_id == task_id))
        if identity_id is None:
            return None, None
        identity = await db.scalar(select(MemoryIdentity).where(MemoryIdentity.id == identity_id).with_for_update())
        task = await db.scalar(select(MemoryIndexTask).where(MemoryIndexTask.task_id == task_id).with_for_update(skip_locked=skip_locked))
        return identity, task

    def _touch(self, row):
        row.updated_at, row.revision = self._now(), row.revision + 1

    def _valid(self, identity, task):
        return (identity is not None and identity.target_epoch == self.target_epoch
                and identity.target_fingerprint == self.target_fingerprint and identity.source_state == 'live'
                and identity.generation == task.generation and identity.body_hash == task.body_hash
                and identity.encoder_version == task.encoder_version
                and identity.current_operation_id == task.operation_id)

    def _owns(self, task, ticket):
        return (task is not None and task.state == 'running' and task.worker_id == self.worker_id
                and task.worker_epoch == ticket.worker_epoch and task.round_no == ticket.round_no
                and task.round_deadline_at == ticket.round_deadline_at)

    def _owns_active(self, task, ticket):
        return (self._owns(task, ticket) and task.lease_until is not None
                and task.lease_until > self._now() and ticket.round_deadline_at > self._now())

    def _release(self, task):
        task.worker_id, task.lease_until = None, None
        self._touch(task)

    @staticmethod
    def _result(task):
        return {'task_id': task.task_id, 'state': task.state, 'round_no': task.round_no,
                'attempt': task.attempt, 'reason': task.error_code}

    async def _snapshot(self, task_id):
        try:
            async with self._session() as db:
                task = await db.get(MemoryIndexTask, task_id)
                return self._result(task) if task else {'task_id': task_id, 'state': 'unavailable', 'reason': 'task_unavailable'}
        except Exception:
            return {'task_id': task_id, 'state': 'unavailable', 'reason': 'task_state_unreadable'}

    async def _anchor_result(self, db, task, state):
        anchor = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == task.operation_id).with_for_update())
        if anchor and anchor.source_result == 'confirmed' and anchor.index_result != 'ready':
            anchor.index_result = state
            self._touch(anchor)

    async def _manual(self, db, identity, task, op, reason):
        task.state, task.next_attempt_at, task.error_code = 'manual', None, reason
        self._release(task)
        if self._valid(identity, task):
            identity.index_state = 'manual'
            self._touch(identity)
        if op is not None:
            op.index_result = 'manual'
            op.lease_until, op.worker_id = None, None
            op.receipt_summary = {**(op.receipt_summary or {}), 'reason': reason}
            self._touch(op)
            if op.dispatch_state == 'prepared':
                # The SQL send-permission transition never committed. Holding
                # all three locks and ending the task fences its old owner.
                op.dispatch_state, op.index_result = 'not_sent', 'failed'
                if identity.inflight_operation_id == op.operation_id:
                    identity.inflight_operation_id = None
                    self._touch(identity)
                self._terminal(op)
        await self._anchor_result(db, task, 'manual')
        await self._event(db, task, op, 'manual_required', reason, self._now())

    async def _supersede(self, db, identity, task):
        task.state, task.next_attempt_at, task.error_code = 'superseded', None, 'task_generation_superseded'
        self._release(task)
        # No remote operation can be discarded here. An inflight operation
        # retains its identity fence even if later metadata is inconsistent.
        await self._anchor_result(db, task, 'superseded')
        await self._event(db, task, None, 'superseded', task.error_code, self._now())

    async def claim(self, task_id):
        now = self._now()
        async with self._session() as db:
            await self._fence(db)
            # The fence serializes capacity decisions. This is a fresh first
            # consistent read under MySQL RR, without locking tasks out of order.
            count = await db.scalar(select(func.count()).select_from(MemoryIndexTask).join(
                MemoryIdentity, MemoryIdentity.id == MemoryIndexTask.identity_id).where(
                MemoryIdentity.target_fingerprint == self.target_fingerprint,
                MemoryIdentity.target_epoch == self.target_epoch,
                MemoryIndexTask.state == 'running', MemoryIndexTask.lease_until > now))
            identity, task = await self._locked(db, task_id, skip_locked=True)
            if task is None or task.state in {'completed', 'superseded', 'manual'}:
                return None
            if not self._valid(identity, task):
                await self._supersede(db, identity, task)
                await db.commit()
                return None
            op = None
            if identity.inflight_operation_id:
                op = await db.scalar(select(MemoryOperation).where(
                    MemoryOperation.operation_id == identity.inflight_operation_id).with_for_update())
                if (op is None or op.operation_kind != 'index' or op.task_id != task.task_id
                        or op.generation != task.generation or op.target_epoch != self.target_epoch
                        or op.dispatch_state not in {'prepared', 'claimed', 'dispatching', 'unknown'}):
                    # Move a blocked candidate's due time forward so a bounded
                    # scan can reach other identities. Never touch the foreign
                    # (often source-write) operation or its identity fence.
                    if now >= task.round_deadline_at:
                        await self._manual(db, identity, task, None, 'index_round_expired')
                    else:
                        task.state, task.error_code = 'retry_wait', 'identity_busy'
                        task.next_attempt_at = now + timedelta(seconds=5)
                        self._release(task)
                    await db.commit()
                    return None
            if now >= task.round_deadline_at:
                await self._manual(db, identity, task, op, 'index_round_expired')
                await db.commit()
                return None
            # An existing ambiguous write can be verified from its immutable
            # payload even if this process no longer has the original encoder.
            if op is None and task.encoder_version != self.encoder_version:
                await self._manual(db, identity, task, None, 'index_profile_unavailable')
                await db.commit()
                return None
            if task.next_attempt_at and now < task.next_attempt_at:
                return None
            if task.state == 'running' and task.lease_until and task.lease_until > now:
                return None
            if count >= self.MAX_CONCURRENCY:
                return None
            if (task.round_deadline_at - now).total_seconds() < self.READ_TIMEOUT:
                await self._manual(db, identity, task, op, 'index_round_expired')
                await db.commit()
                return None
            if op is None and task.attempt >= self.MAX_ATTEMPTS:
                await self._manual(db, identity, task, None, 'index_attempts_exhausted')
                await db.commit()
                return None
            if op:
                summary = dict(op.receipt_summary or {})
                if summary.get('probe_round') != task.round_no:
                    summary.update(probe_round=task.round_no, probe_count=0)
                if summary.get('probe_count', 0) >= self.MAX_PROBES:
                    await self._manual(db, identity, task, op, 'index_probe_budget_exhausted')
                    await db.commit()
                    return None
                op.receipt_summary = summary
                op.worker_id, op.worker_epoch = self.worker_id, op.worker_epoch + 1
                op.lease_until = min(now + timedelta(seconds=self.LEASE_SECONDS), task.round_deadline_at)
                self._touch(op)
            task.state, task.worker_id = 'running', self.worker_id
            task.worker_epoch += 1
            task.lease_until = min(now + timedelta(seconds=self.LEASE_SECONDS), task.round_deadline_at)
            self._touch(task)
            mode = ('prepared' if op.dispatch_state == 'prepared' else 'reconcile') if op else 'write'
            ticket = IndexTicket(task.task_id, identity.id, task.worker_epoch, task.round_no, task.round_deadline_at,
                                 mode, op.operation_id if op else None,
                                 op.worker_epoch if op else None)
            await db.commit()
            return ticket

    async def renew(self, ticket):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            if not self._owns_active(task, ticket) or not self._valid(identity, task):
                return False
            task.lease_until = min(self._now() + timedelta(seconds=self.LEASE_SECONDS), task.round_deadline_at)
            self._touch(task)
            if ticket.operation_id:
                op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
                if (identity.inflight_operation_id != ticket.operation_id or op is None
                        or op.worker_id != self.worker_id or op.worker_epoch != ticket.operation_worker_epoch):
                    return False
                op.lease_until = task.lease_until
                self._touch(op)
            await db.commit()
            return True

    async def _heartbeat(self, ticket):
        while True:
            await asyncio.sleep(self.RENEW_SECONDS)
            try:
                if not await self.renew(ticket):
                    return
            except Exception:
                return

    async def _source_context(self, ticket):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            if not self._owns_active(task, ticket) or not self._valid(identity, task):
                return None
            prepared = None
            if identity.inflight_operation_id:
                if ticket.mode != 'prepared' or identity.inflight_operation_id != ticket.operation_id:
                    return None
                op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
                if (op is None or op.dispatch_state != 'prepared' or op.worker_id != self.worker_id
                        or op.worker_epoch != ticket.operation_worker_epoch or not op.pending_payload
                        or _hash(op.pending_payload) != op.payload_hash):
                    return None
                prepared = deepcopy(op.pending_payload)
            # Only committed tags for this exact generation are source evidence.
            tags = set((await db.scalars(select(MemoryOperation.remote_tag).where(
                MemoryOperation.identity_id == identity.id, MemoryOperation.generation == task.generation,
                MemoryOperation.target_epoch == self.target_epoch, MemoryOperation.dispatch_state == 'confirmed',
                MemoryOperation.source_result == 'confirmed',
                MemoryOperation.operation_kind.in_({'create', 'update', 'index', 'baseline'})))).all())
            return identity, task, tags, prepared

    @staticmethod
    def _prepared_source_matches(prepared, document):
        """Reclaim only an unsent intent whose complete source is still current."""
        try:
            before, current = dict(prepared['fields']), dict(document['fields'])
            for key in ('mr_operation_id', 'mr_encoder_version'):
                before.pop(key, None)
                current.pop(key, None)
            return (prepared['id'] == document['id'] and before == current
                    and all(abs(a-b) <= 1e-6 for a, b in zip(prepared['vector'], document['vector'])))
        except Exception:
            return False

    def _source_valid(self, identity, task, tags, fetched):
        try:
            if getattr(fetched, 'status', None) != 'found':
                return False
            doc, fields = fetched.document, fetched.document['fields']
            if (doc['id'] != identity.doc_id or fields.get('type') != identity.memory_type
                    or type(fields.get('user_id')) is not int or fields['user_id'] != identity.owner_user_id
                    or fields.get('mr_deleted') is not False or type(fields.get('mr_epoch')) is not int
                    or fields['mr_epoch'] != self.target_epoch or type(fields.get('mr_generation')) is not int
                    or fields['mr_generation'] != task.generation or fields.get('mr_body_sha256') != task.body_hash.hex()
                    or fields.get('mr_operation_id') not in tags or body_hash(doc) != task.body_hash):
                return False
            if parse_doc_id(doc['id']) and (fields.get('key') != parse_key_from_content(fields['content'])
                    or doc['id'] != build_doc_id(identity.memory_type, fields.get('key'), identity.owner_user_id)):
                return False
            unit = normalize_dense(doc['vector'])
            return all(abs(a-b) <= 1e-6 for a, b in zip(unit, doc['vector']))
        except Exception:
            return False

    async def _defer_read(self, ticket, reason):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            if not self._owns(task, ticket):
                return
            op = None
            if ticket.operation_id:
                op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
            if not self._valid(identity, task):
                await self._supersede(db, identity, task)
            elif self._now() + timedelta(seconds=5) >= task.round_deadline_at:
                await self._manual(db, identity, task, op, reason)
            else:
                task.state, task.error_code = 'retry_wait', reason
                task.next_attempt_at = self._now() + timedelta(seconds=5)
                self._release(task)
                await self._event(db, task, None, 'source_read_deferred', reason, self._now())
            await db.commit()

    async def _prepare(self, ticket, document):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            if not self._owns_active(task, ticket):
                return None
            if not self._valid(identity, task):
                await self._supersede(db, identity, task)
                await db.commit()
                return None
            if identity.inflight_operation_id or self._now() >= task.round_deadline_at:
                await self._defer_inside(db, identity, task)
                await db.commit()
                return None
            operation_id, tag, now = str(uuid4()), str(uuid4()), self._now()
            # Fetch may include read-only metadata such as score. Persist only
            # write-protocol properties, retaining the entire business fields.
            payload = {key: deepcopy(document[key]) for key in ('id', 'vector', 'fields', 'sparse_vector') if key in document}
            payload['fields'].update(mr_epoch=self.target_epoch, mr_generation=task.generation,
                mr_body_sha256=task.body_hash.hex(), mr_deleted=False,
                mr_encoder_version=task.encoder_version, mr_operation_id=tag)
            if len(_json(payload).encode()) > 1024 * 1024:
                raise MemoryControlError(20120, 'index_payload_too_large')
            digest = _hash(payload)
            task.attempt += 1
            op = MemoryOperation(operation_id=operation_id, identity_id=identity.id, generation=task.generation,
                parent_operation_id=None, task_id=task.task_id, round_no=task.round_no, attempt=task.attempt,
                source_generation_key=None, operation_kind='index', owner_actor_type='system', owner_actor_id=1,
                request_hash=digest, target_epoch=self.target_epoch, source_result='confirmed', index_result='pending',
                dispatch_state='prepared', pending_payload=payload, payload_hash=digest, remote_tag=tag,
                worker_id=self.worker_id, worker_epoch=1, lease_until=task.lease_until,
                reconcile_until=task.round_deadline_at, receipt_summary={'encoder_version': task.encoder_version,
                    'probe_round': task.round_no, 'probe_count': 0}, created_at=now, updated_at=now, revision=1)
            db.add(op)
            identity.inflight_operation_id, identity.index_state = operation_id, 'repairing'
            self._touch(identity)
            self._touch(task)
            await db.flush()
            await self._event(db, task, op, 'attempt_started', None, now)
            await db.commit()
            return replace(ticket, operation_id=operation_id, operation_worker_epoch=1)

    async def _defer_inside(self, db, identity, task):
        if self._now() >= task.round_deadline_at:
            await self._manual(db, identity, task, None, 'index_round_expired')
        else:
            task.state, task.next_attempt_at, task.error_code = 'retry_wait', self._now() + timedelta(seconds=5), 'identity_busy'
            self._release(task)

    async def _dispatch_intent(self, ticket):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
            if (not self._owns_active(task, ticket) or not self._valid(identity, task)
                    or identity.inflight_operation_id != ticket.operation_id or op is None
                    or op.worker_epoch != ticket.operation_worker_epoch or op.worker_id != self.worker_id
                    or op.dispatch_state != 'prepared' or self._now() >= task.round_deadline_at
                    or not op.pending_payload or _hash(op.pending_payload) != op.payload_hash):
                return None
            op.dispatch_state, op.dispatched_at = 'dispatching', self._now()
            task.lease_until = min(self._now() + timedelta(seconds=self.LEASE_SECONDS), ticket.round_deadline_at)
            op.lease_until = task.lease_until
            self._touch(task)
            self._touch(op)
            await db.commit()
        # Commit acknowledgement alone does not grant the sender permission.
        async with self._session() as db:
            op = await db.get(MemoryOperation, ticket.operation_id)
            task = await db.get(MemoryIndexTask, ticket.task_id)
            identity = await db.get(MemoryIdentity, ticket.identity_id)
            if (not self._owns_active(task, ticket) or not self._valid(identity, task)
                    or identity.inflight_operation_id != ticket.operation_id or op is None
                    or op.dispatch_state != 'dispatching' or op.worker_id != self.worker_id
                    or op.worker_epoch != ticket.operation_worker_epoch or not op.pending_payload
                    or _hash(op.pending_payload) != op.payload_hash or self._now() >= task.round_deadline_at):
                return None
            return identity.partition_name, deepcopy(op.pending_payload), task.round_deadline_at

    def _terminal(self, op):
        now = self._now()
        op.pending_payload, op.worker_id, op.lease_until = None, None, None
        op.terminal_at, op.receipt_until, op.tombstone_until = now, now + timedelta(days=7), now + timedelta(days=30)
        self._touch(op)

    async def _finish(self, ticket, status, reason):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
            if (not self._owns(task, ticket) or op is None or identity.inflight_operation_id != op.operation_id
                    or op.worker_epoch != ticket.operation_worker_epoch or op.worker_id != self.worker_id):
                return
            if not self._valid(identity, task) or not op.pending_payload or _hash(op.pending_payload) != op.payload_hash:
                await self._manual(db, identity, task, op, 'index_confirmation_unverified')
            elif status == 'confirmed':
                task.state, task.error_code, task.next_attempt_at = 'completed', None, None
                self._release(task)
                identity.inflight_operation_id, identity.index_state = None, 'ready'
                self._touch(identity)
                op.dispatch_state, op.index_result = 'confirmed', 'ready'
                op.receipt_summary = {**(op.receipt_summary or {}), 'reason': None}
                self._terminal(op)
                await self._anchor_result(db, task, 'ready')
                await self._event(db, task, op, 'completed', None, self._now())
            elif status == 'rejected':
                identity.inflight_operation_id = None
                self._touch(identity)
                op.dispatch_state, op.index_result = 'not_sent', 'failed'
                op.receipt_summary = {**(op.receipt_summary or {}), 'reason': reason}
                self._terminal(op)
                delay = 5 if task.attempt == 1 else 30
                if task.attempt >= self.MAX_ATTEMPTS or self._now() + timedelta(seconds=delay) >= task.round_deadline_at:
                    await self._manual(db, identity, task, None, 'index_attempts_exhausted')
                else:
                    task.state, task.error_code = 'retry_wait', reason
                    task.next_attempt_at = self._now() + timedelta(seconds=delay)
                    self._release(task)
                    await self._event(db, task, op, 'retry_scheduled', reason, self._now())
            else:
                op.dispatch_state, op.index_result = 'unknown', 'unknown'
                op.receipt_summary = {**(op.receipt_summary or {}), 'reason': reason}
                op.worker_id, op.lease_until = None, None
                self._touch(op)
                if self._now() >= task.round_deadline_at or (op.receipt_summary or {}).get('probe_count', 0) >= self.MAX_PROBES:
                    await self._manual(db, identity, task, op, 'index_evidence_unverified')
                else:
                    task.state, task.error_code = 'retry_wait', reason
                    task.next_attempt_at = self._now() + timedelta(seconds=5)
                    self._release(task)
                    await self._event(db, task, op, 'readback_pending', reason, self._now())
            await db.commit()

    def _matches(self, op, identity, fetched):
        try:
            if getattr(fetched, 'status', None) != 'found' or not op.pending_payload:
                return False
            expected, actual = op.pending_payload, fetched.document
            if (_hash(expected) != op.payload_hash or actual['id'] != identity.doc_id
                    or actual['fields'] != expected['fields'] or actual['fields']['mr_operation_id'] != op.remote_tag
                    or type(actual['fields'].get('mr_epoch')) is not int
                    or actual['fields']['mr_epoch'] != op.target_epoch
                    or type(actual['fields'].get('mr_generation')) is not int
                    or actual['fields']['mr_generation'] != op.generation
                    or type(actual['fields'].get('user_id')) is not int
                    or actual['fields']['user_id'] != identity.owner_user_id
                    or actual['fields'].get('type') != identity.memory_type
                    or actual['fields'].get('mr_deleted') is not False
                    or actual['fields'].get('mr_body_sha256') != body_hash(expected).hex()
                    or body_hash(actual) != body_hash(expected)):
                return False
            normalize_dense(actual['vector'])  # Validation only; preserve raw readback as evidence.
            if not all(abs(a-b) <= 1e-6 for a, b in zip(actual['vector'], expected['vector'])):
                return False
            sparse, wanted = validate_sparse(actual.get('sparse_vector') or {}), validate_sparse(expected.get('sparse_vector') or {})
            return sparse.keys() == wanted.keys() and all(abs(sparse[k]-wanted[k]) <= 1e-6 for k in wanted)
        except Exception:
            return False

    async def _probe(self, ticket):
        async with self._session() as db:
            await self._fence(db)
            identity, task = await self._locked(db, ticket.task_id)
            op = await db.scalar(select(MemoryOperation).where(MemoryOperation.operation_id == ticket.operation_id).with_for_update())
            if (not self._owns_active(task, ticket) or op is None or identity.inflight_operation_id != op.operation_id
                    or op.worker_epoch != ticket.operation_worker_epoch or not self._valid(identity, task)):
                return
            summary = dict(op.receipt_summary or {})
            if summary.get('probe_round') != task.round_no:
                summary.update(probe_round=task.round_no, probe_count=0)
            if ((task.round_deadline_at - self._now()).total_seconds() < self.READ_TIMEOUT
                    or summary.get('probe_count', 0) >= self.MAX_PROBES):
                await self._manual(db, identity, task, op, 'index_probe_budget_exhausted')
                await db.commit()
                return
            summary['probe_count'] = summary.get('probe_count', 0) + 1
            op.receipt_summary = summary
            self._touch(op)
            partition, doc_id = identity.partition_name, identity.doc_id
            await db.commit()
        try:
            if (ticket.round_deadline_at - self._now()).total_seconds() < self.READ_TIMEOUT:
                await self._finish(ticket, 'unknown', 'index_round_expired')
                return
            fetched = await asyncio.wait_for(self.remote.fetch(partition, doc_id), timeout=self.READ_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            fetched = None
        matched = self._matches(op, identity, fetched)
        await self._finish(ticket, 'confirmed' if matched else 'unknown', 'index_evidence_unverified')

    async def _document_vector(self, document, value):
        """Ordinary repair retains validated dense; backfill freezes its document provider."""
        return document["vector"]

    async def process(self, task_id):
        ticket, heartbeat, sent = None, None, False
        current = asyncio.current_task()
        self._active.add(current)
        try:
            if self._stopping:
                return await self._snapshot(task_id)
            ticket = await self.claim(task_id)
            if ticket is None:
                return await self._snapshot(task_id)
            heartbeat = asyncio.create_task(self._heartbeat(ticket))
            if ticket.mode == 'reconcile':
                await self._probe(ticket)
            else:
                context = await self._source_context(ticket)
                if context is None:
                    return await self._snapshot(task_id)
                identity, task, tags, prepared_payload = context
                if (task.round_deadline_at - self._now()).total_seconds() < self.READ_TIMEOUT:
                    await self._defer_read(ticket, 'index_round_expired')
                    return await self._snapshot(task_id)
                try:
                    fetched = await asyncio.wait_for(self.remote.fetch(identity.partition_name, identity.doc_id), timeout=self.READ_TIMEOUT)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    fetched = None
                if not self._source_valid(identity, task, tags, fetched):
                    await self._defer_read(ticket, 'source_read_unverified')
                    return await self._snapshot(task_id)
                document = deepcopy(fetched.document)
                if ticket.mode == 'prepared':
                    if not self._prepared_source_matches(prepared_payload, document):
                        await self._defer_read(ticket, 'source_read_unverified')
                        return await self._snapshot(task_id)
                else:
                    value = document['fields']['content'] if document['id'].startswith('mem_') else parse_value_from_content(document['fields']['content'])
                    try:
                        document["vector"] = await self._document_vector(document, value)
                        sparse = self.encoder.encode_document(value)
                        if inspect.isawaitable(sparse):
                            sparse = await asyncio.wait_for(sparse, timeout=max(0, (ticket.round_deadline_at - self._now()).total_seconds()))
                        document['sparse_vector'] = validate_sparse(sparse)
                    except Exception:
                        await self._defer_read(ticket, 'index_encode_failed')
                        return await self._snapshot(task_id)
                    prepared = await self._prepare(ticket, document)
                    if prepared is None:
                        return await self._snapshot(task_id)
                    ticket = prepared
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat
                heartbeat = asyncio.create_task(self._heartbeat(ticket))
                dispatch = await self._dispatch_intent(ticket)
                if dispatch is None:
                    # This invocation has not called the adapter. CAS in finish
                    # prevents a stale owner from retiring another owner's work.
                    await self._finish(ticket, 'rejected', 'index_dispatch_not_sent')
                    return await self._snapshot(task_id)
                partition, payload, deadline = dispatch
                remaining = (deadline - self._now()).total_seconds()
                if remaining <= 0:
                    await self._finish(ticket, 'rejected', 'index_round_expired')
                    return await self._snapshot(task_id)
                try:
                    sent = True
                    result = await asyncio.wait_for(self.remote.full_upsert(partition, payload), timeout=min(self.WRITE_TIMEOUT, remaining))
                    status = getattr(result, 'status', 'unknown')
                except asyncio.CancelledError:
                    raise
                except Exception:
                    status = 'unknown'
                await self._finish(ticket, status, 'remote_rejected' if status == 'rejected' else 'remote_outcome_unknown')
        except asyncio.CancelledError:
            # The caller is awaited by stop(); cancellation never detaches a send.
            with suppress(Exception):
                if ticket and ticket.operation_id:
                    await self._finish(ticket, 'unknown' if sent or ticket.mode == 'reconcile' else 'rejected', 'worker_stopped')
                elif ticket:
                    await self._defer_read(ticket, 'worker_stopped')
            raise
        except Exception:
            # One failed task cannot stop the scan. A durable intent not locally
            # acknowledged is left fenced for recovery, never guessed not-sent.
            with suppress(Exception):
                if ticket and ticket.operation_id:
                    await self._finish(ticket, 'unknown', 'task_execution_unverified')
                elif ticket:
                    await self._defer_read(ticket, 'task_execution_unverified')
        finally:
            if heartbeat:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat
            self._active.discard(current)
        return await self._snapshot(task_id)

    async def run_once(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MemoryControlError(20120, 'scan_limit_invalid')
        async with self._session() as db:
            now = self._now()
            ids = list((await db.scalars(select(MemoryIndexTask.task_id).join(
                MemoryIdentity, MemoryIdentity.id == MemoryIndexTask.identity_id).where(
                MemoryIdentity.target_fingerprint == self.target_fingerprint,
                MemoryIdentity.target_epoch == self.target_epoch,
                MemoryIndexTask.state.in_({'pending', 'retry_wait', 'running'}),
                or_(MemoryIndexTask.next_attempt_at.is_(None), MemoryIndexTask.next_attempt_at <= now),
                or_(MemoryIndexTask.state != 'running', MemoryIndexTask.lease_until.is_(None), MemoryIndexTask.lease_until <= now),
            ).order_by(MemoryIndexTask.next_attempt_at, MemoryIndexTask.task_id).limit(limit))).all())
        results = []
        # Bound local fanout too; SQL remains the authority across all processes.
        for offset in range(0, len(ids), self.MAX_CONCURRENCY):
            results.extend(await asyncio.gather(*(self.process(value) for value in ids[offset:offset+self.MAX_CONCURRENCY])))
        return results

    async def _run(self):
        problem, reported_at = None, 0.0
        while not self._stopping:
            try:
                await self.run_once()
                if problem is not None:
                    log.info('memory_index_scan_recovered')
                    problem = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reason, now = type(exc).__name__, time.monotonic()
                if problem != reason or now - reported_at >= 60:
                    log.warning('memory_index_scan_failed reason=%s', reason)
                    problem, reported_at = reason, now
            await asyncio.sleep(self.SCAN_SECONDS)

    def start(self):
        if self._loop_task is None or self._loop_task.done():
            self._stopping = False
            self._loop_task = asyncio.create_task(self._run())
        return self._loop_task

    async def stop(self):
        self._stopping = True
        tasks = set(self._active)
        if self._loop_task:
            tasks.add(self._loop_task)
        tasks.discard(asyncio.current_task())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._loop_task = None
