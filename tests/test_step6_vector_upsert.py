# -*- coding: utf-8 -*-
# STEP-014 单元测试：Step6 四路 DashVector 向量写入

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.memory_llm_service import (
    Step6MemoryOutput,
    parse_kv_lines,
    upsert_step6_vectors,
)
from backend.utils.character_knowledge_validate import build_doc_id, hash_key

_SAMPLE_KEY = "外貌-体态-细节"
_SAMPLE_KEY2 = "兴趣-偏好-饮品"
_SAMPLE_KEY3 = "价值观-待人-方式"


class TestParseKvLines:
    def test_normal_3_lines(self):
        text = (
            f"{_SAMPLE_KEY}：说话时肩膀略绷紧\n"
            f"{_SAMPLE_KEY2}：学手冲咖啡\n"
            f"{_SAMPLE_KEY3}：先听完再反驳"
        )
        result = parse_kv_lines(text)
        assert len(result) == 3
        assert result[0] == (_SAMPLE_KEY, "说话时肩膀略绷紧")

    def test_line_without_fullwidth_colon_discarded(self):
        text = f"{_SAMPLE_KEY}：说话时肩膀略绷紧\n这行没有全角冒号\n{_SAMPLE_KEY2}：学手冲咖啡"
        result = parse_kv_lines(text)
        assert len(result) == 2


class TestUpsertStep6Vectors:
    _FAKE_VECTOR = [0.1] * 1024

    @staticmethod
    def _make_output(**overrides) -> Step6MemoryOutput:
        defaults = {
            "InnerMonologue": "",
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

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_character_public_3_lines(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = self._make_output(
            CharacterPublicSettings=(
                f"{_SAMPLE_KEY}：说话时肩膀略绷紧\n"
                f"{_SAMPLE_KEY2}：学手冲咖啡\n"
                f"{_SAMPLE_KEY3}：先听完再反驳"
            )
        )
        counts = await upsert_step6_vectors(output, user_id=1)

        assert counts["character_global"] == 3
        assert mock_dv.upsert.call_count == 3
        for call in mock_dv.upsert.call_args_list:
            doc_id = call.kwargs["doc_id"]
            assert doc_id.endswith("_0")
            assert "user_id" not in call.kwargs["fields"]
            assert call.kwargs["fields"]["stable_key"]

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_invalid_two_layer_key_skipped(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = self._make_output(
            CharacterPublicSettings="外貌-体态：两层 key 应跳过\n兴趣-偏好-饮品：合法三层"
        )
        counts = await upsert_step6_vectors(output, user_id=1)

        assert counts["character_global"] == 1
        mock_dv.upsert.assert_called_once()
        assert mock_dv.upsert.call_args.kwargs["fields"]["stable_key"] == "兴趣-偏好-饮品"

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_character_private_with_user_id(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        key = "用户-信任-试探"
        output = self._make_output(
            CharacterPrivateSettings=f"{key}：信任在下降"
        )
        counts = await upsert_step6_vectors(output, user_id=42)

        assert counts["character_private"] == 1
        kwargs = mock_dv.upsert.call_args.kwargs
        assert kwargs["doc_id"] == build_doc_id("character_private", key, 42)
        assert kwargs["fields"]["user_id"] == 42

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_same_key_overwrite_same_doc_id(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        text = f"{_SAMPLE_KEY}：旧描述"
        await upsert_step6_vectors(
            self._make_output(CharacterPublicSettings=text), user_id=1
        )
        await upsert_step6_vectors(
            self._make_output(CharacterPublicSettings=f"{_SAMPLE_KEY}：新描述"), user_id=1
        )

        ids = [c.kwargs["doc_id"] for c in mock_dv.upsert.call_args_list]
        assert ids[0] == ids[1] == build_doc_id("character_global", _SAMPLE_KEY)

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_content_and_stable_key_fields(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        output = self._make_output(
            CharacterPublicSettings=f"{_SAMPLE_KEY}：说话时肩膀略绷紧"
        )
        await upsert_step6_vectors(output, user_id=1)

        fields = mock_dv.upsert.call_args.kwargs["fields"]
        assert fields["content"] == f"{_SAMPLE_KEY}：说话时肩膀略绷紧"
        assert fields["stable_key"] == _SAMPLE_KEY

    @pytest.mark.asyncio
    @patch("backend.services.memory_llm_service.dashvector_client")
    @patch("backend.services.memory_llm_service.embedding_service")
    async def test_doc_id_uses_hash_not_raw_key(self, mock_emb, mock_dv):
        mock_emb.get_embedding = AsyncMock(return_value=self._FAKE_VECTOR)
        mock_dv.upsert = AsyncMock(return_value=True)

        await upsert_step6_vectors(
            self._make_output(CharacterPublicSettings=f"{_SAMPLE_KEY}：描述"),
            user_id=1,
        )
        doc_id = mock_dv.upsert.call_args.kwargs["doc_id"]
        assert _SAMPLE_KEY not in doc_id
        assert hash_key(_SAMPLE_KEY) in doc_id
