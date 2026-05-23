# -*- coding: utf-8 -*-
"""chat-time.js 纯函数单测（Node 执行，不启动浏览器）。"""

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
    snippet = """
    const prev = new Date(2026, 4, 22, 23, 58).getTime();
    const cur = new Date(2026, 4, 23, 0, 2).getTime();
    console.log(JSON.stringify(shouldShowTimeStamp(cur, prev)));
    """
    assert _run_js_block(snippet) is True


def test_format_today_hour_minute():
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = new Date(2026, 4, 23, 14, 30).getTime();
    const realNow = Date.now;
    Date.now = () => new Date(2026, 4, 23, 15, 0).getTime();
    const s = formatChatTime(t);
    Date.now = realNow;
    console.log(JSON.stringify(s));
    """
    assert _run_js_block(snippet) == "14:30"


def test_format_yesterday_zh():
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = new Date(2026, 4, 22, 9, 5).getTime();
    Date.now = () => new Date(2026, 4, 23, 10, 0).getTime();
    console.log(JSON.stringify(formatChatTime(t)));
    """
    result = _run_js_block(snippet)
    assert result.startswith("昨天 ")
    assert "9:05" in result


def test_format_old_date_slash():
    snippet = """
    setChatTimeOptions({ locale: 'zh', hour12: false });
    const t = new Date(2026, 4, 1, 8, 0).getTime();
    Date.now = () => new Date(2026, 4, 23, 10, 0).getTime();
    console.log(JSON.stringify(formatChatTime(t)));
    """
    result = _run_js_block(snippet)
    assert result.startswith("2026/5/1 ")
    assert "8:00" in result
