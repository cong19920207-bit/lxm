# persona-prompt-world-state 技术债

- 文档 ID：`tech-debt-persona-prompt-world-state`
- 权威状态：`canonical`
- 功能范围：`persona-prompt-world-state`
- 必读依赖：无
- 相关技术债：`TD-002`, `TD-003`, `TD-021`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-002] 后台 Prompt 与主链 Step5 / Step5.5 热加载 — **已清偿（STEP-026，2026-05-07）**

- **原问题**：旧版七模块 `prompt_modules` 与 `PromptBuilder` 主链未对齐，运营调模板易误判已生效。
- **当前实现**：
  1. **Step5 模块1 System**：`admin_config.config_key = step5_system_prompt`（JSON `{"content"}`），发布后 `active_config:step5_system_prompt`；`PromptBuilder` 经 `_load_step5_system_template_raw` 热加载，缺省回退 `SYSTEM_PROMPT_TEXT`。
  2. **Step5.5**：`step5_5_prompt_fragments` 六段 + `step5_5_prompt_fragments.py` 占位符/默认合并；总开关 **`step5_5_enabled`**（STEP-009，独立页发布）。
  3. **废弃**：旧 **`prompt_modules`** 管理接口已移除，运行时**不再读取** `prompt_modules`。
  4. **在线测试**：`POST /api/admin/prompt/test` 使用 **`PromptBuilder.build_chat_prompt`** + `chat_with_step5_parse(..., is_test=true)`，与主链一致；`use_draft` 覆盖 Step5 System 草稿。
- **契约 / 单测**：见 **`docs/contract.md`**「STEP-026」；**`tests/test_step026_prompt_config.py`**。
- **残留备注**：除模块1 System 与 Step5.5 六段外，其余 Prompt 模块（Persona、Relationship、Memory 等）仍以代码拼装为主；若未来需运营级全模块模板化，另立需求与条目。

### [TD-003] Prompt 管理页版本历史分页失败时列表不刷新

- 位置：`admin/pages/prompt.html` → `loadHistoryPage`
- 问题：`GET /api/admin/prompt/history` 返回 `null`、`code !== 0` 或请求异常时，函数**不更新** `#prompt-history-list` DOM。首屏加载失败会走 `DOMContentLoaded` 里 `else` 显示「加载失败，请刷新重试」；但用户点击分页后若该次请求失败，列表仍保留**上一页或旧数据**，与真实状态不一致，易误判。
- 当前处理：无
- 待处理：
  1. 在 `loadHistoryPage` 的失败分支写入明确错误文案（与首屏一致或 Toast）
  2. 可选：失败时回退 `historyPage` 或禁用分页按钮，避免页码与内容错位
- 触发时机：顺带优化后台列表页错误处理时一并改；或用户反馈历史区「翻页后内容不对」时处理
- 风险等级：**低**（仅影响管理端历史区展示，不涉及编辑、发布与线上对话）

### [TD-021] 林小梦活动状态描述：当前为静态 JSON 占位，完整活动计划功能待建（**待清偿**）

- **背景**：对话链路改造 Step1 需要一条「活动描述串」（描述林小梦当前在做什么，如"她现在应该在午休"），供 Step1.5 Prompt 与 Step3 新增模块 B 注入。完整功能需按时间段（含工作日 / 周末区分）、概率权重、可运营配置等多维度决策，尚无完整产品计划。
- **当前处理（本期 Step1～3 改造阶段占位方案）**：
  - `admin_config` 表新增条目 `config_key = "activity_schedule"`，值为静态 JSON，以**小时段**为 key 映射活动描述文案，示例：
    ```json
    {
      "0-6":   "她现在应该在睡觉",
      "7-8":   "她现在在吃早餐",
      "9-12":  "她应该在工作",
      "12-14": "她现在在午休",
      "14-18": "她应该在工作",
      "18-20": "她现在在吃晚饭或休息",
      "20-23": "她现在在放松"
    }
    ```
  - 运行时优先读 Redis `active_config:activity_schedule`（TTL 与其他 admin_config 一致）；未命中降级读 DB。
  - **未配置 / 未命中当前小时段 / JSON 解析失败**时产出**空字符串**；Step1.5 Prompt 与 Step3 模块 B **条件性注入**——空串时跳过该行，不插入空白占位文案，不中断主对话链路。
  - **不新建表**，**不做管理后台专属配置页面**（后台可通过现有 `admin_config` 通用编辑页手动维护 JSON）。
- **待处理（完整功能）**：
  1. 建独立 `activity_schedule` 表，字段含 `hour_start` / `hour_end` / `weekday_mask`（位掩码区分工作日/周末）/ `description` / `probability`（权重）/ `is_active`；支持多条并存、按概率随机选取。
  2. 配套管理后台页面：列表 + 新增 / 编辑 / 删除 / 启用停用，角色权限与其他 admin_config 一致。
  3. 运行时读取改为查独立表（含 Redis 缓存层），废弃 `activity_schedule` admin_config 条目。
  4. 可选：支持节假日特殊文案（依赖 `world_state` 或另行维护节假日表）。
- **触发时机**：产品确认活动状态需精细化运营（如「主动消息用活动状态做差异化话术」或「用户反馈角色状态描述不自然」）时排期。
- **风险等级**：**低**（当前占位不影响主对话核心链路；仅影响 Prompt 辅助上下文质量）
- **关联**：`doc/对话链路改造-需求确认记录.md` §2.10 **R-L1L3-11**；Step3 新增模块 B「时间与活动状态」。
