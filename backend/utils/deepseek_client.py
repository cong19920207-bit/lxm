# -*- coding: utf-8 -*-
# DeepSeek LLM 调用客户端（生活流 LLM-01~07 专用）
#
# 与火山引擎豆包 `LLMClient`（backend/utils/llm_client.py）完全独立，互不影响：
#   - 独立 API Key / Endpoint（走环境变量 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL）
#   - 每个 LLM 节点的模型版本由 admin_config 独立配置（见 deepseek_llm_service）
#
# 结构参照豆包 LLMClient（异步 httpx.AsyncClient，非流式），符合本项目全异步架构。
# 超时/重试：timeout=45s、retry=2 次、指数退避 (2s, 4s)。
# 说明：生活流 DeepSeek（V4pro）日场景等长输出实测常超 15s，统一抬到 45s；
# 与豆包 LLM_TIMEOUT 默认 45s 对齐，互不影响。
# 重试策略（STEP-002 单测要求）：4xx 立即抛错不重试；5xx / 超时 / 网络错误才重试。

import asyncio
import logging
import time

import httpx

from backend.config import get_deepseek_api_key, get_deepseek_base_url

logger = logging.getLogger(__name__)

# 超时与重试配置：retry=2 次，指数退避 2s / 4s；单次默认 45s
DEEPSEEK_MAX_RETRIES = 2
DEEPSEEK_RETRY_BASE_DELAY = 2.0  # 指数退避基准：第 1 次重试等 2s，第 2 次等 4s
DEEPSEEK_DEFAULT_TIMEOUT = 45.0


class DeepSeekError(Exception):
    """DeepSeek 调用失败（重试耗尽或不可重试的错误）"""
    pass


class DeepSeekClient:
    """DeepSeek 异步客户端（非流式）"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DEEPSEEK_DEFAULT_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_deepseek_api_key()}",
        }

    async def chat_sync(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        timeout: float = DEEPSEEK_DEFAULT_TIMEOUT,
    ) -> str:
        """
        非流式调用 DeepSeek，返回完整文本内容。

        Args:
            messages: OpenAI 兼容消息数组，如 [{"role": "system", ...}, {"role": "user", ...}]
            model: 模型名称（由上层 deepseek_llm_service 按节点从 admin_config 读取后传入）
            temperature: 采样温度
            timeout: 单次请求超时（秒），默认 45

        Returns:
            LLM 输出的 content 字符串

        Raises:
            DeepSeekError: 4xx 不可重试错误立即抛出；5xx/超时/网络错误重试耗尽后抛出
        """
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        last_error: Exception | None = None

        for attempt in range(1 + DEEPSEEK_MAX_RETRIES):
            if attempt > 0:
                delay = DEEPSEEK_RETRY_BASE_DELAY * attempt  # 2s, 4s
                logger.warning("DeepSeek 调用第 %d 次重试，等待 %.1fs", attempt, delay)
                await asyncio.sleep(delay)

            start_time = time.monotonic()
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{get_deepseek_base_url()}/chat/completions",
                    headers=self._build_headers(),
                    json=body,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                elapsed = time.monotonic() - start_time
                logger.info("DeepSeek 调用完成，model=%s 耗时 %.2fs", model, elapsed)

                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "") or ""
                return ""

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # 4xx 客户端错误：立即抛出，不重试
                if 400 <= status < 500:
                    logger.error("DeepSeek 调用 4xx 不重试 (status=%d): %s", status, str(e))
                    raise DeepSeekError(f"DeepSeek HTTP {status}: {e}") from e
                # 5xx 服务端错误：可重试
                last_error = e
                logger.error(
                    "DeepSeek 调用 5xx (attempt=%d, status=%d): %s",
                    attempt + 1, status, str(e),
                )
            except (httpx.RequestError, httpx.TimeoutException) as e:
                # 网络错误 / 超时：可重试
                last_error = e
                logger.error(
                    "DeepSeek 调用失败 (attempt=%d): %s", attempt + 1, str(e)
                )

        raise DeepSeekError(f"DeepSeek 调用重试耗尽: {last_error}") from last_error


# 全局单例
deepseek_client = DeepSeekClient()
