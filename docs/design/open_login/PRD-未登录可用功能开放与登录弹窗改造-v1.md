# 未登录可用功能开放与登录弹窗改造 PRD

> 版本：v1.0
> 状态：待评审
> 涉及模块：首页 / 朋友圈 / 聊天 / 设置 / 日记 / 记忆星云 / 关系 / 登录鉴权体系

---

# 1. 功能背景

## 当前功能是什么
全站除 `login.html` 外，所有页面（首页、朋友圈、聊天、日记、记忆星云、关系、设置）在前端通过 `checkLogin()` 强制拦截，未登录用户一进入即被跳转到 `login.html`；后端对应接口也全部通过 `Depends(get_current_user)` 强鉴权，无 token 一律 401。两层拦截叠加，未登录用户完全无法接触任何页面内容。

## 当前存在的问题
- 未登录用户没有任何“先看看”的路径，转化路径生硬，用户必须先注册/登录才能了解产品
- 历史 PRD（`PRD-林小梦主页改版-v1.md` 中 N1 / TD-HOME-08）已将“首页游客浏览”列为远期 backlog，本轮是该债务的正式落地

## 改造目标
在不引入游客身份体系（详见 C18）的前提下，让部分页面对未登录用户开放只读浏览，功能性操作（发送消息、点赞评论、修改资料等）仍需登录；登录触发方式从“整页跳转”升级为“弹窗登录”，降低访客流失。

---

# 2. 方案确认决策记录

| 编号 | 问题 | 决策 |
|---|---|---|
| C1 | 页面未登录可见性分类 | ✅ 已确认：`index.html`/`feed.html`/`settings.html` 开放未登录浏览（部分内容）；`chat.html` 页面内容不变，操作需登录；`diary.html`/`memory.html`/`relationship.html` 维持必须登录才可见 |
| C2 | 首页关系模块（顶部胶囊） | ✅ 已确认：未登录复用现有“陌生人”（level=0）默认渲染，点击→弹登录弹窗 |
| C3 | 首页日记预览卡 | ✅ 已确认：复用现有“陌生人锁定”视觉（`diary-lock`），展示通用占位文案；与“已登录陌生人”视觉相同但点击分叉（已登录陌生人正常进入 `diary.html`，未登录弹窗）。当前方案先这样，后续可优化 |
| C4 | 首页未读消息角标 | ✅ 已确认：未登录不展示该模块 |
| C5 | 首页陪伴天数 | ✅ 已确认：未登录不展示天数，固定文案“故事从今天开始”（不同于现有 `hideKnownDays()` 的整体隐藏，需新增独立分支） |
| C6 | 首页快捷互动栏（语音/视频/记忆星云/入睡/更多） | ✅ 已确认：未登录点击统一弹登录弹窗；登录后维持现状（记忆星云正常跳转，其余 4 项显示“敬请期待”） |
| C7 | feed.html 帖子列表 | ✅ 已确认：未登录只读展示（文案/图片/话题标签/展示点赞数/展示评论数/Header 配置）；“我的评论”私有区块、`user_liked` 状态未登录不展示；点赞/评论/enter → 弹登录弹窗 |
| C8 | feed.html 未读/SSE 实时角标 | ✅ 已确认：未登录不展示该模块，登录后再挂载 |
| C9 | chat.html | ✅ 已确认：页面展示内容不变，不做锁定态引导页；发送等交互动作 → 弹登录弹窗（该规则天然同时覆盖“从未登录”与“token 过期”两种情况，无需额外区分） |
| C10 | settings.html | ✅ 已确认：页面开放未登录访问；顶部人设资料卡正常展示（未登录跳过 `relationship/status` 请求，用现有 `DEFAULT_STATUS_TEXT` 兜底）；“账号与安全”“陪伴与偏好”两个板块隐藏；“关于林小梦”板块正常展示；“退出登录”按钮未登录态改为“点击登录”，点击弹登录弹窗 |
| C11 | 登录弹窗组件形态 | ✅ 已确认：新增全局登录弹窗，完整承载登录/注册/找回密码三个面板，复用 `login.html` 现有 `panel-login`/`panel-register`/`panel-reset` markup 及 `handleLogin`/`handleRegister`/`handleReset`/`switchPanel` 逻辑；登录成功后行为由“跳转 index.html”改为“关闭弹窗 + 原地刷新当前页数据” |
| C12 | login.html 整页去留 | ✅ 已确认：保留，作为兜底页面（不再作为 diary/memory/relationship 的 token 失效跳转目标，见 C15） |
| C13 | 找回密码身份校验加固 | ✅ 已确认：不动，复用现状（无邮箱/短信验证），本轮无第三方登录接入 |
| C14 | diary/memory/relationship 被未登录用户直接访问（手动输网址/外部分享链接） | ✅ 已确认：跳转回首页 `index.html` + 自动弹出登录弹窗（不再跳转 `login.html` 独立页面） |
| C15 | 已登录用户在 diary/memory/relationship 会话中途 token 失效时的处理 | ✅ 已确认：统一为 C14 同款处理（跳首页 + 弹窗），不再单独维持“整页跳转 login.html”的旧逻辑，未登录访问与 token 中途失效两种场景处理方式完全一致 |
| C16 | index/feed/settings 三个开放页面的后台个性化请求 401 处理 | ✅ 已确认：静默降级为访客态渲染，不主动弹窗、不强制跳转；仅用户后续主动点击需登录功能点时才弹窗 |
| C17 | 后端可选鉴权改造范围 | ✅ 已确认：新增 `get_current_user_optional`，应用于 `feed.list`、`feed.config/header`、`app/persona-background` 三个只读接口；其余写操作接口全部保持强制登录不变 |
| C18 | 游客试聊 / 预注册体系 | ✅ 已确认本轮不做：涉及鉴权模型新增、LLM 调用成本风控、数据继承规则，建议单独立项 |

