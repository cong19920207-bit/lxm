# -*- coding: utf-8 -*-
# STEP-014 单元测试：Step6 四路 DashVector 向量写入

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.memory_llm_service import (
    Step6MemoryOutput,
    _build_doc_id,
    parse_kv_lines,
    upsert_step6_vectors,
)


# ============ parse_kv_lines 测试 ============


class TestParseKvLines:
    """全角冒号分割行解析"""

    def test_normal_3_lines(self):
        """3 行合法 key：value → 返回 3 条"""
        text = "外貌-体态：说话时肩膀略绷紧\n兴趣-偏好：学手冲咖啡\n价值观-待人：先听完再反驳"
        result = parse_kv_lines(text)
        assert len(result) == 3
        assert result[0] == ("外貌-体态", "说话时肩膀略绷紧")
        assert result[1] == ("兴趣-偏好", "学手冲咖啡")
        assert result[2] == ("价值观-待人", "先听完再反驳")

    def test_line_without_fullwidth_colon_discarded(self):
        """无全角冒号的行 → 丢弃，其余正常"""
        text = "外貌-体态：说话时肩膀略绷紧\n这行没有全角冒号\n兴趣-偏好：学手冲咖啡"
        result = parse_kv_lines(text)
        assert len(result) == 2
        assert result[0] == ("外貌-体态", "说话时肩膀略绷紧")
        assert result[1] == ("兴趣-偏好", "学手冲咖啡")

    def test_empty_string(self):
        """空字符串 → 空列表"""
        assert parse_kv_lines("") == []

    def test_only_invalid_lines(self):
        """全部行都无全角冒号 → 空列表"""
        text = "没有冒号1\n没有冒号2\nhalf:colon"
        assert parse_kv_lines(text) == []

    def test_empty_key_discarded(self):
        """全角冒号前无 key → 丢弃"""
        text = "：空key值\n外貌-体态：正常值"
        result = parse_kv_lines(text)
        assert len(result) == 1
        assert result[0] == ("外貌-体态", "正常值")

    def test_empty_value_discarded(self):
        """全角冒号后无 value → 丢弃"""
        text = "空value：\n外貌-体态：正常值"
        result = parse_kv_lines(text)
        assert len(result) == 1
        assert result[0] == ("外貌-体态", "正常值")

    def test_value_with_multiple_fullwidth_colons(self):
        """value 中包含全角冒号 → 仅按首处分割"""
        text = "测试key：值部分：含冒号：多个"
        result = parse_kv_lines(text)
        assert len(result) == 1
        assert result[0] == ("测试key", "值部分：含冒号：多个")

    def test_blank_lines_skipped(self):
        """空行跳过"""
        text = "key1：value1\n\n\nkey2：value2\n  \nkey3：value3"
        result = parse_kv_lines(text)
        assert len(result) == 3

    def test_whitespace_trimmed(self):
        """key/value 前后空白被去除"""
        text = "  外貌-体态  ：  说话时肩膀略绷紧  "
        result = parse_kv_lines(text)
        assert result[0] == ("外貌-体态", "说话时肩膀略绷紧")


# ============ _build_doc_id 测试 ============


class TestBuildDocId:
    def test_with_user_id(self):
        doc_id = _build_doc_id("character_private", "用户-信任", 42)
        assert doc_id == "character_private:用户-信任:42"

    def test_without_user_id(self):
        doc_id = _build_doc_id("character_global", "外貌-体态", None)
        assert doc_id == "character_global:外貌-体态:"


# ============ upsert_step6_vectors 测试 ============


def _make_output(**overrides) -> Step6MemoryOutput:
    """构造 Step6MemoryOutput 实例"""
    defaults = {
        "InnerMonologue": "测试内心独白",
        "CharacterPublicSettings": "无",
        "CharacterPrivateSettings": "无",
        "CharacterKnowledges": "无",
        "UserSettings": "无",
        "UserRealName": "无",
        "UserHobbyName": "无",
        "UserDescription": "无",
        "CharacterPurpose": "无",
        "CharacterAttitude": "无",
        "RelationDescription": "无",
    }
    defaults.update(overrides)
    return Step6MemoryOutput(**defaults)


# 固定的 mock 向量
_FAKE_VECTOR = [0.1] * 1024


