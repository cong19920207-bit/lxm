# 语音通话独立总开关 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建独立语音总开关页面和发布链路，使切换只改变自身状态，不保存或发布其他语音配置草稿。

**Architecture:** `voice_call_master_switch` 使用既有 `admin_config` 的独立 active 版本，不设草稿。管理端一次确认后调用专属 API；运行时从 MySQL 权威记录读取总开关，再应用既有维护、软停和灰度门禁。旧整包的 `global.enabled` 保留作历史兼容，但不再控制准入。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、MySQL、原生管理后台 HTML/JavaScript、pytest、Playwright、Docker Compose。

**Spec:** `docs/superpowers/specs/2026-09-27-voice-master-switch-design.md`（已确认）。

## Global Constraints

- 只允许 `super_admin`、`tech_ops` 发布总开关；其他现有语音只读角色可查看。
- 切换请求不得修改 `voice_call_config`、`voice_call_script` 的 active、草稿、版本、摘要和历史；普通配置发布/回滚也不得修改独立键。
- 新通话读取总开关；已建立通话不中断。独立状态缺失、损坏或 MySQL 不可用时禁止新通话。
- 开启只读核验当前已生效配置；关闭不依赖其他草稿。维护、软停、灰度、额度、能力和 Provider 检查照旧。
- 部署先迁移、后启用新运行时代码；不通过测试主动开启本地真实语音服务。
- 当前语音实现多为未跟踪文件；执行前保留当前 checkout 的现有改动，不从只含 HEAD 的新 checkout 开始，也不把无关文件放入提交。

## Review Focus

- 遗留 `voice_call_config` 草稿仅改变旧 `global.enabled` 时，普通发布不能改变独立开关；Task 4 的集成测试覆盖。
- 两名管理员同时确认相反目标时，后提交者收到 409 且 UI 显示重新读取的生效值；Task 2、5 覆盖。
- 请求提交成功但响应丢失时，页面重新 GET 后只显示权威状态，不重复盲发；Task 5 覆盖。
- 独立键缺失、值损坏或 MySQL 不可用时，新通话被拒绝且不能被旧 Redis/发布锚放行；Task 3 覆盖。
- 开启状态与软停、维护、灰度冲突时，各原有门禁仍能拒绝新通话；Task 3 覆盖。

---

### Task 1: 独立键与数据迁移

**Files:**
- Modify: `backend/constants/realtime_voice_config.py`（增加 `VOICE_CALL_MASTER_SWITCH_KEY = "voice_call_master_switch"` 并导出）
- Create: `alembic/versions/v8h_voice_master_switch.py`（`revision = "v8h_voice_master_switch_001"`，`down_revision = "v8g_voice_evidence_time_001"`）
- Create: `tests/test_realtime_voice_master_switch_migration.py`

**Interfaces:** Produces 独立键常量与只插入独立 active 行的数据迁移；Task 2、3 使用此常量。迁移记录值精确为 `{"enabled": boolean}`、`version=1`、`is_active=True`、`is_draft=False`、`updated_by="system_migration"`。

- [ ] **Step 1: 写失败测试。** `test_migration_backfills_from_active_without_mutating_drafts` 参数化旧 active 开/关、缺失、无效；`test_migration_skips_existing_switch` 验证已存在时不写；`test_downgrade_preserves_published_switch` 验证降级不删除后续版本。断言旧 active/草稿逐字节不变。
- [ ] **Step 2: 运行红灯。** `docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" -v "$PWD/alembic:/app/alembic:ro" backend pytest -q tests/test_realtime_voice_master_switch_migration.py`；预期因迁移文件/常量缺失失败。
- [ ] **Step 3: 实现数据迁移。** 只读最高版本 active `voice_call_config`，仅布尔 `global.enabled` 可用于初值，其他情况关闭；使用同一连接插入独立键，不改旧行。降级不删独立状态。
- [ ] **Step 4: 重跑同一测试，预期通过。**
- [ ] **Step 5: 仅暂存本任务文件并提交** `feat: seed independent voice master switch`。

