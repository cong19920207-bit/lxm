<!-- prd-delivery-harness-meta {"schema_version":2,"run_id":"20260802T095138Z-open-login","artifact":"steps_draft","owner_phase":"prd-to-steps","state":"STEPS_DRAFTED","outcome":"PASS_WITH_RISKS","code_status":"NOT_STARTED","source_digest":"819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f"} -->
# 未登录可用功能开放与登录弹窗改造：STEP 草稿

> Harness: phase=prd-to-steps; state=STEPS_DRAFTED; outcome=PASS_WITH_RISKS; code_status=NOT_STARTED

> 本文是待完整复审的草稿，不代表已验证、可执行或已开始开发。业务代码状态为 `NOT_STARTED`。

## 1. 冻结输入

- PRD：`prd-open-login`，v1.0。
- 用户补充决定：UD-01～UD-03，全部采用 Phase 0 推荐方案 A。
- 需求：C1～C18、CSTR-01～CSTR-06、UD-01～UD-03，共 27 项。
- 验收：AC-01～AC-07，共 7 项。
- 排除：游客身份/试聊/数据继承、找回密码加固、第三方登录、数据库新增表字段、删除独立登录页。
- 风险：R-01～R-06；其中技术债全局编号需要实施前停止门。
- 来源摘要：`819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f`。

## 2. STEP 总览

| STEP | 单一目标 | 前置依赖 | 主要验收 | 草稿状态 |
|---|---|---|---|---|
| STEP-001 | 建立后端可选鉴权并保证匿名只读响应无用户数据 | 无 | AC-07 | `draft` |
| STEP-002 | 建立共享登录弹窗与分场景认证状态处理 | 无 | AC-06 | `draft` |
| STEP-003 | 实现首页访客降级态 | STEP-001、STEP-002 | AC-01 | `draft` |
| STEP-004 | 实现 Feed 访客只读态与登录后恢复 | STEP-001、STEP-002 | AC-02、AC-07 | `draft` |
| STEP-005 | 实现 Settings 访客展示分层 | STEP-001、STEP-002 | AC-03 | `draft` |
| STEP-006 | 实现 Chat 无私有数据访客壳与交互门禁 | STEP-002 | AC-04 | `draft` |
| STEP-007 | 统一三个受保护页面的首页弹窗回退 | STEP-002 | AC-05 | `draft` |
| STEP-008 | 完成契约、测试与跨页面交付门禁 | STEP-001～STEP-007 | AC-01～AC-07 | `draft` |

## 3. 需求 → STEP 映射

| 需求 ID | STEP |
|---|---|
| C1 | STEP-003、STEP-004、STEP-005、STEP-006、STEP-007 |
| C2、C3、C4、C5、C6 | STEP-003 |
| C7 | STEP-001、STEP-004 |
| C8 | STEP-004 |
| C9 | STEP-006 |
| C10 | STEP-005 |
| C11、C12 | STEP-002 |
| C13 | STEP-002、STEP-008 |
| C14、C15 | STEP-002、STEP-007 |
| C16 | STEP-002、STEP-003、STEP-004、STEP-005 |
| C17 | STEP-001 |
| C18 | STEP-006、STEP-008 |
| CSTR-01 | STEP-003 |
| CSTR-02 | STEP-002 |
| CSTR-03 | STEP-001、STEP-002、STEP-003、STEP-004、STEP-005 |
| CSTR-04 | STEP-001、STEP-004 |
| CSTR-05 | STEP-001、STEP-008 |
| CSTR-06 | STEP-002 |
| UD-01 | STEP-002 |
| UD-02 | STEP-004 |
| UD-03 | STEP-006 |

## 4. 验收 → STEP 映射

| 验收 ID | STEP | 覆盖方式 |
|---|---|---|
| AC-01 | STEP-003、STEP-008 | 首页访客态专项验证 + 集成交付门禁 |
| AC-02 | STEP-004、STEP-008 | Feed 匿名只读/写门禁专项验证 + 集成交付门禁 |
| AC-03 | STEP-005、STEP-008 | Settings 展示分层专项验证 + 集成交付门禁 |
| AC-04 | STEP-006、STEP-008 | Chat 访客壳/主动交互专项验证 + 集成交付门禁 |
| AC-05 | STEP-007、STEP-008 | 三个受保护页面导航/401 专项验证 + 集成交付门禁 |
| AC-06 | STEP-002、STEP-008 | 三面板与成功回调专项验证 + 集成交付门禁 |
| AC-07 | STEP-001、STEP-004、STEP-008 | API 响应字段断言 + Feed 页面验证 + 集成交付门禁 |

## 5. 依赖关系

```text
STEP-001 ─┬─> STEP-003 ─┐
          ├─> STEP-004 ─┤
          └─> STEP-005 ─┤
STEP-002 ─┬─> STEP-003 ─┤
          ├─> STEP-004 ─┤
          ├─> STEP-005 ─┤
          ├─> STEP-006 ─┤──> STEP-008
          └─> STEP-007 ─┘
```

STEP-001 与 STEP-002 可以并行；STEP-003～STEP-007 在各自前置满足后可并行；STEP-008 必须等待所有功能 STEP 完成。

## 6. 完整 STEP 提示词

### [STEP-001] 后端可选鉴权与匿名响应隔离

**阶段状态**：`draft`

**目标**：仅把 PRD 指定的三个只读接口改为可选鉴权，并保证匿名响应不查询或返回任何用户绑定数据。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C7 | Feed 匿名只读时不展示私有评论和 `user_liked` | `PRD` |
| 需求 | C17 | 可选鉴权只用于 Feed list/header 与 App persona-background | `PRD` |
| 约束 | CSTR-03、CSTR-04、CSTR-05 | 失效 token 可被前端识别；匿名响应无用户字段；不新增表字段 | `PRD` |
| 验收 | AC-07 | Feed/App 匿名响应不夹带用户绑定字段 | `PRD` |

