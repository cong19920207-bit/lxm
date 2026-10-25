# Relationship Data

- 文档 ID：`contract-relationship-data`
- 权威状态：`canonical`
- 功能范围：`relationship`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-005`

### 表名：relationship


| 字段名                    | 类型                   | 必填  | 默认值    | 说明       |
| ---------------------- | -------------------- | --- | ------ | -------- |
| id                     | Integer PK           | 是   | 自增     |          |
| user_id                | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`，`index=True`） |
| level                  | Integer              | 是   | -      | 关系等级 0–3 |
| growth_value           | Integer              | 是   | -      | 成长值      |
| last_interaction_at    | DateTime             | 否   | NULL   | 上次互动     |
| consecutive_login_days | Integer              | 是   | 0      | 连续登录天数（ORM `default=0`） |
| updated_at             | DateTime             | 是   | utcnow | `onupdate=utcnow` |
| relation_description   | Text                 | 否   | NULL   | 关系描述（R-MEM-05，Step6 记忆写回） |
| user_real_name         | String(50)           | 否   | NULL   | 用户真实称呼（R-MEM-05） |
| user_hobby_name        | String(50)           | 否   | NULL   | 用户昵称（R-MEM-05） |
| user_description       | Text                 | 否   | NULL   | 用户印象（R-MEM-05） |
| character_purpose      | Text                 | 否   | NULL   | 角色当前回应策略（R-MEM-07） |
| character_attitude     | Text                 | 否   | NULL   | 角色当前态度（R-MEM-07） |
| future_timestamp       | Integer              | 否   | NULL   | Future 预约时间戳（R-FUT-02） |
| future_action          | String(200)          | 否   | NULL   | Future 预约意图摘要（R-FUT-02） |
| future_slot_version    | BIGINT UNSIGNED      | 是   | ORM/SQL 0 | 同用户槽版本；所有写入/清理（含同值 ABA）递增，见[条件消费](#future-slot-version) |
| proactive_times        | Integer              | 是   | 0      | 主动消息计数，上限 3（R-FUT-03，`server_default="0"`） |
| like_aware_special_used_count | Integer       | 是   | 0      | 生活流·点赞感知 IM 特殊档已用次数（入队成功 +1；可后台重置） |
| read_aware_special_used_count | Integer       | 是   | 0      | 生活流·已读感知 IM 特殊档已用次数（入队成功 +1；可后台重置） |
| has_ever_commented_feed | Integer             | 是   | 0      | 生活流·是否已发生过全局首次评论（首次评论 `due_at` 强制 +30s；置 1 后不回退） |

### 表名：relationship_growth_log


| 字段名         | 类型         | 必填  | 默认值    | 说明       |
| ----------- | ---------- | --- | ------ | -------- |
| id          | Integer PK | 是   | 自增     |          |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| action_type | String(30) | 是   | -      | dialog 等 |
| points      | Integer    | 是   | -      | 本次得分     |
| created_at  | DateTime   | 是   | utcnow |          |

<a id="voice-growth-shared"></a>
语音来源增量（v8b，原表新增，历史行允许NULL）：

| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| source_type | String(64) | 是 | NULL | 来源类型 |
| source_id | String(64) | 是 | NULL | 来源幂等ID |
| eligible_seconds | Integer | 是 | NULL | 合格成长秒数 |
| business_date | Date | 是 | NULL | 北京时间业务日 |

`uk_growth_source`为(source_type, source_id)唯一索引；历史NULL可并存。语音按call来源去重，结算见[语音数据](../realtime-voice/data.md#lifecycle)，文字成长不据此补造source值。

### 表名：relationship_level_history


| 字段名         | 类型         | 必填  | 默认值    | 说明  |
| ----------- | ---------- | --- | ------ | --- |
| id          | Integer PK | 是   | 自增     |     |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| from_level  | Integer    | 是   | -      | 升级前等级 |
| to_level    | Integer    | 是   | -      | 升级后等级 |
| achieved_at | DateTime   | 是   | utcnow |     |

### 表名：relationship_change_history


| 字段名            | 类型                   | 必填  | 默认值    | 说明       |
| ---------------- | -------------------- | --- | ------ | -------- |
| id               | BigInteger PK（MySQL BIGINT，SQLite INTEGER 兼容） | 是   | 自增     |          |
| relationship_id  | Integer FK(relationship.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| user_id          | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 冗余便于查询（`index=True`） |
| field_name       | String(50)           | 是   | -      | 被更新的字段名（snake_case，如 `relation_description`） |
| old_value        | Text                 | 否   | NULL   | 更新前的值   |
| new_value        | Text                 | 否   | NULL   | 更新后的值   |
| trigger_source   | String(20)           | 是   | step6  | 触发来源（`server_default="step6"`） |
| round_id         | String(36)           | 否   | NULL   | 关联的对话轮次 ID |
| created_at       | DateTime             | 是   | utcnow | 写入时间    |

- **设计语义**：append-only 表，仅 INSERT 不做 UPDATE/DELETE（R-L1L3-05）；经 STEP-008 明确授权的 S15 清理仅删除 `relation_description/user_real_name/user_hobby_name/user_description/character_purpose/character_attitude` 对应历史，保留其它字段历史。此为已实现维护工具例外，不表示已执行业务清理。
- **索引**：`(user_id, created_at)` 组合索引（`ix_rel_change_user_created`），支持按用户 + 时间排序查询
- **关联需求**：R-L1L3-05（变更历史）、R-MEM-05（6 个扩展字段全部参与历史记录）
- **触发来源**：本期仅 `step6`（Step6 自动更新触发写入）；后续如启用管理后台手动编辑，可扩展其他来源标记（R-L1L3-07 本期不做）

<a id="future-slot-version"></a>
### Future 槽的同用户版本

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

future_slot_version 为 MySQL BIGINT UNSIGNED，非空，ORM/SQL默认0，迁移随v9f引入。所有槽写/清递增，包括同值ABA；消费捕获(user,version,timestamp,action)，不得只按当前正文认同一槽。Step8的Step6条件清理及原版本CAS唯一见[Future接口](../agent-future/api.md#future-slot-cas)，成功身份/消息和效果审计见[Future数据](../agent-future/data.md#future-consumption-data)。普通主文字future_clear_slot默认None，不改变其原标量输入。
