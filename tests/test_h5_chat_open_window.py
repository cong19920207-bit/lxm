# -*- coding: utf-8 -*-
"""
H5 聊天未闭环窗口逻辑单测（镜像 frontend/pages/chat.html 中 getOpenWindowUserRows 等）。

与 backend/services/chat_service.fetch_open_window_user_rows 语义对齐：
最后一条已落库 assistant 之后的 user 行；流式中 data-ai-in-flight 的 AI 不计入边界。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RowType = Literal["ai", "user", "agent"]


@dataclass
class MockRow:
    kind: RowType
    delivery: str = "delivered"
    in_flight: bool = False

    @property
    def is_user(self) -> bool:
        return self.kind == "user"

    @property
    def is_ai_boundary(self) -> bool:
        return self.kind == "ai" and not self.in_flight


def get_open_window_user_indices(rows: list[MockRow]) -> list[int]:
    """镜像 chat.html getOpenWindowUserRows 的索引版，便于断言。"""
    last_ai_idx = -1
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r.kind == "agent":
            continue
        if r.kind == "ai" and r.in_flight:
            continue
        if r.kind == "ai":
            last_ai_idx = i
            break
    out: list[int] = []
    for i in range(last_ai_idx + 1, len(rows)):
        if rows[i].is_user:
            out.append(i)
    return out


def count_open_pending(rows: list[MockRow]) -> tuple[int, bool]:
    pending = 0
    has_bang = False
    for i in get_open_window_user_indices(rows):
        d = rows[i].delivery
        if d in ("failed_timeout", "failed_error"):
            has_bang = True
        if d in ("pending_llm", "failed_timeout", "failed_error"):
            pending += 1
    return pending, has_bang


def mark_open_window_delivered(rows: list[MockRow]) -> None:
    for i in get_open_window_user_indices(rows):
        d = rows[i].delivery
        if d in ("pending_llm", "failed_timeout", "failed_error"):
            rows[i].delivery = "delivered"


class TestOpenWindowBoundary:
    def test_before_finalize_inflight_excludes_new_ai(self):
        """done 前：in-flight AI 在末尾，应标窗口内 user 为 delivered。"""
        rows = [
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        mark_open_window_delivered(rows)
        assert [r.delivery for r in rows[1:4]] == ["delivered", "delivered", "delivered"]

    def test_after_finalize_old_logic_would_fail(self):
        """finalize 后：最后 AI 已在末尾，旧逻辑 lastAiIdx+1 无 user（回归用例）。"""
        rows = [
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("ai"),
        ]
        last_ai_idx = len(rows) - 1
        marked = [
            i
            for i in range(last_ai_idx + 1, len(rows))
            if rows[i].is_user and rows[i].delivery == "pending_llm"
        ]
        assert marked == []
        # 正确做法：须在 finalize 前标；此处模拟 finalize 前状态
        rows_pre = [
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        mark_open_window_delivered(rows_pre)
        assert rows_pre[1].delivery == "delivered"
        assert rows_pre[2].delivery == "delivered"

    def test_count_only_open_window_not_history(self):
        rows = [
            MockRow("ai"),
            MockRow("user", "delivered"),
            MockRow("user", "delivered"),
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        pending, has_bang = count_open_pending(rows)
        assert pending == 2
        assert has_bang is False

    def test_agent_does_not_close_window(self):
        rows = [
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("agent"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        indices = get_open_window_user_indices(rows)
        assert indices == [1, 3]

    def test_multibubble_inflight_skipped_for_boundary(self):
        rows = [
            MockRow("ai"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
            MockRow("ai", in_flight=True),
        ]
        mark_open_window_delivered(rows)
        assert rows[1].delivery == "delivered"

    def test_first_conversation_no_prior_ai(self):
        rows = [
            MockRow("user", "pending_llm"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        mark_open_window_delivered(rows)
        assert rows[0].delivery == "delivered"
        assert rows[1].delivery == "delivered"

    def test_resend_failed_marked_delivered_on_done(self):
        rows = [
            MockRow("ai"),
            MockRow("user", "failed_timeout"),
            MockRow("user", "pending_llm"),
            MockRow("ai", in_flight=True),
        ]
        mark_open_window_delivered(rows)
        assert rows[1].delivery == "delivered"
        assert rows[2].delivery == "delivered"

    def test_pending_five_in_window_blocks(self):
        rows = [
            MockRow("ai"),
            *[MockRow("user", "pending_llm") for _ in range(5)],
            MockRow("ai", in_flight=True),
        ]
        pending, has_bang = count_open_pending(rows)
        assert pending == 5
        assert has_bang is False

    def test_has_bang_allows_sixth_slot_semantics(self):
        """有叹号时 hasBang=true（前端不拦第 6 条，与契约一致）。"""
        rows = [
            MockRow("ai"),
            *[MockRow("user", "pending_llm") for _ in range(4)],
            MockRow("user", "failed_timeout"),
            MockRow("ai", in_flight=True),
        ]
        pending, has_bang = count_open_pending(rows)
        assert pending == 5
        assert has_bang is True


def test_chat_html_contains_open_window_helpers():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "pages" / "chat.html").read_text(
        encoding="utf-8"
    )
    assert "function getOpenWindowUserRows()" in html
    assert "data-ai-in-flight') === '1'" in html
    assert "markOpenWindowUsersDelivered()" in html
    # done 须在 finalize 之前标记
    idx_mark = html.index("markOpenWindowUsersDelivered()")
    idx_finalize = html.index("aiBubble.finalize(doneMessages")
    assert idx_mark < idx_finalize
