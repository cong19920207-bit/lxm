# chat-emotion 技术债

- 文档 ID：`tech-debt-chat-emotion`
- 权威状态：`canonical`
- 功能范围：`chat-emotion`
- 必读依赖：无
- 相关技术债：`TD-015`, `TD-016`, `TD-019`, `TD-020`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-015] H5 对话调度与持久化：单路 SSE、落库时机 vs「历史 / 新消息」队列体验（**部分清偿 · 2026-05-11：主链 + H5 连发（无 `sending`、300ms 防抖 + IME）+ 契约已同步**）

> **记录策略**：本条保留**定稿表、术语与排期边界**；**`docs/contract.md`** 已随主链与 **H5 发送策略（`Abort`/`chatSendSession`、队列预判、`lastSendOrResendAt`+300ms、`compositionend`）** 同步。后续体验工单若再改 H5，**优先改契约 + 本节「首版主链 vs 后续排期」**，避免与代码脱钩。  
> **详细实施步骤（阶段、迁移、接口、文件清单）**：见 **`docs/chat-refactor-implementation-plan.md`**。  
> **产品开发方案（两大目标、范围 Must/Should、旅程与规则表）**：见 **`docs/product-development-plan-h5-chat.md`**。

#### 术语（产品侧定义）

- **历史消息**：以「**已收到 AI 回复的那条助手消息**」为分界，**该条之前**（含该条助手及更早轮次）均为历史。
- **新消息（未处理）**：**最后一条历史助手消息之后**、用户新发出且**尚未被本轮 AI 回复闭环**的内容；按用户**输入先后顺序**排队。

#### 历史行为（归档 · 改造前）

- **前端（旧）**：曾用全局 `sending` 贯穿 `fetch`/SSE，易出现「整段结束前无法再发」类体验问题。
- **后端（旧网描述）**：单次 `POST /api/chat/send` → LLM → SSE；**SSE 生成器跑完后**才后置任务写库等叙事，与现网「入队即写 user」已不一致。
- **结论（归档）**：旧网「**一问一答单通道**」与产品期望**不一致**。

**（2026-05 勘误 · 与现网对齐）**：**后端**仍为「**入队即写 user**、**`generation_id` 作废**、**防抖打包调度**、**多 user 一包**」（见 `backend/routers/chat.py`）。**H5（`frontend/pages/chat.html`，2026-05-11+）**：**已移除 `sending`**；**流中再发 / 打断** 依赖 **`AbortController` + `chatSendSession` + `consumeChatSse` 内代过滤**；

**防连点** 为 **`lastSendOrResendAt` + `CHAT_SEND_DEBOUNCE_MS`（300ms，`send` 与叹号 `resend` 共用）**；**系统中文输入法** 下发送钮依赖 **`oncompositionend`/`onkeyup`** 调 **`updateSendBtn`**。细则以 **`docs/contract.md` → `POST /api/chat/send`「H5 实现说明」** 为准。上段「历史行为」仅作**归档**，**不得**当作当前验收依据。

#### 产品期望（目标体验）

1. **打断**：用户已发第一条且 AI 尚未在客户端完成回复时，若再发第二条，则**废弃第一条请求上所有仍在进行的进度**（客户端中止 SSE、服务端取消/忽略该次生成结果），将**两条（及更多）均视为「未处理新消息」**，由后续调度**一次性或按约定规则**交给 AI（具体是一句合并还是多轮结构，实现阶段在 Prompt/接口里定稿）。
2. **背压上限**：同一用户**最多 5 条**未处理新消息（FIFO）。超过时：
   - **客户端**：输入锁定（与现网「等待中不可回车发下一条」类似，但语义变为「队列已满」）。
   - **服务端**：**拒绝**再进入未处理队列（如返回明确错误码/文案，防绕过客户端）。
3. **动机**：对话整体更像连续聊天，而不是「必须等打字机动画跑完才能说下一句」。

#### 与「异步落库 / 不依赖 SSE 读完」的关系

