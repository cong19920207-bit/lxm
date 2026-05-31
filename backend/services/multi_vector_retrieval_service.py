# -*- coding: utf-8 -*-
# Step2 多路向量检索服务：基于 Step1.5 输出执行 per-route 主路 + 2.5 补充路检索
# 正常路径：四路各自独立 Embedding（cp 不再复用 cg）+ key_l2 过滤主路 + 按需 Keywords 补充路
# 需求来源：R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21；C2/C7/C10/C11/C12/C34/C35/C36/C37

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

# 补充路触发阈值（C2/C7，本期写死常量）：主路 count<2 或 max_score<该值即触发补充路
SUPPLEMENT_TRIGGER_THRESHOLD = 0.75

# 补充路与合并后最终结果的 TopK（C12，写死，与热配 top_k 无关）
_SUPPLEMENT_TOP_K = 3
_MERGED_TOP_K = 3


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

    # C10 跳过的路（QueryQuestion 为「无」/空串），路名用 memory_type 常量值（C37）
    skipped_routes: list[str] = field(default_factory=list)

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


def _should_skip(question: str) -> bool:
    """C10 跳过判断：QueryQuestion 为空串或字符串「无」均视为跳过。"""
    v = (question or "").strip()
    return v == "" or v == "无"


def should_trigger_supplement(main_results: list[dict]) -> bool:
    """
    补充路触发判断（C7，行为 A）：主路命中 <2 条，或最高分 < 阈值即触发。

    仅对「未跳过且主路已执行」的路调用（C35）。
    """
    if len(main_results) < 2:
        return True
    return max(r.get("score", 0.0) for r in main_results) < SUPPLEMENT_TRIGGER_THRESHOLD


def merge_results(main: list[dict], supplement: list[dict]) -> list[dict]:
    """
    主路 + 补充路合并去重（按 id）→ score 降序 → 固定 Top3（C12/C37）。
    """
    seen: set[str] = set()
    merged: list[dict] = []
    for r in main + supplement:
        doc_id = r.get("id", "")
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            merged.append(r)
    merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return merged[:_MERGED_TOP_K]