---

# 3. 功能改动说明

## 改动前
全站（除 `login.html`）前端 `checkLogin()` 强拦截 + 后端全部接口强鉴权，未登录用户无法进入任何页面，登录只有整页跳转一种触发方式。

## 改动后
`index.html`/`feed.html`/`settings.html` 开放未登录浏览（内容分层展示，部分模块隐藏或替换为通用文案）；`diary.html`/`memory.html`/`relationship.html` 维持整页必须登录，未登录访问或 token 失效统一跳首页+弹窗；`chat.html` 页面可见、操作需登录；新增全局登录弹窗，承担绝大多数登录触发场景，`login.html` 整页作为独立入口保留。

## 核心变化汇总

| 页面 | 改动前 | 改动后 |
|---|---|---|
| index.html | 无 token 直接跳 login.html | 开放浏览，关系/日记模块降级展示，未读角标隐藏，功能点点击弹窗 |
| feed.html | 无 token 直接跳 login.html | 帖子只读可见，点赞评论等操作弹窗，未读角标隐藏 |
| settings.html | 无 token 直接跳 login.html | 开放浏览，仅展示人设资料卡+关于林小梦，其余板块隐藏，退出按钮变登录入口 |
| chat.html | 无 token 直接跳 login.html | 内容不变，发送等操作弹窗 |
| diary/memory/relationship.html | 无 token 直接跳 login.html | 未登录访问、token 中途失效均统一跳首页+弹窗（不再跳 login.html 整页） |
| 登录触发方式 | 仅整页跳转 login.html | 弹窗为主，login.html 作为独立入口保留 |

---

# 4. 功能详细逻辑

## 完整流程

**流程一：访客进入首页**
```
访客打开 index.html
 → 不发起 relationship/diary/agent-unread 等纯个性化请求
 → 渲染访客默认态：关系模块=陌生人默认文案、日记卡=锁定态占位文案、
    未读角标=隐藏、陪伴天数=“故事从今天开始”
 → feed 预览卡、快捷互动栏正常展示（feed 数据走已开放的匿名接口）
```

**流程二：访客点击需登录功能**
```
访客点击（日记卡 / 关系胶囊 / 快捷互动栏任意按钮 / feed 点赞评论 / chat 发送 / settings 退出登录位）
 → 弹出登录弹窗（面板默认落在“登录”）
 → 弹窗内可切换“注册”“找回密码”
 → 登录/注册成功 → 关闭弹窗 → 原地刷新当前页数据（不跳转）
```

**流程三：访客访问必须登录页面（未登录访问 或 token 中途失效）**
```
用户打开 diary.html / memory.html / relationship.html
 → 检测无有效 token（从未登录，或会话中途 token 失效）
 → 跳转 index.html
 → 自动弹出登录弹窗
```

**流程四：三个开放页面的后台请求 401**
```
index/feed/settings 页面发起个性化请求
 → 返回 401（访客或 token 过期）
 → 静默清 token，按访客态渲染，不弹窗、不跳转
 → 等待用户下一次主动点击需登录功能，走流程二
```

---

# 5. 边界情况

## 首页
- 已登录陌生人（relationship level=0）与未登录访客，日记卡视觉相同，点击行为不同：前者正常进入 `diary.html`，后者弹窗（C3）
- `goToRelationship()` 为 `index.html`/`chat.html` 共用函数，`chat.html` 内调用场景固定发生在已登录会话中（关系升级提示），加未登录判断不影响该调用点