- **不矛盾**：队列模型反而**更要求**把「用户句何时算已接受」「被打断的那一轮助手句是否写库、如何标记」**写清楚**；落库若仍绑在「整段 SSE 结束」，在**主动打断**场景下会**更频繁**出现「用户句未持久化」或「孤儿 LLM 结果」问题。
- **建议一并设计**（实现时定稿即可）：
  - 进入服务端「新消息队列」或用户点击发送瞬间，是否**立即**落库 user 行（或等价可恢复状态）；
  - 被打断轮次：助手不完整输出是否**不写**、是否写占位、是否影响 `sort_seq`/时间线；
  - Redis 队列 vs 仅内存 vs DB 状态机，与多 Tab / 刷新的一致性。
- **清偿本条时**：建议在 PR 或契约中**同时**写清：队列语义、最大长度、打断语义、落库时序；避免只改前端或只改落库一半。

#### 方案与计划（**已定稿 2026-04-09**，清偿前仍以代码为准）

| 项 | 定稿 |
|----|------|
| **LLM 超时** | **仅** H5 对话链路（含同链路的重发/打包调度）使用 **45s** 独立配置；**其余** LLM 调用维持通用 **15s**（与现网 `llm_client` 默认一致）。**不**做「全链路 45」，故与「聊天超时 45」**无冲突**（全链路 45 仅为曾讨论过的假设，已否决）。 |
| **新输入 vs 旧代** | **有新 user 进入未闭环窗口并触发打断时**，进行中的旧 **`generation_id` 作废**，旧 LLM 结果**不落库**（与术语里「新消息打断」一致）。 |
| **Q14=A** | 超过 10 条参与打包时：**最旧 user 行仍保留在 DB**（时间线/后台可查原文），**本轮 Prompt 不再带上**该条；可打标 `skipped_in_prompt`（或等价字段）便于排错。 |
| **Q15=B** | **新 user 成功入队后自动触发**合并调度（对当前**未闭环窗口**打包 + **防抖**，避免连续按键风暴；防抖参数实现时定）。 |
| **Q16 + 确认点 1（选项 1）** | **仅**「用户点击叹号触发的**重发**调度」：**每用户、每未闭环批次、每分钟最多 2 次**。**自动调度（Q15）不计入**该 2 次，单独靠**防抖**把连续入队合并为**少量** LLM 调用。**无**「每 45s / 每分钟定时自动重发」的既定设计：45s 仅为**单次等 LLM 返回**的上限，不是循环周期。故**不会**因「超时 45s + 限流 2 次」天然形成无限自动循环。若日后增加「失败自动重试定时器」，须另设**最大重试次数**与退避，避免死循环。 |
| **Q17=B** | **`POST /api/chat/send` 与重发接口**均支持幂等键（如 `client_message_id` / `Idempotency-Key`），防重复入队。 |
| **Q18=A** | 每次用户点击发送生成**新** UUID；**重发不新建 user 行**，走专用重发语义。 |
| **新发送是否带上轮失败 user** | **是**（在 **Q15=B** 下）：下一次调度对**整个未闭环窗口**打包，**包含**此前超时/失败仍带叹号的 user 行 + **新**入队行（仍受 **10 条窗口 + Q14 裁剪**约束）。用户**仅点重发、未发新句**时，同样是对当前未闭环窗口重调度（与上一致）。 |
| **叹号与落库** | **user 正文在入队成功时即落库**；**叹号**依赖行上**失败/待重试状态字段**（或等价），**非**仅存内存。故：**退出再进 H5**，只要拉 `timeline`/历史且接口带出状态，**可恢复叹号**。**管理后台** `GET .../conversations` 已能看**文本**；是否展示「失败/叹号」图标或列属**可选增强**，非「看不见落库内容」。 |
| **失败 UI** | 参与该代的每条 user 左侧红叹号可点重发；**不走**「走神」助手入库；假 AI 话**不进**统计与记忆链路。 |
| **5 条与叹号例外** | 无叹号时 enforce ≤5；有叹号时可继续输入并突破 5。 |
| **内容安全** | 未通过 → 不入队、无叹号。 |
| **情绪（见 TD-016 / TD-020）** | 采用 **C2**：引入 **`round_id`（或 batch_id）** 关联「多 user + 单 assistant」一轮；**emotion_log** 按轮写**一次**，表意为**用户状态**；**管理端用户详情 →「情绪日志」** 为 **V2-C 只读** Tab + **`GET .../emotion-rounds`**（**不等价**于「后台情绪整包已完工」）；**Admin 短期属性写入、Agent/统计读边** 等见 **TD-020**；H5 是否再按 `round_id` 做展示增强为可选。 |
| **System / 结构化输出（统一轮次，不分单句/多句协议）** | **JSON 形态不改**：仍为 `{"emotion":{"label","confidence"},"reply"}`，与现网 `llm_service._parse_llm_response`、`schemas/chat.py` 的 `ChatDoneEvent`、`prompt_builder.SYSTEM_PROMPT_TEXT` 中【结构化输出指令】一致。**单条发送与多条打包共用同一套输出约束**；差别仅在 **模块 7 User Input** 传入的字符串是「一句」还是「多句合并的一块」（如换行分隔），**emotion** 始终表示**本轮整体用户状态**，**reply** 为**针对本轮的一条**助手回复。实现时建议在 **`SYSTEM_PROMPT_TEXT`** 和/或 **`_build_user_input`** 增加**一两句说明**（用户可能连续发送多段内容，请**综合理解后**仍只输出**一个** JSON 对象），降低模型拆成多个 JSON 或漏字段的概率。**不要求**新增第三层 schema 分支（除非产品后续增字段）。 |
| **实现顺序建议** | 配置 45s → 入队落库与 `generation_id` → timeline/行状态字段 → H5 叹号与重发 → 打包 Prompt 与 10 条裁剪 → 幂等与重发 2 次/分钟 → **TD-016**（`round_id` + emotion_log）→ 契约与常量。 |

