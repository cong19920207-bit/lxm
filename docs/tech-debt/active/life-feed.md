# life-feed 技术债

- 文档 ID：`tech-debt-life-feed`
- 权威状态：`canonical`
- 功能范围：`life-feed`
- 必读依赖：无
- 相关技术债：`TD-032`, `TD-033`, `TD-034`, `TD-035`, `TD-036`, `TD-037`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-032] 朋友圈全屏预览手势与浏览器返回冲突（**已处理 · 现有兼容性说明**）

> **编号说明**：本条对应《朋友圈页面展示逻辑规范_v1.1》正文中的「技术债 TD-001（H5 全屏预览左右滑手势与页面返回手势冲突）」。该文档 TD-001 与本 `tech-debt.md` 全局 [TD-001]（users 表遗留字段）为**两套独立编号**，为避免覆盖全局 TD-001，生活流侧统一登记为 **TD-032**。

- **位置**：`frontend/pages/feed.html` → `openPreview()` 全屏预览层（STEP-023）。
- **问题**：H5 全屏预览的左右滑切换与浏览器边缘返回手势（尤其 iOS Safari 侧滑返回）存在优先级冲突，滑动切图可能误触发返回。
- **当前处理（STEP-023 已落地）**：
  1. 预览层挂载时 `document.body.style.overscrollBehaviorX = 'contain'`，卸载时恢复原值；同时 `overflow:hidden` 锁背景滚动。
  2. 预览层 `touchmove` 使用 **non-passive** 监听并 `preventDefault()`，阻断浏览器边缘返回与页面滚动；`touch-action: none`。
  3. 放大态（scale>1.05）下禁用左右切换，单击关闭、双指缩放（1~3x）。
- **兼容性说明**：老版本 Safari 若不支持 `overscroll-behavior`，仍依赖 `preventDefault()` 兜底；极端老机型可能仍偶发边缘返回，属可接受范围，**不阻断上线**。此逻辑为未来 APP 端复用预留。
- **风险等级**：**低**。
- **关联**：《朋友圈页面展示逻辑规范_v1.1》§图片预览 TD-001；STEP-023。

### [TD-033] 日生活计划后台「LLM 日志摘要」未实现（**待清偿**）

- **位置**：STEP-008 开发任务 5；`life_plan_mgmt` / `life-plan.html` 日场景 Tab。
- **问题**：文档要求展示 gen_status 与按 `scene_id` 过滤的 system_log 摘要；当前仅展示 gen_status，无日志区/接口。
- **当前处理**：2026-07-09 补齐 CRUD 时明确不做（确认点 4）；已记入 `M3_契约草案.md`。
- **待处理**：补轻量「最近日志」接口 + 日场景页折叠区；或产品确认永久砍掉后从 steps 验收项剔除。
- **触发时机**：运营反馈生成失败难排查时。
- **风险等级**：**低**（不影响主链路；失败仍有 gen_status / toast）。
- **关联**：STEP-008、STEP-031；`docs/contract/drafts/生活流/M3_契约草案.md` §1.1。

### [TD-034] 生活流部分管理列表仍用无样式的 `data-table`（**已清偿** · 2026-07-09）

- **位置**：`admin/pages/feed-posts.html` / `feed-comments.html` / `agent-aware.html`。
- **问题**：`admin-common.css` 仅定义 `.admin-table`；`data-table` 无公共样式，列表显得挤、与用户管理不一致。
- **处理**：三页已统一为 `admin-table` + `.tag` + `.op-btn-*` + `.empty-tip`，并补齐文档已有、服务端已具备的管理 UI。
- **关联**：`admin-common.css` §表格；M3 草案「通用前端约定」。

### [TD-035] 朋友圈帖子「真删除」与「隐藏/下架」未分离（**待清偿**）

- **位置**：`backend/routers/admin/feed_mgmt.py` `DELETE /feed/posts/{id}`；`admin/pages/feed-posts.html`。
- **问题**：PRD 10.3 要求删除与隐藏语义分开；当前 DELETE 仅将 `is_visible=0`，与 PATCH visibility 隐藏等价。后台内容页已去掉易误解的「删除」按钮，仅保留隐藏/展示。
- **当前处理**：UI 不提供删除；真删能力未实现。
- **待处理**：DELETE 改为物理删除或独立软删标记（列表默认过滤），与 `is_visible` 下架分离；再恢复删除按钮与确认文案。
- **触发时机**：运营需要彻底清掉错帖/测试帖时。
- **风险等级**：**中**（需明确是否级联评论/点赞及 H5 缓存）。
- **关联**：PRD §10.3#3/#4；STEP-014。

### [TD-036] 后台朋友圈本地图片上传未实现（**待清偿**）

- **位置**：STEP-014 明确「本 STEP 不实现上传」；`POST /feed/posts` upload 模式仅接收已有 `image_urls`。
- **问题**：无「选本地文件 → 上传 OSS → 回填 URL」的后台接口与 UI；管理员无法在后台直接配图发帖。
- **当前处理**：内容页「文字发帖」仅纯文字；AI 生成可选 `image_type` 出图；粘贴 CDN URL 编辑能力未作为本版重点。
- **待处理**：新增 admin 上传接口（或复用通用 OSS 上传）+ 发帖/编辑表单选图。
- **触发时机**：运营需要手动发带图帖且不愿走 OSS 控制台时。
- **风险等级**：**低～中**（权限、CDN 域名、文件类型校验）。
- **关联**：PRD §10.3#5a；STEP-014「不在本环节范围内」。

### [TD-037] 朋友圈空态未对齐 UI 规范（插画 + 指定文案）（**待清偿**）

- **位置**：`frontend/pages/feed.html` `#state-empty`；`docs/design/life-feed/朋友圈页面展示逻辑规范_v1.1.md` §5.5 / 确认清单 #16。
- **问题**：展示规范要求空态为「角色风格插画 + 提示文案（如小梦还没有发动态哦～）」；STEP-022 降级为「v1 不强制配图」；现 H5 仅文案「这里还没有内容哦～」，无插画、文案也不一致。
- **当前处理**：本轮朋友圈展示修复（签名 / 日期列 / 相对时间）明确降级，维持现状。
- **待处理**：
  1. 补角色风格空态插画资源
  2. 文案改为规范示例或产品确认文案
  3. 空态布局与现有 `.feed-state` 对齐
- **触发时机**：朋友圈空态体验优化，或上线前预填不足、空态易被用户看到时。
- **风险等级**：**低**（预填后少见；不影响列表主路径）。
- **关联**：UI 规范 §5.5；STEP-022「空态 v1 不强制配图」。

---

### 已处理（库结构 / 运维）

- `**admin_config.config_key` 误设 UNIQUE（2026-04）**：导致人格/Prompt 等保存草稿 `INSERT` 报 MySQL **1062**。处理：执行 `scripts/migrate_admin_config_config_key_nonunique.sql` 去掉唯一、重建非唯一索引；契约与 `schema_ddl.sql` 已写明「同一 key 多行」。运行时读 persona：`PromptBuilder._get_persona_from_cache` 已与 `get_active_config` 对齐增加 `is_draft=False`。
