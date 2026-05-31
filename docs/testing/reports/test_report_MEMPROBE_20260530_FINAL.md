# 记忆检索与 Prompt 优化 · Docker 联调报告（最终版）

- **生成时间**：2026-05-30
- **探针 ID**：`20260530`
- **测试账号**：`e2emem20260530` / **user_id**：`7`
- **环境**：Docker Compose（`lxm_backend` + `lxm_mysql` + Redis），对话 `POST http://127.0.0.1:8000/api/chat/send`
- **Prompt 全量**：见同目录 [`test_report_MEMPROBE_20260530_prompt_full.md`](test_report_MEMPROBE_20260530_prompt_full.md)（约 2800 行，含 Step1.5/5/5.5/6/MemoryExtract 全文）
- **控制台日志**：[`test_run_MEMPROBE_20260530.log`](test_run_MEMPROBE_20260530.log)、[`prompt_trace_8rounds.log`](prompt_trace_8rounds.log)
- **HTTP 逐轮 SSE 明细**：[`test_report_MEMPROBE_20260530.md`](test_report_MEMPROBE_20260530.md)（续跑召回段）

---

## 一、测试结论汇总

| 用例 | 目标 | 存储是否写入 | 缓冲后召回（对话） | 结论 |
|------|------|--------------|-------------------|------|
| **1 称呼** | 昵称 + 真名 | ✅ `relationship.user_hobby_name` / `user_real_name` | ✅ 回复含「探针昵称20260530」 | **通过** |
| **2 饮食记忆** | 最爱山竹 | ✅ MySQL `memory` + Step6 DashVector `user_*_7` | ❌ 称「还不知道」 | **存储有、检索未注入 Prompt** |
| **3 过敏 bundled** | 菠萝过敏 | ✅ MySQL `memory`「用户对菠萝过敏」 | ❌ 称「还不知道」 | **同上** |
| **4 约定做事** | 后天看电影 | ❌ `future_action` 仍为 NULL；Step6 `future=cleared_*` | ❌ 回复「还没约过看电影」 | **未落 Future 槽；召回失败** |

**根因摘要（召回 2/3/4）**：

- 召回轮 **Step2 日志均为** `hits=0(... u=0)`，`user` 路虽执行但 **阈值 0.7 过滤后 0 条**（DashVector 常出现「共 N 条，过滤后 0 条」）。
- Step1.5 在 Prompt 追踪中能为水果/过敏/约定生成 **非空 `UserProfileQueryQuestion`**，但检索仍无命中 → 需排查 **key_l2 IN 过窄 / 向量相似度 / 旧文档字段**（见 TD-026）。
- **称呼**不依赖向量，走 `relationship` + **`user_nickname` 模块** → 召回成功。
- **约定**依赖 Step6 **Future 槽**；日志 `future=cleared_by_action_none` 或 `cleared_parse_failed`，`relationship.future_action` 为空。

---

## 二、写入阶段对话（HTTP，已落库）

以下为 `conversation_log`（user_id=7）摘录，证明四路写入 + 12 轮缓冲已执行。

| id | role | content（摘要） |
|----|------|-----------------|
| 694 | user | 你可以叫我【探针昵称20260530】，我的真名是【探针真名20260530】。 |
| 697 | user | 记住一下，我最爱吃的水果是【山竹探针_20260530】… |
| 700 | user | 我对菠萝过敏 + 以后推荐吃的要记住这点 |
| 703 | user | 我们约定…后天晚上八点…电影《探针电影_20260530》… |
| 706–737 | user/assistant | 缓冲 12 轮（嗯/好的/哈哈…） |

---

## 三、存储层验证（Docker MySQL）

### 3.1 relationship（称呼）

```
user_hobby_name = 探针昵称20260530
user_real_name  = 探针真名20260530
future_action     = NULL
future_timestamp  = NULL
```

