# Memory Knowledge Data

- 文档 ID：`contract-memory-knowledge-data`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### 表名：memory


| 字段名                     | 类型          | 必填  | 默认值    | 说明                    |
| ----------------------- | ----------- | --- | ------ | --------------------- |
| id                      | Integer PK  | 是   | 自增     |                       |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`          |
| content                 | Text        | 是   | -      |                       |
| importance_score        | Float       | 是   | -      |                       |
| source                  | String(20)  | 是   | -      | auto / manual / admin |
| dashvector_id           | String(100) | 否   | NULL   | 向量侧 ID（`index=True`） |
| is_deleted              | Boolean     | 是   | False  | 软删除                   |
| created_at              | DateTime    | 是   | utcnow |                       |
| updated_at              | DateTime    | 是   | utcnow | `onupdate=utcnow`     |
| expires_at              | DateTime    | 否   | NULL   | 过期时间                  |

- **运行时口径（TD-022 已清偿，表结构保留）**：长记忆第一套写入已下线，H5/Admin 列表改读 Step6 用户向量；`memory` 表仍在 ORM/库中，主链不再 `extract_and_save`。存量清理与表删除见 TD-022。
