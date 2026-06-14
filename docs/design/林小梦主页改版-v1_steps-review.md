# 开发步骤文档审查报告 · 林小梦主页改版-v1_steps · 2026-06-10

> 审查对象：`docs/design/林小梦主页改版-v1_steps.md`  
> 对照 PRD：`docs/design/PRD-林小梦主页改版-v1.md`（v1.7）  
> 代码核查范围：`frontend/pages/index.html`、`settings.html`、`api.js`、`tests/test_h5_static_contract.py`、`docs/contract.md`

---

## 我对两份文档的理解（阶段一摘要）

### PRD 核心内容

- **目标**：将 H5 主页从浅色功能聚合页升级为深色沉浸陪伴首页，内嵌记忆/日记/关系预览，不破坏子页与现有 API。
- **主要决策点**：C1–C19、Q1–Q4、R1–R4、N1–N5、K1–K7（均已闭合）。
- **涉及模块**：`index.html`（主）、`api.js`、`settings.html`、静态图、契约测试、`contract.md`。
- **验收标准**：§9 检查项 6 条（元检查清单）；§4.1 功能对比表 23 项为实质验收面。
- **技术债**：TD-HOME-01～08（PRD §8 内标注，未写入 `docs/tech-debt.md`）。

### 开发步骤文档核心内容

- **STEP 总数**：19
- **功能点（F）总数**：24 核心 + 4 项「不做」
- **声明不做**：心情标签（C12）、关怀语卡（Q1/C13）、全局 theme 改版、快捷互动未登录分支

---

## 📊 一、总览评分表

| 维度 | 状态 | 问题数 |
|------|------|--------|
| PRD 决策覆盖率 | ⚠️ | 2 条偏差 |
| 幻觉（凭空添加内容） | ✅ | 0 条明确幻觉 |
| 遗漏（PRD 有，步骤文档缺） | ⚠️ | 6 条 |
| 与 PRD 冲突 | ⚠️ | 2 条 |
| 表述不清晰 | ⚠️ | 5 条 |
| 依赖顺序合理性 | ❌ | 2 条 |
| 验收标准可测性 | ⚠️ | 3 条 |
| 技术债标注完整性 | ⚠️ | 1 条 |
| 代码事实核查（函数/路径） | ⚠️ | 2 条 |

图例：✅ 无问题 / ⚠️ 有风险 / ❌ 有明确错误

---

## 🔍 二、逐 STEP 问题标注

#### STEP-002 settings.html 引用公共状态语

**[冲突] · [依赖问题] · 严重程度：高**

> PRD 原文：N4 上收 `api.js`；N5 与 index **同 PR** 三联更新测试与 contract。  
> 步骤文档写法：STEP-002 完成标志要求「`test_settings_*` 相关静态测试仍通过」。  
> 问题说明：现网 `test_settings_change_password_ids` 断言 `settings.html` 内含字符串 `"EMOTION_STATUS_MAP"`（`tests/test_h5_static_contract.py` L105）。STEP-002 删除 settings 本地 map 后**该测试必然失败**，但 settings 测试更新仅在 STEP-019，中间 17 个 STEP 无法通过全量静态测试。  
> 建议：① STEP-002 同步修改 settings 静态测试（断言改为 `resolveStatusText` 来自 `api.js` 或 `api.js` 含 `EMOTION_STATUS_MAP`）；或 ② 将 STEP-002 完成标志改为「仅手测 settings 页，静态测试在 STEP-019 一并更新」并删除「测试仍通过」表述。

---

#### STEP-004 顶栏情绪头像 + 亲密度组件

**[遗漏] · 严重程度：中**

