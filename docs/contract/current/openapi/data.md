# Openapi Data

- 文档 ID：`contract-openapi-data`
- 权威状态：`canonical`
- 功能范围：`openapi`
- 必读依赖：`contract-shared-conventions`, `contract-chat-emotion-api`, `contract-agent-future-api`
- 相关技术债：`TD-030`, `TD-031`

### 表名：user_timeline_seq


| 字段名      | 类型            | 必填  | 默认值 | 说明   |
| -------- | ------------- | --- | --- | ---- |
| user_id  | Integer PK / FK(users.id, ON DELETE CASCADE) | 是   | -   | 复合主键之一 |
| next_seq | BigInteger    | 是   | 1   | 下一序号（ORM `default=1`） |

### 表名：user_api_keys

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | 自增 |
| user_id | Integer FK(users.id) UNIQUE | 每用户一行 |
| key_hash | String(64) | SHA-256(api_key + OPEN_API_PEPPER) |
| key_prefix | String(24) | 脱敏展示，Admin 原样输出 |
| created_at | DateTime | 首次签发时间（重新生成不刷新） |
| last_used_at | DateTime NULL | 鉴权成功且 ≥60s 节流更新 |
| created_by_admin_id | Integer NULL | 签发管理员 |
