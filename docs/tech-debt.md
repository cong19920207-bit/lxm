# 技术债务记录

**专项决策**：AI 日记改造范围、权限、运维约定见 **`docs/diary-refactor-decisions.md`**（与 **TD-006、TD-007、TD-013、TD-014** 对应）；**运维 / 手动批跑 / 发布门禁**见 **`docs/ops-diary.md`**。H5 对话「历史/新消息」队列、打断与落库见 **TD-015**（**部分清偿**，见正文）；**按轮情绪 / `round_id`（TD-016）**：**V2-A/B/C** 已合并（库表、闭环写入、**管理端用户详情 →「情绪日志」只读 Tab** + `emotion-rounds`）；口语「**后台情绪还没做完**」多指 **TD-020**（短期属性 Admin/Agent/统计读边等），**不等价**于只读 Tab 未交付；H5 是否进一步按 `round_id` 做展示增强见体验/工单；**记忆检索 query 改写 / LLM 重写**见 **TD-017**；**日记「有互动」与仅失败 user 行**见 **TD-018**；**H5 多 Tab 并行聊天与 SSE 代展示**见 **TD-019**；**用户短期情绪属性（与句级/轮级情绪分层、Redis 与 DB 展示口径）**见 **TD-020**（**V3-A 基座已落地**，Admin/策略仍待）；**双轨用户记忆（列表库 vs Step6 向量）及合并口径**见 **TD-022、TD-023**；**Step6 四类 KV「一行一条」落库稳定性（L4 检测 / L5 自动修复）**见 **TD-028、TD-029**；**内容安全 `failed_blocked` 不可叹号重发（H5 / Open 共用）**见 **TD-030**；**Open API `check_send_quota`（10104）非原子**见 **TD-031**（PRD §8 TD-NEW-05）。

### [TD-001] users 表遗留字段待清理

- 字段：users.relationship_level、users.growth_value
- 问题：注册写入默认值 0 后不再更新，真实数据在 relationship 表
- 当前处理：Admin 查询已改读 relationship 表；users 字段保留，注册路径不动
- 待处理：
  1. 确认全量无读路径后，从 User Model 删除这两个字段
  2. 出 Alembic migration 删列（含 downgrade）
  3. 清理注册路径中的 relationship_level=0 / growth_value=0 赋值
- 触发时机：H5 客户端有用户资料相关改动时一并处理
- 风险等级：低

### [TD-002] 后台 Prompt 与主链 Step5 / Step5.5 热加载 — **已清偿（STEP-026，2026-05-07）**

- **原问题**：旧版七模块 `prompt_modules` 与 `PromptBuilder` 主链未对齐，运营调模板易误判已生效。
- **当前实现**：
  1. **Step5 模块1 System**：`admin_config.config_key = step5_system_prompt`（JSON `{"content"}`），发布后 `active_config:step5_system_prompt`；`PromptBuilder` 经 `_load_step5_system_template_raw` 热加载，缺省回退 `SYSTEM_PROMPT_TEXT`。
  2. **Step5.5**：`step5_5_prompt_fragments` 六段 + `step5_5_prompt_fragments.py` 占位符/默认合并；总开关 **`step5_5_enabled`**（STEP-009，独立页发布）。
  3. **废弃**：旧 **`prompt_modules`** 管理接口已移除，运行时**不再读取** `prompt_modules`。
  4. **在线测试**：`POST /api/admin/prompt/test` 使用 **`PromptBuilder.build_chat_prompt`** + `chat_with_step5_parse(..., is_test=true)`，与主链一致；`use_draft` 覆盖 Step5 System 草稿。
- **契约 / 单测**：见 **`docs/contract.md`**「STEP-026」；**`tests/test_step026_prompt_config.py`**。
- **残留备注**：除模块1 System 与 Step5.5 六段外，其余 Prompt 模块（Persona、Relationship、Memory 等）仍以代码拼装为主；若未来需运营级全模块模板化，另立需求与条目。

### [TD-003] Prompt 管理页版本历史分页失败时列表不刷新

- 位置：`admin/pages/prompt.html` → `loadHistoryPage`
- 问题：`GET /api/admin/prompt/history` 返回 `null`、`code !== 0` 或请求异常时，函数**不更新** `#prompt-history-list` DOM。首屏加载失败会走 `DOMContentLoaded` 里 `else` 显示「加载失败，请刷新重试」；但用户点击分页后若该次请求失败，列表仍保留**上一页或旧数据**，与真实状态不一致，易误判。
- 当前处理：无
- 待处理：
  1. 在 `loadHistoryPage` 的失败分支写入明确错误文案（与首屏一致或 Toast）
  2. 可选：失败时回退 `historyPage` 或禁用分页按钮，避免页码与内容错位
- 触发时机：顺带优化后台列表页错误处理时一并改；或用户反馈历史区「翻页后内容不对」时处理
- 风险等级：**低**（仅影响管理端历史区展示，不涉及编辑、发布与线上对话）

### [TD-004] Agent 规则（agent_rules）管理端可配、运行时未读取

