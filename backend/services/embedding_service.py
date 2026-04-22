# -*- coding: utf-8 -*-
# Embedding 服务：封装阿里云 text-embedding-v3，支持 Redis 缓存和批量调用

import hashlib
import json
import logging
import time

import httpx

from backend.config import get_aliyun_api_key, get_embedding_endpoint, get_embedding_model
from backend.redis_client import get_redis

logger = logging.getLogger(__name__)

EMBEDDING_CACHE_TTL = 86400  # Redis 缓存 24 小时
EMBEDDING_TIMEOUT = 10.0  # API 超时（秒）
MAX_BATCH_SIZE = 25  # 阿里云单次最多 25 条


class EmbeddingService:
    """Embedding 服务：Redis 缓存 + 批量调用阿里云 text-embedding-v3"""

    @staticmethod
    def _cache_key(text: str) -> str:
        """生成 Redis 缓存 key：emb:{md5(text)}"""
        md5 = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"emb:{md5}"

    async def get_embedding(self, text: str) -> list[float]:
        """
        获取单条文本的 embedding 向量。
        优先读 Redis 缓存，未命中则调用阿里云 API 并回写缓存。
        """
        cache_key = self._cache_key(text)

        # 读缓存
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Embedding 缓存命中: %s", cache_key)
                return json.loads(cached)
        except Exception as e:
            logger.warning("Redis 缓存读取失败: %s", str(e))

        # 调用 API
        embeddings = await self._call_embedding_api([text])
        if not embeddings:
            return []

        result = embeddings[0]

        # 写缓存
        try:
            redis = await get_redis()
            await redis.set(cache_key, json.dumps(result), ex=EMBEDDING_CACHE_TTL)
        except Exception as e:
            logger.warning("Redis 缓存写入失败: %s", str(e))

        return result

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取 embedding 向量（阿里云支持最多 25 条/次）。
        先批量检查 Redis 缓存，仅对未命中的文本调用 API。
        """
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        # 批量检查缓存
        try:
            redis = await get_redis()
            cache_keys = [self._cache_key(t) for t in texts]
            cached_values = await redis.mget(cache_keys)
            for i, cached in enumerate(cached_values):
                if cached:
                    results[i] = json.loads(cached)
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(texts[i])
        except Exception as e:
            logger.warning("Redis 批量缓存读取失败: %s", str(e))
            uncached_indices = list(range(len(texts)))
            uncached_texts = list(texts)

        if not uncached_texts:
            return [r if r is not None else [] for r in results]

        # 分批调用 API（每批最多 25 条）
        all_embeddings: list[list[float]] = []
        for start in range(0, len(uncached_texts), MAX_BATCH_SIZE):
            batch = uncached_texts[start : start + MAX_BATCH_SIZE]
            batch_result = await self._call_embedding_api(batch)
            all_embeddings.extend(batch_result)

        # 填充结果并批量写入缓存
        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            for j, idx in enumerate(uncached_indices):
                if j < len(all_embeddings):
                    results[idx] = all_embeddings[j]
                    pipe.set(
                        self._cache_key(texts[idx]),
                        json.dumps(all_embeddings[j]),
                        ex=EMBEDDING_CACHE_TTL,
                    )
            await pipe.execute()
        except Exception as e:
            logger.warning("Redis 批量缓存写入失败: %s", str(e))
            for j, idx in enumerate(uncached_indices):
                if j < len(all_embeddings):
                    results[idx] = all_embeddings[j]

        return [r if r is not None else [] for r in results]

    async def _call_embedding_api(self, texts: list[str]) -> list[list[float]]:
        """调用阿里云 text-embedding-v3 API"""
        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT) as client:
                response = await client.post(
                    get_embedding_endpoint(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {get_aliyun_api_key()}",
                    },
                    json={
                        "model": get_embedding_model(),
                        "input": {"texts": texts},
                        "parameters": {"text_type": "query"},
                    },
                )
                response.raise_for_status()
                data = response.json()
                elapsed = time.monotonic() - start_time
                logger.info(
                    "Embedding API 调用完成，%d 条文本，耗时 %.2fs", len(texts), elapsed
                )

                output = data.get("output", {})
                embeddings_data = output.get("embeddings", [])
                # 按 text_index 排序确保顺序与输入一致
                embeddings_data.sort(key=lambda x: x.get("text_index", 0))
                return [item.get("embedding", []) for item in embeddings_data]

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Embedding API 调用失败 (elapsed=%.2fs): %s", elapsed, str(e))
            raise


# 全局单例
embedding_service = EmbeddingService()
