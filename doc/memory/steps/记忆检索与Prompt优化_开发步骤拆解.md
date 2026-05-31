# 记忆检索与Prompt优化 开发步骤拆解

> PRD 来源：`doc/mem_doc/PRD-记忆检索与Prompt优化.md`（v6.1）  
> 契约文档：`docs/contract.md`  
> 进度追踪：`docs/progress/记忆检索与Prompt优化_progress.md`  
> 拆解日期：2026-05-30

---

## 1. 功能清单

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F1 | DashVector `build_filter()` 统一双引号 filter；`search()` 新增 `candidate_keys=[]` 默认参数 | [核心] | 无 |
| F2 | Step1.5 输出扩展为 13 字段（含 CharacterPrivate 独立组 + 各路 CandidateKeys）；校验改为 JSON 解析成功即 success（四路全「无」合法，C1） | [核心] | 无 |
| F3 | Step1.5 Prompt：HyDE 陈述句规则、CandidateKeys 规则、主链标签文案（C20）、Few-shot、保留【关系状态】称呼行（C13） | [核心] | F2 |
| F4 | 主链 `chat.py`：bundled=`"\n".join`、`_truncate_bundled`（尾部 4000）、`rewrite_input`/`fallback_embedding` 共用截断结果；删除 `last_user_text` 死变量（C39） | [核心] | F2 |
| F5 | `step8_subchain.py`：`last_user_text`→`rewrite_input`，仍传 `future_action`（C17/C31） | [核心] | F2 |
| F6 | Step2：跳过判断（空串/「无」，C10）；`character_private` 独立 Embedding；主路透传 CandidateKeys + `build_filter` | [核心] | F1, F2 |
| F7 | Step2：2.5 路补充（per-route、跳过优先 C35）；合并 Top3 写回；`skipped_routes`；`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`（C7/C11/C12/C36/C37） | [核心] | F6 |
| F8 | Step6：`upsert_step6_vectors` fields 新增 `key_l1`/`key_l2`；称呼提取条件 Prompt 优化 | [核心] | 无 |
| F9 | Admin：`character_knowledge_service` 抽取 `_build_knowledge_fields`；create/update 补写 key；`list_entries` 改用 `build_filter`（C15/C33） | [核心] | F1 |
| F10 | `prompt_builder`：新增 `user_nickname` 模块（不可裁剪）；`relationship` 移除称呼行；`MODULE_TOKEN_LIMITS` 硬编码 ≤50（C3/C8/C16/C30） | [核心] | 无 |
| F11 | Step8 `build_step8_prompt` + Agent `build_active_message_prompt` 同步 `user_nickname`（C4/C14/C26） | [核心] | F10 |
| F12 | pytest 存量修复 + 3 条冒烟；`docs/contract.md` 同步（C21/C23/C38） | [核心] | F1~F11 |
| F13 | TD-022（mem_* 与 Step6 同池）本期不做 | [可选] | — |
| F14 | 上线前验收：Admin update 后 `key_l2` 仍在（不阻塞开发） | [可选] | F9 |

**明确本期不改动（PRD §9）**：`step5_5_service` / `step5_5_prompt_fragments`、SSE、H5 接口、Admin 列表展示、`character_knowledge_validate.py` / `constants.py` / `relationship_service.py`。

---

## 2. 开发环节总览

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-001 | `build_filter` + `search(candidate_keys)` | `backend/services/dashvector_client.py` | 无 | 低 |
| STEP-002 | Step1.5 模型 13 字段 + 校验 C1 + `rewrite_input` 重命名 | `backend/services/query_rewrite_service.py` | 无 | 中 |
| STEP-003 | Step1.5 Prompt 全量更新 | `backend/services/query_rewrite_service.py` | STEP-002 | 中 |
| STEP-004 | 主链 bundled / 截断 / fallback 接入 | `backend/routers/chat.py` | STEP-002 | 中 |
| STEP-005 | Step8 调用点 `rewrite_input` | `backend/services/step8_subchain.py` | STEP-002 | 低 |
| STEP-006 | Step2 跳过 + 独立 cp Embedding + 主路 CandidateKeys | `backend/services/multi_vector_retrieval_service.py` | STEP-001, STEP-002 | 中 |
| STEP-007 | Step2 2.5 补充路 + `skipped_routes` + 合并写回 | `backend/services/multi_vector_retrieval_service.py` | STEP-006 | 高 |
| STEP-008 | Step6 向量 fields + 称呼提取 Prompt | `backend/services/memory_llm_service.py` | 无 | 低 |
| STEP-009 | Admin 知识库 key_l1/key_l2 + list filter | `backend/services/character_knowledge_service.py` | STEP-001 | 低 |
| STEP-010 | `user_nickname` 模块 + relationship 删称呼 | `backend/services/prompt_builder.py` | 无 | 中 |
| STEP-011 | Step8 / Agent Prompt 同步称呼模块 | `prompt_builder.py`（`build_active_message_prompt` 即定义于此，非 `agent_service.py`） | STEP-010 | 低 |
| STEP-012 | 单测 + contract 一次发布收口 | `tests/*`, `docs/contract.md` | STEP-001~011 | 中 |

