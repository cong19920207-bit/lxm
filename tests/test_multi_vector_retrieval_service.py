# -*- coding: utf-8 -*-
# Step2 多路向量检索服务单元测试（STEP-020）
# 场景1：正常路径 → 3 Embedding + 4 检索，合计 ≤12 条结果
# 场景2：降级路径 → 1 Embedding + 4 检索
# 场景3：某路 0 命中 → 对应结果为空列表
# 边界测试：热配 TopK=5 → 使用配置值而非默认 3

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.multi_vector_retrieval_service import (
    MultiVectorRetrievalResult,
    _DEFAULT_THRESHOLD,
    _DEFAULT_TOP_K,
    execute_multi_vector_retrieval,
)
from backend.services.query_rewrite_service import (
    QueryRewriteOutput,
    QueryRewriteResult,
)


def _make_search_result(doc_id: str, score: float, content: str) -> dict:
    """构造 DashVector search 返回的单条结果"""
    return {
        "id": doc_id,
        "score": score,
        "content": content,
        "fields": {"content": content},
    }


def _normal_query_rewrite_result() -> QueryRewriteResult:
    """Step1.5 正常成功的输出"""
    return QueryRewriteResult(
        success=True,
        output=QueryRewriteOutput(
            InnerMonologue="用户在聊熬夜",
            CharacterGlobalQueryQuestion="林小梦的作息设定是什么",
            CharacterGlobalQueryKeywords="作息 性格",
            CharacterKnowledgeQueryQuestion="熬夜对健康有什么影响",
            CharacterKnowledgeQueryKeywords="熬夜 健康",
            UserProfileQueryQuestion="用户最近提到过失眠吗",
            UserProfileQueryKeywords="失眠 压力",
        ),
    )


def _fallback_query_rewrite_result(emb: list[float] | None = None) -> QueryRewriteResult:
    """Step1.5 降级的输出"""
    return QueryRewriteResult(
        success=False,
        fallback_embedding=emb or [0.1, 0.2, 0.3],
    )


# ============ 场景1：正常路径 → 3 Embedding + 4 检索 ============


class TestScenario1NormalPath:
    @pytest.mark.asyncio
    async def test_normal_3_embeddings_4_searches_up_to_12_results(self):
        """正常路径：3 Embedding 并行 + 4 DashVector 检索并行，合计 ≤12 条"""
        fake_cg_emb = [1.0, 0.0, 0.0]
        fake_ck_emb = [0.0, 1.0, 0.0]
        fake_up_emb = [0.0, 0.0, 1.0]

        cg_hits = [_make_search_result("cg_1", 0.95, "角色设定1")]
        cp_hits = [
            _make_search_result("cp_1", 0.88, "私有设定1"),
            _make_search_result("cp_2", 0.85, "私有设定2"),
        ]
        ck_hits = [
            _make_search_result("ck_1", 0.92, "知识1"),
            _make_search_result("ck_2", 0.80, "知识2"),
            _make_search_result("ck_3", 0.75, "知识3"),
        ]
        u_hits = [
            _make_search_result("u_1", 0.90, "用户记忆1"),
            _make_search_result("u_2", 0.78, "用户记忆2"),
        ]

        async def mock_get_embedding(text: str) -> list[float]:
            if "角色" in text or "作息" in text:
                return fake_cg_emb
            if "知识" in text or "熬夜" in text:
                return fake_ck_emb
            return fake_up_emb

        call_count = {"search": 0}
        search_calls = []

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7
        ):
            call_count["search"] += 1
            search_calls.append({
                "memory_type": memory_type,
                "user_id": user_id,
                "top_k": top_k,
                "threshold": threshold,
            })
            if memory_type == "character_global":
                return cg_hits
            if memory_type == "character_private":
                return cp_hits
            if memory_type == "character_knowledge":
                return ck_hits
            if memory_type == "user":
                return u_hits
            return []

        with patch(
            "backend.services.multi_vector_retrieval_service.embedding_service.get_embedding",
            side_effect=mock_get_embedding,
        ), patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            side_effect=mock_search,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_normal_query_rewrite_result(),
                user_id=42,
            )

        assert isinstance(result, MultiVectorRetrievalResult)
        assert result.is_fallback is False
        assert len(result.character_global_results) == 1
        assert len(result.character_private_results) == 2
        assert len(result.character_knowledge_results) == 3
        assert len(result.user_results) == 2

        total = len(result.all_results)
        assert total <= 12
        assert total == 8

        assert call_count["search"] == 4

        # character_global 无 user_id
        cg_call = next(c for c in search_calls if c["memory_type"] == "character_global")
        assert cg_call["user_id"] is None

        # character_private 有 user_id
        cp_call = next(c for c in search_calls if c["memory_type"] == "character_private")
        assert cp_call["user_id"] == 42

        # character_knowledge 无 user_id
        ck_call = next(c for c in search_calls if c["memory_type"] == "character_knowledge")
        assert ck_call["user_id"] is None

        # user 有 user_id
        u_call = next(c for c in search_calls if c["memory_type"] == "user")
        assert u_call["user_id"] == 42


