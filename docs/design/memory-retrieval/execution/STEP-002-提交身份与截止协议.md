---
title: "STEP-002 提交身份与截止协议"
status: PLANNED
authority: false
authority_scope: STEP_002_CHAT_PROTOCOL_DESIGN
business_code_status: NOT_STARTED
updated: "2026-10-09"
---
# STEP-002 提交身份与截止协议

> 本附录是 STEP-002 任务2/3/4/6/9的唯一聊天协议设计明细；主定稿文档引用本页，不另抄字段/表名。所有新增能力、参数和结构均为 **PLANNED**，不是运行契约或实施完成证据。
> **2026-10-09 USER_DECISION已确认功能超时口径：数据库事务内最终CAS为业务裁决点，不要求证明物理落盘时刻。** 固定180秒、Step1.5/Step2各45秒、每个失败调用最多重试一次、断线不取消且同代不续时均保持；详见§2。

## 1. 来源与已核查事实

依据：[PRD §7.2/7.4/7.5/9.3.2](../PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md)、[STEP-002](../steps-verified-v3.2-后台闭环修正版.md)、[聊天接口](../../../contract/current/chat-emotion/api.md)、[聊天数据](../../../contract/current/chat-emotion/data.md)、[OpenAPI](../../../contract/current/openapi/api.md)、[共享信封](../../../contract/current/_shared/conventions.md)。源码基线HEAD为`9c6f9855f5f2808a21c9e6bd761847198df2d516`；本页不读取历史/迁移基线。

| REPO_BASELINE定位 | 已核实事实及设计约束 |
|---|---|
| `backend/schemas/chat.py:7-24` | content为1–2000字符；send ID可选且≤64，resend ID可选且≤128；无最短长度、UUID、字符集限制。空串/Unicode/斜杠不能擅自改为非法 |
| `frontend/pages/chat.html:1289-1302,1375-1385` | fetch前生成UUID或时间戳+随机fallback，body和Idempotency-Key同发；当前ID仅局部变量，无持久核实索引 |
| `backend/routers/chat.py:719-777`、`services/chat_service.py:251-308` | ID/header未进入enqueue；现有字段不等于幂等。send先Redis换代/作废Future，后SQL保存user；resend先Redis扣配额再换代 |
| `utils/auth_middleware.py:13-48`、`utils/open_api_auth.py:31-75` | H5取JWT真实user，Open取API Key数据库归属；Open认证可能更新last_used_at，属于鉴权元数据 |
| `routers/open/chat.py:17-42`、`services/open_chat_service.py:57-73` | Open send只有content、resend无Body；success为messages/emotion/round_id；obsolete→10108，其余聊天业务错误透传，无另一套转换器 |
| `chat_queue_service.py:19-20,49-112` | generation Redis TTL7天；恢复锁值恒1/TTL90秒/无条件DEL；正常防抖及resend未统一持锁。resend为INCR后EXPIRE，默认同batch每60秒2次 |
| `chat_service.py:80-155,158-216` | 窗口为最后assistant之后user；send quota是≥5且无叹号的队列检查，**没有发送计数扣额表**。恢复只在满队全pending时触发；Future/result进程内，wait_for120秒且finally删除共享注册 |
| `routers/chat.py:467-576,227-310,632-639` | 最后核代早于安全/Step5.5；success/failure helper无代际条件；外层异常可能唤醒当前新代。成功事务写user状态、N条assistant与emotion_log |
| `services/step8_subchain.py:169,216-264,376-455` | 正常和人格风险兜底分别独立commit；正常有Step6及衰减/pt+1，兜底没有 |
| `services/future_handler.py:93-185` | 正常/兜底True都再经Handler pt+1和agent:count；成功失败均无条件清槽。正常链因此有两个既有pt+1执行点，本期不得偷偷合成一次 |
| `frontend/pages/chat.html:1293-1304,1340-1352,1437-1465` | 120秒timer在fetch返回就清掉，并非覆盖SSE消费；网络异常当前被写成失败；历史loadTimeline受noMoreTimeline/cursor限制 |
| `routers/admin/users.py:44,258-391` | Admin历史依super_admin/ops_admin/observer独立鉴权，先count/union分页再批量实体读取；身份为message_source+id |
| `routers/chat.py:719/757/781/825`、`routers/open/chat.py:17/26/34` | 拟新增两条submissions GET无现有路由冲突；普通单段request_id必须解决既有任意ID的传输编码 |

## 2. 截止判据：2026-10-09 USER_DECISION已确认

