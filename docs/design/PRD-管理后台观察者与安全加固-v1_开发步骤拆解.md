# PRD-管理后台观察者与安全加固-v1 开发步骤拆解

> PRD：`docs/design/PRD-管理后台观察者与安全加固-v1.md`（v2.2）  
> 项目配置：`docs/design/PROJECT_CONFIG_林小梦.md`  
> 漏洞专档：`docs/security/admin-backend-vulns-2026-07.md`  
> 进度追踪：`docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`  
> 拆解日期：2026-07-15  
> 代码核对基线：当前工作区（35 个后台页面；26 个含非 GET 调用页面，其中账号页 1 个、业务页 25 个；7 处 life-config 发布调用；3 个内建导出接口）

## 0. 严格边界与执行门禁

- 阶段 A 必须独立开发、测试、人工确认和部署，运行稳定后才允许执行 STEP-018 及以后阶段 B 环节。
- 本期不实施：VULN-001 发布测试状态机、VULN-007 后端强制改密、IP＋账号限流、数据库与 Redis 发布一致性重构、管理员停用/启用、单设备 Token 黑名单、历史日志批量改写、统一角色注册中心、CI/CD、Playwright。
- “禁止导出”仅指系统内建导出/下载，不承诺阻止截图、复制、开发者工具读取或分页聚合。
- 每阶段只有在实现与真实验证完成后，才同步该阶段的 `docs/contract.md`、`.cursorrules`、漏洞状态和 PRD 状态。
- 不得把 40 个 STEP 串成一次开发指令；后续须按 `milestone-step-execution` 组织 M1/M2/M3，并一次只执行一个 STEP。

## 1. 功能清单

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F-001 | ADMIN_JWT_SECRET 统一校验与启动双守卫 | [核心] | 无 |
| F-002 | token_version 数据库字段与迁移 | [核心] | 无 |
| F-003 | Admin JWT 携带并校验 token_version | [核心] | STEP-002 |
| F-004 | 登录行锁事务与第五次锁定撤销 | [核心] | STEP-002 |
| F-005 | 登录失败统一响应、伪哈希与安全日志 | [核心] | STEP-004 |
| F-006 | 自助改密撤销全部旧会话 | [核心] | STEP-003 |
| F-007 | 登出执行账号级全会话撤销 | [核心] | STEP-003 |
| F-008 | 账号安全操作的版本递增矩阵 | [核心] | STEP-002 |
| F-009 | life-config 发布服务端 CONFIRM 校验 | [核心] | 无 |
| F-010 | 7 个 life-config 前端发布入口传递 CONFIRM | [核心] | STEP-009 |
| F-011 | 共享递归凭据脱敏工具 | [核心] | 无 |
| F-012 | 操作日志写入、列表、详情与导出双层脱敏 | [核心] | STEP-011 |
| F-013 | 系统日志列表与导出统一脱敏 | [核心] | STEP-011 |
| F-014 | 阶段 A 自动化安全回归 | [核心] | STEP-001~STEP-013 |
| F-015 | 真实 MySQL 8 并发登录验证 | [核心] | STEP-004,STEP-005 |
| F-016 | 阶段 A 四角色回归与真实验证记录 | [核心] | STEP-014,STEP-015 |
| F-017 | 阶段 A 契约同步、独立部署与人工门禁 | [核心] | STEP-016 |
| F-018 | observer 角色与账号管理最小扩展 | [核心] | STEP-017 |
| F-019 | 观察者后端方法级集中总闸 | [核心] | STEP-018 |
| F-020 | CORS OPTIONS 匿名预检边界 | [核心] | STEP-019 |
| F-021 | 3 个内建导出接口显式拒绝观察者 | [核心] | STEP-019 |
| F-022 | 用户、统计与日志读取角色拆分 | [核心] | STEP-019,STEP-012 |
| F-023 | AI 配置与测试模块读取角色拆分 | [核心] | STEP-019 |
| F-024 | 记忆、向量、知识、Agent、关系与情绪读取角色拆分 | [核心] | STEP-019 |
| F-025 | 系统监控、系统日志与第三方状态读取角色拆分 | [核心] | STEP-019,STEP-013 |
| F-026 | 生活流全模块读取角色拆分 | [核心] | STEP-019 |
| F-027 | 第三方凭据与用户 Open API Key 状态化展示 | [核心] | STEP-022,STEP-025 |
| F-028 | 全量 Admin 路由鉴权与 GET/HEAD 副作用审计 | [核心] | STEP-019~STEP-027 |
| F-029 | 前端 observer 公共菜单、Header、只读助手与请求兜底 | [核心] | STEP-018,STEP-019 |
| F-030 | 观察者账号管理页直访拦截 | [核心] | STEP-029 |
| F-031 | 用户、报表与日志页面观察者只读改造 | [核心] | STEP-022,STEP-021,STEP-027,STEP-029 |
| F-032 | 系统监控、第三方、AI 测试与看板页面只读改造 | [核心] | STEP-023,STEP-025,STEP-027,STEP-029 |
| F-033 | 人格、Prompt、安全规则与对话流 Prompt 页面只读改造 | [核心] | STEP-023,STEP-029 |
| F-034 | 记忆、向量与知识页面只读改造 | [核心] | STEP-024,STEP-027,STEP-029 |
| F-035 | Agent、关系、日记规则与日记历史页面只读改造 | [核心] | STEP-024,STEP-029 |
| F-036 | 生活计划与世界观页面只读改造 | [核心] | STEP-026,STEP-029 |
| F-037 | 朋友圈内容、评论与感知页面只读改造 | [核心] | STEP-026,STEP-029 |
| F-038 | 生活流人格拓展、Prompt 与系统参数页面只读改造 | [核心] | STEP-026,STEP-029 |
| F-039 | 阶段 B 后端权限与敏感读取自动化门禁 | [核心] | STEP-018~STEP-028 |
| F-040 | 35 页面五角色验收、文档同步与阶段 B 独立部署 | [核心] | STEP-030~STEP-039 |

### 1.1 需求追踪矩阵

| 需求来源 | 对应 STEP | 覆盖说明 |
|---------|-----------|---------|
| C1 | STEP-017、STEP-040 | A/B 独立开发、确认与部署 |
| C2 | STEP-018、STEP-029 | `observer` 与“观察者” |
| C3 | STEP-006、STEP-019、STEP-029 | 自助改密、旧会话失效、前端重登 |
| C4 | STEP-018、STEP-030 | 账号菜单、直访、API 403、仅 super_admin 管理 |
| C5 | STEP-022～027、STEP-031～038 | 除账号管理外的业务数据读取 |
| C6 | STEP-021、STEP-040 | 仅禁止系统内建导出，不承诺防数据外带 |
| C7 | STEP-019～021 | 后端总闸、两个精确例外、导出拒绝、OPTIONS |
| C8 | STEP-029、STEP-031～038 | 公共只读助手、统一标记、请求兜底、全页面改造 |
| C9 | STEP-001 | JWT 密钥双守卫与不强制轮换边界 |
| C10 | STEP-002～008 | token_version、历史 Token、递增矩阵、全员重登 |
| C11 | STEP-007 | 登出为账号级全会话撤销 |
| C12 | STEP-004、STEP-015 | 行锁事务与真实 MySQL 8 并发验证 |
| C13 | STEP-005 | 统一失败响应、无剩余次数、伪哈希 |
| C14 | STEP-011～013 | 共享无状态幂等脱敏、写读双层保护 |
| C15 | STEP-009、STEP-010 | life-config 后端 20021 与 7 个前端入口 |
| C16 | STEP-016、STEP-040 | VULN-001 保持延期，不实施状态机或迁移 |
| C17 | STEP-017、STEP-040 | 发布一致性保持延期，不误写为已修 |
| C18 | STEP-006、STEP-016、STEP-040 | 仅保留前端 90 天提醒，不加后端门禁 |
| C19 | STEP-005、STEP-016、STEP-040 | 不做限流，保留恶意锁号风险 |
| C20 | STEP-008、STEP-018 | 不新增管理员停用/启用接口与 UI |
| C21 | STEP-028、STEP-039 | GET/HEAD 副作用审计与缓存回填边界 |
| C22 | STEP-021 | 三个现有导出接口逐一拒绝 observer |
| C23 | STEP-027、STEP-032、STEP-034 | Step6、Embedding、召回/Token 页面归属 |
| C24 | STEP-012、STEP-013、STEP-027 | 凭据状态化与系统/操作日志脱敏 |
| C25 | STEP-018、STEP-029 | 现有分散结构最小扩展，不建角色注册中心 |
| C26 | STEP-014～017、STEP-039、STEP-040 | pytest、MySQL、契约测试、人工验收、分阶段文档与部署 |
| A1 | STEP-001 | JWT 密钥启动守卫 |
| A2 | STEP-002、STEP-003、STEP-006～008 | Token 版本与会话撤销 |
| A3 | STEP-004、STEP-005、STEP-015 | 登录事务、统一失败与并发验证 |
| A4 | STEP-009、STEP-010 | life-config 服务端 CONFIRM |
| A5 | STEP-011～013 | 操作日志与系统日志凭据脱敏 |
| A6 | STEP-014～017 | 阶段 A 测试、回归、文档、部署门禁 |
| B1 | STEP-018、STEP-030 | 角色、账号和账号页禁入 |
| B2 | STEP-019～021、STEP-028、STEP-039 | 集中总闸、导出、OPTIONS 与路由审计 |
| B3 | STEP-022～027 | 业务读取角色与敏感读取 |
| B4 | STEP-029～038 | 公共助手与后台全页面只读改造 |
| B5 | STEP-017、STEP-040 | 契约与两阶段独立交付 |
| VULN-002 | STEP-001、STEP-014 | 默认密钥删除、双守卫与测试 |
| VULN-003 | STEP-002～004、STEP-006、STEP-008、STEP-014 | 锁定与版本撤销 |
| VULN-004 | STEP-004、STEP-015 | 登录计数竞态修复与 MySQL 验证 |
| VULN-005 | STEP-009、STEP-010、STEP-014 | CONFIRM 前后端与回归 |
| VULN-006 | STEP-007、STEP-014 | 登出撤销 |
| VULN-008 响应统一部分 | STEP-005、STEP-014 | 枚举收敛；恶意锁号风险保留 |
| VULN-009 | STEP-011～014 | 共享脱敏、操作日志、系统日志与测试 |
| VULN-001、VULN-007 | STEP-016、STEP-040 | 显式保持延期/未修，不产生实施任务 |

