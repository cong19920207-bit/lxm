# 林小梦主页改版-v1 开发步骤拆解

> PRD 来源：`docs/design/PRD-林小梦主页改版-v1.md`（v1.7）
> 进度追踪：`docs/progress/林小梦主页改版-v1_progress.md`
> 契约文档：`docs/contract.md`
> 拆解原则：每 STEP 只改一个最小功能单元，完成后可独立验收，不阻塞其他 STEP 的并行准备（除明确标注的前置依赖外）。
> 修订：2026-06-10（依据 `林小梦主页改版-v1_steps-review.md` 审查建议）

---

## 1. 功能清单

| # | 功能点 | 优先级 | 依赖 |
|---|--------|--------|------|
| F01 | `api.js` 上收 `EMOTION_STATUS_MAP` + `resolveStatusText`（N4） | [核心] | 无 |
| F02 | `settings.html` 删除本地状态语 map，改引 `api.js`（N4） | [核心] | F01 |
| F03 | 主页独立深色夜景 + 玻璃拟态主题（C2，不改 `h5-theme.css`） | [核心] | 无 |
| F04 | 顶栏：情绪头像 + 林小梦 + ♥（R1-B） | [核心] | F03 |
| F05 | 顶栏：亲密度进度条 + 数值 + 点击进设置（C3/C10/C14/R3） | [核心] | F03 |
| F06 | 顶栏：移除用户首字母头像与独立 ⚙️（C10） | [核心] | F04/F05 |
| F07 | 顶栏：「陪伴你的第 N 天」（C4，`known_days`） | [核心] | F04 |
| F08 | Hero 立绘沿用 `index.png` + 深色遮罩/滤镜（C18） | [核心] | F03 |
| F09 | 移除黄粉装饰球 DOM/局部隐藏（N2） | [核心] | F08 |
| F10 | Hero 大字号台词 + `resolveStatusText` 链路（N4） | [核心] | F01, F08 |
| F11 | 北京时间 24h 时钟 + 八段时段词（C11/TD-HOME-05） | [核心] | F08 |
| F12 | Good night 手写装饰，深夜+晚上显示（Q2-B/C8） | [核心] | F11 |
| F13 | Hero 音频波形纯装饰动画（C8） | [核心] | F08 |
| F14 | 快捷互动栏 5 项 + Toast「敬请期待」（C5/N1） | [核心] | F03 |
| F15 | 「我们的记忆」纵向预览卡（C6/N3/R2/C17） | [核心] | F03 |
| F16 | 「她的日记」纵向预览卡（C16/Q3/Q4/R4/C17） | [核心] | F03, F05（Lv0 锁需 level；可与 F15 并行） |
| F17 | 「关系状态」纵向预览卡（C7/C15） | [核心] | F03, F05 |
| F18 | 删除 `.home-rel-card` 中部横卡（C19-A） | [核心] | F05, F17 |
| F19 | 删除 `.home-feature-grid` 三宫格（§4.1 #14–16） | [核心] | F15, F16, F17 |
| F20 | 纵向滚动多卡布局（§4.1 #19） | [核心] | F14–F19 |
| F21 | 底部 CTA「和她说说话吧」+ 副文案 + 未读角标（C9） | [核心] | F03 |
| F22 | 骨架屏匹配新布局（§4.1 #20） | [核心] | F14–F21 |
| F23 | `loadPage` 并行五接口聚合（§4.7） | [核心] | F07, F15, F16, F21 |
| F24 | 静态契约测试 + `contract.md` 首页摘要同步（N5/K6） | [核心] | F01–F23 |
| — | **不做**：「她此刻的心情」标签（C12） | — | — |
| — | **不做**：关怀语独立卡（Q1/C13） | — | — |
| — | **不做**：全局 `h5-theme.css` 改版（C2） | — | — |
| — | **不做**：快捷互动未登录分支（N1，本期 `checkLogin` 拦截） | — | — |
| — | **保留**：子页跳转路径、`checkLogin()`、`formatBadgeCount`、`localStorage.setItem('relationship_level')` | — | — |
| — | **本期跳过**：PRD §7 可选 `common.css` 主页色板变量 | — | — |

---

## 2. 开发环节总览

