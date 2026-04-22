# H5 对话改造：可执行任务清单 + AI 开发提示词（按顺序）

> **依据**：`docs/product-development-plan-h5-chat.md`、`docs/chat-refactor-implementation-plan.md`、`docs/tech-debt.md`（TD-015 / TD-016 / TD-017 / **TD-020**）、`**docs/admin-conversations-extension-analysis.md`**（管理端与 H5 字段统一、已定稿 A–L / 统一 / G1·H1·I1 / J2·K1·L1）。**迭代开发计划与 Vibe 提示词**：`**docs/chat-refactor-vibe-coding-plan.md`**。**  
> **产品锁定：向量检索 embedding 文本 = 本轮打包中的最后一条 user 原文（选项 B）；防抖 500ms；重发限流 仅叹号、2 次/分钟；不做全链路 45s。**  
> **重发请求体（确认点1）：选项 3 — `ChatResendRequest` 在任务 6 中可**合并支持**多种锚定字段（如 `log_ids` 或 `anchor_log_id`、`batch_anchor_sort_seq` 等）与幂等键；最终实现以代码为准，任务 8 的 `contract.md` 写清**最终实现 + 推荐字段**（与 `admin-conversations-extension-analysis.md` 文首表一致）。  
> **契约**：`docs/contract.md` 建议在 **阶段任务 8** 或与后端 API 稳定后**一次性**更新，避免半成品契约。  
> **TD-016**（`round_id`、按轮 emotion、后台情绪）：与下列任务 **解耦**，可在 **任务 8 之后** 单独立项或并行由另一分支完成。  
> **TD-020**（用户短期情绪属性、Redis/DB 真相源）：见 `docs/tech-debt.md`；与 **「后续里程碑」** 并列留痕，**勿与任务 1–8 重复实现**。  
> **主链 vs 增量**：任务 **1–8** 视为 **已交付**；**H5 流中再发、`sending`、气泡、契约补句** 见本文 **「后续里程碑」**，实施时 **勿重做** 后端调度与入队逻辑。

---

## 执行前共识（给 AI / 人的检查单）

- 已读 **TD-015** 定稿表与 **产品开发方案** §五 Must。  
- **管理端**：`GET /api/admin/users/{user_id}/conversations` 的 `list[]` 与 H5 `**GET /api/chat/timeline`** 的 `items[]` **字段名相同**、`delivery_status` **枚举与 Python 单点常量相同**；**只读**返回，**不**提供代用户重发（**L1**）。详情见 `**docs/admin-conversations-extension-analysis.md`** 文首已定稿表（A1–E1、D1、统一、G1、H1、I1、J2、K1、L1）。  
- 不改无关模块（Agent、日记、非聊天 LLM）除非任务显式写出。  
- 聊天失败：**不**将「走神」写入 `conversation_log` 的 assistant；用户侧用 **叹号状态** 表达失败。  
- 新输入：**作废旧 `generation_id`**；仅**当前有效代**可落 assistant。  
- 后置任务（成长、记忆提取、`ai_emotion`）：**每成功闭环一轮 assistant 一次**。

---

## 管理后台与契约：已定稿整合（执行摘要）

> **完整论证、风险表、归档选项**：仍见 `**docs/admin-conversations-extension-analysis.md`**；**开发以本节 + 下方任务 6 / 7 / 8 提示词为准**。


| 代号           | 含义（须在代码/契约中落实）                                                                                                                                                                                            |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A1**       | `role=assistant` 的 `list[]` / `items[]` 行：**仍带** `delivery_status`、`skipped_in_prompt` **键**，值为 `**null`**。                                                                                               |
| **B1**       | `delivery_status`：**英文蛇形**字符串；Admin 表格用**中文映射**展示（前端本地表，非第二套 API 枚举）。                                                                                                                                     |
| **C1**       | 历史迁移行默认视为已成功闭环（如 `completed` / `delivered`），**与任务 2 默认值及 Python 常量表统一**。                                                                                                                                  |
| **D1**       | Admin `list[]` **必须**含 `**sort_seq`**，与 H5 `timeline` 的 `items[]` 一致。                                                                                                                                     |
| **E1**       | API **返回** `skipped_in_prompt`（bool 或 null）；**K1**：`user-detail` **首屏不默认列**该字段，可展开查看。                                                                                                                     |
| **F1**       | `docs/contract.md` 与后端字段在 **任务 6 或 8** 同节奏更新，避免长期漂移。                                                                                                                                                      |
| **统一**       | `**GET /api/chat/timeline` → `items[]`** 与 `**GET /api/admin/users/{id}/conversations` → `list[]`**：字段名相同、`**delivery_status` 枚举取值相同**、**同一单点 Python 常量源**；`contract.md` **H5 对话**与**管理端用户对话**两处**并列**写清。 |
| **G1**       | 日记「当日有互动」等：**首版不改** `DiaryService` 逻辑；与叹号失败叠加的口径见 `**docs/tech-debt.md` [TD-018]**。                                                                                                                       |
| **H1**       | `**GET /api/chat/history`** 的 `messages[]`：**不扩展**与 timeline 对齐的送达字段；**任务 8** 须在 `contract.md` **显式写清**「送达态、`sort_seq`、叹号相关以 **timeline** 为准；history 与 timeline **能力可不一致**」。                              |
| **I1**       | **统计 SQL 逻辑不变**；若契约文字与实现对「累计对话」等描述不一致，**任务 8 只改契约表述**。                                                                                                                                                    |
| **J2**       | `contract.md` 中 `**delivery_status` 取值**：写「与代码单点枚举一致」+ **示例值**（如 `failed_timeout`）；**不**全文复制枚举表。                                                                                                          |
| **K1**       | `**admin/pages/user-detail.html`** 历史对话：**默认列**展示 `delivery_status`（短标签/图标）；**不**默认列 `skipped_in_prompt`（二级/展开）。                                                                                          |
| **L1**       | 用户端重发 **固定** `**POST /api/chat/resend`**；禁止 Admin 页面或 `/api/admin/`** **代用户重发**。                                                                                                                          |
| **确认点1·选项3** | `**ChatResendRequest`**：可声明多种锚定字段 + 幂等键，任务 6 定稿必填子集；任务 8 的 `contract.md` 只写**最终实现** + 推荐字段。                                                                                                               |


