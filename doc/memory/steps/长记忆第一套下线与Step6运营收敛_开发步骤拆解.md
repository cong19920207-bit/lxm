# 长记忆第一套下线与 Step6 运营收敛 开发步骤拆解

> PRD 来源：`doc/mem_doc/PRD-长记忆第一套下线与Step6运营收敛.md`（v1.3，M1~M20 + C-01~C-10 + R-01 + P1~P10）
> 进度文档：`docs/progress/长记忆第一套下线与Step6运营收敛_progress.md`
> 契约文档：`docs/contract.md`
> 生成日期：2026-05-31
> 发布粒度（M18）：**一次发布**——本拆解将一次发布拆为 16 个可独立验证的开发单元，按依赖顺序串行落地，最终合并为同一 PR / 同一发布窗口。

---

## 1. 功能清单

> 逐条来自 PRD，不增不减。优先级：`[核心]` 直接服务「下线 + 收敛」主目标；`[扩展]` 运营能力补齐；`[可选]` 文档/运维收尾。

| # | 功能点 | 来源 | 优先级 | 依赖 |
|---|--------|------|--------|------|
| F1 | 新增 `is_user_manageable_doc_id(doc_id, *, user_id, expected_type)` 双匹配校验 | P3 / §6.2.1 | [核心] | 无 |
| F2 | 新建 `user_vector_memory_service`（user / character_private CRUD + 列表辅助） | C-06 / §6.2.1 | [核心] | F1 |
| F3 | Admin 用户记忆 / 私有状态 API（`user-memories` / `private-settings`）+ 删除旧 `/users/{id}/memories*` | C-01/C-09/P5/P9 / §6.2.2 | [核心] | F2 |
| F4 | H5 `GET /api/memory/list` 改造为只读 Step6 user 列表 + 删除 H5 写路由 | M9/C-05/P9 / §6.3.1 | [核心] | F2 |
| F5 | 全局用户记忆 API：`memories/global` 改向量检索 + `batch-delete` 改 `doc_ids` | M5/M6/R-01/P4/P8/P5 / §6.4.2 | [扩展] | F2 |
| F6 | `build_step6_prompt` 异步化 + 读 `step6_memory_prompt` 热配置 + DEFAULT 逐字复刻 | M7/M12/C-08/P2/P6 / §6.6.1-2 | [核心] | 无 |
| F7 | `GET/PUT /api/admin/step6-memory-prompt` + Pydantic 校验 + 删除 `memory-rules` API | C-02/C-10/P5 / §6.6.1/§6.6.4 | [扩展] | F6 |
| F8 | 下线第一套写入：删 `extract_and_save` 调用 + 物理删危险函数 + 其余标 `@deprecated` | M1/M10/P10 / §6.1.1 | [核心] | 无 |
| F9 | `memory_injected` 恒 null + `chat_send` send 时死代码清理（P7） | M11/P7 / §6.5 | [核心] | 无 |
| F10 | 召回侧 P1 确认：`multi_vector_retrieval_service` / `agent_service` 不加 `mem_*` 过滤 | M10/M13/P1 / §6.1.3/§7.1 | [核心] | 无 |
| F11 | 前端 `memory.html` 改为只读 KV 卡片列表 | M9 / §6.3.2 | [扩展] | F4 |
| F12 | 前端 `settings.html`「记忆自动提取」改只读说明、移除 Toggle | M17/C-07 / §6.3.3 | [扩展] | 无 |
| F13 | 前端 `user-detail.html` 用户记忆改造 + 新增私有状态 Tab | M3/M4 / §6.2.3 | [扩展] | F3 |
| F14 | 前端 `memory-rules.html`：Step6 Prompt Tab + 全局用户记忆 Tab + 删第一套 UI | M7/C-04/R-01 / §6.6.3/§6.4.3 | [扩展] | F5、F7 |
| F15 | 契约文档 + 技术债（TD-022/023/024）同步更新 | M16/§10 | [可选] | F1~F14 |
| F16 | 上线前 / 上线后运维清理与验收 checklist（人工，非代码） | M2/M18/§11 | [可选] | F1~F15 |

---

## 2. 开发环节总览

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-001 | 新增 `is_user_manageable_doc_id` 双匹配校验 | `backend/utils/character_knowledge_validate.py` | 无 | 低 |
| STEP-002 | 新建 `user_vector_memory_service` | `backend/services/user_vector_memory_service.py` | STEP-001 | 中 |
| STEP-003 | Admin 用户记忆 / 私有状态 API + 删旧记忆接口 | `backend/routers/admin/users.py`（+ 可能新文件） | STEP-002 | 中 |
| STEP-004 | H5 `GET /api/memory/list` 只读改造 + 删写路由 | `backend/routers/memory.py` | STEP-002 | 中 |
| STEP-005 | 全局用户记忆 API 改造（global + batch-delete） | `backend/routers/admin/memory_mgmt.py` | STEP-002 | 中 |
| STEP-006 | `build_step6_prompt` 异步化 + 热配置 + DEFAULT 复刻 | `backend/services/memory_llm_service.py`、`backend/services/step6_orchestrator.py` | 无 | 高 |
| STEP-007 | `step6-memory-prompt` API + 删 `memory-rules` API | `backend/routers/admin/memory_mgmt.py` | STEP-006 | 中 |
| STEP-008 | 下线第一套写入 + 物理删危险函数 | `backend/routers/chat.py`、`backend/services/memory_service.py` | 无 | 中 |
| STEP-009 | `memory_injected` 恒 null + send 死代码清理 | `backend/routers/chat.py` | 无 | 中 |
| STEP-010 | 召回侧 P1 确认（不加 `mem_*` 过滤） | `backend/services/multi_vector_retrieval_service.py`、`backend/services/agent_service.py` | 无 | 低 |
| STEP-011 | 前端 `memory.html` 只读 KV 列表 | `frontend/pages/memory.html` | STEP-004 | 中 |
| STEP-012 | 前端 `settings.html` 记忆整理只读说明 | `frontend/pages/settings.html` | 无 | 低 |
| STEP-013 | 前端 `user-detail.html` 用户记忆 + 私有状态 Tab | `admin/pages/user-detail.html` | STEP-003 | 中 |
| STEP-014 | 前端 `memory-rules.html` 三 Tab 改造 | `admin/pages/memory-rules.html` | STEP-005、STEP-007 | 中 |
| STEP-015 | 契约 + 技术债同步 | `docs/contract.md`、`docs/tech-debt.md` | STEP-001~014 | 中 |
| STEP-016 | 上线前/后运维清理与验收 checklist | 运维（DashVector / MySQL） | STEP-001~015 | 低 |

> 说明：STEP-006~010、STEP-012 与前段（001~005）无强代码依赖，可并行开发；为保证「一次发布」可回归，建议合并前统一跑回归。

---

## 3. 开发提示词

---

### [STEP-001] 新增 `is_user_manageable_doc_id` 双匹配校验

**目标**：在公共校验工具中新增用户级（user / character_private）可管理性判定函数，校验 `type` 与 `user_suffix` 双匹配，使两个 Tab 互不互通（P3）。

---

**前置条件检查**：

> 无前置条件。

---

**需要参考的文件**：
- `@backend/utils/character_knowledge_validate.py` — 现有 `parse_doc_id` / `is_admin_manageable_doc_id` / `build_doc_id` 约定，新函数在其后追加
- `@backend/constants.py` — `MEMORY_TYPE_USER` / `MEMORY_TYPE_CHARACTER_PRIVATE` / `VALID_MEMORY_TYPES` 常量

**环境/数据前提**：
- `parse_doc_id(doc_id)` 已返回 `(memory_type, user_suffix)`，`user_suffix` 为 `"0"`（角色级）或用户 ID 字符串

---

**需求原文引用**：
> P3：新增 `is_user_manageable_doc_id(doc_id, *, user_id, expected_type)`；`user-memories` 绑 `expected_type="user"`、`private-settings` 绑 `"character_private"`，校验 **type 与 user_suffix 双匹配**，两 Tab 互不互通。（§6.2.1）

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| doc_id | str | DashVector 文档 ID（`{type}_{hash12}_{user_suffix}`） | 需求文档原文 |
| user_id | int | 当前用户 ID（关键字参数） | 需求文档原文 |
| expected_type | str | 期望的 memory_type（`"user"` 或 `"character_private"`，关键字参数） | 需求文档原文 |
| 返回值 | bool | type==expected_type 且 user_suffix==str(user_id) 时为 True | 需求文档原文 |

---