用户最新明确决定：“这就是个功能限制，不能因为这个限制阻[止]开发，如果整体流程180s失败就算是失败”。据此本期采用**最终原子CAS的业务裁决时间**，覆盖此前将截止解释为“数据库物理提交完成时刻”的要求；不再引入物理提交时刻证明门槛、binlog观察器或GTID配置改动。该确认由主定稿文档同步到PRD/STEP，本页据此给出唯一实施口径。

整轮原起点与D持久化；D=起点+180秒，包含防抖/排队/上下文/检索/Prompt/回复/安全及最终成功业务裁决。每阶段截止=min(阶段起点+45秒,D)，重试及退避在阶段内，成功调用不重跑。D后不新增生成调用、不首次成功CAS；连接/核实余量不提供新的业务预算。

| 情形 | 唯一裁决与对外结果 |
|---|---|
| D前合法成功CAS，事务最终commit成功 | 同一事务持锁裁决并记录decision_at/result/terminal；实际落盘或回执可稍后，确认后仍成功，不另起生成 |
| 到D仍无成立的成功裁决 | 收口为failed_timeout（业务state=failed、reason=deadline_exceeded）；迟到模型不得再通过成功CAS，即使失败扫描尚未运行 |
| commit回执丢失 | 只读核实同一commit_marker对应的持久decision和结果；不能将超时后另建成功包装成“核实”，也不看created_at猜测 |
| 原事务确认rollback | 未形成有效成功裁决；D已过则超时失败，原user消息沿失败/重发资格处理，不自动重生成 |
| 原事务仍未知或数据库不可读 | 保持unverified至有限核实界并告警；未知不是正常执行中，不提供resend或新生成权限 |

本地只读元数据（2026-10-09）：MySQL8.0.46，log_bin=ON、ROW、sync_binlog=1、innodb_flush_log_at_trx_commit=1、binlog_order_commits=ON；gtid_mode/enforce_gtid_consistency/session_track_gtids均OFF，日志保留30天；容器与宿主常见PATH未找到mysqlbinlog。没有读取业务binlog正文或修改变量。