| 环节编号 | 功能名称 | 涉及模块 | 前置环节 | 预计复杂度 |
|---------|---------|---------|---------|----------|
| STEP-001 | api.js 状态语公共模块上收 | `api.js` | 无 | 低 |
| STEP-002 | settings.html 引用公共状态语 | `settings.html` | STEP-001 | 低 |
| STEP-003 | 主页深色主题基础壳层 | `index.html`（CSS） | 无 | 中 |
| STEP-004 | 顶栏情绪头像 + 亲密度组件 | `index.html` | STEP-003 | 中 |
| STEP-005 | 陪伴天数展示 | `index.html` | STEP-004 | 低 |
| STEP-006 | Hero 立绘夜景 + 移除装饰球 | `index.html` | STEP-003 | 中 |
| STEP-007 | Hero 台词样式与 resolveStatusText | `index.html` | STEP-001, STEP-006 | 低 |
| STEP-008 | 北京时间时钟与时段词 | `index.html` | STEP-006 | 中 |
| STEP-009 | Good night 条件装饰 | `index.html` | STEP-008 | 低 |
| STEP-010 | Hero 波形纯装饰 | `index.html` | STEP-006 | 低 |
| STEP-011 | 快捷互动栏占位 UI | `index.html` | STEP-003 | 低 |
| STEP-012 | 「我们的记忆」预览卡 | `index.html` | STEP-003 | 中 |
| STEP-013 | 「她的日记」预览卡 | `index.html` | STEP-003, STEP-004 | 中 |
| STEP-014 | 「关系状态」预览卡 + 删除横卡 | `index.html` | STEP-004, STEP-012 | 中 |
| STEP-015 | 删除三宫格 + 纵向滚动布局 | `index.html` | STEP-012, STEP-013, STEP-014 | 低 |
| STEP-016 | 底部 CTA 改版与未读角标 | `index.html` | STEP-003 | 低 |
| STEP-017 | 骨架屏适配新布局 | `index.html` | STEP-011–STEP-016 | 低 |
| STEP-018 | loadPage 五接口并行聚合 | `index.html` | STEP-004, STEP-005, STEP-007, STEP-012, STEP-013, STEP-016 | 中 |
| STEP-019 | 契约测试与 contract 摘要同步 | `tests/`, `contract.md` | STEP-001–STEP-018 | 低 |

---

## 3. 开发提示词

### [STEP-001] api.js 状态语公共模块上收

**目标**：将 `EMOTION_STATUS_MAP`、`DEFAULT_STATUS_TEXT`、`resolveStatusText` 上收到 `api.js`，供首页与设置页共用。

---

**前置条件检查**：无前置条件

---

**需要参考的文件**：
- `@frontend/pages/settings.html` — 现有本地 `EMOTION_STATUS_MAP` / `resolveStatusText` 实现
- `@frontend/static/js/api.js` — 追加导出位置
- `@docs/contract.md` — 设置页状态语兜底规则

**环境/数据前提**：无

---

**需求原文引用**：
> N4 | 状态语兜底抽取 | `EMOTION_STATUS_MAP` + `resolveStatusText(data)` **上收** `api.js`；`index.html` 与 `settings.html` 共用；settings 删除本地重复定义（清偿 TD-HOME-07）

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `status_text` | String | 优先展示的状态语 | 需求文档原文 |
| `ai_current_emotion` | String | 情绪标签，映射 `EMOTION_STATUS_MAP` | 需求文档原文 |
| `DEFAULT_STATUS_TEXT` | String | 最终兜底文案 | [自定义]：值与 settings 现网常量 `DEFAULT_STATUS`（`今天状态不错，继续陪伴你吧~`）一致；上收后统一命名为 `DEFAULT_STATUS_TEXT` |

---

**开发任务**：
1. 在 `api.js` 新增 `EMOTION_STATUS_MAP`（与 `settings.html` 现网 map 条目一致）
2. 新增 `DEFAULT_STATUS_TEXT` 常量（文案与现网 `DEFAULT_STATUS` 逐字相同）
3. 新增 `resolveStatusText(data)`：`status_text` → `EMOTION_STATUS_MAP[ai_current_emotion]` → `DEFAULT_STATUS_TEXT`
4. **本 STEP 不修改** `settings.html` 与 `index.html`

**不在本环节范围内**：
- `settings.html` 删重复定义（STEP-002）
- `index.html` 接入（STEP-007）
- 契约文档更新（STEP-019）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常场景 | `{ status_text: '自定义语' }` | `'自定义语'` |
| 正常场景 | `{ ai_current_emotion: '想念' }` | map 对应文案 |
| 边界测试 | `{}` | `DEFAULT_STATUS_TEXT` |

---

**完成标志**：
- [ ] `api.js` 可在控制台调用 `resolveStatusText`
- [ ] 未改动 `index.html` / `settings.html` 行为
- [ ] 进度文档 STEP-001 更新为 ✅

---

**完成后执行**：
> 1. 更新 `docs/progress/林小梦主页改版-v1_progress.md` STEP-001 → ✅
> 2. 下一环节：**STEP-002 settings.html 引用公共状态语**

---

### [STEP-002] settings.html 引用公共状态语

