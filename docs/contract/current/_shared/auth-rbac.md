# Shared Auth Rbac

- 文档 ID：`contract-shared-auth-rbac`
- 权威状态：`canonical`
- 功能范围：`shared-auth-rbac`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：无

### 模块：管理后台认证（`/api/admin/auth`）

#### 安全与会话通用约定

- `ADMIN_JWT_SECRET` 必须显式配置；缺失、空值、纯空白、`admin_secret_change_me`、`your_admin_jwt_secret_here` 在配置读取或应用启动时均失败。阶段 A 不额外规定长度、复杂度或轮换规则，用户端 `JWT_SECRET` 不受影响。
- 新签发 Admin JWT 含整数 `token_version`；统一鉴权以数据库账号为最终事实，校验 Token 类型、签名、过期、账号存在/启用/未锁定及实时版本。历史无版本、非整数或版本不匹配 Token，以及无效账号状态均返回 HTTP 401。
- 下列事件成功后 `token_version` 精确递增一次：第五次错密锁定、自助改密、登出、超级管理员重置他人密码、他人角色实际变化。仅修改备注、提交相同角色、手动解锁不递增；解锁不恢复锁定前 Token。
- 登出按账号撤销全部会话，本阶段不实现单设备 Token 黑名单。

#### POST /api/admin/auth/login

- **所属端**：管理后台
- **Body**：`AdminLoginRequest` — username, password
- **响应**：`ApiResponse`；`data`: token, username, role, need_change_password（**接口字段未变**；`token` 内嵌 JWT 的 `sub` 实现上为字符串，见上文「统一说明」鉴权条）
- **失败响应**：不存在账号、密码错误、账号锁定、账号停用统一返回 HTTP 200，`{"code":20001,"data":null,"message":"账号或密码错误"}`；不存在账号执行固定伪 bcrypt，真实原因仅进入不含提交凭据的服务端安全日志。
- **并发与锁定**：已存在账号的登录查询使用 `SELECT ... FOR UPDATE`；锁定检查、密码校验、失败计数、第五次锁定和成功清零在同一事务完成。第 5 次错密后保持 `login_fail_count=5`、`is_locked=true`，并仅在该锁定事件递增一次 `token_version`；锁定后继续尝试不再改变状态。
- **关联表**：admin_users；admin_operation_logs（登录日志）
- **状态**：已实现

#### POST /api/admin/auth/logout

- **Body**：无
- **响应**：`ApiResponse`；需 Bearer Admin JWT；成功 **`code=0`**，`data` 可为 `null`，**`message`**「已退出登录」
- **会话语义**：成功时在同一事务递增当前账号 `token_version`，该账号全部既有 Token 随即失效；其他账号不受影响。
- **关联表**：admin_operation_logs（登出日志）
- **状态**：已实现

#### POST /api/admin/auth/change-password

- **Body**：`AdminChangePasswordRequest` — **`old_password`**、**`new_password`**、**`confirm_password`**（各 `min_length=1`，`max_length=100`）；新密码强度与 **`_validate_admin_password`** 一致（≥12 位，含大写、小写、数字、特殊字符）
- **语义**：当前登录管理员修改**本人**密码；校验旧密码通过后更新 `password_hash` 与 **`last_password_change_at`**，并记操作日志（`module=系统`，`action=edit`，描述含「修改密码」）
- **会话语义**：成功时 `token_version` 递增一次，使当前及其他设备的旧 Token 全部失效；失败分支不修改密码或版本。前端成功后清除本地会话并跳转登录页。
- **响应**：`ApiResponse`；成功 **`code=0`**，**`message`**「密码修改成功」；失败：**`20004`** `ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG`；**`20005`** `ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD`；**`20006`** `ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH`；**`20007`** `ADMIN_ERR_AUTH_PASSWORD_POLICY`（`message` 可为具体校验文案）
- **管理端**：**`admin/static/js/admin-api.js`** — **`renderHeader`** 渲染顶栏「修改密码」按钮；**`showChangePasswordModal()`** 弹窗收集三项密码，`adminRequest('POST', '/api/admin/auth/change-password', { old_password, new_password, confirm_password })`；前端先于请求校验非空及 **`new_password === confirm_password`**（不一致时 Toast「两次新密码不一致」，与后端 **20006** 语义一致）
- **状态**：已实现

---

### 模块：管理后台账号（`/api/admin`，super_admin）

