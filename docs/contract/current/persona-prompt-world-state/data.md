# Persona Data

- 文档 ID：`contract-persona-data`
- 权威状态：`canonical`
- 功能范围：`persona-prompt-world-state`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-002`, `TD-003`, `TD-020`, `TD-021`

<a id="dialogue-shared-context"></a>
### 本轮回复模型可见的上下文

每个聊天 generation/lease 或独立诊断冻结一次人设、可见背景、时间及实际固定模块。人设按 Redis、数据库有效版、代码默认顺序解析，并记录来源、可得版本与读取错误。缺失字段继续缺失，固定关系等级 0 是有效值。历史含最多 30 个完整轮，以 Asia/Shanghai 时间与 JSON 转义正文确定性渲染。

请求绑定的官方计数器选择满足 recent_chat 模块预算及总预算的最长完整后缀。完整渲染留 64 token 安全量，并在实际余量内先为记忆、知识及分隔符留空间。系统提示与人设按各自完整渲染正文（含标题）计量，等于模块上限允许使用，超过单项上限时阻断。固定部分超过总预算或无法确认计数时也阻断。Router 只看最终可见背景，改写与回复共用同一份历史，后续选入维持冻结边界。本轮输入使用原始消息边界，在 user_input 预算内由官方计数器计量含说明的完整回复模块。Router、Step1.5 改写及其降级检索、Step3 回复共用同一份正文。优先保留最新的连续完整消息。最新单条加说明仍超限时先省略说明，正文仍超限才保留该条尾部。两端记录相同的原文半开区间与裁剪状态，回复摘要覆盖实际发送的模块。[检索与路由](../memory-knowledge/api.md#memory-retrieval-protocol)

### 表名：world_state


| 字段名                     | 类型         | 必填  | 默认值    | 说明  |
| ----------------------- | ---------- | --- | ------ | --- |
| id                      | Integer PK | 是   | 自增     |     |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                 | Text       | 是   | -      |     |
| trigger_conversation_id | Integer    | 否   | NULL   | ORM 未声明 `ForeignKey`（仅整型可空） |
| relevance_weight        | Float      | 是   | 1.0    | ORM `default=1.0` |
| created_at              | DateTime   | 是   | utcnow |     |
