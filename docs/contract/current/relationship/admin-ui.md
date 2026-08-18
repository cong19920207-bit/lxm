# Relationship Admin

- 文档 ID：`contract-relationship-admin`
- 权威状态：`canonical`
- 功能范围：`relationship`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-005`

### `admin/pages/relationship-rules.html`（关系成长配置）

- **实现状态**：已实现。`activeKey='relationship'`，顶栏标题「关系成长配置」。`super_admin` / `ai_trainer` 可配置，`observer` 仅读关系规则。
- **顶部横幅**：始终展示 **TD-005**（配置写入 `admin_config` 与 `relationship_service.py` 硬编码未对齐，见 `docs/tech-debt.md`）。
- **Tab**：`initTabs('main-tabs')` — 等级配置（`#tab-levels`）| 成长值规则（`#tab-growth`）。
- **接口**：`GET` / `PUT` **`/api/admin/relationship-rules`**
  - **PUT Body** 须同时包含 `levels`、`growth_rules`、`confirmed`。
  - `confirmed:false`：仅返回影响预览（`affected_upgrade_users`、`affected_downgrade_users`），不发布。
  - `confirmed:true`：发布配置并执行升级；对「应降级」用户写 Redis 过渡期（7 天），与 `relationship_mgmt.py` 一致。
  - 最高等级（level 3）的 `threshold` 前端提交 **99999**（表单展示为禁用占位「最高等级」）；后端校验要求阈值列严格递增。
- **成长值规则**：表格行 `action_type` 与 `relationship_service.py` 中 **`GROWTH_ACTIONS`** 一致：`dialog` / `long_session` / `daily_login` / `reply_agent`。
- **前端校验（成长值）**：`readGrowthRulesFromForm()` 要求每行「单次积分」「每日上限」均为 **≥1 的整数**（`parseInt` 后校验）；非法时 `showToast(..., 'error')` 并返回 **`null`，不发起 PUT**。「检查影响并保存」「影响预览 · 确认保存」「保存成长规则」三处在组 Body 前均判断 `growth` 非空。
- **默认值**：`GET` 的 `data` 为 `null` 或缺字段时，前端用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` 等价默认填充（与 `relationship_service.py` 硬编码一致）。
- **交互**：「检查影响并保存」先 `PUT` `confirmed:false` 弹出「影响预览」Modal，再「确认保存」`confirmed:true`；「保存成长规则」直接 `PUT` `confirmed:true`（与等级表单当前值一并提交）。

### 技术债记录（关系 / 日记管理页）

| 编号 | 说明 |
| --- | --- |
| **TD-005** | `relationship_rules` 已写入 `admin_config`，`relationship_service.py` 仍用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` / 固定阈值判定，需改服务后后台配置才对用户端生效。 |
| **TD-006** | ~~`diary-history.html` 未建~~ → 已提供页面与 **super_admin / ops_admin** 菜单；`diary-rules` 内历史链接已可用。 |
| **TD-007** | ~~生成与调度未读配置~~ → 已读 `diary_rules`（`diary_rules_loader` + `DiaryService` + 启动时 Cron **`Asia/Shanghai`**）；兼容旧 `generation_prompt`。 |
| **TD-008** | LLM 响应耗时无法按日拆分；数据报表 AI 性能折线用人格偏离率；仪表盘 `llm_avg_response_ms` 无样本为 `null`。 |
| **TD-009** | `report_type=feature` 缺按日 `open_rate` / `agent_replied`，表格暂 4 列。 |
| **TD-010** | `GET /system/status` 的 `alerts[]` 无单条发生时间，监控页用刷新时刻代替；补充字段时的修改范围与库内消费方见 `tech-debt.md`。 |
| **TD-011** | `get_system_status` 在 Redis INFO 异常时 `hits`/`misses` 可能未定义，存在 `NameError` 风险；见 `tech-debt.md`。 |

---

#
