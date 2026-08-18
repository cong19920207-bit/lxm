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
| scheduled_publish_time | DateTime | 是 | - | **北京墙钟 naive**；可见条件：`<=feed_now() AND is_visible=1 AND generation_status='ready'` |
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
