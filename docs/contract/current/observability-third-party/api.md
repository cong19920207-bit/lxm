# Observability Api

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


- 文档 ID：`contract-observability-api`
- 权威状态：`canonical`
- 功能范围：`observability-third-party`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`
- 相关技术债：`TD-008`, `TD-009`, `TD-010`, `TD-011`, `TD-012`, `TD-033`

### 模块：数据统计（`/api/admin/stats`）

<a id="h5-visitor-reports"></a>
#### H5 访客与设备

以下 GET 共用已登录的 `super_admin`、`ops_admin`、`observer` 读权限。未登录返回 401，其余角色返回 403。列表使用 `list/total/page/page_size`，默认每页 20 条，最大 100 条。事件时间返回带 UTC 时区的 ISO 时间。

| 完整路径 | 参数与返回结果 |
|---|---|
| `/api/admin/stats/visitors/summary` | 看板按北京时间读取今天的日汇总，返回 `day/first_day/today` 及与访客报表同源的 `visitors/visits/opens/unidentified_opens`。 |
| `/api/admin/stats/visitors` | `day` 默认北京今天，`order=desc/asc` 按来访次数排序，相同次数按编号。`first_day` 是启用北京日和日总保留起点中较晚者。超界返回 400。三项为 `visitors/visits/opens`，无号差额为 `unidentified_opens`。`state=available/empty/expired`，每行包含编号、所选日次数和首次／最近来访开始时间。`device` 为保留期内最近的设备资料、身份、网络、首次／最近访问时间和存续期累计次数，与设备接口同口径，设备资料不可用时为 `null`。 |
| `/api/admin/stats/visitors/{visitor_id}` | 必填 `day`。每次来访返回 `visit_id/start/changes/opens`。仅前台返回的来访可以有零次打开。 |
| `/api/admin/stats/devices` | 按最近前台发生时间倒序。每个在保留期内的编号一行，包括最近身份、网络、设备资料、首次及最近时间、当前存续期累计。 |
| `/api/admin/stats/devices/{visitor_id}` | `list` 为保留期内逐次打开，按发生时间倒序分页；另有按时间排列的身份变化 `changes`。设备不存在或连续 90 天未访问返回 404。 |

每笔事件保留自己的 `event_id/visit_id/occurred_at/received_at/entry/identity/network/delayed`。身份为 `guest`、账号 ID 字符串或 `unknown`。网络快照含完整 IP 和当次归属地，来源不明时为 `{"ip":null,"region":"来源未知"}`。最近网络到期后为 `null`。首收时的网络用于补报，晚到记录按发生时间归入原日。每个北京日首次前台活动开始来访。再次打开或返回前台距上次前台活动满 30 分钟另起一次。站内操作更新活动时间，单独身份变化只更新身份与最近快照。

启用时点由迁移 `v10f_visitor_analytics_001` 固定。明细和完整 IP 满 30 天到期，设备满 90 天无访问结束本次存续，日总保留至次年对应北京日。读取即时执行保留边界，调度每 10 分钟物理清理。主站与公开网关分别覆盖来源头，后端校验直连边缘节点。如需确认内网访客，可在 `VISITOR_VERIFIED_LAN_CLIENTS` 配置已核实直连端点，`VISITOR_INTERMEDIARIES` 指定应排除的中间节点，均为逗号分隔的完整地址。归属地使用构建时固定版本及 SHA-256 的 IPv4/IPv6 XDB，运行时离线查询，目录可由 `VISITOR_GEO_DIR` 指定。[H5 收件](../h5-app/api.md) · [本地库安装器](../../../../scripts/install_visitor_geo.py)

- **GET** `/stats/dashboard` — `**ApiResponse`**，所有登录管理员可访问；`data` 为**嵌套对象**（按角色裁剪）：
  - `super_admin` / `ops_admin` / `observer`：`user`（`new_users_today` 等）、`retention`（`next_day_retention` / `day7_retention` / `day30_retention`，可 `null`）、`conversation`、`agent`、`ai_performance`
  - `ai_trainer`：仅 `ai_performance`
  - `tech_ops`：空对象 `{}`
  - `ai_performance.llm_avg_response_ms`：**无 Redis 响应时间样本时为 `null`**（与真实平均 **0** ms 区分）；`llm_success_rate` 可 `null`
  - **人格偏离率**（`persona_deviation_rate`）：当日 `persona_risk_flag=true` 条数 / 当日 **`role=assistant`** 的 `conversation_log` 条数 × 100%（与 `stats_service._get_ai_performance_data` 一致）
- **GET** `/stats/trend` — Query `metric`, `days`；`data` 为 **`[{ date, value }, ...]`** 数组（非 `dates`/`values` 对象）；需 `super_admin` / `ops_admin` / `observer`
- **GET** `/stats/report` — Query report_type, start_date, end_date, page, page_size；`data`: `{ list, total, page, page_size, extra }`
- **GET** `/stats/liblib` — Query `days`（1~30）；LiblibAI 日统计；角色 `super_admin` / `ai_trainer` / `tech_ops` / `observer`（见「管理后台 · 生活流」）
- **POST** `/stats/report/export` — Query 同报表条件，Excel 流；`ai_performance` 导出列第三表头为 **「AI回复数」**（对应 `total_count`，assistant 条数）
- **说明**：`report_type=user` 时 `extra.level_distribution` 按 `**relationship.level`** 统计（无行用户计入 level 0），与后台用户列表关系字段数据源一致；**该分布为当前全量用户快照，不随 `start_date`/`end_date` 过滤**（与 `list[]` 按日明细不同）。
- **状态**：已实现

---

### 模块：系统监控与第三方（`/api/admin`）

- **GET** `/system/status`；**GET** `/third-party/status` — `ApiResponse`
- 第三方状态中的 `bm25` 分别返回本地 `encoder_ready`、`initialization`、`index`、`backfill` 和 `checked_at`；字段与判定见[BM25状态](#bm25-runtime-status)。
- **PUT** `/third-party/{service_name}/config` — Body 自由 dict；保存前服务端用「已发布配置 ∪ Body」合并后做连通性测试（失败则 `ApiResponse.fail` code=5001，不落库）
- **POST** `/third-party/{service_name}/test-connection` — 可选 **JSON Body**（字段与 PUT 一致片段即可，如 `endpoint`、`api_key`）；服务端将 Body 与**当前已发布** `admin_config` 中对应 `third_party:*` 配置 **合并** 后调用与 PUT 相同的探测逻辑；无 Body 或 `{}` 时等价于仅用已发布配置 + 各探测函数内对环境变量的回退
- 上述自由dict/各探测内部回退是原非记忆provider流程；embedding/rerank/dashvector已接[记忆provider严格dirty与canonical发布](#memory-provider-config)，不能向三者继续扩展任意字段、坏发布回默认或无身份重试。doubao/content-safety保持原流程。
- **GET** `/system/logs` — Query：`log_type`（`system` \| `error`，对应 `_LOG_TYPE_FILE_MAP`）、可选 `level`、可选 `start_date`/`end_date`（缺省为近 7 天）、`page`/`page_size`；成功 `data`：`{ total, page, page_size, list:[{ time, level, module, message }] }`（**`list` 按日志时间 `time` 降序，最新在前**）；**POST** `/system/logs/export` — Query 条件同上、**无 Body**；成功为 **xlsx 流**（非 JSON 信封）；范围校验失败 HTTP 400；**查询**区间 `(end-start).days > 30`、**导出** `> 7` 被拒绝（与 `system_monitor.py` 一致）；导出文件内行顺序与列表查询一致（同条件下按 `time` 降序）
- **凭据脱敏**：系统日志列表分页结果与 Excel 导出行在返回前统一调用共享凭据脱敏工具；所有获准角色获得一致结果。单条消息处理异常时失败关闭为 `[REDACTED]`，时间、级别、模块、收集、筛选、排序和日期范围不变。
- **说明**：`system_monitor.py` 末尾有 `# TODO: 后续接口`
- **状态**：已实现（除标注 TODO 部分）

