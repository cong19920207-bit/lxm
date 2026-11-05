# 养宠管理后台

- 文档 ID：`contract-pet-system-admin`
- 权威状态：`canonical`
- 功能范围：`pet-system`
- 实现入口：`admin/pages/pet.html`、`admin/static/js/pet*.js`、`backend/routers/admin/pet*.py`

## 导航和页面

侧栏在「生活流 Prompt」下方设置独立的「养宠管理」折叠分组。二级入口按下表排列，通过 `section` 定位。进入养宠页时展开分组并高亮当前项。窄屏使用页内导航。

页面统一展示场景说明及可展开的使用步骤，状态优先使用中文标签并保留原始诊断值；列表将时间和精确定位条件收进“更多筛选”，已有条件自动展开，提交仍携带全部筛选值。

| 养宠分区 | section | 页内组织 |
|---|---|---|
| 概览 | `overview` | 常用工作入口 → 四项指标 → 任务运行、陪伴档位、预算、内容请求；请求记录依据可展开，部分接口失败不覆盖其他成功区域 |
| 宠物与记录 | `pets` | 列表筛选；详情导航按了解宠物、查看记录、排查问题分组，原详情与返回筛选链接保留 |
| 规则与成本 | `rules` | 仅保留成长互动、共同事件、偏好、自动照顾、预算叙事回访五个业务分类；明确修改预览 → 保存草稿 → 服务端校验 → 确认影响发布 |
| 素材与运行配置 | `settings` | 独立二级入口 `section=settings`；页内仅固定模板与素材（`domain=appearance`）、运行开关（`domain=runtime`）两个分类，各自保留独立配置版本与权限 |
| AI 与文案 | `ai` | 每个工作流有触发场景说明，模板及提示词使用中文标签；模拟输入、模型测试和发布操作保持分区 |
| 任务与修复 | `tasks` | `mode=tasks/repair/text` 分别对应任务排查、单宠修复、文字处理；旧 `id` 直达任务详情、`text` 直达文字、`pet/repair` 直达修复；浏览不触发业务操作 |
| 版本与操作日志 | `versions` | 明确视图切换与当前选中；切换保留共用筛选，但清除两类视图不兼容的 `action`；详情先展示所选版本、线上版本与影响提示 |

旧 `section=rules` 且 `domain` 为 `appearance` 或 `runtime` 的链接保留其参数并跳转到 `section=settings`，避免旧书签落入错误的规则编辑器。概览运行开关入口同步指向新页。

页面资源携带版本参数。保存、校验、发布保留在主操作栏，预览、差异、历史和操作回执可从「更多操作」打开。

## 草稿与历史

四个配置域分别维护生效版本与草稿，不展示环境名。编辑器持续显示“当前生效 vN”和“草稿 DN”，根据内容差异区分未保存、已保存未发布、校验失败、已校验待发布、与生效版一致及基准变化；字段显示前后值，业务页签显示变动数量。同一配置域各页签共同发布，确认框展示完整差异。

- 每次内容变动的草稿保存写入 `pet_config_draft_revision`，同内容且基准相同的重复保存不增加修订。历史包含保存人、时间、基准与差异。迁移只保留迁移时仍存在的最新草稿，无法补回先前覆盖的修订。
- `GET /api/admin/pets/config/{domain}/drafts` 分页读取草稿与发布历史；只读角色不返回草稿内容。`POST /api/admin/pets/config/{domain}/restore` 支持从草稿或已发布版本恢复为新草稿；AI 可指定工作流，仅恢复对应提示词、长度与思考设置，生日仅恢复固定模板。共享全局思考模式冲突时阻止恢复并提示核对，不连带修改其他场景。
- `DELETE /api/admin/pets/config/{domain}/drafts/{revision}` 删除指定草稿（逻辑删除，保留操作审计）；删除当前草稿后清除编辑指针、校验与测试关联并返回生效配置，修订号递增以拒绝旧请求。已删除草稿不再显示或允许恢复；已发布版本保留。恢复和删除携带操作标识、原因、预期修订及生效基准，支持原操作幂等查询。
- AI 提示词、长度或有效思考模式变更，需要受影响工作流的真实模型测试通过才能发布；回执须绑定当前修订、完整内容摘要和当前模型配置，且文案校验与用量回执完整性均通过。改动后旧测试失效；固定模板变更仅做确定性校验。整域回滚沿用历史内容生成新版本，记录来源，保留未发布草稿及其原基准并要求重新核对，不重写历史文字。
- 保存、恢复、删除均进入养宠专属操作审计。发布结果关联来源草稿修订，版本列表标识当前生效版。
- 保存和校验回执只对应发出请求时的内容。请求期间继续编辑，后续输入仍显示未保存。清空数字字段会提示补填。
- 发布请求结果不确定时，可查询或用原操作标识重试。回滚成功后，当前详情页保留所选历史版本与返回来源，并立即更新生效版本、回滚基准和回执。查询到同域已完成的原回滚也应用这项更新。

