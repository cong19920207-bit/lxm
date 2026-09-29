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
    - **不**再使用全局变量 **`sending`** 阻塞整段请求或 SSE 消费——**是否允许继续发**以服务端 **10104** 等为准，前端由 **`getOpenWindowUserRows()`** 界定未闭环窗口（与 **`chat_service.fetch_open_window_user_rows`** 一致：最后一条已落库 **非 agent** assistant 之后，**排除** **`data-ai-in-flight="1"`**），**`countOpenPendingUsers`** 仅计窗口内 **`pending_llm` / `failed_timeout` / `failed_error`（≥5 且无叹号）** 预判，外加 **`CHAT_CLIENT_ABORT_MS`（120s）** 客户端中止；
    - **防连点**：`send` 与叹号 **`resend` 共用** 时间戳 **`lastSendOrResendAt`**，在通过内容非空、队列预判之后、**即将 `fetch` 之前**若距上次不足 **`CHAT_SEND_DEBOUNCE_MS`（300ms）** 则 **静默 `return`**。**输入法与回车键**：`#msg-input` 设 **`enterkeyhint="send"`**（软键盘回车键语义；**具体标签以系统为准**），并使用 **`oncompositionend` / `onkeyup`** 同步调用 **`updateSendBtn()`**（与 `oninput` 并列），避免系统中文输入法下发送钮长期 **`disabled`**。
    - **发送键与键盘**：`#send-btn` 声明 **`type="button"`**；**`updateSendBtn()`** 按 **`trim`** 同步 **`disabled` 属性** 与 **`.disabled`** 类，禁用态样式背景 **`#D8D8DC`**、前景 **`#8E8E93`**，有内容时可点；**`setupSendBtnKeepKeyboard()`** 在 **`initChat`** 中注册 **`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听，内 **`preventDefault`**，避免点击发送时焦点从 **`#msg-input`** 移到按钮导致移动端键盘自动收起；
    - **`handleSend`** 仍仅由 **`click` / `onclick`** 触发（与 debounce、SSE 会话快照逻辑无冲突）。`consumeChatSse` 仅当传入的会话快照与 **`chatSendSession`** 一致时继续解析；收到 **`meta`** 后记录本连接 **`generation_id`** 与 **`message_count`**；若 **`delta`** 携带 **`generation_id`** 且与 **`meta`** 不一致则丢弃该条；
    - 收到 **`done`** 时**先** **`markOpenWindowUsersDelivered()`**（窗口内 user **`data-delivery`→`delivered`**，**resend** 成功亦同），**再** **`finalize(done.messages)`**（**不可**颠倒）；若有 **`emotion.label`** 调用 **`updateChatBackgroundEmotion`**。**10104** 或前端满队预判后仍 **`loadTimeline(true)`**（向列表底部追加 timeline，**不**清空 DOM、**不**回写已有行 **`data-delivery`**，**非**完整自愈）。
    - 服务端 DB / Redis 仍为权威真相，本段约束端上 **`data-delivery` 预判** 与 SSE 展示不串台。
  - **`delta`**：`{"type":"delta","content":"...","message_index":<0≤i<N>}` — 按条推送增量文本，`message_index` 标识目标气泡槽位（§2.9.4）
  - **`done`**：`{"type":"done","messages":[{"type":"text","content":"..."},...],"emotion":{"label":"...","confidence":0.0~1.0}}` — 完整 messages 数组为真相源（§2.7.5），整轮一个 emotion 对象（§2.7.3）；H5 收到后按 `done.messages` 渲染 N 个独立气泡，禁止预铺空气泡
  - **`failed`**：`{"type":"failed","code":<int>,"message":"..."}` — 超时/LLM 失败、**Step5 对外 `messages[].content` 任一条内容安全拦截**（`code`**10101**，见 **STEP-012** / §9.1）等，**不**写入 assistant 行
  - **`obsolete`**：本连接对应代已被新输入作废
- **失败（未进入 SSE）**：`ApiResponse` JSON — 如 **10101** 内容安全、**10104** 队列满（无叹号时未处理 ≥5）、**10102** 等；返回 **10104** 前若未闭环行**均为 `pending_llm`**，服务端 **异步补跑** 一轮 bundle（见顶栏 **2026-06-04 队列死锁修复** 摘要），**仍返回 10104**，客户端宜提示等待后刷新 timeline
- **语义摘要**：用户输入内容安全通过后 **立即** 写入 user 行（`delivery_status=pending_llm`）；打包调度 **防抖**（默认 500ms，配置 `CHAT_DEBOUNCE_MS`）；主链路 Step5 LLM 超时 **45s**（`LLM_TIMEOUT_CHAT`）；Step5 解析成功后 **先** 对 **`inner_monologue`** 与 **`messages[].content`** 逐条跑与入队前同款的 `check_content`（§9.1 / §9.3，见 **STEP-012**）：`inner_monologue` 违规仅日志并替换为空串；
  - **任一条 message 违规** → 整轮失败，user 行标 **`failed_blocked`**，不进入 Step5.5、不落 assistant；Step5 messages 全通过后，若 `admin_config` 中 **`step5_5_enabled`** 开启且双门闩命中，则 **追加** Step5.5 润色（HTTP 子超时 **30s**，见 STEP-009 / §2.7.4 D2）；**Step5.5 返回的 messages 亦逐条过安全**，违规则 **回退** Step5 合并后 messages（与 R-BND-06 一致）；
  - 成功闭环后按 **`final_messages` 条数 N** 写入 **N 行** `role=assistant`（每行一条气泡正文，连续 `sort_seq`，共享 `round_id`，见 **STEP-011** / §2.8.1）并异步后置任务（成长、记忆、`ai_emotion` 等；记忆拼接仍用整轮 `ai_reply`）；**Step6 入参仍仅用 Step5 原始 messages 合并结果**，不受 Step5.5 与安全替换后的对外文案影响（R-BND-05）；**Step6 记忆 LLM + 向量 + 关系写回**在落库成功后 **`asyncio.create_task` 异步入队**，不阻塞 SSE（**STEP-016** / §2.8.4 M2）
