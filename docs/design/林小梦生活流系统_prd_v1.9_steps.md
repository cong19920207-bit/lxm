# 林小梦生活流系统 PRD v1.9 开发步骤拆解

> 来源：`docs/design/prd_v1.9.md`（v1.9.4）+ `docs/design/prompt_spec_v1.2_complete.md`（v1.2.4）+ `docs/design/朋友圈页面展示逻辑规范_v1.1.md`（v1.4）
> 进度追踪：`docs/progress/林小梦生活流系统_prd_v1.9_progress.md`
> 实施计划：`docs/design/林小梦生活流系统_实施计划.md`（M1→M2→M3；契约分阶段汇总见该文档 §7）
> 契约文档：`docs/contract.md`（生活流 M3 后合并；阶段草案 `docs/contract/drafts/生活流/`）
>
> **补遗（2026-07-05 审查回填）**：SSE 推送调度、未读回复滚动定位、Header 配置来源、后台菜单注册等 14 处细化遗漏已写入对应 STEP；新增 **STEP-038**。
>
> **补遗（2026-07-05 steps_review 回填）**：`agent_message.trigger_type` 迁移、4.4.1 图片张数分布、横切系统日志、关系档 level 映射、TD-001、SSE 同帖去重等。
>
> **补遗（2026-07-05 二次审查 v2 回填）**：M1/M2/M3 里程碑重划分（M1=22 STEP 保证用户 Feed 完整可用/M2=5 STEP 感知 IM 独立线 + SSE + 已读上报/M3=12 STEP 全部后台）；5 个二选一技术选型定案；15 个偏薄 STEP 内容补齐；10 处幻觉/竞态/遗漏修复；契约措辞统一为「契约条目草稿」。
>
> **补遗（2026-07-09 · DeepSeek 超时）**：生活流 DeepSeek 单次超时由 15s 统一调整为 **45s**（`DEEPSEEK_DEFAULT_TIMEOUT` + 感知 IM `_AWARE_TIMEOUT`）；STEP-002 / 020 / 021 正文已同步。原因与验收见 `docs/contract/drafts/生活流/M1_临时缺陷台账.md` TB-LF-006、`M1_契约草案.md`「DeepSeek 超时 / 重试」。**不影响**豆包对话主链、SSE 心跳 15s。

---

## 0. 横切要求（所有 STEP 必读）

以下要求为**所有 STEP 共同遵守的项目级规范**，不在每个 STEP 中重复列出。

### 0.1 系统日志埋点（PRD 2.2.2 / 3.2.5 / 4.7 / 6.4；v1.5「全流程日志埋点」）

- 生活流 LLM/定时任务/互动关键节点均须写入后台可查看的系统日志（接入方式与现有 `system-logs` 页面一致，参考 `backend/tasks/ai_diary_task.py` 现有埋点风格）
- **强制覆盖 STEP**：005 / 007 / 009 / 011 / 012 / 013 / 018 / 020 / 021
- **强制事件类型**：任务触发（INFO）、跳过（INFO）、成功（INFO 含关键指标）、单条失败重试（WARN）、最终失败（ERROR）
- **验收要点**：后台 `admin/pages/system-logs.html` 可按关键词过滤到本 STEP 相关日志

### 0.2 项目安全与规范协同（`.cursorrules`）

**所有生活流后台 API（STEP-006 / 008 / 010 / 014 / 030~036）必须遵守**：

- **JWT 鉴权**：除登录注册外必须校验；后台 API 路径前缀统一 `/api/admin/life-feed/...` 或按现有惯例 `/api/admin/<模块>/...`；RBAC 至少要求 `ai_trainer` 或以上
- **操作日志**：涉及"发布 / 编辑 / 删除 / 隐藏 / 手动补发"的操作，必须写入 `operation_log`（沿用现有 `admin/pages/operation-logs.html` 数据源）
- **admin_config 草稿机制**：所有配置项写入走 `is_draft / is_active` 双字段流程，通过既有「测试集验证 → CONFIRM 二次确认 → 5min 监控窗口」三道卡点发布；本 STEP 拆解不重复描述该流程细节
- **API 响应统一格式**：`{"code": 0, "data": {}, "message": "success"}`

**所有生活流用户端 API（STEP-015 / 016 / 017 / 026 / 029）必须遵守**：

- **JWT 鉴权**：Bearer Token；未登录返回 401
- **请求参数校验**：使用现有 Pydantic 校验体系（参考 `backend/routers/chat.py`）
- **错误码**：新增错误码必须在 `backend/constants.py` 定义常量

### 0.3 契约文档措辞统一（与实施计划 §7 对齐）

- 单个 STEP 完成时**不**直接更新 `docs/contract.md`
- 各 STEP 完成标志中出现的"契约文档已更新"**统一解读为**：在 STEP 交付说明中附「契约条目草稿」，等本里程碑收尾时由里程碑负责人汇总进 `docs/contract/drafts/生活流/M*_契约草案.md`
- `docs/contract.md` 只在 **M3 全链路验收通过后**一次性合并（见实施计划 §7.4）

### 0.4 环境变量新增清单（在 M1 开工前**一次性**写入 `.env.example` 与部署文档）

| 变量名 | 用途 | 首次引入 STEP |
|-------|------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | STEP-002 |
| `DEEPSEEK_BASE_URL` | DeepSeek Endpoint（如 `https://api.deepseek.com`） | STEP-002 |
| `LIBLIB_ACCESS_KEY` | LiblibAI AccessKey | STEP-012 |
| `LIBLIB_SECRET_KEY` | LiblibAI SecretKey（HMAC-SHA1 签名用） | STEP-012 |
| `LIBLIB_BASE_URL` | LiblibAI Endpoint | STEP-012 |
| `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` / `OSS_ENDPOINT` / `OSS_BUCKET` | 阿里云 OSS 凭证与桶（存 feed_post 图片） | STEP-012 |
| `OSS_CDN_DOMAIN` | OSS 对应 CDN 加速域名（写入 `feed_post.image_urls`） | STEP-012 |
| `FEED_IMAGE_REFERENCE_PUBLIC_URL` | 生产域名的 base.png URL（供 LiblibAI 公网拉取，附录 A-3） | STEP-012 |

**技术凭证一律不进后台 UI**（沿用现有惯例，见 PRD §9 前言）。

### 0.5 五个二选一技术选型定案（原 STEP 遗留的「或」型问题，本次全部拍板）

| 选型 | 定案 | 涉及 STEP |
|------|------|----------|
| **scene_id 规则** | `scene_{plan_date}_{seq:03d}`（如 `scene_2026-06-01_001`），全局唯一；`plan_date` 为 YYYY-MM-DD；`seq` 从 001 起编号且当日单调递增 | STEP-007（生成方）；STEP-009 / 011 / 013（消费方） |
| **`feed_post.actual_publish_time` 写入方式** | STEP-013 落库时写 `NULL`；STEP-015 Feed 列表 API 查询命中 `scheduled_publish_time <= NOW() AND is_visible=1 AND actual_publish_time IS NULL` 的记录时，**同步 UPDATE** 一次为 `NOW()`；**无独立定时任务** | STEP-013 / STEP-015 |
| **LLM-05 评论回复延迟调度** | 走 **DB 轮询**（沿用 STEP-019 `agent_aware_queue` 架构思路，但用**独立字段**：`feed_comment.due_at DATETIME NULL` + `gen_status='pending'`）；1min 独立轮询任务扫描 `due_at <= NOW() AND gen_status='pending'`；不走 APScheduler 内存延迟任务 | STEP-001（表结构补 due_at）/ STEP-018（轮询任务） |
| **SSE 连接注册表** | v1 **单进程内存字典** `dict[user_id -> list[asyncio.Queue]]`，用户断开自动 remove；不引入 Redis Pub/Sub | STEP-026 |
| **LiblibAI 统计对接** | 新增 Redis HSET `liblib_stats:{date}`（HINCRBY `total` / `success` / `failed` / `points_used`），沿用现有 `.cursorrules` 中 `llm_stats:{date}` 风格；不依赖日志聚合 | STEP-012（写入）/ STEP-036（读取展示） |

---

### 0.6 里程碑重划分（对齐实施计划 v2）

- **M1（22 STEP）· 内容流水线 + 用户 Feed 完整可用 + 首页入口**：001~005, 007, 009, 011~013, 015~018, 022~025, 027~028, 037
- **M2（5 STEP）· 感知 IM 独立线 + SSE + 已读闭环**：019, 020, 021, 026, 029
- **M3（12 STEP）· 后台运营**：006, 008, 010, 014, 030~036, 038

**独立验证原则**：M1 结束用户能刷 Feed + 点赞 + 发评 + 收到 LXM 回复 + 看图放大 + 首页入口感知新内容（下拉刷新触发）；M2 结束新增感知 IM + SSE 实时新帖提示 + 已读闭环；M3 结束后台可编辑全部人设/配置/内容。

---

## 1. 功能清单

### 1.1 全局人设与内容配置（第零章）[核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-001 | `lxm_base_persona` 复用现有 `persona` 配置，不新建独立项 | [核心] | 现有 persona 管理 |
| F-002 | `lxm_likes` / `lxm_dislikes` / `lxm_writing_style` / `lxm_content_limits` 后台可编辑 | [核心] | F-001 |
| F-003 | `categories_vocab` 固定枚举，约束 LLM-01 | [核心] | 无 |
| F-004 | `emotion_vocab` 14 核心词 + 自由兜底 + 图片映射兜底表 | [核心] | 无 |

### 1.2 基础设施 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-005 | 新建 `DeepSeekClient`，LLM-01~07 独立模型版本配置 | [核心] | 无 |
| F-006 | 生活流全量数据表（11.4）+ users/relationship 扩展字段 | [核心] | 无 |
| F-007 | Prompt 后台配置 P-01~P-14 种子与 Tab 结构（第九章） | [核心] | F-002~F-004 |

### 1.3 LIFE000 生活规划引擎 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-008 | LLM-01 周大纲：周日 23:00 + 23:30 重试，`days_count` 参数化 | [核心] | F-003,F-005,F-007 |
| F-009 | 周大纲后台管理：查看/单日 CRUD/条件内一键生成 | [核心] | F-008 |
| F-010 | LLM-02 日场景：每日 00:20，场景数≥2，强约束 city+categories | [核心] | F-008 |
| F-011 | 日生活计划后台管理 | [核心] | F-010 |

### 1.4 PER003 她的宇宙 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-012 | LLM-03 动态快照 + 静态事件同次生成，00:45，45s×3 重试 | [核心] | F-010,F-007 |
| F-013 | 她的宇宙后台管理（快照 CRUD + 事件库 CRUD） | [核心] | F-012 |

### 1.5 LIFE001 朋友圈内容生成 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-014 | LLM-04 文案：双路径 emotion、hashtags、旅游叙事 P-05 | [核心] | F-012,F-007 |
| F-015 | 结构化去重（venue_type+category+city，7 天）+ 文本相似度≥0.75 | [核心] | F-014 |
| F-016 | LiblibAI 图片：P-12 人物 / P-13a/b/c 非人物，关键词兜底 | [核心] | F-004 |
| F-017 | 每日 01:00 发布任务：2~3 条、发布窗口、OSS+CDN、降级策略 | [核心] | F-014,F-016 |
| F-018 | 朋友圈后台管理：CRUD/隐藏/手动发布/自动开关 | [核心] | F-017 |

### 1.6 LIFE002 Feed 展示 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-019 | 朋友圈独立 H5 页（UI 规范全文） | [核心] | F-017 |
| F-020 | 首页「朋友圈入口」替换「记忆入口」；记忆迁至 IM 右上角 | [核心] | F-019 |
| F-021 | 双徽标：[New] + 未读 LXM 评论数字角标 | [核心] | F-019 |
| F-022 | `GET /api/feed/events` SSE `feed_new` | [核心] | F-019 |
| F-023 | 历史可见范围 7/30/180/全部（后台统一） | [核心] | F-019 |

### 1.7 LIFE004 互动 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-024 | 点赞：展示数公式、feed_like、取消不撤回 IM | [核心] | F-019 |
| F-025 | LLM-05 评论必回：关系档延迟、首次 30s override、v1 简单回复 | [核心] | F-024 |
| F-026 | LLM-06 点赞 IM：特殊档窗口+常规 30%，agent_aware_queue 独立线 | [核心] | F-024,F-027 |
| F-027 | agent_aware_queue + 独立轮询 + agent_message 落库 action_score=0 | [核心] | F-006,F-005 |

### 1.8 LIFE005 已读感知 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-028 | 停留即已读；近 6h 点赞 IM 入队互斥 | [核心] | F-027 |
| F-029 | LLM-07：特殊档 P-14 + 常规 P-08~P-11，关系四档 | [核心] | F-028 |

### 1.9 对话联动 [核心]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-030 | v1 仅页面跳转：首页↔朋友圈↔IM，不向 IM 注入 Feed | [核心] | F-019,F-020 |

### 1.10 后台管理 [核心/扩展]

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-031 | Tab0 全局配置管理（10.0） | [核心] | F-002~F-004 |
| F-032 | 生活计划+她的宇宙管理页（10.1,10.2） | [核心] | F-009,F-013 |
| F-033 | Prompt Tab1~6 管理（第九章） | [核心] | F-007 |
| F-034 | 评论管理 10.4：含失败补发 | [核心] | F-025 |
| F-035 | 点赞/已读感知消息管理 10.8 | [核心] | F-026,F-029 |
| F-036 | 发布时间窗口/可见范围/南半球白名单等系统参数（10.5~10.7） | [扩展] | F-017 |
| F-037 | 后台生活流模块菜单入口与 RBAC 路由注册 | [核心] | F-031 |

---

## 2. 开发环节总览

> **列说明**：
> - **前置环节**：**必须**已完成的其他 STEP（真实代码/表/接口依赖，非仅顺序偏好）
> - **可并行**：与本 STEP **同一里程碑内**可并行执行的 STEP
> - **里程碑**：M1 / M2 / M3

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 可并行 | 复杂度 | 里程碑 |
|---------|---------|---------|---------|--------|--------|--------|
| STEP-001 | 数据层迁移（生活流全表+扩展字段） | DB/Alembic | 无 | — | 中 | M1 |
| STEP-002 | DeepSeekClient 与 LLM 节点独立模型配置 | backend/utils | 无 | STEP-001 | 中 | M1 |
| STEP-003 | 生活流全局 admin_config 配置项与热加载 | admin_config | STEP-001 | STEP-002 | 中 | M1 |
| STEP-004 | Prompt 模板初始种子（P-01~P-14） | admin_config | STEP-003 | — | 低 | M1 |
| STEP-005 | LLM-01 周大纲自动定时任务 | LIFE000/scheduler | STEP-002,003,004 | STEP-012 | 高 | M1 |
| STEP-007 | LLM-02 日场景定时任务 | LIFE000/scheduler | STEP-005 | STEP-012 | 高 | M1 |
| STEP-009 | LLM-03 她的宇宙定时任务 | PER003/scheduler | STEP-007,004 | STEP-012 | 高 | M1 |
| STEP-011 | LLM-04 文案生成（去重/相似度/旅游叙事） | LIFE001 | STEP-009,004 | STEP-012 | 高 | M1 |
| STEP-012 | LiblibAI 客户端与图片生成服务 | LIFE001/图片 | STEP-003 | STEP-005~011 | 高 | M1 |
| STEP-013 | LIFE001 每日发布整合任务（01:00） | LIFE001/scheduler | STEP-011,012 | — | 高 | M1 |
| STEP-015 | Feed 列表与用户读 API | LIFE002 API | STEP-001 | STEP-005~013 | 中 | M1 |
| STEP-016 | 点赞 API（feed_like） | LIFE004 API | STEP-015 | STEP-017 | 中 | M1 |
| STEP-017 | 评论 API（发评/私有列表） | LIFE004 API | STEP-015 | STEP-016 | 中 | M1 |
| STEP-018 | LLM-05 评论回复延迟任务 | LIFE004 | STEP-002,017 | — | 高 | M1 |
| STEP-022 | 朋友圈 H5 页面骨架（Header+列表+加载态） | frontend | STEP-015 | STEP-028 | 高 | M1 |
| STEP-023 | Feed 图片展示与全屏预览 | frontend | STEP-022 | STEP-024 | 中 | M1 |
| STEP-024 | 互动栏（点赞/评论输入） | frontend | STEP-016,017,022 | STEP-023 | 中 | M1 |
| STEP-025 | 评论区展示（私有+「我」） | frontend | STEP-024 | — | 低 | M1 |
| STEP-027 | 首页朋友圈入口与双徽标 | frontend | STEP-015,022 | STEP-028 | 中 | M1 |
| STEP-028 | IM 页记忆入口迁移 | frontend | 无 | STEP-022,027 | 低 | M1 |
| STEP-037 | 页面路由互通（第八章 v1） | frontend | STEP-022,027,028 | — | 低 | M1 |
| STEP-019 | agent_aware_queue 基础设施与独立轮询 | LIFE004/005 | STEP-001,002 | STEP-026 | 高 | M2 |
| STEP-020 | LLM-06 点赞感知 IM | LIFE004 | STEP-016,019 | STEP-021,026 | 高 | M2 |
| STEP-021 | LLM-07 已读感知 IM | LIFE005 | STEP-019,015 | STEP-020,026 | 高 | M2 |
| STEP-026 | SSE 新帖推送（端点 + 到点广播调度） | LIFE002 API | STEP-015,022 | STEP-019~021 | 中 | M2 |
| STEP-029 | 已读上报（评论曝光+Feed 停留） | API+frontend | STEP-021,025 | — | 中 | M2 |
| STEP-006 | 周大纲后台管理 API | admin API | STEP-005 | STEP-008,010,014 | 中 | M3 |
| STEP-008 | 日生活计划后台管理 API | admin API | STEP-007 | STEP-006,010,014 | 中 | M3 |
| STEP-010 | 她的宇宙后台管理 API | admin API | STEP-009 | STEP-006,008,014 | 中 | M3 |
| STEP-014 | 朋友圈后台管理 API | admin API | STEP-013 | STEP-006,008,010 | 中 | M3 |
| STEP-030 | 后台 Tab0 全局人设与词汇表管理 | admin UI | STEP-003 | STEP-032,033,036 | 中 | M3 |
| STEP-031 | 后台生活计划+她的宇宙管理页 | admin UI | STEP-006,010 | STEP-034,035 | 中 | M3 |
| STEP-032 | 后台 Prompt Tab1~4 管理页 | admin UI | STEP-004 | STEP-030,033,036 | 高 | M3 |
| STEP-033 | 后台 Prompt Tab5~6 互动与已读管理页 | admin UI | STEP-004 | STEP-030,032,036 | 中 | M3 |
| STEP-034 | 后台评论管理（10.4） | admin UI | STEP-014,018 | STEP-031,035 | 中 | M3 |
| STEP-035 | 后台点赞/已读感知消息管理（10.8） | admin UI | STEP-020,021 | STEP-031,034 | 中 | M3 |
| STEP-036 | 后台发布时间/可见范围/系统参数 | admin UI | STEP-003 | STEP-030,032,033 | 低 | M3 |
| STEP-038 | 后台生活流菜单入口与路由注册 | admin UI | STEP-030~036 全部 ✅ | — | 低 | M3 |

**依赖修订说明**（相较原文档）：
1. STEP-002 前置由「STEP-001」改为「无」——DeepSeekClient 不依赖任何生活流表，只依赖 `.env` 与 admin_config 现有表；可与 STEP-001 并行
2. STEP-003 前置保留「STEP-001」——需要 `admin_config` 现有表存在（本项目已存在，实际无强依赖，但保留串行以避免混淆）
3. STEP-015 前置改为「STEP-001」——只需表结构，不需 STEP-013 已经产出数据；STEP-015 可与 STEP-005~013 并行
4. STEP-034 前置补「STEP-014」——评论管理页需后台管理 API 路径框架
5. STEP-038 前置改为「STEP-030~036 全部 ✅」——原「STEP-014」不足以支撑菜单指向真实页面

---

## 3. 开发提示词

### [STEP-001] 数据层迁移（生活流全表+扩展字段）

**目标**：建立生活流系统全部数据库表与 ORM 模型，含 users/relationship 扩展字段。

---

**前置条件检查**：无前置条件。

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 11.4 数据存储设计
- `@backend/models/user.py` — users 表现有结构
- `@backend/models/relationship.py` — relationship 表现有结构
- `@backend/models/agent_message.py` — 现有 `trigger_type String(10)` 与 `TriggerType` 常量（STEP-001 须扩展）
- `@backend/models/__init__.py` — 模型注册方式
- `@alembic/versions/v4a_step001_relationship_extend.py` — Alembic 迁移命名与结构惯例参照（本次沿用 `v6a_step001_life_feed_*.py` 命名）

**环境/数据前提**：
- MySQL 8.0 可连接
- 无

---

**需求原文引用**：
> 11.4 数据存储设计：life_plan_outline、life_plan、worldview_snapshot、worldview_event、feed_post、feed_like、feed_comment、agent_aware_queue；users 新增 last_feed_entered_at；relationship 新增 like_aware_special_used_count、read_aware_special_used_count、has_ever_commented_feed。

