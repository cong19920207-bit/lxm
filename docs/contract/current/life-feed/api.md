# Life Feed Api

- 文档 ID：`contract-life-feed-api`
- 权威状态：`canonical`
- 功能范围：`life-feed`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-032`, `TD-033`, `TD-034`, `TD-035`, `TD-036`, `TD-037`
- 最近同步：`2026-08-13`（未登录开放与登录弹窗：文首当前口径 + 保留 C-028 迁移原文）

> **当前口径（2026-08-13）**：`GET /api/feed/list` 与 `GET /api/feed/config/header` 为可选 Bearer。完全缺少 `Authorization` 头返回公共数据；有效 token 保留登录用户语义；头存在但无效均 HTTP `401`，不降级为匿名。匿名 list 必须省略 `user_liked` 和 `comments`；header 另含 `home_city`。其余 `/api/feed` 端点仍强鉴权。细则见「当前口径：Feed 可选鉴权与访客只读态」。下文「模块：H5 朋友圈 / 生活流」为 2026-07-19 迁移原文，其中“全部 JWT”和 list 必含用户字段已被当前口径取代。

### 模块：H5 朋友圈 / 生活流（`/api/feed`）

> 全部 JWT；响应 `{"code":0,"data":{},"message":"success"}`。路由：`backend/routers/feed.py`。  
> **与对话主链**：v1 **无** Feed/世界观注入 Prompt；感知 IM 与 P0–P4/Future **业务零耦合**，仅共用 `agent_message` + `sort_seq` + 未读角标 API。

#### GET /api/feed/list

- **Query**：`cursor`（可选，上一页最后一条 `scheduled_publish_time` ISO）、`size`（默认 20，上限 50）
- **过滤**：`scheduled_publish_time<=feed_now()` · `is_visible=1` · `generation_status='ready'` · 历史窗 `feed_history_visible_range`（相对 `feed_now()`）
- **响应 `data`**：`{ posts:[{ id, content_text, hashtags, image_urls, scheduled_publish_time, emotion, city, display_likes, user_liked, display_comments, comments:[{ id, content, reply_to_lxm, lxm_reply, lxm_reply_at, lxm_reply_read_at }] }], next_cursor }`
- **约定**：评论**仅当前用户**私有；`scheduled_publish_time` 为北京墙钟 ISO（无 `Z`）；`city` 来自 `feed_post.city`（可空串）；`display_comments` 为计算字段；命中且 `actual_publish_time IS NULL` 懒惰写回
- **状态**：已实现

#### POST /api/feed/enter

- **写** `users.last_feed_entered_at=feed_now()`；`data`: `{ anchor_comment_id }`（最近未读 LXM 回复评论 ID，可 null）
- **状态**：已实现

#### GET /api/feed/badge

- **`data`**：`{ has_new, new_post_count, unread_reply_count }`
- **`has_new`**：存在已到点可见帖且（`scheduled_publish_time > last_feed_entered_at` 或从未进入）
- **`new_post_count`**：同上口径条数；**从未 enter** 时固定 `0`（此时若有可见帖仍可 `has_new=true`）
- **`unread_reply_count`**：当前用户未读 LXM 回复数
- **H5**：首页未读胶囊 / 底栏新动态；聊天角标 = `unread_reply_count + new_post_count`；有未读回复跳转 `?focus=unread_reply`
- **状态**：已实现

#### GET /api/feed/config/header

- **`data`**：`{ header_bg_url, header_avatar_url, signature, display_nickname }`（缺省回落 `life_feed_config`）
- **状态**：已实现

#### POST /api/feed/{post_id}/like

- 幂等点赞；真实新增时 `real_likes+1`；**先 commit 点赞事务再** `await like_aware_service.on_like_hook`（TB-LF-009）
- **响应**：`{ user_liked: true, display_likes }`
- **状态**：已实现

#### DELETE /api/feed/{post_id}/like

- 幂等取消；`real_likes-1`（`AND real_likes>0`）；**不撤回**已触发感知 IM
- **状态**：已实现

#### POST /api/feed/{post_id}/comments

- **Body**：`{ content, reply_to_lxm? }`（content 1~200；同帖 30s 频控；内容安全）
- **响应**：`{ comment_id, created_at, gen_status, reply_to_lxm }`
- **首次评论**：原子抢占 `has_ever_commented_feed` → `due_at=utcnow()+30s`；否则按关系档延迟（`comment_reply_delay_{stage}_{min|max}`，stage∈stranger/friend/intimate/**soulmate**）
- **`reply_to_lxm`**：仅展示标记；LLM-05 仍单条必回、无历史评论注入
- **状态**：已实现

#### GET /api/feed/events（SSE）

- **鉴权**：Query **`token`**（EventSource 无法带 Header）；`text/event-stream`；15s heartbeat 注释行
- **事件**：`{"type":"feed_new","delta":<本轮新帖数>}`；断线不补历史
- **状态**：已实现

#### POST /api/feed/comments/{comment_id}/read

- 写 `lxm_reply_read_at`（幂等）；越权 **`code=10506`** `ERR_FEED_COMMENT_FORBIDDEN`
- **状态**：已实现

#### POST /api/feed/{post_id}/read

- 校验可见+到点（`feed_now()`）后 `read_aware_service.on_feed_read`
- **状态**：已实现

#### 错误码（10500 段）

| code | 常量 | 说明 |
|------|------|------|
| 10500 | `ERR_FEED_POST_NOT_FOUND` | 不存在 / 未到点 / 隐藏 |
| 10501 | `ERR_FEED_POST_HIDDEN` | 管理员隐藏（预留） |
| 10502 | `ERR_COMMENT_EMPTY` | 评论为空 |
| 10503 | `ERR_COMMENT_TOO_LONG` | 超过 200 字 |
| 10504 | `ERR_COMMENT_RATE_LIMIT` | 30s 内重复评论 |
| 10506 | `ERR_FEED_COMMENT_FORBIDDEN` | 无权操作该评论 |
| — | `ERR_CONTENT_SAFETY_VIOLATION` | 内容安全（全局码） |

#### 感知 IM 服务约定（非独立 HTTP）

| 服务 | 要点 |
|------|------|
| `agent_aware_service` | 独立表排队；60s 轮询；落 `agent_message`（`action_score=0`）+ `allocate_sort_seq`；**不**走日上限 8 次 / 30min / 黑名单 / action_score |
| `like_aware_service.on_like_hook` | 同帖去重 → 特殊档（CAS 占位，入队失败回滚计数）→ 常规 30%；Prompt `prompt_p07`；节点 `llm_06` |
| `read_aware_service` | 多帖取最近一条；点赞后抑制；**用户级冷却**（`read_aware_user_cooldown_hours`，默认 6h，按入队 `created_at` 滚动，窗口内最多 1 条 `READ_AWARE`）；特殊档 `prompt_p14` / 常规 `prompt_p08~p11`；节点 `llm_07`；特殊档计数同 CAS+回滚 |
| `feed_sse_service` | 单进程内存注册表（v1 单实例） |

#### 定时任务（APScheduler · Asia/Shanghai）

| 触发 | 任务 | 说明 |
|------|------|------|
| 周日 23:00 / 23:30 | `weekly_outline_task` / `_retry` | LLM-01 |
| 每日 00:20 / 00:30 | `daily_scenes_task` / `_retry` | LLM-02 当日场景 |
| 每日 00:45 | `daily_her_universe_task` | LLM-03 |
| 每日 01:00 | `daily_feed_publish_task` | LIFE001 |
| 每 30s | `comment_reply_poll_task` | LLM-05（`due_at` UTC） |
| 每 60s | `agent_aware_poll_task` | 感知队列消费（`due_at` UTC） |
| 每 30s | `feed_new_broadcast_task` | SSE：`ready+visible+scheduled<=feed_now()+sse_broadcasted=0` |

手动：`python -m backend.tasks.life_feed_task <task_name>`

#### DeepSeek / Liblib / OSS / Redis（生活流）

| 项 | 约定 |
|----|------|
| DeepSeek 超时 | 单次默认 **45s**，retry=2，退避 2s/4s；与豆包超时互不影响 |
| Liblib payload | `templateUuid` + `generateParams`；selfie 含 `sourceImage`/`strength`/`resizedWidth`/`resizedHeight`；键见 `liblib_*` admin_config |
| 同帖多图 | `imgCount` 固定 1；`count≥2` 按 seq 构图变体 + 独立 seed；进行中任务并发 **1** |
| OSS 路径 | `lxm/posts/{post_id}/{seq:02d}.webp` |
| Redis | `liblib_stats:{YYYYMMDD}`；`active_config:{key}`；DeepSeek 复用 `llm_stats` / `llm_response_times` |

#### 关系档映射（代码常量）

`RELATIONSHIP_STAGE_MAP`：`0→stranger` · `1→friend` · `2→intimate` · `3→soulmate`（知己）。唯一来源：`backend/constants/life_feed_config.py`。

#### H5 `feed.html` 展示口径（摘要）

| 项 | 约定 |
|----|------|
| 路由 | `/pages/feed.html`；`?focus=unread_reply`；与 index/chat/memory 互通 |
| 时间 | `scheduled_publish_time` 按北京墙钟字符串解析 |
| 城市 | 左列弱化定位 + 城市名（无天气） |
| 评论角标 | `display_comments`；发评本地 +1 |
| 落款 | `reply_to_lxm=false`→「我：」；`true`→「我回复 林小梦：」；LXM「林小梦回复 我：」 |
| 话题 | 正文单 `#` 着色（兼容 `#话题#`）；不单独渲染 `hashtags[]` 行 |
| 进页 boot | `#feed-boot-loading`；渐进 alpha/blur；8s 硬超时；哨兵延后挂载（TB-LF-010） |
| SSE 提示条 | 「林小梦更新了 N 条动态」= **新帖** delta，**不是**评论回复未读 |
| 已读 | 回复曝光 0.6 上报；卡片停留 3s；观察器须 observe **自身** `.feed-item` |
| 列表 UI | 同日左列合并、meta 行左时间右展开、单图 4:3、评论无「正在回复」占位等（详见草案快照 / 《朋友圈页面展示逻辑规范》v1.6） |