#### 超时、自动调度、重发：三者关系（答疑）

| 概念 | 作用 | 是否循环 |
|------|------|----------|
| **聊天 45s** | 单次 HTTP 等 LLM 的最长等待；超时则本轮失败 → 叹号，**不**自动再请求 | 否 |
| **自动调度（Q15=B）** | **事件驱动**（有新 user 入队）+ **防抖**，合并触发 LLM；**不是**定时器每分钟跑 | 否；调用次数由用户发消息频率与防抖决定 |
| **重发限流（Q16 + 确认点 1）** | **仅**限制**手动点叹号**触发的调度 **2 次/分钟** | 否；超限应直接拒绝或提示稍后 |

若你听到的「自动重新发送每分钟一次」**不是**上述设计，而是另一种产品（例如失败由系统每分钟代点重发），**当前 TD-015 未包含**，需单独立项并加**总次数上限**，否则确有循环风险。

#### 「国际化」说明（需求模板用语）

此前「国际化」出现在**需求整合技能**的**通用检查清单**中，表示「若产品要多语言再补需求」；**并非**本项目已提出的功能。当前方案**无** i18n 实施项，可忽略。

#### 清偿 TD-015：代码 / 配置 / 契约变动总表（结合现仓库）

| 层级 | 路径或文档 | 变动要点（摘要） |
|------|------------|------------------|
| 配置 | `backend/config.py`、`.env` 示例 | 新增聊天专用超时（如 `LLM_TIMEOUT_CHAT=45`）；非聊天仍走原 `LLM_TIMEOUT` |
| HTTP 客户端 | `backend/utils/llm_client.py` 或调用处 | 对话调用传入 **45s**（按请求覆盖），避免全局改为 45 |
| 对话路由 | `backend/routers/chat.py` | 入队、落 user、`generation_id`、作废、打包调度、防抖、重发接口、重发 2 次/分钟、超时/失败不落走神 assistant、`_post_chat_tasks` 触发点、SSE `meta`/`generation_id`/错误事件 |
| Prompt | `backend/services/prompt_builder.py` | `build_chat_prompt`：**user_input** 改为「本轮打包字符串」；**SYSTEM** 或 `_build_user_input`：**结构化 JSON 说明**补充「多段合并理解、仍单 JSON」；**embedding** 是否用**末条/合并**文本需实现时定 |
| LLM 解析 | `backend/services/llm_service.py` | `chat_with_parse` 可接**超时参数**；聊天失败路径**不向对话 SSE 输出**走神正文（与 TD-015 失败 UI 一致） |
| 模型 / 库 | `backend/models/conversation_log.py`、`schema_ddl.sql`、迁移脚本 | `round_id`（可与 TD-016 分阶段）、user 行**送达/失败态**、`skipped_in_prompt` 等 |
| Schema / 常量 | `backend/schemas/chat.py`、`backend/constants.py` | `ChatSendRequest` 扩展幂等字段；队列满、重发限流等 **ERR_*** |
| 记忆 / 后置任务 | `backend/routers/chat.py` 内 `_post_chat_tasks`、`backend/services/memory_service.py` | 记忆拼接**多 user + 单 reply**；成长值/Redis `ai_emotion` **每成功闭环一次** |
| 时间线 / 管理端 API | `backend/routers/chat.py`（timeline）、`backend/routers/admin/users.py`（conversations） | `items` 带出失败态；Admin 列表字段契约对齐 |
| 测试 | `tests/test_chat.py`、`scripts/test_chat_e2e.py` 等 | 断言不再依赖「走神」助手落库；补超时/幂等/打包用例 |
| H5 | `frontend/pages/chat.html` | 叹号、45s 与首包纠偏、防抖发送、幂等头、Abort 旧代、timeline 渲染状态 |
| Admin | `admin/pages/user-detail.html`（历史对话 Tab；**情绪日志 Tab · V2-C**） | 可选列：失败态；情绪 Tab：`GET .../emotion-rounds` |
| 契约 | `docs/contract.md` | `POST /api/chat/send`、SSE 事件、timeline 字段、错误码、异步写入语义更新 |
| 技术债 | 本文 **TD-016 / TD-020** | **TD-016** V2-A/B/C：`round_id`、按轮 `emotion_log`、**只读**情绪 Tab；**TD-020**：后台情绪运营剩余项 |

