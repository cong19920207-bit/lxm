# Shared Conventions

- 文档 ID：`contract-shared-conventions`
- 权威状态：`canonical`
- 功能范围：`shared-conventions`
- 必读依赖：无
- 相关技术债：无

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
| `ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`          | 20029 | 查询日期格式须为 YYYY-MM-DD；**`start_date > end_date`** 时 message 为「结束日期不能早于开始日期」（`admin_date_filter` 共用） |
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
| `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`        | 20046 | 向量/Token 热配置 PATCH 非法 |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID`  | 20047 | 角色知识库：type/key/value 非法 |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG`   | 20048 | key 超 20 汉字            |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG` | 20049 | value 超 100 汉字         |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY`  | 20050 | 同 type+key 已存在         |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND`      | 20051 | doc_id 不存在             |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED` | 20052 | Embedding 或 DashVector 失败 |


---

### H5 可选鉴权例外（2026-08-13）

H5 用户端默认仍为 `Authorization: Bearer`。仅以下三个 GET 允许完全缺少 `Authorization` 头时匿名访问；头存在但无效仍返回 HTTP `401`。细则见 `contract-h5-app-api` 与 `contract-life-feed-api`。

- `GET /api/feed/list`
- `GET /api/feed/config/header`
- `GET /api/app/persona-background`

