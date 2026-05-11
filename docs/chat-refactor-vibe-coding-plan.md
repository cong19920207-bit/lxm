# H5 对话改造：Vibe Coding 开发计划 + 提示词

> **用途**：给「边对齐边写」的迭代开发用——**小步、可验收、少回炉**；与 **`docs/chat-refactor-agent-tasks.md`**、**`docs/product-development-plan-h5-chat.md`**、**`docs/chat-refactor-implementation-plan.md`**、**`docs/tech-debt.md`（TD-015 / TD-016 / TD-020）**、**`docs/contract.md`** 一致。  
> **前提（已定稿）**：主链 **任务 1–8** 与 **S1–S3**（连发/打断、`Abort`/`chatSendSession`、进行中 AI 气泡、契约补句）**已交付**；**2026-05-11** 起 H5 **已移除 `sending`**，改为 **300ms 防抖 + IME**。历史 **N2/N3 `sending` 解锁** 讨论见 `chat-refactor-agent-tasks.md` 附录（**已归档**）。**确认点 1–4** 见该文档「后续里程碑」；**勿**再以旧 `sending` 语义写新验收。

---

## 一、Vibe 工作方式（约定）

1. **先读再改**：打开本节「必读索引」对应段落，grep 现网实现，**禁止**凭记忆重写 `chat.py` 入队/打包/10104。  
2. **最小 diff**：一个 PR 只做一张表里的「一个切片」；无关格式化、大范围重排一律不做。  
3. **验收先于合并**：每个切片有 **DoD（完成定义）**；手工或脚本勾一条算一条。  
4. **契约同步**：动接口/字段/端行为 → 按 `.cursor/rules/docup.mdc` 更新 **`docs/contract.md`** 顶部日期与对应小节。  
5. **中文注释**：新增注释 UTF-8；与仓库现有风格一致。

---

## 二、必读索引（动刀前 10 分钟）

| 顺序 | 文档 | 读什么 |
|------|------|--------|
| 1 | `docs/chat-refactor-agent-tasks.md` | 执行前共识、**后续里程碑**表、**已定稿确认点 1–4**、附录 N0–Nk |
| 2 | `docs/product-development-plan-h5-chat.md` | §五 Must/Should、目标 A/B |
| 3 | `docs/tech-debt.md` | **[TD-015]** 首版主链 vs 后续排期；**[TD-016][TD-020]** 边界 |
| 4 | `docs/contract.md` | **POST /api/chat/send**、**resend**、**timeline**、H1/J2/L1 |
| 5 | `frontend/pages/chat.html` | `handleSend`、`consumeChatSse`、叹号监听、`chatSendSession` / `data-ai-in-flight` |

---

## 三、范围快照（防止做重复）

| 状态 | 内容 |
|------|------|
| **已完成（勿回炉）** | 入队即落 user、`generation_id` 作废、防抖打包、45s 聊天超时、叹号 **resend** 限流、幂等、timeline/Admin 字段对齐、SSE `meta`/`failed`/`obsolete`、`chat.html` **S1–S3**（**无 `sending`**、**300ms 防抖**、**IME**、移除进行中 AI 行、`Abort`/`chatSendSession`）、`contract.md` 流中再发与多端半句 |
| **明确不做（本期）** | Admin 代用户重发（**L1**）、全链路改 **TD-017** 检索改写；管理端情绪区**仅只读**（无代发、无改写 DB） |
| **下一波（按序）** | **S4** 回归（清单须按 **2026-05-11** 勘误更新）→ **TD-020** → **TD-016 / 任务 9 / V2-A–C** 已合并 |
| **N2 触发条件** | **已归档**：历史上 **N2/N3 与 `sending`** 的讨论见 `chat-refactor-agent-tasks.md` 附录；**现网**以 **`contract.md` + `chat.html`** 为准，**不再**以 `sending` 解锁作立项条件 |

---

## 四、阶段计划（产品计划 → 工程切片）

### 阶段 V1 · 收尾与质量（优先）

