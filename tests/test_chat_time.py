# -*- coding: utf-8 -*-
"""chat-time.js 纯函数单测（Node 执行，不启动浏览器；断言按 Asia/Shanghai）。"""

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHAT_TIME_JS = REPO / "frontend" / "static" / "js" / "chat-time.js"


def _run_js(expr: str):
    """执行表达式并 JSON 解析 stdout。"""
    code = CHAT_TIME_JS.read_text(encoding="utf-8") + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.check_output(["node", "-e", code], text=True, cwd=str(REPO))
    return json.loads(out.strip())


def _run_js_block(snippet: str):
    """执行多行脚本；末尾须为 console.log(JSON.stringify(...))。"""
    code = CHAT_TIME_JS.read_text(encoding="utf-8") + "\n" + snippet.strip() + "\n"
    out = subprocess.check_output(["node", "-e", code], text=True, cwd=str(REPO))
    return json.loads(out.strip())


def test_should_show_first_message():
    assert _run_js("shouldShowTimeStamp(Date.now(), null)") is True


def test_should_not_show_within_five_minutes_same_day():
    assert _run_js("shouldShowTimeStamp(Date.now() + 60000, Date.now())") is False


def test_should_show_cross_natural_day():
    # 北京 2026-05-22 23:58 → 2026-05-23 00:02（UTC 分别 -8h）
    snippet = """
    const prev = Date.UTC(2026, 4, 22, 15, 58);
    const cur = Date.UTC(2026, 4, 22, 16, 2);
    console.log(JSON.stringify(shouldShowTimeStamp(cur, prev)));
    """
    assert _run_js_block(snippet) is True


def test_format_today_hour_minute():
    # 北京 2026-05-23 14:30 / now 15:00
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = Date.UTC(2026, 4, 23, 6, 30);
    const realNow = Date.now;
    Date.now = () => Date.UTC(2026, 4, 23, 7, 0);
    const s = formatChatTime(t);
    Date.now = realNow;
    console.log(JSON.stringify(s));
    """
    assert _run_js_block(snippet) == "14:30"


def test_format_yesterday_zh():
    # 北京 2026-05-22 09:05；now 2026-05-23 10:00
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = Date.UTC(2026, 4, 22, 1, 5);
    Date.now = () => Date.UTC(2026, 4, 23, 2, 0);
    console.log(JSON.stringify(formatChatTime(t)));
    """
    result = _run_js_block(snippet)
    assert result.startswith("昨天 ")
    assert "9:05" in result


def test_format_old_date_slash():
    # 北京 2026-05-01 08:00；now 2026-05-23 10:00
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = Date.UTC(2026, 4, 1, 0, 0);
    Date.now = () => Date.UTC(2026, 4, 23, 2, 0);
    console.log(JSON.stringify(formatChatTime(t)));
    """
    result = _run_js_block(snippet)
    assert result.startswith("2026/5/1 ")
    assert "8:00" in result


def test_beijing_parts_from_utc_iso_naive_concept():
    """UTC 06:30 → 北京 14:30。"""
    snippet = """
    const p = getBeijingParts(Date.UTC(2026, 4, 23, 6, 30));
    console.log(JSON.stringify(p));
    """
    p = _run_js_block(snippet)
    assert p["y"] == 2026
    assert p["mo"] == 5
    assert p["d"] == 23
    assert p["h"] == 14
    assert p["mi"] == 30