## 2. 开发环节总览

### 2.1 阶段 A：安全加固

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-001 | ADMIN_JWT_SECRET 统一校验与启动双守卫 | `backend/config.py`、`backend/main.py`、`.env.example`、`tests/` | 无 | 低 |
| STEP-002 | token_version 数据库字段与迁移 | `backend/models/admin_user.py`、`alembic/versions/`、`scripts/schema_ddl.sql`、`tests/` | 无 | 中 |
| STEP-003 | Admin JWT 携带并校验 token_version | `backend/utils/admin_auth.py`、`backend/models/admin_user.py`、`tests/test_admin_auth.py` | STEP-002 | 中 |
| STEP-004 | 登录行锁事务与第五次锁定撤销 | `backend/routers/admin/auth.py`、`backend/models/admin_user.py`、`tests/` | STEP-002 | 高 |
| STEP-005 | 登录失败统一响应、伪哈希与安全日志 | `backend/routers/admin/auth.py`、`backend/constants/__init__.py`、`backend/utils/`、`tests/test_admin_auth.py` | STEP-004 | 中 |
| STEP-006 | 自助改密撤销全部旧会话 | `backend/routers/admin/auth.py`、`admin/static/js/admin-api.js`、`tests/test_admin_auth.py` | STEP-003 | 中 |
| STEP-007 | 登出执行账号级全会话撤销 | `backend/routers/admin/auth.py`、`admin/static/js/admin-api.js`、`tests/test_admin_auth.py` | STEP-003 | 低 |
| STEP-008 | 账号安全操作的版本递增矩阵 | `backend/routers/admin/accounts.py`、`backend/schemas/admin_auth.py`、`backend/models/admin_user.py`、`tests/test_admin_auth.py` | STEP-002 | 中 |
| STEP-009 | life-config 发布服务端 CONFIRM 校验 | `backend/routers/admin/life_config_mgmt.py`、`backend/constants/__init__.py`、`tests/` | 无 | 低 |
| STEP-010 | 7 个 life-config 前端发布入口传递 CONFIRM | `admin/pages/life-feed-global.html`、`admin/pages/life-feed-prompts.html`、`admin/pages/life-feed-system.html`、`admin/pages/life-plan.html`、`tests/` | STEP-009 | 中 |
| STEP-011 | 共享递归凭据脱敏工具 | `backend/utils/`、`tests/` | 无 | 高 |
| STEP-012 | 操作日志写入、列表、详情与导出双层脱敏 | `backend/utils/admin_auth.py`、`backend/routers/admin/operation_logs.py`、`tests/` | STEP-011 | 中 |
| STEP-013 | 系统日志列表与导出统一脱敏 | `backend/routers/admin/system_monitor.py`、`backend/utils/`、`tests/test_system_monitor_logs.py` | STEP-011 | 中 |
| STEP-014 | 阶段 A 自动化安全回归 | `tests/`、`backend/`、`admin/` | STEP-001~STEP-013 | 高 |
| STEP-015 | 真实 MySQL 8 并发登录验证 | `tests/`、`docs/testing/`、`docs/progress/` | STEP-004,STEP-005 | 高 |
| STEP-016 | 阶段 A 四角色回归与真实验证记录 | `tests/`、`docs/security/admin-backend-vulns-2026-07.md`、`docs/progress/` | STEP-014,STEP-015 | 高 |
| STEP-017 | 阶段 A 契约同步、独立部署与人工门禁 | `docs/contract.md`、`.cursorrules`、`docs/security/admin-backend-vulns-2026-07.md`、`docs/progress/` | STEP-016 | 高 |

### 2.2 阶段 B：观察者（仅阶段 A 独立部署并稳定后执行）

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-018 | observer 角色与账号管理最小扩展 | `backend/schemas/admin_auth.py`、`backend/models/admin_user.py`、`backend/routers/admin/accounts.py`、`admin/pages/accounts.html`、`admin/static/js/admin-api.js` | STEP-017 | 中 |
| STEP-019 | 观察者后端方法级集中总闸 | `backend/utils/admin_auth.py`、`backend/routers/admin/auth.py`、`tests/` | STEP-018 | 高 |
| STEP-020 | CORS OPTIONS 匿名预检边界 | `backend/main.py`、`backend/utils/admin_auth.py`、`tests/` | STEP-019 | 中 |
| STEP-021 | 3 个内建导出接口显式拒绝观察者 | `backend/routers/admin/operation_logs.py`、`backend/routers/admin/stats.py`、`backend/routers/admin/system_monitor.py`、`backend/utils/admin_auth.py` | STEP-019 | 中 |
| STEP-022 | 用户、统计与日志读取角色拆分 | `backend/routers/admin/users.py`、`backend/routers/admin/stats.py`、`backend/routers/admin/operation_logs.py` | STEP-019,STEP-012 | 高 |
| STEP-023 | AI 配置与测试模块读取角色拆分 | `backend/routers/admin/persona.py`、`backend/routers/admin/prompt_mgmt.py`、`backend/routers/admin/chat_prompt_view.py`、`backend/routers/admin/test_cases.py`、`backend/routers/admin/safety_rules.py` | STEP-019 | 高 |
| STEP-024 | 记忆、向量、知识、Agent、关系与情绪读取角色拆分 | `backend/routers/admin/memory_mgmt.py`、`backend/routers/admin/vector_config.py`、`backend/routers/admin/knowledge_mgmt.py`、`backend/routers/admin/agent_mgmt.py`、`backend/routers/admin/relationship_mgmt.py`、`backend/routers/admin/emotion_config.py`、`backend/routers/admin/world_state_mgmt.py` | STEP-019 | 高 |
| STEP-025 | 系统监控、系统日志与第三方状态读取角色拆分 | `backend/routers/admin/system_monitor.py` | STEP-019,STEP-013 | 中 |
| STEP-026 | 生活流全模块读取角色拆分 | `backend/routers/admin/life_config_mgmt.py`、`backend/routers/admin/life_plan_mgmt.py`、`backend/routers/admin/feed_mgmt.py`、`backend/routers/admin/feed_comment_mgmt.py`、`backend/routers/admin/agent_aware_mgmt.py`、`backend/routers/admin/worldview_mgmt.py` | STEP-019 | 高 |
| STEP-027 | 第三方凭据与用户 Open API Key 状态化展示 | `backend/routers/admin/system_monitor.py`、`backend/routers/admin/users.py`、`admin/pages/third-party.html`、`admin/pages/user-detail.html`、`tests/` | STEP-022,STEP-025 | 高 |
| STEP-028 | 全量 Admin 路由鉴权与 GET/HEAD 副作用审计 | `backend/main.py`、`backend/routers/admin/*.py`、`tests/` | STEP-019~STEP-027 | 高 |
| STEP-029 | 前端 observer 公共菜单、Header、只读助手与请求兜底 | `admin/static/js/admin-api.js`、`admin/static/css/admin-common.css`、`tests/` | STEP-018,STEP-019 | 高 |
| STEP-030 | 观察者账号管理页直访拦截 | `admin/pages/accounts.html`、`admin/static/js/admin-api.js`、`backend/routers/admin/accounts.py`、`tests/` | STEP-029 | 中 |
| STEP-031 | 用户、报表与日志页面观察者只读改造 | `admin/pages/users.html`、`admin/pages/user-detail.html`、`admin/pages/data-report.html`、`admin/pages/operation-logs.html`、`admin/pages/system-logs.html` | STEP-022,STEP-021,STEP-027,STEP-029 | 高 |
| STEP-032 | 系统监控、第三方、AI 测试与看板页面只读改造 | `admin/pages/system-monitor.html`、`admin/pages/third-party.html`、`admin/pages/test-tool.html`、`admin/pages/dashboard.html` | STEP-023,STEP-025,STEP-027,STEP-029 | 高 |
| STEP-033 | 人格、Prompt、安全规则与对话流 Prompt 页面只读改造 | `admin/pages/persona.html`、`admin/pages/prompt.html`、`admin/pages/step5-5-switch.html`、`admin/pages/safety-rules.html`、`admin/pages/chat-prompt-step15.html`、`admin/pages/chat-prompt-step3.html`、`admin/pages/chat-prompt-step8.html`、`admin/pages/chat-prompt-agent.html` | STEP-023,STEP-029 | 高 |
| STEP-034 | 记忆、向量与知识页面只读改造 | `admin/pages/memory-rules.html`、`admin/pages/vector-token-config.html`、`admin/pages/knowledge.html` | STEP-024,STEP-027,STEP-029 | 高 |
| STEP-035 | Agent、关系、日记规则与日记历史页面只读改造 | `admin/pages/agent-rules.html`、`admin/pages/relationship-rules.html`、`admin/pages/diary-rules.html`、`admin/pages/diary-history.html` | STEP-024,STEP-029 | 高 |
| STEP-036 | 生活计划与世界观页面只读改造 | `admin/pages/life-plan.html`、`admin/pages/worldview.html` | STEP-026,STEP-029 | 高 |
| STEP-037 | 朋友圈内容、评论与感知页面只读改造 | `admin/pages/feed-posts.html`、`admin/pages/feed-comments.html`、`admin/pages/agent-aware.html` | STEP-026,STEP-029 | 高 |
| STEP-038 | 生活流人格拓展、Prompt 与系统参数页面只读改造 | `admin/pages/life-feed-global.html`、`admin/pages/life-feed-prompts.html`、`admin/pages/life-feed-system.html` | STEP-026,STEP-029 | 高 |
| STEP-039 | 阶段 B 后端权限与敏感读取自动化门禁 | `tests/`、`backend/routers/admin/`、`backend/utils/admin_auth.py` | STEP-018~STEP-028 | 高 |
| STEP-040 | 35 页面五角色验收、文档同步与阶段 B 独立部署 | `admin/pages/*.html`（含 `login.html`、`error.html`）、`tests/`、`docs/contract.md`、`.cursorrules`、`docs/security/admin-backend-vulns-2026-07.md`、`docs/progress/` | STEP-030~STEP-039 | 高 |

