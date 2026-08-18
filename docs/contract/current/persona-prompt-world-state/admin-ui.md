# Persona Admin

- 文档 ID：`contract-persona-admin`
- 权威状态：`canonical`
- 功能范围：`persona-prompt-world-state`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-002`, `TD-003`, `TD-020`, `TD-021`

### `admin/pages/persona.html`（AI人格管理）

- **实现状态**：已实现。布局左 55% 编辑区、右 45% 版本历史；`activeKey='persona'`，标题「AI人格管理」。`super_admin` / `ai_trainer` 可编辑，`observer` 仅读人格、历史和版本内容。
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

### `admin/pages/prompt.html`（Prompt 管理 · Step5 / Step5.5）

- **实现状态**：已实现（STEP-026；2026-07-13 侧栏收入「对话流 Prompt」）。Query **`?tab=step5`**（默认）| **`?tab=step55`** 控制首屏主 Tab 与侧栏高亮（`cp-step5` / `cp-step55`）。顶栏标题随 Tab：「Step5 主对话」/「Step5.5 润色」。`super_admin` / `ai_trainer` 可编辑，`observer` 可读但不可草稿、测试、发布、回滚或删除。
- **主 Tab**：**Step5 System**（整段 `textarea`，对应 `GET|PUT /api/admin/prompt/step5/draft`，配置键 **`step5_system_prompt`**）| **Step5.5 片段**（六个子 Tab：`system`、`style_rules`、`ctx_readonly`、`relation_brief`、`history_brief`、`messages_input`，对应 `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`）。
- **首屏加载**：`GET /api/admin/prompt/step5`、`GET /api/admin/prompt/step5-5/fragments`；草稿优先：`GET .../step5/draft`、`GET .../step5-5/draft` 与生效内容合并后填入编辑区。
- **保存草稿**：Step5 — `PUT /api/admin/prompt/step5/draft`；Step5.5 — `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`（仅当前子 Tab）。
- **丢弃草稿**：`DELETE /api/admin/prompt/step5/draft`、`DELETE /api/admin/prompt/step5-5/draft`。
- **在线测试**：Modal；`POST /api/admin/prompt/test`，Body 含 `use_draft`（为 `true` 时使用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致；成功展示 `ai_reply`（messages 合并）、人格匹配条、内容安全、`full_prompt` 折叠区。
- **testPassed**：每次「开始测试」前置 `false`；**成功**且 `ai_reply` 去空白非空 → `true`，用于解锁 **发布 Step5** 与 **发布 Step5.5**；编辑任意 textarea / 切换草稿语义变更时应重新测试。
- **发布**：`POST /api/admin/prompt/step5/publish` / `POST /api/admin/prompt/step5-5/publish`，Body `confirm_text:'CONFIRM'`、`test_passed:true`（须先在线测试通过）。
- **版本历史**：两块独立列表 — **`GET /api/admin/prompt/step5/history`** 与 **`GET /api/admin/prompt/step5-5/history`**；查看 `GET .../history/{version}`；回滚 `POST .../rollback` + `CONFIRM`。

### `admin/pages/step5-5-switch.html`（Step5.5 总开关）

- **实现状态**：已实现（STEP-026）。侧栏 **`activeKey='cp-step55-switch'`**（归入「对话流 Prompt」分组；旧 key `step55switch` 仍可兼容高亮）。`super_admin` / `ai_trainer` 可发布，`observer` 仅读当前状态。
- **接口**：`GET /api/admin/prompt/step5-5-switch`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ enabled }`；`DELETE .../draft`；`POST .../publish`（**不要求**先跑主链 LLM 测试，仅需确认 **`CONFIRM`**）；`GET .../history`、`POST .../rollback`。配置键 **`step5_5_enabled`**（与 STEP-009 运行时读取一致）。

### 对话流 Prompt 只读页（`admin/pages/chat-prompt-*.html`）

- **实现状态**：已实现（2026-07-13）。侧栏分组 **`CHAT_PROMPT_MENU`**（`super_admin` / `ai_trainer`）；一级菜单**不再**单独列出「Prompt管理 / Step5.5开关 / 记忆规则」。
- **子项与落页**：

| 菜单 key | 展示名 | 页面 / 行为 |
|----------|--------|-------------|
| cp-step15 | Step1.5 查询重写 | `chat-prompt-step15.html`（只读，`GET .../chat-prompt-view/step15`） |
| cp-step3 | Step3 Prompt 拼装 | `chat-prompt-step3.html`（只读，`GET .../step3`） |
| cp-step5 | Step5 主对话 | `prompt.html?tab=step5`（可编辑） |
| cp-step55 | Step5.5 润色 | `prompt.html?tab=step55`（可编辑） |
| cp-step55-switch | Step5.5 开关 | `step5-5-switch.html`（可配置） |
| cp-step6 | Step6 记忆拆解 | `memory-rules.html?nav=cp-step6`（可编辑；`activeKey=cp-step6`） |
| cp-step8 | Step8 Future 主动 | `chat-prompt-step8.html`（只读） |
| cp-agent | Agent 主动 P0～P4 | `chat-prompt-agent.html`（只读；与 Step8 独立） |

- **样式**：分组标题与一级 `.menu-item` 同为 **14px**；二级 `.menu-sub` **14px**、`padding-left: 56px`。

### `admin/pages/test-tool.html`（AI测试工具）

