#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示：用户一句话 → Step1.5（打印真实拼装 Prompt）→ Step2（打印三路检索问句 + 模拟召回）
→ Step3（真实 build_chat_prompt，已 mock Redis/admin_config，不连外网）。

说明：
- Step1.5 的「JSON 出参」与 Step2 的「向量命中」在无密钥环境下只能模拟；
- Step3 使用仓库内 PromptBuilder.build_chat_prompt，输出为真实拼装逻辑结果。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.multi_vector_retrieval_service import MultiVectorRetrievalResult
from backend.services.prompt_builder import MODULE_SEPARATOR, PromptBuilder
from backend.services.query_rewrite_service import (
    QueryRewriteOutput,
    QueryRewriteResult,
    _build_step1_5_prompt,
)


# 模拟用户本轮打包后的输入（与 chat.py 里 bundled 一致：可多单行合并）
USER_ONE_LINE = "今晚又失眠了，脑子停不下来。"

# 极简人格片段（仅用于演示 Step1.5 Prompt 长度；真实链路读 Redis persona）
PERSONA_STUB = "（演示用精简人格）温柔细腻、共情强，语言短句口语化。"


def _round_context_demo() -> dict:
    return {
        "time_description": "现在是周五晚上22点30分",
        "activity_description": "",
        "relation_description": "用户常熬夜加班，最近情绪略焦虑",
        "user_real_name": "无",
        "user_hobby_name": "小梦",
        "user_description": "喜欢听用户吐槽工作压力",
        "character_purpose": "",
        "character_attitude": "",
        "level": 1,
        "level_name": "朋友",
        "silence_days": 0,
    }


def _mock_step15_output() -> QueryRewriteOutput:
    """
    模拟 Step1.5 LLM 返回的 7 字段（与真实 JSON 结构一致）。
    数值/措辞为演示用，非线上模型真实输出。
    """
    return QueryRewriteOutput(
        InnerMonologue="用户又在说失眠，先接住情绪，别急着给建议。",
        CharacterGlobalQueryQuestion="林小梦如何温柔陪伴失眠、焦虑的用户？",
        CharacterGlobalQueryKeywords="失眠,陪伴,焦虑",
        CharacterKnowledgeQueryQuestion="角色设定里关于睡眠、熬夜关怀的表述有哪些？",
        CharacterKnowledgeQueryKeywords="失眠,熬夜,关心",
        UserProfileQueryQuestion="用户是否有长期失眠、加班或睡眠障碍相关记录？",
        UserProfileQueryKeywords="失眠,加班,睡眠",
    )


def _mock_step2_results() -> MultiVectorRetrievalResult:
    """模拟 Step2 四路 DashVector 命中（dict 结构与运行时一致）。"""
    r = MultiVectorRetrievalResult(top_k=3, threshold=0.7, is_fallback=False)
    r.character_global_results = [
        {"id": "character_global:demo:1", "score": 0.88, "content": "面对用户深夜在线时，语气要轻、不评判。", "fields": {}},
    ]
    r.character_private_results = [
        {"id": "character_private:demo:u1", "score": 0.81, "content": "该用户曾提到赶项目 deadline，易焦虑。", "fields": {}},
    ]
    r.character_knowledge_results = [
        {"id": "character_knowledge:demo:2", "score": 0.79, "content": "世界观：2149 研究员身份，可用「未来视角」轻轻转移注意力。", "fields": {}},
    ]
    r.user_results = [
        {"id": "mem_101", "score": 0.84, "content": "用户上周说过喝咖啡后更难入睡。", "fields": {}},
        {"id": "user:睡眠:u1", "score": 0.76, "content": "睡眠：用户自述入睡困难。", "fields": {}},
    ]
    return r