---

**字段定义**：

| 字段/表 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| life_plan_outline | 表 | 周大纲，plan_date UNIQUE | PRD 11.4 |
| life_plan | 表 | scenes JSON，gen_status | PRD 11.4 |
| worldview_snapshot | 表 | 动态快照 | PRD 11.4 |
| worldview_event | 表 | event_name UNIQUE | PRD 11.4 |
| feed_post | 表 | 含 dedup_hash、image_urls 平铺数组、image_reference_url、image_type | PRD 11.4 |
| feed_like | 表 | uk_user_post | PRD 11.4 |
| feed_comment | 表 | 含 lxm_reply_read_at；**新增 `due_at DATETIME NULL`** 供 LLM-05 延迟轮询消费（本 STEP 补齐） | PRD 11.4 + 本次二选一定案 0.5 |
| agent_aware_queue | 表 | LIKE_AWARE/READ_AWARE | PRD 11.4 |
| users.last_feed_entered_at | DATETIME NULL | [New] 徽标 | PRD 11.4 |
| relationship.like_aware_special_used_count | INT NOT NULL DEFAULT 0 | 点赞特殊档计数 | PRD 11.4 |
| relationship.read_aware_special_used_count | INT NOT NULL DEFAULT 0 | 已读特殊档计数 | PRD 11.4 |
| relationship.has_ever_commented_feed | TINYINT(1) NOT NULL DEFAULT 0 | 全局首次评论标记 | PRD 11.4 |
| agent_message.trigger_type | 由 `String(10)` → `String(16)` | 为 `LIKE_AWARE`/`READ_AWARE` 预留 | PRD 11.4 + 二次审查 |

---

**开发任务**：
1. 在 `backend/models/` 新增上述 8 张表的 SQLAlchemy 模型（每表一个文件），字段与 PRD 11.4 SQL 一致；**表字段注释保留 PRD 11.4 原始 COMMENT 内容**（便于后台 DB 排查）
2. 扩展 `User` / `Relationship` 模型对应列（3 列），字段级 `default=` 与 `nullable` 严格对齐 PRD
3. `feed_comment` 模型比 PRD 11.4 多 **1 列 `due_at DATETIME NULL COMMENT 'LLM-05 计划回复时间；轮询消费用'`**（本次二选一定案，见 §0.5）
4. 编写 Alembic 迁移文件 **`alembic/versions/v6a_step001_life_feed_tables.py`**：
   - `upgrade()` 依次 create_table 8 张表 + alter users/relationship/agent_message
   - `down_revision` 指向当前 head（先运行 `alembic heads` 确认；本仓库 head 目前为 `v5_covers_beijing_date_ai_diary`，可能已变更以最新为准）
   - `downgrade()` 完整可回滚（reverse drop 顺序：aware_queue → feed_* → worldview_* → life_plan_* → 反向 alter）
5. 在 `backend/models/__init__.py` 注册新模型 8 处（Base 元数据可发现）
6. **扩展 `agent_message` 感知 IM 类型**：
   - `TriggerType` 常量类新增 `LIKE_AWARE = "LIKE_AWARE"`、`READ_AWARE = "READ_AWARE"`
   - 将 `agent_message.trigger_type` 由 `String(10)` 扩为 **`String(16)`**（`LIKE_AWARE`/`READ_AWARE` 各 10 字符顶满原字段）
   - 同步更新 `backend/models/agent_message.py` 顶部注释与契约条目草稿

**不在本环节范围内**：
- 业务逻辑、API、定时任务
- 感知 IM 入队与消费逻辑（STEP-019~021）
- Prompt 种子写入（STEP-004）
- `admin_config` 生活流 config_key 写入（STEP-003）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 迁移 upgrade | 空库执行迁移 | 8 表 + 扩展列存在；`agent_message.trigger_type` 长度 16 |
| feed_like 唯一约束 | 同 user_id+post_id 插入两次 | 第二次抛 IntegrityError |
| feed_comment.due_at 允许为 NULL | INSERT 不传 due_at | 落库成功且 due_at IS NULL |
| life_plan_outline.plan_date UNIQUE | 同 plan_date 插入两次 | 第二次抛 IntegrityError |
| worldview_event.event_name UNIQUE | 同 event_name 插入两次 | 第二次抛 IntegrityError |
| relationship 扩展列默认值 | 新用户插入 relationship | 三个新列均为 0 |
| TriggerType 常量 | `TriggerType.LIKE_AWARE == "LIKE_AWARE"` | True |
| downgrade | 执行 downgrade | 8 表全部 drop，agent_message.trigger_type 回退 String(10) |

---

**完成标志**：
- [ ] `alembic upgrade head` 成功，`alembic downgrade -1` 可逆
- [ ] ORM 模型与迁移表结构一致（字段名/类型/nullable/default 全对齐 PRD 11.4）
- [ ] `agent_message.trigger_type` 已扩为 String(16)，`TriggerType` 含 6 项常量（P0–P4 + FUTURE + LIKE_AWARE + READ_AWARE）
- [ ] `feed_comment.due_at` 存在且可为 NULL
- [ ] 单元测试全部通过
- [ ] **契约条目草稿已附交付说明**（8 张新表 + users/relationship/agent_message 扩展）
- [ ] 进度文档 STEP-001 → ✅

---

**契约条目草稿模板（提交时附）**：
```markdown
### STEP-001 · 数据库表结构（M1 草稿）
- 新表：life_plan_outline / life_plan / worldview_snapshot / worldview_event / feed_post / feed_like / feed_comment(含 due_at) / agent_aware_queue
- 扩展：users.last_feed_entered_at；relationship.{like_aware_special_used_count, read_aware_special_used_count, has_ever_commented_feed}
- 变更：agent_message.trigger_type 由 String(10) → String(16)；枚举新增 LIKE_AWARE/READ_AWARE
- 索引：见迁移文件 v6a_step001_life_feed_tables.py
```

---

**完成后执行**：**STEP-002**（可与 STEP-003 并行开工，STEP-003 需先验证 admin_config 现有表存在）。

---

### [STEP-002] DeepSeekClient 与 LLM 节点独立模型配置

**目标**：新建独立于豆包 `LLMClient` 的 `DeepSeekClient`，支持 LLM-01~07 各自后台可配模型版本；API Key/Endpoint 走环境变量。

---

**前置条件检查**：无（可与 STEP-001 并行开工；本 STEP 不依赖生活流新表，只依赖现有 `admin_config` 表）

---

**需要参考的文件**：
- `@backend/utils/llm_client.py` — 参照结构，**不修改**豆包客户端
- `@backend/config.py` — 环境变量读取惯例
- `@docs/design/prompt_spec_v1.2_complete.md` — Q11 模型选型
- `@backend/services/admin_config_service.py` — 配置热加载
- `@backend/services/llm_service.py` — 现有 `llm_stats:{date}` HSET 写入惯例参照

**环境/数据前提**：
- `.env` 新增 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`（见 §0.4 环境变量清单）
- `.env.example` 同步更新示例

---

**需求原文引用**：
> LLM-01~07 均通过新建的 DeepSeekClient 调用，与现有对话主链豆包完全独立；每个节点独立配置模型版本，API Key/Endpoint 走服务器环境变量，不在后台暴露。

---

**字段定义**：

| 字段名 | 类型 | 默认值 | 说明 | 来源 |
|-------|------|--------|------|------|
| `deepseek_model_llm_01` ~ `deepseek_model_llm_07` | admin_config String | `deepseek-v4-pro` | 各节点模型版本，独立可切换 | [自定义] config_key 命名全局统一 |
| `DEEPSEEK_API_KEY` | env | — | 技术凭证 | PRD §9 前言 |
| `DEEPSEEK_BASE_URL` | env | `https://api.deepseek.com` | Endpoint | PRD §9 前言 |

---

**开发任务**：
1. 新建 `backend/utils/deepseek_client.py`：类 `DeepSeekClient`，方法 `chat_sync(messages, model, temperature=0.7, timeout=45)`；HTTP 层用 `httpx.AsyncClient`；**timeout=45s、retry=2 次、指数退避 (2s, 4s)**（2026-07-09 由 15s 上调，对齐豆包默认 45s、适配 deepseek-v4-pro 长输出；与豆包 `llm_client` 互不影响）；捕获 `TimeoutError`/`HTTPStatusError`；重试耗尽抛 `DeepSeekError`
2. 新建 `backend/services/deepseek_llm_service.py`：方法 `call_llm(node_key: str, messages: list, temperature: float = 0.7) -> str`；`node_key ∈ {"llm_01",...,"llm_07"}`；内部按 `deepseek_model_{node_key}` 从 admin_config 读取当前模型版本（走 `admin_config_service.get_active_config`，Redis 缓存 3600s）
3. `backend/config.py` 补 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` 读取；缺失时**启动阶段日志 WARN**（不阻断启动，避免测试环境阻塞）
4. 预留 7 个 `admin_config` 模型配置 key 的**常量声明**放到 `backend/constants.py`（不做数据写入；实际种子写入在 STEP-004）
5. **LLM 统计写入 Redis**（复用现有惯例，参考 `.cursorrules`）：
   - `LPUSH llm_response_times {耗时ms}`（保留最近 1000 条，TTL=2 天）
   - `HINCRBY llm_stats:{date} total 1`
   - 成功时 `HINCRBY llm_stats:{date} success 1`
   - 失败时 `HINCRBY llm_stats:{date} failed 1`

**不在本环节范围内**：
- 各 LLM 业务 Prompt 拼装（各业务 STEP）
- 修改现有 `llm_client.py` 豆包逻辑
- LiblibAI 客户端（STEP-012）
- 内容安全检查（生活流 LLM 各业务 STEP 各自接入 `content_safety_service`）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| mock HTTP 成功 | 合法 messages + model | 返回 content 字符串 |
| 超时重试 | 前 2 次超时，第 3 次成功 | 返回 content；重试计数=2 |
| 完全超时 | 连续 3 次超时 | 抛 DeepSeekError |
| 4xx 不重试 | HTTP 401 | 立即抛错，不重试 |
| 5xx 重试 | 前 2 次 500，第 3 次 200 | 返回 content |
| 模型配置热加载 | 切换 `deepseek_model_llm_04` 的 admin_config 生效版本 | 下次调用使用新模型名 |
| Redis 统计 | 一次成功调用 | `llm_stats:{today}` 的 total 与 success 各 +1 |

---

**完成标志**：
- [ ] `DeepSeekClient` 可独立调用（本地 curl 验证或 pytest mock）
- [ ] `.env` 缺失时启动不崩溃，仅 WARN
- [ ] 7 个 `deepseek_model_llm_XX` 常量已声明
- [ ] `llm_stats:{date}` 与 `llm_response_times` 正常写入
- [ ] 不改动豆包 `llm_client.py`
- [ ] **契约条目草稿**已附交付说明（DeepSeek 配置项 + 环境变量 + Redis 统计 key）
- [ ] STEP-002 → ✅

---

**完成后执行**：**STEP-003**（若 STEP-001 已完成）；本 STEP 与 STEP-001 可完全并行。

---

### [STEP-003] 生活流全局 admin_config 配置项与热加载

**目标**：落地第零章全局配置项（除 persona 复用外），支持 Redis `active_config:{key}` 热加载。

---

**前置条件检查**：STEP-001 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 第零章、9.0、9.4 映射表
- `@backend/services/admin_config_service.py`
- `@backend/models/admin_config.py`

**环境/数据前提**：STEP-001 完成

---

**需求原文引用**：
> lxm_likes/lxm_dislikes/lxm_writing_style/lxm_content_limits、categories_vocab、emotion_vocab；图片映射表 venue_type_img_keyword、category_img_keyword、emotion_img_keyword、emotion_atmosphere_desc、emotion_fallback_*；feed_text_similarity_threshold 默认 0.75；主场城市 home_city；生活节奏比例；点赞/已读特殊档参数（9.5/9.6）。
>
> 10.7 发布频率配置（每日 2/3 条概率）；UI 规范第六章朋友圈 Header 角色展示（背景图/头像/昵称/签名）。

---

**开发任务**：
1. 新建 `backend/constants/life_feed_config.py`（或在 `backend/constants.py` 追加）：定义全部 `config_key` 常量，命名一律 **snake_case + 生活流前缀**（如 `feed_*` / `lxm_*` / `like_aware_*` / `read_aware_*` / `emotion_*` / `venue_*` / `category_*`）
2. 实现读取辅助函数 `get_life_feed_config(key: str, default: Any) -> Any`（走 `admin_config_service.get_active_config`，命中 Redis 缓存 TTL=3600s）
3. 编写**初始化脚本** `backend/scripts/seed_life_feed_config.py`：幂等写入默认值（存在则跳过）
   - `categories_vocab`（10 项，PRD 0.3）
   - `emotion_vocab`（14 项，PRD 0.4）
   - `lxm_likes` / `lxm_dislikes` / `lxm_writing_style` / `lxm_content_limits`（PRD 0.2 默认值）
   - `home_city = "杭州"`
   - `feed_text_similarity_threshold = 0.75`
4. **互动特殊档参数**（PRD 9.5/9.6）：
   - `like_aware_special_window_hours = 48`
   - `like_aware_special_max_count = 1`
   - `like_aware_special_delay_sec = 30`
   - `read_aware_special_window_hours = 48`
   - `read_aware_special_max_count = 1`
   - `read_aware_special_delay_sec = 60`
   - `read_suppress_after_like_im_hours = 6`
5. **关系档延迟配置**（PRD 6.3；min/max 各阶段独立）：
   - 评论回复 `comment_reply_delay_{stage}_min/max`（stage ∈ stranger/friend/intimate/soulmate）
   - 点赞常规档 `like_regular_delay_{stage}_min/max`
   - 已读常规档 `read_regular_delay_{stage}_min/max`
   - **单位统一为秒**（避免 min/max 单位混淆），写入常量文件顶端注释
6. **发布频率**：`feed_daily_post_count_2_weight = 50` / `feed_daily_post_count_3_weight = 50`（PRD 4.2.1）
7. **图片张数分布（PRD 4.4.1）**：`feed_image_count_0_weight=30` / `_1_weight=35` / `_2_3_weight=25` / `_4_weight=10`（供 STEP-012 按帖抽签 0–4 张；2-3 张再等概率二拆一）
8. **图片类型权重（PRD 4.4.2）**：`feed_image_type_selfie_weight=40` / `_daily_weight=30` / `_scenery_weight=20` / `_emotion_weight=10`
9. **朋友圈页 Header 展示** [自定义]：
   - `feed_page_header_bg_url`（默认走 `/static/images/feed/bg_default.jpg` 或占位；无则前端兜底纯色）
   - `feed_page_header_avatar_url`（**默认读取现有 persona 头像**，见 STEP-030 明确回落链）
   - `feed_page_signature`（默认「今天也要好好生活呀~」，PRD 无原文，[自定义]）
   - `feed_page_display_nickname`（默认「林小梦」，只读）
10. **发布窗口时间**（PRD 10.5）：`feed_publish_window_1 = "10:00-12:00"` / `_2 = "15:00-20:00"` / `_3 = "20:00-23:00"`
11. **历史可见范围**（PRD 10.6）：`feed_history_visible_range` 枚举值 `7d|30d|180d|all`，默认 `all`
12. **南半球城市白名单**（PRD 10.7#4）：`southern_hemisphere_cities` = JSON 数组（初始含悉尼/墨尔本/布里斯班/珀斯/奥克兰/惠灵顿/开普敦/布宜诺斯艾利斯/圣地亚哥）
13. **点赞倍率范围**（PRD 10.7#2）：`feed_base_likes_min=1` / `_max=8` / `feed_like_multiplier_min=1` / `_max=3`
14. **`admin_config` 草稿机制遵守**：初始化脚本写入时 `is_draft=False, is_active=True`（种子直接生效，不走三道卡点；后续 STEP-030~036 修改配置必须走草稿→测试集→CONFIRM→5min 监控流程）
15. **关系档字符串常量**（供 STEP-018 / 019 / 020 / 021 共用，避免各处硬编码）：
    ```python
    # backend/constants/life_feed_config.py
    RELATIONSHIP_STAGE_MAP = {0: "stranger", 1: "friend", 2: "intimate", 3: "soulmate"}
    RELATIONSHIP_STAGE_ZH = {"stranger": "陌生", "friend": "朋友", "intimate": "亲密", "soulmate": "知己"}
    def level_to_stage(level: int) -> str: ...
    ```
    ⚠️ 该映射为**全生活流唯一来源**，STEP-018/019/020/021 必须复用，不允许在 service 层重造

**不在本环节范围内**：
- 后台 UI（STEP-030/032/033/036）
- Prompt 全文种子（STEP-004）
- 映射表值（`venue_type_img_keyword` 等 4 张图像关键词映射表由 STEP-004 与 Prompt 一同种子化）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 种子脚本幂等 | 二次执行 | 不产生重复行，DB 无异常 |
| Redis 缓存 | 修改 admin_config 后 SELECT | 3600s 内命中旧值，`invalidate_cache` 后取新值 |
| `level_to_stage(2)` | 输入 2 | 返回 `"intimate"` |
| `get_life_feed_config` 命中默认值 | key 不存在 | 返回传入的 default |

---

**完成标志**：
- [ ] 全部 config_key 常量已声明并可读
- [ ] 种子脚本幂等且默认值与 PRD 一致
- [ ] Redis 缓存 TTL=3600s
- [ ] `RELATIONSHIP_STAGE_MAP` 已定义并对外导出
- [ ] **契约条目草稿**已附交付说明（admin_config 全清单）
- [ ] STEP-003 → ✅

---

**完成后执行**：**STEP-004**

---

### [STEP-004] Prompt 模板初始种子（P-01~P-14）

**目标**：将《提示词规格文档》全文作为 admin_config **生效**种子写入，支持后续按 config_key 分别管理 P-01-S / P-01-U / P-12-pos/neg / P-13a-pos/neg / ... ；实现 `life_prompt_service.render_prompt` 统一模板渲染入口。

---

**前置条件检查**：STEP-003 ✅

---

**需要参考的文件**：
- `@docs/design/prompt_spec_v1.2_complete.md` — 第五节全文（P-01 ~ P-14 完整正文）
- `@backend/routers/admin/prompt_mgmt.py` — 现有 Prompt 发布流程参照
- `@backend/services/prompt_builder.py` — 现有对话主链 Prompt 渲染惯例参照（**只读参照，不修改**）
- `@backend/services/admin_config_service.py` — 配置写入接口

---

**需求原文引用**：
> 所有涉及 LLM 生成的环节均在后台提供独立 Prompt 配置项；P-04 含可选段标记解析；P-05 A/B/C/D 四阶段独立配置。

---

**config_key 映射表**（本 STEP 落地全部 Prompt config_key）：

| 模板 | config_key（System / User / 变体） | 说明 |
|------|---------------------------------|------|
| P-01 | `prompt_p01_system` / `prompt_p01_user` | LLM-01 周大纲，含 `{{days_count}}` |
| P-02 | `prompt_p02_system` / `prompt_p02_user` | LLM-02 日场景 |
| P-03 | `prompt_p03_system` / `prompt_p03_user` | LLM-03 她的宇宙 |
| P-04 | `prompt_p04_system` / `prompt_p04_user` | LLM-04 文案生成，含 `[可选段·快照]` `[可选段·旅游]` 两处可选段 |
| P-05 | `prompt_p05_departure` / `prompt_p05_transit` / `prompt_p05_return` / `prompt_p05_oneday` | LLM-04 旅游叙事四阶段 |
| P-06 | `prompt_p06_system` / `prompt_p06_user` | LLM-05 评论回复（v1 简单回复，含 `[可选段·记忆]` 但 v1 恒为空） |
| P-07 | `prompt_p07_system` / `prompt_p07_user` | LLM-06 点赞感知（特殊档与常规档共用同一 Prompt） |
| P-08 ~ P-11 | `prompt_p08_system` ~ `prompt_p11_system` + 各自 `_user` | LLM-07 已读常规四档（陌生/朋友/亲密/知己） |
| P-12 | `prompt_p12_pos` / `prompt_p12_neg` | 图像 IMG1 人物图正/负向提示词 |
| P-13a | `prompt_p13a_pos` / `prompt_p13a_neg` | 日常图（Star-3 Alpha） |
| P-13b | `prompt_p13b_pos` / `prompt_p13b_neg` | 风景图 |
| P-13c | `prompt_p13c_pos` / `prompt_p13c_neg` | 情绪图 |
| P-14 | `prompt_p14_system` / `prompt_p14_user` | LLM-07 已读特殊档（帖文相关，好接话） |

**图像关键词映射表 config_key**（本 STEP 一并种子化）：

| config_key | 类型 | 说明 |
|-----------|------|------|
| `venue_type_img_keyword` | JSON dict | venue_type → 英文关键词（不完整，由 category 兜底） |
| `category_img_keyword` | JSON dict | category → 英文关键词（100% 覆盖 10 项） |
| `emotion_img_keyword` | JSON dict | emotion → 人物图表情/状态关键词（覆盖 14 核心词） |
| `emotion_atmosphere_desc` | JSON dict | emotion → 情绪图氛围描述词（覆盖 14 核心词） |
| `emotion_fallback_img_keyword` | JSON list | 未命中兜底关键词组 |
| `emotion_fallback_atmosphere_desc` | JSON list | 未命中兜底氛围描述组 |

---

**开发任务**：
1. 新建 `backend/services/life_prompt_service.py`，提供：
   ```python
   def render_prompt(template_key: str, variables: dict, optional_segments: dict[str, bool] | None = None) -> str
   ```
   - `variables` 通过 `{{var_name}}` 占位符替换（简单字符串替换，非 Jinja2）
   - `optional_segments` 控制 `[可选段·xxx]...[/可选段]` 是否保留；`True` 保留段内内容（去除标记），`False` 整段删除
   - 未提供的可选段默认 `False`（删除）
   - 支持嵌套变量替换（先展开可选段，再替换变量）
2. 新建 `backend/scripts/seed_life_feed_prompts.py`：**幂等**写入全部 P-01~P-14 与图像映射表默认值到 `admin_config`
   - 每条配置：`config_key`（上表）、`config_value`（正文 / JSON 字符串）、`is_draft=False`、`is_active=True`、`version=1`
   - 已存在则跳过（不覆盖，避免误清空运营手改的内容）
3. `render_prompt` 内 **`{{lxm_base_persona}}` 变量特殊处理**：不从 `variables` 取，而是从 `active_config:persona`（现有 IM 系统的 persona 配置）读取，避免同一角色人设在两处维护
4. **变量白名单校验**：`render_prompt` 结束后检查是否还有未替换的 `{{...}}`，若有则 raise `PromptRenderError`（防止 vibe coding 漏传变量）

**不在本环节范围内**：
- 后台 Tab UI（STEP-032/033）
- 实际 LLM 调用（各业务 STEP）
- Prompt A/B 测试机制（未来功能）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 简单变量替换 | `"你好 {{name}}"`, `{"name": "小梦"}` | `"你好 小梦"` |
| 可选段保留 | `"a[可选段·记忆]b[/可选段]c"`, `optional_segments={"记忆": True}` | `"abc"` |
| 可选段删除 | 同上，`{"记忆": False}` | `"ac"` |
| persona 注入 | Prompt 含 `{{lxm_base_persona}}` | 从 active_config:persona 读取并注入 |
| 变量遗漏 | Prompt 剩余 `{{unknown}}` | 抛 PromptRenderError |
| 种子幂等 | 二次执行 seed 脚本 | 不产生重复；不覆盖已存在 config_key |

---

**完成标志**：
- [ ] 所有 P-01~P-14 与 6 张映射表 config_key 已写入 admin_config
- [ ] `render_prompt` 支持变量替换 + 可选段解析 + persona 特殊处理 + 遗漏校验
- [ ] 种子脚本幂等
- [ ] **契约条目草稿**已附交付说明（Prompt config_key 全清单）
- [ ] STEP-004 → ✅

---

**完成后执行**：**STEP-005**（上游生成链起点）

---

### [STEP-005] LLM-01 周大纲自动定时任务

**目标**：每周日 23:00 生成下一自然周大纲（LLM-01），失败 23:30 重试；落库 life_plan_outline；软约束生活比例。

---

**前置条件检查**：STEP-002、003、004 均 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 2.2 全文
- `@docs/design/prompt_spec_v1.2_complete.md` — P-01
- `@backend/tasks/scheduler.py` — 定时任务注册惯例
- `@backend/tasks/ai_diary_task.py` — 任务结构参照

**需求原文引用**：
> 每周日 23:00 触发 days_count=7；23:30 重试；categories 必须从 categories_vocab 选取；长途旅游同一自然周内收尾；本月累计本地/短途/长途天数软约束注入。

---

**开发任务**：
1. 新建 `backend/services/life_planner_service.py`，方法 `generate_week_outline(days_count: int, week_start_date: date, is_manual: bool = False) -> dict`：
   - 调用 `life_prompt_service.render_prompt("prompt_p01_system", ...)` 与 `..._user`；变量含 `days_count / week_start_date / week_end_date / home_city / current_month / month_local_days / month_short_trip_days / month_long_trip_days / categories_vocab`（categories_vocab 拼接为逗号分隔字符串）
   - 走 `deepseek_llm_service.call_llm("llm_01", messages)`
   - JSON 解析：**LLM 输出可能带 markdown 代码块，需先剥离**（正则 `^```json\s*|\s*```$`）
2. **JSON 校验**（应用层）：
   - 条数 == `days_count`
   - 每条含 `date`（YYYY-MM-DD）、`city`（非空）、`categories`（非空字符串，多个用 `\n` 分隔）
   - `categories` 拆分后每项在当前 `categories_vocab` 列表内
   - 校验失败视同技术失败，重试
3. 按自然日落库 `life_plan_outline`，`gen_status='auto'`（手动补录时 `is_manual=True`，落库 `gen_status='manual'`）
4. 统计当月 home_city/短途/长途天数（自然月边界，跨周按日分摊；PRD 2.2.4）
5. `backend/tasks/life_feed_task.py` 注册 APScheduler cron：
   - `weekly_outline_task`：周日 23:00 (Asia/Shanghai)
   - `weekly_outline_retry_task`：周日 23:30（仅当 23:00 失败时执行；实现方式：任务开始先查是否已有本次 `week_start_date` 的落库，有则 skip）
6. **系统日志**（见 §0.1）：触发（INFO）、成功（INFO 含条数）、单次失败（WARN 含失败原因）、最终失败（ERROR）、跳过（INFO 已有落库）

**不在本环节范围内**：
- 后台手动生成 API（STEP-006）
- LLM-02（STEP-007）
- 生活比例硬性约束（PRD 明确为软约束，仅注入参考数值）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| Mock LLM 正常返回 | days_count=7 | 7 条落库 |
| LLM 返回条数不符 | 返回 6 条 | 校验失败，重试；仍失败标记 ERROR |
| categories 词表外 | 返回含"XX" | 校验失败重试 |
| 已有落库 | 该周已生成过 | 跳过并记日志 |
| markdown 代码块剥离 | LLM 返回 ` ```json ... ``` ` | 正确解析 |

---

**完成标志**：
- [ ] scheduler 已注册两个 cron
- [ ] 手动触发（`python -m backend.tasks.life_feed_task weekly_outline_task`）可跑通
- [ ] 落库、系统日志均符合 PRD
- [ ] **契约条目草稿**已附交付说明（scheduler cron key）
- [ ] STEP-005 → ✅

---

**完成后执行**：**STEP-007**（本里程碑 M1 内 STEP-006 在 M3 处理）

---

### [STEP-006] 周大纲后台管理 API

**目标**：10.1 周大纲管理：查看、单日 CRUD、条件满足时一键生成剩余自然日；主场城市/生活节奏比例读写。

---

**前置条件检查**：STEP-005 ✅（需要 `life_planner_service.generate_week_outline` 可复用于手动生成）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 2.2.5、10.1
- `@backend/routers/admin/` — 路由与 RBAC 惯例（参照 `admin_diary_query.py` 等现有 admin 路由）
- `@backend/services/auth_service.py` — RBAC 检查中间件
- `@backend/services/admin_config_service.py` — 读写 `home_city`

**API 清单**：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/life-plan/outline?week_start_date=YYYY-MM-DD` | ai_trainer+ | 查询某周大纲全 7 天 |
| GET | `/api/admin/life-plan/outline?plan_date=YYYY-MM-DD` | ai_trainer+ | 查询单日 |
| POST | `/api/admin/life-plan/outline` | ai_trainer+ | 新增单日条目（body: {plan_date, city, categories}）；已存在返回 409 |
| PUT | `/api/admin/life-plan/outline/{plan_date}` | ai_trainer+ | 编辑单日 |
| DELETE | `/api/admin/life-plan/outline/{plan_date}` | ai_trainer+ | 删除单日 |
| POST | `/api/admin/life-plan/outline/generate` | ai_trainer+ | 一键生成剩余自然日（body: {week_start_date, days_count?}），仅当剩余日零落库时可用 |
| GET | `/api/admin/life-plan/settings` | ai_trainer+ | 读取 home_city + 本地/短途/长途比例参考值 |
| PUT | `/api/admin/life-plan/settings` | ai_trainer+ | 写入（走 admin_config 草稿流程） |

