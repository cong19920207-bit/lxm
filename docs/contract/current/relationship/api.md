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
- **响应**：`ApiResponse`；`data` 为数组：今日各行为 `action_type`, `earned_today`, `daily_limit`, `points_per_action`（读 Redis 旧 key 前缀 `growth:{user_id}:{date}:{action_type}`，写入侧同时写新旧 key，仍可读）
- **状态**：已实现

#### GET /api/relationship/detail

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level_info, growth_info, milestones, level_history, today_growth, ai_current_emotion
- **状态**：已实现

#### GET /api/relationship/growth-log

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ list, total, page, page_size }`（`list` 项：id, action_type, action_label, points, created_at）
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
