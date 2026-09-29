# Admin Security Api

- 文档 ID：`contract-admin-security-api`
- 权威状态：`canonical`
- 功能范围：`admin-security-accounts`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`
- 相关技术债：无

### 模块：管理后台操作日志（`/api/admin`）

- **GET** `/operation-logs`（Query：admin_username, module, action, start_date, end_date, page, page_size）
- **GET** `/operation-logs/{log_id}`
- **POST** `/operation-logs/export`（Excel 流）
- **导出参数说明**：服务端以 **Query** 接收 `admin_username`、`module`、`action`、`start_date`、`end_date`（与列表筛选一致），**非** JSON Body；前端 `POST` 时将条件拼在 URL 查询串上、Body 为空即可触发 `adminRequest` 的 blob 下载逻辑。
- **响应列表**：`data`: `{ total, page, page_size, list: [...] }`；`list[]` 含 `id`, `admin_user_id`, `admin_username`, `module`, `action`, `target_description`, `ip_address`, `created_at`
- **详情**：`GET /operation-logs/{log_id}` 成功 `data` 另含 `before_value`, `after_value`（可为 `null`）
- **关联表**：admin_operation_logs
- **鉴权角色**：列表/详情 GET 为 `super_admin` / `ops_admin` / `tech_ops` / `observer`（`ai_trainer` 无此菜单与接口权限）；导出仍仅原三角色并显式拒绝 observer。
- **凭据脱敏**：`target_description`、`before_value`、`after_value` 写入前统一脱敏；列表、详情和 Excel 导出返回前再次脱敏，以遮蔽历史遗留明文。单字段异常失败关闭为 `[REDACTED]`，不批量改写历史数据库行。
- **状态**：已实现
- **管理端页面**：`admin/pages/operation-logs.html`
  - 首屏：`DOMContentLoaded`（若文档已就绪则立即执行）触发 `loadLogs(1)`。
  - 筛选：`admin_username` 输入框；`module` / `action` 下拉的选项与当前仓库内所有 `log_operation(..., module=, action=)` 写入值一致（模块：`ai_config`、`memory`、`third_party`、`用户管理`、`账号管理`、`系统`；类型：`batch_delete`、`create`、`delete`、`edit`、`login`、`logout`、`publish`、`unlock`、`update_config`）；日期 `start_date` / `end_date`；搜索/重置调用 `loadLogs(1)`；**导出 Excel** 为 `POST /api/admin/operation-logs/export` + 当前筛选的 Query 串。
  - 列表：`page_size=20`，列 时间 / 操作人 / 操作模块 / 操作类型 / 操作描述 / 详情；操作类型 Tag：`publish`→`tag-success`，`delete` 与 `batch_delete`→`tag-error`，`rollback`→`tag-warning`（仅当库中仍存在该 `action` 的旧记录时可能见到），其余→`tag-default`。
  - 详情：`GET /api/admin/operation-logs/{id}`，Modal 宽 680px，展示操作人/模块/类型/时间/IP，修改前（`#fff2f0`）与修改后（`#f6ffed`）`<pre>` 对比，无数据展示「（无）」。
  - **说明**：`action` 筛选下拉的选项**仅包含**当前代码路径里 `log_operation(..., action=)` 的实际写入值，**不包含** `rollback`。人格/Prompt 等「回滚」接口经 `AdminConfigService.rollback_config` → `publish_config` 记日志时，`action` 为 **`publish`**（`target_description` 等可体现回滚语义）。

---

### 管理端列表日期筛选（`admin_date_filter`）

以下接口 Query 的 **`start_date` / `end_date`**（`YYYY-MM-DD`）共用 **`backend/services/admin_date_filter.py`**：

