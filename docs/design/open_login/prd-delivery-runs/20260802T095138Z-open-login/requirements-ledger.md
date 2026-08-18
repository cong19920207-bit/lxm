<!-- prd-delivery-harness-meta {"schema_version":2,"run_id":"20260802T095138Z-open-login","artifact":"requirements_ledger","owner_phase":"prd-review","state":"PRD_READY","outcome":"PASS_WITH_RISKS","code_status":"NOT_STARTED","source_digest":"819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f"} -->
# 未登录可用功能开放与登录弹窗改造：需求审查台账

> Harness: phase=prd-review; state=PRD_READY; outcome=PASS_WITH_RISKS; code_status=NOT_STARTED

## 1. 阶段结论

- 阶段结果：`PASS_WITH_RISKS`。
- 状态：`PRD_READY`。
- 原先 3 组多解语义已由 `USER_DECISION` 明确收敛为方案 A；当前无阻断项，可进入 STEP 拆解。
- 代码状态：`NOT_STARTED`；本次只新增运行台账与索引，没有修改业务代码或正式 Contract。
- 证据范围：结论来自当前仓库文件（`REPO_BASELINE`）与当前权威契约（`CONTRACT`），不代表线上运行事实。

## 2. 输入与来源覆盖

| 来源类别 | 已核验内容 | 结论 |
|---|---|---|
| `USER_DECISION` | `user-decision-all-a` | 用户明确确认 B-01、B-02、B-03 全部采用方案 A |
| `PRD` | `prd-open-login`，v1.0，状态“待评审” | 182 行均完成首轮读取与第二次来源覆盖检查 |
| `CONTRACT` | 共享响应、用户认证、H5 App、Life Feed、Chat、Diary、Memory、Relationship 当前契约 | 当前契约仍把相关用户接口记为 Bearer/JWT；若实施 PRD，需同步契约 |
| `CONTRACT` | 当前技术债索引及 core-user-auth/cross-cutting 详情 | 全局索引当前仅登记 `TD-001`～`TD-037`；PRD 的 `TD-AUTH-01/02` 尚未进入全局编号体系 |
| `REPO_BASELINE` | 8 个 H5 页面、公共 `api.js`、认证/Feed/App 路由与 Feed 服务 | 已定位强制跳转、私有请求、可选鉴权落点与现有测试入口 |
| `REPO_BASELINE` | `tests/test_app_persona_background.py`、`tests/test_step015_feed_service.py`、`tests/test_h5_static_contract.py`、`README.md` | 已确认现有测试会被匿名访问改造影响；仓库推荐门禁为 `PYTHONPATH=. pytest tests/` |
| `RUNTIME` | 工作区 venv 的 FastAPI 0.139.0 `HTTPBearer.__call__` | `auto_error=False` 时缺头、空凭据和非 Bearer scheme 都返回 `None`；可选鉴权必须额外区分“完全无头”与“头存在但格式错误” |

完整文件路径、SHA-256 与来源摘要见同目录 `run.json` 的 `source_manifest`。未读取 `.doc-migration-baseline/`、契约历史、契约草案或技术债归档。

## 3. 需求台账

