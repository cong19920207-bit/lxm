# 项目契约文档

> 最后更新：2026-07-17 — 管理后台观察者与安全加固 v1 完成，正式进入五角色体系。

> 版本口径：本文后续保留的“最后更新：2026-07-16”长索引是历史生成纪要，不覆盖本页顶部 2026-07-17 最新契约与 observer 权威增量章节。

> **2026-07-17 摘要（管理后台观察者与安全加固 v1 正式同步）**：管理员角色体系扩展为五角色，新增 `observer`（展示名“观察者”）。observer 经完整 Admin JWT、账号状态、`token_version` 和数据库实时角色校验后，可读取已批准的后台业务数据，但 POST/PUT/PATCH/DELETE 默认 403，仅精确放行登出和自助改密；账号管理及操作日志/数据报表/系统日志三个内建导出继续拒绝。第三方凭据、用户 Open API Key 及 DashVector 凭据对 observer 仅返回配置状态，不返回原文或可推断片段。前端以 `isObserver()`、`applyObserverReadOnly()`、`data-write-action`、动态节点处理及 `adminRequest()` 请求兜底完成 35 页只读闭环，后端仍是最终权限边界。阶段 B 于 2026-07-16 17:02 CST 独立部署，收尾最终全量 pytest 918 通过 / 0 失败 / 4 跳过，35/35 页五角色浏览器验收、机器烟测和项目所有者稳定性确认通过。VULN-001、VULN-007、VULN-008 恶意锁号及其他明确延期项仍为已知未修。

> **2026-07-16 摘要（管理后台安全加固 · 阶段 A 正式同步）**：后台 JWT 密钥改为必须显式配置，缺失、空白及公开占位值在配置读取与应用启动时均被拒绝；`admin_users` 新增 `token_version INTEGER NOT NULL DEFAULT 0`，Admin JWT 携带并实时校验该版本及账号启用/锁定状态，历史无版本 Token 拒绝。登录使用 MySQL 行锁原子累计失败次数，第 5 次错误锁定并仅撤销一次会话；不存在账号、错密、锁定、停用统一返回 HTTP 200 / `20001` / `data:null` /「账号或密码错误」。锁定、自助改密、登出、重置密码、实际角色变化撤销旧会话，备注/相同角色/解锁不误撤销。`POST /api/admin/life-config/publish` 服务端强制精确 `confirm_text="CONFIRM"`，错误返回 `20021`，现有 7 个前端入口同步。操作日志写入与读取、系统日志读取/导出统一执行递归、幂等、失败关闭的凭据脱敏。阶段 A 于 2026-07-16 12:04 CST 独立部署，经机器烟测、稳定性观察及 `super_admin` / `ops_admin` 人工重新登录确认。角色体系仍为四角色，`observer` 尚未实现；VULN-001、VULN-007 与 VULN-008 恶意锁号风险仍为已知未修。

> **2026-07-13 摘要（管理后台 · 对话流 Prompt 侧栏 + 只读展示）**：侧栏新增可折叠分组 **「🗣️ 对话流 Prompt」**（`CHAT_PROMPT_MENU`，`super_admin` / `ai_trainer`）：**Step1.5 查询重写** / **Step3 Prompt 拼装** / **Step5 主对话** / **Step5.5 润色** / **Step5.5 开关** / **Step6 记忆拆解** / **Step8 Future 主动** / **Agent 主动 P0～P4**。其中 Step5/5.5 链到现有 **`prompt.html?tab=step5|step55`**（可编辑，方案 A）；Step6 链到 **`memory-rules.html`**（可编辑）；Step5.5 开关链到现有开关页。新增只读 API（无草稿/发布）：**`GET /api/admin/chat-prompt-view/step15|step3|step8|agent`**（实现 `chat_prompt_view.py` + `chat_prompt_view_service.py`，文案与运行时 `query_rewrite_service` / `prompt_builder` 同源常量一致）。只读页：`chat-prompt-step15.html` / `chat-prompt-step3.html` / `chat-prompt-step8.html` / `chat-prompt-agent.html`。**废止**一级菜单独立项「Prompt管理」「Step5.5开关」「记忆规则」（入口均收入本分组；直链旧 URL 仍可用）。原侧栏「🌿 生活宇宙」**改名为「🌿 生活流 Prompt」**；子项顺序改为：**生活计划 → 生活流人格拓展**（原「全局配置」，页 `life-feed-global.html` 顶栏同步改名）→ 朋友圈·内容 → 评论 → 感知 → 她的宇宙 → Prompt·生活流 → 发布&系统参数。分组标题字号与一级菜单统一 **14px**；二级 `.menu-sub` 字号 **14px**、`padding-left: 56px`。单测 **`tests/test_chat_prompt_view.py`**。无库表 DDL 变更。

> **2026-07-12 摘要（生活流正式合并）**：将 `docs/contract/drafts/生活流/` 下 **M1+M2+M3 契约草案**一次性合并进本文档——扩展既有表字段，新增生活流 8 表、用户端 `/api/feed/*`、感知 IM/SSE、定时任务、admin_config/环境变量、后台 6 路由 + 8 页 +「生活宇宙」菜单/RBAC（**侧栏展示名已于 2026-07-13 改为「生活流 Prompt」**，见上条）。正式条目见下文 **「生活流（朋友圈）」** 各节；草案目录保留作快照。关系档映射以代码为准：**`0→stranger / 1→friend / 2→intimate / 3→soulmate`**（知己；草案 M1 曾写 `confidant` 为笔误）。

> **2026-07-12 摘要（H5 朋友圈 · 话题着色 + 进页 boot）**：**`frontend/pages/feed.html`**（**不**改 `/api/feed/*` 与库表）。正文话题：**单 `#` 起标**着色至空格/标点（兼容 `#话题#`）；进页全屏 **`#feed-boot-loading`**（文案「正在进入她的生活…」）进度驱动 alpha/blur，列表+首屏图就绪后退场，**8s 硬超时**；无限滚动哨兵**延后挂载**（修复抢跑导致遮罩卡满 8s，**TB-LF-010**）。下拉刷新仍用骨架。细则见下文 **「生活流 · H5 `feed.html`」**（草案快照：`docs/contract/drafts/生活流/M1_契约草案.md`）。

> **2026-07-12 摘要（H5 记忆星云 · 表现层对齐实况）**：**`frontend/pages/memory.html`** 顶栏主标题 **`.bar-title`** 定为 **「记忆星云」**（浏览器 `<title>`：**「林小梦 - 记忆星云」**）；副标题 **`#nebula-count-subtitle`** 为 **「N 颗记忆星体」**。右上 **`#nebula-tip`** 为说明圆钮（Toast：「记忆根据你们的对话自动整理，目前仅供查看。」），**无**旧「对话自动整理 · 只读」大角标。脚本栈：**`three.min.js`（r149）** + **`three-line2.js`** + **`memory-connection-layer.js`** + **`memory-nebula.js`**。中心节点 id **`core-memory`**（卡片分类「她记得 · 记忆总览」）；卫星星点按 `key` 首段分色；关系线由 **`MemoryConnectionLayer`** 接管（`buildSelectLinks` / `clearSelectLines` 为契约锚点）。详情卡：**不展示 `key`**，标题由 `value` 首句截断（`titleFromValue`），正文 `value||content`，底栏「来自你们的对话」+「长期记忆」。底栏：手势提示 + **回到中心**；空态浮层「去和她聊聊」。**`#nebula-count-num`** 仍为 **hidden** 兼容锚点（可见计数以 subtitle 为准）。**不**改 `/api/memory/*` 与库表。静态 **`test_memory_html_nebula_surface_contract`**。**废止**「顶栏主标题为『她记得的你』」及「中心恒星文案『林小梦的记忆核』落屏」口径。

> **2026-07-12 摘要（朋友圈评论角标假数）**：**`feed_post`** 增 **`base_comments` / `comment_multiplier`**（迁移 **`v6e_display_comments_001`**）；历史帖默认 **0×1**（不回填，展示=真实可见条数）。新帖（LIFE001 / 后台手动）与点赞同范围随机写入。**`GET /api/feed/list`** 增 **`display_comments = base_comments × comment_multiplier + len(comments)`**；H5 **`feed.html`** 评论角标改用该字段，发评本地 **+1**。细则见下文 **「生活流」** 表/列表 API；单测 **`TestDisplayComments`**。

> **2026-07-12 摘要（H5 首页朋友圈卡 · 未读胶囊与正文间距）**：**`frontend/pages/index.html`** 朋友圈富预览卡表现微调（**不**改 `/api/feed/*` 与库表）。**`#feed-reply-pill`** 从标题行移出，置于 **`.home-feed-main`** 内绝对定位（`position: absolute`，`right: min(172px, calc(46% + 4px))`），叠在左文案与右双图夹缝；有未读时**不**顶开「朋友圈」标题与缩略图位置；无缩略图时贴右（`:has(.home-feed-thumbs:empty)`）。**`.home-feed-body`**：`margin-top: 6px`、`line-height: 1.7`（两行预览更疏）。**`renderFeedReplyPill`** 显隐逻辑不变。静态 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`** 增补锚点。**废止**「未读回复胶囊挂在 `.home-card-title-row` 内参与文档流」口径。

> **2026-07-12 摘要（H5 记忆星云 · Three.js 3D）**：**`frontend/pages/memory.html`** + **`memory-nebula.js`** 升级为 **Three.js r149**（本地 **`/static/js/vendor/three.min.js`**，约 **608KB / gzip ~153KB**）真 3D 星云：**中心恒星常驻**（节点 id **`core-memory`**；无用户记忆亦可环视）；周围星点来自分页拉齐 **`GET /api/memory/list`**；自动慢转（`prefers-reduced-motion` 关闭）+ 单指滑动环视 + 双指远近 + 点选详情抽屉；空态改为底部浮层（不遮挡星云）。后续表现层文案/连接线以文首 **「H5 记忆星云 · 表现层对齐实况」** 为准。**不**改 `/api/memory/*` 与库表。静态 **`test_memory_html_nebula_surface_contract`**。

> **2026-07-11 摘要（H5 记忆页 · 星云可视化）**：**`frontend/pages/memory.html`** 由只读卡片列表改为**全屏记忆星云**（**不**改 `/api/memory/*` 与库表）。脚本 **`/static/js/memory-nebula.js`**：分页拉齐 **`GET /api/memory/list`** → 哈希稳定落点 + 轻量斥力 → 按 `key` 首段分桶弱连线 → **Canvas 2D** 绘制；交互：单指平移、双指捏合缩放（clamp 约 **0.5×～3×**，自管 transform，不依赖浏览器页面缩放）、点选星点打开底部抽屉展示 `key`/`value`（无 key 退化 `content`）；顶栏标题「记忆星云」+ 只读角标「对话自动整理 · 只读」；空态引导去聊天。入口仍为首页快捷栏 / 聊天顶栏 → **`/pages/memory.html`**。静态 **`tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract`**。

> **2026-07-11 摘要（H5 首页快捷栏 · 记忆星云）**：**`frontend/pages/index.html`** — 快捷互动第三项由「一起听歌」改为 **「记忆星云」**；图标与聊天页同源 **`/static/images/chat/icon-memory-nebula.png`**（`.home-quick-icon img` 约 **22×22**）；点击 → **`/pages/memory.html`**（与 **`chat.html`** 顶栏记忆星云入口一致）。其余四项（语音通话 / 视频通话 / 陪我入睡 / 更多互动）仍 Toast「敬请期待」。**不**改后端接口/库表。静态 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`** 增补锚点。**废止**下文「快捷五项全部 Toast / 一起听歌」口径中与本条冲突的表述。

> **2026-07-11 摘要（H5 聊天页顶栏/气泡对齐设计稿）**：**`frontend/pages/chat.html`** — 顶栏改为**三块独立胶囊**（透明底，无整条毛玻璃条）：左 **返回圆钮** → **`/pages/index.html`**；中 **`.bar-profile`**（**`#chat-header-avatar`** 固定 **`default.png`** + 头像右下绿点 +「林小梦」+ 状态文案仅 **「在线」**）；右 **`.bar-actions`** 双图标无文案（竖线分隔）——朋友圈图标 **`/static/images/chat/icon-feed.png`**（透明底，自首页同款素材抠黑；**`goChatFeed()`**），记忆星云 **`/static/images/chat/icon-memory-nebula.png`**（透明底 PNG）→ **`/pages/memory.html`**；**删除** **`.more-btn`** / 「⋯」/「📖」。朋友圈角标 **`#feed-badge`**：**`loadChatFeedBadge()`** 调 **`GET /api/feed/badge`**，展示数 = **`unread_reply_count + new_post_count`**（合计 0 隐藏；**`formatBadgeCount`**）；点击：有未读回复 → **`/pages/feed.html?focus=unread_reply`**，否则 **`/pages/feed.html`**（与首页 **`goFeed`** 一致）；**`visibilitychange`** 回页刷新角标。气泡：用户 **半透明紫 + 白字**；AI **白玻璃 + 左下紫菱形光点**（**`::after`**）；头像约 **36px**。底栏：浮起玻璃面板 + 顶部 **handle 短横线（仅视觉）**；**`#send-btn`** 启用 **`#7C5CFF`** + 纸飞机 SVG，禁用仍 **`#D8D8DC`/`#8E8E93`**；placeholder **`想和我吐槽什么…`** 不变。**时间**：**`parseMessageTimestamp`** 对无时区 ISO（后端 **`utcnow` naive `isoformat`**）补 **`Z`** 按 UTC 解析；**`chat-time.js`** 自然日/文案一律 **`Asia/Shanghai`**（**`getBeijingParts`** / **`isSameBeijingDay`**）。**发送/SSE/防抖/未闭环窗口逻辑不变**。静态 **`tests/test_h5_static_contract.py::test_chat_html_immersive_surface_contract`**；时间 **`tests/test_chat_time.py`**。**废止**下文 **2026-05-23** 聊天沉浸摘要中「整条毛玻璃顶栏 / `.more-btn` / 绿发送钮」表述。

> **2026-07-11 摘要（H5 首页结构对齐设计稿）**：**`frontend/pages/index.html`** — 顶栏头像点击 → **`/pages/settings.html`**；右上胶囊改为粉心 + **`#relationship-level-name`**（陌生/朋友/亲密/知己）+ 进度，点击 → **`goToRelationship()`**；**删除**「关系状态」预览卡；朋友圈改为富预览卡（正文/双图/更新时间/底栏新动态引导 + 未读回复胶囊；**未读胶囊布局以 2026-07-12「H5 首页朋友圈卡 · 未读胶囊与正文间距」为准**）；日记卡保留，换 3D icon；底部 CTA/未读角标**不变**；快捷五项中第三项「记忆星云」见上条 **「H5 首页快捷栏 · 记忆星云」** 摘要（原「一起听歌」口径废止）。**`GET /api/feed/badge`** 增补 **`new_post_count`**（与 `has_new` 同源，对齐 list 可见窗；从未 enter 时 `new_post_count=0`）；首页 **`loadFeedHomeCard`** 并行 badge + **`GET /api/feed/list?size=8`**；聊天页亦消费同一 badge（角标求和，见上条摘要）。细则见下文 **「生活流 · GET /api/feed/badge」**。静态 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`**；**`tests/test_step015_feed_service.py`**。

> **2026-06-14 摘要（H5 未闭环窗口本地态修复）**：**`frontend/pages/chat.html`** — 新增 **`getOpenWindowUserRows()`**，与后端 **`chat_service.fetch_open_window_user_rows`** 对齐：以最后一条**已落库** assistant（**非** `.agent`、**非** `data-ai-in-flight="1"`）为界，其后的 user 行为**未闭环窗口**。**`countOpenPendingUsers`** 仅统计该窗口内 **`pending_llm` / `failed_timeout` / `failed_error`**（**不**扫全历史 user）。**`markOpenWindowUsersDelivered`** 在 SSE **`done`** 中**先于** **`finalize()`** 调用（`finalize` 后本轮 AI 已在列表末尾，若在之后标记则窗口 user 无法标 **`delivered`**，会导致下轮误弹「待处理消息过多」）。**`resend`** 成功时同一函数将窗口内 **`failed_*`** 标 **`delivered`** 并移除叹号。**`failed_blocked`** 仍**不**纳入前端叹号/预判（与 **TD-030** 一致）。**10104** / 前端满队预判时仍调用 **`loadTimeline(true)`**（仅追加 timeline，**非**完整自愈，见 **POST /api/chat/send**「H5 实现说明」）。单测 **`tests/test_h5_chat_open_window.py`**；静态锚点 **`tests/test_h5_static_contract.py`**。

> **2026-06-14 摘要（H5 首页全屏加载页 · PRD v1.8 增量）**：**`frontend/pages/index.html`** 在深色沉浸主页（v1.7）之上新增 **全屏首屏加载层** **`#home-loading-screen`**（**不**改后端接口/库表）。**门闩**：并行预载静态图 **`index.png`**、**`loader_avatar.jpg`**、**`sunset.png`**、**`diary_1.png`**、**`default.png`** + 情绪头像（**`AVATAR_MAP[ai_current_emotion]`**，预载完成后 **仅一次** **`updateAvatarEmotion`**）+ **`loadPage`** 五接口 **`Promise.allSettled`**；且 **`elapsed ≥ 3000ms`**；进度至 **100%** 后再固定停留 **500ms** 退出。**Session**：**`sessionStorage.lxm_home_loader_done`**；同浏览器标签内再次进入 **`index.html`** **跳过**全屏加载（仍 **`loadPage`** 刷新数据）；**`performance.navigation.type === 'reload'`** 清除标记并重走加载；**`api.js` `clearToken()`**（登出/401）清除标记。**加载页 DOM**：**`#home-loading-hero`**（`index.png` 随进度提亮/去模糊）；**`#loading-avatar`** → **`/static/images/Index/loader_avatar.jpg`**（加载专用图，**非**顶栏情绪图）；**`.loading-avatar-ring`** 渐变环 + **`.loading-avatar-ripple`** 双圈波纹；品牌 **「林小梦」** + 副标题 **「正在靠近你的世界」**；底部 **`#home-loading-message`** 轮播三句（我在。别急。/ 马上就见面了。/ 来了？我等你一会儿了。）。**`loadPage({ deferAvatar: true })`** 加载期间不触发顶栏换图；API 完成后 **`#main-content.content-loaded`**（**`.skeleton-wrap`** 仍作失败兜底）。**退出过渡（A+）**：加载层 **`is-exiting`** 淡出 + 主页 **`is-enter-reveal` → `is-enter-active`** 轻 fade + **`home-enter-item`** 七段 stagger（**`--enter-delay` 0.1s～0.6s**）；**`html:has(#home-loading-screen)`** / **`html:has(.h5-home-page.is-enter-reveal)`** 强制深色底 **`#0a0a1a`** 防白闪。**`api.js`**：**`updateAvatarEmotion`** 同步更新 **`#linxiaomeng-avatar`** 与 **`#loading-avatar`**（若存在）。**`prefers-reduced-motion: reduce`** 关闭粒子/波纹/过渡动画。静态 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`** 增补 **`#home-loading-screen`**、**`loading-avatar-ring`**、**`is-enter-reveal`**、**`lxm_home_loader_done`** 等锚点。
>
> **2026-06-10 摘要（H5 首页深色沉浸改版 · PRD v1.7）**：**`frontend/pages/index.html`** — 深色夜景 + 玻璃拟态局部样式（**不**改 **`h5-theme.css`** 全局）。顶栏：**`#linxiaomeng-avatar`** + **`updateAvatarEmotion`** +「林小梦」+ **`#known-days`**（**`GET /api/relationship/detail` → `milestones.known_days`**）+ 右侧亲密度胶囊（星标 + **`#progress-fill` / `#progress-info`**，点击 **`/pages/settings.html`**）；**移除** **`#user-initial`**、独立 ⚙️、中部 **`.home-rel-card`**、三宫格 **`.home-feature-grid`**。Hero：**`index.png`** 夜景遮罩 + 大字号北京时间时钟（**`getBeijingDate`** / **`Asia/Shanghai`**）+ 月亮 icon + 时段词 + 大字号引号 **`#status-text`**（**`resolveStatusText`**，**`api.js`** 上收 **N4**）+ Good night 装饰 + 波形纯装饰；**不展示**「她此刻的心情」标签（C12）。快捷栏 **`.home-quick-actions-wrap`** 玻璃条内 **`.home-quick-actions`** 5 项（**2026-07-11** 起第三项为「记忆星云」→ **`/pages/memory.html`**，见文首「H5 首页快捷栏 · 记忆星云」；其余仍 Toast「敬请期待」）。**一屏布局**：**`body.h5-skin` + `.h5-home-page`** **`height`/`max-height:100vh`**、**`overflow:hidden`**；**`.home-hero`** 高约 **44vh**（小屏 **40vh**）；**`.h5-home-main`** **`margin-top:-30px`** 叠压 Hero；**`.home-cards-scroll`** **`overflow:hidden`**（**不**纵向滚动，废止 PRD §4.1 #19「卡片区可滚动」实现口径）。三张纵向预览卡：**记忆**（左图标+标题副标题；右 **`#memory-preview`**+缩略图；**`GET /api/memory/list?page=1&page_size=1`**，**`list[0].value||content`** 截断 ~40 字）、**日记**（左标题+NEW+副标题「记录她的心情和生活」；右 **`#diary-preview`** + **`.home-card-meta-row`**（**`#diary-time`** + Lv0 **`#diary-lock`**）+ 缩略图；固定句 +「刚刚写下 ·」+ **`formatTime`**）、**关系**（左标题+副标题；右 **`.home-card-right--rel`** 内 **`#relationship-level-name`** + **`.home-card-chevron`**；四级 **`level_name`**，无暧昧副文案 C15-C）。底部 CTA **`.home-cta-btn`**「**和她说说话吧**」+ 副文案「她在等你哦」+ **`.home-cta-arrow`**；**`#unread-badge`** / **`GET /api/agent/unread-count`** 不变。**`loadPage`** 五接口 **`Promise.allSettled`** 并行（加载页门闩亦等 API settle；见 **2026-06-14** 摘要）。静态 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`**；状态语 **`tests/test_h5_static_contract.py::test_settings_change_password_ids`** 断言 **`api.js`**。**废止**下文 **2026-05-23 首页摘要** 中横卡/三宫格/装饰球/隐藏头像等表述。
>
> **2026-06-05 摘要（P0–P4 主动消息 Step5 解析对齐）**：**`agent_service.generate_and_save_message`** 改走 **`llm_service.chat_with_step5_parse`** + **`merge_messages_if_exceed`**，从 **`messages[]`** 拼 **`agent_message.content`**；解析/HTTP 失败与人格风险兜底使用 **`AGENT_FALLBACK_REPLIES[trigger_type]`**，**不再**误用对话 **`DEFAULT_FALLBACK`（走神）** 或 **`admin_config.fallback_reply`**。FUTURE/Step8 链路不变。单测 **`tests/test_agent_generate_step5.py`**；本地验证脚本 **`scripts/verify_agent_p1_p4_docker.py`**。

> **2026-06-05 摘要（管理端日期筛选统一 · 阶段 C）**：**`backend/services/admin_date_filter.py`** 现由 **`users.py`（conversations / emotion-rounds）**、**`admin_diary_query.py`（diaries / diary-history）**、**`agent_mgmt.py`（agent-messages）** 共用；**`start_date > end_date`** 统一 **20029**。单测 **`tests/test_admin_user_conversations.py`**、**`tests/test_admin_date_filter.py`**；日记 API 增补反选日期用例。

> **2026-06-05 摘要（管理端历史对话 · 日期筛选 + 首屏最近）**：**`GET /api/admin/users/{user_id}/conversations`** 与 **`GET .../emotion-rounds`** 的 **`start_date` / `end_date`** 与日记/主动消息列表对齐：**`start_date`** → `created_at >= 当日 00:00:00`；**`end_date`**（闭区间日历日）→ `created_at < end_date + 1 day`；**`start_date > end_date`** → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`（20029）**；实现 **`backend/services/admin_date_filter.py`**。接口排序仍为 **`sort_seq` 升序**分页。**`admin/pages/user-detail.html` 历史对话 Tab**：日期输入默认 **近 7 天**；查询/首屏先取 `total` 再拉 **最后一页**（区间内最新 20 条）；顶部 **「加载更早」** 向更旧翻页（`page - 1`，prepend）。

> **2026-06-04 摘要（H5 对话队列死锁修复）**：未闭环窗口 **≥5 条且全部为 `pending_llm`（无叹号）** 时，**`POST /api/chat/send`** 返回 **10104** 前会 **`trigger_recovery_if_queue_stuck`** 后台补跑 **`_execute_llm_bundle`**（Redis 锁 **`chat:bundle:lock:{user_id}`**，TTL **90s**）；**`generation` 在 LLM 前/后已变** 时同样调度恢复 bundle；**`GET /api/chat/timeline`** 首屏（**无 `cursor`**）亦触发同一恢复逻辑。H5 本地 **`done`→`delivered`** 细则见 **2026-06-14「未闭环窗口本地态修复」** 摘要；**10104** JSON 响应移除本地气泡并 **`loadTimeline(true)`**（追加拉取，非完整自愈）。Open **`open_send`** 与 H5 共用 **`chat_service`** 恢复逻辑。单测 **`tests/test_chat_queue_deadlock_verify.py`**。

> **2026-06-04 摘要（Open API v1 · PRD-OpenAPI-APIKey-v1）**：新增表 **`user_api_keys`**；环境变量 **`OPEN_API_PEPPER`**（≥32，缺失拒绝启动）；6 个 **`/api/open/v1/*`** 接口（同步 JSON）；Admin **`GET|POST /api/admin/users/{user_id}/open-api-key`**；写路径迁至 **`chat_service`**、timeline 迁至 **`timeline_read_service`**；错误码 **10108**；集成文档 **`docs/design/open-api-v1.md`**。详见下文 **「Open API v1」** 模块。

> **2026-05-30 摘要（记忆检索与 Prompt 优化升级 · PRD v6.1 一次发布）**：四类向量记忆检索与 Prompt 称呼模块整体升级，全部在同一 PR 合并（C21）。**Step1.5（`query_rewrite_service`）**：`QueryRewriteOutput` 由 7 字段扩为 **13 字段**——四路各含 `QueryQuestion`/`QueryKeywords`/`CandidateKeys`，其中 **`CharacterPrivate*` 为新增独立一组**（不再复用 Global）；校验改为 **JSON 解析成功即 `success=True`，四路全「无」是合法成功态**（C1，删除「至少一组非空抛错」）；入参 **`last_user_text` 重命名为 `rewrite_input`**（C25，三处调用点同步：`chat.py`、`step8_subchain.py`、内部 fallback）；主链 Prompt 用户消息标题改为 **「【用户本轮消息（可能多段，换行分隔）】」+ 综合理解说明**，Step8（`source="step8"`）保持原 **「【用户当前消息】」**（C17/C19/C20）；【任务】追加 HyDE 陈述句规则 / CandidateKeys 规则 / 四路分类参考 / 4 条 Few-shot；【关系状态】仍保留「用户称呼」行（C13）。**主链（`chat.py`）**：新增 `BUNDLED_MAX_CHARS=4000` + `_truncate_bundled()`（尾部 4000 字符）；`bundled = "\n".join(...)` 上移至 Step1.5 调用前，`bundled_truncated` 供 **Step1.5 `rewrite_input` 与降级 `fallback_embedding` 共用**；Step5 `build_chat_prompt(user_input=bundled)` 仍传整包；删除死变量 `last_user_text`（C39）。**Step2（`multi_vector_retrieval_service`）**：改为 **per-route 主路 + 2.5 补充路**；`_should_skip()`（空串/「无」跳过，C10）；`character_private` 使用独立 Question 的 Embedding（不复用 cg）；主路 `search(..., candidate_keys=该路CandidateKeys, top_k=热配)`；补充路触发 `should_trigger_supplement`（`count<2 OR max_score<0.75`，常量 **`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`** C2/C7），Keywords 空则跳过补充（C11），补充路 `candidate_keys=[]`、`top_k=3`、阈值沿用热配（C34/C36），合并去重→score 降序→**固定 Top3 写回各路 `*_results`**（C12/C37）；`MultiVectorRetrievalResult` 新增 **`skipped_routes`**（路名用 memory_type 常量值），C1 四路全无属成功态 **`is_fallback=False`**；降级路径不变（4 路同一 fallback embedding、不加 key_l2）。**DashVector（`dashvector_client`）**：新增统一 **`build_filter(memory_type, user_id, candidate_keys)`**（双引号 + 值内 `"` 转义，已验证合法 C9/C27/C32），`search()` 新增 `candidate_keys: list[str] = []` 默认参数并内部走 `build_filter`（老调用方零改动 C33/C34）。**Step6（`memory_llm_service`）**：`upsert_step6_vectors` 写入 fields 新增 **`key_l1` / `key_l2`**（中文字符串直存，doc_id 仍 hash）；Step6 Prompt 中 `UserRealName` / `UserHobbyName` 提取触发条件明确化（11 字段 JSON 结构不变）。**Admin（`character_knowledge_service`）**：抽取 **`_build_knowledge_fields(key, content)`**（含 `key_l1`/`key_l2`），`create_entry` 与 `update_entry` 共用，**update 必须补写**（C15，不赌 Upsert 字段保留）；`list_entries` filter 由单引号 `type = '...'` 改为 **`build_filter(mt, None, [])`** 双引号（C33）；后台列表展示与门禁不变。**Prompt（`prompt_builder`）**：新增 **`user_nickname` 模块**（`_build_user_nickname_prompt`，直接取 `relationship_info`，C16；三分支 + 全空返回 `""`），`MODULE_ORDER` 插入 **recent_chat 之后、user_input 之前**（C8）；有称呼时主链为 **10 段**（含模块 A 时），无称呼为 **8～9 段**（见 STEP-021 历史条目的 ⚠️ 注记）。`MODULE_TOKEN_LIMITS["user_nickname"]=50` **代码硬编码**（C30），**不在 `TRIM_PRIORITY` 中即绝不裁剪**；**`prompt_token_config` 热配不覆盖** `user_nickname`（`PUT` Body 无该字段；`_load_token_limits` 忽略库内同名键）。`_build_relationship_prompt` **移除「亲密称呼/用户真名」两行**（两处分支，C3）；`build_step8_prompt` 同步 user_nickname（同主链位置，C4）；`build_active_message_prompt` 在 **relationship 之后、memory 之前** 插入（Agent 无 recent_chat，C14/C26）；`step5_5` 不改动（C22）。**测试**：`tests/test_query_rewrite_service.py`、`tests/test_multi_vector_retrieval_service.py`、`tests/test_step024_step8_subchain.py`、`tests/test_prompt_builder.py`（模块顺序含 `user_nickname`）、**`tests/test_dashvector_client.py`**（`build_filter` 四场景）。**技术债**：**TD-022**（mem_* 与 Step6 同池）、**TD-026**（存量向量无 key_l1/key_l2）、**TD-027**（补充路触发阈值与 top_k 未热配）；**TD-017** 查询改写层已部分由 Step1.5 实现，完整 HyDE/多策略仍待评估。
>
> **2026-05-29 摘要（H5 设置页 Profile 卡对齐设计稿）**：**`frontend/pages/settings.html`** Profile 卡二次微调 — **`.profile-card`** 去描边、柔阴影（**`0 8px 28px rgba(124,58,237,0.10)`**）、星点装饰略降 opacity；**`#profile-status`** 改为 **`.profile-status-text`** **纯文字**（无白底胶囊）；底行状态语与 **`.profile-wave`** 同行 **`align-items: center`**；**`.profile-online`** 增加浅底 pill（**`rgba(255,255,255,0.55)`**）；**不**展示陪伴天数。业务脚本与接口**不变**。
>
> **2026-05-29 摘要（H5 设置页软 UI 改版）**：**`frontend/pages/settings.html`** — **`body`** 增加 **`settings-soft-page`**（局部覆盖 neo 黑边：白卡轻阴影、粉紫渐变底；**不**改 **`h5-theme.css`** 全局）。**Profile 卡**：**`#linxiaomeng-avatar`** + **`updateAvatarEmotion(ai_current_emotion)`**；**`GET /api/relationship/status`** 驱动状态语（优先 **`status_text`**，否则 **`EMOTION_STATUS_MAP[ai_current_emotion]`**，兜底「今天状态不错，继续陪伴你吧~」）；固定「● 在线」。**关于林小梦**：手风琴首次展开 **`GET /api/app/persona-background`** 懒加载 **`background`**（后台 **`admin_config` persona 生效版**）。**改密码 / Toggle / 退出** 业务脚本与接口路径**不变**（Toggle 仍调 **`/api/user/settings`**，改密码仍 **`POST /api/auth/reset-password`**；已知缺口见 **TD-024**、**TD-025**）。静态 **`tests/test_h5_static_contract.py::test_settings_change_password_ids`**；接口单测 **`tests/test_app_persona_background.py`**。
>
> **2026-05-29 摘要（H5 关系页 · 今日成长横排）**：**`frontend/pages/relationship.html`** — **拍立得**：**`rotate(-8deg)`**；相框 **`padding-bottom: 5px`** + 竖图 **84×108** + **`img translateY(-8px)`**，caption **11px** 极窄底边，多露出照片区域。**今日成长**：**`.rel-today-grid`** 由 2×2 改为 **横排四列 `display:flex`**（**`.rel-task-card`** **`flex:1`**）；右下角未完成 **`.tc-foot`** 紫色 **13px**「X分」；已完成 **`.tc-done`** 绿色纯字（**无**胶囊 **`.done-tag`**）。四项副文案：**还差获得 X 分** / **聊够10分钟可获得+20分** / **今日登录 +5** / **回复可获得+10分**；第四项标题 **「回复消息」**；顶部总计文案仍为 **「今日总计 +N 亲密值」**。Hero / 亲密进度 / 成长历程 / 成长记录 / 接口不变。静态 **`tests/test_h5_static_contract.py::test_relationship_html_surface_contract`** 增补锚点。
>
> **2026-05-26 摘要（H5 关系页改版）**：**`frontend/pages/relationship.html`** — **`body`** 增加 **`relationship-page`**（暗黑沉浸，**`html:has(> body.relationship-page)`** 铺 **`#050508`** 底，**不**沿用全站 neo 白卡；去掉固定 **`top-bar`**，改为 **`.rel-hero`** 主图 **`/static/images/relationship/Relationship_Lxm.png`** + 透明 **`.rel-hero-bar`**（返回 + 胶囊「我们的关系」）；**`.rel-hero-profile`**（**`bottom: 50px`**）展示「林小梦」+ **`.rel-level-badge`**（**`level_info.name`**）+ **`level_info.description`** + **`level_info.perks`**；**`.rel-hero-foot`** 底行留空占位。**`.rel-main`**：**`margin-top: -50px`**（相识时间、亲密进度、今日成长、成长历程、成长记录整体上移；**不**再动 Hero 信息区）。**拍立得** **`.rel-polaroid`**：**`rotate(-8deg)`** 逆时针；竖图 **84×88**；caption **「想和你去看海。」** 单行 **`white-space: nowrap`**；**`#linxiaomeng-avatar`** 绑 **`updateAvatarEmotion(ai_current_emotion)`**。**亲密进度**：标题行 **✦** + 手写「继续加油哦~ ♡」**`#progress-section .rel-handwrite { transform: translateX(-50px) }`**（**`max-width: 360px`** 时为 **`-28px`**）；进度条 **13px** 纯紫填充；解锁行仅 **`>`** 视觉（点击仍展开 **`next_perks`**）。**今日成长**：**`.rel-today-grid` 2×2**；**`.tc-status` 右下** 分数/已完成。四列统计无单位；**成长历程** / **成长记录**逻辑不变。升级弹窗暗黑肤；接口不变。静态 **`tests/test_h5_static_contract.py::test_relationship_html_surface_contract`**。
>
> **2026-05-17 摘要**：AI 日记 M2a 手动批跑提供仓库脚本 **`scripts/run_diary_batch.py`**（入口 **`python -m scripts.run_diary_batch`**），与 **`DiaryService.run_daily_diary_task`** 同源；命令与语义见 **`docs/ops-diary.md`** §3。
>
> **2026-05-16 摘要**：AI 日记 Cron 改为 **`Asia/Shanghai`**（与 `diary_rules.generation_hour/minute` 一致）；对话统计窗为上海锚点日 **D** 的 **[D−1 00:00, D 00:00)**；表 **`ai_diary.covers_beijing_date`**（北京覆盖日）；`GET /api/diary/list` 的 **`items[]`** 含 **`covers_beijing_date`**；管理端 **`diary-history`** / **`users/{id}/diaries`** 的 **`list[]`** 含 **`covers_beijing_date`**（日期筛选仍按 **`created_at`**）；`PUT /diary-rules` 的 **`generation_hour`** 合法范围 **0–23**（北京时间）。
>
> **2026-05-23 摘要（H5 聊天居中时间戳）**：**`frontend/static/js/chat-time.js`** 提供 **`formatChatTime`** / **`shouldShowTimeStamp`** / **`getChatTimeOptions`** / **`setChatTimeOptions`**（自然日、**>5 分钟或跨日** 插戳、周一起算、**zh/en** + **hour12** 配置，默认 **zh** 24 小时）。**`chat.html`** 仅展示居中 **`.msg-time-divider`**（**不再**在气泡内显示时间）；消息行 **`data-created-at`**；**`insertTimelineBatch`** 处理首屏与上拉 prepend 边界；乐观发送用客户端 **`Date.now()`**。失败叹号 **`.msg-bang`** 仍在气泡左侧，**`align-items: center`** 垂直居中（**业务逻辑不变**）。**`api.js` 的 `formatTime`** 仍供记忆页等使用。**接口与发送/SSE/防抖不变**；单测 **`tests/test_chat_time.py`**。**时区补记（2026-07-11）**：展示与自然日改为 **`Asia/Shanghai`**；见文首「H5 聊天页顶栏/气泡对齐设计稿」摘要。
>
> **2026-05-23 摘要（H5 聊天页沉浸改版）**：**`frontend/pages/chat.html`** — **`body`** 增加 **`chat-immersive`**（**`h5-theme.css`** 中聊天 neo 规则仅作用于 **`body.h5-skin:not(.chat-immersive)`**，其它 H5 页不变）。全屏背景 **`.chat-bg`**（**`#chat-bg-image`** + 25% 黑遮罩（无背景模糊）；**`background-position: center 72%`**）；情绪联动改由页内 **`updateChatBackgroundEmotion(emotionLabel)`** 切换 **`AVATAR_MAP`** 同路径静态图（来源不变：**timeline 末条 AI `data-emotion` / SSE `done.emotion.label`**），**不再**调用 **`updateAvatarEmotion`**。Agent 未读条沉浸深色半透明样式。**接口与发送/SSE/防抖逻辑不变**。**顶栏 / 气泡 / 发送钮表现层以 2026-07-11「H5 聊天页顶栏/气泡对齐设计稿」为准**（废止本条中「整条毛玻璃顶栏 / `.more-btn` / 绿发送钮 `#A6FF7B`」表述）。
>
> **2026-05-23 摘要（H5 日记页改版）**：**`frontend/pages/diary.html`** — **`body`** 增加 **`diary-page`**（仍含 **`h5-skin`**）；去掉固定 **`top-bar`**，改为 **`.diary-hero`**（**`background-image: /static/images/diary/dary_ri.png`**，高约 **45vh**，底渐变接 **`#f3f0ff`**）；返回钮 **`.diary-hero-bar .back-btn`**：**位置/尺寸与 `chat-top-bar .back-btn` 一致**（**36px**、顶栏 **`padding: calc(safe-area + 8px) 12px 10px`**）；视觉为 **`#B8A8F0` 45%** 半透明 + 内描边 + **8px** 外发光 + SVG 左箭头（**`history.back()`**）。列表 **`.diary-main`** **`margin-top: calc(-17vh + 60px)`**（小屏 **`max-height:640px`** 时 **`-40px`**）与头图渐变叠压。列表 **`.diary-card`** 为白卡轻阴影（**不再**挂全局 **`.card`** neo 边）；左栏 **英文月 / 日 / 中文星期 / 装饰 SVG**（**`weekday % 4`** 轮换，无业务含义）；右栏仅 **正文 3 行截断 +「继续看 >」/「收起」**（**无**头像、昵称、时间、心情标签）；点击整卡就地展开，展开未读时 **`POST /api/diary/{id}/read`**。未读：**淡紫描边 + 左上细紫条 + 右上角点**（非橙色）。空态/错误态/主按钮在 **`body.diary-page`** 下换肤；**接口与分页/空态等级分支逻辑不变**。静态资源 **`tests/test_h5_static_contract.py`** 允许多类名 **`body`**。
>
> **2026-05-23 摘要（H5 首页改版）**：**`frontend/pages/index.html`** — 布局为 **`.home-hero`**（**`background-image: /static/images/Index/index.png`**）+ **`.home-rel-card`** 关系横卡 + **`.home-feature-grid`** 三功能卡 + 底部 **「进入聊天」** 渐变胶囊；顶栏叠在 Hero 上（左 **`#user-initial`** 半透明圆钮、右 **设置** **`/pages/settings.html`**）。**`#linxiaomeng-avatar`** 节点保留 **`display:none`**，首页不再调用 **`updateAvatarEmotion`**。未读角标 **`#unread-badge`**、**`#status-text`**、**`GET /api/relationship/status`** / **`GET /api/agent/unread-count`** 语义不变；进度条 **`#progress-fill`** 仍 **`transition: width 0.8s`** 动画，主题填充 **`linear-gradient(90deg, #3b82f6, #ec4899)`**（**`h5-theme.css`** **`.home-rel-card .progress-bar`**）。黄/粉装饰球 **`.home-hero .h5-home-decor::before/::after`** 保留 **`h5-wiggle` / `h5-float-y`**，坐标锚定 Hero。**`prefers-reduced-motion: reduce`** 下关闭装饰与未读呼吸。静态断言 **`tests/test_h5_static_contract.py::test_index_html_home_surface_contract`**。
>
> 最后更新：2026-07-16 — **管理后台安全加固阶段 A**（密钥双守卫、`token_version` 会话撤销、原子登录锁定与统一失败响应、life-config 服务端 CONFIRM、操作/系统日志凭据脱敏、独立部署与人工稳定性确认；角色仍为四角色）。—— 2026-07-13 — **管理后台 · 对话流 Prompt 侧栏 + 只读展示**（文首摘要：`CHAT_PROMPT_MENU`、只读 API `chat-prompt-view/*`、生活流侧栏改名/子项重排）。—— 2026-07-12 — **已读感知用户级冷却**（`read_aware_user_cooldown_hours` 默认 6；按入队 `created_at` 滚动，窗口内最多 1 条 `READ_AWARE`；后台「生活流 Prompt · 互动」可配）。—— **生活流正式合并**（M1+M2+M3 草案并入本文「生活流」各节；草案目录保留快照）。—— **H5 朋友圈 · 话题着色 + 进页 boot**（单 `#` 着色、`#feed-boot-loading` 渐进透明度、哨兵延后 / TB-LF-010；见文首摘要）。—— **H5 记忆星云 · 表现层对齐实况**（顶栏标题「记忆星云」、副标题「N 颗记忆星体」、连接线层 + 详情卡只读文案；见文首摘要）。—— **H5 首页朋友圈卡 · 未读胶囊与正文间距**（`#feed-reply-pill` 绝对定位夹缝、正文下移/行距；见文首摘要）。—— **H5 记忆星云 · Three.js 3D**（中心记忆核 + 自动慢转 + 滑动环视；见文首摘要）。—— 2026-07-11 — **H5 记忆页 · 星云可视化**（Canvas 2D，已被上条覆盖）。—— **H5 首页快捷栏 · 记忆星云**（「一起听歌」→「记忆星云」+ 同源 icon → **`/pages/memory.html`**；见文首摘要）。—— **H5 聊天页顶栏/气泡对齐设计稿**（三块胶囊顶栏、朋友圈/记忆星云入口与 badge 求和角标、紫气泡/紫发送、北京时间戳；见文首摘要）。—— **H5 首页结构对齐设计稿**（头像→设置、右上等级→关系、删关系卡、朋友圈富预览；**`GET /api/feed/badge.new_post_count`**；见文首摘要）。—— 2026-06-14 — **H5 未闭环窗口本地态修复**（文首摘要：`getOpenWindowUserRows`、`done` 先于 `finalize` 标 `delivered`；单测 **`tests/test_h5_chat_open_window.py`**）。—— **H5 首页全屏加载页**（文首摘要：门闩 3s+500ms、Session 跳过、双头像、`loader_avatar.jpg`、A+ 入场；**`loadPage` 改为 `allSettled`**；静态测试锚点增补）。—— **2026-06-10** — **H5 首页一屏布局与预览卡 DOM 对齐**（文首摘要增补：Hero 44vh、主内容叠层、卡片区不滚动；日记/关系预览右栏化；静态测试增补 **`.home-card-meta-row`** 等锚点）。—— **H5 首页深色沉浸改版**（见文首 2026-06-10 摘要；废止 2026-05-23 首页摘要中横卡/三宫格/装饰球表述）。—— **2026-06-05** — **P0–P4 主动消息 Step5 解析对齐**：`agent_service` 生成链路改用 `chat_with_step5_parse`（见上条摘要）。—— **管理端历史对话与日期筛选（A/B/C）**：`backend/services/admin_date_filter.py` 统一 **conversations / emotion-rounds / diaries / diary-history / agent-messages** 的 `start_date`/`end_date`；**user-detail.html** 历史对话 Tab 默认近 7 天、末页首屏、「加载更早」；单测 **`tests/test_admin_user_conversations.py`**。—— 2026-05-31 — **长记忆第一套下线与 Step6 运营收敛（PRD v1.3 一次发布）**：H5 `GET /api/memory/list` 改只读 KV（删 `PUT/DELETE/POST` 写路由 + `schemas/memory.py`）；新增 Admin `user-memories`/`private-settings`（主键 `doc_id`，删旧 `/users/{id}/memories*`）；`memories/global` 改向量检索（可选 `user_id`、`truncated`、R-01 300 上限 / P9 500 cap）、`batch-delete` 改 `{doc_ids}`；新增 `GET/PUT /api/admin/step6-memory-prompt`（保存即发布，6 块 + 11 `task_fields`），删 `memory-rules` API（C-08）；`build_step6_prompt` 异步化 + Redis→DB→DEFAULT 三级回退（DEFAULT 逐字复刻，P6）；下线第一套写入（删 `extract_and_save` 调用 + 物理删危险函数，其余 `@deprecated`）；`memory_injected` 恒 null（仅历史字段，M11/P7）；召回侧（`multi_vector_retrieval_service`/`agent_service`）确认**不过滤 `mem_*`**（P1，靠 M2 人工清理）；前端 `memory.html` 只读、`settings.html`「记忆整理」只读说明、`user-detail.html` 用户记忆+私有状态 Tab、`memory-rules.html` 三 Tab（Step6 Prompt 默认/向量库/全局用户记忆）。详见各模块条目与 `docs/progress/长记忆第一套下线与Step6运营收敛_progress.md`。—— 2026-05-30 — **记忆检索与 Prompt 优化升级（PRD v6.1 一次发布）**：Step1.5 输出 13 字段 + `rewrite_input` + C1 校验、Step2 2.5 路融合 + `skipped_routes` + `build_filter` 双引号、Step6/Admin 写入 `key_l1`/`key_l2`、Prompt 新增 `user_nickname` 模块（relationship 删称呼），详见「2026-05-30 摘要」。—— **2026-05-29** — **H5 设置页 Profile 卡**对齐设计稿（状态语纯文字、在线浅底 pill、卡片柔阴影无描边，见「Profile 卡对齐设计稿」摘要）。—— **H5 设置页软 UI 改版** + **`GET /api/app/persona-background`**（见「H5 设置页软 UI 改版」摘要）。—— **H5 关系页**：拍立得 **-8deg** + 极窄底边（**84×108**）、今日成长 **横排四列** + **`.tc-done`** 状态样式 + 任务文案（见「2026-05-29 摘要」）。—— **2026-05-26** — **H5 关系页**三次微调：**`.rel-main` 上移 50px**、亲密进度手写左移、拍立得 **-8deg** + caption「想和你去看海。」（见摘要）。—— **2026-05-26** — 关系页设计稿二次对齐（四宫格/进度条/拍立得等）。—— **2026-05-24** — **Step6 / 角色知识库 doc_id 与三层 key 改造**：DashVector `doc_id` 统一为 `{type}_{sha256(key)[:12]}_{user_suffix}`（`user_suffix=0` 或 `user_id`）；KV **key 强制三层 `XXX-XXX-XXX`**；向量 `fields` 新增 **`stable_key`**；`dashvector_client.upsert` 解析响应体失败信息；公共工具 **`backend/utils/character_knowledge_validate.py`**；单测 **`tests/test_character_knowledge_validate.py`**、**`tests/test_dashvector_upsert_response.py`**；**旧记忆 `mem_*` 路径不变**。—— **STEP-027 角色知识库 CRUD**（`GET|POST|PUT|DELETE /api/admin/character-knowledge`，DashVector 直写；页面 **`admin/pages/knowledge.html`**；错误码 **20047–20052**；单测 **`tests/test_admin_character_knowledge.py`**）。—— **2026-05-23** — **H5 日记页表现对齐参考图**（见「2026-05-23 摘要（H5 日记页改版）」）。—— **H5 聊天居中时间戳（微信式分组 + 叹号垂直居中）**（见「2026-05-23 摘要（H5 聊天居中时间戳）」）。—— **H5 聊天页沉浸表现对齐参考图**（见上条摘要）。—— **H5 首页表现对齐参考图**（见「2026-05-23 摘要（H5 首页改版）」）。—— **2026-05-17** — **H5 全站表现层刷新**：新增 **`frontend/static/css/h5-theme.css`**（neo 粗线边、偏移阴影、粉紫渐变页背景、装饰微动效、气泡入场等），各用户端页面 **`body` 增加 `class="h5-skin"`** 并在 **`common.css` 之后** 引入 **`/static/css/h5-theme.css`**；**`frontend/static/css/common.css`** 中全局色板微调（如 **`--color-primary`**、**`--color-bg`**）与主题协调。**不修改接口与业务脚本逻辑**。**`chat.html`** 中 **`#send-btn`** 的 **禁用态** 仍为 **`#D8D8DC` / `#8E8E93`**（页面内联规则保留；主题层仅对 **`:not(:disabled):not(.disabled)`** 覆盖启用态渐变）。**`prefers-reduced-motion: reduce`** 下关闭装饰、气泡入场、**`h5-page-fade`**（**`.page-body`**、**`.h5-home-main`**）等动画。**`h5-theme.css` 补充**：**`html:has(> body.h5-skin)`** 与 **`body.h5-skin`** 同铺渐变底，避免 overscroll 露白；关系页 **`.progress-section` / `.today-section` / `.timeline-section` / `.log-section`**、记忆 **`.add-panel` / `.memory-edit`**、聊天 **`.msg-bang` / `.levelup-tip` / `.thinking-bubble`** 等 neo 线框与阴影增强。静态锚点单测 **`tests/test_h5_static_contract.py`**。—— **2026-05-11** — **H5 `chat.html` 输入与发送钮**：`#msg-input` **`enterkeyhint="send"`**（软键盘回车键语义贴近「发送」，**具体标签文案以系统/WebView 为准**）；**`updateSendBtn`** 按 **`trim`** 同步 **`#send-btn`** 的 **`disabled` 属性** 与 **`.disabled`**，禁用态背景 **`#D8D8DC`**、符号 **`#8E8E93`**（对齐系统键盘「发送」置灰态），有内容时 **`#send-btn`** 启用态由 **`h5-theme.css`** 表现为 **渐变主钮**（与原先 **`var(--color-primary)`** 填充圆钮等价：**可点**）。**——** **H5 `chat.html` 发送键焦点**：`#send-btn` 为 **`type="button"`**，**`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听内 **`preventDefault`**，减轻点发送时 **`#msg-input`** 失焦导致的移动端键盘自动收起；**`handleSend`** 仍由 **`click`** 触发。**——** **H5 `chat.html` 发送（流控）**：移除全局 **`sending`**；**`send`** 与叹号 **`resend`** 共用 **`lastSendOrResendAt` + `CHAT_SEND_DEBOUNCE_MS`（300ms）** 静默防连点（通过内容非空与 **`countOpenPendingUsers`** 预判后再打时间戳）；**`oncompositionend`/`onkeyup`** 同步 **`updateSendBtn`**。细则见 **POST /api/chat/send**「H5 实现说明」。**——** **管理后台认证契约补全与自助改密**：拆分 **`POST /api/admin/auth/logout`** 与 **`POST /api/admin/auth/change-password`**；change-password Body **`AdminChangePasswordRequest`**（`old_password`、`new_password`、`confirm_password`，与 `schemas/admin_auth.py` 一致）；成功 **`code=0`**、**`message`**「密码修改成功」；失败 **20004**（旧密码不正确）、**20005**（新密码与旧密码相同）、**20006**（两次新密码不一致）、**20007**（密码强度不符，与 **`_validate_admin_password`** 一致）；**`admin/static/js/admin-api.js`** **`renderHeader`** 在「退出登录」左侧提供「修改密码」，**`showChangePasswordModal`** 经 **`adminRequest`** 提交改密，成功 Toast「密码已修改，请重新登录」后 **`clearAdminToken`** 并跳转 **`/admin/pages/login.html`**（与 **`accounts.html`** 对自身仅「修改备注」、对他人「重置密码」互补）。—— **2026-05-10** — **管理后台系统日志**：`GET /api/admin/system/logs` 的 `data.list` 按 `time` **降序**；`admin/pages/system-logs.html` 分页回调 **`window.systemLogsGoPage_system`** / **`window.systemLogsGoPage_error`** + **`renderPagination`**；单测 **`tests/test_system_monitor_logs.py`**。—— **H5 `chat.html`（续）**：与首段摘要一致，完整见 **POST /api/chat/send**「H5 实现说明」。**`LLM_TIMEOUT`（通用 LLM HTTP）默认 45s**：`get_llm_timeout_seconds()` 读取环境变量 **`LLM_TIMEOUT`**，未配置时默认 **45**（与 **`LLM_TIMEOUT_CHAT`** 默认一致）；适用于日记生成、记忆提取 LLM、Agent 主动消息、后台配置测试集（`chat_with_parse` 未传超时）、`chat_stream`、`chat_sync` 未显式传 `timeout_sec` 等——详见 **「部署与网关（对话 SSE）」** 下 **环境与通用 LLM HTTP 超时**。2026-05-08 — **SSE 等待上限语义（与代码一致）**：`_BUNDLE_WAIT_TIMEOUT_SEC`（默认 **120s**，`backend/routers/chat.py`）仅作用于 `_sse_chat_wait_bundle` 内 `asyncio.wait_for` 对本代 `generation` Future 的等待；**不**等价于 `_execute_llm_bundle` 整段服务端墙钟的数学上界。Step1.5、Step5 等经 `llm_client.chat_sync` 时内层至多 **3 次** HTTP（`LLM_MAX_RETRIES=2`），单次 `timeout_sec` 由调用方传入（Step1.5 **45s**、Step5 默认 **`LLM_TIMEOUT_CHAT` 45s**），叠加 **1s、2s** 退避后，**单段子调用**在极端全超时场景下即可 **超过 120s**；整链再串 Step2、Step5.5 等后，**可能出现 SSE 已结束等待而后台 `_execute_llm_bundle` 仍在执行**——属客户端等待与后台调度**解耦**，**120s 非产品硬指标**。详见 **「部署与网关（对话 SSE）」** 与 **POST /api/chat/send**。**Step1.5 查询重写（STEP-019）**：`query_rewrite_service._STEP1_5_TIMEOUT_SEC` **45s**；业务层整轮「LLM+解析」**仅 1 次**，失败即 R-L1L3-12 `_fallback_with_embedding`；`llm_client.chat_sync` 单次 HTTP 同 **45s**，内层仍最多 **3 次** POST + 1s/2s 退避。**Step6 记忆 LLM 超时**：`step6_orchestrator._STEP6_LLM_TIMEOUT_SEC` 由 **15s 调至 45s**（固定常量，非环境变量；异步不阻塞 SSE）。**STEP-026**：管理后台 Step5 / Step5.5 Prompt 与 **`step5_5_enabled`** 总开关——运行时 **`step5_system_prompt`**（JSON `{"content"}`）热加载模块1 System；**`step5_5_prompt_fragments`** 六段模板 + **`backend/services/step5_5_prompt_fragments.py`** 占位符与发布校验；**废弃**旧 **`prompt_modules`** 七模块接口；**`POST /api/admin/prompt/test`** 改为 **`PromptBuilder.build_chat_prompt`**（与主链一致，`use_draft` 覆盖 Step5 System）；页面 **`admin/pages/prompt.html`**、**`admin/pages/step5-5-switch.html`**；RBAC **`super_admin`+`ai_trainer`**；单测 **`tests/test_step026_prompt_config.py`**。**STEP-025**：管理后台 **`GET|PUT /api/admin/configs/vector_retrieval_config`** 与 **`GET|PUT /api/admin/configs/prompt_token_config`**（Body 为部分字段 PATCH，与库中生效值及代码默认合并后走 `admin_config_service.publish_config`；Redis `active_config:{key}`；RBAC `super_admin`+`ai_trainer`；错误码 **`20046`** `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`；页面 **`admin/pages/vector-token-config.html`**（双 Tab）；单测 **`tests/test_admin_vector_token_config.py`** 6 条）。**STEP-024 勘误**：Step8 子链路 Step1 装载方式为「同一 `AsyncSession` 内顺序查询」最近对话（库内至多取 20 条、下游使用末 10 轮）+ relationship + emotion，**禁止**对同一 session 使用 `asyncio.gather` 并行 IO（与 SQLAlchemy 异步会话约束一致）；对外接口、表结构、Future 消费语义不变。**同日**：Admin 用户详情 **GET /api/admin/users/{user_id}/conversations** 合并 `conversation_log` 与 `agent_message`（按 `sort_seq`、`id` 升序，与 H5 `GET /api/chat/timeline` 时间线一致；字段见「管理后台用户管理」）。2026-05-05 起 STEP 纪要：（**STEP-024**：Step8 子链路——新增 `backend/services/step8_subchain.py`：`execute_step8_subchain(user_id, future_action)` 实现 Future 槽到期后完整主动消息子链路（Step1 顺序装载 + Step1.5 变体（输入用 `future.action` 替代 `last_user_text`，降级路径用 `future.action` 生成单 Embedding）+ Step2 多路向量检索 + Step3 变体（`PromptBuilder.build_step8_prompt()` 将【用户消息】替换为【主动发起】模块含 `future.action` 摘要）+ Step5 LLM 调用（含内容安全检查与人格偏离检测）+ Step5.5 可配低概率触发（`STEP8_GATE_A_PROBABILITY=0.03`）→ 写入 `agent_message` 表（不走 SSE）→ Step6 异步记忆总结 → `proactive_times` +1 → 衰减门控 `0.15^(proactive_times+1)` 概率写入下一轮 Future 预约）；`prompt_builder.py` 新增 `_build_proactive_input()` 与 `build_step8_prompt()` 方法；`step5_5_service.py` `should_trigger_step5_5()` / `execute_step5_5()` 新增 `gate_a_override` 参数支持外部覆盖门闩 A 概率；`future_handler.py` `_consume_one()` 中占位调用 `generate_and_save_message(FUTURE)` 替换为 `execute_step8_subchain()`；`tests/test_step024_step8_subchain.py` 10 条、`tests/test_step023_future_handler.py` 修正为 14 条单测全部通过。**STEP-023**：Future 槽消费轮询 Handler。**STEP-022**：proactive_times 计数/清零 + 频控调整（R-FUT-03 / §2.2 变更 8.2）——`chat.py` `POST /api/chat/send` 入口新增 proactive_times 清零逻辑（用户发新消息时将 `relationship.proactive_times` 置 0）；`agent_service.py` 频控参数调整：每日上限 2→8（含 Future 槽消费计入）、两次间隔 6h→30min；`generate_and_save_message` 成功后 proactive_times +1（上限 3）；新增 `increment_agent_count_for_future()` 方法供 STEP-023 Future 槽消费后计入 `agent:count` 计数器；新增 `reset_inactive_proactive_times()` 方法实现 30 天无活动自动清零（清空 proactive_times + Future 槽）；`scheduler.py` Agent 扫描间隔 6h→30min、新增每日凌晨 1:00 UTC 30 天无活动清零定时任务；`tests/test_step022_proactive_times.py` 18 条单测全部通过。**STEP-021**：Step3 Prompt 新增模块 + Token 裁剪（R-L1L3-19）——`prompt_builder.py` 重构为 9 模块结构：新增模块 A「角色设定与知识」（`_build_character_knowledge_prompt()`，合并 `character_global`+`character_private`+`character_knowledge` 三路检索结果，超限按 DashVector score 从低到高逐条裁剪）插入 Persona 后 Relationship 前；模块 B「时间与活动」（原 `_build_time_prompt()` 重新定位）插入 Emotion 后 Recent Chat 前；`MAX_TOTAL_TOKENS` 5200→7373；`MODULE_TOKEN_LIMITS` 全部更新（system 720 / persona 1080 / character_knowledge 600 / relationship 360 / memory 900 / emotion 270 / time_activity 80 / recent_chat 1800 / user_input 900）；新增 `_load_token_limits()` 从 `admin_config:prompt_token_config` 热加载各模块上限（缺省回退默认值）；`_trim_to_budget()` 实现 5 级裁剪优先级（recent_chat→memory→character_knowledge→relationship 扩展→time_activity，System/Persona 绝不裁）；`_build_memory_prompt()` 兼容 Step2 dict 列表和 ORM 实例；`build_chat_prompt()` 新增 `retrieval_results` 参数接收 Step2 四路检索结果；`chat.py` `_execute_llm_bundle` 传递 `retrieval_result.format_for_prompt()` + `user_memory_results`（dict 列表替代旧 `_MemoryProxy`）；`tests/test_prompt_builder.py` 30 条（含新增 STEP-021 场景：全量注入无裁剪、超限裁剪优先级、模块 A score 裁剪、热配覆盖默认、9 模块顺序验证、空结果跳过等）。**STEP-020**：Step2 多路向量检索（R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21）——新增 `backend/services/multi_vector_retrieval_service.py`：`MultiVectorRetrievalResult` dataclass（4 路检索结果 + `top_k`/`threshold`/`is_fallback` 元数据，提供 `all_results`/`user_memory_results`/`format_for_prompt` 属性）；`execute_multi_vector_retrieval()` 主入口：正常路径阶段① `asyncio.gather` 并行 3 Embedding（CharacterGlobal / CharacterKnowledge / UserProfile）→ 阶段② `asyncio.gather` 并行 4 DashVector 检索（`character_global` 无 user_id + `character_private` 有 user_id + `character_knowledge` 无 user_id + `user` 有 user_id），CharacterGlobal Embedding 复用于 `character_global`+`character_private` 两路；降级路径（Step1.5 失败）用 `fallback_embedding` 执行全部 4 路（R-L1L3-12）；热配置 `admin_config:vector_retrieval_config`（`{"top_k":3,"threshold":0.7}`）支持运行时调整 TopK/阈值（R-L1L3-17）；`chat.py` `_execute_llm_bundle` 集成 Step1.5（`execute_query_rewrite`）+ Step2（`execute_multi_vector_retrieval`），删除旧 `user_embedding = await _get_embedding(last_user_text)` 及关联 `_search_memories` 调用（R-L1L3-21），`_persona_text` 前提获取后复用至 Step6（消除重复 Redis 读取）；`tests/test_multi_vector_retrieval_service.py` 新增 6 条单测（正常 3+4 并行、降级 1+4、降级无 Embedding、部分路 0 命中、热配 TopK=5、无配置回退默认）。**STEP-019**：Step1.5 查询重写 LLM（R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14）——新增 `backend/services/query_rewrite_service.py`：`QueryRewriteOutput` Pydantic 模型（7 字段：`InnerMonologue` + 3 组 `QueryQuestion`/`Keywords`）、`QueryRewriteResult` dataclass（`success` + `output` + `fallback_embedding`）；`_build_step1_5_prompt()` 拼装 7 模块（系统指令 + 时间活动 + 人格 + 关系 + 近期对话 + 用户消息 + 任务含输出 Schema）；`execute_query_rewrite()` 主入口（**timeout=45s**；业务层 **不重试**；`chat_sync` 内层仍最多 3 次 HTTP + 1s/2s 退避）；`_parse_query_rewrite_output()` 解析 JSON 并校验至少一组 QueryQuestion 非空；`_fallback_with_embedding()` 降级路径用 `last_user_text` 通过 `embedding_service.get_embedding` 生成单 Embedding 作为统一 fallback（R-L1L3-12：不触发叹号，用户无感）；结构化日志含 `user_id`、失败原因、链路来源（`source="main"/"step8"`）；`tests/test_query_rewrite_service.py` 新增 7 条单测（场景1 三组 Query 完整、场景2 超时即降级+日志、场景3 InnerMonologue 仅内存、边界非法 JSON 降级、解析与 Prompt）。**STEP-018**：Step1 并行装载扩展（R-L1L3-01 / R-L1L3-06）——`chat.py` 新增 `_build_round_context()` 辅助函数，在 `_execute_llm_bundle` 中 `_get_relationship` 读取后构建本轮内存上下文 dict（含 `time_description`、`activity_description`、`relation_description`、`user_real_name`、`user_hobby_name`、`user_description`、`character_purpose`、`character_attitude`、`level`、`level_name`、`silence_days`），扩展字段 NULL 时用占位文案（`relation_description` 默认 `"暂无，初次互动"`，其余默认空串）；`round_context` 在 Step5.5 和 Step6 调用处共用同一份（不重复 SELECT）；`POST /api/chat/send` 的 `asyncio.gather` 中移除 `_get_relationship`（无下游消费的重复 SELECT）；`prompt_builder.py` 的 `build_chat_prompt` 新增可选 `round_context` 参数，`_build_time_prompt` 优先使用预计算值（避免重复调 `_generate_time_description` / Redis 读 `activity_schedule`）；`tests/test_step018_round_context.py` 新增 10 条单测。**STEP-017**：`prompt_builder.py` 新增 `get_activity_description()` 异步函数（R-L1L3-11）：从 Redis `active_config:activity_schedule` 读取静态 JSON，按当前小时段匹配活动描述文案，未配置/未命中/解析失败返回空字符串；`_build_time_prompt()` 改为 async，条件性注入活动描述（空串时跳过该行）；`build_chat_prompt()` 对应 await 调用；`tests/test_prompt_builder.py` 新增 9 条单测（时间描述精确场景 + 活动描述匹配/未配置/未命中/非法JSON/Redis异常/条件注入）。**STEP-016**：`backend/services/step6_orchestrator.py` 新增 `Step6Snapshot` + `execute_step6`（§2.8.4 M2 半异步）：`chat.py` 在 Step5 解析成功、内容安全通过且 `_persist_bundle_success` 落库后 `asyncio.create_task(execute_step6(snapshot))` 入队，不阻塞 `_resolve_generation_future`/SSE；快照含 `merge_messages_if_exceed(step5_result.messages)`（≤5，CP1）、`round_id`、打包用户原文、`persona`（Redis `active_config:persona` 未命中则 `DEFAULT_PERSONA`）、关系等级名与 relationship 扩展列读快照、近期对话 `{role,content}` 列表、Step5 `future`；管线：`build_step6_prompt` → `llm_client.chat_sync`（**45s** 固定常量 `_STEP6_LLM_TIMEOUT_SEC`，非 `LLM_TIMEOUT_CHAT`）→ `parse_step6_output` → `upsert_step6_vectors`（STEP-014）→ 独立 session 加载 `relationship` 后 `RelationshipService.update_relationship_from_step6`（STEP-015）并 `commit`；失败 sleep **500ms** 再试，**共 2 次**仍失败则 ERROR 日志结束，不影响客户端；入队 try/except 失败仅日志；`tests/test_step016_step6_orchestrator.py` **6** 条通过；**未**实现管理后台 Step6 失败监控（STEP-028）。**STEP-015**：`relationship_service.py` 新增 `update_relationship_from_step6(relationship, step6_output, round_id, *, future_time_natural, future_action)` 方法（R-MEM-05 / §2.8.4）——6 个标量字段（`UserRealName`→`user_real_name`、`UserHobbyName`→`user_hobby_name`、`UserDescription`→`user_description`、`CharacterPurpose`→`character_purpose`、`CharacterAttitude`→`character_attitude`、`RelationDescription`→`relation_description`）：值非「无」→ UPDATE 覆盖 + 调用 `RelationshipHistoryService.append_history` 写入变更历史（含 old_value），值为「无」→ 跳过赋值保留旧值；Future 槽：action 为「无」→ 清空 `future_timestamp`+`future_action`，`time_natural` 非「无」→ 调用 `parse_future_time` 解析（成功→写入 `future_timestamp`+`future_action`，失败→清空槽位+保留 `proactive_times`+写 warning 日志）；所有历史记录 `trigger_source='step6'` 携带 `round_id`；`tests/test_step015_relationship_step6.py` 11 条单测全部通过；**已由 STEP-016 在 `chat.py` 主链异步入队调用。****STEP-014**：`memory_llm_service` 增补 Step6 四路 DashVector 写入（R-MEM-04）——`parse_kv_lines()` 按换行拆行、首处全角冒号拆 key-value，空 key/value 或无冒号行丢弃；`upsert_step6_vectors(output, user_id)` 对 `CharacterPublicSettings`/`CharacterPrivateSettings`/`CharacterKnowledges`/`UserSettings`：值为「无」整路跳过，否则逐行 `embedding_service.get_embedding(value)` + `dashvector_client.upsert`；`doc_id`=`{memory_type}:{stable_key}:{user_id或空}`；`character_global`/`character_knowledge` 不写 `user_id` 字段，`character_private`/`user` 写 `fields.user_id` 且 doc_id 含用户后缀；`content` 存「key：value」全文；`tests/test_step6_vector_upsert.py` 22 条通过；**已由 STEP-016 在 `chat.py` 主链异步入队调用。****STEP-013**：新增 `backend/services/memory_llm_service.py` 实现 Step6 记忆总结 LLM 的 Prompt 拼装与 JSON 解析（R-MEM-01 / R-MEM-06 / R-MEM-07 / §2.5）——`Step6MemoryOutput` Pydantic 模型（驼峰命名，11 字段：`InnerMonologue` + 4 类可检索记忆 `CharacterPublicSettings`/`CharacterPrivateSettings`/`CharacterKnowledges`/`UserSettings` + 6 类标量 `UserRealName`/`UserHobbyName`/`UserDescription`/`CharacterPurpose`/`CharacterAttitude`/`RelationDescription`）；`parse_step6_output()` 解析规则：JSON 不合法→抛 `Step6ParseError`，字段缺失→默认「无」（`InnerMonologue` 默认空串）；`build_step6_prompt()` 拼装 8 模块（系统指令 + 时间 + 人格 + 关系状态 + 近期历史 + 本轮对话 + 任务 + §2.5 完整 few-shot），本轮 AI 回复数据来源仅为 Step5 产出的 `messages`（非 Step5.5 润色后，§2.9.3）；`tests/test_memory_llm_service.py` 30 条单测全部通过。不含 relationship 标量更新（STEP-015）、异步入队（STEP-016）。**STEP-012**：内容安全兼容新结构化输出（§9.1 / §9.3）——`chat.py` 新增 `_check_messages_safety()` 逐条检测 `messages[].content`（任一违规→整轮失败，user 行标 `failed_blocked`，不进 Step5.5，不入队 Step6）、`_check_inner_monologue_safety()` 检测 `inner_monologue`（违规仅日志+替换空串，不拦截整轮，避免污染 Step6 记忆）；Step5.5 输出也经逐条安全检测（违规→回退 Step5 合并后 messages）；`constants.py` 新增 `DELIVERY_STATUS_FAILED_BLOCKED = "failed_blocked"`；`tests/test_step012_content_safety.py` 10 条单测覆盖全通过/第 N 条违规整轮失败/inner_monologue 违规替换/Step5.5 违规回退。**STEP-011**：`conversation_log` 多气泡落库（§2.8.1 / §2.8.3）——`_persist_bundle_success` 接收 `messages` 列表（原 `ai_reply` 单条拼接），按 `len(messages)` 一次性 `allocate_sort_seq(user_id, count=N)` 分配连续 `sort_seq`，写入 N 行 `role=assistant`（每行 `content` = `messages[i].content`，与本包 user 行共享同一 `round_id`）；后置任务仍用 `ai_reply="\n".join(...)"`；`GET /api/chat/timeline` 沿用 `sort_seq` 合并排序，升序展示与气泡顺序一致；`tests/test_chat.py` 新增 `TestStep011MultiBubblePersist` 4 条并修正 STEP-008 单测入参。**STEP-010**：SSE 协议扩展（多气泡流式）——`_sse_chat_wait_bundle` 重写：首包 `meta` 新增 `message_count`（§2.9.4 CP2），`delta` 事件按 `message_index` 分条推送，`done` 事件携带完整 `messages` 数组（真相源 §2.7.5）+ 整轮 `emotion`（§2.7.3）；H5 `appendAIThinkingBubble` 重构为多气泡渲染器（不预铺空气泡，`delta` 动态创建槽位，`done` 纠偏定稿）、`consumeChatSse` 适配新字段。**STEP-009**：新增 `backend/services/step5_5_service.py` 实现 Step5.5 响应润色完整链路——`should_trigger_step5_5()` 双门闩 OR 触发判定（总开关 `admin_config` key=`step5_5_enabled` + 门闩 A 12% + 门闩 B 仅 `knowledge_expand="是"` 时 50%）、`build_step5_5_prompt()` 按 `step5_5_prompt.md` 全文拼装、`parse_step5_5_output()` 校验 JSON 数组 + type="text" + content 非空、`execute_step5_5()` 含 30s 独立子超时（§2.7.4 D2）与失败回退；`chat.py` `_execute_llm_bundle` 接入 Step5.5（Step5 成功后调用，成功则覆盖 `final_messages`，失败/未触发则回退 Step5 合并后 messages；Step6 入参快照 `step6_messages` 始终取 Step5 原始 messages 合并结果，不受 Step5.5 影响（R-BND-05））；`tests/test_step5_5.py` 新增 32 个单测（总开关关闭、门闩 A 命中、门闩 B 命中、非法 JSON 回退、超时回退、7 条合并到 5 条等）。**STEP-008**：`chat.py` `round_id` 提前至 Step5 成功时生成（§2.9.3），`_persist_bundle_success` 改为接收外部 `round_id` 不再自行生成，SSE Future payload 新增 `round_id` + `step6_messages` 供 Step6 入队使用；`_BUNDLE_WAIT_TIMEOUT_SEC` 55→120（§2.11.2）；Nginx `proxy_read_timeout` 已为 300s 满足 ≥130s 要求；`tests/test_chat.py` 新增 `TestStep008RoundId` 3 条单测并修复 `test_chat_send_stream_response` 对 `chat_with_step5_parse` 的 mock。**STEP-007**：`backend/utils/future_time_parser.py` 实现 `parse_future_time()` / `is_future_slot_valid()`（§2.8.4，UTC 基准，3 种正则 +「无」→ None；失败 `logger.warning` 结构化日志）；`tests/test_future_time_parser.py` 单测 22 条。**STEP-006**：`constants.py` 新增 `MAX_MESSAGES_COUNT=5` / `MAX_SINGLE_MESSAGE_LENGTH=2000` 消息合并常量；`llm_service.py` 新增 `merge_messages_if_exceed()` 纯函数（§2.9.1，>5 条时将第 6 条起 content 半角空格拼入第 5 条，超长尾部截断+日志）；`chat.py` `_execute_llm_bundle` 接入消费点 1（纯 Step5 路径合并）与消费点 3（Step6 入参快照 CP1，变量 `step6_messages` 预留），SSE payload `step5.messages` 改为合并后版本。**STEP-005**：`llm_service.py` Step5 输出 JSON 解析器 + 校验规则（§2.7.7 / CP3 / U1 / U2 / R-BND-02），新增 `Step5Output` Pydantic 模型（6 字段扁平结构）+ `parse_step5_output()` 解析函数 + `chat_with_step5_parse()` 方法；`chat.py` `_execute_llm_bundle` 替换旧 `chat_with_parse_strict` 调用，不再读取 `reply` 字段，改为拼接 `messages[].content`；SSE payload 新增 `step5` 完整结构化数据。**STEP-004**：`prompt_builder.py` Step5 提示词改造（R-BND-13 / §2.7.9），`SYSTEM_PROMPT_TEXT` 替换为新 6 字段 JSON Schema（inner_monologue / messages / relation_change / future / emotion / knowledge_expand）+ few-shot 示例 + 【知识性话题回应原则】新增；`_build_relationship_prompt()` 尾部追加 4 行扩展字段（relation_description / user_description / user_hobby_name / user_real_name）；新增【当前时间】模块（`_generate_time_description()`）；hint 文字与主动消息 Schema 同步更新；`MODULE_TOKEN_LIMITS["system"]` 400→1200，`MAX_TOTAL_TOKENS` 4096→5200。**STEP-003**：DashVector type 常量 + search/upsert 签名扩展（R-L1L3-08 / R-L1L3-15 / R-VEC-01），`constants.py` 新增 4 类 `MEMORY_TYPE_*` 常量，`dashvector_client` 的 `upsert()` / `search()` 支持 `memory_type` 参数与 type 过滤。**STEP-002**：新增 `relationship_change_history` append-only 历史表（R-L1L3-05），Alembic 迁移 `v4b_step002_001`，`RelationshipHistoryService.append_history()` 仅 INSERT。**STEP-001**：`relationship` 表新增 9 个扩展字段——记忆写回 6 字段 + Future 槽 3 字段，Alembic 迁移 `v4a_step001_001`。2026-04-13 及更早：H5 对话 TD-015、SSE `meta.generation_id`、`resend`、timeline 等见历次说明。）

本文档依据当前仓库内 FastAPI 路由、Pydantic Schema 与 SQLAlchemy Model 扫描生成；SSE/文件流接口的 HTTP 层不包在统一 JSON 信封内，已单独标注。

---

## 数据库表结构

### 表名：users


| 字段名                | 类型          | 必填  | 默认值    | 说明                               |
| ------------------ | ----------- | --- | ------ | -------------------------------- |
| id                 | Integer PK  | 是   | 自增     | 用户 ID                            |
| username           | String(20)  | 是   | -      | 唯一索引（`unique=True`，ORM）            |
| password_hash      | String(255) | 是   | -      | 密码哈希                             |
| created_at         | DateTime    | 是   | utcnow | 注册时间                             |
| last_login_at      | DateTime    | 否   | NULL   | 最后登录                             |
| relationship_level | Integer     | 是   | 0      | 关系等级 0–3（与 relationship 表存在并行字段） |
| growth_value       | Integer     | 是   | 0      | 成长值（与 relationship 表存在并行字段）      |
| is_banned          | Boolean     | 是   | False  | 是否封禁                             |
| login_fail_count   | Integer     | 是   | 0      | 连续登录失败次数                         |
| locked_until       | DateTime    | 否   | NULL   | 锁定截止时间                           |
| last_feed_entered_at | DateTime  | 否   | NULL   | 最近进入朋友圈时间（生活流；`POST /api/feed/enter` 写 **`feed_now()`** 北京墙钟；用于 `has_new`） |


### 表名：relationship


| 字段名                    | 类型                   | 必填  | 默认值    | 说明       |
| ---------------------- | -------------------- | --- | ------ | -------- |
| id                     | Integer PK           | 是   | 自增     |          |
| user_id                | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`，`index=True`） |
| level                  | Integer              | 是   | -      | 关系等级 0–3 |
| growth_value           | Integer              | 是   | -      | 成长值      |
| last_interaction_at    | DateTime             | 否   | NULL   | 上次互动     |
| consecutive_login_days | Integer              | 是   | 0      | 连续登录天数（ORM `default=0`） |
| updated_at             | DateTime             | 是   | utcnow | `onupdate=utcnow` |
| relation_description   | Text                 | 否   | NULL   | 关系描述（R-MEM-05，Step6 记忆写回） |
| user_real_name         | String(50)           | 否   | NULL   | 用户真实称呼（R-MEM-05） |
| user_hobby_name        | String(50)           | 否   | NULL   | 用户昵称（R-MEM-05） |
| user_description       | Text                 | 否   | NULL   | 用户印象（R-MEM-05） |
| character_purpose      | Text                 | 否   | NULL   | 角色当前回应策略（R-MEM-07） |
| character_attitude     | Text                 | 否   | NULL   | 角色当前态度（R-MEM-07） |
| future_timestamp       | Integer              | 否   | NULL   | Future 预约时间戳（R-FUT-02） |
| future_action          | String(200)          | 否   | NULL   | Future 预约意图摘要（R-FUT-02） |
| proactive_times        | Integer              | 是   | 0      | 主动消息计数，上限 3（R-FUT-03，`server_default="0"`） |
| like_aware_special_used_count | Integer       | 是   | 0      | 生活流·点赞感知 IM 特殊档已用次数（入队成功 +1；可后台重置） |
| read_aware_special_used_count | Integer       | 是   | 0      | 生活流·已读感知 IM 特殊档已用次数（入队成功 +1；可后台重置） |
| has_ever_commented_feed | Integer             | 是   | 0      | 生活流·是否已发生过全局首次评论（首次评论 `due_at` 强制 +30s；置 1 后不回退） |


### 表名：conversation_log


| 字段名                | 类型         | 必填  | 默认值    | 说明               |
| ------------------ | ---------- | --- | ------ | ---------------- |
| id                 | Integer PK | 是   | 自增     |                  |
| user_id            | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`     |
| role               | String(20) | 是   | -      | user / assistant |
| content            | Text       | 是   | -      |                  |
| emotion_label      | String(50) | 否   | NULL   | 用户消息情绪           |
| emotion_confidence | Float      | 否   | NULL   |                  |
| memory_injected    | JSON       | 否   | NULL   | **仅历史字段，已停用**：列保留，新 user 行恒 `null`（M11/P7，长记忆第一套下线后 send 不再做向量检索/注入计算） |
| persona_risk_flag  | Boolean    | 是   | False  | 人格风险标记           |
| persona_risk_type  | String(50) | 否   | NULL   |                  |
| sort_seq           | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| delivery_status    | String(32) | 否   | NULL   | user 行：送达/等待/失败等（与 `constants` 一致）；assistant 为 NULL |
| skipped_in_prompt  | Boolean    | 是   | false  | Q14：未进入本轮 Prompt 的 user 行 |
| round_id           | String(36) | 否   | NULL   | TD-016 / STEP-011：一轮内全部 user 行与**全部** assistant 行共用同一 UUID 文本（多气泡时为多行 assistant，每行独立 `sort_seq`）；旧数据可为 NULL |
| created_at         | DateTime   | 是   | utcnow |                  |


### 表名：emotion_log


| 字段名             | 类型                              | 必填  | 默认值    | 说明  |
| --------------- | ------------------------------- | --- | ------ | --- |
| id              | Integer PK                      | 是   | 自增     |     |
| user_id         | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| emotion_label   | String(50)                      | 是   | -      |     |
| confidence      | Float                           | 是   | -      |     |
| conversation_id | Integer FK(conversation_log.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| round_id        | String(36)                      | 否   | NULL   | 与本轮 conversation 对齐；旧数据可为 NULL |
| created_at      | DateTime                        | 是   | utcnow |     |


### 表名：user_short_term_emotion


| 字段名          | 类型         | 必填  | 默认值    | 说明                               |
| ------------ | ---------- | --- | ------ | -------------------------------- |
| id           | Integer PK | 是   | 自增     |                                  |
| user_id       | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 每用户一行（`unique=True`）              |
| emotion_label | String(50) | 是   | -      | 短期情绪标签                           |
| confidence    | Float      | 是   | -      |                                  |
| payload       | Text       | 否   | NULL   | 可选 JSON 文本（ORM `nullable=True`）    |
| updated_at    | DateTime   | 是   | utcnow | `onupdate=utcnow`                |


### 表名：memory


| 字段名                     | 类型          | 必填  | 默认值    | 说明                    |
| ----------------------- | ----------- | --- | ------ | --------------------- |
| id                      | Integer PK  | 是   | 自增     |                       |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`          |
| content                 | Text        | 是   | -      |                       |
| importance_score        | Float       | 是   | -      |                       |
| source                  | String(20)  | 是   | -      | auto / manual / admin |
| dashvector_id           | String(100) | 否   | NULL   | 向量侧 ID（`index=True`） |
| is_deleted              | Boolean     | 是   | False  | 软删除                   |
| created_at              | DateTime    | 是   | utcnow |                       |
| updated_at              | DateTime    | 是   | utcnow | `onupdate=utcnow`     |
| expires_at              | DateTime    | 否   | NULL   | 过期时间                  |


### 表名：ai_diary


| 字段名                            | 类型         | 必填  | 默认值    | 说明    |
| ------------------------------ | ---------- | --- | ------ | ----- |
| id                             | Integer PK | 是   | 自增     |       |
| user_id                        | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                        | Text       | 是   | -      |       |
| relationship_level_at_creation | Integer    | 是   | -      | 生成时等级 |
| is_read                        | Boolean    | 是   | False  |       |
| covers_beijing_date            | Date       | 否   | NULL   | 日记内容覆盖的北京日历日；旧数据可为 NULL（不回填）；与 `user_id` 唯一约束防重复 |
| created_at                     | DateTime   | 是   | utcnow |       |


### 表名：agent_message


| 字段名          | 类型         | 必填  | 默认值    | 说明    |
| ------------ | ---------- | --- | ------ | ----- |
| id           | Integer PK | 是   | 自增     |       |
| user_id      | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| trigger_type | String(16) | 是   | -      | P0–P4 / FUTURE / **`LIKE_AWARE`** / **`READ_AWARE`**（生活流感知 IM；落库 `action_score=0`；与 P0–P4/Future **业务零耦合**，仅共用本表与 `sort_seq`） |
| content      | Text       | 是   | -      |       |
| action_score | Float      | 是   | -      |       |
| is_read      | Boolean    | 是   | False  |       |
| sort_seq     | BigInteger | 是   | 0      | 时间线排序（`index=True`） |
| created_at   | DateTime   | 是   | utcnow |       |


### 表名：login_log


| 字段名         | 类型         | 必填  | 默认值    | 说明                        |
| ----------- | ---------- | --- | ------ | ------------------------- |
| id          | Integer PK | 是   | 自增     |                           |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`              |
| login_at    | DateTime   | 是   | -      |                           |
| time_period | String(20) | 是   | -      | morning / evening / other |
| created_at  | DateTime   | 是   | utcnow |                           |


### 表名：world_state


| 字段名                     | 类型         | 必填  | 默认值    | 说明  |
| ----------------------- | ---------- | --- | ------ | --- |
| id                      | Integer PK | 是   | 自增     |     |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| content                 | Text       | 是   | -      |     |
| trigger_conversation_id | Integer    | 否   | NULL   | ORM 未声明 `ForeignKey`（仅整型可空） |
| relevance_weight        | Float      | 是   | 1.0    | ORM `default=1.0` |
| created_at              | DateTime   | 是   | utcnow |     |


### 表名：relationship_growth_log


| 字段名         | 类型         | 必填  | 默认值    | 说明       |
| ----------- | ---------- | --- | ------ | -------- |
| id          | Integer PK | 是   | 自增     |          |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| action_type | String(30) | 是   | -      | dialog 等 |
| points      | Integer    | 是   | -      | 本次得分     |
| created_at  | DateTime   | 是   | utcnow |          |


### 表名：relationship_level_history


| 字段名         | 类型         | 必填  | 默认值    | 说明  |
| ----------- | ---------- | --- | ------ | --- |
| id          | Integer PK | 是   | 自增     |     |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| from_level  | Integer    | 是   | -      | 升级前等级 |
| to_level    | Integer    | 是   | -      | 升级后等级 |
| achieved_at | DateTime   | 是   | utcnow |     |


### 表名：relationship_change_history


| 字段名            | 类型                   | 必填  | 默认值    | 说明       |
| ---------------- | -------------------- | --- | ------ | -------- |
| id               | BigInteger PK（MySQL BIGINT，SQLite INTEGER 兼容） | 是   | 自增     |          |
| relationship_id  | Integer FK(relationship.id, ON DELETE CASCADE) | 是   | -      | `index=True` |
| user_id          | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | 冗余便于查询（`index=True`） |
| field_name       | String(50)           | 是   | -      | 被更新的字段名（snake_case，如 `relation_description`） |
| old_value        | Text                 | 否   | NULL   | 更新前的值   |
| new_value        | Text                 | 否   | NULL   | 更新后的值   |
| trigger_source   | String(20)           | 是   | step6  | 触发来源（`server_default="step6"`） |
| round_id         | String(36)           | 否   | NULL   | 关联的对话轮次 ID |
| created_at       | DateTime             | 是   | utcnow | 写入时间    |

- **设计语义**：append-only 表，仅 INSERT 不做 UPDATE/DELETE（R-L1L3-05）
- **索引**：`(user_id, created_at)` 组合索引（`ix_rel_change_user_created`），支持按用户 + 时间排序查询
- **关联需求**：R-L1L3-05（变更历史）、R-MEM-05（6 个扩展字段全部参与历史记录）
- **触发来源**：本期仅 `step6`（Step6 自动更新触发写入）；后续如启用管理后台手动编辑，可扩展其他来源标记（R-L1L3-07 本期不做）


### 表名：user_timeline_seq


| 字段名      | 类型            | 必填  | 默认值 | 说明   |
| -------- | ------------- | --- | --- | ---- |
| user_id  | Integer PK / FK(users.id, ON DELETE CASCADE) | 是   | -   | 复合主键之一 |
| next_seq | BigInteger    | 是   | 1   | 下一序号（ORM `default=1`） |


### 表名：admin_users


| 字段名                   | 类型          | 必填  | 默认值    | 说明            |
| --------------------- | ----------- | --- | ------ | ------------- |
| id                    | Integer PK  | 是   | 自增     |               |
| username              | String(50)  | 是   | -      | 唯一索引（`unique=True`） |
| password_hash         | String(255) | 是   | -      |               |
| role                  | String(20)  | 是   | -      | super_admin / ops_admin / ai_trainer / tech_ops / observer（展示名“观察者”） |
| remark                | String(200) | 否   | NULL   |               |
| is_active             | Boolean     | 是   | True   | ORM `default=True` |
| is_locked             | Boolean     | 是   | False  | ORM `default=False` |
| login_fail_count      | Integer     | 是   | 0      |               |
| token_version         | Integer     | 是   | 0      | 后台账号级会话版本；数据库 `NOT NULL DEFAULT 0` |
| last_login_at         | DateTime    | 否   | NULL   |               |
| last_password_change_at | DateTime  | 否   | NULL   |               |
| created_at            | DateTime    | 是   | utcnow |               |
| created_by            | String(50)  | 否   | NULL   |               |


### 表名：admin_config


| 字段名        | 类型          | 必填  | 默认值    | 说明        |
| ---------- | ----------- | --- | ------ | --------- |
| id         | Integer PK  | 是   | 自增     |           |
| config_key | String(100) | 是   | -      | **非唯一**索引（`index=True`）；同一 key 多行见下 |
| config_value | Text      | 否   | NULL   | JSON 字符串等（`nullable=True`） |
| version    | Integer     | 是   | 1      | ORM `default=1` |
| is_active  | Boolean     | 是   | True   | ORM `default=True` |
| is_draft   | Boolean     | 是   | False  | ORM `default=False`；`comment`：True=草稿 / False=正式或历史 |
| updated_by | String(50)  | 否   | NULL   |           |
| updated_at | DateTime    | 是   | utcnow | `onupdate=utcnow` |

- **行语义与约束**：同一 `config_key` **允许且需要**多行并存——例如一条草稿（`is_draft=true`，`is_active=false`）、一条当前生效（`is_active=true`，`is_draft=false`）、多条历史版本（`is_active=false`，`is_draft=false`）。**禁止**对 `config_key` 单列建立 **UNIQUE**；否则 `PUT /api/admin/persona/draft`、`prompt` 草稿保存等会在 `INSERT` 草稿时触发 MySQL **1062**。新建库见 `scripts/schema_ddl.sql`；已错建唯一索引的库执行 **`scripts/migrate_admin_config_config_key_nonunique.sql`**（执行前用 `SHOW INDEX FROM admin_config` 核对索引名）。
- **运行时约定 key（节选，非表结构 DDL）**：除既有 `persona`、`fallback_reply` 等外，对话链路读取 **`step5_system_prompt`**（Step5 模块1 System 整段，缺省回退代码内 `SYSTEM_PROMPT_TEXT`）、**`step5_5_prompt_fragments`**（Step5.5 六段 JSON，缺省与 `step5_5_prompt_fragments.py` 内置默认合并）、**`step5_5_enabled`**（Step5.5 总开关，§2.7.1；`AdminConfigService.get_active_config`，Redis `active_config:step5_5_enabled`）；开关无库内生效行时视为关闭。管理端：侧栏 **「🗣️ 对话流 Prompt」** 分组内 **`prompt.html?tab=step5|step55`**（Step5 / Step5.5 可编辑）、**`step5-5-switch.html`**（总开关）；Step1.5 / Step3 / Step8 / Agent 任务指令另见只读页与 **`GET /api/admin/chat-prompt-view/*`**（2026-07-13）。


### 表名：admin_operation_logs


| 字段名                | 类型          | 必填  | 默认值    | 说明        |
| ------------------ | ----------- | --- | ------ | --------- |
| id                 | Integer PK  | 是   | 自增     |           |
| admin_user_id      | Integer     | 否   | NULL   | 可空（账号删除后仍保留日志，ORM `nullable=True`） |
| admin_username     | String(50)  | 是   | -      |           |
| module             | String(50)  | 是   | -      |           |
| action             | String(20)  | 是   | -      |           |
| target_description | String(500) | 否   | NULL   |           |
| before_value       | Text        | 否   | NULL   |           |
| after_value        | Text        | 否   | NULL   |           |
| ip_address         | String(50)  | 否   | NULL   |           |
| created_at         | DateTime    | 是   | utcnow |           |


---

### 生活流新增表（8）

> 迁移：`v6a_step001_*`（建表+扩展）· `v6b_step019_026_*`（`agent_aware_queue.prompt_key/extra_context` + `feed_post.sse_broadcasted`）· `v6c_*`（`feed_comment.is_hidden`）· `v6d_*`（`reply_to_lxm`）· `v6e_*`（`base_comments`/`comment_multiplier`）。  
> 时区：**帖子到点 / `last_feed_entered_at` / 计划发布时间** = **Asia/Shanghai 墙钟**（`feed_now()`）；**评论 `due_at`/`created_at`、感知队列 `due_at`** = **UTC**（刻意分离）。

#### 表名：life_plan_outline

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| week_start_date | Date | 是 | 所属自然周周一 |
| plan_date | Date | 是 | 自然日（unique） |
| city | String(50) | 是 | 当天城市 |
| categories | String(200) | 是 | 内容分类，多个用 `\\n` 分隔；取值∈`categories_vocab` |
| gen_status | String(16) | 是 | `auto` / `manual` |
| created_at / updated_at | DateTime | 是 | |

#### 表名：life_plan

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| plan_date | Date | 是 | unique；关联大纲日 |
| scenes | JSON | 是 | 场景数组（scene_id/time_range/city/category/venue_type/description） |
| gen_status | String(16) | 是 | `generating` / `ready` / `failed` |
| created_at | DateTime | 是 | |

#### 表名：worldview_snapshot

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| plan_date | Date | 是 | |
| scene_id | String(64) | 是 | `scene_{plan_date}_{seq:03d}` |
| feeling_text | Text | 否 | 感受描述 |
| emotion_value | String(50) | 否 | 情绪；词表优先，可自由词 |
| focus_tag | String(100) | 否 | |
| worldview_trigger | String(100) | 否 | 写入事件库的话题标签 |
| gen_status | String(16) | 是 | `generating` / `ready` / `failed` |
| created_at / updated_at | DateTime | 是 | |

#### 表名：worldview_event

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer PK | 是 | 自增 |
| event_name | String(200) | 是 | unique 话题名 |
| event_view | Text | 是 | 固定看法；核心态度以 `[核心态度：X] ` 前缀嵌入（无独立列；X∈喜欢/排斥/矛盾/无感） |
| source_scene_id | String(64) | 否 | |
| created_at / updated_at | DateTime | 是 | |

#### 表名：feed_post

| 字段名 | 类型 | 必填 | 默认 | 说明 |
|--------|------|------|------|------|
| id | Integer PK | 是 | 自增 | |
| scene_id | String(64) | 否 | NULL | |
| scheduled_publish_time | DateTime | 是 | - | **北京墙钟 naive**；可见条件：`<=feed_now() AND is_visible=1 AND generation_status='ready'` |
| actual_publish_time | DateTime | 否 | NULL | STEP-013 落 NULL；列表首次命中懒惰写 `feed_now()` |
| generation_status | String(16) | 是 | - | `generating` / `ready` / `failed` |
| content_text | Text | 是 | - | |
| hashtags | JSON | 否 | NULL | |
| image_urls | JSON | 否 | NULL | CDN WebP 数组 |
| image_reference_url | String(512) | 否 | NULL | 人物参考图说明用；基准图本地 `/static/images/avatar/character-ref/base.png` |
| image_type | String(16) | 否 | NULL | `selfie` / `daily` / `scenery` / `emotion` |
| emotion | String(20) | 是 | - | |
| city | String(50) | 是 | - | 场景城市 |
| season | String(20) | 是 | - | 春/夏/秋/冬 |
| base_likes / like_multiplier / real_likes | Integer | 是 | - | 展示点赞 = base×倍率+real |
| base_comments | Integer | 是 | 0 | 虚拟评论底；新帖随机；历史默认 0（不回填） |
| comment_multiplier | Integer | 是 | 1 | 仅放大 base_comments；历史默认 1 |
| is_visible | SmallInteger | 是 | 1 | 0=下架 / 1=展示 |
| dedup_hash | String(64) | 是 | - | `md5(venue_type\|category\|city)` |
| sse_broadcasted | SmallInteger | 是 | 0 | SSE 新帖广播去重 |
| created_at / updated_at | DateTime | 是 | | |

**计算字段（非 DB 列）**：`display_likes = base_likes × like_multiplier + real_likes`；`display_comments = base_comments × comment_multiplier + 当前用户可见评论条数`。

#### 表名：feed_like

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | |
| user_id / post_id | Integer FK | UNIQUE(user_id, post_id) |
| created_at | DateTime | |

#### 表名：feed_comment

| 字段名 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| id | Integer PK | | |
| post_id / user_id | Integer FK | | |
| content | Text | | 用户评论 |
| reply_to_lxm | SmallInteger | 0 | 1=点小梦回复发出；仅 H5 落款；**无**父子树 |
| lxm_reply / lxm_reply_at / lxm_reply_read_at | Text/DateTime | NULL | LXM 回复与已读 |
| gen_status | String(16) | pending | `pending`→`generating`→`ready`/`failed`；后台软删后列表可筛 `hidden`（见 `is_hidden`） |
| due_at | DateTime | NULL | **UTC**；LLM-05 轮询 `pending AND due_at<=utcnow()` |
| is_hidden | SmallInteger | 0 | 后台软删；用户端不展示 |
| created_at / updated_at | DateTime | | |

#### 表名：agent_aware_queue

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | |
| user_id / post_id | Integer FK | |
| trigger_type | String(16) | `LIKE_AWARE` / `READ_AWARE` |
| relationship_stage | String(20) | 入队快照：`stranger`/`friend`/`intimate`/`soulmate` |
| due_at | DateTime | **UTC** |
| status | String(16) | `pending`→`generating`→`sent`/`failed` |
| prompt_key | String(32) | 入队确定；消费不重算档位 |
| extra_context | JSON | 如 `is_special` |
| agent_message_id | Integer | 成功后关联 |
| fail_reason | String(255) | |
| created_at / updated_at | DateTime | |

---

## 接口定义

### 统一说明

- **H5 端**成功响应：`ApiResponse`，`code=0`（`SUCCESS`）表示成功；失败为业务错误码（如 `10001` 起，见 `constants.py`）。
- **管理后台**：除 SSE/文件流及下文单独说明外，**所有 JSON 业务接口成功响应信封统一为 `ApiResponse`**（`code=0` 成功；`code` 为 `**2xxxx**`（`ADMIN_ERR_*`）表示业务失败；**正常业务路径下 HTTP 状态码为 200**，与 H5 信封一致）。
- **鉴权失败**仍为 **HTTP 401 / 403**（由 `get_current_admin`、`require_role` 等 Depends 抛出 `HTTPException`，非业务层 JSON 信封）。
- **Pydantic 校验失败（422）**、**未捕获的服务器异常（500）** 等响应结构**不是** `ApiResponse`，前端需按 `admin-api.js` 中 `!resp.ok` 等逻辑兜底。
- **管理端 `adminRequest`**：第 5 参数可选 `{ silentErrorToast: true }`，抑制 `code≠0` 时的默认错误 Toast，便于调用方按业务码单独 `showToast`（例如用户禁用/启用 20012、20013）。
- **遗留**：`/api/admin/stats/*` 中部分参数错误仍可能为 `**HTTPException(400)`**；`/api/admin/third-party/*` 保存前连接失败可能为 `**ApiResponse.fail(code=5001)`**（与 `ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED=20040` 语义对应，后续可对齐）。
- **鉴权**：H5 为 `Authorization: Bearer`，JWT 用户端；后台为独立 Admin JWT（签名密钥 `ADMIN_JWT_SECRET`，与用户端独立），payload 含 `type=admin`、`role`、`sub`；**`sub` 为管理员用户 ID 的十进制字符串**（JWT 内非 JSON number），以满足 PyJWT 2.8+ 对 `sub` 的类型要求，服务端 `get_current_admin` 将其转为整数后查 `admin_users`。部分路由另需 `require_role(...)`。

#### 字段命名规范

- **基准**：以 **H5 用户端**已有接口为准，管理后台新建或改造分页接口时与之对齐。
- **列表数组字段名**：分页 `data` 内列表统一为 `**list`**（对齐 H5 `GET /api/memory/list`、`GET /api/relationship/growth-log`）；配合 `**total`、`page`、`page_size`**。
- **记录主键**：列表元素资源主键统一为 `**id`**（对齐 H5 记忆列表等）。
- **例外（历史约定，未改路由）**：H5 `**GET /api/chat/history`** 使用 `**messages`**；`**GET /api/diary/list`**、`**GET /api/chat/timeline**` 使用 `**items**`；管理后台各分页接口已统一采用 `**list` + `id**`（见下文用户管理、记忆、统计、系统日志等模块）。另：管理后台 `**GET /api/admin/accounts**` 成功时 `**data` 即为账号对象数组本身**（无分页对象包装），见「管理后台账号」模块。

#### Admin 错误码规范

- Admin 业务错误码从 **20001** 起，**边开发边补**全量枚举；常量命名格式 `**ADMIN_ERR_{模块}_{描述}`**（全大写下划线），定义于 `backend/constants.py`；与 H5 错误码（**10001** 起）**两套独立**，互不占用同一数值语义。
- 后台业务失败应返回 `**ApiResponse.fail(ADMIN_ERR_xxx, message=...)`**，文案可覆盖 `ADMIN_ERROR_MESSAGES` 中的默认描述。
- **依赖鉴权**（`backend/utils/admin_auth.py`）未使用本段枚举，仍为 **401/403** + `HTTPException.detail` 文案（如「未提供认证 Token」「权限不足」），不在 20001 列表内。

**当前已定义错误码及含义：**


| 常量名                                            | 数值    | 含义                  |
| ---------------------------------------------- | ----- | ------------------- |
| `ADMIN_ERR_AUTH_LOGIN_FAILED`                  | 20001 | 登录：账号不存在或密码错误（统一提示） |
| `ADMIN_ERR_AUTH_ACCOUNT_LOCKED`                | 20002 | 登录：账号已锁定            |
| `ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING` | 20003 | 登录：密码错误并提示剩余尝试次数    |
| `ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG`            | 20004 | 修改密码：旧密码不正确         |
| `ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD`      | 20005 | 修改密码：新密码与旧密码相同      |
| `ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH` | 20006 | 修改密码：两次新密码不一致       |
| `ADMIN_ERR_AUTH_PASSWORD_POLICY`               | 20007 | 管理员密码强度不符合要求        |
| `ADMIN_ERR_USER_NOT_FOUND`                     | 20008 | H5 用户不存在            |
| `ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY`          | 20009 | 编辑用户记忆：内容为空         |
| `ADMIN_ERR_USER_MEMORY_NOT_FOUND`              | 20010 | 记忆不存在或不属于该用户        |
| `ADMIN_ERR_USER_STATUS_ACTION_INVALID`         | 20011 | 禁用/启用：action 非法     |
| `ADMIN_ERR_USER_ALREADY_BANNED`                | 20012 | 用户已处于禁用状态           |
| `ADMIN_ERR_USER_NOT_BANNED`                    | 20013 | 用户未被禁用              |
| `ADMIN_ERR_ACCOUNT_USERNAME_EXISTS`            | 20014 | 创建管理员：用户名已存在        |
| `ADMIN_ERR_ACCOUNT_NOT_FOUND`                  | 20015 | 管理员账号不存在            |
| `ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE`     | 20016 | 不可修改自己的角色           |
| `ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF`         | 20017 | 不可删除自己的账号           |
| `ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER`        | 20018 | 超级管理员账号不可删除         |
| `ADMIN_ERR_PERSONA_FIELD_EMPTY`                | 20019 | 人格配置存在空字段           |
| `ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD`            | 20020 | 无草稿可丢弃              |
| `ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID`        | 20021 | 发布/回滚未输入 CONFIRM    |
| `ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED`     | 20022 | 发布前测试未通过            |
| `ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND`  | 20023 | 回滚目标版本不存在           |
| `ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE`         | 20024 | Prompt 模块不可编辑       |
| `ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING`         | 20025 | Prompt 缺少必填占位符      |
| `ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH`         | 20026 | 无待发布的 Prompt 草稿     |
| `ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID`      | 20027 | 记忆规则阈值或区间不合法        |
| `ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED`        | 20028 | 向量库连接测试失败（保存配置时）    |
| `ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`          | 20029 | 查询日期格式须为 YYYY-MM-DD；**`start_date > end_date`** 时 message 为「结束日期不能早于开始日期」（`admin_date_filter` 共用） |
| `ADMIN_ERR_AGENT_RULE_PARAM_INVALID`           | 20030 | Agent 规则数值参数越界      |
| `ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID`         | 20031 | trigger_type 非法     |
| `ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID`         | 20032 | 主动消息模板规则参数非法        |
| `ADMIN_ERR_RELATIONSHIP_RULE_INVALID`          | 20033 | 关系等级规则校验失败          |
| `ADMIN_ERR_DIARY_RULE_PARAM_INVALID`           | 20034 | 日记生成规则参数非法          |
| `ADMIN_ERR_EMOTION_CONFIG_INVALID`             | 20035 | 情绪配置非法              |
| `ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID`          | 20036 | 违禁词 Excel 不合法或无可导入词 |
| `ADMIN_ERR_SYSTEM_OPENPYXL_MISSING`            | 20037 | 服务器缺少 openpyxl      |
| `ADMIN_ERR_THIRD_PARTY_SERVICE_NAME_INVALID`   | 20038 | 第三方服务名非法            |
| `ADMIN_ERR_THIRD_PARTY_REQUEST_BODY_EMPTY`     | 20039 | 更新第三方配置：请求体为空       |
| `ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED` | 20040 | 第三方配置保存前连接测试失败      |
| `ADMIN_ERR_SYSTEM_LOG_QUERY_INVALID`           | 20041 | 系统日志查询/导出条件非法       |
| `ADMIN_ERR_STATS_QUERY_INVALID`                | 20042 | 数据统计查询/导出条件非法       |
| `ADMIN_ERR_TEST_CASE_MIN_RETAIN`               | 20043 | 删除测试用例将低于最少保留条数     |
| `ADMIN_ERR_TEST_CASE_NOT_FOUND`                | 20044 | 指定测试用例不存在           |
| `ADMIN_ERR_OPERATION_LOG_NOT_FOUND`            | 20045 | 操作日志记录不存在           |
| `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`        | 20046 | 向量/Token 热配置 PATCH 非法 |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID`  | 20047 | 角色知识库：type/key/value 非法 |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG`   | 20048 | key 超 20 汉字            |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG` | 20049 | value 超 100 汉字         |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY`  | 20050 | 同 type+key 已存在         |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND`      | 20051 | doc_id 不存在             |
| `ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED` | 20052 | Embedding 或 DashVector 失败 |


---

### 模块：H5 认证（`/api/auth`）

#### POST /api/auth/register

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`RegisterRequest` — `username` string 必填 6–20 字母数字；`password` string 必填 8–20；`confirm_password` string 必填
- **响应**：`ApiResponse`；`data` 为 `{ token, user_id, username }`（`TokenData`）
- **关联表**：users, relationship（初始化）
- **状态**：已实现

#### POST /api/auth/login

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`LoginRequest` — `username`, `password` 必填；`remember_me` bool 默认 false
- **响应**：`ApiResponse`；`data` 同注册
- **关联表**：users, login_log
- **状态**：已实现

#### POST /api/auth/reset-password

- **所属端**：H5
- **鉴权**：无
- **请求 Body**：`ResetPasswordRequest` — `username`, `new_password`, `confirm_password`
- **响应**：`ApiResponse`；成功 `message` 文案
- **关联表**：users
- **状态**：已实现
- **H5 设置页说明**：`frontend/pages/settings.html` 的「修改密码」仍调用本接口，但前端 Body 含 `old_password` 且未传 `confirm_password`，与 Schema 不一致；**不校验原密码**。清偿见 **TD-025**。

#### POST /api/auth/logout

- **所属端**：H5
- **鉴权**：Bearer 用户 JWT
- **请求 Body**：无
- **响应**：`ApiResponse`
- **状态**：已实现（服务端无状态，客户端删 Token）

---

### 模块：H5 应用（`/api/app`）

#### GET /api/app/persona-background

- **所属端**：H5
- **鉴权**：Bearer 用户 JWT
- **响应**：`ApiResponse`；`data`: `{ background: string }` — 当前生效 **`admin_config.config_key=persona`** JSON 的 **`background`**（角色背景）；无配置或字段为空时回退 **`prompt_builder.DEFAULT_PERSONA`** 中【角色背景】段落
- **数据源**：`admin_config_service.get_active_config("persona")`（Redis `active_config:persona`，**非草稿**）
- **H5 用法**：`settings.html`「关于林小梦」手风琴**首次展开**时懒加载
- **实现**：`backend/routers/app.py`；`main.py` 已挂载
- **状态**：已实现

---

### 模块：H5 对话（`/api/chat`）

#### POST /api/chat/send

- **所属端**：H5
- **鉴权**：Bearer
- **请求 Body**：`ChatSendRequest` — `content` string 1–2000；**`client_message_id`** string 可选（≤64，建议 UUID，可与请求头 **`Idempotency-Key`** 一致，幂等语义以服务端实现为准）
- **响应**：**非 JSON 信封**；成功为 `StreamingResponse`（`text/event-stream`）。SSE 事件（JSON 行）包括但不限于：
  - **`meta`**：`{"type":"meta","generation_id":"<uuid>","message_count":<N>}` — 首包（CP2）；客户端应丢弃与当前有效代不一致的流片段（与 TD-015 一致）；`message_count` 表示本轮回复包含 N 条独立消息气泡（§2.9.4）
  - **H5 实现说明（`frontend/pages/chat.html`）**：**表现层（2026-07-11，在 2026-05-23 沉浸底上改版）**：**`body.h5-skin.chat-immersive`**；全屏背景 **`#chat-bg-image`** 由 **`updateChatBackgroundEmotion`** 按 **`done.emotion.label`** / timeline **`emotion_label`** 切换（**`AVATAR_MAP`**，与 **`api.js`** 头像资源同路径）。顶栏三块胶囊（无整条毛玻璃底）：返回 → **`/pages/index.html`**；**`.bar-profile`**（**`#chat-header-avatar`** 固定默认图 + 绿点 +「林小梦」+「在线」）；**`.bar-actions`**（朋友圈 **`icon-feed.png`** / 记忆星云 **`icon-memory-nebula.png`**，透明底、无文案）；**无** **`.more-btn`**。朋友圈：**`loadChatFeedBadge`** → **`GET /api/feed/badge`**，角标 = **`unread_reply_count + new_post_count`**；**`goChatFeed`** 跳转规则同首页（有未读回复带 **`?focus=unread_reply`**）。气泡：用户半透明紫白字、AI 白玻璃 + 左下紫菱形光点。底栏浮起玻璃 + handle（仅视觉）；**`#msg-input`** placeholder **`想和我吐槽什么…`**；**`#send-btn`** 启用 **`#7C5CFF`**（纸飞机图标），禁用 **`#D8D8DC`/`#8E8E93`**（**`h5-theme.css`** 对 **`.chat-immersive`** 不覆盖发送钮启用态）。**时间展示**：引入 **`/static/js/chat-time.js`**；**`parseMessageTimestamp`** 对无时区 ISO 按 UTC（补 **`Z`**）；**`formatChatTime` / `shouldShowTimeStamp`** 自然日与文案按 **`Asia/Shanghai`**（当天 **`HH:mm`**、昨天/前天/周几/更早 **`YYYY/M/D HH:mm`**；**>5 分钟或跨北京自然日** 或首条显示；周一起算）；消息行 **`data-created-at`**（timeline 用 **`created_at`**，发送用客户端时间）；**气泡内不显示时间**；流式槽位仅 **`.msg-content`**。**失败叹号** **`.msg-bang`** 在用户气泡左侧，flex 垂直居中（送达态业务不变）。**发送与 SSE（逻辑不变）**：每次发起 **`send` / `resend`** 前递增本地 **`chatSendSession`** 并 **`AbortController`** 打断上一请求；**不**再使用全局变量 **`sending`** 阻塞整段请求或 SSE 消费——**是否允许继续发**以服务端 **10104** 等为准，前端由 **`getOpenWindowUserRows()`** 界定未闭环窗口（与 **`chat_service.fetch_open_window_user_rows`** 一致：最后一条已落库 **非 agent** assistant 之后，**排除** **`data-ai-in-flight="1"`**），**`countOpenPendingUsers`** 仅计窗口内 **`pending_llm` / `failed_timeout` / `failed_error`（≥5 且无叹号）** 预判，外加 **`CHAT_CLIENT_ABORT_MS`（120s）** 客户端中止；**防连点**：`send` 与叹号 **`resend` 共用** 时间戳 **`lastSendOrResendAt`**，在通过内容非空、队列预判之后、**即将 `fetch` 之前**若距上次不足 **`CHAT_SEND_DEBOUNCE_MS`（300ms）** 则 **静默 `return`**。**输入法与回车键**：`#msg-input` 设 **`enterkeyhint="send"`**（软键盘回车键语义；**具体标签以系统为准**），并使用 **`oncompositionend` / `onkeyup`** 同步调用 **`updateSendBtn()`**（与 `oninput` 并列），避免系统中文输入法下发送钮长期 **`disabled`**。**发送键与键盘**：`#send-btn` 声明 **`type="button"`**；**`updateSendBtn()`** 按 **`trim`** 同步 **`disabled` 属性** 与 **`.disabled`** 类，禁用态样式背景 **`#D8D8DC`**、前景 **`#8E8E93`**，有内容时可点；**`setupSendBtnKeepKeyboard()`** 在 **`initChat`** 中注册 **`mousedown`** 与 **`touchstart`（`{ passive: false }`）** 监听，内 **`preventDefault`**，避免点击发送时焦点从 **`#msg-input`** 移到按钮导致移动端键盘自动收起；**`handleSend`** 仍仅由 **`click` / `onclick`** 触发（与 debounce、SSE 会话快照逻辑无冲突）。`consumeChatSse` 仅当传入的会话快照与 **`chatSendSession`** 一致时继续解析；收到 **`meta`** 后记录本连接 **`generation_id`** 与 **`message_count`**；若 **`delta`** 携带 **`generation_id`** 且与 **`meta`** 不一致则丢弃该条；收到 **`done`** 时**先** **`markOpenWindowUsersDelivered()`**（窗口内 user **`data-delivery`→`delivered`**，**resend** 成功亦同），**再** **`finalize(done.messages)`**（**不可**颠倒）；若有 **`emotion.label`** 调用 **`updateChatBackgroundEmotion`**。**10104** 或前端满队预判后仍 **`loadTimeline(true)`**（向列表底部追加 timeline，**不**清空 DOM、**不**回写已有行 **`data-delivery`**，**非**完整自愈）。服务端 DB / Redis 仍为权威真相，本段约束端上 **`data-delivery` 预判** 与 SSE 展示不串台。
  - **`delta`**：`{"type":"delta","content":"...","message_index":<0≤i<N>}` — 按条推送增量文本，`message_index` 标识目标气泡槽位（§2.9.4）
  - **`done`**：`{"type":"done","messages":[{"type":"text","content":"..."},...],"emotion":{"label":"...","confidence":0.0~1.0}}` — 完整 messages 数组为真相源（§2.7.5），整轮一个 emotion 对象（§2.7.3）；H5 收到后按 `done.messages` 渲染 N 个独立气泡，禁止预铺空气泡
  - **`failed`**：`{"type":"failed","code":<int>,"message":"..."}` — 超时/LLM 失败、**Step5 对外 `messages[].content` 任一条内容安全拦截**（`code`**10101**，见 **STEP-012** / §9.1）等，**不**写入 assistant 行
  - **`obsolete`**：本连接对应代已被新输入作废
- **失败（未进入 SSE）**：`ApiResponse` JSON — 如 **10101** 内容安全、**10104** 队列满（无叹号时未处理 ≥5）、**10102** 等；返回 **10104** 前若未闭环行**均为 `pending_llm`**，服务端 **异步补跑** 一轮 bundle（见顶栏 **2026-06-04 队列死锁修复** 摘要），**仍返回 10104**，客户端宜提示等待后刷新 timeline
- **语义摘要**：用户输入内容安全通过后 **立即** 写入 user 行（`delivery_status=pending_llm`）；打包调度 **防抖**（默认 500ms，配置 `CHAT_DEBOUNCE_MS`）；主链路 Step5 LLM 超时 **45s**（`LLM_TIMEOUT_CHAT`）；Step5 解析成功后 **先** 对 **`inner_monologue`** 与 **`messages[].content`** 逐条跑与入队前同款的 `check_content`（§9.1 / §9.3，见 **STEP-012**）：`inner_monologue` 违规仅日志并替换为空串；**任一条 message 违规** → 整轮失败，user 行标 **`failed_blocked`**，不进入 Step5.5、不落 assistant；Step5 messages 全通过后，若 `admin_config` 中 **`step5_5_enabled`** 开启且双门闩命中，则 **追加** Step5.5 润色（HTTP 子超时 **30s**，见 STEP-009 / §2.7.4 D2）；**Step5.5 返回的 messages 亦逐条过安全**，违规则 **回退** Step5 合并后 messages（与 R-BND-06 一致）；成功闭环后按 **`final_messages` 条数 N** 写入 **N 行** `role=assistant`（每行一条气泡正文，连续 `sort_seq`，共享 `round_id`，见 **STEP-011** / §2.8.1）并异步后置任务（成长、记忆、`ai_emotion` 等；记忆拼接仍用整轮 `ai_reply`）；**Step6 入参仍仅用 Step5 原始 messages 合并结果**，不受 Step5.5 与安全替换后的对外文案影响（R-BND-05）；**Step6 记忆 LLM + 向量 + 关系写回**在落库成功后 **`asyncio.create_task` 异步入队**，不阻塞 SSE（**STEP-016** / §2.8.4 M2）
- **SSE 与后台 bundle 墙钟（`chat.py`）**：`_BUNDLE_WAIT_TIMEOUT_SEC`（默认 **120s**）仅限制 **`_sse_chat_wait_bundle`** 中 `asyncio.wait_for` 等待本代 **`generation` Future** 的最长时间；**不保证** **`_execute_llm_bundle`** 整段在服务端于 120s 内结束。Step1.5、Step5 等调用 **`llm_client.chat_sync`** 时，内层至多 **3 次** HTTP + 退避，单次超时分别为 **45s**（Step1.5 `_STEP1_5_TIMEOUT_SEC`）与 **`LLM_TIMEOUT_CHAT`（默认 45s，Step5）**，极端退化下 **SSE 可先返回超时/`failed` 而后台仍在执行**；与 **「部署与网关（对话 SSE）」** 中 Nginx 建议一并阅读。
- **关联表**：conversation_log, emotion_log（异步）；Redis `chat:gen:{user_id}`、防抖键、`ai_emotion:{user_id}` 等；**Step6**（§2.8.4 M2）：成功闭环后 **后台异步** 更新 DashVector 四类记忆文档 + `relationship` 标量/Future（失败不落库、不改 SSE，见 **STEP-016**）
- **状态**：已实现

#### POST /api/chat/resend

- **所属端**：H5
- **鉴权**：Bearer（**与 send 同域**；**禁止**管理端或 `/api/admin/` 代用户重发，L1）
- **请求 Body**：`ChatResendRequest` — `client_resend_id` 可选（≤128）
- **响应**：与 send 成功时相同 **SSE** 契约；当前未闭环窗口 **无** 叹号态 user 时 **10107**（`ERR_CHAT_NOTHING_TO_RESEND`）；超过 **2 次/分钟** 时 **10105**（`ERR_CHAT_RESEND_LIMIT`）
- **语义**：**不**插入新 user 行，仅对当前未闭环失败窗口再次调度 LLM
- **状态**：已实现

#### GET /api/chat/history

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page` int ≥1 默认 1；`page_size` int 1–50 默认 20
- **响应**：`ApiResponse`；`data`: `{ messages: [{id, role, content, emotion_label, created_at}], total, page, page_size }`
- **说明（H1）**：`messages[]` **不保证**包含 `delivery_status`、`sort_seq` 等送达字段；叹号恢复、与 Admin 列表对齐的送达态以 **`GET /api/chat/timeline`** 的 **`items[]`** 为准；history 与 timeline **能力可不一致**
- **关联表**：conversation_log
- **状态**：已实现

#### GET /api/chat/timeline

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`cursor` int 可选；`limit` int 1–50 默认 20
- **响应**：`ApiResponse`；`data`: `{ items: [...], next_cursor, has_more }`
- **`items[]`（conversation_log 来源）**：`source`, `sort_seq`, `id`, `content`, `created_at`, `emotion_label`, **`delivery_status`**, **`skipped_in_prompt`**, `is_read`, `trigger_type`（后两者对 agent 有值）；**`delivery_status` 取值**与 **`backend/constants.py`** 中单点常量一致（示例：`delivered`、`pending_llm`、`failed_timeout`、`failed_error`、`failed_blocked`），**不在**契约全文复制枚举表（J2）；**多气泡**：同一 `round_id` 下可有 **多条** `source=assistant` 行，按 `sort_seq` **升序**即为气泡展示顺序（与 SSE `done.messages` 下标一致，STEP-011）
- **首屏恢复（2026-06-04）**：**无 `cursor`** 时，若满足 **10104** 同等条件（满队且全 `pending_llm`），服务端在返回 `items` 前 **异步** 调度 bundle 恢复（与 **POST /api/chat/send** 10104 路径共用 `chat_service.trigger_recovery_if_queue_stuck`）
- **assistant / agent 行**：`delivery_status`、`skipped_in_prompt` **键存在且值为 `null`**（A1）
- **关联表**：conversation_log, agent_message
- **状态**：已实现

#### 部署与网关（对话 SSE）

- **Nginx**：`location` 代理 H5 **`/api/chat/send`**、**`/api/chat/resend`** 时，建议 **`proxy_read_timeout` ≥ 130s**（在 **`_BUNDLE_WAIT_TIMEOUT_SEC` 默认 120s** 之上留余量），避免网关早于 **`_sse_chat_wait_bundle`** 的 `wait_for` 先断开。**注意**：120s 仅为 **SSE 等待 Future 的客户端侧上限**（见 **POST /api/chat/send** 语义摘要），**不是** `_execute_llm_bundle` 整段墙钟的硬上界；仓库内 `nginx/nginx.conf` 若已为 **300s** 则满足上述要求。旧稿「≥50s、略大于 Step5 单次 45s」**不足以**覆盖 Step1.5 + Step5 多 POST 退避 + Step5.5 等串联场景，以本条为准。

##### 环境与通用 LLM HTTP 超时

- **配置**：环境变量 **`LLM_TIMEOUT`**（秒），由 **`backend/config.py`** 的 **`get_llm_timeout_seconds()`** 读取；**代码默认值 45**（与 **`LLM_TIMEOUT_CHAT`** 默认对齐）。本地/部署时在项目根目录 **`.env`** 中设置（模板见 **`.env.example`**）；**`backend/config.py`** 在 import 时对 **`项目根目录/.env`** 执行 **`load_dotenv`**。
- **语义**：单次 HTTP 上限作用于 **`httpx` 请求**；同一调用仍可能经 **`llm_client.chat_sync` 内最多 3 次 POST**（`LLM_MAX_RETRIES=2`）+ **1s / 2s** 退避。
- **典型落点**（`timeout_sec` **未**传入 **`chat_sync`** 或与 **`get_llm_timeout_seconds()`** 同源）：**AI 日记**（`diary_service` 主/兜底两次 **`chat_sync`**）、**对话记忆提取 LLM**、**管理后台配置发布前人格测试集**（`admin_config_service` → **`chat_with_parse`**）、**`llm_client.chat_stream`**。
- **P0–P4 主动消息（与上条区分）**：**`agent_service._call_llm_for_agent_prompt`** → **`chat_with_step5_parse`**，显式传入 **`get_llm_timeout_chat_seconds()`**（与 H5 Step5 同源，默认 **45s**）；**不**走 **`generate_with_fallback`**。
- **与主链路区分**：H5 **`send`/`resend`** 打包调度中的 Step5 / Step1.5 等使用 **`get_llm_timeout_chat_seconds()`**（**`LLM_TIMEOUT_CHAT`**）或路由内显式常量；**不**因本条而将 Step5 改为读取 **`LLM_TIMEOUT`**。

---

### 模块：H5 日记（`/api/diary`）

#### GET /api/diary/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`（1–50）
- **响应**：`ApiResponse`；`data` 为 `DiaryListResponse`：`items`（`DiaryItem`: id, content, relationship_level_at_creation, is_read, created_at, **covers_beijing_date** 可为 `null`）, total, page, page_size
- **说明**：成功响应 JSON **从不**包含 `diaries` 键；客户端须使用 **`items`**（与全局「字段命名规范」一致）。**`covers_beijing_date`** 为日记所覆盖的**北京日历日**；H5 列表日期展示优先使用该字段，缺失时回退 **`created_at`** 的本地解析（旧数据 H2 不回填）。
- **内容安全（产品已定案）**：AI 日记正文为系统生成内容，**当前**不对 LLM 输出做与 H5 用户消息同款的独立 `check_content`；合规边界以 PRD 与本条为准。
- **生成侧超时**：服务端调用 **`llm_client.chat_sync`** 未显式传 `timeout_sec` 时，单次 HTTP 上限为 **`get_llm_timeout_seconds()`**（环境变量 **`LLM_TIMEOUT`**，默认 **45s**）；内层重试与退避见 **「部署与网关」—「环境与通用 LLM HTTP 超时」**。
- **关联表**：ai_diary
- **状态**：已实现

#### POST /api/diary/{diary_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **Path**：`diary_id` int
- **响应**：`ApiResponse`；失败 `ERR_DIARY_NOT_FOUND`
- **关联表**：ai_diary
- **状态**：已实现

### `frontend/pages/diary.html`（H5 日记页）

- **接口**：仍仅消费 **`GET /api/diary/list`**（`items`）、**`POST /api/diary/{id}/read`**；**`items[]`** 含 **`covers_beijing_date`**（可为 `null`）。
- **初始化**：**不**以 `GET /api/relationship/status` 阻塞日记列表；关系等级在后台并行更新，用于空状态文案（`relationship_level` 仍可读 `localStorage` 兜底）。
- **布局**：**`.diary-hero`** 头图 **`/static/images/diary/dary_ri.png`**；**`.diary-main`** 列表区 **`margin-top: calc(-17vh + 60px)`**（与头图渐变叠压，小屏 **`-40px`**）；返回钮见摘要「淡薰衣草圆钮」；**`body.h5-skin.diary-page`** 页面底 **`#f3f0ff`**（覆盖全站 neo 渐变底，仅本页）。
- **列表日期（左栏）**：优先 **`covers_beijing_date`** 解析为 **英文月缩写（如 MAY）+ 日数字 + 中文星期**；无覆盖日时回退 **`created_at`** 的本地日历分量；底部装饰图标 **`getDay() % 4`** 四选一 SVG，**无业务含义**。
- **列表正文（右栏）**：**`content`** 默认 **3 行**截断；**「继续看 >」** / 展开后 **「收起」**；整卡点击切换；**不展示**头像、昵称、生成时刻、心情标签。
- **已读**：展开时若 **`is_read === false`**，移除 **`.unread`**、**`POST .../read`**；未读样式为淡紫边框/细左边线/右上角点（**非**橙色 **`.unread` 左边线** 旧样式）。
- **空态与失败**：无数据时展示原有等级分支空状态（文案不变）；列表首屏失败时展示 **`#empty-error`** 与 **「重新加载」**（重置分页后重新 `init`）；`showEmptyState` 会先隐藏其它空态/错误块，避免叠显。
- **分页**：首屏或后续页无更多数据时置 **`noMore`**，避免无意义触底请求。

---

### 模块：H5 记忆（`/api/memory`）

> **长记忆第一套下线（PRD v1.3 一次发布）**：H5 记忆改为**只读**——`GET /api/memory/list` 改读 Step6 user 向量 KV；`PUT/DELETE/POST` 写路由**已删除**。记忆统一由对话 Step6 异步管线自动整理写入，H5 不再支持手动增删改（C-05/M9）。运行时**不过滤 `mem_*`**（P1，旧脏数据靠 M2 人工清理）。

> **H5 展示（2026-07-12 · 以页面实况为准）**：**`frontend/pages/memory.html`**（`body.memory-nebula-page`）为 **Three.js 真 3D 记忆星云**，**不**改本模块 HTTP/库表。
>
> - **脚本**：`/static/js/api.js` → **`three.min.js`（r149）** → **`three-line2.js`** → **`memory-connection-layer.js`** → **`memory-nebula.js`**
> - **顶栏**：返回（优先 `history.back` 当 referrer 为 index/chat，否则 → `/pages/chat.html`）；主标题 **「记忆星云」**；副标题 **`#nebula-count-subtitle`**「**N 颗记忆星体**」；右上 **`#nebula-tip`** 说明 Toast；**`#nebula-count-num`** 为 **hidden** 兼容锚点（可见计数以 subtitle 为准）
> - **场景**：全屏背景图 **`/static/images/memory-nebula/nebula-bg.jpg`** + WebGL；中心恒星贴图 **`core-star.png`**（节点 id **`core-memory`**）；卫星贴图按 `key` 首段分桶（teal/green/purple/pink/gold）；装饰背景星点 + 轨道环；**`MemoryConnectionLayer`** 绘制默认/选中关系线（Line2）
> - **交互**：自动慢转（`prefers-reduced-motion` 关闭）；单指环视；双指远近（半径 clamp **6～28**）；点选打开底部详情卡；**回到中心**；点选后选中高亮 + 关系线激活
> - **详情卡**：分类「她记得 · …」；标题 **`titleFromValue(value)`**（**不展示 key**）；正文 `value||content`；来源「来自你们的对话」；角标「长期记忆」。点中心核 →「她记得 · 记忆总览」+ 记忆条数文案
> - **空态**：浮层文案 +「去和她聊聊」→ `/pages/chat.html`（不遮挡可环视的中心核）
> - **废止**：卡片列表 DOM、`#memory-list`、顶栏「对话自动整理 · 只读」、顶栏主标题「她记得的你」、详情卡 `#nebula-sheet-key`、中心屏上「林小梦」字标
> - **静态锚点**：**`tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract`**

> **H5 展示（2026-07-11，已被上条覆盖）**：曾为 Canvas 2D 星云；现以 2026-07-12 Three.js + 表现层实况为准。

#### GET /api/memory/list

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ total, page, page_size, list: [{doc_id, key, value, content}] }`（**不再返回** `id`/`importance_score`/`source`）
- **数据源**：DashVector `list_by_filter(build_filter("user", user_id, []), top_k=USER_LIST_TOPK=500)`；`total`=cap 内条数（P9，非库内真实总数）
- **状态**：已实现（只读改造）
- **H5 消费**：记忆星云页 **`fetchAllMemories`** 分页拉齐后布局星点；首页记忆预览卡仍取 `page=1&page_size=1`（`value||content` 截断）

#### ~~PUT /api/memory/{memory_id}~~（已删除）

- **下线说明**：H5 写路由已移除（C-05），记忆由 Step6 自动整理，不支持手动修改。

#### ~~DELETE /api/memory/{memory_id}~~（已删除）

- **下线说明**：同上。

#### ~~POST /api/memory/add~~（已删除）

- **下线说明**：同上。`schemas/memory.py`（`MemoryAddRequest`/`MemoryUpdateRequest`/`AdminMemoryUpdateRequest`）已随之删除。

---

### 模块：H5 主动消息（`/api/agent`）

> **P0–P4 生成链路（服务端，非 HTTP）**：定时扫描 **`AgentService.check_and_trigger`** → **`generate_and_save_message`**。Prompt：**`PromptBuilder.build_active_message_prompt`**（Step5 System + 主动任务模块）。LLM：**`chat_with_step5_parse`** → **`messages[]`** 合并为单条 **`content`** 写入 **`agent_message`**。失败兜底：**`AGENT_FALLBACK_REPLIES`**（按 `trigger_type`），**禁止**对话走神占位入库。FUTURE 走 **Step8**（`execute_step8_subchain`），本段不适用。

#### GET /api/agent/messages

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组 `{id, trigger_type, content, action_score, created_at}[]`（仅未读）
- **关联表**：agent_message
- **状态**：已实现

#### POST /api/agent/messages/{message_id}/read

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`
- **状态**：已实现

#### GET /api/agent/unread-count

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`: `{ count: int }`
- **说明**：计入全部未读 `agent_message`（含生活流感知 **`LIKE_AWARE` / `READ_AWARE`**，与 P0–P4/FUTURE 同表）
- **状态**：已实现

---

### 模块：H5 关系（`/api/relationship`）

**用户可见口径**：H5 关系页进度与今日总计等文案使用 **「亲密值」**；接口与库表字段仍为 **`growth_value`**、**`growth_info`**、Redis **`growth_*`** 前缀等（技术名不变）。关系页表现见文首 **「2026-05-26 摘要（H5 关系页改版）」**。

#### GET /api/relationship/status

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level, level_name, growth_value, current_growth, next_threshold, progress_percent, silence_days, ai_current_emotion（见 `RelationshipService.get_relationship_info`）
- **关联表**：relationship；Redis
- **状态**：已实现

#### GET /api/relationship/history

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data` 为数组：今日各行为 `action_type`, `earned_today`, `daily_limit`, `points_per_action`（读 Redis 旧 key 前缀 `growth:{user_id}:{date}:{action_type}`，写入侧同时写新旧 key，仍可读）
- **状态**：已实现

#### GET /api/relationship/detail

- **所属端**：H5
- **鉴权**：Bearer
- **响应**：`ApiResponse`；`data`：level_info, growth_info, milestones, level_history, today_growth, ai_current_emotion
- **状态**：已实现

#### GET /api/relationship/growth-log

- **所属端**：H5
- **鉴权**：Bearer
- **Query**：`page`, `page_size`
- **响应**：`ApiResponse`；`data`: `{ list, total, page, page_size }`（`list` 项：id, action_type, action_label, points, created_at）
- **关联表**：relationship_growth_log
- **状态**：已实现

---


### 模块：H5 朋友圈 / 生活流（`/api/feed`）

> 全部 JWT；响应 `{"code":0,"data":{},"message":"success"}`。路由：`backend/routers/feed.py`。  
> **与对话主链**：v1 **无** Feed/世界观注入 Prompt；感知 IM 与 P0–P4/Future **业务零耦合**，仅共用 `agent_message` + `sort_seq` + 未读角标 API。

#### GET /api/feed/list

- **Query**：`cursor`（可选，上一页最后一条 `scheduled_publish_time` ISO）、`size`（默认 20，上限 50）
- **过滤**：`scheduled_publish_time<=feed_now()` · `is_visible=1` · `generation_status='ready'` · 历史窗 `feed_history_visible_range`（相对 `feed_now()`）
- **响应 `data`**：`{ posts:[{ id, content_text, hashtags, image_urls, scheduled_publish_time, emotion, city, display_likes, user_liked, display_comments, comments:[{ id, content, reply_to_lxm, lxm_reply, lxm_reply_at, lxm_reply_read_at }] }], next_cursor }`
- **约定**：评论**仅当前用户**私有；`scheduled_publish_time` 为北京墙钟 ISO（无 `Z`）；`city` 来自 `feed_post.city`（可空串）；`display_comments` 为计算字段；命中且 `actual_publish_time IS NULL` 懒惰写回
- **状态**：已实现

#### POST /api/feed/enter

- **写** `users.last_feed_entered_at=feed_now()`；`data`: `{ anchor_comment_id }`（最近未读 LXM 回复评论 ID，可 null）
- **状态**：已实现

#### GET /api/feed/badge

- **`data`**：`{ has_new, new_post_count, unread_reply_count }`
- **`has_new`**：存在已到点可见帖且（`scheduled_publish_time > last_feed_entered_at` 或从未进入）
- **`new_post_count`**：同上口径条数；**从未 enter** 时固定 `0`（此时若有可见帖仍可 `has_new=true`）
- **`unread_reply_count`**：当前用户未读 LXM 回复数
- **H5**：首页未读胶囊 / 底栏新动态；聊天角标 = `unread_reply_count + new_post_count`；有未读回复跳转 `?focus=unread_reply`
- **状态**：已实现

#### GET /api/feed/config/header

- **`data`**：`{ header_bg_url, header_avatar_url, signature, display_nickname }`（缺省回落 `life_feed_config`）
- **状态**：已实现

#### POST /api/feed/{post_id}/like

- 幂等点赞；真实新增时 `real_likes+1`；**先 commit 点赞事务再** `await like_aware_service.on_like_hook`（TB-LF-009）
- **响应**：`{ user_liked: true, display_likes }`
- **状态**：已实现

#### DELETE /api/feed/{post_id}/like

- 幂等取消；`real_likes-1`（`AND real_likes>0`）；**不撤回**已触发感知 IM
- **状态**：已实现

#### POST /api/feed/{post_id}/comments

- **Body**：`{ content, reply_to_lxm? }`（content 1~200；同帖 30s 频控；内容安全）
- **响应**：`{ comment_id, created_at, gen_status, reply_to_lxm }`
- **首次评论**：原子抢占 `has_ever_commented_feed` → `due_at=utcnow()+30s`；否则按关系档延迟（`comment_reply_delay_{stage}_{min|max}`，stage∈stranger/friend/intimate/**soulmate**）
- **`reply_to_lxm`**：仅展示标记；LLM-05 仍单条必回、无历史评论注入
- **状态**：已实现

#### GET /api/feed/events（SSE）

- **鉴权**：Query **`token`**（EventSource 无法带 Header）；`text/event-stream`；15s heartbeat 注释行
- **事件**：`{"type":"feed_new","delta":<本轮新帖数>}`；断线不补历史
- **状态**：已实现

#### POST /api/feed/comments/{comment_id}/read

- 写 `lxm_reply_read_at`（幂等）；越权 **`code=10506`** `ERR_FEED_COMMENT_FORBIDDEN`
- **状态**：已实现

#### POST /api/feed/{post_id}/read

- 校验可见+到点（`feed_now()`）后 `read_aware_service.on_feed_read`
- **状态**：已实现

#### 错误码（10500 段）

| code | 常量 | 说明 |
|------|------|------|
| 10500 | `ERR_FEED_POST_NOT_FOUND` | 不存在 / 未到点 / 隐藏 |
| 10501 | `ERR_FEED_POST_HIDDEN` | 管理员隐藏（预留） |
| 10502 | `ERR_COMMENT_EMPTY` | 评论为空 |
| 10503 | `ERR_COMMENT_TOO_LONG` | 超过 200 字 |
| 10504 | `ERR_COMMENT_RATE_LIMIT` | 30s 内重复评论 |
| 10506 | `ERR_FEED_COMMENT_FORBIDDEN` | 无权操作该评论 |
| — | `ERR_CONTENT_SAFETY_VIOLATION` | 内容安全（全局码） |

#### 感知 IM 服务约定（非独立 HTTP）

| 服务 | 要点 |
|------|------|
| `agent_aware_service` | 独立表排队；60s 轮询；落 `agent_message`（`action_score=0`）+ `allocate_sort_seq`；**不**走日上限 8 次 / 30min / 黑名单 / action_score |
| `like_aware_service.on_like_hook` | 同帖去重 → 特殊档（CAS 占位，入队失败回滚计数）→ 常规 30%；Prompt `prompt_p07`；节点 `llm_06` |
| `read_aware_service` | 多帖取最近一条；点赞后抑制；**用户级冷却**（`read_aware_user_cooldown_hours`，默认 6h，按入队 `created_at` 滚动，窗口内最多 1 条 `READ_AWARE`）；特殊档 `prompt_p14` / 常规 `prompt_p08~p11`；节点 `llm_07`；特殊档计数同 CAS+回滚 |
| `feed_sse_service` | 单进程内存注册表（v1 单实例） |

#### 定时任务（APScheduler · Asia/Shanghai）

| 触发 | 任务 | 说明 |
|------|------|------|
| 周日 23:00 / 23:30 | `weekly_outline_task` / `_retry` | LLM-01 |
| 每日 00:20 / 00:30 | `daily_scenes_task` / `_retry` | LLM-02 当日场景 |
| 每日 00:45 | `daily_her_universe_task` | LLM-03 |
| 每日 01:00 | `daily_feed_publish_task` | LIFE001 |
| 每 30s | `comment_reply_poll_task` | LLM-05（`due_at` UTC） |
| 每 60s | `agent_aware_poll_task` | 感知队列消费（`due_at` UTC） |
| 每 30s | `feed_new_broadcast_task` | SSE：`ready+visible+scheduled<=feed_now()+sse_broadcasted=0` |

手动：`python -m backend.tasks.life_feed_task <task_name>`

#### DeepSeek / Liblib / OSS / Redis（生活流）

| 项 | 约定 |
|----|------|
| DeepSeek 超时 | 单次默认 **45s**，retry=2，退避 2s/4s；与豆包超时互不影响 |
| Liblib payload | `templateUuid` + `generateParams`；selfie 含 `sourceImage`/`strength`/`resizedWidth`/`resizedHeight`；键见 `liblib_*` admin_config |
| 同帖多图 | `imgCount` 固定 1；`count≥2` 按 seq 构图变体 + 独立 seed；进行中任务并发 **1** |
| OSS 路径 | `lxm/posts/{post_id}/{seq:02d}.webp` |
| Redis | `liblib_stats:{YYYYMMDD}`；`active_config:{key}`；DeepSeek 复用 `llm_stats` / `llm_response_times` |

#### 关系档映射（代码常量）

`RELATIONSHIP_STAGE_MAP`：`0→stranger` · `1→friend` · `2→intimate` · `3→soulmate`（知己）。唯一来源：`backend/constants/life_feed_config.py`。

#### H5 `feed.html` 展示口径（摘要）

| 项 | 约定 |
|----|------|
| 路由 | `/pages/feed.html`；`?focus=unread_reply`；与 index/chat/memory 互通 |
| 时间 | `scheduled_publish_time` 按北京墙钟字符串解析 |
| 城市 | 左列弱化定位 + 城市名（无天气） |
| 评论角标 | `display_comments`；发评本地 +1 |
| 落款 | `reply_to_lxm=false`→「我：」；`true`→「我回复 林小梦：」；LXM「林小梦回复 我：」 |
| 话题 | 正文单 `#` 着色（兼容 `#话题#`）；不单独渲染 `hashtags[]` 行 |
| 进页 boot | `#feed-boot-loading`；渐进 alpha/blur；8s 硬超时；哨兵延后挂载（TB-LF-010） |
| SSE 提示条 | 「林小梦更新了 N 条动态」= **新帖** delta，**不是**评论回复未读 |
| 已读 | 回复曝光 0.6 上报；卡片停留 3s；观察器须 observe **自身** `.feed-item` |
| 列表 UI | 同日左列合并、meta 行左时间右展开、单图 4:3、评论无「正在回复」占位等（详见草案快照 / 《朋友圈页面展示逻辑规范》v1.6） |

---

### 模块：H5 用户（占位）

- **文件**：`backend/routers/user.py` 当前**无路由实现**；**未在 `main.py` 挂载**（保持不挂载）。
- **说明**：已在 `routers/user.py` **文件顶部**加入占位 TODO 注释；**产品需求确认前不挂载**，避免与其他模块路由命名冲突；实现昵称、头像等个人资料接口时在本文件扩展并再 `include_router`。
- **H5 设置页**：`frontend/pages/settings.html` 仍调用 **`GET/PUT /api/user/settings`**（`memory_auto_extract`、`agent_message_enabled`），后端未实现；见 **TD-024**。
- **状态**：占位（详见该文件内注释）

---

### 模块：管理后台认证（`/api/admin/auth`）

#### 安全与会话通用约定

- `ADMIN_JWT_SECRET` 必须显式配置；缺失、空值、纯空白、`admin_secret_change_me`、`your_admin_jwt_secret_here` 在配置读取或应用启动时均失败。阶段 A 不额外规定长度、复杂度或轮换规则，用户端 `JWT_SECRET` 不受影响。
- 新签发 Admin JWT 含整数 `token_version`；统一鉴权以数据库账号为最终事实，校验 Token 类型、签名、过期、账号存在/启用/未锁定及实时版本。历史无版本、非整数或版本不匹配 Token，以及无效账号状态均返回 HTTP 401。
- 下列事件成功后 `token_version` 精确递增一次：第五次错密锁定、自助改密、登出、超级管理员重置他人密码、他人角色实际变化。仅修改备注、提交相同角色、手动解锁不递增；解锁不恢复锁定前 Token。
- 登出按账号撤销全部会话，本阶段不实现单设备 Token 黑名单。

#### POST /api/admin/auth/login

- **所属端**：管理后台
- **Body**：`AdminLoginRequest` — username, password
- **响应**：`ApiResponse`；`data`: token, username, role, need_change_password（**接口字段未变**；`token` 内嵌 JWT 的 `sub` 实现上为字符串，见上文「统一说明」鉴权条）
- **失败响应**：不存在账号、密码错误、账号锁定、账号停用统一返回 HTTP 200，`{"code":20001,"data":null,"message":"账号或密码错误"}`；不存在账号执行固定伪 bcrypt，真实原因仅进入不含提交凭据的服务端安全日志。
- **并发与锁定**：已存在账号的登录查询使用 `SELECT ... FOR UPDATE`；锁定检查、密码校验、失败计数、第五次锁定和成功清零在同一事务完成。第 5 次错密后保持 `login_fail_count=5`、`is_locked=true`，并仅在该锁定事件递增一次 `token_version`；锁定后继续尝试不再改变状态。
- **关联表**：admin_users；admin_operation_logs（登录日志）
- **状态**：已实现

#### POST /api/admin/auth/logout

- **Body**：无
- **响应**：`ApiResponse`；需 Bearer Admin JWT；成功 **`code=0`**，`data` 可为 `null`，**`message`**「已退出登录」
- **会话语义**：成功时在同一事务递增当前账号 `token_version`，该账号全部既有 Token 随即失效；其他账号不受影响。
- **关联表**：admin_operation_logs（登出日志）
- **状态**：已实现

#### POST /api/admin/auth/change-password

- **Body**：`AdminChangePasswordRequest` — **`old_password`**、**`new_password`**、**`confirm_password`**（各 `min_length=1`，`max_length=100`）；新密码强度与 **`_validate_admin_password`** 一致（≥12 位，含大写、小写、数字、特殊字符）
- **语义**：当前登录管理员修改**本人**密码；校验旧密码通过后更新 `password_hash` 与 **`last_password_change_at`**，并记操作日志（`module=系统`，`action=edit`，描述含「修改密码」）
- **会话语义**：成功时 `token_version` 递增一次，使当前及其他设备的旧 Token 全部失效；失败分支不修改密码或版本。前端成功后清除本地会话并跳转登录页。
- **响应**：`ApiResponse`；成功 **`code=0`**，**`message`**「密码修改成功」；失败：**`20004`** `ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG`；**`20005`** `ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD`；**`20006`** `ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH`；**`20007`** `ADMIN_ERR_AUTH_PASSWORD_POLICY`（`message` 可为具体校验文案）
- **管理端**：**`admin/static/js/admin-api.js`** — **`renderHeader`** 渲染顶栏「修改密码」按钮；**`showChangePasswordModal()`** 弹窗收集三项密码，`adminRequest('POST', '/api/admin/auth/change-password', { old_password, new_password, confirm_password })`；前端先于请求校验非空及 **`new_password === confirm_password`**（不一致时 Toast「两次新密码不一致」，与后端 **20006** 语义一致）
- **状态**：已实现

---

### 模块：管理后台账号（`/api/admin`，super_admin）

- **GET** `/accounts` — 响应 `ApiResponse`；`**data` 为管理员账号的平铺数组**（**无** `total` / `page` / `page_size` / `list` 等分页包装）。单条字段：`id`, `username`, `role`, `remark`, `last_login_at`, `is_active`, `is_locked`, `created_at`（时间字段为 ISO 字符串或 `null`）。
- **POST** `/accounts` — Body：`AdminCreateAccountRequest` — `username`（1–50）、`password`（1–100，强度见下）、`role`（`super_admin`  `ops_admin`  `ai_trainer`  `tech_ops`  `observer`）、`remark`（可选，≤200）。成功 `data` 为新账号 `_admin_to_dict`。前端 `**adminRequest(..., { silentErrorToast: true })`** 后按业务码处理：`**20014`**（`ADMIN_ERR_ACCOUNT_USERNAME_EXISTS`）→ Toast「账号名已存在，请换一个」；`**20007`**（`ADMIN_ERR_AUTH_PASSWORD_POLICY`）→ Toast「密码不符合复杂度要求」；其余非 0 → `message` 或「操作失败」。**密码复杂度**与后端 `_validate_admin_password` 一致，前端实时校验 5 项：≥12 位、含大写 A-Z、含小写 a-z、含数字 0-9、含特殊字符（非字母数字）。
- **PUT** `/accounts/{account_id}` — Body：`AdminUpdateAccountRequest`，**partial update**：`role`、`remark` 均为 **Optional**，**JSON 中未传或值为 `null` 的字段不修改**；`remark` 传空字符串 `""` 时表示清空备注。成功 `data` 为更新后的 `_admin_to_dict`。前端 `**silentErrorToast: true`** 时建议处理：`**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ Toast「账号不存在」；`**20016`**（`ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE`）→ Toast「不可修改自己的角色」（编辑他人账号时兜底；当前登录用户仅改自己备注时请求体应**只含 `remark`**、**不传 `role`**，避免误触 20016）。
- **角色变化会话语义**：超级管理员把他人角色实际改为不同值时，目标账号 `token_version` 递增一次；仅修改备注或提交相同角色不递增。
- **POST** `/accounts/{account_id}/reset-password` — **管理员账号**重置密码（**勿与**用户管理 `**POST /api/admin/users/{user_id}/reset-password`** 混淆）。Body 无。成功 `data`：`{ "new_password": string }`，为 **16 位**随机强密码（含大小写、数字、特殊字符，满足 `_validate_admin_password`）。失败 `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）→ 前端 Toast「账号不存在」（建议 `silentErrorToast: true`）。**管理端 `accounts.html`**：确认弹窗后请求；成功后打开「密码重置成功」Modal 展示 `new_password`（`user-select: all` 等样式）；「复制密码」优先 `navigator.clipboard.writeText`，不支持时用临时 `textarea` + `document.execCommand('copy')`；「我已记录」关闭 Modal，**不刷新列表**。
- **重置密码会话语义**：成功时目标账号 `token_version` 递增一次，目标账号全部旧 Token 失效。
- **POST** `/accounts/{account_id}/unlock` — Body 无。若账号**不存在** → `**20015`**（`ADMIN_ERR_ACCOUNT_NOT_FOUND`）。若账号**未锁定**（`is_locked=false`）→ 仍返回 `**code=0`**（`ApiResponse.ok`），`message` 为「该账号未被锁定」——**非业务错误码**；前端可统一按 `code=0` 视为成功（如 Toast「账号已解锁」后刷新列表）。若已锁定则清除锁定与登录失败计数并记操作日志 → `code=0`，`message`「账号已解锁」。建议 `**silentErrorToast: true`**，`**20015**` → Toast「账号不存在」。
- **解锁会话语义**：解锁不递增 `token_version`，也不恢复锁定前已失效的 Token。
- **DELETE** `/accounts/{account_id}` — 成功 `code=0`，`message`「删除成功」（无额外 `data` 要求）。失败：`**20015`** 账号不存在；`**20017**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF`）不可删除自己；`**20018**`（`ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER`）超级管理员账号不可删除。前端 `**silentErrorToast: true**` 时建议：`20015` →「账号不存在」、`20017` →「不可删除自己的账号」、`20018` →「超级管理员账号不可删除」。
- **关联表**：admin_users
- **状态**：已实现
- **管理端页面**：`admin/pages/accounts.html`
  - Step 1：骨架、权限初始化（`checkAdminLogin` → 非 `super_admin` 跳转 `error.html?type=403` → `currentUsername` / `loadAccountList`）；`currentUsername` 与 `accountMap` 声明在 **script 顶层**，避免放在 `DOMContentLoaded` 闭包内导致全局 `onclick` 等函数无法访问。
  - **Step 2 完成**：列表加载（`GET /api/admin/accounts`）、`account-table-wrap` 内 **3 行骨架屏**、成功渲染表格列（账号 / 角色 / 备注 / 创建时间 / 最后登录 / 状态 / 操作）、失败或响应异常时文案「加载失败，请刷新重试」、空数组「暂无账号数据」；**行数据**在渲染前 `**accountMap.clear()`** 再 `**accountMap.set(id, row)`**；操作列 `**onclick` 仅传数值 `id`**，回调内 `**accountMap.get(id)**` 取完整行，**避免** `JSON.stringify` 写入 HTML 属性时特殊字符破坏引号。
  - **Step 3 完成**：**创建账号 Modal** — `openCreateModal()` 打开 `#create-account-modal-overlay`（`modal-overlay` + `modal-content` / `modal-header` / `modal-body` / `modal-footer`），并重置字段与校验状态；表单含账号（必填 max 50）、密码（必填，**oninput** 五项复杂度 ✓/✗，全绿且账号非空、确认密码一致、已选角色后启用「确认创建」）、确认密码（不一致时红色「两次密码不一致」）、角色 select（占位「请选择角色」）、备注 textarea（选填 max 200）；提交 **POST** `/api/admin/accounts`，成功关闭 Modal、Toast「账号创建成功」、`**loadAccountList()`**。
  - **Step 4 完成**：**编辑 Modal（含自身备注）** — **入口 A**（`row.username !== currentUsername`）：操作列「编辑」→ `openEditModal(id)`，打开 `#edit-account-modal-overlay`；打开时 `**resetEditAccountModal()`** 再写入行数据；顶部灰色说明「正在编辑：{username}」（`.modal-hint`）；角色 select 与 Step 3 相同选项、预填 `row.role`、必选；备注 textarea 预填、选填、**maxlength=200**；提交 **PUT** `/api/admin/accounts/{id}`，Body `**{ role, remark }`**（`silentErrorToast: true`），`**20015`** →「账号不存在」、`**20016**` →「不可修改自己的角色」；成功关闭、Toast「账号已更新」、`**loadAccountList()**`。入口 B（自身）：「修改备注」→ `openEditRemarkModal(id)`，打开 `#edit-remark-modal-overlay`；打开时 `**resetEditRemarkOnlyModal()**` 再写入；顶部说明「仅可修改自己账号的备注」；**不渲染角色下拉**（独立 Modal，DOM 中无角色字段）；提交 Body **仅 `{ remark }`**；成功 Toast「备注已更新」并 `**loadAccountList()**`。
  - **Step 5 完成**：**重置密码** — 非自身行操作列「重置密码」→ `openResetPasswordModal(id)`（`accountMap.get(id)`）；`**showConfirm`** 文案「确认重置「{username}」的密码？系统将生成新的强密码。」（用户名需 **HTML 转义** 后插入确认层）；确认后 **POST** `/api/admin/accounts/{id}/reset-password`（`silentErrorToast: true`），`**20015`** → Toast「账号不存在」；成功则 `**showResetPasswordResultModal(data.new_password)`**，`**#reset-password-result-modal-overlay`** 标题「密码重置成功」、正文说明 + 新密码展示区（monospace 20px 等）；「复制密码」→ Clipboard API + `**execCommand('copy')**` 兜底；「我已记录」或关闭 → `**closeResetPasswordResultModal()**`，**不** `loadAccountList()`。
  - **Step 6 完成（accounts.html 全部功能）**：**解锁** — `is_locked=true` 时操作列「解锁」→ `unlockAccount(id)`；`**showConfirm`**「确认解锁「{username}」的账号？」（用户名 **escapeHtml**）；**POST** `/api/admin/accounts/{id}/unlock`（`silentErrorToast: true`）；`**code=0`** → Toast「账号已解锁」、`**loadAccountList()**`（含未锁定账号误触时后端仍 `code=0` 的约定）；`**20015**` →「账号不存在」。**删除** — 非自身且非 `super_admin` 行「删除」→ `deleteAccount(id)`（自身无删除按钮、`super_admin` 行按钮 `disabled` 已在 Step 2）；`**showConfirm(..., null, { danger: true })`**（`admin-api.js` 危险样式：`modal-content--danger` + 确认钮 `btn-danger`），文案「确认删除「{username}」？此操作不可恢复。」；**DELETE** `/api/admin/accounts/{id}`（`silentErrorToast: true`）；`**20017`** / `**20018**` / `**20015**` 对应上述 Toast；成功 Toast「账号已删除」、`**loadAccountList()**`。

---

### 模块：管理后台观察者统一权限契约（`observer`）

> **权限优先级**：本节是 2026-07-17 起 observer 的权威增量契约。本文后续各历史模块/页面条目中仅列原四角色的旧记录，原四角色能力保持不变，observer 的 GET/HEAD 增量和写入/导出拒绝均以本节为准；不得因旧条目的混合 GET|PUT 表述向 observer 扩展任何写权限。

#### 五角色体系

| 角色 | 展示名 | 主要能力 |
|------|--------|----------|
| `super_admin` | 超级管理员 | 全部后台能力及账号管理 |
| `ops_admin` | 运营管理员 | 用户、统计、运营和操作日志的既有能力 |
| `ai_trainer` | AI训练师 | 人格、Prompt、记忆、Agent、关系/日记及 AI 测试的既有能力 |
| `tech_ops` | 技术运维 | 系统监控、第三方、系统/操作日志的既有能力 |
| `observer` | 观察者 | 除账号管理和系统内建导出外的已批准业务数据只读查看 |

#### 后端最终权限边界

- 所有需鉴权的 Admin 请求先校验 JWT 类型、签名、过期、`token_version`、账号存在/启用/未锁定及数据库实时角色；前端 `sessionStorage` 角色不是授权依据。
- observer 可进入各端点已明确批准的 GET/HEAD 读取集合；读取不得写 MySQL 业务数据、权限/账号状态、配置版本，不得触发生成、测试、发布、修复、回填、删除或异步任务；只允许从权威读结果派生的有限 TTL 幂等缓存回填。
- observer 的 POST/PUT/PATCH/DELETE 在统一鉴权入口默认返回 HTTP 403，业务处理器不执行；仅精确放行 `POST /api/admin/auth/logout` 和 `POST /api/admin/auth/change-password`。
- `GET /api/admin/accounts` 及账号列表、创建、编辑、重置密码、解锁、删除始终仅 `super_admin`；observer 不获得账号数据。
- 操作日志、数据报表、系统日志三个现有内建导出路由额外挂载与 HTTP 方法无关的 observer 拒绝依赖；今后新增 export/download 路由也必须显式拒绝。
- 匿名 OPTIONS 仅由 CORS 中间件处理预检，返回预检结果而非业务数据；匿名 GET/HEAD 和写请求仍须正常鉴权。

#### 已批准读取与敏感数据

- observer 可读取用户列表/详情/对话/情绪轮次/日记、统计、脱敏操作与系统日志、AI 人格/Prompt/测试配置、记忆/向量/知识/Agent/关系/日记/情绪/世界状态、系统/第三方状态及生活流现有业务读取。
- 第三方凭据仅附加布尔 `credential_configured`，用户 Open API Key 仅返回布尔 `enabled`，DashVector 仅返回配置状态；不得返回原文、首尾/prefix/suffix、掩码片段、哈希或可推断凭据的时间元数据。
- 操作日志 `target_description` / `before_value` / `after_value` 写入前脱敏，列表/详情/导出读取时再脱敏；系统日志列表/导出使用同一共享、递归、幂等、失败关闭工具。

#### 前端 35 页只读体验

- observer 菜单复用业务读取导航但不显示账号管理，Header 显示“观察者”；直访 `accounts.html` 在请求账号数据前跳转 403 错误页。
- `isObserver()` 是统一角色判断；`data-write-action` 标记写控件，`applyObserverReadOnly()` 对首屏和 MutationObserver 发现的动态节点重复应用：写按钮/链接隐藏，展示型 input/textarea 只读，select、checkbox/radio、range 和 file 控件禁用。
- `adminRequest()` 为 observer 提供非读取请求的前端体验兜底，不替代后端总闸；搜索、筛选、分页、Tab、详情、复制、日期切换、描述展开、状态/统计查看及纯 GET 刷新保持可用。
- “禁止导出”仅指系统内建导出/下载/生成报表，不承诺防截图、复制、开发者工具读取或跨分页聚合。

#### 验证和发布事实

- 后端门禁固定当前 159 个 Admin 路由（69 个 GET/HEAD、90 个写方法）、两个精确 POST 例外及三个导出；STEP-039 专项 98 通过。
- 35 页五角色浏览器验收、页面静态组合 39 通过、range 修复相关回归 13 通过；全量 pytest 917 通过 / 0 失败 / 4 跳过。
- 阶段 B 于 2026-07-16 17:02 CST 独立部署，项目所有者于 2026-07-17 确认暂无问题；STEP-040 临时 observer 验收账号已删除。

---

### 模块：管理后台操作日志（`/api/admin`）

- **GET** `/operation-logs`（Query：admin_username, module, action, start_date, end_date, page, page_size）
- **GET** `/operation-logs/{log_id}`
- **POST** `/operation-logs/export`（Excel 流）
- **导出参数说明**：服务端以 **Query** 接收 `admin_username`、`module`、`action`、`start_date`、`end_date`（与列表筛选一致），**非** JSON Body；前端 `POST` 时将条件拼在 URL 查询串上、Body 为空即可触发 `adminRequest` 的 blob 下载逻辑。
- **响应列表**：`data`: `{ total, page, page_size, list: [...] }`；`list[]` 含 `id`, `admin_user_id`, `admin_username`, `module`, `action`, `target_description`, `ip_address`, `created_at`
- **详情**：`GET /operation-logs/{log_id}` 成功 `data` 另含 `before_value`, `after_value`（可为 `null`）
- **关联表**：admin_operation_logs
- **鉴权角色**：列表/详情 GET 为 `super_admin` / `ops_admin` / `tech_ops` / `observer`（`ai_trainer` 无此菜单与接口权限）；导出仍仅原三角色并显式拒绝 observer。
- **凭据脱敏**：`target_description`、`before_value`、`after_value` 写入前统一脱敏；列表、详情和 Excel 导出返回前再次脱敏，以遮蔽历史遗留明文。单字段异常失败关闭为 `[REDACTED]`，不批量改写历史数据库行。
- **状态**：已实现
- **管理端页面**：`admin/pages/operation-logs.html`
  - 首屏：`DOMContentLoaded`（若文档已就绪则立即执行）触发 `loadLogs(1)`。
  - 筛选：`admin_username` 输入框；`module` / `action` 下拉的选项与当前仓库内所有 `log_operation(..., module=, action=)` 写入值一致（模块：`ai_config`、`memory`、`third_party`、`用户管理`、`账号管理`、`系统`；类型：`batch_delete`、`create`、`delete`、`edit`、`login`、`logout`、`publish`、`unlock`、`update_config`）；日期 `start_date` / `end_date`；搜索/重置调用 `loadLogs(1)`；**导出 Excel** 为 `POST /api/admin/operation-logs/export` + 当前筛选的 Query 串。
  - 列表：`page_size=20`，列 时间 / 操作人 / 操作模块 / 操作类型 / 操作描述 / 详情；操作类型 Tag：`publish`→`tag-success`，`delete` 与 `batch_delete`→`tag-error`，`rollback`→`tag-warning`（仅当库中仍存在该 `action` 的旧记录时可能见到），其余→`tag-default`。
  - 详情：`GET /api/admin/operation-logs/{id}`，Modal 宽 680px，展示操作人/模块/类型/时间/IP，修改前（`#fff2f0`）与修改后（`#f6ffed`）`<pre>` 对比，无数据展示「（无）」。
  - **说明**：`action` 筛选下拉的选项**仅包含**当前代码路径里 `log_operation(..., action=)` 的实际写入值，**不包含** `rollback`。人格/Prompt 等「回滚」接口经 `AdminConfigService.rollback_config` → `publish_config` 记日志时，`action` 为 **`publish`**（`target_description` 等可体现回滚语义）。

---

### 管理端列表日期筛选（`admin_date_filter`）

以下接口 Query 的 **`start_date` / `end_date`**（`YYYY-MM-DD`）共用 **`backend/services/admin_date_filter.py`**：

- **`start_date`**：`created_at >= 当日 00:00:00`
- **`end_date`**（闭区间日历日）：`created_at < end_date + 1 day`
- **`start_date > end_date`** 或格式非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`（20029）**（反选时 message：「结束日期不能早于开始日期」）

**适用接口**：**`GET /users/{user_id}/conversations`**、**`GET /users/{user_id}/emotion-rounds`**、**`GET /users/{user_id}/diaries`**、**`GET /diary-history`**、**`GET /agent-messages`**。

**例外（未纳入本工具）**：**`GET /operation-logs`** 仍按 `end_date` 当日 **23:59:59** 闭区间过滤（`operation_logs.py`）。

---

### 模块：管理后台用户管理（`/api/admin`）

- **GET** `/users` — Query 筛选 username, relationship_level, status, 注册/登录时间范围, page, page_size；`data.list` 含 id, username, created_at, last_login_at, relationship_level, growth_value, total_conversation_count, status
- **管理端列表页（`admin/pages/users.html`）**：表格首列展示 **`list[].id`（用户 ID）**，便于与日记历史等处的 `user_id` 对照；接口字段未增删。
- **说明（关系字段数据源）**：**用户列表** `data.list[]` 与**详情页展平后的** `**userData`** 使用字段名 `**relationship_level`、`growth_value`**；详情接口原始 JSON 中对应为 `**data.relationship.level`、`data.relationship.growth_value`**。上述数值均来自 `**relationship` 表**（模型字段 `Relationship.level`、`Relationship.growth_value`），与用户端 `RelationshipService` 权威读法一致（按 `user_id` 关联；无行时按等级 0、成长值 0）。`**users` 表同名列为历史遗留，本模块不作为数据源**，详见 `[tech-debt.md](tech-debt.md)` **TD-001**。
- **GET** `/users/{user_id}` — 响应 `data` 为嵌套对象（HTTP 层不变）：
  - `**basic`**：`id`, `username`, `created_at`, `last_login_at`, `status`（`normal`  `banned`）, `is_banned`
  - `**relationship`**：`level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`
  - `**activity`**：`total_conversation_count`, `active_days_last7`, `agent_message_reply_count`
- **管理端详情页（`admin/pages/user-detail.html`）**：成功拉取详情后，仅在 `**loadUserDetail`** 内将上述嵌套**展平**为脚本内存变量 `**userData`**（不修改接口响应）。展平规则：`basic.*` 字段名保持不变；`relationship.level` → `relationship_level`；`relationship` 其余键名不变；`activity.active_days_last7` → `active_days_7d`；`activity.agent_message_reply_count` → `agent_reply_count`；`activity.total_conversation_count` 不变。若 `data` 缺少 `basic` / `relationship` / `activity` 任一层，前端提示「用户详情数据格式异常」且不写入 `userData`。**「AI日记」Tab**：**首次**切换到该 Tab 时请求 **`GET /users/{user_id}/diaries`** **不带**日期（全量时间、倒序第一页）；再次进入同一用户详情会话内 **不重复**首屏请求；**「查询」**按当前日期输入从第 1 页重拉；**「加载更多」**在同一组日期条件下分页追加；表格列含日记 **`id`**（与 **`diary-history`** 第一列一致）、正文摘要、`relationship_level_at_creation` 映射等级名、已读、**`covers_beijing_date`（覆盖日）**、创建时间；正文 **`escapeHtml`**。
- `**userData` 展平后字段全集**（仅浏览器脚本内存，**非** HTTP 响应体）：`id`, `username`, `created_at`, `last_login_at`, `status`, `is_banned`, `relationship_level`, `level_name`, `growth_value`, `next_threshold`, `progress_percent`, `total_conversation_count`, `active_days_7d`, `agent_reply_count` — 与 `loadUserDetail` 实现一致，供 `renderInfoCards`、账号 Tab、顶栏操作等读取。
- **GET** `/users/{user_id}/conversations` — **数据源**：合并 **`conversation_log`** 与 **`agent_message`**（主动消息仅存在于后者，与 H5 一致）。**Query**：`start_date`、`end_date`（见上文 **`admin_date_filter`**，两表均按 `created_at` 过滤）、`page`、`page_size`（1–100）。**排序**：全局 **`sort_seq` 升序**，同 `sort_seq` 时 **`id` 升序**（再分页），与用户端时间线合并规则一致。**`data.total`**：两表在日期条件下的行数之和。**`data.list[]` 公共字段**：`id`、`role`、`content`、`persona_risk_flag`、`created_at`、`sort_seq`。**来源区分**：**`message_source`** — `conversation`（来自 `conversation_log`）| `agent`（来自 `agent_message`）。两表各自自增 `id` 可能数值重合，**唯一键为 `(message_source, id)`**。——**`message_source === conversation`**：`emotion_label`、`emotion_confidence`（仅 user 行）、`delivery_status`、`skipped_in_prompt`（assistant 行二者均为 **null**，user 行按库）；**`trigger_type`、`is_read` 固定为 null**。——**`message_source === agent`**：`role` 固定 **`assistant`**，`emotion_*` 为 null，`persona_risk_flag` 固定 **false**，`delivery_status` / `skipped_in_prompt` 为 **null**，**`trigger_type`** 为 `agent_message.trigger_type`（如 `P0`…`P4`、`FUTURE`），**`is_read`** 为布尔。与 H5 **`GET /api/chat/timeline`**：`items[]` 中对话行对应 `source` 为 `user`/`assistant`，主动消息对应 `source: agent`；管理端使用字段名 **`message_source`** 而非 `source`，语义可对齐查阅。
- **管理端详情页「历史对话」Tab（`admin/pages/user-detail.html`）**：列表渲染读取 **`message_source`**；**`agent`** 行展示 **`trigger_type`** 标签及 **`is_read === false`** 时的「未读」标签，气泡左侧条样式与主动消息区分。**日期筛选**：**`#conv-start-date` / `#conv-end-date`** 默认 **今天 −7 天 ~ 今天**（仅输入框为空时写入）；**「查询」**与首屏均走 **`loadConversationsInitial`**：先 **`page=1`** 取 **`total`**，再请求 **`page=ceil(total/page_size)`** 渲染（区间内**最新**一页）；列表上方 **「加载更早」** 请求 **`page=当前页−1`** 并 **prepend**（保留滚动位置）；接口侧仍为 **`sort_seq` 升序**分页。
- **GET** `/users/{user_id}/emotion-rounds` — 鉴权 **`super_admin` / `ops_admin`**（与 **`.../conversations`** 一致）。Query：`start_date`、`end_date`（见上文 **`admin_date_filter`**）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**。成功 `data`：`{ total, page, page_size, list[] }`；**`list[]`**：`emotion_log_id`, `round_id`, `emotion_label`, `confidence`, `created_at`, `anchor_conversation_id`, `user_text`（同 `round_id` 下 **user 行按 `sort_seq` 升序**换行拼接）, `assistant_text`（同 `round_id` 下 **assistant 行按 `sort_seq` 升序遍历后的末条** `content`；多气泡轮次与 STEP-011 一致，非首条）。排序：**`emotion_log.created_at` 降序**（最新轮在前）。**管理端详情页「情绪日志」Tab** 首屏**不传**日期（全量时间、降序第一页）。
- **GET** `/users/{user_id}/diaries` — 鉴权 **`super_admin` / `ops_admin` 仅**（与 **`.../conversations`**、**`GET /diary-history`** 一致；**不含** `ai_trainer`，与 **`.../memories`** 不同，属有意区分）。Query：`start_date`、`end_date`（见上文 **`admin_date_filter`**）、`page`、`page_size`（1–100）。用户不存在 → **`ADMIN_ERR_USER_NOT_FOUND`**；日期非法 → **`ADMIN_ERR_QUERY_DATE_FORMAT_INVALID`（20029）**。成功 `data`：`{ total, page, page_size, list }`；**`list[]`** 字段与 **`GET /api/admin/diary-history`** 的 **`list[]`** 相同：`id`, `user_id`, `username`, `content`, `relationship_level_at_creation`, `is_read`, `created_at`, `covers_beijing_date`。实现上与 **`diary-history`** 共用 **`backend.services.admin_diary_query`**，避免双入口不一致。
- **用户记忆 / 私有状态（长记忆第一套下线，C-01/C-09/P3/P5/§6.2.2）**：旧 **`GET/PUT/DELETE /users/{user_id}/memories*`** 已删除，改为两组基于 Step6 向量的 KV CRUD，**主键 `doc_id`**（不再用 `memory_id`），写操作记 `admin_operation_logs`（module 区分 `user_memory` / `private_setting`）。权限 **`super_admin` / `ops_admin` / `ai_trainer`**（P5）。**编辑仅改 value，改 key 走 DELETE + POST**（C-03/§7.2）。`doc_id` 双匹配校验 `is_user_manageable_doc_id`（type + user_suffix），**两组互不互通**（P3）。
  - **`user-memories`（type=`user`）**：
    - **GET** `/users/{user_id}/user-memories` — Query `keyword`/`page`/`page_size`；`data`：`{ total, page, page_size, list:[{doc_id, key, value, content, user_id?}] }`；`total`=cap 内条数（`USER_LIST_TOPK=500`，P9）。
    - **POST** `/users/{user_id}/user-memories` — Body `{key, value}`（key 须三层 `XXX-XXX-XXX`）；`data` 为新条目。
    - **PUT** `/users/{user_id}/user-memories/{doc_id:path}` — Body `{value}`（仅改 value，`doc_id` 需 URL encode，服务端 `unquote`）。
    - **DELETE** `/users/{user_id}/user-memories/{doc_id:path}`。
  - **`private-settings`（type=`character_private`）**：路径与字段同上，固定 `expected_type="character_private"`；页内说明「角色对该用户的私有设定，非用户自传事实」（§7.6）。
- **PUT** `/users/{user_id}/status` — Body `{ "action": "ban"|"unban" }`
- **POST** `/users/{user_id}/reset-password` — `data.new_password`
- **管理端页面**：`admin/pages/user-detail.html` 含「账号管理」Tab 与顶栏按钮，对接上述 PUT/POST；逻辑上 `**userData.status === 'banned'`** 与 `**basic.status`** 及用户列表 `list[].status` 一致（见错误码 20012、20013）；展示与操作均基于展平后的 `userData`（见上条）。
- **关联表**：users, **relationship**, conversation_log, memory, agent_message 等
- **状态**：已实现

---

### 模块：向量召回与 Prompt Token 热配置（`/api/admin/configs`，STEP-025）

- **鉴权**：Bearer Admin JWT；GET 角色 **`super_admin` / `ai_trainer` / `observer`**，PUT 仍仅 **`super_admin` / `ai_trainer`**（`ops_admin` / `tech_ops` 等 → **HTTP 403**）。
- **GET** `/vector_retrieval_config` — 成功 `data`：`{ top_k, threshold }`（与 `multi_vector_retrieval_service` 默认 **TopK=3、阈值=0.7** 及库中已发布行合并后的**完整**对象，供管理端表单展示）。**不涵盖**：Step2 **2.5 补充路**触发条件中的 **`SUPPLEMENT_TRIGGER_THRESHOLD=0.75`**（`count<2 OR max_score<0.75`，代码常量 **TD-027**）、补充路固定 **`top_k=3`**（C36）。
- **PUT** `/vector_retrieval_config` — Body：`{ "top_k"?: int, "threshold"?: float }`（均为可选，**至少提供其一**且不得为 `null`；**禁止**多余字段）。语义为 **PATCH**：与当前 `admin_config` 生效 JSON 及上述默认值合并 → **`admin_config_service.publish_config`** → MySQL 新版本 + Redis **`active_config:vector_retrieval_config`**。`top_k` 合法 **1–20**；`threshold` **0.0–1.0**。无任何有效更新字段 → **`20046`**（`ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`）。发布写入 **`admin_operation_log`**（`log_operation`，`module=ai_config`，`action=publish`，`target_description` 含配置键）。
- **GET** `/prompt_token_config` — 成功 `data`：`{ max_total, system, persona, character_knowledge, relationship, memory, emotion, time_activity, recent_chat, user_input }`（与 `prompt_builder` 默认上限及库中已发布行合并后的完整对象；**不含** `user_nickname`，该模块上限固定 **50** 且只读）。若历史库 JSON 含 `user_nickname` 键，**运行时 `_load_token_limits` 忽略**。
- **PUT** `/prompt_token_config` — Body：上列字段均可选，**至少其一**，整数下界 **1**（`max_total`/`system`/… 各自 Pydantic `ge=1`，`max_total` `le=50000`，模块单项 `le=20000`），**禁止**多余字段（**不可**提交 `user_nickname`）。PATCH 合并后整包发布，Redis **`active_config:prompt_token_config`**。
- **`build_filter(memory_type, user_id, candidate_keys)`**（`backend/utils/dashvector_client.py`）：统一构造 DashVector filter——`type = "{memory_type}"`（双引号）；可选 `AND user_id = {id}`；`candidate_keys` 每项按 `-` 拆分，**段数≥2** 时取前两段拼 **`key_l2 IN (...)`**（值内 `"` 转义为 `\"`），单层 Key 丢弃；**`search()`** 默认 `candidate_keys=[]` 内部调用；**`character_knowledge_service.list_entries`** 使用 `build_filter(mt, None, [])`。单测 **`tests/test_dashvector_client.py`**。
- **错误与 HTTP**：请求体非 JSON 或无法解析为对象 → **HTTP 422**；字段类型/范围违反 Pydantic → **422**；业务侧「空 PATCH」或合并后校验失败 → **信封 `code=20046`**（`message` 可含具体原因）。
- **关联表**：`admin_config`（`config_key` 分别为 `vector_retrieval_config`、`prompt_token_config`）；**Redis**：`active_config:{config_key}`，以及发布流程中的 `publish_monitor:{config_key}`（与既有 `AdminConfigService.publish_config` 一致）。
- **运行时消费**：Step2 `execute_multi_vector_retrieval` 与 `PromptBuilder._load_token_limits` 仍通过 `admin_config_service.get_active_config` 读取（见 STEP-020 / STEP-021 契约摘要）；本模块仅提供管理端读写入口。
- **管理端页面**：`admin/pages/vector-token-config.html` — Tab「向量召回」「Prompt Token」；`admin-api.js` 菜单键 **`vector-token`**（`super_admin` 与 `ai_trainer` 的 `MENU_CONFIG`）；保存时脚本对比首屏快照，**仅提交有变化的字段**以契合 PATCH 语义。
- **状态**：已实现

---

### 模块：角色知识库（`/api/admin/character-knowledge`，STEP-027 / R-L1L3-20）

- **鉴权**：Bearer Admin JWT；GET 角色 **`super_admin` / `ai_trainer` / `observer`**，POST/PUT/DELETE 仍仅 **`super_admin` / `ai_trainer`**（其余 → **HTTP 403**）。
- **存储**：**仅 DashVector**（无 `admin_config`、无 MySQL 镜像表）；与 Step6 `upsert_step6_vectors` 共用 **`doc_id`** 与 **`fields.content`** 约定。
- **doc_id 格式**：`{memory_type}_{sha256(key)[:12]}_{user_suffix}`（DashVector 合法字符；`user_suffix` 角色级为 **`0`**，用户级为 **`user_id`**，如 `character_global_a3f8c2e91b04_0`）。**不再**使用冒号分隔的旧格式。
- **key 格式**：强制三层 **`XXX-XXX-XXX`**（恰好两段半角 `-`）；非法 key（含两层 `外貌-体态`、无连字符 `真实姓名`）在 Step6 写入与后台 POST 时**拒绝/丢弃**。
- **Embedding**：新增/改 **value** 时对 **value 文本** 调用 `embedding_service.get_embedding`（与 Step6 一致，非整行 `key：value`）。
- **fields**：`content` = `key` + 全角冒号 `：` + `value`；**`stable_key`** = key 原文（供列表展示与 keyword 匹配）；**`key_l1`**（一级 Key，如 `外貌`）与 **`key_l2`**（二级 Key，如 `外貌-体态`，供 Step2 主路 `key_l2 IN` 结构化过滤）由写入路径补齐（Step6 `upsert_step6_vectors` 与 Admin `_build_knowledge_fields` 共用，四类均写，C9/C15，见「2026-05-30 摘要」）；`type` 由 `dashvector_client.upsert` 合并写入；`user_id` 仅 `character_private` / `user`（Step6 自动写入，后台不可管）。
- **DashVector upsert**：HTTP 2xx 后若响应 `message` 含 `failed operation` / `is invalid` 视为失败（避免 doc_id 非法时误报成功）。
- **GET** `/character-knowledge` — Query：`type`（可选，`character_global` | `character_knowledge`）、`keyword`（可选，子串匹配 key 或 value）、`page`（默认 1）、`page_size`（1–100，默认 20）。成功 `data`：`{ total, page, page_size, list }`；`list[]`：`doc_id`, `type`, `key`, `value`, `content`。列表含 **Step6 自动写入** 的同 type 条目；每类 filter 查询 `topk=500` 后内存分页与 keyword 过滤（条目极多时最多展示约 500/类）。
- **POST** `/character-knowledge` — Body：`{ "type", "key", "value" }`（均必填）。`type` 仅两枚举；**`key` 须三层 `XXX-XXX-XXX`**，CJK 计数 ≤20，每段允许汉字/数字/英文/`-`/`_`，禁止全角 `：`；`value` CJK ≤100。同 `type+key`（hash 相同）已存在 → **`20050`**。Embedding 空或 upsert 失败 → **`20052`**。成功 `data` 为单条对象（字段同 `list[]`）。
- **PUT** `/character-knowledge/{doc_id}` — 路径参数须 **URL 编码**；**key 不可改**，Body 仅 `{ "value" }`。`doc_id` 须为可管理的角色级条目（`character_global` / `character_knowledge` 且 `_0` 后缀），禁止操作 `character_private` / `user`。不存在 → **`20051`**；校验/向量失败码同 POST。
- **DELETE** `/character-knowledge/{doc_id}` — 同上路径规则；成功 `data`：`{ "doc_id" }`。
- **审计**：POST/PUT/DELETE 写入 `admin_operation_log`（`module=character_knowledge`，`action` 为 `create` / `update` / `delete`）。
- **DashVector 客户端扩展**：`list_by_filter(filter, topk)`（仅 filter 查询）、`fetch_by_ids(ids)`（按 id 拉取）。
- **管理端页面**：`admin/pages/knowledge.html` — 顶栏「角色知识库」；`activeKey=knowledge`；内嵌 **demo 格式提示**；类型筛选 + 关键词；表格 CRUD；编辑态 **key/type 只读**；菜单 `admin-api.js` **`📚 角色知识库`**（`super_admin` / `ai_trainer`）。
- **不在范围**：`character_private` 维护、批量导入。
- **状态**：已实现

---

### 模块：人格 / 情绪 / 世界观 / Prompt / 安全 / 测试用例

- **人格**：`GET/PUT/DELETE /persona/draft`，`GET /persona/current`，`POST /persona/test|publish`，`GET /persona/history`，`GET /persona/history/{version}`，`POST /persona/rollback` — Body 见 `persona.py` 内联模型
- **GET /api/admin/persona/history/{version}**：鉴权与角色同其他人格接口（`super_admin` / `ai_trainer`）。成功 `data`：`version`, `is_active`, `updated_by`, `updated_at`, `content`（JSON 解析后的对象，解析失败时为原始字符串）。版本不存在 → `20023`（`ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND`），`message` 为「版本 V{n} 不存在」。
- **POST /api/admin/persona/test** 成功 `data`（`admin_config_service.run_standard_tests`）：`total`, `passed`, `failed`, `pass_rate`, `can_publish`, `details`（数组），可选 `message`（如无测试用例等）。`details[]` 含 `case_id`, `input`, `ai_reply`, `total_score`, `level`, `style_score`, `boundary_score`, `emotion_score`, `violations`, **`passed`**（布尔，与该条是否计入通过一致，供管理端展示 Tag）。
- **情绪**：`GET /emotion-config`；`PUT /emotion-config/{emotion_name}` — `EmotionUpdateRequest`
- **世界观**：`GET|PUT /world-state/config`；`GET /world-state/history`
- **Prompt**（实现见 `backend/routers/admin/prompt_mgmt.py`；鉴权均为 **`super_admin` / `ai_trainer`**）：
  - **废弃说明**：旧版 **`prompt_modules`**（七模块）相关接口 **`GET /prompt/modules`、`PUT /prompt/draft/{module_name}`、`DELETE /prompt/draft`（旧）、`POST /prompt/publish`（旧）、`GET /prompt/history`（旧）、`POST /prompt/rollback`（旧）** 已移除；库内若仍存在 `config_key=prompt_modules` 的历史行可运维手工删除，**运行时不再读取**。
  - **运行时配置键**：**`step5_system_prompt`** — Step5 模块1 System（JSON `{"content": string}`）；**`step5_5_prompt_fragments`** — Step5.5 六段（JSON 对象，键：`system`、`style_rules`、`ctx_readonly`、`relation_brief`、`history_brief`、`messages_input`，占位符与发布校验见服务端）；**`step5_5_enabled`** — 总开关（与 STEP-009 一致）。
  - **Step5 System**：`GET /api/admin/prompt/step5`（`data`：`version`、`has_draft`、`content`、`baseline_is_builtin`）；`GET /api/admin/prompt/step5/draft`；`PUT /api/admin/prompt/step5/draft` Body `{ "content": string }`；`DELETE /api/admin/prompt/step5/draft`；`POST /api/admin/prompt/step5/publish` Body `confirm_text`、`test_passed`（发布前校验 Step5 JSON 契约字段名子串：`inner_monologue`、`messages`、`relation_change`、`future`、`emotion`、`knowledge_expand`）；`GET /api/admin/prompt/step5/history`、`GET /api/admin/prompt/step5/history/{version}`、`POST /api/admin/prompt/step5/rollback`。
  - **Step5.5 六段**：`GET /api/admin/prompt/step5-5/fragments`（`data.fragments`、`fragment_keys`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5/draft`；`PUT /api/admin/prompt/step5-5/draft/{fragment_key}` Body `{ "content": string }`（`fragment_key` 限于六键）；`DELETE /api/admin/prompt/step5-5/draft`；`POST /api/admin/prompt/step5-5/publish`（占位符与 system 段契约关键词校验）；`GET /api/admin/prompt/step5-5/history`、`GET .../history/{version}`、`POST .../rollback`。
  - **Step5.5 总开关**：`GET /api/admin/prompt/step5-5-switch`（`enabled`、`draft_enabled`、`version`、`has_draft`）；`GET /api/admin/prompt/step5-5-switch/draft`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ "enabled": bool }`；`DELETE .../draft`；`POST .../publish` Body `confirm_text: CONFIRM`（**不要求**先跑主链 LLM 在线测试；可与 `test_passed` 一并提交）；`GET .../history`、`POST .../rollback`。
  - **在线测试**：`POST /api/admin/prompt/test` — Body：`test_input`（必填）、`relationship_level`（0–3）、`emotion_label`、`mock_memories`（字符串数组）、`use_draft`（bool，为 `true` 时用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致，LLM **`chat_with_step5_parse(..., is_test=true)`**；成功 `data`：`full_prompt`、`ai_reply`（`messages[].content` 合并）、`persona_match`、`content_safety`、`token_estimate`。
- **对话流 Prompt 只读展示**（实现见 `backend/routers/admin/chat_prompt_view.py` + `backend/services/chat_prompt_view_service.py`；鉴权 **`super_admin` / `ai_trainer`**；**无**草稿/发布/写库）：
  - **GET** `/api/admin/chat-prompt-view/step15` — Step1.5 查询重写模板；`data`：`readonly`、`title`、`description`、`source_file`、`variants[]`（`key=main|step8`，`content` 为占位符拼装全文，与 `_build_step1_5_prompt` 同源）。
  - **GET** `/api/admin/chat-prompt-view/step3` — Step3 拼装规则；`data`：`module_order`、`trim_priority`、`empathy_rules`、`emotion_mapping`、`level_definitions`、`silence_corrections`（与 `prompt_builder` 常量同源）。
  - **GET** `/api/admin/chat-prompt-view/step8` — Step8【主动发起】模板；`data.proactive_input_template` = `STEP8_PROACTIVE_INPUT_TEMPLATE`（含 `{{future_action}}`）。
  - **GET** `/api/admin/chat-prompt-view/agent` — Agent P0～P4 任务指令；`data.triggers[]`（`key`/`task_instruction`/`full_task_block`）与 `ACTIVE_TRIGGER_INSTRUCTIONS` + `AGENT_TASK_OUTPUT_SUFFIX` 一致。
  - **页面**：`chat-prompt-step15.html` / `chat-prompt-step3.html` / `chat-prompt-step8.html` / `chat-prompt-agent.html`；侧栏 `CHAT_PROMPT_MENU`（见管理端页面节）。
- **安全**（`backend/routers/admin/safety_rules.py`，前缀 `/api/admin`）：
  - **GET** `/safety-rules` — 成功 `data`：`banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords`（均为 `string[]`，无生效配置时为空数组）。
  - **PUT** `/safety-rules/banned-keywords` — Body：`{ "keywords": string[] }`（Pydantic `KeywordsUpdateRequest`：**`keywords` 至少 1 个元素**）。
  - **PUT** `/safety-rules/persona-keywords` — 同上。
  - **PUT** `/safety-rules/style-keywords` — 同上。
  - **POST** `/safety-rules/banned-keywords/import` — `multipart/form-data`，字段名 **`file`**（`.xlsx` / `.xls`）；与现有违禁词合并去重后发布。成功 `data`：`imported_count`（本次从表格读取到的非空行数）、`total_count`（合并去重后的词库总数）。
- **测试用例**：`GET|POST /test-cases/{config_key}`；`DELETE /test-cases/{config_key}/{case_id}`。**POST Body**（`TestCaseCreateRequest`）：`input`（必填）、`expected_pass_criteria`（必填）、`emotion_label`（默认 `平静`）、`relationship_level`（默认 `1`，0–3）。成功 `data`：`case`、`total_count`，并与 `publish_config` 成功回执字段合并返回。
- **响应**：`ApiResponse`
- **关联表**：admin_config（及部分 Redis）
- **状态**：已实现

---

### 模块：记忆与向量（管理）

> **长记忆第一套下线（PRD v1.3）**：旧 **`GET/PUT /memory-rules`** 已删除（C-02/C-08：`memory_rules` 后台不展示、不提供 API，历史配置行仅保留库内不读取）；改为 **`GET/PUT /step6-memory-prompt`**。`memories/global` 改向量检索、`batch-delete` 改按 `doc_ids`。本系列权限 **`super_admin` / `ai_trainer`**（P5）。运行时**不过滤 `mem_*`**（P1）。
- **GET** `/step6-memory-prompt` — 成功 `data` 为当前生效 Step6 记忆 Prompt 6 块结构；**无生效配置时返回 DEFAULT**（`STEP6_PROMPT_DEFAULT`，逐字复刻旧硬编码，P6）。6 块：`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields`（dict，**恰好 11 项**，key/顺序同 `_ALL_FIELD_NAMES`）/ `merge_rules` / `few_shot_example`。
- **PUT** `/step6-memory-prompt` — Body `Step6MemoryPromptRequest`（6 块）：5 个文本块非空 + `task_fields` 恰含 11 个 key 且各项非空（C-10 Pydantic 必填校验，不做 persona 测试集 / CONFIRM 门禁）；**保存即发布**（`publish_config` 更新 MySQL+Redis `active_config:step6_memory_prompt`，~100ms，免重启），写 `admin_operation_log`。运行时由 `memory_llm_service.build_step6_prompt`（已 `async`）三级回退 Redis→DB→DEFAULT 读取；动态注入区块（时间/人格/关系/历史/本轮对话）**不可配置覆盖**。
- **GET** `/vector-db-config` — 成功 `data`：`endpoint`、`collection_name`、`top_k`、**`api_key_masked`**（脱敏，不含明文 `api_key`）；无 DB 配置时回退读环境变量并同样返回 `api_key_masked`。
- **PUT** `/vector-db-config` — Body `VectorDbConfigRequest`：`endpoint`、`collection_name`、`top_k`（Pydantic 默认 5，**无 1–20 上限校验**）；`api_key` 可选（不传则保留库内原值）；`need_test_first`（bool，**为 `true` 时保存前会先测连**，失败则拒绝保存）。管理页保存可传 `need_test_first:false`，依赖前端「先测后存」。
- **POST** `/vector-db-config/test-connection` — Body `VectorDbTestRequest`（字段均可选）：`endpoint`、`collection_name`、`api_key`；缺省时从已发布配置或环境变量补全。成功 `data`：`connected`（bool）、`latency_ms`、`error`（字符串）。
- **GET** `/memories/global` — 全局用户记忆检索（Step6 user 向量，**仅 type=user，不含 character_private**，§6.4.1）。Query：`keyword`、`user_id`（**可选**）、`page`、`page_size`（**移除** `start_date`/`end_date`/`source`）。有 `user_id` → `top_k=USER_LIST_TOPK=500`（P4）；无 → `top_k=GLOBAL_LIST_TOPK_NO_USER=300`（R-01/P4）。`keyword` 先 `list_by_filter` 再内存子串过滤（key/value/content）后分页。`data`：`{ total, page, page_size, list:[{doc_id, user_id, key, value, content}] }`；**未传 `user_id` 且候选命中上限（==300）时附 `truncated: true`**（R-01）。
- **DELETE** `/memories/batch-delete` — Body `BatchDeleteRequest`：`{ doc_ids: list[str] }`（min 1 / max 100，P8）。逐条校验「以 `user_` 前缀 + `parse_doc_id` 合法」，非法计入 `failed_doc_ids` 不中断；合法项 `dashvector_client.delete` 累加 `deleted_count`；仅删 DashVector（不走 MySQL）；「涉及用户」从 `user_suffix` 聚合写入 `log_operation`（module 仍用 `memory`）。`data`：`{ deleted_count, failed_doc_ids }`。
- **状态**：已实现（长记忆第一套下线改造）

---

### 模块：Agent 管理

#### GET /api/admin/agent-night-keywords

- **所属端**：管理后台
- **鉴权**：Bearer Admin JWT（角色同 PUT：`super_admin` / `ai_trainer`）
- **响应**：`ApiResponse`；`data` 与 **PUT** Body 一致：`{ "keywords": string[] }`（无生效配置时 `keywords` 为空数组 `[]`）
- **数据来源**：`get_active_config("agent_night_keywords", use_cache=False)`（查 **admin_config** 当前生效行，**不**经 Redis）
- **关联表**：admin_config
- **同模块其它路由**：**GET|PUT** `/agent-rules` — `AgentRulesRequest`；**GET** `/agent-message-rules`（整包）/ **PUT** `/agent-message-rules/{trigger_type}`（单类型）；**PUT** `/agent-night-keywords` — `NightKeywordsRequest`；**GET** `/agent-messages` — Query：`user_id`（可选）、`trigger_type`、`is_read`、`start_date`、`end_date`（见 **`admin_date_filter`**）、`page`、`page_size`（1–100）；鉴权 **`super_admin` / `ops_admin` / `ai_trainer`**；排序 **`created_at` 降序**；成功 `data`：`{ total, page, page_size, list[] }`；**`list[]`**：`id`, `user_id`, `trigger_type`, `content`, `action_score`, `is_read`, `created_at`
- **状态**：已实现

---

### 模块：关系规则与日记（管理）

- **GET|PUT** `/relationship-rules` — 两阶段 `confirmed` 预览/发布
- **GET|PUT** `/diary-rules` — `DiaryRulesRequest`（见下文字段）；PUT 发布写入 `admin_config`，Redis `active_config:diary_rules`
- **GET** `/diary-history` — Query：`user_id`（可选）、`start_date`、`end_date`（见 **`admin_date_filter`**，按 **`created_at` 过滤，F1**）、`page`、`page_size`（1–100）；鉴权 **`super_admin` / `ops_admin`**；成功 `data`：`{ total, page, page_size, list:[{ id, user_id, username, content, relationship_level_at_creation, is_read, created_at, covers_beijing_date }] }`（**`username`** 来自 `users.username`）。列表查询与 **`GET /users/{user_id}/diaries`** 共用 **`fetch_admin_diary_list_page`**，在相同 **`user_id` + 日期 + 分页** 下结果一致；排序 **`created_at` 降序**。
- **状态**：已实现

**`DiaryRulesRequest`（PUT `/diary-rules` Body）**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `max_length` | int | 是 | 50–300 |
| `frequency` | str | 否 | 默认 `daily` |
| `generation_hour` | int | 是 | **0–23**（**北京时间**，与 APScheduler **`Asia/Shanghai`** Cron 一致） |
| `generation_minute` | int | 否 | 0–59，默认 **15**（代码回退默认与 `diary_rules_loader` 一致） |
| `prompt_with_interaction` | str | 条件 | 与 `prompt_without_interaction` **同时非空**时生效 |
| `prompt_without_interaction` | str | 条件 | 同上 |
| `generation_prompt` | str | 条件 | **兼容旧版**：非空时等价于两套 Prompt 使用同一文本（服务端同时写入双字段与 `generation_prompt` 键） |

三者至少满足：**双 Prompt 同时填写** 或 **仅 `generation_prompt`**，否则 `ADMIN_ERR_DIARY_RULE_PARAM_INVALID`。

---

### 模块：数据统计（`/api/admin/stats`）

- **GET** `/stats/dashboard` — `**ApiResponse`**，所有登录管理员可访问；`data` 为**嵌套对象**（按角色裁剪）：
  - `super_admin` / `ops_admin` / `observer`：`user`（`new_users_today` 等）、`retention`（`next_day_retention` / `day7_retention` / `day30_retention`，可 `null`）、`conversation`、`agent`、`ai_performance`
  - `ai_trainer`：仅 `ai_performance`
  - `tech_ops`：空对象 `{}`
  - `ai_performance.llm_avg_response_ms`：**无 Redis 响应时间样本时为 `null`**（与真实平均 **0** ms 区分）；`llm_success_rate` 可 `null`
  - **人格偏离率**（`persona_deviation_rate`）：当日 `persona_risk_flag=true` 条数 / 当日 **`role=assistant`** 的 `conversation_log` 条数 × 100%（与 `stats_service._get_ai_performance_data` 一致）
- **GET** `/stats/trend` — Query `metric`, `days`；`data` 为 **`[{ date, value }, ...]`** 数组（非 `dates`/`values` 对象）；需 `super_admin` / `ops_admin` / `observer`
- **GET** `/stats/report` — Query report_type, start_date, end_date, page, page_size；`data`: `{ list, total, page, page_size, extra }`
- **GET** `/stats/liblib` — Query `days`（1~30）；LiblibAI 日统计（见「管理后台 · 生活流」）
- **POST** `/stats/report/export` — Query 同报表条件，Excel 流；`ai_performance` 导出列第三表头为 **「AI回复数」**（对应 `total_count`，assistant 条数）
- **说明**：`report_type=user` 时 `extra.level_distribution` 按 `**relationship.level`** 统计（无行用户计入 level 0），与后台用户列表关系字段数据源一致；**该分布为当前全量用户快照，不随 `start_date`/`end_date` 过滤**（与 `list[]` 按日明细不同）。
- **状态**：已实现

---


### 模块：管理后台 · 生活流（`/api/admin`）

> 前缀 `/api/admin`；Admin JWT；写操作落 `operation_log`；配置类写操作走草稿三卡点。路由：`life_plan_mgmt` / `worldview_mgmt` / `feed_mgmt` / `feed_comment_mgmt` / `agent_aware_mgmt` / `life_config_mgmt`。

#### 生活计划（`life_plan_mgmt`）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/life-plan/outline` | 编辑 + ops 只读 | `week_start_date` 或 `plan_date` |
| POST/PUT/DELETE | `/life-plan/outline...` | 编辑 | categories∈词汇表；同日已存在报错 |
| POST | `/life-plan/outline/generate` | 编辑 | LLM-01 手动生成本周剩余日 |
| GET/PUT | `/life-plan/settings` | GET 含 ops；PUT 编辑 | home_city + life_ratio_*；PUT **仅草稿**，发布走 `/life-config/publish` |
| GET | `/life-plan/daily` | 编辑 + ops | 单日或 `start&end&page&size` |
| POST | `/life-plan/daily/{plan_date}/generate` | 编辑 | LLM-02 |
| POST/PUT/DELETE | `/life-plan/daily/{plan_date}/scenes...` | 编辑 | category 必须∈当日大纲；scenes&lt;2 不主动降级 gen_status |

#### 她的宇宙（`worldview_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/worldview/snapshots` | 仅 `plan_date`→数组；无参或 start/end→分页 `{total,page,size,list}`（默认近 14 天） |
| GET/PUT/DELETE | `/worldview/snapshots/{id}` | 删被 feed 引用时 WARN，可含 `referenced_by_post` |
| GET/POST/PUT/DELETE | `/worldview/events...` | `core_attitude` 四选项以前缀写入 `event_view` |

#### 朋友圈内容（`feed_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed/posts` | status∈all/visible/hidden/failed |
| GET/PUT | `/feed/posts/{id}` | 详情含 image_urls/hashtags/dedup_hash；**另含** base_comments/comment_multiplier/虚拟评论底 |
| DELETE | `/feed/posts/{id}` | **现状=下架**（`is_visible=0`）；真删未实现（TD-035）；UI 不提供删除钮 |
| PATCH | `/feed/posts/{id}/visibility` | `{is_visible:0/1}` |
| POST | `/feed/posts` | mode∈upload/ai_generate；管理员跳过 dedup/similarity；新帖随机写评论假数底 |
| GET/PUT | `/feed/config/auto-publish` | **不含** ops_admin；写入口在系统参数页 |

#### 评论管理（`feed_comment_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed/comments` | 筛 post_id/user_id/gen_status（含 hidden） |
| GET/PUT/DELETE | `/feed/comments/{id}` | DELETE=`is_hidden=1` |
| POST | `/feed/comments/{id}/regenerate` | LLM-05 补发，立即 queued |

#### 感知消息（`agent_aware_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/agent-aware` | queue LEFT JOIN agent_message |
| GET | `/agent-aware/{queue_id}` | 含 extra_context |
| POST | `/agent-aware/{queue_id}/retry` | 重试 failed |
| DELETE | `/agent-aware/{queue_id}` | 不撤回已送达 IM |
| POST | `/users/{user_id}/aware/reset` | **仅 super_admin**；特殊档计数归零 |

#### 生活流配置（`life_config_mgmt`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/life-config?keys=` | 生效值+草稿；白名单校验；ops/tech 只读 |
| PUT | `/life-config/draft` | 保存草稿 |
| DELETE | `/life-config/draft/{config_key}` | 丢弃草稿 |
| POST | `/life-config/publish` | Body 增加可缺省的 `confirm_text`；进入发布前必须精确等于 `CONFIRM`，否则返回 `20021`；发布 + Redis + 5min 监控 |

`confirm_text` 不替代既有角色鉴权，也不是二次认证。现有 7 个前端发布入口均在共享 `showConfirmInput` 回调内显式发送 `confirm_text: "CONFIRM"`；取消或错误文本不会调用发布接口。草稿、生效版本、历史、回滚、Redis 发布流程与数据库结构保持不变。

**白名单**：`life_feed_config` 全部 `CONFIG_*` + life_ratio_* + 四档延迟键（`comment_reply_delay_*` / `like_regular_delay_*` / `read_regular_delay_*`，stage∈stranger/friend/intimate/**soulmate**）+ Prompt/图像映射 + DeepSeek 节点模型键。

#### GET /api/admin/stats/liblib

- Query `days`（1~30，默认 7）；读 Redis `liblib_stats:{YYYYMMDD}`
- 权限：super_admin / ai_trainer / tech_ops
- `data`：`{ days, daily:[{date,total,success,failed,points_used}], summary }`；Redis 异常可 `redis_error:true`

#### RBAC（生活流）

| 角色 | 权限 |
|------|------|
| super_admin | 全部读写；唯一可 reset 特殊档 |
| ai_trainer | 全部读写 |
| ops_admin | **只读**：朋友圈内容/评论/感知/生活计划/她的宇宙；可读 life-config；**不可** auto-publish |
| tech_ops | **只读**：系统参数 + Liblib 看板 |
| observer | 全部已批准生活流 GET 只读；不可草稿、发布、回滚、生成、增删改、显隐、重试或重置 |

---

### 模块：系统监控与第三方（`/api/admin`）

- **GET** `/system/status`；**GET** `/third-party/status` — `ApiResponse`
- **PUT** `/third-party/{service_name}/config` — Body 自由 dict；保存前服务端用「已发布配置 ∪ Body」合并后做连通性测试（失败则 `ApiResponse.fail` code=5001，不落库）
- **POST** `/third-party/{service_name}/test-connection` — 可选 **JSON Body**（字段与 PUT 一致片段即可，如 `endpoint`、`api_key`）；服务端将 Body 与**当前已发布** `admin_config` 中对应 `third_party:*` 配置 **合并** 后调用与 PUT 相同的探测逻辑；无 Body 或 `{}` 时等价于仅用已发布配置 + 各探测函数内对环境变量的回退
- **GET** `/system/logs` — Query：`log_type`（`system` \| `error`，对应 `_LOG_TYPE_FILE_MAP`）、可选 `level`、可选 `start_date`/`end_date`（缺省为近 7 天）、`page`/`page_size`；成功 `data`：`{ total, page, page_size, list:[{ time, level, module, message }] }`（**`list` 按日志时间 `time` 降序，最新在前**）；**POST** `/system/logs/export` — Query 条件同上、**无 Body**；成功为 **xlsx 流**（非 JSON 信封）；范围校验失败 HTTP 400；**查询**区间 `(end-start).days > 30`、**导出** `> 7` 被拒绝（与 `system_monitor.py` 一致）；导出文件内行顺序与列表查询一致（同条件下按 `time` 降序）
- **凭据脱敏**：系统日志列表分页结果与 Excel 导出行在返回前统一调用共享凭据脱敏工具；所有获准角色获得一致结果。单条消息处理异常时失败关闭为 `[REDACTED]`，时间、级别、模块、收集、筛选、排序和日期范围不变。
- **说明**：`system_monitor.py` 末尾有 `# TODO: 后续接口`
- **状态**：已实现（除标注 TODO 部分）

---

## 管理端页面

### `admin/pages/system-monitor.html`（系统监控）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 仅可读取系统状态。
- **接口**：`GET /api/admin/system/status`（**10 秒缓存**，后端 Redis key `cache:system_status`，已处理）；请求使用 `admin-api.js` 的 **`adminRequest`**，无单独封装函数。
- **响应 `data` 结构**：`cpu:{ percent, cores }`；`memory:{ percent, total_gb, used_gb }`；`disk:{ percent, total_gb, used_gb }`；`redis:{ hit_rate, used_memory, connected_clients }`；`alerts:[{ level:'warning'|'critical', message }]`.
- **展示约定**：四张指标卡为 **纯 SVG 环形进度**（`stroke-dasharray` 控制弧长，周长按 \(2\pi\times34\)）；**Redis 命中率**色阶与 CPU/内存/磁盘相反（高为好）。Redis 卡副文案按产品与需求仅展示 **「已用内存：{used_memory}」**（`connected_clients` 由接口提供但本页不展示）。
- **CPU 趋势**：ECharts 折线，内存数组最多 **60** 点，与前端 **每 10 秒** 拉取一次对齐，覆盖约 **近 10 分钟**；标题为「近10分钟 CPU 趋势」，**不写「近1小时」**。
- **告警列表**：接口无单条时间字段时，各行左侧时间为 **本次刷新时刻**；若未来扩展字段见 **`docs/tech-debt.md` [TD-010]**。
- **生命周期**：`beforeunload` 时 `clearInterval` 释放定时器；`resize` 时 `cpuChart.resize()`。

### `admin/pages/system-logs.html`（系统日志）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 可读脱敏列表，不可导出。
- **Tab**：仅 2 个（`system` / `error`），无第三方服务日志 Tab；`activeKey='system-logs'`，顶栏标题「系统日志」。
- **调用**：`GET /api/admin/system/logs`
  - `log_type` 枚举：`system` \| `error`（对应后端 `_LOG_TYPE_FILE_MAP` → `system.log` / `error.log`）。
  - 日期参数：`YYYY-MM-DD`（`type="date"` 原生值，与后端 `datetime.date` 一致）。
  - 单次查询区间：后端拒绝 `(end_date - start_date).days > 30`；前端前置校验一致。
- **导出**：`POST /api/admin/system/logs/export`（仅 Query，无 Body）；`adminRequest('POST', url)` **不传 `data`** 以走 `admin-api.js` 的 blob/xlsx 下载分支。
  - 单次导出：后端拒绝区间 `days > 7`；前端前置校验与后端一致（避免前后端口径不一）。
- **状态**：`system` / `error` 各自维护 `pageState`（含 `hasQueried`：仅在该 Tab **从未成功请求过列表**时，切换 Tab 自动触发首次 `queryLogs`；**已加载但 0 条**不重复自动请求）；`page_size=50`；分页使用 `admin-api.js` 的 **`renderPagination`**，第四参须为全局回调名字符串 **`window.systemLogsGoPage_system`**（system Tab）或 **`window.systemLogsGoPage_error`**（error Tab），**禁止**传入匿名函数（`renderPagination` 将回调拼入 `onclick`，匿名函数经 `toString` 会丢失闭包，导致翻页无效）。
- **安全**：列表中 `row.message` 经 **`escapeHtml`** 再写入 `innerHTML`；错误详情弹窗用 **`textContent`** 写入正文，防 XSS；`ERROR` 行「详情」按钮传参使用 `JSON.stringify` + `</` → `\u003c/` 及属性内 `&quot;` 转义，避免引号截断属性。

### `admin/pages/third-party.html`（第三方服务监控）

- **权限**：`super_admin` / `tech_ops` / `observer`；observer 仅读状态与非敏感配置，凭据仅显示已/未配置，不可保存或测试连接。
- **调用**：`GET /api/admin/third-party/status`（**60 秒缓存**，后端 Redis key `cache:third_party_status`，已处理）；定时 **60s** 刷新；`beforeunload` 时 `clearInterval` 防泄漏。
- **卡片**：`#service-grid` 为 2×2 栅格；首屏 4 个 `.skeleton`（高 200px）；成功后渲染服务卡。**标题**使用接口返回的 `name`（不硬编码展示文案）；`svcKey` 由前端 `SERVICE_KEY_MAP` 与后端 `_VALID_SERVICES` 路径对齐（`doubao` / `embedding` / `dashvector` / `content_safety`）。
- **内容安全卡**：独立布局，仅 `today_blocked` + 状态灯；代码注释 **TD-003**（与全局 `tech-debt.md` 中 [TD-003] 编号不同指代）：无真实第三方 HTTP 后端，探测为 Redis `banned_keywords`；配置弹窗为说明 +「测试 Redis 连通性」+「关闭」，无保存。
- **配置弹窗（非 content_safety）**：Endpoint（`type=url`）、API Key（留空保留原值）；**保存**初始禁用；**测试连接** 发 `POST .../test-connection`，Body 含表单中**非空**的 `endpoint` / `api_key`（可与已发布配置合并探测）；`connected===true` 后启用保存。**保存**：`PUT .../config`，Body 仅传非空字段；`api_key` 空则不传；须本弹窗内测试通过后才提交（前端校验）；服务端仍会再次测试合并结果。
- **技术债记录**
  - **TD-003（本页注释口径）**：内容安全无独立第三方 API，探测走 Redis；若未来接入真实内容安全服务需后端字段与探测实现。
  - **TD-012**：`third_party:*` 已可落库与热键 `active_config:third_party:*`，**对话/向量/Embedding 等业务运行时仍以环境变量等现有路径为准**，与后台保存易不一致；清偿时见 `docs/tech-debt.md` [TD-012]。

### `admin/pages/dashboard.html`（数据看板）

- **实现状态**：已实现。`activeKey='dashboard'`，顶栏标题「数据看板」。`observer` 仅读并与 `super_admin` / `ops_admin` 一样获得完整看板数据；`tech_ops` 仅提示文案无统计卡片；`ai_trainer` 仅展示 LLM 成功率、人格偏离率等 AI 性能卡片。
- **接口**：`GET /api/admin/stats/dashboard` 的 `data` 为**嵌套对象**（见上文「模块：数据统计」）；卡片脚本内 **`flattenDashboard`** 将 `user` / `retention` / `agent` / `ai_performance` 展平为卡片字段（如 `new_users_today`→`new_users`、`persona_deviation_rate`→`persona_risk_rate`）。
- **趋势图**：`GET /api/admin/stats/trend?metric=...&days=7` 的 `data` 为 **`[{ date, value }]`**；脚本 **`trendListToAxes`** 拆出 `dates`/`values` 再喂 ECharts。
- **告警**：人格偏离 / LLM 成功率 / 次日留存 等阈值判断使用 **`typeof === 'number'`**，避免将 `null` 当 0。

### `admin/pages/persona.html`（AI人格管理）

- **实现状态**：已实现。布局左 55% 编辑区、右 45% 版本历史；`activeKey='persona'`，标题「AI人格管理」。`super_admin` / `ai_trainer` 可编辑，`observer` 仅读人格、历史和版本内容。
- **接口对接**：
  - `GET /api/admin/persona/current`：状态栏「当前生效版本 / 暂无生效版本」、`has_draft` 驱动右侧「有未发布的草稿」+「丢弃草稿」（`DELETE /api/admin/persona/draft`，`showConfirm`）或「已发布」。
  - `GET /api/admin/persona/draft`：有草稿则用 `data.config_value` 五字段填充编辑区；无草稿则用 `current.content`；并行加载时编辑区骨架屏，三请求完成后渲染。**数据库**：若 `admin_config` 对 `config_key` 误设 UNIQUE，保存草稿会 500（MySQL 1062），见表结构「admin_config」与迁移脚本 `migrate_admin_config_config_key_nonunique.sql`。
  - **首屏容错（仅前端，非接口变更）**：若 `GET .../current` 失败（网络/非 0 等）而 `GET .../draft` 成功且 `data` 非空，使用内存占位对象仅设置 `has_draft: true`，使右侧仍显示「有未发布的草稿」与「丢弃草稿」；左侧内容仍以 `draft.config_value` 为准；生效版本文案仍以 `current` 成功后的响应为准。
  - **对称边界**：若 `current` 成功且 `data.has_draft===true`，但 `GET .../draft` 未成功取到草稿体，编辑区会回退为 `current.content`（生效版本），并 Toast 警告「草稿未能加载…请刷新」，避免与状态栏「有草稿」静默不一致。
  - **测试与发布**：每次点击「测试效果」时先将 `testPassed` 置 `false`；请求失败或非 0 时保持 `false`，避免上次「测试通过」在 422/网络错误后仍可点「发布生效」。
  - `PUT /api/admin/persona/draft`：「保存草稿」；成功后 `savedSnapshot` 对齐、Toast、调用 `GET .../current` 刷新状态栏（`adminRequest` 使用 `silentErrorToast: true` 避免与后续文案重复）；若刷新失败则再 `showToast(..., 'warning')` 提示手动刷新页面。
  - `POST /api/admin/persona/test`：「测试效果」弹窗内 loading → 渲染 `details` 列表（输入、回复、得分进度条、`passed` 对应通过/失败 Tag）、底部 `passed/total` 总结；`can_publish===true` 时 `.alert-success` 与 **`testPassed=true`**；否则 `.alert-error` 且 **`testPassed=false`**。
  - `POST /api/admin/persona/publish`：`testPassed=false` 时「发布生效」禁用；`showConfirmInput` 后 Body 含 `content`、`test_passed:true`、`confirm_text:'CONFIRM'`。
  - `GET /api/admin/persona/history` + `renderPagination`（`page_size=10`）：时间线列表「查看 / 回滚」。
  - `GET /api/admin/persona/history/{version}`：「查看」只读弹窗完整五段（历史列表仅 `summary` 截断，不足以展示全文）。
  - `POST /api/admin/persona/rollback`：`showConfirmInput` + `confirm_text:'CONFIRM'`。
- **testPassed 联动**：初始 `false`，发布钮禁用。仅当最近一次「测试效果」请求成功且响应 `can_publish===true` 时置 `true`。各 textarea `input` 时置 `false`（内容变更须重测）。关闭测试弹窗仅重置 loading/结果区 DOM，**不**重置 `testPassed`。
- **未保存提示**：`savedSnapshot` 为 JSON 序列化的五字段（与加载源：草稿优先于生效内容一致）；`oninput` 与快照比较，差异则显示 `.alert.alert-warning`「有未保存的修改」。

### `admin/pages/prompt.html`（Prompt 管理 · Step5 / Step5.5）

- **实现状态**：已实现（STEP-026；2026-07-13 侧栏收入「对话流 Prompt」）。Query **`?tab=step5`**（默认）| **`?tab=step55`** 控制首屏主 Tab 与侧栏高亮（`cp-step5` / `cp-step55`）。顶栏标题随 Tab：「Step5 主对话」/「Step5.5 润色」。`super_admin` / `ai_trainer` 可编辑，`observer` 可读但不可草稿、测试、发布、回滚或删除。
- **主 Tab**：**Step5 System**（整段 `textarea`，对应 `GET|PUT /api/admin/prompt/step5/draft`，配置键 **`step5_system_prompt`**）| **Step5.5 片段**（六个子 Tab：`system`、`style_rules`、`ctx_readonly`、`relation_brief`、`history_brief`、`messages_input`，对应 `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`）。
- **首屏加载**：`GET /api/admin/prompt/step5`、`GET /api/admin/prompt/step5-5/fragments`；草稿优先：`GET .../step5/draft`、`GET .../step5-5/draft` 与生效内容合并后填入编辑区。
- **保存草稿**：Step5 — `PUT /api/admin/prompt/step5/draft`；Step5.5 — `PUT /api/admin/prompt/step5-5/draft/{fragment_key}`（仅当前子 Tab）。
- **丢弃草稿**：`DELETE /api/admin/prompt/step5/draft`、`DELETE /api/admin/prompt/step5-5/draft`。
- **在线测试**：Modal；`POST /api/admin/prompt/test`，Body 含 `use_draft`（为 `true` 时使用 **`step5_system_prompt`** 草稿覆盖模块1）。服务端 **`PromptBuilder.build_chat_prompt`** 与主链一致；成功展示 `ai_reply`（messages 合并）、人格匹配条、内容安全、`full_prompt` 折叠区。
- **testPassed**：每次「开始测试」前置 `false`；**成功**且 `ai_reply` 去空白非空 → `true`，用于解锁 **发布 Step5** 与 **发布 Step5.5**；编辑任意 textarea / 切换草稿语义变更时应重新测试。
- **发布**：`POST /api/admin/prompt/step5/publish` / `POST /api/admin/prompt/step5-5/publish`，Body `confirm_text:'CONFIRM'`、`test_passed:true`（须先在线测试通过）。
- **版本历史**：两块独立列表 — **`GET /api/admin/prompt/step5/history`** 与 **`GET /api/admin/prompt/step5-5/history`**；查看 `GET .../history/{version}`；回滚 `POST .../rollback` + `CONFIRM`。

### `admin/pages/step5-5-switch.html`（Step5.5 总开关）

- **实现状态**：已实现（STEP-026）。侧栏 **`activeKey='cp-step55-switch'`**（归入「对话流 Prompt」分组；旧 key `step55switch` 仍可兼容高亮）。`super_admin` / `ai_trainer` 可发布，`observer` 仅读当前状态。
- **接口**：`GET /api/admin/prompt/step5-5-switch`；`PUT /api/admin/prompt/step5-5-switch/draft` Body `{ enabled }`；`DELETE .../draft`；`POST .../publish`（**不要求**先跑主链 LLM 测试，仅需确认 **`CONFIRM`**）；`GET .../history`、`POST .../rollback`。配置键 **`step5_5_enabled`**（与 STEP-009 运行时读取一致）。

### 对话流 Prompt 只读页（`admin/pages/chat-prompt-*.html`）

- **实现状态**：已实现（2026-07-13）。侧栏分组 **`CHAT_PROMPT_MENU`**（`super_admin` / `ai_trainer`）；一级菜单**不再**单独列出「Prompt管理 / Step5.5开关 / 记忆规则」。
- **子项与落页**：

| 菜单 key | 展示名 | 页面 / 行为 |
|----------|--------|-------------|
| cp-step15 | Step1.5 查询重写 | `chat-prompt-step15.html`（只读，`GET .../chat-prompt-view/step15`） |
| cp-step3 | Step3 Prompt 拼装 | `chat-prompt-step3.html`（只读，`GET .../step3`） |
| cp-step5 | Step5 主对话 | `prompt.html?tab=step5`（可编辑） |
| cp-step55 | Step5.5 润色 | `prompt.html?tab=step55`（可编辑） |
| cp-step55-switch | Step5.5 开关 | `step5-5-switch.html`（可配置） |
| cp-step6 | Step6 记忆拆解 | `memory-rules.html?nav=cp-step6`（可编辑；`activeKey=cp-step6`） |
| cp-step8 | Step8 Future 主动 | `chat-prompt-step8.html`（只读） |
| cp-agent | Agent 主动 P0～P4 | `chat-prompt-agent.html`（只读；与 Step8 独立） |

- **样式**：分组标题与一级 `.menu-item` 同为 **14px**；二级 `.menu-sub` **14px**、`padding-left: 56px`。

### `admin/pages/test-tool.html`（AI测试工具）

- **实现状态**：已实现。主布局 **grid 40% : 60%**（`gap:16px`）；左侧自上而下：`测试参数配置` 卡片、`最近测试记录` 卡片（`margin-top:16px`）；右侧 `测试结果` 卡片。`activeKey='test'`，顶栏标题「AI测试工具」。`super_admin` / `ai_trainer` 可测试与保存，`observer` 仅可读配置和历史结果。样式入口：`admin-common.css` + 页内 `<style>`。
- **测试参数**：`使用配置` 单选——当前生效（`use_draft:false`）/ 草稿（`use_draft:true`）；关系等级、用户情绪；模拟记忆 `textarea`（按换行计非空行数，展示「已输入 n/5 条」，n>5 时 `.alert-warning`）；测试输入必填。
- **开始测试**：校验测试输入非空；`POST /api/admin/prompt/test`，Body 与 `PromptTestRequest` 一致（`mock_memories` 取前 5 条非空行）。服务端拼装与线上一致：**`PromptBuilder.build_chat_prompt`**（STEP-026）；`use_draft:true` 时使用 **`step5_system_prompt`** 草稿作为模块1。成功：右侧淡入展示 AI 气泡（头像「梦」）、人格匹配总分+等级 Tag、三维进度条（40%/40%/20%）、内容安全区块、`full_prompt` 折叠区（Token 数 `Math.ceil(full_prompt.length * 1.5)`）；底部「保存为测试用例」可用。
- **测试历史**：`localStorage` key=`admin_test_history`，最多 10 条，项含 `time`（ISO）、`test_input`、`use_draft`、`relationship_level`、`emotion_label`、`mock_memories`。点击行回填左侧表单；「清空」经 `showConfirm` 后清除并重绘。
- **保存测试用例**：Modal（宽约 480px）填写 `expected_pass_criteria`；`POST /api/admin/test-cases/persona`，Body 使用最近一次**成功**测试快照中的 `test_input`→`input`、`emotion_label`、`relationship_level` 及弹窗中的期望标准。成功 Toast「已保存为测试用例」并关闭 Modal。

### `admin/pages/safety-rules.html`（内容安全规则）

- **实现状态**：已实现。`activeKey='safety'`，顶栏标题「内容安全规则」。`super_admin` / `ai_trainer` 可修改，`observer` 仅读规则。
- **首屏**：`GET /api/admin/safety-rules`，将 `banned_keywords`、`persona_boundary_keywords`、`style_violation_keywords` 写入**三个可变的同一数组引用**（加载时原地 `replaceInPlace`，避免 Enter 添加与刷新后闭包指向旧数组）。
- **Tab**：`initTabs('safety-tabs')` — 违规关键词 | 人格禁区关键词 | 语言风格禁忌词。
- **标签云**：`min-height:120px` + `border:1px solid var(--border)` 容器；词条为 `span.safety-kw-tag`，`×` 仅从本地数组 `splice` 并重新渲染，**不立即请求**。
- **输入**：各 Tab `input` 宽 240px，`Enter` → `trim` 后非空且不重复则 `push` 并清空输入框。
- **保存**：对应 **PUT** `/api/admin/safety-rules/banned-keywords`、`.../persona-keywords`、`.../style-keywords`，Body `{ keywords }`；若当前数组为空则前端 Toast 提示（与后端 **`keywords` 至少 1 项** 一致），成功 Toast「保存成功」。
- **违禁词 Tab**：「批量导入 Excel」触发隐藏 `file`，`accept=".xlsx,.xls"`；`FormData` 字段名 **`file`** + `adminRequest('POST','/api/admin/safety-rules/banned-keywords/import', formData, true)`；成功 Toast「成功导入{imported_count}个关键词，当前共{total_count}个」并 **GET 刷新**。
- **首屏竞态**：首次 `GET /api/admin/safety-rules` 请求期间禁用三个输入框、三个「保存更新」与「批量导入 Excel」；待响应返回且（若成功）已 `replaceInPlace` + `renderAllClouds` 后再解除 `is-loading` 并启用控件（失败时仍启用，避免永久锁死）。
- **导入与未保存**：维护 `lastSyncedSnapshot`（成功 GET 或任意一次保存成功后对三数组的 `JSON.stringify`）；`isDirty()` 为真时点「批量导入 Excel」先 `showConfirm`（文案：将重新加载全部关键词，未保存的修改会丢失…），确认后再打开文件选择；取消则不发起导入。

### `admin/pages/knowledge.html`（角色知识库）

- **实现状态**：已实现。`activeKey='knowledge'`，顶栏标题「角色知识库」。`super_admin` / `ai_trainer` 可 CRUD，`observer` 仅可查询、筛选和分页。
- **Demo 区**：`.ck-demo-card` 固定展示 type / **三层 key** / value 示例与全角冒号格式说明；注明 `character_private` 不在此页维护。
- **列表**：`GET /api/admin/character-knowledge`；筛选 `type` + `keyword`（Enter 或点查询）；分页上一页/下一页；表格列 type（标签）、key（来自 `stable_key` 或 content）、value（截断 + `title` 全文）、编辑/删除。
- **新增**：Modal — type 下拉、**三层 key**（前端 `validateKeyFormat` 预检）、`value`；`POST` Body `{ type, key, value }`。
- **编辑**：`key` 与 type **只读**（`#ck-modal-key[readonly]`，隐藏 type 行）；仅改 `value`；`PUT /api/admin/character-knowledge/{encodeURIComponent(doc_id)}`。
- **删除**：`showConfirm(..., { danger: true })` 后 `DELETE` 同上路径。

### `admin/pages/memory-rules.html`（Step6 记忆拆解 / 原记忆规则页）

- **实现状态**：已实现。侧栏入口归入 **「对话流 Prompt → Step6 记忆拆解」**（`activeKey='cp-step6'`）；**一级菜单不再展示「记忆规则」**。顶栏标题仍可为「记忆规则配置」（页内文案未改业务逻辑）。`super_admin` / `ai_trainer` 可配置，`observer` 仅读 Step6 Prompt、全局记忆和非敏感 DashVector 参数。
- **布局**：顶部 **Tab 标签行**单独一块 `.page-card`（`memory-tab-header-card`），**每个 Tab 内容区**各包一层 `.page-card` 作为表单容器；外层 `#memory-page-wrap` 仅承担 `is-loading`，不再使用单一大卡片包全页。
- **Tab**（长记忆第一套下线改造，§6.6.3/§6.4.3）：`initTabs('memory-tabs')` — **Step6 记忆 Prompt（默认）** | 向量数据库配置 | **全局用户记忆**。**默认 Tab 为 Step6 记忆 Prompt**；旧「记忆规则」Tab（记忆提取 Prompt / 重要性评分 / 存储阈值 / 检索合并阈值）与 `memory-rules` GET/PUT 调用**已删除**（C-04/C-08，不展示历史 `memory_rules`）。
- **Step6 记忆 Prompt Tab**：`GET /api/admin/step6-memory-prompt` 填充 6 块分区表单（`system_instruction` / `output_format_rules` / `kv_field_rules` / `task_fields` 11 项按 `TASK_FIELD_NAMES` 固定顺序渲染 `textarea` / `merge_rules` / `few_shot_example`）；保存收集后 `PUT /api/admin/step6-memory-prompt`（**保存即发布**），任一文本块或任一 `task_fields` 子项为空则前端 `showToast` 拦截，成功 Toast「Step6 记忆 Prompt 已保存并发布」。
- **全局用户记忆 Tab**：`user_id`（选填 `number`）+ `keyword`（选填）+ 分页；`GET /api/admin/memories/global`，列 `用户ID/Key/Value/操作`；勾选行 + 「批量删除选中」或单行「删除」→ `DELETE /api/admin/memories/batch-delete`（Body `{doc_ids}`）；固定提示「未指定用户时仅在最多 300 条用户记忆中检索，结果可能不完整，建议填写用户 ID」（R-01），API 返回 `truncated:true` 时额外 `.alert-warning` 强化展示。
- **向量库 Tab**：`GET /api/admin/vector-db-config`；Endpoint（`type=url`）、Collection、TopK（**测连/保存须为 1–20**；`GET` 返回的 `top_k` **原样填入**（≥1），若历史上 &gt;20 则展示真实值，须改回 1–20 后再测连/保存，**不再**将非法值静默改为 5）、脱敏 Key 只读 +「修改」展开明文 `password` 输入；**点击「修改」**清空明文框并 `testPassed=false`、清空测连结果区；明文框 `input` 同样重置测试通过与结果；测试结果区 `#vector-test-result` **无内容时 `display:none`**，有结果时 `display:block`；**「测试连接」**发起请求前先展示 `.alert-info`「正在测试连接…」；`POST .../test-connection` Body 对应 `VectorDbTestRequest`：**`endpoint`、`collection_name`、`api_key` 三字段均可不传或传 `null`**，未提供的项由后端从**已发布配置**或**环境变量**补全（与 `memory_mgmt.py` 一致）；本页实现为：`endpoint`/`collection_name` 常带表单当前值（空则 `null`），**仅当明文 Key 框有非空值时带 `api_key`**；成功 `.alert-success` 与延迟 ms；失败 `.alert-error`，文案优先 `data.error`，否则回退 **`ApiResponse.message`**（仍用 `textContent` 写入节点）；`code≠0` 时在结果区展示 **`message`**（该请求使用 `adminRequest(..., { silentErrorToast: true })`，避免与统一信封错误 Toast 重复）；`res` 为空（网络异常、HTTP 非 JSON 等）时 `adminRequest` 仍可能保留全局 Toast，结果区展示「请求失败」摘要。通过后启用「保存」。**「保存」**初始 `disabled`+`title="请先测试连接"`；`PUT /api/admin/vector-db-config`，Body 含 `need_test_first:false`，`api_key` 仅在有新明文时传递；成功后 `testPassed=false`、禁用保存、收起明文编辑、`GET` 刷新脱敏 Key。
- **首屏加载**：`#memory-page-wrap.is-loading` 期间 `.memory-disable-while-load` 使用 `pointer-events:none` 避免未返回数据时误操作。**不**使用 `firstLoadFinished` 变量（该变量在 `safety-rules.html` 中仍用于首屏禁用控件，与本页实现无关）。

### `admin/pages/agent-rules.html`（Agent配置）

- **实现状态**：已实现。`activeKey='agent'`，顶栏标题「Agent配置」。`super_admin` / `ai_trainer` 可配置，`observer` 仅读 Agent 规则。
- **内存状态（切 Tab 不丢未保存编辑）**：`gTriggersData`、`gDecisionData`、`gMessageRulesData`、`p3Keywords` 四份独立对象；**PUT Body 以当前两 Tab 表单为准**（见下），成功后内存与已提交内容对齐。
- **首屏并行加载**（`DOMContentLoaded`，`adminRequest` + `silentErrorToast` 以便合并失败提示）：`GET /api/admin/agent-rules`、`GET /api/admin/agent-message-rules`、`GET /api/admin/agent-night-keywords`；`#agent-page-wrap.is-loading` 期间 `.agent-disable-while-load` 禁用操作。`data===null` 或缺字段时用与 `agent_service.py` 默认值一致的表单基线（如 P1 沉默天数 3、最少对话 10 轮等）。
- **Tab**：`initTabs('main-tabs')` — 触发条件（`#tab-triggers`）| 决策引擎 & 消息规则（`#tab-decision`）。
- **PUT `/api/admin/agent-rules`**：Body **必须**同时包含 `triggers` 与 `decision_engine`（与 `AgentRulesRequest` 一致）。「保存触发规则」与「保存决策配置」两次请求中，**`triggers` 均来自 `readTriggersFromForm()`**、**`decision_engine` 均来自 `readDecisionFromForm()`**（另一 Tab 隐藏时 DOM 仍可读），避免只改一侧却在另一侧保存时用旧 `gTriggersData`/`gDecisionData` 覆盖服务端；成功后回写 `gTriggersData`、`gDecisionData` 与 Body 一致。
- **P2**：`habit_days_threshold` 前端限制为 **5～当前 `accumulation_days`**，与 `agent_mgmt.py` 校验一致（`accumulation_days` 7–30）。
- **P3 凌晨关键词**：独立接口 **`GET`/`PUT /api/admin/agent-night-keywords`**，Body / 响应 `data.keywords` 为 `string[]`；`NightKeywordsRequest` 要求至少 1 个关键词。**「保存触发规则」**：始终 `PUT agent-rules`；仅当 `p3Keywords.length >= 1` 时并行 `PUT agent-night-keywords`；若关键词为空，仍提示触发规则保存成功，并 **Toast 警告** 未调用关键词保存（避免与服务端 `min_length=1` 冲突）。标签删除用 `indexOf`+`splice` 后 `renderP3Tags()`。
- **agent-message-rules**：**`GET /api/admin/agent-message-rules`** 成功时 `data` 为以 `P0`…`P4` 为 key 的对象，元素含 `generation_requirements`、`examples`、`max_length`。消息规则子卡片：`examples` 至少 3 条输入框，不足补空；删除钮仅当行数 &gt; 3 时显示；最多 5 条示例。**「保存决策配置」**：先 `PUT agent-rules`；再对校验通过的类型 **按 P0→P4 串行** **`PUT /api/admin/agent-message-rules/{type}`**（避免后端整包读-改-写时并行请求互相覆盖），Body `generation_requirements`、`examples`（trim 后非空，3–5 条）、`max_length`（**必填**，20–100）；某类型示例 &lt; 3 或长度非法则 **跳过该类型** 并 Toast，其余仍提交；部分失败 Toast「部分配置保存失败，请检查」。**「保存决策配置」**前同样执行 P2 习惯门槛校验（与「保存触发规则」一致）。
- **运行时说明**：`triggers` / `decision_engine` 持久化后 **当前 `AgentService` 仍未读取**（与后台配置易不一致），见 **`docs/tech-debt.md` [TD-004]**；**P3 关键词**经 Redis `agent:night_keywords` 已接入运行时。

### `admin/pages/relationship-rules.html`（关系成长配置）

- **实现状态**：已实现。`activeKey='relationship'`，顶栏标题「关系成长配置」。`super_admin` / `ai_trainer` 可配置，`observer` 仅读关系规则。
- **顶部横幅**：始终展示 **TD-005**（配置写入 `admin_config` 与 `relationship_service.py` 硬编码未对齐，见 `docs/tech-debt.md`）。
- **Tab**：`initTabs('main-tabs')` — 等级配置（`#tab-levels`）| 成长值规则（`#tab-growth`）。
- **接口**：`GET` / `PUT` **`/api/admin/relationship-rules`**
  - **PUT Body** 须同时包含 `levels`、`growth_rules`、`confirmed`。
  - `confirmed:false`：仅返回影响预览（`affected_upgrade_users`、`affected_downgrade_users`），不发布。
  - `confirmed:true`：发布配置并执行升级；对「应降级」用户写 Redis 过渡期（7 天），与 `relationship_mgmt.py` 一致。
  - 最高等级（level 3）的 `threshold` 前端提交 **99999**（表单展示为禁用占位「最高等级」）；后端校验要求阈值列严格递增。
- **成长值规则**：表格行 `action_type` 与 `relationship_service.py` 中 **`GROWTH_ACTIONS`** 一致：`dialog` / `long_session` / `daily_login` / `reply_agent`。
- **前端校验（成长值）**：`readGrowthRulesFromForm()` 要求每行「单次积分」「每日上限」均为 **≥1 的整数**（`parseInt` 后校验）；非法时 `showToast(..., 'error')` 并返回 **`null`，不发起 PUT**。「检查影响并保存」「影响预览 · 确认保存」「保存成长规则」三处在组 Body 前均判断 `growth` 非空。
- **默认值**：`GET` 的 `data` 为 `null` 或缺字段时，前端用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` 等价默认填充（与 `relationship_service.py` 硬编码一致）。
- **交互**：「检查影响并保存」先 `PUT` `confirmed:false` 弹出「影响预览」Modal，再「确认保存」`confirmed:true`；「保存成长规则」直接 `PUT` `confirmed:true`（与等级表单当前值一并提交）。

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

### `admin/pages/data-report.html`（数据报表）

- **实现状态**：已实现。`activeKey='report'`，顶栏标题「数据报表」。`super_admin` / `ops_admin` / `observer` 可访问，observer 不可导出；**`ai_trainer` / `tech_ops`** 跳转 `error.html?type=403`。
- **聚合卡片**：`GET /api/admin/stats/dashboard`，按 **嵌套字段** 读取（`retention` / `conversation` / `ai_performance` 等）；字段为 `null` 时统一展示「—」；标注「(今日)」的指标与后端「当日」统计一致。
- **总注册用户数**：`GET /api/admin/users?page=1&page_size=1` 的 `data.total`（与日期筛选无关，首屏一次）。
- **报表明细与图表**：`GET /api/admin/stats/report?report_type=...&start_date=...&end_date=...&page=1&page_size=100`；Tab 切换后延迟 `onQuery` 刷新当前类型数据；**用户** Tab 期间新增/对话期间总量等由 `list[]` 前端求和。
- **功能使用 Tab**：后端 `feature` 行字段仅 `date` / `agent_sent` / `agent_opened` / `reply_rate`；缺按日 `open_rate` / `agent_replied` 见 **TD-009**。
- **AI 性能 Tab**：折线图为 **人格偏离率按日**（`list[].deviation_rate`），非 LLM 响应时长；见 **TD-008**。
- **导出 Excel**：`adminRequest('POST', url)` **不传 `data` 参数**，URL 含 `report_type`、`start_date`、`end_date` Query，由 `admin-api.js` 识别 `spreadsheetml` 触发 blob 下载。
- **图表**：ECharts；`chartInstances` + `getChart`；`window.resize` 时 `resize()`。
- **Tab 切换与「查询」**：`initTabs` 切换后 **`setTimeout(0, onQuery)`**，且 **`onQuery()` 返回的 Promise 完成后再 `setTimeout(50ms, resizeAllCharts)`**，避免请求未完成时提前 `resize` 导致图表尺寸异常；「查询」按钮同样 **`onQuery().then` → 延迟 `resize`**。首屏加载同逻辑。
- **用户报表饼图**：`extra.level_distribution` 为全量用户等级分布，**与日期筛选无关**；页面饼图标题下灰色说明与接口语义一致。


### 生活流管理页（`admin/pages/` · 侧栏「🌿 生活流 Prompt」）

| 页面 | 菜单 key | 内容摘要 |
|------|----------|----------|
| `life-plan.html` | life-plan | 周大纲 / 日场景 CRUD；ops 只读 |
| `life-feed-global.html` | life-feed-global | **生活流人格拓展**（原「全局配置」：人设扩展 + 词汇表 + Header 配置） |
| `feed-posts.html` | feed-posts | 列表/详情/编辑/发帖/显隐；计划时间 `formatWallClock`；详情含虚拟评论底；**无**删除钮 |
| `feed-comments.html` | feed-comments | 筛评/编辑/软删/补发 |
| `agent-aware.html` | agent-aware | 队列视图/重试/删除；super 可重置特殊档 |
| `worldview.html` | worldview | 快照近14天分页 + 事件库；ops 只读 |
| `life-feed-prompts.html` | life-feed-prompts / -i | P-01~14 + 图像映射 + 互动参数（模型/延迟/特殊档） |
| `life-feed-system.html` | life-feed-system | 自动发布/窗口/可见范围/点赞倍率 + **Liblib 生图参数** + Liblib 看板 |

**前端约定**：`LIFE_FEED_MENU` + `initLifeFeedPage`；列表统一 `admin-table`；只读角色隐藏 `[data-edit-only]`；侧栏滚动记忆 `admin_sidebar_scroll`。分组标题展示名 **「🌿 生活流 Prompt」**（原「生活宇宙」，2026-07-13）；插入位置在 **「对话流 Prompt」之后**（`MENU_CONFIG` 占位 `group:'life_feed'`）。  
**子项顺序（2026-07-13）**：**生活计划 → 生活流人格拓展 → 朋友圈·内容 → 评论 → 感知 → 她的宇宙 → Prompt·生活流 → 发布&系统参数**。  
ops_admin 可见子项相对顺序：生活计划 → 内容 → 评论 → 感知 → 她的宇宙。

**相关技术债**：TD-033 日计划 LLM 日志摘要未做；TD-035 真删帖未分离；TD-036 本地图片上传未实现。联调台账快照：`docs/contract/drafts/生活流/M1_临时缺陷台账.md`（TB-LF-001~010 均已闭合）。

---

### 技术债记录（关系 / 日记管理页）

| 编号 | 说明 |
| --- | --- |
| **TD-005** | `relationship_rules` 已写入 `admin_config`，`relationship_service.py` 仍用 `LEVEL_CONFIG` / `GROWTH_ACTIONS` / 固定阈值判定，需改服务后后台配置才对用户端生效。 |
| **TD-006** | ~~`diary-history.html` 未建~~ → 已提供页面与 **super_admin / ops_admin** 菜单；`diary-rules` 内历史链接已可用。 |
| **TD-007** | ~~生成与调度未读配置~~ → 已读 `diary_rules`（`diary_rules_loader` + `DiaryService` + 启动时 Cron **`Asia/Shanghai`**）；兼容旧 `generation_prompt`。 |
| **TD-008** | LLM 响应耗时无法按日拆分；数据报表 AI 性能折线用人格偏离率；仪表盘 `llm_avg_response_ms` 无样本为 `null`。 |
| **TD-009** | `report_type=feature` 缺按日 `open_rate` / `agent_replied`，表格暂 4 列。 |
| **TD-010** | `GET /system/status` 的 `alerts[]` 无单条发生时间，监控页用刷新时刻代替；补充字段时的修改范围与库内消费方见 `tech-debt.md`。 |
| **TD-011** | `get_system_status` 在 Redis INFO 异常时 `hits`/`misses` 可能未定义，存在 `NameError` 风险；见 `tech-debt.md`。 |

---

## 开发日志

### STEP-001：relationship 表 DDL 迁移
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：为 relationship 表新增 9 个扩展字段，支撑 Step6 记忆写回与 Step8 Future 槽机制
- 涉及文件：
  - `backend/models/relationship.py`（修改）
  - `alembic/versions/v4a_step001_relationship_extend.py`（新增）
- 字段变更：
  - 新增字段：relation_description - TEXT - 关系描述
  - 新增字段：user_real_name - VARCHAR(50) - 用户真实称呼
  - 新增字段：user_hobby_name - VARCHAR(50) - 用户昵称
  - 新增字段：user_description - TEXT - 用户印象
  - 新增字段：character_purpose - TEXT - 角色当前回应策略
  - 新增字段：character_attitude - TEXT - 角色当前态度
  - 新增字段：future_timestamp - INTEGER - Future 预约时间戳
  - 新增字段：future_action - VARCHAR(200) - Future 预约意图摘要
  - 新增字段：proactive_times - INTEGER(default=0) - 主动消息计数
- 测试结果：✅ Lint 通过，ORM 与迁移脚本字段一致
- 备注：无

### STEP-002：relationship 变更历史表
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：创建 append-only 历史表 `relationship_change_history`，记录 Step6 对 relationship 扩展字段的每次更新；`RelationshipHistoryService.append_history()` 仅做 INSERT，支持排障与回溯
- 涉及文件：
  - `backend/models/relationship_change_history.py`（新增）
  - `backend/models/__init__.py`（修改：注册 RelationshipChangeHistory）
  - `alembic/versions/v4b_step002_relationship_change_history.py`（新增）
  - `backend/services/relationship_history_service.py`（新增）
  - `tests/test_relationship_change_history.py`（新增）
- 字段变更：
  - 新增表：relationship_change_history（9 个字段，详见数据库表结构章节）
- 测试结果：✅ 全部通过（7 个用例：单条写入字段完整性、连续写入排序、old_value 为 NULL、round_id 为 NULL、按 user_id 查询、空历史）
- 备注：主键使用 `BigInteger().with_variant(Integer, "sqlite")` 兼容 SQLite 测试环境的 autoincrement 限制

### STEP-003：DashVector type 常量 + search/upsert 签名扩展
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `constants.py` 定义 4 类 DashVector 向量类型常量（R-L1L3-08），扩展 `dashvector_client` 的 `upsert()` / `search()` 签名支持 `memory_type` 参数（R-L1L3-15），按规则拼接 filter 实现分类型检索与写入（R-VEC-01）
- 涉及文件：
  - `backend/constants.py`（修改：新增 `MEMORY_TYPE_CHARACTER_GLOBAL` / `MEMORY_TYPE_CHARACTER_PRIVATE` / `MEMORY_TYPE_CHARACTER_KNOWLEDGE` / `MEMORY_TYPE_USER` 常量及 `VALID_MEMORY_TYPES` 校验集合）
  - `backend/utils/dashvector_client.py`（修改：`upsert()` 新增 `memory_type` 参数并自动注入 `type` 字段；`search()` 新增 `memory_type` 参数、`user_id` 改为可选、按规则拼接 filter）
  - `backend/services/vector_service.py`（修改：`upsert()` / `search()` 透传 `memory_type` 参数）
  - `backend/services/memory_service.py`（修改：5 处调用适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/routers/chat.py`（修改：`_search_memories` 适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/services/agent_service.py`（修改：`_search_memories_for_agent` 适配 `memory_type=MEMORY_TYPE_USER`）
  - `backend/routers/admin/users.py`（修改：编辑记忆 upsert 适配 `memory_type=MEMORY_TYPE_USER`）
- 字段变更：
  - 新增常量：`MEMORY_TYPE_CHARACTER_GLOBAL` = `"character_global"` - 角色公开设定
  - 新增常量：`MEMORY_TYPE_CHARACTER_PRIVATE` = `"character_private"` - 角色私有设定
  - 新增常量：`MEMORY_TYPE_CHARACTER_KNOWLEDGE` = `"character_knowledge"` - 角色知识技能
  - 新增常量：`MEMORY_TYPE_USER` = `"user"` - 用户画像
  - `dashvector_client.search()` 签名：新增 `memory_type: str`，`user_id: int` → `user_id: int | None = None`
  - `dashvector_client.upsert()` 签名：新增 `memory_type: str`，自动向 fields 注入 `"type"` 字段
  - filter 拼接规则：无 user_id → `type = '{memory_type}'`；有 user_id → `type = '{memory_type}' AND user_id = {uid}`
- 测试结果：✅ Lint 通过，所有现有调用已适配新签名
- 备注：无（本环节不新建 collection、不做旧数据迁移；Step2 多路检索已在 STEP-020 实现）

### STEP-004：Step5 Prompt 提示词改造
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：按 `Step5-prompt提示词改造.md` 对 `prompt_builder.py` 进行最小化改写，输出新 6 字段 JSON Schema（inner_monologue / messages / relation_change / future / emotion / knowledge_expand），新增【知识性话题回应原则】与【当前时间】模块，关系状态追加 4 行扩展字段，同步更新 hint 与主动消息 Schema
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：`SYSTEM_PROMPT_TEXT` 完全替换为新 Schema + 示例 + 知识性话题原则；`_build_relationship_prompt()` 尾部追加 4 行扩展字段；新增 `_generate_time_description()` 和 `_build_time_prompt()`；`build_chat_prompt()` 插入时间模块；`_build_user_input()` hint 替换；`_build_active_task_instruction()` 输出指令同步；Token 预算调整）
  - `backend/routers/admin/prompt_mgmt.py`（修改：`_MODULE_TOKEN_LIMITS` 与 `_TOTAL_TOKEN_LIMIT` 同步调整）
  - `tests/test_prompt_builder.py`（新增：10 个测试用例覆盖 Schema 验证、扩展字段注入/空值、模块顺序、时间描述）
  - `docs/contract.md`（修改：更新时间、Token 限制引用、开发日志）
- 字段变更：
  - `MODULE_TOKEN_LIMITS["system"]`：400 → 1200（含完整 Schema + few-shot 示例，实测 1152 Token）
  - `MODULE_TOKEN_LIMITS["relationship"]`：200 → 250（追加 4 行扩展字段）
  - `MAX_TOTAL_TOKENS`：4096 → 5200
  - `prompt_mgmt.py` `_MODULE_TOKEN_LIMITS` / `_TOTAL_TOKEN_LIMIT` 同步更新
  - `SYSTEM_PROMPT_TEXT`：新增【回复格式规则】messages 数组 + type 约束、【知识性话题回应原则】、完整 6 字段 JSON Schema + 字段说明 + 输出示例
  - `_build_relationship_prompt()` 输出：追加 `关系描述` / `对TA的印象` / `亲密称呼` / `用户真名` 四行（读取 STEP-001 新增的 relationship 扩展列）
  - 新增模块★【当前时间】：`_generate_time_description()` 生成 `现在是{周几}{时段}{时}点{分}分`
- 测试结果：✅ 全部 10 个用例通过
- 备注：无（不改【身份禁区】【核心陪伴原则】【人格设定】【用户记忆】【情绪状态】【最近对话】的原有内容；不实现 Step5.5；不实现 Step1-3 角色记忆/知识检索）

### STEP-005：Step5 输出 JSON 解析器 + 校验规则
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：替换现有 `{emotion, reply}` 解析器，支持新 6 字段扁平 JSON 解析 + 严格校验（§2.7.7 / CP3 / U1 / U2 / R-BND-02）
- 涉及文件：
  - `backend/services/llm_service.py`（修改：新增 `Step5ParseError` 异常类、`MessageItem` / `RelationChange` / `FutureSlot` / `EmotionResult` / `Step5Output` Pydantic 模型、`parse_step5_output()` 解析函数、`LLMService.chat_with_step5_parse()` 方法；保留旧 `chat_with_parse_strict` 供 Agent 主动消息等旧链路兼容）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 内 `chat_with_parse_strict` → `chat_with_step5_parse`，不再读取 `result["reply"]`，改为拼接 `step5_result.messages[].content`；SSE Future payload 新增 `step5` 字段携带完整结构化数据）
  - `tests/test_step5_parser.py`（新增：25 个单元测试覆盖合法解析、CP3 大小写敏感、U2 空消息、U1 knowledge_expand trim、默认值填充、边界非 JSON）
- 字段变更：
  - 新增 Pydantic 模型 `Step5Output`：`inner_monologue(str)` / `messages(List[MessageItem])` / `relation_change(RelationChange)` / `future(FutureSlot)` / `emotion(EmotionResult)` / `knowledge_expand(str)`
  - SSE `_resolve_generation_future` payload 新增 `step5: dict`（`model_dump()` 序列化）
  - `ai_reply` 生成逻辑：`"\n".join(m.content for m in step5_result.messages)`
- 校验规则：
  - JSON 解析失败 → `Step5ParseError`
  - `messages` 为空数组或全部 content trim 为空 → `Step5ParseError`（U2）
  - 任一 `messages[].type` 非精确 `"text"` → `Step5ParseError`（CP3，大小写敏感）
  - `knowledge_expand` trim 后仅精确「是」为是，其余按「否」（U1），不判失败
  - `relation_change.delta` 缺失 → 默认 0（R-BND-02）
  - `future` 缺失 → 默认 `time_natural="无", action="无"`
- 测试结果：✅ 全部 25 个用例通过
- 备注：STEP-006 已实现 messages >5 合并；STEP-007 已实现 `future.time_natural` 解析（见 STEP-007）；Step5.5 触发与润色见 **STEP-009**。

### STEP-006：messages >5 条合并规则（§2.9.1）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：实现 §2.9.1 定义的消息合并规则——当 messages 超过 5 条时，将第 6 条及以后的 content 按顺序用半角空格拼入第 5 条（下标 4）末尾；合并后若超过可配置的单条长度上限则尾部截断并打日志
- 涉及文件：
  - `backend/constants.py`（修改：新增 `MAX_MESSAGES_COUNT=5` 消息最大条数上限、`MAX_SINGLE_MESSAGE_LENGTH=2000` 合并后单条 content 最大字符数）
  - `backend/services/llm_service.py`（修改：新增 `merge_messages_if_exceed(messages, max_count=5, max_length=2000)` 纯函数；新增 import `MAX_MESSAGES_COUNT` / `MAX_SINGLE_MESSAGE_LENGTH`）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 内 Step5 成功后先算 `step6_messages`（Step5 原始 messages 合并），再条件调用 Step5.5（STEP-009）；`final_messages` 为 5.5 成功时的润色结果否则为 Step5 合并结果；`ai_reply` 与 SSE payload 中 `step5.messages` 使用 `final_messages`）
  - `tests/test_merge_messages.py`（新增：16 个单元测试覆盖不合并、6 条合并、8 条合并、截断+日志、自定义参数、空格拼接等场景）
- 消费点接入：
  - 消费点 1（Step5 路径 / 5.5 回退）：`final_messages = merge_messages_if_exceed(step5_result.messages)` — 未触发 Step5.5 或 5.5 失败/未命中门闩时使用；`ai_reply`、`step5.messages` 均基于此
  - 消费点 2（Step5.5 输出后）：`execute_step5_5` 返回非空时 `final_messages = step5_5_result`（函数内已对 5.5 解析结果执行 `merge_messages_if_exceed`），见 **STEP-009**
  - 消费点 3（Step6 入参快照 CP1）：`step6_messages = merge_messages_if_exceed(step5_result.messages)`，**仅** Step5 原始产出，供后续 Step6 入队，见 **STEP-016**
- 函数签名：`merge_messages_if_exceed(messages: list[MessageItem], max_count: int = 5, max_length: int = 2000) -> list[MessageItem]`
- 合并规则：
  - `len(messages) <= max_count` → 原样返回（浅拷贝）
  - `len(messages) > max_count` → 保留前 max_count-1 条不变，第 max_count 条 content 与后续所有条 content 用半角空格拼接
  - 合并后 content 长度 > max_length → 尾部截断至 max_length + WARNING 日志
  - 纯函数，不修改入参
- 测试结果：✅ 全部 16 个用例通过
- 备注：消费点 3（Step6 入队接线）已由 **STEP-016** 完成；不修改 LLM Prompt 中对条数的描述；SSE 多气泡分包推送逻辑已在 **STEP-010** 实现

### STEP-007：future.time_natural 时间解析器（§2.8.4）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：纯 Python 正则解析 LLM 输出的 `future.time_natural`，基准时区 UTC；合法格式返回 Unix 秒级时间戳，「无」返回 `None`（无预约）；非法格式返回 `None` 并 `logger.warning` 结构化日志（`raw_input` / `reason` / `action=slot_cleared`）。另提供 `is_future_slot_valid(ts)`：`now - ts <= 1800` 为有效（30 分钟过期窗口）
- 涉及文件：
  - `backend/utils/future_time_parser.py`（新增：`parse_future_time`、`is_future_slot_valid`、内部 `_log_parse_failure`）
  - `tests/test_future_time_parser.py`（新增）
- 字段变更：
  - 无（本环节仅新增工具模块与测试，未改数据库与对外 HTTP 契约）
- 测试结果：✅ 全部 22 个用例通过
- 备注：未接入 `chat.py` / `relationship` 写入与 Step8 轮询消费（仍不在本 STEP 范围）；调用方在解析失败时需自行清空 Future 槽并保留 `proactive_times`（与需求 §2.8.4 一致）

### STEP-008：round_id 提前生成 + 超时配置（§2.9.3 / §2.11.2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`round_id` 在 `_execute_llm_bundle` 内于 Step5 解析成功（`chat_with_step5_parse` 正常返回）后立即 `str(uuid.uuid4())` 生成；同一值传入 `_persist_bundle_success` 写入本轮 pack 内全部 user 行、**全部 assistant 行**（STEP-011 起可为 N 行）及 `emotion_log`；成功闭环时 `_resolve_generation_future` 的内存 payload 增加 `round_id`、`step6_messages`（合并后 messages 的 `model_dump` 列表）供后续 Step6 入队读取；`_sse_chat_wait_bundle` 使用 `_BUNDLE_WAIT_TIMEOUT_SEC = 120.0`（**仅** `asyncio.wait_for` 等待本代 Future 的上限，**不**约束 `_execute_llm_bundle` 整段墙钟，见 **POST /api/chat/send** 与 **「部署与网关（对话 SSE）」**）；`LLM_TIMEOUT_CHAT`（默认 45s）未改；仓库内 `nginx/nginx.conf` 的 `proxy_read_timeout` 已为 300s，满足 ≥130s。
- 涉及文件：
  - `backend/routers/chat.py`（修改）
  - `tests/test_chat.py`（修改：新增 `TestStep008RoundId`；`test_chat_send_stream_response` 改为 mock `chat_with_step5_parse`）
  - `docs/contract.md`（修改：顶部摘要、本开发日志条目）
- 字段变更：
  - 新增字段：无（MySQL/SQLite 表无 DDL 变更）
  - 修改字段 / 契约扩展：`Future` 成功 payload 新增 `round_id`（`str`，UUID 文本）、`step6_messages`（`list[dict]`，Step6 入参快照）；私有函数 `_persist_bundle_success` 新增必填参数 `round_id: str`（原在函数内 `uuid.uuid4()` 生成，现改为调用方传入）；模块常量 `_BUNDLE_WAIT_TIMEOUT_SEC`：`55.0` → `120.0`（**SSE** 侧 `wait_for` 等待同代 Future 的上限；**非**后端 `_execute_llm_bundle` 墙钟硬指标）
- API / 接口契约：
  - 接口名称：无新增 HTTP 路由
  - Method + Path：无变更（`POST /api/chat/send`、`POST /api/chat/resend` 等）
  - Request Body：无变更
  - Response：成功 / 失败信封与 SSE 事件类型与 STEP 前一致；`round_id` / `step6_messages` 仅服务端 Future 内存 payload
  - 变更类型：无（对外契约不变）
- 数据模型：
  - 表名 / 集合名：无新增表
  - 变更类型：无（未新增列、未修改列类型）
  - 字段详情：`conversation_log.round_id`、`emotion_log.round_id` 仍为既有列（TD-016 / V2-B）；本 STEP 仅改变 `round_id` 的生成时机与落库/Future 一致性
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 共 28 条，含 `TestStep008RoundId` 3 条）
- 未完成项记录：
  - 无（Step6 异步入队与 `Step6Snapshot` 使用 `round_id` 及合并后 messages 已在 **STEP-016** 完成；STEP-008 仍负责 Future payload 携带 `round_id` / `step6_messages` 供观测）
- 备注：`round_id` 与 `generation_id` 仍为独立 UUID（需求文档「与 generation_id 同源」为建议项）；Step5 解析失败路径不生成 `round_id`、不调用 `_persist_bundle_success`。**STEP-011** 起 `_persist_bundle_success` 的 assistant 落库参数由 `ai_reply: str` 改为 `messages: list`（多行 assistant），`round_id` 传入方式不变。**`_BUNDLE_WAIT_TIMEOUT_SEC`** 仅为 SSE 侧 `wait_for` 上限，**非**整链墙钟硬指标，见契约顶栏「SSE 等待上限语义」与 **POST /api/chat/send**。

### STEP-009：Step5.5 触发判定 + LLM 调用 + 解析（§2.7.1 / §2.7.4 D2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 Step5 解析成功后，读取 `admin_config` 总开关与双门闩 OR 判定；命中则按 `doc/step5_5_prompt.md` 拼装 Prompt、调用豆包非流式接口、解析 JSON 数组、经 `merge_messages_if_exceed` 合并至 ≤5 条后覆盖 `final_messages`；未命中/超时/解析失败则回退 Step5 合并 messages（R-BND-06）。`step6_messages` 始终仅基于 Step5 原始 messages 合并（R-BND-05）。
- 涉及文件：
  - `backend/services/step5_5_service.py`（新增）
  - `backend/routers/chat.py`（修改：接入 `execute_step5_5`、`LEVEL_DEFINITIONS`）
  - `tests/test_step5_5.py`（新增）
  - `docs/contract.md`（修改：本条目、admin_config 说明、H5 对话语义摘要、STEP-006 消费点描述）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：无
  - 新增运行时配置约定：`admin_config.config_key = step5_5_enabled`，`config_value` 可为 JSON 布尔 / 字符串 / 数字等，`get_active_config` 解析后按实现约定判定开/关（true/1/on/yes/enabled 等视为开启）
- API / 接口契约：
  - 接口名称：无新增用户端或管理端 HTTP 接口
  - Method + Path：无变更（仍通过 `POST /api/chat/send`、`POST /api/chat/resend` 触发同一 `_execute_llm_bundle` 链路）
  - Request Body：无变更（`ChatSendRequest` / `ChatResendRequest`）
  - Response：成功仍为 SSE（`meta` / `delta` / `done` / `failed` / `obsolete`）；**不**因 Step5.5 新增帧类型；失败码与既有定义一致
  - 变更类型：**服务端内部行为扩展**（条件追加第二次 LLM HTTP 调用，子超时 30s）
- 数据模型：
  - 表名：`admin_config`（既有表）
  - 变更类型：新增约定 `config_key` 行（由运维/后台发布，非代码迁移自动生成）
  - 字段详情：`config_key = step5_5_enabled`；`config_value` 为开关语义内容；须 `is_active=true` 且 `is_draft=false` 的生效行；Redis 键 `active_config:step5_5_enabled` 与现有热加载机制一致
- 触发判定规则（§2.7.1）：
  - 总开关（B3）：`step5_5_enabled` 关闭 → 不执行 Step5.5
  - 门闩 A：`rand < 0.12`（12%）
  - 门闩 B：仅 `knowledge_expand == "是"` 时 `rand < 0.5`（50%）
  - 命中 A OR B → 执行 Step5.5
- LLM 调用规则：
  - 独立子超时 30s（§2.7.4 D2）：`asyncio.wait_for` + `llm_client.chat_sync(..., timeout_sec=30)`
  - 输出：顶层 JSON **数组**（R-BND-04），元素 `{ "type": "text", "content": "..." }`，解析后经 `merge_messages_if_exceed` 至 ≤5 条
- 回退机制（R-BND-06）：超时、HTTP 异常、非法 JSON、`type`/`content` 校验失败 → `execute_step5_5` 返回 `None`，主链路使用 Step5 的 `merge_messages_if_exceed(step5_result.messages)` 作为 `final_messages`
- 测试结果：✅ 全部通过（`pytest tests/test_step5_5.py` 共 32 条）
- 测试覆盖场景：
  - 场景1：总开关关闭 → 不触发（4 个用例）
  - 场景2：开关开启 + knowledge_expand="否" + 命中门闩 A（3 个用例）
  - 场景3：开关开启 + knowledge_expand="是" + 命中门闩 B（4 个用例）
  - 场景4：LLM 返回非法 JSON → 回退（4 个用例）
  - 场景5：LLM 超时 → 回退（2 个用例）
  - 边界：5.5 返回 7 条 → 合并到 5 条（2 个用例）；解析/Prompt/开关值兼容等（13 个用例）
- 未完成项记录：
  - 无（管理端 Step5.5 总开关与模板编辑已由 **STEP-026** 交付）
- 备注：`should_trigger_step5_5()` 支持 `_rand_a` / `_rand_b` 单测注入；Step5.5 Prompt 正文由 **`admin_config:step5_5_prompt_fragments`** 六段模板热加载（缺省与 `step5_5_prompt_fragments.py` / `doc/step5_5_prompt.md` 对齐），运行时 **`build_step5_5_prompt(..., fragments=...)`** 拼装。Step5.5 走 `llm_client` 直调，**未**写入 `LLMService._record_stats` 的 Redis 统计（与主链路 Step5 调用不同）；若需看板包含 5.5，可在后续 STEP 对齐统计写入。

### STEP-010：SSE 协议扩展（多气泡流式）（§2.9.4 / §2.7.5 / §2.7.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：服务端 `_sse_chat_wait_bundle` 按 CP2 先发 `meta`（含 `message_count`、`generation_id`），再按条发 `delta`（含 `message_index`），末包 `done` 含整轮 `messages` + `emotion`；`step5.messages` 为空时回退 `reply` 单条。H5 `appendAIThinkingBubble` / `consumeChatSse` 不预铺空气泡、按 index 填槽、`done.messages` 定稿。单测：`TestStep010SseMultiBubble`（3 条集成、单条边界、Python 镜像 H5 乱序填槽与 done 覆盖语义）、`test_chat_send_stream_response` 补充断言；集成路径须 mock `execute_step5_5`，避免 `admin_config_service` 走未 mock 的 `redis_client.get_redis`。
- 涉及文件：
  - `backend/routers/chat.py`（修改）
  - `frontend/pages/chat.html`（修改）
  - `tests/test_chat.py`（修改）
  - `docs/contract.md`（修改）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段 / 契约扩展（SSE JSON 行，非 ORM）：
    - `meta.message_count` - `int` - 本轮气泡条数 N（失败/obsolete/超时路径可为 0）
    - `delta.message_index` - `int` - 目标气泡下标 0≤index<N
    - `done.messages` - `array` - `[{"type":"text","content":"..."}, ...]`，客户端真相源
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 全量）
- 备注：未实现 voice/image 多模态 SSE；`resend` 与 `send` 共用协议未单独改。真实网络乱序 E2E 未纳入本 STEP，乱序/以 done 为准由 Python 镜像单测覆盖。
- API / 接口契约：
  - 接口名称：H5 对话流式发送 / 叹号重发
  - Method + Path：`POST /api/chat/send`、`POST /api/chat/resend`（无变更）
  - Request Body：与 `ChatSendRequest` / `ChatResendRequest` 一致（无变更）
  - Response：
    - 成功：`StreamingResponse`（`text/event-stream`），SSE 行 JSON；`meta`：`generation_id`、`message_count`；`delta`：`content`、`message_index`；`done`：`messages`、`emotion`；另含 `failed` / `obsolete` 等既有类型
    - 失败（未进 SSE）：`ApiResponse`，`code` + `message`（如队列满 10104 等，与既有定义一致）
  - 变更类型：**修改**（SSE 帧字段扩展，事件类型名不变）
- 数据模型：
  - 表名 / 集合名：无
  - 变更类型：无
  - 字段详情：无
- H5 端行为变更（契约补充）：
  - `appendAIThinkingBubble()`：`setMessageCount` / `appendTextAt` / `finalize`
  - `consumeChatSse()`：解析 `meta.message_count`、`delta.message_index`、`done.messages`
- 未完成项记录：
  - 无

### STEP-011：conversation_log 多气泡落库（§2.8.1 / §2.8.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：成功闭环时 `_persist_bundle_success` 将 `final_messages`（Step5.5 成功则为其输出，否则 Step5 合并后列表）按条落库：`allocate_sort_seq(user_id, count=len(messages), db=...)` 一次取 N 个连续序号，循环插入 N 行 `ConversationLog(role="assistant", content=messages[i].content, sort_seq=seqs[i], round_id=...)`；pack 内 user 行仍批量标 `delivered` 并写同一 `round_id`；`emotion_log` 仍挂首条 pack user 的 `id`。`messages` 为空时函数直接 `return` 并打 warning（正常路径不应出现）。`GET /api/chat/timeline` 未改代码：合并后按 `sort_seq` 排序，多 assistant 自然按序展示。
- 涉及文件：
  - `backend/routers/chat.py`（修改：`_persist_bundle_success` 签名 `ai_reply`→`messages`，`_execute_llm_bundle` 传 `final_messages`）
  - `tests/test_chat.py`（修改：新增 `TestStep011MultiBubblePersist`；`TestStep008RoundId::test_persist_bundle_success_uses_passed_round_id` 适配新签名）
  - `docs/contract.md`（修改：本条目、表说明、H5 模块语义、timeline 说明、顶部摘要）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：无（`conversation_log` 列集合不变）
  - 行为变更：原「每轮成功闭环写 **1** 行 assistant（`content` 为多气泡 `\n` 拼接）」→ 写 **N** 行 assistant（N = 对外 messages 条数，≤5 由 Step5/合并保证），每行独立 `id` / `sort_seq`，`round_id` 与本轮 user 行一致
- 测试结果：✅ 全部通过（`pytest tests/test_chat.py` 全量 36 条，含 STEP-011 新增 4 条）
- 备注：管理后台用户对话查看页 **未** 在本 STEP 适配多行 assistant 展示（与需求范围一致）；人格偏离率分母仍为当日 `role=assistant` 的 `conversation_log` **行数**，多气泡一轮会计多条。
- API / 接口契约：
  - 接口名称：无新增路由；H5 timeline / send 响应结构字段名不变
  - Method + Path：`GET /api/chat/timeline`、`POST /api/chat/send`、`POST /api/chat/resend` — **路径与 JSON 信封不变**
  - Request Body：无变更
  - Response：
    - `GET /api/chat/timeline`：`items[]` 中同一用户时间线可出现 **多条** `source=assistant` 且可共享 `round_id`（契约未强制返回 `round_id` 字段，DB 层已写入；若客户端需分组可后续扩展响应）
    - `POST /api/chat/send` / `resend`：SSE 契约同 STEP-010（无变更）
  - 变更类型：**行为/语义补充**（DB 行数与 timeline 列表项数相对 STEP-010 前「单条 assistant」增加）
- 数据模型：
  - 表名：`conversation_log`
  - 变更类型：无（仅写入行数语义变化）
  - 字段详情：无新增列；`round_id` 含义更新见上文数据库表结构
- 未完成项记录：
  - 未完成功能：管理后台对话查看页面对「同一 round 多行 assistant」的展示与可读性优化
  - 原因：STEP-011 明确不包含 Admin UI
  - 计划在后续 STEP（产品排期）中处理

### STEP-012：内容安全兼容新结构化输出（§9.1 / §9.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `_execute_llm_bundle` 内 Step5 解析成功且 generation 仍有效后，依次执行：① `_check_inner_monologue_safety` 对 `inner_monologue` 调用 `check_content`，违规则 `logger.warning` 并赋空串（不拦截整轮，避免 Step6 记忆污染）；② `_check_messages_safety` 对 `step5_result.messages` 每条非空 `content` 调用 `check_content`，任一 `is_safe=False` 则 `_mark_pack_failed(..., DELIVERY_STATUS_FAILED_BLOCKED)`、`_resolve_generation_future` 携带 `code=10101`（`ERR_CONTENT_UNSAFE`）并 `return`（不执行 Step5.5）；③ Step5.5 返回非空时对其 `messages` 再跑 `_check_messages_safety`，不通过则 `final_messages = merge_messages_if_exceed(step5_result.messages)` 并打 warning。未改 `content_safety_service.check_content` 规则本身；未对 Step6 产出做安全检测（§9.1）。
- 涉及文件：
  - `backend/constants.py`（修改：新增 `DELIVERY_STATUS_FAILED_BLOCKED = "failed_blocked"`）
  - `backend/routers/chat.py`（修改：新增 `_check_messages_safety`、`_check_inner_monologue_safety`；`_execute_llm_bundle` 插入上述检测逻辑）
  - `tests/test_step012_content_safety.py`（新增：集成 + 辅助函数单测共 10 条）
  - `docs/contract.md`（修改：本开发日志、`POST /api/chat/send` 的 `failed`/语义摘要、`delivery_status` 示例、顶部「最后更新」摘要）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：`conversation_log.delivery_status`（user 行）— 新增合法取值 **`failed_blocked`**（与 `backend/constants.py` 常量 `DELIVERY_STATUS_FAILED_BLOCKED` 一致），表示 **AI 侧** Step5 对外 messages 内容安全拦截导致的整轮失败
- 测试结果：✅ 全部通过（`pytest tests/test_step012_content_safety.py` 10 条；`pytest tests/test_chat.py` 36 条；`pytest tests/test_step5_5.py` 32 条回归）
- 备注：`POST /api/chat/resend` 依赖的 `_open_window_has_bang` 当前仅将 `failed_timeout` / `failed_error` 视为「叹号可重发」；**`failed_blocked` 未纳入**，故纯内容拦截失败时 **可能** 返回 **10107**（无可重发），与超时/解析类叹号行为不完全一致；若产品要求拦截后也可重试，需在后续 STEP 扩展 `_open_window_has_bang` 与前端叹号映射。
- API / 接口契约：
  - 接口名称：`POST /api/chat/send`、`POST /api/chat/resend`（SSE 成功路径）
  - Method + Path：`POST /api/chat/send`、`POST /api/chat/resend`
  - Request Body：无变更（与既有 `ChatSendRequest` / `ChatResendRequest` 一致）
  - Response：
    - 成功（SSE）：事件类型集合不变；**`failed` 事件** 在 Step5 messages 安全拦截时 **`code` 可为 `10101`**（`ERR_CONTENT_UNSAFE`），`message` 为服务端文案（如「内容安全拦截」）
    - 失败（未进入 SSE）：无变更（用户输入侧 **10101** 仍为既有语义）
  - 变更类型：**修改**（SSE `failed` 的 `code` 语义扩展；成功路径内部增加 AI 输出安全分支）
- 数据模型：
  - 表名：`conversation_log`
  - 变更类型：**无新列**；`delivery_status` 字符串枚举在契约与常量层 **新增取值** `failed_blocked`（见上「字段变更」）
  - 字段详情：无新增物理列
- 未完成项记录：
  - 无（`failed_blocked` 与重发叹号是否打通见上「备注」，属产品/后续 STEP 可选）

### STEP-013：Step6 记忆总结 LLM Prompt + JSON 解析（R-MEM-01 / R-MEM-06 / R-MEM-07 / §2.5）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `memory_llm_service.py`，提供 `Step6MemoryOutput`（驼峰 11 字段，与 Step5 snake_case 独立）；`build_step6_prompt()` 按「系统指令 + 当前时间 + 人格 + 关系状态 + 近期历史（不含本轮）+ 本轮完整对话 + 任务说明 + §2.5 完整 few-shot」拼装；本轮「林小梦」侧正文仅拼接 **Step5 解析产出的** `messages[].content`（§2.9.3，不含 Step5.5 润色）；`parse_step6_output()` 用与 Step5 同类的首段 `{...}` 正则提取后 `json.loads`，顶层非对象则失败；字段缺失时除 `InnerMonologue` 默认空串外其余默认字符串「无」；非法 JSON 抛 `Step6ParseError`。多行 `key：value` 中行级合法性（全角冒号）不在本模块校验，由 STEP-014 丢弃非法行。
- 涉及文件：
  - `backend/services/memory_llm_service.py`（新增：`Step6MemoryOutput`、`Step6ParseError`、`parse_step6_output`、`build_step6_prompt`、§2.5 few-shot 常量）
  - `tests/test_memory_llm_service.py`（新增：解析与 Prompt 拼装单测 30 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志条目）
- 字段变更：
  - 新增字段：无（无 DDL；`Step6MemoryOutput` 为内存模型，非 DB 列）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_memory_llm_service.py` 30 条）
- 备注：`build_step6_prompt` / `parse_step6_output` 已由 **STEP-016** 在 `execute_step6` 管线中调用；四路向量 `upsert_step6_vectors`、relationship 写回 `update_relationship_from_step6` 同由 STEP-016 编排调用。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service 与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：—
  - 变更类型：**无**
  - 字段详情：无
- 未完成项记录：
  - 未完成功能：Step6 调用后的 **LLM 统计异步写入**（与主对话 `llm_service` 统计路径对齐，若产品要求单独计数可后续 STEP 增补）
  - 原因：STEP-016 范围不含 Redis `llm_stats` / `llm_response_times` 写入
  - 计划在后续运维/观测 STEP 或统一埋点中处理

### STEP-015：Step6 relationship 标量 + 历史 + Future 槽（R-MEM-05 / §2.8.4）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `relationship_service.py` 的 `RelationshipService` 类中新增 `update_relationship_from_step6(relationship, step6_output, round_id, *, future_time_natural, future_action)` 方法。**6 个标量字段写回**：通过 `_STEP6_FIELD_MAP` 映射 Step6 驼峰字段名到 relationship 表蛇形列名（`UserRealName`→`user_real_name`、`UserHobbyName`→`user_hobby_name`、`UserDescription`→`user_description`、`CharacterPurpose`→`character_purpose`、`CharacterAttitude`→`character_attitude`、`RelationDescription`→`relation_description`）；值非「无」→ `setattr` 覆盖 + 调用 `RelationshipHistoryService.append_history` 写入变更历史（old_value 从当前 relationship 实例读取）；值为「无」→ 跳过该列赋值，保留库内上一轮值。**Future 槽处理**：优先判定 `future_action` 为「无」→ 清空 `future_timestamp` 和 `future_action`；否则当 `future_time_natural` 非「无」时调用 `parse_future_time()` 解析——成功→写入 `future_timestamp`（Unix 时间戳）+ `future_action`，失败→清空 future 字段 + 保留 `proactive_times` 不变 + `logger.warning` 结构化日志。所有变更历史记录 `trigger_source='step6'`，携带 `round_id`。不在本 STEP 范围：`relation_change.delta` 与 growth 的映射（R-BND-09 暂缓）、`proactive_times` 的 +1 逻辑（STEP-022 负责）。
- 涉及文件：
  - `backend/services/relationship_service.py`（修改：新增 `_STEP6_FIELD_MAP` 类属性、`update_relationship_from_step6` 方法；新增 import `RelationshipHistoryService`、`parse_future_time`、`Optional`）
  - `tests/test_step015_relationship_step6.py`（新增：标量写回+历史+Future 槽单测 11 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-013 未完成项更新）
- 字段变更：
  - 新增字段：无（无 DDL；所需列已由 STEP-001 创建）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step015_relationship_step6.py` 11 条）
- 备注：`update_relationship_from_step6` 已由 **STEP-016** `execute_step6` 在独立 DB session 中调用并 `commit`。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service 方法与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：`relationship`（已有）、`relationship_change_history`（已有）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无
- 未完成项记录：
  - ~~`proactive_times` +1（STEP-022）~~ → ✅ 已由 STEP-022 完成
  - 未完成功能：`relation_change.delta` 与 growth 的映射（R-BND-09）
  - 原因：STEP-015 范围仅限 Service 方法交付
  - 计划在 R-BND-09 相关 STEP 中处理

### STEP-014：Step6 DashVector 四路向量写入（R-MEM-04）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `memory_llm_service.py` 中实现 `parse_kv_lines(text)`：按 `\n` 拆行，每行按**首处**全角冒号 `：` 分割为 `(key, value)`，strip 后 key 或 value 为空、或行内无全角冒号的行丢弃。`upsert_step6_vectors(output: Step6MemoryOutput, user_id: int)` 遍历四类字段与 `constants` 中 `MEMORY_TYPE_*` 映射：`CharacterPublicSettings`→`character_global`、`CharacterPrivateSettings`→`character_private`、`CharacterKnowledges`→`character_knowledge`、`UserSettings`→`user`；字段值等于字符串「无」（strip 后）则整路跳过；否则对合法行生成 `doc_id="{memory_type}:{stable_key}:{user_id或空}"`（无 user 后缀时第三段为空字符串，形如 `character_global:外貌-体态:`）；对 **value** 调用 `embedding_service.get_embedding`，向量非空则 `dashvector_client.upsert(doc_id, vector, fields, memory_type)`，其中 `fields.content` 为「key：value」整行文本；`character_private` 与 `user` 在 `fields` 中附带 `user_id`（整数），另两类不附带；`dashvector_client` 合并 `type=memory_type`（与 STEP-003 一致）。同 key 同 type（及同 user 作用域）再次 upsert 覆盖；本轮未再出现的 key **不**自动删除。返回 `dict[str, int]` 为各 `memory_type` 成功写入条数计数。
- 涉及文件：
  - `backend/services/memory_llm_service.py`（修改：新增 `parse_kv_lines`、`_build_doc_id`、`upsert_step6_vectors` 及常量映射；依赖 `embedding_service`、`dashvector_client`）
  - `tests/test_step6_vector_upsert.py`（新增：解析、doc_id、四路写入 mock 单测 22 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-013 备注与未完成项）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step6_vector_upsert.py` 22 条；回归 `tests/test_memory_llm_service.py` 30 条）
- 备注：`upsert_step6_vectors` 已由 **STEP-016** `execute_step6` 调用；管理后台知识库 CRUD 见 **STEP-027**；`memory` 表 `dashvector_id` 与 Step6 行级 doc_id 无强制关联（Step6 使用稳定 doc_id 策略）。
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部异步函数与单测，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**
- 数据模型：
  - 表名 / 集合名：**DashVector 集合**（配置项 `collection_name`，与既有向量库配置一致；无新集合名）
  - 变更类型：**运行时文档约定**（非 MySQL 迁移）
  - 字段详情：
    - 文档 `id`（即 upsert 的 `doc_id`）：字符串，`{memory_type}:{stable_key}:{user_id或空}`，`stable_key` 为全角冒号前的 key 原文
    - 向量字段 `vector`：与 `text-embedding-v3` 维度一致（与既有 `embedding_service` 一致）
    - `fields.type`：四类之一 `character_global` / `character_private` / `character_knowledge` / `user`（由客户端合并写入，与 STEP-003 检索 filter 一致）
    - `fields.content`：字符串，格式为「key：value」（全角冒号，与解析行一致）
    - `fields.user_id`：整数，**仅** `character_private`、`user` 两类写入；`character_global`、`character_knowledge` **省略**该字段
- 未完成项记录：
  - 无（对话链路调用已由 **STEP-016** 完成）

### STEP-016：Step6 异步入队 + M2 半异步 + 重试（§2.8.4 / §2.9.3）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`Step6Snapshot` 在 `_execute_llm_bundle` 内于 Step5 解析成功、内容安全通过、`_persist_bundle_success` 落库之后构建：`step6_messages = merge_messages_if_exceed(step5_result.messages)`（≤5，CP1，**不含** Step5.5 润色）；`asyncio.create_task(execute_step6(snapshot))` 入队，**不 await**，保证 `_resolve_generation_future` / SSE 不被 Step6 阻塞（M2）；`execute_step6` 内整段管线失败时 `asyncio.sleep(0.5)` 后 **再执行 1 次**（共 2 次），仍失败则 `logger.error` 含 `exc_info` 后返回，**允许不落库**；快照含 `persona`（Redis `active_config:persona`，空则 `DEFAULT_PERSONA`）、关系等级名、relationship 六列读快照、近期对话 `{role,content}`、Step5 `future`、打包用户原文 `bundled`；`_step6_pipeline`：`build_step6_prompt` → `llm_client.chat_sync`（**45s**，模块常量 `_STEP6_LLM_TIMEOUT_SEC`，固定值非环境变量）→ `parse_step6_output` → `upsert_step6_vectors` → 新开 `async_session_maker` 加载 `Relationship` → `update_relationship_from_step6` → `commit`；无 `relationship` 行则 warning 跳过标量更新；入队构建 try/except 仅日志。SSE 事件格式**未**改。
- 涉及文件：
  - `backend/services/step6_orchestrator.py`（新增：`Step6Snapshot`、`execute_step6`、`_ConvProxy`、`_step6_pipeline`）
  - `backend/routers/chat.py`（修改：导入 `DEFAULT_PERSONA`、`REDIS_KEY_PERSONA`、`Step6Snapshot`、`execute_step6`；闭环成功后 `create_task(execute_step6)`）
  - `tests/test_step016_step6_orchestrator.py`（新增：6 条单测）
  - `docs/contract.md`（修改：顶部摘要、H5 对话语义、STEP-006/008/013/014/015 备注与未完成项、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL；无新 HTTP 字段）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step016_step6_orchestrator.py` 6 条；回归 `tests/test_merge_messages.py` + `test_step016` 共 22 条）
- 备注：未实现 **STEP-028** 管理后台 Step6 失败监控页；Step6 **未**写入与主对话相同的 Redis `llm_stats` / `llm_response_times` 统计（与 `.cursorrules` 全量 LLM 统计口径可后续对齐）；退避固定 **500ms**（需求区间 200ms～1s 取默认中值）。
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由；`POST /api/chat/send` / `resend` 的 SSE 事件集合不变）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（服务端后台异步行为补充，见 H5 模块「语义摘要」）
- 数据模型：
  - 表名 / 集合名：`relationship`、`relationship_change_history`、DashVector 文档（与 STEP-014/015 一致）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 未完成功能：管理后台 Step6 失败可观测性（**STEP-028**）；Step6 LLM 与主链一致的 **Redis LLM 统计**写入（若产品要求）
  - 原因：本 STEP 明确排除管理端监控；统计未纳入范围
  - 计划在 STEP-028 或统一观测 STEP 中处理

### STEP-022：proactive_times 计数/清零 + 频控调整（R-FUT-03 / §2.2 变更 8.2）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：**proactive_times 清零**：`chat.py` `POST /api/chat/send` 入口在用户消息落库 commit 后、防抖调度前，独立 session 查询 `relationship` 表，若 `proactive_times != 0` 则置 0 并 commit，异常仅日志不阻断主链路。**频控参数调整（§2.2 变更 8.2）**：`agent_service.py` `check_and_trigger` 方法中每日上限从 2 调整为 8（含 Future 槽消费计入），两次间隔从 `timedelta(hours=6)` 调整为 `timedelta(minutes=30)`。**proactive_times +1**：`generate_and_save_message` 在 Redis 计数器 INCR 后，独立 session 加载 `relationship`，若 `proactive_times < 3` 则 +1 并 commit（上限保护 3），异常仅日志不阻断。**Future 槽计入计数器**：新增 `increment_agent_count_for_future(user_id)` 方法，对 `agent:count:{user_id}:{date}` 执行 INCR + EXPIRE（TTL 到日末），供 STEP-023 Future 槽消费成功后调用。**30 天无活动清零**：新增 `reset_inactive_proactive_times()` 方法，查询 `proactive_times > 0` 且 `last_interaction_at` 为 NULL 或超过 30 天的 relationship 记录，将 `proactive_times` 置 0 + 清空 `future_timestamp`/`future_action`；`scheduler.py` 注册每日凌晨 1:00 UTC CronTrigger 执行该任务。**Agent 扫描间隔调整**：`scheduler.py` 中 Agent 主动消息扫描从 `IntervalTrigger(hours=6)` 调整为 `IntervalTrigger(minutes=30)`，与频控最小间隔匹配。
- 涉及文件：
  - `backend/routers/chat.py`（修改：`chat_send` 函数新增 proactive_times 清零逻辑块）
  - `backend/services/agent_service.py`（修改：`check_and_trigger` 频控参数 2→8、6h→30min；`generate_and_save_message` 新增 proactive_times +1 逻辑；新增 `increment_agent_count_for_future` 方法；新增 `reset_inactive_proactive_times` 方法）
  - `backend/tasks/scheduler.py`（修改：Agent 扫描间隔 6h→30min；新增 `_run_inactive_reset` 包装器 + `inactive_proactive_reset_task` CronTrigger 注册）
  - `tests/test_step022_proactive_times.py`（新增：proactive_times 计数/清零 + 频控参数单测 18 条）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志）
- 字段变更：
  - 新增字段：无（`proactive_times` 已在 STEP-001 添加）
  - 修改字段：无
- 测试结果：✅ 全部 18 条通过（`pytest tests/test_step022_proactive_times.py`：场景1 用户发消息清零 3 条、场景2 主动消息后+1 3 条、场景3 概率公式验证 3 条、频控参数边界 4 条、30 天无活动清零 4 条、Future 槽计入计数器 1 条）
- API / 接口契约：
  - 接口名称：`POST /api/chat/send`（已有接口，新增内部副作用）
  - Method + Path：POST /api/chat/send
  - Request Body：无变更
  - Response：无变更
  - 变更类型：**内部行为变更**（无对外 HTTP 契约变更，仅新增内部 proactive_times 清零副作用）
- 数据模型：
  - 表名 / 集合名：`relationship`（已有表，读写 `proactive_times` / `future_timestamp` / `future_action`）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - ~~未完成功能：Future 槽消费轮询（STEP-023）~~ → ✅ 已由 **STEP-023** 完成
  - ~~未完成功能：Step8 子链路专用 LLM 调用与编排（STEP-024）~~ → ✅ 已由 **STEP-024** 完成

### STEP-023：Future 槽消费轮询 Handler（R-AGT-02 / Step8 轮询）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：新增 `FutureSlotHandler`（`future_handler.py`），由 APScheduler 每 **60 秒** 执行 `scan_and_consume()`：联表 `relationship` + `users`，筛选 **4 条件同时成立** 的到期槽（`future_timestamp` 非空、≤当前 Unix 秒、>当前时间−1800、用户未封禁）。单用户 `_consume_one()`：**始终**检查 Redis `agent:blacklist:{user_id}`；**不**走 8 次/天与 30 分钟间隔频控；调用 `calculate_action_score(user_id, TriggerType.FUTURE)`，评分 **<6** 或黑名单则 **仅清空** `future_timestamp`/`future_action` 并打日志。通过则调用 `execute_step8_subchain(user_id, future_action)` 执行 Step8 子链路（已由 STEP-024 实现）；成功后再 `_on_consume_success`：**清空槽**、`proactive_times` **+1**（上限 3）、`increment_agent_count_for_future` 计入当日 `agent:count`。`cleanup_expired_slots()` 清理 **超出 30 分钟窗口** 的残留槽位。路 B：`check_and_trigger` 在频控前若 `_has_pending_future_slot`（`future_timestamp > now`）则 **跳过** 定时扫描写入。
- 涉及文件：
  - `backend/services/future_handler.py`（新增：`FutureSlotHandler` / `future_handler` 单例）
  - `backend/tasks/scheduler.py`（修改：新增 `_run_future_slot_scan`、`future_slot_scan_task` IntervalTrigger 60s）
  - `backend/services/agent_service.py`（修改：`check_and_trigger` 路 B 优先级保护；`_has_pending_future_slot`；`TRIGGER_WEIGHTS` / `AGENT_FALLBACK_REPLIES` 增加 FUTURE；`import time`）
  - `backend/models/agent_message.py`（修改：`TriggerType.FUTURE`）
  - `tests/test_step023_future_handler.py`（新增：14 条单测）
  - `docs/contract.md`（修改：`agent_message.trigger_type` 说明、顶部摘要、本开发日志、STEP-022 未完成项）
- 字段变更：
  - 新增字段：无（无 DDL）
  - 修改字段：`agent_message.trigger_type` — 允许取值扩展为含 **`FUTURE`**（仍为 `String(10)`，ORM 层 `TriggerType` 常量）
- 测试结果：✅ 全部通过（`pytest tests/test_step023_future_handler.py` 14 条）
- 备注：Future 消费成功后已由 **STEP-024** 实现的 `execute_step8_subchain()` 完成 Step8 专用子链路。轮询周期取 **60 秒**（需求「参考每秒」的折中，避免 DB 压力过大）。
- API / 接口契约：
  - 接口名称：无新增对外 HTTP 接口（仅后台定时任务）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（运行时行为：定时扫描 Redis + MySQL）
- 数据模型：
  - 表名 / 集合名：`agent_message`（`trigger_type` 语义扩展）、`relationship`（读写 Future 槽与 `proactive_times`）、Redis `agent:count:{user_id}:{date}`、`agent:blacklist:{user_id}`
  - 变更类型：**取值约定扩展**（无表结构 DDL）
  - 字段详情：无新列；`trigger_type` 新增合法枚举值 `FUTURE`
- 未完成项记录：
  - ~~未完成功能：Step8 子链路 **专用** LLM 调用与编排（STEP-024）~~ → ✅ 已由 **STEP-024** 完成
  - 未完成功能：管理后台 Future/Agent 监控页（若需求单独立项）

---

### STEP-024：Step8 子链路（R-L1L3-12 / §8.3 子链路编排）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- > ⚠️ 本条为 2026-05-05 历史纪要，其中 Step1.5 入参描述（`future.action` 替代 `last_user_text`）已被顶部「2026-05-30 摘要」更新为 `rewrite_input`，**当前实现以摘要为准**。
- 实现说明：新增 `step8_subchain.py`，实现 Future 槽到期触发的主动消息子链路 `execute_step8_subchain(user_id, future_action)`，复用主链 Step 变体：**Step1** 在单个 `async with async_session_maker()` 会话内 **顺序** `await` `_get_recent_conversations`（最多 20 条、反转后取末 10 轮参与下游）、`_get_relationship`、`_get_emotion_context`（数据源与主链相同；**不得**对同一 `AsyncSession` 使用 `asyncio.gather` 并行执行多条语句，否则触发 SQLAlchemy 异步会话状态错误）；**Step1.5 变体** 调用 `execute_query_rewrite(source="step8")`，输入用 `future.action` 替代 `last_user_text`，降级路径用 `future.action` 通过 `embedding_service.get_embedding` 生成单 Embedding（R-L1L3-12）；**Step2** 完全复用 `execute_multi_vector_retrieval()`；**Step3 变体** 调用 `PromptBuilder.build_step8_prompt()`，将 9 模块中的【用户消息】替换为【主动发起】模块（含 `future.action` 摘要，指导 LLM 以预约内容自然开启对话）；**Step5** 完全复用 `llm_service.chat_with_step5_parse()`，含内容安全检查（`check_content`）与人格偏离检测（`_check_persona_risk` 关键词扫描，偏离时回退默认回复写入 `agent_message`）；**Step5.5** 调用 `execute_step5_5(gate_a_override=0.03)` 配置较低触发概率（主链 0.12 vs Step8 0.03）；**产出** 写入 `agent_message` 表（`trigger_type=FUTURE`，不走 SSE），`sort_seq` 通过 `allocate_sort_seq` 分配；**Step6** `asyncio.create_task(execute_step6(snapshot))` 异步入队记忆总结（不阻塞）；**衰减门控** `_decay_gate_and_update`：`proactive_times` +1（上限 3），以 `0.15^(proactive_times+1)` 概率从 Step5 输出解析 future 字段并写入下一轮 Future 预约。边界处理：`future_action` 为空/None/纯空白→日志 + 返回 False。`prompt_builder.py` 新增 `_build_proactive_input(future_action, limits)` 和 `build_step8_prompt(user_id, ...)` 两个方法。`step5_5_service.py` `should_trigger_step5_5()` / `execute_step5_5()` 新增 `gate_a_override` 可选参数支持外部覆盖门闩 A 概率。`future_handler.py` `_consume_one()` 中 `generate_and_save_message(FUTURE)` 占位替换为 `execute_step8_subchain(user_id, future_action)`。**维护（2026-05-07）**：修正 Step1 装载实现描述（顺序查询替代错误的同 session 并行 gather）；不改变对外契约。
- 涉及文件：
  - `backend/services/step8_subchain.py`（新增：`execute_step8_subchain`、`_get_recent_conversations`、`_get_relationship`、`_get_emotion_context`、`_build_step8_round_context`、`_check_persona_risk`、`_fallback_write_agent_message`、`_decay_gate_and_update`；常量 `STEP8_GATE_A_PROBABILITY=0.03`、`DECAY_BASE=0.15`、`PROACTIVE_TIMES_CAP=3`、`STEP8_FALLBACK_REPLY`、`PERSONA_RISK_KEYWORDS`）
  - `backend/services/prompt_builder.py`（修改：`PromptBuilder` 新增 `_build_proactive_input()` 和 `build_step8_prompt()` 方法）
  - `backend/services/step5_5_service.py`（修改：`should_trigger_step5_5()` 和 `execute_step5_5()` 新增 `gate_a_override` 参数）
  - `backend/services/future_handler.py`（修改：`_consume_one()` 中调用替换为 `execute_step8_subchain`；新增 `from backend.services.step8_subchain import execute_step8_subchain`）
  - `tests/test_step024_step8_subchain.py`（新增：10 条单测）
  - `tests/test_step023_future_handler.py`（修改：2 条测试适配 `execute_step8_subchain` mock）
  - `docs/contract.md`（修改：顶部摘要、STEP-022/STEP-023 未完成项更新、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step024_step8_subchain.py` 10 条：场景1 完整子链路执行+agent_message 写入、场景2 Step1.5 失败降级用 future.action Embedding、场景3 proactive_times=3 衰减概率≈0.05%、衰减门控命中写入 Future、衰减门控未命中不写入、future_action 空/None/纯空白 3 条边界、Step5 失败返回 False、proactive_times 上限不超过 3）；既有测试 `test_step023_future_handler.py` 14 条 + `test_step5_5.py` 32 条 + `test_prompt_builder.py` 30 条全部通过（共 86 条无回归）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由，子链路为内部后台任务）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（运行时行为：Future 槽到期后内部触发）
- 数据模型：
  - 表名 / 集合名：`agent_message`（写入 `trigger_type=FUTURE` 的主动消息）、`relationship`（读写 `proactive_times`/`future_timestamp`/`future_action`）
  - 变更类型：**运行时写入**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-021：Step3 Prompt 新增模块 + Token 裁剪（R-L1L3-19）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- > ⚠️ 本条为 2026-05-05 历史纪要；**2026-05-30** 起主链在 recent_chat 与 user_input 之间新增 **`user_nickname` 模块**（有称呼时 +1 段）、relationship 删除称呼行，**以顶部「2026-05-30 摘要」为准**。
- 实现说明：`prompt_builder.py` 重构为 9 模块结构拼装（R-L1L3-19）。新增模块 A「角色设定与知识」（`_build_character_knowledge_prompt()`）：合并 Step2 的 `character_global` + `character_private` 结果标记为「角色设定」，`character_knowledge` 结果标记为「角色知识」，所有条目按 DashVector score 降序排列，超过 `character_knowledge` Token 上限时从低分端逐条移除（不重新计算 Embedding）；模块 A 插入在 Persona 之后、Relationship 之前。新增模块 B「时间与活动状态」（原 `_build_time_prompt()`）：形式上归入 `time_activity` 模块键，保持在 Emotion 之后 Recent Chat 之前位置，空活动描述时跳过活动行。`MAX_TOTAL_TOKENS` 从 5200 调整为 7373（基线 ×1.8）；`MODULE_TOKEN_LIMITS` 全部更新为 R-L1L3-19 指定默认值（system 720 / persona 1080 / character_knowledge 600 / relationship 360 / memory 900 / emotion 270 / time_activity 80 / recent_chat 1800 / user_input 900）。新增 `_load_token_limits()` 方法：从 `admin_config_service.get_active_config("prompt_token_config")` 热加载 JSON 配置（期望格式 `{"max_total": 7373, "system": 720, ...}`），仅覆盖存在且 > 0 的键，其余回退默认值，异常时全部回退默认值。`_trim_to_budget()` 实现 5 级裁剪优先级引擎：①`recent_chat` 从最早对话逐条删除 → ②`memory` 从末尾（最低分）逐条删除 → ③`character_knowledge`（模块 A）按 score 从低到高逐条删除 → ④`relationship` 扩展部分移除（调用 `_build_relationship_prompt_core()` 仅保留核心等级/语气/沉默修正）→ ⑤`time_activity`（模块 B）整块移除；System / Persona 绝不裁剪。`_build_memory_prompt()` 扩展为兼容 Step2 检索结果（dict 列表，含 `content`/`score`）和 Memory ORM 实例两种格式。`build_chat_prompt()` 新增 `retrieval_results: dict | None` 参数，接收 `MultiVectorRetrievalResult.format_for_prompt()` 输出的四路检索结果 dict。所有模块构建方法统一接收 `limits` 参数（从热配加载），不再硬编码读取全局常量。`chat.py` `_execute_llm_bundle` 中：`memories` 参数改为直接传递 `memories_raw`（Step2 user_results dict 列表），不再通过 `_MemoryProxy` 包装；新增 `retrieval_for_prompt = retrieval_result.format_for_prompt()` 并传递给 `build_chat_prompt`。`build_active_message_prompt()` 保持向后兼容（仍接受 Memory ORM 实例，不使用模块 A/B）。
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：常量 `MAX_TOTAL_TOKENS`/`MODULE_TOKEN_LIMITS` 更新；新增 `TRIM_PRIORITY`/`MODULE_ORDER`/`_PROMPT_TOKEN_CONFIG_KEY` 常量；新增 `admin_config_service` 导入；`PromptBuilder` 类重构——新增 `_load_token_limits()`/`_build_character_knowledge_prompt()`/`_merge_character_knowledge_items()`/`_render_character_knowledge()`/`_build_relationship_prompt_core()`/`_trim_to_budget()` 方法；`build_chat_prompt()` 新增 `retrieval_results` 参数、9 模块 dict 拼装流程；所有 `_build_*` 方法新增 `limits` 参数；删除旧 `_check_token_limit()` 方法）
  - `backend/routers/chat.py`（修改：`_execute_llm_bundle` 中删除 `_MemoryProxy` 类及包装逻辑，改为直接传 `memories_raw` + `retrieval_for_prompt`）
  - `tests/test_prompt_builder.py`（修改：30 条测试含新增 STEP-021 场景：全量注入无裁剪、总 Token 超限裁剪优先级、模块 A score 裁剪、热配覆盖默认值、9 模块顺序验证、模块 A 空结果跳过、relationship 扩展裁剪、Step2 dict 格式记忆、默认 Token 上限验证）
  - `docs/contract.md`（修改：顶部「最后更新」摘要、本开发日志、STEP-020 未完成项关闭）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 admin_config 键：`prompt_token_config`（JSON，`{"max_total": 7373, "system": 720, "persona": 1080, "character_knowledge": 600, "relationship": 360, "memory": 900, "emotion": 270, "time_activity": 80, "recent_chat": 1800, "user_input": 900}`，由管理后台 STEP-025 创建的配置页发布）
- 测试结果：✅ 全部通过（`pytest tests/test_prompt_builder.py` 30 条：含场景1 全量注入无裁剪、场景2 超限先裁 recent_chat 再裁 memory、场景3 模块 A 超 600 按 score 裁剪、边界热配 recent_chat=1000 使用配置值、9 模块顺序/8 模块顺序（无模块 A）、模块 A 内容注入/空结果跳过、Step2 dict 格式记忆、relationship 扩展裁剪核心、Token 默认值验证、原有 STEP-004/STEP-017 测试全量保留）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部 Prompt 拼装改造）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取 `prompt_token_config`，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 管理后台「Prompt Token 配置」页创建与发布流程（STEP-025）

---

### STEP-020：Step2 多路向量检索（R-L1L3-10 / R-L1L3-17 / R-L1L3-18 / R-L1L3-21）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- > ⚠️ 本条为 2026-05-05 历史纪要，已被顶部「2026-05-30 摘要」更新（per-route 主路 + 2.5 补充路、`character_private` 独立 Embedding、`skipped_routes`、按路容错），**当前实现以摘要为准**。
- 实现说明：新增 `multi_vector_retrieval_service.py`，实现 Step2 多路向量检索。`MultiVectorRetrievalResult` dataclass 承载 4 路检索结果（`character_global_results` / `character_private_results` / `character_knowledge_results` / `user_results`），附带 `top_k` / `threshold` / `is_fallback` 元数据，提供 `all_results`（去重合并按 score 降序）、`user_memory_results`（兼容旧 `memories_raw` 格式）、`format_for_prompt`（分路 dict）属性。`execute_multi_vector_retrieval()` 主入口：正常路径（Step1.5 成功）阶段① `asyncio.gather` 并行调用 `embedding_service.get_embedding` 生成 3 个 Embedding（CharacterGlobal / CharacterKnowledge / UserProfile），阶段② `asyncio.gather` 并行执行 4 次 `dashvector_client.search`（`character_global` 无 user_id + `character_private` 有 user_id 复用 CharacterGlobal Embedding + `character_knowledge` 无 user_id + `user` 有 user_id）；降级路径（Step1.5 失败）用 `fallback_embedding` 直接执行全部 4 路检索（R-L1L3-12），过滤条件不变。从 `admin_config_service.get_active_config("vector_retrieval_config")` 热加载 TopK 和阈值（R-L1L3-17），期望 JSON `{"top_k": 3, "threshold": 0.7}`，无配置或解析失败时回退默认值。`chat.py` `_execute_llm_bundle` 中：在 `round_context` 构建后新增 Step1.5（`execute_query_rewrite`）+ Step2（`execute_multi_vector_retrieval`）调用，`memories_raw` 取自 `retrieval_result.user_memory_results`，`memories` 取自 `_MemoryProxy` 包装后的列表；删除旧 `user_embedding = await _get_embedding(last_user_text)` 及关联 `_search_memories` 调用（R-L1L3-21）；`_persona_text` 在 Step1.5 阶段预获取后复用至 Step6 快照构建，消除重复 Redis `GET`。
- 涉及文件：
  - `backend/services/multi_vector_retrieval_service.py`（新增：`MultiVectorRetrievalResult`、`_load_retrieval_config`、`_phase1_generate_embeddings`、`_phase2_parallel_search`、`_fallback_search`、`execute_multi_vector_retrieval`）
  - `backend/routers/chat.py`（修改：新增 `execute_multi_vector_retrieval` / `execute_query_rewrite` 导入；`_execute_llm_bundle` 中删除旧 `user_embedding` / `_search_memories` 代码，新增 Step1.5 + Step2 调用链，`_persona_text` 提前获取复用至 Step6）
  - `tests/test_multi_vector_retrieval_service.py`（新增：6 条单测）
  - `docs/contract.md`（修改：顶部摘要、本开发日志、STEP-019 未完成项更新）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 admin_config 键：`vector_retrieval_config`（JSON，`{"top_k": 3, "threshold": 0.7}`，由管理后台 STEP-025 创建的配置页发布）
- 测试结果：✅ 全部通过（`pytest tests/test_multi_vector_retrieval_service.py` 6 条：场景1 正常 3 Embedding+4 检索 ≤12 条、场景2 降级 1 Embedding+4 检索、场景2b 降级无 Embedding 返回空、场景3 部分路 0 命中、边界热配 TopK=5 覆盖默认、无配置回退默认值）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部数据流改造）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取 `vector_retrieval_config`，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - ~~Prompt 拼装层消费 4 路检索结果（STEP-021）~~ → ✅ 已由 STEP-021 完成
  - 管理后台「向量召回配置」页创建与发布流程（STEP-025）

---

### STEP-019：Step1.5 查询重写 LLM（R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14）
- 完成时间：2026-05-05（**2026-05-08** 调整超时与业务层重试策略，见实现说明）
- 状态：✅ 已完成
- > ⚠️ 本条为 2026-05-05 历史纪要，已被顶部「2026-05-30 摘要」更新（`QueryRewriteOutput` 扩为 13 字段、`rewrite_input` 改名、C1 四路全「无」合法成功态），**当前实现以摘要为准**。
- 实现说明：新增 `query_rewrite_service.py`，实现 Step1.5 查询重写 LLM 调用。`QueryRewriteOutput` Pydantic 模型定义 7 字段输出（`InnerMonologue` + `CharacterGlobalQueryQuestion`/`Keywords` + `CharacterKnowledgeQueryQuestion`/`Keywords` + `UserProfileQueryQuestion`/`Keywords`，字段名与 R-L1L3-09 严格一致）；`QueryRewriteResult` dataclass 作为返回值（`success`=True 时 `output` 非空，`success`=False 时 `fallback_embedding` 非空为降级成功）。`_build_step1_5_prompt()` 按需求文档 Step1.5 Prompt 结构拼装 7 模块（系统指令、时间活动、人格、关系、近期对话、用户消息、任务含完整输出 JSON Schema），复用 STEP-018 的 `round_context` 预计算值（R-L1L3-14：共用已截取的 `recent_10`，不新增 DB 查询），兼容 dict 和 ORM 实例两种对话格式。`execute_query_rewrite()` 主入口：**timeout=45s**（`_STEP1_5_TIMEOUT_SEC`）；**业务层不重试**（整轮「LLM + 解析」仅 1 次，失败后立即 `_fallback_with_embedding()`）；底层经 `llm_client.chat_sync`，**单次 HTTP 超时同 45s**，内层仍最多 **3 次** POST + 1s/2s 退避（`LLM_MAX_RETRIES`）；`_parse_query_rewrite_output()` 用与 Step5/Step6 同类的首段 `{...}` 正则提取后 `json.loads`，校验至少一组 QueryQuestion 非空；降级（R-L1L3-12）：用 `last_user_text`（Step8 子链路为 `future.action`）通过 `embedding_service.get_embedding` 生成单 Embedding 作为 Step2 全部 4 路检索的统一 query，不触发叹号，用户无感知。结构化日志含 `user_id`、`elapsed`、`error`、`source`（区分主链 `main` / Step8 子链路 `step8`）。`InnerMonologue` 不落库、不返前端。**与整链等待**：Step1.5 为 `_execute_llm_bundle` 内首段 LLM 子调用之一，其 `chat_sync` 最坏耗时可 **单独超过** `_BUNDLE_WAIT_TIMEOUT_SEC`（120s），与 **SSE `wait_for`** 的关系见 **POST /api/chat/send** 与 **「部署与网关（对话 SSE）」**。
- 涉及文件：
  - `backend/services/query_rewrite_service.py`（新增：`QueryRewriteOutput`、`QueryRewriteResult`、`_build_step1_5_prompt`、`_parse_query_rewrite_output`、`execute_query_rewrite`、`_fallback_with_embedding`）
  - `tests/test_query_rewrite_service.py`（新增：7 条单测，mock `llm_client.chat_sync` / `embedding_service.get_embedding`）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_query_rewrite_service.py` 7 条：场景1 正常返回三组 QueryQuestion/Keywords、场景2 LLM 超时后降级与结构化日志、场景3 InnerMonologue 仅 `output` 内存字段、边界非法 JSON 一次失败后降级、`_parse_query_rewrite_output` 与 `_build_step1_5_prompt` 纯函数）
- API / 接口契约：
  - 接口名称：无（本 STEP 仅新增内部 Service，未暴露新 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部新增查询重写层）
- 数据模型：
  - 表名 / 集合名：无（不涉及 DB 变更）
  - 变更类型：**无**
  - 字段详情：无新列
- 未完成项记录：
  - ~~`_execute_llm_bundle` 接入 `execute_query_rewrite` 调用~~ → **已在 STEP-020 中完成**
  - 管理后台 Step1.5 失败记录查询（R-L1L3-13，STEP-028 或统一观测 STEP 中处理）

---

### STEP-018：Step1 并行装载扩展（R-L1L3-01 / R-L1L3-06）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：在 `_execute_llm_bundle` 的 LLM 打包路径中，于 `_get_relationship` 读取之后新增 `_build_round_context()` 辅助函数构建本轮内存上下文 dict，包含：`time_description`（调用 `_generate_time_description()`）、`activity_description`（调用 `get_activity_description()`）、6 个关系扩展字段（`relation_description` / `user_real_name` / `user_hobby_name` / `user_description` / `character_purpose` / `character_attitude`，NULL 时用占位文案）、`level` / `level_name` / `silence_days`；`round_context` 在 Step5.5（`execute_step5_5` 调用处）和 Step6（`Step6Snapshot` 构建处）共用同一份，不重复 SELECT；`POST /api/chat/send` 的 `asyncio.gather` 中移除 `_get_relationship`（R-L1L3-01：无下游消费的重复 SELECT）；`build_chat_prompt` 新增可选 `round_context` 参数，`_build_time_prompt` 优先使用预计算的时间/活动描述值，避免重复生成/Redis 读取
- 涉及文件：
  - `backend/routers/chat.py`（修改：新增 `from datetime import datetime`；新增 `_generate_time_description` / `get_activity_description` 导入；新增 `_build_round_context()` 辅助函数；`_execute_llm_bundle` 中构建 `round_context` 并传入 `build_chat_prompt`、Step5.5、Step6 调用处；`chat_send` 的 gather 移除 `_get_relationship`）
  - `backend/services/prompt_builder.py`（修改：`build_chat_prompt` 新增 `round_context: dict | None = None` 参数并传递给 `_build_time_prompt`；`_build_time_prompt` 新增 `round_context` 关键字参数，有值时跳过 `_generate_time_description()` / `get_activity_description()` 调用）
  - `tests/test_step018_round_context.py`（新增：10 条单测覆盖扩展字段有值、全 NULL 占位、时间/活动注入、新用户无 relationship、gather 静态检查、round_context 键完整性）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
- 测试结果：✅ 全部通过（`pytest tests/test_step018_round_context.py` 10 条；`pytest tests/test_prompt_builder.py tests/test_chat.py` 55 条回归通过）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅对话链路内部数据流优化）
- 数据模型：
  - 表名 / 集合名：`relationship`（仅读取已有字段，无 DDL）
  - 变更类型：**无**
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-017：时间描述串 + 活动描述串生成（R-L1L3-11）
- 完成时间：2026-05-05
- 状态：✅ 已完成
- 实现说明：`_generate_time_description()` 已在 STEP-004 实现（纯代码按周几+时段+小时:分钟生成自然语言）；本 STEP 新增 `get_activity_description()` 异步函数，从 Redis `active_config:activity_schedule` 读取静态 JSON（格式如 `{"14-18": "她在写代码"}`），按当前小时段匹配，未配置/未命中/解析失败→空字符串；`_build_time_prompt()` 改为 async，活动描述非空时追加在时间描述后一行，空串时跳过
- 涉及文件：
  - `backend/services/prompt_builder.py`（修改：新增 `import json`；新增模块级 `get_activity_description()` 异步函数；`_build_time_prompt()` 同步→异步，条件注入活动描述；`build_chat_prompt()` 对应 await）
  - `tests/test_prompt_builder.py`（修改：新增 9 条测试用例，`_build_prompt` 辅助函数增加 `get_activity_description` mock）
  - `docs/contract.md`（修改：顶部摘要、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL）
  - 修改字段：无
  - 新增 Redis 缓存键：`active_config:activity_schedule`（JSON，由管理后台通用 admin_config 编辑发布）
- 测试结果：✅ 全部通过（`pytest tests/test_prompt_builder.py` 19 条）
- admin_config 配置格式：`config_key = "activity_schedule"`，`config_value` 为 JSON 对象，key 为小时范围 `"start-end"`（start <= hour < end），value 为活动描述文案字符串
- 备注：不创建管理后台专属页面（复用现有 admin_config 通用编辑）；不实现完整活动计划功能（TD-021 技术债）
- API / 接口契约：
  - 接口名称：无（未新增/修改对外 HTTP 路由）
  - Method + Path：—
  - Request Body：—
  - Response：—
  - 变更类型：**无**（仅 Prompt 拼装层内部变更）
- 数据模型：
  - 表名 / 集合名：`admin_config`（仅读取，无 DDL）
  - 变更类型：**运行时读取**（无 DDL）
  - 字段详情：无新列
- 未完成项记录：
  - 无

---

### STEP-025：管理后台向量召回 + Prompt Token 热配置（R-L1L3-17 / R-L1L3-19 / §6）
- 完成时间：2026-05-07
- 状态：✅ 已完成
- 实现说明：新增 `GET|PUT /api/admin/configs/vector_retrieval_config` 与 `GET|PUT /api/admin/configs/prompt_token_config`；**PUT 语义为部分字段 PATCH**：请求体仅含待更新键（`exclude_unset` + 剔除 `null`），与库中当前生效 JSON 及代码默认值合并后调用 `admin_config_service.publish_config`（MySQL 多版本行 + Redis `active_config:{config_key}` + `publish_monitor:{key}`）；鉴权 `super_admin` + `ai_trainer`；`GET` 返回合并后的完整生效视图供表单展示；管理端单页双 Tab `vector-token-config.html` 保存时仅提交相对首屏快照有变化的字段；审计沿用 `publish_config` 内 `log_operation` → `admin_operation_log`（`module=ai_config`，`action=publish`）
- 涉及文件：
  - `backend/routers/admin/vector_config.py`（新增）
  - `backend/main.py`（修改：`include_router` 注册 `/api/admin/configs`）
  - `backend/constants.py`（修改：新增 `ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID = 20046` 及 `ADMIN_ERROR_MESSAGES`）
  - `admin/pages/vector-token-config.html`（新增）
  - `admin/static/js/admin-api.js`（修改：`MENU_CONFIG` 增加 `vector-token` 菜单项，`super_admin` / `ai_trainer`）
  - `tests/test_admin_vector_token_config.py`（新增）
  - `docs/contract.md`（修改：文首摘要、`### 模块：向量召回与 Prompt Token 热配置`、本开发日志）
- 字段变更：
  - 新增字段：无（无 MySQL DDL；`admin_config` 仍用既有 `config_key` / `config_value` 行）
  - 修改字段：无
  - 新增错误码：`ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID`（20046）— 请求体未含任何有效更新字段，或合并后向量/Token 业务校验失败
- 测试结果：✅ 全部通过（`pytest tests/test_admin_vector_token_config.py` 6 条）
- API / 接口契约：
  - 接口名称：向量召回热配置读取 / 部分更新发布
  - Method + Path：`GET /api/admin/configs/vector_retrieval_config`、`PUT /api/admin/configs/vector_retrieval_config`
  - Request Body（PUT，均为可选，**至少其一**，`extra=forbid`）：
    - `"top_k"`: `int` — 1–20，全路统一 TopK
    - `"threshold"`: `float` — 0.0–1.0，相似度阈值
  - Response：
    - 成功：`{ "code": 0, "data": { ... }, "message": "success" }` — GET 的 `data` 为 `{ top_k, threshold }`；PUT 的 `data` 为 `publish_config` 返回的 `{ version, published_at }` 等
    - 失败：空 PATCH 或合并后校验失败 → `{ "code": 20046, "message": string, "data": null }`；鉴权失败 → HTTP **403**；非法 JSON / Pydantic 校验失败 → HTTP **422**
  - 变更类型：**新增**
  - 接口名称：Prompt Token 热配置读取 / 部分更新发布
  - Method + Path：`GET /api/admin/configs/prompt_token_config`、`PUT /api/admin/configs/prompt_token_config`
  - Request Body（PUT，字段均可选，**至少其一**，`extra=forbid`；整型 `ge=1`，`max_total` `le=50000`，模块单项 `le=20000`）：
    - `"max_total"`: `int` — 总池上限
    - `"system"` / `"persona"` / `"character_knowledge"` / `"relationship"` / `"memory"` / `"emotion"` / `"time_activity"` / `"recent_chat"` / `"user_input"`: `int` — 各模块 Token 上限
  - Response：成功/失败信封同上；GET 的 `data` 为上述键的完整对象（与 `prompt_builder` 默认合并）
  - 变更类型：**新增**
- 数据模型：
  - 表名 / 集合名：`admin_config`（无 DDL 变更）
  - 变更类型：**无**（沿用现有多行语义：`config_key` 为 `vector_retrieval_config` / `prompt_token_config` 的已发布行）
  - 字段详情：无新列；`config_value` JSON 形态由本 STEP 管理端约定（向量：`top_k`+`threshold`；Token：`max_total` + 九模块键）
- 未完成项记录：
  - 无
- 备注：无（STEP-026）

---

### STEP-026：管理后台 Step5 / Step5.5 Prompt 编辑 + Step5.5 总开关（§2.7.9 / §2.7.1 B3）
- 完成时间：2026-05-07
- 状态：✅ 已完成
- 实现说明：主链 Step5 模块1 System 从 **`admin_config.config_key = step5_system_prompt`**（JSON `{"content": string}`）热加载，缺省回退 **`SYSTEM_PROMPT_TEXT`**（`prompt_builder._load_step5_system_template_raw`）；Step5.5 从 **`step5_5_prompt_fragments`** 六段合并默认后拼装（`step5_5_prompt_fragments.py` + `execute_step5_5` 内 `load_active_step5_5_fragments`）；**废弃**旧 **`prompt_modules`** 七模块管理接口；**`POST /api/admin/prompt/test`** 使用 **`build_chat_prompt`** + **`chat_with_step5_parse(..., is_test=true)`**，`use_draft` 时覆盖 Step5 System；总开关 **`step5_5_enabled`** 独立页发布（发布不要求先跑 LLM 测试）；RBAC **`super_admin` + `ai_trainer`**；发布校验 Step5 契约字段名与 Step5.5 占位符（`20025`）。
- 涉及文件：
  - `backend/services/prompt_builder.py`（Step5 System 热加载、`build_chat_prompt` 可选 `system_prompt_override`）
  - `backend/services/step5_5_prompt_fragments.py`（新增：默认六段、拼装、校验）
  - `backend/services/step5_5_service.py`（`build_step5_5_prompt` 支持片段、`load_active_step5_5_fragments`）
  - `backend/routers/admin/prompt_mgmt.py`（重写：Step5 / Step5.5 / 开关 / 测试）
  - `admin/pages/prompt.html`、`admin/pages/step5-5-switch.html`、`admin/static/js/admin-api.js`（菜单原 `step55switch`；**2026-07-13** 起侧栏入口为「对话流 Prompt」内 `cp-step55-switch`）
  - `tests/test_step026_prompt_config.py`（新增）；`tests/test_prompt_builder.py`（mock `get_active_config`）
- 字段变更：无 DDL；**新增运行时约定键** `step5_system_prompt`、`step5_5_prompt_fragments`（`step5_5_enabled` 沿用 STEP-009）
- 测试结果：`pytest tests/test_step026_prompt_config.py tests/test_step5_5.py` 通过
- API / 接口契约：见本文档「模块：人格 / 情绪 / … / **Prompt**」整节；旧 **`prompt_modules`** 路径已删除
- 未完成项记录：无

---

### STEP-027：管理后台角色知识库 CRUD（R-L1L3-20）
- 完成时间：2026-05-24
- 状态：✅ 已完成
- 实现说明：新增 `GET|POST|PUT|DELETE /api/admin/character-knowledge`；`character_knowledge_service` + `character_knowledge_validate`；`dashvector_client.list_by_filter` / `fetch_by_ids`；仅维护 `character_global` / `character_knowledge`；RBAC `super_admin` + `ai_trainer`；页面 `knowledge.html` + 菜单 📚
- 涉及文件：
  - `backend/routers/admin/knowledge_mgmt.py`（新增）
  - `backend/services/character_knowledge_service.py`（新增）
  - `backend/utils/character_knowledge_validate.py`（新增）
  - `backend/utils/dashvector_client.py`（修改：list/fetch）
  - `backend/constants.py`（修改：20047–20052）
  - `backend/main.py`（修改：注册路由）
  - `admin/pages/knowledge.html`（新增）
  - `admin/static/js/admin-api.js`（修改：菜单）
  - `tests/test_admin_character_knowledge.py`（新增）
  - `docs/contract.md`（本条目）
- 测试结果：✅ `pytest tests/test_admin_character_knowledge.py` 5 条通过

---

### STEP-028：Step6 / 角色知识库 doc_id 合法化 + 三层 key（R-MEM-04 修订）
- 完成时间：2026-05-24
- 状态：✅ 已完成
- 实现说明：DashVector `doc_id` 由 `{type}:{key}:` 改为 `{type}_{sha256(key)[:12]}_{user_suffix}`（`user_suffix=0` 或 `user_id`）；KV **key 强制三层 `XXX-XXX-XXX`**；向量 `fields.stable_key` 存 key 原文；`dashvector_client.upsert` 解析响应 `message` 中单条失败；Step6 Prompt/few-shot 同步三层 key；**旧记忆 `mem_*` 不变**。
- 涉及文件：
  - `backend/utils/character_knowledge_validate.py`（修改：统一 `build_doc_id` / `parse_doc_id` / `validate_key` / `hash_key`）
  - `backend/services/memory_llm_service.py`（修改：接入公共 doc_id；`validate_key` 丢弃非法行；写 `stable_key`）
  - `backend/services/character_knowledge_service.py`（修改：列表/CRUD 适配新 doc_id；写 `stable_key`）
  - `backend/utils/dashvector_client.py`（修改：upsert 业务失败检测）
  - `admin/pages/knowledge.html`（修改：三层 key 说明与前端预检）
  - `tests/test_character_knowledge_validate.py`（新增）
  - `tests/test_dashvector_upsert_response.py`（新增）
  - `tests/test_step6_vector_upsert.py`、`tests/test_admin_character_knowledge.py`（修改）
  - `docs/contract.md`、`doc/对话链路改造-需求确认记录.md`（修改）
- 测试结果：✅ `pytest tests/test_character_knowledge_validate.py tests/test_step6_vector_upsert.py tests/test_admin_character_knowledge.py tests/test_dashvector_upsert_response.py tests/test_memory_llm_service.py` **59** 条通过

---

### 管理后台 · 对话流 Prompt 侧栏 + 只读展示（2026-07-13）
- 完成时间：2026-07-13
- 状态：✅ 已完成
- 实现说明：侧栏新增可折叠分组 **「🗣️ 对话流 Prompt」**（`CHAT_PROMPT_MENU`）；Step1.5 / Step3 / Step8 / Agent P0～P4 为只读页 + **`GET /api/admin/chat-prompt-view/*`**（文案与运行时同源常量）；Step5 / Step5.5 / Step5.5 开关 / Step6 链到既有可编辑页（方案 A）。废止一级独立项「Prompt管理 / Step5.5开关 / 记忆规则」。生活流侧栏改名 **「🌿 生活流 Prompt」**，子项重排并以「生活流人格拓展」替换「全局配置」展示名。无 DDL。
- 涉及文件：
  - `backend/routers/admin/chat_prompt_view.py`、`backend/services/chat_prompt_view_service.py`（新增）
  - `backend/services/prompt_builder.py`（抽出只读同源常量）
  - `backend/main.py`（注册路由）
  - `admin/pages/chat-prompt-step15.html` / `step3` / `step8` / `agent`（新增）
  - `admin/pages/prompt.html`、`memory-rules.html`、`step5-5-switch.html`、`life-feed-global.html`（侧栏/顶栏入口）
  - `admin/static/js/admin-api.js`、`admin/static/css/admin-common.css`
  - `tests/test_chat_prompt_view.py`（新增）
  - `docs/contract.md`、`docs/contract/drafts/生活流/M3_契约草案.md`（本条目）
- 测试结果：✅ 只读 API + `prompt_builder` 相关单测通过
- API / 接口契约：见上文「Prompt」模块 · 对话流 Prompt 只读展示；管理端页面节「对话流 Prompt 只读页」
- 未完成项记录：无

---

## 契约对齐问题清单


| 问题描述                                                                                                                                                                                                                 | 涉及文件                                                                                                                                  | 建议修改                                                                                                       | 状态                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------- |
| 管理后台曾混用 `StandardResponse` 与 `ApiResponse`；业务接口已统一为 `**ApiResponse`**（`stats`/`system_monitor` 除外仍部分使用 `HTTPException` 表示参数错误）                                                                                       | `routers/admin/*.py`                                                                                                                  | 已与 H5 对齐信封；统计/监控参数错误后续可改为 `ApiResponse.fail` + `ADMIN_ERR_*`                                               | **已修复**               |
| **用户表 `users.relationship_level` / `growth_value` 与 `relationship` 表并行**：成长逻辑写读均以 `relationship` 为准；**Admin 用户列表/详情及用户报表等级分布**已改为 JOIN `relationship` 读 `Relationship.level` / `growth_value`。`users` 冗余列仍存，见 TD-001 | `models/user.py`, `models/relationship.py`, `routers/admin/users.py`, `services/stats_service.py`, `services/relationship_service.py` | 可选：移除 `users` 冗余列或单写源同步                                                                                    | **已修复（Admin 查询层）**    |
| ~~H5 `**GET /api/memory/list`** 与后台分页：列表字段 `**list`**、元素主键 `**id`** 已对齐~~（Admin：`/users`、`/users/.../conversations`、`/users/.../memories`、`/memories/global`、`/stats/report`、`/system/logs` 等）                       | `routers/admin/users.py`, `routers/admin/memory_mgmt.py`, `services/stats_service.py`, `routers/admin/system_monitor.py`              | 与用户端记忆列表约定一致                                                                                               | **已修复**               |
| ~~后台编辑用户记忆使用 `**request.json()` 手写 Body**，无 Pydantic 模型，与 H5 `MemoryUpdateRequest` 风格不一致~~                                                                                                                           | `routers/admin/users.py`, `schemas/memory.py`                                                                                         | 已使用 `AdminMemoryUpdateRequest`                                                                             | **已修复**               |
| `**backend/routers/user.py` 未挂载**：无 H5「个人资料」等独立接口；**已加文件顶占位注释**，需求确认前不挂载                                                                                                                                             | `main.py`, `routers/user.py`                                                                                                          | 产品确认后在本文件实现并 `include_router`                                                                              | **已修复（占位说明已补齐，暂不挂载）** |
| ~~Agent **凌晨关键词**仅有 **PUT**，无对称 **GET~~**                                                                                                                                                                            | `routers/admin/agent_mgmt.py`                                                                                                         | 已增加 **GET** `/api/admin/agent-night-keywords`，`get_active_config(..., use_cache=False)` 读 **admin_config** | **已修复**               |
| ~~**管理端用户详情页**将 `GET /users/{user_id}` 嵌套 `data` 直接赋给 `userData`，按扁平字段读取，导致 `status`、`relationship_level` 等为 `undefined`，状态与禁用/启用逻辑失效~~                                                                              | `admin/pages/user-detail.html`                                                                                                        | 在 `**loadUserDetail**` 内校验 `basic`/`relationship`/`activity` 并**展平**为 `userData`（字段映射见上模块说明）               | **已修复**               |
| H5 `**/api/relationship/history**` 与 `**/api/relationship/growth-log**` 数据源不同（Redis 今日汇总 vs MySQL 流水）；命名易混淆                                                                                                          | `routers/relationship.py`, `relationship_service.py`                                                                                  | 文档/接口命名区分（如 `today-summary` vs `growth-log`）                                                               | 待优化                   |
| ~~**`GET .../conversations` / `.../emotion-rounds`** 的 **`end_date`** 使用 `created_at <= YYYY-MM-DD`（MySQL 解析为当日 0 点），结束日当天记录被截断~~                                                                                                        | `routers/admin/users.py`, `services/admin_date_filter.py`                                                                               | 已改为 `created_at < end_date+1day`，与 `admin_diary_query` 一致（2026-06-05）                                      | **已修复**               |
| 后台用户对话 API 按 **`sort_seq` 升序**分页；H5 **`timeline`** 按 **`sort_seq` 降序**首屏；**`user-detail.html`** 首屏拉末页以展示区间内最新记录；字段结构略异（后台多 `persona_risk_flag`、`emotion_confidence`）；**STEP-011 后**一轮可对应 **多行** `role=assistant`，后台列表为逐行展平，**未**做同 `round_id` 聚合展示                                                                                                        | `routers/admin/users.py`, `routers/chat.py`, `admin/pages/user-detail.html`                                                             | 保持 API 升序；前端已末页首屏 +「加载更早」                                                                                    | 已知差异（体验已缓解）           |
| 鉴权：**H5 JWT** 与 **Admin JWT**（`type=admin`）密钥与 payload 不同，不可混用                                                                                                                                                       | `jwt_handler.py`, `admin_auth.py`                                                                                                     | 保持现状；客户端勿混用 Token                                                                                          | 符合设计                  |
| ~~**`admin_config.config_key` 单列 UNIQUE**~~：与草稿/多版本设计冲突，保存人格或 Prompt 草稿时 `INSERT` 触发 **1062** → 管理端 500                                                                                                                         | MySQL 索引 / `scripts/migrate_admin_config_config_key_nonunique.sql`                                                                 | 执行迁移去掉唯一、重建非唯一索引；见契约「表名：admin_config」                                                                  | **已修复（库侧须执行脚本）**    |
| **记忆规则 `importance_rules[].score`**：`MemoryRulesRequest` 中 `ImportanceRule.score` 仅为 `int`，**服务端未校验 1–4**；与 PRD/管理页约定（1–4 分）一致依赖前端与配置发布流程                                                                                    | `routers/admin/memory_mgmt.py`                                                                                                        | 可选：在 `ImportanceRule` 或 `update_memory_rules` 内增加 `Field(ge=1, le=4)` 或与产品对齐的区间校验                                      | 待修复                   |
| **向量库 `top_k`**：`VectorDbConfigRequest.top_k` 默认 5，**无上限 20 等校验**；管理页前端限制 1–20                                                                                                                                    | `routers/admin/memory_mgmt.py`                                                                                                        | 可选：Pydantic 增加 `le=20` 等与 UI 一致                                                                               | 待修复                   |
| ~~**`DiaryRulesRequest` 双 Prompt + 生成读配置**~~ | `relationship_mgmt.py`, `diary_service.py`, `scheduler.py`, `main.py`, `diary_rules_loader.py`, `diary-rules.html` | 已实现；PUT 支持双字段与 `generation_prompt` 兼容；调度 **UTC** | **已修复** |
| ~~H5 **`markOpenWindowUsersDelivered` 在 `finalize` 之后执行**，窗口内 user 无法标 **`delivered`**，连发后下轮误弹「待处理消息过多」；**`countOpenPendingUsers`** 曾扫全历史 user~~ | `frontend/pages/chat.html` | **`getOpenWindowUserRows`** + **`done` 先于 `finalize`** 标记（2026-06-14） | **已修复** |
| H5 **`loadTimeline(true)`** 在 10104/满队预判时仅**追加** timeline，**不**清空 DOM、**不**同步已有行 **`data-delivery`**，无法作为完整自愈 | `frontend/pages/chat.html` | 可选：清空重拉或按 id 回写 `delivery_status`；主路径依赖 **`done` 本地标记** | 待优化 |
| H5 **`GET/PUT /api/user/settings`** 未实现；设置页 Toggle 无法持久化，主链亦未读取 | `frontend/pages/settings.html`, `routers/user.py` | 实现用户偏好持久化 + 记忆/Agent 链路读取；见 **TD-024** | **待修复** |
| H5 设置页改密码与 **`POST /api/auth/reset-password`** Body/安全语义不一致 | `frontend/pages/settings.html`, `routers/auth.py`, `schemas/auth.py` | 新增需登录 change-password 或对齐 Schema + 原密码校验；见 **TD-025** | **待修复** |
| **`.env.example` 中 `OPEN_API_PEPPER` 重复定义**（约第 27 行与第 62 行各一处；契约文首 Open API 摘要与 §Open API 模块仅描述一次） | `.env.example` | 删除应用配置段重复项，保留 Open API 专节一处 | **待修复** |
| H5 记忆星云资源目录存在未引用贴图 **`star-base.png`**（页面/脚本仅用 teal/green/purple/pink/gold + `core-star`） | `frontend/static/images/memory-nebula/star-base.png` | 删除闲置资源，或确认后续启用后补引用 | **待修复** |
| H5 记忆星云 **`#nebula-count-num`** 永久 `hidden`，仅 JS 同步数字；可见文案已迁至 **`#nebula-count-subtitle`** | `frontend/pages/memory.html`, `memory-nebula.js`, `test_h5_static_contract.py` | 可选：移除 hidden 节点并同步静态锚点；或保留为兼容锚点并在契约中标明（当前契约已标明） | 已知残留（可选清） |


---

## Open API v1（第三方 API Key）

> 集成说明见 **`docs/design/open-api-v1.md`**。鉴权：**HTTP 401** + `{"detail":"..."}`；业务：**ApiResponse**。

### 表名：user_api_keys

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer PK | 自增 |
| user_id | Integer FK(users.id) UNIQUE | 每用户一行 |
| key_hash | String(64) | SHA-256(api_key + OPEN_API_PEPPER) |
| key_prefix | String(24) | 脱敏展示，Admin 原样输出 |
| created_at | DateTime | 首次签发时间（重新生成不刷新） |
| last_used_at | DateTime NULL | 鉴权成功且 ≥60s 节流更新 |
| created_by_admin_id | Integer NULL | 签发管理员 |

### POST `/api/open/v1/chat/send`

- 鉴权：`get_current_user_by_api_key`
- Body：`OpenChatSendRequest` `{ "content": "1-2000" }`
- 成功 `data`：`{ messages, emotion, round_id }`（与 H5 SSE `done` 同源提取）
- 业务码：10101/10102/10104/10108 等同 H5 规则

### POST `/api/open/v1/chat/resend`

- **无 Body 参数**（空 POST）
- 10107/10105 等同 H5；`failed_blocked` 不可 resend（TD-030）

### GET `/api/open/v1/chat/timeline`

- Query：`cursor`、`limit`；`data` 与 H5 timeline 一致（`timeline_read_service`）

### GET `/api/open/v1/agent/messages` · GET `/api/open/v1/agent/unread-count` · POST `/api/open/v1/agent/messages/{message_id}/read`

- `data` 与对应 H5 `/api/agent/*` 一致

### Admin：GET/POST `/api/admin/users/{user_id}/open-api-key`

- RBAC：`super_admin`、`ops_admin`
- GET：`enabled`、`key_prefix`、`created_at`、`last_used_at`（无明文）
- POST：响应一次性 `api_key`；操作日志 `create` / `edit`（N4）

---

## 需要优先修复的问题（按影响程度排序）

1. ~~`**users` 与 `relationship` 成长/等级字段双源不一致（Admin 展示）**~~ — Admin 列表/详情与用户报表等级分布已读 `relationship` 表；`users` 上冗余字段仍属技术债（TD-001），可选后续迁移移除。
2. ~~**管理后台响应信封混用**~~ — 业务接口已统一为 `ApiResponse`；`stats`/`system_monitor` 仍有个别 `HTTPException(400)`，可按需继续收敛。
3. ~~**分页列表字段命名不统一（`list` / `items`）及全局记忆 `memory_id` vs `id**`~~ — Admin 已与 H5 记忆/成长日志分页约定对齐（`list` + `id`）；H5 `messages` / `items` 等历史字段名见上文「字段命名规范」。
4. ~~**后台用户记忆更新无 Schema 校验**~~ — 已使用 `AdminMemoryUpdateRequest`，与 H5 风格对齐。
5. ~~**Agent 凌晨关键词缺少 GET**~~ — 已提供 **GET** `/api/admin/agent-night-keywords`。
6. `**user` 路由占位** — 已在 `user.py` 顶部补充 TODO；**未挂载**为有意为之，待产品确认个人资料接口后再实现。
7. ~~**用户详情页 `userData` 与嵌套接口未对齐**~~ — 已在 `loadUserDetail` 展平；契约见「管理后台用户管理」模块中 `**GET /users/{user_id}`** 与 `**userData` 展平** 条目。

---

*文档生成方式：扫描 `backend/main.py` 挂载路由、`backend/routers/**/*.py`、`backend/models/**/*.py`、`backend/schemas/**/*.py` 及核心 Service 返回值；未运行服务做运行时校验。*
