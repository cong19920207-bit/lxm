# H5 App Api

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

- 文档 ID：`contract-h5-app-api`
- 权威状态：`canonical`
- 功能范围：`h5-app`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-015`, `TD-024`, `TD-025`
- 最近同步：`2026-10-25`（设置页／退出确认及桌面入口复查收尾，手机HTTPS恢复经用户确认延期；保留既有BGM、主页验收及接口缺口边界）

> **当前口径（2026-08-13）**：`GET /api/app/persona-background` 为可选 Bearer。完全缺少 `Authorization` 头返回公共人格背景；有效 token 返回同一公共配置；头存在但无效（空值、非 Bearer、空 Bearer、伪造/过期 token、封禁用户）均 HTTP `401`。可选Bearer白名单仅此接口与 `GET /api/feed/list`、`GET /api/feed/config/header`。页面访客态、共享登录弹窗与四类 `401` 策略以「H5 认证与页面访问策略」为准。下文「模块：H5 应用」为 2026-07-19 迁移原文，其中“鉴权：Bearer 用户 JWT”已被当前口径取代。

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

### H5 认证与页面访问策略

BGM独立公开 `GET /api/bgm/catalog`，不解析Authorization，账号与偏好不参与结果，H5须显式不附Token。匿名目录客户端、各页生命周期、主页面板与六页气泡均已接入，本地Docker正式页已有实际OSS播放及Chrome/Safari局部证据；完整环境覆盖另按唯一结项记录保留。它不改变下面三个可选Bearer接口的无效头401规则，详见[BGM接口](../bgm/api.md)。

#### 匿名 HTTP 白名单

| 方法 | 路径 | 无 `Authorization` | 有效 Bearer | 头存在但无效 |
|---|---|---|---|---|
| `GET` | `/api/feed/list` | `200`，公共 Feed 且省略用户字段 | `200`，保留登录用户语义 | HTTP `401` |
| `GET` | `/api/feed/config/header` | `200`，公共 Header | `200` | HTTP `401` |
| `GET` | `/api/app/persona-background` | `200`，公共人格背景 | `200` | HTTP `401` |

- 可选Bearer白名单包含上述三个 GET。另有完全匿名BGM目录，见下项。页面可以未登录停留，不代表该页其他接口匿名开放。
- 未引入游客账号、游客会话、游客试聊、数据继承、新表字段或数据库迁移。
- Feed 列表的完整条件响应和其余 Feed 端点强鉴权口径以 `contract-life-feed-api` 为准。认证 API 本身的请求/响应契约不变。

#### 共享登录弹窗

- **视觉基线**：手机端为底部上滑的深色半透明圆角 sheet，桌面端居中；遮罩层压暗当前页，sheet 使用紫蓝边线/光晕、头像与心形标识，主按钮为紫蓝到粉色渐变；需适配安全区、小屏滚动和 `prefers-reduced-motion`。
- **登录面板结构**：标题“登录后，她就能记住你了”，副标题“保存聊天、记忆和关系进度，下次回来还能继续陪伴。”；包含账号、密码/可见性切换、记住我、“登录并继续”、“暂不登录，继续看看”、“注册账号”和“找回密码”。
- 注册/找回密码面板沿用同一容器、字段风格、错误提示和密码可见性交互；关闭按钮、遮罩层点击、Escape 与“暂不登录”均可关闭。
- 开放页的交互登录使用全局单例弹窗；默认打开登录面板，可切换注册和找回密码面板，重复打开不叠加新弹窗。
- 登录成功后保存 token、关闭弹窗，并在原开放页交付成功回调一次。
- 弹窗内注册采用 UD-01 方案 A：直接保存注册响应 token、关闭弹窗并回调一次。
- 独立 `/pages/login.html` 保持既有行为：注册成功后提示用户再登录，登录成功后进首页。找回密码沿用既有接口和校验，本轮不增加短信、邮箱、第三方身份校验或安全加固。
- 登录/注册成功只恢复当前页的登录态数据与资源；不自动重放触发登录的写操作或聊天发送。

#### HTTP `401` 处理策略

仅当前有效请求的 HTTP `401` 执行下列策略：先清除本地 token，再执行调用点明确选择的后续行为。显式传入取消信号或有效性检查的请求，若已取消、超出批次截止、被新代次替代或登录快照已变化，必须在 `401` 副作用前终止，不能清除新 token 或触发旧页面回退。未传这些选项的既有调用点保持原策略。

| 策略 | 使用场景 | `401` 后行为 |
|---|---|---|
| `LEGACY_LOGIN_PAGE` | 未显式迁移的既有调用点 | 保持独立登录页回退 |
| `SILENT_VISITOR` | 开放页的背景/私有数据读取 | 清理已加载私有状态并静默降级为访客，不弹窗 |
| `INTERACTIVE_MODAL` | 用户主动写操作或私有交互 | 回滚本次临时 UI，保留可恢复输入，在当前页弹出共享登录窗 |
| `PROTECTED_HOME_MODAL` | 受保护页初始化或中途请求 | 停止并清理页面私有资源，使用 `replace` 回首页，通过一次性信号弹登录窗 |

#### 开放页访客态

| 页面 | 未登录可见内容 | 禁止的私有初始化 | 主动交互与登录恢复 |
|---|---|---|---|
| Index | 默认头像/状态；文案“故事从今天开始”；关系 `0 / 200`；日记锁定占位；隐藏未读；只加载公共 Feed 与按需公共 BGM | 不加载用户关系、私有首页数据或未读 | 前四格快捷入口、关系和日记入口先弹窗；第五格 BGM 公开；成功后私有首页数据与未读各恢复一次 |
| Feed | 公共 Header 和公共 List | 不 enter、不请求 badge、不连 SSE、不启动观察器或私有 focus | 点赞/评论在 UI 或请求改变前先弹窗；成功后各私有资源恢复一次，不重放写操作 |
| Settings | 默认资料；私有标题/设置卡隐藏；BGM 两个本地开关公开；“关于林小梦”可懒加载公共 persona | 不加载关系、私有状态或账号设置 | 登录按钮弹窗；成功后关系、状态与设置各恢复一次；BGM 与 About 保持可用 |
| Chat | 只渲染访客壳；Feed 入口仍公开 | 不读时间线、未读、草稿，不发模型请求 | 发送、Enter、重试、记忆入口先弹窗；成功后恢复私有数据一次，保留输入但不自动发送 |

#### 受保护页统一回退

| 页面 | 直接无 token | 初始化中收到 `401` | 登录成功后 |
|---|---|---|---|
| Diary | 私有请求前回首页 | 停止观察器/私有初始化后回首页 | 留在首页，不自动返回 Diary |
| Memory | 渲染器、动画和私有请求前回首页 | 停止 RAF、定时器、渲染器和连接层后回首页 | 留在首页，不使用 return URL |
| Relationship | 私有请求前回首页 | 停止增长观察器/私有初始化后回首页 | 留在首页，不自动返回 Relationship |

- Diary、Memory、Relationship 后端 GET 保持强鉴权，无 token 均返回 HTTP `401`；不新增匿名占位 API 或分享预览。
- 旧独立HTML的受保护页回退使用 `sessionStorage` 一次性信号 `lxm_open_login_once`，首页先删除再打开弹窗；AppShell由AuthService在当前有效回退提交后打开一次共享登录窗。同页并发 `401` 只导航一次、自动弹窗一次，刷新、关闭或后退不形成循环。
- 一次性信号只表示“在首页打开登录弹窗”，不保存返回路由或用户数据；本轮不实现 return URL、登录后自动回跳或写操作自动重放。

---

### 主页 v2：场景、加载与数据

本节对应仓库中的 `frontend/pages/index.html`、`settings.html`、`frontend/static/js/home-data.js`、`home-preferences.js`、`home-scene-core.js`、`home-scene.js`、`frontend/static/css/home-scene.css`、共享 `api.js` 和 `nginx/nginx.conf`。它记录已实现行为及尚未启用的配置。主页本期已由用户确认真机人工验收通过；最新验收来源、范围及后续事项见 [主页 STEP 记录 §9.21](../../../design/home-redesign/steps-verified.md#921-本期主页人工验收通过与文档收尾2026-10-03)。

#### 静态场景与首页图片

- 首页默认采用 `home-scene/v4/` 中的背景和完整人物，两张静态核心图由首页早期内联逻辑挂载。场景增强脚本、可选贴片或 Canvas 失败时，已可用的核心图与业务入口继续显示；坏图隐藏。
- 人物、头发和眨眼贴片使用同一 `853×1844` 源画布坐标及同一外层布局变换。布局依据实际顶栏、Hero 和卡片空间调整，桌面以最大 `560px` 的竖向页面居中并配暗色延展；短屏可滚动，保留正常缩放和手势。
- 人物布局参考顶栏头像、主要文字及关系按钮的自然尺寸，排除顶栏入场位移和模块加载／失败提示的临时高度；视口及主要内容不变时，刷新、聊天页返回和后退缓存恢复不因这些临时状态改变人物尺寸或页内位置。正常滚动及后退时的滚动恢复仍保留。
- 首页默认头像、情绪头像、加载专用头像及日记预览图使用 `home-thumbnails/v2/` 的内容摘要 URL。加载头像与主页情绪头像职责分开；默认／加载头像按既定顺序回退，都不可用时隐藏，不在同页重复预载已失败 URL。其他页面继续使用原图和默认映射。
- `updateAvatarEmotion(emotionLabel, avatarOptions = {})` 支持可选 `avatarMap`、`onError(img, failedSrc)` 与 `isCurrent()`。异步图像回调仅在有效时更新；未传选项保持原映射和回退。

#### 加载时序与恢复

- 正常流程保留至少 `3000ms` 展示、完成后 `500ms` 停留与 `550ms` 透明度退出；系统减少动态时取消退出过渡。压缩图片不改变这段固定展示节奏。
- 背景和完整人物的加载／解码等待截止为启动后 `5s`；业务 API、头像和可选特效不参与遮罩完成条件。启动后的绝对 `8s` 截止用于幂等释放遮罩和显示入口；后台恢复时检查绝对时间，不重新计时。
- 原 `sessionStorage.lxm_home_loader_done='1'` 语义保留：同标签合法标记的非刷新返回跳过遮罩，刷新走正常流程；`clearToken()` 清除该标记。跳过遮罩仍初始化数据和场景。
- 存储访问异常不阻断启动。无法读取 token 时区分“未知”和已确认访客；不把存储故障当作鉴权失败。`HomeStartup` 保存本次启动状态和可用的内存登录快照，供晚到模块读取。

#### 共享请求上下文

- `request(method, path, data, requestOptions = {})` 支持可选 `signal` 和 `isCurrent()`：信号透传给 `fetch`，在发送前、响应副作用前及 JSON 解析后检查有效性。
- 显式受控请求已取消时抛 `AbortError`，上下文失效时抛 `StaleRequestError`；调用方负责丢弃结果。它们不是新的服务端状态码。默认调用的网络失败仍返回 `code=-1` 信封，当前有效 `401` 仍按上文四类策略处理。
- 首页的 `saveToken()`／`clearToken()` 更新启动登录快照并发布 `home-auth-change`；其他页不增加该事件。首页同步处理本页登录变化和其他标签的 token storage 变化。

#### 首页模块取数与保留内容

- 登录态分别请求关系、相识天数、日记、聊天未读、Feed 列表与 Feed 角标六个现有端点，独立显示先到结果；访客只请求公共 Feed 列表。没有新增首页聚合接口或匿名私有接口。
- 每个请求批次从启动起至多 `8s`，到期以 `AbortController` 取消未完成请求。同模块的加载、Feed 刷新和局部重试在请求未完成时去重；登录变化取消旧批次。请求代次、登录快照和头像异步回调共同防止旧结果覆盖新状态。
- 模块分别表示未完成、成功、失败、访客和登录未知。合法成功响应的空数组才表示真实空态；缺少必需字段按失败处理。失败保留当前账号已有成功数据并提供局部重试，切换账号时清除旧账号数据。超时不清 token，不触发登录降级。
- 关系未知时日记显示“解锁状态待确认”；只有有效关系 `level=0` 才按未解锁呈现。访客保留上文规定的锁定占位。成长值依次使用 `current_growth`、`growth_value`，`next_threshold=null` 为满级 `100%`；相识天数继续来自 `milestones.known_days`。
- 状态文案继续由 `resolveStatusText` 决定；北京时间 `HH:mm`、七时段和 `hour<5 || hour>=20` 的 Good night 保留。日记仍为固定预览句、原 `formatTime` 相对时间，严格 `is_read === false` 才显示 NEW。
- Feed 卡显示最近帖文字、按北京墙钟解释的更新时间，并从返回帖子顺序中取最多两张图片；坏缩略图隐藏。真实数据不足两张时不补示例图。登录角标与 `goFeed` 未读定位保持；页面重新可见时仅协调 Feed 刷新，不新增轮询或因场景恢复重载全部模块。
- 原顶栏、快捷栏、朋友圈、日记和聊天 CTA 的顺序、导航及登录门禁保持；视频／入睡／更多互动仍提示“敬请期待”。人物本地回应按下节处理。语音入口、子页业务、音频协议与计费沿用原约定。

### 主页 v2：互动、暂停与质量

#### 渐进动效与人物回应

- 无暂停原因且完整人物可用后，按需加载呼吸、眨眼、三组发丝、待机动作、灯光、雨和城市窗星光的可选效果。初始关闭动态或系统减少动态时不预先启动可选效果；失败仅影响对应增强能力。
- 呼吸只做平滑轻微上下位移，不缩放完整人物；待机动作及用户触发的本地回应继续按各自动作计划运行。
- 人物头脸和上身的有效区域支持点击、Enter、Space，触发本地轻微回应；回应过程中连点合并，暂停或减少动态时不启动。该操作不跳转、不发送聊天、关系写入或模型请求；访客也可使用，不初始化私有数据。
- 装饰层不抢事件，业务按钮、卡片及覆盖层优先；正常滚动、缩放和键盘操作保留。
- 人物稳定性已在桌面 Chrome 核对首次加载、真实刷新、聊天返回按钮、真实后退缓存和临时失败提示，见 [人物稳定性回归](../../../../reports/home-motion-settings/character-stability-results.json)；聊天业务响应为受控夹具。当前本地 Docker 页面另核对访客加载／刷新和源码一致性，见 [Docker 验证](../../../../reports/home-motion-settings/character-docker-results.json)。这些结果不包含真实手机浏览器地址栏伸缩引起的视口变化。

#### AppShell 设置页与退出确认（2026-10-24）

- 用户确认采用“轻柔卡片＋柔光双色图标＋柔光底部面板”。AppShell 设置分为“陪伴方式”“画面与动效”“背景音乐”“账号与关于”，头像区缩小，图标使用本地静态 SVG；记忆整理作为说明。陪伴／动效与下方密码区由 `data-settings-private` 同步隐藏，访客保留 BGM、本地偏好与 About，标题变为“关于”，底部按钮打开现有登录窗。密码原校验／请求／敏感值清理不变，TD-024/TD-025 未清偿。
- `AuthInteractions.logout()` 使用专属柔光底部面板，标题“退出当前账号？”，说明退出后以访客身份浏览、再次聊天需登录，以及聊天记录／记忆和本机音乐设置保留；按钮为“取消”“退出登录”。适配安全区、小屏／横屏、减少动态，复用原背景 inert、滚动锁定、焦点循环／恢复、遮罩／Escape 取消、切页／身份失效与请求归属；确认前不发请求。其他确认窗与独立 HTML 回退页沿用原外观。
- 本轮实际模块与 Chrome 的受控接口／账号、窄屏及横屏验证见设置页实施证据（本地留存，未随本次提交；原引用：`../../../../reports/settings-redesign/settings-redesign.json`）；既有设置回归使用本地真实 404/422 验证未解决接口缺口，见回归证据（本地留存，未随本次提交；原引用：`../../../../reports/settings-redesign/settings-regression/settings-browser.json`）。不据此宣称真实账号完整业务或实体手机验收通过。

#### BGM 本地偏好与公开设置

- `settings.html` 在 `settings-private-sections` 外按顺序显示“下次打开时自动播放”（独立 HTML 回退页仍为“下次打开时自动播放 BGM”）“音乐淡入淡出”，访客可操作，无登录弹窗、偏好 API、账号分区或上报。自动播放说明仅影响新访问，不改变当前播放/暂停/关闭；浏览器仍可能要求点击播放。设置页保持浅色，BGM 与画面开关统一紫色，并提示偏好只保存在当前设备/浏览器；输出能力已明确不支持淡入淡出时就地显示能力说明，pending不误报。原“主页动效”及倾斜继续在私有区。
- `bgm-preferences.js` 提供 `BgmPreferences.read(field)`、`write(field, value)` 和 `get()`；前两者返回 `{value, scope, note}`，后者返回五项值。`motionEnabled` 委托既有 `HomePreferences`，原 `lxm_home_motion_enabled` 的 0/1 与 `lxm_home_motion_session` 不变；倾斜不在五项内。
- 新字段/默认值：`fadeEnabled=true`、`autoplayEnabled=true`、`volume=0.30`、`lastSelectedTrackId=null`；布尔严格校验，音量须有限且 0～1，手选为空或 1～128 字符的字母/数字/下划线/连字符 ID。键依次为 `lxm_bgm_fade_enabled`、`lxm_bgm_autoplay_enabled`、`lxm_bgm_volume`、`lxm_bgm_last_selected_track_id`，每字段独立 `{version:1,value,revision}`。不使用 demo 键或账号 ID。字段损坏只回退该字段；未知版本保留原记录，不按本版解释或覆盖。
- 保存依次尝试 localStorage、同名加 `_session` 的 sessionStorage、当前文档内存；失败即时保留选择，提示“仅本次”或“仅本页，离开可能恢复”。成功本地保存清对应临时覆盖；同字段递增 revision 防止删除临时值失败后旧选择反盖新保存。读取不可用显示默认值提示。正常保存不弹成功消息。`bgm-settings.js` 仅渲染和写偏好，不调用播放/暂停/关闭，不监听跨标签事件遥控播放。
- 登录、退出和换账号沿用必要账号字段清理，保留五项。存储整体不可读时，设置页按访客渲染，公开偏好仍可在内存中使用。模块不含采集管线或网络诊断。
- STEP-009 的 证据（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step009/browser-results.json`） 覆盖真实 Chrome、受控业务 API、存储异常、390px 和原 motion 回归。音量/手选已与正式播放器接线，后续本地Docker/OSS及Chrome/Safari的播放、音量和部分页面流有独立证据；这些不将早期受控账号往返、目标手机或完整跨环境验收提升为通过，汇总见[本版结项](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)。

