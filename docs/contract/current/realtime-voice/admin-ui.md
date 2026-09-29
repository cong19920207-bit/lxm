# 实时语音管理界面契约

- 文档 ID：`contract-realtime-voice-admin-ui`
- 权威状态：`canonical`
- 功能范围：`realtime-voice`
- 必读依赖：`contract-shared-auth-rbac`, `contract-realtime-voice-api`, `contract-realtime-voice-data`
- 相关技术债：[TD-038～043](../../../tech-debt/active/realtime-voice.md)
- 更新：2026-09-29；本文件定义现有页面行为，不替代后端权限/审计约束。

<a id="pages"></a>
## 页面与权限

所有页面位于 `admin/pages/`；菜单显示不替代服务端鉴权。匿名/过期凭据先走既有后台登录。角色简写：超管=super_admin，运维=tech_ops，运营=ops_admin，训练=ai_trainer，观察=observer。

| 页面 | 可读角色 | 可写角色与边界 |
|---|---|---|
| `voice-master-switch.html` | 五角色 | 超管/运维发布独立总开关 |
| `voice-config.html` | 五角色 | 运行配置超管/运维；话术超管/训练；测连/能力/播放超管/运维；强测最终仅超管 |
| `voice-calls.html` | 超管/运营/观察 | 导出超管/运营；debug/删除仅超管；不因读权限开放管理操作 |
| `voice-jobs.html` | 超管/运营/观察/运维 | 失败任务补跑仅超管/运维；显示资格与拒绝原因，无任务正文/快照 |
| `voice-crisis.html` | 仅超管 | 只读隔离原文与审计；不提供导出 |
| `voice-metrics.html` | 五角色 | 全部只读，无导出或真实账单写入 |
| `voice-ops.html` | 超管/运维/观察 | 软停/硬停/强制结束仅超管/运维 |
| `voice-prompts.html` | 超管/训练/观察 | 只读当前执行模板，无保存/发布 |

<a id="configuration-ui"></a>
## 配置与总开关

- 配置按运行参数/话术分组，常用项使用中文表单，模型和音色分开；高级JSON有差异行提示。读取当前版本/草稿revision，分节保存、校验、发布、历史比较和回滚使用[API乐观锁](api.md#admin-config)，冲突时提示重新读取，不覆盖他人草稿。
- 发布/回滚填写CONFIRM和变更说明。能力表分开显示声明、证据和当前有效结果；失效、过期、跨指纹或未通过不会因为绿色历史记录被开启。强测是测试范围例外，不是生产能力验证；运行消费缺口TD-042继续显示为边界。
- 独立总开关页读取单独版本并发布，不要求用户编辑庞大JSON。开放范围、白名单、维护、软停等阻断信息单独展示，打开总开关不表示所有用户立刻有权拨打。
- 单用户额外时长入口按秒数和账户版本提交，允许范围/角色见[API](api.md#master-quota)。每日额度更改对旧账户按当前发布值显示，不需要手工给每个旧用户补差额。
- `tone_instruction`、`explicit_exit`当前尚无对应运行消费（TD-039/040）；profile测连发布联动为TD-041。页面存在配置项不视为这些债务已完成。

<a id="playback-ui"></a>
## 诊断播放与 Prompt

管理播放不申请麦克风，调用独立测试通道，实际AudioBuffer播放onended后发送匹配身份/字节数ACK。停止测试需回报真实已播前缀；流断开关闭Provider及临时target。超时/未播/拒绝/客户端断开均展示独立结果，不把HTTP200或收到音频当passed，不自动修改六能力。

Prompt页7个Tab展示10个执行源码模板，精确保留占位符、复制当前模板；不是具体用户通话的完整Prompt，不提供编辑。VOICE-MEM-01同时展示当前执行MEMORY_RULES和配置补充语义；示例说明不作为模型输出解析。会前voice_instruction_template留在配置页编辑，非本页第11个运行源码模板。

<a id="records-ui"></a>
## 记录、任务、危机与运维

通话列表筛选/分页、详情、有效正文、用量、冻结配置和审计按[API](api.md#admin-records)投影。音色voice_id筛选尚未完成（TD-043）。列表/导出不显示危机原文、调试生成正文和失效正文；导出只五字段有效转写。冻结配置为脱敏副本，当前credential配置状态不可冒充历史密钥状态。

正文用textContent展示，不将模型内容作为HTML。私有正文不写localStorage/sessionStorage，页面隐藏清理敏感展示，BFCache返回重新拉取；过期/删除后不可从旧缓存恢复。任务页只显示安全元信息和合格retry_path；补跑不能强行越过保留期/删除围栏。危机页仅超管且无导出，读取也会审计。

运维页区分软停、硬停和单通强制结束；结果显示业务终态、结算及cleanup_pending，不把请求已发送当清理已完成。破坏性动作按现有CONFIRM流程。未完成的恢复/补结算不以新按钮冒充已实现（TD-038）。

<a id="metrics-ui"></a>
## 指标看板

四个Tab分别呈现业务日指标、短期观测、历史日聚合及模拟成本核对；异步请求使用当前查询身份，旧响应不得覆盖新查询。明确标记北京时间业务日与UTC观测日、任务最终结果与重试样本、null/unknown/provisional原因；指标字典解释来源和单位。

真实价格未配置时普通estimated_cost显示未配置；用户显式选模拟时显示CNY 0.06/分钟及独立模拟维度。账单核对只预览模拟输入，不写真实账单。所有五角色仅查看，没有导出或发布入口。

<a id="acceptance-scope"></a>
## 交付验证范围

P1采用用户确认的电脑Chrome范围，复用既有通过的拆分证据；不新增真手机/实服/真实账单要求。当前开发里程碑结论为PASS_WITH_RISKS，AC30模型实际采用及已确认降级保留；R03/R05/R09延期对应TD-041/042/043。额外全仓测试74项失败保留风险记录，不写成全仓通过，也不自动改变本次已确认P1验收范围。
