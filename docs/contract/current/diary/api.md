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
- **跨端**：与[Open 日记](../openapi/api.md#feed-diary-openapi)共用本人查询及已读。两端均按创建时间倒序，同一创建时间按 ID 倒序。H5 响应继续只含原分页字段。
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

### AppShell 日记页（`frontend/templates/diary.html` + `frontend/static/js/pages/diary.js`）

- **入口**：有 `frontend/app-entry.html` 时由 AppShell 提供 `/pages/diary.html`；缺失时回退下节独立旧页面。本节为源码行为；是否生效以部署入口及构建版本为准。
- **接口与权限**：沿用受保护的 `GET /api/diary/list`、`POST /api/diary/{id}/read`；关系等级并行更新，仅决定空列表文案。不增加心情字段、正文生成或日期查询接口。
- **顶部导航**：返回按钮复用共用 `page-back page-back--dark` 组件（36px 无色玻璃圆底、44px 点击区、18px SVG）；顶栏复用 `page-back-bar` 的 `env(safe-area-inset-top) + 8px` 上边距和左右 12px 留白，日历按钮同步避开顶部安全区；头图及局部文字对比层同时增加顶部安全区偏移，保持图片满宽等比及按钮与原文的相对间隔，避免遮住名字。
- **展示**：原头图 `/static/images/diary/dary_ri.png` 满宽等比显示（width:100%、height:auto），日期栏以 `margin-top:clamp(-210px,-40vw,-110px)` 带动下方信纸整体上移，并以淡紫渐变衔接；七日日期栏、右上角月历、单篇原画信纸及前后篇按钮。正文按接口原文完整显示并保留换行；长文随文档自然滚动。插画头尾保持比例，侧边纹理纵向重复，避免长文拉伸原画；信纸四角以 14px 圆角裁切。
- **固定选纸**：资源顺序为 `calm, happy, curious, missing, worry, shy, sleepy`，索引 `(正整数日记 ID - 1) % 7`，非法 ID 回退 calm。资源是装饰，不代表真实情绪；不展示心情名称、心情读屏描述或按心情添加的示例落款。
- **日期**：优先 `covers_beijing_date`，旧数据回退 `created_at` 本地日历日。七日栏显示当前篇/选中日期所在的周一至周日；同日多篇，日期选择打开接口顺序中的首篇，前后篇可访问其余记录。
- **分页与月历**：首次打开接口首篇；上一篇为接口相邻较早记录、下一篇为相邻较新记录。每次最多请求 50 条、按 ID 去重。打开月历或选择尚未加载日期时串行补齐分页，只有遍历结束才将缺失日期标为无日记；加载失败可重试，当前正文保留。无日记日期展示该日空态，不触发生成。
- **阅读辅助**：七日栏插画缩至单格宽度的 72%、最大 38px，日期/信纸标题等辅助文字使用更深的灰紫色；头图两行浅色文字在原字形位置局部叠加对比度，原图文件、人物、构图及文案不变。底部翻页栏采用轻薄暖纸色圆角浮层和无填色按钮，距视口底部 12px 加安全区、左右留白，最大宽度 560px；相邻日期只显示月日，中央为定位图标按钮（可访问名称“回到最新一篇”），替代“今天”文案。预留正文底部空间，不随长文滚动或折页移动。
- **回到最新一篇（2026-11-06）**：点击中央定位图标打开当前按时间倒序列表中的首篇已有日记，今天无日记时也不落入今天空态；今天有新日记时首篇即今天。已经选中同篇时不重复翻页；沿用阅读后标记规则。七日栏/月历仍能显式选择今天及其他空日期，空日期保留底栏与最近相邻篇导航。无日记或加载/翻页期间禁用定位。
- **翻页**：相邻篇、七日栏和月历的有日记日期统一采用约 620ms 的斜向折线、纸背与阴影揭页；上一篇/更早日期向右翻，下一篇/更新日期向左翻，同一篇不重复动画。长文仍自然滚动，不拆成固定纸页；在顶部选日期保留页面位置，已滚入正文时在折页遮盖下将新信纸定位至视口顶部，不做可见的纵向滚动动画。动画期间防重入，日历按钮暂不可用；减少动态效果时直接切换。首末边界须在确认无相邻记录后禁用。
- **已读**：当前正文实际呈现且折页结束后提交；开场遮罩未退出、后台隐藏、月历遮挡、预取或恢复空日期均不提交。显式关闭月历/恢复可见时补检查当前篇。成功已读在历史快照中保留；同一页面实例已尝试的 ID 不自动重试失败请求。2026-11-04 用户确认：离页后返回创建新页面实例，当前正文实际呈现且服务端仍未读、快照也无成功已读事实时，允许再次提交以补记已读；不恢复旧实例的失败请求队列。
- **状态与生命周期**：快照只保留 selectedId、selectedDate、calendarMonth、cursor、有界 readIds（最多最近 500 项）及共享滚动/焦点状态，不保存日记正文集合。返回重取至所选 ID/日期并恢复位置；所选 ID 已不存在时提示并打开首篇。切账号/卸载丢弃迟到响应并取消动画。
- **空态**：保留关系等级两种原空列表文案；首屏和后续页失败提供重试；月历使用原生模态对话框管理焦点与 Escape 关闭。
- **验证范围（2026-11-03）**：本地隔离候选构建的 Chrome 受控接口与真实 Docker API/MySQL 验证，证据见 `docs/superpowers/plans/execution/evidence/diary-ui-20261103/`；手机 Safari/微信和生产部署未验证。2026-11-06 的最新定位、日历、翻页、已读、返回与账号隔离回归见本轮检查记录（本地留存，未随本次提交；原引用：`../../../../reports/ui-controls-20261106/final-check/summary.json`），使用同一最终候选构建和受控接口。

### `frontend/pages/diary.html`（独立旧页面回退）

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