**任务映射**：`get_user_conversations` 序列化 → **任务 6**；`user-detail.html` 列与中文映射 → **任务 7**；`contract.md`（Admin+H5+resend+J2+H1+I1+SSE）→ **任务 8**。

---

## 任务 1：配置与聊天专用 LLM 超时（45s）

**目标**：仅 H5 对话相关 LLM 调用使用 **45s**；全局/其他调用保持 **15s**（或现有 `LLM_TIMEOUT`）。

**AI 提示词（复制使用）**：

```
你是本仓库的后端开发。请实现「聊天链路专用 LLM 超时 45s」，其余 LLM 调用仍为通用超时（当前 15s）。

约束：
1. 在 backend/config.py（及 .env 示例若有）增加可读配置项，例如 LLM_TIMEOUT_CHAT=45，默认 45；保留原有 LLM 超时配置不变。
2. 修改方式二选一或组合：在 llm_service.chat_with_parse 增加可选参数 timeout_sec，仅 chat 路由传入 45；或在 chat 调用链单独构造 httpx 超时。禁止把全项目所有 LLM 调用静默改为 45s。
3. 不要改 Agent、记忆提取、管理端测试等非 /api/chat/send 与重发同链路的调用超时。

验收：单测或最小脚本能证明 chat_with_parse(..., timeout_sec=45) 生效；非聊天路径仍为 15。
```

**涉及文件（预期）**：`backend/config.py`、`backend/utils/llm_client.py` 或 `backend/services/llm_service.py`、`backend/routers/chat.py`（调用处）。

---

## 任务 2：数据模型 — `conversation_log` 扩展（失败态 / Q14 标记）

**目标**：支持 **叹号再进页**、**Q14 最旧条不入 Prompt 但仍在库**。

**AI 提示词**：

```
你是本仓库后端开发。请为 conversation_log 增加与 TD-015 一致的字段（命名可与产品协商，须与 ORM 一致）：

1. delivery_status（或等价枚举字符串）：至少区分：成功送达 LLM 并闭环、等待 LLM、超时/失败可重试等。须与「叹号展示」映射关系在代码注释（中文）中写清。
2. skipped_in_prompt：bool，默认 false，用于 Q14 超过 10 条时最旧行仍落库但标记本轮未进 Prompt。

要求：
- 提供 Alembic 迁移或项目惯用的 SQL 增量脚本，与 backend/models/conversation_log.py 同步。
- 不删除历史数据；新列有合理默认值。
- 暂不实现 TD-016 的 round_id（若本任务已加 round_id 需与 TD-016 文档一致则单独说明）；优先完成 delivery 与 skipped 即可。

验收：迁移可执行；ORM 可读写；旧行默认状态合理。
```

**涉及文件**：`backend/models/conversation_log.py`、迁移脚本、`schema_ddl.sql`（若项目要求同步）。

---

## 任务 3：Redis 状态 — `generation_id`、防抖、重发限流

**目标**：每用户当前有效代；**防抖 500ms**（可配置 CHAT_DEBOUNCE_MS）；**仅叹号重发** 每分钟 **2 次**（自动调度不计入）。

**AI 提示词**：

```
你是本仓库后端开发。请实现 TD-015 约定的 Redis 侧能力（多实例安全）：

1. 存储并原子更新当前用户有效 generation_id（如 chat:gen:{user_id}）。新 user 入队并触发打断时递增/换新代，使旧 LLM 结果落库前校验失败。
2. 自动调度防抖：新消息入队后 500ms（配置 CHAT_DEBOUNCE_MS，默认 500）内合并触发一次「打包调度」，避免连发 keys 风暴。多实例必须用 Redis 实现防抖，不可用仅进程内变量。
3. 重发限流：仅针对「用户点击叹号触发的重发接口」计数，每用户每未闭环批次每分钟最多 2 次；超限返回明确业务错误码（constants.py 定义）。自动调度不得占用该配额。

约束：键名带 user_id；考虑 TTL 避免泄漏；失败时降级策略在注释中说明。

验收：并发下代替换正确；防抖合并为少量调用；重发第 3 次同分钟内被拒绝。
```