**开发任务**：
1. 在 `character_knowledge_validate.py` 新增 `is_user_manageable_doc_id(doc_id: str, *, user_id: int, expected_type: str) -> bool`。
2. 内部调用 `parse_doc_id(doc_id)`：为 None 返回 `False`。
3. 解析出 `(memory_type, user_suffix)` 后，校验 `memory_type == expected_type` **且** `user_suffix == str(user_id)`，两者同时满足才返回 `True`。
4. 可定义模块常量 `USER_MANAGEABLE_TYPES = frozenset({MEMORY_TYPE_USER, MEMORY_TYPE_CHARACTER_PRIVATE})`，对 `expected_type` 不在该集合时返回 `False`（防御）。
5. 函数加中文 docstring（UTF-8），说明 P3 双匹配语义。

**不在本环节范围内**：
- 不修改 `is_admin_manageable_doc_id`（角色级，保持现状）
- 不新建 service / 路由（由 STEP-002/003 负责）
- 不抽 `_build_knowledge_fields` 公共模块（M 明确二期可选）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常 user 匹配 | `user_xxx_123`, user_id=123, expected_type="user" | True |
| 正常 private 匹配 | `character_private_xxx_123`, user_id=123, expected_type="character_private" | True |
| 跨类型误删拦截 | `character_private_xxx_123`, user_id=123, expected_type="user" | False |
| user 不匹配 | `user_xxx_456`, user_id=123, expected_type="user" | False |
| 角色级 doc_id | `character_global_xxx_0`, user_id=123, expected_type="user" | False |
| 非法 doc_id | `""` / `mem_5` / 段数不符 | False |

---

**完成标志**：
- [ ] 函数可正常运行
- [ ] 单元测试全部通过
- [ ] 回归测试通过（`is_admin_manageable_doc_id` 行为不变）
- [ ] 契约文档已更新（如有）
- [ ] 进度文档已更新：将 **STEP-001** 状态更新为 ✅

---

**完成后执行**：

> 1. 打开 `docs/progress/长记忆第一套下线与Step6运营收敛_progress.md`
> 2. 将 STEP-001 状态从 ⬜ 改为 ✅
> 3. 填写完成日期
> 4. 提示开发者：**下一个环节是 [STEP-002] 新建 `user_vector_memory_service`**，可以开始执行。

---

### [STEP-002] 新建 `user_vector_memory_service`

**目标**：新建用户向量记忆服务，提供 `type=user` / `type=character_private` 的 DashVector CRUD 与列表辅助，复用 `character_knowledge_validate` 工具，行为与 Step6 upsert 一致（C-06）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 | `is_user_manageable_doc_id` 双匹配校验 | 检查 `docs/progress/长记忆第一套下线与Step6运营收敛_progress.md` 中 STEP-001 是否为 ✅ |

> ❌ 前置非 ✅ 请先完成 STEP-001。

---

**需要参考的文件**：
- `@backend/services/character_knowledge_service.py` — **结构范本**：`_build_knowledge_fields` / `_entry_from_doc` / `list_entries` / `create_entry` / `update_entry` / `delete_entry` 写法，本服务照此对齐但 type 与 user_suffix 不同
- `@backend/utils/character_knowledge_validate.py` — `validate_key` / `validate_value` / `build_doc_id` / `build_content` / `parse_doc_id` / `parse_value_from_content` / `is_user_manageable_doc_id`(STEP-001)
- `@backend/utils/dashvector_client.py` — `build_filter` / `upsert` / `delete` / `list_by_filter` / `fetch_by_ids`
- `@backend/services/memory_llm_service.py` — `upsert_step6_vectors` 写入 fields（`content`/`stable_key`/`key_l1`/`key_l2`/`user_id`）以保持一致
- `@backend/constants.py` — `MEMORY_TYPE_USER` / `MEMORY_TYPE_CHARACTER_PRIVATE`

**环境/数据前提**：
- STEP-001 提供的 `is_user_manageable_doc_id` 可用
- DashVector 用户级 doc_id 约定：`{type}_{sha256(key)[:12]}_{user_id}`

---

**需求原文引用**：
> C-06：新建 `user_vector_memory_service`（不扩展 `character_knowledge_service`）。
> §6.2.1 差异表：memory_type=`user`/`character_private`；user_suffix=`str(user_id)`；list filter=`build_filter(mt, user_id, [])`；可管理 doc_id 用 `is_user_manageable_doc_id`。
> P9：单用户三处统一 `USER_LIST_TOPK=500`；`total` = cap 内条数。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| USER_LIST_TOPK | int = 500 | 单用户列表 `list_by_filter` 上限常量（P9） | 需求文档原文 |
| GLOBAL_LIST_TOPK_NO_USER | int = 300 | 全局无 user_id 时上限（R-01/P4），供 STEP-005 复用 | 需求文档原文 |
| UserVectorEntry | dict | `{doc_id, key, value, content, user_id?}` | §8.3 原文 |

> 建议：`USER_LIST_TOPK` / `GLOBAL_LIST_TOPK_NO_USER` 定义在本服务模块顶部，供 STEP-004/005 import 复用，避免常量分散。

---

**开发任务**：
1. 新建 `backend/services/user_vector_memory_service.py`，定义类 `UserVectorMemoryService`，文末导出单例 `user_vector_memory_service`。
2. 内部组装 fields 的辅助函数（复刻 `_build_knowledge_fields`，但用户级须额外写 `user_id`）：`content` / `stable_key` / `key_l1` / `key_l2` / `user_id`，与 `upsert_step6_vectors` 一致。
3. `list_entries(memory_type, user_id, keyword, page, page_size)`：
   - `build_filter(memory_type, user_id, [])` → `list_by_filter(filter, top_k=USER_LIST_TOPK)`
   - 仅保留 `is_user_manageable_doc_id(doc_id, user_id=user_id, expected_type=memory_type)` 通过项
   - 解析为 `UserVectorEntry`，keyword 对 `key`/`value`/`content` 子串内存过滤
   - `total` = 过滤后条数（cap 内），再内存分页
4. `create_entry(memory_type, user_id, key, value)`：`validate_key` + `validate_value` → `build_doc_id(memory_type, key, user_id)` → 重复校验（`fetch_by_ids`/doc_exists）→ embedding(value) → upsert。
5. `update_entry(memory_type, user_id, doc_id, value)`：先 `is_user_manageable_doc_id` 双匹配校验 → 读取已存在 key（`stable_key`）→ 仅改 value → 重新 embedding → upsert（补写 key_l1/key_l2）。
6. `delete_entry(memory_type, user_id, doc_id)`：`is_user_manageable_doc_id` 双匹配校验 → `dashvector_client.delete([doc_id])`。
7. 错误返回风格与 `character_knowledge_service` 一致（`{"error_code", "message"}` 或 `{"data": ...}`），错误码复用现有 `ADMIN_ERR_CHARACTER_KNOWLEDGE_*` 或按需在 `constants.py` 新增（标注 `[自定义]` 并全局统一）。

**不在本环节范围内**：
- 不挂载任何 HTTP 路由（STEP-003/004/005 负责）
- 不实现全局跨用户检索分页逻辑细节（STEP-005 在路由层组装，可调用本服务 list 辅助）
- 不改 `character_knowledge_service`
- 不抽公共 fields 模块（二期可选）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| list 正常 | 某 user_id 下 3 条 user 向量 | 返回 3 条 UserVectorEntry，total=3 |
| list 跨类型隔离 | 同 user_id 混有 character_private | expected_type="user" 时不含 private 条目 |
| create 校验失败 | 非三层 key | 返回校验错误码 |
| update 仅改 value | 合法 doc_id + 新 value | key 不变、content 重组、upsert 成功 |
| delete 跨类型拦截 | private doc_id 传 expected_type="user" | 拒绝、不删除 |

---

**完成标志**：
- [ ] 服务 CRUD 可运行
- [ ] 单元测试通过
- [ ] 回归测试通过（角色知识库服务不受影响）
- [ ] 契约文档已更新（新增 service 说明）
- [ ] 进度文档已更新：**STEP-002** → ✅

---

**完成后执行**：

> 更新 progress 后提示：**下一个环节是 [STEP-003] Admin 用户记忆 / 私有状态 API + 删旧记忆接口**。

---

### [STEP-003] Admin 用户记忆 / 私有状态 API + 删旧记忆接口

**目标**：新增 `user-memories`（user）与 `private-settings`（character_private）两组 CRUD 接口，删除旧 `/users/{id}/memories*` 接口（C-01/C-09）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | `user_vector_memory_service` | progress 中 STEP-002 是否为 ✅ |

---

