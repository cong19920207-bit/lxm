# AI 日记运维说明

> 与 `**docs/diary-refactor-plan.md**`、`**docs/diary-refactor-decisions.md**`、**TD-013** 一致。

---

## 1. 发布 / 验收门禁（复制到发布 checklist 即可）

- **H5 对话须可用**：日记与对话共用 `VOLC_`* 与 `llm_client`。**若对话不可用，不验收日记生成阶段（TD-007 阶段 B/C）上线。**

---

## 2. 时间与「今日」口径（UTC）

- **APScheduler 的 Cron** 与 `**DiaryService` 内「今日是否已生成 / 当日对话」**均以 **UTC** 为准，直至全项目统一业务时区。
- 运维排期、值班沟通时**勿按仅本地时区**理解「凌晨任务」。

---

## 3. 手动触发每日日记批跑（M2a / TD-013）

**适用**：宿主机休眠、misfire 日志、满足生成条件但当日未见新日记等。

**注意**：

- **同一 UTC 自然日**已为某用户生成过日记的，会**跳过**，不会同一天插两条。
- 尽量避免与定时任务触发**同一时刻**并行执行（极端竞态下理论风险极低）。

**命令**（容器名以 `docker compose ps` 为准，示例为 `lxm_backend`）：

```bash
docker exec lxm_backend sh -c 'cd /app && python -c "
import asyncio
from backend.database import async_session_maker
from backend.services.diary_service import DiaryService

async def run():
    async with async_session_maker() as db:
        svc = DiaryService(db)
        await svc.run_daily_diary_task()

asyncio.run(run())
"'
```

- 示例为**静态命令**，勿与用户输入拼接进 shell。
- 若 `asyncio.run` 在特殊环境报错，可改为在容器内执行独立 `.py` 脚本。

---

## 4. 批跑「成功数为 0」或 LLM 失败排查

1. 看 `**logs/error.log`** / 容器 `docker logs lxm_backend` 是否含 `日记 LLM`、`LLM 非流式` 等错误。
2. 确认 `**.env` / 容器环境** 中 `**VOLC_`*** 与线上一致，容器可访问火山 **HTTPS**。
3. 确认用户是否满足 **PRD**：0 级不生成；1 级且无当日（UTC）互动不生成等。
4. 查 **火山配额 / 限流** 是否与对话侧同时异常。

---

## 5. 修改日记生成时刻后（H1 / TD-013）

- 后台保存 `generation_hour` / `generation_minute` 后，须 **重启 `lxm_backend`（或等价进程）**，新的 Cron 才会注册；**不支持**热更新调度。

---

## 6. Misfire 策略（已定案）

- **维持 APScheduler 默认** `misfire_grace_time` / `coalesce`，不额外调参；漏跑以 **本节第 3 条手动批跑** + 次日定时任务为主。若日后频繁 missed，再评估调参（见 `docs/diary-refactor-decisions.md` §6）。

---

*最后更新：2026-04-07*