- 配置：`admin_config.config_key = agent_rules`（`triggers` + `decision_engine`），发布后 Redis `active_config:agent_rules` 同步更新；管理接口见 `backend/routers/admin/agent_mgmt.py`。
- 问题：`AgentService`（`backend/services/agent_service.py`）中 **P1 / P2 / P4 触发条件**、**每日触发次数**、**两次间隔**、**行动评分阈值**等均为**代码内写死**，**不读取**上述配置；运营在后台修改触发参数与决策引擎对线上主动消息逻辑**当前无效果**。
- 例外：**P3 凌晨关键词**走独立配置 `agent_night_keywords` / Redis `agent:night_keywords`，`_get_night_keywords()` **会读取**，修改关键词可影响 P3 行为。
- 实现约定：**若需求/提示词与现有代码不一致，以现有代码为准**；本页（Agent 配置）仍按接口持久化全量 JSON，待本债清偿后再与运行时对齐。
- 当前处理：无
- 待处理：
  1. `AgentService` 启动或判定时读取 `active_config:agent_rules`（或等价生效源），解析 `triggers`、`decision_engine`
  2. 用配置替换 `_check_p1` / `_check_p2` / `_check_p4` 及 `check_and_trigger` 内频率、评分门槛等硬编码，字段名与 `AgentRulesRequest` / 管理端表单一致
  3. 缺配置或解析失败时回退到当前硬编码行为，避免线上逻辑真空
- 触发时机：需要「后台改 Agent 规则即生效」时排期；可与 Agent 配置页（`agent-rules.html`）联调验收
- 风险等级：**中**（同类「后台配置未接入运行时」债务：易误判「已保存配置 = 已生效」）

### [TD-005] 关系规则（relationship_rules）已入库但运行时仍读硬编码

- **配置**：`admin_config.config_key = relationship_rules`（JSON 含 `levels`、`growth_rules`），发布后 Redis `active_config:relationship_rules` 与库内生效行同步；管理接口见 `backend/routers/admin/relationship_mgmt.py`（`GET`/`PUT /api/admin/relationship-rules`，两阶段 `confirmed`）。
- **问题**：`RelationshipService`（`backend/services/relationship_service.py`）中 `**LEVEL_CONFIG`、`GROWTH_ACTIONS`**、**`_calc_level` 内固定阈值（200 / 800 / 2000）**均为代码写死，**不读取**上述配置。后果：后台修改等级阈值、名称描述、成长加分规则后，H5 侧 **成长值累计**、**等级计算**、**关系详情/进度文案** 等仍按旧硬编码执行，与 `relationship_rules` **易不一致**；管理端发布时仍会按新规则做用户升级与降级过渡期（`relationship_mgmt.py`），加剧「库内等级 / 展示阈值 / 实际加分规则」认知分裂。
- **关联**：与 **TD-001**（`users` 表冗余成长字段）独立；清偿本债时应统一以 `relationship` 表 + 生效配置为准，避免再引入第三套阈值来源。
- **实现约定**：在 `relationship_service.py` 读配置；字段名与 `RelationshipRulesRequest` / 管理端 `readLevelsFromForm`、`readGrowthRulesFromForm` 一致；**缺配置或解析失败时回退当前 `LEVEL_CONFIG` / `GROWTH_ACTIONS` / `_calc_level` 行为**，避免线上逻辑真空。
- **当前处理**：管理端 `admin/pages/relationship-rules.html` 顶部横幅提示 TD-005；`docs/contract.md` 已描述接口与前端校验。
- **待处理**：
  1. 在 `RelationshipService`（或独立小模块）中读取 `active_config:relationship_rules`（或 `get_active_config(..., use_cache=False)` 等与管理端一致的生效源），解析 `levels`、`growth_rules`。
  2. `**add_growth`**：按配置中的 `growth_rules` 取 `points` / `daily_limit`；连续登录加成等特例逻辑与现行为对齐后再迁移。
  3. `**_calc_level` / `get_relationship_info` / `get_relationship_detail**`：按配置 `levels[].threshold` 计算等级；`level_name`、权益描述等优先用配置，缺字段再回退硬编码。
  4. 全局检索仍写死 `200`/`800`/`2000` 或仅读 `LEVEL_CONFIG` 的调用点，一并改为读配置或单点封装。
- **触发时机**：需要「后台改关系/成长即对用户端生效」时排期；可与 `relationship-rules.html` 联调验收。
- **风险等级**：**中**（与 TD-004 同类：易误判「已保存配置 = 已生效」）

### [TD-006] 日记历史接口已具备，管理列表页待建 — **已清偿（2026-04-07）**

- **位置**：`backend/routers/admin/relationship_mgmt.py` → `GET /api/admin/diary-history`；**`admin/pages/diary-history.html`**；`admin/static/js/admin-api.js` → **`MENU_CONFIG.super_admin` / `ops_admin`** 菜单项 **`diary-history`**。
- **接口**：**GET** `/api/admin/diary-history`（Query 不变）；鉴权 **`super_admin` / `ops_admin`**（O1，不扩 `ai_trainer`）。
- **当前处理**：列表页对接接口；表格 **`content`** 使用 **`escapeHtml`**；`diary-rules.html` 内历史链接对已授权角色可用。契约见 **`docs/contract.md`**「`admin/pages/diary-history.html`」。

### [TD-007] 日记规则（diary_rules）已入库但生成链路未读取 — **已清偿（2026-04-07）**

