# -*- coding: utf-8 -*-
# §2.9.1 messages 合并规则单元测试

import logging

import pytest

from backend.services.llm_service import MessageItem, merge_messages_if_exceed


def _make_messages(count: int) -> list[MessageItem]:
    """生成指定条数的 MessageItem 列表"""
    return [
        MessageItem(type="text", content=f"第{i + 1}条内容")
        for i in range(count)
    ]


class TestMergeMessagesNoMerge:
    """测试场景1：条数 ≤ max_count → 原样返回，不合并"""

    def test_3_messages_no_merge(self):
        msgs = _make_messages(3)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 3
        for i in range(3):
            assert result[i].content == f"第{i + 1}条内容"
            assert result[i].type == "text"

    def test_5_messages_no_merge(self):
        msgs = _make_messages(5)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 5
        for i in range(5):
            assert result[i].content == f"第{i + 1}条内容"

    def test_1_message_no_merge(self):
        msgs = _make_messages(1)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 1
        assert result[0].content == "第1条内容"

    def test_empty_list(self):
        result = merge_messages_if_exceed([])
        assert len(result) == 0


class TestMergeMessages6Items:
    """测试场景2：6 条 → 返回 5 条，第 5 条 content 含原第 5、6 条"""

    def test_6_messages_merge_to_5(self):
        msgs = _make_messages(6)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 5

        for i in range(4):
            assert result[i].content == f"第{i + 1}条内容"
            assert result[i].type == "text"

        assert result[4].content == "第5条内容 第6条内容"
        assert result[4].type == "text"

    def test_original_not_modified(self):
        """合并后原列表不被修改"""
        msgs = _make_messages(6)
        original_5th = msgs[4].content
        merge_messages_if_exceed(msgs)

        assert len(msgs) == 6
        assert msgs[4].content == original_5th


class TestMergeMessages8Items:
    """测试场景3：8 条 → 返回 5 条，第 5 条包含原第 5、6、7、8 条"""

    def test_8_messages_merge_to_5(self):
        msgs = _make_messages(8)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 5

        for i in range(4):
            assert result[i].content == f"第{i + 1}条内容"

        assert result[4].content == "第5条内容 第6条内容 第7条内容 第8条内容"
        assert result[4].type == "text"

    def test_10_messages_merge_to_5(self):
        msgs = _make_messages(10)
        result = merge_messages_if_exceed(msgs)

        assert len(result) == 5
        expected_tail = " ".join(f"第{i + 1}条内容" for i in range(4, 10))
        assert result[4].content == expected_tail


class TestMergeMessagesTruncation:
    """边界测试：合并后第 5 条超 max_length → 截断至 max_length 并记录日志"""

    def test_truncation_at_max_length(self):
        msgs = [
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="A" * 100),
            MessageItem(type="text", content="B" * 100),
        ]
        max_len = 50
        result = merge_messages_if_exceed(msgs, max_length=max_len)

        assert len(result) == 5
        assert len(result[4].content) == max_len

    def test_truncation_logs_warning(self, caplog):
        msgs = [
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="A" * 100),
            MessageItem(type="text", content="B" * 100),
        ]
        max_len = 50
        with caplog.at_level(logging.WARNING):
            merge_messages_if_exceed(msgs, max_length=max_len)

        assert any("超长" in record.message for record in caplog.records)

    def test_exactly_at_max_length_no_truncation(self):
        """合并结果恰好等于 max_length 时不截断"""
        content_5 = "A" * 10
        content_6 = "B" * 9
        expected = content_5 + " " + content_6
        max_len = len(expected)

        msgs = [
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content="短"),
            MessageItem(type="text", content=content_5),
            MessageItem(type="text", content=content_6),
        ]
        result = merge_messages_if_exceed(msgs, max_length=max_len)

        assert len(result[4].content) == max_len
        assert result[4].content == expected

    def test_no_truncation_within_limit(self):
        """合并后未超限时不截断，不打日志"""
        msgs = _make_messages(6)
        result = merge_messages_if_exceed(msgs, max_length=2000)

        assert result[4].content == "第5条内容 第6条内容"


class TestMergeMessagesCustomMaxCount:
    """自定义 max_count 参数"""

    def test_max_count_3(self):
        msgs = _make_messages(5)
        result = merge_messages_if_exceed(msgs, max_count=3)

        assert len(result) == 3
        assert result[0].content == "第1条内容"
        assert result[1].content == "第2条内容"
        assert result[2].content == "第3条内容 第4条内容 第5条内容"

    def test_max_count_1(self):
        msgs = _make_messages(3)
        result = merge_messages_if_exceed(msgs, max_count=1)

        assert len(result) == 1
        assert result[0].content == "第1条内容 第2条内容 第3条内容"


class TestMergeMessagesSpaceJoin:
    """验证半角空格拼接规则"""

    def test_space_joining(self):
        """第 5 条末尾无论是否有空格，拼接时始终追加空格 + 下一段"""
        msgs = [
            MessageItem(type="text", content="a"),
            MessageItem(type="text", content="b"),
            MessageItem(type="text", content="c"),
            MessageItem(type="text", content="d"),
            MessageItem(type="text", content="尾部有空格 "),
            MessageItem(type="text", content="第六条"),
        ]
        result = merge_messages_if_exceed(msgs)

        assert result[4].content == "尾部有空格  第六条"

    def test_empty_content_still_joins(self):
        """空 content 条目仍按空格拼接"""
        msgs = [
            MessageItem(type="text", content="a"),
            MessageItem(type="text", content="b"),
            MessageItem(type="text", content="c"),
            MessageItem(type="text", content="d"),
            MessageItem(type="text", content="第五条"),
            MessageItem(type="text", content=""),
            MessageItem(type="text", content="第七条"),
        ]
        result = merge_messages_if_exceed(msgs)

        assert result[4].content == "第五条  第七条"