**涉及文件**：`backend/redis_client.py`（若需封装）、`backend/routers/chat.py` 或新 `backend/services/chat_queue_service.py`、`backend/constants.py`。

---

## 任务 4：对话核心状态机 — 入队、打包、作废、落库时机、重发接口

**目标**：实现 TD-015 主链路：**user 入队即 INSERT**；打包未闭环窗口（≤10 条，Q14 最旧标记 skipped）；**仅末条 user 原文**做 embedding 检索；**LLM 成功且 generation 仍有效**即写 assistant 并触发 `_post_chat_tasks`（**不**再等 SSE 结束）；主动打断不落旧 assistant；聊天失败 **SSE 不输出走神正文**；提供 **重发** API（幂等见任务 6）。

**AI 提示词**：

```
你是本仓库后端开发。请重构 backend/routers/chat.py 中与 POST /api/chat/send 及 SSE 相关的核心流程，严格符合 docs/tech-debt.md TD-015 定稿与 docs/product-development-plan-h5-chat.md Must 条款。

必须实现：
1. user 消息通过内容安全检查后入队并立即写入 conversation_log（含 sort_seq 分配规则与现有一致或文档化的新规则）。
2. 维护未闭环 user 行列表（最多 10 条参与本轮 Prompt；更旧行 skipped_in_prompt=true 且本包不包含其文本）。
3. 向量检索：embedding 仅使用「本轮参与打包中的最后一条 user」的原文（产品锁定选项 B）。
4. generation_id：每次开始一次调度（含自动防抖触发、重发触发）生成新代；新 user 打断时旧代作废，旧 LLM 返回后不得写 assistant。
5. LLM 解析成功后若 generation 仍有效：写 assistant、emotion_log 写入策略暂沿用现逻辑直至 TD-016（可临时挂 assistant 行 id）；调用现有 _post_chat_tasks 等价逻辑（成长、记忆、Redis ai_emotion），且整轮记忆拼接为多 user + 单 reply。
6. 超时 45s 或 LLM 异常：不写 assistant；将相关 user 行置为可展示叹号的状态；不向客户端 SSE 写入「走神」作为 AI 正式内容（可发 type=error 或 failed 事件，契约在任务 8 更新）。
7. 重发接口：路径固定为 **POST /api/chat/resend**（用户 JWT，**L1**）；不新建 user 行，触发当前未闭环窗口再次调度；受 Redis 限流 2 次/分钟。**不**新增 `/api/admin/...` 类「代用户重发」接口；管理端不参与重发。

禁止：为失败路径向 conversation_log 插入 assistant 占位「走神」；在未校验 generation 时写 assistant。

验收：集成测试或手工场景：打断、超时、被动成功、重发、10 条裁剪行为与文档一致。
```

**涉及文件**：`backend/routers/chat.py`、`_sse_chat_generator`、`_post_chat_tasks`、`backend/services/memory_service.py`（拼接入参）、`embedding` 调用处。

---

## 任务 5：Prompt — 本轮打包字符串 + System 文案补充

**目标**：`build_chat_prompt` 接收 **本轮一块 user 文本**（多句换行/序号均可）；**SYSTEM_PROMPT_TEXT** 或 `_build_user_input` 增加 **一两句中文**：多段输入需综合理解、**仍只输出一个 JSON 对象**；**不**拆「单句/多句」两套 JSON schema。

**AI 提示词**：

```
你是本仓库后端开发。请修改 backend/services/prompt_builder.py：

1. build_chat_prompt（及调用链）支持将「本轮多条 user」格式化为单一 user_input 字符串注入模块 7，保持 Token 裁剪上限行为与现网一致或可配置。
2. 在 SYSTEM_PROMPT_TEXT 或 _build_user_input 前缀增加简短中文说明：用户可能连续发送多段内容，须综合理解，输出仍为单一 JSON：emotion + reply。
3. 不修改 JSON 字段名与 llm_service._parse_llm_response 的解析契约（除非同步改全链路并列入契约任务）。

验收：单条发送行为与改造前语义等价；多条打包后 Prompt 中仅一块「用户消息」区域。
```

**涉及文件**：`backend/services/prompt_builder.py`、`backend/routers/chat.py`（调用 build_chat_prompt 处）。

---

## 任务 6：API 契约雏形 — 幂等、timeline、Admin `list[]`、错误码、SSE meta

**目标**：`ChatSendRequest` 增加幂等字段；`**ChatResendRequest`（确认点1·选项3）**：Body 可组合多种锚定方式（如 `log_ids` / `anchor_log_id`、`batch_anchor_sort_seq` 等与限流「未闭环批次」校验一致）及 幂等键，任务 6 内定稿**最终实现**的必填子集与校验规则；`GET /api/chat/timeline` 返回 delivery_status、skipped_in_prompt、sort_seq（与任务 2 列一致）；`**GET /api/admin/users/{user_id}/conversations`** 的 `data.list[]` **与 timeline 同名字段、同一套 `delivery_status` 枚举常量**（A1：assistant 行两键存在且值为 null；B1：英文蛇形枚举）；**constants** 增加队列满、重发限流、幂等冲突等；SSE **首包或 meta** 带 `generation_id`（与 TD-015 一致）。**依赖任务 2**：迁移未执行前 Admin/timeline **不得**编造虚构状态。