**前置依赖**：无。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `backend/utils/auth_middleware.py` | `existing` | `REPO_BASELINE` | `repo-auth-middleware` / `backend/utils/auth_middleware.py` | 复用现有 Bearer、JWT 与封禁校验 |
| `.venv-step001/lib/python3.11/site-packages/fastapi/security/http.py` | `existing` | `RUNTIME` | `runtime-fastapi-http-security` / `.venv-step001/lib/python3.11/site-packages/fastapi/security/http.py` | 核实 `auto_error=False` 对缺头与错误 scheme 均返回 `None` |
| `backend/routers/feed.py` | `existing` | `REPO_BASELINE` | `repo-feed-router` / `backend/routers/feed.py` | 精确切换 list/header，确认写路由不变 |
| `backend/services/feed_service.py` | `existing` | `REPO_BASELINE` | `repo-feed-service` / `backend/services/feed_service.py` | 建立 `user_id=None` 隔离分支 |
| `backend/routers/app.py` | `existing` | `REPO_BASELINE` | `repo-app-router` / `backend/routers/app.py` | persona-background 可选鉴权 |
| `tests/test_app_persona_background.py` | `existing` | `REPO_BASELINE` | `repo-test-app-persona` / `tests/test_app_persona_background.py` | 修改匿名 401 旧断言并补坏 token 用例 |
| `tests/test_step015_feed_service.py` | `existing` | `REPO_BASELINE` | `repo-test-feed-service` / `tests/test_step015_feed_service.py` | 补匿名列表字段与查询隔离用例 |
| `get_current_user_optional` | `planned` | `PLANNED` | 不适用 | 新可选依赖；仅内部符号，不新增外部接口 |

**输入**：

- Phase 0 已确认的 C17 精确接口白名单。
- 现有 `get_current_user` 的 token、封禁与 HTTP 401 行为。
- 现有 Feed 列表过滤、分页、展示计数和 `actual_publish_time` 懒惰写回逻辑。

**输出**：

- 三个只读接口支持无 Authorization 请求。
- 有效 token 继续返回登录用户的既有个性化字段。
- 匿名 Feed 条目不包含 `user_liked`、`comments` 或其他用户绑定字段；展示评论数只使用匿名可得部分。
- 其余 Feed 写接口、badge、enter、events 和所有非指定接口继续强制登录。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 缺少凭据 | 可选依赖返回 `None`，不抛 401 | C17、PRD 第 6 章 |
| 无效/过期凭据 | Authorization 头存在但为空、scheme 错误、token 伪造或过期时保持 HTTP 401，使开放页能够清理失效凭据 | C16、CSTR-03、现有强鉴权基线 |
| 匿名 Feed 私有字段 | 响应中不包含 `user_liked`、当前用户评论或其他用户绑定字段 | C7、CSTR-04、AC-07 |
| 数据结构 | 不新增数据库表或字段 | CSTR-05 |

**开发任务**：

1. 先补可选鉴权的完全无 Authorization 头、空 Bearer、错误 scheme、有效 token、伪造/过期 token 和封禁 token 测试；只有完全无头可进入匿名分支。
2. 实现可选依赖，复用现有 JWT 与封禁检查，避免复制后产生安全分叉。
3. 只替换 `GET /api/feed/list`、`GET /api/feed/config/header`、`GET /api/app/persona-background` 的依赖。
4. 调整 `list_feed` 类型与分支：匿名路径不得执行按用户评论或点赞查询，也不得先组装后删除可能泄漏的字段。
5. 保留列表可见性、游标、时间口径、展示数、Header 和 persona 回退逻辑；保留当前懒惰写回并用幂等测试覆盖 R-02。
6. 增加路由级断言，确认未携带 token 可访问三个 GET，坏 token 仍为 401，写接口无 token 仍为 401。

**不在本 STEP 范围内**：

- 不开放 `/api/feed/enter`、badge、events、like、comments、read。
- 不修改前端页面、登录弹窗或 401 UI 策略。
- 不新增游客身份、数据库迁移、限流业务规则或公开错误码。
- 不在本 STEP 写正式 Contract；由 STEP-008 同步。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 请求三个白名单 GET | HTTP 成功；只返回公共内容 | AC-07 |
| 正常 | 有效 token 请求 Feed list | 保留登录用户既有 `user_liked` 与私有评论语义 | AC-07 |
| 异常 | 过期、伪造或封禁 token 请求白名单 GET | HTTP 401，不静默当作匿名用户 | AC-07 |
| 异常 | Authorization 头为空、使用非 Bearer scheme 或 Bearer 凭据为空 | HTTP 401，不按无头匿名请求处理 | AC-07 |
| 边界 | 匿名 Feed 有帖子、点赞和多个用户评论 | 响应无用户字段，不执行用户维度查询；展示计数不泄漏评论正文 | AC-07 |
| 边界 | 无 token 请求任一 Feed 写接口 | HTTP 401，业务处理器不执行 | AC-07 |

**完成标志**：

- [ ] 三个白名单 GET 的匿名/有效/无效 token 测试通过
- [ ] 匿名响应字段和查询隔离断言通过
- [ ] 其余写接口强鉴权回归通过
- [ ] 无模型、迁移或新增持久化字段
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-001 状态、验证命令与输出、变更文件、接口矩阵、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-002] 共享登录弹窗与认证状态策略

**阶段状态**：`draft`

**目标**：提供可由各页面调用的三面板登录弹窗和按请求场景区分的认证失效处理，同时保持独立登录页现有入口与行为。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C11、C12、C13 | 全局三面板弹窗；保留独立登录页；找回密码不加固 | `PRD` |
| 需求 | C14、C15、C16 | 受保护页跳首页弹窗；开放页 401 静默访客化 | `PRD` |
| 约束 | CSTR-02、CSTR-03、CSTR-06 | 默认登录面板；清坏 token；成功回调且不新增持久状态 | `PRD` |
| 决定 | UD-01 | 弹窗注册成功直接保存 token；独立登录页行为不变 | `USER_DECISION` |
| 验收 | AC-06 | 三面板与独立页能力一致，成功后不跳离当前开放页 | `PRD` |

**前置依赖**：无。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 当前 request/saveToken/clearToken/checkLogin/goToRelationship |
| `frontend/pages/login.html` | `existing` | `REPO_BASELINE` | `repo-login-page` / `frontend/pages/login.html` | 三面板 markup、校验与提交逻辑来源 |
| `backend/routers/auth.py` | `existing` | `REPO_BASELINE` | `repo-auth-router` / `backend/routers/auth.py` | 确认 register 已返回 token、reset 维持现状 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | 共享 H5 静态契约回归入口 |
| 共享弹窗公开调用面 | `planned` | `PLANNED` | 不适用 | 内部函数名按实现时现有命名风格确定 |
| 受保护页到首页的单次弹窗信号 | `planned` | `PLANNED` | 不适用 | 内部传递机制；不得变成持久用户数据 |