## 3. 开发提示词

### [STEP-001] ADMIN_JWT_SECRET 统一校验与启动双守卫

**目标**：删除后台 JWT 公开默认回退，并让配置读取与 lifespan 复用同一校验函数。

---

**前置条件检查**：

> 无前置条件。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/config.py` — 本环节实际代码或验证位置
- `@backend/main.py` — 本环节实际代码或验证位置
- `@.env.example` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> `ADMIN_JWT_SECRET` 不再使用代码默认回退；缺失、空值、纯空白、`admin_secret_change_me`、`your_admin_jwt_secret_here` 均导致启动失败；当前自定义密钥不强制轮换。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `ADMIN_JWT_SECRET` | String | 后台 JWT 签名密钥 | 需求文档原文 |

---

**开发任务**：
1. 在 `backend/config.py` 实现唯一校验函数并由 `get_admin_jwt_secret()` 复用。
2. 在 lifespan 显式调用同一函数实现启动快速失败。
3. 保留 `.env.example` 示例用途，但确保示例值不可运行；测试显式设置独立密钥。

**不在本环节范围内**：
- 不增加最短长度、复杂度或强制轮换规则。
- 不修改用户端 `JWT_SECRET`。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 有效自定义密钥可读取且应用可启动 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 缺失/空值/纯空白/两个公开值均拒绝 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 配置读取与 lifespan 使用同一规则，无双份判断 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-001** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-001 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-002 token_version 数据库字段与迁移**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-002] token_version 数据库字段与迁移

**目标**：为 `admin_users` 增加非空、默认 0 的会话版本字段并兼容现有行。

---

**前置条件检查**：

> 无前置条件。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/models/admin_user.py` — 本环节实际代码或验证位置
- `@alembic/versions/` — 本环节实际代码或验证位置
- `@scripts/schema_ddl.sql` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 本期仅一项必需迁移：`admin_users.token_version INTEGER NOT NULL DEFAULT 0`；现有行回填为 0。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `token_version` | Integer | 管理员会话版本，NOT NULL DEFAULT 0 | 需求文档原文 |

---

**开发任务**：
1. 更新 ORM 模型及角色注释所需的现状说明。
2. 新增符合仓库 Alembic 链路的迁移，现有行回填 0。
3. 同步仓库建库 DDL 中 `admin_users` 字段并增加迁移测试。

**不在本环节范围内**：
- 不为 `observer` 角色新增数据库迁移。
- 不新增测试凭证、草稿版本或发布状态表。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 新库字段默认值为 0 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 已有行升级后值为 0 且非空 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 迁移重复/回滚边界按现有 Alembic 规范验证 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-002** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-002 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-003 Admin JWT 携带并校验 token_version**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-003] Admin JWT 携带并校验 token_version