## 后台接口与权限

接口使用管理员 JWT。侧栏可见性与写权限分开，服务端按操作和配置域重新核对权限。

| 配置域或能力 | 写入角色 |
|---|---|
| 规则与素材发布、回滚、草稿恢复及删除 | `super_admin`、`ops_admin` |
| 运行配置发布、回滚、草稿恢复及删除 | `super_admin`、`ops_admin`、`tech_ops` |
| AI 配置发布、回滚、草稿恢复及删除、真实模型调试 | `super_admin`、`ai_trainer` |

`observer` 无写权限。修复、任务恢复、文字处理和诊断读取的授权范围以 `backend/services/pet_admin_security.py` 为准。

下列路径相对于 `/api/admin/pets`。

| 用途 | 方法和相对路径 |
|---|---|
| 权限、概览和记录 | `GET /permissions`、`/overview/{section}`、`/pets`、`/pets/{pet_id}`、`/pets/{pet_id}/{panel}`、`/daily/{pet_id}`、`/photo-assets/{snapshot_id}` |
| 配置编辑和预览 | `GET /config/{domain}`、`/editor/{domain}`。规则、外观等预览走 `GET/POST /preview/{domain}`，AI 走 `GET/POST /ai/preview`。 |
| 保存、校验和发布 | `PUT /config/{domain}/draft` 提交完整 `content`、`expected_revision`、`base_version`。 `POST /config/{domain}/validate` 提交 `revision`。 `GET /config/{domain}/impact?revision=…` 预览，`POST /config/{domain}/publish` 另需 `base_version`、`operation_id`、`reason`。 |
| 回滚与开关 | `GET /config/{domain}/rollback-preview?target_version=…` 预览。 `POST /config/{domain}/rollback` 提交 `target_version`、`base_version`、`operation_id`、`reason`。 `POST /runtime/disable` 用于单项停用。 |
| 模型 | `GET /model-status`。 `POST /ai/test` 提交 `operation_id`、`reason`、`revision`、`content_digest`、`workflow` 与模拟 `inputs`。 |
| 素材、任务和修复 | `GET/POST /resources`、`GET /resources/{resource_id}/references`、`GET /tasks`、`GET/POST /tasks/{object_id}`、`GET /repair/{pet_id}/preview`、`POST /repair/{pet_id}`、`GET/POST /texts/{text_id}`。 |
| 版本与审计 | `GET /versions`、`/versions/{version_id}`、`/logs`、`/audit`、`/operations/{operation_id}`。 `POST /operations` 可登记允许的准备操作。 |

## 验收与发布边界

2026-11-01 的本地 Docker Chrome 验收覆盖领养、共同玩球、留影归档、历史授权回读及运行开关联动。移动端使用模拟视口。

2026-11-03 在本地 Docker 验证了 `v9x_pet_drafts_001` 的已有库升级。迁移前后四域草稿及发布历史的内容摘要一致，49 项隔离后端测试和 10 组后台浏览器测试通过。

2026-11-04 的本地后台验收走通草稿保存、校验、真实模型测试、发布、删除与回滚。随后在原版本详情页实测回滚到相同内容生成 AI v4，页面立即显示 v4。对应的 11 组后台浏览器回归通过。该记录属于本地开发验收，实体 iPhone、微信与生产发布各需独立验收证据。