**目标**：删除 `settings.html` 本地重复定义，改用 `api.js` 的 `resolveStatusText`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 | api.js 状态语公共模块 | progress 中 STEP-001 为 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/settings.html` — 删除本地 map
- `@frontend/static/js/api.js` — 引用 `resolveStatusText`
- `@tests/test_h5_static_contract.py` — `test_settings_change_password_ids`（N4 断言迁移）

**环境/数据前提**：STEP-001 已完成

---

**需求原文引用**：
> settings 删除本地重复定义（清偿 TD-HOME-07）
> N5：静态契约与实现同 PR 同步（settings 侧在本 STEP 即改，与 STEP-019 index 侧分开）

---

**开发任务**：
1. 删除 `settings.html` 内 `EMOTION_STATUS_MAP`、`DEFAULT_STATUS` 与本地 `resolveStatusText` 函数
2. 状态语渲染改为调用全局 `resolveStatusText(res.data)`；兜底文案走 `api.js` 的 `DEFAULT_STATUS_TEXT`
3. **同步更新** `test_settings_change_password_ids`：移除对 `settings.html` 内含 `EMOTION_STATUS_MAP` 的断言；改为断言 `api.js` 含 `EMOTION_STATUS_MAP` / `resolveStatusText`，且 `settings.html` 引用 `resolveStatusText`
4. 验证设置页加载后状态语与改版前一致

**不在本环节范围内**：
- `index.html` 任何改动
- `contract.md` 文首摘要（STEP-019）
- `test_index_html_home_surface_contract`（STEP-019）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 回归 | 设置页打开 | 状态语正常显示，无控制台报错 |
| 静态 | `pytest tests/test_h5_static_contract.py::test_settings_change_password_ids` | 通过 |

---

**完成标志**：
- [ ] settings 页行为与 STEP-001 前一致
- [ ] settings 静态契约测试已更新并通过
- [ ] 进度文档 STEP-002 → ✅

---

**完成后执行**：
> 下一环节可并行：**STEP-003 主页深色主题** 或继续串行

---

### [STEP-003] 主页深色主题基础壳层

**目标**：为 `index.html` 建立深色夜景 + 玻璃拟态局部样式基础，不改全局 `h5-theme.css`，暂保留现网 DOM 结构可用。

---

**前置条件检查**：无前置条件（可与 STEP-001/002 并行）

---

**需要参考的文件**：
- `@frontend/pages/index.html` — 局部 `<style>` 改写
- `@docs/design/PRD-林小梦主页改版-v1.md` §3、§4.1 #1

**环境/数据前提**：无

---

**需求原文引用**：
> 主页独立深色主题（`index.html` 局部样式），**不**全局改 `h5-theme.css`（C2）
> 色彩：深黑紫 `#0a0a1a` ~ `#1A1A2E` + `#A855F7` 强调

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `--home-bg-deep` | CSS 变量 | 页面深底色 | [自定义] |
| `--home-accent-purple` | CSS 变量 | 霓虹紫强调色 `#A855F7` | 需求文档原文 |

---

**开发任务**：
1. 重写 `.page.h5-home-page` 背景为深色渐变
2. 新增玻璃拟态卡片基础 class（如 `.home-glass-card`）[自定义]
3. 配置 `env(safe-area-inset-*)` 安全区
4. **保留**现网顶栏/Hero/关系卡/三宫格/CTA 仍可渲染（仅换色，不删 DOM）

**不在本环节范围内**：
- 顶栏结构改造（STEP-004）
- 删除 `.home-rel-card` / `.home-feature-grid`（STEP-014/015）
- 修改 `h5-theme.css`
- PRD §7 可选 `frontend/static/css/common.css` 色板变量（**本期跳过**）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 视觉 | 打开首页 | 深色底，现网模块仍可见可操作 |
| 回归 | 其他 H5 页 | 不受本页局部样式影响 |
| 说明 | STEP-003～018 期间 | `test_index_html_home_surface_contract` **预期失败**，STEP-019 收官后恢复 |

---

**完成标志**：
- [ ] 深色主题壳层生效
- [ ] 现网功能仍可点击跳转
- [ ] STEP-003 → ✅

---

**完成后执行**：
> 下一环节：**STEP-004 顶栏改造**

---

### [STEP-004] 顶栏情绪头像 + 亲密度组件

