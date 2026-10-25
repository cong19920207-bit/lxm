# STEP-002：参数字典与推演样例

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

版本 `m2-design-20261009.1`；日期2026-10-09；全部 **PLANNED**。属于[主技术方案](STEP-002-技术方案与参数定稿.md)，不是新需求、已生效配置或正式质量结论。Q02～Q07原取舍不重选；以下给出有限工程默认及实施断言。聊天/轮询专有参数唯一来源为[提交协议](STEP-002-提交身份与截止协议.md)，后台参数/schema唯一来源为[后台交接](STEP-002-后台接口与页面交接.md)。

## 1. 全字典共用校验与发布规则

- `int`必须JSON整数且拒绝bool，`float`必须有限数；范围含端点，null/NaN/Infinity拒绝。PATCH缺省=保留当前，不等于0；首次无已发布配置才用本文默认，已发布配置不完整/非法拒绝发布及新链消费，不暗退默认。除明确说明外0非法，不代表关闭一路。
- 热参数记入版本化`vector_retrieval_config/prompt_token_config`；发布通过合并校验、完整测连/模型profile校验后，数据库事务写head/version/publish receipt，commit确认后失效Redis。缓存key必须携精确版本；运行冻结组合，不能一次请求中途换值。版本未知维持unverified，不用更后active version代替本次成功。
- `固定`参数不可由Admin表单改变；`profile`参数随已验证供应商/编码器profile整体发布，不能单改限制上限假装供应商放宽。参数改变只影响新请求，维护task与回填run继续冻结自身profile和原轮截止。
- 默认是工程起点，不承诺召回质量、费用或日常延迟达标。020冻结同集标注/质量口径，021评测才能调整门槛；不沿旧向量threshold复制值。

## 2. Q02/Q04：四路、分值与融合

路径中`r∈{cg,cp,ck,user}`逐路展开，存储字段为嵌套`routes.r`；后台显示四行、每行以下四个数值。cg公开设定、cp角色对用户私有设定、ck角色知识、user用户记忆；映射现有type而非新增类型分类。

| 字段 | 类型/单位 | 默认 | 范围/空零/交叉校验 | 生效与故障影响 | 交接断言 |
|---|---|---:|---|---|---|
| `routes.r.dense_top_k`（4项） | int/条 | 20 | 1～50；null/0非法 | 热配置；每路独立dense候选上限；无score门槛 | 003/010：四路独立，负分可入候选 |
| `routes.r.bm25_top_k`（4项） | int/条 | 20 | 1～50；null/0非法 | 热配置；每路独立sparse上限；空query跳过有明确原因 | 003/010：不能用0关路 |
| `routes.r.final_top_k`（4项） | int/条 | 8 | 1～50且≤dense+bm25 | 热配置；去重/重排准入后按本路截前缀，再受token预算 | 003/013：无固定3条、路间不借名额 |
| `routes.r.rerank_min_score`（4项） | float/API score | 0.10 | 0～1；0合法代表所有合法API分可过；null非法 | 热配置；仅完整正常rerank判`score>=threshold`；降级忽略此字段 | 011/021：实测三例0.88/0.33/0.006仅证明API分，0.10待同集校准 |
| `rrf_k` | int/名次平滑，固定profile | 60 | 固定60 | 双通道失败融合用rank，不比较dense/BM25数值 | 011：手算例A |
| `rrf_dense_weight / rrf_bm25_weight` | float/profile | 1 / 1 | 固定等权 | 单通道直接保留原顺序，双通道同分按合并输入序 | 011：不能生成rerank_score |
| `dense_candidate_threshold` | null/固定 | null | 只允许null | 新链停用旧threshold，旧控件显示停用 | 003/010/019：不得以0代替null |

同一通道排序按供应商rank；合并输入先dense有序，再补BM25新身份，身份=(partition,id,generation,body_hash)。正常rerank同分按该输入序，再按稳定id；重复identity同代去重。同身份版本不一致先做可信当前核对，过期rank不参与新代融合。