### Task 2: 独立发布服务与管理接口

**Files:**
- Create: `backend/services/realtime_voice_master_switch_service.py`
- Create: `backend/routers/admin/voice_master_switch.py`
- Modify: `backend/main.py`（在 `/api/admin/voice` 下注册新路由）
- Modify: `tests/test_step028_admin_route_audit.py`、`tests/test_step039_observer_backend_gate.py`（精确声明 GET/POST 角色）
- Create: `tests/test_realtime_voice_master_switch_api.py`

**Interfaces:** `RealtimeVoiceMasterSwitchService.get_state(db: AsyncSession) -> dict[str, Any]` 返回 `enabled/version/updated_at/updated_by`；`publish(db: AsyncSession, *, enabled: bool, expected_version: int, admin_user: AdminUser, request: Request | None = None) -> dict[str, Any]`。GET `/api/admin/voice/master-switch`；POST `/api/admin/voice/master-switch/publish` Body 仅 `enabled: StrictBool`、`expected_version: int >= 1`。409 为版本冲突，状态不可用为 503。

- [ ] **Step 1: 写失败测试。** `test_get_is_read_only`；`test_publish_only_changes_switch_and_audit` 核对旧配置 active/草稿/版本逐字节不变；`test_concurrent_publish_conflicts`；`test_duplicate_active_rows_fail_closed`；`test_enable_validates_active_not_draft` 核对人格锚/凭据失败零写入而关闭不读草稿；`test_switch_routes_enforce_roles_and_strict_body` 覆盖五角色与不合法 Body。
- [ ] **Step 2: 运行红灯。** `docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" backend pytest -q tests/test_realtime_voice_master_switch_api.py tests/test_step028_admin_route_audit.py tests/test_step039_observer_backend_gate.py`；预期新接口测试失败。
- [ ] **Step 3: 实现服务与路由。** POST 锁定独立 active 行并核对 `expected_version`，开启时只读核验 active 语音整包、人格锚和必需凭据；一次事务写新 active 版本及脱敏操作日志后提交。GET 与运行时只认 MySQL 权威值，不使用可能滞后的 Redis 开关缓存。
- [ ] **Step 4: 重跑同一测试，预期通过。**
- [ ] **Step 5: 仅暂存本任务文件并提交** `feat: publish voice master switch independently`。

### Task 3: 运行时准入与快照

**Files:**
- Modify: `backend/services/realtime_voice_runtime_config_service.py`（读取、精确校验独立键；`VoiceRuntimeBundle` 持有开关状态/版本；新通话快照记录该状态）
- Modify: `backend/services/realtime_voice_create_service.py`（关闭原因优先使用独立状态）
- Modify: `tests/test_realtime_voice_step006_runtime_loader.py`、`tests/test_realtime_voice_step010_create.py`（现有 fixture 增加独立键）
- Create: `tests/test_realtime_voice_master_switch_runtime.py`

**Interfaces:** `_MysqlContext` 增加独立 active 行；`VoiceRuntimeBundle.master_switch_enabled: bool | None = None`、`master_switch_version: int | None = None`，直接构造 bundle 的既有测试显式传入状态。`should_block_new_call(user_id)` 先拒绝非 `True` 的独立状态，再检查维护、软停和灰度。快照顶层增加 `master_switch_enabled`、`master_switch_version`，不改 `resolved_config` 或原内容摘要。

- [ ] **Step 1: 写失败测试。** `test_master_switch_overrides_legacy_enabled_only` 覆盖旧值反向组合及维护/软停/灰度；`test_missing_invalid_or_unavailable_switch_blocks` 覆盖 DB 故障与发布锚；`test_new_call_snapshot_records_switch_version`；`test_existing_call_not_interrupted`。
- [ ] **Step 2: 运行红灯。** `docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" backend pytest -q tests/test_realtime_voice_master_switch_runtime.py`；预期旧门禁行为导致失败。
- [ ] **Step 3: 实现读取和门禁。** 在当前 MySQL 上下文查询中纳入独立键，精确验证 `{"enabled": bool}`、active/版本/时间；失败关闭。可信 fallback 只消费旧全局字段中的维护、软停、灰度，不消费旧 enabled。创建链路优先报 `disabled`，其他原因保持原语义。
- [ ] **Step 4: 运行 `docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" backend pytest -q tests/test_realtime_voice_master_switch_runtime.py tests/test_realtime_voice_step006_runtime_loader.py tests/test_realtime_voice_step010_create.py`，预期通过。**
- [ ] **Step 5: 仅暂存本任务文件并提交** `feat: gate new voice calls on master switch`。

