# PRD：记忆系统检索与 Prompt 优化升级

> 版本：v6.1（复查修订）
> 状态：待开发
> 涉及模块：`memory_llm_service` / `character_knowledge_service` / `query_rewrite_service` / `multi_vector_retrieval_service` / `dashvector_client` / `prompt_builder` / `knowledge_mgmt` / `chat.py` / `step8_subchain.py`
> v6.1 变更：新增 C31~C39 复查决策（修复 Step8 调用点、filter 双引号验证、build_filter 统一入口、补充路 per-route 与跳过优先、补充路阈值、合并写回与状态口径、存量测试修复、死变量清理）

---

# 1. 功能背景

## 当前功能是什么

系统拥有四类向量记忆库，通过 DashVector 存储和检索：

| 类型 | 含义 | 写入方 |
|---|---|---|
| `character_global` | 虚拟人公开设定（外观/性格/兴趣等） | Step6 + Admin |
| `character_knowledge` | 虚拟人知识与技能库 | Step6 + Admin |
| `character_private` | 虚拟人对当前用户的私有设定（信任/策略等） | Step6 |
| `user` | 用户画像与用户记忆 | Step6 |

每轮对话中，Step1.5 对用户消息做查询改写，Step2 用改写结果在 DashVector 做向量检索，Step3 将检索结果注入 Prompt，Step5 据此生成回复。对话结束后 Step6 异步总结本轮记忆并写入 DashVector。

## 当前存在的问题

**问题一：检索精度不足**
- Step1.5 已输出 `QueryQuestion` 和 `QueryKeywords`，但 Step2 只用了 QueryQuestion 做 Embedding，Keywords 完全未消费
- 检索无结构化过滤，全量数据中做向量搜索噪声大
- QueryQuestion 保留疑问句结构，与 DashVector 中陈述句记忆语义方向不对齐
- Step1.5 只用最后一条用户消息做改写，连续多发时理解不完整

**问题二：character_global 和 character_private 共用同一个 Embedding**
- 两者语义本质不同：前者是虚拟人全局属性，后者是虚拟人对当前用户的私有态度和策略
- 共用 Embedding 导致 character_private 路检索方向不准

**问题三：DashVector 存储缺少前缀索引字段**
- 现有字段：`content` / `stable_key` / `type` / `user_id`
- 无 `key_l1` / `key_l2` 前缀字段，DashVector filter 无法按 Key 分类缩圈

**问题四：UserRealName / UserHobbyName 写入保守、使用不稳定**
- Step6 Prompt 对称呼字段触发条件描述模糊，LLM 倾向保守输出「无」
- 称呼存放在 `relationship` 模块，Token 裁剪优先级第 4，裁掉后虚拟人丢失称呼
- Prompt 中无明确指令要求「必须用该称呼称呼用户」

## 改造目标

1. Step1.5 输入改为整包 bundled（连续多发时理解完整意图）
2. 三路融合检索：Question（HyDE）+ CandidateKeys（结构化过滤）为主路，Keywords 为召回不足时补充兜底
3. character_private 从 character_global 分离，独立一组 Query
4. 存储侧补全 `key_l1` / `key_l2` 前缀字段（Step6 + Admin 两条写入路径均需补齐）
5. Step6 LLM 输出结构不变，仅修改写入 DashVector 时的 fields 拼装
6. 修复 UserRealName / UserHobbyName 的写入提取条件和 Prompt 注入方式

---

# 2. 方案确认决策记录

以下为全部已确认决策点，直接作为实现基线。

| 编号 | 问题 | 决策 |
|---|---|---|
| C1 | 四路 QueryQuestion 均为"无"时，Step1.5 是否算成功 | **算成功**（success=True），四路跳过，Step2 零检索；修改现有校验逻辑 |
| C2 | 补充路触发阈值 0.75 是否可配置 | **本期写死**为常量 `SUPPLEMENT_TRIGGER_THRESHOLD = 0.75` |
| C3 | 称呼字段分工 | **relationship 模块移除称呼行**；UserRealName + UserHobbyName 统一由 `user_nickname` 新模块承担 |
| C4 | Step8 子链路是否同步 user_nickname | **同步**，`build_step8_prompt()` 插入 user_nickname 模块 |
| C5 | TD-022（mem_* 与 Step6 同池）是否本期处理 | **本期不做**，文档标注技术债 |
| C6 | CandidateKeys 为空时是否允许 Keywords 做主检索 | **严格 2.5 路**，CandidateKeys=[] 时主路无 filter 正常用 HyDE，0 条再触发 Keywords |
| C7 | 补充路触发条件 | **行为 A**：`count < 2 OR max_score < 0.75`，宁多勿少 |
| C8 | user_nickname 模块位置（主链） | **recent_chat 之后，user_input 之前** |
| C9 | DashVector filter 引号与中文 | **统一双引号**；filter 中文字符串直接使用；基本转义（值中双引号转义为 `\"`）；hash 只用于 doc_id，与 filter 无关 |
| C10 | QueryQuestion 跳过判断逻辑 | `value.strip() == "" OR value.strip() == "无"` 均视为跳过，统一处理 |
| C11 | Keywords 为空时补充路行为 | **跳过补充路**，该路最终结果以主路为准，不做空串 Embedding |
| C12 | 补充路合并后 TopK | **固定 Top 3**，与热配 top_k 无关；主路 top_k 使用热配值，补充路 top_k 固定 3 |
| C13 | Step1.5 Prompt 中是否保留用户称呼行 | **保留**，Step1.5 是改写模型不是对话模型，昵称上下文有助于生成更准确的 UserProfile Query |
| C14 | Agent build_active_message_prompt 是否同步 user_nickname | **同步**；user_nickname 位于 relationship 之后、memory 之前（与主链不同，Agent 无 recent_chat） |
| C15 | Admin update_entry 是否补写 key_l1/key_l2 | **必须补写**，不赌 Upsert 字段保留行为；与 create_entry 逻辑一致；建议抽公共函数 |
| C16 | user_nickname 数据来源 | **直接从 relationship_info 取**，不经 round_context 中转 |
| C17 | Step8 是否适用 Q1（bundled） | **不适用**；Step8 传给 Step1.5 的是 future_action（约 20 字约定描述），不是用户消息包，逻辑不同 |
| C18 | fallback_embedding 是否同步用 bundled | **同步用 bundled**；截断后传入（与 C28 共用同一截断函数） |
| C19 | recent_chat 与 bundled 重复怎么处理 | **接受重复**（与 Step3 行为一致）；Step1.5【任务】加综合理解说明 |
| C20 | Step1.5【用户当前消息】文案 | **主链**：标题改为「【用户本轮消息（可能多段，换行分隔）】」并加综合理解说明；**Step8**：保持原标签不变 |
| C21 | 发布粒度 | **一次发布**：PRD 全量 + Q1 + contract 更新 + 测试集；拆开会出现 bundled 进旧 7 字段 Prompt 的中间态 |
| C22 | Step5.5 称呼是否改动 | **不改动**；Step5.5 有独立 6 段 Prompt 结构，称呼在 relation_brief 片段独立管理，与主链 C3 完全独立；`{{USER_HOBBY_NAME}}` 为必填占位符，删除会导致 Admin 发布校验失败 |
| C23 | 后台发布测试集更新范围 | **pytest 单测 + CI 新增 3 条冒烟（分两层）**：Step1.5 层：① 四路全「无」→ success=True，fallback_embedding 为空；② 含 CharacterPrivateCandidateKeys → 解析成功；Step2 层：③ 四路全无时 skipped_routes 含四路，无 DashVector 调用；Admin 发布门禁不改动 |
| C24 | bundled 拼接格式 | **保持 `"\n".join(content)`**，与 Step3/Step5 现有格式一致 |
| C25 | 参数命名 | **`last_user_text` 重命名为 `rewrite_input`**，避免传 bundled 时语义误导 |
| C26 | Agent user_nickname 位置 | **relationship 之后、memory 之前**（Agent 无 recent_chat，与主链位置逻辑一致但结构不同） |
| C27 | filter 统一 | **统一 `build_filter()` 函数**；`search()` 与 `list_by_filter` 共用；type 和 key_l2 均用双引号 |
| C28 | bundled 截断范围 | **Step1.5 输入（rewrite_input）与 fallback_embedding 两处均截断**，共用同一截断函数；避免「LLM 超时失败」与「Embedding 报错」两类风险 |
| C29 | bundled 截断 N 的具体值 | **尾部 4000 字符**；策略：取 `bundled[-4000:]`；尾部优先（最后几条消息语义更重要）；4000 字符约 1500~2000 Token，在阿里云 text-embedding-v3 安全范围内 |
| C30 | user_nickname Token 上限是否热配 | **硬编码在 MODULE_TOKEN_LIMITS**；模块文案极短（20~50 Token），运营无调参需求；本期不新增配置项 |

