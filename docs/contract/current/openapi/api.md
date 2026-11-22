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

<a id="feed-diary-openapi"></a>
### 日记与朋友圈（2026-11-13）

以下路径相对 `/api/open/v1`。每个请求均使用 `Authorization: Bearer <现有 API Key>`。升级前已签发且仍有效的 Key 可直接使用，新旧 Key 使用相同规则。服务器从 Key 确定账号，与 H5 共享评论、点赞、进入时间、回复和日记已读。业务响应使用 `ApiResponse`，成功 `code=0`，业务拒绝为 HTTP 200 加非零 code。鉴权失败为 HTTP 401，结构校验失败为 HTTP 422。账号数据和事件流响应使用 `Cache-Control: private, no-store` 及 `Vary: Authorization`。

| 方法与路径 | 请求与结果 |
|---|---|
| `GET /feed/config/header` | 封面、头像、昵称、签名和主场城市。封面和头像为绝对 HTTP(S) 地址。 |
| `GET /feed/list` | `size` 默认 20、范围 1–50。首轮不传 `cursor`，后续原样回传上页 `next_cursor`，为 null 时结束。按北京发布时间及同时间的帖子 ID 倒序，非法游标返回 10001。返回 `{posts,next_cursor}`。 |
| `GET /feed/posts/{id}` | 返回一条与列表同形的帖子。包括 `id,content_text,hashtags,image_urls,scheduled_publish_time,emotion,city,display_likes,user_liked,display_comments,comments`。图片地址按原顺序返回，可直接打开。 |
| `POST /feed/{id}/like`、`DELETE /feed/{id}/like` | 点赞或撤销，返回 `{user_liked,display_likes}`。重复设为同一状态不会重复计数。 |
| `POST /feed/{id}/comments` | JSON `{content,reply_to_lxm?}`。内容 1–200 字，拒绝全空白，同账号同帖 30 秒频控，与 H5 共用内容安全检查。成功返回 `{comment_id,created_at,gen_status:"pending",reply_to_lxm}`。 |
| `GET /feed/badge`、`POST /feed/enter` | 后台刷新用 badge，返回 `{has_new,new_post_count,unread_reply_count}`。真正进入页面才调用 enter，更新进入时间并返回最近未读可见回复的位置 `{anchor_post_id,anchor_comment_id}`，没有时两者均为 null。 |
| `POST /feed/{id}/read`、`POST /feed/comments/{id}/read` | 分别上报已阅读的帖子和小梦的回复。前者进入既有阅读感知逻辑；后者返回 `{affected}`，未生成回复或重复上报均为 0。预取不发送这两种请求。 |
| `GET /feed/events` | 带认证头读取 `text/event-stream`，`feed_new` 事件给出 `delta`。长连接断开后先刷新列表和角标再重连。事件不补发，也不用于等待评论正文。 |
| `GET /diary/list` | `page` 从 1 开始，`page_size` 默认 20、范围 1–50。返回 `{items,total,page,page_size}`，每篇含 `id,content,created_at,covers_beijing_date,relationship_level_at_creation,is_read`。仅当 total=0 时附 `empty_state:{kind,message}`，kind 为 `new` 或 `active`。 |
| `POST /diary/{id}/read` | 实际展示该篇正文后显式上报，无请求体，成功时 data 为 null，重复提交成功。外账号或不存在返回 10300。 |

**发评论与读取回复。** 调用方可为一次发评提供 `Idempotency-Key`（1–128 个可见 ASCII 字符，不含空格）。同账号、同键、同帖、相同正文和回复标记，重放得到原创建回执，即使小梦已回复也不会创建新任务。更换帖子、正文或标记返回 10507。未提供请求键时，失去回执后先刷新详情核实。评论过快返回 10504。单帖查询中的 `comments[]` 仅有本账号未隐藏的评论，含 `id,content,reply_to_lxm,lxm_reply,lxm_reply_at,lxm_reply_read_at`。首次发评成功时回复可能为空，之后刷新单帖可见。点小梦的回复时，按同一帖再提交 `reply_to_lxm:true`。

