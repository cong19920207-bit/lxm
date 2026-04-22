# 接口契约文档（逆向重建）

> 依据仓库扫描：`backend/main.py` 路由挂载、`backend/routers/**/*.py`、`backend/schemas/**/*.py`、`backend/constants.py`、`backend/utils/auth_middleware.py`、`backend/utils/admin_auth.py`、`backend/models/**/*.py`。  
> **无**独立 Swagger/OpenAPI YAML/JSON 配置文件；FastAPI 运行时默认提供 `/openapi.json` 与 `/docs`（未与本文逐条对拍，**实现以源码为准**）。  
> 更新时间（推断）：以仓库当前代码为准。

---

## 一、模块总览


| 分类         | 说明                                                                                                                                         |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 框架         | FastAPI，`backend/main.py` 入口                                                                                                               |
| 用户端 API 前缀 | `/api/auth`、`/api/chat`、`/api/diary`、`/api/memory`、`/api/relationship`、`/api/agent`（**无** `/h5/`、`/mobile/` 等专用前缀；H5 静态页与浏览器共用下列接口，**推断**） |
| 管理端 API 前缀 | `/api/admin/auth` 与 `/api/admin/*`                                                                                                         |
| 静态与页面      | H5：`/`、`/pages/{page}.html`、`/static`；管理端：`/admin`、`/admin/static`、`/admin/pages/{page}.html`；头像容错：`/static/images/avatar/{filename}`      |
| 统一 JSON 信封 | `backend/schemas/common.py` → `ApiResponse`：`{ "code": int, "data": any, "message": str }`；成功 `code=0`（`SUCCESS`）                          |
| 例外         | `POST /api/chat/send`、`POST /api/chat/resend` 成功路径为 **SSE**（`text/event-stream`），**非** `ApiResponse` 信封；部分管理端导出为文件流                        |
| 用户 JWT     | `Authorization: Bearer <token>`，`get_current_user` 校验；失败 **HTTP 401** + `detail` 字符串（非业务 `code`）                                           |
| 管理 JWT     | 同上；`get_current_admin` / `verify_admin_token`；`type=admin`；角色不足 **HTTP 403**                                                               |
| 占位未挂载      | `backend/routers/user.py` 仅有 TODO，**未** `include_router`                                                                                   |


**自定义异常 / 错误表达**：业务侧主要用 `ApiResponse.fail(code, message)`；鉴权用 `HTTPException`。无单独业务异常类文件；错误码集中在 `backend/constants.py`。

**Pydantic 校验失败**：FastAPI 默认 **HTTP 422**，响应体非 `ApiResponse`。

---

## 二、H5 端接口

> 按任务规则：无 `/h5/` 等前缀。下列为 **面向 H5 前端目录 `frontend/` 的 HTTP 页面与静态资源**（推断：由 `main.py` 与 `StaticFiles` 直接暴露）。


| 方法  | 路径                                 | 功能说明                              |
| --- | ---------------------------------- | --------------------------------- |
| GET | `/`                                | 返回 `frontend/pages/login.html`    |
| GET | `/pages/{page_name}.html`          | 子页面；文件不存在时回退 `login.html`         |
| GET | `/static/images/avatar/{filename}` | 头像；不存在则 `default.png`             |
| —   | `/static/*`                        | `StaticFiles(frontend/static)` 挂载 |


**请求/响应**：文件响应为主，无统一 JSON 信封。

---

## 三、客户端接口

> URL 前缀符合任务中的 `**/api/`**（客户端归类）。**同一套接口由 H5 页面调用**（推断：与第二节并存，无独立 `/app/` 路由）。

### 3.1 通用说明

- **鉴权**：除注册、登录、重置密码外，均需 Bearer 用户 JWT。
- **响应**：除下文注明外，均为 `ApiResponse`；HTTP 状态码多为 200，业务错误看 `code`。

### 3.2 认证 `/api/auth`