## 2.1 v6.1 复查决策（C31~C39）

以下为对照代码仓复查后新增/补强的决策点，与 C1~C30 同等效力。

| 编号 | 问题 | 决策 |
|---|---|---|
| C31 | 参数重命名 `last_user_text→rewrite_input`（C25）会破坏 Step8 调用点 | **§9 改造范围补 `step8_subchain.py`**；三处调用点（`chat.py`、`step8_subchain.py`、`query_rewrite_service` 内部）同步改 `rewrite_input`；Step8 仍传 `future_action`（不传 bundled，与 C17 一致） |
| C32 | filter 双引号（C9/C27）是否被 DashVector 接受 | **已验证：双引号合法**。阿里云官方文档示例使用双引号（`name like "zhang%"`），现网单引号亦可用，二者均被支持。保留 C9/C27 双引号方案，`build_filter()` 对 value 内双引号转义（`\"`） |
| C33 | `build_filter()` 落地范围与 `list_by_filter` 共用方式（C27） | **build_filter 作为统一入口**：`search()` 新增 `candidate_keys: list[str] = []` 默认参数并内部调用 build_filter（老调用方零改动，自动获得双引号，行为不变）；`character_knowledge_service.list_entries` 改为用 `build_filter(mt, None, [])` 生成 filter 后传入 `list_by_filter`；§9 补注共用调用方（memory 去重 / agent / chat QA）「已评估，双引号合法，行为不变」 |
| C34 | `search()` 新签名与补充路复用契约（C7/C11/C12） | **补充路与主路共用同一 `search()`**：签名 `search(vector, memory_type, user_id, top_k, threshold, candidate_keys=[])`；主路 `candidate_keys=该路CandidateKeys, top_k=热配`；补充路 `candidate_keys=[], top_k=3`，靠空 keys 在 build_filter 中自然去掉 `key_l2`，无需新增方法 |
| C35 | 补充路触发/执行粒度（C7） | **per-route 独立判断**：四路各自用自己的结果与 Keywords 判断与执行补充；且 **被 C10 跳过的路（QueryQuestion=「无」/空）不触发补充路，最终结果直接 []**（跳过优先级高于补充触发）；`should_trigger_supplement` 仅对「未跳过且主路已执行」的路调用 |
| C36 | 补充路 `threshold` 取值 | **沿用热配 threshold（默认 0.7），与主路一致**；补充路兜底力来自「换 Keywords 这条不同 query + 去 key_l2 约束」，而非降阈值（降阈值与本次提精度初衷相悖）；上线后若兜底偏弱，再按 TD 升级为独立可配阈值 |
| C37 | 补充路合并结果写回 + C1 状态口径 | ①每路「主路+补充路合并去重→score 降序→Top3」**写回该路对应的 `*_results` 字段**；②C1 四路全无属成功态：`is_fallback=False`、`skipped_routes=四路全名`；③`skipped_routes` 路名**统一用 memory_type 常量值**（`character_global` / `character_private` / `character_knowledge` / `user`），与 `format_for_prompt()` 的 key、C23 测试断言、日志口径一致 |
| C38 | 存量测试随改动 fail（C23 仅含新增冒烟） | **C23 测试范围扩充：含存量测试修复**。`tests/test_query_rewrite_service.py`：`last_user_text`→`rewrite_input` 改名 + 改写「三组全空抛错」用例为「四路全空→success=True 不抛错」；`tests/test_step024_step8_subchain.py`：断言键名 `last_user_text`→`rewrite_input`。与新增 3 条冒烟共同构成完整测试范围，保障 C21 一次发布 CI 绿 |
| C39 | `chat.py` 的 `last_user_text` 死变量 | **删除 `last_user_text`**；`bundled = "\n".join(...)` 与 `bundled_truncated = _truncate_bundled(bundled)` 定义提前到 Step1.5 调用之前，Step1.5（rewrite_input）与 Step5（build_chat_prompt 的 user_input）**共用同一个 bundled** |

---

# 3. DashVector Upsert 语义分析（C15 依据）

## 项目实际使用的接口

```
POST /v1/collections/{collection}/docs/upsert
```

`dashvector_client.upsert()` 每次传入的 `merged_fields = {**fields, "type": memory_type}`，即本次请求体就是该文档的完整 fields。

## 官方文档对两个接口的说明差异

| 接口 | Method | 对「只传部分 fields」的说明 |
|---|---|---|
| Update | PUT .../docs | 明确：未传的 fields 会被置为 null |
| Upsert | POST .../docs/upsert | 仅写「id 已存在则等同于更新」，**未说明未传字段是否保留** |

## 结论

**不赌 Upsert 的字段保留行为。update_entry 必须与 create_entry 一样补写 key_l1/key_l2。**

- 改动极小（多 2 行，与 create_entry 逻辑完全一致）
- 无论 Upsert 是「覆盖」还是「null 未传字段」，都安全
- 单测 mock 按整包替换 fields 实现，印证了全量覆盖的假设

**上线前验收项**（不阻塞开发）：create 写入 key_l2 → fetch 确认存在 → update value → fetch 确认 key_l2 仍在。

---

# 4. Step5.5 称呼分析（C22 依据）

## 结论：Step5.5 不改动

Step5.5 使用独立 6 段 Prompt 结构（system / style_rules / ctx_readonly / relation_brief / history_brief / messages_input），称呼在 `relation_brief` 片段中独立管理：

```
【关系与称呼】
亲密称呼：{{USER_HOBBY_NAME}}
→ 若为「无」或空：不要凭空造一个
用户真名：{{USER_REAL_NAME}}
→ 若为「无」或空：不要凭空造一个
```

## 为什么不存在重复指令问题

```
主链 Step5 Prompt（user_nickname 模块）：
  → 「请用小明称呼用户」
  → Step5 LLM 生成回复 messages

↓ 串行，Step5 完成后才进入 Step5.5

Step5.5 Prompt（relation_brief 片段）：
  → 「亲密称呼：小明」（润色时的参考上下文）
  → Step5.5 LLM 对 messages 做语气润色

两个是串行的独立 LLM 调用，各自有各自的 Prompt
Step5.5 的称呼是「润色参考」，不是对用户说话的指令
主链 relationship 模块是否被裁剪，不影响 Step5.5
  （Step5.5 数据来源是 chat.py 直接传参，绕过 prompt_builder）
```

## 为什么不能删

`{{USER_HOBBY_NAME}}` 在 `STEP5_5_PLACEHOLDER_RULES` 中被列为必填占位符，`validate_step5_5_fragments_dict()` 校验会对其做强制检查，删除会导致 Admin 发布模板时校验失败。

---

# 5. 功能改动说明

## 改动前

### Step1.5 输入与输出