**AI 提示词**：

```
你是本仓库后端开发。请更新 backend/schemas/chat.py、backend/constants.py、backend/routers/chat.py，并扩展 backend/routers/admin/users.py 中 get_user_conversations 的序列化。

【H5 / 用户端】
1. POST /api/chat/send 请求体支持 client_message_id（或 Idempotency-Key 与之一致），重复请求不重复插入 user 行。
2. POST /api/chat/resend（L1）：定义 ChatResendRequest（确认点1·选项3）—— 可同时声明多种可选锚定字段 + 幂等键，服务端校验「指向当前未闭环窗口、状态允许重发」；实现时选定最终必填组合并在类 docstring（中文）写清；与任务 3 重发限流键维度一致。
3. GET /api/chat/timeline 的 items[]：user 行带 delivery_status、skipped_in_prompt、sort_seq（命名与 Admin 完全一致）；assistant 行按 A1 带键且值为 null。
4. SSE：在首条事件或独立 meta 事件中下发 generation_id，供前端丢弃过期流。

【管理端 · 与 admin-conversations-extension-analysis.md 一致】
5. GET /api/admin/users/{user_id}/conversations 的 list[]：每条追加 delivery_status、skipped_in_prompt、sort_seq，语义与 timeline 相同；枚举禁止硬编码第二套字符串，须从与 H5 共用的单点模块导入（如 constants 或约定模块）。
6. role=assistant：delivery_status、skipped_in_prompt 键齐全、值为 null（A1）；role=user：skipped_in_prompt 为 bool；历史行默认值与 C1 一致（与迁移默认统一）。
7. 本接口只读不写库；鉴权保持 super_admin / ops_admin。

验收：重复 client_message_id 第二次行为符合幂等设计；timeline 与 Admin list 对同一用户同一批数据字段名与枚举值一致；旧客户端忽略新键不报错。
```

**涉及文件**：`backend/schemas/chat.py`、`backend/constants.py`、`backend/routers/chat.py`、`**backend/routers/admin/users.py`**。

---

## 任务 7：H5 前端 — `chat.html` + 管理端 `user-detail.html`（K1）

**目标**：**H5**：叹号 UI、Abort 旧 SSE、`generation_id` 校验、幂等头、45s 与 timeline 纠偏、≤5 / 叹号例外、`**POST /api/chat/resend`（L1）**调用。**Admin**：历史对话区按 **K1** 展示 `delivery_status`（中文标签映射 **B1**）；**不**默认展示 `skipped_in_prompt`（可收在展开/次要入口）；**不**增加代用户重发按钮（**L1**）。

**AI 提示词**：

```
你是本仓库前端开发。请分别完成 H5 与管理端历史对话展示（保持现有样式体系）。

【Part A — frontend/pages/chat.html】产品开发方案 Must 中与 UI 相关的部分：
1. 根据 timeline 返回的 user 行状态显示左侧红叹号（样式参考产品给定示意图）；点击触发 POST /api/chat/resend（L1），请求体按任务 6 已定 ChatResendRequest（确认点1·选项3：锚定字段 + 幂等键）；成功后清除叹号。
2. 发送与流式：使用 AbortController；仅当 SSE 携带的 generation_id 与当前页面有效代一致时渲染 delta；否则丢弃。
3. 请求头携带幂等键（与后端约定一致）。
4. 未处理条数限制：无叹号时 ≤5 禁止继续发送（与后端一致）；存在叹号时允许突破 5（与文档一致）。
5. 客户端超时与首包策略与「服务端为准、timeline 纠偏」一致，避免与 45s 服务端超时长期打架。

约束：API_BASE 相对路径不变；不引入新构建工具。

【Part B — admin/pages/user-detail.html 历史对话 Tab / #conversations-list】与 docs/admin-conversations-extension-analysis.md K1、B1 一致：
1. 消费 GET /api/admin/users/{user_id}/conversations 的 list[]（任务 6 已追加字段）：默认增加一列（或图标）展示 delivery_status，使用前端中文映射表（枚举值与 H5 同源，勿手写另一套英文）。
2. skipped_in_prompt：API 已有则可在展开行、tooltip 或「高级信息」中展示；首屏表格默认不占列。
3. 禁止：代用户触发重发的按钮或调用 POST /api/chat/resend（管理端无用户 JWT，且 L1 明确不做代重发）。

验收：H5 手工可走通打断、超时叹号、重发、再进页叹号恢复（依赖任务 2/6）；Admin 打开用户详情历史对话可见送达态列，与 H5 叹号心智一致；无代重发入口。
```

**涉及文件**：`frontend/pages/chat.html`、`**admin/pages/user-detail.html`**（及若存在的专用 JS 片段）。

---

## 任务 8：测试、网关说明、契约文档更新

**目标**：更新 `tests/test_chat.py` 等；**docs/contract.md** 同步 **H5 对话**与**管理端用户对话**模块；README 或 ops 说明 Nginx `proxy_read_timeout` ≥ 45s。

