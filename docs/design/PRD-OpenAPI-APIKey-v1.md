# 林小梦 Open API（API Key 第三方接入）PRD

> 版本：v1.9  
> 状态：需求已对齐，可进入开发  
> 涉及模块：Open API 鉴权、H5 对话主链（复用）、Agent 主动消息、管理后台用户详情、契约文档  
> 最后更新：2026-06-04

---

# 1. 功能背景

## 当前功能是什么

林小梦（LXM）现有对话能力面向 H5 用户端：用户注册登录后，通过 JWT 鉴权访问 `/api/chat/*`（SSE 流式发送）、`/api/chat/timeline`（统一时间线）、`/api/chat/resend`（失败重发）及 `/api/agent/*`（主动消息未读/已读）。对话主链包含记忆检索、关系成长、Step6 长期记忆、内容安全等完整业务。

## 当前存在的问题

- 无面向第三方客户端（如桌面宠物、其他受信软件）的 **API Key 鉴权** 与 **稳定对外契约**。
- 第三方若强行复用 H5 JWT 流程，需模拟登录、维护 Token 刷新，且 SSE 集成成本高。
- 缺少管理后台为用户签发/吊销 Key 的能力。

## 改造目标

1. 为已有 H5 账号提供 **每用户 1 个** 专属 API Key，由 **管理后台** 生成。
2. 提供 **Open API v1**（同步 JSON，**6 个接口**），使 PC 桌面等第三方接入后 **等价于嵌入一个聊天窗口**，并支持托盘角标轮询。
3. 与 H5 主流程 **数据同源、主链同用**；Open API 为 **薄 Facade 层**，契约独立版本化，H5 迭代默认不牵动 Open v1（特殊情况见边界章节）。
4. **一次性全量开发**（C-Open），不分期。

---

# 2. 方案确认决策记录

## 2.0 产品决策（C1–C17）

| 编号 | 问题 | 决策 | 状态 |
|------|------|------|------|
| C1 | API Key 绑定谁？ | **方案 A**：绑定现有 H5 用户；须先有账号；每账号 **1 个** Key；重新生成即覆盖旧 Key | ✅ 已确认 |
| C2 | LXM 与第三方的职责边界 | LXM 提供接口 + 文档；第三方按文档自行实现 UI/超时/展示；LXM 不规定宠物端技术栈 | ✅ 已确认 |
| C3 | Open API 能力范围 | **C-Open 全量（6 接口）**：send + resend + timeline + agent messages + agent read + **agent unread-count** | ✅ 已确认 |
| C4 | 是否分期 | **否**，一期全部开发 | ✅ 已确认 |
| C5 | 传输形态 | Open API **统一同步 JSON**；不提供 SSE；内部仍走现有 `_execute_llm_bundle` 等主链 | ✅ 已确认 |
| C6 | 数据存储 | 与 H5 **同一套库表**（`conversation_log`、`agent_message`、`relationship`、`memory` 等）；仅新增 Key 鉴权表 | ✅ 已确认 |
| C7 | 后台 Key 管理入口 | **方案 A**：挂在 Admin **用户详情页** | ✅ 已确认 |
| C8 | Key 可操作角色 | `super_admin` + `ops_admin` | ✅ 已确认 |
| C9 | Key 格式与存储 | 前缀 `sk-lxm-` + 随机串（≥32 字节）；库内 **`SHA-256(api_key + OPEN_API_PEPPER)`**；明文仅创建/重新生成时展示一次 | ✅ 已确认 |
| C10 | 是否支持「禁用 Key」 | **不支持单独 disable**，仅「有 Key / 无 Key」；重新生成即吊销 | ✅ 已确认 |
| C11 | Open API 限流规则 | 与 H5 **完全共用** 10104 队列、10105 重发限制、内容安全等 | ✅ 已确认 |
| C12 | 鉴权 Header 格式 | **`Authorization: Bearer <api_key>`**（见 §2.1、§10 安全约束） | ✅ 已确认 |
| C13 | 文档交付物 | `docs/design/open-api-v1.md`（含安全章节）+ 开发后更新 `docs/contract.md` | ✅ 已确认 |
| C14 | Bearer 安全风险应对 | 见 §10：路径隔离、Key 熵、哈希+pepper、防日志泄露、禁止浏览器直连等 | ✅ 已确认 |
| C15 | 测试/生产等多环境对接 | **用户自行配置 Base URL + API Key**；**每环境独立 Key**；**生产公网已确认为 `http://cllxm.com`**；测试地址不写死 | ✅ 已确认 |
| C16 | PC 托盘未读角标 | **方案 B**：纳入 `GET /api/open/v1/agent/unread-count`（轻量轮询，对齐 H5） | ✅ 已确认 |
| C17 | Open 鉴权失败响应 | **HTTP 401** + FastAPI `detail` 文案；不使用 H5 业务码 10012（Token 语义）；详见 §2.4 | ✅ 已确认 |

## 2.0.1 需求评审补充决策（N1–N9，2026-06-03）

| 编号 | 问题 | 决策 | 状态 |
|------|------|------|------|
| N1 | `OPEN_API_PEPPER` 缺失时启动策略 | **整应用拒绝启动**（`lifespan`/启动检查，缺失或为空则 `RuntimeError` 退出）；有效 pepper 长度 **≥32** | ✅ 已确认 |
| N2 | Open 等待 Future 遇 `obsolete` | 新增 **`ERR_CHAT_GENERATION_OBSOLETE = 10108`**；HTTP 200 + ApiResponse；`send`/`resend` 均适用；**message 见 V7 / §4.3** | ✅ 已确认 |
| N3 | Open 鉴权失败 401 响应格式 | **FastAPI `HTTPException` + `detail`**（与 H5/Admin 一致，非 ApiResponse 信封）；详见 §2.4 | ✅ 已确认 |
| N4 | Admin 操作日志 action | **`module="用户管理"`**；首次 **`action="create"`**；重新生成 **`action="edit"`**（`before/after` 存脱敏 `key_prefix`）；明细写 `target_description`；禁止明文 Key | ✅ 已确认 |
| N5 | 主链重构边界 | **`chat_service.py`** 提供入队前共享校验（**V9**）+ `enqueue_send` / `enqueue_resend` / `await_bundle_payload`（**写路径**）；Future 状态迁 service；**最小搬迁**（O6）；**不迁移** `_execute_llm_bundle` / `_build_round_context` 等 | ✅ 已确认 |
| N6 | Open `resend` Body | **v1 路由不声明 Body 参数**（O7）；**不暴露、不解析** `client_resend_id` | ✅ 已确认 |
| N7 | Admin 展示 Base URL | **MVP 不做**；生产地址写在 `open-api-v1.md`；`OPEN_API_PUBLIC_BASE_URL` 可在 `.env.example` 注释预留，v1 不读取 | ✅ 已确认 |
| N8 | Nginx 不记录 Authorization | **纳入验收、轻量实现**：`nginx.conf` 注释 + 部署文档抽检说明 | ✅ 已确认 |
| N9 | HTTP 明文传 Key 文档警示 | **`open-api-v1.md` 独立「传输安全」小节**（标准警示）；产品侧不拦截 HTTP 调用 | ✅ 已确认 |