- **配置**：`admin_config.diary_rules`；发布后 Redis `active_config:diary_rules`；PUT 支持 **`prompt_with_interaction` / `prompt_without_interaction`**，兼容仅存 **`generation_prompt`** 的旧 JSON。
- **当前处理**：
  1. **`backend/services/diary_rules_loader.py`**：解析、校验、`max_length` / 时刻越界回退 **0:30 UTC**、Prompt 缺省回退内置模板；供 **`DiaryService`** 与 **`main.py` lifespan** 共用。
  2. **`DiaryService.generate_diary_for_user`**：保留等级 / **覆盖日（北京）**已生成 / 1 级无互动等 **early-return**；按 **`has_interaction`** 选模板；**`fill_diary_prompt_template`** 替换占位符（含 **`covers_date_label_zh`**）；**`max_length`** 写入 Prompt 与截断；LLM 失败或空内容时 **硬编码模板重试**；**不对日记正文做 `check_content`**。
  3. **`scheduler.start_scheduler(diary_hour, diary_minute)`**：日记任务 **`CronTrigger` 使用 `ZoneInfo("Asia/Shanghai")`**；启动前 **`await get_scheduled_diary_cron_times()`**。**改时刻须重启 backend**（TD-013）。
- **管理端**：`diary-rules.html` 双 Prompt + 北京时间时/分；顶栏已定案短句。契约与运维见 **`docs/contract.md`**、**`docs/ops-diary.md`**。

### [TD-013] 日记调度：Cron 热更新未做 + misfire 补跑仅运维手动（M2a）

- **决策来源**：`docs/diary-refactor-decisions.md`（2026-04-07）。
- **子项 A — 与 TD-007 配套**：`diary_rules` 中 `generation_hour` / `generation_minute` 接入后，**修改触发时刻须重启 `lxm_backend`（或等价进程）** 后 APScheduler 才按新 Cron 注册；**不实现**运行中热更新 Trigger（后续若做再关闭本条子项）。
- **子项 B — misfire 补跑**：APScheduler **missed** 导致当日批跑未执行时，**当前约定**通过 **`docs/ops-diary.md`** §3：推荐 **`python -m scripts.run_diary_batch`**（与 `run_daily_diary_task` 同源），或容器内等价 **`docker exec … python -m scripts.run_diary_batch`**；**无**管理端按钮、**无**受控 HTTP API。后续若增加 super_admin 触发接口 + 限频 + 审计，再在本条标注升级或拆条。
- **当前处理（2026-04-16）**：待处理原第 1 点已由 **`docs/ops-diary.md`** §3 承接（可复制命令与环境注意）；仓库脚本 **`scripts/run_diary_batch.py`**（2026-05-17）。
- **待处理**：
  1. ~~在 `README` 或 `docs/` 运维小节写入 **可复制的 docker exec 命令** 与环境前提（`.env` / 网络）。~~ **已完成**：见 **`docs/ops-diary.md`** §3；是否在根 **`README`** 再挂入口链接可按团队习惯选做。
  2. （可选）实现热更新 Cron、（可选）实现 M2b 手动触发 API。
- **风险等级**：**低**（运维可接受手动补跑时，对线上功能无逻辑缺口；主要风险是「无人知会补跑」导致当日无日记）

### [TD-014] H5 日记列表误用 `diaries`，与契约 `items` 不一致 — **已清偿（2026-04-07）**

- **位置**：`frontend/pages/diary.html` → **`loadDiaries`** 仅使用 **`res.data.items`**；`code≠0` 或缺 `data` 时不翻页；**`noMore`** 按 `total` 与 **`page_size`** 契约判断；首屏失败 **`showToast`**。
- **关联**：`docs/diary-refactor-decisions.md` §2、§3；`docs/contract.md` H5 日记列表。

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

**（2026-05 勘误 · 与现网对齐）**：**后端**仍为「**入队即写 user**、**`generation_id` 作废**、**防抖打包调度**、**多 user 一包**」（见 `backend/routers/chat.py`）。**H5（`frontend/pages/chat.html`，2026-05-11+）**：**已移除 `sending`**；**流中再发 / 打断** 依赖 **`AbortController` + `chatSendSession` + `consumeChatSse` 内代过滤**；**防连点** 为 **`lastSendOrResendAt` + `CHAT_SEND_DEBOUNCE_MS`（300ms，`send` 与叹号 `resend` 共用）**；**系统中文输入法** 下发送钮依赖 **`oncompositionend`/`onkeyup`** 调 **`updateSendBtn`**。细则以 **`docs/contract.md` → `POST /api/chat/send`「H5 实现说明」** 为准。上段「历史行为」仅作**归档**，**不得**当作当前验收依据。

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

### [TD-017] 记忆检索：查询改写 / LLM 重写检索 query（**部分清偿 · 2026-05-30**）

- **背景**：对话链路曾用用户原文直接 `get_embedding` → DashVector 检索。产品希望增强召回（同义扩展、多轮指代消解、隐私脱敏后再检索等）。
- **当前处理（2026-05-30 · PRD v6.1）**：主链已实现 **Step1.5**（`query_rewrite_service`：13 字段、四路 Question/Keywords/CandidateKeys、HyDE 规则、失败降级单 Embedding）；Step2 按路检索与 **2.5 补充路** 已落地。见 `docs/contract.md`「2026-05-30 摘要」。
- **仍待评估**：独立小模型/规则缓存、改写 on/off A/B、与 embedding 缓存 key 策略等（原 TD-017 完整愿景）；**不阻塞**现网主链。
- **待处理**：
  1. 设计改写链路：独立小 LLM / 规则 / 缓存；输入为「本轮用于检索的文本」，输出为「检索 query」再 embedding。
  2. 与 `embedding_service` Redis 缓存 key 策略对齐（改写结果 vs 原文分别缓存或统一 key）。
  3. 评估成本、延迟与 A/B（改写 on/off）。
  4. 清偿后更新 `docs/contract.md` 若对外暴露行为差异。