#### 首版主链 vs 后续排期（**勿重复开发**）

| 类别 | 说明 |
|------|------|
| **已在首版 TD-015 任务 1–8 范围交付（代码侧，勿重做）** | 聊天 **45s**、**`CHAT_DEBOUNCE_MS`**、**`delivery_status` / `skipped_in_prompt`**（库须已迁移）、**入队即 INSERT user**、Redis **`generation_id`** 与作废、**防抖打包**、**未闭环窗口 ≤10 + Q14**、**叹号 + `POST /api/chat/resend` + 2 次/分钟**、**幂等键**、**`GET /api/chat/timeline`** / **Admin `GET .../conversations`** 字段对齐、H5 **Abort + `meta.generation_id` + ≤5/叹号例外**、`docs/contract.md` **主文**已多轮同步等。 |
| **仍待后续排期（产品工单驱动，非主链阻塞）** | **H5 连发与防抖已演进（2026-05-11）**：**无 `sending`**，**300ms** 静默防抖 + **IME** 同步发送钮 + **`Abort`/`chatSendSession`**（见 `frontend/pages/chat.html`、`docs/contract.md`「H5 实现说明」）。**S4 回归清单**须按清单内 **2026-05-11 勘误** 更新用例表述。**S4**、气泡/叹号边角体验等见 **`docs/chat-refactor-agent-tasks.md` →「后续里程碑」**、**`docs/chat-refactor-implementation-plan.md` →「十三、后续增量」**；**勿**重复实现后端入队/作废/防抖。 |
| **与 TD-016 / TD-020 边界** | **TD-016**：`round_id`、按轮 `emotion_log`、**Admin「情绪日志」只读 Tab**（V2-C）**已交付**。**TD-020**：**广义后台情绪**（短期属性 Admin 写入/修订、Agent/统计读边、产品文案）**仍进行中**（V3-A 基座已落地）。H5 连发与 **TD-020** **互不阻塞**。 |

#### 清偿 TD-015 时建议改动的页面/接口清单（简表，与上表互补）

| 类型 | 位置 |
|------|------|
| H5 | `frontend/pages/chat.html` |
| API | `POST /api/chat/send`、重发路由、`GET /api/chat/timeline` |
| Admin | `admin/pages/user-detail.html` → `#conversations-list`；`GET /api/admin/users/{user_id}/conversations` |
| 后端核心 | `chat.py`、`prompt_builder.py`、`llm_service.py`、`llm_client` / `config`、`conversation_log`、Redis |
| 契约 | `docs/contract.md` |

