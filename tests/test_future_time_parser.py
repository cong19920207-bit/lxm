# -*- coding: utf-8 -*-
# future_time_parser 单元测试

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.utils.future_time_parser import (
    is_future_slot_valid,
    parse_future_time,
)


class TestParseOffsetFormat:
    """格式1：N(分钟|小时|天)后"""

    def test_30_minutes_later(self):
        """场景1："30分钟后" → 当前 UTC + 1800s"""
        now = int(time.time())
        result = parse_future_time("30分钟后")
        assert result is not None
        # 允许 1 秒误差（执行耗时）
        assert abs(result - (now + 1800)) <= 1

    def test_2_hours_later(self):
        """"2小时后" → 当前 UTC + 7200s"""
        now = int(time.time())
        result = parse_future_time("2小时后")
        assert result is not None
        assert abs(result - (now + 7200)) <= 1

    def test_1_day_later(self):
        """"1天后" → 当前 UTC + 86400s"""
        now = int(time.time())
        result = parse_future_time("1天后")
        assert result is not None
        assert abs(result - (now + 86400)) <= 1

    def test_0_minutes_later(self):
        """边界："0分钟后" → 当前时间"""
        now = int(time.time())
        result = parse_future_time("0分钟后")
        assert result is not None
        assert abs(result - now) <= 1


class TestParseDatetimeFormat:
    """格式2：今天/明天 HH:MM"""

    def test_today_1430(self):
        """场景2："今天 14:30" → 当日 UTC 14:30"""
        result = parse_future_time("今天 14:30")
        assert result is not None
        dt = datetime.fromtimestamp(result, tz=timezone.utc)
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.second == 0
        # 确认是今天
        today_utc = datetime.now(timezone.utc).date()
        assert dt.date() == today_utc

    def test_tomorrow_0900(self):
        """场景3："明天 09:00" → 次日 UTC 09:00"""
        result = parse_future_time("明天 09:00")
        assert result is not None
        dt = datetime.fromtimestamp(result, tz=timezone.utc)
        assert dt.hour == 9
        assert dt.minute == 0
        assert dt.second == 0
        # 确认是明天
        tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        assert dt.date() == tomorrow_utc

    def test_today_no_space(self):
        """无空格 "今天14:30" 也能匹配（正则用 \\s*）"""
        result = parse_future_time("今天14:30")
        assert result is not None
        dt = datetime.fromtimestamp(result, tz=timezone.utc)
        assert dt.hour == 14
        assert dt.minute == 30


class TestNoneKeyword:
    """格式3："无" → None"""

    def test_none_keyword(self):
        """场景4："无" → None"""
        result = parse_future_time("无")
        assert result is None

    def test_none_with_spaces(self):
        """带空格的 " 无 " → None（strip 后匹配）"""
        result = parse_future_time(" 无 ")
        assert result is None


class TestInvalidFormats:
    """非法格式 → None + 日志"""

    def test_chinese_number(self):
        """场景6："两小时后" → None（中文数字不匹配）"""
        result = parse_future_time("两小时后")
        assert result is None

    def test_vague_time(self):
        """场景5："明天上午" → None（无具体时间）"""
        result = parse_future_time("明天上午")
        assert result is None

    def test_next_week(self):
        """"下周一" → None"""
        result = parse_future_time("下周一")
        assert result is None

    def test_empty_string(self):
        """空字符串 → None"""
        result = parse_future_time("")
        assert result is None

    def test_none_input(self):
        """None 输入 → None"""
        result = parse_future_time(None)
        assert result is None

    def test_random_text(self):
        """随机文本 → None"""
        result = parse_future_time("我想睡觉了")
        assert result is None

    def test_invalid_hour(self):
        """"今天 25:00" → None（小时越界）"""
        result = parse_future_time("今天 25:00")
        assert result is None

    def test_invalid_minute(self):
        """"今天 12:61" → None（分钟越界）"""
        result = parse_future_time("今天 12:61")
        assert result is None


class TestIsFutureSlotValid:
    """过期窗口验证"""

    def test_future_timestamp_valid(self):
        """未来时间戳 → 有效"""
        future_ts = int(time.time()) + 600
        assert is_future_slot_valid(future_ts) is True

    def test_just_passed_within_window(self):
        """刚过去 10 分钟 → 有效（在 30 分钟窗口内）"""
        past_ts = int(time.time()) - 600
        assert is_future_slot_valid(past_ts) is True

    def test_at_boundary(self):
        """恰好 30 分钟前 → 有效（<= 1800）"""
        boundary_ts = int(time.time()) - 1800
        assert is_future_slot_valid(boundary_ts) is True

    def test_expired(self):
        """超过 30 分钟 → 无效"""
        expired_ts = int(time.time()) - 1801
        assert is_future_slot_valid(expired_ts) is False

    def test_long_expired(self):
        """过期很久 → 无效"""
        expired_ts = int(time.time()) - 7200
        assert is_future_slot_valid(expired_ts) is False
