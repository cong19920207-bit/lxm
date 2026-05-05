# -*- coding: utf-8 -*-
# Step2 多路向量检索服务：基于 Step1.5 输出执行 3 Embedding + 4 DashVector 并行检索
# 需求来源：R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21

import asyncio
import logging
import time
from dataclasses import dataclass, field

from backend.constants import (
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
    MEMORY_TYPE_CHARACTER_PRIVATE,
    MEMORY_TYPE_USER,
)
from backend.services.admin_config_service import admin_config_service
from backend.services.embedding_service import embedding_service
from backend.services.query_rewrite_service import QueryRewriteResult
from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)

# 热配置 config_key（R-L1L3-17）
_VECTOR_RETRIEVAL_CONFIG_KEY = "vector_retrieval_config"

# 热配置默认值
_DEFAULT_TOP_K = 3
_DEFAULT_THRESHOLD = 0.7


@dataclass
class MultiVectorRetrievalResult:
    """Step2 多路检索结果，供 Step3 Prompt 拼装消费"""

    # 四路检索原始结果（每条: {"id": str, "score": float, "content": str, "fields": dict}）
    character_global_results: list[dict] = field(default_factory=list)
    character_private_results: list[dict] = field(default_factory=list)
    character_knowledge_results: list[dict] = field(default_factory=list)
    user_results: list[dict] = field(default_factory=list)

    # 使用的配置值（供调试日志）
    top_k: int = _DEFAULT_TOP_K
    threshold: float = _DEFAULT_THRESHOLD

    # 是否走了降级路径
    is_fallback: bool = False

    @property
    def all_results(self) -> list[dict]:
        """四路结果合并（去重按 id），保留 score 排序"""
        seen = set()
        merged = []
        for item in (
            self.character_global_results
            + self.character_private_results
            + self.character_knowledge_results
            + self.user_results
        ):
            doc_id = item.get("id", "")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                merged.append(item)
        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return merged

    @property
    def user_memory_results(self) -> list[dict]:
        """兼容旧 memories_raw 格式，供后置任务 memory_injected 使用"""
        return self.user_results

    def format_for_prompt(self) -> dict[str, list[dict]]:
        """格式化为可插入 Prompt 的分路结构"""
        return {
            "character_global": self.character_global_results,
            "character_private": self.character_private_results,
            "character_knowledge": self.character_knowledge_results,
            "user": self.user_results,
        }


async def _load_retrieval_config() -> tuple[int, float]:
    """
    从 admin_config 热加载 TopK 和阈值（R-L1L3-17）。

    config_key = "vector_retrieval_config"
    期望 JSON 格式: {"top_k": 3, "threshold": 0.7}
    无配置或解析失败时回退默认值。
    """
    try:
        config = await admin_config_service.get_active_config(
            _VECTOR_RETRIEVAL_CONFIG_KEY
        )
        if config and isinstance(config, dict):
            top_k = int(config.get("top_k", _DEFAULT_TOP_K))
            threshold = float(config.get("threshold", _DEFAULT_THRESHOLD))
            if top_k < 1:
                top_k = _DEFAULT_TOP_K
            if not (0.0 <= threshold <= 1.0):
                threshold = _DEFAULT_THRESHOLD
            return top_k, threshold
    except Exception as e:
        logger.warning("加载向量召回配置失败，使用默认值: %s", str(e))

    return _DEFAULT_TOP_K, _DEFAULT_THRESHOLD


async def _phase1_generate_embeddings(
    query_rewrite_result: QueryRewriteResult,
) -> tuple[list[float], list[float], list[float]]:
    """
    阶段① asyncio.gather 并行生成 3 个 Embedding（R-L1L3-18）。

    CharacterGlobal / CharacterKnowledge / UserProfile 各一个。
    返回 (cg_embedding, ck_embedding, up_embedding)。
    """
    output = query_rewrite_result.output
    cg_text = output.CharacterGlobalQueryQuestion
    ck_text = output.CharacterKnowledgeQueryQuestion
    up_text = output.UserProfileQueryQuestion

    cg_emb, ck_emb, up_emb = await asyncio.gather(
        embedding_service.get_embedding(cg_text),
        embedding_service.get_embedding(ck_text),
        embedding_service.get_embedding(up_text),
    )

    return cg_emb, ck_emb, up_emb