## 2.0.2 架构与实现优化决策（O1–O7，2026-06-03）

| 编号 | 问题 | 决策 | 状态 |
|------|------|------|------|
| O1 | timeline / agent 读接口路径 | **`timeline_read_service`**（或等价模块）提供 `get_timeline`；H5 / Open **共用**；**不经过** `chat_service`（1-B） | ✅ 已确认 |
| O2 | `await_bundle_payload` 120s 等待 | **仅允许** `asyncio.Future` + `asyncio.wait_for`；**禁止** `threading.*.wait` / 同步 sleep（2-C） | ✅ 已确认 |
| O3 | generation **obsolete** 触发 | **`enqueue_send` / `enqueue_resend` 内**调用 `_new_generation_for_user` → `_invalidate_generation_future`；**禁止**第二套 obsolete 逻辑（3-A） | ✅ 已确认 |
| O4 | `round_id` 来源 | 从现有 Future **成功 payload** 读取；**无需**改 `_execute_llm_bundle`（R1-A） | ✅ 已确认 |
| O5 | `last_used_at` 写入频率 | 允许 **≥60s 节流** 写库；Admin 展示精度到分钟可接受（R2-B） | ✅ 已确认 |
| O6 | N5 迁移范围 | **最小搬迁**（R3-A）：仅 Future + enqueue + await；`_build_round_context` 等暂留 `chat.py`；开发前 grep 依赖（§7 STEP-0） | ✅ 已确认 |
| O7 | Open `resend` FastAPI Body | 路由 **不声明** body 参数，避免空 POST 422（R4-A） | ✅ 已确认 |

## 2.0.3 实现层确认（V1–V9，req-confirm · 2026-06-04）

| 编号 | 问题 | 决策 | 状态 |
|------|------|------|------|
| V1 | N5/O6 `chat_service` 最小搬迁边界 | Future 三件套 + `enqueue_send` / `enqueue_resend` / `await_bundle_payload` + **`_resolve_generation_future`**（供 `chat.py` 内 `_execute_llm_bundle` import）迁入 **`chat_service`**；**入队前校验** 见 **V9**（非留 router 内联复制）；**不迁** `_execute_llm_bundle`、`_build_round_context`；**禁止** `chat_service` → `routers.chat` 反向依赖；**禁止** Open `import routers.chat`（§7 STEP-0） | ✅ 已确认 |
| V2 | `OPEN_API_PEPPER` 环境策略 | **严格 N1**：缺失/空/长度 &lt;32 → 整应用拒绝启动；**测试/生产各独立 pepper**（与 C15 每环境独立 Key 配套）；写入 `DEPLOY.md` / `docs/ops/docker-admin-deploy.md`；**与 JWT 无关**（Open 不用 `JWT_SECRET`，见 §2.1.1） | ✅ 已确认 |
| V3 | Open `send`/`resend` 成功 JSON | 成功 `data`：**`{ messages, emotion, round_id }`** — `messages`/`emotion` 对齐 H5 SSE **`done`**（**`[{type, content}, …]`**，正文读 **`content`**；**不含 `text` 字段**）+ `{label, confidence}`；**不暴露** `generation_id`、`step5`、`reply`；`round_id` 从 Future payload 读取（O4）；**timeline / agent 三接口** `data` **原样复用** H5 | ✅ 已确认 |
| V4 | `failed_blocked` 不可叹号重发 | **接受现状**（与 H5 一致）：`_open_window_has_bang` 不含 `failed_blocked` → resend **10107**；`open-api-v1.md` 注明仅 `failed_timeout`/`failed_error` 可 resend；技术债见 **`docs/tech-debt.md` [TD-030]** | ✅ 已确认 |
| V5 | Key 重新生成库内实现 | **单行 UPDATE 覆盖** `key_hash`/`key_prefix`（非 DELETE+INSERT、非 soft-delete 多行）；**`created_at` 保留首次签发**；重新生成时 **`last_used_at` 置 NULL**；`created_by_admin_id` 更新为本次操作员 | ✅ 已确认 |
| V6 | Admin 操作日志 action | 严格 **N4**：首次 **`create`**，重新生成 **`edit`**（**不用** `update`）；`module="用户管理"` | ✅ 已确认 |
| V7 | `10108` 的 `message` 文案 | **`ERROR_MESSAGES[10108]`** =「回复已被新消息取代，请拉取时间线查看后再操作」；HTTP 200 + ApiResponse；`data` 为 null | ✅ 已确认 |
| V8 | `last_used_at` 节流 | **DB 侧**：鉴权成功且 `last_used_at` 为 NULL 或距现在 **≥60s** 才 UPDATE；Admin 展示精度到 **分钟**（O5） | ✅ 已确认 |
| V9 | 入队前校验抽取（内容安全 / 10104） | N5 期间将 `chat.py` 内联的 **`check_content`**、**`persona_risk` 检测**、**10104 队列检查** 抽为 **`chat_service`** 共享函数：**`check_content_safety(content)`**（空/unsafe + persona_risk 标志）、**`check_send_quota(user_id, db)`**（10104）；H5 `chat_send` 与 Open `routers/open/chat.py` **均调用**；**禁止** Open router `import routers.chat` | ✅ 已确认 |

---

## 2.1 C12 说明：第三方请求里 Key 放哪？

指：**桌面宠物/其他软件每次调 Open API 时，HTTP 请求头里怎么携带 API Key**。

常见两种写法：

| 写法 | 示例 | 说明 |
|------|------|------|
| **A. Bearer（推荐）** | `Authorization: Bearer sk-lxm-a1b2c3...` | 与 H5 的 JWT 同一请求头名，只是值换成 API Key；FastAPI `HTTPBearer` 可复用 |
| **B. 专用头** | `X-API-Key: sk-lxm-a1b2c3...` | 语义更直观，但与现有 H5 鉴权方式不同，需单独中间件 |