| ID | PRD 原意摘要 | 来源位置 | 处置 |
|---|---|---|---|
| C1 | index/feed/settings 部分开放；chat 页面可见但操作需登录；diary/memory/relationship 仍为登录页 | PRD 2/C1，行 27 | 已登记；chat 访客数据边界按 UD-03 收敛 |
| C2 | 访客首页关系胶囊复用 level=0 默认态，点击登录弹窗 | PRD 2/C2，行 28 | 已登记 |
| C3 | 访客日记卡复用陌生人锁定视觉与占位文案，点击弹窗 | PRD 2/C3，行 29 | 已登记 |
| C4 | 访客首页不显示未读消息角标 | PRD 2/C4，行 30 | 已登记 |
| C5 | 访客首页陪伴天数改为“故事从今天开始” | PRD 2/C5，行 31 | 已登记 |
| C6 | 访客点击首页五个快捷互动项均弹窗；登录态维持既有分叉 | PRD 2/C6，行 32 | 已登记 |
| C7 | 访客可读 Feed 公共内容，不显示私有评论和 `user_liked`；点赞/评论/enter 触发登录 | PRD 2/C7，行 33 | 已登记；访客初始化按 UD-02 跳过自动 `/enter`，显式写交互才触发登录 |
| C8 | 访客不挂载 Feed 未读/SSE，登录后才挂载 | PRD 2/C8，行 34 | 已登记 |
| C9 | chat 不做锁定引导；发送等交互在未登录或 token 过期时弹窗 | PRD 2/C9，行 35 | 已登记；无效会话按 UD-03 静默进入无私有数据的访客壳 |
| C10 | settings 访客只保留人设资料卡和“关于”；隐藏账号安全、陪伴偏好；退出位改登录入口 | PRD 2/C10，行 36 | 已登记 |
| C11 | 新增全局三面板登录弹窗，复用整页登录 markup/逻辑；登录成功关闭并原地刷新数据 | PRD 2/C11，行 37 | 已登记；弹窗注册成功按 UD-01 直接建立登录态 |
| C12 | 保留独立 `login.html` 兜底入口 | PRD 2/C12，行 38 | 已登记 |
| C13 | 找回密码身份校验本轮不加固，不接第三方登录 | PRD 2/C13，行 39 | 已登记为明确排除项和已知安全风险 |
| C14 | 未登录直访 diary/memory/relationship 时跳首页并自动弹窗 | PRD 2/C14，行 40 | 已登记 |
| C15 | 三个受保护页面 token 中途失效也统一跳首页并弹窗 | PRD 2/C15，行 41 | 已登记 |
| C16 | index/feed/settings 的个性化请求 401 时清 token、静默降级，不弹窗或跳转 | PRD 2/C16，行 42 | 已登记；只适用于这三个页面 |
| C17 | `feed.list`、`feed.config/header`、`app/persona-background` 使用可选鉴权，其余写接口保持强鉴权 | PRD 2/C17，行 43 | 已登记；缺 token 与坏 token 的语义需按 C16 分开处理 |
| C18 | 不实现游客身份、试聊、预注册和数据继承 | PRD 2/C18，行 44 | 已登记为排除项 |

### 派生约束

| ID | 约束 | 来源位置 | 处置 |
|---|---|---|---|
| CSTR-01 | 访客首页不得发起 relationship/diary/agent-unread 等纯个性化请求 | PRD 流程一，行 73–80 | 必须验证网络请求不存在，而非仅隐藏 UI |
| CSTR-02 | 访客点击需登录功能时，弹窗默认打开登录面板 | PRD 流程二，行 82–88 | 必须覆盖键盘/点击入口 |
| CSTR-03 | 开放页 401 必须先清理失效 token，再渲染访客态 | PRD 流程四，行 98–104 | 可选鉴权必须让无 token 与无效/过期 token 行为可区分 |
| CSTR-04 | 匿名 Feed 响应不得携带 `user_liked`、当前用户评论或其他用户绑定字段 | PRD 边界，行 114–115；检查项，行 174 | 需后端响应级断言，不只做前端不展示 |
| CSTR-05 | 本轮不新增数据库表或字段 | PRD 数据结构，行 128–132 | 已登记 |
| CSTR-06 | 登录弹窗采用成功回调刷新当前页数据，不新增持久化状态 | PRD 数据结构，行 130–132 | 回调契约可作为普通实现细节规划，前提是 B-01 收敛 |

## 4. 验收台账

| ID | 通过条件 | 来源位置 | 当前可测性 |
|---|---|---|---|
| AC-01 | index 未登录可浏览，个性化模块按 C2–C5 降级且不发起私有请求 | PRD 检查项，行 168；流程一 | 可做静态契约 + 浏览器网络断言 |
| AC-02 | feed 未登录可只读浏览，写操作受登录门禁保护 | PRD 检查项，行 169 | 可测；需断言访客不调用 `/enter`、badge、SSE 或已读上报 |
| AC-03 | settings 未登录可访问，两个私有板块隐藏，“关于林小梦”可加载 | PRD 检查项，行 170 | 可做静态契约 + 匿名 API 测试 |
| AC-04 | chat 未登录发送会打开登录弹窗 | PRD 检查项，行 171 | 可测；同时断言访客壳不加载私有 timeline/Agent/badge |
| AC-05 | diary/memory/relationship 未登录直访与 token 失效均跳首页并自动弹窗 | PRD 检查项，行 172 | 需浏览器导航与 401 场景测试 |
| AC-06 | 登录弹窗三面板功能与独立登录页一致，成功后不跳离当前开放页 | PRD 检查项，行 173 | 可测；弹窗注册成功直接保存 token，独立登录页行为不变 |
| AC-07 | Feed/App 匿名接口响应不包含用户绑定字段 | PRD 检查项，行 174 | 可做路由/服务层响应断言 |