**目标**：顶栏左侧展示情绪头像+林小梦+♥；右侧亲密度进度条（含数值），点击进入设置；移除用户首字母与 ⚙️。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题壳层 | STEP-003 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/index.html`
- `@frontend/pages/settings.html` — `updateAvatarEmotion` 用法参照
- `@frontend/static/js/api.js` — `updateAvatarEmotion`, `request`
- `@docs/contract.md` — `GET /api/relationship/status` 字段

**环境/数据前提**：`GET /api/relationship/status` 可用（待查契约文档）

---

**需求原文引用**：
> §4.1 #2：名从 Hero 上移至顶栏（情绪头像 +「林小梦」+ ♥）
> R1-B：顶栏林小梦头像随 `ai_current_emotion` 切换（`updateAvatarEmotion` / `AVATAR_MAP`）
> C10：右上角「亲密度」胶囊/进度组件 **即设置入口** → `settings.html`；**移除**独立 ⚙️
> C14：可显示 `current_growth / next_threshold`；R3-A：`next_threshold` 为 null 时显示 `{数值} / 已满级`，进度条 100%

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `progress_percent` | Number | 顶栏进度条宽度（**优先用 API 值**，勿用 `LEVEL_THRESHOLDS` 重算） | 需求文档原文 |
| `current_growth` | Number | 亲密度当前值（展示用；与 `growth_value` 同值时可互换） | 需求文档原文 |
| `growth_value` | Number | 满级文案左侧数值（R3-A 口径；通常与 `current_growth` 相同） | 需求文档原文 |
| `next_threshold` | Number/null | 下一档阈值；null 表示满级 | 需求文档原文 |
| `ai_current_emotion` | String | 驱动 `updateAvatarEmotion` | 需求文档原文 |

---

**开发任务**：
1. 顶栏 DOM：左侧 `#linxiaomeng-avatar` 可见（可移除 `.home-avatar-legacy` 隐藏区或合并为顶栏头像），并调用 `updateAvatarEmotion`
2. 展示「林小梦」+ 紫色心形图标（**角色名仅顶栏一处**）
3. **删除** Hero 内 `.home-hero-name-row`、`.home-hero-star`（§4.1 #2，避免双份角色名）
4. 右侧亲密度组件：label「亲密度」+ 进度条 + 数值；整区点击 `location.href='/pages/settings.html'`
5. 删除 `#user-initial`、`.settings-btn`
6. 将原 `.home-rel-card` 内进度渲染**迁移到顶栏**；**删除**现网 `LEVEL_THRESHOLDS` 硬编码进度计算，改用 API 的 `next_threshold` + `progress_percent`
7. 迁移完成后对 `.home-rel-card` 设 `display:none`（或等价隐藏），避免与顶栏亲密度重复展示，直至 STEP-014 删 DOM
8. `loadPage` 中 status 接口渲染顶栏亲密度与头像；**保留** `localStorage.setItem('relationship_level', level)`（日记等子页可能读取）

**不在本环节范围内**：
- `known_days`（STEP-005）
- 物理删除 `.home-rel-card` DOM（STEP-014）
- 关系卡 `level_name` 展示（STEP-014，届时删除 `LEVEL_LABELS` 用于关系等级的逻辑）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常 | level=1, current_growth=344, next_threshold=800, progress_percent=24 | 顶栏显示 `344 / 800`，进度条 width=24% |
| 满级 | `next_threshold: null`, growth_value=2500 | `2500 / 已满级`，进度条 100% |
| 布局 | 渲染后 | 页面仅顶栏一处「林小梦」，Hero 无 `.home-hero-name` |
| 交互 | 点击亲密度区 | 跳转 settings.html |

---

**完成标志**：
- [ ] 顶栏新结构可用，旧入口已移除，Hero 旧名行已删
- [ ] 横卡已隐藏，顶栏无重复亲密度以外的中部进度条
- [ ] STEP-004 → ✅

---

**完成后执行**：
> 下一环节：**STEP-005 陪伴天数** 或 **STEP-006 Hero 立绘**

---

### [STEP-005] 陪伴天数展示

**目标**：顶栏展示「陪伴你的第 {N} 天」，数据来自 `relationship/detail`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-004 | 顶栏结构 | STEP-004 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/index.html`
- `@docs/contract.md` — `GET /api/relationship/detail` → `milestones.known_days`

**环境/数据前提**：`GET /api/relationship/detail` 可用

---

**需求原文引用**：
> C4：使用 `known_days`（相识天数），取自 `GET /api/relationship/detail` → `milestones.known_days`
> 展示：「陪伴你的第 {N} 天」
> `detail` 请求失败：陪伴天数显示「—」或隐藏

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `milestones.known_days` | Number | 相识天数 | 需求文档原文 |

---

**开发任务**：
1. 顶栏增加 `#known-days` 或等价节点
2. `loadPage` 增加 `GET /api/relationship/detail` 请求（可先独立 `Promise`，STEP-018 再统一并行）
3. 成功渲染「陪伴你的第 {N} 天」；失败显示「—」或隐藏

**不在本环节范围内**：
- 五接口最终 `Promise.all` 整合（STEP-018）
- 后端将 `known_days` 并入 status（§6.2 P2，非本期）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常 | `known_days: 27` | 「陪伴你的第 27 天」 |
| 异常 | detail 接口失败 | 「—」或节点隐藏，其余模块正常 |

---

**完成标志**：
- [ ] 陪伴天数展示正确
- [ ] STEP-005 → ✅

---

### [STEP-006] Hero 立绘夜景 + 移除装饰球

**目标**：Hero 沿用 `index.png`，加深色遮罩/滤镜适配夜景；移除黄粉装饰球。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题 | STEP-003 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/index.html`
- `@frontend/static/css/h5-theme.css` — 仅参考，**不改**

**环境/数据前提**：无

---

**需求原文引用**：
> C18：沿用 `/static/images/Index/index.png`，靠深色 CSS 遮罩/滤镜适配夜景主题
> N2：移除现网 `.h5-home-decor` 黄粉装饰球；`index.html` 局部隐藏或删除 DOM，不改全局 theme

---

**开发任务**：
1. 调整 `.home-hero::after` 为深色渐变遮罩（替换浅色 `#f8f4ff` 过渡）
2. 删除或隐藏 `.h5-home-decor` DOM 及依赖其的局部样式
3. 保持 `background-size: cover`、`min-height` 沉浸占比（小屏 `min-height: 50vh` 见 §5）

