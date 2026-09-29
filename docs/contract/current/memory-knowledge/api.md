# Memory Knowledge Api

- 文档 ID：`contract-memory-knowledge-api`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### 模块：H5 记忆（`/api/memory`）

> **长记忆第一套下线（PRD v1.3 一次发布）**：H5 记忆改为**只读**——`GET /api/memory/list` 改读 Step6 user 向量 KV；`PUT/DELETE/POST` 写路由**已删除**。记忆统一由对话 Step6 异步管线自动整理写入，H5 不再支持手动增删改（C-05/M9）。运行时**不过滤 `mem_*`**（P1，旧脏数据靠 M2 人工清理）。

> **H5 展示（2026-07-12 · 以页面实况为准）**：**`frontend/pages/memory.html`**（`body.memory-nebula-page`）为 **Three.js 真 3D 记忆星云**，**不**改本模块 HTTP/库表。
>
> - **脚本**：`/static/js/api.js` → **`three.min.js`（r149）** → **`three-line2.js`** → **`memory-connection-layer.js`** → **`memory-nebula.js`**
> - **顶栏**：返回（优先 `history.back` 当 referrer 为 index/chat，否则 → `/pages/chat.html`）；主标题 **「记忆星云」**；副标题 **`#nebula-count-subtitle`**「**N 颗记忆星体**」；右上 **`#nebula-tip`** 说明 Toast；**`#nebula-count-num`** 为 **hidden** 兼容锚点（可见计数以 subtitle 为准）
> - **场景**：全屏背景图 **`/static/images/memory-nebula/nebula-bg.jpg`** + WebGL；中心恒星贴图 **`core-star.png`**（节点 id **`core-memory`**）；卫星贴图按 `key` 首段分桶（teal/green/purple/pink/gold）；装饰背景星点 + 轨道环；**`MemoryConnectionLayer`** 绘制默认/选中关系线（Line2）
> - **交互**：自动慢转（`prefers-reduced-motion` 关闭）；单指环视；双指远近（半径 clamp **6～28**）；点选打开底部详情卡；**回到中心**；点选后选中高亮 + 关系线激活
> - **详情卡**：分类「她记得 · …」；标题 **`titleFromValue(value)`**（**不展示 key**）；正文 `value||content`；来源「来自你们的对话」；角标「长期记忆」。点中心核 →「她记得 · 记忆总览」+ 记忆条数文案
> - **空态**：浮层文案 +「去和她聊聊」→ `/pages/chat.html`（不遮挡可环视的中心核）
> - **废止**：卡片列表 DOM、`#memory-list`、顶栏「对话自动整理 · 只读」、顶栏主标题「她记得的你」、详情卡 `#nebula-sheet-key`、中心屏上「林小梦」字标
> - **静态锚点**：**`tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract`**

> **H5 展示（2026-07-11，已被上条覆盖）**：曾为 Canvas 2D 星云；现以 2026-07-12 Three.js + 表现层实况为准。

#### GET /api/memory/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ total, page, page_size, list: [{doc_id, key, value, content}] }`（**不再返回** `id`/`importance_score`/`source`）
- **数据源**：DashVector `list_by_filter(build_filter("user", user_id, []), top_k=USER_LIST_TOPK=500)`；`total`=cap 内条数（P9，非库内真实总数）
- **状态**：已实现（只读改造）
- **H5 消费**：记忆星云页 **`fetchAllMemories`** 分页拉齐后布局星点；首页记忆预览卡仍取 `page=1&page_size=1`（`value||content` 截断）

#### ~~PUT /api/memory/{memory_id}~~（已删除）

- **下线说明**：H5 写路由已移除（C-05），记忆由 Step6 自动整理，不支持手动修改。

#### ~~DELETE /api/memory/{memory_id}~~（已删除）

- **下线说明**：同上。

#### ~~POST /api/memory/add~~（已删除）

- **下线说明**：同上。`schemas/memory.py`（`MemoryAddRequest`/`MemoryUpdateRequest`/`AdminMemoryUpdateRequest`）已随之删除。

---

### 模块：向量召回与 Prompt Token 热配置（`/api/admin/configs`，STEP-025）