官方8.0.46源码在`write_transaction`的1711–1716行，为复制延迟监测取`immediate_commit_timestamp`；`ordered_commit`依次经过8899的flush、8972/9000的sync、9025/9075的commit阶段；8556及11633调用引擎提交。该时间早于日志同步/引擎commit。[赋时源码](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql/binlog.cc#L1711) · [提交顺序](https://github.com/mysql/mysql-server/blob/mysql-8.0.46/sql/binlog.cc#L8899)；官方定义服务于复制延迟监测，[MySQL文档](https://dev.mysql.com/doc/mysql-replication-excerpt/8.0/en/replication-delayed.html)。

上述元数据/源码证据只解释为何将业务截止与存储确认分开，**不再作为开发门槛**。decision_at是最终CAS在数据库内的裁决时间，不是物理commit时间；“请求发起时间、模型完成时间、created_at或先填一个时间戳”均不能替代该裁决。

## 3. 身份、输入与两个只读接口

唯一域固定为可信`user_id + operation + raw_request_id`；operation=`send|resend`，channel/API Key版本不进入去重域。request_id不是generation或message_id。

| 入口 | 身份来源、校验与兼容 |
|---|---|
| H5 POST `/api/chat/send` | body `client_message_id`；原可选≤64约束不变；H5附送header不另设身份域，body为准 |
| H5 POST `/api/chat/resend` | body `client_resend_id`；原可选≤128约束不变，仍不新增user |
| Open原send/resend | 新可选`Idempotency-Key`；send≤64、resend≤128；不增加必填Body字段。无头旧调用方可用，但全回执丢失时不保证精确关联 |
| H5 GET `/api/chat/submissions/{operation}/{request_id}` | `get_current_user`；查询条件始终带真实user |
| Open GET `/api/open/v1/chat/submissions/{operation}/{request_id}` | `get_current_user_by_api_key`；同service、独立API Key认证 |

GET的path `request_id`统一为`b64.`+无padding的base64url(原ID的UTF-8字节)，响应仍返回原字符串；空串为`b64.`。解码须规范往返且满足对应operation原长度，非法编码/operation→422。客户端helper负责编码；不可用普通URL encode假定斜杠、空串、`..`均安全。校验Unicode、`/`、`%`、空白、空串及长度边界的往返。

省略/null身份沿兼容路径，由服务端为内部持久记录生成UUID并标`client_key_present=false`；碰撞时仅为未接收内部身份重选。空串是有身份。ID按原字节精确比较，不trim、不Unicode归一化、不使用大小写不敏感索引。

send指纹是版本1的canonical JSON（字段固定顺序、UTF-8、无多余空格）：`{"operation":"send","content":<既有strip后实际接受正文>}`的SHA256；不掺模型/时间/channel。resend首次在锁内冻结既有未闭环窗口及最小sort_seq batch锚点，指纹为operation+该目标ID有序列表；当前请求没有显式目标字段，重复ID直接核实冻结目标，不能以“现在窗口不同”再次扣额。未来若引入可选显式目标，必须与冻结目标比较；本期不新增该字段。

### 3.1 响应字段（两GET完全相同）

正常查询`HTTP200 ApiResponse.ok(data=SubmissionStatus)`；鉴权401、形状422及未捕获500保持项目既有非ApiResponse边界。查询不触发模型、准入、补偿或收口写；仅认证last_used_at等原元数据可照旧发生。

| 字段 | JSON类型/空值与枚举 |
|---|---|
| operation / request_id | string，原操作与原ID |
| admission_state | `accepted/not_found/expired/unverified` |
| processing_state | `pending/success/failed/superseded/unverified`或null；未找到/过期不等于失败 |
| status_reason / state_origin | string或null；受控reason，origin=`lifecycle/legacy/unavailable` |
| state_revision | 十进制string或null（BIGINT不可假定JS安全整数） |
| status_observed_at | UTC ISO8601含微秒与Z，观测时间，不伪装提交时间 |
| accepted_generation_id / effective_generation_id | UUID string或null；首次与当前承接代分别表达 |
| accepted_at / original_deadline_at / effective_deadline_at | UTC string或null；同代值不变 |
| reconcile_until / dedupe_expires_at | UTC string或null；固定窗口，GET不滑动延长 |
| source_messages | array `{source:'user',id:int,sort_seq:string}`；send一行、resend冻结窗口 |
| result | null或`{round_id:string,messages:[{id:int,sort_seq:string,type:'text',content:string}],emotion:{label,confidence}}`，直接从既有成功行读取 |
| can_resend | boolean，由当前有效窗口、失败类型及无未知提交共同决定；真实POST仍再次检查 |

success结果定位直接用服务端message/round ID，不扩改Open timeline固定十字段、不依赖历史分页或相似文本。无Prompt/候选/凭据输出；其他user同ID与本人不存在都返回not_found，不泄露是否跨用户存在。

### 3.2 身份/错误与投影矩阵

| 情形 | 响应与副作用 |
|---|---|
| 同ID同输入、已接收pending | 等待/读取同一当前有效代；不新增user/额度/代/模型流程 |
| 同ID同输入、已成功 | H5重放已有SSE内容，Open保持`data.messages/emotion/round_id`；来源均是已存结果 |
| 同ID同输入、已失败 | 沿原10101/10102等错误，不自动再次生成；新显式resend须新ID并过原资格 |
| 同ID异输入/显式异目标 | 新增PLANNED `ERR_CHAT_REQUEST_ID_CONFLICT=10109`，HTTP200业务失败；原映射不变，不返回旧正文 |
| 不同ID同正文 | 不去重，沿原队列/额度/合并规则 |
| 跨user同ID / 同user跨入口同ID | 前者独立隔离；后者同一去重域，Key轮换不重复执行 |
| G1作废但消息由G2承接 | 返回G2当前状态/D/revision，保留accepted_generation=G1；不将消息永久标失败 |
| 无承接的真实superseded | Open沿10108；H5沿obsolete事件；GET返回superseded且can_resend=false |
| 无记录/墓碑/DB无法核实 | GET code0分别not_found/expired/unverified；前二processing=null，后者unverified；均can_resend=false，不自动重发 |
| 同步POST到等候上限仍未知 | 新增PLANNED `ERR_CHAT_SUBMISSION_UNVERIFIED=10110`，HTTP200业务失败，data带身份/只读定位/can_resend=false；不可复用10102冒充确定失败 |
| 原业务拒绝 | 10100空内容、10101安全、10104满队、10105重发限额、10107无重发资格；10106已有重复忽略码不改作身份冲突 |

10109/10110经基线constants静态核对未占用，实施时再核对并统一登记。H5 meta/done增量携身份、服务端消息/round、generation、revision；delta携同代/修订或由已绑定流上下文定位；保留原type/messages/emotion。客户端不得以TCP断开/本地timer判业务失败。Open调用方的本地timeout无法由本项目强制改变，接入说明明确未知只读核实。

## 4. PLANNED物理schema：本页统一命名

共同约定：下列新表均InnoDB；`UUID=CHAR(36) CHARACTER SET ascii COLLATE ascii_bin`，`T=DATETIME(6)`存UTC，`REV=BIGINT UNSIGNED`；ID/枚举明确区分大小写。所有表均有`created_at T NOT NULL, updated_at T NOT NULL`，仅真实写入更新updated_at。除注明NULL外全部NOT NULL；无匿名user。状态约束同时有Pydantic/领域校验和MySQL CHECK。所有查询/更新同时带user_id及资源身份。用户归属FK采用ON DELETE CASCADE；生命周期内部FK不自动级联删除未决结果，按§6有序清理。chat_generation与future_consumption均另有`timing_config_version VARCHAR(64) NOT NULL`，记录本次冻结参数版本。

| 新表 | 完整领域字段、索引/约束 |
|---|---|
| `chat_user_state` | `user_id INT PK FK users(id) ON DELETE CASCADE; current_generation_id UUID NULL; state_revision REV DEFAULT 0`；current_generation引用同user的generation；这是接收/换代/终态共同锁点 |
| `chat_generation` | `generation_id UUID PK; user_id INT FK users; accepted_at T; deadline_at T; state VARCHAR(16); phase VARCHAR(24); state_revision REV; reason VARCHAR(64) NULL; round_id UUID NULL; commit_marker UUID NULL; decision_at T NULL; commit_observed_at T NULL; commit_evidence_kind VARCHAR(24) NULL; lease_owner UUID NULL; lease_epoch REV DEFAULT 0; lease_until T NULL; dispatch_state VARCHAR(16); next_dispatch_at T; remote_started_at T NULL; reconcile_until T; terminal_at T NULL`；UNIQUE(user_id,generation_id)、UNIQUE(round_id)、UNIQUE(commit_marker)；INDEX(state,deadline_at)、INDEX(dispatch_state,next_dispatch_at)、INDEX(phase,reconcile_until) |
| `chat_submission` | `id BIGINT UNSIGNED PK AUTO_INCREMENT; user_id INT FK users; operation VARCHAR(8); request_id VARBINARY(512); client_key_present BOOLEAN; fingerprint BINARY(32) NULL; fingerprint_version SMALLINT UNSIGNED NULL; channel VARCHAR(16); accepted_generation_id UUID NULL; accepted_at T; expires_at T; tombstone_until T; record_state VARCHAR(12)`；UNIQUE(user_id,operation,request_id)、UNIQUE(user_id,id)；INDEX(record_state,expires_at)；active时fingerprint/version/accepted_generation必填，tombstone可清关联但保留身份 |
| `chat_submission_message` | `submission_id BIGINT UNSIGNED; user_id INT; conversation_id INT; ordinal INT UNSIGNED`；PK(submission_id,conversation_id)、UNIQUE(submission_id,ordinal)；同user复合FK到submission和conversation；INDEX(user_id,conversation_id) |
| `chat_message_state` | `conversation_id INT PK; user_id INT; effective_generation_id UUID; state_revision REV; processing_state VARCHAR(16); reason VARCHAR(64) NULL; status_changed_at T`；同user复合FK到conversation/generation；INDEX(user_id,effective_generation_id)；每消息仅一份当前投影 |
| `chat_generation_message` | `generation_id UUID; user_id INT; conversation_id INT; ordinal INT UNSIGNED; in_prompt BOOLEAN`；PK(generation_id,conversation_id)、UNIQUE(generation_id,ordinal)；同user复合FK；冻结窗口及last10，不复制正文 |
| `chat_resend_quota` | `user_id INT FK users; batch_sort_seq BIGINT; window_started_at T; expires_at T; accepted_count SMALLINT UNSIGNED DEFAULT 0`；PK(user_id,batch_sort_seq)，CHECK accepted_count BETWEEN 0 AND 2；INDEX(expires_at)；固定60秒窗口，限额2次，不能由重复身份刷新 |
| `chat_lifecycle_effect` | `id BIGINT UNSIGNED PK AUTO_INCREMENT; user_id INT FK users; owner_kind VARCHAR(8); owner_id UUID; effect_kind VARCHAR(32); state VARCHAR(16); attempts SMALLINT UNSIGNED DEFAULT 0; next_attempt_at T NULL; lease_owner UUID NULL; lease_until T NULL; last_reason VARCHAR(64) NULL; effect_date DATE NULL; completed_at T NULL`；UNIQUE(owner_kind,owner_id,effect_kind)；INDEX(state,next_attempt_at)；owner_kind=`chat/future`，领域校验对应同user owner存在 |
| `future_consumption` | `consume_id UUID PK; user_id INT FK users; slot_version REV; slot_timestamp INT; slot_action VARCHAR(200); accepted_at T; deadline_at T; state VARCHAR(16); phase VARCHAR(24); state_revision REV; reason VARCHAR(64) NULL; success_kind VARCHAR(8) NULL; agent_message_id INT NULL; round_id UUID NULL; commit_marker UUID NULL; decision_at T NULL; commit_observed_at T NULL; commit_evidence_kind VARCHAR(24) NULL; lease_owner UUID NULL; lease_epoch REV DEFAULT 0; lease_until T NULL; remote_started_at T NULL; reconcile_until T; terminal_at T NULL`；UNIQUE(user_id,slot_version)、UNIQUE(agent_message_id)、UNIQUE(commit_marker)；INDEX(state,deadline_at)、INDEX(phase,reconcile_until)；agent_message引用同user实体 |

既有表增量：`relationship.future_slot_version REV NOT NULL DEFAULT0`；`conversation_log`与`agent_message`各加`UNIQUE(user_id,id)`供同user复合FK（原PK/id/排序不变）。不新增整段对话副本；既有round_id允许一轮N条assistant，**不得**给conversation_log.round_id单列加UNIQUE。chat_generation.round_id唯一仅限制一代一轮。

状态字典：generation/consumption `state=pending/success/failed/superseded`；`phase=admitted/running/commit_prepared/commit_unknown/reconcile_exhausted/terminal`；`dispatch_state=pending/claimed/done`；submission `record_state=active/tombstone`；effect `state=pending/running/done/failed/unverified`；success_kind=`normal/fallback`；channel=`h5/open/internal`。commit_evidence_kind只允许`atomic_decision`或NULL，表示同事务持久裁决，不依赖引擎审计或GTID。unknown是结果知识状态，投影为unverified，不伪造已确认失败。

约束：deadline_at=accepted_at+180秒；reconcile_until=deadline_at+本次冻结margin（默认60秒）；success须有唯一结果身份、同事务持久CAS裁决且decision_at<deadline_at，failed/superseded无首次成功结果；terminal单向不可覆写。所有接受/归属/状态改变（含Future消费）在user_state下分配严格递增revision，再写同次快照；JSON输出为字符串。terminal_at取成立的终态裁决时间；commit_observed_at仅是确认观测时点，迟到不否定原成功。reason只允许`llm_failed/content_blocked/prompt_budget_exceeded/prompt_budget_unverified/deadline_exceeded/generation_superseded/execution_lost/commit_unknown/deadline_unverified/storage_unavailable/legacy_record/legacy_pending/id_conflict/expired`及NULL；原异常正文只进受控日志，不进回执。

## 5. 事务、调度和恢复顺序

### 5.1 接收与代际

1. 完成认证/请求形状与现行正文规范化；有ID者先查已登记关联，**锁内再查**，重复身份在再次扣额、入队、换代之前收敛。原已接受重复不重复执行安全/模型流程。
2. 固定锁序：`chat_user_state → 当前generation/consumption → relationship（若涉及）→ 消息状态/额度 → user_timeline_seq`；多消息按ID升序。首次state行用唯一约束初始化并重读，deadlock只允许重试尚未发生远端/提交未知的本地事务，不重复业务调用。
3. 在一个SQL事务中：锁内复查队列/资格；send写user与sort_seq，resend冻结原窗口并消耗SQL quota；写submission及关联；创建新generation、持久起点/D与dispatch=pending；只作废未成功旧代；将可承接消息转交新代并写revision。user/额度/身份/有效代一起commit。
4. accepted_at在取得准入相关行锁后，用独立`SELECT UTC_TIMESTAMP(6)`取本次新鲜DB UTC时间，D=accepted_at+180秒；其后准入事务耗时包含在预算内，只有事务被确认成立才对外称合法接收。明确rollback不影响旧代；未知先核实同ID，不能任意恢复旧代或补建新代。
5. commit确认后才发Redis提示/唤醒dispatcher、注销旧观察者；generation的dispatch字段就是本期持久outbox，**不另建跨服务任务平台**。commit后通知前退出，由启动/周期扫描发现，包括1/2/3/4条pending。
6. dispatcher领取携带`user_id,generation_id,lease_epoch,绝对D`，不能仅传user_id再读取当前代重新执行。已admitted且未remote_started可用原剩余预算安全恢复；已开始远端而失主者先核实结果，不默认重放模型流。无成功且可证明旧worker失权时收口execution_lost；未知则保持unverified。

resend SQL窗口：首次真实接受设置window_started_at/expires_at=+60秒；过期后锁内重置；未过期且count=2返回10105；同ID重查不消费/刷新。沿原业务含义2次/60秒，不复制Redis拒绝请求继续INCR的实现瑕疵。send仅原5条检查，不新增收费/发送额度。

### 5.2 终态仲裁

成功、失败、deadline收口、换代全部走共同事务仲裁；锁内校验当前归属、epoch、非终态与截止，user状态、N条assistant/agent_message、emotion及唯一结果/terminal关联与最终CAS同事务。旧任务任何异常只能处理自己携带的身份，不能重新取当前gen唤醒或修改新代。

最终成功CAS顺序：先按固定顺序拿齐相关行锁并完成结果暂存/flush（尚未对外可见），再**独立执行`SELECT UTC_TIMESTAMP(6)`**检查原D；不能复用事务开始时间、应用时钟或开始于锁等待前的同一SQL语句时间。随后最终UPDATE CAS再次以自身语句的新鲜`UTC_TIMESTAMP(6)`同时赋decision_at并检查`deadline_at > UTC_TIMESTAMP(6)`、state=pending、user/gen/epoch/当前归属；相关锁已持有，不允许拿锁等待前的旧now通过。CAS影响行数必须为1；恰好等于D也拒绝成功。fresh SELECT用于锁后预检，UPDATE自身时间避免两语句间调度跨D仍放行。

CAS失败要回滚全部暂存成功消息/情绪/关联，再在锁内确认实际终态；D已过且无成立成功则原子写state=failed、reason=deadline_exceeded并将本代参与user标failed_timeout。迟到模型即使先于失败扫描回库也无法首次成功；不能只靠5秒扫描“最终会超时”保护截止。成功与新输入同锁顺序竞争，已成功不可撤销。

CAS与结果事务最终commit成功后才发布success；rollback表示该CAS未成立。commit未知时使用新会话的主库锁定读/当前读等待原事务结束，核对同commit_marker、state、decision_at、epoch及结果身份：读到成立的D前成功即保留，读到明确无成功且D已过才超时失败；仍无法核实则unverified。不能使用REPEATABLE READ旧快照或created_at猜结论，不能重放原成功事务或D后补做成功CAS。实际落盘/回执稍晚不改变已成立裁决。

正常/兜底开事务helper都必须显式接收`generation_id或consume_id、epoch、D、commit_marker`，不能在外层核一次就遗漏helper。commit未知时先等原事务结束并按marker查主库，禁止普通False/10102收口。后置Step6/成长/情绪/衰减/计数异常单独记录effect，不回滚既存成功。

Redis只作提示。若保留锁，值为owner UUID+epoch，compare-owner Lua续期/释放，15秒lease/5秒续期；SQL epoch才是写资格。丢锁停止并核实，旧owner不得DEL新锁或继续无条件提交。锁持有/续期不刷新D；D后仅允许既有裁决事务确认/核实或失败收口，不新生成或首次成功CAS。

连接等待使用独立observer或shield共享通知；超时/注销仅移除本observer，不能清有效业务注册。SQL是恢复权威，内存Future丢失不代表失败。启动立即扫描，再按5秒/100条分批扫dispatch、过期lease、deadline、unknown核实；持续依赖故障到固定核实界发去重告警并标reconcile_exhausted，不能无限正常pending。

last10之外保留skipped_in_prompt；代收口时消息processing_state也收口，不能留下永恒pending。success在此表示归属代已成功，不声称该消息参与Prompt；原delivery_status与skipped兼容输出保留，展示明确区分。

## 6. 有限参数、窗口与保留

以下是本页PLANNED技术默认，实施前校验，不是现有值或新增用户可编辑记忆配置；进程启动加载带版本参数，非法值启动拒绝，不在请求中无名常量回退。业务180/45/一次失败调用重试不是可编辑字段。

| 参数 | 默认；允许范围/交叉校验 | 生效/依据 |
|---|---|---|
| text_status_poll_interval_ms | 2000；1000–10000 | 可见pending常规间隔，180秒约90次轻量GET |
| text_status_poll_max_interval_ms | 10000；normal～30000 | 错误退避上限，60秒核实窗内仍有多次机会 |
| text_status_poll_backoff_factor | 2；大于1且≤3 | 2/4/8/10秒，读成功恢复normal，不重置总窗口 |
| text_status_probe_timeout_ms | 3000；500–10000 | 单次timeout=min(配置,剩余核实窗)，纯SQL读不等模型 |
| text_status_reconcile_margin_ms | 60000；10000–120000 | D后的只读核实余量，不授予生成权限 |
| text_admission_reconcile_window_ms | 240000；180000–300000 | meta前未知从首次提交前固定本地起点观察；not_found不证明永不会晚到 |
| text_status_max_inflight_per_target / per_page | 1固定 / 2（1–5） | 同目标合并事件，多目标公平调度、独立终止 |
| text_lifecycle_scan_interval_ms / batch_size | 5000（1000–10000）/100（1–500） | 启动即扫，后续索引分页，SQL领取防并发 |
| text_submission_retention_seconds | 604800；≥180+margin且≤2592000 | 首次接受后7天完整身份保障，沿当前Redis7天量级的技术选择，非现有SQL保证 |
| text_submission_tombstone_seconds | 2592000；≥完整保障期 | 首次接受起算总30天；保障结束后只留最小身份/过期标记，明确expired |
| text_local_submission_retention_seconds | 604800；≤服务端完整保障期 | 按登录用户保存最小ID/已知关联/首次提交时点，不另存正文/凭据 |
| text_commit_prepare_reserve_ms | 5000；1000–10000 | 最终CAS/取消收口预留，不能替代CAS截止校验或扩大D |
| text_server_wait_margin_ms | 10000；1000–30000 | 有效D+10秒连接等候，未确定返回unverified而非失败 |
| text_client_transport_margin_ms | 20000；≥server margin且≤60000 | 有效D+20秒覆盖完整SSE消费；未获D前从首次fetch计200秒仅管连接 |
| text_lock_lease_ms / renew_ms | 15000 / 5000；0<renew<lease≤30000 | owner比较、SQL fence权威；实际TTL不超过剩余生命周期及核实界 |
| proxy_read_timeout | 仓库当前300秒；部署需核实 | 上游读取空闲超时，非总时长；另有connect75秒，不统一称180秒 |

所有身份、D、revision、核实窗在重复POST/GET、切页、进程恢复中不滑动。未知admission拿到可信有效D后跟随该D+margin；仍没拿到按固定首次窗口停止。服务端accepted/gen起点不由客户端提供。

完整保障期满只在已确定终态、无活跃承接、无commit调查时转tombstone并清关联；tombstone仍拒绝该ID重新执行，30天后可清除，之外不承诺永久去重/可查。未结案unknown不自动删除防重锚点，转异常调查保留最小记录而非持续运行；此例外不续自动核实预算。查询expired/not_found永远不会触发执行。

H5确定终态且原行/回复去重完成后清本地项；unknown到本地上限清自动观察记录并保留普通“待核实”提示，不伪造失败。登出停timer并隔离/清当前用户可见索引，下一账号不得继承。隐藏/离线只取消观察，保留本用户最小索引供恢复。

时序：0秒合法接受(D180)→30秒断线→80秒回页立即GET pending→按2秒读取→120秒success/failed更新同一行并停止；G2合法承接才带更高revision/新D，G1回页不另获180秒。170秒起DB持续不可用→最多查到240秒→停止timer并显示待核实；服务端一次告警。以后主动回页仅一次GET，不重开耗尽窗口。

## 7. Step8消费与真实副作用

扫描捕获`user_id+future_slot_version+timestamp+action`；黑名单/低分检查及子链接收均验证版本。子链原输入保持future_action，接受后D=原起点+180秒，同消费恢复不续时。返回结构`{consume_id,terminal,success_kind,agent_message_id,commit_evidence,effects}`，不能仅靠协程末尾bool。

| 结果 | agent_message | 子链Step6 | 子链衰减/pt+1 | Handler pt+1 | agent:count | 清槽 |
|---|---|---|---|---|---|---|
| normal confirmed success | 既有1条 | 既有一次 | 既有一次、原概率 | 既有一次 | 既有一次 | 仅仍匹配被消费version |
| fallback confirmed success | 既有固定文案1条 | 0 | 0 | 既有一次 | 既有一次 | 同上 |
| 提交前确定失败 | 0 | 0 | 0 | 0 | 0 | 同上 |
| commit未知 | 不发布未核实结果 | 暂不触发 | 暂不触发 | 暂不触发 | 暂不触发 | 暂不清/不重复消费 |
| 已确认成功，收尾跨D或失败 | 保留成功 | 原集合防重 | 原集合防重 | 原集合防重 | 原集合防重 | 条件清槽，不改业务失败 |

normal的两个pt+1执行点分别对应`normal_decay`与`handler_proactive`，各自上限3，保持原次数/顺序。SQL effect唯一记录与相应更新同事务。Redis计数用Lua原子“消费effect去重标记+INCR+EXPIRE”，重复核实不再加；计数UTC日期冻结于成功所属日，恢复隔日不加到新日。该去重标记保留至少消费身份保障期，不用SQL done与Redis INCR两个独立操作冒充原子。

所有写/清槽推进future_slot_version，必须适配`relationship_service.py:715/752/781`、`step8_subchain.py:430`、`future_handler.py:160/183/212`、`agent_service.py:443`；同值重建也换版，防ABA。成功计数与条件清槽命中分开：新槽出现不漏原成功计数，也不清新槽。Step6/衰减新写Future保持原触发边界，不能给fallback新增Step6。过期、低分、黑名单清理亦带捕获版本，不能仅user_id清空。

## 8. Admin/H5同源纯读投影

实现一个纯读`project_chat_message_states(user_id, message_keys, db)`供H5核实和Admin历史使用。Admin先按原count/union规则分页，再按本页复合身份批量关联chat_message_state→generation/consumption，一条消息只出一条投影；不能在分页前join一对多submission改变total。Admin保留自身RBAC，不调用用户JWT端点冒充管理员。

| 持久事实 | processing_state / reason / origin / revision |
|---|---|
| 当前有效代pending且未到D | pending / null / lifecycle / 真实revision |
| G1superseded但消息有效归属G2 | G2当前状态与revision，不能展示G1永久失败 |
| 已确认成功/失败/无承接作废 | success/failed/superseded；受控原因；lifecycle；真实revision |
| 到D但终态/提交未确认、依赖读取失败 | unverified / deadline_unverified或storage_unavailable / lifecycle或unavailable；能证实才带revision；GET不写失败 |
| 没有生命周期的旧delivered/failed | 相应历史状态 / legacy_record / legacy / null；不补造generation/D/revision |
| 旧pending且没有生命周期 | unverified / legacy_pending / legacy / null；不能装作正常新任务 |
| assistant/普通agent不适用新生命周期 | processing_state=null，origin=legacy或对应真实来源；原delivery_status=null保持 |

统一增量字段为`processing_state/status_reason/state_origin/state_revision/status_observed_at`；观察时点每次响应生成，不混入revision排序。同一真实revision输出一致业务状态；依赖失效是观测未知，不允许覆盖客户端已经确定的更高版本终态。

## 9. 故障矩阵与交接

| 故障/边界输入 | 权威观察、恢复及断言 |
|---|---|
| auth/形状/安全拒绝，user/身份/额度写失败 | 无合法接收或同事务rollback；旧gen、旧消息和额度不改 |
| 准入commit回执丢失 | 同身份主库核实，未知不盲补偿；无第二user/额度/gen |
| SQL已接收、Redis通知/调度前退出 | 持久dispatch扫描；原gen/原D，不需第5条新消息 |
| 分别1/2/3/4条pending进程退出 | 启动/到期扫描均发现；未远端可安全同代恢复，已远端不默默重放，超D无新模型 |
| 并发同ID同文/异文、不同ID同文、跨用户/入口 | 分别一次接收、10109拒绝、不同操作、隔离/共用去重域；计数/消息/代际断言完整 |
| 新输入与旧提交竞争、安全/Step5.5期间换代 | 同锁仲裁；只有合法接受才能作废旧代；旧成功不可撤销、旧失败不可改新行 |
| 179.x与180.x最终CAS竞争 | 持锁后新鲜DB UTC；decision_at<D且同事务成立才success；=D或>D拒绝成功并超时失败；物理commit/回执稍晚不反转原裁决 |
| 锁等待跨D、fresh SELECT与UPDATE间跨D | 不用等待前statement时间；UPDATE自身UTC再次检查，结果暂存整体rollback，无首次迟到成功 |
| DB持续不可用、commit未知 | 固定核实界后unverified+去重告警；无模型续时、无限pending或重复首次成功 |
| 旧锁到期、新owner持锁、旧task迟到 | owner比较+SQL epoch；旧task不能续/删/提交新owner任务 |
| 断线/timeout/多个observer取消 | 仅断观察，后台原代继续；不能删有效共享业务state或伪造失败 |
| 80回页pending→120终态、历史noMore、乱序结果 | 独立GET；原行更新、message ID去重；更低revision/旧SSE不回退当前状态 |
| 正常/兜底分别D前CAS，commit/回执或后置跨D | 同事务最终确认后保持原成功；分别原effect集合各一次，不给兜底加Step6 |
| fallback最终CAS前过D、commit未知 | helper同仲裁；前者无首次消息/计数/Step6，后者只核实原decision，不按普通False清槽 |
| 执行中产生新Future、同值重建 | version条件清理保留新槽；成功计数不依赖清槽是否命中 |
| Admin页同id不同表/多提交关联/依赖读失败 | 复合身份、total/页数/排序不变；一份纯读投影，未知不伪装legacy |
| 7天过期、30天墓碑清理、unknown未结案 | 公布保障边界；expired/not_found不执行；未知锚点不可在调查中自动删除 |

责任：014实现准入/持久代际/两GET/主链仲裁/1～4pending恢复与纯读投影；015接线两处Step8事务、结构化终态和条件清槽；016实现最小身份保存、编码、有限核实及SSE/原行去重；017/018消费Admin页后投影。模型调用数/各调用预算由主定稿文档统一，不在本页重复定义。

本页已依据2026-10-09 USER_DECISION收口功能截止协议，完成源码与只读元数据核对、设计交接；迁移/故障注入/真实入口/浏览器/部署Nginx均未验证。物理落盘时刻证明不再阻止本期实施；整体进度只记STEP §3，本页不裁决M2完成或宣称运行通过。
