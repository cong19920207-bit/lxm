# PROJECT_CONFIG_林小梦

> 用途：记录项目实况、已确认长期约束和本次需求边界；详细设计以关联 PRD 为准。  
> 更新日期：2026-07-15  
> 当前状态：管理后台观察者与安全加固 v2.2 需求细化确认完成，尚未开发和验证

---

## 基本信息

- **项目名称**：林小梦（lxm_for）
- **项目类型**：陪伴型 AI 虚拟人 H5 + 管理后台
- **技术栈**：Python 3.11 + FastAPI + SQLAlchemy（异步）+ MySQL 8 + Redis + DashVector；前端原生 HTML/CSS/JS；后台 PC 原生页

---

## 代码结构

- **代码根目录**：仓库根（后端包 `backend/`）
- **主要入口**：`backend/main.py`
- **管理后台静态文件**：`admin/pages/`、`admin/static/`

### 观察者与安全加固关键文件

| 文件路径 | 职责描述 |
|---------|---------|
| `backend/utils/admin_auth.py` | Admin JWT 签发/校验、`get_current_admin`、角色依赖、观察者总闸、操作日志写入 |
| `backend/config.py`、`backend/main.py`、`.env.example` | `ADMIN_JWT_SECRET` 配置与启动守卫 |
| `backend/routers/admin/auth.py` | 登录、登出、自助改密、失败计数和会话撤销 |
| `backend/routers/admin/accounts.py` | 管理员账号 CRUD、解锁、重置密码和角色变更 |
| `backend/models/admin_user.py` | `admin_users` 表；`role`、`is_locked`、目标字段 `token_version` |
| `backend/routers/admin/life_config_mgmt.py` | 生活流配置草稿和发布；目标增加服务端 CONFIRM |
| `backend/routers/admin/operation_logs.py` | 操作日志列表、详情和导出；目标增加读取脱敏 |
| `backend/routers/admin/stats.py` | 看板、报表和导出 |
| `backend/routers/admin/system_monitor.py` | 系统监控和日志导出 |
| `admin/static/js/admin-api.js` | 菜单、角色展示、请求封装和目标统一只读助手 |
| `admin/pages/*.html` | 后台页面；当前 35 个页面，其中 26 个含非 GET 调用，账号管理以外约 25 个需观察者只读核对 |

---

## 项目文档

- **契约文档**：`docs/contract.md`
- **需求文档**：`docs/design/PRD-管理后台观察者与安全加固-v1.md`
- **漏洞专档**：`docs/security/admin-backend-vulns-2026-07.md`
- **项目规则**：`.cursorrules`

详细权限、迁移、测试和延期风险以 PRD v2.2 与漏洞专档 2026-07-15 复核版本为准。`docs/contract.md` 和 `.cursorrules` 中仍描述现有四角色的部分，只能按阶段在代码实现并验证后同步，不能提前写成已上线。

---

## 当前项目约定

- **接口响应格式**：统一 `{"code": 0, "data": {}, "message": "success"}`（ApiResponse）。
- **字段命名风格**：snake_case，与数据库字段一致。
- **后台鉴权**：`Authorization: Bearer` Admin JWT；`type` 必须为 `admin`；除登录外的 `/api/admin/*` 接口必须鉴权。
- **当前后台角色**：`super_admin`、`ops_admin`、`ai_trainer`、`tech_ops`。
- **目标新增角色**：`observer`，展示名“观察者”；在实现和迁移完成前不能视为线上已有角色。
- **账号锁定现状和目标均保持**：连续 5 次密码错误后锁定，仅超级管理员手动解锁，不自动解除。
- **前端路径**：后台页 `/admin/pages/xxx.html`；API 相对路径 `/api/admin/...`。
- **安全边界**：后端鉴权是唯一可信权限边界，前端隐藏或禁用按钮只用于体验。
- **开发约束**：未确认的大范围方案不直接写代码；实现后必须运行可行验证并记录真实结果。

---

## 已确认的目标规则

### 观察者

- 除账号管理外可以读取后台业务数据，包括对话、记忆、日志、配置和第三方信息。
- `GET/HEAD` 在 Admin JWT、实时账号状态、Token 版本和端点角色校验通过后默认允许；CORS `OPTIONS` 是匿名基础设施预检例外，不返回业务数据。
- GET/HEAD 不得修改业务、权限、账号或配置状态；允许从权威读取结果派生的幂等、有限 TTL 缓存回填。
- 只精确放行 `POST /api/admin/auth/logout` 和 `POST /api/admin/auth/change-password`。
- 账号管理菜单隐藏；直接打开账号静态页时由前端立即拦截/跳转，账号数据 API 由后端拒绝。
- 当前操作日志、数据报表、系统日志 3 个导出接口分别增加与 HTTP 方法无关的观察者拒绝依赖；未来导出/下载接口沿用该规则。
- “禁止导出”不等于阻止截图、复制或分页聚合。
- 前端对账号管理以外约 25 个含写入口业务页面做一次性只读改造：公共只读助手＋统一写操作标记＋`adminRequest` 非 GET 兜底；以后新增写控件遵守同一规范。
- 写按钮隐藏，展示型文本字段只读，选择框/开关/文件控件禁用；搜索、筛选、分页、Tab、详情、复制和纯 GET 刷新保留。
- 第三方凭据及用户 Open API Key 对观察者只显示“已配置/未配置”，不显示首尾字符。
- 角色实现按现有校验、菜单、标签结构最小扩展，本期不重构统一角色注册中心。

