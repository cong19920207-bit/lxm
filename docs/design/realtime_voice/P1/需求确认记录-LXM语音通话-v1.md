# LXM 语音通话 · 需求确认记录 v1.3

> 版本：v1.3
> 状态：已确认（本记录为决策事实源；PRD、后台 DESIGN、交互规格与 STEP 已回写；对应实现 STEP 同期产出并验证契约增量，全部里程碑通过后统一整合现行契约）
> 初次确认：2026-08-26
> 最近更新：2026-08-30
>
> **审查对象**
> - `docs/design/realtime_voice/P1/PRD-LXM语音通话仿真交互设计-v2.md`
> - `docs/design/realtime_voice/P1/DESIGN-LXM语音通话后台配置与管理-v1.md`
> - `docs/design/realtime_voice/P1/LXM语音通话交互规格与PRD映射-v1.md`
>
> **代码核查范围**
> `backend/models/admin_config.py`、`backend/services/admin_config_service.py`、`backend/models/admin_user.py`、`backend/utils/admin_auth.py`、`backend/models/relationship.py`、`backend/services/relationship_service.py`、`backend/models/relationship_growth_log.py`、`backend/constants/__init__.py`、`backend/utils/character_knowledge_validate.py`、`backend/utils/dashvector_client.py`、`backend/services/memory_llm_service.py`、`backend/services/step6_orchestrator.py`、`backend/services/timeline_read_service.py`、`backend/services/chat_service.py`、`backend/services/chat_queue_service.py`、`backend/services/open_chat_service.py`、`backend/services/content_safety_service.py`、`backend/services/agent_service.py`、`backend/services/diary_service.py`、`backend/services/stats_service.py`、`backend/services/llm_service.py`、`backend/services/future_handler.py`、`backend/routers/admin/*.py`、`frontend/pages/chat.html`、`feat/realtime-voice-phase0@b937a78` 分支全量
>
> **不在读取范围**（按 `AGENTS.md`）
> `.doc-migration-baseline/`、`docs/design/realtime_voice/P1/history/`

---

## 0. 前提裁定

本次确认先裁定三项前提，后续所有决策以此为基础。

| 编号 | 前提 | 裁定 |
|---|---|---|
| P-01 | `docs/design/realtime_voice/P0/决策记录-林小梦实时语音通话-v2.md`（C1–C27）与 P1 PRD v2 的关系 | **P1 PRD v2 全面取代 P0 决策记录**；P0 标为历史文档。冲突项一律以 P1 PRD v2 + 本记录为准 |
| P-02 | 部署形态 | **单实例部署**。与文字链路现状一致（`chat_service._generation_futures` 为进程内字典，`asyncio.Future` 无法跨实例共享）。此前提须写入 DESIGN 作为显式约束 |
| P-03 | 浏览器支持范围 | 本期**仅支持独立浏览器**。微信内置浏览器走"浏览器不支持"阻断页（Demo 14），记为已知限制。P0 C27 要求的微信 JSSDK 录音方案本期不做 |

### 0.1 P0 决策记录被取代的具体条目

保留在此处备查，避免后续开发误引用。

| P0 决策 | P0 原内容 | 本期以何为准 |
|---|---|---|
| C2 | `stable_key` 打 `source=voice_call` 标记 | **作废**。`stable_key` 是 `build_doc_id` 的哈希输入，打标记会使语音与文字的同一条记忆分裂成两个 `doc_id`，破坏 upsert 去重。改为 V2-3（溯源走 MySQL 台账，向量 `fields` 与文字完全同构） |
| C7 | 余额制按秒，新用户 600 秒，无每日重置 | **作废**。改为 V10-3（全局统一日配额，`Asia/Shanghai` 自然日重置） |
| C8 | 连续 10 秒静音强制结束 | **作废**。以 PRD 的 12 秒静音超时为准 |
| C10 | 摘要不展示用户侧，仅后台可见 | **作废**。以 PRD §14.3 + Demo 16 的卡片一句话摘要为准 |
| C11 / C26 | 有效通话日 + 里程碑；首通 +5、通话日 +5、≥10 分钟 +10、日上限 20 | **作废**。以 PRD AC36/AC37 为准（65 秒 → 10 点，日上限 100） |
| C20 | 8 秒未接通 | **作废**。以 PRD AC3 的 12 秒为准 |
| C16 / C17 / C23 / C24 | 危机内容识别与响应 | **有效，补回本期范围**。见第 15 组 |
| C27 | 微信内置浏览器 JSSDK 录音 | 本期不做，见 P-03 |
| C19 / C25 | 永不承认是 AI；语音人格边界规则 | **有效**，项目级铁律，不受本次确认影响 |

---

## 1. 决策总表

### 第 1 组：跨模态派生指标与情绪链路

**问题**：语音不写 `conversation_log`，导致 6 个既有派生指标失真；情绪链路在语音中缺失。

| 编号 | 决策 |
|---|---|
| V1-1 | **写入端**：语音成长值走新增独立方法，在其中更新 `relationship.last_interaction_at`；`add_growth` 等既有函数一行不改。自动修复沉默天数与语气修正、P1 时间条件、P4 轻度沉默 |
| V1-2 | **读取端最小止损（2 处）**：`_check_p0` 的「24h 内无新对话」纳入 connected 通话；日记 `_get_conversation_summary_in_window` 的 `has_interaction` 纳入 connected 通话 |
| V1-3 | **记技术债（4 处）**：ActionScore 活跃度权重、P1 的「≥10 轮」、P3 凌晨在线、人格偏离率语音口径 |
| V1-4 | **情绪**：CALL-SUM-01 整通产出一条，存 `voice_call` 新增字段；**不写** `emotion_log` / Redis `ai_emotion` / `user_short_term_emotion`；仅供语音会前小包与后台通话详情使用 |
| V1-5 | 摘要失败时，日记侧需定义降级取值，不得把空字符串注入 Prompt |

**关键依据**

- 「不动老逻辑」不等于「老功能行为不变」。老功能的判定依据是 `conversation_log`，语音不写它，老功能会在语音用户身上主动输出错误内容：给刚打完一小时电话的用户发「一天没联系了」；2 级用户当天日记写「今天没联系」；纯语音用户 ActionScore 活跃度恒为 0。这三条是用户直接可见的穿帮。
- 情绪不能写共享 `emotion_log`：日记 `_get_recent_emotion`、主动消息 `_check_p0`、短期情绪服务第 3 层兜底查的都是「该用户最新一条 `emotion_log`」且**不带渠道过滤**，写入即被自动消费，违反「不用在其他业务上」。
- 不写 `emotion_log` 顺带绕开硬阻塞：`emotion_log.conversation_id` 为 NOT NULL 且外键指向 `conversation_log.id`，语音无 `conversation_log` 行可挂。
- 日记走「上海前一日」窗口、次日执行，CALL-SUM-01 在挂断后数秒完成，竞态风险低。

---

### 第 2 组：VOICE-MEM-01 记忆写入契约

**问题**：`memory_type` 取值、Stable Key 格式、可写入路范围、溯源落点、未完话题归属。

