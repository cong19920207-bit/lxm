# 林小梦生活流系统 PRD v1.9 开发进度追踪（v2）

> 文档路径：`docs/progress/林小梦生活流系统_prd_v1.9_progress.md`
> 创建时间：2026-07-05
> **v2 更新时间**：2026-07-05（同步二次审查修订：M1/M2/M3 按新 22/5/12 STEP 划分；补齐依赖与备注）
> **最近补记**：2026-07-12（H5 话题着色 + 进页 boot / TB-LF-010；同日评论角标假数 `display_comments` / 迁移 `v6e`；连续回复 `reply_to_lxm`；TB-LF-001/008/009 等同前）
> PRD 来源：`docs/design/prd_v1.9.md`（v1.9.4）
> 补充规格：`docs/design/prompt_spec_v1.2_complete.md`（v1.2.6）、`docs/design/朋友圈页面展示逻辑规范_v1.1.md`
> 拆解文档：`docs/design/林小梦生活流系统_prd_v1.9_steps.md`（v2）
> 实施计划：`docs/design/林小梦生活流系统_实施计划.md`（v2，M1→M2→M3 + 契约分阶段汇总）
> 契约文档：`docs/contract.md`（生活流：**2026-07-12 已合并**；阶段草案快照见 `docs/contract/drafts/生活流/`）
>
> **运维补丁（2026-07-09）**：DeepSeek 单次超时 15s→45s（全局默认 + 感知 IM 显式）；日场景 `plan_date=2026-07-10` 复测 ready（约 36s）。详见 TB-LF-006 / M1 契约「DeepSeek 超时 / 重试」。
> **运维补丁（2026-07-10）**：Liblib 图生图补 `resizedWidth/Height`；后台「发布 & 系统参数」可配生图参数；TB-LF-001 闭合。
> **运维补丁（2026-07-10 · 多图）**：同帖多图构图变体（B）；`liblib_client` 进行中任务并发 5→1；业务路径对帖 #2 强制四图复验通过（TB-LF-008）。
> **运维补丁（2026-07-12 · 评论角标）**：`base_comments`/`comment_multiplier` + list `display_comments`；历史不回填；`TestDisplayComments` 4 通过。详见 M1 契约草案。
> **运维补丁（2026-07-12 · H5 boot / 话题）**：进页全屏 boot（渐进透明度、8s 硬超时、哨兵延后）；话题单 `#` 着色；TB-LF-010 闭合。详见 M1「前端页面」与展示规范 v1.6。

---

## 进度总览

| 完成数 | 总环节数 | 完成率 | 当前里程碑 | M1 完成 | M2 完成 | M3 完成 |
|-------|---------|-------|-----------|---------|---------|---------|
| 38 | 38 | 100% | M3 完成 | 21/21 | 5/5 | 12/12 |

> 每完成一个 STEP，手动更新上表中的完成数和完成率。
> 里程碑闸门与契约汇总规则见 `docs/design/林小梦生活流系统_实施计划.md`。

---

## M1 · 用户可用（22 STEP）

**独立验证目标**：用户能刷 Feed + 点赞 + 发评 + 收 LXM 回复 + 图片放大 + 评论区 + 首页入口。

### 波次 W1 · 地基（4 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-001 | 数据层迁移（生活流全表+扩展字段） | 无 | ✅ | 2026-07-05 | 8 表 ORM + v6a 迁移；feed_comment.due_at；agent_message.trigger_type→String(16)+2 枚举；14 项单测通过 |
| STEP-002 | DeepSeekClient 与 LLM 节点独立模型配置 | 无（可与 001 并行） | ✅ | 2026-07-05 | 独立 DeepSeekClient（4xx 不重试/5xx+超时重试2次退避2s,4s）+ deepseek_llm_service 模型热加载 + llm_stats 统计；7 个 config key 常量；未改豆包 client；10 项单测通过。**2026-07-09**：`DEEPSEEK_DEFAULT_TIMEOUT` 15→**45**（TB-LF-006） |
| STEP-003 | 生活流全局 admin_config 配置项与热加载 | 001 | ✅ | 2026-07-05 | constants/life_feed_config.py 全量 config_key+默认值+RELATIONSHIP_STAGE_MAP；幂等种子脚本；get_life_feed_config/invalidate；constants 转包不破坏导入；12 项单测通过 |
| STEP-004 | Prompt 模板初始种子（P-01~P-14） | 003 | ✅ | 2026-07-05 | life_prompt_service.render_prompt（可选段/persona 注入/遗漏校验）；34 个 prompt config_key + 6 张映射表幂等种子；16 项单测通过 |

