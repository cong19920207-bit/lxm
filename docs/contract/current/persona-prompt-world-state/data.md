# Persona Data

- 文档 ID：`contract-persona-data`
- 权威状态：`canonical`
- 功能范围：`persona-prompt-world-state`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-002`, `TD-003`, `TD-020`, `TD-021`

### 表名：world_state


| 字段名                     | 类型         | 必填  | 默认值    | 说明  |
| ----------------------- | ---------- | --- | ------ | --- |
| id                      | Integer PK | 是   | 自增     |     |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                 | Text       | 是   | -      |     |
| trigger_conversation_id | Integer    | 否   | NULL   | ORM 未声明 `ForeignKey`（仅整型可空） |
| relevance_weight        | Float      | 是   | 1.0    | ORM `default=1.0` |
| created_at              | DateTime   | 是   | utcnow |     |