**输入**：

- 现有 login.html 的 panel-login/panel-register/panel-reset、校验、登录、注册、重置逻辑。
- 当前公共 request 对所有 401 强制跳独立登录页的行为。
- UD-01 对弹窗注册成功与独立页注册成功的明确分叉。

**输出**：

- 全局可调用的登录弹窗，默认登录面板，可切换注册和找回密码。
- 当前页可传入一次性成功回调；登录或弹窗注册成功后关闭弹窗并刷新本页数据。
- 公共请求层允许调用方明确选择开放页静默访客化、受保护页首页弹窗回退、主动交互弹窗三类行为；内部命名由实现时确定。
- 独立 login.html 保留直接入口、登录后去首页、注册后回登录面板的既有用户体验。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 弹窗默认面板 | 登录 | CSTR-02 |
| 弹窗登录成功 | 保存 token、关闭弹窗、调用当前页成功回调，不跳页 | C11、CSTR-06 |
| 弹窗注册成功 | 保存 register 响应 token、关闭弹窗、调用成功回调 | UD-01 |
| 独立页注册成功 | 保持“注册成功，请登录”并切回登录面板 | UD-01 |
| 找回密码 | 完整保留现状，不增加邮箱/短信/第三方身份校验 | C13 |

**开发任务**：

1. 先建立共享弹窗的结构、三面板切换、校验、提交防重、关闭和成功回调契约测试。
2. 从独立登录页复用已核实的规则与请求语义，避免两套密码/用户名校验漂移；具体复用结构以不改变独立页行为为门禁。
3. 实现弹窗登录成功和 UD-01 注册成功分支；重置成功仍切回弹窗登录面板。
4. 重构公共 401 处理，使页面/调用点能够选择 PRD 规定的三类结果；未显式迁移的既有调用点不得意外改变。
5. 实现受保护页面跳首页后只自动打开一次弹窗的内部信号，消费后清理，避免刷新/后退循环；不添加用户业务字段。
6. 保留 `clearToken()` 的现有会话清理，并确保过期 token 在访客化或弹窗前先清除。
7. 为键盘焦点、遮罩关闭、重复打开、重复提交和成功回调仅执行一次补边界验证。

**不在本 STEP 范围内**：

- 不直接改造 index/feed/settings/chat/diary/memory/relationship 的页面业务分支。
- 不改变认证 API 请求/响应、密码策略、找回密码安全模型或第三方登录。
- 不删除或改写独立 login.html 的用户可见流程。
- 不决定页面刷新函数的具体名称；由对应页面 STEP 接入。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 当前开放页主动打开弹窗并登录成功 | 弹窗关闭，只调用一次成功回调，URL 不跳到首页 | AC-06 |
| 正常 | 弹窗注册成功 | 使用响应 token 建立登录态并回调；不要求二次登录 | AC-06 |
| 正常 | 独立 login.html 注册成功 | 仍切回登录面板，不自动建立登录态 | AC-06 |
| 异常 | 登录失败、注册失败、重置失败 | 弹窗保留，展示既有错误语义，不执行成功回调 | AC-06 |
| 边界 | 重复点击提交或重复触发 401 | 请求不重复提交；同一弹窗/回调不重复执行 | AC-06 |

**完成标志**：

- [ ] 三面板正常/失败/切换与焦点行为验证通过
- [ ] 弹窗和独立页的注册成功分叉符合 UD-01
- [ ] 三类 401 策略可由调用点明确选择
- [ ] 找回密码能力未扩大，独立登录页行为未改变
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-002 状态、验证证据、变更文件、弹窗调用契约、401 策略矩阵、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-003] 首页访客降级态

**阶段状态**：`draft`