- **鉴权**：Bearer Admin JWT；GET 角色 **`super_admin` / `ai_trainer` / `observer`**，PUT 仍仅 **`super_admin` / `ai_trainer`**（`ops_admin` / `tech_ops` 等 → **HTTP 403**）。
- **GET** `/vector_retrieval_config` — 成功 `data`：`{ top_k, threshold }`（与 `multi_vector_retrieval_service` 默认 **TopK=3、阈值=0.7** 及库中已发布行合并后的**完整**对象，供管理端表单展示）。**不涵盖**：Step2 **2.5 补充路**触发条件中的 **`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`**（`count<2 OR max_score<0.75`，代码常量 **TD-027**）、补充路固定 **`top_k=3`**（C36）。
- **PUT** `/vector_retrieval_config` — Body：`{ "top_k"?: int, "threshold"?: float }`（均为可选，**至少提供其一**且不得为 `null`；**禁止**多余字段）。语义为 **PATCH**：与当前 `admin_config` 生效 JSON 及上述默认值合并 → **`admin_config_service.publish_config`** → MySQL 新版本 + Redis **`active_config:vector_retrieval_config`**。`top_k` 合法 **1–20**；`threshold` **0.0–1.0**。
  - 无任何有效更新字段 → **`20046`**（`ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`）。发布写入 **`admin_operation_log`**（`log_operation`，`module=ai_config`，`action=publish`，`target_description` 含配置键）。
- **GET** `/prompt_token_config` — 成功 `data`：`{ max_total, system, persona, character_knowledge, relationship, memory, emotion, time_activity, recent_chat, user_input }`（与 `prompt_builder` 默认上限及库中已发布行合并后的完整对象；**不含** `user_nickname`，该模块上限固定 **50** 且只读）。若历史库 JSON 含 `user_nickname` 键，**运行时 `_load_token_limits` 忽略**。
- **PUT** `/prompt_token_config` — Body：上列字段均可选，**至少其一**，整数下界 **1**（`max_total`/`system`/… 各自 Pydantic `ge=1`，`max_total` `le=50000`，模块单项 `le=20000`），**禁止**多余字段（**不可**提交 `user_nickname`）。PATCH 合并后整包发布，Redis **`active_config:prompt_token_config`**。
- **`build_filter(memory_type, user_id, candidate_keys)`**（`backend/utils/dashvector_client.py`）：统一构造 DashVector filter——`type = "{memory_type}"`（双引号）；可选 `AND user_id = {id}`；`candidate_keys` 每项按 `-` 拆分，**段数≥2** 时取前两段拼 **`key_l2 IN (...)`**（值内 `"` 转义为 `\"`），单层 Key 丢弃；**`search()`** 默认 `candidate_keys=[]` 内部调用；**`character_knowledge_service.list_entries`** 使用 `build_filter(mt, None, [])`。单测 **`tests/test_dashvector_client.py`**。
- **错误与 HTTP**：请求体非 JSON 或无法解析为对象 → **HTTP 422**；字段类型/范围违反 Pydantic → **422**；业务侧「空 PATCH」或合并后校验失败 → **信封 `code=20046`**（`message` 可含具体原因）。
- **关联表**：`admin_config`（`config_key` 分别为 `vector_retrieval_config`、`prompt_token_config`）；**Redis**：`active_config:{config_key}`，以及发布流程中的 `publish_monitor:{config_key}`（与既有 `AdminConfigService.publish_config` 一致）。
- **运行时消费**：Step2 `execute_multi_vector_retrieval` 与 `PromptBuilder._load_token_limits` 仍通过 `admin_config_service.get_active_config` 读取（见 STEP-020 / STEP-021 契约摘要）；本模块仅提供管理端读写入口。
- **管理端页面**：`admin/pages/vector-token-config.html` — Tab「向量召回」「Prompt Token」；`admin-api.js` 菜单键 **`vector-token`**（`super_admin` 与 `ai_trainer` 的 `MENU_CONFIG`）；保存时脚本对比首屏快照，**仅提交有变化的字段**以契合 PATCH 语义。
- **状态**：已实现

---

### 模块：记忆与向量（管理）

