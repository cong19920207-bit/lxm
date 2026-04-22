# -*- coding: utf-8 -*-
# Redis 异步客户端，用于缓存和热数据

import logging

import redis.asyncio as aioredis

from backend.config import get_redis_url

logger = logging.getLogger(__name__)

_redis_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    """初始化 Redis 异步连接池（应用启动时调用）"""
    global _redis_pool
    if _redis_pool is not None:
        return
    _redis_pool = aioredis.from_url(
        get_redis_url(),
        decode_responses=True,
        max_connections=20,
    )
    logger.info("Redis 连接池已初始化")


async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端实例，未初始化时自动初始化"""
    global _redis_pool
    if _redis_pool is None:
        await init_redis()
    return _redis_pool


async def close_redis() -> None:
    """关闭 Redis 连接池（应用关闭时调用）"""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis 连接池已关闭")