- **GET** `/accounts` — 响应 `ApiResponse`；`**data` 为管理员账号的平铺数组**（**无** `total` / `page` / `page_size` / `list` 等分页包装）。单条字段：`id`, `username`, `role`, `remark`, `last_login_at`, `is_active`, `is_locked`, `created_at`（时间字段为 ISO 字符串或 `null`）。
- **POST** `/accounts` — Body：`AdminCreateAccountRequest` — `username`（1–50）、`password`（1–100，强度见下）、`role`（`super_admin`  `ops_admin`  `ai_trainer`  `tech_ops`  `observer`）、`remark`（可选，≤200）。成功 `data` 为新账号 `_admin_to_dict`。前端 `**adminRequest(..., { silentErrorToast: true })`** 后按业务码处理：`**20014`**（`ADMIN_ERR_ACCOUNT_USERNAME_EXISTS`）→ Toast「账号名已存在，请换一个」；
  - `**20007`**（`ADMIN_ERR_AUTH_PASSWORD_POLICY`）→ Toast「密码不符合复杂度要求」；其余非 0 → `message` 或「操作失败」。**密码复杂度**与后端 `_validate_admin_password` 一致，前端实时校验 5 项：≥12 位、含大写 A-Z、含小写 a-z、含数字 0-9、含特殊字符（非字母数字）。
- **PUT** `/accounts/{account_id}` — Body：`AdminUpdateAccountRequest`，**partial update**：`role`、`remark` 均为 **Optional**，**JSON 中未传或值为 `null` 的字段不修改**；`remark` 传空字符串 `""` 时表示清空备注。成功 `data` 为更新后的 `_admin_to_dict`。前端 `**silentErrorToast: true`** 时建议处理：`**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ Toast「账号不存在」；`**20016`**（`ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE`）→ Toast「不可修改自己的角色」（编辑他人账号时兜底；当前登录用户仅改自己备注时请求体应**只含 `remark`**、**不传 `role`**，避免误触 20016）。
- **角色变化会话语义**：超级管理员把他人角色实际改为不同值时，目标账号 `token_version` 递增一次；仅修改备注或提交相同角色不递增。
- **POST** `/accounts/{account_id}/reset-password` — **管理员账号**重置密码（**勿与**用户管理 `**POST /api/admin/users/{user_id}/reset-password`** 混淆）。Body 无。成功 `data`：`{ "new_password": string }`，为 **16 位**随机强密码（含大小写、数字、特殊字符，满足 `_validate_admin_password`）。失败 `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ 前端 Toast「账号不存在」（建议 `silentErrorToast: true`）。
  - **管理端 `accounts.html`**：确认弹窗后请求；成功后打开「密码重置成功」Modal 展示 `new_password`（`user-select: all` 等样式）；「复制密码」优先 `navigator.clipboard.writeText`，不支持时用临时 `textarea` + `document.execCommand('copy')`；「我已记录」关闭 Modal，**不刷新列表**。