- **`start_date`**：`created_at >= 当日 00:00:00`
- **`end_date`**（闭区间日历日）：`created_at < end_date + 1 day`
- **`start_date > end_date`** 或格式非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`（20029）**（反选时 message：「结束日期不能早于开始日期」）

**适用接口**：**`GET /users/{user_id}/conversations`**、**`GET /users/{user_id}/emotion-rounds`**、**`GET /users/{user_id}/diaries`**、**`GET /diary-history`**、**`GET /agent-messages`**。

**例外（未纳入本工具）**：**`GET /operation-logs`** 仍按 `end_date` 当日 **23:59:59** 闭区间过滤（`operation_logs.py`）。

---

### 模块：管理后台用户管理（`/api/admin`）

- **GET** `/users` — Query 筛选 username, relationship_level, status, 注册/登录时间范围, page, page_size；`data.list` 含 id, username, created_at, last_login_at, relationship_level, growth_value, total_conversation_count, status
- **管理端列表页（`admin/pages/users.html`）**：表格首列展示 **`list[].id`（用户 ID）**，便于与日记历史等处的 `user_id` 对照；接口字段未增删。
- **说明（关系字段数据源）**：**用户列表** `data.list[]` 与**详情页展平后的** `**userData`** 使用字段名 `**relationship_level`、`growth_value`**；详情接口原始 JSON 中对应为 `**data.relationship.level`、`data.relationship.growth_value`**。上述数值均来自 `**relationship` 表**（模型字段 `Relationship.level`、`Relationship.growth_value`），与用户端 `RelationshipService` 权威读法一致（按 `user_id` 关联；无行时按等级 0、成长值 0）。`**users` 表同名列为历史遗留，本模块不作为数据源**，详见 `[tech-debt.md](../../../tech-debt.md)` **TD-001**。
- **GET** `/users/{user_id}` — 响应 `data` 为嵌套对象（HTTP 层不变）：
  - `**basic`**：`id`, `username`, `created_at`, `last_login_at`, `status`（`normal`  `banned`）, `is_banned`
  - `**relationship`**：`level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`
  - `**activity`**：`total_conversation_count`, `active_days_last7`, `agent_message_reply_count`
- **管理端详情页（`admin/pages/user-detail.html`）**：成功拉取详情后，仅在 `**loadUserDetail`** 内将上述嵌套**展平**为脚本内存变量 `**userData`**（不修改接口响应）。展平规则：`basic.*` 字段名保持不变；`relationship.level` → `relationship_level`；`relationship` 其余键名不变；`activity.active_days_last7` → `active_days_7d`；`activity.agent_message_reply_count` → `agent_reply_count`；`activity.total_conversation_count` 不变。
  - 若 `data` 缺少 `basic` / `relationship` / `activity` 任一层，前端提示「用户详情数据格式异常」且不写入 `userData`。**「AI日记」Tab**：**首次**切换到该 Tab 时请求 **`GET /users/{user_id}/diaries`** **不带**日期（全量时间、倒序第一页）；再次进入同一用户详情会话内 **不重复**首屏请求；**「查询」**按当前日期输入从第 1 页重拉；**「加载更多」**在同一组日期条件下分页追加；
  - 表格列含日记 **`id`**（与 **`diary-history`** 第一列一致）、正文摘要、`relationship_level_at_creation` 映射等级名、已读、**`covers_beijing_date`（覆盖日）**、创建时间；正文 **`escapeHtml`**。
- `**userData` 展平后字段全集**（仅浏览器脚本内存，**非** HTTP 响应体）：`id`, `username`, `created_at`, `last_login_at`, `status`, `is_banned`, `relationship_level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`, `total_conversation_count`, `active_days_7d`, `agent_reply_count` — 与 `loadUserDetail` 实现一致，供 `renderInfoCards`、账号 Tab、顶栏操作等读取。
- **GET** `/users/{user_id}/conversations` — **数据源**：合并 **`conversation_log`** 与 **`agent_message`**（主动消息仅存在于后者，与 H5 一致）。**Query**：`start_date`、`end_date`（见上文 **`admin_date_filter`**，两表均按 `created_at` 过滤）、`page`、`page_size`（1–100）。**排序**：全局 **`sort_seq` 升序**，同 `sort_seq` 时 **`id` 升序**（再分页），与用户端时间线合并规则一致。**`data.total`**：两表在日期条件下的行数之和。
  - **`data.list[]` 公共字段**：`id`、`role`、`content`、`persona_risk_flag`、`created_at`、`sort_seq`。**来源区分**：**`message_source`** — `conversation`（来自 `conversation_log`）| `agent`（来自 `agent_message`）。两表各自自增 `id` 可能数值重合，**唯一键为 `(message_source, id)`**。
  - ——**`message_source === conversation`**：`emotion_label`、`emotion_confidence`（仅 user 行）、`delivery_status`、`skipped_in_prompt`（assistant 行二者均为 **null**，user 行按库）；**`trigger_type`、`is_read` 固定为 null**。
  - ——**`message_source === agent`**：`role` 固定 **`assistant`**，`emotion_*` 为 null，`persona_risk_flag` 固定 **false**，`delivery_status` / `skipped_in_prompt` 为 **null**，**`trigger_type`** 为 `agent_message.trigger_type`（如 `P0`…`P4`、`FUTURE`），**`is_read`** 为布尔。与 H5 **`GET /api/chat/timeline`**：`items[]` 中对话行对应 `source` 为 `user`/`assistant`，主动消息对应 `source: agent`；
  - 管理端使用字段名 **`message_source`** 而非 `source`，语义可对齐查阅。
- **管理端详情页「历史对话」Tab（`admin/pages/user-detail.html`）**：列表渲染读取 **`message_source`**；**`agent`** 行展示 **`trigger_type`** 标签及 **`is_read === false`** 时的「未读」标签，气泡左侧条样式与主动消息区分。**日期筛选**：**`#conv-start-date` / `#conv-end-date`** 默认 **今天 −7 天 ~ 今天**（仅输入框为空时写入）；**「查询」**与首屏均走 **`loadConversationsInitial`**：先 **`page=1`** 取 **`total`**，再请求 **`page=ceil(total/page_size)`** 渲染（区间内**最新**一页）；列表上方 **「加载更早」** 请求 **`page=当前页−1`** 并 **prepend**（保留滚动位置）；接口侧仍为 **`sort_seq` 升序**分页。
- **GET** `/users/{user_id}/emotion-rounds` — 鉴权 **`super_admin` / `ops_admin`**（与 **`.../conversations`** 一致）。Query：`start_date`、`end_date`（见上文 **`admin_date_filter`**）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**。成功 `data`：`{ total, page, page_size, list[] }`；
  - **`list[]`**：`emotion_log_id`, `round_id`, `emotion_label`, `confidence`, `created_at`, `anchor_conversation_id`, `user_text`（同 `round_id` 下 **user 行按 `sort_seq` 升序**换行拼接）, `assistant_text`（同 `round_id` 下 **assistant 行按 `sort_seq` 升序遍历后的末条** `content`；多气泡轮次与 STEP-011 一致，非首条）。排序：**`emotion_log.created_at` 降序**（最新轮在前）。
  - **管理端详情页「情绪日志」Tab** 首屏**不传**日期（全量时间、降序第一页）。