#### 设置页动效与倾斜偏好

- 从主页左上角头像进入设置页，在“画面与动效”（独立 HTML 回退页仍为“陪伴与偏好”）中操作“主页动效”开关；形态沿用该分区的紫色滑动开关。默认开启并统一控制呼吸、眨眼、发丝、待机／本地回应、灯光、雨和城市窗星光，不拆分单项开关。访客仍隐藏设置页私有分区，可通过原共享登录窗登录后查看。
- “倾斜视差”开关与“主页动效”并列，沿用相同开关形态，默认关闭，需用户主动开启。两个控制开关均只放在设置页；主页“更多互动”保留原按钮名称，登录后点击提示“敬请期待”，不打开动效面板或跳转设置。访客点击更多互动沿用共享登录窗；登录后只恢复数据，不自动重放更多操作或申请传感器权限。
- `localStorage.lxm_home_motion_enabled`：`'0'` 关闭，`'1'` 开启；无保存选择默认开启。首次可能启动动态前读取，当前浏览器跨刷新、重访及账号切换保持，不跨设备同步。
- 首页与设置页通过 `home-preferences.js` 共用该偏好，不写入 `GET/PUT /api/user/settings`。开关表示用户选择；系统减少动态优先于用户开启，设置页显示对应说明。读取失败显示“本次默认开启”；本地写入失败而会话存储可用时，用 `sessionStorage.lxm_home_motion_session` 传递本次选择并提示无法长期保存，后续保存成功时清除临时值。两种存储均不可写时保留本页内存选择，后续读取、后退缓存恢复和倾斜前置检查采用同一选择，并提示“选择仅在本页生效，暂时无法保存；离开页面后可能恢复原设置”。其他标签的新保存选择可替换本页临时选择。
- 首页重新可见或由浏览器后退缓存恢复时，先重新读取偏好再恢复场景；同浏览器其他标签页修改保存值也会同步。关闭动态停止场景动作和方向监听；重新开启不自动申请新权限。
- 主页动效入口调整已在桌面 Chrome 的 `390×844` 视口、受控业务 API 及隔离 Nginx 验证，覆盖开关形态、默认开启、保存／刷新／账号切换、真实后退缓存、跨标签同步、存储异常和系统减少动态，见 [动效回归证据](../../../../reports/home-motion-settings/results.json)。设置页倾斜授权及回到主页后的方向监听采用受控 `DeviceOrientationEvent` 和权限结果验证，见 [倾斜回归证据](../../../../reports/home-motion-settings/tilt-settings-results.json)；不包含真机 HTTPS 权限、真实方向或正式服部署验收。