| 编号 | 决策 |
|---|---|
| V2-1 | PRD 示例改为真实取值（`user` / `character_private`）；VOICE-MEM-01 输出后**前置校验** `validate_key` / `validate_value`，不合规记 `dropped` 指标且**不触发重试**，不沿用 Step6 的静默 `continue` |
| V2-2 | **只允许写 `user` 与 `character_private` 两路**，代码侧硬拒绝 `character_global` / `character_knowledge` |
| V2-3 | 溯源信息**不写向量 `fields`**，改为 MySQL 独立台账（`call_id` / `turn_index` / `doc_id` / `memory_type` / `stable_key` / `pipeline_version` / `written_at`）；向量 `fields` 保持与文字链路完全一致（`content` / `stable_key` / `key_l1` / `key_l2` / `user_id`） |
| V2-4 | `unfinished_topics` / 未来约定存 `voice_call` 新增字段，仅服务语音会前小包；不进向量库、不占 Future 槽、不复用 `relationship.character_purpose` |

**关键依据**

- Step6 的写入循环对非法 key 只是 `continue` + info 日志（`memory_llm_service.py` L483–490）。若照抄，PRD §11.3 的两层示例 `后续话题-日本行程` 会被静默丢弃：任务标 success、指标显示成功、实际零写入。
- Stable Key 真实约束（`character_knowledge_validate.py`）：恰好 3 段、每段非空、仅允许汉字/数字/英文/`-`/`_`、**key 汉字 ≤20**、**value 汉字 ≤100**。口语内容天然更长，超限会被 `validate_value` 拒绝。
- `character_global` / `character_knowledge` 的 `doc_id` 后缀为 `"0"`，即**角色级、跨全体用户共享**。PRD §11.3 未限定可写路，意味着单个用户的通话可污染所有用户看到的林小梦设定。
- `dashvector_client.upsert` 是 HTTP 全量 upsert，溯源字段写进 `fields` 后，文字链路对同一 Stable Key 的下一次 upsert 会将其擦除，审计目标必然落空。台账方案同时绕开「DashVector 是否接受未预定义字段」这一未验证假设。
- 台账顺带支撑 §11.6 的漏单检查与后台 §12.1 的「记忆任务成功/失败数」列。
- V2-4 的代价：未完话题不进向量库，**文字聊天侧无法召回**，只有语音会前小包能用。

---

### 第 3 组：语音内容安全

| 编号 | 决策 |
|---|---|
| V3-1 | Phase 1 做「检测 + 记录，不干预播放」：用户 ASR final 与 AI 有效文本双向跑 `check_content` + 人格风险扫描，结果写 `voice_call_turn` 标记 |
| V3-2 | 句级拦截随第 8 组的能力取证结果再升级（依赖 `TTSSentenceStart/End` 与 `supports_playback_text_mapping`） |
| V3-3 | 使用**独立** Redis 计数键与独立指标，不并入 `content_block_count:{date}`，不污染既有看板 |
| V3-4 | 命中回合的 `memory_status` 置 `skipped`，不进 VOICE-MEM-01 |

**关键依据**

- `content_safety_service.check_content` 是纯 Redis 关键词子串匹配，耗时亚毫秒级，放入实时回路无延迟负担；异常时 fail-open，与「P4 通话不中断」同向。
- 文字链路是**入口拦截**（`check_content_safety` 在入队前执行，命中直接返回 `ERR_CONTENT_UNSAFE`，消息不进 LLM）；语音里用户话已出口、上游已在生成，只能做**出口止损**。这是产品语义硬差异，PRD 不能写成「沿用现有内容安全检查」。
- `stats_service` 的内容拦截率 = `content_block_count` / 当日 `role=assistant` 的 `conversation_log` 条数。语音若递增同一键，分子含语音、分母不含，拦截率虚高。
- 检测 fail-open 时需区分「检测通过」与「检测异常放行」两种状态，否则 Redis 故障期间安全状态不可审计。

---

### 第 4 组：`voice_call` 状态枚举与用户可见记录矩阵

| 编号 | 决策 |
|---|---|
| V4-1 | **预检全部通过后才建 `voice_call` 行**；从 `status` 移除 `preflight`，起始态为 `deciding`；阻断只走服务端指标（按原因分维度）+ 结构化日志，不落业务表 |
| V4-2 | `status` 终态**四分**：`ended`（接通过）/ `missed` / `failed` / `cancelled`。§6.2 状态机图中的 `ENDED` 标注为「流程终点抽象节点」，不是 `status` 取值 |
| V4-3 | `end_reason` 至少含九项：`user_hangup` / `user_cancel` / `exit_intent` / `silence_timeout` / `quota_exhausted` / `hard_limit` / `reconnect_timeout` / `provider_error` / `system_error` |
| V4-4 | `summary_status` 四态：`pending` / `ready` / `failed` / `not_applicable`。仅满足摘要资格的接通通话进入 `pending` 并调用摘要 LLM；`ready` 展示一句话摘要和展开箭头，`failed` 展示完整静态卡且无箭头；接通但不满足摘要资格、`missed` 及无卡片场景均为 `not_applicable`，且不调用摘要 LLM |
| V4-5 | 用户可见记录矩阵按下表定稿 |
| V4-6 | `POST /api/voice/calls` 必填 `Idempotency-Key`：UUID、长度不超过 64；同一用户范围唯一。同 key + 同 payload 在 24 小时重放窗内返回原 `call_id`，不新建票据或通话；同 key + 不同 payload 返回 409；原票据已消费或过期时返回该**通话**当前状态，不创建替代票据 |
| V4-7 | 结束页与异常文案均为 `voice_call_script` 的初始默认稿，可由后台发布覆盖；`user_cancel` 不展示结束页，直接返回聊天；`provider_error` / `system_error` 按接通前后区分文案 |

**V4-5 记录矩阵**

| 结束类型 | 落 `voice_call` | 时间线卡片 | 占 `sort_seq` | `summary_status` |
|---|---|---|---|---|
| 接通且满足摘要资格 | 是 | 完整卡片 | 是 | `pending` → `ready`/`failed` |
| 接通但不满足摘要资格（含纯静音、不足 15 秒或无意义回合） | 是 | 完整静态卡片 | 是 | `not_applicable` |
| 角色未接 | 是 | 轻量未接卡片 | 是 | `not_applicable` |
| 用户在响铃/接通阶段取消 | 是 | 无 | 否 | `not_applicable` |
| 技术失败（建连失败 / 超 12 秒） | 是 | 无 | 否 | `not_applicable` |
| 预检阻断（无额度 / 权限 / 不支持 / 并发 / 维护） | 否 | 无 | 否 | — |

**V4-7 `voice_call_script` 初始默认稿**

| 场景 / `end_reason` | 默认行为或文案 |
|---|---|
| `user_hangup` | 「就先聊到这」 |
| `user_cancel` | 不展示结束页，直接返回聊天 |
| `exit_intent` | 「好，那我们先聊到这」 |
| `silence_timeout` | 「好像暂时听不到你，我们下次再聊」 |
| `quota_exhausted` | 「今天能聊的时间用完啦，我们下次再聊」 |
| `hard_limit` | 「这次聊得有点久，我们先休息一下」 |
| `reconnect_timeout` | 「网络没有恢复，我们下次再接着聊」 |
| `provider_error` / `system_error`（接通前） | 「暂时无法接通」 |
| `provider_error` / `system_error`（接通后） | 「通话暂时中断，请稍后再试」 |

**关键依据**