> **发布约束（C21）**：STEP-001~012 须在同一 PR 合并发布，避免 bundled 进入旧 7 字段 Prompt 的中间态。

### 2.1 每步完成后固定动作

每个 STEP 开发并通过**本步**单测后，**不必改本拆解文档**，按下面执行：

| # | 动作 | 说明 |
|---|------|------|
| 1 | 更新进度 | `docs/progress/记忆检索与Prompt优化_progress.md`：对应行状态 → ✅，填写完成日期 |
| 2 | 契约 delta 备注 | 在同一行**备注**写：`契约 delta：xxx`（对外字段/行为一句）；无则 `契约 delta：无` |
| 3 | contract | **不在此步定稿** `docs/contract.md`（可在 feature 分支草稿积累）；**定稿仅在 STEP-012**（C21） |

**STEP-012 额外**：将 progress 各步「契约 delta」合并写入 `docs/contract.md`，更新「最后更新」日期，并填写 progress 文末「契约更新记录」表。

---

## 3. 开发提示词

### [STEP-001] DashVector build_filter 与 search 签名

**目标**：实现统一双引号 filter 构造，并为 `search()` 增加 `candidate_keys` 默认参数，老调用方零改动。

---

**前置条件检查**：

> 无前置条件。

---

**需要参考的文件**：
- `@backend/services/dashvector_client.py` — 现有 `search()` / `list_by_filter()` 实现
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Step2 filter 规则（C9/C27/C32/C33/C34）
- `@docs/contract.md` — DashVector 字段与 Step2 契约摘要（待 STEP-012 回写）

**环境/数据前提**：
- DashVector 集合已存在且 `type` / `user_id` filter 现网可用
- 无

---

**需求原文引用**：
> filter 统一 `build_filter()` 函数；`search()` 与 `list_by_filter` 共用；type 和 key_l2 均用双引号。  
> `search()` 新增 `candidate_keys: list[str] = []` 默认参数并内部调用 build_filter（老调用方零改动，自动获得双引号，行为不变）。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `build_filter(memory_type, user_id, candidate_keys)` | `str` | 返回 DashVector filter 字符串 | 需求文档原文 |
| `candidate_keys` | `list[str]` | 二级/三级 Key 前缀，用于推导 `key_l2 IN (...)` | 需求文档原文 |
| value 内 `"` | 转义为 `\"` | filter 值转义规则 | 需求文档原文（C9） |

---

**开发任务**：
1. 新增模块级 `build_filter(memory_type: str, user_id: int | None, candidate_keys: list[str]) -> str`：先拼 `type = "{memory_type}"`；有 `user_id` 则 `AND user_id = {id}`；对 `candidate_keys` 每项 `split("-")`，长度≥2 时取 `parts[0]-parts[1]` 入 `key_l2` 集合（值内双引号转义）。
2. 修改 `search()` 签名增加 `candidate_keys: list[str] = []`，内部 `filter_str = build_filter(...)`，其余逻辑不变。
3. 确认 `list_by_filter` 可被外部传入 `build_filter` 生成的字符串（本 STEP 不强制改 `character_knowledge_service`，留给 STEP-009）。

**不在本环节范围内**：
- Step2 补充路业务逻辑（STEP-007）
- `character_knowledge_service.list_entries` 改造（STEP-009）
- 单测新增（STEP-012）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常 | `candidate_keys=["经历-出行","偏好-饮食"]`, `memory_type=user`, `user_id=1` | 含 `key_l2 IN ("经历-出行", "偏好-饮食")` 且全双引号 |
| 边界 | `candidate_keys=[]` | 仅 type（+ user_id），无 key_l2 子句 |
| 边界 | key 含 `"` | 转义后 filter 合法 |
| 非法 key | `["偏好"]` 单层 | 该项丢弃，不报错 |

