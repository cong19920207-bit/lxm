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
