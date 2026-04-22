# AI 日记详细修复方案

> **决策依据**：`docs/diary-refactor-decisions.md`  
> **技术债映射**：TD-014（H5）、TD-007 + TD-013（生成与调度）、TD-006（后台历史）、TD-013（运维文档）  
> **审查**：本文已纳入「需求对齐 / 兼容性 / 逻辑 / 安全 / 上线」等审查结论（见 **§〇**）。

---

## 〇、需求对齐检查结论（已纳入本方案）

### 0.1 内容安全是否与对话一致（**已定案**）

- **现状**：`chat.py` 对用户输入走 `check_content`；`diary_service.py` 在 LLM 输出后**仅截断**。
- **已定案（`docs/diary-refactor-decisions.md` §6）**：**选项 A**——日记 LLM 产出**不做**独立 `check_content`；契约/PRD 已备忘（见 `docs/contract.md`）。阶段 B **不实现**对话侧同款安全步骤。

### 0.2 业务分支与 PRD（**风险：高**，误改易错生成/漏生成）

- PRD 规则已在 `generate_diary_for_user` 中实现：**0 级不生成**、**1 级且无当日互动不生成**、**≥2 无互动可生成想念向**、**当日已有一条则跳过**等 **early-return 必须保留**。
- **硬性条款（阶段 B）**：**禁止**仅替换 Prompt 而删除或合并这些分支。正确顺序为：**先**完成等级 / 当日是否已有日记 / `has_interaction` 等判定与 **early-return**，**再**在各**已命中的分支内**组装「来自 `diary_rules` 的模板与占位符」或回退硬编码文案。
- **测试清单**须包含：**0 级跳过**、**1 级无当日互动不生成**（见 §四）。

### 0.3 笔误修正

- 原验收写「手动验证（阶段 D）」**错误**；阶段 D 为后台历史页。**与调度无关**的生成内容验证应在 **阶段 B 完成后**即可用手动 `generate_diary_for_user` 验证，**不依赖阶段 D**。

### 0.4 与现有接口

- `GET /api/diary/list` 已 `model_dump()` 输出 `**items`**，与 `docs/contract.md` 一致；阶段 A 仅前端，无破坏性 API 变更。契约已注明后端**从不**返回 `diaries` 键（见 `docs/contract.md` H5 日记模块）。

### 0.5 读取配置 API

- 真实签名为：`await admin_config_service.get_active_config(config_key: str, *, use_cache: bool = True)`。**无** `get_active_config("diary_rules", ...)` 的额外位置参数；`DiaryService` 内必须使用 `**await`**。
- 首版默认 `**use_cache=True`**，与 `publish_config` 写 Redis 行为一致即可。**可选优化**（非首版必选）：批跑内对同一规则只解析一次，或争议场景下 `use_cache=False`，在方案外单独立项。

### 0.6 阶段 A 分页与错误（**风险：中**）

- `res.code !== 0`：**不得**继续触底累加；应 Toast/提示并保持当前列表状态。
- `total` 缺失或非数字时：**勿**用 `totalLoaded + items.length >= total`（易 **NaN**）；回退策略：**本页 `items.length < (res.data.page_size || 20)` 则 `noMore = true`**。

### 0.7 UTC 与运维心智（**风险：中**）

- **APScheduler Cron** 与 `**DiaryService` 内「今日」**均以 **UTC** 为准，与现网 Docker 日志中 UTC 表现一致；直至「服务器/业务时区统一」改造前，**阶段 C、阶段 E** 须在文档中显式写出，避免值班按仅本地时间理解「凌晨任务」。

### 0.8 `generation_hour` 脏数据

- 管理端 PUT 校验 **0–5**；若库中被手工写成越界值，启动读配置时应 **clamp 或与 PUT 同等校验后回退 0:30**，并 **warning** 日志，与「合法保存进不来」区分。

### 0.9 管理端 XSS（**风险：中**）

- 阶段 D 列表/详情渲染 `content` 前须 `**escapeHtml`**（或与 `system-logs.html` 同源模式），避免特殊字符破坏 DOM。

### 0.10 B 与 C 共享配置解析（**风险：低**）

- 建议抽取 `**diary_rules_loader`（或等价）**：「读配置 + 校验 + 回退默认值」供 **DiaryService** 与 **start_scheduler** 共用，避免两处 JSON 解析不一致。

### 0.11 手动批跑与定时重叠（**风险：低**）

- 依赖 DB「当日已有一条则跳过」；极端竞态下理论双插概率极低。运维文档写明：**尽量避免与 Cron 触发窗口重叠**；若未来要强保证，再议 DB 唯一约束（超出本方案）。

### 0.12 上线与回滚（**风险：低**）