**开发任务**：
1. 按上表实现 8 个端点
2. `categories` 选择器校验：POST/PUT 时 categories 拆分后每项须在 `categories_vocab` 内，否则 400
3. `generate` 接口内部调 `life_planner_service.generate_week_outline(..., is_manual=True)`；返回生成结果同步等待（不用异步任务）；若"今天及以后剩余日"已有 ≥1 天落库则返回 409 + 错误码 `OUTLINE_ALREADY_EXISTS`
4. **10.1#4 主场城市与生活节奏**：`settings` 接口读写 `home_city` / `life_ratio_local` / `life_ratio_short_trip` / `life_ratio_long_trip`（后 3 项默认 70/20/10）；PUT 走 admin_config 草稿 → 三道卡点
5. RBAC 与 JWT 见 §0.2；所有写操作落 `operation_log`

**不在本环节范围内**：
- 管理后台页面（STEP-031）
- 日计划场景 CRUD（STEP-008）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 查询空周 | week_start_date 无数据 | 200 空数组 |
| POST categories 非法 | categories="外星探索" | 400 |
| generate 已有部分落库 | 剩余日已有 1 天 | 409 `OUTLINE_ALREADY_EXISTS` |
| DELETE 后 generate | DELETE 全周后 | 可生成成功 |
| PUT settings 走草稿 | 修改 home_city | admin_config draft 创建，不立即生效 |

---

**完成标志**：
- [ ] 8 个 API 均可通过 curl 测试
- [ ] RBAC 校验生效（非 ai_trainer 返回 403）
- [ ] 操作日志已落库
- [ ] **契约条目草稿**已附交付说明（API 路径 / 请求响应 / 错误码）
- [ ] STEP-006 → ✅

---

### [STEP-007] LLM-02 日场景定时任务

**目标**：每日 00:20 为次日生成 2~5 场景；无大纲则跳过；<2 场景则 00:30 重试。

---

**前置条件检查**：STEP-005 ✅（需要 `life_plan_outline` 表有数据；测试环境可手动种一条）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 2.3
- `@docs/design/prompt_spec_v1.2_complete.md` — P-02
- `@backend/services/life_planner_service.py`（STEP-005 已建）

---

**开发任务**：
1. 在 `life_planner_service.py` 追加方法 `generate_daily_scenes(plan_date: date) -> dict`：
   - 读取 `life_plan_outline` 对应日；不存在则日志 INFO 并 return skip
   - `life_prompt_service.render_prompt("prompt_p02_system"/"prompt_p02_user", {date, outline_city, outline_categories, lxm_likes, lxm_dislikes})`
   - `deepseek_llm_service.call_llm("llm_02", messages)`
   - JSON 解析（同 STEP-005 剥离 markdown）
2. **JSON 校验**：
   - `scenes` 数组长度 ∈ [2, 5]
   - 每个 scene 含 `time_range`（`HH:MM-HH:MM` 格式，两端在 06:00–20:00 内）
   - `city == outline_city`（强约束）
   - `category ∈ outline_categories`（强约束）
   - `venue_type` 非空字符串（自由发挥）
   - `description` 长度 ≥ 200 字符
3. **scene_id 生成规则**（本次二选一定案，见 §0.5）：`scene_{plan_date}_{seq:03d}`，seq 从 001 起编号且当日单调递增（`scene_2026-06-01_001`, `scene_2026-06-01_002`, ...）
4. 写入 `life_plan.scenes`（JSON 数组），`gen_status='ready'`；场景数 < 2 或校验失败标 `failed`
5. scheduler cron：00:20 / 00:30（Asia/Shanghai）；00:30 只在 00:20 失败时执行（先查 gen_status，非 ready 才跑）
6. 关键节点写入系统日志（PRD 2.3.1）：任务触发（INFO）、outline 检查（INFO）、跳过（INFO）、成功（INFO 含场景数）、单次失败（WARN）、最终失败（ERROR）、重试（WARN）

**不在本环节范围内**：
- 后台手动生成 API（STEP-008）
- 场景 CRUD（STEP-008）
- 她的宇宙 LLM-03（STEP-009）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 无大纲 | outline 不存在 | 跳过并记 INFO 日志 |
| 场景数<2 | LLM 返回 1 条 | gen_status=failed，00:30 重试 |
| city 不符 | LLM 返回 city='上海'，outline='杭州' | 校验失败重试 |
| time_range 越界 | 返回 "05:00-06:00" | 校验失败重试 |
| scene_id 编号 | 生成 3 条 | scene_id 001/002/003 |
| 已 ready 时二次执行 | gen_status='ready' | 跳过 |

---

**完成标志**：
- [ ] scheduler 已注册；手动触发可跑通
- [ ] scene_id 命名符合 §0.5 定案
- [ ] 场景数<2 时不发布下游（gen_status=failed）
- [ ] 系统日志可见
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-007 → ✅

---

### [STEP-008] 日生活计划后台管理 API

**目标**：10.1 日计划查看 / 场景 CRUD / 手动触发 LLM-02 生成 / 手动补录场景（10.1#8）。

---

**前置条件检查**：STEP-007 ✅（复用 `generate_daily_scenes`）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 2.3、10.1
- `@backend/services/life_planner_service.py`（STEP-007）
- `@backend/routers/admin/` — 路由与 RBAC 惯例

**API 清单**：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/life-plan/daily?plan_date=YYYY-MM-DD` | ai_trainer+ | 查询某日 life_plan（含 scenes JSON、gen_status） |
| GET | `/api/admin/life-plan/daily?start=YYYY-MM-DD&end=YYYY-MM-DD` | ai_trainer+ | 范围查询（分页） |
| POST | `/api/admin/life-plan/daily/{plan_date}/generate` | ai_trainer+ | 手动触发 LLM-02 生成 |
| POST | `/api/admin/life-plan/daily/{plan_date}/scenes` | ai_trainer+ | 手动新增一条 scene（body: {time_range, city, category, venue_type, description}）|
| PUT | `/api/admin/life-plan/daily/{plan_date}/scenes/{scene_id}` | ai_trainer+ | 编辑单条 scene |
| DELETE | `/api/admin/life-plan/daily/{plan_date}/scenes/{scene_id}` | ai_trainer+ | 删除单条 scene |

**开发任务**：
1. 按上表实现 6 个端点
2. `generate` 接口内部调 `life_planner_service.generate_daily_scenes(plan_date)`；同步等待；若 outline 缺失返回 409 `OUTLINE_MISSING`
3. **手动新增 scene**（10.1#8）：
   - scene_id 沿用 §0.5 定案，取当日最大 seq + 1
   - `category` 必须在当日 outline 的 `categories` 内（保持强约束）
   - 追加后若 life_plan.gen_status='failed' 且 scenes 数 ≥ 2，**自动升级为 ready**（打开下游发布链路）
4. **手动编辑/删除 scene**：直接改 life_plan.scenes JSON；scenes 数降至 <2 时 gen_status 保持不变（**不主动降级为 failed**，避免误操作破坏已发布）
5. 展示 gen_status 与 LLM 日志摘要（读取 system_log 表按 scene_id 过滤）
6. RBAC + operation_log 全覆盖

**不在本环节范围内**：
- 管理后台页面（STEP-031）
- 她的宇宙（STEP-010）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 查询无数据 | plan_date 不存在 | 404 |
| 手动 generate 无 outline | outline 不存在 | 409 |
| 手动新增 category 不合规 | category 不在 outline.categories | 400 |
| 追加至 2 条自动升级 | failed → 追加一条 → 现 2 条 | gen_status=ready |
| 删除 scene | 存在 scene_id | 200，scenes 数组少 1 |

---

**完成标志**：
- [ ] 6 API 可 curl 测试
- [ ] scene_id 编号严格递增，无重复
- [ ] operation_log 覆盖所有写操作
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-008 → ✅

---

### [STEP-009] LLM-03 她的宇宙定时任务

**目标**：00:45 遍历当日 ready 场景，每 scene 一次 LLM-03；快照入库 + worldview_event INSERT IGNORE。

---

**前置条件检查**：STEP-007、004 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 3.2、3.3
- `@docs/design/prompt_spec_v1.2_complete.md` — P-03

---

**开发任务**：
1. 新建 `backend/services/her_universe_service.py`：
   - `generate_for_scene(scene: dict, plan_date: date) -> tuple[Snapshot, Event | None]`
   - **单次调用超时 45s**、**立即重试最多 3 次**（含首次；共最多 3 次尝试）
   - 变量：`{scene_description, scene_venue_type, scene_category, scene_city, emotion_vocab, lxm_base_persona}`
   - 输出 schema 校验（缺失即视为内容失败重试）：
     - 快照必填：`feeling_text` / `emotion_value` / `focus_tag` / `worldview_trigger`
     - 事件必填：`event_name`（描述性短语 ≥ 10 字符）/ `event_view`（100–200 字）/ `core_attitude ∈ {"喜欢","排斥","矛盾","无感"}`
2. 主任务 `daily_her_universe_task(plan_date: date)`：
   - 查 `life_plan.gen_status = 'ready'`；无则整任务 skip
   - 遍历 scenes，**串行**处理（避免 DeepSeek 并发过高；本项目单机 QPS 低）
   - 单条 failed 不阻断其余
3. 快照写入：`worldview_snapshot` 按 `scene_id` upsert（存在则更新，本地不生成重复）
4. 事件写入：`worldview_event` INSERT ON DUPLICATE KEY UPDATE（`event_name` UNIQUE，已存在跳过；不覆盖首次版本）
5. scheduler cron：**00:45 每日**（Asia/Shanghai）；无独立重试 cron（单条内 3 次立即重试）
6. 系统日志（PRD 3.2.5）：任务触发（INFO）、ready 检查（INFO scene 数）、单条开始（INFO scene_id）、单条成功（INFO scene_id/耗时/尝试次数）、单条中途失败（WARN 失败类型/当前次数）、单条最终失败（ERROR scene_id）、event 写入（INFO event_name / 操作结果 新增/跳过）、整体完成（INFO 成功/失败数）

**不在本环节范围内**：
- 后台管理页（STEP-010）
- LLM-04 文案（STEP-011）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 无 ready 计划 | life_plan 不存在或 failed | 任务 skip |
| 3 场景全成功 | mock LLM 三次 | 3 快照 + 3 事件（若 name 不重） |
| 单条 3 次失败 | mock LLM 全超时 | 该 snapshot=failed，其余正常 |
| event_name 已存在 | 第二次遇到同名 | INSERT IGNORE，跳过 |
| core_attitude 非法 | 返回 "喜爱" | 校验失败重试 |

---

**完成标志**：
- [ ] 单条失败不阻断整体
- [ ] event_name UNIQUE 生效
- [ ] 系统日志按 scene_id 可查
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-009 → ✅

---

### [STEP-010] 她的宇宙后台管理 API

**目标**：10.2 快照与事件库 CRUD；emotion_value 可选 vocab 或自由输入；核心态度四选项。

---

**前置条件检查**：STEP-009 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 3.2、3.3、10.2
- `@backend/services/her_universe_service.py`（STEP-009）

**API 清单**：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/worldview/snapshots?plan_date=YYYY-MM-DD` | ai_trainer+ | 按日查快照列表 |
| GET | `/api/admin/worldview/snapshots/{id}` | ai_trainer+ | 快照详情 |
| PUT | `/api/admin/worldview/snapshots/{id}` | ai_trainer+ | 编辑快照（emotion_value/focus_tag/worldview_trigger/feeling_text） |
| DELETE | `/api/admin/worldview/snapshots/{id}` | ai_trainer+ | 删除单条快照 |
| GET | `/api/admin/worldview/events?keyword=xxx&page=&size=` | ai_trainer+ | 事件库列表（分页 + 关键词 event_name 模糊） |
| POST | `/api/admin/worldview/events` | ai_trainer+ | 新增事件（含 core_attitude 四选项）|
| PUT | `/api/admin/worldview/events/{id}` | ai_trainer+ | 编辑（允许覆盖，管理员权威）|
| DELETE | `/api/admin/worldview/events/{id}` | ai_trainer+ | 删除 |

**开发任务**：
1. 按上表 8 端点
2. `emotion_value` 编辑校验：允许 `emotion_vocab` 内取值 **或** 自由字符串（保留自由兜底能力，PRD 10.2#4）
3. `core_attitude` 严格枚举：喜欢/排斥/矛盾/无感（PRD 3.3.2）
4. 事件库列表响应含 `source_scene_id / created_at / updated_at`（10.2 追溯需求）
5. RBAC + operation_log 全覆盖；PUT/DELETE 快照时若对应 feed_post 已生成，仅记 WARN 不阻断

**不在本环节范围内**：
- 管理后台页面（STEP-031）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| emotion_value 自由词 | 输入"温柔" | 允许（不校验 vocab） |
| core_attitude 非法 | "喜爱" | 400 |
| 事件模糊查询 | keyword="景区" | 返回 event_name 含"景区"的记录 |
| DELETE 已被引用的快照 | feed_post 已用 | 200 + 记 WARN |

---