- **触发时机**：TD-015 对话打包上线后，若召回质量不足再排期。
- **风险等级**：**低～中**（多一次调用与失败回退策略）

### [TD-018] 日记「当日有互动」与仅失败 / 未闭环 user 行语义（**待清偿**）

- **背景**：`DiaryService._get_today_conversation_summary`（`backend/services/diary_service.py`）在当日存在**任意** `conversation_log` 时即 `has_interaction=True`，摘要拼接最多 5 条 user 内容。TD-015 后 **user 更早落库**，可能出现**当日仅有失败/未闭环 user、无成功 assistant**，仍判定「有互动」并走**有互动**日记分支，与部分用户/运营直觉可能不一致。
- **当前处理（2026-04-09）**：产品选择 **G1 — 维持现网语义**，**不**在 TD-015 首版同步改日记判定。
- **待处理**：评估是否改为「至少存在一轮成功闭环（或等价 `delivery_status` / 存在 assistant）」再判 `has_interaction`；若改，联动日记规则文案、`generate_diary_for_user`、**`docs/contract.md`** 日记模块说明与 E2E。
- **触发时机**：上线后反馈「无 AI 回复日仍显示有互动日记」或数据质检提出时排期。
- **风险等级**：**低**（体验与口径，非安全）
- **关联**：`docs/admin-conversations-extension-analysis.md` 确认点 G（已定稿 G1）。

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

### [TD-021] 林小梦活动状态描述：当前为静态 JSON 占位，完整活动计划功能待建（**待清偿**）

- **背景**：对话链路改造 Step1 需要一条「活动描述串」（描述林小梦当前在做什么，如"她现在应该在午休"），供 Step1.5 Prompt 与 Step3 新增模块 B 注入。完整功能需按时间段（含工作日 / 周末区分）、概率权重、可运营配置等多维度决策，尚无完整产品计划。
- **当前处理（本期 Step1～3 改造阶段占位方案）**：
  - `admin_config` 表新增条目 `config_key = "activity_schedule"`，值为静态 JSON，以**小时段**为 key 映射活动描述文案，示例：
    ```json
    {
      "0-6":   "她现在应该在睡觉",
      "7-8":   "她现在在吃早餐",
      "9-12":  "她应该在工作",
      "12-14": "她现在在午休",
      "14-18": "她应该在工作",
      "18-20": "她现在在吃晚饭或休息",
      "20-23": "她现在在放松"
    }
    ```
  - 运行时优先读 Redis `active_config:activity_schedule`（TTL 与其他 admin_config 一致）；未命中降级读 DB。
  - **未配置 / 未命中当前小时段 / JSON 解析失败**时产出**空字符串**；Step1.5 Prompt 与 Step3 模块 B **条件性注入**——空串时跳过该行，不插入空白占位文案，不中断主对话链路。
  - **不新建表**，**不做管理后台专属配置页面**（后台可通过现有 `admin_config` 通用编辑页手动维护 JSON）。
- **待处理（完整功能）**：
  1. 建独立 `activity_schedule` 表，字段含 `hour_start` / `hour_end` / `weekday_mask`（位掩码区分工作日/周末）/ `description` / `probability`（权重）/ `is_active`；支持多条并存、按概率随机选取。
  2. 配套管理后台页面：列表 + 新增 / 编辑 / 删除 / 启用停用，角色权限与其他 admin_config 一致。
  3. 运行时读取改为查独立表（含 Redis 缓存层），废弃 `activity_schedule` admin_config 条目。
  4. 可选：支持节假日特殊文案（依赖 `world_state` 或另行维护节假日表）。
- **触发时机**：产品确认活动状态需精细化运营（如「主动消息用活动状态做差异化话术」或「用户反馈角色状态描述不自然」）时排期。
- **风险等级**：**低**（当前占位不影响主对话核心链路；仅影响 Prompt 辅助上下文质量）
- **关联**：`doc/对话链路改造-需求确认记录.md` §2.10 **R-L1L3-11**；Step3 新增模块 B「时间与活动状态」。

### [TD-022] 用户记忆双轨并存：MySQL「列表记忆」与 Step6 四路向量未收敛（**已清偿**）

- **清偿说明（2026-05-31，长记忆第一套下线 PRD v1.3 一次发布）**：第一套写入已下线——`chat.py` 删除 `memory_service.extract_and_save` 调用，物理删除 `extract_and_save`/`_deduplicate_and_save` 及专属私有方法，其余记忆方法标 `@deprecated`；H5/Admin 改读 Step6 user 向量（`/api/memory/list` 只读、`user-memories`/`private-settings`、`memories/global`/`batch-delete`）；唯一写入真相源收敛为 **Step6 向量**。运行时**不过滤 `mem_*`**（P1，推翻原 M13/M10），存量 `mem_*` 脏数据靠 **M2 发布前人工清理**（DashVector 删 `mem_` 前缀 + 清空 MySQL `memory` 表业务数据，表结构保留 M8），见 STEP-016 运维 checklist。PR 号占位：`<PR-待补>`。
- **背景（历史）**：当前存在**两套并行**的用户相关记忆链路，**不互为替代**，且 Step2 检索侧**未隔离**。
- **第一套（列表 / CRUD）**：
  - **写入**：对话成功闭环后置任务 **`memory_service.extract_and_save`**（`MEMORY_EXTRACT_PROMPT` → LLM 返回 `{"memory_list":["短句",...]}`）；用户 **H5「我的记忆」** 与 **管理端用户详情 → 记忆** 的 **手动添加** 亦写入同路径。
  - **存储**：**MySQL `memory` 表**为主；向量侧经 **`vector_service.upsert`**，`doc_id` 形如 **`mem_{memory_id}`**，`type = user`，`fields` 含 `user_id`、`content` 等。
  - **展示**：用户端 **`/api/memory/*`**、管理端用户记忆接口，均读 **`memory` 表**。
