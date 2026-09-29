# Persona Api

- 文档 ID：`contract-persona-api`
- 权威状态：`canonical`
- 功能范围：`persona-prompt-world-state`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-002`, `TD-003`, `TD-020`, `TD-021`

### 模块：角色知识库（`/api/admin/character-knowledge`，STEP-027 / R-L1L3-20）

- **鉴权**：Bearer Admin JWT；GET 角色 **`super_admin` / `ai_trainer` / `observer`**，POST/PUT/DELETE 仍仅 **`super_admin` / `ai_trainer`**（其余 → **HTTP 403**）。
- **存储**：**仅 DashVector**（无 `admin_config`、无 MySQL 镜像表）；与 Step6 `upsert_step6_vectors` 共用 **`doc_id`** 与 **`fields.content`** 约定。
- **doc_id 格式**：`{memory_type}_{sha256(key)[:12]}_{user_suffix}`（DashVector 合法字符；`user_suffix` 角色级为 **`0`**，用户级为 **`user_id`**，如 `character_global_a3f8c2e91b04_0`）。**不再**使用冒号分隔的旧格式。
- **key 格式**：强制三层 **`XXX-XXX-XXX`**（恰好两段半角 `-`）；非法 key（含两层 `外貌-体态`、无连字符 `真实姓名`）在 Step6 写入与后台 POST 时**拒绝/丢弃**。
- **Embedding**：新增/改 **value** 时对 **value 文本** 调用 `embedding_service.get_embedding`（与 Step6 一致，非整行 `key：value`）。
- **fields**：`content` = `key` + 全角冒号 `：` + `value`；**`stable_key`** = key 原文（供列表展示与 keyword 匹配）；**`key_l1`**（一级 Key，如 `外貌`）与 **`key_l2`**（二级 Key，如 `外貌-体态`，供 Step2 主路 `key_l2 IN` 结构化过滤）由写入路径补齐（Step6 `upsert_step6_vectors` 与 Admin `_build_knowledge_fields` 共用，四类均写，C9/C15，见「2026-05-30 摘要」）；`type` 由 `dashvector_client.upsert` 合并写入；`user_id` 仅 `character_private` / `user`（Step6 自动写入，后台不可管）。
- **DashVector upsert**：HTTP 2xx 后若响应 `message` 含 `failed operation` / `is invalid` 视为失败（避免 doc_id 非法时误报成功）。
- **GET** `/character-knowledge` — Query：`type`（可选，`character_global` | `character_knowledge`）、`keyword`（可选，子串匹配 key 或 value）、`page`（默认 1）、`page_size`（1–100，默认 20）。成功 `data`：`{ total, page, page_size, list }`；`list[]`：`doc_id`, `type`, `key`, `value`, `content`。列表含 **Step6 自动写入** 的同 type 条目；每类 filter 查询 `topk=500` 后内存分页与 keyword 过滤（条目极多时最多展示约 500/类）。
- **POST** `/character-knowledge` — Body：`{ "type", "key", "value" }`（均必填）。`type` 仅两枚举；**`key` 须三层 `XXX-XXX-XXX`**，CJK 计数 ≤20，每段允许汉字/数字/英文/`-`/`_`，禁止全角 `：`；`value` CJK ≤100。同 `type+key`（hash 相同）已存在 → **`20050`**。Embedding 空或 upsert 失败 → **`20052`**。成功 `data` 为单条对象（字段同 `list[]`）。
- **PUT** `/character-knowledge/{doc_id}` — 路径参数须 **URL 编码**；**key 不可改**，Body 仅 `{ "value" }`。`doc_id` 须为可管理的角色级条目（`character_global` / `character_knowledge` 且 `_0` 后缀），禁止操作 `character_private` / `user`。不存在 → **`20051`**；校验/向量失败码同 POST。
- **DELETE** `/character-knowledge/{doc_id}` — 同上路径规则；成功 `data`：`{ "doc_id" }`。
- **审计**：POST/PUT/DELETE 写入 `admin_operation_log`（`module=character_knowledge`，`action` 为 `create` / `update` / `delete`）。
- **DashVector 客户端扩展**：`list_by_filter(filter, topk)`（仅 filter 查询）、`fetch_by_ids(ids)`（按 id 拉取）。
- **管理端页面**：`admin/pages/knowledge.html` — 顶栏「角色知识库」；`activeKey=knowledge`；内嵌 **demo 格式提示**；类型筛选 + 关键词；表格 CRUD；编辑态 **key/type 只读**；菜单 `admin-api.js` **`📚 角色知识库`**（`super_admin` / `ai_trainer`）。
- **不在范围**：`character_private` 维护、批量导入。
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
  - **Step5 System**：`GET /api/admin/prompt/step5`（`data`：`version`、`has_draft`、`content`、`baseline_is_builtin`）；`GET /api/admin/prompt/step5/draft`；`PUT /api/admin/prompt/step5/draft` Body `{ "content": string }`；`DELETE /api/admin/prompt/step5/draft`；
    - `POST /api/admin/prompt/step5/publish` Body `confirm_text`、`test_passed`（发布前校验 Step5 JSON 契约字段名子串：`inner_monologue`、`messages`、`relation_change`、`future`、`emotion`、`knowledge_expand`）；`GET /api/admin/prompt/step5/history`、`GET /api/admin/prompt/step5/history/{version}`、`POST /api/admin/prompt/step5/rollback`。
  - **Step5.5 六段**：`GET /api/admin/prompt/step5-5/fragments`（`data.fragments`、`fragment_keys`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5/draft`；`PUT /api/admin/prompt/step5-5/draft/{fragment_key}` Body `{ "content": string }`（`fragment_key` 限于六键）；`DELETE /api/admin/prompt/step5-5/draft`；`POST /api/admin/prompt/step5-5/publish`（占位符与 system 段契约关键词校验）；`GET /api/admin/prompt/step5-5/history`、`GET .../history/{version}`、`POST .../rollback`。
  - **Step5.5 总开关**：`GET /api/admin/prompt/step5-5-switch`（`enabled`、`draft_enabled`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5-switch/draft`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ "enabled": bool }`；`DELETE .../draft`；`POST .../publish` Body `confirm_text: CONFIRM`（**不要求**先跑主链 LLM 在线测试；可与 `test_passed` 一并提交）；`GET .../history`、`POST .../rollback`。
  - **在线测试**：`POST /api/admin/prompt/test` — Body：`test_input`（必填）、`relationship_level`（0–3）、`emotion_label`、`mock_memories`（字符串数组）、`use_draft`（bool，为 `true` 时用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致，LLM **`chat_with_step5_parse(..., is_test=true)`**；成功 `data`：`full_prompt`、`ai_reply`（`messages[].content` 合并）、`persona_match`、`content_safety`、`token_estimate`。
