# observability-third-party 技术债

- 文档 ID：`tech-debt-observability-third-party`
- 权威状态：`canonical`
- 功能范围：`observability-third-party`
- 必读依赖：无
- 相关技术债：`TD-008`, `TD-009`, `TD-010`, `TD-011`, `TD-012`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-008] 统计报表：LLM 响应耗时无法按日展示

- **数据与能力边界**（以 `backend/services/llm_service.py` 写入、`stats_service._get_ai_performance_data` 读取为准）：
  1. `**llm_response_times`**：`LPUSH` + `LTRIM` 保留最近 **1000** 条耗时，**不按自然日分区**，无法据此还原「历史某日的平均响应时长」。
  2. `**llm_stats:{YYYYMMDD}`**：按**自然日** Hash 存 `total`/`success`，但 key 带 `**EXPIRE` 172800**（约 2 天），Redis 内**无法覆盖**数据报表常见的 **30～90 天**成功率序列（除非改 TTL 或另存归档）。
  3. 仪表盘 `llm_avg_response_ms` / `llm_success_rate` 均来自上述 Redis，**仅反映当前窗口或当日**，`_get_ai_performance_data` 不提供按日历史序列。
- **问题**：「数据报表」AI 性能 Tab 的 **LLM 耗时/成功率按日折线**在**现存储与接口**下无法直接实现；页面以 `**report_type=ai_performance` 的 `list[].deviation_rate`**（MySQL 按日聚合）作折线，与 LLM 耗时语义不同，需读者知悉。
- **关联**：`admin/pages/data-report.html` 图表副标题、`docs/contract.md` 中 **TD-008** 说明；仪表盘 `ai_performance.llm_avg_response_ms` 无 Redis 样本时为 `**null`**（前端「—」），有样本时为数值（可与真实 **0ms** 区分）。
- **当前处理**：页面文案与契约已标注本债；无按日 LLM 曲线。
- **待处理**：
  1. 若产品坚持按日 LLM 指标：新增**按日聚合**（如每日任务写 MySQL/Redis 结构化字段，或扩展 `llm_stats` 写入粒度），再供 `GET /stats/report` 或独立趋势接口消费。
  2. 与数据看板、PRD 中「LLM 统计写入」规则对齐口径（成功/耗时/拦截的「日界」与服务器时区）。
- **触发时机**：需要运营按日对比 LLM 性能或与偏离率**分列展示**时排期。
- **风险等级**：**低**（展示层取舍，不影响对话与鉴权链路）

### [TD-009] 统计报表：feature 明细缺按日 open_rate / agent_replied

- **接口**：`GET /api/admin/stats/report?report_type=feature`（及 `**POST /stats/report/export`** 同类型）；实现见 `backend/services/stats_service.py` → `_report_feature`；路由 `backend/routers/admin/stats.py` 中 `_REPORT_HEADERS` / `_REPORT_FIELDS`。
- **问题**：明细每行仅 `**date` / `agent_sent` / `agent_opened` / `reply_rate`**；按日 **打开率（open_rate）**、**回复条数（agent_replied）**（或产品最终字段名）**未在接口与导出中输出**。仪表盘 `GET /stats/dashboard` → `agent` 仅有**当日** `agent_open_rate` 等，**不能**替代按日行上的 open_rate。
- **关联**：`docs/contract.md` 数据报表小节与 **TD-009** 提示；`admin/pages/data-report.html` 功能使用 Tab 顶栏 ℹ️ 文案。
- **当前处理**：`data-report.html` 表格暂 **4 列**（日期、发送数、打开数、回复率）；导出 Excel 与后端字段一致。
- **待处理**：
  1. `_report_feature`：按日计算并返回 `open_rate`（如 `agent_opened/agent_sent`）、`agent_replied` 等（口径需产品确认：是否与 `reply_rate` 定义重叠）。
  2. `stats.py`：扩展 `_REPORT_HEADERS` / `_REPORT_FIELDS` 与导出行写入。
  3. `data-report.html`：增列与空值展示规则；契约同步字段表。
- **触发时机**：需要与 PRD/运营报表字段「打开率、回复数」逐日对齐时排期。
- **风险等级**：**低**（缺列不影响现有发送/打开/回复率逻辑）

### [TD-010] 系统监控：`alerts[]` 无单条发生时间，前端用刷新时刻代替

- **位置**：`backend/routers/admin/system_monitor.py` → `get_system_status`（组装 `data.alerts`）；`admin/pages/system-monitor.html` → `renderAlerts`（告警列表左侧时间列）。
- **接口**：**GET** `/api/admin/system/status`；`data.alerts` 当前为 `{ level, message }[]`；响应体经 Redis `**cache:system_status`** 缓存，TTL **10s**（`system_monitor.py` → `_set_cached`）。
- **问题**：告警项**仅有** `level`、`message`，**无**单条**产生时间**。管理端各行左侧时间均为**当次请求成功时的刷新时刻**（`HH:MM:SS`），多条告警无法排序，与「指标实际越阈时刻」也不一致，不利排障与截图留痕。
- **关联**：`docs/contract.md` →「`admin/pages/system-monitor.html`」小节已约定「无单条时间字段时用刷新时刻」。**库内消费方**：全仓库仅本接口与 `**system-monitor.html`** 依赖 `alerts` 形状，无 H5、定时任务或其它后台页。**与 TD-011** 无实现依赖，可并行排期。
- **当前处理**：后端不写字段；前端 `renderAlerts(alerts, timeStr)` 用单次 `refreshSystemStatus` 成功时的 `nowTimeLabel()` 填各行时间。
- **待处理**：
  1. **后端**：`alerts.append` 增加时间字段（建议 `**occurred_at`**：ISO8601 或与后台其它列表一致的时间格式）；写入时刻可与各阈值分支判定对齐，或由产品确认统一用 `datetime.utcnow()`。
  2. **缓存**：JSON 结构变更后旧缓存 **10s 内过期**，无需迁移；若需新旧前端并存，契约中约定新字段**可选**、旧页忽略即可。
  3. **契约**：`docs/contract.md`「模块：系统监控与第三方」与 `**system-monitor.html` 小节** 补充 `alerts[]` 字段表；清偿后管理端技术债表本条按团队惯例标 **已修复** 或删行。
  4. **前端**：优先展示 `occurred_at`（展示粒度由产品定），缺失时回退刷新时刻。