**输入**：`last_user_text = pack_rows[-1].content`（仅最后一条）

**输出（7 字段）**：

```json
{
  "InnerMonologue": "...",
  "CharacterGlobalQueryQuestion": "...",
  "CharacterGlobalQueryKeywords": "...",
  "CharacterKnowledgeQueryQuestion": "...",
  "CharacterKnowledgeQueryKeywords": "...",
  "UserProfileQueryQuestion": "...",
  "UserProfileQueryKeywords": "..."
}
```

- character_global 和 character_private 共用同一组 Query
- Keywords 生成但不消费
- 校验：任一 QueryQuestion 非空才算成功，全空抛错降级

### Step2 检索（3 Embedding + 4 路）

```
cg_emb = Embedding(CharacterGlobalQueryQuestion)
ck_emb = Embedding(CharacterKnowledgeQueryQuestion)
up_emb = Embedding(UserProfileQueryQuestion)

character_global  路：cg_emb，无 user_id
character_private 路：cg_emb，有 user_id   ← 复用，不独立
character_knowledge 路：ck_emb，无 user_id
user 路：up_emb，有 user_id

filter：type = '{memory_type}' [AND user_id = {uid}]
QueryQuestion="无"时仍做 Embedding 和检索（无意义调用）
```

### DashVector 存储字段

```json
{
  "content": "外貌-体态-细节：说话时肩膀略绷紧",
  "stable_key": "外貌-体态-细节",
  "type": "character_global"
}
```

doc_id 格式：`{memory_type}_{sha256(key)[:12]}_{user_suffix}`

### Prompt 称呼相关

```
【关系状态】（Token 裁剪第 4 优先级，可被裁掉）
...
亲密称呼：小明    ← 可被裁掉
用户真名：王明    ← 可被裁掉
```

---

## 改动后

### Step1.5 输入与输出

**输入（C24/C25）**：

```python
bundled = "\n".join(r.content for r in pack_rows)  # 整包，\n 分隔
await execute_query_rewrite(rewrite_input=bundled, ...)  # 参数重命名
```

**输出（13 字段）**：

```json
{
  "InnerMonologue": "...",

  "CharacterGlobalQueryQuestion": "... | 无 | 空串",
  "CharacterGlobalQueryKeywords": "...",
  "CharacterGlobalCandidateKeys": ["外貌-体态", "兴趣-偏好"],

  "CharacterPrivateQueryQuestion": "... | 无 | 空串",
  "CharacterPrivateQueryKeywords": "...",
  "CharacterPrivateCandidateKeys": ["用户-信任", "策略-回复"],

  "CharacterKnowledgeQueryQuestion": "... | 无 | 空串",
  "CharacterKnowledgeQueryKeywords": "...",
  "CharacterKnowledgeCandidateKeys": ["咖啡-萃取", "职场-边界"],

  "UserProfileQueryQuestion": "... | 无 | 空串",
  "UserProfileQueryKeywords": "...",
  "UserProfileCandidateKeys": ["经历-出行", "偏好-饮食"]
}
```

**校验变更（C1）**：JSON 解析成功即 success=True，四路全「无」是合法成功态，不再抛错。

### Step2 检索（2.5 路融合）

```
主路（各路独立）：
  cg_emb  = Embedding(CharacterGlobalQueryQuestion)
  cp_emb  = Embedding(CharacterPrivateQueryQuestion)  ← 独立，不再复用
  ck_emb  = Embedding(CharacterKnowledgeQueryQuestion)
  up_emb  = Embedding(UserProfileQueryQuestion)

  filter：build_filter() 统一函数，双引号（C27）
  含 key_l2 IN (...)（中文字符串，C9）

补充路（按需触发，C7/C11/C12）：
  触发：count < 2 OR max_score < 0.75
  Keywords 空串 → 该路补充路跳过（C11）
  Keywords 非空 → kw_emb = Embedding(Keywords)，无 key_l2 filter
  合并去重 → score 降序 → Top 3（固定，C12）
```

### DashVector 存储字段（改造后）

```json
{
  "content": "外貌-体态-细节：说话时肩膀略绷紧",
  "stable_key": "外貌-体态-细节",
  "key_l1": "外貌",
  "key_l2": "外貌-体态",
  "type": "character_global"
}
```

doc_id 仍然 hash（原因：doc_id 不支持中文，与 filter 机制无关）。

### Prompt 称呼相关（C3/C8/C16）

```
【关系状态】（移除称呼行）
当前关系等级：...
语气与行为边界：...
关系描述：...
对TA的印象：...
← 亲密称呼行删除
← 用户真名行删除

【用户称呼】← 新增，不可裁剪，recent_chat 之后，user_input 之前
请用「小明」称呼用户（用户偏好称呼，日常优先使用）；真名为「王明」（正式场合备用）
```

---

## 核心变化汇总

| 维度 | 改动前 | 改动后 |
|---|---|---|
| Step1.5 输入 | 最后一条 last_user_text | 整包 bundled 截断后传入（尾部 4000 字符，C24/C25/C28/C29）|
| Step1.5 参数名 | last_user_text | rewrite_input（C25）|
| Step1.5 字段数 | 7 | 13 |
| Step1.5 校验 | 任一 QueryQuestion 非空 | JSON 解析成功即可，全「无」合法（C1）|
| 跳过判断 | 无 | 空串 OR「无」均跳过（C10）|
| character_private | 复用 CharacterGlobal Embedding | 独立一组（3 字段 + 独立 Embedding）|
| Keywords | 生成不消费 | 主路不足时兜底；空串跳过（C11）|
| DashVector filter | 单引号，仅 type + user_id | 双引号，build_filter() 统一，增加 key_l2 IN（C9/C27）|
| 补充路 TopK | 无 | 固定 3，与热配 top_k 无关（C12）|
| 存储字段 | stable_key | 新增 key_l1 / key_l2 |
| Admin update_entry | 只传 content/stable_key | 同步补 key_l1/key_l2（C15）|
| 称呼注入 | relationship 模块，可裁剪 | 独立 user_nickname 模块，不可裁剪（C3）|
| 称呼数据来源 | 经 Prompt 模块读取 | 直接从 relationship_info 取（C16）|
| Step8 称呼 | 无保障 | 同步 user_nickname 模块（C4）|
| Agent 称呼 | 无保障 | build_active_message_prompt 同步，relationship 之后 memory 之前（C14/C26）|
| Step5.5 | 原有称呼在 relation_brief 片段 | 不改动（C22）|
| fallback_embedding | 用 last_user_text | 用 bundled_truncated（尾部 4000 字符，与 rewrite_input 共用同一截断结果，C18/C28/C29）|

---

# 6. 功能详细逻辑

## 完整对话链路

```
用户发送消息（可连续多发）
    ↓
Step1（数据准备）
    ↓
bundled = "\n".join(pack_rows 内容)        ← 整包拼接（C24）
bundled_truncated = bundled[-4000:]        ← 截断，两处共用（C28/C29）
    ↓
Step1.5（查询改写 LLM）
  输入：rewrite_input=bundled_truncated（C25/C28）
  输出：13 字段；四路全「无」合法（C1）
    ↓
Step2（多路向量检索）
  character_private 独立 Embedding
  2.5 路融合；跳过逻辑（C10）
    ↓
Step3（Prompt 拼装）
  新增 user_nickname 模块（不可裁剪）
  relationship 删称呼行
    ↓
Step5（LLM 生成回复）
    ↓
Step5.5（润色，C22 不改）
    ↓
SSE 推送
    ↓（异步，不阻塞 SSE）
Step6（记忆总结 & 写入 DashVector）
  fields 新增 key_l1/key_l2
  称呼提取条件优化
```

---

## Step1.5 详细逻辑

### 输入变更（Q1/C24/C25/C28/C29）