- 四处文档互相矛盾：§15.1 的 `preflight` 暗示预检前建行；§20.1 AC1 写「完成检查**后**创建 `call_id`」；§18 E1–E4 与交互规格四个阻断页均写「不创建有效通话」。`preflight` 要么永不出现，要么 E1–E4 是错的。
- 重连超时结束的通话**已经接通过**，交互规格 §7 明确「保留有效通话记录」，应生成完整卡片。
- 阻断分布本质是运维指标，50 人规模用监控维度足够；真需要按用户回溯时再补尝试表，`voice_call` 结构不变，不会返工。
- `POST /api/voice/calls` 的幂等键与 C13 的「上一通结束后 3 秒内禁止再拨」是两件事：前者防网络重试重复建通话，后者防用户误触。

---

### 第 5 组：时间线通话卡片

| 编号 | 决策 |
|---|---|
| V5-1 | item **扁平扩展** 5 个字段（`call_id` / `call_status` / `duration_seconds` / `summary_status` / `call_summary`），其余 source 置 `null`；不引入 `payload` 子对象 |
| V5-2 | Open API **返回**通话卡片；对应实现 STEP 同期产出并验证 `docs/design/openapi/open-api-v1.md`、`docs/contract/current/openapi/api.md` 与 `docs/contract/current/chat-emotion/api.md` 的契约增量，全部里程碑通过后统一整合现行契约；根 `docs/contract.md` 仅在入口路由变化时更新 |
| V5-3 | 后台「历史对话 Tab」本期**不纳入**通话，页面加提示指向独立的语音通话记录页 |
| V5-4 | 摘要 ready 的传达：结束页「返回聊天」时首次拉取时间线；若卡片仍 `pending`，3 秒后仅自动重拉 1 次，总请求数固定为 2，不做无限轮询 |
| V5-7 | CALL-SUM 生产并存储 `reasoning`，仅 `super_admin` 可在后台调优查看，默认保留 30 天；不得进入用户侧、timeline 或任何导出 |
| V5-5 | `sort_seq` **插入时一次性分配**，摘要更新走 UPDATE、绝不重新分配；不生成卡片的结束类型不占号 |
| V5-6 | 前端 `renderTimelineItem` **必须新增 `source === 'call'` 分支** |

**关键依据**

- `renderTimelineItem`（`frontend/pages/chat.html` L1486–1499）只有 `source === 'user'` 与 else 两个分支。`source=call` 会落进 else 被渲染成**普通 AI 文本气泡**，正是 PRD §14.3 禁止的行为；若 call 卡片无 `content` 字段，会渲染出空气泡。这不是可选优化。
- `open_get_timeline` 是对 `get_timeline` 的直接透传（`open_chat_service.py` L76–82），改动会立刻反映到对外契约。
- 后台 `GET /api/admin/users/{user_id}/conversations` 是独立的 SQL `union_all` 实现，与 `timeline_read_service` 是两份代码，改一边不影响另一边。
- 三源各取 `limit+1` 内存合并、`next_cursor` 取 reverse 后首项，加第三源不破坏分页正确性。
- `allocate_sort_seq` 走 `SELECT ... FOR UPDATE` 行锁；通话结束时用户可能同时在发文字，需确认锁等待不拖长结束流程。
- **待确认前提**：当前是否已有真实第三方接入 Open API v1。若有，新增 `source` 取值属于对外契约变更，需评估其对未知 source 的容错。

---

### 第 6 组：语音关系成长值

| 编号 | 决策 |
|---|---|
| V6-1 | 在 `RelationshipService` 内**新增独立方法**（如 `add_voice_growth(user_id, eligible_seconds, call_id)`），复用 `_get_or_create_relationship` / `_calc_level` / 升级历史写入；`add_growth` 一行不改 |
| V6-2 | 日上限时区：语音按 `Asia/Shanghai`（沿用日记与生活流的 `ZoneInfo` 先例）；文字保持现状不动 |
| V6-3 | 幂等记录：`ALTER relationship_growth_log` 增加可空 `source_type` / `source_id` / `eligible_seconds` / `business_date` + `UNIQUE(source_type, source_id)`。MySQL 唯一索引**对 NULL 不去重**，既有行与既有写入完全不受影响 |
| V6-4 | 语音回合**不叠加** `dialog` +2 分，只按时长结算 |
| V6-5 | 语音日上限**独立 100 点**，接受全渠道 200 点/天 |
| V6-6 | 用户主动静音期间**不计入** `growth_eligible_seconds`；达日上限时**部分给分**（与既有 `add_growth` 的 `min(points, limit - current)` 语义一致） |
| V6-7 | `ACTION_LABELS` 需补语音条目，否则后台成长记录列表显示空标签 |

**关键依据**

- `GROWTH_ACTIONS` 的点数与日上限都是常量，`add_growth` 签名只接受 `action_type`，无法承载可变点数。
- 现有日上限时区是混用的：Redis key 日期用 `date.today()`（服务器本地日），TTL 用 `_seconds_until_midnight()` 基于 `datetime.utcnow()`，即 key 按本地日命名却在 UTC 午夜过期。
- **产品节奏变更提示**：现有文字四项日上限合计正好 100 点（50+20+10+20）。语音再独立给 100 后全渠道 200/天，而 0→1 级门槛 200 分——理论上一天可从「陌生」升到「朋友」；1→2 级从最快 8 天压缩到 4 天。PRD C20 未讨论此影响。已按产品视角确认接受（语音时间成本远高于文字，更快的关系推进符合直觉；50 人内测阶段推进偏快比偏慢更易观察调整）。
- 并发风险：新方法与 `add_growth` 会并发写同一行 `relationship`（用户边通话边发文字），需行锁或条件更新。这是 C54 要协调的共享标量。
- `get_relationship_detail` 返回的 `today_growth` 结构含硬编码 50，不含语音，关系页展示会与实际不符，需同步处理。

---

### 第 7 组：配置承载与版本锚定

| 编号 | 决策 |
|---|---|
| V7-1 | `base_version` **复用生效行的 `version`**；`ALTER admin_config` 增加可空 `draft_revision` 列；语音走自己的草稿保存方法（带乐观锁），发布复用 `publish_config` |
| V7-2 | `persona_ref` 存 `version` + 人格正文 `sha256`，不存正文全文 |
| V7-3 | 语音配置**第一天接入运行时**，「改配置即生效」写成显式验收项；缺配置或解析失败回退代码默认值 |
| V7-4 | 草稿保存带 `base_version` + `draft_revision` 乐观锁，冲突返回专用错误码 |
| V7-5 | 发布卡点一改为**参数取值范围校验**（如超时 5–30 秒、并发上限 ≥1），不套用 `run_standard_tests`；保留 CONFIRM 确认与发布后 5 分钟监控窗口 |
| V7-6 | 配置在**通话开始时快照锁定**，通话期间不重读（AC11 的必然要求） |

**关键依据**

