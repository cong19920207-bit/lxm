# -*- coding: utf-8 -*-
# 火山引擎豆包 LLM 调用客户端，支持流式输出、重试

import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx

from backend.config import (
    get_llm_timeout_seconds,
    get_volc_api_key,
    get_volc_endpoint,
    get_volc_model,
)

logger = logging.getLogger(__name__)

# 超时与重试配置（流式等未单独传参时使用 get_llm_timeout_seconds()）
LLM_MAX_RETRIES = 2
LLM_RETRY_BASE_DELAY = 1.0  # 指数退避基准：1s, 2s


class LLMClient:
    """火山引擎豆包 LLM 异步客户端"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=get_llm_timeout_seconds())
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_volc_api_key()}",
        }

    def _build_body(self, prompt: str, stream: bool = True) -> dict:
        return {
            "model": get_volc_model(),
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": stream,
        }

    async def chat_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        流式调用 LLM，逐块 yield 文本内容。
        自动重试2次，指数退避。
        """
        last_error: Exception | None = None

        for attempt in range(1 + LLM_MAX_RETRIES):
            if attempt > 0:
                delay = LLM_RETRY_BASE_DELAY * attempt
                logger.warning(
                    "LLM 流式调用第 %d 次重试，等待 %.1fs",
                    attempt, delay,
                )
                import asyncio
                await asyncio.sleep(delay)

            start_time = time.monotonic()
            try:
                client = await self._get_client()
                async with client.stream(
                    "POST",
                    f"{get_volc_endpoint()}/chat/completions",
                    headers=self._build_headers(),
                    json=self._build_body(prompt, stream=True),
                    timeout=get_llm_timeout_seconds(),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                logger.warning("LLM 流式数据解析失败: %s", data_str)

                elapsed = time.monotonic() - start_time
                logger.info("LLM 流式调用完成，耗时 %.2fs", elapsed)
                return  # 成功则退出重试循环

            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                elapsed = time.monotonic() - start_time
                last_error = e
                logger.error(
                    "LLM 流式调用失败 (attempt=%d, elapsed=%.2fs): %s",
                    attempt + 1, elapsed, str(e),
                )

        raise last_error or RuntimeError("LLM 流式调用失败")

    async def chat_sync(self, prompt: str, timeout_sec: float | None = None) -> str:
        """
        非流式调用 LLM，返回完整文本。
        自动重试2次，指数退避。

        Args:
            prompt: 完整 prompt
            timeout_sec: 单次请求超时（秒）；None 时使用 get_llm_timeout_seconds()（默认 45）
        """
        effective_timeout = (
            timeout_sec if timeout_sec is not None else get_llm_timeout_seconds()
        )
        last_error: Exception | None = None

        for attempt in range(1 + LLM_MAX_RETRIES):
            if attempt > 0:
                delay = LLM_RETRY_BASE_DELAY * attempt
                logger.warning(
                    "LLM 非流式调用第 %d 次重试，等待 %.1fs",
                    attempt, delay,
                )
                import asyncio
                await asyncio.sleep(delay)

            start_time = time.monotonic()
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{get_volc_endpoint()}/chat/completions",
                    headers=self._build_headers(),
                    json=self._build_body(prompt, stream=False),
                    timeout=effective_timeout,
                )
                response.raise_for_status()
                data = response.json()
                elapsed = time.monotonic() - start_time
                logger.info("LLM 非流式调用完成，耗时 %.2fs", elapsed)

                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""

            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                elapsed = time.monotonic() - start_time
                last_error = e
                logger.error(
                    "LLM 非流式调用失败 (attempt=%d, elapsed=%.2fs): %s",
                    attempt + 1, elapsed, str(e),
                )

        raise last_error or RuntimeError("LLM 非流式调用失败")


# 全局单例
llm_client = LLMClient()
