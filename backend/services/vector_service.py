# -*- coding: utf-8 -*-
# 向量检索服务：封装 DashVector 操作，供 MemoryService 调用

import logging

from backend.utils.dashvector_client import dashvector_client
from backend.services.memory_business_writer import get_memory_writer

logger = logging.getLogger(__name__)


def source_snapshot(identity):
    if identity is None:return None
    return tuple(getattr(identity,k) for k in ('id','generation','body_hash','current_operation_id',
        'inflight_operation_id','source_state','target_epoch','owner_user_id','memory_type'))


class VectorService:
    """向量检索服务：对 DashVectorClient 的业务层封装"""

    async def upsert(
        self,
        memory_id: int,
        embedding: list[float],
        metadata: dict,
        memory_type: str,
        *, writer=None,
    ) -> str:
        """
        写入向量到 DashVector。

        Args:
            memory_id: 记忆 ID（用于生成 dashvector_id）
            embedding: 向量
            metadata: 元数据，包含 user_id / content / importance_score / created_at
            memory_type: 向量类型（R-L1L3-08 四类常量之一）

        Returns:
            dashvector_id（格式 mem_{memory_id}）
        """
        dashvector_id = f"mem_{memory_id}"
        fields = {
            "user_id": metadata.get("user_id"),
            "content": metadata.get("content", ""),
            "importance_score": metadata.get("importance_score", 0),
            "created_at": metadata.get("created_at", ""),
        }

        writer = writer or await get_memory_writer()
        result = await writer.upsert(memory_type=memory_type, user_id=metadata.get('user_id'), source='text',
                                     doc_id=dashvector_id, fields=fields, vector=embedding)
        if result.receipt['source_result'] == 'failed':
            raise RuntimeError('memory_vector_write_failed')
        return result

    async def search(
        self,
        query_embedding: list[float],
        memory_type: str,
        user_id: int | None = None,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """
        按类型与可选用户 ID 过滤检索，返回相似度 >= threshold 的 Top K 结果。

        Args:
            query_embedding: 查询向量
            memory_type: 向量类型（R-L1L3-08 四类常量之一）
            user_id: 用户 ID（可选，有值时追加 user_id 过滤）
            top_k: 返回 Top K 条结果
            threshold: 相似度阈值

        Returns:
            [{"id": str, "score": float, "content": str, "fields": dict}, ...]
        """
        return await dashvector_client.search(
            vector=query_embedding,
            memory_type=memory_type,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        )

    async def delete(self, dashvector_id: str, *, user_id: int, writer=None, expected_source, sql_digest):
        """Original writer/epoch tombstone; never a legacy physical DELETE.

        The durable original delete intent also repairs a lost SQL soft-delete
        commit. Unknown source results remain recoverable by this same identity.
        """
        from sqlalchemy import select
        from backend.models.memory_control import MemoryIdentity,MemoryOperation
        from backend.services.memory_mutation_service import MutationTarget
        from backend.services.memory_runtime_service import MemoryControlError
        writer=writer or await get_memory_writer()
        await writer.validate_context()
        target=MutationTarget(writer.partition,dashvector_id,'user',user_id,
            writer.config.target_epoch,bytes.fromhex(writer.config.target_fingerprint))
        async with writer.mutations._session() as db:
            await writer.mutations._fence(db,target.target_epoch,target.target_fingerprint)
            identity=await db.scalar(select(MemoryIdentity).where(MemoryIdentity.target_fingerprint==target.target_fingerprint,
                MemoryIdentity.partition_name==target.partition_name,MemoryIdentity.doc_id==dashvector_id))
            if source_snapshot(identity)!=expected_source:
                raise MemoryControlError(20127,'legacy_delete_source_changed')
            # No source writer can dispatch without this durable identity.
            # A SQL-only row (embedding/preparation never reached) needs no write.
            if identity is None:return None
            if identity.memory_type!='user' or identity.owner_user_id!=user_id:
                raise MemoryControlError(20125,'memory_source_unavailable')
            generation=identity.generation
            prior_id=identity.inflight_operation_id or (identity.current_operation_id if identity.source_state=='deleted' else None)
            prior=await db.get(MemoryOperation,prior_id) if prior_id else None
            if prior_id and (not prior or prior.operation_kind!='delete' or prior.owner_actor_type!='text'
                    or prior.owner_actor_id!=user_id or prior.target_epoch!=target.target_epoch
                    or (prior.receipt_summary or {}).get('source_entry')!='legacy-memory-delete'
                    or (prior.receipt_summary or {}).get('legacy_sql_digest')!=sql_digest):
                raise MemoryControlError(20128,'memory_source_unverified')
        if prior:
            if prior.dispatch_state=='prepared':receipt=await writer.mutations.dispatch(prior.operation_id,actor_type='text',actor_id=user_id)
            elif prior.source_result in {'pending','unknown'}:receipt=await writer.mutations.reconcile(prior.operation_id,actor_type='text',actor_id=user_id)
            else:receipt=writer.mutations._receipt(prior)
        else:
            receipt=await writer.mutations.write(target=target,kind='delete',actor_type='text',actor_id=user_id,
                document={'id':dashvector_id,'vector':[1.0]+[0.0]*1023,'fields':{'type':'user','user_id':user_id,'content':''}},
                source_entry='legacy-memory-delete',expected_generation=generation,receipt_extra={'legacy_sql_digest':sql_digest})
        if receipt['source_result']!='confirmed':
            error=MemoryControlError(20128,'legacy_delete_unverified');error.receipt=receipt;raise error
        return receipt


# 全局单例
vector_service = VectorService()
