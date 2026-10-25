# Chat Emotion Data

- 文档 ID：`contract-chat-emotion-data`
- 权威状态：`canonical`
- 功能范围：`chat-emotion`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-015`, `TD-016`, `TD-018`, `TD-019`, `TD-020`, `TD-023`, `TD-030`

### 表名：conversation_log


| 字段名                | 类型         | 必填  | 默认值    | 说明               |
| ------------------ | ---------- | --- | ------ | ---------------- |
| id                 | Integer PK | 是   | 自增     |                  |
| user_id            | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`     |
| role               | String(20) | 是   | -      | user / assistant |
| content            | Text       | 是   | -      |                  |
| emotion_label      | String(50) | 否   | NULL   | 用户消息情绪           |
| emotion_confidence | Float      | 否   | NULL   |                  |
| memory_injected    | JSON       | 否   | NULL   | **仅历史字段，已停用**：列保留，新 user 行恒 `null`；新链召回、选入与使用保护由独立结构记录，不回写此历史字段 |
| persona_risk_flag  | Boolean    | 是   | False  | 人格风险标记           |
| persona_risk_type  | String(50) | 否   | NULL   |                  |
| sort_seq           | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| delivery_status    | String(32) | 否   | NULL   | user 行：送达/等待/失败等（与 `constants` 一致）；assistant 为 NULL |
| skipped_in_prompt  | Boolean    | 是   | false  | Q14：未进入本轮 Prompt 的 user 行 |
| round_id           | String(36) | 否   | NULL   | TD-016 / STEP-011：一轮内全部 user 行与**全部** assistant 行共用同一 UUID 文本（多气泡时为多行 assistant，每行独立 `sort_seq`）；旧数据可为 NULL |
| created_at         | DateTime   | 是   | utcnow |                  |

### 表名：emotion_log


