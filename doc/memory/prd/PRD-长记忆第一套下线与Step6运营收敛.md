# PRD：长记忆第一套下线与 Step6 运营收敛

> 版本：**v1.3**  
> 状态：**需求已确认**（M1~M20 + C-01~C-10 + R-01 + P1~P10 复查，待开发）  
> 需求确认日期：**2026-05-31**（R-01 同日补充；P1~P10 复查同日确认）  
> 前置 PRD：`PRD-记忆检索与Prompt优化.md`（v6.1，Step1.5/Step2/四路向量检索已落地）  
> 关联技术债：**TD-022**、**TD-023**（第一套双轨与跨源合并，本期清偿主路径）  
> 涉及模块：`memory_service` / `memory_llm_service` / **`user_vector_memory_service`（新建）** / `routers/memory.py` / `routers/chat.py` / `routers/admin/users.py` / `routers/admin/memory_mgmt.py` / `character_knowledge_validate`（工具复用）/ `multi_vector_retrieval_service` / `agent_service` / `frontend/pages/memory.html` / `frontend/pages/settings.html` / `admin/pages/user-detail.html` / `admin/pages/memory-rules.html`

---

# 1. 功能背景

## 1.1 当前功能是什么

系统存在 **两套并行** 的「用户长记忆」能力：

| 轨道 | 写入 | 存储 | 展示/运营 | 对话召回 |
|------|------|------|-----------|----------|
| **第一套（列表轨）** | 对话后置 `extract_and_save`；H5/Admin 手动增删改 | MySQL `memory` + DashVector `mem_{memory_id}` | H5「我的记忆」、Admin 用户详情「用户记忆」、`/memories/global` | 与 Step6 **同池** `type=user`（历史 PRD 标注 TD-022 本期不做） |
| **第二套（Step6）** | 对话成功闭环后异步 `execute_step6` → `upsert_step6_vectors` | DashVector `user_{hash12}_{userId}` 等；`UserSettings`→`user`，`CharacterPrivateSettings`→`character_private` | **无** 专用运营页（私有设定仅落向量） | Step2 **user 路** + Prompt 模块 5 |

主对话 Prompt 构建已走 **Step1.5 + Step2 四路检索**；第一套列表轨在检索池内仍可能与 Step6 **重复注入、语义冲突**，且合并语义不一致（TD-023）。

## 1.2 当前存在的问题

**问题一：双轨并存，维护与排障成本高**  
两套写入格式（自由短句 vs 三层 `key：value`）、两套去重规则（MySQL 0.92 合并 vs stable key upsert），运营改列表记忆不影响 Step6 向量。

**问题二：第一套合并可能误伤 Step6 向量**  
`memory_service._deduplicate_and_save` 对相似向量 **无差别** `delete(doc_id)`，可能删掉 `user_*` 文档而仅软删 `mem_*` 对应 MySQL 行。

**问题三：管理端能力割裂**  
- 用户级 `user` / `character_private` 向量只能依赖对话 Step6 自动写入，**无法**像「角色知识库」一样在后台维护。  
- `character_private` 无 Admin 入口，排查用户私有设定困难。

**问题四：记忆规则页与运行时脱节**  
`memory_rules` 配置项（提取 Prompt、重要性、存储/合并阈值）服务于第一套，**运行时未读取**；Step6 Prompt 写死在 `memory_llm_service.build_step6_prompt`，调优需发版。

**问题五：send 时 `memory_injected` 与主链不一致**  
`chat_send` 仍用旧向量检索写 `conversation_log.memory_injected`，与 bundle 内 Step2 结果无关，易误导排查。

## 1.3 改造目标

1. **下线第一套**：停止 `extract_and_save`、停止 `memory` 表读写、停止 `mem_*` 写入与列表轨召回；H5/Admin 列表轨增删改接口废弃。  
2. **收敛为 Step6 唯一长记忆写入与 user 路召回**（`character_private` 仍走 Step6 写入 + Step2 专路，与 user 路分离）。  
3. **运营能力补齐**：Admin 用户详情 **用户记忆** + **私有状态** Tab；**记忆规则页**增加 **全局用户记忆** Tab（跨用户搜 `user` 向量）。  
4. **Step6 Prompt 后台可配 + 热更**：记忆规则页改造，替换为第一套废弃项 + Step6 结构化 Prompt 配置。  
5. **上线前数据清理**：人工清空 MySQL `memory` + DashVector `mem_*`（**不做**代码迁移脚本）。  
6. **`memory_injected` 恒为 null**（C-MEM-05），缩小改动面。

---

# 2. 方案确认决策记录

## 2.1 产品决策（M1~M20）

以下为产品/研发已确认决策，作为实现基线。

