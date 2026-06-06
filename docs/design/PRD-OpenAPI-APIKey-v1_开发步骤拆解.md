# PRD-OpenAPI-APIKey-v1 开发步骤拆解

> PRD：`docs/design/PRD-OpenAPI-APIKey-v1.md`（v1.9）  
> 进度追踪：`docs/progress/PRD-OpenAPI-APIKey-v1_progress.md`  
> 拆解日期：2026-06-04  
> 修订日期：2026-06-04（审查修订：tech-debt 同步、401 验收、H5 SSE 边界、STEP-000 测试范围）

---

## 1. 功能清单

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F1 | 开发前 STEP-0：grep `routers.chat` 依赖、确认单向依赖方向 | [核心] | 无 |
| F2 | `OPEN_API_PEPPER` 必填（≥32）、缺失则整应用拒绝启动 | [核心] | 无 |
| F3 | 新增表 `user_api_keys`（每用户 1 行，hash+prefix，无明文） | [核心] | F2 |
| F4 | Open API Key 鉴权：`Authorization: Bearer sk-lxm-...`、401 `detail`、路径仅 `/api/open/v1/*` | [核心] | F3 |
| F5 | `last_used_at` 鉴权成功且 ≥60s 节流写库（V8） | [核心] | F4 |
| F6 | 错误码 `10108` + `ERROR_MESSAGES` 文案（V7） | [核心] | 无 |
| F7 | `chat_service`：`check_content_safety` / `check_send_quota`（V9，与 H5 共用） | [核心] | F1 |
| F8 | `chat_service` 写路径：Future 运行时、generation 作废链、`enqueue_send`/`enqueue_resend`、`await_bundle_payload`、`_resolve_generation_future`（V1/O2/O3） | [核心] | F7 |
| F9 | `timeline_read_service.get_timeline`；H5/Open 读路径共用（O1） | [核心] | F1 |
| F10 | H5 `routers/chat.py` 改调 service 层，**SSE 行为不变** | [核心] | F8, F9 |
| F11 | Open 同步 JSON：`POST send` / `POST resend`（resend **无 Body**）/ `GET timeline` | [核心] | F4, F6, F8, F9 |
| F12 | Open agent：`messages` / `unread-count` / `messages/{id}/read` | [核心] | F4 |
| F13 | Admin API：`GET/POST /api/admin/users/{user_id}/open-api-key` + 操作日志（N4） | [核心] | F3 |
| F14 | Admin 用户详情页 Key 区块（生成/重新生成/脱敏展示） | [核心] | F13 |
| F15 | 第三方集成文档 `docs/design/open-api-v1.md`（含传输安全 S16） | [核心] | F11, F12 |
| F16 | 更新 `docs/contract.md` Open API 模块 | [核心] | F11~F14 |
| F17 | Nginx 禁止记录 Authorization 注释 + 部署抽检说明（N8） | [扩展] | 无 |
| F18 | `.env.example` / `DEPLOY.md` pepper 与多环境说明（V2/C15） | [扩展] | F2 |
| F19 | 核对/同步 `docs/tech-debt.md` **[TD-030]**、**[TD-031]**（§8：路径随搬迁更新、与 open-api-v1 交叉引用） | [核心] | F7, F11, F15 |

**本期明确不做（PRD 已排除，不拆 STEP）：** 单独 disable Key（C10）、Admin 展示 Base URL（N7）、Open `client_message_id` / `client_resend_id` 幂等、Open SSE。

---