**需要参考的文件**：
- `@backend/routers/admin/users.py` — 旧 `GET/PUT/DELETE /users/{user_id}/memories*`（接口四/五/六）须删除；新接口可挂在此文件或新建子路由文件
- `@backend/routers/admin/knowledge_mgmt.py` — **路由范本**：`{doc_id:path}` + `unquote` + `log_operation` + `require_role` 写法
- `@backend/services/user_vector_memory_service.py` — STEP-002 提供的 CRUD
- `@docs/contract.md` — Admin 路径命名风格、统一响应信封

**环境/数据前提**：
- STEP-002 service 可用
- `require_role` / `log_operation` / `get_current_admin` 工具可用

---

**需求原文引用**：
> C-01：Admin API `/api/admin/users/{user_id}/user-memories`、`.../private-settings` + `{doc_id:path}`；删除旧 `/users/{id}/memories*`。
> §6.2.2：GET（keyword/page/page_size）、POST（`{key,value}`）、PUT（`{doc_id:path}`，**仅改 value**，C-03）、DELETE。
> P5：用户详情系列权限 = `super_admin + ops_admin + ai_trainer`。
> P9：`user-memories` 列表走 `USER_LIST_TOPK=500`，`total`=cap 内条数。
> §6.2.2：写操作记 `admin_operation_logs`，module 建议区分 `user_memory` / `private_setting`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| POST body | `{key:str, value:str}` | 新增条目 | 需求文档原文 |
| PUT body | `{value:str}` | 仅改 value（C-03） | 需求文档原文 |
| 列表项 | `{doc_id, key, value, content}` | §8.3 | 需求文档原文 |

---

**开发任务**：
1. 删除 `users.py` 中 `list_user_memories`（接口四）、`update_memory`（接口五）、`delete_memory`（接口六）三个路由及其专属 import（`Memory`、`AdminMemoryUpdateRequest`、`embedding_service`、`vector_service`、`MEMORY_TYPE_USER` 如仅此处使用）。删前确认无其他引用。
2. 新增 `user-memories` 四个路由（GET/POST/PUT/DELETE），调用 `user_vector_memory_service`，固定 `memory_type=MEMORY_TYPE_USER`、`expected_type="user"`：
   - `GET /api/admin/users/{user_id}/user-memories`：keyword、page、page_size
   - `POST /api/admin/users/{user_id}/user-memories`：body `{key,value}`
   - `PUT /api/admin/users/{user_id}/user-memories/{doc_id:path}`：body `{value}`，`unquote(doc_id)`
   - `DELETE` 同路径
3. 新增 `private-settings` 四个路由，结构同上，固定 `memory_type=MEMORY_TYPE_CHARACTER_PRIVATE`、`expected_type="character_private"`。
4. 全部 8 个路由权限 `require_role("super_admin", "ops_admin", "ai_trainer")`（P5）。
5. 写操作（POST/PUT/DELETE）调用 `log_operation`，module 用 `user_memory` / `private_setting` 区分。
6. 校验用户存在性（沿用 `users.py` 现有 `ADMIN_ERR_USER_NOT_FOUND` 模式，可选）。

**不在本环节范围内**：
- 不改前端（STEP-013 负责）
- 不改全局接口（STEP-005 负责）
- 不改 relationship 标量写回（M15 明确不并入）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| GET user-memories | 已有 user 向量 | 返回 KV 列表 |
| POST 新增 | `{key:"偏好-饮食-口味", value:"不吃辣"}` | upsert 成功，返回 doc_id |
| PUT 仅改 value | `{value:"能吃微辣"}` | key 不变、value 更新 |
| DELETE | 合法 doc_id | 删除成功 |
| 旧接口已删 | `GET /users/{id}/memories` | 404 |
| 跨 Tab 隔离 | private doc_id 调 user-memories DELETE | 拒绝 |

---

**完成标志**：
- [ ] 8 个新路由可运行、旧 3 路由已删
- [ ] 单元测试通过
- [ ] 回归测试通过（用户详情其他接口不受影响）
- [ ] 契约文档已更新（新增/删除路径）
- [ ] 进度文档已更新：**STEP-003** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-004] H5 `GET /api/memory/list` 只读改造 + 删写路由**。

---

### [STEP-004] H5 `GET /api/memory/list` 只读改造 + 删写路由

**目标**：H5 记忆列表接口改为只读 Step6 user 向量 KV 列表，删除 H5 写路由（C-05）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | `user_vector_memory_service` | progress 中 STEP-002 是否为 ✅ |

---

**需要参考的文件**：
- `@backend/routers/memory.py` — 现有 `GET /list` + `PUT/DELETE/{memory_id}` + `POST /add`
- `@backend/services/user_vector_memory_service.py` — STEP-002 提供的 list 辅助
- `@backend/schemas/memory.py` — `MemoryAddRequest` / `MemoryUpdateRequest` 若仅此处使用可一并清理（删前确认 Admin 侧 `AdminMemoryUpdateRequest` 不受影响）

**环境/数据前提**：
- STEP-002 service 可用；`get_current_user` 鉴权可用

---

**需求原文引用**：
> §6.3.1：`GET /api/memory/list` 保留路径，响应改为 `{total,page,page_size,list:[{doc_id,key,value,content}]}`；不再返回 `importance_score`/`source`/`id`；走 `list_by_filter(build_filter("user", user_id, []), top_k=USER_LIST_TOPK=500)`，`total`=cap 内条数；不过滤 `mem_*`（P1）。
> C-05：H5 删除写路由；`memory.html` 只读。
> §6.1.2：`PUT/DELETE/POST /api/memory/*` 删除路由。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| 响应 list 项 | `{doc_id, key, value, content}` | §8.3，无 id/importance/source | 需求文档原文 |
| updated_at | str? | 可选；DashVector 无该字段则不返回 | 需求文档原文 |

---

**开发任务**：
1. 改写 `GET /api/memory/list`：调用 `user_vector_memory_service.list_entries(MEMORY_TYPE_USER, user_id, keyword=None, page, page_size)`，返回新结构。
2. 删除 `PUT /{memory_id}`、`DELETE /{memory_id}`、`POST /add` 三个路由及对应 import / schema。
3. `memory.py` 不再 import `memory_service`（若改造后无引用）。
4. 保持统一信封 `ApiResponse.ok(data=...)`。

**不在本环节范围内**：
- 不改前端 `memory.html`（STEP-011 负责）
- 不改 `memory_service`（STEP-008 负责物理删/标记）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常列表 | 该用户有 user 向量 | 返回 KV 列表、字段无 importance/source/id |
| 空态 | 该用户无 user 向量 | `list=[]`，total=0 |
| 写路由已删 | `POST /api/memory/add` | 404 |
| cap 口径 | >500 条 | total=cap 内条数（≤500） |

---

**完成标志**：
- [ ] GET 改造可运行、3 写路由已删
- [ ] 单元测试通过
- [ ] 回归测试通过
- [ ] 契约文档已更新
- [ ] 进度文档已更新：**STEP-004** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-005] 全局用户记忆 API 改造**。

---

### [STEP-005] 全局用户记忆 API 改造（global + batch-delete）

**目标**：`GET /memories/global` 改为按可选 user_id / keyword 检索 Step6 user 向量；`DELETE /memories/batch-delete` 改为按 `doc_ids` 仅删 DashVector（M5/M6/R-01/P4/P8）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-002 | `user_vector_memory_service` | progress 中 STEP-002 是否为 ✅ |

---

**需要参考的文件**：
- `@backend/routers/admin/memory_mgmt.py` — 现有 `search_memories_global` / `batch_delete_memories`，含旧 `BatchDeleteRequest(memory_ids)`、`MemoryRulesRequest`
- `@backend/services/user_vector_memory_service.py` — 常量 `USER_LIST_TOPK` / `GLOBAL_LIST_TOPK_NO_USER` 及 list 辅助
- `@backend/utils/dashvector_client.py` — `build_filter` / `list_by_filter` / `delete`
- `@backend/utils/character_knowledge_validate.py` — `parse_doc_id` 用于 batch-delete 校验

**环境/数据前提**：
- STEP-002 service / 常量可用

---

**需求原文引用**：
> §6.4.2：`GET /api/admin/memories/global`：`user_id` 可选——有则 `build_filter("user", user_id, [])` top_k=500（P4），无则 `build_filter("user", None, [])` top_k=300（R-01/P4）；keyword 先 `list_by_filter` 再内存子串过滤；page/page_size 对过滤后分页。移除 `start_date`/`end_date`/`source`。响应增可选 `truncated: true`。
> P8：`batch-delete` 请求 `{doc_ids: list[str]}`（保留 min 1/max 100），响应 `{deleted_count, failed_doc_ids}`，仅删 DashVector，校验「`user_` 前缀 + `parse_doc_id` 合法」，日志 module 仍用 `memory`，「涉及用户」从 `user_suffix` 解析聚合。
> P5：本系列权限 = `super_admin + ai_trainer`。
> §6.4.1：global 不含 `character_private`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| global 响应 list 项 | `{doc_id, user_id, key, value, content}` | §8.3 | 需求文档原文 |
| truncated | bool? | 未传 user_id 且命中上限时为 true | R-01 原文 |
| batch-delete 请求 | `{doc_ids: list[str]}` min 1 max 100 | P8 | 需求文档原文 |
| batch-delete 响应 | `{deleted_count, failed_doc_ids}` | P8 | 需求文档原文 |