| 编号 | 问题 | 决策 |
|------|------|------|
| **M1** | 唯一真相源 | **Step6**；第一套整体下线（Q1=A） |
| **M2** | 历史数据 | **不做代码迁移**；上线前运维 **手工** 清理 MySQL `memory` 全表数据 + DashVector 删除全部 **`mem_*`** doc_id |
| **M3** | Admin 用户记忆 | **新增**对用户 `type=user`（Step6 `UserSettings`）的 **增删改查**；服务层 **新建 `user_vector_memory_service`**，工具复用 `character_knowledge_validate` |
| **M4** | Admin 私有状态 | 用户详情 **新开 Tab「私有状态」**，位于「用户记忆」**右侧**；管理 `type=character_private`（Step6 `CharacterPrivateSettings`），同样 **KV + build_doc_id** CRUD |
| **M5** | 全局记忆搜索 | **方案 B**：`GET /api/admin/memories/global` 改为按 **user_id / 关键词** 检索 **Step6 user 向量**（**不含** `character_private`） |
| **M6** | 全局批量删除 | **保留** `batch-delete`；Body 为 **`doc_ids`**，**仅允许** `user_*`（禁止 `mem_*`） |
| **M7** | 记忆规则页 | **改造**：移除第一套字段；新增 **Step6 记忆总结 Prompt** + **全局用户记忆** Tab；**admin_config + Redis 热更** |
| **M8** | MySQL `memory` 表 | **方案 A**：**保留表结构**，本期接口 **不再读写**；不删表 |
| **M9** | H5「我的记忆」 | **只读**；展示 Step6 `user` 向量解析后的 **key / value**（可展示 `content` 整行） |
| **M10** | 第一套召回 | **全部下线**（含 `search_relevant_memories`、Agent 直连 `vector_service` 捞 `mem_*`）；**P1 修订**：Agent 召回侧亦不加 `mem_*` 运行时过滤，依赖 M2 清理 |
| **M11** | `memory_injected` | **方案 A**：`chat_send` 写入 user 行时 **恒为 `null`**；不再在 send 时做向量检索（见 §6.5） |
| **M12** | Step6 主流程 | **不改** `execute_step6` 编排顺序；仅 `build_step6_prompt` 改为读配置模板拼装 |
| **M13** | 检索安全垫 | ~~Step2 user 路过滤 `doc_id.startswith("mem_")`~~ → **P1 修订：取消该过滤**，Step2 user 路不做运行时 `mem_*` 过滤，依赖 M2 人工清理 |
| **M14** | 角色知识库 | `character_global` / `character_knowledge` **不在本期范围** |
| **M15** | relationship 标量 | `UserRealName` / `UserHobbyName` 等 **relationship 写回** 不变；**不**并入「用户记忆」列表 |
| **M16** | TD-022/023 | 本期实施后，在 `tech-debt.md` 标注 **第一套已下线**；TD-028/029 **不纳入本期** |
| **M17** | TD-024 设置页开关 | `memory_auto_extract` **本期不实现**；设置页改为 **只读说明行**（见 **C-07**） |
| **M18** | 发布粒度 | **一次发布**：后端过滤 + 停写 + 新 Admin API + 前端 Tab + Step6 Prompt 配置 + 契约更新；**M2 清理在发布前/发布窗口执行** |
| **M19** | H5 用户手动增删改 | **删除** `PUT/DELETE/POST /api/memory/*` 路由，仅保留 `GET /list`（见 **C-05**） |
| **M20** | Admin 用户记忆旧接口 | **删除** `GET/PUT/DELETE /users/{id}/memories*`；改用 **`user-memories` / `private-settings`**（见 **C-01、C-09**） |

## 2.2 需求细化确认（C-01~C-10，2026-05-31）

| 编号 | 决策 |
|------|------|
| **C-01** | Admin API：**`/api/admin/users/{user_id}/user-memories`**、**`.../private-settings`** + `{doc_id:path}`；**删除**旧 `/users/{id}/memories*` |
| **C-02** | `config_key` = **`step6_memory_prompt`**；**`GET/PUT /api/admin/step6-memory-prompt`**；**删除** `GET/PUT /api/admin/memory-rules` |
| **C-03** | Admin **PUT 仅改 value**；改 key = **DELETE + POST** |
| **C-04** | 保留 `memories/global` + `batch-delete`；在 **`memory-rules.html` 新增 Tab「全局用户记忆」**（仅 `type=user`） |
| **C-05** | H5 **删除**写路由；`memory.html` **只读** |
| **C-06** | **新建 `user_vector_memory_service`**（**不**扩展 `character_knowledge_service`） |
| **C-07** | 设置页：「记忆自动提取」改为 **只读说明**（如「对话结束后会自动整理成记忆，无需手动设置」），**移除 Toggle** |
| **C-08** | **`memory_rules` 后台不展示**；`admin_config` 历史行可保留，仅供 DB/运维查阅 |
| **C-09** | 旧 Admin `/users/.../memories*`：**确认删除**（无 410 废弃期） |
| **C-10** | Step6 Prompt：**保存即发布** + Pydantic/必填校验（**不做** persona 测试集/CONFIRM 门禁） |

## 2.3 复查补充确认（2026-05-31）

| 编号 | 决策 |
|------|------|
| **R-01** | 全局检索 **`user_id` 可选**；未指定用户时 DashVector `list_by_filter` **`top_k=300`**（常量，可配置化二期）；keyword 在内存子串过滤后再分页；UI **固定提示**：「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」 |

## 2.4 复查二次确认（P1~P10，2026-05-31）

> 本轮复查结合实际代码核对，修订/细化以下 10 项；与前文 M/C/R 冲突处**以本表为准**，并已就地修订对应章节。