- 生效行的 `version` 由 `publish_config` 递增（`new_version = current_version + 1`），可直接作 `base_version`。但草稿行 `version` **恒为 0** 且后续保存原地覆盖，无法作 `draft_revision`。
- `save_draft` 是无条件 last-write-wins，两个 `ai_trainer` 同时编辑后保存者静默覆盖，无任何冲突提示。
- **悬空引用**：`_MAX_HISTORY_VERSIONS = 20`，超出即物理删除最早历史版本。DESIGN 已为语音配置定了「通话自身另存完整快照」故不受影响；但 PRD 的 `persona_ref.version` 是**指针**，人格发布超 20 次后早期通话的追溯链会静默断裂。存 `sha256` 可在版本行被清理后仍判定「与当前生效版本是否相同」，体积恒定。
- **系统性风险**：仓库已有四条同类技术债 —— TD-004（Agent 规则）、TD-005（关系规则）、TD-007（曾经）、TD-012（第三方配置），模式一致：后台配置页已交付、可保存可发布，但**运行时不读取**。语音配置里的并发上限与时长配额直接决定成本，若不接入运行时，运营调低配额控成本时不会生效，问题要到账单出来才发现。
- `rollback_config` 是「把旧内容作为新版本重新发布」，版本号单调递增不复用，此语义适用于语音配置，可直接沿用。

---

### 第 8 组：S2S 上游能力取证

| 编号 | 决策 |
|---|---|
| V8-1 | **补一轮真实上游取证**（在 P0 分支补齐 8 个事件采集 + 六项能力位定向矩阵 + 填写 Go/No-Go 报告）；**同时并行开工**不依赖能力位的部分：第 4、5、6、7 组（状态枚举、时间线卡片、成长值、后台配置） |
| V8-2 | 六个能力位**默认全 `false`**，只有拿到证据才置 `true`；证据指纹包含 Provider Profile、模型、协议 Profile、Adapter、SDK 与测试用例版本，默认有效 30 天、可配置 7–90 天；任一指纹维度变化或到期即自动 `stale`，运行时按 `false` 降级并退出 `all`，只能经审计在 `test` 强制启用 |
| V8-3 | 重连降级形态：重连成功后以「新 Session + 补注入会前小包」继续，接受上下文断层；`voice_call_script` 初始衔接语为「刚刚好像断了一下。你刚才说到哪儿了？」，可后台发布覆盖 |
| V8-4 | 挡在取证之后的四块：打断语义、上下文截断、句级播报映射、重连恢复 |
| V8-5 | 能力证据的生产事实源为 MySQL 独立追加式记录 `voice_capability_evidence`；每次测试运行按每个能力位生成一条记录，`evidence_report_id` 为稳定唯一 UUID，`evidence_run_id` 为同轮分组 UUID。证据只追加，不更新、不做业务删除；配置草稿/版本只保存服务端生成的只读投影与引用。证据 payload 必须脱敏，禁止密钥、原始音频、用户转写、上游敏感原文及明文、可逆或可反推个人信息；完整证据仅 `super_admin` / `tech_ops` 可读，其他有配置读权角色只读非敏感投影 |

**关键依据**

- Phase 0 代码在独立分支 `feat/realtime-voice-phase0`（提交 `b937a78`「将 Phase0 实时语音实验栈隔离到独立分支」，未合 main），含真实端点 `wss://openspeech.bytedance.com/api/v3/realtime/dialogue`、二进制协议编解码、会前小包、召回编排、弱网代理。**工具链完整**。
- **但取证结论未产出**：分支上只有 `Phase0-GoNoGo-报告模板.md`，不存在任何已填写的报告。进度文档标「16/16 100%」指的是代码与单测就绪，不是真实上游采数完成。STEP-002 备注「mock + 凭据校验」是准确的。
- **事件采集白名单缺全部关键事件**。Phase 0 的 `EVENT_TYPES` 为：`session_start` / `s2s_connected` / `s2s_disconnected` / `asr_final` / `first_audio_frame` / `barge_in` / `stop_playback` / `state_change` / `recall_triggered` / `embedding_done` / `retrieval_done` / `rag_injected` / `degraded` / `recall_discarded` / `preamble_source_latency` / `voice_persona_ready` / `preamble_injected` / `preamble_inject_failed` / `error`。PRD 事件表里的 `ChatResponse` / `ChatEnded` / `TTSSentenceStart/End` / `TTSEnded` / `ConversationTruncated` / `SessionFailed` / `UsageResponse` **全部不在采集范围**，这些事件名来自 2026-07-18 桌面调研（厂商文档），非实测。

**六项能力位取证覆盖度**

| 能力位 | 采集基础 | 说明 |
|---|---|---|
| `supports_current_turn_rag_gate` | 部分 | 有 `rag_injected`，但「避免双回复」需 `ChatResponse`/`ChatEnded` 才能判定，未采集 |
| `supports_reply_cancel` | 无 | 无对应事件 |
| `supports_context_truncate` | 无 | 需 `ConversationTruncated` 确认 |
| `supports_playback_text_mapping` | 无 | 需 `TTSSentenceStart/End` |
| `supports_sentence_playback_ack` | 无 | 需句级播放确认，未实现 |
| `supports_session_reconnect` | 无 | 无对应事件 |

**六项中零项有完整证据，一项有部分基础。**

- PRD §22 的 Phase 0 定义本身是正确的（锚定 `feat/realtime-voice-phase0@b937a78`，明确「可与后台专项并行」，逐条列出待验证项）。真正的缺陷是**进度文档标 16/16 100% 会让人误判取证已交付**。
- 成本对比：补齐 8 个事件采集 + 一轮采数是**数天**量级；Phase 1 按错误假设开发后返工涉及后端交互逻辑、前端状态机与 18 张高保真页，是**数周**量级。且取证产出物（填好的 Go/No-Go）正是六个能力位所要求的「验证状态 + 证据版本」，不是额外工作。
- v1.1 已收口证据版本失效规则：按 V8-2 的六维指纹、有效期和 `stale` 降级语义执行，不再列为未定项。

---

### 第 9 组：后台权限与凭据

| 编号 | 决策 |
|---|---|
| V9-1 | 语音配置按性质**拆成两个 `config_key`**：`voice_call_config`（超时、并发、配额、能力位、总开关与用户白名单（非 capability 灰度）、关系阶段窗口与保留期）写权限 `super_admin, tech_ops`；`voice_call_script`（会前小包模板、结束页/异常/危机副文案、衔接话术）写权限 `super_admin, ai_trainer`。两者读权限均为 `super_admin, ai_trainer, tech_ops, ops_admin, observer` |
| V9-2 | 未过期的 effective 转写正文可见范围为 `super_admin, ops_admin, observer`；`observer` 只读，`ai_trainer` 与其他无正文权限角色访问正文均返回 403 |
| V9-3 | 凭据**只走环境变量**；`credential_ref` = 环境变量名 + 已/未配置状态。DESIGN 须显式声明「改凭据需改 env 并重启」 |
| V9-4 | 不引入权限点框架，按仓库既有惯例在语音 router 模块内定义角色元组 |
| V9-5 | 通话记录导出维持 `POST /api/admin/voice/calls/export`，并显式挂 `deny_observer_export`；`observer` 导出返回 403 |
| V9-6 | observer 边界：只读通话列表/详情/指标/配置，并可读取未过期的 effective 转写正文；不得读取完整生成调试文本，导出固定 403；所有写操作由方法级总闸自动拒绝；凭据只返回已/未配置状态，禁止原文、首尾、掩码、哈希或可推断元数据 |
| V9-7 | 若提供「强制挂断进行中通话」等运维动作，权限归 `tech_ops`，且必须写操作日志 |

**关键依据**

