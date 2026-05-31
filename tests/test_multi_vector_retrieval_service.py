# -*- coding: utf-8 -*-
# Step2 多路向量检索服务单元测试（改造后：per-route 主路 + 2.5 补充路）
# 场景1：正常路径 → 四路各自独立 Embedding（cp 不复用 cg）+ 主路 candidate_keys 透传
# 场景2：降级路径 → 1 Embedding + 4 检索（不加 key_l2）
# 场景3：某路 0 命中 → 对应结果为空列表
# 冒烟用例3（C23）：四路全「无」→ skipped_routes 含四路、0 次 search、is_fallback=False
# 补充路：主路命中不足触发 Keywords 补充（candidate_keys=[]）
# 边界：热配 TopK=5

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
    """Step1.5 正常成功的 13 字段输出，四路均有 Question（cp 独立一组）。"""
    return QueryRewriteResult(
        success=True,
        output=QueryRewriteOutput(
            InnerMonologue="用户在聊熬夜",
            CharacterGlobalQueryQuestion="林小梦的作息设定是什么",
            CharacterGlobalQueryKeywords="作息 性格",
            CharacterGlobalCandidateKeys=["性格-特征"],
            CharacterPrivateQueryQuestion="林小梦对用户的态度倾向",
            CharacterPrivateQueryKeywords="态度 信任",
            CharacterPrivateCandidateKeys=["用户-信任"],
            CharacterKnowledgeQueryQuestion="熬夜对健康有什么影响",
            CharacterKnowledgeQueryKeywords="熬夜 健康",
            CharacterKnowledgeCandidateKeys=["心理-情绪"],
            UserProfileQueryQuestion="用户最近提到过失眠吗",
            UserProfileQueryKeywords="失眠 压力",
            UserProfileCandidateKeys=["习惯-作息"],
        ),
    )


def _all_none_query_rewrite_result() -> QueryRewriteResult:
    """C1：四路 QueryQuestion 全为「无」/空串的合法成功态。"""
    return QueryRewriteResult(
        success=True,
        output=QueryRewriteOutput(
            InnerMonologue="纯情绪",
            CharacterGlobalQueryQuestion="无",
            CharacterPrivateQueryQuestion="无",
            CharacterKnowledgeQueryQuestion="",
            UserProfileQueryQuestion="无",
        ),
    )


def _fallback_query_rewrite_result(emb: list[float] | None = None) -> QueryRewriteResult:
    """Step1.5 降级的输出"""
    return QueryRewriteResult(
        success=False,
        fallback_embedding=emb or [0.1, 0.2, 0.3],
    )


# 四路按 Question 文本返回不同 Embedding，用于验证 cp 独立、不复用 cg
def _route_embedding(text: str) -> list[float]:
    if "作息设定" in text or "作息" in text:
        return [1.0, 0.0, 0.0, 0.0]
    if "态度" in text or "信任" in text:
        return [0.0, 1.0, 0.0, 0.0]
    if "健康" in text or "熬夜" in text:
        return [0.0, 0.0, 1.0, 0.0]
    return [0.0, 0.0, 0.0, 1.0]


# ============ 场景1：正常路径 → 四路独立 Embedding + candidate_keys 透传 ============


class TestScenario1NormalPath:
    @pytest.mark.asyncio
    async def test_four_routes_independent_embedding_and_candidate_keys(self):
        """四路均活跃，各返回 2 条高分（不触发补充）；cp 独立 Embedding；主路透传 candidate_keys。"""
        emb_calls = []
        search_calls = []

        async def mock_get_embedding(text: str) -> list[float]:
            emb_calls.append(text)
            return _route_embedding(text)

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            search_calls.append({
                "memory_type": memory_type,
                "user_id": user_id,
                "vector": vector,
                "candidate_keys": candidate_keys,
            })
            return [
                _make_search_result(f"{memory_type}_1", 0.95, f"{memory_type}内容1"),
                _make_search_result(f"{memory_type}_2", 0.85, f"{memory_type}内容2"),
            ]

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
        assert result.skipped_routes == []
        assert len(result.character_global_results) == 2
        assert len(result.character_private_results) == 2
        assert len(result.character_knowledge_results) == 2
        assert len(result.user_results) == 2

        # 高分且 ≥2 条，不触发补充 → 恰好 4 次主路 search
        assert len(search_calls) == 4

        # character_global 无 user_id；character_private/user 有 user_id
        cg_call = next(c for c in search_calls if c["memory_type"] == "character_global")
        cp_call = next(c for c in search_calls if c["memory_type"] == "character_private")
        ck_call = next(c for c in search_calls if c["memory_type"] == "character_knowledge")
        u_call = next(c for c in search_calls if c["memory_type"] == "user")
        assert cg_call["user_id"] is None
        assert cp_call["user_id"] == 42
        assert ck_call["user_id"] is None
        assert u_call["user_id"] == 42

        # cp 独立 Embedding：与 cg 向量不同（不再复用）
        assert cp_call["vector"] != cg_call["vector"]

        # 主路透传各路 candidate_keys
        assert cg_call["candidate_keys"] == ["性格-特征"]
        assert cp_call["candidate_keys"] == ["用户-信任"]
        assert u_call["candidate_keys"] == ["习惯-作息"]


