# 项目契约文档

> 最后更新：2026-04-13（**客户端/脚本**：H5 `chat.html` 使用 **`chatSendSession`** 与 SSE **`meta.generation_id`** 丢弃与当前发送不一致的流片段（见下文 **POST /api/chat/send** 节）；`scripts/test_chat_e2e.py` 改为 **HTTP+SSE** 调用真实接口。**延续 2026-04-12 — H5 对话 TD-015**：`conversation_log` 增加 **`delivery_status` / `skipped_in_prompt`**；**`POST /api/chat/send`** 入队即落库 user、SSE **`meta.generation_id`**、聊天 LLM **45s**；**`POST /api/chat/resend`**（用户 JWT，叹号重发 **2 次/分钟**）；**`GET /api/chat/timeline`** 的 `items[]` 与 **`GET /api/admin/users/{user_id}/conversations`** 的 `list[]` 同名字段与 **`backend/constants.py` 中单点枚举**一致；**`GET /api/chat/history`** 不含送达态，以 **timeline** 为准（H1）；错误码 **10104–10107**；部署 **Nginx `proxy_read_timeout`** 建议略大于 45s。日记「有互动」口径未改，见 **TD-018**。2026-04-08 及更早：管理端 diaries、日记 Cron 等见历次说明。）

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
| round_id           | String(36) | 否   | NULL   | TD-016：一轮多 user + 单 assistant 共用 UUID 文本；旧数据可为 NULL |
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
| created_at                     | DateTime   | 是   | utcnow |       |


### 表名：agent_message


| 字段名          | 类型         | 必填  | 默认值    | 说明    |
| ------------ | ---------- | --- | ------ | ----- |
| id           | Integer PK | 是   | 自增     |       |
| user_id      | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| trigger_type | String(10) | 是   | -      | P0–P4（见 `TriggerType` 常量类） |
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
  - **`meta`**：`{"type":"meta","generation_id":"<uuid>"}` — 客户端应丢弃与当前有效代不一致的流片段（与 TD-015 一致）
  - **H5 实现说明（`frontend/pages/chat.html`）**：每次发起 **`send` / `resend`** 前递增本地 **`chatSendSession`** 并 **`AbortController`** 打断上一请求；`consumeChatSse` 仅当传入的会话快照与 **`chatSendSession`** 一致时继续解析；收到 **`meta`** 后记录本连接 **`generation_id`**；若 **`delta`** 携带 **`generation_id`** 且与 **`meta`** 不一致则丢弃该条。服务端 DB / Redis 仍为权威真相，本段仅约束端上展示不串台。
  - **`delta`** / **`done`**：与现网一致；**`done`** 含 `emotion`
  - **`failed`**：`{"type":"failed","code":<int>,"message":"..."}` — 超时/LLM 失败等，**不**将走神类 assistant 落库
  - **`obsolete`**：本连接对应代已被新输入作废
- **失败（未进入 SSE）**：`ApiResponse` JSON — 如 **10101** 内容安全、**10104** 队列满（无叹号时未处理 ≥5）、**10102** 等
- **语义摘要**：内容安全通过后 **立即** 写入 user 行（`delivery_status=pending_llm`）；打包调度 **防抖**（默认 500ms，配置 `CHAT_DEBOUNCE_MS`）；聊天链路 LLM 超时 **45s**（`LLM_TIMEOUT_CHAT`）；成功闭环后写 assistant 与异步后置任务（成长、记忆、`ai_emotion` 等）
- **关联表**：conversation_log, emotion_log（异步）；Redis `chat:gen:{user_id}`、防抖键、`ai_emotion:{user_id}` 等
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
- **`items[]`（conversation_log 来源）**：`source`, `sort_seq`, `id`, `content`, `created_at`, `emotion_label`, **`delivery_status`**, **`skipped_in_prompt`**, `is_read`, `trigger_type`（后两者对 agent 有值）；**`delivery_status` 取值**与 **`backend/constants.py`** 中单点常量一致（示例：`delivered`、`pending_llm`、`failed_timeout`、`failed_error`），**不在**契约全文复制枚举表（J2）
- **assistant / agent 行**：`delivery_status`、`skipped_in_prompt` **键存在且值为 `null`**（A1）
- **关联表**：conversation_log, agent_message
- **状态**：已实现

