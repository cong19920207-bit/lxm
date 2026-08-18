# agent-future 技术债

- 文档 ID：`tech-debt-agent-future`
- 权威状态：`canonical`
- 功能范围：`agent-future`
- 必读依赖：无
- 相关技术债：`TD-004`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-004] Agent 规则（agent_rules）管理端可配、运行时未读取

- 配置：`admin_config.config_key = agent_rules`（`triggers` + `decision_engine`），发布后 Redis `active_config:agent_rules` 同步更新；管理接口见 `backend/routers/admin/agent_mgmt.py`。
- 问题：`AgentService`（`backend/services/agent_service.py`）中 **P1 / P2 / P4 触发条件**、**每日触发次数**、**两次间隔**、**行动评分阈值**等均为**代码内写死**，**不读取**上述配置；运营在后台修改触发参数与决策引擎对线上主动消息逻辑**当前无效果**。
- 例外：**P3 凌晨关键词**走独立配置 `agent_night_keywords` / Redis `agent:night_keywords`，`_get_night_keywords()` **会读取**，修改关键词可影响 P3 行为。
- 实现约定：**若需求/提示词与现有代码不一致，以现有代码为准**；本页（Agent 配置）仍按接口持久化全量 JSON，待本债清偿后再与运行时对齐。
- 当前处理：无
- 待处理：
  1. `AgentService` 启动或判定时读取 `active_config:agent_rules`（或等价生效源），解析 `triggers`、`decision_engine`
  2. 用配置替换 `_check_p1` / `_check_p2` / `_check_p4` 及 `check_and_trigger` 内频率、评分门槛等硬编码，字段名与 `AgentRulesRequest` / 管理端表单一致
  3. 缺配置或解析失败时回退到当前硬编码行为，避免线上逻辑真空
- 触发时机：需要「后台改 Agent 规则即生效」时排期；可与 Agent 配置页（`agent-rules.html`）联调验收
- 风险等级：**中**（同类「后台配置未接入运行时」债务：易误判「已保存配置 = 已生效」）