## 2. 开发环节总览

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-000 | 开发前依赖梳理（STEP-0） | `backend/routers/chat.py`、tests、admin/prompt_mgmt | 无 | 低 |
| STEP-001 | OPEN_API_PEPPER 配置与启动校验 | `config.py`、`.env.example`、`main.py` lifespan | 无 | 低 |
| STEP-002 | user_api_keys 表与 ORM | `models/`、`database` | STEP-001 | 低 |
| STEP-003 | Open API Key 鉴权依赖 | `utils/open_api_auth.py` | STEP-002 | 中 |
| STEP-004 | 错误码 10108 | `constants.py` | 无 | 低 |
| STEP-005 | chat_service 入队前共享校验（V9） | `services/chat_service.py`、`routers/chat.py`（抽离源） | STEP-000 | 中 |
| STEP-006 | chat_service 写路径搬迁（V1/O2/O3） | `services/chat_service.py`、`routers/chat.py` | STEP-005 | 高 |
| STEP-007 | timeline_read_service（O1） | `services/timeline_read_service.py`、`routers/chat.py` | STEP-000 | 中 |
| STEP-008 | H5 chat 接入 service 层回归 | `routers/chat.py` | STEP-006, STEP-007 | 高 |
| STEP-009 | open_chat_service Facade | `services/open_chat_service.py`、`schemas/open_*.py` | STEP-003,004,006,007 | 中 |
| STEP-010 | Open chat 路由 + main 挂载 | `routers/open/chat.py`、`main.py` | STEP-009 | 中 |
| STEP-011 | open_agent Facade + 路由 | `services/open_agent_service.py`、`routers/open/agent.py` | STEP-003 | 低 |
| STEP-012 | Admin Open API Key API | `routers/admin/users.py` | STEP-002 | 中 |
| STEP-013 | Admin 用户详情 Key UI | `admin/pages/user-detail.html`、`admin/static/js/admin-api.js` | STEP-012 | 中 |
| STEP-014 | 第三方文档 open-api-v1.md | `docs/design/open-api-v1.md` | STEP-010, STEP-011 | 中 |
| STEP-015 | contract + tech-debt + Nginx + 部署说明 | `docs/contract.md`、`docs/tech-debt.md`、`nginx/nginx.conf`、`DEPLOY.md` | STEP-010~014 | 低 |

---

## 3. 开发提示词

### [STEP-000] 开发前依赖梳理（STEP-0）

**目标**：在 N5 最小搬迁前确认 `chat.py` 被谁 import、依赖方向无环，并记录 H5 回归清单。

---

**前置条件检查**：无前置条件。

---

**需要参考的文件**：
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §7.0、§9.1
- `@backend/routers/chat.py` — 待搬迁符号清单
- `@backend/routers/admin/prompt_mgmt.py` — 已知 `_build_round_context` 依赖

**环境/数据前提**：无

---

**需求原文引用**：
> N5 **最小搬迁** 启动前执行：  
> 1. `rg "from backend.routers.chat import" backend tests`  
> 2. **依赖方向：** `chat_service` **禁止** import `routers.chat`  
> 3. `_build_round_context`、Prompt 相关符号 **本期不迁**  
> 4. **`chat_service` 须暴露 `_resolve_generation_future`**  
> 5. **`check_content_safety` / `check_send_quota` 由 `chat_service` 提供**；Open router **未**直接 `import routers.chat`  
> 6. H5 回归范围：`send` / `resend` SSE（含 `obsolete`、**failed_blocked→10101**）、10104/10105、双端混用、timeline 字段不变。

---

**开发任务**：
1. 执行 `rg "from backend.routers.chat import" backend tests`，输出依赖清单到进度文档备注或团队 Wiki。
2. 确认搬迁符号列表：Future 三件套、`_new_generation_for_user`、`_invalidate_generation_future`、`enqueue_send`、`enqueue_resend`、`await_bundle_payload`、`_resolve_generation_future`、入队前校验（待 STEP-005 命名）。
3. 明确 **不迁**：`_execute_llm_bundle`、`_build_round_context`；**H5 保留** `_sse_chat_wait_bundle` 于 `chat.py`，其实现应在 STEP-008 **调用** `chat_service.await_bundle_payload`（非删除 SSE 层）。
4. **测试影响**：确认 `tests/test_step018_round_context.py` — 主要依赖 `_build_round_context`（不迁，应不受搬迁影响）；另含对 `chat_send` 源码的静态检查（STEP-008 改 `chat_send` 后须回归该文件）。
5. 编写 H5 手工/自动化回归检查表（§9.1 共 12 条）。

**不在本环节范围内**：实际代码搬迁。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 依赖扫描 | rg 命令 | 清单含 prompt_mgmt、tests，无 `chat_service → routers.chat` |
| test_step018 | 阅读 `test_step018_round_context.py` import 列表 | 已标注：仅 `_build_round_context` 不受迁；`chat_send` 静态测需 STEP-008 后回归 |

