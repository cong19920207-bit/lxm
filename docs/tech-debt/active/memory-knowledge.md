# memory-knowledge 技术债

- 文档 ID：`tech-debt-memory-knowledge`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：无
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-017] 记忆检索：查询改写 / LLM 重写检索 query（**部分清偿 · 2026-05-30**）

- **背景**：对话链路曾用用户原文直接 `get_embedding` → DashVector 检索。产品希望增强召回（同义扩展、多轮指代消解、隐私脱敏后再检索等）。
- **当前处理（2026-05-30 · PRD v6.1）**：主链已实现 **Step1.5**（`query_rewrite_service`：13 字段、四路 Question/Keywords/CandidateKeys、HyDE 规则、失败降级单 Embedding）；Step2 按路检索与 **2.5 补充路** 已落地。见 `docs/contract.md`「2026-05-30 摘要」。
- **仍待评估**：独立小模型/规则缓存、改写 on/off A/B、与 embedding 缓存 key 策略等（原 TD-017 完整愿景）；**不阻塞**现网主链。
- **待处理**：
  1. 设计改写链路：独立小 LLM / 规则 / 缓存；输入为「本轮用于检索的文本」，输出为「检索 query」再 embedding。
  2. 与 `embedding_service` Redis 缓存 key 策略对齐（改写结果 vs 原文分别缓存或统一 key）。
  3. 评估成本、延迟与 A/B（改写 on/off）。
  4. 清偿后更新 `docs/contract.md` 若对外暴露行为差异。
- **触发时机**：TD-015 对话打包上线后，若召回质量不足再排期。
- **风险等级**：**低～中**（多一次调用与失败回退策略）

### [TD-022] 用户记忆双轨并存：MySQL「列表记忆」与 Step6 四路向量未收敛（**已清偿**）

- **清偿说明（2026-05-31，长记忆第一套下线 PRD v1.3 一次发布）**：第一套写入已下线——`chat.py` 删除 `memory_service.extract_and_save` 调用，物理删除 `extract_and_save`/`_deduplicate_and_save` 及专属私有方法，其余记忆方法标 `@deprecated`；H5/Admin 改读 Step6 user 向量（`/api/memory/list` 只读、`user-memories`/`private-settings`、`memories/global`/`batch-delete`）；唯一写入真相源收敛为 **Step6 向量**。运行时**不过滤 `mem_*`**（P1，推翻原 M13/M10），存量 `mem_*` 脏数据靠 **M2 发布前人工清理**（DashVector 删 `mem_` 前缀 + 清空 MySQL `memory` 表业务数据，表结构保留 M8），见 STEP-016 运维 checklist。PR 号占位：`<PR-待补>`。
- **背景（历史）**：当前存在**两套并行**的用户相关记忆链路，**不互为替代**，且 Step2 检索侧**未隔离**。
- **第一套（列表 / CRUD）**：
  - **写入**：对话成功闭环后置任务 **`memory_service.extract_and_save`**（`MEMORY_EXTRACT_PROMPT` → LLM 返回 `{"memory_list":["短句",...]}`）；用户 **H5「我的记忆」** 与 **管理端用户详情 → 记忆** 的 **手动添加** 亦写入同路径。
  - **存储**：**MySQL `memory` 表**为主；向量侧经 **`vector_service.upsert`**，`doc_id` 形如 **`mem_{memory_id}`**，`type = user`，`fields` 含 `user_id`、`content` 等。
  - **展示**：用户端 **`/api/memory/*`**、管理端用户记忆接口，均读 **`memory` 表**。
- **第二套（Step6 结构化总结）**：
  - **写入**：**Step6** 独立 LLM（**`memory_llm_service.build_step6_prompt` / `parse_step6_output`**），输出 **11 个驼峰字段**；其中 **`UserSettings` / Character\*** 等约定为**多行 `key：value`（中文全角冒号）**；**`upsert_step6_vectors`** 按行解析后写入 **DashVector 四路**（`user` / `character_private` 等），`doc_id` 形如 **`user:{stable_key}:{user_id}`**；另有 **`relationship`** 表上若干 **Step6 标量/描述写回**。
  - **存储**：**无**与「记忆列表」一一对应的 **`memory` 表行**；真相在 **向量 + relationship 扩展字段**。