**完成标志**：
- [ ] 8 API 可测；enum 校验生效；operation_log 覆盖
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-010 → ✅

---

### [STEP-011] LLM-04 文案生成（去重/相似度/旅游叙事）

**目标**：实现单条朋友圈文案生成核心逻辑（不含图片、不含定时发布整合），含结构化去重、文本相似度过滤、旅游叙事阶段判断、emotion 双路径写入。

---

**前置条件检查**：STEP-009、004 ✅（需要快照数据 + Prompt 模板）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 4.3~4.6
- `@docs/design/prompt_spec_v1.2_complete.md` — P-04、P-05
- `@backend/services/life_prompt_service.py`（STEP-004）
- `@backend/services/deepseek_llm_service.py`（STEP-002）

---

**开发任务**：
1. 新建 `backend/services/feed_content_service.py`：
   - `generate_post_text(scene: dict, snapshot: Snapshot | None, plan_date: date) -> PostDraft`
   - `PostDraft` = `{post_text, hashtags: list[str], emotion: str}`

2. **emotion 双路径**（PRD 4.3.2）：
   - `snapshot is not None and snapshot.gen_status == 'ready'` → `emotion = snapshot.emotion_value`；Prompt 走 `optional_segments={"快照": True}`，输出 schema `{post_text, hashtags}`
   - 否则（None 或 failed 或 generating）→ Prompt 走 `optional_segments={"快照": False}`，输出 schema `{post_text, hashtags, emotion}`；emotion 从 LLM 输出取

3. **结构化去重**（PRD 4.5.1，本 STEP 明确算法）：
   - `dedup_hash = md5(f"{venue_type}|{category}|{city}".encode("utf-8")).hexdigest()`（**用 `|` 分隔避免歧义**；UTF-8 编码固定；实现放 `backend/utils/hash_utils.py`）
   - 查询 `feed_post` 表 7 天窗口内是否已存在同 `dedup_hash` 且 `generation_status='ready'` 或 `scheduled_publish_time` 未来的记录
   - 命中 → 抛 `DedupHitException(scene_id, hit_post_id)`；调用方（STEP-013）捕获后跳过该 scene

4. **文本相似度**（PRD 4.5.2，本 STEP 明确算法）：
   - 生成成功后，取近 7 天 `feed_post.content_text` 全部记录
   - 采用 **Jaccard 系数（bi-gram 字符）** 计算：
     ```python
     def bi_gram_set(text: str) -> set[str]:
         text = re.sub(r"\s+", "", text)
         return {text[i:i+2] for i in range(len(text)-1)}
     def jaccard(a: str, b: str) -> float:
         sa, sb = bi_gram_set(a), bi_gram_set(b)
         return len(sa & sb) / max(len(sa | sb), 1)
     ```
   - 与任一历史文案相似度 ≥ `feed_text_similarity_threshold`（默认 0.75）→ 抛 `SimilarityHitException(scene_id, hit_post_id, score)`
   - 命中不重试；调用方（STEP-013）跳过该 scene

5. **旅游叙事**（PRD 4.6）：
   - 判定阶段：读取本周 outline 的城市序列 + `home_city`，按 PRD 4.6 判断表返回 `travel_stage ∈ {"departure","transit","return","oneday", None}`
   - 若非 None，`optional_segments={"旅游": True}`，注入变量 `{week_city_sequence, travel_day_index, travel_stage_prompt_key}`（后者对应 `prompt_p05_departure` / `_transit` / `_return` / `_oneday`）
   - 主场城市：从 admin_config `home_city` 读取

6. **hashtags 概率分布**：读取 admin_config（STEP-003 已备 config_key，若无则用默认 50/30/10/10）；抽签决定期望 hashtags 数量作为 Prompt 提示；实际 LLM 输出以其为准（不强制截断）

7. **内容安全**（[自定义·项目惯例]）：`post_text` 生成后，调 `content_safety_service.check(text)`；违规 → 抛 `ContentSafetyException`，调用方跳过

8. `PostDraft` 与生成日志一并返回上层，本 STEP **不落库**（落库由 STEP-013 负责）

**不在本环节范围内**：
- 图片生成（STEP-012）
- 01:00 定时任务（STEP-013）
- 后台管理 API（STEP-014）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 快照 ready | emotion_value="慵懒" | 生成结果 emotion="慵懒"（直接复制） |
| 快照 failed | snapshot.gen_status='failed' | LLM 输出 emotion 字段 |
| dedup 命中 | 同 venue+cat+city 已存在 | DedupHitException |
| 相似度 0.8 | 与历史文案 Jaccard=0.8 | SimilarityHitException |
| 主场城市 | city='杭州', home_city='杭州' | 不注入旅游段 |
| 返程日 | 昨日苏州/今日苏州/明日杭州 | travel_stage='return'，注入 P-05-return |
| 内容安全违规 | 违规文本 | ContentSafetyException |
| hashtags 抽签 0 | 权重 100/0/0/0 | LLM Prompt 提示"不生成话题" |

---

**完成标志**：
- [ ] emotion 双路径覆盖测试通过
- [ ] dedup_hash 算法与 STEP-001 表字段一致
- [ ] 相似度算法可切换阈值
- [ ] 旅游叙事判断表全 4 分支已测
- [ ] 内容安全接入
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-011 → ✅

---

### [STEP-012] LiblibAI 客户端与图片生成服务

**目标**：IMG1 人物图 + Star-3 Alpha 非人物图；关键词映射与兜底；WebP 压缩；OSS 上传；临时文件即时清理；LiblibAI 调用统计。

---

**前置条件检查**：STEP-003 ✅（依赖 config_key `feed_image_count_*_weight` / `feed_image_type_*_weight` / 4 张映射表）；可与 STEP-004~011 并行开工

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 4.4、11.2
- `@docs/design/prompt_spec_v1.2_complete.md` — 第六节 P-12/P-13
- `@frontend/static/images/avatar/character-ref/base.png` — 参考图（已就位）

---

**开发任务**：
1. 新建 `backend/utils/liblib_client.py`：
   - HMAC-SHA1 签名（AccessKey / Signature / Timestamp / SignatureNonce 四参数拼接）
   - `submit_task(task_type, params) -> task_id`（异步任务提交）
   - `poll_task(task_id, timeout_sec) -> image_url | None`（轮询结果，返回 CDN 图片 URL）
   - **限速**：QPS ≤ 1/s（用 `asyncio.Semaphore(1)` + 显式 `await asyncio.sleep(1)`）
   - **并发**：进行中任务并发 = **1**（`asyncio.Semaphore(1)` 包裹提交+轮询；2026-07-10 联调：账号侧上限约 1，原 ≤5 会导致多图后几张失败，见 TB-LF-008）
2. 新建 `backend/services/feed_image_service.py`：
   - `generate_images(post_context: dict) -> list[str]`（返回 CDN URL 数组，可能为空数组 = 纯文字帖）
   - **张数抽签**：按 `feed_image_count_*_weight` 权重抽签，先决定张数 ∈ {0,1,2-3,4}；若命中"2-3"则等概率再拆分为 2 或 3
   - **张数=0**：直接返回 `[]`，不调 LiblibAI
   - **类型抽签**：按 `feed_image_type_*_weight` 权重抽 `image_type ∈ {"selfie","daily","scenery","emotion"}`，整帖统一
   - **同帖多图变体（2026-07-10）**：`count≥2` 时按 seq 追加构图后缀 + 独立 seed；单次任务 `imgCount=1`（见 TB-LF-008 / M1 契约）
3. **关键词映射与兜底**（PRD 4.4.5）：
   - selfie（IMG1 图生图）：Prompt = P-12-pos 模板注入 `{emotion_keyword}`（从 `emotion_img_keyword` 查；未命中用 `emotion_fallback_img_keyword` 随机取一组），reference_url 从 `FEED_IMAGE_REFERENCE_PUBLIC_URL` env 读取
   - daily/scenery/emotion（Star-3 文生图）：Prompt 分别用 P-13a/b/c；变量含 `{venue_keyword, category_keyword, emotion_atmosphere}`；`venue_keyword` 从 `venue_type_img_keyword` 查，**未命中回落 `category_img_keyword[category]`**；`emotion_atmosphere` 类似兜底
4. **超时降级**（PRD 4.4.3）：
   - 单张 poll 上限 **3 分钟**；超时视为该张失败
   - 整帖所有图片整批 **15 分钟**（用 `asyncio.wait_for` 包裹整批 gather）
   - 人物组与非人物组**并行**（本项目 v1 每帖只有一种 image_type，实际不会并行；但保留组分离以备未来多类型）
   - 部分失败不阻断已完成图片；整批全失败降级为空数组（触发纯文字发布）
5. **图片下载与压缩**：
   - LiblibAI 返回 URL → `httpx` 下载到 `/tmp/lxm-feed-{uuid}.jpg`（本地临时目录，进程唯一）
   - 用 Pillow 转 WebP quality=85
   - 上传至 OSS `/lxm/posts/{post_id}/{seq:02d}.webp`（post_id 由调用方 STEP-013 传入；`seq` 从 01 起）
   - **临时文件上传成功/失败后 `os.unlink` 立即删除**（try/finally）
6. **OSS/CDN**：
   - 用 `oss2` SDK；Bucket 从 env `OSS_BUCKET` 读取
   - 写入 `feed_post.image_urls` 的最终 URL = `f"https://{OSS_CDN_DOMAIN}/lxm/posts/{post_id}/{seq:02d}.webp"`
7. **LiblibAI 统计**（本次二选一定案 §0.5）：
   - 每次任务提交后：`HINCRBY liblib_stats:{today} total 1`
   - 成功：`HINCRBY liblib_stats:{today} success 1`；`HINCRBY liblib_stats:{today} points_used {返回的 points}`（若接口返回积分）
   - 失败：`HINCRBY liblib_stats:{today} failed 1`
8. **真实感增强**（PRD 4.4.4）：由 P-12/P-13 模板内容承担，无需服务层额外处理

**不在本环节范围内**：
- 部署环境公网拉取 base.png 实测（附录 A-3，运维验收）
- 落库到 `feed_post.image_urls`（STEP-013 负责）
- 图片相似度参数 UI（STEP-032）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 张数=0 抽签 | mock random | 返回 `[]`，不调 LiblibAI |
| selfie 3 张 | 抽 selfie + 3 | 提交 3 个 IMG1 任务 |
| venue 未命中 | venue_type="宠物店" | 回落 category_img_keyword |
| emotion 自由词 | emotion="温柔" | 用 fallback 兜底组 |
| 单张超时 | poll 3min 未返回 | 该张失败，其余继续 |
| 全批失败 | 全部超时 | 返回 `[]` |
| WebP 压缩临时清理 | 单张成功 | `/tmp/lxm-feed-*.jpg` 不存在 |
| 统计写入 | 一张成功 | liblib_stats:{today} total/success 各 +1 |

---

**完成标志**：
- [ ] 张数分布可配置抽签
- [ ] 关键词映射 4 张表兜底路径全测
- [ ] 单张/整批超时降级
- [ ] 临时文件 100% 清理（try/finally 覆盖）
- [ ] CDN 域名 env 读取，不硬编码
- [ ] liblib_stats:{date} 写入
- [ ] **契约条目草稿**已附交付说明（OSS 路径 / CDN key / 统计 key）
- [ ] STEP-012 → ✅（本地可用 mock 完成开发；部署后再实测公网拉取 base.png）

---

### [STEP-013] LIFE001 每日发布整合任务（01:00）

**目标**：01:00 整合文案 + 图片 + 落库 feed_post；随机 2~3 条；分配发布窗口；`scheduled_publish_time` 控制到点可见。

---

**前置条件检查**：STEP-011、012 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 4.1、4.2、4.7、10.3
- `@backend/services/feed_content_service.py`（STEP-011）
- `@backend/services/feed_image_service.py`（STEP-012）
- `@backend/services/admin_config_service.py`

---

**开发任务**：
1. 新建 `backend/tasks/life_feed_task.py`（如 STEP-005/007 未创则本 STEP 建）追加 `daily_feed_publish_task(plan_date: date)`：
   - 读取 `life_plan.gen_status='ready'`；无则日志 INFO 并 return
   - **自动开关校验**：读 admin_config `feed_auto_publish_enabled`（默认 True）；False 时任务 skip 并记 INFO
2. **发布数量抽签**（PRD 4.2.1）：
   - 从 admin_config 读 `feed_daily_post_count_2_weight`/`_3_weight`，抽 2 或 3
   - `final_count = min(target, dedup_after_available_scene_count)`
3. **场景分配**：按 scenes 时间顺序前 N 条（`sorted(scenes, key=lambda s: s['time_range'])`）分配给发布窗口
   - 窗口来源：admin_config `feed_publish_window_1/2/3`（STEP-003 已备）；2 条用窗口 1+2，3 条用窗口 1+2+3
   - 每个窗口内随机选一具体时间（`random.randint(start_sec, end_sec)`）作为 `scheduled_publish_time`
4. **单条生成流程**（串行处理，避免超并发）：
   - 读取快照：`worldview_snapshot.gen_status='generating'` **视同 `failed`** 降级（PRD 4.1）
   - 调 `feed_content_service.generate_post_text(scene, snapshot, plan_date)`
   - `DedupHitException` / `SimilarityHitException` / `ContentSafetyException` → 该条跳过，可用条数减 1，日志记录
   - 调 `feed_image_service.generate_images(post_context)`；全失败视为纯文字帖
5. **落库**（`generation_status='ready'`, `is_visible=1`, `actual_publish_time=NULL`, `image_reference_url=FEED_IMAGE_REFERENCE_PUBLIC_URL`）：
   - `base_likes = random.randint(feed_base_likes_min, feed_base_likes_max)`
   - `like_multiplier = random.randint(feed_like_multiplier_min, feed_like_multiplier_max)`
   - `real_likes = 0`
   - `dedup_hash` 沿用 STEP-011 计算的哈希（避免重复 md5）
   - `image_type` 记录 STEP-012 抽签结果
6. **season 计算**（PRD 4.4.3 / 10.7#4）：
   - `southern_hemisphere_cities` 从 admin_config 读；命中则用反向月份：3-5→秋 / 6-8→冬 / 9-11→春 / 12-2→夏
   - 未命中用北半球标准：3-5→春 / 6-8→夏 / 9-11→秋 / 12-2→冬
   - 单独函数 `backend/utils/season_utils.py::compute_season(city: str, plan_date: date) -> str`
7. **actual_publish_time 写入方式**（二选一定案 §0.5）：本 STEP 只写 `scheduled_publish_time`，`actual_publish_time` 保留 NULL；STEP-015 Feed 列表 API 在查询到到点且未写的记录时 UPDATE 一次
8. scheduler cron：**01:00 每日** Asia/Shanghai
9. **关键节点系统日志**（PRD 4.7）：任务触发（INFO）、当日无 life_plan（INFO）、去重检查（INFO scene_id/dedup_hash/结果）、发布数量确定（INFO 随机值/可用数/最终）、文案生成开始/成功/失败（对应级别 + scene_id）、图片生成开始/组失败/整批超时/全失败（对应级别）、Feed 落库成功（INFO post_id/scheduled_publish_time）、整体完成（INFO 成功/跳过/失败）

**不在本环节范围内**：
- 手动 AI 生成（STEP-014）
- 用户端 API（STEP-015）
- SSE 推送（STEP-026 属 M2）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 无 life_plan | plan_date 不存在 | 任务 skip |
| 自动开关 False | admin_config 关闭 | 任务 skip |
| 抽 3 条但可用 2 场景 | scenes 数=2 | 发布 2 条 |
| dedup 命中 1 条 | 其中 1 scene 命中 | 发布 count-1 条 |
| 图片全失败 | mock LiblibAI 全超时 | 该条纯文字发布 |
| 快照 generating | snapshot=generating | 视同 failed 降级 |
| season 南半球 | city=悉尼, plan_date=6-15 | season='冬' |
| scheduled_publish_time | 3 条 | 分别落在 3 个窗口内 |

---

**完成标志**：
- [ ] scheduler 01:00 注册；手动触发可跑通
- [ ] `is_visible=1`、`actual_publish_time=NULL` 严格落库
- [ ] season 双半球逻辑覆盖
- [ ] 关闭自动发布开关时 skip 生效
- [ ] 系统日志按 post_id/scene_id 可查
- [ ] **契约条目草稿**已附交付说明（feed_post 字段落库策略）
- [ ] STEP-013 → ✅

---

### [STEP-014] 朋友圈后台管理 API

**目标**：10.3 朋友圈 CRUD、隐藏/展示、手动新增（上传 / AI 生成复用 LLM-04）、自动发布开关。

---

**前置条件检查**：STEP-013 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.3
- `@backend/services/feed_content_service.py`（STEP-011）
- `@backend/services/feed_image_service.py`（STEP-012）

**API 清单**：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/feed/posts?status=&page=&size=` | ai_trainer+ | 列表（status ∈ all/visible/hidden/failed）|
| GET | `/api/admin/feed/posts/{id}` | ai_trainer+ | 详情（含 image_urls / hashtags / dedup_hash） |
| PUT | `/api/admin/feed/posts/{id}` | ai_trainer+ | 编辑（content_text/hashtags/image_urls/scheduled_publish_time/emotion） |
| DELETE | `/api/admin/feed/posts/{id}` | ai_trainer+ | 删除（客户端下架，DB 保留） |
| PATCH | `/api/admin/feed/posts/{id}/visibility` | ai_trainer+ | body {is_visible: 0\|1}，隐藏/展示切换 |
| POST | `/api/admin/feed/posts` | ai_trainer+ | 手动新增（body 支持两种模式：upload / ai_generate） |
| GET | `/api/admin/feed/config/auto-publish` | ai_trainer+ | 读取 `feed_auto_publish_enabled` |
| PUT | `/api/admin/feed/config/auto-publish` | ai_trainer+ | 修改开关（走 admin_config 草稿） |

**开发任务**：
1. 按上表实现 8 端点
2. **手动新增（AI 生成）**（PRD 10.3#5b）：`POST /api/admin/feed/posts` body `{"mode": "ai_generate", "description": "...", "scheduled_publish_time": "...", "image_type"?: "selfie|daily|scenery|emotion"}`：
   - 复用 `feed_content_service.generate_post_text`，但 scene 传入模拟构造（venue_type/category/city 从 body 可选注入或默认主场城市+"日常"），description 作为 `optional_segments` 或 Prompt 变量注入
   - 不做 dedup / similarity 检查（管理员权威）
   - 图片可选调 `feed_image_service.generate_images`（若 body `image_type` 传入）
   - 落库 `generation_status='ready'`, `is_visible=1`
3. **手动新增（上传）**：`POST /api/admin/feed/posts` body `{"mode": "upload", "content_text": "...", "hashtags": [...], "image_urls": [...], "emotion": "...", "scheduled_publish_time": "..."}`
   - `image_urls` 已由前端上传至 OSS 后传回，本 STEP 不实现上传
4. **可见性切换**：hidden → visible 后 `feed_like`/`feed_comment` 完整保留（DB 层本来就没删）；PRD 10.3#4 承诺"完整复原"
5. **自动开关**：读写 `feed_auto_publish_enabled` admin_config；PUT 走草稿；生效后 STEP-013 任务下次执行时读取
6. RBAC + operation_log 全覆盖；删除/隐藏必落 operation_log

**不在本环节范围内**：
- 前端图片上传服务（v1 由管理员在 OSS 控制台手动上传或走单独文件上传接口，后者可扩展）
- 后台管理页面 UI（本 STEP 只做 API；页面在 STEP 一个后续 M3 页面组）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 列表 status=hidden | 有 3 条 is_visible=0 | 返回 3 条 |
| PATCH visibility 0→1 | 已有点赞/评论 | 200，历史数据完整 |
| ai_generate 无 description | body 缺 description | 400 |
| ai_generate 成功 | 合法 body | 落库 1 条，image_urls 可能为 [] |
| upload 缺 image_urls | mode=upload | 允许（纯文字） |
| PUT auto-publish=false | 修改开关 | draft 创建，走三道卡点 |

---

**完成标志**：
- [ ] 8 API 可测；RBAC 校验；operation_log 覆盖
- [ ] AI 生成路径复用 LLM-04（不新建 LLM 节点）
- [ ] 隐藏后复原历史互动数据保留
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-014 → ✅

---

### [STEP-015] Feed 列表与用户读 API

**目标**：用户端 Feed 分页列表；可见范围过滤；点赞展示数；进入朋友圈写 `last_feed_entered_at`；未读评论数；`actual_publish_time` 懒惰写回。

---

**前置条件检查**：STEP-001 ✅（只需表结构；不依赖 STEP-013 已有数据；可与 STEP-005~013 并行）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 5.4、5.6、5.7、5.8、6.1.1
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 全文布局参照

**API 清单**：

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/feed/list?cursor=&size=20` | Feed 列表（游标分页） |
| POST | `/api/feed/enter` | 进入朋友圈页；写 last_feed_entered_at；返回 anchor_comment_id |
| GET | `/api/feed/badge` | 首页双徽标数据（PRD 5.6） |