## feed.html
- 匿名访问下 `user_liked`、“我的评论”等用户绑定字段需显式判空，避免后端 optional-auth 改造遗漏导致异常或误返回上一用户数据（需专门测试用例覆盖）

## settings.html
- “关于林小梦”板块背后接口 `app/persona-background` 本身不依赖 `user_id`，开放匿名访问后功能不受影响

## diary/memory/relationship.html
- 未登录访问与 token 中途失效两种触发场景，统一走“跳首页+弹窗”，无需再区分处理分支（C15 已收敛）

## 全局
- 找回密码维持现状（无身份校验），登录弹窗铺开后入口变多，但本轮不加固（C13，已知风险，登记入技术债）

---

# 6. 数据结构

本轮不新增数据库表或字段，主要变化：
- 后端新增依赖函数 `get_current_user_optional`，返回类型 `Optional[int]`（无 token 返回 `None`，不抛异常）
- 前端新增共享登录弹窗组件的状态管理（面板切换、登录成功回调），不涉及持久化存储

---

# 7. 改造范围与文件索引

| 文件 | 改动内容 | 改动量 |
|---|---|---|
| `frontend/pages/index.html` | 移除 `checkLogin()`；`loadPage()` 增加未登录分支（跳过个性化请求，渲染访客默认态）；日记卡/关系胶囊/快捷互动栏点击逻辑增加登录判断；陪伴天数新增访客文案分支 | 中 |
| `frontend/pages/feed.html` | 移除 `checkLogin()`；帖子列表匿名可读；点赞/评论/enter 增加登录判断；未读/SSE 角标改为登录后挂载 | 中 |
| `frontend/pages/settings.html` | 移除 `checkLogin()`；隐藏“账号与安全”“陪伴与偏好”板块；退出登录按钮态切换；`loadProfile()` 未登录跳过请求 | 中 |
| `frontend/pages/chat.html` | 发送等操作增加登录判断，触发弹窗 | 小 |
| `frontend/pages/diary.html` / `memory.html` / `relationship.html` | `checkLogin()` 改为跳首页+弹窗（覆盖未登录访问与 token 中途失效两种触发场景） | 小（3 处同构改动） |
| `frontend/static/js/api.js` | 新增登录弹窗组件（复用 `login.html` 面板逻辑）；新增/复用未登录判断工具函数；`goToRelationship()` 等共享函数适配 | 中偏大（新组件） |
| `frontend/pages/login.html` | 面板 markup/逻辑被抽取复用，页面本身保留不变 | 无 |
| `backend/utils/auth_middleware.py` | 新增 `get_current_user_optional` 依赖 | 小 |
| `backend/routers/feed.py` | `list`、`config/header` 路由切换为可选鉴权 | 小 |
| `backend/routers/app.py` | `persona-background` 路由切换为可选鉴权 | 小 |
| `backend/services/feed_service.py` | `list_feed` 支持 `user_id=None` 分支，跳过私有评论/`user_liked` 查询 | 小 |

---

# 8. 技术债标注

| 编号 | 内容 | 状态 |
|---|---|---|
| TD-HOME-08 / N1-B（历史债务） | 首页游客浏览模式 | 本轮落地实现，视为了结 |
| TD-AUTH-01（新增） | 找回密码缺少身份校验，登录弹窗铺开后入口增多，风险维持现状未收紧 | 登记，暂不处理 |
| TD-AUTH-02（新增） | 游客试聊/预注册体系（设备标识、微信静默授权 openid、匿名身份与正式账号数据继承） | 明确排除本轮，建议单独立项 |

---

# 9. 检查项

| 项目 | 状态 |
|---|---|
| index.html 未登录浏览可用，个性化模块正确降级 | ⚠️ 待开发验收 |
| feed.html 未登录只读浏览，写操作正确拦截 | ⚠️ 待开发验收 |
| settings.html 未登录访问，板块隐藏与“关于林小梦”正常 | ⚠️ 待开发验收 |
| chat.html 未登录发送触发弹窗 | ⚠️ 待开发验收 |
| diary/memory/relationship 未登录访问与 token 失效均跳首页+弹窗 | ⚠️ 待开发验收 |
| 登录弹窗三面板功能与现有 login.html 一致 | ⚠️ 待开发验收 |
| feed/app 匿名接口返回体不夹带用户绑定字段 | ⚠️ 待开发验收 |

---

# 版本记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-08-02 | 初始版本 |
