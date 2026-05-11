# H5 对话队列 / 落库 / 叹号重发 — 详细修改方案

> 依据 **`docs/tech-debt.md`** 中 **TD-015**（已定稿 2026-04-09）、**TD-016** 与现网 **`docs/contract.md`** H5 对话模块整理。  
> **产品开发方案（两大目标、Must/Should、用户旅程）**：**`docs/product-development-plan-h5-chat.md`**。  
> **按顺序任务 + AI 提示词**：**`docs/chat-refactor-agent-tasks.md`**。  
> **清偿 TD-015 后**须同步更新 **`docs/contract.md`**；本文不替代契约正文。

---

## 一、需求快照（验收导向）

| 编号 | 需求 | 来源 |
|------|------|------|
| R1 | 用户发消息后 **入队成功即落库** user 行；再进页 / 拉 timeline **可见** | TD-015 |
| R2 | **新输入打断**时旧 `generation_id` **作废**，旧 LLM 结果 **不落库** | TD-015 |
| R3 | **被动**关页/断网且未作废时，LLM **已成功**则 **算闭环**（助手可落库，**不**依赖 SSE 发完）；以 **服务端** 为准 | TD-015 |
| R4 | LLM **45s** 超时（仅对话链路）；失败 **红叹号**，**不**将「走神」助手写入 DB/统计/记忆 | TD-015 |
| R5 | 未闭环窗口 **多 user** → **一次** LLM → **一条** assistant；**10 条**参与上限，超出 **Q14=A**（库保留、Prompt 不带上最旧，可打标） | TD-015 |
| R6 | 无叹号时未处理 **≤5**；有叹号可 **突破 5** | TD-015 |
| R7 | **Q15=B**：新 user 入队 **自动调度** + **防抖**；**Q16+确认点1**：**仅**叹号重发 **2 次/分钟** | TD-015 |
| R8 | **send + 重发** 均 **幂等**（Q17–Q18） | TD-015 |
| R9 | 结构化输出 **仍为** `emotion` + `reply`；User Input **统一「本轮一块」**（单句/多句仅内容量不同） | TD-015 |
| R10 | **TD-016**：`round_id`、emotion_log **按轮**、管理端 **只读**「情绪日志」Tab + `emotion-rounds` — **已交付**；**广义后台情绪**（Admin 短期属性写入、Agent/统计读边等）见 **TD-020**，**未完成** | TD-016 / TD-020 |
| R11 | 内容安全 **未过不入队** | TD-015 |

**待补充（非阻塞）**：多语言 / 离线队列 — 未纳入本期。

---

## 二、需求再审（一致性 / 缺口）

| 项 | 结论 |
|----|------|
| 内部一致 | 「5 条 + 叹号例外」「主动作废 vs 被动闭环」「重发限流仅手动」与 TD-015 表一致。 |
| 与旧「产品期望」小节 | 旧文「交给 AI 的拼法」已由定稿「一次 LLM + 打包字符串」覆盖。 |
| 缺口 A | **向量 embedding** 用 **合并文本** 还是 **末条** — **§九 确认点 2** 已采纳实施默认 **末条（B）**；合并串或 **TD-017** 改写为后续优化。 |
| 缺口 B | **防抖**具体毫秒 — 见 **§九 确认点 3**（方案默认：**300–500ms** 可配置）。 |
| 缺口 C | **TD-015 首版** 若 **未** 上 `round_id`，emotion_log 可 **临时** 仍关联「本轮 assistant 行 id」或「最后一条 user 行 id」，**TD-016** 再迁移到 `round_id`（与 TD-016 依赖说明一致）。 |

---

## 三、方案审核（摘要）

| 维度 | 结论 |
|------|------|
| 可行性 | 成立；Redis 存 `generation_id` + 调度锁 + 防抖计时器；DB 存真相。 |
| 风险 | 并发代竞态 → 落 assistant 前 **CAS 校验 generation**；多 Tab → 以服务端为准。 |
| 影响 | 见下文阶段任务表；统计以 **真实 assistant** 为准，不走神入库。 |

