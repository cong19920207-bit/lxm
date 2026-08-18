# Core User Auth Data

- 文档 ID：`contract-core-user-auth-data`
- 权威状态：`canonical`
- 功能范围：`core-user-auth`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-001`, `TD-024`, `TD-025`

### 表名：users


| 字段名                | 类型          | 必填  | 默认值    | 说明                               |
| ------------------ | ----------- | --- | ------ | -------------------------------- |
| id                 | Integer PK  | 是   | 自增     | 用户 ID                            |
| username           | String(20)  | 是   | -      | 唯一索引（`unique=True`，ORM）            |
| password_hash      | String(255) | 是   | -      | 密码哈希                             |
| created_at         | DateTime    | 是   | utcnow | 注册时间                             |
| last_login_at      | DateTime    | 否   | NULL   | 最后登录                             |
| relationship_level | Integer     | 是   | 0      | 关系等级 0–3（与 relationship 表存在并行字段） |
| growth_value       | Integer     | 是   | 0      | 成长值（与 relationship 表存在并行字段）      |
| is_banned          | Boolean     | 是   | False  | 是否封禁                             |
| login_fail_count   | Integer     | 是   | 0      | 连续登录失败次数                         |
| locked_until       | DateTime    | 否   | NULL   | 锁定截止时间                           |
| last_feed_entered_at | DateTime  | 否   | NULL   | 最近进入朋友圈时间（生活流；`POST /api/feed/enter` 写 **`feed_now()`** 北京墙钟；用于 `has_new`） |