> **长记忆第一套下线（PRD v1.3）**：旧 **`GET/PUT /memory-rules`** 已删除（C-02/C-08：`memory_rules` 后台不展示、不提供 API，历史配置行仅保留库内不读取）；改为 **`GET/PUT /step6-memory-prompt`**。`memories/global` 改向量检索、`batch-delete` 改按 `doc_ids`。本系列权限 **`super_admin` / `ai_trainer`**（P5）。运行时**不过滤 `mem_*`**（P1）。
- **GET** `/step6-memory-prompt` — 成功 `data` 为当前生效 Step6 记忆 Prompt 6 块结构；**无生效配置时返回 DEFAULT**（`STEP6_PROMPT_DEFAULT`，逐字复刻旧硬编码，P6）。6 块：`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields`（dict，**恰好 11 项**，key/顺序同 `_ALL_FIELD_NAMES`）/ `merge_rules` / `few_shot_example`。
- **PUT** `/step6-memory-prompt` — Body `Step6MemoryPromptRequest`（6 块）：5 个文本块非空 + `task_fields` 恰含 11 个 key 且各项非空（C-10 Pydantic 必填校验，不做 persona 测试集 / CONFIRM 门禁）；**保存即发布**（`publish_config` 更新 MySQL+Redis `active_config:step6_memory_prompt`，~100ms，免重启），写 `admin_operation_log`。运行时由 `memory_llm_service.build_step6_prompt`（已 `async`）三级回退 Redis→DB→DEFAULT 读取；动态注入区块（时间/人格/关系/历史/本轮对话）**不可配置覆盖**。
- **GET** `/vector-db-config` — 成功 `data`：`endpoint`、`collection_name`、`top_k`、**`api_key_masked`**（脱敏，不含明文 `api_key`）；无 DB 配置时回退读环境变量并同样返回 `api_key_masked`。
- **PUT** `/vector-db-config` — Body `VectorDbConfigRequest`：`endpoint`、`collection_name`、`top_k`（Pydantic 默认 5，**无 1–20 上限校验**）；`api_key` 可选（不传则保留库内原值）；`need_test_first`（bool，**为 `true` 时保存前会先测连**，失败则拒绝保存）。管理页保存可传 `need_test_first:false`，依赖前端「先测后存」。
- **POST** `/vector-db-config/test-connection` — Body `VectorDbTestRequest`（字段均可选）：`endpoint`、`collection_name`、`api_key`；缺省时从已发布配置或环境变量补全。成功 `data`：`connected`（bool）、`latency_ms`、`error`（字符串）。
- **GET** `/memories/global` — 全局用户记忆检索（Step6 user 向量，**仅 type=user，不含 character_private**，§6.4.1）。Query：`keyword`、`user_id`（**可选**）、`page`、`page_size`（**移除** `start_date`/`end_date`/`source`）。有 `user_id` → `top_k=USER_LIST_TOPK=500`（P4）；无 → `top_k=GLOBAL_LIST_TOPK_NO_USER=300`（R-01/P4）。`keyword` 先 `list_by_filter` 再内存子串过滤（key/value/content）后分页。`data`：`{ total, page, page_size, list:[{doc_id, user_id, key, value, content}] }`；**未传 `user_id` 且候选命中上限（==300）时附 `truncated: true`**（R-01）。
- **DELETE** `/memories/batch-delete` — Body `BatchDeleteRequest`：`{ doc_ids: list[str] }`（min 1 / max 100，P8）。逐条校验「以 `user_` 前缀 + `parse_doc_id` 合法」，非法计入 `failed_doc_ids` 不中断；合法项 `dashvector_client.delete` 累加 `deleted_count`；仅删 DashVector（不走 MySQL）；「涉及用户」从 `user_suffix` 聚合写入 `log_operation`（module 仍用 `memory`）。`data`：`{ deleted_count, failed_doc_ids }`。
- **状态**：已实现（长记忆第一套下线改造）

---

<a id="last-write-source"></a>
### 向量最后写入来源

user / character_private向量文档增加内部溯源字段`last_write_source`，值为`voice|text|admin|unknown`，表示当前版本的最后写入渠道。语音/文字/管理写入分别写对应值；缺失或非法值读取为unknown，**不把旧数据一律补成text**。该字段保存在向量库，不是MySQL列，不修改Stable Key、doc_id、相似度排名或四路检索配额，也不代表这条记忆全部历史事实都来自最后一次渠道。仅溯源，不扩展本页既有H5公开响应字段；逐轮语音任务与trace见[语音数据](../realtime-voice/data.md#memory)。