**开发任务**：
1. 新建 `backend/routers/feed.py`（用户端），前缀 `/api/feed`，JWT 依赖注入
2. **`GET /api/feed/list`**：
   - 查询：`scheduled_publish_time <= NOW() AND is_visible = 1 AND generation_status = 'ready'`
   - **可见范围过滤**：从 admin_config 读 `feed_history_visible_range`；`7d/30d/180d` → `AND scheduled_publish_time >= NOW() - INTERVAL {N} DAY`；`all` 不过滤
   - **游标分页**：`cursor` = last item 的 `scheduled_publish_time` timestamp；`size` 默认 20，上限 50；`ORDER BY scheduled_publish_time DESC LIMIT size`
   - **actual_publish_time 懒惰写回**（本次二选一定案 §0.5）：查询命中且 `actual_publish_time IS NULL` 的记录 → 批量 `UPDATE feed_post SET actual_publish_time=NOW() WHERE id IN (...) AND actual_publish_time IS NULL`（幂等）
   - **响应字段**：
     ```json
     {
       "posts": [{
         "id": 1, "content_text": "...", "hashtags": ["a"],
         "image_urls": ["https://cdn.../a.webp"],
         "scheduled_publish_time": "...", "emotion": "慵懒",
         "display_likes": 35,
         "user_liked": true,
         "comments": [{"id":1,"content":"...","lxm_reply":"...","lxm_reply_at":"...","lxm_reply_read_at":null}]
       }],
       "next_cursor": "2026-06-01T15:00:00"
     }
     ```
   - **评论过滤**：仅返回 `user_id = current_user` 的评论（PRD 6.2.1 私有）
   - **display_likes 计算**：`base_likes * like_multiplier + real_likes`（不 SQL 计算，Python 层组装，便于单测）
3. **`POST /api/feed/enter`**：
   - `UPDATE users SET last_feed_entered_at = NOW() WHERE id = current_user_id`
   - 查最近一条 `feed_comment WHERE user_id=? AND lxm_reply IS NOT NULL AND lxm_reply_read_at IS NULL ORDER BY lxm_reply_at DESC LIMIT 1`
   - 返回 `{"anchor_comment_id": <id or null>}`（PRD 5.6.3）
4. **`GET /api/feed/badge`**：
   - `has_new = EXISTS(feed_post WHERE scheduled_publish_time <= NOW() AND is_visible=1 AND (scheduled_publish_time > last_feed_entered_at OR last_feed_entered_at IS NULL))`
   - `unread_reply_count = COUNT(feed_comment WHERE user_id=? AND lxm_reply IS NOT NULL AND lxm_reply_read_at IS NULL)`
   - 响应 `{"has_new": true, "unread_reply_count": 3}`
   - **前端徽标互斥**：两者同时存在时前端仅展示数字角标（本 STEP 后端两个字段都返回）
5. **`is_visible=0` 帖子对用户完全不可见**（PRD 5.8）：所有查询强制 `is_visible=1`
6. **错误码**：新增 `FEED_POST_NOT_FOUND` / `FEED_POST_HIDDEN` 常量至 `backend/constants.py`

**不在本环节范围内**：
- 点赞 API（STEP-016）
- 评论 API（STEP-017）
- SSE 推送（STEP-026 属 M2）
- 已读上报（STEP-029 属 M2）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 空 Feed | DB 无数据 | 返回 `[]` |
| 分页 | 30 条数据，cursor=null size=20 | 返回 20 条 + next_cursor |
| is_visible=0 | 有隐藏帖 | 不返回 |
| 未到点 | scheduled_publish_time > now | 不返回 |
| actual_publish_time 懒惰写 | 首次到点查询 | UPDATE 一次为 NOW，二次查询保持不变 |
| 私有评论 | 其他用户评论 | 不出现在 comments |
| enter 无未读 | 无 pending lxm_reply | anchor_comment_id=null |
| badge 两个数据 | has_new=true + unread=3 | 返回两个字段 |
| 可见范围 7d | admin_config="7d" 且 8 天前的帖 | 不返回 |

---

**完成标志**：
- [ ] 3 API 均可通过 curl + JWT 测试
- [ ] 分页正确、可见范围过滤生效
- [ ] actual_publish_time 懒惰写回验证（首次查询后不再 NULL）
- [ ] 评论私有过滤覆盖测试
- [ ] **契约条目草稿**已附交付说明（用户端 API）
- [ ] STEP-015 → ✅

---

### [STEP-016] 点赞 API（feed_like）

**目标**：点赞 / 取消点赞；`real_likes ±1`；触发点赞 IM 判定钩子（M1 期间为 stub；M2 STEP-020 完成后自动生效）。

---

**前置条件检查**：STEP-015 ✅（沿用 `backend/routers/feed.py` 路由文件）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 6.1.1、6.1.2、6.1.3

**API 清单**：

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/feed/{post_id}/like` | 点赞 |
| DELETE | `/api/feed/{post_id}/like` | 取消点赞 |

**开发任务**：
1. `POST /api/feed/{post_id}/like`：
   - 校验 post 存在 且 `is_visible=1` 且 `scheduled_publish_time <= NOW()`；否则 404 `FEED_POST_NOT_FOUND`
   - 用 `INSERT IGNORE INTO feed_like (user_id, post_id) VALUES (?, ?)`（**幂等**，重复点赞不报错）
   - 若 `affected_rows == 1`（真实新增）：`UPDATE feed_post SET real_likes = real_likes + 1 WHERE id = ?`（原子）
   - **调用钩子** `like_aware_service.on_like_hook(user_id=?, post_id=?)`；
     - M1 期间 `like_aware_service` 只提供 stub 实现（记 DEBUG 日志 `like_aware_service.on_like_hook called (stub, awaiting STEP-020)`，返回 None）
     - M2 STEP-020 会用真实实现替换 stub，签名不变；本 STEP 与钩子解耦
   - 返回 `{"user_liked": true, "display_likes": <new_display_likes>}`
2. `DELETE /api/feed/{post_id}/like`：
   - `DELETE FROM feed_like WHERE user_id=? AND post_id=?`；`affected_rows==1` 则 `real_likes = real_likes - 1`（原子，且加 `AND real_likes > 0` 防负）
   - **不撤回**已触发/已入队的点赞 IM（PRD 6.1.2）：本 STEP 不做任何 agent_aware_queue 操作
   - 返回 `{"user_liked": false, "display_likes": <new_display_likes>}`
3. 新建 `backend/services/like_aware_service.py`（M1 只放 stub 函数骨架，方法签名严格与 STEP-020 保持一致）：
   ```python
   async def on_like_hook(user_id: int, post_id: int) -> None:
       """点赞感知钩子。M1 stub 实现；M2 STEP-020 会替换为真实入队逻辑。"""
       logger.debug("on_like_hook stub: user=%s post=%s", user_id, post_id)
   ```
4. 系统日志（PRD 6.4）：用户点赞事件（INFO user_id/post_id）、取消点赞事件（INFO 含 real_likes 变更后值）
5. **同一用户同帖二次点赞**：DB 唯一约束保证只算一次；API 返回始终成功幂等

**不在本环节范围内**：
- 点赞 IM 判定逻辑（特殊档 / 30% / 关系档延迟 / 入队）→ STEP-020
- 感知 IM 落库 → STEP-019/020

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 首次点赞 | 未点过 | real_likes+1，返回 display_likes 更新 |
| 重复点赞 | 已点过 | 200 幂等，real_likes 不变 |
| 取消点赞 | 已点过 | real_likes-1 |
| 取消未点过 | 未点过 | 200 幂等，real_likes 不变（保持 >=0）|
| 隐藏帖 | is_visible=0 | 404 |
| 未到点 | scheduled_publish_time > now | 404 |
| 钩子 stub | 点赞成功 | 记 DEBUG 日志，不落 agent_aware_queue |

---

**完成标志**：
- [ ] `like_aware_service.on_like_hook` 签名固化（M2 只替换实现）
- [ ] 幂等 + 原子性覆盖
- [ ] 系统日志可见
- [ ] progress 备注「M1 期间 stub 生效；M2 STEP-020 完成后感知 IM 启用」
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-016 → ✅

---

### [STEP-017] 评论 API（发评 / 私有列表）

**目标**：用户发评；写入 `feed_comment`；计算 `due_at`；评论区列表已在 STEP-015 私有过滤；含长度限制与频控。

---

**前置条件检查**：STEP-015 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 6.2.1、6.2.2、6.3
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 4.4/4.5
- `@backend/services/relationship_service.py` — 关系等级读取参照

**API 清单**：

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/feed/{post_id}/comments` | 发评（含追评） |

**开发任务**：
1. `POST /api/feed/{post_id}/comments` body `{"content": "..."}`：
   - 校验 post 存在 + 可见 + 已到点
   - **content 长度限制**（本次决策 §comment_limits=A）：`1 <= len(content) <= 200`；否则 400 `COMMENT_TOO_LONG` / `COMMENT_EMPTY`
   - **频控**（本次决策 §comment_limits=A）：`SELECT COUNT(*) FROM feed_comment WHERE user_id=? AND post_id=? AND created_at >= NOW() - INTERVAL 30 SECOND`；≥1 则 429 `COMMENT_RATE_LIMIT`
   - **内容安全** [自定义·项目惯例]：`content_safety_service.check(content)`；违规 400 `CONTENT_SAFETY_VIOLATION`
2. **首次评论 override 竞态处理**（本次决策 §first_comment_race=A）：
   - 事务内先 `UPDATE relationship SET has_ever_commented_feed=1 WHERE user_id=? AND has_ever_commented_feed=0`
   - 若 `affected_rows == 1` → 本次评论为**全局首次**，`due_at = NOW() + 30 seconds`
   - 若 `affected_rows == 0` → 已发过评论，`due_at = NOW() + rand(delay_min, delay_max)`（按关系档；使用 STEP-003 中定义的 `RELATIONSHIP_STAGE_MAP` + `comment_reply_delay_{stage}_min/max`）
3. **写入 feed_comment**：
   - 字段：`post_id, user_id, content, gen_status='pending', due_at, created_at=NOW()`
   - `lxm_reply / lxm_reply_at / lxm_reply_read_at` 保持 NULL
4. **不直接调用 LLM-05**：本 STEP 仅写库；STEP-018 独立轮询任务扫 due_at 到期 pending 记录
5. **响应**：`{"comment_id": <id>, "created_at": "...", "gen_status": "pending"}`
6. 系统日志（PRD 6.4）：INFO 记录 `user_id / post_id / comment_id / is_first_comment(bool)`
7. 错误码全部落 `constants.py`

**不在本环节范围内**：
- LLM-05 生成（STEP-018）
- 评论区展示（STEP-025）
- 后台评论管理（STEP-034）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 空 content | "" | 400 COMMENT_EMPTY |
| 超长 | 201 字符 | 400 COMMENT_TOO_LONG |
| 30s 内二次发评 | 同帖 | 429 COMMENT_RATE_LIMIT |
| 内容违规 | 违规词 | 400 CONTENT_SAFETY_VIOLATION |
| 首次评论 | has_ever_commented_feed=0 | UPDATE 生效，due_at ≈ +30s |
| 短时并发首次评论 | 用户 A/B 相同瞬间对不同帖首发 | 各自 UPDATE 独立，各自 override 30s（**注意：同用户短时对多帖并发**：只有第一条 UPDATE 成功→ override；其余落非首次延迟。用 SQL 原子 UPDATE 保证） |
| 非首次评论 | has_ever_commented_feed=1，关系=亲密 | due_at ≈ +60~180s（按 config） |
| 隐藏帖发评 | is_visible=0 | 404 |

---

**完成标志**：
- [ ] content 长度 + 频控 + 内容安全三层校验
- [ ] 首次评论竞态用原子 UPDATE 消除
- [ ] due_at 按关系档正确计算（复用 `RELATIONSHIP_STAGE_MAP` + STEP-003 config）
- [ ] 系统日志按 comment_id 可查
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-017 → ✅

---

### [STEP-018] LLM-05 评论回复延迟任务（DB 轮询消费）

**目标**：独立轮询任务扫描 `feed_comment.due_at` 到期的 pending 记录，调用 LLM-05 生成回复；45s×3 重试；写入 `lxm_reply`；内容安全兜底。

---

**前置条件检查**：STEP-002、017 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 6.2.2、6.3、6.4
- `@docs/design/prompt_spec_v1.2_complete.md` — P-06
- `@backend/services/deepseek_llm_service.py`（STEP-002）
- `@backend/services/life_prompt_service.py`（STEP-004）
- `@backend/services/content_safety_service.py`
- `@backend/services/relationship_service.py` — user_hobby_name / user_real_name 读取

---

**开发任务**：
1. 新建 `backend/services/comment_reply_service.py`：
   - `poll_and_consume() -> int`（返回处理条数）
   - 查询：`SELECT * FROM feed_comment WHERE gen_status='pending' AND due_at <= NOW() LIMIT 50 FOR UPDATE SKIP LOCKED`（并发安全）
   - 逐条 `consume_one(comment)`（生成流程见下）
2. **consume_one 流程**：
   a. 事务开始，`UPDATE feed_comment SET gen_status='generating' WHERE id=? AND gen_status='pending'`；若 `affected_rows==0` 跳过（已被其他 worker 处理）
   b. 读取 relationship：`level → stage = RELATIONSHIP_STAGE_MAP[level]`（复用 STEP-003 定义）
   c. 读取用户称呼：`relationship_info.user_hobby_name / user_real_name`（复用现有函数）；两者皆空则不注入称呼段
   d. Prompt 变量：`{post_text, user_comment, relationship_stage_zh, user_call}`；`optional_segments={"记忆": False}`（v1 不注入 user_interest_memories）
   e. **重试循环**：最多 3 次（含首次），单次 timeout 45s
      - 调 `deepseek_llm_service.call_llm("llm_05", messages, temperature=0.8)`
      - 若返回空/失败 → WARN 日志 + 立即重试
   f. 3 次全失败 → `UPDATE gen_status='failed'`，ERROR 日志（含 comment_id）；结束
   g. **内容安全**（[自定义·项目惯例]）：`content_safety_service.check(reply_text)`；违规 → `gen_status='failed'`，ERROR 日志
   h. 通过 → `UPDATE feed_comment SET lxm_reply=?, lxm_reply_at=NOW(), gen_status='ready' WHERE id=?`
3. **注意**：`has_ever_commented_feed` 已在 STEP-017 入队时置 1（详见 STEP-017 首次评论竞态处理），本 STEP 不再操作该字段
4. 新建 scheduler cron：`comment_reply_poll_task`，**每 30 秒**执行一次（延迟窗口最小 30s override 需要至少 30s 精度）
5. 系统日志（PRD 6.4）：
   - `pending → generating`（INFO comment_id）
   - LLM-05 调用开始（INFO comment_id / relationship_stage）
   - LLM-05 调用成功（INFO comment_id / 耗时 / 尝试次数）
   - LLM-05 单次失败（WARN comment_id / 失败类型 / 当前次数）
   - 最终失败（ERROR comment_id / 静默不回，可后台补发）
   - 内容安全违规（ERROR comment_id）

**不在本环节范围内**：
- 后台补发（STEP-034）
- 已读上报（STEP-029）
- 用户曝光 LXM 回复的 UI 事件（STEP-025/029）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 无 pending | DB 无待处理 | 返回 0 |
| 未到期 | due_at > now | 不消费 |
| 到期首次评论 | override 30s | 消费成功，reply 落库 |
| 3 次全超时 | mock LLM timeout | gen_status=failed |
| 内容违规 | 违规回复文本 | gen_status=failed，ERROR |
| 并发消费（两 worker） | 同一 comment | 仅一方成功 UPDATE generating |
| 关系档=知己 | level=3 | Prompt 变量 relationship_stage_zh="知己" |
| 无称呼 | hobby_name+real_name 都空 | Prompt 不注入称呼段 |

---

**完成标志**：
- [ ] 轮询 cron 已注册（30s 周期）
- [ ] 3 次重试逻辑正确
- [ ] 内容安全接入
- [ ] 并发消费 FOR UPDATE SKIP LOCKED 生效
- [ ] gen_status 状态机严格：pending → generating → ready/failed
- [ ] 系统日志按 comment_id 可查
- [ ] **契约条目草稿**已附交付说明（feed_comment.due_at 用法）
- [ ] STEP-018 → ✅

---

### [STEP-019] agent_aware_queue 基础设施与独立轮询

**目标**：独立排队表消费架构；不复用 AGE003/Step8/Future；落库 agent_message action_score=0。

---

**前置条件检查**：STEP-001、002 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 6.1.3、7.3、11.4
- `@docs/design/prompt_spec_v1.2_complete.md` — 第七节
- `@backend/models/agent_message.py` — `TriggerType` 扩展（STEP-001 已迁移 `String(16)`）
- `@backend/services/agent_service.py` — **仅参照** sort_seq 落库，不耦合扫描逻辑
- `@backend/services/timeline_seq_service.py`

**开发任务**：
1. 新建 `backend/services/agent_aware_service.py`：
   - `async enqueue(user_id: int, aware_type: str, related_post_id: int | None, prompt_key: str, delay_seconds: int, relationship_stage: str, extra_context: dict | None = None) -> int`：
     - `aware_type ∈ {"LIKE_AWARE", "READ_AWARE"}`
     - 写入 `agent_aware_queue`（`status='pending'`, `due_at=NOW() + delay_seconds seconds`）
     - 快照 `relationship_stage`（如"陌生"/"朋友"/"亲密"/"知己"），避免消费时关系变化导致 Prompt 变化
     - `extra_context` JSON（含 selected_scene_text / snapshot_summary 等，视 STEP-020/021 需要传入）
     - 返回 `queue_id`
   - `async consume_pending(batch_size=20) -> int`：轮询消费入口
2. **独立轮询任务** `agent_aware_poll_task`（`backend/tasks/agent_aware_task.py`）：
   - cron: 每 60 秒
   - 查询：`SELECT * FROM agent_aware_queue WHERE status='pending' AND due_at <= NOW() ORDER BY due_at ASC LIMIT 20 FOR UPDATE SKIP LOCKED`
3. `consume_record(queue_row)`：
   a. `UPDATE agent_aware_queue SET status='generating' WHERE id=? AND status='pending'`（原子锁）
   b. 按 `aware_type` 分派：
      - `LIKE_AWARE` → 调 `like_aware_service.generate_and_send(queue_row)`（STEP-020 实现）
      - `READ_AWARE` → 调 `read_aware_service.generate_and_send(queue_row)`（STEP-021 实现）
   c. 生成成功后 → 落库 `agent_message`（`trigger_type=LIKE_AWARE/READ_AWARE`）→ 调 `timeline_seq_service.allocate_sort_seq` → `agent_aware_queue.status='sent'`
   d. 失败 → `status='failed'`，ERROR 日志
4. `TriggerType` 常量在 STEP-001 已扩；本 STEP 只需引用；确保 `agent_message.trigger_type` String(16) 已生效
5. **明确不调用**（区别于对话主链 Agent）：
   - `calculate_action_score`（不评分，逢触发必尝试）
   - 日上限 8 次（不共享 `agent:count:{user_id}:{date}` 计数器）
   - 30 分钟间隔（不共享 `agent:last_at:{user_id}` 时间戳）
   - 黑名单（PRD 6.1.5 明确感知 IM 不受黑名单限制）
   - Step8 记忆检索、双 LLM 融合
6. 系统日志：入队（INFO queue_id/aware_type/user_id/due_at）、消费开始（INFO queue_id）、发送成功（INFO queue_id/agent_message_id/sort_seq）、失败（WARN queue_id/失败类型）

**不在本环节范围内**：
- LLM-06 具体 Prompt 与判定（STEP-020）
- LLM-07 具体 Prompt 与判定（STEP-021）
- 特殊档窗口逻辑（分别在 020/021 内实现）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 入队 like_aware | delay=30s | agent_aware_queue 新增；due_at=now+30s |
| 未到期消费 | due_at > now | 不消费 |
| 到期消费 | mock like_aware_service | status: pending → generating → sent；agent_message 落库 |
| 并发消费 | 两 worker 抢同一条 | 仅一方成功 UPDATE generating |
| 失败 | mock 抛错 | status=failed，其他行不受影响 |

---

**完成标志**：
- [ ] enqueue / consume 状态机严格
- [ ] FOR UPDATE SKIP LOCKED 生效
- [ ] agent_message 落库时 timeline_seq 分配正确
- [ ] 不共享对话主链 Agent 的计数器与间隔
- [ ] **契约条目草稿**已附交付说明（agent_aware_queue 表 + service 接口）
- [ ] STEP-019 → ✅

---

### [STEP-020] LLM-06 点赞感知 IM

**目标**：PRD 6.1.3 完整点赞 IM 规则：特殊档 100% / 常规档 30% / 关系档延迟 / 同帖去重 / 入队计数。**替换 STEP-016 的 `like_aware_service.on_like_hook` stub 实现**。

---

**前置条件检查**：STEP-016、019 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 6.1.3
- `@docs/design/prompt_spec_v1.2_complete.md` — P-07