**已确认（C12）**：采用 **A. Bearer**；安全不依赖换头名，而依赖 **§10 路径隔离与 Key 生命周期管理**。

### 2.1.1 Open 鉴权与 JWT 环境变量区分（V2 · 2026-06-04）

| 维度 | H5 / Admin | Open API v1 |
|------|------------|-------------|
| 凭证 | JWT Token | API Key（`sk-lxm-...`） |
| 请求头 | `Authorization: Bearer <jwt>` | `Authorization: Bearer <api_key>`（**头名相同，值不同**） |
| 环境变量 | `JWT_SECRET` / `ADMIN_JWT_SECRET` | **`OPEN_API_PEPPER`**（服务端哈希 pepper，**不是** Token，不可作为 Bearer 传给接口） |
| 校验 | 验签 + 过期 | 前缀 `sk-lxm-` + `SHA-256(api_key + pepper)` 比对库内 hash |

误将 JWT 当作 Open Key 调用 `/api/open/v1/*` → **401**（S2）；误将 API Key 调用 `/api/chat/*` → JWT 路由 **401**（S1）。

## 2.2 C15：多环境怎么连？（用户自定义配置）

**不做**「环境标识接口」、**不做** Key 前缀区分环境、**不在 LXM 代码里写死测试/生产域名列表**。

第三方（桌面宠物等）在**自身设置页**提供两项可编辑配置（用户复制粘贴，与常见 SaaS 接入方式一致）：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| **服务器地址 / Base URL** | LXM 服务根地址，**不含** `/api/...` 路径 | **生产（已确认）**：`http://cllxm.com`；测试：由运维提供后用户自行填写 |
| **API Key** | 在**该环境** Admin 用户详情中生成的 Key | `sk-lxm-...` |

**拼接规则：**

```text
{Base URL 去掉末尾 /}/api/open/v1/chat/send
```

**生产环境（已确认）：**

| 项 | 值 |
|----|-----|
| 公网 Base URL | **`http://cllxm.com`** |
| Open API 示例 | `http://cllxm.com/api/open/v1/chat/send` |
| Admin（签发 Key） | `http://cllxm.com/admin` |
| API Key | 在**该生产环境** Admin → 用户详情 → 生成 |

```text
Base URL: http://cllxm.com
API Key:  sk-lxm-xxxx（在生产 Admin 用户详情中生成）

POST http://cllxm.com/api/open/v1/chat/send
Authorization: Bearer sk-lxm-xxxx
```

**每环境独立 Key（已确认）：**

- 测试库、生产库 **数据隔离**；在测试 Admin 生成的 Key **不能**用于生产 Base URL。
- 换环境 = 同时更换 **Base URL + 在该环境重新复制 Key**。

**LXM 侧交付（N7）：**

- `open-api-v1.md` 说明上述两项配置及拼接规则；**生产 Base URL 固定写 `http://cllxm.com`**；测试地址不写死，注明「向运维索取测试 Base URL」。
- Admin 用户详情 **v1 不展示** Open API 根地址；运维/第三方以集成文档为准。

**HTTPS 说明：** 当前生产公网为 **`http://cllxm.com`**（用户已确认）。若后续部署启用 HTTPS，文档改为 `https://cllxm.com`，第三方仅更新 Base URL 配置，Key 不变。传输风险说明见 §10.3 **S16** 与 `open-api-v1.md`「传输安全」章节（N9）。

## 2.3 C16：PC 桌面宠物 — 未读角标（方案 B）

**场景：** 宠物最小化到系统托盘，需周期性轮询「林小梦有没有主动消息」，不宜每次拉 `agent/messages` 全文。

**用法：**

| 场景 | 接口 |
|------|------|
| 托盘角标 / 后台轮询 | `GET /api/open/v1/agent/unread-count` → `{ count }` |
| 用户点开聊天 / 弹通知预览 | `GET agent/messages` + `timeline` |
| 已读后 | `POST agent/messages/{id}/read` |

## 2.4 C17 / N3：Open 鉴权失败 HTTP 401 响应格式

Open API 鉴权失败使用 **FastAPI `HTTPException`**，响应体为 **`{"detail":"<文案>"}`**（与 H5/Admin JWT 鉴权一致），**不是** `{ "code": 0, "data": {}, "message": "success" }` 业务信封，**不使用** H5 业务码 10012。

| 场景 | HTTP | 响应体示例 |
|------|------|------------|
| 未提供 `Authorization` | 401 | `{"detail":"未提供 API Key"}`；响应头含 `WWW-Authenticate: Bearer` |
| Key 无效 / 已吊销 / 格式错误（含非 `sk-lxm-` 前缀、误传 JWT） | 401 | `{"detail":"API Key 无效或已吊销"}`（S8：不区分原因） |
| 用户被 Admin 禁用 | 401 | `{"detail":"账号已被禁用"}` |

**说明：** API Key 用于 JWT 路由 `/api/chat/*` 时，由 JWT 鉴权拒绝（401，`detail` 为 JWT 语义文案），仍满足 S1 路径隔离验收。

---

# 3. 功能改动说明

## 改动前

- 对话仅 JWT（`get_current_user`）可访问。
- 无 `user_api_keys` 表及 Admin Key 管理 UI/API。
- 无 `/api/open/v1/*` 路由。

## 改动后

- 新增 **API Key 鉴权**（`get_current_user_by_api_key`），校验通过后得到与 JWT 相同的 `user_id`。
- 新增 **Open API v1** **六个**接口（同步 JSON 包装现有逻辑）。
- Admin **用户详情页** 增加 Open API Key 区块：生成、重新生成、脱敏展示、审计日志。
- 新增 **`docs/design/open-api-v1.md`**（或等价路径）供第三方集成；`docs/contract.md` 追加 Open API 模块。
- **`chat_service.py`** 承接 send/resend **写路径**（入队 + Future 等待）；**`timeline_read_service`** 承接 timeline **读路径**（O1）；H5 与 Open 共用。

## 核心变化汇总

| 维度 | 改动前 | 改动后 |
|------|--------|--------|
| 第三方鉴权 | 无 | API Key → user_id |
| 发消息 | 仅 JWT + SSE | JWT + SSE；Open Key + **同步 JSON** |
| 读历史 | JWT + timeline | 同上 + Open timeline |
| 数据 | — | Open 与 H5 **完全共享** |
| 架构 | 单路由域 | **写路径**：Facade → `chat_service` → 主链；**读路径**：Facade → `timeline_read_service` / agent 查询 |