### 波次 W2 · 内容流水线（6 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-005 | LLM-01 周大纲自动定时任务 | 002,003,004 | ✅ | 2026-07-05 | life_planner_service.generate_week_outline（markdown 剥离/条数+词表校验/连续日期）+ 当月本地/短途/长途统计（连续行程口径，待确认）+ scheduler 周日 23:00/23:30 双 cron + CLI；8 项单测通过 |
| STEP-007 | LLM-02 日场景定时任务 | 005 | ✅ | 2026-07-05 | generate_daily_scenes（为次日生成/无大纲跳过/2~5场景+time_range 06-20/city+category 强约束/desc≥200/scene_id=scene_{date}_{seq:03d}/failed 落库供重试/ready 跳过/upsert）+ scheduler 00:20/00:30 双 cron；8 项单测通过 |
| STEP-009 | LLM-03 她的宇宙定时任务 | 007,004 | ✅ | 2026-07-05 | her_universe_service（generate_for_scene 45s×3重试/snapshot 按scene_id upsert/event INSERT IGNORE 不覆盖首次/单条失败不阻断）+ call_llm 增 timeout 透传 + scheduler 00:45 cron；6 项单测通过。⚠️core_attitude 与 P-03 schema 冲突采兼容口径（待确认） |
| STEP-011 | LLM-04 文案生成 | 009,004 | ✅ | 2026-07-05 | feed_content_service.generate_post_text（emotion 双路径/结构化去重 DedupHit/Jaccard bi-gram 相似度 SimilarityHit/旅游4阶段判定+P-05注入/hashtag抽签提示/内容安全）+ hash_utils.compute_dedup_hash + hashtag权重config(4项) + P-04-U 模板方案A规范化标记；12项单测通过。方案A经确认 |
| STEP-012 | LiblibAI 客户端与图片生成服务 | 003（可与 005~011 并行） | ✅ | 2026-07-06 | liblib_client + feed_image_service + OSS/WebP/liblib_stats；**2026-07-10**：官方 payload + resized 可配（TB-LF-001）；**同日**：多图变体 + 进行中任务并发=1（TB-LF-008） |
| STEP-013 | LIFE001 每日发布整合任务（01:00） | 011,012 | ✅ | 2026-07-06 | feed_publish_service.run_daily_publish（自动开关skip/无plan skip/发布数量抽签min(target,可用)/窗口分配+窗口内随机时刻/快照generating视同failed降级/dedup·similarity·安全跳过减1/图片全失败纯文字/先建generating行再回填image_urls+image_type/season双半球）+ season_utils.compute_season + feed_auto_publish_enabled config + scheduler 01:00 cron + CLI；actual_publish_time留NULL；11项单测通过。**2026-07-12**：新帖写入 `base_comments`/`comment_multiplier`（与点赞同范围） |

### 波次 W3 · Feed + 互动 API（4 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-015 | Feed 列表与用户读 API | 001（可与 005~013 并行） | ✅ | 2026-07-06 | feed_service+routers/feed.py（/list 游标分页+可见范围过滤+ready+is_visible+已到点/actual_publish_time懒写回幂等/评论私有过滤/display_likes Python组装/user_liked批量；/enter写last_feed_entered_at+anchor；/badge has_new+unread_reply_count）+错误码10500段。**2026-07-12**：list 增 `display_comments`；`TestDisplayComments` |
| STEP-016 | 点赞 API（feed_like） | 015 | ✅ | 2026-07-06 | POST/DELETE /{post_id}/like（幂等/real_likes±1原子防负/隐藏+未到点404/on_like_hook调用）；like_aware_service.on_like_hook stub（M1生效；M2 STEP-020替换实现，签名固定） |
| STEP-017 | 评论 API（发评/私有列表） | 015 | ✅ | 2026-07-06 | POST /{post_id}/comments（长度1-200/30s频控/内容安全三层校验/首次评论原子UPDATE has_ever_commented_feed抢占→override 30s/非首次按关系档RELATIONSHIP_STAGE_MAP延迟/写pending+due_at） |
| STEP-018 | LLM-05 评论回复延迟任务 | 002,017 | ✅ | 2026-07-06 | comment_reply_service（poll_and_consume扫due_at到期pending FOR UPDATE SKIP LOCKED/consume_one原子claim pending→generating/P-06渲染+称呼可选段方案A规范化/45s×3重试/内容安全/状态机ready·failed）+scheduler 30s IntervalTrigger。M1期间LLM-05生效，感知IM(LLM-06/07)属M2 |