**可见性与日期。** 仅到点、已就绪、可见且在历史窗口内的帖子可读取或互动，失效的帖子 ID 返回 10500。不可见或不属于本人的评论已读请求返回 10506。日记按创建时间、ID 倒序，同一日期可翻多篇；优先按 `covers_beijing_date` 归日，旧数据为 null 时客户端以 `created_at` 的本地日期回退。月历和七日栏从分页结果构造，完整加载前不能把缺失日期当作空日。正文展示规则和信纸索引见[日记页面契约](../diary/api.md)。消息角标复用 `GET /api/open/v1/agent/unread-count`，音乐使用 [Open BGM 曲库](#bgm-openapi)。

外部客户端示例（`LXM_BASE_URL` 为可访问的站点地址）：

```bash
curl "$LXM_BASE_URL/api/open/v1/diary/list?page=1&page_size=20" \
  -H "Authorization: Bearer $LXM_API_KEY"
curl "$LXM_BASE_URL/api/open/v1/feed/list?size=20" \
  -H "Authorization: Bearer $LXM_API_KEY"
curl "$LXM_BASE_URL/api/open/v1/feed/$POST_ID/comments" \
  -H "Authorization: Bearer $LXM_API_KEY" -H "Idempotency-Key: $REQUEST_ID" \
  -H "Content-Type: application/json" -d '{"content":"这张照片在哪儿拍的？"}'
```

发布时先运行数据库迁移 `v9z_feed_comment_idem_001`，再启用对应后端。账号与授权决定见[功能 PRD v1](../../../design/openapi/PRD-日记与朋友圈外部API-v1.md)，存储约定见[Open 数据契约](data.md)。

2026-11-13 本地 Docker 已完成上述迁移，后端镜像为 `lxm_for-backend:feed-diary-open-20261113`。通过 `http://127.0.0.1:8000` 使用升级前已签发的 Key，实测通过日记列表、已读日记重复上报，以及朋友圈页头、角标、列表翻页、单帖详情、评论与回复读取、已读回复重复上报、点赞与取消点赞的同状态重试和 SSE 心跳。抽取的帖子配图可匿名读取，空白评论返回 10502。此次实测未新增评论或触发新的阅读感知。

<a id="bgm-openapi"></a>
### BGM 曲库（2026-11-14）

`GET /api/open/v1/bgm/catalog` 沿用现有 Bearer API Key，无参数。每次请求先校验 Key 和账号状态；缺少或无效 Key、账号禁用均返回 HTTP 401。目录和媒体版本与 [H5 公开曲库](../bgm/api.md)共用，成功返回 `code=0` 和 `data={catalog_version,default_track_id,tracks}`。数组按发布顺序排列，每项含 `id,name,media_version,audio_url,duration_seconds,cover_url,cover_version`。播放器匿名读取 HTTPS 音频及可选封面。合法空目录仍为 HTTP 200，`default_track_id=null, tracks=[]`。目录服务暂不可用返回 HTTP 503、`code=20207, data=null` 和 `Retry-After: 2`。HTTP 200 和 503 响应均设置 `Cache-Control: private, no-store` 和 `Vary: Authorization`。

本地 Docker 已通过既有 Key 读取曲库并对照 H5 核对快照。两首已发布曲目的音频分段请求均返回 206，完整音频均可解码，封面可读取。调用示例见[第三方接入指南](../../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-bgm)。

<a id="memory-nebula-openapi"></a>
### 记忆星云（记忆星球）

`GET /api/open/v1/memory/list` 使用已签发的 Bearer API Key，只读该账号的 `user` 记忆。与 [H5 记忆星云](../memory-knowledge/api.md)共用记忆来源、归属校验和列表顺序。分页参数为 `page`（默认 1，最小 1）和 `page_size`（默认 20，1–50）。成功为 HTTP 200、`code=0`，`data={total,page,page_size,list}`。可浏览集合最多 500 条，按 `doc_id` 升序分页。单项只投影 `doc_id,key,value,content` 四个字符串。旧记录保留原文并允许空键。

空页返回 `list=[]`，保留当前集合的 `total`。缺少或无效 Key、账号禁用为 401，分页参数越界为 422。记忆源读取失败为 HTTP 503、`code=20129,data=null`。全站维护时沿用全局 503/20126。路由的成功响应和记忆源不可读响应均带 `Cache-Control: private, no-store`、`Vary: Authorization`。

2026-11-14 本地 Docker 已用升级前签发的 Key 验证实际分页、末页后空列表、四个展示字段及鉴权。接入和渲染示例见[第三方接入指南](../../../partner/林小梦-OpenAPI-宠物端接入指南.md#partner-memory)。