---

# 4. 功能详细逻辑

## 4.1 架构（薄 Facade + 主链复用）

```
第三方客户端
    │ Authorization: Bearer sk-lxm-xxx
    ▼
/api/open/v1/*  （Open Facade：鉴权 + JSON 适配 + 稳定契约）
    │
    ├──【写路径】open_chat_service.send / resend
    │       ▼
    │   chat_service.check_content_safety / check_send_quota  （V9，入队前）
    │       ▼
    │   chat_service.enqueue_send / enqueue_resend / await_bundle_payload  （O2/O3/O6/V1）
    │       ▼
    │   _execute_llm_bundle / Step6 / 成长值 …
    │
    ├──【读路径】open_chat_service.timeline  ──►  timeline_read_service.get_timeline  （O1，不经过 chat_service）
    │
    └── open_agent_service.*  ──►  现有 agent 查询逻辑（不经过 chat_service）
    ▲
/api/chat/* （H5 JWT + SSE）
    ├── send/resend → chat_service（写路径，与 Open 共用）
    └── timeline   → timeline_read_service（读路径，与 Open 共用）
```

**职责边界（O1 / V1 / V9）：**

- **`chat_service`**：
  - **入队前共享校验（V9）**：**`check_content_safety(content)`** — 空内容（10100）、内容安全（10101）、**persona_risk 标志**（供 enqueue 写 user 行）；**`check_send_quota(user_id, db)`** — 10104 队列满判定（逻辑抽自现 `_fetch_open_window_user_rows` + `_should_block_new_send`）。
  - **写路径（V1）**：Future 运行时、generation 作废链、send/resend **入队核心**（含 user 行落库、proactive_times 清零、防抖/即时调度 `_execute_llm_bundle`）、`await_bundle_payload`；暴露 **`_resolve_generation_future`** 供 `_execute_llm_bundle` 唤醒等待方。
- **`routers/chat.py` / `routers/open/chat.py`**：路由层仅 **调用** 上述共享函数 + `enqueue_*` / SSE 或 JSON 适配；**不** 内联复制校验逻辑；**禁止** Open `import routers.chat`。
- **`routers/chat.py`**（本期另保留）：`_execute_llm_bundle` 全文、`_build_round_context`、`_sse_chat_wait_bundle`。
- **`timeline_read_service`**（或等价命名）：仅 **读路径** — 合并 `conversation_log` + `agent_message` 的 timeline 查询；由 `chat.py` 与 `open_chat_service` 共同调用。
- **`open_agent_service`**：agent 未读/已读等 **读/轻写**，直接包装现有 `agent.py` 逻辑，**不经过** `chat_service`。

**隔离原则：**

- Open 层 **不复制** Step1.5 / Step5 / Step6 业务代码。
- H5 改 SSE 事件、前端 UI → Open v1 JSON 字段 **保持不变**（除非发 v2）。
- 主链 **语义变更**（如多气泡、内容安全策略）→ Open 行为跟随，但需在 changelog 说明。

## 4.2 API Key 生命周期

1. Admin 在用户详情页点击「生成 API Key」。
2. 服务端生成 `sk-lxm-{random}`，返回 **明文一次**；库内存 `key_hash`（pepper 哈希）、**`key_prefix`**（脱敏展示串，格式见 §6.1）、`user_id`、`created_at`、`last_used_at`。
3. 若该用户已有 Key → **重新生成**前二次确认 → 对 **`user_api_keys` 唯一行 UPDATE 覆盖** `key_hash`/`key_prefix`（**V5**）；`created_at` **保留首次签发**；`last_used_at` **置 NULL**；旧 Key **立即**失效。
4. 请求携带 Key → 哈希比对 → 解析 `user_id` → 检查 `user_banned:{user_id}` → 鉴权成功且（`last_used_at` 为 NULL 或距现在 **≥60s**）时 UPDATE `last_used_at`（**V8 / O5**）。
5. 用户被 Admin 禁用 → Key 与 JWT **同步 401**（`detail`:「账号已被禁用」）。

## 4.3 Open API v1 接口清单（6 个）

| 方法 | 路径 | 说明 | 对齐 H5 |
|------|------|------|---------|
| POST | `/api/open/v1/chat/send` | Body: `{ "content": "..." }`（1–2000 字）；成功 `data`: `{ messages[], emotion, round_id }` | `POST /api/chat/send` |
| POST | `/api/open/v1/chat/resend` | **v1 路由不声明 Body**（O7/R4-A）；成功返回同 send | `POST /api/chat/resend` |
| GET | `/api/open/v1/chat/timeline` | Query: `cursor`, `limit`；经 **`timeline_read_service`**；响应与 H5 一致（O1） | `GET /api/chat/timeline` |
| GET | `/api/open/v1/agent/messages` | 未读主动消息列表；`data` 为数组 | `GET /api/agent/messages` |
| GET | `/api/open/v1/agent/unread-count` | 未读条数；`data`: `{ count: int }` | `GET /api/agent/unread-count` |
| POST | `/api/open/v1/agent/messages/{message_id}/read` | 标记已读 | `POST /api/agent/messages/{id}/read` |

**统一响应信封（业务成功/失败）：** `{ "code": 0, "data": {}, "message": "success" }`（与 H5 一致）。**鉴权失败**：**HTTP 401** + `{"detail":"..."}`（§2.4），非上述业务信封。

**send/resend 同步语义：**

- Open 与 H5 **共用** `chat_service.enqueue_send` / `enqueue_resend` 入队；Open 调用 `chat_service.await_bundle_payload(generation_id)` 等待 Future，**禁止**直接返回 H5 的 `StreamingResponse`。
- **`await_bundle_payload` 必须使用 asyncio 异步等待**（`asyncio.Future` + `asyncio.wait_for`，与现 `_sse_chat_wait_bundle` 相同）；**禁止** `threading.Event.wait()` / `time.sleep()` 等同步阻塞（O2）。
- 阻塞等待上限与 H5 SSE 一致，默认 **120s**（`_BUNDLE_WAIT_TIMEOUT_SEC`）。
- 成功：`code=0`，`data` 结构见下（**V3**）；`messages` 提取逻辑与 `_sse_chat_wait_bundle` 成功分支一致（优先 `step5.messages`，空则回退 `reply` 单条）；`emotion` 缺省 `{"label":"平静","confidence":1.0}`；`round_id` **必填**（O4）。
- 业务失败：JSON `{ "code": 101xx, "message": "..." }`。
- 客户端 HTTP 超时建议 **≥ 130s**。

