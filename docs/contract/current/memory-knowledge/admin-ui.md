# Memory Knowledge Admin

- 文档 ID：`contract-memory-knowledge-admin`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### `admin/pages/memory-rules.html`（Step6 记忆拆解 / 原记忆规则页）

- **实现状态**：已实现。侧栏入口归入 **「对话流 Prompt → Step6 记忆拆解」**（`activeKey='cp-step6'`）；**一级菜单不再展示「记忆规则」**。顶栏标题仍可为「记忆规则配置」（页内文案未改业务逻辑）。`super_admin` / `ai_trainer` 可配置，`observer` 仅读 Step6 Prompt、全局记忆和非敏感 DashVector 参数。
- **布局**：顶部 **Tab 标签行**单独一块 `.page-card`（`memory-tab-header-card`），**每个 Tab 内容区**各包一层 `.page-card` 作为表单容器；外层 `#memory-page-wrap` 仅承担 `is-loading`，不再使用单一大卡片包全页。
- **Tab**（长记忆第一套下线改造，§6.6.3/§6.4.3）：`initTabs('memory-tabs')` — **Step6 记忆 Prompt（默认）** | 向量数据库配置 | **全局用户记忆**。**默认 Tab 为 Step6 记忆 Prompt**；旧「记忆规则」Tab（记忆提取 Prompt / 重要性评分 / 存储阈值 / 检索合并阈值）与 `memory-rules` GET/PUT 调用**已删除**（C-04/C-08，不展示历史 `memory_rules`）。
- **Step6 记忆 Prompt Tab**：`GET /api/admin/step6-memory-prompt` 填充 6 块分区表单（`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields` 11 项按 `TASK_FIELD_NAMES` 固定顺序渲染 `textarea` / `merge_rules` / `few_shot_example`）；保存收集后 `PUT /api/admin/step6-memory-prompt`（**保存即发布**），任一文本块或任一 `task_fields` 子项为空则前端 `showToast` 拦截，成功 Toast「Step6 记忆 Prompt 已保存并发布」。
- **全局用户记忆 Tab**：`user_id`（选填 `number`）+ `keyword`（选填）+ 分页；`GET /api/admin/memories/global`，列 `用户ID/Key/Value/操作`；勾选行 + 「批量删除选中」或单行「删除」→ `DELETE /api/admin/memories/batch-delete`（Body `{doc_ids}`）；固定提示「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」（R-01），API 返回 `truncated:true` 时额外 `.alert-warning` 强化展示。
- **向量库 Tab**：`GET /api/admin/vector-db-config`；Endpoint（`type=url`）、Collection、TopK（**测连/保存须为 1–20**；`GET` 返回的 `top_k` **原样填入**（≥1），若历史上 &gt;20 则展示真实值，须改回 1–20 后再测连/保存，**不再**将非法值静默改为 5）、脱敏 Key 只读 +「修改」展开明文 `password` 输入；**点击「修改」**清空明文框并 `testPassed=false`、清空测连结果区；明文框 `input` 同样重置测试通过与结果；测试结果区 `#vector-test-result` **无内容时 `display:none`**，有结果时 `display:block`；
  - **「测试连接」**发起请求前先展示 `.alert-info`「正在测试连接…」；`POST .../test-connection` Body 对应 `VectorDbTestRequest`：**`endpoint`、`collection_name`、`api_key` 三字段均可不传或传 `null`**，未提供的项由后端从**已发布配置**或**环境变量**补全（与 `memory_mgmt.py` 一致）；本页实现为：`endpoint`/`collection_name` 常带表单当前值（空则 `null`），**仅当明文 Key 框有非空值时带 `api_key`**；成功 `.alert-success` 与延迟 ms；
  - 失败 `.alert-error`，文案优先 `data.error`，否则回退 **`ApiResponse.message`**（仍用 `textContent` 写入节点）；`code≠0` 时在结果区展示 **`message`**（该请求使用 `adminRequest(..., { silentErrorToast: true })`，避免与统一信封错误 Toast 重复）；`res` 为空（网络异常、HTTP 非 JSON 等）时 `adminRequest` 仍可能保留全局 Toast，结果区展示「请求失败」摘要。通过后启用「保存」。**「保存」**初始 `disabled`+`title="请先测试连接"`；
  - `PUT /api/admin/vector-db-config`，Body 含 `need_test_first:false`，`api_key` 仅在有新明文时传递；成功后 `testPassed=false`、禁用保存、收起明文编辑、`GET` 刷新脱敏 Key。
- **首屏加载**：`#memory-page-wrap.is-loading` 期间 `.memory-disable-while-load` 使用 `pointer-events:none` 避免未返回数据时误操作。**不**使用 `firstLoadFinished` 变量（该变量在 `safety-rules.html` 中仍用于首屏禁用控件，与本页实现无关）。