---

#

---

<a id="memory-implementation-boundary"></a>
### 本轮实现与环境边界

本节记载工作区已实现、在自有隔离环境验证的增量。2026-10-13本地Docker业务环境`local-docker:lxmfor`已完成S15并开放epoch2，运行于新库`local_test_collection`；旧库和旧隔离分区已退役且不复用名称。实际验证及版本见唯一STEP §3.39。M8 的 cg=0.18/user=0.15 是隔离评测候选，共享默认仍为0.1；内置 System 修复不覆盖合法 active/draft/显式 override。AC19/AC20 原失败和未齐质量对照按最新用户决定作为本阶段非阻断风险保留，不能据功能通过宣称质量全通过。最终 M8/GATE-D 与实际部署状态见唯一 STEP §3。

<a id="memory-provider-config"></a>
### 记忆Provider同源配置和有效探测

仅embedding/rerank/dashvector三类接持久canonical发布与EffectiveMemoryConfig resolver：dashvector同 `/api/admin/vector-db-config`使用vector_db_config head，embedding/rerank分别third_party:embedding/rerank。doubao与content-safety维持原独立流程，不能套用新receipt宣称。

三类PUT与test只允许原合法provider字段：dashvector endpoint/collection_name/api_key/dimension/dtype/metric，embedding endpoint/model/api_key/dimension，rerank endpoint/model/api_key；按完整组解析dirty合并，不默许任意字段/字段null清空或已发布坏配置回默认。新链固定目标new_lxm_memory_long_collection、1024/FLOAT/dotproduct；endpoint/model/Key来源与字段source同一次快照，探测具体方法仍现有协议。GET公开configured/credential_configured、field_sources、profiles及版本，不明文凭据。