#### 主动倾斜

- 未保存当前标签会话的倾斜选择时默认关闭。用户在设置页主动开启时检查主页动效选择、系统减少动态、已知旧背景状态、安全上下文及 `DeviceOrientationEvent`；需要 `requestPermission()` 的浏览器在该次开关点击调用栈内申请权限。
- 成功开启后，`sessionStorage.lxm_home_tilt_enabled` 和 `lxm_home_tilt_permission` 保存本标签会话的选择及授权交接提示，用于设置／主页导航、后退和刷新；不主动跨标签同步，不跨设备同步，不写入账号设置接口。交接提示不替代浏览器权限判定，主页不自动调用权限申请；必须收到有效数据才报告实际已开启。存储失败反馈原因，不显示未保存的启用选择。
- 设置页开关表示本次标签页的用户选择；分别显示关闭、等待授权、返回主页后待有效数据、已开启、暂停和不可用。仅接受有限的 `beta`／`gamma`，初始或旋转后等待有效数据最多 `5s`；拒绝、不支持、不安全连接及超时均反馈原因并保持关闭。运行状态及原因可用 `sessionStorage.lxm_home_tilt_status` 交接给设置页，不包含方向数值。
- 倾斜关闭标记写入失败时，立即关闭本页监听并保留内存关闭决定；现有状态通道仍可写时，以 `enabledOverride=false` 和 `storageNote` 将关闭决定及保存失败原因交接给设置页，旧开启标记不再使倾斜恢复。显式成功开启会清除关闭覆盖并更新 `choiceId`，使原主页后退缓存中的临时关闭决定可被此次选择替换；交接更新失败时不报告已开启。状态通道也不可写时只保证本页关闭，并提示离开页面后可能恢复原设置；主页自动关闭时用提示消息说明，设置页手动关闭时在该开关下说明。超时原因与保存失败说明分别保留。
- 首次有效方向作为基准，方向事件只更新输入，由场景唯一主调度应用视差；屏幕旋转后重设基准。关闭、暂停和销毁移除方向监听；关闭动效只暂停已主动开启的倾斜，同页恢复不重复申请权限。设置页取消、离开、退出登录、关闭动效或系统减少动态后，迟到的授权结果作废。
- 当前人物视差位移上限为横向 `±12 CSS px`、纵向 `±8 CSS px`，由 `HomeSceneCore.CONFIG.parallax` 统一配置并由渲染层读取；背景层当前不随倾斜移动。方向归一化范围 `xRange=20°`、`yRange=25°`，竖屏时表示相对首次有效姿态左右侧倾 `20°`、前后倾斜 `25°` 达到满幅，超出后钳制；横屏沿用屏幕方向旋转映射与重新校准。平滑采用按帧时间计算的指数跟随，时间常数 `smoothingMs=140`，不是固定延迟或完成时间。本次调整对应提交 `9c6f985`。
- 方向数据仅在本页内存用于视觉输入，不上传、不持久化。手机 HTTP 局域网预览不满足安全上下文；本期真机人工验收已通过，结果及设备明细的记录边界见下文「验收边界」。
- 本轮存储异常修复覆盖双存储不可写、超时关闭写入失败、全部倾斜存储不可写、显式关闭与存储恢复，以及交接失败不误启用；初始化关闭提示已验证在主页就绪且可见后补发一次，覆盖后退缓存保留待提示内容、新成功选择使旧提示失效及销毁清理。验证入口见 [9 组组合异常回归证据](../../../../reports/home-motion-settings/preference-failure-results.json)；仅适用于本地桌面 Chrome 的受控存储、方向能力／权限及可见性环境，后退缓存使用浏览器真实恢复。