---

**完成标志**：
- [ ] `build_filter` 可被其他模块 import
- [ ] 现有 `search()` 调用方无需改参即可编译运行
- [ ] **进度**：progress 中 STEP-001 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：build_filter、search(candidate_keys)`；无则 `契约 delta：无`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-002** Step1.5 模型与校验改造

---

### [STEP-002] Step1.5 输出模型 13 字段 + 校验 C1 + rewrite_input

**目标**：扩展 `QueryRewriteOutput` 为 13 字段，删除「至少一组 QueryQuestion 非空」抛错逻辑，参数 `last_user_text` 重命名为 `rewrite_input`。

---

**前置条件检查**：

> 无前置条件（可与 STEP-001 并行，但发布前须合并）。

---

**需要参考的文件**：
- `@backend/services/query_rewrite_service.py`
- `@tests/test_query_rewrite_service.py` — 仅了解待改断言，具体修改在 STEP-012
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Step1.5、`QueryRewriteOutput` 定义（C1/C25）

---

**需求原文引用**：
> JSON 解析成功 + Pydantic 校验通过 = success=True；四路全为「无」是合法成功态，不再抛错。  
> 参数命名：`last_user_text` 重命名为 `rewrite_input`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `CharacterPrivateQueryQuestion` | `str` | 私有设定路 HyDE 问句 | 需求文档原文 |
| `CharacterPrivateQueryKeywords` | `str` | 私有设定路 Keywords | 需求文档原文 |
| `CharacterPrivateCandidateKeys` | `list[str]` | 私有设定路 CandidateKeys | 需求文档原文 |
| `CharacterGlobalCandidateKeys` 等 | `list[str]` | 其余三路 CandidateKeys | 需求文档原文 |
| `rewrite_input` | `str` | 原 `last_user_text`，主链为 bundled_truncated，Step8 为 future_action | 需求文档原文（C25） |

---

**开发任务**：
1. 扩展 `QueryRewriteOutput` Pydantic 模型为 PRD §8 完整 13 字段（含 4 组 CandidateKeys）。
2. `execute_query_rewrite` 及 `_build_step1_5_prompt` 形参：`last_user_text` → `rewrite_input`；`_fallback_with_embedding(text=rewrite_input, ...)` 同步。
3. 删除 `_parse_query_rewrite_output` 中「三组/四路 QueryQuestion 全空则 raise」逻辑；解析成功即 `success=True`。
4. 确保 `QueryRewriteResult` 对外字段与下游 `multi_vector_retrieval_service` 读取名一致（CharacterPrivate* 等新字段）。

**不在本环节范围内**：
- Step1.5 Prompt 文案/Few-shot（STEP-003）
- `chat.py` / `step8_subchain.py` 调用方改参（STEP-004/005）
- 单测批量修复（STEP-012）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 四路全「无」 | mock LLM 返回四路 Question 均为「无」 | `success=True`，不抛异常 |
| 含 Private 字段 | mock 含 `CharacterPrivateCandidateKeys` | 解析为 `list[str]`，`success=True` |
| 非法 JSON | 非 JSON 响应 | `success=False`，走 fallback 路径 |

---

**完成标志**：
- [ ] 模型与解析逻辑与 PRD 一致
- [ ] 无「全空抛错」残留
- [ ] **进度**：progress 中 STEP-002 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：QueryRewriteOutput 13 字段、rewrite_input、C1 校验`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-003** Step1.5 Prompt 全量更新（或可与 STEP-004 并行，须同 PR 发布）

---

### [STEP-003] Step1.5 Prompt 全量更新

**目标**：按 PRD 更新 Step1.5 Prompt【任务】、HyDE/CandidateKeys 规则、主链用户消息标签与 Few-shot；Step8（`source="step8"`）保持原【用户当前消息】标签。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | 13 字段模型与 rewrite_input | progress 中 STEP-002 为 ✅ |

---

**需要参考的文件**：
- `@backend/services/query_rewrite_service.py` — `_build_step1_5_prompt`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Step1.5 Prompt 改写规则、示例 1~4、C13/C17/C19/C20

---

**需求原文引用**：
> 主链：标题改为「【用户本轮消息（可能多段，换行分隔）】」并加综合理解说明。  
> Step8：保持原标签不变。  
> Step1.5 的【关系状态】模块继续保留「用户称呼」行（C13）。

---

