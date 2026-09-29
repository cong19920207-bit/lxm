# 实时语音技术债

- 文档 ID：`tech-debt-realtime-voice`
- 权威状态：`canonical`（技术债记录，不替代接口契约）
- 功能范围：`realtime-voice`
- 必读依赖：无
- 相关技术债：`TD-038`、`TD-039`、`TD-040`、`TD-041`、`TD-042`、`TD-043`

<a id="td-038"></a>

### [TD-038] 解耦通话结束与结算，补齐异常补偿及人工修复（待清偿）

- **接口**：`POST /api/voice/calls/{call_id}/end`、`POST /api/admin/voice/calls/{call_id}/force-end`、`POST /api/admin/voice/ops/hard-stop`；实现见 `backend/services/realtime_voice_ops_service.py` → `VoiceOpsService._end_call_once` / `_reconcile`，以及 `backend/services/realtime_voice_quota_service.py` → `VoiceQuotaService.recover` / `settle`。
- **问题**：通话终态、用量账本、时间线卡片、成长值在同一事务中提交。已接通通话在本地计量器不可用且 Redis 检查点缺失、无效或不一致时，结算会拒绝继续，数据库通话仍可能保持活动状态并阻塞新拨打。当前没有独立的 `settlement_pending` 状态、持久化补偿任务或经审计的一键修复流程；删除占用键不能解决数据库活动状态，直接改终态会遗漏结算。
- **关联**：`backend/services/realtime_voice_create_service.py` 的活动通话拦截；`backend/models/realtime_voice.py` 的通话与用量账本；`backend/services/relationship_service.py` 的语音成长幂等；`backend/routers/admin/voice_ops.py`、`admin/static/js/voice-ops-admin.js` 的运维结果与固定编号重试。
- **当前处理**：2026-09-27 已确认本期修复 `autoflush=False` 下终态与卡片未写入就被成长服务重新读取的根因，并完善 H5 状态恢复及后台部分失败提示。本期实现保持单事务结算；缺少可信计量依据时返回人工核查提示，不猜测时长、不清零账本、不强制释放数据库占用。已有清理器及固定通话重试可处理有完整依据的结束与提交后清理。上述根因修复的代码与回归用例已写入，正式测试按用户要求暂停，尚未部署或恢复现有残留通话；本条延期能力尚未实施。
- **待处理**：
  1. 为通话终态和结算状态分别定义状态机、持久化字段与原子边界，使结束媒体连接和释放拨打占用不依赖所有结算副作用成功；先补齐契约与数据迁移方案。
  2. 设计未结算用量预留和重拨额度校验，防止释放占用后绕过配额；明确跨日、超额与成长值口径。检查点永久缺失时的人工裁决规则需产品确认。
  3. 增加持久化补偿任务，按 `call_id` 幂等重试账本、卡片和成长值，支持失败分类、告警及恢复后对账；记录清理待完成目标，覆盖当前近期终态重试窗口以外的故障。
  4. 后台增加经权限控制和审计的单通话修复入口：展示故障阶段与证据、固定修复目标、展示逐项结果。证据完整时执行幂等修复；证据不足时进入人工核查，禁止直接清零或无依据补账。
  5. 覆盖进程退出、Redis 长时间故障、结算与释放交错、多端重拨、重复任务及缺失证据的故障注入验收后，再启用自动补偿和一键修复。
- **触发时机**：当前开发版本收尾后安排可靠性迭代；出现检查点丢失、长时间依赖故障或同类占用残留时优先排期。
- **风险等级**：**高**（异常状态会阻塞用户拨打；错误补偿可能造成漏计、重复计费或成长值重复发放，需要独立设计与验证）。

<a id="td-039"></a>

### [TD-039] 语音设置的语气说明可发布但未进入实际会话（待清偿）

- **接口**：`PATCH /api/admin/voice/config/config/draft/voice`、`POST /api/admin/voice/config/config/publish`；运行时见 `backend/services/realtime_voice_provider_service.py` → `VoiceProviderAdapter.start_session`。
- **问题**：后台将 `voice.tone_instruction` 展示为可编辑的「语气说明」，配置校验也要求它是字符串，但创建语音会话时仅使用 `voice_id`、`speech_rate`、`loudness_rate` 和 `expressive` 等字段；人格指令由 `context_pack.voice_instruction_template` 组装。填写并发布 `tone_instruction` 不会改变发给服务商的会话指令或音色参数，容易让配置者误以为它已经生效。
- **关联**：`admin/static/js/voice-config-admin.js` 的「语气说明」字段；`backend/constants/realtime_voice_config.py` 的默认配置；`backend/services/realtime_voice_config_service.py` 的校验；`backend/services/realtime_voice_context_pack_service.py` 的人格指令组装。
- **当前处理**：字段可保存、校验和发布；运行时未读取其值。现有语音指令模板独立生效。
- **待处理**：
  1. 确认「语气说明」预期影响的范围，并核对服务商协议及人格指令长度预算；决定将其安全地纳入会话指令，还是从可编辑项中撤下。口径需产品确认。
  2. 按决定补齐运行时传递与有效性测试，或完成字段废弃及已有配置值的兼容处理；同步后台生效说明。
