# 用户发一条消息：步骤化说明与 Prompt 结构

**最后更新**：2026-04-16  

本文档用与 `test_output.log`（集成测试脚本）**相同的「步骤1～步骤6」分段方式**描述链路，并补充 **线上 `POST /api/chat/send` 与脚本的差异**、**Prompt 七模块如何拼接**、**主要字段定义**。

---

## 1. 你看到的 `test_output.log` 在模拟什么

日志来自「独立脚本、不经过真实 SSE」的演练：每一轮对话会打印：

- `【用户输入】` / `【语意识别】`（脚本自己的语义说明，**不是**线上接口返回）
- **步骤1～6**：与「读库 → 检索 → 拼 Prompt → 安全 → LLM → 后置」的认知顺序一致，便于阅读
- **线上**同一轮对话里：部分内容在 `**POST /api/chat/send` 的同步段**执行，部分在 **防抖结束后的 `_execute_llm_bundle`** 执行，最后通过 **SSE** 把结果推给前端（见下文「对照表」）

---

## 2. 按日志风格拆解各步骤（含子项说明）

以下写法模仿 `test_output.log` 的层级（`------------------------------ 步骤N ...`、`[成功]` 行）。

### 轮次头（脚本独有）

```
============================== 第 N 轮对话 ===============================
【用户输入】……
【语意识别】……
```

- **含义**：脚本为可读性加的标题；线上 H5 没有「语意识别」这一 HTTP 字段。

---

### 步骤1 并行获取

```
------------------------------ 步骤1 并行获取 ------------------------------
  [成功] 最近对话
       共 20 条（DB 存 20 轮，Prompt 用最近 10 轮）
      [1] id=… 用户 | content=… | emotion=… | memory_injected=…条
      [2] id=… 林小梦 | content=…
      …
  [成功] 关系信息
       level=…, growth_value=…, last_interaction_at=…
  [成功] 情绪上下文
       label=…, confidence=…
  [成功] 用户 Embedding
       维度=1024
```


| 子项           | 数据来源 / 代码位置                                                                                                                          | 含义                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------- |
| 最近对话         | DB `conversation_log`，按时间取 **最多 20 条**，拼 Prompt 时取其中 **最后 10 轮**（user/assistant 成对语境）                                                | 模块 6「最近对话」的原始输入            |
| 关系信息         | DB `relationship`                                                                                                                    | 模块 3：等级名、行为边界、沉默天数修正       |
| 情绪上下文        | 脚本侧：与「`emotion_log` 最新一条」或短期情绪设计对齐；**线上打包 LLM** 用 `user_short_term_emotion_service.read_for_prompt`（Redis → DB 表 → `emotion_log` 兜底） | 模块 5：用户情绪 + AI 联动情绪 + 共情规则 |
| 用户 Embedding | 阿里云 embedding，向量维度 **1024**                                                                                                          | 步骤 2 向量检索的查询向量             |


**注意（线上与日志的差异）**：`POST /api/chat/send` 里曾 `gather` 最近对话、关系、`_get_latest_emotion` 等，但 **真正拼 Prompt 只在 `_execute_llm_bundle` 里重新拉取**；以代码为准时，**以打包阶段读到的为准**。

---

### 步骤2 向量检索

```
------------------------------ 步骤2 向量检索 ------------------------------
  [成功] 向量检索
       检索到 K 条（阈值>=0.7）
      [1] score=… | 记忆文本
      …
```


| 项         | 定义                                                                                       |
| --------- | ---------------------------------------------------------------------------------------- |
| 存储        | 长期记忆：**MySQL + DashVector**（检索走向量）                                                       |
| TopK      | **5**                                                                                    |
| 相似度阈值     | **≥ 0.7** 才作为相关记忆进入 Prompt                                                               |
| 写入 user 行 | `conversation_log.memory_injected`：JSON 列表，元素含 `content`、`score`（入队时按**当前句**检索结果写入，便于审计） |


---

### 步骤3 拼装 Prompt

```
--------------------------- 步骤3 拼装 Prompt ----------------------------
  [成功] Prompt 拼装
       总长度约 … 字符
      --- 完整 Prompt ---
      ……各模块正文……
      --- Prompt 结束 ---
```

见 **第 4 节「七模块如何拼凑」**。

---

### 步骤4 内容安全与人格风险

