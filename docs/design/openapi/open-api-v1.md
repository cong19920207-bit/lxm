# 林小梦 Open API v1 集成文档

> 面向第三方客户端（桌面宠物等）。鉴权：**API Key**；响应：**同步 JSON**（非 SSE）。  
> 生产 Base URL（已确认）：**`http://cllxm.com`**  
> **对外完整接入指南（含流程图、字段表、联调清单）**：[`docs/partner/林小梦-OpenAPI-宠物端接入指南.md`](../partner/林小梦-OpenAPI-宠物端接入指南.md)

---

## 1. 配置项

| 配置 | 说明 |
|------|------|
| **服务器地址 / Base URL** | 根地址，不含 `/api/...`，例 `http://cllxm.com` |
| **API Key** | 在对应环境 Admin → 用户详情 → 生成，格式 `sk-lxm-...` |

拼接示例：`{BaseURL}/api/open/v1/chat/send`  
测试环境 Base URL 向运维索取；**测试 Key 不能用于生产**。

---

## 2. 鉴权

请求头：

```http
Authorization: Bearer sk-lxm-xxxxxxxx
```

鉴权失败为 **HTTP 401**，响应体 FastAPI 标准：

```json
{"detail":"未提供 API Key"}
```

| 场景 | detail | 备注 |
|------|--------|------|
| 未提供 Authorization | `未提供 API Key` | 含响应头 `WWW-Authenticate: Bearer` |
| Key 无效/已吊销/格式错误 | `API Key 无效或已吊销` | 不区分具体原因 |
| 用户被禁用 | `账号已被禁用` | |

**勿**将 API Key 用于 H5 路由 `/api/chat/*`（会按 JWT 拒绝）。

---

## 3. 业务响应信封

成功/业务失败（除 401 外）：

```json
{"code":0,"data":{},"message":"success"}
```

`send` / `resend` 成功 `data`：

```json
{
  "messages": [{"type":"text","content":"..."}],
  "emotion": {"label":"开心","confidence":0.9},
  "round_id": "uuid"
}
```

| code | 含义 |
|------|------|
| 10101 | 内容安全（入队前或 `failed_blocked`） |
| 10102 | LLM 失败/超时 |
| 10104 | 队列满（未闭环 ≥5 且无叹号） |
| 10105 | 重发过于频繁 |
| 10107 | 当前无可重发 |
| **10108** | 等待中被新消息作废，请拉 timeline 对账 |

客户端 HTTP 超时建议 **≥ 130s**（服务端等待上限 120s）。

---

## 4. 接口列表

### POST `/api/open/v1/chat/send`

Body：`{"content":"1-2000字"}`

### POST `/api/open/v1/chat/resend`

**无 Body**（空 POST 即可）。

仅当 timeline 中存在 `failed_timeout` / `failed_error` 叹号窗口时可重发。  
**`failed_blocked` 不可 resend**，须重新 `send`（见技术债 TD-030）。

### GET `/api/open/v1/chat/timeline`

Query：`cursor`（可选）、`limit`（1–50，默认 20）。  
响应与 H5 `GET /api/chat/timeline` 的 `data` 一致。

### GET `/api/open/v1/agent/messages`

未读主动消息列表，与 H5 一致。

### GET `/api/open/v1/agent/unread-count`

`data`: `{ "count": 0 }`，供托盘轮询。

### POST `/api/open/v1/agent/messages/{message_id}/read`

标记单条已读。

---

## 5. 传输安全（S16）

- 当前生产为 **HTTP** 明文传输，Bearer 中的 Key 可能被中间人窃听。
- **强烈建议** 仅在受信网络使用，或待 HTTPS 上线后更新 Base URL。
- **禁止**在浏览器地址栏或前端页面直连 Open API（避免 Key 泄露）。
- 服务端与 Nginx **不应**在 access log 中记录 `$http_authorization`。

---

## 6. curl 示例（生产）

```bash
curl -X POST 'http://cllxm.com/api/open/v1/chat/send' \
  -H 'Authorization: Bearer sk-lxm-你的Key' \
  -H 'Content-Type: application/json' \
  -d '{"content":"你好"}'
```