---

## 四、阶段划分（推荐）

| 阶段 | 内容 | 产出 |
|------|------|------|
| **P0** | 配置 `LLM_TIMEOUT_CHAT`、对话调用 **45s** 注入 | 超时行为可测 |
| **P1** | `conversation_log` 扩展：**送达状态**、`skipped_in_prompt`（可选）、迁移脚本 | DB 可表达叹号 |
| **P2** | `chat.py`：**入队即写 user**、Redis **generation**、作废、打包字符串、**防抖调度**、**重发接口** + **2 次/分**、LLM 成功后 **立即** `_post_chat_tasks`（按 TD-015），SSE 仅展示 | 核心状态机 |
| **P3** | `prompt_builder`：**本轮 user 块**、SYSTEM/ `_build_user_input` **一两句**合并说明；`llm_service` 聊天失败 **SSE 不输出走神** | Prompt 与错误 UX |
| **P4** | `timeline` / `history` 响应带 **delivery_status**（或等价）；`schemas` + `constants` + 幂等 | API 契约雏形 |
| **P5** | H5 `chat.html`：叹号、Abort、幂等头、**generation** 校验、与 timeline 对齐 | 端上闭环 |
| **P6** | 测试与 e2e 脚本调整；**contract.md** 正式更新 | 可发布 |
| **P7（TD-016）** | `round_id`、`emotion_log` 模型与 Admin「待完成」收口 | 与 TD-015 解耦可并行晚于 P6 |

---

## 五、数据模型与迁移

### 5.1 `conversation_log`（P1/P2）

建议新增（命名可微调，实现时与 ORM 一致）：

- `delivery_status`（或 `outbound_status`）：如 `delivered` / `pending_llm` / `failed_timeout` / `failed_error`（枚举字符串或 tinyint）。
- `skipped_in_prompt`：`bool`，默认 false（**Q14**）。
- **`round_id`**：可 **P7** 再加；P2–P6 若 emotion 需挂接，临时用 **assistant 行 id** 写入 emotion_log（TD-016 再迁）。

**迁移**：新建 Alembic 或项目惯用 `schema_ddl.sql` 增量；**回滚**：删列或置默认。

### 5.2 Redis（P2）

- `chat:gen:{user_id}` → 当前有效 `generation_id`（字符串）。
- `chat:resend_count:{user_id}:{batch_key}` 或滑动窗口，实现 **2 次/分钟**（`batch_key` = 未闭环窗口指纹，如 **最小 sort_seq** 或 **round 临时 id**）。
- 防抖：`chat:debounce:{user_id}` + TTL，或进程内 asyncio 任务（多实例时 **必须用 Redis**）。

### 5.3 `emotion_log`（P7 / TD-016）

按 TD-016：`round_id`、写入策略、Admin 展示；**P6 前** 可维持现关联方式并在 TD-016 一次迁移。

---

## 六、接口与契约变更（实现后写入 contract.md）

### 6.1 `POST /api/chat/send`

- **Body**：保留 `content`；新增 **`client_message_id`**（UUID，必填或推荐）；可选 **`Idempotency-Key`** 与之一致。
- **成功**：仍为 SSE；首条或 `meta` 事件带 **`generation_id`**（JSON 字段名契约写明）。
- **失败**：JSON `ApiResponse`；新增 **队列满**、**幂等重复** 等 `ERR_*`。
- **SSE**：保留 `delta` / `done`；可增加 **`type":"error"`** 或 **`failed`**（仅结束、无走神正文）。

### 6.2 重发（**L1 已定**：用户端路由）

- **路径（契约写死）**：`POST /api/chat/resend`（**用户 JWT**，与 `send` 同鉴权域）。Body 与幂等键以任务 4/6 的 `schemas` 为准（示例：`log_ids` 或 `batch_anchor_sort_seq` + 幂等键）。  
- 语义：**不 INSERT 新 user 行**，仅触发对 **当前未闭环窗口** 的再调度；**计入** 2 次/分钟。  
- **管理端**：**不**提供代替用户在后台页面触发重发的能力（无 `/api/admin/.../resend` 类接口）；运营仅只读查看对话与 `delivery_status` 等字段，重发由 **H5 用户本人** 完成（见 `docs/admin-conversations-extension-analysis.md` **L1**）。