**不在本环节范围内**：
- 时钟/台词/波形（STEP-007–010）
- 修改 `h5-theme.css` 全局装饰球规则

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 视觉 | 打开首页 | Hero 夜景风格，无黄粉球 |
| 资源 | 网络面板 | 仍只请求 `index.png` |

---

**完成标志**：
- [ ] Hero 夜景生效，装饰球不可见
- [ ] STEP-006 → ✅

---

### [STEP-007] Hero 台词样式与 resolveStatusText

**目标**：Hero 区大字号引号台词样式，数据走 `resolveStatusText`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001 | api.js 状态语 | STEP-001 ✅ |
| STEP-006 | Hero 视觉 | STEP-006 ✅ |

---

**需要参考的文件**：
- `@frontend/pages/index.html`
- `@frontend/static/js/api.js` — `resolveStatusText`

**需求原文引用**：
> 大字号引号台词；`resolveStatusText`：`status_text` → `EMOTION_STATUS_MAP` → 默认文案

---

**开发任务**：
1. 将 `#status-text` 从白色小气泡升级为 Hero **大字号引号台词**样式（保留 id）；`.home-status-bubble` 去气泡白底，改为引号台词布局（或移除 bubble 容器仅留 `#status-text`）
2. `loadPage` 中 `status-text` 赋值改为 `resolveStatusText(d)`
3. 移除硬编码兜底 `'和你在一起的每一天都很开心'`（改走 N4 链路）
4. **不新增**「她此刻的心情」标签模块（C12）

**不在本环节范围内**：
- 时钟/时段（STEP-008）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 正常 | 有 `status_text` | 显示接口文案 |
| 兜底 | 无 `status_text`，有 emotion | map 文案 |
| 兜底 | 皆无 | `DEFAULT_STATUS_TEXT` |

---

**完成标志**：
- [ ] 台词样式与数据链路符合 PRD
- [ ] STEP-007 → ✅

---

### [STEP-008] 北京时间时钟与时段词

**目标**：Hero 展示北京时间 `HH:mm`（冒号闪动）+ 八段时段词。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-006 | Hero 区 | STEP-006 ✅ |

---

**需要参考的文件**：
- `@docs/design/PRD-林小梦主页改版-v1.md` §4.8

**需求原文引用**：
> 按北京时间分 8 段；Hero 展示 24h 时钟（冒号闪动）+ 时段词
> 前端用 `Intl` 或手动 offset 取北京时间，避免仅依赖用户本机非北京时区
> `prefers-reduced-motion` 下冒号常亮

---

**字段定义**：

| 字段名 | 类型 | 说明 | 来源 |
|-------|------|------|------|
| `hour` | Number | 北京时间 0–23 | [自定义] |
| `periodLabel` | String | 深夜/清晨/上午/中午/下午/傍晚/晚上 | 需求文档原文 §4.8 |

---

**开发任务**：
1. 实现 `getBeijingDate()` 或等价工具（TD-HOME-05）
2. Hero 增加时钟 DOM + 时段词 DOM
3. 冒号 CSS 闪动动画；`prefers-reduced-motion: reduce` 时关闭闪动
4. `setInterval` 每分钟刷新时段（跨 05:00/20:00 边界）

**不在本环节范围内**：
- Good night 装饰（STEP-009）
- §4.8 配套句 UI（本期不展示）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 时段 | hour=1 | 时段词「深夜」 |
| 时段 | hour=10 | 「上午」 |
| 动画 | `prefers-reduced-motion` | 冒号不闪动 |

---

**完成标志**：
- [ ] 时钟与时段词正确
- [ ] STEP-008 → ✅

---

### [STEP-009] Good night 条件装饰

**目标**：Hero 左侧手写体 `Good night`，仅深夜与晚上时段显示。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-008 | 北京时间 hour | STEP-008 ✅ |

---

**需求原文引用**：
> Q2-B：深夜（00:00–04:59）与晚上（20:00–23:59）显示；其余隐藏
> 判定：`hour >= 20` 或 `hour < 5`
> 纯装饰；`prefers-reduced-motion` 下仍展示

---

**开发任务**：
1. Hero 左侧增加 `.home-good-night` 节点
2. 与时钟共用北京时间 hour 判定显隐
3. 手写/script 字体（如 `Ma Shan Zheng`，与关系页一致）

**不在本环节范围内**：
- 真实语音/交互

---

**单元测试要求**：

| 场景 | hour | 预期 |
|------|------|------|
| 显示 | 1 | 可见 |
| 显示 | 21 | 可见 |
| 隐藏 | 12 | `display:none` 或移除 |

---

**完成标志**：
- [ ] Good night 时段逻辑正确
- [ ] STEP-009 → ✅

---

### [STEP-010] Hero 波形纯装饰

