# diary 技术债

- 文档 ID：`tech-debt-diary`
- 权威状态：`canonical`
- 功能范围：`diary`
- 必读依赖：无
- 相关技术债：`TD-006`, `TD-007`, `TD-013`, `TD-014`, `TD-018`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-006] 日记历史接口已具备，管理列表页待建 — **已清偿（2026-04-07）**

- **位置**：`backend/routers/admin/relationship_mgmt.py` → `GET /api/admin/diary-history`；**`admin/pages/diary-history.html`**；`admin/static/js/admin-api.js` → **`MENU_CONFIG.super_admin` / `ops_admin`** 菜单项 **`diary-history`**。
- **接口**：**GET** `/api/admin/diary-history`（Query 不变）；鉴权 **`super_admin` / `ops_admin`**（O1，不扩 `ai_trainer`）。
- **当前处理**：列表页对接接口；表格 **`content`** 使用 **`escapeHtml`**；`diary-rules.html` 内历史链接对已授权角色可用。契约见 **`docs/contract.md`**「`admin/pages/diary-history.html`」。

### [TD-007] 日记规则（diary_rules）已入库但生成链路未读取 — **已清偿（2026-04-07）**

- **配置**：`admin_config.diary_rules`；发布后 Redis `active_config:diary_rules`；PUT 支持 **`prompt_with_interaction` / `prompt_without_interaction`**，兼容仅存 **`generation_prompt`** 的旧 JSON。
- **当前处理**：
  1. **`backend/services/diary_rules_loader.py`**：解析、校验、`max_length` / 时刻越界回退 **0:30 UTC**、Prompt 缺省回退内置模板；供 **`DiaryService`** 与 **`main.py` lifespan** 共用。
  2. **`DiaryService.generate_diary_for_user`**：保留等级 / **覆盖日（北京）**已生成 / 1 级无互动等 **early-return**；按 **`has_interaction`** 选模板；**`fill_diary_prompt_template`** 替换占位符（含 **`covers_date_label_zh`**）；**`max_length`** 写入 Prompt 与截断；LLM 失败或空内容时 **硬编码模板重试**；**不对日记正文做 `check_content`**。
  3. **`scheduler.start_scheduler(diary_hour, diary_minute)`**：日记任务 **`CronTrigger` 使用 `ZoneInfo("Asia/Shanghai")`**；启动前 **`await get_scheduled_diary_cron_times()`**。**改时刻须重启 backend**（TD-013）。
- **管理端**：`diary-rules.html` 双 Prompt + 北京时间时/分；顶栏已定案短句。契约与运维见 **`docs/contract.md`**、**`docs/ops-diary.md`**。

### [TD-013] 日记调度：Cron 热更新未做 + misfire 补跑仅运维手动（M2a）

- **决策来源**：`docs/diary-refactor-decisions.md`（2026-04-07）。
- **子项 A — 与 TD-007 配套**：`diary_rules` 中 `generation_hour` / `generation_minute` 接入后，**修改触发时刻须重启 `lxm_backend`（或等价进程）** 后 APScheduler 才按新 Cron 注册；**不实现**运行中热更新 Trigger（后续若做再关闭本条子项）。
- **子项 B — misfire 补跑**：APScheduler **missed** 导致当日批跑未执行时，**当前约定**通过 **`docs/ops-diary.md`** §3：推荐 **`python -m scripts.run_diary_batch`**（与 `run_daily_diary_task` 同源），或容器内等价 **`docker exec … python -m scripts.run_diary_batch`**；**无**管理端按钮、**无**受控 HTTP API。后续若增加 super_admin 触发接口 + 限频 + 审计，再在本条标注升级或拆条。
- **当前处理（2026-04-16）**：待处理原第 1 点已由 **`docs/ops-diary.md`** §3 承接（可复制命令与环境注意）；仓库脚本 **`scripts/run_diary_batch.py`**（2026-05-17）。
- **待处理**：
  1. ~~在 `README` 或 `docs/` 运维小节写入 **可复制的 docker exec 命令** 与环境前提（`.env` / 网络）。~~ **已完成**：见 **`docs/ops-diary.md`** §3；是否在根 **`README`** 再挂入口链接可按团队习惯选做。
  2. （可选）实现热更新 Cron、（可选）实现 M2b 手动触发 API。
- **风险等级**：**低**（运维可接受手动补跑时，对线上功能无逻辑缺口；主要风险是「无人知会补跑」导致当日无日记）

### [TD-014] H5 日记列表误用 `diaries`，与契约 `items` 不一致 — **已清偿（2026-04-07）**

- **位置**：`frontend/pages/diary.html` → **`loadDiaries`** 仅使用 **`res.data.items`**；`code≠0` 或缺 `data` 时不翻页；**`noMore`** 按 `total` 与 **`page_size`** 契约判断；首屏失败 **`showToast`**。
- **关联**：`docs/diary-refactor-decisions.md` §2、§3；`docs/contract.md` H5 日记列表。

### [TD-018] 日记「当日有互动」与仅失败 / 未闭环 user 行语义（**待清偿**）

- **背景**：`DiaryService._get_today_conversation_summary`（`backend/services/diary_service.py`）在当日存在**任意** `conversation_log` 时即 `has_interaction=True`，摘要拼接最多 5 条 user 内容。TD-015 后 **user 更早落库**，可能出现**当日仅有失败/未闭环 user、无成功 assistant**，仍判定「有互动」并走**有互动**日记分支，与部分用户/运营直觉可能不一致。
- **当前处理（2026-04-09）**：产品选择 **G1 — 维持现网语义**，**不**在 TD-015 首版同步改日记判定。
- **待处理**：评估是否改为「至少存在一轮成功闭环（或等价 `delivery_status` / 存在 assistant）」再判 `has_interaction`；若改，联动日记规则文案、`generate_diary_for_user`、**`docs/contract.md`** 日记模块说明与 E2E。
- **触发时机**：上线后反馈「无 AI 回复日仍显示有互动日记」或数据质检提出时排期。
- **风险等级**：**低**（体验与口径，非安全）
- **关联**：`docs/admin-conversations-extension-analysis.md` 确认点 G（已定稿 G1）。