---

### 当前口径：Feed 可选鉴权与访客只读态

> 本节取代上方迁移原文中的 H5 Feed 鉴权、list/header 响应和访客页面行为；其他 Life Feed 业务规则保持不变。

#### H5 用户端鉴权边界

| 方法与路径 | 鉴权 | 说明 |
|------|------|------|
| `GET /api/feed/list` | 可选 Bearer 用户 JWT | 完全缺少 `Authorization` 时返回公共 Feed；有效 token 保留登录用户语义 |
| `GET /api/feed/config/header` | 可选 Bearer 用户 JWT | 完全缺少 `Authorization` 时返回公共 Header；有效 token 返回同一公共配置 |
| `/api/feed` 其余端点 | 必填用户 JWT | 常规端点使用 Bearer，`events` 使用 Query `token`；包括 enter、badge、events、点赞、评论与已读接口，未登录不开放 |

- 可选鉴权只把“完全没有 `Authorization` 请求头”视为匿名。
- 只要 `Authorization` 请求头存在，空值、非 Bearer scheme、空 Bearer、伪造/过期 token 或封禁用户均返回 HTTP `401`，不降级为匿名。
- 该例外不改变共享鉴权约定，也不代表存在游客身份或游客会话。

#### GET /api/feed/list 条件响应

