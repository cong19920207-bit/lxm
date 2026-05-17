# 项目契约文档

> **2026-05-17 摘要**：AI 日记 M2a 手动批跑提供仓库脚本 **`scripts/run_diary_batch.py`**（入口 **`python -m scripts.run_diary_batch`**），与 **`DiaryService.run_daily_diary_task`** 同源；命令与语义见 **`docs/ops-diary.md`** §3。
>
> **2026-05-16 摘要**：AI 日记 Cron 改为 **`Asia/Shanghai`**（与 `diary_rules.generation_hour/minute` 一致）；对话统计窗为上海锚点日 **D** 的 **[D−1 00:00, D 00:00)**；表 **`ai_diary.covers_beijing_date`**（北京覆盖日）；`GET /api/diary/list` 的 **`items[]`** 含 **`covers_beijing_date`**；管理端 **`diary-history`** / **`users/{id}/diaries`** 的 **`list[]`** 含 **`covers_beijing_date`**（日期筛选仍按 **`created_at`**）；`PUT /diary-rules` 的 **`generation_hour`** 合法范围 **0–23**（北京时间）。
>
> **2026-05-17 摘要（H5 首页）**：**`frontend/pages/index.html`** — 未读角标 **`#unread-badge`** 锚定在「进入聊天」按钮右上角（**`GET /api/agent/unread-count`** 的 **`count>0`** 时 **`display:block`** 并 **`classList.add('unread-badge--active')`** 启用呼吸缩放；无未读时隐藏且移除该类）。**`#status-text`**：仍由首页脚本在 **`GET /api/relationship/status`** 成功后赋值（**`data.status_text` 有则用之**；当前 **`RelationshipService.get_relationship_info`** 未返回该键时与改动前一致，走默认「和你在一起的每一天都很开心」），外包 **`.home-status-bubble`** 漫画对白气泡。关系进度条仅在 **`.h5-home-main`** 内：**粗胶囊**轨道、白底未填充段、填充 **`linear-gradient(90deg, #3b82f6, #ec4899)`**（**`h5-theme.css`**）。四入口按钮左侧 **SVG** 图标；骨架屏 **`.skeleton-progress`** 高度与真条对齐。**`prefers-reduced-motion: reduce`** 下页内与 **`h5-theme.css`** 均关闭未读呼吸动画。静态断言 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`**。
>
> 最后更新：2026-05-17 — **H5 全站表现层刷新**：新增 **`frontend/static/css/h5-theme.css`**（neo 粗线边、偏移阴影、粉紫渐变页背景、装饰微动效、气泡入场等），各用户端页面 **`body` 增加 `class="h5-skin"`** 并在 **`common.css` 之后** 引入 **`/static/css/h5-theme.css`**；**`frontend/static/css/common.css`** 中全局色板微调（如 **`--color-primary`**、**`--color-bg`**）与主题协调。**不修改接口与业务脚本逻辑**。**`chat.html`** 中 **`#send-btn`** 的 **禁用态** 仍为 **`#D8D8DC` / `#8E8E93`**（页面内联规则保留；主题层仅对 **`:not(:disabled):not(.disabled)`** 覆盖启用态渐变）。**`prefers-reduced-motion: reduce`** 下关闭装饰、气泡入场、**`h5-page-fade`**（**`.page-body`**、**`.h5-home-main`**）等动画。**`h5-theme.css` 补充**：**`html:has(> body.h5-skin)`** 与 **`body.h5-skin`** 同铺渐变底，避免 overscroll 露白；关系页 **`.progress-section` / `.today-section` / `.timeline-section` / `.log-section`**、记忆 **`.add-panel` / `.memory-edit`**、聊天 **`.msg-bang` / `.levelup-tip` / `.thinking-bubble`** 等 neo 线框与阴影增强。静态锚点单测 **`tests/test_h5_static_contract.py`**。—— **2026-05-11** — **H5 `chat.html` 输入与发送钮**：`#msg-input` **`enterkeyhint="send"`**（软键盘回车键语义贴近「发送」，**具体标签文案以系统/WebView 为准**）；**`updateSendBtn`** 按 **`trim`** 同步 **`#send-btn`** 的 **`disabled` 属性** 与 **`.disabled`**，禁用态背景 **`#D8D8DC`**、符号 **`#8E8E93`**（对齐系统键盘「发送」置灰态），有内容时 **`#send-btn`** 启用态由 **`h5-theme.css`** 表现为 **渐变主钮**（与原先 **`var(--color-primary)`** 填充圆钮等价：**可点**）。**——** **H5 `chat.html` 发送键焦点**：`#send-btn` 为 **`type="button"`**，**`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听内 **`preventDefault`**，减轻点发送时 **`#msg-input`** 失焦导致的移动端键盘自动收起；**`handleSend`** 仍由 **`click`** 触发。**——** **H5 `chat.html` 发送（流控）**：移除全局 **`sending`**；**`send`** 与叹号 **`resend`** 共用 **`lastSendOrResendAt` + `CHAT_SEND_DEBOUNCE_MS`（300ms）** 静默防连点（通过内容非空与 **`countOpenPendingUsers`** 预判后再打时间戳）；**`oncompositionend`/`onkeyup`** 同步 **`updateSendBtn`**。细则见 **POST /api/chat/send**「H5 实现说明」。**——** **管理后台认证契约补全与自助改密**：拆分 **`POST /api/admin/auth/logout`** 与 **`POST /api/admin/auth/change-password`**；change-password Body **`AdminChangePasswordRequest`**（`old_password`、`new_password`、`confirm_password`，与 `schemas/admin_auth.py` 一致）；成功 **`code=0`**、**`message`**「密码修改成功」；失败 **20004**（旧密码不正确）、**20005**（新密码与旧密码相同）、**20006**（两次新密码不一致）、**20007**（密码强度不符，与 **`_validate_admin_password`** 一致）；**`admin/static/js/admin-api.js`** **`renderHeader`** 在「退出登录」左侧提供「修改密码」，**`showChangePasswordModal`** 经 **`adminRequest`** 提交改密，成功 Toast「密码已修改，请重新登录」后 **`clearAdminToken`** 并跳转 **`/admin/pages/login.html`**（与 **`accounts.html`** 对自身仅「修改备注」、对他人「重置密码」互补）。—— **2026-05-10** — **管理后台系统日志**：`GET /api/admin/system/logs` 的 `data.list` 按 `time` **降序**；`admin/pages/system-logs.html` 分页回调 **`window.systemLogsGoPage_system`** / **`window.systemLogsGoPage_error`** + **`renderPagination`**；单测 **`tests/test_system_monitor_logs.py`**。—— **H5 `chat.html`（续）**：与首段摘要一致，完整见 **POST /api/chat/send**「H5 实现说明」。**`LLM_TIMEOUT`（通用 LLM HTTP）默认 45s**：`get_llm_timeout_seconds()` 读取环境变量 **`LLM_TIMEOUT`**，未配置时默认 **45**（与 **`LLM_TIMEOUT_CHAT`** 默认一致）；适用于日记生成、记忆提取 LLM、Agent 主动消息、后台配置测试集（`chat_with_parse` 未传超时）、`chat_stream`、`chat_sync` 未显式传 `timeout_sec` 等——详见 **「部署与网关（对话 SSE）」** 下 **环境与通用 LLM HTTP 超时**。2026-05-08 — **SSE 等待上限语义（与代码一致）**：`_BUNDLE_WAIT_TIMEOUT_SEC`（默认 **120s**，`backend/routers/chat.py`）仅作用于 `_sse_chat_wait_bundle` 内 `asyncio.wait_for` 对本代 `generation` Future 的等待；**不**等价于 `_execute_llm_bundle` 整段服务端墙钟的数学上界。Step1.5、Step5 等经 `llm_client.chat_sync` 时内层至多 **3 次** HTTP（`LLM_MAX_RETRIES=2`），单次 `timeout_sec` 由调用方传入（Step1.5 **45s**、Step5 默认 **`LLM_TIMEOUT_CHAT` 45s**），叠加 **1s、2s** 退避后，**单段子调用**在极端全超时场景下即可 **超过 120s**；整链再串 Step2、Step5.5 等后，**可能出现 SSE 已结束等待而后台 `_execute_llm_bundle` 仍在执行**——属客户端等待与后台调度**解耦**，**120s 非产品硬指标**。详见 **「部署与网关（对话 SSE）」** 与 **POST /api/chat/send**。**Step1.5 查询重写（STEP-019）**：`query_rewrite_service._STEP1_5_TIMEOUT_SEC` **45s**；业务层整轮「LLM+解析」**仅 1 次**，失败即 R-L1L3-12 `_fallback_with_embedding`；`llm_client.chat_sync` 单次 HTTP 同 **45s**，内层仍最多 **3 次** POST + 1s/2s 退避。**Step6 记忆 LLM 超时**：`step6_orchestrator._STEP6_LLM_TIMEOUT_SEC` 由 **15s 调至 45s**（固定常量，非环境变量；异步不阻塞 SSE）。**STEP-026**：管理后台 Step5 / Step5.5 Prompt 与 **`step5_5_enabled`** 总开关——运行时 **`step5_system_prompt`**（JSON `{"content"}`）热加载模块1 System；**`step5_5_prompt_fragments`** 六段模板 + **`backend/services/step5_5_prompt_fragments.py`** 占位符与发布校验；**废弃**旧 **`prompt_modules`** 七模块接口；**`POST /api/admin/prompt/test`** 改为 **`PromptBuilder.build_chat_prompt`**（与主链一致，`use_draft` 覆盖 Step5 System）；页面 **`admin/pages/prompt.html`**、**`admin/pages/step5-5-switch.html`**；RBAC **`super_admin`+`ai_trainer`**；单测 **`tests/test_step026_prompt_config.py`**。**STEP-025**：管理后台 **`GET|PUT /api/admin/configs/vector_retrieval_config`** 与 **`GET|PUT /api/admin/configs/prompt_token_config`**（Body 为部分字段 PATCH，与库中生效值及代码默认合并后走 `admin_config_service.publish_config`；Redis `active_config:{key}`；RBAC `super_admin`+`ai_trainer`；错误码 **`20046`** `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`；页面 **`admin/pages/vector-token-config.html`**（双 Tab）；单测 **`tests/test_admin_vector_token_config.py`** 6 条）。**STEP-024 勘误**：Step8 子链路 Step1 装载方式为「同一 `AsyncSession` 内顺序查询」最近对话（库内至多取 20 条、下游使用末 10 轮）+ relationship + emotion，**禁止**对同一 session 使用 `asyncio.gather` 并行 IO（与 SQLAlchemy 异步会话约束一致）；对外接口、表结构、Future 消费语义不变。**同日**：Admin 用户详情 **GET /api/admin/users/{user_id}/conversations** 合并 `conversation_log` 与 `agent_message`（按 `sort_seq`、`id` 升序，与 H5 `GET /api/chat/timeline` 时间线一致；字段见「管理后台用户管理」）。2026-05-05 起 STEP 纪要：（**STEP-024**：Step8 子链路——新增 `backend/services/step8_subchain.py`：`execute_step8_subchain(user_id, future_action)` 实现 Future 槽到期后完整主动消息子链路（Step1 顺序装载 + Step1.5 变体（输入用 `future.action` 替代 `last_user_text`，降级路径用 `future.action` 生成单 Embedding）+ Step2 多路向量检索 + Step3 变体（`PromptBuilder.build_step8_prompt()` 将【用户消息】替换为【主动发起】模块含 `future.action` 摘要）+ Step5 LLM 调用（含内容安全检查与人格偏离检测）+ Step5.5 可配低概率触发（`STEP8_GATE_A_PROBABILITY=0.03`）→ 写入 `agent_message` 表（不走 SSE）→ Step6 异步记忆总结 → `proactive_times` +1 → 衰减门控 `0.15^(proactive_times+1)` 概率写入下一轮 Future 预约）；`prompt_builder.py` 新增 `_build_proactive_input()` 与 `build_step8_prompt()` 方法；`step5_5_service.py` `should_trigger_step5_5()` / `execute_step5_5()` 新增 `gate_a_override` 参数支持外部覆盖门闩 A 概率；`future_handler.py` `_consume_one()` 中占位调用 `generate_and_save_message(FUTURE)` 替换为 `execute_step8_subchain()`；`tests/test_step024_step8_subchain.py` 10 条、`tests/test_step023_future_handler.py` 修正为 14 条单测全部通过。**STEP-023**：Future 槽消费轮询 Handler。**STEP-022**：proactive_times 计数/清零 + 频控调整（R-FUT-03 / §2.2 变更 8.2）——`chat.py` `POST /api/chat/send` 入口新增 proactive_times 清零逻辑（用户发新消息时将 `relationship.proactive_times` 置 0）；`agent_service.py` 频控参数调整：每日上限 2→8（含 Future 槽消费计入）、两次间隔 6h→30min；`generate_and_save_message` 成功后 proactive_times +1（上限 3）；新增 `increment_agent_count_for_future()` 方法供 STEP-023 Future 槽消费后计入 `agent:count` 计数器；新增 `reset_inactive_proactive_times()` 方法实现 30 天无活动自动清零（清空 proactive_times + Future 槽）；`scheduler.py` Agent 扫描间隔 6h→30min、新增每日凌晨 1:00 UTC 30 天无活动清零定时任务；`tests/test_step022_proactive_times.py` 18 条单测全部通过。**STEP-021**：Step3 Prompt 新增模块 + Token 裁剪（R-L1L3-19）——`prompt_builder.py` 重构为 9 模块结构：新增模块 A「角色设定与知识」（`_build_character_knowledge_prompt()`，合并 `character_global`+`character_private`+`character_knowledge` 三路检索结果，超限按 DashVector score 从低到高逐条裁剪）插入 Persona 后 Relationship 前；模块 B「时间与活动」（原 `_build_time_prompt()` 重新定位）插入 Emotion 后 Recent Chat 前；`MAX_TOTAL_TOKENS` 5200→7373；`MODULE_TOKEN_LIMITS` 全部更新（system 720 / persona 1080 / character_knowledge 600 / relationship 360 / memory 900 / emotion 270 / time_activity 80 / recent_chat 1800 / user_input 900）；新增 `_load_token_limits()` 从 `admin_config:prompt_token_config` 热加载各模块上限（缺省回退默认值）；`_trim_to_budget()` 实现 5 级裁剪优先级（recent_chat→memory→character_knowledge→relationship 扩展→time_activity，System/Persona 绝不裁）；`_build_memory_prompt()` 兼容 Step2 dict 列表和 ORM 实例；`build_chat_prompt()` 新增 `retrieval_results` 参数接收 Step2 四路检索结果；`chat.py` `_execute_llm_bundle` 传递 `retrieval_result.format_for_prompt()` + `user_memory_results`（dict 列表替代旧 `_MemoryProxy`）；`tests/test_prompt_builder.py` 30 条（含新增 STEP-021 场景：全量注入无裁剪、超限裁剪优先级、模块 A score 裁剪、热配覆盖默认、9 模块顺序验证、空结果跳过等）。**STEP-020**：Step2 多路向量检索（R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21）——新增 `backend/services/multi_vector_retrieval_service.py`：`MultiVectorRetrievalResult` dataclass（4 路检索结果 + `top_k`/`threshold`/`is_fallback` 元数据，提供 `all_results`/`user_memory_results`/`format_for_prompt` 属性）；`execute_multi_vector_retrieval()` 主入口：正常路径阶段① `asyncio.gather` 并行 3 Embedding（CharacterGlobal / CharacterKnowledge / UserProfile）→ 阶段② `asyncio.gather` 并行 4 DashVector 检索（`character_global` 无 user_id + `character_private` 有 user_id + `character_knowledge` 无 user_id + `user` 有 user_id），CharacterGlobal Embedding 复用于 `character_global`+`character_private` 两路；降级路径（Step1.5 失败）用 `fallback_embedding` 执行全部 4 路（R-L1L3-12）；热配置 `admin_config:vector_retrieval_config`（`{"top_k":3,"threshold":0.7}`）支持运行时调整 TopK/阈值（R-L1L3-17）；`chat.py` `_execute_llm_bundle` 集成 Step1.5（`execute_query_rewrite`）+ Step2（`execute_multi_vector_retrieval`），删除旧 `user_embedding = await _get_embedding(last_user_text)` 及关联 `_search_memories` 调用（R-L1L3-21），`_persona_text` 前提获取后复用至 Step6（消除重复 Redis 读取）；`tests/test_multi_vector_retrieval_service.py` 新增 6 条单测（正常 3+4 并行、降级 1+4、降级无 Embedding、部分路 0 命中、热配 TopK=5、无配置回退默认）。**STEP-019**：Step1.5 查询重写 LLM（R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14）——新增 `backend/services/query_rewrite_service.py`：`QueryRewriteOutput` Pydantic 模型（7 字段：`InnerMonologue` + 3 组 `QueryQuestion`/`Keywords`）、`QueryRewriteResult` dataclass（`success` + `output` + `fallback_embedding`）；`_build_step1_5_prompt()` 拼装 7 模块（系统指令 + 时间活动 + 人格 + 关系 + 近期对话 + 用户消息 + 任务含输出 Schema）；`execute_query_rewrite()` 主入口（**timeout=45s**；业务层 **不重试**；`chat_sync` 内层仍最多 3 次 HTTP + 1s/2s 退避）；`_parse_query_rewrite_output()` 解析 JSON 并校验至少一组 QueryQuestion 非空；`_fallback_with_embedding()` 降级路径用 `last_user_text` 通过 `embedding_service.get_embedding` 生成单 Embedding 作为统一 fallback（R-L1L3-12：不触发叹号，用户无感）；结构化日志含 `user_id`、失败原因、链路来源（`source="main"/"step8"`）；`tests/test_query_rewrite_service.py` 新增 7 条单测（场景1 三组 Query 完整、场景2 超时即降级+日志、场景3 InnerMonologue 仅内存、边界非法 JSON 降级、解析与 Prompt）。**STEP-018**：Step1 并行装载扩展（R-L1L3-01 / R-L1L3-06）——`chat.py` 新增 `_build_round_context()` 辅助函数，在 `_execute_llm_bundle` 中 `_get_relationship` 读取后构建本轮内存上下文 dict（含 `time_description`、`activity_description`、`relation_description`、`user_real_name`、`user_hobby_name`、`user_description`、`character_purpose`、`character_attitude`、`level`、`level_name`、`silence_days`），扩展字段 NULL 时用占位文案（`relation_description` 默认 `"暂无，初次互动"`，其余默认空串）；`round_context` 在 Step5.5 和 Step6 调用处共用同一份（不重复 SELECT）；`POST /api/chat/send` 的 `asyncio.gather` 中移除 `_get_relationship`（无下游消费的重复 SELECT）；`prompt_builder.py` 的 `build_chat_prompt` 新增可选 `round_context` 参数，`_build_time_prompt` 优先使用预计算值（避免重复调 `_generate_time_description` / Redis 读 `activity_schedule`）；`tests/test_step018_round_context.py` 新增 10 条单测。**STEP-017**：`prompt_builder.py` 新增 `get_activity_description()` 异步函数（R-L1L3-11）：从 Redis `active_config:activity_schedule` 读取静态 JSON，按当前小时段匹配活动描述文案，未配置/未命中/解析失败返回空字符串；`_build_time_prompt()` 改为 async，条件性注入活动描述（空串时跳过该行）；`build_chat_prompt()` 对应 await 调用；`tests/test_prompt_builder.py` 新增 9 条单测（时间描述精确场景 + 活动描述匹配/未配置/未命中/非法JSON/Redis异常/条件注入）。**STEP-016**：`backend/services/step6_orchestrator.py` 新增 `Step6Snapshot` + `execute_step6`（§2.8.4 M2 半异步）：`chat.py` 在 Step5 解析成功、内容安全通过且 `_persist_bundle_success` 落库后 `asyncio.create_task(execute_step6(snapshot))` 入队，不阻塞 `_resolve_generation_future`/SSE；快照含 `merge_messages_if_exceed(step5_result.messages)`（≤5，CP1）、`round_id`、打包用户原文、`persona`（Redis `active_config:persona` 未命中则 `DEFAULT_PERSONA`）、关系等级名与 relationship 扩展列读快照、近期对话 `{role,content}` 列表、Step5 `future`；管线：`build_step6_prompt` → `llm_client.chat_sync`（**45s** 固定常量 `_STEP6_LLM_TIMEOUT_SEC`，非 `LLM_TIMEOUT_CHAT`）→ `parse_step6_output` → `upsert_step6_vectors`（STEP-014）→ 独立 session 加载 `relationship` 后 `RelationshipService.update_relationship_from_step6`（STEP-015）并 `commit`；失败 sleep **500ms** 再试，**共 2 次**仍失败则 ERROR 日志结束，不影响客户端；入队 try/except 失败仅日志；`tests/test_step016_step6_orchestrator.py` **6** 条通过；**未**实现管理后台 Step6 失败监控（STEP-028）。**STEP-015**：`relationship_service.py` 新增 `update_relationship_from_step6(relationship, step6_output, round_id, *, future_time_natural, future_action)` 方法（R-MEM-05 / §2.8.4）——6 个标量字段（`UserRealName`→`user_real_name`、`UserHobbyName`→`user_hobby_name`、`UserDescription`→`user_description`、`CharacterPurpose`→`character_purpose`、`CharacterAttitude`→`character_attitude`、`RelationDescription`→`relation_description`）：值非「无」→ UPDATE 覆盖 + 调用 `RelationshipHistoryService.append_history` 写入变更历史（含 old_value），值为「无」→ 跳过赋值保留旧值；Future 槽：action 为「无」→ 清空 `future_timestamp`+`future_action`，`time_natural` 非「无」→ 调用 `parse_future_time` 解析（成功→写入 `future_timestamp`+`future_action`，失败→清空槽位+保留 `proactive_times`+写 warning 日志）；所有历史记录 `trigger_source='step6'` 携带 `round_id`；`tests/test_step015_relationship_step6.py` 11 条单测全部通过；**已由 STEP-016 在 `chat.py` 主链异步入队调用。****STEP-014**：`memory_llm_service` 增补 Step6 四路 DashVector 写入（R-MEM-04）——`parse_kv_lines()` 按换行拆行、首处全角冒号拆 key-value，空 key/value 或无冒号行丢弃；`upsert_step6_vectors(output, user_id)` 对 `CharacterPublicSettings`/`CharacterPrivateSettings`/`CharacterKnowledges`/`UserSettings`：值为「无」整路跳过，否则逐行 `embedding_service.get_embedding(value)` + `dashvector_client.upsert`；`doc_id`=`{memory_type}:{stable_key}:{user_id或空}`；`character_global`/`character_knowledge` 不写 `user_id` 字段，`character_private`/`user` 写 `fields.user_id` 且 doc_id 含用户后缀；`content` 存「key：value」全文；`tests/test_step6_vector_upsert.py` 22 条通过；**已由 STEP-016 在 `chat.py` 主链异步入队调用。****STEP-013**：新增 `backend/services/memory_llm_service.py` 实现 Step6 记忆总结 LLM 的 Prompt 拼装与 JSON 解析（R-MEM-01 / R-MEM-06 / R-MEM-07 / §2.5）——`Step6MemoryOutput` Pydantic 模型（驼峰命名，11 字段：`InnerMonologue` + 4 类可检索记忆 `CharacterPublicSettings`/`CharacterPrivateSettings`/`CharacterKnowledges`/`UserSettings` + 6 类标量 `UserRealName`/`UserHobbyName`/`UserDescription`/`CharacterPurpose`/`CharacterAttitude`/`RelationDescription`）；`parse_step6_output()` 解析规则：JSON 不合法→抛 `Step6ParseError`，字段缺失→默认「无」（`InnerMonologue` 默认空串）；`build_step6_prompt()` 拼装 8 模块（系统指令 + 时间 + 人格 + 关系状态 + 近期历史 + 本轮对话 + 任务 + §2.5 完整 few-shot），本轮 AI 回复数据来源仅为 Step5 产出的 `messages`（非 Step5.5 润色后，§2.9.3）；`tests/test_memory_llm_service.py` 30 条单测全部通过。不含 relationship 标量更新（STEP-015）、异步入队（STEP-016）。**STEP-012**：内容安全兼容新结构化输出（§9.1 / §9.3）——`chat.py` 新增 `_check_messages_safety()` 逐条检测 `messages[].content`（任一违规→整轮失败，user 行标 `failed_blocked`，不进 Step5.5，不入队 Step6）、`_check_inner_monologue_safety()` 检测 `inner_monologue`（违规仅日志+替换空串，不拦截整轮，避免污染 Step6 记忆）；Step5.5 输出也经逐条安全检测（违规→回退 Step5 合并后 messages）；`constants.py` 新增 `DELIVERY_STATUS_FAILED_BLOCKED = "failed_blocked"`；`tests/test_step012_content_safety.py` 10 条单测覆盖全通过/第 N 条违规整轮失败/inner_monologue 违规替换/Step5.5 违规回退。**STEP-011**：`conversation_log` 多气泡落库（§2.8.1 / §2.8.3）——`_persist_bundle_success` 接收 `messages` 列表（原 `ai_reply` 单条拼接），按 `len(messages)` 一次性 `allocate_sort_seq(user_id, count=N)` 分配连续 `sort_seq`，写入 N 行 `role=assistant`（每行 `content` = `messages[i].content`，与本包 user 行共享同一 `round_id`）；后置任务仍用 `ai_reply="\n".join(...)"`；`GET /api/chat/timeline` 沿用 `sort_seq` 合并排序，升序展示与气泡顺序一致；`tests/test_chat.py` 新增 `TestStep011MultiBubblePersist` 4 条并修正 STEP-008 单测入参。**STEP-010**：SSE 协议扩展（多气泡流式）——`_sse_chat_wait_bundle` 重写：首包 `meta` 新增 `message_count`（§2.9.4 CP2），`delta` 事件按 `message_index` 分条推送，`done` 事件携带完整 `messages` 数组（真相源 §2.7.5）+ 整轮 `emotion`（§2.7.3）；H5 `appendAIThinkingBubble` 重构为多气泡渲染器（不预铺空气泡，`delta` 动态创建槽位，`done` 纠偏定稿）、`consumeChatSse` 适配新字段。**STEP-009**：新增 `backend/services/step5_5_service.py` 实现 Step5.5 响应润色完整链路——`should_trigger_step5_5()` 双门闩 OR 触发判定（总开关 `admin_config` key=`step5_5_enabled` + 门闩 A 12% + 门闩 B 仅 `knowledge_expand="是"` 时 50%）、`build_step5_5_prompt()` 按 `step5_5_prompt.md` 全文拼装、`parse_step5_5_output()` 校验 JSON 数组 + type="text" + content 非空、`execute_step5_5()` 含 30s 独立子超时（§2.7.4 D2）与失败回退；`chat.py` `_execute_llm_bundle` 接入 Step5.5（Step5 成功后调用，成功则覆盖 `final_messages`，失败/未触发则回退 Step5 合并后 messages；Step6 入参快照 `step6_messages` 始终取 Step5 原始 messages 合并结果，不受 Step5.5 影响（R-BND-05））；`tests/test_step5_5.py` 新增 32 个单测（总开关关闭、门闩 A 命中、门闩 B 命中、非法 JSON 回退、超时回退、7 条合并到 5 条等）。**STEP-008**：`chat.py` `round_id` 提前至 Step5 成功时生成（§2.9.3），`_persist_bundle_success` 改为接收外部 `round_id` 不再自行生成，SSE Future payload 新增 `round_id` + `step6_messages` 供 Step6 入队使用；`_BUNDLE_WAIT_TIMEOUT_SEC` 55→120（§2.11.2）；Nginx `proxy_read_timeout` 已为 300s 满足 ≥130s 要求；`tests/test_chat.py` 新增 `TestStep008RoundId` 3 条单测并修复 `test_chat_send_stream_response` 对 `chat_with_step5_parse` 的 mock。**STEP-007**：`backend/utils/future_time_parser.py` 实现 `parse_future_time()` / `is_future_slot_valid()`（§2.8.4，UTC 基准，3 种正则 +「无」→ None；失败 `logger.warning` 结构化日志）；`tests/test_future_time_parser.py` 单测 22 条。**STEP-006**：`constants.py` 新增 `MAX_MESSAGES_COUNT=5` / `MAX_SINGLE_MESSAGE_LENGTH=2000` 消息合并常量；`llm_service.py` 新增 `merge_messages_if_exceed()` 纯函数（§2.9.1，>5 条时将第 6 条起 content 半角空格拼入第 5 条，超长尾部截断+日志）；`chat.py` `_execute_llm_bundle` 接入消费点 1（纯 Step5 路径合并）与消费点 3（Step6 入参快照 CP1，变量 `step6_messages` 预留），SSE payload `step5.messages` 改为合并后版本。**STEP-005**：`llm_service.py` Step5 输出 JSON 解析器 + 校验规则（§2.7.7 / CP3 / U1 / U2 / R-BND-02），新增 `Step5Output` Pydantic 模型（6 字段扁平结构）+ `parse_step5_output()` 解析函数 + `chat_with_step5_parse()` 方法；`chat.py` `_execute_llm_bundle` 替换旧 `chat_with_parse_strict` 调用，不再读取 `reply` 字段，改为拼接 `messages[].content`；SSE payload 新增 `step5` 完整结构化数据。**STEP-004**：`prompt_builder.py` Step5 提示词改造（R-BND-13 / §2.7.9），`SYSTEM_PROMPT_TEXT` 替换为新 6 字段 JSON Schema（inner_monologue / messages / relation_change / future / emotion / knowledge_expand）+ few-shot 示例 + 【知识性话题回应原则】新增；`_build_relationship_prompt()` 尾部追加 4 行扩展字段（relation_description / user_description / user_hobby_name / user_real_name）；新增【当前时间】模块（`_generate_time_description()`）；hint 文字与主动消息 Schema 同步更新；`MODULE_TOKEN_LIMITS["system"]` 400→1200，`MAX_TOTAL_TOKENS` 4096→5200。**STEP-003**：DashVector type 常量 + search/upsert 签名扩展（R-L1L3-08 / R-L1L3-15 / R-VEC-01），`constants.py` 新增 4 类 `MEMORY_TYPE_*` 常量，`dashvector_client` 的 `upsert()` / `search()` 支持 `memory_type` 参数与 type 过滤。**STEP-002**：新增 `relationship_change_history` append-only 历史表（R-L1L3-05），Alembic 迁移 `v4b_step002_001`，`RelationshipHistoryService.append_history()` 仅 INSERT。**STEP-001**：`relationship` 表新增 9 个扩展字段——记忆写回 6 字段 + Future 槽 3 字段，Alembic 迁移 `v4a_step001_001`。2026-04-13 及更早：H5 对话 TD-015、SSE `meta.generation_id`、`resend`、timeline 等见历次说明。）