- 仓库实际做法是每个 router 模块定义自己的角色元组（`_READ_ROLES` / `_WRITE_ROLES`），`require_role(*roles)` 逐端点挂载。三类既有模板：AI 配置类 `(super_admin, ai_trainer, observer)` 读 / `(super_admin, ai_trainer)` 写；系统技术类 `(super_admin, tech_ops, observer)` / `(super_admin, tech_ops)`；用户业务数据 `(super_admin, ops_admin, observer)`。
- `_USER_BUSINESS_READ_ROLES` 不含 `ai_trainer` —— 这是一条既有隐私边界（`ai_trainer` 看不到用户历史对话），语音应对齐而非打破。`ai_trainer` 调话术可用在线测试工具。
- **凭据冲突**：DESIGN 要求语音密钥「不进入 `config_value`、Redis、历史、审计 before/after 或通话快照」，而既有做法恰恰相反 —— TD-012 记录 `admin_config.third_party:doubao` 里就存着 Endpoint 与 API Key 并同步到 Redis，**而运行时实际读的是环境变量与 `config.py`**。语音要用的是同一个厂商的同一套凭据；若引入第三种存法，运维会搞不清「豆包 key 到底改哪里」。走 env 同时满足「密钥零落地」与 observer 脱敏，并把「不支持后台热切」写成已知约束而非第五条同类债。
- V9-1 拆两个 key 同时缓解 V7-4 的草稿并发问题：话术编辑与阈值调整本就是不同人做不同事。

---

### 第 10 组：并发容量、通话租约与时长配额

| 编号 | 决策 |
|---|---|
| V10-1 | 单实例部署前提写入 DESIGN（见 P-02） |
| V10-2 | 租约带 **owner token**（锁值存 `call_id` 而非 `"1"`），释放前校验持有者；TTL 设较短值并在通话心跳中**续租**；**续租失败即结束通话**（走 `system_error`），不放任锁自然过期 |
| V10-3 | 全局并发用 Redis 计数器，配合定期扫描「进行中但超过硬顶时长」的 `voice_call` 行做**归零对账** |
| V10-4 | 时长配额：全局统一日配额，`Asia/Shanghai` 自然日重置，配额值从 `voice_call_config` 读 |
| V10-5 | 配额**不预扣**；通话中用服务端计时器实时比对「已用 vs 剩余」，结算时一次性扣减；崩溃时按最后一次心跳时长补扣 |
| V10-6 | 预检须复用 `User.is_banned` / Redis `user_banned:{user_id}`；v1.1 已同步写入 PRD C109 |
| V10-7 | 30 秒 grace 期间**仍计入**并发容量（音频仍在传输） |

**关键依据**

- 既有 `try_acquire_bundle_lock` 是无 owner token 的裸 NX 锁，释放直接 `delete` 不校验持有者。对 bundle 场景可接受（TTL 90 秒、同用户天然串行），但语音锁最长持有 1 小时，跨实例误删与续租风险被放大。
- 锁自然过期意味着系统认为通话已结束但音频流仍在走，此时用户可从另一设备拨入形成双通。主动结束通话虽损体验，但状态确定。
- 误触频控（3 秒内禁止再拨）可直接沿用 `try_consume_resend_quota` 的 `INCR` + 窗口 TTL 范式。
- **配额扣减时点的隐含约束**：PRD 的「额度耗尽后 30 秒 grace」要求服务端在通话过程中实时知道额度是否用尽。预扣模型下通话中不存在「耗尽」时刻；事后结算模型下通话中无法感知。只有实时比对能支撑 grace。而服务端本就要计时（算 `growth_eligible_seconds` 与 1 小时硬顶），实时比对是零额外成本。
- 配额重置时区必须与 V6-2 一致，否则出现「额度已重置但成长值没重置」的错位。
- 语音占用 Redis 与数据库连接的时长远超既有任何链路（1 小时 vs 数十秒），连接池容量需重新评估。

---

### 第 11 组：与主动消息体系的关系

| 编号 | 决策 |
|---|---|
| V11-1 | 本期**不做**林小梦主动呼入；`voice_call` **预留 `initiated_by`** 字段（`user` / `character`），本期恒为 `user`，后续加呼入不改表 |
| V11-2 | `voice_followup_job`（未接后的解释消息）走 `agent_message`，**绕过**「8 次/天 + 30 分钟间隔」，消费成功后**回填** `agent:count:{user_id}:{date}`（沿用 Future 槽的 R-AGT-02 范式） |
| V11-3 | 通话结束调用既有 `_reset_proactive_times` |
| V11-4 | 通话进行中**不抑制**文字主动消息投递，**记技术债**（穿帮风险） |
| V11-5 | 语音**读写都不碰** Future 槽；语音里说的约定不会触发后续主动消息，**记技术债**（后续版本考虑给语音独立槽位） |
| V11-6 | `voice_call_config` 承载可发布的关系阶段发送窗口：陌生 `[10:00,21:00)`、朋友 `[09:30,22:00)`、亲密 `[09:00,22:30)`、知己 `[09:00,23:00)`；时区 `Asia/Shanghai`，窗口左闭右开，抖动 0–20 分钟，最大顺延 24 小时。首次种子发布与读取失败回退共用一份规范默认值，业务分支不得复制硬编码 |
| V11-7 | 每个关系阶段使用非空 `windows` 数组，每个窗口为分钟精度、左闭右开的当日区间；必须 `start < end`，不允许跨日。同阶段窗口不得重叠（允许首尾相邻），不同阶段可重叠，且每个窗口时长必须大于 `jitter_max_minutes`。复用 `POST /api/admin/voice/config/config/validate` 提供无状态变更的测试预览：输入关系阶段、候选时间和确定性 0–20 分钟抖动；候选时间已在窗口内则结果为 `in_window` 且不加抖动，否则顺延到下一窗口再加抖动；恰好 24 小时允许，超过 24 小时取消。校验/预览权限为 `super_admin` / `tech_ops`；错误码固定为 `FOLLOWUP_WINDOW_RANGE_INVALID`、`FOLLOWUP_WINDOW_OVERLAP`、`FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER`、`FOLLOWUP_PREVIEW_INPUT_INVALID` |
| V11-8 | `voice_call_script.followup.missed_explanation_template` 首发逐字值固定为「刚刚没接到你的电话，晚一点我们再聊呀。」，不带任何变量；可随 `voice_call_script` 发布/回滚。配置缺失或解析失败时回退同一份规范默认值并告警，不得使用空串、占位文案或业务分支复制值 |

**关键依据**

- H5 平台硬约束：网页在用户未打开页面时无法接收推送、无法响铃、无法唤起系统来电界面。「林小梦主动打电话」在 H5 上只有「用户正好在页面时弹出呼入提示」一种形态，而这恰是最无价值的场景。
- `increment_agent_count_for_future` 提供了「绕过频控但计入计数」的成熟范式，可直接参照。
- `_reset_proactive_times` 是 `chat_service` 内的独立函数，语音调用它属于「新代码调老函数」，零侵入。
- Future 槽是**单槽**（`relationship.future_timestamp` + `future_action`），语音写入会覆盖文字链路刚写的内容，PRD §12.5 正因此禁止。
- V11-4 的穿帮场景：用户挂断后在时间线看到「刚才你在忙吗」——她一边通话一边问你在不在忙。已确认本期不扩散改动范围，记债后续优化。
- 时区提示：`agent:count` 用 `datetime.utcnow()`（UTC 日），是仓库中的**第三种**时区口径（另两种为服务器本地日与 `Asia/Shanghai`）。语音不参与主动消息计数故不受影响。