**成功响应示例（send / resend 相同，V3）：**

```json
{
  "code": 0,
  "data": {
    "messages": [
      {"type": "text", "content": "..."}
    ],
    "emotion": {
      "label": "开心",
      "confidence": 0.92
    },
    "round_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "message": "success"
}
```

**Open v1 错误码补充：**

| code | 含义 | message（`ERROR_MESSAGES`） |
|------|------|----------------------------|
| 10101 | 内容安全拦截（**入队前**用户输入 **或** bundle 完成后模型输出 **`failed_blocked`**） | 现有文案（如「消息包含不适当内容，请修改后重试」） |
| 10108 | 本代 generation 已被新消息作废（`obsolete`）；见 §5.3 | **回复已被新消息取代，请拉取时间线查看后再操作**（V7） |

**10101 备注：** 两种拦截时机对外 **同一错误码**；Open 均为 HTTP 200 + ApiResponse，`data=null`。**第三方无需区分**入队前拦截与 `failed_blocked`；可通过 timeline 查看 user 行 `delivery_status`（`failed_blocked` 时须重新 send，不可 resend，见 TD-030）。

**MVP 不支持：**

- Open send Body **不暴露** `client_message_id`（H5 Schema 有字段但 `chat.py` 未实现幂等）。
- Open resend **不声明 Body 参数**（O7）；不支持 `client_resend_id`（N6；H5 前端会传但 backend 未实现幂等）。

## 4.4 Admin 用户详情 — Open API Key 区块

| 元素 | 说明 |
|------|------|
| 状态 | 未开通 / 已开通 |
| Key 展示 | 脱敏 **`sk-lxm-{前4}…{后4}`**（例 `sk-lxm-a1b2…wxyz`），由 **`key_prefix` 字段原样输出**；**never** 再次展示明文 |
| 元数据 | 创建时间（**首次签发**，重新生成不刷新）、最后使用时间（**展示到分钟**） |
| 操作 | 「生成 Key」「重新生成 Key」（二次确认：旧 Key 立即失效） |
| 权限 | `super_admin` + `ops_admin`（C8） |
| 审计 | 复用 `log_operation()`（N4）；首次 `action=create`，重新生成 `action=edit`；**v1 不展示** Base URL（N7） |

## 4.5 完整流程（第三方发消息）

```
1. 第三方 POST /api/open/v1/chat/send + API Key
2. Open 鉴权 → user_id
3. chat_service.check_content_safety(content) + check_send_quota(user_id, db)  （V9，与 H5 共用）
4. chat_service.enqueue_send
     → _new_generation_for_user（Redis 新 generation_id）
     → _invalidate_generation_future(old_gen)   # 作废旧代 Future（O3）
     → 写 user 行、proactive_times 清零、防抖、调度 _execute_llm_bundle（与 H5 相同）
5. chat_service.await_bundle_payload(gen_id)   # asyncio.wait_for ≤120s（O2）
6. 成功 → JSON 返回 messages + emotion + round_id（**V3** / O4）；异步 Step6 / 成长值 / ai_emotion（不阻塞响应体）
7. obsolete → 10108（**V7**）；超时/LLM 失败 → 10102；入队前内容安全 → 10101；bundle 完成后模型输出拦截（`failed_blocked`）→ 同 **10101**（HTTP 200，`data=null`）
```

**禁止（O3）：** 在 `_execute_llm_bundle` 完成路径、Open Facade 或 bundle 内 **另行实现** 第二套 obsolete 判定；必须与 H5 共用 `_new_generation_for_user` 链。

## 4.6 Admin API — Open API Key

