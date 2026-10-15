"""Source mutation intents and exact readback; no scheduler or business routes.

An unconfirmed dispatch permanently retains its identity slot until matching
evidence is observed. Neither a lease nor an absent/stale fetch authorizes a
second write. The only payload is the bounded, temporary pending operation.
"""
import asyncio
from copy import deepcopy
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.models.memory_control import MemoryIdentity, MemoryOperation, MemoryIndexTask, MemoryUseClaim, MemoryUseItem
from backend.services.memory_config_publication import get_or_create_publish_id
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence
from backend.utils.character_knowledge_validate import build_doc_id, parse_doc_id, parse_key_from_content, parse_value_from_content, validate_key, validate_value
from backend.utils.memory_vector import normalize_dense

MutationError = MemoryControlError
PUBLIC_TYPES = frozenset({"character_global", "character_knowledge"})
PRIVATE_TYPES = frozenset({"user", "character_private"})
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class MutationTarget:
    """Construct from authenticated/domain ownership, never an LLM/body owner."""
    partition_name: str
    doc_id: str
    memory_type: str
    owner_user_id: int
    target_epoch: int
    target_fingerprint: bytes


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).digest()


def body_hash(document):
    """The same semantic body encoded by dense/sparse; free mem_* stays whole."""
    fields = document["fields"]
    content = fields.get("content")
    if not isinstance(content, str):
        raise MutationError(20120, "memory_content_invalid")
    body = content if document["id"].startswith("mem_") else parse_value_from_content(content)
    return hashlib.sha256(body.encode()).digest()


def _validate_target(target):
    if (not isinstance(target, MutationTarget) or not isinstance(target.target_fingerprint, bytes)
            or len(target.target_fingerprint) != 32 or type(target.target_epoch) is not int or target.target_epoch < 1
            or not isinstance(target.partition_name, str) or not _NAME.fullmatch(target.partition_name)
            or not isinstance(target.doc_id, str) or not _NAME.fullmatch(target.doc_id)
            or type(target.owner_user_id) is not int):
        raise MutationError(20120, "memory_identity_invalid")
    if not ((target.memory_type in PUBLIC_TYPES and target.owner_user_id == 0)
            or (target.memory_type in PRIVATE_TYPES and target.owner_user_id > 0)):
        raise MutationError(20120, "memory_owner_invalid")
    parsed = parse_doc_id(target.doc_id)
    if parsed and parsed != (target.memory_type, str(target.owner_user_id)):
        raise MutationError(20120, "memory_owner_mismatch")


def _actor(actor_type, actor_id):
    if actor_type not in {"admin", "user", "text", "voice", "system"} or type(actor_id) is not int or actor_id <= 0:
        raise MutationError(20120, "memory_actor_invalid")


def _internal_id(value):
    try:
        identity = UUID(value)
        if str(identity) != value or identity.version != 4:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise MutationError(20120, "operation_id_invalid") from None
    return value


def _normalized_document(target, kind, document):
    try:
        if not isinstance(document, dict) or not {"id", "vector", "fields"} <= document.keys():
            raise ValueError()
        if set(document) - {"id", "vector", "fields", "sparse_vector"} or document["id"] != target.doc_id:
            raise ValueError()
        result = json.loads(_json(document))
        fields = result["fields"]
        if not isinstance(fields, dict) or fields.get("type") != target.memory_type or type(fields.get("user_id")) is not int or fields["user_id"] != target.owner_user_id:
            raise MutationError(20120, "memory_owner_mismatch")
        if any(key.lower() in {"api_key", "authorization", "password", "credential", "credentials", "prompt", "exception"} for key in fields):
            raise ValueError()
        # Prior control metadata is never accepted as the caller's authority.
        for key in list(fields):
            if key.startswith("mr_"):
                del fields[key]
        result.pop("sparse_vector", None)
        if kind == "delete":
            fields["content"], fields["key"] = "", ""
            result["vector"] = [1.0] + [0.0] * 1023
        else:
            if not isinstance(fields.get("content"), str) or not fields["content"].strip():
                raise ValueError()
            if parse_doc_id(target.doc_id):
                key = fields.get("key")
                if (not isinstance(key, str) or validate_key(key) or validate_value(parse_value_from_content(fields["content"]))
                        or parse_key_from_content(fields["content"]) != key
                        or target.doc_id != build_doc_id(target.memory_type, key, target.owner_user_id)):
                    raise MutationError(20120, "memory_stable_key_mismatch")
            result["vector"] = normalize_dense(result["vector"])
        if len(_json(result).encode()) > 1024 * 1024:
            raise MutationError(20120, "memory_payload_too_large")
        return result
    except MutationError:
        raise
    except Exception:
        raise MutationError(20120, "memory_payload_invalid") from None


