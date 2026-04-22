# -*- coding: utf-8 -*-
# 阿里云 DashVector 向量检索客户端

import logging
import time

import httpx

from backend.config import get_dashvector_api_key, get_dashvector_collection, get_dashvector_endpoint

logger = logging.getLogger(__name__)

DASHVECTOR_TIMEOUT = 10.0  # 秒
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.7  # 相似度阈值


class DashVectorClient:
    """阿里云 DashVector 异步客户端"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DASHVECTOR_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "dashvector-auth-token": get_dashvector_api_key(),
        }

    async def search(
        self,
        vector: list[float],
        user_id: int,
        top_k: int = DEFAULT_TOP_K,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> list[dict]:
        """
        向量检索：查找与输入向量最相似的记忆。

        Args:
            vector: 查询向量
            user_id: 用户 ID（用于过滤）
            top_k: 返回 Top K 条结果
            threshold: 相似度阈值，低于此值的结果被过滤

        Returns:
            [{"id": str, "score": float, "content": str, "fields": dict}, ...]
        """
        start_time = time.monotonic()
        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()

        try:
            client = await self._get_client()
            response = await client.post(
                f"{endpoint}/v1/collections/{collection}/query",
                headers=self._build_headers(),
                json={
                    "vector": vector,
                    "topk": top_k,
                    "filter": f"user_id = {user_id}",
                    "include_vector": False,
                },
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            elapsed = time.monotonic() - start_time
            logger.info("DashVector 检索完成，耗时 %.2fs", elapsed)

            results = []
            output = data.get("output", [])
            for item in output:
                score = item.get("score", 0.0)
                if score >= threshold:
                    results.append({
                        "id": item.get("id", ""),
                        "score": score,
                        "content": item.get("fields", {}).get("content", ""),
                        "fields": item.get("fields", {}),
                    })

            logger.info(
                "DashVector 检索结果：共 %d 条（阈值 %.2f 过滤后 %d 条）",
                len(output), threshold, len(results),
            )
            return results

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("DashVector 检索失败 (elapsed=%.2fs): %s", elapsed, str(e))
            return []

    async def upsert(
        self,
        doc_id: str,
        vector: list[float],
        fields: dict,
    ) -> bool:
        """
        插入或更新向量文档。

        Args:
            doc_id: 文档 ID
            vector: 向量
            fields: 附加字段（content, user_id, importance_score 等）

        Returns:
            是否成功
        """
        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()

        try:
            client = await self._get_client()
            response = await client.post(
                f"{endpoint}/v1/collections/{collection}/docs",
                headers=self._build_headers(),
                json={
                    "docs": [{
                        "id": doc_id,
                        "vector": vector,
                        "fields": fields,
                    }],
                },
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            logger.info("DashVector upsert 成功: doc_id=%s", doc_id)
            return True

        except Exception as e:
            logger.error("DashVector upsert 失败: doc_id=%s, error=%s", doc_id, str(e))
            return False

    async def delete(self, doc_ids: list[str]) -> bool:
        """删除指定 ID 的向量文档"""
        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()

        try:
            client = await self._get_client()
            response = await client.request(
                "DELETE",
                f"{endpoint}/v1/collections/{collection}/docs",
                headers=self._build_headers(),
                json={"ids": doc_ids},
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            logger.info("DashVector 删除成功: ids=%s", doc_ids)
            return True

        except Exception as e:
            logger.error("DashVector 删除失败: ids=%s, error=%s", doc_ids, str(e))
            return False


# 全局单例
dashvector_client = DashVectorClient()
