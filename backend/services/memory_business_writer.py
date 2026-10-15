"""Business write adapters for the active new target; indexes remain durable tasks.

The string-compatible result preserves old document-id boundaries while its
receipt distinguishes a saved source from an index awaiting independent repair.
"""
from types import SimpleNamespace
import hashlib
import json
import os
from sqlalchemy import select

from backend.models.memory_control import MemoryIdentity, MemoryOperation
from backend.services.memory_mutation_service import MemoryMutationService, MutationTarget, PUBLIC_TYPES, PRIVATE_TYPES
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence
from backend.utils.character_knowledge_validate import build_doc_id, build_content, validate_key, validate_value
from backend.utils.memory_vector import normalize_dense


class MemoryWriteResult(str):
    def __new__(cls, doc_id, receipt):
        result = super().__new__(cls, doc_id)
        result.receipt = {**receipt, 'doc_id': doc_id}
        return result


class VoiceAtomResult(str):
    def __new__(cls, status, receipt=None):
        result = super().__new__(cls, status)
        result.receipt = receipt
        return result


def source_identity(channel, *parts):
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return channel + ':' + digest[:58]


class MemoryBusinessWriter:
    def __init__(self, sessions, mutations, config, embed, partition='default'):
        self.sessions, self.mutations, self.config, self.embed, self.partition = sessions, mutations, config, embed, partition
        self.context = {k: getattr(config, k) for k in ('target_epoch', 'target_fingerprint', 'encoder_version', 'config_snapshot_id')}
        self.context['versions'] = config.public()['versions'] if hasattr(config, 'public') else {}

    async def validate_context(self, expected=None):
        if expected and any(expected.get(k) != self.context[k] for k in ('target_epoch','target_fingerprint','encoder_version')):
            raise MemoryControlError(20127, 'runtime_target_changed')
        if expected and 'versions' in expected and expected['versions'] != self.context['versions']:
            raise MemoryControlError(20127, 'runtime_config_changed')
        async with self.mutations._session() as db:
            await require_active_fence(db, self.mutations.environment_id, self.config.target_epoch,
                bytes.fromhex(self.config.target_fingerprint), self.mutations.allow_isolated, lock=False)

    async def _prior(self, source_entry, source, actor_id, doc_id):
        if not source_entry:
            return None
        async with self.mutations._session() as db:
            # The entry binds trusted execution + atom. Never substitute the
            # newest identity operation for this original source receipt.
            op = await db.scalar(select(MemoryOperation).where(
                MemoryOperation.owner_actor_type == source, MemoryOperation.owner_actor_id == actor_id,
                MemoryOperation.operation_kind.in_({'create','update'}),
                MemoryOperation.receipt_summary['source_entry'].as_string() == source_entry,
                MemoryOperation.receipt_summary['doc_id'].as_string() == doc_id,
            ).order_by(MemoryOperation.created_at.desc()).limit(1))
            if op is not None:
                return self.mutations._receipt(op)
        return None

    async def upsert(self, *, memory_type, user_id, source, key=None, value=None, doc_id=None,
                     fields=None, vector=None, source_entry='', resume_only=False):
        if (memory_type not in PUBLIC_TYPES | PRIVATE_TYPES or source not in {'text','voice','admin','unknown','system'}
                or type(user_id) is not int or user_id < 1):
            raise ValueError('invalid_memory_atom')
        owner = user_id if memory_type in PRIVATE_TYPES else 0
        if doc_id is None:
            if not isinstance(key,str) or not isinstance(value,str) or validate_key(key) or validate_value(value):
                raise ValueError('invalid_user_memory_atom')
            key,value = key.strip(),value.strip()
            doc_id=build_doc_id(memory_type,key,owner)
            segments=key.split('-')
            fields={'key':key,'stable_key':key,'key_l1':segments[0],'key_l2':'-'.join(segments[:2]),
                    'content':build_content(key,value)}
        elif not isinstance(doc_id,str) or not doc_id.startswith('mem_') or not isinstance(fields,dict):
            raise ValueError('invalid_memory_atom')
        actor_type = 'system' if source == 'unknown' else source
        prior=await self._prior(source_entry,actor_type,user_id,doc_id)
        if prior:
            if prior['dispatch_state'] == 'prepared' and prior['source_result'] == 'pending':
                prior=await self.mutations.dispatch(prior['internal_operation_id'],actor_type=actor_type,actor_id=user_id)
            elif prior['source_result'] not in {'confirmed','failed','superseded'}:
                prior=await self.mutations.reconcile(prior['internal_operation_id'],actor_type=actor_type,actor_id=user_id)
            return MemoryWriteResult(doc_id,prior)
        if resume_only:
            return MemoryWriteResult(doc_id,{'source_result':'confirmed','index_result':'unknown','task_id':None,
                'reason':'legacy_trace_without_operation','internal_operation_id':None})
        await self.validate_context()
        if vector is None:
            vector=await self.embed(value)
        vector=normalize_dense(vector)
        target=MutationTarget(self.partition,doc_id,memory_type,owner,self.config.target_epoch,bytes.fromhex(self.config.target_fingerprint))
        async with self.mutations._session() as db:
            identity=await db.scalar(select(MemoryIdentity).where(MemoryIdentity.target_fingerprint==target.target_fingerprint,
                MemoryIdentity.partition_name==self.partition,MemoryIdentity.doc_id==doc_id))
            kind='update' if identity and identity.source_state=='live' else 'create'
        document={'id':doc_id,'vector':vector,'fields':{**fields,'type':memory_type,'user_id':owner,'last_write_source':source}}
        from backend.services.memory_write_source import observe_previous_source, record_source_observation
        async def fetch(ids):
            found = await self.mutations.remote.fetch(self.partition, ids[0])
            return {ids[0]: found.document} if found.status == 'found' else {}
        previous = await observe_previous_source(SimpleNamespace(fetch_by_ids=fetch), doc_id)
        receipt=await self.mutations.write(target=target,kind=kind,document=document,actor_type=actor_type,
                                          actor_id=user_id,source_entry=source_entry)
        if receipt['source_result'] == 'confirmed':
            record_source_observation(previous)
        return MemoryWriteResult(doc_id,receipt)


async def get_memory_writer(*, session_factory=None, expected_context=None):
    """Resolve once at execution start; missing activation/config never falls back."""
    environment=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    if not environment:
        raise MemoryControlError(20126,'runtime_environment_missing')
    if session_factory is None:
        from backend.database import async_session_maker
        session_factory=async_session_maker
    from backend.services.memory_effective_config import resolve_active_memory_config
    from backend.services.memory_embedding_cache import MemoryEmbeddingCache
    from backend.utils.memory_vector_client import MemoryVectorClient
    async with session_factory() as db:
        config=await resolve_active_memory_config(db,environment)
    mutations=MemoryMutationService(session_factory,MemoryVectorClient(config.providers['dashvector']),environment,config.encoder_version)
    writer=MemoryBusinessWriter(session_factory,mutations,config,MemoryEmbeddingCache(config.providers['embedding']).get_embedding)
    await writer.validate_context(expected_context)
    return writer