发布身份、原来源role、自有回执、unknown查询以及写库后缓存规则唯一见[记忆配置](../memory-knowledge/api.md#memory-config-publication)，不复制第二套发布状态；第三方原S/T/V读与S/T写保持，A不借同head获得第三方入口。provider异常只公开安全原因，不透传服务返回、SQL错误或凭据。旧保留消费者另见[DotProduct](../memory-knowledge/api.md#memory-dotproduct-retained-consumers)。

<a id="bm25-runtime-status"></a>
### BM25本地编码器、初始化与回填状态

`GET /api/admin/third-party/status` 的 `bm25` 状态每次读取，不复用服务统计的60秒缓存；权限仍为super_admin/tech_ops/observer。只读查询不启动初始化、执行器或回填，不写入业务记录，也不进行远端文档写查或连通性探测。

- `provider/package/version/encoder_version/encoder_ready/statistics_sha256` 来自本地固定profile与加载校验。单独调用本地能力检测只能证明编码器状态，`ready=null`、`reason=index_status_unchecked`，不判断索引是否初始化。
- `initialization.state`：读取当前 `MEMORY_RUNTIME_ENVIRONMENT_ID` 的fence，核对已发布DashVector有效配置的目标指纹和关联S15回执。环境缺失为`not_configured`，fence缺失为`not_initialized`，目标不符为`target_mismatch`；维护期间按关联回执区分`initializing/failed/unknown/maintenance`。仅active、目标/环境/epoch一致、回执completed/opened且completed_at存在时为`ready`，其余回执不完整为`unverified`。这是持久初始化与开放证据，不代表远端当前健康探测。
- `index`：仅在初始化与开放核实后统计相同目标指纹与epoch的非deleted身份；返回`total/ready/pending/manual/unverified`。live且ready且编码版本匹配才计ready，来源unknown计unverified，manual单列，其余计pending；状态分别为`empty/ready/pending/attention`。空目录明确返回empty，不虚构回填完成。
- `backfill`：仅选当前environment/目标指纹/epoch及固定编码版本的回填记录（scope与frozen_versions的epoch都匹配）。按创建时间从新到旧检查，优先展示尚未闭合的记录；较新、已完成核对且范围覆盖旧run全部partitions、ended_at不早于旧run最后更新的记录，可以替代旧interrupted/manual_required报告；新完成子范围、仍pending/running或完成后又恢复的旧run不能被遮住。无未闭合记录时展示最新完成记录，无记录为`not_started`。保留pending/running/interrupted/manual_required；completed还须report_complete=true且unresolved_count=0，否则unverified。返回run_id/stage、scanned_records、unique_source_ids、total_known/total_source_ids、unresolved_count/report_complete；总量未确认时total_source_ids=null，不计算百分比。查询只读取监控所需列、流式分批遍历，不以列表截断推断全部完成，也不修改旧run状态。
- 汇总`ready`只有编码器可用、初始化ready、当前索引ready或empty、回填completed或无记录时才为true；已知阻塞为false，状态读取失败/超时为null（若编码器已有确定失败则为false）。三个持久状态查询共3秒预算；失败保留已独立查明的字段，其余为unknown。`reason`只返回受控原因，不暴露原始SQL错误、凭据或记忆正文。

2026-10-15 17:10（Asia/Shanghai）已将此修复部署到本地Docker `local-docker:lxmfor`，镜像 `lxm_for-backend:bm25-status-20261015-a5fdb205592f`，以原运行镜像叠加4个相关文件，保留原环境、回环端口和挂载；MySQL/Redis/Nginx未重建。真实本地HTTP/MySQL核验：编码器ready、初始化ready，115条当前非删除记录中114条ready、1条来源unverified，pending/manual均0；无回填记录。待核实项在部署前已存在；7张初始化/索引/回填相关表的数量与元数据摘要在部署及页面验收后完全一致，本轮未执行初始化、回填或生产操作。17:14通过另一既有有效本地登录会话完成真实浏览器DOM和截图核对，卡片逐项匹配接口，汇总为黄色待处理状态；原过期会话未重置账号或凭据。部署与核验状态为VERIFIED_LOCAL_DOCKER，记录见仓库忽略文件 `data/runtime-checks/bm25-status-local-20261015-a5fdb205592f.json`，同名JPG为真实页面截图。