- **第二套（Step6 结构化总结）**：
  - **写入**：**Step6** 独立 LLM（**`memory_llm_service.build_step6_prompt` / `parse_step6_output`**），输出 **11 个驼峰字段**；其中 **`UserSettings` / Character\*** 等约定为**多行 `key：value`（中文全角冒号）**；**`upsert_step6_vectors`** 按行解析后写入 **DashVector 四路**（`user` / `character_private` 等），`doc_id` 形如 **`user:{stable_key}:{user_id}`**；另有 **`relationship`** 表上若干 **Step6 标量/描述写回**。
  - **存储**：**无**与「记忆列表」一一对应的 **`memory` 表行**；真相在 **向量 + relationship 扩展字段**。
- **检索现状**：主对话 **Step2**（**`multi_vector_retrieval_service`**）第四路对 **`MEMORY_TYPE_USER` + `user_id`** 做向量检索，**不过滤** `doc_id` 前缀——**旧 `mem_*` 与 Step6 `user:…` 文档在同一过滤条件下共同参与相似度排序**，均可进入 Prompt（在阈值与 `top_k` 内）。主链**已不再**单独依赖旧接口名做「仅列表记忆」检索，但**物理上仍同池召回**。
- **当前影响**：**不阻断**主流程；可能 **Prompt 内语义重复**、**运营/用户改删列表记忆与 Step6 向量不一致**、维护 **两套格式约定**（自由短句 vs `key：value`）成本高。
- **常见误判（已澄清）**：「关掉第一套后，用户在客户端按第二套格式**手打**多行 `key：value`」——在**不改后端**的前提下，仍走 **`memory` 表 + `mem_*`**，**不会**自动等价于 Step6 的 **`parse_kv_lines` + 稳定 `doc_id` 覆盖** 写入路径。
- **待处理（与 TD-023 可合并排期）**：
  1. **产品定稿**：唯一「真相源」——仅列表、仅 Step6、或「列表展示 + 检索仅 Step6」等方案。
  2. **写入侧**：下线或迁移 **`extract_and_save`**；若保留手动维护，需明确写入 **第二套向量规则** 或中间同步层（须开发，非现网手输可达成）。
  3. **检索侧**：若只认一套，需在 **`dashvector_client.search` 过滤条件或业务层** 排除另一套 `doc_id`/标记位，或 **拆 collection**（评估迁移成本）。
  4. **展示侧**：若产品要求列表与检索同源，需 **新读路径**（从向量/同步表聚合）或 **定期同步** 至 `memory` 表（须契约与冲突策略）。
- **触发时机**：产品要统一「我的记忆」与对话注入口径、或研发要降低双写维护成本时排期。
- **风险等级**：**中**（长期语义漂移与排障成本；短期功能可用）
- **关联**：**TD-017**（检索 query 侧）、**TD-023**（合并与去重口径）；实现锚点：`backend/services/memory_service.py`、`backend/services/memory_llm_service.py`、`backend/services/multi_vector_retrieval_service.py`、`backend/routers/chat.py`（后置任务与 Step6 入队）。

### [TD-023] 用户记忆跨源合并与去重口径待统一（**已缓解**）

- **缓解说明（2026-05-31）**：随 TD-022 下线第一套写入，「同一用户事实」不再产生 `mem_*` 新增，新写入唯一走 Step6 **同 `memory_type` + 同 stable `key` 的 upsert 覆盖**（合并阈值 ≥0.92 的 MySQL 去重逻辑已随 `_deduplicate_and_save` 物理删除）。**残留**：存量历史 `mem_*` 与 `user:…` 在清理前仍同池召回（靠 M2 人工清理，P1），跨源对账脚本仍未提供；待 M2 清理完成后本项可视情况关闭。
- **背景（历史）**：在 **TD-022** 双轨前提下，「同一用户事实」可能以 **不同形态** 并存——例如 **`mem_*` 整句摘要** 与 **Step6 `user:` 行级 `key：value`** 在 **同一 `type=user` 检索池** 中均可命中；第一套另有 **MySQL + 向量相似度 ≥ 0.92 合并**（`memory_service._deduplicate_and_save`），第二套为 **同 `memory_type` + 同 stable `key` 的 upsert 覆盖**，**两套合并语义互不自动对齐**。
- **问题**：缺少 **跨 `doc_id` 方案 / 跨表** 的统一「合并、覆盖、废弃」规则；清理其中一套时易产生 **孤儿向量**、**重复注入** 或 **用户删列表但对话仍召回旧向量** 等产品/数据一致性问题。
- **待处理（建议与 TD-022 同一里程碑清偿）**：
  1. **定义合并产品口径**：何种情况视为同一记忆（语义相似 vs key 相同 vs 人工绑定）；**列表删除**是否级联删向量、是否影响 Step6 行。
  2. **技术方案**：统一 **doc_id 命名空间** 或引入 **`source` / `pipeline` 字段** 供检索过滤与后台审计；必要时提供 **离线对账脚本**（MySQL `memory` ↔ DashVector `user` 文档）。
  3. **迁移策略**：若收敛为单套，明确 **历史 `mem_*` 与 `user:…` 的保留、迁移、批量删除** 顺序与回滚。
  4. **管理端**：全局记忆搜索、批量删除（现有 **`memory_mgmt`**）与 Step6 文档的 **操作边界** 写进契约，避免误删非列表来源文档。
