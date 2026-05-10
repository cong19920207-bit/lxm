# -*- coding: utf-8 -*-
# 管理后台系统日志：文件解析与多文件时间排序（不触库）

import datetime
import tempfile
from pathlib import Path

import pytest

from backend.routers.admin.system_monitor import _parse_log_line, _read_and_filter_logs


def test_parse_log_line_valid():
    line = "2026-05-10 12:00:00 | INFO | some.module | hello | world"
    out = _parse_log_line(line)
    assert out is not None
    assert out["time"] == "2026-05-10 12:00:00"
    assert out["level"] == "INFO"
    assert out["module"] == "some.module"
    assert out["message"] == "hello | world"


def test_parse_log_line_invalid_short():
    assert _parse_log_line("no pipes") is None


@pytest.fixture()
def two_day_log_files():
    """模拟当日文件 + 昨日轮转文件，条目不按时间交错写入。"""
    with tempfile.TemporaryDirectory() as tmp:
        today_p = Path(tmp) / "system.log"
        yday_p = Path(tmp) / "system.log.2026-05-09"
        # 当日文件：较早的一条在前（文件中升序）
        today_p.write_text(
            "2026-05-10 10:00:00 | INFO | a | early today\n"
            "2026-05-10 18:00:00 | INFO | a | late today\n",
            encoding="utf-8",
        )
        # 昨日文件：午夜一条
        yday_p.write_text(
            "2026-05-09 23:59:00 | INFO | a | yesterday last\n",
            encoding="utf-8",
        )
        # 与 _collect_log_files 一致：先今日路径再昨日路径
        yield [str(today_p), str(yday_p)]


def test_read_and_filter_logs_sorts_newest_first(two_day_log_files):
    start = datetime.date(2026, 5, 9)
    end = datetime.date(2026, 5, 10)
    rows = _read_and_filter_logs(two_day_log_files, None, start, end)
    times = [r["time"] for r in rows]
    assert times == sorted(times, reverse=True)
    assert rows[0]["message"] == "late today"
    assert rows[-1]["message"] == "yesterday last"


def test_read_and_filter_logs_level_filter(two_day_log_files):
    start = datetime.date(2026, 5, 9)
    end = datetime.date(2026, 5, 10)
    rows = _read_and_filter_logs(two_day_log_files, "WARNING", start, end)
    assert rows == []