# ============ 场景2：降级路径 → 1 Embedding + 4 检索 ============


class TestScenario2FallbackPath:
    @pytest.mark.asyncio
    async def test_fallback_1_embedding_4_searches(self):
        """降级路径：Step1.5 失败，用单 Embedding 执行全部 4 路检索（不加 key_l2）。"""
        fallback_emb = [0.5, 0.5, 0.5]

        search_vectors = []
        candidate_keys_seen = []

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            search_vectors.append(vector)
            candidate_keys_seen.append(candidate_keys)
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

        # 4 次检索全部使用同一个 fallback embedding，且不加 key_l2（candidate_keys 为空）
        assert len(search_vectors) == 4
        for vec in search_vectors:
            assert vec == fallback_emb
        for ck in candidate_keys_seen:
            assert ck == []

    @pytest.mark.asyncio
    async def test_fallback_no_embedding_returns_empty(self):
        """降级路径：fallback_embedding 也为空时，返回全空结果。"""
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
        """character_knowledge / user 路返回 0 命中（Keywords 也置空避免补充），其余路正常。"""
        # 把 ck/up 两路 Keywords 置空，触发补充时直接以主路（空）为准（C11）
        qr = _normal_query_rewrite_result()
        qr.output.CharacterKnowledgeQueryKeywords = ""
        qr.output.UserProfileQueryKeywords = ""

        async def mock_get_embedding(text: str) -> list[float]:
            return _route_embedding(text)

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            if memory_type == "character_global":
                return [
                    _make_search_result("cg_1", 0.90, "设定1"),
                    _make_search_result("cg_2", 0.86, "设定2"),
                ]
            if memory_type == "character_private":
                return [
                    _make_search_result("cp_1", 0.82, "私有1"),
                    _make_search_result("cp_2", 0.80, "私有2"),
                ]
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
                query_rewrite_result=qr,
                user_id=42,
            )

        assert result.is_fallback is False
        assert len(result.character_global_results) == 2
        assert len(result.character_private_results) == 2
        assert len(result.character_knowledge_results) == 0
        assert len(result.user_results) == 0
        assert len(result.all_results) == 4


# ============ 冒烟用例3（C23）：四路全「无」→ 跳过、0 次 search、成功态 ============


class TestSmokeAllRoutesSkipped:
    @pytest.mark.asyncio
    async def test_all_routes_none_skipped_no_search(self):
        search_mock = AsyncMock()
        embedding_mock = AsyncMock()

        with patch(
            "backend.services.multi_vector_retrieval_service.embedding_service.get_embedding",
            embedding_mock,
        ), patch(
            "backend.services.multi_vector_retrieval_service.dashvector_client.search",
            search_mock,
        ), patch(
            "backend.services.multi_vector_retrieval_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_multi_vector_retrieval(
                query_rewrite_result=_all_none_query_rewrite_result(),
                user_id=7,
            )

        # 四路全跳过：路名用 memory_type 常量值（C37）
        assert set(result.skipped_routes) == {
            "character_global",
            "character_private",
            "character_knowledge",
            "user",
        }
        assert result.character_global_results == []
        assert result.character_private_results == []
        assert result.character_knowledge_results == []
        assert result.user_results == []
        # 零次 DashVector 调用、零次 Embedding
        assert search_mock.await_count == 0
        assert embedding_mock.await_count == 0
        # C1 成功态，不是降级
        assert result.is_fallback is False


# ============ 补充路：主路命中不足触发 Keywords 补充 ============