- **触发时机**：启动 **TD-022** 收敛方案时 **一并设计清偿**；不宜在仅关接口不关向量的情况下单独「关第一套」。
- **风险等级**：**中**（数据一致性与检索可解释性；误操作可影响多用户向量集合）
- **关联**：**TD-022**；`backend/services/memory_service.py`（合并阈值与 `mem_*`）、`backend/services/memory_llm_service.py`（`parse_kv_lines` / `upsert_step6_vectors`）、`backend/routers/admin/memory_mgmt.py`。

### [TD-024] H5 设置页用户偏好开关后端未实现（**部分清偿**）

- **部分清偿说明（2026-05-31，C-07）**：`settings.html`「记忆自动提取」Toggle 已**移除**，改为只读说明行「记忆整理 / 对话结束后会自动整理成记忆，无需手动设置」，并删除前端对 `memory_auto_extract` 的读取与 PUT；记忆由 Step6 自动整理，`memory_auto_extract` 偏好缺口**不复存在**。**残留**：`agent_message_enabled`（主动消息推送）Toggle 仍在线、后端 `GET/PUT /api/user/settings` 仍未实现/未读取，本项**未全量清偿**。
- **位置**：`frontend/pages/settings.html` → `GET/PUT /api/user/settings`（~~`memory_auto_extract`~~ 已移除、`agent_message_enabled` 仍待）
- **问题**：前端 Toggle 已接线并默认 `active`；后端 **`routers/user.py` 未挂载**、无持久化字段；保存时接口不存在或失败 Toast；即使补接口，记忆提取链路与 Agent 扫描**当前也未读取**这两项开关。
- **待处理**：
  1. 在 `users` 表或独立用户设置表增加字段并迁移；
  2. 实现 `GET/PUT /api/user/settings` 并在 `main.py` 挂载 `user` 路由；
  3. 记忆提取（Step6 / 后置任务）与 Agent 触发链路读取开关并写契约。
- **触发时机**：产品要求设置页「记忆自动提取」「主动消息推送」真实生效时排期。
- **风险等级**：**中**（UI 可交互但偏好不持久、不生效，易误导用户）
- **关联**：`docs/contract.md`「H5 用户（占位）」；`frontend/pages/settings.html`。

### [TD-026] Step6/Admin 前写入的 DashVector 文档缺少 key_l1/key_l2（**待清偿**）

- **背景**：2026-05-30 起 Step2 主路 `build_filter` 支持 **`key_l2 IN (...)`** 结构化过滤（由 Step1.5 `CandidateKeys` 推导）。**新写入**（Step6 `upsert_step6_vectors`、Admin `_build_knowledge_fields`）均补齐 `key_l1`/`key_l2`；**历史向量**可能仅有 `type`/`user_id`/`content`，无二级 Key 字段。
- **当前处理**：主路 `candidate_keys` 过滤对旧文档**不命中**时，依赖 **2.5 补充路**（`candidate_keys=[]`、更宽 filter）与纯向量相似度兜底；**不阻断**主对话。
- **待处理**：离线批量回填 `key_l1`/`key_l2`（需从 `content` 或 `stable_key` 解析）；或产品接受旧文档仅走补充路/降级召回。
- **触发时机**：运营反馈「结构化 Key 检索召回偏少」或要做全量 Key 运营筛选时排期。
- **风险等级**：**低～中**（召回质量与可解释性）
- **关联**：`docs/contract.md`「2026-05-30 摘要」；`backend/utils/dashvector_client.py` `build_filter`。

### [TD-027] Step2 补充路触发阈值与 top_k 未纳入热配（**待清偿**）

- **背景**：`multi_vector_retrieval_service` 中 **`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`**（`count<2 OR max_score<0.75`）与补充路 **`top_k=3`** 为**代码常量**；`vector_retrieval_config` 热配仅覆盖主路 **`top_k`/`threshold`**。
- **当前处理**：按 PRD C2/C7/C36 写死，管理端不可调。
- **待处理**：产品确认是否将补充路阈值/top_k 并入 `vector_retrieval_config` 或独立配置键；变更时同步契约与 `tests/test_multi_vector_retrieval_service.py`。
- **触发时机**：运营需按环境调补充路 aggressiveness 时排期。
- **风险等级**：**低**
- **关联**：`docs/contract.md` §向量召回与 Prompt Token 热配置。

### [TD-028] Step6 四类 KV 写入前缺少「多 key 挤一行」检测与阻断（**L4 · 待清偿**）