| 切片 | 交付物 | DoD（验收） |
|------|--------|-------------|
| **V1-A** | **S4** 手工回归清单（可贴到工单）；清单路径：`docs/chat-refactor-s4-manual-regression-checklist.md` | 连发、打断、满 5、叹号破 5、超时叹号、气泡消失、登出/401；**不**回归测后端状态机「从零实现」 |
| **V1-B** | （可选）`scripts/test_chat_e2e.py` 增补 **HTTP+SSE** 场景 | 至少覆盖：**首包慢时** 在 **300ms 防抖间隔外** 可发第二条（或脚本层模拟 session）；失败路径不断言已删功能；脚本已覆盖 ✓ |

### 阶段 V2 · TD-016 / 任务 9（与 H5 连发解耦）

| 切片 | 交付物 | DoD |
|------|--------|-----|
| **V2-A** | `round_id` 模型与迁移策略（与现网 emotion 挂接方式对齐 agent-tasks **任务 9**） | **已交付（2026-04-15）**：ORM + **Alembic** `td016_v2a_001` + 可选 `scripts/migrate_td016_round_id.sql` + `schema_ddl.sql` + `contract.md`；迁移可执行；写入见 V2-B |
| **V2-B** | 写入路径：本轮 user+assistant 与 `emotion_log` **按轮** | **已交付（2026-04-15）**：`_persist_bundle_success` 写 `round_id`；句级 `emotion_label` 不变；`contract.md` 已补 |
| **V2-C** | Admin 情绪区「待完成」→ 真数据（仅任务书范围） | **已交付（2026-04-15）**：`emotion-rounds` + `user-detail.html` Tab；`super_admin`/`ops_admin`；无 L1 |

### 阶段 V3 · TD-020

| 切片 | 交付物 | DoD |
|------|--------|-----|
| **V3-A** | 用户短期情绪：Redis/DB 真相源与读写边界 | **进行中（2026-04-15）**：`user_emotion:{user_id}` + `user_short_term_emotion`；读仅 `_execute_llm_bundle`；`send` 首段无新 Redis；与 [TD-020] 一致 |

### 阶段 VX ·（已并入主线，归档）

| 切片 | 交付物 | DoD |
|------|--------|-----|
| **VX-A（归档）** | 历史上 **N2 与 `sending` 解锁** 的契约与风险说明 | **已由 2026-05-11 演进取代**：H5 **移除 `sending`**，改 **300ms 防抖 + IME**；**不改**后端打包/代语义。详见 **`docs/contract.md`**。 |

---

## 五、通用「Vibe 基座」提示词（每次开新会话可粘贴）

```
你是本仓库的开发者。上下文：林小梦 H5 对话 TD-015 主链与 S1–S3 已交付；**H5 `chat.html`（2026-05-11+）无全局 `sending`**，连发靠 **`Abort`/`chatSendSession`** + **300ms 防抖**，详见 **`docs/contract.md`**「H5 实现说明」。

硬约束：
1. 不要重写 backend/routers/chat.py 的入队、打包、generation 作废、10104、防抖语义；除非我明确要求且附带设计理由。
2. 改动前用 Read/Grep 对照 docs/chat-refactor-agent-tasks.md「后续里程碑」与 docs/contract.md 对应节。
3. 最小 diff；中文注释 UTF-8；API 信封与错误码与 backend/constants.py、contract.md 一致。
4. 若改接口/字段/端上可见行为，同步更新 docs/contract.md（最后更新日期 + 相关小节）。

本次切片目标（由我填写）：________
验收标准（DoD）：________
```

---

## 六、分场景提示词（复制后填空）

### 6.1 S4 · 手工回归 / 轻量 e2e（V1）

```
【角色】测试与脚本维护。

【背景】H5 `chat.html`（2026-05-11+）：**无全局 `sending`**；**`lastSendOrResendAt` + 300ms**（`send`/叹号共用）仅防连点；**`Abort` + `chatSendSession` 递增**；`removeAiInFlightRows`；`failed`/`obsolete` 移除进行中 AI；`send` 失败时 user 行 `failed_*` + 叹号；**`CHAT_CLIENT_ABORT_MS`（120s）** 客户端中止。详见 **`docs/contract.md`**「H5 实现说明」与 **`docs/chat-refactor-s4-manual-regression-checklist.md`**（须按清单内 **2026-05-11 勘误** 执行）。

【任务】
1. 按 **`docs/chat-refactor-s4-manual-regression-checklist.md`** 勾选：连发、首包慢（**300ms 外**可再发、与旧 `sending` 预期不同）、打断、满 5、叹号破 5、SSE `failed`、超时 `Abort`、401。
2. （若我要求）在 `scripts/test_chat_e2e.py` 增加最小断言：不 mock 主链；失败时打印可读日志。

【禁止】把后端 chat 状态机从零写一遍或改 10104 语义。

【完成】清单可勾选 +（若有脚本）本地可跑通命令一行写 README 或注释。
```

