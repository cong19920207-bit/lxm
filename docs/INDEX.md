# 文档索引

> LLM 与人工查阅的默认入口（2026-07-19）。机器路由以 [llm-manifest.json](llm-manifest.json) 为准；契约正文以 `contract/current/` 为准。

## 默认读取边界

- 默认扫描：本索引、[contract.md](contract.md)、`contract/current/`、[contract/known-gaps.md](contract/known-gaps.md)、[tech-debt.md](tech-debt.md)、`tech-debt/active/`、`requirement-pool/`。
- 默认排除：`.doc-migration-baseline/`、`contract/history/`、`design/realtime_voice/P1/history/`、`contract/drafts/`、`tech-debt/archive/`。
- 基线、历史、草案和归档只有在用户明确要求对应操作时才读取，不作为当前权威依据。

## 功能 / 任务 → 必读契约

| 任务或功能 | 当前权威入口 | 技术债 |
|---|---|---|
| 全局响应、错误码、分页、时间、SSE | [共享约定](contract/current/_shared/conventions.md) | [总索引](tech-debt.md) |
| Admin JWT、角色、observer、权限 | [认证与 RBAC](contract/current/_shared/auth-rbac.md) | [账号与认证](tech-debt/active/core-user-auth.md) |
| 用户、登录、设置、密码 | [接口](contract/current/core-user-auth/api.md) · [数据](contract/current/core-user-auth/data.md) | [账号与认证](tech-debt/active/core-user-auth.md) |
| 未登录开放、登录弹窗、访客态 | [H5 页面策略](contract/current/h5-app/api.md) · [Feed 可选鉴权](contract/current/life-feed/api.md) | [总索引](tech-debt.md) |
| H5 应用入口 | [接口](contract/current/h5-app/api.md) | [总索引](tech-debt.md) |
| 实时语音、结束、占用残留、异常结算恢复 | [接口](contract/current/realtime-voice/api.md) · [数据](contract/current/realtime-voice/data.md) · [后台](contract/current/realtime-voice/admin-ui.md) | [实时语音 TD-038](tech-debt/active/realtime-voice.md#td-038) |
| 实时语音配置发布、测试能力与后台音色筛选的 P1 延期问题 | [后台契约](contract/current/realtime-voice/admin-ui.md)；原 P1 延期目标保留 | [TD-041](tech-debt/active/realtime-voice.md#td-041) · [TD-042](tech-debt/active/realtime-voice.md#td-042) · [TD-043](tech-debt/active/realtime-voice.md#td-043) |
| 实时语音收尾体验候选需求 | [需求池索引](requirement-pool/README.md) · [RP-001](requirement-pool/active/realtime-voice-ending-grace/RP-001.md#rp-001)（待评估，非 PRD/契约） | — |
| 实时语音记忆抽取质量候选需求 | [需求池索引](requirement-pool/README.md) · [RP-002](requirement-pool/active/realtime-voice-memory-extraction/RP-002.md#rp-002)（待评估，非 PRD/契约） | — |
| 聊天、SSE、情绪 | [接口](contract/current/chat-emotion/api.md) · [数据](contract/current/chat-emotion/data.md) | [聊天与情绪](tech-debt/active/chat-emotion.md) |
| 记忆、知识库、Step6、向量 | [接口](contract/current/memory-knowledge/api.md) · [数据](contract/current/memory-knowledge/data.md) · [后台](contract/current/memory-knowledge/admin-ui.md) | [记忆与知识](tech-debt/active/memory-knowledge.md) |
| 日记与时区 | [接口](contract/current/diary/api.md) · [数据](contract/current/diary/data.md) · [后台](contract/current/diary/admin-ui.md) | [日记](tech-debt/active/diary.md) |
| 关系成长 | [接口](contract/current/relationship/api.md) · [数据](contract/current/relationship/data.md) · [后台](contract/current/relationship/admin-ui.md) | [关系](tech-debt/active/relationship.md) |
| Agent、Future、主动消息 | [接口](contract/current/agent-future/api.md) · [数据](contract/current/agent-future/data.md) · [后台](contract/current/agent-future/admin-ui.md) | [Agent](tech-debt/active/agent-future.md) |
| 人格、Prompt、世界状态、安全 | [接口](contract/current/persona-prompt-world-state/api.md) · [数据](contract/current/persona-prompt-world-state/data.md) · [后台](contract/current/persona-prompt-world-state/admin-ui.md) | [人格与 Prompt](tech-debt/active/persona-prompt-world-state.md) |
| 朋友圈、生活流 | [接口](contract/current/life-feed/api.md) · [数据](contract/current/life-feed/data.md) · [后台](contract/current/life-feed/admin-ui.md) | [生活流](tech-debt/active/life-feed.md) |
| 管理账号、用户、操作日志 | [接口](contract/current/admin-security-accounts/api.md) · [数据](contract/current/admin-security-accounts/data.md) | [账号与认证](tech-debt/active/core-user-auth.md) |
| 统计、系统监控、第三方 | [接口](contract/current/observability-third-party/api.md) · [后台](contract/current/observability-third-party/admin-ui.md) | [可观测性](tech-debt/active/observability-third-party.md) |
| OpenAPI、API Key、resend | [接口](contract/current/openapi/api.md) · [数据](contract/current/openapi/data.md) | [OpenAPI](tech-debt/active/openapi.md) · [跨功能](tech-debt/active/cross-cutting.md) |

## 路由 / 表名 / 代码路径 → 文档

| 检索信号 | 必读文档 |
|---|---|
| `/api/voice`、`/api/admin/voice`、`voice_*`、`realtime_voice_*` | [语音接口](contract/current/realtime-voice/api.md) · [语音数据](contract/current/realtime-voice/data.md) · [语音后台](contract/current/realtime-voice/admin-ui.md) |
| `/api/chat`、`conversation_log`、`emotion_log`、`backend/routers/chat.py` | [聊天接口](contract/current/chat-emotion/api.md) · [聊天数据](contract/current/chat-emotion/data.md) |
| `/api/memory`、`memory`、`step6_orchestrator.py` | [记忆接口](contract/current/memory-knowledge/api.md) · [记忆数据](contract/current/memory-knowledge/data.md) |
| `/api/diary`、`ai_diary`、`ai_diary_task.py` | [日记接口](contract/current/diary/api.md) · [日记数据](contract/current/diary/data.md) |
| `/api/relationship`、`relationship_*` | [关系接口](contract/current/relationship/api.md) · [关系数据](contract/current/relationship/data.md) |
| `/api/agent`、`agent_message`、`future_handler.py` | [Agent 接口](contract/current/agent-future/api.md) · [Agent 数据](contract/current/agent-future/data.md) |
| `/api/feed`、`feed_*`、`life_feed_task.py` | [生活流接口](contract/current/life-feed/api.md) · [生活流数据](contract/current/life-feed/data.md) |
| `get_current_user_optional`、`lxm_open_login_once`、`/api/app/persona-background`、登录弹窗、未登录 | [H5 页面策略](contract/current/h5-app/api.md) · [生活流接口](contract/current/life-feed/api.md) |
| `/api/open/v1`、`user_api_keys`、`backend/routers/open/` | [OpenAPI 接口](contract/current/openapi/api.md) · [OpenAPI 数据](contract/current/openapi/data.md) |
| `admin/pages/`、`frontend/pages/`、全部路由/模型/任务归属 | [代码面覆盖表](contract/code-surface-coverage.md) |

## 产品需求与设计

| 入口 | 内容 |
|---|---|
| [design/README.md](design/README.md) | 按功能分类的 PRD、开发步骤、实施计划与审查文档 |
| [主页改版 v2 PRD](design/home-redesign/PRD-林小梦主页改版-v2.md) | 本地实现及 [H5 契约](contract/current/h5-app/api.md) 已同步；真机倾斜、声音、性能与部署验收待补，当前状态见 [唯一 STEP 进度](design/home-redesign/steps-verified.md#9-林小梦主页改版-v2-step-进度)；旧版见 [history](design/home-redesign/history/README.md) |
| [design/DESIGN_SYSTEM.md](design/DESIGN_SYSTEM.md) | 设计系统 |
| [design/product-development-plan-h5-chat.md](design/product-development-plan-h5-chat.md) | H5 对话产品开发方案 |
| [design/chat-message-pipeline.md](design/chat-message-pipeline.md) | 消息管线说明 |

## 工程协作资料

| 入口 | 内容 |
|---|---|
| [VERSIONS.md](VERSIONS.md) | 产品版本与发布切片 |
| [progress/](progress/) | 专项迭代进度 |
| [refactor/chat/](refactor/chat/) | 对话 / H5 改造资料 |
| [refactor/diary/](refactor/diary/) | AI 日记改造资料 |
| [testing/reports/](testing/reports/) | 验收与 E2E 报告 |
| [testing/checklists/](testing/checklists/) | 手工回归清单 |
| [testing/guides/](testing/guides/) | 测试、trace 与排障说明 |
| [ops/docker-admin-deploy.md](ops/docker-admin-deploy.md) | Docker / Admin 部署与 Alembic 升级 |
| [ops-diary.md](ops-diary.md) | 日记时区、批跑与发布注意 |

## 需求定稿与 Prompt

| 入口 | 内容 |
|---|---|
| [../doc/chat/](../doc/chat/) | 对话链路需求确认与输入流程 |
| [../doc/prompts/](../doc/prompts/) | Step5 / Step5.5 Prompt 定稿 |
| [../doc/memory/prd/](../doc/memory/prd/) | 记忆专项 PRD |
| [../doc/memory/steps/](../doc/memory/steps/) | 记忆专项开发步骤 |

## 维护与核验

- [known-gaps.md](contract/known-gaps.md) 保存旧文档原有缺口与执行时发现的盘点差异，不把旧缺失伪装成已覆盖。
- `scripts/verify_docs_structure.py` 校验结构、关系、覆盖、链接、基线和八类检索演练。
- `scripts/build_legacy_snapshot.py --date YYYY-MM-DD` 仅在用户明确要求时创建新快照；同日期目录存在时拒绝覆盖。