#### 部署与网关（对话 SSE）

- **Nginx**：`location` 代理 H5 **`/api/chat/send`**、**`/api/chat/resend`** 时，建议 **`proxy_read_timeout`** 设置为 **≥ 50s**（略大于 `LLM_TIMEOUT_CHAT` 默认 45s），避免长耗时 SSE 被网关提前断开。

---

### 模块：H5 日记（`/api/diary`）

#### GET /api/diary/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`（1–50）
- **响应**：`ApiResponse`；`data` 为 `DiaryListResponse`：`items`（`DiaryItem`: id, content, relationship_level_at_creation, is_read, created_at）, total, page, page_size
- **说明**：成功响应 JSON **从不**包含 `diaries` 键；客户端须使用 **`items`**（与全局「字段命名规范」一致）。
- **内容安全（产品已定案）**：AI 日记正文为系统生成内容，**当前**不对 LLM 输出做与 H5 用户消息同款的独立 `check_content`；合规边界以 PRD 与本条为准。
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

- **接口**：仍仅消费 **`GET /api/diary/list`**（`items`）、**`POST /api/diary/{id}/read`**；**无** 请求/响应结构变更。
- **初始化**：**不**以 `GET /api/relationship/status` 阻塞日记列表；关系等级在后台并行更新，用于空状态文案（`relationship_level` 仍可读 `localStorage` 兜底）。
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

#### POST /api/admin/auth/logout / change-password