**开发任务**：
1. 在 `_build_step1_5_prompt` 中根据 `source` 区分主链/Step8 用户消息模块文案（主链 C20，Step8 不变 C17）。
2. 【任务】末尾追加：HyDE 陈述句规则（四路）、CandidateKeys 规则（四路）、各路分类参考表。
3. 追加 PRD 示例 1~4 作为 Few-shot（含连发综合理解示例）。
4. 【任务】增加「综合理解所有段落整体意图，不必逐段单独处理」（C19）。
5. 确认【关系状态】仍含用户称呼行（与主链 `user_nickname` 职责分离，C13）。

**不在本环节范围内**：
- `chat.py` bundled 拼接（STEP-004）
- Step2 检索逻辑

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| source=main | 调用 `_build_step1_5_prompt` | Prompt 含「用户本轮消息（可能多段」 |
| source=step8 | 同上 | Prompt 仍为「用户当前消息」类原文案 |
| Few-shot | 检查生成 Prompt 字符串 | 含 PRD 示例 2（海鲜过敏+今晚吃啥） |

---

**完成标志**：
- [ ] 主链/Step8 Prompt 分支正确
- [ ] **进度**：progress 中 STEP-003 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：Step1.5 Prompt HyDE/CandidateKeys/主链标签`；无则 `无`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-004** 主链 chat.py bundled 接入

---

### [STEP-004] 主链 chat.py bundled 与截断共用

**目标**：在 `chat.py` 实现 bundled 拼接、尾部 4000 截断，`rewrite_input` 与 `fallback_embedding` 共用同一 `bundled_truncated`；删除 `last_user_text` 死变量；Step5 `user_input` 共用同一 `bundled`（未截断整包，C39）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | rewrite_input 参数名 | progress STEP-002 ✅ |

---

**需要参考的文件**：
- `@backend/routers/chat.py` — `_execute_llm_bundle`：现状 `last_user_text`（约 L535，死变量）、Step1.5 调用 `execute_query_rewrite`（约 L561）、`bundled = "\n".join(...)`（约 L579，**已存在**）、`build_chat_prompt(user_input=bundled, ...)`（约 L583，**已使用整包**）
- `@backend/services/query_rewrite_service.py`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — C24/C28/C29/C39

---

**需求原文引用**：
> `bundled = "\n".join(r.content for r in pack_rows)`  
> `bundled_truncated = _truncate_bundled(bundled)` — 尾部 4000，两处共用。  
> 删除 `last_user_text`；Step1.5 与 Step5 user_input 共用同一个 bundled。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `BUNDLED_MAX_CHARS` | `int` | `4000` | 需求文档原文（C29） |
| `_truncate_bundled(text)` | `str` | `text[-4000:]` if len>4000 else text | 需求文档原文 |

---

**开发任务**：
1. 在合适位置（建议 `chat.py` 或共享 util）定义 `BUNDLED_MAX_CHARS = 4000` 与 `_truncate_bundled`。
2. 将 `bundled = "\n".join(...)`（现约 L579）的定义**上移**到 Step1.5 调用（现约 L561）之前，并在其后派生 `bundled_truncated = _truncate_bundled(bundled)`。
3. `execute_query_rewrite(..., rewrite_input=bundled_truncated, ...)`；降级 `fallback_embedding` 使用同一 `bundled_truncated`（C18/C28）。
4. 删除死变量 `last_user_text = pack_rows[-1].content`（约 L535）。
5. `build_chat_prompt` 的 `user_input` **保持**传 `bundled`（现 L583 已是整包，仅因 bundled 定义上移而复用同一变量，Step5 输入语义不变，C39）。
6. 不修改 Step8 子链路（STEP-005）。

---

**不在本环节范围内**：
- Step8 `step8_subchain.py`（STEP-005）
- Step1.5 Prompt 内容（STEP-003）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 短消息包 | 3 条短 content | bundled 无截断，rewrite 与 user_input 一致 join |
| 超长包 | 模拟 >4000 字符 | `bundled_truncated` 长度为 4000，取尾部 |
| 降级 | Step1.5 失败 mock | fallback embedding 入参为 truncated 文本 |

---

**完成标志**：
- [ ] 主链无 `last_user_text` 残留
- [ ] **进度**：progress 中 STEP-004 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：bundled_truncated、rewrite_input 主链入参`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-005** Step8 调用点同步

---

### [STEP-005] Step8 子链路 rewrite_input 调用点