**目标**：让未登录或开放页会话失效的用户看到 PRD 定义的首页访客态，同时不发起任何纯个性化请求。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C1、C2、C3、C4、C5、C6 | 首页开放；关系/日记/角标/天数/快捷栏按访客规则降级 | `PRD` |
| 需求 | C16 | 首页个性化 401 静默访客化 | `PRD` |
| 约束 | CSTR-01、CSTR-03 | 访客不发个性化请求；坏 token 清理后访客化 | `PRD` |
| 验收 | AC-01 | 首页访客浏览可用且降级正确 | `PRD` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 匿名 Feed list 可用 | 无 token 的 Feed list 路由测试通过 |
| STEP-002 | 登录弹窗与开放页静默 401 策略 | 弹窗/回调/静默访客化测试通过 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/pages/index.html` | `existing` | `REPO_BASELINE` | `repo-index-page` / `frontend/pages/index.html` | 当前入口、首页渲染与全部点击点 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 认证状态、弹窗和 goToRelationship |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | 首页静态契约回归 |
| 首页访客渲染分支 | `planned` | `PLANNED` | 不适用 | 内部函数名按现有 render 命名风格确定 |

**输入**：

- 当前 `loadPage()` 的 relationship/status、relationship/detail、diary/list、agent/unread-count 并发请求。
- 当前 `loadFeedHomeCard()` 的 badge/list 并发请求。
- 已确认访客展示文案和点击分叉。

**输出**：

- 无 token 首次打开首页直接完成访客渲染，不跳独立登录页。
- 关系胶囊使用陌生人默认态；日记卡使用 `diary-lock` 通用占位；未读模块隐藏；陪伴天数为“故事从今天开始”。
- Feed 预览只请求匿名 list，不请求 badge；快捷栏正常展示。
- 关系胶囊、日记卡和五个快捷项在访客点击时打开登录弹窗；Feed、Settings、Chat 公共页面入口仍可导航。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 陪伴天数访客文案 | “故事从今天开始” | C5 |
| 日记访客视觉 | 与已登录陌生人同为 `diary-lock`，内容为通用占位，点击行为不同 | C3 |
| 快捷栏 | 访客五项均弹窗；登录后记忆星云跳转、其余四项“敬请期待” | C6 |
| 首页 401 | 清 token，静默重绘访客态，不弹窗、不跳页 | C16 |

**开发任务**：

1. 先扩展首页静态契约与浏览器验收清单，覆盖访客文案、隐藏区、点击点和请求白名单。
2. 移除入口强制 `checkLogin()`，在初始化最早处判定有无 token；访客分支不启动四个个性化请求。
3. 增加独立访客渲染路径，不复用 `hideKnownDays()` 的整体隐藏行为来替代 C5 文案。
4. 调整 Feed 首页卡：访客只请求匿名 list，显式清空/隐藏未读回复和新动态角标，不调用 badge。
5. 把关系、日记和快捷项的认证判断放在导航/Toast 前；访客弹窗，登录态保持现状。
6. 让开放页个性化请求的 401 使用 STEP-002 静默策略，并保证只执行一次访客重绘。
7. 登录弹窗成功回调重新走登录态首页数据加载，避免重复 loader、时钟、visibility 监听或并发请求。

**不在本 STEP 范围内**：

- 不改变 Feed 列表页、Chat、Settings 或受保护页面逻辑。
- 不向访客请求 relationship、diary、agent badge 或 Feed badge。
- 不把 Chat 入口改成需登录；Chat 页面本身按 C1 开放。
- 不改变已登录首页既有文案、动画和路由。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | localStorage 无 token 打开 index | 页面不跳转；关系/日记/天数/角标符合访客定义 | AC-01 |
| 正常 | 访客点击关系、日记或任一快捷项 | 默认登录面板打开；未发生受保护导航 | AC-01 |
| 异常 | 携带过期 token，任一个性化请求返回 401 | token 清除，静默切访客态，不弹窗不跳页 | AC-01 |
| 边界 | 访客首页初始化与切回前台 | 网络中没有 relationship/diary/agent/badge 请求，Feed list 可刷新且监听不重复 | AC-01 |
| 边界 | 弹窗登录成功 | 原页加载登录数据，已登录快捷栏行为不变 | AC-01 |

**完成标志**：

- [ ] 首页静态契约和目标浏览器场景通过
- [ ] 访客网络请求白名单证据已保存
- [ ] 精确文案、隐藏区和全部点击分叉通过
- [ ] 登录态首页回归通过
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-003 状态、验证证据、首页网络请求清单、变更文件、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-004] Feed 访客只读态

**阶段状态**：`draft`

**目标**：让访客直接浏览公共 Feed 列表，并在不发起任何私有写入或实时连接的前提下把显式写交互引导到登录弹窗。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C1、C7、C8、C16 | Feed 开放只读；隐藏私有态和实时角标；401 静默降级 | `PRD` |
| 约束 | CSTR-03、CSTR-04 | 清坏 token；匿名响应/页面无用户绑定数据 | `PRD` |
| 决定 | UD-02 | 访客跳过 enter、badge、SSE 和两类已读上报 | `USER_DECISION` |
| 验收 | AC-02、AC-07 | 访客只读/写门禁；匿名接口无用户字段 | `PRD` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 匿名 list/header 与字段隔离 | 三个白名单 GET 测试及 AC-07 断言通过 |
| STEP-002 | 登录弹窗、成功回调与开放页 401 策略 | 弹窗和静默访客化测试通过 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/pages/feed.html` | `existing` | `REPO_BASELINE` | `repo-feed-page` / `frontend/pages/feed.html` | Feed 初始化、交互、SSE 与已读观察器 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 弹窗和静默 401 |
| `backend/routers/feed.py` | `existing` | `REPO_BASELINE` | `repo-feed-router` / `backend/routers/feed.py` | 确认只有 list/header 匿名 |
| `backend/services/feed_service.py` | `existing` | `REPO_BASELINE` | `repo-feed-service` / `backend/services/feed_service.py` | 匿名响应语义 |
| `tests/test_step015_feed_service.py` | `existing` | `REPO_BASELINE` | `repo-test-feed-service` / `tests/test_step015_feed_service.py` | Feed 服务回归 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | H5 访客门禁静态断言 |

**输入**：

- 当前 `initFeed()` 自动 enter、消息角标、列表、SSE 和已读观察器的顺序。
- 当前点赞乐观更新、评论面板、focus 锚点和 visibility 刷新逻辑。
- STEP-001 匿名响应与 STEP-002 登录成功回调。

**输出**：

- 访客加载 Header 和公共帖子列表，可查看文案、图片、话题、展示点赞/评论数。
- 访客不展示私有评论、不呈现已赞态，不调用 enter/badge/agent unread/SSE/comment-read/post-read。
- 访客点击点赞或评论时先打开登录弹窗，不做乐观更新、不打开评论输入面板、不发请求。
- 登录成功后原地切换为登录态 Feed，执行一次 enter 并恢复私有数据、角标、SSE 和已读观察器。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 访客可见 | 文案、图片、话题标签、展示点赞数、展示评论数、Header | C7 |
| 访客不可见 | 当前用户评论区、`user_liked` 状态、未读/SSE 角标 | C7、C8 |
| 访客初始化 | 仅 list/header；跳过 enter、badge、SSE 和已读上报 | UD-02 |
| 写交互 | 点赞和评论在任何本地状态变化前打开登录弹窗 | C7、UD-02 |

**开发任务**：

1. 先补 Feed 访客静态契约、API 响应和浏览器网络/交互验收。
2. 移除入口强制登录，拆分访客初始化与登录初始化，保持公共 Header/list 的加载/错误/分页体验。
3. 访客不调用 `loadMsgBadge()`、`/api/feed/enter`、`connectFeedSSE()`，也不挂载评论回复曝光或帖子停留已读观察器。
4. 匿名条目缺少 `user_liked`/`comments` 时安全渲染为未赞且无私有评论，不把缺字段当异常。
5. 在点赞乐观更新、评论面板打开和评论回复点击之前增加主动登录门禁；取消访客状态下的任何本地计数变化。
6. 对 visitor + `?focus=unread_reply` 忽略私有锚点，不发 enter；登录态保持既有定位行为。
7. 过期 token 的列表/个性化 401 清 token 后关闭 SSE/观察器并静默重建访客态。
8. 登录成功回调必须幂等恢复 enter、badge/SSE/观察器和私有列表，防止重复 EventSource、IntersectionObserver 或 enter。

**不在本 STEP 范围内**：