---

**完成标志**：
- [ ] 依赖清单已记录
- [ ] 搬迁/不迁边界已书面确认（含 `_sse_chat_wait_bundle` 保留于 H5）
- [ ] `test_step018_round_context.py` 影响范围已记录
- [ ] `docs/progress/PRD-OpenAPI-APIKey-v1_progress.md` 中 **STEP-000** 为 ✅

---

**完成后执行**：下一环节 **STEP-001**（可与 STEP-004 并行）或 **STEP-005**（需 STEP-000 ✅）。

---

### [STEP-001] OPEN_API_PEPPER 配置与启动校验

**目标**：配置项 `OPEN_API_PEPPER` 缺失/空/长度&lt;32 时应用无法启动。

---

**前置条件检查**：无。

---

**需要参考的文件**：
- `@backend/config.py` — JWT 类配置写法
- `@backend/main.py` — lifespan
- `@.env.example`
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §6.4 N1/V2

---

**需求原文引用**：
> **严格 N1**：缺失/空/长度 &lt;32 → 整应用拒绝启动；**测试/生产各独立 pepper**；**与 JWT 无关**。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| OPEN_API_PEPPER | string | Key 哈希 pepper，≥32 字符 | 需求文档原文 |

---

**开发任务**：
1. `config.py` 增加 `get_open_api_pepper()`，校验长度 ≥32。
2. `lifespan` 或模块加载时调用，失败 `raise RuntimeError`。
3. `.env.example` 增加注释示例（`openssl rand -hex 32`）；`OPEN_API_PUBLIC_BASE_URL` 仅注释预留（N7 不读取）。

**不在本环节范围内**：Key 生成与鉴权逻辑。

---

**完成标志**：
- [ ] 无 pepper 时 `uvicorn` 启动失败
- [ ] STEP-001 ✅

---

**完成后执行**：下一环节 **STEP-002**。

---

### [STEP-002] user_api_keys 表与 ORM 模型

**目标**：落库 API Key 元数据（hash、prefix、时间戳），每用户唯一一行。

---

**前置条件检查**：STEP-001 ✅。

---

**需要参考的文件**：
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §6.1
- `@backend/models/` — 现有 User 模型风格
- `@backend/database.py` — create_all_tables

---

**需求原文引用**：
> 新增表 `user_api_keys`：`user_id` 唯一、`key_hash` VARCHAR(64)、`key_prefix` VARCHAR(24)、`created_at`（首次签发不刷新）、`last_used_at`、`created_by_admin_id`；**不存明文**。

---

**开发任务**：
1. 新增 `backend/models/user_api_key.py`（表名可微调）。
2. 注册到 metadata / `create_all_tables`。
3. `user_id` UNIQUE；FK → `users.id`。

**不在本环节范围内**：Admin 生成 Key 业务逻辑。

---

**完成标志**：
- [ ] 建表成功，模型可被 Admin/Open 引用
- [ ] STEP-002 ✅

---

### [STEP-003] Open API Key 鉴权依赖

**目标**：实现 `get_current_user_by_api_key`，仅用于 Open 路由。

---

**前置条件检查**：STEP-002 ✅。

---

**需要参考的文件**：
- `@backend/utils/auth_middleware.py` — H5 JWT 模式对照
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §2.4、§10.2 S1~S9
- 待查代码仓库：`user_banned:{user_id}` Redis key 用法（与 JWT 禁用一致）

---

**需求原文引用**：
> 前缀 `sk-lxm-` + `SHA-256(api_key + OPEN_API_PEPPER)` 恒定时间比较；`last_used_at` NULL 或 ≥60s 才 UPDATE。  
> §2.4 鉴权失败 **分场景**（HTTP 401 + `{"detail":"..."}`，非 ApiResponse 信封）：
> - 未提供 `Authorization` → `detail`：「未提供 API Key」；响应头含 **`WWW-Authenticate: Bearer`**
> - Key 无效/已吊销/格式错（含非 `sk-lxm-`、误传 JWT）→ `detail`：「API Key 无效或已吊销」（S8 不区分原因）
> - 用户被 Admin 禁用 → `detail`：「账号已被禁用」

