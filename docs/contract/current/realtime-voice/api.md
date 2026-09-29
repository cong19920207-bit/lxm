# 实时语音接口契约

- 文档 ID：`contract-realtime-voice-api`
- 权威状态：`canonical`
- 功能范围：`realtime-voice`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`, `contract-realtime-voice-data`
- 相关技术债：[TD-038～043](../../../tech-debt/active/realtime-voice.md)
- 更新：2026-09-29；合并 P1 M1～M7 与本地人工验收后已完成增量。状态以[执行记录](../../../design/realtime_voice/P1/execution/实时语音通话开发执行记录.md)为准；开发验收不等于生产发布授权。

<a id="user-http"></a>
## 用户 HTTP 接口

前缀 `/api/voice`；全部需要用户 Bearer JWT，按用户隔离；不可读取他人通话。成功为 `{code:0,data:...}`。状态、正文相关响应 `Cache-Control: no-store`。调用方不能提交用户 ID、有效助手正文或计费事实。

| 方法 / 完整路径 | 输入 | 成功语义 |
|---|---|---|
| POST `/api/voice/calls` | 严格 Body：`source="home"`、UUID `device_id`、严格布尔 `browser_supported`/`microphone_granted`；Header `Idempotency-Key` 为 UUID | `call_id,status,call_ticket`；24小时内同用户同键同请求重放同一通话；票据过期或已消费时返回 null，不重新建通 |
| GET `/api/voice/quota` | 无 | `remaining_seconds`；按当前已发布额度计算，只读，不靠 GET 修改旧账户 |
| GET `/api/voice/calls/{call_id}` | UUID 路径参数 | `call_id,status,end_reason,has_connected,duration_seconds,end_message,show_end_page,crisis`；无转写正文 |
| POST `/api/voice/calls/{call_id}/end` | 可选 Query `only_if_unconnected=false` | 请求结束；true 时只允许 deciding/ringing 原子取消；状态已变化返回409；清理不完整可返回 `cleanup_pending`，不得伪报结算完成 |
| POST `/api/voice/calls/{call_id}/reconnect` | 严格 Body `device_id` | 同一 call 在恢复窗口申请新单次票据；只允许 reconnecting、原设备及本进程 owner |

建通按浏览器、麦克风、封禁、总开关/开放范围、危机配置、余额、Provider、并发与租约预检。失败不留下半条通话或账本。当前活跃通话绑定发布版本和不可变快照，不随草稿/后续发布热变。

错误使用 HTTP 状态与结构化原因：401用户缺失；403封禁；404不存在或非本人；409幂等请求不一致（`IDEMPOTENCY_KEY_REUSED`）、并发/状态冲突；503内部、危机配置或 Provider 不可用。浏览器/麦克风/余额/冷却/开放范围的阻断原因由服务返回，客户端不得把预检失败展示成已接通。幂等记录不完整返回503，不猜测创建结果。

<a id="websocket"></a>
## WebSocket、来源和帧

- WEBSOCKET `/api/voice/calls/{call_id}/stream` 与 `/api/voice/calls/{call_id}/reconnect-stream`。握手子协议为 `voice.v1`、`ticket.<票据>`、`device.<设备UUID>`；不把凭据放入 URL。单次短效票据原子消费，绑定用户/call/device/用途。默认票据30秒，心跳5秒、租约15秒。
- 必须有唯一合法 Host 与 Origin；显式 Origin 白名单优先，否则校验同源的协议/Host/端口。默认 WSS。开发 ws 仅在显式本地开关开启且浏览器来源、目标均 loopback、转发源为受信本地/私网代理时允许；不能把私网 Origin 泛化为允许。
- 拒绝握手关闭4403；接受后的服务异常1011。并发连接和首连清理均核对 owner/generation。旧首连失败清理不能结束已经接通或已被新 owner 接管的通话。
- 上行16kHz PCM、下行24kHz PCM；上行目标40ms。帧上限12000字节、每秒60帧，PCM偶数字节且上限6400；非法/过量帧按网关策略拒绝。持久化不保存 PCM。
- 客户端控制帧包含心跳、播放 `progress`、`sentence`、`reply_complete`、`audio_complete`、`barge_in`。call/session/reply/播放进度须匹配服务端当前状态；客户端不决定 effective_text。字幕/生成正文不等于用户实际听到的正文。
- Nginx 专门代理 `/api/voice/`，WebSocket Upgrade、原始 Origin 和实际转发链正确传递；不能套用对话 SSE 的缓冲/超时假设。服务侧票据校验仍是鉴权边界。

<a id="runtime"></a>
## 接通、播放、结束与恢复

- 状态值和计费事实见[数据契约](data.md#lifecycle)。CALL-01冻结人格/上下文，决策失败按已发布 fallback 策略；默认至少响铃4秒、等待上限12秒、兜底延迟4～8秒。`call01_fallback`只保存是否实际采用兜底，不把旧 NULL 当 false。
- 会前包分离固定人格、动态状态、近期有效文字和长期记忆；默认5000/2000/800字符、5条记忆、30天回看、总预算3000ms，受 ready barrier 约束。来源失败走已定义最小包，不能跨用户借用。
- 回合由服务端 ASR final、生成正文和播放证据组装。完整播放/精确片段/确认句子/无证据逐级降级；只有经安全门禁的用户 final 和有效助手正文进入后续记忆、摘要、成长与日记。
- 打断可立即停本地播放；远端取消、上下文截断只按有效能力证据启用，不能把请求发出当远端执行成功。轻附和识别要求原回复存在非零且推进的500ms播放证据；纯附和组合可丢弃，暂存上限2秒/64帧/64序号。514删除待TTS完结，571 ACK不是取消完成证据；缺失TTS尾部清理仍有已记录风险。
- 原生结束信号 `20000002` 等匹配回复播放完成后再等默认800ms（允许0～3000ms）结束；新用户发言撤销待结束。静默6/12秒进入确认/收尾；固定兜底只覆盖不可用情形，不覆盖明确拒绝或 time_low。不能用原生10秒期限截断仍在播放的音频。
- 重连默认15秒，恢复期暂停计费/成长，不重放 PCM、不重置最初接通时间。默认同call重建 Provider session 并重新构建上下文；只有证实的 session reconnect 能力才保留会话。当前只支持本进程 owner，无跨worker迁移承诺。
- 正常结束、取消、断线、硬停共用幂等 finalizer；结束响应和后台结果区分“业务结束请求”“结算完成”“租约清理完成”。恢复能力缺口保留[TD-038](../../../tech-debt/active/realtime-voice.md#td-038)。

<a id="recall"></a>
## 通话中召回及安全边界

- VOICE-RECALL-01只判断需要过去信息与检索问题，输出严格 JSON；先检查本通资料，再 preamble，不足才访问按用户隔离的四路长期检索。只选择提供的真实资料 ID；每路结果受预算控制，注入最多3条、每条600字符。
- 当前仅使用 Provider **502** 注入，不使用510。当前问题最多发出一次；在回复前安全窗口发送资料，并实施同一用户问题最多一个可交付回复的门禁。输出守卫保留首个事件350（句首）或首个非空事件550（文本）对应reply_id，后续不同reply_id被抑制，不能保证模型实际采用记忆。
- 迟到结果在本通缓存标记 `delivery_pending`，最早下一轮 final 后安全窗口尝试发送，不必等同话题再次检索；仅成功发送才原子消费对应缓存版本。结束、删除、过期或能力不满足时不发送。缓存只在当前通话使用。
- 502是否允许由后台配置及有效能力证据决定，不是面向用户的模型开关。AC30实际模型采用是用户已接受的开发验收偏差，发送成功不能标成采用成功。
- 危机与普通内容安全先于普通落库；危机原文隔离在专属表，不写普通回合、记忆、摘要和普通日志。词库缓存不可用时有限回退唯一有效发布行，满足条件才修缓存；数据库也无有效词库则阻断新通话。有效但不匹配的缓存不擅自覆盖。
- 用户只收到危机提示和资源，不收到识别原文/调试证据。危机隔离、告警和过期详见[data.md](data.md#safety)。

<a id="h5-ui"></a>
## H5 展示

首页电话入口先展示用途/麦克风说明再请求权限，按钮依据实际阻断原因展示重试、返回或取消。连接进度与失败路径区分首次连接和通话中断线；旧请求不得覆盖当前 call 的状态。终态查询尚未成功时保留 call 标识并允许重试查询，不创建新通话掩盖未知状态。

通话页显示头像、状态、接通后时长、额度与控件，不显示转写。额度不足提供查看额度/返回动作，不提供立即重拨；技术失败重拨使用新的幂等键；取消不展示结束页。未接固定显示“她现在可能不方便”，不套用通后主动消息模板且不显示重试。重连保持原通话语义，支持退出；横竖布局、安全区、reduced-motion/焦点可访问性按现有页面实现。

结束卡片和危机资源卡在[H5 timeline](../chat-emotion/api.md#voice-timeline)定义。Open API v1沿用[原协议](../openapi/api.md#voice-compatibility)。相邻 `refreshCrisis()` 旧GET401竞态仍为已记录风险，本契约不将其记成已修复。

<a id="admin-config"></a>
## 后台配置、证据与发布

以下路径以 `/api/admin/voice` 开头；后台 Bearer JWT。五角色是 `super_admin / ops_admin / ai_trainer / tech_ops / observer`。读配置允许五角色；运行配置写仅 super_admin/tech_ops，话术写仅 super_admin/ai_trainer；observer无写入和导出权限。

| 方法 / 后缀 | 参数与语义 |
|---|---|
| GET `/config/{key}` | 读取配置/话术当前发布、草稿和版本信息，凭据脱敏；key按服务允许集合 |
| PATCH `/config/config/draft/{section}`、`/config/script/draft/{section}` | `base_version>=0,draft_revision>=1或null,content`；严格Body；分节草稿、乐观锁冲突409 |
| DELETE `/config/config/draft/{section}`、`/config/script/draft/{section}` | 删除该节草稿覆盖 |
| DELETE `/config/config/draft`、`/config/script/draft` | 丢弃整个草稿 |
| POST `/config/config/validate`、`/config/script/validate` | 校验候选；可选 followup_preview 含 stage/candidate_at/jitter_minutes，仅预览，无发送/发布副作用 |
| POST `/config/config/publish`、`/config/script/publish` | `confirm_text="CONFIRM",change_note`（1～500字符）；校验、冻结版本、审计后发布 |
| GET `/config/{key}/history`、`/config/{key}/history/{version}` | 版本列表/指定版本，敏感引用按角色投影 |
| POST `/config/config/rollback`、`/config/script/rollback` | `version>=1,confirm_text="CONFIRM",change_note`；历史内容以新版本发布，不改历史 |
| POST `/config/test-connection`、`/config/test-capability` | super_admin/tech_ops；严格测试请求，只测试指定配置，不自动发布/启用能力 |
| GET `/capability-evidence/{evidence_report_id}` | 五角色可读元信息；原始证据及操作者仅super_admin/tech_ops |
| POST `/config/capabilities/{capability_key}/force-test` | 服务层最终仅super_admin；`effective_scope="test",confirm_text="CONFIRM",reason`（1～500）；留审计；当前运行消费缺口见TD-042 |

测连接受空JSON或省略Body；能力测试精确Body `{capability_key}`，每次一项；请求开始冻结草稿，默认服务端60秒期限，取消/超时清理runner。

测试结果用 `data.status=passed|failed|error` 表达，Provider失败仍可为 HTTP200/code0；包含 nullable latency_ms、failure_category、`test_version=admin-voice-test/v1`、tested_draft_revision、tested_at，能力测试另含key/run/report引用。failure_category为none/invalid_config/credential_missing/authentication_failed/timeout/upstream_unavailable/protocol_error/evidence_invalid/internal_error。不回传密钥。通用schema错误422、权限401/403；业务错误20071～20078分别为参数、冲突、未找到、无草稿、缺凭据、危机配置无效、发布失败、人格缺失，以服务错误信封为准。

测试passed写verified草稿投影、failed写failed/off、error写unverified/off，替换旧强制锚；测连不写能力状态，测试不发布active。强测需非空测试用户名单且仅允许unverified/stale，failed/verified/all拒绝；reason仅留长度与hash审计，当前运行消费缺口TD-042不被强测成功响应掩盖。

六能力声明/证据/运行有效值是三个不同事实。指纹、TTL、过期/跨版本证据规则见[data.md](data.md#configuration)；没有公开任意证据导入接口。当前profile与测连发布联动缺口保留TD-041，不能描述为已经完整门禁。

<a id="master-quota"></a>
## 独立总开关与人工额外时长

| 方法 / 完整路径 | 权限 / 请求 | 结果与约束 |
|---|---|---|
| GET `/api/admin/voice/master-switch` | 五角色 | enabled/version/updated_at/updated_by；独立发布行，缺失或无效失败关闭 |
| POST `/api/admin/voice/master-switch/publish` | super_admin/tech_ops；严格bool enabled，严格int expected_version>=1 | 乐观锁；相同值不升版本。开启校验已发布语音包/人格/凭据/能力条件；关闭不要求通过开启检查；DB与审计同事务 |
| GET `/api/admin/voice/users/{user_id}/quota` | super_admin/ops_admin/observer | quota_date,daily_free_seconds,free_remaining_seconds,extra_remaining_seconds,remaining_seconds,version |
| POST `/api/admin/voice/users/{user_id}/quota/extra` | super_admin/ops_admin；严格int seconds 1～86400、expected_version>=0 | 单用户加时、版本冲突409，账户与审计同事务；不支持减时/批量修改 |

总开关 `voice_call_master_switch` 独立于运行配置与话术，旧 `global.enabled` 仅保留兼容。开放范围、维护和软停仍独立生效。新发布每日额度对已用/未用旧账户均按当前额度减已用秒数计算，保留额外秒数，不把存量300秒账户永远冻结在300；快照中的通话规则不因此改写。

<a id="admin-ops"></a>
## 运维与危机

| 方法 / 完整路径 | 权限 / 语义 |
|---|---|
| GET `/api/admin/voice/ops/active-calls` | super_admin/tech_ops/observer；活跃元信息，无正文 |
| POST `/api/admin/voice/ops/soft-stop` | super_admin/tech_ops、CONFIRM；阻止新建，不强结束既有 |
| POST `/api/admin/voice/ops/hard-stop` | super_admin/tech_ops、CONFIRM；停止新建并请求结束既有，逐项报告结果 |
| POST `/api/admin/voice/calls/{call_id}/force-end` | super_admin/tech_ops、CONFIRM；幂等结束，报告结算/清理状态 |
| GET `/api/admin/voice/crisis-records`、`/crisis-records/{record_id}` | 仅super_admin；列表page默认1/page_size默认20最大100，AI事故优先、时间/id倒序；列表不含原文/命中词，详情仅未过期时含content_plaintext/matched_keyword；逐记录（空列表也有一次）审计/no-store；不提供危机导出 |

<a id="admin-records"></a>
## 通话记录、导出、删除与任务

| 方法 / 完整路径 | 权限 / 语义 |
|---|---|
| GET `/api/admin/voice/calls` | super_admin/ops_admin/observer；分页/过滤、默认不含已删除记录 |
| GET `/api/admin/voice/calls/{call_id}` | 同上；公开元信息及合法未到期摘要 |
| GET `/api/admin/voice/calls/{call_id}/turns` | 同上；仅有效正文投影；after>=0、limit默认50最大200 |
| GET `/api/admin/voice/calls/{call_id}/usage` | 同上；账本、有效/计费/免费/额外秒数 |
| GET `/api/admin/voice/calls/{call_id}/config` | 同上；冻结快照脱敏副本，不回写历史；super_admin可见credential_ref及当前configured布尔，ops/observer只见configured；credential_revision_ref都隐藏 |
| GET `/api/admin/voice/calls/{call_id}/audit` | 同上；通话相关审计 |
| GET `/api/admin/voice/calls/{call_id}/debug` | 仅super_admin；有效期内生成正文/推理诊断；不包含隔离危机原文 |
| POST `/api/admin/voice/calls/export` | super_admin/ops_admin，observer显式拒绝；严格call_ids 1～100，去重、缺失则全批404；只导出call_id、turn_index、user_text_final、assistant_text_effective、effective_text_expires_at五字段有效转写投影，固定now、按call_id/turn_index加锁校验后审计，成功data为items/snapshot_at；过期/隔离行不输出空壳 |
| DELETE `/api/admin/voice/calls/{call_id}` | 仅super_admin；先锁任务设置删除围栏再清理，保留账本/成长/已成功向量及必要元信息；成功data含call_id/changed/cache_keys/deleted_at，不含完整对象；异常503固定提示；不等于账号注销 |
| GET `/api/admin/voice/calls/{call_id}/jobs` | super_admin/ops_admin/observer/tech_ops；kind memory/postprocess/followup、after/limit；只给任务元信息，符合条件才返回retry_path，无提取快照或正文 |
| POST `/api/admin/voice/jobs/{job_id}/retry` | super_admin/tech_ops；失败记忆任务满足保留期/围栏/快照条件才允许补跑，返回job_id/job_type=memory/status/attempt_count；累计尝试不重置，不增加耗尽的自动预算 |
| POST `/api/admin/voice/summary-jobs/{job_id}/retry` | super_admin/tech_ops；失败摘要任务的受限补跑 |

列表 Query：page默认1、page_size默认20最大100、user_id、status、end_reason、provider、model、config_version、summary_status、memory_status、postprocess_status、interrupted、expired、cleared、audit_view；deleted只在audit_view使用；started_from含起点/started_before不含终点，UTC时间。**尚不支持voice_id过滤**（TD-043）。

上述记录读写实施R04审计：每请求摘要和call_reference使用同request_id；列表过滤白名单，provider/model/end_reason等自由文本仅散列，不记未知参数、正文和密钥。合法身份的拒绝与业务失败同样留痕；未认证不伪造管理员身份。审计失败不返回成功正文。导出和详情共享保留期/删除/安全投影，不能从调试正文回补有效正文。

<a id="admin-metrics"></a>
## 指标与成本只读接口

五角色均可读，前缀 `/api/admin/voice/metrics`：GET `/dictionary`、`/daily`、`/observations`、`/history`、`/billing-preview`。daily/observations要求day；history要求start/end，daily/history可选simulated_pricing=false；history最多31日。口径、空值和维度以[data.md](data.md#metrics)为唯一事实定义；看板不能用UTC重试样本替换业务日分母。

- daily从持久化源只读计算；history读已物化日聚合，标记 `current_durable_state`；observations读短期Redis样本，字典提供来源/单位/空值原因。普通估算未配置价格返回null，显式 `simulated_pricing` 使用模拟单价和独立维度。
- billing-preview要求起止日与账单起止日对应，含首尾最多31日、同币种三位大写、unit minute/second、非负十进制单价/账单成本，6位ROUND_HALF_UP。只计算返回，不写真实账单，不以模拟数据冒充商业对账。

<a id="admin-prompts-playback"></a>
## Prompt 只读与管理播放

- GET `/api/admin/voice/prompt-view`、`/prompt-view/{prompt_key}`：super_admin/ai_trainer/observer；7个Tab展示10个当前执行源码模板：call_answer、recall、memory、summary、time_low、silence_confirm、goodbye、silence_fallback、closing_review、followup_review；保留占位符，不拼出用户私有单通完整Prompt。会前 `context_pack.voice_instruction_template` 仍是配置页的独立可编辑模板。
- POST `/api/admin/voice/config/test-playback`：super_admin/tech_ops；独立NDJSON流 `audio/playback_end/result`，不采麦克风、24k PCM，不改变正式能力。
- POST `/api/admin/voice/config/test-playback/{test_id}/ack`、`/api/admin/voice/config/test-playback/{test_id}/stop-ack`：同角色且原管理员；绑定call/session/reply/audio_bytes（最多4MiB），仅实际音频播放完成后ACK；stop-ack包含真实播放时长与停止事实，played_ms与字节/48取整一致。过期/身份/状态冲突409，格式422。Redis只存短效身份，默认60秒；单管理员一个探针，Provider45秒/总体60秒上限。收到音频不等于实际播放成功。

能力测试同时支持Accept: application/x-ndjson：复用audio/playback_end/result和播放ACK，独立事务提交证据/草稿投影/审计。管理截断按实际已播前缀512查询→513截断→512读回，目标/ACK/前缀不唯一或不匹配为error/unverified；音频只在本请求内使用，不保存PCM。每次探针只获一个指定操作权限，不进入业务snapshot或自动重试；keep_alive不发送push_to_talk专用515。命中回答不证明RAG生成等待门，未知/超时不当成可信不支持。
