# Core User Auth Api

- 文档 ID：`contract-core-user-auth-api`
- 权威状态：`canonical`
- 功能范围：`core-user-auth`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-001`, `TD-024`, `TD-025`

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
- **H5 设置页说明**：`frontend/pages/settings.html` 的「修改密码」仍调用本接口，但前端 Body 含 `old_password` 且未传 `confirm_password`，与 Schema 不一致；**不校验原密码**。清偿见 **TD-025**。

#### POST /api/auth/logout

- **所属端**：H5
- **鉴权**：Bearer 用户 JWT
- **请求 Body**：无
- **响应**：`ApiResponse`
- **状态**：已实现（服务端无状态，客户端删 Token）

---

### 模块：H5 用户（占位）

- **文件**：`backend/routers/user.py` 当前**无路由实现**；**未在 `main.py` 挂载**（保持不挂载）。
- **说明**：已在 `routers/user.py` **文件顶部**加入占位 TODO 注释；**产品需求确认前不挂载**，避免与其他模块路由命名冲突；实现昵称、头像等个人资料接口时在本文件扩展并再 `include_router`。
- **H5 设置页**：`frontend/pages/settings.html` 仍调用 **`GET/PUT /api/user/settings`**（`memory_auto_extract`、`agent_message_enabled`），后端未实现；见 **TD-024**。
- **状态**：占位（详见该文件内注释）

---
