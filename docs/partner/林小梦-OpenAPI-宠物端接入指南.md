# 林小梦 Open API — 宠物端接入指南

> **文档版本**：v1.5
> **适用接口**：Open API v1（`/api/open/v1/*`）  
> **最后更新**：2026-11-28
> **读者**：第三方桌面宠物 / 客户端开发同学  

外部客户端用同一账号的 **Base URL 与 API Key** 接入对话、主动消息、日记、朋友圈、BGM 和记忆星云（记忆星球）。本地 Docker 已验证，升级前签发的有效 Key 可直接使用这些能力，无需换 Key 或单独授权。生产环境的开放时间以运营通知为准。

---

## 目录

1. [能力范围](#1-能力范围) · [我的应用要改吗？](#partner-chat-upgrade)
2. [接入前准备](#2-接入前准备)
3. [环境配置（Base URL）](#3-环境配置base-url)
4. [鉴权](#4-鉴权)
5. [通用约定](#5-通用约定)
6. [推荐客户端流程](#6-推荐客户端流程)
7. [接口说明](#7-接口说明) · [聊天未读](#partner-chat-unread) · [日记](#partner-diary) · [朋友圈](#partner-feed) · [BGM](#partner-bgm) · [记忆星云](#partner-memory)
8. [时间线字段与状态](#8-时间线字段与状态)
9. [错误码与处理](#9-错误码与处理)
10. [安全要求](#10-安全要求)
11. [联调与验收](#11-联调与验收)
12. [常见问题](#12-常见问题)
13. [附录：curl 示例](#13-附录curl-示例)

---

## 1. 能力范围

### 1.1 客户端可接入的能力

| 能力 | 接口 |
|------|------|
| 发送用户消息（同步等待 AI 回复） | `POST /api/open/v1/chat/send` |
| 失败重发（叹号恢复） | `POST /api/open/v1/chat/resend` |
| 拉取统一时间线（历史、对账、失败态） | `GET /api/open/v1/chat/timeline` |
| 同一账号的聊天总未读（首页、托盘角标） | `GET /api/open/v1/chat/unread` |
| 核对一批已加载气泡的未读状态 | `GET /api/open/v1/chat/unread/status` |
| 确认用户看到的一条普通回复或主动消息 | `POST /api/open/v1/chat/messages/{source}/{id}/read` |
| 未读主动消息列表 | `GET /api/open/v1/agent/messages` |
| 仅主动消息的未读数量 | `GET /api/open/v1/agent/unread-count` |
| 标记主动消息已读 | `POST /api/open/v1/agent/messages/{message_id}/read` |
| 阅读日记、翻页、月历和已读同步 | [日记的 2 个接口和分页规则](#partner-diary) |
| 浏览动态与图片、点赞、评论与回复、角标和新帖通知 | [朋友圈的 11 个接口和交互规则](#partner-feed) |
| 展示曲库、播放背景音乐 | [BGM 曲库与播放示例](#partner-bgm) |
| 浏览账号的长期记忆、点开星体查看正文 | [记忆星云分页与字段](#partner-memory) |

客户端还可以[查询聊天请求的提交状态](../contract/current/openapi/api.md#submission-status)，或用同一 Key [与平台已领养的小狗互动](../contract/current/openapi/api.md#pet-openapi)。

### 1.2 本接入不包含

以下能力 **不在 Open API v1**，请勿使用 H5 的 JWT 路由（`/api/chat/*`、`/api/auth/*` 等）：

- 用户注册 / 登录 / Token 刷新  
- 独立查询当前关系等级、亲密值
- SSE 流式对话  
- 管理后台（`/api/admin/*`）  

业务错误提示请 **直接展示** 响应中的 `message` 字段（服务端已配置中文文案）。

### 1.3 数据同源说明

- 每个 API Key 绑定 **一个** 林小梦 H5 用户账号。  
- 两端共享同一账号的文字消息、主动消息、日记已读、点赞、评论和回复。朋友圈的 `comments` 只返回当前账号可见的本人评论及小梦的回复。
- H5 和宠物端发起的聊天都进入同一条时间线。任一端发送或重发后，小梦每个成功保存的回复气泡各算一条未读，每条主动消息也各算一条。用户发言、失败请求和通话卡片不计数。任一端确认一条，另一端下次查询即可看到这条已读。

```mermaid
flowchart LR
  subgraph 宠物端
    Pet[桌面宠物客户端]
  end
  subgraph 林小梦服务端
    Open["/api/open/v1/*<br/>API Key 鉴权"]
    Core[对话主链<br/>记忆/关系/安全/LLM]
    DB[(聊天记录与逐条已读状态)]
  end
  subgraph 其它端
    H5[H5 聊天页<br/>JWT 鉴权]
  end
  Pet -->|Bearer sk-lxm-...| Open
  Open --> Core
  Core --> DB
  H5 -->|Bearer JWT| Core
```

<a id="partner-chat-upgrade"></a>
### 1.4 我的应用要改吗？

已有应用可沿用当前环境的 Base URL 和有效 Key。按应用实际提供的功能判断，多项适用时分别处理。

| 应用现在怎么用 | 需要做什么 |
|---|---|
| 只调用发送、重发或获取文本，例如后台脚本 | 能容忍新增响应字段的应用可继续使用原请求。脚本收到文本后无需发回执，这些回复会保留在同账号的聊天未读中。 |
| 用严格模型解析 JSON，例如遇到额外字段就报错 | 更新 `send`、`resend` 成功结果的气泡模型，接受 `id`、`sort_seq`、`is_read`。若也解析提交状态的 `result.messages[]`，同步更新。时间线的 `assistant.is_read` 接受布尔值，`user.is_read` 仍可为 `null`。 |
| 在首页或托盘显示「所有聊天未读」 | 角标改读 `GET /chat/unread` 的 `data.count`，其中已包含主动消息。只展示「主动消息未读」的独立入口可继续使用 `/agent/unread-count`。 |
| 有聊天阅读界面，希望在宠物端看过的气泡也从 H5 未读中消掉 | 展示时保留每条的 `source` 和 `id`，用户实际读到哪条就发哪条回执。返回前台时重新核对已加载气泡和角标。 |

历史普通回复已有的已读或未读状态继续生效。历史上未记录阅读状态的普通回复按已读展示。完整请求和响应见[聊天未读接口](#partner-chat-unread)。

---

## 2. 接入前准备

### 2.1 账号与 API Key（一对一）

| 规则 | 说明 |
|------|------|
| 绑定关系 | Key 对应一个林小梦账号。日记、朋友圈和聊天都从 Bearer Key 识别用户，请求无需传用户 ID。 |
| Key 签发 | 由林小梦运营在管理后台 **手动生成**，明文 **仅展示一次** |
| Key 格式 | `sk-lxm-` + 随机串，例：`sk-lxm-a1b2c3d4...` |
| 重新生成 | 在后台对该用户再次「生成/重新生成」会 **立即吊销** 旧 Key，宠物端须更新配置 |
| 获取方式 | **联系林小梦运营** 提供对应环境的 Base URL 与 API Key（联调、生产分别申请） |

运营侧操作路径（供对接参考，宠物端无需调用）：管理后台 → 用户管理 → 用户详情 → **Open API Key** → 生成。

### 2.2 宠物端须实现的配置项

在宠物 **设置页** 提供两项可编辑配置（用户粘贴即可，与常见 SaaS 接入方式一致）：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| **服务器地址 / Base URL** | 林小梦服务根地址，**不要**包含 `/api/...` 路径；末尾不要加 `/` | 生产：`http://cllxm.com` |
| **API Key** | 该环境下运营签发的 Key | `sk-lxm-xxxxxxxx` |

**URL 拼接规则：**

```text
完整接口地址 = {Base URL}/api/open/v1/{资源路径}
```

示例：

```text
Base URL:  http://cllxm.com
发送消息:  http://cllxm.com/api/open/v1/chat/send
```

> **重要**：测试环境与生产环境的 **Base URL 与 API Key 必须成对更换**。测试库签发的 Key **不能**用于生产 Base URL。

---

## 3. 环境配置（Base URL）

采用 **「用户粘贴不同 Base URL 切换环境」** 的最简方案，林小梦不在宠物包内写死环境列表。

| 环境 | Base URL（配置值） | API Key |
|------|-------------------|---------|
| **生产** | `http://cllxm.com` | 在生产环境由运营签发 |
| **联调 / 测试** | 联调时由运营 **单独提供**（常见为运营本地 Docker 暴露的地址，如 `http://127.0.0.1` 或内网 IP；**以运营当时提供的为准**） | 在 **同一测试环境** 由运营签发 |

说明：

- 生产公网当前为 **HTTP**（非 HTTPS），见 [§10 安全要求](#10-安全要求)。若后续升级为 HTTPS，只需在宠物设置中把 Base URL 改为 `https://cllxm.com`，Key 不变。  
- 在运行本项目 Docker 的电脑上，已验证的 Base URL 为 `http://127.0.0.1:8000`（经 Nginx）。另一台设备联调时请用运营提供的可达地址，`127.0.0.1` 指向设备自身。
- 文档 **不写死** 测试 Key；实际联调时向运营索取 **一对**「测试 Base URL + 测试 API Key」。

---

## 4. 鉴权

### 4.1 请求头

所有 `/api/open/v1/*` 请求必须携带：

```http
Authorization: Bearer sk-lxm-你的APIKey
```

- 发送 JSON 请求体时附 `Content-Type: application/json`。订阅朋友圈新帖时可附 `Accept: text/event-stream`；图片直接使用返回的 URL 加载，不向图片域名转发 API Key。
- 把 API Key 拿去调 `/api/chat/send` 等 H5 接口会 **401**；把 JWT 拿来调 Open 接口也会 **401**。

### 4.2 鉴权失败（HTTP 401）

鉴权失败 **不** 使用业务信封 `{code, data, message}`，而是 FastAPI 标准格式：

```json
{"detail":"未提供 API Key"}
```

| HTTP | `detail` 文案 | 处理建议 |
|------|---------------|----------|
| 401 | `未提供 API Key` | 检查是否携带 `Authorization` |
| 401 | `API Key 无效或已吊销` | 检查 Key 是否粘贴完整、是否已被重新生成 |
| 401 | `账号已被禁用` | 联系运营处理用户状态 |

---

## 5. 通用约定

### 5.1 业务响应信封

普通接口的 HTTP 200 响应使用下列 JSON 信封。HTTP 401 和 422 返回 `detail`；朋友圈 `GET /feed/events` 成功后返回 SSE 流。

```json
{
  "code": 0,
  "data": {},
  "message": "success"
}
```

| 字段 | 说明 |
|------|------|
| `code` | `0` 表示成功；非 `0` 为业务错误码 |
| `data` | 成功时的业务数据；失败时多为 `null` |
| `message` | 人类可读文案；**失败时请直接展示给用户** |

### 5.2 HTTP 超时

| 接口类型 | 建议客户端超时 |
|----------|----------------|
| `POST .../chat/send`、`POST .../chat/resend` | 按部署的等待时限预留网络时间。本版业务时限从服务端接收并登记请求起算 180 秒，默认配置下的 curl 示例设置为 210 秒 |
| 普通 JSON 查询 | 10–30 秒 |
| `GET /feed/events` | 长连接；空闲时约每 15 秒收到心跳，可据此设置读取超时。 |

### 5.3 参数校验失败（HTTP 422）

例如 `send` 的 `content` 为空或超过 2000 字，可能返回 **422**，body 为 FastAPI 校验详情，**不是** 上表业务信封。宠物端应在本地先做长度校验（1–2000 字），尽量避免 422。

---

## 6. 推荐客户端流程

### 6.1 应用冷启动

```mermaid
sequenceDiagram
  participant Pet as 宠物端
  participant API as 林小梦 Open API

  Pet->>API: GET /chat/unread
  API-->>Pet: count, first_unread, latest_unread
  Pet->>Pet: 用 count 更新聊天总角标
  opt 打开聊天窗口
    Pet->>API: GET /chat/timeline?limit=20
    API-->>Pet: items[], has_more, next_cursor
    Pet->>Pet: 按时间顺序展示，保留每条的 source 和 id
  end
```

应用启动或回到前台时，用当前账号的 Key 查询总未读。用户打开聊天时加载时间线，已有缓存的气泡可用 `GET /chat/unread/status` 核对。打开窗口、加载历史或在后台轮询都不会消除未读。[逐条确认流程](#partner-chat-flow)

### 6.2 用户发送消息

```mermaid
sequenceDiagram
  participant User as 用户
  participant Pet as 宠物端
  participant API as 林小梦 Open API

  User->>Pet: 输入并发送
  Pet->>Pet: 乐观展示 user 气泡（可选）
  Pet->>API: POST /chat/send { content }
  Note over Pet,API: 同步等待结果，用户可能已经离开聊天
  alt code = 0
    API-->>Pet: messages[], emotion, round_id
    alt 用户仍在聊天页
      Pet->>Pet: 按 id 展示气泡，逐条判断正文是否可见
    else 用户已离开
      Pet->>Pet: 保留未读，刷新聊天总角标
    end
  else code = 10108
    API-->>Pet: message 提示已作废
    Pet->>API: GET /chat/timeline
    Pet->>Pet: 以时间线为准刷新
  else 其它 code
    API-->>Pet: message
    Pet->>Pet: Toast 展示 message
    Pet->>API: GET /chat/timeline（建议）
  end
```

**要点：**

- `send` 为 **同步**：一次请求返回完整 AI 回复，无需再收 SSE。  
- `data.messages` 为数组，**按顺序逐条展示**（与线上一致，可能 1–3 条短句）。  
- 每个元素含 `id`、`sort_seq`、`type`、`content`、`is_read`。用 `content` 显示正文，用 `assistant` 和该元素的 `id` 提交回执。接收响应时保留服务端返回的阅读状态。
- `data.emotion`：`{ "label": "开心", "confidence": 0.9 }`，可用于切换宠物表情/氛围（可选）。  
- 用户 **连发** 时，较早的请求可能返回 **10108**，必须以 **timeline 对账** 为准，不要当作最终失败。

### 6.3 失败与叹号重发

**内容安全分两条路径（勿混淆）：**

| 阶段 | 行为 | 同步接口 | timeline user 行 |
|------|------|----------|------------------|
| **用户输入**不安全 | 入队前拦截，**不写入** `pending_llm` | **10101**，展示 `message` | 通常无新行 |
| **AI 输出**不安全 | 已入队生成后拦截 | **10101**，展示 `message` | **`failed_blocked`** |

```mermaid
stateDiagram-v2
  [*] --> rejected_input: 用户输入不安全
  rejected_input --> [*]: send 返回 10101
  [*] --> pending_llm: 用户 send 入队成功
  pending_llm --> delivered: LLM 成功
  pending_llm --> failed_timeout: 超时
  pending_llm --> failed_error: LLM/服务错误
  pending_llm --> failed_blocked: AI 输出内容安全
  failed_timeout --> delivered: resend 成功
  failed_error --> delivered: resend 成功
  failed_blocked --> [*]: 不可 resend，须新 send
```

1. 通过 `timeline` 查看 **user** 行的 `delivery_status`。  
2. 仅当存在 **`failed_timeout`** 或 **`failed_error`** 时，可调用 `POST /chat/resend`（**无 Body**）。  
3. **`failed_blocked` 不可 resend**（同步接口已是 10101）；须提示用户 **重新 `send` 新内容**（不必改原句，新一句即可）。  
4. `resend` 成功后按 `send` 的方式处理每个新回复气泡。用户已退出聊天时，新回复仍逐条计入未读。

<a id="partner-chat-flow"></a>
### 6.4 退出聊天再回来，看到哪条就消哪条

假设同一账号原先没有未读。用户从 H5 发完消息就退回首页，小梦随后回复两条，示例 ID 为 41、42。通过 Open API 发起对话也遵循同一规则。下图特意先读第二条，便于验证第一条是否仍然未读。图中宠物端的请求路径相对 `/api/open/v1`。

```mermaid
sequenceDiagram
  participant H5 as 同账号 H5
  participant API as 聊天服务
  participant Pet as 宠物端
  H5->>API: 发送消息
  Note over H5: 用户退回首页
  Note over API: 保存普通回复 41、42，各增加一条未读
  Pet->>API: GET /chat/unread
  API-->>Pet: count = 2
  Pet->>API: GET /chat/timeline
  Note over Pet: 用户只看到第二条正文
  Pet->>API: POST /chat/messages/assistant/42/read
  API-->>Pet: id = 42, is_read = true
  H5->>API: 查询聊天未读
  API-->>H5: count = 1，剩余 41
  Note over H5: 用户看到第一条正文
  H5->>API: 提交 41 的单条回执
  Pet->>API: GET /chat/unread
  API-->>Pet: count = 0
```

- **判断用户看到哪条。** 只对处于未读状态、正文实际可见的气泡提交回执。宠物端可参考 H5 的可见判定：聊天在前台且有焦点，短消息完整显示，长消息至少连续两行完整显示，持续 650 毫秒。切页、失焦或遮挡会中断计时。该判定由展示端执行。
- **更新角标。** 回执成功后重新查询 `GET /chat/unread`，显示最新 `data.count`。离开期间有新回复或另一端已读时，重新查询也能得到当前总数。只看到第一条就退出，第二条仍未读。
- **处理回执超时。** 用同一账号、同一 `source` 和 `id` 重试，重复确认不会多扣。再次打开缓存页面时，用状态接口核对具体气泡。

主动消息的 `trigger_type` 取值（展示用，不影响接口逻辑）：`P0` 情绪跟进、`P1` 长期沉默、`P2` 日常问候、`P3` 凌晨在线、`P4` 轻度沉默、`FUTURE`（对话中约定的 Future 槽到期）等。

---

## 7. 接口说明

以下 `{base}` 表示 `{Base URL}/api/open/v1`。

### 7.1 POST `{base}/chat/send`

**发送用户消息，同步返回 AI 回复。**

**请求 Body：**

```json
{
  "content": "你好呀"
}
```

| 字段 | 类型 | 约束 |
|------|------|------|
| `content` | string | 必填，1–2000 字（去首尾空格后非空） |

**成功 `code = 0` 时 `data`：**

```json
{
  "messages": [
    { "id": 41, "sort_seq": "106", "type": "text", "content": "嗨，我在呢。", "is_read": false },
    { "id": 42, "sort_seq": "107", "type": "text", "content": "你今天过得怎么样？", "is_read": false }
  ],
  "emotion": {
    "label": "开心",
    "confidence": 0.9
  },
  "round_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 说明 |
|------|------|
| `messages` | 每个元素是一条已保存的普通回复，按数组顺序展示。`type` 为 `text`，`content` 为正文。 |
| `messages[].id`、`sort_seq` | `id` 是整数，与 `source=assistant` 组合标识这条气泡。`sort_seq` 是十进制字符串，用于排序。 |
| `messages[].is_read` | 布尔值。新回复初始为 `false`。在请求身份保留期内，用原幂等键重放同一成功请求，返回原气泡 ID 和当前已读状态。 |
| `emotion.label` | 林小梦当前情绪标签，如：开心、担心、想念、平静 |
| `emotion.confidence` | 0–1 置信度 |
| `round_id` | 本轮对话 UUID。时间线不返回此字段，逐条回执使用各气泡自己的 `id` |

发送或重发丢失响应时，可用原请求标识[查询提交状态](../contract/current/openapi/api.md#submission-status)，`dedupe_expires_at` 是该身份的保留截止时间。状态为 `expired` 时，请刷新时间线核对结果。过期标识清理后，再用同一个键提交也可能生成新回复并增加未读。逐条已读回执始终按气泡的 `source` 和 `id` 重试。

---

### 7.2 POST `{base}/chat/resend`

**对最近一次可重发的失败窗口发起重试。**

- **无请求 Body**（空 POST 即可，`Content-Type: application/json` 可保留）。  
- 成功 `data` 结构与 `send` 相同。  
- 无可重发失败句时返回 **10107**；重发过于频繁返回 **10105**（2 次/分钟量级，与线上一致）。

---

### 7.3 GET `{base}/chat/timeline`

**拉取对话 + 主动消息统一时间线（分页）。**

**Query：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `cursor` | int，可选 | 上一页返回的 `next_cursor`（`sort_seq`） |
| `limit` | int，可选 | 1–50，默认 20 |

**成功 `data` 示例。** 沿用上面的两条回复，宠物端已确认 42。查询 `GET /chat/timeline?limit=1` 返回最新一条。

```json
{
  "items": [{
    "source": "assistant", "id": 42, "sort_seq": 107,
    "content": "你今天过得怎么样？", "created_at": "2026-11-28T10:00:00",
    "emotion_label": "开心", "delivery_status": null, "skipped_in_prompt": null,
    "is_read": true, "trigger_type": null
  }],
  "next_cursor": 107,
  "has_more": true
}
```

每页 `items` 按旧到新排列。向更早历史翻页时，传入本页 `next_cursor`，把返回的记录放在已有列表前面。查询时间线保留所有气泡的阅读状态。

<a id="partner-chat-unread"></a>
#### 7.3.1 聊天总未读、单条回执与状态核对

下面的示例与 §6.4 使用同一组消息。请求均携带当前账号的 Bearer Key，成功响应取 `data`。

**① 查总未读。** `GET {base}/chat/unread`。收到两条回复、尚未看到任何一条时，结果如下。

```json
{
  "count": 2,
  "first_unread":  { "source": "assistant", "id": 41, "sort_seq": "106" },
  "latest_unread": { "source": "assistant", "id": 42, "sort_seq": "107" }
}
```

`count` 是普通回复和主动消息的未读气泡总数。两个锚点分别定位最早、最新的未读气泡，`sort_seq` 是十进制字符串。只剩一条时两个锚点指向同一条。锚点之间可以包含已读消息。

**② 只确认看到的那条。** `POST {base}/chat/messages/{source}/{id}/read`，无请求体。普通回复用 `assistant`，主动消息用 `agent`。例如只看到 42 时，向 `/chat/messages/assistant/42/read` 提交一次，得到：

```json
{ "source": "assistant", "id": 42, "is_read": true }
```

重复发送同一回执仍成功。回执响应只包含该条消息的状态。重新查总数，两端此时都得到 `count=1`，两个锚点都指向 41。

**③ 核对已加载的气泡。** `GET {base}/chat/unread/status?assistant_id=41&assistant_id=42` 仅返回请求范围内、本账号仍未读的气泡。上一步之后，结果如下。

```json
{ "unread": [{ "source": "assistant", "id": 41 }] }
```

查询普通回复传 `assistant_id`，主动消息传 `agent_id`。两个参数均可重复、可混用，合计传 1–100 个 ID，每个取值为 1–2147483647。未命中返回 `{"unread":[]}`。查询保留原阅读状态，不能用来探测某 ID 是否存在或属于哪个账号。

**④ 在 H5 读完 41 后，宠物端再次查总未读。** 若期间没有其他新消息，返回：

```json
{ "count": 0, "first_unread": null, "latest_unread": null }
```

回执指定的消息在当前账号和来源下找不到时，返回 HTTP 200、业务码 `10111`。不支持的 `source`（如 `user`）、状态查询漏传 ID 或超过数量与取值范围时，返回 HTTP 422。[可执行的 curl 示例](#partner-chat-curl)

---

### 7.4 GET `{base}/agent/messages`

**未读主动消息列表（已读的不返回）。**

**成功 `data`：** 数组，元素示例：

```json
{
  "id": 1001,
  "trigger_type": "P4",
  "content": "好久没聊了，有点想你。",
  "action_score": 7,
  "created_at": "2026-06-04T12:00:00"
}
```

---

### 7.5 GET `{base}/agent/unread-count`

**仅统计主动消息。** 适用于有独立「主动消息」入口的应用。聊天总角标直接使用 `GET /chat/unread` 的 `data.count`。

**成功 `data`：**

```json
{
  "count": 2
}
```

---

### 7.6 POST `{base}/agent/messages/{message_id}/read`

**将一条主动消息标为已读。**

- 路径参数 `message_id` 为整数，来自 `agent/messages` 或 timeline 中 `source=agent` 的 `id`。  
- 成功 `code = 0`；消息不存在或不属于当前用户：**10400**，`message` 为「主动消息不存在」。  
- 重复确认已读的主动消息返回成功。此处和统一聊天回执更新同一条主动消息，调用其中一个即可。

---

<a id="partner-diary"></a>
### 7.7 日记

| 请求（相对 `{base}`） | 参数与成功结果 |
|---|---|
| `GET /diary/list` | `page` 从 1 开始，`page_size` 默认 20，可取 1–50。返回 `items, total, page, page_size`。每篇自带全文。仅当账号总篇数为 0 时，另有 `empty_state: {kind, message}`，`kind` 为 `new` 或 `active`，可直接展示 `message`。 |
| `POST /diary/{diary_id}/read` | 用 `items[].id`，无请求体。正文实际展示后调用，成功返回 `code=0, data=null`；重复上报成功。 |

单篇 `items[]` 示例（示意数据）：

```json
{
  "id": 42, "content": "雨停了。\n窗台上的叶子还挂着水。",
  "created_at": "2026-11-13T08:10:00", "covers_beijing_date": "2026-11-12",
  "relationship_level_at_creation": 2, "is_read": false
}
```

打开日记时先展示第一页首篇，保留正文换行。列表按创建时间倒序，同一时间按 ID 倒序。七日栏与月历按 `covers_beijing_date` 归日；旧记录该值为 `null` 时用 `created_at` 的本地日期。同日多篇时选中日期先展示第一篇，前后翻篇可看其余记录。翻页按 ID 去重，直到已取完 `total` 或收到空页；日历中尚未加载的日期要先补分页，再判断当天是否有日记。预取与浏览月历不会标记正文已读。

<a id="partner-feed"></a>
### 7.8 朋友圈

首页展示红点时取角标；用户打开朋友圈时再调用进入接口，加载页头和首屏。列表里的帖子已经包含正文、配图和评论，点开帖子或发评后只需刷新该帖详情。

| 请求（相对 `{base}`） | 参数与成功结果 |
|---|---|
| `GET /feed/badge` | `has_new, new_post_count, unread_reply_count`。从未进入过朋友圈的账号可能有新帖但计数为 0；显示新帖提示用 `has_new`。 |
| `POST /feed/enter` | 无请求体。更新进入时间，返回最近未读回复的 `anchor_post_id, anchor_comment_id`，两者为空时正常展示首屏。 |
| `GET /feed/config/header` | `header_bg_url, header_avatar_url, display_nickname, signature, home_city`。封面和头像为绝对地址。 |
| `GET /feed/list` | `size` 默认 20，可取 1–50。返回 `posts, next_cursor`。首页省略 `cursor`，下一页把 `next_cursor` 原样作为查询参数传回并做 URL 编码，值为 `null` 时结束。 |
| `GET /feed/posts/{post_id}` | 返回一个与列表元素结构相同的帖子。 |
| `POST /feed/{post_id}/like`、`DELETE /feed/{post_id}/like` | 无请求体。分别设为已点赞、未点赞，使用返回的 `user_liked, display_likes` 更新界面。重复发送相同操作不会重复计数。 |
| `POST /feed/{post_id}/comments` | JSON 传 `content`（1–200 字，须有非空白内容）。普通评论可省略 `reply_to_lxm`；点小梦的回复再回她时传 `true`。返回 `comment_id, created_at, gen_status:"pending", reply_to_lxm`。 |
| `POST /feed/{post_id}/read` | 无请求体。用户实际阅读帖子后上报，成功返回 `data={}`，可触发阅读感知。 |
| `POST /feed/comments/{comment_id}/read` | 无请求体。用户读到小梦的回复后，用原评论的 `id` 上报。返回 `affected`；首次标记为 1，已经读过或回复尚未生成均为 0。 |
| `GET /feed/events` | 保持带 Bearer 头的 SSE 连接。收到例如 `data: {"type":"feed_new","delta":1}` 时刷新新帖提示，忽略 `: heartbeat`。断线期间的事件不补发，恢复时重新拉列表和角标。 |

**渲染帖子。** 用 `id` 定位帖子，`content_text, hashtags, scheduled_publish_time, emotion, city` 展示动态，`image_urls[]` 是按展示顺序排列的完整图片地址。点赞按钮取 `user_liked`，展示数取 `display_likes` 和 `display_comments`。后者是展示用评论数，与当前账号可见的 `comments[]` 长度可能不同。

**读取回复。** 每条 `comments[]` 包含 `id, content, reply_to_lxm, lxm_reply, lxm_reply_at, lxm_reply_read_at`。发评成功只代表评论已收录；刷新单帖后按评论 ID 找到原评论，`lxm_reply` 有值时展示回复，`lxm_reply_read_at` 为空表示该回复未读。朋友圈 SSE 只通知新帖。

**重试评论。** 每次新的发评动作可生成一个 `Idempotency-Key`（1–128 个非空格的可见 ASCII 字符，例如 UUID）。请求超时时，同账号用原键、原帖子、原正文和原回复标记重试，可取回原创建回执。同键改内容会返回 10507。未带键的请求丢失回执时，先刷新详情核对；同账号同帖的新评论间隔至少 30 秒。

<a id="partner-bgm"></a>
### 7.9 BGM 曲库与播放

`GET {base}/bgm/catalog` 使用现有 Bearer Key，无需请求体或查询参数。成功时返回完整曲库，曲目顺序和默认曲与 H5 相同。曲名允许重复，选曲时使用曲目 ID。

| 成功响应中的字段 | 客户端用法 |
|---|---|
| `data.catalog_version` | 整数，标识本次曲库快照的版本。 |
| `data.default_track_id`、`data.tracks[]` | 按数组顺序显示曲目，在数组中按 ID 找到默认曲。空曲库返回 `tracks: []` 和 `default_track_id: null`，可显示“暂无背景音乐”。 |
| `id`、`name`、`duration_seconds` | 分别是曲目标识、展示名和以秒计的时长。 |
| `audio_url`、`media_version` | 将 HTTPS 地址原样交给播放器。缓存音频时以曲目 ID 和音频版本区分资源。 |
| `cover_url`、`cover_version` | 封面单独更新。按 `cover_url` 判断能否显示，值为 `null` 时显示占位图。 |

用户选择音乐后由客户端控制播放、暂停、切歌、音量与进度。请求曲库时携带 Key，读取音频和封面时直接访问返回的 URL，媒体请求不附加 Bearer 或 Cookie。桌面播放器可以用 HTTP Range 分段读取或跳转播放位置。

沿用附录中的 `BASE` 和 `KEY`。以下示例使用 `jq` 找到默认曲并读取开头 64 字节，正常返回 HTTP 206。若曲库暂不可用，接口返回 HTTP 503、业务码 `20207` 和 `Retry-After: 2`。此时保留已有列表，按响应头稍后重试。

```bash
if catalog=$(curl -fsS "$BASE/api/open/v1/bgm/catalog" -H "Authorization: Bearer $KEY"); then
  audio_url=$(jq -r '.data as $d | $d.tracks[] | select(.id == $d.default_track_id) | .audio_url' <<< "$catalog")
  if [ -n "$audio_url" ]; then
    curl -fsS --range 0-63 --output /dev/null --write-out 'HTTP %{http_code}\n' "$audio_url"
  fi
fi
```

<a id="partner-memory"></a>
### 7.10 记忆星云（记忆星球）

`GET {base}/memory/list` 返回当前 Key 所属账号在 H5「记忆星云」中可见的长期记忆。每条记录都带有完整正文，用户点开星体时可直接显示。记忆由对话流程整理，外部客户端可以分页浏览。

沿用附录中的 `BASE` 与 `KEY`。首次请求从第 1 页开始，每页默认 20 条，可选 1–50 条。

```bash
curl -fsS "$BASE/api/open/v1/memory/list?page=1&page_size=50" \
  -H "Authorization: Bearer $KEY"
```

以下为示意响应。

```json
{
  "code": 0,
  "data": {
    "total": 1, "page": 1, "page_size": 50,
    "list": [{
      "doc_id": "mem_example",
      "key": "",
      "value": "喜欢在下雨时听音乐。",
      "content": "喜欢在下雨时听音乐。"
    }]
  },
  "message": "success"
}
```

| 字段 | 客户端用法 |
|---|---|
| `total, page, page_size, list` | `total` 是当前可浏览条数，最多 500。按页码递增加载，按 `doc_id` 去重。取足 `total` 或收到空页即结束。无记忆时返回 `total=0, list=[]`，越过末页时仍返回当前总数。 |
| `doc_id` | 星体的字符串标识，用于选中、去重和切换详情。列表按此字段升序返回。 |
| `key` | 记忆分类键，例如 `偏好-饮品-茶`。按 H5 的展示规则取第一段作为分类依据，旧记忆的空键归到“其他”。 |
| `value, content` | `value` 是展示正文，`content` 是原文。优先展示 `value`，为空时取 `content`。旧记忆可以只有原文。星体位置、连线和前后切换由客户端根据已加载列表生成。 |

无效 Key 返回 HTTP 401，页码或每页条数越界返回 HTTP 422。记忆来源暂不可读时返回 HTTP 503、业务码 `20129` 和 `data=null`。此时保留已加载的星体，提示稍后重试；只有成功且 `total=0` 时展示空星云。

## 8. 时间线字段与状态

### 8.1 `items[]` 单条结构

时间线合并 **用户/AI 对话** 与 **主动消息**，用 `source` 区分：

| `source` | 含义 | 典型字段 |
|----------|------|----------|
| `user` | 用户发送 | `content`, `delivery_status`, `emotion_label` |
| `assistant` | 林小梦回复 | `content`, `emotion_label`, `is_read`；`delivery_status` 为 `null` |
| `agent` | 主动消息 | `content`, `is_read`, `trigger_type` |

**公共字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `sort_seq` | int | 全局排序序号，分页游标 |
| `id` | int | 来源内的记录 ID。用 `(source, id)` 定位气泡。 |
| `content` | string | 文本内容 |
| `created_at` | string | ISO8601 时间 |
| `emotion_label` | string \| null | 情绪标签 |
| `delivery_status` | string \| null | 仅 **user** 行有意义，见下表 |
| `skipped_in_prompt` | bool \| null | user 行：是否未进入本轮 Prompt |
| `is_read` | bool \| null | assistant 和 agent 行：`false` 未读、`true` 已读。user 行为 `null` |
| `trigger_type` | string \| null | agent 行：触发类型 P0–P4、`FUTURE` 等 |

发送结果中的每个 `messages[].id` 对应时间线上 `source=assistant` 且 `id` 相同的那一条。时间线的 `sort_seq` 为 JSON 整数，发送结果与未读锚点中的同名字段为十进制字符串。

### 8.2 `delivery_status`（user 行）

| 值 | 含义 | 宠物端 UI 建议 |
|----|------|----------------|
| `pending_llm` | 等待 AI 生成 | 发送中 / loading |
| `delivered` | 已成功回复 | 正常 |
| `failed_timeout` | 超时 | 显示重试（可调 `resend`） |
| `failed_error` | 服务错误 | 显示重试（可调 `resend`） |
| `failed_blocked` | AI 输出内容安全拦截（用户输入已在入队前单独拦截） | **不要** 走 resend；重新 `send` 新消息 |

**assistant / agent 行** 的 `delivery_status`、`skipped_in_prompt` 键存在但值为 **`null`**。

### 8.3 多气泡与 timeline 对齐

- `send` / `resend` 成功时，先按 `messages[]` 顺序显示，再用 `(assistant, id)` 与时间线合并。即使两条正文相同，也各有自己的 `id` 和阅读状态。
- 主动消息使用 `(agent, id)`。两个来源的数字 ID 可能相同，列表去重、缓存和回执都须保留来源。
- 同步接口失败或返回 **10108** 时，重新拉时间线。使用缓存恢复界面时，可按已加载气泡查询当前未读状态。

---

## 9. 错误码与处理

业务失败时 **HTTP 状态码仍为 200**，请判断 `code` 字段。

| code | 含义 | 建议处理 |
|------|------|----------|
| **0** | 成功 | 解析 `data` |
| **10100** | 内容为空 | 本地校验，提示用户输入 |
| **10101** | 内容安全不通过（**含**用户输入入队前拦截、**或** AI 输出拦截后同步失败） | **展示 `message`**；用户输入场景改措辞重发；AI 输出场景 timeline 可能为 `failed_blocked`，**重新 send** |
| **10102** | LLM 失败/超时 | **展示 `message`**，拉 timeline 看是否 `failed_timeout`/`failed_error`，可 resend |
| **10104** | 待处理消息过多（未闭环 ≥5 且无叹号） | 展示 `message`，等待后刷新时间线核对待处理消息 |
| **10105** | 重发过于频繁 | **展示 `message`**，稍后重试 |
| **10107** | 当前无可重发 | **展示 `message`**，检查 timeline |
| **10108** | 等待中被新消息取代 | **展示 `message`**，**必须** `GET timeline` 对账 |
| **10111** | 统一聊天回执找不到当前账号、指定来源的消息 | 刷新时间线，核对 `source` 和 `id` |
| **10400** | 专用主动消息回执找不到该消息 | **展示 `message`** |
| **10001** | 朋友圈翻页游标无效 | 清除游标，从第一页重新加载 |
| **10300** | 日记不存在或不属于当前账号 | 刷新日记列表 |
| **10500** | 帖子不可见 | 刷新朋友圈列表，移除失效帖子 |
| **10502 / 10503 / 10505** | 评论为空、超过 200 字或未通过内容安全检查 | 保留草稿，按 `message` 提示用户修改 |
| **10504** | 同账号同帖 30 秒内再次发评 | 保留草稿，等频控窗口结束再提交 |
| **10506** | 评论对当前账号不可用 | 刷新帖子详情 |
| **10507** | 评论请求键已用于不同请求 | 重试原动作时恢复原参数；用户确认发送一条新评论时再生成新键 |

完整中文 `message` 以服务端返回为准，常见默认值包括：

- 10101：`消息包含不适当内容，请修改后重试`  
- 10104：`待处理消息过多，请先等待或处理失败提示`  
- 10108：`回复已被新消息取代，请拉取时间线查看后再操作`  

---

## 10. 安全要求

1. **传输**：生产当前为 **HTTP**，Bearer 中的 Key 可能被窃听；请仅在受信网络使用，或待 HTTPS 上线后更新 Base URL。  
2. **存储**：API Key 存操作系统凭据库或加密配置，**不要**写进日志、崩溃上报、截图。  
3. **禁止**在浏览器网页中直连 Open API（易泄露 Key）。  
4. **禁止**把 Key 提交到公开仓库。  
5. 客户端日志勿打印完整 `Authorization` 头。

---

## 11. 联调与验收

### 11.1 联调物资（向运营索取）

- [ ] 测试环境 **Base URL**（一对配置）  
- [ ] 测试环境 **API Key**（对应该 Base URL 下签发的用户）  
- [ ] 确认该用户在后台 **未禁用**  

生产上线前另行索取生产 Base URL（`http://cllxm.com`）与生产 Key。

### 11.2 建议验收用例

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 配置 Base URL + Key，拉 timeline | `code=0`，`items` 可渲染 |
| 2 | send 正常短句 | `code=0`，`messages` 非空，`emotion` 有 `label` |
| 3 | send：`""` / 仅空格 / 超长 | `""` → **422**；仅空格经校验后 → **10100**；超长 → **422**（建议本地先校验 1–2000 字） |
| 4 | 故意触发敏感词（若可测） | `code=10101`，展示 `message` |
| 5 | timeline 中 `failed_timeout` 后 resend | `code=0` 或合理失败码 |
| 6 | `failed_blocked` 行点 resend | `code=10107`，须改内容后 send |
| 7 | 快速连发两条 send | 至少一条可能 10108；timeline 最终一致 |
| 8 | 用 `/agent/messages` 获取并确认一条主动消息 | `/agent/unread-count` 和聊天总未读均减少一条，普通回复状态保留 |
| 9 | 错误 Key | HTTP 401 |
| 10 | 用 Key 调 `/api/chat/send` | HTTP 401（路径隔离） |
| 11 | 用升级前已签发的有效 Key 拉日记，再展示一篇并上报已读 | 可直接读取；刷新列表后该篇 `is_read=true` |
| 12 | 拉朋友圈、打开配图、以列表中的 ID 刷新单帖 | 图片可打开；正文、本人评论、小梦回复及点赞状态能对应到同一帖 |
| 13 | 在联调账号发评，使用原键原内容重试，再刷新该帖 | 两次回执的 `comment_id` 一致，列表只有一条新评论；回复生成后在该条评论中可见 |
| 14 | 用已有 Key 取 BGM 曲库，选中默认曲，加载音频和封面 | 已发布曲目与 H5 排序一致，音频可播放。封面为空时展示占位图。 |
| 15 | 用已有 Key 分页加载记忆并点开星体，再用另一个联调账号重读 | 各自只能读取本人记忆；正文可直接展示，超过末页返回空数组。 |
| 16 | 初始总未读为 0，H5 发完即退回首页。等待两条回复，只看第一条后退出 | 总数先为 2，再为 1。宠物端核对两条 ID，只返回第二条未读。 |
| 17 | 初始总未读为 0，通过 Open 发起对话并接收两条回复，只在宠物端确认第二条，再在 H5 读第一条 | 收到回复后为 2，确认第二条后两端为 1。重复确认第二条仍为 1。H5 确认第一条后，宠物端再查为 0。 |
| 18 | 同时有一条未读普通回复和一条未读主动消息，后台查询总数、拉时间线、核对状态，再只确认主动消息 | 所有查询均保留两条未读。最后只剩普通回复，即使两条的数字 ID 碰巧相同也分别计数。 |

---

## 12. 常见问题

**Q：宠物需要帮用户注册林小梦账号吗？**  
A：需要先有 H5 用户账号，再由运营绑定签发 Key；Open API **不提供注册接口**。

**Q：能否一个 Key 给多台设备？**  
A：技术上可以共用同一 Key，但多设备同时发消息会共享同一聊天队列与 10104/10108 规则，**建议一宠一端一 Key**（由运营为每端用户各建账号与 Key）。

**Q：send 很慢是否正常？**  
A：`send` 同步等待本轮生成。客户端按 §5.2 配置超时；等待期间用户离开聊天，成功保存的回复仍会计入未读。

**Q：已有聊天 Key 可以看日记和朋友圈吗？**
A：可以。在已部署这版接口的同一环境，沿用原 Base URL 和有效 Key，请求 `/api/open/v1/diary/list` 和 `/api/open/v1/feed/list` 即可。日记中的 `relationship_level_at_creation` 表示撰写时的等级。

**Q：重新生成 Key 后旧客户端会怎样？**  
A：旧 Key 立即 401，须让用户更新配置或联系运营重新粘贴。

**Q：timeline 里一直 `pending_llm` 怎么办？**  
A：先用原请求标识查询[提交状态](../contract/current/openapi/api.md#submission-status)，再刷新时间线。长时间仍未结束时联系运营，避免重复发送同一条用户消息。

---

## 13. 附录：curl 示例

以下命令适用于运行本地 Docker 的电脑。先将本地环境已签发的 API Key 放入环境变量 `KEY`。在其他环境联调时换成对应的根地址和 Key。

```bash
export BASE="http://127.0.0.1:8000"
```

**发送消息：**

```bash
curl -sS -X POST "${BASE}/api/open/v1/chat/send" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"content":"你好"}' \
  --max-time 210
```

**时间线：**

```bash
curl -sS "${BASE}/api/open/v1/chat/timeline?limit=20" \
  -H "Authorization: Bearer ${KEY}"
```

<a id="partner-chat-curl"></a>
**查聊天总角标。** 以下步骤使用 §6.4 的场景。在联调账号收到两条普通回复后执行。

```bash
curl -sS "$BASE/api/open/v1/chat/unread" -H "Authorization: Bearer $KEY"
```

**只确认实际看到的第二条。** 从 `send` 的 `data.messages[]` 或时间线 `source=assistant` 的行取真实 `id`，把第一条的 ID 赋给 `FIRST_ID`，第二条的 ID 赋给 `SEEN_ID`。先查询两条的状态，此步不会标为已读。

```bash
curl -sSG "$BASE/api/open/v1/chat/unread/status" -H "Authorization: Bearer $KEY" \
  --data-urlencode "assistant_id=${FIRST_ID:?请设置第一条回复的 ID}" \
  --data-urlencode "assistant_id=${SEEN_ID:?请设置实际看到的第二条回复的 ID}"
```

用户看到第二条后执行下面的空 POST，再核对状态和总数。假设期间无其他读写，状态查询只返回第一条，总数为 1。主动消息的回执同理，把路径中的 `assistant` 改成 `agent`，使用这条主动消息自己的 ID；核对状态时传 `agent_id`。

```bash
curl -sS -X POST "$BASE/api/open/v1/chat/messages/assistant/${SEEN_ID:?请设置实际看到的第二条回复的 ID}/read" \
  -H "Authorization: Bearer $KEY"
curl -sSG "$BASE/api/open/v1/chat/unread/status" -H "Authorization: Bearer $KEY" \
  --data-urlencode "assistant_id=${FIRST_ID:?请设置第一条回复的 ID}" \
  --data-urlencode "assistant_id=${SEEN_ID:?请设置实际看到的第二条回复的 ID}"
curl -sS "$BASE/api/open/v1/chat/unread" -H "Authorization: Bearer $KEY"
```

**重发（无 Body）：**

```bash
curl -sS -X POST "${BASE}/api/open/v1/chat/resend" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  --max-time 210
```

---

**读取日记、朋友圈和下一页。** 将 `CURSOR` 设为本次列表返回的非空 `data.next_cursor` 后再执行第三条。

```bash
curl -sS "$BASE/api/open/v1/diary/list?page=1&page_size=20" -H "Authorization: Bearer $KEY"
curl -sS "$BASE/api/open/v1/feed/list?size=20" -H "Authorization: Bearer $KEY"
curl -sSG "$BASE/api/open/v1/feed/list" -H "Authorization: Bearer $KEY" \
  --data-urlencode "cursor=$CURSOR" --data-urlencode "size=20"
```

**发评并查看回复。** 将 `POST_ID` 设为列表返回的帖子 ID，`REQUEST_ID` 设为本次发评生成的 UUID。第一条命令会实际新增评论；之后可单独重复第二条查看小梦的回复。

```bash
curl -sS "$BASE/api/open/v1/feed/$POST_ID/comments" \
  -H "Authorization: Bearer $KEY" -H "Idempotency-Key: $REQUEST_ID" \
  -H 'Content-Type: application/json' -d '{"content":"这张照片是在哪里拍的？"}'
curl -sS "$BASE/api/open/v1/feed/posts/$POST_ID" -H "Authorization: Bearer $KEY"
```

## 文档变更

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.5 | 2026-11-28 | 增加 H5 与宠物端共享聊天未读的升级说明、总角标、批量状态查询和逐条回执。同步流程图、气泡字段、curl 示例及跨端验收用例。 |
| v1.4 | 2026-11-14 | 新增记忆星云只读接口、分页示例、旧记忆展示和读取失败处理。 |
| v1.3 | 2026-11-14 | 新增 BGM 曲库、默认曲选择、媒体读取示例及空曲库和服务异常的处理。 |
| v1.2 | 2026-11-13 | 增加日记、朋友圈接入与联调用例，说明既有 Key、分页、已读、图片、评论重试和 SSE。 |
| v1.1 | 2026-06-04 | 对照代码复核：修正 timeline 无 `round_id`、内容安全双路径、Open timeline 不触发队列恢复、10104 后台补跑、验收用例与 `FUTURE` 触发类型 |
| v1.0 | 2026-06-04 | 首版：宠物端接入说明 |

参见[集成摘要](../design/openapi/open-api-v1.md)与[服务端 Open API 契约](../contract/current/openapi/api.md)。