**目标**：`step8_subchain.py` 中 `execute_query_rewrite` 调用形参改为 `rewrite_input=future_action`，不传 bundled（C17/C31）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | rewrite_input 重命名 | progress STEP-002 ✅ |

---

**需要参考的文件**：
- `@backend/services/step8_subchain.py`
- `@tests/test_step024_step8_subchain.py` — 断言键名改写在 STEP-012

---

**需求原文引用**：
> Step8 传给 Step1.5 的是 future_action（约 20 字），不是用户消息包；`last_user_text`→`rewrite_input`。

---

**开发任务**：
1. 将 `execute_query_rewrite(..., last_user_text=future_action, ...)` 改为 `rewrite_input=future_action`。
2. 更新文件内注释（去掉「替代 last_user_text」过时描述）。
3. 确认 `source="step8"` 仍传入，供 STEP-003 Prompt 分支使用。

**不在本环节范围内**：
- Step8 Prompt `user_nickname`（STEP-011）
- 单测修复（STEP-012）

---

**完成标志**：
- [ ] 调用编译通过
- [ ] **进度**：progress 中 STEP-005 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：step8 rewrite_input`；无则 `无`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-006** Step2 主路与跳过逻辑

---

### [STEP-006] Step2 跳过判断 + character_private 独立 Embedding + 主路检索

**目标**：实现 C10 跳过（不 Embedding、不 search）；`character_private` 使用独立 `CharacterPrivateQueryQuestion` Embedding；主路 `search` 传入各路 `CandidateKeys`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 | build_filter + search | progress ✅ |
| STEP-002 | 13 字段 QueryRewrite 输出 | progress ✅ |

---

**需要参考的文件**：
- `@backend/services/multi_vector_retrieval_service.py`
- `@backend/services/dashvector_client.py`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Step2 跳过、Embedding 并行、主路调用

---

**需求原文引用**：
> `value.strip() == "" OR value.strip() == "无"` 均视为跳过。  
> character_private 独立生成，不再复用 character_global 的 Embedding。  
> 主路：`search(..., candidate_keys=该路CandidateKeys, top_k=热配)`。

---

**开发任务**：
1. 实现 `_should_skip(question: str) -> bool`。
2. Phase1：仅对未跳过三路（cg/cp/ck/up）并行 `get_embedding`；cp 使用 `CharacterPrivateQueryQuestion`。
3. Phase2：未跳过路调用 `dashvector_client.search`，`candidate_keys` 取自对应 `*CandidateKeys`；跳过路结果 `[]`。
4. 暂不实现补充路（STEP-007）；`MultiVectorRetrievalResult` 可先预留 `skipped_routes` 字段并在本 STEP 写入跳过路名（memory_type 常量值）。

**不在本环节范围内**：
- 补充路 Keywords Embedding（STEP-007）
- `SUPPLEMENT_TRIGGER_THRESHOLD` 合并逻辑（STEP-007）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 四路全跳过 | 四路 Question 均为「无」 | 零次 `search` 调用；四路 `[]`；`skipped_routes` 含四路常量名 |
| 仅 user 路 | 仅 UserProfile Question 非空 | 仅 1 次 user embedding + 1 次 search |
| cp 独立 | Global/Private 均有 Question | 两次不同 embedding，不复用 cg_emb |

---

**完成标志**：
- [ ] 主路 filter 带 key_l2（有 CandidateKeys 时）
- [ ] **进度**：progress 中 STEP-006 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：Step2 跳过 C10、cp 独立 Embedding、主路 CandidateKeys`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-007** Step2 2.5 补充路

---

### [STEP-007] Step2 2.5 路补充检索与结果合并

**目标**：实现 per-route 补充触发（C35：已跳过路不触发）；Keywords 空则跳过补充（C11）；补充路 `candidate_keys=[]`、`top_k=3`、threshold 沿用热配（C36）；合并 Top3 写回各路 `*_results`（C37）；`SUPPLEMENT_TRIGGER_THRESHOLD = 0.75`（C2）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-006 | Step2 主路与跳过 | progress ✅ |

---

**需要参考的文件**：
- `@backend/services/multi_vector_retrieval_service.py`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 2.5 路、C7/C11/C12/C35/C36/C37

---

**需求原文引用**：
> 触发：`count < 2 OR max_score < 0.75`（行为 A）。  
> 被 C10 跳过的路不触发补充，最终结果直接 []。  
> 合并去重 → score 降序 → Top3 写回该路 `*_results`。  
> C1 四路全无：`is_fallback=False`，`skipped_routes` 填四路全名。

