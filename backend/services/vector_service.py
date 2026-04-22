# -*- coding: utf-8 -*-
# 向量检索服务：封装 DashVector 操作，供 MemoryService 调用

import logging

from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)


class VectorService:
    """向量检索服务：对 DashVectorClient 的业务层封装"""

    async def upsert(
        self,
        memory_id: int,
        embedding: list[float],
        metadata: dict,
    ) -> str:
        """
        写入向量到 DashVector。

        Args:
            memory_id: 记忆 ID（用于生成 dashvector_id）
            embedding: 向量
            metadata: 元数据，包含 user_id / content / importance_score / created_at

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

        success = await dashvector_client.upsert(
            doc_id=dashvector_id,
            vector=embedding,
            fields=fields,
        )

        if not success:
            logger.error("DashVector upsert 失败: memory_id=%d", memory_id)
            raise RuntimeError(f"DashVector upsert 失败: memory_id={memory_id}")

        return dashvector_id

    async def search(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """
        按用户 ID 过滤检索，返回相似度 >= threshold 的 Top K 结果。

        Returns:
            [{"id": str, "score": float, "content": str, "fields": dict}, ...]
        """
        return await dashvector_client.search(
            vector=query_embedding,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        )

    async def delete(self, dashvector_id: str) -> None:
        """删除指定向量"""
        success = await dashvector_client.delete(doc_ids=[dashvector_id])
        if not success:
            logger.warning("DashVector 删除失败: %s", dashvector_id)


# 全局单例
vector_service = VectorService()