**AI 提示词**：

```
你是本仓库开发与文档维护者。

1. 更新 tests/test_chat.py（及相关 e2e）：去除「失败必返回走神 assistant 落库」类旧断言；增加幂等、generation 作废、重发限流的覆盖（可 mock Redis/LLM）；若有 Admin conversations 序列化单测则对齐新字段。

2. 更新 docs/contract.md（与 admin-conversations-extension-analysis.md、F1、J2、H1、I1、L1 一致）：
   - H5：POST /api/chat/send；POST /api/chat/resend（L1，仅用户 JWT；Body 按任务 6 最终实现 + 确认点1·选项3；不写管理端重发）。
   - H5：GET /api/chat/timeline 的 items[] — delivery_status（J2：引用单点枚举 + 示例值）、skipped_in_prompt、sort_seq；SSE 事件类型与 generation_id、错误码表。
   - 管理端：GET /api/admin/users/{user_id}/conversations 的 data.list[] — 与 timeline **同名字段、同枚举说明方式（J2）**；写明 A1（assistant 两键 null）。
   - H1：单独一小节说明 GET /api/chat/history 的 messages[] **不保证**含上述送达字段；**以 timeline 为准**。
   - I1：核对 stats / 累计对话等描述与现 SQL 一致，**只改文字不改统计逻辑**。
   - G1：可脚注「日记 has_interaction 口径见 TD-018」，避免读者误以为本期已改日记服务。
   - 更新文档顶部「最后更新」日期。

3. 在 docs/ 或部署文档中增加一句：Nginx 与 LLM 超时对齐，read_timeout 建议略大于 45s。

验收：pytest 相关用例通过；contract 与实现一致；H5 与 Admin 对话列表字段描述无两套枚举。
```

**涉及文件**：`tests/test_chat.py`、`docs/contract.md`、`nginx/` 或 `docs/ops-*.md`（视仓库结构）。

---

## 任务 9（可选 / 并行）：TD-016 — `round_id` 与按轮 emotion

> **进度（2026-04-15）**：**已完成 ✓** — **V2-A** 库表与迁移；**V2-B** 闭环写入 `round_id`；**V2-C** **`GET /api/admin/users/{user_id}/emotion-rounds`** + 用户详情「情绪日志」Tab。可选：H5 进一步按 `round_id` 做 UI 增强（非本条必做）。

**目标**：见 `docs/tech-debt.md` [TD-016]；**依赖**任务 4–8 中 assistant 与多 user 关系已稳定。

**AI 提示词**：

```
你是本仓库开发。**V2-A/B/C 已合**：`round_id` 与按轮 `emotion_log` 写入见 **V2-B**；Admin 只读 **`GET /api/admin/users/{user_id}/emotion-rounds`** 与用户详情「情绪日志」Tab 见 **V2-C**；契约见 `docs/contract.md`。若后续迭代：H5 按 `round_id` 展示增强、或改 `emotion_log.conversation_id` 挂接策略，须另开 PR 并更新契约。

不重复实现 TD-015 已完成的叹号与调度逻辑；**不改** `chat.py` 主链除非单独立项。
```

---

## 逻辑复核（生成后自检 — 已通过）


| 检查项         | 结论                                                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| 任务顺序依赖      | 1→2→3 可部分并行（1+2），但 **4 依赖 1–3 与 2**；**5 与 4 可紧耦合**，建议 4 后立刻 5；**6 可与 4 后半并行**，timeline 需 2 的列；**7 依赖 6 的 API**；**8 最后**。 |
| 与产品锁定冲突     | 无；embedding **末条**在任务 4 明确写出。                                                                                            |
| 与 TD-016 冲突 | TD-016 单独为任务 9，避免与任务 4 同 PR 拖大风险。                                                                                        |
| 契约更新时机      | 任务 8 集中更新，避免任务 4–7 期间 contract 半真半假。                                                                                     |
| 重发限流与防抖     | 任务 3 与定稿「仅重发计 2 次/分、自动防抖 500ms」一致。                                                                                       |
| 失败不走神       | 任务 4、7、8 均覆盖。                                                                                                            |
| 遗漏          | **K1** 已升格为 **任务 7 必做**（`user-detail.html` 默认 `delivery_status` 列）；与「产品方案 Could」不冲突，以已定稿为准。                              |


---

## 二次复核（2026-04-09）— 执行计划补充结论


| 项                   | 结论                                                                                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **任务 4 与 6 分工**     | 任务 4 可先把 **重发路由骨架**（路径、鉴权、调状态机）落地，**请求/响应体与幂等细节**以任务 6 的 `schemas` 为准，避免两 PR 字段不一致；**禁止**任务 4 单独合并任务 6 而不更新 schema。                                                                        |
| **统计口径**            | 「对话轮次」等若按 `conversation_log` **assistant 条数**或既有 SQL 统计，多 user 一条 assistant **通常仍计 1 轮**；若存在按「成对 user+assistant」硬编码，需在 **任务 8** 核对 `stats_service` / 报表 SQL，**不**在本清单另开任务号，作为 **8 的子检查项**。 |
| **人格风险**            | 每条 user 入队仍应按现网对 **单行** 做 `_detect_persona_risk` 并写入该行（任务 4 提示词可显式写一句）。                                                                                                                    |
| **Admin 与 H5 字段对齐** | **任务 6** 必改 `get_user_conversations`；**任务 7** 必改 `user-detail.html`（K1）；**任务 8** 必更 `contract.md` 双写（与文首「管理后台与契约：已定稿整合」一致）。                                                                |