#### 统一暂停与清理

- 每页场景幂等挂载一次，以单一主 RAF 按帧时间差驱动。加载中、后台、共享登录窗可见、语音面板可见、用户关闭动态、系统减少动态和旧背景模式分别登记暂停原因；只有全部解除才运行。
- 语音暂停依据实际面板可见性，覆盖准备、权限、呼叫、结果和错误状态，不以通话接通为唯一触发。关闭一个面板只解除对应原因。观察适配仅在首页，不修改共享登录、麦克风或音频链路。
- 暂停恢复自然姿态，取消排队眨眼／待机动作和方向监听；隐藏与 bfcache 停止场景帧，返回保留实例并检查截止，不追赶后台时间。真正页面销毁统一清理场景 RAF、计时器、事件、观察器和特效；普通场景暂停不触发整页取数。

#### 质量策略与当前配置

- 环境绘制优先 `30fps`，雨／光点复用纹理；Canvas 有效 DPR 默认至多 `1.5`。正式像素预算、统计窗口和最低帧率由真机量测确定。
- 已实现的降级顺序为减少雨／星光、停止发丝、退为静态。同一实例降档后，后台、弹窗或 bfcache 恢复不升档；刷新／全新页面重新评估，仍尊重动态偏好和系统设置。
- **当前正式自动降级判定尚未启用**：Q201 正式参数未确定。`HomeScene.quality.configure()` 接受带来源的 `pixelBudget`、`windowMs`、`minimumFps`；没有有效配置时仅采集可用的帧间隔、长任务及 JS 堆指标。测试夹具参数不能作为产品配置或手机性能结论。