@pytest.mark.asyncio
class TestUpsertStep6Vectors:
    """四路向量写入集成测试（mock embedding + dashvector）"""

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_character_public_3_lines(self, mock_emb, mock_dv):
        """场景1：CharacterPublicSettings 含 3 行合法 key：value → 写入 3 条 character_global"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(
            CharacterPublicSettings="外貌-体态：说话时肩膀略绷紧\n兴趣-偏好：学手冲咖啡\n价值观-待人：先听完再反驳"
        )
        counts = await upsert_step6_vectors(output, user_id=1)

        assert counts["character_global"] == 3
        assert mock_dv.upsert.call_count == 3

        # 验证 doc_id 不含 user_id（character_global 不携带）
        for call in mock_dv.upsert.call_args_list:
            doc_id = call.kwargs.get("doc_id") or call[1].get("doc_id") or call[0][0] if call[0] else call.kwargs["doc_id"]
            assert doc_id.endswith(":")  # 无 user_id 部分
            assert "user_id" not in (call.kwargs.get("fields") or call[1].get("fields", {}))

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_character_private_2_lines_with_user_id(self, mock_emb, mock_dv):
        """场景2：CharacterPrivateSettings 含 2 行 → 写入 2 条 character_private，均带 user_id"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(
            CharacterPrivateSettings="用户-信任试探：信任在下降\n策略-回复：故意放慢半拍"
        )
        counts = await upsert_step6_vectors(output, user_id=42)

        assert counts["character_private"] == 2
        assert mock_dv.upsert.call_count == 2

        # 验证 doc_id 和 fields 都包含 user_id
        for call in mock_dv.upsert.call_args_list:
            kwargs = call.kwargs
            assert ":42" in kwargs["doc_id"]
            assert kwargs["fields"]["user_id"] == 42

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_field_value_wu_skipped(self, mock_emb, mock_dv):
        """场景3：某字段值为「无」→ 跳过整路写入"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output()  # 全部默认「无」
        counts = await upsert_step6_vectors(output, user_id=1)

        assert counts["character_global"] == 0
        assert counts["character_private"] == 0
        assert counts["character_knowledge"] == 0
        assert counts["user"] == 0
        mock_dv.upsert.assert_not_called()

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_invalid_line_discarded_rest_ok(self, mock_emb, mock_dv):
        """场景4：某行缺全角冒号 → 该行丢弃，其余正常写入"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(
            UserSettings="作息-惯性：经常熬夜\n这行没有全角冒号会被丢弃\n沟通-偏好：喜欢反问"
        )
        counts = await upsert_step6_vectors(output, user_id=10)

        assert counts["user"] == 2
        assert mock_dv.upsert.call_count == 2

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_same_key_overwrite(self, mock_emb, mock_dv):
        """边界测试：同 key 第二轮写入 → 覆盖旧向量（upsert 语义）"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        # 第一轮
        output1 = _make_output(CharacterPublicSettings="外貌-体态：旧描述")
        await upsert_step6_vectors(output1, user_id=1)

        # 第二轮 —— 同 key 新 value
        output2 = _make_output(CharacterPublicSettings="外貌-体态：新描述")
        await upsert_step6_vectors(output2, user_id=1)

        # 两轮各调一次，总共 2 次 upsert，doc_id 相同
        assert mock_dv.upsert.call_count == 2
        first_doc_id = mock_dv.upsert.call_args_list[0].kwargs["doc_id"]
        second_doc_id = mock_dv.upsert.call_args_list[1].kwargs["doc_id"]
        assert first_doc_id == second_doc_id == "character_global:外貌-体态:"

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_all_4_types_mixed(self, mock_emb, mock_dv):
        """四路同时有数据 → 各自写入正确数量"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(
            CharacterPublicSettings="外貌-体态：绷紧\n兴趣-偏好：咖啡",
            CharacterPrivateSettings="用户-信任：下降",
            CharacterKnowledges="咖啡-萃取：闷蒸30秒\n职场-边界：缓冲话术\n编程-Python：异步编程",
            UserSettings="作息-惯性：熬夜",
        )
        counts = await upsert_step6_vectors(output, user_id=5)

        assert counts["character_global"] == 2
        assert counts["character_private"] == 1
        assert counts["character_knowledge"] == 3
        assert counts["user"] == 1
        assert mock_dv.upsert.call_count == 7

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_user_settings_has_user_id(self, mock_emb, mock_dv):
        """UserSettings 写入必须携带 user_id"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(UserSettings="作息-惯性：经常熬夜")
        await upsert_step6_vectors(output, user_id=99)

        kwargs = mock_dv.upsert.call_args_list[0].kwargs
        assert kwargs["fields"]["user_id"] == 99
        assert ":99" in kwargs["doc_id"]
        assert kwargs["memory_type"] == "user"

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_character_knowledge_no_user_id(self, mock_emb, mock_dv):
        """CharacterKnowledges 写入不携带 user_id"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(CharacterKnowledges="咖啡-萃取：闷蒸30秒")
        await upsert_step6_vectors(output, user_id=1)

        kwargs = mock_dv.upsert.call_args_list[0].kwargs
        assert "user_id" not in kwargs["fields"]
        assert kwargs["doc_id"].endswith(":")
        assert kwargs["memory_type"] == "character_knowledge"

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_embedding_failure_skips_line(self, mock_emb, mock_dv):
        """embedding 异常 → 跳过该行，不影响其他行"""
        call_count = 0

        async def _side_effect(text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Embedding API 超时")
            return _FAKE_VECTOR

        mock_emb.get_embedding = AsyncMock(side_effect=_side_effect)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(
            CharacterPublicSettings="外貌-体态：绷紧\n兴趣-偏好：咖啡"
        )
        counts = await upsert_step6_vectors(output, user_id=1)

        # 第一行 embedding 失败跳过，第二行成功
        assert counts["character_global"] == 1
        assert mock_dv.upsert.call_count == 1

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_upsert_failure_counted_as_zero(self, mock_emb, mock_dv):
        """dashvector upsert 返回 False → 不计入写入成功数"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=False)

        output = _make_output(CharacterPublicSettings="外貌-体态：绷紧")
        counts = await upsert_step6_vectors(output, user_id=1)

        assert counts["character_global"] == 0
        mock_dv.upsert.assert_called_once()

    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_content_field_format(self, mock_emb, mock_dv):
        """写入 DashVector 的 content 字段格式为「key：value」"""
        mock_emb.get_embedding = AsyncMock(return_value=_FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = _make_output(CharacterPublicSettings="外貌-体态：说话时肩膀略绷紧")
        await upsert_step6_vectors(output, user_id=1)

        kwargs = mock_dv.upsert.call_args_list[0].kwargs
        assert kwargs["fields"]["content"] == "外貌-体态：说话时肩膀略绷紧"


# 支持直接运行
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
