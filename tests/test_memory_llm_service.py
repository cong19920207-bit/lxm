# -*- coding: utf-8 -*-
# Step6 记忆总结 LLM 单元测试：Pydantic 模型、JSON 解析、Prompt 拼装

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.llm_service import MessageItem
from backend.services.memory_llm_service import (
    Step6MemoryOutput,
    Step6ParseError,
    build_step6_prompt,
    parse_step6_output,
)


# ============ 辅助工厂 ============


def _full_json(**overrides) -> str:
    """生成包含全部 11 字段的合法 JSON 字符串"""
    data = {
        "InnerMonologue": "内心想法测试",
        "CharacterPublicSettings": "外貌-体态：测试体态描述",
        "CharacterPrivateSettings": "用户-信任：信任度测试",
        "CharacterKnowledges": "咖啡-萃取：闷蒸30秒",
        "UserSettings": "作息-惯性：经常熬夜",
        "UserRealName": "小明",
        "UserHobbyName": "阿远",
        "UserDescription": "嘴硬心软型",
        "CharacterPurpose": "接下来两轮稳住气氛",
        "CharacterAttitude": "表面平和、内里保留试探",
        "RelationDescription": "聊得来的网友",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


class _FakeConv:
    """模拟 ConversationLog 实例"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


# ============ 测试场景1：合法 JSON 含全部 11 字段 → 正常解析 ============


class TestParseFullFields:
    def test_all_11_fields_parsed(self):
        raw = _full_json()
        result = parse_step6_output(raw)

        assert isinstance(result, Step6MemoryOutput)
        assert result.InnerMonologue == "内心想法测试"
        assert result.CharacterPublicSettings == "外貌-体态：测试体态描述"
        assert result.CharacterPrivateSettings == "用户-信任：信任度测试"
        assert result.CharacterKnowledges == "咖啡-萃取：闷蒸30秒"
        assert result.UserSettings == "作息-惯性：经常熬夜"
        assert result.UserRealName == "小明"
        assert result.UserHobbyName == "阿远"
        assert result.UserDescription == "嘴硬心软型"
        assert result.CharacterPurpose == "接下来两轮稳住气氛"
        assert result.CharacterAttitude == "表面平和、内里保留试探"
        assert result.RelationDescription == "聊得来的网友"

    def test_json_with_markdown_wrapper(self):
        """LLM 可能在 JSON 外包裹 markdown 代码块"""
        raw = "```json\n" + _full_json() + "\n```"
        result = parse_step6_output(raw)
        assert result.InnerMonologue == "内心想法测试"

    def test_json_with_prefix_text(self):
        """LLM 可能在 JSON 前输出一段解释文字"""
        raw = "以下是本轮记忆总结：\n" + _full_json()
        result = parse_step6_output(raw)
        assert result.CharacterPublicSettings == "外貌-体态：测试体态描述"


# ============ 测试场景2：某字段值为「无」 → 正常解析 ============


class TestParseFieldWithWu:
    def test_user_real_name_wu(self):
        raw = _full_json(UserRealName="无")
        result = parse_step6_output(raw)
        assert result.UserRealName == "无"

    def test_all_memory_fields_wu(self):
        raw = _full_json(
            CharacterPublicSettings="无",
            CharacterPrivateSettings="无",
            CharacterKnowledges="无",
            UserSettings="无",
        )
        result = parse_step6_output(raw)
        assert result.CharacterPublicSettings == "无"
        assert result.CharacterPrivateSettings == "无"
        assert result.CharacterKnowledges == "无"
        assert result.UserSettings == "无"

    def test_character_purpose_wu(self):
        raw = _full_json(CharacterPurpose="无", CharacterAttitude="无")
        result = parse_step6_output(raw)
        assert result.CharacterPurpose == "无"
        assert result.CharacterAttitude == "无"


# ============ 测试场景3：JSON 缺少某字段 → 默认为「无」 ============


class TestParseMissingFields:
    def test_missing_user_real_name(self):
        data = json.loads(_full_json())
        del data["UserRealName"]
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step6_output(raw)
        assert result.UserRealName == "无"

    def test_missing_inner_monologue_defaults_empty(self):
        """InnerMonologue 缺失默认空字符串，非「无」"""
        data = json.loads(_full_json())
        del data["InnerMonologue"]
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step6_output(raw)
        assert result.InnerMonologue == ""

    def test_missing_multiple_fields(self):
        data = json.loads(_full_json())
        del data["CharacterKnowledges"]
        del data["UserDescription"]
        del data["RelationDescription"]
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step6_output(raw)
        assert result.CharacterKnowledges == "无"
        assert result.UserDescription == "无"
        assert result.RelationDescription == "无"
        # 保留的字段不受影响
        assert result.CharacterPublicSettings == "外貌-体态：测试体态描述"

    def test_empty_json_object(self):
        """空 JSON 对象，所有字段走默认"""
        result = parse_step6_output("{}")
        assert result.InnerMonologue == ""
        assert result.CharacterPublicSettings == "无"
        assert result.UserRealName == "无"
        assert result.CharacterPurpose == "无"


# ============ 边界测试：多行 key：value 中某行无全角冒号 → 由下游 STEP-014 丢弃该行 ============


class TestMultiLineKeyValueBoundary:
    def test_line_without_fullwidth_colon_kept_as_is(self):
        """
        本环节仅解析 JSON 字段值为字符串，不做行级拆分校验。
        包含无全角冒号的行仍然保留在字段值中，由 STEP-014 负责丢弃。
        """
        multi_line = "外貌-体态：说话时肩膀略绷紧\n这行没有全角冒号\n兴趣-偏好：学手冲咖啡"
        raw = _full_json(CharacterPublicSettings=multi_line)
        result = parse_step6_output(raw)
        assert "这行没有全角冒号" in result.CharacterPublicSettings
        assert "外貌-体态：说话时肩膀略绷紧" in result.CharacterPublicSettings

    def test_newline_in_value(self):
        """多行内容中包含换行符，正常保留"""
        multi_line = "作息-惯性：熬夜到凌晨\n沟通-偏好：喜欢反问"
        raw = _full_json(UserSettings=multi_line)
        result = parse_step6_output(raw)
        assert "\n" in result.UserSettings


# ============ 异常情况测试 ============


class TestParseErrors:
    def test_empty_string_raises(self):
        with pytest.raises(Step6ParseError, match="空文本"):
            parse_step6_output("")

    def test_whitespace_only_raises(self):
        with pytest.raises(Step6ParseError, match="空文本"):
            parse_step6_output("   \n  ")

    def test_invalid_json_raises(self):
        with pytest.raises(Step6ParseError, match="JSON 解析失败"):
            parse_step6_output("{这不是合法JSON}")

    def test_pure_json_array_no_object(self):
        """纯数组内无对象字面量 → 正则无法提取 → 解析失败"""
        with pytest.raises(Step6ParseError, match="不是对象|JSON 解析失败"):
            parse_step6_output('["hello", "world"]')

    def test_json_array_with_nested_object_extracts_first(self):
        """数组内含对象 → 正则提取首个 {...}，缺失字段默认「无」"""
        result = parse_step6_output('[{"UserRealName": "小明"}]')
        assert result.UserRealName == "小明"
        assert result.CharacterPublicSettings == "无"

    def test_non_string_field_converted(self):
        """字段值为非字符串（如数字）→ 自动转为 str"""
        data = json.loads(_full_json())
        data["UserRealName"] = 12345
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_step6_output(raw)
        assert result.UserRealName == "12345"


# ============ Prompt 拼装测试 ============


class TestBuildStep6Prompt:
    def _build_default_prompt(self, **overrides) -> str:
        defaults = dict(
            persona_text="测试人格设定",
            level_name="朋友",
            relation_description="聊得来的网友",
            user_real_name=None,
            user_hobby_name="阿远",
            user_description="嘴硬心软型",
            character_purpose="稳住气氛",
            character_attitude="表面平和",
            recent_conversations=[
                _FakeConv("user", "你好"),
                _FakeConv("assistant", "嗨！"),
            ],
            step5_messages=[
                MessageItem(type="text", content="第一条回复"),
                MessageItem(type="text", content="第二条回复"),
            ],
            user_input="今天加班好累",
        )
        defaults.update(overrides)
        # build_step6_prompt 已异步化（STEP-006）：隔离热配置读取（patch 为 None → 走 DEFAULT），
        # 同步运行协程，保持各测试断言不变，验证 DEFAULT 拼装结果。
        with patch(
            "backend.services.memory_llm_service.admin_config_service.get_active_config",
            new=AsyncMock(return_value=None),
        ):
            return asyncio.run(build_step6_prompt(**defaults))

    def test_prompt_contains_system_instruction(self):
        prompt = self._build_default_prompt()
        assert "【系统指令】" in prompt
        assert "仅输出合法 JSON" in prompt

    def test_prompt_contains_time(self):
        prompt = self._build_default_prompt()
        assert "【当前时间】" in prompt

    def test_prompt_contains_persona(self):
        prompt = self._build_default_prompt()
        assert "【人格设定】" in prompt
        assert "测试人格设定" in prompt

    def test_prompt_contains_relationship(self):
        prompt = self._build_default_prompt()
        assert "【关系状态】" in prompt
        assert "朋友" in prompt
        assert "聊得来的网友" in prompt
        assert "阿远" in prompt

    def test_prompt_contains_recent_history(self):
        prompt = self._build_default_prompt()
        assert "【近期历史摘要" in prompt
        assert "用户：你好" in prompt
        assert "林小梦：嗨！" in prompt

    def test_prompt_contains_current_turn(self):
        prompt = self._build_default_prompt()
        assert "【本轮完整对话】" in prompt
        assert "用户：今天加班好累" in prompt
        assert "林小梦：第一条回复" in prompt

    def test_prompt_contains_task(self):
        prompt = self._build_default_prompt()
        assert "【任务】" in prompt
        assert "InnerMonologue" in prompt
        assert "CharacterPublicSettings" in prompt
        assert "RelationDescription" in prompt

    def test_prompt_contains_few_shot(self):
        prompt = self._build_default_prompt()
        assert "【输出示例】" in prompt
        assert "CharacterPurpose" in prompt
        assert "CharacterAttitude" in prompt

    def test_data_source_is_step5_only(self):
        """本轮 AI 回复来源仅为 Step5 messages（非 Step5.5）"""
        step5_msgs = [
            MessageItem(type="text", content="Step5原始回复A"),
            MessageItem(type="text", content="Step5原始回复B"),
        ]
        prompt = self._build_default_prompt(step5_messages=step5_msgs)
        assert "Step5原始回复A" in prompt
        assert "Step5原始回复B" in prompt

    def test_null_relationship_fields_show_default(self):
        """关系字段为 None 时显示占位文案"""
        prompt = self._build_default_prompt(
            relation_description=None,
            user_real_name=None,
            user_hobby_name=None,
            user_description=None,
            character_purpose=None,
            character_attitude=None,
        )
        assert "用户真实称呼：无" in prompt
        assert "用户昵称/绰号：无" in prompt

    def test_empty_recent_conversations(self):
        prompt = self._build_default_prompt(recent_conversations=[])
        assert "暂无历史对话" in prompt

    def test_all_11_fields_in_few_shot(self):
        """§2.5：8 字段全部出现在 few-shot 示例中（实际是 11 字段）"""
        prompt = self._build_default_prompt()
        for field in [
            "InnerMonologue",
            "CharacterPublicSettings",
            "CharacterPrivateSettings",
            "CharacterKnowledges",
            "UserSettings",
            "UserRealName",
            "UserHobbyName",
            "UserDescription",
            "CharacterPurpose",
            "CharacterAttitude",
            "RelationDescription",
        ]:
            assert field in prompt, f"few-shot 中缺少字段 {field}"