- **检索现状**：主对话 **Step2**（**`multi_vector_retrieval_service`**）第四路对 **`MEMORY_TYPE_USER` + `user_id`** 做向量检索，**不过滤** `doc_id` 前缀——**旧 `mem_*` 与 Step6 `user:…` 文档在同一过滤条件下共同参与相似度排序**，均可进入 Prompt（在阈值与 `top_k` 内）。主链**已不再**单独依赖旧接口名做「仅列表记忆」检索，但**物理上仍同池召回**。
- **当前影响**：**不阻断**主流程；可能 **Prompt 内语义重复**、**运营/用户改删列表记忆与 Step6 向量不一致**、维护 **两套格式约定**（自由短句 vs `key：value`）成本高。
- **常见误判（已澄清）**：「关掉第一套后，用户在客户端按第二套格式**手打**多行 `key：value`」——在**不改后端**的前提下，仍走 **`memory` 表 + `mem_*`**，**不会**自动等价于 Step6 的 **`parse_kv_lines` + 稳定 `doc_id` 覆盖** 写入路径。
- **待处理（与 TD-023 可合并排期）**：
  1. **产品定稿**：唯一「真相源」——仅列表、仅 Step6、或「列表展示 + 检索仅 Step6」等方案。
  2. **写入侧**：下线或迁移 **`extract_and_save`**；若保留手动维护，需明确写入 **第二套向量规则** 或中间同步层（须开发，非现网手输可达成）。
  3. **检索侧**：若只认一套，需在 **`dashvector_client.search` 过滤条件或业务层** 排除另一套 `doc_id`/标记位，或 **拆 collection**（评估迁移成本）。
  4. **展示侧**：若产品要求列表与检索同源，需 **新读路径**（从向量/同步表聚合）或 **定期同步** 至 `memory` 表（须契约与冲突策略）。
- **触发时机**：产品要统一「我的记忆」与对话注入口径、或研发要降低双写维护成本时排期。
- **风险等级**：**中**（长期语义漂移与排障成本；短期功能可用）
- **关联**：**TD-017**（检索 query 侧）、**TD-023**（合并与去重口径）；实现锚点：`backend/services/memory_service.py`、`backend/services/memory_llm_service.py`、`backend/services/multi_vector_retrieval_service.py`、`backend/routers/chat.py`（后置任务与 Step6 入队）。

### [TD-023] 用户记忆跨源合并与去重口径待统一（**已缓解**）

- **缓解说明（2026-05-31）**：随 TD-022 下线第一套写入，「同一用户事实」不再产生 `mem_*` 新增，新写入唯一走 Step6 **同 `memory_type` + 同 stable `key` 的 upsert 覆盖**（合并阈值 ≥0.92 的 MySQL 去重逻辑已随 `_deduplicate_and_save` 物理删除）。**残留**：存量历史 `mem_*` 与 `user:…` 在清理前仍同池召回（靠 M2 人工清理，P1），跨源对账脚本仍未提供；待 M2 清理完成后本项可视情况关闭。
- **背景（历史）**：在 **TD-022** 双轨前提下，「同一用户事实」可能以 **不同形态** 并存——例如 **`mem_*` 整句摘要** 与 **Step6 `user:` 行级 `key：value`** 在 **同一 `type=user` 检索池** 中均可命中；第一套另有 **MySQL + 向量相似度 ≥ 0.92 合并**（`memory_service._deduplicate_and_save`），第二套为 **同 `memory_type` + 同 stable `key` 的 upsert 覆盖**，**两套合并语义互不自动对齐**。
- **问题**：缺少 **跨 `doc_id` 方案 / 跨表** 的统一「合并、覆盖、废弃」规则；清理其中一套时易产生 **孤儿向量**、**重复注入** 或 **用户删列表但对话仍召回旧向量** 等产品/数据一致性问题。
- **待处理（建议与 TD-022 同一里程碑清偿）**：
  1. **定义合并产品口径**：何种情况视为同一记忆（语义相似 vs key 相同 vs 人工绑定）；**列表删除**是否级联删向量、是否影响 Step6 行。
  2. **技术方案**：统一 **doc_id 命名空间** 或引入 **`source` / `pipeline` 字段** 供检索过滤与后台审计；必要时提供 **离线对账脚本**（MySQL `memory` ↔ DashVector `user` 文档）。
  3. **迁移策略**：若收敛为单套，明确 **历史 `mem_*` 与 `user:…` 的保留、迁移、批量删除** 顺序与回滚。
  4. **管理端**：全局记忆搜索、批量删除（现有 **`memory_mgmt`**）与 Step6 文档的 **操作边界** 写进契约，避免误删非列表来源文档。