### Task 4: 旧配置页退出总开关控制

**Files:**
- Modify: `admin/pages/voice-config.html`（移除总开关卡片和专属样式）
- Modify: `admin/static/js/voice-config-admin.js`（移除原开关逻辑；global JSON 不展示 `enabled`，保存时补回原草稿值）
- Modify: `backend/services/realtime_voice_config_service.py`（`_save_draft_section_checked` 拒绝新修改旧 `global.enabled`）
- Modify: `tests/test_realtime_voice_step005_config_control.py`
- Modify: `tests/test_realtime_voice_global_switch_browser.cjs`（迁移为“旧页无开关、其他 global 字段可保存”的回归）

**Interfaces:** 普通 `global` PATCH 仍提交完整合法对象，但 `enabled` 必须等于当前所基于的 active/草稿值；历史草稿和配置回滚不写 `voice_call_master_switch`。旧 JSON 编辑区继续编辑 `maintenance_mode`、`soft_stop`、`rollout` 等字段。

- [ ] **Step 1: 写失败测试。** `test_legacy_enabled_cannot_be_saved`、`test_legacy_draft_publish_and_rollback_leave_switch_unchanged`；浏览器断言旧页无开关、global JSON 不显示 `enabled`，其他字段仍可保存。
- [ ] **Step 2: 运行红灯。** `docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" backend pytest -q tests/test_realtime_voice_step005_config_control.py -k 'legacy_enabled or legacy_draft'`，再运行旧页 Playwright 脚本；预期旧入口仍存在。
- [ ] **Step 3: 删除旧卡片/事件并实现服务端字段保护。** UI 保存 global 时从当前选中草稿补回旧 enabled，并提示“总开关在独立页面”；不修改别的字段或当前草稿修订规则。
- [ ] **Step 4: 重跑上述 pytest、`tests/test_realtime_voice_global_switch_browser.cjs` 和 `tests/test_realtime_voice_config_conflict_browser.cjs`，预期通过。**
- [ ] **Step 5: 仅暂存本任务文件并提交** `refactor: remove legacy voice switch control`。

### Task 5: 独立页面、导航与确认交互

**Files:**
- Create: `admin/pages/voice-master-switch.html`
- Create: `admin/static/js/voice-master-switch-admin.js`
- Modify: `admin/static/js/admin-api.js`（五角色菜单增加“总开关”，语音分组识别新页面）
- Modify: 附录列出的 39 个 `admin/pages/*.html`（统一更新静态脚本 SHA12 查询参数，避免旧菜单缓存）
- Modify: `tests/test_realtime_voice_global_switch_browser.cjs`（独立页浏览器行为）
- Modify: `tests/test_step040_admin_page_inventory.py`（新页面清单与角色）

**Interfaces:** 页面仅 GET/POST Task 2 的 API。点击开关立刻恢复当前视觉状态，弹窗只有取消/确认；确认期间禁重复操作；POST 成功后重新 GET 才改变视觉状态。只读角色看状态但不能提交。