- **推荐顺序**：**先 A**（可独立发布，有数据即可修复空白列表）→ **B+C 合并**并**计划一次 backend 重启** → **D、E** 可与 D 并行。  
- **回滚**：前端回滚 `diary.html`；后端回滚硬编码 Prompt/调度；**无**表结构迁移。

### 0.13 其它低优先级

- 性能：批跑时长与 `level≥1` 用户数、LLM 超时相关；规模变大时再议队列/分批（非本次必须）。  
- 阶段 E 示例：**容器名以 `docker compose ps` 为准**；`asyncio.run` 适用于一次性 `docker exec` 进程；示例保持静态，**勿**与用户输入拼接进 shell。  
- 实现后：**阶段 D 验收**须含按 docup **更新 `docs/contract.md`**（如 `diary-history.html` 页面约定）及 **tech-debt TD-006 清偿标注**。

---

## 一、目标与范围


| 目标   | 说明                                                                                   |
| ---- | ------------------------------------------------------------------------------------ |
| 用户可见 | H5 正确展示 `GET /api/diary/list` 返回的日记，支持分页与已读                                          |
| 配置生效 | `DiaryService` 使用 `admin_config` 中已发布的 `**diary_rules`**（双字段 Prompt、字数、截断策略）         |
| 调度一致 | 每日批跑触发时刻与 `**generation_hour` / `generation_minute`** 一致；**改时刻后须重启 backend**（TD-013） |
| 运营可查 | `super_admin` / `ops_admin` 在后台分页查看日记历史（TD-006）                                      |
| 运维可补 | 文档化 **misfire / 漏跑** 时的手动批跑命令（TD-013 M2a）                                            |
| 合规对齐 | **§〇.1 已定案 A**（日记不做独立内容安全）                                                           |


**不在本次必须范围**：Cron 热更新、管理端「一键触发生成」API、业务日界从 UTC 改为国内日、TD-012 第三方 doubao 运行时读库、DB 唯一约束防竞态（除非产品要求）。

---

## 二、前置条件

1. **环境**：Docker 中 `lxm_backend` 可访问火山 API；H5 对话已稳定（与日记同源 `VOLC_*`）。**若对话不可用，不进入 B/C 的上线验收**（与对话同源门禁）。
2. **数据**：库内存在 `admin_config` 中 `config_key=diary_rules` 的**已发布**行；若无，需先在后台「日记规则」保存一次或种子数据。
3. **契约**：实现后与 `docs/contract.md` 中 H5 `/api/diary`、管理端 `diary-history` / `diary-rules` 小节对齐；阶段 D 交付时**必更**契约中后台页面约定（见 §〇.13）。

---

## 三、分阶段任务

### 阶段 A — H5 日记列表（TD-014，优先）

**问题**：`frontend/pages/diary.html` 使用 `res.data.diaries`，后端仅返回 `data.items`。

**改动要点**：

1. `loadDiaries` 内：`const items = res.data.items || []`（**不**再读 `diaries`）。
2. `**res.code !== 0`**：提示错误，**不**增加 `totalLoaded`、**不**错误翻页。
3. **「没有更多」**：在 `code === 0` 且数据可靠时：
  - 若 `total` 为有效数字：`totalLoaded + items.length >= total` → `noMore`；
  - 若 `total` 缺失/非法：回退 `**items.length < (page_size 或 20)`** → `noMore`（见 §〇.6）。
4. 变量命名：`diaries` → `items`（或 `list`），后续 `forEach` 一致。
5. **回归**：`initDiary` 已请求 `GET /api/relationship/status` 并写 `localStorage`，空状态逻辑可保持不变。

**验收**：

- 登录有日记用户：列表出现卡片，展开可标已读。
- 无日记用户：空状态与等级一致。
- 多页：触底加载直至 `noMore`；接口失败时不出现 NaN 或死循环加载。

**涉及文件**：`frontend/pages/diary.html`（必要时核对 `frontend/static/js/api.js` 无需改）。

---

### 阶段 B — 生成链路读取 `diary_rules`（TD-007）

**问题**：`backend/services/diary_service.py` 内 Prompt、字数提示、截断等硬编码，未读配置。

**改动要点**：

