"""M4 four-route, independent dense/BM25 retrieval. Opt-in until M6 wiring.

Remote fields are evidence to compare with SQL truth, never authority. The
immutable DTO survives rerank and Prompt selection without borrowing stale ranks.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
import hashlib
import math

from sqlalchemy import select

from backend.models.memory_control import MemoryIdentity, MemoryOperation
from backend.services.memory_runtime_service import require_active_fence
from backend.utils.character_knowledge_validate import parse_value_from_content, parse_key_from_content, build_doc_id

ROUTE_TYPES = {'cg': 'character_global', 'cp': 'character_private', 'ck': 'character_knowledge', 'user': 'user'}


@dataclass(frozen=True)
class Candidate:
    route: str
    identity_id: int
    partition: str
    doc_id: str
    generation: int
    body_hash: bytes
    value: str = field(repr=False)
    memory_type: str = ''
    owner_user_id: int = 0
    key: str | None = None
    source_channels: tuple[str, ...] = ()
    dense_rank: int | None = None
    bm25_rank: int | None = None
    dense_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None
    route_rank: int = 0
    order_method: str = 'input'
    admission_reason: str = 'current_source'
    trust_state: str = 'verified'
    encoder_version: str | None = None


@dataclass(frozen=True)
class Removal:
    doc_id: str
    route: str
    reason: str
    stage: str = 'candidate'
    identity_id: int | None = None


@dataclass(frozen=True)
class RouteResult:
    route: str
    question: str = field(repr=False)
    candidates: tuple[Candidate, ...] = ()
    removed: tuple[Removal, ...] = ()
    dense_status: str = 'skipped'
    bm25_status: str = 'skipped'
    rerank_status: str = 'not_started'
    reason: str | None = None
    candidate_snapshots: tuple[Candidate, ...] = ()


class CandidateValidator:
    def __init__(self, session_factory, environment_id, *, allow_isolated=False):
        self.sessions, self.environment_id, self.allow_isolated = session_factory, environment_id, allow_isolated

    async def merge(self, route, user_id, partition, config, dense, sparse):
        if route not in ROUTE_TYPES or type(user_id) is not int or user_id <= 0:
            raise ValueError('candidate_context_invalid')
        rows = list(dense) + list(sparse)
        ids = {r['id'] for r in rows if isinstance(r, dict) and isinstance(r.get('id'), str)}
        target = bytes.fromhex(config.target_fingerprint)
        async with self.sessions() as db:
            await require_active_fence(db, self.environment_id, config.target_epoch, target,
                                       allow_isolated=self.allow_isolated, lock=False)
            records = {r.doc_id: r for r in (await db.scalars(select(MemoryIdentity).where(
                MemoryIdentity.target_fingerprint == target, MemoryIdentity.partition_name == partition,
                MemoryIdentity.doc_id.in_(ids)))).all()}
            pending = {op_id for r in records.values()
                       for op_id in (r.inflight_operation_id, r.current_operation_id) if op_id}
            ops = {o.operation_id: o for o in (await db.scalars(select(MemoryOperation).where(
                MemoryOperation.operation_id.in_(pending)))).all()} if pending else {}
        merged, removed = {}, []
        for channel, documents in [('dense', dense), ('bm25', sparse)]:
            seen = set()
            for rank, document in enumerate(documents, 1):
                doc_id = document.get('id', '') if isinstance(document, dict) else ''
                row = records.get(doc_id)
                reason, value, key = self._check(document, row, route, user_id, config, channel, ops)
                if reason:
                    removed.append(Removal(doc_id, route, reason, identity_id=row.id if row else None))
                    continue
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                item = merged.get(doc_id) or Candidate(route, row.id, partition, doc_id, row.generation,
                    row.body_hash, value, row.memory_type, row.owner_user_id, key,
                    encoder_version=row.encoder_version)
                merged[doc_id] = replace(item, source_channels=item.source_channels + (channel,),
                    **{channel + '_rank': rank, channel + '_score': float(document['score'])})
        return tuple(merged.values()), tuple(removed)

    @staticmethod
    def _check(document, row, route, user_id, config, channel, ops):
        fail = lambda reason: (reason, '', None)
        if row is None or not isinstance(document, dict) or not isinstance(document.get('fields'), dict):
            return fail('unverified')
        fields = document['fields']
        owner = user_id if route in {'cp', 'user'} else 0
        if (row.memory_type != ROUTE_TYPES[route] or row.owner_user_id != owner
                or fields.get('type') != row.memory_type or type(fields.get('user_id')) is not int
                or fields['user_id'] != owner):
            return fail('ownership')
        if row.source_state == 'deleted' or fields.get('mr_deleted') is True:
            return fail('deleted')
        if row.source_state != 'live':
            return fail('unverified')
        if row.inflight_operation_id:
            op = ops.get(row.inflight_operation_id)
            if not (op and op.operation_kind == 'index' and op.identity_id == row.id
                    and op.generation == row.generation and op.target_epoch == row.target_epoch
                    and op.source_result == 'confirmed' and op.task_id is not None
                    and op.dispatch_state in {'prepared', 'claimed', 'dispatching', 'unknown'}):
                return fail('unverified')
        if type(document.get('score')) not in (int, float) or not math.isfinite(document['score']):
            return fail('unverified')
        if row.target_epoch != config.target_epoch:
            return fail('stale')
        content = fields.get('content')
        if not isinstance(content, str) or not content.strip():
            return fail('unverified')
        legacy = row.doc_id.startswith('mem_')
        value = content if legacy else parse_value_from_content(content)
        key = None if legacy else fields.get('key')
        if not legacy:
            if (not isinstance(key, str) or parse_key_from_content(content) != key
                    or build_doc_id(row.memory_type, key, owner) != row.doc_id):
                return fail('unverified')
        digest = hashlib.sha256(value.encode()).digest()
        if not value.strip() or digest != row.body_hash:
            return fail('stale')
        # Only an initial, SQL-confirmed baseline can prove a legacy snapshot
        # without remote version tags. After any allocated mutation, identical
        # body text alone cannot distinguish an old score from the current one.
        baseline = ops.get(row.current_operation_id)
        unversioned_baseline = (legacy and row.generation == row.allocated_generation == 1
            and baseline is not None and baseline.operation_kind == 'baseline'
            and baseline.identity_id == row.id and baseline.generation == 1
            and baseline.target_epoch == row.target_epoch
            and baseline.source_result == 'confirmed' and baseline.dispatch_state == 'confirmed')
        for name, expected in [('mr_epoch', row.target_epoch), ('mr_generation', row.generation)]:
            if name in fields:
                if type(fields[name]) is not int or fields[name] != expected:
                    return fail('stale')
            elif not unversioned_baseline:
                return fail('unverified')
        if fields.get('mr_body_sha256', digest.hex() if unversioned_baseline else None) != digest.hex():
            return fail('stale')
        if 'mr_deleted' in fields and fields['mr_deleted'] is not False:
            return fail('unverified')
        if channel == 'bm25' and (document['score'] <= 0 or row.index_state != 'ready'
                or row.encoder_version != config.encoder_version
                or fields.get('mr_encoder_version') != config.encoder_version):
            return fail('stale')
        return None, value, key


async def _direct_call(kind, invoke):
    return await invoke()


async def retrieve_route(route, query, *, user_id, partition, config, remote, encoder,
                         embed, validator, call=None):
    if route not in ROUTE_TYPES or type(user_id) is not int or user_id <= 0:
        raise ValueError('candidate_context_invalid')
    if query.skipped:
        return RouteResult(route, query.question, reason='explicit_skip')
    call = call or _direct_call
    limits = config.retrieval['routes'][route]
    filter_text = "type='" + ROUTE_TYPES[route] + "'"
    if route in {'cp', 'user'}:
        filter_text += f' AND user_id={user_id}'

    async def dense():
        vector = await call('embedding', lambda: embed(query.question))
        result = await call('vector_query', lambda: remote.query_dense(partition, vector,
            top_k=limits['dense_top_k'], filter=filter_text))
        return result

    async def sparse():
        if encoder.encoder_version != config.encoder_version:
            raise ValueError('encoder_version_mismatch')
        encoded = encoder.encode_query(query.keywords)
        if not encoded:
            return None
        return await call('vector_query', lambda: remote.query_sparse(partition, encoded,
            top_k=limits['bm25_top_k'], filter=filter_text))

    async def channel(invoke):
        try:
            result = await invoke()
            if result is None:
                return 'no_terms', ()
            if result.status != 'confirmed':
                return 'error', ()
            return ('ok' if result.documents else 'no_match'), result.documents
        except Exception:
            return 'error', ()

    (ds, dense_rows), (bs, sparse_rows) = await asyncio.gather(channel(dense), channel(sparse))
    # A remote server returning more than requested cannot expand rerank inputs.
    dense_rows, sparse_rows = dense_rows[:limits['dense_top_k']], sparse_rows[:limits['bm25_top_k']]
    try:
        candidates, removed = await validator.merge(route, user_id, partition, config, dense_rows, sparse_rows)
        return RouteResult(route, query.question, candidates, removed, ds, bs)
    except Exception:
        return RouteResult(route, query.question, dense_status=ds, bm25_status=bs, reason='source_unverified')