### 波次 W4 · H5（4 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-022 | 朋友圈 H5 页面骨架 | 015 | ✅ | 2026-07-06 | frontend/pages/feed.html（Header读/api/feed/config/header+兜底/消息icon角标/mounted调enter+list/相对时间四分支/骨架屏/空态/错误态重试/下拉刷新/无限滚动500ms限流）+ GET /api/feed/config/header。**2026-07-12**：进页 `#feed-boot-loading`（渐进 alpha/blur、硬超时 8s）；哨兵延后挂载（TB-LF-010）；下拉刷新仍骨架 |
| STEP-023 | Feed 图片展示与全屏预览 | 022 | ✅ | 2026-07-06 | 1/2/3-4张布局+懒加载+失败灰占位不阻断；全屏预览左右滑+双指缩放1~3x+单击/按钮关闭；话题着色；TD-001手势冲突处理（overscroll-behavior contain+non-passive preventDefault），登记 tech-debt TD-032。**2026-07-12**：话题改为单 `#` 起标至空格/标点（兼容 `#话题#`） |
| STEP-024 | 互动栏（点赞/评论输入） | 016,017,022 | ✅ | 2026-07-06 | 点赞乐观更新+失败回滚+300ms防抖+服务端为准；底部评论面板maxlength200+字数计+发送态+429/400 Toast；同一时刻仅一帖评论态 |
| STEP-025 | 评论区展示（私有+「我」） | 024 | ✅ | 2026-07-06 | 用户评论强制「我：」/LXM「林小梦回复 我：」轻度高亮(#FFF9E6)/lxm_reply=null占位「林小梦正在回复...」/anchor_comment_id 或 ?focus=unread_reply 首屏 scrollIntoView+闪烁1.5s后清锚点 |

### 波次 W5 · 导航（3 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-027 | 首页朋友圈入口与双徽标 | 015,022 | ✅ | 2026-07-06 | index.html 记忆卡替换为「她的朋友圈」入口；/api/feed/badge：unread>0数字角标 / 否则has_new红点 / 皆无不显示（互斥）；点击 unread>0→?focus=unread_reply 否则进列表顶；visibilitychange刷新（无轮询） |
| STEP-028 | IM 页记忆入口迁移 | 无（可与 022 并行） | ✅ | 2026-07-06 | chat.html 右上角新增📖记忆入口→/pages/memory.html；memory.html 内部功能与样式未改 |
| STEP-037 | 页面路由互通（第八章 v1） | 022,027,028 | ✅ | 2026-07-06 | 入口链路核对（index↔feed↔chat↔memory）；memory.html 返回改为→chat.html；prompt_builder.py 经检索无 feed_post/worldview_snapshot 引用（IM 主链 v1 无 Feed 注入，无需改动） |

---

## M2 · 感知闭环（5 STEP）

**独立验证目标**：感知 IM 独立线 + SSE 实时新帖 + 已读闭环。前置：M1 全部 ✅。

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-019 | agent_aware_queue 基础设施与独立轮询 | 001,002 | ✅ | 2026-07-08 | agent_aware_service(enqueue/consume_pending/consume_record 原子锁 pending→generating→sent/failed)+agent_aware_task 60s IntervalTrigger；落 agent_message action_score=0+timeline_seq；不共享 P0-P4 计数器/间隔/黑名单；v6b 迁移加 prompt_key/extra_context |
| STEP-020 | LLM-06 点赞感知 IM | 016,019 | ✅ | 2026-07-08 | like_aware_service 真实实现替换 stub（同帖去重/特殊档 100%+used_count 原子+1/常规档 30%+关系档延迟/内容安全）；generate_and_send 用 P-07+llm_06。**2026-07-09**：`_AWARE_TIMEOUT` 15→**45** |
| STEP-021 | LLM-07 已读感知 IM | 019,015 | ✅ | 2026-07-08 | read_aware_service（on_feed_read/batch 多帖取最近发布/同帖去重/6h 点赞互斥/特殊档 P-14/常规档 P-08~11 关系档映射/内容安全）；generate_and_send 用 llm_07。**2026-07-09**：共用 `_AWARE_TIMEOUT=45` |
| STEP-026 | SSE 新帖推送 | 015,022 | ✅ | 2026-07-08 | feed_sse_service 单进程内存注册表 + GET /api/feed/events(token query+15s 心跳)+feed_new_broadcast_task 30s；feed_post.sse_broadcasted 去重；feed.html EventSource+「X 条新动态」条+指数退避重连 |
| STEP-029 | 已读上报（评论曝光+Feed 停留） | 021,025 | ✅ | 2026-07-08 | POST /api/feed/comments/{id}/read(幂等+越权 403 ERR 10506)+POST /api/feed/{post_id}/read(触发 on_feed_read)；feed.html IntersectionObserver 评论 0.6 曝光 + Feed 卡片停留 3s |

---

## M3 · 运营可管（12 STEP）

**独立验证目标**：运营 4 角色可全流程操作。前置：M1+M2 全部 ✅。

### 波次 W1 · 后台 API（4 STEP，全部可并行）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-006 | 周大纲后台管理 API | 005 | ✅ | 2026-07-08 | life_plan_mgmt：outline CRUD/一键生成 + settings；**2026-07-09**：GET 对 ops_admin 只读放开 |
| STEP-008 | 日生活计划后台管理 API | 007 | ✅ | 2026-07-08 | life_plan_mgmt：daily 查询/触发生成/手动补录场景 scenes；operation_log 覆盖；**2026-07-09**：编辑场景补 category∈当日大纲校验（定案 B）；LLM 日志摘要仍未做→TD-033 |
| STEP-010 | 她的宇宙后台管理 API | 009 | ✅ | 2026-07-08 | worldview_mgmt：snapshots + events 分页/CRUD；core_attitude 四选项；删快照校验 feed_post 引用；**2026-07-09**：snapshots 支持近14天分页（无参默认）+ 单日数组兼容；ops_admin 只读 GET |
| STEP-014 | 朋友圈后台管理 API | 013 | ✅ | 2026-07-08 | feed_mgmt：posts 列表(4状态)/详情/编辑/可见性/删除 + 手动新增双模式(upload/ai_generate，管理员权威跳过 dedup/similarity) + 自动发布开关；ops_admin 只读；**2026-07-09 UI**：feed-posts 详情/编辑/文字发帖/AI 可选出图/显隐 + 自动发布只读跳转；真删→TD-035；本地上传→TD-036 |

### 波次 W2 · 后台 UI（7 STEP，多数可并行）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-030 | 后台 Tab0 全局人设与词汇表管理 | 003 | ✅ | 2026-07-08 | life-feed-global.html：人设扩展(likes/dislikes/style/limits)+词汇表(categories/emotion 标签编辑)+feed_page_* Header 配置(bg/avatar/签名/昵称只读)；草稿→发布三卡点 |
| STEP-031 | 后台生活计划+她的宇宙管理页 | 006,010 | ✅ | 2026-07-08 | **2026-07-09 补齐**：life-plan（周大纲 CRUD/设置草稿+发布/日场景弹窗增删改/进入日场景/admin-table）+ worldview（快照近14天分页+CRUD/事件 CRUD/emotion 词表+自由输入/admin-table）；ops_admin 只读进页 |
| STEP-032 | 后台 Prompt Tab1~4 管理页 | 004 | ✅ | 2026-07-08 | life-feed-prompts.html：内容 Prompt(P-01~05)tab + 图像映射 6 表 JSON 可视化 tab；逐项/批量草稿·发布 |
| STEP-033 | 后台 Prompt Tab5~6 互动与已读管理页 | 004 | ✅ | 2026-07-08 | life-feed-prompts.html 互动 tab：P-06~14 Prompt + 互动参数(LLM-05/06/07 模型 + 评论回复/点赞常规/已读常规四档延迟 min/max + 点赞·已读特殊档窗口/上限/延迟 + 已读点赞互斥小时数)，数字校验，走三卡点 |
| STEP-034 | 后台评论管理（10.4） | 014,018 | ✅ | 2026-07-08 | feed-comments.html + feed_comment_mgmt：5 状态筛选(pending/generating/ready/failed/hidden)+手动补发 regenerate；ops_admin 只读；**2026-07-09 UI**：admin-table + post/user 筛选 + 已读列 + 编辑/软隐/补发 |
| STEP-035 | 后台点赞/已读感知消息管理（10.8） | 020,021 | ✅ | 2026-07-08 | agent-aware.html + agent_aware_mgmt：queue×message 联合视图(user/trigger/status 筛选)+重试/删除+重置用户特殊档计数(super_admin)；ops_admin 只读；**2026-07-09 UI**：admin-table + 消息摘要 + 详情弹窗 + 重置入口 |
| STEP-036 | 后台发布时间/可见范围/系统参数 | 003 | ✅ | 2026-07-08 | life-feed-system.html：自动发布开关+发布窗口×3+历史可见范围+base_likes/like_multiplier 范围+LiblibAI 近 7 天看板；**2026-07-10** 增「Liblib 生图参数」（UUID×2/steps/尺寸/resized/strength）；tech_ops 只读 |

### 波次 W3 · 菜单（1 STEP）

| 环节编号 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|---------|---------|------|---------|------|
| STEP-038 | 后台生活流菜单入口与路由注册 | 030~036 全部 ✅ | ✅ | 2026-07-08 | LIFE_FEED_MENU + 四角色 RBAC；**2026-07-09**：ops_admin 增生活计划/她的宇宙只读子项；GET life-config 对 ops 放开 |

---

## 状态说明

- ⬜ 未开始
- 🔄 进行中
- ✅ 已完成
- ❌ 阻塞中（在备注中填写原因）

---

## 契约更新记录

| 日期 | 里程碑/STEP | 更新内容 | 文档位置 |
|------|------------|---------|---------|
| — | STEP-* | 单个 STEP 完成时仅在交付说明附「契约条目草稿」，不改任何契约文档 | 交付说明 |
| 2026-07-06 | M1 完成 | 汇总 M1 全部 22 STEP 契约草稿为 `M1_契约草案.md`（含 M2/M3 交接章节） | `docs/contract/drafts/生活流/M1_契约草案.md` |
| 2026-07-08 | M2 完成 | 增量汇总 M2 草稿为 `M2_契约草案.md`（不重复 M1 已稳定内容） | `docs/contract/drafts/生活流/M2_契约草案.md` |
| 2026-07-08 | M3 完成 | 增量汇总 M3 后台 API/UI/菜单/RBAC 草稿为 `M3_契约草案.md`（不重复 M1/M2 已稳定内容） | `docs/contract/drafts/生活流/M3_契约草案.md` |
| 2026-07-09 | M3 增量补记 | STEP-031 UI 补齐 + 快照多日分页 + 场景编辑校验 B + ops 只读扩权 + admin-table；写入 M3 草案 §1.1/1.2/2.1/2.2/RBAC | `docs/contract/drafts/生活流/M3_契约草案.md` |
| 2026-07-09 | M3 增量补记 | STEP-014/034/035 管理页 UI 补齐（内容/评论/感知）；§1.3 DELETE/auto-publish 语义澄清；新增 §2.3~2.5；TD-034 清偿、TD-035/036 | `docs/contract/drafts/生活流/M3_契约草案.md` · `docs/tech-debt.md` |
| 2026-07-10 | 横切补记（Feed 时区） | `scheduled_publish_time`/到点/`feed_now()` 统一 Asia/Shanghai；H5·后台墙钟展示；SSE 广播同步；台账 TB-LF-007 | `M1_契约草案.md` · `M2_契约草案.md` · `M3_契约草案.md` · `M1_临时缺陷台账.md` |
| 2026-07-10 | 横切补记（Liblib TB-LF-001） | 官方 payload + resized 可配；`life-feed-system` 生图参数；真机出图闭合 | `M1_契约草案.md` · `M3_契约草案.md` · `M1_临时缺陷台账.md` · `prompt_spec_v1.2_complete.md` · 本进度 |
| 2026-07-10 | 横切补记（多图 TB-LF-008） | 同帖多图构图变体 B；进行中任务并发=1；业务帖 #2 四图复验 | `M1_契约草案.md` · `M3_契约草案.md` · `M1_临时缺陷台账.md` · `prompt_spec` v1.2.6 · 本进度 |
| 2026-07-11 | H5 朋友圈 UI 补记 | feed.html 对齐设计图：同日左列合并、meta 行、单图 4:3、字号字体、评论区样式、互动图标；澄清 SSE 新帖提示条≠评论回复未读；无 API/库变更 | `M1_契约草案.md` · `M2_契约草案.md` · `M3_契约草案.md` · `drafts/生活流/README.md` |
| 2026-07-12 | **全链路合并** | 汇总 M1+M2+M3 三份草案正式并入 `docs/contract.md`（扩展既有表 + 生活流新表/API/任务/后台）；草案目录保留快照；关系档以 `soulmate` 为准 | `docs/contract.md` · `drafts/生活流/README.md` |
| 待触发 | — | （合并已完成；后续增量直接改 `contract.md`） | `docs/contract.md` |

---

## 阻塞记录

| 日期 | STEP | 阻塞原因 | 解决方案 | 解决日期 |
|------|------|---------|---------|---------|
| — | STEP-012 | A-3 / TB-LF-001 Liblib 真机出图 | **测试环境已闭合（2026-07-10）**；生产域名参考图拉取仍建议部署后复核 | 2026-07-10 |

---

## 变更记录

| 日期 | 变更描述 | 影响 STEP | 处理方式 |
|------|---------|---------|---------|
| 2026-07-05 | 初始拆解，基于 PRD v1.9.4 | 全部 | — |
| 2026-07-05 | 审查遗漏回填：SSE 调度、未读滚动、Header 配置、后台菜单等；新增 STEP-038 | STEP-003,008,013,015~022,026~027,030,034~038 | 已写入 steps 文档 |
| 2026-07-05 | steps_review 遗漏回填：trigger_type 迁移、4.4.1 张数、系统日志横切、level 映射、TD-001、SSE 去重等 | STEP-001,003,006~009,012~013,018~021,023,026,031,035,038 | 已写入 steps 文档 |
| 2026-07-05 | 新增实施计划 + 契约分阶段汇总规则（M1/M2 草案，M3 合并 contract.md） | — | `docs/design/林小梦生活流系统_实施计划.md` |
| 2026-07-05 | **v2 二次审查修订**：<br>1. M1/M2/M3 重划分（22/5/12）<br>2. STEP-023/025 前移至 M1（用户体验完整性）<br>3. 5 个二选一技术选型定案（scene_id / actual_publish_time / LLM-05 延迟 / SSE 注册表 / LiblibAI 统计）<br>4. 15 个偏薄 STEP 内容补齐<br>5. 首次评论 30s override 竞态处理明确（STEP-017 原子 UPDATE 抢占）<br>6. STEP-016 stub → M2 STEP-020 替换机制明确<br>7. 契约措辞统一为「契约条目草稿」<br>8. 每个 M 独立验证清单添加<br>9. STEP 依赖顺序图与波次表重构 | 全部 38 STEP + 实施计划全文 | v2 已写入 steps.md、实施计划.md、progress.md |
| 2026-07-09 | STEP-031 管理页 CRUD/展示补齐；快照近14天分页；编辑场景 category 校验；ops 只读生活计划/宇宙；列表改 admin-table | 006,008,010,031,038 | 代码已改；M3 契约草案已增量；技术债 TD-033/034 |
| 2026-07-09 | 朋友圈内容/评论/感知三页 UI 补齐（admin-table + 文档已有 API 接线）；真删帖/本地上传记 TD；无服务端契约变更 | 014,034,035 | 代码已改；M3 草案 §2.3~2.5；TD-034 清偿、TD-035/036 新增 |
| 2026-07-10 | Feed 到点时区：列表/SSE/`last_feed_entered_at` 用 `feed_now()`（上海墙钟）；H5/后台计划时间按墙钟展示；评论 due_at 仍 UTC | 015,016,017,026,029 + 前端/后台展示 | 代码已改；临时契约与台账 TB-LF-007 已同步；**未**改 `contract.md` |
| 2026-07-10 | Liblib 官方 payload + 图生图 resized 可配；真机 text2img/img2img；后台生图参数表单 | 012,036 | 台账 TB-LF-001 闭合；M1/M3 草案 + prompt_spec v1.2.5 + 本进度已同步；**未**改 `contract.md` |
| 2026-07-10 | 同帖多图轻量变体 + Liblib 进行中任务并发 5→1；业务路径帖 #2 四图复验 | 012 | 台账 TB-LF-008 闭合；M1/M3 + prompt_spec v1.2.6 + 本进度已同步；**未**改 `contract.md` |

---

## 二次审查修复项对照表（v2 交付说明）

### P0（v2 已修复）

- [x] M1 前移 STEP-023（图片全屏预览）→ M1 用户可用图片放大
- [x] M1 前移 STEP-025（评论区展示）→ M1 用户可看到自己评论与 LXM 回复
- [x] STEP-017 首次评论 30s override 竞态修复（`UPDATE ... WHERE has_ever_commented_feed=0` 原子抢占）
- [x] STEP-016 on_like_hook stub 明确 M2 由 STEP-020 替换
- [x] scene_id 命名规范定案：`scene_{plan_date}_{seq:03d}`
- [x] `actual_publish_time` 写入方式定案：STEP-015 懒惰写回
- [x] LLM-05 延迟调度定案：DB 轮询 `feed_comment.due_at`
- [x] SSE 连接注册表定案：单进程内存字典
- [x] LiblibAI 统计定案：`liblib_stats:{date}` HSET
- [x] `dedup_hash` 算法明确：`md5(f"{venue}|{cat}|{city}").hexdigest()`
- [x] 文本相似度算法明确：Jaccard bi-gram，阈值 0.75
- [x] 关系档字符串常量集中：`RELATIONSHIP_STAGE_MAP`（STEP-003），全 STEP 复用

### P1（v2 已修复）

- [x] STEP-006/008/010/014 后台 API 每个 STEP 补齐 API 清单与字段校验规则
- [x] STEP-011 补 emotion 双路径落库规则（快照 ready/failed）
- [x] STEP-012 图片张数抽签 + 类型抽签 + 4 张映射表兜底路径全流程
- [x] STEP-013 season 计算 + 关闭自动发布开关时 skip 逻辑
- [x] STEP-017 评论字符长度 ≤ 200 + 30s/帖同用户频控
- [x] STEP-018 LLM-05 gen_status 状态机（pending → generating → ready/failed）
- [x] STEP-022~025 每个 STEP 补充 DOM/事件/CSS 关键点
- [x] STEP-026 补 SSE 心跳 + 断线重连 + `sse_broadcasted` 字段迁移
- [x] STEP-029 前端 IntersectionObserver + Feed 停留 3s 逻辑
- [x] STEP-030~036 每个 admin 页面结构 + 三卡点发布流程
- [x] STEP-038 前置改为 030~036 全部 ✅ 避免死链

### P1（横切遗漏）

- [x] §0.1 系统日志埋点强制覆盖 STEP 清单
- [x] §0.2 JWT + 操作日志 + admin_config 草稿机制横切说明
- [x] §0.3 契约措辞统一
- [x] §0.4 环境变量清单（DeepSeek + LiblibAI + OSS + CDN + 参考图 URL）
- [x] §0.5 五个二选一定案

### P2（可选优化，已作为 v2 附加改进）

- [x] 附录 A 波次表按新 M 边界重写
- [x] 每个 STEP 补齐"完成后执行"下一步指引
- [x] 每个 STEP 补齐"契约条目草稿"提交说明

---

## v1 → v2 迁移备注

- v1 已完成的 STEP 若继续沿用，需重新对照 v2 版对应 STEP 的"开发任务"章节验收剩余点
- 若 v1 期间已提交契约条目草稿，v2 里程碑负责人在汇总时须重新对齐（重点检查 `feed_comment.due_at` / `agent_message.trigger_type` / `RELATIONSHIP_STAGE_MAP` 三项是否已落）