- **重置密码会话语义**：成功时目标账号 `token_version` 递增一次，目标账号全部旧 Token 失效。
- **POST** `/accounts/{account_id}/unlock` — Body 无。若账号**不存在** → `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）。若账号**未锁定**（`is_locked=false`）→ 仍返回 `**code=0`**（`ApiResponse.ok`），`message` 为「该账号未被锁定」——**非业务错误码**；前端可统一按 `code=0` 视为成功（如 Toast「账号已解锁」后刷新列表）。若已锁定则清除锁定与登录失败计数并记操作日志 → `code=0`，`message`「账号已解锁」。建议 `**silentErrorToast: true`**，`**20015**` → Toast「账号不存在」。
- **解锁会话语义**：解锁不递增 `token_version`，也不恢复锁定前已失效的 Token。
- **DELETE** `/accounts/{account_id}` — 成功 `code=0`，`message`「删除成功」（无额外 `data` 要求）。失败：`**20015`** 账号不存在；`**20017**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF`）不可删除自己；`**20018**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER`）超级管理员账号不可删除。前端 `**silentErrorToast: true**` 时建议：`20015` →「账号不存在」、`20017` →「不可删除自己的账号」、`20018` →「超级管理员账号不可删除」。
- **关联表**：admin_users
- **状态**：已实现
- **管理端页面**：`admin/pages/accounts.html`
  - Step 1：骨架、权限初始化（`checkAdminLogin` → 非 `super_admin` 跳转 `error.html?type=403` → `currentUsername` / `loadAccountList`）；`currentUsername` 与 `accountMap` 声明在 **script 顶层**，避免放在 `DOMContentLoaded` 闭包内导致全局 `onclick` 等函数无法访问。
  - **Step 2 完成**：列表加载（`GET /api/admin/accounts`）、`account-table-wrap` 内 **3 行骨架屏**、成功渲染表格列（账号 / 角色 / 备注 / 创建时间 / 最后登录 / 状态 / 操作）、失败或响应异常时文案「加载失败，请刷新重试」、空数组「暂无账号数据」；**行数据**在渲染前 `**accountMap.clear()`** 再 `**accountMap.set(id, row)`**；操作列 `**onclick` 仅传数值 `id`**，回调内 `**accountMap.get(id)**` 取完整行，**避免** `JSON.stringify` 写入 HTML 属性时特殊字符破坏引号。
  - **Step 3 完成**：**创建账号 Modal** — `openCreateModal()` 打开 `#create-account-modal-overlay`（`modal-overlay` + `modal-content` / `modal-header` / `modal-body` / `modal-footer`），并重置字段与校验状态；表单含账号（必填 max 50）、密码（必填，**oninput** 五项复杂度 ✓/✗，全绿且账号非空、确认密码一致、已选角色后启用「确认创建」）、确认密码（不一致时红色「两次密码不一致」）、角色 select（占位「请选择角色」）、备注 textarea（选填 max 200）；提交 **POST** `/api/admin/accounts`，成功关闭 Modal、Toast「账号创建成功」、`**loadAccountList()`**。
  - **Step 4 完成**：**编辑 Modal（含自身备注）** — **入口 A**（`row.username !== currentUsername`）：操作列「编辑」→ `openEditModal(id)`，打开 `#edit-account-modal-overlay`；打开时 `**resetEditAccountModal()`** 再写入行数据；顶部灰色说明「正在编辑：{username}」（`.modal-hint`）；角色 select 与 Step 3 相同选项、预填 `row.role`、必选；备注 textarea 预填、选填、**maxlength=200**；
    - 提交 **PUT** `/api/admin/accounts/{id}`，Body `**{ role, remark }`**（`silentErrorToast: true`），`**20015`** →「账号不存在」、`**20016**` →「不可修改自己的角色」；成功关闭、Toast「账号已更新」、`**loadAccountList()**`。入口 B（自身）：「修改备注」→ `openEditRemarkModal(id)`，打开 `#edit-remark-modal-overlay`；打开时 `**resetEditRemarkOnlyModal()**` 再写入；顶部说明「仅可修改自己账号的备注」；**不渲染角色下拉**（独立 Modal，DOM 中无角色字段）；
    - 提交 Body **仅 `{ remark }`**；成功 Toast「备注已更新」并 `**loadAccountList()**`。
  - **Step 5 完成**：**重置密码** — 非自身行操作列「重置密码」→ `openResetPasswordModal(id)`（`accountMap.get(id)`）；`**showConfirm`** 文案「确认重置「{username}」的密码？系统将生成新的强密码。」（用户名需 **HTML 转义** 后插入确认层）；确认后 **POST** `/api/admin/accounts/{id}/reset-password`（`silentErrorToast: true`），`**20015`** → Toast「账号不存在」；
    - 成功则 `**showResetPasswordResultModal(data.new_password)`**，`**#reset-password-result-modal-overlay`** 标题「密码重置成功」、正文说明 + 新密码展示区（monospace 20px 等）；「复制密码」→ Clipboard API + `**execCommand('copy')**` 兜底；「我已记录」或关闭 → `**closeResetPasswordResultModal()**`，**不** `loadAccountList()`。
  - **Step 6 完成（accounts.html 全部功能）**：**解锁** — `is_locked=true` 时操作列「解锁」→ `unlockAccount(id)`；`**showConfirm`**「确认解锁「{username}」的账号？」（用户名 **escapeHtml**）；**POST** `/api/admin/accounts/{id}/unlock`（`silentErrorToast: true`）；`**code=0`** → Toast「账号已解锁」、`**loadAccountList()**`（含未锁定账号误触时后端仍 `code=0` 的约定）；`**20015**` →「账号不存在」。
    - **删除** — 非自身且非 `super_admin` 行「删除」→ `deleteAccount(id)`（自身无删除按钮、`super_admin` 行按钮 `disabled` 已在 Step 2）；`**showConfirm(..., null, { danger: true })`**（`admin-api.js` 危险样式：`modal-content--danger` + 确认钮 `btn-danger`），文案「确认删除「{username}」？此操作不可恢复。」；**DELETE** `/api/admin/accounts/{id}`（`silentErrorToast: true`）；`**20017`** / `**20018**` / `**20015**` 对应上述 Toast；
    - 成功 Toast「账号已删除」、`**loadAccountList()**`。

