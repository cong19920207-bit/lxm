# Observability Admin

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


- 文档 ID：`contract-observability-admin`
- 权威状态：`canonical`
- 功能范围：`observability-third-party`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`
- 相关技术债：`TD-008`, `TD-009`, `TD-010`, `TD-011`, `TD-012`, `TD-033`

### `admin/pages/system-monitor.html`（系统监控）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 仅可读取系统状态。
- **接口**：`GET /api/admin/system/status`（**10 秒缓存**，后端 Redis key `cache:system_status`，已处理）；请求使用 `admin-api.js` 的 **`adminRequest`**，无单独封装函数。
- **响应 `data` 结构**：`cpu:{ percent, cores }`；`memory:{ percent, total_gb, used_gb }`；`disk:{ percent, total_gb, used_gb }`；`redis:{ hit_rate, used_memory, connected_clients }`；`alerts:[{ level:'warning'|'critical', message }]`.
- **展示约定**：四张指标卡为 **纯 SVG 环形进度**（`stroke-dasharray` 控制弧长，周长按 \(2\pi\times34\)）；**Redis 命中率**色阶与 CPU/内存/磁盘相反（高为好）。Redis 卡副文案按产品与需求仅展示 **「已用内存：{used_memory}」**（`connected_clients` 由接口提供但本页不展示）。
- **CPU 趋势**：ECharts 折线，内存数组最多 **60** 点，与前端 **每 10 秒** 拉取一次对齐，覆盖约 **近 10 分钟**；标题为「近10分钟 CPU 趋势」，**不写「近1小时」**。
- **告警列表**：接口无单条时间字段时，各行左侧时间为 **本次刷新时刻**；若未来扩展字段见 **`docs/tech-debt.md` [TD-010]**。
- **生命周期**：`beforeunload` 时 `clearInterval` 释放定时器；`resize` 时 `cpuChart.resize()`。

### `admin/pages/system-logs.html`（系统日志）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 可读脱敏列表，不可导出。
- **Tab**：仅 2 个（`system` / `error`），无第三方服务日志 Tab；`activeKey='system-logs'`，顶栏标题「系统日志」。
- **调用**：`GET /api/admin/system/logs`
  - `log_type` 枚举：`system` \| `error`（对应后端 `_LOG_TYPE_FILE_MAP` → `system.log` / `error.log`）。
  - 日期参数：`YYYY-MM-DD`（`type="date"` 原生值，与后端 `datetime.date` 一致）。
  - 单次查询区间：后端拒绝 `(end_date - start_date).days > 30`；前端前置校验一致。
- **导出**：`POST /api/admin/system/logs/export`（仅 Query，无 Body）；`adminRequest('POST', url)` **不传 `data`** 以走 `admin-api.js` 的 blob/xlsx 下载分支。
  - 单次导出：后端拒绝区间 `days > 7`；前端前置校验与后端一致（避免前后端口径不一）。
- **状态**：`system` / `error` 各自维护 `pageState`（含 `hasQueried`：仅在该 Tab **从未成功请求过列表**时，切换 Tab 自动触发首次 `queryLogs`；**已加载但 0 条**不重复自动请求）；`page_size=50`；分页使用 `admin-api.js` 的 **`renderPagination`**，第四参须为全局回调名字符串 **`window.systemLogsGoPage_system`**（system Tab）或 **`window.systemLogsGoPage_error`**（error Tab），**禁止**传入匿名函数（`renderPagination` 将回调拼入 `onclick`，匿名函数经 `toString` 会丢失闭包，导致翻页无效）。
- **安全**：列表中 `row.message` 经 **`escapeHtml`** 再写入 `innerHTML`；错误详情弹窗用 **`textContent`** 写入正文，防 XSS；`ERROR` 行「详情」按钮传参使用 `JSON.stringify` + `</` → `\u003c/` 及属性内 `&quot;` 转义，避免引号截断属性。

### `admin/pages/third-party.html`（第三方服务监控）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 仅读状态与非敏感配置，凭据仅显示已/未配置，不可保存或测试连接。
- **调用**：`GET /api/admin/third-party/status`（**60 秒缓存**，后端 Redis key `cache:third_party_status`，已处理）；定时 **60s** 刷新；`beforeunload` 时 `clearInterval` 防泄漏。
- **BM25卡片**：与其他服务复用`tp-card/tp-card-head/tp-row`，独立展示本地组件/编码版本、本地编码器、索引初始化、当前索引与待处理数量、回填状态/阶段及扫描进度、检查时间；窄屏改为单列。判定消费[BM25真实状态接口](api.md#bm25-runtime-status)，编码器加载成功不推定初始化或回填完成；无回填记录、总量待确认、需人工处理及状态未知分别显示。读取失败清除旧卡片中的确定状态，缺失字段不默认未初始化/已完成，不能仅凭旧版ready标志亮绿灯。编码版本与所有动态值转义显示，保留完整版本但可换行；只读「查看索引维护」链接不执行修复或回填。BM25状态不复用统计缓存，页面刷新周期仍为60秒。
- **本地真实验收（2026-10-15）**：本次修复已部署local-docker:lxmfor；真实浏览器显示编码器已就绪、初始化已完成并开放、索引114/115与来源待核实1条、无回填记录，黄色汇总状态与HTTP/MySQL一致。验证期间未执行初始化/回填，7张相关状态表前后摘要不变；镜像、截图与证据见[API部署核验记录](api.md#bm25-runtime-status)。生产环境未操作。
- **卡片**：`#service-grid` 为 2×2 栅格；首屏 4 个 `.skeleton`（高 200px）；成功后渲染服务卡。**标题**使用接口返回的 `name`（不硬编码展示文案）；`svcKey` 由前端 `SERVICE_KEY_MAP` 与后端 `_VALID_SERVICES` 路径对齐（`doubao` / `embedding` / `dashvector` / `content_safety`）。
- **内容安全卡**：独立布局，仅 `today_blocked` + 状态灯；代码注释 **TD-003**（与全局 `tech-debt.md` 中 [TD-003] 编号不同指代）：无真实第三方 HTTP 后端，探测为 Redis `banned_keywords`；配置弹窗为说明 +「测试 Redis 连通性」+「关闭」，无保存。
- **配置弹窗（非 content_safety）**：Endpoint（`type=url`）、API Key（留空保留原值）；**保存**初始禁用；**测试连接** 发 `POST .../test-connection`，Body 含表单中**非空**的 `endpoint` / `api_key`（可与已发布配置合并探测）；`connected===true` 后启用保存。**保存**：`PUT .../config`，Body 仅传非空字段；`api_key` 空则不传；须本弹窗内测试通过后才提交（前端校验）；服务端仍会再次测试合并结果。
- **技术债记录**
  - **TD-003（本页注释口径）**：内容安全无独立第三方 API，探测走 Redis；若未来接入真实内容安全服务需后端字段与探测实现。
  - **TD-012作用域**：embedding/rerank/dashvector当前已实现同源resolver/canonical发布，生效仍受具体environment/fence与部署约束；旧业务容器未部署，doubao/content-safety等原流程保留。不能用全体“仍只读环境变量”描述这些工作区增量，见[当前Provider页面](#memory-provider-admin)。

### `admin/pages/dashboard.html`（数据看板）

- **实现状态**：已实现。`activeKey='dashboard'`，顶栏标题「数据看板」。`observer` 仅读并与 `super_admin` / `ops_admin` 一样获得完整看板数据；`tech_ops` 仅提示文案无统计卡片；`ai_trainer` 仅展示 LLM 成功率、人格偏离率等 AI 性能卡片。
- **接口**：`GET /api/admin/stats/dashboard` 的 `data` 为**嵌套对象**（见上文「模块：数据统计」）；卡片脚本内 **`flattenDashboard`** 将 `user` / `retention` / `agent` / `ai_performance` 展平为卡片字段（如 `new_users_today`→`new_users`、`persona_deviation_rate`→`persona_risk_rate`）。
- **趋势图**：`GET /api/admin/stats/trend?metric=...&days=7` 的 `data` 为 **`[{ date, value }]`**；脚本 **`trendListToAxes`** 拆出 `dates`/`values` 再喂 ECharts。
- **告警**：人格偏离 / LLM 成功率 / 次日留存 等阈值判断使用 **`typeof === 'number'`**，避免将 `null` 当 0。

### `admin/pages/data-report.html`（数据报表）

- **实现状态**：已实现。`activeKey='report'`，顶栏标题「数据报表」。`super_admin` / `ops_admin` / `observer` 可访问，observer 不可导出；**`ai_trainer` / `tech_ops`** 跳转 `error.html?type=403`。
- **聚合卡片**：`GET /api/admin/stats/dashboard`，按 **嵌套字段** 读取（`retention` / `conversation` / `ai_performance` 等）；字段为 `null` 时统一展示「—」；标注「(今日)」的指标与后端「当日」统计一致。
- **总注册用户数**：`GET /api/admin/users?page=1&page_size=1` 的 `data.total`（与日期筛选无关，首屏一次）。
- **报表明细与图表**：`GET /api/admin/stats/report?report_type=...&start_date=...&end_date=...&page=1&page_size=100`；Tab 切换后延迟 `onQuery` 刷新当前类型数据；**用户** Tab 期间新增/对话期间总量等由 `list[]` 前端求和。
- **功能使用 Tab**：后端 `feature` 行字段仅 `date` / `agent_sent` / `agent_opened` / `reply_rate`；缺按日 `open_rate` / `agent_replied` 见 **TD-009**。
- **AI 性能 Tab**：折线图为 **人格偏离率按日**（`list[].deviation_rate`），非 LLM 响应时长；见 **TD-008**。
- **导出 Excel**：`adminRequest('POST', url)` **不传 `data` 参数**，URL 含 `report_type`、`start_date`、`end_date` Query，由 `admin-api.js` 识别 `spreadsheetml` 触发 blob 下载。
- **图表**：ECharts；`chartInstances` + `getChart`；`window.resize` 时 `resize()`。
- **Tab 切换与「查询」**：`initTabs` 切换后 **`setTimeout(0, onQuery)`**，且 **`onQuery()` 返回的 Promise 完成后再 `setTimeout(50ms, resizeAllCharts)`**，避免请求未完成时提前 `resize` 导致图表尺寸异常；「查询」按钮同样 **`onQuery().then` → 延迟 `resize`**。首屏加载同逻辑。
- **用户报表饼图**：`extra.level_distribution` 为全量用户等级分布，**与日期筛选无关**；页面饼图标题下灰色说明与接口语义一致。

---

<a id="memory-implementation-boundary"></a>
### 本轮实现与环境边界

本节记载工作区已实现、在自有隔离环境验证的增量。2026-10-13本地Docker业务环境`local-docker:lxmfor`已完成S15并开放epoch2，运行于新库`local_test_collection`；旧库和旧隔离分区已退役且不复用名称。实际验证及版本见唯一STEP §3.39。M8 的 cg=0.18/user=0.15 是隔离评测候选，共享默认仍为0.1；内置 System 修复不覆盖合法 active/draft/显式 override。AC19/AC20 原失败和未齐质量对照按最新用户决定作为本阶段非阻断风险保留，不能据功能通过宣称质量全通过。最终 M8/GATE-D 与实际部署状态见唯一 STEP §3。

<a id="memory-provider-admin"></a>
### 记忆Provider页面与未知保存

embedding/rerank/dashvector表单消费同源有效配置/version/source与credential_configured；dirty合并、原入口role、UTF8纯文本显示和测试/保存双反馈保持。dashvector固定新目标/维度/FLOAT/DotProduct，旧TopK只读。api_key未修改不提交；observer仅配置状态，写/测控件data-write-action及后端403。服务端保存仍重新探测，不信前端testPassed；dirty/Key变化重置测连结果与允许保存状态。

发布前校时+UUIDv7，unknown保原publish_id，GET本人原来源回执核实，不用active新版本或刷新成功冒充原保存成功。保存确认才显示成功，未知/失败/过期分别显示。运行resolver已接三类配置但生效依具体environment/fence/部署；旧业务容器未部署，不能延续“所有记忆消费者仍只读环境变量”的笼统说法，也不能宣称本轮热切换上线。doubao/content-safety旧流程保持，详见[API](api.md#memory-provider-config)。