- **SSE 与后台 bundle 墙钟（`chat.py`）**：`_BUNDLE_WAIT_TIMEOUT_SEC`（默认 **120s**）仅限制 **`_sse_chat_wait_bundle`** 中 `asyncio.wait_for` 等待本代 **`generation` Future** 的最长时间；**不保证** **`_execute_llm_bundle`** 整段在服务端于 120s 内结束。Step1.5、Step5 等调用 **`llm_client.chat_sync`** 时，内层至多 **3 次** HTTP + 退避，单次超时分别为 **45s**（Step1.5 `_STEP1_5_TIMEOUT_SEC`）与 **`LLM_TIMEOUT_CHAT`（默认 45s，Step5）**，极端退化下 **SSE 可先返回超时/`failed` 而后台仍在执行**；与 **「部署与网关（对话 SSE）」** 中 Nginx 建议一并阅读。
- **关联表**：conversation_log, emotion_log（异步）；Redis `chat:gen:{user_id}`、防抖键、`ai_emotion:{user_id}` 等；**Step6**（§2.8.4 M2）：成功闭环后 **后台异步** 更新 DashVector 四类记忆文档 + `relationship` 标量/Future（失败不落库、不改 SSE，见 **STEP-016**）
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
- **首屏恢复（2026-06-04）**：**无 `cursor`** 时，若满足 **10104** 同等条件（满队且全 `pending_llm`），服务端在返回 `items` 前 **异步** 调度 bundle 恢复（与 **POST /api/chat/send** 10104 路径共用 `chat_service.trigger_recovery_if_queue_stuck`）
- **assistant / agent 行**：`delivery_status`、`skipped_in_prompt` **键存在且值为 `null`**（A1）
- **关联表**：conversation_log, agent_message
- **状态**：已实现

<a id="voice-timeline"></a>
#### H5语音时间线扩展

H5调用内部get_timeline时固定`include_calls=True`；**include_calls不是公开Query参数**。增加source=call，复用同一sort_seq排序，item增加`call_id,duration_seconds,call_status,summary_status,call_summary`；其他来源这五字段为null。call_summary仅在ready、未过期、未删除时可读；摘要稍后完成只更新原卡片，不新增sort_seq。危机资源以`crisis_resource`安全投影加入，不泄露隔离原文；其他项目为null。

响应no-store。首次拉取含pending摘要时前端3秒后只补拉一次，使用pending_reload标记；用户后续滚动按正常cursor分页，不无限轮询。通话卡片和资源卡为H5扩展，Open v1另按[其原十字段协议](../openapi/api.md#voice-compatibility)投影。语音接口与状态见[语音契约](../realtime-voice/api.md#h5-ui)。

#### 部署与网关（对话 SSE）

- **Nginx**：`location` 代理 H5 **`/api/chat/send`**、**`/api/chat/resend`** 时，建议 **`proxy_read_timeout` ≥ 130s**（在 **`_BUNDLE_WAIT_TIMEOUT_SEC` 默认 120s** 之上留余量），避免网关早于 **`_sse_chat_wait_bundle`** 的 `wait_for` 先断开。**注意**：120s 仅为 **SSE 等待 Future 的客户端侧上限**（见 **POST /api/chat/send** 语义摘要），**不是** `_execute_llm_bundle` 整段墙钟的硬上界；仓库内 `nginx/nginx.conf` 若已为 **300s** 则满足上述要求。旧稿「≥50s、略大于 Step5 单次 45s」**不足以**覆盖 Step1.5 + Step5 多 POST 退避 + Step5.5 等串联场景，以本条为准。

##### 环境与通用 LLM HTTP 超时

- **配置**：环境变量 **`LLM_TIMEOUT`**（秒），由 **`backend/config.py`** 的 **`get_llm_timeout_seconds()`** 读取；**代码默认值 45**（与 **`LLM_TIMEOUT_CHAT`** 默认对齐）。本地/部署时在项目根目录 **`.env`** 中设置（模板见 **`.env.example`**）；**`backend/config.py`** 在 import 时对 **`项目根目录/.env`** 执行 **`load_dotenv`**。
- **语义**：单次 HTTP 上限作用于 **`httpx` 请求**；同一调用仍可能经 **`llm_client.chat_sync` 内最多 3 次 POST**（`LLM_MAX_RETRIES=2`）+ **1s / 2s** 退避。
- **典型落点**（`timeout_sec` **未**传入 **`chat_sync`** 或与 **`get_llm_timeout_seconds()`** 同源）：**AI 日记**（`diary_service` 主/兜底两次 **`chat_sync`**）、**对话记忆提取 LLM**、**管理后台配置发布前人格测试集**（`admin_config_service` → **`chat_with_parse`**）、**`llm_client.chat_stream`**。
- **P0–P4 主动消息（与上条区分）**：**`agent_service._call_llm_for_agent_prompt`** → **`chat_with_step5_parse`**，显式传入 **`get_llm_timeout_chat_seconds()`**（与 H5 Step5 同源，默认 **45s**）；**不**走 **`generate_with_fallback`**。
- **与主链路区分**：H5 **`send`/`resend`** 打包调度中的 Step5 / Step1.5 等使用 **`get_llm_timeout_chat_seconds()`**（**`LLM_TIMEOUT_CHAT`**）或路由内显式常量；**不**因本条而将 Step5 改为读取 **`LLM_TIMEOUT`**。

---
