# Relationship Api

- 文档 ID：`contract-relationship-api`
- 权威状态：`canonical`
- 功能范围：`relationship`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-005`

### 模块：H5 关系（`/api/relationship`）

**用户可见口径**：H5 关系页进度与今日总计等文案使用 **「亲密值」**；接口与库表字段仍为 **`growth_value`**、**`growth_info`**、Redis **`growth_*`** 前缀等（技术名不变）。关系页表现见文首 **「2026-05-26 摘要（H5 关系页改版）」**。

#### GET /api/relationship/status

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level, level_name, growth_value, current_growth, next_threshold, progress_percent, silence_days, ai_current_emotion（见 `RelationshipService.get_relationship_info`）
- **关联表**：relationship；Redis
- **状态**：已实现

#### GET /api/relationship/history

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组：今日各行为 `action_type`, `earned_today`, `daily_limit`, `points_per_action`。`long_session`、`reply_agent` 从 SQL 成长日志按北京时间业务日汇总；`dialog`、`daily_login` 保留 Redis 旧 key 前缀 `growth:{user_id}:{date}:{action_type}` 的读取方式。
- **状态**：已实现

#### GET /api/relationship/detail

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level_info, growth_info, milestones, level_history, today_growth, ai_current_emotion
- **今日任务状态**：`today_growth` 提供 `today_dialog_limit`、`today_session_limit`、`today_reply_limit`、`today_voice_limit`。前三项与实际加分常量一致；语音通过通话运行时配置解析器读取当前上限，读取失败返回 `null`，不影响其他积分展示。已开始的通话仍按其冻结快照结算。
- **完成口径**：日常对话、语音、深度聊天、回应消息在今日得分达到对应正数日上限时显示「今日已完成」及勾选；有分但未达上限显示「进行中」，零分显示「待完成」。每日见面获得一次登录奖励即完成，不要求达到登录积分上限。上限为 0 显示「今日暂无奖励」；未知上限不显示完成勾选。完成后仍可查看规则。
- **状态**：已实现

#### GET /api/relationship/growth-log

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ list, total, page, page_size, window_start, window_end }`（`list` 项：id, action_type, action_label, points, created_at）。`created_at` 与窗口边界使用带 `Z` 的 UTC ISO 时间。
- **可见范围**：固定为北京时间今天及前 6 个自然日；`window_start` 包含、`window_end` 不包含（明日 00:00）。`total` 与每页列表均限定同一用户、同一窗口，按 `created_at DESC, id DESC` 稳定排序。跨北京时间零点的后续分页若返回新窗口，客户端清空旧页并重新读取第一页。限制仅作用于查询展示，不删除历史记录，也不改变成长累计或写入规则。
- **关联表**：relationship_growth_log
- **状态**：已实现

---

### 模块：关系规则与日记（管理）

- **GET|PUT** `/relationship-rules` — 两阶段 `confirmed` 预览/发布
- **GET|PUT** `/diary-rules` — `DiaryRulesRequest`（见下文字段）；PUT 发布写入 `admin_config`，Redis `active_config:diary_rules`
- **GET** `/diary-history` — Query：`user_id`（可选）、`start_date`、`end_date`（见 **`admin_date_filter`**，按 **`created_at` 过滤，F1**）、`page`、`page_size`（1–100）；鉴权 **`super_admin` / `ops_admin`**；
  - 成功 `data`：`{ total, page, page_size, list:[{ id, user_id, username, content, relationship_level_at_creation, is_read, created_at, covers_beijing_date }] }`（**`username`** 来自 `users.username`）。列表查询与 **`GET /users/{user_id}/diaries`** 共用 **`fetch_admin_diary_list_page`**，在相同 **`user_id` + 日期 + 分页** 下结果一致；排序 **`created_at` 降序**。
- **状态**：已实现

**`DiaryRulesRequest`（PUT `/diary-rules` Body）**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `max_length` | int | 是 | 50–300 |
| `frequency` | str | 否 | 默认 `daily` |
| `generation_hour` | int | 是 | **0–23**（**北京时间**，与 APScheduler **`Asia/Shanghai`** Cron 一致） |
| `generation_minute` | int | 否 | 0–59，默认 **15**（代码回退默认与 `diary_rules_loader` 一致） |
| `prompt_with_interaction` | str | 条件 | 与 `prompt_without_interaction` **同时非空**时生效 |
| `prompt_without_interaction` | str | 条件 | 同上 |
| `generation_prompt` | str | 条件 | **兼容旧版**：非空时等价于两套 Prompt 使用同一文本（服务端同时写入双字段与 `generation_prompt` 键） |

三者至少满足：**双 Prompt 同时填写** 或 **仅 `generation_prompt`**，否则 `ADMIN_ERR_DIARY_RULE_PARAM_INVALID`。

---

<a id="voice-growth"></a>
### 语音成长增量

`GET /api/relationship/detail`的`today_growth`增加`today_voice_points`并计入今日总值，语音独立使用当前语音成长规则的日上限。内部add_voice_growth仅对合格有效秒数按北京时间结束业务日计分，默认30秒/5分、日100分，与通话终结同事务并按call来源幂等。文字成长和旧history读取语义保留；字段唯一来源见[成长记录](data.md#voice-growth-shared)。

### 深度聊天与回应主动消息奖励（2026-11-04）

- **触发**：H5 / OpenAPI 共用成功聊天后置流程，以已提交的 `round_id` 识别用户消息与 AI 回复；失败、未闭环、未进入 Prompt 的消息不参与。仅打开页面、输入中、标记主动消息已读均不发奖；不追溯补发旧轮次。
- **深度聊天 `long_session`**：每轮取最后一条有效用户发言时间，多条打包及多气泡回复只算一轮。相邻成功轮次发言间隔 **≤300秒** 属于同一段；**>300秒** 重新计时。一段跨度达到 **600秒** 后奖励 **20分**，北京时间每天最多 **20分**，午夜重置计时。发奖在该轮成功收到回复后进行。
- **回应主动消息 `reply_agent`**：寻找上一成功轮次之后、当前轮最后一条有效用户发言之前的最新同用户 `agent_message`，以 `sort_seq` 定序；已读状态不影响回应认定。同一轮前多条主动消息只奖一次 **10分**，同一主动消息永久只奖一次，每个北京时间自然日最多 **20分**；在用户发言后才到达的主动消息不能归给该次发言。
- **一致性**：两项奖励使用用户/关系行锁，积分、升级历史及来源唯一成长日志在同一 SQL 事务内提交；事务失败全部回滚。MySQL 死锁/锁等待超时（1213/1205）仅对奖励整事务最多尝试3次，不重试日常对话/Redis记分。业务日取成功轮次 AI 回复落库时间的北京时间日期；不改原日常对话、登录或语音加分流程。默认积分仍沿用 `GROWTH_ACTIONS`，后台配置未接入的问题仍见 TD-005。
- **查询**：`detail.today_growth.today_session_points`、`today_reply_points` 及 `history` 对应项均读 SQL 日志，计入 `today_total_points`；不依赖两项旧 Redis 计数。无 `business_date` 的历史日志按 `created_at` 对应北京时间日兼容汇总。日志来源字段见 [数据契约](data.md#chat-bonus-sources)。