**开发任务**：
1. 替换 `like_aware_service.py` 中的 `on_like_hook` stub 为真实实现：
   ```python
   async def on_like_hook(user_id: int, post_id: int) -> None:
       # 1. 判定是否已同帖入队过
       exists = await db.execute("SELECT 1 FROM agent_aware_queue WHERE user_id=? AND related_post_id=? AND aware_type='LIKE_AWARE' AND status IN ('pending','generating','sent') LIMIT 1")
       if exists: return  # 同帖 LIKE_AWARE 去重
       # 2. 判定档位
       ...
   ```
2. **特殊档判定**（PRD 6.1.3#1）：
   - 条件：`NOW() - users.created_at <= like_aware_special_window_hours` 且 `relationship.like_aware_special_used_count < like_aware_special_max_count`
   - 100% 触发；`delay = like_aware_special_delay_sec`（默认 30s）
   - `relationship.like_aware_special_used_count += 1`（原子 UPDATE ... = ... + 1）
   - 调 `agent_aware_service.enqueue(user_id, "LIKE_AWARE", post_id, "prompt_p07", delay, relationship_stage=level_to_stage_zh(level), extra_context={"is_special": True})`
3. **常规档判定**（PRD 6.1.3#2）：
   - `random.random() < 0.30` 才继续；否则跳过（日志 INFO reason="30%_miss"）
   - `stage = RELATIONSHIP_STAGE_MAP[level]`
   - `delay = random.randint(like_regular_delay_{stage}_min, like_regular_delay_{stage}_max)`
   - 调 `agent_aware_service.enqueue(...)`
4. **generate_and_send(queue_row)**（STEP-019 分派入口调用）：
   - Prompt: P-07-system/P-07-user；变量含 `{post_text, post_hashtags, post_emotion, user_call, relationship_stage_zh}`
   - `deepseek_llm_service.call_llm("llm_06", messages, temperature=0.7)`；单次超时 **45s**；重试 2 次（`_AWARE_TIMEOUT`，与 DeepSeek 全局默认对齐）
   - **内容安全** [自定义·项目惯例]：走 `content_safety_service.check`；违规 → 记 failed，不落 agent_message
   - 落 `agent_message`（`content=生成文本`, `trigger_type='LIKE_AWARE'`, `is_read=0`）
5. 系统日志（PRD 6.4）：点赞触发（INFO user/post/档位/延迟）、跳过（INFO reason ∈ {"already_queued","30%_miss","special_used_max"}）、入队成功（INFO queue_id）、生成完成（INFO agent_message_id）

**不在本环节范围内**：
- Feed API 层点赞接口（STEP-016）
- 后台感知消息管理页（STEP-035）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 特殊档窗口内 | 用户注册 2h，count=0 | 100% 入队，count → 1 |
| 特殊档已用满 | count=1, max=1 | 走常规档 |
| 常规档 30% 命中 | random=0.1 | 入队，延迟按关系档 |
| 常规档 30% 未中 | random=0.9 | 跳过 |
| 同帖已入队 | queue 已存在 | 跳过 |
| 内容违规 | mock 内容安全 fail | agent_message 未落，queue=failed |

---

**完成标志**：
- [ ] like_aware_service.on_like_hook 真实实现替换 stub
- [ ] 特殊/常规判定 + 30% + 关系档延迟 + 同帖去重全覆盖
- [ ] like_aware_special_used_count 原子递增
- [ ] 内容安全接入
- [ ] 系统日志按 queue_id 可查
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-020 → ✅

---

### [STEP-021] LLM-07 已读感知 IM

**目标**：PRD 7.1~7.4 已读感知：6h 点赞互斥 / 特殊档 P-14 / 常规四档 P-08~P-11 / 同帖去重 / 多帖取最近发布一条 / 入队计数。

---

**前置条件检查**：STEP-019、015 ✅（本 STEP 需 STEP-029 已读上报或直接以 STEP-015 的返回列表当作已读）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 7.1~7.4、6.1.4
- `@docs/design/prompt_spec_v1.2_complete.md` — P-08~P-11、P-14

**开发任务**：
1. 新建 `backend/services/read_aware_service.py`：
   - `on_feed_read(user_id: int, post_id: int) -> None`（由 STEP-029 已读上报调用；本 STEP 提供实现骨架 + 支持从 Feed 列表 API 内部触发的兜底路径）
2. **同帖 READ_AWARE 去重**：
   - `SELECT 1 FROM agent_aware_queue WHERE user_id=? AND related_post_id=? AND aware_type='READ_AWARE' AND status IN ('pending','generating','sent') LIMIT 1`；存在则跳过
3. **6h 点赞互斥**（PRD 7.2）：
   - `SELECT 1 FROM agent_aware_queue WHERE user_id=? AND aware_type='LIKE_AWARE' AND status IN ('pending','sent') AND created_at >= NOW() - INTERVAL {read_suppress_after_like_im_hours} HOUR LIMIT 1`
   - 存在则跳过并记 INFO reason="like_im_suppress_6h"
4. **多帖取最近发布一条**（PRD 7.3）：
   - 若一次上报多个 post_id（STEP-029 批量），按 `scheduled_publish_time DESC LIMIT 1` 取最近发布的一条作为 anchor
5. **特殊档判定**（PRD 6.1.4）：
   - 条件：`NOW() - users.created_at <= read_aware_special_window_hours` 且 `relationship.read_aware_special_used_count < read_aware_special_max_count`
   - 100% 触发；`delay = read_aware_special_delay_sec`（默认 60s）
   - Prompt 用 P-14（帖文相关，好接话）
   - `relationship.read_aware_special_used_count += 1`（原子）
6. **常规档判定**：
   - 关系档决定 Prompt：`level_to_stage(level)` → `stranger/friend/intimate/soulmate` → `prompt_p08/09/10/11`
   - `delay = random.randint(read_regular_delay_{stage}_min, read_regular_delay_{stage}_max)`
7. **generate_and_send(queue_row)**：
   - 变量：`{post_text, post_hashtags, post_emotion, user_call, relationship_stage_zh, snapshot_summary}`
   - `snapshot_summary` 从 `worldview_snapshot` 取该 post 对应 scene_id 的快照文本；缺失时降级为空字符串
   - `deepseek_llm_service.call_llm("llm_07", messages, temperature=0.8)`；**45s × 2 重试**（`_AWARE_TIMEOUT`，与 DeepSeek 全局默认对齐）
   - **内容安全** [自定义·项目惯例]：违规 → failed，不落 agent_message
   - 落 `agent_message`（`trigger_type='READ_AWARE'`）
8. 系统日志：触发（INFO user/post/档位/延迟）、跳过（INFO reason ∈ {"already_queued","like_im_suppress_6h","special_used_max"}）、入队（INFO queue_id）、生成完成（INFO agent_message_id）

**不在本环节范围内**：
- 已读上报端点（STEP-029）
- 后台感知消息管理页（STEP-035）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 特殊档 | 注册 1h count=0 | 100% 入队，Prompt=P-14 |
| 关系=陌生 | level=0 | Prompt=P-08 |
| 关系=知己 | level=3 | Prompt=P-11 |
| 6h 内已有 LIKE_AWARE | 存在 | 跳过 reason="like_im_suppress_6h" |
| 同帖已入队 READ_AWARE | 已存在 | 跳过 |
| 多帖 | 批量 3 帖 | 只对最近发布 1 帖入队 |
| 内容违规 | mock 检测 fail | failed，不落 agent_message |

---

**完成标志**：
- [ ] on_feed_read 全流程
- [ ] 6h 互斥 + 同帖去重 + 多帖取最近 + 特殊/常规判定
- [ ] read_aware_special_used_count 原子递增
- [ ] 关系档→P-08~P-11 映射正确
- [ ] 系统日志按 queue_id 可查
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-021 → ✅

---

### [STEP-022] 朋友圈 H5 页面骨架（Header+列表+加载态）

**目标**：新建 `frontend/pages/feed.html`（或约定路径）；Header+Feed 列表+骨架屏+错误态+空态；符合 UI 规范二、三、五章。

---

**前置条件检查**：STEP-015 ✅

---

**需要参考的文件**：
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 全文
- `@frontend/pages/diary.html` — 页面结构参照
- `@frontend/static/css/common.css`

**页面路由**：`/pages/feed.html`

**开发任务**：
1. 新建 `frontend/pages/feed.html`；沿用现有 `common.css` 与 `.cursorrules` 前端规范（**API_BASE 为空字符串**，所有 fetch 相对路径）
2. **Header 结构**（UI 3.1）：
   - 顶部返回按钮（左）/ 消息 icon（右，跳转 `chat.html`）
   - Header 背景图：`img[src]` 读取 `/api/feed/config/header`（**新增轻量 API 一次性读取 STEP-003 的 4 个 `feed_page_*` 配置**；未命中回落到 `/static/images/feed/bg_default.jpg` 与 persona 现有头像 `/static/images/avatar/character-ref/base.png`）
   - 消息 icon 复用 `GET /api/agent/unread-count` 展示未读角标（PRD 5.3、UI 3.1）
3. **`mounted` 生命周期**：
   - 调 `POST /api/feed/enter`
   - 若响应 `anchor_comment_id` 非空 → 记录到 window 变量供 STEP-025 滚动使用
   - 或 URL 带 `?focus=unread_reply` → 同上（来自首页跳转，STEP-027）
   - 调 `/api/feed/list` 拉首屏
4. **Feed 卡片**（UI 3.2）：
   - **左日期列 + 右文案区**（DOM 结构 `<div class="feed-item"><div class="date-col">...</div><div class="content-col">...</div></div>`）
   - **相对时间规则**（UI 4.3）：今天显示 `HH:mm`；昨天显示 `昨天 HH:mm`；本周内显示 `周X HH:mm`；更早显示 `MM-DD HH:mm`
   - 文案在上；图片区在下（图片区由 STEP-023 填充）
5. **下拉刷新**：pull-to-refresh（可复用 chat.html 模式或纯原生实现）
6. **无限滚动**：滚动到底触发 `next_cursor` 请求；连续请求限流 500ms
7. **骨架屏**：首屏 loading 展示 3~5 条骨架卡片（CSS `linear-gradient` shimmer 动画）
8. **错误态**：网络失败展示"加载失败"占位 + 重试按钮（UI 5.5）
9. **空态**：无内容展示"无内容"文字提示（v1 不强制配图）
10. **JWT**：从 `localStorage.getItem('token')` 取，加到 `Authorization: Bearer ${token}` 头
11. **附带实现 `GET /api/feed/config/header`**（20 行代码）：直接读 admin_config 4 项 `feed_page_*` 返回 JSON（可放在 STEP-015 或本 STEP 完成）

**不在本环节范围内**：
- 图片预览（STEP-023）
- 互动栏（STEP-024）
- 评论区（STEP-025）
- SSE 新帖推送（STEP-026 属 M2）

---

**验收要点**：
- [ ] Header 背景图/头像/签名读取配置成功；配置缺失有兜底
- [ ] 相对时间规则四分支覆盖测试
- [ ] 骨架屏、错误态、空态、下拉刷新、无限滚动均可见
- [ ] 消息 icon 角标随 IM 未读数变化
- [ ] mounted 已调 POST /api/feed/enter；anchor_comment_id 已记录（**滚动定位在 STEP-025 完成**）

---

**完成标志**：
- [ ] 页面本地可打开
- [ ] Header/列表/骨架屏/错误态/空态 UI 验收通过
- [ ] **契约条目草稿**已附交付说明（新增 `/api/feed/config/header` 若有）
- [ ] STEP-022 → ✅

---

### [STEP-023] Feed 图片展示与全屏预览

**目标**：PRD 4.2 图片布局 1/2/3~4 张；全屏预览左右滑 + 双指缩放；hashtags 着色；处理 TD-001 手势冲突。

---

**前置条件检查**：STEP-022 ✅

---

**需要参考的文件**：
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 3.3 图片区、5.2 预览
- `@docs/tech-debt.md`（若存在）— TD-001 状态

**开发任务**：
1. **缩略图布局**（UI 3.3）：
   - **1 张**：卡片全宽（宽度 100%，高度按宽高比自适应但上限 360px；`object-fit: cover`）
   - **2 张**：两列并排（每列 50% 宽，等高，1:1 裁切）
   - **3~4 张**：三列网格（`grid-template-columns: repeat(3, 1fr); gap: 4px;`）；4 张自动换行为 2 行 2 列或 3+1，v1 简化为 3 列 4 项自动换行
   - **懒加载**：`loading="lazy"`
   - **加载失败 fallback**：单张失败展示灰色占位（不阻断整帖）
2. **全屏预览层**（UI 5.2）：
   - 点击缩略图弹出全屏 overlay（`position: fixed; z-index: 9999`）
   - **左右滑切换**：touch 事件监听 `touchstart / touchmove / touchend`，横向滑动 > 阈值切换
   - **双指缩放**：`touchmove` 检测两指距离变化，`transform: scale()` 实现（1.0x ~ 3.0x）
   - **点击关闭**：单击（非 pinch/swipe）关闭 overlay
   - **右上角关闭按钮**：兜底关闭入口
3. **hashtags 着色**：正文中 `#xx话题#` 用 `<span class="hashtag">` 包裹，蓝色 `#576b95`（微信标准色）；点击不跳转（v1）
4. **TD-001 手势冲突处理**：
   - 全屏预览层挂载时 `document.body.style.overscrollBehaviorX = 'contain'`；卸载时恢复
   - 预览层内 `touchmove` 事件 `preventDefault()`（在 non-passive listener 上）阻止浏览器边缘返回手势
   - 若浏览器不支持 `overscroll-behavior`（老版本 Safari），记 tech-debt 备注但不阻断上线
   - **同步 `tech-debt.md`**：TD-001 状态改为「已处理 · 现有兼容性说明」或「已关闭」

**不在本环节范围内**：
- 图片评论/点赞（已由 STEP-024 覆盖）
- 图片 CDN 域名配置（STEP-012）

---

**验收要点**：
- [ ] 4 种布局肉眼过检
- [ ] 单击→打开预览，双指缩放，左右滑切换
- [ ] 全屏时浏览器边缘返回不触发
- [ ] hashtags 蓝色渲染
- [ ] 图片加载失败不阻断帖子

---

**完成标志**：
- [ ] 1/2/3~4 张布局
- [ ] 全屏预览滑动 + 缩放
- [ ] hashtags 着色
- [ ] TD-001 手势冲突已处理并同步 `tech-debt.md`
- [ ] **契约条目草稿**已附交付说明（若有前端契约）
- [ ] STEP-023 → ✅

---

### [STEP-024] 互动栏（点赞 / 评论输入）

**目标**：UI 4.4 点赞切换高亮 + 数字变化；💬 弹出底部输入框发评/追评；乐观更新 + 失败回滚。

---

**前置条件检查**：STEP-016、017、022 ✅

---

**需要参考的文件**：
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 4.4 互动栏

**开发任务**：
1. **点赞按钮**（UI 4.4）：
   - 每张卡片右下角 ❤️ + 数字；`user_liked=true` 时 ❤️ 高亮（红色 `#e64340`）
   - 点击**乐观更新**：立即切换高亮 + 数字 ±1；后调 `POST/DELETE /api/feed/{post_id}/like`
   - 失败回滚：请求失败还原状态，弹 Toast「操作失败，请重试」
   - **防抖**：连续快点 300ms 内合并为一次请求（或干脆锁 300ms）
2. **💬 评论按钮**：
   - 点击弹出**底部固定输入框**（fixed bottom + 半屏遮罩）
   - 输入框自动聚焦（`autofocus`）；软键盘弹起（`inputmode="text"`）
   - **字数限制**：`maxlength="200"`；实时展示 `已输入 N / 200`
   - **发送按钮**：`content.trim().length >= 1` 才可点击
   - 发送后调 `POST /api/feed/{post_id}/comments`；成功后清空输入框、收起面板、追加评论到评论区（STEP-025 渲染）；显示占位「LXM 正在回复...」等待 STEP-018 生成
   - **错误处理**：
     - 429（30s 频控） → Toast「你刚刚才评论过，等 30 秒吧~」
     - 400 长度/内容安全 → Toast 显示对应文案
3. **不支持点击评论行回复 TA**（PRD 6.2.1 明确 v1 不实现楼中楼）
4. **追评**：与首次评论走同一 API/输入框；后端已按用户私有列表处理（STEP-015）
5. **UI 状态**：
   - 输入框展开状态记录到 `data.commentingPostId`，同时只允许一个帖子处于评论态
   - 页面滚动至输入框对齐位置（避免键盘遮挡）
6. **JWT header 传递**同 STEP-022

**不在本环节范围内**：
- 评论区渲染（STEP-025）
- SSE 新评论推送（STEP-026）

---

**验收要点**：
- [ ] 点赞高亮 + 数字变化即时反映
- [ ] 双击/快速点击不多发请求
- [ ] 评论字数超限按钮变灰
- [ ] 30s 频控 Toast 正确
- [ ] 发送成功后输入框收起、评论追加、"LXM 正在回复..." 占位

---

**完成标志**：
- [ ] 点赞乐观更新 + 失败回滚
- [ ] 评论输入框 + 字数计 + 发送 + 错误处理
- [ ] 键盘不遮挡
- [ ] **契约条目草稿**已附交付说明（前端交互）
- [ ] STEP-024 → ✅

---

### [STEP-025] 评论区展示（私有 + 「我」标签）

**目标**：UI 4.5 私有评论区渲染；用户与 LXM「回复 @我」统一显示「我」；未读 LXM 回复锚点滚动定位；轻度高亮。

---

**前置条件检查**：STEP-024 ✅

---

**需要参考的文件**：
- `@docs/design/朋友圈页面展示逻辑规范_v1.1.md` — 4.5 评论区
- `@docs/design/prd_v1.9.md` — 5.6.3 未读评论锚点

**开发任务**：
1. **评论区结构**（UI 4.5）：
   - 每张 Feed 卡片下方渲染评论区（仅当 `comments.length > 0` 时展示）
   - 单条评论 DOM：
     ```html
     <div class="comment-row" data-comment-id="{id}">
       <span class="comment-author">我：</span>
       <span class="comment-content">{content}</span>
     </div>
     <div class="comment-reply" data-comment-id="{id}">
       <span class="comment-author">林小梦回复 我：</span>
       <span class="comment-content lxm-reply-text">{lxm_reply}</span>
     </div>
     ```
2. **强制「我」标签**（PRD 6.2.1）：
   - 用户评论作者名一律渲染为「我」；**不允许**用 `user.nickname` / `user.username`（即使 API 返回也丢弃）
   - LXM 回复作者名固定「林小梦回复 我」
3. **LXM 回复轻度高亮**：
   - `.lxm-reply-text` 加轻微背景色 `background: #FFF9E6;` 或字色 `color: #576b95;`（v1 选一种即可，跟 hashtag 呼应）
   - 不加边框/图标，避免打扰
4. **未读 LXM 回复锚点滚动**（PRD 5.6.3、STEP-022 已记录 anchor）：
   - 首屏渲染完成后（`nextTick` 或 `setTimeout(0)`），检查 `window.__feedAnchorCommentId__`
   - 存在则 `document.querySelector('[data-comment-id="{id}"]').scrollIntoView({block: 'center', behavior: 'smooth'})`
   - 滚动后**闪烁高亮** 1.5s（加 `.comment-highlighted` class，CSS `@keyframes flash`），再自动移除
   - 滚动完成后清 `window.__feedAnchorCommentId__` 防止后续分页触发
5. **加载 LXM 回复占位**（STEP-024 发送评论后追加了占位）：
   - 若某评论 `lxm_reply=null`，展示 `<div class="comment-reply-loading">林小梦正在回复...</div>`
   - v1 不做主动轮询；页面下拉刷新时会自动更新（STEP-018 生成后回填）
6. **仅渲染 API 返回的评论**：STEP-015 后端已按 user_id 过滤，前端不做二次过滤

**不在本环节范围内**：
- 已读上报（STEP-029 属 M2）
- 评论行点击回复 TA（v1 不实现）

---

**验收要点**：
- [ ] 用户评论作者名 100% 显示「我」
- [ ] LXM 回复轻度高亮，视觉上与用户评论区分
- [ ] URL 带 `?focus=unread_reply` 或 anchor_comment_id 非空 → 滚动定位 + 闪烁高亮 1.5s
- [ ] 用户刚发的评论显示"林小梦正在回复..."占位

---

**完成标志**：
- [ ] 评论区渲染正确
- [ ] 「我」标签强制生效
- [ ] 锚点滚动 + 闪烁高亮
- [ ] LXM 回复占位
- [ ] STEP-025 → ✅

---

### [STEP-026] SSE 新帖推送（端点 + 到点广播调度）

**目标**：PRD 5.9 独立 SSE；`feed_new` 事件；仅朋友圈页挂载；含后端到点可见时的推送调度；同帖单轮去重。

---

**前置条件检查**：STEP-015、022 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 5.9.1~5.9.3
- `@backend/routers/chat.py` — SSE 现有实现参照（**只读参照，不修改**）

