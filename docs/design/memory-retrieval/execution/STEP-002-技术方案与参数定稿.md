# STEP-002：技术方案与参数定稿

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


日期：2026-10-09。文档版本：`m2-design-20261009.1`。全部新增表、接口、参数与算法均为 **PLANNED**；本文是 STEP-002 唯一技术入口，不是运行契约或第二份进度记录。实施状态、审查结果、阻塞与恢复位置只写 [STEP §3](../steps-verified-v3.2-后台闭环修正版.md#3-step总览依赖与进度)。

来源：[PRD v3.2](../PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md)、[里程碑 M2](记忆存入与分路混合召回优化开发里程碑文档.md#m2技术定稿)、用户 S15 最新清理决定。基线 HEAD=`9c6f9855f5f2808a21c9e6bd761847198df2d516`；未读历史/迁移快照，未修改业务源码、env、数据库、容器或云 Collection。

## 1. 交付边界与唯一字段来源

| 技术产物 | 唯一负责内容 | 实施 STEP |
|---|---|---|
| 本文 | 源/索引物理锚点、远端顺序、当前凭据、使用保护、配置冻结、消费者/迁移清单 | 003～008、010～013、019、022 |
| [参数字典](STEP-002-参数字典与推演样例.md) | Q02～Q06 检索/预算/时限/恢复数值、计数器、限制、手算样例 | 003～005、009～013、020～021 |
| [提交身份与截止协议](STEP-002-提交身份与截止协议.md) | Q05 聊天/Future schema、双 GET、准入、唯一终态、轮询、Step8 副作用 | 014～016、019 |
| [后台接口与页面交接](STEP-002-后台接口与页面交接.md) | Q07 API/角色/页面、诊断/回填/配置发布 schema、持久回执与未知核实 | 003、007～008、014、017～019 |
| [S15 清理与保留设计](STEP-002-S15清理与保留设计.md) | 38 表、共享列、弱引用、语音数值、Redis/日志/进程、T0/完成标记与恢复 | 008、022 |

字段若在附录定稿，本文仅引用，不重复建立别名表。诊断/维护展示历史可按授权删除，当前身份、在途操作、未结案提交和清理完成标记不得被历史删除级联清掉。没有新增事实历史恢复功能。

**2026-10-09 USER_DECISION**：用户明确180秒是功能限制，不能因物理提交时刻证明阻止开发，整体流程到时未成功即失败。采用最终数据库事务内CAS作为业务裁决点：取得所有相关行锁后校验数据库UTC，并在最终UPDATE内再次校验原deadline；180秒后不能首次裁决成功。已成立但回执丢失只核实原裁决，实际落盘/回执可稍后，不再执行模型或续时。MySQL binlog取时早于真正提交的事实保留作设计依据，不再设为开发前置；不引入GTID/提交观察器。详细时序见提交协议。

## 2. 已核实运行事实与证据

| 分类 | 事实 | 使用边界 |
|---|---|---|
| M1 / RUNTIME | 同 cluster 新库 `local_test_collection`，1024/FLOAT/dotproduct；双独立 dense/sparse 查询；默认 partition 空、隔离测试 partition 共 607；L2 归一化可用 | 不把新库存在视为应用已切换；运行 env 仍旧 Cosine。完整证据复用 STEP §3.5 的 Gate-A 报告 |
| M1 / RUNTIME | 完整 upsert 会替换字段并清除省略的 sparse；局部 PUT 省略/空 sparse 不可靠地清除旧索引 | 新源写/索引写统一 full upsert，禁止靠空 sparse PATCH 清旧版本 |
| M2 / RUNTIME | 当前豆包 `doubao-seed-2-0-lite-260428` 官方 tokenization 合成三例返回 8/13/9；gte-rerank-v2 三条全量映射有效 | 模型证据（本地留存，未随本次提交；原引用：`evidence/STEP-002-model-probe-2026-10-09.json`）；没有业务正文；不是正式质量评测 |
| M2 / RUNTIME | 三个合成 single-user 请求的 `prompt_tokens-text_tokens=29`，测试显式关闭 thinking、输出上限 16 | 计数证据（本地留存，未随本次提交；原引用：`evidence/STEP-002-counter-probe-2026-10-09.json`）；不能据三例宣称所有请求的普适封装上界，未改线上请求形状 |
| M2 / READ_ONLY | 本地 MySQL 39 表含 alembic_version，38 ORM 表列一致；全 InnoDB、0 trigger；读取列/索引/外键/计数，不读取业务正文 | schema 观测（本地留存，未随本次提交；原引用：`evidence/STEP-002-schema-observation-2026-10-09.json`）、补充元数据（本地留存，未随本次提交；原引用：`evidence/STEP-002-extra-observation-2026-10-09.json`）；不是执行 T0 清理基线 |
| M2 / STATIC | 当前 generation 先 Redis 换代后 SQL 保存；源写缺持久 intent；配置发布先缓存后提交 | 附录引用实际函数；设计修复不能被当作当前已有能力 |

## 3. 数据模型（PLANNED，MySQL 8 / InnoDB）

### 3.1 共用类型与约束

`U64=BIGINT UNSIGNED`；`UUID=CHAR(36) CHARACTER SET ascii COLLATE ascii_bin`；摘要=`BINARY(32)` SHA-256；时间=`DATETIME(6)` UTC；状态=`VARCHAR(32) ascii_bin`，应用 enum 与 CHECK 双重验证。ID 字段非空，另标 `?` 才可 NULL。JSON 只含下列已定义载荷，禁止把 credentials、异常原文、完整 Prompt 复制进表。所有控制表含 `created_at/updated_at`，单调 `revision U64`；读取新鲜真相用主库，不用只读副本/Redis。

表内 `FK` 默认为 `RESTRICT`；不在删除诊断/维护历史时 cascade 到控制表。下面的 `UNIQUE`、索引、状态约束须进入 Alembic 迁移，不只写 ORM 注释。共享锁按 identity_id 升序获取，用户生命周期仲裁按可信 user_id 单行锁；禁止相反顺序循环等待。

| 表 | 字段（除通用列外） | 键/索引及不变量 |
|---|---|---|
| `memory_runtime_fence` | `environment_id VARCHAR(64) PK, target_epoch U64, target_fingerprint BINARY(32), mode VARCHAR(16), reset_run_id UUID?` | mode=`maintenance/active`；epoch 单调增加；仅一行环境真相。启用必须已有完成且匹配目标的 S15 run |
| `memory_identity` | `id U64 PK AUTO_INCREMENT, target_epoch U64, target_fingerprint BINARY(32), partition_name VARCHAR(64) ascii_bin, doc_id VARCHAR(64) ascii_bin, memory_type VARCHAR(32), owner_user_id BIGINT, generation U64, allocated_generation U64, body_hash BINARY(32)?, source_state VARCHAR(24), index_state VARCHAR(24), encoder_version VARCHAR(128)?, current_operation_id UUID?, inflight_operation_id UUID?` | UNIQUE(target_fingerprint,partition_name,doc_id)；INDEX(source_state,index_state,id)。owner=0 仅公开类型，私有两类必须实际 user>0；generation 单调且删除重建不归零；source_state=`unknown/live/deleted`；index_state=`not_ready/ready/repairing/manual/deleted` |
| `memory_operation` | `operation_id UUID PK, identity_id U64? FK, generation U64?, parent_operation_id UUID? FK, task_id UUID? FK, round_no INT UNSIGNED?, attempt INT UNSIGNED?, source_generation_key BINARY(32)?, operation_kind VARCHAR(24), owner_actor_type VARCHAR(16), owner_actor_id BIGINT, client_request_id UUID?, idempotency_hash BINARY(32)?, request_hash BINARY(32), target_epoch U64, source_result VARCHAR(24), index_result VARCHAR(24), dispatch_state VARCHAR(24), pending_payload JSON?, payload_hash BINARY(32)?, remote_tag UUID, worker_id UUID?, worker_epoch U64, lease_until DATETIME(6)?, dispatched_at DATETIME(6)?, reconcile_until DATETIME(6), terminal_at DATETIME(6)?` | UNIQUE(source_generation_key)；UNIQUE(task_id,round_no,attempt)；UNIQUE(parent_operation_id,identity_id)；UNIQUE(owner_actor_type,owner_actor_id,idempotency_hash)；INDEX(dispatch_state,lease_until)、INDEX(source_result,reconcile_until)。operation_kind=`create/update/delete/index/retry/baseline/batch`；identity/generation仅batch父项可NULL，其他项CHECK非空；source_generation_key仅源操作填hash(identity,generation)，index/retry/baseline/batch为NULL，允许同代不同encoder及多轮index尝试各有独立operation；source_result=`pending/confirmed/failed/unknown/superseded`；index_result=`pending/ready/failed/unknown/manual/not_required/superseded` |
| `memory_index_task` | `task_id UUID PK, identity_id U64 FK, operation_id UUID FK（固定原源或baseline操作，不改指向某次index尝试）, generation U64, encoder_version VARCHAR(128), body_hash BINARY(32), state VARCHAR(24), round_no INT UNSIGNED, attempt INT UNSIGNED, round_started_at DATETIME(6), round_deadline_at DATETIME(6), next_attempt_at DATETIME(6)?, worker_id UUID?, worker_epoch U64, lease_until DATETIME(6)?, error_code VARCHAR(64)?` | UNIQUE(identity_id,generation,encoder_version)；INDEX(state,next_attempt_at,task_id)；state=`pending/running/retry_wait/manual/completed/superseded`。重复手动重试返回同 task，并在锁内推进 round；运行中不可并行增轮 |
| `memory_use_claim` | `claim_id UUID PK, consumer_kind VARCHAR(24), execution_id UUID, target_epoch U64, owner_id UUID, state VARCHAR(24), created_deadline_at DATETIME(6), handoff_at DATETIME(6)?, closed_at DATETIME(6)?, error_code VARCHAR(64)?` | UNIQUE(consumer_kind,execution_id)；state=`reserved/dispatching/handed_off/aborted/unknown`；此表不保存正文，只保存最终使用授权。跨进程不自动接管 `dispatching/unknown` |
| `memory_use_item` | `claim_id UUID FK, identity_id U64 FK, generation U64, body_hash BINARY(32), route VARCHAR(4), ordinal INT UNSIGNED` | PK(claim_id,identity_id)，INDEX(identity_id,claim_id)。只列最终选择前缀，非整个候选库；写入阻塞检查仅未关闭 claim |
| `memory_reset_run` | `run_id UUID PK, environment_id VARCHAR(64), reset_key VARCHAR(16), manifest_hash BINARY(32), protocol_version VARCHAR(32), target_epoch U64, target_fingerprint BINARY(32), t0 DATETIME(6)?, phase VARCHAR(32), state VARCHAR(24), baseline_digest BINARY(32)?, completed_at DATETIME(6)?, opened_at DATETIME(6)?, operator_id BIGINT, last_error_code VARCHAR(64)?` | UNIQUE(environment_id,reset_key)，reset_key CHECK=`S15`；state=`planned/maintenance/running/unknown/failed/completed/opened`；完成记录永不自动清理；新 run 不得绕过一次性约束 |
| `memory_reset_item` | `run_id UUID FK, kind VARCHAR(16), resource_key VARCHAR(191) ascii_bin, state VARCHAR(24), fixed_scope JSON, cursor JSON?, before_count U64?, after_count U64?, preserve_digest_before BINARY(32)?, preserve_digest_after BINARY(32)?, result_digest BINARY(32)?, error_code VARCHAR(64)?` | PK(run_id,kind,resource_key)，kind=`phase/resource`；索引(state,run_id)；fixed_scope 只存表/列/ID 上界/容器目标，不存旧正文；批次进度与同库修改同事务 |

Admin批删父operation持有请求幂等锚点、唯一子项ID清单/分类计数；每个child独立operation_id及identity事务，父子在触网前同事务登记，父结果从各child持久结果聚合，不重发已确认child。child幂等键为空，原header只父项持有；单项源操作使用同一表。外部source_state等是内部结果的显式投影，映射见后台附录。Admin内部operation_id固定UUIDv4；带新增Header时保存原UUIDv7 client_request_id及hash。对外write_result.operation_id有Header返回该v7，否则返回内部v4；GET路径v7按可信actor+hash查并比原值，v4按内部PK+actor查，其他版本/非法格式422。这样POST全部回执丢失仍可用预存Header核实，跨管理员同Header不撞全局PK；不把此规则套聊天旧ID。pending_payload最大1MiB（含完整dense/fields），超限写前失败且不触网；摘要相等仍核对原身份避免哈希碰撞合并。

operation另有`receipt_summary JSON?`（≤256KiB、无记忆正文/向量/凭据）、`receipt_until DATETIME(6)?`、`tombstone_until DATETIME(6)?`；它们与终态即清的pending_payload严格分开。单项保存原接口成功字段和状态定位；batch在触网前保存去重后的稳定输入序号、requested_doc_id、child_operation_id或固定拒绝分类，非法/非user项无需伪造identity子项。每项状态演进持久更新摘要或从已绑定child重建，不能依赖进程内数组。终态后7天内保留完整摘要供丢回执复读，7～30天只留actor/客户端ID/hash/原请求digest及expired定位；未决不回收。S15清该摘要中旧doc_id/Key等语义文本，仅保留保护所需不透明child ID/分类计数，详清理附录；不能借本字段保存旧正文。

`memory_maintenance_event`、诊断、回填、配置发布表详见后台附录；`chat_*` 和 Future 字段详见提交附录。S15 额外加 `voice_call.cleared_run_id UUID?`，索引该列，FK reset_run RESTRICT；不改现有 voice 终态以伪装取消完成。

operation.dispatch_state固定为`prepared/claimed/dispatching/confirmed/unknown/not_sent/superseded`。prepared→claimed领取；claimed在尚未触网且可证明旧worker停止时可重新领取；一旦dispatching只可走confirmed、unknown或供应商明确拒绝后的not_sent，不允许租约把它倒退prepared。index的每个新attempt创建独立operation_id/tag并受原task+round+attempt计数；若上一attempt未知，不开启下一写attempt。源已确认时index操作的source_result只投影同代源confirmed，不用它重复推进generation。 每次index操作必须有task_id/round_no/attempt（attempt从1起）；UNIQUE(task_id,round_no,attempt)使同轮同次只生成一个持久tag。自动首轮round_no=0。手动新轮受理复用operation_kind=retry作为**本地回执**：同事务锁task、校验当前代/滚动次数、推进round_no并写actor+client_request_id/hash+request_hash→task/round，attempt=0、dispatch_state=confirmed、无远端调用/正文payload；受原7天详细/30天墓碑保障，重复同ID先读原轮，不因该轮已完成再开轮。运行中返回原task不创建新轮，**仍须同事务登记该请求的无正文no-op回执**：绑定当时task/round、attempt=NULL、receipt_summary.accepted_new_round=false；后续同ID即使原轮完成也只复读no-op，不能新开轮。对已授权且目标存在的确定拒绝同样登记固定结果；鉴权/非法形状/目标不存在等未受理请求不返回code0。普通index尝试不占人工请求幂等键。task/operation循环FK在建表后ALTER添加，运行时先来源operation→task→index/retry operation。可信legacy建立目录时用baseline本地操作：冻结完整来源manifest与归属/正文hash、隔离旁路writer后核对登记，不发送源写、不补造事实时间；该操作是task来源锚，不是旧库迁移。

### 3.2 稀疏和远端字段

远端保留现有 `id/content/type/user_id/key` 等业务字段；新增动态元数据：`mr_epoch:int`、`mr_generation:int`、`mr_body_sha256:string64`、`mr_operation_id:string36`、`mr_deleted:bool`、`mr_encoder_version:string128`。源正文仍 `key：value`，向量与稀疏只编码 value；可信 mem_* 自由正文用完整 content。所有字段按 M1 支持的动态字段能力验证；不预设未创建 Schema 字段可原地改类型。

DashVector 不提供本方案所需的按 generation 条件 upsert/CAS。因此 SQL 核代后发一次 HTTP 仍不足以阻止旧请求迟到覆盖；不能仅凭租约到期允许另一个请求写同 identity。下面的持久 dispatch fence 必须覆盖**源写、索引写、删除和重建**。

## 4. 源操作、派生索引与未知结果

### 4.1 写前锚点与严格单在途

1. 先检查维护 fence、可信归属、既有校验/查重/Stable Key。Admin 同 Idempotency-Key 先查原回执并比 canonical request_hash；不同请求内容冲突，不改原锚点。没有 key 也先生成并持久 operation_id，网络回执缺失不能自动重做。
2. 同一 SQL 事务锁 identity；检查未关闭 use_claim、inflight_operation_id。冲突有限等待 2 秒后返回明确 busy/待核实，不占新 generation、不宣布源成功。新合法源操作在同事务推进allocated_generation并取其值作为本次generation（包括失败代次也不复用）；current generation只在确认时切换，持久 pending_payload、remote_tag 和 identity.inflight，提交并读回后才触网。
3. dispatch_state=`prepared` 可安全领取，持久 worker_epoch、owner、lease；提交 `dispatching` 后才能发一个远端请求。`dispatching/unknown` 不因 TTL 自动变回 prepared。进程崩溃在“标记发送→真正发送”之间同样未知，宁可转人工，不用重发赌请求没有发生。
4. 源 upsert 为完整 dense+业务字段+元数据，不带 sparse，可靠清除旧 sparse。必须核实 HTTP 与业务 code、对应文档结果；禁止只看 2xx/少数关键词。远端明确 success 后同事务写 current_generation/hash/live、source_result=confirmed 和唯一 index_task，再清 inflight；delete确认则current source/index=deleted、index_result=not_required，不创建补正文任务。该事务回执未知先按 operation_id 读回。此处才可向用户确认“正文已保存，索引待修复”。
5. 远端 success 后本地提交失败：写前 operation 仍存在，identity 暂不确认；扫描 fetch 对比 remote_tag/generation/hash/归属，恢复同一确认事务。不用当前 query/fetch 自证当前有效性；当前资格来自 SQL 锚点，fetch 只核实已登记的本次 intent。
6. 明确未发送/供应商有确定原子拒绝语义时可记 failed。网络断开、超时、5xx/含混批量响应都记 source_unknown，保持 identity fence。matching remote_tag 可证该 upsert 已应用；旧值/不存在只代表当前观察，不能证明迟到请求永不执行，故不释放 fence。核实到期转 manual 并去重告警，同身份新变更暂不可用，其余身份继续。

源在途阶段最新变化未确认：新链排除该 identity 并标 `source_unverified`，避免远端被部分覆盖却继续用旧凭据。源已确认而 index pending/failed 时，dense 仍可用；只能将当前代的索引 ready 视为 BM25 完整。旧索引命中不能挪分给新正文。

### 4.2 索引任务与删除/重建

任务领取 `SELECT ... FOR UPDATE SKIP LOCKED`，复核 current_generation/hash/epoch/encoder_version 和 source_live，原子占 identity.inflight。**每次**远端提交前复核；无法安全取得 slot 就 retry_wait，不能把旧任务改成最新代继续写。索引 full upsert 带完整当前 dense/字段/新 sparse，使用本轮唯一 remote_tag。完成后同事务更新 task/index_state；丢回执沿同 intent 核实，未知不并行重发。

删除采用**逻辑删除 full upsert**作为可核实单次操作：同 doc_id，`mr_deleted=true`、正文/key 清空、归属保持、稀疏省略、dense 为固定单位向量 `[1,0,…,0]`、带新 generation/tag。该向量只是不可召回的墓碑；所有最新消费者/list/fetch 的活数据视图排除墓碑。新库全部新写都携mr_deleted；已核实legacy无该字段不能因新增metadata过滤被排除：SQL凭据+返回后墓碑过滤兼容，无依据不要求远端`mr_deleted=false`强过滤。墓碑可能占候选槽，记录过滤数量，不额外无限补查；后续安全物理回收只在完整隔离窗口。凭据可靠提交后删除成功；下次合法同 ID 创建 generation 再+1，完整覆盖墓碑。物理移除只在全 writer 隔离的 S15/目标退役窗口执行，不在普通重建竞争中执行无条件 delete。

这样 late-delete 不会在允许重建之后删掉新文档：旧 delete 未核清时重建不能取得 slot；确认其 tag 已应用后才解除单在途约束。索引旧任务同理。不能用“查到不存在”代替确认无迟到 delete，不能手工删 identity/operation 来强行解锁。业务删除后的检索/管理列表均不得显示墓碑；语音/普通 Agent 只适配存储活数据与 DotProduct，不因此获得新链使用保护。

故障恢复不会新增事实历史：pending_payload 仅为当前未决操作恢复所需，完成/取代即清 payload；当前 live 正文仍在唯一向量文档，控制表只留摘要和代次。pending 历史堆积到人工状态也不得自动清保护锚点。

### 4.3 有限执行与人工重试

自动每轮最多 3 次远端明确可重试的尝试，首次后 5/30 秒退避，最长 120 秒；核实超时和次数也计入该轮。remote_unknown 只读核实，不计作“可重新写一次”。维护并发全环境 4、同 identity 1；租约 15 秒/5 秒续期只是调度活性，不解除远端 fence。参数完整范围见参数字典。

人工 retry 只给同一有效 task 开新轮，旧预算/每次尝试仍保留；同身份最多 3 个人工轮/24 小时，超额返回限流及可重试时点，不无限计时。unknown 的人工按钮仍先核实，不跳过 unresolved dispatch；只有可证明从未发送/已完成或已隔离退役旧目标，才能恢复写资格。无需重跑 Step6/语音提取。删除展示历史不取消未决任务。

## 5. 候选、使用点与 Prompt DTO

### 5.1 冻结与可信候选

`EffectiveMemoryConfig` 不可变：`config_snapshot_id UUID`、三个配置精确版本/来源（DB version 或 env fingerprint）、target_epoch/fingerprint、embedding model+dimension+normalization、encoder版本/训练语料摘要、rerank profile、12 数量/4 门槛、全部预算/计数器、阶段/调用预算。凭据只在进程内引用 secret handle，不进入 DTO/日志/历史。一次请求先解析组合再冻结；缓存缺失读主库，库不可读不静默拿另一套默认；仅从未发布过该配置时才采用明确 env/default 来源。

`Candidate`：`route cg|cp|ck|user, identity_id, partition, doc_id, generation, body_hash, key?, value, memory_type, owner_user_id, source_channels[], dense_rank?, bm25_rank?, dense_score?, bm25_score?, rerank_score?, route_rank, order_method, admission_reason, trust_state, encoder_version?`。仅合并同路同 identity/同代同 hash；两通道代次不同只保留可信当前一方，旧 rank 不挪用。type/user_id 由后端可信上下文构造 filter；不接受 LLM 指定 owner，不用 CandidateKeys/category 作硬过滤。

查询顺序：独立 dense/sparse→批量 SQL 当前凭据核对→核对返回正文 hash/元数据→去重→完整 rerank 或路内融合→门槛→路内 final_top_k→完整条目模块预算→最终预算与使用检查。dense 阈值 `None`，不得 `0` 剔除负分。空/“无”跳路、missing/null 回退本次已知输入、空 BM25 不发空稀疏查询，按 PRD §7.1.1 presence-aware 处理。

DashVector具体协议沿M1实测：dense请求传L2后的真实query vector、不带sparse；BM25独立请求传1024维全零dense**协议占位**＋同版本`encode_queries(Keywords)` sparse，分别携本路topk/filter/include_fields。只传sparse而没有vector会被服务当过滤查询，HTTP/code0也不算词法成功。零dense占位仅允许此专用BM25适配器，不能绕过真实embedding非零验证。服务无词交集仍会返回score=0的填充项；这类记作`no_lexical_match`而不当BM25命中，不是可配置相关性门槛；dense负分仍保留。两路均按点积原分降序记录，不执行`1-score`的Cosine距离换算。

### 5.2 最终检查到模型输入交付的保护

仅最终选中 identities 参与使用保护，按 ID 升序锁行，检查 current_generation/hash/live/无 source_unknown、运行 epoch、原 deadline。失效项及该路后缀一并移除，不补位，重新渲染计数。该事务持久 `memory_use_claim + items`，把最终使用资格固定为 `reserved`；源确认/变更在分配新 generation 前检查 claim，不能跨过这个 reservation。

持有者将 claim CAS 为 `dispatching` 并复核原截止后，通过限定的模型适配器交付这份不可变输入；完成请求体交付即标 `handed_off`、释放保护，不等完整回复。已关闭 claim 的后续变更不撤回已合法交付的输入。诊断没有回复调用，在同一检查点将“最终可注入快照”交付诊断结果构造器后关闭。旧测试 mock 分支不得创建真实 claim。

**故障口径**：reserved 且可证明没有 dispatch 的记录可过期中止；dispatching 后进程/网络结果未知，转 unknown，不凭租约到期释放。所有可能继续交付的 owner 已退出且输入 socket 已关闭/请求体交付已确认，才允许关闭；无法证明则有界核实后人工，受影响 identity 的新变更返回待核实，不能宣布变更已生效。同步 task timeout 必须等待 send-task 取消收口；不允许后台 detached send 在 claim 释放后继续发送。SQL 锁本身不能解决断连后旧进程恢复；持久 reservation 才是不自动放行的凭据。

004/013 必须注入“检查后暂停→并发删除→恢复发送”“连接丢失→旧 owner 醒来”“交付完成回执丢失”三类故障；若适配器不能证明 handoff/停止则保持 unknown，而非删除保护记录。保护等待 2 秒、handoff 5 秒、核实 30 秒均属有限操作预算，不延长当前请求 180 秒。

### 5.3 结构化结果与兼容

`PromptBuildResult={prompt:str, config_snapshot_id, counter:{id,model,rendered_tokens,envelope_reserve,total_charge}, selected:[Candidate+rendered_text+module_ordinal], removed:[identity,route,reason,stage], route_counts, module_charges, over_budget:bool, use_claim_id?}`；`selected` 只含最终正文和路内前缀，不把初选清单当实际注入。removed reasons 固定：`ownership/unverified/stale/deleted/threshold/final_limit/module_budget/total_budget/invalidated_suffix`。

旧 `prompt_mgmt.test_prompt` 调专门后端函数 `build_legacy_mock_prompt(...) -> str`，保留 current/draft/系统 override；内部只消费固定 mock candidates，不碰真实索引，不创建聊天/诊断历史。普通聊天、Step8 和新诊断不接收前端 mock flag；旧 Agent helper 保留现有返回类型。013/019 分别验证三个消费者，不以旧字符串测试通过代替真实候选保护。

## 6. 配置、模型、消费者及部署交接

| 来源/模块 | 目标行为 | 实施与验证 |
|---|---|---|
| `vector_retrieval_config` | 8 候选数、4 最终数、4 rerank 门槛；旧统一 top_k/threshold 不再被新链读取 | 003 配置合并/范围校验；019 两处旧控件展示停用说明 |
| `prompt_token_config` | 保持原模块布局和裁剪优先级；固定 nickname=50 不可编辑；完整昵称实际计数 | 003 白名单保存/回读；013 两个昵称边界 |
| `vector_db_config` / `third_party:dashvector` | 同一 canonical head，原两个入口保留原角色；目标必须新库/1024/dotproduct/FLOAT，source env 不新增 | 003 DB 后缓存、精确 publish_id；019 旧 alias 适配 |
| `third_party:embedding` / env | 继续 text-embedding-v4/1024；文档/query/缓存命中统一 L2，拒绝零/错维/非有限 | 003/006/019；不沿用旧 emb:MD5 缓存当已归一化证据 |
| BM25 profile | DashText 0.0.7、zh analyzer 配置/字典/统计文件摘要固定；只在版本明确变更时重建 | 004/008；M1已证明load/dump精度差异须固定统计，禁止每请求重fit |
| rerank profile | `gte-rerank-v2`、阿里云杭州 DashScope 实测路径；具体限制/分值/降级见参数字典 | 011 正常全量映射、错误/超限整路 fallback；020/021质量校准 |
| `dashvector_client`、`vector_service`、`vector_memory_write_service`、`user_vector_memory_service`、`character_knowledge_service`、后台 CRUD | 统一 target/normalization、full upsert、墓碑视图、intent/索引状态；保留各入口验证/权限/同 Key 身份 | 004～007、019 |
| `multi_vector_retrieval_service`、`query_rewrite_service`、`prompt_builder`、`routers/chat`、`open_chat_service`、`step8_subchain` | 新四路链/45+45/冻结版本/使用保护/唯一终态 | 009～016 |
| `realtime_voice_recall_service` 直接 HTTP、语音会前 memory 读取、语音 memory writer/trace | 同新目标；L2 后 dotproduct score 原语义适配；列表与过滤排墓碑；writer仍原20秒包装、源已保存不等索引完整 | 006、019；不升级语音召回算法或延长原读超时 |
| 普通 Agent / Future / 星云记忆列表与管理读侧 | 新库与活数据视图、分数方向；仅 Step8 新文字子链用新检索；普通 Agent 不纳入新使用保护 | 015、019，运行全部现用消费者回归 |
| `admin_config_service` / 发布清理 | head锁内先提交版本与publish锚点，再失效缓存；旧版本清理不删活跃冻结/未决提交依赖 | 003/019；详后台附录 |

缓存键新命名：`emb:v2:{provider_profile_hash}:{model}:{dimension}:l2-v1:{sha256(value)}`，TTL=7天；值仍检验 shape/finiteness/norm 后使用；provider hash 不含密钥明文，凭据更换不必改语义 hash，model/endpoint/normalization 改动必须换命名空间。BM25 cache 如使用，键含 encoder_version+body_hash；不跨统计版本复用。

旧 Cosine 名仅保留为退役清单和审计记录，不做可选运行回退；不新增 migration_source_* env。实际 `.env` 单目标、配置库/alias/cache/容器进程同步切换发生在 022，不能 M2 悄悄改 env 使旧代码连新库。若环境存在更后配置版本，先核其准确目标和版本，不以最后列表项推断本次发布成功。

Alembic 交接：004 建 identity/operation/index_task/use_claim/item；003 建 config_head/publish；008 建 backfill/reset/fence 并完成 S15 工具依赖字段（voice cleared marker）；014 建 chat 身份/代际表及消息归属；015 加 Future slot/version/effect；017 建诊断/展示历史。006～019 实现各消费点后由 022停写切换；创建 fence 表的实际依赖应与004一并建立运行读取所需行，008补reset对象及可空关联，不让004依赖未来008。上述是原 STEP 内迁移拆分，不新增/重排 STEP。

## 7. 故障推演与交接验收

| 故障输入 | 可观察持久证据与唯一允许动作 | 禁止结果 | 实施 |
|---|---|---|---|
| 写前SQL不可用 | 无intent就不触网，沿原失败信封 | 远端已写而无恢复身份 | 004/007 |
| 源成功、SQL登记失败 | intent/tag存在；只核实本次源并补同一确认事务 | 报完整成功、重提取/重写新代 | 004/005 |
| BM25超时/未知 | index intent保留inflight；只读核tag，超限manual | lease到期后重发旧正文覆盖新代 | 005 |
| 删除与索引repair竞争 | identity单在途、generation单调；落后任务superseded | 旧repair复活删除正文 | 004/007 |
| 删除后同ID重建 | 墓碑操作已核清才允许新generation | 旧无条件delete清新内容 | 004/008 |
| 同ID两通道正文不一致 | SQL current hash决定唯一可信来源，保留该来源原rank | 把旧通道高分挪给新正文 | 010 |
| 使用检查后删除到达 | claim先取得则删除等待/明确busy；变更先确认则候选移除 | 已确认删除仍首次注入 | 013 |
| use owner断连迟醒 | dispatch_unknown持久保护；证明停止后才解锁 | TTL到期后任意新写成功且旧send继续 | 004/013 |
| 任一路rerank缺/重复/非法index | 本路整体RRF，score=NULL；其他路正常 | 半个有效列表冒充完整正常排序 | 011 |
| 新用户保存失败/准入unknown | 见提交协议，user/额度/gen同事务，先读同ID | 原代先作废、重复额度/多user行 | 014 |
| 1～4 pending进程崩溃 | 持久dispatch索引、启动/5秒扫描、原deadline | 等第5条才恢复、同代加180秒 | 014/016 |
| Step8兜底/正常commit未知 | 同一consume唯一提交仲裁，未知先核实，成功副作用原集合 | bool失败后重复落消息或清新Future | 015 |
| 诊断结果保存失败 | run先持久，有限核实→manual/unknown，页面不重跑 | 假装无历史成功、业务写入 | 017/018 |
| 配置commit响应丢失且别人发布V+1 | 本publish_id映射到原committed_version或unknown | 拿active V+1当本次成功 | 003/019 |
| S15部分清理/完成标记unknown | 维护态、精确资源断点/保留摘要、读回后续跑 | 重清T0后新数据、旧库回切 | 008/022 |

原十个 RV31 子用例逐一交接：AC12-a→003/013昵称与预算；AC29-a→014/016提交身份与核实；AC29-b→016有限同步；AC34-a→014原子准入/1～4恢复；AC27-a、AC34-b→015两出口提交与收尾；AC33-a→013/019旧mock字符串；AC18-a→006语音writer；AC18-b→019语音writer到新BM25；AC30-a→004/005/007持久锚点和未知恢复。后台12个子用例由后台附录逐项映射，不能因设计完成将整体AC或业务STEP标DONE。

本轮设计静态验证与合成模型调用可以证明字段/参数/协议有审阅产物；不能证明尚未实现的故障注入已经通过。后续每个实施 STEP 必须按该表运行真实事务/并发和接口测试。最终二审与静态证据回传到唯一STEP §3；未实现的事务/接口不提前标为运行通过。