---

## 管理后台：任务档位（与已定稿对齐）


| 档位        | 页面 / 接口                                                                          | TD-015 首版是否必做      | 说明                                                                                                             |
| --------- | -------------------------------------------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------- |
| **必做**    | `GET /api/admin/users/{user_id}/conversations`（`backend/routers/admin/users.py`） | **是**（**任务 6**）    | `list[]` **只读**追加 `delivery_status`、`skipped_in_prompt`、`sort_seq`；与 timeline **同名字段、同一套枚举常量**；A1/B1/C1/D1/E1。 |
| **必做**    | `admin/pages/user-detail.html` 历史对话                                              | **是**（**任务 7·K1**） | 默认列 `delivery_status`（中文映射）；`skipped_in_prompt` 非首屏默认列；**无**代重发（L1）。                                           |
| **必做**    | `docs/contract.md` 管理用户小节                                                        | **是**（**任务 8**）    | `list[]` 与 H5 并列；**J2**；**H1**；**I1** 文字核对；**L1** 仅写用户端 resend。                                                |
| **任务 9**  | 情绪日志 / `emotion_log` 按轮（**`GET .../emotion-rounds`** + 用户详情 Tab）                                              | **否**（相对 TD-015 首版） | **TD-016 已交付（V2-C）**：只读、**`super_admin`/`ops_admin`**、无 L1。                                                                                          |
| **一般不必改** | 用户列表 `total_conversation_count` 等                                                | 否                  | **I1**：统计逻辑不变，契约文字在任务 8 子项对齐。                                                                                  |
| **一般不必改** | `prompt_mgmt` / 人格测试等管理端 LLM                                                     | 否                  | 非聊天链路 **15s**（任务 1）。                                                                                           |
| **禁止**    | Admin 代用户重发                                                                      | **禁止**             | **L1**：无 `/api/admin/`** 重发、无后台重发按钮。                                                                           |


**长篇场景分析、确认点 A–F 归档讨论**：见 `**docs/admin-conversations-extension-analysis.md`**（执行以本文 **「管理后台与契约：已定稿整合」** + **任务 6 / 7 / 8** 为准）。

---

## 后续里程碑（2026-04 沟通收口 · **待排期执行**）

> **定位**：本节记录 **任务 1–8 主链已交付之后** 才动手的增量；**不得**把已完成的入队/代作废/防抖/叹号重发/timeline/Admin 列表等 **再实现一遍**。实施前对照 **`docs/tech-debt.md` [TD-015] →「首版主链 vs 后续排期」** 与下表 **「勿重复」** 列。

### 与任务编号的对应关系

| 范围 | 状态 | 说明 |
|------|------|------|
| **任务 1–8** | **已完成（主链）** | 以仓库当前 `backend/routers/chat.py`、`frontend/pages/chat.html`、`docs/contract.md` 等为准；验收过即 **关闭**，勿回退重造。 |
| **本节「后续里程碑」** | **部分已交付（S1–S3、**VX-A（N2）**、任务 9 / TD-016）；S4 进行中；TD-020 V3-A 基座已落地** | **VX-A**：H5 **`sending` N2 解锁** + `contract.md` / 本节附录与手工用例已同步。**S4** 手工清单见 **`docs/chat-refactor-s4-manual-regression-checklist.md`**（逐项勾选完成后将本行状态改为已完成）；e2e 视团队仍可用 `scripts/test_chat_e2e.py`；**TD-020** 剩余 Admin/策略见 `tech-debt.md`。 |

### 需求快照（产品已确认）

1. **连发与打断**：在 AI 对**未闭环批次**的回复**尚未在 H5 展示完**时，用户可继续输入发送；**新输入打断**旧 SSE 展示进度；**多条 user**（示例 msg1/msg2，**实际 2～5 条**，受背压与叹号例外约束）均进入未处理队列，由后端**既有**打包调度处理。  
2. **背压**：与现网一致 — **最多 5 条**未处理新消息，超过则 **H5 锁输入 + 服务端 10104**；**叹号重发等可破 5**，**不重改**已实现逻辑。  
3. **气泡生命周期**：**打断** → 移除**进行中**的旧林小梦气泡，**仅保留**与**当前有效代**相关的新气泡（新气泡出现在**当前未闭环 user 序列之后**，如最后一条 user 之后）；**超时/失败** → 进行中 AI 气泡**移除**，**叹号在 user**；气泡语义 **只绑当前最新一轮生成**。  
4. **情绪分层（本期不大改句级/轮级实现）**：句级 `conversation_log.emotion_label` 仍表示**该句**；轮级与 **TD-016** 对齐；**用户短期情绪属性** 见 **`docs/tech-debt.md` [TD-020]**。  
5. **契约**：在 **`docs/contract.md`** **`POST /api/chat/send`** 节 **显式补充** — 允许 **未完成 SSE 时再发起 `send`**，仍以 **Abort + `chatSendSession` + `meta.generation_id`** 防串台（**仅文档与 H5 门闩**，**不改**后端已具备的作废/入队语义）。  
6. **数据模型（后续独立迭代）**：**`round_id` 贯穿本轮 user+assistant** — 归 **TD-016 / 任务 9**，**不在**本节重复 DB 设计细节。  
7. **管理后台情绪日志 Tab**：**V2-C 已交付**（`emotion-rounds` + Tab）；**不阻塞** 本节 1–3 的 H5 连发项。

