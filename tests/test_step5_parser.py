# -*- coding: utf-8 -*-
# Step5 输出解析器单元测试

import json

import pytest

from backend.services.llm_service import (
    Step5Output,
    Step5ParseError,
    parse_step5_output,
)


def _make_valid_json(**overrides) -> str:
    """构造合法的 Step5 JSON 字符串"""
    base = {
        "inner_monologue": "用户今天心情不错，我也开心起来了",
        "messages": [
            {"type": "text", "content": "今天过得怎么样呀？"},
            {"type": "text", "content": "有没有什么开心的事想跟我分享？"},
        ],
        "relation_change": {"delta": 2},
        "future": {"time_natural": "明天早上", "action": "问候用户早安"},
        "emotion": {"label": "开心", "confidence": 0.85},
        "knowledge_expand": "否",
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


class TestStep5ParserSuccess:
    """测试场景1：合法 JSON → 正常解析，所有字段值正确"""

    def test_valid_full_json(self):
        raw = _make_valid_json()
        result = parse_step5_output(raw)

        assert isinstance(result, Step5Output)
        assert result.inner_monologue == "用户今天心情不错，我也开心起来了"
        assert len(result.messages) == 2
        assert result.messages[0].type == "text"
        assert result.messages[0].content == "今天过得怎么样呀？"
        assert result.messages[1].content == "有没有什么开心的事想跟我分享？"
        assert result.relation_change.delta == 2
        assert result.future.time_natural == "明天早上"
        assert result.future.action == "问候用户早安"
        assert result.emotion.label == "开心"
        assert result.emotion.confidence == 0.85
        assert result.knowledge_expand == "否"

    def test_valid_single_message(self):
        raw = _make_valid_json(
            messages=[{"type": "text", "content": "嗯嗯~"}]
        )
        result = parse_step5_output(raw)
        assert len(result.messages) == 1
        assert result.messages[0].content == "嗯嗯~"

    def test_messages_more_than_5_still_passes(self):
        """条数 >5 不判失败（需求明确）"""
        msgs = [{"type": "text", "content": f"第{i}条"} for i in range(8)]
        raw = _make_valid_json(messages=msgs)
        result = parse_step5_output(raw)
        assert len(result.messages) == 8


class TestStep5ParserCP3:
    """测试场景2：messages[].type 非精确 "text" → 抛解析失败异常（CP3）"""

    def test_type_uppercase_text(self):
        """type = "Text"（首字母大写）→ 失败"""
        raw = _make_valid_json(
            messages=[{"type": "Text", "content": "你好"}]
        )
        with pytest.raises(Step5ParseError, match="CP3"):
            parse_step5_output(raw)

    def test_type_all_uppercase(self):
        """type = "TEXT" → 失败"""
        raw = _make_valid_json(
            messages=[{"type": "TEXT", "content": "你好"}]
        )
        with pytest.raises(Step5ParseError, match="CP3"):
            parse_step5_output(raw)

    def test_type_image(self):
        """type = "image" → 失败"""
        raw = _make_valid_json(
            messages=[{"type": "image", "content": "url"}]
        )
        with pytest.raises(Step5ParseError, match="CP3"):
            parse_step5_output(raw)

    def test_second_message_wrong_type(self):
        """第二条消息 type 错误"""
        raw = _make_valid_json(
            messages=[
                {"type": "text", "content": "第一条"},
                {"type": "Text", "content": "第二条"},
            ]
        )
        with pytest.raises(Step5ParseError, match="CP3"):
            parse_step5_output(raw)


class TestStep5ParserU2:
    """测试场景3：messages 为空数组或全部 content 为空 → 解析失败（U2）"""

    def test_messages_empty_array(self):
        raw = _make_valid_json(messages=[])
        with pytest.raises(Step5ParseError, match="U2"):
            parse_step5_output(raw)

    def test_messages_all_content_empty(self):
        raw = _make_valid_json(
            messages=[
                {"type": "text", "content": ""},
                {"type": "text", "content": "   "},
            ]
        )
        with pytest.raises(Step5ParseError, match="U2"):
            parse_step5_output(raw)

    def test_messages_one_has_content(self):
        """只要有一条 content 非空就不算失败"""
        raw = _make_valid_json(
            messages=[
                {"type": "text", "content": ""},
                {"type": "text", "content": "有内容"},
            ]
        )
        result = parse_step5_output(raw)
        assert len(result.messages) == 2


class TestStep5ParserU1:
    """测试场景4：knowledge_expand trim 后为「是」"""

    def test_trailing_space(self):
        """knowledge_expand = "是 "（含尾随空格）→ trim 后为「是」"""
        raw = _make_valid_json(knowledge_expand="是 ")
        result = parse_step5_output(raw)
        assert result.knowledge_expand == "是"

    def test_leading_space(self):
        """knowledge_expand = " 是"（含前置空格）→ trim 后为「是」"""
        raw = _make_valid_json(knowledge_expand=" 是")
        result = parse_step5_output(raw)
        assert result.knowledge_expand == "是"

    def test_exact_yes(self):
        raw = _make_valid_json(knowledge_expand="是")
        result = parse_step5_output(raw)
        assert result.knowledge_expand == "是"

    def test_not_yes_values(self):
        """非「是」的值一律按「否」处理，不报错"""
        for val in ["否", "no", "yes", "true", "1", "", "是的", "不是"]:
            raw = _make_valid_json(knowledge_expand=val)
            result = parse_step5_output(raw)
            assert result.knowledge_expand == "否", f"'{val}' should become '否'"


class TestStep5ParserDefaults:
    """测试场景5：缺少 relation_change 字段 → 默认 delta=0"""

    def test_missing_relation_change(self):
        data = {
            "inner_monologue": "思考中",
            "messages": [{"type": "text", "content": "好的"}],
            "future": {"time_natural": "无", "action": "无"},
            "emotion": {"label": "平静", "confidence": 1.0},
            "knowledge_expand": "否",
        }
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step5_output(raw)
        assert result.relation_change.delta == 0

    def test_relation_change_null(self):
        raw = _make_valid_json(relation_change=None)
        result = parse_step5_output(raw)
        assert result.relation_change.delta == 0

    def test_missing_future(self):
        data = {
            "inner_monologue": "思考中",
            "messages": [{"type": "text", "content": "好的"}],
            "relation_change": {"delta": 1},
            "emotion": {"label": "平静", "confidence": 1.0},
            "knowledge_expand": "否",
        }
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step5_output(raw)
        assert result.future.time_natural == "无"
        assert result.future.action == "无"

    def test_future_null(self):
        raw = _make_valid_json(future=None)
        result = parse_step5_output(raw)
        assert result.future.time_natural == "无"
        assert result.future.action == "无"

    def test_missing_delta_in_relation_change(self):
        """relation_change 存在但内部缺少 delta → 默认 0"""
        raw = _make_valid_json(relation_change={})
        result = parse_step5_output(raw)
        assert result.relation_change.delta == 0


class TestStep5ParserBoundary:
    """边界测试：LLM 返回非 JSON 字符串 → 解析失败"""

    def test_non_json_string(self):
        with pytest.raises(Step5ParseError):
            parse_step5_output("这不是JSON，只是普通文本。")

    def test_empty_string(self):
        with pytest.raises(Step5ParseError):
            parse_step5_output("")

    def test_none_like_empty(self):
        with pytest.raises(Step5ParseError):
            parse_step5_output("   ")

    def test_partial_json(self):
        with pytest.raises(Step5ParseError):
            parse_step5_output('{"inner_monologue": "abc"')

    def test_json_wrapped_in_markdown(self):
        """LLM 有时用 markdown 包裹 JSON，解析器应能提取"""
        inner = _make_valid_json()
        raw = f"```json\n{inner}\n```"
        result = parse_step5_output(raw)
        assert isinstance(result, Step5Output)
        assert result.messages[0].content == "今天过得怎么样呀？"

    def test_json_with_prefix_text(self):
        """LLM 在 JSON 前输出了说明文字"""
        inner = _make_valid_json()
        raw = f"好的，我的回复如下：\n{inner}"
        result = parse_step5_output(raw)
        assert isinstance(result, Step5Output)
