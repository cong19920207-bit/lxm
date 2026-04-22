# -*- coding: utf-8 -*-
# 阿里云 text-embedding-v3 向量化客户端

import logging
import time

import httpx

from backend.config import get_aliyun_api_key, get_embedding_endpoint, get_embedding_model

logger = logging.getLogger(__name__)

EMBEDDING_TIMEOUT = 10.0  # 秒


class EmbeddingClient:
    """阿里云 text-embedding-v3 异步客户端"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> list[float]:
        """
        将文本转换为向量。

        Args:
            text: 待向量化的文本

        Returns:
            浮点数向量列表
        """
        start_time = time.monotonic()
        try:
            client = await self._get_client()
            response = await client.post(
                get_embedding_endpoint(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {get_aliyun_api_key()}",
                },
                json={
                    "model": get_embedding_model(),
                    "input": {"texts": [text]},
                    "parameters": {"text_type": "query"},
                },
                timeout=EMBEDDING_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            elapsed = time.monotonic() - start_time
            logger.info("Embedding 调用完成，耗时 %.2fs", elapsed)

            output = data.get("output", {})
            embeddings = output.get("embeddings", [])
            if embeddings:
                return embeddings[0].get("embedding", [])

            logger.warning("Embedding 返回为空: %s", data)
            return []

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Embedding 调用失败 (elapsed=%.2fs): %s", elapsed, str(e))
            raise


# 全局单例
embedding_client = EmbeddingClient()