- **响应**：`ApiResponse`；需 Bearer Admin JWT
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
- **管理端详情页（`admin/pages/user-detail.html`）**：成功拉取详情后，仅在 `**loadUserDetail`** 内将上述嵌套**展平**为脚本内存变量 `**userData`**（不修改接口响应）。展平规则：`basic.*` 字段名保持不变；`relationship.level` → `relationship_level`；`relationship` 其余键名不变；`activity.active_days_last7` → `active_days_7d`；`activity.agent_message_reply_count` → `agent_reply_count`；`activity.total_conversation_count` 不变。若 `data` 缺少 `basic` / `relationship` / `activity` 任一层，前端提示「用户详情数据格式异常」且不写入 `userData`。**「AI日记」Tab**：**首次**切换到该 Tab 时请求 **`GET /users/{user_id}/diaries`** **不带**日期（全量时间、倒序第一页）；再次进入同一用户详情会话内 **不重复**首屏请求；**「查询」**按当前日期输入从第 1 页重拉；**「加载更多」**在同一组日期条件下分页追加；表格列含日记 **`id`**（与 **`diary-history`** 第一列一致）、正文摘要、`relationship_level_at_creation` 映射等级名、已读、创建时间；正文 **`escapeHtml`**。
- `**userData` 展平后字段全集**（仅浏览器脚本内存，**非** HTTP 响应体）：`id`, `username`, `created_at`, `last_login_at`, `status`, `is_banned`, `relationship_level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`, `total_conversation_count`, `active_days_7d`, `agent_reply_count` — 与 `loadUserDetail` 实现一致，供 `renderInfoCards`、账号 Tab、顶栏操作等读取。
- **GET** `/users/{user_id}/conversations` — `data.list` 含 id, role, content, emotion_label, emotion_confidence（user 行）, persona_risk_flag, created_at, **`sort_seq`**, **`delivery_status`**, **`skipped_in_prompt`**；字段名与枚举与 H5 **`GET /api/chat/timeline`** 的 `items[]` **对齐**（assistant 行 `delivery_status` / `skipped_in_prompt` 为 **null**，A1）
- **GET** `/users/{user_id}/diaries` — 鉴权 **`super_admin` / `ops_admin` 仅**（与 **`.../conversations`**、**`GET /diary-history`** 一致；**不含** `ai_trainer`，与 **`.../memories`** 不同，属有意区分）。Query：`start_date`、`end_date`（`YYYY-MM-DD`，与 **`diary-history`** 语义相同）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**；日期非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`**。成功 `data`：`{ total, page, page_size, list }`；**`list[]`** 字段与 **`GET /api/admin/diary-history`** 的 **`list[]`** 相同：`id`, `user_id`, `username`, `content`, `relationship_level_at_creation`, `is_read`, `created_at`。实现上与 **`diary-history`** 共用 **`backend.services.admin_diary_query`**，避免双入口不一致。
- **GET** `/users/{user_id}/memories` — `data.list` 含 id, content, importance_score, source, created_at, updated_at
- **PUT** `/users/{user_id}/memories/{memory_id}` — Body：`AdminMemoryUpdateRequest` — `content`（必填，1–500 字，去首尾空白后不得为空）；`importance_score`（可选，0.0–1.0，**预留**，当前不落库）
- **DELETE** 同上路径
- **PUT** `/users/{user_id}/status` — Body `{ "action": "ban"|"unban" }`
- **POST** `/users/{user_id}/reset-password` — `data.new_password`
- **管理端页面**：`admin/pages/user-detail.html` 含「账号管理」Tab 与顶栏按钮，对接上述 PUT/POST；逻辑上 `**userData.status === 'banned'`** 与 `**basic.status`** 及用户列表 `list[].status` 一致（见错误码 20012、20013）；展示与操作均基于展平后的 `userData`（见上条）。
- **关联表**：users, **relationship**, conversation_log, memory, agent_message 等
- **状态**：已实现

---

### 模块：人格 / 情绪 / 世界观 / Prompt / 安全 / 测试用例

- **人格**：`GET/PUT/DELETE /persona/draft`，`GET /persona/current`，`POST /persona/test|publish`，`GET /persona/history`，`GET /persona/history/{version}`，`POST /persona/rollback` — Body 见 `persona.py` 内联模型
- **GET /api/admin/persona/history/{version}**：鉴权与角色同其他人格接口（`super_admin` / `ai_trainer`）。成功 `data`：`version`, `is_active`, `updated_by`, `updated_at`, `content`（JSON 解析后的对象，解析失败时为原始字符串）。版本不存在 → `20023`（`ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND`），`message` 为「版本 V{n} 不存在」。
- **POST /api/admin/persona/test** 成功 `data`（`admin_config_service.run_standard_tests`）：`total`, `passed`, `failed`, `pass_rate`, `can_publish`, `details`（数组），可选 `message`（如无测试用例等）。`details[]` 含 `case_id`, `input`, `ai_reply`, `total_score`, `level`, `style_score`, `boundary_score`, `emotion_score`, `violations`, **`passed`**（布尔，与该条是否计入通过一致，供管理端展示 Tag）。
- **情绪**：`GET /emotion-config`；`PUT /emotion-config/{emotion_name}` — `EmotionUpdateRequest`
- **世界观**：`GET|PUT /world-state/config`；`GET /world-state/history`
- **Prompt**（实现见 `backend/routers/admin/prompt_mgmt.py`）：
  - `GET /prompt/modules` — `data`：`version`（无生效配置时可为 0）、`has_draft`、`modules`（各模块含 `content`、`token_limit`、`editable`、`note` 等）、`total_token_limit`（4096）。**编辑区内容**：以本接口返回的 `modules` 为基线；若 `has_draft=true`，应用 `GET /prompt/draft` 的 `config_value` 与 `modules` **深度合并**后填充可编辑 Tab（与 `persona` 草稿优先策略一致）。
  - `GET /prompt/draft` — 无草稿时 `data` 可为 `null`。
  - `PUT /prompt/draft/{module_name}` — Body：`{ "content": string }`；`module_name` 仅允许 `system` | `relationship` | `user_memory` | `emotion` | `recent_chat`。服务端校验占位符：relationship 须含 `{{关系等级名称}}`；user_memory 须含 `{{Top5记忆列表}}`；emotion 须含 `{{用户情绪}}` 与 `{{AI联动情绪}}`。
  - `DELETE /prompt/draft` — 丢弃草稿。
  - `POST /prompt/test` — Body：`test_input`（必填）、`relationship_level`（0–3）、`emotion_label`（如 开心/悲伤/…/平静）、`mock_memories`（字符串数组）、`use_draft`（bool）。成功 `data`：`full_prompt`、`ai_reply`、`persona_match`（`total_score`、`level` 高|中|低、`style_score`、`boundary_score`、`emotion_score`、`violations`）、`content_safety`（`is_safe`、`reason`）、`token_estimate`。
  - `POST /prompt/publish` — Body：`confirm_text`（须为 `CONFIRM`）、`test_passed`（bool，为 `true` 才允许发布）；**须有草稿**。无用户端 `content` 字段，发布内容来自草稿整包。
  - `GET /prompt/history` — 分页，`data` 同人格历史列表结构（含 `summary` 摘要）。
  - `GET /prompt/history/{version}` — 与 `persona/history/{version}` 对称，成功 `data` 含 `version`、`is_active`、`updated_by`、`updated_at`、`content`（JSON 解析后的对象，失败时为原始值）。不存在 → `20023`。
  - `POST /prompt/rollback` — Body：`version`、`confirm_text: CONFIRM`
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
- **GET** `/diary-history` — Query：`user_id`、`start_date`、`end_date`（`YYYY-MM-DD`）、`page`、`page_size`（1–100）；鉴权 **`super_admin` / `ops_admin`**；成功 `data`：`{ total, page, page_size, list:[{ id, user_id, username, content, relationship_level_at_creation, is_read, created_at }] }`（**`username`** 来自 `users.username`，与 `user_id` 内联）。列表查询与 **`GET /users/{user_id}/diaries`**（固定路径用户）共用 **`fetch_admin_diary_list_page`**，在相同 **`user_id` + 日期 + 分页** 下结果一致。
- **状态**：已实现

**`DiaryRulesRequest`（PUT `/diary-rules` Body）**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `max_length` | int | 是 | 50–300 |
| `frequency` | str | 否 | 默认 `daily` |
| `generation_hour` | int | 是 | 0–5（UTC 小时） |
| `generation_minute` | int | 否 | 0–59，默认 0 |
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
- **GET** `/system/logs` — Query：`log_type`（`system` \| `error`，对应 `_LOG_TYPE_FILE_MAP`）、可选 `level`、可选 `start_date`/`end_date`（缺省为近 7 天）、`page`/`page_size`；成功 `data`：`{ total, page, page_size, list:[{ time, level, module, message }] }`；**POST** `/system/logs/export` — Query 条件同上、**无 Body**；成功为 **xlsx 流**（非 JSON 信封）；范围校验失败 HTTP 400；**查询**区间 `(end-start).days > 30`、**导出** `> 7` 被拒绝（与 `system_monitor.py` 一致）
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
- **状态**：`system` / `error` 各自维护 `pageState`（含 `hasQueried`：仅在该 Tab **从未成功请求过列表**时，切换 Tab 自动触发首次 `queryLogs`；**已加载但 0 条**不重复自动请求）；`page_size=50`；分页使用 `admin-api.js` 的 **`renderPagination`**。
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

### `admin/pages/prompt.html`（Prompt 管理）

- **实现状态**：已实现。主内容区与版本历史区栅格 **7fr : 3fr**（约 70% : 30%）；`activeKey='prompt'`，标题「Prompt管理」。`super_admin` / `ai_trainer` 以外角色跳转 `error.html?type=403`。
- **可编辑 Tab**：与后端 `_EDITABLE_MODULES` 一致：`system`、`relationship`、`user_memory`、`emotion`、`recent_chat`；固定文案提示 persona / user_input 不在本页维护。
- **首屏并行加载**：`GET /api/admin/prompt/modules`、`GET /api/admin/prompt/history?page=1&page_size=10`、`GET /api/admin/prompt/draft`；若 `has_draft` 且草稿 `config_value` 存在，与 `modules` 深度合并后写入各 Tab textarea；`savedSnapshots` **按模块**记录上次已对齐内容。**对称边界**：`has_draft===true` 但草稿体未成功合并时，Toast 警告「草稿未能加载…」以免状态栏与编辑区不一致（与 `persona` 草稿容错同类）。
- **Token 行**：`Math.ceil(文本长度 * 1.5)`，上限与 `_MODULE_TOKEN_LIMITS` 对齐（system 400、relationship 200、user_memory 500、emotion 150、recent_chat 1000）；超出用 `var(--danger)`。
- **占位符**：保存草稿前前端按 `_PLACEHOLDER_RULES` 校验，缺失则 `showToast` 且不请求。
- **状态栏**：与 `persona.html` 同款逻辑；丢弃草稿 `DELETE /api/admin/prompt/draft`。生效版本文案：`version>0` 显示 `V{version}`，否则「默认内置模板（未发布过）」（接口无 `updated_by` 元数据时的前端表述）。
- **保存草稿**：`PUT /api/admin/prompt/draft/{当前激活 module_name}`，Body `{ content }`；仅当前 Tab。
- **在线测试**：Modal 约 800×560，左 40% 表单（`use_draft` 单选、关系等级、情绪、模拟记忆最多 5 行、测试输入），右 60% 结果；`POST /api/admin/prompt/test`。展示 AI 气泡、总分条 + 等级 Tag（高≥80 / 中≥60 / 低）、三维进度条与权重说明、内容安全、`full_prompt` 折叠区（`pre` monospace，Token 按 `Math.ceil(full_prompt.length * 1.5)`）。
- **testPassed**：每次点击「开始测试」**发起请求前**置 `false`（避免上次成功、本次失败后仍可发布）；请求**成功**且 `data.ai_reply` **去空白后非空**时置 `true`（不依赖人格匹配分数）。各模块 textarea `input` 时置 `false`；关闭测试 Modal **不**重置 `testPassed`。
- **发布**：`testPassed=false` 时「发布生效」禁用；`showConfirmInput` 后 `POST /api/admin/prompt/publish`，Body `confirm_text:'CONFIRM'`、`test_passed:true`。
- **版本历史**：与 `persona` 相同交互（时间线、分页、`查看` / `回滚`）；`GET /api/admin/prompt/history/{version}` 查看 JSON；`POST /api/admin/prompt/rollback` + `CONFIRM`。

### `admin/pages/test-tool.html`（AI测试工具）

- **实现状态**：已实现。主布局 **grid 40% : 60%**（`gap:16px`）；左侧自上而下：`测试参数配置` 卡片、`最近测试记录` 卡片（`margin-top:16px`）；右侧 `测试结果` 卡片。`activeKey='test'`，顶栏标题「AI测试工具」。仅 `super_admin` / `ai_trainer` 可访问，其余角色跳转 `error.html?type=403`。样式入口：`admin-common.css` + 页内 `<style>`。
- **测试参数**：`使用配置` 单选——当前生效（`use_draft:false`）/ 草稿（`use_draft:true`）；关系等级、用户情绪；模拟记忆 `textarea`（按换行计非空行数，展示「已输入 n/5 条」，n>5 时 `.alert-warning`）；测试输入必填。
- **开始测试**：校验测试输入非空；`POST /api/admin/prompt/test`，Body 与 `PromptTestRequest` 一致（`mock_memories` 取前 5 条非空行）。成功：右侧淡入展示 AI 气泡（头像「梦」）、人格匹配总分+等级 Tag、三维进度条（40%/40%/20%）、内容安全区块、`full_prompt` 折叠区（Token 数 `Math.ceil(full_prompt.length * 1.5)`）；底部「保存为测试用例」可用。
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
- **顶部横幅**：**「已接入生成与调度；改生成时刻后须重启 backend。」**（定案见 `docs/diary-refactor-decisions.md` §6）。运维见 **`docs/ops-diary.md`**。
- **接口**：`GET` / `PUT` **`/api/admin/diary-rules`**。
  - **Body**：`DiaryRulesRequest` — 两个独立 **`textarea`**（`#gen-prompt-with` / `#gen-prompt-without`）对应 **`prompt_with_interaction`** / **`prompt_without_interaction`**；`max_length`（滑块 50–300，`step=10`）；`frequency` 固定 `"daily"`；**UTC** 时刻：`#gen-hour`（0–5）+ `#gen-minute`（0–59）。
  - **加载**：若库内仅有旧字段 **`generation_prompt`**，两套文本域均回填该值；若仅有单侧新字段则与 `generation_prompt` 策略一致（以服务端正则解析为准）。