---

### 模块：管理后台观察者统一权限契约（`observer`）

> **权限优先级**：本节是 2026-07-17 起 observer 的权威增量契约。本文后续各历史模块/页面条目中仅列原四角色的旧记录，原四角色能力保持不变，observer 的 GET/HEAD 增量和写入/导出拒绝均以本节为准；不得因旧条目的混合 GET|PUT 表述向 observer 扩展任何写权限。

#### 五角色体系

| 角色 | 展示名 | 主要能力 |
|------|--------|----------|
| `super_admin` | 超级管理员 | 全部后台能力及账号管理 |
| `ops_admin` | 运营管理员 | 用户、统计、运营和操作日志的既有能力 |
| `ai_trainer` | AI训练师 | 人格、Prompt、记忆、Agent、关系/日记及 AI 测试的既有能力 |
| `tech_ops` | 技术运维 | 系统监控、第三方、系统/操作日志的既有能力 |
| `observer` | 观察者 | 除账号管理和系统内建导出外的已批准业务数据只读查看 |

#### 后端最终权限边界

- 所有需鉴权的 Admin 请求先校验 JWT 类型、签名、过期、`token_version`、账号存在/启用/未锁定及数据库实时角色；前端 `sessionStorage` 角色不是授权依据。
- observer 可进入各端点已明确批准的 GET/HEAD 读取集合；读取不得写 MySQL 业务数据、权限/账号状态、配置版本，不得触发生成、测试、发布、修复、回填、删除或异步任务；只允许从权威读结果派生的有限 TTL 幂等缓存回填。
- observer 的 POST/PUT/PATCH/DELETE 在统一鉴权入口默认返回 HTTP 403，业务处理器不执行；仅精确放行 `POST /api/admin/auth/logout` 和 `POST /api/admin/auth/change-password`。
- `GET /api/admin/accounts` 及账号列表、创建、编辑、重置密码、解锁、删除始终仅 `super_admin`；observer 不获得账号数据。
- 操作日志、数据报表、系统日志三个现有内建导出路由额外挂载与 HTTP 方法无关的 observer 拒绝依赖；今后新增 export/download 路由也必须显式拒绝。
- 匿名 OPTIONS 仅由 CORS 中间件处理预检，返回预检结果而非业务数据；匿名 GET/HEAD 和写请求仍须正常鉴权。

#### 已批准读取与敏感数据

- observer 可读取用户列表/详情/对话/情绪轮次/日记、统计、脱敏操作与系统日志、AI 人格/Prompt/测试配置、记忆/向量/知识/Agent/关系/日记/情绪/世界状态、系统/第三方状态及生活流现有业务读取。
- 第三方凭据仅附加布尔 `credential_configured`，用户 Open API Key 仅返回布尔 `enabled`，DashVector 仅返回配置状态；不得返回原文、首尾/prefix/suffix、掩码片段、哈希或可推断凭据的时间元数据。
- 操作日志 `target_description` / `before_value` / `after_value` 写入前脱敏，列表/详情/导出读取时再脱敏；系统日志列表/导出使用同一共享、递归、幂等、失败关闭工具。

#### 前端 35 页只读体验

- observer 菜单复用业务读取导航但不显示账号管理，Header 显示“观察者”；直访 `accounts.html` 在请求账号数据前跳转 403 错误页。
- `isObserver()` 是统一角色判断；`data-write-action` 标记写控件，`applyObserverReadOnly()` 对首屏和 MutationObserver 发现的动态节点重复应用：写按钮/链接隐藏，展示型 input/textarea 只读，select、checkbox/radio、range 和 file 控件禁用。
- `adminRequest()` 为 observer 提供非读取请求的前端体验兜底，不替代后端总闸；搜索、筛选、分页、Tab、详情、复制、日期切换、描述展开、状态/统计查看及纯 GET 刷新保持可用。
- “禁止导出”仅指系统内建导出/下载/生成报表，不承诺防截图、复制、开发者工具读取或跨分页聚合。

#### 验证和发布事实

- 后端门禁固定当前 159 个 Admin 路由（69 个 GET/HEAD、90 个写方法）、两个精确 POST 例外及三个导出；STEP-039 专项 98 通过。
- 35 页五角色浏览器验收、页面静态组合 39 通过、range 修复相关回归 13 通过；全量 pytest 917 通过 / 0 失败 / 4 跳过。
- 阶段 B 于 2026-07-16 17:02 CST 独立部署，项目所有者于 2026-07-17 确认暂无问题；STEP-040 临时 observer 验收账号已删除。

---
