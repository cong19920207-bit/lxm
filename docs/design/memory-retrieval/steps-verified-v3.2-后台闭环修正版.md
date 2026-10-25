---

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。

title: "记忆存入与分路混合召回优化 v3.2 STEP 后台闭环修正版"
version: "v3.2"
status: revised
authority: true
authority_scope: STEP_PLAN
mode: document-review-repair
implementation_status: "见§3唯一执行记录"
progress_updated: "2026-10-15"
review_status: STATIC_REVIEWED_WITH_GATES
stage_result: PASS_WITH_RISKS
handoff_state: DOC_REVISED_WITH_GATES
updated: "2026-10-09"
source_step_sha256: "9aeb49ca4d7c778c1a929d395f38c5bd021cd0d52f77657733ffca7f96da9fd5"
source_prd_sha256: "a31209d8f151a8f5a6aa9e31998f7c90f22495cb328b6811f06189f2ade9dd1a"
companion_prd: "PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md"
companion_prd_sha256: "a31209d8f151a8f5a6aa9e31998f7c90f22495cb328b6811f06189f2ade9dd1a"
review_commit: "9c6f9855f5f2808a21c9e6bd761847198df2d516"
review_commit_scope: "原后台闭环稿登记2026-10-08经GitHub读取main并定向复读后台代码；本轮核对本地同提交及关键源码并做静态检查，无新增GitHub或RUNTIME证据"
delivery_scope: "文档修复与静态自检；未实施代码或生产操作"
---
# 记忆优化 v3.2 · STEP 后台闭环完整修正版

本文件以完整STEP v3.1为历史基础，配套 [PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md](PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md)。原RV31六类修正及10个子用例保留；原后台闭环稿依据其登记的main代码把ADM32-01～07写入002/003/004/007/008/009/013/014/017/018/019/022的任务与验收，新增12个原AC子用例。本轮继承最新用户取舍并修正局部交接/边界验收，见§1.4及§7.4；执行方不需要再将聊天中的问题手工拼入。

保留全部 **22个STEP、15F、35根AC、26RQ、13CSTR**。增加的是后台联动的实现责任和017对008的**验收收口前置**；其开发前置不变，008不反向依赖管理页面。其余原依赖保留，编号顺序不代替依赖。

**以下保留2026-10-08文档修订时点**：当时0/22、M1核验中；当前执行状态唯一见§3。当时按S15更新清理/保留范围并静态审核，未运行新业务/浏览器/数据库测试或实际清理；既有新库隔离证据保留，原后台稿的GitHub读取与旧审计只作历史来源。

## 1. 来源摘要与事实边界

- 当前配套 PRD：`PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md`，P01 / `PRD`；SHA-256：`a31209d8f151a8f5a6aa9e31998f7c90f22495cb328b6811f06189f2ade9dd1a`。本文所有 P01 条款定位以该完整修正版为准，不再指向未经修订的 v3。
- 原后台稿输入完整性登记（历史）：完整PRD v3.1 SHA-256 `e99fc15cd52f62bc4aab021735e93bb03c44056ae3e9532e564f1b14a4d2631e`；完整STEP v3.1 SHA-256 `9aeb49ca4d7c778c1a929d395f38c5bd021cd0d52f77657733ffca7f96da9fd5`。原稿登记两份已完整读取并重算，原件未覆盖；本轮不重读或重算历史文件。原v3及旧STEP来源继续保留于历史记录。
- 修订依据：原后台补齐授权、P01 §6.8与A32登记的代码证据，以及§1.4最新用户取舍和本轮局部修复授权；RV31原六项及包装层补充保持，不将原报告的纯函数复现算作本轮运行结果。
- 代码来源：原后台稿登记的GitHub main为 `9c6f9855f5f2808a21c9e6bd761847198df2d516`；本轮核对本地HEAD为同一提交并定向复核关键源码/当前契约，未新增GitHub或线上读取。A32表保留原登记定位，其他全链证据沿原基线；未重读旧93项全部来源，实施前核对后续提交差异。
- 默认文档入口为docs/INDEX.md与docs/llm-manifest.json，本轮已读取AGENTS、索引及manifest默认读取边界；本配套文件是用户显式授权的目标文档。当前设计入口由本轮文档整理同步，实际运行current契约及实施后的必要导航更新仍由022负责。
- 不扫描迁移基线、契约历史/草案、语音 P1 历史或技术债归档；本次文档同步不调用线上、不运行模型/功能/性能或生产操作；既有001新库隔离RUNTIME证据见§3.5，不冒充应用端到端或实际清理验证。
- 来源标签继续区分 `USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`、`PLANNED`、`UNVERIFIED`。已有业务值 **180 秒、45+45、最多重试一次、nickname固定预算配置值50** 与尚需技术定稿的数值分开；昵称保留正文不裁剪并完整计入总量，50不是实际文本的硬上限。拟新增接口是目标协议，不是已有运行接口；其物理 schema/错误映射/部署参数由 STEP-002 定稿。

### 1.1 评审基线差异与本次修复责任

- 文字Step6和Admin仍直接写DashVector，语音才经共享writer；只改共享writer会漏入口（B05/B07/B09/B10）。当前Stable doc_id为类型、Key哈希及归属后缀，不照抄技术债中的旧示例（B14）。
- B04的upsert/delete/fetch现状无法可靠区分所有业务失败/未知/明确不存在；query+topk及展示身份过滤不是完整遍历。STEP-001/004/008分别承担基础设施证明、操作契约和真实回填。
- B16热配置Redis发布发生在请求DB commit前，通用只保留20版本；B04/B20实际业务取环境getter，后台保存/测连来源另在B13/B18。新能力同源消费与保护由STEP-003落实。
- 现有B23等待120秒只等进程内Future，B24恢复锁90秒且缺持有者安全释放；不存在已核实的整轮deadline/持久互斥终态。不能只调常量；由STEP-002/014定稿并验收。
- U08发送幂等标识但B22/B23尚未消费，H5连接错误直接本地标失败，现有时间线主要追加行。不能声称已有完整幂等/状态重同步；提交未知核实和去重由STEP-014/016落实。
- 既有B31 Prompt测试是mock且调用回复模型；新诊断另建，只读装载、同次实际选入由STEP-017落实。B12用户详情允许ops_admin的局部权限，不可推广到四路诊断。
- RV31-R01：B17 的可编辑字段集合排除固定 `user_nickname`，校验却仍要求它出现；原报告已复现合法预算更新失败。STEP-003 必须修正白名单一致性并加入正向保存断言，不开放固定字段编辑。
- RV31-R02/R03：提交身份必须进入服务端持久关联；核实请求与既有历史分页分开。STEP-002 定稿，014 实现，016 覆盖回页仍 pending 到终态的有限持续同步；不得按文字/时间猜测身份。
- RV31-R04：B27 的 `_fallback_write_agent_message` 是独立写事务，正常分支又存在提交后收尾。STEP-015 覆盖两个成功出口、未知提交、成功后收尾超时及新 Future 防误清，不只改正常保存位置。
- RV31-R05/R06：B31 的旧 Prompt Test 是共享构建器的显式消费者，STEP-013/019 保留 mock 与字符串契约；语音局部写入交由006，新文字链的跨入口 BM25 验收交由019。
- PRD Q02–Q07和GATE-A–D仍是明确依赖：不阻断本次文档复审，会阻断相关开发定稿/正式质量判定/生产切换；费用、日常延迟和提升幅度的数字目标按§1.4排除，不因缺这些数字阻断。若真实核验要求改变既有产品边界，只确认受影响选择，保留其他决定。

### 1.2 证据目录

各 source_id 沿用原 STEP 的证据标识，不冒充 manifest 注册 ID。P01 是同目录交付的当前 v3.2 PRD；其他 `existing` 表示在原评审快照中存在的仓库相对路径，行号绑定该快照，不是本次重新核验最新源码的声明。执行前核对路径/符号漂移；新增接口、测试及物理字段标 `planned`。原稿记录的本地绝对目录不再作为可移植交付的路径前提。

| source_id | 路径（existing） | locator | 来源 |
|---|---|---|---|
| E01 | `docs/INDEX.md` | L1（默认文档入口与边界） | `REPO_BASELINE` |
| E02 | `docs/llm-manifest.json` | L1（当前权威文档白名单） | `REPO_BASELINE` |
| P01 | `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | §6–§9、§11–§13；S10/§9.7固定180秒；以稳定条款定位 | `PRD` |
| C01 | `docs/contract/current/memory-knowledge/api.md` | L1（当前接口与最后写入来源） | `CONTRACT` |
| C02 | `docs/contract/current/memory-knowledge/admin-ui.md` | L1（当前后台页面） | `CONTRACT` |
| C03 | `docs/contract/current/memory-knowledge/data.md` | L1（旧 memory 表保留、主写入已下线） | `CONTRACT` |
| C04 | `docs/contract/current/_shared/conventions.md` | L1（响应、分页及错误码约定） | `CONTRACT` |
| C05 | `docs/contract/current/_shared/auth-rbac.md` | L1（observer 与后端角色边界） | `CONTRACT` |
| C06 | `docs/contract/current/chat-emotion/api.md` | L1（文字消息与 SSE） | `CONTRACT` |
| C07 | `docs/contract/current/chat-emotion/data.md` | L1（消息状态及代际） | `CONTRACT` |
| C08 | `docs/contract/current/openapi/api.md` | L1（OpenAPI 入口与信封） | `CONTRACT` |
| C09 | `docs/contract/current/h5-app/api.md` | L1（受控客户端当前界面） | `CONTRACT` |
| D01 | `docs/tech-debt/active/memory-knowledge.md` | 既有问题现状；不产生本期修债义务 | `REPO_BASELINE` |
| B01 | `backend/services/query_rewrite_service.py` | QueryRewriteOutput:28；_parse_query_rewrite_output:271；_build_step1_5_prompt:137；execute_query_rewrite:307 | `REPO_BASELINE` |
| B02 | `backend/services/multi_vector_retrieval_service.py` | MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | `REPO_BASELINE` |
| B03 | `backend/services/prompt_builder.py` | count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | `REPO_BASELINE` |
| B04 | `backend/utils/dashvector_client.py` | build_filter:19；search:78；upsert:153；delete:210；list_by_filter:232；fetch_by_ids:273 | `REPO_BASELINE` |
| B05 | `backend/services/memory_llm_service.py` | upsert_step6_vectors:445 | `REPO_BASELINE` |
| B06 | `backend/services/step6_orchestrator.py` | execute_step6:64 | `REPO_BASELINE` |
| B07 | `backend/services/vector_memory_write_service.py` | upsert_user_memory:11 | `REPO_BASELINE` |
| B08 | `backend/services/realtime_voice_memory_service.py` | _write_atom:727；_finish:779；stage_deletion_fence:503 | `REPO_BASELINE` |
| B09 | `backend/services/character_knowledge_service.py` | create_entry:157；update_entry:200；delete_entry:256；list_entries:85 | `REPO_BASELINE` |
| B10 | `backend/services/user_vector_memory_service.py` | create_entry:172；update_entry:215；delete_entry:258；list_entries:103 | `REPO_BASELINE` |
| B11 | `backend/routers/admin/knowledge_mgmt.py` | L1（知识新增/value 编辑/删除路由） | `REPO_BASELINE` |
| B12 | `backend/routers/admin/users.py` | L44/258/500（历史对话角色/查询及user/private原CRUD；本次A32定向复读） | `REPO_BASELINE` |
| B13 | `backend/routers/admin/memory_mgmt.py` | vector-db-config GET/PUT/test:L161–320；batch_delete_memories:430；search_memories_global:364 | `REPO_BASELINE` |
| B14 | `backend/utils/character_knowledge_validate.py` | build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | `REPO_BASELINE` |
| B15 | `backend/services/vector_service.py` | L1（历史 mem_* 自由正文与普通 Agent 检索） | `REPO_BASELINE` |
| B16 | `backend/services/admin_config_service.py` | get_active_config:31；publish_config:181 | `REPO_BASELINE` |
| B17 | `backend/routers/admin/vector_config.py` | VectorRetrievalPatch:34；_prompt_hot_config_keys/预算合并与校验:L94–134 | `REPO_BASELINE` |
| B18 | `backend/routers/admin/system_monitor.py` | L35（第三方保存/测连与独立权限） | `REPO_BASELINE` |
| B19 | `backend/config.py` | get_dashvector_endpoint:147；get_dashvector_api_key:142；get_dashvector_collection:155 | `REPO_BASELINE` |
| B20 | `backend/services/embedding_service.py` | get_embedding:30；_call_embedding_api:122 | `REPO_BASELINE` |
| B21 | `backend/utils/llm_client.py` | chat_sync:116 | `REPO_BASELINE` |
| B22 | `backend/routers/chat.py` | _execute_llm_bundle:377；_persist_bundle_success:227；_mark_pack_failed:296；_sse_chat_wait_bundle:648；chat_send:720；chat_resend:758；chat_timeline:826 | `REPO_BASELINE` |
| B23 | `backend/services/chat_service.py` | await_bundle_payload:206；enqueue_send:251；enqueue_resend:287；new_generation_for_user:171；schedule_recovery_bundle:129 | `REPO_BASELINE` |
| B24 | `backend/services/chat_queue_service.py` | try_acquire_bundle_lock:81；release_bundle_lock:89；schedule_debounced:49 | `REPO_BASELINE` |
| B25 | `backend/services/open_chat_service.py` | open_send:21；open_resend:46；_payload_to_api_response:57 | `REPO_BASELINE` |
| B26 | `backend/routers/open/chat.py` | L1（OpenAPI send/resend） | `REPO_BASELINE` |
| B27 | `backend/services/step8_subchain.py` | execute_step8_subchain:56；提交后收尾:L216起；_fallback_write_agent_message:376；_decay_gate_and_update:397 | `REPO_BASELINE` |
| B28 | `backend/services/future_handler.py` | scan_and_consume:42；_consume_one:93；_on_consume_success:146；_clear_future_slot:175 | `REPO_BASELINE` |
| B29 | `backend/services/chat_prompt_view_service.py` | get_step15_prompt_view:47；get_step3_prompt_view/get_step8_prompt_view（只读规则） | `REPO_BASELINE` |
| B30 | `backend/routers/admin/chat_prompt_view.py` | view_step15_prompt:26 | `REPO_BASELINE` |
| B31 | `backend/routers/admin/prompt_mgmt.py` | test_prompt:617 | `REPO_BASELINE` |
| B32 | `backend/utils/admin_auth.py` | get_current_admin:93；require_role:183 | `REPO_BASELINE` |
| B33 | `backend/routers/memory.py` | L19（只读 list 路由） | `REPO_BASELINE` |
| B34 | `backend/services/agent_service.py` | _search_memories_for_agent:688；generate_and_save_message:276 | `REPO_BASELINE` |
| B35 | `backend/services/realtime_voice_recall_service.py` | L1（既有语音实时召回） | `REPO_BASELINE` |
| B36 | `backend/services/realtime_voice_context_source_service.py` | L1（既有 user/private 会前读取） | `REPO_BASELINE` |
| B37 | `backend/services/realtime_voice_context_pack_service.py` | L1（既有会前过滤与打包） | `REPO_BASELINE` |
| B38 | `backend/models/realtime_voice.py` | VoiceMemoryJob:349；VoiceMemoryTrace:478 | `REPO_BASELINE` |
| B39 | `alembic/env.py` | L9（现有迁移加载方式） | `REPO_BASELINE` |
| B40 | `backend/database.py` | L37（请求数据库依赖提交点） | `REPO_BASELINE` |
| U01 | `admin/pages/vector-token-config.html` | L66（当前统一 TopK/threshold 与预算页） | `REPO_BASELINE` |
| U02 | `admin/pages/third-party.html` | L92（当前第三方测连页） | `REPO_BASELINE` |
| U03 | `admin/pages/memory-rules.html` | L330（Step6 Prompt、全局列表和批删） | `REPO_BASELINE` |
| U04 | `admin/pages/knowledge.html` | L247（只读 Key、value 编辑、删除） | `REPO_BASELINE` |
| U05 | `admin/pages/user-detail.html` | L710–935（历史对话）；L1005–1195（user/private记忆编辑/回执） | `REPO_BASELINE` |
| U06 | `admin/pages/chat-prompt-step15.html` | L1（主链/Step8 只读预览） | `REPO_BASELINE` |
| U07 | `admin/static/js/admin-api.js` | L1（现有导航与只读控件约定） | `REPO_BASELINE` |
| U08 | `frontend/pages/chat.html` | L1121（CHAT_CLIENT_ABORT_MS）；loadTimeline:L1437；visibilitychange:L1797 | `REPO_BASELINE` |
| U09 | `frontend/static/js/memory-nebula.js` | L1（现有列表分页、节点与空态） | `REPO_BASELINE` |
| U10 | `nginx/nginx.conf` | L1（仓库网关 timeout 配置） | `REPO_BASELINE` |
| T00 | `README.md` | L9（PYTHONPATH=. pytest tests/） | `REPO_BASELINE` |
| T01 | `tests/test_query_rewrite_service.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T02 | `tests/test_multi_vector_retrieval_service.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T03 | `tests/test_prompt_builder.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T04 | `tests/test_step6_vector_upsert.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T05 | `tests/test_memory_write_source.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T06 | `tests/test_dashvector_client.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T07 | `tests/test_dashvector_upsert_response.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T08 | `tests/test_admin_character_knowledge.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T09 | `tests/test_admin_vector_token_config.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T10 | `tests/test_chat.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T11 | `tests/test_step023_future_handler.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T12 | `tests/test_step024_step8_subchain.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T13 | `tests/test_chat_prompt_view.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T14 | `tests/test_h5_static_contract.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T15 | `tests/test_realtime_voice_step028_memory.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T16 | `tests/test_realtime_voice_step030_recall.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T17 | `tests/test_realtime_voice_step026_context_pack.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |
| T18 | `tests/test_realtime_voice_step029_jobs_runtime.py` | L1（现有测试模块；新增预期须以当前 v3.2 为准） | `REPO_BASELINE` |

测试入口已在T00核实：`PYTHONPATH=. pytest tests/`。实施时按STEP影响选模块，示例`PYTHONPATH=. pytest tests/test_query_rewrite_service.py tests/test_multi_vector_retrieval_service.py`只表示沿现有入口的局部选择，非本轮已执行。T18真实事务/锁测试另需其隔离运行环境；默认skip不能当真实事务通过。新增维护/诊断/回填/并发测试及运行命令按实际方案定位，未定稿不写成已有文件或生产命令。

### 1.3 本次后台定向证据与计划新增项

A32-01～14与P01 §2.1.1同号，均为原后台稿登记的`REPO_BASELINE/CONTRACT`，不是RUNTIME；原main读取不代表本轮重新访问GitHub或复读全部A32来源。本轮本地关键源码复核与静态检查另见§7.4，源文件链接在P01可直接定位。

| 证据 | 当前文件/定位 | 用途 |
|---|---|---|
| A32-01 | `backend/routers/admin/users.py`；44-46、258-393、500-647 | _USER_BUSINESS_READ_ROLES；get_user_conversations；user/private读写角色与源响应包装 |
| A32-02 | `admin/pages/user-detail.html`；710-935、1005-1195 | 历史标签/分页/查询；新增Modal、行内编辑、单删及结果收口 |
| A32-03 | `backend/routers/admin/vector_config.py`；1-280 | 策略读写角色；旧top_k/threshold；固定nickname白名单与错误校验；GET/PUT |
| A32-04 | `admin/pages/vector-token-config.html`；55-340 | 两个Tab、dirty PATCH、加载/默认值与保存GET回读 |
| A32-05 | `backend/routers/admin/memory_mgmt.py`；35-320、350-480 | 独立vector_db_config入口/角色；全局user与1～100批删、旧返回 |
| A32-06 | `admin/pages/memory-rules.html`；330-590 | 第二个TopK、测连；global表格/截断提示、单删复用batch |
| A32-07 | `backend/routers/admin/system_monitor.py`；35-73、288-485 | 系统域角色、服务白名单、状态卡、配置/测连与缓存/日志 |
| A32-08 | `admin/pages/third-party.html`；75-285 | 系统域页面限制、SERVICE_KEY_MAP、测试通过/改字段作废与配置弹窗 |
| A32-09 | `backend/routers/admin/knowledge_mgmt.py`；1-150 | 角色公开/知识CRUD、角色与只改value |
| A32-10 | `admin/pages/knowledge.html`；240-465 | 原Modal、保存/关闭/刷新和删除确认 |
| A32-11 | `admin/static/js/admin-api.js`；1-190、245-425 | observer精确只读限制、动态data-write-action、adminRequest、确认与菜单 |
| A32-12 | `backend/services/chat_prompt_view_service.py`；1-200 | Step1.5模板同源；Step3 token_limit_default常量；Step8/Agent只读说明 |
| A32-13 | `backend/routers/admin/chat_prompt_view.py`；1-85 | Step1.5/Step3/Step8只读路由及角色 |
| A32-14 | `docs/contract/current/memory-knowledge/admin-ui.md`；全文 | 当前三Tab结构、原字段/角色和菜单位置；目标变更不冒充current运行事实 |

两页memory-diagnostics.html/memory-index-maintenance.html、对应JS、新管理API/响应字段及下文测试文件均为`PLANNED`。现有admin/pages目录已查看，未把新页说成既有；实施时按002检查注册/命名冲突。新状态和索引元数据不建立事实历史版本查询。

### 1.4 最新用户取舍的继承（2026-10-07～08）

继承2026-10-07质量取舍及S14全入口DotProduct适配；最新S15取消旧Cosine搬迁/完整导出/迁移源env前提，正式上线或重新开放测试前一次性清除旧对话、向量相关MySQL/缓存任务、对话画像及旧预约，保留日记/朋友圈/账号资料/姓名昵称/亲密度数值。精确矩阵见PRD §12.4和里程碑§2.1；F08新库维护保留。22步编号/标题/依赖不变，022“回退演练”指新数据恢复，非旧库回切。

- 费用/成本不作为本期评测、验收或切换门槛，不要求冻结或达成费用目标；已有调用费用信息可附记，缺失不阻断020/021/022。
- 日常延迟与提升幅度先记录同集真实观察/对照，暂不设数字达标阈值或百分比承诺，不能因缺数字目标阻断020/021/022。45+45、固定180秒整轮及同代不续时、一次失败调用重试、有限恢复/隔离等硬条件保持。
- 本期优先解决文字记忆漏召回、无关注入/混淆及现有稍复杂记忆/查询的精准召回，覆盖语义改写/指代与多个限定条件；样本和预期依现存正文，不合成缺失事实、不调整内容结构。四路、同Key覆盖、提取协议与语音读取延期边界保持。
- 正式验收仍须冻结同集语料/查询、相关与无答案标注、质量判断口径、关键场景及真实输出；核对最终选入质量与关键场景不退步，正常/降级分报，逐项说明非关键退步。候选命中不能代替最终选入质量；可按证据报告观察到的改善，无百分比承诺。

## 2. 功能与约束清单

| ID | PRD需求 | 原优先级 | 本期处理 | STEP覆盖 |
|---|---|---|---|---|
| F01 | Step6 索引写入 | 核心 | 按原需求交付 | STEP-006 |
| F02 | 其他写入口一致 | 配套 | 按原需求交付 | STEP-006、STEP-007 |
| F03 | 删除与失败恢复 | 配套 | 按原需求交付 | STEP-004、STEP-005、STEP-007、STEP-017 |
| F04 | 分路混合召回 | 核心 | 按原需求交付 | STEP-010、STEP-021 |
| F05 | 分路重排及分数 | 核心 | 按原需求交付 | STEP-011、STEP-021 |
| F06 | 数量、模块与总预算 | 核心 | 按原需求交付 | STEP-013、STEP-021 |
| F07 | 有界容错与降级 | 核心 | 按原需求交付 | STEP-009、STEP-010、STEP-011、STEP-012、STEP-014、STEP-021 |
| F08 | 历史补索引与回填记录可查看 | 核心 | 原回填及其后台结果承接 | STEP-001、STEP-008、STEP-017、STEP-018；019集成 |
| F09 | 生效配置 | 配套 | 按原需求交付 | STEP-003、STEP-022 |
| F10 | 真实诊断与历史 | 配套 | 按原需求交付 | STEP-017、STEP-018 |
| F11 | 共用调用方 | 配套 | 按原需求交付 | STEP-012、STEP-014、STEP-015 |
| F12 | 三端兼容 | 配套 | 按原需求交付，含旧 Prompt Test 消费者 | STEP-007、STEP-013、STEP-014、STEP-015、STEP-016、STEP-018、STEP-019、STEP-022 |
| F13 | 语音实时召回 | 延期 | 算法升级延期RP-004；019完成S14存储/score适配及回归 | 不映射升级实施；STEP-019兼容 |
| F14 | 语音会前加载 | 延期 | 算法升级延期RP-004；019完成S14存储/score适配及回归 | 不映射升级实施；STEP-019兼容 |
| F15 | Step1.5 BM25 词组生成 | 核心 | 按原需求交付 | STEP-009、STEP-020、STEP-021 |

未编号约束只生成CSTR追踪号，不改造为RQ或新优先级。来源均为P01/`PRD`。

| ID | 约束 | locator与范围 | STEP |
|---|---|---|---|
| CSTR-01 | 提取/身份/安全保持及候选信任边界 | §4.2、§7.1“越权或不可信候选”、§11.1/11.2、§12.8；不改提取结构/Stable Key/同Key覆盖/原Step5输入及安全职责；候选正文仅作数据，不覆盖系统指令/可信用户归属 | STEP-006、STEP-013、STEP-019 |
| CSTR-02 | GATE-A索引基础设施 | §9.3.1 GATE-A及完整遍历要求；真实属性、双独立候选、编码版本、完整遍历及结束证据 | STEP-001 |
| CSTR-03 | GATE-B行为接口定稿 | §9.3.1 GATE-B及参数字典；具体协议/schema/故障设计与完整参数字典 | STEP-002 |
| CSTR-04 | GATE-C评测冻结 | §9.3.1 GATE-C；§11.5与§1.4取舍；正式判定前冻结同集语料/查询/标注/质量口径/关键场景；费用不设门槛，日常延迟/提升幅度仅记录 | STEP-020 |
| CSTR-05 | GATE-D切换证据 | §9.3.1 GATE-D；全部功能、真实同集总体改善（不设幅度数字阈值）与关键不退步、硬时限、新库维护完整性、S15清理/保留核验及新数据恢复证据与执行边界；费用及日常延迟/提升幅度数字目标不阻断 | STEP-022 |
| CSTR-06 | 可信有效性与使用点保护 | §6.6.2可信有效性与使用检查点；失效/不确定排除；检查到使用之间有确定顺序/保护；使用后的变更不撤回历史输入 | STEP-004、STEP-010、STEP-013 |
| CSTR-07 | 有效配置组合冻结及凭据记录边界 | §6.3、§12.3/12.5；实际消费版本固定，中途发布只影响后续请求，显式回退来源；本期配置/测连/服务调用的凭据不得进入响应、错误或日志 | STEP-003 |
| CSTR-08 | 同源最终选入与前缀保真 | §6.3.1结构化选入与前缀保真；身份不丢、逆成功选入序裁剪、失效后缀淘汰、不补位、同次Prompt清单一致 | STEP-013 |
| CSTR-09 | 诊断无业务副作用、费用及凭据记录边界 | §6.7.1、§12.3/12.5；只读装载、不写聊天业务状态，实际外部调用有费用；本期服务凭据不得进入诊断/维护响应、错误、日志或持久记录 | STEP-017 |
| CSTR-10 | 运维交付与操作授权 | §12.4/12.8运维交付；新库回填/断点/对账/执行器、S15一次性清理及新数据恢复交付，不自动生产操作 | STEP-008、STEP-022 |
| CSTR-11 | 范围外消费者兼容 | §6.4、§12.8及S14；星云/Agent/语音存储与score适配，既有读取、权限、安全保持；算法升级及补时间排除 | STEP-019 |
| CSTR-12 | 按实际实施同步文档 | §12.8文档同步；实际行为契约及必要导航/manifest/记录同步，不把目标PRD写成运行事实 | STEP-022 |
| CSTR-13 | 新Future防旧执行误清 | §11.5硬约束：对应测试内新槽位被旧任务误删为0；成功/失败各自业务语义保持，只核对消费身份衔接，不扩成功计数/预约改造 | STEP-015 |

### 2.1 排除项与技术债

- RQ-02延期RP-003、RQ-03/04及F13/14升级延期RP-004；按S14适配存储/score并回归，不建立算法升级STEP。新的记忆/意图路由、统一ResolvedQuery/全局rerank、事件事实版本、改Key、内容拆解/原子化/历史重抽取均排除。
- PRD §4.2的范围控制建议保留建议身份：不无依据换embedding/维度/缓存、升级普通Agent、引入知识图谱/整套记忆平台/H5 CRUD/全项目配置治理。若基础设施迫使迁移，返回Q06评估，不静默扩范围。
- D01仅作既有问题现状证据，不作为本PRD技术债处置清单；本期没有额外 TD 编号清偿义务；RV31-R01 是当前预算配置必须修正的直接缺陷，不因没有 TD 编号而排除。不修改 D01，也不据文档修订宣称债务关闭。
- PRD §12.7的未编号限制完整保留：同Key经历覆盖延期RP-003；语音实时召回/会前升级延期RP-004，按S14适配存储/score并回归且不补造时间；新路由沿S3延期；文字提取缺少旧记忆输入及解析/内容质量不改；Step6非持久create_task/跨入口写序仅承诺定稿的本期索引一致性和失败恢复；本期新能力打通有效配置，全项目历史治理不自动纳入；列表cap不能证明全量，近似token计数及最终超限只告警不能满足硬预算，回填完整遍历与RQ-09阻断必须落实，计数器/安全预留仍待Q03。派生索引恢复不扩为全部任务可靠性或事实恢复。

## 3. STEP总览、依赖与进度

依赖列区分开发前置与验收收口前置，编号顺序不替代依赖。每个STEP仅承担所列独立目标；开发前置未完成/缺验收证据时停止当前STEP开发。STEP-017的AC12业务对照须STEP-015证据（传递014），新增AC11-a回填读取对照须STEP-008证据；DONE须两者满足。其开发前置不变，不阻止其余开发并行，008不依赖017/018。运行启用新链还必须等待S15实际清理/保留核验及GATE-D，STEP-010的隔离实现不表示可以用不完整索引切换业务。

### 3.1 进度总览

| 完成数 | 总数 | 当前状态 |
|---|---|---|
| 22 | 22 | 001～020原验证保持；021按用户取舍完成功能收口、质量FAIL/缺项非阻断保留；022准备、正式契约整合及本地Docker实际S15/部署均完成，M8/GATE-D按用户接受风险收口；CONTRACT_MERGED_VERIFIED。后续自动索引/新增修复、82项积压清零及qwen3.7-text-rerank本地部署已补记，最新证据与边界见[§3.40](#memory-v32-followup-closure)，原收口时点保留于§3.39 |

### 3.2 STEP明细

下表证据中的“未部署／未接业务”等描述保留各STEP原验收时点；后续本地启用见§3.39，部署后修复及最新验证边界见§3.40，不以历史阶段状态覆盖当前进度。

| STEP | 功能名称 | 需求ID | 验收ID | 前置STEP | 状态 | 证据 |
|---|---|---|---|---|---|---|
| STEP-001 | 索引基础设施与完整遍历核验 | F08、CSTR-02 | AC11、CSTR-02 | 无 | `DONE` | S15收口核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-S15收口与完整来源方案-2026-10-09.md`）；双通道/603、新模型/来源方案及本地Docker实际部署映射齐全 |
| STEP-002 | 行为、接口与参数定稿 | CSTR-03 | CSTR-03 | STEP-001 | `DONE` | GATE-B设计核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-002-GATE-B-核验记录-2026-10-09.md`）；40项检查与独立二审通过，见§3.6 |
| STEP-003 | 请求有效配置与后台独立数量 | F09、RQ-05、RQ-06、RQ-12、RQ-19、RQ-23、CSTR-07 | AC05、AC12、AC17、AC28、CSTR-07、AC13 | STEP-002 | `DONE` | 实现与核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-003-实现核验记录-2026-10-09.md`）：96局部、2真实MySQL、27Chrome场景与真实provider/counter通过；二审修复；未部署 |
| STEP-004 | 可信当前凭据与派生索引维护核心 | F03、RQ-13、RQ-14、CSTR-06 | AC10、AC23、AC30、AC31 | STEP-001,STEP-002,STEP-003 | `DONE` | 实现与核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-004-实现核验记录-2026-10-09.md`）：持久源/使用保护、真实MySQL并发与云端隔离组件通过；未接业务 |
| STEP-005 | 有限索引恢复执行器 | F03、RQ-14、RQ-14.1 | AC23、AC30 | STEP-004 | `DONE` | M3核验（本地留存，未随本次提交；原引用：`execution/evidence/M3-配置与维护核心核验-2026-10-09.md`）：worker23项、retry16项及独立二审；最终243＋1项组合/定向、8项真实MySQL与云串联通过 |
| STEP-006 | 文字及语音写入接入索引维护 | F01、F02、RQ-13、RQ-14、CSTR-01 | AC01、AC02、AC16、AC18、AC30 | STEP-005 | `DONE` | 实际文字/语音/legacy包装层、139项局部与既有回归、独立复核P1关闭；见§3.10；未部署 |
| STEP-007 | Admin 既有 CRUD 与维护反馈 | F02、F03、F12、RQ-13、RQ-14 | AC02、AC10、AC13、AC30 | STEP-005 | `DONE` | 四类CRUD/回执/持久批删/三页恢复；166局部、真实MySQL2、Chrome2及三项独立复核修复通过，见§3.10 |
| STEP-008 | 历史现存正文完整回填 | F08、RQ-13、RQ-14、CSTR-10 | AC11、AC23、AC31 | STEP-001,STEP-006,STEP-007 | `DONE` | 603持久回填/DTO、S15工具及保留恢复隔离演练；六项独立复核与整体语音集成缺陷均关闭，见§3.10；实际业务清理归022 |
| STEP-009 | BM25 词组与确定性改写补齐 | F15、F07、RQ-01、RQ-10 | AC07、AC20、AC21、AC32、AC33 | STEP-002 | `DONE` | 字段存在性解析、确定性补齐、BM25同源模板与只读预览；M4汇总证据（本地留存，未随本次提交；原引用：`execution/evidence/M4-检索与Prompt内核核验-2026-10-10.md`）及真实rewrite协议通过；真实质量留021 |
| STEP-010 | 四路双通道候选与有效性去重 | F04、F07、RQ-01、RQ-11、RQ-19、RQ-23、CSTR-06 | AC03、AC08、AC13、AC21、AC28、AC31、AC32 | STEP-003,STEP-004,STEP-009 | `DONE` | 可信SQL核代/归属/正文摘要、独立dense/BM25和空因；7项隔离用例及四路真实云结果通过，补齐legacy版本证明；见§3.8 |
| STEP-011 | 路内完整 rerank 与故障融合 | F05、F07、RQ-01、RQ-11、RQ-12、RQ-23 | AC04、AC09、AC28、AC32 | STEP-002,STEP-010 | `DONE` | 全量重排映射、同分、门槛与RRF；11项含query/单篇/全请求超限零发送零重试用例及真实云重排通过；见§3.8 |
| STEP-012 | 45 秒加 45 秒检索编排 | F07、F11、RQ-20 | AC07、AC08、AC09、AC22 | STEP-009,STEP-010,STEP-011 | `DONE` | 45+45共享截止/一次重试/迟到拒绝；10项含真实asyncio截止混合收口、HTTP错误分类用例通过；见§3.8 |
| STEP-013 | 完整 Prompt 选择与最终有效性 | F06、F12、RQ-05、RQ-07、RQ-08、RQ-09、CSTR-01、CSTR-06、CSTR-08 | AC04、AC05、AC06、AC12、AC13、AC26、AC31、AC33、CSTR-01 | STEP-003,STEP-004,STEP-011 | `DONE` | M4完整证据（本地留存，未随本次提交；原引用：`execution/evidence/M4-检索与Prompt内核核验-2026-10-10.md`）：数量/裁剪/真实官方计数/并发有效性与HTTP交付、旧适配及只读两页通过；分项与延期边界见§3.8 |
| STEP-014 | 主文字与 OpenAPI 唯一终态 | F07、F11、F12、RQ-09、RQ-22、RQ-24 | AC14、AC15、AC26、AC27、AC29、AC34、AC13 | STEP-002,STEP-012,STEP-013 | `DONE` | 实际入口/固定180秒/唯一终态/身份与纯读投影、真实MySQL及独立复核均闭环；见§3.13 |
| STEP-015 | Step8 新结果与条件清槽 | F11、F12、RQ-09、RQ-20、RQ-22、CSTR-13 | AC15、AC22、AC26、AC27、AC34、CSTR-13 | STEP-012,STEP-013,STEP-014 | `DONE` | 两保存出口/固定180秒/结构化提交/原副作用防重/全部条件清槽通过；独立I1/I2闭环，见§3.13 |
| STEP-016 | H5 等待与消息重同步 | F12、RQ-22、RQ-24 | AC14、AC27、AC29 | STEP-014 | `DONE` | 原条件及历史接线窄修复复核闭环；见§3.14 |
| STEP-017 | 真实诊断与维护管理后端 | F10、F03、RQ-09、RQ-15、RQ-16、RQ-17、RQ-17.1、RQ-21、CSTR-09、F08 | AC12、AC13、AC23、AC24、AC25、AC26、AC30、AC31、AC33、AC35、CSTR-09、AC11 | 开发：STEP-002,STEP-005,STEP-012,STEP-013；AC12验收：STEP-015（传递014）；AC11-a验收：STEP-008；DONE两者均须满足 | `DONE` | 017核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-017-后端诊断与维护核验-2026-10-11.md`）及实际契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-017-契约增量.md`）；三链/008真实记录对照、持久状态/权限/分页/故障及独立复核通过，见§3.17 |
| STEP-018 | 诊断与维护后台操作页面 | F10、F12、RQ-09、RQ-15、RQ-16、RQ-17、RQ-17.1、RQ-21、F08 | AC13、AC24、AC25、AC26、AC30、AC35、AC11 | STEP-003,STEP-007,STEP-017 | `DONE` | 018核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-018-诊断与维护页面核验-2026-10-11.md`）及契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-018-契约增量.md`）；真实Chrome/SQL接口、完整分页及fix1独立闭环，见§3.18 |
| STEP-019 | 范围外消费者及三端兼容回归 | F12、CSTR-01、CSTR-11 | AC13、AC14、AC16、AC17、AC18、AC33、AC05、AC11、AC12、AC30、AC35 | STEP-006,STEP-007,STEP-014,STEP-015,STEP-016,STEP-018 | `DONE` | 019核验及GAP-01补证（本地留存，未随本次提交；原引用：`execution/evidence/STEP-019-消费者与后台兼容核验-2026-10-11.md`）及契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-019-契约增量.md`）；原有效分项复用，实际S15→读API→Chrome保留/空态补证齐全，重新结算见§3.22；§3.19/3.21保留原时点 |
| STEP-020 | 正式评测前冻结 | RQ-18、F15、CSTR-04 | AC19、CSTR-04 | STEP-002 | `DONE` | 冻结登记（本地留存，未随本次提交；原引用：`execution/evidence/STEP-020-正式评测冻结-2026-10-12.json`）；.1原结论保留§3.27；§3.34已完成获批补标及一轮Prompt/cg-user隔离修复的24例真实验证，有改善仍有质量失败，新版本未冻结/未重判GATE-C |
| STEP-021 | 同集真实质量与性能验收 | RQ-18、F04、F05、F06、F07、F08、F15 | AC19、AC20 | STEP-008,STEP-012,STEP-013,STEP-019,STEP-020 | `DONE` | 批准兼容核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-查询空响应兼容核验-2026-10-13.json`）；§3.36按用户授权完成功能收口，原质量FAIL/缺对照保留非阻断，不追认原完成条件全PASS |
| STEP-022 | 切换证据、回退演练与交接 | RQ-18、F09、F12、CSTR-05、CSTR-10、CSTR-12 | AC17、CSTR-05 | STEP-008,STEP-018,STEP-019,STEP-021 | `DONE` | §3.39：原隔离目标凭供应商回执及独立退役证明收口；准备/18份正式契约整合核验完成；实际S15 70资源/58保留摘要通过，本地Docker已开放、旧库退役、重启不重复清理；原质量风险保留，详见部署证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-本地Docker部署收口-2026-10-13.json`） |

### 3.3 阻断与来源变化

| 日期 | STEP | 类型 | 证据或变化 | 处理结果 |
|---|---|---|---|---|
| 2026-10-05 | STEP-001/002/020/022 | 历史技术门槛登记 | 原 P01 §9.3.1；无运行证据 | 保留原待执行状态，不计作新的产品待答。 |
| 2026-10-07 | STEP-002/003/006/013/014/015/016/019/022 | 文档修订 | RV31-R01～R06、P01 新增子条款及 §5.1 映射 | 已写入执行要求；未实施，全部 NOT_STARTED。 |
| 2026-10-08 | STEP-002/003/004/008/013/017/018/019/020/021/022 | 当前取舍继承与交接修复 | §1.4的2026-10-07用户决定、当前v3.2引用、分项完成条件、分页/昵称/配置未知边界 | 仅文档修订及静态核对；22步/ID/依赖保持，未实施，仍0/22。 |
| 2026-10-08 | STEP-001 | 实施核验阻塞 | `.env`目标实读1024/FLOAT/cosine、无稀疏schema；完整扫描/可信身份清单及隔离双通道实证缺失，详见§3.5 | 核验工具和证据已落盘；不提交GATE_EVIDENCE_READY，不进入002，不改生产数据。 |
| 2026-10-11 | STEP-019/M7 | 原验收证据缺口 | M7-GAP-01：原“配置与操作闭环”的S15清理后空历史及保留资料/日记/朋友圈/亲密度数值可见性；现有SQL保留证据与筛选空态不能替代同一清理后夹具的实际API/页面对照 | §3.21曾阻塞；按§3.22自有S15夹具/实际API/Chrome补证关闭，019重新DONE、M7通过。无对应业务源码缺陷或需求变更，未执行业务清理。 |
| 2026-10-12 | STEP-020/M8 | 必要评测输入缺口 | 当前入口/manifest无正式同集/标注产物；按用户补充仅查本地Docker，现存文字无可复核相关记忆快照，旧memory表0不能证明远端向量为空。缺当前真实文字失败样本、当前源身份/正文及标注；M1/M4合成探针不等价 | 020 BLOCKED，GATE-C NOT_PASSED；021/022及正式契约整合未进入。原时点见§3.23；只读权限已按最新决定补齐，现存正文及查询候选见§3.24，剩余为真实失败及实际运行组合；不是缺费用、延迟或改善数字目标。 |

进度保留在本主文档，不另建重复进度文件；状态只使用`NOT_STARTED`、`IN_PROGRESS`、`DONE`、`BLOCKED`。只有对应完成标志有验证证据才能改DONE。文档交接状态 `DOC_REVISED_WITH_GATES` 表示正文修订与静态自检完成；原 `STEPS_VERIFIED` 是旧计划的历史交接状态。两者都不是运行验证；当前实施状态以本§3为准，文档头和任务内原阶段说明保留其文档修订时点。

### 3.4 里程碑编排登记
2026-10-08 编排阶段 USER_DECISION：用户要求完成已修正的编排文档并自审，当时不启动业务开发；后续开发授权与实际进展见§3.5。
计划：[记忆存入与分路混合召回优化开发里程碑文档](execution/记忆存入与分路混合召回优化开发里程碑文档.md)；计划状态：IMPLEMENTATION_PLAN_READY。
本§3继续作为唯一执行记录；计划只记录分组/交接，不另建执行日志。后续S14/S15已授权同步受影响任务/验收；22步编号、标题及依赖保持。

| 里程碑 | STEP顺序 | 状态 | 闸门证据/判定 |
|---|---|---|---|
| M1 | 001 | VERIFIED | GATE_EVIDENCE_READY已接收；GATE-A通过（PASS_WITH_RISKS），证据及后续边界见§3.5 |
| M2 | 002 | VERIFIED | GATE_EVIDENCE_READY已接收，GATE-B PASS_WITH_RISKS；仅设计验收，见§3.6 |
| M3 | 003→004→005 | VERIFIED | USER_DECISION 2026-10-09：用户明确接受既有M3证据并批准进入M4；沿用完整证据（本地留存，未随本次提交；原引用：`execution/evidence/M3-配置与维护核心核验-2026-10-09.md`），未复跑或宣称本轮新增运行验证 |
| M4 | 009→010→011→012→013 | VERIFIED | 2026-10-10接收GATE_EVIDENCE_READY并逐项核对原完成标志，PASS_WITH_RISKS；有效证据及后续边界见§3.8/3.9 |
| M5 | 006→007→008 | VERIFIED | 2026-10-10按原完成条件接收证据，PASS_WITH_RISKS；79路径及日志摘要匹配，见§3.12 |
| M6 | 014→015→016 | VERIFIED | 2026-10-11接收GATE_EVIDENCE_READY，原完成条件及有效证据齐全，PASS_WITH_RISKS；见§3.15 |
| M7 | 017→018→019 | VERIFIED | 最终闸门PASS_WITH_RISKS：M7-GAP-01定向补证齐全、019重新结算；原前置及其余有效证据复用，见§3.22；§3.20/3.21保留原提交/判定时点 |
| M8 | 020→021→022 | IN_PROGRESS | 020/GATE-C .1历史保持；021功能收口/质量非阻断；§3.38最小回执修复VERIFIED，缺原run独立事实仍BLOCKED；022 IN_PROGRESS，正式整合未开始，最终GATE-D/M8未裁决 |

契约整合状态：NOT_STARTED；017/018/019各自实际增量已汇入M7临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M7-临时契约.md`），§3.22补证未产生行为/接口增量，原临时契约继续有效；M7闸门已通过但不提前正式整合。M3临时契约候选（本地留存，未随本次提交；原引用：`execution/contract-drafts/M3-临时契约.md`）、M4临时契约候选（本地留存，未随本次提交；原引用：`execution/contract-drafts/M4-临时契约.md`）、M5临时契约候选（本地留存，未随本次提交；原引用：`execution/contract-drafts/M5-临时契约.md`）及M6临时契约候选（本地留存，未随本次提交；原引用：`execution/contract-drafts/M6-临时契约.md`）已随各阶段局部证据交接。未来CONTRACT_*状态和READY证据事件在此独立登记，不混入STEP状态列。
最后收口：022业务证据齐→收齐含M8的有效临时契约→正式整合/验证→原完成标志齐→022 DONE及M8/VERIFIED；详见计划§7.2。
编排阶段静态检查PASS、独立复核通过，阶段结果PASS_WITH_RISKS；不代表业务完成。当前20/22，M1～M7闸门已通过；017～019及M7判定见§3.22。020冻结/GATE-C .1见§3.27，021原始阻塞/最小模板及实际结果见§3.29～§3.31，§3.32校准/原因补证本轮已执行，§3.34新增获批补标/一轮隔离修复及24正常真实回复验证，残余与恢复位置见该节；022及正式契约整合未启动。历史结算/暂停记录保留原时点；早期019资源夹具事故及未知旧部署影响不能解释为零副作用。

### 3.5 M1/STEP-001 执行与恢复（2026-10-09）

- USER_DECISION：继续M1；本轮明确运行环境为本地Docker，要求说明未通过的原因、需用户做什么及停止原因。继承S15仅维护新库，启用前一次性清旧对话/向量关联数据，保留资料/姓名昵称/亲密度数值/日记/朋友圈，清画像与旧预约；不迁移旧Cosine。22步任务/验收/依赖不改。
- 产物：S15收口与完整来源方案（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-S15收口与完整来源方案-2026-10-09.md`）、早先运行JSON（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-S15-runtime-mapping-2026-10-09.json`）、本轮Docker运行JSON（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-S15-docker-mapping-2026-10-09.json`）、Docker只读探针（本地留存，未随本次提交；原引用：`../../../scripts/probe_memory_docker_mapping.py`）。原双通道报告（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-双通道与遍历核验报告-2026-10-09.md`）、合成BM25/断点/截图及10月8日证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-001-基础设施核验报告-2026-10-08.md`）保留原时间点；旧导出/复用阻塞已取消。
- 有效RUNTIME复用：同Endpoint两库属性/指纹一致；新库1024/FLOAT/dotproduct/SERVING，607合成样本在m1_20261009_147cb5a2、default=0，旧库97。真实v4合成输入1024维有限非零，L2范数1.0，新库隔离query code0。旧后台1536维测连反例HTTP200/code=-2019已证，003/019修实际维度/业务码；本轮不重复收费调用/写入，不读业务正文。
- 完整来源交接：603清单/256后续读347、四组600/1/1/1及冻结编码证据有效；补齐backend 14处上下层写删调用、原始HTTP运维脚本与配置分叉。新库空基线＋所有writer写前持久身份/操作锚点可承接完整来源；断点/结束、未知/删除/同ID重建及禁止旁路见报告。002定schema，004/006/007接线，008演练，022实际空库启用；目录仍PLANNED。
- 原阻塞及解除：早先Docker不可连接且3306/6379/8000拒绝连接，无法读取运行配置；并非新库/模型测试失败。用户明确本地Docker后，13:45起实测四容器已运行（13:34启动），项目归属一致；相关16文件摘要一致，backend单PID1，向量/模型6项有效配置与核对时本地配置逐项相同。MySQL三个配置key有效行均0、Redis无对应缓存，按源码回落env；当前仍旧库，新库同Cluster指纹匹配；容器以实际进程配置GET两库描述均HTTP200/code0，属性正确。无法仅凭早先拒连判断Docker当时退出或启动中；不编造历史根因。
- 闸门判定：已接收GATE_EVIDENCE_READY，按M1原清单逐项核对属性/配额/归属、双独立候选/score/更新语义、编码/603完整清单/断点结束、真实模型/L2、新库来源及T0交接，全部满足本阶段要求；GATE-A通过，M1 VERIFIED（PASS_WITH_RISKS），STEP-001 DONE，1/22。无运行契约增量；未进入002。当前旧库是后续切换前现状，不阻塞001；环境缺项已消除，用户无需修改配置或重启。
- 验证与二审：沿用未变化的6项隔离探针单测及真实双通道/603/模型证据；本轮Docker探针语法、真实JSON断言、配置/源码匹配及失败脱敏/不签闸门检查通过。独立二审无Critical/Important/Minor，确认GATE-A证据足够；最终静态复核通过（摘要/链接/manifest、1898行未超限、§3外逐字不变）。不把工具验证算作应用E2E。早先模型探针凭据键错误已纠正并重跑成功；任意中途失败恢复仍由008交付，不夸大已有受控断点试验。
- 交付/恢复：本次只读核验、证据及执行状态变化，PRD/STEP任务和验收/里程碑/正式契约/env/业务实现未改；无业务契约增量，不建立空临时契约。未启动/重启服务、未切库或清数据，607样本仍保留。后续恢复M2/STEP-002；无待用户补充的环境信息。非阻断限制：生产身份目录、完整故障恢复/生产统计/质量、停写排空及新库切换仍待后续实现；607样本由022处理，不将未来能力算作完成。

### 3.6 M2/STEP-002 技术定稿与复核（2026-10-09）

- DONE / M2 VERIFIED / GATE-B PASS_WITH_RISKS：唯一[技术入口](execution/STEP-002-技术方案与参数定稿.md)及四附录、真实只读schema/合成模型证据齐；40项设计检查（本地留存，未随本次提交；原引用：`execution/evidence/STEP-002-design-check-2026-10-09.json`）和独立二审（本地留存，未随本次提交；原引用：`execution/evidence/STEP-002-独立二审-2026-10-09.md`）通过，GATE_EVIDENCE_READY及逐任务映射见核验记录（本地留存，未随本次提交；原引用：`execution/evidence/STEP-002-GATE-B-核验记录-2026-10-09.md`）。USER_DECISION：180秒按最终事务CAS功能裁决，不要求证明物理落盘时刻，超时未成功即失败；已裁决丢回执只核实，不重生成/续时，已同步PRD §9.7。无新增阻塞/待用户配置项；未改业务/env/Docker运行、未清数据、未进入003；无已实施运行契约增量。下一步M3/003配置、004凭据、005恢复；运行故障/质量/实际清理由各原STEP验收。

### 3.7 M4早期执行与暂停记录（2026-10-09）

- USER_DECISION：接受M3既有证据并进入M4；顺序实施009→010→011→012→013，在M4收尾汇总验收单元测试前暂停，不进入M5。
- 009：`parse_memory_queries`保留字段存在性；缺失/null/非法类型复用原输入，合法空/无才跳过，非法CandidateKeys只警告；运行模板/主链与Step8只读预览同源BM25词组和完整13字段示例。
- 本次局部验证：`TIKTOKEN_CACHE_DIR=/private/tmp/lxm-m3-tiktoken PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_memory_query_rewrite.py tests/test_query_rewrite_service.py tests/test_chat_prompt_view.py -q --tb=short`，23 passed；新8例先红后绿。仅隔离模板/解析/预览，不代表真实模型语义质量。
- 010～012：新隔离入口为`memory_hybrid_retrieval`、`memory_rerank`、`memory_retrieval_pipeline`；复用冻结配置、BM25及SQL控制，不接旧业务入口。provider/query区分临时HTTP错误以约束一次重试；旧writer未新增重试。
- 本次局部证据：010的5项SQLite/通道用例；011与provider/vector组件43 passed；012与候选/vector组件30 passed。012虚拟钟用例明确先完成全部候选再推进重排时钟，不把未拿到候选的路计作“已完成候选”。网络响应使用HTTP传输替身，不宣称云端RUNTIME。
- 013实现：`memory_prompt_builder`输出完整Prompt、初选/最终清单、逐条渲染、原因与实际计数；cg→cp→ck轮转、user独立、整条停止/逆序裁剪/同路前缀、不补位。`prompt_builder.build_memory_prompt`承接原上下文模板和完整昵称；普通Agent原helper保持。候选沿原角色标签与`key：value`显示，数据控制字符转义，内部ID/归属仅留DTO，不写进模型正文。
- 计数/保护交接：`OfficialTextCounter.from_config`与`validate_bound_counter`核对冻结模型、官方adapter、id及profile；已知完整模块前缀批量计数并缓存，不以分段token相加替代完整计数。`reserve_prompt`以SQL最终校验淘汰失效项及同路后缀，持久预留后重计数；返回`use_claim_id`和原`use_deadline_at`。`GuardedModelClient.send`必须消费此结果，body交付事件后确认handoff；取消先收口send-task/关闭连接，SQL回执受原截止约束，不能续时。无法证明完成/停止则保留持久保护。`memory_mutation_service._claim_blocked`只在既有锁序内回收已过期且从未dispatch的`reserved`，不按到期释放`dispatching/unknown`。
- 兼容/预览：后台旧Prompt Test显式调用`build_legacy_mock_prompt -> str`，保留mock、草稿和override，不伪造候选身份；Step3/Step8 API与页面从同一`SELECTION_RULES`展示新规则，默认预算标明代码默认值，普通Agent预览不升级。
- 独立审查：009～012静态审查及013高风险增补发现5项问题（legacy缺版本证明、query成功码、原呈现契约、SQL收口时限、冻结counter绑定），均已修复并复核；后续发现过期reserved回收缺口，已修复。回收及批量前缀计数的最后只读复核未发现新增确定缺陷。此结论不替代M4汇总验收。
- 本次修复局部证据（均已实际运行，不能跨组相加）：候选/vector组件23 passed；之后候选7 passed（包含可信初始baseline/分配过新代次的边界）；Prompt/handoff/token及旧Prompt/预览组合66 passed；新增批量计数后token/选入/handoff组合31 passed；过期reserved三态加既有mutation/use_guard组合40 passed。供应商响应均为HTTP替身；SQL为临时SQLite，未宣称MySQL并发锁或云端实际交付已验证。
- 页面证据：`RUN_M4_BROWSER_TESTS=1 TIKTOKEN_CACHE_DIR=/private/tmp/lxm-m3-tiktoken PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_memory_prompt_pages.py -q --tb=short`，1 passed，覆盖真实Chrome中Step3/Step8两页；仅拦截同源GET API，零模型/零业务写。普通沙箱Chrome启动受限，授权隔离进程运行后通过。Python目标文件`py_compile`与`git diff --check`通过；未运行全仓测试。
- **2026-10-09历史暂停位置**：当时按用户要求未开始M4汇总验收单元测试，下列命令为当时恢复入口；该暂停已被2026-10-10用户“完成M4阶段所有测试”取代，实际结果及当前恢复位置见§3.8。早期替身证据不能推定真实环境通过。

```bash
TIKTOKEN_CACHE_DIR=/private/tmp/lxm-m3-tiktoken PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_memory_query_rewrite.py tests/test_memory_hybrid_candidates.py tests/test_memory_rerank.py tests/test_memory_retrieval_pipeline.py tests/test_memory_prompt_selection.py tests/test_memory_model_handoff.py tests/test_memory_token_budget.py tests/test_memory_vector_components.py tests/test_memory_use_guard.py tests/test_memory_use_guard_review.py tests/test_memory_mutation_service.py tests/test_query_rewrite_service.py tests/test_prompt_builder.py tests/test_chat_prompt_view.py -q --tb=short
```

### 3.8 M4全部本阶段测试与交接（2026-10-10）

- USER_DECISION：用户明确恢复并要求完成M4所有测试；继承M3已接受与009→013范围，本轮不进入M5。前次暂停已解除，不把正式质量/完整旧Test矩阵/业务接线提前纳入M4。
- DONE：009～013本M负责的分项均有输入/预期/实际证据；013改为DONE，当前10/22。M4详细证据（本地留存，未随本次提交；原引用：`execution/evidence/M4-检索与Prompt内核核验-2026-10-10.md`）记录分项映射、命令、版本、失败收敛、隔离和延期边界；云原始JSON（本地留存，未随本次提交；原引用：`execution/evidence/M4-隔离云串联运行-2026-10-10.json`）不含凭据或完整Prompt/回复。
- 最终局部/回归：18模块同进程组合196 passed / 6.46s，无skip；覆盖新内核、use guard/mutation/token、旧rewrite/Prompt/预览、旧多路/Step8及observer。真实SQL/socket 5 passed / 11.13s，唯一deselect云项单独运行1 passed / 55.75s；Chrome1 passed / 4.85s覆盖Step3/Step8两页。各组彼此不同用例，不与早期重复组合相加；未跑全仓。
- 高风险证据：实际asyncio原截止同时保留已成功路门槛、未完重排融合、慢查询取消与失败空路，截止后无新调用；query/单篇/全请求超限零HTTP零重试；四路4/5/6/7独立上限均触发且保持前缀和角色轮转。真实httpcore/socket部分body发送后peer断连、sender取消先join/close再SQL停止回执：可确认aborted允许变更，不可确认unknown持续阻塞/不TTL释放/不重发；另覆盖旧owner迟到及已交付回执丢失。
- 云分项：独立真实rewrite传输/解析＋固定四路Query的真实Embedding→source/index→dense/BM25→SQL→rerank→官方计数→真实模型handoff，不能标为真实rewrite质量或业务E2E。20合成样本首次索引完成，各路5最终20；完整渲染542 tokens、昵称60 tokens，硬预算反例阻断。报告明确基快照、合成fixture ID及参数覆盖；只在自有新分区写入，删除后GET确认cleanup=confirmed。
- 复核：只读二审发现4项证据缺口，补齐真实截止、部分body断连、rerank超限和数量上限；窄复核全部关闭、无新增确定阻塞。首轮旧Prompt词表缓存缺失只恢复公共词表；云准备按next_attempt_at等候、rewrite改用定稿20秒调用预算，未弱化断言或更改实现。18个Python目标编译、diff/manifest/链接及§3外摘要核对通过。
- 契约/环境：M4临时契约候选（本地留存，未随本次提交；原引用：`execution/contract-drafts/M4-临时契约.md`）已汇总并登记manifest，正式整合仍NOT_STARTED。启动原Docker Desktop恢复测试MySQL；每例随机库创建/实际迁移/删除，仅本次自有云分区清理；未修改env/compose、业务库、旧数据或部署新代码。本轮新增/增强测试及必要交接记录，未新增业务功能。
- GATE_EVIDENCE_READY：009～013本M分项、45+45、一次重试、有效性与硬预算证据齐备，提交M4闸门。M4状态保持IN_PROGRESS待判定，不由执行器标VERIFIED；恢复点为核对本证据及临时契约并判定M4，未进入006/M5。019完整旧Test接口矩阵、021同集真实质量性能、022实际切换仍待原阶段；无新增需用户补配置事项。

### 3.9 M4闸门判定与M5执行边界（2026-10-10）

- USER_DECISION：完成M4闸门验收，通过后继续M5，在M5收尾验收单元测试前暂停。该授权包含阶段推进及M5必要局部验证，不包含运行实际S15清理、切换新链或部署。
- M4 GATE PASS_WITH_RISKS / VERIFIED：接收§3.8的GATE_EVIDENCE_READY；逐项核对计划M4的009协议/降级与预览、010有效候选/双通道、011完整重排/非法映射/超限/RRF、012共享截止/一次重试/迟到收口、013数量/整条/昵称计数/硬预算/使用保护/旧适配及页面，全部有对应输入、预期、实际输出。196组合、5真实SQL/socket、1真实云分项、Chrome两页及四项复核缺口关闭证据有效，源码前提无变化，本轮不重复收费调用或相同测试。M4临时契约已收齐；非阻断边界仍为021语义质量、019完整旧Test矩阵及后续业务接线/启用。
- M5顺序与依赖核对：006和007均消费已验收005的持久源操作/有限恢复；008依赖001完整来源方案及006/007全部writer接线。006→007共用writer与回执接口，007→008共享源身份与fence，故按原顺序而不并行修改；006/007/008各自任务与测试口径无冲突。仅运行各STEP必要局部验证；M5最终跨STEP汇总验收单测尚不运行。
- 工作区沿用现有未提交M3/M4源码及用户改动；不新建分叉进度、不提交。按subagent-driven-development委派单STEP实施及只读复核，任务临时材料放/private/tmp，唯一持久进度仍为本§3。M4闸门判定依据用户本次明确授权及已确认清单，不要求用户再次确认阶段推进。

### 3.10 M5局部执行与恢复（2026-10-10）

- STEP-006 DONE：新增冻结新目标的`MemoryBusinessWriter`，接文字四类、语音两类及legacy `mem_*`入口；源确认/索引维护分态，原operation核实未知，voice ready snapshot保留原无凭据write_context，trace不冒充索引完成。原11字段、Step5输入、关系标量、同Key覆盖、text/voice及默认unknown来源、20秒外层等待保持。实际SQLite intent/trace/worker及包装层执行，模型/embedding/远端为受控替身，未新增真实MySQL或云模型证据。
- 006必要局部命令：`PYTHONPATH=. TIKTOKEN_CACHE_DIR=/private/tmp/lxm-m3-tiktoken .venv-step001/bin/python -m pytest -q tests/test_memory_write_integration.py tests/test_step6_vector_upsert.py tests/test_memory_write_source.py tests/test_realtime_voice_step028_memory.py tests/test_realtime_voice_step028_jobs.py tests/test_realtime_voice_step029_compensation.py tests/test_realtime_voice_step028_metrics.py tests/test_step016_step6_orchestrator.py tests/test_memory_mutation_service.py tests/test_memory_index_worker.py` → **139 passed / 6.90s**；源码编译及diff检查通过。独立复核发现并关闭唯一P1：MemoryService两条旧入口已改用冻结writer编码器，实际入口断言旧embedding零调用、原writer透传及迟到epoch拒绝；未运行M5汇总。
- 接口交接：`get_memory_writer(expected_context=...)`要求服务器明确`MEMORY_RUNTIME_ENVIRONMENT_ID`及有效fence，缺失失败关闭；不会改.env、激活或回落旧库。008仍须在关系写事务及旧SQL/voice任务入口加入S15守卫，不能由向量拒写推断画像/Future安全；019负责AC18-b新文字召回串联；实际目标环境配置/清理/启用归022及既定闸门。006增量及只读复核临时材料位于`/private/tmp/lxm-m5/step-006-*`。
- 007回归发现既有静态兼容项：`test_step024_observer_domain_read_roles.py::test_all_domain_routes_use_read_or_write_role_collection`要求所有GET在装饰器声明固定角色数组，而M3既有`vector_config.get_publication`按原`source_entry`动态使用S/T/V或S/A/V。该源码不属007增量；已核对动态授权仍在，未弱化断言或扩大角色。记录原失败，019统一收口静态检查适配；007仍须通过本步实际角色/API矩阵，不用此说明豁免权限验收。
- STEP-007 DONE：四类既有源CRUD与自有回执GET、持久父子批删、三页source/index分态和session恢复已交付；可选规范UUIDv7、actor/当前角色、历史成功与当前代次、先持久后外调保持。首轮139局部/真实随机MySQL2/Chrome三页1项通过；独立审查发现三项并已集中修复、窄复核全部关闭：旧GET/POST/观察timer绑定原ID和序号；列表兼容严格可信baseline及仅索引未知的已确认源，legacy只读；原权限列表GET提供server_time，提交前校时及同source busy保护，校时失败不分配ID。最终66定向、166必要局部回归（16条既有JWT warnings）和真实Chrome2项通过；MySQL2项前提未变复用，非本轮重跑。API/SQLite及浏览器HTTP为受控替身，MySQL仅随机自有库。首轮浏览器元数据误复制已校正为1 passed/3.72s，修复后2 passed/5.06s分别留存。

- M5局部证据（本地留存，未随本次提交；原引用：`execution/evidence/M5-写入与回填局部证据-2026-10-10.md`）保留006/007输入、预期、命令和真实/模拟边界。007证据恢复：`/private/tmp/lxm-m5/step-007-{report,review}.md`、`step-007-verification.json`、`step-007-files.json`；总增量SHA256 `4e1787a59c8b6e272beca656caf462d1613abffb1ea34c402e812cf045af55b8`，修复增量`ab4fbfe14d4c97677b3bd1b904d735879fdf77d1c24721228198c50ed907bb08`。源/页面实际增量同步M5临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M5-临时契约.md`）。008已按顺序交新代理实施，涵盖完整来源/持久DTO及S15全部矩阵、迟到守卫、隔离演练；本阶段不执行实际业务S15，M5最终汇总验收单元测试仍未运行。
- 008实施中发现全局SQL封写还需受限原run排空通道，否则已发操作不能记录确定收口、T0无法成立。实现裁定：CAS/摘要/调用者自报或签名本身均不证明外部完成；不新增独立结算器服务或密钥体系，复用原source tag/代次/hash远端核实、原transport完成/停止事实及voice最终服务端关闭/flush事实，缺证据或重启丢失证据保持unknown/维护。此项尚在实现验证，不作为已通过证据。
- 008首轮局部证据已取得：603条SQLite持久回填/中断/DTO，专项35 passed+2资源skip、直接影响356 passed、真实pre-v9d MySQL非空保留2 passed、自有Redis/容器/临时文件5 passed；各组重叠，不能相加。独立复核进行中：自查legacy删除仍绕过原epoch；复核确认实际DashVector SDK stats对象适配、已知backend挂载/完整配置与容器内日志适配、known-unsent voice jobs原终态排空存在缺口。均属于008工具可执行边界，集中修复前保持IN_PROGRESS，不将其改列022延期。M5收尾汇总验收单测仍未运行。
- 008二次冻结自查修复：legacy改持久tombstone后再软删SQL，新增6例和相关局部组合60 passed；但独立复核又复现“首次SQL快照后、读取目录generation前”在线更新会被旧请求误删，不能按这60项宣称并发闭合。集中复核另确认S15 receipt清空后007 GET会把历史confirmed batch重算failed，以及actual回填任意64hex基线摘要缺少可信reset/full-manifest关联。六项均需本STEP修复，复现与集中报告置`/private/tmp/lxm-m5/step-008-review*`；不改变原需求、不以模拟通过替代真实SDK或目标配置适配。
- 008集中修复轮1已启动。Ruling：actual完整来源以已有reset run/item的完成事实、环境/target/epoch及全partition清空范围核验，不新增manifest表/服务或外部签名系统；无法核验的actual full_manifest拒绝，isolated可接受明确合成证明。依据001已确认的新库空基线方案；代价是未经可信reset的实际目录不能被本工具宣称全量完成，不能为“可运行”接受任意摘要。Docker受保护重建配置仅离线0700/0600材料，SQL和报告只存摘要，演练只用自有容器及合成env。R3已知未发送任务在T0前按原终态协议收敛后再采保留/10指标基线，unknown和既有终态不得强改。
- 008修复轮1局部结果：165 passed+2资源skip / 49.16s、补充baseline/CLI 14 passed / 10.28s、真实自有资源7 passed / 1.50s、真实MySQL2 passed / 5.28s，53个Python增量编译通过。总diff `e7c1316953e37ab5cad3bd6f416accd96a7c0d72be3bfbfca5eb27a79eede2f9`。窄复核又以真实005 claim→prepare及真实batch→原child readback复现R3两项遗漏：源confirmed但index尚未发送的意图、全部child已确定但父unknown的派生回执仍堵住T0。第二轮仅修这两条收敛路径；未把未决外部请求强制释放，也未运行M5最终汇总。
- 008第二轮：原两反例RED2→GREEN2，直接影响131 passed / 19.77s、CLI1项及编译通过；R1/R2/R4/R5/R6和R3b父批次均已独立关闭。R3a正常running路径通过，但复核真实005读源失败进入retry_wait时仍保留未dispatch的prepared intent、维护排空却跳过，新增1 failed反例。第三轮仅修此可达未发送状态，保持原gen/hash/task/attempt绑定、source confirmed及已dispatch/unknown保护，不以TTL判断外部安全；源码其余部分冻结。

- 008第三轮窄修复：原retry_wait反例RED1→GREEN1，prepared/dispatched索引定向5 passed、13 deselected / 2.81s，53文件编译通过；真实005 running/retry_wait且lease仍有效的prepared原意图均按强绑定未发送证明排空，dispatching/unknown负例保持。独立复核R1～R6全部关闭，总diff SHA256 `c89223fa1130e5d9f2f3a0f8133d1ef3ec7bd31eb328cd64e9c80467203e21a2`，文件清单`43594f4813346aec0e88cddb422f1e64b8722c750649f2284b56e5a81e67a5ac`。
- M5整体只读复核发现一条新集成P1：008的voice `_write_atom`在外层trace事务通过`lock_call`持有运行fence，再等待006 writer内层独立source事务获取同一fence，active环境会自阻塞。实际文件SQLite/独立连接对照：未设置环境1 passed，合法active环境1 failed且零源写/trace；原内存StaticPool测试未覆盖。按已确认语义修正事务边界，提交trace前仍须同事务校验原epoch/lease/fence；只运行这条缺陷及直接影响验证，不启动M5最终汇总。报告与复现位于`/private/tmp/lxm-m5/final-review*`、`test_final_voice_fence_review.py`。

- 整体复核完整报告仅1项新P1；其余未判事项按原分工保留：017/018持久DTO查询与页面、019 AC18-b和旧静态权限适配、021真实质量、022实际S15/全实例封板/旧目标退役，不提前纳入或宣称完成。sort_seq旧历史恢复未建立本次新链可达失败前提，不列确定缺陷；未扩大成全仓潜在风险审计。整体复核修复前报告SHA256 `f67e09e905b777ed8c5ff250ea89914da02fdce3fe3e6820b8ed8660d3d3aad9`，只对本修复增量再做一次窄复核。

- 整体复核修复wave进行中：原自锁反例RED1/1→GREEN2；首次拆事务后active独立连接及迟到trace局部验证通过。root按现行realtime-voice/data.md“删除先锁记忆任务、防迟到写回”核对更早窗口，实施者确认第一段commit后、source prepare/dispatch前完成删除仍能发送新源写；首个修复冻结仅候选。当前同一wave补原call/job/token发送许可与真实stage_deletion_fence并发反例，不能仅凭后二次trace检查结算。最终一次窄复核尚未派发，未启动M5汇总。

- 整体复核同一wave修复已冻结：用call gate→doc gate→短SQL事务保持原删除等待顺序，实际retention双向反例RED1/1→GREEN2，最后直接影响**95 passed / 6.91s**，55个008 Python编译通过。MySQL新gate生命周期仅模拟验证，未冒称真实锁演练；源码/日志SHA匹配。最终M5增量77路径，总diff `9bd3357fa1a844effef0bb998ce994f64775cac710bbb6dac293af72141e13cf`；最小4路径修复及完整证据见M5局部证据（本地留存，未随本次提交；原引用：`execution/evidence/M5-写入与回填局部证据-2026-10-10.md`），正在最后一次只读窄复核。上述95项仅语音修复及直接影响，不是M5最终汇总验收。

- STEP-008 DONE：六项独立复核及整体集成P1均已关闭。最后ONE窄复核确认事务释放、原epoch重查、call→doc→SQL锁序、唯一retention staging入口、删除先后两方向、原operation恢复和取消/busy释放均符合本轮范围，无新增确定Critical/Important项；未重复运行测试。报告`/private/tmp/lxm-m5/final-fix-review.md` SHA256 `871c956f664b2adc1273b6599977bbd73e562b2b499346f68836b2e5d3b77aa1`。最终77路径及日志摘要核对、文档链接/manifest和§3外不变检查通过；局部证据按真实/替身及历史/本轮分别保留。
- **历史暂停与恢复点（已由§3.11新授权解除）**：当时按用户明确要求停在**M5收尾汇总验收单元测试开始前**。006～008本步实施及必要局部验证/复核完成，累计13/22；M5仍IN_PROGRESS，未运行最终跨STEP汇总验收、未提交GATE_EVIDENCE_READY、未判M5闸门、未进入M6。恢复时先核本§3、M5证据（本地留存，未随本次提交；原引用：`execution/evidence/M5-写入与回填局部证据-2026-10-10.md`）、临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M5-临时契约.md`）及最终77路径SHA；再按计划M5原分项运行收尾汇总单元验收，结合前提仍成立的MySQL/页面/资源证据判闸门，不重复无变化的收费调用。019既有角色AST适配、017/018页面、021真实质量、022实际业务S15与启用仍按原分工；本轮未部署、未改.env、未执行业务清理或提交代码。临时证据与603夹具保留供续接，无需用户补配置。

### 3.11 M5收尾验收恢复（2026-10-10）

- USER_DECISION：用户要求完成M5阶段所有测试，补齐真实MySQL新锁机制验证；解除§3.10单元验收前暂停。范围保持006～008及其直接影响，不提前执行M6、实际业务S15或部署；完成后提交M5 GATE_EVIDENCE_READY，闸门仍待判定。
- 恢复前77路径源码与前轮冻结after SHA一致。已启动40模块/节点跨STEP汇总（临时清单及原始日志`/private/tmp/lxm-m5-validation-20261010/aggregate-selection.json`、`aggregate.txt`），另运行真实隔离资源与三页Chrome；真实MySQL新锁由独立验证代理补可重复用例，仅自有随机测试库/容器。原测试预期仍依据需求/接口，失败不弱化有效断言。
- 汇总首轮2 failed/678 passed/2 skipped，原因是后台CRUD与观察者页面导入的认证测试在收集阶段全局注入空scheduler，令两语音scheduler任务ImportError；两项单跑通过，两个最小组合均已原样RED→GREEN。仅移除`test_admin_character_knowledge.py`、`test_admin_memory_write_operations.py`、`test_admin_auth.py`中的三处全局替身，业务断言与生产源码不变。修复后同一40模块/节点汇总**680 passed、2 skipped / 83.26s，退出0**；2 skip为资源opt-in用例，另组实际验证通过；认证模块补验**72 passed / 35.33s**。既有JWT短密钥警告保留，未改全局配置。
- 本轮独立实测：既有MySQL后台写入/清理迁移**4 passed / 13.05s**；新`test_memory_voice_fence_mysql.py` **14 passed / 41.77s＋新增1 passed / 21.53s**；真实Redis/Docker/临时文件**7 passed / 1.60s**；三页Chrome**2 passed / 5.85s**。全部退出0，分组各记不跨组累加。MySQL8.0.46实际独立连接/active fence、call/doc提交后持锁、池归还/取消释放、retention两种先后、迟到epoch/maintenance、原operation/快照恢复均通过；业务source20秒和call gate真实GET_LOCK(...,20)超时分别实测，后者busy未误释放原owner。SQL/锁/包装层真实，模型/embedding/向量远端与页面HTTP为受控替身。
- 已核对所有本轮新锁测试随机库删除与自有gate无占用；新增第15项前后原14项/helpers字节相同，14整组及1定向证据分别保留。原77路径仅两Admin测试变化，生产源码冻结不变；加认证测试与新MySQL模块形成79路径当前清单，本轮4个测试模块编译通过。603生产DTO夹具SHA保持不变，沿用完整遍历/中断恢复证据。原始日志及before/after/清理JSON见`/private/tmp/lxm-m5-validation-20261010/`，说明、命令与摘要写入原M5证据（本地留存，未随本次提交；原引用：`execution/evidence/M5-写入与回填局部证据-2026-10-10.md`），临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M5-临时契约.md`）仅补验证边界。
- **GATE_EVIDENCE_READY（M5）**：006～008局部实施/复核与本轮收尾测试证据齐全，累计13/22；M5维持IN_PROGRESS，恢复位置为M5闸门核对/判定，未进入M6。019旧静态角色AST适配及AC18-b、017/018查询页面、021真实质量、022实际业务S15/全实例封板/配置启用仍按原分工。未部署、未改.env/业务库、未执行实际清理或提交代码；无需用户补配置。

### 3.12 M5闸门判定与M6本轮边界（2026-10-10）

- USER_DECISION：先按原计划核对并判定M5；通过后014→015各自完整实施/验证/记录，014全部原完成条件满足后才开始015。停在016开始前，等待用户手动换模型；不启动016、M6汇总、M7，不部署/切换新链。前提未变证据复用；确定缺陷或必要证据缺失阻塞M5时停止，不带病进入M6。
- M5闸门PASS_WITH_RISKS/VERIFIED：当前79路径与`/private/tmp/lxm-m5-validation-20261010/final-source-inventory.json`全部一致，root日志SHA全部匹配。006实际文字/语音包装层、源/索引分态、20秒/trace与原operation恢复；007四类CRUD/自有回执/持久批删/三页；008超cap603持久DTO/完整遍历/中断恢复、清理保留及资源演练均有原输入—预期—实际证据；独立复核确定问题已关闭。最终680汇总、真实MySQL新锁15及既有4、资源7、Chrome2、认证72均按原环境/替身边界接收，本轮不重复运行。原完成标志的进度/契约回传与未越界要求满足，接收M5证据（本地留存，未随本次提交；原引用：`execution/evidence/M5-写入与回填局部证据-2026-10-10.md`）及临时契约。
- 保留风险/边界：模型/embedding/向量远端受控替身不冒称真实质量；019既有AST权限适配/AC18-b、017/018查询页面、021真实质量、022实际S15与启用仍属原阶段，无新增M5阻塞。正式契约整合NOT_STARTED。
- 014预检：前置002提交协议及012/013检索/最终交模已验证；014生产实际入口/持久事务/身份及后台投影由本步承担，015消费其提交仲裁但仍以自身Future接受时间定原deadline，两步依赖一致。014/015均不实施016同步UI；按用户既定范围复用当前dirty工作区，增量以每步开始前源码为基线，不覆盖用户或M3～M5变更。
- 实施/复核采用每步一个实施代理、完成后独立窄复核；不并行两个实施者。唯一进度继续本§3，不另建技能ledger；临时brief/before/diff/日志置`/private/tmp/lxm-m6-20261010/`，实际契约增量沿原execution机制交接。当前014 IN_PROGRESS：23文件实施冻结，99项完整验收、64项直接影响及scanner新准入恢复窄修21项均通过；组有重叠不相加。已交独立窄复核，尚未结算，015/016 NOT_STARTED。实际输入/预期/结果见M6局部证据（本地留存，未随本次提交；原引用：`execution/evidence/M6-文字与Future局部证据-2026-10-10.md`），接口增量见M6临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M6-临时契约.md`）；临时报告`014-report.md`、root差异`014-diff.patch`。
- 014独立窄复核发现2项Important：active fence锁前RR快照令同ID并发唯一键报错/不同ID漏承接；已确认commit后附加回读失败误返unverified并跳过成功副作用。独立MySQL定向2＋1项RED，报告`014-review.md`；当前同一wave修复锁后current-read和成功ACK分支，并补原SSE有效断言及本步清理批次饥饿定向项。014保持IN_PROGRESS，未结算/未开始015；未受影响证据复用。

- 014修复窄复核：原RR并发/ORM缓存、清理饥饿和SSE断言均Closed；99/64/21复用未变部分，修复8项及最终36项通过。原成功副作用Important仍有ACK后观察跨D取消分支（实际worker RED1项），进入同问题微修，尚未DONE/未进入015；不重开已关闭项。

### 3.13 M6逐步实施与016前停止（2026-10-10）

- STEP-014 DONE：依002/012/013已验证产物实现实际H5/Open入口→同次冻结检索/Prompt/保护→SQL终态；180秒准入起固定、身份原子幂等/承接、lease owner、未知提交、1～4 pending故障恢复、两只读GET和Admin分页后同源投影均有原输入/预期/输出证据。23文件增量保留原dirty改动；迁移仅随机隔离MySQL运行，未改真实环境。
- 014证据/复核：原99完整验收（零skip）、64直接影响、scanner窄修21按未变部分复用；独立反证发现RR快照与成功ACK后效果遗漏，四文件修复8反例及最终36通过，取消遗漏微修最终10通过。全部原Important/Minor与SSE断言已Closed，最后`014-ack-fix-review.md` Spec符合/Quality Approved；各组重叠不相加、不冒称全为最后版本一次运行。真实独立连接/active fence/事务/锁及actual routes，外部模型/safety/部分时钟受控；H5/Open认证fixture替代、AdminJWT真实；页面019、实云质量、部署与完整异步历史重放均不在本结论。
- 014交接：详见M6局部证据（本地留存，未随本次提交；原引用：`execution/evidence/M6-文字与Future局部证据-2026-10-10.md`）和实际临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M6-临时契约.md`）。root23路径SHA匹配，最终清单`014-files.json` SHA `e349732a6bc0c110e6f9eecc681d679d461a77d1a5ca012f1bccd21dc58ec598`；自有测试库/连接清理0。ACK明确/未知权威成功后，在任何观测/退出await前同步注册两原效果；未知未证实不通知。请求编码、GET/SSE DTO/十进制修订号、原/有效代及D/状态fixtures交016/019。
- 014完成时的依赖与恢复：014全部原完成条件和必要契约/进度已回传，累计14/22。按本轮既定授权进入015独立实施/验证，临时brief/before/report沿`/private/tmp/lxm-m6-20261010/015-*`；016 NOT_STARTED，M6仍IN_PROGRESS，未运行M6汇总或M7，未部署/切链。正式契约整合NOT_STARTED。
- 015实施交审：18文件冻结；原指定024/023已实跑，基础56通过后仅scanner窄修4通过，直接影响58通过（1条未改旧夹具warning）。真实MySQL独立连接/active fence与Redis自有键证据齐，清理自有库/键均0；尚待独立复核，不提前DONE。原S15 N17清后保留成功审计/解除结果FK例外已接新表，未执行实际清理；完整输入/预期/结果见M6局部证据与`015-report.md`。

- 015首次独立复核Needs fixes：I1未知ACK已确认后结果metadata await跨D漏原效果；I2旧Step8的Step6“无/解析失败”清槽未传原版本，实际误清新Future。真实MySQL1＋2项RED，报告`015-review.md`；同wave修复成功通知上下文及Snapshot→标量条件清理，未启动016/未提前DONE。

- STEP-015 DONE：原012/013/014前置齐后独立完成正常/兜底同消费仲裁、原180秒、结构化unknown、原正常/兜底效果集合与防重、所有本次清槽身份匹配/新Future保留；S15 N16/N17新表直接兼容按既定例外实现。最终19文件，新增Step6Snapshot可选captured Slot仅服务本次条件清理，普通主链默认语义保持。
- 015有效证据：基础56（含原指定024 21项、023 12项）＋最后scanner定向4、直接影响58按未变部分复用；独立反证I1 unknown确证后await漏效果/I2实际Step6两分支误清新槽经同wave修复，定向24＋2及普通主链兼容12均通过。`015-fix-review.md` I1/I2 Closed、Spec/Quality Approved，无新增阻塞；原RED和分段版本保留，不累加各组为一次通过数。真实独立MySQL/active fence和实际Redis Lua，provider/部分时钟受控；旧夹具warning及失快照历史异步恢复限制如实保留。
- 最终核对：两步实际接口已写M6临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M6-临时契约.md`），需求→输入/预期/结果及日志/SHA见M6局部证据（本地留存，未随本次提交；原引用：`execution/evidence/M6-文字与Future局部证据-2026-10-10.md`）。root最终40路径组合清单`/private/tmp/lxm-m6-20261010/final-source-inventory.json` SHA `b50333f7c00148fa5deccdc7785fec38abbb29f2ee77f636a82d2050ee3f07dd`全部匹配；共享路径按015最终版本覆盖014时点版本，其余014未变。自有随机DB/Redis测试键已清理0；原603夹具与前步证据保留。
- **本轮停止点**：累计15/22，014与015分别满足原完成条件并DONE；016 NOT_STARTED，M6仍IN_PROGRESS，未启动016/M6汇总/M7，未部署/改env/切换新链。等待用户手动换模型后明确恢复，不自动执行下一阶段。无需新增用户决定，正式契约整合NOT_STARTED。
- **016恢复接口**：先核本§3与M6实际契约/证据及最终40路径SHA；消费H5原client_message_id/client_resend_id、`b64.`规范路径编码、两GET的SubmissionStatus、SSE meta/done身份与十进制revision、原accepted与effective generation/D区别及server can_resend（10110/未知不可重发）。状态夹具`014-status-fixtures.json`已保留；刷新/乱序/本地最小身份保存由016实施，本轮未做。015的Result/consume_id/slot版本与可选future_clear_slot交后续诊断/兼容消费者，不把普通bool当成功。016原依赖014已满足，但必须等用户恢复。


### 3.14 M6恢复016与汇总验收（2026-10-10）

- USER_DECISION：沿同一工作区/权威来源恢复016，原完成条件满足后做M6汇总；仅提交GATE_EVIDENCE_READY，停M6闸门判定前，不进入M7/部署/切链。014/015后端事务、并发、截止、仲裁或终态确定缺陷只保存最小复现并暂停受影响依赖，等待用户切回Astra；016局部问题可定向修复。
- 前置复用：40路径最终组合清单当前SHA全部匹配，014/015原完成条件及独立复核结论继续有效，不重复实施/全组重跑或收费调用。016 IN_PROGRESS，汇总验收待其独立完成；唯一进度仍本§3。临时016 baseline/brief/report与浏览器原始证据沿原目录保存。
- 016必要配置接线：002规定client margin≥server margin，固定前端20秒无法覆盖服务端允许30秒；增加认证只读client-timing投影，校验前端参数并消费TIMING同源值，不改014/015业务语义。实际本地Nginx只读核对300秒idle/75秒connect与SSE缓冲关闭；未部署/重载。
- 016刷新失败行兼容接线：timeline十字段无can_resend且终态本地ID须清理，增加认证只读resend-eligibility复用原资格谓词，保留timeline与重发业务；客户端不从failed_*推定资格。必要只读投影/等价性与账号/额度矩阵验收，不改014终态语义。

- 016首次交审9文件：Chrome23场景（14显式POST/max2）、配置/静态29、资格真实MySQL3、调度node通过；未提前DONE。独立复核另复现首次配置503后无法回页恢复、旧账号SSE收尾提示污染新账号、非法参数未启动拒绝；均016局部接线，保存/tmp原复现并进入单一修复wave，014/015业务语义无新缺陷。

- 016修复wave1/5：三项Important全部Closed，Spec/Quality PASS，无剩余项；窄复核`016-fix-review.md` SHA `13fb77434aa6e1321c92e30b0f577d0162b20fd384611dcc0f2951dfdd4ce143`。原23/29/SQL3/node与定向15/6证据共同满足016全部原完成条件，实际增量已同步M6临时契约及局部证据，STEP-016 DONE，累计16/22。未将替身/虚拟clock推定真实业务运行或部署；014/015事务前提不变。现在仅补M6当前H5→实际014路由→隔离SQL→DOM汇总链，尚未提交GATE_EVIDENCE_READY。

- 汇总新确定缺陷：实际默认timeline(include_calls=True)在`timeline_read_service.py:99`把既定两个过滤谓词组成tuple而500，影响016回页历史。三条实际SQL/DOM链已各通过，但临时include_calls=False适配只证明未受影响文字链，不能据此交READY。Ruling：仅修既定谓词AND连接，保留所有S15/删除/权限/分页过滤，无新增行为/关键取舍；代价为需补默认历史链直接影响回归。016暂恢复IN_PROGRESS；原014/015写语义无变化，不触发Astra语义修复边界。原负例、预期实际及精确修复另存原/tmp，修后只补受影响验证。

- 默认history修复闭环：实际默认GET RED1→GREEN3/5.49s，独立MySQL正常文字、各voice清理条件/owner/status/null-sort及分页anchor同scope、4表前后逐行不变；仅既定谓词逗号→AND。`016-timeline-review.md` SHA `c850ba10ff85502099f5e7ce19d0e2ff66eccae369ff7eae0bda830966146468`确认Spec/Quality PASS、缺陷Closed；包装报告hash已同步，无源码/测试改动。默认Chrome聚合3场景/14.93s通过，迟到旧GET消费另1项/8.98s通过，均正常include_calls=True并刷新后精确恢复SQL身份、无新增POST。016恢复DONE，累计16/22；M6证据冻结与接线质量复核中，未交READY或判闸门。

- M6限定汇总复核：`m6-summary-review.md` SHA `89fb3cf06e6edf9c499df3bb1f16416780170cf30bcfed4994f9ae3307f5b515`，Evidence completeness/Scoped quality PASS，无未关闭Critical/Important/Minor；51源、2/tmp夹具及153证据全匹配。当前三链原生Chrome→实际14HTTP/独立MySQL→DOM/default reload，原GET确实json消费与时序断言；014/015原真实事务/锁/Redis/Future及016原版本/窗口长时序前提未变复用，未重复收费调用。实际值/替身/skip/旧失败/清理边界逐项取M6证据及最终聚合报告，不合并成一组总数。
- **GATE_EVIDENCE_READY（M6）**：014～016全部原分项与完成条件、跨STEP接线和关键运行证据齐全，实际契约已汇总M6临时契约，累计16/22；M6保持IN_PROGRESS，**未判定闸门**。恢复先读本§3.14、M6局部证据/临时契约，核最终`m6-final-source-inventory.json`（51路径，SHA `353c8f92ac8b447280d94c8ae2536e43e4f2211943564e47e0c0a4a3ad76525a`）、`016-aggregate-report.md`及153证据外置索引和`m6-summary-review.md`，再由用户手动换模型按原M6清单判定；未自动进入M7。
- **本轮停止/限制**：默认历史500及配置恢复/账号退出/启动拒绝等016发现已修复并独立闭环，无待Astra后端语义缺陷。已运行容器仍旧120秒链，新源码未部署/改env/切换；网关300秒为idle。原23浏览器长时序使用模拟clock，最终聚合用实际wall/独立MySQL、provider/auth/部分阶段受控；未冒充实云质量、JWT签名、生产逐chunk或完整lifespan。正式契约整合NOT_STARTED，017～022按原范围，M7/部署均未启动；保留用户改动和原冻结证据，无需新增用户决定。等待手动换模型，到此结束本轮。

### 3.15 M6最终闸门判定与停止（2026-10-11）

- USER_DECISION：本轮仅审核014～016原完成条件、最终实现及已提交证据；授权判定M6并完成阶段契约交接，判定后停止，不进入M7、不部署/切链。前提未变结果直接复用，无业务源码修改、测试重跑或收费调用。
- **M6闸门PASS_WITH_RISKS / VERIFIED**：接收§3.14的GATE_EVIDENCE_READY；按里程碑M6原清单核对，014～016各自分项/完成标志及汇总接线证据齐全，无未关闭确定缺陷、必要证据缺口或实际契约遗漏。累计16/22，M7/M8仍NOT_STARTED；下列限制沿原分工保留，不增改验收条件。
- 有效版本：重新核算`/private/tmp/lxm-m6-20261010/m6-final-source-inventory.json`的51路径全部匹配，清单SHA `353c8f92ac8b447280d94c8ae2536e43e4f2211943564e47e0c0a4a3ad76525a`；153项聚合证据索引全部匹配，索引SHA `35ee97ed16f011219829aaa3829a1e359c7877fe3bf3c2b267335cab4259a825`。另核014/015最终日志/复核/状态夹具摘要，均一致；共享router/lifecycle仅016已验证只读增量，014/015事务及效果前提有效。服务端版本`chat-lifecycle-v1:142ded17eeda1569`、客户端`chat-client-v1:f64340198e97ef04`。

| 原完成条件 | 最终实现与接收证据 | 判定 |
|---|---|---|
| 014：实际文字/Open新检索Prompt；身份/入队原子性；固定180秒、唯一终态、未知提交、owner；少量pending恢复、纯读状态/Admin投影 | 真实隔离MySQL迁移/独立连接/current read/CAS/锁/回滚及实际入口；原99/64/21未变部分、修复8/36及最终ACK10分段复用，最终复核全部Closed；正常/未知ACK成功通知在可取消收尾前登记 | 全部满足 |
| 015：正常及独立兜底同次保护、固定180秒、成功后收尾、原效果防重、所有清槽匹配及新Future保护 | 原024/023实际运行与MySQL56、scanner4、直接58、修复24/2/普通主链12；真实Redis Lua原子防重证据未变，实际Step6可选捕获Slot透传/CAS；I1/I2 Closed | 全部满足 |
| 016：预存最小身份、meta前断线核实、有限持续同步、单在途/单调版本/去重、历史独立及账号隔离 | 真实Chrome23场景＋修复6；配置29/启动15、node、资格SQL3及默认历史修复SQL3；原ID/窗口不续期、server can_resend与完整SSE余量分离，原全部发现Closed | 全部满足 |
| M6：跨STEP接线、真实事务/锁及浏览器同步 | 默认Chrome→实际FastAPI→独立MySQL→DOM/reload三链3通过；旧GET实际JSON消费补证1通过/2未影响项deselected，非第四场景；最终限定复核Evidence completeness/Scoped quality PASS、未关闭项0 | 汇总满足 |

- 证据界限：以上均为本轮核验后接收的既有结果，重叠组不相加。事务/锁真实且非内存共享连接；1～4 pending进程故障以持久状态模拟。Chrome真实网络/DOM，原长时序使用模拟浏览器clock、汇总三链使用真实墙钟；外部provider/部分认证和末端效果受控，不推定实云质量/生产逐chunk性能或物理180秒等待。跨进程完全丢失历史副作用快照不新增自动重放承诺；无必要验收skip。
- 阶段契约交接：接受M6临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M6-临时契约.md`）中014/015/016实际接口及正式落点，含两migration、SubmissionStatus/SSE/规范ID/十进制revision、Future Result/Slot/clear_slot/effect、client-timing与resend-eligibility。019消费原`014-status-fixtures.json`及角色/分页/legacy边界；正式契约整合仍NOT_STARTED，依计划§7.2留最后阶段，不提前改current契约。
- **停止与恢复**：本轮闸门已判定并结束，无待修复/补证阻塞，不启动M7。后续须用户另行授权；恢复先读本§3.15、M6证据（本地留存，未随本次提交；原引用：`execution/evidence/M6-文字与Future局部证据-2026-10-10.md`）、临时契约和上述最终清单，冻结聚合报告SHA `53730c19409f19f4f1f728975ac953f8fde5fa9654ce95ad264f1ed83e70cba7`、限定复核SHA `89fb3cf06e6edf9c499df3bb1f16416780170cf30bcfed4994f9ae3307f5b515`。019完整兼容/后台页面、021真实质量、022实际S15/切换/回退及正式契约收口未完成；当前容器仍旧链120秒、Nginx300秒idle，M6通过不代表新链上线。未部署、未改env或业务库。

### 3.16 M7恢复预检与018前置阻塞（2026-10-11）

- USER_DECISION：确认M6通过及017全部原条件已满足后，依018→019分别实施/验证，再汇总M7并停闸门判定前；本轮未授权补做017。M6 VERIFIED有效，当前51源码与最终清单SHA `353c8f92ac8b447280d94c8ae2536e43e4f2211943564e47e0c0a4a3ad76525a`全部匹配，无测试重跑。
- **前置未满足**：017明细仍NOT_STARTED、无完成证据；当前Admin路由AST无`/memory-diagnostics`或`/memory-index-maintenance`目标接口，main未注册目标router，模型导出无诊断run。因此无法确认017原完成条件。依据018原前置及里程碑M7单步门禁，018 BLOCKED，019/M7汇总未启动、无READY/闸门判定；未改业务源码或产生契约增量。
- **最小恢复要求**：先独立实施并验证017全部原条件，交回目标API/持久执行与保存分态、共享身份幂等/并发及权限、永久快照/历史保护/有限维护动作证据；AC12须实际014/015消费路径对照，AC11-a须008生成的真实run/items查询及跨页完整性，附最终版本与必要契约。既有共享内核/回填结果可复用，不能用其替代017未实现接口；不以018页面替身跳过后端前置。
- **本轮停止**：累计16/22不变；恢复先读本§3.16、017原任务/完成标志和002后台协议，待017完成交接后重核其有效版本，再恢复018→019/M7汇总。若需本会话补做017，须用户扩大实施范围；当前无独立于该依赖链的其他授权实施项。未进入M8、未部署/改env/执行业务清理，保留原改动。

### 3.17 M7/STEP-017 实施与交接（2026-10-11）

- USER_DECISION：核对M6原闸门；通过后完整实施并验证017，在018前停止；不启动018/019/M7汇总/M8，不部署或执行业务清理。
- M6复用：§3.15已判VERIFIED/PASS_WITH_RISKS，本轮51源码和153证据与原冻结清单全部SHA匹配，原结论有效；未重跑M6。017开发前置002/005/012/013及验收前置008/015（传递014）按原产物继续核对，不以helper/手造JSON替代。
- 本轮起点（现已完成，见下方结算）：沿指定dirty工作区，单实施者完成后独立窄复核；用户手动换模型的阶段停止点保持，不自动推进后续阶段。临时brief/before/日志/报告位于`/private/tmp/lxm-m7-017-20261011/`，唯一进度仍本§3，无新ledger；契约沿原execution交接。
- 前置复核：002五份技术产物与当前PRD均匹配原`STEP-002-design-check-2026-10-09.json`摘要；PRD现行摘要为`f0ba76573516e55b2bb4197450dfaaa2f36e9ec0ae431a0b4cb78a87ab093caa`，STEP头的旧配套摘要属于修订时点，§3.6已记载后续用户截止解释，本轮未改需求。008原603持久SQLite及DTO匹配最新冻结摘要，原run含603唯一items/连续序号1～603、unresolved=0、report_complete=true；API消费使用副本，原证据保留。
- 工程边界判定：017新增诊断表加入既有`create_all`排除集合及S15预留表的定稿终态枚举属于本表落地兼容；只能补本表已确认终态，不改变既有表/状态/清理规则，活动/未知/保护引用仍须保护，并补定向验证。未授权执行S15或修改其他STEP已验收行为。
- 首次交审：28路径（14新增/14修改），63新组零skip、141直接回归、最后维护测试加强16通过（重叠不累加）；root核对28源/before及49证据SHA匹配。本轮证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-017-后端诊断与维护核验-2026-10-11.md`）区分实际MySQL/API/三链接线/008生产记录与远端HTTP/计数/Redis替身。尚未DONE。
- 独立复核`017-review.md`：规格/质量NEEDS_CHANGES，3 Important（删除ACK超时误返回20129、校验淘汰原因API不可达、真实任务缺回填关联）及1 Minor（受保护DELETE拒绝仍can_delete=true）；3条最小反例RED，008关联用原603记录副本核实。已交同实施者一次集中修复，只重测相关范围；补原定任务attempts大清单证据，不重跑未变141组。多回填关联允许在同task详情以`section=backfills`分页，属于原关联读取的017实现细化，不新增写能力/权限；原失败与冻结材料保留。

- fix1闭环：四项独立发现全部关闭，限定6路径修改；10项定向（含4真实MySQL提交超时）、39项Admin回归、最终2项removal投影通过，重叠不累加。原未变共享层141项及三链接线证据继续有效；补齐真实008关联和扩容attempts/多批次1/20/100稳定分页。最终29源码/before与17新增证据SHA均匹配，原008603文件未改。
- 独立窄复核`017-fix1-review.md` Spec/Quality ACCEPT，新增问题0，原I1/I2/I3/M1 Closed；SHA `12dca52be2b02a21dfedc3c64d6afc59825025b85e3c60eb9fa6a67184892771`。最终源码清单`017-fix1-files.json` SHA `11eb426a10d7cc2d4af669ac56ff14cb4bb99cd0c7d2f2e4bf4fc8d70e228d23`；证据清单`017-fix1-evidence-hashes.json` SHA `0809e3523dc1b98127eca7c3974c054196e6b738896e56978a844421262ab56e`。首轮报告/RED保留，完整输入/预期/输出见本轮证据与临时报告§7。
- **STEP-017 DONE，累计17/22**：002/005/012/013开发前置及008/015（传递014）验收前置均满足；原八项任务/全部负责验收及四项完成标志齐全。实际main/OpenAPI/Step8业务装载消费同次对照、13类业务表零变更/零回复Step6、永久快照/分态/幂等/故障、11API/五角色/完整分页/实际维护和008读取有证据，未用模拟外部服务推定真实云模型质量或生产部署。
- 实际增量交接：STEP-017契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-017-契约增量.md`）记录新表/迁移、11接口、S/A写及S/A/V读、执行/保存分态、身份/期限/未知提交、永久快照/保护、候选与attempts/回填关联及items分页；已纳入manifest。正式契约整合仍NOT_STARTED，M7临时汇总尚未创建。
- **本轮停止于018之前**：017前置阻塞解除，018恢复为NOT_STARTED；M7保持IN_PROGRESS，未提交GATE_EVIDENCE_READY、未判M7闸门。后续由用户手动切换模型，先核本§3.17、局部证据/实际契约及最终源码清单，按018原前置核003/007/017，再执行已获授权范围；本轮不启动018/019/M7汇总/M8，不部署/改env/业务清理，保留原dirty改动。

### 3.18 M7/STEP-018→019及汇总恢复（2026-10-11）

- USER_DECISION：沿同工作区和现行PRD/STEP/里程碑，确认M6与017后顺序完整实施018→019，每步独立验收/交接，再补M7原跨STEP汇总，证据齐提交GATE_EVIDENCE_READY并停闸门判定前；不进入M8、部署或业务清理，模型由用户手动切换。
- 前置核对：M6 §3.15 VERIFIED/PASS_WITH_RISKS，017 §3.17 DONE；本轮017最终29源码及17新增证据SHA全部匹配，原完成条件/008真实603与015传递014交接有效。018原003/007输出沿§3.6/3.10及对应局部证据核对，017实际契约和接口消费按最终冻结版本；未机械重跑既有组。当前仍17/22。
- 执行边界：同dirty工作区，改前逐路径before与最终SHA/diff/报告放`/private/tmp/lxm-m7-018019-20261011/`；唯一进度保持本§3，没有新ledger，不改PRD/计划/STEP任务。018先完成实施、真实Chrome逐动作/实际API数据消费和独立规格/质量复核，后进入019；不合批结算。
- 异常边界继承用户本轮要求：M6提交/终态、M5源或并发保护、017权限/幂等/历史保护的核心语义缺陷，保存最小复现/影响/恢复点，暂停受影响部分等待切A，继续不受影响的已授权工作。普通局部缺陷只在既定行为范围内修复并定向回归。
- 原协议核对：002定稿诊断状态GET初始2秒、×1.5至5秒上限，受理+150秒绝对观察截止，离页/登出/终态停止；属于已授权有限只读观察，须由018实施，不与019历史对话禁止轮询串用。客户端按已鉴权server_time校时生成首次UUIDv7，不能用本地时钟偏差改变受理窗；必要DTO补足仅能是普通公开读字段，不触碰017核心语义。
- 局部接口补足（018原002校时责任）：017诊断GET列表为空时无条目server_time，允许仅成功列表data增加顶层UTC server_time，空/非空均可校时；失败不冒时间可信。不新增权限/路由/执行或修改幂等/留存/保护核心语义，属于本轮允许的普通DTO补足。须保留before、相关API及偏差/失败/校时双击证据，增量归018交接；017原验证按未变核心前提复用。
- 018实施已派单一实施者；要求页面与菜单、双状态/身份复用、候选/选入/筛选分页、维护动作/CRUD关联、008→017真实记录、失败/空态/旧响应/安全文本都有输入—预期—实际证据。019尚未启动，M7汇总/READY尚未提交，闸门未判定。
- 018首轮冻结9路径/55证据，root核SHA均匹配；runtime11真实Chrome2 passed/27.91s、未知身份窄组1 passed/4.84s、观察停止窄组1 passed/2.84s、DTO直接后端39 passed/5.11s，完整候选104/008items603/attempts104/run关联103的1/20/100集合沿runtime8有效分项复用。模拟/真实、实现后验收及原失败已明列，未称部署或实云质量。
- 018独立首审Spec/Quality NEEDS_FIX：R018-01离页后晚到POST回执恢复GET，R018-02新执行初始退避未复位2秒，R018-03历史列表本身1/20/100完整集合缺证。前两项真实Chrome窄反例在018-review-narrow-results.json，均属018 UI局部，无M6/M5/017核心缺陷证据。集中fix1修观察生命周期/参数并只补历史分页，其他绿组前提未变直接复用；018仍IN_PROGRESS、019未启动。完整报告018-review.md/018-report.md位于本轮临时目录，不以自审替代独立结算。
- 018 fix1实施者定向验证：生命周期六等待/停止场景、导航返回原执行GET和登出旧回执不重写session；连续两执行严格2000ms起步；105匹配+8干扰SQL历史在1/20/100及默认20、末空页、有效筛选全序列通过。其余大详情分页保持复用，等待fix1冻结与独立窄复核，尚不计DONE。

- **018 fix1独立收口**：R018-01/02/03全ADDRESSED，Spec/Quality ACCEPT、新问题0；018-fix1-review.md SHA `017686318dcb34a774af4bd039ab5ec0af7f0a475b9eecd1d61fdf10f32edb24`。最终9路径清单SHA `b16b32460b42970370072b58f088cb9d7a18b24e03b38ab3177248d510a256d6`，78过程/有效证据清单SHA `67aa7d7c9c9bad7d8396c3fb3ef10cc13de2f7ac7da48c019314bd53b83497ba`；root核对无不明漂移。四路径局部差异/原失败保留，不重扫已绿大详情。
- **STEP-018 DONE，累计18/22**：原七项任务/全部负责分项及四项完成标志齐；实际Chrome→017 SQL/008数据、状态/身份/权限/分页/故障/安全与独立复核有输入预期实际。契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-018-契约增量.md`）及证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-018-诊断与维护页面核验-2026-10-11.md`）纳入manifest。003/007/017及未变收费服务/后端核心证据直接复用；真实/受控边界按报告保持。
- **019启动边界**：018独立结算后核006/007/014/015/016原已验证输出与版本，M5/M6无未解释漂移，018最终9路径/证据有效。按本轮授权派新单步实施者完成019原12任务和全分项，包含实际DotProduct接线、语音writer→BM25、后台历史/H5同修订、五角色全域、配置/CRUD/旧Test/三预览与保留消费者，不作为纯测试步骤。M7汇总尚未开始，未READY/未判闸门，M8 NOT_STARTED。
- 019内部检查点（非结算）：旧缓存/API dense、DashVector query/upsert及语音会前直接HTTP未L2、非有限score/顺序的有效RED已留；接同一严格normalizer后首批25项GREEN，保留原key/TTL/批量/时限、Agent与语音自身数量过滤。后台历史投影/长修订/查询隔离已按原契约留RED后接线；其他原分项仍待实施验证，不用局部通过推019 DONE。
- 019整链内部检查点：AC18-b实际MySQL、VoiceMemoryService两类writer/trace→worker ready→main send已绿，核同ID两代当前value/BM25、旧词失效、B用户零候选；remote为受控stateful，未称实云质量。157项原消费者/Agent/语音/Step6/H5/提取回归及Admin/H5逐状态同消息同修订对照通过；历史Chrome/预览、配置未知精确提交与CRUD/星云/全矩阵仍在进行，无确定核心阻塞。
- 019环境故障披露：早期隔离夹具漏替换默认Redis，实际SETEX `memory_config:vector_retrieval_config:1` TTL3600，值与隔离DB测试计数一致（精确只读核查有exists/TTL/摘要），并调用DEL `active_config:vector_retrieval_config`，无before/返回值不能确认原key及删除效果；第三方status默认读可能miss写`cache:third_party_status` TTL60，日志不足区分。当前源码typed resolver与AdminConfigService versioned分支读SQL，根精确查版本缓存只有写入点无消费者；未核旧运行部署影响，不声称共享环境零副作用。后续在redis_client/system_monitor两导入处全部桩隔离；不再写共享Redis，不扫描、不自行恢复或清理无before缓存。保存实际限制及故障证据交独立复核，非M6/M5/017核心语义缺陷结论。后续查明两导入处不足：Step6 GET的AdminConfigService非versioned Redis/独立SQL工厂仍可能读或miss回填`active_config:step6_memory_prompt`（TTL3600），实际写入无历史返回证据。最终夹具统一覆盖所有loaded原Redis绑定remaining=[]及该独立SQL工厂，受影响节点定向验证/复用依据须在019报告明列，不把早期组冒称全部隔离。

- 019分页范围核对：本轮明确要求CRUD大清单跨页闭环，原007小DTO/写反馈不能替代。用户/私有详情补最小分页控件，保持首屏100和既有API；按当前正式memory-knowledge/api的P9候选上限500、全局无user上限300/有user500及truncated语义，只验收既有上限内完整性，不升级读取算法或声称数据库全量。此为已授权019集成补缺，未改变M5源/并发保护；正在定向Chrome/API验证，不作为019结算。

### 3.19 STEP-019独立结算与M7汇总恢复（2026-10-11）

- 018独立DONE后按本轮授权核006/007/014/015/016/018已验证输出，实施019原12任务及全部分项；019核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-019-消费者与后台兼容核验-2026-10-11.md`）逐项要求—实现—证据，019契约增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/STEP-019-契约增量.md`）只记实际7生产路径变化。18源码/测试、78证据SHA全部匹配，HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`未变，精确dirty版本清单`019-files.json` SHA `1b41a2e0a4be9d6bcd9e088e54d1bebed12ead37b156970098089b532fb5023b`；临时证据目录沿`/private/tmp/lxm-m7-018019-20261011/`，未commit/worktree/部署/改env或业务清理。
- DONE / 19/22：实际全现用DotProduct适配（单/批旧cache、DashVector search/upsert、Agent/语音直HTTP、CRUD/星云/测连）、后台历史014投影/H5同消息同revision及长修订/复合身份/旧响应、旧Prompt Test真实API/三预览、五角色145实际准入、12计数有效消费、未知发布遇他人同/异值更后版本但仅精确自有receipt确认、真实CRUD/星云闭环已各自验收。语音实际writer/trace→ready→main文字BM25两代同ID/current value/旧词失效/A-B为AC18-b；006局部和本集成不混用。
- 本步实际结果（组重叠不相加）：25项DotProduct GREEN；157原消费者回归；27项最终局部（4既有JWT测试短keywarning）；旧Prompt最终1；history实际API/Chrome1（4.93s）；配置/CRUD主流程1（87.35s）、103×3实际源记录，四域API1/20/100与知识/全局Chrome20；最新用户/私有详情只读Chrome1（22.00s），每域103条100+3/筛选51/失败/迟到/空态/GET零表变化；003缺当前完整源码SHA的测连表单只窄补4原Chrome场景，不重跑27或收费调用。voice有效PASS沿组合的独立节点，另一history夹具失败不冒称整组全绿；失败日志/RED全部保留。
- 独立Spec符合/Quality Approved，0Critical/Important，不需集中fix；review SHA `ffdabeb7696d08861ef08eded751ccbd18e082ebd716fc185e50638028d15284`。四Minor已明确：code若存在须整数0，正式增量准确校正而不升级provider；history组附带KV GET未断言status/body，不推整页所有背景成功（最新KV由runtime11直接覆盖）；原JWT测试warning不改生产密钥；长单行测试维护性建议。未发现M6终态/M5源并发/017身份权限历史保护核心缺陷，不需切A。
- 早期共享Redis/独立配置SQL夹具事故及未知旧部署影响沿§3.18与019核验原文；最终8/9/11 loaded原Redis绑定remaining=[]、AdminConfigService SQL工厂随机测试库、审计Mock-only。没有before，不擅恢复/清理，不把后续隔离成功抹成早期零副作用。远端模型/provider受控，真实SQL/业务writer/实际路由/Chrome；既有实云按未变前提复用，未做新实云质量或运行部署验收。
- 恢复点：现在才开始M7原汇总，先映射017～019及跨STEP继承证据，按实际缺口定向补验/整合增量。当前M7 IN_PROGRESS，未提交GATE_EVIDENCE_READY，未判M7闸门；M8 NOT_STARTED。本轮最终只交READY并结束，等待用户手动换模型后按原M7清单判闸门，不自行切模型/继续020或生产清理。

### 3.20 M7汇总验收证据就绪与模型交接停止（2026-10-11）

- **GATE_EVIDENCE_READY（M7）**：M6已通过/017全部原完成条件先核满足，018→019各自独立实施/验收/DONE后，按原M7计划完成跨STEP汇总。完整要求—实现—证据映射（本地留存，未随本次提交；原引用：`execution/evidence/M7-后台闭环与兼容核验-2026-10-11.md`）、最终整体复核（本地留存，未随本次提交；原引用：`execution/evidence/M7-最终整体复核-2026-10-11.md`）、源码/证据索引（本地留存，未随本次提交；原引用：`execution/evidence/M7-源码与证据索引-2026-10-11.json`）及实际临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M7-临时契约.md`）已进入当前manifest。累计19/22；M7仍IN_PROGRESS，未判PASS/VERIFIED；M8/020～022 NOT_STARTED。
- 汇总先映射已有全部原分项，不重跑前提未变组/大清单/收费调用。阶段整体独立读4344行actual dirty增量及三独立review，Spec/Quality可接受、新增Critical/Important/Minor均0；final-review SHA `8cfc2e349b4b69e3a6d805079a0e3e5f417271e21ddf23d52b9a2c7de10cfa1d`。独立解析业务三链、Voice两代BM25、历史7同修订pair、145分域准入、unknown精确self版本、CRUD/诊断/回填稳定全集合及保护；没有新的命名风险需加跑，不把静态检查当运行证明。017/018既有Important均集中fix1独立关闭，019四Minor按§3.19准确交接，无待A核心缺陷。
- 版本：HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`未变，同工作区保留用户/前序dirty；55本阶段唯一路径最终清单SHA `0b26a85a4ad743451166a1831f8a50f9e450c1af98c9e0959145461a189cc4b7`，full-diff SHA `6384e827358afac49ab2d72d504df18bb4f303f1d174c012f5ba86492d801e0c`。M5/M6→017→018→019共167相关源版本链/当前SHA无未解释差异，normalize_dense主体AST保持；017原49（报告accepted fix1副本例外）、fix1 17、01878、01978、M6 153索引成员已匹配，008原SQLite/603生产清单未改。数量是索引成员不是测试用例，不累加重叠组。
- 真实SQL/事务/业务writer/路由/装载/Chrome与远端provider、部分auth身份、计数/时钟/运输替身边界见映射，实云仅继承原未变证据，不推新质量或部署。历史组附带KV请求结果未断言、最新KV另验收；M5/006局部与019 AC18-b、旧Test reply与诊断reply0分列。早期019默认Redis实际SET版本缓存/active DEL未知效果、可能status/Step6 miss写及旧部署影响未知全部保留；最终隔离remaining=[]及独立SQL工厂只定向覆盖受影响节点，没有before不擅恢复/清理，不声称零环境副作用。未改PRD/计划/STEP §3外内容、正式current契约、env；未commit/部署/运行业务迁移或清理。
- **本轮到此结束**：恢复位置是用户手动换模型后的原M7闸门清单核对/判定，先核本§3及有效索引/三步完成标志/实际契约/限制；不自行判M7闸门、不切模型、不开始020/M8、不部署或执行业务清理。必要材料若恢复时缺失不能冒称已复核，先最小补证；若出现M6/M5/017核心新缺陷按用户要求保存复现、影响和恢复点回A。

### 3.21 M7最终闸门审核与停止（2026-10-11）

- USER_DECISION：本轮按现行计划审核017～019原完成条件、有效实现/验收证据及实际契约增量，授权判定并更新唯一记录；判定后停止，不进入M8、不部署或执行业务清理。只读当前权威入口及必要源码/原始证据，复用前提未变结果；无新源码修复、业务测试重跑、收费调用或共享资源访问。
- **M7闸门NOT_PASSED / BLOCKED**：M6原PASS_WITH_RISKS/VERIFIED有效，017的008真实记录与015实际业务对照及018/019前置均满足；但019原测试表“配置与操作闭环”有一项必要可观察证据缺口M7-GAP-01，不能以SQL保留或其他空态推定完成。当前019仅该验收BLOCKED、18/22；017/018及其他已验证分项保持。§3.19的DONE和§3.20的GATE_EVIDENCE_READY保留历史提交时点，当前以本条更正为准，不将READY等同闸门通过。

| 原条件/重点 | 本次核对的有效实现与证据 | 判定 |
|---|---|---|
| M6及三步前置 | §3.15原闸门；002/005/012/013、003/007/017、006/007/014/015/016/018的有效版本链；017 AC12实际main/OpenAPI/Step8至回复前的ID/正文/选入/token对照，AC11-a原008持久生产run/item | 满足；不重复原测试 |
| 017全部原任务、API/持久/并发/权限/保护 | 同源装载及实际三链对照；诊断reply/Step6/13类聊天表写为0；真实MySQL外呼前登记、重复/ACK未知、执行保存分态和DELETE未知；后端角色/资格、永久快照及未完成引用保护，fix1均关闭 | 原完成条件满足 |
| 018全部原任务、真实浏览器与大清单 | 原身份重复/刷新/显式重跑、校时/有限观察/离页守卫、双状态/失败空态/文本安全、后端维护资格；008原603条→017实际API→018Chrome，候选104/历史105及维护事件/关联按1/20/100完整稳定，fix1均关闭 | 原完成条件满足 |
| 019已验证分项及M7接线 | 全现用DotProduct/L2与旧门槛/时限/缓存；实际Voice writer→ready→新主文字BM25两代同ID/当前正文/用户隔离；旧Test实际API及独立零新增副作用、三个只读预览；后台/H5七对同修订、145分域准入/旧来源owner、精确发布回执及CRUD四域分页/真实Chrome | 已有证据有效；不据局部结果推下行缺失条件 |
| 019“配置与操作闭环”：S15清理后空历史、保留资料/日记/朋友圈/亲密度数值可见且不变 | M5真实MySQL `test_memory_reset_mysql.py`→`exercise_nonempty_reset`证明非空SQL身份/值保留及对话清空；019 `test_memory_compat_browser.cjs`的`filter-empty`使用日期筛选，H5空态来自两条批删。现有有效输出没有同一S15清理后夹具经实际读API及真实页面核对保留功能/数值可见性 | **M7-GAP-01：必要证据缺口，阻塞019 DONE及M7通过；不是已确认代码缺陷** |
| 实际契约增量 | 三步增量→M7临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M7-临时契约.md`）的11API/权限/身份/时限/双状态/永久历史/保护/分页/前端观察及消费者接线逐项一致，未发现实际契约遗漏 | 增量有效；正式current整合仍NOT_STARTED，按022最后阶段安排 |

- **最小补证范围/恢复位置**：从本§3.21的M7-GAP-01恢复。在自有隔离库使用既有S15非空保留夹具和清理流程，记录清前/清后身份与字段值；通过现用实际读API及真实Chrome页面核对资料/姓名昵称、亲密度/等级/成长值、日记与朋友圈正文仍可见且与基线一致，同时核对清后历史的API与页面空态。保存输入—预期—实际、run/user及最终源码摘要、API输出/DOM结果和资源隔离证据；如已有同等有效证据只需精确补交映射。复用M5存储保留及本期其他已验证结果，不重跑全部003/007/017/018/019，不调用付费模型，不触碰业务清理/部署。缺口不要求改变需求、权限、核心状态或正式契约；未发现需切A的核心语义缺陷。补证后只重审此条件及补证的实际影响，再结算019/M7。
- 有效版本重新核算：HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`未变，最终55源码、167继承相关源码及before、五个原始证据索引全部匹配；原017报告仅accepted fix1追加，冻结副本和当前摘要分别匹配。四份最终review/六份提交文档均匹配，`normalize_dense` before019/current AST相同。008原SQLite SHA `bddd59363f2849ee8133fb7e3da84ee6ed7ca21400a78aea7b725e50db658f37`未变，只读SQL独立确认run `c6341c07-9ec3-442a-b16a-49511d40cb5a`、603唯一身份/seq1～603、standard1/legacy602、completed/catchup/unresolved0/report_complete。源码清单/阶段diff及各索引摘要沿§3.20，不把索引成员数当用例数。
- 本次只读核算输出：m7-gate-source-evidence-check.json（本地留存，未随本次提交），SHA `08674c2729694bf4576c528f94616bc2c7723e16aed4595908bec98a39a7a4b2`；缺口定位及最小范围：m7-gate-evidence-gap.json（本地留存，未随本次提交），SHA `2ce0ea5a54886d23c90c623ecefea57b4bc4218913ac5513f72c439ae4ed8eed`。二者是原始审核产物，不是另一份进度记录；来源/实现及既有运行结果见阶段证据映射（本地留存，未随本次提交；原引用：`execution/evidence/M7-后台闭环与兼容核验-2026-10-11.md`）。
- 限制及停止：真实SQL/事务/锁、实际入口/writer/装载、API与Chrome证据按各组范围接收；远端provider/部分身份/时钟/运输受控，不冒充新实云质量、token真实性或部署。原019Redis版本缓存实际SET、active DEL效果未知、可能status/Step6 miss写及旧部署影响未知仍保留；最终隔离证据有效，但不能倒推早期零副作用，没有before不擅恢复或清理。本次未改正式契约/PRD/计划/STEP §3外内容或业务源码，未重测或清理。**本轮到此结束：M7未通过，M8/020～022 NOT_STARTED；不自动切模型或进入下一阶段。**

### 3.22 M7-GAP-01补证、019重新结算与最终闸门停止（2026-10-11）

- USER_DECISION：沿用同工作区及唯一记录，按§3.21最小范围先找等效证据，缺失时以自有隔离S15夹具经实际API/真实浏览器补齐；补证后重新结算019并判定M7，更新记录后停止。不得改变需求/核心语义、重复其他有效测试、进入M8、部署或执行业务清理。本条是§3.21阻塞后的当前结算；§3.19～3.21保留当时DONE/READY/NOT_PASSED事件，不能以旧事件覆盖本条。
- 等效证据核对：M5真实MySQL非空保留与清历史有效，019日期筛选空态和批删空态也各自有效，但仍不能代替同一S15清后夹具的实际保留页面结果。故只增加PY隔离补证（本地留存，未随本次提交；原引用：`../../../tests/test_memory_s15_visibility_runtime.py`）及CJS浏览器补证（本地留存，未随本次提交；原引用：`../../../tests/test_memory_s15_visibility_browser.cjs`），完整输入—预期—实际映射（本地留存，未随本次提交；原引用：`execution/evidence/STEP-019-消费者与后台兼容核验-2026-10-11.md`）已追加原019证据；未改任何生产源码/API/页面、需求、原验收或其他STEP完成标志。

| 本次补齐的原条件 | 有效实际证据与输出 | 结算 |
|---|---|---|
| 同一S15清后历史空态 | 自有MySQL真实迁移/原reset流程，清前普通/Agent各1；实际Admin历史2→0、H5 history1→0、timeline2→0且has_more=false；Chrome后台“暂无对话记录”和H5消息行2→0，在实际装载完成后核对 | M7-GAP-01空态部分满足 |
| 资料、日记、朋友圈、亲密度可见且不变 | 实际Admin/H5原读API清前后保留字段相同；Chrome资料卡/日记Tab、H5展开日记/亲密度/朋友圈共五组保留DOM相同。账号/注册登录/正常状态、2级亲密、累计1117（API/后台）、H5原区间317/1200和距下级883、同日记/帖子id1正文均保持；朋友圈等现有boot遮罩退出后取证 | M7-GAP-01保留可见性满足；现用资料页无姓名昵称展示字段，只以SQL原值保持证明其保留，不新增UI/API或冒称DOM已展示 |
| 存储和资源边界 | users/ai_diary/feed_post全行摘要前后相同；Relationship身份/姓名昵称/等级/成长值相同。最终run `1c673d18-5821-4dbd-85b7-679ff35d5885`仅库`lxm_m3_test_4cb19108e05d4adfa800af6436b19449`、环境isolated:gap01；completed但fence始终maintenance，未opening；两个读阶段SQL DML0/恢复执行0/外部Python HTTP[]/原Redis绑定remaining=[] | 没有新业务或核心语义缺陷；隔离清理不冒充正式S15/切换 |

- 新增实际验证：最终`RUN_M3_MYSQL_TESTS=1 GAP01_OUT=/private/tmp/lxm-m7-gap01-20261011/run4 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_memory_s15_visibility_runtime.py -q --tb=short`为**1 passed in 9.78s，exit0，无skip**。清前/清后各10直接API探针、各15真实Chrome API响应，另清前异步资格GET1次，合计51个HTTP200/全部GET；每次Chrome六消费者断言、十张清前后截图。真实SQL/reset/原读路由服务/原页面JS；身份、Redis内存替身、空外部资源清单及seal声明受控，不证明生产停写/排空或远端服务。Chrome阻断外部字体及无关向量Tab请求，相关提示保留，不据此宣称整页背景请求全成功；原019独立KV证据复用。
- 失败处理和重跑依据：run1本地连接受沙箱限制，setup失败未创建夹具；run2把H5区间成长值误断言为累计值，纠正测试口径且保留累计API/后台断言，未执行S15；run3为1passed/7.26s但朋友圈截图在进入动画，强化boot完成等待后仅重跑同一补证场景得run4。各轮日志与执行源码副本保留；不改页面、不降低断言，不重跑003/007/017/018/019其他有效测试或收费调用。
- 019重新结算：006/007/014/015/016/018输出与有效版本前提未变，原12任务及既有全部分项继续沿§3.19/3.21和019原证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-019-消费者与后台兼容核验-2026-10-11.md`）复用；唯一缺失的原“配置与操作闭环”S15可观察部分由本次实际链补齐，完成标志全部满足，**STEP-019 DONE，19/22，M7-GAP-01 CLOSED**。未发现需要回A处理的M6终态/M5源并发/017权限幂等历史保护核心缺陷。
- **M7最终闸门PASS_WITH_RISKS / VERIFIED**：按现行M7原清单重新接收补证后的GATE_EVIDENCE_READY并判定。M6原PASS_WITH_RISKS/VERIFIED继续有效；017开发002/005/012/013及DONE所需008实际持久603生产记录/015真实业务对照（传递014）、018的003/007/017、019的006/007/014/015/016/018均满足。017同源三链至同次Prompt/零reply/零Step6/零聊天写、执行身份及双状态/持久并发/角色/历史引用保护；018真实浏览器/008→017→018实际读取/稳定大分页；019全入口DotProduct/保留预算时限缓存、Voice writer→ready→新文字BM25同ID/当前正文/隔离、旧Test/三预览、后台与H5同修订/五角色分域、配置精确回执/CRUD分页闭环，原证据映射和最终版本不变，本次只补原缺失行。API/Chrome/存储/并发与必要实际链证据齐全，未以模拟或局部通过代替原明确实际要求。
- 版本与回查：HEAD仍`9c6f9855f5f2808a21c9e6bd761847198df2d516`；原55最终源码及167继承相关源码全部SHA匹配，原索引/008持久记录沿§3.20/3.21有效且未覆盖。新增PY SHA `2c31d63dbe18d1a9b48e351b1b5fb9e3a81817ed49b0a1ea8a82445711d06597`、CJS SHA `814fa5758224c5fc415e3bee0b771ae6dfc302842b82f7a78342b9da932d6c96`，29消费源码摘要与实际执行前版本一致。补证最终索引（本地留存，未随本次提交） SHA `57c05c31e118b7430ec17a5a2ded62017fafe5c832770783db700fd8b27f55f2`；原019证据追加前副本SHA `7472d7c3dcbc7722e39a4ea09dad19da842589d05692a5ac67c8e4fce2fcb1e3`，新补证以独立索引接续而不篡改冻结摘要，索引成员数不当用例数。
- 实际契约增量为0：本次只有测试和证据，API/权限/状态/幂等/保护/分页与消费行为未改变，原017/018/019增量及M7临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M7-临时契约.md`）继续有效，无空增量文件。正式契约整合仍NOT_STARTED，继续按022最后阶段安排；PRD/计划/STEP §3外/正式current/env不变。
- 限制及停止：原019早期Redis版本缓存实际SET、active DEL效果未知、可能status/Step6 miss写及旧部署影响未知仍保留；最终隔离补证不能抹去历史事故，没有before不擅恢复或清理。受控远端、部分身份/计数/时钟/运输边界及已有skip继续按原组区分，M7通过不证明M8真实质量/token或生产启用。**本轮到此结束；M8/020～022 NOT_STARTED，正式整合NOT_STARTED。**未来只有用户明确恢复才核M8原进入条件；不自动切模型、启动020/下一阶段、部署、开启新链或执行业务清理。

### 3.23 M8/STEP-020前置与本地Docker输入核对、GATE-C未通过（2026-10-12）

- USER_DECISION：本轮授权020→021→022准备→正式契约整合→交接验证连续顺序执行，每步独立核前置/原完成标志，前一步全部通过才进入下一步；020/GATE-C在本轮裁决，022进入后保持IN_PROGRESS、GATE-D/M8最终闸门留下一轮A。不得合批/并行、重复其余有效测试、部署、实际S15业务清理/开放或旧库退役。用户随后说明可能没有现成评测集，要求自行检查/寻找验证办法，**只做本地Docker上项目的测试**；已按此补充定向核对本地材料，没有再要求确认推进顺序或擅自替换原正式质量口径。
- 原前置复用：§3.22 M7 PASS_WITH_RISKS/VERIFIED有效；002原GATE-B设计/五份定稿及PRD六项来源SHA全部匹配。HEAD仍`9c6f9855f5f2808a21c9e6bd761847198df2d516`，M7最终55源码、167继承相关源码以及GAP-01最终29消费源/23证据成员全部匹配，既有功能/事务/API/Chrome/云探针不重跑。当前PRD、STEP任务/验收及里程碑顺序未变。

| 020原任务/完成条件 | 本次实际核对及可复用边界 | 结果 |
|---|---|---|
| 同集现存语料/查询/相关和无答案标注、真实关键场景及实际N | 当前INDEX/manifest与002/M1/M4有效材料未定位正式产物；按用户补充读取本地lxm项目SQL，21条现存文字中用户7/助手14，全部记忆注入解码后为null，无可复核的相关文档ID/正文及失败标注；旧memory表0。7个SQL非NULL JSON单元实际为JSON null，不是七份记忆快照 | 必要输入未齐；正式样本N未确定，不能把7条泛化聊天或0条记忆写成已冻结正式集 |
| 文字漏召回、混淆、改写/指代、多个限定条件及AC20输入 | PRD §11.5要求关键场景从当前真实文字失败样本选取；本地现有记录不能证明哪条当前记忆应命中/是否遗漏，也无足以覆盖上述关键场景的已标注正例/负例。M1的603合成身份与M4的四路20条合成/门槛0探针仅证明既定功能，不等同质量样本 | 未以造事实、改记忆结构或新合成演示取代原必要数据；此项阻塞正式冻结 |
| 单位/分母/汇总/逐样本质量、关键不退步及三种Query对照 | 原PRD/020口径有效，但尚无可绑定的标注集和旧词组/新BM25词组/完整Question逐样本对照；没有先跑模型再择样/改标准 | 未冻结，不宣称完成；费用及日常延迟/提升幅度数字目标明确不是缺口 |
| 实际源码/模型/Prompt/编码器/索引/配置及负载组合 | 工作区有效新源码摘要可复用；只读Docker lxm_backend/lxm_mysql/lxm_redis/lxm_nginx归属当前项目、均运行。后端已观察7条源码：原query_rewrite/prompt_builder为HEAD旧版，与工作区不同，multi_vector原文件相同，新retrieval/effective-config/hybrid/reset四文件不存在；实际DB版本v8h_voice_master_switch_001、所查新控制/诊断/版本表未创建。原配置getter返回豆包doubao-seed-2-0-lite-260428、embedding-v4、memory_long_collection | 明确运行边界；配置名称不代表已调用成功，不能把旧容器当M7新链已生效。未部署/重启/迁移；独立隔离测试副本可与部署区分，但本轮尚未建立或正式运行 |
| 正常/改写降级/单通道失败/rerank故障分报及硬约束 | 002参数/已验收功能继续保留180秒、45+45、一次失败调用重试、连接/收口/有限恢复语义；各链分别报告的原要求保持，未混用模拟/真实、探索/正式结果 | 功能旧证据复用；尚未形成绑定正式样本集/实际负载的冻结产物，不以功能结果代替AC19/AC20 |
| 三项原完成标志、来源回传与唯一记录 | 本节及原始输入核对记录当前已证实事实、未取得输入与恢复条件，没有正式同集/质量判断完成证据，无新增行为契约 | 020不能DONE；完成数仍19/22 |

- 新验证仅只读Docker输入/环境探针：`docker inspect`核四容器compose归属为当前路径；`docker exec -i lxm_backend python -`运行两份临时探针，SQL显式READ ONLY并rollback，第二版元数据探针exit0及文字素材探针exit0。另只读依赖版本exit0：pytest9.1.1/pytest-asyncio1.4.0/SQLAlchemy2.0.51/httpx0.28.1/tiktoken0.13.0/FastAPI0.139.0/DashVector1.0.23，dashtext未安装；未安装、复制或启动新的测试运行副本。没有业务DML、模型/外部检索调用、Docker启动/重建、业务库schema迁移或资源清理。首次探针在JSON输出阶段因SUM返回Decimal序列化失败，未改变读事务；输入/stderr保留，仅修探针JSON编码后定向重读，不把失败抹成PASS，也不重跑功能集。
- **GATE-C NOT_PASSED；STEP-020 BLOCKED，M8 BLOCKED**：按本轮闸门核对授权及原020异常行/CSTR-04，必要同集、可复核标注与真实关键场景不足，尚不能形成完整可复现的正式冻结版本。不是已确认检索实现缺陷，也不否定M7；不要求新增费用/日常p95/改善幅度阈值。旧Docker源码与工作区不同只作为环境事实，不单凭“未部署”判工作区实现失败；目前直接阻塞是正式样本/标注前提没有取得。
- 原始可回查材料：020输入与版本核对（本地留存，未随本次提交），SHA `bea8f4d9fdfa706b0b23cf079f94c87d09fa5bb5e5b5f1ab32afb87718ead935`；Docker只读元数据（本地留存，未随本次提交）及本地原始文字素材（本地留存，未随本次提交）。完整原始正文仅留本地临时证据，未对外传输；失败探针与运行输入副本均在同目录。它们是核对证据，不是新的计划/进度文件。读取限当前入口/manifest、上述有效材料及必要源码/本地项目表；没有读取迁移基线、历史文档或其他Docker项目数据。
- 继续寻找素材及自动审批拒绝：为核对SQL之外的现存正文，已准备`/private/tmp/lxm-m8-20261012/docker_vector_readonly.py`，具体仅从lxm_backend调用项目配置的DashVector describe及四类filter-query（topk100，不以该cap证明完整来源），不写删向量、不调用回复模型、凭据不进输出、正文仅留本地。**执行命令被自动审批拒绝，脚本没有在容器内执行、没有任何远端请求**；理由为“虽从本地容器发起，仍会使用项目凭据访问远程DashVector并读取可能敏感的向量正文；用户仅授权本地Docker测试，未授权外部服务访问”。没有绕行、改用网页/API间接访问或重试被拒操作；已就这项具体只读访问提出权限问题，未收到明确答复不执行。即使该读取获得授权，也必须先核当前事实、形成并冻结正式样本/标注，再判GATE-C；读取成功本身不等于020完成，更不代替021真实评测。
- **最小恢复位置及交A事项**：从020任务1/本节输入缺口恢复，需要有来源身份及当前正文的固定语料、能复核的实际文字失败查询/上下文、相关文档与无答案标注，并覆盖原文字关键场景及AC20专有实体/去套话/指代/模糊时间/否定语义。现有向量事实位于配置指向的远端服务，本轮仅本地Docker核对、未访问远端；不能据旧SQL memory表0认定整个向量库为空或伪造其当前源证明。若当前真实失败数据确实不存在，应由A裁决数据前提是否需调整；不擅自把纯合成样本提升为正式AC19验收，也不将只读本地核对变成外部服务运行/新写入授权。数据补齐后在已授权本地Docker的独立隔离测试上下文中核实际源码/模型/索引/配置和负载组合，冻结并复核GATE-C后再进入021，无需重新确认已授顺序。
- 021/022及正式整合交接：020未全部通过，按原前置及用户顺序要求，**STEP-021、STEP-022仍NOT_STARTED**；没有启动真实旧/新链或AC20质量评测、022演练/35AC+22子例+13CSTR总对账，不能先把022标IN_PROGRESS或借准备工作跳过021。正式契约整合及整合后验证NOT_STARTED；未登记CONTRACT_MERGED_PENDING_VERIFICATION/CONTRACT_VERIFICATION_READY，不提交不存在的完整READY。M8本轮实际契约增量0（只有只读核对），无空临时契约文件；原M1～M7有效临时增量继续保留，正式整合须等022原顺序收齐M8实际产物后执行。
- 本轮停止：只改本§3进度/缺口回传，保留用户/前序源码和原证据。M7已通过、早期019环境事故及未知旧部署影响沿原记录；本轮未做恢复或清理。没有裁决GATE-D、M8最终闸门或正式契约闸门，没有部署、业务开放、实际S15清理、旧库退役或自动切模型。当前交A的是020必要输入/范围问题，不能把本轮只读核对说成020～022或最终交接完成。

### 3.24 STEP-020只读授权补证与有据查询候选（2026-10-12）

- 最新USER_DECISION：“允许本次只读核对”，针对§3.23被拒绝的具体操作：从本地lxm_backend使用项目配置访问DashVector，仅describe及四类filter-query、不写删、不调用回复模型，正文只留本地、凭据不输出。该答复补齐此操作授权，随后执行成功；此前审批拒绝及未执行事实仍保留原时点，不再把该只读权限列为未解决阻塞。不是对新远端模型调用或测试索引写入的自动扩展授权。
- 实际运行：`docker exec -i lxm_backend python -`执行原已准备脚本，exit0、stderr空；describe及character_global/private/knowledge/user四类filter-query均HTTP200/code0，共97个不同ID，数量19/26/5/47。目标仍是`memory_long_collection`，SERVING、1024/FLOAT/cosine、无sparse schema/index。四个topk100查询是已观察正文快照，不能替代完整遍历/源总量/当前代次证明；未改变旧库或新库内容、分区、索引、配置、SQL及容器运行状态。没有其他远端请求或模型调用。
- 数据准备：保留97条原始fields/content和ID，按ID排序的本地快照与原始响应逐条结构相等；未拆解/改写记忆、补年份/城市/姓名或构造缺失事实。记录显式探针内容、跨用户记录及两条“专属爱称存在/完全不记得”冲突，后者无时间/代次依据，未猜测覆盖先后或修复源事实，也未选为计分候选。旧源快照不自证新链SQL凭据或008完成状态。
- 基于可观察正文自行准备24条人工查询候选，含5条无答案，覆盖实体、改写、指代、模糊时间、否定、多个限定条件、混淆及跨用户无答案。逐条给出所需事实和相关ID；24条身份引用/路由/归属及answerable一致性检查通过。人工查询和构造上下文均明确标为夹具，不冒充历史聊天/当前失败；历史7条真实用户查询另列为failure UNVERIFIED，null注入不能单独证明漏召回。实际新旧词组/Question三对照仍为待取得值，不用手造词组替代真实Step1.5输出。
- 该产物是`input_candidate_not_formal_freeze`，**不是020正式冻结或021质量结果**：候选数24、正文观察数97是实际计数；正式N/关键场景数尚未填，不能把候选数直接结算成正式样本量。记录候选计分单位、不同分母/空分母N/A、相关性/证据利用判断及正常/改写降级/dense失败/BM25失败/rerank失败独立口径；仍须结合实际实验版本和正式关键场景冻结，既有180秒、45+45、失败最多一次重试及002有限约束保持，无新增费用/延迟/改善幅度阈值。
- 要求—证据对应：020任务1的现存正文来源、身份/标注准备取得新证据；真实失败关键场景尚无可复核旧链输出。任务2的实际模型/Prompt/编码器/索引/配置/负载及三查询冻结尚未具备本地隔离新链运行组合；原Docker缺新链模块与dashtext事实沿§3.23，未部署不能单独判代码失败。任务3的原硬参数/功能证据仍复用，候选分报口径已登记，尚未作为正式冻结收口。M7/002及其源码/证据摘要仍按§3.23复用，无业务改动、故障或新疑点，不重跑其余测试。
- 原始交接：本次补证索引（本地留存，未随本次提交），SHA `da7d6c4b3fdaaf87a6134230d1419765a105d80ca8d9c4d12962764b01bab91c`；原始只读结果（本地留存，未随本次提交），SHA `d11c9236736019a2b64384b757791c411648002a829d56d9013693727c4d2234`；原文快照（本地留存，未随本次提交），SHA `1eba5b69f2bff53ace92b3aa5306b541375469be035cc0e082849673c5ec1e35`；24条标注候选（本地留存，未随本次提交），SHA `a1ee46ec470d4766aaf81ba92bb8f426c091ccf72445dbf93bf610a1e1075c87`。输入脚本/原始空stderr及核对结果在同目录，临时证据不是第二份进度记录；正文仅存本地，正式导航/manifest/契约没有提前整合。
- **当前结算与恢复**：020仍BLOCKED、GATE-C NOT_PASSED（原完成标志不足，不是新增需求或确定代码缺陷）；021/022及正式契约整合/验证NOT_STARTED，完成数19/22。已提出具体范围问题：是否允许从本地Docker隔离评测副本调用现有改写/embedding/rerank/回复模型，并仅在新库独立M8测试分区写入本批快照派生索引，先探索性旧链取得实际失败，再正式冻结；不改旧库/现有业务SQL，不部署/清理。明确答复前不执行这些外部调用/写入。恢复从本节24候选及020任务1/2进行，不能在缺实际运行证据时判GATE-C或进入021，也不更改原关键不退步标准。
- 本次无业务源码、Prompt、模型、配置或正式契约语义修改，M8实际契约增量仍0；未裁决GATE-D、未标M8 VERIFIED、未执行S15业务清理/开放/旧库退役。正式整合与CONTRACT_VERIFICATION_READY仍须按020→021→022原顺序履行，不能用只读补证代替完整交付。

### 3.25 STEP-020隔离真实探索、索引准备与正常改写阻塞（2026-10-12）

- 最新USER_DECISION：“允许上述隔离真实评测”，具体承接§3.24所问：本地Docker隔离副本调用现有改写、embedding、rerank及回复模型，所选正文可作为模型输入，快照派生索引只写新库独立M8分区，旧库保持只读、不改既有业务库、不部署不清理。该授权已执行，无待重复确认的外部调用权限；§3.23审批拒绝只保留原时点。执行范围仍020→GATE-C→021→022→正式整合/验证，不能因准备成功越过前置。
- 前置及源码复用：M7/§3.22及002/§3.6仍有效，HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`，工作区原用户/前序改动保留；本轮327份评测源码、M7的55份源码及167份继承源码、GAP-01的29份源码/23份证据、002六份来源、25份受保护权威文档摘要全部匹配。未重跑其余已验收测试；旧业务Docker源码与新工作区副本分别取证，不以“未部署”判实现失败。
- 隔离运行组合：原ARM64容器无可用dashtext Linux ARM64 wheel，安装失败证据保留；仅建立自有 `lxm_m8_eval_0498495e`，`python:3.11.15-slim` Linux/amd64（镜像摘要及实际依赖在证据索引），复制当前源码和原Docker `/app`旧链源码。私有数据库 `lxm_m8_0498495e6e6c4e8c`、环境 `isolated:m8_0498495e6e6c4e8c`、Redis写前缀 `m8_0498495e6e6c4e8c:`；无应用端口/部署/常驻索引循环。ORM新建schema及active fence只是自有夹具，不代替迁移或022/S15实际启用证据。原业务SQL、Redis配置及原服务环境未修改。
- 实际配置纠偏：先前窄SQL探针未使用正确 `persona` key，隔离初始旧链24条使用代码DEFAULT_PERSONA；后续实际只读取得已发布persona第3版及用户1关系快照，原共享Redis对应配置缓存为空。**24条结果及原始输入/输出全部保留为默认参数探索，不能据此选当前正式关键场景或报告正式改善**。已把实际persona复制到私有配置并只预热自有缓存；已登记冷缓存改写可能取DEFAULT、Prompt装载后取DB persona的边界，不改已验收装载语义。配置/语料没有为通过评测改写。
- 当前persona定向探索：仅重核代表C01“你刚刚改完甲方要求的第几版UI？”；实际旧改写/embedding/Cosine检索/旧Prompt构造完成约27287ms，标注两条cg第八版正文，实际改写转ck，候选及最终选入均0，存在可复核文字漏召回。人工查询基于现存事实，不伪称历史用户失败；该一条证明不能代替24条当前配置同集正式基线/关键清单冻结。旧链沿自身原TopK3/threshold0.7/每路最终3、原45秒调用及内部重试，属探索，不能将其当新链20秒调用/一次重试验收。
- 夹具故障与费用证据复用：私有fence首次初始化因未声明维护bootstrap被既有保护拒绝，第二次只修夹具标记，业务保护未改；旧C06首次模型/检索已成功，Prompt上下文夹具dict不符合旧对象形状而失败。保留原72871ms失败记录，只修夹具形状并复用已收费改写/检索，164ms为修复后本地渲染耗时，**不是该查询完整整轮延迟**；没有据此报告性能改善。未弱化断言或修改其他STEP源码。
- 真实服务及派生索引准备：已实际核新库DotProduct属性、原编码器 `memory-bm25-zh-v1:17dbc3fe3a4d2ed8dd70a72bef5bf8812abea09585a137e07cbd2fd76b4db194` /统计SHA `62d586126746a5c8df9a218187b5200ee306055daa5af47d90b3a1b1bcce51de`、真实v4 1024维单位embedding、gte-rerank响应及官方tokenization。使用现有Mutation/IndexWorker在 `local_test_collection / m8_0498495e6e6c4e8c` 完成96条写前持久登记、源确认和索引任务，96 identity live/ready、96任务completed、无在途保护。原97条中的非标准旧ID `user_xingming_4` 未修复/复制，原快照保持，用户1的68条有效语料及24查询标签不受影响；正式同集身份口径仍须冻结。独立只读逐ID fetch复核全部原字段、当前正文SHA/epoch/generation、dense单位及sparse存在，全部一致；手工就绪探针“第八版 UI”和带user_id=1的“瘫着”稀疏查询返回真实匹配文本，用户筛选无跨归属。此处仅索引准备，不能代替021最终选入/回答质量、增量对账或008生产回填证据。
- **阻塞M8-020-REWRITE-RUNTIME及最小复现**：实际persona3/C01/当前13字段Prompt/项目模型 `doubao-seed-2-0-lite-260428`，生产等效默认HTTP客户端10秒内两次ReadTimeout（10125/10091ms）；同输入独立HTTP read20诊断受原StageBudget每调用20秒取消（20017/20011ms，两次），未取得新链正常Step1.5输出。默认客户端10秒会缩短20秒最大预算，但20秒诊断也未通过，**根因不能仅归为10秒，也不能推定供应商宕机或完整新链失败**。未改变HTTP生产客户端、Prompt、模型、硬时限或重试语义；20秒客户端注入只为探索，非生产正常证据。当前缺实际新BM25词组/完整Question及有效正常组合，不能把原输入fallback、共享helper单测或降级成功作为正常质量/AC20通过。

| 020原要求/完成标志 | 当前实施与证据 | 结论 |
|---|---|---|
| 任务1同集/查询/相关与无答案标注、关键清单及逐样本/分母/汇总冻结 | 97原文、24人工候选（5无答案）身份/事实核对；当前persona旧C01真实漏召回；完整当前基线、关键清单及正式口径尚未冻结 | PARTIAL，非DONE |
| 任务2实际模型/Prompt/编码器/索引/配置/负载与旧词组/新BM25词组/Question对照 | 实际版本、依赖、配置快照、96就绪索引；无正常新改写三查询值 | BLOCKED |
| 任务3正常/改写降级/单通道失败/rerank故障分报及硬约束 | 002原180秒/45+45/一次重试及连接/收口/有限恢复参数复用；候选口径保留，未签正式冻结；没有费用/日常延迟/提升幅度数字门槛 | PARTIAL；不混用探索与正式结果 |
| 全部原完成标志、来源回传、§3及实际契约 | 新发现环境/实际输入/失败/影响边界已回传；任务1/2仍不足 | 020 BLOCKED，GATE-C NOT_PASSED |

- 原始交接：隔离探索证据索引（本地留存，未随本次提交），SHA `dbe7f92b1eb5c59148e262c9be0ba78a37bdaf731dd08292ab60aa1c3be615e8`，209份输入、helper、源码/依赖清单、原始输出及持久回执摘要；真实索引准备（本地留存，未随本次提交）、逐ID只读复核（本地留存，未随本次提交）、生产等效改写失败（本地留存，未随本次提交）、20秒独立诊断（本地留存，未随本次提交）、实际persona旧C01（本地留存，未随本次提交）及失败原件均在同目录。服务凭据输出扫描133份结果/实际上下文，命中0；helper只保留脱敏异常类型/原因。正文/合法业务输入按原授权留本地，不为脱敏改写正文；未调用回复模型或Step6，私有聊天表0。
- **交A及恢复条件**：暂停020冻结及其依赖，交A定位当前009/012已验收改写组合的实际可用性；建议在保持180秒、45+45、调用20秒及最多一次失败重试下，审定必要的Prompt/模型调用参数或适配修复范围，不能简单延长预算。若需要改已验收行为/共享参数/Prompt或模型，先登记新版本及受影响前提，不自动改002/009/012。恢复从本§3.25/020任务1、2的同C01正常改写最小复现开始，取到有效正常输出后再完成当前persona同集基线/关键场景、三查询/计分冻结及GATE-C；未变化的encoder/embedding/rerank、索引和M7/002直接复用。自有分区/数据库/回执原样保留，无未知在途；不要盲目重复制或清除锚点。
- 当前结算：19/22，M1～M7仍VERIFIED；020 BLOCKED/GATE-C NOT_PASSED，**021、022仍NOT_STARTED**（022的IN_PROGRESS要求适用于其前置完成后，不提前进入）。022准备/隔离演练、35AC/22子例/13CSTR总对账、正式契约整合及整合后验证均未执行，CONTRACT_* /READY未提交。M8本轮实际业务契约增量0：仅隔离工具组合及证据，正式导航/manifest/覆盖和M1～M7有效临时契约保持；不创建空临时契约或提前把未部署行为写成事实。本轮仅更新唯一§3，未裁决GATE-D/M8最终闸门，未部署、清理业务数据、开放、退役或自动切模型。

### 3.26 STEP-020真实改写恢复与冻结准备（2026-10-12，执行中）

- USER_DECISION：沿§3.25定位实际改写根因，保持180秒、45+45、单调用20秒及最多一次失败重试；最小修复后真实核验并恢复020，允许本轮GATE-C判定；021→022→契约整合/验证仍逐步前置，022保持IN_PROGRESS，最终GATE-D/M8交A。继承全部隔离模型/派生索引授权，不再重复询问。
- 根因证据：当前 `doubao-seed-2-0-lite-260428` 请求未传thinking，官方支持enabled（默认）/disabled并提示思考摘要可能有高包间延迟，来源[官方深度思考](https://docs.volcengine.com/docs/ark/deep-thinking?lang=zh)。实际persona3/C01/同一2083-token Prompt，仅加入 `thinking.type=disabled`，HTTP200、4856ms、188输出tokens、reasoning_tokens=0、13字段解析通过；原默认10秒两次及20秒两次无响应沿§3.25保留。对照支持默认隐藏思考为主要耗时原因，不推定网络/供应商整体故障。
- 最小修复：仅 `backend/services/memory_retrieval_pipeline.py::RewriteProvider` 对已核实当前型号关闭Step1.5隐藏思考；其他型号不附加未核实参数，Prompt/四路字段/InnerMonologue保留，Step5回复及旧Prompt Test仍沿既有输出/thinking。002参数字典§2对回复计数封装/thinking的限制继续有效，本次不是为了沿用disabled-thinking计数样本修改回复设置；counter/64预留/共享schema/权限/使用保护不变，无时限/重试扩张。原源码保存在 `/private/tmp/lxm-m8-20261012/memory_retrieval_pipeline-before-mode-fix.py`，新请求模式须随020代码版本冻结；先前新改写失败只保留故障历史，不作为正式正常结果。
- 定向验证：新增 `tests/test_memory_rewrite_request_mode.py` 实际HTTP请求形状反例先1 failed/2 passed，随后与既有pipeline/query规则组合21 passed；捕获改写请求、其他模型参数不扩张及503最多一次重试。供应商故障是HTTP替身，非真实云故障；修改后的实际源码单次HTTP200/5326ms、无重试，原13字段解析通过。分别保存red/green、真实参数对照及修复后运行文件，不以解析通过代替AC20语义或最终质量通过。旧/新回复代码未改。
- 冻结准备：原97正文/24人工候选、96就绪派生索引和002/M7证据复用；实际persona3下补查C01/C04/C06/C13/C14/C23：旧链出现漏召回，以及模糊时间/指代查询选入不相关ID；所有当前输入/输出保留。初始DEFAULT_PERSONA24条继续仅作探索。正在串行补齐其余18条当前persona旧词组，随后记录24条真实新BM25词组/Question并固定关键清单、样本数与计分/分报口径。未读取新链最终选入来选择关键场景，没有修改原文结构或相关事实。
- 当前020 IN_PROGRESS，GATE-C仍NOT_PASSED（冻结未齐）；021/022及正式整合未启动，19/22。本段为恢复中间检查点，不能当020结算或质量通过。没有部署、业务清理/开放、回复模型调用、Step6或自动切模型。

### 3.27 STEP-020独立结算与GATE-C（2026-10-12）

- 前置：M7 §3.22已通过，002六份定稿及原参数证据不变；008/012/013/019已验证输出供下一步消费。源码327项冻结核对无额外变化，仅§3.26已验证Step1.5请求模式适配；未改PRD/验收/共享协议/原回复模型思考设置。
- 020原任务1：冻结同集97条只读正文快照、96条可信派生身份、同一user1可用68条；24个人工有据查询、19可回答/5无答案、24个直接相关ID计分分母；关键C01/C04/C06/C13/C14依据当前persona3旧链真实失败在新最终选入前固定。现存冲突正文保留；不修造外域非标准ID、不补缺失年份/城市，不宣称97是全业务全集。
- 原任务2：24×四路实际旧Keywords/新BM25 Keywords/完整Question全部冻结；实际persona3、关系快照、Prompt/source327/模型/编码器/索引/配置/依赖及串行负载均登记。原24旧链检索/Prompt原始结果复用，正式阶段只补同次快照回复调用，不伪造旧整轮耗时；探索性默认persona结果排除。
- 原任务3：正常24与改写降级/dense失败/BM25失败/rerank故障各6样本分别定义；故障注入是模拟，存活服务是真实。逐样本最终选入0/1/2、候选/最终覆盖、相关/无关注入、回答证据利用、总体改善/关键不退步和非关键退步解释口径已固定；无费用、日常延迟或提升幅度数字门槛。180秒、45+45、20秒及最多一次失败重试保持。
- 冻结版本 `m8-freeze-20261012.1`，本地 `/private/tmp/lxm-m8-20261012/step020-formal-freeze.json` SHA-256 `71d6cdb0b7c31b3b989f71840647c03584312ca66ddfa9bba2457c1bc9ccd473`；`step020-freeze-validation.json` 12项PASS（验证脚本字段位置错误已仅修正脚本，未改冻结口径）。冻结登记（本地留存，未随本次提交；原引用：`execution/evidence/STEP-020-正式评测冻结-2026-10-12.json`）保留要求—证据和环境边界；M8临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`）仅登记当前已验证请求适配。
- 按本轮用户明确授权履行GATE-C核对职责：020全部原完成标志齐全，**020 DONE；GATE-C PASS_WITH_RISKS**。限制为固定现存样本集、人工有据查询、私有Docker评测环境和显式模拟故障，均已在正式运行前冻结；不是质量通过或部署/开放许可。下一步021按008/012/013/019/020前置及冻结版本开始；022/正式契约整合仍未启动。
- 独立回传：20/22；没有回复模型正式评测结果、GATE-D/M8最终判定、生产清理/部署/开放或切模型。§3.25/3.26保持历史时点，正式评测发现问题不得回改本冻结。

### 3.28 STEP-021冻结同集真实评测（2026-10-12，执行中）

- 启动前核对：008 M5真实持久回填及019语音writer→新BM25证据复用，源状态/索引/隔离语义不变；012/013阶段截止、数量/预算/最终有效性和M6三入口交付证据复用；019 DotProduct全消费者与后台闭环前提不变。020 §3.27 DONE/GATE-C通过，正式冻结SHA及327项源码核对通过。
- 严格使用 `m8-freeze-20261012.1`，新链使用实际 `execute_memory_retrieval→PromptBuilder.build_memory_prompt→reserve_prompt→GuardedModelClient.send` 与官方计数、实际SQL使用保护。直接组合共享业务内核，显式私有分区；不冒称原业务H5/部署环境全链，也不写聊天消息/队列或触发Step6。M6真实主文字/OpenAPI/Step8接线证据沿原边界复用。
- 正常24样本串行运行，每样本先登记原始输入/身份和dispatching，再保存准备Prompt/保护claim，回复调用前后持久留证；同身份已有observed复用，未收口状态不盲重发。实际响应/错误及源码版本保留，收费证据不机械重跑。正常与模拟故障的真实存活服务结果分开，当前未结算AC19/AC20。

### 3.29 STEP-021真实语义缺口、暂停及A恢复交接（2026-10-12）

- 020结算不倒改：§3.27 DONE/GATE-C PASS_WITH_RISKS，冻结 `m8-freeze-20261012.1` SHA `71d6cdb0b7c31b3b989f71840647c03584312ca66ddfa9bba2457c1bc9ccd473` 不变；180秒、45+45、单改写20秒、最多一次失败重试保持。旧/新24条实际控制、97原文/96可靠派生身份、关键清单和标注均复用，没有依据本次结果重选样本/改分母/阈值。
- 首次正式C01保护错误是**评测夹具遗漏实际入口business epoch上下文**，不是据此判核心实现缺陷。无模型探针真实重现 `business_epoch_not_frozen`；仅评测脚本调用既有 `enter_business_epoch` 并设置上下文，探针实际零调用收口aborted。原C01曾进入dispatching，完整输入是否已交付无法从原记录确认；补上下文后仅mark_unknown，**不重放、不释放、不当回复成功**。不能称首次故障零回复发送；原失败输入/Prompt/身份/输出及脚本v1保留。修正后以新显式测试身份运行v2，不增加同次失败回复重试；业务源码/冻结参数/需求/共享保护语义均未改。
- 实际正常新链v2完成C01～C07共7/24；真实改写/embedding/新DotProduct dense+BM25/rerank/官方计数/同次Prompt/SQL reserve/HTTP输入交付/回复全部取证，各claim handed_off。时间分别23692/18060/21761/25614/21336/24244/22293ms；只列真实观察，不推定全天日常分位或完整硬故障覆盖。C08在检索阶段按门禁取消，未有最终选入/claim/回复结果；C09～C24未运行，正常分母仍24，不能排除失败/取消后宣布通过。四组降级、实际三查询稀疏对照、旧Prompt回复均未运行；旧24条真实检索/Prompt结果及固定三输入控制继续有效，不冒充这些未运行结果。
- **M8-AC20-01（确定阻塞）**：依据PRD §6.5规则1/4、AC20、021任务1及首完成标志；C04原输入显式否定喂鹿并问共同海边骑车目的地，实际cg Question改为一般兴趣偏好，丢否定/共同期待条件；C05原过去日本赏樱地点问句，实际cg Question变一般出行兴趣偏好，丢日本/樱花实体和地点事实意图。13字段解析成功、候选命中或回复提及目的地不能代替Question完整语义。逐路原输出和原输入在本地原始文件，无阈值弱化。
- **M8-QUALITY-02（已确认影响，完整相对判定未完成）**：C01最终无直接相关ID，未选入现存第八版正文而回复第7版；C06冻结无答案样本选择无关user记录并编造2019年份，原正文/上下文没有该年。最终选入/正文/回答分别记录。固定口径下C01～C07选入分数0/1/1/1/1/0/1，所有选入都有无关项；这是7样本部分结果，不能用它宣布24总体改善或关键不退步。其余输出/评分未核对齐全，不扩大潜在风险审计。
- 停止与不受影响核对：SIGINT取消owned evaluator，asyncio等待当前任务收口；实际 `/proc` 无评测进程。只读SQL审计9 claims=7 handed_off/1 aborted/1 unknown，原unknown保留；96身份live/ready/epoch1、无inflight，96索引任务completed；conversation_log/agent_aware_queue/agent_message均0。7完成样本逐项核对同ID当前正文及摘要、分区/owner域、总token及180秒PASS；没有重跑M6/M7同样测试。198份容器输出按3项实际配置凭据扫描0命中。完整原始错误/取消/响应只保存在本地临时证据。
- 外溢门禁与最小裁决范围：修复M8-AC20-01需修改已经冻结的Step1.5 Prompt/已验收009改写输出语义；本轮授权明确要求此类变更先交A。因此**021 BLOCKED**，本轮不自动调整Prompt、模型、相关性门槛、回复防幻觉策略或标注/标准。A先裁决仅保留主体、时间、否定、有据实体和具体事实意图的Prompt最小修复；登记新版本并说明哪些冻结/证据需要更新，保持样本/质量标准及硬限。QUALITY-02先用已存候选/来源/实际重排查路由及选入传播，不借此扩大共享参数或已验收核心行为改造。
- 独立交付：阻塞核验及SHA索引（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-真实评测阻塞核验-2026-10-12.json`）；源码HEAD仍 `9c6f9855f5f2808a21c9e6bd761847198df2d516` 加冻结工作区327项SHA。新业务改动仍只有RewriteProvider特定型号thinking请求适配，21项定向测试及真实模式验证沿§3.26直接复用。M8临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`）仅该实际增量，不写未通过质量或未部署事实。
- 最终交接登记核验：`/private/tmp/lxm-m8-20261012/rewrite-resume-handoff-verification.json` PASS，327冻结源码/002六份/GAP29源码与23证据无偏移；M7 55及继承167仅已登记RewriteProvider差异，25受保护文档仅INDEX/manifest必要导航变化。STEP只改§3、§3.22 M7判定不变，31原始证据SHA匹配；776份本地证据/新导航记录按3实际凭据扫描0命中，`git diff --check` PASS。本项是交接登记复核，**不是正式契约整合后验证**。
- 恢复位置：本§3.29→A裁决冻版本/009语义修复→定向真实验证及冻结有效性登记→021剩余正常/三对照/降级/旧回复/完整质量和增量对账。原unknown执行不得盲重发；C08取消无claim、不当失败已恢复结果。020无需无依据整套重跑；所有未受影响M1～M7证据继续复用。
- 本轮20/22，M1～M7 VERIFIED；020 DONE/GATE-C通过，021 BLOCKED。**022仍NOT_STARTED**，其前置021未通过，不能提前标IN_PROGRESS或进行演练/总对账/正式整合；022保持IN_PROGRESS的授权适用于实际启动后。正式契约整合/整合后验证未开始，未提交 `CONTRACT_MERGED_PENDING_VERIFICATION` 或 `CONTRACT_VERIFICATION_READY`，未裁决GATE-D/M8 VERIFIED；未部署、实际业务清理/开放/旧库退役或自动切模型。

### 3.30 M8两项阻塞根因审核、最小修复与版本裁决（2026-10-12，交下一轮执行）

- **本轮裁决**：M8-AC20-01和M8-QUALITY-02均保持OPEN，021仍`BLOCKED`；批准下一轮仅修正Step1.5模板的分路说明、语义保持指令及少量通用示例，并建立`m8-freeze-20261012.2`。本轮只读复核最终源码/已存真实输入输出并更新本§3；没有实施该修复、调用模型或重新运行评测。020的`.1` DONE/GATE-C PASS_WITH_RISKS保留原时点，**.2目前仅修订范围获批，尚无实际冻结文件/SHA或GATE-C结论**。
- 依据与版本：PRD §6.5规则1/4、AC20、§11.5，021任务1～3/原完成标志，002已确认分路/参数，以及§3.27冻结和§3.29原始阻塞。源码HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`，冻结工作区327项SHA逐一匹配；31项原始证据索引SHA匹配。复核证明 `/private/tmp/lxm-m8-20261012/m8-blocker-review-proof.json` SHA-256 `bc68dd14a674ee268756582835daa906a71697676a8e0d9bdb75c7fa69a34f88`；完整正文、实际Prompt和原始模型输出仍只保存在本地隔离证据，沿原阻塞索引（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-真实评测阻塞核验-2026-10-12.json`）取用。不是新增模拟运行证据。

**已确认传播位置及影响**

| 对象 | 真实证据核对 | 根因/裁决 |
|---|---|---|
| C04 / AC20 | 原问句否定喂鹿、问与用户共同期待的海边骑车地点；实际cg Question改成一般兴趣偏好，另启cp通用相处/回复策略。最终16条=2直接相关+14无关；否定和共同期待未保留，虽命中直接正文也不替代AC20。 | 模型原始JSON已丢语义，解析前发生；当前分路说明/示例存在把具体事实泛化成偏好或回复策略的歧义。修复模板，不能凭回答出现地点宣布语义通过。 |
| C05 / AC20 | 日本/樱花还在Keywords，却从实际cg Question丢失；过去赏樱地点变一般出行兴趣偏好。最终8条=1直接相关+7无关，当前京都正文确已选入。 | Question是dense及rerank实际输入，关键词命中不能代替完整Question。不是正确候选在预算阶段被删；针对有据实体和具体事实意图修复模板。 |
| C01 / QUALITY-02 | 实际仅启ck，Question为一般UI改稿流程/次数；已就绪的第八版两条源ID `character_global_a9abe70e1acf_0` / `character_global_abb860d87aa3_0` 属cg，被实际ck类型filter排除，未进入候选。最终3条全无关，回答第7版无选入依据。 | Step1.5把角色当前经历误作职业知识并泛化查询，是正确域候选缺失的已确认上游原因；后端按既定type filter执行正确。不得跨域放宽filter、改共享门槛/预算或将回复错误视为已随路由修复。 |
| C06 / QUALITY-02 | 最近上下文明确“你”去日本两次并在京都赏樱，事实主体是角色；实际cg跳过，Question虽写林小梦却落user。user_id=1过滤正确；最终8条同用户无关记录，未选入已有次级支持cg正文 `character_global_d0b6e4fb39d0_0`。原上下文、最终Prompt及97原文没有2019，回答仍编造该年。 | 已确认主体/事实分路错误及独立的无答案回答失败；这是语义误取同用户记录，未发现跨用户泄露。查询修正可能改变回答上下文，**尚无证据证明足以消除年份编造**；未知年份标准不变，不能关闭此项或自动改回复模型。 |

- 四例原输入及有据上下文均实际进入Step1.5 Prompt；模型 `doubao-seed-2-0-lite-260428`、`stream=false`、已验证`thinking.type=disabled`与原调用参数匹配。provider原始Questions与解析后的四路Questions逐项相等，实际HTTP均200、无改写/通道/rerank降级。rerank按value发文档、响应index→ID/当前正文逐项对应；owner/分区/正文hash/最终Prompt/交付保护核对通过。无已确认映射、分数方向、索引就绪或身份失效缺陷支持本次修改这些组件；只是四例范围内的根因定位，不推定全套021已通过。
- 当前模板已经有主体/实体/否定/模糊时间保留规则，不能记作规则完全缺失。**模板诱因是有依据的推断**：cg说明偏重外貌/性格/兴趣/价值观，角色自身经历与职业知识边界不清；user说明未充分区分消息作者与事实主体；关系模块说明易诱导通用回复策略；既有少量示例未覆盖这些事实分路对照。原始JSON违约为确定事实；哪条具体模板文字导致何种概率变化尚未通过A/B证明，最小修复效果仍须真实模型验收。

**下一轮批准的实施边界**

- 业务源码仅限 `backend/services/query_rewrite_service.py::_build_step1_5_prompt`、`_memory_few_shot`：澄清既有四域的主体/事实归属，角色自身过去/当前事实沿既有cg检索，ck仍是知识/技能，user仍是用户事实，cp仅在实际需要用户专属关系/态度/约定时启用；消息的user角色不能直接决定事实属于user。强化具体待查事实/未知槽位、有据实体、共同对象、时间与否定/限定条件的保留，不把事实问句改偏好或建议。用少量通用示例验证边界，不把冻结样本的正确版本、年份或目的地写入模板，不新增样本ID特判、解析后修词/跨路补查或答案提示。
- 保持13字段/字符串协议、原skip/presence/fallback、CandidateKeys及内心理解语义、上下文装载和所有调用方同源关系；不改变记忆结构/事实、不增加调用。模型、请求thinking适配、temperature/max_tokens等原参数、编码器、索引、类型/用户filter、rerank/value映射、0.1门槛、TopK、模块与总预算、官方计数器、执行/保存/权限/并发/历史保护及Step5回复Prompt/模型/用途均不在本次修复范围。硬限继续180秒、45+45、单改写20秒、最多一次失败重试；不通过缩减断言、改变标注或重复成功采样掩盖失败。
- 允许在既有改写测试补充受影响模板/字段/调用边界的定向验证；静态或模拟通过不能替代真实AC20。隔离评测脚本只可按新源码/Prompt/控制输入登记实际版本与复用条件，保留v2已修正的epoch上下文；不通过脚本覆盖Question、筛掉坏候选/回答、改变评分或给回复正确答案。共享调用方模板行为有中等影响风险，下一轮须定向核对主文字/OpenAPI/Step8/诊断及只读预览实际装载/消费来源；不因此全量重跑未受影响M6/M7权限/分页/存储或收费流程。
- C01/C06同时验最终ID、当前正文及回答证据；C06必须按原无答案/未知年份口径独立判断。若主体/Question已正确但仍无关注入或编造年份，保存该新版本原输入/输出/候选/Prompt/正文证据，021继续BLOCKED，交A裁决实际剩余原因；**不在本授权内追加回复模型/回复Prompt改造、后处理事实过滤或共享参数调整**。任何需改变共享契约、需求或已验收核心状态/保护行为的发现同样暂停受影响部分。

**新冻结版本和证据有效性**

- `.1`冻结文件及SHA `71d6cdb0b7c31b3b989f71840647c03584312ca66ddfa9bba2457c1bc9ccd473`不可覆盖。`.2`落盘须包含最终实际模板/源码SHA、评测脚本版本及新链24条实际BM25词组/完整Question控制；只替换本次实际变化的版本及派生控制，登记精确差异。实际修复完成且定向真实语义核对后，按020原职责做新冻结/GATE-C增量适用性核对，通过才恢复021正式评测；本轮不预判`.2`GATE-C。
- 不变项：97原文/96可靠索引身份、旧/新共同68条eligible范围、24查询/有据上下文、19有答案/5无答案、微观计分分母24、关键C01/C04/C06/C13/C14、全部相关/次级支持/无答案标注、逐样本选入与回答质量口径、关键不退步/非关键解释、正常与四降级分报、三查询对照及负载。模型/编码器/索引/配置及原时限/连接收口/恢复约束不变；仍不新增费用、日常延迟或改善幅度阈值。禁止按新结果重新挑样本、造事实或重算旧链输入。

| 证据组 | 下一轮有效性与最小补验 |
|---|---|
| 原语料、查询、上下文、标注、关键清单、计分/质量方法 | 直接复用，迁移版本引用；不重新标注或缩分母。 |
| 原Docker旧链24条真实改写/检索/Prompt与旧Keywords | 旧链版本不变则直接复用，不能把新模板倒灌旧基线；旧回复仍未运行，不能写成既有通过。 |
| 96身份索引/current body/归一化/owner及008、019真实回填/语音BM25等已验证前置 | 实际索引/正文前提不变时直接复用；不重新建分区/回填整库。021原要求的增量对账仍须完成，不用既有静态就绪替代。 |
| 未改的请求模式、硬限、解析协议、管道保护、权限/历史/分页及M1～M7有效证据 | 按实际影响复用；修复后query_rewrite_service文件SHA会变化须登记，不能继续宣称327源码全相同。仅受模板装载/语义传播影响的现有调用验证需补，不将SHA变化泛化成全部前置失效。旧Prompt耗时观察不代表新Prompt耗时。 |
| `.1`新链24条控制、7条正式正常结果、首次C01故障与C08取消 | 保留历史观察/失败证据，**不作为.2质量通过证据、不混版本求平均**；共享模板改变全部新链输入，因此.2须完成24条实际新控制/正常质量，不能只复跑四个失败样本。原unknown不得重放/释放，取消无结果不得计通过。 |
| AC20/AC19、三查询实际稀疏对照、四降级各6样本、旧回复及硬故障/增量验收 | 按021原范围在.2下完成未验证部分；降级注入是模拟故障、其余真实调用须分别报告。符合最终相同源码/Prompt/模型/上下文的前置实际改写输出可直接转作该版控制，避免重复收费调用；未匹配前提不得复用。 |

- **恢复顺序**：本§3.30批准范围→下一轮实施最小模板修复/定向协议与真实C01/C04/C05/C06语义核对→冻结最终`.2`的24条实际控制/版本差异并核对GATE-C适用性→021同版本正常/三对照/四降级/旧回复及完整质量/时限/增量对账。旧收费证据和未改前置先映射复用；无新变更/失败/具体影响时不全量重复。若只改模板仍未满足质量则按上项交A，不跳到022。
- 交接登记核验：`/private/tmp/lxm-m8-20261012/m8-blocker-review-handoff-verification.json` PASS；仅STEP §3变化、历史§3.29及M7 §3.22原结论未改，327冻结源码和31原始证据SHA未变，INDEX/manifest/M8临时契约及原`.1`冻结未改，`git diff --check` PASS。本项为只读审核与记录交接核验，不是新真实评测或正式整合后验证。
- 本次实际契约增量为0：只作范围/版本裁决，尚无新实现事实，不改M8临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`）或正式契约。完成数仍20/22，M1～M7 VERIFIED，021 BLOCKED，022 NOT_STARTED；正式整合/整合后验证未开始，不提交READY、不判GATE-D或M8、不进入022，不部署、清理业务或开放。本轮交接后停止，由用户手动进入下一轮执行。

### 3.31 最小模板修复实施、四例真实验证及残余质量暂停（2026-10-12）

- **授权与实际实施**：消费§3.30裁决；冻结前先验证C01/C04/C05/C06。只修改 `query_rewrite_service.py::_build_step1_5_prompt`、`_memory_few_shot` 的分路说明/语义保留指令及4个通用示例：角色自身事实与知识技能分开、消息作者不替代事实主体、cp不因需要回复自动启用，保留具体待查事实/未知槽位、实体、共同对象、时间和否定。无冻结答案、样本ID特判、跨路补查或解析后修词。两个函数之外AST与原源码一致；原327项源码仅该文件变化，旧SHA `82c1069084401977f23fe95511aa3d825f88fe6e17d7fe0271291b044170426b` → 新SHA `07ab8abaf37330ec50f0a81026d1d1b63eebd7843ee259e04c277f6f48b56242`；HEAD仍 `9c6f9855f5f2808a21c9e6bd761847198df2d516` 加工作区SHA。已仅复制至自有Docker `lxm_m8_eval_0498495e`，原业务容器未部署。
- **前置/口径不改**：旧冻结 `.1` 文件/SHA和原语料97/索引96/共同eligible68、24查询/有据上下文、19有答案/5无答案、关键5、相关/次级支持/无答案标注及计分/质量口径不变；008/012/013/019及M1～M7未受影响证据沿§3.30复用。模型/调用参数/thinking适配、编码器、索引、0.1门槛、TopK、预算/计数器、回复模型/Prompt、13字段/skip/presence/fallback、共享状态/保护/权限不改，180秒、45+45、单改写20秒、一次失败重试不改。新模板SHA差异已登记，不宣称M7原源码指纹全相同。
- 验证次序及边界：复用四例已存真实失败输出作修复前RED，不重复收费调用；隔离Docker执行现有改写/请求模式/管道/只读预览定向回归 **22 passed、2 deselected**（两个未受影响旧Prompt Test案例按范围不重跑）。实际pytest入口仅该四文件，`-q -k 'not legacy_prompt'`；HTTP为桩，不能代替下列真实质量。主链/Step8只读模板由同源生成函数取新说明，ASGI预览GET零模型/源操作；其余入口接线代码未变，既有接线证据复用，不把本轮说成业务HTTP/浏览器整套重测。
- **四例真实验证**：使用既有隔离DB/Redis前缀/新库测试分区，实际共享kernel→真实改写/embedding→DotProduct dense+BM25→真实rerank→官方token计数→同次Prompt/SQL reserve→GuardedModelClient实际回复。脚本v3只限定四例及新证据命名，保留v2 epoch上下文修正；报告标为冻结前定向验证和 `.2-candidate`，引用 `.1` 仅作原口径基线，没有伪称正式冻结/正式24样本结果。每例单次改写、四路字段/字符串与CandidateKeys协议有效、无实际服务故障/模拟注入；没有手工替换Query/候选/回答。

| 样本 | 原要求的核心改写语义核对 | 实际最终选入与回答 | 固定选入分数；实际整轮/改写耗时ms |
|---|---|---|---|
| C01 | cg保留角色/刚刚/甲方/UI/修订版本，ck等跳过；不补版本答案 | 第八版两条直接正文进入Prompt，回答第八版；仍有3条无关正文，不给完整质量PASS | 1；25253 / 5313 |
| C04 | cg保留共同对象/期待/海边/骑车/吹风/地点、非喂小鹿限定；通用cp不再启用 | 2直接+6无关，回答含镰仓；额外地点/场景细节不作为已证实事实 | 1；22471 / 4814 |
| C05 | cg保留角色/以往/日本/樱花/具体地点，不再泛化偏好 | 1直接+5无关，京都有据；回答“两次都特意赶樱花季”超过原正文只证明日本两次/曾在京都赏樱的范围，不宣布回复完整通过 | 1；20283 / 4655 |
| C06 | 从原近期上下文解析林小梦/日本京都/樱花/那次发生年份，cg启用、user跳过，Question不补年份 | 1条已标注次级支持+4无关；真实回复编造2023。原上下文/实际最终Prompt/97原文均无2023，未知事实未保留，**质量FAIL** | 0；22273 / 5136 |

- 四例核心改写语义修复有据，**不是AC20完整通过**：其余20样本、套话/模糊时间等全量子项未验证，M8-AC20-01不能仅凭四例关闭。新24正常/三实际稀疏对照/四降级各6/旧回复/完整相对质量及增量对账仍未齐；不把这四例或旧`.1`七条混版本汇总，不能推定总体改善/关键不退步。这里只报告各例实际耗时，不新增日常延迟或改善数字门槛。
- **残余根因证据与门禁**：C06正确分路后仍失败，满足§3.30明确的暂停条件。实际19条rerank请求只传value，响应index→正文/ID/分数逐一正确；最终按既定0.1门槛、排序和数量执行。4条无关正文分数分别 `0.1253118493/0.1193387684/0.1186289383/0.1082568524`，均达到原门槛，次级支持分数 `0.2078636675`。未发现ID/正文映射或owner错配；新Question正确不能保证低分误相关被排除，也不能保证回复模型保留未知年份。继续修复需裁决选入证据准入/未知事实回答约束的最小范围；本轮不擅自调共享门槛、预算、排序、回复Prompt/模型或新增后处理。核验脚本最初误把已按rerank排序的快照当成请求顺序，改为验证实际请求index→value/ID/全部19分数及门槛/排序；修正的是核验脚本假设，未改业务或降低原断言。
- **停止/持久状态/凭据**：四例均实际handed_off，owned evaluator已退出、无残留进程。只读SQL审计13 claims=11 handed_off/1 aborted/1 unknown，原unknown继续保留，不重放/释放；96身份live/ready/epoch1、无inflight，96索引任务completed；conversation_log/agent_aware_queue/agent_message仍均0。203份容器证据按3实际服务凭据扫描0命中。没有触发Step6或写聊天业务行；仅自有评测claim/命名空间缓存按实际链运行，不能把模型输入交付称零外部调用。
- **冻结与结算**：由于四例已出现约定残余质量FAIL，停止后续冻结/正式评测推进并交A；没有继续花费生成其余20新控制或实施外围补丁。`m8-freeze-20261012.2`仍仅candidate源码/四例实际输入输出，未落盘正式冻结文件/SHA，**新GATE-C NOT_EVALUATED**，不得把旧`.1`PASS_WITH_RISKS直接移植到新模板。020的旧版本DONE/GATE-C历史结论仍有效；021 BLOCKED，022原前置未通过，因此仍NOT_STARTED，不能为满足终止点措辞提前标IN_PROGRESS。正式整合/整合后验证NOT_STARTED，没有 `CONTRACT_MERGED_PENDING_VERIFICATION` 或 `CONTRACT_VERIFICATION_READY`；GATE-D/M8未判。
- 要求—实现—证据：本轮真实修复核验及9项SHA索引（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-最小模板修复真实验证-2026-10-12.json`），完整原输入/输出/Prompt/当前正文在 `/private/tmp/lxm-m8-20261012/targeted-template-v1-normal-C*.json` 的C01/C04/C05/C06四个单文件；`template-repair-real-review.json`记录逐例原标注判断、分数/映射及实际边界，`template-repair-stop-runtime-audit.json`为只读收口证据。原§3.29失败/原unknown/取消及旧版本证据原件保留。实际模板增量已补M8临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`），INDEX/manifest仅导航本轮证据；无正式运行事实整合。
- 交接登记核验：`/private/tmp/lxm-m8-20261012/template-repair-final-handoff-verification.json` PASS，STEP仅§3变化，原§3.30裁决和M7 §3.22判定未改；327源码仅已授权模板差异，旧31项及本轮9项原始证据SHA匹配，原`.1`冻结未改，manifest唯一且新证据导航完整，`git diff --check` PASS。该结果不是正式契约整合后验证或质量闸门通过。
- **交A恢复位置**：本§3.31 → 先审原C06及新C06原Query/实际19条重排分数/最终5条当前正文/实际可见回答，裁决残余无关注入与未知事实编造的最小修复范围及是否需新的版本边界，保留原样本/标注/质量/硬限；不在执行器内连续改模板直到抽到成功。四例改写和既有不变前置可按最终相同源码/Prompt/模型/输入哈希复用；修改会影响的输出才重新取证。裁决后再恢复未冻结的 `.2` 或裁决指定新版本的24控制/GATE-C→021全原范围；021全部通过才进入022。本轮20/22并停止，不部署、不清理业务/开放/退役，不自动切模型。

### 3.32 C06准入与年份编造原因审核、最小范围及下一轮交接（2026-10-12）

- **本轮裁决**：用户怀疑虚拟角色为了延续对话而补造事实，实际模型确实生成了没有依据的年份；“为了延续对话”是合理假设，尚非已隔离证明的动机/单一原因。C06包含两个不同问题：项目0.1准入门槛未达到原无答案选入标准；回复模型生成无依据年份，项目人格/缺事实约束与模型行为的贡献尚未分离。未发现映射、归属、旧正文或交付代码缺陷，**不能把实现按参数执行正确推成项目质量已通过，也不能把整个C06认定为纯外部问题**。021仍BLOCKED，当前明确项目侧阻塞是最终无关注入。
- 用户最新处置决定登记：**若核验证实是项目之外的模型问题，保留原质量FAIL和“不接受”的问题点，不能单独阻塞后续已授权任务**。这是推进处置的条件例外，不把原得分/标注/无答案标准改为PASS，不抹去失败样本或假称全部原AC通过；最终M8是否通过仍留最终闸门。该例外不能连带豁免独立的项目准入失败。目前纯外部条件尚未满足，年份项记录“失败、归因待分离”，不据此自动启动回复模型改造。
- 审核边界：读取当前权威PRD/002/STEP及必要实现、已存原C06和修复后C06真实证据；准入与回复因果分别独立只读复核，结论一致。没有新模型/API调用、配置写入、业务代码修改或重跑有效测试；只更新本§3。证明 `/private/tmp/lxm-m8-20261012/C06-residual-cause-review.json` SHA-256 `9cbfde2e393b8dfff0dbe9224cf7b04fd7546630f99b8dfd458041a62c2ff5a1`，原始证据沿§3.31及其SHA索引读取。

**准入链与回答链的事实**

| 最终cg正文摘要 | 实际gte-rerank-v2分数 | 原冻结标注 |
|---|---:|---|
| 日本两次，曾京都赏樱 | 0.2078636675 | 仅次级支持，不含年份 |
| 期待奈良喂鹿、镰仓骑车 | 0.1253118493 | 无关 |
| 喜欢刷搞笑猫视频 | 0.1193387684 | 无关 |
| 想再去奈良/镰仓骑车 | 0.1186289383 | 无关 |
| 正在赶UI稿，偶尔模特拍摄 | 0.1082568524 | 无关 |

- 全19条响应index完整、唯一、HTTP200；`index→实际请求value→快照ID/正文→分数`逐条正确，按降序/原稳定规则排序。5条达到0.1者恰等最终5条，没有预算或失效裁剪改出另一集合；均cg/owner0/generation1，正文hash、分区和当前正文有效。故不存在用改映射/放宽用户域/换正文来修复的依据。外部重排对无关文本给低正分是输入分数事实；**项目用何种门槛准入是独立的配置质量责任**，供应商分数不是事实正确率。
- 定稿依据重新核对：PRD §6.3正常重排按可配置最低门槛准入，允许空路、数值经评测确定；002参数字典§1明确“默认是工程起点，不承诺召回质量……021评测才能调整门槛”，`routes.r.rerank_min_score`行明确0.10“待同集校准”。因此源码符合既定比较规则但工程起点没有完成真实质量校准。原0.1不因这次失败被倒改成“以前已经合格”；当前无答案只能为空或仅预标次级支持，4无关仍grade0。
- 年份核对：修复前错误user路回答2019，修复后正确cg路回答2023；两次实际最终Prompt均没有回答中的年份。修复后实际Prompt、上下文及97正文无2023，模型可见回答新增2023和鸭川场景，年份不是渲染/解析/索引正文改出来的。项目有效系统规则强调保持虚拟身份和提供实质回应，**没有直接要求造年份**；当前记忆`DATA_NOTICE`只限制正文指令，不提供明确的缺事实/不猜测约束。人格指令与缺少证据边界诱发补全是有据推断，尚未用隔离对照证明哪一项必要或足够；不能仅凭模型最终发出年份就排除项目Prompt影响。
- 模型与调用核对：实际模型/响应型号仍 `doubao-seed-2-0-lite-260428`；实际Prompt首模块与 `prompt_builder.SYSTEM_PROMPT_TEXT` 字节相同，SHA `9bf73c922d7480423e373831d61b04d03003f14868e368dc4140afc5cf97ee2f`，persona与既有version3快照一致。三个回复/构建源码仍匹配旧冻结；`GuardedModelClient.send`仅model/单user完整Prompt/stream=false，没有temperature/max_tokens/thinking覆盖。**回复HTTP请求body未单独抓包**，参数依据是冻结源码、同一prepared对象/真实handoff和实际返回型号，不冒称存在独立网络请求取证。Step1.5的thinking关闭不能冒充回复模型的设置。

**下一轮最小修复与原因补证裁决**

- **准入修复只开放既有cg配置校准**：按原021同集校准职责，仅在自有M8隔离配置版本研究 `routes.cg.rerank_min_score`；其他路、共享默认`ROUTE_DEFAULT`、模型/索引/TopK/预算、候选/选入算法、正文、权限/保护均保持。业务代码修复范围0，不改有效业务环境配置。这是本次对§3.30/§3.31执行时“门槛保持0.1”边界的明确局部修订，**不是改变冻结质量标准或扩大共享参数改造**。实际新值尚未定稿，不能用C06单例过滤成功就确定门槛，也不把重排分数当答案置信度。
- 先复用最终模板SHA `07ab8abaf37330ec50f0a81026d1d1b63eebd7843ee259e04c277f6f48b56242` 的四例实际输出和19条完整分数；按原24查询/有据上下文/原标签补齐缺失的新链控制及校准所需实际分数，以固定统一cg值检查全部相关/无答案、最终选入/关键不退步及非关键退步解释。原旧模板七条结果不能冒充当前模板缺失分数；不得逐样本换阈值、删失败样本、改分母或靠回复随机成功选值。已有前准入服务结果只有在Query、模型/实际请求参数、分区/当前正文/编码器/索引前提一致时可复用；该复用不是手造新配置最终选入结果。校准是探索记录，定稿后冻结统一实际配置再做原正式验收；若仅cg门槛无法满足原要求，提交具体差异，不扩为其他路/算法/模型改造。
- **年份只批准两种新增原因对照，未批准回复侧修复**：复用原C06完整Prompt失败为既有对照，不再运行原链；①保持实际项目Prompt/原问题/近期上下文/persona/模型参数，仅保留已标注次级支持正文，移除4无关项；②使用同一事实正文、原问题/上下文的中性材料问答副本，移除项目人格/关系/陪伴指令，用通用“仅按材料、缺失事实保留未知”规则，不提供年份/城市答案。两副本各一次真实调用，保存精确Prompt/源码/参数SHA、可见输出、实际超时/失败和独立诊断身份。只作自有本地Docker探索性评测，不改业务Prompt/诊断API或新增诊断回复能力；不重试抽到满意文本、不重放原unknown执行。既有180秒、45+45、单改写20秒和最多一次失败重试不变；不新增已交付回复输入的盲重发，沿原收口/保护规则取证。
- 对照解释边界：项目副本仍失败、中性副本能保留未知，支持项目指令/模型交互贡献；中性副本也失败，只能证明相同模型在项目之外仍有独立失败，**不能单次推出项目完全无贡献**。移除无关项后正确，也不能把单次随机输出视作稳定质量通过。根据实际对照、传递完整性及有无项目侧待修项判定能否触发用户的外部模型问题非阻塞分支；不能预先承诺归因或转为PASS。若仍需改共享回复Prompt/人格/模型，保留最小证据再次交审核，不在下一轮自动修复。

**新冻结、复用与推进边界**

- 正式版本仍规划 `m8-freeze-20261012.2`：旧`.1`不可覆盖，`.2`此前未正式冻结，不伪造已存在的新SHA或无依据递增正式版本。下一轮每个隔离配置候选明确独立修订ID/实际值/来源，保留原`.2-candidate`四例材料；最终新冻结包含模板SHA、实际定稿cg值及配置版本、24条实际新词组/Question、原固定样本/标注/质量/负载和全部模型/编码器/索引/时限。仅有新的探索性原因副本不会改变正式业务Prompt；若后续另批准真正业务Prompt/模型/算法变化，另登记版本和受影响证据，不能混入本范围。
- 直接复用：97原文/96索引/共同eligible68、24输入上下文/19+5/关键5/全部标注及质量方法；原Docker旧链24改写/检索/Prompt/旧Keywords；当前模板四例真实核心改写；未变的embedding/索引/身份正文/归属/生命周期/权限/历史/分页及M1～M7原证据。实际source327仍仅此前已登记模板差异，本轮未新增源码/配置变化。原旧回复未运行及其他未验证部分仍未验证，不借此次审核标通过。
- 门槛变化会使cg准入/最终Prompt、完整token/预算与总量裁剪、回答/实际延迟需要按最终配置重新验；原4例0.1下选入/回复保留历史FAIL/观察，不能当新配置通过。Question/关键词/前准入召回/完整重排响应在实际服务输入与当前正文条件未变时可复用，不机械重复收费调用。模板语义未改变的四例不用重复改写；补齐原24及原四组降级/三查询对照/旧回复/索引增量对账仍是计划原范围，不扩大为全仓回归。两个原因副本不得计入正式24样本或替代其真实回答评分。
- 推进处置：当前项目准入问题仍需修复/同集验收，不能因怀疑模型而解除；年份项不自动要求改项目，也不能宣称合格。后续若项目侧准入已达标且剩余问题已核验证实属于项目外部模型局限，按用户本轮决定登记“不接受、非阻塞”、保留原质量FAIL和复现/版本，允许继续后续已授权准备；必须明示这是用户授权推进例外，**不登记全部原质量完成条件通过、不用其代替最终M8判定**。纯外部结论证据不足时列具体未分离因素，不静默套用例外，也不反复改项目或重复同一调用。
- 交接登记核验：`/private/tmp/lxm-m8-20261012/C06-review-final-handoff-verification.json` PASS；STEP仅§3变化，历史§3.31和M7判定未改，原`.1`冻结及旧31/本轮9份原始证据SHA匹配，实际模板SHA不变，`git diff --check` PASS。本项是只读审核/记录核验，不是新模型测试或正式契约整合后验证。
- 本轮实际契约增量0，只审核/裁决与更新唯一§3，不改M8临时契约/正式契约/导航。020旧`.1`DONE/GATE-C历史PASS_WITH_RISKS保留；`.2`NOT_FROZEN/GATE-C NOT_EVALUATED，021 BLOCKED（项目准入质量），022 NOT_STARTED、正式整合/整合后验证NOT_STARTED，无READY或GATE-D/M8结论。恢复位置：**本§3.32 → 下一轮隔离cg校准及两种原因对照 → 登记实际参数/归因/非阻塞条件是否满足 → `.2`冻结/GATE-C → 原021完整评测及如实评分 → 按原授权及明确推进例外处理后续**。本轮交接即停止，不直接实施、不进入022，不部署、不清理业务/开放/退役，不自动切模型。

### 3.33 M8隔离同集补测、cg校准可行性与C06原因对照暂停（2026-10-12）

- **授权与结论**：用户要求继续后续全部测试，按§3.32和既定020→021→022顺序恢复。本轮完成原同集缺失20例当前模板控制/真实选择，加上复用4例共24例；完成两种新的C06真实原因对照。发现明确的非cg准入失败、AC20时间语义缺口及项目Prompt/模型交互影响，已超出本轮仅cg门槛校准、回复侧只补证不修复的边界。021保持BLOCKED，不假称“全部测试完成”，不发布新配置、不继续冻结/正式验收或022。
- 执行依据：当前入口/manifest、原PRD/STEP/002/里程碑；使用execute-approved-work继续既定验证，不另建计划或进度。前置复核：327份源码仅既有获批模板SHA与旧冻结不同，其余326匹配；此前31+9份原始证据SHA匹配；M1～M7及020 `.1`前提未变的分项复用。未重跑有效测试，未更改原样本/标注/质量口径/模型/Prompt/共享默认/索引/时限。
- 隔离环境沿用 `lxm_m8_eval_0498495e`、数据库 `lxm_m8_0498495e6e6c4e8c`、环境 `isolated:m8_0498495e6e6c4e8c`、新库独立分区 `m8_0498495e6e6c4e8c`及自有Redis命名空间。当前模板SHA `07ab8abaf37330ec50f0a81026d1d1b63eebd7843ee259e04c277f6f48b56242`；业务源码/有效配置本轮变更0，cg实际仍0.1。源码版本为既有HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`及已核327份工作区清单，不能只用HEAD代替脏工作区版本。

**本轮真实验证与复用**

| 要求/对象 | 实际路径与证据 | 结果与边界 |
|---|---|---|
| 当前模板同集控制及真实候选→重排→Prompt选择 | C01/C04/C05/C06复用§3.31；其余20例运行自有 `/eval/run_cg_calibration_inputs.py`，实际 `execute_memory_retrieval→PromptBuilder→reserve_prompt`/官方计数/SQL保护 | 20/20观察完成；当前24例控制齐全，96路对象/13字段协议已核。新增真实rewrite20、embedding22、vector-query44、rerank22；没有为这些20例调用回复模型。它们是新冻结前探索证据，不能冒充正式021完成 |
| 完整重排映射/选入正文/分域/计数/时限 | 对全部当前24例逐route按实际请求values与响应index对照；快照ID/原文摘要/owner/当前代/私有分区及最终官方counter | 全量响应映射、降序及0.1比较、当前正文/归属/预算均通过；这些正确性不能替代相关性。实测每例retrieval及prepared均小于45秒，20秒改写/最多一次失败重试及180秒不变；未新增故障模拟或声称正式降级组已测 |
| 同集cg门槛校准可行性 | 原24标注与实际完整cg分数，枚举分数边界/中间区间；`cg-calibration-feasibility-review.json`中的frontier明确只作准入分析 | **不存在能满足全部原无答案条件的单一cg门槛**：C17/C21/C23仅user路活动，cg为空，任意cg值均不改变其当前user最终选入。未定稿/发布任何新值，投影不作实际新配置最终Prompt结果 |
| C06项目副本仅保留次级支持 | 原同次完整Prompt仅删除4无关正文，其他输入/人格/关系/时间/格式不变；实际模型、guard及官方计数；真实HTTP请求body独立捕获 | 1次真实回复，仍编造“2021年的三月底”及鸭川场景；Prompt无2021。claim handed_off，未盲重发；不能用删除无关项推定回答已修复 |
| C06中性材料问答副本 | 同一事实正文/原问题/近期上下文，按§3.32移除人格/关系/陪伴指令，通用缺事实保留未知；实际同模型/原model/messages/stream参数 | 1次真实回复明确“未提及……具体年份，该信息未知”；claim handed_off。只是新探索对照，不计正式24样本或改业务Prompt |

**确定失败、影响及最小恢复范围**

| 问题 | 需求/原冻结依据与真实差异 | 本轮可否消除及下一轮审核范围 |
|---|---|---|
| 非cg无答案准入 | 原五个无答案只能空或预标次级支持；C17选入3条无姓名的user记录，分数0.113568/0.110265/0.101830；C23选入2条无水果事实的user记录，0.122423/0.108435；C21除日本计划次级支持0.256359外，还选无关乘车担忧0.145140 | cg无候选且不占共享角色预算，调cg无效；保持各例grade0，不改标签/分母。交A核定是否仅扩大到隔离user门槛的原同集校准；不能自行扩大cp/ck或共享默认，也不从单例定新值 |
| AC20时间意图丢失 | C09原问“服装是为什么时候的拍摄准备”；实际cg Question为“最近整理的服装对应的拍摄用途”，Keywords也是用途，不含要问的拍摄时间 | 字段协议通过不替代语义；“最近”修饰整理不能代替拍摄排期。保留真实FAIL，不重抽模型输出。交A核定Step1.5通用时间槽保持的最小模板修订及新冻结版本，不改样本或提供“下周”答案 |
| 固定相关ID/分路漏召回 | C10/C12/C16的原标注直接ID分别在ck/ck/cp，当前这些路跳过、仅cg有候选，最终直接ID为0；部分cg正文含类似职业/地点事实，但并非原标注相关ID | 不倒改原标签、不把同答案词出现当最终质量通过。交A核定路由/语义还是标注前提问题，需保留本次Query、原正文和原标注对照；本轮不得修标签或扩大模板/读取算法 |
| C06回复编造原因 | 项目副本仍编造2021，中性副本保留未知；两者实际同一模型/事实/原问题；前次完整Prompt编造2023的证据复用 | 支持项目指令/模型交互影响，不证明单一原因或稳定行为；**不满足纯外部模型问题的非阻塞条件**。仍为“不接受、FAIL”；交A核定证据边界最小变更或进一步有区分能力的原因验证，不自行修改回复Prompt/模型/人格 |

- 原同集探索性最终选入grade宏均分旧0.333333→当前0.666667（分母24）；关键C01/C04/C13/C14由0→1，C06仍0。当前19有答案/5无答案标准、全部标签及关键清单不变。均分改善不能豁免无答案和AC20失败，也不能代替回复证据利用；C10/C12/C16按原直接ID记录0，不利用同义正文倒改分数。当前24的原三查询对照、旧回复、正式新回复/四组降级及索引增量对账仍未全部完成，未因此登记PASS。
- 实测隔离串行prep观察：retrieval p50 5464ms/p95 7285ms，prepared p50 6594ms/p95 8432ms；只观察、无新增阈值。四例历史回复与20例selection-only阶段分开，不拼成虚假的完整新链24总时延；旧链真实回复还未齐，不作回答质量提升结论。
- 原始证据：`/private/tmp/lxm-m8-20261012/cg-calibration-runtime-final/`保留20份逐样本及两份原因对照的精确输入、外部响应/版本与独立身份；汇总 `/private/tmp/lxm-m8-20261012/cg-calibration-feasibility-review.json` SHA-256 `debffb28e33425c0aad5e08bdf497e143f17f80e9784064ff856203e06d704d2`（原登记1666567b…为补记非关键退步前摘要，本轮仅校正登记，不改原始运行件）含24件选择+2件原因对照的摘要索引、逐例原标注比较、完整重排/正文核验及校准不能通过的证明。既有§3.31/.1原件均未覆盖。
- 临时harness预检曾以整份config比较导致请求级随机snapshot ID断言失败；未发出模型调用。只排除请求级nonce后仍逐字段核对所有有效参数，并按guard bytes原契约转换fingerprint；源语义断言未弱化。原因/配置差异及根据工具输入还原的失败脚本留本地；首次stderr只在工具记录中，未冒称独立stderr文件。实际两次原因HTTP请求body已捕获，仅model/messages/stream，无服务凭据头。
- 结束只读审计 `/private/tmp/lxm-m8-20261012/cg-calibration-stop-runtime-audit.json`：35条claim=21 aborted（新增20选择保护已明确abort）+13 handed_off（新增两次原因回复）+原1 unknown；原unknown身份不重放/释放。96 live/ready、epoch1/no-inflight及96 completed索引任务保持，聊天/AgentAware/AgentMessage表均0，无评测进程，228份容器结果中3个实际服务凭据命中0。没有部署、业务清理/开放/旧库退役。
- **版本/证据有效性**：旧`.1`SHA `71d6cdb0b7c31b3b989f71840647c03584312ca66ddfa9bba2457c1bc9ccd473`与其020 DONE/GATE-C历史PASS_WITH_RISKS保持；`.2`仍NOT_FROZEN、新GATE-C NOT_EVALUATED。当前24真实控制/分数/失败不可覆盖，后续仅在源码/Query/模型/参数/当前正文前提不变时复用。准入配置变化需重验实际最终Prompt/计数/回答；模板变化按Query影响登记新控制，不能冒用这批旧Query或机械全重跑。原因副本不是正式回复版本，不增加实际业务契约。
- **唯一恢复位置**：本§3.33→A逐项裁决user校准、C09时间槽及C10/C12/C16分路/固定标注关系、C06回复证据边界的最小范围和证据失效面→获批隔离实施/定向验证→新冻结/GATE-C→原021完整正式评测→前置满足后022及正式契约整合/验证。当前020旧DONE、021 BLOCKED、022 NOT_STARTED、正式整合/整合后验证NOT_STARTED，实际临时契约增量0，不提交CONTRACT_VERIFICATION_READY，不裁决GATE-D/M8。依已确认外溢边界停止受影响推进，不能把用户“全部测试”解释为允许改变需求/冻结标准/共享参数或回复模型。

### 3.34 M8一轮最小Prompt/隔离门槛修复、获批补标与真实验证（2026-10-12）

- **本轮授权/停止点**：用户批准先核等效正文/标注，再做必要Prompt及门槛最小修复，仅本地隔离Docker真实验证；不换模型、不改人格或质量标准，先修一轮看结果。其后明确批准C10 direct及C24 secondary两处补标。本轮完成一轮实施和24例真实正常链取证，**有局部改善但仍有残余与退步**，停止追加修复/正式冻结；021继续BLOCKED，不进入022/正式契约整合，不部署/清业务/开放，不判最终GATE-D/M8。
- 依据仍为现行入口/manifest/PRD/STEP/002/里程碑；使用execute-approved-work，2个独立只读复核分别核正文、源码差异、实际Prompt与公开回复/AC20。不新增计划/进度文档，不把抽取的模型内心理解作为公开回复或质量判断依据。
- **等效性与批准的新标签**：C10 cg `character_global_4748b83d5e7a_0`同时支持UI和模特拍摄，补为direct；C24同正文仅职业secondary，不补公司名。C12未来出行正文缺体验评价，C16公开泛称用户缺user1绑定；C17聊天方式/C21普通乘车担忧/C23休息习惯不等效于目标事实，标签不改。新标签 `m8-labels-20261012.2`：`/private/tmp/lxm-m8-20261012/one-repair-labels-v2.json` SHA `8a7691cad15f0e26d4f3a909ee7fe626f7f63eda711da0e2a0ebb011390e1a41`。原24问题/上下文/用户、97快照/96可信索引、19有答案/5无答案、5关键、分母/汇总与质量原则不变；micro相关ID分母因新增direct依法从24变25，旧/前一版/本轮均按同一新标签重算，旧`.1`和原失败不覆盖。
- **实际实现/版本**：仅`query_rewrite_service.py`两个模板函数澄清待查时间、体验评价与具体经历/未来计划、当前用户共同落实计划；加3通用示例，不含样本答案/ID。SHA `31e2ae7018d2cabcc6f755e87c3f9fa8b817a2c983267320b1240a93f6761695`。仅`prompt_builder.py::SYSTEM_PROMPT_TEXT`增加个人事实缺失保持未知/不得冒充亲历的依据规则，原人格/身份/陪伴/格式及所有业务函数不改；SHA `b0bb51e5ac00c5b6cddbf77de24360db9e92a1a20a093713d01c39974d8cc966`。实际副本无active Step5覆盖，完整新规则进入每份真实Prompt；原合法current/draft/override优先级不变。HEAD仍`9c6f9855f5f2808a21c9e6bd761847198df2d516`，327源码清单与旧冻结比325份相同、仅上述2份变化，不能用HEAD替代脏工作区版本。
- **隔离参数实际生效**：沿用`lxm_m8_eval_0498495e`/DB `lxm_m8_0498495e6e6c4e8c`/环境`isolated:m8_0498495e6e6c4e8c`/分区及Redis `m8_0498495e6e6c4e8c`。按原持久发布/epoch保护提交一个`vector_retrieval_config`版本1/revision1：cg 0.18、user 0.15；cp/ck仍0.1，共享默认仍全部0.1。持久提交及查询回执一致，其余TopK、预算、模型/端点/请求参数、编码器、索引/目标/代、180/45+45/20/最多一次失败重试逐字段不变。此值是本轮隔离候选，**不是已通过/冻结/业务默认**；实际model始终`doubao-seed-2-0-lite-260428`，原回复thinking/格式/人格不改。

**要求—实现—证据/结果**

| 原要求/修复目标 | 本轮有效实施及实际证据 | 结论与边界 |
|---|---|---|
| 无答案只空或标注secondary，不注入无关正文 | 24例真实外部改写/双召回/重排，实际SQL当前正文/归属→PromptBuilder→官方计数→reserve_prompt→guarded同模型回复；五个无答案最终选入grade均2 | 无关选入从前版5/5失败变0/5；C06仅京都secondary、C21仅日本计划secondary，C17/C23/C24为空。**选入成功不能代替未知回答保持** |
| 时间语义、等效职业及当前用户共同计划 | C09 Question保留拍摄安排时间，选入“下周”正文；C10选入获批等效cg；C16改cp且选user1私有奈良/镰仓计划 | 这些子项有真实改善。C04仍cg，保留排除喂小鹿及镰仓目标；没有为通过强行把C10只转ck |
| 四路改写独立语义/AC20 | 24/24完整13字段、96路对象、实际model/Prompt/请求参数；独立核原问题与Query字段 | **C02**把“马上洗澡”泛成后续行为，Question丢动作/即时关系；**C14**丢即时消气限定，均FAIL，答案正确不豁免。C15保留未保证前提但“是否”有陈述式模板偏差；不机械认定Keywords少UI/未词即语义反转，不新增标准 |
| 有答案最终直接选入及非关键退步 | 候选直接21/25、最终直接19/25；C07目标0.176147被cg0.18拒；C11打开cp/user但ck跳；C12仍cg而ck跳 | **C07/C11/C12 final grade0**。C07/C11前版1→0，C12仍0；C19保留一条直接正文但另一0.144121被user0.15拒，grade仍1，micro-ID损失明确记录。cp/ck未扩修；不能用调cg消除分路失败 |
| 回答利用原正文、不补造未知事实 | 24个实际guarded回复，完整实际Prompt/输出保留，独立核可见messages | C06明确年份未知，原年份编造本次消失；仍有亲历扩写。C05两次都专门京都/古街花瓣，C07错甜品，C08半小时/重复片段习惯，C09西湖拍摄/服饰安排，C10额外摄影能力，C17从未告知姓名断言均有无据细节。C24人格有自由职业/半模特半UI，但不能据此断言无供职公司/私单/完全自安排；不改变noanswer。C13更乖目标正确但绝对“不会挨凶”超出相对依据，不推定整例PASS。不把比喻、一般知识或明确未来想象一律当个人事实失败 |
| 字段/映射/持久身份/时限与完整Prompt | 每路全部真实rerank输入values→输出index/分数映射、降序和候选门槛、所有候选及选入body_hash/owner/代/私有分区、官方计数/guard及收口 | 均通过；没有身份/正文错映射或新核心状态缺陷。每次rewrite小于20秒、retrieval/prepared小于45秒、整例最大34830ms，实际总charge最大1816≤7373；固定system全文保留/实际计入总量，模块配置不改。基础正确性不等于质量通过 |
| 必要影响回归/副作用 | 4个既有文件共35个不同案例：初次29 passed/6缺SQLite驱动错误；恢复后Prompt selection 21 passed，与前次非SQLite14合计35；原断言不改 | 只读预览、旧Prompt Test当前/草稿消费、字段及Prompt预算/保留/保护定向回归通过；模型/API模拟与真实样本分开，不把mock当真实质量/完整业务API。未重跑未受影响浏览器/并发/M1～M7套件 |

- 新增真实调用：rewrite24、embedding23（缓存继续有效）、dense25、BM25 25、rerank25、guarded reply24；官方counter真实。串行正常整例p50 21078ms/p95 28545ms，retrieval p50 5628/p95 6622、prepared p50 6804/p95 8870；仅本地隔离负载观察，不当部署日常表现、不设费用/延迟/提升阈值。无新故障注入，不把原故障模拟改称真实服务故障。
- 同新标签选入宏均分：旧24 `0.333333`→前一版24 `0.791667`→本轮24 `1.291667`；5关键选择grade不低于旧基线，但C06等回复/AC20失败仍阻塞，不能用均分证明AC19/AC20、关键回复不退步或021 DONE。原正式旧回复、三查询对照、降级各组及本候选完整增量对账仍未齐，本轮不推定齐全。
- **证据/恢复材料**：逐例原始输入/外部完整响应/当前候选/Prompt/公开回复与执行身份位于`/private/tmp/lxm-m8-20261012/one-repair-runtime/`，旧原件独立保留；汇总`/private/tmp/lxm-m8-20261012/one-repair-normal-review.json` SHA `2a0965fbb0e5cd457756e6bd3081f23c5a1f62142f800e9ff54f203ff5d573b5`，含24件原始摘要及逐例原口径判定/分母/失效面；源码/输入版本`one-repair-source-version.json`，授权/范围`one-repair-scope.json`。本轮独立run_revision `m8-one-repair-20261012.1`，**未冻结**；标签新版本不等于正式020冻结。两文件和STEP修改前备份在同根目录，保留用户原改动。
- 预检工具错误与恢复：隔离副本缺既有测试/fixture及aiosqlite，按精确文件补齐并仅给副本安装0.22.1；本地compile缓存越写边界改为内存语法核验。配置harness字段名及遗漏business epoch上下文在外部业务调用前失败，前两意图无accepted记录；补回原保护后第三身份提交成功，随后比较只读Mapping对象失败，**查询/复用同一已提交身份**完成比较，最终只有一个发布版本/回执。错误原始终端片段在工具记录及安全汇总，不冒称独立全量stderr文件；未改产品/权限/epoch/幂等规则来绕过失败，未重复已handoff回复。
- 结束只读审计：`one-repair-runtime/one-repair-stop-runtime-audit.json` SHA `9c92a809f5b05e0dc3e9e87e045029027c05d135759bac6f8403dc9f9b2df430`；59 claims=21 aborted+37 handed_off+原1 unknown，新24均handed_off；原unknown不重放/释放。96 live/ready、epoch1/no-inflight，96索引任务completed；聊天/AgentAware/AgentMessage均0，无评测进程；260份容器结果对3个实际服务凭据命中0。未启动回填/业务清理、未写旧库、未部署/开放。
- **有效性与交接**：原`.1`SHA `71d6cdb0b7c31b3b989f71840647c03584312ca66ddfa9bba2457c1bc9ccd473`及历史020 DONE/GATE-C PASS_WITH_RISKS保持；26件旧当前控制/原因原件摘要再核一致，并按同新标签比较，不改原冻结果。325份未变源码对应的M1～M7物理协议/身份/权限/并发/页码/保留消费者证据复用。旧回复不能覆盖新默认Prompt，旧Query/分数不能冒用为新控制；新门槛须核实际最终选入，本轮已做，仍非接受配置。
- **根因与下一轮最小恢复位置**：本§3.34→A核C07准入取舍、C11/C12实际分路和C02/C14时间/动作槽、回复证据边界残余及C24未知/否定推论边界。实际新规则已装载，模型仍扩写；不是旧规则未加载或ID/正文错配，单轮仍不证明唯一根因/稳定失败率/纯外部模型豁免。保留同集/已批标签/质量/模型/人格/时限，不能靠改标注或降低标准消除。获批再最小定向修复→登记实际新源码/Prompt/参数/控制→新冻结/GATE-C→原021完整验收→022准备及正式契约整合/验证。当前新GATE-C NOT_EVALUATED，021 BLOCKED，022/正式整合/整合后验证NOT_STARTED；只同步M8实际临时增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`），不提交CONTRACT_VERIFICATION_READY，最终GATE-D/M8留下一轮A。

### 3.35 M8功能收口、质量风险接受与022准备/契约交接（2026-10-12）

- **USER_DECISION（最新执行边界）**：用户明确批准当前质量问题作为本阶段非阻断风险保留，不再调优；先核对最终版本功能流程证据，复用有效结果、只补缺项，通过后按顺序完成022准备、隔离演练、正式契约整合及整合后验证。022保持IN_PROGRESS，交CONTRACT_VERIFICATION_READY即停止，最终GATE-D/M8由下一轮A裁决；不部署、不清理或开放业务。
- 本决定只调整本阶段推进条件：§3.34原AC19/AC20失败、退步、未完成正式旧回复/三查询/降级质量比较保留原判定，不能记为原质量全通过或改写样本/标注/标准。原020 `.1`及历史GATE-C保留，最终候选另登记实际版本与运行前提，不追认旧冻结覆盖新Prompt/隔离门槛。
- **功能核对IN_PROGRESS**：327最终源码与§3.34版本逐项摘要全匹配；24原件全匹配。M6/M7状态、权限、分页、幂等、原45+45/20/一次重试/180秒与保护机械功能前提未变，复用已验收证据。只补最终默认Prompt下main/OpenAPI/Step8三入口诊断对照和96身份远端全量/新正文增量对账；正常真实模型24及35定向回归不重复。
- 自有 `lxm_m8_eval_0498495e`原评测DB/分区及未closed unknown claim保留，不对其reset、不释放原保护。后续022演练另用新的自有随机DB/environment/partition/Redis namespace，仍仅本地Docker隔离运行；不自动启动业务服务或清理真实环境。
- 当前020 DONE/GATE-C .1历史保持；最终候选源码/参数另登记，不重追认新冻结；021 BLOCKED（仅下面新增功能协议裁决），022 NOT_STARTED，正式契约整合NOT_STARTED，未提交CONTRACT_VERIFICATION_READY。

- **本轮实际补证**：最终功能核对及原始证据SHA索引（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-最终功能核对-2026-10-12.json`）。327源码与§3.34逐项一致；三入口3个实际API/MySQL案例通过，使用最终默认SYSTEM且诊断零回复/Step6/聊天写，provider/counter为HTTP模拟，不冒充真实回复质量。96身份真实SQL/DashVector逐个字段/当前正文/代/hash/索引ready均通过，2个真实sparse读探针通过；原评测分区只读，原unknown claim不释放。
- **真实增量与失败边界**：自有第三新库/分区两次实际voice writer源确认、两个IndexWorker任务首attempt completed，同ID代1→2和当前正文/BM25已验证；旧词真实confirmed空、新词命中。首次/第二次自有probe发生source回执未知、原120秒核实后manual_required，原intent/payload/远端文档保留，未强制确认或重新发送。完整环境/身份/恢复保护见证据；本轮共4次真实embedding，rewrite/rerank/reply新增0次，未重复原24或35有效回归。
- **M8-FUNCTION-GAP-01（新增，不能归入已接受的质量风险）**：无用户2文档的真实查询稳定返回HTTP200、整数code=0、output=null；公共`MemoryVectorClient._query`只接受array，故返回unknown/query_outcome_unknown，原“confirmed空且无跨用户文档”断言FAIL。未发现跨用户泄露，不能以documents为空或上述局部通过宣称功能全通过。官方HTTP查询文档[出参协议](https://help.aliyun.com/zh/document_detail/2510319.html)只声明output数组，PRD/002/临时契约未明确null等同空；独立复核同结论。
- **最小裁决/恢复位置**：已有可审阅 `/private/tmp/lxm-m8-final-20261012/query-null-proposed.patch`（SHA `7c1a05d7367f6511e466bed20833c316c25e555a39010cd04568e47d7885194e`），只拟在成功HTTP/显式整数code=0且存在output:null时查询归一为空，其余缺字段/错误型/错误码仍unknown；不触碰fetch/upsert/index/use/reset、模型/Prompt/参数/时限。候选预期的录制协议复现2 failed/14 passed，是未获批语义的RED，不计正式PASS。用户裁决后仅相关dense/sparse协议、空/失败通道及原自有分区真实查询回归；两代写入/非空24/三入口/M6M7前提未变结果复用，不重跑。当前未改业务源码/临时契约语义。
- **不受影响准备**：只读对账70项（35根AC、22子项、13CSTR）及160份引用证据文件全部摘要匹配；022最小7类演练范围和禁止触碰的4个目标已存 `/private/tmp/lxm-m8-final-20261012/reset-gap-map.json`，但未实际进入022/执行清理。正式整合映射只读准备179项/23新表/17新HTTP operation；已独立补齐映射提取遗漏的14个mixin继承字段，23表/17路由唯一；原映射保留、修正候选在 `/private/tmp/lxm-m8-final-20261012/contract-map-proposal-corrected.json`，这是只读准备产物，不改变实现或正式契约。按既定先后顺序等待本功能项裁决，未运行演练、部署、业务清理/开放或最终M8闸门。


### 3.36 已批准空查询兼容、022准备与最终契约交接（2026-10-13）

- **USER_DECISION**：只在成功HTTP、整数code=0且显式output:null时兼容为空，缺字段/非法形状/错误仍unknown；写入/索引/使用保护、所有时限和重试保持。定向通过后按022准备→隔离演练→正式整合→只读验证连续执行；质量风险非阻断保留、不再调优，022 IN_PROGRESS，交CONTRACT_VERIFICATION_READY即停止，最终M8/GATE-D由下一轮A判定，不部署或清理/开放业务。
- **021功能收口PASS_WITH_RECORDED_PROVIDER_ANOMALIES**：批准补丁及定向验证（本地留存，未随本次提交；原引用：`execution/evidence/STEP-021-查询空响应兼容核验-2026-10-13.json`），源码revision `m8-query-null-20261013.1`。仅 `MemoryVectorClient._query` 的显式成功null→空；327源中其余326与上一最终版本相同，AST只改本函数；新测试添加16组合和4通道case，所有原断言保留。初次16 passed＋16 subtests/4测试输入错误；仅修本轮测试字段后4 passed，共20不同case＋16subtests。已验收写入/readback保护与非空结果回归通过，不换模型/Prompt/门槛。
- **真实与模拟边界**：原第三自有分区只读新/旧词及当前正文验证通过，原writer/index不重放，新增模型调用0。本次实云dense/sparse空filter响应省略output，按本次批准边界保持unknown，不把缺字段伪认为confirmed空；原实云显式null输入的录制协议测试通过。初次强求今日云形状仍为昨日null的harness断言失败已留原件，后续按用户批准的“缺output仍unknown”核实际输入/输出，不降低项目断言或扩大兼容。云形状异常作为服务边界供A复核，安全无跨用户候选，不借此宣布服务始终无故障。
- **证据恢复**：主机重启后原host `/private/tmp`丢失；仅启动已有Docker应用和自有eval容器恢复测试环境，未改业务镜像/配置或清理业务。eval容器内三入口报告SHA与§3.35相同、96对账及两代原件恢复，24正常原始文件保留；丢失的只读映射/包装报告按当前源码重新生成且新摘要登记，不虚构旧文件或旧sha恢复。原4个受保护目标均不reset/解除unknown，恢复清单见本轮证据。
- **状态/前提**：020 DONE及GATE-C `.1`历史结论保持，未把新Prompt/门槛/本补丁追认旧质量冻结；021按本次用户授权的功能范围 DONE，原AC19/AC20失败及未齐正式对照仍原判定、作为非阻断风险/限制交A，不记原质量全部通过。008/018/019原有效输出和新功能收口允许进入022；以下记录022实际完成范围及新核心停点，022保持IN_PROGRESS，正式整合/整合后验证NOT_STARTED，未提交READY或判M8通过。
- **022局部工具修复**：真实SDK 1.0.23拒绝带HTTPS scheme的endpoint（原GRPC及只改HTTP均-2952）；最终仅`dashvector_reset_adapter`的Client参数取原URL的netloc，原HTTPS输入校验/target fingerprint、GRPC/10秒默认、delete_all/计数/unknown规则不变。中间HTTP方案实际loop冲突已撤销并保留失败，未扩大SDK生命周期改造。最终真实只读Client/get/stats/list及同run原factory prepare=count1通过，窄构造断言1 passed；原统计/零计数保护3项及Docker类实证前提未变复用。最终源码`m8-preparation-20261013.3`：327运行来源中325未变，只有批准query兼容和此SDK目标表示两处；M8实际增量（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`）只记录已实现范围，不声明整条维护工具通过。
- **022已完成实证**：隔离准备/恢复核验（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-隔离准备与恢复核验-2026-10-13.md`）及同名JSON逐项记录实际MySQL游标/完成COMMIT后丢ACK、新进程原CLI同身份恢复、completed后open前进程崩溃、非空资料/日记/朋友圈/关系值及十项指标保留。无云独立run的真实Redis Lua丢ACK只dispatch一次、日志私有归档、精确对象清理、新SQL同ID恢复/旧epoch拒绝/同reset不重清、23次MySQL发布保留最新20+受保护首版=21通过；cache callback为模拟，不等效远端memory/index恢复。自建Docker原断言的rm后create失败→新adapter只create不start/挂载与日志材料保护通过；实际只读schema为61表/23新增，ORM表/列集合一致。作用域仅自有夹具，停写proof不宣称生产全实例封闭；不重跑其余前提未变的API/浏览器/收费调用。
- **M8-022-GAP-01，核心停止条件**：自有完整run `dc757b63-260e-4c9e-b323-6cbab294494e`、DB `lxm_m8_reset_387cb640a03d436a881236df9872fdae`、partition `m8reset_40113f64b083478598`，58 SQL资源confirmed、vector-new:owned unknown、Redis/log/object pending；原CLI read实际返回unknown/epoch2/maintenance、completed_at/opened_at均空。原delete_all的供应商raw ACK/code/request_id未保存，不能区分原ACK未知与ACK确认后短时计数非零；当前count0与原reconcile仍unknown，不能以0确认原请求完成。该新目标为第5受保护目标，禁止重发/delete、apply/open、强解或以新run覆盖。已保存最小复现、原故障、输入版本、manifest/auth及只读恢复位置；未改VectorResetAdapter或M5/M6/017核心状态/保护语义。
- **全量映射与契约边界**：35根AC/22子例/13CSTR逐项映射（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-验收逐项证据映射-2026-10-13.json`）保留各自要求、实现、版本、环境及原结果，明确AC19/20风险与AC17/AC17-a/CSTR05完整准备缺口，不用根项或模拟掩盖子项。全部M1–M8有效增量/无新增依据已收齐，181项、23表、17新增HTTP、18正式落点的映射候选v2（本地留存，未随本次提交；原引用：`execution/evidence/M8-正式契约整合映射候选-v2-2026-10-13.json`）及锚点候选、18正文候选、42新增覆盖/10受影响位置刷新仅准备，31旧句冲突仍待整合。18正式文档SHA均未变，未登记CONTRACT_MERGED_PENDING_VERIFICATION，未进入正式契约验证，未提交CONTRACT_VERIFICATION_READY；不把未整合、未部署行为写成正式运行事实。
- **交A最小范围/恢复顺序**：先按隔离核验的只读命令及原run材料（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-隔离准备与恢复核验-2026-10-13.md`）核原请求独立、精确完成/目标退役证明；若需新增durable ACK/后续count收口，触及删除确认核心语义，先由A裁决，不能本轮自行扩修。恢复同run合法收口→完整资源成功及开放后仅新memory writer/index/当前正文恢复证据→核022准备齐全→应用已保全契约候选/覆盖/导航→只读正式整合验证→提交READY。候选正文/脚本另保存在自有eval `/eval/contract-candidates-only-20261013.tar`，未执行apply。原四目标未触碰；新旧质量/失败记录保留，最终GATE-D/M8仍留下一轮A，不部署或执行业务清理/开放/旧库退役。

### 3.37 M8-022-GAP-01根因审核与最小范围裁决（2026-10-13）

- **USER_DECISION/本轮边界**：按§3.36只审核原删除执行、回执和unknown收口，裁决最小修复/补证/恢复范围，登记后交下一轮执行即停止。本轮未修改业务源码，未调用真实删除/apply/open/模型或业务写；原run、清单、授权、fence及5个受保护目标保持，质量风险继续非阻断、不再调优，不裁决最终M8或执行部署/业务清理/开放/退役。
- **实证入口**：GAP-01审核与下一轮裁决（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-GAP-01-根因审核-2026-10-13.json`），含真实MySQL SELECT原件、当前SDK本地源、4个内存分支复现及安全原件摘要。原数据库`lxm_m8_reset_387cb640a03d436a881236df9872fdae`/run `dc757b63-260e-4c9e-b323-6cbab294494e`仍unknown、phase=sql、epoch2、fence maintenance、completed_at/opened_at空；58 SQL资源confirmed、vector-new:owned unknown、3资源pending。原manifest hash读回匹配，vector资源revision2、cursor=NULL、after_count=NULL，fixed_scope内before_count=1。
- **确定根因**：真实factory仅把SDK回执压成confirmed/unknown，未保留code/request_id；`VectorResetAdapter.execute`把“回执非成功”和“回执成功但count非0”都返回同一`{state:unknown}`；runner仅保存最终result_digest/通用error_code，无法还原回执，后续核实还可能覆盖摘要。默认reconcile只有退役钩子，真实factory未接原请求完成/退役证据。**安全阻断正确，回执保全与恢复接线存在项目缺口**，不能把unknown保护本身判作错误。
- **原执行分支边界**：实际result_digest为`f541413e…29a999`，与适配器直接返回裸unknown完全匹配，与服务层捕获execute异常后生成的结果不匹配；仍不能区分供应商非成功（包括SDK内已捕获的错误）与成功后非零计数。SDK1.0.23原同步默认async_req=False，Response构造已调用get；未发现忘记get/await问题，Collection源码SHA与原SDK证据一致。原供应商code/request_id仍未保存，不能宣布实际删除失败、超时或统计延迟已被证实；§3.36的当前count0仅为原时点只读结果，本轮不重复云查询。
- **最小修复裁决：APPROVED_PLAN_ONLY，交下一轮实施**。仅限真实vector factory/`VectorResetAdapter`、S15 runner向量资源的结构化回执checkpoint/核实接线及直接测试；不得扩大到M6/M5源写/017核心语义或通用存储重构。明确原SDK回执与当前空态分开，收到安全回执后、count前先持久保全；后续count非0/失败/进程退出不能抹掉已收到的事实。可使用现有`memory_reset_item.cursor`的带版本向量命名空间，绑定原run/resource/target_digest/revision，fixed_scope/manifest不可改，不新增表/列、通用状态枚举、网页接口或角色。回执仅含已校验身份/code/请求ID/同步模式/计数及固定分类，禁止服务凭据、供应商message/output正文及原始错误进入记录。
- **核实裁决**：同原记录只读核实，不重发删除。同步成功回执的完成语义须有可复核依据；accepted/布尔真值/缺失字段不冒充completed。只有原请求确切完成证据与当前精确目标空态同时有效，才可确认同目标；缺据继续unknown。独立request_completed与target_retired必须分型验证，不能把请求完成证明塞进原retirement布尔钩子伪称退役；真退役须证明迟到删除不会影响新目标。本裁决不授权实际退役、换目标/partition/目录身份或另建run覆盖原失败。
- **旧run补证/恢复范围**：先查授权范围内现存供应商原请求完成/精确目标隔离退役材料，绑定原目标、操作和请求身份；当前已核材料无此独立证明。新补丁不能追溯补造cursor=NULL旧记录的ACK。没有独立证明时，原run继续维护unknown；即使新补丁定向通过，也不能以count0、等待时间、TTL/epoch、重启、签名自报、新夹具成功或另一run强解此目标。本轮仅SELECT，不写回原资源/回执或修改manifest/auth。
- **下一轮定向验证**：详见审核JSON V1～V10。必须覆盖明确成功/错误/缺字段回执、ACK后非零及count异常、checkpoint后新进程只读恢复、checkpoint COMMIT未知及保存前崩溃、旧无ACK+0仍unknown、run/target/resource/版本错配与并发冲突不覆盖、原身份不重发且unknown不开放、完成与退役证明分型及凭据不留存。用实际MySQL/新进程验持久点，内存/供应商模拟和真实存储分别报告；只有合法收口证据齐全后才补原完整资源与新memory writer/index/当前正文恢复，不用局部PASS推定全链。
- **版本与复用**：本轮327运行源/3测试文件与`m8-preparation-20261013.3`逐项摘要相同，HEAD仍`9c6f9855f5f2808a21c9e6bd761847198df2d516`。4个分支仅内存回调，真实provider/模型/删除调用0；初始化环境变量、账号不匹配1045及辅助AST显示语法失败已保留/说明，最终复用原完整run调用者的既有连接来源完成只读核验，未输出凭据或弱化业务断言。原SQL/Redis/log/object/Docker保留证据及M6/M7/API/浏览器/收费模型结果前提未变直接复用；下轮只重测向量回执/checkpoint/CLI及实际受影响保护，保持180秒、45+45、20秒、一次失败重试及原S15 SDK10秒默认，不改Prompt/模型/门槛/样本/标注/质量标准。
- **契约与停止点**：本轮仅审核裁决，无新增已实现运行契约，M1–M8的181项候选和正式落点原状保留；不把上述PLANNED字段或未部署行为合入正式事实。022仍IN_PROGRESS、M8未VERIFIED，正式整合/验证NOT_STARTED，未交CONTRACT_VERIFICATION_READY。下一轮先落实最小补丁及V1～V9，再按原run独立证据判断是否可合法收口；缺据停受影响部分交A。恢复后依序补剩余原资源/完整空态保留无回写/仅新memory索引恢复→核022准备→正式实际契约整合→整合后只读验证/READY。只读原CLI入口和私有manifest/auth仍在§3.36链接的目录；本轮审核原件另保存在自有eval `/eval/gap01-review-20261013/`，不自动执行下一轮。

### 3.38 M8-022-GAP-01最小回执修复、定向验证及原run补证停止（2026-10-13）

- **本轮授权/结算**：按用户最新授权实施§3.37 P1～P3；最小补丁 **VERIFIED**，原run合法收口仍 **BLOCKED/缺独立完成或精确退役证据**。保持原run及全部保护，不重发删除、不以零计数/时间/epoch强解、不倒补ACK；质量继续非阻断、不再调优。022保持IN_PROGRESS，未裁决GATE-D/M8、未部署/清理/开放。
- **证据入口**：最小回执修复与V1～V10对应（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-GAP-01-最小回执修复验证-2026-10-13.json`）及其安全原件目录。依据仍为现行PRD/验证STEP/里程碑、§3.37审核；原任务和验收未改，唯一进度仍在本§3，不新建执行计划或进度文档。
- **实际实现**：仅`memory_reset_resources.py`的VectorResetAdapter/factory与`memory_reset_service.py`向量专用_external/checkpoint。先持久登记原run/resource/target_digest/不可变dispatch revision，再外调；factory明确沿用同步默认，仅整数code、合法有界request_id及已核SDK同步完成语义构成回执，不使用bool/accepted/缺字段确认。现有cursor.vector_receipt保全首份回执，count前commit；后续非零、异常或注入退出不抹回执。COMMIT回执未知只读原记录的相同回执，未保存继续unknown、不重发。
- **核实/并发**：同身份恢复只读原回执与当前精确空态；旧无ACK默认unknown，不靠count0收口。完成/退役独立证据分别校验，布尔退役、错请求/目标/资源/协议/版本及冲突回执拒绝，迟到unknown不降级confirmed。独立reader是内部可信验证口，必须先认证供应商/隔离事实，形状校验不等于事实认证；真实factory没有接入现存独立reader，CLI无自报证明/force接口。legacy_read仅绑定已有行版本的只读锚点，不代表追溯登记删除或ACK。
- **安全/兼容**：回执只留协议/操作/code/请求ID/同步模式/固定分类，postcheck只留固定状态及U64合法计数；不留供应商message/output正文或原始错误，factory请求ID包含自身凭据时拒绝。固定scope/manifest和物理表列、通用状态/HTTP/角色/参数来源不变；其他适配器、SQL清理、fence、最终完成/开放逻辑AST未变。180秒、45+45、20秒/一次重试与S15 SDK默认10秒保持；无模型、Prompt、门槛、样本、标注或质量标准变更。
- **版本**：最终`m8-preparation-20261013.5`，HEAD `9c6f9855f5f2808a21c9e6bd761847198df2d516`加现有未提交改动。相对`.3`327份运行来源只有上述2份改变，325份摘要相同；`.4`为第一版修复，随后在已批准有界留存范围补U64异常计数校验并登记`.5`，未改冻结/GATE-C。源码/测试摘要与自有Docker实际文件一致，回执/计数外其余AST相同。用户改动保留，原业务容器未生效。

| 本轮验证 | 结果 | 实际/模拟边界 |
|---|---|---|
| 最终定向断言及受影响旧回归 | **40 passed，0 failed/skip**：35新增、5旧回归 | 真SQLite/生产runner/factory；SDK边界替身，无云删除/count/模型 |
| 持久checkpoint/新CLI与worker/COMMIT回执未知/并发 | **4 passed，0 failed/skip**，最终源码 | 真MySQL、独立CLI read及独立只读恢复进程；供应商替身，故障为注入，并非真实云故障/杀死生产进程 |
| 原run保护核对 | 固定SELECT数据包与§3.37完全一致 | 真MySQL只读事务；0原run写、0云查询，未重新读取旧count推断完成 |
| 凭据及影响核验 | 已知9值扫描无命中；325份来源/不受影响AST相同 | 扫描范围和原件见JSON，不代表未知凭据的全仓审计；合法业务快照留存未改 |

- **失败保留/处理**：首个Docker缺复制夹具导致收集失败，复制原夹具后12 RED复现；追加安全检查2 RED（缺登记可补ACK、错请求证明可保存）均最小修复；异常count越界1 RED后仅补上界校验。旧零count单测缺新登记上下文1 FAIL只改夹具，原unknown/零计数不收口/不重发断言保留；最终40+4按`.5`实际源码通过。全部原始输入、输出及阶段摘要保留，未倒改断言/需求。
- **原run停止依据**：run `dc757b63-260e-4c9e-b323-6cbab294494e`/DB `lxm_m8_reset_387cb640a03d436a881236df9872fdae`仍unknown、phase sql、epoch2/fence maintenance、completed_at/opened_at空；vector-new:owned revision2/cursor=NULL/after_count=NULL。58 SQL confirmed、3外部pending。旧回执code/request_id仍缺，原清单/授权/结果摘要、当前历史零计数、前T0 seals及新夹具成功均不能补原请求完成。本轮未写原资源记录、未调用原apply/open或新真实删除。
- **复用及契约**：M6/M7/API/浏览器/模型、原SQL/Redis/log/object/Docker已验证且前提未变的证据直接复用；不把局部资源PASS推定完整S15/新远端memory恢复。已实现增量只追加M8临时契约（本地留存，未随本次提交；原引用：`execution/contract-drafts/M8-临时契约.md`）；正式18落点及覆盖原状、181历史候选未合并。后续合法恢复允许整合时，须刷新S15候选源码及cursor字段增量，不能继续使用旧源码摘要为最终证据。
- **交A最小补证/恢复点**：须取得并认证原精确目标/删除操作/请求身份的独立供应商完成记录，或精确目标隔离退役证明（证明迟到旧删除不影响新目标）；字段形状/本地签名自报不算证明。原私有材料、只读CLI入口和5保护目标沿§3.36/§3.37，新增4个自有三表MySQL夹具保留，数据库名见证据XML。本轮没有上述独立事实，按用户明确门禁暂停受影响及依赖工作，等待A裁决，不再尝试收口。
- **合法恢复后原顺序**：同原run核实收口→余下原资源/完整空态与保留无回写→仅新数据writer/索引/当前正文恢复→022准备总对账→正式实际契约整合→整合后只读验证/CONTRACT_VERIFICATION_READY。本轮正式整合/验证仍NOT_STARTED、READY=false；020 DONE及GATE-C `.1`历史结论保持，021仅获准功能范围DONE、原质量FAIL非阻断风险保持，022 IN_PROGRESS/M8未VERIFIED。到此交接停止，不自动下一轮。


### 3.39 原隔离阻塞合法收口、正式整合及本地部署授权（2026-10-13）

- **最新 USER_DECISION**：先解决新库隔离测试分区阻塞，完成022准备和正式契约收尾，再部署本地Docker；按已确认S15清理/保留范围执行，不再调优质量、不强解unknown。本轮明确授权覆盖旧的“READY后停止/不部署”执行限制，未改变清理、保留、unknown或质量原验收语义。
- **原run合法收口 PASS**：只退役自建`m8reset_40113f64b083478598`，取得供应商同步成功回执及独立认证读取“不存在”，其他分区清单不变；该名称永久不复用。真实内部验证器经现有target_retired协议绑定原run/resource/目标/revision提交，原delete_all结果仍unknown、重发0次，不补造ACK。同一`dc757b63-260e-4c9e-b323-6cbab294494e`完成62资源确认、58 SQL保留摘要一致后开放epoch2。证据：原run退役收口与新数据恢复（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-原run退役收口与新数据恢复-2026-10-13.json`）。
- **新数据恢复 PASS**：新建不同分区`m8restore_670e14f4a40b497daf`，真实writer/index首次完成；仅删除新合成文档模拟丢失，再通过原writer恢复相同ID/当前正文至generation2并BM25命中。HTTP fetch缺output仍unknown；独立SDK成功空字典确认丢失，未修改产品断言/协议。旧epoch写入拒绝，重复原reset不清新数据，资源revision未变。新增embedding2次、rewrite/rerank/reply0次，无质量调优。
- **正式整合及验证**：按原181项候选合入18份current，保留各文件已有内容/31项冲突的定向处理；追加.5向量回执API及既有JSON cursor逻辑结构，无DDL/接口权限变化。核对327来源仅原已验收.5两文件差异，181唯一正式锚点、18份链接及AST409代码对象覆盖通过，刷新70处行号；定向40断言+4真MySQL历史证据及本轮真实同run链有效复用。完整映射：正式契约整合与验证（本地留存，未随本次提交；原引用：`execution/evidence/M8-正式契约整合与验证-2026-10-13.json`）。`CONTRACT_VERIFICATION_READY`，准备及正式契约验证证据已齐；不追认原AC19/20质量FAIL或缺项为PASS。
- **实际部署 VERIFIED**：业务库`lxmfor`已由v8h通过Alembic升级v9g；S15 run `1f31e89e-2a43-4ccf-a28d-f0faae06450e`确认70资源、58 SQL保留摘要一致，UTC `07:06:48.023311`完成、`07:11:05.251690`开放epoch2。旧账号数据库凭据已失效；旧库`memory_long_collection`取得同步删除成功及独立-2021，6个其余旧测试分区取得各自退役回执/-2022，所有退役名称不复用。只保留新库default；原unknown行不改、不重发。
- **部署发现的最小修复**：v9a的33字符revision超出旧MySQL VARCHAR(32)，先以真实CLI测试复现1406，再扩版本列至128；仅回滚已核实为空的两张本次未完成DDL表后正常升级，不手工stamp。空库查询可缺output，保持远端unknown；列表在精确SQL身份域完全无记录时直接空态，存在任意状态身份仍严格核验。该读优化不改召回参数/回执/索引或强解未知。compose固定amd64以支持原dashtext，构建排除凭据、归档与macOS元数据。旧Wi-Fi地址失效，使用既有voice-local叠加仅绑定127.0.0.1。
- **本轮验证**：候选镜像定向98通过/2跳过/16子断言（跳过的host Docker操作已由实际S15补实证）；空列表及关联102通过/16子断言（先99通过，另3为缺scripts挂载，补只读挂载后3通过）；新增真实MySQL CLI迁移1及现有迁移/发布夹具1通过。7个空目录用例先4红/3绿再全绿；未弱化已有断言。最终镜像`m8-local-20261013.6`，实际327份backend/Alembic源码与工作区一致；相对.3仅原.5两份、v9a及本次列表服务4份差异。现有质量/硬时限证据按前提复用，无新增完整质量评测。
- **实际用户可见与重启**：H5首页/后台登录可显示；真实鉴权API的文字历史、时间线、H5/Admin四类记忆列表为空，旧语音正文详情/轮次/debug为404，用户旧通话仅保留状态元数据。账号/姓名昵称/亲密度/成长及朋友圈/配额/计费/统计按T0摘要保留，38条成长、33帖子/14评论/11点赞、7账本/110日统计保留；真实业务日记原本0条，不据此冒充非空日记测试，后者复用019隔离证据。开放后真实新正文写入/索引→重启→当前正文/BM25仍可读；再正常删除自有探针，live=0，保留正常期限的1个删除墓碑。重建最终容器和重复同run均不清理、资源revision/开放时间不变，旧正文无回写。原测试容器停止但保留证据。
- **交付/闸门结算**：022准备DONE、实际清理DONE、业务开放DONE、旧库退役DONE；正式18份/181原映射加回执、迁移版本列及空态增量已实际合入并核验，`CONTRACT_MERGED_VERIFIED`。M8/GATE-D按最新用户明确接受的AC19/20质量FAIL/缺对照风险收口，结果`PASS_WITH_RISKS`；不改成原质量全PASS，不继续调优。全部35根AC、22子项、13约束沿原70项映射补本轮完成附录，无新STEP。唯一剩余项为原已接受风险及延期项，无本轮实施阻塞。
- **恢复位置/证据**：本地Docker完整部署证据（本地留存，未随本次提交；原引用：`execution/evidence/STEP-022-本地Docker部署收口-2026-10-13.json`）；入口`http://127.0.0.1/`、`http://127.0.0.1/admin`。本地离线备份及回执在`data/s15-offline/1f31e89e-2a43-4ccf-a28d-f0faae06450e`（目录0700/文件0600，Git忽略、镜像构建排除、应用未挂载），原临时路径继续保留用于既有证据定位。只能前向修复/恢复开放后新数据，不回切旧库或恢复旧正文；普通启动不重新执行S15。

<a id="memory-v32-followup-closure"></a>

### 3.40 后续修复、积压清零与新模型部署收尾（2026-10-15文档同步）

- **本轮授权与结算范围**：用户要求同步现有文档及进度，补入后续修复、积压清零、新模型部署结果，保留已接受风险、延期项和未验证边界；不改代码、配置或数据，保留工作区既有改动。以下10月13～14日运行结果沿用其原始记录，不冒充本轮重新执行；§3.39及更早阶段结论原样保留，不新开STEP或重判历史闸门。
- **当前完成结论**：本期22/22开发及本地部署完成，正式契约已整合，按用户接受的质量风险交付。部署后的遗漏接线和新增失败已修复，既有索引积压已清零；本轮完成的是文档同步，不表示原AC19/20全部通过，也不表示生产部署或新模型完整质量验收完成。

| 后续事项 | 实际处理及有效证据 |
|---|---|
| 普通索引执行器未接应用生命周期 | 10月13日补齐lifespan启动/停止及配置变更后的有限恢复；仅依赖当前DashVector目标、fence/epoch和编码器，不依赖回复、embedding或rerank配置。新业务写入约3秒自动ready；过期旧任务仍按原截止规则转人工，不自动重开轮次。当日部署记录（本地留存，未随本次提交；原引用：`../../../data/runtime-checks/memory-index-20261013.json`）保留当时后台新增仍返回20129的失败边界。 |
| 后台原因反馈及新增20129 | 列表只展示匹配当前身份/代/hash/encoder/操作的维护原因；缺失证据明确不可用。10月14日新增专用只读gRPC预检，沿用冻结目标，仅明确成功空结果才继续首次create；通用HTTP缺output仍unknown，更新/删除/未知对账规则不放宽。真实浏览器单次新增code0，约4.05秒自动ready、attempt1/round0，远端dense/sparse及身份完整匹配，临时记忆正常删除。新增部署验收（本地留存，未随本次提交；原引用：`../../../data/runtime-checks/memory-create-20261014.json`）。 |
| 旧索引积压清零 | 10月14日按当时82条manual基线，先试恢复3条（本地留存，未随本次提交；原引用：`../../../data/runtime-checks/memory-backlog-pilot-20261014.json`），再按10/10/10/10/10/10/10/9恢复79条；均走原重试API、revision及幂等协议，不改原正文/业务字段/dense向量，不改未知对账。最终83条live/ready，无manual/pending/running/retry_wait；不是“83条全部人工重试”。分批及收尾记录（本地留存，未随本次提交；原引用：`../../../data/runtime-checks/memory-backlog-batches-20261014.json`）中逐条远端/浏览器、未选任务/identity/operation及fence比对通过。 |
| 清零后真实新增闭环 | 同一记录的`real_create_followup`于10月14日11:22（北京时间）验证：浏览器仅新增1条临时记忆，约2.18秒自动completed/ready，零人工retry；正常删除并核实墓碑及列表移除。原数据及操作不变，最终恢复83条live/ready、4条deleted，任务87条completed及1条原superseded，无积压；历史回执按协议保留。 |
| rerank接口及模型可配置、新模型生效 | `.env`和示例均显式配置`ALIYUN_RERANK_ENDPOINT`及`ALIYUN_RERANK_MODEL=qwen3.7-text-rerank`；代码不再默认接口/模型，可选独立凭据留空复用既有百炼凭据，已发布配置仍优先。有效配置/后台测试/profile同源，请求按现协议仅传top_n，不改变四路编排、门槛、预算或unknown语义。10月14日14:28（北京时间）本地镜像`lxm_for-backend:rerank-qwen37-20261014-dac2edd7`部署完成，仅重建backend，保留原运行环境/端口及MySQL、Redis、Nginx容器；运行301份backend源码与工作区一致。新模型部署及调用记录（本地留存，未随本次提交；原引用：`../../../data/runtime-checks/rerank-qwen37-20261014.json`）。 |

- **新模型运行验证范围（10月14日）**：有效配置及冻结快照均为`qwen3.7-text-rerank`、source=env、version=0、epoch2。运行容器对固定合成文本真实重排1次、2个候选，状态ok、分数合法，约240ms；真实HTTP测连code0/connected=true，约250ms。`/admin`、`/pages/chat.html`、`/openapi.json`均200，执行器正常启动，验证前后业务状态一致。该记录不包含新模型的真实业务上下文诊断、聊天回复或Step6写入；当时业务诊断因未授权向外部供应商传输私有上下文被自动审批拒绝，已改用固定文本验证，未执行被拒命令。
- **本轮新核对与证据有效期（10月15日）**：上述5份本地运行JSON均存在且可解析；索引/新增修复的15份源码与10月14日记录哈希全部一致；`.env`的两项rerank配置存在，完整文件哈希与已部署记录一致。只读Docker快照确认`lxm_backend`运行于上述新模型镜像；未重跑模型调用、浏览器、业务读写、质量评测或部署，不能据容器运行状态推定当日端到端全部正常。301份源码一致性及调用时延仍是10月14日结果，不标为本轮重验。
- **已接受质量风险继续保留**：AC19效果/回复质量、AC20语义质量的原FAIL及C02立即行动、C14即时安抚、时间语义等残余失败不改判；正式旧回复、旧关键词/新BM25关键词/完整Question三方案同集对照及降级质量组等缺项仍未补齐。后续候选及新模型未重新完成正式冻结和完整同集质量验收，不能由“可调用／积压为0”推定召回或回复质量达标；§3.34隔离cg/user候选门槛不据此宣称已全量部署。继续按用户取舍停止调优，费用不作门槛，日常延迟/提升幅度仅记录观察。
- **延期及排除项继续保留**：F13/F14、RQ-03/04语音实时召回与会前加载算法升级仍归RP-004；RQ-02同Key经历历史/事实版本仍归RP-003，保留同Key覆盖。内容结构、Key调整、原子化/历史重抽取、新记忆/意图路由等不因本次收尾纳入交付；本期语音仅含已确认写入、存储/score适配及兼容回归。原70项验收映射及35根AC/22子项/13约束不变。
- **恢复位置与未验证边界**：继续使用本节唯一状态及上述原证据；正式行为见current契约。旧回滚镜像标签`lxm_for-backend:before-rerank-20261014-dac2edd7`仅为部署记录中的恢复参考；其临时runtime/rollback override文件当前已不存在，本轮未验证回滚可执行性，不把临时路径作为可直接复用的部署入口。沿§3.39只前向修复开放后新数据，不回切旧库、不恢复旧正文、不强解unknown，普通启动不重做S15。生产环境、跨版本长期运行及新模型完整质量验收未由本轮补证；无需为文档收尾重新执行清理或业务写入。
- **文档同步验证 VERIFIED**：本轮仅更新5份现有入口/进度文档；新增或更新行中的37个本地链接及新锚点可解析，Markdown围栏/行数预算、manifest JSON及差异空白检查通过。manifest仅更新3个现有条目的检索关键词，ID、状态、权威标记和关系不变；原§3.3～3.39记录及§4之后需求/验收正文不变，配套PRD、current契约及1056份非docs文件（含源码、配置和`.env`）与本轮前快照哈希一致。该VERIFIED只结算本次文档工作，不替代原功能、部署或质量验收。


#### 生产发布补记（2026-10-15，实际执行）

- **授权及边界**：用户授权通过指定GitHub仓库发布到杭州ECS，不备份线上数据；阿里云旧向量库及其中数据保留，只切换到新库。最新决定是临时固定生产库名、通用配置修复延期。本补记为真实生产执行，不将上述10月13～14日本地结果冒充生产证据；原质量风险和延期项继续有效。
- **发布来源**：发布分支 `codex/deploy-memory-v32-20261015`，提交 `62f7955f6619e60727ba5854b42a98dfb954db15`；生产快照仅在后端常量及两处后台表单将测试库字面量换为 `new_lxm_memory_long_collection`，工作区本地测试目标保持原值。白名单导出489个运行文件，聚合SHA256 `ac398f1406bd493b37b5062cee46dbd01702247999e905d3df07fbcf6fc069d1`，排除测试、文档、`.env`及线上数据。运行镜像 `sha256:e93e293e8fa309db3bcff5883ffde37ce3ba60c48becfbc142033780eca1be56`，484个实际运行来源文件与快照逐项一致；本地主工作区、真实Git index及既有用户改动保留。
- **环境和兼容配置**：线上原有Embedding v4、回复模型和密钥沿用；补齐三项公开env字段：`MEMORY_RUNTIME_ENVIRONMENT_ID=prod-ecs:lxmfor`、DashScope rerank地址及`ALIYUN_RERANK_MODEL=qwen3.7-text-rerank`。原召回配置v4只有TopK/threshold，不能被新链读取；通过原持久发布服务提交v5的约定四路20/20/8/0.1，旧值留只读legacy，publish `01a13db2-6216-7ece-bda3-b6691ad9e9ea`；未调优门槛。数据库由v8h迁移到 `v9g_memory_diagnostic_001` 成功。
- **封闭、清理与保留**：旧Nginx/backend正常退出、restart=no，80/443/8000无监听，无其他后端进程，宿主cron仅证书续期。生产专用保留旧向量/不备份入口复用S15 SQL/Redis/断点和防重清保护，不伪造删除或凭据撤销回执。run `81d3901d-e39c-4766-9d23-b750739a4211`，manifest `b11854dd941541559b90ab42cbd4b76376548491e0d7d8e990d23b5ab4aaac73`；66项confirmed，58张表保留字段摘要独立核对一致。清除原1979条会话、29条memory、508条emotion及明确队列/旧Future/语音正文副本等既定范围；用户资料、昵称/姓名、关系数值、日记、朋友圈、成长/配额/账本/指标等按原矩阵保留。旧容器及其日志可写层移除，不复制数据、日志或配置归档，不删除MySQL/Redis卷或OSS保留对象。
- **向量与开放**：旧 `lxm_memory_long_collection` 全程只读、245条不变；新库初始为空，1024/FLOAT/DotProduct及稀疏查询能力通过，Embedding/rerank固定合成文本真实调用正常。03:59:39 UTC完成清理，04:01:30 UTC独立open，环境active/epoch2。先内网验收，后恢复原HTTPS、端口及TLS挂载；MySQL、Redis原容器ID与卷均未替换。
- **本轮验收**：最终本地定向47 passed/2 skipped，生产固定库名27个隔离浏览器会话通过。真实后台HTTP仅新增1条合成记忆，约3.163秒源成功、约10.828秒自动completed/ready，attempt1/round0；远端dense1024/sparse8项、dense及BM25查询命中，后台列表ready无维修原因。随后正常DELETE并核实generation2墓碑、列表恢复0；只保留正常协议的1个已删除identity、3个operation和1个completed索引任务，不做物理抹除。未向模型发送真实私有业务上下文。
- **普通重启及公网**：正常重启后仍只有上述opened run、epoch2，测试墓碑/3个操作/索引历史均保留，没有再清理。公网首页、后台、聊天页和Index大写图片均HTTPS200，实际认证业务API code0、空列表及新目标配置正确。原Nginx未公开OpenAPI，公网404、内网200；最初错误期待公网200的测试日志保留，依据原路由修正验收范围，未改网关或放宽业务断言。四容器均running，原unless-stopped恢复。
- **维护入口与证据**：运行源在 `/opt/lxm/releases/memory-v32-62f7955`；`/opt/lxm/.env` 的COMPOSE_FILE指定原base/override与新增release覆盖，默认Compose使用本次源码构建目录。普通启动不调用S15，后续只前向修复，不回切旧事实。本次脱敏发布记录（本地留存，未随本次提交；原引用：`../../../data/deploy/production-v32-20261015-eweq4jei/release-manifest.json`）与公网截图（本地留存，未随本次提交；原引用：`../../../data/deploy/production-v32-20261015-eweq4jei/public-admin.jpg`）在Git忽略目录；服务器原始无正文维护回执在该release的`maintenance/`。**生产部署及本轮读写闭环VERIFIED**；通用库名配置改造延期，AC19/AC20原FAIL、完整质量对照缺项及长期运行边界仍未补证，不据此宣称整体质量全通过。

## 4. 需求映射

F与CSTR完整映射见§2；下表保留全部26项RQ，包括两个子项和三个延期项。仅直接承担条款/可独立子条款的STEP映射，不给所有相邻层重复挂需求。

| RQ | 原主题 | 状态 | STEP或排除/恢复位置 |
|---|---|---|---|
| RQ-01 | 本期边界、四路混合召回、路内重排与 BM25 词组原则 | 确认 | STEP-009、STEP-010、STEP-011 |
| RQ-02 | 同 Key 下多次经历保留与事实版本 | 延期 | RP-003（§9.4 RQ-02）；保留同Key覆盖；STEP-006/019仅检验兼容，非经历历史交付。 |
| RQ-03 | 语音实时召回是否升级 | 延期 | RP-004（§9.4 RQ-03）；语音实时召回升级延期，STEP-019适配存储/score及回归，STEP-006是写入接入。 |
| RQ-04 | 语音会前加载是否升级 | 延期 | RP-004（§9.4 RQ-04）；语音会前升级延期，STEP-019适配存储/score及回归，不补造时间。 |
| RQ-05 | 最终数量上限的配置粒度 | 确认 | STEP-003、STEP-013 |
| RQ-06 | 旧 TopK/threshold 到候选数、最终数和新门槛的过渡 | 确认 | STEP-003 |
| RQ-07 | 角色三路共享预算的分配方式 | 确认 | STEP-013 |
| RQ-08 | 高排名整条放不下时的选择策略 | 确认 | STEP-013 |
| RQ-09 | 总预算约束及不可裁剪内容仍超限时的行为 | 确认 | STEP-013、STEP-014、STEP-015、STEP-017、STEP-018 |
| RQ-10 | 改写失败、缺字段或 Keywords 为空时的降级范围 | 确认 | STEP-009 |
| RQ-11 | rerank 失败时的路内降级方式 | 确认 | STEP-010、STEP-011 |
| RQ-12 | 低相关与降级结果的准入规则 | 确认 | STEP-003、STEP-011 |
| RQ-13 | BM25 索引正文口径 | 确认 | STEP-004、STEP-006、STEP-007、STEP-008 |
| RQ-14 | 索引部分失败时的成功口径、可见状态与恢复时限 | 确认 | STEP-004、STEP-005、STEP-006、STEP-007、STEP-008 |
| RQ-14.1 | 自动补索引持续失败后的处理边界 | 确认 | STEP-005 |
| RQ-15 | 真实诊断的阶段和后台入口 | 确认 | STEP-017、STEP-018 |
| RQ-16 | 新诊断及索引维护的执行权与结果查看权 | 确认 | STEP-017、STEP-018 |
| RQ-17 | 诊断保存内容与留存期限 | 确认 | STEP-017、STEP-018 |
| RQ-17.1 | 诊断详细记录、文本快照及已完成索引维护记录的留存期限 | 确认 | STEP-017、STEP-018 |
| RQ-18 | 真实同集文字召回质量、关键不退步、硬时限及索引完整性门槛；费用不考虑，日常延迟/提升幅度仅记录无数字阈值 | 确认 | STEP-020、STEP-021、STEP-022；以§1.4最新取舍为准 |
| RQ-19 | 向量与 BM25 候选数量的配置粒度 | 确认 | STEP-003、STEP-010 |
| RQ-20 | 检索依赖的超时、重试与总等待预算 | 确认 | STEP-012、STEP-015 |
| RQ-21 | 记忆删除后诊断文本快照的处理 | 确认 | STEP-017、STEP-018 |
| RQ-22 | 保留两阶段各45秒；S10/§9.7固定整轮业务180秒，同代不续时；H5/OpenAPI及网关等待按必要余量衔接，连接/锁实现仍待Q05 | 确认 | STEP-014、STEP-015、STEP-016；012按§7.2接收剩余整轮截止，业务起点/终态由调用方负责 |
| RQ-23 | 旧 `dashvector_client.search` 在返回候选前执行 `score >= threshold`，仅说“不转作 rerank 门槛”不能决定新链是否仍过滤候选 | 确认 | STEP-003、STEP-010、STEP-011 |
| RQ-24 | v2 §7.2 将客户端单独断开继续/取消留在 Q05；本轮就用户离开或断网的体验提问 | 确认 | STEP-014、STEP-016 |

## 5. 验收映射

全部AC来源均为P01 §8对应稳定AC条款/`PRD`。同一AC拆给多个STEP时下表明确各自子条款；本轮仅校验映射，不运行AC。设计闸门的门槛验收使用其CSTR号，不虚构AC36或把相关设计工作泛称业务验收完成。

| AC | 负责STEP | 子条款边界 |
|---|---|---|
| AC01 | STEP-006 | 006：正文编码/身份/覆盖 |
| AC02 | STEP-006、STEP-007 | 006：语音写；007：Admin增改及旧词失效 |
| AC03 | STEP-010 | 010：去key_l2且双来源 |
| AC04 | STEP-011、STEP-013 | 011：本路请求；013：不跨分数选择 |
| AC05 | STEP-003、STEP-013、STEP-019 | 003：12项字段与AC05-a表单；013：数量>3；019：页面/API集成 |
| AC06 | STEP-013 | 013：轮转/整条/二次裁剪/硬阻断 |
| AC07 | STEP-009、STEP-012 | 009：字段/原输入/Step8补齐；012：改写超时收口 |
| AC08 | STEP-010、STEP-012 | 010：通道独立保留/空因；012：截止结果保留 |
| AC09 | STEP-011、STEP-012 | 011：完整重排/门槛/融合；012：耗尽降级 |
| AC10 | STEP-004、STEP-007 | 004：删除凭据；007：Admin更新单删批删 |
| AC11 | STEP-001、STEP-008、STEP-017、STEP-018、STEP-019 | 001完整来源；008回填与持久run；017读取/018页面/019集成共同完成AC11-a，017该项及DONE等待008证据 |
| AC12 | STEP-003、STEP-013、STEP-017、STEP-019 | 003配置冻结、AC12-a合法预算及AC12-b多入口来源；013真实选入；017实际业务对照须015，DONE另须008回填证据；019完成AC12-b页面/接口/运行消费集成 |
| AC13 | STEP-003、STEP-007、STEP-010、STEP-013、STEP-014、STEP-017、STEP-018、STEP-019 | 各入口原角色/原用户隔离及新诊断既定权限；003/007/014/017接口、018页面、019完成AC13-a分域矩阵与AC13-b安全渲染；010/013仍负责候选安全 |
| AC14 | STEP-014、STEP-016、STEP-019 | 014主链及Admin纯读状态投影/分页；016 H5；019星云与AC14-a/b后台历史对话及同修订跨端回归 |
| AC15 | STEP-014、STEP-015 | 014：OpenAPI；015：Step8输入和新结果 |
| AC16 | STEP-006、STEP-019 | 006：文字/语音提取保持；019：配置/情绪回归 |
| AC17 | STEP-003、STEP-019、STEP-022 | 003新库目标与历史控件；019全入口DotProduct/权限；022按S15一次性清理、保留数据核验、开放/新数据恢复及旧库退役 |
| AC18 | STEP-006、STEP-019 | 006：AC18-a 局部写入身份/value/来源/索引状态及恢复；019：AC18-b 经语音实际 writer→新文字 BM25 链的同一身份当前正文集成验收，并保留原读取时限/缓存/过滤/投递兼容；006不承担完整新文字链。 |
| AC19 | STEP-020、STEP-021 | 020：同集语料/查询/标注/质量口径/关键场景冻结；021：文字漏召回/混淆/稍复杂查询的真实最终选入质量、关键不退步/退步解释/正常降级；日常延迟/提升幅度仅记录，费用不设门槛 |
| AC20 | STEP-009、STEP-021 | 009：Prompt规则/模板、解析及既有字段协议子验收；021：真实模型四路输出的实体、去套话、指代、模糊时间/否定语义子验收，按020冻结的Q05标准判定 |
| AC21 | STEP-009、STEP-010 | 009：Prompt/只读预览；010：Keywords/Question职责与旧补充向量替换 |
| AC22 | STEP-012、STEP-015 | 012：45+45/重试/截止；015：Step8同规则 |
| AC23 | STEP-004、STEP-005、STEP-008、STEP-017 | 004：锚点/未知/并发；005：有限恢复；008：回填缺口；017：授权手动恢复 |
| AC24 | STEP-017、STEP-018 | 017：永久/手删/快照/未完成保护；018：可观察页面 |
| AC25 | STEP-017、STEP-018 | 017：源删历史保留且不召回恢复；018：历史展示 |
| AC26 | STEP-013、STEP-014、STEP-015、STEP-017、STEP-018 | 013：超预算阻断；014：主链OpenAPI失败/刷新重发；015：Step8条件清槽/零调用；017/018：真实诊断预算阻断/最终选入/零回复及零业务写入 |
| AC27 | STEP-014、STEP-015、STEP-016 | 014：合法入队起180秒/同代不续时/终态/未知；015：子链接收起同样180秒及提交收口；016：受控等待/部署余量不延业务截止；015另负责AC27-a全部成功出口与提交后收尾 |
| AC28 | STEP-003、STEP-010、STEP-011 | 003：旧配置停用；010：真正不过滤含负分；011：正常准入/故障融合 |
| AC29 | STEP-014、STEP-016 | 014：断线继续、AC29-a提交身份/幂等/只读核实；016：按该协议返回pending/成功/失败/未知并去重，AC29-b有限持续收敛；002只负责协议定稿，不冒充运行验收。 |
| AC30 | STEP-004、STEP-005、STEP-006、STEP-007、STEP-017、STEP-018、STEP-019 | 004源/索引锚点；005修复；006原AC30-a包装层；007 AC30-b/c自有回执、三页源/索引及批删分态；017/018维护反馈；019UI/API集成 |
| AC31 | STEP-004、STEP-008、STEP-010、STEP-013、STEP-017 | 004：凭据/变更/保护历史；008：旧回填资格；010：重排前当前来源；013：使用点/后缀淘汰；017：历史删除保护 |
| AC32 | STEP-009、STEP-010、STEP-011 | 009：字段实际存在/非法CandidateKeys；010：空编码；011：重排完整/限额/同分 |
| AC33 | STEP-009、STEP-013、STEP-017、STEP-019 | 013选择/前缀/渲染、017同次诊断；原AC33-a旧Test不变；009/013/019完成AC33-b三处只读预览及默认/有效值区分 |
| AC34 | STEP-014、STEP-015 | 014：锁所有者/提交仲裁；015：本次条件清槽；014负责AC34-a入队失败与1～4条pending崩溃，015负责AC34-b成功收尾及新Future防误清 |
| AC35 | STEP-017、STEP-018、STEP-019 | 017执行/保存/历史及维护接口；018两页导航/详情/刷新/分页/删除，AC35-a闭合；019相应浏览器/API回归；不新增生产回填控制 |

| 未编号约束验收 | 负责STEP | 通过条件 |
|---|---|---|
| CSTR-01 | STEP-013 | P01 §7.1“越权或不可信候选”/§11.1；候选仅作数据，不覆盖受控系统指令及可信route/doc_id/用户归属；提取和旧安全兼容仍按006/019的AC16验证 |
| CSTR-02 | STEP-001 | P01 §9.3.1 GATE-A及完整遍历要求；真实属性、双独立候选、编码版本、完整遍历及结束证据 |
| CSTR-03 | STEP-002 | P01 §9.3.1 GATE-B及参数字典；具体协议/schema/故障设计与完整参数字典 |
| CSTR-04 | STEP-020 | P01 §9.3.1 GATE-C；§11.5与§1.4取舍；冻结同集语料/查询/标注/质量口径/关键场景；费用不设门槛，日常延迟/提升幅度仅记录 |
| CSTR-05 | STEP-022 | P01 §9.3.1 GATE-D；全部功能、真实同集质量与关键不退步、硬时限、新库维护完整性、S15清理/保留核验及新数据恢复证据与执行边界；缺费用及日常延迟/提升幅度数字目标不阻断 |
| CSTR-07 | STEP-003 | P01 §6.3/§12.3/12.5；冻结有效版本；配置中已知服务凭据在正常/异常调用及测连的响应、错误、日志中不可见 |
| CSTR-09 | STEP-017 | P01 §6.7.1/§12.3/12.5；诊断无业务副作用；已知调用配置凭据不得进入诊断/维护响应、错误、日志或持久记录，业务文本快照原语义保持 |

### 5.1 本次修订的原 AC 子用例与责任边界

以下十项是 P01 §8.1 中原 AC 的细化，不增加 AC36 或产品决策。按同一 ID 记录“输入、观察点、预期、实际、环境/版本、命令或步骤、证据”；没有实际输出不能勾选实施完成。

| 子用例 | 正文依据 | 负责 STEP / 实际验收边界 | 报告问题 |
|---|---|---|---|
| AC12-a | §6.3.2 | 003：无/有历史配置的合法预算保存、固定配置值50、部分更新、发布回读/未知核实和在途冻结；013：昵称实际>50但总量合格不裁剪、最终总量超限阻断 | RV31-R01 |
| AC29-a | §7.4.1 | 014：H5/OpenAPI身份与只读核实；016消费与未知提交UI；002只交设计 | RV31-R02 |
| AC29-b | §7.4.2 | 016：80秒回页仍pending，后续成功/失败更新与有界停止；不依赖历史分页 | RV31-R03 |
| AC34-a | §7.4.3 | 014：入队失败不误作废旧代，1～4条pending进程退出后按原deadline收敛 | RV31-R02补充 |
| AC27-a | §7.5 | 015：正常/兜底全部提交出口，179.x秒已提交后跨180秒收尾仍成功 | RV31-R04 |
| AC34-b | §7.5 | 015：提交未知不盲目失败/重跑，原副作用不重复，成功/失败均不误清新Future | RV31-R04 |
| AC33-a | §6.3.3 | 013：构建器字符串兼容单测；019：旧Prompt测试接口当前/草稿/覆盖及权限回归 | RV31-R05 |
| AC18-a | §6.4、§6.6.3 | 006：局部写入身份/value/type/user_id/来源/索引状态/trace及恢复证据 | RV31-R06 |
| AC18-b | §6.4 | 019：语音实际writer写入→索引确认就绪→新文字链同ID/当前value的BM25候选与用户隔离 | RV31-R06 |
| AC30-a | §6.6.3 | 006：真实文字Step6与语音包装层取消/20秒超时/成功trace不阻断独立修复 | RV31补充 |

### 5.2 后台联动子用例映射（ADM32；12项）

对应P01 §8.2，根AC仍35项；与§5.1原10项合计22子用例。不得只补本节而漏各步开发任务/实际测试。

| 子用例 | PRD正文 | 负责STEP与边界 | 追踪 |
|---|---|---|---|
| AC14-a | §6.8.2 | 014后端；019页面/跨端 | ADM32-01 |
| AC14-b | §6.8.2 | 014查询；019浏览器 | ADM32-01 |
| AC05-a | §6.8.3 | 003；019集成回归 | ADM32-02 |
| AC12-b | §6.8.3 | 003；019集成回归 | ADM32-02 |
| AC17-a | §6.8.3 | 003；019兼容；022切换 | ADM32-02 |
| AC30-b | §6.8.4 | 004基础；007本步直接验收；019页面回归 | ADM32-03 |
| AC30-c | §6.8.4 | 007；019页面回归 | ADM32-03 |
| AC11-a | §6.8.6 | 008记录；017查询；018页面；019集成 | ADM32-04 |
| AC35-a | §6.8.5～§6.8.8 | 017协议/接口；018页面 | ADM32-05 |
| AC13-a | §6.8.7 | 003/007/014/017局部；018前端；019总矩阵 | ADM32-06 |
| AC13-b | §6.8.5～§6.8.7 | 007/018页面；019浏览器回归 | ADM32-06 |
| AC33-b | §6.8.9 | 009词组；013预算预览；019接口/UI | ADM32-07 |

017开发不依赖008，但AC11-a及DONE需008实际记录证据；018/019须验证该生产→查询→页面关系，不能拿手工拼出的JSON替代端到端证据。014/019历史对话保持手动查询，不新增后台自动轮询。

## 6. 完整STEP提示词

使用时保留每个STEP完整正文及其引用证据行。共同PRD输入为`PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md`（existing/PRD/P01），要求短引在本STEP“来源映射/业务定义”保留；证据目录提供具体路径/符号。开发任务均为后续执行计划；本次文档复审已通过，实际实施仍须在用户授权范围内并满足相应前置与停止门。

### 6.0 每步执行与证据规则

实施方先读取配套 PRD、当前 STEP、已验证的前置输出以及相关现行代码。只核对本步涉及的路径；漂移涉及业务行为时修正影响记录，不盲套历史行号、不扩扫历史目录。

实现类 STEP 在对应既有测试模块先加入下列失败断言，再做最小接线/修改，最后运行本步模块与必要交叉回归。测试名称和新接口在本计划中是目标，不声明源码已存在。基础设施/技术定稿/评测冻结步骤交付自己的证据，不能用设计通过替代业务运行通过。示例命令沿 T00 已登记入口使用 `PYTHONPATH=. pytest tests/…`；真实外部调用必须限定授权测试环境，费用不作为本期门槛，模拟、真实事务、浏览器、线上证据分列。纯静态断言或被 skip 的集成用例不是运行通过。

每步输出具体变更路径、接口/参数版本、故障时序及实际证据，逐项关联 §5/§5.1；阻断项写明恢复条件。§3 的 DONE 只在本步负责的全部证据齐全时更新。未填的基础设施/model/有限恢复数字不是可随意默认的留白：001/002必须交付所需具体参数与协议后才允许依赖实现；020冻结真实评测集/标注/口径/关键场景，不要求费用或日常延迟/提升幅度数字目标。

### 6.0.1 ADM32未来验证落点（实施时创建/执行，非本轮已运行）

| 文件/入口 | 状态 | 主要测试断言与责任 |
|---|---|---|
| `tests/test_admin_vector_token_config.py` | EXISTING，003扩用例 | 12字段独立、合法/非法/加载失败与发布回读；AC05-a/12-a/12-b/17-a；API结果不能替代浏览器表单验证 |
| `tests/test_memory_v32_admin_status.py` | PLANNED，014创建/019集成 | 当前代承接、未知commit、legacy、同号复合身份、多提交不放大total、原角色；AC14-a/b |
| `tests/test_memory_v32_admin_write_feedback.py` | PLANNED，007创建/019集成 | 自有回执、同ID冲突、源/索引分态、4唯一项批删计数、旧响应兼容；AC30-b/c |
| `tests/test_memory_v32_admin_backfill.py` | PLANNED，008夹具/017查询/019集成 | 超cap持久run、中断/总量未知、对账完成条件及后台GET零执行副作用；AC11-a |
| `tests/test_memory_v32_admin_permissions.py` | PLANNED，017建立/019补全 | §6.8.7五角色×域，直访/篡改ID、observer只读、自有回执边界；AC13-a |
| `tests/test_memory_v32_admin_ui_contract.py` | PLANNED，018/019 | 静态字段/菜单/按钮/安全插值和只读预览契约；静态通过不等于浏览器通过 |
| 真实浏览器＋隔离后端/受控桩 | 019记录实际使用工具和入口 | 按各子用例点击/编辑/保存/断开/刷新/切用户/故障响应并记录DOM与网络输出；不凭空声称项目已有某E2E框架 |

实施者先写能暴露原行为缺口的测试，再实现、运行并记录失败→通过证据。现有入口为 `PYTHONPATH=. pytest tests/`；新文件创建后可逐个运行 `PYTHONPATH=. pytest tests/test_memory_v32_admin_status.py -q` 等实际文件命令。缺少数据库/浏览器依赖或用例skip必须说明，不能标端到端通过。代码/测试新文件名与项目冲突时由002登记等价实际路径，同时更新本表和责任STEP，不改业务验收。

### [STEP-001] 索引基础设施与完整遍历核验

**阶段状态**：以§3为准；001新库隔离核验已有证据，GATE-A剩余项未通过。**目标**：证明指定新库双通道与完整来源可行。

**来源映射**：需求`F08 / CSTR-02`；负责验收`AC11 / CSTR-02`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：无前置STEP；输入PRD、现行契约与授权环境必须可读取。核验真实基础设施未获证据时，本STEP门槛不通过。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/utils/dashvector_client.py` | `existing` | `REPO_BASELINE` | B04 / build_filter:19；search:78；upsert:153；delete:210；list_by_filter:232；fetch_by_ids:273 | 核对既有行为/接入或验证落点 |
| `backend/utils/character_knowledge_validate.py` | `existing` | `REPO_BASELINE` | B14 / build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | 核对既有行为/接入或验证落点 |
| `backend/services/vector_service.py` | `existing` | `REPO_BASELINE` | B15 / L1（历史 mem_* 自由正文与普通 Agent 检索） | 核对既有行为/接入或验证落点 |
| 只读核验报告及完整遍历适配方案（位置按已核实项目约定确定）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：给出可证明双通道与全量遍历可行的 GATE-A 证据。对应产物与本STEP验收证据。

**业务定义**：PRD §9.3.1：两类候选集与上限独立；只用现存正文；全量不以 capped 列表或总条数相等证明。 来源：P01 / `F08、CSTR-02`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按P01 S15核验指定同Cluster新库（1024/FLOAT/DotProduct）的实际属性/配额和部署归属；复用隔离双通道/score证据，不能凭截图/空schema/code0判通过；旧Cosine完整导出及旧向量复用不再是前提，新库完整来源方案仍须核实。
2. 核验编码器、词典/统计/语料版本在查询和文档端一致；真实验证同文档更新时sparse省略/清空/替换及fields保留语义，保证正文更新后旧稀疏不能继续有效。定位完整遍历接口或可信身份清单、断点及结束条件，禁止用TopK列表替代。
3. 在隔离可信清单证明标准KV/可靠mem_*全文、空正文/身份异常均可枚举及超cap/断点/结束；核验新数据模型/维度与归一化，明确新库所有writer身份如何进入可信完整来源。交接T0全进程封写设计，清理对象细化交002，不做旧Cosine搬迁。

**不在本STEP范围内**：不执行启用前真实清理，不跑生产回填，不选择事实历史/新路由。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 可完整遍历的样本来源 | 身份清单/摘要与结束条件可复核，分组无遗漏。 | AC11 |
| 异常 | 仅 query+topk，或属性/归属不可确认 | GATE-A 不通过，记录缺口；不把列表当全量。 | CSTR-02 |
| 边界 | 超cap/自然语言冒号；隔离新库sparse省略/清空/替换、同ID更新 | 完整枚举、旧自由正文不截断；分数方向/字段保留及旧稀疏失效有实证，无证据不放行。 | AC11 CSTR-02 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-001、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-002] 行为、接口与参数定稿

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：形成有故障时序和可验证断言的 GATE-B 技术基线。

**来源映射**：需求`CSTR-03`；负责验收`CSTR-03`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-001《索引基础设施与完整遍历核验》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C04 / L1（响应、分页及错误码约定） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C05 / L1（observer 与后端角色边界） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/chat-emotion/api.md` | `existing` | `CONTRACT` | C06 / L1（文字消息与 SSE） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/chat-emotion/data.md` | `existing` | `CONTRACT` | C07 / L1（消息状态及代际） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/openapi/api.md` | `existing` | `CONTRACT` | C08 / L1（OpenAPI 入口与信封） | 核对既有行为/接入或验证落点 |
| `backend/services/admin_config_service.py` | `existing` | `REPO_BASELINE` | B16 / get_active_config:31；publish_config:181 | 核对既有行为/接入或验证落点 |
| `backend/services/chat_service.py` | `existing` | `REPO_BASELINE` | B23 / await_bundle_payload:206；enqueue_send:251；enqueue_resend:287；new_generation_for_user:171；schedule_recovery_bundle:129 | 核对既有行为/接入或验证落点 |
| `backend/services/chat_queue_service.py` | `existing` | `REPO_BASELINE` | B24 / try_acquire_bundle_lock:81；release_bundle_lock:89；schedule_debounced:49 | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B40 / L37（请求数据库依赖提交点） | 核对既有行为/接入或验证落点 |
| 技术方案、参数字典及拟新增 schema/API/页面/迁移清单；路径和内部名称按已核实项目约定确定。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：形成有故障时序和可验证断言的 GATE-B 技术基线。对应产物与本STEP验收证据。

**业务定义**：PRD Q02–Q07/§9.3.1：已确认业务不重选；S10/§7.2/7.4/9.7已定整轮业务固定180秒、两阶段各45秒、失败调用最多重试一次及同代不续时；默认值、字段、零值、融合、模型门槛、调用/退避/收口预留、连接等待余量、锁/提交仲裁和恢复参数尚未定稿。 来源：P01 / `CSTR-03`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 基于 STEP-001 实测能力定稿源/索引持久锚点、可信当前凭据、使用点保护、状态及迁移。给出字段类型、唯一约束、事务/远端调用顺序、领取/恢复状态机和故障矩阵；覆盖源成功后本地登记失败、BM25调用未知、删除/重建并发及旧任务迟到，不只写“保证一致”。
2. 按 P01 §7.4.1 输出 send/resend 提交协议：消费 H5 既有 `client_message_id/client_resend_id`，OpenAPI采用可选 `Idempotency-Key`；明确两个拟新增只读入口 `GET /api/chat/submissions/{operation}/{request_id}` 和 `GET /api/open/v1/chat/submissions/{operation}/{request_id}` 的鉴权、信封及现行错误映射。先核对路由冲突和字段约束，再定请求/响应schema；新路径不是已运行接口。
3. 输出请求身份→用户消息→当前有效generation→原deadline→互斥终态的关系模型。请求身份按可信user+operation+ID隔离，channel不另开重复域；区分同ID同内容、同ID异内容、不同ID同内容、跨用户同ID、不同入口同ID、同次恢复与显式新resend。request_id不是generation；已入队消息按既有打包规则被合法新代承接时，保留原提交身份并记录当前归属及单调状态版本，查询不得续时。
4. 定稿合法入队边界与提交仲裁时序：鉴权/校验、幂等判定、user持久保存/额度、generation变化、调度注册分别何时可见；旧代只能因已确认合法的新输入作废。对“新消息保存失败”和“仅1～4条pending且进程退出”给出可恢复持久证据、扫描/核实入口及有限收口；不依赖满队、重发新输入或内存Future。正常与Step8独立兜底写事务均列提交前/commit未知/已提交后收尾矩阵；锁所有权、条件清槽和结果核实不得延长业务授权。
5. 逐项填写 P01 §9.3.2 和原Q02～Q07参数字典：路/入口、字段名、类型/单位、默认值/范围、空零语义、交叉校验、发布/缓存、来源版本、回退影响和测试依据。固定180秒、45+45、最多一次失败调用重试和nickname固定预算配置值50直接沿用；昵称保留正文不裁剪、完整计入max_total，交003/013两例：实际昵称>50且最终总量合格可用、按既定裁剪后最终仍超总量按RQ-09阻断。其他预算/模型/融合/维护次数与时限须有明确数值及依据，费用与日常延迟/提升幅度数字目标依§1.4排除。模型限制和融合提供可手算样例，不能用“后续合理配置”放行。
6. 为 H5 定稿 `text_status_poll_interval_ms`、`text_status_poll_max_interval_ms`、`text_status_poll_backoff_factor`、`text_status_probe_timeout_ms`、`text_status_reconcile_margin_ms` 的有限数值及关系；另定 admission未知核实截止、请求身份保留/过期核实规则、各层连接总/空闲时限。给出0→30断线→80回页pending→120终态与数据库持续不可用的时序，客户端停止和服务端待核实/告警分别闭环；轮询、换页与重复请求都不能刷新原窗口。
7. 定稿同次冻结配置、结构化候选/Prompt结果、无副作用诊断、分页/并发/历史保存失败协议；为旧 `prompt_mgmt.test_prompt` 指定字符串兼容包装与后端受控mock分支，保持当前/草稿与系统提示覆盖，不允许真实聊天/新诊断绕过可信候选检查。把协议/状态/预算样例及10个子用例逐一交给对应实施STEP。

8. 按P01 §6.8.1～6.8.9冻结后台交接包：既有/目标路由、每页字段→API映射、状态样例、分入口权限、默认20/范围1～100分页、诊断并发/核实上限；本节已定的页面与业务语义不得再写成待产品选择。为Admin源写operation_id、Idempotency-Key、write_result及自有只读回执定物理持久锚点和有限保障期，不靠回执返回后才登记。
9. 为历史对话定义与H5同源的纯读状态投影：processing_state/status_reason/state_origin/state_revision/status_observed_at；SQL按消息页批量关联一份当前投影，不能增加total/行数。补superseded被新代承接、deadline已过未确认、旧历史来源及依赖读取失败矩阵；不复用用户JWT接口冒充管理员鉴权。
10. 列出vector_retrieval_config、vector_db_config、third_party/env及全部读写/进程清单，含语音直接HTTP/Agent/后台/两处旧控件。按S15冻结新运行目标、归一化/缓存、BM25版本、单库分态维护及008→017/018回填DTO；不新增迁移源env。依据里程碑§2.1逐项核实真实schema/共享字段/外键与弱引用、语音正文副本、清理和保留清单、计费/成长数值不变、Redis/旧Future/异步任务封写、一次完成标记与失败续跑/恢复设计；008交工具演练、022实际清理，无反向依赖。参数/配置发布未知须关联精确提交，不能猜更后版本。

**不在本STEP范围内**：不把原则冒充已验证实现，不把拟定字段/错误码/默认值冒充当前代码或用户新增业务决定；不把数量为 0 偷换成关闭一路。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | STEP-001 真实核验通过 | Q02–Q07 均有具体设计、参数依据和验收断言；按方案复核每个故障窗口。 | CSTR-03 |
| 异常 | 缺唯一终态或维护记录失败后的恢复证明 | GATE-B 不通过，标明相关模块不能放行。 | CSTR-03 |
| 边界 | 未知提交、同 ID 重建、零值及模型请求限制；180秒前后提交与同代恢复 | 空零语义/并发时序/非法输入可逐项推演；180秒不得列为待选值，阶段取较早截止，同代不续时；连接/收口余量及锁/仲裁方案有独立依据，无隐式默认。 | CSTR-03 |
| 请求与代际矩阵 | 同ID同正文/异正文、不同ID同正文、跨用户或跨入口同ID、消息被合法新代承接、旧OpenAPI不带ID | 给出每格唯一的身份/额度/消息/代际/响应行为；旧调用方能力缺口如实说明，不能用文本时间猜测。 | CSTR-03 |
| 故障时序设计 | 新消息保存失败、1～4条pending进程退出、commit回执未知、Step8兜底与提交后收尾、80秒回页pending | 对每格给持久观察点、deadline继承、恢复动作、停止条件和实施STEP；没有物理证据路径则GATE-B不通过。 | CSTR-03 |
| 参数完整性 | 五项同步参数、未知核实窗口、身份保留、业务/阶段/传输/锁/后台修复时限 | 固定值不重新待选；其余均有有限数值、单位/范围/校验和依据，客户端无无限滑动续期。 | CSTR-03 |
| 后台技术交接 | §6.8页面/API/角色/字段表及回填生产消费时序 | 逐接口含成功/失败/未知/权限样例，有限参数已填；无未知值默认放行、无008反向依赖；表单规格不再留给执行者猜 | CSTR-03 |
| 昵称与发布未知设计 | 昵称实际>50且总量合格/最终总量超限；本次配置响应未知后他人发布更后版本 | 固定50是配置值，正文不裁剪并完整计总量，两边界交003/013；配置核实精确关联本次提交/发布版本或审计，当前状态不足时保持待核实，交003/019 | CSTR-03 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] P01 §9.3.2 要求的协议、故障时序、参数表、消费兼容表全部有具体可审阅产物；未定schema/必要有限数值不能以文档原则替代GATE-B，§1.4排除的数字目标不计缺口。

- [ ] 本步ADM32设计分项有可审阅协议/schema/字段到API/角色/状态与故障样例、有限参数和责任交接证据；不要求尚未实施的接口或页面运行结果，不将P01 §8.2整项标通过。接口由对应实施STEP验收，管理查询/页面与浏览器结果由017/018/019收口，不增加开发依赖。

**完成回传**：返回STEP-002、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-003] 请求有效配置与后台独立数量

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让新链配置保存、测连、消费和版本冻结一致。

**来源映射**：需求`F09 / RQ-05 / RQ-06 / RQ-12 / RQ-19 / RQ-23 / CSTR-07`；负责验收`AC05 / AC12 / AC17 / AC28 / CSTR-07`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32验收映射补充**：AC13 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| `backend/services/admin_config_service.py` | `existing` | `REPO_BASELINE` | B16 / get_active_config:31；publish_config:181 | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/vector_config.py` | `existing` | `REPO_BASELINE` | B17 / VectorRetrievalPatch:34；_prompt_hot_config_keys/预算合并与校验:L94–134 | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/system_monitor.py` | `existing` | `REPO_BASELINE` | B18 / L35（第三方保存/测连与独立权限） | 核对既有行为/接入或验证落点 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B19 / get_dashvector_endpoint:147；get_dashvector_api_key:142；get_dashvector_collection:155 | 核对既有行为/接入或验证落点 |
| `backend/services/embedding_service.py` | `existing` | `REPO_BASELINE` | B20 / get_embedding:30；_call_embedding_api:122 | 核对既有行为/接入或验证落点 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B40 / L37（请求数据库依赖提交点） | 核对既有行为/接入或验证落点 |
| `admin/pages/vector-token-config.html` | `existing` | `REPO_BASELINE` | U01 / L66（当前统一 TopK/threshold 与预算页） | 核对既有行为/接入或验证落点 |
| `admin/pages/third-party.html` | `existing` | `REPO_BASELINE` | U02 / L92（当前第三方测连页） | 核对既有行为/接入或验证落点 |
| `tests/test_admin_vector_token_config.py` | `existing` | `REPO_BASELINE` | T09 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 新配置字段、有效组合载体与保护标记（按 STEP-002 定稿），按002定稿填写具体值及依据，未定不实施。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `backend/routers/admin/memory_mgmt.py` | EXISTING / A32-05 | vector-db-config及测连、原角色 |
| `admin/pages/memory-rules.html` | EXISTING / A32-06 | 向量库Tab第二处TopK |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让新链配置保存、测连、消费和版本冻结一致。对应产物与本STEP验收证据。

**业务定义**：PRD §6.3及S14：八项候选、四项最终数量独立；正常rerank门槛与预算分开；新文字链不读旧TopK/threshold；只维护新Collection，旧名称仅限明确的一次性清理清单，历史配置供审计；§12.3/12.5禁止凭据进入响应、错误和日志。来源：P01 / `F09、RQ-05、RQ-06、RQ-12、RQ-19、RQ-23、CSTR-07、S14`；其余参数按前置定稿，不冒充现有实现。

**开发任务**：

1. 按定稿参数扩展既有配置页/API 与校验，不复制旧统一数值为四路新默认；明确旧控件对新链停用。
2. 让本期 BM25/rerank 的测连和实际调用消费同一有效来源；冻结检索/预算/模型/索引编码版本组合，错误回退来源显式记录。
3. 实现新Collection运行配置及发布/缓存一致性，所有后台测连与实例有效目标相同且不fallback旧库；取消迁移源env，清理工具须显式目标而非沿用默认运行名。保留必要审计/新数据恢复材料不被20版本清理误删；本步隔离验证，实际启用归022。
4. 配置读取/有效组合、测连及本期实际服务调用的响应、错误和日志禁止携带明文服务凭据；合法调用仍从定稿配置取凭据，不扩为全项目日志或凭据存储治理。

5. 在B17修正 `_prompt_hot_config_keys()`、部分更新合并及校验所遍历字段不一致的问题：统一用可编辑白名单，固定预算配置值 `user_nickname=50` 不接受PUT且不因缺失被按0拒绝；昵称保留现有正文不裁剪，实际完整渲染按同一计数器计入max_total，50不是实际文本硬上限、每次实际占用或额外总预算。实际昵称>50且最终总量合格可用；按既定裁剪后最终总量仍超限按RQ-09阻断。不改变其他原默认值，不通过扩大白名单绕过缺陷。

6. 在T09先新增无配置/已有配置两组正向测试，逐个保存合法 `memory`、`character_knowledge`、`max_total`，验证只改提交项；经实际配置API保存、GET回读、后续构建消费与当前冻结请求对照，核对任务5的昵称两边界。已确认发布失败或DB提交失败保持原有效值；发布结果未知按002的本次提交关联核实，当前值/版本不是本次结果证明；固定字段/空对象/未知字段/非法类型范围仍拒绝。

7. 按P01 §6.8.3改U01：保留两个Tab，第一个改“混合召回”，四路×向量候选/BM25候选/最终数量表；门槛、Token说明与实际版本分区。使用002字段规则生成或校验表单，空/小数/非有限数不得parseInt兜底；无有效配置的Tab不允许保存。
8. 更新U01快照/dirty PATCH/保存中/错误/回读状态：不重复PUT，不在回读失败时再次发布；在受保护提交内合并当前有效配置，未提交项不丢。响应未知须精确关联本次提交/发布版本或审计证据；期间出现更后版本不能用当前值或版本判本次成功/失败，证据不足保留输入并显示待核实、只读核实不重发。固定昵称预算配置值只读50，正文不裁剪、保留AC12-a；旧TopK/threshold折叠只读，不在新表单提交。
9. 将U03向量库Tab及B13的GET/PUT vector-db-config、test-connection加入本步影响清单，标明独立旧top_k用途和原读写角色。与U02/B18按002来源表核对新能力保存/测连/运行；新外部服务同步前端SERVICE_KEY_MAP/后端_VALID_SERVICES及状态返回，本地BM25只显示实际能力，不虚构网络服务卡。
10. 测连按同一组参数和实际业务结果判定；关键字段改变使旧测试失效。原Key空值保留、掩码不写回，本期before/after和失败日志不泄露凭据；新角色矩阵按§6.8.7逐域验收。Collection/编码变更需要回填时不得靠测连直接切换。

**不在本STEP范围内**：不治理全项目第三方配置，不新增语音/Agent召回算法；S14全入口存储/分数适配由004/019承接，最终候选与注入由后续STEP实现。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 逐项调整 8+4 配置；单次调用中发布新值 | 只有对应参数变化；本次组合固定，后续请求读新值。 | AC05 AC12 |
| 异常 | 非法/缺失配置或测连与保存来源不同 | 按定稿规则拒绝/显式回退，不能伪称已发布版本。 | AC12 |
| 边界 | 清理超过20版本、修改旧threshold；运行/清理目标混用 | 审计及恢复材料仍可定位；新链不受旧阈值影响，运行不fallback旧库，目标错配拒绝启用。 | AC17 AC28 |
| 凭据禁止项 | 仅在服务调用配置放已知测试凭据标记，分别正常调用/测连、触发鉴权或服务错误及配置保存失败 | 本期配置/测连/调用的响应、错误与日志均不含该明文标记；凭据按合法配置使用，不将标记放业务输入，也不改变业务文本快照语义。 | CSTR-07 |
| 正向预算保存 | 无历史配置；有历史配置含固定nickname；分别提交合法memory/character_knowledge/max_total的部分更新 | 保存成功且未提交字段保持，GET及后续运行消费新值；nickname预算配置值固定50、正文不裁剪并完整计入Prompt总量，不能因缺失按0拒绝。 | AC12-a |
| 预算异常及冻结 | 显式提交nickname、空对象、未知字段、非法值；合法更新期间有在途请求；提交/发布失败 | 非法输入按原边界拒绝；旧请求预算固定，新请求仅消费已确认生效版本；失败不产生半套新配置。 | AC12-a |
| 昵称完整计数两边界 | 昵称实际渲染>50，分别给出最终总量≤max_total与按既定裁剪后最终仍>max_total的配置/消费样例 | 固定配置值50不裁剪昵称且完整计实际总量，两例预期分别为可用/按RQ-09阻断。003验证配置与消费口径并交013实际构建/零回复调用边界，不把013后续证据作为003开发前置。 | AC12-a |
| 12项页面与加载 | 四路×三列单项修改，小数/空值/某Tab读取失败 | 对应字段独立生效，无隐藏默认；非法精确拒绝，失败Tab不可保存 | AC05-a |
| 多入口测连与权限 | U01/U02/U03原配置域，变更测试字段/保存/回读/业务消费，凭据与本地BM25分支 | §6.8.3来源一致；保留vector-db和third-party不同角色；无虚构服务/统计，无明文凭据 | AC12-b AC13-a |
| 配置发布未知与并发 | 本次PUT响应丢失/回读失败；他人随后发布不同值或相同值的更后版本；本次关联证据可用/不可用 | 精确核实本次提交与发布版本/审计，不能仅当前值或当前版本倒推本次结果；证据不足仍待核实、保留输入且不自动PUT，GET不发布新版本 | AC12-a AC12-b |
| 旧控件双入口 | 两处旧TopK/threshold及env/后台Collection | 历史项只读审计、现用项按来源标注；不控制新12项、无旧库回切，权限保持 | AC17-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 附T09合法预算更新的失败→修复→通过证据及 `PYTHONPATH=. pytest tests/test_admin_vector_token_config.py` 实际结果；仅非法拒绝用例不能完成本步。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-003、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-004] 可信当前凭据与派生索引维护核心

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让每次源变更和 BM25 维护有可靠身份、代次及故障锚点。

**来源映射**：需求`F03 / RQ-13 / RQ-14 / CSTR-06`；负责验收`AC10 / AC23 / AC30 / AC31`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-001《索引基础设施与完整遍历核验》的已验证输出；STEP-002《行为、接口与参数定稿》的已验证输出；STEP-003《请求有效配置与后台独立数量》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/utils/dashvector_client.py` | `existing` | `REPO_BASELINE` | B04 / build_filter:19；search:78；upsert:153；delete:210；list_by_filter:232；fetch_by_ids:273 | 核对既有行为/接入或验证落点 |
| `backend/utils/character_knowledge_validate.py` | `existing` | `REPO_BASELINE` | B14 / build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | 核对既有行为/接入或验证落点 |
| `backend/models/realtime_voice.py` | `existing` | `REPO_BASELINE` | B38 / VoiceMemoryJob:349；VoiceMemoryTrace:478 | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B40 / L37（请求数据库依赖提交点） | 核对既有行为/接入或验证落点 |
| `tests/test_dashvector_client.py` | `existing` | `REPO_BASELINE` | T06 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_dashvector_upsert_response.py` | `existing` | `REPO_BASELINE` | T07 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| BM25 适配、持久维护/当前凭据 schema 与增量迁移（按 STEP-002 定稿，现仓库未有该能力）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让每次源变更和 BM25 维护有可靠身份、代次及故障锚点。对应产物与本STEP验收证据。

**业务定义**：PRD §6.6.1/6.6.2：成功须源操作确认且凭据可靠登记；源成功/失败/未知与索引结果分别判断；摘要/代次只是技术元数据。 来源：P01 / `F03、RQ-13、RQ-14、CSTR-06`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 实现新DotProduct库客户端、写/查稠密统一L2（含缓存/新库补索引入口，拒绝零/非有限/维度错配），BM25保持原权重；新增定稿持久锚点、当前正文/归属/代次或删除凭据。核验业务code及逐文档结果，不能只看HTTP/bool；明确不存在与读取失败分开。
2. 源读取失败保持待核实；源已发生但登记/响应未知能经对账收敛，先行孤儿索引不可作为有效记忆。
3. 实现旧任务提交前资格校验、删除/重建及最终使用保护；按001实证处理同库dense/fields/sparse更新与清空，字段完整保留，正文变更后旧稀疏不可冒充就绪；源/dense/BM25状态分列，当前generation+摘要匹配才可修复，迟到任务不覆盖新正文或复活删除。展示历史删除不移除保护状态。

4. 为007消费的Admin源写回执提供同一操作持久基础：可信admin_id+operation_id、源接口/type/user归属、方法/输入指纹、源与索引分态、结果修订及可恢复锚点。源动作前完成可恢复登记，同身份返回原结果，冲突不覆盖；源调用未知及源成功但回执保存失败可核实，不能先远端写后仅补日志。保障期及回收条件取002，临时回执不保存新的全文历史。

**不在本STEP范围内**：不新增事实版本查询，不统一跨入口原始事实优先顺序；尚不接业务写入口或实现后台重试调度。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 同身份新增/更新/确认删除 | 源与索引分态可追踪；确认变更前后的当前凭据确定。 | AC10 AC30 |
| 异常 | HTTP 2xx 业务失败、源响应未知/登记失败、query/fetch 同时滞后 | 不误报成功/不存在，不靠两次滞后读取互证有效；缺口可发现恢复。 | AC23 AC30 AC31 |
| 边界 | 旧操作与同ID重建；正文更新后sparse失败/省略、修复迟到、字段缺失 | 旧操作不覆盖新值/删除新建；旧稀疏无效，修复仅当前代且元数据不丢；零/非有限向量不入库，保护历史不可误删。 | AC23 AC31 |
| Admin操作锚点 | 源动作前后崩溃、同ID重复/异内容、源确认未知 | 持久可核实、同身份不重放、冲突不覆盖；为007回执提供证据 | AC30-b |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32仅对持久操作锚点、源/索引分态及上述基础故障测试记录输入、预期和真实基础组件输出；AC30-b的本步基础分项有证据，不要求007的源接口/页面或017～019的管理查询/页面结果，不将整个AC30-b提前标通过。

**完成回传**：返回STEP-004、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-005] 有限索引恢复执行器

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让维护缺口按当前正文有限恢复并可转人工。

**来源映射**：需求`F03 / RQ-14 / RQ-14.1`；负责验收`AC23 / AC30`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-004《可信当前凭据与派生索引维护核心》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/realtime_voice_memory_service.py` | `existing` | `REPO_BASELINE` | B08 / _write_atom:727；_finish:779；stage_deletion_fence:503 | 核对既有行为/接入或验证落点 |
| `backend/models/realtime_voice.py` | `existing` | `REPO_BASELINE` | B38 / VoiceMemoryJob:349；VoiceMemoryTrace:478 | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| 索引恢复执行器与任务操作能力（按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让维护缺口按当前正文有限恢复并可转人工。对应产物与本STEP验收证据。

**业务定义**：PRD §6.6：后台恢复不是在线 45 秒预算；有限自动重试、超限需人工；不重放提取或旧值。 来源：P01 / `F03、RQ-14、RQ-14.1`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 落实持久任务领取/并发、重试及退避上限、执行器启停与崩溃恢复，保存每次尝试和下次计划/人工原因。
2. 修复前复核当前凭据与正文；源读失败不当删除；单条失败不影响其他记录；完成/被新操作取代可区分。
3. 手动重试对同一有效任务幂等：执行中返回现任务、已完成无需重复、被取代关联新任务；按定稿规则处理新一轮预算和告警。

**不在本STEP范围内**：不重跑 Step6/语音抽取 LLM，不持久治理全部旧异步任务；页面和权限接口归 STEP-017/018。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | BM25 待修复且源正文有效 | 从当前正文恢复，记录可查，向量能力可继续使用。 | AC23 |
| 异常 | BM25 结果未知、进程中断/保存记录失败、源读失败 | 锚点可恢复；不误删、不报完整成功；耗尽转人工。 | AC23 |
| 边界 | 重复手动重试、旧任务被更新/删除取代 | 同一有效任务不并行重复，旧正文不复活。 | AC23 AC30 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-005、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-006] 文字及语音写入接入索引维护

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让文字四类和语音两类既有写入维护同一正文口径。

**来源映射**：需求`F01 / F02 / RQ-13 / RQ-14 / CSTR-01`；负责验收`AC01 / AC02 / AC16 / AC18 / AC30`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-005《有限索引恢复执行器》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/memory_llm_service.py` | `existing` | `REPO_BASELINE` | B05 / upsert_step6_vectors:445 | 核对既有行为/接入或验证落点 |
| `backend/services/step6_orchestrator.py` | `existing` | `REPO_BASELINE` | B06 / execute_step6:64 | 核对既有行为/接入或验证落点 |
| `backend/services/vector_memory_write_service.py` | `existing` | `REPO_BASELINE` | B07 / upsert_user_memory:11 | 核对既有行为/接入或验证落点 |
| `backend/services/realtime_voice_memory_service.py` | `existing` | `REPO_BASELINE` | B08 / _write_atom:727；_finish:779；stage_deletion_fence:503 | 核对既有行为/接入或验证落点 |
| `backend/utils/character_knowledge_validate.py` | `existing` | `REPO_BASELINE` | B14 / build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | 核对既有行为/接入或验证落点 |
| `backend/routers/chat.py` | `existing` | `REPO_BASELINE` | B22 / _execute_llm_bundle:377；_persist_bundle_success:227；_mark_pack_failed:296；_sse_chat_wait_bundle:648；chat_send:720；chat_resend:758；chat_timeline:826 | 核对既有行为/接入或验证落点 |
| `tests/test_step6_vector_upsert.py` | `existing` | `REPO_BASELINE` | T04 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_memory_write_source.py` | `existing` | `REPO_BASELINE` | T05 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_realtime_voice_step028_memory.py` | `existing` | `REPO_BASELINE` | T15 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 既有写入口的索引维护接线及分态汇总（沿 STEP-004/005 协议）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让文字四类和语音两类既有写入维护同一正文口径。对应产物与本STEP验收证据。

**业务定义**：PRD §6.4/6.6：仅 value 编码；原 Key/doc_id/覆盖/来源与提取协议保持；索引失败不等于源写入失败。 来源：P01 / `F01、F02、RQ-13、RQ-14、CSTR-01`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按002全入口清单接入文字upsert_step6_vectors、语音upsert_user_memory及仍在用的vector_service旧格式写入口；仅写指定新库并复用004维护，不漏直接写路径，维持text/voice来源及合法历史格式。
2. 保持文字 11 字段、关系标量、原 Step5 回复输入与回复后的异步边界；语音有效输入/memory_items/user/private/trace/通话删除围栏保持。
3. 逐条区分源与索引状态并汇总；源保存后索引失败可独立恢复，已有成功语音 trace 不阻止补索引，不重新抽取。

4. 实际验证路径必须经过 B06 `execute_step6` → B05 `upsert_step6_vectors`，以及 B08 `_write_atom` → B07 writer → trace提交。将“源已保存、索引待修复”的结构化结果传回原包装层，不让仅索引失败逃逸为整个提取pipeline异常，不重复执行原关系等无关副作用。源明确失败仍沿既有失败边界，源未知先按操作身份核实。

5. 保持语音既有外层20秒等待；不要同步等待BM25全部成功才确认源保存。由004/005可靠登记并处理维护任务，语音取消、20秒超时或源成功trace后仍能独立补索引，不重抽取、不把trace当索引完成。以可控时钟和故障桩覆盖远端写已确认/回执未知、trace提交失败、维护执行器重启。

6. 本步只交AC18-a：正文/value、doc_id、type/user_id、text/voice来源、源/索引状态、trace与恢复身份可核对；不等待或声称新文字检索接线完成。把同一记忆测试身份和维护完成判据交STEP-019，由其负责AC18-b跨入口验收，禁止反向添加对010/完整H5的依赖。

**不在本STEP范围内**：不改内容拆解/Prompt、事实覆盖/时间，不升级语音读取，不增加 Admin CRUD。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 词项分别仅在 Key/仅在 value；文字四类、语音两类合法输出 | BM25/向量只编码 value，身份/覆盖和原输入结构保持；本步仅验证AC18-a的局部写入及索引状态，不宣称AC18-b已贯通。 | AC01 AC02 AC16 AC18 |
| 异常 | 源保存成功而索引失败 | 每条有保存成功/待修复状态，其他成功条不被扩大为失败，不重抽取。 | AC30 |
| 边界 | 同 Key 更新、语音成功 trace 后再修复 | 旧词不可作为当前有效内容；原协议/trace 幂等保持。 | AC02 AC16 AC30 |
| 文字包装层 | 从execute_step6触发源保存成功、BM25失败/超时，随后执行独立修复 | 原提取LLM与原无关副作用调用次数不因索引故障增加；保存成功/待修复可追踪，修复读当前value，不重放Step6。 | AC30-a |
| 语音包装层 | 实际_write_atom外层20秒等待，源已确认但索引延迟、外层取消或已有成功trace | 不扩大语音时限；持久任务可继续有限修复；trace不能阻断补索引，索引状态不冒充完整成功，不重新抽取。 | AC30-a AC18-a |
| 写入结果未知 | 源回执丢失/trace登记失败，远端可能已写入 | 按操作身份先核实，不盲目重复写/抽取、不把未知当源成功；维护锚点可定位，其他成功条目不被扩大为失败。 | AC30-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] AC18-a与AC30-a有真实包装层故障证据，不仅是共享writer单测；AC18-b明确移交019且本步不勾选跨入口通过。

**完成回传**：返回STEP-006、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-007] Admin 既有 CRUD 与维护反馈

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让四类新增/value 编辑及既有单删批删逐条显示真实源和索引结果。

**来源映射**：需求`F02 / F03 / F12 / RQ-13 / RQ-14`；负责验收`AC02 / AC10 / AC13 / AC30`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-005《有限索引恢复执行器》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/memory-knowledge/admin-ui.md` | `existing` | `CONTRACT` | C02 / L1（当前后台页面） | 核对既有行为/接入或验证落点 |
| `backend/services/character_knowledge_service.py` | `existing` | `REPO_BASELINE` | B09 / create_entry:157；update_entry:200；delete_entry:256；list_entries:85 | 核对既有行为/接入或验证落点 |
| `backend/services/user_vector_memory_service.py` | `existing` | `REPO_BASELINE` | B10 / create_entry:172；update_entry:215；delete_entry:258；list_entries:103 | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/knowledge_mgmt.py` | `existing` | `REPO_BASELINE` | B11 / L1（知识新增/value 编辑/删除路由） | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/users.py` | `existing` | `REPO_BASELINE` | B12 / L44/258/500（历史对话角色/查询及user/private原CRUD；本次A32定向复读） | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/memory_mgmt.py` | `existing` | `REPO_BASELINE` | B13 / vector-db-config GET/PUT/test:L161–320；batch_delete_memories:430；search_memories_global:364 | 核对既有行为/接入或验证落点 |
| `admin/pages/memory-rules.html` | `existing` | `REPO_BASELINE` | U03 / L330（Step6 Prompt、全局列表和批删） | 核对既有行为/接入或验证落点 |
| `admin/pages/knowledge.html` | `existing` | `REPO_BASELINE` | U04 / L247（只读 Key、value 编辑、删除） | 核对既有行为/接入或验证落点 |
| `admin/pages/user-detail.html` | `existing` | `REPO_BASELINE` | U05 / L710–935（历史对话）；L1005–1195（user/private记忆编辑/回执） | 核对既有行为/接入或验证落点 |
| `tests/test_admin_character_knowledge.py` | `existing` | `REPO_BASELINE` | T08 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 兼容响应增量与 CRUD 维护关联反馈（字段按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `admin/static/js/admin-api.js` | EXISTING / A32-11 | 精确可选Idempotency-Key映射，保留认证/错误包装 |
| `GET /api/admin/memory-write-operations/{operation_id}` | PLANNED / P01 §6.8.4 | 自有源写回执，不是全局维护查询 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让四类新增/value 编辑及既有单删批删逐条显示真实源和索引结果。对应产物与本STEP验收证据。

**业务定义**：PRD §6.6.1：源保存成功但索引失败仍按保存成功收口，给警告/维护入口；既有查重、只改 value 和各入口权限保持。 来源：P01 / `F02、F03、F12、RQ-13、RQ-14`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 覆盖角色公开/知识及 user/private 的直接 upsert/delete 路径与全局 user 批删；不得绕开当前凭据/锚点。
2. API 兼容旧信封且逐条返回或可查身份、源结果、索引状态、错误与维护关联，分别汇总；未知先核实，不盲目再次新增。
3. 现有三个 CRUD 页面展示部分成功/待核实/索引警告；保留同 Key 已存在则编辑规则和用户详情 ops_admin 既有局部权限，不扩展新诊断权限。

4. 分别修改U04 openModal/saveModal/删除、U05 saveKvEntry/deleteKvEntry/showKvAddModal，以及U03 renderGlobalTable/doGlobalDelete/globalDeleteOne。源成功+索引待修复仍正常关闭新增Modal或退出行内编辑，页内警告/列表徽标保留；源失败留输入，源未知禁本次重复提交但可关闭和只读核实。不要给全局user页新增创建/编辑。
5. 按P01 §6.8.4在三类源API和batch-delete接入可选Idempotency-Key，沿004操作锚点返回write_result；新增自有GET memory-write-operations/{operation_id}并注册路由。此GET按发起管理员+当前来源读权限/type/user范围校验，不调用全局诊断管理接口，不给ops_admin开放维护列表。
6. 在U07 adminRequest增加仅映射Idempotency-Key的可选requestExtra.idempotencyKey，保留既有返回/错误和Authorization处理。受控页面提交前生成身份，session仅存最小未核实ID/来源；回页GET核实、退出清理，不自动换ID重发。不把网络错误或not_found写成源失败。
7. 批删保持1～100请求校验，仅user；唯一doc_id逐项处理/计数，兼容deleted_count/failed_doc_ids并增量返回详细源/索引状态。按2成功(含1索引待清理)+1失败+1未知的固定夹具断言源合计4，索引不能再相加；部分成功不重放整包。
8. 结果区维护链接使用task_id并由角色控制，无权者仍可看原页面所需摘要但不出现403跳转。按当前代次刷新列表，旧删除/更新回执不影响同ID新代；刷新列表失败不抹掉已确认源成功。接口/页面输出安全转义，不改存储正文。新维护页面由018交付，本步可验证链接契约但不得据此提前部署。

**不在本STEP范围内**：不增加改 Key/H5 CRUD，不将全局 user 批删扩大到 private；维护历史新页面归 STEP-018。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 四类新增/value 更新、单删/批删 | 同口径索引联动，旧正文/已删代次不作为有效记忆。 | AC02 AC10 |
| 异常 | HTTP 成功业务失败、响应丢失、批量部分成功 | 源与索引分态逐条可追踪；成功正文不提示重建，未知先核实。 | AC30 |
| 边界 | 同 Key 再点击新增、不同用户/角色操作 | 原查重与权限不回退；已保存状态不给自动重复提交。 | AC13 AC30 |
| 逐页面源/索引反馈 | 知识库Modal、user/private新增Modal及行内value编辑，成功索引失败/源失败/未知 | §6.8.4收口正确；未知只读核实，部分成功不重复新增；列表读取失败不抹掉保存回执 | AC30-b |
| 批次分类与重复 | 4唯一项含2删除成功其中1待清理、1失败、1未知；重复/非法/private及响应丢失 | 源分类合计4；保留旧字段，未知不当失败，索引维度不重计；已成功项不整包重删 | AC30-c |
| 权限与展示 | ops查看自己的user操作结果、猜其他operation_id、HTML正文/错误与确认框 | 只读回执按来源范围及本人，未获全局维护权；纯文本不执行脚本 | AC13-a AC13-b |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-007、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-008] 历史现存正文完整回填

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：提供新库正常回填/补索引与一次性清理工具，隔离演练T0封写、保留数据核对及中断续跑。

**来源映射**：需求`F08 / RQ-13 / RQ-14 / CSTR-10`；负责验收`AC11 / AC23 / AC31`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-001《索引基础设施与完整遍历核验》的已验证输出；STEP-006《文字及语音写入接入索引维护》的已验证输出；STEP-007《Admin 既有 CRUD 与维护反馈》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/utils/dashvector_client.py` | `existing` | `REPO_BASELINE` | B04 / build_filter:19；search:78；upsert:153；delete:210；list_by_filter:232；fetch_by_ids:273 | 核对既有行为/接入或验证落点 |
| `backend/utils/character_knowledge_validate.py` | `existing` | `REPO_BASELINE` | B14 / build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | 核对既有行为/接入或验证落点 |
| `backend/services/vector_service.py` | `existing` | `REPO_BASELINE` | B15 / L1（历史 mem_* 自由正文与普通 Agent 检索） | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| 实际全量回填/对账入口与运维说明（路径/命令按已核实项目约定确定，不在草稿虚构生产命令）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `回填run/逐项结果持久DTO及数据生产接口` | PLANNED / P01 §6.8.6 | 008生产，017读取，018显示；物理schema由002 |

**输入**：P01所列需求、S15及前置输出。**输出**：新库正常回填/补索引、持久对账记录，一次性清理工具/dry-run/隔离演练；实际清理归022，不搬迁旧Cosine。在线修复仍校验当前代，不把清理混进日常启动或维护任务。

**业务定义**：PRD §6.6/§9.3.1：KV 仅 value；可靠旧 mem_* 自由文本用完整 content；不能生成 Key/改写正文/补事实时间。 来源：P01 / `F08、RQ-13、RQ-14、CSTR-10`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按001方案实现新库当前正文的完整回填/补索引、断点/限速/分类；保持doc_id及合法元数据，按实际模型生成/验证dense并L2、固定版本BM25；新库现存正文来源须可信完整，异常单列，不重抽取旧事实。不复制旧Cosine，F08/后台回填记录能力仍交付。
2. 复用持久锚点与当前凭据，提交前复核代次；协调在线增改删和索引重建，不重复、不用旧值覆盖/删后复活。
3. 按002白名单实现并隔离演练一次性清理：显式环境/对象/run与dry-run→全部入口/调度/worker及保留数据封写并核实在途→T0后重取保留身份/值基线→向量/SQL/缓存任务分阶段清理→零数据/无回写/保留值不变验证。覆盖共享relationship及四项画像/Future变更历史、语音弱引用/正文副本、旧Future及主动队列；中断核实后幂等续跑，未知阻断；完成标记确认持久化后才开放；提交未知先核实，完成未开放只续开放步骤，防重启清新数据。实际在线执行归022，不删无关业务。

4. 按P01 §6.8.6产出持久run_id、环境模式、范围/版本、阶段、起止/最后更新、基线/游标安全摘要/对账截止点、分类计数和逐项关联任务；不要只输出stdout。所有分类和完成判断由回填/对账组件生成，区分扫描数/唯一源数/尝试数，可信总量未知时保留null或明确未知标记。
5. 在隔离库构造超展示cap的批次及中断/异常/未知/并发增改删，证明状态持久后可读取、续跑不重放旧值；完成须全量身份+正文+增量闭合。交017真实记录夹具和读取DTO；008不依赖后台页面或新管理API，不新增网页回填启动功能。

**不在本STEP范围内**：不复用展示 cap/身份过滤 helper，不重抽取历史，不恢复同 Key 覆盖事实，常规补索引不自动清理 mem_*；S15一次性清理中的旧存量按明确清单处理。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 超cap新库隔离可信源、标准KV和自由正文；按002清单构造清理/保留样本 | 新库回填完整且ID/正文保持、仅dense归一化；清理演练后向量/旧正文/画像预约为空，资料数值及日记/朋友圈身份和值不变 | AC11 CSTR-10 |
| 异常 | 回填读取失败；清理跨存储中断/未知、共享表或目标错配、旧worker迟到、完成标记未知/完成后开放前崩溃 | 缺口可追踪并核实续跑；不误删保留字段、不开放、不回写；未知先核实，完成后只续开放，普通重启不删除新数据 | AC11 AC23 CSTR-10 |
| 边界 | 回填时在线更新/删除/同 ID 重建 | 提交前资格复核；身份+摘要+增量对账，无旧代复活。 | AC11 AC31 |
| 回填持久记录生产 | 超cap数据、未知总量、中断、格式异常/未知索引与在线变更 | run/阶段/分类/截止点可持久读取；不把cap或脚本退出码当完成；真实记录交017 | AC11-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32仅对真实回填run/逐项持久记录生产、计数/完成条件及上述回填测试记录输入、预期和实际输出，并把DTO/夹具交017；不要求尚未实施的管理API或页面结果。AC11-a只记录008生产分项，017查询、018页面、019集成后续收口，008完成不反向依赖它们。

**完成回传**：返回STEP-008、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-009] BM25 词组与确定性改写补齐

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让四路 Query 字段保留原结构并按当前 v3.2 区分跳过和异常。

**来源映射**：需求`F15 / F07 / RQ-01 / RQ-10`；负责验收`AC07 / AC20 / AC21 / AC32`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32验收映射补充**：AC33 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/query_rewrite_service.py` | `existing` | `REPO_BASELINE` | B01 / QueryRewriteOutput:28；_parse_query_rewrite_output:271；_build_step1_5_prompt:137；execute_query_rewrite:307 | 核对既有行为/接入或验证落点 |
| `backend/services/chat_prompt_view_service.py` | `existing` | `REPO_BASELINE` | B29 / get_step15_prompt_view:47；get_step3_prompt_view/get_step8_prompt_view（只读规则） | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/chat_prompt_view.py` | `existing` | `REPO_BASELINE` | B30 / view_step15_prompt:26 | 核对既有行为/接入或验证落点 |
| `admin/pages/chat-prompt-step15.html` | `existing` | `REPO_BASELINE` | U06 / L1（主链/Step8 只读预览） | 核对既有行为/接入或验证落点 |
| `tests/test_query_rewrite_service.py` | `existing` | `REPO_BASELINE` | T01 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_chat_prompt_view.py` | `existing` | `REPO_BASELINE` | T13 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 字段存在性与有效查询载体（内部类型按 STEP-002 定稿）；预览使用既有同源函数。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让四路 Query 字段保留原结构并按当前 v3.2 区分跳过和异常。对应产物与本STEP验收证据。

**业务定义**：PRD §6.5/7.1.1：Keywords 是空格分隔字符串；Question 完整语义；只合法实际存在的空串/无才主动跳过。 来源：P01 / `F15、F07、RQ-01、RQ-10`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 更新四路 Keywords Prompt 规则/few-shot：本路实体与必要限定词、去套话、有限有据同义词，不补年份城市/权重/稀疏向量。
2. 解析保留字段存在性：缺省/null/非字符串不借默认空串跳过；Question 缺失用本次原输入，Keywords 不可用则用有效 Question，保留其他有效路；非法 CandidateKeys 仅警告。
3. 主链/Step8 只读预览和运行时同源；补齐不加专用 LLM，Step8 原输入仍为自身 future_action；时间编排交 STEP-012。

4. 按P01 §6.8.9复核后台Step1.5主链/Step8预览仍直接调用同源模板；旧字段结构保持，只读GET不运行改写LLM。将新词组职责与输入source映射的接口样例交013/019，不能仅修改页面静态说明而运行模板未改。

**不在本STEP范围内**：不改 Step6/语音内容提取，不新增统一 Query/补齐调用，不在本 STEP 接真实 BM25/rerank；AC20在本节点仅验Prompt规则/模板、解析及字段协议，真实模型词组/Question语义质量归STEP-021。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 专名/套话/指代/模糊时间/否定的模板与解析协议样本 | Prompt规则/few-shot直接表达本路实体有据、去套话及Question完整语义；固定协议样本的字段名/字符串类型和路隔离保持。该局部验证不判真实模型语义质量通过。 | AC20 AC21 |
| 异常 | Question/Keywords 缺省、null、非字符串、空对象/非法 JSON | 原输入确定性补齐，有效字段保留，不增加补齐 LLM。 | AC07 AC32 |
| 边界 | 显式空 Question 与非法 CandidateKeys | 前者跳过，后者不拖垮有效路；预览仍只读。 | AC07 AC21 AC32 |
| 模板预览 | GET主链与Step8查询模板 | 新词组与实际模板同源，预览零LLM，交019接口回归 | AC33-b |

**完成标志**：

- [ ] 当前STEP负责的模板/解析/字段协议子条款通过且有输入/预期/输出证据；AC20真实模型语义子验收仍由STEP-021完成，不以本节点DONE代替真实质量通过。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-009、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-010] 四路双通道候选与有效性去重

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让每路独立召回两组合法候选并保留真实来源和状态。

**来源映射**：需求`F04 / F07 / RQ-01 / RQ-11 / RQ-19 / RQ-23 / CSTR-06`；负责验收`AC03 / AC08 / AC13 / AC21 / AC28 / AC31 / AC32`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-003《请求有效配置与后台独立数量》的已验证输出；STEP-004《可信当前凭据与派生索引维护核心》的已验证输出；STEP-009《BM25 词组与确定性改写补齐》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | 核对既有行为/接入或验证落点 |
| `backend/utils/dashvector_client.py` | `existing` | `REPO_BASELINE` | B04 / build_filter:19；search:78；upsert:153；delete:210；list_by_filter:232；fetch_by_ids:273 | 核对既有行为/接入或验证落点 |
| `backend/utils/character_knowledge_validate.py` | `existing` | `REPO_BASELINE` | B14 / build_doc_id:54；parse_doc_id:67；parse_value_from_content:135 | 核对既有行为/接入或验证落点 |
| `backend/services/embedding_service.py` | `existing` | `REPO_BASELINE` | B20 / get_embedding:30；_call_embedding_api:122 | 核对既有行为/接入或验证落点 |
| `tests/test_multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | T02 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_dashvector_client.py` | `existing` | `REPO_BASELINE` | T06 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| BM25 查询/独立向量候选适配与结构化通道结果（路径/类型按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让每路独立召回两组合法候选并保留真实来源和状态。对应产物与本STEP验收证据。

**业务定义**：PRD §6.3/7.1.1：Question 供向量、Keywords 供 BM25；仅 type/user_id 隔离和独立候选上限，不读 key_l2 或旧 threshold。 来源：P01 / `F04、F07、RQ-01、RQ-11、RQ-19、RQ-23、CSTR-06`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 在指定新Collection上按新协议分别查询dense/BM25获得八组候选，不以一次混合TopK代替；稠密query经004统一归一化，保留真实来源分，关闭新文字链原分过滤（含合法负分）；其他现用消费者按S14由019适配。
2. 通道失败保留另一路成功且不替换有效查询；BM25 无可编码词项不发空 sparse/无条件请求，与错误和有词无匹配区分。
3. 送 rerank 前按可信当前凭据校验；按路/身份去重保留原分/原名次/代次；不同正文来源只保留可证明当前者，不把旧来源分挪给新正文。

**不在本STEP范围内**：不进行路间去重/全局排序，不删分类元数据；其他现用入口的DotProduct筛选适配由019完成，本步不冒称已完成其回归或重排/最终注入。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 分类不匹配；有效 Question/新词组；两用户相似正文 | 合法正文可入本路双候选集，职责/来源和用户隔离正确。 | AC03 AC13 AC21 |
| 异常 | 单/双通道失败、正常无匹配、无有效词项 | 成功结果保留；空候选不需重排；三种空因可区分且不发无条件查询。 | AC08 AC32 |
| 边界 | 负分合法候选、调旧阈值、双通道不同代次且 query/fetch 滞后 | 不按原分过滤；只保留可信当前来源，不移借旧分/名次，不确定者排除并记录。 | AC28 AC31 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-010、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-011] 路内完整 rerank 与故障融合

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：得到四份只按本路 Question 排序并可解释降级的结果。

**来源映射**：需求`F05 / F07 / RQ-01 / RQ-11 / RQ-12 / RQ-23`；负责验收`AC04 / AC09 / AC28 / AC32`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出；STEP-010《四路双通道候选与有效性去重》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | 核对既有行为/接入或验证落点 |
| `tests/test_multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | T02 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 路内 rerank 适配和已定融合实现（模型参数不在本草稿填值）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：得到四份只按本路 Question 排序并可解释降级的结果。对应产物与本STEP验收证据。

**业务定义**：PRD §6.3/7.1.1：空路不调用；非空发送全部合法候选正文；正常门槛准入，失败名次融合且重排分为空。 来源：P01 / `F05、F07、RQ-01、RQ-11、RQ-12、RQ-23`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 适配已定阿里云实际模型/API/地域，绑定候选输入顺序/当前正文，要求全量排序/分数，不提前按最终数量只请求 TopN。
2. 检查唯一范围内整数索引、覆盖完整、有限且 API 合法分数；缺项/重复/越界/NaN/错误信封整路降级，返回正文不能替换权威输入。
3. 按冻结门槛正常准入；降级按手算验证的名次融合/单通道保序，不混原始分、跨路分；同分固定输入顺序再稳定身份；检查 Query/单篇/全请求限制，已知超限不发送/不重试/不截断/不分批比分。

**不在本STEP范围内**：不生成事实可靠度，不把融合分冒充 rerank 分；最终注入与阶段总时限由其他 STEP 负责。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 四个不同 Question 及完整合法返回 | 请求只有本路候选；低相关可整路为空，同分稳定。 | AC04 AC09 |
| 异常 | 超时/非法索引/缺项重复/非法分/错误信封 | 仅本路降级，重排分空；不套门槛，其他路不受影响。 | AC09 AC32 |
| 边界 | 空路/单通道/输入限制超限/低旧向量分 | 空路零请求；单通道保序；超限不发非法请求；候选门槛未偷偷恢复。 | AC28 AC32 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-011、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-012] 45 秒加 45 秒检索编排

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让两阶段截止时间、一次重试和迟到收口真实约束所有四路。

**来源映射**：需求`F07 / F11 / RQ-20`；负责验收`AC07 / AC08 / AC09 / AC22`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-009《BM25 词组与确定性改写补齐》的已验证输出；STEP-010《四路双通道候选与有效性去重》的已验证输出；STEP-011《路内完整 rerank 与故障融合》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/query_rewrite_service.py` | `existing` | `REPO_BASELINE` | B01 / QueryRewriteOutput:28；_parse_query_rewrite_output:271；_build_step1_5_prompt:137；execute_query_rewrite:307 | 核对既有行为/接入或验证落点 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | 核对既有行为/接入或验证落点 |
| `backend/services/embedding_service.py` | `existing` | `REPO_BASELINE` | B20 / get_embedding:30；_call_embedding_api:122 | 核对既有行为/接入或验证落点 |
| `backend/utils/llm_client.py` | `existing` | `REPO_BASELINE` | B21 / chat_sync:116 | 核对既有行为/接入或验证落点 |
| `backend/routers/chat.py` | `existing` | `REPO_BASELINE` | B22 / _execute_llm_bundle:377；_persist_bundle_success:227；_mark_pack_failed:296；_sse_chat_wait_bundle:648；chat_send:720；chat_resend:758；chat_timeline:826 | 核对既有行为/接入或验证落点 |
| `backend/services/step8_subchain.py` | `existing` | `REPO_BASELINE` | B27 / execute_step8_subchain:56；提交后收尾:L216起；_fallback_write_agent_message:376；_decay_gate_and_update:397 | 核对既有行为/接入或验证落点 |
| `tests/test_query_rewrite_service.py` | `existing` | `REPO_BASELINE` | T01 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | T02 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_step024_step8_subchain.py` | `existing` | `REPO_BASELINE` | T12 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 共享检索阶段截止/取消与调用重试适配（内部名称按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让两阶段截止时间、一次重试和迟到收口真实约束所有四路。对应产物与本STEP验收证据。

**业务定义**：PRD §7.2：改写最多45秒；整个 Step2 另45秒且四路共用；临时失败调用最多重试一次，退避在预算内。按S10/§7.2，每个业务阶段的实际deadline=min(该阶段起点+45秒, 调用方传入的原整轮deadline)；主链/OpenAPI/Step8整轮固定180秒及其起点分别由014/015负责，诊断仍沿自身已定阶段规则。 来源：P01 / `F07、F11、RQ-20`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 接收业务调用方的原整轮deadline，每阶段取阶段起点+45秒与该deadline中的较早者；上下文/排队已消耗时间不能在检索阶段重获。用实际阶段截止时间约束调用/退避/收口，给后续重排和本地收口留时间；外底层重试不能叠加，范围外共享默认重试不变。
2. 改写失败/耗尽以原输入及合法字段进入 Step2 自身预算；参数/鉴权/非法输出直接降级，不反复修补。
3. 预算不足不再重试，截止取消未完成调用/忽略迟到/不发新请求；已重排成功保留门槛，候选已有但重排未完路按融合，空路为空。

**不在本STEP范围内**：不把90秒当整轮响应承诺，不将检索阶段45秒套到语音读取/回复模型/索引后台恢复；业务180秒起点与终态由STEP-014/015负责，不给独立诊断新增180秒整轮承诺。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 成功通道与暂时失败通道同时存在 | 成功不重跑；每失败调用至多一次重试，候选保留。 | AC08 AC22 |
| 异常 | 参数/鉴权/非法输出，耗尽阶段与迟到结果 | 直接降级；截止后无新请求/迟到注入，保留已有结果。 | AC07 AC09 AC22 |
| 边界 | 四路慢请求及多次底层重试配置；业务阶段开始时整轮剩余少于45秒 | 整体Step2不逐路累加，45+45含退避；实际阶段截止取阶段+45与原整轮截止较早者，切换阶段/重试均不延长180秒原截止；主链/OpenAPI/Step8同规则。 | AC22 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-012、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-013] 完整 Prompt 选择与最终有效性

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：输出与实际渲染一致的结构化选入结果并硬阻断超总预算。

**来源映射**：需求`F06 / F12 / RQ-05 / RQ-07 / RQ-08 / RQ-09 / CSTR-01 / CSTR-06 / CSTR-08`；负责验收`AC04 / AC05 / AC06 / AC12 / AC13 / AC26 / AC31 / AC33 / CSTR-01`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-003《请求有效配置与后台独立数量》的已验证输出；STEP-004《可信当前凭据与派生索引维护核心》的已验证输出；STEP-011《路内完整 rerank 与故障融合》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/prompt_builder.py` | `existing` | `REPO_BASELINE` | B03 / count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | 核对既有行为/接入或验证落点 |
| `backend/services/agent_service.py` | `existing` | `REPO_BASELINE` | B34 / _search_memories_for_agent:688；generate_and_save_message:276 | 核对既有行为/接入或验证落点 |
| `tests/test_prompt_builder.py` | `existing` | `REPO_BASELINE` | T03 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 结构化 Prompt 构建/选入结果及新链选择 helper（类型按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |
| `backend/routers/admin/prompt_mgmt.py` | `existing` | `REPO_BASELINE` | B31 / test_prompt:617；mock:L639起；字符串消费:L665起 | 显式旧Prompt测试消费者，须保留mock/草稿/字符串接口 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `backend/services/chat_prompt_view_service.py` | EXISTING / A32-12 | get_step3_prompt_view/get_step8_prompt_view |
| `admin/pages/chat-prompt-step3.html、chat-prompt-step8.html` | EXISTING（目录与同源API定位） | 按§6.8.9修改只读展示 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：输出与实际渲染一致的结构化选入结果并硬阻断超总预算。对应产物与本STEP验收证据。

**业务定义**：PRD §6.3.1：角色 cg→cp→ck rank 轮转，user 独立；完整条目计数，放不下停该路；二次裁剪逆成功选入序。§7.1“越权或不可信候选”/§11.1规定候选正文仅作数据，不覆盖系统指令或可信用户归属。 来源：P01 / `F06、RQ-05、RQ-07、RQ-08、RQ-09、CSTR-01、CSTR-06、CSTR-08`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按四最终上限及冻结模块预算选整条，标题/标签/分隔符计入定稿计数；空路跳过，不跨路比分；保留 route/doc_id/正文代次和成功选入顺序。
2. 沿既有模块优先级从实际初选集合删尾：角色逆成功选入序、各路前缀、不回候选补位；最终使用前可信校验，失效项及同路已选后缀一并淘汰，重计数。
3. 同次输出实际完整 Prompt、初选/最终清单/渲染/token及原因，并沿STEP-004定稿协议交付最终校验到实际交模之间的保护/有效性结果，由调用方遵守，不能只在构建返回时fetch一次。最终仍超预算阻断且不得换预算；新旧helper分离，普通Agent保持。
4. 新渲染直接维护候选数据/系统指令信任边界：value即使含指令、角色标记或分隔符也仅为候选数据，不能决定受控系统指令来源/结构、route/doc_id或用户归属；这些仍由受控模板与可信元数据决定。不新增安全模型，也不改提取正文/Key/既有安全链。

5. 显式接入B31 `test_prompt`：新业务/诊断消费结构化结果，旧测试经兼容包装取字符串文本供原模型调用及 `len(full_prompt)`；不能把结果对象直接传入。保留当前配置、`use_draft`、`system_prompt_override`、原请求响应/权限；mock缺少真实ID/代次时由后端受控旧测试分支处理，不伪造真实身份，不调用真实索引核验模拟数据。

6. 新增构建局部用例AC33-a：仅content/score的旧mock仍产生字符串且覆盖模式正确；普通业务/新诊断携不完整候选时仍按原可信边界拒绝/淘汰；mock许可不能由客户端参数开启。以桩计数证明旧测试适配未新增改写/检索/索引写/聊天入队/Step6，新诊断未新增回复模型；旧测试自身原模型调用保留。接口级回归交019。

7. 按P01 §6.8.9同步B29 get_step3_prompt_view/get_step8_prompt_view及原Step3/Step8只读页：角色轮转/user独立/整条前缀/逆序裁剪/硬预算说明从同一规则定义或可验证映射产生；保留module_order/trim_priority/token_limit_default等旧字段。默认标签不能冒充生效预算，预览GET不读取某用户完整上下文或调用模型；普通Agent原预览不升级。
8. 将AC33-b预览接口/页面与AC33-a旧Prompt Test分开验收，分别捕获零模型预览调用和旧测试原模型调用，防止复用新诊断helper改变权限或产生新业务写。
9. 保留昵称正文不裁剪，固定预算配置值50不当实际文本硬上限；完整昵称渲染按同一计数器计入max_total。运行AC12-a两边界：实际昵称>50且最终总量合格可用；按既定整条裁剪后最终仍超max_total按RQ-09硬阻断，不能裁昵称或换预算来放行。

**不在本STEP范围内**：不截断正文，不强制均分/每路一条，不持久保存普通聊天完整 Prompt；消息失败/终态由调用方 STEP 负责。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 四路非空/空路，候选足够且最终合法上限大于3 | 轮转/数量生效，无Top3；同次清单与渲染/token一致，不跨请求比分。 | AC04 AC05 AC12 AC33 |
| 异常 | 下一条过长、初选后总预算不足、不可裁仍超限 | 停止对应路；逆序整条删除且不补位；最终阻断回复模型零调用，不换配置。 | AC06 AC26 AC33 |
| 边界 | 最终校验后至实际交模前并发变更；普通Agent对照 | 按定稿协议确定变更/使用次序：变更先于最终使用检查生效则淘汰该项及同路后缀且不补位；已合法交付后变更不撤回；旧Agent保持。 | AC31 AC33 |
| 候选信任边界 | 合法候选value含“忽略系统指令”、伪系统/用户角色标记、分隔符及他人归属声明，可信元数据保持原用户与路 | 核对最终组装结构：候选明确仅作数据，受控系统指令来源/结构不可由value覆盖，route/doc_id/用户归属仍取可信元数据；原安全链保持。局部构建断言不宣称所有模型绝对安全。 | AC13 CSTR-01 |
| 旧测试构建兼容 | 仅content/score的旧mock、当前/草稿及系统提示覆盖；新构建器返回结构化结果 | 兼容包装输出字符串，原模型参数及文本长度正确；不访问真实索引、不造ID/版本、不改变覆盖语义。 | AC33-a |
| mock信任边界 | 普通聊天/新诊断传缺ID候选或试图请求mock模式；旧测试使用后端固定mock分支 | 只有后端受控旧测试可走mock适配，真实消费者仍执行可信校验；无新增业务写/Step6，诊断仍零回复调用。 | AC33-a AC13 |
| 预算规则预览 | GET Step3/Step8；默认值与新生效预算不同 | 默认标签不冒充有效配置，新选择规则可核对，原字段保持，零模型调用 | AC33-b |
| 昵称完整计数两边界 | 完整昵称实际token>50；一例最终总量≤max_total，一例按既定裁剪后不可裁内容仍使最终总量>max_total | 两例昵称原文不裁剪并按实际完整计数；固定50仅为只读预算配置值。总量合格可用，最终超总量按RQ-09阻断、回复模型零调用，不换配置 | AC12-a AC26 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] AC33-a局部构建测试通过并将旧API模式矩阵交019；普通Agent原helper及真实候选校验未被兼容逻辑削弱。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-013、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-014] 主文字与 OpenAPI 唯一终态

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让已入队文字任务按原固定180秒整轮deadline收敛为互斥终态。

**来源映射**：需求`F07 / F11 / F12 / RQ-09 / RQ-22 / RQ-24`；负责验收`AC14 / AC15 / AC26 / AC27 / AC29 / AC34`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32验收映射补充**：AC13 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出；STEP-012《45 秒加 45 秒检索编排》的已验证输出；STEP-013《完整 Prompt 选择与最终有效性》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/chat-emotion/api.md` | `existing` | `CONTRACT` | C06 / L1（文字消息与 SSE） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/chat-emotion/data.md` | `existing` | `CONTRACT` | C07 / L1（消息状态及代际） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/openapi/api.md` | `existing` | `CONTRACT` | C08 / L1（OpenAPI 入口与信封） | 核对既有行为/接入或验证落点 |
| `backend/routers/chat.py` | `existing` | `REPO_BASELINE` | B22 / _execute_llm_bundle:377；_persist_bundle_success:227；_mark_pack_failed:296；_sse_chat_wait_bundle:648；chat_send:720；chat_resend:758；chat_timeline:826 | 核对既有行为/接入或验证落点 |
| `backend/services/chat_service.py` | `existing` | `REPO_BASELINE` | B23 / await_bundle_payload:206；enqueue_send:251；enqueue_resend:287；new_generation_for_user:171；schedule_recovery_bundle:129 | 核对既有行为/接入或验证落点 |
| `backend/services/chat_queue_service.py` | `existing` | `REPO_BASELINE` | B24 / try_acquire_bundle_lock:81；release_bundle_lock:89；schedule_debounced:49 | 核对既有行为/接入或验证落点 |
| `backend/services/open_chat_service.py` | `existing` | `REPO_BASELINE` | B25 / open_send:21；open_resend:46；_payload_to_api_response:57 | 核对既有行为/接入或验证落点 |
| `backend/routers/open/chat.py` | `existing` | `REPO_BASELINE` | B26 / L1（OpenAPI send/resend） | 核对既有行为/接入或验证落点 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B40 / L37（请求数据库依赖提交点） | 核对既有行为/接入或验证落点 |
| `tests/test_chat.py` | `existing` | `REPO_BASELINE` | T10 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 整轮 deadline/终态仲裁与有界未知核实协议（持久结构/参数按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `backend/routers/admin/users.py` | EXISTING / A32-01 | get_user_conversations及原历史读取权限 |
| `admin/pages/user-detail.html` | EXISTING / A32-02 | 历史对话状态/分页/查询，不限原记忆Tab |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让已入队文字任务按原固定180秒整轮deadline收敛为互斥终态。对应产物与本STEP验收证据。

**业务定义**：PRD S10/§7.3/7.4/9.7：新有效generation合法入队起固定180秒，覆盖后续防抖/排队、上下文、Step1.5/2、Prompt校验、Step5、安全/Step5.5与提交；同代恢复/重连/重试不刷新起点或续时，单连接断开不取消业务。 来源：P01 / `F07、F11、F12、RQ-09、RQ-22、RQ-24`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 主链send/resend与OpenAPI消费同次四路结果/Prompt/冻结配置，并遵守STEP-013交付的最终校验到实际交模保护协议，不能把Prompt返回时检查代替使用点检查。合法入队持久记录原起点及+180秒deadline，检索按STEP-012阶段与整轮较早截止；防抖/排队、检索外上下文、Step5、安全/Step5.5和提交均纳入，Step6异步提取及索引后台恢复不计入回复业务预算。
2. 持久仲裁成功/失败/作废；提交与 deadline/generation/锁所有权协调，未知提交先核实且有界核实/告警，不允许超限首次成功或旧代改新代。
3. 连接 Future 注销只释放等待资源；恢复锁按剩余生命周期持有/续期/释放且旧持有者不得删新锁；预算/整轮失败持久可重发态，刷新一致、resend不重复user，不落成功assistant/Step6；截止前成功不因传输迟到覆写失败。

4. 在B22/B23/B25/B26贯通002定稿身份；入口校验通过后以可信user+operation+request_id原子占有/判重，同ID同输入返回同次状态，不重新扣额度、建user、换代或启动LLM；同ID异输入返回明确冲突，不同ID同正文视为不同合法提交。显式resend关联原允许消息但不新增user；查询身份必须用户隔离，不能依赖文本时间。

5. 落地 P01 §7.4.1 两个只读GET，沿既有信封返回admission状态、业务终态/未知、user/assistant身份、原提交及当前有效generation/deadline关联、单调状态版本与服务端can_resend。保留H5两个既有标识，OpenAPI头为可选；旧调用方不提供ID时不能宣称回执全丢仍精确核实。查询不重新入队/扣额度/换代/续时；明确not_found、admission未知与commit未知，未知期间不可盲目重发。

6. 把新消息持久保存、额度处理、有效代切换与调度注册按002原子/可恢复设计接线。注入“旧代运行中新输入保存失败”验证旧代不因未确认合法的新提交误作废。独立确认请求身份记录与业务generation非一一恒等：新合法输入承接旧pending消息时更新其当前归属，旧请求查询回正确参与结果，原ID不重复建消息。

7. 增加不依赖满队的当前文字任务核实/截止收口入口：1、2、3、4条pending分别在入队/调度/commit回执窗口模拟进程退出，按持久身份和原180秒截止恢复判断；已提交保持成功，确认未提交且截止耗尽才失败，不能刷新deadline或继续首次成功。未能核实时转待核实与有限告警，不保持虚假正常执行中；不承诺自动恢复原模型流。

8. 扩展B12 get_user_conversations的user行响应，按P01 §6.8.2附加权威processing_state/status_reason/state_origin/state_revision/status_observed_at；保留原_USER_BUSINESS_READ_ROLES、日期/分页信封、sort_seq及agent行语义。投影复用本步骤同源状态读取，不拿用户JWT或request参数绕过管理员鉴权。
9. 先分页消息再批量关联当前归属，验证一个user行的多次提交/承接不放大total；conversation/agent同ID以复合身份区分。确认成功保持成功；旧代被新代承接显示新状态；commit未知、状态依赖不可读和deadline过期未确认不得伪装失败。只读投影不仲裁写库/换代/启动恢复；旧历史来源有证据才按legacy回退。
10. 将状态接口夹具和修订号规则交019，至少包括成功、pending、budget/deadline失败、unverified、superseded无承接/有承接、legacy及读取失败。完成AC14-a后端与AC14-b查询子项；页面手动刷新及乱序由019验收，不新增后台轮询/重发/停止。

**不在本STEP范围内**：不以客户端标识已发送推定幂等已生效，不新增完整任务平台/推送/停止按钮，不改输入与输出安全职责或原 Step6 输入。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 两阶段接近各45秒，仍在合法入队后180秒内成功提交，断线期间成功或响应迟到 | 既有响应/SSE兼容；一次成功提交，截止前已合法成功不被迟到传输改失败，Step6仅原成功边界触发，回读可见。 | AC14 AC15 AC27 AC29 |
| 异常 | 超token总预算、合法入队后180秒耗尽且未确认成功、提交回执未知 | token预算阻断Step5/5.5/6零调用；时间耗尽按仲裁收口，不再首次成功提交或触发Step6。未知commit先有界核实/告警，按真实提交收敛，不以连接错误覆盖成功，不续时或放行重复重发。 | AC26 AC27 AC34 |
| 异常-连接 | 单纯HTTP/SSE取消，任务已合法入队 | 仅注销连接等待，不标业务失败/取消任务，继承原deadline继续；未知接收先核实。 | AC29 |
| 边界 | 固定180秒前后提交竞争；新代作废旧代、同代恢复/重连/重试、旧锁持有者迟到 | 同代继承原起点和180秒deadline，覆盖防抖/排队不续时；成功/失败/作废互斥，截止后无首次迟到成功，旧代不改新代/删新锁，无重复user/assistant；锁持有/续期按所有权和剩余生命周期，不能仅改TTL常量。 | AC26 AC27 AC29 AC34 |
| 请求判重 | 同user+operation+ID同输入重复、同ID异输入、不同ID同文本、跨用户或H5/OpenAPI同ID | 同请求仅一条user/一次准入副作用/同一有效处理结果；异输入冲突、不同ID为不同输入、跨用户隔离；跨入口不另开重复域。 | AC29-a |
| 回执未知与重发区别 | 已入队但SSE meta前断线；读接口找到pending/成功/失败；未提供ID的旧OpenAPI | 新协议能精确关联同请求并保留原deadline；can_resend按服务端实际状态，未知不放行；旧无ID缺口明确，不用文本时间猜测。 | AC29-a |
| 入队原子边界 | 旧代仍在运行，新输入user保存或额度提交失败；不同请求被合法新代承接 | 未确认合法的新提交不作废旧代、不留无主额度；已合法入队的消息与当前有效代/结果正确关联，查询不新建消息。 | AC34-a AC29-a |
| 少量pending进程故障 | 分别1～4条pending，在合法入队后/调度注册前/commit回执丢失后进程退出 | 不依赖满队；按原起点和截止核实，成功不被覆盖、未提交到期失败、未知有限核实/告警；无重置180秒、重复assistant或Step6。 | AC34-a |
| 后台状态与当前代 | 同消息多提交/新代承接、success/failed/unverified/superseded/legacy | 投影与H5同源，未知非失败，旧代不盖新代；不增加后台业务动作 | AC14-a |
| 查询身份/分页 | conversation和agent同号；多提交join；日期/page筛选；状态关联不可读 | 复合身份不冲突，total/排序不放大，错误不伪装空/成功；读接口零状态写 | AC14-b |
| 历史读取原权限 | super_admin/ops_admin/observer与ai_trainer/tech_ops分别直访conversations，含篡改user_id及会话失效 | 严格保留原业务读取角色；用户ID只决定授权域内读取对象，不让更改参数绕过鉴权；GET无写入副作用 | AC13-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] AC29-a与AC34-a覆盖实际H5/OpenAPI入口、只读核实及持久状态；提交仲裁另有真实事务/锁测试，模拟通过不能替代隔离数据库并发证据。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-014、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-015] Step8 新结果与条件清槽

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让 Step8 复用新检索/预算并防止本次旧执行清掉新槽位。

**来源映射**：需求`F11 / F12 / RQ-09 / RQ-20 / RQ-22 / CSTR-13`；负责验收`AC15 / AC22 / AC26 / AC27 / AC34 / CSTR-13`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-012《45 秒加 45 秒检索编排》的已验证输出；STEP-013《完整 Prompt 选择与最终有效性》的已验证输出；STEP-014《主文字与 OpenAPI 唯一终态》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/step8_subchain.py` | `existing` | `REPO_BASELINE` | B27 / execute_step8_subchain:56；提交后收尾:L216起；_fallback_write_agent_message:376；_decay_gate_and_update:397 | 核对既有行为/接入或验证落点 |
| `backend/services/future_handler.py` | `existing` | `REPO_BASELINE` | B28 / scan_and_consume:42；_consume_one:93；_on_consume_success:146；_clear_future_slot:175 | 核对既有行为/接入或验证落点 |
| `backend/services/prompt_builder.py` | `existing` | `REPO_BASELINE` | B03 / count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | 核对既有行为/接入或验证落点 |
| `tests/test_step023_future_handler.py` | `existing` | `REPO_BASELINE` | T11 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_step024_step8_subchain.py` | `existing` | `REPO_BASELINE` | T12 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 本次Future消费身份传递与条件清理接口（按 STEP-002 定稿）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让 Step8 复用新检索/预算并防止本次旧执行清掉新槽位。对应产物与本STEP验收证据。

**业务定义**：PRD S10/§7.3/7.4/9.7：输入仍为自身future_action，整轮从该次子链执行被接收时起算固定180秒，同次重试/恢复不刷新原起点；失败清本次仍匹配槽位。§11.5零误删约束还要求核对成功收尾的兼容衔接，不改变原成功计数/生成策略。 来源：P01 / `F11、F12、RQ-09、RQ-20、RQ-22、CSTR-13`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 接入四路/同源冻结Prompt结果与45+45阶段规则，遵守STEP-013最终校验到交模保护协议；保留原来源输入，不沿旧跨路分排序。
2. 持久承接本次子链接收起点及+180秒deadline，复用提交仲裁保护，检索阶段取阶段+45与原整轮截止较早者；同次恢复/重试不续时，提交未知先核实，截止前已合法成功不被迟到响应改失败，截止后无首次成功。预算/超限失败不落agent_message、不成功计数、不触发Step6；Step6异步提取及索引后台恢复不计入回复业务预算。
3. 携带本次消费身份/代次，保持既有成功/失败各自清理语义，凡本次旧执行进行清理均须当前仍匹配；验证成功期间产生新Future的防误清衔接。仅落实§11.5防误删，不改成功计数/预约策略，不新增自动重试或全部Future重构。

4. 枚举B27全部成功出口，正常保存与 `_fallback_write_agent_message` 均传入同次消费身份、原deadline、有效代/锁所有权和唯一提交保护；兜底helper自开事务不能绕过保护。原人格风险兜底内容和触发条件保持，原兜底没有的Step6/计数/其他副作用不得因共用收尾新增。

5. 将子链返回/Handler处理区分“提交前失败、提交结果未知、已确认成功后收尾”。不要把包住整个协程的timeout或最后bool当真实提交结论：179.x秒已确认保存，后置Step6调度/衰减/回传超过180秒仍为成功；提交后副作用沿原触发边界执行并独立记录结果，不因收尾错误重新生成消息。commit未知先按同一消费身份有限核实，不直接清槽/计失败/重跑；核实后才执行对应已确认状态的处理。

6. 对正常/兜底逐项记录原副作用清单、触发条件和唯一性锚点；成功计数、Step6调度等只在原本存在的成功边界执行一次。所有成功/失败清槽携带消费身份/代次条件；收尾期间产生的新Future必须保留，旧执行不能按user_id无条件清空。仅完善本次提交保护，不扩展全部Future任务平台。

**不在本STEP范围内**：不升级普通 Agent 召回，不扩为全部Future异常治理；本STEP只直接承担Step8条款。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 自身future_action触发、同源四份结果，子链接收后180秒内合法提交 | 输入/来源保持；新链排序/数量/预算正确消费；45+45阶段与剩余整轮取较早截止，截止前已合法成功保持。 | AC15 AC22 AC27 |
| 异常 | 超token预算、子链接收后180秒耗尽、未知commit | 已确认失败无主动消息/成功计数/Step6，仅清本次仍匹配槽位；未知commit先核实，不续时/重复提交，不在截止后首次成功。 | AC26 AC27 AC34 |
| 边界 | 成功/失败执行期间产生新Future、固定180秒前后提交竞争、旧任务迟到/同次重复恢复 | 子链接收起点与原180秒截止不刷新；终态按提交保护收敛，旧执行不误清新槽，成功生成/计数语义保持，失败条件清槽满足AC34；阶段/整轮截止后无新检索或首次迟到成功。 | AC22 AC27 AC34 CSTR-13 |
| 兜底提交边界 | 人格风险触发独立fallback helper，提交前预算耗尽或锁/有效代已丢失 | 兜底也不能首次成功保存agent_message；执行同次仲裁及条件清槽，原兜底内容/触发不改、不补加Step6。 | AC27-a |
| 成功后收尾超时 | 正常与兜底分别在179.x秒确认提交，收尾或响应跨过180秒 | 唯一成功状态与消息保持；不因协程超时/最终返回迟到改判失败，不重新生成/重复成功计数，原副作用边界保持。 | AC27-a AC34-b |
| 未知提交及新Future | commit回执丢失、成功/失败/核实期间新Future写入、同次恢复重复到达 | 按消费身份先核实，不盲目重跑或清槽；所有清理仅匹配本次，保留新Future；只有原允许的成功副作用执行且不重复。 | AC34-b |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] B27全部保存出口均在保护清单，AC27-a/AC34-b覆盖正常与独立兜底；附 `PYTHONPATH=. pytest tests/test_step024_step8_subchain.py tests/test_step023_future_handler.py` 实际输出及必要事务故障证据。

**完成回传**：返回STEP-015、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-016] H5 等待与消息重同步

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让离页/断线返回后的显示按服务端真实消息身份收敛。

**来源映射**：需求`F12 / RQ-22 / RQ-24`；负责验收`AC14 / AC27 / AC29`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-014《主文字与 OpenAPI 唯一终态》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/chat-emotion/api.md` | `existing` | `CONTRACT` | C06 / L1（文字消息与 SSE） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/openapi/api.md` | `existing` | `CONTRACT` | C08 / L1（OpenAPI 入口与信封） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C09 / L1（受控客户端当前界面） | 核对既有行为/接入或验证落点 |
| `frontend/pages/chat.html` | `existing` | `REPO_BASELINE` | U08 / L1121（CHAT_CLIENT_ABORT_MS）；loadTimeline:L1437；visibilitychange:L1797 | 核对既有行为/接入或验证落点 |
| `nginx/nginx.conf` | `existing` | `REPO_BASELINE` | U10 / L1（仓库网关 timeout 配置） | 核对既有行为/接入或验证落点 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | T14 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 消息状态重同步与客户端等待适配；以已定180秒业务预算衔接连接/收口/传输余量，实际各层等待值仍经Q05定稿和部署核验。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让离页/断线返回后的显示按服务端真实消息身份收敛。对应产物与本STEP验收证据。

**业务定义**：PRD S10/§7.4/9.7：整轮业务固定180秒，各层连接等待/收口/传输余量不延业务截止；断线只是连接状态；返回同步pending/成功/失败，未知待同步，不自动send/resend或新建generation。 来源：P01 / `F12、RQ-22、RQ-24`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按已定固定180秒业务预算及002定稿余量，衔接受控H5、OpenAPI服务端与网关等待；明确总时长/空闲时长，不一律设180，不把fetch返回等同完整SSE消费结束。核验实际部署值，任何连接/状态核实余量都不延长业务deadline。
2. H5在首次网络提交前生成并按登录用户保存最小请求标识，send沿 `client_message_id`、resend沿 `client_resend_id`；只保存核实所需ID/已知关联，不另存完整聊天或凭据。meta前断线也能按014的只读GET核实，不按文字时间查找；未知提交不自动send/resend。
3. 为未收口的提交建立与 `loadTimeline` 历史分页完全分离的状态同步：可见回页/网络恢复先查，仍pending或待核实时按冻结配置有限持续查询。每个身份最多一个在途查询，多个恢复事件合并；正常间隔、失败退避上限、单次超时分别消费002定稿的 `text_status_poll_interval_ms`、`text_status_poll_max_interval_ms`、`text_status_poll_backoff_factor`、`text_status_probe_timeout_ms`。
4. 同步窗口按已知服务端原deadline及 `text_status_reconcile_margin_ms` 截止；admission未知使用002给出的首次提交核实截止。禁止每次回页/失败/成功查询重置窗口。到截止仍无法确认时停止自动循环并显示待核实，不当作业务失败、不开放重发；后续显式回页只读一次可以刷新真实状态，但不自动复活已耗尽窗口。
5. 按服务端request/message/当前generation及单调状态版本就地更新已有user/assistant行；旧查询响应和旧SSE不能覆盖新版本或重复追加。查询不受历史游标、loadingTimeline、noMoreTimeline和历史滚动位置阻断；新合法输入导致代际承接时以服务端当前归属更新，不能用旧请求deadline给新代本地判失败。
6. 确认成功/失败/作废且该请求不再被有效新代承接时停止该提交同步；页面隐藏/离开、网络断开、退出登录时停止本地计时和在途等待，不取消服务端任务。重新登录同用户只核实本用户最小标识，异用户不能读/展示原用户状态；失败反馈与重发资格只采用服务端字段。
7. 同步OpenAPI可选身份头与只读核实说明，旧调用方无ID限制明确；第三方本地timeout无法由本项目代改。完成真实浏览器/受控网络回归，静态源码检查只能作为补充，不能证明计时与SSE竞态正确。

**不在本STEP范围内**：不新增推送/停止按钮/自动重发/客户端检索配置，不改星云功能。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 断线期间成功，或返回时仍pending | 已有消息行状态更新、已存回复可见，无重复新增/生成。 | AC14 AC29 |
| 异常 | HTTP/SSE断开、尚未入队或提交确认未知 | 不猜服务端failed/success，不自动send/resend；可核实时按真实状态收敛。 | AC29 |
| 异常-回读 | 返回时已确认服务端失败，含不可重发的安全拒绝 | 更新已有行按既有失败类型展示；只有服务端允许的失败窗口可resend，连接未知不冒充已失败。 | AC14 AC29 |
| 边界 | 两阶段接近各45秒、业务180秒边界前后、切页刷新/旧SSE/新输入作废 | 等待覆盖业务终态及已定收口/传输余量；余量不延长业务180秒截止，同代返回/重连不刷新起点，旧片段不污染新代；具体连接余量据Q05与部署证据核对。 | AC27 AC29 |
| 回页后继续收敛 | 0秒合法入队、30秒断线、80秒回页pending，120秒服务端成功或失败 | 80秒后仍按有限策略读取，下一次合法查询更新同一消息行，终态后停止；无需再次刷新，无重复生成/额度/消息。 | AC29-b |
| 历史分页与竞态 | 历史已noMore、旧游标或历史请求在途；状态查询和旧SSE/不同版本响应乱序 | 同步照常，最多一条在途状态查询/身份；按可信关联和版本更新，旧SSE/旧状态不覆盖最新，不重复assistant。 | AC29-b |
| 有界停止与账号 | 服务端持续不可用/未知至核实截止；反复切页/联网；隐藏/离线/退出/切账号 | 不滑动续时，不无限pending/自动重发；停止本地等待不取消服务端；只读本用户状态，实际终态与未知展示区分。 | AC29-b AC29-a |
| meta前断线 | H5已经送出请求但尚无服务端meta，后台实际已入队或拒绝 | 从首次发送前保存的ID精确核实；不按文本时间推断；服务端确认允许失败窗口之前无resend。 | AC29-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] AC29-b有可复核时序/网络请求及DOM身份记录；新同步不复用历史分页开关，轮询参数与PRD/002协议一致，实际截止不续期。

**完成回传**：返回STEP-016、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-017] 真实诊断与维护管理后端

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：提供无聊天副作用的同源诊断执行、历史和维护操作。

**来源映射**：需求`F10 / F03 / RQ-09 / RQ-15 / RQ-16 / RQ-17 / RQ-17.1 / RQ-21 / CSTR-09`；负责验收`AC12 / AC13 / AC23 / AC24 / AC25 / AC26 / AC30 / AC31 / AC33 / AC35 / CSTR-09`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32功能映射补充**：F08仅承担原历史回填结果的管理侧读取/展示；不新增回填控制。

**ADM32验收映射补充**：AC11 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出；STEP-005《有限索引恢复执行器》的已验证输出；STEP-012《45 秒加 45 秒检索编排》的已验证输出；STEP-013《完整 Prompt 选择与最终有效性》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**验收收口前置**：AC12实际业务对照须STEP-015输出（传递014）；AC11-a回填记录读取须STEP-008输出；本STEP最终DONE须两者均满足。开发前置不变，API/权限/夹具可并行；008不得反向依赖017/018。共享012/013 helper或手工统计JSON不能代替实际业务/回填数据生产证据。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C04 / L1（响应、分页及错误码约定） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C05 / L1（observer 与后端角色边界） | 核对既有行为/接入或验证落点 |
| `backend/routers/chat.py` | `existing` | `REPO_BASELINE` | B22 / _execute_llm_bundle:377；_persist_bundle_success:227；_mark_pack_failed:296；_sse_chat_wait_bundle:648；chat_send:720；chat_resend:758；chat_timeline:826 | 核对既有行为/接入或验证落点 |
| `backend/services/step8_subchain.py` | `existing` | `REPO_BASELINE` | B27 / execute_step8_subchain:56；提交后收尾:L216起；_fallback_write_agent_message:376；_decay_gate_and_update:397 | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/prompt_mgmt.py` | `existing` | `REPO_BASELINE` | B31 / test_prompt:617 | 核对既有行为/接入或验证落点 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B32 / get_current_admin:93；require_role:183 | 核对既有行为/接入或验证落点 |
| `backend/models/realtime_voice.py` | `existing` | `REPO_BASELINE` | B38 / VoiceMemoryJob:349；VoiceMemoryTrace:478 | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| 诊断/历史/维护管理API、执行与快照schema及增量迁移（新增路径按 STEP-002 定稿，不冒充已有mock接口）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `P01 §6.8.8目标API、memory-diagnostics.html、memory-index-maintenance.html及配套JS` | PLANNED | 实际schema/注册经002核验；按§6.8实现，不冒称已有 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：提供无聊天副作用的同源诊断执行、历史和维护操作。对应产物与本STEP验收证据。

**业务定义**：PRD §6.7：指定用户/输入/链路，只读上下文到实际选入即止；执行与历史保存分态；永久历史/快照，源删除不联动删除快照。§12.3/12.5禁止本期服务凭据进入响应、错误、日志或诊断/维护记录，原输入与候选文本快照留存语义保持。 来源：P01 / `F10、F03、RQ-09、RQ-15、RQ-16、RQ-17、RQ-17.1、RQ-21、CSTR-09`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 抽取同源只读上下文/输入装载，禁止复用有副作用send/Step1；真实改写→双召回→路内重排→同次Prompt选入，不回复、不触发Step6；已有调用费用信息可附记，缺失不阻断验收，不要求费用目标。
2. 实现定稿执行身份、同次提交幂等、运行状态查询/异常中断收口、历史/维护分页筛选和逐项结果；执行完成但保存失败单列。
3. 后端仅super_admin/ai_trainer执行/重试/删历史，observer只读、其他不新增；保存原输入/四路文本/候选快照和实际版本结果，永久无自动到期；删除诊断连附属快照，完成维护历史删除保留保护状态/未完成任务，既有审计只摘要。
4. 诊断执行、保存失败及维护重试的响应、错误、日志、有效版本记录和持久诊断/维护记录禁止携带明文服务凭据；不改变合法业务输入/候选快照的永久保存与手删语义，不清洗业务文本或扩为全项目治理。

5. 按P01 §6.8.8实现新memory-diagnostics与memory-index-maintenance目标API并注册路由：执行/列表/详情/终态删除，任务查询/有限重试/历史清理，回填批次摘要与分页items。沿ApiResponse和20默认/1～100页大小，名单、日期、状态、source及ID校验不依赖前端。
6. 诊断request_id在付费调用前持久关联，重复点击/响应丢失可只读找到原execution_id；显式重跑新身份且用当前上下文。源main/openapi/step8按实际适配器组装；用户ID直接由后端核实，不调用trainer无权限的用户目录。执行状态与历史保存状态分列，保存失败不伪造快照；运行中不把删除历史当取消执行。
7. 读取008已持久run/逐项结果，提供阶段/版本/截止点/完整性和分类计数，不从capped全局列表重算；中断/进度不可用/历史已清理明确返回，不启动回填。AC11-a最终证据必须包含008生成记录，不能只用手造统计JSON完成。
8. 实施§6.8.7原权限矩阵及严格的管理动作判定：can_retry/can_delete只反映服务端资格；未完成/被取代/保护引用不得误重试或误删。自有源回执属于007，不以新全局权限替换原CRUD权限。响应/日志/确认文本均不泄漏凭据或执行候选HTML。

**不在本STEP范围内**：不写用户消息/队列/generation/额度/关系/最近互动/情绪/Future/主动计数，不保存全对话/完整Prompt/回复，不以快照回填或事实恢复。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 指定用户/输入与同上下文结果，中途发布新配置；AC12业务对照须先有STEP-015验收证据（传递014） | AC12固定同一上下文/有效配置快照，对照实际主链/OpenAPI及Step8装载/消费路径在回复调用前的最终ID/正文/数量/token，不能只对照mock/helper；诊断自身AC33同次清单/渲染一致，诊断请求回复/Step6为0。可用隔离夹具截获实际业务接线路径，不要求生成回复或访问生产。 | AC12 AC33 |
| 异常 | 越权、重复提交/重试、异常中断、历史保存失败 | 后端拒绝/复用执行，状态可查；源/索引分态；不无限执行中；未完成任务不可历史清理。 | AC13 AC23 AC30 AC35 |
| 异常-预算 | 诊断最终仍超总预算 | 返回预算阻断及同次最终选入；Step5/5.5/6为0，消息/Future及其余聊天业务状态无写入。 | AC26 AC35 |
| 边界 | 源记忆删除后回看/重跑；删历史仍有旧任务在途 | 旧快照仅可查看、无自动到期；重跑用新上下文新记录；删除不删当前记忆/保护状态，无业务副作用。 | AC24 AC25 AC31 AC35 |
| 凭据禁止项 | 仅在服务调用配置放已知测试凭据标记；正常诊断/维护执行、服务或测连错误、历史保存失败及维护重试 | 本期相关响应、错误、日志和诊断/维护持久记录均不含该明文标记；合法配置调用仍可使用，业务输入/候选快照留存语义及未完成任务保护保持，不将测试凭据放业务输入。 | CSTR-09 |
| 管理API与保存故障 | 同诊断request_id回执丢失/重复，保存失败、运行中删记录、维护重试/删保护引用 | 同次一次执行，状态可GET核实；保存与执行分态；删除不取消在途任务、不删源 | AC35-a |
| 详情大清单分页 | 同一次已保存诊断的超单页候选清单；008真实回填批次的固定逐项清单；默认20及page_size=1/100，连续读到末页 | §6.8.8大清单分页返回，单页不超page_size；固定执行/run与筛选的跨页条目集合按002定稿复合身份完整、无重复/漏项，稳定排序与total口径可核对；末页/空页不伪完成，GET不重跑诊断/回填 | AC35-a |
| 回填查询依赖 | 008已生成真实隔离批次/逐项记录；中断和未知总量 | 查询不触发脚本，完整输出阶段/截止点/分类，未解决不完成；DONE须008证据 | AC11-a |
| 分域权限 | 五角色直访任务/回填/诊断、已存在自有源回执 | 新接口按§6.8.7，不能替换旧来源权限或引入用户目录越权 | AC13-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；AC12须015证据（传递014）、AC11-a须008证据，最终DONE须两者均具备，原开发前置不变；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32后端任务及上述新增测试已记录真实输入/接口输出；所负责P01 §8.2的协议/查询/权限分项有证据，未完成的验收依赖不标通过。页面及浏览器结果由018/019收口，不作为017开发前置。

**完成回传**：返回STEP-017、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-018] 诊断与维护后台操作页面

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：让授权用户可完成诊断、查历史、重试和逐项删除反馈。

**来源映射**：需求`F10 / F12 / RQ-09 / RQ-15 / RQ-16 / RQ-17 / RQ-17.1 / RQ-21`；负责验收`AC13 / AC24 / AC25 / AC26 / AC30 / AC35`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32功能映射补充**：F08仅承担原历史回填结果的管理侧读取/展示；不新增回填控制。

**ADM32验收映射补充**：AC11 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-003《请求有效配置与后台独立数量》的已验证输出；STEP-007《Admin 既有 CRUD 与维护反馈》的已验证输出；STEP-017《真实诊断与维护管理后端》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/admin-ui.md` | `existing` | `CONTRACT` | C02 / L1（当前后台页面） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C05 / L1（observer 与后端角色边界） | 核对既有行为/接入或验证落点 |
| `admin/pages/memory-rules.html` | `existing` | `REPO_BASELINE` | U03 / L330（Step6 Prompt、全局列表和批删） | 核对既有行为/接入或验证落点 |
| `admin/pages/knowledge.html` | `existing` | `REPO_BASELINE` | U04 / L247（只读 Key、value 编辑、删除） | 核对既有行为/接入或验证落点 |
| `admin/pages/user-detail.html` | `existing` | `REPO_BASELINE` | U05 / L710–935（历史对话）；L1005–1195（user/private记忆编辑/回执） | 核对既有行为/接入或验证落点 |
| `admin/static/js/admin-api.js` | `existing` | `REPO_BASELINE` | U07 / L1（现有导航与只读控件约定） | 核对既有行为/接入或验证落点 |
| `backend/routers/admin/prompt_mgmt.py` | `existing` | `REPO_BASELINE` | B31 / test_prompt:617 | 核对既有行为/接入或验证落点 |
| 独立诊断页/维护页和菜单入口（路径按 STEP-002 定稿）；既有CRUD只增加维护关联。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `P01 §6.8.8目标API、memory-diagnostics.html、memory-index-maintenance.html及配套JS` | PLANNED | 实际schema/注册经002核验；按§6.8实现，不冒称已有 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：让授权用户可完成诊断、查历史、重试和逐项删除反馈。对应产物与本STEP验收证据。

**业务定义**：PRD §6.7.1：独立页面及导航；执行/保存状态分开，刷新查询身份；观察者仅查看，不因按钮隐藏代替后端权限。 来源：P01 / `F10、F12、RQ-09、RQ-15、RQ-16、RQ-17、RQ-17.1、RQ-21`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 按已定页面/API实现用户/输入/来源诊断和四路输入、来源/分数/名次、准入/降级/淘汰、实际选入/token/耗时版本显示，区分历史与当前。
2. 展示执行中/完成/部分降级/执行失败/预算阻断及保存失败；重复点击不重复付费执行，显式重执行生成新记录；刷新按执行身份查状态。
3. 诊断列表时间/用户/来源/状态筛选分页；维护另按类型/操作/记忆身份及错误/尝试/下次计划/人工原因定位；手动重试/历史删除逐项反馈，删除失败留记录；只读角色无写操作。

4. 创建P01 §6.8指定两个页面及配套JS（均planned），在U07现有AI对话配置分组紧邻召回配置增加入口和高亮；observer只能GET查看。加载/失败/空态分开；用户ID手填且权限由017判定，不为trainer打开用户管理。
5. 诊断页按输入、冻结版本、四路候选、实际选入/Token、执行/保存状态五块实现；原分/重排分/故障排序分开。执行中冻结输入，重复点击与回页只查原身份；显式重新执行新身份；历史及详情内大清单分页默认20/最大100、稳定排序，不能以一次返回全部历史规避page_size。保存失败不显示已保存，历史文本仅查看，删除终态历史按原快照规则反馈。
6. 维护页默认索引任务、另设回填批次Tab；列表/详情/按钮矩阵取§6.8.6。接008→017真实批次数据，提供run/任务定位，未知总量不画百分比，失败/未追平不能显示完成；不加网页启动/暂停/全量重试按钮。历史删除不取消任务，缺失关联给历史已清理占位。
7. 验证007已有页面跳转按角色及task_id定位：ops只见其原页面摘要，无越权跳转；新页返回后可重新查询源当前状态，不把旧操作代次套到新行。动态按钮data-write-action、GET筛选/只读刷新、安全文本渲染和错误保留统一覆盖；按钮禁用不是服务端权限或幂等证明。

**不在本STEP范围内**：不新增自动定时全量诊断/回复生成/自动过期，不赋予ops_admin/tech_ops新诊断权限。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 授权角色执行/筛选/回看/重试/删历史 | 四路与最终选入可查；删除附属快照，当前记忆不受影响。 | AC24 AC25 AC30 AC35 |
| 异常 | 执行完成保存失败、刷新/重复点击、删除失败/越权 | 明确保存失败和真实阶段；不重跑；保留失败记录，后端权限不可绕过。 | AC13 AC35 |
| 异常-预算 | 真实诊断最终超总预算 | 页面显示预算阻断及实际最终选入/原因，不显示生成成功；回复/Step6零调用且聊天消息/Future未改。 | AC26 AC35 |
| 边界 | observer直访写操作、处理中维护删除、源记忆已删除 | observer仅读；未完成和保护状态不可误删；历史快照仍供查看。 | AC13 AC24 AC25 AC35 |
| 页面路径与执行状态 | 从新菜单/CRUD结果进入，运行刷新/重复提交/重跑/保存失败/删历史 | 定位同任务；原执行与保存双状态，GET不调用模型；终态历史按规则删除 | AC35-a |
| 详情大清单跨页 | 同一已保存诊断/固定回填run含超单页候选或逐项清单；默认20及页大小1/100，前后翻页/末页/切筛选/刷新失败 | 页面与017分页响应同一身份/筛选，页内数量受限且按002定稿复合条目身份的逐页集合完整无重复/漏项，末页/空页与失败分开；旧响应不覆盖新筛选，翻页/只读刷新不新建执行或启动回填 | AC35-a |
| 回填页面 | 008→017的批次记录，未知总量/未解决/完成截止点/中断 | 展示可信分类/缺口和关联任务，不画假100%，没有回填启动按钮 | AC11-a |
| 权限与文本 | observer动态控件/GET筛选，ops跳转，含HTML候选及错误 | 无越权入口，GET仍可用，全文安全显示不执行代码，存储语义不变 | AC13-a AC13-b |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-018、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-019] 范围外消费者及三端兼容回归

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：证明共享改动没有升级或破坏明确保留的消费者。

**来源映射**：需求`F12 / CSTR-01 / CSTR-11`；负责验收`AC13 / AC14 / AC16 / AC17 / AC18 / AC33`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**ADM32验收映射补充**：AC05 / AC11 / AC12 / AC30 / AC35 仅承担§5.2分配的后台子条款，与原来源映射共同生效。

**前置依赖**：STEP-006《文字及语音写入接入索引维护》的已验证输出；STEP-007《Admin 既有 CRUD 与维护反馈》的已验证输出；STEP-014《主文字与 OpenAPI 唯一终态》的已验证输出；STEP-015《Step8 新结果与条件清槽》的已验证输出；STEP-016《H5 等待与消息重同步》的已验证输出；STEP-018《诊断与维护后台操作页面》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/memory-knowledge/admin-ui.md` | `existing` | `CONTRACT` | C02 / L1（当前后台页面） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C05 / L1（observer 与后端角色边界） | 核对既有行为/接入或验证落点 |
| `backend/services/prompt_builder.py` | `existing` | `REPO_BASELINE` | B03 / count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | 核对既有行为/接入或验证落点 |
| `backend/routers/memory.py` | `existing` | `REPO_BASELINE` | B33 / L19（只读 list 路由） | 核对既有行为/接入或验证落点 |
| `backend/services/agent_service.py` | `existing` | `REPO_BASELINE` | B34 / _search_memories_for_agent:688；generate_and_save_message:276 | 核对既有行为/接入或验证落点 |
| `backend/services/realtime_voice_recall_service.py` | `existing` | `REPO_BASELINE` | B35 / L1（既有语音实时召回） | 核对既有行为/接入或验证落点 |
| `backend/services/realtime_voice_context_source_service.py` | `existing` | `REPO_BASELINE` | B36 / L1（既有 user/private 会前读取） | 核对既有行为/接入或验证落点 |
| `backend/services/realtime_voice_context_pack_service.py` | `existing` | `REPO_BASELINE` | B37 / L1（既有会前过滤与打包） | 核对既有行为/接入或验证落点 |
| `frontend/static/js/memory-nebula.js` | `existing` | `REPO_BASELINE` | U09 / L1（现有列表分页、节点与空态） | 核对既有行为/接入或验证落点 |
| `tests/test_prompt_builder.py` | `existing` | `REPO_BASELINE` | T03 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | T14 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_realtime_voice_step028_memory.py` | `existing` | `REPO_BASELINE` | T15 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_realtime_voice_step030_recall.py` | `existing` | `REPO_BASELINE` | T16 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| `tests/test_realtime_voice_step026_context_pack.py` | `existing` | `REPO_BASELINE` | T17 / L1（现有测试模块；新增预期须以当前 v3.2 为准） | 核对既有行为/接入或验证落点 |
| 针对有效需求的兼容证据；新断言按PRD和旧消费者有效契约，不照抄旧新链Top3预期。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |
| `backend/routers/admin/prompt_mgmt.py` | `existing` | `REPO_BASELINE` | B31 / test_prompt:617 | 经旧API验证当前/草稿/系统覆盖与字符串消费 |
| `backend/services/realtime_voice_memory_service.py` | `existing` | `REPO_BASELINE` | B08 / _write_atom:727；_finish:779 | AC18-b使用实际语音writer，不手写索引代替 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / execute_multi_vector_retrieval:270及新接线 | AC18-b实际新文字召回链 |
| `tests/test_memory_v31_prompt_test_compat.py` | `planned` | `PLANNED` | 本步拟新增API回归测试文件，执行前核对现有同类测试可复用性 | AC33-a当前/草稿/覆盖、鉴权与调用次数 |

**ADM32补充落点**（不替代上表）：

| 路径/协议 | 事实标签 | 用途 |
|---|---|---|
| `backend/routers/admin/users.py` | EXISTING / A32-01 | get_user_conversations及原历史读取权限 |
| `admin/pages/user-detail.html` | EXISTING / A32-02 | 历史对话状态/分页/查询，不限原记忆Tab |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：证明共享改动没有升级或破坏明确保留的消费者。对应产物与本STEP验收证据。

**业务定义**：PRD §4.2/6.4/12.8：F13/F14和RQ-03/04算法升级延期；本期含语音写入索引、S14全入口存储/score适配及既有行为回归。 来源：P01 / `F12、CSTR-01、CSTR-11`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 对H5星云只读列表字段/doc_id/节点/预览/空态、聊天信封/SSE/失败重发和后台各既有角色权限做可观察回归。
2. 核对Step6六块配置/11字段、语音memory_items/输入/trace/协议及情绪confidence/已有安全链保持；不补造updated_at。
3. 按S14完成全部现用读写DotProduct适配与回归，含普通Agent、语音实时及会前直接HTTP、缓存命中、CRUD/星云与后台测连：query均L2，score越大越相似，查明threshold/范围/排序使用点，无旧库硬编码/fallback。保持各入口自身TopK、Prompt预算、时限/缓存/迟到及时间过滤；模型/维度不变，真实分数与模拟分开记证。

4. 在原后端测试运行环境经 `POST /api/admin/prompt/test` 执行当前配置、草稿配置及合法 `system_prompt_override`，模型用桩捕获参数；确认传入字符串、文本长度及原响应字段语义正确，旧mock不要求真实doc_id/代次。分别以原允许/拒绝角色验证权限未改变；不新开放mock模式。局部构建单测来自013，API级结果归AC33-a。

5. 以调用计数/写入探针验证旧Prompt Test仅保留原回复模型调用，不因新构建器新增真实改写、召回、索引写、聊天状态或Step6；真实诊断则实际执行检索但回复模型与业务写仍为零。普通Agent旧helper及其它既有消费者对照原基线，不用全局放宽候选校验修旧测试。

6. 执行AC18-b：经B08实际语音writer写入一条合法user/private记忆，记录doc_id、user_id、当前value/来源和维护任务；等待已确认索引就绪或按005有限恢复完成，再用同用户经新文字链查询只在该value中的辨识词。断言BM25来源候选为同一ID/当前value，非Key文本、非过期版本；用另一用户同样查询不能获得此私有候选。只有向量命中或索引仍待修复不得判本用例通过。

7. 将AC18-a的006局部证据和AC18-b的新文字集成证据分列；保持原语音读链的时限、缓存、过滤、迟到投递及会前时间口径。若修改同Key再次查询，仍按当前正文与既定覆盖规则验证，不新增历史版本能力。

8. 在U05历史对话区域修改convDeliveryLabel/buildConversationsHtml/fetchConversationsPage/searchConversations及相关装载：消费014的新投影、保留legacy区分和复合身份；仍用既有手动查询，不新增轮询。查询序号防旧用户/旧筛选/旧分页响应覆盖；失败与空态分开，同筛选旧数据标过期，切用户不留上一用户内容。
9. 经实际admin GET与H5读状态入口对照同一条消息、同一修订，完成AC14-a/AC14-b；包括generation承接、未知commit、已成功但连接失败、旧记录、多提交join以及无副作用断言。不是只单测字符串标签。
10. 执行AC13-a五角色×各域矩阵，含user/private原权限、历史对话无trainer、原vector-db-config有trainer、第三方仅tech/super写、新诊断无ops/tech；逐条验证直访/篡改ID、自有回执与菜单一致。诊断能手填用户ID，不依赖权限更大的用户目录。
11. 用真实页面和隔离接口记录验证AC05-a/AC12-b/AC17-a、AC30-b/AC30-c、AC11-a、AC35-a、AC13-b：字段到响应、源与索引部分成功、操作未知核实、批次计数、跨页与删除引用保护。对本次配置发布响应未知且他人随后发布更后版本，核对002/003的精确提交关联；当前值/版本不能倒推本次结果，证据不足保持待核实且不自动再PUT。对§6.8.8诊断/回填详情大清单，逐页记录ID集合、page_size/total/排序与浏览器结果，核对完整、无重复/漏项及GET无执行副作用。静态HTML/JS检查不能替代浏览器点击/刷新/乱序输出证据；沿现有工具或记录手工步骤，不凭空宣布已有浏览器自动化套件。
12. 对Step1.5/Step3/Step8只读预览完成AC33-b，与AC33-a旧Prompt Test分开；默认Token不冒充有效配置，预览零模型/零用户状态写。以上只补本期后台联动，不升级普通Agent、语音读链或H5星云。

**不在本STEP范围内**：不完成F13/F14读取算法升级，不关闭内容质量/覆盖历史/全部异步可靠性债务，不新建H5记忆CRUD。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | H5星云/预览与发送重发、既有Admin各角色 | 字段/身份/空态和原权限兼容；新功能权限按既定矩阵。 | AC13 AC14 |
| 异常 | Agent空结果/长记忆；语音超时/过期/删除/迟到；新库自命中/负分/零向量 | DotProduct自命中接近1、负分方向正确，零向量拒绝；各入口筛选含浮点边界与归一化实测一致；原选择/截断、时限/投递保持，不套文字45秒或补时间。 | AC17 AC18 AC33 |
| 边界 | 保存提取配置、同Key覆盖和情绪展示；语音写入后文字检索 | 提取协议/情绪字段保持；AC18-b须由实际语音writer经已就绪索引进入新文字BM25链，核对同ID/当前value与用户隔离；不宣称语音读取升级。 | AC16 AC18 |
| 旧Prompt测试接口 | 当前配置/草稿/系统覆盖，合法与禁止角色，旧mock只有content/score | 原信封/覆盖/权限保持；模型收到字符串，长度等于文本长度；mock不查真实索引，不新增业务写或Step6。 | AC33-a |
| 两类工具职责 | 旧Prompt测试与新真实诊断分别运行，计数各模型/索引/业务写调用 | 旧测试保留原回复模型但不新增真实召回；新诊断执行真实检索但零回复/零Step6，不能混用成功证据。 | AC33-a AC13 |
| 语音写→新文字BM25 | 经实际语音writer写入/同Key更新，确认索引就绪后同用户文字查询；另一用户同查询 | 同一doc_id、当前value、正确voice来源和BM25命中可查，无旧词旧版或跨用户候选；纯向量命中不代替此验收。 | AC18-b |
| 跨入口依赖未完成 | 006源写已成功，但维护任务未完成或新文字查询未接线 | 保留局部AC18-a证据，AC18-b阻断/未通过；不把006通过冒充全部语音到文字链通过。 | AC18-b |
| 历史对话整链 | 实际admin API/H5同状态修订+U05查询/翻页/切用户/失败，generation承接与legacy | AC14-a/b全部断言；浏览器无自动任务重启/轮询，不跨用户留正文、不重复气泡 | AC14-a AC14-b |
| 后台权限全矩阵 | 五角色×本期配置/CRUD/历史/诊断/维护/回填/预览域，直接请求 | 原权限保留，新权限严格；自有回执有来源边界，trainer不借诊断访问用户目录 | AC13-a |
| 配置与操作闭环 | 真实页面/隔离API，两处TopK、策略保存/测连、源索引状态/批删回执；S15清理后空历史及保留资料/日记/朋友圈 | 页/API/实际值一致，失败/未知不伪成功；新库空数据行为正确，非向量保留功能与亲密度数值可见且不变；实际022仍另核验 | AC05-a AC12-b AC17-a AC30-b AC30-c |
| 配置发布未知跨页回归 | 本次PUT响应未知后，他人发布不同值/相同值的更后版本；关联证据有/无，回页只读核实 | 浏览器/API凭本次提交关联的发布版本或审计证据收口；当前值/版本不足时保持待核实，不自动PUT，不把他人版本算成本次成功/失败 | AC12-b |
| 回填与诊断界面 | 008真实记录→017→018，执行/保存故障、历史清理，HTML/特殊字符 | 可信进度、按规则清理与原状态保持；GET零业务副作用且安全纯文本 | AC11-a AC35-a AC13-b |
| 详情大清单端到端 | 真实隔离已保存诊断与008固定回填的超单页清单，经017 API→018浏览器；默认20/页大小1与100、逐页至末页、刷新/切筛选/读取失败 | API和页面的同执行/run/筛选跨页条目集合按002定稿复合身份与生产清单一致，无重复/漏项，单页不超page_size；total/稳定排序/末页可核对，空与失败分开；只读翻页/刷新零模型执行/零回填启动 | AC35-a |
| 三个只读预览 | Step1.5/Step3/Step8 GET及页面，旧Prompt Test和Agent对照 | 原字段/权限、默认来源标识与新规则相符；预览零模型，Test保留原用途 | AC33-b |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] AC33-a接口级、AC18-b跨入口及原语音/Agent消费者回归分别有输出；未发生读取算法升级。新增测试文件标planned直至实际创建，其执行命令与结果随交付记录。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：返回STEP-019、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-020] 正式评测前冻结

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：形成不可事后改口径的 GATE-C 评测基线。

**来源映射**：需求`RQ-18 / F15 / CSTR-04`；负责验收`AC19 / CSTR-04`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-002《行为、接口与参数定稿》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/query_rewrite_service.py` | `existing` | `REPO_BASELINE` | B01 / QueryRewriteOutput:28；_parse_query_rewrite_output:271；_build_step1_5_prompt:137；execute_query_rewrite:307 | 核对既有行为/接入或验证落点 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | 核对既有行为/接入或验证落点 |
| `backend/services/prompt_builder.py` | `existing` | `REPO_BASELINE` | B03 / count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | 核对既有行为/接入或验证落点 |
| 评测集/标注/指标与参数冻结产物（位置按已核实项目约定确定）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：形成不可事后改口径的 GATE-C 评测基线。对应产物与本STEP验收证据。

**业务定义**：PRD §11.5及§1.4最新取舍：冻结同集新旧对照、标注与质量判断口径，重点文字漏召回、无关注入/混淆、语义改写/指代及多个限定条件的稍复杂记忆/查询；同集总体效果有据改善（不设幅度数字阈值），关键场景不退步；候选与最终选入质量、证据利用分别观察，正常与降级分报。费用不作为门槛，日常延迟和提升幅度仅记录真实观察，暂不设数字阈值。 来源：P01 / `RQ-18、F15、CSTR-04`与`USER_DECISION`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 冻结查询/现存语料/相关文档/无答案标注、关键场景清单与实际样本数，明确计分单位/分母/汇总、逐样本相关性/最终选入质量和关键不退步判断口径；包含文字漏召回、混淆、语义改写/指代及多个限定条件的稍复杂查询，不能合成缺失事实或为评测改内容结构。
2. 记录实际测试负载、模型/Prompt/编码器/索引/配置组合及日常分位延迟/提升幅度的观察方式；冻结旧词组/新词组/完整Question对照。费用不纳入本期评测门槛，不要求冻结费用目标；日常延迟与提升幅度暂无数字阈值，不因缺这些目标阻断本步。
3. 准备正常、改写降级、单通道失败、rerank故障独立评测口径及PRD硬约束零违规断言；探索性试验和正式验收分开记录。固定180秒整轮业务上界、45+45、一次失败调用重试及Q05连接/收口/有限恢复参数仍需定稿与验证；不把180秒当日常耗时目标，也不把观察项改为数字达标门槛。

**不在本STEP范围内**：不虚构样本量/缺失事实、费用目标或日常延迟/提升幅度数字阈值，不宣称未测收益，不事后改变关键场景、不调整记忆内容结构；回答证据利用评测不进入诊断页回复能力。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 冻结前有同集语料/查询、可复核相关/无答案标注、关键场景及质量口径 | GATE-C版本与质量判断完整可复现；费用目标和日常延迟/提升幅度数字阈值不是必填或通过条件。 | AC19 CSTR-04 |
| 异常 | 缺同集/无答案标注/质量口径/关键场景或混用降级结果 | 列真实证据缺口，不进行正式质量判定；不得把缺费用或日常延迟/提升幅度数字目标列为阻断。 | CSTR-04 |
| 边界 | 比较旧词组/新BM25词组/Question及非关键退步；暂无数字提升目标 | 比较组合与逐项质量/退步解释要求预先固定，不重选关键场景；记录观察到的变化，无百分比承诺。 | AC19 |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-020、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-021] 同集真实质量与性能验收

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：用冻结标准判断召回改善目标是否真实达成。

**来源映射**：需求`RQ-18 / F04 / F05 / F06 / F07 / F08 / F15`；负责验收`AC19 / AC20`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-008《历史现存正文完整回填》的已验证输出；STEP-012《45 秒加 45 秒检索编排》的已验证输出；STEP-013《完整 Prompt 选择与最终有效性》的已验证输出；STEP-019《范围外消费者及三端兼容回归》的已验证输出；STEP-020《正式评测前冻结》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `backend/services/query_rewrite_service.py` | `existing` | `REPO_BASELINE` | B01 / QueryRewriteOutput:28；_parse_query_rewrite_output:271；_build_step1_5_prompt:137；execute_query_rewrite:307 | 核对既有行为/接入或验证落点 |
| `backend/services/multi_vector_retrieval_service.py` | `existing` | `REPO_BASELINE` | B02 / MultiVectorRetrievalResult:40；merge_results:135；_retrieve_route:150；execute_multi_vector_retrieval:270 | 核对既有行为/接入或验证落点 |
| `backend/services/prompt_builder.py` | `existing` | `REPO_BASELINE` | B03 / count_tokens:276；build_chat_prompt:412；build_step8_prompt:560；build_active_message_prompt:494；_merge_character_knowledge_items:702；_trim_to_budget:1024 | 核对既有行为/接入或验证落点 |
| 真实同集质量、日常延迟/提升幅度观察、硬约束与索引完整性报告（按已核实项目约定确定，不用模拟充运行证据；不要求费用目标）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：用冻结标准判断召回改善目标是否真实达成。对应产物与本STEP验收证据。

**业务定义**：PRD §11.5及§1.4最新取舍：功能通过不能代替真实最终选入质量；重点文字漏召回、混淆与稍复杂记忆/查询；同集总体效果有据改善（不设幅度数字阈值），关键不退步、少量非关键退步逐项说明。费用不设门槛，日常延迟/提升幅度仅记录，无数字阈值或百分比承诺；两个45秒及S10整轮180秒仍是硬故障上界。AC20/§6.5的真实四路Step1.5输出语义直接在本STEP按020冻结的质量口径验收，009只完成模板/解析协议子条款，不调整内容结构或升级语音读取。 来源：P01 / `RQ-18、F04、F05、F06、F07、F08、F15`与`USER_DECISION`；原具体默认值不自动沿用为新链参数。普通实现细节为`PLANNED`，按已核实项目约定与前置定稿确定。

**开发任务**：

1. 在授权的评测环境同集运行旧链/新链与三种查询对照，真实模型/检索调用记录代码、Prompt、模型、编码器/索引、配置和评测集版本；直接执行AC20真实四路Step1.5样本，按§6.5及020冻结的Q05口径判定核心实体有据、去套话、指代/模糊时间/否定语义及既有字段协议，不能仅以AC19总体改善替代。
2. 分路/关键场景/无答案、正常和各降级链记录候选覆盖、最终覆盖/无关注入与混淆、证据使用及日常分位时延/积压/请求数和观察到的提升幅度；逐样本保留真实输出及相关性判断，候选命中不能代替最终选入质量。费用不作为必需评测项或通过条件。
3. 对照冻结质量口径、关键不退步及硬约束、全量身份/当前正文和增量对账输出通过/未通过；非关键退步逐项解释，未运行/模拟/部署差异明确标注。不得因缺费用目标、日常延迟或提升幅度数字阈值阻断本步，也不得用记录代替硬条件验证。

**不在本STEP范围内**：不改冻结质量口径来过验收，不以候选有结果/回答提及一段内容代替最终选入质量，不承诺百分比提升、不调整内容结构、不升级语音读取，不自动切换生产。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | STEP-020冻结且各前置功能已验证 | 同集最终选入质量及总体效果改善（不设幅度数字阈值）、关键不退步、硬时限/完整性均有真实证据；日常延迟/提升幅度记录观察，无费用或数字提升目标门槛。 | AC19 |
| 异常 | 功能过但关键质量退步/硬约束违规、外部持续故障或缺真实质量证据 | 只报告已证实部分，质量验收或切换保持阻断；缺费用目标或日常延迟/提升幅度数字阈值不能作为失败理由。 | AC19 |
| 真实模型语义 | 使用含专有名词、套话、指代、模糊年份与否定条件的冻结样本，实际运行四路Step1.5 | Keywords为本路BM25词组，按§6.5/冻结Q05保留有据核心实体、去套话、不补造年份城市；Question保持本路完整语义；字段名/字符串类型兼容，不输出权重或稀疏向量。逐对象给真实输出/判定证据，009局部协议通过不替代本项。 | AC20 |
| 边界 | 关键与非关键样本、正常与降级差异 | 关键不被总体平均掩盖，非关键退步逐项说明，降级独立报告。 | AC19 |
| 文字关键场景 | 冻结的现存记忆/查询覆盖漏召回、无关注入/混淆、语义改写/指代及多个限定条件；保留相关/无答案标注 | 逐样本核对真实最终选入ID/当前正文/相关性和混淆，不补缺失事实、不改内容结构；关键不退步按冻结口径判定，观察改善据实报告，无百分比承诺。 | AC19 |

**完成标志**：

- [ ] AC19及AC20真实模型语义子条款分别有冻结版本、实际输出及质量判定证据，同集总体效果有据改善（不设幅度数字阈值），关键场景不退步；硬时限沿S10固定180秒、45+45及已定连接余量口径验证，日常延迟/提升幅度只记录，无费用或数字提升目标门槛，未改冻结质量口径或其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

**完成回传**：返回STEP-021、完成/阻断状态、产物/变更文件、验证命令或环境及结果、来源变化、下一依赖已满足的STEP；不得自动启动下一STEP。

### [STEP-022] 切换证据、回退演练与交接

**阶段状态**：文档修订并静态核对；实施状态仍为 `NOT_STARTED`。**目标**：形成满足 GATE-D 的可审阅发布准备交付。

**来源映射**：需求`RQ-18 / F09 / F12 / CSTR-05 / CSTR-10 / CSTR-12`；负责验收`AC17 / CSTR-05`；均为`PRD` P01，需求准确摘要/短引见以下业务定义，验收子条款见本STEP测试表及§5。

**前置依赖**：STEP-008《历史现存正文完整回填》的已验证输出；STEP-018《诊断与维护后台操作页面》的已验证输出；STEP-019《范围外消费者及三端兼容回归》的已验证输出；STEP-021《同集真实质量与性能验收》的已验证输出。核对其产物、参数/版本与完成证据；任一未满足停止当前STEP，不用编号顺序推定已完成。

**参考路径与符号**：

| 路径/符号 | 状态 | 来源证据 | source_id / locator | 用途 |
|---|---|---|---|---|
| `PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md` | `existing` | `PRD` | P01 / L1（§6–§9、§11–§13） | 需求与验收依据 |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | C01 / L1（当前接口与最后写入来源） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/memory-knowledge/admin-ui.md` | `existing` | `CONTRACT` | C02 / L1（当前后台页面） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/memory-knowledge/data.md` | `existing` | `CONTRACT` | C03 / L1（旧 memory 表保留、主写入已下线） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C04 / L1（响应、分页及错误码约定） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/chat-emotion/api.md` | `existing` | `CONTRACT` | C06 / L1（文字消息与 SSE） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/chat-emotion/data.md` | `existing` | `CONTRACT` | C07 / L1（消息状态及代际） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/openapi/api.md` | `existing` | `CONTRACT` | C08 / L1（OpenAPI 入口与信封） | 核对既有行为/接入或验证落点 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C09 / L1（受控客户端当前界面） | 核对既有行为/接入或验证落点 |
| `backend/services/admin_config_service.py` | `existing` | `REPO_BASELINE` | B16 / get_active_config:31；publish_config:181 | 核对既有行为/接入或验证落点 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B39 / L9（现有迁移加载方式） | 核对既有行为/接入或验证落点 |
| `nginx/nginx.conf` | `existing` | `REPO_BASELINE` | U10 / L1（仓库网关 timeout 配置） | 核对既有行为/接入或验证落点 |
| `README.md` | `existing` | `REPO_BASELINE` | T00 / L9（PYTHONPATH=. pytest tests/） | 核对既有行为/接入或验证落点 |
| 发布/新库恢复准备与现有记录交接（按实际设计确定，不新增里程碑执行计划）。 | `planned` | `PLANNED` | 不适用 | 本STEP拟交付，非已有能力 |

**输入**：P01所列本STEP需求、表内现有基线及前置STEP输出。**输出**：形成满足 GATE-D 的可审阅发布准备交付。对应产物与本STEP验收证据。

**业务定义**：PRD §9.3.1/12.4、S15及里程碑§2.1：全AC/真实同集质量/硬约束、清理及保留数据演练/新数据恢复齐全才具备准备条件；正式上线或重新开放测试前实际清理并核验后开放。只维护新库，不回切旧版/导入旧事实；准备、实际清理、开放和旧库退役分别记§3，不能以准备DONE冒充执行完成。

**开发任务**：

1. 汇总各STEP的AC子条款证据/环境/版本，核对全部35AC无未覆盖子条款，包括AC19真实同集文字最终选入质量/关键不退步、AC20真实模型语义、AC27/S10固定180秒与同代不续时、180秒前后终态/未知提交及等待余量证据；日常延迟/提升幅度仅交观察记录，不要求费用目标或数字阈值。准备执行器启停/并发/恢复、状态迁移、实际配置校验和已核实回填入口。
2. 按008工具隔离演练全实例停写、一次性清理中断/续跑、空数据/无回写/保留身份值不变、完成标记提交未知及完成后开放前崩溃、开放后的新数据恢复；必要材料不被20版本清理误删。落实具体环境/清单/窗口，正式上线或重新开放测试前执行实际清理、冒烟清样本、开放与旧库退役并逐项记证；失败未知保持维护态，绝不普通重启清空、改env回旧库或恢复旧内容。已有明确授权不重复确认，新增实质对象另处理。
3. 仅按实际已完成行为同步当前契约/必要导航manifest/测试与现有进度，给出剩余问题/授权范围/恢复位置；交付可审阅命令与演练证据后才申请实际生产动作授权。

4. 把§5.1十个子用例逐项纳入切换证据：合法预算保存、请求身份/只读核实、H5有限同步、少量pending崩溃收口、Step8兜底与提交后收尾、旧Prompt Test、语音写→文字BM25及真实写入包装层。根AC通过不能掩盖子用例未测；对语音AC18-a/18-b按006/019责任验收，不重复误计完成数。

5. 将P01 §6.8逐页/API/权限/子验收纳入发布证据：003/007/014/017/018/019实际结果及008新库维护与一次性清理演练齐备。新后台不能先于响应状态/权限接口启用；全部现用入口的新库目标与参数来源须验证，不能以新页可打开当上线通过，不维护旧版本分支。
6. 实施完成后同步当前memory-knowledge/admin-ui与api、admin-security-accounts的conversations响应、observability-third-party的新实际服务能力、persona-prompt预览、共享权限必要条目，以及INDEX/manifest/code-surface覆盖；只记录确实实现的字段/路径，不把本次PLANNED规格提前当运行契约。文档快照/原件保留，不执行未经授权的生产回填或部署。

**不在本STEP范围内**：本次文档修复阶段不改current运行契约；文档阅读入口/manifest已随v3.2同步。实际清理/回填/灰度/发布按S15及相应授权落实具体环境/窗口，不虚构开关名/比例/窗口或未经核验生产命令。

**测试与验收**：按定稿环境/版本/计数器运行；模拟与真实证据分别记录。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
|---|---|---|---|
| 正常 | 功能/质量/硬约束、清理/保留与新数据恢复演练齐全 | 准备证据齐；正式上线或重新开放测试前实际清理/保留核验与冒烟清样本后开放，全实例仅新库，旧库退役另记 | CSTR-05 AC17 |
| 异常 | 门槛未测、源变更遗漏/目标错配/未决操作、恢复材料丢失 | 不开放新写或删除旧库；定位恢复点；不把缺费用/日常延迟/幅度目标列为阻断。 | CSTR-05 |
| 边界 | 开放新写后故障、超过20版本清理、旧writer/任务复活或重复清理 | 仅新数据恢复/前向修复；材料可用；旧写入阻断开放；已完成清理不会因普通重启再次删除新数据，旧内容不恢复 | AC17 |
| 后台发布闭合 | 逐页/API/字段/状态/权限/验收以及回填生产查询记录 | §6.8和12子用例均有实际证据，缺后端状态/权限/清理保留/新数据恢复证据不得单独上线页面 | CSTR-05 |
| 配置切换与退役演练 | 精确旧新库与SQL/缓存清单、共享表保留字段、全入口env/后台配置、重复执行 | 新12项不被旧值覆盖；实际向量/旧正文/画像/预约清空、保留身份及值不变、旧任务无回写、CRUD/隔离/新数据恢复通过；旧库退役及审计记录齐备。演练不替代实际启用前证据 | AC17-a |

**完成标志**：

- [ ] 当前STEP负责的全部验收子条款通过且有输入/预期/输出证据；未改其他STEP范围。
- [ ] 新发现路径/符号/参数/契约来源已按existing/planned/unverified回传；关键未核实项不得宣称可执行事实。
- [ ] §3进度及必要实际契约记录已回传；不因模拟通过推定部署或真实模型通过。

- [ ] 35个根AC及§5.1十个子用例均有对应实施证据；本次文档自检不能作为GATE-D运行证据。

- [ ] 本步ADM32任务及上述新增测试已记录真实输入/接口输出/页面结果；所负责P01 §8.2子项均有证据，未完成的依赖不标通过。

**完成回传**：分别报告022准备、实际清理、业务开放、旧库退役与实际环境/证据，保存§3；未发生写“未执行”，不因准备DONE宣称S15完成。给出范围/来源/阻断/恢复点，不新增STEP。

## 7. 本次文档自检与交付状态

本节保留原v3.2后台闭环稿的文档静态核对登记，不是本轮新增GitHub或实现/运行验收；原RV31修正沿§7.1保留，仍有效门槛沿§7.2保留，本轮取舍继承及局部核对见§7.4。

- [x] 原后台稿登记两份v3.1完整输入及摘要已核对，原件保留；本轮未重读或重算历史文件，当前P01指向配套v3.2 PRD并登记实际摘要。
- [x] 原后台稿登记main读取与固定提交，后台事实按A32定位；本轮核对本地HEAD同提交及关键源码，不把原读取动作或旧测试当本轮GitHub/RUNTIME证据。
- [x] 原13章/15F/26RQ/35根AC/13CSTR/22STEP保留；10个旧子用例＋12个后台子用例均对应正文、责任STEP和测试。
- [x] 开发依赖保持；017新增008验收收口门且原015验收门保留，依赖图无环，008不依赖新管理页面。
- [x] 历史对话、两处旧TopK、多入口配置、源写回执/三页反馈、回填持久记录承接、两新页面、分域权限与只读预览均有明确落点。
- [x] 180秒/45+45/有限重试/同代不续时/nickname固定预算配置值50及正文不裁剪、完整计总量/语音既有20秒包装层范围保持，不新增后台重发、停止、强制完成或全量回填控制。
- [x] 原13.5及RV31历史记录不改写为本轮运行；新页面/API/字段/测试文件显式PLANNED。配套文件名/摘要、根及子验收映射、章节引用和Markdown表格/围栏完成静态检查。

### 7.0 ADM32本轮闭合对账

| 追踪 | PRD | 实施/验收落点 | 当前状态 |
|---|---|---|---|
| ADM32-01 历史对话 | §6.8.2、AC14-a/b | 002协议、014权威投影、019页面和跨端 | 文档已补，未实施 |
| ADM32-02 配置与旧入口 | §6.8.3、AC05-a/12-b/17-a | 002来源表、003表单/API、019全入口适配回归、022切换/恢复/退役 | 文档已补，未实施 |
| ADM32-03 源写回执/CRUD | §6.8.4、AC30-b/c | 004持久基础、007实际API/页面、019集成 | 文档已补，未实施 |
| ADM32-04 回填到后台 | §6.8.6、AC11-a | 008记录→017 API→018页面→019集成 | 文档已补；017 DONE需008证据 |
| ADM32-05 两页诊断/维护 | §6.8.5/6.8.8、AC35-a | 017/018，继承原AC24/25/31留存/保护 | 文档已补，未实施 |
| ADM32-06 分域权限/安全显示 | §6.8.7、AC13-a/b | 各入口局部＋019五角色矩阵/浏览器 | 文档已补，未实施 |
| ADM32-07 只读预览 | §6.8.9、AC33-b | 009词组、013预算规则、019回归；原AC33-a保持 | 文档已补，未实施 |

### 7.1 六项评审修正的落点

| 报告问题 | PRD正文 | STEP实际执行位置 | 文档状态 / 运行状态 |
|---|---|---|---|
| RV31-R01 合法Prompt预算保存 | §6.3.2、AC12-a | 003任务5/6、正向/异常保存测试 | 已写回 / 未实施 |
| RV31-R02 请求身份与未知核实 | §7.4.1/7.4.3、AC29-a/AC34-a | 002协议及物理时序、014入口/持久/查询/崩溃、016客户端消费 | 已写回 / 未实施 |
| RV31-R03 回页pending持续收敛 | §7.4.2、AC29-b | 016独立同步、有限窗口、SSE/历史分页竞态与时序测试 | 已写回 / 未实施 |
| RV31-R04 Step8全部成功出口 | §7.5、AC27-a/AC34-b | 015正常+独立兜底+提交未知/后置收尾与清槽 | 已写回 / 未实施 |
| RV31-R05 旧Prompt Test兼容 | §6.3.3、AC33-a | 013字符串/mock构建；019当前/草稿API及副作用回归 | 已写回 / 未实施 |
| RV31-R06 语音验收责任 | §6.4、AC18-a/AC18-b | 006局部写入；019实际语音writer到新文字BM25 | 已写回 / 未实施 |

补充AC30-a由006直接经过Step6/语音实际包装层验证。上述定位是修订追踪，执行方仍须阅读各步全部任务及原AC/CSTR，不得只执行新增条目。

### 7.2 当前仍必须完成的门槛

| 后续事项 | 本文已经明确什么 | 停止条件及责任STEP |
|---|---|---|
| Collection/完整遍历/编码能力 | 验证目标、来源与故障用例 | 001无实际证据不通过；不执行真实清理或跑生产全量回填。 |
| schema/其余参数/锁/未知核实 | 新入口/身份和状态语义、计时/恢复时序、最小字段职责及参数表产物要求；本期配置提交结果精确关联 | 002须将物理设计、错误映射、必要有限数值及依据填实并评审；未完成不放行依赖实现。费用与日常延迟/提升幅度数字目标不计缺口。 |
| 实际业务与UI/事务兼容 | 每个实际消费出口和本次新增子用例 | 003/006/013～019等按前置逐步实施；真实事务、浏览器、隔离依赖缺失不能用mock冒充通过。 |
| 真实质量与硬约束证据 | 同集文字漏召回/混淆/稍复杂查询的标注、最终选入质量、同集总体改善（不设幅度数字阈值）、关键不退步、正常/降级分报；日常延迟/提升幅度仅记录，费用不设门槛 | 020未冻结真实同集/标注/质量口径不正式判定；021缺真实同集总体改善/关键不退步/硬约束证据不通过。不得因缺费用或日常延迟/提升幅度数字目标阻断020/021/022，不宣称未观察到的优化收益。 |
| 仓库集成/部署与切换 | 配套文件版本与记录、原导航/current更新责任 | 022按实际实现同步；全量对账/新库恢复/运行证据不齐不切换；生产操作另需授权。 |

**原后台文档阶段交接：`DOC_REVISED_WITH_GATES / PASS_WITH_RISKS`；当时业务未实施。当前执行状态见§3。** RV31六项及ADM32后台联动均已成为正文与执行/验收要求；物理协议、模型/有限参数、浏览器/数据库/真实效果和生产切换证据仍须按门槛完成，不假装程序已修复。

### 7.3 原STEP版本来源（历史记录，非本次执行声明）

> 本文件由已封存的 R1 修复候选 `steps-candidate-r1.md` 签发，候选 SHA-256 为 `cb3ef78014d0936e4bb4375ecb95b17040cb81c20efef6794c75b9f5c33f736b`，原稿 `steps-draft.md` SHA-256 为 `21d3be4c12af7add7f8567d4abd6b06118ef0c43bdbdaced4309c6dbe38fea29`。用户已授权“按审计结果修复并复审”；`$execute-approved-work` 作为候选唯一写入方完成 SDR-001～006，`$step-doc-review` 随后依据当前 PRD、必要契约与代码事实对全部 STEP 完整复审，结果为 **PASS_WITH_RISKS / STEPS_VERIFIED**，过程及证据见 `step-audit.md`。本文的权威范围为经复审的 STEP 计划，实施状态仍为 0/22、`NOT_STARTED`；相应门槛和运行验收须在实施时完成。本轮未实施业务代码、生产回填或发布。原稿及候选保留。

上述旧版陈述仅保留原计划来源及历史审核状态；其工具、路径与审计产物不表示本次重新执行/生成。本次用户授权的是文档修复与复核，交付边界以本文件开头及§7.4为准，实施门槛见§7.2。

### 7.4 2026-10-08本轮局部修订记录（非业务实施）

- 继承2026-10-07用户取舍到§1.4、RQ-18/AC19/CSTR-04/05、共同执行门及020～022/§7.2：费用不设门槛，日常延迟/提升幅度只记录，无数字阈值；文字精准召回与现有稍复杂查询优先，不调整内容结构，语音读取仍延期。
- 当前P01及测试预期引用统一为v3.2，历史v3.1来源和摘要保留；原后台稿GitHub/审计登记与本轮本地复核区分。002只交设计证据，004只交持久基础证据，008只交真实回填生产证据，后续管理查询/页面按017/018/019收口，开发和验收依赖不变。
- 按既有P01 §6.8.8把详情大清单分页及跨页完整性写入017/018/019的AC35-a直接边界测试；依据当前PRD与既有helper明确昵称50是固定预算配置值，正文不裁剪并完整计入max_total，补003/013两边界；配置发布未知的本次提交关联设计交002，003/019补并发更后版本与证据不足待核实断言，不建通用写平台。
- 本轮验证只覆盖文档与本地源码证据：核对22STEP、15F、26RQ、35根AC、13CSTR及22子AC集合、原开发/验收边、0/22状态、历史审计原文、围栏与表格、费用/延迟/提升及版本引用作用域；无源码修改、运行测试、模型调用、线上查询或生产操作。当前配套PRD摘要由两文档收尾时统一重算；历史来源摘要不重算。

**本节记录原局部修订交接`DOC_REVISED_WITH_GATES / PASS_WITH_RISKS`；最新S15修订及0/22执行状态见§3.5。** 本轮文档修复不会将任何实施STEP标DONE；后续按§7.2提交真实技术定稿、质量/硬约束、事务/浏览器及切换证据。