- 不匿名开放 enter、badge、events、like、comments 或 read API。
- 不新增游客点赞/评论草稿、匿名身份或登录后的自动重放写操作。
- 不改变 Feed 公共内容排序、游标、时间、图片预览或展示计数公式。
- 不新增限流业务值。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 打开 Feed | Header/list 正常；只显示公共字段 | AC-02、AC-07 |
| 正常 | 访客点击点赞或评论 | 弹窗打开；无写请求、无乐观更新、无评论面板 | AC-02 |
| 异常 | 旧 token 在初始化请求中返回 401 | 清 token，关闭私有资源，静默继续公共列表 | AC-02 |
| 边界 | 访客带 `focus=unread_reply` | 不调用 enter，不定位私有评论，公共列表可用 | AC-02、AC-07 |
| 边界 | 弹窗登录成功后切登录态 | enter/SSE/观察器各建立一次，私有字段恢复且分页不重复 | AC-02 |

**完成标志**：

- [ ] 访客网络中只有允许的公共请求
- [ ] 匿名字段、点赞/评论门禁和 focus 边界通过
- [ ] 登录成功后的私有能力恢复且无重复资源
- [ ] 登录态 Feed 全部既有回归通过
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-004 状态、验证证据、访客/登录请求矩阵、SSE/观察器数量证据、变更文件和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-005] Settings 访客展示分层

**阶段状态**：`draft`

**目标**：让访客只看到人设资料卡和“关于林小梦”，隐藏账号/偏好能力，并把退出登录位置转换为登录弹窗入口。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C1、C10、C16 | Settings 开放；访客展示分层；401 静默降级 | `PRD` |
| 约束 | CSTR-03 | 失效 token 清理后按访客态渲染 | `PRD` |
| 验收 | AC-03 | 访客板块隐藏且“关于林小梦”正常 | `PRD` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | persona-background 匿名可读 | 匿名/坏 token 路由测试通过 |
| STEP-002 | 登录弹窗、成功回调和静默 401 策略 | 弹窗与 401 策略测试通过 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/pages/settings.html` | `existing` | `REPO_BASELINE` | `repo-settings-page` / `frontend/pages/settings.html` | 资料卡、两私有板块、关于、退出按钮 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 默认状态语、弹窗与静默 401 |
| `backend/routers/app.py` | `existing` | `REPO_BASELINE` | `repo-app-router` / `backend/routers/app.py` | 关于内容公共来源 |
| `tests/test_app_persona_background.py` | `existing` | `REPO_BASELINE` | `repo-test-app-persona` / `tests/test_app_persona_background.py` | persona 匿名 API 回归 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | Settings 结构与分支断言 |

**输入**：

- 当前资料卡 `loadProfile()`、偏好 `loadSettings()`、关于懒加载和退出逻辑。
- STEP-001 公共 persona endpoint 与 STEP-002 登录成功回调。

**输出**：

- 访客进入 Settings 不跳转，资料卡使用默认头像/`DEFAULT_STATUS_TEXT`，不请求 relationship/status。
- “账号与安全”“陪伴与偏好”连同各自标题和内容完全隐藏。
- “关于林小梦”正常懒加载公共 persona-background。
- 退出按钮访客态显示“点击登录”并打开弹窗；登录后恢复私有板块、数据加载和退出行为。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 访客资料卡 | 正常展示，状态语使用现有 `DEFAULT_STATUS_TEXT`，不请求 relationship/status | C10 |
| 访客隐藏板块 | “账号与安全”“陪伴与偏好”标题与内容均不显示 | C10 |
| 访客可见板块 | “关于林小梦”正常展示并可加载 | C10 |
| 退出按钮访客态 | 文案“点击登录”，点击打开登录弹窗 | C10 |

**开发任务**：

1. 先补 Settings 访客/登录双态静态契约和浏览器验收。
2. 移除入口强制登录，建立一次性状态渲染，使标题与卡片成组隐藏，避免只隐藏控件留下空标题。
3. 访客跳过 `loadProfile()` 的 relationship 请求和 `loadSettings()`；直接应用默认资料卡。
4. 保留“关于林小梦”懒加载，并让匿名 persona 失败只影响该区块，不触发登录跳转。
5. 把退出按钮渲染成双态：访客为“点击登录”且不调用 logout；登录态保持现有确认和登出流程。
6. 个性化请求 401 时清 token、关闭私有交互并静默重绘访客态。
7. 登录弹窗成功回调恢复两板块、资料和设置加载、退出按钮；避免重复绑定和重复懒加载状态污染。

**不在本 STEP 范围内**：

- 不修复或实现用户偏好后端，也不清偿 TD-024/TD-025。
- 不加固找回密码或 Settings 改密码语义。
- 不改变 persona 内容、资料卡文案映射或已登录设置交互。
- 不修改其他页面。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 打开 Settings | 资料卡默认态、About 可见、两私有板块隐藏、按钮为“点击登录” | AC-03 |
| 正常 | 访客展开 About | 只请求公共 persona，成功展示角色背景 | AC-03 |
| 异常 | 有过期 token 且私有请求返回 401 | 清 token，静默访客化，不跳页不弹窗 | AC-03 |
| 边界 | 访客点击“点击登录”并成功登录 | 原页恢复私有板块和退出按钮，资料/设置各加载一次 | AC-03 |
| 边界 | 匿名 persona 加载失败 | 只显示 About 失败文案，其余访客页面保持可用 | AC-03 |

**完成标志**：

- [ ] Settings 双态结构、文案与请求矩阵通过
- [ ] About 匿名正常/失败分支通过
- [ ] 401 静默降级和登录恢复通过
- [ ] 已登录 Settings 回归通过
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-005 状态、验证证据、访客/登录 DOM 与请求矩阵、变更文件、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-006] Chat 访客壳与主动交互门禁

**阶段状态**：`draft`

**目标**：让无有效会话的用户停留在现有 Chat 页面壳中且不加载私有数据或触发模型调用，只在主动受保护交互时打开登录弹窗。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C1、C9、C18 | Chat 页面可见、操作需登录；不建游客试聊/身份 | `PRD` |
| 决定 | UD-03 | 无 token/过期 token 静默访客壳，不加载 timeline/Agent/badge | `USER_DECISION` |
| 验收 | AC-04 | 访客发送触发登录弹窗 | `PRD` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-002 | 登录弹窗、主动交互 401 和静默访客化能力 | 弹窗/401 策略测试通过 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/pages/chat.html` | `existing` | `REPO_BASELINE` | `repo-chat-page` / `frontend/pages/chat.html` | 初始化、timeline、Agent、badge、发送和重试 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 登录弹窗、清 token、受保护导航 |
| `docs/contract/current/chat-emotion/api.md` | `existing` | `CONTRACT` | `contract-chat-emotion-api` / `docs/contract/current/chat-emotion/api.md` | 保持聊天接口强鉴权和既有发送语义 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | Chat 静态结构回归 |
| Chat 访客初始化分支 | `planned` | `PLANNED` | 不适用 | 只初始化页面壳和输入交互，不拉私有数据 |