### 6.2 TD-016 / 任务 9 · 模型与迁移（V2）

```
【角色】后端 + 迁移。

【背景】TD-015 已交付；round_id / 按轮 emotion_log / Admin 展示归 TD-016（chat-refactor-agent-tasks 任务 9）。chat-refactor-implementation-plan §五 写明 round_id 可 P7 再加，现网若有临时挂接须兼容迁移。

【任务】
1. 读 tech-debt.md [TD-016] 与 agent-tasks 任务 9 提示词，列出与现表 emotion_log、conversation_log 的差异表。
2. 实现迁移 + ORM；落库路径增量修改，保留旧读路径或一次性迁移策略在 PR 描述写清。
3. 更新 docs/contract.md 仅触及你改的接口/字段。

【禁止】改 chat 打包条数、防抖、重发限流逻辑；Admin 代用户重发（L1）。

【验收】迁移可执行；核心聊天 send 仍绿；Admin 仅展示范围不越权。
```

### 6.3 TD-020 · 短期用户情绪（V3）

```
【角色】后端 + Redis/DB。

【背景】TD-020 定义用户短期情绪属性与真相源；与 TD-016 可交叉但勿改乱 chat 主链。

【任务】
1. 只读 tech-debt.md [TD-020]，写「读写矩阵」：谁写、谁读、TTL、与 ai_emotion 关系。
2. 按矩阵实现最小闭环；配置走 config.py / .env。
3. contract.md 补 Admin 或 H5 若新增只读接口。

【禁止】为情绪把聊天 LLM 超时或 SSE 结构改掉。

【验收】单元或最小集成可重复跑；无密钥写进仓库。
```

### 6.4 ~~产品驱动 · N2 解锁小版本~~（**已归档 · 2026-05-11**）

> **说明**：历史上 **N2 与 `sending` 解锁** 的 VX 切片已由 **「移除 `sending` + 300ms 防抖 + IME」** 取代；**勿**再按下列提示词新开「仅改 N2 解锁点」工单。若产品仍有 **SSE 首包时序** 类新需求，请**新建立项**并对照现 **`contract.md` + `chat.html`**。

```
【归档 · 勿直接执行】以下内容为 2026-04 历史稿，仅供理解旧讨论：

【角色】H5 + 契约；必要时只读后端 SSE 首包时序。

【背景】曾讨论 N2（HTTP 200 + `text/event-stream`）与 N3（`meta`）与 `sending` 的先后关系；现网已演进为无 `sending`、Abort/session 主导连发。

【任务】（已不执行）若仍考古，只读 `chat-refactor-agent-tasks.md` 附录归档段与 `contract.md`。
```

### 6.5 契约-only 同步（任意阶段）

```
【角色】文档。

【任务】对照本次 PR 改动的路由/Schema/Model，更新 docs/contract.md：最后更新日期、相关接口小节；若有对接歧义写入「契约对齐问题清单」并标「待修复」。

【禁止】改写未改代码的接口语义。

【验收】与 grep 到的实现一致；H5 与管理端字段名并列处不丢 J2/H1/L1。
```

---

## 七、与产品计划的映射（一句话）

| 产品方案 | 工程落点 |
|----------|----------|
| 目标 A 可恢复 | 主链已 R1/R4 + timeline；后续只做回归与 TD-016 展示 |
| 目标 B 连贯可控 | 主链 + **S1–S3**；**S4** 锁质量；**H5 发送策略** 以 **`contract.md` + `chat.html`** 为准 |
| Must M1–M10 | 任务 1–8 + contract |
| Should S1 TD-016 | 阶段 V2 |
| Should TD-020 | 阶段 V3 |