### 3.2 memory 表（MemoryExtract 路径，非 Step6 向量主路径）

| id | content | source |
|----|---------|--------|
| 36 | 用户最爱吃的水果是山竹 | auto |
| 37 | 用户对菠萝过敏 | auto |

### 3.3 Step6 向量（backend 日志摘录）

- 写入阶段曾出现：`Step6 向量写入成功: doc_id=user_*_7, type=user`（多条）
- 部分轮次 `UserSettings` 为「无」整路跳过
- 召回相关轮次 Step2：`hits=0(cg=0 cp=0 ck=0 u=0)`

---

## 四、召回阶段（HTTP，缓冲后）

| 探针问题 | AI 回复要点 | 断言 |
|----------|-------------|------|
| 你还记得平时怎么叫我吗？ | 日常叫你「探针昵称20260530」 | ✅ |
| 我喜欢吃什么水果？ | 「还不知道呢…快告诉我」 | ❌ |
| 我有什么不能吃或要忌口的？ | 「还不知道呢」 | ❌ |
| 我们之前约过什么事？看电影… | 「还没约过看电影呢」 | ❌（修正：原脚本误把含「电影」判为通过） |

完整 SSE JSON 见 [`test_report_MEMPROBE_20260530.md`](test_report_MEMPROBE_20260530.md)。

---

## 五、Prompt 全量追踪说明

| 项 | 说明 |
|----|------|
| 首次 ASGI（宿主机） | 失败：宿主机 `.env` 连的 MySQL 与 Docker 不是同一套，`e2emem20260530` 不存在 |
| 二次 ASGI（**容器内** `python3 /app/mem_prd_docker_e2e.py --prompt-trace-only`） | ✅ 8 轮全文已写入 **`test_report_MEMPROBE_20260530_prompt_full.md`** |
| 与 HTTP 差异 | ASGI 段使用 **内存 Redis 桩 + 立即防抖**，链路语义与线上一致，Prompt/LLM 为真实调用 |

**Step1.5 召回水果轮示例（追踪日志）**：

```json
"UserProfileQueryQuestion": "用户最爱的水果是山竹，其他水果基本不吃的饮食偏好",
"UserProfileCandidateKeys": ["偏好-饮食", "偏好-口味", "习惯-饮食"]
```

**Step2 同轮**：`user_hits=0`，DashVector「共 3 条，阈值 0.70 过滤后 0 条」。

---

## 六、产物清单

| 文件 | 内容 |
|------|------|
| `test_report_MEMPROBE_20260530_FINAL.md` | 本文件（结论 + 证据索引） |
| `test_report_MEMPROBE_20260530.md` | HTTP 召回 SSE 明细 |
| `test_report_MEMPROBE_20260530_prompt_full.md` | 8 轮 Prompt + LLM 原始输出 |
| `test_run_MEMPROBE_20260530.log` | HTTP/续跑控制台 |
| `prompt_trace_8rounds.log` | 容器内 Prompt 追踪 backend 日志 |
| `scripts/mem_prd_docker_e2e.py` | 联调脚本（**仅新增**，未改 backend 业务代码） |

---

## 七、建议后续

1. **检索 0 命中**：对 user_id=7 在 DashVector 按 `type="user" AND user_id=7` 拉取 doc，核对 `key_l2` 与 query 相似度；必要时临时降 threshold 或关 key_l2 filter 做 A/B。
2. **Future 约定**：检查 Step6 输出 `future.action` / `future_time_natural` 是否被 LLM 填成「无」；解析「后天晚上八点」失败日志需对齐 `parse_future_time`。
3. **双写路径**：MySQL `memory` 已有山竹/菠萝，但主链 Prompt 的 `memory` 模块来自 **Step2 向量**；需确认产品是否要让 H5「记忆列表」与对话注入同源。

---

*本报告由 `scripts/mem_prd_docker_e2e.py` 自动生成并人工整理结论。*