- **触发时机**：启动 **TD-022** 收敛方案时 **一并设计清偿**；不宜在仅关接口不关向量的情况下单独「关第一套」。
- **风险等级**：**中**（数据一致性与检索可解释性；误操作可影响多用户向量集合）
- **关联**：**TD-022**；`backend/services/memory_service.py`（合并阈值与 `mem_*`）、`backend/services/memory_llm_service.py`（`parse_kv_lines` / `upsert_step6_vectors`）、`backend/routers/admin/memory_mgmt.py`。

### [TD-026] Step6/Admin 前写入的 DashVector 文档缺少 key_l1/key_l2（**待清偿**）

- **背景**：2026-05-30 起 Step2 主路 `build_filter` 支持 **`key_l2 IN (...)`** 结构化过滤（由 Step1.5 `CandidateKeys` 推导）。**新写入**（Step6 `upsert_step6_vectors`、Admin `_build_knowledge_fields`）均补齐 `key_l1`/`key_l2`；**历史向量**可能仅有 `type`/`user_id`/`content`，无二级 Key 字段。
- **当前处理**：主路 `candidate_keys` 过滤对旧文档**不命中**时，依赖 **2.5 补充路**（`candidate_keys=[]`、更宽 filter）与纯向量相似度兜底；**不阻断**主对话。
- **待处理**：离线批量回填 `key_l1`/`key_l2`（需从 `content` 或 `stable_key` 解析）；或产品接受旧文档仅走补充路/降级召回。
- **触发时机**：运营反馈「结构化 Key 检索召回偏少」或要做全量 Key 运营筛选时排期。
- **风险等级**：**低～中**（召回质量与可解释性）
- **关联**：`docs/contract.md`「2026-05-30 摘要」；`backend/utils/dashvector_client.py` `build_filter`。

### [TD-027] Step2 补充路触发阈值与 top_k 未纳入热配（**待清偿**）

- **背景**：`multi_vector_retrieval_service` 中 **`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`**（`count<2 OR max_score<0.75`）与补充路 **`top_k=3`** 为**代码常量**；`vector_retrieval_config` 热配仅覆盖主路 **`top_k`/`threshold`**。
- **当前处理**：按 PRD C2/C7/C36 写死，管理端不可调。
- **待处理**：产品确认是否将补充路阈值/top_k 并入 `vector_retrieval_config` 或独立配置键；变更时同步契约与 `tests/test_multi_vector_retrieval_service.py`。
- **触发时机**：运营需按环境调补充路 aggressiveness 时排期。
- **风险等级**：**低**
- **关联**：`docs/contract.md` §向量召回与 Prompt Token 热配置。

### [TD-028] Step6 四类 KV 写入前缺少「多 key 挤一行」检测与阻断（**L4 · 待清偿**）

- **背景**：Step6 字段 **`CharacterPublicSettings` / `CharacterPrivateSettings` / `CharacterKnowledges` / `UserSettings`** 约定为 **多行 `key：value`（全角冒号）**，**一行一条**；`parse_kv_lines` 仅按 **`\n` 拆行**，每行取**首处** `：` 为界。2026-05 已在 **`build_step6_prompt`** 增加「多条信息分行规则」与反例（Prompt-first），但 **写入链路无确定性校验**。
- **问题（稳定性 L4）**：当 LLM 仍将多条独立 `三层key：value` 写在**同一行**（常见以 **`；` + 下一 key** 串联）时，解析只得 **1 条** `(key, value)`，`value` 内夹带其它 key 全文 → **静默错误落库**（角色知识库后台可见「一条 value 含多个 key」）；**无日志指标、无告警、无跳过写入**，运营只能人工发现并编辑。
- **当前处理**：依赖 Prompt 约束 + few-shot 多行 `\n` 示例；**不满足**「坏格式可自动发现或不落库」的 **L4** 目标。
- **待处理（建议最小集）**：
  1. 在 **`upsert_step6_vectors`** 调用 **`parse_kv_lines` 之后**（或解析函数出口），对每字段每行 `(key, value)` 做 **启发式检测**：例如 `value` 内再出现 **`；`（或 `;`）后接合法三层 key + 全角 `：`**，或「`parse_kv_lines` 行数 = 1 但 value 汉字数 / 嵌套 key 模式异常」。
  2. 命中时 **`logger.warning`**（含 `user_id`、`field_name`、`round_id` 若可得、截断 preview），可选递增 Redis/日计数 **`step6_kv_merge_risk:{date}`** 供监控页或日志检索。
  3. **产品择一**：仅观测（仍写入，便于对比 Prompt 效果）；或 **跳过该字段当轮向量写入**（relationship 标量仍可按既有逻辑写回，避免整轮 Step6 失败）；或 **跳过单行** 仅丢弃可疑行。须在 **`docs/contract.md`** STEP-014 写明行为。
  4. 管理端 **角色知识库列表** 可选：对 `content` / `value` 做同款检测并展示「疑似合并」标记（非必须，可与 1 共用工具函数）。
