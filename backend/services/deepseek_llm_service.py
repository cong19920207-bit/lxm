# -*- coding: utf-8 -*-
# 生活流 DeepSeek LLM 调用服务：按节点读取 admin_config 模型版本 + Redis 统计写入
#
# 与豆包对话主链 llm_service 完全独立；LLM-01~07 各节点模型版本可在后台独立切换。

import asyncio
import datetime
import logging
import time

from backend.constants import DEEPSEEK_DEFAULT_MODEL, DEEPSEEK_NODE_MODEL_CONFIG_KEYS
from backend.redis_client import get_redis
from backend.services.admin_config_service import admin_config_service
from backend.utils.deepseek_client import DeepSeekError, deepseek_client

logger = logging.getLogger(__name__)


class DeepSeekLLMService:
    """生活流 LLM 节点调用服务（llm_01 ~ llm_07）"""

    async def call_llm(
        self,
        node_key: str,
        messages: list[dict],
        temperature: float = 0.7,
        timeout: float | None = None,
    ) -> str:
        """
        调用指定生活流 LLM 节点。

        Args:
            node_key: 节点标识，取值 "llm_01" ~ "llm_07"
            messages: OpenAI 兼容消息数组
            temperature: 采样温度
            timeout: 单次调用超时（秒）；None 时使用客户端默认超时。
                     部分节点（如 LLM-03 要求 45s）按需显式传入。

        Returns:
            LLM 输出 content 字符串

        Raises:
            ValueError: node_key 非法
            DeepSeekError: DeepSeek 调用失败（由客户端抛出）
        """
        if node_key not in DEEPSEEK_NODE_MODEL_CONFIG_KEYS:
            raise ValueError(f"非法的 DeepSeek 节点：{node_key}")

        # 按节点从 admin_config 读取当前生效模型版本（走 Redis 缓存 TTL=3600s）
        config_key = DEEPSEEK_NODE_MODEL_CONFIG_KEYS[node_key]
        model = await admin_config_service.get_active_config(config_key)
        if not model or not isinstance(model, str):
            model = DEEPSEEK_DEFAULT_MODEL

        chat_kwargs = {"model": model, "temperature": temperature}
        if timeout is not None:
            chat_kwargs["timeout"] = timeout

        start_time = time.time()
        try:
            content = await deepseek_client.chat_sync(messages, **chat_kwargs)
            response_ms = int((time.time() - start_time) * 1000)
            asyncio.create_task(self._record_stats(response_ms, True))
            return content
        except Exception as e:
            response_ms = int((time.time() - start_time) * 1000)
            asyncio.create_task(self._record_stats(response_ms, False))
            logger.error("DeepSeek call_llm 失败 node=%s: %s", node_key, str(e))
            raise

    async def _record_stats(self, response_ms: int, success: bool) -> None:
        """异步写入 LLM 调用统计到 Redis（复用 .cursorrules llm_stats 惯例）"""
        today = datetime.date.today().strftime("%Y%m%d")
        try:
            r = await get_redis()
            await r.lpush("llm_response_times", response_ms)
            await r.ltrim("llm_response_times", 0, 999)
            await r.expire("llm_response_times", 172800)
            await r.hincrby(f"llm_stats:{today}", "total", 1)
            if success:
                await r.hincrby(f"llm_stats:{today}", "success", 1)
            else:
                await r.hincrby(f"llm_stats:{today}", "failed", 1)
            await r.expire(f"llm_stats:{today}", 172800)
        except Exception as e:
            logger.error("DeepSeek stats write failed: %s", e)


# 全局单例
deepseek_llm_service = DeepSeekLLMService()