class MemoryMutationService:
    def __init__(self, session_factory, remote, environment_id, encoder_version, clock=None, *, allow_isolated=False):
        if not isinstance(environment_id, str) or not environment_id or len(environment_id) > 64:
            raise MutationError(20120, "environment_invalid")
        if not isinstance(encoder_version, str) or not encoder_version or len(encoder_version) > 128:
            raise MutationError(20120, "encoder_version_invalid")
        self.sessions, self.remote = session_factory, remote
        self.environment_id, self.encoder_version = environment_id, encoder_version
        self.clock = clock or datetime.utcnow
        self.allow_isolated = allow_isolated

    @asynccontextmanager
    async def _session(self):
        # Bounded SQL/claim contention; remote calls never run inside this scope.
        async with asyncio.timeout(2):
            async with self.sessions() as db:
                yield db

    def _now(self):
        now = self.clock()
        return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now

    def _receipt(self, op):
        state = "full"
        if op.terminal_at and op.receipt_until and self._now() >= op.receipt_until:
            state = "expired"
        summary = op.receipt_summary or {}
        if summary.get("reason")=="cleared":state="cleared"
        source = op.source_result
        if source == "pending" and op.dispatch_state in {"dispatching", "unknown"}:
            source = "unknown"
        return {"operation_id": op.client_request_id or op.operation_id, "internal_operation_id": op.operation_id,
                "identity_id": op.identity_id, "generation": op.generation, "source_result": source,
                "index_result": op.index_result, "dispatch_state": op.dispatch_state, "revision": op.revision,
                "task_id": op.task_id, "receipt_state": state,
                "reason": "operation_receipt_expired" if state == "expired" else summary.get("reason"),
                "source_entry": summary.get("source_entry"),
                "operation_kind": op.operation_kind, "doc_id": summary.get("doc_id"),
                "memory_type": summary.get("memory_type"), "owner_user_id": summary.get("owner_user_id"),
                "observed_at": op.updated_at.isoformat(timespec="microseconds") + "Z"}

    async def _get(self, db, operation_id, actor_type, actor_id, *, lock=False):
        query = select(MemoryOperation).where(MemoryOperation.owner_actor_type == actor_type,
                                             MemoryOperation.owner_actor_id == actor_id)
        try:
            parsed = UUID(operation_id)
            if str(parsed) != operation_id or parsed.version not in {4, 7}:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise MutationError(20120, "operation_id_invalid") from None
        if parsed.version == 4:
            query = query.where(MemoryOperation.operation_id == operation_id)
        else:
            query = query.where(MemoryOperation.idempotency_hash == hashlib.sha256(operation_id.encode()).digest())
        if lock:
            query = query.with_for_update()
        op = await db.scalar(query.execution_options(populate_existing=True))
        if op and parsed.version == 7 and op.client_request_id != operation_id:
            raise MutationError(20121, "operation_identity_conflict")
        return op

    async def get_receipt(self, operation_id, *, actor_type, actor_id):
        _actor(actor_type, actor_id)
        try:
            async with self._session() as db:
                op = await self._get(db, operation_id, actor_type, actor_id)
                return self._receipt(op) if op else None
        except MutationError:
            raise
        except Exception:
            raise MutationError(20129, "operation_receipt_unreadable") from None

    async def _read_operation(self, operation_id, actor_type, actor_id):
        async with self._session() as db:
            return await self._get(db, operation_id, actor_type, actor_id)

    async def _unknown_receipt(self, operation_id, actor_type, actor_id):
        try:
            result = await self.get_receipt(operation_id, actor_type=actor_type, actor_id=actor_id)
            if result:
                if result["source_result"] not in {"confirmed", "failed", "superseded"}:
                    result.update(source_result="unknown", reason="operation_commit_unconfirmed")
                return result
        except MutationError:
            pass
        return {"operation_id": operation_id, "internal_operation_id": operation_id, "identity_id": None,
                "generation": None, "source_result": "unknown", "index_result": "unknown", "dispatch_state": "unknown",
                "revision": None, "task_id": None, "receipt_state": "unavailable", "source_entry": None,
                "reason": "operation_commit_unconfirmed", "observed_at": self._now().isoformat() + "Z"}

    async def _fence(self, db, epoch, fingerprint):
        return await require_active_fence(db, self.environment_id, epoch, fingerprint, self.allow_isolated)

    async def _identity(self, db, target):
        values = dict(target_epoch=target.target_epoch, target_fingerprint=target.target_fingerprint,
            partition_name=target.partition_name, doc_id=target.doc_id, memory_type=target.memory_type,
            owner_user_id=target.owner_user_id, generation=0, allocated_generation=0,
            source_state="unknown", index_state="not_ready", created_at=self._now(), updated_at=self._now(), revision=1)
        if db.get_bind().dialect.name == "mysql":
            statement = mysql_insert(MemoryIdentity).values(**values).on_duplicate_key_update(id=MemoryIdentity.id)
        else:
            statement = sqlite_insert(MemoryIdentity).values(**values).on_conflict_do_nothing(
                index_elements=["target_fingerprint", "partition_name", "doc_id"])
        await db.execute(statement)
        identity = await db.scalar(select(MemoryIdentity).where(
            MemoryIdentity.target_fingerprint == target.target_fingerprint,
            MemoryIdentity.partition_name == target.partition_name, MemoryIdentity.doc_id == target.doc_id,
        ).with_for_update().execution_options(populate_existing=True))
        if (identity.memory_type != target.memory_type or identity.owner_user_id != target.owner_user_id
                or identity.target_epoch != target.target_epoch):
            raise MutationError(20127, "memory_identity_mismatch")
        return identity

    async def _claim_blocked(self, db, identity_id):
        # Called after fence/identity locks. The claim lock serializes expiry
        # against begin_handoff: only a never-dispatched reservation may expire.
        query = select(MemoryUseClaim).join(MemoryUseItem, MemoryUseItem.claim_id == MemoryUseClaim.claim_id).where(
            MemoryUseItem.identity_id == identity_id, MemoryUseClaim.closed_at.is_(None),
        ).order_by(MemoryUseClaim.claim_id).with_for_update().execution_options(populate_existing=True)
        blocked = False
        for claim in (await db.scalars(query)).all():
            if claim.state == 'reserved' and claim.created_deadline_at <= self._now():
                claim.state = 'aborted'
                claim.closed_at = self._now()
                claim.error_code = 'reserved_expired_before_dispatch'
                claim.revision += 1
            else:
                blocked = True
        return blocked

    async def prepare(self, *, target, kind, document, actor_type, actor_id, client_request_id=None, source_entry="", request_digest=None, receipt_extra=None, expected_generation=None):
        _validate_target(target)
        _actor(actor_type, actor_id)
        if actor_type == "user" and target.owner_user_id != actor_id:
            raise MutationError(20120, "memory_owner_mismatch")
        if kind not in {"create", "update", "delete"} or not isinstance(source_entry, str) or len(source_entry) > 64:
            raise MutationError(20120, "memory_operation_invalid")
        if client_request_id is not None:
            try:
                get_or_create_publish_id(client_request_id)
            except Exception:
                raise MutationError(20120, "client_request_id_invalid") from None
        if receipt_extra is not None and (not isinstance(receipt_extra, dict)
                or set(receipt_extra) - {'stable_key','legacy_sql_digest'} or len(_json(receipt_extra).encode()) > 255 * 1024):
            raise MutationError(20120, 'receipt_summary_invalid')
        if expected_generation is not None and (type(expected_generation) is not int or expected_generation<0):
            raise MutationError(20120,'expected_generation_invalid')
        normalized = _normalized_document(target, kind, document)
        request_hash = _hash({"target": [target.target_fingerprint.hex(), target.target_epoch, target.partition_name,
            target.doc_id, target.memory_type, target.owner_user_id], "kind": kind, "document": normalized, "source_entry": source_entry})
        if request_digest is not None:
            if not isinstance(request_digest, bytes) or len(request_digest) != 32:
                raise MutationError(20120, "request_digest_invalid")
            request_hash = request_digest
        operation_id = str(uuid4())
        durable_intent = False
        try:
            async with self._session() as db:
                if client_request_id:
                    prior = await self._get(db, client_request_id, actor_type, actor_id)
                    if prior:
                        if not hmac.compare_digest(prior.request_hash, request_hash):
                            raise MutationError(20121, "operation_identity_conflict")
                        return self._receipt(prior)
                    age = int(self._now().replace(tzinfo=timezone.utc).timestamp()*1000) - (UUID(client_request_id).int >> 80)
                    if age > 120000 or age < -30000:
                        raise MutationError(20123, "operation_id_outside_window")
                await self._fence(db, target.target_epoch, target.target_fingerprint)
                # Recheck after the environment/identity serialization boundary.
                if client_request_id:
                    prior = await self._get(db, client_request_id, actor_type, actor_id, lock=True)
                    if prior:
                        if not hmac.compare_digest(prior.request_hash, request_hash):
                            raise MutationError(20121, "operation_identity_conflict")
                        return self._receipt(prior)
                identity = await self._identity(db, target)
                if expected_generation is not None and identity.generation!=expected_generation:
                    raise MutationError(20127,'memory_generation_changed')
                if identity.inflight_operation_id is not None:
                    raise MutationError(20128, "memory_source_unverified")
                if await self._claim_blocked(db, identity.id):
                    raise MutationError(20126, "memory_in_use")
                if kind == "create" and identity.source_state == "live":
                    raise MutationError(20121, "memory_already_exists")
                if kind in {"update", "delete"} and identity.source_state != "live":
                    raise MutationError(20125, "memory_source_unavailable")
                generation, now = identity.allocated_generation + 1, self._now()
                identity.allocated_generation, identity.inflight_operation_id = generation, operation_id
                identity.revision, identity.updated_at = identity.revision + 1, now
                remote_tag = str(uuid4())
                digest = body_hash(normalized)
                normalized["fields"].update(mr_epoch=target.target_epoch, mr_generation=generation,
                    mr_body_sha256=digest.hex(), mr_operation_id=remote_tag,
                    mr_deleted=kind == "delete", mr_encoder_version="")
                if len(_json(normalized).encode()) > 1024 * 1024:
                    raise MutationError(20120, "memory_payload_too_large")
                op = MemoryOperation(operation_id=operation_id, identity_id=identity.id, generation=generation,
                    source_generation_key=_hash([identity.id, generation]), operation_kind=kind,
                    owner_actor_type=actor_type, owner_actor_id=actor_id, client_request_id=client_request_id,
                    idempotency_hash=hashlib.sha256(client_request_id.encode()).digest() if client_request_id else None,
                    request_hash=request_hash, target_epoch=target.target_epoch, source_result="pending",
                    index_result="not_required" if kind == "delete" else "pending", dispatch_state="prepared",
                    pending_payload=normalized, payload_hash=_hash(normalized), remote_tag=remote_tag, worker_epoch=0,
                    reconcile_until=now + timedelta(seconds=120), created_at=now, updated_at=now, revision=1,
                    receipt_summary={"source_entry": source_entry, "doc_id": target.doc_id,
                        "memory_type": target.memory_type, "owner_user_id": target.owner_user_id,
                        "encoder_version": self.encoder_version, **(receipt_extra or {})})
                db.add(op)
                await db.flush()
                durable_intent = True
                await db.commit()
            # Read durable identity, not an ORM object left in a committed session.
            verified = await self._read_operation(operation_id, actor_type, actor_id)
            if verified is None or verified.request_hash != request_hash:
                return await self._unknown_receipt(operation_id, actor_type, actor_id)
            return self._receipt(verified)
        except MutationError:
            raise
        except Exception:
            if durable_intent:
                return await self._unknown_receipt(operation_id, actor_type, actor_id)
            raise MutationError(20129, "operation_preparation_unavailable") from None

    async def prepare_batch_delete(self, *, targets, requested_doc_ids, actor_id, target_epoch,
                                   target_fingerprint, client_request_id=None):
        """Bind the entire ordered input and every eligible child before any send.

        targets has trusted user targets or None for fixed invalid/non-user items.
        Lock order remains environment -> sorted identities -> operations.
        """
        _actor('admin', actor_id)
        if len(_json(requested_doc_ids).encode()) > 240 * 1024:
            raise MutationError(20120, 'receipt_summary_too_large')
        digest = _hash({'kind': 'batch', 'doc_ids': requested_doc_ids})
        if client_request_id is not None:
            try:
                get_or_create_publish_id(client_request_id)
            except Exception:
                raise MutationError(20120, 'client_request_id_invalid') from None
        async with self._session() as db:
            if client_request_id:
                prior = await self._get(db, client_request_id, 'admin', actor_id)
                if prior:
                    if not hmac.compare_digest(prior.request_hash, digest):
                        raise MutationError(20121, 'operation_identity_conflict')
                    return prior, False
                age = int(self._now().replace(tzinfo=timezone.utc).timestamp()*1000) - (UUID(client_request_id).int >> 80)
                if age > 120000 or age < -30000:
                    raise MutationError(20123, 'operation_id_outside_window')
            valid = [target for target in targets if target is not None]
            await self._fence(db, target_epoch, target_fingerprint)
            if client_request_id:
                prior = await self._get(db, client_request_id, 'admin', actor_id, lock=True)
                if prior:
                    if not hmac.compare_digest(prior.request_hash, digest):
                        raise MutationError(20121, 'operation_identity_conflict')
                    return prior, False
            identities = {}
            for target in sorted(valid, key=lambda target: target.doc_id):
                _validate_target(target)
                if (target.memory_type != 'user' or target.target_epoch != target_epoch
                        or target.target_fingerprint != target_fingerprint):
                    raise MutationError(20120, 'memory_owner_invalid')
                identities[target.doc_id] = await self._identity(db, target)
            now, parent_id = self._now(), str(uuid4())
            parent = MemoryOperation(operation_id=parent_id, operation_kind='batch', owner_actor_type='admin',
                owner_actor_id=actor_id, client_request_id=client_request_id,
                idempotency_hash=hashlib.sha256(client_request_id.encode()).digest() if client_request_id else None,
                request_hash=digest, target_epoch=target_epoch,
                source_result='pending', index_result='pending', dispatch_state='prepared', remote_tag=str(uuid4()),
                worker_epoch=0, reconcile_until=now + timedelta(seconds=120), created_at=now, updated_at=now,
                revision=1, receipt_summary={'memory_type': 'user', 'items': []})
            db.add(parent)
            await db.flush()
            items = []
            for seq, (doc_id, target) in enumerate(zip(requested_doc_ids, targets)):
                item = {'input_seq': seq, 'requested_doc_id': doc_id, 'child_operation_id': None}
                identity = identities.get(doc_id)
                reason = ('invalid_or_non_user' if target is None else
                    'memory_source_unverified' if identity.inflight_operation_id else
                    'memory_source_unavailable' if identity.source_state != 'live' else
                    'memory_in_use' if await self._claim_blocked(db, identity.id) else None)
                if reason:
                    item.update(source_state='failed', index_state='not_executed', reason=reason)
                    items.append(item)
                    continue
                child_id, remote_tag = str(uuid4()), str(uuid4())
                document = _normalized_document(target, 'delete', {'id': doc_id, 'vector': [1.0]+[0.0]*1023,
                    'fields': {'type': 'user', 'user_id': target.owner_user_id, 'content': ''}})
                generation = identity.allocated_generation + 1
                identity.allocated_generation, identity.inflight_operation_id = generation, child_id
                identity.revision, identity.updated_at = identity.revision + 1, now
                document['fields'].update(mr_epoch=target.target_epoch, mr_generation=generation,
                    mr_body_sha256=body_hash(document).hex(), mr_operation_id=remote_tag, mr_deleted=True, mr_encoder_version='')
                db.add(MemoryOperation(operation_id=child_id, identity_id=identity.id, generation=generation,
                    source_generation_key=_hash([identity.id,generation]), parent_operation_id=parent_id,
                    operation_kind='delete', owner_actor_type='admin', owner_actor_id=actor_id,
                    request_hash=_hash(document), target_epoch=target.target_epoch, source_result='pending',
                    index_result='not_required', dispatch_state='prepared', pending_payload=document,
                    payload_hash=_hash(document), remote_tag=remote_tag, worker_epoch=0,
                    reconcile_until=now + timedelta(seconds=120), created_at=now, updated_at=now, revision=1,
                    receipt_summary={'source_entry':'admin:batch','doc_id':doc_id,'memory_type':'user',
                        'owner_user_id':target.owner_user_id,'encoder_version':self.encoder_version}))
                item['child_operation_id'] = child_id
                items.append(item)
            parent.receipt_summary = {'memory_type':'user','items':items}
            try:
                await db.commit()
            except Exception:
                error = MutationError(20122, 'batch_commit_unconfirmed')
                error.receipt = {**self._receipt(parent), 'source_result':'unknown', 'index_result':'unknown'}
                raise error from None
        verified = await self._read_operation(parent_id, 'admin', actor_id)
        if verified is None or verified.request_hash != digest:
            error = MutationError(20122, 'batch_preparation_unconfirmed')
            error.receipt = {**self._receipt(parent), 'source_result':'unknown', 'index_result':'unknown'}
            raise error
        return verified, True

    async def _locked_operation(self, db, operation_id, actor_type, actor_id):
        op = await self._get(db, operation_id, actor_type, actor_id)
        if op is None or op.identity_id is None:
            raise MutationError(20125, "operation_unavailable")
        identity = await db.get(MemoryIdentity, op.identity_id)
        if identity is None:
            raise MutationError(20129, "memory_identity_unavailable")
        await self._fence(db, op.target_epoch, identity.target_fingerprint)
        identity = await db.scalar(select(MemoryIdentity).where(MemoryIdentity.id == op.identity_id)
                                  .with_for_update().execution_options(populate_existing=True))
        op = await self._get(db, operation_id, actor_type, actor_id, lock=True)
        return op, identity

    async def dispatch(self, operation_id, *, actor_type, actor_id):
        _actor(actor_type, actor_id)
        _internal_id(operation_id)
        worker, worker_epoch = str(uuid4()), None
        remote_started = False
        try:
            async with self._session() as db:
                op, identity = await self._locked_operation(db, operation_id, actor_type, actor_id)
                if op.dispatch_state != "prepared" or op.source_result != "pending":
                    return self._receipt(op)
                if identity.inflight_operation_id != op.operation_id or identity.allocated_generation != op.generation:
                    raise MutationError(20127, "operation_not_current")
                if await self._claim_blocked(db, identity.id):
                    raise MutationError(20126, "memory_in_use")
                now = self._now()
                encoder_version = (op.receipt_summary or {}).get("encoder_version")
                if not isinstance(encoder_version, str) or not encoder_version or len(encoder_version) > 128:
                    raise MutationError(20128, "operation_encoder_unverified")
                if now >= op.reconcile_until:
                    self._failed(op, identity, "operation_expired_before_dispatch")
                    await db.commit()
                    return self._receipt(op)
                op.worker_id, op.worker_epoch = worker, op.worker_epoch + 1
                worker_epoch = op.worker_epoch
                op.lease_until, op.dispatch_state = now + timedelta(seconds=15), "claimed"
                op.revision, op.updated_at = op.revision + 1, now
                await db.commit()
            claimed = await self._read_operation(operation_id, actor_type, actor_id)
            if claimed is None or claimed.worker_id != worker or claimed.worker_epoch != worker_epoch or claimed.dispatch_state != "claimed":
                return await self._unknown_receipt(operation_id, actor_type, actor_id)
            async with self._session() as db:
                op, identity = await self._locked_operation(db, operation_id, actor_type, actor_id)
                if (op.dispatch_state != "claimed" or op.worker_id != worker or op.worker_epoch != worker_epoch
                        or op.lease_until <= self._now() or op.reconcile_until <= self._now()):
                    return self._receipt(op)
                if identity.inflight_operation_id != operation_id or identity.allocated_generation != op.generation:
                    raise MutationError(20127, "operation_not_current")
                op.dispatch_state, op.dispatched_at = "dispatching", self._now()
                op.updated_at, op.revision = self._now(), op.revision + 1
                await db.commit()
            sent = await self._read_operation(operation_id, actor_type, actor_id)
            if (sent is None or sent.dispatch_state != "dispatching" or sent.worker_id != worker
                    or sent.worker_epoch != worker_epoch or sent.pending_payload is None
                    or _hash(sent.pending_payload) != sent.payload_hash):
                return await self._unknown_receipt(operation_id, actor_type, actor_id)
            async with self._session() as db:
                identity = await db.get(MemoryIdentity, sent.identity_id)
                partition = identity.partition_name
            # Exactly one call; cancellation/timeouts cannot make another lease a sender.
            try:
                remote_started = True
                result = await asyncio.wait_for(self.remote.full_upsert(partition, deepcopy(sent.pending_payload)), timeout=10)
                status = getattr(result, "status", None)
            except asyncio.CancelledError:
                await self._mark_unknown(operation_id, actor_type, actor_id, "remote_outcome_unknown")
                raise
            except Exception:
                status = "unknown"
            if status == "confirmed":
                return await self._confirm(operation_id, actor_type, actor_id)
            if status == "rejected":
                async with self._session() as db:
                    op, identity = await self._locked_operation(db, operation_id, actor_type, actor_id)
                    if op.source_result not in {"confirmed", "failed"}:
                        self._failed(op, identity, "remote_rejected")
                        await db.commit()
                    return self._receipt(op)
            return await self._mark_unknown(operation_id, actor_type, actor_id, "remote_outcome_unknown")
        except MutationError:
            if remote_started:
                return await self._unknown_receipt(operation_id, actor_type, actor_id)
            raise
        except Exception:
            return await self._unknown_receipt(operation_id, actor_type, actor_id)

    def _terminal(self, op):
        now = self._now()
        op.pending_payload = None
        op.terminal_at, op.receipt_until, op.tombstone_until = now, now + timedelta(days=7), now + timedelta(days=30)
        op.lease_until, op.worker_id = None, None
        op.updated_at, op.revision = now, op.revision + 1

    def _failed(self, op, identity, reason):
        op.source_result, op.dispatch_state = "failed", "not_sent"
        op.index_result = "not_required"
        op.receipt_summary = {**(op.receipt_summary or {}), "reason": reason}
        if identity.inflight_operation_id == op.operation_id:
            identity.inflight_operation_id = None
            identity.updated_at, identity.revision = self._now(), identity.revision + 1
        self._terminal(op)

    async def _mark_unknown(self, operation_id, actor_type, actor_id, reason):
        try:
            async with self._session() as db:
                op, identity = await self._locked_operation(db, operation_id, actor_type, actor_id)
                if op.source_result in {"confirmed", "failed", "superseded"}:
                    return self._receipt(op)
                op.source_result, op.dispatch_state = "unknown", "unknown"
                op.receipt_summary = {**(op.receipt_summary or {}), "reason": reason}
                op.revision, op.updated_at = op.revision + 1, self._now()
                if self._now() >= op.reconcile_until:
                    op.index_result, identity.index_state = "manual", "manual"
                    identity.revision, identity.updated_at = identity.revision + 1, self._now()
                await db.commit()
                return self._receipt(op)
        except Exception:
            return await self._unknown_receipt(operation_id, actor_type, actor_id)

    async def _confirm(self, operation_id, actor_type, actor_id):
        try:
            async with self._session() as db:
                op, identity = await self._locked_operation(db, operation_id, actor_type, actor_id)
                if op.source_result in {"confirmed", "failed", "superseded"}:
                    return self._receipt(op)
                if (identity.inflight_operation_id != operation_id or identity.allocated_generation != op.generation
                        or op.pending_payload is None or _hash(op.pending_payload) != op.payload_hash):
                    raise MutationError(20128, "operation_confirmation_unverified")
                if op.dispatch_state not in {"dispatching", "unknown"}:
                    raise MutationError(20128, "operation_not_dispatched")
                now = self._now()
                encoder_version = (op.receipt_summary or {}).get("encoder_version")
                if not isinstance(encoder_version, str) or not encoder_version or len(encoder_version) > 128:
                    raise MutationError(20128, "operation_encoder_unverified")
                # Pending old tasks lose eligibility; completed historical evidence stays unchanged.
                old_tasks = list((await db.scalars(select(MemoryIndexTask).where(
                    MemoryIndexTask.identity_id == identity.id,
                    MemoryIndexTask.state.not_in({"completed", "superseded"}),
                ).with_for_update())).all())
                for task in old_tasks:
                    task.state, task.updated_at, task.revision = "superseded", now, task.revision + 1
                identity.generation, identity.body_hash = op.generation, body_hash(op.pending_payload)
                identity.current_operation_id, identity.inflight_operation_id = operation_id, None
                identity.source_state = "deleted" if op.operation_kind == "delete" else "live"
                identity.index_state = "deleted" if op.operation_kind == "delete" else "not_ready"
                identity.encoder_version = None if op.operation_kind == "delete" else encoder_version
                identity.updated_at, identity.revision = now, identity.revision + 1
                op.source_result, op.dispatch_state = "confirmed", "confirmed"
                op.index_result = "not_required" if op.operation_kind == "delete" else "pending"
                op.receipt_summary = {**(op.receipt_summary or {}), "reason": None}
                if op.operation_kind != "delete":
                    task = MemoryIndexTask(task_id=str(uuid4()), identity_id=identity.id, operation_id=operation_id,
                        generation=op.generation, encoder_version=encoder_version, body_hash=identity.body_hash,
                        state="pending", round_no=0, attempt=0, round_started_at=now,
                        round_deadline_at=now + timedelta(seconds=120), next_attempt_at=now, worker_epoch=0,
                        created_at=now, updated_at=now, revision=1)
                    db.add(task)
                    await db.flush()
                    op.task_id = task.task_id
                self._terminal(op)
                await db.commit()
                return self._receipt(op)
        except Exception:
            return await self._unknown_receipt(operation_id, actor_type, actor_id)

    async def reconcile(self, operation_id, *, actor_type, actor_id):
        _actor(actor_type, actor_id)
        _internal_id(operation_id)
        try:
            op = await self._read_operation(operation_id, actor_type, actor_id)
            if op is None:
                raise MutationError(20125, "operation_unavailable")
            if op.source_result in {"confirmed", "failed", "superseded"} or op.dispatch_state in {"prepared", "claimed"}:
                return self._receipt(op)
            if self._now() >= op.reconcile_until:
                return await self._mark_unknown(operation_id, actor_type, actor_id, "operation_manual_required")
            async with self._session() as db:
                identity = await db.get(MemoryIdentity, op.identity_id)
                if identity is None:
                    raise MutationError(20129, "memory_identity_unavailable")
                await self._fence(db, op.target_epoch, identity.target_fingerprint)
                partition, doc_id = identity.partition_name, identity.doc_id
            try:
                fetched = await asyncio.wait_for(self.remote.fetch(partition, doc_id), timeout=3)
            except Exception:
                fetched = None
            if self._matches(op, identity, fetched):
                return await self._confirm(operation_id, actor_type, actor_id)
            return await self._mark_unknown(operation_id, actor_type, actor_id, "remote_evidence_unverified")
        except MutationError:
            raise
        except Exception:
            return await self._unknown_receipt(operation_id, actor_type, actor_id)

    def _matches(self, op, identity, fetched):
        try:
            if getattr(fetched, "status", None) != "found" or not isinstance(fetched.document, dict):
                return False
            actual, expected = fetched.document, op.pending_payload
            if not expected or _hash(expected) != op.payload_hash or actual.get("id") != identity.doc_id:
                return False
            fields = actual["fields"]
            if (fields != expected["fields"] or fields.get("mr_operation_id") != op.remote_tag
                    or type(fields.get("mr_epoch")) is not int or fields["mr_epoch"] != op.target_epoch
                    or type(fields.get("mr_generation")) is not int or fields["mr_generation"] != op.generation
                    or fields.get("type") != identity.memory_type or type(fields.get("user_id")) is not int
                    or fields["user_id"] != identity.owner_user_id or body_hash(actual) != body_hash(expected)
                    or type(fields.get("mr_deleted")) is not bool
                    or fields.get("mr_body_sha256") != body_hash(expected).hex()
                    or actual.get("sparse_vector")):
                return False
            normalize_dense(actual["vector"])  # Validate; never repair a readback into proof.
            vector = actual["vector"]
            return all(abs(a-b) <= 1e-6 for a, b in zip(vector, expected["vector"]))
        except Exception:
            return False

    async def write(self, **kwargs):
        prepared = await self.prepare(**kwargs)
        if prepared["dispatch_state"] != "prepared" or prepared["source_result"] != "pending" or prepared["receipt_state"] != "full":
            return prepared
        return await self.dispatch(prepared["internal_operation_id"], actor_type=kwargs["actor_type"], actor_id=kwargs["actor_id"])
