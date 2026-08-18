# cross-cutting 技术债

- 文档 ID：`tech-debt-cross-cutting`
- 权威状态：`canonical`
- 功能范围：`cross-cutting`
- 必读依赖：无
- 相关技术债：`TD-030`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-030] 内容安全 `failed_blocked` 未纳入叹号重发窗口（H5 / Open 共用，**待清偿**）

- **位置**：`backend/services/chat_service.py` → `open_window_has_bang` / `enqueue_resend`；`POST /api/chat/resend`；`POST /api/open/v1/chat/resend`（共用同一判定链，见 **`docs/design/openapi/PRD-OpenAPI-APIKey-v1.md`** §8 **TD-NEW-02**）。
- **问题**：Step5 / Step5.5 对外 `messages[].content` 任一条内容安全不通过时，user 行标 **`delivery_status=failed_blocked`**（见 **STEP-012** / `docs/contract.md` H5 对话 send 语义）。当前叹号判定 **仅**包含 `failed_timeout`、`failed_error`，**不含** `failed_blocked`。后果：该 user 行 **无叹号 UI**（H5）、**不可** `resend`（返回 **10107** `ERR_CHAT_NOTHING_TO_RESEND`）；用户/第三方须 **重新 send 新消息**，易误判为「系统无响应」。
- **需求确认（2026-06-04）**：Open API v1 需求评审 **V4 方案 A** — **本期接受现状**，与 H5 保持一致；**不**在 Open 单独放宽 resend 规则。
- **当前处理**：
  1. 运行时逻辑 **不改**；Open `resend` 与 H5 共用 `_open_window_has_bang`（经 N5 `chat_service` 搬迁后仍须保持单点判定）。
  2. 第三方文档 **`docs/design/openapi/open-api-v1.md`** 已写明：仅 `failed_timeout` / `failed_error` 可 resend；`failed_blocked` 请 **重新 send**。
- **待处理（单独立项，H5 + Open 同期）**：
  1. 产品确认：`failed_blocked` 是否允许叹号重发（重跑 LLM 仍可能再次 blocked，价值待评估）。
  2. 若做：扩展 `_open_window_has_bang` 含 `DELIVERY_STATUS_FAILED_BLOCKED`；H5 `chat.html` 叹号展示规则对齐；Open resend 共用；更新 `docs/contract.md` 与 Open 集成文档。
  3. 若不做：可在 H5 timeline / 失败 user 行增加 **明确文案**（如「内容未通过审核，请修改后重发」），降低困惑。
- **触发时机**：用户/运营反馈 blocked 场景无法恢复；或 Open 第三方集成验收反馈 resend 语义不清时评估。
- **风险等级**：**低**（发生频率相对 timeout/error 较低；send 入队前 10101 已挡大部分输入侧违规；主要影响 **模型输出侧** blocked）
- **关联**：**TD-015**（叹号与 resend 主链）；**PRD-OpenAPI-APIKey-v1** §8 **TD-NEW-02**、§5.2 对话共用规则（C11）。