---

**开发任务**：
1. 新建 `backend/utils/open_api_auth.py`：`HTTPBearer` + 前缀校验 + hash 比对。
2. 鉴权成功后解析 `user_id`；检查 `user_banned`。
3. `last_used_at` DB 侧节流（V8）。
4. 日志/异常栈禁止完整 Key（S6）。
5. 缺 `Authorization` 时返回 `WWW-Authenticate: Bearer`（§2.4）。

**不在本环节范围内**：Open 路由挂载、Admin 签发。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 无 Authorization 头 | `GET /api/open/v1/...` 无头 | 401 + `未提供 API Key` + `WWW-Authenticate: Bearer` |
| 无效 Key | `Bearer eyJ...` 或 `Bearer sk-lxm-xxx`（库无） | 401 + `API Key 无效或已吊销` |
| 用户禁用 | 有效 Key 但 `user_banned` | 401 + `账号已被禁用` |

---

**完成标志**：
- [ ] 上述 **三种** 401 场景分别验收通过（勿合并为一条「无效 Key」）
- [ ] 缺 Authorization 时响应头含 `WWW-Authenticate: Bearer`
- [ ] STEP-003 ✅

---

### [STEP-004] 错误码 10108（generation obsolete）

**目标**：Open 等待 Future 被新 send/resend 作废时返回业务码 10108。

---

**前置条件检查**：无。

---

**需要参考的文件**：
- `@backend/constants.py`
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §4.3、V7

---

**需求原文引用**：
> **`ERR_CHAT_GENERATION_OBSOLETE = 10108`**；**`ERROR_MESSAGES[10108]`** =「回复已被新消息取代，请拉取时间线查看后再操作」；HTTP 200 + ApiResponse。

---

**开发任务**：
1. 常量与 `ERROR_MESSAGES` 追加 10108。
2. 确认 H5 SSE 仍用 `obsolete` 事件，**不**改 H5 业务码。

---

**完成标志**：
- [ ] 10108 文案与 PRD 一致
- [ ] STEP-004 ✅

---

### [STEP-005] chat_service 入队前共享校验（V9）

**目标**：从 `chat.py` 抽出内容安全与 10104 队列检查，供 H5 与 Open 共用。

---

**前置条件检查**：STEP-000 ✅。

---

**需要参考的文件**：
- `@backend/routers/chat.py` — `check_content`、persona_risk、`_fetch_open_window_user_rows`、`_should_block_new_send`
- `@backend/services/chat_service.py` — 当前几乎为空，可在此实现
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — V9

---

**需求原文引用**：
> **`check_content_safety(content)`**（空/unsafe + persona_risk 标志）、**`check_send_quota(user_id, db)`**（10104）；H5 与 Open **均调用**；**禁止** Open `import routers.chat`。

---

**开发任务**：
1. 在 `chat_service.py` 实现上述两函数，逻辑与现 `chat.py` 内联一致。
2. 返回结构便于 router 映射 10100/10101/10104。
3. **不** import `routers.chat`。

---

**完成标志**：
- [ ] 函数可被 chat.py 与后续 Open router 调用
- [ ] （可选，STEP-015 收口）`docs/tech-debt.md` **[TD-031]** 中「位置」已指向 `chat_service.check_send_quota`（若 STEP-005 已迁）
- [ ] STEP-005 ✅

---

### [STEP-006] chat_service 写路径搬迁（V1/O2/O3）

**目标**：Future 运行时与 send/resend 入队、同步等待迁到 `chat_service`，obsolete 仅由入队链触发。

---

**前置条件检查**：STEP-005 ✅。

---

**需要参考的文件**：
- `@backend/routers/chat.py` — `_generation_futures`、`_new_generation_for_user`、`_invalidate_generation_future`、`chat_send`/`chat_resend` 入队段、`_sse_chat_wait_bundle`
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §4.5、§5.3.1、O2/O3/V1

---