```python
# chat.py 改动：先拼 bundled，截断后传入
# C39：删除原 last_user_text = pack_rows[-1].content（改造后成死变量）；
#      bundled / bundled_truncated 定义提前到 Step1.5 调用之前，
#      Step1.5（rewrite_input）与 Step5（build_chat_prompt 的 user_input）共用同一个 bundled

# 截断工具函数（C28/C29），两处共用
BUNDLED_MAX_CHARS = 4000  # 尾部 4000 字符

def _truncate_bundled(text: str) -> str:
    """取尾部 4000 字符；尾部语义更重要（最后几条消息）"""
    return text[-BUNDLED_MAX_CHARS:] if len(text) > BUNDLED_MAX_CHARS else text

bundled = "\n".join(r.content for r in pack_rows)  # C24：\n join
bundled_truncated = _truncate_bundled(bundled)       # C28/C29：两处共用截断

query_rewrite_result = await execute_query_rewrite(
    user_id=user_id,
    rewrite_input=bundled_truncated,   # C25：参数重命名，传截断后整包（C28）
    persona_text=_persona_text,
    round_context=round_context,
    recent_conversations=recent_10,
    source="main",
)

# fallback_embedding 同步（C18/C28）：共用同一截断结果
_fallback_with_embedding(text=bundled_truncated, ...)
```

**Step8 不适用 Q1（C17）**：

```python
# step8_subchain.py 保持不变
execute_query_rewrite(
    rewrite_input=future_action,  # 约 20 字 future_action，不是用户消息包
    source="step8",
)
```

### Prompt 改写规则（新增内容，追加到【任务】模块末尾）

**主链 Step1.5 标签变更（C20）**：

```
改前：【用户当前消息】

改后：【用户本轮消息（可能多段，换行分隔）】
      请综合理解所有段落的整体意图后改写，
      不必逐段单独处理，以整体意图为准（C19）
```

**Step8 Step1.5 标签不变（C17/C20）**：

Step8 输入是 future_action，单条约 20 字，原标签【用户当前消息】语义仍然准确，不修改。

**HyDE 陈述句改写要求（四路均适用）**：

```
QueryQuestion 改写规则：
❌ 禁止：保留疑问词（什么、有没有、哪些、怎么、吗、呢）
❌ 禁止：以「问」「想知道」「询问」等动词开头
✅ 必须：改写为陈述句
✅ 必须：语义重心落在「事实内容」上
✅ 保留：所有关键语义词
不需要检索该类记忆时，输出空串或字符串"无"
```

**CandidateKeys 生成规则（四路均适用）**：

```
CandidateKeys 生成规则：
- 推断用户意图可能命中的记忆分类
- 输出二级或三级 Key 前缀，宁多勿少，最多 8 个
- Key 格式：XXX-XXX 或 XXX-XXX-XXX
- 极度模糊或该路为「无」时，输出空数组 []
```

**各路分类参考**：

| 路 | 含义 | 分类参考 |
|---|---|---|
| CharacterGlobal | 虚拟人公开设定 | 外貌-体态 / 兴趣-偏好 / 价值观-待人 / 性格-特征 |
| CharacterPrivate | 虚拟人对当前用户私有态度 | 用户-信任 / 策略-回复 / 关系-态度 |
| CharacterKnowledge | 虚拟人知识技能 | 咖啡-萃取 / 职场-边界 / 心理-情绪 |
| UserProfile | 用户画像与记忆 | 经历-出行 / 偏好-饮食 / 社交-朋友 / 习惯-作息 |

**Step1.5 Prompt【关系状态】保留用户称呼行（C13）**：

```
Step1.5 的【关系状态】模块继续保留「用户称呼：{call_name}」行
原因：Step1.5 是改写模型，不对用户说话
      昵称上下文有助于生成更准确的 UserProfile Query
      与 C3（主链 Prompt 称呼职责分离）不冲突
```

**Few-shot 示例（追加到 Step1.5 Prompt，含多条连发示例）**：

示例1 — 单条，只涉及用户记忆：
```json
用户本轮消息：
我喜欢吃什么？

输出：
{
  "CharacterGlobalQueryQuestion": "无",
  "CharacterGlobalCandidateKeys": [],
  "CharacterPrivateQueryQuestion": "无",
  "CharacterPrivateCandidateKeys": [],
  "CharacterKnowledgeQueryQuestion": "无",
  "CharacterKnowledgeCandidateKeys": [],
  "UserProfileQueryQuestion": "用户喜欢吃的食物和口味偏好",
  "UserProfileCandidateKeys": ["偏好-饮食", "偏好-口味"]
}
```

示例2 — 多条连发，综合理解整体意图：
```json
用户本轮消息：
我对海鲜过敏
今晚吃什么好

输出：
{
  "CharacterGlobalQueryQuestion": "无",
  "CharacterGlobalCandidateKeys": [],
  "CharacterPrivateQueryQuestion": "无",
  "CharacterPrivateCandidateKeys": [],
  "CharacterKnowledgeQueryQuestion": "无",
  "CharacterKnowledgeCandidateKeys": [],
  "UserProfileQueryQuestion": "用户的饮食禁忌和今晚的饮食偏好",
  "UserProfileCandidateKeys": ["偏好-饮食", "健康-过敏", "习惯-饮食"]
}
```

示例3 — 涉及虚拟人私有设定：
```json
用户本轮消息：
你最近对我印象怎么样？

输出：
{
  "CharacterGlobalQueryQuestion": "无",
  "CharacterGlobalCandidateKeys": [],
  "CharacterPrivateQueryQuestion": "林小梦对当前用户的印象和态度",
  "CharacterPrivateCandidateKeys": ["用户-信任", "关系-态度", "策略-回复"],
  "CharacterKnowledgeQueryQuestion": "无",
  "CharacterKnowledgeCandidateKeys": [],
  "UserProfileQueryQuestion": "无",
  "UserProfileCandidateKeys": []
}
```

示例4 — 纯情绪，四路全无：
```json
用户本轮消息：
唉

输出：
{
  "CharacterGlobalQueryQuestion": "无",
  "CharacterGlobalCandidateKeys": [],
  "CharacterPrivateQueryQuestion": "无",
  "CharacterPrivateCandidateKeys": [],
  "CharacterKnowledgeQueryQuestion": "无",
  "CharacterKnowledgeCandidateKeys": [],
  "UserProfileQueryQuestion": "无",
  "UserProfileCandidateKeys": []
}
```

### 校验逻辑变更（C1）

```python
# 删除旧校验（全部移除）
# has_any = (CharacterGlobalQueryQuestion or CharacterKnowledgeQueryQuestion or UserProfileQueryQuestion)
# if not has_any: raise ValueError(...)

# 新校验：JSON 解析成功 + Pydantic 校验通过 = success=True
# 四路全为「无」是合法成功态，不再抛错
```

### QueryRewriteOutput 模型

```python
class QueryRewriteOutput(BaseModel):
    InnerMonologue: str = ""

    CharacterGlobalQueryQuestion: str = ""
    CharacterGlobalQueryKeywords: str = ""
    CharacterGlobalCandidateKeys: list[str] = []

    CharacterPrivateQueryQuestion: str = ""        # 新增
    CharacterPrivateQueryKeywords: str = ""        # 新增
    CharacterPrivateCandidateKeys: list[str] = []  # 新增

    CharacterKnowledgeQueryQuestion: str = ""
    CharacterKnowledgeQueryKeywords: str = ""
    CharacterKnowledgeCandidateKeys: list[str] = [] # 新增

    UserProfileQueryQuestion: str = ""
    UserProfileQueryKeywords: str = ""
    UserProfileCandidateKeys: list[str] = []        # 新增
```

---

## Step2 详细逻辑

### 跳过判断（C10）