async def _phase2_parallel_search(
    cg_emb: list[float],
    ck_emb: list[float],
    up_emb: list[float],
    user_id: int,
    top_k: int,
    threshold: float,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    阶段② asyncio.gather 并行执行 4 次 DashVector 检索（R-L1L3-10 / R-L1L3-18）。

    - character_global：CharacterGlobal Embedding，无 user_id
    - character_private：CharacterGlobal Embedding，有 user_id（R-L1L3-10 复用）
    - character_knowledge：CharacterKnowledge Embedding，无 user_id
    - user：UserProfile Embedding，有 user_id
    """
    cg_results, cp_results, ck_results, u_results = await asyncio.gather(
        dashvector_client.search(
            vector=cg_emb,
            memory_type=MEMORY_TYPE_CHARACTER_GLOBAL,
            user_id=None,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=cg_emb,
            memory_type=MEMORY_TYPE_CHARACTER_PRIVATE,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=ck_emb,
            memory_type=MEMORY_TYPE_CHARACTER_KNOWLEDGE,
            user_id=None,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=up_emb,
            memory_type=MEMORY_TYPE_USER,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        ),
    )

    return cg_results, cp_results, ck_results, u_results


async def _fallback_search(
    fallback_emb: list[float],
    user_id: int,
    top_k: int,
    threshold: float,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    降级路径：用单 Embedding 执行全部 4 路检索（R-L1L3-12）。

    过滤条件不变（character_global 无 user_id，character_private/user 有 user_id）。
    """
    cg_results, cp_results, ck_results, u_results = await asyncio.gather(
        dashvector_client.search(
            vector=fallback_emb,
            memory_type=MEMORY_TYPE_CHARACTER_GLOBAL,
            user_id=None,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=fallback_emb,
            memory_type=MEMORY_TYPE_CHARACTER_PRIVATE,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=fallback_emb,
            memory_type=MEMORY_TYPE_CHARACTER_KNOWLEDGE,
            user_id=None,
            top_k=top_k,
            threshold=threshold,
        ),
        dashvector_client.search(
            vector=fallback_emb,
            memory_type=MEMORY_TYPE_USER,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
        ),
    )

    return cg_results, cp_results, ck_results, u_results


async def execute_multi_vector_retrieval(
    query_rewrite_result: QueryRewriteResult,
    user_id: int,
) -> MultiVectorRetrievalResult:
    """
    Step2 多路向量检索入口。

    正常路径（Step1.5 成功）：
        阶段① asyncio.gather 并行 3 Embedding
        阶段② asyncio.gather 并行 4 DashVector 检索
        CharacterGlobal Embedding 复用于 character_global + character_private

    降级路径（Step1.5 失败）：
        用 fallback_embedding 执行全部 4 路检索（R-L1L3-12）

    Args:
        query_rewrite_result: Step1.5 输出
        user_id: 用户 ID

    Returns:
        MultiVectorRetrievalResult 四路检索结果
    """
    start_time = time.monotonic()

    # 热加载 TopK 和阈值（R-L1L3-17）
    top_k, threshold = await _load_retrieval_config()

    result = MultiVectorRetrievalResult(
        top_k=top_k,
        threshold=threshold,
    )

    if query_rewrite_result.success and query_rewrite_result.output:
        # ── 正常路径：3 Embedding + 4 检索 ──
        try:
            # 阶段① 并行生成 3 个 Embedding
            cg_emb, ck_emb, up_emb = await _phase1_generate_embeddings(
                query_rewrite_result
            )

            # 任一 Embedding 为空时记录警告，但继续执行非空路
            empty_routes = []
            if not cg_emb:
                empty_routes.append("CharacterGlobal")
            if not ck_emb:
                empty_routes.append("CharacterKnowledge")
            if not up_emb:
                empty_routes.append("UserProfile")
            if empty_routes:
                logger.warning(
                    "Step2 部分 Embedding 为空: user_id=%d routes=%s",
                    user_id, empty_routes,
                )

            # 阶段② 并行执行 4 次检索
            cg_results, cp_results, ck_results, u_results = (
                await _phase2_parallel_search(
                    cg_emb=cg_emb or [],
                    ck_emb=ck_emb or [],
                    up_emb=up_emb or [],
                    user_id=user_id,
                    top_k=top_k,
                    threshold=threshold,
                )
            )

            result.character_global_results = cg_results
            result.character_private_results = cp_results
            result.character_knowledge_results = ck_results
            result.user_results = u_results
            result.is_fallback = False

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            total_hits = (
                len(cg_results) + len(cp_results)
                + len(ck_results) + len(u_results)
            )
            logger.info(
                "Step2 多路检索完成(正常): user_id=%d elapsed=%dms "
                "hits=%d(cg=%d cp=%d ck=%d u=%d) top_k=%d threshold=%.2f",
                user_id, elapsed_ms, total_hits,
                len(cg_results), len(cp_results),
                len(ck_results), len(u_results),
                top_k, threshold,
            )
            return result

        except Exception as e:
            logger.error(
                "Step2 正常路径异常，尝试降级: user_id=%d error=%s",
                user_id, str(e),
            )
            # 正常路径失败时无法自动降级（无 fallback_embedding），返回空结果
            result.is_fallback = True
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "Step2 正常路径失败且无降级 Embedding: "
                "user_id=%d elapsed=%dms",
                user_id, elapsed_ms,
            )
            return result

    else:
        # ── 降级路径：1 Embedding → 4 检索（R-L1L3-12）──
        result.is_fallback = True
        fallback_emb = query_rewrite_result.fallback_embedding

        if not fallback_emb:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "Step2 降级路径无可用 Embedding: user_id=%d elapsed=%dms",
                user_id, elapsed_ms,
            )
            return result

        try:
            cg_results, cp_results, ck_results, u_results = (
                await _fallback_search(
                    fallback_emb=fallback_emb,
                    user_id=user_id,
                    top_k=top_k,
                    threshold=threshold,
                )
            )

            result.character_global_results = cg_results
            result.character_private_results = cp_results
            result.character_knowledge_results = ck_results
            result.user_results = u_results

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            total_hits = (
                len(cg_results) + len(cp_results)
                + len(ck_results) + len(u_results)
            )
            logger.info(
                "Step2 多路检索完成(降级): user_id=%d elapsed=%dms "
                "hits=%d(cg=%d cp=%d ck=%d u=%d) top_k=%d threshold=%.2f",
                user_id, elapsed_ms, total_hits,
                len(cg_results), len(cp_results),
                len(ck_results), len(u_results),
                top_k, threshold,
            )
            return result

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "Step2 降级路径检索失败: user_id=%d elapsed=%dms error=%s",
                user_id, elapsed_ms, str(e),
            )
            return result
