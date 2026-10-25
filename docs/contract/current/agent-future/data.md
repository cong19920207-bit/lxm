# Agent Future Data

- 文档 ID：`contract-agent-future-data`
- 权威状态：`canonical`
- 功能范围：`agent-future`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-004`, `TD-015`

### 表名：agent_message


| 字段名          | 类型         | 必填  | 默认值    | 说明    |
| ------------ | ---------- | --- | ------ | ----- |
| id           | Integer PK | 是   | 自增     |       |
| user_id      | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| trigger_type | String(16) | 是   | -      | P0–P4 / FUTURE / **`VOICE_FOLLOWUP`** / **`LIKE_AWARE`** / **`READ_AWARE`**（生活流感知 IM；落库 `action_score=0`；与 P0–P4/Future **业务零耦合**，仅共用本表与 `sort_seq`） |
| content      | Text       | 是   | -      |       |
| action_score | Float      | 是   | -      |       |
| is_read      | Boolean    | 是   | False  |       |
| sort_seq     | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| created_at   | DateTime   | 是   | utcnow |       |

<a id="voice-followup-shared"></a>
### 语音后续消息来源

`agent_message.trigger_type`另允许`VOICE_FOLLOWUP`（String(16)可容纳）。语音任务成功时同事务写入既有消息与sort_seq，沿用未读/时间线读取，不占Future任务槽。任务状态、发送窗和计数补偿唯一归属[语音数据](../realtime-voice/data.md#postprocess)。

<a id="future-consumption-data"></a>
### Future 消费持久记录

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

迁移 `v9f_future_consumption_001` 接 `v9e`，新增 future_consumption、relationship.future_slot_version（无符号BIGINT，ORM/SQL默认0）及 agent_message `UNIQUE(user_id,id)`（`uq_agent_message_user_id`）。复用[服务端计时](../chat-emotion/data.md#chat-timing)和成功effect表；不改普通agent_message字段/读取协议。槽、Result及成功决定唯一见[Future接口](api.md#future-consumption)。

due扫描排除已有(user_id,slot_version)身份；旧pending仅原reconcile_until内核实，超界有限告警、不续D；同值新version可新准入。正常/fallback都必须有同owner消息、round、marker、decision<D和atomic_decision；unverified不得当失败再次生成。

<a id="future-effects"></a>
### 原身份效果恢复及清后保护

Redis Lua将effect marker、INCR及EXPIRE原子执行；`agent:future:effect:{consume_id}`保留30天，`agent:count:{user}:{YYYY-MM-DD}`固定原成功UTC日，重复/次日核实不加新日。SQL done与Redis INCR不能被描述为跨系统原子事务。已确认成功数值效果沿7天身份保障期及原UTC日恢复，不误用提交未知核实窗截断。

原worker持快照时同步登记原效果，effect lease和进程任务标识保护恢复扫描不抢先判未知。跨进程丢失Step6/decay快照且保护期结束后记unverified，不重新生成/伪报done；仍可由原身份恢复的Handler数值防重执行。未承诺完整历史异步重放。

经授权S15保留consume成功审计/效果锚点，slot_action清为空串、agent_message_id清NULL；正常事务仍需真实同owner消息，CHECK保留已批准清后例外。以reset resource fixed_scope/cursor确认原cleared身份并拒恢复/重放，不能仅看空正文/FK推断。对外terminal=cleared不修改SQL success；未决phase/effect仍阻断清理。业务清理范围及保护唯一见[记忆数据](../memory-knowledge/data.md)。

<a id="future-consumption"></a>
### 表名：future_consumption

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `consume_id` | CHAR(36), ASCII/ascii_bin | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | ForeignKey('users.id',ondelete='CASCADE') |
| `slot_version` | BIGINT UNSIGNED | 否 | — | — |
| `slot_timestamp` | INTEGER | 否 | — | — |
| `slot_action` | VARCHAR(200) | 否 | — | — |
| `timing_config_version` | VARCHAR(64) ASCII/ascii_bin | 否 | — | — |
| `accepted_at` | DATETIME(6) | 否 | — | — |
| `deadline_at` | DATETIME(6) | 否 | — | — |
| `state` | VARCHAR(16) ASCII/ascii_bin | 否 | ORM 'pending' | — |
| `phase` | VARCHAR(24) ASCII/ascii_bin | 否 | ORM 'admitted' | — |
| `state_revision` | BIGINT UNSIGNED | 否 | — | — |
| `reason` | VARCHAR(64) ASCII/ascii_bin | 是 | — | — |
| `success_kind` | VARCHAR(8) ASCII/ascii_bin | 是 | — | — |
| `agent_message_id` | INTEGER | 是 | — | UNIQUE |
| `round_id` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `commit_marker` | CHAR(36), ASCII/ascii_bin | 是 | — | UNIQUE |
| `decision_at` | DATETIME(6) | 是 | — | — |
| `commit_observed_at` | DATETIME(6) | 是 | — | — |
| `commit_evidence_kind` | VARCHAR(24) ASCII/ascii_bin | 是 | — | — |
| `lease_owner` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `lease_epoch` | BIGINT UNSIGNED | 否 | ORM 0 / SQL '0' | — |
| `lease_until` | DATETIME(6) | 是 | — | — |
| `remote_started_at` | DATETIME(6) | 是 | — | — |
| `reconcile_until` | DATETIME(6) | 否 | — | — |
| `terminal_at` | DATETIME(6) | 是 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_future_slot` | UNIQUE (user_id, slot_version) |
| `fk_future_message` | FOREIGN KEY (user_id, agent_message_id) → (agent_message.user_id, agent_message.id) |
| `ck_future_state` | CHECK state IN ('pending','success','failed','superseded') |
| `ck_future_phase` | CHECK phase IN ('admitted','running','commit_prepared','commit_unknown','reconcile_exhausted','terminal') |
| `ck_future_kind` | CHECK success_kind IS NULL OR success_kind IN ('normal','fallback') |
| `ck_future_evidence` | CHECK commit_evidence_kind IS NULL OR commit_evidence_kind='atomic_decision' |
| `ck_future_success` | CHECK state != 'success' OR (round_id IS NOT NULL AND commit_marker IS NOT NULL AND decision_at IS NOT NULL AND decision_at < deadline_at AND commit_evidence_kind='atomic_decision') |
| `ck_future_reason` | CHECK reason IS NULL OR reason IN ('llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified','deadline_exceeded','generation_superseded','execution_lost','commit_unknown','deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired') |
| `ix_future_deadline` | INDEX (state, deadline_at) |
| `ix_future_reconcile` | INDEX (phase, reconcile_until) |