- [ ] **Step 1: 写失败浏览器测试。** 取消零写入；确认一次 POST、无配置草稿请求；失败与响应丢失时重新 GET 后显示权威状态且错误紧邻开关；409 显示最新状态；重复点击只发一次；最后操作信息、五角色权限、新菜单角标及旧配置页无开关。
- [ ] **Step 2: 运行红灯。** `NODE_PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules /Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_realtime_voice_global_switch_browser.cjs`；预期新页面或元素缺失。
- [ ] **Step 3: 实现独立页与菜单。** 使用后台已有 `adminRequest`、`renderSidebar`、`renderHeader`；不复用旧配置页的草稿发布按钮；计算新的 `admin-api.js` SHA12 并更新引用它的页面。
- [ ] **Step 4: 重跑浏览器脚本、`docker compose run --rm --no-deps -v "$PWD/backend:/app/backend:ro" -v "$PWD/tests:/app/tests:ro" -v "$PWD/admin:/app/admin:ro" backend pytest -q tests/test_step040_admin_page_inventory.py`，再运行 `node --check` 检查新增 JS；预期通过。**
- [ ] **Step 5: 仅暂存本任务文件并提交** `feat: add standalone voice switch page`。

### Task 6: 集成验证与本地 Docker 更新

**Files:** 无产品文件；仅在前述测试真实失败时修改对应任务文件并重新验证。

**Interfaces:** 依赖 Tasks 1–5 的迁移、API、运行时和页面均已通过各自测试。

- [ ] **Step 1: 运行受影响回归。** Docker pytest 覆盖 `test_realtime_voice_master_switch_{migration,api,runtime}.py`、`test_realtime_voice_step005_config_control.py`、`test_realtime_voice_step006_runtime_loader.py`、`test_realtime_voice_step010_create.py`、`test_step028_admin_route_audit.py`、`test_step039_observer_backend_gate.py`、`test_step040_admin_page_inventory.py`；Playwright 运行 `test_realtime_voice_global_switch_browser.cjs` 与 `test_realtime_voice_config_conflict_browser.cjs`。全部通过，且测试断言其他配置草稿内容/修订号不变。
- [ ] **Step 2: 记录迁移前本地 active 开关值和相关草稿版本，并备份本地数据库。**
- [ ] **Step 3: 构建新 backend 镜像。** 构建失败时使用已验证的最小构建上下文，避免 AppleDouble 文件进入镜像。
- [ ] **Step 4: 使用新镜像执行 `docker compose run --rm --no-deps backend alembic upgrade head`。** 核对独立键初值等于迁移前生效值，旧草稿未变。
- [ ] **Step 5: 执行 `docker compose up -d backend`。** 只读检查新 API 路由、管理页面与容器健康；不主动切换真实开关。
- [ ] **Step 6: 最终核对。** 旧语音设置页无开关、新页有且状态等于迁移前生效值；运行时无未处理异常。记录迁移版本、测试输出、镜像和残余风险。

## 附录：Task 5 缓存版本涉及的现有页面

以下页面目前都直接引用 `admin-api.js?v=3efd5f3d5927`；只改这条脚本的查询参数，保留各页其他内容：

```text
admin/pages/accounts.html
admin/pages/agent-aware.html
admin/pages/agent-rules.html
admin/pages/chat-prompt-agent.html
admin/pages/chat-prompt-step15.html
admin/pages/chat-prompt-step3.html
admin/pages/chat-prompt-step8.html
admin/pages/dashboard.html
admin/pages/data-report.html
admin/pages/diary-history.html
admin/pages/diary-rules.html
admin/pages/feed-comments.html
admin/pages/feed-posts.html
admin/pages/knowledge.html
admin/pages/life-feed-global.html
admin/pages/life-feed-prompts.html
admin/pages/life-feed-system.html
admin/pages/life-plan.html
admin/pages/login.html
admin/pages/memory-rules.html
admin/pages/operation-logs.html
admin/pages/persona.html
admin/pages/prompt.html
admin/pages/relationship-rules.html
admin/pages/safety-rules.html
admin/pages/step5-5-switch.html
admin/pages/system-logs.html
admin/pages/system-monitor.html
admin/pages/test-tool.html
admin/pages/third-party.html
admin/pages/user-detail.html
admin/pages/users.html
admin/pages/vector-token-config.html
admin/pages/voice-calls.html
admin/pages/voice-config.html
admin/pages/voice-crisis.html
admin/pages/voice-jobs.html
admin/pages/voice-metrics.html
admin/pages/worldview.html
```