- **实现状态**：已实现。主布局 **grid 40% : 60%**（`gap:16px`）；左侧自上而下：`测试参数配置` 卡片、`最近测试记录` 卡片（`margin-top:16px`）；右侧 `测试结果` 卡片。`activeKey='test'`，顶栏标题「AI测试工具」。`super_admin` / `ai_trainer` 可测试与保存，`observer` 仅可读配置和历史结果。样式入口：`admin-common.css` + 页内 `<style>`。
- **测试参数**：`使用配置` 单选——当前生效（`use_draft:false`）/ 草稿（`use_draft:true`）；关系等级、用户情绪；模拟记忆 `textarea`（按换行计非空行数，展示「已输入 n/5 条」，n>5 时 `.alert-warning`）；测试输入必填。
- **开始测试**：校验测试输入非空；`POST /api/admin/prompt/test`，Body 与 `PromptTestRequest` 一致（`mock_memories` 取前 5 条非空行）。服务端拼装与线上一致：**`PromptBuilder.build_chat_prompt`**（STEP-026）；`use_draft:true` 时使用 **`step5_system_prompt`** 草稿作为模块1。成功：右侧淡入展示 AI 气泡（头像「梦」）、人格匹配总分+等级 Tag、三维进度条（40%/40%/20%）、内容安全区块、`full_prompt` 折叠区（Token 数 `Math.ceil(full_prompt.length * 1.5)`）；底部「保存为测试用例」可用。
- **测试历史**：`localStorage` key=`admin_test_history`，最多 10 条，项含 `time`（ISO）、`test_input`、`use_draft`、`relationship_level`、`emotion_label`、`mock_memories`。点击行回填左侧表单；「清空」经 `showConfirm` 后清除并重绘。
- **保存测试用例**：Modal（宽约 480px）填写 `expected_pass_criteria`；`POST /api/admin/test-cases/persona`，Body 使用最近一次**成功**测试快照中的 `test_input`→`input`、`emotion_label`、`relationship_level` 及弹窗中的期望标准。成功 Toast「已保存为测试用例」并关闭 Modal。

### `admin/pages/safety-rules.html`（内容安全规则）

- **实现状态**：已实现。`activeKey='safety'`，顶栏标题「内容安全规则」。`super_admin` / `ai_trainer` 可修改，`observer` 仅读规则。
- **首屏**：`GET /api/admin/safety-rules`，将 `banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords` 写入**三个可变的同一数组引用**（加载时原地 `replaceInPlace`，避免 Enter 添加与刷新后闭包指向旧数组）。
- **Tab**：`initTabs('safety-tabs')` — 违规关键词 | 人格禁区关键词 | 语言风格禁忌词。
- **标签云**：`min-height:120px` + `border:1px solid var(--border)` 容器；词条为 `span.safety-kw-tag`，`×` 仅从本地数组 `splice` 并重新渲染，**不立即请求**。
- **输入**：各 Tab `input` 宽 240px，`Enter` → `trim` 后非空且不重复则 `push` 并清空输入框。
- **保存**：对应 **PUT** `/api/admin/safety-rules/banned-keywords`、`.../persona-keywords`、`.../style-keywords`，Body `{ keywords }`；若当前数组为空则前端 Toast 提示（与后端 **`keywords` 至少 1 项** 一致），成功 Toast「保存成功」。
- **违禁词 Tab**：「批量导入 Excel」触发隐藏 `file`，`accept=".xlsx,.xls"`；`FormData` 字段名 **`file`** + `adminRequest('POST','/api/admin/safety-rules/banned-keywords/import', formData, true)`；成功 Toast「成功导入{imported_count}个关键词，当前共{total_count}个」并 **GET 刷新**。
- **首屏竞态**：首次 `GET /api/admin/safety-rules` 请求期间禁用三个输入框、三个「保存更新」与「批量导入 Excel」；待响应返回且（若成功）已 `replaceInPlace` + `renderAllClouds` 后再解除 `is-loading` 并启用控件（失败时仍启用，避免永久锁死）。
- **导入与未保存**：维护 `lastSyncedSnapshot`（成功 GET 或任意一次保存成功后对三数组的 `JSON.stringify`）；`isDirty()` 为真时点「批量导入 Excel」先 `showConfirm`（文案：将重新加载全部关键词，未保存的修改会丢失…），确认后再打开文件选择；取消则不发起导入。

### `admin/pages/knowledge.html`（角色知识库）

- **实现状态**：已实现。`activeKey='knowledge'`，顶栏标题「角色知识库」。`super_admin` / `ai_trainer` 可 CRUD，`observer` 仅可查询、筛选和分页。
- **Demo 区**：`.ck-demo-card` 固定展示 type / **三层 key** / value 示例与全角冒号格式说明；注明 `character_private` 不在此页维护。
- **列表**：`GET /api/admin/character-knowledge`；筛选 `type` + `keyword`（Enter 或点查询）；分页上一页/下一页；表格列 type（标签）、key（来自 `stable_key` 或 content）、value（截断 + `title` 全文）、编辑/删除。
- **新增**：Modal — type 下拉、**三层 key**（前端 `validateKeyFormat` 预检）、`value`；`POST` Body `{ type, key, value }`。
- **编辑**：`key` 与 type **只读**（`#ck-modal-key[readonly]`，隐藏 type 行）；仅改 `value`；`PUT /api/admin/character-knowledge/{encodeURIComponent(doc_id)}`。
- **删除**：`showConfirm(..., { danger: true })` 后 `DELETE` 同上路径。