| 编号 | 问题 | 决策 | 影响章节 |
|------|------|------|----------|
| **P1** | `mem_*` 与 Step6 `user` 同 `type=user`+`user_id`，`build_filter("user")` 无法区分 | **不做任何运行时过滤**，完全依赖 **M2 人工清理**；列表与召回侧均不加 `mem_*` 过滤（**推翻 M13/M10 的过滤要求**） | M10、M13、§6.1.3、§7.1 |
| **P3** | 用户记忆 / 私有状态两 Tab 共用单一可管理校验会跨类型误删 | 新增 **`is_user_manageable_doc_id(doc_id, *, user_id, expected_type)`**；`user-memories` 绑 `expected_type="user"`、`private-settings` 绑 `"character_private"`，校验 **type 与 user_suffix 双匹配**，两 Tab 互不互通 | §6.2.1 |
| **P9** | H5/Admin 单用户列表走 DashVector 后 cap/total 口径 | 单用户三处（H5 `list` / Admin `user-memories` / global 带 user_id）统一 **`USER_LIST_TOPK=500`**；`total` = **cap 内条数**（非库内真实总数），契约/前端注明上限 | §6.3.1、§6.2.2、§6.4.2 |
| **P10** | 第一套死代码处置 | **物理删除** `memory_service.extract_and_save` / `_deduplicate_and_save` 及其**专属私有方法**（`_extract_memories_from_llm` / `_parse_memory_list` / `_calculate_importance` / `_calc_expires_at`，删前核对无保留函数引用）+ `chat.py` 调用点；`add_memory_manual` / `update_memory` / `delete_memory` / `search_relevant_memories` / `get_user_memories` 标 **`@deprecated` 保留** | §6.1.1、§9 |
| **P6** | Step6 Prompt 拆 6 块与现硬编码混排不一一对应 | **DEFAULT 逐字复刻**现 `build_step6_prompt` 全文，按现状切入 6 块（`kv_field_rules` 含「多条分行规则」整段，`task_fields` 文本保留现有夹带细则）；验收基线＝**DEFAULT 拼出结果与旧硬编码逐字相等** | §6.6.1、§6.6.2 |
| **P2** | 读热配置需异步 | `build_step6_prompt` 改 **`async def`**，内部 `await get_active_config` + 三级回退（Redis→DB→DEFAULT）；唯一调用点 `step6_orchestrator._step6_pipeline`（async）加 `await`。**编排顺序不变，函数异步化属必要签名变更** | §6.6.1 |
| **P4** | global 带 user_id 的 top_k 未定值 | 带 `user_id` 复用 **`USER_LIST_TOPK=500`**；无 `user_id` 用 **`GLOBAL_LIST_TOPK_NO_USER=300`**（R-01） | §6.4.2 |
| **P5** | 新接口权限一致性 | 按领域分权：记忆规则页系列（`step6-memory-prompt` / `memories/global` / `batch-delete`）= **`super_admin + ai_trainer`**；用户详情 `user-memories` / `private-settings` = **`super_admin + ops_admin + ai_trainer`**（契约注明非不一致 bug） | §6.2.2、§6.4.2、§6.6.3 |
| **P8** | batch-delete 字段 | 请求 **`{doc_ids: list[str]}`**（保留 `min_length=1, max_length=100`）；响应 **`{deleted_count, failed_doc_ids}`**；**仅删 DashVector**；校验「`user_` 前缀 + `parse_doc_id` 合法」；日志 **module 仍用 `memory`**，「涉及用户」从 doc_id 的 `user_suffix` 解析聚合 | §6.4.2 |
| **P7** | M11 落地后 send 时死代码 | **彻底清理**：删 `chat_send` 内 `asyncio.gather`（`_get_recent_conversations`/`_get_latest_emotion`/`_get_embedding` 三件套，三者在 send 内本就无下游消费者）+ `_search_memories` 调用 + `memory_injected` 计算；`user_log.memory_injected=None`；并删孤儿函数 `_search_memories` / `_get_embedding`（经核实仅 `chat_send` 使用）及多余 `embedding_service` import | §6.1.1、§6.5 |

---

# 3. 与旧 PRD 的关系

| 旧决策 | 本 PRD |
|--------|--------|
| C5（TD-022 本期不做） | **由本 PRD 承接**，专门清偿双轨 |
| v6.1 四路检索 / Step6 写入 | **保持不变**，仅增加 user 路 `mem_*` 过滤与 Prompt 配置化 |

---

# 4. 目标架构（改动后）

## 4.1 数据流总览

```
对话成功闭环
  └─ asyncio.create_task(execute_step6)
        ├─ build_step6_prompt()  ← 读 admin_config「step6_memory_prompt」热配置
        ├─ LLM → parse_step6_output
        ├─ upsert_step6_vectors（UserSettings → user；CharacterPrivateSettings → character_private；等）
        └─ update_relationship_from_step6（标量字段，非本 PRD 列表范围）

下轮对话
  └─ Step1.5 → Step2（含 user 路 + character_private 路，过滤 mem_*）
        └─ Prompt 模块 5「用户记忆」← 仅 user 路结果

运营 / 用户查看
  ├─ H5 GET /api/memory/list                    → 只读 user 向量 KV
  ├─ Admin 用户详情「用户记忆」Tab                 → user 向量 CRUD（user-memories）
  ├─ Admin 用户详情「私有状态」Tab                 → character_private CRUD（private-settings）
  ├─ Admin 记忆规则页 Tab「全局用户记忆」          → GET /memories/global + batch-delete（仅 user_*）
  └─ Admin GET/PUT /step6-memory-prompt           → Step6 Prompt 热配置

已移除
  ├─ extract_and_save / memory 表 API / mem_* 写入
  ├─ GET/PUT/DELETE /api/admin/memory-rules
  ├─ GET/PUT/DELETE /api/admin/users/{id}/memories*
  ├─ PUT/DELETE/POST /api/memory/*（H5 写接口）
  └─ chat_send 时 memory_injected 向量快照
```

## 4.2 DashVector 用户侧文档约定（不变）

| memory_type | Step6 字段 | doc_id | user_id 过滤 |
|-------------|------------|--------|----------------|
| `user` | `UserSettings` | `user_{sha256(key)[:12]}_{userId}` | 是 |
| `character_private` | `CharacterPrivateSettings` | `character_private_{hash12}_{userId}` | 是 |