---

**开发任务**：
1. 模块常量 `SUPPLEMENT_TRIGGER_THRESHOLD = 0.75`。
2. `should_trigger_supplement(main_results)`：仅对「未跳过且主路已执行」路调用。
3. 补充路：Keywords 非空 → `kw_emb` + `search(candidate_keys=[], top_k=3, threshold=热配)`。
4. `merge_results(main, supplement) -> merged[:3]`（按 id 去重，score 降序）。
5. 降级路径（Step1.5 失败）：保持现有 `fallback_embedding` 四路检索逻辑，不加 key_l2；与 PRD C18 一致。
6. 完善 `MultiVectorRetrievalResult.skipped_routes` 与 `is_fallback` 口径（C37）。

**不在本环节范围内**：
- Step1.5 / chat 改动
- 新增冒烟单测（STEP-012）

---

**单元测试要求**（STEP-012 用例 3 预置）：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 主路 1 条低分 | count<2 触发补充 | 调用 Keywords embedding + 第二次 search |
| Keywords 空 | 触发条件满足但 Keywords="" | 不补充 embedding，结果=主路 |
| 跳过优先 | Question=「无」 | 不调用 `should_trigger_supplement` |

---

**完成标志**：
- [ ] 2.5 路与 PRD 行为 A 一致
- [ ] **进度**：progress 中 STEP-007 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：2.5 补充路、skipped_routes、合并 Top3`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-008** Step6 向量字段

---

### [STEP-008] Step6 upsert key_l1/key_l2 + 称呼提取 Prompt

**目标**：`upsert_step6_vectors` 写入 `key_l1`、`key_l2`；优化 Step6 Prompt 中 UserHobbyName/UserRealName 提取条件文案。

---

**前置条件检查**：

> 无前置条件（可与 STEP-006 并行）。

---

**需要参考的文件**：
- `@backend/services/memory_llm_service.py` — `upsert_step6_vectors`（约 L312），现 fields 拼装在约 L376-379（仅 `content` + `stable_key`）
- `@backend/utils/character_knowledge_validate.py` — `validate_key` 保证三层 key
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Step6

---

**需求原文引用**：
> fields 新增 key_l1、key_l2；doc_id 仍 hash。  
> Step6 LLM 输出 11 字段 JSON 结构不变。  
> UserHobbyName/UserRealName 触发提取条件明确化。

---

**开发任务**：
1. 在 `upsert_step6_vectors`（或等价函数）中，`segments = key.split("-")` 后写入 `key_l1=segments[0]`，`key_l2=segments[0]+"-"+segments[1]`。
2. 更新 Step6 记忆总结 Prompt 中称呼字段说明（PRD §6 原文块）。
3. 不修改 `parse_kv_lines` 与 11 字段 JSON schema。

---

**完成标志**：
- [ ] 新写入向量含 key_l1/key_l2
- [ ] **进度**：progress 中 STEP-008 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：Step6 fields key_l1/key_l2、称呼提取 Prompt`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-009** Admin 知识库字段

---

### [STEP-009] Admin character_knowledge key 字段与 list filter

**目标**：抽取 `_build_knowledge_fields`；`create_entry`/`update_entry` 共用；`update_entry` 必须补写 key_l1/key_l2（C15）；`list_entries` 改用 `build_filter`（C33）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 | build_filter | progress ✅ |

---

**需要参考的文件**：
- `@backend/services/character_knowledge_service.py` — `_resolve_stable_key(fields, content)`（约 L44）、`list_entries`（约 L69，现 L90 为单引号 `filter_str = f"type = '{mt}'"`）、`create_entry`（约 L140）、`update_entry`（约 L183）
- `@backend/services/dashvector_client.py` — `build_filter`（STEP-001 产出）
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Admin（C15/C33）

---

**开发任务**：
1. 新增 `_build_knowledge_fields(key, content) -> dict`（含 stable_key、key_l1、key_l2）。
2. `create_entry` / `update_entry` 均使用该函数组装 fields；`update_entry` 的 key 通过现有 `_resolve_stable_key(fields, content)`（注意实参为 fields+content，非 PRD 笔误的 `doc_id`）获取后再构建。
3. `list_entries`：将 L90 单引号 `f"type = '{mt}'"` 改为 `filter_str = build_filter(mt, None, [])`（双引号，与检索侧一致）后 `list_by_filter`。
4. Admin 列表页 `knowledge.html` 不展示 key_l1/key_l2（无需改前端）。