| 方法   | 路径                         | 功能   | 请求                                                                        | 响应 data / 说明                   | 可能 code / 异常                     |
| ---- | -------------------------- | ---- | ------------------------------------------------------------------------- | ------------------------------ | -------------------------------- |
| POST | `/api/auth/register`       | 注册   | Body：`RegisterRequest`（username 6–20 字母数字；password 8–20；confirm_password） | `{ token, user_id, username }` | 10002–10007、10004 等              |
| POST | `/api/auth/login`          | 登录   | Body：`LoginRequest`（username, password, remember_me 默认 false）             | 同上；记住我 30 天 / 否则 1 天           | 10008–10011、10009（带剩余次数 message） |
| POST | `/api/auth/reset-password` | 重置密码 | Body：`ResetPasswordRequest`（username, new_password, confirm_password）     | 成功仅 message                    | 10005–10008 等                    |
| POST | `/api/auth/logout`         | 登出   | Header Bearer                                                             | message                        | 401 未授权                          |


### 3.3 对话 `/api/chat`


| 方法   | 路径                   | 功能               | 请求                                                                                               | 响应                                                                                                     | 可能 code / 说明                                            |
| ---- | -------------------- | ---------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| POST | `/api/chat/send`     | 发送消息（防抖入队 + SSE） | Body：`ChatSendRequest`：`content` 1–2000；`client_message_id` 可选 ≤64 【待补全：与幂等/10106 服务端联动若未接线则仅透传】 | **SSE**：首帧 `meta.generation_id`；`delta`；`done`+emotion；`failed`/`obsolete`                             | 入队前 JSON 失败：10100、10102、10101、10104；流内 failed 含 10102 等 |
| POST | `/api/chat/resend`   | 叹号重发             | Body：`ChatResendRequest`（`client_resend_id` 可选）                                                  | 同 SSE                                                                                                  | 10107、10105                                             |
| GET  | `/api/chat/history`  | 分页历史             | Query：`page`≥1，`page_size` 1–50                                                                  | `{ messages[], total, page, page_size }`；**无** `delivery_status`/`sort_seq`                            | 401                                                     |
| GET  | `/api/chat/timeline` | 统一时间线            | Query：`cursor` 可选；`limit` 1–50                                                                   | `{ items[], next_cursor, has_more }`；项含 `source`、`sort_seq`、`delivery_status`（assistant/agent 为 null）等 | 401                                                     |


**SSE 事件类型（摘要）**：`meta`、`delta`、`done`、`failed`（`type, code, message`）、`obsolete`。

**常量**：`delivery_status` 与 `backend/constants.py` 中 `DELIVERY_STATUS_*` 一致。

### 3.4 日记 `/api/diary`


| 方法   | 路径                           | 功能   | 请求                            | 响应 data                                                                                                                 | 可能 code |
| ---- | ---------------------------- | ---- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------- |
| GET  | `/api/diary/list`            | 列表   | Query：`page`，`page_size` 1–50 | `DiaryListResponse`：`items[]`（id, content, relationship_level_at_creation, is_read, created_at）, total, page, page_size | 401     |
| POST | `/api/diary/{diary_id}/read` | 标记已读 | Path：`diary_id`               | 空 data                                                                                                                  | 10300   |


### 3.5 记忆 `/api/memory`


| 方法     | 路径                        | 功能   | 请求                                       | 响应 data                                                    | 可能 code     |
| ------ | ------------------------- | ---- | ---------------------------------------- | ---------------------------------------------------------- | ----------- |
| GET    | `/api/memory/list`        | 分页列表 | Query：`page`，`page_size`                 | `{ total, page, page_size, list[] }`；元素见 `_memory_to_dict` | 401         |
| PUT    | `/api/memory/{memory_id}` | 编辑   | Body：`MemoryUpdateRequest.content` 1–500 | 成功无 data                                                   | 10001、10200 |
| DELETE | `/api/memory/{memory_id}` | 删除   | Path                                     | 成功无 data                                                   | 10200       |
| POST   | `/api/memory/add`         | 手动新增 | Body：`MemoryAddRequest.content` 1–500    | 单条记忆 dict                                                  | 10001       |


**list 元素字段**：`id, content, importance_score, source, created_at, updated_at, expires_at`（ISO 字符串或 null）。

### 3.6 关系 `/api/relationship`


