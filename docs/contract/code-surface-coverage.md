# 代码面反向契约覆盖

- 文档 ID：`contract-code-surface-coverage`
- 权威状态：`canonical`
- 功能范围：`routing`
- 必读依赖：`docs/llm-manifest.json`
- 相关技术债：无

> 执行时实际盘点为 200 个路由装饰器；计划中的 194 是较早盘点值。差异保留为可见事实，不将新增路由伪装成迁移遗漏。

| 类型 | 数量 |
|---|---:|
| 路由 | 200 |
| 模型 | 26 |
| 后台页面 | 35 |
| H5 页面 | 8 |
| 调度任务 | 13 |

H5 页面的未登录浏览、共享登录弹窗与 `401` 策略以 `contract-h5-app-api` 为准；下表主契约仍按页面业务模块归属。Feed 匿名 list/header 另见 `contract-life-feed-api`。

## 明细

| 类型 | 代码位置 | 功能范围 | 契约文档 |
|---|---|---|---|
| 路由 | `backend/main.py:202` | `shared-conventions` | `contract-shared-conventions` |
| 路由 | `backend/main.py:207` | `shared-conventions` | `contract-shared-conventions` |
| 路由 | `backend/main.py:216` | `shared-conventions` | `contract-shared-conventions` |
| 路由 | `backend/main.py:221` | `shared-conventions` | `contract-shared-conventions` |
| 路由 | `backend/main.py:230` | `shared-conventions` | `contract-shared-conventions` |
| 路由 | `backend/routers/admin/accounts.py:98` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/accounts.py:111` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/accounts.py:163` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/accounts.py:213` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/accounts.py:254` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/accounts.py:289` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/agent_aware_mgmt.py:67` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_aware_mgmt.py:121` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_aware_mgmt.py:142` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_aware_mgmt.py:166` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_aware_mgmt.py:188` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:57` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:69` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:140` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:152` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:200` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:222` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/agent_mgmt.py:259` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/admin/auth.py:94` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/auth.py:173` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/auth.py:192` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/chat_prompt_view.py:22` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/chat_prompt_view.py:33` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/chat_prompt_view.py:44` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/chat_prompt_view.py:55` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/emotion_config.py:37` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/emotion_config.py:49` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/admin/feed_comment_mgmt.py:59` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_comment_mgmt.py:104` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_comment_mgmt.py:125` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_comment_mgmt.py:152` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_comment_mgmt.py:171` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:122` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:154` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:177` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:209` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:231` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:278` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:420` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/feed_mgmt.py:434` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/knowledge_mgmt.py:42` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/knowledge_mgmt.py:65` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/knowledge_mgmt.py:96` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/knowledge_mgmt.py:128` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/life_config_mgmt.py:73` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_config_mgmt.py:101` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_config_mgmt.py:119` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_config_mgmt.py:142` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:105` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:134` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:167` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:197` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:219` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:262` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:280` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:346` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:378` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:408` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:457` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/life_plan_mgmt.py:505` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:111` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:125` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:161` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:193` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:301` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:360` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/memory_mgmt.py:426` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/operation_logs.py:44` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/operation_logs.py:123` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/operation_logs.py:155` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/persona.py:93` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:118` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:130` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:154` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:169` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:192` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:239` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:256` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/persona.py:293` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:137` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:160` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:165` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:178` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:189` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:234` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:245` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:273` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:298` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:321` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:326` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:363` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:374` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:421` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:432` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:460` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:485` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:508` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:513` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:526` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:537` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:580` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:591` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/prompt_mgmt.py:616` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/relationship_mgmt.py:57` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/admin/relationship_mgmt.py:69` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/admin/relationship_mgmt.py:198` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/admin/relationship_mgmt.py:210` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/admin/relationship_mgmt.py:281` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/admin/safety_rules.py:73` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/safety_rules.py:92` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/safety_rules.py:107` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/safety_rules.py:122` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/safety_rules.py:137` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/stats.py:50` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/stats.py:60` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/stats.py:85` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/stats.py:127` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/stats.py:213` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:75` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:163` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:376` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:464` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:723` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/system_monitor.py:794` | `observability-third-party` | `contract-observability-api` |
| 路由 | `backend/routers/admin/test_cases.py:46` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/test_cases.py:73` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/test_cases.py:133` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/users.py:54` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:161` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:258` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:398` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:644` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:661` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:678` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:696` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:714` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:731` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:748` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:766` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:786` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:820` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:840` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:899` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/users.py:973` | `admin-security-accounts` | `contract-admin-security-api` |
| 路由 | `backend/routers/admin/vector_config.py:143` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/vector_config.py:156` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/vector_config.py:211` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/vector_config.py:224` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/admin/world_state_mgmt.py:35` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/world_state_mgmt.py:47` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/world_state_mgmt.py:82` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:100` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:163` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:177` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:204` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:244` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:268` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:291` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/admin/worldview_mgmt.py:325` | `persona-prompt-world-state` | `contract-persona-api` |
| 路由 | `backend/routers/agent.py:21` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/agent.py:57` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/agent.py:88` | `agent-future` | `contract-agent-future-api` |
| 路由 | `backend/routers/app.py:27` | `h5-app` | `contract-h5-app-api` |
| 路由 | `backend/routers/auth.py:104` | `core-user-auth` | `contract-core-user-auth-api` |
| 路由 | `backend/routers/auth.py:151` | `core-user-auth` | `contract-core-user-auth-api` |
| 路由 | `backend/routers/auth.py:222` | `core-user-auth` | `contract-core-user-auth-api` |
| 路由 | `backend/routers/auth.py:249` | `core-user-auth` | `contract-core-user-auth-api` |
| 路由 | `backend/routers/chat.py:719` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/chat.py:757` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/chat.py:781` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/chat.py:825` | `chat-emotion` | `contract-chat-emotion-api` |
| 路由 | `backend/routers/diary.py:22` | `diary` | `contract-diary-api` |
| 路由 | `backend/routers/diary.py:71` | `diary` | `contract-diary-api` |
| 路由 | `backend/routers/feed.py:36` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:48` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:58` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:68` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:78` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:92` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:106` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:125` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:164` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/feed.py:178` | `life-feed` | `contract-life-feed-api` |
| 路由 | `backend/routers/memory.py:19` | `memory-knowledge` | `contract-memory-knowledge-api` |
| 路由 | `backend/routers/open/agent.py:19` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/open/agent.py:28` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/open/agent.py:37` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/open/chat.py:17` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/open/chat.py:26` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/open/chat.py:34` | `openapi` | `contract-openapi-api` |
| 路由 | `backend/routers/relationship.py:15` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/relationship.py:26` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/relationship.py:37` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/routers/relationship.py:48` | `relationship` | `contract-relationship-api` |
| 路由 | `backend/utils/admin_auth.py:159` | `core-user-auth` | `contract-core-user-auth-api` |
| 模型 | `backend/models/admin_config.py:12` | `admin-security-accounts` | `contract-admin-security-data` |
| 模型 | `backend/models/admin_operation_log.py:13` | `core-user-auth` | `contract-core-user-auth-data` |
| 模型 | `backend/models/admin_user.py:12` | `core-user-auth` | `contract-core-user-auth-data` |
| 模型 | `backend/models/agent_aware_queue.py:20` | `agent-future` | `contract-agent-future-data` |
| 模型 | `backend/models/agent_message.py:32` | `agent-future` | `contract-agent-future-data` |
| 模型 | `backend/models/ai_diary.py:12` | `diary` | `contract-diary-data` |
| 模型 | `backend/models/conversation_log.py:13` | `chat-emotion` | `contract-chat-emotion-data` |
| 模型 | `backend/models/emotion_log.py:12` | `chat-emotion` | `contract-chat-emotion-data` |
| 模型 | `backend/models/feed_comment.py:16` | `life-feed` | `contract-life-feed-data` |
| 模型 | `backend/models/feed_like.py:14` | `life-feed` | `contract-life-feed-data` |
| 模型 | `backend/models/feed_post.py:17` | `life-feed` | `contract-life-feed-data` |
| 模型 | `backend/models/life_plan.py:12` | `life-feed` | `contract-life-feed-data` |
| 模型 | `backend/models/life_plan_outline.py:15` | `life-feed` | `contract-life-feed-data` |
| 模型 | `backend/models/login_log.py:12` | `core-user-auth` | `contract-core-user-auth-data` |
| 模型 | `backend/models/memory.py:12` | `memory-knowledge` | `contract-memory-knowledge-data` |
| 模型 | `backend/models/relationship.py:13` | `relationship` | `contract-relationship-data` |
| 模型 | `backend/models/relationship_change_history.py:14` | `relationship` | `contract-relationship-data` |
| 模型 | `backend/models/relationship_growth_log.py:12` | `relationship` | `contract-relationship-data` |
| 模型 | `backend/models/relationship_level_history.py:12` | `relationship` | `contract-relationship-data` |
| 模型 | `backend/models/user.py:12` | `core-user-auth` | `contract-core-user-auth-data` |
| 模型 | `backend/models/user_api_key.py:12` | `openapi` | `contract-openapi-data` |
| 模型 | `backend/models/user_short_term_emotion.py:12` | `chat-emotion` | `contract-chat-emotion-data` |
| 模型 | `backend/models/user_timeline_seq.py:11` | `core-user-auth` | `contract-core-user-auth-data` |
| 模型 | `backend/models/world_state.py:12` | `persona-prompt-world-state` | `contract-persona-data` |
| 模型 | `backend/models/worldview_event.py:16` | `persona-prompt-world-state` | `contract-persona-data` |
| 模型 | `backend/models/worldview_snapshot.py:15` | `persona-prompt-world-state` | `contract-persona-data` |
| 后台页面 | `admin/pages/accounts.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/agent-aware.html:1` | `agent-future` | `contract-agent-future-admin` |
| 后台页面 | `admin/pages/agent-rules.html:1` | `agent-future` | `contract-agent-future-admin` |
| 后台页面 | `admin/pages/chat-prompt-agent.html:1` | `agent-future` | `contract-agent-future-admin` |
| 后台页面 | `admin/pages/chat-prompt-step15.html:1` | `chat-emotion` | `contract-chat-emotion-api` |
| 后台页面 | `admin/pages/chat-prompt-step3.html:1` | `chat-emotion` | `contract-chat-emotion-api` |
| 后台页面 | `admin/pages/chat-prompt-step8.html:1` | `chat-emotion` | `contract-chat-emotion-api` |
| 后台页面 | `admin/pages/dashboard.html:1` | `observability-third-party` | `contract-observability-admin` |
| 后台页面 | `admin/pages/data-report.html:1` | `observability-third-party` | `contract-observability-admin` |
| 后台页面 | `admin/pages/diary-history.html:1` | `diary` | `contract-diary-admin` |
| 后台页面 | `admin/pages/diary-rules.html:1` | `diary` | `contract-diary-admin` |
| 后台页面 | `admin/pages/error.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/feed-comments.html:1` | `life-feed` | `contract-life-feed-admin` |
| 后台页面 | `admin/pages/feed-posts.html:1` | `life-feed` | `contract-life-feed-admin` |
| 后台页面 | `admin/pages/knowledge.html:1` | `memory-knowledge` | `contract-memory-knowledge-admin` |
| 后台页面 | `admin/pages/life-feed-global.html:1` | `life-feed` | `contract-life-feed-admin` |
| 后台页面 | `admin/pages/life-feed-prompts.html:1` | `life-feed` | `contract-life-feed-admin` |
| 后台页面 | `admin/pages/life-feed-system.html:1` | `life-feed` | `contract-life-feed-admin` |
| 后台页面 | `admin/pages/life-plan.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/login.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/memory-rules.html:1` | `memory-knowledge` | `contract-memory-knowledge-admin` |
| 后台页面 | `admin/pages/operation-logs.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/persona.html:1` | `persona-prompt-world-state` | `contract-persona-admin` |
| 后台页面 | `admin/pages/prompt.html:1` | `persona-prompt-world-state` | `contract-persona-admin` |
| 后台页面 | `admin/pages/relationship-rules.html:1` | `relationship` | `contract-relationship-admin` |
| 后台页面 | `admin/pages/safety-rules.html:1` | `persona-prompt-world-state` | `contract-persona-admin` |
| 后台页面 | `admin/pages/step5-5-switch.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/system-logs.html:1` | `observability-third-party` | `contract-observability-admin` |
| 后台页面 | `admin/pages/system-monitor.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/test-tool.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/third-party.html:1` | `observability-third-party` | `contract-observability-admin` |
| 后台页面 | `admin/pages/user-detail.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/users.html:1` | `admin-security-accounts` | `contract-admin-security-api` |
| 后台页面 | `admin/pages/vector-token-config.html:1` | `memory-knowledge` | `contract-memory-knowledge-admin` |
| 后台页面 | `admin/pages/worldview.html:1` | `persona-prompt-world-state` | `contract-persona-admin` |
| H5 页面 | `frontend/pages/chat.html:1` | `chat-emotion` | `contract-chat-emotion-api` · `contract-h5-app-api` |
| H5 页面 | `frontend/pages/diary.html:1` | `diary` | `contract-diary-api` · `contract-h5-app-api` |
| H5 页面 | `frontend/pages/feed.html:1` | `life-feed` | `contract-life-feed-api` · `contract-h5-app-api` |
| H5 页面 | `frontend/pages/index.html:1` | `h5-app` | `contract-h5-app-api` |
| H5 页面 | `frontend/pages/login.html:1` | `core-user-auth` | `contract-core-user-auth-api` |
| H5 页面 | `frontend/pages/memory.html:1` | `memory-knowledge` | `contract-memory-knowledge-api` · `contract-h5-app-api` |
| H5 页面 | `frontend/pages/relationship.html:1` | `relationship` | `contract-relationship-api` · `contract-h5-app-api` |
| H5 页面 | `frontend/pages/settings.html:1` | `core-user-auth` | `contract-core-user-auth-api` · `contract-h5-app-api` |
| 调度任务 | `backend/tasks/scheduler.py:152` | `diary` | `contract-diary-api` |
| 调度任务 | `backend/tasks/scheduler.py:165` | `agent-future` | `contract-agent-future-api` |
| 调度任务 | `backend/tasks/scheduler.py:174` | `agent-future` | `contract-agent-future-api` |
| 调度任务 | `backend/tasks/scheduler.py:183` | `agent-future` | `contract-agent-future-api` |
| 调度任务 | `backend/tasks/scheduler.py:192` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:201` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:212` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:219` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:228` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:237` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:246` | `life-feed` | `contract-life-feed-api` |
| 调度任务 | `backend/tasks/scheduler.py:255` | `agent-future` | `contract-agent-future-api` |
| 调度任务 | `backend/tasks/scheduler.py:264` | `life-feed` | `contract-life-feed-api` |
