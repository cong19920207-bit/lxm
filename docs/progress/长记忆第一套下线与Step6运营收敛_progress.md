# 长记忆第一套下线与 Step6 运营收敛 开发进度追踪

> 文档路径：`docs/progress/长记忆第一套下线与Step6运营收敛_progress.md`
> 创建时间：2026-05-31
> PRD 来源：`doc/mem_doc/PRD-长记忆第一套下线与Step6运营收敛.md`（v1.3）
> 步骤拆解：`doc/mem_doc/长记忆第一套下线与Step6运营收敛_开发步骤拆解.md`
> 契约文档：`docs/contract.md`

---

## 进度总览

| 完成数 | 总环节数 | 完成率 |
|-------|---------|-------|
| 16 | 16 | 100% |

> 每完成一个 STEP，手动更新上表中的完成数和完成率。

---

## 环节进度明细

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-001 | 新增 `is_user_manageable_doc_id` 双匹配校验 | 无 | ✅ | 2026-05-31 | P3 |
| STEP-002 | 新建 `user_vector_memory_service` | STEP-001 | ✅ | 2026-05-31 | C-06，含 USER_LIST_TOPK/GLOBAL_LIST_TOPK_NO_USER 常量 |
| STEP-003 | Admin 用户记忆 / 私有状态 API + 删旧记忆接口 | STEP-002 | ✅ | 2026-05-31 | C-01/C-09，权限 super+ops+ai |
| STEP-004 | H5 `GET /api/memory/list` 只读改造 + 删写路由 | STEP-002 | ✅ | 2026-05-31 | C-05；删整文件 schemas/memory.py（已全孤儿） |
| STEP-005 | 全局用户记忆 API 改造（global + batch-delete） | STEP-002 | ✅ | 2026-05-31 | M5/M6/R-01/P4/P8 |
| STEP-006 | `build_step6_prompt` 异步化 + 热配置 + DEFAULT 复刻 | 无 | ✅ | 2026-05-31 | P2/P6，DEFAULT 逐字相等已校验通过 |
| STEP-007 | `step6-memory-prompt` API + 删 `memory-rules` API | STEP-006 | ✅ | 2026-05-31 | C-02/C-10，权限 super+ai |
| STEP-008 | 下线第一套写入 + 物理删危险函数 | 无 | ✅ | 2026-05-31 | P10；_calculate_importance/_calc_expires_at 因 add_memory_manual 引用而保留 |
| STEP-009 | `memory_injected` 恒 null + send 死代码清理 | 无 | ✅ | 2026-05-31 | M11/P7，user 行恒 null，删孤儿 _search_memories/_get_embedding 及 import |
| STEP-010 | 召回侧 P1 确认（不加 `mem_*` 过滤） | 无 | ✅ | 2026-05-31 | P1，两文件确认零功能改动，仅加 P1 防误加过滤注释 |
| STEP-011 | 前端 `memory.html` 只读 KV 列表 | STEP-004 | ✅ | 2026-05-31 | §6.3.2，移除增删改 UI/API，KV 卡片+只读说明+新空态 |
| STEP-012 | 前端 `settings.html` 记忆整理只读说明 | 无 | ✅ | 2026-05-31 | C-07，移除 Toggle 与 memory_auto_extract 读写，改只读「记忆整理」行 |
| STEP-013 | 前端 `user-detail.html` 用户记忆 + 私有状态 Tab | STEP-003 | ✅ | 2026-05-31 | §6.2.3，主键 doc_id，新增私有状态 Tab+说明，编辑仅改 value |
| STEP-014 | 前端 `memory-rules.html` 三 Tab 改造 | STEP-005、STEP-007 | ✅ | 2026-05-31 | §6.6.3/§6.4.3，三 Tab（Step6 Prompt 默认/向量库/全局用户记忆），删第一套 UI |
| STEP-015 | 契约 + 技术债同步 | STEP-001~014 | ✅ | 2026-05-31 | §10，contract.md + tech-debt.md（TD-022 已清偿/023 已缓解/024 部分清偿）同步 |
| STEP-016 | 上线前/后运维清理与验收 checklist | STEP-001~015 | ✅ | 2026-05-31 | M2/§11，§11.3 回归 130 项全通过；验收报告 `doc/mem_doc/test_report_MEMOFFLINE_20260531.md`；§11.1 清理 + §11.2 八项验收待发布负责人在发布窗口执行回填 |

> 状态说明：
> - ⬜ 未开始
> - 🔄 进行中
> - ✅ 已完成
> - ❌ 阻塞中（在备注中填写原因）

---

## 契约更新记录

> 每次完成 STEP 后，如有新增接口或数据结构，在此记录。

| 日期 | STEP | 更新内容 | 契约文档位置 |
|------|------|---------|------------|
| — | — | — | — |

---

## 阻塞记录

> 记录开发过程中遇到的阻塞问题，解决后在此更新。

| 日期 | STEP | 阻塞原因 | 解决方案 | 解决日期 |
|------|------|---------|---------|---------|
| — | — | — | — | — |

---

## 变更记录

> 如需求发生变更，在此记录，并注明影响的 STEP。

| 日期 | 变更描述 | 影响 STEP | 处理方式 |
|------|---------|---------|---------|
| — | — | — | — |