| 方法  | 路径                             | 功能     | 响应 data（源码摘要）                                                                                                         | 可能 code                            |
| --- | ------------------------------ | ------ | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| GET | `/api/relationship/status`     | 关系概览   | `level, level_name, growth_value, current_growth, next_threshold, progress_percent, silence_days, ai_current_emotion` | 401                                |
| GET | `/api/relationship/history`    | 今日成长明细 | 数组：`action_type, earned_today, daily_limit, points_per_action`（服务层聚合）                                                 | 401                                |
| GET | `/api/relationship/detail`     | 详情页    | `level_info, growth_info, milestones, level_history, today_growth, ai_current_emotion` 等                              | 401                                |
| GET | `/api/relationship/growth-log` | 成长日志分页 | Query：`page`，`page_size`                                                                                              | `{ list, total, page, page_size }` |


### 3.7 主动消息 `/api/agent`


| 方法   | 路径                                      | 功能   | 响应 data                                                  | 可能 code |
| ---- | --------------------------------------- | ---- | -------------------------------------------------------- | ------- |
| GET  | `/api/agent/messages`                   | 未读列表 | 数组：`id, trigger_type, content, action_score, created_at` | 401     |
| POST | `/api/agent/messages/{message_id}/read` | 标记已读 | message                                                  | 10400   |
| GET  | `/api/agent/unread-count`               | 未读数  | `{ count }`                                              | 401     |


---

## 四、管理后台接口

> 前缀：`/api/admin/auth` 或 `/api/admin/...`；鉴权 Bearer **Admin** JWT；多数写操作记 `admin_operation_logs`（实现细节见各路由）。**角色**：`require_role(...)` 或 `dependencies=[require_role(...)]` 标注于源码。

### 4.1 认证 `/api/admin/auth`


| 方法   | 路径                                | 功能  | 请求 Body                      | 失败 code           |
| ---- | --------------------------------- | --- | ---------------------------- | ----------------- |
| POST | `/api/admin/auth/login`           | 登录  | `AdminLoginRequest`          | 20001–20003、20007 |
| POST | `/api/admin/auth/logout`          | 登出  | —                            | 401               |
| POST | `/api/admin/auth/change-password` | 改密  | `AdminChangePasswordRequest` | 20004–20007       |


成功登录 `data`：`token, username, role, need_change_password`（`AdminLoginResponse` 字段）。

### 4.2 超级管理员账号 `/api/admin`


| 方法     | 路径                                      | 依赖角色        | 说明                          |
| ------ | --------------------------------------- | ----------- | --------------------------- |
| GET    | `/accounts`                             | super_admin | `data` 为账号数组（无分页包装）         |
| POST   | `/accounts`                             | super_admin | `AdminCreateAccountRequest` |
| PUT    | `/accounts/{account_id}`                | super_admin | `AdminUpdateAccountRequest` |
| DELETE | `/accounts/{account_id}`                | super_admin | 20015–20018                 |
| POST   | `/accounts/{account_id}/reset-password` | super_admin | 返回 `new_password`           |
| POST   | `/accounts/{account_id}/unlock`         | super_admin | 未锁定也可 code=0                |


### 4.3 操作日志 `/api/admin`


| 方法   | 路径                         | 角色（源码）                           | 说明                  |
| ---- | -------------------------- | -------------------------------- | ------------------- |
| GET  | `/operation-logs`          | super_admin, ops_admin, tech_ops | 分页 list             |
| GET  | `/operation-logs/{log_id}` | 同上                               | 含 before/after      |
| POST | `/operation-logs/export`   | 同上                               | Excel 流，Query 同列表筛选 |


### 4.4 用户管理 `/api/admin`


| 方法     | 路径                                      | 角色                     | 说明                        |
| ------ | --------------------------------------- | ---------------------- | ------------------------- |
| GET    | `/users`                                | super_admin, ops_admin | 多条件筛选 + 分页                |
| GET    | `/users/{user_id}`                      | 同上                     | 嵌套 basic/relationship/... |
| GET    | `/users/{user_id}/conversations`        | 同上                     | 对话审计                      |
| GET    | `/users/{user_id}/emotion-rounds`       | 同上                     | 情绪轮次                      |
| GET    | `/users/{user_id}/memories`             | + ai_trainer           | 分页记忆                      |
| GET    | `/users/{user_id}/diaries`              | super_admin, ops_admin | 日记                        |
| PUT    | `/users/{user_id}/memories/{memory_id}` | + ai_trainer           | Body 含 content 等          |
| DELETE | `/users/{user_id}/memories/{memory_id}` | + ai_trainer           |                           |
| PUT    | `/users/{user_id}/status`               | super_admin, ops_admin | ban/unban                 |
| POST   | `/users/{user_id}/reset-password`       | super_admin, ops_admin | H5 用户重置                   |


