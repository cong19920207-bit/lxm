# 林小梦 Open API v1 集成文档

> 面向第三方客户端（桌面宠物等）。鉴权使用同一账号的 **API Key**；普通接口返回 JSON，朋友圈新帖通知使用 SSE。
> 生产 Base URL（已确认）：**`http://cllxm.com`**  
> **对外完整接入指南（含流程图、字段表、联调清单）**：[`docs/partner/林小梦-OpenAPI-宠物端接入指南.md`](../../partner/林小梦-OpenAPI-宠物端接入指南.md)

---

## 1. 配置项

| 配置 | 说明 |
|------|------|
| **服务器地址 / Base URL** | 根地址，不含 `/api/...`，例 `http://cllxm.com` |
| **API Key** | 在对应环境 Admin → 用户详情 → 生成，格式 `sk-lxm-...` |

拼接示例：`{BaseURL}/api/open/v1/chat/send`  
测试环境 Base URL 向运维索取；**测试 Key 不能用于生产**。

2026-11-13 已在本地 Docker 的 `http://127.0.0.1:8000` 验证日记与朋友圈。该环境升级前签发且仍有效的 Key 可直接访问，无需重新签发或单独授权。生产开放时间以运营通知为准。

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

普通接口 HTTP 200 时使用以下信封，成功为 `code=0`，业务失败为非零码。HTTP 401 和 422 返回 `detail`；朋友圈新帖 SSE 按事件流读取。

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

聊天 `send` / `resend` 的客户端 HTTP 超时建议 **≥ 130s**（服务端等待上限 120s）。

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
响应沿用 Open v1 原 `items/next_cursor/has_more` 和十字段、user/assistant/agent 三来源投影，不再泛称与 H5 一致。H5新增语音卡片/危机资源字段不进入 v1；sort_seq空隙合法。唯一协议定义见[OpenAPI 当前契约](../../contract/current/openapi/api.md#voice-compatibility)。

### GET `/api/open/v1/agent/messages`

未读主动消息列表，与 H5 一致。

### GET `/api/open/v1/agent/unread-count`

`data`: `{ "count": 0 }`，供托盘轮询。

### POST `/api/open/v1/agent/messages/{message_id}/read`

标记单条已读。

### 日记与朋友圈

下表路径相对 `/api/open/v1`。列表预取只用于浏览，显示正文或回复后再调用对应的已读接口。

| 客户端动作 | 请求 |
|---|---|
| 阅读日记与同步已读 | `GET /diary/list` 按页码读取已有全文，`POST /diary/{diary_id}/read` 上报已展示的日记。见[日记分页、月历和示例](../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-diary)。 |
| 浏览朋友圈 | `GET /feed/config/header` 取页头，`GET /feed/list` 按游标翻页，`GET /feed/posts/{post_id}` 刷新单帖的正文、图片、本人评论及小梦回复。 |
| 点赞、发评、读回复 | `POST /feed/{post_id}/like` 点赞，`DELETE /feed/{post_id}/like` 取消；`POST /feed/{post_id}/comments` 发评并支持原键重试；`POST /feed/{post_id}/read` 和 `POST /feed/comments/{comment_id}/read` 分别上报读帖和读回复。 |
| 角标、进入与新帖提醒 | `GET /feed/badge` 查询角标，用户打开页面时调用 `POST /feed/enter`；`GET /feed/events` 使用 Bearer 鉴权并返回 `text/event-stream`。见[朋友圈字段、重试和订阅](../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-feed)。 |

其他已开放能力见[养宠接口](../../contract/current/openapi/api.md#pet-openapi)和[聊天请求状态查询](../../contract/current/openapi/api.md#submission-status)。

### BGM 背景音乐

`GET /api/open/v1/bgm/catalog` 使用同一环境已签发的有效 Key，返回 `catalog_version, default_track_id, tracks`。播放器由 `tracks[]` 取曲名、时长、音频与可选封面，使用返回的 HTTPS 地址直接读取媒体。仅目录请求携带 Key。空曲库返回 HTTP 200 和空数组，曲库暂不可用返回 HTTP 503、业务码 20207 和 `Retry-After: 2`。参见[第三方指南的播放示例](../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-bgm)。

---

### 记忆星云（记忆星球）

`GET /api/open/v1/memory/list?page=1&page_size=50` 使用已有账号 Key。按页码返回 `total, page, page_size, list`，单条含 `doc_id, key, value, content`。每页默认 20 条、最多 50 条，当前可浏览集合最多 500 条。客户端可以直接按记录显示星体和正文。参见[记忆星云接入指南](../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-memory)。

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