1. **业务顺序（硬性）**：**不得**改动或绕过现有 **level / 当日已生成 / has_interaction** 等分支与 **early-return**（§〇.2）。仅在进入「允许生成」分支后，用配置化文案替换原硬编码 Prompt 组装逻辑。
2. **读取配置**：`await admin_config_service.get_active_config("diary_rules", use_cache=True)`（单例 `admin_config_service`，**必须 await**；签名见 §〇.5）。
3. **解析结构（与契约 / `DiaryRulesRequest` 同步改造）**：**已定案**以 `**prompt_with_interaction`**、`**prompt_without_interaction`**、`max_length`、`frequency`、`generation_hour`、`generation_minute` 为权威字段；不再以单一 `generation_prompt` 为唯一来源。若已发布 JSON 仍只有旧键 `**generation_prompt**`，须在 loader 内 **兼容**（例如：两新字段均缺时，有/无互动分支暂用同一旧文案，或后台引导重新保存一次）——具体策略在开发任务中写明并加日志。
4. **模板选用**：按 `has_interaction` 在 `prompt_with_interaction` / `prompt_without_interaction` 中择一，再替换占位符；与后台双框、`PUT /api/admin/diary-rules` 同时上线，避免半套 API。
5. **字数与截断**：LLM 要求中的字数上限使用配置 `**max_length`**；后处理截断与 `max_length` 挂钩（如 `max_length + 冗余`），注释说明与旧 400/600 对应关系。
6. **回退**：配置为空、JSON 非法、必填缺失时，**整段回退**当前硬编码 Prompt + 原默认字数/截断，**warning** 日志。
7. **内容安全**：按 **§〇.1 已定案 A**，不对日记正文做 `check_content`。

**验收**：

- **阶段 B 完成后**即可用手动 `generate_diary_for_user`（测试用户）验证内容与字数；**不依赖阶段 D**。
- 修改后台 `diary_rules` 后（配合 B 已上线），生成内容贴近新配置；配置故意损坏时回退路径可生成。
- **阶段 C 上线并重启后**，批跑时刻与配置一致（与 B 正交）。

**涉及文件**：`backend/services/diary_service.py`；**推荐**新增 `backend/services/diary_rules_loader.py`（或等价）供 **阶段 B 与 C 共用**（§〇.10）。

---

### 阶段 C — 调度时刻读配置（TD-007 + TD-013）

**问题**：`backend/tasks/scheduler.py` 写死 `CronTrigger(hour=0, minute=30)`。

**改动要点**：

1. **UTC 说明**：Cron 触发时间与 `DiaryService` 的「今日」均为 **UTC**（§〇.7）；文档与运维须知一致写出。
2. **启动时**读取生效 `diary_rules` 的 `generation_hour`（合法范围与 PUT 一致 **0–5**）、`generation_minute`（**0–59**）。**越界或非法**时 **clamp/回退 `0:30 UTC`** 并 **warning**（§〇.8）。
3. **与 FastAPI 生命周期衔接**：`lifespan` 内 `**await`** 读配置后再 `start_scheduler(hour, minute)`，避免同步上下文滥用 `asyncio.run`。
4. **TD-013**：不做热更新；`**diary-rules` 保存后须重启 `lxm_backend`** 才应用新时刻。`diary-rules.html` 保存成功 Toast 或横幅提示（清偿 TD-007 后更新横幅文案，避免仍写「未读配置」）。

**验收**：

- 改 `generation_hour/minute`，重启容器后，`docker logs` 中调度 **next run** 与配置一致（UTC）。
- 非法配置回退 0:30，服务可启动。

**涉及文件**：`backend/tasks/scheduler.py`、`backend/main.py`（`lifespan`）、可选 `diary_rules_loader.py`、`admin/pages/diary-rules.html`。

---

### 阶段 D — 管理端日记历史（TD-006）

**问题**：`GET /api/admin/diary-history` 已实现，无页面与菜单。

**改动要点**：

1. **新建** `admin/pages/diary-history.html`（风格对齐 `users.html` / `memory-rules.html`：顶栏、`renderSidebar`、`adminRequest`）。
2. **菜单**：仅在 `**MENU_CONFIG.super_admin`** 与 `**MENU_CONFIG.ops_admin`** 中增加一项（如 `key: 'diary-history'`，`href: 'diary-history.html'`）；**不**给 `ai_trainer`（决策 O1）。
3. **接口**：`GET /api/admin/diary-history`，Query 与现后端一致；`data.list[]` 字段：`id`、`user_id`、`content`、`relationship_level_at_creation`、`is_read`、`created_at`。
4. **交互**：筛选、分页、日期格式错误提示；空列表与加载失败与同类页一致。
5. **XSS**：`content` 展示前 `**escapeHtml`**（或与 `system-logs.html` 一致）（§〇.9）。
6. **规则页链接**：`diary-rules.html` 已按决策 **§6** 为 **super_admin / ops_admin** 预留入口（现网多为 super 可见）；若与最终实现不一致再对齐。

**验收**：

- 两角色登录可见菜单并可分页浏览；`ai_trainer` 无菜单且直链 403。
- **按 docup 更新 `docs/contract.md`**（`diary-history.html` 页面与接口消费约定）；**更新 `docs/tech-debt.md` TD-006 状态**（清偿后按团队惯例标已修复或删行）（§〇.13）。

**涉及文件**：`admin/pages/diary-history.html`（新）、`admin/static/js/admin-api.js`、`admin/pages/diary-rules.html`（可选）。

---

