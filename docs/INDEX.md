# 文档索引

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> LLM 与人工查阅的默认入口（2026-07-19）。机器路由以 [llm-manifest.json](llm-manifest.json) 为准；契约正文以 `contract/current/` 为准。

## 默认读取边界

- 默认扫描：本索引、[contract.md](contract.md)、`contract/current/`、[contract/known-gaps.md](contract/known-gaps.md)、[tech-debt.md](tech-debt.md)、`tech-debt/active/`、`requirement-pool/`。
- 默认排除：`.doc-migration-baseline/`、`contract/history/`、`design/realtime_voice/P1/history/`、`contract/drafts/`、`tech-debt/archive/`、`design/memory-retrieval/history/`。
- 基线、历史、草案和归档只有在用户明确要求对应操作时才读取，不作为当前权威依据。

## 功能 / 任务 → 必读契约

| 任务或功能 | 当前权威入口 | 技术债 |
|---|---|---|
| 全局响应、错误码、分页、时间、SSE | [共享约定](contract/current/_shared/conventions.md) | [总索引](tech-debt.md) |
| Admin JWT、角色、observer、权限 | [认证与 RBAC](contract/current/_shared/auth-rbac.md) | [账号与认证](tech-debt/active/core-user-auth.md) |
| 用户、登录、设置、密码 | [接口](contract/current/core-user-auth/api.md) · [数据](contract/current/core-user-auth/data.md) | [账号与认证](tech-debt/active/core-user-auth.md) |
| 未登录开放、登录弹窗、访客态 | [H5 页面策略](contract/current/h5-app/api.md) · [Feed 可选鉴权](contract/current/life-feed/api.md) | [总索引](tech-debt.md) |
| BGM 背景音乐、管理库与处理操作 | [接口与播放器](contract/current/bgm/api.md) · [数据](contract/current/bgm/data.md) · [后台](contract/current/bgm/admin-ui.md)；[V1.3 版本完结与保留项](design/bgm_music/steps-verified.md#bgm-v13-closure) | — |
| H5 应用入口 | [接口](contract/current/h5-app/api.md) | [总索引](tech-debt.md) |
| 实时语音、结束、占用残留、异常结算恢复 | [接口](contract/current/realtime-voice/api.md) · [数据](contract/current/realtime-voice/data.md) · [后台](contract/current/realtime-voice/admin-ui.md) | [实时语音 TD-038](tech-debt/active/realtime-voice.md#td-038) |
| 实时语音配置发布、测试能力与后台音色筛选的 P1 延期问题 | [后台契约](contract/current/realtime-voice/admin-ui.md)；原 P1 延期目标保留 | [TD-041](tech-debt/active/realtime-voice.md#td-041) · [TD-042](tech-debt/active/realtime-voice.md#td-042) · [TD-043](tech-debt/active/realtime-voice.md#td-043) |
| 实时语音收尾体验候选需求 | [需求池索引](requirement-pool/README.md) · [RP-001](requirement-pool/active/realtime-voice-ending-grace/RP-001.md#rp-001)（待评估，非 PRD/契约） | — |
| 实时语音记忆抽取质量候选需求 | [需求池索引](requirement-pool/README.md) · [RP-002](requirement-pool/active/realtime-voice-memory-extraction/RP-002.md#rp-002)（待评估，非 PRD/契约） | — |
| 下一版本实时语音记忆召回升级 | [需求池索引](requirement-pool/README.md) · [RP-004](requirement-pool/active/realtime-voice-memory-recall/RP-004.md#rp-004)（本期排除，下一版本细化） | — |
| 聊天、SSE、情绪 | [接口](contract/current/chat-emotion/api.md) · [数据](contract/current/chat-emotion/data.md) | [聊天与情绪](tech-debt/active/chat-emotion.md) |
| 聊天输入后的省略号与回复展示优化 | [需求池索引](requirement-pool/README.md) · [RP-005](requirement-pool/active/chat-input-output-display/RP-005.md#rp-005)（已记录，待细化、待排期） | — |
| 记忆、知识库、Step6、向量 | [接口](contract/current/memory-knowledge/api.md) · [数据](contract/current/memory-knowledge/data.md) · [后台](contract/current/memory-knowledge/admin-ui.md) | [记忆与知识](tech-debt/active/memory-knowledge.md) |
| DashVector Collection 库名统一配置与多环境发布 | [记忆接口](contract/current/memory-knowledge/api.md) · [后台配置](contract/current/memory-knowledge/admin-ui.md) | [TD-044（最高优先级 P0）](tech-debt/active/memory-knowledge.md#td-044) |
| Step6 昵称、姓名、后续行动计划等非向量信息后台展示 | [需求池索引](requirement-pool/README.md) · [RP-006](requirement-pool/active/step6-non-vector-admin-display/RP-006.md#rp-006)（已记录，待细化、待排期） | — |
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
| `/api/admin/bgm`、`bgm_*`、`admin/pages/bgm.html` | [BGM接口](contract/current/bgm/api.md) · [数据](contract/current/bgm/data.md) · [后台](contract/current/bgm/admin-ui.md) |
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
| [H5 开场体验：设计与接入](design/h5-entry-experience/设计说明.md) | 已接入原加载构图内底部切换、授权期间保持蒙版、允许或拒绝后平缓进入；本机真实OSS播放与原生权限链路已验，方向位移使用虚拟传感器，iPhone与生产未验 |
| [H5 AppShell 改造方案 v2](design/h5-appshell/改造方案-v2-20261022.md) · [唯一 STEP 进度 §8](design/h5-appshell/steps-verified.md#8-h5-appshell-step进度) | 同文档路由、八页模块化与稳定播放；候选和源码契约已交付。2026-10-23复查4项遗漏已修复并回归，原AppShell范围27/27完成，见§8.33；并行新增开场体验的整体集成不计入本次结论；[上线前待验项](design/h5-appshell/execution/真机验收操作单.md#上线前待验清单2026-10-23复查)单列，生产未部署 |
| [记忆召回开发入口](design/memory-retrieval/README.md) · [PRD v3.2 后台闭环修正版](design/memory-retrieval/PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md) · [STEP v3.2 后台闭环修正版](design/memory-retrieval/steps-verified-v3.2-后台闭环修正版.md) | 重点文字漏召回、混淆与稍复杂查询；费用不作门槛，日常延迟/提升幅度仅记录；整轮固定180秒、同代不续时；六项评审修正及后台12个子用例已写回，文档静态复核PASS_WITH_RISKS / DOC_REVISED_WITH_GATES；最新S15：仅新DotProduct库，启用前一次性清理旧对话/向量关联数据，保留日记/朋友圈/资料数值，清画像/旧预约；分工见里程碑§2.1；M1基础设施及[M2技术设计](design/memory-retrieval/execution/STEP-002-技术方案与参数定稿.md)已核验，M3按配置→维护核心→有限恢复实施；M7证据映射（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/M7-后台闭环与兼容核验-2026-10-11.md`）及实际临时契约（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/contract-drafts/M7-临时契约.md`）仅交阶段证据；M8冻结登记（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-020-正式评测冻结-2026-10-12.json`）、真实评测阻塞证据（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-021-真实评测阻塞核验-2026-10-12.json`）、最小模板修复真实验证（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-021-最小模板修复真实验证-2026-10-12.json`）及M8实际临时契约（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/contract-drafts/M8-临时契约.md`）为本地隔离证据；最终功能核对（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-021-最终功能核对-2026-10-12.json`）保留质量非阻断取舍；批准null查询兼容核验（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-021-查询空响应兼容核验-2026-10-13.json`）已完成，022隔离准备与恢复核验（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-隔离准备与恢复核验-2026-10-13.md`）、GAP-01根因审核/下一轮裁决（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-GAP-01-根因审核-2026-10-13.json`）、回执最小修复定向核验（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-GAP-01-最小回执修复验证-2026-10-13.json`）及70项验收映射（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-验收逐项证据映射-2026-10-13.json`）保留回执修复及原阻塞时点；原run退役及新数据恢复（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-原run退役收口与新数据恢复-2026-10-13.json`）已合法闭合；181项正式契约候选（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/M8-正式契约整合映射候选-v2-2026-10-13.json`）已刷新并完成18份正式整合及验证（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/M8-正式契约整合与验证-2026-10-13.json`），CONTRACT_MERGED_VERIFIED；本地Docker实际S15与部署验收（本地留存，未随本次提交；原引用：`design/memory-retrieval/execution/evidence/STEP-022-本地Docker部署收口-2026-10-13.json`）已完成，按已接受质量风险收口；后续自动索引/新增20129修复、82项积压清零及qwen3.7-text-rerank本地部署已补记；当前完成项、验证与恢复边界唯一见[STEP §3.40](design/memory-retrieval/steps-verified-v3.2-后台闭环修正版.md#memory-v32-followup-closure)，保留AC19/20质量FAIL、缺对照及延期项，新模型未完成完整同集质量验收；旧PRD v1/v2/v3/v3.1、原验证版STEP/v3.1及过程资料见 history（本地留存，未随本次提交；原引用：`design/memory-retrieval/history/README.md`），不替代现行运行契约 |
| [主页改版 v2 PRD](design/home-redesign/PRD-林小梦主页改版-v2.md) | 本期主页已于 `2026-10-03` 由用户确认真机人工验收通过，[H5 契约](contract/current/h5-app/api.md) 已补记倾斜参数及验收来源；Q201 未启用及专项量测保留后续跟进，见 [唯一 STEP 记录 §9.21](design/home-redesign/steps-verified.md#921-本期主页人工验收通过与文档收尾2026-10-03)；旧版见 [history](design/home-redesign/history/README.md) |
| [BGM V1.3 PRD](design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md) · [唯一 STEP／结项](design/bgm_music/steps-verified.md#bgm-v13-closure) | 2026-10-21 用户确认本版开发交付完结；人工反馈及有效证据保留，手机／微信及其他未验项延期；现行契约、部署和测试资产后续待办见结项节 |
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