- **背景**：Step6 字段 **`CharacterPublicSettings` / `CharacterPrivateSettings` / `CharacterKnowledges` / `UserSettings`** 约定为 **多行 `key：value`（全角冒号）**，**一行一条**；`parse_kv_lines` 仅按 **`\n` 拆行**，每行取**首处** `：` 为界。2026-05 已在 **`build_step6_prompt`** 增加「多条信息分行规则」与反例（Prompt-first），但 **写入链路无确定性校验**。
- **问题（稳定性 L4）**：当 LLM 仍将多条独立 `三层key：value` 写在**同一行**（常见以 **`；` + 下一 key** 串联）时，解析只得 **1 条** `(key, value)`，`value` 内夹带其它 key 全文 → **静默错误落库**（角色知识库后台可见「一条 value 含多个 key」）；**无日志指标、无告警、无跳过写入**，运营只能人工发现并编辑。
- **当前处理**：依赖 Prompt 约束 + few-shot 多行 `\n` 示例；**不满足**「坏格式可自动发现或不落库」的 **L4** 目标。
- **待处理（建议最小集）**：
  1. 在 **`upsert_step6_vectors`** 调用 **`parse_kv_lines` 之后**（或解析函数出口），对每字段每行 `(key, value)` 做 **启发式检测**：例如 `value` 内再出现 **`；`（或 `;`）后接合法三层 key + 全角 `：`**，或「`parse_kv_lines` 行数 = 1 但 value 汉字数 / 嵌套 key 模式异常」。
  2. 命中时 **`logger.warning`**（含 `user_id`、`field_name`、`round_id` 若可得、截断 preview），可选递增 Redis/日计数 **`step6_kv_merge_risk:{date}`** 供监控页或日志检索。
  3. **产品择一**：仅观测（仍写入，便于对比 Prompt 效果）；或 **跳过该字段当轮向量写入**（relationship 标量仍可按既有逻辑写回，避免整轮 Step6 失败）；或 **跳过单行** 仅丢弃可疑行。须在 **`docs/contract.md`** STEP-014 写明行为。
  4. 管理端 **角色知识库列表** 可选：对 `content` / `value` 做同款检测并展示「疑似合并」标记（非必须，可与 1 共用工具函数）。
- **触发时机**：Prompt 加强后仍抽检到合并条；或要把「每条知识独立向量」视为硬 SLA 时排期 **TD-028**（可与 **TD-029** 分阶段）。
- **风险等级**：**中**（数据质量与检索语义；不阻断主对话 SSE）
- **关联**：**TD-022**（Step6 向量轨）；`backend/services/memory_llm_service.py`（`parse_kv_lines`、`upsert_step6_vectors`、`build_step6_prompt`）；`backend/utils/character_knowledge_validate.py`（`validate_key` 复用）；`backend/services/character_knowledge_service.py`（展示侧可选）。

### [TD-029] Step6 四类 KV 同行多 key 无自动拆分/重试修复（**L5 · 待清偿**）

- **背景**：在 **TD-028（L4）** 仅解决「能看见 / 能选择不落库」的前提下，**L5** 要求坏格式 **自动修复** 后仍按约定 **多条独立 upsert**，而非长期依赖人工改后台或重跑对话。
- **问题**：即使 Prompt 合规率提升，模型仍可能偶发同行拼接；当前 **无**（a）确定性 **拆行**（例如在 `；` + 合法三层 `key：` 处切分为多行再 `parse_kv_lines`）；（b）检测到违规后的 **Step6 子链路重试**（附「请用 `\n` 分行」类纠错提示）；（c）对已落库脏数据的 **离线重解析脚本**。
- **待处理（与 TD-028 二选一或组合，须产品确认）**：
  1. **解析兜底（偏 L5）**：扩展 `parse_kv_lines`（或前置 normalize）：在保留「**默认仍为一行一条**」前提下，对 **行首 / `\n` / `；`** 后的合法三层 `key：` 切分点拆成多段再 upsert；切分后仍走 **`validate_key` / `validate_value`**；需评估 value 正文误拆风险并写单测（含截图同款 `体育-球类-篮球：…；体育-球类-乒乓球：…`）。
  2. **重试兜底**：当 TD-028 检测命中且策略为「拒绝写入」时，**仅重试 Step6 LLM 一次**（`execute_step6` 已有 1 次整体重试，可改为「解析层违规触发的定向重试」并在 Prompt 末尾追加一行纠错说明），避免与 JSON 解析失败混为一谈。
  3. **数据修复（可选二期）**：对 DashVector `character_knowledge` / `character_global` 等 `content` 批量重跑新解析器并 upsert（评估 embedding 成本；与 **TD-026** 回填可同窗口）。
- **实现约定**：若采用解析兜底，契约须写明 **「Prompt 要求换行 + 解析器对同行多 key 的兼容边界」**，避免与运营手动在后台录入的单行 value（内含分号但非 key）冲突；**优先**在 TD-028 观测 1～2 周再决定是否上 1，降低误拆。
- **触发时机**：**TD-028** 指标显示违规率仍高于可接受阈值；或上线后仍频繁出现合并条且人工处理成本高。
- **风险等级**：**中**（误拆导致向量语义碎片化；重试增加 Step6 耗时与 LLM 成本）
- **关联**：**TD-028**（L4 前置观测）；**TD-026**（重解析时可顺带补 `key_l1`/`key_l2`）；`backend/services/step6_orchestrator.py`。

### [TD-025] H5 改密码前后端契约不一致（**待清偿**）

