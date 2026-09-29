# Diary Api

- 文档 ID：`contract-diary-api`
- 权威状态：`canonical`
- 功能范围：`diary`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-006`, `TD-007`, `TD-013`, `TD-014`, `TD-018`

### 模块：H5 日记（`/api/diary`）

#### GET /api/diary/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`（1–50）
- **响应**：`ApiResponse`；`data` 为 `DiaryListResponse`：`items`（`DiaryItem`: id, content, relationship_level_at_creation, is_read, created_at, **covers_beijing_date** 可为 `null`）, total, page, page_size
- **说明**：成功响应 JSON **从不**包含 `diaries` 键；客户端须使用 **`items`**（与全局「字段命名规范」一致）。**`covers_beijing_date`** 为日记所覆盖的**北京日历日**；H5 列表日期展示优先使用该字段，缺失时回退 **`created_at`** 的本地解析（旧数据 H2 不回填）。
- **内容安全（产品已定案）**：AI 日记正文为系统生成内容，**当前**不对 LLM 输出做与 H5 用户消息同款的独立 `check_content`；合规边界以 PRD 与本条为准。
- **生成侧超时**：服务端调用 **`llm_client.chat_sync`** 未显式传 `timeout_sec` 时，单次 HTTP 上限为 **`get_llm_timeout_seconds()`**（环境变量 **`LLM_TIMEOUT`**，默认 **45s**）；内层重试与退避见 **「部署与网关」—「环境与通用 LLM HTTP 超时」**。
- **关联表**：ai_diary
- **状态**：已实现

#### POST /api/diary/{diary_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **Path**：`diary_id` int
- **响应**：`ApiResponse`；失败 `ERR_DIARY_NOT_FOUND`
- **关联表**：ai_diary
- **状态**：已实现

### `frontend/pages/diary.html`（H5 日记页）

- **接口**：仍仅消费 **`GET /api/diary/list`**（`items`）、**`POST /api/diary/{id}/read`**；**`items[]`** 含 **`covers_beijing_date`**（可为 `null`）。
- **初始化**：**不**以 `GET /api/relationship/status` 阻塞日记列表；关系等级在后台并行更新，用于空状态文案（`relationship_level` 仍可读 `localStorage` 兜底）。
- **布局**：**`.diary-hero`** 头图 **`/static/images/diary/dary_ri.png`**；**`.diary-main`** 列表区 **`margin-top: calc(-17vh + 60px)`**（与头图渐变叠压，小屏 **`-40px`**）；返回钮见摘要「淡薰衣草圆钮」；**`body.h5-skin.diary-page`** 页面底 **`#f3f0ff`**（覆盖全站 neo 渐变底，仅本页）。
- **列表日期（左栏）**：优先 **`covers_beijing_date`** 解析为 **英文月缩写（如 MAY）+ 日数字 + 中文星期**；无覆盖日时回退 **`created_at`** 的本地日历分量；底部装饰图标 **`getDay() % 4`** 四选一 SVG，**无业务含义**。
- **列表正文（右栏）**：**`content`** 默认 **3 行**截断；**「继续看 >」** / 展开后 **「收起」**；整卡点击切换；**不展示**头像、昵称、生成时刻、心情标签。
- **已读**：展开时若 **`is_read === false`**，移除 **`.unread`**、**`POST .../read`**；未读样式为淡紫边框/细左边线/右上角点（**非**橙色 **`.unread` 左边线** 旧样式）。
- **空态与失败**：无数据时展示原有等级分支空状态（文案不变）；列表首屏失败时展示 **`#empty-error`** 与 **「重新加载」**（重置分页后重新 `init`）；`showEmptyState` 会先隐藏其它空态/错误块，避免叠显。
- **分页**：首屏或后续页无更多数据时置 **`noMore`**，避免无意义触底请求。

---

<a id="voice-activity"></a>
### 日记与语音活动来源

日记候选窗口及P0近期互动判定按语音connected_at纳入接通活动。正文只引用未删除、未过期且summary_status=ready的摘要；其余情况使用非空、无转写正文的通话事实，不读取生成正文/推理/危机隔离原文，不修改旧三层情绪字段。接口响应和日记表结构保持既有定义；摘要生命周期见[语音数据](../realtime-voice/data.md#postprocess)。