# ============ 场景2：降级路径 → 1 Embedding + 4 检索 ============


class TestScenario2FallbackPath:
    @pytest.mark.asyncio
    async def test_fallback_1_embedding_4_searches(self):
        """降级路径：Step1.5 失败，用单 Embedding 执行全部 4 路检索"""
        fallback_emb = [0.5, 0.5, 0.5]

        search_vectors = []

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7
        ):
            search_vectors.append(vector)
            return [_make_search_result(f"{memory_type}_1", 0.85, f"{memory_type}内容")]

        with patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            side_effect=mock_search,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_fallback_query_rewrite_result(fallback_emb),
                user_id=99,
            )

        assert result.is_fallback is True
        assert len(result.character_global_results) == 1
        assert len(result.character_private_results) == 1
        assert len(result.character_knowledge_results) == 1
        assert len(result.user_results) == 1

        # 4 次检索全部使用同一个 fallback embedding
        assert len(search_vectors) == 4
        for vec in search_vectors:
            assert vec == fallback_emb

    @pytest.mark.asyncio
    async def test_fallback_no_embedding_returns_empty(self):
        """降级路径：fallback_embedding 也为空时，返回全空结果"""
        with patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=QueryRewriteResult(
                    success=False, fallback_embedding=[]
                ),
                user_id=99,
            )

        assert result.is_fallback is True
        assert result.character_global_results == []
        assert result.character_private_results == []
        assert result.character_knowledge_results == []
        assert result.user_results == []


# ============ 场景3：某路 0 命中 → 对应结果为空列表 ============


class TestScenario3PartialHits:
    @pytest.mark.asyncio
    async def test_some_routes_zero_hits(self):
        """character_knowledge 和 user 路返回 0 命中，其余路正常"""
        fake_emb = [1.0, 2.0, 3.0]

        async def mock_get_embedding(text: str) -> list[float]:
            return fake_emb

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7
        ):
            if memory_type == "character_global":
                return [_make_search_result("cg_1", 0.90, "设定")]
            if memory_type == "character_private":
                return [_make_search_result("cp_1", 0.82, "私有")]
            # character_knowledge 和 user 路返回空
            return []

        with patch(
            "backend.services.multi_vector_retrieval_service.embedding_service.get_embedding",
            side_effect=mock_get_embedding,
        ), patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            side_effect=mock_search,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_normal_query_rewrite_result(),
                user_id=42,
            )

        assert result.is_fallback is False
        assert len(result.character_global_results) == 1
        assert len(result.character_private_results) == 1
        assert len(result.character_knowledge_results) == 0
        assert len(result.user_results) == 0

        # all_results 只有 2 条
        assert len(result.all_results) == 2


# ============ 边界测试：热配 TopK=5 → 使用配置值 ============


class TestBoundaryHotConfig:
    @pytest.mark.asyncio
    async def test_hot_config_topk_5_overrides_default(self):
        """admin_config 配置 TopK=5 和自定义阈值，检索时使用配置值"""
        fake_emb = [1.0, 2.0, 3.0]
        captured_params = []

        async def mock_get_embedding(text: str) -> list[float]:
            return fake_emb

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7
        ):
            captured_params.append({"top_k": top_k, "threshold": threshold})
            return [_make_search_result(f"{memory_type}_1", 0.90, "内容")]

        hot_config = {"top_k": 5, "threshold": 0.65}

        with patch(
            "backend.services.multi_vector_retrieval_service.embedding_service.get_embedding",
            side_effect=mock_get_embedding,
        ), patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            side_effect=mock_search,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=hot_config,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_normal_query_rewrite_result(),
                user_id=42,
            )

        assert result.top_k == 5
        assert result.threshold == 0.65

        # 4 次检索全部使用热配值
        assert len(captured_params) == 4
        for params in captured_params:
            assert params["top_k"] == 5
            assert params["threshold"] == 0.65

    @pytest.mark.asyncio
    async def test_hot_config_none_uses_defaults(self):
        """admin_config 无配置时回退默认值"""
        fake_emb = [1.0, 2.0, 3.0]
        captured_params = []

        async def mock_get_embedding(text: str) -> list[float]:
            return fake_emb

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7
        ):
            captured_params.append({"top_k": top_k, "threshold": threshold})
            return []

        with patch(
            "backend.services.multi_vector_retrieval_service.embedding_service.get_embedding",
            side_effect=mock_get_embedding,
        ), patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            side_effect=mock_search,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_normal_query_rewrite_result(),
                user_id=42,
            )

        assert result.top_k == _DEFAULT_TOP_K
        assert result.threshold == _DEFAULT_THRESHOLD

        for params in captured_params:
            assert params["top_k"] == _DEFAULT_TOP_K
            assert params["threshold"] == _DEFAULT_THRESHOLD