**需求原文引用**：
> `await_bundle_payload` **仅** `asyncio.Future` + `asyncio.wait_for`（≤120s）；obsolete **仅** `enqueue_*` → `_new_generation_for_user` → `_invalidate_generation_future`；暴露 **`_resolve_generation_future`** 供 `_execute_llm_bundle`。

---

**开发任务**：
1. 搬迁 Future 字典与锁、generation Redis 交互（或保留 queue_service 调用）。
2. 实现 `enqueue_send`、`enqueue_resend`、`await_bundle_payload`、`_resolve_generation_future`。
3. `_execute_llm_bundle` **仍留** `chat.py`，通过 import `_resolve_generation_future` 唤醒。
4. `chat_service` **禁止** import `routers.chat`。

---

**不在本环节范围内**：H5 路由改调（STEP-008）、Open Facade。

---

**完成标志**：
- [ ] grep 无 `chat_service → routers.chat`
- [ ] obsolete 触发点唯一（§9.1 #2）
- [ ] STEP-006 ✅

---

### [STEP-007] timeline_read_service（O1）

**目标**：抽出 `get_timeline`，H5/Open 读路径共用，**不经过** `chat_service`。

---

**前置条件检查**：STEP-000 ✅。

---

**需要参考的文件**：
- `@backend/routers/chat.py` — timeline 路由实现
- `@docs/contract.md` — `GET /api/chat/timeline` 字段定义

---

**需求原文引用**：
> **`timeline_read_service`** 提供 `get_timeline`；H5 / Open **共用**；**不经过** `chat_service`（O1）。

---

**开发任务**：
1. 新建 `backend/services/timeline_read_service.py`，迁移合并 `conversation_log` + `agent_message` 逻辑。
2. 响应字段与契约 H5 timeline **完全一致**（待查契约文档 `items[]` 结构）。

---

**完成标志**：
- [ ] `get_timeline` 可独立单测
- [ ] STEP-007 ✅

---

### [STEP-008] H5 chat 接入 service 层（回归）

**目标**：`chat.py` 的 send/resend/timeline 改调 `chat_service` + `timeline_read_service`，SSE 对外契约不变。

---

**前置条件检查**：STEP-006、STEP-007 ✅。

---

**需要参考的文件**：
- `@backend/routers/chat.py`
- `@docs/contract.md` — H5 对话模块
- `@tests/test_chat.py` 等

---

**需求原文引用**：
> Open API **不修改** H5 `/api/chat/send` SSE 行为；H5 回归无破坏（验收 #5）。

---

**开发任务**：
1. `chat_send`/`chat_resend` 调用 `check_*` + `enqueue_*`；**必须保留** `_sse_chat_wait_bundle` 作为 H5 对外 SSE 适配层（PRD 验收 #5、§4.1）。
2. `_sse_chat_wait_bundle` **应**在内部调用 `chat_service.await_bundle_payload`（O2：`asyncio.Future` + `asyncio.wait_for`，≤120s），再将 payload 转为 SSE 事件（`meta`/`delta`/`done`/`obsolete`/`failed`）；**禁止**删除 SSE 层或改用 `threading`/同步 sleep 阻塞。
3. timeline 路由改调 `timeline_read_service.get_timeline`。
4. 跑现有 chat 相关测试（含 `tests/test_step018_round_context.py` 中 `chat_send` 静态检查）+ §9.1 H5 回归项。

---

**完成标志**：
- [ ] H5 仍仅通过 SSE 暴露 send/resend；`_sse_chat_wait_bundle` 未从路由层移除
- [ ] SSE：done / failed / obsolete、10104/10105、failed_blocked→10101 行为不变
- [ ] `test_step018_round_context.py` 通过或已按需更新
- [ ] STEP-008 ✅

---

### [STEP-009] open_chat_service Facade

**目标**：封装 Open send/resend 同步 JSON 与 timeline 转发。

---

**前置条件检查**：STEP-003、004、006、007 ✅。

---

**需要参考的文件**：
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — V3、§4.3（messages 与 `_sse_chat_wait_bundle` 成功分支一致）
- `@backend/routers/chat.py` — `_sse_chat_wait_bundle` 成功分支（**实现以代码为准**；勿在 Open 层自创提取规则）

---

