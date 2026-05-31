# -*- coding: utf-8 -*-
# 阿里云 DashVector 向量检索客户端

import logging
import time

import httpx

from backend.config import get_dashvector_api_key, get_dashvector_collection, get_dashvector_endpoint
from backend.constants import VALID_MEMORY_TYPES

logger = logging.getLogger(__name__)

DASHVECTOR_TIMEOUT = 10.0  # 秒
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.7  # 相似度阈值


def build_filter(
    memory_type: str,
    user_id: int | None,
    candidate_keys: list[str],
) -> str:
    """
    统一构造 DashVector filter 字符串（C9/C27）。

    - type 与 key_l2 一律使用双引号（C9 已验证 DashVector 合法 C32）
    - 有 user_id 时追加 user_id 数值过滤
    - candidate_keys 每项按 "-" 拆分，长度 ≥2 时取前两段拼成二级 Key
      （如 "经历-出行-自驾" → "经历-出行"）入 key_l2 IN 集合；
      长度 <2 的非法项（如单层 "偏好"）直接丢弃，不报错
    - key_l2 值内的双引号转义为 \"
    - 去重保序：输出顺序与 candidate_keys 出现顺序一致，便于稳定测试

    Returns:
        如 'type = "user" AND user_id = 1 AND key_l2 IN ("经历-出行", "偏好-饮食")'
    """
    base = f'type = "{memory_type}"'
    if user_id is not None:
        base += f" AND user_id = {user_id}"
    if candidate_keys:
        l2_keys: list[str] = []
        for k in candidate_keys:
            parts = k.split("-")
            if len(parts) >= 2:
                # 取前两段拼成二级 Key，并转义值中的双引号（C9）
                l2 = (parts[0] + "-" + parts[1]).replace('"', '\\"')
                if l2 not in l2_keys:
                    l2_keys.append(l2)
        if l2_keys:
            quoted = ", ".join(f'"{v}"' for v in l2_keys)
            base += f" AND key_l2 IN ({quoted})"
    return base


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
        memory_type: str,
        user_id: int | None = None,
        top_k: int = DEFAULT_TOP_K,
        threshold: float = SIMILARITY_THRESHOLD,
        candidate_keys: list[str] = [],
    ) -> list[dict]:
        """
        向量检索：查找与输入向量最相似的记忆。

        Args:
            vector: 查询向量
            memory_type: 向量类型（R-L1L3-08 四类常量之一）
            user_id: 用户 ID（可选，有值时追加 user_id 过滤）
            top_k: 返回 Top K 条结果
            threshold: 相似度阈值，低于此值的结果被过滤
            candidate_keys: 二级/三级 Key 前缀，用于推导 key_l2 IN（C33/C34）；
                默认 [] → 老调用方零改动，filter 仅含 type(+user_id)

        Returns:
            [{"id": str, "score": float, "content": str, "fields": dict}, ...]
        """
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(f"非法的 memory_type: {memory_type}，合法值: {VALID_MEMORY_TYPES}")

        # 统一走 build_filter（双引号，C9/C27）
        filter_str = build_filter(memory_type, user_id, candidate_keys)

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
                    "filter": filter_str,
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
        memory_type: str,
    ) -> bool:
        """
        插入或更新向量文档。

        Args:
            doc_id: 文档 ID
            vector: 向量
            fields: 附加字段（content, user_id, importance_score 等）
            memory_type: 向量类型（R-L1L3-08 四类常量之一）

        Returns:
            是否成功
        """
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(f"非法的 memory_type: {memory_type}，合法值: {VALID_MEMORY_TYPES}")

        merged_fields = {**fields, "type": memory_type}
        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()

        try:
            client = await self._get_client()
            response = await client.post(
                f"{endpoint}/v1/collections/{collection}/docs/upsert",
                headers=self._build_headers(),
                json={
                    "docs": [{
                        "id": doc_id,
                        "vector": vector,
                        "fields": merged_fields,
                    }],
                },
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            message = str(data.get("message", ""))
            message_lower = message.lower()
            if "failed operation" in message_lower or "is invalid" in message_lower:
                logger.error(
                    "DashVector upsert 业务失败: doc_id=%s, message=%s",
                    doc_id, message[:300],
                )
                return False
            logger.info("DashVector upsert 成功: doc_id=%s, type=%s", doc_id, memory_type)
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

    async def list_by_filter(self, filter_str: str, top_k: int = 100) -> list[dict]:
        """
        按 filter 条件列出文档（不传 vector，仅条件过滤）。

        Returns:
            [{"id": str, "content": str, "fields": dict}, ...]
        """
        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()

        try:
            client = await self._get_client()
            response = await client.post(
                f"{endpoint}/v1/collections/{collection}/query",
                headers=self._build_headers(),
                json={
                    "filter": filter_str,
                    "topk": top_k,
                    "include_vector": False,
                },
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("output", []):
                fields = item.get("fields", {}) or {}
                results.append({
                    "id": item.get("id", ""),
                    "content": fields.get("content", ""),
                    "fields": fields,
                })
            logger.info(
                "DashVector list_by_filter 完成: filter=%s, count=%d",
                filter_str, len(results),
            )
            return results
        except Exception as e:
            logger.error("DashVector list_by_filter 失败: %s", str(e))
            return []

    async def fetch_by_ids(self, doc_ids: list[str]) -> dict[str, dict]:
        """
        按 ID 批量获取文档。

        Returns:
            {doc_id: {"id", "content", "fields"}}，不存在的 id 不包含在结果中
        """
        if not doc_ids:
            return {}

        endpoint = get_dashvector_endpoint()
        collection = get_dashvector_collection()
        ids_param = ",".join(doc_ids)

        try:
            client = await self._get_client()
            response = await client.get(
                f"{endpoint}/v1/collections/{collection}/docs",
                headers=self._build_headers(),
                params={"ids": ids_param},
                timeout=DASHVECTOR_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            output = data.get("output", {}) or {}
            found: dict[str, dict] = {}
            for doc_id, item in output.items():
                if not item or not isinstance(item, dict):
                    continue
                fields = item.get("fields", {}) or {}
                content = fields.get("content", "")
                if not content:
                    continue
                found[doc_id] = {
                    "id": item.get("id", doc_id),
                    "content": content,
                    "fields": fields,
                }
            return found
        except Exception as e:
            logger.error("DashVector fetch_by_ids 失败: %s", str(e))
            return {}


# 全局单例
dashvector_client = DashVectorClient()
