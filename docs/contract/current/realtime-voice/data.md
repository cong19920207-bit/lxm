# 实时语音数据与内部处理契约

- 文档 ID：`contract-realtime-voice-data`
- 权威状态：`canonical`
- 功能范围：`realtime-voice`
- 必读依赖：`contract-shared-conventions`, `contract-admin-security-data`, `contract-relationship-data`, `contract-agent-future-data`
- 相关技术债：[TD-038～043](../../../tech-debt/active/realtime-voice.md)
- 更新：2026-09-29。本文件定义语音自有表和内部处理；HTTP/WS见[接口](api.md)，共享表字段仅在原域定义。

<a id="schema"></a>
## 表结构与迁移边界

12张语音表由 Alembic 管理，普通启动 create_all 明确排除；缺表/列/索引或类型不兼容时启动检查失败关闭。`call_id`应用上限64字符，为弱引用而非物理外键；不据此约定UUID物理排序规则。状态通过应用层封闭值校验，不使用数据库原生ENUM/CHECK。下列类型以MySQL编译结果为准；默认值区分ORM与server_default，`—`表示无默认（非NULL默认）。所有普通时间为UTC，业务日另明确使用北京时间。

迁移顺序：v8a（admin_config草稿revision）→v8b（成长来源列）→v8c（12表）→v8d（账本duration_seconds/quota_date可空）→v8e（记忆extraction_snapshot可空）→v8f（call01_fallback可空）→v8g（能力tested_at/verified_at/expires_at为DATETIME(6)）→v8h（独立总开关）。v8g降级前拒绝丢精度；v8h只在不存在任何同key行时从有效旧global.enabled初始化，否则不覆盖；降级保留总开关及历史。契约整合不执行迁移。