**需求原文引用**：
> 成功 `data`：**`{ messages, emotion, round_id }`** — `messages` 为 `[{type, content}]`（对齐 H5 SSE `done`）；obsolete → **10108**；`round_id` 从 Future payload（O4）。  
> PRD §4.3：`messages` 提取逻辑与 `_sse_chat_wait_bundle` 成功分支一致（现网实现见 `chat.py` L804–812 或 STEP-008 抽出的共享函数）。

---

**开发任务**：
1. 新建 `open_chat_service.py`：`send`/`resend`/`get_timeline`。
2. `send`/`resend`：`check_*` → `enqueue_*` → `await_bundle_payload` → 组装 V3 JSON。
3. **messages 提取**：与 `_sse_chat_wait_bundle` 成功分支一致——读 `payload["step5"]["messages"]`，空则回退 `payload["reply"]` 单条；**推荐**在 STEP-008 抽共享函数（如 `build_done_messages_from_payload`），Open/H5 **共用**，避免双份实现漂移。
4. 新增 `schemas/open_chat.py`（send Body；**resend 无 Body Schema**）。
5. **禁止** `import routers.chat`。

---

**完成标志**：
- [ ] 成功响应仅含 V3 三字段；10108/10101/10102 映射正确
- [ ] `messages` 与 H5 SSE `done` 同源（共享函数或对齐 `chat.py` 逻辑）
- [ ] STEP-009 ✅

---

### [STEP-010] Open chat 路由 + main 挂载

**目标**：暴露 `/api/open/v1/chat/*` 三个接口并注册到 FastAPI。

---

**前置条件检查**：STEP-009 ✅。

---

**需要参考的文件**：
- `@backend/main.py`
- `@backend/routers/agent.py` — 路由前缀风格参考

---

**需求原文引用**：
> `POST .../send`；`POST .../resend` **v1 路由不声明 Body**；`GET .../timeline`；鉴权失败 HTTP 401 + `detail`。

---

**开发任务**：
1. `backend/routers/open/chat.py`，prefix `/api/open/v1/chat`。
2. `resend` 路由 **不声明** body 参数（O7）。
3. `main.py` `include_router`；确认 API Key **不能**访问 `/api/chat/*`（S1 由 JWT 路由自然拒绝）。

---

**完成标志**：
- [ ] 空 POST resend 不 422
- [ ] STEP-010 ✅

---

### [STEP-011] open_agent Facade + 路由

**目标**：Open 侧 3 个 agent 接口，data 与 H5 一致。

---

**前置条件检查**：STEP-003 ✅。

---

**需要参考的文件**：
- `@backend/routers/agent.py`
- `@docs/contract.md` — `/api/agent` 模块

---

**需求原文引用**：
> C-Open 全量含 **agent unread-count**；`data` **原样复用** H5。

---

**开发任务**：
1. `open_agent_service.py` 包装现有 agent 查询/已读逻辑。
2. `routers/open/agent.py`，prefix `/api/open/v1/agent`。
3. `main.py` 挂载。

---

**完成标志**：
- [ ] 三接口与 H5 字段一致
- [ ] STEP-011 ✅

---

### [STEP-012] Admin Open API Key API

**目标**：后台查询/生成/重新生成 Key，写审计日志，明文仅响应一次。

---

**前置条件检查**：STEP-002 ✅。

---

**需要参考的文件**：
- `@backend/routers/admin/users.py`
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §4.6、§6.3、V5/V6/N4

---

**需求原文引用**：
> GET/POST `/api/admin/users/{user_id}/open-api-key`；重新生成 **单行 UPDATE**；首次 `action=create`，重新生成 `action=edit`；**禁止**日志明文 Key。

---

**开发任务**：
1. GET：状态、key_prefix、created_at、last_used_at（分钟精度展示在 UI）。
2. POST：生成 `sk-lxm-` + ≥32 字节随机；hash 入库；返回一次性 `api_key`。
3. RBAC：`super_admin` + `ops_admin`。
4. `log_operation()` 按 N4。

---

**完成标志**：
- [ ] 重新生成后旧 Key 立即 401（可用手工测 Open）
- [ ] STEP-012 ✅

---

### [STEP-013] Admin 用户详情 Key UI