### 执行清单（建议顺序 · 实施时再拆 PR）

| 步骤 | 交付物 | 涉及文件（主要） | **勿重复（已有能力）** |
|------|--------|------------------|-------------------------|
| S1 | **`sending` 门闩**：在 **收到 SSE `meta` 且已解析 `generation_id`（节点 N3）之后** 置 **`sending=false`**，允许下一次 `send`；**不改变** `pending≥5` / `hasBang` 判断 | `frontend/pages/chat.html` | **已交付**；勿改后端 **10104**、**`_should_block_new_send`** 语义 |
| S2 | **气泡 DOM**：新 `send` 触发 **Abort** 后 **移除**旧「进行中」**`.msg-row.ai`**；新代仅 **一条**进行中 AI 气泡；**failed/obsolete** 同样移除进行中气泡 | `frontend/pages/chat.html` | **已交付**；勿重复实现 **generation** 丢弃逻辑（已有 `consumeChatSse`） |
| S3 | **契约**：`contract.md` **H5 实现说明** 增加「**允许流中再 `send`**」及与 **Abort/session/generation** 的关系 | `docs/contract.md` | **已交付**；勿改写已实现 **SSE 事件类型**表意以外的后端契约 |
| S4 | **回归**：手工 / e2e — 连发、打断、5 条满、叹号破 5、超时叹号与气泡消失 | **`docs/chat-refactor-s4-manual-regression-checklist.md`**；`scripts/test_chat_e2e.py` 等（视团队） | **进行中**（手工清单已产出，全场景勾选并确认无缺陷后再标完成）；勿重跑已实现的后端单测场景当「新功能」 |

> **VX-A（2026-04-15）**：**S1** 历史交付描述曾为 **N3（`meta`）解锁 `sending`**；当前仓库实现为 **N2（SSE 响应体首包非空字节）**，以 **`docs/contract.md` → `POST /api/chat/send`「H5 实现说明」** 为真源。

#### 已定稿（沟通收口 · 2026-04）

- **确认点 1（已定）**：**选项 1** — **叹号重发**与 **`send` 共用 `sending` 规则**；**在收到 SSE `meta` 之前** 若 `sending===true`，**重发入口同样不可点**（与 `handleSend` 门闠一致）。（**VX-A**：解锁阈值前移至 **N2** 后，「**`meta` 前**」字面不再与旧表一致；**仍**共用同一 **`sending` 变量**。若产品要求 **N2～N3 间隙内禁叹号**，需第二门闩 — **需产品签字** 后另开切片。）  
- **确认点 3（已定）**：`docs/contract.md` 采用 **「H5 实现说明」为主写清流中再 `send`**，并在 **`POST /api/chat/send` 语义摘要** 加 **半句** 说明「**多端并发连接时服务端仍以单用户代与打包调度为准、非双 LLM 并行**」，避免对接方误读（由 **S3** 落地时写入）。  
- **确认点 2（已定）**：**选项 α = N3** — 在 **收到 `meta`（节点 N3）之后** `sending=false`；若上线后体验仍不达标，**再评估** 选项 β（N2），见附录 **「演进策略」**。（**VX-A 已立项执行**：现网 H5 采用 **选项 β = N2** 解锁，见附录表与 **`contract.md`**。）  
- **确认点 4（已定）**：**选项 1** — **不设**上线前硬性埋点/量化达标线；是否启动 **N2** 小版本以 **产品与工单反馈** 驱动再议。（**已立项；VX-A 已交付（2026-04-15）**。）

#### 附录：`sending` 解锁时机（确认点 2 · 节点图与场景）

下列为 **同一次** `POST /api/chat/send`（msg1）从点击到流结束的一条时间轴；**竖线右侧**为「若在此刻之前 `sending` 仍为 true，则 **第二条 send / 叹号重发** 被挡住」的示意。

```text
  N0          N1              N2                         N3                    N4 …           Nk
  │           │               │                          │                     │              │
  ▼           ▼               ▼                          ▼                     ▼              ▼
用户点击    sending=true    HTTP 200 且               收到首条可解析         首条 delta      done / failed /
发 msg1     fetch 已发出    Content-Type 为            SSE：`type=meta`      （界面开始      连接结束
                            text/event-stream          含 generation_id      打字）          （VX-A：`sending=false`
                            （响应头已到，              （本代可判定）                          在 N2 首字节）
                            body 可读前或刚读）
```