```python
def _should_skip(question: str) -> bool:
    v = question.strip()
    return v == "" or v == "无"

# 跳过的路：不生成 Embedding，不执行 DashVector 搜索，结果为 []
# 记录到 skipped_routes 字段
```

### Embedding 并行生成

```python
# 仅对未跳过的路并行 gather
# character_private 独立生成，不再复用 character_global 的 Embedding
tasks = {}
if not skip_cg: tasks["cg"] = get_embedding(CharacterGlobalQueryQuestion)
if not skip_cp: tasks["cp"] = get_embedding(CharacterPrivateQueryQuestion)
if not skip_ck: tasks["ck"] = get_embedding(CharacterKnowledgeQueryQuestion)
if not skip_up: tasks["up"] = get_embedding(UserProfileQueryQuestion)

results = await asyncio.gather(*tasks.values())
```

### filter 构造规则（C9/C27 统一 build_filter）

```python
def build_filter(
    memory_type: str,
    user_id: int | None,
    candidate_keys: list[str],
) -> str:
    """
    统一 filter 构造函数，search() 与 list_by_filter 共用（C27）
    全部使用双引号（C9）
    """
    # type 双引号
    base = f'type = "{memory_type}"'
    if user_id is not None:
        base += f' AND user_id = {user_id}'
    if candidate_keys:
        l2_set = set()
        for k in candidate_keys:
            parts = k.split("-")
            if len(parts) >= 2:
                # 转义值中的双引号（C9）
                l2 = (parts[0] + "-" + parts[1]).replace('"', '\\"')
                l2_set.add(l2)
        if l2_set:
            quoted = ", ".join(f'"{v}"' for v in l2_set)
            base += f' AND key_l2 IN ({quoted})'
    return base

# 示例输出：
# 'type = "user" AND user_id = 123 AND key_l2 IN ("经历-出行", "偏好-饮食")'
```

**关于中文 filter 的说明（C9）**：
- `stable_key` / `content` 字段已在 DashVector 中存储大量中文，中文字符串存储无问题
- `key_l2` 用中文存入 fields，filter 中用同样的中文字符串匹配，UTF-8 编码天然一致
- hash 只用于 doc_id（doc_id 有格式限制），与 filter 是完全独立的两套机制

### search() 新签名与主/补充路调用契约（C33/C34）

```python
# dashvector_client.search 新签名：新增 candidate_keys 默认参数，内部统一走 build_filter()
async def search(
    vector, memory_type, user_id=None,
    top_k=DEFAULT_TOP_K, threshold=SIMILARITY_THRESHOLD,
    candidate_keys: list[str] = [],   # 新增（C33/C34）；默认 [] → 老调用方零改动
) -> list[dict]:
    filter_str = build_filter(memory_type, user_id, candidate_keys)
    ...

# 主路调用：带该路 CandidateKeys，top_k 用热配
search(vector=cg_emb, memory_type=..., user_id=..., top_k=热配top_k,
       threshold=热配threshold, candidate_keys=该路CandidateKeys)

# 补充路调用：candidate_keys=[] → build_filter 自然去掉 key_l2（范围更宽兜底），top_k 写死 3
search(vector=kw_emb, memory_type=..., user_id=..., top_k=3,
       threshold=热配threshold, candidate_keys=[])
```

补充路与主路**共用同一个 `search()`**，仅靠 `candidate_keys=[]` 区分，无需新增方法（C34）。

### 2.5 路补充触发（C7/C11/C12/C35/C36）

**补充路 per-route 独立判断（C35）**：四路各自用自己的主路结果与各自 Keywords 判断/执行补充；
**被 C10 跳过的路（QueryQuestion=「无」/空）不触发补充路，最终结果直接 []**（跳过优先级高于补充触发）。

```python
SUPPLEMENT_TRIGGER_THRESHOLD = 0.75  # 常量，本期写死（C2）

def should_trigger_supplement(main_results: list[dict]) -> bool:
    """仅对「未跳过且主路已执行」的路调用（C35）"""
    if len(main_results) < 2:
        return True
    return max(r["score"] for r in main_results) < SUPPLEMENT_TRIGGER_THRESHOLD

# 每路独立执行（per-route，C35）：
# 0) 该路被 C10 跳过 → 不触发补充，最终结果 []，不调用 should_trigger_supplement
# 1) should_trigger_supplement(该路主路结果) 为 True 才进入补充
# 2) 该路 Keywords 空串 → 跳过补充路，结果以主路为准（C11）
# 3) 该路 Keywords 非空：
#      kw_emb = Embedding(该路 Keywords)
#      search(candidate_keys=[], top_k=3, threshold=热配threshold)  # 去 key_l2，阈值沿用主路（C36）

# 合并逻辑（C12）：合并去重 → score 降序 → Top3 → 写回该路对应 *_results（C37）
def merge_results(main: list, supplement: list) -> list:
    seen = set()
    merged = []
    for r in main + supplement:
        if r["id"] not in seen:
            seen.add(r["id"])
            merged.append(r)
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:3]  # 固定 Top 3
```

**补充路阈值说明（C36）**：补充路 `threshold` 沿用热配 threshold（默认 0.7），与主路一致；
兜底力来自「换 Keywords 这条不同 query + 去 key_l2 约束」，而非降阈值。

**TopK 分层说明（C12）**：

| 阶段 | top_k 来源 | 说明 |
|---|---|---|
| 主路 DashVector 搜索 | 热配 `vector_retrieval_config.top_k`（默认 3）| 可运营调整 |
| 补充路 DashVector 搜索 | 写死 3 | 兜底，不随热配变 |
| 合并后最终结果 | 写死 Top 3 | 控 Token 和噪声，不随热配变 |

### MultiVectorRetrievalResult 变更

```python
@dataclass
class MultiVectorRetrievalResult:
    character_global_results: list[dict] = field(default_factory=list)
    character_private_results: list[dict] = field(default_factory=list)
    character_knowledge_results: list[dict] = field(default_factory=list)
    user_results: list[dict] = field(default_factory=list)
    top_k: int = _DEFAULT_TOP_K
    threshold: float = _DEFAULT_THRESHOLD
    is_fallback: bool = False
    skipped_routes: list[str] = field(default_factory=list)  # 新增（C37）
```

**字段写回与状态口径（C37）**：
- 每路「主路+补充路合并 Top3」写回该路对应的 `*_results` 字段
- `skipped_routes` 路名统一用 memory_type 常量值：`character_global` / `character_private` / `character_knowledge` / `user`（与 `format_for_prompt()` key、C23 断言、日志一致）
- C1 四路全无属**成功态**：`is_fallback=False`，`skipped_routes` 填四路全名（区别于 Step1.5 失败的降级态 `is_fallback=True`）

---

## Step6 详细逻辑

### LLM 输出结构（不变）

Step6 LLM 输出的 11 字段 JSON 结构不变，`parse_kv_lines` 解析逻辑不变。

### upsert_step6_vectors 改动

```python
for key, value in kv_pairs:
    key_err = validate_key(key)
    if key_err:
        continue  # 现有逻辑：校验失败跳过

    # validate_key 通过 → key 必然是三层 XXX-XXX-XXX
    # segments 必然有 3 段，无需额外防御
    segments = key.split("-")

    doc_id = build_doc_id(memory_type, key, effective_user_id)
    # doc_id 仍然 hash：doc_id 不支持中文，与 key_l2 filter 无关（C9）

    vector = await embedding_service.get_embedding(value)

    fields = {
        "content": build_content(key, value),
        "stable_key": key,
        "key_l1": segments[0],                      # 新增
        "key_l2": segments[0] + "-" + segments[1],  # 新增，中文字符串直接存
    }
    if attach_user_id:
        fields["user_id"] = user_id

    await dashvector_client.upsert(
        doc_id=doc_id,
        vector=vector,
        fields=fields,
        memory_type=memory_type,
    )
```