## 5. 排除项与技术债

### 排除项

| ID | 内容 | 来源 |
|---|---|---|
| OUT-01 | 不实现游客身份、游客试聊、预注册或匿名数据继承 | C18 |
| OUT-02 | 不加固找回密码身份校验，不接第三方登录 | C13 |
| OUT-03 | 不新增数据库表或字段 | PRD 第 6 章 |
| OUT-04 | 不把 `login.html` 删除或取消独立入口 | C12 |

### PRD 明示技术债

| ID | 内容 | 本轮处置 |
|---|---|---|
| TD-HOME-08 / N1-B | 首页游客浏览历史债务 | PRD 计划在本轮了结；历史文档未作为当前权威来源重读 |
| TD-AUTH-01 | 找回密码缺少身份校验 | 本轮明确不处理；保留风险 R-01；当前仅视为 PRD 本地编号 |
| TD-AUTH-02 | 游客试聊/预注册体系 | 本轮明确排除，建议另立 PRD；当前仅视为 PRD 本地编号 |

当前权威技术债索引只记录 `TD-001`～`TD-037`，且 core-user-auth 已存在相关的 `TD-025`。本 Harness 不自行分配新全局编号，也不把 PRD 本地别名直接写入全局索引；若实施时要登记全局技术债，必须先按项目治理规则取得编号/别名处理确认。

## 6. 当前仓库基线与 PRD 差异

| 范围 | `REPO_BASELINE` / `CONTRACT` 事实 | PRD 要求 | 评估 |
|---|---|---|---|
| 公共请求层 | `frontend/static/js/api.js::request` 对任意 HTTP 401 清 token 后跳 `/pages/login.html` | 开放页静默降级、受保护页跳首页弹窗、主动交互弹窗 | 必须把 401 策略改为可按页面/请求上下文选择，不能只删除 `checkLogin()` |
| 可选鉴权解析 | 当前 `_bearer_scheme` 使用 `HTTPBearer(auto_error=False)`；运行时对缺头和错误 scheme 都给依赖函数 `None` | 只有真正无 token 才能匿名，坏 token/坏认证头仍需 401 | 新依赖不能只用 `credentials is None` 判断访客；需测试缺头、空 Bearer、错误 scheme、伪造/过期 token |
| 页面入口 | index/feed/settings/chat/diary/memory/relationship 均调用 `checkLogin()` | 只有后三个维持强页面门禁 | 改造入口已定位 |
| Feed 初始化 | `initFeed()` 先自动 POST `/api/feed/enter`，同时加载未读、挂 SSE 和已读上报观察器 | 访客只读且不挂未读/SSE | 访客必须跳过私有写入/上报；`enter` 的弹窗语义需确认 |
| Feed 响应 | `list_feed` 总会按 `user_id` 查询私有评论和点赞，返回 `comments`/`user_liked` | 匿名响应不得夹带用户字段 | 可行；需 `user_id=None` 专门分支和回归测试 |
| Feed GET 副作用 | `list_feed` 会懒惰写 `actual_publish_time` | 对匿名开放列表 | 技术可行，但扩大公开流量触发 DB 写的范围，见 R-02 |
| Chat 初始化 | `initChat()` 会加载 Feed badge、私有 timeline、Agent messages；全局 401 当前整页跳登录 | 页面可见，操作才触发弹窗 | 不能让访客请求或看到私有历史；初始态/过期态口径需确认 |
| 注册 | `/api/auth/register` 当前返回 token；独立页 `handleRegister()` 却忽略 token并提示“注册成功，请登录” | 流程二写“登录/注册成功”均关闭弹窗并刷新 | UD-01 已确认：仅弹窗直接保存 token，独立页行为不变 |
| App Persona | 路由逻辑不使用 `user_id`，但依赖 `get_current_user`；现有测试断言匿名 401 | 改为匿名可读 | 改造直接；需同步测试与 H5 App 契约 |
| 当前契约 | Life Feed 写“全部 JWT”，H5 App persona 写 Bearer | 三个只读接口改可选鉴权 | PRD 优先；实施时必须同步当前正式契约，但本 Harness 不写正式 Contract |
| 验证入口 | README 给出 `PYTHONPATH=. pytest tests/`；现有 Feed/App/H5 静态测试覆盖相关路径 | 增加匿名/过期 token/UI 交互验证 | 可行；浏览器级导航与网络断言仍需新增 |