**API 清单**：

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/feed/events` | SSE 长连接（text/event-stream），JWT |

**开发任务**：
1. 新建 `backend/services/feed_sse_service.py`：
   - **单进程内存注册表**（本次二选一定案 §0.5）：`_connections: dict[user_id, list[asyncio.Queue]]`
   - `register(user_id: int) -> asyncio.Queue`：创建 Queue，加入注册表
   - `unregister(user_id: int, queue: asyncio.Queue)`：从注册表移除
   - `broadcast_new_feed(post_ids: list[int])`：向所有在线用户 Queue put `{"type": "feed_new", "delta": len(post_ids)}`
2. `GET /api/feed/events`（新增到 STEP-015 建的 `backend/routers/feed.py`）：
   ```python
   @router.get("/events")
   async def feed_events(request: Request, user_id: int = Depends(current_user_id)):
       async def event_generator():
           q = feed_sse_service.register(user_id)
           try:
               while not await request.is_disconnected():
                   event = await asyncio.wait_for(q.get(), timeout=15)
                   yield f"data: {json.dumps(event)}\n\n"
           except asyncio.TimeoutError:
               yield ": heartbeat\n\n"   # 心跳
           finally:
               feed_sse_service.unregister(user_id, q)
       return EventSourceResponse(event_generator())
   ```
   - **心跳**：15s 无事件发送 `: heartbeat`（SSE 注释形式，不解析）
3. **推送调度任务**（本 STEP 一并交付）：
   - 新建 `backend/tasks/feed_new_broadcast_task.py`
   - cron: 每 30 秒扫描
   - 查询：`feed_post` 中 `generation_status='ready' AND is_visible=1 AND scheduled_publish_time <= NOW() AND sse_broadcasted = 0`
   - **同帖单轮去重**（本 STEP 明确）：给 `feed_post` 新增布尔字段 `sse_broadcasted TINYINT(1) DEFAULT 0`（需在 STEP-001 迁移中一并加入；已加入者跳过；否则本 STEP 补一次 Alembic 迁移 `v6b_step026_sse_broadcasted.py`）
   - 找到新帖后：调 `broadcast_new_feed(post_ids)`；然后批量 `UPDATE feed_post SET sse_broadcasted=1 WHERE id IN (...)`
4. **前端 EventSource**（写入 `feed.html`）：
   - `mounted` 时 `new EventSource('/api/feed/events?token=' + jwt)`（浏览器 EventSource 不支持自定义 header，需 query string 传 token；后端 `Depends(current_user_id)` 需兼容 query 参数 or 用 cookie 认证）
   - **兼容方案**：在 `backend/routers/feed.py` `feed_events` 端点内单独实现 token 从 query 读取的兜底（与主 JWT 中间件解耦）
   - 收到 `feed_new` → 累加 `pendingNewCount` → 顶部展示「X 条新动态」提示条
   - 点击提示条 → 滚顶 + 重新拉 `/api/feed/list?cursor=null` → 清零 pendingNewCount
5. **断线重连**：EventSource 默认自动重连；额外用 `onerror` 中指数退避（1s / 2s / 4s / 最大 30s）
6. **重连不补发历史事件**（PRD 5.9.3）：SSE 服务无消息队列持久化；用户依赖下拉刷新兜底
7. **仅朋友圈页挂载**：`chat.html` / `index.html` 等其他页面不建 EventSource，避免连接泄漏

**不在本环节范围内**：
- 对话 SSE 任何改动
- Redis Pub/Sub 多实例扩展（v1 不做）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 单用户注册 | user 1 建 SSE | 注册表 1 项 |
| 广播 | 3 帖到点 | 所有在线 Queue put delta=3 |
| 同帖二次扫描 | 已 sse_broadcasted=1 | 不再广播 |
| 断开清理 | 客户端关闭 | 注册表移除 |
| 心跳 | 15s 空闲 | 发送注释 |

---

**完成标志**：
- [ ] SSE 端点 + 心跳 + 断连清理
- [ ] 推送调度任务 30s cron + `sse_broadcasted` 字段去重
- [ ] 前端 EventSource + 「X 条新动态」提示条 + 点击滚顶
- [ ] 断线自动重连
- [ ] **契约条目草稿**已附交付说明（SSE 端点 + `sse_broadcasted` 字段迁移）
- [ ] STEP-026 → ✅

---

### [STEP-027] 首页朋友圈入口与双徽标

**目标**：PRD 5.6 替换记忆入口；[New] 与数字角标互斥规则；点击进入行为；轮询频率控制。

---

**前置条件检查**：STEP-015、022 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 5.6.1~5.6.4
- `@frontend/pages/index.html` — 现有首页布局
- `@frontend/pages/memory.html` — 现有记忆入口位置

**开发任务**：
1. **替换记忆入口位置**：
   - `index.html` 中原「记忆」入口 DOM 位置替换为「朋友圈」入口（图标 + 文字 + 徽标容器）
   - 图标可用现有 IM 应用惯例（如相机/相册/林小梦头像轮廓，v1 用文字＋圆点即可）
2. **调 `/api/feed/badge`**：
   - `mounted` 时调一次
   - 页面 `visibilitychange` 从 hidden → visible 时再调一次
   - **不加自动轮询**（避免频繁请求）；用户从 chat.html/memory.html 返回时通过 `visibilitychange` 或 `pageshow` 事件重新拉取
3. **双徽标互斥逻辑**（PRD 5.6.2）：
   - `has_new === true && unread_reply_count === 0` → 显示红点 [New]
   - `unread_reply_count > 0` → 显示数字角标（无论 has_new 是否 true）
   - `has_new === false && unread_reply_count === 0` → 不显示任何徽标
4. **点击跳转行为**（PRD 5.6.3）：
   - `unread_reply_count > 0` → 跳转 `/pages/feed.html?focus=unread_reply`（由 STEP-022/025 触发滚动定位到最新未读回复）
   - `has_new === true && unread_reply_count === 0` → 跳转 `/pages/feed.html`（进入列表顶部）
   - 无徽标点击 → 跳转 `/pages/feed.html`（进入列表顶部）
5. `last_feed_entered_at` 由 Feed 页 `POST /api/feed/enter` 写入（**非本 STEP 写入**）；本 STEP 不做该字段任何操作
6. **兼容性**：老用户 `last_feed_entered_at IS NULL` 时 `has_new` 由后端保证返回 true（STEP-015 已实现）

**不在本环节范围内**：
- Feed 页内部滚动定位（STEP-025）
- SSE 实时新增角标（STEP-026 属 M2）

---

**验收要点**：
- [ ] 老用户首次进入首页看到 [New]
- [ ] 有未读评论时看到数字角标（≥1）
- [ ] 数字角标点击→带 focus=unread_reply 跳转
- [ ] 从 chat 返回首页角标随 IM 未读同步（若 `visibilitychange` 触发）

---

**完成标志**：
- [ ] 双徽标互斥
- [ ] 点击跳转带 query 正确
- [ ] visibilitychange 更新
- [ ] STEP-027 → ✅

---

### [STEP-028] IM 页记忆入口迁移

**目标**：原首页记忆入口迁至 `chat.html` 右上角图标；点击跳转 `/pages/memory.html`；保留原记忆页所有功能不变。

---

**前置条件检查**：无（可与 STEP-022 / STEP-027 并行）

---

**需要参考的文件**：
- `@frontend/pages/chat.html` — 现有 IM 页
- `@frontend/pages/memory.html` — 记忆页

**开发任务**：
1. **chat.html Header 右上角**：
   - 在现有 icon（如设置、返回等）旁增加**记忆 icon**（v1 用文字「记忆」或书本 emoji `📖`，视觉与现有一致）
   - 点击 → `window.location.href = '/pages/memory.html'`
2. **不修改**：memory.html 页面内部（保持现有功能与样式）
3. **注意**：本 STEP 不删除 index.html 记忆入口（STEP-027 会替换）；两者独立完成不会冲突
4. **v1 不做**：memory 页顶部返回按钮特殊处理（v1 通过浏览器 back 或站内导航返回 chat）
5. **样式**：与 chat 页现有 icon 视觉统一；不引入新 CSS 依赖

**不在本环节范围内**：
- 首页记忆入口移除（STEP-027）
- memory.html 功能修改

---

**验收要点**：
- [ ] chat 页右上角出现记忆 icon
- [ ] 点击跳转到 memory 页
- [ ] chat 页原有功能不受影响

---

**完成标志**：
- [ ] chat.html 右上角记忆 icon 到位
- [ ] STEP-028 → ✅

---

### [STEP-029] 已读上报（评论曝光 + Feed 停留）

**目标**：PRD 5.7 评论回复曝光写 `lxm_reply_read_at`；停留 Feed 视同已读 → 触发已读 IM（STEP-021）；角标实时减少。

---

**前置条件检查**：STEP-021、025 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 5.7、7.1
- `@backend/services/read_aware_service.py`（STEP-021）

**API 清单**：

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/feed/comments/{id}/read` | 单条评论已读上报（body 可为空） |
| POST | `/api/feed/{post_id}/read` | 单帖已读上报 |

**开发任务**：
1. **后端 `POST /api/feed/comments/{id}/read`**：
   - 校验 `feed_comment.user_id == current_user`（防越权）；否则 403
   - `UPDATE feed_comment SET lxm_reply_read_at = NOW() WHERE id = ? AND user_id = ? AND lxm_reply IS NOT NULL AND lxm_reply_read_at IS NULL`
   - 幂等（重复上报不报错，`affected_rows` 可能为 0）
2. **后端 `POST /api/feed/{post_id}/read`**：
   - 校验 post 存在 + 可见 + 已到点
   - **调 `read_aware_service.on_feed_read(user_id, post_id)`**（STEP-021 提供）→ 触发已读 IM 判定与入队
   - 返回 200 空对象
3. **前端 IntersectionObserver（评论曝光）**：
   - 在 STEP-025 已挂载的 `.comment-reply[data-comment-id]` DOM 上挂 IntersectionObserver
   - `threshold: 0.6`（评论 60% 进入视口）
   - 触发后调 `POST /api/feed/comments/{id}/read`；成功后从 observer 卸载该节点
   - **debounce/去重**：本地维护 `Set<commentId>` 已上报集合，避免重复请求
4. **前端 Feed 停留检测**（PRD 5.7）：
   - 每张 feed 卡片挂 IntersectionObserver，threshold 0.5
   - 卡片进入视口后**计时 3 秒**（`setTimeout`）；未离开则视为"已读"，调 `POST /api/feed/{post_id}/read`
   - 卡片提前离开视口 → 清除 timeout
   - 已上报的 post_id 记入 Set 不重复上报
5. **首页角标实时减少**：
   - 每次 `/api/feed/comments/{id}/read` 成功后，前端本地 `unreadReplyCount--`；同步更新首页返回后能看到新值（用 `sessionStorage` 或 postMessage）
   - v1 简化：不做跨页同步，只保证下次进入首页时 `/api/feed/badge` 返回最新值即可
6. **系统日志（后端）**：INFO 记录 user_id / comment_id 或 post_id / 操作类型

**不在本环节范围内**：
- 已读 IM 生成逻辑（STEP-021 已实现）
- 后台补发已读 IM（STEP-035）

---

**验收要点**：
- [ ] 评论进入视口后自动上报，`lxm_reply_read_at` 落库
- [ ] Feed 卡片停留 3s 后触发已读 IM 判定
- [ ] 用户切换到其他页面后再回来，角标数值正确
- [ ] 重复曝光同一评论不重复请求

---

**完成标志**：
- [ ] 两 API + 前端上报 + 幂等
- [ ] 联动 read_aware_service.on_feed_read
- [ ] **契约条目草稿**已附交付说明
- [ ] STEP-029 → ✅

---

### [STEP-030] 后台 Tab0 全局人设与词汇表管理

**目标**：PRD 10.0 全局配置页；persona 入口说明复用；categories / emotion 词汇表编辑；朋友圈页 Header 展示配置。

---

**前置条件检查**：STEP-003 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.0
- `@admin/pages/persona.html` — 现有人设页参照（**不修改**其内部逻辑，只做导航说明）
- `@backend/routers/admin/admin_config.py` — admin_config 读写 API

**开发任务**：
1. 新建 `admin/pages/life-feed-global.html`：
   - 页面标题「生活流 · 全局配置」
   - 侧边导航（如后续加更多 tab）
2. **人设说明块**：文字提示「基础人设复用 `/admin/pages/persona.html`，在此可扩展生活流特有偏好」；点击链接跳转 persona 页
3. **生活流人设扩展**：编辑 4 个 config_key 走草稿三卡点流程：
   - `lxm_likes`（多行文本，逗号分隔或换行）
   - `lxm_dislikes`（同上）
   - `lxm_writing_style`（多行文本描述）
   - `lxm_content_limits`（多行文本，禁忌）
4. **词汇表编辑器**（标签形式）：
   - `categories_vocab`（10 项，标签形式，可增删拖拽）
   - `emotion_vocab`（14 项，同上）
   - **新增/删除情绪词时**：弹窗提示"请同步更新 `emotion_img_keyword` 和 `emotion_atmosphere_desc` 映射表（在 STEP-032 Prompt Tab4）"（PRD 9.4）
5. **朋友圈页 Header 展示配置**：4 个 config_key 编辑：
   - `feed_page_header_bg_url`（URL 输入 + 图片预览）
   - `feed_page_header_avatar_url`（URL 输入 + 图片预览；说明「默认使用 persona 头像」）
   - `feed_page_signature`（单行文本，≤ 30 字）
   - `feed_page_display_nickname`（**只读展示**「林小梦」，不允许修改）
6. **home_city**（PRD 0.5）：单行文本；标注「主场城市，影响文案生成城市序列」
7. **保存流程**：所有字段修改走 admin_config 草稿；点击「发布」触发既有三道卡点（测试集验证 + CONFIRM + 5min 监控窗口）
8. **RBAC**：仅 `ai_trainer` 及以上可访问；`ops_admin` 只读

**不在本环节范围内**：
- 图像关键词映射表 UI（STEP-032）
- 特殊档参数（STEP-033）
- 发布时间与系统参数（STEP-036）

---

**验收要点**：
- [ ] 保存后 admin_config 有对应 draft 记录
- [ ] Feed 页 Header 展示随发布后 3600s 内更新
- [ ] 新增情绪词时提示映射同步

---

**完成标志**：
- [ ] 页面本地可打开
- [ ] 保存 → 发布走三道卡点
- [ ] operation_log 覆盖
- [ ] STEP-030 → ✅

---

### [STEP-031] 后台生活计划 + 她的宇宙管理页

**目标**：PRD 10.1、10.2 管理界面：周大纲日历/CRUD/生成 + 日计划场景可视化 + 她的宇宙快照/事件库 + 主场城市配置。

---

**前置条件检查**：STEP-006、010 ✅（管理 API 已就绪）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.1、10.2
- `@admin/pages/` — 现有后台页面参照

**开发任务**：
1. 新建 `admin/pages/life-plan.html` + `admin/pages/worldview.html`（或合并单页 2 tab）
2. **周大纲页**：
   - 顶部日期选择器（周开始日）
   - 表格展示 7 天：日期 / 城市 / 品类 / gen_status / 操作
   - 每行「编辑 / 删除」按钮 → 走 STEP-006 API
   - 顶部「一键生成剩余自然日」按钮 → 走 `POST /api/admin/life-plan/outline/generate`；生成中转圈；成功后刷新表格
   - 顶部嵌入「主场城市与生活节奏」配置表单（`GET/PUT /api/admin/life-plan/settings`，PRD 10.1#4）：home_city + 3 个比例数字输入
3. **日计划页**（点击某日进入）：
   - 展示该日 scenes JSON 数组，每条为一个可折叠卡片：`{time_range} · {city} · {category} · {venue_type} · description...`
   - 每卡片右上角「编辑 / 删除」按钮
   - 底部「+ 新增场景」按钮 → 弹窗表单（time_range/city/category/venue_type/description）
   - 顶部「手动触发 LLM-02 生成」按钮
   - **场景 JSON 可视化编辑**：编辑弹窗字段 5 个，避免暴露 raw JSON
4. **她的宇宙 · 快照页**：
   - 日期选择器 → 展示当日全部 snapshots 表格（scene_id / feeling_text 摘要 / emotion_value / focus_tag / worldview_trigger 摘要 / gen_status / 操作）
   - 点击行进入详情弹窗，可编辑上述 4 字段
5. **她的宇宙 · 事件库页**：
   - 顶部关键词搜索（event_name 模糊）
   - 分页表格：event_name / event_view 摘要 / core_attitude / source_scene_id / created_at
   - 每行「编辑 / 删除」
   - 顶部「+ 新增事件」按钮 → 弹窗（event_name 唯一、event_view、core_attitude 四选下拉）
6. **RBAC**：ai_trainer 及以上；ops_admin 只读
7. 所有修改经 STEP-006/010 API，走各自的 operation_log 埋点

**不在本环节范围内**：
- 内容 Prompt 编辑（STEP-032）
- 朋友圈内容编辑（后台朋友圈管理页由 STEP-014 API 支撑，页面本 STEP 不实现——**新增设计说明**：M3 后期若需单独朋友圈管理页可加 STEP-039，v1 靠 API 直接编辑亦可）

---

**验收要点**：
- [ ] 周大纲显示 + CRUD 顺畅
- [ ] 场景编辑弹窗 5 字段完整
- [ ] 手动 LLM-02 触发反馈明确
- [ ] 事件库搜索 + 4 选下拉
- [ ] operation_log 覆盖

---

**完成标志**：
- [ ] 4 大功能块可用
- [ ] STEP-031 → ✅

---

### [STEP-032] 后台 Prompt Tab1~4 管理页

**目标**：Prompt 编辑页 Tab1 LIFE000（P-01/P-02）/ Tab2 她的宇宙（P-03）/ Tab3 文案（P-04/P-05）/ Tab4 图片（P-12/P-13a-c + 6 张映射表）；含 LLM-01~04 模型版本切换。

---

**前置条件检查**：STEP-004 ✅（Prompt 已种子化）

---

**需要参考的文件**：
- `@docs/design/prompt_spec_v1.2_complete.md` — 全 Prompt 内容
- `@admin/pages/prompt.html` — 现有 Prompt Tab 页样式与草稿流程参照

**开发任务**：
1. 新建 `admin/pages/life-feed-prompts.html`，顶部 4 tab：
   - **Tab1 · LIFE000**：编辑 `prompt_p01_system/user` 与 `prompt_p02_system/user`；每个 Prompt 独立草稿→测试集→发布流程；顶部展示模型版本下拉（`deepseek_model_llm_01/02`，从 admin_config 读，可切换）
   - **Tab2 · 她的宇宙**：编辑 `prompt_p03_system/user` + `deepseek_model_llm_03`
   - **Tab3 · 文案**：编辑 `prompt_p04_system/user` + `prompt_p05_departure/transit/return/oneday` + `deepseek_model_llm_04`；**可选段标记语法说明**：`[可选段·快照]...[/可选段]` `[可选段·旅游]...[/可选段]`
   - **Tab4 · 图片**：
     - 编辑 `prompt_p12_pos/neg` / `p13a_pos/neg` / `p13b_pos/neg` / `p13c_pos/neg`
     - **图像映射表可视化编辑**（PRD 4.4.5、9.4）：4 张主表 `venue_type_img_keyword` / `category_img_keyword` / `emotion_img_keyword` / `emotion_atmosphere_desc`（键值对表格，支持增删）+ 2 张兜底列表 `emotion_fallback_img_keyword` / `emotion_fallback_atmosphere_desc`
2. **Prompt 编辑器**：
   - Textarea（monospace 字体，最小高度 400px）
   - 右侧展示"变量白名单"提示（如 P-01 变量列表 `{{days_count}}` 等）
   - 底部按钮：预览渲染（客户端调 `render_prompt` mock 测试）/ 保存草稿 / 发布（走三卡点）
3. **发布流程**：
   - 保存草稿 → admin_config `is_draft=True, is_active=False`（同 config_key 最多 1 条草稿）
   - 「发布」按钮触发已有的三卡点流程（测试集→CONFIRM→5min 监控）
4. **RBAC**：`ai_trainer` 及以上；`ops_admin` 只读
5. `operation_log` 覆盖草稿保存 / 发布 / 回滚

**不在本环节范围内**：
- Tab5/Tab6（STEP-033）
- 模型 API Key 编辑（技术凭证不进后台，PRD §9 前言）

---

**验收要点**：
- [ ] 4 tab 切换流畅
- [ ] 每个 Prompt 独立草稿 + 发布
- [ ] 映射表 6 张可视化编辑
- [ ] LLM-01~04 模型版本下拉可切换
- [ ] 发布走三卡点

---

**完成标志**：
- [ ] 4 tab 完整
- [ ] 草稿→发布链路验证
- [ ] operation_log 覆盖
- [ ] STEP-032 → ✅

---

### [STEP-033] 后台 Prompt Tab5~6 互动与已读管理页

**目标**：Tab5 评论 + 点赞（P-06 / P-07）/ Tab6 已读（P-08~P-11 + P-14）；含各关系档延迟 min/max + 特殊档窗口参数编辑。

---

**前置条件检查**：STEP-004 ✅

---

**需要参考的文件**：
- `@docs/design/prompt_spec_v1.2_complete.md` — P-06~P-14
- `@admin/pages/prompt.html` — 现有 Prompt 页参照

