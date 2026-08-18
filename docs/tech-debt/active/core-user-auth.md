# core-user-auth 技术债

- 文档 ID：`tech-debt-core-user-auth`
- 权威状态：`canonical`
- 功能范围：`core-user-auth`
- 必读依赖：无
- 相关技术债：`TD-001`, `TD-024`, `TD-025`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-001] users 表遗留字段待清理

- 字段：users.relationship_level、users.growth_value
- 问题：注册写入默认值 0 后不再更新，真实数据在 relationship 表
- 当前处理：Admin 查询已改读 relationship 表；users 字段保留，注册路径不动
- 待处理：
  1. 确认全量无读路径后，从 User Model 删除这两个字段
  2. 出 Alembic migration 删列（含 downgrade）
  3. 清理注册路径中的 relationship_level=0 / growth_value=0 赋值
- 触发时机：H5 客户端有用户资料相关改动时一并处理
- 风险等级：低

### [TD-024] H5 设置页用户偏好开关后端未实现（**部分清偿**）

- **部分清偿说明（2026-05-31，C-07）**：`settings.html`「记忆自动提取」Toggle 已**移除**，改为只读说明行「记忆整理 / 对话结束后会自动整理成记忆，无需手动设置」，并删除前端对 `memory_auto_extract` 的读取与 PUT；记忆由 Step6 自动整理，`memory_auto_extract` 偏好缺口**不复存在**。**残留**：`agent_message_enabled`（主动消息推送）Toggle 仍在线、后端 `GET/PUT /api/user/settings` 仍未实现/未读取，本项**未全量清偿**。
- **位置**：`frontend/pages/settings.html` → `GET/PUT /api/user/settings`（~~`memory_auto_extract`~~ 已移除、`agent_message_enabled` 仍待）
- **问题**：前端 Toggle 已接线并默认 `active`；后端 **`routers/user.py` 未挂载**、无持久化字段；保存时接口不存在或失败 Toast；即使补接口，记忆提取链路与 Agent 扫描**当前也未读取**这两项开关。
- **待处理**：
  1. 在 `users` 表或独立用户设置表增加字段并迁移；
  2. 实现 `GET/PUT /api/user/settings` 并在 `main.py` 挂载 `user` 路由；
  3. 记忆提取（Step6 / 后置任务）与 Agent 触发链路读取开关并写契约。
- **触发时机**：产品要求设置页「记忆自动提取」「主动消息推送」真实生效时排期。
- **风险等级**：**中**（UI 可交互但偏好不持久、不生效，易误导用户）
- **关联**：`docs/contract.md`「H5 用户（占位）」；`frontend/pages/settings.html`。

### [TD-025] H5 改密码前后端契约不一致（**待清偿**）

- **位置**：`frontend/pages/settings.html` → `POST /api/auth/reset-password`；`backend/routers/auth.py`、`backend/schemas/auth.py`
- **问题**：前端传 `old_password` 且不传 `confirm_password`；后端 **`ResetPasswordRequest` 要求 `confirm_password`**、**不校验原密码**（按用户名存在即可重置），存在安全缺口与字段不匹配；422 或静默忽略原密码校验。
- **待处理**：
  1. 新增需登录的 `POST /api/auth/change-password`（校验旧密码 + 新密码确认），或；
  2. 对齐 `reset-password` 的 Body 与校验逻辑（含原密码验证），并更新 H5 请求体。
- **触发时机**：安全审查或改密码功能正式验收时。
- **风险等级**：**中**（已知安全与契约偏差）
- **关联**：`backend/schemas/auth.py` `ResetPasswordRequest`；管理端改密见 `POST /api/admin/auth/change-password`（已实现完整校验，可作参考）。
