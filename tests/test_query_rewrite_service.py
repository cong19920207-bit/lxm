# -*- coding: utf-8 -*-
# Step1.5 查询重写 LLM 单元测试（STEP-019）
# 场景1：正常返回 → 3 组 QueryQuestion/Keywords 完整
# 场景2：LLM 两次超时 → 降级路径 + 结构化日志
# 场景3：InnerMonologue 仅内存字段（本服务不落库、不返前端）
# 边界：非法 JSON → 两次失败后降级

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.services.query_rewrite_service import (
    QueryRewriteOutput,
    _build_step1_5_prompt,
    _parse_query_rewrite_output,
    execute_query_rewrite,
)


def _valid_step1_5_json(**overrides) -> str:
    data = {
        "InnerMonologue": "用户在问熬夜相关，语气轻松",
        "CharacterGlobalQueryQuestion": "林小梦的作息与性格设定是什么",
        "CharacterGlobalQueryKeywords": "作息 性格",
        "CharacterKnowledgeQueryQuestion": "熬夜对健康的影响有哪些知识点",
        "CharacterKnowledgeQueryKeywords": "熬夜 健康",
        "UserProfileQueryQuestion": "用户最近提到过睡眠或工作压力吗",
        "UserProfileQueryKeywords": "睡眠 压力",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


class _FakeConv:
    """模拟 ConversationLog"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


def _base_round_context() -> dict:
    return {
        "time_description": "现在是周三下午15点30分",
        "activity_description": "她在写代码",
        "relation_description": "聊得来的朋友",
        "user_real_name": "",
        "user_hobby_name": "阿远",
        "level_name": "朋友",
    }


def _base_execute_kwargs() -> dict:
    return {
        "user_id": 10001,
        "last_user_text": "今天又熬夜了哈哈",
        "persona_text": "温柔细腻的林小梦",
        "round_context": _base_round_context(),
        "recent_conversations": [
            _FakeConv("user", "早安"),
            _FakeConv("assistant", "早呀"),
        ],
        "source": "main",
    }


# ============ 场景1：正常返回 → 3 组完整 ============


class TestScenario1NormalSuccess:
    @pytest.mark.asyncio
    async def test_three_groups_query_complete(self):
        raw = _valid_step1_5_json()

        with patch(
            "backend.services.query_rewrite_service.llm_client.chat_sync",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            result = await execute_query_rewrite(**_base_execute_kwargs())

        assert result.success is True
        assert result.output is not None
        assert result.fallback_embedding == []

        o = result.output
        assert o.CharacterGlobalQueryQuestion.strip()
        assert o.CharacterGlobalQueryKeywords.strip()
        assert o.CharacterKnowledgeQueryQuestion.strip()
        assert o.CharacterKnowledgeQueryKeywords.strip()
        assert o.UserProfileQueryQuestion.strip()
        assert o.UserProfileQueryKeywords.strip()


# ============ 场景2：两次超时 → 降级 + 日志 ============


class TestScenario2DoubleTimeoutFallback:
    @pytest.mark.asyncio
    async def test_two_timeouts_then_fallback_embedding_and_logs(self, caplog):
        caplog.set_level("INFO")

        fake_vec = [0.01, 0.02, 0.03]

        with patch(
            "backend.services.query_rewrite_service.llm_client.chat_sync",
            new_callable=AsyncMock,
            side_effect=[
                httpx.TimeoutException("timeout1"),
                httpx.TimeoutException("timeout2"),
            ],
        ), patch(
            "backend.services.query_rewrite_service.embedding_service.get_embedding",
            new_callable=AsyncMock,
            return_value=fake_vec,
        ), patch(
            "backend.services.query_rewrite_service.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await execute_query_rewrite(**_base_execute_kwargs())

        assert result.success is False
        assert result.output is None
        assert result.fallback_embedding == fake_vec

        err_msgs = " ".join(r.message for r in caplog.records)
        assert "启动降级" in err_msgs or any(
            "Step1.5 查询重写最终失败" in r.message for r in caplog.records
        )
        assert any(
            "降级 Embedding 生成成功" in r.message for r in caplog.records
        )


# ============ 场景3：InnerMonologue 不落库不返前端（本模块仅解析入内存） ============


class TestScenario3InnerMonologueMemoryOnly:
    @pytest.mark.asyncio
    async def test_inner_monologue_present_on_output_only(self):
        """InnerMonologue 随 QueryRewriteOutput 在内存中传递；本服务不写 DB、不调用前端。"""
        raw = _valid_step1_5_json(InnerMonologue="仅内部使用的独白")

        with patch(
            "backend.services.query_rewrite_service.llm_client.chat_sync",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            result = await execute_query_rewrite(**_base_execute_kwargs())

        assert result.success is True
        assert result.output.InnerMonologue == "仅内部使用的独白"


# ============ 边界：非法 JSON → 降级 ============


class TestBoundaryIllegalJsonFallback:
    @pytest.mark.asyncio
    async def test_illegal_json_twice_then_fallback(self):
        fake_vec = [1.0, 2.0]

        with patch(
            "backend.services.query_rewrite_service.llm_client.chat_sync",
            new_callable=AsyncMock,
            return_value="这不是合法 JSON {{{",
        ), patch(
            "backend.services.query_rewrite_service.embedding_service.get_embedding",
            new_callable=AsyncMock,
            return_value=fake_vec,
        ), patch(
            "backend.services.query_rewrite_service.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await execute_query_rewrite(**_base_execute_kwargs())

        assert result.success is False
        assert result.fallback_embedding == fake_vec


# ============ 解析与 Prompt 纯函数 ============


class TestParseQueryRewriteOutput:
    def test_parse_full_json(self):
        raw = _valid_step1_5_json()
        out = _parse_query_rewrite_output(raw)
        assert isinstance(out, QueryRewriteOutput)

    def test_all_three_questions_empty_raises(self):
        raw = json.dumps(
            {
                "InnerMonologue": "x",
                "CharacterGlobalQueryQuestion": "",
                "CharacterKnowledgeQueryQuestion": "",
                "UserProfileQueryQuestion": "",
            },
            ensure_ascii=False,
        )
        with pytest.raises(ValueError, match="三组 QueryQuestion 全部为空"):
            _parse_query_rewrite_output(raw)


class TestBuildStep15Prompt:
    def test_contains_modules_and_user_message(self):
        text = _build_step1_5_prompt(
            persona_text="人格",
            round_context=_base_round_context(),
            recent_conversations=[{"role": "user", "content": "你好"}],
            user_input="测试消息",
        )
        assert "【系统指令】" in text
        assert "【人格设定】" in text
        assert "【关系状态】" in text
        assert "【近期对话】" in text
        assert "测试消息" in text
        assert "CharacterGlobalQueryQuestion" in text
