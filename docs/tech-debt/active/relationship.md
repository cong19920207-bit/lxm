# relationship 技术债

- 文档 ID：`tech-debt-relationship`
- 权威状态：`canonical`
- 功能范围：`relationship`
- 必读依赖：无
- 相关技术债：`TD-005`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-005] 关系规则（relationship_rules）已入库但运行时仍读硬编码

- **配置**：`admin_config.config_key = relationship_rules`（JSON 含 `levels`、`growth_rules`），发布后 Redis `active_config:relationship_rules` 与库内生效行同步；管理接口见 `backend/routers/admin/relationship_mgmt.py`（`GET`/`PUT /api/admin/relationship-rules`，两阶段 `confirmed`）。
- **问题**：`RelationshipService`（`backend/services/relationship_service.py`）中 `**LEVEL_CONFIG`、`GROWTH_ACTIONS`**、**`_calc_level` 内固定阈值（200 / 800 / 2000）**均为代码写死，**不读取**上述配置。后果：后台修改等级阈值、名称描述、成长加分规则后，H5 侧 **成长值累计**、**等级计算**、**关系详情/进度文案** 等仍按旧硬编码执行，与 `relationship_rules` **易不一致**；管理端发布时仍会按新规则做用户升级与降级过渡期（`relationship_mgmt.py`），加剧「库内等级 / 展示阈值 / 实际加分规则」认知分裂。
- **关联**：与 **TD-001**（`users` 表冗余成长字段）独立；清偿本债时应统一以 `relationship` 表 + 生效配置为准，避免再引入第三套阈值来源。
- **实现约定**：在 `relationship_service.py` 读配置；字段名与 `RelationshipRulesRequest` / 管理端 `readLevelsFromForm`、`readGrowthRulesFromForm` 一致；**缺配置或解析失败时回退当前 `LEVEL_CONFIG` / `GROWTH_ACTIONS` / `_calc_level` 行为**，避免线上逻辑真空。
- **当前处理**：管理端 `admin/pages/relationship-rules.html` 顶部横幅提示 TD-005；`docs/contract.md` 已描述接口与前端校验。
- **待处理**：
  1. 在 `RelationshipService`（或独立小模块）中读取 `active_config:relationship_rules`（或 `get_active_config(..., use_cache=False)` 等与管理端一致的生效源），解析 `levels`、`growth_rules`。
  2. `**add_growth`**：按配置中的 `growth_rules` 取 `points` / `daily_limit`；连续登录加成等特例逻辑与现行为对齐后再迁移。
  3. `**_calc_level` / `get_relationship_info` / `get_relationship_detail**`：按配置 `levels[].threshold` 计算等级；`level_name`、权益描述等优先用配置，缺字段再回退硬编码。
  4. 全局检索仍写死 `200`/`800`/`2000` 或仅读 `LEVEL_CONFIG` 的调用点，一并改为读配置或单点封装。
- **触发时机**：需要「后台改关系/成长即对用户端生效」时排期；可与 `relationship-rules.html` 联调验收。
- **风险等级**：**中**（与 TD-004 同类：易误判「已保存配置 = 已生效」）
