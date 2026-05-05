# -*- coding: utf-8 -*-
# Step5.5 响应润色单元测试

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.llm_service import MessageItem, merge_messages_if_exceed
from backend.services.step5_5_service import (
    GATE_A_PROBABILITY,
    GATE_B_PROBABILITY,
    STEP5_5_SWITCH_CONFIG_KEY,
    STEP5_5_TIMEOUT_SEC,
    build_step5_5_prompt,
    execute_step5_5,
    parse_step5_5_output,
    should_trigger_step5_5,
)


# ============ 辅助工厂函数 ============


def _make_messages(count: int = 2) -> list[MessageItem]:
    return [
        MessageItem(type="text", content=f"第{i + 1}条内容")
        for i in range(count)
    ]


def _make_valid_step5_5_output(count: int = 2) -> str:
    """构造合法的 Step5.5 JSON 数组输出"""
    items = [{"type": "text", "content": f"润色后第{i + 1}条"} for i in range(count)]
    return json.dumps(items, ensure_ascii=False)


class _ConvProxy:
    """模拟 ConversationLog 对象"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


def _make_recent_conversations() -> list:
    return [
        _ConvProxy("user", "今天好累啊"),
        _ConvProxy("assistant", "辛苦了，休息一下吧"),
    ]


def _base_execute_kwargs(**overrides) -> dict:
    """构造 execute_step5_5 的基本参数"""
    base = {
        "step5_messages": _make_messages(2),
        "step5_inner_monologue": "用户似乎有些疲惫",
        "step5_emotion_label": "担心",
        "step5_emotion_confidence": 0.85,
        "step5_relation_change_delta": 1,
        "step5_future_time_natural": "无",
        "step5_future_action": "无",
        "step5_knowledge_expand": "否",
        "level_name": "朋友",
        "user_hobby_name": None,
        "user_real_name": None,
        "recent_conversations": _make_recent_conversations(),
    }
    base.update(overrides)
    return base


# ============ 测试场景 1：总开关关闭 → 不触发 ============


class TestStep55SwitchOff:
    """测试场景1：总开关关闭 → 不触发 Step5.5"""

    @pytest.mark.asyncio
    async def test_switch_off_returns_false(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await should_trigger_step5_5("否")
            assert result is False

    @pytest.mark.asyncio
    async def test_switch_none_returns_false(self):
        """admin_config 无此配置项 → 视为关闭"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await should_trigger_step5_5("是")
            assert result is False

    @pytest.mark.asyncio
    async def test_switch_string_false(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value="false",
        ):
            result = await should_trigger_step5_5("是")
            assert result is False

    @pytest.mark.asyncio
    async def test_execute_returns_none_when_switch_off(self):
        """execute_step5_5 在开关关闭时直接返回 None"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None


# ============ 测试场景 2：开关开启 + knowledge_expand="否" + 命中门闩 A ============


class TestStep55GateA:
    """测试场景2：总开关开启 + knowledge_expand="否" + rand=0.05 → 命中门闩 A → 触发"""

    @pytest.mark.asyncio
    async def test_gate_a_hit(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "否", _rand_a=0.05, _rand_b=0.99
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_gate_a_miss(self):
        """rand_a=0.5 超过 0.12 → 门闩 A 未命中"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "否", _rand_a=0.5, _rand_b=0.99
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_gate_a_boundary(self):
        """rand_a 恰好等于 0.12 → 不命中（< 才命中）"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "否", _rand_a=GATE_A_PROBABILITY, _rand_b=0.99
            )
            assert result is False


# ============ 测试场景 3：开关开启 + knowledge_expand="是" + 命中门闩 B ============


class TestStep55GateB:
    """测试场景3：总开关开启 + knowledge_expand="是" + rand_A=0.5 + rand_B=0.3 → 命中门闩 B"""

    @pytest.mark.asyncio
    async def test_gate_b_hit(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "是", _rand_a=0.5, _rand_b=0.3
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_gate_b_only_with_knowledge_expand_yes(self):
        """knowledge_expand="否" 时门闩 B 不生效"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "否", _rand_a=0.5, _rand_b=0.3
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_gate_b_boundary(self):
        """rand_b 恰好等于 0.5 → 不命中"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "是", _rand_a=0.5, _rand_b=GATE_B_PROBABILITY
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_both_gates_hit(self):
        """A 和 B 都命中 → 仍然触发"""
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await should_trigger_step5_5(
                "是", _rand_a=0.01, _rand_b=0.1
            )
            assert result is True


# ============ 测试场景 4：LLM 返回非法 JSON → 回退 Step5 ============


class TestStep55InvalidJSON:
    """测试场景4：5.5 LLM 返回非法 JSON → 回退 Step5"""

    @pytest.mark.asyncio
    async def test_non_json_returns_none(self):
        """LLM 返回纯文本 → parse 失败 → execute 返回 None"""
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value="这不是JSON，只是普通文本。",
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None

    @pytest.mark.asyncio
    async def test_json_object_not_array(self):
        """LLM 返回 JSON 对象而非数组 → 失败"""
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value='{"type": "text", "content": "hello"}',
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None

    @pytest.mark.asyncio
    async def test_wrong_type_field(self):
        """type 不是 "text" → 失败"""
        bad_output = json.dumps([{"type": "image", "content": "hello"}])
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value=bad_output,
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """content 为空字符串 → 失败"""
        bad_output = json.dumps([{"type": "text", "content": ""}])
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value=bad_output,
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None


# ============ 测试场景 5：LLM 超时 → 回退 Step5 ============


class TestStep55Timeout:
    """测试场景5：5.5 超时 → 回退 Step5"""

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        async def _slow_llm(*args, **kwargs):
            await asyncio.sleep(60)
            return "[]"

        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                side_effect=_slow_llm,
            ),
            patch(
                "backend.services.step5_5_service.STEP5_5_TIMEOUT_SEC",
                0.1,
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None

    @pytest.mark.asyncio
    async def test_http_exception_returns_none(self):
        """LLM HTTP 异常 → 回退"""
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM 非流式调用失败"),
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is None


# ============ 边界测试：5.5 返回 7 条 → 合并到 5 条 ============


class TestStep55MergeExceed:
    """边界测试：5.5 返回 7 条 → 合并到 5 条"""

    @pytest.mark.asyncio
    async def test_7_messages_merged_to_5(self):
        output_7 = _make_valid_step5_5_output(7)
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value=output_7,
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is not None
            assert len(result) == 5
            # 第 5 条应含合并内容
            assert "润色后第5条" in result[4].content
            assert "润色后第6条" in result[4].content
            assert "润色后第7条" in result[4].content

    @pytest.mark.asyncio
    async def test_5_messages_no_merge(self):
        """恰好 5 条 → 不合并"""
        output_5 = _make_valid_step5_5_output(5)
        with (
            patch(
                "backend.services.step5_5_service.admin_config_service.get_active_config",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.should_trigger_step5_5",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.step5_5_service.llm_client.chat_sync",
                new_callable=AsyncMock,
                return_value=output_5,
            ),
        ):
            result = await execute_step5_5(**_base_execute_kwargs())
            assert result is not None
            assert len(result) == 5


# ============ 解析器独立测试 ============


class TestStep55Parser:
    """parse_step5_5_output 独立校验测试"""

    def test_valid_array(self):
        raw = json.dumps([
            {"type": "text", "content": "你好呀"},
            {"type": "text", "content": "今天怎么样"},
        ])
        result = parse_step5_5_output(raw)
        assert len(result) == 2
        assert result[0].content == "你好呀"

    def test_markdown_wrapped(self):
        """LLM 用 markdown 包裹 → 应能提取"""
        inner = json.dumps([{"type": "text", "content": "测试"}])
        raw = f"```json\n{inner}\n```"
        result = parse_step5_5_output(raw)
        assert len(result) == 1

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="空文本"):
            parse_step5_5_output("")

    def test_empty_array_raises(self):
        with pytest.raises(ValueError, match="空数组"):
            parse_step5_5_output("[]")

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="不是数组"):
            parse_step5_5_output('{"type": "text"}')

    def test_type_not_text_raises(self):
        raw = json.dumps([{"type": "Image", "content": "abc"}])
        with pytest.raises(ValueError, match='非精确 "text"'):
            parse_step5_5_output(raw)

    def test_content_whitespace_only_raises(self):
        raw = json.dumps([{"type": "text", "content": "   "}])
        with pytest.raises(ValueError, match="content 为空"):
            parse_step5_5_output(raw)


# ============ Prompt 构建测试 ============


class TestStep55PromptBuilder:
    """build_step5_5_prompt 基本校验"""

    def test_prompt_contains_required_sections(self):
        prompt = build_step5_5_prompt(
            step5_inner_monologue="内心独白测试",
            step5_emotion_label="开心",
            step5_emotion_confidence=0.9,
            step5_relation_change_delta=1,
            step5_future_time_natural="明天",
            step5_future_action="问候",
            step5_messages=_make_messages(2),
            level_name="朋友",
            user_hobby_name="小可爱",
            user_real_name="张三",
            recent_conversations=_make_recent_conversations(),
        )
        assert "消息编排模块" in prompt
        assert "角色语态特征" in prompt
        assert "输出格式" in prompt
        assert "只读参考上下文" in prompt
        assert "内心独白测试" in prompt
        assert "开心" in prompt
        assert "delta = 1" in prompt
        assert "朋友" in prompt
        assert "小可爱" in prompt
        assert "张三" in prompt
        assert "待润色消息" in prompt
        assert "第1条内容" in prompt

    def test_prompt_no_hobby_name(self):
        """无亲密称呼时显示「无」"""
        prompt = build_step5_5_prompt(
            step5_inner_monologue="",
            step5_emotion_label="平静",
            step5_emotion_confidence=1.0,
            step5_relation_change_delta=0,
            step5_future_time_natural="无",
            step5_future_action="无",
            step5_messages=_make_messages(1),
            level_name="陌生",
            user_hobby_name=None,
            user_real_name=None,
            recent_conversations=[],
        )
        assert "亲密称呼：无" in prompt
        assert "用户真名：无" in prompt


# ============ 总开关值兼容测试 ============


class TestStep55SwitchValues:
    """验证总开关各种值类型的判定"""

    @pytest.mark.asyncio
    async def test_switch_string_true(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value="true",
        ):
            result = await should_trigger_step5_5("否", _rand_a=0.01)
            assert result is True

    @pytest.mark.asyncio
    async def test_switch_int_1(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=1,
        ):
            result = await should_trigger_step5_5("否", _rand_a=0.01)
            assert result is True

    @pytest.mark.asyncio
    async def test_switch_dict_enabled(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value={"enabled": True},
        ):
            result = await should_trigger_step5_5("否", _rand_a=0.01)
            assert result is True

    @pytest.mark.asyncio
    async def test_switch_string_0(self):
        with patch(
            "backend.services.step5_5_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value="0",
        ):
            result = await should_trigger_step5_5("否", _rand_a=0.01)
            assert result is False