- **触发时机**：Prompt 加强后仍抽检到合并条；或要把「每条知识独立向量」视为硬 SLA 时排期 **TD-028**（可与 **TD-029** 分阶段）。
- **风险等级**：**中**（数据质量与检索语义；不阻断主对话 SSE）
- **关联**：**TD-022**（Step6 向量轨）；`backend/services/memory_llm_service.py`（`parse_kv_lines`、`upsert_step6_vectors`、`build_step6_prompt`）；`backend/utils/character_knowledge_validate.py`（`validate_key` 复用）；`backend/services/character_knowledge_service.py`（展示侧可选）。

### [TD-029] Step6 四类 KV 同行多 key 无自动拆分/重试修复（**L5 · 待清偿**）

- **背景**：在 **TD-028（L4）** 仅解决「能看见 / 能选择不落库」的前提下，**L5** 要求坏格式 **自动修复** 后仍按约定 **多条独立 upsert**，而非长期依赖人工改后台或重跑对话。
- **问题**：即使 Prompt 合规率提升，模型仍可能偶发同行拼接；当前 **无**（a）确定性 **拆行**（例如在 `；` + 合法三层 `key：` 处切分为多行再 `parse_kv_lines`）；（b）检测到违规后的 **Step6 子链路重试**（附「请用 `\n` 分行」类纠错提示）；（c）对已落库脏数据的 **离线重解析脚本**。
- **待处理（与 TD-028 二选一或组合，须产品确认）**：
  1. **解析兜底（偏 L5）**：扩展 `parse_kv_lines`（或前置 normalize）：在保留「**默认仍为一行一条**」前提下，对 **行首 / `\n` / `；`** 后的合法三层 `key：` 切分点拆成多段再 upsert；切分后仍走 **`validate_key` / `validate_value`**；需评估 value 正文误拆风险并写单测（含截图同款 `体育-球类-篮球：…；体育-球类-乒乓球：…`）。
  2. **重试兜底**：当 TD-028 检测命中且策略为「拒绝写入」时，**仅重试 Step6 LLM 一次**（`execute_step6` 已有 1 次整体重试，可改为「解析层违规触发的定向重试」并在 Prompt 末尾追加一行纠错说明），避免与 JSON 解析失败混为一谈。
  3. **数据修复（可选二期）**：对 DashVector `character_knowledge` / `character_global` 等 `content` 批量重跑新解析器并 upsert（评估 embedding 成本；与 **TD-026** 回填可同窗口）。
- **实现约定**：若采用解析兜底，契约须写明 **「Prompt 要求换行 + 解析器对同行多 key 的兼容边界」**，避免与运营手动在后台录入的单行 value（内含分号但非 key）冲突；**优先**在 TD-028 观测 1～2 周再决定是否上 1，降低误拆。
- **触发时机**：**TD-028** 指标显示违规率仍高于可接受阈值；或上线后仍频繁出现合并条且人工处理成本高。
- **风险等级**：**中**（误拆导致向量语义碎片化；重试增加 Step6 耗时与 LLM 成本）
- **关联**：**TD-028**（L4 前置观测）；**TD-026**（重解析时可顺带补 `key_l1`/`key_l2`）；`backend/services/step6_orchestrator.py`。