**目标**：用户详情页 Open API Key 管理区块。

---

**前置条件检查**：STEP-012 ✅。

---

**需要参考的文件**：
- `@admin/pages/user-detail.html`
- `@admin/static/js/admin-api.js`

---

**需求原文引用**：
> 状态未开通/已开通；脱敏 `key_prefix`；生成/重新生成二次确认；**v1 不展示** Base URL（N7）。

---

**开发任务**：
1. UI 区块 + 调用 GET/POST API。
2. 生成成功弹窗展示明文一次，复制后不再显示。
3. 权限与 C8 角色一致。

---

**完成标志**：
- [ ] ops_admin / super_admin 可见；其他角色不可见
- [ ] STEP-013 ✅

---

### [STEP-014] 第三方文档 open-api-v1.md

**目标**：交付第三方可读集成文档。

---

**前置条件检查**：STEP-010、011 ✅。

---

**需要参考的文件**：
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §10.3、验收 #6

---

**需求原文引用**：
> 含：401 示例、六接口、10108 文案、failed_blocked 不可 resend（TD-030）、托盘轮询、超时 ≥130s、传输安全 S16、生产 `http://cllxm.com` curl 示例。

---

**开发任务**：
1. 新建 `docs/design/open-api-v1.md`。
2. 独立「传输安全」章节（N9）。
3. C15 Base URL + Key 配置说明。
4. **TD-030**：写明 `failed_blocked` **不可** `resend`，须重新 `send`（仅 `failed_timeout`/`failed_error` 可 resend）；与 PRD §8、验收 #6/#14 一致。

---

**完成标志**：
- [ ] 文档与实现路径一致
- [ ] `failed_blocked` / resend 说明已写入（满足 TD-030「当前处理」第 2 条）
- [ ] STEP-014 ✅

---

### [STEP-015] contract.md + tech-debt + Nginx + 部署说明

**目标**：同步契约、技术债文档、Nginx 注释、pepper 部署文档。

---

**前置条件检查**：STEP-010~014 ✅。

---

**需要参考的文件**：
- `@docs/contract.md`
- `@docs/tech-debt.md` — **[TD-030]**、**[TD-031]**（PRD §8）
- `@docs/design/PRD-OpenAPI-APIKey-v1.md` — §8
- `@nginx/nginx.conf`
- `@DEPLOY.md` 或 `docs/ops/docker-admin-deploy.md`

---

**需求原文引用**：
> §8：**TD-030**（`failed_blocked` 不可叹号重发，V4 本期接受现状，完整描述见 tech-debt）；**TD-031**（10104 非原子，搬迁后行为一致不恶化，完整描述见 tech-debt）。

---

**开发任务**：
1. `contract.md` 新增 Open API v1 模块（6 接口 + 401 三场景 + 10108 + Admin Key API）。
2. **`docs/tech-debt.md` 核对/同步**（债项正文仓库已存在，本期**不改运行时行为**）：
   - **[TD-030]**：确认「位置」含 `chat_service` 搬迁后的 `_open_window_has_bang` / resend 单点；确认「当前处理」已指向 `open-api-v1.md`（STEP-014 交付）。
   - **[TD-031]**：将「位置」从 `chat.py` 内联更新为 **`chat_service.check_send_quota`**（及 `_fetch_open_window_user_rows` 若仍被其调用）；注明 Open v1 已落地。
   - 顶栏索引若缺 TD-030/031 链接则补全。
3. `nginx.conf` 注释禁止记录 `$http_authorization`（N8）。
4. DEPLOY 增加 pepper 生成与多环境说明（V2）。

---

**完成标志**：
- [ ] 契约与代码一致；顶部「最后更新」为今日
- [ ] TD-030 / TD-031 条目与本期实现路径、open-api-v1.md 交叉引用一致
- [ ] STEP-015 ✅

---

## 4. 自检清单

