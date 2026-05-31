# S4 手工回归清单（H5 `chat.html`）

> **2026-05-11 勘误**：现网 **无全局 `sending`**；`send` 与叹号 **`resend`** 共用 **`lastSendOrResendAt` + `CHAT_SEND_DEBOUNCE_MS`（300ms）**（通过内容非空与 **`countOpenPendingUsers`** 后、**`fetch` 前**打点）；**`compositionend` / `keyup`** 须能刷新发送按钮（中文 IME）。**防串台** 仍以 **`AbortController` + `chatSendSession` 递增 + `meta.generation_id`** 为准；**`removeAiInFlightRows`**；`failed` / `obsolete` 移除进行中 AI；`send` 失败时 user 行 `failed_*` + 叹号。  
> **背景（已实现）**：与上勘误一致；历史文档中 **N2/N3 解锁 `sending`** 的表述 **已废弃**，以 **`docs/contract.md` → `POST /api/chat/send`「H5 实现说明」** 为准。  
> **契约口径**：`docs/contract.md` — `POST /api/chat/send`、`POST /api/chat/resend`、SSE 事件、`H5 实现说明（流中再发）`。  
> **环境**：测试账号、`/pages/chat.html`、DevTools（Network / EventStream / Console）。

---

## S4 手工回归清单

### 场景 1：连发（首条 `meta` 到达后再发第二条 · 推荐路径）

**操作步骤**

- 发送第一条消息 msg1，在 Network 的 EventStream（或响应流）中确认已收到 SSE `data:` 行，且 JSON 为 `"type":"meta"` 且含非空字符串 `generation_id`（N3）。
- 在 **已收到上述 `meta` 之后**（同轮回复仍可处于 `delta` 流式中），**间隔 ≥300ms** 输入 msg2 并点击发送（避免命中 **`CHAT_SEND_DEBOUNCE_MS`** 静默防抖）。

**预期结果**

- msg2 **正常入队**：出现新的 user 气泡，并发起新的 `POST /api/chat/send`；前一条 SSE 连接被 **Abort**；DOM 中**至多一条** `.msg-row.ai[data-ai-in-flight="1"]`；与当前 `meta` 不一致的 `delta` 不写入当前气泡。

**失败判定**

- `meta` 已到达后仍无法发出 msg2；或出现多条进行中 AI 行；或旧代 `delta` 串入新气泡正文。

---

### 场景 2：首包慢（`meta` 未到达前尝试第二条）

**操作步骤**

- 使用 DevTools **Slow 3G**（或等价限速），发送 msg1，使响应已进入 SSE 但**尚未**出现含 `generation_id` 的 `"type":"meta"`。
- **子用例 A**：在该窗口内 **300ms 内** 连点发送 msg2 — 应被 **防抖静默丢弃**（无第二条 `fetch`、无第二条 user 气泡）。  
- **子用例 B**：**停 ≥300ms** 后再点发送 msg2 — 应 **发起**第二条 `POST /api/chat/send`，前一条连接 **canceled/aborted**；若此时已有 **叹号** 且测试 **resend**，同样须 **间隔 ≥300ms** 再点（与 `send` 共用防抖）。

**预期结果**

- **不再**存在「等 `meta` 才解锁 `sending`」导致 **第二条永久发不出**；卡顿仅可能来自 **300ms 防抖**（有意设计）或 **`pending≥5`** 等既有规则。

**失败判定**

- **`meta` 迟到** 场景下，**已间隔 ≥300ms** 仍完全无法发起第二条 `fetch`（且非 10104 / pending 等业务拦截）；或 IME composition 结束后发送钮仍永久灰掉不可用。

---

### 场景 3：打断（`Abort` + `chatSendSession` 递增）

**操作步骤**

- 发送 msg1，待 **N3 `meta` 已返回**（或流式进行中任意时刻），**间隔 ≥300ms** 后再发 msg2（或等价「发送中再次触发发送」的操作）。
- 在 Network 中记录：第二次 `POST /api/chat/send` 发起前后，前一次 fetch 状态为 **canceled / aborted**；必要时在 Console 临时打印或断点确认 `chatSendSession` 在新 `send` 前已递增，且已执行 `removeAiInFlightRows()`。

**预期结果**

- 旧进行中 AI 行被移除；仅保留与当前代相关的思考/回复气泡；过期 SSE 不再驱动当前 UI。

**失败判定**

- 打断后仍残留 `data-ai-in-flight="1"` 的旧 AI 行；或旧连接仍在更新当前可见 AI 气泡。

---

### 场景 4：满 5 条（防抖边界 — 第 5 条须正常打包发出）

**操作步骤**

- 在无叹号、未触发「待处理过多」拦截的前提下，**连续快速发送 5 条**短消息（尽量落在前端允许的 `pending<5` 窗口内逐条发出，或配合慢速网络使 5 条均在 assistant 闭环前保持为 `pending_llm`）。
- 观察 Network：5 次 `POST /api/chat/send` 均返回 **可进入 SSE**（或业务上可接受的 200 流），**第 5 条**不因防抖逻辑被静默丢弃；时间线或 UI 上可见 **5 条 user** 均曾进入未闭环队列并最终由后端打包调度处理（以服务端日志或最终 assistant 覆盖范围为准，**不测**状态机内部实现细节）。

