# Diary Admin

- 文档 ID：`contract-diary-admin`
- 权威状态：`canonical`
- 功能范围：`diary`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-006`, `TD-007`, `TD-013`, `TD-014`, `TD-018`

### `admin/pages/diary-rules.html`（日记规则配置）

- **实现状态**：已实现。`activeKey='diary'`，顶栏标题「日记规则配置」。`super_admin` / `ai_trainer` 可配置，`observer` 仅读日记规则。
- **顶部横幅**：**「已接入生成与调度；改生成时刻后须重启 backend。」**（定案见 `docs/diary-refactor-decisions.md` §6）。运维见 **`docs/ops-diary.md`**；与定时任务同源的手动批跑为 **`PYTHONPATH=. python -m scripts.run_diary_batch`**（容器内见 **`docs/ops-diary.md`** §3）。
- **接口**：`GET` / `PUT` **`/api/admin/diary-rules`**。
  - **Body**：`DiaryRulesRequest` — 两个独立 **`textarea`**（`#gen-prompt-with` / `#gen-prompt-without`）对应 **`prompt_with_interaction`** / **`prompt_without_interaction`**；`max_length`（滑块 50–300，`step=10`）；`frequency` 固定 `"daily"`；**北京时间（`Asia/Shanghai`）** 时刻：`#gen-hour`（**0–23**，脚本填充选项）+ `#gen-minute`（0–59，默认 **15**）。
  - **占位符**：含 **`{{covers_date_label_zh}}`**（服务端注入，如 `5月15日`）；其余与契约 **`DiaryRulesRequest`** 说明一致。
  - **加载**：若库内仅有旧字段 **`generation_prompt`**，两套文本域均回填该值；若仅有单侧新字段则与 `generation_prompt` 策略一致（以服务端正则解析为准）。
- **保存成功**：`showToast` 提示保存成功并强调 **修改生成时刻须重启 backend** 后 Cron 才更新（与 **TD-013** 一致）。
- **字数滑块与回填**：若 `GET` 的 `max_length` 非 10 步进，**`snapMaxLengthToSliderStep`** + `warning` Toast（与契约前文一致）。
- **日记历史链接**：`super_admin` / `ops_admin` / `observer` 展示（`ai_trainer` 不展示）；指向 **`diary-history.html`**。

### `admin/pages/diary-history.html`（AI 日记历史）

- **权限**：`super_admin` / `ops_admin` / `observer`；`observer` 仅读，`ai_trainer` 直链仍为 403。
- **菜单**：`MENU_CONFIG` 中 `super_admin`、`ops_admin`、`observer` 含 **`key: 'diary-history'`** → `diary-history.html`；**不包含** `ai_trainer`（决策 O1）。
- **接口**：`GET /api/admin/diary-history`，Query 与后端一致；列表 **`content`** 经 **`escapeHtml`** 写入表格单元格，`title` 存放完整正文（已转义）便于悬停查看；表格列：**日记 `id`**、**账号**（`username`）、**账号ID**（`user_id`）、正文、生成时等级、已读、**覆盖日(北京)**（`covers_beijing_date`，可为空）、**创建时间**（`created_at`）。
- **交互**：用户 ID（筛选框仍为数字 ID）、开始/结束日期筛选；**查询**拉取第 1 页；**`renderPagination`** 分页；空列表展示「暂无数据」。