### 6.3 `GET /api/chat/timeline`（及必要时 history）

- `items[]` 增加 **`delivery_status`**（或嵌套在 user 条目内）；**可选** `generation_id`（一般不必每条都带）。

### 6.4 Admin `GET /api/admin/users/{id}/conversations`

- **可选** 增加与 H5 一致的失败态字段，便于列「送达失败」；**非必须**首版。

---

## 七、后端文件级任务清单

| 文件 | 任务 |
|------|------|
| `backend/config.py` | `LLM_TIMEOUT_CHAT`，默认 45；`CHAT_DEBOUNCE_MS` 可选 |
| `backend/utils/llm_client.py` | 支持 **per-request timeout** 或封装 `chat_completion(..., timeout=)` |
| `backend/services/llm_service.py` | `chat_with_parse(..., timeout=45)`；供 chat 路由专用 |
| `backend/routers/chat.py` | 状态机、入队、`generation`、打包、防抖、重发限流、`_post_chat_tasks` 时机、SSE、取消走神 SSE 正文 |
| `backend/services/prompt_builder.py` | `build_chat_prompt(..., bundled_user_text=)`；SYSTEM / `_build_user_input` 文案 |
| `backend/models/conversation_log.py` | 新字段 |
| `backend/schemas/chat.py` | `ChatSendRequest` 扩展；重发 Schema |
| `backend/constants.py` | 新错误码 |
| `backend/services/memory_service.py` | `extract_and_save` 入参 **多 user 文本 + 单 reply** |
| `backend/routers/admin/users.py` | 可选扩展 conversations 字段 |
| `schema_ddl.sql` / migrations | 与上同步 |

---

## 八、前端（H5）

| 文件 | 任务 |
|------|------|
| `frontend/pages/chat.html` | 叹号 UI；`fetch` **AbortController** 与 **generation** 比对；请求头 **幂等**；**45s** 与首包/服务端 timeline 纠偏；防抖与 **≤5 / 叹号例外**；重发调用 |

---

## 九、管理后台

| 文件 | 任务 |
|------|------|
| `admin/pages/user-detail.html` | 历史对话 Tab：**可选** 显示 `delivery_status` |
| 情绪相关页 | 按 **TD-016** 显示「待完成」或延后改 |

---

## 十、测试与发布

- 单测：`tests/test_chat.py` — 去「走神」助手断言；补 **幂等**、**generation 作废**、**重发限流**（mock Redis）。
- E2E：`scripts/test_chat_e2e.py` 若有硬编码走神，需改。
- 网关/Nginx：`proxy_read_timeout` ≥ **45s**（略大于 LLM），避免截断 SSE。
- **contract.md**：P6 合并前更新「最后更新」与 H5 对话节。

---

## 十一、需你确认的实现细节（可选，有默认）

### 确认点 2：向量检索用哪段文本

**背景**：打包多 user 时，embedding 与 DashVector 检索仍要一段 `text`。

**场景 A**：用 **本轮参与打包的合并字符串**（截断到合理长度）。  
**场景 B**：仅用 **最后一条** user（与现网单条发送最接近）。

**推荐**：**B**（成本低、行为可预期）。  
**若选 A**：记忆相关性可能更「全」，但需规定截断与顺序。

**产品侧采纳建议（实施默认）**：**选项 B —— 仅用本轮参与打包中的最后一条 user 原文**做 embedding 与向量检索；与现网「单条发送 = 该句检索」一致。若后续要上「合并串」或 **TD-017**（query 改写），再迭代而不推翻首版状态机。  
**（2026-04-09 产品确认）**：首版 **锁定选项 B**；上线后用数据评估是否引入合并串或 **TD-017**。