async def _retrieve_route(
    *,
    memory_type: str,
    question: str,
    keywords: str,
    candidate_keys: list[str],
    user_id: int | None,
    top_k: int,
    threshold: float,
) -> list[dict]:
    """
    单路完整检索：主路（Question Embedding + key_l2 过滤）+ 按需补充路（C7/C11/C12/C34/C35/C36）。

    调用方须保证该路「未被 C10 跳过」（被跳过路直接 []，不进入本函数）。
    流程：
      1. 主路：Embedding(Question) → search(candidate_keys=该路 CandidateKeys, top_k=热配)
      2. 补充判断：should_trigger_supplement(主路结果) 为 True 才进入补充
      3. Keywords 空串 → 跳过补充，结果以主路为准（C11）
      4. Keywords 非空 → Embedding(Keywords) → search(candidate_keys=[], top_k=3, 阈值沿用热配 C36)
      5. 合并去重 → score 降序 → Top3 写回（C37）

    容错（PRD「Step2 某路 Embedding 失败」§异常场景）：本路任一步骤（Embedding/检索）
    抛异常时不向上抛，记录 warning 后返回 []，确保单路失败不影响其他路（C35）。
    所有返回分支统一经 merge_results 收口为最终 Top3（C12/C37），与热配 top_k 解耦。
    """
    try:
        main_emb = await embedding_service.get_embedding(question)
        if not main_emb:
            logger.warning("Step2 主路 Embedding 为空: memory_type=%s", memory_type)
            return []

        main_results = await dashvector_client.search(
            vector=main_emb,
            memory_type=memory_type,
            user_id=user_id,
            top_k=top_k,
            threshold=threshold,
            candidate_keys=candidate_keys,
        )

        # 2.5 补充路：仅在主路召回不足时触发（C7）
        if not should_trigger_supplement(main_results):
            # 不触发补充也统一收口为 Top3（C12/C37），避免热配 top_k>3 时超额
            return merge_results(main_results, [])

        kw = (keywords or "").strip()
        if not kw:
            # C11：Keywords 空串，跳过补充路，以主路为准
            return merge_results(main_results, [])

        kw_emb = await embedding_service.get_embedding(kw)
        if not kw_emb:
            logger.warning("Step2 补充路 Keywords Embedding 为空: memory_type=%s", memory_type)
            return merge_results(main_results, [])

        supplement_results = await dashvector_client.search(
            vector=kw_emb,
            memory_type=memory_type,
            user_id=user_id,
            top_k=_SUPPLEMENT_TOP_K,
            threshold=threshold,
            candidate_keys=[],  # 补充路去 key_l2 约束，范围更宽兜底（C34）
        )

        return merge_results(main_results, supplement_results)

    except Exception as e:
        # 单路失败不影响其他路（C35 / PRD 异常场景）：记录 warning 后返回 []
        logger.warning(
            "Step2 单路检索异常，按空结果处理: memory_type=%s error=%s",
            memory_type, str(e),
        )
        return []


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
    Step2 多路向量检索入口（per-route 主路 + 2.5 补充路）。

    正常路径（Step1.5 成功）：
        四路各自独立（character_private 不再复用 character_global 的 Embedding）；
        被 C10 跳过的路（QueryQuestion 为「无」/空）直接 []、记入 skipped_routes；
        未跳过路并行执行 _retrieve_route（路内：Question Embedding + key_l2 主路
        → 按需 Keywords 补充路 → 合并去重 → Top3 写回，C7/C11/C12/C34/C35/C36/C37）；
        单路异常被路内/gather 双重兜底为 []，不影响其他路。

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
        # ── 正常路径：per-route 主路 + 2.5 补充路（C10/C34/C35/C37）──
        try:
            output = query_rewrite_result.output

            # 四路定义：memory_type 常量、Question/Keywords/CandidateKeys、是否带 user_id
            # character_private 使用独立 Question，不再复用 character_global 的 Embedding
            route_defs = [
                (
                    "character_global", MEMORY_TYPE_CHARACTER_GLOBAL, None,
                    output.CharacterGlobalQueryQuestion,
                    output.CharacterGlobalQueryKeywords,
                    output.CharacterGlobalCandidateKeys,
                ),
                (
                    "character_private", MEMORY_TYPE_CHARACTER_PRIVATE, user_id,
                    output.CharacterPrivateQueryQuestion,
                    output.CharacterPrivateQueryKeywords,
                    output.CharacterPrivateCandidateKeys,
                ),
                (
                    "character_knowledge", MEMORY_TYPE_CHARACTER_KNOWLEDGE, None,
                    output.CharacterKnowledgeQueryQuestion,
                    output.CharacterKnowledgeQueryKeywords,
                    output.CharacterKnowledgeCandidateKeys,
                ),
                (
                    "user", MEMORY_TYPE_USER, user_id,
                    output.UserProfileQueryQuestion,
                    output.UserProfileQueryKeywords,
                    output.UserProfileCandidateKeys,
                ),
            ]

            # 跳过判断（C10）：跳过路不生成 Embedding、不检索，结果直接 []
            active_routes = []  # (route_key, coroutine)
            for route_key, mt, rid, question, keywords, cand_keys in route_defs:
                if _should_skip(question):
                    result.skipped_routes.append(route_key)
                    continue
                active_routes.append((
                    route_key,
                    _retrieve_route(
                        memory_type=mt,
                        question=question,
                        keywords=keywords,
                        candidate_keys=cand_keys or [],
                        user_id=rid,
                        top_k=top_k,
                        threshold=threshold,
                    ),
                ))

            # 未跳过路并行检索（每路内部「主路→按需补充」串行，路间并行）。
            # return_exceptions=True：即使某路意外抛错也不击穿其他路（C35 双保险，
            # _retrieve_route 内部已兜底，这里再防御异常协程）
            route_results: dict[str, list[dict]] = {}
            if active_routes:
                gathered = await asyncio.gather(
                    *[coro for _, coro in active_routes],
                    return_exceptions=True,
                )
                for (route_key, _), res in zip(active_routes, gathered):
                    if isinstance(res, Exception):
                        logger.warning(
                            "Step2 路检索协程异常，按空结果处理: route=%s error=%s",
                            route_key, str(res),
                        )
                        route_results[route_key] = []
                    else:
                        route_results[route_key] = res

            # 合并 Top3 写回各路对应字段（C37）；跳过路保持默认 []
            # P1（长记忆第一套下线）：user 路一律不过滤 mem_* 前缀文档，
            # 旧脏数据完全依赖 M2 人工清理（STEP-016），运行时不做任何过滤，请勿误加。
            result.character_global_results = route_results.get("character_global", [])
            result.character_private_results = route_results.get("character_private", [])
            result.character_knowledge_results = route_results.get("character_knowledge", [])
            result.user_results = route_results.get("user", [])
            # C1 四路全无属成功态：is_fallback=False（区别于 Step1.5 失败的降级态）
            result.is_fallback = False

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            total_hits = (
                len(result.character_global_results)
                + len(result.character_private_results)
                + len(result.character_knowledge_results)
                + len(result.user_results)
            )
            logger.info(
                "Step2 多路检索完成(正常): user_id=%d elapsed=%dms "
                "hits=%d(cg=%d cp=%d ck=%d u=%d) skipped=%s top_k=%d threshold=%.2f",
                user_id, elapsed_ms, total_hits,
                len(result.character_global_results),
                len(result.character_private_results),
                len(result.character_knowledge_results),
                len(result.user_results),
                result.skipped_routes, top_k, threshold,
            )
            return result

        except Exception as e:
            logger.error(
                "Step2 正常路径异常: user_id=%d error=%s",
                user_id, str(e),
            )
            # 正常路径异常≠Step1.5 降级：is_fallback 维持 False（C37 口径，
            # is_fallback=True 仅代表 Step1.5 失败的降级态）；返回已有结果
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