**例A（手算）**：dense `[A,B,C]`，BM25 `[B,D,A]`。RRF(A)=1/61+1/63=0.0322664585；B=1/62+1/61=0.0325224749；C=1/63=0.0158730159；D=1/62=0.0161290323。顺序`B,A,D,C`，全部rerank_score=null，final_top_k=2得到`B,A`。若仅dense成功则`A,B,C`，不是拿dense分数冒充重排分。

## 3. Q03：模型计数、模块预算与完整条目

| 字段 | 默认token | 范围/可编辑性 | 归属与校验 |
|---|---:|---|---|
| `max_total` | 7373 | int 1024～32768，热配置 | 完整最终Prompt官方text计数+封装预留；不得用模块配置和代替实际消耗 |
| `system` / `persona` | 720 / 1080 | 各1～8192 | 延续既有模块用途；不可裁剪内容最终超限阻断 |
| `character_knowledge` | 600 | 1～8192 | cg/cp/ck共享；含标题/标签/分隔符；按cg→cp→ck轮转 |
| `relationship` | 360 | 1～8192 | 原关系模块与原裁剪策略 |
| `memory` | 900 | 1～8192 | user独立；完整key：value、标题/分隔符 |
| `emotion` / `time_activity` | 270 / 80 | 各1～8192 | 原上下文用途/裁剪策略 |
| `recent_chat` | 1800 | 1～16384 | 原近聊模块，仍按既有优先级先裁剪 |
| `user_nickname` | 50 | 固定，不在PATCH可编辑集合 | 不是昵称全文上限；不截昵称，全文实际计总量 |
| `user_input` | 900 | 1～8192 | 沿既有输入截断；记忆条目不借此截断 |
| `request_envelope_reserve` | 64 | profile固定64 | 总量额外预留，包在max_total内；不是给昵称另加额度 |
| `output_context_reserve` | 4096 | profile固定4096 | 仅校验供应商上下文可容纳输入+输出，不从记忆模块扣、不改变旧回复max_tokens设置 |
| `tokenization_call_timeout_ms` | 5000 | int 1000～10000/profile | 原整轮预算内；计数不可用就prompt_budget_unverified失败，不用近似值放行 |
| `tokenization_max_retry` | 1 | 固定最多一次临时失败重试 | 退避250ms计入原预算；确定参数错误不重试 |

每个可编辑模块预算≤max_total；固定nickname在合并后校验，不要求PATCH提交固定字段。保留模块和顺序：system/persona/character_knowledge/relationship/memory/emotion/time_activity/recent_chat/nickname/input。总量裁剪优先级沿现有`recent_chat → memory → character_knowledge → relationship → time_activity`；不自动换一套低预算配置，不重新从候选补位。

**计数器决定**：新链以实际冻结回复model的官方Ark `/api/v3/tokenization` 对**完整渲染字符串**计数，标识`ark-tokenization:{model}:render-v1`；各模块渲染也用同计数器，动态拼接后重新完整计数，不能累加独立字符串token数当最终真实值。标题/标签/换行/昵称均在渲染内。请求内按(model,sha256文本)缓存，批量计数已知候选模块前缀，避免每加一条串行HTTP；计数时限属于整轮，不新开业务窗口。

current运行model为`doubao-seed-2-0-lite-260428`，真实API与三例结果见主文证据。`cl100k_base`可在旧链继续显示近似，**不得**在新链硬预算、诊断中冒称供应商实测计数；换model但无对应官方counter/profile则拒绝激活新链。64是显式工程预留，合成single-user/disabled-thinking样本封装差29，不构成所有供应商封装的数学证明；保留请求形状/模型版本并记录实际usage用于发现漂移。不得为了使用这份样本，擅自把业务thinking关闭或max_tokens改成16。

