# 技术债兼容索引

- 文档 ID：`tech-debt-index`
- 权威状态：`canonical`（编号、状态与详情路由）
- 默认详情：`docs/tech-debt/active/`
- 归档门禁：只有代码核验完成且用户明确确认后才移入 `archive/`

本文件保留全部 43 个编号，但不再承载详情正文。TD-001～TD-037 状态文字来自迁移源，未在本次迁移中改判；TD-038 为 2026-09-27 经确认新增，TD-039～TD-040 为 2026-09-28 核实的语音技术债；TD-041～TD-043 为 2026-09-29 经用户决定延期的 P1 问题 R03、R05、R09。

| 编号 | 原标题 | 迁移状态 | 主要功能 | 唯一详情 |
|---|---|---|---|---|
| TD-001 | users 表遗留字段待清理 | 待清偿 | `core-user-auth` | [docs/tech-debt/active/core-user-auth.md](tech-debt/active/core-user-auth.md#td-001) |
| TD-002 | 后台 Prompt 与主链 Step5 / Step5.5 热加载 — **已清偿（STEP-026，2026-05-07）** | 已清偿（原文状态，待用户确认归档） | `persona-prompt-world-state` | [docs/tech-debt/active/persona-prompt-world-state.md](tech-debt/active/persona-prompt-world-state.md#td-002) |
| TD-003 | Prompt 管理页版本历史分页失败时列表不刷新 | 待清偿 | `persona-prompt-world-state` | [docs/tech-debt/active/persona-prompt-world-state.md](tech-debt/active/persona-prompt-world-state.md#td-003) |
| TD-004 | Agent 规则（agent_rules）管理端可配、运行时未读取 | 待清偿 | `agent-future` | [docs/tech-debt/active/agent-future.md](tech-debt/active/agent-future.md#td-004) |
| TD-005 | 关系规则（relationship_rules）已入库但运行时仍读硬编码 | 待清偿 | `relationship` | [docs/tech-debt/active/relationship.md](tech-debt/active/relationship.md#td-005) |
| TD-006 | 日记历史接口已具备，管理列表页待建 — **已清偿（2026-04-07）** | 已清偿（原文状态，待用户确认归档） | `diary` | [docs/tech-debt/active/diary.md](tech-debt/active/diary.md#td-006) |
| TD-007 | 日记规则（diary_rules）已入库但生成链路未读取 — **已清偿（2026-04-07）** | 已清偿（原文状态，待用户确认归档） | `diary` | [docs/tech-debt/active/diary.md](tech-debt/active/diary.md#td-007) |
| TD-013 | 日记调度：Cron 热更新未做 + misfire 补跑仅运维手动（M2a） | 待清偿 | `diary` | [docs/tech-debt/active/diary.md](tech-debt/active/diary.md#td-013) |
| TD-014 | H5 日记列表误用 `diaries`，与契约 `items` 不一致 — **已清偿（2026-04-07）** | 已清偿（原文状态，待用户确认归档） | `diary` | [docs/tech-debt/active/diary.md](tech-debt/active/diary.md#td-014) |
| TD-008 | 统计报表：LLM 响应耗时无法按日展示 | 待清偿 | `observability-third-party` | [docs/tech-debt/active/observability-third-party.md](tech-debt/active/observability-third-party.md#td-008) |
| TD-009 | 统计报表：feature 明细缺按日 open_rate / agent_replied | 待清偿 | `observability-third-party` | [docs/tech-debt/active/observability-third-party.md](tech-debt/active/observability-third-party.md#td-009) |
| TD-010 | 系统监控：`alerts[]` 无单条发生时间，前端用刷新时刻代替 | 待清偿 | `observability-third-party` | [docs/tech-debt/active/observability-third-party.md](tech-debt/active/observability-third-party.md#td-010) |
| TD-011 | 系统监控：`get_system_status` 在 Redis INFO 异常时可能 `NameError` | 待清偿 | `observability-third-party` | [docs/tech-debt/active/observability-third-party.md](tech-debt/active/observability-third-party.md#td-011) |
| TD-012 | 第三方服务配置（`third_party:`*）已可落库，业务运行时未读取 | 待清偿 | `observability-third-party` | [docs/tech-debt/active/observability-third-party.md](tech-debt/active/observability-third-party.md#td-012) |
| TD-015 | H5 对话调度与持久化：单路 SSE、落库时机 vs「历史 / 新消息」队列体验（**部分清偿 · 2026-05-11：主链 + H5 连发（无 `sending`、300ms 防抖 + IME）+ 契约已同步；2026-08-21：再进页接上 `pending_llm` 仍待后续排期**） | 部分完成（原文状态） | `chat-emotion` | [docs/tech-debt/active/chat-emotion.md](tech-debt/active/chat-emotion.md#td-015) |
| TD-016 | 按轮情绪（`round_id`）与后台「情绪日志」只读展示（**V2-A/B/C 已交付；广义后台情绪运营见 TD-020**） | 已处理（原文状态，待用户确认归档） | `chat-emotion` | [docs/tech-debt/active/chat-emotion.md](tech-debt/active/chat-emotion.md#td-016) |
| TD-017 | 记忆检索：查询改写 / LLM 重写检索 query（**部分清偿 · 2026-05-30**） | 部分完成（原文状态） | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-017) |
| TD-018 | 日记「当日有互动」与仅失败 / 未闭环 user 行语义（**待清偿**） | 待清偿 | `diary` | [docs/tech-debt/active/diary.md](tech-debt/active/diary.md#td-018) |
| TD-019 | H5 多 Tab 同账号并行聊天：各 Tab 独立 SSE 会话，未跨 Tab 同步「当前有效代」（**待评估**） | 待评估 | `chat-emotion` | [docs/tech-debt/active/chat-emotion.md](tech-debt/active/chat-emotion.md#td-019) |
| TD-020 | 用户短期情绪属性：与句级 / 轮级情绪分层及展示「真相源」（**进行中 · V3-A，2026-04-15**） | 部分完成（原文状态） | `chat-emotion` | [docs/tech-debt/active/chat-emotion.md](tech-debt/active/chat-emotion.md#td-020) |
| TD-021 | 林小梦活动状态描述：当前为静态 JSON 占位，完整活动计划功能待建（**待清偿**） | 待清偿 | `persona-prompt-world-state` | [docs/tech-debt/active/persona-prompt-world-state.md](tech-debt/active/persona-prompt-world-state.md#td-021) |
| TD-022 | 用户记忆双轨并存：MySQL「列表记忆」与 Step6 四路向量未收敛（**已清偿**） | 已清偿（原文状态，待用户确认归档） | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-022) |
| TD-023 | 用户记忆跨源合并与去重口径待统一（**已缓解**） | 部分完成（原文状态） | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-023) |
| TD-024 | H5 设置页用户偏好开关后端未实现（**部分清偿**） | 部分完成（原文状态） | `core-user-auth` | [docs/tech-debt/active/core-user-auth.md](tech-debt/active/core-user-auth.md#td-024) |
| TD-026 | Step6/Admin 前写入的 DashVector 文档缺少 key_l1/key_l2（**待清偿**） | 待清偿 | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-026) |
| TD-027 | Step2 补充路触发阈值与 top_k 未纳入热配（**待清偿**） | 待清偿 | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-027) |
| TD-028 | Step6 四类 KV 写入前缺少「多 key 挤一行」检测与阻断（**L4 · 待清偿**） | 待清偿 | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-028) |
| TD-029 | Step6 四类 KV 同行多 key 无自动拆分/重试修复（**L5 · 待清偿**） | 待清偿 | `memory-knowledge` | [docs/tech-debt/active/memory-knowledge.md](tech-debt/active/memory-knowledge.md#td-029) |
| TD-025 | H5 改密码前后端契约不一致（**待清偿**） | 待清偿 | `core-user-auth` | [docs/tech-debt/active/core-user-auth.md](tech-debt/active/core-user-auth.md#td-025) |
| TD-030 | 内容安全 `failed_blocked` 未纳入叹号重发窗口（H5 / Open 共用，**待清偿**） | 待清偿 | `cross-cutting` | [docs/tech-debt/active/cross-cutting.md](tech-debt/active/cross-cutting.md#td-030) |
| TD-031 | Open API `check_send_quota`（10104）为非原子「先 SELECT 再 INSERT」（**待清偿**） | 待清偿 | `openapi` | [docs/tech-debt/active/openapi.md](tech-debt/active/openapi.md#td-031) |
| TD-032 | 朋友圈全屏预览手势与浏览器返回冲突（**已处理 · 现有兼容性说明**） | 已处理（原文状态，待用户确认归档） | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-032) |
| TD-033 | 日生活计划后台「LLM 日志摘要」未实现（**待清偿**） | 待清偿 | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-033) |
| TD-034 | 生活流部分管理列表仍用无样式的 `data-table`（**已清偿** · 2026-07-09） | 已清偿（原文状态，待用户确认归档） | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-034) |
| TD-035 | 朋友圈帖子「真删除」与「隐藏/下架」未分离（**待清偿**） | 待清偿 | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-035) |
| TD-036 | 后台朋友圈本地图片上传未实现（**待清偿**） | 待清偿 | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-036) |
| TD-037 | 朋友圈空态未对齐 UI 规范（插画 + 指定文案）（**待清偿**） | 待清偿 | `life-feed` | [docs/tech-debt/active/life-feed.md](tech-debt/active/life-feed.md#td-037) |
| TD-038 | 解耦通话结束与结算，补齐异常补偿及人工修复 | 待清偿 | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-038) |
| TD-039 | 语音设置的语气说明可发布但未进入实际会话 | 待清偿 | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-039) |
| TD-040 | 清理未调用的显式结束语义分类器 | 待清偿 | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-040) |
| TD-041 | R03：运行配置发布与回滚缺目标绑定的连接预检 | 待清偿（P1 延期） | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-041) |
| TD-042 | R05：强制 test 能力未贯通测试用户的实际通话 | 待清偿（P1 延期） | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-042) |
| TD-043 | R09：后台通话列表缺按 voice_id 筛选 | 待清偿（P1 延期） | `realtime-voice` | [docs/tech-debt/active/realtime-voice.md](tech-debt/active/realtime-voice.md#td-043) |
