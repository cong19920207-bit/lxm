# Memory Knowledge Admin

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


- 文档 ID：`contract-memory-knowledge-admin`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### `admin/pages/memory-rules.html`（Step6 记忆拆解 / 原记忆规则页）

- **实现状态**：已实现。侧栏入口归入 **「对话流 Prompt → Step6 记忆拆解」**（`activeKey='cp-step6'`）；**一级菜单不再展示「记忆规则」**。顶栏标题仍可为「记忆规则配置」（页内文案未改业务逻辑）。`super_admin` / `ai_trainer` 可配置，`observer` 仅读 Step6 Prompt、全局记忆和非敏感 DashVector 参数。
- **布局**：顶部 **Tab 标签行**单独一块 `.page-card`（`memory-tab-header-card`），**每个 Tab 内容区**各包一层 `.page-card` 作为表单容器；外层 `#memory-page-wrap` 仅承担 `is-loading`，不再使用单一大卡片包全页。
- **Tab**（长记忆第一套下线改造，§6.6.3/§6.4.3）：`initTabs('memory-tabs')` — **Step6 记忆 Prompt（默认）** | 向量数据库配置 | **全局用户记忆**。**默认 Tab 为 Step6 记忆 Prompt**；旧「记忆规则」Tab（记忆提取 Prompt / 重要性评分 / 存储阈值 / 检索合并阈值）与 `memory-rules` GET/PUT 调用**已删除**（C-04/C-08，不展示历史 `memory_rules`）。
- **Step6 记忆 Prompt Tab**：`GET /api/admin/step6-memory-prompt` 填充 6 块分区表单（`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields` 11 项按 `TASK_FIELD_NAMES` 固定顺序渲染 `textarea` / `merge_rules` / `few_shot_example`）；保存收集后 `PUT /api/admin/step6-memory-prompt`（**保存即发布**），任一文本块或任一 `task_fields` 子项为空则前端 `showToast` 拦截，成功 Toast「Step6 记忆 Prompt 已保存并发布」。
- **全局用户记忆 Tab**：`user_id`（选填 `number`）+ `keyword`（选填）+ 分页；`GET /api/admin/memories/global`，列 `用户ID/Key/Value/操作`；勾选行 + 「批量删除选中」或单行「删除」→ `DELETE /api/admin/memories/batch-delete`（Body `{doc_ids}`）；固定提示「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」（R-01），API 返回 `truncated:true` 时额外 `.alert-warning` 强化展示。 删除显示source/index分态、逐项结果与维护跳转；未知保原身份查询，不能把源成功索引在途报全完成。见[配置与CRUD反馈](#memory-config-and-crud-ui)。
- **向量库 Tab**：GET `/api/admin/vector-db-config`，固定新目标/维度/FLOAT/DotProduct；legacy TopK只读、不提交top_k/need_test_first。Key未修改不提交，修改/dirty重置testPassed与结果；测试连接及安全成功/失败提示、先测后存交互保留，后端保存重新测连与持久回执。unknown按原publish_id只读核实，保存确认后刷新；observer仅配置状态。详情见[配置与CRUD反馈](#memory-config-and-crud-ui)。
- **首屏加载**：`#memory-page-wrap.is-loading` 期间 `.memory-disable-while-load` 使用 `pointer-events:none` 避免未返回数据时误操作。**不**使用 `firstLoadFinished` 变量（该变量在 `safety-rules.html` 中仍用于首屏禁用控件，与本页实现无关）。

---

<a id="memory-implementation-boundary"></a>
### 本轮实现与环境边界

本节记载工作区已实现、在自有隔离环境验证的增量。2026-10-13本地Docker业务环境`local-docker:lxmfor`已完成S15并开放epoch2，运行于新库`local_test_collection`；旧库和旧隔离分区已退役且不复用名称。实际验证及版本见唯一STEP §3.39。M8 的 cg=0.18/user=0.15 是隔离评测候选，共享默认仍为0.1；内置 System 修复不覆盖合法 active/draft/显式 override。AC19/AC20 原失败和未齐质量对照按最新用户决定作为本阶段非阻断风险保留，不能据功能通过宣称质量全通过。最终 M8/GATE-D 与实际部署状态见唯一 STEP §3。

<a id="memory-diagnostics-page"></a>
### 诊断页、菜单与原身份观察

新增 `admin/pages/memory-diagnostics.html`和对应memory-diagnostics-admin.js；菜单与维护页紧邻既有召回/Token，同域S/A/V可直访，O/T在请求新域前403。写控件data-write-action，observer仍可GET筛选/详情/分页/刷新，隐藏按钮不替代后端矩阵。

页面五块为原输入/来源/时间、冻结版本/上下文、四路Question/Keywords与候选、同次最终选入/token、执行/保存分态。长配置/候选details折叠、纯文本；按实际原分/名次、rerank、排序方式及fallback分、准入/淘汰/initial与final标志展示，缺值“未提供”，不补造费用、分数或source删除事实。保存failed/unknown不得显示已保存。

执行前由成功GET历史的server_time+performance.now校时，先busy占校时，再UUIDv7POST；在途冻结输入。sessionStorage只存请求/执行身份和无正文观察截止；重复点击复用，刷新GET原request/execution，不重POST。观察2秒×1.5/max5秒，受理+150秒停止，单GET5秒；待核实保持原状态，不自动失败/重跑。只有显式重执行建立新身份并记录parent。离页/登出/pagehide撤销观察代次；所有await核原身份/代次/凭据，旧响应不再发详情/历史/查询、不重建清掉的会话；晚POST仅原凭据还在时留最小身份。pageshow恢复原身份GET，初始间隔2秒但原窗口不续期；busy属于页面代次，不由旧await释放。

历史/四路候选与后端稳定身份/total对应，默认20、选择1/20/100，完整跨页；筛选/用户切换清旧详情并由查询序号拒迟到。空态、初次读取失败、旧快照更新失败分别显示；失败不造空页。API原HTML字符串以textContent或等效纯文本转义展示。实际API、权限、执行/保存态见[诊断生命周期](api.md#memory-diagnostic-lifecycle)，不以浏览器控制代替服务端幂等/保护证据。

<a id="memory-maintenance-page"></a>
### 维护页、真实回填和原CRUD衔接

新增 `admin/pages/memory-index-maintenance.html`、memory-index-maintenance-admin.js和共享memory-admin-common.js。默认索引task，另设backfill；can_retry/can_delete按后端资格，POST/DELETE仍锁验。重试发送UUIDv7及revision字符串，unknown只留最小request/task/revision并GET核实，不乐观报完成。展示event删除不取消/删除task、source或008对账保护，保护按钮不可用。原CRUD维护链接定位task_id，返回原页GET当前行，不将旧操作代次套新行；URL只有ID/筛选。

任务、attempts、实际关联backfills、run、items均消费真实GET分页；默认20、选1/20/100，查询scope/page序号隔离旧响应。回填读取008→017持久run/items；total未知显示扫描数/“总量未定”，无假百分比；只在state=completed、report_complete、unresolved0及cutoff存在时显示“截至记录时点完成”。历史已删明确占位，不用末空页宣布完成。无网页启动、暂停、全量回填、强制完成或恢复历史操作。见[后端分页/资格](api.md#memory-admin-paging)。

<a id="memory-config-and-crud-ui"></a>
### 配置表单、未知回执与源/索引双状态

用户详情的用户/私有记忆及全局用户记忆列表通过共享 `memory-index-status.js` 展示当前 `index_maintenance`，替代笼统“索引待修复”：区分等待处理、处理中、等待重试、需人工处理、原因暂不可用，并显示具体中文原因、白名单错误码、写入尝试次数和未超时的下次计划时间；已就绪不展示警告。超时且未领取的任务明确标记“已超时，尚未领取”，不能仅凭写入次数0推定从未执行。原因等动态文本转义；S/A/V可通过有效task_id跳转维护页，O只读原因，不展示其无权访问的维护链接。刷新仍为原列表GET，不自动修复或重试。该展示增量于2026-10-13已合并并在本地Docker生效。真实浏览器核验用户页、全局页及维护task_id跳转：旧任务显示本轮超时/需人工处理/写入尝试0次，新记忆ready不显示警告；无页面脚本错误、无浏览器写请求。后台新增入口的独立20129问题见[运行核验边界](api.md#memory-maintenance-and-backfill)。

2026-10-14分批恢复后的只读收尾复查：用户页44条、全局用户记忆3页44条及知识库2页39条均就绪、无待修复标记；维护页manual_required筛选总数0，当前自动索引任务显示completed/ready、尝试1/轮次0、无人工原因，手动重试按钮禁用。当前环境没有未就绪条目，等待/超时/待核实/人工处理/缺少原因等展示由原用户/全局浏览器隔离夹具复核，中文原因、白名单码、写入次数、已就绪不警告、文本转义及权限链接均通过；不将夹具状态冒充实际运行状态。本轮真实浏览器全部请求仅GET/HEAD、无脚本错误；自动新增沿用此前真实验收并只读复核原回执，本轮未新增或重试记忆。现有证据记录及验证范围见[收尾运行记录](api.md#memory-write-receipts)，未改变页面交互或核实规则。

2026-10-14另获授权补做一条临时记忆的真实新增：后台表单一次POST返回code0，初始列表准确显示等待处理、等待执行器领取及尝试0次；随后自动索引完成，用户页与全局页就绪且无警告，维护页显示current/completed/ready、尝试1/轮次0、无人工原因。验收后按正常DELETE移除该条，真实用户页不再显示、全局精确搜索为空态；有效用户记忆仍44条、知识库仍39条，零待修复。运行界面、权限和核实规则未修改，仅新增/删除这一条测试数据；最新真实验收和正常协议清理证据已追加现有记录的`real_create_followup`，详见[运行验收记录](api.md#memory-write-receipts)。

召回页四路dense/bm25/final topK及rerank门槛，Token页含只读nickname=50；只dirty更新、严格边界，旧TopK/threshold只读。后台向量库固定新目标new_lxm_memory_long_collection、1024/FLOAT/DotProduct，legacy TopK只读、不提交top_k/need_test_first；api_key未编辑不提交，已配状态不暴露observer掩码。前端“先测后存”保留，后端PUT按canonical provider发布与再次测试保证，不依赖客户端testPassed作为授权。dirty变更或Key编辑撤销testPassed/测连结果；成功/失败/unknown分开。

2026-10-15生产发布仅在发布快照将两处表单及后端固定目标统一为 `new_lxm_memory_long_collection`，本地测试目标不变。通用库名配置修复延期。生产快照已上线；27个隔离浏览器会话、真实后台HTTP新增/索引就绪列表/检索/正常删除及公网后台页面通过，测试后列表为空。具体范围及生产证据见唯一STEP §3.40。


发布先校UTCserver_time并UUIDv7，成功回执才显示保存；unknown保原publish_id查本人回执，刷新不以active后来版本猜成功。第三方dashvector与向量库同head；embedding/rerank参数共同生效resolver。rerank模型不固定为gte-rerank-v2；未发布时接口和模型取显式env，已发布时沿用后台配置优先，升级须先测后存。详情表单纯文本，凭据只显示许可配置状态/脱敏，不输出原文。

四类CRUD保持Stable Key、value-only、成功原字段；显示source_state/index_state两态及maintenance_task_id跳转，源成功索引pending不提示全完成、不重提取/重写。重复相同操作原ID及digest复读；未知查询原operation。批删保deleted_count/failed_doc_ids及逐项source/index，不能将index在途造source失败。用户/私有详情原GET增加上一页/下一页/只读刷新，初始page_size100；total仅500候选过滤条数，明确非全库，筛选scope回页1、拒迟到，删除后超末页仅GET回末页。全局无user300/有user500及truncated原口径保持，不升级列表算法。


三页共享memory-write-feedback：源成功关闭/退出编辑且保索引警告，明确源失败保输入；未知可关闭，自动只读观察60秒后手动核实。session只留未决ID/来源，回页GET、退出清除；回调/timer绑定原ID与观察序号，晚GET/POST不影响新操作。原权限来源列表成功GET附server_time；提交前同来源busy校时，校时失败保输入且不分配ID，首次未受理与已有expired/unknown分别展示，不以本地偏差绕时间窗。
