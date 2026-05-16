# AI 日记运维说明

> 与 `**docs/diary-refactor-plan.md**`、`**docs/diary-refactor-decisions.md**`、**TD-013** 一致。

---

## 1. 发布 / 验收门禁（复制到发布 checklist 即可）

- **H5 对话须可用**：日记与对话共用 `**VOLC_`*** 与 `llm_client`。**若对话不可用，不验收日记生成阶段（TD-007 阶段 B/C）上线。**

---

## 2. 时间与「统计窗」口径（Asia/Shanghai）

- **APScheduler 的日记 Cron** 使用 **`Asia/Shanghai`**，**`generation_hour` / `generation_minute`** 与后台「日记规则」一致，表示**北京时间**触发点（默认建议 **0:15**）。
- **`DiaryService`**：批跑开始时取一次上海锚点日历日 **D**，对话统计窗为 **`[D−1 00:00, D 00:00)`**（上海）；入库字段 **`covers_beijing_date = D−1`**（北京日历日）。与 UTC 自然日无强制对齐要求。
- **运维排期**：沟通「凌晨任务」时请以 **北京时间** 理解日记任务。

---

## 3. 手动触发每日日记批跑（M2a / TD-013）

**适用**：宿主机休眠、misfire 日志、满足生成条件但未见新日记等。

**注意**：

- **同一覆盖日（`covers_beijing_date`，北京）**已为某用户生成过日记的，会**跳过**，不会同一天（覆盖日）插两条。
- **补跑语义（M1）**：手动执行时刻的锚点 **D = 当前上海日历日**，总结的是 **D−1** 的对话；**不能**通过该入口指定「漏跑的那一天」——晚几天补跑即总结「执行日的前一天」。
- 尽量避免与定时任务触发**同一时刻**并行执行（极端竞态下理论风险极低）。

**推荐命令**（与定时任务同源：`DiaryService.run_daily_diary_task`；仓库脚本 **`scripts/run_diary_batch.py`**，模块入口 **`python -m scripts.run_diary_batch`**）：

本地（项目根目录）：

```bash
PYTHONPATH=. python -m scripts.run_diary_batch
```

容器内（容器名以 `docker compose ps` 为准，示例为 `lxm_backend`；应用根目录一般为 `/app`）：

```bash
docker exec lxm_backend sh -c 'cd /app && python -m scripts.run_diary_batch'
```

- 上述示例为**静态命令**，勿与用户输入拼接进 shell。
- **备选**（与旧版等价，不推荐长期维护）：`docker exec` 内 `python -c '…'` 内联 `asyncio` + `async_session_maker` + `DiaryService.run_daily_diary_task()`，逻辑与上表一致。

---

## 4. 批跑「成功数为 0」或 LLM 失败排查

1. 看 `**logs/error.log`** / 容器 `docker logs lxm_backend` 是否含 `日记 LLM`、`LLM 非流式` 等错误。
2. 确认 `**.env` / 容器环境** 中 `**VOLC_`*** 与线上一致，容器可访问火山 **HTTPS**。
3. 确认用户是否满足 **PRD**：0 级不生成；1 级且**统计窗内**无互动不生成等。
4. 查 **火山配额 / 限流** 是否与对话侧同时异常。

---

## 5. 修改日记生成时刻后（H1 / TD-013）

- 后台保存 `generation_hour` / `generation_minute` 后，须 **重启 `lxm_backend`（或等价进程）**，新的 Cron 才会注册；**不支持**热更新调度。

---

## 6. Misfire 策略（已定案）

- **维持 APScheduler 默认** `misfire_grace_time` / `coalesce`，不额外调参；漏跑以 **本节第 3 条手动批跑** + 次日定时任务为主。若日后频繁 missed，再评估调参（见 `docs/diary-refactor-decisions.md` §6）。

---

*最后更新：2026-05-17*