### [TD-016] 按轮情绪（`round_id`）与后台「情绪日志」只读展示（**V2-A/B/C 已交付；广义后台情绪运营见 TD-020**）

- **状态（2026-04-16）**：**在 V2-A/B/C 约定范围内已交付** — **V2-A** 可空列 + 迁移；**V2-B** **`_persist_bundle_success`** 写入同轮 `round_id`；**V2-C** **`GET /api/admin/users/{user_id}/emotion-rounds`** + **`admin/pages/user-detail.html` →「情绪日志」Tab**（**只读**列表、`super_admin`/`ops_admin`）。契约见 `docs/contract.md`。
- **与「后台情绪未完」的口径**：若指 **只读按轮列表 + 接口**，本条目**已闭环**；若指 **运营可改短期属性、策略/统计显式消费情绪分层、统一后台文案** 等整包能力，**未完成部分归 TD-020**（及本条「可选后续」），**勿**与 V2-C 混为一谈。
- **背景**：TD-015 定稿采用 **C2**：多 user + 单 assistant 共享 **`round_id`（或 batch_id）**；**emotion_log 每轮一条**，语义为**用户状态**（非逐条 user 绑定 `conversation_id` 的语言情绪）。
- **当前处理**：与契约「关联表说明：`round_id`」及 Admin 用户模块 **emotion-rounds** 条目一致。
- **可选后续（不阻塞本条）**：
  1. **H5**：头像/联动情绪是否改为显式按 `round_id` 聚合展示（现网仍可依赖最近一条 `emotion_log` / Redis 等既有路径）。
  2. **`emotion_log.conversation_id` 改挂 assistant** 等策略若产品要改，另开变更单。
- **依赖**：已满足（TD-015 打包与闭环路径清晰）。
- **风险等级**：**低**（管理端只读；主链未改）

### [TD-019] H5 多 Tab 同账号并行聊天：各 Tab 独立 SSE 会话，未跨 Tab 同步「当前有效代」（**待评估**）

- **背景**：`frontend/pages/chat.html` 使用页内 **`chatSendSession`** + **`meta.generation_id`** 防止**同一 Tab** 内旧 SSE 串台；**每个浏览器 Tab** 拥有独立 JS 上下文，**不**与其它 Tab 共享会话令牌或服务端 Redis `chat:gen:{user_id}` 的展示态。
- **产品决策（2026-04）**：**接受现状（D2a）**——以 **DB + `GET /api/chat/timeline`** 为权威真相；多 Tab 各自消费各自流，**不**在首版做跨 Tab 单代 UI 强一致。
- **问题 / 风险**：同账号**多 Tab 同时发送**时，各 Tab 气泡可能短暂与用户「单线对话」心理模型不一致；**刷新页面或依赖 timeline 纠偏**后可与服务器对齐。若未来用户投诉或运营质检提出，再评估是否值得做 **BroadcastChannel**、**轮询当前代**、**WebSocket** 等方案。
- **当前处理**：无代码改动需求；本条目仅作**技术债留痕**，便于后续「有问题再说」时快速定位口径。
- **待处理（可选）**：收集反馈 → 产品确认是否升级为「多 Tab 仅认一条活跃代」→ 选型与排期。
- **触发时机**：明确投诉、或需与竞品「单会话多端同步」对齐时。
- **风险等级**：**低**（体验口径，非安全/计费核心路径）
- **关联**：`docs/contract.md` → H5 `POST /api/chat/send` 节「H5 实现说明」；`docs/product-development-plan-h5-chat.md`（真相在服务端）；集成脚本 **`scripts/test_chat_e2e.py`** 仍以 **HTTP+SSE 手工长测** 为主、**不**纳入默认 CI（见根目录 **README**「开发与测试」）。

### [TD-020] 用户短期情绪属性：与句级 / 轮级情绪分层及展示「真相源」（**进行中 · V3-A，2026-04-15**）