## 7. 用户补充决定与阻断清零

| ID | 已确认决定 | 来源 | 影响 |
|---|---|---|---|
| UD-01 | 弹窗注册成功直接保存注册接口返回的 token，关闭弹窗并刷新当前页；独立 `login.html` 保持现有注册后再登录行为 | `USER_DECISION` `user-decision-all-a` | 收敛 C11/流程二的注册分支 |
| UD-02 | 访客 Feed 初始化跳过 `/enter`、badge、SSE、评论回复已读和帖子停留已读，只匿名请求列表与 Header；显式写交互才弹窗 | `USER_DECISION` `user-decision-all-a` | 收敛 C7 与开放浏览目标 |
| UD-03 | Chat 无 token 或 token 过期时静默显示现有页面壳，不请求/展示私有 timeline、Agent 消息或 Feed badge；主动交互才弹窗 | `USER_DECISION` `user-decision-all-a` | 收敛 C9 与 C16 未覆盖的 Chat 初始化行为 |

本次 Phase 0 复审未发现剩余业务阻断项。

## 8. 非阻断风险

| ID | 风险 | 证据与影响 | 计划性处置 |
|---|---|---|---|
| R-01 | 找回密码无身份校验的入口扩散 | PRD C13/TD-AUTH-01 明确维持现状；全局弹窗会增加入口曝光 | 不阻断本轮，但验收需确认未意外扩大接口能力，并保留技术债 |
| R-02 | 匿名 Feed 列表可触发懒惰 DB 写和更多公开读取负载 | `FeedService.list_feed` 会写 `actual_publish_time`，此前接口全部 JWT | 实施前增加匿名并发/幂等回归与必要的访问频率观察；不在本 PRD自行新增限流业务规则 |
| R-03 | 当前正式契约与 PRD 冲突 | Life Feed/H5 App 当前契约仍要求 JWT/Bearer | 实施 STEP 必须包含契约同步门禁；本次规划不改正式契约 |
| R-04 | 现有测试断言会被需求有意改变 | persona 匿名 401 测试、Feed 服务签名、H5 静态字符串均受影响 | 实施时先更新/新增需求测试，再改代码 |
| R-05 | 尚无运行时或浏览器证据 | 本阶段只读取仓库与文档 | 不把仓库事实表述为线上事实；实施验收需补浏览器网络与导航证据 |
| R-06 | PRD 技术债编号与全局索引不兼容 | PRD 使用 `TD-AUTH-01/02`，当前权威索引仅有 `TD-001`～`TD-037`，且相关安全缺口已见 `TD-025` | 保留 PRD 本地编号；修改全局索引前设置停止门并请求编号/别名决策 |

## 9. 第二次来源覆盖检查

- PRD 决策 C1–C18：18/18 已进入台账。
- PRD 完整流程：4/4 已进入需求或冲突处置。
- PRD 边界：5/5 已进入约束、风险或阻断项。
- PRD 文件索引：11/11 个改造行已与当前路径核验；`login.html` 的“抽取复用但文件无改动”作为普通实现结构问题，不单独制造业务确认。
- PRD 技术债：3/3 已登记；已核验全局编号冲突并记录 R-06，未自行创造替代编号。
- PRD 检查项：7/7 已分配 AC-01～AC-07。
- 需求/验收到 STEP 映射：尚未生成；Phase 0 已通过，交由 Phase 1 建立完整映射。

## 10. 阶段报告

- 结果：`PASS_WITH_RISKS`。
- 阻断项：无；B-01、B-02、B-03 已分别由 UD-01、UD-02、UD-03 收敛。
- 非阻断风险：R-01～R-06。
- 后续：进入 Phase 1 生成需求/验收到 STEP 的完整映射和 `steps-draft.md`。