---

**开发任务**：
1. 改写 `GET /memories/global`：
   - 参数仅 `keyword`、`user_id`(可选)、`page`、`page_size`；移除 `start_date`/`end_date`/`source`。
   - `user_id` 有值：`build_filter("user", user_id, [])`、top_k=`USER_LIST_TOPK`；无值：`build_filter("user", None, [])`、top_k=`GLOBAL_LIST_TOPK_NO_USER`。
   - `list_by_filter` 取候选 → keyword 内存子串过滤（key/value/content）→ 分页。
   - 列表项含 `user_id`（从 `doc_id` 的 `user_suffix` 解析，或 fields.user_id）。
   - 未传 user_id 且候选数命中上限（==300）时响应附 `truncated: true`。
2. 改写 `DELETE /memories/batch-delete`：
   - 新 `BatchDeleteRequest(doc_ids: list[str] = Field(..., min_length=1, max_length=100))`。
   - 逐条校验：以 `user_` 开头 **且** `parse_doc_id` 合法；非法 → 计入 `failed_doc_ids` 不中断。
   - 合法项 `dashvector_client.delete([doc_id])`，成功累加 `deleted_count`。
   - 「涉及用户」从各 doc_id `user_suffix` 解析去重聚合，写入 `log_operation` 的 `target_description`，module 仍用 `"memory"`。
   - 响应 `{deleted_count, failed_doc_ids}`。
3. 删除本文件内已废弃的 `MemoryRulesRequest` / `ImportanceRule` 等若仅 `memory-rules` 用（STEP-007 会删除 `memory-rules` 路由；若并行开发，本步可暂留，STEP-007 统一清理——以避免冲突，**本步只动 global/batch-delete**）。
4. 权限保持 `require_role("super_admin", "ai_trainer")`（P5，已符合）。
5. 移除对 MySQL `Memory` / `vector_service` 的依赖（global/batch-delete 不再走 MySQL）。

**不在本环节范围内**：
- 不删 `memory-rules` API（STEP-007 负责，避免与本步冲突）
- 不改 `vector-db-config` Tab 相关接口
- 不改前端 `memory-rules.html`（STEP-014 负责）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| global 带 user_id | user_id=123 + keyword | top_k=500 内过滤分页，含 user_id 字段 |
| global 无 user_id | 仅 keyword | top_k=300，命中上限附 truncated=true |
| global 不含 private | 库中混有 character_private | 结果仅 type=user |
| batch-delete 正常 | `{doc_ids:["user_..","user_.."]}` | deleted_count=2 |
| batch-delete 非法前缀 | 含 `mem_5` / `character_private_..` | 计入 failed_doc_ids，不删 |
| batch-delete 日志 | 删 2 条跨 2 用户 | target_description 含聚合用户、module=memory |

---

**完成标志**：
- [ ] global/batch-delete 改造可运行
- [ ] 单元测试通过
- [ ] 回归测试通过（vector-db-config 接口不受影响）
- [ ] 契约文档已更新
- [ ] 进度文档已更新：**STEP-005** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-006] `build_step6_prompt` 异步化 + 热配置 + DEFAULT 复刻**。

---

### [STEP-006] `build_step6_prompt` 异步化 + 热配置 + DEFAULT 复刻

**目标**：将 `build_step6_prompt` 改为 `async`，从 `admin_config.step6_memory_prompt` 读取可配置区块（Redis→DB→DEFAULT 三级回退），DEFAULT 模板逐字复刻现硬编码输出（P2/P6）。

---

**前置条件检查**：

> 无前置条件（与 STEP-001~005 无代码依赖，可并行）。

---

**需要参考的文件**：
- `@backend/services/memory_llm_service.py` — 现 `build_step6_prompt`（硬编码全文，复刻基准）、`_FEW_SHOT_EXAMPLE`、`_ALL_FIELD_NAMES`
- `@backend/services/step6_orchestrator.py` — 唯一调用点 `_step6_pipeline`（已是 async），需加 `await`
- `@backend/services/admin_config_service.py` — `get_active_config(config_key)` 签名与三级回退现状（待查代码仓库确认 Redis→DB 行为）
- `@tests/test_memory_llm_service.py` — 现有 prompt 拼装单测（复刻验收基线参考）

**环境/数据前提**：
- `admin_config_service.get_active_config("step6_memory_prompt")` 可用；无配置时返回 None

---

**需求原文引用**：
> P2：`build_step6_prompt` 改 `async def`，内部 `await get_active_config("step6_memory_prompt")` + 三级回退（Redis→DB→DEFAULT）；唯一调用点 `step6_orchestrator._step6_pipeline`（async）加 `await`。编排顺序不变。
> §6.6.2：可配置区块 6 块：`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields`(11 项) / `merge_rules` / `few_shot_example`；动态注入区块（时间/人格/关系/历史/本轮对话）不可配置覆盖。拼装顺序与现硬编码一致。
> P6：DEFAULT 逐字复刻现 `build_step6_prompt` 全文；验收基线＝DEFAULT 拼出结果与旧硬编码逐字相等；`task_fields` 固定 11 项且顺序与 `_ALL_FIELD_NAMES` 一致。
> §6.6.4：运行时读配置失败 → DEFAULT + `logger.error`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| config_key | str = `"step6_memory_prompt"` | admin_config 键 | C-02 原文 |
| 可配置块 | dict | `system_instruction`/`output_format_rules`/`kv_field_rules`/`task_fields`/`merge_rules`/`few_shot_example` | §6.6.2 原文 |
| task_fields | dict(11 项) | key 为 11 字段名，顺序同 `_ALL_FIELD_NAMES` | P6 原文 |
| STEP6_PROMPT_DEFAULT | dict/常量 | 逐字复刻现硬编码切块 | P6 原文 |

---

**开发任务**：
1. 将现硬编码 prompt **逐字切块**为 6 个可配置区块，定义 `STEP6_PROMPT_DEFAULT`（dict）常量：
   - `system_instruction`：「你是林小梦…」系统指令段
   - `output_format_rules` + `kv_field_rules`：输出格式要求 + 「多条信息分行规则」整段（P6 归此块）
   - `task_fields`：11 个字段说明（保留现有夹带的「禁止同一行串联」等细则）
   - `merge_rules`：合并规则 + 错误/正确示例两行
   - `few_shot_example`：复用 `_FEW_SHOT_EXAMPLE`
2. 新增内部拼装函数 `_assemble_step6_prompt(config, *, 动态参数...)`：按 `system_instruction → output_format_rules + kv_field_rules → 动态块（时间/人格/关系/历史/本轮）→ 【任务】 + task_fields 1~11 → merge_rules → few_shot_example` 顺序拼装。
3. 将 `build_step6_prompt` 改为 `async def`：
   - `try`: `config = await admin_config_service.get_active_config("step6_memory_prompt")`；解析失败/为空 → `config = STEP6_PROMPT_DEFAULT` + `logger.error`（仅异常时）
   - 三级回退由 `get_active_config`（Redis→DB）+ 本函数 DEFAULT 兜底实现
   - 调 `_assemble_step6_prompt` 返回字符串
4. `step6_orchestrator._step6_pipeline` 调用处改 `prompt = await build_step6_prompt(...)`，**编排顺序与入参不变**。
5. **验收基线**：写测试断言「DEFAULT 配置拼出的 prompt 与旧硬编码输出逐字相等」（可在改造前先快照旧输出）。

**不在本环节范围内**：
- 不实现 Admin `step6-memory-prompt` 读写 API（STEP-007 负责）
- 不改 `execute_step6` 编排顺序、`upsert_step6_vectors`、`parse_step6_output`
- 不改前端 `memory-rules.html`（STEP-014 负责）
- 不删 `memory_rules` 历史配置行（C-08 保留）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| DEFAULT 逐字相等 | 无 admin_config | 拼出 prompt 与旧硬编码逐字相等 |
| 热配置覆盖 | admin_config 改 system_instruction | prompt 含新 system_instruction |
| 动态块不可覆盖 | 配置不含时间块 | prompt 仍含【当前时间】等动态块 |
| 读配置异常回退 | get_active_config 抛错 | 用 DEFAULT + logger.error |
| task_fields 顺序 | — | 1~11 顺序与 `_ALL_FIELD_NAMES` 一致 |