- **触发时机**：下次调整语音音色或提示词配置时，尤其在向配置者承诺「语气说明」生效前。
- **风险等级**：**中**（已发布的可编辑字段不产生预期效果，会误导配置和验收；不影响当前通话的基本运行）。

<a id="td-040"></a>

### [TD-040] 清理未调用的显式结束语义分类器（待清偿）

- **接口**：`WS /api/voice/calls/{call_id}/stream`；实现见 `backend/services/realtime_voice_ending_service.py` → `ClosingSemanticGate.explicit_exit`，当前结束事件处理见 `backend/services/realtime_voice_gateway_service.py` → `observe_ending_event`。
- **问题**：`explicit_exit` 保留了「用户是否明确要求现在结束通话」的独立 LLM 判断提示词，但生产调用链没有调用该方法。当前通话结束意图由语音服务商的原生结束信号和播放完成证据处理；闲置分类器容易使提示词盘点和后续维护误判为仍有一条 LLM 结束判断链路。这是遗留实现，不代表现有结束功能缺失。
- **关联**：`backend/services/realtime_voice_provider_service.py` 的 `enable_user_query_exit`；`tests/test_realtime_voice_native_exit.py` 的原生结束回归测试；`tests/test_realtime_voice_step018_ending.py` 的分类器单元测试。
- **当前处理**：`ClosingSemanticGate.explicit_exit` 仅由单元测试直接调用；原生结束测试明确断言运行时不会调用它。
- **待处理**：
  1. 确认原生结束信号是否为唯一正式路径，以及是否需要分类器作为有条件的备用路径；不要直接把第二次 LLM 判断接入现有结束流程。
  2. 若无备用需求，删除闲置方法和对应孤立测试；若需保留，明确触发条件、失败回退与时延预算，并补齐真实调用链验收。
- **触发时机**：下次整理语音收尾链路或提示词清单时。
- **风险等级**：**低**（当前功能由原生结束路径承接，主要是闲置代码和认知成本）。

<a id="td-041"></a>

### [TD-041] R03：运行配置发布与回滚缺目标绑定的连接预检（待清偿）

- **接口**：`POST /api/admin/voice/config/config/publish`、`POST /api/admin/voice/config/config/rollback`；独立诊断入口为 `POST /api/admin/voice/config/test-connection`。实现见 `backend/services/realtime_voice_config_service.py` → `RealtimeVoiceConfigService._publish_checked` / `_rollback_checked`，以及 `backend/services/realtime_voice_admin_test_service.py` → `RealtimeVoiceAdminTestService.test_connection`。
- **问题**：运行配置发布与回滚校验配置结构、凭据引用和能力证据，但未对本次将生效的目标快照强制连接预检。独立连接测试只测试当时的草稿；随后草稿或生效版本变化时，其成功结果不能证明发布或回滚目标可连接。Adapter/Profile 组合错误可能直到实际通话才暴露。
- **关联**：P1 修复计划 R03（`docs/design/realtime_voice/P1/execution/P1-人工验收问题顺序修复计划-20260928.md`）；`backend/services/realtime_voice_provider_service.py` 的支持组合；`backend/routers/admin/voice_config.py`、`admin/static/js/voice-config-admin.js` 的配置入口与反馈。
- **当前处理**：2026-09-29 用户决定延期至后续修复，代码仍只有独立连接测试，发布和回滚尚无目标绑定预检。独立测试通过不得记为发布门禁通过；本条未完成，也不代表当前配置已获真实 Provider 验证。
- **待处理**：
  1. 从 Adapter 实际声明提供受支持的 Provider/Adapter/Profile 组合；后台限制选择，后端拒绝未声明组合。
  2. 复用现有凭据解析、超时、关闭和失败归类，对每次 `voice_call_config` 发布及历史目标回滚执行自动连接预检；独立测试仍仅用于诊断，纯话术发布、软停和关闭总开关不受 Provider 故障阻断。
  3. 预检时不持有数据库行锁；测试目标绑定快照身份、版本和内容哈希，通过后重读并校验并发变更，再进入现有 DB/Redis 提交与补偿。失败、超时或版本冲突不得产生半发布状态，审计只记录目标身份和脱敏失败类别。
  4. 用受控 Runner 与隔离 MySQL/Redis 覆盖成功、拒绝、超时、取消、版本竞争、回滚和补偿；真实 Provider 握手另按实际环境与授权取证。完成后同步 P1 临时契约。