### 主页 v2：资源缓存与回退

- `data-home-scene-mode="dynamic"` 为默认；将首页 HTML 根属性改为 `legacy` 并刷新，可切回精确路径 `/static/images/Index/Index.png`。主动旧模式只请求旧图，不预热新七图；动态偏好值保留，界面说明动态未运行，倾斜不申请权限。
- 默认模式不预热旧大图。两张核心图均失败，或核心截止时均不可用，切回旧图；单核心／可选图失败保留其余可用层。回退复用当前加载和数据控制器，不重新计时或取消失效请求保护；旧图也失败则保留底色和业务入口，不循环重试。
- 仓库 Nginx 对 `/pages/index.html`、`/pages/settings.html`，场景脚本 `home-data/home-preferences/home-scene-core/home-scene`，BGM脚本 `bgm-preferences/bgm-settings/bgm-controller/bgm-output/bgm-catalog/bgm-player/bgm-session/bgm-page/bgm-record/bgm-home/bgm-bubble/bgm-ducking/bgm-media/bgm-preparation`、`voice-entry`（均位于 `/static/js/`，扩展名 `.js`），及 `/static/css/home-scene.css`、`/static/css/bgm.css` 返回 `Cache-Control: no-cache`，并关闭 ETag 与 If-Modified-Since 判断，以获取更新后的内容和回退设置。媒体对象的独立不可变版本缓存见[BGM接口](../bgm/api.md)。
- `/static/images/home-scene/v4/` 与 `/static/images/home-thumbnails/v2/` 下带 `12` 位十六进制内容摘要的 WebP／JPG 成功响应缓存一年：`public, max-age=31536000, immutable`。内容变化必须换 URL；缺失图片的 `404` 不加长期缓存，manifest 不套用此规则。其他页面、共享脚本与语音资源继续原策略。
- 以上缓存已在本地真实 Nginx 验证，外层 HTTPS／CDN 和正式服部署状态需要在实际环境单独核对。

### 主页 v2：验收边界