**目标**：让新 Token 携带版本，并在统一鉴权时校验账号状态、锁定状态与数据库实时版本。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-002 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置
- `@backend/models/admin_user.py` — 本环节实际代码或验证位置
- `@tests/test_admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 新签发的 Admin JWT 必须携带版本；`get_current_admin` 同时校验 Token 类型、签名和过期时间、账号存在且 `is_active=True`、账号未锁定、Token 版本等于数据库当前版本；历史无版本 Token 拒绝。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `token_version` | Integer | Admin JWT 与数据库实时版本 | 需求文档原文 |

---

**开发任务**：
1. 扩展 `create_admin_token` 的 payload 和调用方。
2. 在 `get_current_admin` 校验 `is_active`、`is_locked` 与版本一致性。
3. 历史无版本、类型错误、版本错误统一按未授权处理。

**不在本环节范围内**：
- 不实现 JWT 黑名单或单设备撤销。
- 不依赖 Token 中旧角色作为最终授权依据。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 新 Token 版本匹配可鉴权 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 历史无版本或版本不匹配返回 401 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 锁定/停用/账号不存在均不能通过 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-003** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-003 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-004 登录行锁事务与第五次锁定撤销**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-004] 登录行锁事务与第五次锁定撤销

**目标**：用 MySQL 行锁保证同账号失败计数、第五次锁定和版本递增原子完成。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-002 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/auth.py` — 本环节实际代码或验证位置
- `@backend/models/admin_user.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 查询管理员账号后使用 `SELECT ... FOR UPDATE` 锁定目标行；在同一事务内完成锁定状态检查、密码校验、失败计数、第五次锁定、版本递增和成功登录后的计数清零。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `login_fail_count` | Integer | 连续失败计数 | 需求文档原文 |
| `is_locked` | Boolean | 第五次失败后锁定 | 需求文档原文 |
| `token_version` | Integer | 锁定时递增 | 需求文档原文 |

---

**开发任务**：
1. 将存在账号的登录查询改为 `SELECT ... FOR UPDATE`。
2. 在单事务内处理锁定、校验、计数、第五次锁定和成功清零。
3. 锁定时递增 `token_version`；锁定后计数保持 5，不再递增。

**不在本环节范围内**：
- 不自动解锁。
- SQLite 不替代 MySQL 8 行锁并发验证。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 正确密码成功并清零失败计数 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 串行第五次错误锁定并递增版本 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 锁定后再次请求计数保持 5 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-004** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-004 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-005 登录失败统一响应、伪哈希与安全日志**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-005] 登录失败统一响应、伪哈希与安全日志

**目标**：统一所有登录失败的外部响应，并隐藏账号存在性和剩余次数。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-004 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/auth.py` — 本环节实际代码或验证位置
- `@backend/constants/__init__.py` — 本环节实际代码或验证位置
- `@backend/utils/` — 本环节实际代码或验证位置
- `@tests/test_admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 不存在账号、密码错误、锁定、停用统一返回 HTTP 200、业务码 `20001`、`data: null` 和“账号或密码错误”；不存在账号时执行伪密码哈希校验；真实失败原因只进入服务端安全日志，并遵守脱敏规则。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `code` | Integer | 20001 | 需求文档原文 |
| `data` | null | 登录失败数据 | 需求文档原文 |
| `message` | String | 账号或密码错误 | 需求文档原文 |

---

**开发任务**：
1. 收敛四类失败为完全一致的 HTTP 200 与 ApiResponse。
2. 删除剩余次数和锁定状态的对外暴露。
3. 为不存在账号执行伪 bcrypt 校验，真实原因仅写脱敏安全日志。

**不在本环节范围内**：
- 不实现 IP＋账号限流。
- 不改变连续 5 次锁定规则。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 不存在/错密/锁定/停用响应体完全一致 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 响应不含剩余次数或真实状态 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 服务端仍可区分真实原因且日志无凭据 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-005** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-005 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-006 自助改密撤销全部旧会话**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-006] 自助改密撤销全部旧会话

**目标**：改密成功时递增版本，并让前端清除 Token 后返回登录页。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-003 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/auth.py` — 本环节实际代码或验证位置
- `@admin/static/js/admin-api.js` — 本环节实际代码或验证位置
- `@tests/test_admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 用户修改自己的密码：`token_version` 递增，当前及其他设备重新登录；观察者允许修改自己的密码。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `token_version` | Integer | 改密成功后递增 | 需求文档原文 |

---

**开发任务**：
1. 密码校验全部通过后更新密码与时间并递增版本。
2. 保持现有密码强度与错误码。
3. 确认公共改密 UI 成功后清除本地 Token 并跳转登录页。

**不在本环节范围内**：
- 不增加 90 天后端强制改密门禁。
- 不授予观察者任何业务写权限。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 改密成功后当前与其他设备旧 Token 均 401 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 改密失败不递增版本 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 重新登录获得新版本 Token |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-006** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-006 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-007 登出执行账号级全会话撤销**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-007] 登出执行账号级全会话撤销

**目标**：登出时递增版本，使同账号所有设备旧会话失效。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-003 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/auth.py` — 本环节实际代码或验证位置
- `@admin/static/js/admin-api.js` — 本环节实际代码或验证位置
- `@tests/test_admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 登出递增版本，使同账号所有设备旧会话失效；本期不实现单设备 Token 黑名单。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `token_version` | Integer | 登出时递增 | 需求文档原文 |

---

**开发任务**：
1. 在登出事务中递增当前管理员版本。
2. 保留登出操作日志与成功响应。
3. 验证前端登出后清理本地会话。

**不在本环节范围内**：
- 不实现单设备登出。
- 不新增 Token 黑名单。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 登出后原 Token 立即 401 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 同账号其他设备旧 Token 同时 401 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 重新登录正常 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-007** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-007 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-008 账号安全操作的版本递增矩阵**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-008] 账号安全操作的版本递增矩阵

**目标**：在重置密码和实际角色变化时撤销会话，并保证备注、相同角色和解锁不误递增。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-002 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/accounts.py` — 本环节实际代码或验证位置
- `@backend/schemas/admin_auth.py` — 本环节实际代码或验证位置
- `@backend/models/admin_user.py` — 本环节实际代码或验证位置
- `@tests/test_admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 超级管理员重置密码、实际角色变更时递增；仅修改备注或提交相同角色不递增；超级管理员手动解锁不递增，旧会话不能复活。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `token_version` | Integer | 账号安全操作的会话版本 | 需求文档原文 |

---

**开发任务**：
1. 重置密码成功时递增目标账号版本。
2. 仅在 `role` 实际变化时递增；备注或相同角色保持不变。
3. 解锁仅清锁定与计数，不递增版本；验证旧 Token 仍失效。

**不在本环节范围内**：
- 不新增管理员停用/重新启用接口或 UI。
- 不把紧急数据库停用做成日常功能。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 重置/实际角色变更递增版本 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 备注/相同角色/解锁不递增 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 解锁后锁定前 Token 仍为 401 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-008** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-008 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-009 life-config 发布服务端 CONFIRM 校验**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-009] life-config 发布服务端 CONFIRM 校验

**目标**：在生活流发布端点显式校验 `confirm_text == "CONFIRM"`。

---

**前置条件检查**：

> 无前置条件。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/life_config_mgmt.py` — 本环节实际代码或验证位置
- `@backend/constants/__init__.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 发布请求模型增加 `confirm_text`；字段允许缺省或空值进入端点业务校验；缺失、空值或错误值统一通过 `ApiResponse` 返回业务码 `20021`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `confirm_text` | String/None | 发布确认文本 | 需求文档原文 |

---

**开发任务**：
1. 为 `PublishBody` 增加可缺省/空值字段。
2. 端点在发布前严格校验等于 `CONFIRM`，否则返回 20021。
3. 补充无值、空值、错误值、正确值与无权限回归。

**不在本环节范围内**：
- 不改变草稿、生效版本、历史版本、回滚或数据库结构。
- CONFIRM 不是二次认证。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 正确 CONFIRM 且有权限时成功 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 缺失/空值/错误值均返回 20021 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 无权限仍为 403 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-009** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-009 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-010 7 个 life-config 前端发布入口传递 CONFIRM**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-010] 7 个 life-config 前端发布入口传递 CONFIRM

**目标**：让当前 7 处生活流发布调用显式发送 `confirm_text: "CONFIRM"`。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-009 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/life-feed-global.html` — 本环节实际代码或验证位置
- `@admin/pages/life-feed-prompts.html` — 本环节实际代码或验证位置
- `@admin/pages/life-feed-system.html` — 本环节实际代码或验证位置
- `@admin/pages/life-plan.html` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 当前 7 处 life-config 前端发布调用全部显式传递 `confirm_text: "CONFIRM"`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `confirm_text` | String | 固定值 CONFIRM | 需求文档原文 |

---

**开发任务**：
1. 逐一核对并修改已定位的 7 处 `/api/admin/life-config/publish` 调用。
2. 保留每个入口原有 `config_key`、`config_value` 和交互。
3. 增加静态契约测试确保数量与参数均覆盖。

**不在本环节范围内**：
- 不修改人格、Step5/Step5.5 的测试/发布逻辑。
- 不新增第 8 个发布入口。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 7 处合法发布均显式传 CONFIRM |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 任一入口缺字段时静态测试失败 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有草稿/发布交互保持不变 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-010** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-010 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-011 共享递归凭据脱敏工具**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-011] 共享递归凭据脱敏工具

**目标**：实现共享、无状态、幂等、失败关闭的精确凭据脱敏工具。

---

**前置条件检查**：

