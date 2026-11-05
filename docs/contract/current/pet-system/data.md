# 养宠数据与迁移

- 文档 ID：`contract-pet-system-data`
- 权威状态：`canonical`
- 功能范围：`pet-system`
- 实现入口：`backend/models/pet*.py`、`alembic/versions/v9i_pet_foundation.py` 至 `v9x_pet_config_drafts.py`

## 持久化边界

| 范围 | 主要记录 | 约定 |
|---|---|---|
| 宠物档案与状态 | `pet_profile`、`pet_state`、`pet_rule_snapshot` | 档案按账号唯一，保留成长依据。状态和规则引用随结算推进。 |
| 事实、请求和展示 | `pet_fact_event`、`pet_fact_request`、`pet_interaction`、`pet_snapshot`、`pet_display_entry` | 请求键用于同一操作的去重或查证。事实与历史快照独立于展示，保留发生时的值和版本引用。 |
| 活动与回访 | `pet_activity`、`pet_absence`、`pet_view_session`、`pet_return`、`pet_account_lifecycle` | 活动、离开期间、回访依据和账号生命周期单独记录。业务日采用 `Asia/Shanghai`，持久化时刻按 UTC 处理。 |
| 正式文字 | `pet_formal_text`、`pet_text_source`、`pet_text_visibility` | 文字记录关联具体来源事实。隐藏或更正保留可追溯依据。配置发布、回滚不重写既有文字。 |
| 留影资源 | `pet_photo_asset`、`pet_photo_delete_job`、`pet_snapshot` | 图像放在私有 OSS，数据库记录对象状态与历史快照。拍摄和归档分开。归档引用保持历史姓名、阶段和资源版本，访问时生成短期签名链接。 |
| 调度、生成和预算 | `pet_rule_job`、`pet_job_health`、`pet_task_candidate`、`pet_generation_task`、`pet_request_attempt`、`pet_budget_entry`、`pet_budget_mutex`、`pet_diagnostic_payload` | 业务任务、模型尝试、额度与诊断分开。已发送请求保留额度与结果记录，结果未知不能当作未发送处理。 |
| 配置与后台操作 | `pet_config_head`、`pet_config_draft_revision`、`pet_config_version`、`pet_resource`、`pet_admin_operation`、`pet_admin_audit` | 分域维护当前指针和历史。草稿修订、发布版本、资源登记和操作审计分别追踪。 |

## 配置版本与草稿

- `pet_config_head` 每个域一条，保存当前生效版本、草稿及其基准、修订号和校验绑定。
- 草稿内容有变动时保存独立快照，含来源、操作者、时间及内容摘要。同内容且基准相同的重复保存复用修订。删除标记指定草稿，保留审计。删除当前草稿时清除编辑指针和校验关联，修订计数递增。
- 每次发布或回滚新增不可变版本。发布记录来源草稿，回滚记录来源历史版本。回滚后的未发布草稿保留原基准，后续编辑需重新核对。操作标识在同一请求内容下用于查询和幂等处理。
- `v9x_pet_drafts_001` 将迁移时仍存在的草稿写入修订表。迁移前已被覆盖的草稿无法补回。已发布版本与历史事实不重写。

## 调度与部署

养宠调度注册在 `backend/tasks/scheduler.py`，覆盖规则结算、自动照顾、日概览、叙事候选、生成队列、失效任务清理及生日纪念。后台浏览使用已保存数据。升级已有数据库前核对迁移链，私有 OSS、模型连接与预算按目标环境配置。

发送前校验沿用用户、宠物、任务再到运行围栏的锁顺序，围栏校验仍在实际网络发送前完成。模型尝试的 `reason` 区分 `send_unknown`、`execution_error`、`execution_cancelled` 及认领失效；结果可保留 HTTP 状态和失败阶段／类别，不存原始异常消息或凭证。HTTP 200 响应头不代表完整结果或 usage 已收到。超时、执行异常与取消仍保守保留已消耗额度，不自动重发；队列意外异常须进入调度失败记录，不能吞掉后报告正常。上述诊断使用现有字段，无新增迁移。
