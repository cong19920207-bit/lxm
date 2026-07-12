# -*- coding: utf-8 -*-
# 生活流全局配置读取服务（STEP-003）
#
# 统一入口：get_life_feed_config(key, default) —— 走 admin_config_service.get_active_config，
# 命中 Redis 缓存 active_config:{key}（TTL=3600s），未命中回落 MySQL 并回写缓存。
# invalidate_life_feed_config_cache(key) —— 删除对应 Redis 缓存，使下次读取取库最新值。

import logging
from typing import Any

from backend.redis_client import get_redis
from backend.services.admin_config_service import admin_config_service

logger = logging.getLogger(__name__)


async def get_life_feed_config(key: str, default: Any = None) -> Any:
    """
    读取生活流全局配置项当前生效值。

    Args:
        key: config_key（建议使用 backend.constants.life_feed_config 中的常量）
        default: 配置不存在时的兜底返回值

    Returns:
        config_value（可 JSON 解析则为 dict/list/标量，否则原始字符串）；不存在返回 default。
    """
    value = await admin_config_service.get_active_config(key, use_cache=True)
    if value is None:
        return default
    return value


async def invalidate_life_feed_config_cache(key: str) -> None:
    """使指定配置项的 Redis 缓存失效（后台改配置后调用，令下次读取取库最新值）。"""
    try:
        redis = await get_redis()
        await redis.delete(f"active_config:{key}")
    except Exception as e:
        logger.warning("生活流配置缓存失效失败 key=%s: %s", key, e)
