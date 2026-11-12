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

<a id="pet-openapi"></a>
### 养宠 `/api/open/v1/pet`（2026-11-07）

接口前缀为 `/api/open/v1/pet`；2026-11-07 已完成真实 HTTP/MySQL 验证、并发回执及占用/奖励上限修复，见首次验收（本地留存，未随本次提交；原引用：`../../../superpowers/plans/evidence/2026-11-07-pet-openapi-live.json`）与并发修复验收（本地留存，未随本次提交；原引用：`../../../superpowers/plans/evidence/2026-11-07-pet-openapi-concurrency.json`）。此生效结论仅覆盖本地环境，生产未部署。

使用现有 `Authorization: Bearer <API Key>` 与 `get_current_user_by_api_key`。操作账号在平台领养的同一只小狗，状态、记录、占用及亲近度与 H5 共享。成功程序互动按本人参与计算；只查询不计活跃，不创建页面停留心跳。接口使用 `ApiResponse`，响应设置 `Cache-Control: private, no-store`、`Vary: Authorization`。

**必须先在平台领养。** Open 不提供 `/adopt`，也不自动领养。`GET /me` 成功返回 `{adopted,pet,adoption_path}`：

- 未领养：`{adopted:false,pet:null,adoption_path:"/pages/pet.html"}`，message 为“请先到平台领养小狗”。相对入口使用平台站点地址打开。
- 已领养：`adopted:true`、`pet` 为[现有宠物档案](../pet-system/api.md)，`adoption_path:null`。读取可触发时间结算，但不是用户参与。
- 其他业务接口均服务端核对宠物归属。无宠物时 `code=20302`，`data={reason:"pet_not_found",adoption_path:"/pages/pet.html"}`，message 同上；不创建宠物、尝试或事实。资源不存在或属于他人时返回对应不可用原因，不返回领养引导。

以下路径相对 `/api/open/v1/pet`；所有写入请求体拒绝未知字段，不接受 user_id、actor、completion_mode 或手势 evidence。请求键 `request_key` 1–96 字符，必须非空白；attempt_id/event_id 最长 36 字符。

| 方法 | 路径 | 请求与成功 data |
|---|---|---|
| GET | `/me` | 上述领养状态与档案。 |
| POST | `/feed` | `{request_key}`；即时喂食，返回现有互动结果。已饱或被占用时沿现有拒绝规则。 |
| POST | `/interactions` | `{kind:"touch"或"play",request_key}`；创建程序互动尝试。 |
| GET | `/interaction-requests?request_key=...` | 推荐恢复入口，查询参数按 URL 编码，支持包含斜杠、空格等字符的原键；未查到时 `data=null`。 |
| GET | `/interaction-requests/{request_key}` | 同一结果的路径别名，适用于 UUID 等单路径段标识；任意请求键使用上述 query 入口，避免路径解码或归一化改变原键。 |
| GET | `/interactions/{attempt_id}` | 本账号尝试结果；读取不自动完成或推进尝试终态。 |
| POST | `/interactions/{attempt_id}/finish` | `{}` 或 `{cancel:false}` 尝试完成；`{cancel:true}` 取消。 |
| GET | `/records` | 可选 `day=YYYY-MM-DD`，按上海业务日返回现有日记录。 |
| GET | `/events/{event_id}` | 可选 `origin=daily/album`、`origin_date=YYYY-MM-DD`，返回现有事件详情。 |
| GET | `/expressions/{event_id}` | 返回事件表达及 `pending/stale/source`；保持模板兜底与 AI 预算约束。 |

互动结果沿用 `{id,kind,state,event_id,result,expression,started_at,expires_at,payload,pet}`；程序抚摸/陪玩额外返回 `ready_at` 和 `retry_after_ms`。`payload.completion_mode=programmatic`，`minimum_seconds` 为创建时适用规则。终态 `retry_after_ms=0`。

- 创建后根据 `retry_after_ms` 等待，再提交 finish；过早 finish 保持 `code=0,state=pending` 并返回剩余等待，不奖励、不终结。单纯等待或 GET 不完成动作。客户端依据服务端状态处理，不能仅靠本地时钟认定完成。
- 到时 finish 重验运行开关、宠物版本、期限和状态；成功 `state=done,result.completed=true`，通过同一完成服务记录事实、状态变化、亲近度与活跃。冷却或当日奖励已满仍可完成，按原规则不给额外亲近度。
- 取消、过期、版本变化、停用或精力不足可分别返回 `cancelled/expired/obsolete/blocked/refused`；不能当作成功参与。程序尝试窗口为 `max(60秒,minimum_seconds+30秒)`。
- 同键同动作同模式重放返回原尝试；同键换动作或模式为 `20303/request_content_changed`。H5 原尝试不能由 Open finish 完成，Open 原尝试也不能用 H5 finish 完成；返回 `20303/interaction_entry_mismatch`。两端同账号结果可读。
- 网页及 Open 共用单个待完成互动占用，冲突按现行 `pet_busy` 处理。现有奖励冷却、每日上限、喂食与精力规则、AI 并发和费用上限都继续生效。
- 丢回执时保留原 `request_key/attempt_id` 查询。查不到也只重试原请求，不换键重做。GET 返回过期时间已过但仍为 pending 时，可用原 finish 收敛为 expired，或由下次新动作清理过期占用。
- 鉴权 HTTP 401；结构错误 HTTP 422；宠物业务错误 HTTP 200 + 非零 code/data.reason。客户端必须同时检查 HTTP 状态和业务码；不要因 `code=0` 就把 pending/refused 当作已完成。

最小调用示例（`LXM_BASE_URL`、`LXM_API_KEY` 由调用方设置，密钥不写入代码或日志）：

```bash
curl "$LXM_BASE_URL/api/open/v1/pet/me" \
  -H "Authorization: Bearer $LXM_API_KEY"

# 确认 adopted=true 后，为这次动作生成并保存唯一请求键。
curl "$LXM_BASE_URL/api/open/v1/pet/interactions" \
  -H "Authorization: Bearer $LXM_API_KEY" -H 'Content-Type: application/json' \
  -d '{"kind":"touch","request_key":"一次动作的唯一请求键"}'

# 保存返回的 id 到 ATTEMPT_ID，按 retry_after_ms 等待后提交；未知结果用原 id 查询。
curl "$LXM_BASE_URL/api/open/v1/pet/interactions/$ATTEMPT_ID/finish" \
  -H "Authorization: Bearer $LXM_API_KEY" -H 'Content-Type: application/json' -d '{}'
```

循环由外部程序驱动：读状态与 `availability` → 选择动作 → 等待/完成或处理拒绝 → 读结果与记录 → 决定下次动作。共同玩球、照片、改名、前台心跳和服务器托管自动照顾不在此 Open 接口范围内。