**后续优化记录**：见 **`docs/tech-debt.md` [TD-017]**（检索 query 改写 / LLM 重写，待清偿）。

### 确认点 3：自动调度防抖时长

**背景**：Q15=B 需防抖。

**选项**：300ms / 500ms / 800ms（或配置项）。

**已定稿（用户确认）**：**500ms** 作为默认；建议 **`CHAT_DEBOUNCE_MS=500`** 可配置。

---

## 十二、小结

- **无阻塞矛盾**；可按 **P0→P6** 实施，**TD-016** 可 **P7** 并行或紧随。  
- **确认点 2**：实施默认已写为 **选项 B（末条）**；你若要改为合并串，开工前说一声即可。**确认点 3** 已定为 **500ms**。检索 **query 改写**见 **TD-017**（后续优化）。  
- **主链状态（2026-04）**：**P0–P6** 及 **`docs/chat-refactor-agent-tasks.md` 任务 1–8** 对应能力已在仓库 **交付**；**勿重复**实现入队、`generation_id`、防抖打包、叹号重发、timeline/Admin 字段对齐等。  
- **下一步**：**P0–P6 主链以外的增量** 见 **「十三、后续增量」**；动代码前仍建议 **pre-change-analysis** 拆 PR；详见 **`docs/chat-refactor-agent-tasks.md` →「后续里程碑」**、**`docs/tech-debt.md` [TD-015] →「首版主链 vs 后续排期」**。

---

## 十三、后续增量（2026-04 沟通收口 · **待排期，勿与主链重复**）

> **与本文 §一～十一的关系**：本节**不推翻**已定稿的 R1–R9、P0–P6；仅收纳 **主链交付之后** 才实施的 **H5 体验 + 契约补句 + 与 TD-016/TD-020 的边界**。执行时 **不得** 把已在 `backend/routers/chat.py` 实现的打包/作废/10104 等 **再写一遍**。  
> **Vibe coding 排期 + 可复制提示词**：见 **`docs/chat-refactor-vibe-coding-plan.md`**。

### 1. 产品增量（摘要）

- **连发**：在 AI **流式输出未完成**时允许再 `send`；**Abort** 旧连接；**多条 user**（2～5，示例 msg1/msg2）进入**既有**未闭环打包。  
- **气泡**：打断 → **移除**旧进行中 AI 气泡，新气泡在 **当前未闭环 user 序列之后**；超时/失败 → **移除**进行中 AI 气泡，**叹号在 user**；**不重改**叹号破 5 规则。  
- **契约**：`docs/contract.md` 明示 **「允许未完成 SSE 再 `send`」** 与 **Abort / `chatSendSession` / `generation_id`** 的关系（**文档 + H5**：**无 `sending`**、**300ms 防抖**、**IME**；后端语义不变）。  
- **数据模型 `round_id`**：仍归 **TD-016 / P7 / `chat-refactor-agent-tasks` 任务 9**，**不在本节展开 DDL**。  
- **用户短期情绪属性**：**TD-020**，与句级/轮级分层；**本期不大改**句级识别主链路。

### 2. 实现落点（仅索引）

| 增量项 | 主要落点 | 备注 |
|--------|----------|------|
| `CHAT_SEND_DEBOUNCE_MS` 与流中再发 | `frontend/pages/chat.html` | **已定（2026-05-11）**：**移除 `sending`**；`send`/叹号共用 **`lastSendOrResendAt` + 300ms**；连发/打断仍靠 **`Abort`/`chatSendSession`**；详见 `contract.md`「H5 实现说明」 |
| 气泡生命周期 | 同上 | 与 **§八** 叹号/UI 共存，**增量**修改 |
| 契约补句 | `docs/contract.md` → `POST /api/chat/send` | **不重写**已实现 SSE 字段定义 |
| `round_id` / 按轮 emotion | TD-016、任务 9 | **勿并入**本节首版排期必做 |
| 短期情绪属性 | TD-020 | 依赖 TD-016 稳定后再做 |
