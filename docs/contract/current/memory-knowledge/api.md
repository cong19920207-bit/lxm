# Memory Knowledge Api

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


- 文档 ID：`contract-memory-knowledge-api`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### 模块：H5 记忆（`/api/memory`）

> **长记忆第一套下线（PRD v1.3 一次发布）**：H5 记忆改为**只读**——`GET /api/memory/list` 改读 Step6 user 向量 KV；`PUT/DELETE/POST` 写路由**已删除**。记忆统一由对话 Step6 异步管线自动整理写入，H5 不再支持手动增删改（C-05/M9）。运行时**不过滤 `mem_*`**（P1，旧链历史清理说明；本轮新目标激活/S15须遵从[当前工具与环境边界](#memory-maintenance-and-backfill)，未执行业务清理）。

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
- **GET** `/vector_retrieval_config` — 当前四路完整 `routes`、只读审计 `legacy`、`version/source/server_time`，默认20/20/8/0.1；字段边界及来源见[有效配置](#memory-config-publication)。旧保留消费者的 TopK=3/threshold=0.7 及2.5补充路 count<2 OR max_score<0.75、固定top_k=3/TD-027保持，不进入新文字链。
- **PUT** `/vector_retrieval_config` — 只dirty四路合法字段，合并校验后持久发布；拒未知/null/空更新。API输入、默认、组合校验、UUIDv7/unknown回执和DB后缓存见[有效配置](#memory-config-publication)。原操作日志保留module=ai_config/action=publish且不含凭据。
- **GET/PUT** `/prompt_token_config` — GET含固定只读 `user_nickname=50` 与完整有效预算、版本/来源/UTC时钟；PUT不得提交nickname，范围和单模块≤总量由[有效配置](#memory-config-publication)规定。昵称原文不按50裁剪但完整计数；旧helper不替代新链冻结预算。
- **`build_filter(memory_type, user_id, candidate_keys)`**（`backend/utils/dashvector_client.py`）：统一构造 DashVector filter——`type = "{memory_type}"`（双引号）；可选 `AND user_id = {id}`；`candidate_keys` 每项按 `-` 拆分，**段数≥2** 时取前两段拼 **`key_l2 IN (...)`**（值内 `"` 转义为 `\"`），单层 Key 丢弃；**`search()`** 默认 `candidate_keys=[]` 内部调用；
  - **`character_knowledge_service.list_entries`** 使用 `build_filter(mt, None, [])`。单测 **`tests/test_dashvector_client.py`**。 新文字链CandidateKeys仅协议提示，不作为跳过当前源/归属校验的豁免；该helper保留给原消费者，见[检索协议](#memory-retrieval-protocol)。
- **错误与 HTTP**：请求体非 JSON 或无法解析为对象 → **HTTP 422**；字段类型/范围违反 Pydantic → **422**；业务侧「空 PATCH」或合并后校验失败 → **信封 `code=20046`**（`message` 可含具体原因）。
- **关联控制表与消费**：admin_config保留配置JSON，memory_config_head/publish记录canonical head/原actor发布回执；DB确认后缓存，Redis热键不替代提交锚点。新文字链一次冻结EffectiveMemoryConfig，旧execute_multi_vector_retrieval/Token helper仅保留消费者；见[有效配置](#memory-config-publication)与[控制表](data.md#schema-memory_config_head)。
- **管理端页面**：`admin/pages/vector-token-config.html` — Tab「向量召回」「Prompt Token」；`admin-api.js` 菜单键 **`vector-token`**（`super_admin` 与 `ai_trainer` 的 `MENU_CONFIG`）；保存时脚本对比首屏快照，**仅提交有变化的字段**以契合 PATCH 语义。
- **状态**：已实现

---

### 模块：记忆与向量（管理）

> **长记忆第一套下线（PRD v1.3）**：旧 **`GET/PUT /memory-rules`** 已删除（C-02/C-08：`memory_rules` 后台不展示、不提供 API，历史配置行仅保留库内不读取）；改为 **`GET/PUT /step6-memory-prompt`**。`memories/global` 改向量检索、`batch-delete` 改按 `doc_ids`。本系列权限 **`super_admin` / `ai_trainer`**（P5）。运行时**不过滤 `mem_*`**（P1）。
- **GET** `/step6-memory-prompt` — 成功 `data` 为当前生效 Step6 记忆 Prompt 6 块结构；**无生效配置时返回 DEFAULT**（`STEP6_PROMPT_DEFAULT`，逐字复刻旧硬编码，P6）。6 块：`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields`（dict，**恰好 11 项**，key/顺序同 `_ALL_FIELD_NAMES`）/ `merge_rules` / `few_shot_example`。
- **PUT** `/step6-memory-prompt` — Body `Step6MemoryPromptRequest`（6 块）：5 个文本块非空 + `task_fields` 恰含 11 个 key 且各项非空（C-10 Pydantic 必填校验，不做 persona 测试集 / CONFIRM 门禁）；**保存即发布**（`publish_config` 更新 MySQL+Redis `active_config:step6_memory_prompt`，~100ms，免重启），写 `admin_operation_log`。运行时由 `memory_llm_service.build_step6_prompt`（已 `async`）三级回退 Redis→DB→DEFAULT 读取；动态注入区块（时间/人格/关系/历史/本轮对话）**不可配置覆盖**。
- **GET/PUT** `/vector-db-config`、**POST** `/vector-db-config/test-connection` — GET返回许可公开配置/版本/来源、legacy TopK只读及凭据配置状态；PUT VectorDbConfigRequest仅endpoint/collection_name/api_key可选dirty字段，禁止top_k/need_test_first与未知字段，后端按canonical provider发布并测连。test可省略字段或null以使用解析配置组，公开connected/latency_ms/安全error；固定新目标和来源/回执规则见[有效配置](#memory-config-publication)。observer不返回掩码片段。
- **GET** `/memories/global` — 全局用户记忆检索（Step6 user 向量，**仅 type=user，不含 character_private**，§6.4.1）。Query：`keyword`、`user_id`（**可选**）、`page`、`page_size`（**移除** `start_date`/`end_date`/`source`）。有 `user_id` → `top_k=USER_LIST_TOPK=500`（P4）；无 → `top_k=GLOBAL_LIST_TOPK_NO_USER=300`（R-01/P4）。`keyword` 先 `list_by_filter` 再内存子串过滤（key/value/content）后分页。
  - `data`：`{ total, page, page_size, list:[{doc_id, user_id, key, value, content}] }`；**未传 `user_id` 且候选命中上限（==300）时附 `truncated: true`**（R-01）。 当前列表还附generation/index_state/legacy_read_only并核当前SQL归属/代/hash/墓碑；此cap读取算法保持，不证明全来源，见[当前写回执](#memory-write-receipts)。
- **DELETE** `/memories/batch-delete` — Body `{doc_ids}`仍1～100，user-only稳定去重；父及合法子项触网前持久，源确认/索引分态，原operation重放仅核实未决，未知不再删。保留deleted_count/failed_doc_ids、涉及user溯源及原操作日志，新增source_counts/index_counts与逐项状态；见[批量写回执](#memory-write-receipts)。
- **状态**：已实现（长记忆第一套下线改造）

---

<a id="last-write-source"></a>
### 向量最后写入来源

user / character_private向量文档增加内部溯源字段`last_write_source`，值为`voice|text|admin|unknown`，表示当前版本的最后写入渠道。语音/文字/管理写入分别写对应值；缺失或非法值读取为unknown，**不把旧数据一律补成text**。该字段保存在向量库，不是MySQL列，不修改Stable Key、doc_id、相似度排名或四路检索配额，也不代表这条记忆全部历史事实都来自最后一次渠道。仅溯源，不扩展本页既有H5公开响应字段；逐轮语音任务与trace见[语音数据](../realtime-voice/data.md#memory)。

---

<a id="memory-implementation-boundary"></a>
### 本轮实现与环境边界

本节记载工作区已实现、在自有隔离环境验证的增量。2026-10-13本地Docker业务环境`local-docker:lxmfor`已完成S15并开放epoch2，运行于新库`local_test_collection`；旧库和旧隔离分区已退役且不复用名称。实际验证及版本见唯一STEP §3.39。M8 的 cg=0.18/user=0.15 是隔离评测候选，共享默认仍为0.1；内置 System 修复不覆盖合法 active/draft/显式 override。AC19/AC20 原失败和未齐质量对照按最新用户决定作为本阶段非阻断风险保留，不能据功能通过宣称质量全通过。最终 M8/GATE-D 与实际部署状态见唯一 STEP §3。

<a id="memory-config-publication"></a>
### 有效配置与持久发布

四路固定为 `cg/cp/ck/user`。每路完整配置为 `{dense_top_k,bm25_top_k,final_top_k,rerank_min_score}`；前三者为严格整数1～50，`final_top_k≤dense_top_k+bm25_top_k`，门槛为有限非布尔0～1。缺历史发布时默认20/20/8/0.1；历史 `legacy.top_k/threshold`仅只读审计，不进入新文字链。GET `/api/admin/configs/vector_retrieval_config` 返回完整 `routes`、`legacy`、`version/source/server_time`；PUT只提交dirty路/字段，严格拒未知字段、显式null和空更新，经合并后组合校验。

Token配置GET `/api/admin/configs/prompt_token_config`返回完整冻结预算与版本/来源/UTC时钟，含固定 `user_nickname=50`。PUT只允许 `max_total/system/persona/character_knowledge/relationship/memory/emotion/time_activity/recent_chat/user_input`；总量1024～32768，recent_chat 1～16384，其余可编辑模块1～8192，单模块不得超过总量。nickname不可提交。非法/空组合20046，结构校验422；合法昵称正文不因超过50裁剪，仍计入完整Prompt。

两个向量配置入口（本模块 `/api/admin/vector-db-config`与第三方 `dashvector`）共用 `vector_db_config` canonical head；embedding/rerank分别为 `third_party:embedding`和`third_party:rerank`。输入、已发布JSON及显式允许的初始环境来源按组解析，不在字段/HTTP适配层隐式换来源；已发布坏配置/读取失败不改用默认。rerank未发布时必须显式设置`ALIYUN_RERANK_ENDPOINT`和`ALIYUN_RERANK_MODEL`，代码不默认接口或模型；可选`ALIYUN_RERANK_API_KEY`留空复用`ALIYUN_ACCESS_KEY_ID`中的百炼凭据。已发布配置仍优先。`EffectiveMemoryConfig`一次冻结 retrieval/prompt/provider版本、来源与凭据handle、目标指纹、encoder/统计/语料摘要、reply model、官方counter和阶段参数，rerank profile的model与本次有效provider一致。preview没有active epoch；active resolver校验fence，不负责激活。

发布可选规范小写 UUIDv7 `Idempotency-Key`，缺省由服务器生成。actor+发布ID+原输入摘要首次持久登记，先DB确认再更新缓存；重复原ID/摘要复读原结果，冲突20121、首次时间窗过去120秒/未来30秒、过窗20123、revision冲突20127、依赖不可读20129、未知提交20122。同次未知不能由更晚active版本推成功，保留原ID查询。

`GET /api/admin/configs/publications/{publish_id}`是本人原发布回执，只读且重新检查原来源当前角色。DTO为 `publish_id/canonical_key/source_entry/commit_state/committed_version/observed_at/reason/server_time`；committed_version仅confirmed committed时给值。对外状态 `pending/unknown/committed/rejected/expired`，内部accepted/validating按owner lease投影；pending/unknown返回20122、expired20123、不存在20125。

第三方原入口允许S/T/V读，召回/Token及向量原入口允许S/A/V读；不借该GET跨角色域。控制结构见[data](data.md#schema-memory_config_head)，角色见[共享矩阵](../_shared/auth-rbac.md#memory-role-matrix)。

<a id="memory-write-receipts"></a>
### 当前正文写入、CRUD与自有回执

`MemoryBusinessWriter`要求服务器 `MEMORY_RUNTIME_ENVIRONMENT_ID`与已验证新目标fence；缺失20126/runtime_environment_missing。一次冻结writer、目标/epoch/encoder/配置版本，恢复不能借新版本重发旧payload。四类Admin CRUD、文字Step6、语音user/private及合法旧mem正文均经持久 `prepare→dispatch/reconcile`；可信actor、完整intent、同identity单在途、更新/墓碑/同ID重建generation单调。源确认与派生索引ready分别判断，不因索引pending重复提取、关系副作用或源写。

<a id="step6-diagnostic-logs"></a>
**Step6诊断日志（内部观察）**：`execute_step6`每次尝试结束时以INFO汇总一条`step6_diagnostic`事件，关联`user_id/round_id/attempt`及执行阶段；writer初始化失败也记录对应阶段并保持原异常传播。诊断采集或日志输出失败不改变原返回、异常、取消和重试行为；该事件不新增公开API或持久业务状态。

四类KV字段按解析所得JSON、在原默认值/类型转换前区分`input_state=explicit_none/missing/null/empty/non_string/text`；仅字段存在且原值为去首尾空白后等于“无”的字符串时记`explicit_none`，不能把缺字段或默认回填算作LLM明确返回“无”。摘要分别统计解析行、有效KV、格式/Key校验丢弃原因及写入尝试；整体JSON解析失败由阶段和异常类型定位，不推断字段返回“无”。

写入按已有回执分别观察`source_result/index_result`，保留可得的`doc_id/ordinal/generation/internal_operation_id`；源`pending/unknown`不归为已确认失败，源`confirmed`也不等于索引`ready`。等待写入期间取消且未取得回执时仅记`unobserved/receipt_not_observed`，未知代次/操作ID为空；`unobserved`只表示本次未观察到回执，不扩展持久状态枚举，也不触发额外核实或重写。`relationship_result=committed`仅在实际提交后记录；未到达、已开始和缺记录跳过分别为`not_reached/started/skipped_missing`。尝试`completed`或原任务`done`不代表所有候选写入成功或索引已就绪。

新增摘要仅记录元数据、白名单原因和异常类型，不记录Prompt、LLM原文、Key/Value、凭据或任意异常正文；并发轮次的诊断上下文隔离。原六块Prompt、11字段解析/默认值、KV提取、四路写入身份、源/索引判断及关系更新逻辑保持，`output`协议边界不变。

2026-10-15本地Docker部署与验收：镜像`lxm_for-backend:step6-diagnostic-20261015-199c731343f7`在doc_op修复镜像上仅叠加两个Step6服务模块，原运行配置及向量适配器保持。经明确授权的两轮合成对话分别观察到私有字段`explicit_none`且零写入，以及有效私有约定源`confirmed`、索引从`pending`自动到`ready`；不据此归因历史缺失原因，历史未知记录未处理。镜像摘要、回滚镜像、文件哈希及两轮实际结果见本地部署与验收证据（仓库忽略文件）（本地留存，未随本次提交；原引用：`../../../../data/runtime-checks/step6-diagnostics-20261015.json`）的`local_docker_deployment/runtime_diagnosis`。

原Stable Key、同Key创建冲突、value-only编辑、请求体和成功字段保持；写入可选规范小写UUIDv7 `Idempotency-Key`，无Header兼容内部UUIDv4。非法Header422先于副作用；同ID不同内容20121、首次窗20123，unknown仅核实原tag，不换ID重发。成功原code0附 `write_result`；源pending/unknown为20122，索引pending单独展示。

后台首次新增的存在性预检：通用HTTP fetch成功但缺`output`仍为unknown，仅内部原因细分为`read_output_missing`。只有尚无原持久操作的create分支遇到此原因，才追加一次独立gRPC只读核实；沿用冻结provider凭据、同一cluster/collection/partition/doc_id，校验SDK返回的集合名称，拒绝改变目标的URL路径及SDK明文传输覆盖。只有成功码严格为整数0、有效request_id及明确空文档字典才可继续原prepare/dispatch；非空、异常、超时或容量已满仍返回20129，不生成写入intent。核实总截止5秒覆盖SDK初始化、集合读取与fetch，每次RPC上限1.5秒，每进程最多4个并行核实且不排队、不自动重试；超时/取消后的实际线程退出前继续占槽，迟到结果不推进写入，并释放底层连接。原目标fence、同identity单在途和幂等保护继续执行；更新/删除/批量、未知操作对账、写后确认和索引核实不使用此路径。该增量于2026-10-14完成工作区代码与隔离验证，随后已获准部署到local-docker:lxmfor并完成下述真实验收；未恢复积压。

此次代码验证：新增63项与相关回归210项合计273项通过，另16个子用例通过。覆盖真实Admin路由/隔离SQLite控制表、受控HTTP响应及已安装SDK1.0.23的真实Client/get/fetch与protobuf解析（仅替换RPC传输，无远端访问），以及超时零写、幂等、并发在途保护、目标切换和原未知对账。测试进程使用空`MEMORY_RUNTIME_ENVIRONMENT_ID`隔离本机运行环境，目标/身份保护由隔离fixture显式提供；未改变应用运行配置。部署前本轮重跑新增63项全部通过；此前273项组合回归及16个子用例结果沿用，真实运行证据另列如下。

2026-10-14实际部署与验收：本次修改已在main工作区，保留全部既有改动；以原运行镜像为基底，仅叠加`memory_vector_client.py`、`admin_memory_write_service.py`和新`memory_create_verifier.py`，镜像标签`memory-create-20261014`（摘要`18bc44b0b00b573009e1a8cff76de86b27571b9dd4aa07d761b0abac0ef4dab1`），回滚镜像`lxm-index-rollback:20261014`。运行环境、端口和挂载逐项相同。真实浏览器点击后台新增并保存一次，返回code0/source succeeded（约1.75秒），随后约4.05秒自动index ready，索引attempt1/round0；远端dense1024、sparse9项及generation/body hash/encoder/操作tag/归属均匹配。用户页与全局页的新条目无待修复警告，旧条目显示本轮超时/需人工处理/尝试0次，维护链接可读，浏览器无脚本错误。临时验收记忆已按正常DELETE协议删除并确认远端墓碑、列表移除。部署前86条任务在验收及清理后逐条未变，其中82条manual任务attempt/round均0；不将上一轮83条数量视为本轮基线。另对未写入ID只读实测：通用fetch仍为unknown/read_output_missing，同冻结目标的专用gRPC核实成功，零写入。脱敏证据见仓库忽略文件`data/runtime-checks/memory-create-20261014.json`。

2026-10-14后续获准小批恢复：以87条任务、其中82条manual为本次基线，只选择3条符合`retry_eligible`且无在途未知操作的user任务，通过原后台重试API携带当前revision及独立UUIDv7逐条执行；每条确认成功后才提交下一条，没有重复提交或直接修改控制表。3条均在round1/attempt1完成（约4.84、1.71、5.27秒），远端稀疏项从0变为11、13、8；只读回查确认原正文/业务字段、dense1024向量、generation及源操作未变，索引操作tag、冻结encoder版本及重算稀疏权重匹配。真实浏览器核对用户页、全局页均无待修复警告，维护页为completed/ready且重试按钮禁用；剩余条目仍正确显示本轮超时及尝试0次。恢复前后逐项比对：其余84条任务、未选identity及无关operation均未变，仅新增3个retry和3个index操作，fence未变；剩余79条manual仍round0/attempt0，等待用户另行确认，不继续恢复。未改应用代码、配置、通用远端核实或未知操作对账规则。脱敏证据及截图见仓库忽略文件`data/runtime-checks/memory-backlog-pilot-20261014.json`。

2026-10-14剩余积压分批恢复：用户后续授权继续恢复上述79条，每批正常后才继续、遇异常立即暂停。实际按10/10/10/10/10/10/10/9共8批执行，包含user41、character_global30、character_knowledge8；每条只提交一次原后台重试请求，均round1/attempt1完成。每条严格只读回查源数据、业务字段及dense向量摘要未变，索引tag、encoder及稀疏权重与冻结编码器结果匹配；每批真实浏览器核对维护详情及对应业务列表，完成前不进入下一批，并逐项确认未选任务/identity/无关operation及fence未变。第4批发生一次验收脚本分页时序异常后立即停止后续提交：只读复现确认接口响应到达时列表仍在加载、下一页按钮尚未启用，8条知识技能实际均在第2页且ready；仅给临时验收脚本补充DOM渲染完成等待，保留全部断言，重新只读核验本批远端、页面及控制记录正常后继续，没有重复重试或改变应用代码。最终79条均completed/ready，累计控制表86条completed及1条原superseded，无manual/pending/running/retry_wait；本轮仅新增79个retry及79个index操作，全部原源数据及其余8条任务未变。后台manual_required筛选总数0，用户页44条、知识库两页39条均ready且无待修复标记。运行镜像及通用远端核实、未知操作对账规则不变；脱敏证据、每批截图及最终零积压截图见仓库忽略文件`data/runtime-checks/memory-backlog-batches-20261014.json`。

2026-10-14收尾只读复查：当前镜像仍为上述18bc44b0版本，执行器启动1次、无停止或不可用日志；15个运行文件与工作区一致，其中新增核实相关3个文件的哈希与部署记录一致。83条live/ready记忆（user44、character_global31、character_knowledge8）逐条严格fetch，dense1024、epoch/generation/body hash/encoder/index tag/归属/未删除标志及重算稀疏权重均匹配；此前恢复82条的业务字段和dense摘要未变。当前自动索引任务的维护页显示completed/ready、round0/attempt1、无人工原因且重试禁用；另只读核对此前真实新增验收的原持久回执，仍为约4.05秒自动完成、无retry操作，已按原验收清理的样本不当作当前live记忆。本轮未新增测试记忆，新建行为沿用此前真实验收证据，未声称本轮进行了新写入验收。真实浏览器用户页44条、全局用户记忆3页44条、知识库2页39条均ready且无待修复标记，manual_required总量0。实际未写入ID的通用fetch仍unknown/read_output_missing，仅专用create核实可获同目标gRPC空结果，零写入；新增、超时、通用确认和未知操作保护等92项隔离回归通过，原用户/全局原因渲染浏览器夹具也通过。原因异常场景为隔离夹具覆盖，不向当前已就绪数据注入故障。复查前后task/identity/operation/fence逐项未变，未执行创建、删除、重试、部署或执行器启停；现有运行记录`data/runtime-checks/memory-backlog-batches-20261014.json`已追加`readonly_closure_review`及截图。本次范围内未发现遗漏，状态VERIFIED，无剩余运行操作。

2026-10-14补做真实新增验收：用户另行明确授权一条临时测试记忆及正常协议删除。实际浏览器在用户1的新增表单只提交一次POST，code0/source succeeded（约1.40秒），未返回20129；初始真实行显示“等待处理／等待执行器领取并补建BM25索引／写入尝试0次”，约2.18秒自动转completed/ready，round0/attempt1、零人工retry。远端dense1024、sparse11项，正文、key、owner/type、epoch/generation/body hash、encoder与index tag及重算稀疏权重全部匹配；用户页、全局页均无待修复标记，维护页current/completed/ready、无人工原因且重试禁用。验收后只发送一次原认证DELETE（约0.46秒、code0），确认generation2远端墓碑及原delete tag、用户/全局列表移除，真实全局搜索为空态。有效记忆恢复83条；原87条任务、全部原identity/operation及fence逐项未变，仅增加该测试身份的create/index/delete共3个operation及1条已完成索引历史，当前87条completed与1条原superseded，无manual/pending/running/retry_wait。正常协议保留已删除identity和历史回执，不以直接物理清理替代墓碑。15个运行文件仍与工作区一致、3个新增核实文件哈希仍与部署记录一致，未改应用代码、配置或核实规则。现有记录`data/runtime-checks/memory-backlog-batches-20261014.json`已追加`real_create_followup`及实际截图；本次为新执行的真实新增、自动索引和删除验收，不再仅依赖前述历史新增证据，状态VERIFIED，临时认证文件已清除，无剩余运行操作。

`write_result`为 `operation_id/internal_operation_id/source_state/index_state/generation/identity_id/result_revision/maintenance_task_id/receipt_state/reason/observed_at`；数值身份/代/修订为十进制字符串或null，manual索引另给maintenance_state=manual_required。内部source confirmed→succeeded、superseded→failed；index manual→unknown、superseded→not_executed，delete源确认且not_required映为ready。`MemoryWriteResult(str)`兼容doc_id并附receipt；`VoiceAtomResult(str)`兼容原written/existing状态并附receipt，trace只证明源曾确认。

`GET /api/admin/memory-write-operations/{operation_id}`接受规范小写UUIDv4/v7，仅读本人create/update/delete/batch锚点并重新校验来源角色。全局/知识及batch为S/A/V，其余user/private为S/O/A/V，T无新增。旧操作source成功与 `currentness/current_generation/current_source_state/current_index_state`分开，不由后来正文重建旧成功。未决仅核实原operation，不新增源写；cleared或expired20123、不存在20125、作用域不可读20129。cleared回执是无正文白名单投影，不重聚合清空items或推进恢复。

全局user批删1～100，稳定去重且user-only；父与全部合法子项首次触网前同事务持久，原子项成功删除不重放。返回 `source_counts/index_counts`、逐项状态，同时保留 `deleted_count/failed_doc_ids`；加锁重算防晚读聚合回退。列表用SQL当前归属/代/hash/墓碑核验；confirmed初始baseline可兼容缺mr字段legacy，同代confirmed源的index在途不隐藏正文。附generation/index_state/legacy_read_only；无Stable Key可信旧正文只读。cap和读取算法保持，列表不证明完整来源。

<a id="memory-retrieval-protocol"></a>
### 四路查询、双召回和路内重排

Step1.5共享模板保留13字段：InnerMonologue及四组 `CharacterGlobal/CharacterPrivate/CharacterKnowledge/UserProfile`的QueryQuestion、QueryKeywords、CandidateKeys。解析生成四路 `MemoryQuery(question,keywords,skipped,question_state,keywords_state,warnings)`；Question缺失/null/非法复用原输入，合法空/“无”跳过；无合法Keywords复用Question，确定性补齐零付费调用。CandidateKeys只是协议提示，非法告警，不能作为新链结构化过滤豁免。模板说明有据实体、事实主体/未知槽位、时间、否定、经历与共同计划，不补缺失年份/城市，不输出权重/稀疏向量；实际模型语义质量仍以评测证据为准。

新目标 `new_lxm_memory_long_collection`，1024/FLOAT/DotProduct；dense写查统一严格L2，拒零/nonfinite/错维度，合法负分保留；BM25保原权重，空词项零查询，独立sparse请求仅协议alpha0使用零dense占位，剔零分填充而不影响dense。固定dashtext0.0.7与发布的 `memory-bm25-zh-v1:17dbc3fe3a4d2ed8dd70a72bef5bf8812abea09585a137e07cbd2fd76b4db194`；请求不fit/下载。Embedding新缓存v2含query/document语义profile和原value SHA256，命中仍验证L2。

2026-10-15生产发布按用户决定采用临时固定目标：仅生产发布快照将后端目标常量及两处后台表单的测试库字面量统一替换为 `new_lxm_memory_long_collection`。工作区本地测试库保持原值；通用库名配置改造延期，没有新增 `target_collection` 响应字段。该快照已部署到生产并开放epoch2；实际清理、运行与验收证据见唯一STEP §3.40的生产发布补记。

`CandidateValidator.merge`逐通道以当前SQL源/代/hash/归属/fence为权威，剔旧证据后重新计名次；legacy仅可匹配confirmed初始baseline且未分配新代；index未ready仅dense可用。四路各自独立候选、去重/排名/空因，不跨路比分。每路以Question及完整合法去重value调用本次冻结的rerank模型、top_n=N；本地env及配置示例使用`qwen3.7-text-rerank`，不限制为固定模型名，升级模型仍须兼容现有DashScope文本重排协议及本地准入约束。返回须完整唯一范围内int index及有限0～1分数，先排序后阈值，同分按输入序/身份稳定。故障整路RRF K=60或单通道名次，rerank_score=null，不套正常门槛；已成功路保留正常准入。

重排本地准入单位U= UTF8 bytes+32；任一Q/D>4000、N>500或N*U(Q)+ΣU(D)>30000时local_size_guard，零发送/零重试，不截正文/分批，U不冒充供应商真实tokens。

`MemoryVectorClient._query`仅在HTTP成功、严格整数code=0且明确存在output:null时确认空（同output=[]）；missing output、非数组非null、错误/布尔code、非法行或HTTP/provider失败仍unknown。非空行校验/当前性/归属、fetch、源写、原tag/full payload读回不放宽。2026-10-13实云空filter省略output，按该边界仍unknown；历史实云显式null输入仅录制协议验证通过，不能描述今天供应商始终返回成功空。

`run_pipeline/execute_memory_retrieval`消费单次冻结配置和调用方原D；改写、四路共享Step2分别min(起点+45秒,原D)，单改写20秒，失败调用最多一次重试、250ms退避在原预算内，永久/鉴权/非法输出不重试；取消并拒迟到，保留收口余量。固定整轮180秒及最终事务仲裁由[文字契约](../chat-emotion/api.md)与[Step8契约](../agent-future/api.md)负责。仅匹配doubao-seed-2-0-lite-260428的Step1.5非流式请求增加thinking:{type:disabled}，其他模型/Step5/旧PromptTest用途保持。只读模板见[人格契约](../persona-prompt-world-state/api.md#memory-readonly-previews)。

<a id="memory-prompt-selection"></a>
### 最终选入、官方计数与输入使用保护

`build_prompt→PromptBuildResult`保留prompt/config_snapshot_id/counter/selected/initial_selected/removed/route_counts/module_charges/over_budget/modules及可选use_claim_id/use_deadline_at；SelectedEntry绑定可信candidate、rendered_text和选入序，正文/Prompt不进repr或日志。四路独立final_top_k，角色cg→cp→ck按名次轮转、user独立预算；整条连标题/标签/分隔计数，首条不合停止该路。总超限按原裁剪优先级及角色逆成功序删尾，保持前缀、不补位；最终失效项及同路后缀淘汰后重渲染/重计数。候选正文只是数据，控制字符/模块分隔转义，key:value标签取可信metadata，身份/归属留DTO。

`OfficialTextCounter`绑定冻结reply model/官方endpoint/id/profile；count_many要求完整唯一indexed响应；按已知模块前缀/文本hash缓存，最终仍对完整字符串官方计数并预留64。昵称原文不裁；计数不可用失败、超总预算PromptBudgetExceeded，不换预算或近似值。保留普通Agent旧helper，旧测试使用[内部mock适配](../persona-prompt-world-state/api.md#memory-legacy-prompt-test)。

`reserve_prompt`在SQL最后核验后登记持久claim及原deadline；GuardedModelClient.send核claim/model/预算并取原datetime/monotonic截止较早者，httpcore body.complete后才confirm_handoff。无原预留结果不能裸发HTTP。取消先join sender、关闭客户端/socket再confirm_stopped；SQL回执也不越原D。未证明交付或停止则dispatching/unknown保护，不TTL解锁、不重发；确认交付不撤回历史输入，完整回复未到可释放使用锁。仅原owner可abort未发送reserved，mutation在fence→identity→claim锁序回收已过期且未dispatch的reserved；dispatching/unknown不按过期释放。

<a id="memory-maintenance-and-backfill"></a>
### 有限执行器、持久回填与S15工具

应用 lifespan 通过 `memory_index_runtime` 管理普通索引执行器的启动与停止。每5秒只读核对 DashVector 已发布配置、环境激活 fence/epoch/目标和本地 BM25 profile；未配置环境不启动，依赖不可用则停止执行器并定期限流记录脱敏原因，恢复后重新启动。配置或凭据变更时先等待旧实例停止，再启动新实例；不依赖回复模型、embedding 或 rerank 配置。运行异常日志只含白名单原因或异常类型，不输出原始异常文本、凭据或记忆正文。此增量于2026-10-13 17:54部署到local-docker:lxmfor，镜像标签`memory-index-20261013`，沿用原运行环境，仅叠加本轮7个后端文件。业务MemoryBusinessWriter写入的新记忆约3秒自动ready，远端读回dense1024、13个稀疏词项及正确encoder版本；临时验收记忆随后按正常删除协议清理。83条旧积压仅按原截止规则转manual，attempt/round仍为0，未重试或恢复。后台新增入口另实测返回20129/memory_source_unreadable：远端不存在ID的成功响应缺output，原严格协议仍判unknown；该入口在当时尚未通过，不以业务写入验证替代；2026-10-14新增修复的实际验收见上文。该次脱敏部署证据见仓库忽略文件`data/runtime-checks/memory-index-20261013.json`。

MemoryIndexWorker显式start/stop，持久claim/renew/process；全环境4槽、同identity单在途；每轮120秒、3次明确失败写及5/30秒退避；unknown最多24次只读核实、5秒间隔/单次3秒。retry先登记actor+UUIDv7固定结果，running/completed/rejected也可复读；manual新轮受revision及滚动24h最多3轮约束，unknown只核原intent不重发/解锁。终态清临时正文payload，详细无正文回执7天、墓碑30天，未决不回收；维护展示事件不承担恢复权威。

用户/私有记忆和全局用户记忆列表的当前行附 `index_maintenance`：ready 为 null，其余为 `{state,task_id,reason_code,reason,attempt_count,next_attempt_at,overdue}`。批读任务必须匹配当前 identity、generation、body_hash、encoder_version、operation_id，排除 superseded；缺失当前任务时 state=unavailable、task_id=null，明确原因暂不可用。reason/reason_code仅来自中文白名单；attempt_count为写入尝试次数，next_attempt_at为UTC时间或null。仍在pending/running/retry_wait但轮次截止已过时overdue=true，只有worker_epoch=0且attempt=0才能显示“尚未领取”。列表GET只读，不刷新持久状态、续期或触发重试；启动执行器后过期任务仍按原规则转人工处理，不自动重开积压轮次。

MemoryBackfillService在冻结target/epoch/partition按持久identity目录扫描，保存基线/范围摘要、高水位、checkpoint、15秒lease及原版本；默认20项/秒、合法(0,100]，有限3轮追赶。KV仅value、legacy完整正文，保持ID/当前正文/合法元数据，不重抽取/补时间。复用原代次intent/task、同锁序与正文摘要，旧task不改为新代；完成须全部当前身份、正文、代次及增量对账闭合，未解决单列，不由cap/maxID/退出码/零读取推完成。

`read(run_id)/items(run_id,after,limit)`消费真实持久DTO，limit1～100、item_seq稳定；总量未知null，包含模式/范围/阶段/时间/版本/基线/安全游标/截止/扫描数/唯一源数/尝试数/分类对账与task关联。管理Web只查询这些记录，不启动、暂停或全量回填。actual基线仅接受原opened reset/env/target/epoch/manifest对应empty_catalog证明及精确零partition确认；actual full_manifest无法核验时拒绝，isolated合成证明须显式allow_isolated及isolated:环境。

`scripts.memory_maintenance` reset默认preview只读，apply须显式配置/原manifest/run授权；先maintenance、排空原操作后T0重取基线、epoch只增一次。SQL固定PK清理与cursor同事务，提交未知查原run，completed读回后独立open，opened重入不得清新数据。正常回填和实际业务S15是不同动作；本轮文档不授权或声明实际业务清理。

2026-10-15新增工作区专用入口 `scripts.memory_production_release`，默认同样为只读preview。依据本次生产授权，manifest显式记录 `production_policy={old_vectors:preserve,data_backup:none}`；旧库只读核对分区/数量不变，新库必须真实空态，不调用向量删除或伪造删除/退役回执。该模式用 `old_runtime_target_isolated` 替代不适用的 `old_credentials_revoked` 封闭证明，其他停写/排空/结算证据仍须齐全；普通S15入口的原保护未放宽。SQL/Redis/同run断点、completed/opened及禁止重清复用原实现。精确已停旧backend通过Docker移除（不带卷删除），Compose只创建已冻结新backend且禁止重建已有依赖；日志/临时对象仅核对该旧容器可写层退出在线，不复制业务数据或日志归档，存在未盘点持久可写挂载则拒绝。该入口已在生产run `81d3901d-e39c-4766-9d23-b750739a4211` 完成清理及独立open：66项confirmed、58张表保留摘要一致，旧库245条未变；临时合成记忆新增/自动索引/dense及BM25查询/正常删除通过，普通重启后仍为唯一opened run、epoch2。新库仅留该测试的1个已删除墓碑、业务列表为空。生产结果不替代完整语义质量评测；详细证据见唯一STEP §3.40。

清理矩阵保留资料/数值/日记/朋友圈/指标/账本身份与值，只清relationship既定六字段及对应历史、语音正文/提取/config副本/旧队列并留cleared墓碑；未落地planned表仅核策略/schema，不能称已执行。HTTP/WS/scheduler明确environment时冻结env/epoch/target，SQL flush含autoflush与DML同事务校fence；旧epoch、maintenance或无上下文拒写。未配置environment不会自动启用部署维护，新writer仍需activation。

pre-T0源unknown只fetch核原tag/gen/hash，use保护只按原transport交付/join-close事实收口，语音仅原进程活handle可真实end/final_flush/结算；TTL/重启/自报值不替代完成。terminate_unsent限原run可证未dispatch intent，batch只在原child全核实后聚合，未知阻断T0。Redis按T0固定键形状/类型/值摘要Lua compare-delete+原run marker；向量精确cluster/collection/partition，delete_all未知不能因count0闭合。Docker/日志/音频只处理原明确范围，恢复材料离线0700/0600、不含SQL/manifest明文凭据，容器rm不带-v、恢复create不start；不能扫描其他容器/OSS。恢复采用新数据恢复与前向修复，不回切旧事实。结构见[data](data.md#memory-control-retention)，运维执行仍以具体授权/022证据为准。

<a id="memory-diagnostic-lifecycle"></a>
### 只读真实诊断与执行/保存分态

诊断来源为 `main/openapi/step8`：前两者共享实际主文字只读装载和组装，step8共享实际Step8装载和组装；真实Step1.5→四路双召回→路内重排→同次Prompt选入/官方计数。诊断不调用reply/send/Step1、不触发Step6、不写聊天、关系、情绪或日记业务状态；诊断表、摘要审计及输入使用claim是自身控制记录。

外部调用前持久 `UNIQUE(admin_id,request_id)` 和输入摘要；规范小写UUIDv7首次时间窗过去120秒/未来30秒。已登记身份先复读，输入冲突20121；显式重执行新request_id，可带UUIDv4 parent_execution_id并重新装载上下文。run/execution_id为UUIDv4。环境fence/锁串行准入，用户/管理员/环境1/1/2；执行120秒、另30秒保存，lease15秒每5秒续租，不续原截止。

执行态 `accepted/running/completed/degraded/failed/budget_blocked/interrupted/manual_required`；保存态独立 `pending/saved/failed/unknown/deleted`。先提交执行终态，另事务提交快照；执行完成而保存失败明确failed/snapshot_available=false。startup/周期恢复只收口原持久状态，不重发远端；失联owner不能证明停止时manual_required/unknown保留保护，无新增强制释放或自动重跑。GET纯读，不恢复任务。

公共投影含 `id/execution_id/request_id/user_id/admin_id/source/parent_execution_id/execution_state/history_state/revision/snapshot_available/reason/stage/created_at/started_at/finished_at/observed_at/deadline_at/persist_deadline_at/status_url/can_delete/server_time`，必要时action_reason/use_protected；revision十进制字符串，时间UTC。

详情默认另给 `input/frozen_versions/context_sources/selection_result/metrics/candidate_total/snapshot_semantics`；selection_result不旁路输出selected/initial_selected/removed大数组，仅给其count。candidates分页含可信原文、原分/名次、重排分/排序、渲染及初始/最终选入；仅淘汰提示行entry_kind、route/doc_id/identity/ordinal/stage/reason与选入false，不伪造正文。

历史保存原输入、四路改写、可信候选与同次选入/token、版本/上下文来源/调用耗时；不保存完整对话、完整Prompt或reply。费用不可得cost=null/cost_status=not_provided。服务凭据不进DTO、错误、日志、诊断或维护记录；合法业务input和候选原文保留，包括HTML，UI必须纯文本呈现。

快照永久保存，无自动到期；源删除不删历史、不回写源。手删仅终态history saved/failed/deleted、无lease owner及reserved/dispatching/unknown使用claim；unknown/manual_required/在途不可删。原子清input/candidate/selection/metrics/config/context及业务引用，留最小幂等/审计锚点和删除后30天tombstone，未新增自动清理。删除不取消执行、不删源。维护展示事件可删不代表恢复权威已删；未完成backfill/operation/task及使用保护引用仍阻断。

普通GET内部5秒，未读到/依赖故障20129；DELETE原commit未启动失败20129，启动后无法确认20122并携原execution_id/record_id，通过GET核实；准入未知20122用原request_id查询，不盲POST。不存在/无可用快照20125，资格不符20126，日期/组合错误20120，非法类型422，并发20124，过窗20123。权限唯一矩阵见[共享契约](../_shared/auth-rbac.md#memory-role-matrix)。

<a id="memory-admin-paging"></a>
### 诊断、维护和回填分页/动作投影

统一列表 `{list,total,page,page_size}`，默认1/20，page≥1、page_size1～100，total是同筛选完整数量；诊断历史另给server_time用于空态校时。日期UTC日开始含、end下一日不含；诊断按created_at/run_id降序，任务updated_at/task_id降序，回填started_at/run_id降序；候选保实际稳定ordinal（route过滤不重编号），attempts created_at/id升序，关联backfills run_id升序，items item_seq/id升序。详情大数组只能对应section分页，末空页不表示任务完成。

任务DTO为 `id/task_id/identity_id/type/user_id/doc_id/source/operation/operation_id/source_state/index_state/maintenance_state/generation/current_generation/currentness/attempt_count/round_no/revision/updated_at/next_attempt_at/manual_reason/can_retry/can_delete/action_reason`；identity/generation/revision为十进制字符串。

详情含deleted_attempt_count、history_state=available/partially_deleted、backfill_total；仅唯一实际关联run时run_id有值，默认superseded_by，section分别attempts/backfills。事件为 `id/record_id/event_id/record_kind/task_id/run_id/operation_id/event_type/source_state/index_state/maintenance_state/attempt_number/started_at/ended_at/created_at/reason/details/can_delete/action_reason`。

回填直接读008持久记录：`id/run_id/mode/execution_state/stage/source_scope/baseline/high_water/checkpoint_summary/cutoff/scanned_records/unique_source_ids/attempt_count/total_known/total_source_ids/source_class_counts/reconcile_counts/unresolved_count/report_complete/history_state/progress_available/can_delete/action_reason/frozen_versions/index_version/encoder_version/started_at/ended_at/updated_at/revision`。

total_known=false时total_source_ids为null，不推百分比。deleted仅保标识/history_state=deleted/progress_available=false/reason=display_history_deleted/不可删除，无可用进度20125。

items为 `id/run_id/item_seq/source_identity/type/user_id/source_class/content_digest/current_generation/index_result/reconcile_state/task_id/attempt_count/observed_at/reason`，digest为hex或null，id/item_seq/current_generation为十进制字符串或null。

retry资格由005后端只读判定，POST再锁验，旧代/源未知/已删/不合资格拒绝。history DELETE只清展示details/reason并标deleted，当前可信完成代、无未决源操作、活动task、useclaim或未完成对账引用才有资格。008仍保对账引用保护，无新增释放其权威的Web动作。所有回填GET不启动/暂停/恢复回填。

<a id="diagnostic-execute"></a>
### POST /api/admin/memory-diagnostics

`POST /api/admin/memory-diagnostics`；角色：S/A。

输入：ExecuteBody：request_id规范UUIDv7、user_id严格正整数、source=main/openapi/step8、input非空1～2000（step8≤200）、parent_execution_id可选UUIDv4。

响应与语义：原执行公共投影；新执行外部调用前登记。同身份同摘要复用；另有并发/期限/保存分态。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_diagnostics.py:45`。

<a id="diagnostic-history"></a>
### GET /api/admin/memory-diagnostics

`GET /api/admin/memory-diagnostics`；角色：S/A/V。

输入：page/page_size；request_id规范UUIDv7且仅当前actor；user_id正整数；source；state（执行态）；start_date/end_date。

响应与语义：完整历史列表+server_time；created_at/run_id降序。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_diagnostics.py:55`。

<a id="diagnostic-detail"></a>
### GET /api/admin/memory-diagnostics/{execution_id}

`GET /api/admin/memory-diagnostics/{execution_id}`；角色：S/A/V。

输入：execution_id规范UUIDv4；section可选candidates；route仅在section=candidates时可给cg/cp/ck/user；page/page_size。

响应与语义：公共投影及默认小详情；section则候选完整分页，无快照20125。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_diagnostics.py:64`。

<a id="diagnostic-delete"></a>
### DELETE /api/admin/memory-diagnostics/{execution_id}

`DELETE /api/admin/memory-diagnostics/{execution_id}`；角色：S/A。

输入：execution_id规范UUIDv4；不按原admin_id扩大或收紧原删除角色。

响应与语义：按终态/lease/use保护资格清历史并留锚点；can_delete及unknown收口遵从生命周期。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_diagnostics.py:72`。

<a id="maintenance-tasks"></a>
### GET /api/admin/memory-index-maintenance/tasks

`GET /api/admin/memory-index-maintenance/tasks`；角色：S/A/V。

输入：page/page_size、user_id、type=character_global/character_private/character_knowledge/user、state=pending/running/retry_wait/manual_required/completed/superseded/source_unverified、operation=create/update/delete/index/retry/baseline/batch、source=admin/text/voice/system、doc_id长1～64、start_date/end_date。

响应与语义：任务公共投影列表，updated_at/task_id降序。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:29`。

<a id="maintenance-task-detail"></a>
### GET /api/admin/memory-index-maintenance/tasks/{task_id}

`GET /api/admin/memory-index-maintenance/tasks/{task_id}`；角色：S/A/V。

输入：task_id规范UUIDv4；section可选attempts/backfills；page/page_size。

响应与语义：默认小详情；attempt事件或真实关联backfills分页。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:39`。

<a id="maintenance-task-retry"></a>
### POST /api/admin/memory-index-maintenance/tasks/{task_id}/retry

`POST /api/admin/memory-index-maintenance/tasks/{task_id}/retry`；角色：S/A。

输入：task_id规范UUIDv4；Body request_id规范UUIDv7、expected_revision规范ASCII正十进制字符串且<2^64。

响应与语义：原005固定重试回执：后端重新锁验资格/修订/原request；不盲重发unknown远端。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:45`。

<a id="maintenance-history-delete"></a>
### DELETE /api/admin/memory-index-maintenance/history/{record_id}

`DELETE /api/admin/memory-index-maintenance/history/{record_id}`；角色：S/A。

输入：record_id规范ASCII正十进制且<2^63。

响应与语义：删除展示历史，不删task/source/backfill权威、不取消在途；protected20126、commit未知20122。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:54`。

<a id="maintenance-backfills"></a>
### GET /api/admin/memory-index-maintenance/backfills

`GET /api/admin/memory-index-maintenance/backfills`；角色：S/A/V。

输入：page/page_size、state=pending/running/interrupted/manual_required/completed、stage=scan/index/reconcile/catchup、start_date/end_date。

响应与语义：真实run投影列表，started_at/run_id降序。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:63`。

<a id="maintenance-backfill-detail"></a>
### GET /api/admin/memory-index-maintenance/backfills/{run_id}

`GET /api/admin/memory-index-maintenance/backfills/{run_id}`；角色：S/A/V。

输入：run_id规范UUIDv4。

响应与语义：真实008单run进度/版本/来源摘要；无虚构总量，不启动任务。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:70`。

<a id="maintenance-backfill-items"></a>
### GET /api/admin/memory-index-maintenance/backfills/{run_id}/items

`GET /api/admin/memory-index-maintenance/backfills/{run_id}/items`；角色：S/A/V。

输入：run_id规范UUIDv4；page/page_size；query class=standard_kv/legacy_free_text/empty/identity_or_parse_error；state=matched/missing/extra/mismatch/unknown/retry_wait/identity_or_parse_error。

响应与语义：真实items完整分页，item_seq/id升序。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_index_maintenance.py:75`。

<a id="memory-write-operation"></a>
### GET /api/admin/memory-write-operations/{operation_id}

`GET /api/admin/memory-write-operations/{operation_id}`；角色：本人+原来源读取角色。

输入：operation_id规范小写UUIDv4/v7。

响应与语义：原write_result固定receipt；cleared/expired20123、不存在20125、来源不可读20129。仅读本人且核原来源角色，未决可核原tag但不发新源写。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/memory_write_operations.py:14`。

<a id="config-publication-receipt"></a>
### GET /api/admin/configs/publications/{publish_id}

`GET /api/admin/configs/publications/{publish_id}`；角色：本人+原配置入口角色。

输入：publish_id规范小写UUIDv7。

响应与语义：原publish DTO+server_time；pending/unknown20122、expired20123、不存在20125；原第三方/召回/Token/向量来源读取角色。

信封沿用 `ApiResponse`；本域通用状态、字段、分页与错误见[诊断生命周期](#memory-diagnostic-lifecycle)、[分页与动作投影](#memory-admin-paging)，原来源自有回执另见[写入回执](#memory-write-receipts)或[配置发布](#memory-config-publication)。实现来源：`backend/routers/admin/vector_config.py:123`。

<a id="memory-dotproduct-retained-consumers"></a>
### 保留消费者的DotProduct适配

旧EmbeddingService单/批API与缓存消费严格1024维有限非零L2；原缓存key/TTL86400、批25、单调用10秒、query text_type/model/endpoint保持。旧缓存消费时归一化，不清库重建。旧DashVector search/upsert触网前L2，原TopK、threshold、filter及10秒保持；响应无code仍沿原允许成功body，若有code须严格整数0；有限非bool score稳定降序，非法向量沿原[]/False失败。新文字MemoryVectorClient独立，不套旧门槛。

普通Agent、语音实时/会前、直接HTTP、CRUD、星云、后台测连均核对DotProduct方向与L2；语音 `bounded_dotproduct_score`仅消费[-1,1]及绝对1e-6传输容差，边界夹±1，非有限/布尔/真越界拒绝；原实时0.7、会前非负与时限/质量/过期/去重/数量/缓存/迟到处理保持，具体见[语音契约](../realtime-voice/api.md)。新BM25/重排不用此函数。实际语音writer同ID源确认→索引ready→新文字BM25当前正文/跨user隔离有独立证据，纯dense命中不代替。

<a id="memory-sdk-endpoint-compat"></a>
### 隔离S15 SDK工厂地址兼容

实际工具工厂接受经校验的https endpoint；构造DashVector SDK客户端仅传 `endpoint=urlsplit(endpoint).netloc`，保留原GRPC默认与10秒默认。原完整endpoint仍参与目标指纹，来源/新库/partition精确约束不变。显式HTTP协议构造在SDK1.0.23异步运行loop出现冲突，失败记录保留，已撤销该HTTP参数，不能作为有效行为。

只读实际最终工厂Client/get/stats/list返回code0、自有partition原1条、零写；局部RED/GREEN与原stats/zero/unknown删除保护证据分列。该适配不修改unknown删除收口、清理提交、S15保护或恢复为旧业务；其有效准备证据待022原工具prepare/drill收齐后由唯一记录确认。本节仅描述工作区最小地址适配，不声明部署或业务清理。

<a id="memory-mutation-payload-and-legacy"></a>
### 原意图、正文载荷和旧源删除

write DTO顶层仅id/vector/fields/sparse_vector；只读fetch score不写回，合法全部业务fields保留。源写省略sparse清旧派生索引；索引full upsert沿原冻结当前正文/归属/代/hash及独立tag。旧task不改为最新代，prepared新owner恢复原attempt/tag/payload，dispatching/unknown只读核实。writer只编码KV value、旧自由正文全content，使用writer.embed新profile，不读旧MD5 embedding缓存；原公共owner0/私有可信user及voice/text/admin/unknown last_write_source保持。

`full_upsert`在HTTP 200、顶层code严格为整数0、output恰有一条且文档ID匹配、逐条code严格为整数0时，接受字符串`doc_op=insert/update/upsert`直接确认成功，不额外fetch。仅在HTTP 200且顶层code严格为整数0、但逐条回执未满足直接确认条件时，沿原完整载荷读回核实；HTTP或顶层code不满足原成功条件时仍直接unknown。output缺失/null/空/非法结构、fetch/query及未知操作的判断不变。

2026-10-15已部署本地Docker，镜像`lxm_for-backend:doc-op-20261015-632fffbdb8e4`，回滚镜像`lxm_for-backend:doc-op-rollback-20261015-5749696e8ab1`。以原运行镜像为基底仅叠加该适配器；298个后端源码文件逐项核对仅此文件变化，原环境变量、端口、挂载和网络保持一致。真实Admin HTTP API对用户1的专用临时私有状态执行新增、编辑：源均succeeded，索引分别约3.7秒、4.7秒从pending到ready，任务均completed/attempt1；编辑保持doc_id/key，generation从1增至2，列表、SQL和远端正文摘要一致，dense1024及sparse有效。临时条目已通过正常DELETE清理并确认列表移除、远端墓碑；原私有条目及1条历史未知操作逐字段未变。该验收不代表Step6 LLM自动提取或浏览器UI写入验收；未恢复或改写历史未知操作。脱敏证据见仓库忽略文件`data/runtime-checks/doc-op-20261015.json`。

legacy源删除第一次SQL快照同事务冻结目录身份/代/hash和原SQL摘要；原writer持久tombstone确认后再校原行/epoch/delete-op软删SQL，未知/回执丢失复用原intent。prepare可选期望代/hash只加强原快照，旧缺省调用不变。cleared receipt保mt/授权域、opaque operation/child、固定源/索引计数和原结果，去Key/doc_id等语义文本；自有GET直接读白名单，不聚合空items或reconcile。

<a id="s15-vector-receipt"></a>
### S15 向量删除回执与独立退役证据

`VectorResetAdapter` 在第一次外调前持久登记 run/resource/精确目标摘要/不可变 revision；同步删除的原 code/request_id 回执必须在 count 前提交。有效原回执不可变，后续计数失败或中断不能抹除；checkpoint 提交未知只读核实原记录，禁止重发。只有同步成功原回执或内部可信验证器认证的独立请求完成证据，再加当前精确目标为空，才能确认完成。单独 count=0、等待、进程退出、本地签名或自报 JSON 都不证明原请求结束。

内部独立验证器也可认证精确目标已退役且迟到删除已隔离的 `target_retired` 证据；这允许原 run 收口，但不把原未知删除结果改写为成功。退役目标名称永久不复用。生产 factory 不自动提供该验证器；没有网页、CLI force 或用户上传证明接口。证据逻辑结构见[既有 cursor](data.md#s15-vector-cursor)。

本轮真实隔离核验：原分区退役取得供应商成功回执，并由独立认证读取确认不存在；同一 run 完成并开放，在不同新分区验证真实写入、索引、新数据恢复和重复 reset 不再清理。HTTP fetch 成功但缺 output 仍为 unknown；演练中的缺失文档由独立 SDK 空字典读取确认，未放宽产品协议。业务环境生效状态只以 STEP §3 的部署记录为准。

<a id="s15-empty-catalog-list"></a>
### 清理后无身份记录的列表空态

H5与Admin源列表先查询冻结目标、精确分区、类型及用户归属的SQL身份目录；没有任何匹配身份时返回空列表，不调用供应商，也不将远端unknown解释为空。所有身份状态均纳入存在性判断；只要存在unknown/live/deleted身份，仍走原远端查询和当前源验证。SQL失败不得转为空，操作回执、fetch及缺失output的query严格语义不变。该路径仅作用于已有列表，不改变召回质量参数。
