# -*- coding: utf-8 -*-
# 核心 LLM 调用服务：流式对话、结构化解析、兜底回复

import asyncio
import datetime
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from typing import List

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.admin_config import AdminConfig
from backend.constants import MAX_MESSAGES_COUNT, MAX_SINGLE_MESSAGE_LENGTH
from backend.redis_client import get_redis
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# JSON 提取正则：匹配第一个 { ... } 块（支持嵌套）
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


# ============ Step5 结构化输出模型 ============


class Step5ParseError(Exception):
    """Step5 JSON 解析/校验失败异常"""
    pass


class MessageItem(BaseModel):
    """单条消息"""
    type: str
    content: str


class RelationChange(BaseModel):
    """关系变化"""
    delta: int = 0


class FutureSlot(BaseModel):
    """未来行为槽"""
    time_natural: str = "无"
    action: str = "无"


class EmotionResult(BaseModel):
    """情绪结果"""
    label: str = "平静"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            v = float(v)
            return max(0.0, min(1.0, v))
        except (TypeError, ValueError):
            return 1.0


class Step5Output(BaseModel):
    """Step5 LLM 输出的完整结构化模型（§2.7.7）"""
    inner_monologue: str = ""
    messages: List[MessageItem]
    relation_change: RelationChange = Field(default_factory=RelationChange)
    future: FutureSlot = Field(default_factory=FutureSlot)
    emotion: EmotionResult = Field(default_factory=EmotionResult)
    knowledge_expand: str = "否"

    @field_validator("knowledge_expand", mode="before")
    @classmethod
    def normalize_knowledge_expand(cls, v):
        """U1：trim 后仅精确「是」为是，其余一律「否」"""
        if isinstance(v, str) and v.strip() == "是":
            return "是"
        return "否"


def parse_step5_output(raw_json_str: str) -> Step5Output:
    """
    解析 LLM 返回的 Step5 JSON 字符串，执行严格校验。

    校验规则：
    - JSON 解析失败 → Step5ParseError
    - messages 为空数组或全部 content 为空 → Step5ParseError（U2）
    - 任一 messages[].type 非精确 "text" → Step5ParseError（CP3）
    - knowledge_expand trim 后仅「是」为是，其余按「否」（U1），不失败
    - relation_change.delta 缺失 → 默认 0（R-BND-02）
    - future 缺失 → 默认 time_natural="无", action="无"

    Raises:
        Step5ParseError: 解析或校验失败
    """
    if not raw_json_str or not raw_json_str.strip():
        raise Step5ParseError("LLM 返回空文本")

    # 尝试提取 JSON 块
    json_str = raw_json_str.strip()
    match = _JSON_PATTERN.search(json_str)
    if match:
        json_str = match.group()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        raise Step5ParseError(f"JSON 解析失败: {e}") from e

    if not isinstance(data, dict):
        raise Step5ParseError("JSON 顶层不是对象")

    # U2：messages 为空数组或全部 content trim 后为空 → 失败
    messages_raw = data.get("messages")
    if not isinstance(messages_raw, list) or len(messages_raw) == 0:
        raise Step5ParseError("messages 为空数组（U2）")

    all_content_empty = all(
        not item.get("content", "").strip()
        for item in messages_raw
        if isinstance(item, dict)
    )
    if all_content_empty:
        raise Step5ParseError("messages 每条 content trim 后均为空（U2）")

    # CP3：messages[].type 必须精确等于字面量 "text"（大小写敏感）
    for i, item in enumerate(messages_raw):
        if not isinstance(item, dict):
            raise Step5ParseError(f"messages[{i}] 不是对象")
        msg_type = item.get("type")
        if msg_type != "text":
            raise Step5ParseError(
                f"messages[{i}].type=\"{msg_type}\" 非精确 \"text\"（CP3）"
            )

    # R-BND-02：relation_change 缺失 → 填入默认
    if "relation_change" not in data or data["relation_change"] is None:
        data["relation_change"] = {"delta": 0}
    elif isinstance(data["relation_change"], dict) and "delta" not in data["relation_change"]:
        data["relation_change"]["delta"] = 0

    # future 缺失 → 填入默认
    if "future" not in data or data["future"] is None:
        data["future"] = {"time_natural": "无", "action": "无"}

    # emotion 缺失 → 填入默认
    if "emotion" not in data or data["emotion"] is None:
        data["emotion"] = {"label": "平静", "confidence": 1.0}

    try:
        result = Step5Output(**data)
    except Exception as e:
        raise Step5ParseError(f"Pydantic 校验失败: {e}") from e

    return result

def merge_messages_if_exceed(
    messages: list[MessageItem],
    max_count: int = MAX_MESSAGES_COUNT,
    max_length: int = MAX_SINGLE_MESSAGE_LENGTH,
) -> list[MessageItem]:
    """
    §2.9.1：当 messages 超过 max_count 条时，将第 max_count 条及以后
    的 content 按顺序用半角空格拼入第 max_count 条（下标 max_count-1）
    的 content 末尾。合并后若超过 max_length 则尾部截断并打日志。

    纯函数，不修改入参；返回新列表。

    Args:
        messages: Step5 / Step5.5 解析出的 MessageItem 列表
        max_count: 最大条数上限，默认 5
        max_length: 合并后单条 content 最大字符数，默认 2000

    Returns:
        合并后的 MessageItem 列表（长度 ≤ max_count）
    """
    if len(messages) <= max_count:
        return list(messages)

    merged = list(messages[:max_count])

    tail_item = merged[max_count - 1]
    accumulated = tail_item.content
    for item in messages[max_count:]:
        accumulated = accumulated + " " + item.content

    if len(accumulated) > max_length:
        logger.warning(
            "消息合并后第 %d 条超长（%d > %d），执行尾部截断",
            max_count, len(accumulated), max_length,
        )
        accumulated = accumulated[:max_length]

    merged[max_count - 1] = MessageItem(type=tail_item.type, content=accumulated)
    return merged


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
            timeout_sec: 单次 LLM HTTP 超时（秒）。None 表示使用通用超时（默认 45s，见 LLM_TIMEOUT）。
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

    async def chat_with_step5_parse(
        self,
        prompt: str,
        is_test: bool = False,
        timeout_sec: float | None = None,
    ) -> Step5Output:
        """
        H5 对话主链路：调用 LLM 后使用 Step5 解析器解析 6 字段结构化输出。

        解析失败时抛 Step5ParseError，供上层决定叹号/兜底策略。

        Args:
            prompt: 完整 Prompt 文本
            is_test: 后台测试调用时为 True，跳过统计写入
            timeout_sec: LLM HTTP 超时（秒）

        Returns:
            Step5Output 结构化数据

        Raises:
            Step5ParseError: 解析/校验失败
            Exception: LLM HTTP 调用失败
        """
        start_time = time.time()
        try:
            raw_text = await llm_client.chat_sync(prompt, timeout_sec=timeout_sec)
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, True))
            result = parse_step5_output(raw_text)
            return result
        except Step5ParseError:
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, False))
            raise
        except Exception as e:
            response_ms = int((time.time() - start_time) * 1000)
            if not is_test:
                asyncio.create_task(self._record_stats(response_ms, False))
            logger.error("LLM chat_with_step5_parse 调用失败: %s", str(e))
            raise

    async def chat_with_parse_strict(
        self,
        prompt: str,
        is_test: bool = False,
        timeout_sec: float | None = None,
    ) -> dict:
        """
        H5 对话打包调度：HTTP 失败或无法解析为合法 JSON 时抛异常，不返回走神占位字典。
        （保留兼容：Agent 主动消息等旧链路仍可使用）
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