---

### 第 12 组：灰度与总开关

| 编号 | 决策 |
|---|---|
| V12-1 | 全局总开关 + 用户白名单（`config_key` 存 user_id 列表），**不做**百分比 rollout |
| V12-2 | 紧急停用**两级**：软停（只拦新拨打，进行中通话自然结束）与硬停（断开全部进行中通话）；权限归 `tech_ops`，均写操作日志 |
| V12-3 | **移除** `capability_gray` 的按用户维度；能力位是全局事实，只保留「验证状态 + 证据版本 + 强制启用标记」 |

**关键依据**

- 仓库**没有任何 feature flag / rollout / allowlist 基建**，唯一按用户门禁是 `User.is_banned` + Redis `user_banned:{user_id}`（TTL 100 年）。生活流的「白名单」是 `config_key` 可写白名单与南半球城市白名单，与用户灰度无关。
- 50 人规模下灰度的价值不是分批放量，而是「出问题时只影响 3 个人而不是 50 个」。百分比灰度在 50 人里无统计意义（10% = 5 人）。
- 能力位描述的是**上游是否支持某项行为**，是客观事实而非策略。按用户灰度等于允许「对 A 用户上游支持句级映射、对 B 用户不支持」，逻辑上不成立，且会导致同版本同时跑两套交互逻辑、故障无法复现。
- 硬停的额外成本很小（遍历进行中通话逐个结束，V10-3 的对账机制本就需要此能力），但语音依赖外部付费服务，「最坏等 1 小时排空」在异常计费场景下不可接受。

---

### 第 13 组：文档一致性缺陷

**A. 交互规格的 AC 引用错误（3 处）**

PRD v2 实际编号：AC3 = 第 12 秒上游未 ready 的**技术失败**；AC4 = CALL-01 明确不接的**角色未接**。

| 位置 | 文档写的 | 应改为 |
|---|---|---|
| `10-missed-call.html` | `20/AC3` | `20/AC4` |
| `11-connection-failed.html` | `20/AC4` | `20/AC3` |
| `16-chat-record-ready.html` | `20/AC30` | `20/AC38` |

`18-missed-call-record.html` 引用的 `20/AC4` 正确，无需改动。AC30 讲的是召回结果迟到，与摘要无关。

**B. §9.2「继承 PRD 的 TBD」已严重滞后**

十项中七项已经定稿，仅 Q1/Q2/Q3 三项上游能力仍需真实取证。

| 项 | 文档状态 | 实际状态 |
|---|---|---|
| Q6 响铃最短/最大等待 | TBD | 已定：AC2「至少 4 秒」+ AC3「第 12 秒」 |
| Q7 CALL-01 失败兜底 | TBD | 已定：AC6「默认接听 + 4–8 秒中性延迟」 |
| Q8 30 秒收尾计费口径 | TBD | 已定：AC34「每通一次、最多 30 秒**免费**、不负扣、不因重连暂停」 |
| Q10 语音是否加成长值 | TBD | 已定：AC36/AC37 |
| Q11 短附和不打断规则 | TBD | 已定：AC18 |
| Q12 短/异常通话是否生成摘要 | TBD | 已定：AC38/AC39 |
| Q9 追加消息允许时段 | TBD | 已定：陌生 `[10:00,21:00)`、朋友 `[09:30,22:00)`、亲密 `[09:00,22:30)`、知己 `[09:00,23:00)`；`Asia/Shanghai`，0–20 分钟抖动，最多顺延 24 小时 |
| Q1 / Q2 / Q3 上游能力 | TBD | **确实仍是 TBD**（见第 8 组），保留 |

§8 表格「余额归零 → 约 30 秒缓冲的计费口径为 PRD Q8 `TBD`」与 AC34 矛盾，应改为「免费，不扣减」。

**C. 结构与命名问题**

- §9.1 标题为「尚未覆盖与待确认项」，但表内六条全部以 `UI-RESOLVED-` 开头且注明已确认。应移到独立的「已确认设计决策」小节，避免读者误判仍有六个 UI 缺口。
- Demo 文件名 `12-call-duration-limit.html` 实际语义是「额度不足」（映射 `BLOCKED / NO_QUOTA`），真正的通话时长上限是 AC34 的 1 小时硬顶。需在文档点明「硬顶没有独立页面，按交互规格 §5.7 共用结束页 + 差异化副文案」。
- **进度文档误导**：`docs/progress/林小梦实时语音-Phase0_progress.md` 标「16/16 100%」，实际含义是代码与单测就绪，不是 PRD §22 定义的 Phase 0 取证已交付。须在进度文档显式区分「工具就绪」与「取证完成」两个状态。

---

### 第 14 组：指标与埋点

| 编号 | 决策 |
|---|---|
| V14-1 | 本期**不做**前端埋点通道；麦克风权限结果与浏览器能力检测结果随预检请求回传，其余 11 个事件服务端已掌握 |
| V14-2 | 语音指标用**独立 Redis 键前缀 + 独立通话看板**，不并入既有 `/admin/dashboard`，不写入 `llm_stats` / `llm_response_times` |
| V14-3 | 关键十项落 MySQL 日聚合表长期保留；瞬时分布类留 Redis 2 天 |
| V14-4 | 依赖未取证能力的指标在能力位为 `false` 时**显式标为「不可测」**，不上报数值 |
| V14-5 | 成本核对用服务端权威计时 × 单价估算，后台标注「估算值」；定期与真实账单人工对账，**差异率本身作为一个指标** |
| V14-6 | 任务日志默认保留 90 天 |

**V14-3 落表的关键十项**：每日通话数、接通率、未接率、技术失败率、平均通话时长、总有效计费秒数、估算成本、CALL-01 兜底率、VOICE-MEM-01 成功率、摘要成功率。

**关键依据**

- **前端埋点零基建**：全仓库搜不到任何埋点上报实现（无 `/api/track` 类端点、无 `sendBeacon`、无 analytics SDK）。「埋点」只出现在文档里。PRD §21.1 的 13 个事件目前无投递通道。服务端数据比前端埋点更可信（不会丢、不会被拦、不依赖用户网络），走服务端是更好的方案而非仅是更省事。
- **共享污染风险**：`llm_response_times` 是全局共享的单一 List，`llm_service` 与 `deepseek_llm_service` 都 lpush 同一个键，豆包对话、DeepSeek 生活流、感知 IM 的耗时混在一起算平均值。语音的首帧时延与文字的整轮生成耗时不是同一量纲，混算对两边都失去意义。
- **TTL 统一 172800 秒即 2 天**，无任何历史趋势能力。而 V7-3 与 V10-4 都指出并发上限与时长配额直接关系成本，成本判断需要跨周/跨月对比。
- §21.2 有四项指标依赖未取证能力：`truncate 成功率`（需 `ConversationTruncated`）、`effective_text_evidence` 各等级占比（需播放映射或句级 ack）、`双回复次数`（需 `ChatResponse`/`ChatEnded`）、`Provider Usage 与业务时长成本比`（需 `UsageResponse`）。
- 上报 0 是最危险的一类指标错误：`truncate 成功率 0%` 与 `truncate 不可测` 是完全相反的结论。呈现方式统一为「该能力未取证，指标不可测」，使看板本身在提醒还有能力未验证。