**开发任务**：
1. 沿用 STEP-032 建的 `admin/pages/life-feed-prompts.html`，追加 2 个 tab（或独立页 `life-feed-prompts-interact.html`）：
   - **Tab5 · 评论 + 点赞**：
     - 编辑 `prompt_p06_system/user`（评论回复，含 `[可选段·记忆]` 语法说明；v1 恒空）+ `deepseek_model_llm_05`
     - 编辑 `prompt_p07_system/user`（点赞感知，特殊/常规共用）+ `deepseek_model_llm_06`
     - **评论回复延迟参数**（PRD 6.3）：`comment_reply_delay_stranger_min/max`、`_friend_min/max`、`_intimate_min/max`、`_soulmate_min/max` 8 个数字（单位：秒）
     - **点赞感知参数**：
       - 常规档延迟：`like_regular_delay_{stage}_min/max` × 4 档 = 8 个数字
       - 特殊档：`like_aware_special_window_hours` / `_max_count` / `_delay_sec`
       - **首次评论 override 参数**（可选，v1 默认 30s，不必开放；但页面预留只读展示）
   - **Tab6 · 已读感知**：
     - 编辑 `prompt_p08~p11_system/user`（常规四档，陌生/朋友/亲密/知己）+ `prompt_p14_system/user`（特殊档）+ `deepseek_model_llm_07`
     - **已读感知参数**：
       - 常规档延迟：`read_regular_delay_{stage}_min/max` × 4 档 = 8 个数字
       - 特殊档：`read_aware_special_window_hours` / `_max_count` / `_delay_sec`
       - 互斥参数：`read_suppress_after_like_im_hours`
2. **发布流程**：与 STEP-032 一致（草稿→测试集→CONFIRM→5min 监控）
3. **RBAC**：ai_trainer 及以上
4. `operation_log` 覆盖

**不在本环节范围内**：
- Tab1~4（STEP-032）
- 感知消息补发（STEP-035）

---

**验收要点**：
- [ ] Tab5/Tab6 参数编辑完整覆盖 PRD 6.3/6.1.3/7 各档
- [ ] 每类延迟 min/max 单位标注为秒
- [ ] 发布走三卡点

---

**完成标志**：
- [ ] 2 tab 完整
- [ ] 参数值可视化编辑
- [ ] STEP-033 → ✅

---

### [STEP-034] 后台评论管理（10.4）

**目标**：PRD 10.4 全量评论列表 + 筛选 + CRUD + 失败补发 + 已读状态展示。

---

**前置条件检查**：STEP-014、018 ✅（STEP-014 后台管理 API 框架 + STEP-018 LLM-05 服务）

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.4
- `@backend/services/comment_reply_service.py`（STEP-018）
- `@backend/routers/admin/` — admin API 惯例

**新增管理 API**（本 STEP 落地，属 STEP-014 系列扩展）：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/feed/comments?post_id=&user_id=&gen_status=&page=&size=` | ai_trainer+ | 全量评论列表（多筛选） |
| GET | `/api/admin/feed/comments/{id}` | ai_trainer+ | 详情 |
| PUT | `/api/admin/feed/comments/{id}` | ai_trainer+ | 编辑（content / lxm_reply）|
| DELETE | `/api/admin/feed/comments/{id}` | ai_trainer+ | 隐藏/删除（软删或标记）|
| POST | `/api/admin/feed/comments/{id}/regenerate` | ai_trainer+ | 手动触发 LLM-05 补发 |

**开发任务**：
1. 后端实现上表 5 端点
2. **列表筛选 gen_status**（5 状态；PRD 10.4#1）：待回复(pending) / 生成中(generating) / 已回复(ready) / 回复失败(failed) / 已隐藏(hidden)
3. **列表字段**：post_id、user_id、user_content、lxm_reply（摘要）、gen_status、created_at、lxm_reply_read_at（是否已读，PRD 10.4#5）、due_at
4. **CRUD**（PRD 10.4#2）：管理员可编辑 user_content（保留原文） / lxm_reply（覆盖生成）；DELETE 走软删（新增 `is_hidden TINYINT(1) DEFAULT 0`；本 STEP 若表中无该字段，走 Alembic 迁移补一次 `v6c_step034_feed_comment_hidden.py`）
5. **手动补发**：调 `comment_reply_service.consume_one(comment)` **异步** 强制重跑；接口立即返回 `{"status": "queued"}`；`gen_status` 会经 pending → generating → ready/failed
6. **前端 admin/pages/feed-comments.html**：
   - 顶部筛选栏（post_id 输入 / user 下拉 / gen_status 下拉 / 时间范围）
   - 分页表格
   - 每行「编辑 / 删除 / 补发」操作按钮
   - 补发按钮点击后行状态实时更新（可轮询 3s 一次或点击后隐藏按钮 + 提示"已提交，稍后刷新"）
7. RBAC + operation_log 全覆盖

**不在本环节范围内**：
- 感知消息管理（STEP-035）

---

**验收要点**：
- [ ] 5 状态筛选覆盖
- [ ] 补发按钮生效，`consume_one` 重跑
- [ ] 已读状态展示
- [ ] operation_log 覆盖

---

**完成标志**：
- [ ] 5 API + admin 页面
- [ ] 补发链路
- [ ] **契约条目草稿**已附交付说明（feed_comment.is_hidden 新增）
- [ ] STEP-034 → ✅

---

### [STEP-035] 后台点赞 / 已读感知消息管理（10.8）

**目标**：`agent_aware_queue` + `agent_message` 联合视图；补发、删除审计；运营重置特殊档计数。

---

**前置条件检查**：STEP-020、021 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.8
- `@backend/services/agent_aware_service.py`（STEP-019）
- `@backend/models/agent_message.py`

**新增管理 API**：

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/admin/agent-aware?user_id=&trigger_type=&status=&page=` | ai_trainer+ | 联合视图（agent_aware_queue LEFT JOIN agent_message） |
| GET | `/api/admin/agent-aware/{queue_id}` | ai_trainer+ | 详情 |
| POST | `/api/admin/agent-aware/{queue_id}/retry` | ai_trainer+ | 手动重试（failed → pending，due_at 置 NOW） |
| DELETE | `/api/admin/agent-aware/{queue_id}` | ai_trainer+ | 删除队列记录（不撤回已送达 agent_message） |
| POST | `/api/admin/users/{user_id}/aware/reset` | super_admin | 重置 like_aware_special_used_count / read_aware_special_used_count |

**开发任务**：
1. 后端实现上表 5 端点
2. **联合视图字段**：queue_id / user_id / user_nickname / aware_type / status / due_at / created_at / relationship_stage / prompt_key / related_post_id / agent_message_id（若已送达） / agent_message_content 摘要
3. **筛选**：user_id、trigger_type（LIKE_AWARE/READ_AWARE）、status（pending/generating/sent/failed）、时间范围
4. **手动重试**：`UPDATE agent_aware_queue SET status='pending', due_at=NOW() WHERE id=? AND status='failed'`；由 STEP-019 轮询任务扫描消费
5. **删除记录不撤回**（PRD 10.8）：只删 agent_aware_queue，不动 agent_message；日志明确记录"已送达 IM 不撤回"
6. **重置特殊档计数**：`UPDATE relationship SET like_aware_special_used_count=0, read_aware_special_used_count=0 WHERE user_id=?`（PRD 11.4 注释「可后台重置便于测试」）
7. **前端 `admin/pages/agent-aware.html`**：
   - 顶部筛选栏 + 分页表格
   - 详情弹窗显示 extra_context JSON
   - 「重试 / 删除」操作按钮
   - 单独入口「重置用户特殊档计数」按钮（要求二次确认弹窗）
8. RBAC + operation_log；`super_admin` 才可重置

**不在本环节范围内**：
- Prompt 编辑（STEP-033）
- IM 主链消息展示（沿用现有 IM 后台管理）

---

**验收要点**：
- [ ] 联合视图筛选完整
- [ ] 手动重试后自动被 STEP-019 消费
- [ ] 重置计数需二次确认
- [ ] operation_log 覆盖删除/重试/重置

---

**完成标志**：
- [ ] 5 API + admin 页面
- [ ] 重试链路
- [ ] STEP-035 → ✅

---

### [STEP-036] 后台发布时间 / 可见范围 / 系统参数

**目标**：PRD 10.5~10.7 发布窗口 / 可见天数 / 南半球白名单 / 点赞倍率 / 发布频率 / LiblibAI 调用统计看板。

---

**前置条件检查**：STEP-003 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 10.5、10.6、10.7
- `@backend/services/admin_config_service.py`
- `@backend/utils/liblib_client.py`（STEP-012 已写入 liblib_stats:{date}）

**开发任务**：
1. 新建 `admin/pages/life-feed-system.html`，分块：
   - **发布时间窗口**（10.5）：3 个时间范围输入（HH:MM-HH:MM），对应 `feed_publish_window_1/2/3`
   - **可见范围**（10.6）：单选 7d/30d/180d/all，对应 `feed_history_visible_range`
   - **南半球城市白名单**（10.7#4）：标签编辑器，写入 `southern_hemisphere_cities` JSON 数组
   - **点赞倍率与 base_likes 范围**（10.7#2）：4 个数字输入 `feed_base_likes_min/max` / `feed_like_multiplier_min/max`
   - **发布频率权重**（10.7#3）：2 个数字输入 `feed_daily_post_count_2_weight/_3_weight`
   - **图片张数分布权重**（PRD 4.4.1）：4 个数字输入 `feed_image_count_0/1/2_3/4_weight`
   - **图片类型权重**（PRD 4.4.2）：4 个数字输入 `feed_image_type_selfie/daily/scenery/emotion_weight`
   - **文本相似度阈值**：`feed_text_similarity_threshold`（浮点，0.0~1.0）
2. **只读看板**（10.7#1）：新增 API `GET /api/admin/stats/liblib?days=7` 读取 `liblib_stats:{date}` HSET（含 total/success/failed/points_used）；页面展示近 7 天日汇总表 + 折线图（可选 Chart.js 或简单表格；v1 简单表格即可）
3. **发布流程**：所有参数走 admin_config 草稿→测试集→CONFIRM→5min 监控
4. **RBAC**：`ai_trainer` 及以上可修改；`tech_ops` 可只读看板
5. `operation_log` 覆盖所有修改

**不在本环节范围内**：
- 用户管理页（属现有后台）
- Prompt Tab（STEP-032/033）

---

**验收要点**：
- [ ] 所有参数字段展示 + 编辑 + 发布
- [ ] 看板近 7 天统计正确
- [ ] operation_log 覆盖

---

**完成标志**：
- [ ] 页面 + API 完整
- [ ] STEP-036 → ✅

---

### [STEP-037] 页面路由互通（第八章 v1）

**目标**：PRD 8.1 首页 ↔ 朋友圈 ↔ IM 跳转闭环；朋友圈消息 icon→ chat.html；v1 不注入 Feed 到 IM Prompt；核对所有入口链接可用。

---

**前置条件检查**：STEP-022、027、028 ✅

---

**需要参考的文件**：
- `@docs/design/prd_v1.9.md` — 第 8 章
- `@frontend/pages/index.html` / `chat.html` / `memory.html` / `feed.html`

**开发任务**：
1. **入口连接自检**（全部人工点击验证）：
   - `index.html` → 朋友圈入口 → `feed.html`（无徽标 / 带 focus=unread_reply / 带 [New] 三分支）
   - `index.html` → chat 入口 → `chat.html`
   - `chat.html` 右上角记忆 icon → `memory.html`
   - `chat.html` 返回 → `index.html`
   - `feed.html` 返回 → `index.html`
   - `feed.html` 消息 icon → `chat.html`
   - `memory.html` 返回 → `chat.html`（**新**，非 index）
2. **JWT 状态一致性**：全部页面从 `localStorage.getItem('token')` 读取；无 token 均跳转登录页
3. **IM 主链 Prompt 无 Feed 注入**（PRD 第 8 章 v1）：
   - 检查 `backend/services/prompt_builder.py`（现有 IM 主链构建器）无任何 `feed_post` 或 `worldview_snapshot` 引用
   - 若已被误引用，本 STEP 移除；否则文档注明"未引用，v1 无风险"
4. **文档更新**：在 `docs/design/林小梦生活流系统_prd_v1.9_steps.md` 附录或 `docs/design/prd_v1.9.md` 二期规划章节明确「二期新增 Feed 引用/IM 主动分享」
5. **JS 404 检查**：所有页面 devtools console 无 404 / JS 报错
6. **移动端 viewport**：所有页面 `<meta viewport>` 与现有一致

**不在本环节范围内**：
- IM 主链 Prompt 逻辑修改（v1 保持不变）
- 二期 Feed 注入到 IM 主链

---

**验收要点**：
- [ ] 6+ 页面跳转链路全部可用
- [ ] 无 JS 报错
- [ ] IM 主链无 Feed 注入
- [ ] v2 规划文档更新

---

**完成标志**：
- [ ] 全链路人工验证通过
- [ ] STEP-037 → ✅

---

### [STEP-038] 后台生活流菜单入口与路由注册

**目标**：管理后台侧栏注册生活流全部菜单入口（全局配置、生活计划、她的宇宙、朋友圈、评论、感知消息、Prompt Tab、系统参数），配置 RBAC 与分阶段可见性。

---

**前置条件检查**：STEP-030~036 全部 ✅（保证菜单指向的所有目标页面均存在，避免死链）

---

**需要参考的文件**：
- `@admin/static/js/admin-api.js` — `MENU_CONFIG` + `renderSidebar(activeKey)` 注册侧栏
- `@backend/routers/admin/` — 生活流路由前缀惯例

**开发任务**：
1. 在 `MENU_CONFIG` 顶级菜单新增分组「生活流」，子项依次：
   - 全局配置（STEP-030 页面）
   - 生活计划（STEP-031）
   - 她的宇宙（STEP-031）
   - 朋友圈 · 内容（STEP-014 API 支撑 · 若无独立页面则内嵌到生活计划页或本 STEP 补简易列表页）
   - 朋友圈 · 评论（STEP-034）
   - 感知消息（STEP-035）
   - Prompt · 生活流（STEP-032）
   - Prompt · 互动与已读（STEP-033）
   - 发布 & 系统参数（STEP-036）
2. **角色权限**（RBAC）：
   - `super_admin`：全部可见
   - `ai_trainer`：全部可见
   - `ops_admin`：只读（限"朋友圈 · 内容"「朋友圈 · 评论」「感知消息」）
   - `tech_ops`：只读「发布 & 系统参数」中的 LiblibAI 看板部分
3. **文案与 PRD 9 章对齐**：使用「她的宇宙」（**非**「世界观」）；「朋友圈」（**非**「Feed」）
4. **图标**：可用现有 emoji 或字体图标；v1 简化
5. **路由注册**：每个菜单项 `href` 指向对应页面 URL，如 `/admin/pages/life-feed-global.html`
6. **左侧栏默认展开状态**：进入任一生活流页面时，「生活流」分组默认展开

**不在本环节范围内**：
- 各管理页业务逻辑（STEP-030~036 已实现）
- 后台首页仪表盘改动

---

**验收要点**：
- [ ] 生活流分组 9 项菜单全部可见（超管）
- [ ] 每个菜单点击跳转到对应页面，无 404
- [ ] 4 角色权限差异化生效
- [ ] 「她的宇宙」命名正确

---

**完成标志**：
- [ ] MENU_CONFIG 更新完整
- [ ] 所有子菜单 href 有效
- [ ] RBAC 差异化验证
- [ ] STEP-038 → ✅ — **生活流 v1 全链路闭环**

---

## 4. 自检清单

- [x] 需求文档中每一条功能都有对应的 STEP（F-001~F-037 映射至 STEP-001~038）
- [x] 没有增加需求文档中不存在的功能（未加入 @ 功能、IM Feed 卡片等二期项）
- [x] 所有自定义字段已标注 `[自定义]`（如 config_key 命名、SSE 内存注册表选型）
- [x] 二次审查遗留的 5 个二选一定案已全部拍板（§0.5）
- [x] 首次评论 30s override 竞态处理已明确（STEP-017 原子 UPDATE 抢占）
- [x] 契约措辞已统一为「契约条目草稿」（§0.3）
- [x] 环节之间的依赖关系逻辑正确（M1 内容流水线 + Feed 全链路 → M2 感知 IM + SSE + 已读 → M3 后台）
- [x] 每个 M 独立可验证（M1 用户可用 / M2 感知 IM 上线 / M3 后台可运营）
- [x] 每个 STEP 包含单元测试或验收要点
- [x] 进度文档 `林小梦生活流系统_prd_v1.9_progress.md` 已按新 M 划分同步

---

## 附录 A：推荐实施波次（对齐新里程碑）

### M1 波次（22 STEP · 独立验证目标：用户可刷 Feed + 点赞 + 发评 + 收 LXM 回复 + 看图放大 + 首页入口）

| 波次 | STEP | 目标 | 可并行 |
|------|------|------|--------|
| M1-W1 地基 | 001, 002, 003, 004 | 库表迁移 + DeepSeekClient + admin_config + Prompt 种子 | 001↔002 |
| M1-W2 内容流水线 | 005, 007, 009, 011, 012, 013 | 周大纲→日场景→她的宇宙→文案→图片→整合发布 | 012 与 005-011 并行 |
| M1-W3 Feed API | 015, 016, 017, 018 | 用户端 Feed 列表 + 点赞 + 评论 + LLM-05 延迟消费 | 016↔017 |
| M1-W4 H5 | 022, 023, 024, 025 | 页面骨架 + 图片预览 + 互动栏 + 评论区 | 023↔024 |
| M1-W5 导航 | 027, 028, 037 | 首页双徽标 + IM 记忆入口迁移 + 路由互通 | 027↔028 |

**M1 独立验证清单**：
- [ ] 定时任务 5/7/9/11/13 手动触发可跑完整生成一天内容
- [ ] 用户能刷 Feed 分页；可见范围过滤生效
- [ ] 用户点赞按钮切换高亮 + 数字变化
- [ ] 用户发评后 30s~10min 内看到 LXM 回复占位 → 实际回复
- [ ] 用户点击图片全屏预览 + 左右滑 + 双指缩放 + 关闭
- [ ] 首页双徽标显示正确；点击带 focus=unread_reply 跳转
- [ ] 页面路由自检全通过

---

### M2 波次（5 STEP · 独立验证目标：感知 IM 独立线 + SSE 实时新帖 + 已读闭环）

| 波次 | STEP | 目标 | 可并行 |
|------|------|------|--------|
| M2-W1 基础设施 | 019 | agent_aware_queue + 轮询 | — |
| M2-W2 感知 LLM | 020, 021 | LLM-06 点赞感知 + LLM-07 已读感知 | 020↔021 |
| M2-W3 实时推送 | 026 | SSE 新帖端点 + 广播调度 | 独立于 019~021 |
| M2-W4 已读闭环 | 029 | 前端已读上报 + 触发 LLM-07 | — |

**M2 独立验证清单**：
- [ ] 用户点赞后关系档时间到，IM 收到点赞感知消息（`agent_message.trigger_type='LIKE_AWARE'`）
- [ ] 用户已读某帖后（6h 互斥判断通过），IM 收到已读感知消息（`READ_AWARE`）
- [ ] 后端 01:00 发帖到点后，在线用户 30s 内看到「X 条新动态」提示
- [ ] 用户评论曝光后 `lxm_reply_read_at` 立即写入；数字角标随之减少
- [ ] STEP-016 stub 已被 STEP-020 真实实现替换

---

### M3 波次（12 STEP · 独立验证目标：运营 4 角色可全流程操作）

| 波次 | STEP | 目标 | 可并行 |
|------|------|------|--------|
| M3-W1 API 层 | 006, 008, 010, 014 | 后台 API 全部就绪 | 全部可并行 |
| M3-W2 UI 层 | 030, 031, 032, 033, 034, 035, 036 | 后台各页面就绪 | 全部可并行 |
| M3-W3 菜单 | 038 | 生活流菜单注册 + RBAC | 依赖 W1+W2 |

**M3 独立验证清单**：
- [ ] `ai_trainer` 登录可访问全部生活流菜单，编辑 persona/Prompt/参数走三卡点生效
- [ ] `ops_admin` 只读感知消息/评论页
- [ ] 手动补发失败评论 → LLM-05 重跑 → 用户端可见
- [ ] 手动重试感知消息 → 用户端 IM 收到
- [ ] 修改发布窗口/可见范围 → STEP-013/015 下次执行生效
- [ ] 修改南半球城市名单 → season 计算切换生效
- [ ] LiblibAI 看板显示近 7 天调用数与积分

---

## 附录 B：非 STEP 阻塞项

> **部署验收项**：附录 A-3 — 生产域名实测 LiblibAI 拉取 `base.png`（不阻断 STEP-012 开发；部署后运维验收）
>
> **运维项**：上线前可通过 STEP-014 手动发帖或脚本预填充动态（UI 规范 5.5 空态说明）
>
> **阶段二验收**（PRD 12.2#5）：「内容一致性测试」不单独设 STEP；建议在 M1/M2/M3 收尾时人工抽检人设/去重/四档话术，或纳入后台 AI 测试工具扩展