> PRD 原文：§4.1 #2「名从 Hero 上移至顶栏」；§4.1.2「角色名上移至顶栏左侧，与头像、心形、陪伴天数组合」。  
> 步骤文档写法：「Hero 名从 Hero 区上移的完整视觉（可与 STEP-006 协调，本 STEP 先保证顶栏信息完整）」——列为不在范围内。  
> 问题说明：顶栏新增「林小梦」后，Hero 区 `.home-hero-name-row` / `.home-hero-star` 仍保留会导致**双份角色名**，与 PRD 定稿结构图矛盾；但全文无 STEP 明确负责删除 Hero 旧名行。  
> 建议：在 STEP-004 或 STEP-006/007 增加任务：「删除 `.home-hero-name-row` 与星标，角色名仅保留顶栏一处」。

**[不清晰] · 严重程度：中**

> 步骤文档写法：STEP-004～014 期间「横卡暂保留占位」。  
> 问题说明：进度已迁顶栏后，中部 `.home-rel-card` 仍可能展示旧 `LEVEL_LABELS` 与重复进度，验收时易误判为 bug。  
> 建议：在 STEP-004 注明横卡进入 skeleton-only 或 `visibility:hidden` 直至 STEP-014，或缩短 004→014 合并窗口。

**[不清晰] · 严重程度：低**

> PRD 原文：R3-A 满级文案 `{growth_value} / 已满级`。  
> 步骤文档字段表写 `current_growth`，测试用例写 `344 / 已满级`。  
> 建议：统一写「优先 `current_growth`，与 `growth_value` 同值时等价；满级用 API 的 `next_threshold === null`」。

---

#### STEP-007 Hero 台词样式与 resolveStatusText

**[遗漏] · 严重程度：低**

> PRD 原文：状态语从「白色小气泡」升级为「大字号引号台词」。  
> 步骤文档写法：升级 `#status-text` 样式，未提 `.home-status-bubble` 容器是否保留/改造。  
> 建议：明确「气泡容器改引号台词布局，或移除 bubble 背景仅留 `#status-text`」。

---

#### STEP-013 「她的日记」预览卡

**[遗漏] · 严重程度：中**

> PRD 原文：§4.1 #15「她的日记」预览卡；§10 结构图有卡片标题。  
> 步骤文档写法：开发任务未列卡片标题「她的日记」。  
> 建议：开发任务第 1 条补充标题文案与记忆卡、关系卡一致的标题行结构。

**[遗漏] · 严重程度：低**

> PRD 原文：§4.5.1 / §5「日记列表为空：时间行隐藏或『—』」。  
> 步骤文档写法：未写无日记时时间行处理。  
> 建议：单元测试表增加「无 items → 仅固定句，时间行隐藏或 —」。

---

#### STEP-014 「关系状态」预览卡

**[遗漏] · 严重程度：低**

> PRD 原文：§10 结构图卡片区有「关系状态」标题。  
> 步骤文档写法：仅写副标题 + `level_name`，未写卡片主标题。  
> 建议：补充固定标题「关系状态」（与三宫格原入口标题一致）。

---

#### STEP-017 骨架屏适配

**[依赖问题] · 严重程度：中**

> 步骤文档写法：前置 STEP-011～016，未包含 STEP-007～010（Hero 时钟/Good night/波形）。  
> 问题说明：若 007–010 在 017 之后执行，骨架屏与真实 Hero 结构会短期不一致；若之前执行，017 应覆盖 Hero 占位。  
> 建议：前置扩展为 STEP-007～016，或注明「Hero 区骨架不在本期范围（PRD §4.1 #20 仅要求互动栏+三卡）」。

---

#### STEP-018 loadPage 五接口并行聚合

**[依赖问题] · 严重程度：中**

> 步骤文档写法：前置 STEP-005、012、013、016。  
> 问题说明：未列 STEP-004（status 渲染）、STEP-007（resolveStatusText），聚合时易漏改 status 分支或重复请求。  
> 建议：前置改为 STEP-004、005、007、012、013、016；任务中写清「以现有分散 render 函数合并为单次 Promise.all，不新增字段」。

---

#### STEP-019 契约测试与 contract 同步

**[遗漏] · 严重程度：中**