| 节点 | 含义（客户端视角） | `sending`（当前/待改目标） |
|------|-------------------|---------------------------|
| **N0** | 用户点击发送 msg1 | 点击后即将 **true**（与现网一致） |
| **N1** | `fetch` 已发出，尚未收到响应 | **true** |
| **N2** | 已确认 **HTTP 成功** 且 **SSE Content-Type**；**响应体首包非空字节** 已读入 | **VX-A：`sending=false`（解锁点）**；此前为 true |
| **N3** | 已解析 **`meta`**，拿到 **`generation_id`** | **false**（与 N2 后一致）；**仅记录代**，不再负责改 `sending` |
| **N4…** | `delta` 流式输出中 | **false**（允许 msg2 / 叹号规则见确认点 1） |
| **Nk** | `done` / `failed` / 断流 | **false**（`handleSend` 末尾守卫仍可兜底） |

**场景 S-A（首包慢）**  
- **经过**：N2 已到，**N3 延迟**（弱网、网关缓冲）。  
- **用户动作**：想在「AI 还没出字」时就发 **msg2**。  
- **选项 α（N3 解锁）**：此窗口内 **`sending` 仍为 true** → **不能发** msg2、**叹号也不能**（确认点 1）。  
- **选项 β（N2 解锁）**：N2 后即 **`sending=false`** → **可发** msg2；**风险**：`generation_id` 未到时须仅靠 **Abort + session** 丢包，**实现与排错略复杂**。

**场景 S-B（已出字）**  
- **经过**：已过 **N3**，正在 **N4…** 流式。  
- **用户动作**：发 **msg2** 或点叹号。  
- **选项 α / β**：只要解锁点已过，**二者均允许**（仍受 **≤5 / 叹号例外** 约束）；**确认点 1** 下叹号与 send **同门闠**。

**场景 S-C（仅 JSON 错误、未进 SSE）**  
- **经过**：N1 后收到 **4xx/5xx 或 JSON 信封**（未形成 SSE）。  
- **建议**：**立即 `sending=false`**（与「流中再发」无关，属错误路径），避免卡死。

**已定稿（确认点 2）**  
- **采用**：**选项 α = N3** — 在 **N3（`meta`）之后** `sending=false`。  
- **原因**：与契约「**收到 `meta` 后记录 `generation_id`」**一致；与 **确认点 1**（`meta` 前不重发）**同一阈值**，状态机最简单。

**演进策略（不达标再评估 N2）**  
- **先上线 N3**（**确认点 4·选项 1**）：**不**预设埋点门槛或量化达标线；以 **工单与产品反馈** 判断 **S-A**（N2～N3 间隙过长）是否构成显著体验问题。  
- **若需升级到 β（N2 解锁）**：须单独立小版本：补 **N2～N3 间隙** 的 SSE 解析与 **Abort** 验收、**双连接** UI 用例、契约 **半句** 说明；**仍不改** 后端打包/代语义。  
- **VX-A（2026-04-15）**：**β（N2）** 已在 H5 落地；下列手工用例供回归勾选。

#### VX-A 手工用例（可勾选）

- [ ] **用例 1（双 Tab 并发发送）**：两窗口同一账号几乎同时点 **`send`**，确认仅一条进行中 AI、**Abort** 与 **`chatSendSession`** 行为符合预期，**`sending`** 不卡死。  
- [ ] **用例 2（N2 解锁后、`meta` 未到前点叹号）**：先有一条 **failed_** user 行带叹号，再 **`send`**，在 **首包已到达、尚未依赖 `meta` 出字** 的窗口内点叹号 — 记录 **允许 resend** 或 **101xx** 等与 **`contract.md`** 一致；若与产品预期不符 → **需产品签字** 是否加第二门闩。  
- [ ] **用例 3（Abort 后 `chatSendSession` 递增再发）**：超时或打断后 **`chatSendSession`** 已变，再次 **`send`** 正常、**`sending`** 不残留。

### 与任务 7 / 任务 9 / TD-020 的分工

- **任务 7（已完成）**：叹号、Abort、generation、幂等、≤5、重发、timeline 纠偏 — **勿回炉重造**，仅在本节 **增量调整 `sending` 与气泡生命周期**。  
- **任务 9 / TD-016（主交付已完成）**：`round_id`、按轮 `emotion_log`、Admin 情绪 Tab — **见任务 9 / `tech-debt.md` [TD-016]**；与本节 H5 增量 **可并行**；**勿把 `round_id` 写进本节 S1–S3 的必做前置**。  
- **TD-020（进行中 · V3-A）**：短期情绪 Redis **`user_emotion:{user_id}`** + DB **`user_short_term_emotion`**、读写边界 — **见 `tech-debt.md` [TD-020]** 与 **`docs/contract.md`**（无新 HTTP）。

---

## 小结（给 Plan 用的一句话）

**任务 1→8** 为 TD-015 **主链已交付**；**任务 9 / TD-016**（`round_id` + Admin 情绪 Tab）**已交付**；**后续里程碑**（H5 连发门闩 + 气泡 + 契约补充）与 **TD-020** 等为 **待排期或进行中增量**，实施时 **勿与主链重复开发**；检索改写 **TD-017** 仍不纳入本清单。