- **通用响应 `data`**：`{ posts:[{ id, content_text, hashtags, image_urls, scheduled_publish_time, emotion, city, display_likes, display_comments }], next_cursor }`
- **登录用户条件字段**：每条 post 另含 `user_liked` 与 `comments:[{ id, content, reply_to_lxm, lxm_reply, lxm_reply_at, lxm_reply_read_at }]`。
- **匿名条件字段**：post 必须完全省略 `user_liked` 和 `comments`，不得以 `false` 或空数组占位；服务层不查询按当前用户绑定的 `FeedLike` / `FeedComment`。
- **约定**：`display_comments` 为基础展示数加当前登录用户可见评论数，匿名时只含基础展示数；公共可见性、分页、时间/城市口径和 `actual_publish_time IS NULL` 懒惰写回保持不变。

#### GET /api/feed/config/header

- **`data`**：`{ header_bg_url, header_avatar_url, signature, display_nickname, home_city }`（缺省回落 `life_feed_config`）。

#### H5 `feed.html` 访客行为

| 项 | 约定 |
|----|------|
| 访客初始化 | 只请求公共 Header/List；不请求 enter/badge，不连接 SSE，不启动已读观察器，不处理私有 `focus` 定位 |
| 访客交互 | 点赞和评论必须在任何临时 UI 变更或写请求前触发共享登录弹窗 |
| 登录恢复 | 在当前页恢复 enter、badge、私有列表、SSE 与观察器各一次；不自动重放登录前的写操作 |
| `401` 降级 | 背景读取清 token 并恢复访客态；主动写操作回滚本次临时 UI 后弹登录窗；不得在 DOM 保留私有评论 |

---

### 模块：管理后台 · 生活流（`/api/admin`）

> 前缀 `/api/admin`；Admin JWT；写操作落 `operation_log`；配置类写操作走草稿三卡点。路由：`life_plan_mgmt` / `worldview_mgmt` / `feed_mgmt` / `feed_comment_mgmt` / `agent_aware_mgmt` / `life_config_mgmt`。

