# Chat Emotion Api

- 文档 ID：`contract-chat-emotion-api`
- 权威状态：`canonical`
- 功能范围：`chat-emotion`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-015`, `TD-016`, `TD-018`, `TD-019`, `TD-020`, `TD-023`, `TD-030`

### 模块：H5 对话（`/api/chat`）

#### POST /api/chat/send

- **所属端**：H5
- **鉴权**：Bearer
- **请求 Body**：`ChatSendRequest` — `content` string 1–2000；**`client_message_id`** string 可选（≤64，建议 UUID，可与请求头 **`Idempotency-Key`** 一致，幂等语义以服务端实现为准）
- **响应**：**非 JSON 信封**；成功为 `StreamingResponse`（`text/event-stream`）。SSE 事件（JSON 行）包括但不限于：
  - **`meta`**：`{"type":"meta","generation_id":"<uuid>","message_count":<N>}` — 首包（CP2）；客户端应丢弃与当前有效代不一致的流片段（与 TD-015 一致）；`message_count` 表示本轮回复包含 N 条独立消息气泡（§2.9.4）
  - **H5 实现说明（`frontend/pages/chat.html`）**：**表现层（2026-07-11，在 2026-05-23 沉浸底上改版）**：**`body.h5-skin.chat-immersive`**；全屏背景 **`#chat-bg-image`** 由 **`updateChatBackgroundEmotion`** 按 **`done.emotion.label`** / timeline **`emotion_label`** 切换（**`AVATAR_MAP`**，与 **`api.js`** 头像资源同路径）。顶栏三块胶囊（无整条毛玻璃底）：返回 → **`/pages/index.html`**；
    - **`.bar-profile`**（**`#chat-header-avatar`** 固定默认图 + 绿点 +「林小梦」+「在线」）；**`.bar-actions`**（朋友圈 **`icon-feed.png`** / 记忆星云 **`icon-memory-nebula.png`**，透明底、无文案）；**无** **`.more-btn`**。朋友圈：**`loadChatFeedBadge`** → **`GET /api/feed/badge`**，角标 = **`unread_reply_count + new_post_count`**；**`goChatFeed`** 跳转规则同首页（有未读回复带 **`?focus=unread_reply`**）。
    - 气泡：用户半透明紫白字、AI 白玻璃 + 左下紫菱形光点。底栏浮起玻璃 + handle（仅视觉）；**`#msg-input`** placeholder **`想和我吐槽什么…`**；**`#send-btn`** 启用 **`#7C5CFF`**（纸飞机图标），禁用 **`#D8D8DC`/`#8E8E93`**（**`h5-theme.css`** 对 **`.chat-immersive`** 不覆盖发送钮启用态）。**时间展示**：引入 **`/static/js/chat-time.js`**；**`parseMessageTimestamp`** 对无时区 ISO 按 UTC（补 **`Z`**）；
    - **`formatChatTime` / `shouldShowTimeStamp`** 自然日与文案按 **`Asia/Shanghai`**（当天 **`HH:mm`**、昨天/前天/周几/更早 **`YYYY/M/D HH:mm`**；**>5 分钟或跨北京自然日** 或首条显示；周一起算）；消息行 **`data-created-at`**（timeline 用 **`created_at`**，发送用客户端时间）；**气泡内不显示时间**；流式槽位仅 **`.msg-content`**。**失败叹号** **`.msg-bang`** 在用户气泡左侧，flex 垂直居中（送达态业务不变）。
    - **发送与 SSE（逻辑不变）**：每次发起 **`send` / `resend`** 前递增本地 **`chatSendSession`** 并 **`AbortController`** 打断上一请求；
    - **不**再使用全局变量 **`sending`** 阻塞整段请求或 SSE 消费——**是否允许继续发**以服务端 **10104** 等为准，前端由 **`getOpenWindowUserRows()`** 界定未闭环窗口（与 **`chat_service.fetch_open_window_user_rows`** 一致：最后一条已落库 **非 agent** assistant 之后，**排除** **`data-ai-in-flight="1"`**），**`countOpenPendingUsers`** 仅计窗口内 **`pending_llm` / `failed_timeout` / `failed_error`（≥5 且无叹号）** 预判，客户端计时消费服务端 `client-timing`，按原提交起点或可信 effective D 加 transport margin 有界等待（见[客户端同步](../h5-app/api.md#chat-submission-sync)）；
    - **防连点**：`send` 与叹号 **`resend` 共用** 时间戳 **`lastSendOrResendAt`**，在通过内容非空、队列预判之后、**即将 `fetch` 之前**若距上次不足 **`CHAT_SEND_DEBOUNCE_MS`（300ms）** 则 **静默 `return`**。**输入法与回车键**：`#msg-input` 设 **`enterkeyhint="send"`**（软键盘回车键语义；**具体标签以系统为准**），并使用 **`oncompositionend` / `onkeyup`** 同步调用 **`updateSendBtn()`**（与 `oninput` 并列），避免系统中文输入法下发送钮长期 **`disabled`**。
    - **发送键与键盘**：`#send-btn` 声明 **`type="button"`**；**`updateSendBtn()`** 按 **`trim`** 同步 **`disabled` 属性** 与 **`.disabled`** 类，禁用态样式背景 **`#D8D8DC`**、前景 **`#8E8E93`**，有内容时可点；**`setupSendBtnKeepKeyboard()`** 在 **`initChat`** 中注册 **`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听，内 **`preventDefault`**，避免点击发送时焦点从 **`#msg-input`** 移到按钮导致移动端键盘自动收起；
    - **`handleSend`** 仍仅由 **`click` / `onclick`** 触发（与 debounce、SSE 会话快照逻辑无冲突）。`consumeChatSse` 仅当传入的会话快照与 **`chatSendSession`** 一致时继续解析；收到 **`meta`** 后记录本连接 **`generation_id`** 与 **`message_count`**；若 **`delta`** 携带 **`generation_id`** 且与 **`meta`** 不一致则丢弃该条；
    - 收到 **`done`** 时**先** **`markOpenWindowUsersDelivered()`**（窗口内 user **`data-delivery`→`delivered`**，**resend** 成功亦同），**再** **`finalize(done.messages)`**（**不可**颠倒）；若有 **`emotion.label`** 调用 **`updateChatBackgroundEmotion`**。**10104** 或前端满队预判后仍 **`loadTimeline(true)`**（向列表底部追加 timeline，**不**清空 DOM、**不**回写已有行 **`data-delivery`**，**非**完整自愈）。
    - 服务端 DB / Redis 仍为权威真相，本段约束端上 **`data-delivery` 预判** 与 SSE 展示不串台。
  - **`delta`**：`{"type":"delta","content":"...","message_index":<0≤i<N>}` — 按条推送增量文本，`message_index` 标识目标气泡槽位（§2.9.4）
  - **`done`**：`{"type":"done","messages":[{"type":"text","content":"..."},...],"emotion":{"label":"...","confidence":0.0~1.0}}` — 完整 messages 数组为真相源（§2.7.5），整轮一个 emotion 对象（§2.7.3）；H5 收到后按 `done.messages` 渲染 N 个独立气泡，禁止预铺空气泡
  - **`failed`**：`{"type":"failed","code":<int>,"message":"..."}` — 超时/LLM 失败、**Step5 对外 `messages[].content` 任一条内容安全拦截**（`code`**10101**，见 **STEP-012** / §9.1）等，**不**写入 assistant 行
  - **`obsolete`**：本连接对应代已被新输入作废
- **失败（未进入 SSE）**：`ApiResponse` JSON，包括原内容安全、队列、重发额度等拒绝。合法请求先持久准入、SQL 提交确认后消费原 dispatch；startup/周期扫描承担有限恢复。10104、重复请求及只读 GET 不重新派发、不续原 D，核实使用[原提交身份](#submission-status)。
- **语义摘要**：用户输入内容安全通过后 **立即** 写入 user 行（`delivery_status=pending_llm`）；打包调度 **防抖**（默认 500ms，配置 `CHAT_DEBOUNCE_MS`）；新主链回复调用按冻结运行 profile 及原 D 限制（见[召回消费](#m8-retrieval-consumption)），不改变通用/普通 Agent 超时配置；Step5 解析成功后 **先** 对 **`inner_monologue`** 与 **`messages[].content`** 逐条跑与入队前同款的 `check_content`（§9.1 / §9.3，见 **STEP-012**）：`inner_monologue` 违规仅日志并替换为空串；
  - **任一条 message 违规** → 整轮失败，user 行标 **`failed_blocked`**，不进入 Step5.5、不落 assistant；Step5 messages 全通过后，若 `admin_config` 中 **`step5_5_enabled`** 开启且双门闩命中，则 **追加** Step5.5 润色（HTTP 子超时 **30s**，见 STEP-009 / §2.7.4 D2）；**Step5.5 返回的 messages 亦逐条过安全**，违规则 **回退** Step5 合并后 messages（与 R-BND-06 一致）；
  - 成功闭环后按 **`final_messages` 条数 N** 写入 **N 行** `role=assistant`（每行一条气泡正文，连续 `sort_seq`，共享 `round_id`，见 **STEP-011** / §2.8.1）并异步后置任务（成长、记忆、`ai_emotion` 等；记忆拼接仍用整轮 `ai_reply`）；**Step6 入参仍仅用 Step5 原始 messages 合并结果**，不受 Step5.5 与安全替换后的对外文案影响（R-BND-05）；**Step6 记忆 LLM + 向量 + 关系写回**在落库成功后 **`asyncio.create_task` 异步入队**，不阻塞 SSE（**STEP-016** / §2.8.4 M2）
- **SSE 与后台 bundle 时限**：工作区新链以 SQL 准入时刻为起点固定 **180 秒**，Step1.5/检索各 **45 秒**并取原 D 较早者；真实改写单调用 **20 秒**、失败最多一次重试，回复、安全/5.5和提交均受原 D 限制，见[召回消费](#m8-retrieval-consumption)。服务端等待余量与客户端 transport margin 仅用于观察，不能延长业务 D。既有未切换部署的 120 秒等待属于旧环境事实，不能用于推定新链生效。
- **关联与权威**：conversation_log、emotion_log 与 [SQL lifecycle](data.md#chat-lifecycle)；generation owner/epoch/dispatch/终态由 SQL 决定，Redis 仅保留实际防抖、情绪等辅助用途。Step6 在确认成功后后台异步写四类记忆及原关系标量/Future；失败或作废不派发 Step6，后置收尾不能反转已确认成功。
- **状态**：已实现

#### POST /api/chat/resend

- **所属端**：H5
- **鉴权**：Bearer（**与 send 同域**；**禁止**管理端或 `/api/admin/` 代用户重发，L1）
- **请求 Body**：`ChatResendRequest` — `client_resend_id` 可选（≤128）
- **响应**：与 send 成功时相同 **SSE** 契约；当前未闭环窗口 **无** 叹号态 user 时 **10107**（`ERR_CHAT_NOTHING_TO_RESEND`）；超过 **2 次/分钟** 时 **10105**（`ERR_CHAT_RESEND_LIMIT`）
- **语义**：**不**插入新 user 行，仅对当前未闭环失败窗口再次调度 LLM
- **状态**：已实现

#### GET /api/chat/history

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page` int ≥1 默认 1；`page_size` int 1–50 默认 20
- **响应**：`ApiResponse`；`data`: `{ messages: [{id, role, content, emotion_label, created_at}], total, page, page_size }`
- **说明（H1）**：`messages[]` **不保证**包含 `delivery_status`、`sort_seq` 等送达字段；叹号恢复、与 Admin 列表对齐的送达态以 **`GET /api/chat/timeline`** 的 **`items[]`** 为准；history 与 timeline **能力可不一致**
- **关联表**：conversation_log
- **状态**：已实现

#### GET /api/chat/timeline

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`cursor` int 可选；`limit` int 1–50 默认 20；`pending_reload` bool 默认 false
- **响应**：`ApiResponse`；`data`: `{ items: [...], next_cursor, has_more }`
- **`items[]`（conversation_log 来源）**：`source`, `sort_seq`, `id`, `content`, `created_at`, `emotion_label`, **`delivery_status`**, **`skipped_in_prompt`**, `is_read`, `trigger_type`（后两者对 agent 有值）；**`delivery_status` 取值**与 **`backend/constants.py`** 中单点常量一致（示例：`delivered`、`pending_llm`、`failed_timeout`、`failed_error`、`failed_blocked`），**不在**契约全文复制枚举表（J2）；**多气泡**：同一 `round_id` 下可有 **多条** `source=assistant` 行，按 `sort_seq` **升序**即为气泡展示顺序（与 SSE `done.messages` 下标一致，STEP-011）
- **只读恢复投影**：timeline GET 不仲裁、恢复或修改聊天业务状态。持久 dispatch 的 startup/周期有限扫描见 [SQL lifecycle](data.md#chat-lifecycle)；原请求状态核实见 [SubmissionStatus](#submission-status)。
- **assistant / agent 行**：`delivery_status`、`skipped_in_prompt` **键存在且值为 `null`**（A1）
- **关联表**：conversation_log, agent_message
- **状态**：已实现

<a id="voice-timeline"></a>
#### H5语音时间线扩展

H5调用内部get_timeline时固定`include_calls=True`；**include_calls不是公开Query参数**。增加source=call，复用同一sort_seq排序，item增加`call_id,duration_seconds,call_status,summary_status,call_summary`；其他来源这五字段为null。call_summary仅在ready、未过期、未删除时可读；摘要稍后完成只更新原卡片，不新增sort_seq。危机资源以`crisis_resource`安全投影加入，不泄露隔离原文；其他项目为null。

响应no-store。首次拉取含pending摘要时前端3秒后只补拉一次，使用pending_reload标记；用户后续滚动按正常cursor分页，不无限轮询。通话卡片和资源卡为H5扩展，Open v1另按[其原十字段协议](../openapi/api.md#voice-compatibility)投影。语音接口与状态见[语音契约](../realtime-voice/api.md#h5-ui)。

#### 部署与网关（对话 SSE）

- **Nginx**：仓库 `nginx/nginx.conf` 的 **300 秒**为代理 idle timeout，不是整轮业务 D。新链整轮固定180秒，服务端等待余量与 H5 transport margin 见[计时参数](data.md#chat-timing)及[客户端配置](../h5-app/api.md#chat-client-timing)。此前基于旧120秒等待的130秒建议不作为新链有效上界；这些源码/配置事实不代表本轮部署或业务开放。

##### 环境与通用 LLM HTTP 超时

- **配置**：环境变量 **`LLM_TIMEOUT`**（秒），由 **`backend/config.py`** 的 **`get_llm_timeout_seconds()`** 读取；**代码默认值 45**（与 **`LLM_TIMEOUT_CHAT`** 默认对齐）。本地/部署时在项目根目录 **`.env`** 中设置（模板见 **`.env.example`**）；**`backend/config.py`** 在 import 时对 **`项目根目录/.env`** 执行 **`load_dotenv`**。
- **语义**：单次 HTTP 上限作用于 **`httpx` 请求**；同一调用仍可能经 **`llm_client.chat_sync` 内最多 3 次 POST**（`LLM_MAX_RETRIES=2`）+ **1s / 2s** 退避。
- **典型落点**（`timeout_sec` **未**传入 **`chat_sync`** 或与 **`get_llm_timeout_seconds()`** 同源）：**AI 日记**（`diary_service` 主/兜底两次 **`chat_sync`**）、**对话记忆提取 LLM**、**管理后台配置发布前人格测试集**（`admin_config_service` → **`chat_with_parse`**）、**`llm_client.chat_stream`**。
- **P0–P4 主动消息（与上条区分）**：**`agent_service._call_llm_for_agent_prompt`** → **`chat_with_step5_parse`**，显式传入 **`get_llm_timeout_chat_seconds()`**（默认 **45s**）；**不**走 **`generate_with_fallback`**。本轮未改其回复模型、超时或兜底行为。
- **新链的有界调用**：H5/OpenAPI/Step8 的真实 Step1.5 改写按冻结 profile 限单调用20秒及最多一次失败重试；新主链回复按原冻结 profile 和 D。该局部例外不修改本节通用 `LLM_MAX_RETRIES`、普通 Agent 或其它模型调用配置，见[召回消费](#m8-retrieval-consumption)。

---

<a id="m8-retrieval-consumption"></a>
### 新文字链的同源召回与 Prompt 消费

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

主文字、OpenAPI 和 Step8 使用各自原执行身份及截止，从只读同源上下文完成四路真实改写、dense/BM25 双召回、重排及同次 Prompt 选入。`run_pipeline/execute_memory_retrieval` 消费单次冻结配置；`RetrievalResult` 保留 `config_snapshot_id/queries/routes/rewrite_deadline/retrieval_deadline`。改写及检索各45秒，截止取阶段起点+45与原D较早者；四路Step2共享截止并预留候选收口时间。单改写调用20秒、临时失败最多一次重试，250ms退避包含在预算内；鉴权、永久故障和非法输出不重试，迟到结果拒绝。正常、改写降级、单通道失败及 rerank 故障分别呈现，成功重排路保持有效门槛，有可信候选但重排未完成的路融合，无可信候选的路为空。

内部入口须匹配有效 environment/epoch/target fence；`allow_isolated` 仅允许明确 isolated 环境。M4 单独实施时尚未接业务入口的历史边界，已由 M6 实际 `chat_memory_pipeline/step8_memory_pipeline` 接线取代；这不等于业务部署激活。声明运行 environment 时 HTTP/WS/scheduler 冻结同一上下文，SQL flush（含隐式 autoflush）与DML在同事务核 fence；旧 epoch、maintenance 或缺上下文拒写。未配置 environment 不自动开启部署级维护协议，新 writer 仍须显式 activation，具体来源/维护围栏见[记忆接口](../memory-knowledge/api.md)。

每路按自身 final_top_k；角色三路按 character_global→character_private→character_knowledge 逐名次轮转，user 独立预算。计数覆盖整条正文、标题、标签和分隔符，首条放不下即停该路；总超限沿原裁剪优先级，角色逆成功选入序删尾，保留前缀且不补位。最终身份/代/当前正文核验失效时，同路后缀一并淘汰，重新渲染及计数。候选正文是数据，控制字符及模块分隔符转义；标签与 key:value 由可信 metadata 得出，ID/归属保留结构化 DTO，不将正文/Prompt 放入 repr 或日志。[Prompt 结果与身份结构](../memory-knowledge/data.md)不以候选命中替代最终选入。

`reserve_prompt` 在SQL最终核验、持久 claim 和原 D 下重计数，返回 `use_claim_id/use_deadline_at`。`GuardedModelClient.send` 核原 claim、模型及预算，使用原 datetime D 与 monotonic D 较早者；body.complete 后持久确认 handoff，无合法原预留结果不得发送。上下文、检索、回复、安全/5.5及提交均受原D约束；回复模型及人格保持原冻结 profile。诊断只消费同源读取/改写/召回/重排/选入，不调用回复模型、不触发Step6、不写聊天业务状态，诊断操作与历史规则见[记忆后台契约](../memory-knowledge/api.md)。

`PromptBuilder.build_memory_prompt` 返回结构化结果。后台旧 Prompt Test 固定走 `build_legacy_mock_prompt -> str`，保留当前/草稿/override、原角色、原回复模型及 len 文本语义，不调用真实索引；三个只读预览不启用外部调用或业务写，不能由客户端借 mock 开关豁免真实候选身份。普通 Agent 保留原 helper/读取算法。

Step6 在提取模型调用前冻结 writer；`upsert_step6_vectors` 返回 `{counts,items}`，源确认即计源成功，索引 pending 由独立 IndexWorker 恢复；BM25故障不能导致重新提取或重复关系副作用。原11字段、Step5原回复输入、成功后异步边界、标量写回和同 Key 覆盖保持，回执唯一结构见[记忆写入接口](../memory-knowledge/api.md)。

<a id="chat-idempotency"></a>
### 准入身份与重复请求

`chat_service.submit` 经 `chat_lifecycle.admit` 原子保存可信 user、operation、原 request ID、源消息/序号、额度、承接代及 dispatch；锁内归属/窗口使用 current read 并刷新 ORM，避免锁前 RR 旧快照。SQL 提交确认后派发。身份以同用户+operation+原Unicode字节确定，不按 H5/OpenAPI/API key 拆域，不 trim ID。H5 `client_message_id`≤64、`client_resend_id`≤128；OpenAPI 可选 Idempotency-Key 同限。空串合法，缺失/null 生成内部 UUID；send 指纹使用已接受 strip 正文。同ID同输入只读复用原次，异输入10109；不新增 user、扣额度、换代、重复LLM或续 D。resend 冻结原消息集合且不新增user；原2次/60秒额度不因重复请求刷新。

SQL 准入 accepted_at 冻结180秒及计时版本；最终成功决定、提交未知、lease/dispatch 与有限恢复唯一依据见[持久状态](data.md#chat-lifecycle)。10110/未核实期间不可盲重发，不按正文或时间猜请求身份。

<a id="submission-status"></a>
### GET /api/chat/submissions/{operation}/{request_id}

鉴权为原 Bearer 用户，只读 `ApiResponse.data`。operation 为 send/resend；路径 request_id 为 `b64.`+原 UTF8 的规范无填充 base64url（空ID为 `b64.`），非法身份422。OpenAPI 同源定义见[其路由](../openapi/api.md#submission-status)，仅可信 user 自身可读。

| 字段 | 类型/含义 |
|---|---|
| operation / request_id | 原操作与未编码原ID字符串 |
| admission_state | accepted / not_found / expired / unverified |
| processing_state | pending / success / failed / superseded / unverified；not_found/expired 为null |
| status_reason | 有效原因或null；枚举以[SQL状态](data.md#chat-lifecycle)为准 |
| state_origin | lifecycle / unavailable，未找到为null；消息历史投影另可 legacy |
| state_revision | 十进制字符串或null，不能转换为 JS 浮点数比较 |
| status_observed_at | 观察 UTC 时间 |
| accepted_generation_id / effective_generation_id | 原接受代与当前承接有效代，未知为null |
| accepted_at / original_deadline_at / effective_deadline_at | 原接受时间、原代D、当前有效代D，未知为null |
| reconcile_until / dedupe_expires_at | 原核实截止与身份保留截止，未知为null |
| source_messages | 原submission ordinal排序 `{source:'user',id,sort_seq:<十进制字符串>}[]` |
| result | 确认成功为 `{round_id,messages:[{id,sort_seq:<字符串>,type:'text',content}],emotion:{label,confidence}}`，其它null |
| can_resend | 后端原窗口/额度/活动代判断；未知一律false |

读存储失败输出 unverified/storage_unavailable/unavailable，空源/结果且不可重发；过D或lease未知也不伪造成功/失败终态。GET不仲裁、不恢复、不写业务状态。原记录墓碑为expired，与not_found及读取未知分开。

<a id="chat-sse-state"></a>
### SSE 与历史状态投影

原 meta.message_count、delta.message_index、done.messages/emotion 及 failed/obsolete 保留。meta/done 增 `operation/request_id/source_messages/accepted_generation_id/effective_generation_id/effective_deadline_at/reconcile_until/state_revision/can_resend`；delta 增 generation_id/state_revision；done 增 round_id 与已保存 assistant id/sort_seq。成功 messages 仍以最终入库气泡为真相，不预铺空气泡；旧代/低修订不能覆盖新代。H5 的消息身份与有界等待消费见[客户端同步](../h5-app/api.md#chat-submission-sync)，Open 成功仍为 messages/emotion/round_id，原 timeline 十字段不扩展。

Admin既有历史先按原规则计数/分页，再按(conversation或agent,id)批量投影；仅user行增加 processing_state/status_reason/state_origin/state_revision/status_observed_at。origin 可 lifecycle/legacy/unavailable，assistant/普通agent不造user状态；原角色、日期、分页、sort_seq不变，GET只读。后台页面、权限及手动刷新唯一见[后台契约](../admin-security-accounts/api.md#memory-admin-history-state)。

<a id="resend-eligibility"></a>
### GET /api/chat/resend-eligibility

Bearer用户只读 `ApiResponse.data={can_resend,message_ids,state_origin}`。复用原窗口、2次/60秒额度和活动代谓词；候选须确认为 failed_timeout/failed_error 且不是content_blocked。存储未知返回false/[]/unavailable。POST仍重新校验；此接口不自动重发，不给管理端代理用户重发资格。

<a id="client-timing-operation"></a>
### GET /api/chat/client-timing

Bearer用户只读 `ApiResponse.data` 为 `chat_client_timing.CLIENT_TIMING` 的配置投影，不写 SQL/Redis、不调用模型。字段、范围及客户端消费唯一见[H5计时](../h5-app/api.md#chat-client-timing)；返回 timing_config_version/server_timing_config_version。非法参数在 chat router/真实main装载时拒绝，不延长原业务D。

## AppShell 源码增量（2026-10-23）

仅同步客户端生命周期与原提交恢复；以下不增加端点、请求字段、数据库字段或新的重试资格。服务端持久权威和绝对截止仍按[数据契约](data.md#文字准入提交与有限恢复的持久权威)。

<a id="appshell-delta-32"></a>
### SSE与历史状态投影/原提交恢复

原文字提交完整身份/时间/代次/revision/exhausted在旧→新→旧保留；headers等待或流中离页不重发POST，不延期、不重置已耗尽核实。隔离后端重启进一步验证实际客户端保留原提交，服务结果受控。