### 4.5 配置与内容模块（均挂 `/api/admin`，节选路径）


| 模块      | 方法                  | 路径模式                                                                                                                                                           | 备注                                                                                                                  |
| ------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 人格      | GET/PUT/DELETE/POST | `/persona/current`、`/persona/draft`、`/persona/test`、`/persona/publish`、`/persona/history`、`/persona/rollback`                                                  | 20019–20023 等                                                                                                       |
| Prompt  | GET/PUT/DELETE/POST | `/prompt/modules`、`/prompt/draft/{module_name}`、`/prompt/test`、`/prompt/publish`、`/prompt/history`、`/prompt/rollback`                                          | 20024–20026 等                                                                                                       |
| 记忆规则/向量 | GET/PUT/POST/DELETE | `/memory-rules`、`/vector-db-config`、`/vector-db-config/test-connection`、`/memories/global`、`/memories/batch-delete`                                            | 20027–20029                                                                                                         |
| Agent   | GET/PUT             | `/agent-rules`、`/agent-message-rules/{trigger_type}`、`/agent-night-keywords`、`/agent-messages`                                                                 | 20030–20032、20029                                                                                                   |
| 关系与日记规则 | GET/PUT/GET         | `/relationship-rules`、`/diary-rules`、`/diary-history`                                                                                                          | 20033–20034                                                                                                         |
| 情绪配置    | GET/PUT             | `/emotion-config`、`/emotion-config/{emotion_name}`                                                                                                             | 20035                                                                                                               |
| 世界状态    | GET/PUT/GET         | `/world-state/config`、`/world-state/history`                                                                                                                   |                                                                                                                     |
| 内容安全    | GET/PUT/POST        | `/safety-rules`、`/safety-rules/banned-keywords`、`persona-keywords`、`style-keywords`、`banned-keywords/import`                                                   | 20036–20037                                                                                                         |
| 测试用例    | GET/POST/DELETE     | `/test-cases/{config_key}`、`/test-cases/{config_key}/{case_id}`                                                                                                | 20043–20044                                                                                                         |
| 统计      | GET/POST            | `/stats/dashboard`、`/stats/trend`、`/stats/report`、`/stats/report/export`                                                                                       | 20042；部分参数错为 **HTTP 400**（源码）                                                                                       |
| 系统监控    | GET/PUT/POST        | `/system/status`、`/third-party/status`、`/third-party/{service_name}/config`、`/third-party/{service_name}/test-connection`、`/system/logs`、`/system/logs/export` | 20038–20041；**PUT 第三方配置连接失败返回 `code=5001`**（与常量 `ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED=20040` 不一致，**以源码为准**） |


**【待补全】**：各管理接口完整 Query/Body 字段请以对应 `backend/routers/admin/*.py` 与 Pydantic 模型为准（本文保持索引级契约）。

---

## 五、统一异常码表

### 5.1 用户端业务码 `0` / `10000+` / `10200+` …