`fields`：`content`（`key：value`）、`stable_key`、`key_l1`、`key_l2`、`type`（由 client 合并）。

- **`key_l1` / `key_l2`**：由三层 key `XXX-XXX-XXX` 按 `-` 拆分派生（`key_l1` = 第一段，`key_l2` = 前两段），与 Step6/角色知识库写入一致，供 Step2 `key_l2 IN` 过滤；**非**独立存储行。

---

# 5. 功能改动说明

## 5.1 改动前（第一套仍在）

- 后置任务：`extract_and_save` → MySQL + `mem_*`  
- H5：记忆列表 CRUD → `memory` 表  
- Admin：用户记忆 CRUD → `memory` 表 + `mem_*` upsert  
- Admin：全局记忆 → MySQL `memory` 表查询（**无独立前端页，仅 API**）  
- Admin：记忆规则 → 提取 Prompt / 重要性 / 存储&合并阈值（**无效配置**）  
- `chat_send`：`memory_injected` = 旧向量检索结果  
- Agent：`_search_memories_for_agent` → `vector_service` 同池检索  

## 5.2 改动后（本 PRD 目标态）

| 能力 | 改动后行为 |
|------|------------|
| 对话写入 | **仅** Step6 异步写入 |
| 对话召回 | Step2 user 路（+ 过滤 `mem_*`）；Prompt 模块 5 不变 |
| H5 记忆页 | **只读** KV 列表 |
| H5 设置页 | **记忆整理**只读说明，无 `memory_auto_extract` Toggle |
| Admin 用户详情 | **用户记忆** + **私有状态** 两 Tab，KV CRUD |
| Admin 记忆规则页 | **Step6 Prompt** + **向量数据库** + **全局用户记忆** 三 Tab |
| Admin 全局 API | DashVector `type=user`；`batch-delete` 仅 `user_*` doc_ids |
| `memory` 表 | 无接口读写；表保留 |
| `memory_injected` | 新消息 **恒 null** |

---

# 6. 功能详细逻辑

## 6.1 下线第一套写入与召回

### 6.1.1 停止写入

- 删除 `chat.py` → `_post_bundle_success_tasks` 内 `memory_service.extract_and_save(...)` 调用。  
- **P10 处置**：**物理删除** `memory_service.extract_and_save`、`_deduplicate_and_save` 及其**专属私有方法**（`_extract_memories_from_llm` / `_parse_memory_list` / `_calculate_importance` / `_calc_expires_at`——删前核对无保留函数引用，避免 NameError）。这两段是问题二（无差别 `delete` 误伤 `user_*`）的根因，本期铲除。  
- 其余 `add_memory_manual` / `update_memory` / `delete_memory` / `search_relevant_memories` / `get_user_memories` **不再被路由调用** → 标 **`@deprecated` 保留**，物理清理留作下期。

### 6.1.2 API 变更清单

| 接口 | 处理 |
|------|------|
| `GET /api/memory/list` | **改造**为只读 Step6 user 列表（见 6.3），由 `user_vector_memory_service` 提供数据 |
| `PUT/DELETE/POST /api/memory/*` | **删除路由**（C-05）；同 PR 前端不再调用 |
| `GET/PUT/DELETE /api/admin/users/{id}/memories*` | **删除**（C-01、C-09） |
| `GET/POST/PUT/DELETE .../user-memories` | **新增**（user 向量 CRUD） |
| `GET/POST/PUT/DELETE .../private-settings` | **新增**（character_private CRUD） |
| `GET/PUT /api/admin/memory-rules` | **删除**（C-02） |
| `GET/PUT /api/admin/step6-memory-prompt` | **新增**（C-02） |
| `GET /api/admin/memories/global` | **改造**为向量检索（6.4）；去掉 `start_date`/`end_date`/`source` |
| `DELETE /api/admin/memories/batch-delete` | **改造**为 `{ "doc_ids": [...] }`，仅 `user_*` |

### 6.1.3 召回侧

| 位置 | 改动 |
|------|------|
| `multi_vector_retrieval_service` | **P1 修订**：~~`user_results` 写回前过滤 `id.startswith("mem_")`~~ → **不加过滤**，依赖 M2 清理 |
| `agent_service._search_memories_for_agent` | **不再**依赖 MySQL `memory` 校验；**P1 修订**：~~同过滤 `mem_*`~~ → **不加过滤**，依赖 M2 清理 |
| `chat.py` `_search_memories` | **删除调用并删除函数**（配合 M11/P7，已确认仅 `chat_send` 使用） |
| `memory_service.search_relevant_memories` | 无调用方 → 标 `@deprecated` 保留（P10） |

---

## 6.2 Admin 用户向量 CRUD

### 6.2.1 服务层（C-06）

**新建 `backend/services/user_vector_memory_service.py`**（`UserVectorMemoryService`），**不**扩展 `character_knowledge_service`。

复用 `character_knowledge_validate` 与角色库相同约定：

- `validate_key` / `validate_value` / `build_doc_id` / `build_content`  
- 写入 fields 须含 `stable_key`、`key_l1`、`key_l2`（逻辑与 `character_knowledge_service._build_knowledge_fields` / Step6 upsert **保持一致**；本期可不抽公共模块，但行为须一致）  
- `dashvector_client.upsert` / `delete` / `list_by_filter`  

**差异**：