---

### 第 15 组：危机内容识别与响应

补回 P0 C16/C17/C23/C24 定义的能力。

| 编号 | 决策 |
|---|---|
| V15-1 | 命中响应：通话中在通话页底部显示**低干扰、非红色的常驻提示条**（不弹窗、不中断、不打断她说话）；挂断后在聊天流插入独立系统资源卡片，不渲染为 AI 气泡，不额外增加标题、按钮或拨号操作。P1 默认服务地区为中国大陆，使用 12356、110/120 |
| V15-2 | 危机原文存**独立表**，逐字原文，默认保留 30 天；**不进**向量库、`voice_call_turn`、摘要、会前小包；独立权限。原文必须先判定、后持久化；命中/疑似命中时，隔离原文与 turn 非正文标记在同一 MySQL 事务提交，隔离失败不得回退写 turn |
| V15-3 | 可见范围**仅 `super_admin`**，每次查看写审计日志 |
| V15-4 | 本期**仅语音**，文字侧后续迭代（同 P0 C17） |
| V15-5 | 检测方式：纯关键词匹配（新建 `crisis_keywords` config_key + Redis 键，复用 `banned_keywords` 读取范式）；发布/回滚均拒绝规范化后空集（`minItems: 1`），运行时缺失、非法、空集或异常均按疑似命中；接受隐晦表达漏检为已知限制（P0 C24） |
| V15-6 | 覆盖范围：**仅自伤/自杀倾向**。未成年人性内容、性暴力、跟踪控制、医疗危机、诈骗等明确列为已知未覆盖（P0 C23） |
| V15-7 | 危机检测**不 fail-open**。Redis 故障或检测异常时按「疑似命中」处理并告警，不静默放行 |
| V15-8 | 命中回合 `memory_status` 置 `skipped`，不进 VOICE-MEM-01 |
| V15-9 | 检测对象为用户 ASR final 与 AI 有效文本**双向**。AI 侧命中属严重人格事故，除记录外须告警 |
| V15-10 | P1 不增加应用层加密；以独立隔离表、RBAC 和逐次读取审计实现访问隔离 |

**V15-1 默认文案**（作为 `voice_call_script` 初始值，可后台发布覆盖）

- 通话页提示条：「如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。」
- 独立系统资源卡片：「如果你可能马上伤害自己，请立即拨打 110/120，并请一位可信任的人来到你身边；也可以拨打 12356 心理援助热线。」

**关键依据**

- P1 PRD v2 完全没有危机干预章节，而 P0 用四条决策专门定义了它。这使第 3 组的发现从「漏了常规内容安全」升级为「漏了曾明确决策要做的危机干预」。第 3 组只定到 `banned_keywords` 级别，覆盖不到这块。
- 危机原文若存进 `voice_call_turn`，会被会前小包（V2-4）与 CALL-SUM-01 摘要读到，违反 P0 C16 的「脱离记忆系统、不参与召回、不被角色感知」。独立表是唯一能保证不被角色感知的做法。
- V15-1 选低干扰常驻提示条而非角色口吻关心（P0 原倾向），纯粹是可实施性问题：后者要求「当前回合注入并生效」，依赖 `supports_current_turn_rag_gate`，第 8 组已确认零证据。**安全底线不能建在未取证能力上。** 取证通过后可将角色口吻关心作为增强（她先说一句关心，提示条同时在下方出现）。
- 纯关键词在此场景误报率不低（「我要死了」「累死了」等日常表达）。低干扰形态对误报更宽容——误报时用户只看到一条不相关提示条，不会被弹窗打断。
- 与人格铁律的张力：项目规定「永不承认是 AI」「不说教不评判」，危机资源展示本质是一次跳出角色的系统干预。安全优先于沉浸，但干预形式应尽量降低破坏程度。
- 语音检测最早时机是 ASR final（用户说完一句之后），此延迟为固有限制。
- 交互规格 18 张高保真页中**没有任何危机资源展示 UI**，需新增：通话页提示条组件 + 一种时间线卡片类型。

---

### 第 16 组：里程碑契约生命周期与 STEP 验收锚点

本组只修正执行编排和验收归属，不改变任何产品、接口、数据、权限、文案或 UI 事实。

| 编号 | 决策 |
|---|---|
| V16-1 | 对应实现 STEP 同期产出并验证契约增量，不直接改写 `docs/contract/current/`；全部里程碑业务验收通过后，由里程碑编排统一整合现行契约并发起合并后验证。O-04 仍阻塞 Open API 兼容策略、STEP-021 契约增量子任务及整步 DONE，内部卡片实现可先行 |
| V16-2 | 每个 STEP 必须绑定本系统层可直接观察的验收锚点。业务行为优先绑定 AC/CSTR；迁移、结构和基础设施 STEP 可以绑定直接需求、测试与完成标志，不得借前置关系代领下游业务 AC，也不得为满足格式补造验收事实 |

---

## 2. 技术债清单（本次新增）

| 编号 | 内容 | 风险等级 |
|---|---|---|
| TD-V-01 | ActionScore 活跃度权重不含语音，纯语音用户权重恒为 0，主动消息静默发不出 | 中 |
| TD-V-02 | P1 长期沉默的「历史对话 ≥10 轮」不含语音 | 低 |
| TD-V-03 | P3 凌晨在线判定不含语音（语音中的失眠/熬夜关键词不触发） | 低 |
| TD-V-04 | 人格偏离率语音口径未并入既有看板（语音单列，分母不含语音） | 低 |
| TD-V-05 | 通话进行中不抑制文字主动消息投递，可能出现「一边通话一边问在不在忙」的穿帮 | 中 |
| TD-V-06 | 语音里说的约定不触发后续主动消息（不碰 Future 单槽）；后续版本考虑给语音独立槽位 | 低 |
| TD-V-07 | 账号注销移出 P1；后续由独立账号注销项目完成 MySQL、Redis、DashVector、任务表及可控 Provider 用户上下文的全量清理 | 高 |

## 3. 已知约束（非技术债，本期设计选择）

| 编号 | 内容 |
|---|---|
| CS-V-01 | 语音凭据不支持后台热切，改 key 需改 env 并重启（同 TD-012 性质） |
| CS-V-02 | 句级内容安全拦截待 Phase 2（依赖第 8 组能力取证） |
| CS-V-03 | 单实例部署前提，本期不具备水平扩展能力 |
| CS-V-04 | 仅支持独立浏览器，微信内置浏览器走阻断页 |
| CS-V-05 | 未完话题只在语音会前小包生效，文字聊天侧无法召回接续 |
| CS-V-06 | 危机识别仅覆盖自伤/自杀倾向，纯关键词匹配，隐晦表达可能漏检 |
| CS-V-07 | 危机干预本期仅语音，文字侧同样内容无响应 |
| CS-V-08 | 重连后上下文断层（能力未取证时），靠衔接话术缓和 |
| CS-V-09 | 关系推进速度相对纯文字翻倍（全渠道日上限 200 点） |

## 4. 本期明确不做但已预留