| code        | 常量（节选）                     | 默认 message  | 典型场景                       |
| ----------- | -------------------------- | ----------- | -------------------------- |
| 0           | SUCCESS                    | success     | 成功                         |
| 10000       | ERR_SYSTEM                 | 系统内部错误      | 通用                         |
| 10001       | ERR_PARAM_INVALID          | 参数校验失败      | 记忆空内容等                     |
| 10002–10003 | 用户名格式/敏感词                  | 见 constants | 注册                         |
| 10004       | ERR_USERNAME_EXISTS        | 用户名已存在      | 注册                         |
| 10005–10007 | 密码相关                       | 见 constants | 注册/重置                      |
| 10008–10013 | 登录/Token                   | 见 constants | 登录、鉴权类失败在 JWT 层多为 401      |
| 10100       | ERR_CONTENT_EMPTY          | 消息内容不能为空    | chat send                  |
| 10101       | ERR_CONTENT_UNSAFE         | 内容安全        | send                       |
| 10102       | ERR_LLM_FAILED             | 小梦暂时无法回复    | LLM/并行失败/SSE failed        |
| 10103       | ERR_CHAT_RATE_LIMIT        | 消息发送太频繁     | **常量已定义**；【待补全】发送路由是否使用    |
| 10104       | ERR_CHAT_QUEUE_FULL        | 待处理消息过多     | send                       |
| 10105       | ERR_CHAT_RESEND_LIMIT      | 重试过于频繁      | resend                     |
| 10106       | ERR_CHAT_IDEMPOTENT_REPLAY | 重复请求已忽略     | **常量已定义**；【待补全】与 send 幂等联动 |
| 10107       | ERR_CHAT_NOTHING_TO_RESEND | 当前没有需要重试的消息 | resend                     |
| 10200–10202 | 记忆模块                       | 见 constants | memory                     |
| 10300       | ERR_DIARY_NOT_FOUND        | 日记不存在       | diary read                 |
| 10400       | ERR_AGENT_MSG_NOT_FOUND    | 主动消息不存在     | agent read                 |


### 5.2 管理端业务码 `20001–20045`

见 `backend/constants.py` 中 `ADMIN_ERR`_* 与 `ADMIN_ERROR_MESSAGES`；与 H5 数值段独立。

### 5.3 其它 HTTP / 非枚举 JSON


| 场景               | HTTP              | 说明                                                                     |
| ---------------- | ----------------- | ---------------------------------------------------------------------- |
| 用户 JWT 缺失/无效/禁用  | 401               | `get_current_user`：`detail` 中文文案                                       |
| 管理 JWT 问题 / 账号禁用 | 401               | `get_current_admin` / `verify_admin_token`                             |
| 角色不足             | 403               | `require_role`：「权限不足」                                                  |
| Pydantic 校验失败    | 422               | FastAPI 默认结构                                                           |
| 第三方服务名非法等        | 400               | `system_monitor` 部分 `HTTPException`                                    |
| 未捕获异常            | 500               | 非 `ApiResponse`                                                        |
| 第三方配置保存前测试失败     | 200 + `code=5001` | `PUT /api/admin/third-party/{service_name}/config`（与 20040 并存差异，以源码为准） |


---

## 六、数据字典

> 结合 `backend/models/*.py` 与迁移/脚本（`scripts/schema_ddl.sql` 等可能存在历史差分，**以 SQLAlchemy Model 为准**）。仅列核心表。

### 6.1 `users`


| 字段                                | 类型                | 说明                                                |
| --------------------------------- | ----------------- | ------------------------------------------------- |
| id                                | PK int            | 用户 ID                                             |
| username                          | String(20) unique | 登录名                                               |
| password_hash                     | String(255)       | 密码哈希                                              |
| created_at / last_login_at        | DateTime          | 注册 / 最后登录                                         |
| relationship_level / growth_value | int               | **与用户关系表并行存在（历史字段）**；权威读法以业务层 relationship 为准（推断） |
| is_banned                         | bool              | 封禁                                                |
| login_fail_count / locked_until   | int / DateTime    | 登录失败与锁定                                           |


### 6.2 `relationship`


| 字段                     | 类型                | 说明   |
| ---------------------- | ----------------- | ---- |
| id                     | PK                |      |
| user_id                | FK users          | 唯一用户 |
| level                  | int               | 0–3  |
| growth_value           | int               |      |
| last_interaction_at    | DateTime nullable |      |
| consecutive_login_days | int               |      |
| updated_at             | DateTime          |      |


### 6.3 `conversation_log`


| 字段                                    | 类型                  | 说明                                      |
| ------------------------------------- | ------------------- | --------------------------------------- |
| id                                    | PK                  |                                         |
| user_id                               | FK                  |                                         |
| role                                  | String(20)          | user / assistant                        |
| content                               | Text                |                                         |
| emotion_label / emotion_confidence    | 可选                  | 用户消息侧                                   |
| memory_injected                       | JSON                |                                         |
| persona_risk_flag / persona_risk_type | bool / str          |                                         |
| sort_seq                              | BigInteger          | 时间线序                                    |
| delivery_status                       | String(32) nullable | user 行：pending/delivered/failed_* 等     |
| skipped_in_prompt                     | bool                | 未进入本轮 Prompt                            |
| round_id                              | String(36) nullable | **TD-016/V2**：一轮多 user + 单 assistant 关联 |
| created_at                            | DateTime            |                                         |