### Step6 Prompt：称呼提取条件优化

```
UserHobbyName：用户在本轮对话中希望被称呼的方式。
触发提取条件（满足任一即提取）：
  - 用户明确说"叫我XXX"/"你可以叫我XXX"
  - 用户用某个名字或代号自称
  - 用户纠正了虚拟人的称呼方式
  - 用户在轻松语境中透露了昵称
未出现以上情况时，输出"无"

UserRealName：用户的真实姓名或正式称谓。
触发提取条件（满足任一即提取）：
  - 用户主动告知了自己的真名
  - 用户在自我介绍中出现了名字
未出现以上情况时，输出"无"
```

---

## Admin 后台详细逻辑

### character_knowledge_service.py 改动

建议抽取公共函数，create 和 update 共用（C15）：

```python
def _build_knowledge_fields(key: str, content: str) -> dict:
    """create_entry 与 update_entry 共用，避免逻辑分叉"""
    segments = key.split("-")  # validate_key 已保证 3 段
    return {
        "content": content,
        "stable_key": key,
        "key_l1": segments[0],
        "key_l2": segments[0] + "-" + segments[1],
    }

# create_entry 使用
fields = _build_knowledge_fields(key, content)

# update_entry 使用（C15：必须补写，不赌 Upsert 字段保留行为）
# key 从 _resolve_stable_key(doc_id) 获取（读 stable_key 或从 content 解析）
fields = _build_knowledge_fields(key, new_content)
```

**list_entries 改用 build_filter（C33）**：

```python
# 改前：list_entries 自拼单引号 filter
# filter_str = f"type = '{mt}'"

# 改后：统一用 build_filter（双引号，与检索侧一致；list 场景无 user_id / 无 candidate_keys）
filter_str = build_filter(mt, user_id=None, candidate_keys=[])  # → type = "xxx"
rows = await dashvector_client.list_by_filter(filter_str, top_k=LIST_TOPK)
```

### Admin 列表页（knowledge.html）

- 列表展示字段不变（key / value / type / doc_id）
- key_l1 / key_l2 后台不展示，运营无感知
- 搜索/筛选逻辑不变

### Admin 向量/Prompt Token 配置页

本期不新增配置项。`SUPPLEMENT_TRIGGER_THRESHOLD = 0.75` 写死为代码常量。

### 后台发布测试集（C23）

**落地方式：pytest 单测 + CI，Admin 发布门禁不改动。**

**存量测试同步修复（C38，与新增冒烟共同构成完整测试范围）**：
- `tests/test_query_rewrite_service.py`：`_base_execute_kwargs` 的 `last_user_text`→`rewrite_input`；改写 `test_all_three_questions_empty_raises`（C1 删除该校验后，应改为「四路全空→success=True 不抛错」）
- `tests/test_step024_step8_subchain.py`：断言 `call_kwargs.kwargs["last_user_text"]`→`rewrite_input`

新增 3 条冒烟用例，分两个测试文件：

**`tests/test_query_rewrite_service.py`（Step1.5 层）**：

```
用例 1：四路全「无」
  输入：Step1.5 LLM mock 返回四路 QueryQuestion 均为"无"
  断言：success=True
        output.CharacterGlobalQueryQuestion == "无"（或空串）
        fallback_embedding 为空列表（不触发降级）
  注意：不断言 skipped_routes，该字段属于 Step2 的 MultiVectorRetrievalResult

用例 2：含 CharacterPrivateCandidateKeys 的正常输出
  输入：Step1.5 LLM mock 返回含 CharacterPrivateCandidateKeys 字段
  断言：QueryRewriteOutput 解析成功
        CharacterPrivateCandidateKeys 正确为 list[str]
        success=True
```

**`tests/test_multi_vector_retrieval_service.py`（Step2 层）**：

```
用例 3：Step2 在四路全无时的跳过行为
  输入：QueryRewriteResult.success=True，四路 QueryQuestion 均为"无"或空串
  断言：skipped_routes 包含全部四路
        四路检索结果均为 []
        未调用任何 DashVector search（mock 验证零调用）
        is_fallback=False（成功态，不是降级）
```

---

## Prompt 详细逻辑

### 模块顺序（主链，改造后）

```python
MODULE_ORDER = [
    "system",              # ≤720 Token，绝不裁剪
    "persona",             # ≤1080 Token，绝不裁剪
    "character_knowledge", # ≤600 Token，可裁剪（优先级3）
    "relationship",        # ≤360 Token，可裁剪（优先级4，已移除称呼行）
    "memory",              # ≤900 Token，可裁剪（优先级2）
    "emotion",             # ≤270 Token
    "time_activity",       # ≤80 Token，可裁剪（优先级5）
    "recent_chat",         # ≤1800 Token，可裁剪（优先级1）
    "user_nickname",       # ≤50 Token，绝不裁剪（新增，C8）
    "user_input",          # ≤900 Token
]
```

### user_nickname 模块构建（C16）

```python
def _build_user_nickname_prompt(relationship_info) -> str:
    # 直接从 relationship_info 取，不经 round_context（C16）
    hobby = getattr(relationship_info, "user_hobby_name", None) or ""
    real  = getattr(relationship_info, "user_real_name", None) or ""
    hobby = hobby.strip()
    real  = real.strip()

    if hobby and real:
        return (
            "【用户称呼】\n"
            f"用户偏好被称为「{hobby}」（日常优先使用）；"
            f"真名为「{real}」（正式场合备用）"
        )
    elif hobby:
        return f"【用户称呼】\n请用「{hobby}」称呼用户（用户偏好称呼，日常优先使用）"
    elif real:
        return f"【用户称呼】\n用户真名为「{real}」，可在合适场合使用"
    else:
        return ""  # 均为空，不输出该模块
```

### relationship 模块改动（C3）

`_build_relationship_prompt()` 删除以下两行：

```python
# 删除
parts.append(f"亲密称呼：{uhn if uhn else '无'}")
parts.append(f"用户真名：{urn if urn else '无'}")
```

`_build_relationship_prompt_core()`（裁剪版）本来就没有这两行，无需改动。

### Token 裁剪优先级

```
裁剪顺序（从先裁到后裁）：
1. recent_chat     → 从最早对话逐条删除
2. memory          → 从最低分（末尾）逐条删除
3. character_knowledge → 按 score 从低到高逐条删除
4. relationship 扩展 → 移除 relation_description / user_description 等扩展字段
5. time_activity   → 整块移除

绝不裁剪：system / persona / user_nickname
```

### Step8 同步（C4）

`build_step8_prompt()` 新增：

```python
module_texts["user_nickname"] = self._build_user_nickname_prompt(relationship_info)
```

MODULE_ORDER 在 Step8 中与主链一致，user_nickname 插入 recent_chat 之后、user_input 之前。

### Agent 同步（C14/C26）

`build_active_message_prompt()` 新增 user_nickname，位置在 relationship 之后、memory 之前（Agent 无 recent_chat 模块，C26）：

```python
parts = [
    system_prompt,
    persona_prompt,
    relationship_prompt,
    user_nickname_prompt,   # 新增，relationship 之后、memory 之前（C26）
    memory_prompt,
    emotion_prompt,
    task_prompt,
]
```

---

# 7. 边界情况

## Memory 边界

### 四路 QueryQuestion 均为「无」（C1/C10）

```
场景：用户发送「唉」等纯情绪消息
Step1.5 输出：四路 QueryQuestion 均为「无」或空串
处理：success=True，skipped_routes = 四路全部
Step2：零 Embedding，零 DashVector 调用
Prompt：角色设定与知识为空，用户记忆「暂无用户相关记忆」
Step5：依赖 persona 和 relationship 正常生成回复
```

### CandidateKeys 命中 0 条