| 内容 | 预留方式 |
|---|---|
| 林小梦主动呼入 | `voice_call.initiated_by` 字段，本期恒为 `user` |
| 前端埋点通道 | 无（权限与能力检测结果随预检请求回传） |
| 语音专属 Future 槽位 | 记 TD-V-06，本期不碰单槽 |
| 逐轮语音情绪 | 本期整通一条存 `voice_call`，将来可扩到 `voice_call_turn` |
| 预检阻断的按用户回溯 | 本期走服务端指标；需要时再补尝试表，`voice_call` 结构不变 |
| 账号注销全量清理 | 移出 P1，登记 TD-V-07；P1 仅保留后台单通删除且不级联已成功写入的长期记忆 |

## 5. 仍未定项与已收口项

### 5.1 仍未定项

| 编号 | 内容 | 阻塞对象 |
|---|---|---|
| O-01 | 六项能力位的真实取证结论（Go/No-Go 报告） | 打断语义、上下文截断、句级播报、重连恢复、成本对账 |
| O-04 | 是否已有真实第三方接入 Open API v1（决定 V5-2 是否属于对外契约破坏性变更） | 第 5 组落地 |

### 5.2 本轮已收口

| 原编号 | 收口结果 |
|---|---|
| O-02 | 按 V8-2：六维证据指纹、默认 30 天（可配 7–90 天）、变化或到期自动 `stale`；运行时按 `false` 降级并退出 `all`，只能经审计在 `test` 强制启用 |
| O-03 | 按 V4-6：必填 `Idempotency-Key`、UUID ≤64、同用户唯一、24 小时重放与 409 冲突语义 |
| O-05 | 按 V11-6：关系阶段窗口默认值、`Asia/Shanghai`、左闭右开、0–20 分钟抖动、最多顺延 24 小时，均由 `voice_call_config` 发布配置承载 |
| O-06 | 按 V4-7/V8-3/V15-1：结束页、异常、重连与危机文案及行为边界定稿，均作为 `voice_call_script` 初始默认值 |

## 6. 文档回写清单

本轮已同步回写 PRD 与 STEP 的执行编排口径。现行 Open API / chat-emotion 契约不在实现 STEP 中提前改写；对应 STEP 只产出并验证契约增量，全部里程碑通过后统一整合。其他无关文档不在修改范围。

### PRD-LXM语音通话仿真交互设计-v2.md

| 位置 | 修改 |
|---|---|
| §11.3 | `memory_type` 示例改真实取值；Stable Key 改三层并补 value ≤100 汉字约束；限定只可写 `user` / `character_private` |
| §11.4 | 溯源字段从向量 `fields` 改为 MySQL 独立台账 |
| §12.4 | CALL-SUM-01 输出补 `emotion` 与 `unfinished_topics` 的落库位置（均在 `voice_call`） |
| §14.3 | 补 `summary_status` 四态；补 `sort_seq` 分配规则；明确前端须新增 `source=call` 分支 |
| §15.1 | 移除 `preflight`；终态四分；`end_reason` 补至九项 |
| §15 | `voice_call` 新增：情绪字段、`unfinished_topics`、`initiated_by` |
| §21.1 | 前端埋点改为「本期不做通道，权限与能力检测结果随预检回传」 |
| §21.2 | 标注四项依赖未取证能力的指标为「能力位 false 时不可测」；成本改为估算口径 + 差异率指标 |
| 能力位章节 | 删除 `capability_gray` 按用户维度；默认全 `false` |
| `persona_ref` | 改为 `version` + 正文 `sha256` |
| 新增章节 | 危机内容识别与响应（第 15 组全部内容） |
| 新增条目 | 预检须校验 `User.is_banned` |

### DESIGN-LXM语音通话后台配置与管理-v1.md

| 位置 | 修改 |
|---|---|
| §7 | 配置拆为 `voice_call_config`（`tech_ops` 写）与 `voice_call_script`（`ai_trainer` 写） |
| §7 | `base_version` 复用生效行 `version`；`draft_revision` 为新增可空列；草稿保存带乐观锁 |
| §7 | `credential_ref` 改为 env 变量名 + 已/未配置状态；显式声明不支持后台热切 |
| §7 | 卡点一改为参数取值范围校验 |
| §7 | 配置在通话开始时快照锁定，通话期间不重读 |
| §12 | 通话导出挂 `deny_observer_export`；通话文本对 `ai_trainer` 不可见 |
| 新增 | 单实例部署前提；软停/硬停两级紧急停用（归 `tech_ops`）；租约 owner token 与续租/对账机制 |
| 新增 | 危机记录页（仅 `super_admin`，查看写审计） |

### LXM语音通话交互规格与PRD映射-v1.md

| 位置 | 修改 |
|---|---|
| Demo 映射表 | 修正 3 处 AC 引用（见第 13 组 A） |
| §8 | 「30 秒缓冲计费口径为 Q8 TBD」改为「免费，不扣减」 |
| §9.1 | `UI-RESOLVED-*` 六条移到独立的「已确认设计决策」小节 |
| §9.2 | 删除已定稿的七项（Q6/Q7/Q8/Q9/Q10/Q11/Q12），仅保留 Q1/Q2/Q3 能力取证 |
| §10.2 | 「重连成功后恢复真实回合状态」改为「能力未取证时接受上下文断层，由角色说衔接语」 |
| 新增 | 危机提示条与危机资源卡片的交互规格；说明硬顶无独立页面 |
| Demo 12 | 说明文件名与语义不符（实为额度不足） |

### 其他

| 文档 | 修改 |
|---|---|
| `docs/progress/林小梦实时语音-Phase0_progress.md` | 显式区分「工具就绪」与「取证完成」两个状态，不再以 16/16 100% 表述整体完成 |
| `docs/design/realtime_voice/P0/决策记录-林小梦实时语音通话-v2.md` | 标为历史文档，注明被 P1 PRD v2 取代及 C2/C7/C8/C10/C11/C20/C26 作废 |
| P1 本地技术债清单 | TD-V-01～TD-V-07 只在 P1 权威文档与 STEP 中维护，不写入迁移冻结的全局 TD-001～TD-037 集合 |
| `docs/contract/current/openapi/api.md` / `docs/contract/current/chat-emotion/api.md` / `docs/design/openapi/open-api-v1.md` | 时间线实现 STEP 同期产出并验证新增 5 字段与 `source=call` 的契约增量；全部里程碑通过后统一整合，根 `docs/contract.md` 仅在入口路由变化时更新 |

## 7. 版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-08-26 | 首次确认 15 组决策与 O-01～O-06 |
| v1.1 | 2026-08-29 | 收口 O-02/O-03/O-05/O-06；同步权限、卡片矩阵、保留期、默认文案与账号注销延期边界；PRD 同步回写 |
| v1.2 | 2026-08-30 | 收口正式 STEP 复审识别的三项来源缺口：冻结 missed 首发逐字文案、MySQL 独立追加式能力证据记录，以及多窗口范围/重叠校验和无副作用预览契约 |
| v1.3 | 2026-08-30 | 只修正执行编排口径：实现 STEP 产出并验证契约增量、全部里程碑后统一整合现行契约；STEP 使用本系统层可直接观察的 AC/CSTR 或技术验收锚点，禁止基础设施代领业务 AC；产品事实与 O-01/O-04 不变 |
