# Agent Future Api

- 文档 ID：`contract-agent-future-api`
- 权威状态：`canonical`
- 功能范围：`agent-future`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-004`, `TD-015`

### 模块：H5 主动消息（`/api/agent`）

> **P0–P4 生成链路（服务端，非 HTTP）**：定时扫描 **`AgentService.check_and_trigger`** → **`generate_and_save_message`**。Prompt：**`PromptBuilder.build_active_message_prompt`**（Step5 System + 主动任务模块）。LLM：**`chat_with_step5_parse`** → **`messages[]`** 合并为单条 **`content`** 写入 **`agent_message`**。失败兜底：**`AGENT_FALLBACK_REPLIES`**（按 `trigger_type`），**禁止**对话走神占位入库。FUTURE 走 **Step8**（`execute_step8_subchain`），本段不适用。

#### GET /api/agent/messages

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组 `{id, trigger_type, content, action_score, created_at}[]`（仅未读）
- **关联表**：agent_message
- **状态**：已实现

#### POST /api/agent/messages/{message_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`
- **状态**：已实现

#### GET /api/agent/unread-count

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`: `{ count: int }`
- **说明**：计入全部未读 `agent_message`（含生活流感知 **`LIKE_AWARE` / `READ_AWARE`**，与 P0–P4/FUTURE 同表）
- **状态**：已实现

---

### 模块：Agent 管理

#### GET /api/admin/agent-night-keywords

- **所属端**：管理后台
- **鉴权**：Bearer Admin JWT（角色同 PUT：`super_admin` / `ai_trainer`）
- **响应**：`ApiResponse`；`data` 与 **PUT** Body 一致：`{ "keywords": string[] }`（无生效配置时 `keywords` 为空数组 `[]`）
- **数据来源**：`get_active_config("agent_night_keywords", use_cache=False)`（查 **admin_config** 当前生效行，**不**经 Redis）
- **关联表**：admin_config
- **同模块其它路由**：**GET|PUT** `/agent-rules` — `AgentRulesRequest`；**GET** `/agent-message-rules`（整包）/ **PUT** `/agent-message-rules/{trigger_type}`（单类型）；**PUT** `/agent-night-keywords` — `NightKeywordsRequest`；**GET** `/agent-messages` — Query：`user_id`（可选）、`trigger_type`、`is_read`、`start_date`、`end_date`（见 **`admin_date_filter`**）、`page`、`page_size`（1–100）；
  - 鉴权 **`super_admin` / `ops_admin` / `ai_trainer`**；排序 **`created_at` 降序**；成功 `data`：`{ total, page, page_size, list[] }`；**`list[]`**：`id`, `user_id`, `trigger_type`, `content`, `action_score`, `is_read`, `created_at`
- **状态**：已实现

---

<a id="voice-followup"></a>
### 语音后续消息

VOICE_FOLLOWUP由独立voice_followup_job产生，通过既有agent_message未读与timeline接口读取；不创建Future槽，不替换P0～P4任务。按用户已确认口径，语音发送不套旧8条/30分钟门禁，但成功仍计入UTC日主动消息计数；sent后的计数补偿不重发。调用的消息处理子链不等于整个语音通话主链，具体状态见[语音内部处理](../realtime-voice/data.md#postprocess)。

<a id="future-consumption"></a>
### Future/Step8 的身份、提交与效果

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

`Slot(user_id,version,timestamp,action)` 捕获原槽，`Execution(slot,consume_id,owner,epoch,deadline_at,reconcile_until)` 为消费身份。`execute_step8_subchain(user_id,future_action,*,slot=None)` 返回 `Result(consume_id,terminal,success_kind,agent_message_id,commit_evidence,effects)`；禁止 bool(Result)，unverified 不等于失败。

正常保存及独立 fallback 均经 future_lifecycle.commit_success：准入起点+180秒固定，原owner/epoch/marker/槽资格和新鲜DB UTC最终CAS。正常ACK在异步清理前同步通知；未知仅同marker及D前decision权威确认后，在结果/效果metadata写与退出await前通知；原worker快照回调保留至外层核实。未确认不清槽、不重新生成。

`step8_memory_pipeline` 使用自身 future_action，source=step8，接四路改写/双召回/重排、同源Prompt、官方counter、SQL reserve及GuardedModelClient，45+45各取原D较早者；共享最终选入/正文/使用保护见[召回消费](../chat-emotion/api.md#m8-retrieval-consumption)。普通Agent/P0～P4保留原算法、预算、TopK、模型及兜底用途。

normal 成功保持Step6一次、normal_decay原概率与pt上限3、Handler独立pt上限3以及原agent计数；fallback只有原Handler pt/计数，原人格风险文案/触发不改。SQL effect唯一身份及对应数值写同事务，成功不因后置收尾失败反转；持久恢复边界见[Future数据](data.md#future-effects)。

<a id="future-slot-cas"></a>
### 槽版本与 Step8 条件清理

所有槽写/清都推进 future_slot_version，包括同值ABA：Relationship三入口、Step8预约、Handler成功/失败/黑名单/低分/过期、Agent过期及S15均消费原捕获版本。Step8 的 Step6Snapshot 可选 future_clear_slot 经 orchestrator 传入原标量服务；无/解析失败两条清槽按 user/version/timestamp/action 的SQL CAS，未命中返回 preserved_newer_slot。主文字默认None保持原行为，不能清新槽。

成功计数独立于清槽命中；已计数但清槽失败的重入仅补条件清理，不重复计数、Step6或生成。版本物理字段唯一见[relationship](../relationship/data.md#future-slot-version)，原消费/提交/effect记录见[Future数据](data.md#future-consumption-data)。