```
--------------------------- 步骤4 内容安全与人格风险 ----------------------------
  [成功] 内容安全
       is_safe=True, reason=
  [成功] 人格风险
       flag=False, type=None
```


| 子项   | 定义                                                                                                                                   |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 内容安全 | `check_content(用户原文)`；**不通过**则线上直接 **JSON 错误响应**（不会进入 SSE、不会插入 pending 消息）                                                           |
| 人格风险 | 关键词表 `PERSONA_RISK_KEYWORDS`：命中则 `persona_risk_flag=True` 并记录 `persona_risk_type`，写入 **本轮首条 user** 的 `conversation_log`（供统计「人格偏离率」等） |


**顺序说明**：`test_output.log` 里把「步骤4」放在 Prompt 之后，是脚本打印顺序；**线上**在 `POST /api/chat/send` 里是 **先做内容安全与人格标记，再落库 user 行并调度**，不会先把不安全内容拼进 Prompt。

---

### 步骤5 LLM 调用

```
----------------------------- 步骤5 LLM 调用 -----------------------------
  [成功] LLM 原始返回
       长度=… 字符
      --- LLM 原始输出 ---
      {"emotion": {"label": "…", "confidence": …}, "reply": "…"}
      --- 解析结果 ---
  [成功] emotion …
  [成功] reply …
```


| 项       | 定义                                                                        |
| ------- | ------------------------------------------------------------------------- |
| 调用方式    | **非流式** `chat_sync` → 整段 JSON 再解析（`llm_service.chat_with_parse_strict` 等） |
| 超时 / 重试 | 与配置 `get_llm_timeout_chat_seconds()` 一致；失败则 user 行进入「叹号」态等（见路由 `chat.py`） |
| 模型输出契约  | **仅允许**一个 JSON 对象，**不允许** JSON 外其它内容                                      |


**JSON 字段（模型必须遵守的形态）**：

```json
{
  "emotion": {
    "label": "开心|悲伤|焦虑|愤怒|孤独|疲惫|平静 之一",
    "confidence": 0.0
  },
  "reply": "给用户看的自然语言正文（业务上要求 1～3 短句、无 Markdown 列表等）"
}
```

- `emotion`：写入 `emotion_log`，并参与 Redis `ai_emotion:{user_id}`、短期情绪 `user_emotion:{user_id}` 等后置逻辑。
- `reply`：写入 `conversation_log`（`role=assistant`），并经 SSE 以 `delta` 切片形式下发（见步骤 7）。

---

### 步骤6 后台任务

```
------------------------------ 步骤6 后台任务 ------------------------------
  [成功] 后台任务
       conversation_log + emotion_log + 记忆提取 + 成长值 + Redis 已执行
```


| 任务（异步，不阻塞 SSE 首包之后的主体）                                | 作用                             |
| ----------------------------------------------------- | ------------------------------ |
| 更新 user 行 `delivery_status` 等                         | 标记本轮 user 已随 assistant 闭环      |
| 插入 `assistant` 行、`emotion_log`                        | 持久化 AI 回复与本轮情绪                 |
| `memory_service.extract_and_save`                     | 从「用户多句 + 林小梦回复」抽记忆，写长期记忆       |
| `RelationshipService.add_growth` 等                    | 成长值（如有效对话 +2，有日上限等）            |
| Redis `ai_emotion:{user_id}`                          | 展示态：本轮 LLM 情绪 JSON             |
| `user_short_term_emotion_service.persist_after_round` | Prompt 用短期情绪：Redis + DB upsert |


---

### 步骤7（线上独有，日志脚本不打印）：SSE 推送

线上在 **同一次** `POST /api/chat/send` 上保持 **HTTP 长连接**（`text/event-stream`）：

1. **首包** `type: meta`，带 `generation_id`（与 Redis `chat:gen:{user_id}` 对齐，防串代）
2. 等待打包 LLM 完成（进程内 `Future` + 超时，约 55s 量级）
3. **成功**：多个 `type: delta`，`content` 为 `reply` 的**小切片**（模拟流式）；最后 `type: done`，带 `emotion`
4. **失败**：`type: failed`（`code`、`message`）；**代次作废**：`type: obsolete`

**SSE 事件字段（与 `schemas/chat.py` 及实现一致）**：