---

**完成标志**：
- [ ] create/update 字段一致
- [ ] **进度**：progress 中 STEP-009 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：Admin knowledge key_l1/l2、list_entries build_filter`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-010** Prompt user_nickname 模块

---

### [STEP-010] prompt_builder user_nickname + relationship 删称呼

**目标**：新增不可裁剪 `user_nickname` 模块；从 `relationship_info` 直接取称呼（C16）；`relationship` 删除亲密称呼/用户真名两行（C3）；更新 `MODULE_ORDER` 与 `MODULE_TOKEN_LIMITS`（C8/C30）。

---

**前置条件检查**：

> 无前置条件。

---

**需要参考的文件**：
- `@backend/services/prompt_builder.py`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Prompt 详细逻辑

---

**需求原文引用**：
> user_nickname 位于 recent_chat 之后、user_input 之前；绝不裁剪。  
> relationship 模块移除称呼行。  
> 数据来源：直接从 relationship_info 取，不经 round_context。

---

**开发任务**：
1. 实现 `_build_user_nickname_prompt(relationship_info)`（PRD 三种分支 + 全空返回 `""`）。
2. `MODULE_ORDER`（约 L46）插入 `"user_nickname"`（在 `recent_chat` 与 `user_input` 之间）。
3. `MODULE_TOKEN_LIMITS`（约 L24）硬编码 `user_nickname: 50`；`user_nickname` 不在 `TRIM_PRIORITY`（约 L37）中，天然豁免裁剪，确认无需额外改裁剪逻辑。
4. `_build_relationship_prompt`（约 L703）删除称呼行：**`if relationship_info` 分支的 `亲密称呼`（约 L752）/`用户真名`（约 L755）两行，以及 `else` 分支的 `亲密称呼：无`（约 L758）/`用户真名：无`（约 L759）两行，共两处分支均需删除**；`_build_relationship_prompt_core`（约 L763，裁剪版）本就无称呼行，无需改。
5. `build_chat_prompt`（约 L380）需将 `module_texts["user_nickname"]` 填入并参与拼装（与 MODULE_ORDER 对应）。

---

**完成标志**：
- [ ] 主链 `build_chat_prompt` 含 user_nickname
- [ ] relationship 无称呼行
- [ ] **进度**：progress 中 STEP-010 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：user_nickname 模块、relationship 删称呼`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-011** Step8 / Agent 同步

---

### [STEP-011] Step8 与 Agent Prompt 同步 user_nickname

**目标**：`build_step8_prompt` 插入 user_nickname（recent_chat 之后、user_input 之前，C4）；`agent_service.build_active_message_prompt` 在 relationship 之后、memory 之前插入（C14/C26）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-010 | _build_user_nickname_prompt | progress ✅ |

---

**需要参考的文件**：
- `@backend/services/prompt_builder.py` — `build_step8_prompt`（约 L521）与 `build_active_message_prompt`（约 L458，方法定义在 `PromptBuilder` 类内）
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — C4/C14/C26/C22（Step5.5 不改）

> 说明：`agent_service.py` 仅在约 L305 调用 `builder.build_active_message_prompt(...)`，**本环节不需要改动 `agent_service.py`**，真正的插入点在 `prompt_builder.py` 的方法体内（PRD §9 改造范围亦只列 `prompt_builder.py`）。

---

**开发任务**：
1. `build_step8_prompt`：`module_texts["user_nickname"] = self._build_user_nickname_prompt(relationship_info)`，MODULE_ORDER 与主链一致插入位置。
2. `build_active_message_prompt`（`prompt_builder.py` 内）：在现有 `parts = [system, persona, relationship, memory, emotion, task]` 中，`relationship_prompt` 后、`memory_prompt` 前插入 `user_nickname_prompt = self._build_user_nickname_prompt(relationship_info)`。
3. **不修改** `step5_5_service` / `step5_5_prompt_fragments`（C22）。

---

**完成标志**：
- [ ] Step8 / Agent 主动消息 Prompt 含称呼指令
- [ ] **进度**：progress 中 STEP-011 → ✅ 并填完成日期（§2.1）
- [ ] **契约 delta**：progress 备注已写（例：`契约 delta：Step8/Agent user_nickname 位置`）

---

**完成后执行**：