**目标**：Hero 区 CSS/SVG 波形装饰动画，不接语音流。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-006 | Hero 区 | STEP-006 ✅ |

---

**需求原文引用**：
> 首期纯视觉装饰，不接真实语音流（C8）
> `prefers-reduced-motion`：波形动画可关闭

---

**开发任务**：
1. 新增 `.home-waveform` 装饰条（CSS 或 inline SVG）
2. 循环动画；`prefers-reduced-motion` 下静态或隐藏动画

**不在本环节范围内**：
- 音频播放/语音通话

---

**完成标志**：
- [ ] 波形装饰可见且不影响布局点击
- [ ] STEP-010 → ✅

---

### [STEP-011] 快捷互动栏占位 UI

**目标**：新增 5 项快捷互动入口，点击 Toast「敬请期待」。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题 | STEP-003 ✅ |

---

**需求原文引用**：
> 首期做 UI 入口；已登录点击 → Toast「敬请期待」（C5 + N1）
> 语音通话 / 视频通话 / 一起听歌 / 陪我入睡 / 更多互动

---

**开发任务**：
1. Hero 下方新增 `.home-quick-actions` 横栏，5 个按钮 [自定义] class/id
2. 统一 `onclick` → `showToast('敬请期待')`
3. 玻璃拟态/icon 风格与深色主题一致

**不在本环节范围内**：
- 未登录分支（N1 本期不测）
- 真实通话/听歌能力（TD-HOME-02）

---

**完成标志**：
- [ ] 5 项均可点击出 Toast
- [ ] STEP-011 → ✅

---

### [STEP-012] 「我们的记忆」预览卡

**目标**：纵向预览卡展示记忆摘要，点击进 `memory.html`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题 | STEP-003 ✅ |

---

**需要参考的文件**：
- `@docs/contract.md` — `GET /api/memory/list`
- `@frontend/static/images/Index/in_memery/sunset.png`

**需求原文引用**：
> 标题「我们的记忆」；副标题「她记得你们的点点滴滴」
> `GET /api/memory/list?page=1&page_size=1` 首条；单行 `(value || content)` 截断 ~40 字，不展示 key（N3）
> 空态：「她还在了解你，暂无记忆」
> 配图 `/static/images/Index/in_memery/sunset.png`

---

**开发任务**：
1. 新增 `.home-memory-card` DOM（不删三宫格，可并存至 STEP-015）
2. `loadPage` 请求 `memory/list`，渲染预览/空态
3. 整卡点击 `/pages/memory.html`

**不在本环节范围内**：
- 删除三宫格「我的记忆」按钮（STEP-015）
- 按时间序取最近一条（TD-HOME-06，本期接受 doc_id 首条）

---

**完成标志**：
- [ ] 记忆卡数据与跳转正确
- [ ] STEP-012 → ✅

---

### [STEP-013] 「她的日记」预览卡

**目标**：日记预览卡：标题 + 固定句 + 相对时间 + NEW + Lv0 锁。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题 | STEP-003 ✅ |
| STEP-004 | level 来自 status（Lv0 锁） | STEP-004 ✅ |

---

**需要参考的文件**：
- `@frontend/static/js/api.js` — `formatTime`
- `@docs/contract.md` — `diary/list` 响应字段 `items`
- `@frontend/pages/index.html` STEP-012 卡片结构（版式参考，非硬依赖）

**需求原文引用**：
> 卡片标题「她的日记」
> ① 固定句「今天记录点什么好呢...」② `formatTime(created_at)`（R4 四档）
> 不展示正文摘要；`is_read === false` 显示 NEW；Lv0 显示锁（Q4），点击仍进 diary.html
> 日记列表为空：固定句仍展示；时间行隐藏或「—」；无 NEW
> 配图 `/static/images/Index/in_diary/diary_1.png`

---

**开发任务**：
1. 新增 `.home-diary-card`，含固定标题「她的日记」
2. 请求 `GET /api/diary/list?page=1&page_size=1`
3. 渲染固定句、时间行（`formatTime`）、NEW 角标、Lv0 锁图标（`level === 0` 来自 status）
4. 无日记条目时：仅固定句，时间行隐藏或显示「—」，不显示 NEW
5. 整卡点击 `/pages/diary.html`

**不在本环节范围内**：
- 删除三宫格日记入口（STEP-015）

---

**单元测试要求**：

| 场景 | 输入 | 预期输出 |
|------|------|---------|
| 有未读 | `is_read: false` | 显示 NEW |
| 无日记 | `items: []` | 固定句 + 时间隐藏或「—」 |
| Lv0 | `level: 0` | 显示锁图标，点击仍进 diary |

---

**完成标志**：
- [ ] 日记卡各状态（有/无/未读/Lv0锁）正确
- [ ] STEP-013 → ✅

---

### [STEP-014] 「关系状态」预览卡 + 删除横卡

**目标**：关系状态纵向预览卡；删除 `.home-rel-card`。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-004 | level_name 数据 | STEP-004 ✅ |
| STEP-012 | 卡片区 | STEP-012 ✅ |

