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
| memory_injected    | JSON       | 否   | NULL   | **仅历史字段，已停用**：列保留，新 user 行恒 `null`（M11/P7，长记忆第一套下线后 send 不再做向量检索/注入计算） |
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