- [x] 需求文档中每一条功能都有对应的 STEP（F1~F19 → STEP-000~015；F19 收口于 STEP-014/015）
- [x] 没有增加需求文档中不存在的功能（未拆 disable Key、Admin Base URL 等）
- [x] 自定义字段已标注（进度表备注等）
- [x] 不确定路径已标注「待查代码仓库」（如 `user_banned` Redis）
- [x] 关联 H5/agent 契约引用 `docs/contract.md`，未重新验证 H5 合理性
- [x] 环节依赖逻辑正确（搬迁前先 STEP-000；Open 在 service 后）
- [x] 每个 STEP 含完成回调指令
- [x] 进度文档 `docs/progress/PRD-OpenAPI-APIKey-v1_progress.md` 已生成

---

## 附录 A：原项目修改范围总览

> 以下与 PRD §7.1 对齐，并结合当前仓库实况（`chat_service.py` 几乎为空、主链在 `chat.py` ~1000+ 行）。

### A.1 按层级

| 层级 | 变更类型 | 路径/模块 |
|------|----------|-----------|
| **数据层** | 新增表 | `user_api_keys`（+ ORM `models/user_api_key.py`） |
| **配置** | 新增必填 env | `OPEN_API_PEPPER`；`config.py` + `main.py` lifespan |
| **鉴权** | 新增 | `utils/open_api_auth.py`（与 `auth_middleware.py` JWT 并行） |
| **服务层** | 大改/新增 | `services/chat_service.py`（从空壳变为写路径+校验核心） |
| **服务层** | 新增 | `services/timeline_read_service.py`、`open_chat_service.py`、`open_agent_service.py` |
| **路由** | 大改 | `routers/chat.py`（改调 service，保留 `_execute_llm_bundle`+SSE） |
| **路由** | 新增 | `routers/open/chat.py`、`routers/open/agent.py` |
| **路由** | 中改 | `routers/admin/users.py`（Key API） |
| **入口** | 小改 | `main.py`（挂载 open router、pepper 检查） |
| **常量** | 小改 | `constants.py`（10108） |
| **Schema** | 新增 | `schemas/open_*.py` |
| **管理后台** | 中改 | `admin/pages/user-detail.html`、`admin/static/js/admin-api.js` |
| **文档** | 新增/更新 | `docs/design/open-api-v1.md`、`docs/contract.md`、`DEPLOY.md` |
| **部署** | 注释 | `nginx/nginx.conf`（N8） |
| **技术债** | 核对/同步（不改行为） | `docs/tech-debt.md` **[TD-030]**、**[TD-031]**（STEP-014 文档 + STEP-015 路径与交叉引用；债项正文已存在） |

### A.2 明确不改或最小触碰

| 模块 | 说明 |
|------|------|
| `_execute_llm_bundle`、Step5/6、记忆、成长值 | 仍在 `chat.py`（或既有 service），Open **不复制** |
| `_build_round_context` | **本期不迁**；`prompt_mgmt` 继续 `from routers.chat import` |
| H5 前端页面 | **无必须改动**（第三方用 Open API） |
| JWT 登录注册、`/api/auth/*` | 无变更 |
| `conversation_log` 等核心业务表 | **无结构变更**（§6.2） |
| DashVector / 向量库 Admin Key | 与 Open API Key **无关**（grep 中的 api_key 为另一业务） |

### A.3 测试与回归影响面

| 范围 | 原因 |
|------|------|
| `tests/test_chat.py`、`test_step012_content_safety.py` 等 | 符号从 `chat.py` 迁至 `chat_service` 时需改 import 或测 service |
| `tests/test_step018_round_context.py` | **主要**依赖 `_build_round_context`（本期不迁，不受 Future/enqueue 搬迁影响）；**另含** `chat_send` 源码静态检查 — STEP-008 改 `chat_send` 后须回归 |
| 建议新增 Open API 集成测试 | 鉴权 401、send JSON、10108 双端、Key 吊销 |

### A.4 改动量粗估（PRD §7.1）

| 量级 | 文件 |
|------|------|
| **大** | `chat_service.py`、`routers/chat.py` |
| **中** | `open_api_auth.py`、`timeline_read_service.py`、`open_chat_service.py`、`routers/open/chat.py`、`admin/users.py`、`user-detail.html`、`open-api-v1.md`、`contract.md` |
| **小** | 模型、open agent、config、main、constants、nginx 注释、admin-api.js |