| 项 | 角色知识库 | 用户记忆 / 私有状态 |
|----|------------|---------------------|
| memory_type | `character_global` / `character_knowledge` | `user` / `character_private` |
| user_suffix | `0` | `str(user_id)` |
| list filter | `build_filter(mt, None, [])` | `build_filter(mt, user_id, [])` |
| 可管理 doc_id | `is_admin_manageable_doc_id`（角色级） | **P3：新函数 `is_user_manageable_doc_id(doc_id, *, user_id, expected_type)`**，校验 `parse_doc_id` 的 **type == expected_type**（`user` 或 `character_private`）**且 user_suffix == str(user_id)**；`user-memories` 接口固定传 `expected_type="user"`、`private-settings` 固定传 `"character_private"`，**两 Tab 互不互通** |

### 6.2.2 Admin API（已定路径，C-01）

**用户记忆（user）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users/{user_id}/user-memories` | keyword、page、page_size；返回 `list[{ doc_id, key, value, content }]` |
| POST | 同上 | Body：`{ key, value }` → validate → upsert |
| PUT | `/api/admin/users/{user_id}/user-memories/{doc_id:path}` | **仅改 value**（C-03）；Body：`{ value }` |
| DELETE | 同上 | 删 DashVector 文档 |

**私有状态（character_private）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users/{user_id}/private-settings` | 同上 |
| POST/PUT/DELETE | 同上结构 | memory_type=`character_private`；PUT 同样仅 value |

**权限**：`super_admin` / `ops_admin` / `ai_trainer`；写操作记 `admin_operation_logs`（`module` 建议区分 `user_memory` / `private_setting`）。

### 6.2.3 用户详情页 Tab 顺序

在 `admin/pages/user-detail.html` 中，**「用户记忆」右侧** 插入 **「私有状态」**：

```
… | 用户记忆 | 私有状态 | …
```

- **用户记忆**：表格列 `key` / `value` / 操作（编辑 value、删除）；新增条目（三层 key + value）。  
- **私有状态**：同上；页内说明「角色对该用户的私有设定，非用户自传事实」。  
- 主键 **`doc_id`**；**不再**使用 `memory_id`。

---

## 6.3 H5 只读记忆列表

### 6.3.1 接口

`GET /api/memory/list` **保留路径**，响应结构调整：

```json
{
  "code": 0,
  "data": {
    "total": 10,
    "page": 1,
    "page_size": 20,
    "list": [
      {
        "doc_id": "user_a3f8c2e91b04_123",
        "key": "偏好-饮食-口味",
        "value": "不太能吃辣",
        "content": "偏好-饮食-口味：不太能吃辣"
      }
    ]
  }
}
```

- **不再返回** `importance_score`、`source`、`id`（MySQL memory_id）。  
- 可选返回 `updated_at`：若 DashVector 无该字段，则不返回或仅展示「来自对话整理」静态说明。  
- **P9 取数口径**：由 `user_vector_memory_service` 走 `list_by_filter(build_filter("user", user_id, []), top_k=USER_LIST_TOPK)`，**`USER_LIST_TOPK=500`**；`total` = **cap 内条数**（内存分页，非库内真实总数），超过 500 条的尾部不显示（单用户极端场景，概率极低）。与 Admin `user-memories`、global 带 user_id 共用同一常量。  
- **P1**：H5 list **不过滤** `mem_*`（清理前可能短暂展示脏数据，接受）。

### 6.3.2 前端 `memory.html`

- 移除：添加、编辑、删除、保存及对应 API 调用。  
- 展示：卡片 **key** 加粗 + **value** 正文；空态「林小梦还在对话中了解你，暂无整理好的记忆」。  
- 顶部说明：「以下内容由对话自动整理，暂不支持手动修改」。

### 6.3.3 前端 `settings.html`（C-07）

- **删除**「记忆自动提取」Toggle 及对 `memory_auto_extract` 的 `PUT`。  
- **改为只读一行**，示例文案：标题「记忆整理」；说明「对话结束后会自动整理成记忆，无需手动设置」。  
- 「主动消息推送」Toggle **不在本期**（仍属 TD-024 其他项）。

---

## 6.4 全局用户记忆（M5/M6 + C-04）

### 6.4.1 定位

- **用途**：在 **已知关键词、可选 user_id** 时，**跨用户** 检索 `type=user` 向量（运维排查、清脏数据）。  
- **不是** UserSettings / CharacterPrivateSettings 的主维护入口；后者在 **用户详情** 两 Tab。  
- **不包含** `character_private`（必须带 `user_id` 进用户详情查看）。

### 6.4.2 API（含 R-01）

`GET /api/admin/memories/global`：

| 参数 | 行为 |
|------|------|
| `user_id` | **可选**（R-01）。有则 `build_filter("user", user_id, [])`，**`top_k = USER_LIST_TOPK = 500`**（P4，与单用户场景一致）；**无**则 `build_filter("user", None, [])`，**`top_k = GLOBAL_LIST_TOPK_NO_USER = 300`**（P4） |
| `keyword` | 对 `key`/`value`/`content` 子串过滤（**先** `list_by_filter` 取候选集，**再**内存筛 keyword） |
| `page` / `page_size` | 对 keyword 过滤后的结果分页 |

**R-01 语义**：

- 未传 `user_id` 时，**不**保证扫全库；仅在最多 **300** 条 `type=user` 文档上做 keyword 与分页。  
- 响应可选增加 `truncated: true`（当未传 `user_id` 且命中上限时），供前端展示与提示文案一致。  
- **禁止**为全局接口无限增大 `top_k`；角色知识库 `LIST_TOPK=500` **不**自动沿用至跨用户全局（全局无 user_id 时用 **300**）。

**移除参数**：`start_date`、`end_date`、`source`（第一套 MySQL 专用）。

响应 `list` 元素：`doc_id`、`user_id`、`key`、`value`、`content`（见 §8.3）。