---

## 八、小结

**当前默认节奏**：**V1（S4）→ V2（TD-016）→ V3（TD-020）**；**历史 N2 解锁切片** 已归档（见 §6.4）。开发时用 **第五节基座提示词 + 第六节对应切片**，可保持与已定需求、产品计划、契约三方对齐。

---

## 九、Cursor 详细操作步骤（Plan → Agent → 文档收工）

下列步骤按 **一次「切片」**（例如只做 V1-A、或只做 V2-A）执行；**每轮代码合并前必须完成第十节清单**（你要求「每次修改后相关文档要更新」）。

### 9.1 开轮前（2 分钟）

1. 在仓库里选定 **本节切片 ID**：`V1-A` / `V1-B` / `V2-A` …（见第四节表）。  
2. 本地新建分支：`feat/chat-<切片ID>-<简述>`。  
3. 打开 **`docs/chat-refactor-vibe-coding-plan.md`**（本文）+ **`docs/chat-refactor-agent-tasks.md`** 对应段落，确认 **勿回炉** 范围。

### 9.2 使用 Cursor **Plan**（生成计划）

1. 切换到 **Plan**（或等价「先规划」模式，以你当前 Cursor 版本为准）。  
2. **新建对话**，在输入框用 `@` 附加至少这些文件（可全加）：  
   - `@docs/chat-refactor-vibe-coding-plan.md`  
   - `@docs/chat-refactor-agent-tasks.md`  
   - `@docs/contract.md`（若本轮可能触接口）  
   - `@docs/tech-debt.md`（若本轮触 TD-016/TD-020）  
3. **粘贴「块 A：Plan 开题」**（见第十一节），把 `【切片】` / `【DoD】` 改成本轮内容。  
4. 生成计划后 **人工检查三点**：是否要求改 `chat.py` 主链、是否漏掉 **第十节文档**、DoD 是否可执行。不通过则 **在 Plan 里追问** 或缩小范围。

### 9.3 切到 **Agent**（写代码）

1. 新开或续接对话，切换到 **Agent**（可写代码模式）。  
2. **粘贴「块 B：Agent 执行」**（第十一节），附上 Plan 里已定稿的步骤列表（可复制 Plan 输出）。  
3. 让 Agent **按步骤改代码**；每完成一步，要求其 **口头勾选 DoD**；若某步会动接口/字段，**同一步内**完成 `contract.md` 草稿修改（不要留到合并前一夜）。

### 9.4 合并 / PR 前（收工闸）

1. 跑本轮相关命令（如 `pytest` 指定目录、或你项目惯例的 lint）。  
2. **强制执行第十节「文档联动清单」** — 缺一项则 **不合并**。  
3. PR 描述里写三行：**改动摘要**、**已更新文档列表**、**契约风险（无则写无）**。

---

## 十、每次修改后的「文档联动清单」（强制）

> 原则：**代码有行为或结构变化 → 对应文档必须同 PR 更新**；仅改错别字可只改一处。  
> **「今天」**：以你合并当日为准，更新 `contract.md` 顶部 **最后更新**。

| 本轮改动类型 | **必须**更新的文档 | **建议**更新的文档 |
|--------------|-------------------|-------------------|
| 任意 **HTTP API**（路径/Query/Body/响应字段/错误码） | `docs/contract.md`（相关小节 + 顶部日期）；若有歧义追加 **契约对齐问题清单** | `docs/chat-refactor-agent-tasks.md`（若任务状态/映射表变化） |
| **数据库** 表/列/枚举默认值 | `docs/contract.md`（关联表说明）；若有 DDL 脚本，在 `docs/tech-debt.md` 或项目约定的 schema 说明处补一句 | `docs/chat-refactor-implementation-plan.md`（仅当阶段模型与 §五 长期结构不一致时） |
| **仅 H5** `chat.html` 行为（无后端字段变化） | `docs/contract.md` 中 **POST /api/chat/send** 或 **H5 实现说明**（若 UX 与契约描述不一致则必改）+ 顶部日期 | `docs/chat-refactor-agent-tasks.md`「后续里程碑」**状态**（如 S4 完成勾选） |
| **仅脚本 / e2e** | `docs/contract.md` 仅当脚本**改变了对接方式**（例如默认测新接口）；否则在 **`docs/chat-refactor-vibe-coding-plan.md` 第四节** 或脚本顶部注释写 **运行方式** | `docs/chat-refactor-vibe-coding-plan.md` 的 DoD 表可加「脚本已覆盖」脚注 |
| **TD-016 / TD-020** 进度变化 | `docs/tech-debt.md` 对应 TD 小节状态说明 | `docs/chat-refactor-agent-tasks.md` 任务 9 等 |
| **产品确认点**（如 H5 发送策略变更） | `docs/chat-refactor-agent-tasks.md`「已定稿 / 后续里程碑」 | `docs/chat-refactor-implementation-plan.md` §十三 |
| **纯文档**（无代码） | 被改文档自身 + `contract.md` 日期若你改了契约正文 | — |