> 现网测试：`test_index_html_home_surface_contract` 断言 `updateAvatarEmotion` **not in** html；`home-rel-card`、`home-feature-grid` **in** html。  
> 步骤文档：STEP-019 覆盖 index 测试，但未提 **settings 测试**因 N4 需同步（见 STEP-002 冲突）。  
> 建议：STEP-019 开发任务显式列出 `test_settings_change_password_ids` 的 `EMOTION_STATUS_MAP` 断言迁移。

---

## 📋 三、PRD 决策点覆盖率核查

| 决策编号 | 决策内容摘要 | 覆盖 | 覆盖 STEP | 备注 |
|---------|------------|------|----------|------|
| C1 | 以 lxm_for 为准 | ✅ | — | 元决策，无需 STEP |
| C2 | 主页局部深色，不改全局 theme | ✅ | STEP-003 | |
| C3 | 展示名「亲密度」，数据复用 growth | ✅ | STEP-004 | |
| C4 | known_days 来自 detail | ✅ | STEP-005 | |
| C5 | 快捷互动 UI + Toast | ✅ | STEP-011 | |
| C6 | 记忆卡标题「我们的记忆」 | ✅ | STEP-012 | |
| C7 | 四级 level_name | ✅ | STEP-014 | |
| C8 | 波形/Good night 纯装饰 | ✅ | STEP-009, 010 | |
| C9 | CTA 文案改版 | ✅ | STEP-016 | |
| C10 | 亲密度即设置入口 | ✅ | STEP-004 | |
| C11 | 北京时间时钟+时段 | ✅ | STEP-008 | |
| C12 | 不展示心情标签 | ✅ | F 清单「不做」 | 无显式 DOM 删除 STEP，建议在 STEP-007 写「不新增心情模块」 |
| C13 | 移除关怀语卡 | ✅ | F 清单「不做」 | |
| C14 | 亲密度可显示数值 | ✅ | STEP-004 | |
| C15 | 关系卡无第二行 | ✅ | STEP-014 | |
| C16 | 日记固定句+时间 | ✅ | STEP-013 | 缺标题/空时间行细则 |
| C17 | 静态占位图路径 | ✅ | STEP-012, 013 | 图片在仓库为 untracked，开发前需确认已入库 |
| C18 | 沿用 index.png | ✅ | STEP-006 | |
| C19 | 删除中部横卡 | ✅ | STEP-014 | |
| Q1 | 关怀卡移除 | ✅ | F 不做 | |
| Q2 | Good night 深夜+晚上 | ✅ | STEP-009 | |
| Q3 | 日记相对时间 | ✅ | STEP-013 | |
| Q4 | Lv0 日记锁 | ✅ | STEP-013 | |
| R1 | 情绪头像 | ✅ | STEP-004 | |
| R2 | 记忆 API 首条 | ✅ | STEP-012 | |
| R3 | 满级亲密度文案 | ⚠️ | STEP-004 | growth_value vs current_growth 表述不一 |
| R4 | formatTime 四档 | ✅ | STEP-013 | |
| N1 | checkLogin 维持 | ⚠️ | F 保留 | 无 STEP 完成标志回归项 |
| N2 | 移除装饰球 | ✅ | STEP-006 | |
| N3 | 记忆不展示 key | ✅ | STEP-012 | |
| N4 | 状态语上收 api.js | ✅ | STEP-001, 002, 007 | 与 settings 测试冲突见上 |
| N5 | 三联 contract+测试 | ⚠️ | STEP-019 | settings 测试未列入 |
| K1–K7 | 冲突闭合 | ✅ | 分散 | K6→019；无独立 STEP 问题 |

---

## 📋 四、验收标准覆盖率核查

PRD §9 为元检查清单；实质功能验收以 §4.1（23 项）为准：

| 验收条款 | 摘要 | 覆盖 | 覆盖 STEP | 备注 |
|---------|------|------|----------|------|
| §4.1 #1–23 | 功能对比表各项 | ⚠️ | 多数有 | #2 Hero 去名遗漏；#12 不做已声明 |
| §5 边界 | 空数据/权限/视觉 | ⚠️ | 分散 | `relationship_level` localStorage 保留未写 |
| §9 检查项 | C/N/K 闭合等 | ✅ | 全文 | 文档级，非开发 STEP |