class TestSupplementRoute:
    @pytest.mark.asyncio
    async def test_supplement_triggered_when_main_insufficient(self):
        """user 路主路仅 1 条 → 触发补充：Keywords Embedding + candidate_keys=[] 二次 search。"""
        # 仅 user 路活跃，其余三路置「无」
        qr = QueryRewriteResult(
            success=True,
            output=QueryRewriteOutput(
                CharacterGlobalQueryQuestion="无",
                CharacterPrivateQueryQuestion="无",
                CharacterKnowledgeQueryQuestion="无",
                UserProfileQueryQuestion="用户最近提到过失眠吗",
                UserProfileQueryKeywords="失眠 压力",
                UserProfileCandidateKeys=["习惯-作息"],
            ),
        )

        emb_texts = []
        search_calls = []

        async def mock_get_embedding(text: str) -> list[float]:
            emb_texts.append(text)
            return [1.0, 2.0, 3.0]

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            search_calls.append({
                "candidate_keys": candidate_keys,
                "top_k": top_k,
            })
            if len(search_calls) == 1:
                # 主路：仅 1 条低分 → count<2 触发补充
                return [_make_search_result("u_main", 0.72, "主路命中")]
            # 补充路
            return [_make_search_result("u_supp", 0.71, "补充命中")]

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
                query_rewrite_result=qr,
                user_id=42,
            )

        # 主路 + 补充路两次 search
        assert len(search_calls) == 2
        # 主路带 candidate_keys，补充路 candidate_keys=[] 且 top_k=3
        assert search_calls[0]["candidate_keys"] == ["习惯-作息"]
        assert search_calls[1]["candidate_keys"] == []
        assert search_calls[1]["top_k"] == 3
        # 两次 Embedding：Question + Keywords
        assert "用户最近提到过失眠吗" in emb_texts
        assert "失眠 压力" in emb_texts
        # 合并去重后 user 路含主路 + 补充路命中
        ids = {r["id"] for r in result.user_results}
        assert ids == {"u_main", "u_supp"}

    @pytest.mark.asyncio
    async def test_supplement_skipped_when_keywords_empty(self):
        """主路不足但 Keywords 为空 → 跳过补充路，结果以主路为准（C11）。"""
        qr = QueryRewriteResult(
            success=True,
            output=QueryRewriteOutput(
                CharacterGlobalQueryQuestion="无",
                CharacterPrivateQueryQuestion="无",
                CharacterKnowledgeQueryQuestion="无",
                UserProfileQueryQuestion="用户最近提到过失眠吗",
                UserProfileQueryKeywords="",
                UserProfileCandidateKeys=["习惯-作息"],
            ),
        )

        search_count = {"n": 0}

        async def mock_get_embedding(text: str) -> list[float]:
            return [1.0, 2.0, 3.0]

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            search_count["n"] += 1
            return [_make_search_result("u_main", 0.5, "主路")]

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
                query_rewrite_result=qr,
                user_id=42,
            )

        # 仅 1 次主路 search，补充路被跳过
        assert search_count["n"] == 1
        assert len(result.user_results) == 1


# ============ 边界测试：热配 TopK=5 → 使用配置值 ============


class TestBoundaryHotConfig:
    @pytest.mark.asyncio
    async def test_hot_config_topk_5_overrides_default(self):
        """admin_config 配置 TopK=5 和自定义阈值，主路检索时使用配置值。"""
        captured_params = []

        async def mock_get_embedding(text: str) -> list[float]:
            return _route_embedding(text)

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            captured_params.append({"top_k": top_k, "threshold": threshold})
            # ≥2 条高分，避免触发补充
            return [
                _make_search_result(f"{memory_type}_1", 0.90, "内容1"),
                _make_search_result(f"{memory_type}_2", 0.88, "内容2"),
            ]

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

        # 4 次主路检索全部使用热配值
        assert len(captured_params) == 4
        for params in captured_params:
            assert params["top_k"] == 5
            assert params["threshold"] == 0.65

    @pytest.mark.asyncio
    async def test_hot_config_none_uses_defaults(self):
        """admin_config 无配置时回退默认值。"""
        captured_params = []

        async def mock_get_embedding(text: str) -> list[float]:
            return _route_embedding(text)

        async def mock_search(
            vector, memory_type, user_id=None, top_k=3, threshold=0.7,
            candidate_keys=[],
        ):
            captured_params.append({"top_k": top_k, "threshold": threshold})
            return [
                _make_search_result(f"{memory_type}_1", 0.90, "内容1"),
                _make_search_result(f"{memory_type}_2", 0.88, "内容2"),
            ]

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