---

**完成标志**：
- [ ] 函数异步化 + 热配置可运行
- [ ] DEFAULT 逐字相等测试通过
- [ ] 回归测试通过（Step6 管线行为不变）
- [ ] 契约文档已更新（config_key 约定）
- [ ] 进度文档已更新：**STEP-006** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-007] `step6-memory-prompt` API + 删 `memory-rules` API**。

---

### [STEP-007] `step6-memory-prompt` API + 删 `memory-rules` API

**目标**：新增 `GET/PUT /api/admin/step6-memory-prompt`（保存即发布 + Pydantic 必填校验），删除 `GET/PUT /api/admin/memory-rules`（C-02/C-10）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-006 | `build_step6_prompt` 热配置 | progress 中 STEP-006 是否为 ✅（依赖其 config_key 约定与 6 块 schema） |

---

**需要参考的文件**：
- `@backend/routers/admin/memory_mgmt.py` — 现 `get_memory_rules` / `update_memory_rules`（删除）；`update_vector_db_config` 的 `publish_config` 调用范本
- `@backend/services/admin_config_service.py` — `publish_config` / `get_active_config`
- `@backend/services/memory_llm_service.py` — `STEP6_PROMPT_DEFAULT`、`_ALL_FIELD_NAMES`（校验 task_fields 11 项）

**环境/数据前提**：
- STEP-006 的 config_key `step6_memory_prompt` 约定与 6 块结构确定

---

**需求原文引用**：
> C-02：`config_key`=`step6_memory_prompt`；`GET/PUT /api/admin/step6-memory-prompt`；删除 `GET/PUT /api/admin/memory-rules`。
> C-10：保存即发布 + Pydantic/必填校验（不做 persona 测试集/CONFIRM 门禁）。
> P6：保存校验须覆盖 6 块 + 11 个 task_fields 子项非空。
> §6.6.4：`publish_config` 更新 MySQL + Redis（~100ms），不要求重启；JSON 校验失败拒绝保存。
> P5：本系列权限 = `super_admin + ai_trainer`。
> C-08：`memory_rules` 后台不展示、不提供 API。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| PUT body | 6 块结构 | `system_instruction`/`output_format_rules`/`kv_field_rules`/`task_fields`(11)/`merge_rules`/`few_shot_example` | §6.6.2 原文 |
| GET 响应 | 当前生效配置 | 无配置时返回 DEFAULT | C-02/§6.6.1 |

---

**开发任务**：
1. 定义 `Step6MemoryPromptRequest`（Pydantic）：6 个区块字段，`task_fields` 为 dict 且校验包含全部 11 个 key（顺序/集合与 `_ALL_FIELD_NAMES` 一致）、各子项非空；6 块文本字段非空。
2. `GET /api/admin/step6-memory-prompt`：`get_active_config("step6_memory_prompt")`，无则返回 `STEP6_PROMPT_DEFAULT`。
3. `PUT /api/admin/step6-memory-prompt`：Pydantic 校验通过 → `publish_config(config_key="step6_memory_prompt", ...)`（保存即发布，更新 MySQL+Redis）→ 写 `log_operation`。
4. 删除 `get_memory_rules` / `update_memory_rules` 路由及 `MemoryRulesRequest` / `ImportanceRule`（若 STEP-005 未删，此处统一删）。
5. 权限 `require_role("super_admin", "ai_trainer")`。

**不在本环节范围内**：
- 不改运行时读取逻辑（STEP-006 已完成）
- 不改前端（STEP-014 负责）
- 不做 persona 测试集 / CONFIRM 门禁（C-10）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| GET 无配置 | — | 返回 DEFAULT |
| PUT 合法 | 完整 6 块 + 11 task_fields | 发布成功、Redis 命中 |
| PUT 缺 task_field | task_fields 缺 1 项 | 422/校验失败拒绝保存 |
| PUT 空块 | system_instruction 为空 | 校验失败 |
| memory-rules 已删 | `GET /api/admin/memory-rules` | 404 |

---

**完成标志**：
- [ ] step6-memory-prompt 读写可运行、memory-rules 已删
- [ ] 单元测试通过
- [ ] 回归测试通过（发布后 Redis 命中、新对话 Step6 可观测变化）
- [ ] 契约文档已更新
- [ ] 进度文档已更新：**STEP-007** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-008] 下线第一套写入 + 物理删危险函数**。

---

### [STEP-008] 下线第一套写入 + 物理删危险函数

**目标**：删除 `chat.py` 内 `extract_and_save` 调用；物理删除 `memory_service.extract_and_save` / `_deduplicate_and_save` 及其专属私有方法；其余记忆方法标 `@deprecated` 保留（P10/§6.1.1）。

---

**前置条件检查**：

> 无前置条件（与前段并行；但与 STEP-009 同改 `chat.py`，建议串行或合并解决冲突）。

---

**需要参考的文件**：
- `@backend/services/memory_service.py` — `extract_and_save` / `_deduplicate_and_save` / `_extract_memories_from_llm` / `_parse_memory_list` / `_calculate_importance` / `_calc_expires_at`（物理删）；`search_relevant_memories` / `get_user_memories` / `add_memory_manual` / `update_memory` / `delete_memory`（标 deprecated）
- `@backend/routers/chat.py` — `_post_bundle_success_tasks` 内 `memory_service.extract_and_save(...)` 调用（删）

**环境/数据前提**：
- 删前用 Grep 核对被删私有方法无其它引用（避免 NameError）

---

**需求原文引用**：
> §6.1.1：删除 `chat.py` → `_post_bundle_success_tasks` 内 `memory_service.extract_and_save(...)` 调用。
> P10：物理删除 `extract_and_save` / `_deduplicate_and_save` 及专属私有方法（`_extract_memories_from_llm` / `_parse_memory_list` / `_calculate_importance` / `_calc_expires_at`——删前核对无保留函数引用）；`add_memory_manual` / `update_memory` / `delete_memory` / `search_relevant_memories` / `get_user_memories` 标 `@deprecated` 保留。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| @deprecated | 装饰器/注释 | 标记保留但不再调用的方法 | P10 原文 |

> 注：若项目无统一 deprecated 装饰器，可用 `warnings.warn(..., DeprecationWarning)` 或 docstring + 注释标注 `[自定义]`，全局统一。

---

**开发任务**：
1. 删除 `chat.py` `_post_bundle_success_tasks` 内 `extract_and_save` 调用及其 `conversation_content` 拼装块和外层 `try/except`（仅该记忆块，保留 add_growth / Redis 情绪等其余后置逻辑）。同步评估 `_post_bundle_success_tasks` 入参 `bundled_user_text` / `memory_injected` 是否仍被使用（不再使用则清理传参，避免死参数）。
2. Grep 核对 `_extract_memories_from_llm` / `_parse_memory_list` / `_calculate_importance` / `_calc_expires_at` / `_deduplicate_and_save` 仅被 `extract_and_save` 或彼此引用 → 物理删除 `extract_and_save` + `_deduplicate_and_save` + 4 个专属私有方法 + 仅它们使用的模块常量（`IMPORTANCE_KEYWORDS` / `MERGE_THRESHOLD` / `MEMORY_EXTRACT_PROMPT` / `_JSON_PATTERN`）和 import（`llm_client` 等，删前确认）。
3. 对 `search_relevant_memories` / `get_user_memories` / `add_memory_manual` / `update_memory` / `delete_memory` 标 `@deprecated` 保留（不删函数体，遵循「保留之前函数逻辑」要求）。
4. 确认 `memory_service` 单例仍可正常 import（无悬空引用）。

**不在本环节范围内**：
- 不删 `chat_send` 内 send 时死代码（STEP-009 负责，避免冲突）
- 不删 MySQL `memory` 表（M8 保留表结构）
- 不动召回侧（STEP-010 负责）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 对话闭环不触发记忆提取 | 完成一轮对话 | `_post_bundle_success_tasks` 不调用 extract_and_save |
| import 不报错 | import memory_service | 正常，无 NameError |
| deprecated 保留 | 调用 search_relevant_memories | 仍可调用（标记但不报错） |
| 既有测试调整 | `tests/test_chat.py` extract mock | 去掉对应 mock |

---

**完成标志**：
- [ ] 调用点删除、危险函数物理删、其余标 deprecated
- [ ] 单元测试通过（含去 mock 后回归）
- [ ] 回归测试通过（对话闭环主链正常、Step6 写入不变）
- [ ] 契约文档已更新
- [ ] 进度文档已更新：**STEP-008** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-009] `memory_injected` 恒 null + send 死代码清理**。