`DELETE /api/admin/memories/batch-delete`（P8）：

- Body：`{ "doc_ids": ["user_...", ...] }`（保留 `min_length=1, max_length=100`）  
- 校验：每条 `doc_id` 以 `user_` 开头且 `parse_doc_id` 合法（非法/非 `user_` 前缀计入 `failed_doc_ids`，不中断其余）  
- **仅删 DashVector**（不再有 MySQL 软删与 `affected_user_ids`）  
- 响应：**`{ deleted_count, failed_doc_ids }`**  
- 操作日志：`log_operation` 的 **module 仍用 `memory`**；「涉及用户」从各 `doc_id` 的 `user_suffix` 解析聚合后写入 `target_description`  
- **权限（P5）**：`super_admin + ai_trainer`（记忆规则页领域）

### 6.4.3 管理页（C-04 + R-01）

在 `admin/pages/memory-rules.html` 增加 Tab **「全局用户记忆」**：

- 筛选：`user_id`（选填）、`keyword`、分页列表  
- **固定提示**（R-01）：未填用户 ID 时展示——「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」；若 API 返回 `truncated: true` 可强化展示  
- 列：`user_id`、`key`、`value`、操作（跳转用户详情可选）  
- 勾选 + **批量删除** → `batch-delete`  
- 与「Step6 记忆 Prompt」「向量数据库」并列，默认 Tab 仍为 Step6 Prompt

---

## 6.5 `memory_injected` 恒为 null — 范围评估（M11）

| 维度 | 说明 |
|------|------|
| **改动点（P7）** | `chat.py` `chat_send`：删除整段 `asyncio.gather(_get_recent_conversations / _get_latest_emotion / _get_embedding)`（三者在 send 内本就无下游消费者）+ `_search_memories` 调用 + `memory_injected` 计算；创建 user 行时 `memory_injected=None`；保留 `check_content` / `_detect_persona_risk` / 入队落库。并删除孤儿函数 `_search_memories`、`_get_embedding`（经核实仅 `chat_send` 使用）及多余 `embedding_service` import。 |
| **不影响** | `_execute_llm_bundle` 内 Step2 → `build_chat_prompt(memories=...)` **仍正常**；Step6 写入 **不变**。 |
| **数据库** | `conversation_log.memory_injected` 列 **保留**；新行为恒 null，旧数据历史保留。 |
| **Admin 对话列表** | 若展示 `memory_injected`，新记录为空；契约注明「仅历史字段，已停用」。 |
| **统计/报表** | 当前无强依赖该字段的核心指标；**无额外开发**。 |
| **性能** | send 少一次 embedding + 向量检索，**略优**。 |
| **风险** | 低；与真实 Prompt 注入已脱钩（bundle 路径为准）。 |

---

## 6.6 记忆规则页 → Step6 Prompt 可配热更（M7 + C-02/C-08/C-10）

### 6.6.1 配置存储

| 项 | 约定 |
|----|------|
| config_key | **`step6_memory_prompt`**（`admin_config` 表） |
| Redis | `active_config:step6_memory_prompt`，TTL=3600s |
| 读取点 | `memory_llm_service.build_step6_prompt()`：Redis → DB 生效版 → **代码 DEFAULT**。**P2：函数改 `async def`**，内部 `await admin_config_service.get_active_config("step6_memory_prompt")` + 三级回退；唯一调用点 `step6_orchestrator._step6_pipeline`（async）改 `await build_step6_prompt(...)`，**编排顺序不变** |
| 废弃 key | **`memory_rules`**：DB 历史行可保留；**后台不展示、不提供 API**（C-08） |

### 6.6.2 结构化 JSON Schema

运行时 **动态注入** 区块（不可配置覆盖，防破坏链路）：

- `【当前时间】` ← `_generate_time_description()`  
- `【人格设定】` ← snapshot.persona_text  
- `【关系状态】` ← level_name、relation_description、称呼、印象、策略、态度  
- `【近期历史摘要】` ← recent_conversations  
- `【本轮完整对话】` ← user_input + ai_reply  

**可配置区块**（后台表单 + 可选「高级 JSON」）：

```json
{
  "system_instruction": "你是林小梦，请对本轮对话进行总结…",
  "output_format_rules": "仅输出合法 JSON…无内容时输出「无」…",
  "kv_field_rules": "多行 key：value；三层 key；分行规则…",
  "task_fields": {
    "InnerMonologue": "…不超过150字，不落库…",
    "CharacterPublicSettings": "…",
    "CharacterPrivateSettings": "…",
    "CharacterKnowledges": "…",
    "UserSettings": "…",
    "UserRealName": "…",
    "UserHobbyName": "…",
    "UserDescription": "…",
    "CharacterPurpose": "…",
    "CharacterAttitude": "…",
    "RelationDescription": "…"
  },
  "merge_rules": "相同 key 合并新旧 value…",
  "few_shot_example": "【输出示例】\n{ ... 完整 JSON 示例 ... }"
}
```

`build_step6_prompt` 拼装顺序与现硬编码 **一致**：

`system_instruction` → `output_format_rules` + `kv_field_rules` → 动态块 → `【任务】` + 按固定顺序拼接 `task_fields` 1~11 → `merge_rules` → `few_shot_example`。

**P6（DEFAULT 逐字复刻，防漂移）**：DEFAULT 模板以现 `build_step6_prompt` 输出为基准**逐字切块**——块的语义边界服从「复刻现状」而非追求纯净（如「多条信息分行规则」整段归 `kv_field_rules`、`task_fields` 文本保留现有夹带的「禁止同一行串联」等细则、`merge_rules` 含错误/正确示例两行）。**验收基线：DEFAULT 配置拼出的 prompt 与旧硬编码 `build_step6_prompt` 输出逐字相等**。`task_fields` 必须固定 11 项且顺序与 `_ALL_FIELD_NAMES` 一致；保存校验须覆盖 6 块 + 11 个 `task_fields` 子项非空，缺项会致 LLM 漏输出对应字段。