- **保存成功**：`showToast` 提示保存成功并强调 **修改生成时刻须重启 backend** 后 Cron 才更新（与 **TD-013** 一致）。
- **字数滑块与回填**：若 `GET` 的 `max_length` 非 10 步进，**`snapMaxLengthToSliderStep`** + `warning` Toast（与契约前文一致）。
- **日记历史链接**：**仅** `super_admin` / `ops_admin` 展示（`ai_trainer` 不展示）；指向 **`diary-history.html`**。

### `admin/pages/diary-history.html`（AI 日记历史）

- **权限**：**仅** `super_admin` / `ops_admin`；其余角色跳转 `error.html?type=403`（与 **`GET /api/admin/diary-history`** 鉴权一致，`ai_trainer` 直链亦为 403）。
- **菜单**：`MENU_CONFIG` 中 **`super_admin`**、**`ops_admin`** 含 **`key: 'diary-history'`** → `diary-history.html`；**不包含** `ai_trainer`（决策 O1）。
- **接口**：`GET /api/admin/diary-history`，Query 与后端一致；列表 **`content`** 经 **`escapeHtml`** 写入表格单元格，`title` 存放完整正文（已转义）便于悬停查看；表格列：**日记 `id`**、**账号**（`username`）、**账号ID**（`user_id`，与用户管理列表用户 ID 同一含义）、正文等。
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
| **TD-007** | ~~生成与调度未读配置~~ → 已读 `diary_rules`（`diary_rules_loader` + `DiaryService` + 启动时 Cron **UTC**）；兼容旧 `generation_prompt`。 |
| **TD-008** | LLM 响应耗时无法按日拆分；数据报表 AI 性能折线用人格偏离率；仪表盘 `llm_avg_response_ms` 无样本为 `null`。 |
| **TD-009** | `report_type=feature` 缺按日 `open_rate` / `agent_replied`，表格暂 4 列。 |
| **TD-010** | `GET /system/status` 的 `alerts[]` 无单条发生时间，监控页用刷新时刻代替；补充字段时的修改范围与库内消费方见 `tech-debt.md`。 |
| **TD-011** | `get_system_status` 在 Redis INFO 异常时 `hits`/`misses` 可能未定义，存在 `NameError` 风险；见 `tech-debt.md`。 |

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
| 后台用户对话分页按 **created_at 升序**；H5 history 按 **倒序分页**；设计意图不同但字段结构略异（后台多 `persona_risk_flag`、`emotion_confidence`）                                                                                                        | `routers/admin/users.py`, `routers/chat.py`                                                                                           | 保持差异则在前端契约中写清；若需对齐则加 query 参数                                                                              | 已知差异                  |
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