- **触发时机**：运维需按时间线对日志、或产品要求列表展示真实触发时间时排期。
- **风险等级**：**低**（展示/审计语义；不影响鉴权与 psutil 主路径）

### [TD-011] 系统监控：`get_system_status` 在 Redis INFO 异常时可能 `NameError`

- **位置**：`backend/routers/admin/system_monitor.py` → `**get_system_status`**；问题集中在 Redis `**INFO**` 的 `try`/`except` 之后、仍引用 `**hits`/`misses**` 的告警判断（当前与 `redis_hit_rate < 50 and (hits + misses) > 100` 相关）。
- **接口**：**GET** `/api/admin/system/status`。该路径若抛 `**NameError`**，`**ApiResponse` 无法返回**，前端 `adminRequest` 侧多为失败 Toast + 监控页数据不更新（视 HTTP 状态可能为 **500**）。
- **问题**：`hits`、`misses` 只在 `**try` 成功**时赋值；`**INFO` 任一步失败**进入 `**except`** 后两变量可能**未绑定**，后续仍计算 `(hits + misses)` → `**NameError`**，请求中断；此时 **psutil** 已采到的 CPU/内存/磁盘也无法返回。
- **关联**：`docs/contract.md` 文末「管理端页面」**技术债汇总表**列有本条；`**system-monitor.html` 契约小节正文**仅写 TD-010，**未**在正文中写 TD-011。**与 TD-010** 无代码依赖，修复顺序任意。
- **当前处理**：无防御逻辑；Redis 正常时不触发。**2026-04-16 复核**：`get_system_status` 在 Redis `INFO` 的 `except` 之后仍用 `hits`/`misses` 参与命中率告警（约 **104** 行），**`NameError` 风险仍存在**，下方待处理 **未完成**。
- **待处理**：
  1. **推荐**：在 `**try` 前**设 `hits = 0`、`misses = 0`（与 `redis_hit_rate` 等初始化并列），保证异常路径下判断合法；失败时 `hits + misses > 100` 为假，**不**误报命中率偏低。
  2. **备选**：将「命中率偏低」告警**移入** `try` 内、紧跟 `hits`/`misses` 赋值之后。
  3. **验证**：Redis 正常时响应与现网一致；可本地临时在 `info` 前 `raise` 验证仍 **200** 且含系统指标、无命中率误报（**勿提交**测试注入）。
- **触发时机**：Redis 抖动或 **INFO** 失败时；或做 `**system_monitor` 健壮性**小修时合并。
- **风险等级**：**低**（单函数隔离、成功路径不变；回滚即还原该文件）

### [TD-012] 第三方服务配置（`third_party:`*）已可落库，业务运行时未读取

- **配置**：`admin_config.config_key` 为 `third_party:doubao` / `third_party:embedding` / `third_party:dashvector` / `third_party:content_safety`；发布后 Redis `active_config:third_party:`*（TTL 3600s）与 `system_monitor.update_third_party_config` 同步；管理接口见 `backend/routers/admin/system_monitor.py`。
- **问题**：**LLM / Embedding / DashVector 等调用链**（如 `backend/utils/llm_client.py` 及向量、向量化相关客户端）**仍从环境变量与 `backend/config.py` 读取**，**不读取**上述 `third_party:`* 生效配置。后果：管理端 `third-party.html` 保存的 Endpoint/API Key **不改变**当前 H5 对话与记忆链路的真实调用源，易误判「已保存即已切换」。
- **例外**：`POST/PUT` 与探测逻辑会使用合并后的 dict 做**连通性验证**；监控卡片统计来自 Redis `llm_stats` / `embedding_stats` / `vector_stats` / `content_block_count` 等，反映**线上实际流量**，与配置表可能**两套真相**。
- **当前处理**：按产品阶段优先保证 C 端稳定；后台页与接口先交付，运行时接入排期后做。
- **待处理**：
  1. 在 LLM / Embedding / DashVector 客户端统一增加「优先读 `active_config:third_party:`* 或等价生效源，失败回退 env」的解析层，字段名与 `PUT .../third-party/{service}/config` Body 一致。
  2. 发布第三方配置后视需要缩短缓存或广播刷新，避免长 TTL 内新旧混用（与现有 `active_config` 策略对齐）。
  3. `docs/contract.md`「`third-party.html`」小节与清偿后本条按团队惯例标 **已修复** 或删行。
- **触发时机**：需要「后台改 Key/Endpoint 即对线上生效、无需改 env 重启」时排期。
- **风险等级**：**中**（与 TD-004、TD-005 同类：配置与运行时易不一致）