**输入**：

- 当前 initChat 的 draft、Feed badge、timeline、Agent tip、滚动和情绪初始化。
- 当前 handleSend/Enter/失败重试在请求前后的 DOM 状态变化。
- UD-03 对无 token 和初始化过期 token 的统一静默行为。

**输出**：

- 访客看到既有 Chat 页面壳和输入区，不显示锁定态引导页。
- 访客不读取本地用户草稿，不请求 timeline、Agent messages、Feed badge，不发 send/resend 或任何 LLM 相关请求。
- 发送按钮、Enter 发送、失败重试和受保护导航在访客主动操作时打开登录弹窗；Feed 公共导航仍可用。
- 登录成功后原地初始化一次登录态 Chat，不自动发送访客输入。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| Chat 访客展示 | 保留现有页面壳，不增加锁定态引导页 | C9、UD-03 |
| Chat 访客数据 | 不请求/展示私有 timeline、Agent 消息或 Feed badge | UD-03 |
| Chat 访客能力 | 不建立游客试聊或持久化游客数据；主动发送等操作打开弹窗 | C9、C18 |
| 初始化过期 token | 清 token 后静默进入同一访客壳，不自动弹窗 | UD-03 |

**开发任务**：

1. 先补 Chat 访客静态契约和浏览器网络/交互验收，明确“零私有请求、零 send/LLM 请求”。
2. 移除入口强制登录，拆分页面壳初始化与登录用户数据初始化；访客不执行 `loadDraft()`、Feed badge、timeline、Agent tip 或登录态滚动观察。
3. 在发送按钮、Enter 发送、失败重试和需要登录的页面导航最前面执行登录判断，防止先插入气泡、改状态或发请求。
4. 保留 Feed 公共入口；Memory/Relationship 等受保护入口由共享门禁打开弹窗，不让访客先进入受保护页再回跳。
5. 若主动发送期间 token 失效，撤销未完成的本地发送态、清 token并打开弹窗；初始化背景请求的 401 则按 UD-03 静默访客化。
6. 登录成功回调只初始化一次草稿、timeline、Agent、badge、滚动与情绪；不自动重放或发送访客此前输入。
7. 保持登录用户的 SSE、时间线、叹号重试、草稿和关系升级提示语义不变。

**不在本 STEP 范围内**：

- 不新增游客消息、设备 ID、预注册账号、LLM 配额或登录后数据继承。
- 不匿名开放任何 Chat/Agent API。
- 不修改聊天消息协议、错误码、SSE、时间线或重试业务规则。
- 不创建新的锁定态页面或引导文案。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 打开 Chat | 页面壳可见；无 timeline/Agent/badge/draft/LLM 请求 | AC-04 |
| 正常 | 访客点击发送或按 Enter | 登录弹窗打开；无气泡、无 send 请求、无草稿持久化 | AC-04 |
| 异常 | 初始化携带过期 token | 清 token，静默访客壳，不自动弹窗 | AC-04 |
| 异常 | 登录态在主动发送时 token 过期 | 本地发送态回滚并弹窗；不遗留幽灵消息 | AC-04 |
| 边界 | 弹窗登录成功 | 登录态初始化一次，不自动发送访客输入，既有 Chat 能力恢复 | AC-04 |

**完成标志**：

- [ ] Chat 访客网络零私有请求/零模型调用证据已保存
- [ ] 发送、Enter、重试与受保护导航门禁通过
- [ ] 初始化过期与主动交互过期分叉通过
- [ ] 登录态 Chat 回归通过
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-006 状态、验证证据、访客/登录请求矩阵、变更文件、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-007] 受保护页面统一首页弹窗回退

**阶段状态**：`draft`

**目标**：让 Diary、Memory、Relationship 在未登录直访或会话中途失效时统一跳到首页并只自动打开一次登录弹窗。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C1、C14、C15 | 三页维持登录可见；无会话或中途失效均跳首页弹窗 | `PRD` |
| 验收 | AC-05 | 三页直访与 token 失效均走统一回退 | `PRD` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-002 | 首页单次弹窗信号、受保护页 401 策略 | 登录弹窗和受保护回退契约测试通过 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `frontend/pages/diary.html` | `existing` | `REPO_BASELINE` | `repo-diary-page` / `frontend/pages/diary.html` | Diary 入口与请求失效处理 |
| `frontend/pages/memory.html` | `existing` | `REPO_BASELINE` | `repo-memory-page` / `frontend/pages/memory.html` | Memory 入口与请求失效处理 |
| `frontend/pages/relationship.html` | `existing` | `REPO_BASELINE` | `repo-relationship-page` / `frontend/pages/relationship.html` | Relationship 入口与请求失效处理 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | `repo-api-js` / `frontend/static/js/api.js` | 单次信号、清 token 与统一导航 |
| `docs/contract/current/diary/api.md` | `existing` | `CONTRACT` | `contract-diary-api` / `docs/contract/current/diary/api.md` | Diary 接口继续 Bearer |
| `docs/contract/current/memory-knowledge/api.md` | `existing` | `CONTRACT` | `contract-memory-knowledge-api` / `docs/contract/current/memory-knowledge/api.md` | Memory 接口继续 Bearer |
| `docs/contract/current/relationship/api.md` | `existing` | `CONTRACT` | `contract-relationship-api` / `docs/contract/current/relationship/api.md` | Relationship 接口继续 Bearer |

**输入**：

- 三个页面现有入口 `checkLogin()` 与各自 API 请求。
- STEP-002 的受保护页面回退和首页单次弹窗信号。

**输出**：