### 阶段 E — 运维文档（TD-013 M2a）

**改动要点**：**主文档已建**：`**docs/ops-diary.md`**（门禁、UTC、手动批跑、LLM 排查、misfire 定案）。若需在 `README.md` 增加一行入口链接即可。

1. 在 `**README.md`**（可选）或 `**docs/ops-diary.md`**（已具备）写明：
  - **何时手动跑**：宿主机休眠、misfire 日志、满足生成条件但当日无日记等。
  - **UTC**：调度与「今日」均为 **UTC**；补跑影响的是 **UTC 日界内是否已有行**（§〇.7）。
  - **与 Cron 重叠**：尽量避免与定时触发窗口同时跑（§〇.11）。
2. **命令示例**（容器名以实际 `**docker compose ps`** 为准，下例 `lxm_backend` 对应当前 `docker-compose.yml`）：

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

1. 注明：**同一 UTC 自然日已生成过的用户会被跳过**；示例为静态命令，**勿**与用户输入拼接进 shell（§〇.13）。
2. 若 `asyncio.run` 在特殊嵌套环境中失败，可改为容器内 `**python -m`** 调用小脚本文件（一次性进程通常无妨）。

**验收**：按文档在测试环境执行一次，日志出现批跑开始/结束，DB 行为符合预期。

---

## 四、测试清单（建议顺序）


| 序号  | 场景                                                         | 期望                                         |
| --- | ---------------------------------------------------------- | ------------------------------------------ |
| 1   | H5 有日记用户打开日记页                                              | 列表非空，`items` 渲染正确                          |
| 2   | H5 触底 / 接口失败                                               | `noMore` 正确；`code!==0` 不异常翻页、无 NaN         |
| 3   | 修改 `diary_rules` 后手动 `generate_diary_for_user`（**阶段 B 后**） | 内容与字数贴近新配置                                 |
| 4   | **0 级用户**                                                  | `generate_diary_for_user` 返回 False，无新行     |
| 5   | **1 级、UTC 当日无用户发言**                                        | 不生成                                        |
| 5b  | **≥2 级、UTC 当日无用户发言**（可选加强）                                 | 应生成「想念向」日记（与 PRD 一致）                       |
| 6   | 重启 backend 后 APScheduler                                   | next run 与 `generation_hour/minute`（UTC）一致 |
| 7   | 后台日记历史筛选 + 分页                                              | 与 DB 一致；`content` 已转义                      |
| 8   | `diary_rules` 损坏/缺字段                                       | 回退生成成功，日志 warning                          |
| 9   | LLM 失败                                                     | 不写库、不抛未捕获异常（与现网一致）                         |
| 10  | 手动执行阶段 E                                                   | 批跑完成；当日已生成用户不重复插入                          |
| 11  | （不适用）内容安全 A 已定案                                            | 无独立安全用例                                    |


---

## 五、风险与注意点

1. **UTC**：Cron 与「今日」均为 UTC；运维与用户心智可能偏差，文档必须写明（§〇.7）。
2. **占位符与模板**：须与 PRD 两分支一致；误删 early-return 风险高（§〇.2）。
3. **内容安全**：已定案 A；合规边界以契约/PRD 备忘为准（§〇.1）。
4. **并发**：手动批跑尽量避免与 Cron 窗口重叠；semaphore 现状保留（§〇.11）。
5. **性能**：批跑时长与 `level≥1` 用户数、LLM 超时相关；规模增大后再议队列（§〇.13）。
6. **契约与 TD**：阶段 D 交付同步 **contract** 与 **tech-debt**（§〇.13）。

---

## 六、建议排期顺序

1. **阶段 A**（TD-014）。
2. **阶段 B**（TD-007 核心）+ 推荐 `**diary_rules_loader`** 供 C 复用。
3. **阶段 C**（调度 + TD-013）+ **一次 backend 重启**。
4. **阶段 D**（TD-006）+ 契约/tech-debt 更新。
5. **阶段 E**（TD-013 文档），可与 D 并行。

**上线顺序与回滚**：见 **§〇.12**。

---

## 七、文档索引


| 文档                                        | 用途                                |
| ----------------------------------------- | --------------------------------- |
| `docs/diary-refactor-decisions.md`        | 产品/架构决策（含 §6 已定案）                 |
| `docs/ops-diary.md`                       | 运维、发布门禁、手动批跑、LLM 排查               |
| `docs/diary-refactor-decision-vs-plan.md` | 决策与方案对比                           |
| `docs/tech-debt.md`                       | TD-006 / TD-007 / TD-013 / TD-014 |
| `docs/contract.md`                        | 接口与页面契约                           |
| 本文                                        | 分阶段实现、审查结论与验收                     |


---

*最后更新：2026-04-07（纳入需求对齐审查；§6 已定案同步 ops-diary / 契约）*