> 无前置条件。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/utils/` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 对字典和数组直接递归；字符串先尝试按 JSON 解析，无法解析时只匹配已知凭据赋值格式和 Authorization/Bearer 形式；命中值统一替换为 `[REDACTED]`。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `[REDACTED]` | String | 所有命中凭据的替换值 | 需求文档原文 |

---

**开发任务**：
1. 递归处理 dict/list 与嵌套组合，字符串优先解析 JSON。
2. 非 JSON 仅匹配文档列出的凭据字段、赋值格式及 Authorization/Bearer。
3. 保证无状态、幂等；单字段异常失败关闭但不让业务失败。

**不在本环节范围内**：
- 不遮蔽 Prompt、对话、记忆、描述、版本或 `max_tokens`。
- 不批量改写历史数据库行。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 嵌套对象/数组及 JSON 字符串凭据被替换 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 非 JSON Authorization/Bearer 与已知赋值被替换 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 重复调用幂等且 max_tokens 等不误伤 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-011** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-011 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-012 操作日志写入、列表、详情与导出双层脱敏**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-012] 操作日志写入、列表、详情与导出双层脱敏

**目标**：在操作日志写入和全部后台读取路径复用共享脱敏工具。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-011 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/operation_logs.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> `log_operation` 写入前递归脱敏；操作日志列表、详情和导出返回前再次调用同一工具，遮蔽历史遗留明文。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `before_value` | Text | 写入和读取双层脱敏 | 需求文档原文 |
| `after_value` | Text | 写入和读取双层脱敏 | 需求文档原文 |
| `target_description` | String | 可能含凭据时脱敏 | 需求文档原文 |

---

**开发任务**：
1. 在 `log_operation` 写入前处理目标描述、before、after。
2. 列表、详情、Excel 导出读取时再次处理历史值。
3. 确保脱敏异常不阻断原业务或审计写入。

**不在本环节范围内**：
- 不改写既有数据库历史行。
- 不改变日志筛选和导出格式。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 新写入的嵌套凭据已脱敏 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 模拟历史明文在列表/详情/导出均遮蔽 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 非凭据日志内容不变 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-012** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-012 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-013 系统日志列表与导出统一脱敏**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-013] 系统日志列表与导出统一脱敏

**目标**：让系统日志列表和导出对所有管理员统一使用共享脱敏工具。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-011 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/system_monitor.py` — 本环节实际代码或验证位置
- `@backend/utils/` — 本环节实际代码或验证位置
- `@tests/test_system_monitor_logs.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 系统日志列表和导出返回前也调用同一工具，所有管理员角色获得一致的安全读取结果。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| 系统日志行 | String/Object | 返回前共享脱敏 | 需求文档原文 |

---

**开发任务**：
1. 在系统日志分页结果生成前调用共享工具。
2. 在系统日志导出内容生成前调用同一工具。
3. 覆盖已知凭据赋值、Authorization/Bearer 与非凭据内容。

**不在本环节范围内**：
- 不改变日志文件收集、级别筛选和排序。
- 不只对观察者脱敏。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 列表中的凭据被遮蔽 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 导出中的同一凭据被遮蔽 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 普通日志、Prompt 和 max_tokens 不误伤 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-013** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-013 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-014 阶段 A 自动化安全回归**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-014] 阶段 A 自动化安全回归

**目标**：用 pytest 覆盖阶段 A 的配置、会话、登录、CONFIRM、脱敏和原有行为。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-001~STEP-013 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@tests/` — 本环节实际代码或验证位置
- `@backend/` — 本环节实际代码或验证位置
- `@admin/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 以现有 pytest 为主要自动化门禁，补充安全鉴权、脱敏、路由清单和静态页面契约测试；测试报告必须记录实际命令、通过/失败数量和失败原因。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 补齐 JWT 配置、历史 Token、版本撤销矩阵和登录统一响应测试。
2. 补齐 CONFIRM 后端及 7 个前端入口契约测试。
3. 补齐操作日志与系统日志脱敏的正常、异常、边界测试并运行相关回归。

**不在本环节范围内**：
- 不新建 CI/CD 工作流。
- 不引入 Playwright。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 相关 pytest 全部通过并记录命令/数量 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 失败时记录原因且不得标为可发布 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 既有四角色相关自动化无回归 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-014** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-014 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-015 真实 MySQL 8 并发登录验证**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-015] 真实 MySQL 8 并发登录验证

**目标**：在独立非生产 MySQL 8 环境验证行锁计数不丢失。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-004,STEP-005 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@tests/` — 本环节实际代码或验证位置
- `@docs/testing/` — 本环节实际代码或验证位置
- `@docs/progress/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 独立、非生产的真实 MySQL 8 集成环境；显式独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> MySQL 行锁必须在独立、非生产的 MySQL 8 集成环境执行并发测试；SQLite 单元测试不能代替行锁验证。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 准备显式独立 ADMIN_JWT_SECRET 的非生产 MySQL 8 测试环境。
2. 执行同一账号并发错密，验证计数、第五次锁定与版本递增。
3. 记录真实命令、并发规模、通过/失败数量和失败原因。

**不在本环节范围内**：
- 不在生产数据库执行。
- 不以 SQLite 结果替代。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 并发错密计数不丢失 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 阈值达到后锁定且版本仅按规则递增 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 锁定后计数保持 5 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-015** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-015 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-016 阶段 A 四角色回归与真实验证记录**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-016] 阶段 A 四角色回归与真实验证记录

**目标**：完成原有四角色回归并仅据真实结果更新漏洞验证记录。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-014,STEP-015 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@tests/` — 本环节实际代码或验证位置
- `@docs/security/admin-backend-vulns-2026-07.md` — 本环节实际代码或验证位置
- `@docs/progress/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 现有 4 个角色的登录、读写、发布、账号管理和日志导出回归通过；漏洞专档中本期项目均填写真实验证结果；VULN-001、VULN-007 及恶意锁号风险仍明确标为未修。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 按四角色执行登录、读写、发布、账号管理、日志导出回归。
2. 汇总自动化、MySQL 并发和人工结果。
3. 仅对实际验证的 VULN-002/003/004/005/006/008 响应部分/009 填写结果。

**不在本环节范围内**：
- 不关闭 VULN-001、VULN-007 或 VULN-008 恶意锁号风险。
- 测试失败不得写成已验证。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 四角色合法能力无回归 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 已修项目均有真实证据 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 延期与接受风险仍明确保留 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-016** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-016 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-017 阶段 A 契约同步、独立部署与人工门禁**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-017] 阶段 A 契约同步、独立部署与人工门禁

**目标**：只同步已验证的安全契约，并在人工确认、独立部署和稳定性确认后开放阶段 B。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-016 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@docs/contract.md` — 本环节实际代码或验证位置
- `@.cursorrules` — 本环节实际代码或验证位置
- `@docs/security/admin-backend-vulns-2026-07.md` — 本环节实际代码或验证位置
- `@docs/progress/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 按当前项目环境；测试环境显式配置独立 ADMIN_JWT_SECRET。

---

**需求原文引用**：

> 阶段 A 实现、验证并经人工确认后，只同步已经生效的安全契约，观察者继续标记未实现；阶段 A 前后端同步发布，部署后通知所有管理员重新登录，并完成运行稳定性确认。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 取得人工确认后同步阶段 A 已验证契约与长期规则。
2. 独立部署阶段 A 前后端，保留 `token_version` 兼容字段并通知全员重新登录。
3. 记录运行稳定性确认；未确认前将阶段 B 标为阻塞。

**不在本环节范围内**：
- 不提前把 `observer` 写成已上线。
- 不把 A/B 合并为一次开发或部署。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 主契约只描述已生效安全项 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 部署后全员旧 Token 失效并可重新登录 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 人工稳定性门禁有确认人和日期 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-017** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-017 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-018 observer 角色与账号管理最小扩展**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-018] observer 角色与账号管理最小扩展

**目标**：在现有分散结构中加入数据库值 `observer` 和展示名“观察者”。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-017 必须全部为 ✅。若任一不是 ✅，停止本环节。

> 额外门禁：阶段 A 必须已独立部署、完成运行稳定性确认，并有人工确认记录；否则禁止开始阶段 B。

---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/schemas/admin_auth.py` — 本环节实际代码或验证位置
- `@backend/models/admin_user.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/accounts.py` — 本环节实际代码或验证位置
- `@admin/pages/accounts.html` — 本环节实际代码或验证位置
- `@admin/static/js/admin-api.js` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 数据库存储 `observer`，前端展示“观察者”；仅 `super_admin` 可以创建、修改、重置、解锁或删除观察者账号；本期不重构角色注册中心。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `role` | String | observer | 需求文档原文 |
| 角色展示名 | String | 观察者 | 需求文档原文 |

---

**开发任务**：
1. 扩展 Pydantic 角色校验、模型注释和账号创建/编辑选项标签。
2. 保持全部账号管理 API 仅 `super_admin` 可用。
3. 在现有菜单、Header 标签等结构最小加入 observer，不建立统一注册中心。

**不在本环节范围内**：
- 不新增角色数据库迁移。
- 不新增管理员停用/启用功能。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 超级管理员可创建和管理 observer |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 其他角色无法调用账号管理 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 现有四角色选项和标签不受影响 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-018** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-018 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-019 观察者后端方法级集中总闸**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-019] 观察者后端方法级集中总闸

**目标**：在统一管理员鉴权入口按方法默认拒绝观察者写请求，只精确放行登出和自助改密。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-018 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/auth.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 总闸执行顺序为 JWT 与 `token_version` 校验、数据库实时账号/角色校验、锁定与启用状态校验，然后再执行观察者方法规则；`POST/PUT/PATCH/DELETE` 默认 403，仅精确放行登出和修改自己的密码。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 让统一依赖取得 Request 并在完整身份校验后执行观察者方法规则。
2. 只按完整方法＋路径精确放行两个 auth 端点。
3. 确认 GET/HEAD 仅进入后续 `require_role`，不是自动授权。

**不在本环节范围内**：
- 不使用宽路径前缀白名单。
- 不替代各路由已有 `require_role`。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者任意普通写方法返回 403 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 两个精确例外可进入原业务校验 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 伪造/过期/锁定/版本错误先被鉴权拒绝 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-019** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-019 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-020 CORS OPTIONS 匿名预检边界**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-020] CORS OPTIONS 匿名预检边界