- 无 token 直访任一受保护页，不渲染私有页面数据，跳 `/pages/index.html` 后自动打开登录弹窗。
- 页面已加载后任一关键请求返回 401，先清 token，再执行相同首页弹窗回退。
- 不再以 `/pages/login.html` 为三页无会话或过期会话的目标。
- 登录成功后留在首页并刷新首页数据，不自动返回原受保护 URL。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 受保护页集合 | diary.html、memory.html、relationship.html | C1、C14 |
| 无会话回退 | 跳 index.html 并自动弹登录弹窗 | C14 |
| 中途失效回退 | 与无会话完全一致 | C15 |
| 登录后位置 | 当前已在首页；成功后刷新首页，不恢复原 URL | C14、C15 |

**开发任务**：

1. 先补三页静态入口与浏览器导航矩阵测试，覆盖直访和页面中途 401。
2. 用 STEP-002 共享受保护页门禁替换三处 `checkLogin()`，确保在页面私有初始化前完成导航。
3. 为三页请求选择受保护页 401 策略；首次 401 后清 token、停止后续请求/定时器/观察器并只导航一次。
4. 首页消费单次弹窗信号后立即清理，刷新、后退或重复 401 不得形成重定向/弹窗循环。
5. 保留独立 login.html 直接入口，但移除三页对它的自动导航依赖。
6. 登录成功后调用首页登录态刷新，不引入 return URL 或自动返回原页的未确认语义。

**不在本 STEP 范围内**：

- 不匿名开放 Diary、Memory、Relationship API 或页面内容。
- 不增加 return URL、登录后自动回跳、分享页预览或游客占位页。
- 不改变三模块的业务数据、关系等级、日记或记忆逻辑。
- 不修改登录/注册/找回密码表单本身。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 分别直访三页 | 各自只跳一次首页，首页自动弹一次登录弹窗 | AC-05 |
| 异常 | 三页加载中 token 过期且请求返回 401 | 清 token、停止私有加载、跳首页弹窗，不去 login.html | AC-05 |
| 边界 | 多个并发请求同时 401 | 只发生一次导航与一次弹窗信号 | AC-05 |
| 边界 | 在首页关闭弹窗后刷新或后退 | 不再次自动弹窗，不形成循环 | AC-05 |
| 边界 | 弹窗登录成功 | 留在首页并加载登录态首页，不自动回原受保护页 | AC-05 |

**完成标志**：

- [ ] 三页直访和中途失效导航矩阵通过
- [ ] 并发 401、刷新、后退无循环
- [ ] 三模块接口仍强鉴权
- [ ] 登录后位置符合 C14/C15
- [ ] 进度与证据已回传

**完成回传**：返回 STEP-007 状态、验证证据、三页导航矩阵、变更文件、来源变化和下一可执行 STEP；不得自动启动下一 STEP。

### [STEP-008] 契约、测试与跨页面交付门禁

**阶段状态**：`draft`

**目标**：在 STEP-001～STEP-007 全部完成后，用契约同步、自动化回归和浏览器矩阵证明本 PRD 的七项验收可交付且未扩大排除范围。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要 | 来源 |
|---|---|---|---|
| 需求 | C13、C18、CSTR-05 | 不加固找回密码、不建游客体系、不新增表字段 | `PRD` |
| 验收 | AC-01～AC-07 | 七项 PRD 检查项全部通过 | `PRD` |
| 技术债 | TD-AUTH-01、TD-AUTH-02 | PRD 本地编号需保留，但全局编号尚未确认 | `PRD` / `CONTRACT` |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001～STEP-007 | 全部功能实现、专项测试和完成回传 | 每个 STEP 均为 DONE 且完成标志有证据 |

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | `source_id` / `locator` | 用途 |
|---|---|---|---|---|
| `docs/contract/current/life-feed/api.md` | `existing` | `CONTRACT` | `contract-life-feed-api` / `docs/contract/current/life-feed/api.md` | 同步 list/header 可选鉴权和条件响应字段 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | `contract-h5-app-api` / `docs/contract/current/h5-app/api.md` | 同步 persona-background 匿名访问 |
| `docs/tech-debt.md` | `existing` | `CONTRACT` | `tech-debt-index` / `docs/tech-debt.md` | 核验全局技术债编号治理，不擅自新增编号 |
| `docs/tech-debt/active/core-user-auth.md` | `existing` | `CONTRACT` | `tech-debt-core-user-auth` / `docs/tech-debt/active/core-user-auth.md` | 识别既有 TD-025 与 PRD 风险重叠 |
| `README.md` | `existing` | `REPO_BASELINE` | `repo-readme` / `README.md` | 全量 pytest 门禁命令来源 |
| `tests/test_app_persona_background.py` | `existing` | `REPO_BASELINE` | `repo-test-app-persona` / `tests/test_app_persona_background.py` | App 匿名/坏 token 回归 |
| `tests/test_step015_feed_service.py` | `existing` | `REPO_BASELINE` | `repo-test-feed-service` / `tests/test_step015_feed_service.py` | Feed 匿名/登录响应回归 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | `repo-test-h5-static` / `tests/test_h5_static_contract.py` | 七页前端静态契约回归 |
| 浏览器网络与导航验收证据 | `planned` | `PLANNED` | 不适用 | 证明 DOM、导航、请求和弹窗真实交互 |

**输入**：

- STEP-001～STEP-007 的变更、专项测试结果和请求/导航矩阵。
- 当前正式 Life Feed/H5 App 契约与技术债索引约束。
- README 中已核实的全量测试命令。

**输出**：

- 当前正式契约准确描述匿名白名单、坏 token 401、登录/匿名条件字段和其余接口强鉴权。
- 七项 AC 的自动化与浏览器证据索引。
- 找回密码风险和游客体系排除项未被意外扩大；没有数据库迁移。
- PRD 本地 TD-AUTH-01/02 保留；如要进入全局技术债索引，先取得编号/别名决策，不自行写入。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 自动化总门禁 | 在项目根执行 `PYTHONPATH=. pytest tests/` | `REPO_BASELINE` README |
| 浏览器状态矩阵 | 无 token、有效 token、过期 token、弹窗登录/注册成功 | AC-01～AC-07、UD-01～UD-03 |
| 全局技术债编号 | 当前只使用权威索引已有 `TD-001`～`TD-037`；不自行分配新编号 | `CONTRACT` tech-debt-index |

**开发任务**：

