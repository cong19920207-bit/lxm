# Openapi Api

- 文档 ID：`contract-openapi-api`
- 权威状态：`canonical`
- 功能范围：`openapi`
- 必读依赖：`contract-shared-conventions`, `contract-chat-emotion-api`, `contract-agent-future-api`
- 相关技术债：`TD-030`, `TD-031`

### POST `/api/open/v1/chat/send`

- 鉴权：`get_current_user_by_api_key`
- Body：`OpenChatSendRequest` `{ "content": "1-2000" }`
- 成功 `data`：`{ messages, emotion, round_id }`（与 H5 SSE `done` 同源提取）
- 业务码：10101/10102/10104/10108 等同 H5 规则

### POST `/api/open/v1/chat/resend`

- **无 Body 参数**（空 POST）
- 10107/10105 等同 H5；`failed_blocked` 不可 resend（TD-030）

### GET `/api/open/v1/chat/timeline`

- Query：`cursor`、`limit`；`data`沿用Open v1原十字段/三来源投影（`timeline_read_service`），不继承H5语音扩展，见下方兼容边界。

### GET `/api/open/v1/agent/messages` · GET `/api/open/v1/agent/unread-count` · POST `/api/open/v1/agent/messages/{message_id}/read`

- `data` 与对应 H5 `/api/agent/*` 一致

### Admin：GET/POST `/api/admin/users/{user_id}/open-api-key`

- RBAC：`super_admin`、`ops_admin`
- GET：`enabled`、`key_prefix`、`created_at`、`last_used_at`（无明文）
- POST：响应一次性 `api_key`；操作日志 `create` / `edit`（N4）

---

#

<a id="voice-compatibility"></a>
### 与H5语音时间线的兼容边界

Open v1 timeline保持`items/next_cursor/has_more`、原cursor/limit语义，item仅有`source,sort_seq,id,content,created_at,emotion_label,delivery_status,skipped_in_prompt,is_read,trigger_type`十字段，source仅user/assistant/agent。不包含source=call、call_id/duration_seconds/call_status/summary_status/call_summary或crisis_resource。H5语音卡片占用全局sort_seq可形成序号空隙，不改变Open分页行为。未知第三方消费者按可能存在保护原协议；不新增v2。
