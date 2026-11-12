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

### 养宠程序互动持久身份（2026-11-07）

复用[养宠数据](../pet-system/data.md)中的 `pet_profile`、`pet_state`、`pet_interaction`、事实、亲近度和活动记录，不建立第二份宠物，也不增加迁移。

- `pet_interaction.payload.completion_mode=programmatic` 标识 Open 发起的抚摸/陪玩；字段缺失视为原 H5 `gesture`，保持历史兼容。模式由服务端入口指定，调用方不可提交。
- `(pet_id,request_key)` 仍是共享唯一键，去重内容包含 kind 与完成模式；即时喂食沿原 actor=player 的身份，H5/Open 相同喂食请求可复用结果。
- `started_at`、`expires_at`、`config_id`、`pet_data_version`、payload 的 `minimum_seconds` 冻结该尝试的计时及依据；`ready_at/retry_after_ms` 由服务端派生，不新增列。
- Open 与 H5 finish 校验各自模式，最终共用 `complete_participation`；只把成功执行写为 `actual_execution`、`participants=[player]`。奖励、活跃、状态更新、表达沿原事务/事实键处理，重放不重复结算。
- MySQL REPEATABLE READ 下，认证可能先建立旧快照。互动回执及表达查询取得账号锁后，对事实、生成任务和宠物状态使用当前读并刷新 ORM 已加载对象，保证并发完成后返回原事件及最新表达状态，不因旧快照误报 `event_not_found`。
- 同一账号锁内，创建互动/喂食的占用检查、奖励历史、活动锚点和离开记录也使用当前读。不同请求键仍只能保留一个未过期占用；奖励计算包含等待锁期间新提交的奖励，已达每日上限或处于冷却时仍可完成但不追加亲近度；并发首次参与或回访不重复创建活动/离开记录。
- API Key 仍按用户归属，换 Key 不换宠物或请求身份。未领养请求可以更新 API Key 的 last_used_at，但不能建立养宠状态或互动事实。