async def _run_step3(full_prompt: str) -> None:
    print("\n" + "=" * 72)
    print("Step3：PromptBuilder.build_chat_prompt（真实代码路径，节选打印）")
    print("=" * 72)
    total = len(full_prompt)
    head = 2800
    print(f"总字符数: {total}；下方展示前 {head} 字符；模块分隔符为 {repr(MODULE_SEPARATOR)}")
    print("-" * 72)
    print(full_prompt[:head])
    if total > head:
        print(f"\n… 省略后续 {total - head} 字符 …")
    print("-" * 72)
    # 顺带标出各模块标题行，便于肉眼扫
    modules = full_prompt.split(MODULE_SEPARATOR)
    print(f"按 {repr(MODULE_SEPARATOR)} 拆分后共 {len(modules)} 段，各段首行：")
    for i, m in enumerate(modules, 1):
        first = (m.strip().splitlines() or [""])[0][:80]
        print(f"  [{i}] {first}")


async def main() -> None:
    round_ctx = _round_context_demo()
    recent: list = []  # 演示：无历史对话，减少输出噪音

    print("=" * 72)
    print("输入（模拟本轮 user 打包文本，一句）")
    print("=" * 72)
    print(USER_ONE_LINE)

    # ── Step1.5：真实 Prompt 拼装（与线上一致，但不调用 LLM）──
    step15_prompt = _build_step1_5_prompt(
        persona_text=PERSONA_STUB,
        round_context=round_ctx,
        recent_conversations=recent,
        user_input=USER_ONE_LINE,
    )
    print("\n" + "=" * 72)
    print("Step1.5：送入查询重写 LLM 的完整 Prompt（真实 _build_step1_5_prompt 产出）")
    print("=" * 72)
    print(step15_prompt)

    mock_out = _mock_step15_output()
    qr_result = QueryRewriteResult(success=True, output=mock_out, fallback_embedding=[])

    print("\n" + "=" * 72)
    print("Step1.5：模拟 LLM 结构化 JSON 出参（QueryRewriteOutput.model_dump）")
    print("=" * 72)
    print(json.dumps(mock_out.model_dump(), ensure_ascii=False, indent=2))

    # ── Step2：展示会参与 embedding 的三段文本（真实逻辑来自 qr_result.output）──
    print("\n" + "=" * 72)
    print("Step2：阶段① 将分别对以下 3 段文本做 embedding（来自 Step1.5 三个 QueryQuestion）")
    print("=" * 72)
    print("CharacterGlobalQueryQuestion → 用于 character_global + character_private 两路检索")
    print(mock_out.CharacterGlobalQueryQuestion)
    print("\nCharacterKnowledgeQueryQuestion → 用于 character_knowledge 检索")
    print(mock_out.CharacterKnowledgeQueryQuestion)
    print("\nUserProfileQueryQuestion → 用于 user（用户记忆池）检索")
    print(mock_out.UserProfileQueryQuestion)

    mvr = _mock_step2_results()
    retrieval_for_prompt = mvr.format_for_prompt()
    memories_raw = mvr.user_memory_results

    print("\n" + "=" * 72)
    print("Step2：模拟四路 DashVector 召回（format_for_prompt 结构）")
    print("=" * 72)
    print(json.dumps(retrieval_for_prompt, ensure_ascii=False, indent=2))

    # ── Step3：真实 build_chat_prompt ──
    rel = SimpleNamespace(
        level=1,
        last_interaction_at=__import__("datetime").datetime.utcnow(),
        relation_description=round_ctx["relation_description"],
        user_description=round_ctx["user_description"],
        user_hobby_name=round_ctx["user_hobby_name"],
        user_real_name=None,
    )
    emotion_ctx = {"label": "焦虑", "confidence": 0.72}

    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=None)

    async def _fake_get_redis():
        return fake_redis

    # AsyncSession 占位：persona 走 Redis→DB 时 execute 须可 await，避免异常栈污染输出
    mock_db = MagicMock()
    _db_result = MagicMock()
    _db_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=_db_result)

    with (
        patch(
            "backend.services.prompt_builder.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backend.services.prompt_builder.get_redis", _fake_get_redis),
    ):
        builder = PromptBuilder(mock_db)
        full_prompt = await builder.build_chat_prompt(
            user_id=1,
            user_input=USER_ONE_LINE,
            memories=memories_raw,
            recent_conversations=recent,
            relationship_info=rel,
            emotion_context=emotion_ctx,
            round_context=round_ctx,
            retrieval_results=retrieval_for_prompt,
        )

    await _run_step3(full_prompt)


if __name__ == "__main__":
    asyncio.run(main())
