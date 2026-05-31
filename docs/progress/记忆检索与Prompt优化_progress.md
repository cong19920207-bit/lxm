# 记忆检索与Prompt优化 开发进度追踪

> 文档路径：`docs/progress/记忆检索与Prompt优化_progress.md`  
> 创建时间：2026-05-30  
> PRD 来源：`doc/mem_doc/PRD-记忆检索与Prompt优化.md`（v6.1）  
> 拆解文档：`doc/mem_doc/记忆检索与Prompt优化_开发步骤拆解.md`  
> 契约文档：`docs/contract.md`

---

## 进度总览

| 完成数 | 总环节数 | 完成率 |
|-------|---------|-------|
| 12 | 12 | 100% |

> 每完成一个 STEP，手动更新上表中的完成数和完成率。

---

## 环节进度明细

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注（完成后写 `契约 delta：…` 或 `契约 delta：无`，见拆解 §2.1） |
|---------|---------|---------|------|---------|------|
| STEP-001 | build_filter + search(candidate_keys) | 无 | ✅ | 2026-05-30 | 契约 delta：build_filter、search(candidate_keys) |
| STEP-002 | Step1.5 模型13字段+校验C1+rewrite_input | 无 | ✅ | 2026-05-30 | 契约 delta：QueryRewriteOutput 13 字段、rewrite_input、C1 校验 |
| STEP-003 | Step1.5 Prompt 全量更新 | STEP-002 | ✅ | 2026-05-30 | 契约 delta：Step1.5 Prompt HyDE/CandidateKeys/主链标签（C20）、Step8 保持原标签 |
| STEP-004 | chat.py bundled/截断/fallback | STEP-002 | ✅ | 2026-05-30 | 契约 delta：bundled_truncated、rewrite_input 主链入参、删 last_user_text（C39） |
| STEP-005 | Step8 rewrite_input 调用点 | STEP-002 | ✅ | 2026-05-30 | 契约 delta：step8 rewrite_input（仍传 future_action） |
| STEP-006 | Step2 跳过+cp独立Embedding+主路 | STEP-001,002 | ✅ | 2026-05-30 | 契约 delta：Step2 跳过 C10、cp 独立 Embedding、主路 CandidateKeys、skipped_routes 字段 |
| STEP-007 | Step2 2.5补充路+skipped_routes | STEP-006 | ✅ | 2026-05-30 | 契约 delta：2.5 补充路（C7/C11/C36）、SUPPLEMENT_TRIGGER_THRESHOLD=0.75、合并 Top3 写回、is_fallback 口径（C37） |
| STEP-008 | Step6 key_l1/l2+称呼Prompt | 无 | ✅ | 2026-05-30 | 契约 delta：Step6 fields key_l1/key_l2、称呼提取条件 Prompt 明确化 |
| STEP-009 | Admin knowledge fields+filter | STEP-001 | ✅ | 2026-05-30 | 契约 delta：_build_knowledge_fields(key_l1/l2)、create/update 共用、list_entries 改 build_filter（C33） |
| STEP-010 | user_nickname+relationship | 无 | ✅ | 2026-05-30 | 契约 delta：user_nickname 模块（MODULE_ORDER/LIMITS 50、不裁剪）、relationship 删称呼行（C3/C8/C30） |
| STEP-011 | Step8/Agent 称呼同步 | STEP-010 | ✅ | 2026-05-30 | 契约 delta：Step8 user_nickname（C4，同主链位置）、Agent build_active_message_prompt relationship 后 memory 前（C14/C26） |
| STEP-012 | 单测+contract 收口 | STEP-001~011 | ✅ | 2026-05-30 | 契约定稿：见 contract.md「2026-05-30 摘要」；存量修复+3条冒烟全绿 |

> 状态说明：⬜ 未开始 · 🔄 进行中 · ✅ 已完成 · ❌ 阻塞中

---

## 契约更新记录

| 日期 | STEP | 更新内容 | 契约文档位置 |
|------|------|---------|------------|
| 2026-05-30 | STEP-012 | Step1.5 13 字段、rewrite_input、C1 校验、Step2 2.5 路、skipped_routes、is_fallback 口径、build_filter 双引号、search candidate_keys、key_l1/key_l2、Admin _build_knowledge_fields、user_nickname 模块顺序、relationship 删称呼 | `docs/contract.md` 顶部「2026-05-30 摘要」+「最后更新」 |
| 2026-05-30 | 复查收口 | 热配语义（`user_nickname` 不可 PATCH/不可热覆盖）、`build_filter` 契约条、`vector_retrieval_config` 不含补充路阈值；姊妹文档 **TD-026/TD-027**；单测 **`test_dashvector_client`**、**`test_prompt_builder` 模块顺序** | `docs/contract.md` §向量召回与 Prompt Token；`docs/tech-debt.md` |

---

## 阻塞记录

| 日期 | STEP | 阻塞原因 | 解决方案 | 解决日期 |
|------|------|---------|---------|---------|
| — | — | — | — | — |

---

## 变更记录

| 日期 | 变更描述 | 影响 STEP | 处理方式 |
|------|---------|---------|---------|
| 2026-05-30 | 初版拆解自 PRD v6.1 | 全部 | 按 C21 同 PR 发布 |
| 2026-05-30 | 契约复查后文档与单测对齐 | — | 见「契约更新记录」复查收口行 |