| `type`     | 主要字段                                            | 含义        |
| ---------- | ----------------------------------------------- | --------- |
| `meta`     | `generation_id: string`                         | 本连接对应的代次  |
| `delta`    | `content: string`（实现里可带 `generation_id` 做丢弃过期包） | 正文增量      |
| `done`     | `emotion: { label, confidence }`                | 结束        |
| `failed`   | `code`, `message`                               | 错误        |
| `obsolete` | （无额外字段）                                         | 本代已被新发送作废 |


---

## 3. 线上 `POST /api/chat/send` 与「步骤1～6」的对照


| 测试日志步骤                   | 线上发生位置                                              | 说明                                                                    |
| ------------------------ | --------------------------------------------------- | --------------------------------------------------------------------- |
| 步骤1 一部分                  | `send` 内 `gather`（部分结果未用于拼 Prompt）                  | 与脚本「并行获取」类似，但线上以 **bundle 内** 为准                                      |
| 步骤1 完整 + 步骤2 + 步骤3 + 步骤5 | 防抖后的 `_execute_llm_bundle`                          | 未闭环 user 打包、再 embedding、再检索、再 `PromptBuilder.build_chat_prompt`、再 LLM |
| 步骤4                      | `send` 内、**落库前**                                    | 内容安全 + 人格风险                                                           |
| 步骤5 结果对外                 | `StreamingResponse` + `_sse_chat_wait_bundle`       | 先 `meta`，等 Future，再 `delta`/`done`                                    |
| 步骤6                      | `_post_bundle_success_tasks`（`asyncio.create_task`） | LLM 成功落库后触发                                                           |


**额外线上环节（日志不展开）**：

- **代次** `generation_id`：换新代时作废旧 `Future`，防止旧 SSE 吃到新结果。
- **防抖** `schedule_debounced`：短时间多条 user 合并进一次 LLM（`user_input` 可为多行）。
- **队满**：未闭环 pending 过多且无叹号时拒绝新 `send`（错误码见 `constants`）。

---

## 4. Prompt 七模块如何拼凑

实现：`backend/services/prompt_builder.py` 中 `PromptBuilder.build_chat_prompt`。

### 4.1 模块顺序与分隔符

模块按固定顺序用 `**\\n---\\n`**（常量 `MODULE_SEPARATOR`）连接为**一整段字符串**：


| 顺序  | 模块                                  | 代码中的预算（Token，tiktoken 近似） | 是否参与超限裁剪                     |
| --- | ----------------------------------- | ------------------------- | ---------------------------- |
| 1   | System                              | ≤ 400                     | **不裁剪**                      |
| 2   | Persona（`【人格设定】` + Redis/DB/默认五层人格） | ≤ 600                     | **不裁剪**                      |
| 3   | Relationship（`【关系状态】`）              | ≤ 200                     | 一般不裁（总超限时策略见下）               |
| 4   | User Memory（`【用户记忆】`）               | ≤ 500                     | **可裁**（优先级 **2**）            |
| 5   | Emotion（`【情绪状态】`）                   | ≤ 150                     | 一般不裁                         |
| 6   | Recent Chat（`【最近对话】`）               | ≤ 1000                    | **可裁**（优先级 **1**，从**最早**轮删起） |
| 7   | User Input（`【用户消息】`）                | ≤ 500                     | 一般不裁                         |


**总预算**：整段 Prompt 估算 **≤ 4096 Token**（`MAX_TOTAL_TOKENS`）。超限时：**先删最近对话中的最早若干条**，仍超再 **从记忆列表尾部删**（相似度最低的先删）；**绝不删 System、Persona**。

### 4.2 各模块标题与内容要点（字段级）

**模块 1 - System**（固定文案摘要）

- 身份禁区、回复格式（1～3 短句、禁止列表/Markdown）、共情原则
- **结构化输出指令**：要求只输出 JSON：`emotion.label` 从固定 7 类中选、`confidence` 小数、`reply` 字符串

**模块 2 - Persona**

- 前缀：`【人格设定】`
- 正文：Redis `active_config:persona` → 未命中则 DB `admin_config` `config_key=persona` 且生效 → 再未命中用代码内 `DEFAULT_PERSONA`

**模块 3 - Relationship**