```
场景：CandidateKeys=["经历-出行"]，但该用户无此类记忆
主路结果 = []（0 条）→ 触发补充路（count < 2）
补充路：不加 key_l2 filter，范围更宽
补充路仍为 0 条 → 最终结果=[]，Prompt「暂无」，不报错
```

### Keywords 为空串，补充路跳过（C11）

```
场景：主路 < 2 条，触发补充，但 QueryKeywords = ""
处理：该路补充路跳过，最终结果以主路为准
不做空串 Embedding（无意义且浪费 API 调用）
```

### 存量旧数据无 key_l2 字段

```
改造前写入的旧记忆，fields 中无 key_l1/key_l2
主路 key_l2 IN filter → 旧记忆不满足 → 主路不召回
补充路不加 key_l2 filter → 旧记忆可被补充路召回（兜底有效）
长期：单独排期写迁移脚本补全 key_l1/key_l2（本期不做，TD）
```

### CandidateKeys 格式非法

```
场景：LLM 输出 CandidateKeys 包含单层 key（如「偏好」）
处理：build_filter 中 split("-") 后长度 < 2 → 丢弃该项
剩余合法项正常过滤；无合法项 → 不加 key_l2 filter
不报错，不影响主链路
```

### bundled 截断（C18/C28/C29）

```
截断常量：BUNDLED_MAX_CHARS = 4000（尾部字符数）
截断函数：_truncate_bundled(text) → text[-4000:] if len > 4000 else text

两处均使用截断后的 bundled_truncated（C28）：
  1. rewrite_input → Step1.5 LLM 输入（避免 LLM 超长超时失败）
  2. fallback_embedding text → Embedding API 输入（避免 API 报错）

截断策略：尾部优先
  正常 1~5 条短消息：bundled 通常 <2000 字符，截断无损
  极端 10 条长消息：保留尾部约 2 条完整消息，最近意图完整保留
  「过敏」在前、「吃啥」在后 → 尾部 4000 字符通常能覆盖两者

Embedding API 报错仍触发时：
  降级返回空 embedding，fallback 路结果为空，Prompt「暂无」
```

### Admin update_entry 后 key_l2 验收（C15）

```
上线前验收：
  1. create 写入 key_l2
  2. fetch_by_ids 确认 key_l2 存在
  3. Admin 页面 update value（只改 value，不改 key）
  4. fetch_by_ids 确认 key_l2 仍在
此验收用于确认 DashVector Upsert 实际行为，update_entry 已补写 key_l2 保证安全
```

## 对话边界

### Step1.5 降级（LLM 失败，C18/C28）

```
LLM 调用失败 or JSON 解析失败 → success=False
Step2：使用 fallback_embedding（bundled_truncated 的 Embedding，C18/C28）
  与 rewrite_input 共用同一截断结果，无需重复截断
四路均使用 fallback_embedding，不加 key_l2 filter
行为与改造前一致，用户无感知
```

### recent_chat 与 bundled 内容重叠（C19）

```
场景：连发 M1/M2/M3，recent_10 里已包含 M1/M2/M3，bundled 也是 M1\nM2\nM3
Step1.5 改写 LLM 会看到两遍相同内容
处理：接受重复（与 Step3 行为一致）；
     Step1.5 Prompt【任务】加综合理解说明约束 LLM 不重复处理
影响：Step1.5 Token 略增，耗时略增；不影响功能
```

### Step2 某路 Embedding 失败

```
该路主路结果 = [] → 触发补充路（count < 2）
补充路 Embedding 也失败 → 该路最终 = []，Prompt「暂无」
不向上抛异常，记录 warning 日志，不影响其他路
```

### Prompt Token 超限

```
裁剪按优先级执行，user_nickname 不参与裁剪
裁剪后仍超限：记录 warning 日志，允许超限发送（LLM 侧截断）
user_nickname ≤50 Token，对总量影响极小
```

### 称呼模块与关系模块

```
Token 充足：relationship（关系描述/印象）+ user_nickname（称呼指令）均在
Token 紧张：relationship 被裁，user_nickname 仍在（不可裁）
            LLM 仍能看到称呼指令，不丢失
两模块职责分离，无重复指令（C3 保证）
```

### 连续多发时 Step1.5 意图覆盖（Q1 已知缺口）

```
场景：pack_rows 有 10 条（最多），Step1.5 看整包 bundled
     其中前 9 条都在 recent_10 里（历史）
     改写 LLM 同时看到「近期对话」和「当前消息」里的重复内容

影响：Step1.5 Token 增大；改写模型可能过度关注最后几句
缓解：Few-shot 示例已覆盖多条连发场景；任务说明要求「综合整体意图」
长期：可考虑 Step1.5 传入 bundled 时排除已在 recent_10 的消息（本期不做）
```

---

# 8. 数据结构

## DashVector fields 完整矩阵

| 字段 | character_global | character_knowledge | character_private | user |
|---|---|---|---|---|
| content | ✅ | ✅ | ✅ | ✅ |
| stable_key | ✅ | ✅ | ✅ | ✅ |
| key_l1 | ✅ 新增 | ✅ 新增 | ✅ 新增 | ✅ 新增 |
| key_l2 | ✅ 新增 | ✅ 新增 | ✅ 新增 | ✅ 新增 |
| user_id | ❌ | ❌ | ✅ | ✅ |
| type | ✅ | ✅ | ✅ | ✅ |

## 写入路径矩阵

| 类型 | Step6 写入 | Admin 写入 |
|---|---|---|
| character_global | ✅ memory_llm_service | ✅ character_knowledge_service |
| character_knowledge | ✅ | ✅ |
| character_private | ✅ | ❌ 无 Admin 页 |
| user | ✅ | ❌ 无 Admin 页 |

## Step1.5 输出结构

```python
class QueryRewriteOutput(BaseModel):
    InnerMonologue: str = ""

    CharacterGlobalQueryQuestion: str = ""
    CharacterGlobalQueryKeywords: str = ""
    CharacterGlobalCandidateKeys: list[str] = []

    CharacterPrivateQueryQuestion: str = ""
    CharacterPrivateQueryKeywords: str = ""
    CharacterPrivateCandidateKeys: list[str] = []

    CharacterKnowledgeQueryQuestion: str = ""
    CharacterKnowledgeQueryKeywords: str = ""
    CharacterKnowledgeCandidateKeys: list[str] = []

    UserProfileQueryQuestion: str = ""
    UserProfileQueryKeywords: str = ""
    UserProfileCandidateKeys: list[str] = []
```

## Step2 检索结果结构

```python
@dataclass
class MultiVectorRetrievalResult:
    character_global_results: list[dict] = field(default_factory=list)
    character_private_results: list[dict] = field(default_factory=list)
    character_knowledge_results: list[dict] = field(default_factory=list)
    user_results: list[dict] = field(default_factory=list)
    top_k: int = _DEFAULT_TOP_K
    threshold: float = _DEFAULT_THRESHOLD
    is_fallback: bool = False
    skipped_routes: list[str] = field(default_factory=list)  # 新增
```

---

# 9. 改造范围与文件索引