**预期结果**

- 第 1～5 条 user 均能落库并入队；第 5 条与前面几条同属「可打包窗口」语义下**正常发出**，无「仅前 4 条有响应、第 5 条无故消失」类现象。

**失败判定**

- 第 5 条无对应 user 行、无请求或明显丢失；或第 5 条在无失败态下被错误拒绝且无与 10104 等一致的产品说明。

---

### 场景 5：叹号破 5 — `resend` 限流与幂等

**操作步骤**

- 构造 **5 条**未闭环 user 后，将至少一条置为 `failed_*`（出现叹号），使 `hasBang === true`，再发 **第 6 条**新内容，确认 **允许发送**（叹号破 5）。
- 对同一失败 user 在 **1 分钟内**连续点击叹号触发 **第 3 次** `POST /api/chat/resend`，记录响应体 `code`（应为 **10105** `ERR_CHAT_RESEND_LIMIT` 或项目统一错误展示）。
- **幂等**：使用**完全相同**的 `client_resend_id` 与 Header `Idempotency-Key` 连续提交两次**合法** `resend`，第二次应命中 **10106**（`ERR_CHAT_IDEMPOTENT_REPLAY`）或契约约定的重放语义，**无**重复调度副作用。

**预期结果**

- 破 5、限流、幂等与 `docs/contract.md`、`backend/constants.py`（10104–10106）一致。

**失败判定**

- 有叹号时第 6 条仍被前端拦截；第 3 次重发无 10105；同一幂等键两次产生不一致的副作用。

---

### 场景 6：SSE `failed` 与超时 `Abort`（叹号落在对应 user 行）

**操作步骤**

- **SSE `failed`**：触发服务端返回 SSE，JSON 含 `"type":"failed"`（含 `code`/`message`）。确认进行中 AI 行被移除，对应 **send** 的 user 行变为 `failed_timeout`（message 含「超时」）或 `failed_error`，并出现叹号按钮。
- **超时 `Abort`**：发送一条消息后保持 **长时间无正常结束**（断网或卡死），直至浏览器抛出 **`AbortError`**（当前实现为 `setTimeout` **120s** / `CHAT_CLIENT_ABORT_MS = 120000` 触发 `abort`，服务端 LLM 超时为 45s — 见文末「已知边界」）。确认进行中 AI 移除，且仅当 `sessionAtStart === chatSendSession` 时，该条 user 标为 `failed_timeout` 并出现叹号；若期间已发起新 `send` 导致 session 变化，则**不应**误标被取代的旧 user。

**预期结果**

- `failed` 与超时路径均：**进行中 AI 无残留**；叹号在**对应** user 行上。

**失败判定**

- 事件后仍有 `data-ai-in-flight="1"`；`failed` 未给对应 user 补叹号；超时后 **输入区/发送流程假死**；误标非当前轮 user。

---

### 场景 7：401 登出（token 失效）

**操作步骤**

- 将 `localStorage` 中 token 改为无效值（或等待过期），触发 `POST /api/chat/send` 或 `POST /api/chat/resend`，使服务端返回 **HTTP 401**。
- 若 401 发生在 **SSE 已建立**之后，观察连接断开后的 UI 与后续跳转。

**预期结果**

- 移除进行中 AI 气泡；`send` 路径下移除本乐观插入的 user 行；调用 `clearToken()` 并跳转 `/pages/login.html`；UI 与 **`chatSendSession`** 一致、无脏状态。行为与 `docs/contract.md` 及当前 `chat.html` 一致。

**失败判定**

- 未清 token、未跳登录页；或 401 后残留与契约/实现不符的脏状态。

---

## 已知边界 & 不测项

- **不回归**：后端 `chat` 状态机「从零实现」、防抖/打包/代作废/10104 等**服务端语义**的单元证明（仅做 H5 可观测验收）。
- **不测**：管理端 **代用户重发**（**L1**：未实现，不应存在 `/api/admin/` 代触发 `POST /api/chat/resend`）。
- **已知边界**：H5 客户端 `send`/`resend` 的 **`AbortController` 超时为 120s**（`CHAT_CLIENT_ABORT_MS = 120000` ms），与契约中聊天链路 **LLM 45s** 非同一数字；验收超时叹号以 **客户端实际触发为准**，并理解服务端可能先超时失败。
- **（补充）**：无叹号时 **第 6 条** user 由 H5 `pending>=5 && !hasBang` 拦截，与 **10104** 互补；若需验 10104 请用 API 工具绕过前端，本清单不强制。

---

## 契约对齐问题清单（可选登记）

若回归中发现契约正文与端上行为不一致，在此追加：


| 编号  | 描述   | 状态  |
| --- | ---- | --- |
|     | （暂无） |     |