> **每步固定动作**（§2.1）：① progress 本 STEP → ✅；② 备注「契约 delta：…」或「无」；③ 不定稿 contract。  
> **下一环节**：**STEP-012** 测试与契约收口

---

### [STEP-012] 单测存量修复 + 3 条冒烟 + contract 同步

**目标**：完成 C23/C38 测试范围；更新 `docs/contract.md` Step1.5 13 字段与入参变更（C21）；保障一次发布 CI 绿。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 ~ STEP-011 | 全部实现 | progress 均为 ✅ |

---

**需要参考的文件**：
- `@tests/test_query_rewrite_service.py`
- `@tests/test_step024_step8_subchain.py`
- `@tests/test_multi_vector_retrieval_service.py`
- `@docs/contract.md`
- `@doc/mem_doc/PRD-记忆检索与Prompt优化.md` — §6 Admin 测试集 C23/C38

---

**开发任务**：

**存量修复（C38）**：
1. `test_query_rewrite_service.py`：`_base_execute_kwargs` 中 `last_user_text`→`rewrite_input`；`test_all_three_questions_empty_raises` 改为四路全空 `success=True` 不抛错。
2. `test_step024_step8_subchain.py`：断言 `call_kwargs.kwargs["rewrite_input"]`。

**新增冒烟（C23）**：
3. 用例1：四路全「无」→ `success=True`，`fallback_embedding` 为空（或约定空列表语义）。
4. 用例2：含 `CharacterPrivateCandidateKeys` 解析成功。
5. 用例3（`test_multi_vector_retrieval_service.py`）：四路全无 → `skipped_routes` 四路、`is_fallback=False`、mock 零次 `search`。

**契约**：
6. 更新 `docs/contract.md` 顶部「最后更新」日期；补充 Step1.5 输出 13 字段、`rewrite_input`、Step2 2.5 路、`skipped_routes`、`build_filter`、`key_l1`/`key_l2`、`user_nickname` 模块顺序；标注 TD-022/存量迁移为技术债（引用 `docs/tech-debt.md` 若已有条目）。

**回归**：
7. 运行 `pytest tests/test_query_rewrite_service.py tests/test_multi_vector_retrieval_service.py tests/test_step024_step8_subchain.py` 及相关存量用例。

---

**完成标志**：
- [ ] 上述 pytest 全部通过
- [ ] **进度**：progress 中 STEP-012 → ✅ 并填完成日期
- [ ] **契约定稿**：`docs/contract.md` 已合并各步「契约 delta」、更新「最后更新」日期；progress「契约更新记录」表已填
- [ ] **全 PRD 功能验收完成（C21 一次发布）**

---

**完成后执行**：

> **STEP-012 固定动作**（§2.1）：① progress 本 STEP → ✅；② **定稿** `docs/contract.md`；③ 填写 progress「契约更新记录」。  
> 全部 12 个 STEP 完成后，进行上线前手工验收（Admin update 后 key_l2 仍在，PRD §7 可选 F14）。

---

## 4. 自检清单

- [x] 需求文档中每一条功能都有对应的 STEP（F1~F12 → STEP-001~012；F13/F14 已标注可选/验收）
- [x] 没有增加需求文档中不存在的功能
- [x] 自定义字段已标注（如进度文档路径）
- [x] 不确定路径已用「待查代码仓库」或已对照仓库填写 `@backend/...`
- [x] 关联模块引用 `docs/contract.md`（STEP-012 回写）
- [x] 环节依赖：001→006/009；002→003/004/005/006；006→007；010→011；001~011→012
- [x] 每个 STEP 包含完成回调指令（§2.1 每步固定动作 + 各 STEP 完成标志/完成后执行）
- [x] 进度文档 `docs/progress/记忆检索与Prompt优化_progress.md` 已生成

---

## 附录：技术债（本期不实现，仅跟踪）

| 编号 | 描述 |
|------|------|
| TD-022 | user 路 mem_* 与 Step6 同池 — 本期不做 |
| TD-存量迁移 | 旧记忆无 key_l1/key_l2 — 补充路兜底，迁移另排期 |
| TD-热配扩展 | `SUPPLEMENT_TRIGGER_THRESHOLD` 写死 0.75 |
| TD-补充路阈值 | 补充路 threshold 沿用主路 0.7，未独立可配 |
| TD-Step1.5重复 | bundled 与 recent_chat 重叠 |
| TD-Q4护栏 | Step2 最坏 8 次向量检索 RT 监控 |
| TD-contract | 由 STEP-012 在本期关闭 |
