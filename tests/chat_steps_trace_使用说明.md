# 对话 Step 追踪脚本使用说明（集成测试）

测试脚本与产出默认放在 `**tests/**` 目录，与 `pytest`、`scripts/test_chat_e2e.py` 同属一体化验证范畴。

## 脚本位置

`scripts/chat_steps_trace_integration.py`

## 作用

- 使用 **ASGITransport** 在本进程内挂载真实 FastAPI 应用，串行发送 **5 轮**（可配置）用户消息。
- 通过包装 `**llm_client.chat_sync`** 与各 Step 入口函数，按步骤记录：
  - **Step1.5** 查询重写、**Step5** 主结构化对话、**Step5.5** 润色（若触发）、**Step6** 记忆编排、**MemoryExtract** 记忆提取等全部 **非流式 LLM** 调用的完整 Prompt 与原始输出。
  - **Step2** 多路向量检索：打印命中条数与是否降级（无 LLM）。
- 控制台输出风格对齐仓库根目录 `test_output.log`（分轮次、分步骤、`[成功]`/`[失败]`）。
- 运行结束后生成 Markdown 汇总：**默认** `tests/chat_steps_trace_report.md`（可用 `--output-md` 修改）。

## 运行条件

1. `**.env`** 中 MySQL、LLM、Embedding、DashVector 等配置可用（与线上一致）。
2. **数据库表结构必须与当前 ORM 一致**。若出现 `Unknown column 'xxx'`（如 `conversation_log.delivery_status`、`emotion_log.round_id` 等），需先执行迁移或补齐 DDL，否则 `/api/chat/send` 会在「步骤1 并行」失败，不会进入打包与 LLM，脚本将看不到任何 Step 调用。
3. 建议使用**独占测试库**，避免污染生产数据。
4. 测试账号：`e2e_test_user` / `pass1234`；若不存在会自动创建。

## 命令示例

```bash
cd 仓库根目录
PYTHONPATH=. python3 scripts/chat_steps_trace_integration.py

# 指定日志与报告路径（默认报告已在 tests/ 下）
PYTHONPATH=. python3 scripts/chat_steps_trace_integration.py \
  --output-log tests/chat_steps_trace_run.log \
  --output-md tests/chat_steps_trace_report.md

# 仅跑 3 轮、每轮结束后多等几秒再发下一条（便于异步 Step6 收尾）
PYTHONPATH=. python3 scripts/chat_steps_trace_integration.py --rounds 3 --post-round-sleep 6
```

## 实现说明（与线上差异）


| 项                         | 说明                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------- |
| 定时任务                      | 启动前桩掉 `backend.tasks.scheduler`，避免 lifespan 挂真实 APScheduler。                       |
| Redis                     | 使用内存桩满足 `chat:gen`、防抖键等；**与真实 Redis 行为可能略有差异**。                                    |
| 防抖                        | 将 `schedule_debounced` 替换为 **立即执行**打包任务，无需等待防抖窗口。                                  |
| Step6 / 记忆提取              | 仍为异步任务；脚本在每轮 SSE 结束后 `**sleep`** 一段时间，减少与下一轮交错，但不能 100% 保证顺序。                      |
| `POST /api/chat/send` 内并行 | 最近对话、情绪、Embedding、DashVector 预检索等 **未在脚本中单独立块打印**（若需可与旧版 test_output 一样再扩展 patch）。 |


## 输出物（默认位于 tests/）


| 文件                                                   | 说明                                            |
| ---------------------------------------------------- | --------------------------------------------- |
| 控制台 / `--output-log`                                 | 人类可读的逐步 Trace（含长 Prompt）。                     |
| `--output-md`（默认 `tests/chat_steps_trace_report.md`） | 汇总表 + 每轮各 Step 成功/失败统计（不含全文 Prompt，避免 MD 过大）。 |


---

`chat_steps_trace_report.md` 由脚本每次覆盖写入；本说明文件为固定文档，不参与覆盖。