**目标**：保持 CORS OPTIONS 为匿名基础设施预检，且不返回业务数据。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/main.py` — 本环节实际代码或验证位置
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> CORS 中间件处理的 `OPTIONS` 预检作为匿名基础设施请求放行，不返回后台业务数据，也不属于观察者业务读取权限。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 验证 CORS 中间件在业务依赖前处理预检。
2. 确保总闸不把 OPTIONS 实现成需 Admin JWT 的读取请求。
3. 增加匿名预检与业务 GET/HEAD 鉴权对比测试。

**不在本环节范围内**：
- 不为 OPTIONS 返回后台业务数据。
- 不放宽 GET/HEAD 的 Admin 鉴权。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 匿名 OPTIONS 正常返回预检响应 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 匿名 GET/HEAD 仍为 401 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | OPTIONS 不触发业务端点副作用 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-020** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-020 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-021 3 个内建导出接口显式拒绝观察者**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-021] 3 个内建导出接口显式拒绝观察者

**目标**：用与 HTTP 方法无关的专用依赖拒绝观察者访问三个导出端点。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/operation_logs.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/stats.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/system_monitor.py` — 本环节实际代码或验证位置
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 当前 3 个系统内建导出接口分别增加专用观察者拒绝依赖：操作日志、数据报表、系统日志；未来新增导出/下载接口也必须与 HTTP 方法无关地显式拒绝。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 实现可复用的观察者导出拒绝依赖。
2. 分别挂到 operation-logs、stats/report、system/logs 三个 export 路由。
3. 增加导出路由清单测试，防止未来 GET 导出绕过方法总闸。

**不在本环节范围内**：
- 不承诺阻止截图、复制或分页聚合。
- 不删除原有角色依赖。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者访问三个导出均 403 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 原有合法角色仍可导出 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 路由清单能发现未挂拒绝依赖的新导出 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-021** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-021 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-022 用户、统计与日志读取角色拆分**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-022] 用户、统计与日志读取角色拆分

**目标**：让观察者读取用户业务数据、统计和脱敏操作日志，同时保留所有写权限边界。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019,STEP-012 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/users.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/stats.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/operation_logs.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 将观察者加入除账号管理外的必要读取角色集合；现有同时用于 GET 和写请求的角色集合必须拆分为读取集合与写入集合。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 逐路由区分 GET/HEAD 与写操作的角色集合。
2. 为观察者开放确认范围内的用户、统计与已脱敏操作日志读取。
3. 保持用户 Open API Key 敏感显示另由 STEP-026 处理。

**不在本环节范围内**：
- 不开放 `/accounts` 任何读取。
- 不把 observer 加入共用写角色集合。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者可读取确认的用户/统计/日志数据 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 同模块写接口仍 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有四角色合法权限不变 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-022** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-022 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-023 AI 配置与测试模块读取角色拆分**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-023] AI 配置与测试模块读取角色拆分

**目标**：开放人格、Prompt、只读 Prompt、测试历史/配置和安全规则的必要读取，禁止保存、发布、回滚、导入与测试。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/persona.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/prompt_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/chat_prompt_view.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/test_cases.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/safety_rules.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> AI 测试工具页可查看配置或历史结果，但不能发起测试、保存用例或触发生成；业务数据只读开放。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 为各模块建立明确 READ/WRITE 角色集合。
2. 仅将 observer 加入 GET/HEAD 读取端点。
3. 确认测试、保存草稿、发布、回滚、导入、删除等仍由写集合限制。

**不在本环节范围内**：
- 不修改 VULN-001 的测试/发布状态机。
- 不把 observer 加入 `_ALLOWED_ROLES` 共用写集合。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者可读配置/历史 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 观察者测试、保存、发布、回滚均 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 四角色原有能力无误伤 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-023** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-023 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-024 记忆、向量、知识、Agent、关系与情绪读取角色拆分**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-024] 记忆、向量、知识、Agent、关系与情绪读取角色拆分

**目标**：让观察者读取这些业务配置和数据，同时阻止保存、测试连接、生成、删除等动作。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/memory_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/vector_config.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/knowledge_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/agent_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/relationship_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/emotion_config.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/world_state_mgmt.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> `memory-rules.html` 可读取 Step6 Prompt、全局记忆和非敏感 DashVector 参数，但不能保存 Prompt、测试连接、修改密钥或删除记忆；`vector-token-config.html` 的召回和 Token 数值可读但不可保存。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 逐模块拆分 GET/HEAD 读取集合与写集合。
2. 开放确认范围内的记忆、向量数值、知识、Agent、关系、情绪和世界状态读取。
3. 保持测试连接、保存、生成、重置和删除为写权限。

**不在本环节范围内**：
- 不把 `memory-rules.html` 当作 Embedding 配置页。
- 不改变现有业务数据结构。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者读取端点成功 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 所有写/测试/删除端点仍 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有角色读取与写入回归通过 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-024** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-024 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-025 系统监控、系统日志与第三方状态读取角色拆分**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-025] 系统监控、系统日志与第三方状态读取角色拆分

**目标**：开放系统监控、脱敏日志和第三方非敏感状态读取，保持配置修改与连接测试受限。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019,STEP-013 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/system_monitor.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 观察者可读取第三方服务状态和非敏感配置；系统日志和操作日志统一脱敏。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 拆分 system_monitor 中 GET/HEAD 与 PUT/POST 角色集合。
2. 开放系统状态、第三方状态和脱敏系统日志读取。
3. 保持第三方配置更新、连接测试和系统日志导出受限。

**不在本环节范围内**：
- 不向观察者返回凭据片段。
- 不改变系统监控缓存语义。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者可读取系统与第三方状态 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 更新/测试/导出仍 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有 tech_ops 能力不受影响 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-025** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-025 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-026 生活流全模块读取角色拆分**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-026] 生活流全模块读取角色拆分

**目标**：让观察者读取生活流计划、配置、内容、评论、感知与世界观，禁止全部写操作。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/life_config_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/life_plan_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/feed_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/feed_comment_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/agent_aware_mgmt.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/worldview_mgmt.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 除账号管理外，业务数据只读开放，包括配置；现有同时用于 GET 和写请求的角色集合必须拆分为读取集合与写入集合。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 逐个生活流路由将 GET/HEAD 加入 observer 读取集合。
2. 保持生成、保存、发布、编辑、显隐、重试、删除、重置等写集合不含 observer。
3. 核对 life-config、生活计划、朋友圈、评论、感知、世界观所有路由。

**不在本环节范围内**：
- 不改变生活流草稿、版本、回滚和发布一致性。
- 不新增生活流功能。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 观察者可读取六类生活流数据 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 所有生活流写请求均 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有 ops 只读与其他角色写权限不变 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-026** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-026 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-027 第三方凭据与用户 Open API Key 状态化展示**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-027] 第三方凭据与用户 Open API Key 状态化展示