---

**需求原文引用**：
> 副标题固定「你们的关系在慢慢升温」；等级 `level_name`（陌生/朋友/亲密/知己）；等级下无第二行（C15-C）
> C19-A：删除 `.home-rel-card`；亲密度仅在顶栏，等级仅在关系状态预览卡

---

**开发任务**：
1. 新增 `.home-relationship-card`，含固定标题「关系状态」+ 副标题「你们的关系在慢慢升温」+ API `level_name`（陌生/朋友/亲密/知己）
2. **删除**现网 `LEVEL_LABELS` 用于关系等级展示的逻辑；等级文案仅用 `d.level_name` 或 `LEVEL_NAMES[d.level]` 四级短名映射，**不用** `LEVEL_LABELS` 长句（C15-C）
3. 删除 DOM `.home-rel-card` 及相关专属样式（含 STEP-004 临时隐藏）
4. 整卡点击 `goToRelationship()` 或 `/pages/relationship.html`

**不在本环节范围内**：
- 三宫格删除（STEP-015）

---

**完成标志**：
- [ ] 页面无 `.home-rel-card`
- [ ] 关系状态卡展示正确
- [ ] STEP-014 → ✅

---

### [STEP-015] 删除三宫格 + 纵向滚动布局

**目标**：移除 `.home-feature-grid`；主内容区纵向可滚动。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-012 | 记忆卡 | STEP-012 ✅ |
| STEP-013 | 日记卡 | STEP-013 ✅ |
| STEP-014 | 关系卡 | STEP-014 ✅ |

---

**需求原文引用**：
> 改为 Hero 沉浸 + 下方卡片区可滚动（§4.1 #19）
> 三宫格拆为三张纵向预览卡；跳转 URL 不变

---

**开发任务**：
1. 删除 `.home-feature-grid` DOM 与样式
2. 调整 `.h5-home-main` / `.home-modules-panel` 为纵向滚动（`overflow-y: auto`）
3. 移除 `.home-layout-spacer` 等浅色版占位逻辑（若阻碍滚动）

**不在本环节范围内**：
- CTA 样式（STEP-016）
- 骨架屏（STEP-017）

---

**完成标志**：
- [ ] 无三宫格；三张预览卡纵向排列可滚动
- [ ] STEP-015 → ✅

---

### [STEP-016] 底部 CTA 改版与未读角标

**目标**：主文案「和她说说话吧」+ 副文案「她在等你哦」；保留未读角标。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-003 | 深色主题 | STEP-003 ✅ |

---

**需求原文引用**：
> C9：文案改为「和她说说话吧」+ 副文案「她在等你哦」，跳转 `/pages/chat.html` 不变
> 保留 `#unread-badge`、`GET /api/agent/unread-count`、`unread-badge--active` 呼吸动画

---

**开发任务**：
1. 更新 CTA 主副文案与渐变底栏深色样式
2. 确认 `unread-badge` 逻辑未破坏（`formatBadgeCount`、>99）
3. 跳转路径仍为 `chat.html`

**不在本环节范围内**：
- 五接口并行整合（STEP-018）

---

**完成标志**：
- [ ] CTA 文案与角标正常
- [ ] STEP-016 → ✅

---

### [STEP-017] 骨架屏适配新布局

**目标**：骨架屏结构匹配互动栏 + 三张信息卡（无关怀卡）；Hero 区不做骨架（PRD §4.1 #20 未要求）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-011 | 快捷栏 | STEP-011 ✅ |
| STEP-012–016 | 卡片区与 CTA | 均 ✅ |

> Hero 时钟/波形/Good night（STEP-007～010）可在本 STEP 之前或之后完成；骨架屏**不覆盖** Hero 细项，仅保持 Hero 区现有占位或空白。

---

**需求原文引用**：
> 扩展为互动栏 + 三张信息卡占位（无关怀卡）

---

**开发任务**：
1. 重写 `.skeleton-wrap`：快捷栏占位 + 3 张纵向卡占位
2. 删除 skeleton 对 `.home-rel-card`、三宫格行的依赖
3. `content-loaded` 切换逻辑保持不变
4. Hero 区：不新增时钟/波形骨架块（与 PRD 验收范围一致）

---

**完成标志**：
- [ ] 加载中骨架与互动栏+三卡布局一致
- [ ] STEP-017 → ✅

---

### [STEP-018] loadPage 五接口并行聚合

**目标**：`loadPage` 使用 `Promise.all` 并行请求五个接口，统一错误兜底。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-004 | status → 顶栏亲密度/头像/level | STEP-004 ✅ |
| STEP-005 | detail → known_days | STEP-005 ✅ |
| STEP-007 | resolveStatusText → 台词 | STEP-007 ✅ |
| STEP-012 | memory/list | STEP-012 ✅ |
| STEP-013 | diary/list | STEP-013 ✅ |
| STEP-016 | unread-count | STEP-016 ✅ |

---

**需求原文引用**：
> 并行请求：`relationship/status`、`relationship/detail`、`memory/list`、`diary/list`、`agent/unread-count`（§4.7）

