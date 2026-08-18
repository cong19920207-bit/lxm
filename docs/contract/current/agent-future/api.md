# Agent Future Api

- 文档 ID：`contract-agent-future-api`
- 权威状态：`canonical`
- 功能范围：`agent-future`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-004`, `TD-015`

### 模块：H5 主动消息（`/api/agent`）

> **P0–P4 生成链路（服务端，非 HTTP）**：定时扫描 **`AgentService.check_and_trigger`** → **`generate_and_save_message`**。Prompt：**`PromptBuilder.build_active_message_prompt`**（Step5 System + 主动任务模块）。LLM：**`chat_with_step5_parse`** → **`messages[]`** 合并为单条 **`content`** 写入 **`agent_message`**。失败兜底：**`AGENT_FALLBACK_REPLIES`**（按 `trigger_type`），**禁止**对话走神占位入库。FUTURE 走 **Step8**（`execute_step8_subchain`），本段不适用。

#### GET /api/agent/messages

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组 `{id, trigger_type, content, action_score, created_at}[]`（仅未读）
- **关联表**：agent_message
- **状态**：已实现

#### POST /api/agent/messages/{message_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`
- **状态**：已实现

#### GET /api/agent/unread-count

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`: `{ count: int }`
- **说明**：计入全部未读 `agent_message`（含生活流感知 **`LIKE_AWARE` / `READ_AWARE`**，与 P0–P4/FUTURE 同表）
- **状态**：已实现

---

### 模块：Agent 管理

#### GET /api/admin/agent-night-keywords

- **所属端**：管理后台
- **鉴权**：Bearer Admin JWT（角色同 PUT：`super_admin` / `ai_trainer`）
- **响应**：`ApiResponse`；`data` 与 **PUT** Body 一致：`{ "keywords": string[] }`（无生效配置时 `keywords` 为空数组 `[]`）
- **数据来源**：`get_active_config("agent_night_keywords", use_cache=False)`（查 **admin_config** 当前生效行，**不**经 Redis）
- **关联表**：admin_config
- **同模块其它路由**：**GET|PUT** `/agent-rules` — `AgentRulesRequest`；**GET** `/agent-message-rules`（整包）/ **PUT** `/agent-message-rules/{trigger_type}`（单类型）；**PUT** `/agent-night-keywords` — `NightKeywordsRequest`；**GET** `/agent-messages` — Query：`user_id`（可选）、`trigger_type`、`is_read`、`start_date`、`end_date`（见 **`admin_date_filter`**）、`page`、`page_size`（1–100）；
  - 鉴权 **`super_admin` / `ops_admin` / `ai_trainer`**；排序 **`created_at` 降序**；成功 `data`：`{ total, page, page_size, list[] }`；**`list[]`**：`id`, `user_id`, `trigger_type`, `content`, `action_score`, `is_read`, `created_at`
- **状态**：已实现

---