本文档依据当前仓库内 FastAPI 路由、Pydantic Schema 与 SQLAlchemy Model 扫描生成；SSE/文件流接口的 HTTP 层不包在统一 JSON 信封内，已单独标注。

---

## 数据库表结构

### 表名：users


| 字段名                | 类型          | 必填  | 默认值    | 说明                               |
| ------------------ | ----------- | --- | ------ | -------------------------------- |
| id                 | Integer PK  | 是   | 自增     | 用户 ID                            |
| username           | String(20)  | 是   | -      | 唯一索引（`unique=True`，ORM）            |
| password_hash      | String(255) | 是   | -      | 密码哈希                             |
| created_at         | DateTime    | 是   | utcnow | 注册时间                             |
| last_login_at      | DateTime    | 否   | NULL   | 最后登录                             |
| relationship_level | Integer     | 是   | 0      | 关系等级 0–3（与 relationship 表存在并行字段） |
| growth_value       | Integer     | 是   | 0      | 成长值（与 relationship 表存在并行字段）      |
| is_banned          | Boolean     | 是   | False  | 是否封禁                             |
| login_fail_count   | Integer     | 是   | 0      | 连续登录失败次数                         |
| locked_until       | DateTime    | 否   | NULL   | 锁定截止时间                           |


### 表名：relationship


| 字段名                    | 类型                   | 必填  | 默认值    | 说明       |
| ---------------------- | -------------------- | --- | ------ | -------- |
| id                     | Integer PK           | 是   | 自增     |          |
| user_id                | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`，`index=True`） |
| level                  | Integer              | 是   | -      | 关系等级 0–3 |
| growth_value           | Integer              | 是   | -      | 成长值      |
| last_interaction_at    | DateTime             | 否   | NULL   | 上次互动     |
| consecutive_login_days | Integer              | 是   | 0      | 连续登录天数（ORM `default=0`） |
| updated_at             | DateTime             | 是   | utcnow | `onupdate=utcnow` |
| relation_description   | Text                 | 否   | NULL   | 关系描述（R-MEM-05，Step6 记忆写回） |
| user_real_name         | String(50)           | 否   | NULL   | 用户真实称呼（R-MEM-05） |
| user_hobby_name        | String(50)           | 否   | NULL   | 用户昵称（R-MEM-05） |
| user_description       | Text                 | 否   | NULL   | 用户印象（R-MEM-05） |
| character_purpose      | Text                 | 否   | NULL   | 角色当前回应策略（R-MEM-07） |
| character_attitude     | Text                 | 否   | NULL   | 角色当前态度（R-MEM-07） |
| future_timestamp       | Integer              | 否   | NULL   | Future 预约时间戳（R-FUT-02） |
| future_action          | String(200)          | 否   | NULL   | Future 预约意图摘要（R-FUT-02） |
| proactive_times        | Integer              | 是   | 0      | 主动消息计数，上限 3（R-FUT-03，`server_default="0"`） |


### 表名：conversation_log


| 字段名                | 类型         | 必填  | 默认值    | 说明               |
| ------------------ | ---------- | --- | ------ | ---------------- |
| id                 | Integer PK | 是   | 自增     |                  |
| user_id            | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`     |
| role               | String(20) | 是   | -      | user / assistant |
| content            | Text       | 是   | -      |                  |
| emotion_label      | String(50) | 否   | NULL   | 用户消息情绪           |
| emotion_confidence | Float      | 否   | NULL   |                  |
| memory_injected    | JSON       | 否   | NULL   | 注入记忆摘要           |
| persona_risk_flag  | Boolean    | 是   | False  | 人格风险标记           |
| persona_risk_type  | String(50) | 否   | NULL   |                  |
| sort_seq           | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| delivery_status    | String(32) | 否   | NULL   | user 行：送达/等待/失败等（与 `constants` 一致）；assistant 为 NULL |
| skipped_in_prompt  | Boolean    | 是   | false  | Q14：未进入本轮 Prompt 的 user 行 |
| round_id           | String(36) | 否   | NULL   | TD-016 / STEP-011：一轮内全部 user 行与**全部** assistant 行共用同一 UUID 文本（多气泡时为多行 assistant，每行独立 `sort_seq`）；旧数据可为 NULL |
| created_at         | DateTime   | 是   | utcnow |                  |


### 表名：emotion_log