- **触发时机**：扩大后台运行配置发布/回滚使用前；后续 R05 的真实测试通话取证前先完成本项。
- **风险等级**：**高**（错误配置可通过发布并在实际通话建连时失败；修复涉及并发版本、外部调用与 DB/Redis 补偿）。

<a id="td-042"></a>

### [TD-042] R05：强制 test 能力未贯通测试用户的实际通话（待清偿）

- **接口**：`POST /api/admin/voice/config/config/capabilities/{capability_key}/force-test`、`WS /api/voice/calls/{call_id}/stream`；实现见 `backend/services/realtime_voice_runtime_config_service.py` → `_scope_capability_for_call`，`backend/services/realtime_voice_gateway_service.py` 的 Adapter 构造，以及 `backend/services/realtime_voice_provider_service.py` → `VoiceProviderAdapter.capability_enabled`。
- **问题**：运行时 loader 能为 `global.test_user_ids` 中的用户生成强制 `test` 能力快照，但 Gateway 在实际通话中按普通 `call` 创建 Adapter；Adapter 仅允许 `admin_test` 使用 `unverified/stale` 强制能力，导致后台显示启用、实际能力操作仍被关闭。
- **关联**：P1 修复计划 R05（`docs/design/realtime_voice/P1/execution/P1-人工验收问题顺序修复计划-20260928.md`）；后台设计 `ADM-C7` / `ADM-C21` 的审计 `test` 范围；`TD-041` 的配置发布连接门禁。
- **当前处理**：2026-09-29 用户决定延期至后续修复。强制操作的角色、`CONFIRM`、原因和审计规则保留，但 Gateway→Adapter 的实际通话授权未贯通；不能把测试用户通话接通当作强制能力生效证据。
- **待处理**：
  1. 在普通 `call` 目的下，由服务端根据冻结配置的测试用户名单、真实 `call.user_id` 和经 loader 核实的强制审计来源，向 Adapter 传递显式测试通话授权；首次连接和重连共用判定，不接受客户端自报授权，也不把整通电话改为 `admin_test`。
  2. Adapter 继续独立校验能力状态、`test` 范围、强制来源和证据指纹；普通用户、缺身份或来源、`failed/off` 和指纹不符均拒绝，`verified` 能力现有行为保持。
  3. 用 Gateway→真实 Adapter、受控 transport 的自动化用例覆盖能力操作的允许/拒绝及重连；真实 Provider 各能力取证独立进行，不能把受控测试或连接成功写成 `verified/all`。完成后同步 P1 临时契约。
- **触发时机**：使用指定测试用户的真实通话为强制 `test` 能力取证前；按原计划先完成 `TD-041`。
- **风险等级**：**中高**（测试通话无法验证预期能力；若放宽错误，未验证能力可能进入普通用户通话）。

<a id="td-043"></a>

### [TD-043] R09：后台通话列表缺按 voice_id 筛选（待清偿）

- **接口**：`GET /api/admin/voice/calls`；实现见 `backend/routers/admin/voice_records.py` 的列表参数与 `backend/services/realtime_voice_record_service.py` 的通话概览投影。
- **问题**：P1 PRD 要求记录列表支持 Provider、模型和音色筛选；现有概览与列表展示已有 `voice_id`，但 API 查询参数、后台筛选表单和筛选审计白名单均缺 `voice_id`，无法按音色检索通话。
- **关联**：P1 修复计划 R09（`docs/design/realtime_voice/P1/execution/P1-人工验收问题顺序修复计划-20260928.md`）；`admin/static/js/voice-records-admin.js` 的列表筛选；`backend/services/realtime_voice_record_metric_service.py` 的 R04 审计条件白名单。
- **当前处理**：2026-09-29 用户决定延期至后续修复。`voice_id` 仅用于记录展示，尚不是列表筛选条件；这是 P1 需求遗漏的延期记录，不表示需求取消。
- **待处理**：
  1. 为列表 API 和后台表单增加可选 `voice_id`，按冻结快照 `config_snapshot.resolved_config.voice.voice_id` 精确匹配；空输入不发送参数，旧快照缺字段时不误匹配。
  2. 将 `voice_id` 纳入 R04 已建立的审计条件白名单；验证与 Provider、模型、时间范围的组合查询、分页总数、重置筛选及原有导出权限投影。
  3. 运行定向单元、隔离 MySQL 和后台浏览器回归，完成后同步 P1 临时契约中的查询字段与页面行为。
- **触发时机**：后台需要按音色排查或运营通话时；先复用已完成的 R04 筛选审计边界。
- **风险等级**：**低**（影响后台检索效率和 PRD 完整性，不改变现有通话运行或默认列表结果）。