本期RQ-09的硬门槛为约定的`official_rendered_tokens+64 <= max_total`；与供应商包括隐藏chat模板的计费prompt_tokens分列。[火山官方模型列表](https://docs.volcengine.com/docs/82379/1330310?lang=en)于2026-10-09核实当前型号context为256k、最大输入224k、回答默认4k/最大128k；profile以更保守十进制值`context_window=256000,input_limit=224000`冻结，不依赖k的二进制换算。校验`max_total<=input_limit`和`max_total+4096<=context_window`；本期max_total最高32768亦有充足余量。实际请求仍沿既有输出/thinking设置与供应商错误处理，不把4096当已验证的思维链上限；未实测最大上下文边界，003换profile必须重新核公开限制与测连。

**例B（模块前缀）**：角色预算100，标题10；cg1=30、cp1=40、ck1=25、cg2=15、cp2=8（数字为同计数器完整边际charge测试夹具）。选cg1→cp1后占80；ck1放不下则停ck；cg2可入占95；cp2放不下停cp。成功顺序`cg1,cp1,cg2`，总量再需腾15时先删cg2，不能删cp1后补ck1。正文从不截断。

**例C（昵称）**：实际昵称80，其他最终渲染6000，预留64，max_total7373，合计6144通过，固定50不造成截断/单独拒绝；不可裁剪最终渲染7400+64=7464则返回原失败反馈，回复模型调用数0。003/013必须用实际拼接后官方counter/固定测试counter两层分别验，测试数字不是供应商自然语言样例实测。

## 4. Q05：模型profile与请求限制

| 服务/profile | 固定请求与限制 | 超限/异常与证据边界 |
|---|---|---|
| embedding `text-embedding-v4`,1024 | 单批≤10段，每段≤8192 tokens；文档/query均仅value/Question，1024有限非零L2；不在新链调用里默认叠加LLMClient重试 | 模型/错维直接失败或本路dense降级；M1真实1024归一化已验；[官方Embedding](https://help.aliyun.com/zh/model-studio/embedding?disableWebsiteRedirect=true) |
| rerank `gte-rerank-v2` | 实测endpoint=`https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank`；每路独立Question+合法去重value；`top_n=N,return_documents=false` | 只有完整N条唯一整数index、0≤index<N、有限0～1 relevance_score才正常；不能用返回document替换正文 |
| rerank文档数 | 官方≤500；当前每路候选最多50+50=100 | N=0不调用；N>500直接RRF，不切片后比较跨批分数 |
| rerank单Query/Document | 官方各≤4000 tokens | 本地明确保守准入单位`U(s)=len(s.encode('utf-8'))+32`，任一U>4000直接RRF，记录`local_size_guard`，不改正文 |
| rerank全请求 | 官方`N*query_tokens + sum(document_tokens) <= 30000` | 本地按`N*U(Q)+sum(U(Di))<=30000`做准入，超过直接RRF；32不是已证明的云token上界，不冒称真实token |
| rerank供应商拒绝 | HTTP400/确定限长/参数非法 | 整路RRF、不重试、不截断/切片；保留本次limit/error分类，其他路继续 |

gte-rerank-v2官方限制与API字段来源：[阿里云重排API](https://help.aliyun.com/zh/model-studio/text-rerank-api)，2026-10-09核查；`gte-rerank`旧型号已退役，不将其当v2别名。当前没有已证实与云v2完全相同的本地tokenizer，不拿开源同家族模型冒充。U是额外保守工程准入，不是供应商实测tokens/普适上界；所有请求仍以供应商校验为准，合法且完整响应才进入正常链。可能保守降级或被供应商再次拒绝，须在020/021单列比例和质量，不能伪报“全部请求token必合规”。

**例D（限制）**：N=40、query U=100、各doc U=500，预算=40*100+40*500=24000，可发；doc U=700时32000，直接整路降级、不尝试；N=501即使正文短也不发。真实三条返回索引`0,2,1`且分值完整；非法`[0,0,2]`、缺index1、NaN、字符串index、仅返回top3而输入40均整路降级。

## 5. Q05：业务/阶段/调用预算

| 字段 | 默认/单位 | 范围/归属/空零 | 时序和测试 |
|---|---|---|---|
| `text_total_timeout_ms` | 180000ms | 固定，合法入队/Step8接收起点 | 原deadline；2026-10-09用户确认按功能业务裁决，不要求物理落盘证明；见提交协议 |
| `rewrite_stage_timeout_ms` | 45000ms | 固定 | end=min(stage开始+45s,原D)，含退避与补齐 |
| `retrieval_stage_timeout_ms` | 45000ms | 固定，四路共享 | end=min(Step2开始+45s,原D)，不是每路各45后串行累加 |
| `failed_call_max_retry` | 1次 | 固定上限 | 临时连接/限流/5xx可重试；确定非法/已超限/解析输出非法不重试；禁叠加底层默认2次 |
| `retry_backoff_ms` | 250ms | int 100～1000/profile | 全部计入阶段；无剩余预算不发第二次 |
| `rewrite_call_timeout_ms` | 20000ms | int 1000～20000/profile | 两次20s+0.25s<45s；剩余4.75s用于解析/补齐，不能跨D |
| `embedding_call_timeout_ms` | 8000ms | int 1000～8000/profile | Q批量≤4路；2*8+0.25=16.25s |
| `vector_query_timeout_ms` | 4000ms | int 500～4000/profile | dense/sparse独立并行，2*4+0.25=8.25s |
| `rerank_call_timeout_ms` | 8000ms | int 1000～8000/profile | 四路并行，每路2*8+0.25=16.25s |
| `step2_validation_reserve_ms` | 4250ms | 固定profile | 最坏串依赖16.25+8.25+16.25=40.75s，余4.25s；验证更慢即阶段降级，不能挤出45s |
| `step2_route_concurrency` | 4路 | 固定4 | 查询最多8个并行HTTP，rerank4；各受shared stage deadline |
| `use_lock_wait_ms / handoff_timeout_ms` | 2000 / 5000ms | 正整数、profile固定 | 包在整轮；没有剩余就失败，不额外续时 |
| `text_commit_prepare_reserve_ms` | 5000ms | int 1000～10000ms，与提交附录同一字段 | 进入D-当前预留后不再开启生成/润色；提交裁决依原D，不是物理提交保证 |
| `reply_call_timeout_ms` | 60000ms | int 1000～60000/profile | min(配置,D-now-当前预留)；保留原安全/Step5.5边界，共享剩余总预算，后续不足即超时 |
| `voice_writer_timeout_ms` | 20000ms | 沿既有固定20s | 不等待索引全部就绪，不套文字180/45；未确认源不能伪报成功 |

rewrite失败降级是确定性填已有输入，不额外LLM。Step2失败保留已完成合法通道，不能空壳正常。总预算包含防抖/排队/上下文/计数/安全/可选润色/裁决；45+45不是日常延迟目标，模型调用允许预算裁切，不保证每一步总能做满默认超时。成功后Step6和有限索引维护在回复预算之外，不能改变已裁决成功。

## 6. Q06：索引、回填与保护参数

| 字段 | 默认 | 类型/范围/单位 | 来源/故障/验收 |
|---|---:|---|---|
| `index_auto_attempts` | 3 | 固定3次/profile | 包含首次；远端unknown只核实，不能当可重试失败 |
| `index_retry_delays_ms` | [5000,30000] | 固定数组，与3次相配 | 首次/5秒后/再30秒；每次deadline截断；005虚拟钟验证 |
| `index_round_timeout_ms` | 120000 | int 30000～300000/ms | 锚点创建起算，queued也计时；超限manual，不无限续期 |
| `index_call_timeout_ms` | 10000 | int 1000～20000/ms | min(配置,round剩余)；超时=unknown，读核tag |
| `index_probe_interval_ms` | 5000 | int 1000～10000/ms | 120s最多24次只读核实；每probe≤3000ms并串行，剩余不足不发 |
| `index_worker_concurrency` | 4 | int 1～8/全环境 | 单identity固定1；SQL持久领取，不以每进程4偷增全局 |
| `index_worker_lease_ms / renew_ms` | 15000 / 5000 | 固定profile | lease超时可接手只读核实，不释放未知remote fence |
| `index_manual_rounds_per_day` | 3 | int 1～5/identity/滚动24h | 仅同当前task新轮；running返回原task，superseded指向新任务 |
| `use_reconcile_timeout_ms` | 30000 | int 10000～60000/ms | unknown停止自动核实并人工；保护不自动消失，其他identity可服务 |
| `embedding_cache_ttl_seconds` | 604800 | int 3600～604800/秒 | 新命名空间model/dim/L2；命中仍验证归一化 |
| `backfill_batch_size` | 100 | int 1～256/条 | 已知完整identity manifest分批fetch；不用query topk冒充扫描 |
| `backfill_source_read_concurrency` | 2 | int 1～4/全环境 | read受限；mutation仍统一index_worker全局4 |
| `backfill_max_ops_per_second` | 5 | int 1～10/次 | 全环境令牌桶，burst=5；不压过在线源写 |
| `backfill_run_timeout_seconds` | 3600 | int 60～86400/秒 | 到时持久interrupted/cursor；显式续跑同run的新执行段≤3600s，不丢原run身份 |
| `source_receipt_detail_days / tombstone_days` | 7 / 30 | 固定保障期/天 | 未结案不清；source pending payload终态即清，历史event永久可手删 |
| `maintenance_scan_ms / batch_size` | 5000 / 100 | int 1000～10000ms / 1～500 | 启动立即扫描，按next_attempt索引分页；无全表无界循环 |

BM25编码固定`dashtext==0.0.7`及zh分词配置/字典摘要、训练文档manifest摘要、全精度统计序列化摘要，合成`encoder_version=sha256(profile+artifacts)`；**不L2稀疏**。初始空库使用M1验证的确定性seed统计profile：b=0.75、k1=1.2，606条合成value语料SHA256=`caafab17efd523305dfa4c93f0b62005a7b62f89f320b28ca749bdf0a907a746`，固定统计文件synthetic-bm25（本地留存，未随本次提交；原引用：`evidence/STEP-001-synthetic-bm25-2026-10-09.json`） SHA256=`62d586126746a5c8df9a218187b5200ee306055daa5af47d90b3a1b1bcce51de`，词典文件hash逐项取M1 isolated-runtime.encoder.tokenizer_files；这只是可重复初始编码，不是业务语料的质量证明。新正文增量编码不自动重fit；后续显式fit只读当前合法value并产生新不可变版本，旧版仍被在途请求冻结，完成整库index reconciliation后才切active version。008实现落盘manifest及profile加载校验，不只存一个模糊版本字符串。

新库启用后完整来源为所有受控writer在触网前登记的identity集合；008完整遍历该集合，核对目标统计/partition与清单。若发现数量差或未知外部写入，run.execution_state=manual_required、report_complete=false，不宣称完成、不用有上限的list/query补造完整性；隔离样本可用M1完整manifest。S15取消旧库导出/迁移，不取消新库维护的完整对账。回填run/item完成公式和持久DTO见后台附录。

## 7. 参数推演验收边界

字典有限值和例A～D由设计静态检查（本地留存，未随本次提交；原引用：`evidence/STEP-002-design-check.py`）在无网络/无业务导入环境检查，结果属 **DESIGN_STATIC**；真实模型证据只覆盖主文列出的合成调用。不把算术或schema检查当004/014的事务并发运行测试。003必须测参数发布/非法合并/精确回读，011测模型全结果及限制fallback，013测实际渲染/昵称/前缀，014～016测截止与恢复；020/021再给真实质量结论。