- **位置**：`frontend/pages/settings.html` → `POST /api/auth/reset-password`；`backend/routers/auth.py`、`backend/schemas/auth.py`
- **问题**：前端传 `old_password` 且不传 `confirm_password`；后端 **`ResetPasswordRequest` 要求 `confirm_password`**、**不校验原密码**（按用户名存在即可重置），存在安全缺口与字段不匹配；422 或静默忽略原密码校验。
- **待处理**：
  1. 新增需登录的 `POST /api/auth/change-password`（校验旧密码 + 新密码确认），或；
  2. 对齐 `reset-password` 的 Body 与校验逻辑（含原密码验证），并更新 H5 请求体。
- **触发时机**：安全审查或改密码功能正式验收时。
- **风险等级**：**中**（已知安全与契约偏差）
- **关联**：`backend/schemas/auth.py` `ResetPasswordRequest`；管理端改密见 `POST /api/admin/auth/change-password`（已实现完整校验，可作参考）。

### [TD-030] 内容安全 `failed_blocked` 未纳入叹号重发窗口（H5 / Open 共用，**待清偿**）

- **位置**：`backend/services/chat_service.py` → `open_window_has_bang` / `enqueue_resend`；`POST /api/chat/resend`；`POST /api/open/v1/chat/resend`（共用同一判定链，见 **`docs/design/PRD-OpenAPI-APIKey-v1.md`** §8 **TD-NEW-02**）。
- **问题**：Step5 / Step5.5 对外 `messages[].content` 任一条内容安全不通过时，user 行标 **`delivery_status=failed_blocked`**（见 **STEP-012** / `docs/contract.md` H5 对话 send 语义）。当前叹号判定 **仅**包含 `failed_timeout`、`failed_error`，**不含** `failed_blocked`。后果：该 user 行 **无叹号 UI**（H5）、**不可** `resend`（返回 **10107** `ERR_CHAT_NOTHING_TO_RESEND`）；用户/第三方须 **重新 send 新消息**，易误判为「系统无响应」。
- **需求确认（2026-06-04）**：Open API v1 需求评审 **V4 方案 A** — **本期接受现状**，与 H5 保持一致；**不**在 Open 单独放宽 resend 规则。
- **当前处理**：
  1. 运行时逻辑 **不改**；Open `resend` 与 H5 共用 `_open_window_has_bang`（经 N5 `chat_service` 搬迁后仍须保持单点判定）。
  2. 第三方文档 **`docs/design/open-api-v1.md`** 已写明：仅 `failed_timeout` / `failed_error` 可 resend；`failed_blocked` 请 **重新 send**。
- **待处理（单独立项，H5 + Open 同期）**：
  1. 产品确认：`failed_blocked` 是否允许叹号重发（重跑 LLM 仍可能再次 blocked，价值待评估）。
  2. 若做：扩展 `_open_window_has_bang` 含 `DELIVERY_STATUS_FAILED_BLOCKED`；H5 `chat.html` 叹号展示规则对齐；Open resend 共用；更新 `docs/contract.md` 与 Open 集成文档。
  3. 若不做：可在 H5 timeline / 失败 user 行增加 **明确文案**（如「内容未通过审核，请修改后重发」），降低困惑。
- **触发时机**：用户/运营反馈 blocked 场景无法恢复；或 Open 第三方集成验收反馈 resend 语义不清时评估。
- **风险等级**：**低**（发生频率相对 timeout/error 较低；send 入队前 10101 已挡大部分输入侧违规；主要影响 **模型输出侧** blocked）
- **关联**：**TD-015**（叹号与 resend 主链）；**PRD-OpenAPI-APIKey-v1** §8 **TD-NEW-02**、§5.2 对话共用规则（C11）。

### [TD-031] Open API `check_send_quota`（10104）为非原子「先 SELECT 再 INSERT」（**待清偿**）

- **位置**：`backend/services/chat_service.py` → `fetch_open_window_user_rows` + `check_send_quota`（PRD V9 / §8 TD-NEW-05）；H5/Open send 共用。
- **问题**：10104 判定为 **先读未闭环 user 行、再 INSERT 新 user 行**，无 Redis 锁 / Lua / 事务级原子保护。H5 现网已如此；Open 搬迁后 **行为一致，不新增恶化**；极端并发（H5+Open 双端）下两请求可能同时读到 pending&lt;5 并均入队。
- **需求确认（2026-06-04）**：PRD V9 / TD-NEW-05 — **本期接受**，50 用户规模影响可忽略。
- **当前处理**：不改功能设计；Open v1 已落地，行为与 H5 一致；PRD §8 已标注。
- **待处理（单独立项）**：Redis 原子计数或等价机制；**须 H5 + Open 同期改造**。
- **触发时机**：并发 send 导致队列明显超过 5 且无叹号时评估。
- **风险等级**：**低**
- **关联**：PRD **TD-NEW-05**；**TD-030**（独立项）。

---

### 已处理（库结构 / 运维）

- `**admin_config.config_key` 误设 UNIQUE（2026-04）**：导致人格/Prompt 等保存草稿 `INSERT` 报 MySQL **1062**。处理：执行 `scripts/migrate_admin_config_config_key_nonunique.sql` 去掉唯一、重建非唯一索引；契约与 `schema_ddl.sql` 已写明「同一 key 多行」。运行时读 persona：`PromptBuilder._get_persona_from_cache` 已与 `get_active_config` 对齐增加 `is_draft=False`。