1. 审核每个功能 STEP 的证据和实际变更，来源或行为变化时先回到最早受影响 STEP 复审。
2. 更新 Life Feed 当前契约：仅 list/header 可选鉴权、缺 token 与坏 token 分支、匿名字段集合、enter/badge/events/write 继续强鉴权。
3. 更新 H5 App 当前契约：persona-background 可无 token 访问，坏 token 行为与实现一致；不得把其他 App 接口泛化为匿名。
4. 运行针对性测试：`PYTHONPATH=. pytest tests/test_app_persona_background.py tests/test_step015_feed_service.py tests/test_h5_static_contract.py -q`。
5. 运行仓库全量门禁：`PYTHONPATH=. pytest tests/`；失败必须归因并修复本范围回归，不能用跳过或删断言掩盖。
6. 在浏览器逐页执行无 token、有效 token、过期 token、弹窗登录、弹窗注册矩阵，保存 URL、DOM、Network、SSE/观察器数量和无 LLM 调用证据。
7. 核对没有 Alembic 迁移、游客身份/试聊、第三方登录、找回密码加固、return URL 或自动重放写操作。
8. 对 TD-AUTH-01/02 只保留 PRD 本地标识和风险记录；若要修改权威技术债索引，立即停止并请求用户确认全局编号或别名方案。

**不在本 STEP 范围内**：

- 不把 Harness 当前规划行为误当作已执行的契约或代码修改。
- 不通过放宽既有登录接口、写接口或测试断言扩大匿名范围。
- 不自行新增全局技术债编号、归档技术债或改判 TD-025 状态。
- 不以仓库测试通过替代线上运行证据。

**测试与验收**：

| 场景 | 输入/前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 无 token 逐页浏览 index/feed/settings/chat | 四页符合各自访客态，只有允许的公共请求 | AC-01、AC-02、AC-03、AC-04 |
| 正常 | 无 token/过期 token 直访三受保护页 | 跳首页并只弹一次登录弹窗 | AC-05 |
| 正常 | 弹窗登录与注册成功 | 原页登录态数据刷新，独立登录页行为保持 | AC-06 |
| 异常 | 坏 token 请求匿名白名单或页面背景请求 | API 返回 401；开放页按规则访客化，主动操作按规则弹窗 | AC-01～AC-07 |
| 边界 | 匿名 Feed 包含历史点赞/评论数据 | 响应和页面均不夹带用户字段，写接口仍 401 | AC-02、AC-07 |
| 回归 | 全量 tests/ | 退出码 0；无无关失败或新增跳过 | AC-01～AC-07 |

**完成标志**：

- [ ] 两份当前正式契约与最终代码一致
- [ ] 针对性测试与全量 pytest 退出码均为 0
- [ ] 七项 AC 的浏览器状态矩阵全部有证据
- [ ] 排除项、技术债停止门和无迁移检查通过
- [ ] 进度与最终证据已回传

**完成回传**：返回 STEP-008 状态、针对性/全量测试输出、浏览器证据索引、契约差异、排除项检查、技术债停止门状态及全部变更文件；不得声称线上行为已验证。

## 7. 内嵌进度

| 完成数 | 总数 | 当前状态 |
|---|---|---|
| 0 | 8 | `NOT_STARTED` |

| STEP | 功能名称 | 需求 ID | 验收 ID | 前置 STEP | 状态 | 证据 |
|---|---|---|---|---|---|---|
| STEP-001 | 后端可选鉴权与匿名响应隔离 | C7、C17、CSTR-03～05 | AC-07 | 无 | `NOT_STARTED` | — |
| STEP-002 | 共享登录弹窗与认证状态策略 | C11～C16、CSTR-02/03/06、UD-01 | AC-06 | 无 | `NOT_STARTED` | — |
| STEP-003 | 首页访客降级态 | C1～C6、C16、CSTR-01/03 | AC-01 | 001、002 | `NOT_STARTED` | — |
| STEP-004 | Feed 访客只读态 | C1、C7、C8、C16、CSTR-03/04、UD-02 | AC-02、AC-07 | 001、002 | `NOT_STARTED` | — |
| STEP-005 | Settings 访客展示分层 | C1、C10、C16、CSTR-03 | AC-03 | 001、002 | `NOT_STARTED` | — |
| STEP-006 | Chat 访客壳与交互门禁 | C1、C9、C18、UD-03 | AC-04 | 002 | `NOT_STARTED` | — |
| STEP-007 | 受保护页面统一回退 | C1、C14、C15 | AC-05 | 002 | `NOT_STARTED` | — |
| STEP-008 | 契约、测试与交付门禁 | C13、C18、CSTR-05 | AC-01～AC-07 | 001～007 | `NOT_STARTED` | — |

## 8. 阻断、风险与自检

### 阻断项

本阶段未发现业务阻断项。技术债全局编号只影响文档治理，已设置实施前停止门，不影响功能 STEP 的可行性或七项验收表达。

### 非阻断风险

- R-01：找回密码无身份校验且入口扩散，本轮按 C13 保持现状。
- R-02：匿名 Feed list 可能触发既有 `actual_publish_time` 懒惰写回和额外公共读取负载。
- R-03：当前正式契约仍写全部 JWT/Bearer，须在 STEP-008 与最终代码同步。
- R-04：现有测试含匿名 401 旧断言和强鉴权假设，必须先改需求测试再实现。
- R-05：尚无浏览器或运行时证据，当前仅为仓库规划。
- R-06：PRD 的 TD-AUTH-01/02 与全局 TD-xxx 编号体系不兼容，不得自行分配新编号。

### Phase 1 自检

- [x] 27 项需求全部映射到至少一个 STEP
- [x] 7 项验收全部映射到至少一个 STEP
- [x] 每个 STEP 有非空需求、验收和显式依赖
- [x] 未新增业务字段、错误码、权限值、优先级或游客状态
- [x] existing 引用均绑定 `source_id` 与实际 locator
- [x] 未保留关键 `unverified` 引用
- [x] 草稿明确标为 `draft`、`NOT_STARTED`
- [ ] 等待 Phase 2 全量审查、必要修正与完整复审

## 9. 阶段结果

- 结果：`PASS_WITH_RISKS`。
- 状态：`STEPS_DRAFTED`。
- 产物：`steps-draft.md`。
- 下一门禁：`step-doc-review` 完整复审；本草稿不能直接进入执行计划。
