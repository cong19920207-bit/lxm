# Diary Data

- 文档 ID：`contract-diary-data`
- 权威状态：`canonical`
- 功能范围：`diary`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-006`, `TD-007`, `TD-013`, `TD-014`, `TD-018`

### 表名：ai_diary


| 字段名                            | 类型         | 必填  | 默认值    | 说明    |
| ------------------------------ | ---------- | --- | ------ | ----- |
| id                             | Integer PK | 是   | 自增     |       |
| user_id                        | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                        | Text       | 是   | -      |       |
| relationship_level_at_creation | Integer    | 是   | -      | 生成时等级 |
| is_read                        | Boolean    | 是   | False  |       |
| covers_beijing_date            | Date       | 否   | NULL   | 日记内容覆盖的北京日历日；旧数据可为 NULL（不回填）；与 `user_id` 唯一约束防重复 |
| created_at                     | DateTime   | 是   | utcnow |       |
