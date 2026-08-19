# Observability Api

- 文档 ID：`contract-observability-api`
- 权威状态：`canonical`
- 功能范围：`observability-third-party`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`
- 相关技术债：`TD-008`, `TD-009`, `TD-010`, `TD-011`, `TD-012`, `TD-033`

### 模块：数据统计（`/api/admin/stats`）

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
- **PUT** `/third-party/{service_name}/config` — Body 自由 dict；保存前服务端用「已发布配置 ∪ Body」合并后做连通性测试（失败则 `ApiResponse.fail` code=5001，不落库）
- **POST** `/third-party/{service_name}/test-connection` — 可选 **JSON Body**（字段与 PUT 一致片段即可，如 `endpoint`、`api_key`）；服务端将 Body 与**当前已发布** `admin_config` 中对应 `third_party:*` 配置 **合并** 后调用与 PUT 相同的探测逻辑；无 Body 或 `{}` 时等价于仅用已发布配置 + 各探测函数内对环境变量的回退
- **GET** `/system/logs` — Query：`log_type`（`system` \| `error`，对应 `_LOG_TYPE_FILE_MAP`）、可选 `level`、可选 `start_date`/`end_date`（缺省为近 7 天）、`page`/`page_size`；成功 `data`：`{ total, page, page_size, list:[{ time, level, module, message }] }`（**`list` 按日志时间 `time` 降序，最新在前**）；**POST** `/system/logs/export` — Query 条件同上、**无 Body**；成功为 **xlsx 流**（非 JSON 信封）；范围校验失败 HTTP 400；**查询**区间 `(end-start).days > 30`、**导出** `> 7` 被拒绝（与 `system_monitor.py` 一致）；导出文件内行顺序与列表查询一致（同条件下按 `time` 降序）
- **凭据脱敏**：系统日志列表分页结果与 Excel 导出行在返回前统一调用共享凭据脱敏工具；所有获准角色获得一致结果。单条消息处理异常时失败关闭为 `[REDACTED]`，时间、级别、模块、收集、筛选、排序和日期范围不变。
- **说明**：`system_monitor.py` 末尾有 `# TODO: 后续接口`
- **状态**：已实现（除标注 TODO 部分）

---

#