### 6.6.3 管理页 `memory-rules.html` 改造

| Tab | 内容 |
|-----|------|
| **Step6 记忆 Prompt**（默认） | 分区表单；**保存** → `PUT /api/admin/step6-memory-prompt`（**保存即发布**，C-10） |
| **向量数据库** | **保留**现 Tab（`vector-db-config`） |
| **全局用户记忆** | 见 §6.4.3 |

**删除**第一套 UI 与接口：

- 记忆提取 Prompt、重要性评分、存储阈值、检索/合并相似度阈值  
- `GET/PUT /api/admin/memory-rules`  
- **不展示** 历史 `memory_rules` 配置（C-08）

### 6.6.4 发布与回滚（C-10）

- **保存即发布**：`publish_config` 更新 MySQL + Redis（~100ms），**不要求**重启 backend。  
- **门禁**：**Pydantic 校验 + 必填字段非空**；**不做** persona 测试集 / CONFIRM 卡点。  
- **回滚**：切回 `admin_config` 上一生效版本，或运行时 fallback **DEFAULT**。  
- 运行时读配置失败 → **DEFAULT** + `logger.error`。

---

# 7. 边界情况

### 7.1 上线前未清干净 `mem_*`（P1 修订）

- **运行时不做任何 `mem_*` 过滤**（P1=C-1）：`mem_*` 与 Step6 `user` 文档同 `type=user` + 带 `user_id`，`build_filter("user", …)` 与召回路均会命中。  
- 因此清理不彻底时，残留 `mem_*` **可能短暂出现**在 H5「我的记忆」/ Admin 用户记忆 / 全局列表，且会进入 Step2/Agent 召回 → 属**已知风险，靠 M2 人工清理消除**，非 bug。  
- `batch-delete` 仅允许 `user_*` 前缀（P8），**不能**通过 UI 删除残留 `mem_*`；如有残留须**人工**在 DashVector 侧清理。  
- 运维检查：上线后对抽样 user_id `list_by_filter` 确认无 `mem_` 前缀文档。

### 7.7 全局检索未填 user_id（R-01）

- 运营仅用 keyword 跨库搜时，**最多 300 条**候选，可能漏掉未进入候选集的记忆 → 契约与 UI 提示已说明，**非 bug**。  
- 需某用户全量排查时，应 **填写 user_id** 或进入该用户详情「用户记忆」Tab。

### 7.2 Admin 手改 key 与 Step6 自动写入冲突

- 同 stable key → **同 doc_id** → upsert **覆盖**（与 Step6 一致）。  
- 运营手改 value 后，下轮 Step6 若输出同 key，按 Prompt **合并规则** 可能再次覆盖 → 契约注明「手动修改可能被后续对话总结覆盖」。  
- **改 key**：Admin **DELETE + POST**，不提供 PUT 改 key（C-03）。

### 7.3 删除私有状态 / 用户记忆

- **仅删 DashVector**，无 MySQL 行。  
- **不** 自动修改 `relationship` 标量（称呼等仍走 Step6 另一字段）。

### 7.4 Step6 Prompt 配置错误

- 发布时 JSON 校验失败 → **拒绝保存**。  
- 运行时读配置失败 → **fallback DEFAULT** + `logger.error`。  
- LLM 输出仍走 `parse_step6_output`；非法 key 行 **跳过写入**（现逻辑保持）。

### 7.5 H5 旧客户端仍调写接口

- 路由已 **删除** → HTTP **404**；同 PR 静态资源已改为只读，正常用户仅调用 `GET /list`。

### 7.6 `character_private` 与「用户记忆」边界

| Tab | type | 典型 key 示例 |
|-----|------|----------------|
| 用户记忆 | `user` | `偏好-饮食-口味`、`经历-工作-岗位` |
| 私有状态 | `character_private` | `用户-信任-等级`、`策略-回复-口吻` |

避免运营误把用户事实写入私有状态 Tab（页内加一行说明即可）。

---

# 8. 数据结构

## 8.1 MySQL

| 表 / key | 本期 |
|----------|------|
| `memory` | **保留表结构**，无接口读写 |
| `admin_config.step6_memory_prompt` | **新增/生效**配置 |
| `admin_config.memory_rules` | **保留历史行**；**无 API、无 UI**（C-08） |

## 8.2 DashVector（用户相关）

| type | 写入方 | Admin 可管 |
|------|--------|------------|
| `user` | Step6 + Admin 用户记忆 Tab + 全局 Tab 删 | ✅ |
| `character_private` | Step6 + Admin 私有状态 Tab | ✅（仅用户详情） |
| `mem_*` | **停用** | ❌ 清理删除 |

## 8.3 API 响应统一（列表元素）

```typescript
type UserVectorEntry = {
  doc_id: string;
  key: string;
  value: string;
  content: string;  // key + "：" + value
  user_id?: number; // 全局搜索时带
};
```

---

# 9. 改造范围与文件索引