### JWT 与会话

- `ADMIN_JWT_SECRET` 不得有代码默认回退；缺失、空值、纯空白、`admin_secret_change_me`、`your_admin_jwt_secret_here` 拒绝启动；配置读取与 lifespan 显式启动检查复用同一校验函数。
- 当前自定义密钥本期不强制轮换；测试和 CI 必须显式配置独立密钥。
- `admin_users` 目标新增 `token_version INTEGER NOT NULL DEFAULT 0`。
- 锁定、修改自己密码、管理员重置密码、登出、实际角色变更时递增版本；仅修改备注或提交相同角色不递增。
- 解锁不恢复旧 Token；历史无版本 Token 拒绝；首次上线后所有管理员重新登录。
- 本期不新增管理员停用/重新启用功能；紧急直接数据库停用必须同时人工递增 `token_version` 并留审计记录。
- 本期登出是账号级全会话撤销，不实现单设备 Token 黑名单。

### 登录

- 同一管理员的登录检查和失败计数使用 `SELECT ... FOR UPDATE`，在单事务内处理。
- 不存在账号、密码错误、锁定、停用统一返回 HTTP 200、业务码 `20001`、`data: null` 和“账号或密码错误”，不返回剩余尝试次数。
- 不存在账号执行伪密码哈希校验；真实原因只写服务端脱敏安全日志。
- 5 次失败锁定规则保持线上现状；IP＋账号限流本期不做。

### 日志和发布确认

- 使用一个共享、无状态、幂等的递归工具把凭据替换为 `[REDACTED]`；操作日志写入及列表/详情/导出、系统日志列表/导出统一调用；字符串优先解析 JSON，非 JSON 只匹配已知凭据赋值和 Authorization/Bearer 形式；本期不批量改写历史数据库行。
- 脱敏针对 API Key、Secret、Token、Password、Authorization、Pepper、Private Key 等凭据字段，不误伤 Prompt、对话、记忆和 `max_tokens`。
- `POST /life-config/publish` 目标增加服务端 `confirm_text == "CONFIRM"` 校验；字段缺失、空值或错误返回业务码 `20021`；当前 7 个前端发布入口显式传值；CONFIRM 仅防误操作，不是认证。
- 本期不改变 life-config 草稿、当前生效版本、历史版本和回滚逻辑。

### 页面归属确认

- `admin/pages/memory-rules.html`：Step6 记忆 Prompt、全局记忆和 DashVector 配置，不是 Embedding 配置页。
- `admin/pages/third-party.html`：第三方服务及 Embedding 配置页。
- `admin/pages/vector-token-config.html`：向量召回与 Prompt Token 数值配置，不含第三方凭据。

---

## 明确延期与剩余风险

| 编号/主题 | 状态 | 影响范围 |
|-----------|------|----------|
| VULN-001 发布测试可信状态 | 本期延期、高危已知未修 | 可发布角色仍可能伪造 `test_passed`；后续需草稿/测试/发布状态机和服务端测试凭证 |
| VULN-007 90 天强制改密 | 本期延期 | 仅前端提醒，服务端不强制拦截 |
| VULN-008 恶意锁号 | 接受剩余风险 | 已知账号仍可能被连续 5 次错密锁定；限流后续处理 |
| 数据库与 Redis 发布一致性 | 本期延期 | 发布异常时可能短暂不一致 |
| 历史操作日志明文 | 接受边界 | 后台读取会遮蔽，数据库直接查询仍可能看到旧值 |
| 观察者数据外带 | 不在本期能力范围 | 禁止内建导出，但无法阻止截图、复制或分页聚合 |
| 前端角色缓存 | 接受边界 | 可能短暂显示不准确，后端实时鉴权保证不越权 |

---

## 本次交付顺序

**阶段 A：安全加固**  
完成 JWT 密钥守卫、`token_version`、登录行锁与统一响应、life-config 服务端 CONFIRM、共享日志脱敏，以及 pytest、真实 MySQL 8 并发测试和四角色回归；人工确认后独立部署，运行稳定后才进入阶段 B。

**阶段 B：观察者**  
新增 `observer`、集中式后端总闸、读取角色、内建导出拒绝和前端全量只读控制；35 个页面全部盘点，所有权限变动页面按 5 角色权限矩阵逐页验证直接访问、数据加载、读取交互、静态/动态写控件及原有合法写操作，确认观察者只读且原有 4 个角色未受误伤后独立部署。

本期不新增 CI/CD 或 Playwright 基础设施。测试报告必须记录真实命令、通过/失败数量、失败原因和人工验收结果。只有各阶段实际实现并验证通过后，才能同步该阶段的 `docs/contract.md`、`.cursorrules` 及文档状态。
