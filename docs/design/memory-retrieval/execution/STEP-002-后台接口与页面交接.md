# STEP-002 后台接口与页面交接

状态：**PLANNED，技术交接设计；未实现、未上线、未签发 GATE-B**。日期：2026-10-09。主入口：[技术方案与参数定稿](STEP-002-技术方案与参数定稿.md)。需求依据：[PRD](../PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md) §6.3.3、§6.7、§6.8.1～6.8.9；执行依据：[STEP-002](../steps-verified-v3.2-后台闭环修正版.md#step-002-行为接口与参数定稿) 任务7～10。本附录仅定后台协议，不重定聊天物理仲裁或 S15 清理矩阵。

## 1. 已核实的运行代码边界

| 当前事实 | 源码依据 | 设计影响 |
|---|---|---|
| 新诊断、维护、回填查询、自有源写回执尚无路由 | `backend/routers/admin/*.py` 静态 AST：213 条路由，无三个新前缀 | 下文新增接口全部 PLANNED；不以设计替代017/018/019运行验收 |
| Admin JSON 信封为 code/data/message；业务通常HTTP200；鉴权401/403，校验422 | `backend/schemas/common.py:11`；`backend/utils/admin_auth.py:93` | 新业务错误不改成吞掉结构的HTTP409；前端仍须处理非信封异常 |
| 策略配置原读S/A/V、写S/A；向量库配置亦同；第三方原读S/T/V、写S/T | `vector_config.py:23`、`memory_mgmt.py:49`、`system_monitor.py:35` | 两入口保留，不合并角色，不撤A的原向量库权限 |
| 用户管理/对话读S/O/V；user/private API读S/A/O/V、写S/A/O | `users.py:44,500`；`user-detail.html:554` | A可局部记忆API，不因此开放完整用户管理 |
| 旧策略 top_k/threshold 被四路旧检索消费，另有固定最终Top3 | `multi_vector_retrieval_service.py:34,96,165` | 新链不得留下隐性Top3，也不得复制旧3/0.7充新参数 |
| 第二个TopK仅在vector_db_config配置/测连路由读写，未找到业务消费 | `memory_mgmt.py:165,197,305`；backend精确键搜索 | 此控件标历史停用，不误称语音/Agent在消费它 |
| 语音直接HTTP topk=20；普通Agent走vector_service参数 | `realtime_voice_context_source_service.py:19`；`vector_service.py:59` | 同目标/归一化适配交019；不顺带升级范围外读算法 |
| 公共DashVector及两Embedding客户端仍从env getter取值 | `dashvector_client.py:75,109,176,212,239,283`；`embedding_client.py:45`；`embedding_service.py:11` | 后台旧键不是现成的统一运行来源，003须真实接线 |
| 配置先读旧值再整包发布，Redis写入先于依赖收尾commit | `vector_config.py:176,242`；`admin_config_service.py:195–235`；`database.py:37` | 新发布事务与精确回执必须实现，不能冒称已有并发保证 |
| 旧Prompt测试消费str、mock可无真实身份 | `prompt_mgmt.py:82,125,639–713`；`prompt_builder.py:412` | 结构化构建必须有专用字符串兼容包装 |

路径无冲突：原catch-all仅在`/character-knowledge/{doc_id:path}`与两类用户记忆路径内。新增三个独立前缀以及`/configs/publications/{publish_id}`不与其重叠；新增路由仍须在实现测试中核对注册顺序，禁止根级`/{id:path}`。Admin真实权限始终由数据库实时角色、会话版本和逐路由Depends决定，sessionStorage角色仅用于显示。

## 2. 每页字段、API与角色

简称：S=super_admin，A=ai_trainer，O=ops_admin，T=tech_ops，V=observer。表中API均以`/api/admin`开头；未标新增者沿用既有路径/Body，响应字段增量兼容。

| 页面/区域与字段 | API/动作 | 权限 | 交接 |
|---|---|---|---|
| user-detail历史对话：原日期/消息/分页＋五项状态投影 | GET `/users/{user_id}/conversations` | S/O/V读 | 014投影，019页面 |
| vector-token-config混合召回：四路dense/BM25/final共12整数，正常rerank门槛/模型范围，effective版本/来源；旧TopK/threshold只读 | GET/PUT `/configs/vector_retrieval_config` | S/A读写，V读 | 003 |
| 同页Token：原九模块/max_total；nickname50只读说明；加载/保存/回读状态 | GET/PUT `/configs/prompt_token_config` | S/A读写，V读 | 003 |
| memory-rules向量库：Endpoint、新Collection、凭据状态、旧top_k历史标识、测试结果 | GET/PUT `/vector-db-config`；POST `/vector-db-config/test-connection` | S/A读写测，V非敏感读 | 003/019 |
| third-party：实际provider/model/Endpoint/凭据状态/version；本地BM25版本/就绪；实际rerank卡 | GET `/third-party/status`；PUT `/third-party/{service_name}/config`；POST同前缀`/test-connection` | S/T读写测，V非敏感读 | 003 |
| knowledge原Modal：type/key/value、索引徽标、逐次回执；编辑不改Key | GET/POST `/character-knowledge`；PUT/DELETE `/character-knowledge/{doc_id:path}` | S/A读写，V读 | 004/007 |
| user-detail user/private原Modal/行：key/value、当前代次状态、结果区 | GET/POST `/users/{user_id}/user-memories`或`/private-settings`；PUT/DELETE各`/{doc_id:path}` | API S/A/O读写、V读；完整页面仍S/O/V | 004/007 |
| memory-rules全局user：keyword/user_id、分页/truncated、逐项删除结果 | GET `/memories/global`；DELETE `/memories/batch-delete` | S/A读写，V读 | 007；不增全局创建/编辑或private |
| 上述写结果区：operation_id/源与索引状态/revision/核实时点/task关联 | **新增** GET `/memory-write-operations/{operation_id}` | 本管理员＋来源读权限＋type/user范围 | 007，不依赖017 |
| memory-diagnostics：user_id/source/input；输入范围；运行/保存分态；筛选/详情/重跑 | **新增** POST/GET `/memory-diagnostics`；GET/DELETE `/memory-diagnostics/{execution_id}` | S/A执行删读，V只读；O/T无新增 | 017/018 |
| memory-index-maintenance任务Tab：身份/归属/来源/操作/源索引分态/任务状态/尝试/计划/允许动作 | **新增** GET `/memory-index-maintenance/tasks`、`/tasks/{task_id}`；POST `/tasks/{task_id}/retry` | S/A修复读，V读 | 017/018 |
| 同页回填Tab：run范围/版本/阶段/水位/游标摘要/截止点/分类计数/缺口/完整性 | **新增** GET `/memory-index-maintenance/backfills`、`/backfills/{run_id}`、`/backfills/{run_id}/items` | S/A/V读 | 008生产→017查询→018页面→019集成 |
| 维护历史：完成展示记录及关联占位 | **新增** DELETE `/memory-index-maintenance/history/{record_id}` | S/A；V/O/T不可 | 仅纯展示历史，不删保护状态 |
| 保存结果核实：publish_id、提交状态/原提交版本/观察时点 | **新增** GET `/configs/publications/{publish_id}` | 本管理员＋原配置入口读权限 | 003，不能凭最新版本猜结果 |
| Step1.5/3/8预览：同源模板/新规则/default与effective区别 | GET `/chat-prompt-view/step15`、`/step3`、`/step8` | S/A/V读 | 009/013/019，零模型 |
| prompt旧测试：原输入/mock/use_draft与原输出 | POST `/prompt/test` | S/A执行；V不可 | 013/019，旧mock字符串兼容 |

诊断详情分五块：①用户/输入/source/时间；②实际冻结配置组合与上下文来源；③四路Question/Keywords、渠道/doc_id/正文快照/原名次原分/可空rerank/排序/排除原因；④同次模块初选与最终选入/Token/两次裁剪原因；⑤阶段耗时/调用/费用可用信息/执行与保存状态。正常无命中、无可编码词、渠道故障不能统一伪装0条。没有费用统计显示未提供，不声称免费。

新页导航按PRD“AI对话配置”域紧邻召回与Token，旧菜单/高亮保留，不复活已移除一级记忆规则；`admin-api.js:344,406,462,660`的MENU_CONFIG、分组生成、observer菜单及直访校验同步。现代码召回与Token仍为一级项，018应以同域相邻新入口实现既定目标，不能静默搬动其他菜单。写控件用data-write-action，动态节点同样受observer策略；GET搜索/分页/详情/刷新保持可用。文本/Key/错误/确认框安全转义，不改存储正文；URL只含标识和筛选。

## 3. 公共协议、有限参数与错误

新GET分页统一`data={total,page,page_size,list}`，page默认1且>=1，page_size默认20且1～100；元素有id，语义ID可并列。diagnostic按created_at DESC,id DESC；task按updated_at DESC,id DESC；backfill按started_at DESC,id DESC；items按稳定序号ASC,id ASC。筛选严格枚举，时间沿parse_admin_date_range。翻页不作为全量证明。

诊断详情候选、任务尝试和回填items也必须分页。详情支持`section=candidates|attempts`及page/page_size/route筛选，返回该页与total；非适用section拒绝，不能一次返回全部快照规避分页。查询序号防旧用户/筛选/页迟到覆盖；加载失败不是空结果。可保留同筛选旧快照并标更新失败，换用户必须清除上一用户正文。

本附录新诊断/发布/手动重试身份及**本期新增的Admin源CRUD可选Idempotency-Key**合法值采用UUIDv7规范小写36字符；这是新增Header能力的格式约束，不适用于聊天已有client_message_id/client_resend_id/OpenAPI标识。原CRUD不带Header仍合法；带非法新Header返回422且不写入，不把任意字符串当已支持旧协议。可信actor取会话。所有run_id为CHAR(36) ASCII；内部BIGINT主键对JSON输出十进制字符串，避免JS精度损失。请求指纹由服务端规范化method/route/可信actor/目标/body生成；涉及凭据用服务端HMAC且不输出。原公开Body不增必填operation_id；不开放任意Header注入。下文物理时间统一UTC DATETIME(6)，SHA/digest统一BINARY(32)。

| 参数 | 定值/范围 | 语义 |
|---|---|---|
| 诊断用户级/admin级/环境并发 | 1 / 1 / 2，固定工程初值 | 共享持久占位，重复同ID先复读，不另占名额；无无限队列 |
| 诊断总执行期限 | 120000ms | 从受理绝对时点算；不是聊天新授权窗口；Step1.5/2各45000ms且取剩余时间较早者 |
| 持久化/只读核实余量 | 30000ms | 执行120s后仅收口/核实；不得再次调模型或续执行 |
| 单次状态GET等待 | 5000ms | DB不可读返回不可用，不伪造状态 |
| 前端状态观察间隔 | 初始2000ms，×1.5，上限5000ms | 绝对观察截止为受理+150000ms；离页/登出停止GET，不停止或重启执行 |
| 源写未知自动观察窗 | 60000ms | 仅前端观察，结束转人工核实，不把unknown转failed |
| 请求首次受理窗/未来时钟偏差 | 120000ms / 30000ms | 已存在ID先复读；过窗缺记录禁止重新受理。客户端依据已鉴权响应server_time校时 |
| 源写详细回执保障 | 604800s，终态起7天 | 仅终态可清详细结果；未完成/未知/一致性引用绝不回收 |
| 最小身份digest墓碑 | 2592000s，终态起30天 | 7～30天只返回过期摘要，不自动重放；30天后旧UUID时间过窗仍拒首次受理 |
| 新列表默认/最大page_size | 20 / 100 | 含详情大清单；旧接口既有分页不强行重写 |

诊断输入复用对应业务适配器：main/openapi为单次输入，1～2000字符（`schemas/chat.py:9`、`schemas/open_chat.py:8`）；若主方案适配已聚合包，必须沿原尾4000改写/完整Step5输入的差异，不另设页面截断。step8输入作为future_action，1～200字符，与现持久字段`models/relationship.py:40`边界一致，不读取/消费真实Future。空白输入拒绝，正文不靠parseInt/隐式截断改变。其余模型限制/数量/维护次数和调用退避消费主方案Q02～Q06，不由后台另造隐性参数。

当前`backend/constants/__init__.py`Admin码最高20078；静态核对20120～20129未占用。下列为本期预留PLANNED码，实施前再核对；原源写确定失败优先沿原各模块错误码。

| 码/拟常量后缀 | HTTP/用途 | 结果语义 |
|---|---|---|
| 20120 MEMORY_ADMIN_INVALID | 200，业务字段/筛选/状态非法 | 可修正输入；结构类型错误仍422 |
| 20121 MEMORY_REQUEST_CONFLICT | 200，同身份异目标/内容 | 不执行第二次，不覆盖旧回执 |
| 20122 MEMORY_OUTCOME_UNVERIFIED | 200，提交/发布/删除结果未知 | data携已有定位和受控状态；不是确定失败 |
| 20123 MEMORY_RECEIPT_EXPIRED | 200，回执保障期外或过窗首次请求 | 不重放、不冒称失败；人工核实 |
| 20124 MEMORY_CONCURRENCY_LIMIT | 200，诊断并发已满 | 未受理付费执行，重复既有ID先返回原执行 |
| 20125 MEMORY_RECORD_UNAVAILABLE | 200，记录不存在/已清理/不可核实 | 明确可证明的原因；不推断源删除或提交失败 |
| 20126 MEMORY_ACTION_NOT_ALLOWED | 200，活动/人工/保护引用不可删或不可重试 | 返回can_retry/can_delete与受控原因，状态不变 |
| 20127 MEMORY_REVISION_CONFLICT | 200，expected_revision过期/旧任务被替代 | 返回有权读取的最新定位，不执行旧代 |
| 20128 MEMORY_SOURCE_UNVERIFIED | 200，源当前性/删除状态未知 | 只核实，不重跑提取或强制补写 |
| 20129 MEMORY_PERSISTENCE_UNAVAILABLE | 200，可捕获的状态依赖不可读/受理无法持久化 | 不伪造empty/success；未受理时不启动外部调用 |

权限失败仍HTTP401/403；错误正文只受控原因，不返回供应商原异常/Prompt/密钥。已有third-party非法service/body为HTTP400、保存测连失败code5001（system_monitor.py:392～417）；003触及时映射并兼容UI，不假称旧接口已统一2xxxx。GET成功读取failed/unknown记录仍code0；code0仅表示读取或受理成功，不代表源写/诊断执行成功。

## 4. Admin源写、自有回执与批删

`memory_operation`仅消费主方案唯一Schema：内部operation_id固定UUIDv4主键、owner_actor_type/owner_actor_id为可信归属、client_request_id UUIDv7可空、idempotency_hash/request_hash、identity_id/generation、source_result/index_result/dispatch_state、单调revision及终态/过期时间；不另建id BIGINT或平行admin回执registry。maintenance_task_id由对应`memory_index_task.task_id`（UUID）关联投影。Admin Header按actor域去重；对外write_result.operation_id有Header时返回原v7，否则返回内部v4，维护详情可另列internal_operation_id。GET路径v7按当前actor+hash(clientID)定位并核对client_request_id原值，v4按内部PK+当前actor定位；非法UUID/其他版本422。这样POST响应全丢仍能用已保存v7核实，跨管理员相同v7互不冲突；非Admin写沿主方案writer身份，不扩大管理员权限。

请求Body保持原状；受控客户端显式提交前生成operation_id，经`adminRequest(...,{idempotencyKey})`精确映射Idempotency-Key。服务端在任何远端源写前提交可恢复意图；登记不成功不发送。pending载荷按主方案完成后清除，详细回执不另存正文。源unknown保留必要恢复载荷，不能按7天强删。

同ID同规范化请求仅返回原结果；同ID异目标/内容20121；不同ID同内容是合法新显式操作，不做内容去重。无ID旧调用保持原Body/响应，每次是独立请求，可建单次内部写前锚点；不造跨请求永久去重或承诺丢失全部回执后的精确核实。旧调用拿到服务端operation_id后可以核实，丢失则能力有限。

自有GET先校验本人、当前来源读权限及可信type/user范围，不能让传入user_id改权限。O可看原user/private写摘要，但不可跳全局维护；A拥有局部记忆API不开放users目录。无权记录不泄露目标正文。若缺记录、依赖不可读或接收窗口尚可能晚到，结果待核实，不能宣称失败；只有持久未受理/失败证明可如此标记。

| 字段/状态 | 值 | 行为 |
|---|---|---|
| source_state | succeeded/failed/unknown/pending | 源成功保持原code0及原data，增量data.write_result；明确失败原非0；未知20122携定位 |
| index_state | ready/pending/failed/unknown/not_executed | 独立于源状态；删除操作ready表示删除后目标索引状态已达成，不表示源存在 |
| receipt状态 | full/expired/tombstone/unavailable | 7天完整、其后到30天最小身份digest；保护状态不回收；expired不能重发 |
| 索引任务链接 | task_id/operation_id | 仅有新维护读权限者显示；无权限者仍见必要源/索引摘要 |

内部→API显式映射：source_result.confirmed→source_state.succeeded，pending/failed/unknown同名；source superseded仅用于已证明未应用的取消旧操作→failed/reason=operation_superseded，已确认成功的历史操作保留confirmed而仅currentness变旧，不能倒改失败。index_result.ready→ready，pending/failed/unknown同名，manual→unknown且maintenance_state=manual_required；delete的source_result=confirmed且index_result=not_required时→ready（目标删除状态已可靠达成），其余not_required/superseded→not_executed。历史已完成索引不因后续新代自动改写原操作结果。当前identity/index状态与原操作回执分栏，不能把ready墓碑当live源。

源成功而索引待修复/失败/未知，Modal关闭或退出编辑，显示“记忆已保存，BM25索引待修复”。源删除成功且失效保护可靠时同理收口，不因索引失败恢复正文。源未知/pending保留输入供查看、禁本次重复保存、允许关闭并GET核实；仅在当前管理员session保存ID与来源定位，登出清除，不保存正文/密钥。成功回执后列表刷新失败仍是成功待刷新。旧回执只描述旧操作，当前行以当前identity/generation为准，不能用旧删除回执移除新代。

批删仍doc_ids 1～100条、仅user、按唯一doc_id执行与计数；非法/非user单列拒绝，单删仍复用batch。复用memory_operation的operation_kind=batch父项，仅父项identity_id/generation允许NULL；Header/v7仅父项持有，父与child内部operation_id均各自UUIDv4、parent_operation_id指父内部v4，UNIQUE(parent_operation_id,identity_id)，单项沿原identity事务。父项持久固定唯一输入清单及无合法identity项的受控拒绝摘要；合法子项在各自触网前登记，不另建registry。保留deleted_count/failed_doc_ids，并增items与source_counts；deleted_count只计确认源删除，failed_doc_ids兼容收纳未确认项，新UI按failed/unknown/pending区别显示。断言：succeeded+failed+unknown+pending=唯一输入数；index待修复是独立维度，不加进总数。整包丢响应复读各子项，不重删已成功项，不用新ID重放整包。

成功与未知样例（原data字段仍保留）：
```json
{"code":0,"data":{"doc_id":"user_7_example","write_result":{"operation_id":"<uuidv7>","source_state":"succeeded","index_state":"pending","generation":3,"result_revision":2,"maintenance_task_id":"<task-uuid>","reason":"index_repair_pending","observed_at":"2026-10-09T06:00:00Z"}},"message":"success"}
```
```json
{"code":20122,"data":{"write_result":{"operation_id":"<uuidv7>","source_state":"unknown","index_state":"not_executed","result_revision":1,"reason":"source_commit_unconfirmed","observed_at":"2026-10-09T06:00:00Z"}},"message":"结果待核实"}
```

## 5. 真实诊断受理、运行与历史保存

POST body：`request_id,user_id,source,input,parent_execution_id?`；source仅main/openapi/step8，前二者rewrite source=main。parent仅显式重跑关联且须有读取权限，不加载旧快照当新输入。先按请求唯一身份复读/冲突判断，再在同一受保护事务核对user/admin/environment并发占位；受理成功才外部调用。并发实体必须共享持久计数或可串行锁的占位，不只用单进程Semaphore。

`memory_diagnostic_run`：id/execution_id、admin_id、request_id、request_digest（UNIQUE admin+request）、user_id/source/input/parent_id、execution_state/history_state、revision、accepted/start/end/deadline/persist_deadline、frozen_versions、context_source_metadata、stage/call/token摘要、snapshot_available、controlled_reason。大候选快照按route稳定序号保存并支持分页；实现可用同run受控JSON投影，但不能将全量直接返回浏览器。

| 执行状态 | 保存状态 | 页面/恢复 |
|---|---|---|
| accepted/running | pending | 只读观察，不重启/删历史；120s绝对执行期限不随刷新续期 |
| completed/degraded/failed/budget_blocked | saved | 展示真实结果及永久快照，终态可按删除规则手删 |
| 有持久执行终态证据 | failed | 运行结果与“历史保存失败”分别展示，不伪造快照 |
| interrupted/manual_required | failed/unknown | 进程中断或提交结果无法确认；有限核实后人工处理，不伪成功或无限running |
| 任一未知/状态依赖不可读 | unknown/读取不可用 | 不确认执行终态，不允许删除/重跑同ID；恢复后核对原锚点 |

受理基础行先commit，之后执行真实只读上下文装载与检索。只复用读取和输入组装，不调用send/Step1写入口；不写消息、额度、generation、关系/最近互动、情绪、Future、主动计数，不调用回复模型或Step6。外部调用有费用，诊断只允许自身记录/必要审计写入。

阶段结果和快照保存分事务收口：先确认执行状态证据，再保存存在的结果/快照；保存失败基础行仍可查。若DB在执行末尾不可写，不能凭丢失内存结果补造completed；恢复扫描依据lease/deadline及持久阶段证据转interrupted/manual_required。超过120s不再启动新调用，随后30s仅持久化/只读核实；DB持续不可用时前端在150s停止自动观察并提示待人工核实，服务端恢复后补记manual_required，不能要求每次GET承担状态写入。

请求同ID同输入重复POST返回同execution；刷新/回页GET按ID查；`GET /memory-diagnostics?request_id=...`仅精确查询当前发起管理员。显式重跑新ID、新有效上下文/配置，保留parent关联。GET列表/详情、筛选、分页不调模型。无当前源证据只标“历史快照”，不能猜源已删。

DELETE仅终态且执行/保存结果均已确认；删除诊断历史与附属文本快照原子收口，不删当前源/向量，不取消执行，不回填历史正文。删除未知返回20122并GET核实，不自动再执行；必要最小身份digest墓碑保留至30天且不含正文，过期首次UUID拒绝受理。原不可删除审计仅留脱敏摘要。诊断及完成维护展示历史永久保留、不设自动到期；S15一次性清理例外沿主方案，不在本附录重新扩张。

受理/保存失败样例：
```json
{"code":0,"data":{"id":"<run-uuid>","execution_id":"<run-uuid>","request_id":"<uuidv7>","execution_state":"accepted","history_state":"pending","revision":1,"snapshot_available":false,"status_url":"/api/admin/memory-diagnostics/<run-uuid>","deadline_at":"2026-10-09T06:02:00Z"},"message":"success"}
```
```json
{"code":0,"data":{"id":"<run-uuid>","execution_state":"completed","history_state":"failed","revision":5,"snapshot_available":false,"reason":"history_persist_failed","can_delete":true},"message":"success"}
```
第二例必须已有持久执行完成证据，且保存失败已确认、无活动保护引用；否则不得给completed/can_delete=true。

## 6. 索引维护与回填 DTO

`memory_index_task`承载当前identity/generation/operation、task_revision、maintenance_state、尝试次数、next_attempt_at、Q06有限预算/deadline、superseded关系；`memory_maintenance_event`承载尝试/展示历史、record_kind、task/run关联、受控原因和时间。显示历史可删，当前保护凭据在`memory_identity`及活动task/operation中，不因删历史丢失。

| 维护投影 | 允许动作 | 服务端条件 |
|---|---|---|
| pending/retry_wait | 看详情；符合条件可retry | 当前源可信，互斥领取同一有效任务 |
| running | 只读刷新 | 重复retry返回当前任务，不增加调用或重置预算 |
| manual_required | 原因/有限手动retry | 可修复且当前正文可信；新有限尝试预算沿Q06 |
| completed | 看历史；符合条件才删 | 无活动/恢复/一致性引用，不删当前有效性凭据 |
| superseded | 旧任务只读，定位最新 | 旧代不可重放或删除新代 |
| source_unverified | 只读核实 | 不以读失败当删除，不强制成功/补写，不重抽取LLM |

POST `/tasks/{task_id}/retry` body=`{request_id,expected_revision}`；同请求身份规范化绑定task/revision。检查权限→请求复读→当前identity/代次→受保护revision条件领取。重复同次返回同task；版本过期20127，附可读latest_task_id/revision；源未知20128；不可修复20126。7天详细回执/30天墓碑沿§3，未完成不清；不能新建无限预算或整轮抽取。

GET列表字段：id/task_id、type/user_id/doc_id或可靠源身份、source、operation、source_state/index_state/maintenance_state、generation/currentness、attempt_count、updated_at/next_attempt_at、manual_reason、can_retry/can_delete及reason。详情补分页attempts、operation_id/run_id、superseded_by；source_round/call_id确实存在才展示。正文按原权限返回，不把score当情绪或事实可信度。

DELETE `/history/{record_id}`只处理`memory_maintenance_event`的全局ID，record_kind明确task/backfill；已完成且无保护引用才删除纯展示投影。manual_required/unknown/运行批次不可删。回填汇总若仍需逐项对账也不可删；批次列表/详情必须消费对应展示删除标记，已清理摘要不从run再次拼出展示副本，关联显示占位，不以404推断源消失。核心恢复/对账凭据只有主方案允许解除保护后才可处理，不因隐藏历史丢失。

| memory_backfill_run DTO | 类型/含义 |
|---|---|
| id/run_id、mode、source_scope | 字符串ID；isolated/actual；目标/partition/可信目录范围，不含凭据 |
| index_version/encoder_version、started_at/ended_at/updated_at | 实际冻结版本和ISO UTC时间；未结束ended_at=null |
| execution_state、stage | pending/running/interrupted/manual_required/completed；scan/index/reconcile/catchup |
| baseline/high_water/checkpoint_summary/cutoff | 可信启动基线、固定范围上界、安全断点摘要、明确对账截止点；未知为null |
| scanned_records/unique_source_ids/attempt_count | 非负整数，三者独立，不互当总量 |
| source_class_counts | standard_kv/legacy_free_text/empty/identity_or_parse_error分别计数 |
| reconcile_counts/unresolved_count/report_complete | missing/extra/mismatch/unknown/retry_wait等分类；未解决数；只有证据齐才能true |
| total_known/total_source_ids | bool及可空整数；总量未知显示“已扫描N，总量未确定” |

`memory_backfill_item` DTO：id/run_id/稳定item_seq、source_identity/type/user_id、source_class、content_digest/current_generation、index_result/reconcile_state、task_id可空、observed_at、受控reason；分页筛选class/state，不返回凭据或无权限全文。source identity唯一计数由008生产，不由页面拼接cap列表。

完成公式：**可信遍历终点成立 ∧ 身份+正文对账成立 ∧ 增量追平至明确cutoff ∧ unresolved_count=0**。exit0/count相等/已处理数不能替代成功。无可信总数不能画100%；结果暂不可读显示进度不可用。中断保留持久进度；同批次续跑保留run_id和checkpoint，新批次新ID不覆盖旧结果。完成只证明当时cutoff，不承诺之后全库健康。

008产生run/item及恢复/对账证据；017可以先按本DTO夹具开发，AC11-a及017最终DONE仍须008实证；018页面、019真实记录集成。页面没有启动/暂停/取消/强制完成/全量重试按钮，不让008反向依赖017/018。

## 7. 配置唯一来源、发布回执与表单

### 7.1 唯一消费映射（PLANNED）

| 字段域 | 权威发布键/唯一消费 | 原可编辑入口及角色 | 测连/版本/消费者 |
|---|---|---|---|
| 新12数量/正常rerank门槛 | vector_retrieval_config经统一有效解析器 | configs路径S/A；V读 | 同次冻结版本；新文字/OpenAPI/Step8/诊断，不自动升级Agent/语音算法 |
| 九模块/max_total，nickname固定50 | prompt_token_config；nickname不入PATCH | configs路径S/A；V读 | 同解析器供业务/诊断；默认与effective分别标 |
| DashVector Endpoint/collection/credential | vector_db_config为canonical；新Collection固定目标；env逐字段显式回退 | 原vector-db-config S/A；third-party/dashvector S/T为同head别名入口 | 两入口均投影同canonical版本；collection映射collection_name；不保留两个独立生效凭据；全部search/write/直接HTTP/脚本消费同resolver |
| Embedding Endpoint/model/credential | third_party:embedding；env显式回退 | 原third-party S/T；V非敏感读 | 两embedding客户端/诊断/测连同来源；模型维度/归一化和缓存版本含入冻结组合 |
| rerank provider/Endpoint/model/credential | third_party:rerank，实际型号/地域沿主方案Q04 | third-party新增实际卡S/T；V读 | _VALID_SERVICES、后端状态、SERVICE_KEY_MAP同时扩展；未接统计显示暂无数据 |
| BM25能力/就绪/版本 | 本地DashText+新Collection：encoder/字典/统计/语料/索引版本 | 原配置页只读能力信息 | 不虚构远端Endpoint/Key，变更索引版本仍受008/022约束 |
| 两处旧TopK | vector_retrieval top_k/threshold、vector_db.top_k仅历史审计投影 | 原页面折叠只读 | 不进新PATCH，不复制进新12项，不提供旧Collection回切 |

别名入口不合并角色：A仍不能访问third-party；T仍不能访问策略/记忆管理；同一底层字段通过各自原入口授权。旧third_party:dashvector记录保留历史审计，不作为另一套独立运行配置。原Agent参数及语音固定20仍单独明确适用范围，019只完成同目标/归一化/score兼容。

一请求开始在一致快照中解析并冻结检索/预算/provider/model/新Collection/encoder/index/归一化/cache版本组合，中途发布只影响后续请求，不能结束时读最新版冒充实际版本。embedding_service当前`emb:md5(text)`缺模型版本（:25～28），新namespace至少含provider/model/dimension/text_type/归一化版本+文本摘要；旧缓存不能作为新模型证明。

### 7.2 发布事务与精确核实

`memory_config_head`每config_key唯一且可锁，含active_admin_config_id/version/revision；不存在active时也有确定的可串行起点。`memory_config_publish`含publish_id UUID、admin_id、来源入口、canonical_key、规范化request_digest、commit_state、committed_version/committed_at、observed_at、受控reason、7天receipt与30天tombstone期限；唯一actor+publish_id。同发布身份异payload明确冲突。

受保护事务取得最新head/有效值→只合并提交字段→完整校验→写admin_config新版本/head/publish回执/脱敏审计→确认DB commit。不能锁外merge后整包覆盖；同字段按受保护实际提交顺序，未提交字段必须保留。不能借admin_config保留20版本替代精确发布回执，历史修剪不得破坏保障期内证据。

DB确认后发布版本化缓存；缓存写失败不回滚已确认成功、不返回未保存。resolver以权威head定位版本键，禁止“缓存失效失败仍读旧active_config”半生效；不能在commit之前写新有效缓存。commit未知用独立只读连接按publish_id查原提交证据，证据不足保持unknown；后人更高版本、当前值相同、epoch重置均不能证明本次成功。

GET `/configs/publications/{publish_id}`只本人且仍具来源读权限；响应`{publish_id,canonical_key,commit_state:pending|committed|rejected|unknown|expired,committed_version?,observed_at,reason}`；内部accepted/validating投影pending。committed_version为本次版本，可并列current_active_version但不替代。发布未知20122、依赖不可读20129、保障期外20123；不由GET重发发布或写审计。UI PUT提交通过Idempotency-Key带publish_id，旧无ID调用兼容但丢回执精确核实能力有限。

表单状态：loading/load_failed/clean/dirty/submitting/saved_refresh_pending/submission_unverified/error，每Tab独立。加载成功才建立快照/允许保存；失败不用旧默认伪装。仅合法变化字段PUT、无变化不请求、提交禁重复。精确有限整数校验，不parseInt吞小数、空值转0；正常门槛只在对应模型范围作用，降级不套用。nickname50不可写且不作为正文硬截断；模块预算上限之和大于max_total本身不拒绝合法配置。

保存成功但GET失败显示已保存待刷新，不再次PUT；提交未知按publish_id查，不能凭更后版本猜失败。所有保存/测连/运行同resolver：未保存表单仅本次测试，字段修改令旧测试失效；服务端校验最终同组配置，不信前端testPassed/need_test_first。HTTP200不等于业务能力通过，修旧1536维随机测连和只判HTTP状态的问题。Key空保留、掩码拒写；observer仅credential_configured，不给片段/hash；正常/失败/审计/诊断均无明文凭据。

## 8. 历史对话投影与Prompt兼容

历史查询保留原日期/分页/排序/total/message_source+id（users.py:270～392）。先选原消息页，再批量关联每条一份当前权威投影，不一对多join增气泡或total。仅user增字段：processing_state可空pending/success/failed/superseded/unverified；status_reason受控；state_origin=lifecycle/legacy/unavailable（lifecycle对应PRD“current”来源语义，与聊天附录统一wire名称）；state_revision为权威BIGINT的十进制字符串或null；status_observed_at为核实时点。

| 证据 | 展示/限制 |
|---|---|
| 当前合法执行未终态 | 等待回复；断线不判失败 |
| 成功事务确认且回复定位存在 | 回复已保存；不代表设备收到/已读；传输失败不覆盖成功 |
| 已确认deadline/budget/其他失败 | 超时失败或回复失败/受控原因；不称记忆保存失败 |
| 旧代被有效新代承接 | 显示当前新代；无承接且已确认superseded才显示被替代 |
| deadline已过未确认、commit未知、依赖不可读 | 结果待核实/核实不可用，不装作无限正常运行或确定失败 |
| 已确认仅旧协议历史 | 原delivery_status文案＋历史状态；缺字段不默认legacy/success，不伪造revision0 |

沿现有手动查询，不新增自动后台轮询；GET不标已读/扣额/换代/调模型/清Future/重启任务。前端query_sequence和复合身份+revision去重，跨用户旧响应丢弃；状态读取失败不把已知成功改失败。物理仲裁消费主方案，Admin不拿用户JWT冒充鉴权。

新构建返回结构化PromptBuildResult：prompt（仅运行时）、候选/实际选入身份、模块/最终Token、两次裁剪与有效性淘汰、冻结版本。诊断读取同次构建结果，不解析字符串猜ID或另算选择。旧`test_prompt`专用adapter只取`.prompt`给旧模型/len计算，保持full_prompt/ai_reply/persona_match/content_safety/token_estimate及use_draft/system override语义。

受控mock来源仅后端已鉴权旧测试路径构造，不是公开body参数；mock可只有content/score，不补造真实doc_id/代次、不访问真实索引验证模拟ID。旧测试不得新增Step1.5/2/索引读写/聊天入队/Step6；新诊断仍不得回复模型；普通Agent旧helper保持。

预览`chat_prompt_view_service.py:47–150`继续同源占位模板；Step3保留module_order/trim_priority/token_limit_default，代码默认不改名有效配置，effective须同resolver+版本；Step8保留future_action模板、不改Agent P0～P4。预览零模型/真实用户历史加载，无编辑发布。

## 9. 实施及故障验收交接

| 用例 | 必须断言 | 责任 |
|---|---|---|
| 同ID同输入/异输入、不同ID同输入、无ID旧客户端 | 同次仅一次外部调用；异内容冲突；显式新操作不误去重；无ID能力边界如实 | 004/007/017 |
| 源成功索引失败、未知、回执丢失/7天后/30天后迟到 | 源成功正常收口；未知只读核实；过期不重放；未完成不回收 | 004/007 |
| batch重复ID/非法项/2成功1失败1未知 | 分类总数=unique输入；索引待修复不重复计数，整包不重删成功项 | 007 |
| A改字段1、B改字段2；本次commit未知后他人更高版本 | 未提交字段不丢；publish_id证明原提交；新版本/epoch不当证明 | 003/019 |
| user/admin/environment同时并发与相同请求重入 | 上限1/1/2共享成立，同ID不另占/不重复付费，角色不可绕过 | 017 |
| 运行成功保存失败、保存commit未知、进程退出/DB持续不可用 | 运行/保存分态、无快照不伪造；150s观察停止，恢复manual_required不重新调模型 | 017/018 |
| 源删后看历史；删运行/人工/保护记录；删除回执未知 | 快照永久、无恢复源；保护状态不可删；未知GET核实、不借删取消 | 017/018 |
| 同doc_id重建后旧写/删回执；任务revision过期 | 旧回执不覆盖新代、旧task不执行；给最新可读定位 | 004/007/017 |
| 回填真实断点/中断/未知总量/缺失多余不一致 | DTO生产到页面同口径，无假100%；完成公式全满足才完成 | 008→017→018→019 |
| 五角色直访/动态写控件/GET筛选/篡改owner-user-ID | A无第三方/用户目录扩权，O仅自有局部回执，T无诊断，V只读，后端强制 | 003/007/014/017/018/019 |
| 主/草稿/override旧Prompt测试，仅content/score mock | 模型桩实收str，原响应不变；真实链无法开mock旁路；诊断回复调用0 | 013/019 |
| 预览、历史查询、分页失败及晚到响应 | 无模型/业务副作用；错误与空态分开；用户切换不露旧正文 | 014/018/019 |

现有可扩展测试：`tests/test_admin_vector_token_config.py`、`test_admin_character_knowledge.py`、`test_step034_observer_memory_vector_knowledge_pages.py`、`test_prompt_builder.py`、`test_chat_prompt_view.py`。拟新增`tests/test_memory_admin_operations.py`、`test_memory_diagnostics_admin.py`、`test_memory_index_maintenance_admin.py`及两新页面浏览器用例。002仅审查协议/样例/有限参数与故障时序；接口、页面和真实记录的运行验收由相应STEP完成，不提前结算父AC或业务上线。

## 10. 本附录负责的唯一物理Schema定义（PLANNED）

本节是`memory_config_head/publish`、`memory_diagnostic_run`、`memory_backfill_run/item`、`memory_maintenance_event`唯一Schema来源；主方案只建表目录链接。identity/operation/index_task/use_claim/reset/runtime_fence定义由主方案负责，§4/6中的相关字段只是后台消费要求，不另建第二份DDL。未注明NULL的列NOT NULL；所有时间UTC DATETIME(6)，UUID CHAR(36) CHARACTER SET ascii COLLATE ascii_bin，SHA/HMAC BINARY(32)。枚举采用VARCHAR+CHECK及服务层校验，不把未识别状态当成功。

### 10.1 memory_config_head 与 memory_config_publish

| 表/字段 | 类型/默认/约束 | 用途 |
|---|---|---|
| head.config_key | VARCHAR(100) PK | canonical key，仅受控配置白名单；别名映射不多建head |
| head.active_admin_config_id | INT NULL，逻辑关联admin_config.id | 无发布时NULL；不删除被head引用的版本 |
| head.active_version/revision | BIGINT，默认0，>=0 | 版本与并发序号单调，首次发布后>0 |
| head.updated_at | DATETIME(6) | 最新已确认发布时点 |
| publish.id/publish_id | BIGINT PK/UUID；UNIQUE(admin_id,publish_id) | 精确本次发布身份，UUID包含首受理时间范围 |
| publish.admin_id | INT | 可信会话管理员，不级联删除回执 |
| publish.source_entry/canonical_key | VARCHAR(64)/VARCHAR(100) | 原授权入口及实际key，key索引；不能由客户端任意越权指定 |
| publish.request_digest/validated_digest | BINARY(32)/BINARY(32) NULL | 请求和最终测试组指纹；包含凭据的HMAC不出接口 |
| publish.expected_head_revision | BIGINT NULL | 测试组所属基线；提交时变动须重合并/验证 |
| publish.commit_state | VARCHAR(16)，accepted/validating/committed/rejected/unknown | 受理不等于发布；公开读取accepted/validating按pending展示 |
| publish.committed_admin_config_id/committed_version | INT NULL/BIGINT NULL | 仅committed有值，同事务写入；保留审计版本ID即使旧配置后来修剪 |
| publish.created_at/observed_at | DATETIME(6) | 起点/最后持久核实时点 |
| publish.committed_at/terminal_at/receipt_until/tombstone_until | DATETIME(6) NULL | 终态7天详细、30天墓碑；unknown不回收 |
| publish.reason/record_revision | VARCHAR(64) NULL/BIGINT默认1 | 受控原因/结果演进；无原始供应商异常 |
| publish.lease_owner/lease_version/lease_until | UUID NULL/BIGINT默认0/DATETIME(6) NULL | 验证过程单领取，迟到持有者不能提交；不靠过期自动重发测连 |

publish_id按可信admin_id隔离；查询始终带当前管理员，不允许复读另一人的相同ID。head必须在受保护事务内按key取得/首次安全创建并锁定。publish受理行在外部测连前持久化；数据库结果未知只核实同ID，不能重复付费验证。受理行不存凭据或全量原配置，进程退出丢失未提交临时Key时转unknown/manual reason并人工重新显式提交，不自动恢复秘密载荷。

验证获得最终组validated_digest后，提交事务锁head，以最新值合并原PATCH并纯函数校验；如并发修改使待发布组不同，旧测试不复用：在原请求有限窗口内最多重新验证一次，仍冲突则20127且不发布。提交head、新admin_config、publish committed、脱敏审计原子；commit回执未知重新读publish。lease过期恢复者仅核实已提交证据，不能把head变化或新epoch当成功。缓存更新不承担提交证明。

### 10.2 memory_diagnostic_run

| 字段 | 类型/默认/约束 | 用途 |
|---|---|---|
| run_id | UUID PK | 对外execution_id/id别名；不另建自增execution ID |
| admin_id/user_id/environment_id | INT/INT NULL/VARCHAR(64) | 可信发起者/目标用户/部署环境；活动与保留历史user_id必填，仅已删墓碑可清；环境不由body决定；索引(user_id,created_at,run_id) |
| request_id/request_digest | UUID/BINARY(32)，UNIQUE(admin_id,request_id) | 付费执行去重；同ID异输入冲突 |
| source/parent_run_id | VARCHAR(8) NULL，main/openapi/step8；UUID NULL | source仅已删墓碑可清；parent逻辑引用，手删历史不级联删除子执行 |
| input_text | TEXT NULL | 原输入；仅按手动删历史清除，非自动TTL |
| execution_state/history_state | VARCHAR(24)/VARCHAR(16) | §5枚举；history加deleted仅用于已删快照墓碑 |
| result_revision | BIGINT默认1，>=1 | 同run单调结果修订 |
| created_at/observed_at/deadline_at/persist_deadline_at | DATETIME(6) | 受理/核实/120s执行绝对截止/150s核实截止 |
| started_at/finished_at/terminal_at | DATETIME(6) NULL | 未取得证据不得补造finished/terminal |
| stage/controlled_reason | VARCHAR(32)/VARCHAR(64) NULL | 最后持久阶段与受控错误，不留原异常正文 |
| frozen_versions/context_sources | JSON NULL/JSON NULL | 无凭据的实际配置组合、输入来源/时点；不是完整聊天上下文 |
| candidate_snapshots/selection_result/metrics | JSON NULL/JSON NULL/JSON NULL | 本次输入输出快照及结构化结果，不含完整Prompt/回复；内部数组上界由已冻结候选数量限制 |
| snapshot_available | BOOLEAN默认false | 仅真实持久快照完成后true |
| lease_owner/lease_version/lease_until | UUID NULL/BIGINT默认0/DATETIME(6) NULL | 执行领取fencing；stage写回须owner/version有效且未越过阶段授权 |
| deleted_at/tombstone_until | DATETIME(6) NULL | 手删清input、全部结果/上下文/配置快照JSON和可清身份详情，留run/request/actor/digest及删除过期定位；永久历史不自动设deleted_at |

受理共享锁复用主方案`memory_runtime_fence`的本环境行：新短事务先锁fence并确认允许诊断，再以当前读核对accepted/running及未停止占位的run，原子插入；不能用鉴权会话此前的一致性旧快照计数。更新/结束在相同串行占位协议中释放；相同request先返回原run。按user=1/admin=1/environment=2，不因不同来源另开额度。

执行lease建议15000ms、心跳5000ms；续租不得越deadline_at。过期不能接管重跑外部模型，仅核实持久阶段并在确认旧本地执行已停止/无新调用授权后转interrupted/manual_required、释放本地执行占位；未确认占位关闭不得为绕并发先标完成。供应商请求结果未知不宣称远端已结束，也不自动重试。持久化恢复单独在persist_deadline内核实，之后人工；GET永远不领取、不续租、不写状态。

### 10.3 memory_backfill_run 与 memory_backfill_item

| 表/字段 | 类型/默认/约束 | 用途 |
|---|---|---|
| run.run_id | UUID PK | 全部批次/续跑稳定身份 |
| run.mode/execution_state/stage | VARCHAR(16)/VARCHAR(24)/VARCHAR(16) | §6枚举；actual不表示已获当前执行授权 |
| run.source_scope/frozen_versions | JSON/JSON | 目标/partition/目录范围及实际索引编码版本，无凭据 |
| run.scope_digest | BINARY(32) | 绑定范围/基线，恢复时不得偷偷换范围 |
| run.baseline/high_water/checkpoint_summary/cutoff | JSON/JSON NULL/JSON NULL/JSON NULL | 主方案可信目录终点与安全游标；未知不能填0冒充 |
| run.scanned_records/unique_source_ids/attempt_count | BIGINT默认0，>=0 | 互不等价，008负责原子累计/幂等更新 |
| run.total_known/total_source_ids | BOOLEAN默认false/BIGINT NULL | 未知总量不画百分百 |
| run.source_class_counts/reconcile_counts | JSON/JSON | 各固定分类的非负整数，不合并源状态与索引状态 |
| run.unresolved_count/report_complete | BIGINT默认0/BOOLEAN默认false | 完成公式全成立才true，尚未扫描不是无缺口证明 |
| run.created_at/updated_at/started_at/ended_at | DATETIME(6)/DATETIME(6)/DATETIME(6) NULL/DATETIME(6) NULL | 时间证据，不用exit0代替 |
| run.lease_owner/lease_version/lease_until/revision | UUID NULL/BIGINT默认0/DATETIME(6) NULL/BIGINT默认1 | 008执行器互斥领取/恢复，API只读 |
| item.id/run_id/item_seq | BIGINT PK/UUID/BIGINT；UNIQUE(run_id,item_seq) | 每run稳定分页与检查点；run_id索引 |
| item.identity_id/identity_key/identity_digest | BIGINT UNSIGNED NULL/JSON/BINARY(32)；UNIQUE(run_id,identity_digest) | identity_id逻辑关联主目录同型U64；异常身份仍保留原目标/partition/doc_id定位；摘要碰撞须原键核对，不静默合并 |
| item.source_class/current_generation/content_digest | VARCHAR(32)/BIGINT UNSIGNED NULL/BINARY(32) NULL | 四类源分组及已核实代次/正文摘要，空/未知区别 |
| item.index_result/reconcile_state/task_id | VARCHAR(24)/VARCHAR(24)/UUID NULL | §6分类，任务可空；不补造关联 |
| item.attempt_count/revision/observed_at/reason | BIGINT默认0/BIGINT默认1/DATETIME(6)/VARCHAR(64) NULL | 幂等对账更新，受控原因 |

run的保护进度不能由展示历史DELETE删除；展示摘要经maintenance_event清理时，活动/对账引用使can_delete=false。008领取在原scope_digest/checkpoint/目录代次校验后条件增加lease_version，同run续跑；旧持有者更新必须匹配lease。失败/未知项不推进完成游标，恢复仍沿主方案有限预算，不由017生成或重启运行。lease具体时限消费Q06执行器参数，本附录不扩大运行预算。

### 10.4 memory_maintenance_event

| 字段 | 类型/默认/约束 | 用途 |
|---|---|---|
| id/event_id | BIGINT PK/UUID UNIQUE | 对外record_id为id字符串；event_id供写入幂等 |
| record_kind/task_id/run_id/operation_id | VARCHAR(16) task/backfill；UUID NULL/UUID NULL/UUID NULL | 展示来源关联；CHECK至少task或run一项，实际存在才返回 |
| identity_id/generation | BIGINT UNSIGNED NULL/BIGINT UNSIGNED NULL | 与主目录U64同型的历史代次定位，不承担当前有效性保护 |
| event_type/source_state/index_state/maintenance_state | VARCHAR(32)/VARCHAR(16) NULL/VARCHAR(24) NULL/VARCHAR(24) NULL | 可用状态投影，不替代task当前状态 |
| attempt_number/started_at/ended_at/created_at | INT NULL/DATETIME(6) NULL/DATETIME(6) NULL/DATETIME(6) | 每次尝试与排序；索引(task_id,created_at,id)、(run_id,created_at,id) |
| controlled_reason/details | VARCHAR(64) NULL/JSON NULL | 受控摘要/分类计数，禁止凭据/完整Prompt/复制诊断全文 |
| display_deleted_at | DATETIME(6) NULL | 手动删除时details/受控文本一并清空，不能仅隐藏全文仍留存 |

事件不被worker领取，无执行lease；写事件用event_id幂等。DELETE事务先锁事件及关联task/run的当前保护状态，核实已完成且无活动/恢复/一致性引用，再清展示载荷/标记删除并写既有脱敏操作审计。查不到引用不能默认可删；依赖不可读20129。核心身份/任务/操作不能依赖纯展示event才能恢复，否则该event必须保持不可删直到引用解除；GET返回占位不推断源删除。