---

**开发任务**：
1. 将 STEP-004/005/007/012/013/016 中分散的请求与 render 分支，合并为单次 `Promise.all([...])`（**不新增接口、不新增字段**）
2. 各模块独立 try/局部兜底（detail 失败不影响其他；`known_days` 显示「—」或隐藏）
3. 移除分散的重复请求
4. 保留页头 `checkLogin()`（N1）
5. 保留 `localStorage.setItem('relationship_level', level)` 与 `#progress-fill` 的 `transition: width 0.8s` 动画（契约既有行为）

---

**完成标志**：
- [ ] 网络面板仅一轮五请求
- [ ] 各模块渲染与 §5 边界表一致
- [ ] status 台词仍走 `resolveStatusText`
- [ ] STEP-018 → ✅

---

### [STEP-019] 契约测试与 contract 摘要同步

**目标**：更新 `test_index_html_home_surface_contract` 与 `contract.md` 文首首页摘要（N5）。

---

**前置条件检查**：

| 前置环节 | 功能名称 | 验证方式 |
|---------|---------|---------|
| STEP-001–018 | 全部首页改版 | 均 ✅ |

---

**需要参考的文件**：
- `@tests/test_h5_static_contract.py`
- `@docs/contract.md`
- `@docs/design/PRD-林小梦主页改版-v1.md` §7.1

**需求原文引用**：
> 与 `index.html` 同 PR 三联更新——`test_index_html_home_surface_contract` + `docs/contract.md` 文首首页摘要（废止 2026-05-23 旧摘要表述）

**§7.1 锚点**：
- **保留**：`unread-badge`、`/api/agent/unread-count`、`home-hero`、`index.png`、`linxiaomeng-avatar`、`status-text`
- **新增**：`updateAvatarEmotion`、`resolveStatusText`、`/api/relationship/detail`、`/api/memory/list`、`/api/diary/list`、CTA「和她说说话吧」
- **删除断言**：`home-rel-card`、`home-feature-grid`、`h5-home-decor::before`、theme `.home-rel-card .progress-bar` 渐变

---

**开发任务**：
1. 重写 `test_index_html_home_surface_contract` 断言列表（§7.1 锚点）
2. **复核** `test_settings_change_password_ids` 已在 STEP-002 迁移；本 STEP 全量跑静态测试确保无遗漏
3. 在 `contract.md` 文首追加 2026-06-10 首页深色改版摘要，废止 2026-05-23 旧首页摘要
4. 运行 `pytest tests/test_h5_static_contract.py` 通过（含 index + settings）

**不在本环节范围内**：
- 后端接口变更

---

**完成标志**：
- [ ] `test_index_html_home_surface_contract` 与新版 `index.html` 一致
- [ ] 全量 `test_h5_static_contract.py` 通过
- [ ] contract 摘要已更新
- [ ] STEP-019 → ✅，**本 PRD 拆解全部完成**

---

## 4. 自检清单

- [x] 需求文档 §4.1 各功能模块均有对应 STEP（不做项已标注排除）
- [x] 未增加 PRD 未定义功能（关怀卡/心情标签/游客模式等已排除）
- [x] 自定义字段（CSS 变量、DOM class）已标注 `[自定义]`
- [x] 不确定路径已标注「待查代码仓库/契约文档」
- [x] 关联 API 引用 `docs/contract.md` 已有定义
- [x] 环节依赖逻辑正确（api.js → settings+测试 → 各 UI 模块 → 聚合 → 契约）
- [x] 每个 STEP 含完成回调与 progress 更新指令
- [x] 进度文档 `docs/progress/林小梦主页改版-v1_progress.md` 已生成
- [x] 2026-06-10 已按 `林小梦主页改版-v1_steps-review.md` 修订（settings 测试、Hero 去重名、API 字段、依赖链）

---

## 5. 推荐执行顺序（最小互相影响）

```
并行轨 A：STEP-001 → STEP-002（含 settings 静态测试迁移）
并行轨 B：STEP-003 → STEP-004 → STEP-005
并行轨 C：STEP-003 → STEP-006 → STEP-007/008/009/010（007 依赖 001）
并行轨 D：STEP-003 → STEP-011
并行轨 E：STEP-003 → STEP-012 → STEP-013（可与 012 并行，仅依赖 003+004）→ STEP-014 → STEP-015
并行轨 F：STEP-003 → STEP-016

汇合：STEP-017 → STEP-018 → STEP-019
```

**测试预期**：STEP-003～018 期间 `test_index_html_home_surface_contract` 会失败；STEP-002 完成后 settings 测试应已通过；STEP-019 收官后跑全量 `test_h5_static_contract.py`。

同一文件 `index.html` 的多 STEP 建议**按编号串行合并 PR**，避免多人同时改同一区域产生冲突；不同轨（A 改 api.js、B/C/D/E/F 改 index 不同区块）可交错但合并时需 rebase 顺序：001→002→003→004…→019。