#### 生活计划（`life_plan_mgmt`）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/life-plan/outline` | 编辑 + ops 只读 | `week_start_date` 或 `plan_date` |
| POST/PUT/DELETE | `/life-plan/outline...` | 编辑 | categories∈词汇表；同日已存在报错 |
| POST | `/life-plan/outline/generate` | 编辑 | LLM-01 手动生成本周剩余日 |
| GET/PUT | `/life-plan/settings` | GET 含 ops；PUT 编辑 | home_city + life_ratio_*；PUT **仅草稿**，发布走 `/life-config/publish` |
| GET | `/life-plan/daily` | 编辑 + ops | 单日或 `start&end&page&size` |
| POST | `/life-plan/daily/{plan_date}/generate` | 编辑 | LLM-02 |
| POST/PUT/DELETE | `/life-plan/daily/{plan_date}/scenes...` | 编辑 | category 必须∈当日大纲；scenes&lt;2 不主动降级 gen_status |

#### 她的宇宙（`worldview_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/worldview/snapshots` | 仅 `plan_date`→数组；无参或 start/end→分页 `{total,page,size,list}`（默认近 14 天） |
| GET/PUT/DELETE | `/worldview/snapshots/{id}` | 删被 feed 引用时 WARN，可含 `referenced_by_post` |
| GET/POST/PUT/DELETE | `/worldview/events...` | `core_attitude` 四选项以前缀写入 `event_view` |

#### 朋友圈内容（`feed_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed/posts` | status∈all/visible/hidden/failed |
| GET/PUT | `/feed/posts/{id}` | 详情含 image_urls/hashtags/dedup_hash；**另含** base_comments/comment_multiplier/虚拟评论底 |
| DELETE | `/feed/posts/{id}` | **现状=下架**（`is_visible=0`）；真删未实现（TD-035）；UI 不提供删除钮 |
| PATCH | `/feed/posts/{id}/visibility` | `{is_visible:0/1}` |
| POST | `/feed/posts` | mode∈upload/ai_generate；管理员跳过 dedup/similarity；新帖随机写评论假数底 |
| GET/PUT | `/feed/config/auto-publish` | **不含** ops_admin；写入口在系统参数页 |

#### 评论管理（`feed_comment_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed/comments` | 筛 post_id/user_id/gen_status（含 hidden） |
| GET/PUT/DELETE | `/feed/comments/{id}` | DELETE=`is_hidden=1` |
| POST | `/feed/comments/{id}/regenerate` | LLM-05 补发，立即 queued |

#### 感知消息（`agent_aware_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/agent-aware` | queue LEFT JOIN agent_message |
| GET | `/agent-aware/{queue_id}` | 含 extra_context |
| POST | `/agent-aware/{queue_id}/retry` | 重试 failed |
| DELETE | `/agent-aware/{queue_id}` | 不撤回已送达 IM |
| POST | `/users/{user_id}/aware/reset` | **仅 super_admin**；特殊档计数归零 |

#### 生活流配置（`life_config_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/life-config?keys=` | 生效值+草稿；白名单校验；ops/tech 只读 |
| PUT | `/life-config/draft` | 保存草稿 |
| DELETE | `/life-config/draft/{config_key}` | 丢弃草稿 |
| POST | `/life-config/publish` | Body 增加可缺省的 `confirm_text`；进入发布前必须精确等于 `CONFIRM`，否则返回 `20021`；发布 + Redis + 5min 监控 |

`confirm_text` 不替代既有角色鉴权，也不是二次认证。现有 7 个前端发布入口均在共享 `showConfirmInput` 回调内显式发送 `confirm_text: "CONFIRM"`；取消或错误文本不会调用发布接口。草稿、生效版本、历史、回滚、Redis 发布流程与数据库结构保持不变。

**白名单**：`life_feed_config` 全部 `CONFIG_*` + life_ratio_* + 四档延迟键（`comment_reply_delay_*` / `like_regular_delay_*` / `read_regular_delay_*`，stage∈stranger/friend/intimate/**soulmate**）+ Prompt/图像映射 + DeepSeek 节点模型键。

#### GET /api/admin/stats/liblib

- Query `days`（1~30，默认 7）；读 Redis `liblib_stats:{YYYYMMDD}`
- 权限：super_admin / ai_trainer / tech_ops
- `data`：`{ days, daily:[{date,total,success,failed,points_used}], summary }`；Redis 异常可 `redis_error:true`

#### RBAC（生活流）

| 角色 | 权限 |
|------|------|
| super_admin | 全部读写；唯一可 reset 特殊档 |
| ai_trainer | 全部读写 |
| ops_admin | **只读**：朋友圈内容/评论/感知/生活计划/她的宇宙；可读 life-config；**不可** auto-publish |
| tech_ops | **只读**：系统参数 + Liblib 看板 |
| observer | 全部已批准生活流 GET 只读；不可草稿、发布、回滚、生成、增删改、显隐、重试或重置 |

---