| 文件 | 改动内容 | 改动量 |
|------|----------|--------|
| `backend/routers/chat.py` | 去掉 `extract_and_save` 调用；`memory_injected=None`；**P7** 删 `chat_send` 内 gather 三件套 + `_search_memories`/`_get_embedding` 孤儿函数 + 多余 import | 小 |
| `backend/services/memory_service.py` | **P10** 物理删 `extract_and_save`/`_deduplicate_and_save` + 专属私有方法；其余标 `@deprecated` 保留 | 中 |
| `backend/services/user_vector_memory_service.py` | **新建** user / character_private CRUD + global 列表辅助 | 中 |
| `backend/services/memory_llm_service.py` | `build_step6_prompt` 读热配置 + DEFAULT 回退 | 中 |
| `backend/routers/memory.py` | GET 改造；**删除**写路由 | 小 |
| `backend/routers/admin/users.py` | **删除**旧 memories；挂载 user-memories / private-settings | 中 |
| `backend/routers/admin/memory_mgmt.py` | global/batch-delete 改造；**删** memory-rules；**增** step6-memory-prompt | 中 |
| `backend/services/multi_vector_retrieval_service.py` | **P1：不过滤 `mem_*`**（依赖 M2 清理），本期可零改动 | 无～小 |
| `backend/services/agent_service.py` | `_search_memories_for_agent` 不再依赖 MySQL 校验；**P1：不加 `mem_*` 过滤** | 小 |
| `backend/utils/character_knowledge_validate.py` | **P3** 新增 `is_user_manageable_doc_id(doc_id, *, user_id, expected_type)` | 小 |
| `frontend/pages/memory.html` | 只读 KV UI | 中 |
| `frontend/pages/settings.html` | 记忆整理只读说明（C-07） | 小 |
| `admin/pages/user-detail.html` | 用户记忆改造 + 私有状态 Tab | 中 |
| `admin/pages/memory-rules.html` | Step6 Prompt + 全局用户记忆 Tab；删第一套 | 中 |
| `docs/contract.md` | 记忆模块、Admin 路径、下线说明 | 中（实现时同步） |
| `docs/tech-debt.md` | TD-022/023 状态更新 | 小 |
| `tests/test_chat.py` 等 | 去掉 extract mock；新增向量 CRUD 单测 | 中 |

**明确不改（本期）**：

- `step6_orchestrator.py` 编排（除 prompt 来源）  
- `upsert_step6_vectors` / `parse_kv_lines` 核心逻辑  
- Step1.5 / Step2 除 user 路过滤外  
- 角色知识库 `knowledge_mgmt` / `character_knowledge_service` 行为  
- TD-028 / TD-029 / TD-026；TD-024 除 C-07 文案外  
- `_build_knowledge_fields` 抽公共模块（可选二期）

---

# 10. 技术债与契约

| 条目 | 本期处理 |
|------|----------|
| **TD-022** | 第一套下线后标 **已清偿**（附实现 PR 号） |
| **TD-023** | 跨源合并问题随 `extract_and_save` 移除缓解；Admin 仅操作 `user_*` / `character_private_*` |
| **TD-024** | **部分**：设置页记忆项改为只读说明（C-07）；`GET/PUT /api/user/settings` 全量实现仍待 |
| **TD-028/029** | 不纳入 |
| **contract.md** | 实现同 PR 更新；废弃第一套记忆接口与 `memory_rules` API |

---

# 11. 上线与运维检查项

## 11.1 发布前（M2 / M6）

| 步骤 | 操作 |
|------|------|
| 1 | MySQL：清空或归档 **`memory` 表** 全部业务数据（表结构保留） |
| 2 | DashVector：删除 **`doc_id` 以 `mem_` 开头** 的文档 |
| 3 | 抽样验证：任一测试用户 `list user` 无 `mem_*` |
| 4 | 备份：清理前导出 MySQL `memory` + 向量 doc_id 列表备查 |

## 11.2 发布后功能验收

| # | 验收项 |
|---|--------|
| 1 | 完成一轮对话 → Step6 成功 → Admin「用户记忆」/「私有状态」可见新 KV |
| 2 | H5 记忆页只读；设置页为记忆整理说明、无 Toggle |
| 3 | 下轮对话 Prompt 模块 5 能召回相关 user 记忆 |
| 4 | Admin 手增/改/删 user 向量后，下轮检索结果同步 |
| 5 | 记忆规则页「全局用户记忆」：可选 user_id + 关键词；未填 user_id 时见 R-01 提示与 ≤300 条；批量删仅 `user_*` |
| 6 | Step6 Prompt 保存发布 → **无需重启** → 新对话 Step6 可观测变化 |
| 7 | 新 user 行 `memory_injected` 为 null |
| 8 | Agent 主动消息不再依赖 `mem_*` 召回 |

## 11.3 回归范围

- Step1.5 / Step2 四路检索单测 + 冒烟  
- Step6 upsert 单测  
- 角色知识库 CRUD 不受影响  
- Admin 发布 Step6 Prompt 后 Redis 命中  

---

*文档版本 v1.2：v1.1 + 复查项 R-01（全局检索 user_id 可选、top 300 + UI 提示，2026-05-31）。*

*文档版本 v1.3：v1.2 + 复查 P1~P10（§2.4，2026-05-31）。要点：P1 取消所有 `mem_*` 运行时过滤（推翻 M13/M10，改靠 M2 人工清理，§7.1 同步修订）；P3 新增 `is_user_manageable_doc_id` 带 `expected_type` 隔离两 Tab；P9/P4 列表 cap 统一（单用户 500、全局无 user_id 300）；P10 物理删第一套写入/合并危险函数、其余标 deprecated；P6 Step6 Prompt DEFAULT 逐字复刻；P2 `build_step6_prompt` 异步化；P5 按领域分权；P8 batch-delete 改 `doc_ids`/`failed_doc_ids` 仅删向量；P7 清理 send 时死代码。*