**本期状态：人工验收通过（2026-10-03）。** 用户在本期主页改版及倾斜参数调整后明确确认：“我真机测试通过了，你可以记录为人工通过”。本期主页使用体验按该人工确认收口，原“真机倾斜验收延期”状态由本次确认替代。验收人及结果来源为用户本人、本次对话，完整记录见 [唯一执行记录 §9.21](../../../design/home-redesign/steps-verified.md#921-本期主页人工验收通过与文档收尾2026-10-03)。

本地真实前端、受控 API／方向事件、桌面 Chrome 和隔离 Nginx 的既有验证仍按原证据范围保留。用户未逐项提供机型、系统／客户端版本、权限异常、声音链路和四类目标浏览器的用例明细，本记录不补造逐环境测试结果；人工确认与自动化验证分别记载。开发模拟预览的两图及模拟登录仍只作为界面检查证据。

Q201 正式自动降级参数尚未配置、自动降级判定尚未启用；同设备新旧性能／加载专项量测仍保留后续跟进。本次人工通过不将上述配置或量测标为完成，不改写原 STEP 的逐项完成条件与历史统计。正式部署字节、外层缓存及回滚操作也不由人工体验确认代替技术核验。

<a id="chat-client-timing"></a>
### 文字提交计时配置

本节登记已实现契约；2026-10-13本地Docker环境`local-docker:lxmfor`已完成S15清理/保留核验并开放epoch2，旧库及旧隔离分区已退役。实际版本、验证和保留风险见唯一STEP §3.39。

通过认证只读 [GET /api/chat/client-timing](../chat-emotion/api.md#client-timing-operation)取得 ApiResponse.data。CLIENT_TIMING随chat router/真实main导入校验，非法值启动拒绝；配置未就绪不POST，visible/online/pageshow合并恢复配置后继续原ID/原窗口。下面可配置字段对应同名uppercase环境变量，版本 `chat-client-v1:` 加参数摘要。

| 字段 | 默认 | 有效范围 |
|---|---:|---|
| text_status_poll_interval_ms | 2000 | 1000～10000 |
| text_status_poll_max_interval_ms | 10000 | poll_interval～30000 |
| text_status_poll_backoff_factor | 2 | >1且≤3 |
| text_status_max_inflight_per_target | 1 | 固定1 |
| text_status_max_inflight_per_page | 2 | 1～5 |
| text_admission_reconcile_window_ms | 240000 | 180000～300000 |
| text_client_transport_margin_ms | 20000 | server_wait_margin～60000 |
| text_local_submission_retention_seconds | 604800 | 180+server reconcile秒～server retention |

同时返回服务端派生 text_business_deadline_ms=180000、text_status_probe_timeout_ms（默认3000）、text_status_reconcile_margin_ms（默认60000）、text_server_wait_margin_ms（默认10000）、server_timing_config_version 及 timing_config_version，来源见[服务端计时](../chat-emotion/data.md#chat-timing)。客户端配置不是业务截止权威，不能延长原D。

<a id="chat-submission-sync"></a>
### 原身份核实、有界轮询与迟到隔离

`chat-submissions.js` Reconciler 在首次send/resend fetch前保存 `chat_submissions:<JWT user_id>` 最小 operation/request_id/首次时间/固定until/exhausted/有效代D/十进制revision/source user ID及sort_seq。无正文或凭据副本，终态清索引；AppShell卸载/退出/主体切换停止本地等待并清无归属草稿，不一概删除按原user白名单/期限保存的有效提交索引；新主体不能显示旧主体提交。规范UTF8 b64路径见[状态GET](../chat-emotion/api.md#submission-status)，meta前断线仍按原身份查询，不按文本猜测。

状态同步独立于历史cursor/loading/noMore；同target最多1、页面默认2在途，失败有限退避，probe取配置及剩余窗较小者。可信D+reconcile或首次未知核实窗固定，不刷新续期；耗尽停循环、显示待核实，以后显式回页仅一次GET。未核实不显示已失败/已保存，不自动POST；显式合法重发才建立新身份，资格来自[服务端资格接口](../chat-emotion/api.md#resend-eligibility)，POST再次校验。

按可信message ID、generation及十进制revision就地收敛；旧GET/SSE不覆盖新版本，assistant按ID去重，迟到history用户排回复前。资格GET不能覆盖其在途期间的新状态；全部异步POST/reader退出写UI须原user/UI epoch/send session/当前record匹配。

transport计时覆盖整个SSE读取，按首次submitted+180秒+margin或可信effectiveD+margin，finally才清timer。隐藏/离页/离线/退出仅停止本地等待，不取消服务端任务、不把未知判failed、不自动重发；本账号合法未知继续待核实，新账号不显示旧流提示。原页面视觉、键盘、300ms防连点及历史分页规则保持。

### BGM 页面生命周期

未激活壳入口时，各旧HTML继续增量加载BgmPreferences/Output/Controller/Catalog/Player/Session/Page共用模块；激活后的AppShell服务与页面适配遵循下文源码契约。Index、Feed、Chat、Settings按既有开放页策略接入，Diary、Memory、Relationship在自身门禁成立后接入，Login临时阻断但保留旧会话；Admin不接入。共享protected-home-modal实际离页前停止BGM，同页登录弹窗不改变音乐意图。首页加载层音乐暂停入口与后续正文使用同一实例，音乐失败/等待不参与HomeStartup截止或释放条件。

同标签会话须验证可读可写；2000ms本地检查点和关键动作保存，隐藏立即停播，BFCache/可见返回先读取最新暂停/关闭/人工恢复状态再判断恢复资格。存储失败保守禁用基于旧记录的自动出声并提示跨页受限；五项长期偏好与账号往返保持独立。完整字段见[BGM契约](../bgm/api.md)，本地部署证据及真机/完整流程未验项以[BGM唯一结项记录](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)为准。


### 主页 BGM 唱片与面板（STEP-014）

第五格改为公开音乐入口，前四格与关系/日记原门禁保持。`bgm-home.js`调用同页BgmPlayer，使用`bgm-record.js`单个唱片按钮在入口/面板间移动；打开和收起仅改变界面，不授予播放资格或解除会话关闭。玻璃面板提供序号/当前播放音柱、名称/状态歌单、统一SVG播放暂停/下一首、细轨音量与发光小滑块及本次关闭；唱片播放时显示音柱角标与呼吸光晕，暂停、页面隐藏或减少动态效果时停止动画。长曲名完整换行；没有歌词、作者、时长、进度拖动、歌单行封面。统一图像规则和参数见[BGM契约](../bgm/api.md)。

支持遮罩、Escape、浏览器返回、收起按钮和头部下拉；列表滚动/音量拖动独立，打开时隔离背景焦点和滚动，关闭恢复唱片焦点。当前面板按内容自适应增高，上限为520px与可视高度减12px的较小值，列表保底100px（普通40px行约两首半）；两首完整展示，多曲到上限后内部滚动。音量input命中区44px、滑块22px，仅在滑条范围禁用触摸滚动。小视口/横屏受可视高度约束并允许面板滚动至控件；安全区与visualViewport键盘缩减参与布局。默认400ms面板/唱片过渡，减少动态效果和可选动画API失败采用静态可用控件。桌面Safari正式页已有部分操作证据；手机/微信、实际软键盘及未覆盖布局仍保留为未验，桌面缩小视口不替代真机。

正式音量input即时更新BGM输出，change/pointerup/blur合并提交本地偏好；pointercancel回退未提交预览。设备音量降级仅提供明确静音/取消静音，不能显示无效精确滑杆。设置渐变开关经输出适配器立即收敛当前渐变，自动播放仍只写下次访问偏好；两者不授予播放意图，原motion权限和倾斜授权不变。


### 内容页与设置页 BGM 气泡（STEP-015）

Feed/Diary/Memory/Relationship/Chat/Settings共同加载bgm-record.js、bgm-bubble.js和bgm.css；受保护页先通过原门禁，主页/独立登录/Admin不挂载。展开为横向SVG图标加文字的播放暂停/手动恢复及本次关闭，按展开区域与唱片的真实联合边界避让，空白收起不断音；关闭立即停播并移除气泡，设置页不能绕过关闭重开。目录未明或暂时失败保留恢复入口，确认空目录不留下无用按钮。

右侧上下拖动按会话可用高度比例保存，经过显式页面安全区与visualViewport限位；聊天避开输入发送，记忆避开底栏/recenter，设置避开开关/可点行/表单与退出按钮。图片/评论/登录/确认/抽屉/升级等已命名覆盖层临时隐藏控件，结束按最新关闭/恢复状态处理。字段、采用参数和本地验证限制见[BGM契约](../bgm/api.md)；真机、实际键盘与记忆抽屉操作待补证，不以注入状态代替实际交互。

#### BGM 与真实通话准备

主页既有登录/忙碌/浏览器能力拒绝和视频占位入口不关闭BGM。VoiceEntry完整能力预检通过后，先关闭本次音乐再进入用途说明/采麦；取消、拒麦、通话结束均不自动复播，只有清理完成后主页明确播放/选曲可重开。接点见[语音生命周期](../realtime-voice/api.md)和[BGM互斥](../bgm/api.md)。本地Docker/Chrome已有真实采麦与输出前停播、挂断/取消/回复结束保持关闭及人工重开证据；成功重连、实际权限拒绝、完整失败创建清理和其他目标终端仍未覆盖。

本版BGM于2026-10-21按用户明确决定以“开发交付完成、未验项保留”结项；用户人工测试反馈未说明具体设备/用例，不据此新增全量通过。已有主页v2人工验收及Q201等非BGM边界保持各自原记录，BGM结项和延期验收只见[唯一执行记录](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)。

## AppShell 源码增量（2026-10-23）

源码已实现八页AppShell；只有完整入口被显式激活后才使用壳。此处同步已实现行为，不表示已通过完整目标设备验收或已在生产启用。正式业务API、JWT、数据库与OSS/CORS保持原契约。当前候选、运行环境、已验/待验及恢复位置只见[唯一进度§8](../../../design/h5-appshell/steps-verified.md#8-h5-appshell-step进度)。

<a id="appshell-delta-01"></a>
### AppShell构建与入口

构建：内容寻址 `/static/app-builds/aps1-<24hex>/`，schema=1 manifest 包含 URL、SHA256、MIME、字节数、传递依赖；壳固定 manifest 摘要与入口 SRI。缺项/混代/完整性失败停止加载，不回退可变资源。版本目录不可覆盖，旧资源保留规则见下述支持窗口。

<a id="appshell-delta-02"></a>
### AppShell页面生命周期

生命周期：`mount(PageContext) -> {unmount,captureState?}`。PageScope 先失效再取消/清理；迟到资源仍实际释放；页面状态与运行资源分离。八个页面已采用该装配协议。

<a id="appshell-delta-03"></a>
### AppShell导航事务

导航：只拦截八条已知同源路由；返回调用即登记navId，迟到pop先补偿原历史位置，较新意图才提交；已完成的补偿不重复执行。准备失败保留旧页，已提交或 pop 失败显示目标错误/重试；准备及挂载等待15秒。目标 blocker 在旧页释放前安装。参数变化 remount，相同语义不重复 push。六页返回（2026-10-25）：Chat/Feed/Diary/Memory/Relationship/Settings共用Router.back；当前受管历史通过schema/build/entryId/position/route校验且position>0时后退一条，否则replace首页；事务去重。保留query/hash、BGM单层历史与通话离页确认；同build刷新保留可信来路，快照仍只在内存。首页/Login不新增返回，认证与局部关闭语义保持。六页共用36px无色玻璃圆底、44px命中区、18px同款SVG；底色/边线/高光仅中性灰阶，顶栏对齐顶部安全区及左右12px，Diary/Settings用深色箭头。此增量仅AppShell，旧独立HTML回退分支沿用原实现。

<a id="appshell-delta-04"></a>
### AppShell历史与快照

历史：`history.state.__lxmAppShell` schema/build/entryId/position/route/overlay，合并保留外部字段。音乐面板一层历史，关闭共用事务。页面私有快照只在内存，按 entryId+principal+schema，16条/总2MiB/单条128KiB LRU；不接受 history.state 作为页面快照。

<a id="appshell-delta-05"></a>
### AppShell身份代次与401

身份：唯一 AuthService 管理 principal/authEpoch/authAttempt。请求及响应解析/SSE等待均校验原身份和页面代次。401保留原四类策略，清token后按自身新epoch检查每次等待。同源 storage 原生事件中央对账；本页显式通知。

访问交接：受保护页401及独立Login回退先取得事务自己的access阻断再清身份；私有路由守卫/显式回首页登录同样覆盖交接等待。新导航或新身份取消原事务，完成/失败归还原句柄，再由当前有效页按最新意图对账。同页共享登录窗、interactive-modal和silent-visitor不因此暂停音乐。

<a id="appshell-delta-06"></a>
### AppShell共享表单归属

认证：弹窗绑定 session/attempt/route，关闭和卸载清密码及焦点定时。共享注册接受token、恢复当前页一次；独立注册/重置回登录填账号、不自动登录。退出确认及HTTP返回后均检查原身份；不重放被阻写操作。

<a id="appshell-delta-09"></a>
### AppShell通话离页确认

D-02：离页确认“继续通话”留当前页，“结束并离开”停止本地资源后导航；共享确认框必须处于通话层之上，拥有滚动锁、inert、键盘焦点和取消归属。取消/挂断/回页不自动恢复本次已关闭BGM。

<a id="appshell-recovery"></a>
### AppShell真实文档恢复

文档生命周期统一管理hidden/pagehide/freeze/pageshow/resume，真实恢复顺序为身份→历史→存储→通话owner→阻塞→视图→声音，恢复代次只执行一次。旧页scope/导航作废，私有内容遮蔽并按最新主体重挂，声音最后对账。

<a id="appshell-pages"></a>
### AppShell八页装配

Home/Chat/Diary采用显式mount/unmount。Home保持原加载时限、场景和私有门禁；Chat保留原提交request_id/绝对截止/generation/BIGINT revision与有限只读核实、不重发；Diary沿用仅登录准入、分页items与原read语义。页面草稿/条目快照只保留有界普通数据，身份变更清私有缓存，旧页迟到回调不可写入。

<a id="appshell-delta-12"></a>
### AppShell私有快照与只读恢复

Chat滚动锚点包含source和稳定ID，仅重读原分页深度；Diary返回读回服务端真值，成功read事实不回退，恢复展开不产生新read写入。共享私有草稿清理同时覆盖原sessionStorage.chat_draft。

<a id="appshell-delta-13"></a>
### AppShell Feed挂载与服务器真值

Feed每有效挂载认证后enter一次、SSE一条；访客只公共列表/头部。返回读服务器真值，只重读先前分页深度，按既有稳定ID核对列表/评论内容、顺序及去重。未知写响应只读核实，不重放点赞/评论。曝光阈值与3秒停留保留，返回重新计时，旧页上报/重连全失效。

<a id="appshell-delta-14"></a>
### AppShell覆盖层与清理

Feed评论和图片预览由当前实例拥有滚动锁、背景inert、焦点及图像手势监听；退出完整释放。预览不另增加历史条目。加载图像失败/慢响应有限等待，不阻塞页面。

<a id="appshell-delta-15"></a>
### 设置页身份与失败边界

Settings保留公开BGM开关/About和原私有区。登录资料只恢复一次，有效退出停留Settings访客。logout确认和请求绑定原身份/路由，卸载AbortSignal中止本地等待，旧响应不得清新身份或跨页提示。

<a id="appshell-delta-16"></a>
### AppShell设置偏好与主动倾斜

五项设备偏好继续账号独立；自动播放只改变下次访问，关闭音乐不能在Settings重开。倾斜仅直接用户点击请求，取消/超时/失效身份或页面使迟到结果无效；权限等待10秒工程上限后可显式重试。密码在提交结束/折叠关闭/卸载清空，不入快照。

Settings仅将普通“关于”折叠状态存为collapsed.about；历史恢复展开时本实例只读一次公开背景，重复折叠/展开不重复取数。密码表单、授权等待、提交状态不恢复；主体/schema失效按新进入处理。

<a id="appshell-delta-17"></a>
### 设置页已知接口缺口

TD-024缺失账号设置接口与TD-025改密Schema偏差保持已知失败，不修复后端或宣称成功。对应错误呈现、回滚与敏感清理已在本地实际404/422验证，不能声称缺失接口已修复。

<a id="appshell-delta-18"></a>
### 独立登录语义

独立Login复用共享表单规则及AuthFormSession；注册/重置成功回登录并填账号，不自动登录；登录成功仅导航主页一次。切面板/退出/换身份使旧attempt失效，密码字段清空。记住账号和错误次数提示保持。

Login历史快照仅remember及勾选时的username；未勾选的同条目快照优先于旧持久账号默认值。快照仅有界内存，不新增持久保存，不保存密码/旧提交；失效或刷新按原remember_username初始化，不自动提交。

<a id="appshell-delta-22"></a>
### AppShell Memory图形资源与快照

Memory：显式mount，原doc_id/key/value及50条分页/图形交互；PageScope拥有renderer/纹理/材质/几何/RAF/手势/请求。迟到纹理显式释放；connection softTexture按实例拥有；无业务API变化。快照仅view/selectedId，删除的选中项关闭。页面返回沿用共享可信历史规则，不再限制Home/Chat来源；无站内来路时replace首页。

<a id="appshell-delta-23"></a>
### AppShell Relationship参数与分页

Relationship：显式mount，原detail/growth-log字段、每页20条、按日分组及等级/成长规则不变。原id去重保序；快照仅滚动/焦点/权益折叠/已读页数cursor，恢复最多100页为工程上限，手动分页无此上限。Router只消费just_leveled_up=true并保留其他query/hash/history；快照不保存可逆的消费状态。原300ms数值动画、500ms升级延迟/300ms淡出归本实例；OverlayManager拥有锁/inert/焦点，卸载立即清理。无新成长写入。

<a id="appshell-delta-27"></a>
### AppShell双入口兼容

Nginx精确八个旧H5地址优先app-entry.html；未激活则旧HTML。根302首页及未知404保留；模板、app源码不是独立入口。FastAPI已知地址同一入口，根/未知H5以initialPage=login直接初始化；没有激活文件则原登录/独立HTML。入口读取一次后返回，避免回退删除造成stat/open竞争。

<a id="appshell-delta-28"></a>
### AppShell缓存与真实404

壳no-cache；static/app-builds完整不可变资源200/304长缓存，缺模块/模板/CSS/Worklet真实404。API/Admin/SSE/WS及BGM上传location保留原语义；不更改业务协议、JWT、数据库、OSS/CORS。源码已接通；当前是否激活以唯一执行记录与实际入口为准。

<a id="appshell-delta-29"></a>
### AppShell IME与资源清理

八页资源归PageScope；Feed返回调用Router.back。Chat中文组合输入期间及isComposing/keyCode229的Enter不发送，普通Enter保留原发送语义。Home/Chat预加载图完成后解绑事件，在途切内联空图取消，避免空src原生图片残留。

Settings情绪头像采用同样清理规则：已完成图仅解绑回调，在途图切内联空图取消；坏图保留默认头像，旧实例/身份迟到结果不能写当前头像。资源旅程须包含真实非空情绪DTO及慢图、失败图分支。

<a id="appshell-delta-33"></a>
### AppShell发布与回退

发布完整资源校验后才以入口摘要CAS原子替换共享app-entry.html，按摘要备份旧入口；缺资源/摘要损坏/CAS冲突不切换。Nginx与FastAPI分别HTTP验证及失败回退，入口文件原子性不等于两服务部署原子性。

<a id="appshell-delta-34"></a>
### AppShell版本寻址与原生Worklet

两代驻留构建完整保留，实际VoiceAudioTransport经原生AudioContext/addModule加载各自锁定Worklet并创建处理器/输出PCM；真实缺失时明确失败，不走可变fallback。回退仍保留新壳资源，默认无自动清理/到期删除。

<a id="appshell-delta-35"></a>
### AppShell支持窗口与维护窗口

当前、上一代及所有可能活跃构建持续支持；没有旧文档全结束证据或另行批准的受控重新载入窗口就保留。首次backend代码更新选择受控维护窗口；原进程语音owner不跨进程迁移，文字原持久核实规则不变，不宣称灰度或零中断。

<a id="appshell-entry-experience"></a>
### AppShell 每文档开场（2026-10-23）

每次新文档 / 刷新显示一次开场；同文档路由、返回和后台 / BFCache 恢复不重建。完整复用原加载层背景、头像、昵称、昵称下文案及蒙版，准备与授权期间保持同一构图；底层页面约8px模糊并隔离输入；主按钮在一次原始点击内开启音乐并申请方向权限，允许或拒绝后约800ms退去遮罩。系统减少动态使用约120ms短淡出并关闭倾斜；主页动效关闭仍有效。原生权限框由浏览器管理，不以页面自制弹窗替代。

按用户最新确认，进度完成后仅底部进度区域约550ms淡出并交叉淡入音乐 / 倾斜操作区；背景、头像及光效、昵称、昵称下文案、渐变/暗角蒙版保留同一DOM、样式与位置，不再整屏切换。沿用原约3秒视觉进度及完成保持500ms，底部过渡结束才启用“开启并进入”和“直接进入”。减少动态使用约120ms短淡出；短屏允许在开场容器内滚动到操作区。保留8秒准备降级上限；进度是视觉准备反馈，不代表下载字节或真实音频可播放状态。

2026-10-24按钮视觉增量：统一开场主按钮采用独立 `css/invitation-button.css` 组件，冰蓝—紫色—玫粉渐变，呼吸2.6秒、流光3.6秒、渐变单程5.2秒；仅原生按钮启用后开始循环，禁用或系统减少动态时停止。文案仅更新独立标签，装饰不拦截点击。移除“直接进入”下方的音乐与倾斜附注，其业务语义不变；不延后原始点击中的音乐/方向调用，不更改加载与权限等待节奏。

“直接进入”本次暂停音乐、不申请方向、不使用旧会话倾斜标记；新文档初始化即关闭旧倾斜选择。缺设备、不安全上下文、权限拒绝 / 异常或音乐失败均不阻塞页面。权限等待10秒后仅开放显式跳过，未返回前不自动揭示页面；后台或身份变化取消本次结果，迟到结果不生效。首屏资源准备8秒上限不绕过上述取消边界。开场销毁为终态；迟到的资源准备、页面就绪或转场回调不得恢复阶段、写回全局开场标记或重新安排定时器，重复销毁不得清理后续所有者的状态。开场完成前场景不监听方向，完成后沿用现有首个有效事件基准。

非主页直达保留原路由与访客访问规则；需要自动登录窗时等开场结束后重检路由 / 身份再展示，隐藏表单不得抢焦点。麦克风仍仅由现有发起通话流程申请。此节覆盖 AppShell 下早期加载层节奏和“仅设置页申请倾斜”的旧限定；旧 HTML 回退分支不受本次增量影响。源码、本地验证与未验设备边界见[开场设计及接入记录](../../../design/h5-entry-experience/设计说明.md#产品接入验证2026-10-23)。


2026-10-24曾在本地部署中实施入口收拢；本机端口、地址及别名跳转不属于本次共享配置。AppShell 八页路由、入口选择与缓存规则随源码交付。2026-10-25本地桌面设置页／退出弹窗复查通过；手机入口因LAN地址变化不可用，用户确认恢复延期，实体手机验收仍未完成。生产未部署。历史本地配置及验证记录留在本机，验收范围与延期决定见[桌面复查收尾](../../../design/h5-entry-experience/设计说明.md#桌面范围契约复查与收尾2026-10-25)。
