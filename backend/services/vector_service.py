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
        memory_type: str,
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

        success = await dashvector_client.upsert(
            doc_id=dashvector_id,
            vector=embedding,
            fields=fields,
            memory_type=memory_type,
        )

        if not success:
            logger.error("DashVector upsert 失败: memory_id=%d", memory_id)
            raise RuntimeError(f"DashVector upsert 失败: memory_id={memory_id}")

        return dashvector_id

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

    async def delete(self, dashvector_id: str) -> None:
        """删除指定向量"""
        success = await dashvector_client.delete(doc_ids=[dashvector_id])
        if not success:
            logger.warning("DashVector 删除失败: %s", dashvector_id)


# 全局单例
vector_service = VectorService()
