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

<a id="submission-status"></a>
### 原身份复用与 GET /api/open/v1/chat/submissions/{operation}/{request_id}

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

send 可选请求头 `Idempotency-Key`≤64、resend≤128；空串合法，缺失生成内部UUID。身份与H5同可信user/operation域，不按API key/入口拆分。原字节ID、重复/冲突、额度及D规则唯一见[文字身份](../chat-emotion/api.md#chat-idempotency)。原成功data仍 `{messages,emotion,round_id}`，timeline原十字段/三来源、cursor/limit不变。

此GET使用原API key认证用户，只读ApiResponse；operation=send/resend，request_id=`b64.`+规范无填充base64url原UTF8，空ID=`b64.`，非法422。返回字段、精度、not_found/expired/unverified和未知不可重发规则完整复用[SubmissionStatus](../chat-emotion/api.md#submission-status)，不复制第二套DTO。

SQL提交、未知回执及有限恢复权威见[文字持久状态](../chat-emotion/data.md#chat-lifecycle)，Open和H5调用同一实际bundle。无ID旧调用方可继续，但丢回执后不能凭正文/时间精确核实；第三方保留原身份查询，项目不代改其本地timeout或新增重发动作。