- **GET** `/users/{user_id}/diaries` — 鉴权 **`super_admin` / `ops_admin` 仅**（与 **`.../conversations`**、**`GET /diary-history`** 一致；**不含** `ai_trainer`，与 **`.../memories`** 不同，属有意区分）。Query：`start_date`、`end_date`（见上文 **`admin_date_filter`**）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**；日期非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`（20029）**。
  - 成功 `data`：`{ total, page, page_size, list }`；**`list[]`** 字段与 **`GET /api/admin/diary-history`** 的 **`list[]`** 相同：`id`, `user_id`, `username`, `content`, `relationship_level_at_creation`, `is_read`, `created_at`, `covers_beijing_date`。实现上与 **`diary-history`** 共用 **`backend.services.admin_diary_query`**，避免双入口不一致。
- **用户记忆 / 私有状态（长记忆第一套下线，C-01/C-09/P3/P5/§6.2.2）**：旧 **`GET/PUT/DELETE /users/{user_id}/memories*`** 已删除，改为两组基于 Step6 向量的 KV CRUD，**主键 `doc_id`**（不再用 `memory_id`），写操作记 `admin_operation_logs`（module 区分 `user_memory` / `private_setting`）。权限 **`super_admin` / `ops_admin` / `ai_trainer`**（P5）。**编辑仅改 value，改 key 走 DELETE + POST**（C-03/§7.2）。`doc_id` 双匹配校验 `is_user_manageable_doc_id`（type + user_suffix），**两组互不互通**（P3）。
  - **`user-memories`（type=`user`）**：
    - **GET** `/users/{user_id}/user-memories` — Query `keyword`/`page`/`page_size`；`data`：`{ total, page, page_size, list:[{doc_id, key, value, content, user_id?}] }`；`total`=cap 内条数（`USER_LIST_TOPK=500`，P9）。
    - **POST** `/users/{user_id}/user-memories` — Body `{key, value}`（key 须三层 `XXX-XXX-XXX`）；`data` 为新条目。
    - **PUT** `/users/{user_id}/user-memories/{doc_id:path}` — Body `{value}`（仅改 value，`doc_id` 需 URL encode，服务端 `unquote`）。
    - **DELETE** `/users/{user_id}/user-memories/{doc_id:path}`。
  - **`private-settings`（type=`character_private`）**：路径与字段同上，固定 `expected_type="character_private"`；页内说明「角色对该用户的私有设定，非用户自传事实」（§7.6）。
- **PUT** `/users/{user_id}/status` — Body `{ "action": "ban"|"unban" }`
- **POST** `/users/{user_id}/reset-password` — `data.new_password`
- **GET** `/voice/users/{user_id}/quota` — `super_admin` / `ops_admin` / `observer` 只读；返回当前上海日期、当前生效的每日免费秒数、今日免费剩余、额外剩余、总剩余和账户 `version`。无账户时只读返回免费余额和版本 0。
- **POST** `/voice/users/{user_id}/quota/extra` — 仅 `super_admin` / `ops_admin`；Body `{seconds, expected_version}`，`seconds` 为 1–86400 的整数。按用户行锁串行化，仅增加 `voice_quota_account.extra_remaining_seconds`，`version` 递增；不修改今日免费余额或通话用量账本。版本不匹配返回 409，重复提交旧版本不会重复补时；首次建户且用户正在通话时返回 409，待通话结算后重试。额度变更与 `admin_operation_logs`（模块「用户管理」、操作 `edit`）同一事务提交。
- **管理端详情页「账号管理」Tab** 展示上述分池余额；有写权限的管理员输入秒数并确认后补充，观察者仅查看。额外秒数跨上海自然日保留；每日免费池仍按已发布配额自动恢复。
- **管理端页面**：`admin/pages/user-detail.html` 含「账号管理」Tab 与顶栏按钮，对接上述 PUT/POST；逻辑上 `**userData.status === 'banned'`** 与 `**basic.status`** 及用户列表 `list[].status` 一致（见错误码 20012、20013）；展示与操作均基于展平后的 `userData`（见上条）。
- **关联表**：users, **relationship**, conversation_log, memory, agent_message 等
- **状态**：已实现

---