共享表唯一字段定义：[admin_config](../admin-security-accounts/data.md#voice-config-shared)、[relationship_growth_log](../relationship/data.md#voice-growth-shared)、[agent_message](../agent-future/data.md#voice-followup-shared)。

<!-- voice-schema-tables:start -->
<a id="voice_call"></a>
### voice_call

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `user_id` | INTEGER | 否 | FK users.id / ON DELETE RESTRICT |
| `initiated_by` | VARCHAR(16) | 否 | — |
| `status` | VARCHAR(24) | 否 | — |
| `call01_fallback` | BOOL | 是 | — |
| `end_reason` | VARCHAR(64) | 是 | — |
| `provider` | VARCHAR(64) | 是 | — |
| `provider_session_id` | VARCHAR(255) | 是 | — |
| `provider_dialog_id` | VARCHAR(255) | 是 | — |
| `connected_at` | DATETIME | 是 | — |
| `ended_at` | DATETIME | 是 | — |
| `duration_seconds` | INTEGER | 否 | ORM 0 |
| `free_seconds_used` | INTEGER | 否 | ORM 0 |
| `extra_seconds_used` | INTEGER | 否 | ORM 0 |
| `grace_seconds` | INTEGER | 否 | ORM 0 |
| `growth_eligible_seconds` | INTEGER | 否 | ORM 0 |
| `growth_points` | INTEGER | 否 | ORM 0 |
| `sort_seq` | BIGINT | 是 | — |
| `summary_status` | VARCHAR(24) | 否 | — |
| `call_summary` | TEXT | 是 | — |
| `user_emotion` | VARCHAR(64) | 是 | — |
| `assistant_emotion` | VARCHAR(64) | 是 | — |
| `unfinished_topics` | JSON | 是 | — |
| `summary_reasoning` | TEXT | 是 | — |
| `config_snapshot` | JSON | 否 | — |
| `capability_snapshot` | JSON | 否 | — |
| `transcript_retention_days` | INTEGER | 否 | — |
| `generated_retention_days` | INTEGER | 否 | — |
| `transcript_expires_at` | DATETIME | 是 | — |
| `generated_text_expires_at` | DATETIME | 是 | — |
| `reasoning_expires_at` | DATETIME | 是 | — |
| `deletion_fence_at` | DATETIME | 是 | — |
| `deleted_at` | DATETIME | 是 | — |
| `deleted_by` | INTEGER | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_call_generated_expires`：`generated_text_expires_at`。
- `ix_voice_call_reasoning_expires`：`reasoning_expires_at`。
- `ix_voice_call_sort_seq`：`sort_seq`。
- `ix_voice_call_status_ended`：`status, ended_at`。
- `ix_voice_call_transcript_expires`：`transcript_expires_at`。
- `ix_voice_call_user_ended`：`user_id, ended_at`。
- `uk_voice_call_call_id`：UNIQUE `call_id`。

<a id="voice_call_create_idempotency"></a>
### voice_call_create_idempotency

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `user_id` | INTEGER | 否 | FK users.id / ON DELETE RESTRICT |
| `idempotency_key` | VARCHAR(64) | 否 | — |
| `request_payload_sha256` | VARCHAR(64) | 否 | — |
| `call_id` | VARCHAR(64) | 是 | — |
| `ticket_jti` | VARCHAR(64) | 是 | — |
| `ticket_expires_at` | DATETIME | 是 | — |
| `ticket_consumed_at` | DATETIME | 是 | — |
| `replay_expires_at` | DATETIME | 否 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_call_idem_replay_expires`：`replay_expires_at`。
- `uk_voice_call_idem_call`：UNIQUE `call_id`。
- `uk_voice_call_idem_ticket_jti`：UNIQUE `ticket_jti`。
- `uk_voice_call_idem_user_key`：UNIQUE `user_id, idempotency_key`。

<a id="voice_call_turn"></a>
### voice_call_turn

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `turn_index` | INTEGER | 否 | — |
| `question_id` | VARCHAR(64) | 是 | — |
| `reply_id` | VARCHAR(64) | 是 | — |
| `user_text_final` | TEXT | 是 | — |
| `user_asr_confidence` | FLOAT | 是 | — |
| `assistant_text_generated` | TEXT | 是 | — |
| `assistant_text_effective` | TEXT | 是 | — |
| `effective_text_evidence` | VARCHAR(32) | 否 | — |
| `assistant_interrupted` | BOOL | 否 | ORM False |
| `played_audio_ms` | INTEGER | 是 | — |
| `playback_completed_at` | DATETIME | 是 | — |
| `turn_status` | VARCHAR(24) | 否 | — |
| `memory_status` | VARCHAR(24) | 否 | — |
| `user_content_safety_status` | VARCHAR(24) | 否 | — |
| `assistant_content_safety_status` | VARCHAR(24) | 否 | — |
| `user_crisis_status` | VARCHAR(24) | 否 | — |
| `assistant_crisis_status` | VARCHAR(24) | 否 | — |
| `started_at` | DATETIME | 否 | — |
| `finalized_at` | DATETIME | 是 | — |
| `effective_text_expires_at` | DATETIME | 是 | — |
| `generated_text_expires_at` | DATETIME | 是 | — |
| `effective_text_cleared_at` | DATETIME | 是 | — |
| `generated_text_cleared_at` | DATETIME | 是 | — |
| `content_clear_reason` | VARCHAR(32) | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_turn_call_finalized`：`call_id, finalized_at`。
- `ix_voice_turn_effective_expires`：`effective_text_expires_at`。
- `ix_voice_turn_generated_expires`：`generated_text_expires_at`。
- `uk_voice_turn_call_index`：UNIQUE `call_id, turn_index`。
- `uk_voice_turn_call_question`：UNIQUE `call_id, question_id`。

<a id="voice_capability_evidence"></a>
### voice_capability_evidence

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | BIGINT | 否 | PK / 自增 |
| `evidence_report_id` | VARCHAR(36) | 否 | — |
| `evidence_run_id` | VARCHAR(36) | 否 | — |
| `capability_key` | VARCHAR(64) | 否 | — |
| `verification_result` | VARCHAR(16) | 否 | — |
| `source_type` | VARCHAR(32) | 否 | — |
| `provider_profile` | VARCHAR(255) | 否 | — |
| `model_version` | VARCHAR(128) | 否 | — |
| `protocol_profile` | VARCHAR(128) | 否 | — |
| `adapter_version` | VARCHAR(128) | 否 | — |
| `sdk_version` | VARCHAR(128) | 否 | — |
| `evidence_suite_version` | VARCHAR(128) | 否 | — |
| `evidence_fingerprint` | VARCHAR(64) | 否 | — |
| `evidence_payload` | JSON | 否 | — |
| `report_sha256` | VARCHAR(64) | 否 | — |
| `tested_at` | DATETIME(6) | 否 | — |
| `verified_at` | DATETIME(6) | 是 | — |
| `evidence_ttl_days_snapshot` | INTEGER | 否 | — |
| `expires_at` | DATETIME(6) | 是 | — |
| `operator_id` | BIGINT | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_evidence_capability_created`：`capability_key, created_at`。
- `ix_voice_evidence_fingerprint_result_expires`：`evidence_fingerprint, verification_result, expires_at`。
- `ix_voice_evidence_run`：`evidence_run_id`。
- `uk_voice_evidence_report`：UNIQUE `evidence_report_id`。
- `uk_voice_evidence_run_capability`：UNIQUE `evidence_run_id, capability_key`。

<a id="voice_crisis_record"></a>
### voice_crisis_record

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `turn_index` | INTEGER | 否 | — |
| `direction` | VARCHAR(32) | 否 | — |
| `matched_keyword` | VARCHAR(255) | 是 | — |
| `content_plaintext` | TEXT | 是 | — |
| `match_status` | VARCHAR(32) | 否 | — |
| `is_persona_incident` | BOOL | 否 | — |
| `expires_at` | DATETIME | 否 | — |
| `cleared_at` | DATETIME | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_crisis_call_created`：`call_id, created_at`。
- `ix_voice_crisis_expires`：`expires_at`。
- `uk_voice_crisis_call_turn_direction`：UNIQUE `call_id, turn_index, direction`。

<a id="voice_followup_job"></a>
### voice_followup_job

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `user_id` | INTEGER | 否 | FK users.id / ON DELETE RESTRICT |
| `candidate_due_at` | DATETIME | 否 | — |
| `due_at` | DATETIME | 否 | — |
| `latest_due_at` | DATETIME | 否 | — |
| `content` | TEXT | 否 | — |
| `content_type` | VARCHAR(32) | 否 | — |
| `status` | VARCHAR(24) | 否 | — |
| `cancel_reason` | VARCHAR(255) | 是 | — |
| `agent_message_id` | INTEGER | 是 | — |
| `relationship_stage_snapshot` | VARCHAR(24) | 否 | — |
| `schedule_config_version` | VARCHAR(64) | 否 | — |
| `timezone_snapshot` | VARCHAR(64) | 否 | — |
| `allowed_window_snapshot` | JSON | 否 | — |
| `jitter_minutes` | INTEGER | 否 | — |
| `attempt_count` | INTEGER | 否 | ORM 0 |
| `next_retry_at` | DATETIME | 是 | — |
| `fail_reason` | VARCHAR(255) | 是 | — |
| `lease_owner` | VARCHAR(128) | 是 | — |
| `lease_expires_at` | DATETIME | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_followup_status_due`：`status, due_at`。
- `ix_voice_followup_status_retry`：`status, next_retry_at`。
- `ix_voice_followup_user_due`：`user_id, due_at`。
- `uk_voice_followup_call_type`：UNIQUE `call_id, content_type`。

<a id="voice_memory_job"></a>
### voice_memory_job

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `turn_id` | INTEGER | 否 | FK voice_call_turn.id / ON DELETE RESTRICT |
| `turn_index` | INTEGER | 否 | — |
| `pipeline_version` | VARCHAR(64) | 否 | — |
| `status` | VARCHAR(24) | 否 | — |
| `attempt_count` | INTEGER | 否 | ORM 0 |
| `next_retry_at` | DATETIME | 是 | — |
| `extraction_snapshot` | JSON | 是 | — |
| `fail_reason` | VARCHAR(255) | 是 | — |
| `lease_owner` | VARCHAR(128) | 是 | — |
| `lease_expires_at` | DATETIME | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_memory_job_call_turn`：`call_id, turn_index`。
- `ix_voice_memory_job_status_retry`：`status, next_retry_at`。
- `uk_voice_memory_job_turn_pipeline`：UNIQUE `turn_id, pipeline_version`。

<a id="voice_memory_trace"></a>
### voice_memory_trace

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `turn_index` | INTEGER | 否 | — |
| `doc_id` | VARCHAR(100) | 否 | — |
| `memory_type` | VARCHAR(32) | 否 | — |
| `stable_key` | VARCHAR(255) | 否 | — |
| `pipeline_version` | VARCHAR(64) | 否 | — |
| `written_at` | DATETIME | 否 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_memory_trace_call_turn`：`call_id, turn_index`。
- `ix_voice_memory_trace_doc`：`doc_id`。
- `uk_voice_memory_trace_call_turn_doc_pipeline`：UNIQUE `call_id, turn_index, doc_id, pipeline_version`。

<a id="voice_metric_daily"></a>
### voice_metric_daily

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `business_date` | DATE | 否 | — |
| `metric_name` | VARCHAR(100) | 否 | — |
| `dimension_hash` | VARCHAR(64) | 否 | — |
| `dimension_json` | JSON | 否 | — |
| `metric_value` | FLOAT | 否 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_metric_name_day`：`metric_name, business_date`。
- `uk_voice_metric_day_name_dimension`：UNIQUE `business_date, metric_name, dimension_hash`。

<a id="voice_postprocess_job"></a>
### voice_postprocess_job

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `job_type` | VARCHAR(64) | 否 | — |
| `status` | VARCHAR(24) | 否 | — |
| `attempt_count` | INTEGER | 否 | ORM 0 |
| `next_retry_at` | DATETIME | 是 | — |
| `fail_reason` | VARCHAR(255) | 是 | — |
| `lease_owner` | VARCHAR(128) | 是 | — |
| `lease_expires_at` | DATETIME | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_postprocess_status_retry`：`status, next_retry_at`。
- `uk_voice_postprocess_call_type`：UNIQUE `call_id, job_type`。

<a id="voice_quota_account"></a>
### voice_quota_account

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `user_id` | INTEGER | 否 | FK users.id / ON DELETE RESTRICT |
| `free_quota_date` | DATE | 否 | — |
| `free_remaining_seconds` | INTEGER | 否 | — |
| `extra_remaining_seconds` | INTEGER | 否 | — |
| `version` | INTEGER | 否 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_quota_free_date`：`free_quota_date`。
- `uk_voice_quota_user`：UNIQUE `user_id`。

<a id="voice_usage_ledger"></a>
### voice_usage_ledger

| 字段 | MySQL类型 | 可空 | 默认 / 约束 |
|---|---|---|---|
| `id` | INTEGER | 否 | PK / 自增 |
| `call_id` | VARCHAR(64) | 否 | — |
| `segment_seq` | INTEGER | 否 | — |
| `free_seconds_used` | INTEGER | 否 | — |
| `extra_seconds_used` | INTEGER | 否 | — |
| `usage_type` | VARCHAR(32) | 否 | — |
| `duration_seconds` | INTEGER | 是 | — |
| `quota_date` | DATE | 是 | — |
| `created_at` | DATETIME | 否 | ORM utcnow |
| `updated_at` | DATETIME | 否 | ORM utcnow |

索引/唯一约束：
- `ix_voice_usage_call_created`：`call_id, created_at`。
- `uk_voice_usage_call_segment`：UNIQUE `call_id, segment_seq`。
<!-- voice-schema-tables:end -->

<a id="states"></a>
## 应用层状态

| 对象 | 允许值 |
|---|---|
| call.initiated_by | user / character |
| call.status | deciding / ringing / connected / reconnecting / ending / ended / missed / failed / cancelled |
| summary_status | pending / ready / failed / not_applicable |
| effective_text_evidence | full / exact_played / confirmed_sentences / none |
| turn.status | collecting / finalized / interrupted / aborted |
| memory_status | skipped / pending / processing / success / failed / cancelled |
| content_safety_status | pending / passed / matched / error_allowed |
| crisis_status | pending / passed / matched / suspected / isolation_failed |
| content_clear_reason | expired / admin_deleted |
| postprocess.status | pending / processing / success / partial_success / failed / cancelled |
| followup.content_type | topic_continuation / emotional_followup / missed_explanation |
| followup.status | pending / processing / sent / cancelled / failed |
| followup.relationship_stage | stranger / friend / intimate / soulmate |
| memory.type | user / character_private |
| capability.result / source | passed / failed / error；phase0_import / admin_capability_test |

end_reason等开放字符串不擅自转成封闭数据库枚举。历史新增可空字段不能把NULL解释为false、0或已完成。

<a id="configuration"></a>
## 配置、能力与冻结

- `voice_call_config`、`voice_call_script`通过共享admin_config版本/草稿机制管理；独立 `voice_call_master_switch` 为运行总开关事实源，旧global.enabled仅兼容。总开关缺失/无效时关闭，发布校验和API见[接口](api.md#master-quota)。维护、软停、灰度allowlist和test_user_ids继续独立判断。
- 默认补全不修改已存内容/hash；通话冻结config/script版本、哈希、能力有效值、上下文资料及相关模板；历史snapshot为空按兼容投影，不以当前配置伪造旧快照。凭据只存引用，不把环境密钥、音频、危机原文存进快照。
- 默认S2S为doubao、model_version `2.2.0.0`、adapter `voice_adapter_v1`、protocol `doubao_dialog_v3_pcm`、credential_ref `DOUBAO_S2S_ACCESS_KEY`；实际行为取已发布配置。声明值不等于已验证能力。
- 六能力：`supports_current_turn_rag_gate`、`supports_reply_cancel`、`supports_context_truncate`、`supports_playback_text_mapping`、`supports_sentence_playback_ack`、`supports_session_reconnect`。六维为provider_profile/model_version/protocol_profile/adapter_version/sdk_version/evidence_suite_version，以canonical JSON SHA-256计算指纹。按当前六维指纹、证据结果、版本、有效期及effective_scope联合解析；TTL7～90天，跨指纹/过期/未通过不可据此授权all。旧历史passed不自动开启能力，测试范围不能扩散到普通用户。
- 两套整包含schema_version/version/content_sha256，各key独立版本且唯一草稿；发布/回滚生成新版本，成功同步active_config与300秒publish_monitor。seed逐key幂等，已有active不覆盖；禁止percentage灰度、用户级能力灰度、固定记忆ID和Mock/弱网实验配置进入正式schema。
- persona_ref只保存已发布config_key/version/hash；凭据仅允许环境变量引用，禁止密钥值/URL认证信息/嵌套泄漏。config读取super_admin/tech_ops可见非敏感引用和配置状态，其他角色只布尔；credential_revision_ref所有角色隐藏。发布/回滚DB或Redis失败按补偿恢复原状态，change_note审计只保留长度/hash。
- 运行读取校验Redis→MySQL→规范完整默认；规范fallback版本0/published_at=null，不按字段混拼。AC77的服务端Redis最后确认发布envelope无TTL、不含人格正文：提交前安全失效旧锚，commit成功后写新锚；提交前失败恢复，提交后锚写失败保持无锚。无可信DB/锚时拒绝新快照，孤儿缓存版本不得消费。独立总开关仍以其已发布行和失败关闭规则为准，不被旧global.enabled离线锚绕开。
- 内部原整包导入核验同run六项、record/bundle哈希与全部严格证据；另允许从原包显式选择report-id，先验整包身份再按run事务追加选中证据/草稿引用/审计，保留未选原因。原记录重放幂等，身份冲突或时间回读损失回滚；不拼造跨run整包。v3～v5schema与v7/v8/v9实验运行版本分开，既有证据不倒改。没有公开import/更新/任意删除证据API。
- 会前包、CALL-01、连接和交互参数见[运行接口语义](api.md#runtime)；`tone_instruction`与`explicit_exit`尚未完成运行消费，分别保留TD-039/040。profile测连发布联动与force-test消费分别保留TD-041/042，不以表单存在宣称运行能力已齐。

<a id="lifecycle"></a>
## 通话、配额、账本与成长

创建先预检、取用户租约，再以24小时SQL幂等记录锁定请求哈希与call。租约、owner和设备共同保证单用户并发；票据与缓存不能替代SQL事实。状态终结、计费账本、账户、时间线卡片和成长使用共同finalizer事务，先按固定顺序锁用户/call/账本与账户，再释放owner/缓存。无法可靠恢复计量时不猜秒数补账（TD-038）。

- 服务端单调时钟记录connected片段，保留小数余量，不按心跳重复向上取整；跨北京时间零点拆到账本quota_date。reconnecting暂停计量；静音不计成长；grace不计费/不计成长。硬上限默认3600秒从首次connected_at计；免费默认300秒/日，grace默认30秒，均以当前发布值和通话规则为准。
- 读余额以当前发布daily_free_seconds减当日已用免费秒数，再加额外剩余秒数；存量账户的旧daily值不会屏蔽新发布额度。发布300→600后，已用100显示免费剩500，未用显示600；不清空已用或额外时长。GET为只读投影，结算/加时才更新账户。
- 账本区分free/extra/grace、有效成长秒数与用户计时总duration，唯一键约束重复结算。v8d旧行duration/quota_date为NULL时保留unknown，不能推断日归属；provider usage保留单位事实，不当免费时长或财务成本。
- 成长默认每30个有效秒5分、北京时间每日100分上限，只认合格有效文本；技术失败/无有意义互动不增长。终结同事务按call来源幂等，更新关系最近互动与主动次数事实。详情的今日语音分数和文字成长边界见[关系接口](../relationship/api.md#voice-growth)。

<a id="safety"></a>
## 安全与危机隔离

用户ASR final和助手输出在普通持久化前分别做安全/危机判断。危机原文写voice_crisis_record隔离、只留专属短期证据；普通回合/记忆/摘要/日志只留允许事实或隔离状态。普通内容安全故障可按既定error_allowed行为处理，不等于危机隔离失败可以放行。危机隔离写入失败保持失败状态，不反向把原文塞回正常链。

危机词库优先缓存，缓存不可用/无效时有界读取唯一有效发布行，满足条件才修复缓存；数据库也无有效版本时新建通话失败关闭。有效但版本内容不一致的缓存不擅自替换。此行为合并后续已确认实现，取代早期草案“缓存一失效就阻断”的描述，不改写原PRD/STEP。

普通安全匹配复用纯匹配入口，语音独立无正文计数，不改文字旧计数；matched/error_allowed任一侧都不进入memory pending。危机隔离同事务清普通turn的用户final和助手generated/effective；后续有效播放前缀只补同一隔离记录且保留原到期。未播放generated尾文也须先检查，不能据此伪造effective事故。单通提交后只发一次脱敏crisis_detected信号，不干预角色播放。

危机读取super_admin专属、no-store且审计；默认保留30天，到期清原文。用户危机ERROR、AI人格事故CRITICAL日志仅带必要元信息；当前未新增外部消息发送渠道。公开资源通过H5状态/时间线投影，不提供用户侧危机原文检索或导出。

<a id="session-context"></a>
## 本通上下文

Redis `voice:session_context:{call_id}`，schema v1，默认32条/65536字节、TTL7200秒。只允许connected/reconnecting且owner有效、未删除/未终结的通话读写；对象包含turn/candidate/correction/unfinished_topic/recalled_topic/recall_result。按轮序与资料ID覆盖/淘汰，不跨call当长期记忆使用。

迟到召回结果以 `visible_from=当前轮+1` 和 `delivery_pending` 管理；旧缓存缺少该字段时按visible_from大于来源turn推断待投递。下一轮安全窗口用原子版本消费，发送失败保留，删除/过期后拒绝复活。持久化向量来源语义另见[记忆域](../memory-knowledge/api.md#last-write-source)。

<a id="memory"></a>
## 逐轮记忆与补偿

VOICE-MEM-01只用安全通过的用户final和有效助手文本。`MEMORY_RULES`是当前服务端执行模板，冻结配置补充写入提取快照；提示词里的说明/JSON示例是模型输入资料，运行解析对象是模型回复。模型回复必须严格JSON，不容忍额外解释文字，不把提示词示例当成真实记忆。

- 输入保留原始用户事实、此前合格用户final截取最多2000字符（字段名previous_turn_summary不意味着调用了总结模型）、关系级别/描述及本通候选记忆；不喂未知生成正文或危机原文。
- 输出最多5个原子项，只允许user/character_private以及有效Stable Key和content。用户明确提供或确认才当事实，保留条件、计划和不确定性；助手一次客套回答不能变成双方长期约定。输入ASR显式合法confidence低于0.5或非法值跳过，缺省不编造分数。输出原子经共享key/value、去重和再次安全校验；非法项丢弃而不触发模型重试。
- upsert沿用现有doc_id/embedding规则；整对象写入，成功才记录voice_memory_trace。不改Stable Key、排名或四路配额；`last_write_source`只用于向量溯源，旧数据不回填。
- 每回合/pipeline幂等任务；抽取成功即持久化ready的 `extraction_snapshot`，向量重试只复用此快照，不重新问模型。extracting阶段崩溃且无可信ready结果，不自动重提取；快照/正文过期、删除围栏或owner变更拒绝执行。
- 默认请求45秒、模型墙钟50秒，任务lease210秒；最多2次退避重试（1000/5000ms）。同call按序，跨call同用户同doc加锁并核对trace顺序；没有跨所有文字/后台渠道的全局写序保证。
- 管理补跑只对符合条件failed任务开放；任务列表不暴露extraction_snapshot或正文。每秒poll最多消费8通，正常消费后扫描最多8个终态call补偿漏单；voice_postprocess_job的memory_compensation按(call_id,job_type)幂等，补任务/补偿事实/无正文稳定键集合审计同事务；成功后新发现漏单仍可补缺。删除先锁所有记忆任务再设围栏，防止迟到写回。定向测试通过不等于新一轮真实模型质量验证，历史24/24样本仅在其覆盖范围复用。

<a id="postprocess"></a>
## 摘要、卡片、主动消息与跨模态

摘要由voice_postprocess_job独立处理，冻结summary模型/Prompt；默认DeepSeek，不调用实时语音Provider生成摘要。仅用合格有效事实，推理留私有诊断。合格接通默认至少15秒；不合格为not_applicable。ready/失败只更新原call卡片对应字段，不创建新的sort_seq。摘要过期/删除不回显正文。

voice_followup_job独立管理topic_continuation/emotional_followup/missed_explanation；成功同事务写既有agent_message的 `VOICE_FOLLOWUP`，不占Future槽。未接默认文案“刚刚没接到你的电话，晚一点我们再聊呀。”在创建时冻结，不调用摘要模型来编写未接说明。

发送时间按北京时间四关系阶段的非空窗口、0～20分钟抖动与最多24小时延期；执行前重查状态/保留期/围栏/时间窗/用户新消息/同话题/幂等。耗时话题判断在事务外，回到锁内再次比较事实。按已确认口径绕过旧P0～P4的8条/30分钟门禁，不另加限额；成功仍原子计入UTC日主动计数。sent后的count_pending补偿只补计数，不再发送消息。它会经过复用的消息处理子链，开发里程碑通过不代表全仓Step8相关失败全部解决。

日记与P0活动判定以connected_at纳入语音活动；正文只使用未删除、未过期的ready摘要，否则非空的无正文通话事实。不会把语音推理写入旧三层情绪。共享接口的唯一定义见[日记](../diary/api.md#voice-activity)、[Agent](../agent-future/api.md#voice-followup)、[H5时间线](../chat-emotion/api.md#voice-timeline)。

<a id="retention"></a>
## 保留期与删除

默认effective正文180天、generated/reasoning/crisis原文30天、job90天，以冻结/发布规则及字段expires_at判断。过期投影立即隐藏正文，后台清理任务随后物理清内容；不可把“清理尚未跑”解释为仍可读取。管理删除先审计尝试、锁任务并设置call删除围栏，取消未完成任务，清回合/摘要/私有诊断/缓存。保持必要call元数据、账本、成长、已成功向量写入trace及已发送agent_message；删除通话不是撤回所有跨域衍生事实。账号注销全链路清除为P1之外的TD-V-07，AC50不在本次验收集合。

<a id="metrics"></a>
## 日聚合与观测口径

| 指标 | 权威分母/来源 |
|---|---|
| daily_call_count | 北京时间业务日created_at创建的call数 |
| connect_rate / missed_rate / failure_rate | 同日创建call队列为统一分母；接通事实、missed、failed各按持久化终态/事实统计 |
| avg_duration_seconds | 已结束且接通过的通话时长平均；不是Provider usage |
| billable_seconds | 按ledger.quota_date归属的free+extra秒，排除grace；跨日分片按账本日 |
| estimated_cost | 有效配置单价×计费量；未配置或基础量未知返回null |
| call01_fallback_rate | 实际call01_fallback事实；旧NULL导致未知时返回null，不当0 |
| memory_success_rate / summary_success_rate | 各任务created_at业务日、唯一任务最终success与耗尽重试failed；pending/processing标为provisional，不以重试发送次数当分母 |

历史缺quota_date等字段保留unknown/null原因，不能用call日期替代账本归属。daily读持久化源现场算；history读voice_metric_daily中 `current_durable_state` 的日聚合，可随后续完成重算，不是假称不可变历史快照。metric_date/name/dimension唯一，upsert防重。

模拟价格仅显式选择时为CNY 0.06/分钟，单独dimension hash并标simulated；常规未配置价格仍null。模拟账单最多31个业务日、同周期/币种、非负金额，ROUND_HALF_UP6位，只预览不持久化真实财务数据。

Redis观测按**UTC观测发送日**保留172800秒，包含重试，不替代业务日任务统计。reply_observed按session/question/reply去重，最多4096个标识；primary/extra/overflow分开，额外回复率只统计能力有效样本。截断分success/failure/unknown且校验能力；effective证据分布是观测快照样本，混杂/未知不能伪造成确定比率。Provider usage单位未确认时cost ratio保持null。各阶段同期事件覆盖配置fallback、创建/网关/状态/播放/打断、危机、安全、记忆/召回、摘要/卡片/成长/followup、后台授权/结果/审计/固定投影、保留期/删除。独立voice.config.fallback.v1只允许两key和封闭来源/结果维度，TTL172800秒。持久化转换事件在commit后发送，重放不伪增send/insert/expiry；观测失败不反向改变业务结果。向量source_observation只说明写前250ms有界观察，unknown不是0冲突，不能据此算精确跨渠道并发覆盖率。事件字典与样本来源由metric_read/observation服务定义。

<a id="schedulers"></a>
## 调度

| 任务 | 周期 | 行为边界 |
|---|---|---|
| voice reconcile | 5秒 | 活跃owner/租约核对，不猜测恢复结算 |
| crisis expiry | 1分钟 | 专属原文到期清理 |
| memory jobs | 1秒 | 顺序/lease/快照/删除围栏保护 |
| summary jobs | 1秒 | 有效事实摘要与状态回写 |
| followup jobs | 1秒 | 时窗/幂等发送及计数补偿 |
| retention cleanup | 1分钟 | 正文和任务清理，保留必要账本 |
| daily metrics | 1分钟 | 先昨日，再扫描最多7个历史已结束业务日；游标循环、失败保留重试；普通和显式模拟维度都物化 |

APScheduler采用single-instance/coalesce避免同进程叠跑；跨进程仍依赖数据库/Redis幂等与lease，不承诺调度器本身是分布式锁。