| 文件 | 改动内容 | 改动量 |
|---|---|---|
| `chat.py` | 先拼 bundled；`_truncate_bundled()` 截断函数；传 rewrite_input=bundled_truncated；fallback 共用同一截断结果（C18/C24/C25/C28/C29）| 小 |
| `query_rewrite_service.py` | QueryRewriteOutput 新增 6 字段；Prompt 补充 HyDE/CandidateKeys 规则、标签文案、4 条 Few-shot；删除「至少一组非空」校验；参数重命名 rewrite_input（C1/C20/C25）| 中 |
| `multi_vector_retrieval_service.py` | character_private 独立 Embedding；跳过路判断（C10）；各路透传 CandidateKeys；2.5路融合；C11/C12 逻辑；skipped_routes 字段；调用 build_filter()（C27）| 中 |
| `dashvector_client.py` | 新增 `build_filter()` 统一函数（双引号+转义，已验证合法 C32）；`search()` 新增 `candidate_keys=[]` 默认参数并内部调用 build_filter()（C33/C34）| 小 |
| `multi_vector_retrieval_service.py`（补充） | 补充路 per-route 独立判断 + 跳过优先（C35）；补充路 threshold 沿用热配（C36）；合并 Top3 写回各路 `*_results`、skipped_routes 路名用 memory_type 常量值（C37）| 中 |
| `memory_llm_service.py` | `upsert_step6_vectors()` fields 新增 key_l1/key_l2；Step6 Prompt 称呼提取条件优化 | 小 |
| `character_knowledge_service.py` | 抽取 `_build_knowledge_fields()`；`create_entry()` 和 `update_entry()` 共用（C15）；`list_entries` 改用 build_filter（C33）| 小 |
| `prompt_builder.py` | 新增 `_build_user_nickname_prompt()`；MODULE_ORDER 插入 user_nickname；裁剪豁免；relationship 删称呼行；Step8 同步（C4）；Agent 同步 relationship 之后 memory 之前（C14/C26）| 小 |
| `step8_subchain.py` | **新增（C31）**：`execute_query_rewrite` 调用点形参 `last_user_text`→`rewrite_input`，仍传 `future_action`（不传 bundled，与 C17 一致）| 小 |
| `tests/test_query_rewrite_service.py` | **新增（C38）**：`last_user_text`→`rewrite_input` 改名；改写「三组全空抛错」用例为「四路全空→success=True 不抛错」| 小 |
| `tests/test_step024_step8_subchain.py` | **新增（C38）**：断言键名 `last_user_text`→`rewrite_input` | 小 |

**共用调用方（C33，已评估「双引号合法、行为不变」，无需改代码，仅纳入回归测试范围）**：
`vector_service.search` → `memory_service`（0.92 去重合并）/ `agent_service`；`chat.py` QA 检索（line 147）。这些调用方经 `search()` 自动获得双引号 filter，行为等价。

**不改动**：`character_knowledge_validate.py` / `constants.py` / `relationship_service.py` / `step5_5_service.py` / `step5_5_prompt_fragments.py` / SSE 逻辑 / H5 页面接口 / Admin 列表展示

---

# 10. 技术债标注

| 编号 | 描述 | 影响 |
|---|---|---|
| TD-022 | user 路混合 Step6 行级记忆与 mem_* 旧记忆 | 加 key_l2 filter 后 mem_* 仅靠补充路召回 |
| TD-存量迁移 | 改造前写入记忆无 key_l1/key_l2 | 主路 filter 漏旧记忆，需后续迁移脚本 |
| TD-热配扩展 | SUPPLEMENT_TRIGGER_THRESHOLD 写死 0.75 | 需调整时要发版 |
| TD-补充路阈值 | 补充路检索 threshold 本期沿用主路热配 0.7（C36），未独立可配 | 若兜底偏弱需独立阈值时要发版 |
| TD-Step1.5重复 | bundled 与 recent_chat 内容重叠 | Step1.5 Token 略增，可后续优化传参 |
| TD-Q4护栏 | Step2 最坏 4 主路 + 4 补充路，RT 有波动 | 监控 P95 Step2 耗时，叹号增多再加护栏 |
| TD-contract | docs/contract.md 需同步 Step1.5 13 字段、入参变更 | 与实现同 PR 更新（C21）|

---

# 11. 检查项

| 项目 | 状态 |
|---|---|
| Step1.5 输入改为 bundled_truncated（C24/C28/C29/Q1）| ✅ |
| 参数重命名 rewrite_input（C25）| ✅ |
| bundled 截断常量 BUNDLED_MAX_CHARS=4000，尾部（C29）| ✅ |
| rewrite_input 与 fallback_embedding 共用同一截断函数（C28）| ✅ |
| fallback_embedding 同步用 bundled_truncated（C18/C28）| ✅ |
| Step8 不适用 Q1，保持 future_action（C17）| ✅ |
| Step1.5 标签文案更新（主链），Step8 保持原标签（C20）| ✅ |
| recent_chat 与 bundled 重复，接受 + 任务说明约束（C19）| ✅ |
| character_private 独立 Query 组（3 字段 + 独立 Embedding）| ✅ |
| Keywords 作为 2.5 路补充兜底，非等价第三路 | ✅ |
| 补充路触发：count<2 OR max_score<0.75（行为 A，C7）| ✅ |
| 四路全「无」时 success=True，校验逻辑修改（C1）| ✅ |
| 跳过判断：空串和「无」统一处理（C10）| ✅ |
| Keywords 空串时补充路跳过（C11）| ✅ |
| 补充路合并固定 Top 3，主路 top_k 热配独立（C12）| ✅ |
| 补充路 top_k 固定 3，写死不热配 | ✅ |
| filter 统一 build_filter()，双引号 + 基本转义（C9/C27）| ✅ |
| DashVector filter 中文字符串直接使用，hash 只用于 doc_id | ✅ |
| Step6 fields 新增 key_l1/key_l2，doc_id 仍 hash | ✅ |
| Step6 LLM 输出结构和 parse_kv_lines 不变 | ✅ |
| Admin create_entry 与 update_entry 共用 _build_knowledge_fields（C15）| ✅ |
| 上线前验收：update 后 key_l2 仍在 | ⚠️ 发布前验收 |
| user_nickname 直接从 relationship_info 取（C16）| ✅ |
| user_nickname 位置：recent_chat 之后，user_input 之前（主链/Step8，C8）| ✅ |
| user_nickname 不参与裁剪 | ✅ |
| relationship 模块移除称呼行（C3）| ✅ |
| Step1.5 Prompt 保留称呼行（C13）| ✅ |
| UserHobbyName/UserRealName 提取条件明确化 | ✅ |
| Step8 同步 user_nickname（C4）| ✅ |
| Agent build_active_message_prompt 同步，relationship 之后 memory 之前（C14/C26）| ✅ |
| Step5.5 不改动，原因文档化（C22）| ✅ |
| 后台测试集：pytest 单测 3 条冒烟（Step1.5 层 2 条 + Step2 层 1 条），Admin 门禁不改（C23）| ✅ |
| bundled 格式保持 \n join（C24）| ✅ |
| 发布粒度：PRD + Q1 一次发布（C21）| ✅ |
| user_nickname Token 上限硬编码在 MODULE_TOKEN_LIMITS，不热配（C30）| ✅ |
| TD-022 本期不做，文档标注 | ✅ |
| SSE 链路无新增风险 | ✅ |
| H5 接口 / 对话协议不变 | ✅ |
| docs/contract.md 与实现同 PR 更新 | ⚠️ 实现时同步 |
| Step8 调用点同步改 rewrite_input，仍传 future_action（C31）| ✅ |
| filter 双引号已验证 DashVector 合法（C32）| ✅ |
| search() 加 candidate_keys=[] 默认参数，老调用方零改动；list_entries 改用 build_filter（C33）| ✅ |
| 补充路与主路共用 search()，靠 candidate_keys=[] 区分（C34）| ✅ |
| 补充路 per-route 独立判断 + 被跳过路不触发补充（C35）| ✅ |
| 补充路 threshold 沿用热配 0.7，不降阈值（C36）| ✅ |
| 合并 Top3 写回各路 *_results；C1 时 is_fallback=False；skipped_routes 用 memory_type 常量值（C37）| ✅ |
| 存量测试同步修复，与 3 条冒烟共同构成测试范围（C38）| ✅ |
| chat.py 删除 last_user_text 死变量，bundled 上移共用（C39）| ✅ |