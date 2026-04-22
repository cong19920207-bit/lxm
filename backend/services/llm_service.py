# -*- coding: utf-8 -*-
# 核心 LLM 调用服务：流式对话、结构化解析、兜底回复

import asyncio
import datetime
import json
import logging
import re
import time
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.admin_config import AdminConfig
from backend.redis_client import get_redis
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# JSON 提取正则：匹配第一个 { ... } 块（支持嵌套）
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

# 解析失败时的默认回复
DEFAULT_FALLBACK = {
    "emotion": {"label": "平静", "confidence": 1.0},
    "reply": "抱歉，我现在有点走神，你刚才说什么？",
}


class LLMService:
    """核心 LLM 调用服务"""

    async def chat(self, prompt: str, stream: bool = True) -> AsyncGenerator[str, None]:
        """
        调用 LLM 进行对话。

        Args:
            prompt: 完整的 Prompt 文本
            stream: 是否流式输出

        Yields:
            逐块文本内容
        """
        if stream:
            async for chunk in llm_client.chat_stream(prompt):
                yield chunk
        else:
            result = await llm_client.chat_sync(prompt)
            yield result

    async def chat_with_parse(
        self,
        prompt: str,
        is_test: bool = False,
        timeout_sec: float | None = None,
    ) -> dict:
        """
        非流式调用 LLM，解析结构化 JSON 输出。

        期望 LLM 返回：{"emotion": {"label": "xxx", "confidence": 0.9}, "reply": "xxx"}

        解析失败时返回默认值。

        Args:
            prompt: 完整的 Prompt 文本
            is_test: 后台测试调用时为True，跳过统计写入
            timeout_sec: 单次 LLM HTTP 超时（秒）。None 表示使用通用超时（默认 15s）。
                H5 对话主链路应传入 config.get_llm_timeout_chat_seconds()（默认 45s）。

        Returns:
            {"emotion": {"label": str, "confidence": float}, "reply": str}
        """
        start_time = time.time()
        try:
            raw_text = await llm_client.chat_sync(prompt, timeout_sec=timeout_sec)
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, True))
            return self._parse_llm_response(raw_text)
        except Exception as e:
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, False))
            logger.error("LLM chat_with_parse 调用失败: %s", str(e))
            return dict(DEFAULT_FALLBACK)

    async def generate_with_fallback(
        self,
        prompt: str,
        fallback_reply: str,
        db: AsyncSession | None = None,
    ) -> dict:
        """
        带兜底的 LLM 调用：连续2次失败后返回兜底回复。

        兜底回复优先从 admin_config 表读取（key=fallback_reply），
        读取失败则使用传入的 fallback_reply 参数。

        Args:
            prompt: 完整的 Prompt 文本
            fallback_reply: 外部传入的兜底回复文本
            db: 数据库会话（用于读取 admin_config）

        Returns:
            {"emotion": {"label": str, "confidence": float}, "reply": str}
        """
        for attempt in range(2):
            try:
                raw_text = await llm_client.chat_sync(prompt)
                parsed = self._parse_llm_response(raw_text)
                if parsed["reply"]:
                    return parsed
                logger.warning("LLM 返回空回复 (attempt=%d)", attempt + 1)
            except Exception as e:
                logger.error(
                    "LLM generate_with_fallback 失败 (attempt=%d): %s",
                    attempt + 1, str(e),
                )

        # 两次都失败，读取数据库兜底回复
        db_fallback = await self._get_fallback_from_db(db)
        actual_fallback = db_fallback or fallback_reply

        logger.warning("LLM 连续2次失败，使用兜底回复")
        return {
            "emotion": {"label": "平静", "confidence": 1.0},
            "reply": actual_fallback,
        }

    def _parse_llm_response(self, raw_text: str) -> dict:
        """
        从 LLM 原始输出中提取 JSON 并解析 emotion + reply。

        Args:
            raw_text: LLM 原始返回文本

        Returns:
            解析后的字典，解析失败返回默认值
        """
        if not raw_text:
            logger.warning("LLM 返回空文本")
            return dict(DEFAULT_FALLBACK)

        # 尝试用正则提取 JSON 块
        match = _JSON_PATTERN.search(raw_text)
        if match:
            try:
                data = json.loads(match.group())
                emotion = data.get("emotion", {})
                reply = data.get("reply", "")

                if not isinstance(emotion, dict):
                    emotion = {"label": "平静", "confidence": 1.0}

                label = emotion.get("label", "平静")
                confidence = emotion.get("confidence", 1.0)

                # 校验 confidence 范围
                try:
                    confidence = float(confidence)
                    confidence = max(0.0, min(1.0, confidence))
                except (TypeError, ValueError):
                    confidence = 1.0

                return {
                    "emotion": {"label": label, "confidence": confidence},
                    "reply": reply or DEFAULT_FALLBACK["reply"],
                }
            except json.JSONDecodeError:
                logger.warning("LLM 返回 JSON 解析失败: %s", match.group()[:200])

        # 正则也没匹配到，整体尝试 json.loads
        try:
            data = json.loads(raw_text.strip())
            emotion = data.get("emotion", {})
            reply = data.get("reply", "")
            if reply:
                label = emotion.get("label", "平静") if isinstance(emotion, dict) else "平静"
                confidence = emotion.get("confidence", 1.0) if isinstance(emotion, dict) else 1.0
                return {
                    "emotion": {"label": label, "confidence": float(confidence)},
                    "reply": reply,
                }
        except (json.JSONDecodeError, ValueError):
            pass

        logger.warning("LLM 返回无法解析为 JSON: %s", raw_text[:200])
        return dict(DEFAULT_FALLBACK)

    def _parse_llm_response_strict(self, raw_text: str) -> dict | None:
        """
        与 _parse_llm_response 相同解析规则，但失败时返回 None（不返回走神默认值），供 H5 对话闭环使用。
        """
        if not raw_text or not raw_text.strip():
            return None

        match = _JSON_PATTERN.search(raw_text)
        if match:
            try:
                data = json.loads(match.group())
                emotion = data.get("emotion", {})
                reply = data.get("reply", "")

                if not isinstance(emotion, dict):
                    emotion = {"label": "平静", "confidence": 1.0}

                label = emotion.get("label", "平静")
                confidence = emotion.get("confidence", 1.0)

                try:
                    confidence = float(confidence)
                    confidence = max(0.0, min(1.0, confidence))
                except (TypeError, ValueError):
                    confidence = 1.0

                if not reply or not str(reply).strip():
                    return None

                return {
                    "emotion": {"label": label, "confidence": confidence},
                    "reply": str(reply).strip(),
                }
            except json.JSONDecodeError:
                return None

        try:
            data = json.loads(raw_text.strip())
            emotion = data.get("emotion", {})
            reply = data.get("reply", "")
            if not reply or not str(reply).strip():
                return None
            label = emotion.get("label", "平静") if isinstance(emotion, dict) else "平静"
            confidence = emotion.get("confidence", 1.0) if isinstance(emotion, dict) else 1.0
            return {
                "emotion": {"label": label, "confidence": float(confidence)},
                "reply": str(reply).strip(),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    async def chat_with_parse_strict(
        self,
        prompt: str,
        is_test: bool = False,
        timeout_sec: float | None = None,
    ) -> dict:
        """
        H5 对话打包调度：HTTP 失败或无法解析为合法 JSON 时抛异常，不返回走神占位字典。
        """
        start_time = time.time()
        try:
            raw_text = await llm_client.chat_sync(prompt, timeout_sec=timeout_sec)
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, True))
            parsed = self._parse_llm_response_strict(raw_text)
            if parsed is None:
                if not is_test:
                    asyncio.create_task(self._record_stats(response_ms, False))
                raise ValueError("LLM 输出无法解析为结构化 emotion+reply")
            return parsed
        except ValueError:
            raise
        except Exception as e:
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, False))
            logger.error("LLM chat_with_parse_strict 调用失败: %s", str(e))
            raise

    async def _record_stats(self, response_ms: int, success: bool):
        """异步写入 LLM 调用统计数据到 Redis"""
        today = datetime.date.today().strftime("%Y%m%d")
        try:
            r = await get_redis()
            await r.lpush("llm_response_times", response_ms)
            await r.ltrim("llm_response_times", 0, 999)
            await r.expire("llm_response_times", 172800)
            await r.hincrby(f"llm_stats:{today}", "total", 1)
            if success:
                await r.hincrby(f"llm_stats:{today}", "success", 1)
            await r.expire(f"llm_stats:{today}", 172800)
        except Exception as e:
            logger.error("LLM stats write failed: %s", e)

    async def _get_fallback_from_db(self, db: AsyncSession | None) -> str | None:
        """从 admin_config 表读取兜底回复"""
        if db is None:
            return None
        try:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == "fallback_reply",
                AdminConfig.is_active == True,  # noqa: E712
            )
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()
            if config and config.config_value:
                return config.config_value
        except Exception:
            logger.warning("读取 admin_config fallback_reply 失败", exc_info=True)
        return None


# 全局单例
llm_service = LLMService()
