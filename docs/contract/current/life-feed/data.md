# Life Feed Data

- 文档 ID：`contract-life-feed-data`
- 权威状态：`canonical`
- 功能范围：`life-feed`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-032`, `TD-033`, `TD-034`, `TD-035`, `TD-036`, `TD-037`

### 生活流新增表（8）

> 迁移：`v6a_step001_*`（建表+扩展）· `v6b_step019_026_*`（`agent_aware_queue.prompt_key/extra_context` + `feed_post.sse_broadcasted`）· `v6c_*`（`feed_comment.is_hidden`）· `v6d_*`（`reply_to_lxm`）· `v6e_*`（`base_comments`/`comment_multiplier`）。  
> 时区：**帖子到点 / `last_feed_entered_at` / 计划发布时间** = **Asia/Shanghai 墙钟**（`feed_now()`）；**评论 `due_at`/`created_at`、感知队列 `due_at`** = **UTC**（刻意分离）。

#### 表名：life_plan_outline

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| week_start_date | Date | 是 | 所属自然周周一 |
| plan_date | Date | 是 | 自然日（unique） |
| city | String(50) | 是 | 当天城市 |
| categories | String(200) | 是 | 内容分类，多个用 `\\n` 分隔；取值∈`categories_vocab` |
| gen_status | String(16) | 是 | `auto` / `manual` |
| created_at / updated_at | DateTime | 是 | |

#### 表名：life_plan

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| plan_date | Date | 是 | unique；关联大纲日 |
| scenes | JSON | 是 | 场景数组（scene_id/time_range/city/category/venue_type/description） |
| gen_status | String(16) | 是 | `generating` / `ready` / `failed` |
| created_at | DateTime | 是 | |

#### 表名：worldview_snapshot

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| plan_date | Date | 是 | |
| scene_id | String(64) | 是 | `scene_{plan_date}_{seq:03d}` |
| feeling_text | Text | 否 | 感受描述 |
| emotion_value | String(50) | 否 | 情绪；词表优先，可自由词 |
| focus_tag | String(100) | 否 | |
| worldview_trigger | String(100) | 否 | 写入事件库的话题标签 |
| gen_status | String(16) | 是 | `generating` / `ready` / `failed` |
| created_at / updated_at | DateTime | 是 | |

#### 表名：worldview_event

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| event_name | String(200) | 是 | unique 话题名 |
| event_view | Text | 是 | 固定看法；核心态度以 `[核心态度：X] ` 前缀嵌入（无独立列；X∈喜欢/排斥/矛盾/无感） |
| source_scene_id | String(64) | 否 | |
| created_at / updated_at | DateTime | 是 | |

#### 表名：feed_post

| 字段名 | 类型 | 必填 | 默认 | 说明 |
|--------|------|------|------|------|
| id | Integer PK | 是 | 自增 | |
| scene_id | String(64) | 否 | NULL | |
| scheduled_publish_time | DateTime | 是 | - | 北京墙钟 naive。公开读取限已到点、可见、生成就绪且在配置历史范围内的帖子；视频另须满足[已提交媒体条件](api.md#feed-public-post-v8)。 |
| actual_publish_time | DateTime | 否 | NULL | STEP-013 落 NULL；列表首次命中懒惰写 `feed_now()` |
| generation_status | String(16) | 是 | - | `generating` / `ready` / `failed` |
| content_text | Text | 是 | - | |
| hashtags | JSON | 否 | NULL | |
| image_urls | JSON | 否 | NULL | CDN WebP 数组 |
| image_reference_url | String(512) | 否 | NULL | 人物参考图说明用；基准图本地 `/static/images/avatar/character-ref/base.png` |
| image_type | String(16) | 否 | NULL | `selfie` / `daily` / `scenery` / `emotion` |
| emotion | String(20) | 是 | - | |
| city | String(50) | 是 | - | 场景城市 |
| season | String(20) | 是 | - | 春/夏/秋/冬 |
| base_likes / like_multiplier / real_likes | Integer | 是 | - | 展示点赞 = base×倍率+real |
| base_comments | Integer | 是 | 0 | 虚拟评论底；新帖随机；历史默认 0（不回填） |
| comment_multiplier | Integer | 是 | 1 | 仅放大 base_comments；历史默认 1 |
| is_visible | SmallInteger | 是 | 1 | 0=下架 / 1=展示 |
| dedup_hash | String(64) | 是 | - | `md5(venue_type\|category\|city)` |
| sse_broadcasted | SmallInteger | 是 | 0 | SSE 新帖广播去重 |
| created_at / updated_at | DateTime | 是 | | |

**计算字段（非 DB 列）**：`display_likes = base_likes × like_multiplier + real_likes`；`display_comments = base_comments × comment_multiplier + 当前用户可见评论条数`。

视频编辑自迁移 `v10e_feed_video_fields_001` 起在 `feed_video_edit` 保存 `hashtags`（JSON）和 `emotion`（最长 20 字）。升级时，已有草稿继承关联帖的话题和情绪。提交草稿与切换发布版本在同一事务写入帖子字段。新视频首次提交时生成两组互动展示基数和倍率，历史已提交帖沿用已有数值。

换片通过收件校验并写入草稿媒体选择时，更新 `last_edited_at`，草稿媒体从此次有效编辑起保留 7 天。旧草稿有接收记录时，同一草稿所选文件的 `received_at` 是到期计算的下限。重新处理任务或查看草稿均沿用原到期时间。

<a id="feed-video-storage"></a>

#### 置顶、草稿和公开视频版本

| 数据对象 | 所有权和写入时机 |
|---|---|
| `feed_post.media_kind / post_version` | 旧帖升级为 `image_text`、版本 1。普通编辑与视频提交按帖版本校验。点赞、评论和已读继续按原帖 ID 关联。 |
| `feed_pin / feed_pin_order` | 成员关联原帖，位置唯一。整组写入锁定单例版本并原子变更顺序。隐藏或移出时间窗仍保留后台成员和位置。 |
| `feed_video_edit / feed_video_selection / feed_publication` | 编辑保存基准帖版本、草稿版本和最后有效编辑时间。每份编辑选一个媒体版本与封面变体，公开指针只选本帖已明确提交的编辑。 |
| `feed_video_upload / feed_video_admission` | 记录接收操作、容量预留、实收完成时刻和全局序号。有效 MP4/MOV 不超过 200 MiB、180 秒，含边界。按接收完成顺序排队，全局同时处理一条。 |
| `feed_video_task / feed_video_asset` | 任务记录接收、处理、首次失败及持久成片校验信息。产物按媒体版本、类型和变体唯一，保存对象键、URL、规格、字节、摘要及校验时间。 |
| `feed_video_draft_request / feed_video_submission` | 建稿和显式提交各保留幂等回执，绑定操作人、编辑及请求内容或版本。 |

正片为索引前置的 H.264 SDR MP4，最高 720p、30 fps，保留较小尺寸及较低帧率。有声源保留音频，无声源保持无音轨。支持的 PQ／HLG 转单份 SDR，无法可靠转换时提示转为 SDR 后重传。成片持久校验后可清原片，重启或派生失败时按同一版本恢复。短预览取开头最多 5 秒，独立无声 MP4，最高 360p、整文件至多 200 KiB。

默认封面从开头最多 3 秒选取可用画面，无可用帧时可补传。自定义封面支持静态 JPEG、PNG、WebP，最大 5 MiB、最长边 4096。每个封面变体生成独立小／大 WebP，小档 240×180，大档按比例宽至多 720 像素。换封面沿用正片和短预览。四项产物均通过分发校验才可就绪，包括匿名读取、来源许可、字节校验及正片 Range 206。

失败且无持久成片的原片从首次失败起保留 24 小时。草稿到期解除媒体引用，保留编辑字段；正常放弃、替换后从失去最后有效引用起保留 24 小时。清理逐项复核引用和活跃任务，失败项可再次回收。已提交的定时帖、隐藏帖仍保留当前媒体。迁移顺序为 v10a 帖子及版本、v10b 接收及队列、v10c 提交回执、v10d 到期状态、v10e 草稿字段。

#### 表名：feed_like

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | |
| user_id / post_id | Integer FK | UNIQUE(user_id, post_id) |
| created_at | DateTime | |

#### 表名：feed_comment

| 字段名 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| id | Integer PK | | |
| post_id / user_id | Integer FK | | |
| content | Text | | 用户评论 |
| reply_to_lxm | SmallInteger | 0 | 1=点小梦回复发出；仅 H5 落款；**无**父子树 |
| lxm_reply / lxm_reply_at / lxm_reply_read_at | Text/DateTime | NULL | LXM 回复与已读 |
| gen_status | String(16) | pending | `pending`→`generating`→`ready`/`failed`；后台软删后列表可筛 `hidden`（见 `is_hidden`） |
| due_at | DateTime | NULL | **UTC**；LLM-05 轮询 `pending AND due_at<=utcnow()` |
| is_hidden | SmallInteger | 0 | 后台软删；用户端不展示 |
| idempotency_key_digest / request_digest | Binary(32) | NULL | Open 评论可选请求键与创建时的请求摘要。账号与键摘要唯一；旧评论和无键评论保留 NULL。[外部 API 数据](../openapi/data.md) |
| created_at / updated_at | DateTime | | |

#### 表名：agent_aware_queue

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | |
| user_id / post_id | Integer FK | |
| trigger_type | String(16) | `LIKE_AWARE` / `READ_AWARE` |
| relationship_stage | String(20) | 入队快照：`stranger`/`friend`/`intimate`/`soulmate` |
| due_at | DateTime | **UTC** |
| status | String(16) | `pending`→`generating`→`sent`/`failed` |
| prompt_key | String(32) | 入队确定；消费不重算档位 |
| extra_context | JSON | 如 `is_special` |
| agent_message_id | Integer | 成功后关联 |
| fail_reason | String(255) | |
| created_at / updated_at | DateTime | |

---

#