---

### [STEP-009] `memory_injected` 恒 null + send 死代码清理

**目标**：`chat_send` 写 user 行时 `memory_injected=None`，删除 send 时无下游消费者的 gather 三件套、`_search_memories` 调用与孤儿函数（M11/P7/§6.5）。

---

**前置条件检查**：

> 无前置条件（与 STEP-008 同改 `chat.py`，建议串行；若并行须解决合并冲突）。

---

**需要参考的文件**：
- `@backend/routers/chat.py` — `chat_send` 内 `asyncio.gather(_get_recent_conversations / _get_latest_emotion / _get_embedding)`、`_search_memories` 调用、`memory_injected` 计算、`user_log` 构造；孤儿函数 `_search_memories` / `_get_embedding`；`embedding_service` import

**环境/数据前提**：
- 经 PRD 核实：`_get_recent_conversations`/`_get_latest_emotion`/`_get_embedding`/`_search_memories` 在 `chat_send` 内本无下游消费者；`_search_memories`/`_get_embedding` 仅 `chat_send` 使用

---

**需求原文引用**：
> P7：删 `chat_send` 内 `asyncio.gather`（三件套）+ `_search_memories` 调用 + `memory_injected` 计算；`user_log.memory_injected=None`；并删孤儿函数 `_search_memories` / `_get_embedding`（经核实仅 `chat_send` 使用）及多余 `embedding_service` import。
> §6.5：保留 `check_content` / `_detect_persona_risk` / 入队落库；`_execute_llm_bundle` 内 Step2 → `build_chat_prompt(memories=...)` 仍正常；`conversation_log.memory_injected` 列保留，新行为恒 null。
> M11：新消息恒 null。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| memory_injected | null | 新 user 行恒为 None | M11 原文 |

---

**开发任务**：
1. 删除 `chat_send` 内 `try: recent_conversations, emotion_context, user_embedding = await asyncio.gather(...)` 整段及其 `except`。
2. 删除随后的 `memories_raw = ...` / `_search_memories(...)` 调用块与 `memory_injected = [...] or None` 计算。
3. `user_log = ConversationLog(...)` 中 `memory_injected=None`（或移除该 kw，使用列默认）。
4. 保留 `check_content(user_content)`、`_detect_persona_risk(...)`、`_fetch_open_window_user_rows` / 入队 / `schedule_debounced` / SSE 等。
5. 删除孤儿函数 `_search_memories`、`_get_embedding`（Grep 确认仅 `chat_send` 用）。
6. 删除 `from backend.services.embedding_service import embedding_service`（若改造后无引用）；同理评估 `dashvector_client` / `MEMORY_TYPE_USER` import 是否变孤儿（`_search_memories` 用过）。
7. 注意：`_get_recent_conversations` / `_get_latest_emotion` 仍被 `_execute_llm_bundle` 使用 → **不删函数定义**，仅删 send 内调用。

**不在本环节范围内**：
- 不改 `_execute_llm_bundle`（Step2 / Step6 路径不变）
- 不删 `conversation_log.memory_injected` 列（保留历史）
- 不动 `_post_bundle_success_tasks`（STEP-008 已处理记忆块）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 新 user 行 memory_injected | 发送一条消息 | DB 中该行 memory_injected 为 null |
| send 不做向量检索 | 发送消息 | 无 embedding / 向量检索调用 |
| 主链正常 | 完整一轮 | SSE 正常、Step2 Prompt 注入正常 |
| 孤儿函数已删 | Grep `_search_memories`/`_get_embedding` | 无定义残留 |

---

**完成标志**：
- [ ] send 死代码清理、memory_injected 恒 null
- [ ] 单元测试通过
- [ ] 回归测试通过（对话主链、Step2、Step6 不受影响）
- [ ] 契约文档已更新（memory_injected 仅历史字段、已停用）
- [ ] 进度文档已更新：**STEP-009** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-010] 召回侧 P1 确认**。

---

### [STEP-010] 召回侧 P1 确认（不加 `mem_*` 过滤）

**目标**：确认 `multi_vector_retrieval_service` user 路与 `agent_service._search_memories_for_agent` **不加** `mem_*` 运行时过滤、不依赖 MySQL `memory` 校验，依赖 M2 人工清理（P1 推翻 M13/M10）。

---

**前置条件检查**：

> 无前置条件。

---

**需要参考的文件**：
- `@backend/services/multi_vector_retrieval_service.py` — user 路 `user_results` 写回逻辑
- `@backend/services/agent_service.py` — `_search_memories_for_agent`（现已仅走 `vector_service.search`，未依赖 MySQL）

**环境/数据前提**：
- 经核对：`agent_service._search_memories_for_agent` 当前已无 MySQL `memory` 校验

---

**需求原文引用**：
> P1：不做任何运行时过滤，完全依赖 M2 人工清理；列表与召回侧均不加 `mem_*` 过滤（推翻 M13/M10）。
> §6.1.3：`multi_vector_retrieval_service` 不加过滤；`agent_service._search_memories_for_agent` 不再依赖 MySQL 校验、不加 `mem_*` 过滤。
> §9 文件索引：`multi_vector_retrieval_service` 本期可零改动；`agent_service` 小改。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| （无新字段，本步为确认/清理性环节） | — | — | — |

---

**开发任务**：
1. 核对 `multi_vector_retrieval_service` user 路当前**未**对 `id.startswith("mem_")` 做过滤 → 确认零改动；若历史代码中已有该过滤，则按 P1 移除。
2. 核对 `agent_service._search_memories_for_agent` 当前**未**依赖 MySQL `memory` 表校验、**未**加 `mem_*` 过滤 → 确认零改动；若有残留依赖则移除。
3. 在代码注释或契约中记录「P1：依赖 M2 人工清理，运行时不过滤 `mem_*`」（避免后人误加过滤）。

**不在本环节范围内**：
- 不删 MySQL `memory` 表 / 数据（M2 运维 STEP-016）
- 不改 Step1.5 / Step2 其余路（§9「明确不改」）
- 不改 `vector_service` 通用检索

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| user 路无过滤 | user 路检索 | 不对 `mem_` 前缀做过滤 |
| agent 召回无 MySQL 依赖 | agent 检索 | 仅走向量，不查 memory 表 |
| 回归 | Step2 四路检索单测 | 通过 |

---

**完成标志**：
- [ ] 确认/移除过滤完成
- [ ] Step2 四路检索单测通过
- [ ] 回归测试通过
- [ ] 契约文档已更新（P1 说明）
- [ ] 进度文档已更新：**STEP-010** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-011] 前端 `memory.html` 只读 KV 列表**。

---

### [STEP-011] 前端 `memory.html` 只读 KV 列表