**合并前自检口令（可贴给 Agent）：**

```
本轮代码已改完。请按 docs/chat-refactor-vibe-coding-plan.md 第十节执行：
1. 列出「必须更新」的文档是否都已改；缺则补改。
2. 更新 docs/contract.md 顶部「最后更新」为今日（若本轮触达契约）。
3. 用简短列表回复我：改了哪些文件、每份文档改了什么。
```

---

## 十一、粘贴块全集（复制即用）

### 块 A — Plan 开题（生成计划时粘贴）

```
请基于以下仓库文档做开发计划（不要直接大改代码，先输出步骤与风险）：

@docs/chat-refactor-vibe-coding-plan.md
@docs/chat-refactor-agent-tasks.md

【本轮切片 ID】：____（例：V1-A）
【本轮目标】：____
【DoD / 验收】：____

硬约束（必须遵守）：
- TD-015 主链与 S1–S3 已交付；不要计划「重写」backend/routers/chat.py 入队、打包、generation 作废、10104、防抖。
- 计划中每一步都要写清：改哪些文件、如何验收；并单独列出「本轮结束后必须更新的文档」（对照 vibe-coding-plan 第十节）。
- 若涉及 API/DB，计划里必须包含「同步更新 docs/contract.md」的步骤。

输出：有序步骤表 + 风险 + 文档更新清单。
```

### 块 B — Agent 执行（写代码时粘贴）

```
你是本仓库开发者。已批准的步骤如下（粘贴 Plan 输出）：
<<<在此粘贴 Plan 的步骤表>>>

执行要求：
1. 严格按步骤最小 diff 修改；中文注释 UTF-8。
2. 每完成一步，回复进度并勾选对应 DoD。
3. 任何 API/Schema/DB/H5 可见行为变化，必须在本轮同一对话内更新 docs/contract.md（顶部最后更新日期 + 相关小节），并符合 .cursor/rules/docup.mdc。
4. 对照 docs/chat-refactor-vibe-coding-plan.md 第十节更新其他文档（agent-tasks / tech-debt / 本文第四节状态等）。
5. 禁止回炉 chat 主链；若发现与契约冲突，先停下来列出冲突再问我。

先做：从仓库 Read/Grep 确认当前实现，再动手。
```

### 块 C — 仅文档同步（无代码或契约追平）

```
@docs/contract.md
对照当前 backend 路由与 Pydantic Schema、ORM 字段，做一次契约追平：
- 更新顶部「最后更新」为今日；
- 只改与本次代码一致的条目；
- 新歧义写入契约对齐问题清单「待修复」。

不要改业务代码。
```

### 块 D — 第五节「基座」增强版（强制带文档）

（在第五节原文基础上，把下面两句追加到你每次贴的基座提示词末尾即可。）

```
5. 本轮结束必须执行：docs/chat-refactor-vibe-coding-plan.md 第十节文档联动清单；缺一项不得宣称完成。
6. 最后用项目符号列出：改动的代码文件 + 改动的文档文件 + contract.md 是否已更新日期。
```

---

## 十二、（可选）在工单里记录的「一轮一行」模板

```text
切片：V__
PR：
代码：
文档：contract / agent-tasks / tech-debt / vibe-plan（勾）
验收：DoD 已勾选项：……
```
