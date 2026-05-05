# -*- coding: utf-8 -*-
# future.time_natural 自然语言时间解析器
# 将 LLM 输出的自然语言时间转为 Unix 时间戳（UTC 基准）

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# 三种合法格式的正则
_PATTERN_OFFSET = re.compile(r"^(\d+)(分钟|小时|天)后$")
_PATTERN_DATETIME = re.compile(r"^(今天|明天)\s*(\d{2}):(\d{2})$")

# 偏移单位到秒的映射
_UNIT_TO_SECONDS = {
    "分钟": 60,
    "小时": 3600,
    "天": 86400,
}

# 过期窗口：30 分钟
_EXPIRY_WINDOW_SECONDS = 1800


def parse_future_time(time_natural: str) -> Optional[int]:
    """将自然语言时间字符串解析为 Unix 时间戳（UTC）。

    支持格式：
      - "N分钟后" / "N小时后" / "N天后" → 当前 UTC + 偏移
      - "今天 HH:MM" → 当日 UTC 指定时刻
      - "明天 HH:MM" → 次日 UTC 指定时刻
      - "无" → None（表示无预约）

    其他任何格式返回 None 并写结构化日志。
    """
    if not time_natural or not isinstance(time_natural, str):
        _log_parse_failure(time_natural, "空值或非字符串")
        return None

    text = time_natural.strip()

    # "无" → 无预约
    if text == "无":
        return None

    # 格式1：N(分钟|小时|天)后
    match = _PATTERN_OFFSET.match(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        offset_seconds = amount * _UNIT_TO_SECONDS[unit]
        return int(time.time()) + offset_seconds

    # 格式2：今天/明天 HH:MM
    match = _PATTERN_DATETIME.match(text)
    if match:
        day_word = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3))

        # 校验时间合法性
        if hour > 23 or minute > 59:
            _log_parse_failure(text, f"时间值越界: {hour}:{minute}")
            return None

        now_utc = datetime.now(timezone.utc)
        if day_word == "今天":
            target = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            target = (now_utc + timedelta(days=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        return int(target.timestamp())

    # 不匹配任何格式 → 解析失败
    _log_parse_failure(text, "无法匹配任何合法格式")
    return None


def is_future_slot_valid(timestamp: int) -> bool:
    """判断 future 槽位时间戳是否仍在有效窗口内。

    规则：当前 UTC 时间距 timestamp 不超过 30 分钟（1800 秒）视为有效。
    即 timestamp 在 [now - 1800, now + ∞) 范围内有效。
    """
    now = int(time.time())
    return (now - timestamp) <= _EXPIRY_WINDOW_SECONDS


def _log_parse_failure(raw_input: str, reason: str) -> None:
    """写结构化日志记录解析失败"""
    logger.warning(
        "future_time_parse_failure",
        extra={
            "raw_input": raw_input,
            "reason": reason,
            "action": "slot_cleared",
        },
    )