---

## 🗂️ 五、技术债标注完整性

| 技术债编号 | PRD 描述 | 步骤文档写入动作 | 涉及 STEP | 建议 |
|-----------|---------|----------------|---------|------|
| TD-HOME-01 | status_text 可能未返回 | ⚠️ 隐含于 STEP-001/007 | 001, 007 | 在 STEP-007 完成标志注明「兜底走 resolveStatusText」 |
| TD-HOME-02 | 快捷互动无后端 | ✅ | STEP-011 | |
| TD-HOME-03 | 配图静态占位 | ✅ | STEP-012, 013 | |
| TD-HOME-04 | 多模态未实现 | ❌ 无 | — | 可选：F 清单或 STEP-011 备注引用 |
| TD-HOME-05 | 北京时间计算 | ✅ | STEP-008 | |
| TD-HOME-06 | 记忆非时间序 | ✅ | STEP-012 | |
| TD-HOME-07 | 状态语双份 | ✅ | STEP-001, 002 | 完成后可在 tech-debt 或 PR 说明关闭 |
| TD-HOME-08 | 远期游客首页 | ✅ | F 不做 | |

> `docs/tech-debt.md` 中**无** TD-HOME 条目；PRD 仅在 §8 自载。步骤文档不强制写入 tech-debt.md，但若项目惯例要同步，建议在 STEP-019 备注。

---

## 🔗 六、依赖关系合理性分析

| 问题 STEP | 问题描述 | 建议 |
|----------|---------|------|
| STEP-002 | 完成标志要求 settings 静态测试通过，与 N4 搬迁矛盾 | 见第二节高优修复 |
| STEP-013 | 前置 STEP-012 仅为「版式参考」，非硬依赖 | 可改为仅依赖 STEP-003+004，允许与 012 并行 |
| STEP-004→014 | 横卡与顶栏亲密度双显窗口过长 | 004 后隐藏横卡或提前到 005 后删除 |
| STEP-017 | 未含 Hero 子 STEP，骨架与 Hero 可能不同步 | 扩展前置或明确 Hero 不做骨架 |
| STEP-018 | 前置未含 004/007 | 补全 |
| 隐性 | 改版全程 `test_index_html_home_surface_contract` 会失败直至 STEP-019 | 在进度文档备注「019 前 index 契约测试预期失败」 |

**可并行但被串行**：STEP-006/011/012/016 均仅依赖 003，文档已建议并行轨 ✅。

---

## 💻 七、代码事实核查结果

| 核查项 | 步骤文档引用 | 代码实际情况 | 结论 |
|-------|------------|------------|------|
| `resolveStatusText` | STEP-001 新增于 api.js | 仅在 `settings.html` L649，**api.js 无** | ✅ 与「待开发」一致 |
| `EMOTION_STATUS_MAP` | STEP-001 上收 | 仅在 `settings.html` L637 | ✅ 一致 |
| `updateAvatarEmotion` | STEP-004 调用 | `api.js` L91 存在；index **未调用** | ✅ 一致 |
| `formatTime` | STEP-013 | `api.js` L70 存在 | ✅ 存在 |
| `goToRelationship` | STEP-014 | `api.js` L181 存在 | ✅ 存在 |
| `DEFAULT_STATUS_TEXT` | STEP-001 | settings 用 `DEFAULT_STATUS`（非 `_TEXT`） | ⚠️ 命名需与现网常量对齐 |
| 亲密度阈值 | STEP-004 用 `next_threshold` | index 现用 `LEVEL_THRESHOLDS[level]` 硬编码 | ⚠️ STEP-004 必须改现网逻辑 |
| `level_name` vs `LEVEL_LABELS` | STEP-014 用 API level_name | index 现用 `LEVEL_LABELS[level]` 长句 | ⚠️ STEP-014 需删除错误映射 |
| `test_index` 断言 `updateAvatarEmotion not in html` | STEP-019 更新 | 现网仍断言不存在 | ✅ 019 前预期失败 |
| 占位图路径 | C17 | git 状态为 untracked，路径存在 | ⚠️ 合入前需 add 资源 |
| `common.css` 可选变量 | PRD §7 | 步骤未覆盖 | ⚪ 可选，非错误 |