- `当前关系等级`：`LEVEL_DEFINITIONS` 中 0～3 对应 **陌生 / 朋友 / 亲密 / 知己**
- `语气与行为边界`：同上表中的 `behavior` 文案
- **沉默修正**（由 `last_interaction_at` 与当前 UTC 算天数）  
  - 8～14 天：追加「用户最近有些沉默…」类指令  
  - ≥15 天：追加「久别重逢…」类指令

**模块 4 - User Memory**

- 无记忆：`【用户记忆】\\n暂无用户相关记忆`
- 有记忆：多行 `你记住：{content}`（`memories` 列表顺序与检索一致；裁剪时从列表末尾删）

**模块 5 - Emotion**

- 无上下文：`用户情绪：未知` 等兜底句
- 有 `emotion_context`：`用户当前情绪`、`AI联动情绪`（`EMOTION_MAPPING`：如悲伤→担心、平静→保持当前情绪）、`共情规则`（`EMPATHY_RULES`）

**模块 6 - Recent Chat**

- 每行：`用户：{content}` 或 `林小梦：{content}`（`role` 映射）

**模块 7 - User Input**

- 前缀：`【用户消息】`
- 内嵌说明：以下可能为**多段合并**（换行分隔），模型需综合理解，**仍只输出一个 JSON**
- 正文：`user_input` 原文（或打包后的多行字符串）

### 4.3 与 `test_output.log` 中「--- 完整 Prompt ---」的对应关系

日志里出现的块标题顺序即为：

`System 规则段` → `---` → `【人格设定】` → `---` → `【关系状态】` → `---` → `【用户记忆】` → `---` → `【情绪状态】` → `---` → `【最近对话】` → `---` → `【用户消息】`

---

## 5. 主要数据结构速查

### 5.1 `POST /api/chat/send` 请求体（`ChatSendRequest`）


| 字段                  | 类型      | 约束           | 说明              |
| ------------------- | ------- | ------------ | --------------- |
| `content`           | string  | 必填，1～2000 字符 | 用户消息正文          |
| `client_message_id` | string? | 最长 64        | 客户端幂等键（可选，契约预留） |


### 5.2 `conversation_log`（与本链路强相关字段）


| 字段                                        | user 行典型值                                      | assistant 行 |
| ----------------------------------------- | ---------------------------------------------- | ----------- |
| `role`                                    | `user`                                         | `assistant` |
| `content`                                 | 用户原文或打包中的一段                                    | `reply`     |
| `sort_seq`                                | 时间序排序                                          | 新序          |
| `delivery_status`                         | `pending_llm` → 成功后 `delivered`；失败为 `failed_`* | 一般为空        |
| `memory_injected`                         | JSON：检索快照 `[{content, score}, …]`              | 视实现         |
| `persona_risk_flag` / `persona_risk_type` | 关键词检测结果                                        | -           |
| `skipped_in_prompt`                       | 未进入本轮 pack 的 user 行为 true                      | -           |
| `round_id`                                | 闭环成功时同一轮 user/assistant 共享                     | 同左          |


### 5.3 情绪相关字典（Prompt / 后置）


| 名称                                  | 形状                                             | 用途                          |
| ----------------------------------- | ---------------------------------------------- | --------------------------- |
| `emotion_context`（PromptBuilder 参数） | `{"label": str, "confidence": float}` 或 `None` | 模块 5                        |
| LLM 输出 `emotion`                    | 同上                                             | `emotion_log`、Redis、短期情绪持久化 |
| Redis `user_emotion:{user_id}`      | JSON 字符串，同上结构                                  | 短期情绪热读                      |


---

## 6. 主动消息（扩展阅读）

主动消息使用 `**build_active_message_prompt`**：模块 5 改为情绪历史文案，模块 7 改为 `ACTIVE_TRIGGER_INSTRUCTIONS`（P0～P4）+ JSON 输出说明。与 H5 主对话 **路径不同**，不在本日志「每轮 send」内展开。

---

## 7. 参考文件


| 内容           | 路径                                                    |
| ------------ | ----------------------------------------------------- |
| 发送、打包、SSE、落库 | `backend/routers/chat.py`                             |
| 七模块与裁剪       | `backend/services/prompt_builder.py`                  |
| 防抖与代次 Redis  | `backend/services/chat_queue_service.py`              |
| 短期情绪读写       | `backend/services/user_short_term_emotion_service.py` |
| 请求/事件模型      | `backend/schemas/chat.py`                             |
| 测试日志风格来源     | `test_output.log`（仓库根或运行输出）                           |