| 字段名             | 类型                              | 必填  | 默认值    | 说明  |
| --------------- | ------------------------------- | --- | ------ | --- |
| id              | Integer PK                      | 是   | 自增     |     |
| user_id         | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| emotion_label   | String(50)                      | 是   | -      |     |
| confidence      | Float                           | 是   | -      |     |
| conversation_id | Integer FK(conversation_log.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| round_id        | String(36)                      | 否   | NULL   | 与本轮 conversation 对齐；旧数据可为 NULL |
| created_at      | DateTime                        | 是   | utcnow |     |


### 表名：user_short_term_emotion


| 字段名          | 类型         | 必填  | 默认值    | 说明                               |
| ------------ | ---------- | --- | ------ | -------------------------------- |
| id           | Integer PK | 是   | 自增     |                                  |
| user_id       | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`）              |
| emotion_label | String(50) | 是   | -      | 短期情绪标签                           |
| confidence    | Float      | 是   | -      |                                  |
| payload       | Text       | 否   | NULL   | 可选 JSON 文本（ORM `nullable=True`）    |
| updated_at    | DateTime   | 是   | utcnow | `onupdate=utcnow`                |


### 表名：memory


| 字段名                     | 类型          | 必填  | 默认值    | 说明                    |
| ----------------------- | ----------- | --- | ------ | --------------------- |
| id                      | Integer PK  | 是   | 自增     |                       |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`          |
| content                 | Text        | 是   | -      |                       |
| importance_score        | Float       | 是   | -      |                       |
| source                  | String(20)  | 是   | -      | auto / manual / admin |
| dashvector_id           | String(100) | 否   | NULL   | 向量侧 ID（`index=True`） |
| is_deleted              | Boolean     | 是   | False  | 软删除                   |
| created_at              | DateTime    | 是   | utcnow |                       |
| updated_at              | DateTime    | 是   | utcnow | `onupdate=utcnow`     |
| expires_at              | DateTime    | 否   | NULL   | 过期时间                  |


### 表名：ai_diary


| 字段名                            | 类型         | 必填  | 默认值    | 说明    |
| ------------------------------ | ---------- | --- | ------ | ----- |
| id                             | Integer PK | 是   | 自增     |       |
| user_id                        | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                        | Text       | 是   | -      |       |
| relationship_level_at_creation | Integer    | 是   | -      | 生成时等级 |
| is_read                        | Boolean    | 是   | False  |       |
| covers_beijing_date            | Date       | 否   | NULL   | 日记内容覆盖的北京日历日；旧数据可为 NULL（不回填）；与 `user_id` 唯一约束防重复 |
| created_at                     | DateTime   | 是   | utcnow |       |


### 表名：agent_message


| 字段名          | 类型         | 必填  | 默认值    | 说明    |
| ------------ | ---------- | --- | ------ | ----- |
| id           | Integer PK | 是   | 自增     |       |
| user_id      | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| trigger_type | String(10) | 是   | -      | P0–P4 / FUTURE（见 `TriggerType` 常量类） |
| content      | Text       | 是   | -      |       |
| action_score | Float      | 是   | -      |       |
| is_read      | Boolean    | 是   | False  |       |
| sort_seq     | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| created_at   | DateTime   | 是   | utcnow |       |


### 表名：login_log


| 字段名         | 类型         | 必填  | 默认值    | 说明                        |
| ----------- | ---------- | --- | ------ | ------------------------- |
| id          | Integer PK | 是   | 自增     |                           |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`              |
| login_at    | DateTime   | 是   | -      |                           |
| time_period | String(20) | 是   | -      | morning / evening / other |
| created_at  | DateTime   | 是   | utcnow |                           |


### 表名：world_state


| 字段名                     | 类型         | 必填  | 默认值    | 说明  |
| ----------------------- | ---------- | --- | ------ | --- |
| id                      | Integer PK | 是   | 自增     |     |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                 | Text       | 是   | -      |     |
| trigger_conversation_id | Integer    | 否   | NULL   | ORM 未声明 `ForeignKey`（仅整型可空） |
| relevance_weight        | Float      | 是   | 1.0    | ORM `default=1.0` |
| created_at              | DateTime   | 是   | utcnow |     |


### 表名：relationship_growth_log


| 字段名         | 类型         | 必填  | 默认值    | 说明       |
| ----------- | ---------- | --- | ------ | -------- |
| id          | Integer PK | 是   | 自增     |          |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| action_type | String(30) | 是   | -      | dialog 等 |
| points      | Integer    | 是   | -      | 本次得分     |
| created_at  | DateTime   | 是   | utcnow |          |


### 表名：relationship_level_history


| 字段名         | 类型         | 必填  | 默认值    | 说明  |
| ----------- | ---------- | --- | ------ | --- |
| id          | Integer PK | 是   | 自增     |     |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| from_level  | Integer    | 是   | -      | 升级前等级 |
| to_level    | Integer    | 是   | -      | 升级后等级 |
| achieved_at | DateTime   | 是   | utcnow |     |


### 表名：relationship_change_history


| 字段名            | 类型                   | 必填  | 默认值    | 说明       |
| ---------------- | -------------------- | --- | ------ | -------- |
| id               | BigInteger PK（MySQL BIGINT，SQLite INTEGER 兼容） | 是   | 自增     |          |
| relationship_id  | Integer FK(relationship.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| user_id          | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 冗余便于查询（`index=True`） |
| field_name       | String(50)           | 是   | -      | 被更新的字段名（snake_case，如 `relation_description`） |
| old_value        | Text                 | 否   | NULL   | 更新前的值   |
| new_value        | Text                 | 否   | NULL   | 更新后的值   |
| trigger_source   | String(20)           | 是   | step6  | 触发来源（`server_default="step6"`） |
| round_id         | String(36)           | 否   | NULL   | 关联的对话轮次 ID |
| created_at       | DateTime             | 是   | utcnow | 写入时间    |

- **设计语义**：append-only 表，仅 INSERT 不做 UPDATE/DELETE（R-L1L3-05）
- **索引**：`(user_id, created_at)` 组合索引（`ix_rel_change_user_created`），支持按用户 + 时间排序查询
- **关联需求**：R-L1L3-05（变更历史）、R-MEM-05（6 个扩展字段全部参与历史记录）
- **触发来源**：本期仅 `step6`（Step6 自动更新触发写入）；后续如启用管理后台手动编辑，可扩展其他来源标记（R-L1L3-07 本期不做）


### 表名：user_timeline_seq


| 字段名      | 类型            | 必填  | 默认值 | 说明   |
| -------- | ------------- | --- | --- | ---- |
| user_id  | Integer PK / FK(users.id, ON DELETE CASCADE) | 是   | -   | 复合主键之一 |
| next_seq | BigInteger    | 是   | 1   | 下一序号（ORM `default=1`） |


### 表名：admin_users


| 字段名                   | 类型          | 必填  | 默认值    | 说明            |
| --------------------- | ----------- | --- | ------ | ------------- |
| id                    | Integer PK  | 是   | 自增     |               |
| username              | String(50)  | 是   | -      | 唯一索引（`unique=True`） |
| password_hash         | String(255) | 是   | -      |               |
| role                  | String(20)  | 是   | -      | super_admin / ops_admin / ai_trainer / tech_ops（ORM `comment`） |
| remark                | String(200) | 否   | NULL   |               |
| is_active             | Boolean     | 是   | True   | ORM `default=True` |
| is_locked             | Boolean     | 是   | False  | ORM `default=False` |
| login_fail_count      | Integer     | 是   | 0      |               |
| last_login_at         | DateTime    | 否   | NULL   |               |
| last_password_change_at | DateTime  | 否   | NULL   |               |
| created_at            | DateTime    | 是   | utcnow |               |
| created_by            | String(50)  | 否   | NULL   |               |


### 表名：admin_config


| 字段名        | 类型          | 必填  | 默认值    | 说明        |
| ---------- | ----------- | --- | ------ | --------- |
| id         | Integer PK  | 是   | 自增     |           |
| config_key | String(100) | 是   | -      | **非唯一**索引（`index=True`）；同一 key 多行见下 |
| config_value | Text      | 否   | NULL   | JSON 字符串等（`nullable=True`） |
| version    | Integer     | 是   | 1      | ORM `default=1` |
| is_active  | Boolean     | 是   | True   | ORM `default=True` |
| is_draft   | Boolean     | 是   | False  | ORM `default=False`；`comment`：True=草稿 / False=正式或历史 |
| updated_by | String(50)  | 否   | NULL   |           |
| updated_at | DateTime    | 是   | utcnow | `onupdate=utcnow` |

- **行语义与约束**：同一 `config_key` **允许且需要**多行并存——例如一条草稿（`is_draft=true`，`is_active=false`）、一条当前生效（`is_active=true`，`is_draft=false`）、多条历史版本（`is_active=false`，`is_draft=false`）。**禁止**对 `config_key` 单列建立 **UNIQUE**；否则 `PUT /api/admin/persona/draft`、`prompt` 草稿保存等会在 `INSERT` 草稿时触发 MySQL **1062**。新建库见 `scripts/schema_ddl.sql`；已错建唯一索引的库执行 **`scripts/migrate_admin_config_config_key_nonunique.sql`**（执行前用 `SHOW INDEX FROM admin_config` 核对索引名）。
- **运行时约定 key（节选，非表结构 DDL）**：除既有 `persona`、`fallback_reply` 等外，对话链路读取 **`step5_system_prompt`**（Step5 模块1 System 整段，缺省回退代码内 `SYSTEM_PROMPT_TEXT`）、**`step5_5_prompt_fragments`**（Step5.5 六段 JSON，缺省与 `step5_5_prompt_fragments.py` 内置默认合并）、**`step5_5_enabled`**（Step5.5 总开关，§2.7.1；`AdminConfigService.get_active_config`，Redis `active_config:step5_5_enabled`）；开关无库内生效行时视为关闭。管理端：**`admin/pages/prompt.html`**（Step5 + Step5.5 片段）、**`admin/pages/step5-5-switch.html`**（总开关）。


### 表名：admin_operation_logs


| 字段名                | 类型          | 必填  | 默认值    | 说明        |
| ------------------ | ----------- | --- | ------ | --------- |
| id                 | Integer PK  | 是   | 自增     |           |
| admin_user_id      | Integer     | 否   | NULL   | 可空（账号删除后仍保留日志，ORM `nullable=True`） |
| admin_username     | String(50)  | 是   | -      |           |
| module             | String(50)  | 是   | -      |           |
| action             | String(20)  | 是   | -      |           |
| target_description | String(500) | 否   | NULL   |           |
| before_value       | Text        | 否   | NULL   |           |
| after_value        | Text        | 否   | NULL   |           |
| ip_address         | String(50)  | 否   | NULL   |           |
| created_at         | DateTime    | 是   | utcnow |           |


---

## 接口定义

### 统一说明

- **H5 端**成功响应：`ApiResponse`，`code=0`（`SUCCESS`）表示成功；失败为业务错误码（如 `10001` 起，见 `constants.py`）。
- **管理后台**：除 SSE/文件流及下文单独说明外，**所有 JSON 业务接口成功响应信封统一为 `ApiResponse`**（`code=0` 成功；`code` 为 `**2xxxx**`（`ADMIN_ERR_*`）表示业务失败；**正常业务路径下 HTTP 状态码为 200**，与 H5 信封一致）。
- **鉴权失败**仍为 **HTTP 401 / 403**（由 `get_current_admin`、`require_role` 等 Depends 抛出 `HTTPException`，非业务层 JSON 信封）。
- **Pydantic 校验失败（422）**、**未捕获的服务器异常（500）** 等响应结构**不是** `ApiResponse`，前端需按 `admin-api.js` 中 `!resp.ok` 等逻辑兜底。
- **管理端 `adminRequest`**：第 5 参数可选 `{ silentErrorToast: true }`，抑制 `code≠0` 时的默认错误 Toast，便于调用方按业务码单独 `showToast`（例如用户禁用/启用 20012、20013）。
- **遗留**：`/api/admin/stats/*` 中部分参数错误仍可能为 `**HTTPException(400)`**；`/api/admin/third-party/*` 保存前连接失败可能为 `**ApiResponse.fail(code=5001)`**（与 `ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED=20040` 语义对应，后续可对齐）。
- **鉴权**：H5 为 `Authorization: Bearer`，JWT 用户端；后台为独立 Admin JWT（签名密钥 `ADMIN_JWT_SECRET`，与用户端独立），payload 含 `type=admin`、`role`、`sub`；**`sub` 为管理员用户 ID 的十进制字符串**（JWT 内非 JSON number），以满足 PyJWT 2.8+ 对 `sub` 的类型要求，服务端 `get_current_admin` 将其转为整数后查 `admin_users`。部分路由另需 `require_role(...)`。

#### 字段命名规范

- **基准**：以 **H5 用户端**已有接口为准，管理后台新建或改造分页接口时与之对齐。
- **列表数组字段名**：分页 `data` 内列表统一为 `**list`**（对齐 H5 `GET /api/memory/list`、`GET /api/relationship/growth-log`）；配合 `**total`、`page`、`page_size`**。
- **记录主键**：列表元素资源主键统一为 `**id`**（对齐 H5 记忆列表等）。
- **例外（历史约定，未改路由）**：H5 `**GET /api/chat/history`** 使用 `**messages`**；`**GET /api/diary/list`**、`**GET /api/chat/timeline**` 使用 `**items**`；管理后台各分页接口已统一采用 `**list` + `id**`（见下文用户管理、记忆、统计、系统日志等模块）。另：管理后台 `**GET /api/admin/accounts**` 成功时 `**data` 即为账号对象数组本身**（无分页对象包装），见「管理后台账号」模块。

#### Admin 错误码规范

- Admin 业务错误码从 **20001** 起，**边开发边补**全量枚举；常量命名格式 `**ADMIN_ERR_{模块}_{描述}`**（全大写下划线），定义于 `backend/constants.py`；与 H5 错误码（**10001** 起）**两套独立**，互不占用同一数值语义。
- 后台业务失败应返回 `**ApiResponse.fail(ADMIN_ERR_xxx, message=...)`**，文案可覆盖 `ADMIN_ERROR_MESSAGES` 中的默认描述。
- **依赖鉴权**（`backend/utils/admin_auth.py`）未使用本段枚举，仍为 **401/403** + `HTTPException.detail` 文案（如「未提供认证 Token」「权限不足」），不在 20001 列表内。

**当前已定义错误码及含义：**


| 常量名                                            | 数值    | 含义                  |
| ---------------------------------------------- | ----- | ------------------- |
| `ADMIN_ERR_AUTH_LOGIN_FAILED`                  | 20001 | 登录：账号不存在或密码错误（统一提示） |
| `ADMIN_ERR_AUTH_ACCOUNT_LOCKED`                | 20002 | 登录：账号已锁定            |
| `ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING` | 20003 | 登录：密码错误并提示剩余尝试次数    |
| `ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG`            | 20004 | 修改密码：旧密码不正确         |
| `ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD`      | 20005 | 修改密码：新密码与旧密码相同      |
| `ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH` | 20006 | 修改密码：两次新密码不一致       |
| `ADMIN_ERR_AUTH_PASSWORD_POLICY`               | 20007 | 管理员密码强度不符合要求        |
| `ADMIN_ERR_USER_NOT_FOUND`                     | 20008 | H5 用户不存在            |
| `ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY`          | 20009 | 编辑用户记忆：内容为空         |
| `ADMIN_ERR_USER_MEMORY_NOT_FOUND`              | 20010 | 记忆不存在或不属于该用户        |
| `ADMIN_ERR_USER_STATUS_ACTION_INVALID`         | 20011 | 禁用/启用：action 非法     |
| `ADMIN_ERR_USER_ALREADY_BANNED`                | 20012 | 用户已处于禁用状态           |
| `ADMIN_ERR_USER_NOT_BANNED`                    | 20013 | 用户未被禁用              |
| `ADMIN_ERR_ACCOUNT_USERNAME_EXISTS`            | 20014 | 创建管理员：用户名已存在        |
| `ADMIN_ERR_ACCOUNT_NOT_FOUND`                  | 20015 | 管理员账号不存在            |
| `ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE`     | 20016 | 不可修改自己的角色           |
| `ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF`         | 20017 | 不可删除自己的账号           |
| `ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER`        | 20018 | 超级管理员账号不可删除         |
| `ADMIN_ERR_PERSONA_FIELD_EMPTY`                | 20019 | 人格配置存在空字段           |
| `ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD`            | 20020 | 无草稿可丢弃              |
| `ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID`        | 20021 | 发布/回滚未输入 CONFIRM    |
| `ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED`     | 20022 | 发布前测试未通过            |
| `ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND`  | 20023 | 回滚目标版本不存在           |
| `ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE`         | 20024 | Prompt 模块不可编辑       |
| `ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING`         | 20025 | Prompt 缺少必填占位符      |
| `ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH`         | 20026 | 无待发布的 Prompt 草稿     |
| `ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID`      | 20027 | 记忆规则阈值或区间不合法        |
| `ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED`        | 20028 | 向量库连接测试失败（保存配置时）    |
| `ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`          | 20029 | 查询日期格式须为 YYYY-MM-DD |
| `ADMIN_ERR_AGENT_RULE_PARAM_INVALID`           | 20030 | Agent 规则数值参数越界      |
| `ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID`         | 20031 | trigger_type 非法     |
| `ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID`         | 20032 | 主动消息模板规则参数非法        |
| `ADMIN_ERR_RELATIONSHIP_RULE_INVALID`          | 20033 | 关系等级规则校验失败          |
| `ADMIN_ERR_DIARY_RULE_PARAM_INVALID`           | 20034 | 日记生成规则参数非法          |
| `ADMIN_ERR_EMOTION_CONFIG_INVALID`             | 20035 | 情绪配置非法              |
| `ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID`          | 20036 | 违禁词 Excel 不合法或无可导入词 |
| `ADMIN_ERR_SYSTEM_OPENPYXL_MISSING`            | 20037 | 服务器缺少 openpyxl      |
| `ADMIN_ERR_THIRD_PARTY_SERVICE_NAME_INVALID`   | 20038 | 第三方服务名非法            |
| `ADMIN_ERR_THIRD_PARTY_REQUEST_BODY_EMPTY`     | 20039 | 更新第三方配置：请求体为空       |
| `ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED` | 20040 | 第三方配置保存前连接测试失败      |
| `ADMIN_ERR_SYSTEM_LOG_QUERY_INVALID`           | 20041 | 系统日志查询/导出条件非法       |
| `ADMIN_ERR_STATS_QUERY_INVALID`                | 20042 | 数据统计查询/导出条件非法       |
| `ADMIN_ERR_TEST_CASE_MIN_RETAIN`               | 20043 | 删除测试用例将低于最少保留条数     |
| `ADMIN_ERR_TEST_CASE_NOT_FOUND`                | 20044 | 指定测试用例不存在           |
| `ADMIN_ERR_OPERATION_LOG_NOT_FOUND`            | 20045 | 操作日志记录不存在           |


---

### 模块：H5 认证（`/api/auth`）

#### POST /api/auth/register

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`RegisterRequest` — `username` string 必填 6–20 字母数字；`password` string 必填 8–20；`confirm_password` string 必填
- **响应**：`ApiResponse`；`data` 为 `{ token, user_id, username }`（`TokenData`）
- **关联表**：users, relationship（初始化）
- **状态**：已实现

#### POST /api/auth/login

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`LoginRequest` — `username`, `password` 必填；`remember_me` bool 默认 false
- **响应**：`ApiResponse`；`data` 同注册
- **关联表**：users, login_log
- **状态**：已实现

#### POST /api/auth/reset-password

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`ResetPasswordRequest` — `username`, `new_password`, `confirm_password`
- **响应**：`ApiResponse`；成功 `message` 文案
- **关联表**：users
- **状态**：已实现

#### POST /api/auth/logout

- **所属端**：H5
- **鉴权**：Bearer 用户 JWT
- **请求 Body**：无
- **响应**：`ApiResponse`
- **状态**：已实现（服务端无状态，客户端删 Token）

---

### 模块：H5 对话（`/api/chat`）

#### POST /api/chat/send

- **所属端**：H5
- **鉴权**：Bearer
- **请求 Body**：`ChatSendRequest` — `content` string 1–2000；**`client_message_id`** string 可选（≤64，建议 UUID，可与请求头 **`Idempotency-Key`** 一致，幂等语义以服务端实现为准）
- **响应**：**非 JSON 信封**；成功为 `StreamingResponse`（`text/event-stream`）。SSE 事件（JSON 行）包括但不限于：
  - **`meta`**：`{"type":"meta","generation_id":"<uuid>","message_count":<N>}` — 首包（CP2）；客户端应丢弃与当前有效代不一致的流片段（与 TD-015 一致）；`message_count` 表示本轮回复包含 N 条独立消息气泡（§2.9.4）
  - **H5 实现说明（`frontend/pages/chat.html`）**：每次发起 **`send` / `resend`** 前递增本地 **`chatSendSession`** 并 **`AbortController`** 打断上一请求；**不**再使用全局变量 **`sending`** 阻塞整段请求或 SSE 消费——**是否允许继续发**以服务端 **10104** 等为准，前端仅保留 **`countOpenPendingUsers`（未闭环 ≥5 且无叹号）** 预判与 **`CHAT_CLIENT_ABORT_MS`（120s）** 客户端中止；**防连点**：`send` 与叹号 **`resend` 共用** 时间戳 **`lastSendOrResendAt`**，在通过内容非空、队列预判之后、**即将 `fetch` 之前**若距上次不足 **`CHAT_SEND_DEBOUNCE_MS`（300ms）** 则 **静默 `return`**。**输入法与回车键**：`#msg-input` 设 **`enterkeyhint="send"`**（软键盘回车键语义；**具体标签以系统为准**），并使用 **`oncompositionend` / `onkeyup`** 同步调用 **`updateSendBtn()`**（与 `oninput` 并列），避免系统中文输入法下发送钮长期 **`disabled`**。**发送键与键盘**：`#send-btn` 声明 **`type="button"`**；**`updateSendBtn()`** 按 **`trim`** 同步 **`disabled` 属性** 与 **`.disabled`** 类，禁用态样式背景 **`#D8D8DC`**、前景 **`#8E8E93`**，有内容时主色可点；**`setupSendBtnKeepKeyboard()`** 在 **`initChat`** 中注册 **`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听，内 **`preventDefault`**，避免点击发送时焦点从 **`#msg-input`** 移到按钮导致移动端键盘自动收起；**`handleSend`** 仍仅由 **`click` / `onclick`** 触发（与 debounce、SSE 会话快照逻辑无冲突）。`consumeChatSse` 仅当传入的会话快照与 **`chatSendSession`** 一致时继续解析；收到 **`meta`** 后记录本连接 **`generation_id`** 与 **`message_count`**；若 **`delta`** 携带 **`generation_id`** 且与 **`meta`** 不一致则丢弃该条。服务端 DB / Redis 仍为权威真相，本段仅约束端上展示不串台。
  - **`delta`**：`{"type":"delta","content":"...","message_index":<0≤i<N>}` — 按条推送增量文本，`message_index` 标识目标气泡槽位（§2.9.4）
  - **`done`**：`{"type":"done","messages":[{"type":"text","content":"..."},...],"emotion":{"label":"...","confidence":0.0~1.0}}` — 完整 messages 数组为真相源（§2.7.5），整轮一个 emotion 对象（§2.7.3）；H5 收到后按 `done.messages` 渲染 N 个独立气泡，禁止预铺空气泡
  - **`failed`**：`{"type":"failed","code":<int>,"message":"..."}` — 超时/LLM 失败、**Step5 对外 `messages[].content` 任一条内容安全拦截**（`code`**10101**，见 **STEP-012** / §9.1）等，**不**写入 assistant 行
  - **`obsolete`**：本连接对应代已被新输入作废
- **失败（未进入 SSE）**：`ApiResponse` JSON — 如 **10101** 内容安全、**10104** 队列满（无叹号时未处理 ≥5）、**10102** 等
- **语义摘要**：用户输入内容安全通过后 **立即** 写入 user 行（`delivery_status=pending_llm`）；打包调度 **防抖**（默认 500ms，配置 `CHAT_DEBOUNCE_MS`）；主链路 Step5 LLM 超时 **45s**（`LLM_TIMEOUT_CHAT`）；Step5 解析成功后 **先** 对 **`inner_monologue`** 与 **`messages[].content`** 逐条跑与入队前同款的 `check_content`（§9.1 / §9.3，见 **STEP-012**）：`inner_monologue` 违规仅日志并替换为空串；**任一条 message 违规** → 整轮失败，user 行标 **`failed_blocked`**，不进入 Step5.5、不落 assistant；Step5 messages 全通过后，若 `admin_config` 中 **`step5_5_enabled`** 开启且双门闩命中，则 **追加** Step5.5 润色（HTTP 子超时 **30s**，见 STEP-009 / §2.7.4 D2）；**Step5.5 返回的 messages 亦逐条过安全**，违规则 **回退** Step5 合并后 messages（与 R-BND-06 一致）；成功闭环后按 **`final_messages` 条数 N** 写入 **N 行** `role=assistant`（每行一条气泡正文，连续 `sort_seq`，共享 `round_id`，见 **STEP-011** / §2.8.1）并异步后置任务（成长、记忆、`ai_emotion` 等；记忆拼接仍用整轮 `ai_reply`）；**Step6 入参仍仅用 Step5 原始 messages 合并结果**，不受 Step5.5 与安全替换后的对外文案影响（R-BND-05）；**Step6 记忆 LLM + 向量 + 关系写回**在落库成功后 **`asyncio.create_task` 异步入队**，不阻塞 SSE（**STEP-016** / §2.8.4 M2）
- **SSE 与后台 bundle 墙钟（`chat.py`）**：`_BUNDLE_WAIT_TIMEOUT_SEC`（默认 **120s**）仅限制 **`_sse_chat_wait_bundle`** 中 `asyncio.wait_for` 等待本代 **`generation` Future** 的最长时间；**不保证** **`_execute_llm_bundle`** 整段在服务端于 120s 内结束。Step1.5、Step5 等调用 **`llm_client.chat_sync`** 时，内层至多 **3 次** HTTP + 退避，单次超时分别为 **45s**（Step1.5 `_STEP1_5_TIMEOUT_SEC`）与 **`LLM_TIMEOUT_CHAT`（默认 45s，Step5）**，极端退化下 **SSE 可先返回超时/`failed` 而后台仍在执行**；与 **「部署与网关（对话 SSE）」** 中 Nginx 建议一并阅读。
- **关联表**：conversation_log, emotion_log（异步）；Redis `chat:gen:{user_id}`、防抖键、`ai_emotion:{user_id}` 等；**Step6**（§2.8.4 M2）：成功闭环后 **后台异步** 更新 DashVector 四类记忆文档 + `relationship` 标量/Future（失败不落库、不改 SSE，见 **STEP-016**）
- **状态**：已实现

#### POST /api/chat/resend

- **所属端**：H5
- **鉴权**：Bearer（**与 send 同域**；**禁止**管理端或 `/api/admin/` 代用户重发，L1）
- **请求 Body**：`ChatResendRequest` — `client_resend_id` 可选（≤128）
- **响应**：与 send 成功时相同 **SSE** 契约；当前未闭环窗口 **无** 叹号态 user 时 **10107**（`ERR_CHAT_NOTHING_TO_RESEND`）；超过 **2 次/分钟** 时 **10105**（`ERR_CHAT_RESEND_LIMIT`）
- **语义**：**不**插入新 user 行，仅对当前未闭环失败窗口再次调度 LLM
- **状态**：已实现

#### GET /api/chat/history

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page` int ≥1 默认 1；`page_size` int 1–50 默认 20
- **响应**：`ApiResponse`；`data`: `{ messages: [{id, role, content, emotion_label, created_at}], total, page, page_size }`
- **说明（H1）**：`messages[]` **不保证**包含 `delivery_status`、`sort_seq` 等送达字段；叹号恢复、与 Admin 列表对齐的送达态以 **`GET /api/chat/timeline`** 的 **`items[]`** 为准；history 与 timeline **能力可不一致**
- **关联表**：conversation_log
- **状态**：已实现

#### GET /api/chat/timeline

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`cursor` int 可选；`limit` int 1–50 默认 20
- **响应**：`ApiResponse`；`data`: `{ items: [...], next_cursor, has_more }`
- **`items[]`（conversation_log 来源）**：`source`, `sort_seq`, `id`, `content`, `created_at`, `emotion_label`, **`delivery_status`**, **`skipped_in_prompt`**, `is_read`, `trigger_type`（后两者对 agent 有值）；**`delivery_status` 取值**与 **`backend/constants.py`** 中单点常量一致（示例：`delivered`、`pending_llm`、`failed_timeout`、`failed_error`、`failed_blocked`），**不在**契约全文复制枚举表（J2）；**多气泡**：同一 `round_id` 下可有 **多条** `source=assistant` 行，按 `sort_seq` **升序**即为气泡展示顺序（与 SSE `done.messages` 下标一致，STEP-011）
- **assistant / agent 行**：`delivery_status`、`skipped_in_prompt` **键存在且值为 `null`**（A1）
- **关联表**：conversation_log, agent_message
- **状态**：已实现

#### 部署与网关（对话 SSE）

- **Nginx**：`location` 代理 H5 **`/api/chat/send`**、**`/api/chat/resend`** 时，建议 **`proxy_read_timeout` ≥ 130s**（在 **`_BUNDLE_WAIT_TIMEOUT_SEC` 默认 120s** 之上留余量），避免网关早于 **`_sse_chat_wait_bundle`** 的 `wait_for` 先断开。**注意**：120s 仅为 **SSE 等待 Future 的客户端侧上限**（见 **POST /api/chat/send** 语义摘要），**不是** `_execute_llm_bundle` 整段墙钟的硬上界；仓库内 `nginx/nginx.conf` 若已为 **300s** 则满足上述要求。旧稿「≥50s、略大于 Step5 单次 45s」**不足以**覆盖 Step1.5 + Step5 多 POST 退避 + Step5.5 等串联场景，以本条为准。

##### 环境与通用 LLM HTTP 超时

- **配置**：环境变量 **`LLM_TIMEOUT`**（秒），由 **`backend/config.py`** 的 **`get_llm_timeout_seconds()`** 读取；**代码默认值 45**（与 **`LLM_TIMEOUT_CHAT`** 默认对齐）。本地/部署时在项目根目录 **`.env`** 中设置（模板见 **`.env.example`**）；**`backend/config.py`** 在 import 时对 **`项目根目录/.env`** 执行 **`load_dotenv`**。
- **语义**：单次 HTTP 上限作用于 **`httpx` 请求**；同一调用仍可能经 **`llm_client.chat_sync` 内最多 3 次 POST**（`LLM_MAX_RETRIES=2`）+ **1s / 2s** 退避。
- **典型落点**（`timeout_sec` **未**传入 **`chat_sync`** 或与 **`get_llm_timeout_seconds()`** 同源）：**AI 日记**（`diary_service` 主/兜底两次 **`chat_sync`**）、**对话记忆提取 LLM**、**Agent 主动消息**（`llm_service.generate_with_fallback`）、**管理后台配置发布前人格测试集**（`admin_config_service` → **`chat_with_parse`**）、**`llm_client.chat_stream`**。
- **与主链路区分**：H5 **`send`/`resend`** 打包调度中的 Step5 / Step1.5 等使用 **`get_llm_timeout_chat_seconds()`**（**`LLM_TIMEOUT_CHAT`**）或路由内显式常量；**不**因本条而将 Step5 改为读取 **`LLM_TIMEOUT`**。

---

### 模块：H5 日记（`/api/diary`）

#### GET /api/diary/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`（1–50）
- **响应**：`ApiResponse`；`data` 为 `DiaryListResponse`：`items`（`DiaryItem`: id, content, relationship_level_at_creation, is_read, created_at, **covers_beijing_date** 可为 `null`）, total, page, page_size
- **说明**：成功响应 JSON **从不**包含 `diaries` 键；客户端须使用 **`items`**（与全局「字段命名规范」一致）。**`covers_beijing_date`** 为日记所覆盖的**北京日历日**；H5 列表日期展示优先使用该字段，缺失时回退 **`created_at`** 的本地解析（旧数据 H2 不回填）。
- **内容安全（产品已定案）**：AI 日记正文为系统生成内容，**当前**不对 LLM 输出做与 H5 用户消息同款的独立 `check_content`；合规边界以 PRD 与本条为准。
- **生成侧超时**：服务端调用 **`llm_client.chat_sync`** 未显式传 `timeout_sec` 时，单次 HTTP 上限为 **`get_llm_timeout_seconds()`**（环境变量 **`LLM_TIMEOUT`**，默认 **45s**）；内层重试与退避见 **「部署与网关」—「环境与通用 LLM HTTP 超时」**。
- **关联表**：ai_diary
- **状态**：已实现

#### POST /api/diary/{diary_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **Path**：`diary_id` int
- **响应**：`ApiResponse`；失败 `ERR_DIARY_NOT_FOUND`
- **关联表**：ai_diary
- **状态**：已实现

### `frontend/pages/diary.html`（H5 日记页）

- **接口**：仍仅消费 **`GET /api/diary/list`**（`items`）、**`POST /api/diary/{id}/read`**；**`items[]`** 含 **`covers_beijing_date`**（可为 `null`）。
- **初始化**：**不**以 `GET /api/relationship/status` 阻塞日记列表；关系等级在后台并行更新，用于空状态文案（`relationship_level` 仍可读 `localStorage` 兜底）。
- **列表日期**：优先使用 **`covers_beijing_date`** 格式化为「M月D日」；无该字段时回退 **`created_at`**。
- **空态与失败**：无数据时展示原有等级分支空状态；列表首屏失败时展示 **`#empty-error`** 与 **「重新加载」**（重置分页后重新 `init`）；`showEmptyState` 会先隐藏其它空态/错误块，避免叠显。
- **分页**：首屏或后续页无更多数据时置 **`noMore`**，避免无意义触底请求。

---

### 模块：H5 记忆（`/api/memory`）

#### GET /api/memory/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ total, page, page_size, list: [{id, content, importance_score, source, created_at, updated_at, expires_at}] }`
- **关联表**：memory
- **状态**：已实现

#### PUT /api/memory/{memory_id}

- **所属端**：H5
- **鉴权**：Bearer
- **Path**：`memory_id`；**Body**：`MemoryUpdateRequest` — `content` string 1–500
- **响应**：`ApiResponse`
- **关联表**：memory + 向量侧
- **状态**：已实现

#### DELETE /api/memory/{memory_id}

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`
- **状态**：已实现

#### POST /api/memory/add

- **所属端**：H5
- **鉴权**：Bearer
- **Body**：`MemoryAddRequest` — `content` 1–500
- **响应**：`ApiResponse`；`data` 为单条记忆字典（同 list 元素结构）
- **状态**：已实现

---

### 模块：H5 主动消息（`/api/agent`）

#### GET /api/agent/messages

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组 `{id, trigger_type, content, action_score, created_at}[]`（仅未读）
- **关联表**：agent_message
- **状态**：已实现

#### POST /api/agent/messages/{message_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`
- **状态**：已实现

#### GET /api/agent/unread-count

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`: `{ count: int }`
- **状态**：已实现

---

### 模块：H5 关系（`/api/relationship`）

#### GET /api/relationship/status

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level, level_name, growth_value, current_growth, next_threshold, progress_percent, silence_days, ai_current_emotion（见 `RelationshipService.get_relationship_info`）
- **关联表**：relationship；Redis
- **状态**：已实现

#### GET /api/relationship/history

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组：今日各行为 `action_type`, `earned_today`, `daily_limit`, `points_per_action`（读 Redis 旧 key 前缀 `growth:{user_id}:{date}:{action_type}`，写入侧同时写新旧 key，仍可读）
- **状态**：已实现

#### GET /api/relationship/detail

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level_info, growth_info, milestones, level_history, today_growth, ai_current_emotion
- **状态**：已实现

#### GET /api/relationship/growth-log

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ list, total, page, page_size }`（`list` 项：id, action_type, action_label, points, created_at）
- **关联表**：relationship_growth_log
- **状态**：已实现

---

### 模块：H5 用户（占位）

- **文件**：`backend/routers/user.py` 当前**无路由实现**；**未在 `main.py` 挂载**（保持不挂载）。
- **说明**：已在 `routers/user.py` **文件顶部**加入占位 TODO 注释；**产品需求确认前不挂载**，避免与其他模块路由命名冲突；实现昵称、头像等个人资料接口时在本文件扩展并再 `include_router`。
- **状态**：占位（详见该文件内注释）

---

### 模块：管理后台认证（`/api/admin/auth`）

#### POST /api/admin/auth/login

- **所属端**：管理后台
- **Body**：`AdminLoginRequest` — username, password
- **响应**：`ApiResponse`；`data`: token, username, role, need_change_password（**接口字段未变**；`token` 内嵌 JWT 的 `sub` 实现上为字符串，见上文「统一说明」鉴权条）
- **关联表**：admin_users；admin_operation_logs（登录日志）
- **状态**：已实现

#### POST /api/admin/auth/logout

- **Body**：无
- **响应**：`ApiResponse`；需 Bearer Admin JWT；成功 **`code=0`**，`data` 可为 `null`，**`message`**「已退出登录」
- **关联表**：admin_operation_logs（登出日志）
- **状态**：已实现

#### POST /api/admin/auth/change-password

- **Body**：`AdminChangePasswordRequest` — **`old_password`**、**`new_password`**、**`confirm_password`**（各 `min_length=1`，`max_length=100`）；新密码强度与 **`_validate_admin_password`** 一致（≥12 位，含大写、小写、数字、特殊字符）
- **语义**：当前登录管理员修改**本人**密码；校验旧密码通过后更新 `password_hash` 与 **`last_password_change_at`**，并记操作日志（`module=系统`，`action=edit`，描述含「修改密码」）
- **响应**：`ApiResponse`；成功 **`code=0`**，**`message`**「密码修改成功」；失败：**`20004`** `ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG`；**`20005`** `ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD`；**`20006`** `ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH`；**`20007`** `ADMIN_ERR_AUTH_PASSWORD_POLICY`（`message` 可为具体校验文案）
- **管理端**：**`admin/static/js/admin-api.js`** — **`renderHeader`** 渲染顶栏「修改密码」按钮；**`showChangePasswordModal()`** 弹窗收集三项密码，`adminRequest('POST', '/api/admin/auth/change-password', { old_password, new_password, confirm_password })`；前端先于请求校验非空及 **`new_password === confirm_password`**（不一致时 Toast「两次新密码不一致」，与后端 **20006** 语义一致）
- **状态**：已实现

---

### 模块：管理后台账号（`/api/admin`，super_admin）

- **GET** `/accounts` — 响应 `ApiResponse`；`**data` 为管理员账号的平铺数组**（**无** `total` / `page` / `page_size` / `list` 等分页包装）。单条字段：`id`, `username`, `role`, `remark`, `last_login_at`, `is_active`, `is_locked`, `created_at`（时间字段为 ISO 字符串或 `null`）。
- **POST** `/accounts` — Body：`AdminCreateAccountRequest` — `username`（1–50）、`password`（1–100，强度见下）、`role`（`super_admin`  `ops_admin`  `ai_trainer`  `tech_ops`）、`remark`（可选，≤200）。成功 `data` 为新账号 `_admin_to_dict`。前端 `**adminRequest(..., { silentErrorToast: true })`** 后按业务码处理：`**20014`**（`ADMIN_ERR_ACCOUNT_USERNAME_EXISTS`）→ Toast「账号名已存在，请换一个」；`**20007`**（`ADMIN_ERR_AUTH_PASSWORD_POLICY`）→ Toast「密码不符合复杂度要求」；其余非 0 → `message` 或「操作失败」。**密码复杂度**与后端 `_validate_admin_password` 一致，前端实时校验 5 项：≥12 位、含大写 A-Z、含小写 a-z、含数字 0-9、含特殊字符（非字母数字）。
- **PUT** `/accounts/{account_id}` — Body：`AdminUpdateAccountRequest`，**partial update**：`role`、`remark` 均为 **Optional**，**JSON 中未传或值为 `null` 的字段不修改**；`remark` 传空字符串 `""` 时表示清空备注。成功 `data` 为更新后的 `_admin_to_dict`。前端 `**silentErrorToast: true`** 时建议处理：`**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ Toast「账号不存在」；`**20016`**（`ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE`）→ Toast「不可修改自己的角色」（编辑他人账号时兜底；当前登录用户仅改自己备注时请求体应**只含 `remark`**、**不传 `role`**，避免误触 20016）。
- **POST** `/accounts/{account_id}/reset-password` — **管理员账号**重置密码（**勿与**用户管理 `**POST /api/admin/users/{user_id}/reset-password`** 混淆）。Body 无。成功 `data`：`{ "new_password": string }`，为 **16 位**随机强密码（含大小写、数字、特殊字符，满足 `_validate_admin_password`）。失败 `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ 前端 Toast「账号不存在」（建议 `silentErrorToast: true`）。**管理端 `accounts.html`**：确认弹窗后请求；成功后打开「密码重置成功」Modal 展示 `new_password`（`user-select: all` 等样式）；「复制密码」优先 `navigator.clipboard.writeText`，不支持时用临时 `textarea` + `document.execCommand('copy')`；「我已记录」关闭 Modal，**不刷新列表**。
- **POST** `/accounts/{account_id}/unlock` — Body 无。若账号**不存在** → `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）。若账号**未锁定**（`is_locked=false`）→ 仍返回 `**code=0`**（`ApiResponse.ok`），`message` 为「该账号未被锁定」——**非业务错误码**；前端可统一按 `code=0` 视为成功（如 Toast「账号已解锁」后刷新列表）。若已锁定则清除锁定与登录失败计数并记操作日志 → `code=0`，`message`「账号已解锁」。建议 `**silentErrorToast: true`**，`**20015**` → Toast「账号不存在」。
- **DELETE** `/accounts/{account_id}` — 成功 `code=0`，`message`「删除成功」（无额外 `data` 要求）。失败：`**20015`** 账号不存在；`**20017**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF`）不可删除自己；`**20018**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER`）超级管理员账号不可删除。前端 `**silentErrorToast: true**` 时建议：`20015` →「账号不存在」、`20017` →「不可删除自己的账号」、`20018` →「超级管理员账号不可删除」。
- **关联表**：admin_users
- **状态**：已实现
- **管理端页面**：`admin/pages/accounts.html`
  - Step 1：骨架、权限初始化（`checkAdminLogin` → 非 `super_admin` 跳转 `error.html?type=403` → `currentUsername` / `loadAccountList`）；`currentUsername` 与 `accountMap` 声明在 **script 顶层**，避免放在 `DOMContentLoaded` 闭包内导致全局 `onclick` 等函数无法访问。
  - **Step 2 完成**：列表加载（`GET /api/admin/accounts`）、`account-table-wrap` 内 **3 行骨架屏**、成功渲染表格列（账号 / 角色 / 备注 / 创建时间 / 最后登录 / 状态 / 操作）、失败或响应异常时文案「加载失败，请刷新重试」、空数组「暂无账号数据」；**行数据**在渲染前 `**accountMap.clear()`** 再 `**accountMap.set(id, row)`**；操作列 `**onclick` 仅传数值 `id`**，回调内 `**accountMap.get(id)**` 取完整行，**避免** `JSON.stringify` 写入 HTML 属性时特殊字符破坏引号。
  - **Step 3 完成**：**创建账号 Modal** — `openCreateModal()` 打开 `#create-account-modal-overlay`（`modal-overlay` + `modal-content` / `modal-header` / `modal-body` / `modal-footer`），并重置字段与校验状态；表单含账号（必填 max 50）、密码（必填，**oninput** 五项复杂度 ✓/✗，全绿且账号非空、确认密码一致、已选角色后启用「确认创建」）、确认密码（不一致时红色「两次密码不一致」）、角色 select（占位「请选择角色」）、备注 textarea（选填 max 200）；提交 **POST** `/api/admin/accounts`，成功关闭 Modal、Toast「账号创建成功」、`**loadAccountList()`**。
  - **Step 4 完成**：**编辑 Modal（含自身备注）** — **入口 A**（`row.username !== currentUsername`）：操作列「编辑」→ `openEditModal(id)`，打开 `#edit-account-modal-overlay`；打开时 `**resetEditAccountModal()`** 再写入行数据；顶部灰色说明「正在编辑：{username}」（`.modal-hint`）；角色 select 与 Step 3 相同选项、预填 `row.role`、必选；备注 textarea 预填、选填、**maxlength=200**；提交 **PUT** `/api/admin/accounts/{id}`，Body `**{ role, remark }`**（`silentErrorToast: true`），`**20015`** →「账号不存在」、`**20016**` →「不可修改自己的角色」；成功关闭、Toast「账号已更新」、`**loadAccountList()**`。入口 B（自身）：「修改备注」→ `openEditRemarkModal(id)`，打开 `#edit-remark-modal-overlay`；打开时 `**resetEditRemarkOnlyModal()**` 再写入；顶部说明「仅可修改自己账号的备注」；**不渲染角色下拉**（独立 Modal，DOM 中无角色字段）；提交 Body **仅 `{ remark }`**；成功 Toast「备注已更新」并 `**loadAccountList()**`。
  - **Step 5 完成**：**重置密码** — 非自身行操作列「重置密码」→ `openResetPasswordModal(id)`（`accountMap.get(id)`）；`**showConfirm`** 文案「确认重置「{username}」的密码？系统将生成新的强密码。」（用户名需 **HTML 转义** 后插入确认层）；确认后 **POST** `/api/admin/accounts/{id}/reset-password`（`silentErrorToast: true`），`**20015`** → Toast「账号不存在」；成功则 `**showResetPasswordResultModal(data.new_password)`**，`**#reset-password-result-modal-overlay`** 标题「密码重置成功」、正文说明 + 新密码展示区（monospace 20px 等）；「复制密码」→ Clipboard API + `**execCommand('copy')**` 兜底；「我已记录」或关闭 → `**closeResetPasswordResultModal()**`，**不** `loadAccountList()`。
  - **Step 6 完成（accounts.html 全部功能）**：**解锁** — `is_locked=true` 时操作列「解锁」→ `unlockAccount(id)`；`**showConfirm`**「确认解锁「{username}」的账号？」（用户名 **escapeHtml**）；**POST** `/api/admin/accounts/{id}/unlock`（`silentErrorToast: true`）；`**code=0`** → Toast「账号已解锁」、`**loadAccountList()**`（含未锁定账号误触时后端仍 `code=0` 的约定）；`**20015**` →「账号不存在」。**删除** — 非自身且非 `super_admin` 行「删除」→ `deleteAccount(id)`（自身无删除按钮、`super_admin` 行按钮 `disabled` 已在 Step 2）；`**showConfirm(..., null, { danger: true })`**（`admin-api.js` 危险样式：`modal-content--danger` + 确认钮 `btn-danger`），文案「确认删除「{username}」？此操作不可恢复。」；**DELETE** `/api/admin/accounts/{id}`（`silentErrorToast: true`）；`**20017`** / `**20018**` / `**20015**` 对应上述 Toast；成功 Toast「账号已删除」、`**loadAccountList()**`。

---

### 模块：管理后台操作日志（`/api/admin`）

- **GET** `/operation-logs`（Query：admin_username, module, action, start_date, end_date, page, page_size）
- **GET** `/operation-logs/{log_id}`
- **POST** `/operation-logs/export`（Excel 流）
- **导出参数说明**：服务端以 **Query** 接收 `admin_username`、`module`、`action`、`start_date`、`end_date`（与列表筛选一致），**非** JSON Body；前端 `POST` 时将条件拼在 URL 查询串上、Body 为空即可触发 `adminRequest` 的 blob 下载逻辑。
- **响应列表**：`data`: `{ total, page, page_size, list: [...] }`；`list[]` 含 `id`, `admin_user_id`, `admin_username`, `module`, `action`, `target_description`, `ip_address`, `created_at`
- **详情**：`GET /operation-logs/{log_id}` 成功 `data` 另含 `before_value`, `after_value`（可为 `null`）
- **关联表**：admin_operation_logs
- **鉴权角色**：`super_admin` / `ops_admin` / `tech_ops`（`ai_trainer` 无此菜单与接口权限）
- **状态**：已实现
- **管理端页面**：`admin/pages/operation-logs.html`
  - 首屏：`DOMContentLoaded`（若文档已就绪则立即执行）触发 `loadLogs(1)`。
  - 筛选：`admin_username` 输入框；`module` / `action` 下拉的选项与当前仓库内所有 `log_operation(..., module=, action=)` 写入值一致（模块：`ai_config`、`memory`、`third_party`、`用户管理`、`账号管理`、`系统`；类型：`batch_delete`、`create`、`delete`、`edit`、`login`、`logout`、`publish`、`unlock`、`update_config`）；日期 `start_date` / `end_date`；搜索/重置调用 `loadLogs(1)`；**导出 Excel** 为 `POST /api/admin/operation-logs/export` + 当前筛选的 Query 串。
  - 列表：`page_size=20`，列 时间 / 操作人 / 操作模块 / 操作类型 / 操作描述 / 详情；操作类型 Tag：`publish`→`tag-success`，`delete` 与 `batch_delete`→`tag-error`，`rollback`→`tag-warning`（仅当库中仍存在该 `action` 的旧记录时可能见到），其余→`tag-default`。
  - 详情：`GET /api/admin/operation-logs/{id}`，Modal 宽 680px，展示操作人/模块/类型/时间/IP，修改前（`#fff2f0`）与修改后（`#f6ffed`）`<pre>` 对比，无数据展示「（无）」。
  - **说明**：`action` 筛选下拉的选项**仅包含**当前代码路径里 `log_operation(..., action=)` 的实际写入值，**不包含** `rollback`。人格/Prompt 等「回滚」接口经 `AdminConfigService.rollback_config` → `publish_config` 记日志时，`action` 为 **`publish`**（`target_description` 等可体现回滚语义）。

---

### 模块：管理后台用户管理（`/api/admin`）

- **GET** `/users` — Query 筛选 username, relationship_level, status, 注册/登录时间范围, page, page_size；`data.list` 含 id, username, created_at, last_login_at, relationship_level, growth_value, total_conversation_count, status
- **管理端列表页（`admin/pages/users.html`）**：表格首列展示 **`list[].id`（用户 ID）**，便于与日记历史等处的 `user_id` 对照；接口字段未增删。
- **说明（关系字段数据源）**：**用户列表** `data.list[]` 与**详情页展平后的** `**userData`** 使用字段名 `**relationship_level`、`growth_value`**；详情接口原始 JSON 中对应为 `**data.relationship.level`、`data.relationship.growth_value`**。上述数值均来自 `**relationship` 表**（模型字段 `Relationship.level`、`Relationship.growth_value`），与用户端 `RelationshipService` 权威读法一致（按 `user_id` 关联；无行时按等级 0、成长值 0）。`**users` 表同名列为历史遗留，本模块不作为数据源**，详见 `[tech-debt.md](tech-debt.md)` **TD-001**。
- **GET** `/users/{user_id}` — 响应 `data` 为嵌套对象（HTTP 层不变）：
  - `**basic`**：`id`, `username`, `created_at`, `last_login_at`, `status`（`normal`  `banned`）, `is_banned`
  - `**relationship`**：`level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`
  - `**activity`**：`total_conversation_count`, `active_days_last7`, `agent_message_reply_count`
- **管理端详情页（`admin/pages/user-detail.html`）**：成功拉取详情后，仅在 `**loadUserDetail`** 内将上述嵌套**展平**为脚本内存变量 `**userData`**（不修改接口响应）。展平规则：`basic.*` 字段名保持不变；`relationship.level` → `relationship_level`；`relationship` 其余键名不变；`activity.active_days_last7` → `active_days_7d`；`activity.agent_message_reply_count` → `agent_reply_count`；`activity.total_conversation_count` 不变。若 `data` 缺少 `basic` / `relationship` / `activity` 任一层，前端提示「用户详情数据格式异常」且不写入 `userData`。**「AI日记」Tab**：**首次**切换到该 Tab 时请求 **`GET /users/{user_id}/diaries`** **不带**日期（全量时间、倒序第一页）；再次进入同一用户详情会话内 **不重复**首屏请求；**「查询」**按当前日期输入从第 1 页重拉；**「加载更多」**在同一组日期条件下分页追加；表格列含日记 **`id`**（与 **`diary-history`** 第一列一致）、正文摘要、`relationship_level_at_creation` 映射等级名、已读、**`covers_beijing_date`（覆盖日）**、创建时间；正文 **`escapeHtml`**。
- `**userData` 展平后字段全集**（仅浏览器脚本内存，**非** HTTP 响应体）：`id`, `username`, `created_at`, `last_login_at`, `status`, `is_banned`, `relationship_level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`, `total_conversation_count`, `active_days_7d`, `agent_reply_count` — 与 `loadUserDetail` 实现一致，供 `renderInfoCards`、账号 Tab、顶栏操作等读取。
- **GET** `/users/{user_id}/conversations` — **数据源**：合并 **`conversation_log`** 与 **`agent_message`**（主动消息仅存在于后者，与 H5 一致）。**Query**：`start_date`、`end_date`（与改前相同，两表均按 `created_at` 过滤）、`page`、`page_size`（1–100）。**排序**：全局 **`sort_seq` 升序**，同 `sort_seq` 时 **`id` 升序**（再分页），与用户端时间线合并规则一致。**`data.total`**：两表在日期条件下的行数之和。**`data.list[]` 公共字段**：`id`、`role`、`content`、`persona_risk_flag`、`created_at`、`sort_seq`。**来源区分**：**`message_source`** — `conversation`（来自 `conversation_log`）| `agent`（来自 `agent_message`）。两表各自自增 `id` 可能数值重合，**唯一键为 `(message_source, id)`**。——**`message_source === conversation`**：`emotion_label`、`emotion_confidence`（仅 user 行）、`delivery_status`、`skipped_in_prompt`（assistant 行二者均为 **null**，user 行按库）；**`trigger_type`、`is_read` 固定为 null**。——**`message_source === agent`**：`role` 固定 **`assistant`**，`emotion_*` 为 null，`persona_risk_flag` 固定 **false**，`delivery_status` / `skipped_in_prompt` 为 **null**，**`trigger_type`** 为 `agent_message.trigger_type`（如 `P0`…`P4`、`FUTURE`），**`is_read`** 为布尔。与 H5 **`GET /api/chat/timeline`**：`items[]` 中对话行对应 `source` 为 `user`/`assistant`，主动消息对应 `source: agent`；管理端使用字段名 **`message_source`** 而非 `source`，语义可对齐查阅。
- **管理端详情页「历史对话」Tab（`admin/pages/user-detail.html`）**：列表渲染读取 **`message_source`**；**`agent`** 行展示 **`trigger_type`** 标签及 **`is_read === false`** 时的「未读」标签，气泡左侧条样式与主动消息区分。
- **GET** `/users/{user_id}/diaries` — 鉴权 **`super_admin` / `ops_admin` 仅**（与 **`.../conversations`**、**`GET /diary-history`** 一致；**不含** `ai_trainer`，与 **`.../memories`** 不同，属有意区分）。Query：`start_date`、`end_date`（`YYYY-MM-DD`，与 **`diary-history`** 语义相同）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**；日期非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`**。成功 `data`：`{ total, page, page_size, list }`；**`list[]`** 字段与 **`GET /api/admin/diary-history`** 的 **`list[]`** 相同：`id`, `user_id`, `username`, `content`, `relationship_level_at_creation`, `is_read`, `created_at`, `covers_beijing_date`。实现上与 **`diary-history`** 共用 **`backend.services.admin_diary_query`**，避免双入口不一致。
- **GET** `/users/{user_id}/memories` — `data.list` 含 id, content, importance_score, source, created_at, updated_at
- **PUT** `/users/{user_id}/memories/{memory_id}` — Body：`AdminMemoryUpdateRequest` — `content`（必填，1–500 字，去首尾空白后不得为空）；`importance_score`（可选，0.0–1.0，**预留**，当前不落库）
- **DELETE** 同上路径
- **PUT** `/users/{user_id}/status` — Body `{ "action": "ban"|"unban" }`
- **POST** `/users/{user_id}/reset-password` — `data.new_password`
- **管理端页面**：`admin/pages/user-detail.html` 含「账号管理」Tab 与顶栏按钮，对接上述 PUT/POST；逻辑上 `**userData.status === 'banned'`** 与 `**basic.status`** 及用户列表 `list[].status` 一致（见错误码 20012、20013）；展示与操作均基于展平后的 `userData`（见上条）。
- **关联表**：users, **relationship**, conversation_log, memory, agent_message 等
- **状态**：已实现

---

### 模块：向量召回与 Prompt Token 热配置（`/api/admin/configs`，STEP-025）

- **鉴权**：Bearer Admin JWT；角色 **`super_admin` / `ai_trainer`**（`ops_admin` / `tech_ops` 等 → **HTTP 403**）。
- **GET** `/vector_retrieval_config` — 成功 `data`：`{ top_k, threshold }`（与 `multi_vector_retrieval_service` 默认 **TopK=3、阈值=0.7** 及库中已发布行合并后的**完整**对象，供管理端表单展示）。
- **PUT** `/vector_retrieval_config` — Body：`{ "top_k"?: int, "threshold"?: float }`（均为可选，**至少提供其一**且不得为 `null`；**禁止**多余字段）。语义为 **PATCH**：与当前 `admin_config` 生效 JSON 及上述默认值合并 → **`admin_config_service.publish_config`** → MySQL 新版本 + Redis **`active_config:vector_retrieval_config`**。`top_k` 合法 **1–20**；`threshold` **0.0–1.0**。无任何有效更新字段 → **`20046`**（`ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`）。发布写入 **`admin_operation_log`**（`log_operation`，`module=ai_config`，`action=publish`，`target_description` 含配置键）。
- **GET** `/prompt_token_config` — 成功 `data`：`{ max_total, system, persona, character_knowledge, relationship, memory, emotion, time_activity, recent_chat, user_input }`（与 `prompt_builder` 默认上限及库中已发布行合并后的完整对象）。
- **PUT** `/prompt_token_config` — Body：上列字段均可选，**至少其一**，整数下界 **1**（`max_total`/`system`/… 各自 Pydantic `ge=1`，`max_total` `le=50000`，模块单项 `le=20000`），**禁止**多余字段。PATCH 合并后整包发布，Redis **`active_config:prompt_token_config`**。
- **错误与 HTTP**：请求体非 JSON 或无法解析为对象 → **HTTP 422**；字段类型/范围违反 Pydantic → **422**；业务侧「空 PATCH」或合并后校验失败 → **信封 `code=20046`**（`message` 可含具体原因）。
- **关联表**：`admin_config`（`config_key` 分别为 `vector_retrieval_config`、`prompt_token_config`）；**Redis**：`active_config:{config_key}`，以及发布流程中的 `publish_monitor:{config_key}`（与既有 `AdminConfigService.publish_config` 一致）。
- **运行时消费**：Step2 `execute_multi_vector_retrieval` 与 `PromptBuilder._load_token_limits` 仍通过 `admin_config_service.get_active_config` 读取（见 STEP-020 / STEP-021 契约摘要）；本模块仅提供管理端读写入口。
- **管理端页面**：`admin/pages/vector-token-config.html` — Tab「向量召回」「Prompt Token」；`admin-api.js` 菜单键 **`vector-token`**（`super_admin` 与 `ai_trainer` 的 `MENU_CONFIG`）；保存时脚本对比首屏快照，**仅提交有变化的字段**以契合 PATCH 语义。
- **状态**：已实现

---

### 模块：人格 / 情绪 / 世界观 / Prompt / 安全 / 测试用例

- **人格**：`GET/PUT/DELETE /persona/draft`，`GET /persona/current`，`POST /persona/test|publish`，`GET /persona/history`，`GET /persona/history/{version}`，`POST /persona/rollback` — Body 见 `persona.py` 内联模型
- **GET /api/admin/persona/history/{version}**：鉴权与角色同其他人格接口（`super_admin` / `ai_trainer`）。成功 `data`：`version`, `is_active`, `updated_by`, `updated_at`, `content`（JSON 解析后的对象，解析失败时为原始字符串）。版本不存在 → `20023`（`ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND`），`message` 为「版本 V{n} 不存在」。
- **POST /api/admin/persona/test** 成功 `data`（`admin_config_service.run_standard_tests`）：`total`, `passed`, `failed`, `pass_rate`, `can_publish`, `details`（数组），可选 `message`（如无测试用例等）。`details[]` 含 `case_id`, `input`, `ai_reply`, `total_score`, `level`, `style_score`, `boundary_score`, `emotion_score`, `violations`, **`passed`**（布尔，与该条是否计入通过一致，供管理端展示 Tag）。
- **情绪**：`GET /emotion-config`；`PUT /emotion-config/{emotion_name}` — `EmotionUpdateRequest`
- **世界观**：`GET|PUT /world-state/config`；`GET /world-state/history`
- **Prompt**（实现见 `backend/routers/admin/prompt_mgmt.py`；鉴权均为 **`super_admin` / `ai_trainer`**）：
  - **废弃说明**：旧版 **`prompt_modules`**（七模块）相关接口 **`GET /prompt/modules`、`PUT /prompt/draft/{module_name}`、`DELETE /prompt/draft`（旧）、`POST /prompt/publish`（旧）、`GET /prompt/history`（旧）、`POST /prompt/rollback`（旧）** 已移除；库内若仍存在 `config_key=prompt_modules` 的历史行可运维手工删除，**运行时不再读取**。
  - **运行时配置键**：**`step5_system_prompt`** — Step5 模块1 System（JSON `{"content": string}`）；**`step5_5_prompt_fragments`** — Step5.5 六段（JSON 对象，键：`system`、`style_rules`、`ctx_readonly`、`relation_brief`、`history_brief`、`messages_input`，占位符与发布校验见服务端）；**`step5_5_enabled`** — 总开关（与 STEP-009 一致）。
  - **Step5 System**：`GET /api/admin/prompt/step5`（`data`：`version`、`has_draft`、`content`、`baseline_is_builtin`）；`GET /api/admin/prompt/step5/draft`；`PUT /api/admin/prompt/step5/draft` Body `{ "content": string }`；`DELETE /api/admin/prompt/step5/draft`；`POST /api/admin/prompt/step5/publish` Body `confirm_text`、`test_passed`（发布前校验 Step5 JSON 契约字段名子串：`inner_monologue`、`messages`、`relation_change`、`future`、`emotion`、`knowledge_expand`）；`GET /api/admin/prompt/step5/history`、`GET /api/admin/prompt/step5/history/{version}`、`POST /api/admin/prompt/step5/rollback`。
  - **Step5.5 六段**：`GET /api/admin/prompt/step5-5/fragments`（`data.fragments`、`fragment_keys`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5/draft`；`PUT /api/admin/prompt/step5-5/draft/{fragment_key}` Body `{ "content": string }`（`fragment_key` 限于六键）；`DELETE /api/admin/prompt/step5-5/draft`；`POST /api/admin/prompt/step5-5/publish`（占位符与 system 段契约关键词校验）；`GET /api/admin/prompt/step5-5/history`、`GET .../history/{version}`、`POST .../rollback`。
  - **Step5.5 总开关**：`GET /api/admin/prompt/step5-5-switch`（`enabled`、`draft_enabled`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5-switch/draft`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ "enabled": bool }`；`DELETE .../draft`；`POST .../publish` Body `confirm_text: CONFIRM`（**不要求**先跑主链 LLM 在线测试；可与 `test_passed` 一并提交）；`GET .../history`、`POST .../rollback`。
  - **在线测试**：`POST /api/admin/prompt/test` — Body：`test_input`（必填）、`relationship_level`（0–3）、`emotion_label`、`mock_memories`（字符串数组）、`use_draft`（bool，为 `true` 时用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致，LLM **`chat_with_step5_parse(..., is_test=true)`**；成功 `data`：`full_prompt`、`ai_reply`（`messages[].content` 合并）、`persona_match`、`content_safety`、`token_estimate`。
- **安全**（`backend/routers/admin/safety_rules.py`，前缀 `/api/admin`）：
  - **GET** `/safety-rules` — 成功 `data`：`banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords`（均为 `string[]`，无生效配置时为空数组）。
  - **PUT** `/safety-rules/banned-keywords` — Body：`{ "keywords": string[] }`（Pydantic `KeywordsUpdateRequest`：**`keywords` 至少 1 个元素**）。
  - **PUT** `/safety-rules/persona-keywords` — 同上。
  - **PUT** `/safety-rules/style-keywords` — 同上。
  - **POST** `/safety-rules/banned-keywords/import` — `multipart/form-data`，字段名 **`file`**（`.xlsx` / `.xls`）；与现有违禁词合并去重后发布。成功 `data`：`imported_count`（本次从表格读取到的非空行数）、`total_count`（合并去重后的词库总数）。
- **测试用例**：`GET|POST /test-cases/{config_key}`；`DELETE /test-cases/{config_key}/{case_id}`。**POST Body**（`TestCaseCreateRequest`）：`input`（必填）、`expected_pass_criteria`（必填）、`emotion_label`（默认 `平静`）、`relationship_level`（默认 `1`，0–3）。成功 `data`：`case`、`total_count`，并与 `publish_config` 成功回执字段合并返回。
- **响应**：`ApiResponse`
- **关联表**：admin_config（及部分 Redis）
- **状态**：已实现

---

### 模块：记忆与向量（管理）

- **GET** `/memory-rules` — 成功 `data` 为当前生效 JSON 对象；**无生效配置时 `data` 可为 `null`**（前端使用内置默认值：`extract_prompt` 空串；`importance_rules` 四类默认分值 4/3/2/1；`store_threshold=3`；`search_threshold=0.7`；`merge_threshold=0.92`）。
- **PUT** `/memory-rules` — Body `MemoryRulesRequest`：`extract_prompt`（string）；`importance_rules`（**长度须为 4**，元素 `{ type, score }`，`type` 为四类之一）；`store_threshold`（int，**服务端校验 1–4**）；`search_threshold`（float，**0.5–0.85**）；`merge_threshold`（float，**0.85–0.98**）；且 **`merge_threshold` 须严格大于 `search_threshold`**（否则返回 `ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID`）。
- **GET** `/vector-db-config` — 成功 `data`：`endpoint`、`collection_name`、`top_k`、**`api_key_masked`**（脱敏，不含明文 `api_key`）；无 DB 配置时回退读环境变量并同样返回 `api_key_masked`。
- **PUT** `/vector-db-config` — Body `VectorDbConfigRequest`：`endpoint`、`collection_name`、`top_k`（Pydantic 默认 5，**无 1–20 上限校验**）；`api_key` 可选（不传则保留库内原值）；`need_test_first`（bool，**为 `true` 时保存前会先测连**，失败则拒绝保存）。管理页保存可传 `need_test_first:false`，依赖前端「先测后存」。
- **POST** `/vector-db-config/test-connection` — Body `VectorDbTestRequest`（字段均可选）：`endpoint`、`collection_name`、`api_key`；缺省时从已发布配置或环境变量补全。成功 `data`：`connected`（bool）、`latency_ms`、`error`（字符串）。
- **GET** `/memories/global` — `data.list` 中单条主键字段名为 `**id`**（与 H5 记忆列表一致）；其余字段含 user_id, content, importance_score, source, created_at
- **DELETE** `/memories/batch-delete` — Body `BatchDeleteRequest`：`memory_ids`
- **状态**：已实现

---

### 模块：Agent 管理

#### GET /api/admin/agent-night-keywords

- **所属端**：管理后台
- **鉴权**：Bearer Admin JWT（角色同 PUT：`super_admin` / `ai_trainer`）
- **响应**：`ApiResponse`；`data` 与 **PUT** Body 一致：`{ "keywords": string[] }`（无生效配置时 `keywords` 为空数组 `[]`）
- **数据来源**：`get_active_config("agent_night_keywords", use_cache=False)`（查 **admin_config** 当前生效行，**不**经 Redis）
- **关联表**：admin_config
- **同模块其它路由**：**GET|PUT** `/agent-rules` — `AgentRulesRequest`；**GET** `/agent-message-rules`（整包）/ **PUT** `/agent-message-rules/{trigger_type}`（单类型）；**PUT** `/agent-night-keywords` — `NightKeywordsRequest`；**GET** `/agent-messages` — 分页 `data.list`
- **状态**：已实现

---

### 模块：关系规则与日记（管理）

- **GET|PUT** `/relationship-rules` — 两阶段 `confirmed` 预览/发布
- **GET|PUT** `/diary-rules` — `DiaryRulesRequest`（见下文字段）；PUT 发布写入 `admin_config`，Redis `active_config:diary_rules`
- **GET** `/diary-history` — Query：`user_id`、`start_date`、`end_date`（`YYYY-MM-DD`）、`page`、`page_size`（1–100）；鉴权 **`super_admin` / `ops_admin`**；成功 `data`：`{ total, page, page_size, list:[{ id, user_id, username, content, relationship_level_at_creation, is_read, created_at, covers_beijing_date }] }`（**`username`** 来自 `users.username`，与 `user_id` 内联；**`start_date`/`end_date` 仍按 `created_at` 过滤（F1）**）。列表查询与 **`GET /users/{user_id}/diaries`**（固定路径用户）共用 **`fetch_admin_diary_list_page`**，在相同 **`user_id` + 日期 + 分页** 下结果一致。
- **状态**：已实现

**`DiaryRulesRequest`（PUT `/diary-rules` Body）**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `max_length` | int | 是 | 50–300 |
| `frequency` | str | 否 | 默认 `daily` |
| `generation_hour` | int | 是 | **0–23**（**北京时间**，与 APScheduler **`Asia/Shanghai`** Cron 一致） |
| `generation_minute` | int | 否 | 0–59，默认 **15**（代码回退默认与 `diary_rules_loader` 一致） |
| `prompt_with_interaction` | str | 条件 | 与 `prompt_without_interaction` **同时非空**时生效 |
| `prompt_without_interaction` | str | 条件 | 同上 |
| `generation_prompt` | str | 条件 | **兼容旧版**：非空时等价于两套 Prompt 使用同一文本（服务端同时写入双字段与 `generation_prompt` 键） |

三者至少满足：**双 Prompt 同时填写** 或 **仅 `generation_prompt`**，否则 `ADMIN_ERR_DIARY_RULE_PARAM_INVALID`。

---

### 模块：数据统计（`/api/admin/stats`）

- **GET** `/stats/dashboard` — `**ApiResponse`**，所有登录管理员可访问；`data` 为**嵌套对象**（按角色裁剪）：
  - `super_admin` / `ops_admin`：`user`（`new_users_today` 等）、`retention`（`next_day_retention` / `day7_retention` / `day30_retention`，可 `null`）、`conversation`、`agent`、`ai_performance`
  - `ai_trainer`：仅 `ai_performance`
  - `tech_ops`：空对象 `{}`
  - `ai_performance.llm_avg_response_ms`：**无 Redis 响应时间样本时为 `null`**（与真实平均 **0** ms 区分）；`llm_success_rate` 可 `null`
  - **人格偏离率**（`persona_deviation_rate`）：当日 `persona_risk_flag=true` 条数 / 当日 **`role=assistant`** 的 `conversation_log` 条数 × 100%（与 `stats_service._get_ai_performance_data` 一致）
- **GET** `/stats/trend` — Query `metric`, `days`；`data` 为 **`[{ date, value }, ...]`** 数组（非 `dates`/`values` 对象）；需 `super_admin` / `ops_admin`
- **GET** `/stats/report` — Query report_type, start_date, end_date, page, page_size；`data`: `{ list, total, page, page_size, extra }`
- **POST** `/stats/report/export` — Query 同报表条件，Excel 流；`ai_performance` 导出列第三表头为 **「AI回复数」**（对应 `total_count`，assistant 条数）
- **说明**：`report_type=user` 时 `extra.level_distribution` 按 `**relationship.level`** 统计（无行用户计入 level 0），与后台用户列表关系字段数据源一致；**该分布为当前全量用户快照，不随 `start_date`/`end_date` 过滤**（与 `list[]` 按日明细不同）。
- **状态**：已实现

---

### 模块：系统监控与第三方（`/api/admin`）

- **GET** `/system/status`；**GET** `/third-party/status` — `ApiResponse`
- **PUT** `/third-party/{service_name}/config` — Body 自由 dict；保存前服务端用「已发布配置 ∪ Body」合并后做连通性测试（失败则 `ApiResponse.fail` code=5001，不落库）
- **POST** `/third-party/{service_name}/test-connection` — 可选 **JSON Body**（字段与 PUT 一致片段即可，如 `endpoint`、`api_key`）；服务端将 Body 与**当前已发布** `admin_config` 中对应 `third_party:*` 配置 **合并** 后调用与 PUT 相同的探测逻辑；无 Body 或 `{}` 时等价于仅用已发布配置 + 各探测函数内对环境变量的回退
- **GET** `/system/logs` — Query：`log_type`（`system` \| `error`，对应 `_LOG_TYPE_FILE_MAP`）、可选 `level`、可选 `start_date`/`end_date`（缺省为近 7 天）、`page`/`page_size`；成功 `data`：`{ total, page, page_size, list:[{ time, level, module, message }] }`（**`list` 按日志时间 `time` 降序，最新在前**）；**POST** `/system/logs/export` — Query 条件同上、**无 Body**；成功为 **xlsx 流**（非 JSON 信封）；范围校验失败 HTTP 400；**查询**区间 `(end-start).days > 30`、**导出** `> 7` 被拒绝（与 `system_monitor.py` 一致）；导出文件内行顺序与列表查询一致（同条件下按 `time` 降序）
- **说明**：`system_monitor.py` 末尾有 `# TODO: 后续接口`
- **状态**：已实现（除标注 TODO 部分）

---

## 管理端页面

### `admin/pages/system-monitor.html`（系统监控）

- **权限**：`super_admin` / `tech_ops`；其余角色跳转 `error.html?type=403`。
- **接口**：`GET /api/admin/system/status`（**10 秒缓存**，后端 Redis key `cache:system_status`，已处理）；请求使用 `admin-api.js` 的 **`adminRequest`**，无单独封装函数。
- **响应 `data` 结构**：`cpu:{ percent, cores }`；`memory:{ percent, total_gb, used_gb }`；`disk:{ percent, total_gb, used_gb }`；`redis:{ hit_rate, used_memory, connected_clients }`；`alerts:[{ level:'warning'|'critical', message }]`.
- **展示约定**：四张指标卡为 **纯 SVG 环形进度**（`stroke-dasharray` 控制弧长，周长按 \(2\pi\times34\)）；**Redis 命中率**色阶与 CPU/内存/磁盘相反（高为好）。Redis 卡副文案按产品与需求仅展示 **「已用内存：{used_memory}」**（`connected_clients` 由接口提供但本页不展示）。
- **CPU 趋势**：ECharts 折线，内存数组最多 **60** 点，与前端 **每 10 秒** 拉取一次对齐，覆盖约 **近 10 分钟**；标题为「近10分钟 CPU 趋势」，**不写「近1小时」**。
- **告警列表**：接口无单条时间字段时，各行左侧时间为 **本次刷新时刻**；若未来扩展字段见 **`docs/tech-debt.md` [TD-010]**。
- **生命周期**：`beforeunload` 时 `clearInterval` 释放定时器；`resize` 时 `cpuChart.resize()`。

### `admin/pages/system-logs.html`（系统日志）

- **权限**：`super_admin` / `tech_ops`；其余角色跳转 `error.html?type=403`。
- **Tab**：仅 2 个（`system` / `error`），无第三方服务日志 Tab；`activeKey='system-logs'`，顶栏标题「系统日志」。
- **调用**：`GET /api/admin/system/logs`
  - `log_type` 枚举：`system` \| `error`（对应后端 `_LOG_TYPE_FILE_MAP` → `system.log` / `error.log`）。
  - 日期参数：`YYYY-MM-DD`（`type="date"` 原生值，与后端 `datetime.date` 一致）。
  - 单次查询区间：后端拒绝 `(end_date - start_date).days > 30`；前端前置校验一致。
- **导出**：`POST /api/admin/system/logs/export`（仅 Query，无 Body）；`adminRequest('POST', url)` **不传 `data`** 以走 `admin-api.js` 的 blob/xlsx 下载分支。
  - 单次导出：后端拒绝区间 `days > 7`；前端前置校验与后端一致（避免前后端口径不一）。
- **状态**：`system` / `error` 各自维护 `pageState`（含 `hasQueried`：仅在该 Tab **从未成功请求过列表**时，切换 Tab 自动触发首次 `queryLogs`；**已加载但 0 条**不重复自动请求）；`page_size=50`；分页使用 `admin-api.js` 的 **`renderPagination`**，第四参须为全局回调名字符串 **`window.systemLogsGoPage_system`**（system Tab）或 **`window.systemLogsGoPage_error`**（error Tab），**禁止**传入匿名函数（`renderPagination` 将回调拼入 `onclick`，匿名函数经 `toString` 会丢失闭包，导致翻页无效）。
- **安全**：列表中 `row.message` 经 **`escapeHtml`** 再写入 `innerHTML`；错误详情弹窗用 **`textContent`** 写入正文，防 XSS；`ERROR` 行「详情」按钮传参使用 `JSON.stringify` + `</` → `\u003c/` 及属性内 `&quot;` 转义，避免引号截断属性。

### `admin/pages/third-party.html`（第三方服务监控）

- **权限**：`super_admin` / `tech_ops`；其余角色跳转 `error.html?type=403`。
- **调用**：`GET /api/admin/third-party/status`（**60 秒缓存**，后端 Redis key `cache:third_party_status`，已处理）；定时 **60s** 刷新；`beforeunload` 时 `clearInterval` 防泄漏。
- **卡片**：`#service-grid` 为 2×2 栅格；首屏 4 个 `.skeleton`（高 200px）；成功后渲染服务卡。**标题**使用接口返回的 `name`（不硬编码展示文案）；`svcKey` 由前端 `SERVICE_KEY_MAP` 与后端 `_VALID_SERVICES` 路径对齐（`doubao` / `embedding` / `dashvector` / `content_safety`）。
- **内容安全卡**：独立布局，仅 `today_blocked` + 状态灯；代码注释 **TD-003**（与全局 `tech-debt.md` 中 [TD-003] 编号不同指代）：无真实第三方 HTTP 后端，探测为 Redis `banned_keywords`；配置弹窗为说明 +「测试 Redis 连通性」+「关闭」，无保存。
- **配置弹窗（非 content_safety）**：Endpoint（`type=url`）、API Key（留空保留原值）；**保存**初始禁用；**测试连接** 发 `POST .../test-connection`，Body 含表单中**非空**的 `endpoint` / `api_key`（可与已发布配置合并探测）；`connected===true` 后启用保存。**保存**：`PUT .../config`，Body 仅传非空字段；`api_key` 空则不传；须本弹窗内测试通过后才提交（前端校验）；服务端仍会再次测试合并结果。
- **技术债记录**
  - **TD-003（本页注释口径）**：内容安全无独立第三方 API，探测走 Redis；若未来接入真实内容安全服务需后端字段与探测实现。
  - **TD-012**：`third_party:*` 已可落库与热键 `active_config:third_party:*`，**对话/向量/Embedding 等业务运行时仍以环境变量等现有路径为准**，与后台保存易不一致；清偿时见 `docs/tech-debt.md` [TD-012]。

### `admin/pages/dashboard.html`（数据看板）

- **实现状态**：已实现。`activeKey='dashboard'`，顶栏标题「数据看板」。`tech_ops` 仅提示文案无统计卡片；`ai_trainer` 仅展示 LLM 成功率、人格偏离率等 AI 性能卡片。
- **接口**：`GET /api/admin/stats/dashboard` 的 `data` 为**嵌套对象**（见上文「模块：数据统计」）；卡片脚本内 **`flattenDashboard`** 将 `user` / `retention` / `agent` / `ai_performance` 展平为卡片字段（如 `new_users_today`→`new_users`、`persona_deviation_rate`→`persona_risk_rate`）。
- **趋势图**：`GET /api/admin/stats/trend?metric=...&days=7` 的 `data` 为 **`[{ date, value }]`**；脚本 **`trendListToAxes`** 拆出 `dates`/`values` 再喂 ECharts。
- **告警**：人格偏离 / LLM 成功率 / 次日留存 等阈值判断使用 **`typeof === 'number'`**，避免将 `null` 当 0。

### `admin/pages/persona.html`（AI人格管理）

- **实现状态**：已实现。布局左 55% 编辑区、右 45% 版本历史；`activeKey='persona'`，标题「AI人格管理」。`super_admin` / `ai_trainer` 以外角色跳转 `error.html?type=403`。
- **接口对接**：
  - `GET /api/admin/persona/current`：状态栏「当前生效版本 / 暂无生效版本」、`has_draft` 驱动右侧「有未发布的草稿」+「丢弃草稿」（`DELETE /api/admin/persona/draft`，`showConfirm`）或「已发布」。
  - `GET /api/admin/persona/draft`：有草稿则用 `data.config_value` 五字段填充编辑区；无草稿则用 `current.content`；并行加载时编辑区骨架屏，三请求完成后渲染。**数据库**：若 `admin_config` 对 `config_key` 误设 UNIQUE，保存草稿会 500（MySQL 1062），见表结构「admin_config」与迁移脚本 `migrate_admin_config_config_key_nonunique.sql`。
  - **首屏容错（仅前端，非接口变更）**：若 `GET .../current` 失败（网络/非 0 等）而 `GET .../draft` 成功且 `data` 非空，使用内存占位对象仅设置 `has_draft: true`，使右侧仍显示「有未发布的草稿」与「丢弃草稿」；左侧内容仍以 `draft.config_value` 为准；生效版本文案仍以 `current` 成功后的响应为准。
  - **对称边界**：若 `current` 成功且 `data.has_draft===true`，但 `GET .../draft` 未成功取到草稿体，编辑区会回退为 `current.content`（生效版本），并 Toast 警告「草稿未能加载…请刷新」，避免与状态栏「有草稿」静默不一致。
  - **测试与发布**：每次点击「测试效果」时先将 `testPassed` 置 `false`；请求失败或非 0 时保持 `false`，避免上次「测试通过」在 422/网络错误后仍可点「发布生效」。
  - `PUT /api/admin/persona/draft`：「保存草稿」；成功后 `savedSnapshot` 对齐、Toast、调用 `GET .../current` 刷新状态栏（`adminRequest` 使用 `silentErrorToast: true` 避免与后续文案重复）；若刷新失败则再 `showToast(..., 'warning')` 提示手动刷新页面。
  - `POST /api/admin/persona/test`：「测试效果」弹窗内 loading → 渲染 `details` 列表（输入、回复、得分进度条、`passed` 对应通过/失败 Tag）、底部 `passed/total` 总结；`can_publish===true` 时 `.alert-success` 与 **`testPassed=true`**；否则 `.alert-error` 且 **`testPassed=false`**。
  - `POST /api/admin/persona/publish`：`testPassed=false` 时「发布生效」禁用；`showConfirmInput` 后 Body 含 `content`、`test_passed:true`、`confirm_text:'CONFIRM'`。
  - `GET /api/admin/persona/history` + `renderPagination`（`page_size=10`）：时间线列表「查看 / 回滚」。
  - `GET /api/admin/persona/history/{version}`：「查看」只读弹窗完整五段（历史列表仅 `summary` 截断，不足以展示全文）。
  - `POST /api/admin/persona/rollback`：`showConfirmInput` + `confirm_text:'CONFIRM'`。
- **testPassed 联动**：初始 `false`，发布钮禁用。仅当最近一次「测试效果」请求成功且响应 `can_publish===true` 时置 `true`。各 textarea `input` 时置 `false`（内容变更须重测）。关闭测试弹窗仅重置 loading/结果区 DOM，**不**重置 `testPassed`。
- **未保存提示**：`savedSnapshot` 为 JSON 序列化的五字段（与加载源：草稿优先于生效内容一致）；`oninput` 与快照比较，差异则显示 `.alert.alert-warning`「有未保存的修改」。

### `admin/pages/prompt.html`（Prompt 管理 · Step5 / Step5.5）

- **实现状态**：已实现（STEP-026）。`activeKey='prompt'`，标题「Prompt管理」。**仅** `super_admin` / `ai_trainer`；其余角色跳转 `error.html?type=403`。**侧边栏**可链至 **`step5-5-switch.html`**（Step5.5 总开关）。
- **主 Tab**：**Step5 System**（整段 `textarea`，对应 `GET|PUT /api/admin/prompt/step5/draft`，配置键 **`step5_system_prompt`**）| **Step5.5 片段**（六个子 Tab：`system`、`style_rules`、`ctx_readonly`、`relation_brief`、`history_brief`、`messages_input`，对应 `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`）。
- **首屏加载**：`GET /api/admin/prompt/step5`、`GET /api/admin/prompt/step5-5/fragments`；草稿优先：`GET .../step5/draft`、`GET .../step5-5/draft` 与生效内容合并后填入编辑区。
- **保存草稿**：Step5 — `PUT /api/admin/prompt/step5/draft`；Step5.5 — `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`（仅当前子 Tab）。
- **丢弃草稿**：`DELETE /api/admin/prompt/step5/draft`、`DELETE /api/admin/prompt/step5-5/draft`。
- **在线测试**：Modal；`POST /api/admin/prompt/test`，Body 含 `use_draft`（为 `true` 时使用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致；成功展示 `ai_reply`（messages 合并）、人格匹配条、内容安全、`full_prompt` 折叠区。
- **testPassed**：每次「开始测试」前置 `false`；**成功**且 `ai_reply` 去空白非空 → `true`，用于解锁 **发布 Step5** 与 **发布 Step5.5**；编辑任意 textarea / 切换草稿语义变更时应重新测试。
- **发布**：`POST /api/admin/prompt/step5/publish` / `POST /api/admin/prompt/step5-5/publish`，Body `confirm_text:'CONFIRM'`、`test_passed:true`（须先在线测试通过）。
- **版本历史**：两块独立列表 — **`GET /api/admin/prompt/step5/history`** 与 **`GET /api/admin/prompt/step5-5/history`**；查看 `GET .../history/{version}`；回滚 `POST .../rollback` + `CONFIRM`。

### `admin/pages/step5-5-switch.html`（Step5.5 总开关）

- **实现状态**：已实现（STEP-026）。`activeKey='step55switch'`。**仅** `super_admin` / `ai_trainer`。
- **接口**：`GET /api/admin/prompt/step5-5-switch`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ enabled }`；`DELETE .../draft`；`POST .../publish`（**不要求**先跑主链 LLM 测试，仅需确认 **`CONFIRM`**）；`GET .../history`、`POST .../rollback`。配置键 **`step5_5_enabled`**（与 STEP-009 运行时读取一致）。

### `admin/pages/test-tool.html`（AI测试工具）

- **实现状态**：已实现。主布局 **grid 40% : 60%**（`gap:16px`）；左侧自上而下：`测试参数配置` 卡片、`最近测试记录` 卡片（`margin-top:16px`）；右侧 `测试结果` 卡片。`activeKey='test'`，顶栏标题「AI测试工具」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。样式入口：`admin-common.css` + 页内 `<style>`。
- **测试参数**：`使用配置` 单选——当前生效（`use_draft:false`）/ 草稿（`use_draft:true`）；关系等级、用户情绪；模拟记忆 `textarea`（按换行计非空行数，展示「已输入 n/5 条」，n>5 时 `.alert-warning`）；测试输入必填。
- **开始测试**：校验测试输入非空；`POST /api/admin/prompt/test`，Body 与 `PromptTestRequest` 一致（`mock_memories` 取前 5 条非空行）。服务端拼装与线上一致：**`PromptBuilder.build_chat_prompt`**（STEP-026）；`use_draft:true` 时使用 **`step5_system_prompt`** 草稿作为模块1。成功：右侧淡入展示 AI 气泡（头像「梦」）、人格匹配总分+等级 Tag、三维进度条（40%/40%/20%）、内容安全区块、`full_prompt` 折叠区（Token 数 `Math.ceil(full_prompt.length * 1.5)`）；底部「保存为测试用例」可用。
- **测试历史**：`localStorage` key=`admin_test_history`，最多 10 条，项含 `time`（ISO）、`test_input`、`use_draft`、`relationship_level`、`emotion_label`、`mock_memories`。点击行回填左侧表单；「清空」经 `showConfirm` 后清除并重绘。
- **保存测试用例**：Modal（宽约 480px）填写 `expected_pass_criteria`；`POST /api/admin/test-cases/persona`，Body 使用最近一次**成功**测试快照中的 `test_input`→`input`、`emotion_label`、`relationship_level` 及弹窗中的期望标准。成功 Toast「已保存为测试用例」并关闭 Modal。

### `admin/pages/safety-rules.html`（内容安全规则）

- **实现状态**：已实现。`activeKey='safety'`，顶栏标题「内容安全规则」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。
- **首屏**：`GET /api/admin/safety-rules`，将 `banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords` 写入**三个可变的同一数组引用**（加载时原地 `replaceInPlace`，避免 Enter 添加与刷新后闭包指向旧数组）。
- **Tab**：`initTabs('safety-tabs')` — 违规关键词 | 人格禁区关键词 | 语言风格禁忌词。
- **标签云**：`min-height:120px` + `border:1px solid var(--border)` 容器；词条为 `span.safety-kw-tag`，`×` 仅从本地数组 `splice` 并重新渲染，**不立即请求**。
- **输入**：各 Tab `input` 宽 240px，`Enter` → `trim` 后非空且不重复则 `push` 并清空输入框。
- **保存**：对应 **PUT** `/api/admin/safety-rules/banned-keywords`、`.../persona-keywords`、`.../style-keywords`，Body `{ keywords }`；若当前数组为空则前端 Toast 提示（与后端 **`keywords` 至少 1 项** 一致），成功 Toast「保存成功」。
- **违禁词 Tab**：「批量导入 Excel」触发隐藏 `file`，`accept=".xlsx,.xls"`；`FormData` 字段名 **`file`** + `adminRequest('POST','/api/admin/safety-rules/banned-keywords/import', formData, true)`；成功 Toast「成功导入{imported_count}个关键词，当前共{total_count}个」并 **GET 刷新**。
- **首屏竞态**：首次 `GET /api/admin/safety-rules` 请求期间禁用三个输入框、三个「保存更新」与「批量导入 Excel」；待响应返回且（若成功）已 `replaceInPlace` + `renderAllClouds` 后再解除 `is-loading` 并启用控件（失败时仍启用，避免永久锁死）。
- **导入与未保存**：维护 `lastSyncedSnapshot`（成功 GET 或任意一次保存成功后对三数组的 `JSON.stringify`）；`isDirty()` 为真时点「批量导入 Excel」先 `showConfirm`（文案：将重新加载全部关键词，未保存的修改会丢失…），确认后再打开文件选择；取消则不发起导入。

### `admin/pages/memory-rules.html`（记忆规则配置）

- **实现状态**：已实现。`activeKey='memory'`，顶栏标题「记忆规则配置」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。
- **布局**：顶部 **Tab 标签行**单独一块 `.page-card`（`memory-tab-header-card`），**每个 Tab 内容区**各包一层 `.page-card` 作为表单容器；外层 `#memory-page-wrap` 仅承担 `is-loading`，不再使用单一大卡片包全页。
- **Tab**：`initTabs('memory-tabs')` — 记忆规则 | 向量数据库配置。
- **记忆规则 Tab**：`GET /api/admin/memory-rules` 填充表单；`data===null` 时用契约约定默认值；若已发布 JSON 中检索/合并阈值**超出**服务端区间，加载时 **clamp** 至检索 [0.5, 0.85]、合并 [0.85, 0.98] 并 `showToast(..., 'warning')` 一次；Prompt `textarea` `font-size:13px`；存储阈值、向量 TopK 输入宽 **100px**（`.memory-input-w100`）；检索阈值说明行 `font-size:12px`；重要性四行固定类型与展示文案，表格 `.admin-table`，分值 `number` 1–4；检索/合并阈值为 `range`（0.5–0.85 / 0.85–0.98，step 0.01），`oninput` 更新数值展示并调用 **`validateThresholds()`**（内部同步冲突 `.alert-error` 显隐，且 `merge>search` 时返回 true）；保存前再次 `validateThresholds()`，不满足则 `showToast` 并拦截；`PUT` 成功 Toast 文案为 **「记忆规则配置已保存」**；Body 与 `MemoryRulesRequest` 一致（`importance_rules` 按固定顺序提交四类）。
- **向量库 Tab**：`GET /api/admin/vector-db-config`；Endpoint（`type=url`）、Collection、TopK（**测连/保存须为 1–20**；`GET` 返回的 `top_k` **原样填入**（≥1），若历史上 &gt;20 则展示真实值，须改回 1–20 后再测连/保存，**不再**将非法值静默改为 5）、脱敏 Key 只读 +「修改」展开明文 `password` 输入；**点击「修改」**清空明文框并 `testPassed=false`、清空测连结果区；明文框 `input` 同样重置测试通过与结果；测试结果区 `#vector-test-result` **无内容时 `display:none`**，有结果时 `display:block`；**「测试连接」**发起请求前先展示 `.alert-info`「正在测试连接…」；`POST .../test-connection` Body 对应 `VectorDbTestRequest`：**`endpoint`、`collection_name`、`api_key` 三字段均可不传或传 `null`**，未提供的项由后端从**已发布配置**或**环境变量**补全（与 `memory_mgmt.py` 一致）；本页实现为：`endpoint`/`collection_name` 常带表单当前值（空则 `null`），**仅当明文 Key 框有非空值时带 `api_key`**；成功 `.alert-success` 与延迟 ms；失败 `.alert-error`，文案优先 `data.error`，否则回退 **`ApiResponse.message`**（仍用 `textContent` 写入节点）；`code≠0` 时在结果区展示 **`message`**（该请求使用 `adminRequest(..., { silentErrorToast: true })`，避免与统一信封错误 Toast 重复）；`res` 为空（网络异常、HTTP 非 JSON 等）时 `adminRequest` 仍可能保留全局 Toast，结果区展示「请求失败」摘要。通过后启用「保存」。**「保存」**初始 `disabled`+`title="请先测试连接"`；`PUT /api/admin/vector-db-config`，Body 含 `need_test_first:false`，`api_key` 仅在有新明文时传递；成功后 `testPassed=false`、禁用保存、收起明文编辑、`GET` 刷新脱敏 Key。
- **首屏加载**：`#memory-page-wrap.is-loading` 期间 `.memory-disable-while-load` 使用 `pointer-events:none` 避免未返回数据时误操作。**不**使用 `firstLoadFinished` 变量（该变量在 `safety-rules.html` 中仍用于首屏禁用控件，与本页实现无关）。

### `admin/pages/agent-rules.html`（Agent配置）

- **实现状态**：已实现。`activeKey='agent'`，顶栏标题「Agent配置」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。
- **内存状态（切 Tab 不丢未保存编辑）**：`gTriggersData`、`gDecisionData`、`gMessageRulesData`、`p3Keywords` 四份独立对象；**PUT Body 以当前两 Tab 表单为准**（见下），成功后内存与已提交内容对齐。
- **首屏并行加载**（`DOMContentLoaded`，`adminRequest` + `silentErrorToast` 以便合并失败提示）：`GET /api/admin/agent-rules`、`GET /api/admin/agent-message-rules`、`GET /api/admin/agent-night-keywords`；`#agent-page-wrap.is-loading` 期间 `.agent-disable-while-load` 禁用操作。`data===null` 或缺字段时用与 `agent_service.py` 默认值一致的表单基线（如 P1 沉默天数 3、最少对话 10 轮等）。
- **Tab**：`initTabs('main-tabs')` — 触发条件（`#tab-triggers`）| 决策引擎 & 消息规则（`#tab-decision`）。
- **PUT `/api/admin/agent-rules`**：Body **必须**同时包含 `triggers` 与 `decision_engine`（与 `AgentRulesRequest` 一致）。「保存触发规则」与「保存决策配置」两次请求中，**`triggers` 均来自 `readTriggersFromForm()`**、**`decision_engine` 均来自 `readDecisionFromForm()`**（另一 Tab 隐藏时 DOM 仍可读），避免只改一侧却在另一侧保存时用旧 `gTriggersData`/`gDecisionData` 覆盖服务端；成功后回写 `gTriggersData`、`gDecisionData` 与 Body 一致。
- **P2**：`habit_days_threshold` 前端限制为 **5～当前 `accumulation_days`**，与 `agent_mgmt.py` 校验一致（`accumulation_days` 7–30）。
- **P3 凌晨关键词**：独立接口 **`GET`/`PUT /api/admin/agent-night-keywords`**，Body / 响应 `data.keywords` 为 `string[]`；`NightKeywordsRequest` 要求至少 1 个关键词。**「保存触发规则」**：始终 `PUT agent-rules`；仅当 `p3Keywords.length >= 1` 时并行 `PUT agent-night-keywords`；若关键词为空，仍提示触发规则保存成功，并 **Toast 警告** 未调用关键词保存（避免与服务端 `min_length=1` 冲突）。标签删除用 `indexOf`+`splice` 后 `renderP3Tags()`。
- **agent-message-rules**：**`GET /api/admin/agent-message-rules`** 成功时 `data` 为以 `P0`…`P4` 为 key 的对象，元素含 `generation_requirements`、`examples`、`max_length`。消息规则子卡片：`examples` 至少 3 条输入框，不足补空；删除钮仅当行数 &gt; 3 时显示；最多 5 条示例。**「保存决策配置」**：先 `PUT agent-rules`；再对校验通过的类型 **按 P0→P4 串行** **`PUT /api/admin/agent-message-rules/{type}`**（避免后端整包读-改-写时并行请求互相覆盖），Body `generation_requirements`、`examples`（trim 后非空，3–5 条）、`max_length`（**必填**，20–100）；某类型示例 &lt; 3 或长度非法则 **跳过该类型** 并 Toast，其余仍提交；部分失败 Toast「部分配置保存失败，请检查」。**「保存决策配置」**前同样执行 P2 习惯门槛校验（与「保存触发规则」一致）。
- **运行时说明**：`triggers` / `decision_engine` 持久化后 **当前 `AgentService` 仍未读取**（与后台配置易不一致），见 **`docs/tech-debt.md` [TD-004]**；**P3 关键词**经 Redis `agent:night_keywords` 已接入运行时。

### `admin/pages/relationship-rules.html`（关系成长配置）

- **实现状态**：已实现。`activeKey='relationship'`，顶栏标题「关系成长配置」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。
- **顶部横幅**：始终展示 **TD-005**（配置写入 `admin_config` 与 `relationship_service.py` 硬编码未对齐，见 `docs/tech-debt.md`）。
- **Tab**：`initTabs('main-tabs')` — 等级配置（`#tab-levels`）| 成长值规则（`#tab-growth`）。
- **接口**：`GET` / `PUT` **`/api/admin/relationship-rules`**
  - **PUT Body** 须同时包含 `levels`、`growth_rules`、`confirmed`。
  - `confirmed:false`：仅返回影响预览（`affected_upgrade_users`、`affected_downgrade_users`），不发布。
  - `confirmed:true`：发布配置并执行升级；对「应降级」用户写 Redis 过渡期（7 天），与 `relationship_mgmt.py` 一致。
  - 最高等级（level 3）的 `threshold` 前端提交 **99999**（表单展示为禁用占位「最高等级」）；后端校验要求阈值列严格递增。
- **成长值规则**：表格行 `action_type` 与 `relationship_service.py` 中 **`GROWTH_ACTIONS`** 一致：`dialog` / `long_session` / `daily_login` / `reply_agent`。
- **前端校验（成长值）**：`readGrowthRulesFromForm()` 要求每行「单次积分」「每日上限」均为 **≥1 的整数**（`parseInt` 后校验）；非法时 `showToast(..., 'error')` 并返回 **`null`，不发起 PUT**。「检查影响并保存」「影响预览 · 确认保存」「保存成长规则」三处在组 Body 前均判断 `growth` 非空。
- **默认值**：`GET` 的 `data` 为 `null` 或缺字段时，前端用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` 等价默认填充（与 `relationship_service.py` 硬编码一致）。
- **交互**：「检查影响并保存」先 `PUT` `confirmed:false` 弹出「影响预览」Modal，再「确认保存」`confirmed:true`；「保存成长规则」直接 `PUT` `confirmed:true`（与等级表单当前值一并提交）。

### `admin/pages/diary-rules.html`（日记规则配置）

- **实现状态**：已实现。`activeKey='diary'`，顶栏标题「日记规则配置」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。
- **顶部横幅**：**「已接入生成与调度；改生成时刻后须重启 backend。」**（定案见 `docs/diary-refactor-decisions.md` §6）。运维见 **`docs/ops-diary.md`**；与定时任务同源的手动批跑为 **`PYTHONPATH=. python -m scripts.run_diary_batch`**（容器内见 **`docs/ops-diary.md`** §3）。
- **接口**：`GET` / `PUT` **`/api/admin/diary-rules`**。
  - **Body**：`DiaryRulesRequest` — 两个独立 **`textarea`**（`#gen-prompt-with` / `#gen-prompt-without`）对应 **`prompt_with_interaction`** / **`prompt_without_interaction`**；`max_length`（滑块 50–300，`step=10`）；`frequency` 固定 `"daily"`；**北京时间（`Asia/Shanghai`）** 时刻：`#gen-hour`（**0–23**，脚本填充选项）+ `#gen-minute`（0–59，默认 **15**）。
  - **占位符**：含 **`{{covers_date_label_zh}}`**（服务端注入，如 `5月15日`）；其余与契约 **`DiaryRulesRequest`** 说明一致。
  - **加载**：若库内仅有旧字段 **`generation_prompt`**，两套文本域均回填该值；若仅有单侧新字段则与 `generation_prompt` 策略一致（以服务端正则解析为准）。
- **保存成功**：`showToast` 提示保存成功并强调 **修改生成时刻须重启 backend** 后 Cron 才更新（与 **TD-013** 一致）。
- **字数滑块与回填**：若 `GET` 的 `max_length` 非 10 步进，**`snapMaxLengthToSliderStep`** + `warning` Toast（与契约前文一致）。
- **日记历史链接**：**仅** `super_admin` / `ops_admin` 展示（`ai_trainer` 不展示）；指向 **`diary-history.html`**。

### `admin/pages/diary-history.html`（AI 日记历史）

- **权限**：**仅** `super_admin` / `ops_admin`；其余角色跳转 `error.html?type=403`（与 **`GET /api/admin/diary-history`** 鉴权一致，`ai_trainer` 直链亦为 403）。
- **菜单**：`MENU_CONFIG` 中 **`super_admin`**、**`ops_admin`** 含 **`key: 'diary-history'`** → `diary-history.html`；**不包含** `ai_trainer`（决策 O1）。
- **接口**：`GET /api/admin/diary-history`，Query 与后端一致；列表 **`content`** 经 **`escapeHtml`** 写入表格单元格，`title` 存放完整正文（已转义）便于悬停查看；表格列：**日记 `id`**、**账号**（`username`）、**账号ID**（`user_id`）、正文、生成时等级、已读、**覆盖日(北京)**（`covers_beijing_date`，可为空）、**创建时间**（`created_at`）。
- **交互**：用户 ID（筛选框仍为数字 ID）、开始/结束日期筛选；**查询**拉取第 1 页；**`renderPagination`** 分页；空列表展示「暂无数据」。

### `admin/pages/data-report.html`（数据报表）

- **实现状态**：已实现。`activeKey='report'`，顶栏标题「数据报表」。仅 **`super_admin` / `ops_admin`** 可访问，**`ai_trainer` / `tech_ops`** 跳转 `error.html?type=403`。
- **聚合卡片**：`GET /api/admin/stats/dashboard`，按 **嵌套字段** 读取（`retention` / `conversation` / `ai_performance` 等）；字段为 `null` 时统一展示「—」；标注「(今日)」的指标与后端「当日」统计一致。
- **总注册用户数**：`GET /api/admin/users?page=1&page_size=1` 的 `data.total`（与日期筛选无关，首屏一次）。
- **报表明细与图表**：`GET /api/admin/stats/report?report_type=...&start_date=...&end_date=...&page=1&page_size=100`；Tab 切换后延迟 `onQuery` 刷新当前类型数据；**用户** Tab 期间新增/对话期间总量等由 `list[]` 前端求和。
- **功能使用 Tab**：后端 `feature` 行字段仅 `date` / `agent_sent` / `agent_opened` / `reply_rate`；缺按日 `open_rate` / `agent_replied` 见 **TD-009**。
- **AI 性能 Tab**：折线图为 **人格偏离率按日**（`list[].deviation_rate`），非 LLM 响应时长；见 **TD-008**。
- **导出 Excel**：`adminRequest('POST', url)` **不传 `data` 参数**，URL 含 `report_type`、`start_date`、`end_date` Query，由 `admin-api.js` 识别 `spreadsheetml` 触发 blob 下载。
- **图表**：ECharts；`chartInstances` + `getChart`；`window.resize` 时 `resize()`。
- **Tab 切换与「查询」**：`initTabs` 切换后 **`setTimeout(0, onQuery)`**，且 **`onQuery()` 返回的 Promise 完成后再 `setTimeout(50ms, resizeAllCharts)`**，避免请求未完成时提前 `resize` 导致图表尺寸异常；「查询」按钮同样 **`onQuery().then` → 延迟 `resize`**。首屏加载同逻辑。
- **用户报表饼图**：`extra.level_distribution` 为全量用户等级分布，**与日期筛选无关**；页面饼图标题下灰色说明与接口语义一致。

### 技术债记录（关系 / 日记管理页）

| 编号 | 说明 |
| --- | --- |
| **TD-005** | `relationship_rules` 已写入 `admin_config`，`relationship_service.py` 仍用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` / 固定阈值判定，需改服务后后台配置才对用户端生效。 |
| **TD-006** | ~~`diary-history.html` 未建~~ → 已提供页面与 **super_admin / ops_admin** 菜单；`diary-rules` 内历史链接已可用。 |
| **TD-007** | ~~生成与调度未读配置~~ → 已读 `diary_rules`（`diary_rules_loader` + `DiaryService` + 启动时 Cron **`Asia/Shanghai`**）；兼容旧 `generation_prompt`。 |
| **TD-008** | LLM 响应耗时无法按日拆分；数据报表 AI 性能折线用人格偏离率；仪表盘 `llm_avg_response_ms` 无样本为 `null`。 |
| **TD-009** | `report_type=feature` 缺按日 `open_rate` / `agent_replied`，表格暂 4 列。 |
| **TD-010** | `GET /system/status` 的 `alerts[]` 无单条发生时间，监控页用刷新时刻代替；补充字段时的修改范围与库内消费方见 `tech-debt.md`。 |
| **TD-011** | `get_system_status` 在 Redis INFO 异常时 `hits`/`misses` 可能未定义，存在 `NameError` 风险；见 `tech-debt.md`。 |

---

## 开发日志

### STEP-001：relationship 表 DDL 迁移
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：为 relationship 表新增 9 个扩展字段，支撑 Step6 记忆写回与 Step8 Future 槽机制
- 涉及文件：
  - `backend/models/relationship.py`（修改）
  - `alembic/versions/v4a_step001_relationship_extend.py`（新增）
- 字段变更：
  - 新增字段：relation_description - TEXT - 关系描述
  - 新增字段：user_real_name - VARCHAR(50) - 用户真实称呼
  - 新增字段：user_hobby_name - VARCHAR(50) - 用户昵称
  - 新增字段：user_description - TEXT - 用户印象
  - 新增字段：character_purpose - TEXT - 角色当前回应策略
  - 新增字段：character_attitude - TEXT - 角色当前态度
  - 新增字段：future_timestamp - INTEGER - Future 预约时间戳
  - 新增字段：future_action - VARCHAR(200) - Future 预约意图摘要
  - 新增字段：proactive_times - INTEGER(default=0) - 主动消息计数
- 测试结果：✅ Lint 通过，ORM 与迁移脚本字段一致
- 备注：无

### STEP-002：relationship 变更历史表
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：创建 append-only 历史表 `relationship_change_history`，记录 Step6 对 relationship 扩展字段的每次更新；`RelationshipHistoryService.append_history()` 仅做 INSERT，支持排障与回溯
- 涉及文件：
  - `backend/models/relationship_change_history.py`（新增）
  - `backend/models/__init__.py`（修改：注册 RelationshipChangeHistory）
  - `alembic/versions/v4b_step002_relationship_change_history.py`（新增）
  - `backend/services/relationship_history_service.py`（新增）
  - `tests/test_relationship_change_history.py`（新增）
- 字段变更：
  - 新增表：relationship_change_history（9 个字段，详见数据库表结构章节）
- 测试结果：✅ 全部通过（7 个用例：单条写入字段完整性、连续写入排序、old_value 为 NULL、round_id 为 NULL、按 user_id 查询、空历史）
- 备注：主键使用 `BigInteger().with_variant(Integer, "sqlite")` 兼容 SQLite 测试环境的 autoincrement 限制

### STEP-003：DashVector type 常量 + search/upsert 签名扩展
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `constants.py` 定义 4 类 DashVector 向量类型常量（R-L1L3-08），扩展 `dashvector_client` 的 `upsert()` / `search()` 签名支持 `memory_type` 参数（R-L1L3-15），按规则拼接 filter 实现分类型检索与写入（R-VEC-01）
- 涉及文件：
  - `backend/constants.py`（修改：新增 `MEMORY_TYPE_CHARACTER_GLOBAL` / `MEMORY_TYPE_CHARACTER_PRIVATE` / `MEMORY_TYPE_CHARACTER_KNOWLEDGE` / `MEMORY_TYPE_USER` 常量及 `VALID_MEMORY_TYPES` 校验集合）
  - `backend/utils/dashvector_client.py`（修改：`upsert()` 新增 `memory_type` 参数并自动注入 `type` 字段；`search()` 新增 `memory_type` 参数、`user_id` 改为可选、按规则拼接 filter）
  - `backend/services/vector_service.py`（修改：`upsert()` / `search()` 透传 `memory_type` 参数）
  - `backend/services/memory_service.py`（修改：5 处调用适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/routers/chat.py`（修改：`_search_memories` 适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/services/agent_service.py`（修改：`_search_memories_for_agent` 适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/routers/admin/users.py`（修改：编辑记忆 upsert 适配 `memory_type=MEMORY_TYPE_USER`）
- 字段变更：
  - 新增常量：`MEMORY_TYPE_CHARACTER_GLOBAL` = `"character_global"` - 角色公开设定
  - 新增常量：`MEMORY_TYPE_CHARACTER_PRIVATE` = `"character_private"` - 角色私有设定
  - 新增常量：`MEMORY_TYPE_CHARACTER_KNOWLEDGE` = `"character_knowledge"` - 角色知识技能
  - 新增常量：`MEMORY_TYPE_USER` = `"user"` - 用户画像
  - `dashvector_client.search()` 签名：新增 `memory_type: str`，`user_id: int` → `user_id: int | None = None`
  - `dashvector_client.upsert()` 签名：新增 `memory_type: str`，自动向 fields 注入 `"type"` 字段
  - filter 拼接规则：无 user_id → `type = '{memory_type}'`；有 user_id → `type = '{memory_type}' AND user_id = {uid}`
- 测试结果：✅ Lint 通过，所有现有调用已适配新签名
- 备注：无（本环节不新建 collection、不做旧数据迁移；Step2 多路检索已在 STEP-020 实现）

### STEP-004：Step5 Prompt 提示词改造
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：按 `Step5-prompt提示词改造.md` 对 `prompt_builder.py` 进行最小化改写，输出新 6 字段 JSON Schema（inner_monologue / messages / relation_change / future / emotion / knowledge_expand），新增【知识性话题回应原则】与【当前时间】模块，关系状态追加 4 行扩展字段，同步更新 hint 与主动消息 Schema
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：`SYSTEM_PROMPT_TEXT` 完全替换为新 Schema + 示例 + 知识性话题原则；`_build_relationship_prompt()` 尾部追加 4 行扩展字段；新增 `_generate_time_description()` 和 `_build_time_prompt()`；`build_chat_prompt()` 插入时间模块；`_build_user_input()` hint 替换；`_build_active_task_instruction()` 输出指令同步；Token 预算调整）
  - `backend/routers/admin/prompt_mgmt.py`（修改：`_MODULE_TOKEN_LIMITS` 与 `_TOTAL_TOKEN_LIMIT` 同步调整）
  - `tests/test_prompt_builder.py`（新增：10 个测试用例覆盖 Schema 验证、扩展字段注入/空值、模块顺序、时间描述）
  - `docs/contract.md`（修改：更新时间、Token 限制引用、开发日志）
- 字段变更：
  - `MODULE_TOKEN_LIMITS["system"]`：400 → 1200（含完整 Schema + few-shot 示例，实测 1152 Token）
  - `MODULE_TOKEN_LIMITS["relationship"]`：200 → 250（追加 4 行扩展字段）
  - `MAX_TOTAL_TOKENS`：4096 → 5200
  - `prompt_mgmt.py` `_MODULE_TOKEN_LIMITS` / `_TOTAL_TOKEN_LIMIT` 同步更新
  - `SYSTEM_PROMPT_TEXT`：新增【回复格式规则】messages 数组 + type 约束、【知识性话题回应原则】、完整 6 字段 JSON Schema + 字段说明 + 输出示例
  - `_build_relationship_prompt()` 输出：追加 `关系描述` / `对TA的印象` / `亲密称呼` / `用户真名` 四行（读取 STEP-001 新增的 relationship 扩展列）
  - 新增模块★【当前时间】：`_generate_time_description()` 生成 `现在是{周几}{时段}{时}点{分}分`
- 测试结果：✅ 全部 10 个用例通过
- 备注：无（不改【身份禁区】【核心陪伴原则】【人格设定】【用户记忆】【情绪状态】【最近对话】的原有内容；不实现 Step5.5；不实现 Step1-3 角色记忆/知识检索）

### STEP-005：Step5 输出 JSON 解析器 + 校验规则
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：替换现有 `{emotion, reply}` 解析器，支持新 6 字段扁平 JSON 解析 + 严格校验（§2.7.7 / CP3 / U1 / U2 / R-BND-02）
- 涉及文件：
  - `backend/services/llm_service.py`（修改：新增 `Step5ParseError` 异常类、`MessageItem` / `RelationChange` / `FutureSlot` / `EmotionResult` / `Step5Output` Pydantic 模型、`parse_step5_output()` 解析函数、`LLMService.chat_with_step5_parse()` 方法；保留旧 `chat_with_parse_strict` 供 Agent 主动消息等旧链路兼容）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 内 `chat_with_parse_strict` → `chat_with_step5_parse`，不再读取 `result["reply"]`，改为拼接 `step5_result.messages[].content`；SSE Future payload 新增 `step5` 字段携带完整结构化数据）
  - `tests/test_step5_parser.py`（新增：25 个单元测试覆盖合法解析、CP3 大小写敏感、U2 空消息、U1 knowledge_expand trim、默认值填充、边界非 JSON）
- 字段变更：
  - 新增 Pydantic 模型 `Step5Output`：`inner_monologue(str)` / `messages(List[MessageItem])` / `relation_change(RelationChange)` / `future(FutureSlot)` / `emotion(EmotionResult)` / `knowledge_expand(str)`
  - SSE `_resolve_generation_future` payload 新增 `step5: dict`（`model_dump()` 序列化）
  - `ai_reply` 生成逻辑：`"\n".join(m.content for m in step5_result.messages)`
- 校验规则：
  - JSON 解析失败 → `Step5ParseError`
  - `messages` 为空数组或全部 content trim 为空 → `Step5ParseError`（U2）
  - 任一 `messages[].type` 非精确 `"text"` → `Step5ParseError`（CP3，大小写敏感）
  - `knowledge_expand` trim 后仅精确「是」为是，其余按「否」（U1），不判失败
  - `relation_change.delta` 缺失 → 默认 0（R-BND-02）
  - `future` 缺失 → 默认 `time_natural="无", action="无"`
- 测试结果：✅ 全部 25 个用例通过
- 备注：STEP-006 已实现 messages >5 合并；STEP-007 已实现 `future.time_natural` 解析（见 STEP-007）；Step5.5 触发与润色见 **STEP-009**。

### STEP-006：messages >5 条合并规则（§2.9.1）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：实现 §2.9.1 定义的消息合并规则——当 messages 超过 5 条时，将第 6 条及以后的 content 按顺序用半角空格拼入第 5 条（下标 4）末尾；合并后若超过可配置的单条长度上限则尾部截断并打日志
- 涉及文件：
  - `backend/constants.py`（修改：新增 `MAX_MESSAGES_COUNT=5` 消息最大条数上限、`MAX_SINGLE_MESSAGE_LENGTH=2000` 合并后单条 content 最大字符数）
  - `backend/services/llm_service.py`（修改：新增 `merge_messages_if_exceed(messages, max_count=5, max_length=2000)` 纯函数；新增 import `MAX_MESSAGES_COUNT` / `MAX_SINGLE_MESSAGE_LENGTH`）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 内 Step5 成功后先算 `step6_messages`（Step5 原始 messages 合并），再条件调用 Step5.5（STEP-009）；`final_messages` 为 5.5 成功时的润色结果否则为 Step5 合并结果；`ai_reply` 与 SSE payload 中 `step5.messages` 使用 `final_messages`）
  - `tests/test_merge_messages.py`（新增：16 个单元测试覆盖不合并、6 条合并、8 条合并、截断+日志、自定义参数、空格拼接等场景）
- 消费点接入：
  - 消费点 1（Step5 路径 / 5.5 回退）：`final_messages = merge_messages_if_exceed(step5_result.messages)` — 未触发 Step5.5 或 5.5 失败/未命中门闩时使用；`ai_reply`、`step5.messages` 均基于此
  - 消费点 2（Step5.5 输出后）：`execute_step5_5` 返回非空时 `final_messages = step5_5_result`（函数内已对 5.5 解析结果执行 `merge_messages_if_exceed`），见 **STEP-009**
  - 消费点 3（Step6 入参快照 CP1）：`step6_messages = merge_messages_if_exceed(step5_result.messages)`，**仅** Step5 原始产出，供后续 Step6 入队，见 **STEP-016**
- 函数签名：`merge_messages_if_exceed(messages: list[MessageItem], max_count: int = 5, max_length: int = 2000) -> list[MessageItem]`
- 合并规则：
  - `len(messages) <= max_count` → 原样返回（浅拷贝）
  - `len(messages) > max_count` → 保留前 max_count-1 条不变，第 max_count 条 content 与后续所有条 content 用半角空格拼接
  - 合并后 content 长度 > max_length → 尾部截断至 max_length + WARNING 日志
  - 纯函数，不修改入参
- 测试结果：✅ 全部 16 个用例通过
- 备注：消费点 3（Step6 入队接线）已由 **STEP-016** 完成；不修改 LLM Prompt 中对条数的描述；SSE 多气泡分包推送逻辑已在 **STEP-010** 实现

### STEP-007：future.time_natural 时间解析器（§2.8.4）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：纯 Python 正则解析 LLM 输出的 `future.time_natural`，基准时区 UTC；合法格式返回 Unix 秒级时间戳，「无」返回 `None`（无预约）；非法格式返回 `None` 并 `logger.warning` 结构化日志（`raw_input` / `reason` / `action=slot_cleared`）。另提供 `is_future_slot_valid(ts)`：`now - ts <= 1800` 为有效（30 分钟过期窗口）
- 涉及文件：
  - `backend/utils/future_time_parser.py`（新增：`parse_future_time`、`is_future_slot_valid`、内部 `_log_parse_failure`）
  - `tests/test_future_time_parser.py`（新增）
- 字段变更：
  - 无（本环节仅新增工具模块与测试，未改数据库与对外 HTTP 契约）
- 测试结果：✅ 全部 22 个用例通过
- 备注：未接入 `chat.py` / `relationship` 写入与 Step8 轮询消费（仍不在本 STEP 范围）；调用方在解析失败时需自行清空 Future 槽并保留 `proactive_times`（与需求 §2.8.4 一致）

### STEP-008：round_id 提前生成 + 超时配置（§2.9.3 / §2.11.2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`round_id` 在 `_execute_llm_bundle` 内于 Step5 解析成功（`chat_with_step5_parse` 正常返回）后立即 `str(uuid.uuid4())` 生成；同一值传入 `_persist_bundle_success` 写入本轮 pack 内全部 user 行、**全部 assistant 行**（STEP-011 起可为 N 行）及 `emotion_log`；成功闭环时 `_resolve_generation_future` 的内存 payload 增加 `round_id`、`step6_messages`（合并后 messages 的 `model_dump` 列表）供后续 Step6 入队读取；`_sse_chat_wait_bundle` 使用 `_BUNDLE_WAIT_TIMEOUT_SEC = 120.0`（**仅** `asyncio.wait_for` 等待本代 Future 的上限，**不**约束 `_execute_llm_bundle` 整段墙钟，见 **POST /api/chat/send** 与 **「部署与网关（对话 SSE）」**）；`LLM_TIMEOUT_CHAT`（默认 45s）未改；仓库内 `nginx/nginx.conf` 的 `proxy_read_timeout` 已为 300s，满足 ≥130s。
- 涉及文件：
  - `backend/routers/chat.py`（修改）
  - `tests/test_chat.py`（修改：新增 `TestStep008RoundId`；`test_chat_send_stream_response` 改为 mock `chat_with_step5_parse`）
  - `docs/contract.md`（修改：顶部摘要、本开发日志条目）
- 字段变更：
  - 新增字段：无（MySQL/SQLite 表无 DDL 变更）
  - 修改字段 / 契约扩展：`Future` 成功 payload 新增 `round_id`（`str`，UUID 文本）、`step6_messages`（`list[dict]`，Step6 入参快照）；私有函数 `_persist_bundle_success` 新增必填参数 `round_id: str`（原在函数内 `uuid.uuid4()` 生成，现改为调用方传入）；模块常量 `_BUNDLE_WAIT_TIMEOUT_SEC`：`55.0` → `120.0`（**SSE** 侧 `wait_for` 等待同代 Future 的上限；**非**后端 `_execute_llm_bundle` 墙钟硬指标）
- API / 接口契约：
  - 接口名称：无新增 HTTP 路由
  - Method + Path：无变更（`POST /api/chat/send`、`POST /api/chat/resend` 等）
  - Request Body：无变更
  - Response：成功 / 失败信封与 SSE 事件类型与 STEP 前一致；`round_id` / `step6_messages` 仅服务端 Future 内存 payload
  - 变更类型：无（对外契约不变）
- 数据模型：
  - 表名 / 集合名：无新增表
  - 变更类型：无（未新增列、未修改列类型）
  - 字段详情：`conversation_log.round_id`、`emotion_log.round_id` 仍为既有列（TD-016 / V2-B）；本 STEP 仅改变 `round_id` 的生成时机与落库/Future 一致性
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 共 28 条，含 `TestStep008RoundId` 3 条）
- 未完成项记录：
  - 无（Step6 异步入队与 `Step6Snapshot` 使用 `round_id` 及合并后 messages 已在 **STEP-016** 完成；STEP-008 仍负责 Future payload 携带 `round_id` / `step6_messages` 供观测）
- 备注：`round_id` 与 `generation_id` 仍为独立 UUID（需求文档「与 generation_id 同源」为建议项）；Step5 解析失败路径不生成 `round_id`、不调用 `_persist_bundle_success`。**STEP-011** 起 `_persist_bundle_success` 的 assistant 落库参数由 `ai_reply: str` 改为 `messages: list`（多行 assistant），`round_id` 传入方式不变。**`_BUNDLE_WAIT_TIMEOUT_SEC`** 仅为 SSE 侧 `wait_for` 上限，**非**整链墙钟硬指标，见契约顶栏「SSE 等待上限语义」与 **POST /api/chat/send**。

### STEP-009：Step5.5 触发判定 + LLM 调用 + 解析（§2.7.1 / §2.7.4 D2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 Step5 解析成功后，读取 `admin_config` 总开关与双门闩 OR 判定；命中则按 `doc/step5_5_prompt.md` 拼装 Prompt、调用豆包非流式接口、解析 JSON 数组、经 `merge_messages_if_exceed` 合并至 ≤5 条后覆盖 `final_messages`；未命中/超时/解析失败则回退 Step5 合并 messages（R-BND-06）。`step6_messages` 始终仅基于 Step5 原始 messages 合并（R-BND-05）。
- 涉及文件：
  - `backend/services/step5_5_service.py`（新增）
  - `backend/routers/chat.py`（修改：接入 `execute_step5_5`、`LEVEL_DEFINITIONS`）
  - `tests/test_step5_5.py`（新增）
  - `docs/contract.md`（修改：本条目、admin_config 说明、H5 对话语义摘要、STEP-006 消费点描述）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：无
  - 新增运行时配置约定：`admin_config.config_key = step5_5_enabled`，`config_value` 可为 JSON 布尔 / 字符串 / 数字等，`get_active_config` 解析后按实现约定判定开/关（true/1/on/yes/enabled 等视为开启）
- API / 接口契约：
  - 接口名称：无新增用户端或管理端 HTTP 接口
  - Method + Path：无变更（仍通过 `POST /api/chat/send`、`POST /api/chat/resend` 触发同一 `_execute_llm_bundle` 链路）
  - Request Body：无变更（`ChatSendRequest` / `ChatResendRequest`）
  - Response：成功仍为 SSE（`meta` / `delta` / `done` / `failed` / `obsolete`）；**不**因 Step5.5 新增帧类型；失败码与既有定义一致
  - 变更类型：**服务端内部行为扩展**（条件追加第二次 LLM HTTP 调用，子超时 30s）
- 数据模型：
  - 表名：`admin_config`（既有表）
  - 变更类型：新增约定 `config_key` 行（由运维/后台发布，非代码迁移自动生成）
  - 字段详情：`config_key = step5_5_enabled`；`config_value` 为开关语义内容；须 `is_active=true` 且 `is_draft=false` 的生效行；Redis 键 `active_config:step5_5_enabled` 与现有热加载机制一致
- 触发判定规则（§2.7.1）：
  - 总开关（B3）：`step5_5_enabled` 关闭 → 不执行 Step5.5
  - 门闩 A：`rand < 0.12`（12%）
  - 门闩 B：仅 `knowledge_expand == "是"` 时 `rand < 0.5`（50%）
  - 命中 A OR B → 执行 Step5.5
- LLM 调用规则：
  - 独立子超时 30s（§2.7.4 D2）：`asyncio.wait_for` + `llm_client.chat_sync(..., timeout_sec=30)`
  - 输出：顶层 JSON **数组**（R-BND-04），元素 `{ "type": "text", "content": "..." }`，解析后经 `merge_messages_if_exceed` 至 ≤5 条
- 回退机制（R-BND-06）：超时、HTTP 异常、非法 JSON、`type`/`content` 校验失败 → `execute_step5_5` 返回 `None`，主链路使用 Step5 的 `merge_messages_if_exceed(step5_result.messages)` 作为 `final_messages`
- 测试结果：✅ 全部通过（`pytest tests/test_step5_5.py` 共 32 条）
- 测试覆盖场景：
  - 场景1：总开关关闭 → 不触发（4 个用例）
  - 场景2：开关开启 + knowledge_expand="否" + 命中门闩 A（3 个用例）
  - 场景3：开关开启 + knowledge_expand="是" + 命中门闩 B（4 个用例）
  - 场景4：LLM 返回非法 JSON → 回退（4 个用例）
  - 场景5：LLM 超时 → 回退（2 个用例）
  - 边界：5.5 返回 7 条 → 合并到 5 条（2 个用例）；解析/Prompt/开关值兼容等（13 个用例）
- 未完成项记录：
  - 无（管理端 Step5.5 总开关与模板编辑已由 **STEP-026** 交付）
- 备注：`should_trigger_step5_5()` 支持 `_rand_a` / `_rand_b` 单测注入；Step5.5 Prompt 正文由 **`admin_config:step5_5_prompt_fragments`** 六段模板热加载（缺省与 `step5_5_prompt_fragments.py` / `doc/step5_5_prompt.md` 对齐），运行时 **`build_step5_5_prompt(..., fragments=...)`** 拼装。Step5.5 走 `llm_client` 直调，**未**写入 `LLMService._record_stats` 的 Redis 统计（与主链路 Step5 调用不同）；若需看板包含 5.5，可在后续 STEP 对齐统计写入。

### STEP-010：SSE 协议扩展（多气泡流式）（§2.9.4 / §2.7.5 / §2.7.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：服务端 `_sse_chat_wait_bundle` 按 CP2 先发 `meta`（含 `message_count`、`generation_id`），再按条发 `delta`（含 `message_index`），末包 `done` 含整轮 `messages` + `emotion`；`step5.messages` 为空时回退 `reply` 单条。H5 `appendAIThinkingBubble` / `consumeChatSse` 不预铺空气泡、按 index 填槽、`done.messages` 定稿。单测：`TestStep010SseMultiBubble`（3 条集成、单条边界、Python 镜像 H5 乱序填槽与 done 覆盖语义）、`test_chat_send_stream_response` 补充断言；集成路径须 mock `execute_step5_5`，避免 `admin_config_service` 走未 mock 的 `redis_client.get_redis`。
- 涉及文件：
  - `backend/routers/chat.py`（修改）
  - `frontend/pages/chat.html`（修改）
  - `tests/test_chat.py`（修改）
  - `docs/contract.md`（修改）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段 / 契约扩展（SSE JSON 行，非 ORM）：
    - `meta.message_count` - `int` - 本轮气泡条数 N（失败/obsolete/超时路径可为 0）
    - `delta.message_index` - `int` - 目标气泡下标 0≤index<N
    - `done.messages` - `array` - `[{"type":"text","content":"..."}, ...]`，客户端真相源
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 全量）
- 备注：未实现 voice/image 多模态 SSE；`resend` 与 `send` 共用协议未单独改。真实网络乱序 E2E 未纳入本 STEP，乱序/以 done 为准由 Python 镜像单测覆盖。
- API / 接口契约：
  - 接口名称：H5 对话流式发送 / 叹号重发
  - Method + Path：`POST /api/chat/send`、`POST /api/chat/resend`（无变更）
  - Request Body：与 `ChatSendRequest` / `ChatResendRequest` 一致（无变更）
  - Response：
    - 成功：`StreamingResponse`（`text/event-stream`），SSE 行 JSON；`meta`：`generation_id`、`message_count`；`delta`：`content`、`message_index`；`done`：`messages`、`emotion`；另含 `failed` / `obsolete` 等既有类型
    - 失败（未进 SSE）：`ApiResponse`，`code` + `message`（如队列满 10104 等，与既有定义一致）
  - 变更类型：**修改**（SSE 帧字段扩展，事件类型名不变）
- 数据模型：
  - 表名 / 集合名：无
  - 变更类型：无
  - 字段详情：无
- H5 端行为变更（契约补充）：
  - `appendAIThinkingBubble()`：`setMessageCount` / `appendTextAt` / `finalize`
  - `consumeChatSse()`：解析 `meta.message_count`、`delta.message_index`、`done.messages`
- 未完成项记录：
  - 无

### STEP-011：conversation_log 多气泡落库（§2.8.1 / §2.8.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：成功闭环时 `_persist_bundle_success` 将 `final_messages`（Step5.5 成功则为其输出，否则 Step5 合并后列表）按条落库：`allocate_sort_seq(user_id, count=len(messages), db=...)` 一次取 N 个连续序号，循环插入 N 行 `ConversationLog(role="assistant", content=messages[i].content, sort_seq=seqs[i], round_id=...)`；pack 内 user 行仍批量标 `delivered` 并写同一 `round_id`；`emotion_log` 仍挂首条 pack user 的 `id`。`messages` 为空时函数直接 `return` 并打 warning（正常路径不应出现）。`GET /api/chat/timeline` 未改代码：合并后按 `sort_seq` 排序，多 assistant 自然按序展示。
- 涉及文件：
  - `backend/routers/chat.py`（修改：`_persist_bundle_success` 签名 `ai_reply`→`messages`，`_execute_llm_bundle` 传 `final_messages`）
  - `tests/test_chat.py`（修改：新增 `TestStep011MultiBubblePersist`；`TestStep008RoundId::test_persist_bundle_success_uses_passed_round_id` 适配新签名）
  - `docs/contract.md`（修改：本条目、表说明、H5 模块语义、timeline 说明、顶部摘要）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：无（`conversation_log` 列集合不变）
  - 行为变更：原「每轮成功闭环写 **1** 行 assistant（`content` 为多气泡 `\n` 拼接）」→ 写 **N** 行 assistant（N = 对外 messages 条数，≤5 由 Step5/合并保证），每行独立 `id` / `sort_seq`，`round_id` 与本轮 user 行一致
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 全量 36 条，含 STEP-011 新增 4 条）
- 备注：管理后台用户对话查看页 **未** 在本 STEP 适配多行 assistant 展示（与需求范围一致）；人格偏离率分母仍为当日 `role=assistant` 的 `conversation_log` **行数**，多气泡一轮会计多条。
- API / 接口契约：
  - 接口名称：无新增路由；H5 timeline / send 响应结构字段名不变
  - Method + Path：`GET /api/chat/timeline`、`POST /api/chat/send`、`POST /api/chat/resend` — **路径与 JSON 信封不变**
  - Request Body：无变更
  - Response：
    - `GET /api/chat/timeline`：`items[]` 中同一用户时间线可出现 **多条** `source=assistant` 且可共享 `round_id`（契约未强制返回 `round_id` 字段，DB 层已写入；若客户端需分组可后续扩展响应）
    - `POST /api/chat/send` / `resend`：SSE 契约同 STEP-010（无变更）
  - 变更类型：**行为/语义补充**（DB 行数与 timeline 列表项数相对 STEP-010 前「单条 assistant」增加）
- 数据模型：
  - 表名：`conversation_log`
  - 变更类型：无（仅写入行数语义变化）
  - 字段详情：无新增列；`round_id` 含义更新见上文数据库表结构
- 未完成项记录：
  - 未完成功能：管理后台对话查看页面对「同一 round 多行 assistant」的展示与可读性优化
  - 原因：STEP-011 明确不包含 Admin UI
  - 计划在后续 STEP（产品排期）中处理

### STEP-012：内容安全兼容新结构化输出（§9.1 / §9.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `_execute_llm_bundle` 内 Step5 解析成功且 generation 仍有效后，依次执行：① `_check_inner_monologue_safety` 对 `inner_monologue` 调用 `check_content`，违规则 `logger.warning` 并赋空串（不拦截整轮，避免 Step6 记忆污染）；② `_check_messages_safety` 对 `step5_result.messages` 每条非空 `content` 调用 `check_content`，任一 `is_safe=False` 则 `_mark_pack_failed(..., DELIVERY_STATUS_FAILED_BLOCKED)`、`_resolve_generation_future` 携带 `code=10101`（`ERR_CONTENT_UNSAFE`）并 `return`（不执行 Step5.5）；③ Step5.5 返回非空时对其 `messages` 再跑 `_check_messages_safety`，不通过则 `final_messages = merge_messages_if_exceed(step5_result.messages)` 并打 warning。未改 `content_safety_service.check_content` 规则本身；未对 Step6 产出做安全检测（§9.1）。
- 涉及文件：
  - `backend/constants.py`（修改：新增 `DELIVERY_STATUS_FAILED_BLOCKED = "failed_blocked"`）
  - `backend/routers/chat.py`（修改：新增 `_check_messages_safety`、`_check_inner_monologue_safety`；`_execute_llm_bundle` 插入上述检测逻辑）
  - `tests/test_step012_content_safety.py`（新增：集成 + 辅助函数单测共 10 条）
  - `docs/contract.md`（修改：本开发日志、`POST /api/chat/send` 的 `failed`/语义摘要、`delivery_status` 示例、顶部「最后更新」摘要）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：`conversation_log.delivery_status`（user 行）— 新增合法取值 **`failed_blocked`**（与 `backend/constants.py` 常量 `DELIVERY_STATUS_FAILED_BLOCKED` 一致），表示 **AI 侧** Step5 对外 messages 内容安全拦截导致的整轮失败
- 测试结果：✅ 全部通过（`pytest tests/test_step012_content_safety.py` 10 条；`pytest tests/test_chat.py` 36 条；`pytest tests/test_step5_5.py` 32 条回归）
- 备注：`POST /api/chat/resend` 依赖的 `_open_window_has_bang` 当前仅将 `failed_timeout` / `failed_error` 视为「叹号可重发」；**`failed_blocked` 未纳入**，故纯内容拦截失败时 **可能** 返回 **10107**（无可重发），与超时/解析类叹号行为不完全一致；若产品要求拦截后也可重试，需在后续 STEP 扩展 `_open_window_has_bang` 与前端叹号映射。
- API / 接口契约：
  - 接口名称：`POST /api/chat/send`、`POST /api/chat/resend`（SSE 成功路径）
  - Method + Path：`POST /api/chat/send`、`POST /api/chat/resend`
  - Request Body：无变更（与既有 `ChatSendRequest` / `ChatResendRequest` 一致）
  - Response：
    - 成功（SSE）：事件类型集合不变；**`failed` 事件** 在 Step5 messages 安全拦截时 **`code` 可为 `10101`**（`ERR_CONTENT_UNSAFE`），`message` 为服务端文案（如「内容安全拦截」）
    - 失败（未进入 SSE）：无变更（用户输入侧 **10101** 仍为既有语义）
  - 变更类型：**修改**（SSE `failed` 的 `code` 语义扩展；成功路径内部增加 AI 输出安全分支）
- 数据模型：
  - 表名：`conversation_log`
  - 变更类型：**无新列**；`delivery_status` 字符串枚举在契约与常量层 **新增取值** `failed_blocked`（见上「字段变更」）
  - 字段详情：无新增物理列
- 未完成项记录：
  - 无（`failed_blocked` 与重发叹号是否打通见上「备注」，属产品/后续 STEP 可选）

### STEP-013：Step6 记忆总结 LLM Prompt + JSON 解析（R-MEM-01 / R-MEM-06 / R-MEM-07 / §2.5）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `memory_llm_service.py`，提供 `Step6MemoryOutput`（驼峰 11 字段，与 Step5 snake_case 独立）；`build_step6_prompt()` 按「系统指令 + 当前时间 + 人格 + 关系状态 + 近期历史（不含本轮）+ 本轮完整对话 + 任务说明 + §2.5 完整 few-shot」拼装；本轮「林小梦」侧正文仅拼接 **Step5 解析产出的** `messages[].content`（§2.9.3，不含 Step5.5 润色）；`parse_step6_output()` 用与 Step5 同类的首段 `{...}` 正则提取后 `json.loads`，顶层非对象则失败；字段缺失时除 `InnerMonologue` 默认空串外其余默认字符串「无」；非法 JSON 抛 `Step6ParseError`。多行 `key：value` 中行级合法性（全角冒号）不在本模块校验，由 STEP-014 丢弃非法行。
- 涉及文件：
  - `backend/services/memory_llm_service.py`（新增：`Step6MemoryOutput`、`Step6ParseError`、`parse_step6_output`、`build_step6_prompt`、§2.5 few-shot 常量）
  - `tests/test_memory_llm_service.py`（新增：解析与 Prompt 拼装单测 30 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志条目）
- 字段变更：
  - 新增字段：无（无 DDL；`Step6MemoryOutput` 为内存模型，非 DB 列）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_memory_llm_service.py` 30 条）
- 备注：`build_step6_prompt` / `parse_step6_output` 已由 **STEP-016** 在 `execute_step6` 管线中调用；四路向量 `upsert_step6_vectors`、relationship 写回 `update_relationship_from_step6` 同由 STEP-016 编排调用。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service 与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：—
  - 变更类型：**无**
  - 字段详情：无
- 未完成项记录：
  - 未完成功能：Step6 调用后的 **LLM 统计异步写入**（与主对话 `llm_service` 统计路径对齐，若产品要求单独计数可后续 STEP 增补）
  - 原因：STEP-016 范围不含 Redis `llm_stats` / `llm_response_times` 写入
  - 计划在后续运维/观测 STEP 或统一埋点中处理

### STEP-015：Step6 relationship 标量 + 历史 + Future 槽（R-MEM-05 / §2.8.4）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `relationship_service.py` 的 `RelationshipService` 类中新增 `update_relationship_from_step6(relationship, step6_output, round_id, *, future_time_natural, future_action)` 方法。**6 个标量字段写回**：通过 `_STEP6_FIELD_MAP` 映射 Step6 驼峰字段名到 relationship 表蛇形列名（`UserRealName`→`user_real_name`、`UserHobbyName`→`user_hobby_name`、`UserDescription`→`user_description`、`CharacterPurpose`→`character_purpose`、`CharacterAttitude`→`character_attitude`、`RelationDescription`→`relation_description`）；值非「无」→ `setattr` 覆盖 + 调用 `RelationshipHistoryService.append_history` 写入变更历史（old_value 从当前 relationship 实例读取）；值为「无」→ 跳过该列赋值，保留库内上一轮值。**Future 槽处理**：优先判定 `future_action` 为「无」→ 清空 `future_timestamp` 和 `future_action`；否则当 `future_time_natural` 非「无」时调用 `parse_future_time()` 解析——成功→写入 `future_timestamp`（Unix 时间戳）+ `future_action`，失败→清空 future 字段 + 保留 `proactive_times` 不变 + `logger.warning` 结构化日志。所有变更历史记录 `trigger_source='step6'`，携带 `round_id`。不在本 STEP 范围：`relation_change.delta` 与 growth 的映射（R-BND-09 暂缓）、`proactive_times` 的 +1 逻辑（STEP-022 负责）。
- 涉及文件：
  - `backend/services/relationship_service.py`（修改：新增 `_STEP6_FIELD_MAP` 类属性、`update_relationship_from_step6` 方法；新增 import `RelationshipHistoryService`、`parse_future_time`、`Optional`）
  - `tests/test_step015_relationship_step6.py`（新增：标量写回+历史+Future 槽单测 11 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-013 未完成项更新）
- 字段变更：
  - 新增字段：无（无 DDL；所需列已由 STEP-001 创建）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step015_relationship_step6.py` 11 条）
- 备注：`update_relationship_from_step6` 已由 **STEP-016** `execute_step6` 在独立 DB session 中调用并 `commit`。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service 方法与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：`relationship`（已有）、`relationship_change_history`（已有）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无
- 未完成项记录：
  - ~~`proactive_times` +1（STEP-022）~~ → ✅ 已由 STEP-022 完成
  - 未完成功能：`relation_change.delta` 与 growth 的映射（R-BND-09）
  - 原因：STEP-015 范围仅限 Service 方法交付
  - 计划在 R-BND-09 相关 STEP 中处理

### STEP-014：Step6 DashVector 四路向量写入（R-MEM-04）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `memory_llm_service.py` 中实现 `parse_kv_lines(text)`：按 `\n` 拆行，每行按**首处**全角冒号 `：` 分割为 `(key, value)`，strip 后 key 或 value 为空、或行内无全角冒号的行丢弃。`upsert_step6_vectors(output: Step6MemoryOutput, user_id: int)` 遍历四类字段与 `constants` 中 `MEMORY_TYPE_*` 映射：`CharacterPublicSettings`→`character_global`、`CharacterPrivateSettings`→`character_private`、`CharacterKnowledges`→`character_knowledge`、`UserSettings`→`user`；字段值等于字符串「无」（strip 后）则整路跳过；否则对合法行生成 `doc_id="{memory_type}:{stable_key}:{user_id或空}"`（无 user 后缀时第三段为空字符串，形如 `character_global:外貌-体态:`）；对 **value** 调用 `embedding_service.get_embedding`，向量非空则 `dashvector_client.upsert(doc_id, vector, fields, memory_type)`，其中 `fields.content` 为「key：value」整行文本；`character_private` 与 `user` 在 `fields` 中附带 `user_id`（整数），另两类不附带；`dashvector_client` 合并 `type=memory_type`（与 STEP-003 一致）。同 key 同 type（及同 user 作用域）再次 upsert 覆盖；本轮未再出现的 key **不**自动删除。返回 `dict[str, int]` 为各 `memory_type` 成功写入条数计数。
- 涉及文件：
  - `backend/services/memory_llm_service.py`（修改：新增 `parse_kv_lines`、`_build_doc_id`、`upsert_step6_vectors` 及常量映射；依赖 `embedding_service`、`dashvector_client`）
  - `tests/test_step6_vector_upsert.py`（新增：解析、doc_id、四路写入 mock 单测 22 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-013 备注与未完成项）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step6_vector_upsert.py` 22 条；回归 `tests/test_memory_llm_service.py` 30 条）
- 备注：`upsert_step6_vectors` 已由 **STEP-016** `execute_step6` 调用；旧向量清理、管理后台知识库 CRUD 不在本 STEP（需求注明 STEP-027 等）；`memory` 表 `dashvector_id` 与 Step6 行级 doc_id 无强制关联（Step6 使用稳定 doc_id 策略）。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部异步函数与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：**DashVector 集合**（配置项 `collection_name`，与既有向量库配置一致；无新集合名）
  - 变更类型：**运行时文档约定**（非 MySQL 迁移）
  - 字段详情：
    - 文档 `id`（即 upsert 的 `doc_id`）：字符串，`{memory_type}:{stable_key}:{user_id或空}`，`stable_key` 为全角冒号前的 key 原文
    - 向量字段 `vector`：与 `text-embedding-v3` 维度一致（与既有 `embedding_service` 一致）
    - `fields.type`：四类之一 `character_global` / `character_private` / `character_knowledge` / `user`（由客户端合并写入，与 STEP-003 检索 filter 一致）
    - `fields.content`：字符串，格式为「key：value」（全角冒号，与解析行一致）
    - `fields.user_id`：整数，**仅** `character_private`、`user` 两类写入；`character_global`、`character_knowledge` **省略**该字段
- 未完成项记录：
  - 无（对话链路调用已由 **STEP-016** 完成）

### STEP-016：Step6 异步入队 + M2 半异步 + 重试（§2.8.4 / §2.9.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`Step6Snapshot` 在 `_execute_llm_bundle` 内于 Step5 解析成功、内容安全通过、`_persist_bundle_success` 落库之后构建：`step6_messages = merge_messages_if_exceed(step5_result.messages)`（≤5，CP1，**不含** Step5.5 润色）；`asyncio.create_task(execute_step6(snapshot))` 入队，**不 await**，保证 `_resolve_generation_future` / SSE 不被 Step6 阻塞（M2）；`execute_step6` 内整段管线失败时 `asyncio.sleep(0.5)` 后 **再执行 1 次**（共 2 次），仍失败则 `logger.error` 含 `exc_info` 后返回，**允许不落库**；快照含 `persona`（Redis `active_config:persona`，空则 `DEFAULT_PERSONA`）、关系等级名、relationship 六列读快照、近期对话 `{role,content}`、Step5 `future`、打包用户原文 `bundled`；`_step6_pipeline`：`build_step6_prompt` → `llm_client.chat_sync`（**45s**，模块常量 `_STEP6_LLM_TIMEOUT_SEC`，固定值非环境变量）→ `parse_step6_output` → `upsert_step6_vectors` → 新开 `async_session_maker` 加载 `Relationship` → `update_relationship_from_step6` → `commit`；无 `relationship` 行则 warning 跳过标量更新；入队构建 try/except 仅日志。SSE 事件格式**未**改。
- 涉及文件：
  - `backend/services/step6_orchestrator.py`（新增：`Step6Snapshot`、`execute_step6`、`_ConvProxy`、`_step6_pipeline`）
  - `backend/routers/chat.py`（修改：导入 `DEFAULT_PERSONA`、`REDIS_KEY_PERSONA`、`Step6Snapshot`、`execute_step6`；闭环成功后 `create_task(execute_step6)`）
  - `tests/test_step016_step6_orchestrator.py`（新增：6 条单测）
  - `docs/contract.md`（修改：顶部摘要、H5 对话语义、STEP-006/008/013/014/015 备注与未完成项、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL；无新 HTTP 字段）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step016_step6_orchestrator.py` 6 条；回归 `tests/test_merge_messages.py` + `test_step016` 共 22 条）
- 备注：未实现 **STEP-028** 管理后台 Step6 失败监控页；Step6 **未**写入与主对话相同的 Redis `llm_stats` / `llm_response_times` 统计（与 `.cursorrules` 全量 LLM 统计口径可后续对齐）；退避固定 **500ms**（需求区间 200ms～1s 取默认中值）。
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由；`POST /api/chat/send` / `resend` 的 SSE 事件集合不变）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（服务端后台异步行为补充，见 H5 模块「语义摘要」）
- 数据模型：
  - 表名 / 集合名：`relationship`、`relationship_change_history`、DashVector 文档（与 STEP-014/015 一致）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 未完成功能：管理后台 Step6 失败可观测性（**STEP-028**）；Step6 LLM 与主链一致的 **Redis LLM 统计**写入（若产品要求）
  - 原因：本 STEP 明确排除管理端监控；统计未纳入范围
  - 计划在 STEP-028 或统一观测 STEP 中处理

### STEP-022：proactive_times 计数/清零 + 频控调整（R-FUT-03 / §2.2 变更 8.2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：**proactive_times 清零**：`chat.py` `POST /api/chat/send` 入口在用户消息落库 commit 后、防抖调度前，独立 session 查询 `relationship` 表，若 `proactive_times != 0` 则置 0 并 commit，异常仅日志不阻断主链路。**频控参数调整（§2.2 变更 8.2）**：`agent_service.py` `check_and_trigger` 方法中每日上限从 2 调整为 8（含 Future 槽消费计入），两次间隔从 `timedelta(hours=6)` 调整为 `timedelta(minutes=30)`。**proactive_times +1**：`generate_and_save_message` 在 Redis 计数器 INCR 后，独立 session 加载 `relationship`，若 `proactive_times < 3` 则 +1 并 commit（上限保护 3），异常仅日志不阻断。**Future 槽计入计数器**：新增 `increment_agent_count_for_future(user_id)` 方法，对 `agent:count:{user_id}:{date}` 执行 INCR + EXPIRE（TTL 到日末），供 STEP-023 Future 槽消费成功后调用。**30 天无活动清零**：新增 `reset_inactive_proactive_times()` 方法，查询 `proactive_times > 0` 且 `last_interaction_at` 为 NULL 或超过 30 天的 relationship 记录，将 `proactive_times` 置 0 + 清空 `future_timestamp`/`future_action`；`scheduler.py` 注册每日凌晨 1:00 UTC CronTrigger 执行该任务。**Agent 扫描间隔调整**：`scheduler.py` 中 Agent 主动消息扫描从 `IntervalTrigger(hours=6)` 调整为 `IntervalTrigger(minutes=30)`，与频控最小间隔匹配。
- 涉及文件：
  - `backend/routers/chat.py`（修改：`chat_send` 函数新增 proactive_times 清零逻辑块）
  - `backend/services/agent_service.py`（修改：`check_and_trigger` 频控参数 2→8、6h→30min；`generate_and_save_message` 新增 proactive_times +1 逻辑；新增 `increment_agent_count_for_future` 方法；新增 `reset_inactive_proactive_times` 方法）
  - `backend/tasks/scheduler.py`（修改：Agent 扫描间隔 6h→30min；新增 `_run_inactive_reset` 包装器 + `inactive_proactive_reset_task` CronTrigger 注册）
  - `tests/test_step022_proactive_times.py`（新增：proactive_times 计数/清零 + 频控参数单测 18 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志）
- 字段变更：
  - 新增字段：无（`proactive_times` 已在 STEP-001 添加）
  - 修改字段：无
- 测试结果：✅ 全部 18 条通过（`pytest tests/test_step022_proactive_times.py`：场景1 用户发消息清零 3 条、场景2 主动消息后+1 3 条、场景3 概率公式验证 3 条、频控参数边界 4 条、30 天无活动清零 4 条、Future 槽计入计数器 1 条）
- API / 接口契约：
  - 接口名称：`POST /api/chat/send`（已有接口，新增内部副作用）
  - Method + Path：POST /api/chat/send
  - Request Body：无变更
  - Response：无变更
  - 变更类型：**内部行为变更**（无对外 HTTP 契约变更，仅新增内部 proactive_times 清零副作用）
- 数据模型：
  - 表名 / 集合名：`relationship`（已有表，读写 `proactive_times` / `future_timestamp` / `future_action`）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - ~~未完成功能：Future 槽消费轮询（STEP-023）~~ → ✅ 已由 **STEP-023** 完成
  - ~~未完成功能：Step8 子链路专用 LLM 调用与编排（STEP-024）~~ → ✅ 已由 **STEP-024** 完成

### STEP-023：Future 槽消费轮询 Handler（R-AGT-02 / Step8 轮询）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `FutureSlotHandler`（`future_handler.py`），由 APScheduler 每 **60 秒** 执行 `scan_and_consume()`：联表 `relationship` + `users`，筛选 **4 条件同时成立** 的到期槽（`future_timestamp` 非空、≤当前 Unix 秒、>当前时间−1800、用户未封禁）。单用户 `_consume_one()`：**始终**检查 Redis `agent:blacklist:{user_id}`；**不**走 8 次/天与 30 分钟间隔频控；调用 `calculate_action_score(user_id, TriggerType.FUTURE)`，评分 **<6** 或黑名单则 **仅清空** `future_timestamp`/`future_action` 并打日志。通过则调用 `execute_step8_subchain(user_id, future_action)` 执行 Step8 子链路（已由 STEP-024 实现）；成功后再 `_on_consume_success`：**清空槽**、`proactive_times` **+1**（上限 3）、`increment_agent_count_for_future` 计入当日 `agent:count`。`cleanup_expired_slots()` 清理 **超出 30 分钟窗口** 的残留槽位。路 B：`check_and_trigger` 在频控前若 `_has_pending_future_slot`（`future_timestamp > now`）则 **跳过** 定时扫描写入。
- 涉及文件：
  - `backend/services/future_handler.py`（新增：`FutureSlotHandler` / `future_handler` 单例）
  - `backend/tasks/scheduler.py`（修改：新增 `_run_future_slot_scan`、`future_slot_scan_task` IntervalTrigger 60s）
  - `backend/services/agent_service.py`（修改：`check_and_trigger` 路 B 优先级保护；`_has_pending_future_slot`；`TRIGGER_WEIGHTS` / `AGENT_FALLBACK_REPLIES` 增加 FUTURE；`import time`）
  - `backend/models/agent_message.py`（修改：`TriggerType.FUTURE`）
  - `tests/test_step023_future_handler.py`（新增：14 条单测）
  - `docs/contract.md`（修改：`agent_message.trigger_type` 说明、顶部摘要、本开发日志、STEP-022 未完成项）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：`agent_message.trigger_type` — 允许取值扩展为含 **`FUTURE`**（仍为 `String(10)`，ORM 层 `TriggerType` 常量）
- 测试结果：✅ 全部通过（`pytest tests/test_step023_future_handler.py` 14 条）
- 备注：Future 消费成功后已由 **STEP-024** 实现的 `execute_step8_subchain()` 完成 Step8 专用子链路。轮询周期取 **60 秒**（需求「参考每秒」的折中，避免 DB 压力过大）。
- API / 接口契约：
  - 接口名称：无新增对外 HTTP 接口（仅后台定时任务）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（运行时行为：定时扫描 Redis + MySQL）
- 数据模型：
  - 表名 / 集合名：`agent_message`（`trigger_type` 语义扩展）、`relationship`（读写 Future 槽与 `proactive_times`）、Redis `agent:count:{user_id}:{date}`、`agent:blacklist:{user_id}`
  - 变更类型：**取值约定扩展**（无表结构 DDL）
  - 字段详情：无新列；`trigger_type` 新增合法枚举值 `FUTURE`
- 未完成项记录：
  - ~~未完成功能：Step8 子链路 **专用** LLM 调用与编排（STEP-024）~~ → ✅ 已由 **STEP-024** 完成
  - 未完成功能：管理后台 Future/Agent 监控页（若需求单独立项）

---

### STEP-024：Step8 子链路（R-L1L3-12 / §8.3 子链路编排）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `step8_subchain.py`，实现 Future 槽到期触发的主动消息子链路 `execute_step8_subchain(user_id, future_action)`，复用主链 Step 变体：**Step1** 在单个 `async with async_session_maker()` 会话内 **顺序** `await` `_get_recent_conversations`（最多 20 条、反转后取末 10 轮参与下游）、`_get_relationship`、`_get_emotion_context`（数据源与主链相同；**不得**对同一 `AsyncSession` 使用 `asyncio.gather` 并行执行多条语句，否则触发 SQLAlchemy 异步会话状态错误）；**Step1.5 变体** 调用 `execute_query_rewrite(source="step8")`，输入用 `future.action` 替代 `last_user_text`，降级路径用 `future.action` 通过 `embedding_service.get_embedding` 生成单 Embedding（R-L1L3-12）；**Step2** 完全复用 `execute_multi_vector_retrieval()`；**Step3 变体** 调用 `PromptBuilder.build_step8_prompt()`，将 9 模块中的【用户消息】替换为【主动发起】模块（含 `future.action` 摘要，指导 LLM 以预约内容自然开启对话）；**Step5** 完全复用 `llm_service.chat_with_step5_parse()`，含内容安全检查（`check_content`）与人格偏离检测（`_check_persona_risk` 关键词扫描，偏离时回退默认回复写入 `agent_message`）；**Step5.5** 调用 `execute_step5_5(gate_a_override=0.03)` 配置较低触发概率（主链 0.12 vs Step8 0.03）；**产出** 写入 `agent_message` 表（`trigger_type=FUTURE`，不走 SSE），`sort_seq` 通过 `allocate_sort_seq` 分配；**Step6** `asyncio.create_task(execute_step6(snapshot))` 异步入队记忆总结（不阻塞）；**衰减门控** `_decay_gate_and_update`：`proactive_times` +1（上限 3），以 `0.15^(proactive_times+1)` 概率从 Step5 输出解析 future 字段并写入下一轮 Future 预约。边界处理：`future_action` 为空/None/纯空白→日志 + 返回 False。`prompt_builder.py` 新增 `_build_proactive_input(future_action, limits)` 和 `build_step8_prompt(user_id, ...)` 两个方法。`step5_5_service.py` `should_trigger_step5_5()` / `execute_step5_5()` 新增 `gate_a_override` 可选参数支持外部覆盖门闩 A 概率。`future_handler.py` `_consume_one()` 中 `generate_and_save_message(FUTURE)` 占位替换为 `execute_step8_subchain(user_id, future_action)`。**维护（2026-05-07）**：修正 Step1 装载实现描述（顺序查询替代错误的同 session 并行 gather）；不改变对外契约。
- 涉及文件：
  - `backend/services/step8_subchain.py`（新增：`execute_step8_subchain`、`_get_recent_conversations`、`_get_relationship`、`_get_emotion_context`、`_build_step8_round_context`、`_check_persona_risk`、`_fallback_write_agent_message`、`_decay_gate_and_update`；常量 `STEP8_GATE_A_PROBABILITY=0.03`、`DECAY_BASE=0.15`、`PROACTIVE_TIMES_CAP=3`、`STEP8_FALLBACK_REPLY`、`PERSONA_RISK_KEYWORDS`）
  - `backend/services/prompt_builder.py`（修改：`PromptBuilder` 新增 `_build_proactive_input()` 和 `build_step8_prompt()` 方法）
  - `backend/services/step5_5_service.py`（修改：`should_trigger_step5_5()` 和 `execute_step5_5()` 新增 `gate_a_override` 参数）
  - `backend/services/future_handler.py`（修改：`_consume_one()` 中调用替换为 `execute_step8_subchain`；新增 `from backend.services.step8_subchain import execute_step8_subchain`）
  - `tests/test_step024_step8_subchain.py`（新增：10 条单测）
  - `tests/test_step023_future_handler.py`（修改：2 条测试适配 `execute_step8_subchain` mock）
  - `docs/contract.md`（修改：顶部摘要、STEP-022/STEP-023 未完成项更新、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step024_step8_subchain.py` 10 条：场景1 完整子链路执行+agent_message 写入、场景2 Step1.5 失败降级用 future.action Embedding、场景3 proactive_times=3 衰减概率≈0.05%、衰减门控命中写入 Future、衰减门控未命中不写入、future_action 空/None/纯空白 3 条边界、Step5 失败返回 False、proactive_times 上限不超过 3）；既有测试 `test_step023_future_handler.py` 14 条 + `test_step5_5.py` 32 条 + `test_prompt_builder.py` 30 条全部通过（共 86 条无回归）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由，子链路为内部后台任务）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（运行时行为：Future 槽到期后内部触发）
- 数据模型：
  - 表名 / 集合名：`agent_message`（写入 `trigger_type=FUTURE` 的主动消息）、`relationship`（读写 `proactive_times`/`future_timestamp`/`future_action`）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-021：Step3 Prompt 新增模块 + Token 裁剪（R-L1L3-19）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`prompt_builder.py` 重构为 9 模块结构拼装（R-L1L3-19）。新增模块 A「角色设定与知识」（`_build_character_knowledge_prompt()`）：合并 Step2 的 `character_global` + `character_private` 结果标记为「角色设定」，`character_knowledge` 结果标记为「角色知识」，所有条目按 DashVector score 降序排列，超过 `character_knowledge` Token 上限时从低分端逐条移除（不重新计算 Embedding）；模块 A 插入在 Persona 之后、Relationship 之前。新增模块 B「时间与活动状态」（原 `_build_time_prompt()`）：形式上归入 `time_activity` 模块键，保持在 Emotion 之后 Recent Chat 之前位置，空活动描述时跳过活动行。`MAX_TOTAL_TOKENS` 从 5200 调整为 7373（基线 ×1.8）；`MODULE_TOKEN_LIMITS` 全部更新为 R-L1L3-19 指定默认值（system 720 / persona 1080 / character_knowledge 600 / relationship 360 / memory 900 / emotion 270 / time_activity 80 / recent_chat 1800 / user_input 900）。新增 `_load_token_limits()` 方法：从 `admin_config_service.get_active_config("prompt_token_config")` 热加载 JSON 配置（期望格式 `{"max_total": 7373, "system": 720, ...}`），仅覆盖存在且 > 0 的键，其余回退默认值，异常时全部回退默认值。`_trim_to_budget()` 实现 5 级裁剪优先级引擎：①`recent_chat` 从最早对话逐条删除 → ②`memory` 从末尾（最低分）逐条删除 → ③`character_knowledge`（模块 A）按 score 从低到高逐条删除 → ④`relationship` 扩展部分移除（调用 `_build_relationship_prompt_core()` 仅保留核心等级/语气/沉默修正）→ ⑤`time_activity`（模块 B）整块移除；System / Persona 绝不裁剪。`_build_memory_prompt()` 扩展为兼容 Step2 检索结果（dict 列表，含 `content`/`score`）和 Memory ORM 实例两种格式。`build_chat_prompt()` 新增 `retrieval_results: dict | None` 参数，接收 `MultiVectorRetrievalResult.format_for_prompt()` 输出的四路检索结果 dict。所有模块构建方法统一接收 `limits` 参数（从热配加载），不再硬编码读取全局常量。`chat.py` `_execute_llm_bundle` 中：`memories` 参数改为直接传递 `memories_raw`（Step2 user_results dict 列表），不再通过 `_MemoryProxy` 包装；新增 `retrieval_for_prompt = retrieval_result.format_for_prompt()` 并传递给 `build_chat_prompt`。`build_active_message_prompt()` 保持向后兼容（仍接受 Memory ORM 实例，不使用模块 A/B）。
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：常量 `MAX_TOTAL_TOKENS`/`MODULE_TOKEN_LIMITS` 更新；新增 `TRIM_PRIORITY`/`MODULE_ORDER`/`_PROMPT_TOKEN_CONFIG_KEY` 常量；新增 `admin_config_service` 导入；`PromptBuilder` 类重构——新增 `_load_token_limits()`/`_build_character_knowledge_prompt()`/`_merge_character_knowledge_items()`/`_render_character_knowledge()`/`_build_relationship_prompt_core()`/`_trim_to_budget()` 方法；`build_chat_prompt()` 新增 `retrieval_results` 参数、9 模块 dict 拼装流程；所有 `_build_*` 方法新增 `limits` 参数；删除旧 `_check_token_limit()` 方法）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 中删除 `_MemoryProxy` 类及包装逻辑，改为直接传 `memories_raw` + `retrieval_for_prompt`）
  - `tests/test_prompt_builder.py`（修改：30 条测试含新增 STEP-021 场景：全量注入无裁剪、总 Token 超限裁剪优先级、模块 A score 裁剪、热配覆盖默认值、9 模块顺序验证、模块 A 空结果跳过、relationship 扩展裁剪、Step2 dict 格式记忆、默认 Token 上限验证）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-020 未完成项关闭）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 admin_config 键：`prompt_token_config`（JSON，`{"max_total": 7373, "system": 720, "persona": 1080, "character_knowledge": 600, "relationship": 360, "memory": 900, "emotion": 270, "time_activity": 80, "recent_chat": 1800, "user_input": 900}`，由管理后台 STEP-025 创建的配置页发布）
- 测试结果：✅ 全部通过（`pytest tests/test_prompt_builder.py` 30 条：含场景1 全量注入无裁剪、场景2 超限先裁 recent_chat 再裁 memory、场景3 模块 A 超 600 按 score 裁剪、边界热配 recent_chat=1000 使用配置值、9 模块顺序/8 模块顺序（无模块 A）、模块 A 内容注入/空结果跳过、Step2 dict 格式记忆、relationship 扩展裁剪核心、Token 默认值验证、原有 STEP-004/STEP-017 测试全量保留）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部 Prompt 拼装改造）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取 `prompt_token_config`，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 管理后台「Prompt Token 配置」页创建与发布流程（STEP-025）

---

### STEP-020：Step2 多路向量检索（R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `multi_vector_retrieval_service.py`，实现 Step2 多路向量检索。`MultiVectorRetrievalResult` dataclass 承载 4 路检索结果（`character_global_results` / `character_private_results` / `character_knowledge_results` / `user_results`），附带 `top_k` / `threshold` / `is_fallback` 元数据，提供 `all_results`（去重合并按 score 降序）、`user_memory_results`（兼容旧 `memories_raw` 格式）、`format_for_prompt`（分路 dict）属性。`execute_multi_vector_retrieval()` 主入口：正常路径（Step1.5 成功）阶段① `asyncio.gather` 并行调用 `embedding_service.get_embedding` 生成 3 个 Embedding（CharacterGlobal / CharacterKnowledge / UserProfile），阶段② `asyncio.gather` 并行执行 4 次 `dashvector_client.search`（`character_global` 无 user_id + `character_private` 有 user_id 复用 CharacterGlobal Embedding + `character_knowledge` 无 user_id + `user` 有 user_id）；降级路径（Step1.5 失败）用 `fallback_embedding` 直接执行全部 4 路检索（R-L1L3-12），过滤条件不变。从 `admin_config_service.get_active_config("vector_retrieval_config")` 热加载 TopK 和阈值（R-L1L3-17），期望 JSON `{"top_k": 3, "threshold": 0.7}`，无配置或解析失败时回退默认值。`chat.py` `_execute_llm_bundle` 中：在 `round_context` 构建后新增 Step1.5（`execute_query_rewrite`）+ Step2（`execute_multi_vector_retrieval`）调用，`memories_raw` 取自 `retrieval_result.user_memory_results`，`memories` 取自 `_MemoryProxy` 包装后的列表；删除旧 `user_embedding = await _get_embedding(last_user_text)` 及关联 `_search_memories` 调用（R-L1L3-21）；`_persona_text` 在 Step1.5 阶段预获取后复用至 Step6 快照构建，消除重复 Redis `GET`。
- 涉及文件：
  - `backend/services/multi_vector_retrieval_service.py`（新增：`MultiVectorRetrievalResult`、`_load_retrieval_config`、`_phase1_generate_embeddings`、`_phase2_parallel_search`、`_fallback_search`、`execute_multi_vector_retrieval`）
  - `backend/routers/chat.py`（修改：新增 `execute_multi_vector_retrieval` / `execute_query_rewrite` 导入；`_execute_llm_bundle` 中删除旧 `user_embedding` / `_search_memories` 代码，新增 Step1.5 + Step2 调用链，`_persona_text` 提前获取复用至 Step6）
  - `tests/test_multi_vector_retrieval_service.py`（新增：6 条单测）
  - `docs/contract.md`（修改：顶部摘要、本开发日志、STEP-019 未完成项更新）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 admin_config 键：`vector_retrieval_config`（JSON，`{"top_k": 3, "threshold": 0.7}`，由管理后台 STEP-025 创建的配置页发布）
- 测试结果：✅ 全部通过（`pytest tests/test_multi_vector_retrieval_service.py` 6 条：场景1 正常 3 Embedding+4 检索 ≤12 条、场景2 降级 1 Embedding+4 检索、场景2b 降级无 Embedding 返回空、场景3 部分路 0 命中、边界热配 TopK=5 覆盖默认、无配置回退默认值）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部数据流改造）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取 `vector_retrieval_config`，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - ~~Prompt 拼装层消费 4 路检索结果（STEP-021）~~ → ✅ 已由 STEP-021 完成
  - 管理后台「向量召回配置」页创建与发布流程（STEP-025）

---

### STEP-019：Step1.5 查询重写 LLM（R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14）
- 完成时间：2026-05-05（**2026-05-08** 调整超时与业务层重试策略，见实现说明）
- 状态：✅ 已完成
- 实现说明：新增 `query_rewrite_service.py`，实现 Step1.5 查询重写 LLM 调用。`QueryRewriteOutput` Pydantic 模型定义 7 字段输出（`InnerMonologue` + `CharacterGlobalQueryQuestion`/`Keywords` + `CharacterKnowledgeQueryQuestion`/`Keywords` + `UserProfileQueryQuestion`/`Keywords`，字段名与 R-L1L3-09 严格一致）；`QueryRewriteResult` dataclass 作为返回值（`success`=True 时 `output` 非空，`success`=False 时 `fallback_embedding` 非空为降级成功）。`_build_step1_5_prompt()` 按需求文档 Step1.5 Prompt 结构拼装 7 模块（系统指令、时间活动、人格、关系、近期对话、用户消息、任务含完整输出 JSON Schema），复用 STEP-018 的 `round_context` 预计算值（R-L1L3-14：共用已截取的 `recent_10`，不新增 DB 查询），兼容 dict 和 ORM 实例两种对话格式。`execute_query_rewrite()` 主入口：**timeout=45s**（`_STEP1_5_TIMEOUT_SEC`）；**业务层不重试**（整轮「LLM + 解析」仅 1 次，失败后立即 `_fallback_with_embedding()`）；底层经 `llm_client.chat_sync`，**单次 HTTP 超时同 45s**，内层仍最多 **3 次** POST + 1s/2s 退避（`LLM_MAX_RETRIES`）；`_parse_query_rewrite_output()` 用与 Step5/Step6 同类的首段 `{...}` 正则提取后 `json.loads`，校验至少一组 QueryQuestion 非空；降级（R-L1L3-12）：用 `last_user_text`（Step8 子链路为 `future.action`）通过 `embedding_service.get_embedding` 生成单 Embedding 作为 Step2 全部 4 路检索的统一 query，不触发叹号，用户无感知。结构化日志含 `user_id`、`elapsed`、`error`、`source`（区分主链 `main` / Step8 子链路 `step8`）。`InnerMonologue` 不落库、不返前端。**与整链等待**：Step1.5 为 `_execute_llm_bundle` 内首段 LLM 子调用之一，其 `chat_sync` 最坏耗时可 **单独超过** `_BUNDLE_WAIT_TIMEOUT_SEC`（120s），与 **SSE `wait_for`** 的关系见 **POST /api/chat/send** 与 **「部署与网关（对话 SSE）」**。
- 涉及文件：
  - `backend/services/query_rewrite_service.py`（新增：`QueryRewriteOutput`、`QueryRewriteResult`、`_build_step1_5_prompt`、`_parse_query_rewrite_output`、`execute_query_rewrite`、`_fallback_with_embedding`）
  - `tests/test_query_rewrite_service.py`（新增：7 条单测，mock `llm_client.chat_sync` / `embedding_service.get_embedding`）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_query_rewrite_service.py` 7 条：场景1 正常返回三组 QueryQuestion/Keywords、场景2 LLM 超时后降级与结构化日志、场景3 InnerMonologue 仅 `output` 内存字段、边界非法 JSON 一次失败后降级、`_parse_query_rewrite_output` 与 `_build_step1_5_prompt` 纯函数）
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部新增查询重写层）
- 数据模型：
  - 表名 / 集合名：无（不涉及 DB 变更）
  - 变更类型：**无**
  - 字段详情：无新列
- 未完成项记录：
  - ~~`_execute_llm_bundle` 接入 `execute_query_rewrite` 调用~~ → **已在 STEP-020 中完成**
  - 管理后台 Step1.5 失败记录查询（R-L1L3-13，STEP-028 或统一观测 STEP 中处理）

---

### STEP-018：Step1 并行装载扩展（R-L1L3-01 / R-L1L3-06）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `_execute_llm_bundle` 的 LLM 打包路径中，于 `_get_relationship` 读取之后新增 `_build_round_context()` 辅助函数构建本轮内存上下文 dict，包含：`time_description`（调用 `_generate_time_description()`）、`activity_description`（调用 `get_activity_description()`）、6 个关系扩展字段（`relation_description` / `user_real_name` / `user_hobby_name` / `user_description` / `character_purpose` / `character_attitude`，NULL 时用占位文案）、`level` / `level_name` / `silence_days`；`round_context` 在 Step5.5（`execute_step5_5` 调用处）和 Step6（`Step6Snapshot` 构建处）共用同一份，不重复 SELECT；`POST /api/chat/send` 的 `asyncio.gather` 中移除 `_get_relationship`（R-L1L3-01：无下游消费的重复 SELECT）；`build_chat_prompt` 新增可选 `round_context` 参数，`_build_time_prompt` 优先使用预计算的时间/活动描述值，避免重复生成/Redis 读取
- 涉及文件：
  - `backend/routers/chat.py`（修改：新增 `from datetime import datetime`；新增 `_generate_time_description` / `get_activity_description` 导入；新增 `_build_round_context()` 辅助函数；`_execute_llm_bundle` 中构建 `round_context` 并传入 `build_chat_prompt`、Step5.5、Step6 调用处；`chat_send` 的 gather 移除 `_get_relationship`）
  - `backend/services/prompt_builder.py`（修改：`build_chat_prompt` 新增 `round_context: dict | None = None` 参数并传递给 `_build_time_prompt`；`_build_time_prompt` 新增 `round_context` 关键字参数，有值时跳过 `_generate_time_description()` / `get_activity_description()` 调用）
  - `tests/test_step018_round_context.py`（新增：10 条单测覆盖扩展字段有值、全 NULL 占位、时间/活动注入、新用户无 relationship、gather 静态检查、round_context 键完整性）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step018_round_context.py` 10 条；`pytest tests/test_prompt_builder.py tests/test_chat.py` 55 条回归通过）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部数据流优化）
- 数据模型：
  - 表名 / 集合名：`relationship`（仅读取已有字段，无 DDL）
  - 变更类型：**无**
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-017：时间描述串 + 活动描述串生成（R-L1L3-11）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`_generate_time_description()` 已在 STEP-004 实现（纯代码按周几+时段+小时:分钟生成自然语言）；本 STEP 新增 `get_activity_description()` 异步函数，从 Redis `active_config:activity_schedule` 读取静态 JSON（格式如 `{"14-18": "她在写代码"}`），按当前小时段匹配，未配置/未命中/解析失败→空字符串；`_build_time_prompt()` 改为 async，活动描述非空时追加在时间描述后一行，空串时跳过
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：新增 `import json`；新增模块级 `get_activity_description()` 异步函数；`_build_time_prompt()` 同步→异步，条件注入活动描述；`build_chat_prompt()` 对应 await）
  - `tests/test_prompt_builder.py`（修改：新增 9 条测试用例，`_build_prompt` 辅助函数增加 `get_activity_description` mock）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 Redis 缓存键：`active_config:activity_schedule`（JSON，由管理后台通用 admin_config 编辑发布）
- 测试结果：✅ 全部通过（`pytest tests/test_prompt_builder.py` 19 条）
- admin_config 配置格式：`config_key = "activity_schedule"`，`config_value` 为 JSON 对象，key 为小时范围 `"start-end"`（start <= hour < end），value 为活动描述文案字符串
- 备注：不创建管理后台专属页面（复用现有 admin_config 通用编辑）；不实现完整活动计划功能（TD-021 技术债）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅 Prompt 拼装层内部变更）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-025：管理后台向量召回 + Prompt Token 热配置（R-L1L3-17 / R-L1L3-19 / §6）
- 完成时间：2026-05-07
- 状态：✅ 已完成
- 实现说明：新增 `GET|PUT /api/admin/configs/vector_retrieval_config` 与 `GET|PUT /api/admin/configs/prompt_token_config`；**PUT 语义为部分字段 PATCH**：请求体仅含待更新键（`exclude_unset` + 剔除 `null`），与库中当前生效 JSON 及代码默认值合并后调用 `admin_config_service.publish_config`（MySQL 多版本行 + Redis `active_config:{config_key}` + `publish_monitor:{key}`）；鉴权 `super_admin` + `ai_trainer`；`GET` 返回合并后的完整生效视图供表单展示；管理端单页双 Tab `vector-token-config.html` 保存时仅提交相对首屏快照有变化的字段；审计沿用 `publish_config` 内 `log_operation` → `admin_operation_log`（`module=ai_config`，`action=publish`）
- 涉及文件：
  - `backend/routers/admin/vector_config.py`（新增）
  - `backend/main.py`（修改：`include_router` 注册 `/api/admin/configs`）
  - `backend/constants.py`（修改：新增 `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID = 20046` 及 `ADMIN_ERROR_MESSAGES`）
  - `admin/pages/vector-token-config.html`（新增）
  - `admin/static/js/admin-api.js`（修改：`MENU_CONFIG` 增加 `vector-token` 菜单项，`super_admin` / `ai_trainer`）
  - `tests/test_admin_vector_token_config.py`（新增）
  - `docs/contract.md`（修改：文首摘要、`### 模块：向量召回与 Prompt Token 热配置`、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL；`admin_config` 仍用既有 `config_key` / `config_value` 行）
  - 修改字段：无
  - 新增错误码：`ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`（20046）— 请求体未含任何有效更新字段，或合并后向量/Token 业务校验失败
- 测试结果：✅ 全部通过（`pytest tests/test_admin_vector_token_config.py` 6 条）
- API / 接口契约：
  - 接口名称：向量召回热配置读取 / 部分更新发布
  - Method + Path：`GET /api/admin/configs/vector_retrieval_config`、`PUT /api/admin/configs/vector_retrieval_config`
  - Request Body（PUT，均为可选，**至少其一**，`extra=forbid`）：
    - `"top_k"`: `int` — 1–20，全路统一 TopK
    - `"threshold"`: `float` — 0.0–1.0，相似度阈值
  - Response：
    - 成功：`{ "code": 0, "data": { ... }, "message": "success" }` — GET 的 `data` 为 `{ top_k, threshold }`；PUT 的 `data` 为 `publish_config` 返回的 `{ version, published_at }` 等
    - 失败：空 PATCH 或合并后校验失败 → `{ "code": 20046, "message": string, "data": null }`；鉴权失败 → HTTP **403**；非法 JSON / Pydantic 校验失败 → HTTP **422**
  - 变更类型：**新增**
  - 接口名称：Prompt Token 热配置读取 / 部分更新发布
  - Method + Path：`GET /api/admin/configs/prompt_token_config`、`PUT /api/admin/configs/prompt_token_config`
  - Request Body（PUT，字段均可选，**至少其一**，`extra=forbid`；整型 `ge=1`，`max_total` `le=50000`，模块单项 `le=20000`）：
    - `"max_total"`: `int` — 总池上限
    - `"system"` / `"persona"` / `"character_knowledge"` / `"relationship"` / `"memory"` / `"emotion"` / `"time_activity"` / `"recent_chat"` / `"user_input"`: `int` — 各模块 Token 上限
  - Response：成功/失败信封同上；GET 的 `data` 为上述键的完整对象（与 `prompt_builder` 默认合并）
  - 变更类型：**新增**
- 数据模型：
  - 表名 / 集合名：`admin_config`（无 DDL 变更）
  - 变更类型：**无**（沿用现有多行语义：`config_key` 为 `vector_retrieval_config` / `prompt_token_config` 的已发布行）
  - 字段详情：无新列；`config_value` JSON 形态由本 STEP 管理端约定（向量：`top_k`+`threshold`；Token：`max_total` + 九模块键）
- 未完成项记录：
  - 无
- 备注：无（STEP-026）

---

### STEP-026：管理后台 Step5 / Step5.5 Prompt 编辑 + Step5.5 总开关（§2.7.9 / §2.7.1 B3）
- 完成时间：2026-05-07
- 状态：✅ 已完成
- 实现说明：主链 Step5 模块1 System 从 **`admin_config.config_key = step5_system_prompt`**（JSON `{"content": string}`）热加载，缺省回退 **`SYSTEM_PROMPT_TEXT`**（`prompt_builder._load_step5_system_template_raw`）；Step5.5 从 **`step5_5_prompt_fragments`** 六段合并默认后拼装（`step5_5_prompt_fragments.py` + `execute_step5_5` 内 `load_active_step5_5_fragments`）；**废弃**旧 **`prompt_modules`** 七模块管理接口；**`POST /api/admin/prompt/test`** 使用 **`build_chat_prompt`** + **`chat_with_step5_parse(..., is_test=true)`**，`use_draft` 时覆盖 Step5 System；总开关 **`step5_5_enabled`** 独立页发布（发布不要求先跑 LLM 测试）；RBAC **`super_admin` + `ai_trainer`**；发布校验 Step5 契约字段名与 Step5.5 占位符（`20025`）。
- 涉及文件：
  - `backend/services/prompt_builder.py`（Step5 System 热加载、`build_chat_prompt` 可选 `system_prompt_override`）
  - `backend/services/step5_5_prompt_fragments.py`（新增：默认六段、拼装、校验）
  - `backend/services/step5_5_service.py`（`build_step5_5_prompt` 支持片段、`load_active_step5_5_fragments`）
  - `backend/routers/admin/prompt_mgmt.py`（重写：Step5 / Step5.5 / 开关 / 测试）
  - `admin/pages/prompt.html`、`admin/pages/step5-5-switch.html`、`admin/static/js/admin-api.js`（菜单 `step55switch`）
  - `tests/test_step026_prompt_config.py`（新增）；`tests/test_prompt_builder.py`（mock `get_active_config`）
- 字段变更：无 DDL；**新增运行时约定键** `step5_system_prompt`、`step5_5_prompt_fragments`（`step5_5_enabled` 沿用 STEP-009）
- 测试结果：`pytest tests/test_step026_prompt_config.py tests/test_step5_5.py` 通过
- API / 接口契约：见本文档「模块：人格 / 情绪 / … / **Prompt**」整节；旧 **`prompt_modules`** 路径已删除
- 未完成项记录：无

---

## 契约对齐问题清单


| 问题描述                                                                                                                                                                                                                 | 涉及文件                                                                                                                                  | 建议修改                                                                                                       | 状态                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------- |
| 管理后台曾混用 `StandardResponse` 与 `ApiResponse`；业务接口已统一为 `**ApiResponse`**（`stats`/`system_monitor` 除外仍部分使用 `HTTPException` 表示参数错误）                                                                                       | `routers/admin/*.py`                                                                                                                  | 已与 H5 对齐信封；统计/监控参数错误后续可改为 `ApiResponse.fail` + `ADMIN_ERR_*`                                               | **已修复**               |
| **用户表 `users.relationship_level` / `growth_value` 与 `relationship` 表并行**：成长逻辑写读均以 `relationship` 为准；**Admin 用户列表/详情及用户报表等级分布**已改为 JOIN `relationship` 读 `Relationship.level` / `growth_value`。`users` 冗余列仍存，见 TD-001 | `models/user.py`, `models/relationship.py`, `routers/admin/users.py`, `services/stats_service.py`, `services/relationship_service.py` | 可选：移除 `users` 冗余列或单写源同步                                                                                    | **已修复（Admin 查询层）**    |
| ~~H5 `**GET /api/memory/list`** 与后台分页：列表字段 `**list`**、元素主键 `**id`** 已对齐~~（Admin：`/users`、`/users/.../conversations`、`/users/.../memories`、`/memories/global`、`/stats/report`、`/system/logs` 等）                       | `routers/admin/users.py`, `routers/admin/memory_mgmt.py`, `services/stats_service.py`, `routers/admin/system_monitor.py`              | 与用户端记忆列表约定一致                                                                                               | **已修复**               |
| ~~后台编辑用户记忆使用 `**request.json()` 手写 Body**，无 Pydantic 模型，与 H5 `MemoryUpdateRequest` 风格不一致~~                                                                                                                           | `routers/admin/users.py`, `schemas/memory.py`                                                                                         | 已使用 `AdminMemoryUpdateRequest`                                                                             | **已修复**               |
| `**backend/routers/user.py` 未挂载**：无 H5「个人资料」等独立接口；**已加文件顶占位注释**，需求确认前不挂载                                                                                                                                             | `main.py`, `routers/user.py`                                                                                                          | 产品确认后在本文件实现并 `include_router`                                                                              | **已修复（占位说明已补齐，暂不挂载）** |
| ~~Agent **凌晨关键词**仅有 **PUT**，无对称 **GET~~**                                                                                                                                                                            | `routers/admin/agent_mgmt.py`                                                                                                         | 已增加 **GET** `/api/admin/agent-night-keywords`，`get_active_config(..., use_cache=False)` 读 **admin_config** | **已修复**               |
| ~~**管理端用户详情页**将 `GET /users/{user_id}` 嵌套 `data` 直接赋给 `userData`，按扁平字段读取，导致 `status`、`relationship_level` 等为 `undefined`，状态与禁用/启用逻辑失效~~                                                                              | `admin/pages/user-detail.html`                                                                                                        | 在 `**loadUserDetail**` 内校验 `basic`/`relationship`/`activity` 并**展平**为 `userData`（字段映射见上模块说明）               | **已修复**               |
| H5 `**/api/relationship/history**` 与 `**/api/relationship/growth-log**` 数据源不同（Redis 今日汇总 vs MySQL 流水）；命名易混淆                                                                                                          | `routers/relationship.py`, `relationship_service.py`                                                                                  | 文档/接口命名区分（如 `today-summary` vs `growth-log`）                                                               | 待优化                   |
| 后台用户对话分页按 **created_at 升序**；H5 history 按 **倒序分页**；设计意图不同但字段结构略异（后台多 `persona_risk_flag`、`emotion_confidence`）；**STEP-011 后**一轮可对应 **多行** `role=assistant`，后台列表为逐行展平，**未**做同 `round_id` 聚合展示                                                                                                        | `routers/admin/users.py`, `routers/chat.py`                                                                                           | 保持差异则在前端契约中写清；若需对齐则加 query 参数或 Admin UI 聚合                                                                              | 已知差异                  |
| 鉴权：**H5 JWT** 与 **Admin JWT**（`type=admin`）密钥与 payload 不同，不可混用                                                                                                                                                       | `jwt_handler.py`, `admin_auth.py`                                                                                                     | 保持现状；客户端勿混用 Token                                                                                          | 符合设计                  |
| ~~**`admin_config.config_key` 单列 UNIQUE**~~：与草稿/多版本设计冲突，保存人格或 Prompt 草稿时 `INSERT` 触发 **1062** → 管理端 500                                                                                                                         | MySQL 索引 / `scripts/migrate_admin_config_config_key_nonunique.sql`                                                                 | 执行迁移去掉唯一、重建非唯一索引；见契约「表名：admin_config」                                                                  | **已修复（库侧须执行脚本）**    |
| **记忆规则 `importance_rules[].score`**：`MemoryRulesRequest` 中 `ImportanceRule.score` 仅为 `int`，**服务端未校验 1–4**；与 PRD/管理页约定（1–4 分）一致依赖前端与配置发布流程                                                                                    | `routers/admin/memory_mgmt.py`                                                                                                        | 可选：在 `ImportanceRule` 或 `update_memory_rules` 内增加 `Field(ge=1, le=4)` 或与产品对齐的区间校验                                      | 待修复                   |
| **向量库 `top_k`**：`VectorDbConfigRequest.top_k` 默认 5，**无上限 20 等校验**；管理页前端限制 1–20                                                                                                                                    | `routers/admin/memory_mgmt.py`                                                                                                        | 可选：Pydantic 增加 `le=20` 等与 UI 一致                                                                               | 待修复                   |
| ~~**`DiaryRulesRequest` 双 Prompt + 生成读配置**~~ | `relationship_mgmt.py`, `diary_service.py`, `scheduler.py`, `main.py`, `diary_rules_loader.py`, `diary-rules.html` | 已实现；PUT 支持双字段与 `generation_prompt` 兼容；调度 **UTC** | **已修复** |


---

## 需要优先修复的问题（按影响程度排序）

1. ~~`**users` 与 `relationship` 成长/等级字段双源不一致（Admin 展示）**~~ — Admin 列表/详情与用户报表等级分布已读 `relationship` 表；`users` 上冗余字段仍属技术债（TD-001），可选后续迁移移除。
2. ~~**管理后台响应信封混用**~~ — 业务接口已统一为 `ApiResponse`；`stats`/`system_monitor` 仍有个别 `HTTPException(400)`，可按需继续收敛。
3. ~~**分页列表字段命名不统一（`list` / `items`）及全局记忆 `memory_id` vs `id**`~~ — Admin 已与 H5 记忆/成长日志分页约定对齐（`list` + `id`）；H5 `messages` / `items` 等历史字段名见上文「字段命名规范」。
4. ~~**后台用户记忆更新无 Schema 校验**~~ — 已使用 `AdminMemoryUpdateRequest`，与 H5 风格对齐。
5. ~~**Agent 凌晨关键词缺少 GET**~~ — 已提供 **GET** `/api/admin/agent-night-keywords`。
6. `**user` 路由占位** — 已在 `user.py` 顶部补充 TODO；**未挂载**为有意为之，待产品确认个人资料接口后再实现。
7. ~~**用户详情页 `userData` 与嵌套接口未对齐**~~ — 已在 `loadUserDetail` 展平；契约见「管理后台用户管理」模块中 `**GET /users/{user_id}`** 与 `**userData` 展平** 条目。

---

*文档生成方式：扫描 `backend/main.py` 挂载路由、`backend/routers/**/*.py`、`backend/models/**/*.py`、`backend/schemas/**/*.py` 及核心 Service 返回值；未运行服务做运行时校验。*