**目标**：H5 记忆页改为只读 KV 卡片，移除增删改 UI 与 API 调用（M9/§6.3.2）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-004 | H5 `GET /api/memory/list` 只读改造 | progress 中 STEP-004 是否为 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/memory.html` — 现有列表 + 增删改 UI 与 fetch
- `@docs/contract.md` — `GET /api/memory/list` 新响应结构（STEP-004 后）

**环境/数据前提**：
- STEP-004 的新响应 `{total,page,page_size,list:[{doc_id,key,value,content}]}` 已上线

---

**需求原文引用**：
> §6.3.2：移除添加/编辑/删除/保存及对应 API；展示卡片 key 加粗 + value 正文；空态「林小梦还在对话中了解你，暂无整理好的记忆」；顶部说明「以下内容由对话自动整理，暂不支持手动修改」。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| key | str | 卡片标题（加粗） | §6.3.2 原文 |
| value | str | 卡片正文 | §6.3.2 原文 |

---

**开发任务**：
1. 移除「添加 / 编辑 / 删除 / 保存」按钮、弹窗、表单及对应 `fetch('/api/memory/add'|'/{id}')` 调用。
2. 列表渲染改为读取 `data.list[].key` / `.value`（或 `.content` 整行），卡片 key 加粗 + value 正文。
3. 空态文案：「林小梦还在对话中了解你，暂无整理好的记忆」。
4. 顶部说明行：「以下内容由对话自动整理，暂不支持手动修改」。
5. 路径用相对路径（遵循前端路径规范）；中文 UTF-8，检查无乱码。

**不在本环节范围内**：
- 不改后端接口（STEP-004 已完成）
- 不改 settings.html（STEP-012 负责）

---

**单元测试要求**：

> 前端页面，按项目惯例（若有 `tests/test_h5_static_contract.py` 静态断言）补充；用户未要求额外测试脚本时以人工验收为主。

| 场景 | 操作 | 预期 |
|------|------|------|
| 正常展示 | 有记忆 | KV 卡片列表，key 加粗 |
| 空态 | 无记忆 | 显示空态文案 |
| 无写入入口 | 页面检查 | 无增删改按钮 |

---

**完成标志**：
- [ ] 页面只读展示正常
- [ ] 无增删改入口与 API 调用
- [ ] 回归测试通过（H5 其他页不受影响）
- [ ] 契约文档已更新（如有静态断言）
- [ ] 进度文档已更新：**STEP-011** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-012] 前端 `settings.html` 记忆整理只读说明**。

---

### [STEP-012] 前端 `settings.html` 记忆整理只读说明

**目标**：设置页「记忆自动提取」Toggle 改为只读说明行，移除 `memory_auto_extract` 的 PUT（M17/C-07）。

---

**前置条件检查**：

> 无前置条件。

---

**需要参考的文件**：
- `@frontend/pages/settings.html` — 现「记忆自动提取」Toggle 与 `memory_auto_extract` PUT

**环境/数据前提**：
- 无

---

**需求原文引用**：
> C-07：「记忆自动提取」改为只读说明（如「对话结束后会自动整理成记忆，无需手动设置」），移除 Toggle。
> §6.3.3：删除 Toggle 及对 `memory_auto_extract` 的 PUT；改为只读一行，标题「记忆整理」；「主动消息推送」Toggle 不在本期。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| 标题 | str | 「记忆整理」 | §6.3.3 原文 |
| 说明 | str | 「对话结束后会自动整理成记忆，无需手动设置」 | C-07 原文 |

---

**开发任务**：
1. 删除「记忆自动提取」Toggle 控件及其事件绑定、`memory_auto_extract` 的 `PUT` 调用与读取逻辑。
2. 替换为只读一行：标题「记忆整理」+ 说明文案。
3. 「主动消息推送」Toggle 保持不动（不在本期）。
4. 中文 UTF-8 检查无乱码。

**不在本环节范围内**：
- 不实现 `memory_auto_extract` 后端逻辑（M17 本期不实现）
- 不动「主动消息推送」（TD-024 其他项）

---

**单元测试要求**：

| 场景 | 操作 | 预期 |
|------|------|------|
| 只读说明 | 进入设置页 | 「记忆整理」只读行可见，无 Toggle |
| 无 PUT | 页面检查 | 无 memory_auto_extract 请求 |

---

**完成标志**：
- [ ] Toggle 移除、只读说明展示
- [ ] 回归测试通过
- [ ] 契约文档已更新（如有静态断言）
- [ ] 进度文档已更新：**STEP-012** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-013] 前端 `user-detail.html` 用户记忆 + 私有状态 Tab**。

---

### [STEP-013] 前端 `user-detail.html` 用户记忆 + 私有状态 Tab

**目标**：用户详情页「用户记忆」改用 `user-memories` 接口（doc_id 主键），并在其右侧新增「私有状态」Tab（`private-settings`）（M3/M4/§6.2.3）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | Admin 用户记忆 / 私有状态 API | progress 中 STEP-003 是否为 ✅ |

---

**需要参考的文件**：
- `@admin/pages/user-detail.html` — 现「用户记忆」Tab（旧 `/users/{id}/memories*`，memory_id 主键）
- `@admin/pages/memory-rules.html` 或角色知识库页 — KV 表格 + 三层 key 录入交互范本（可选参考）
- `@docs/contract.md` — STEP-003 后的 `user-memories` / `private-settings` 路径与字段

**环境/数据前提**：
- STEP-003 的 8 个接口已上线

---

**需求原文引用**：
> §6.2.3：在「用户记忆」右侧插入「私有状态」；用户记忆表格列 key/value/操作（编辑 value、删除）+ 新增（三层 key+value）；私有状态同上 + 页内说明「角色对该用户的私有设定，非用户自传事实」；主键 `doc_id`，不再用 `memory_id`。
> §7.6：避免运营误把用户事实写入私有状态 Tab（页内加说明）。
> §7.2：改 key = DELETE + POST，不提供 PUT 改 key。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| doc_id | str | 主键（替代 memory_id） | §6.2.3 原文 |
| key/value | str | 三层 key + value | §6.2.3 原文 |

---

**开发任务**：
1. 「用户记忆」Tab 改造：列表调 `GET .../user-memories`，列 key / value / 操作；编辑仅改 value（PUT `{value}`，doc_id 需 URL encode）；删除调 DELETE；新增弹窗（三层 key + value）调 POST。主键改 doc_id。
2. 在「用户记忆」右侧新增「私有状态」Tab：交互同上，调 `private-settings` 系列；页内加说明「角色对该用户的私有设定，非用户自传事实」。
3. 改 key 走 DELETE + POST（不提供 PUT 改 key）。
4. 相对路径、中文 UTF-8 无乱码；遵循后台前端规范（最小宽度 1280px）。

**不在本环节范围内**：
- 不改后端接口（STEP-003 已完成）
- 不改 relationship 标量展示（M15）
- 不改 memory-rules.html（STEP-014 负责）

---

**单元测试要求**：

| 场景 | 操作 | 预期 |
|------|------|------|
| 用户记忆列表 | 打开 Tab | 展示 key/value，主键 doc_id |
| 新增 | 三层 key+value | POST 成功、列表刷新 |
| 编辑 value | 改 value | PUT 成功 |
| 私有状态 Tab | 切到右侧 Tab | character_private 列表 + 说明文案 |
| 跨 Tab 不混 | — | 用户记忆不显示私有状态条目 |

---

**完成标志**：
- [ ] 两 Tab 可正常 CRUD
- [ ] 回归测试通过（用户详情其他 Tab 不受影响）
- [ ] 契约文档已更新（如有静态断言）
- [ ] 进度文档已更新：**STEP-013** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-014] 前端 `memory-rules.html` 三 Tab 改造**。

---

### [STEP-014] 前端 `memory-rules.html` 三 Tab 改造

**目标**：记忆规则页改为「Step6 记忆 Prompt（默认）/ 向量数据库（保留）/ 全局用户记忆」三 Tab，删除第一套 UI（M7/C-04/R-01/§6.6.3/§6.4.3）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-005 | 全局用户记忆 API 改造 | progress 中 STEP-005 是否为 ✅ |
| STEP-007 | `step6-memory-prompt` API | progress 中 STEP-007 是否为 ✅ |

---

**需要参考的文件**：
- `@admin/pages/memory-rules.html` — 现「记忆规则 / 向量数据库」Tab + 第一套字段 UI
- `@docs/contract.md` — `step6-memory-prompt`、`memories/global`、`batch-delete` 新契约

**环境/数据前提**：
- STEP-005 / STEP-007 接口已上线

---

**需求原文引用**：
> §6.6.3：Tab「Step6 记忆 Prompt（默认）」分区表单 → `PUT /api/admin/step6-memory-prompt`（保存即发布）；「向量数据库」保留；「全局用户记忆」见 §6.4.3。删除记忆提取 Prompt/重要性/存储阈值/检索合并阈值 UI、`memory-rules` 调用、不展示历史 `memory_rules`（C-08）。
> §6.4.3：「全局用户记忆」Tab：user_id（选填）+ keyword + 分页列表；固定提示（R-01）；列 user_id/key/value/操作；勾选 + 批量删除 → `batch-delete`；默认 Tab 仍为 Step6 Prompt。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| 固定提示 | str | 「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」 | R-01 原文 |
| Step6 Prompt 表单 | 6 块 | 与 STEP-007 PUT body 对齐 | §6.6.2 原文 |

---

**开发任务**：
1. 删除第一套 UI：记忆提取 Prompt、重要性评分、存储阈值、检索/合并相似度阈值表单及 `memory-rules` 的 GET/PUT 调用。
2. 新增/改造「Step6 记忆 Prompt」Tab（默认）：6 块分区表单（system_instruction / output_format_rules / kv_field_rules / task_fields 11 项 / merge_rules / few_shot_example）；加载 `GET /step6-memory-prompt`，保存 `PUT /step6-memory-prompt`（保存即发布，提示成功）。
3. 保留「向量数据库」Tab（`vector-db-config`）不变。
4. 新增「全局用户记忆」Tab：user_id（选填）+ keyword + 分页；列 user_id/key/value/操作；勾选批量删除 → `DELETE /memories/global... batch-delete`（body `{doc_ids}`）；未填 user_id 时展示固定提示，API 返回 `truncated:true` 时强化展示。
5. 默认 Tab 为「Step6 记忆 Prompt」。
6. 相对路径、中文 UTF-8 无乱码。

**不在本环节范围内**：
- 不改后端接口（STEP-005/007 已完成）
- 不展示历史 `memory_rules`（C-08）

---

**单元测试要求**：

| 场景 | 操作 | 预期 |
|------|------|------|
| Step6 Prompt 保存 | 改 system_instruction 保存 | PUT 成功、提示发布 |
| 全局检索带 user_id | 填 user_id+keyword | 列表展示、含 user_id 列 |
| 全局检索无 user_id | 仅 keyword | 展示固定 300 条提示 |
| 批量删除 | 勾选若干 user_ doc_id | batch-delete 成功 |
| 第一套 UI 已删 | 页面检查 | 无提取 Prompt/阈值表单 |

---

**完成标志**：
- [ ] 三 Tab 正常、第一套 UI 已删
- [ ] 回归测试通过（向量数据库 Tab 不受影响）
- [ ] 契约文档已更新（如有静态断言）
- [ ] 进度文档已更新：**STEP-014** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-015] 契约 + 技术债同步**。

---

### [STEP-015] 契约 + 技术债同步

**目标**：同步更新 `docs/contract.md`（记忆模块/Admin 路径/下线说明）与 `docs/tech-debt.md`（TD-022/023/024 状态）（M16/§10）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001~014 | 全部功能落地 | progress 中 STEP-001~014 是否均为 ✅ |

---

**需要参考的文件**：
- `@docs/contract.md` — 记忆模块接口、Admin 路径、`memory_injected` 字段
- `@docs/tech-debt.md` — TD-022 / TD-023 / TD-024 条目
- `@.cursor/rules/docup.mdc` — 契约更新规范（顶部「最后更新」改今天、追加问题清单）

**环境/数据前提**：
- 各 STEP 已在自身完成时同步部分契约；本步做总收口

---

**需求原文引用**：
> §10：TD-022 标「已清偿」（附 PR 号）；TD-023 缓解；TD-024 部分（设置页只读说明，全量 settings 仍待）；contract.md 同 PR 更新，废弃第一套记忆接口与 `memory_rules` API。
> §6.5：Admin 对话列表 `memory_injected` 契约注明「仅历史字段，已停用」。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| （文档更新，无代码字段） | — | — | — |

---

**开发任务**：
1. `contract.md`：
   - 新增/改写记忆模块：`GET /api/memory/list`（只读 KV）、删除 H5 写接口、`user-memories`/`private-settings`、`memories/global`/`batch-delete`、`step6-memory-prompt`；删除 `memory-rules`、旧 `/users/{id}/memories*`。
   - 标注 `memory_injected` 为「仅历史字段，已停用，新行恒 null」。
   - 标注 P1（运行时不过滤 `mem_*`，靠 M2 清理）、R-01（全局 300 条上限）、P9（单用户 500 cap、total 口径）、P5（权限分域）。
   - 顶部「最后更新」改为今天，追加本次摘要。
2. `tech-debt.md`：TD-022 标「已清偿」（附实现 PR 号占位）；TD-023 标缓解；TD-024 标部分完成（C-07）。
3. 如发现新契约问题，追加「契约对齐问题清单」并标「待修复」。

**不在本环节范围内**：
- 不改代码
- 不处理 TD-028/029/026（不纳入本期）

---

**单元测试要求**：

> 文档更新，无单测；如有契约一致性静态校验（`tests/test_*_contract.py`）则跑通。

---

**完成标志**：
- [ ] 契约 / 技术债更新完整
- [ ] 契约静态断言（如有）通过
- [ ] 进度文档已更新：**STEP-015** → ✅

---

**完成后执行**：

> 提示：**下一个环节是 [STEP-016] 上线前/后运维清理与验收 checklist**。

---

### [STEP-016] 上线前/后运维清理与验收 checklist

**目标**：执行发布前数据清理（人工，非代码）与发布后功能验收（M2/M18/§11）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001~015 | 全部开发与文档落地 | progress 中 STEP-001~015 是否均为 ✅ |

---

**需要参考的文件**：
- `@doc/mem_doc/PRD-长记忆第一套下线与Step6运营收敛.md` — §11 上线与运维检查项

**环境/数据前提**：
- 发布窗口已确定；DashVector / MySQL 运维权限就绪

---

**需求原文引用**：
> §11.1 发布前：清空/归档 MySQL `memory` 表业务数据（表结构保留）；删除 DashVector `doc_id` 以 `mem_` 开头文档；抽样验证任一测试用户 `list user` 无 `mem_*`；清理前导出备份。
> §11.2 发布后验收：8 项（Step6→Admin 可见、H5 只读、Prompt 模块5 召回、Admin 手改同步、全局检索 R-01、Step6 Prompt 保存免重启、新 user 行 memory_injected=null、Agent 不依赖 mem_*）。
> §11.3 回归：Step1.5/Step2 单测+冒烟、Step6 upsert 单测、角色知识库不受影响、Admin 发布 Step6 Prompt 后 Redis 命中。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| （运维操作，无代码字段） | — | — | — |

---

**开发任务**（运维执行，非代码改动）：
1. 发布前：备份导出 MySQL `memory` + 向量 `mem_*` doc_id 列表 → 清空 `memory` 表业务数据（保留表结构）→ 删除 DashVector 全部 `mem_*` 文档 → 抽样 `list user` 确认无 `mem_` 前缀。
2. 发布后逐项验收 §11.2 八条。
3. 跑 §11.3 回归：Step1.5/Step2 单测 + 冒烟、Step6 upsert 单测、角色知识库 CRUD、Admin 发布 Step6 Prompt 后 Redis 命中。
4. 记录验收结果到测试报告（沿用 `doc/mem_doc/test_report_*` 命名风格）。

**不在本环节范围内**：
- 不做代码迁移脚本（M2 明确不做）
- 不删 `memory` 表结构（M8）

---

**单元测试要求**：

> 以 §11.2 / §11.3 验收清单为准，无新增单测。

| 场景 | 操作 | 预期 |
|------|------|------|
| 清理验证 | 抽样 list user | 无 mem_ 前缀文档 |
| Step6 写入可见 | 一轮对话 | Admin 用户记忆/私有状态见新 KV |
| Prompt 热更 | 保存 Step6 Prompt | 免重启、新对话可观测 |
| memory_injected | 新消息 | null |

---

**完成标志**：
- [ ] 发布前清理 + 备份完成
- [ ] 发布后 8 项验收通过
- [ ] §11.3 回归通过
- [ ] 验收报告归档
- [ ] 进度文档已更新：**STEP-016** → ✅（全部完成）

---

**完成后执行**：

> 全部 STEP 完成。更新 progress 总览完成率为 100%，归档验收报告。

---

## 4. 自检清单

- [x] 需求文档中每一条功能都有对应的 STEP（F1~F16 → STEP-001~016 一一映射）
- [x] 没有增加需求文档中不存在的功能
- [x] 所有自定义字段已标注 `[自定义]`（deprecated 标注方式、常量放置位置、错误码新增）
- [x] 不确定的代码路径已标注「待查代码仓库」（`admin_config_service.get_active_config` 三级回退行为）
- [x] 关联外部模块字段引用契约文档（`build_filter` / `upsert_step6_vectors` / 角色知识库约定，均引用现有实现而非重新验证）
- [x] 环节之间依赖关系逻辑正确（STEP-002 依赖 001；003/004/005 依赖 002；007 依赖 006；011 依赖 004；013 依赖 003；014 依赖 005+007；015/016 收尾）
- [x] 每个 STEP 包含完成回调指令（progress 更新 + 下一环节提示）
- [x] 进度文档 `长记忆第一套下线与Step6运营收敛_progress.md` 已生成（见 STEP-016 后续）

---

## 5. 关键约束备注（贯穿全程）

- **P1（最易踩坑）**：列表与召回侧**一律不过滤 `mem_*`**，清理前可能短暂展示脏数据，属已知风险，靠 M2 人工清理（STEP-016），**不要**自作主张加运行时过滤。
- **P6 验收硬基线**：STEP-006 的 DEFAULT 拼出 prompt 必须与旧硬编码**逐字相等**，改造前先快照旧输出。
- **P9 cap 口径**：单用户三处统一 `USER_LIST_TOPK=500`，`total`=cap 内条数（非库内真实总数）。
- **P5 权限分域**（契约注明非 bug）：记忆规则页系列 = `super_admin + ai_trainer`；用户详情系列 = `super_admin + ops_admin + ai_trainer`。
- **C-03**：Admin PUT 仅改 value；改 key = DELETE + POST。
- **M8/M2**：`memory` 表结构保留、不做迁移脚本，仅运维手工清理数据。
- **保留既有正确功能**：物理删仅限 P10 点名的危险函数（extract/dedup 链），其余记忆方法 `@deprecated` 保留函数体。