**目标**：观察者读取凭据时只获得“已配置/未配置”，不获得首尾字符。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-022,STEP-025 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/routers/admin/system_monitor.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/users.py` — 本环节实际代码或验证位置
- `@admin/pages/third-party.html` — 本环节实际代码或验证位置
- `@admin/pages/user-detail.html` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 第三方凭据及用户 Open API Key 对观察者只显示“已配置/未配置”，不显示首尾字符或其他可推断片段。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| 凭据状态 | String/Boolean | 已配置/未配置 | 需求文档原文 |

---

**开发任务**：
1. 按数据库实时 observer 角色裁剪第三方凭据响应。
2. 按 observer 角色裁剪用户 Open API Key 读取响应。
3. 前端按状态展示，其他管理员保持既有权限与统一日志脱敏。

**不在本环节范围内**：
- 不返回 prefix、suffix 或其他可推断片段。
- 不改变其他角色现有接口权限。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 已配置凭据仅显示已配置 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 未配置凭据仅显示未配置 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 响应中不含首尾字符、明文或哈希 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-027** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-027 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-028 全量 Admin 路由鉴权与 GET/HEAD 副作用审计**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-028] 全量 Admin 路由鉴权与 GET/HEAD 副作用审计

**目标**：自动枚举所有 Admin 路由，验证鉴权、观察者写总闸及 GET/HEAD 无业务副作用。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-019~STEP-027 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@backend/main.py` — 本环节实际代码或验证位置
- `@backend/routers/admin/*.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 自动枚举所有 `/api/admin/*` 路由：除登录外必须有管理员鉴权；当前 GET/HEAD 接口不得修改 MySQL 业务数据、权限、账号状态、配置版本，不得触发生成、测试、发布、修复、回填、删除或异步任务。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 建立路由清单测试，检查除登录外的管理员鉴权。
2. 验证所有写路由受观察者总闸，导出有显式拒绝。
3. 逐个审计 GET/HEAD 副作用；仅允许权威读取派生的幂等有限 TTL 缓存回填。

**不在本环节范围内**：
- 不把缓存回填误判为业务写入。
- 不借审计重构无关路由。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 无漏鉴权 Admin 路由 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 观察者无法绕过前端写入或导出 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | GET/HEAD 不产生禁止的业务副作用 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-028** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-028 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-029 前端 observer 公共菜单、Header、只读助手与请求兜底**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-029] 前端 observer 公共菜单、Header、只读助手与请求兜底

**目标**：提供观察者公共角色判断、菜单、Header、首屏/动态只读助手和非 GET 请求兜底。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-018,STEP-019 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/static/js/admin-api.js` — 本环节实际代码或验证位置
- `@admin/static/css/admin-common.css` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 使用公共只读助手、标准写操作标记和 `adminRequest` 非 GET 兜底；写按钮隐藏，展示型文本只读，选择框、开关和文件控件禁用；保留搜索、筛选、分页、Tab、详情、复制和纯 GET 刷新。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `data-write-action` | HTML attribute | 统一写操作标记（示例名称） | [自定义] |

---

**开发任务**：
1. 在现有结构加入 `isObserver()` 和 `applyObserverReadOnly()`，覆盖静态与动态节点。
2. 为 observer 配置不含账号管理的菜单与 Header“观察者”。
3. `adminRequest()` 默认阻止 observer 非 GET，仅精确放行登出与自助改密。

**不在本环节范围内**：
- 不按元素类型粗暴禁用全部按钮或表单。
- 前端不作为权限安全边界。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 写控件按类型隐藏/只读/禁用 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 读取交互保持可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 动态插入控件和非 GET 兜底均生效 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-029** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-029 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-030 观察者账号管理页直访拦截**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-030] 观察者账号管理页直访拦截

**目标**：观察者直接打开账号页时立即跳转，且永远不能取得账号数据。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/accounts.html` — 本环节实际代码或验证位置
- `@admin/static/js/admin-api.js` — 本环节实际代码或验证位置
- `@backend/routers/admin/accounts.py` — 本环节实际代码或验证位置
- `@tests/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 账号管理菜单不显示；直接打开静态页面时由前端立即拦截/跳转，账号数据 API（含 `GET /accounts`）始终 403。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 在 accounts 页面数据请求前识别 observer 并跳转 403 页。
2. 确认 observer 菜单中无账号管理。
3. 直接 API 覆盖 GET、创建、编辑、重置、解锁、删除均为 403。

**不在本环节范围内**：
- 不依赖静态 HTML 本身保护账号数据。
- 不改变 super_admin 管理账号能力。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 直访立即跳转且未发账号请求 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | observer GET /accounts 为 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | super_admin 页面与 API 正常 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-030** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-030 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-031 用户、报表与日志页面观察者只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-031] 用户、报表与日志页面观察者只读改造

**目标**：完成用户、用户详情、数据报表、操作日志和系统日志页面的观察者只读体验。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-022,STEP-021,STEP-027,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/users.html` — 本环节实际代码或验证位置
- `@admin/pages/user-detail.html` — 本环节实际代码或验证位置
- `@admin/pages/data-report.html` — 本环节实际代码或验证位置
- `@admin/pages/operation-logs.html` — 本环节实际代码或验证位置
- `@admin/pages/system-logs.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 搜索、筛选、分页、详情和只读数据展示可用；新增、编辑、保存、删除、导入、导出等入口不可用。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 为五页静态和动态写控件添加统一标记或等价处理。
2. 保留搜索、筛选、分页、详情、复制与 GET 刷新。
3. 隐藏三个页面中的内建导出入口，并落实 Open API Key 状态展示。

**不在本环节范围内**：
- 不阻止普通复制或分页查看。
- 不改变原有四角色合法写操作。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 五页可进入并加载数据 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 写入/导出控件不可用且 API 兜底 403 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 四角色合法操作回归 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-031** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-031 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-032 系统监控、第三方、AI 测试与看板页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-032] 系统监控、第三方、AI 测试与看板页面只读改造

**目标**：让观察者读取系统、第三方、AI 测试配置/历史和看板，同时禁止测试、保存和生成。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-023,STEP-025,STEP-027,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/system-monitor.html` — 本环节实际代码或验证位置
- `@admin/pages/third-party.html` — 本环节实际代码或验证位置
- `@admin/pages/test-tool.html` — 本环节实际代码或验证位置
- `@admin/pages/dashboard.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> AI 测试工具页可查看配置或历史结果，但不能发起测试、保存用例或触发生成；第三方凭据只显示配置状态。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 开放四页 observer 直访与读取角色判断。
2. 处理连接测试、配置保存、用例保存、生成等静态和动态写控件。
3. 第三方页只展示凭据配置状态，保留看板与系统监控读取交互。

**不在本环节范围内**：
- 不显示任何凭据首尾字符。
- 不新增浏览器自动化基础设施。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 四页数据可加载 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 测试/保存/生成控件不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 第三方凭据只显示状态 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-032** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-032 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-033 人格、Prompt、安全规则与对话流 Prompt 页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-033] 人格、Prompt、安全规则与对话流 Prompt 页面只读改造

**目标**：让观察者读取人格、Prompt、安全规则和四个只读 Prompt 页面，禁止所有编辑、测试与发布动作。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-023,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/persona.html` — 本环节实际代码或验证位置
- `@admin/pages/prompt.html` — 本环节实际代码或验证位置
- `@admin/pages/step5-5-switch.html` — 本环节实际代码或验证位置
- `@admin/pages/safety-rules.html` — 本环节实际代码或验证位置
- `@admin/pages/chat-prompt-step15.html` — 本环节实际代码或验证位置
- `@admin/pages/chat-prompt-step3.html` — 本环节实际代码或验证位置
- `@admin/pages/chat-prompt-step8.html` — 本环节实际代码或验证位置
- `@admin/pages/chat-prompt-agent.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 写按钮隐藏；展示型文本字段只读；选择框、开关和文件控件禁用；AI 测试工具不能触发生成。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 扩展八页直访角色判断支持 observer。
2. 处理草稿、保存、测试、发布、回滚、导入和动态弹窗提交。
3. 保留 Tab、历史、详情、复制及纯 GET 刷新。

**不在本环节范围内**：
- 不修复 VULN-001。
- 不改变 Step5/Step5.5 发布业务逻辑。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 八页读取正常 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 写/测试/发布/回滚/导入入口不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 四角色原有合法操作正常 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-033** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-033 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-034 记忆、向量与知识页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-034] 记忆、向量与知识页面只读改造

**目标**：让观察者读取 Step6 Prompt、全局记忆、DashVector 非敏感参数、召回/Token 数值与知识库。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-024,STEP-027,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/memory-rules.html` — 本环节实际代码或验证位置
- `@admin/pages/vector-token-config.html` — 本环节实际代码或验证位置
- `@admin/pages/knowledge.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> `memory-rules.html` 是 Step6 Prompt、全局记忆和 DashVector 配置页；Embedding 配置位于 `third-party.html`；`vector-token-config.html` 只管理召回和 Token 数值。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 三页加入 observer 访问与统一只读处理。
2. 禁止保存 Prompt、测试连接、修改密钥、删除记忆、保存数值及知识增删改。
3. 保留 Tab、查询、筛选、分页、详情和复制。

**不在本环节范围内**：
- 不把 memory-rules 改成 Embedding 页。
- 不显示 DashVector 凭据片段。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 三页读取与查询正常 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 所有保存/测试/删除/增改入口不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 页面归属与 PRD 一致 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-034** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-034 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-035 Agent、关系、日记规则与日记历史页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-035] Agent、关系、日记规则与日记历史页面只读改造

**目标**：让观察者读取 Agent、关系、日记规则和日记历史，禁止配置保存。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-024,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/agent-rules.html` — 本环节实际代码或验证位置
- `@admin/pages/relationship-rules.html` — 本环节实际代码或验证位置
- `@admin/pages/diary-rules.html` — 本环节实际代码或验证位置
- `@admin/pages/diary-history.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 除账号管理外，业务数据只读开放；选择框、开关等无法只读的控件禁用，筛选、分页、Tab、详情保留。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 四页加入 observer 直访与读取支持。
2. 处理规则保存、影响确认、关键词保存等静态和动态写入口。
3. 保留日记历史筛选分页及各页读取交互。

**不在本环节范围内**：
- 不修改运行时技术债。
- 不改变现有四角色权限矩阵。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 四页数据可加载 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 规则保存与确认入口不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 日记历史筛选分页可用 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-035** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-035 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-036 生活计划与世界观页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-036] 生活计划与世界观页面只读改造

**目标**：让观察者查看生活计划和她的宇宙，禁止生成、增删改和配置保存。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-026,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/life-plan.html` — 本环节实际代码或验证位置
- `@admin/pages/worldview.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 搜索、筛选、分页、Tab、详情和纯 GET 刷新保持可用；新增、编辑、保存、删除、发布、回滚、测试等入口不可用。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 扩展两页 `initLifeFeedPage` 或等价访问判断支持 observer。
2. 标记首屏与动态生成/编辑/删除/保存控件。
3. 保留日期、分页、详情和只读展示。

**不在本环节范围内**：
- 不改变 ops_admin 现有只读语义。
- 不修改生活流数据模型。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 两页进入和数据加载正常 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 生成/增删改/保存均不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | ops_admin 与可写角色回归 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-036** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-036 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-037 朋友圈内容、评论与感知页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-037] 朋友圈内容、评论与感知页面只读改造

**目标**：让观察者读取朋友圈内容、评论与感知队列，禁止编辑、发帖、重试、删除和重置。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-026,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/feed-posts.html` — 本环节实际代码或验证位置
- `@admin/pages/feed-comments.html` — 本环节实际代码或验证位置
- `@admin/pages/agent-aware.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 动态创建的按钮、表格行操作和弹窗提交均已覆盖。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 三页加入 observer 访问与公共只读助手。
2. 覆盖表格行编辑/显隐/发帖、评论编辑/软删/补发、感知重试/删除/重置等动态入口。
3. 保留列表、筛选、分页、详情和刷新。

**不在本环节范围内**：
- 不新增真删除或其他生活流功能。
- 不改变 ops_admin 已有读取范围。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 三页列表和详情可用 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 所有动态写操作不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 四角色合法操作无回归 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-037** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-037 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-038 生活流人格拓展、Prompt 与系统参数页面只读改造**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-038] 生活流人格拓展、Prompt 与系统参数页面只读改造

**目标**：让观察者读取三类生活流配置，禁止草稿、发布、测试和保存。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-026,STEP-029 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/life-feed-global.html` — 本环节实际代码或验证位置
- `@admin/pages/life-feed-prompts.html` — 本环节实际代码或验证位置
- `@admin/pages/life-feed-system.html` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 观察者可以读取配置；写按钮隐藏，展示型文本字段只读，选择框、开关和文件控件禁用。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 三页加入 observer 访问与公共只读助手。
2. 覆盖静态及动态草稿、发布、保存、测试等控件。
3. 保留 Tab、配置展示、纯 GET 刷新和状态查看。

**不在本环节范围内**：
- 不改变 7 个 CONFIRM 调用的合法角色流程。
- 不重构数据库与 Redis 发布一致性。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 三页读取正常 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 草稿/发布/测试/保存均不可用 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有合法发布入口继续发送 CONFIRM |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-038** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-038 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-039 阶段 B 后端权限与敏感读取自动化门禁**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-039] 阶段 B 后端权限与敏感读取自动化门禁

**目标**：自动验证 observer 的鉴权、只读、例外、导出拒绝、凭据状态化和四角色回归。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-018~STEP-028 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@tests/` — 本环节实际代码或验证位置
- `@backend/routers/admin/` — 本环节实际代码或验证位置
- `@backend/utils/admin_auth.py` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 观察者权限测试、路由/页面契约测试和全角色回归通过；绕过前端直接请求仍不能写入或导出。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 自动枚举路由并覆盖鉴权、GET/HEAD、所有写方法、两个例外和 CORS OPTIONS。
2. 覆盖账号 API、三个导出、第三方/Open API Key 敏感读取。
3. 按五角色后端权限矩阵验证 observer 与原有四角色。

**不在本环节范围内**：
- 不新增 CI/CD。
- 不以 UI 隐藏替代 API 测试。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | observer 允许读取项全部成功 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | observer 写入/账号/导出全部拒绝 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 原有四角色合法权限无误伤 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-039** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-039 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 STEP-040 35 页面五角色验收、文档同步与阶段 B 独立部署**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

### [STEP-040] 35 页面五角色验收、文档同步与阶段 B 独立部署

**目标**：完成 35 页盘点、所有权限变动页五角色验收，并仅据真实结果同步契约和独立部署阶段 B。

---

**前置条件检查**：

> 开始前检查 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`：STEP-030~STEP-039 必须全部为 ✅。若任一不是 ✅，停止本环节。


---

**需要参考的文件**：
- `@docs/design/PRD-管理后台观察者与安全加固-v1.md` — 目标方案与验收边界
- `@docs/design/PROJECT_CONFIG_林小梦.md` — 项目实况与长期约束
- `@docs/security/admin-backend-vulns-2026-07.md` — 漏洞处置范围
- `@admin/pages/*.html` — 本环节实际代码或验证位置
- `@admin/pages/login.html` — 35 页盘点中的匿名登录页
- `@admin/pages/error.html` — 35 页盘点中的公共错误页
- `@tests/` — 本环节实际代码或验证位置
- `@docs/contract.md` — 本环节实际代码或验证位置
- `@.cursorrules` — 本环节实际代码或验证位置
- `@docs/security/admin-backend-vulns-2026-07.md` — 本环节实际代码或验证位置
- `@docs/progress/` — 本环节实际代码或验证位置

**环境/数据前提**：
- 阶段 A 已通过 STEP-017 门禁。

---

**需求原文引用**：

> 35 个页面全部纳入盘点；所有权限变动页面按 5 角色权限矩阵逐页验证；阶段 B 实现并验证后再更新 `docs/contract.md` 和相关长期规则，并独立部署。

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| — | — | 无新增字段 | 需求文档原文 |

---

**开发任务**：
1. 记录每页、角色、直访、首屏加载、读取交互、静态/动态写控件、合法写操作回归和结论；`login.html`、`error.html` 作为匿名/公共页单独核对，不套用五角色业务写控件规则。
2. 运行页面静态契约测试；动态交互按 PRD 使用逐页人工浏览器验收，不引入 Playwright。
3. 全部通过后同步 observer/RBAC 契约、漏洞与 PRD 状态，记录命令/数量/失败原因并独立部署。

**不在本环节范围内**：
- 不把防截图、复制、分页聚合描述成能力。
- 任何失败时不得标为可发布或已完成。

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | 满足本 STEP 的合法输入/角色/环境 | 35 页均有验收记录且账号页禁入 |
| 异常场景 | 违反本 STEP 的权限、字段或状态条件 | 权限变动页五角色矩阵完整 |
| 边界测试 | 本 STEP 明确的临界值、历史兼容或无操作场景 | 文档只反映已验证事实且阶段 B 独立部署 |

---

**完成标志**：
- [ ] 本 STEP 功能或验证任务已按需求原文完成
- [ ] 本 STEP 新增/调整测试全部通过，并记录真实命令、通过/失败数量
- [ ] 相关回归通过，未影响前置环节及原有合法角色
- [ ] 已遵守阶段契约规则：未验证前不提前修改主契约；到阶段收口 STEP 才同步已生效内容
- [ ] `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 中 **STEP-040** 已更新为 ✅ 并填写完成日期

---

**完成后执行**：

> 1. 打开 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`。  
> 2. 将 STEP-040 状态从 ⬜ 改为 ✅，填写完成日期和真实验证摘要。  
> 3. 提示开发者：**下一个环节是 无；本 PRD 全部环节完成**。  
> 4. 若下一环节属于阶段 B，必须再次确认 STEP-017 的人工门禁；不得自动越过。

## 4. 自检清单

- [x] PRD A1～A6、B1～B5、C1～C26、数据/接口/部署/测试/延期边界均有对应 STEP 或明确排除说明。
- [x] VULN-002、003、004、005、006、008 响应统一部分、009 均有开发与验证 STEP。
- [x] VULN-001、VULN-007、恶意锁号、发布一致性、历史明文、数据外带和前端角色缓存风险未被误写为本期修复。
- [x] 未新增 PRD 外功能；唯一新增命名 `data-write-action` 已按模板标注 `[自定义]`，且 PRD 明确允许“如 data-write-action”。
- [x] 所有代码路径均来自当前仓库核对；通配路径仅用于全量盘点，没有猜测不存在的具体文件。
- [x] 外部模块定义引用 `docs/contract.md` 现状，并通过阶段收口 STEP 约束契约同步时机。
- [x] 依赖关系保持严格 A/B 顺序；STEP-018 明确受 STEP-017 人工门禁约束。
- [x] 每个 STEP 均包含完成回调、测试要求、范围排除和进度更新指令。
- [x] 35 个后台页面全部覆盖：账号页单独禁入；25 个含写入口业务页分组只读改造；其余只读/公共页纳入 35 页五角色盘点。
- [x] 7 个 life-config 发布调用和 3 个内建导出接口均有独立覆盖。
- [x] 进度文档 `docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md` 已生成。