---

## 📝 八、「明确不做」一致性核查

| PRD 排除项 | 步骤文档是否正确排除 | 备注 |
|-----------|-------------------|------|
| 心情标签 C12 | ✅ | |
| 关怀语卡 Q1/C13 | ✅ | |
| 全局 h5-theme.css C2 | ✅ | |
| 快捷互动未登录 N1 | ✅ | |
| 子页/后端算法不改 | ✅ | F 清单「保留」 |
| Ulxm-main 不同步 C1 | ✅ 未误纳入 | |

本次审查未发现在步骤文档中误纳入 PRD 排除项的情况。

---

## 🛠️ 九、综合修改建议

### 高优先级（影响开发正确性，必须修改）

- [ ] **STEP-002 与 settings 静态测试冲突** → STEP-002 同步改 `test_settings_change_password_ids`，或调整完成标志；STEP-019 任务清单补上 settings 测试项。
- [ ] **Hero 区旧「林小梦」名行无归属 STEP** → 在 STEP-004 或 STEP-006 增加删除 `.home-hero-name-row` / `.home-hero-star` 任务，对齐 §4.1 #2。

### 中优先级（影响开发清晰度，建议修改）

- [ ] **STEP-004～014 双份亲密度展示窗口** → 004 后隐藏 `.home-rel-card` 或合并 014 时机。
- [ ] **STEP-013/014 卡片主标题遗漏** → 补充「她的日记」「关系状态」标题行。
- [ ] **STEP-018 前置依赖不全** → 加入 STEP-004、007。
- [ ] **STEP-017 与 Hero 子 STEP 关系** → 写清 Hero 是否纳入骨架范围。
- [ ] **现网 `next_threshold` / `level_name` 误用** → STEP-004/014 任务中显式写「删除 `LEVEL_THRESHOLDS` 进度计算与 `LEVEL_LABELS` 等级展示」。

### 低优先级（可选优化）

- [ ] STEP-001 常量名与现网 `DEFAULT_STATUS` 对齐，减少迁移 diff。
- [ ] F 清单或 STEP-018 补充「保留 `localStorage.setItem('relationship_level')`」回归（diary 等页可能读取）。
- [ ] 进度文档备注：STEP-019 完成前 `test_index_html_home_surface_contract` 预期失败。
- [ ] PRD §7 可选 `common.css` 色板：若不做可写「本期跳过」。

---

## 十、幻觉检查结论

经对照 PRD 原文与现网代码，**未发现步骤文档凭空添加 PRD 未定义的产品功能**（如关怀卡、游客模式、后端新接口等）。  
以下为**合理自定义**（已标注 `[自定义]` 或属实现细节），**不算幻觉**：

- `.home-glass-card`、`.home-quick-actions` 等 CSS 类名
- `DEFAULT_STATUS_TEXT` 命名（与现网 `DEFAULT_STATUS` 仅命名差异）
- STEP 拆分粒度与并行轨建议

---

## 十一、逻辑冲突检查结论

| 类型 | 结论 |
|------|------|
| 与 PRD 产品决策相反 | **未发现**（亲密度、四级、Good night 时段等均一致） |
| 步骤文档内部自相矛盾 | **1 处明确**：STEP-002 要求测试通过 vs 删除 `EMOTION_STATUS_MAP` |
| 与现网代码迁移方向矛盾 | **1 处风险**：若不删 `LEVEL_THRESHOLDS` 则违背 C14/R3 |

---

*审查完成。建议优先修复「STEP-002 测试冲突」与「Hero 双份角色名遗漏」后再按轨执行开发。*