- **背景（产品分层）**：对话里存在三类不同粒度、**不可互相替代**的情绪语义——（1）**句级**：`conversation_log` 上 user 行的 **`emotion_label` / `emotion_confidence`**，仅表示**该句用户文本**的情绪识别结果；（2）**轮级**：LLM 结构化输出中的 **`emotion`**，整包 user 输入对应**一条**助手回复时的综合状态，落库路径与 **TD-016**（`emotion_log` 按轮、`round_id`）对齐；（3）**用户短期情绪属性**：跨多句、多轮的**相对稳定**的「当前情绪画像/属性」，供关怀策略、运营或后台「用户情绪日志」使用，**非**单句字段、**非**单轮 `emotion_log` 可完全承载。
- **产品目标（清偿后应达到）**：在**不大改**现有句级识别与轮级闭环的前提下，**新增**可版本化的「短期属性」来源（例如独立字段、独立表或派生视图），由 **Admin 用户情绪日志**（或等价管线）写入/修订，并与 **句级、轮级** 在数据模型与 API 契约中**显式区分**；H5 / 关系接口等消费方可按场景选择读句级、读轮级或读短期属性，**避免**三者在展示与统计上混为一谈。
- **口径说明（2026-04-16）**：口头「**后台情绪还没做完**」在团队中多指 **本条待办**（Admin 写入/修订短期属性、Agent/统计读边、文案）；**TD-016** 的「情绪日志」Tab 仅为 **只读按轮列表**，**不**覆盖本条产品目标。
- **与确认点 5（Redis vs DB）的关系**：当前 **`ai_emotion:{user_id}`（Redis）** 与 **`GET /api/relationship/*` 的 `ai_current_emotion`** 偏**展示与低延迟**；**`emotion_log`（DB）** 偏**审计与统计**。清偿本条时须在 **`docs/contract.md`** 写清：**展示态可短时不等于 DB 最新一行**（毫秒～秒级可接受）、**审计以 DB 为准**；若未来产品要求「关系页与 DB 强一致」，再评估关系接口读 **`emotion_log` / 短期属性** 或增加缓存失效策略（**不**阻塞 TD-015 多条输入与 TD-016 轮级落地）。
- **依赖**：**TD-016**（`round_id`、按轮 `emotion_log`、**只读**情绪日志 Tab）稳定后，再落「短期属性」主存储与 **Admin 侧扩展能力**，避免同一窗口内两套迁移互相踩踏。
- **V3-A 已实现（切片闭环）**：
  - **Redis 热读热写**：键 **`user_emotion:{user_id}`**，值 JSON（`label` / `confidence`）；TTL 来自环境变量 **`REDIS_USER_EMOTION_TTL`**（秒），`backend/config.py` 中 `get_redis_user_emotion_ttl_seconds()`，**不**与 `ai_emotion:{user_id}`（仍 86400s 硬编码）混用。
  - **DB 冷备**：表 **`user_short_term_emotion`**（`user_id` 唯一，含 `emotion_label`、`confidence`、`payload` JSON 文本、`updated_at`）；每轮成功闭环后置任务 **`_post_bundle_success_tasks`** 内与 Redis 同路径 **upsert**，保证 **TTL 到期前已持久化**；Redis miss 时打包 LLM 路径读 DB，再回退 **`emotion_log` 最新一条**（与改前 Prompt 行为兼容）。
  - **读边界**：**仅** `backend/routers/chat.py` 的 **`_execute_llm_bundle`** 经 **`user_short_term_emotion_service.read_for_prompt`** 读短期属性；**`POST /api/chat/send` 首段不新增 Redis 依赖**。
- **待处理（清偿本条剩余）**：Admin 侧写入/修订短期属性、与 Agent/统计 的显式读边界、产品文案；本条状态在 V3-A 合并后可改为「部分清偿」或保留「进行中」直至 Admin 与策略闭环。
- **触发时机**：产品确认要上线「用户情绪画像 / 后台情绪日志驱动策略」时排期。
- **风险等级**：**中**（与情绪相关统计、Agent 触发、运营解释强相关，需产品文案配合）
- **关联**：**TD-015**（句级 user 行不大改）、**TD-016**（轮级）、`docs/contract.md` H5 对话与关系模块、`backend/services/relationship_service.py`（`ai_current_emotion`）。