挂载于 `/api/admin/users`（与现有用户管理同 RBAC：`super_admin` + `ops_admin`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users/{user_id}/open-api-key` | 查询：是否已开通、`key_prefix` 脱敏、创建/最后使用时间；**不含明文** |
| POST | `/api/admin/users/{user_id}/open-api-key` | 生成或重新生成；响应 **仅此一次** 含完整 `api_key`；写操作日志（N4） |

---

# 5. 边界情况

## 5.1 鉴权

| 场景 | 处理 |
|------|------|
| 未提供 `Authorization` | **HTTP 401**，`detail`:「未提供 API Key」+ `WWW-Authenticate: Bearer` |
| Key 缺失/错误/已吊销/格式错 | **HTTP 401**，`detail`:「API Key 无效或已吊销」（S8；不区分原因） |
| Key 已吊销（重新生成后） | 同上 |
| 用户被禁用 | **HTTP 401**，`detail`:「账号已被禁用」 |
| 一用户一 Key | 生成新 Key 时旧 Key **立即**失效 |
| Key 用于 `/api/chat/*` | **401**（JWT 路由不接受 API Key，S1） |

## 5.2 对话（与 H5 完全共用规则，C11）

| 场景 | H5 | Open |
|------|-----|------|
| 未闭环 ≥5 且无叹号 | **10104** 队列满 | 同左 |
| 重发超过 2 次/分钟 | **10105** | 同左 |
| 入队前内容安全不通过 | **10101**（未进 SSE） | **10101**（HTTP 200，`data=null`） |
| LLM 超时/失败 | **10102** / SSE `failed`；user 行 `failed_timeout` / `failed_error` | **10102**（HTTP 200） |
| 模型输出内容安全拦截 | user 行 **`failed_blocked`**；SSE **`failed`** + **10101**；无叹号 | user 行 **`failed_blocked`**；HTTP 200 + **10101**（**非** `code=0`）；`data=null` |
| `failed_blocked` 后 resend | **10107**（V4 / TD-030） | 同左；须 **重新 send** |
| 多气泡回复 | `done.messages` 为 `[{type, content}, …]` | 成功 `data.messages` 同结构（V3） |
| 双端混用 | 同一 timeline；等待中被新消息顶掉 → SSE **`obsolete`** | 同 timeline；等待中被顶掉 → **10108** |

## 5.3 Open 层特有

| 场景 | 处理 |
|------|------|
| HTTP 超时（客户端 < 120s） | 客户端断开；服务端可能仍在跑 bundle（与 H5 SSE 断连类似）；第三方应拉 timeline 核对 |
| 重复 send | **MVP 不支持** `client_message_id` / 幂等键；超时后靠 timeline 对账 |
| generation **obsolete**（等待中被新 send/resend 作废） | **10108** + message 见 §4.3；禁止立即同内容重发；应 **GET timeline** 对账（N2 / V7） |
| Open resend | **路由不声明 Body**（O7）；不支持 `client_resend_id`（N6）；**仅** `failed_timeout`/`failed_error` 窗口可 resend（**不含** `failed_blocked`，V4） |

### 5.3.1 generation obsolete 触发链与双端对称性（O3）

**唯一触发源（写路径入队时，H5 / Open 共用）：**

```text
enqueue_send / enqueue_resend
  → _new_generation_for_user(user_id)      # Redis 写入新 generation_id
  → _invalidate_generation_future(old_gen) # 旧 Future set_result({obsolete: true})
  → … 写库 / 调度 _execute_llm_bundle …
```

**禁止：** 在 bundle 完成时、Open 层或 `_execute_llm_bundle` 内再实现第二套作废逻辑。

**双端表现（触发源相同，对外形态不同，属预期行为）：**

| 端 | 等待方式 | obsolete 对外表现 |
|----|----------|-------------------|
| **H5** | SSE `_sse_chat_wait_bundle` | SSE 事件 `{"type":"obsolete"}`；前端移除进行中 AI 气泡 |
| **Open** | `await_bundle_payload` 同步 JSON | HTTP 200 + `{"code":10108,"message":"回复已被新消息取代，请拉取时间线查看后再操作","data":null}`（V7） |

**双端混用示例：** Open 阻塞等待 120s 期间，H5 或 Open 再次 `send` → 旧 generation 的 H5 SSE 收 `obsolete`、Open 收 **10108**；用户已发消息仍在 timeline，应拉 timeline 对账而非盲重发。

## 5.4 主链变更例外

以下情况 Open API **行为会随主链变化**，需在 Open API changelog 注明：

- Prompt / 人格 / Step5.5 策略变更
- 内容安全词库变更
- 多气泡、round_id 规则变更

## 5.5 已知契约漂移（非 Open 阻塞）

- H5 `client_resend_id` / 错误码 **10106** 幂等：Schema 与部分测试清单有描述，**backend 未实现**；Open v1 按 N6 不暴露该字段。

---

# 6. 数据结构

## 6.1 新增表：`user_api_keys`（表名实现时可微调）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 自增 |
| user_id | INT FK → users.id | 唯一索引，**每用户最多 1 行** |
| key_hash | VARCHAR(64) | `SHA-256(api_key + OPEN_API_PEPPER)` 十六进制 |
| key_prefix | VARCHAR(24) | **脱敏展示串**，格式 **`sk-lxm-{随机段前4字符}…{末4字符}`**（例 `sk-lxm-a1b2…wxyz`）；**直接存库**，Admin **原样展示**；**不在库内存星号**（V5） |
| created_at | DATETIME | **首次**签发时间；重新生成 **不刷新**（V5） |
| last_used_at | DATETIME NULL | 最后成功鉴权时间；**V8**：仅当 NULL 或距现在 ≥60s 时 UPDATE；Admin 展示到分钟 |
| created_by_admin_id | INT NULL | 签发管理员 |

**不存明文 Key。**

## 6.2 复用表（无结构变更）

- `conversation_log`、`agent_message`、`emotion_log`、`relationship`、`memory`、`users`

## 6.3 Admin 操作日志（N4）

复用现有 `log_operation()` 与 `admin_operation_logs` 表（`action` 列为 `String(20)`，**不使用**超长自定义 action 名）。

| 操作 | module | action | 说明 |
|------|--------|--------|------|
| 首次生成 Key | `用户管理` | `create` | `target_description` 含 user_id、username、脱敏 `key_prefix`（**V6**） |
| 重新生成 Key | `用户管理` | `edit` | `before_value`/`after_value` 为旧/新 `key_prefix`（**不用** `update`） |

**`target_description` 示例（V6）：**

- 首次：`为用户 {username}(ID:{user_id}) 生成 Open API Key，前缀 {key_prefix}`
- 重新生成：`重新生成用户 {username}(ID:{user_id}) 的 Open API Key`

**禁止**在日志任何字段写入完整 API Key（S6）。

## 6.4 环境变量

| 变量 | 说明 |
|------|------|
| `OPEN_API_PEPPER` | Key 哈希 pepper，**必填**；有效长度 **≥32**；缺失或无效 → **整应用拒绝启动**（N1 / V2）；**测试/生产各一套**，勿提交 Git；**轮换须计划作废全部 API Key**；**与 `JWT_SECRET` 无关** |
| `OPEN_API_PUBLIC_BASE_URL` | **v1 不读取**；可在 `.env.example` 注释预留，供后续 Admin 展示 Base URL（N7） |

写入 `.env.example` 与 `backend/config.py`；启动检查在 `main.py` lifespan 或 config 加载时执行。本地/CI 发版前须配置 pepper（`openssl rand -hex 32` 生成示例见 `DEPLOY.md`）。

---

# 7. 改造范围与文件索引

## 7.0 开发前 STEP-0（O6 / R3-A）

N5 **最小搬迁** 启动前执行：

1. `rg "from backend.routers.chat import" backend tests` — 梳理隐性依赖（已知：`prompt_mgmt._build_round_context`、多份测试）。
2. **依赖方向：** `chat_service` **禁止** import `routers.chat`；允许 `chat.py` → `chat_service` 单向依赖。
3. `_build_round_context`、Prompt 相关符号 **本期不迁**，仍留 `chat.py`（或后续 tech debt 单独迁）。
4. **`chat_service` 须暴露 `_resolve_generation_future`**，供 `_execute_llm_bundle` 调用（V1）。
5. **`check_content_safety` / `check_send_quota` 由 `chat_service` 提供**；Open router **未**直接 `import routers.chat`（V9）。
6. H5 回归范围：`send` / `resend` SSE（含 `obsolete`、**failed_blocked→10101**）、10104/10105、双端混用、timeline 字段不变。

## 7.1 文件清单

| 文件 | 改动内容 | 改动量 |
|------|----------|--------|
| `backend/models/user_api_key.py` | 新增模型 | 小 |
| `backend/database` / migration | 新表 | 小 |
| `backend/utils/open_api_auth.py` | Key 校验：前缀、pepper 哈希、恒定时间比较；**仅挂载 open 路由**；`last_used_at` **≥60s DB 节流**（V8/O5） | 中 |
| `backend/services/chat_service.py` | **N5/O6/V1/V9**：`check_content_safety` / `check_send_quota`（抽自 `chat.py`）；Future 运行时 + `_resolve_generation_future` + `enqueue_*` / `await_bundle_payload` + generation 链；**asyncio only**（O2） | 大 |
| `backend/services/timeline_read_service.py` | **O1**：自 `chat.py` 抽出 `get_timeline`；H5 / Open 共用 | 中 |
| `backend/services/open_chat_service.py` | Facade：send/resend → `chat_service`；timeline → `timeline_read_service` | 中 |
| `backend/services/open_agent_service.py` | Facade：agent 包装（不经过 chat_service） | 小 |
| `backend/routers/open/chat.py` | Open 路由：调用 **V9** 共享校验 + `chat_service` 入队/等待；**resend 不声明 Body**（O7）；**禁止** `import routers.chat` | 中 |
| `backend/routers/open/agent.py` | Open 路由 | 小 |
| `backend/routers/admin/users.py` | Key 生成/查询 API + 操作日志（N4） | 中 |
| `backend/schemas/open_*.py` | send 等 Schema；**resend 无 Body Schema**（O7） | 小 |
| `backend/routers/chat.py` | 改调 `chat_service` + `timeline_read_service`；保留 SSE 适配 | 中 |
| `backend/config.py`、`.env.example` | `OPEN_API_PEPPER` 必填校验；pepper 预留注释 | 小 |
| `backend/main.py` | 挂载 open router；启动时 pepper 检查（N1） | 小 |
| `backend/constants.py` | 新增 `ERR_CHAT_GENERATION_OBSOLETE = 10108` 及 **V7** 文案（N2） | 小 |
| `admin/pages/user-detail.html` | Key 管理 UI（无 Base URL 展示，N7） | 中 |
| `admin/static/js/admin-api.js` | API 封装 | 小 |
| `nginx/nginx.conf` | S7 注释：禁止 log_format 记录 `$http_authorization`（N8） | 小 |
| `DEPLOY.md` 或 `open-api-v1.md` | Nginx 日志抽检说明（N8） | 小 |
| `docs/design/open-api-v1.md` | 第三方集成文档；401/10108/obsolete；**10101 含 failed_blocked**；**failed_blocked 不可 resend（TD-030）**；传输安全（N9） | 中 |
| `docs/contract.md` | Open API 契约模块 | 中 |

---

# 8. 技术债标注

| 编号 | 说明 |
|------|------|
| TD-NEW-01 | Open send 同步等待 Future，极端情况下客户端超时后服务端仍完成写入；第三方需通过 timeline 对账（与 H5 SSE 断连同类） |
| **TD-030** | **`failed_blocked` 未纳入叹号重发**（H5 / Open 共用）：V4 本期接受现状；完整描述见 **`docs/tech-debt.md` [TD-030]** |
| TD-NEW-03 | H5 `client_resend_id` / 10106 幂等未实现；Open v1 亦不暴露；若要做须 H5+Open 同期立项 |
| TD-NEW-04 | `_build_round_context` 等仍留 `chat.py`；`prompt_mgmt` 等依赖需在 STEP-0 梳理；后续可单独迁出（O6） |
| TD-NEW-05 | **`check_send_quota`（10104）为非原子「先 SELECT 再 INSERT」**；H5 现网已如此，Open 搬迁（V9）后行为一致，**不新增恶化**；完整描述见 **`docs/tech-debt.md` [TD-031]** |

> **说明**：原 **TD-NEW-02**（`failed_blocked`）已合并为仓库级 **[TD-030]**（2026-06-04 req-confirm V4）。

---

# 9. 检查项

| 项目 | 状态 |
|------|------|
| C1–C17 产品决策 | ✅ |
| N1–N9 需求评审（2026-06-03） | ✅ |
| O1–O7 架构/实现优化（2026-06-03） | ✅ |
| V1–V9 实现层确认（req-confirm · 2026-06-04） | ✅ |
| 契约 `docs/contract.md` 同步 | ⬜ 开发后 |
| Admin 操作审计（N4） | ⬜ 开发时 |
| Nginx Authorization 日志抽检（N8） | ⬜ 部署验收 |

## 9.1 N5 实现检查清单（O2 / O3 / O6 / V9）

| # | 检查项 |
|---|--------|
| 1 | `await_bundle_payload` 仅使用 `asyncio.Future` + `asyncio.wait_for`；无 `threading.*.wait` / 同步 sleep 120s |
| 2 | obsolete **仅**由 `enqueue_*` 内 `_new_generation_for_user` → `_invalidate_generation_future` 触发 |
| 3 | H5 SSE `obsolete` 与 Open **10108** 双端回归（§5.3.1） |
| 4 | `timeline` 经 `timeline_read_service`，**未**误经 `chat_service` |
| 5 | Open `resend` 路由 **无 Body 参数**，空 POST 不 422 |
| 6 | `round_id` 从 Future payload 读取，未改 `_execute_llm_bundle` |
| 7 | STEP-0：`rg "from backend.routers.chat import"` 已执行且无新增反向依赖 |
| 8 | Open 成功 JSON 仅含 `messages`/`emotion`/`round_id`（V3）；10108 message 与 §4.3 一致（V7） |
| 9 | Key 重新生成为单行 UPDATE；`created_at` 不刷新（V5）；`last_used_at` ≥60s 节流（V8） |
| 10 | `check_content_safety` / `check_send_quota` 由 **`chat_service`** 提供；Open router **未** `import routers.chat`（V9） |
| 11 | Open `failed_blocked` → HTTP 200 + **10101**（非 `code=0`）；后续 resend → **10107** |
| 12 | 成功 `messages` 仅 **`{type, content}`** 两字段（V3） |

---

# 10. 安全与权限（C12/C14 硬约束）

## 10.1 为何 Bearer 仍可用、风险在哪

`Authorization: Bearer` 与 H5 JWT **共用头名**，本身不更不安全；主要风险来自 **API Key 长期有效**（无 JWT 的短过期），一旦泄露可在吊销前持续调用 Open API。

因此：**传输用 Bearer + 路径与权限强隔离 + 存储与日志规范 + 文档禁止误用**。

## 10.2 服务端硬约束（实现必做）

| 编号 | 约束 | 说明 |
|------|------|------|
| S1 | **路径隔离** | API Key **仅**可访问 `/api/open/v1/*`；**不可**用于 `/api/chat/*`、`/api/admin/*` 等 JWT 路由 |
| S2 | **前缀校验** | Open 鉴权只接受 `sk-lxm-` 前缀；JWT 形态（如 `eyJ...`）在 Open 路由一律 401，**避免与 JWT 混用** |
| S3 | **传输安全** | **当前生产**为 `http://cllxm.com`（已确认）；详见 §10.3 S16 与 `open-api-v1.md`「传输安全」 |
| S4 | **库内不存明文** | 存 `SHA-256(api_key + OPEN_API_PEPPER)`；**pepper 与 JWT 密钥独立**（§2.1.1）；校验用 **恒定时间比较**（如 `hmac.compare_digest`） |
| S5 | **Key 熵** | 随机部分 ≥ **32 字节**（如 `secrets.token_urlsafe(32)`），前缀固定 `sk-lxm-` |
| S6 | **日志脱敏** | 应用日志、Admin 操作日志、异常栈 **不得**出现完整 Key；仅 `key_prefix` 脱敏 |
| S7 | **Nginx/网关** | 访问日志 **不记录** `Authorization`；`nginx/nginx.conf` 加注释禁止 `$http_authorization`；部署验收抽检（N8） |
| S8 | **错误信息** | 鉴权失败统一文案（「API Key 无效或已吊销」），**不区分**「不存在 / 已吊销 / 格式错」，防枚举 |
| S9 | **吊销** | 重新生成 Key 后旧 hash **立即**失效；用户禁用时 Key 同步 401 |
| S10 | **权限最小化** | Key 绑定 user_id，权限等价于该用户的 **Open 聊天能力**，不含 Admin、不含改密码等 |

## 10.3 第三方集成约束（写入 open-api-v1.md）

| 编号 | 约束 | 说明 |
|------|------|------|
| S11 | **禁止浏览器直连** | 不得在前端 JS、网页 Query、Cookie 中携带 Key（防 XSS/Referer 泄露） |
| S12 | **安全存储** | 桌面端用系统密钥链/加密配置；禁止提交进 Git、截图、硬编码 |
| S13 | **禁止 Query/Body 传 Key** | 仅 `Authorization: Bearer`；禁止 `?api_key=` |
| S14 | **泄露响应** | 怀疑泄露 → Admin **立即重新生成** Key |
| S15 | **超时与对账** | 客户端 HTTP 超时或收到 **10108** 后应 **拉 timeline** 核对，避免重复狂发 |
| S16 | **传输安全（N9）** | 独立章节：当前生产 Base URL 为 **HTTP**；Key 明文传输存在窃听风险；**禁止**浏览器/不可信网络直连；启用 HTTPS 后仅改 Base URL；产品侧 **不拦截** HTTP 调用 |

## 10.4 可选增强（本期不做，记录备查）

- Admin 用户详情展示 Open API Base URL（N7 留后续）
- 按 IP 的鉴权失败限流（防暴力撞库 hash）
- Key 自动过期 TTL（与 C10「无 disable」冲突，需产品另议）
- mTLS / IP 白名单（50 用户规模暂不实施）

## 10.5 Admin 侧

- 生成/重新生成：二次确认 + 操作审计（N4）
- 仅 `super_admin` + `ops_admin` 可见 Key 管理区块（C8）

---

# 11. 验收标准

1. Admin 为用户生成 Key 后，第三方仅用 Key 可完成：发消息、收 JSON 回复、拉 timeline、resend、读/标记 agent 消息、**unread-count 轮询**。
2. 同一用户在 H5 与 Open API 发送的消息，在 timeline 中 **顺序一致**（`sort_seq`）。
3. 重新生成 Key 后，旧 Key **立即** 401（`detail`:「API Key 无效或已吊销」）。
4. 用户禁用后 Key **立即** 401（`detail`:「账号已被禁用」）。
5. Open API 不修改 H5 `/api/chat/send` SSE 行为；H5 回归无破坏（N5 重构后）。
6. 提供第三方可读 `open-api-v1.md`，含：§2.4 鉴权 401 示例、**六**接口、10108 **固定文案**（V7）、**failed_blocked 不可 resend**（TD-030）、PC 托盘轮询、超时建议、**§10.3 安全约束（含 S16 传输安全）**、生产 `http://cllxm.com` 示例 curl。
7. 使用 API Key 访问 `/api/chat/*`（JWT 路由）→ **401**（S1）。
8. 缺 `OPEN_API_PEPPER` 时应用 **无法启动**（N1）。
9. 双端混用下 Open 等待被新消息顶掉 → **10108**；同场景 H5 SSE → **`obsolete`**（§5.3.1，O3）。
10. Open `resend` **无 Body 参数**可成功，不 422（O7）。
11. 应用/Nginx 访问日志抽检 **不出现**完整 Key（N8）；Admin 操作日志无明文 Key（N4/S6）。
12. `timeline` H5 / Open 字段一致，且共用 `timeline_read_service`（O1）。
13. Code review 通过 §9.1 实现检查清单（O2/O3/O6/V9）。
14. Open send 触发 **`failed_blocked`** → HTTP 200 + **`code=10101`**，**不**返回 `code=0`；后续 resend → **10107**。
15. `key_prefix` 库内格式与 Admin 展示一致（§6.1 / §4.4）；`messages` 与 H5 SSE `done` 字段一致（**仅 `type` + `content`**）。

---

# 版本记录

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v1.9 | 2026-06-04 | 文档审查修正：V3 messages 字段；V9 入队前校验抽取；V1 与 V9 对齐；key_prefix 格式统一；failed_blocked→10101；10104 非原子 TD-NEW-05；§5.2 H5/Open 分列 |
| v1.8 | 2026-06-04 | req-confirm V1–V8 写入：§2.0.3、JWT/pepper 区分（§2.1.1）、Open JSON 示例、10108 文案、Key UPDATE 覆盖、last_used_at 节流、failed_blocked/TD-030、chat_service 搬迁边界细化 |
| v1.7 | 2026-06-03 | O1–O7 架构优化：timeline_read_service、asyncio 约束、obsolete 双端对称、round_id/last_used_at/resend Body/N5 最小搬迁 |
| v1.6 | 2026-06-03 | 需求评审 N1–N9 全部确认并写入；修订鉴权 401、10108、chat_service 编排、操作日志、resend Body、pepper 启动策略等 |
| v1.5 | 2026-06-02 | C16 unread-count；审核修订 C9/C17/Admin API/6 接口；状态改开发中 |
| v1.4 | 2026-06-02 | 生产公网 Base URL 确认为 http://cllxm.com |
| v1.3 | 2026-06-02 | 新增 C15：用户自定义 Base URL + 每环境独立 Key |
| v1.0 | 2026-06-02 | 初始版本；汇总 C1–C7 已确认决策 |