- **对话流 Prompt 只读展示**（实现见 `backend/routers/admin/chat_prompt_view.py` + `backend/services/chat_prompt_view_service.py`；鉴权 **`super_admin` / `ai_trainer`**；**无**草稿/发布/写库）：
  - **GET** `/api/admin/chat-prompt-view/step15` — Step1.5 查询重写模板；`data`：`readonly`、`title`、`description`、`source_file`、`variants[]`（`key=main|step8`，`content` 为占位符拼装全文，与 `_build_step1_5_prompt` 同源）。
  - **GET** `/api/admin/chat-prompt-view/step3` — Step3 拼装规则；`data`：`module_order`、`trim_priority`、`empathy_rules`、`emotion_mapping`、`level_definitions`、`silence_corrections`（与 `prompt_builder` 常量同源）。
  - **GET** `/api/admin/chat-prompt-view/step8` — Step8【主动发起】模板；`data.proactive_input_template` = `STEP8_PROACTIVE_INPUT_TEMPLATE`（含 `{{future_action}}`）。
  - **GET** `/api/admin/chat-prompt-view/agent` — Agent P0～P4 任务指令；`data.triggers[]`（`key`/`task_instruction`/`full_task_block`）与 `ACTIVE_TRIGGER_INSTRUCTIONS` + `AGENT_TASK_OUTPUT_SUFFIX` 一致。
  - **页面**：`chat-prompt-step15.html` / `chat-prompt-step3.html` / `chat-prompt-step8.html` / `chat-prompt-agent.html`；侧栏 `CHAT_PROMPT_MENU`（见管理端页面节）。
- **安全**（`backend/routers/admin/safety_rules.py`，前缀 `/api/admin`）：
  - **GET** `/safety-rules` — 成功 `data`：`banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords`、`crisis_keywords`（均为 `string[]`，无对应有效配置时为空数组）；`crisis_keywords` 取已发布数据库配置。另返回只读 `crisis_keywords_status`：`publication_status`（`published` / `unpublished` / `invalid` / `unavailable`）、`active_version`（可空）、`keyword_count`、`cache_status`（`healthy` / `missing` / `invalid` / `unavailable` / `out_of_sync`）、`fallback_ready`。状态检查不写入缓存；`fallback_ready` 仅表示存在有效已发布危机词，不能代表语音通话的其他依赖均可用。
  - **PUT** `/safety-rules/banned-keywords` — Body：`{ "keywords": string[] }`（Pydantic `KeywordsUpdateRequest` 只校验为字符串数组；页面另阻止提交空列表）。
  - **PUT** `/safety-rules/persona-keywords` — 同上。
  - **PUT** `/safety-rules/style-keywords` — 同上。
  - **POST** `/safety-rules/banned-keywords/import` — `multipart/form-data`，字段名 **`file`**（`.xlsx` / `.xls`）；与现有违禁词合并去重后发布。成功 `data`：`imported_count`（本次从表格读取到的非空行数）、`total_count`（合并去重后的词库总数）。
  - **PUT** `/safety-rules/crisis-keywords` — Body `{ "keywords": string[] }`；危机词须通过规范化校验且发布结果非空，成功即生成生效版本。**GET** `/safety-rules/crisis-keywords/history` — `page`（默认 1）、`page_size`（默认 20，1–100）查看版本。**POST** `/safety-rules/crisis-keywords/rollback` — Body `{ "version": 正整数, "confirm_text": "CONFIRM" }`，将所选历史内容发布为新版本。三接口分别返回 `ApiResponse`；发布和回滚失败按服务端错误码返回。
  - **权限**：安全规则读取及危机词历史允许 `super_admin`、`ai_trainer`、`observer`；写入、发布与回滚只允许 `super_admin`、`ai_trainer`。语音通话对危机词的运行时读取及无有效配置时的新建门禁，见[语音当前契约](../realtime-voice/data.md#safety)。
- **测试用例**：`GET|POST /test-cases/{config_key}`；`DELETE /test-cases/{config_key}/{case_id}`。**POST Body**（`TestCaseCreateRequest`）：`input`（必填）、`expected_pass_criteria`（必填）、`emotion_label`（默认 `平静`）、`relationship_level`（默认 `1`，0–3）。成功 `data`：`case`、`total_count`，并与 `publish_config` 成功回执字段合并返回。
- **响应**：`ApiResponse`
- **关联表**：admin_config（及部分 Redis）
- **状态**：已实现

---