### 6.4 `emotion_log`


| 字段                         | 类型                  | 说明        |
| -------------------------- | ------------------- | --------- |
| id                         | PK                  |           |
| user_id                    | FK                  |           |
| emotion_label / confidence |                     |           |
| conversation_id            | FK conversation_log | 锚点 user 行 |
| round_id                   | String(36) nullable | 与对话轮次对齐   |
| created_at                 | DateTime            |           |


### 6.5 `user_short_term_emotion`（TD-020）


| 字段                         | 类型            | 说明         |
| -------------------------- | ------------- | ---------- |
| id                         | PK            |            |
| user_id                    | FK unique     | 每用户一行      |
| emotion_label / confidence |               | 短期情绪画像     |
| payload                    | Text nullable | 可选 JSON 文本 |
| updated_at                 | DateTime      |            |


### 6.6 `memory`


| 字段                                   | 类型           | 说明                    |
| ------------------------------------ | ------------ | --------------------- |
| id / user_id                         |              |                       |
| content                              | Text         |                       |
| importance_score                     | float        |                       |
| source                               | String(20)   | auto / manual / admin |
| dashvector_id                        | str nullable | 向量侧                   |
| is_deleted                           | bool         | 软删                    |
| created_at / updated_at / expires_at |              |                       |


### 6.7 `ai_diary`


| 字段                             | 类型       | 说明  |
| ------------------------------ | -------- | --- |
| id / user_id / content         |          |     |
| relationship_level_at_creation | int      |     |
| is_read                        | bool     |     |
| created_at                     | DateTime |     |


### 6.8 `agent_message`


| 字段                     | 类型         | 说明    |
| ---------------------- | ---------- | ----- |
| id / user_id           |            |       |
| trigger_type           | String     | P0–P4 |
| content / action_score |            |       |
| is_read                | bool       |       |
| sort_seq               | BigInteger |       |
| created_at             | DateTime   |       |


### 6.9 `login_log`


| 字段                      | 类型         | 说明                        |
| ----------------------- | ---------- | ------------------------- |
| id / user_id / login_at |            |                           |
| time_period             | String(20) | morning / evening / other |
| created_at              | DateTime   |                           |


### 6.10 `world_state`


| 字段                      | 类型           | 说明  |
| ----------------------- | ------------ | --- |
| id / user_id / content  |              |     |
| trigger_conversation_id | int nullable |     |
| relevance_weight        | float        |     |
| created_at              | DateTime     |     |


### 6.11 `relationship_growth_log` / `relationship_level_history`

标准字段：user_id、action_type/points/created_at；等级历史：from_level、to_level、achieved_at。

### 6.12 `user_timeline_seq`


| 字段       | 说明         |
| -------- | ---------- |
| user_id  | PK/FK      |
| next_seq | BigInteger |


### 6.13 `admin_users`


| 字段                                                             | 说明                                |
| -------------------------------------------------------------- | --------------------------------- |
| id, username, password_hash, role                              | 角色枚举见 `AdminCreateAccountRequest` |
| remark, is_active, is_locked, login_fail_count                 |                                   |
| last_login_at, last_password_change_at, created_at, created_by |                                   |


### 6.14 `admin_config`


| 字段                                                   | 说明                                        |
| ---------------------------------------------------- | ----------------------------------------- |
| config_key / config_value                            | 同一 key 可多行（草稿/生效/历史），**勿**对 key 单列 UNIQUE |
| version, is_active, is_draft, updated_by, updated_at |                                           |


### 6.15 `admin_operation_logs`


| 字段                                                | 说明  |
| ------------------------------------------------- | --- |
| id, admin_user_id nullable, admin_username        |     |
| module, action, target_description                |     |
| before_value, after_value, ip_address, created_at |     |


---

**文档结束**