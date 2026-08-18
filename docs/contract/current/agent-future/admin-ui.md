# Agent Future Admin

- 文档 ID：`contract-agent-future-admin`
- 权威状态：`canonical`
- 功能范围：`agent-future`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-004`, `TD-015`

### `admin/pages/agent-rules.html`（Agent配置）

- **实现状态**：已实现。`activeKey='agent'`，顶栏标题「Agent配置」。`super_admin` / `ai_trainer` 可配置，`observer` 仅读 Agent 规则。
- **内存状态（切 Tab 不丢未保存编辑）**：`gTriggersData`、`gDecisionData`、`gMessageRulesData`、`p3Keywords` 四份独立对象；**PUT Body 以当前两 Tab 表单为准**（见下），成功后内存与已提交内容对齐。
- **首屏并行加载**（`DOMContentLoaded`，`adminRequest` + `silentErrorToast` 以便合并失败提示）：`GET /api/admin/agent-rules`、`GET /api/admin/agent-message-rules`、`GET /api/admin/agent-night-keywords`；`#agent-page-wrap.is-loading` 期间 `.agent-disable-while-load` 禁用操作。`data===null` 或缺字段时用与 `agent_service.py` 默认值一致的表单基线（如 P1 沉默天数 3、最少对话 10 轮等）。
- **Tab**：`initTabs('main-tabs')` — 触发条件（`#tab-triggers`）| 决策引擎 & 消息规则（`#tab-decision`）。
- **PUT `/api/admin/agent-rules`**：Body **必须**同时包含 `triggers` 与 `decision_engine`（与 `AgentRulesRequest` 一致）。「保存触发规则」与「保存决策配置」两次请求中，**`triggers` 均来自 `readTriggersFromForm()`**、**`decision_engine` 均来自 `readDecisionFromForm()`**（另一 Tab 隐藏时 DOM 仍可读），避免只改一侧却在另一侧保存时用旧 `gTriggersData`/`gDecisionData` 覆盖服务端；成功后回写 `gTriggersData`、`gDecisionData` 与 Body 一致。
- **P2**：`habit_days_threshold` 前端限制为 **5～当前 `accumulation_days`**，与 `agent_mgmt.py` 校验一致（`accumulation_days` 7–30）。
- **P3 凌晨关键词**：独立接口 **`GET`/`PUT /api/admin/agent-night-keywords`**，Body / 响应 `data.keywords` 为 `string[]`；`NightKeywordsRequest` 要求至少 1 个关键词。**「保存触发规则」**：始终 `PUT agent-rules`；仅当 `p3Keywords.length >= 1` 时并行 `PUT agent-night-keywords`；若关键词为空，仍提示触发规则保存成功，并 **Toast 警告** 未调用关键词保存（避免与服务端 `min_length=1` 冲突）。标签删除用 `indexOf`+`splice` 后 `renderP3Tags()`。
- **agent-message-rules**：**`GET /api/admin/agent-message-rules`** 成功时 `data` 为以 `P0`…`P4` 为 key 的对象，元素含 `generation_requirements`、`examples`、`max_length`。消息规则子卡片：`examples` 至少 3 条输入框，不足补空；删除钮仅当行数 &gt; 3 时显示；最多 5 条示例。**「保存决策配置」**：先 `PUT agent-rules`；
  - 再对校验通过的类型 **按 P0→P4 串行** **`PUT /api/admin/agent-message-rules/{type}`**（避免后端整包读-改-写时并行请求互相覆盖），Body `generation_requirements`、`examples`（trim 后非空，3–5 条）、`max_length`（**必填**，20–100）；某类型示例 &lt; 3 或长度非法则 **跳过该类型** 并 Toast，其余仍提交；部分失败 Toast「部分配置保存失败，请检查」。**「保存决策配置」**前同样执行 P2 习惯门槛校验（与「保存触发规则」一致）。
- **运行时说明**：`triggers` / `decision_engine` 持久化后 **当前 `AgentService` 仍未读取**（与后台配置易不一致），见 **`docs/tech-debt.md` [TD-004]**；**P3 关键词**经 Redis `agent:night_keywords` 已接入运行时。