| 字段名             | 类型                              | 必填  | 默认值    | 说明  |
| --------------- | ------------------------------- | --- | ------ | --- |
| id              | Integer PK                      | 是   | 自增     |     |
| user_id         | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| emotion_label   | String(50)                      | 是   | -      |     |
| confidence      | Float                           | 是   | -      |     |
| conversation_id | Integer FK(conversation_log.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| round_id        | String(36)                      | 否   | NULL   | 与本轮 conversation 对齐；旧数据可为 NULL |
| created_at      | DateTime                        | 是   | utcnow |     |

### 表名：user_short_term_emotion


| 字段名          | 类型         | 必填  | 默认值    | 说明                               |
| ------------ | ---------- | --- | ------ | -------------------------------- |
| id           | Integer PK | 是   | 自增     |                                  |
| user_id       | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`）              |
| emotion_label | String(50) | 是   | -      | 短期情绪标签                           |
| confidence    | Float      | 是   | -      |                                  |
| payload       | Text       | 否   | NULL   | 可选 JSON 文本（ORM `nullable=True`）    |
| updated_at    | DateTime   | 是   | utcnow | `onupdate=utcnow`                |

<a id="chat-lifecycle"></a>
### 文字准入、提交与有限恢复的持久权威

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

迁移 `v9e_chat_lifecycle_001` 接 `v9d`，新增下列八表，并增加 conversation_log `UNIQUE(user_id,id)`（`uq_conversation_user_id`）；启动不 create_all 迁移管理表。SQL user_state 锁、修订号、generation owner+epoch、dispatch 和原提交身份为权威。

generation/message 状态为 pending/success/failed/superseded；phase 为 admitted/running/commit_prepared/commit_unknown/reconcile_exhausted/terminal，dispatch 为 pending/claimed/done。原因允许 llm_failed、content_blocked、prompt_budget_exceeded、prompt_budget_unverified、deadline_exceeded、generation_superseded、execution_lost、commit_unknown、deadline_unverified、storage_unavailable、legacy_record、legacy_pending、id_conflict、expired。对外可观察的 unverified 是[只读状态投影](api.md#submission-status)，不能将未知强制写为终态。

准入新鲜 DB UTC 冻结 accepted_at、D=accepted_at+180秒与 timing_config_version。最终事务以新鲜DB时间及原owner/epoch/marker作CAS，在原D前决定success，assistant/emotion/消息关联/成功effect同事务保存；成功须有 round_id、commit_marker、decision_at<D 和 atomic_decision 证据。D前权威成功不因迟到ACK降级。正常ACK后、异步会话退出前同步通知原worker注册效果；未知ACK仅由原marker独立主库锁读确认合法成功后，在观测写及退出await前通知。不能因未知重新生成或盲重发。

SQL lease默认15秒、每5秒续租且不越D；observer仅观察，取消只释放自身等待。失败/作废不得落成功assistant、派Step6或改新代。startup/周期 scan_once 消费持久dispatch，1～4 pending亦可恢复；远端已开始而owner丢失不自动重播流。核实有限、一次告警；依赖耗尽后只有确证新准入可重开扫描，GET、重复请求或回滚不重置原 exhausted/D。

`ChatLifecycleEffect`按 owner_kind/owner_id/effect_kind 去重，owner_kind 为chat/future，state为pending/running/done/failed/unverified；锚定成功后Step6/post_success派发，效果状态与业务终态分开。辅助观察/收尾失败不能反转成功，不承诺新增完整异步历史重放平台。

H5 AppShell新增的是客户端装配与恢复：页面草稿/滚动快照与原提交索引分离，按当前身份隔离；headers等待或SSE读取中离页不重发POST，不改变原until、generation、revision或exhausted。旧→新→旧以及隔离后端重启仅核实原提交。没有本次新增表/字段/迁移；持久业务权威仍为本节既有SQL规则。客户端唯一行为说明见[H5提交同步](../h5-app/api.md#chat-submission-sync)和[API源码增量](api.md#appshell-delta-32)。

<a id="chat-timing"></a>
### 服务端计时与保留参数

`chat_timing.TIMING` 固定 deadline_seconds=180，版本为 `chat-lifecycle-v1:` 加参数摘要；非法值拒加载。各环境变量用下列 uppercase 名称，不开放调大业务D。

| 环境变量 | 默认 | 有效范围 |
|---|---:|---|
| TEXT_STATUS_RECONCILE_MARGIN_MS | 60000 | 10000～120000 |
| TEXT_LIFECYCLE_SCAN_INTERVAL_MS | 5000 | 1000～10000 |
| TEXT_LIFECYCLE_SCAN_BATCH_SIZE | 100 | 1～500 |
| TEXT_SUBMISSION_RETENTION_SECONDS | 604800 | 180+reconcile_margin_ms/1000～2592000 |
| TEXT_SUBMISSION_TOMBSTONE_SECONDS | 2592000 | retention_seconds～315360000 |
| TEXT_COMMIT_PREPARE_RESERVE_MS | 5000 | 1000～10000 |
| TEXT_SERVER_WAIT_MARGIN_MS | 10000 | 1000～30000 |
| TEXT_LOCK_LEASE_MS | 15000 | 1～30000 |
| TEXT_LOCK_RENEW_MS | 5000 | 1～lease_ms-1 |
| TEXT_STATUS_PROBE_TIMEOUT_MS | 3000 | 500～10000 |

客户端轮询/transport参数由[H5计时](../h5-app/api.md#chat-client-timing)定义，只增加观察余量。物理表 below 不改变 H5/OpenAPI 原timeline结构。

<a id="chat-user-state"></a>
### 表名：chat_user_state

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `user_id` | INTEGER | 否 | — | PK; ForeignKey('users.id',ondelete='CASCADE') |
| `current_generation_id` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `state_revision` | BIGINT UNSIGNED | 否 | ORM 0 / SQL '0' | — |

| 约束/索引 | 条件 |
|---|---|
| `fk_chat_current_generation` | FOREIGN KEY (user_id, current_generation_id) → (chat_generation.user_id, chat_generation.generation_id) |

<a id="chat-generation"></a>
### 表名：chat_generation

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `generation_id` | CHAR(36), ASCII/ascii_bin | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | ForeignKey('users.id',ondelete='CASCADE') |
| `timing_config_version` | VARCHAR(64) ASCII/ascii_bin | 否 | — | — |
| `accepted_at` | DATETIME(6) | 否 | — | — |
| `deadline_at` | DATETIME(6) | 否 | — | — |
| `state` | VARCHAR(16) ASCII/ascii_bin | 否 | ORM 'pending' | — |
| `phase` | VARCHAR(24) ASCII/ascii_bin | 否 | ORM 'admitted' | — |
| `state_revision` | BIGINT UNSIGNED | 否 | — | — |
| `reason` | VARCHAR(64) ASCII/ascii_bin | 是 | — | — |
| `round_id` | CHAR(36), ASCII/ascii_bin | 是 | — | UNIQUE |
| `commit_marker` | CHAR(36), ASCII/ascii_bin | 是 | — | UNIQUE |
| `decision_at` | DATETIME(6) | 是 | — | — |
| `commit_observed_at` | DATETIME(6) | 是 | — | — |
| `commit_evidence_kind` | VARCHAR(24) ASCII/ascii_bin | 是 | — | — |
| `lease_owner` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `lease_epoch` | BIGINT UNSIGNED | 否 | ORM 0 / SQL '0' | — |
| `lease_until` | DATETIME(6) | 是 | — | — |
| `dispatch_state` | VARCHAR(16) ASCII/ascii_bin | 否 | ORM 'pending' | — |
| `next_dispatch_at` | DATETIME(6) | 否 | — | — |
| `remote_started_at` | DATETIME(6) | 是 | — | — |
| `reconcile_until` | DATETIME(6) | 否 | — | — |
| `terminal_at` | DATETIME(6) | 是 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_chat_generation_user` | UNIQUE (user_id, generation_id) |
| `ck_chat_generation_state` | CHECK state IN ('pending','success','failed','superseded') |
| `ck_chat_generation_phase` | CHECK phase IN ('admitted','running','commit_prepared','commit_unknown','reconcile_exhausted','terminal') |
| `ck_chat_dispatch_state` | CHECK dispatch_state IN ('pending','claimed','done') |
| `ck_chat_evidence` | CHECK commit_evidence_kind IS NULL OR commit_evidence_kind = 'atomic_decision' |
| `ck_chat_success` | CHECK state != 'success' OR (round_id IS NOT NULL AND commit_marker IS NOT NULL AND decision_at IS NOT NULL AND decision_at < deadline_at AND commit_evidence_kind = 'atomic_decision') |
| `ck_chat_generation_reason` | CHECK reason IS NULL OR reason IN ('llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified','deadline_exceeded','generation_superseded','execution_lost','commit_unknown','deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired') |
| `ix_chat_deadline` | INDEX (state, deadline_at) |
| `ix_chat_dispatch` | INDEX (dispatch_state, next_dispatch_at) |
| `ix_chat_reconcile` | INDEX (phase, reconcile_until) |

<a id="chat-submission"></a>
### 表名：chat_submission

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `id` | BIGINT UNSIGNED | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | ForeignKey('users.id',ondelete='CASCADE') |
| `operation` | VARCHAR(8) ASCII/ascii_bin | 否 | — | — |
| `request_id` | LargeBinary(512).with_variant(VARBINARY(512),'mysql') | 否 | — | — |
| `client_key_present` | BOOLEAN | 否 | — | — |
| `fingerprint` | BINARY(32) | 是 | — | — |
| `fingerprint_version` | INTEGER | 是 | — | — |
| `channel` | VARCHAR(16) ASCII/ascii_bin | 否 | — | — |
| `accepted_generation_id` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `accepted_at` | DATETIME(6) | 否 | — | — |
| `expires_at` | DATETIME(6) | 否 | — | — |
| `tombstone_until` | DATETIME(6) | 否 | — | — |
| `record_state` | VARCHAR(12) ASCII/ascii_bin | 否 | ORM 'active' | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_chat_submission_key` | UNIQUE (user_id, operation, request_id) |
| `uq_chat_submission_user` | UNIQUE (user_id, id) |
| `fk_chat_submission_generation` | FOREIGN KEY (user_id, accepted_generation_id) → (chat_generation.user_id, chat_generation.generation_id) |
| `ck_chat_operation` | CHECK operation IN ('send','resend') |
| `ck_chat_channel` | CHECK channel IN ('h5','open','internal') |
| `ck_chat_record_state` | CHECK record_state IN ('active','tombstone') |
| `ck_chat_active_submission` | CHECK record_state != 'active' OR (fingerprint IS NOT NULL AND fingerprint_version IS NOT NULL AND accepted_generation_id IS NOT NULL) |
| `ix_chat_retention` | INDEX (record_state, expires_at) |

<a id="chat-submission-message"></a>
### 表名：chat_submission_message

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `submission_id` | BIGINT UNSIGNED | 否 | — | PK |
| `conversation_id` | INTEGER | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | — |
| `ordinal` | INTEGER | 否 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_chat_submission_ordinal` | UNIQUE (submission_id, ordinal) |
| `fk_chat_sm_submission` | FOREIGN KEY (user_id, submission_id) → (chat_submission.user_id, chat_submission.id) |
| `fk_chat_sm_conversation` | FOREIGN KEY (user_id, conversation_id) → (conversation_log.user_id, conversation_log.id) |
| `ix_chat_sm_message` | INDEX (user_id, conversation_id) |

<a id="chat-message-state"></a>
### 表名：chat_message_state

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `conversation_id` | INTEGER | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | — |
| `effective_generation_id` | CHAR(36), ASCII/ascii_bin | 否 | — | — |
| `state_revision` | BIGINT UNSIGNED | 否 | — | — |
| `processing_state` | VARCHAR(16) ASCII/ascii_bin | 否 | — | — |
| `reason` | VARCHAR(64) ASCII/ascii_bin | 是 | — | — |
| `status_changed_at` | DATETIME(6) | 否 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `fk_chat_ms_conversation` | FOREIGN KEY (user_id, conversation_id) → (conversation_log.user_id, conversation_log.id) |
| `fk_chat_ms_generation` | FOREIGN KEY (user_id, effective_generation_id) → (chat_generation.user_id, chat_generation.generation_id) |
| `ck_chat_message_state` | CHECK processing_state IN ('pending','success','failed','superseded') |
| `ix_chat_ms_generation` | INDEX (user_id, effective_generation_id) |

<a id="chat-generation-message"></a>
### 表名：chat_generation_message

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `generation_id` | CHAR(36), ASCII/ascii_bin | 否 | — | PK |
| `conversation_id` | INTEGER | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | — |
| `ordinal` | INTEGER | 否 | — | — |
| `in_prompt` | BOOLEAN | 否 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_chat_generation_ordinal` | UNIQUE (generation_id, ordinal) |
| `fk_chat_gm_generation` | FOREIGN KEY (user_id, generation_id) → (chat_generation.user_id, chat_generation.generation_id) |
| `fk_chat_gm_conversation` | FOREIGN KEY (user_id, conversation_id) → (conversation_log.user_id, conversation_log.id) |

<a id="chat-resend-quota"></a>
### 表名：chat_resend_quota

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `user_id` | INTEGER | 否 | — | PK; ForeignKey('users.id',ondelete='CASCADE') |
| `batch_sort_seq` | BIGINT UNSIGNED | 否 | — | PK |
| `window_started_at` | DATETIME(6) | 否 | — | — |
| `expires_at` | DATETIME(6) | 否 | — | — |
| `accepted_count` | INTEGER | 否 | ORM 0 | — |

| 约束/索引 | 条件 |
|---|---|
| `ck_chat_resend_count` | CHECK accepted_count BETWEEN 0 AND 2 |
| `ix_chat_resend_expiry` | INDEX (expires_at) |

<a id="chat-lifecycle-effect"></a>
### 表名：chat_lifecycle_effect

MySQL实际类型及ORM默认；`created_at/updated_at`若列出即继承自Dates，不能漏列。

| 字段 | 类型 | 可空 | 默认 | 约束/更新 |
|---|---|---|---|---|
| `created_at` | DATETIME(6) | 否 | ORM datetime.utcnow | — |
| `updated_at` | DATETIME(6) | 否 | ORM datetime.utcnow | onupdate=datetime.utcnow |
| `id` | BIGINT UNSIGNED | 否 | — | PK |
| `user_id` | INTEGER | 否 | — | ForeignKey('users.id',ondelete='CASCADE') |
| `owner_kind` | VARCHAR(8) ASCII/ascii_bin | 否 | — | — |
| `owner_id` | CHAR(36), ASCII/ascii_bin | 否 | — | — |
| `effect_kind` | VARCHAR(32) ASCII/ascii_bin | 否 | — | — |
| `state` | VARCHAR(16) ASCII/ascii_bin | 否 | — | — |
| `attempts` | INTEGER | 否 | ORM 0 | — |
| `next_attempt_at` | DATETIME(6) | 是 | — | — |
| `lease_owner` | CHAR(36), ASCII/ascii_bin | 是 | — | — |
| `lease_until` | DATETIME(6) | 是 | — | — |
| `last_reason` | VARCHAR(64) ASCII/ascii_bin | 是 | — | — |
| `effect_date` | DATE | 是 | — | — |
| `completed_at` | DATETIME(6) | 是 | — | — |

| 约束/索引 | 条件 |
|---|---|
| `uq_chat_effect` | UNIQUE (owner_kind, owner_id, effect_kind) |
| `ck_chat_effect_state` | CHECK state IN ('pending','running','done','failed','unverified') |
| `ck_chat_effect_owner` | CHECK owner_kind IN ('chat','future') |
| `ix_chat_effect_pending` | INDEX (state, next_attempt_at) |
