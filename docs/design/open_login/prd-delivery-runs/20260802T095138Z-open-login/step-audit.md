<!-- prd-delivery-harness-meta {"schema_version":2,"run_id":"20260802T095138Z-open-login","artifact":"step_audit","owner_phase":"step-doc-review","state":"STEPS_VERIFIED","outcome":"PASS_WITH_RISKS","code_status":"NOT_STARTED","source_digest":"819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f"} -->
# 未登录可用功能开放与登录弹窗改造：STEP 审查报告

> Harness: phase=step-doc-review; state=STEPS_VERIFIED; outcome=PASS_WITH_RISKS; code_status=NOT_STARTED

## 1. 阶段结论

- 结果：`PASS_WITH_RISKS`；无业务阻断项，可生成 `steps-verified.md`。
- 审查对象：保留的 `steps-draft.md`、PRD、UD-01～UD-03、当前权威契约、仓库基线与 FastAPI 运行时源码。
- 当前来源摘要：`819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f`，共 37 项来源。
- 修正轮次：1 轮正式修正；修正后从全部来源重新执行九维复审。
- 代码状态：`NOT_STARTED`；本阶段没有修改业务代码、正式 Contract、部署配置或项目数据。

## 2. 九维总览

| 维度 | 首次审查 | 修正 | 完整复审 |
|---|---|---|---|
| 1. 幻觉检查 | 发现未由来源规定的弹窗焦点/遮罩测试要求，以及索引中虚构的精确符号 `login_modal_api` | 删除这些要求与精确符号；保留实现时可命名的 `PLANNED` 调用面 | `PASS` |
| 2. 遗漏检查 | Memory 实际入口脚本未引用；`TD-HOME-08 / N1-B` 本地了结动作缺失 | 补 `memory-nebula.js`、静态测试入口和 TD-HOME 交付证据 | `PASS` |
| 3. 冲突检查 | 可选 Bearer 若只判断 credentials，会把错误 scheme/空凭据误当匿名 | 明确只有完全无 Authorization 头可匿名；坏头、坏 token、过期/封禁 token 均 401 | `PASS` |
| 4. 不清晰检查 | Memory 的 `checkLogin()` 定位成泛化的“三页入口”；弹窗内部名被提前固化 | 精确定位到两个内联页面和 `memory-nebula.js`；内部名保持未指定 | `PASS` |
| 5. 依赖顺序 | STEP-007 只依赖 STEP-002，但目标首页仍会被 STEP-003 之前的 `checkLogin()` 跳走 | STEP-007 增加 STEP-003 依赖，重建依赖图 | `PASS` |
| 6. 验收可测性 | 服务端响应验收 AC-07 被额外映射到前端 Feed STEP | AC-07/CSTR-04 的责任收口到直接验证 API 的 STEP-001 与总门禁 STEP-008 | `PASS` |
| 7. 决策覆盖率 | 27/27 项需求/决定均已映射 | 映射重建后仍为 27/27 | `PASS` |
| 8. 技术债完整性 | TD-AUTH-01/02 已处置，但漏掉 PRD 明示的 TD-HOME-08 / N1-B | 增加仅在七项验收通过后的 PRD 本地了结证据；不擅改全局索引 | `PASS` |
| 9. 代码事实 | FastAPI optional Bearer 语义和 Memory 外部脚本是两个关键定位缺口 | 纳入 `RUNTIME` 与 `REPO_BASELINE` 实际文件、SHA 和 STEP 引用 | `PASS` |

## 3. 逐 STEP 审查

| STEP | 首审严重度 | 首审发现与证据 | 处置 | 复审 |
|---|---|---|---|---|
| STEP-001 | P1 | FastAPI 0.139.0 的 `HTTPBearer(auto_error=False)` 对缺头、空凭据和错误 scheme 都返回 `None`；直接把 `None` 当匿名会扩大认证边界 | 已在上游重建时补完全无头/坏头/有效/伪造/过期/封禁 token 矩阵 | 通过 |
| STEP-002 | P2 | PRD 未规定键盘焦点和点击遮罩的具体语义；索引还提前命名 `login_modal_api` | 删除未授权验收要求和虚构精确符号；重复提交/回调幂等仍保留 | 通过 |
| STEP-003 | — | 首页访客态、请求白名单、文案与点击分叉均直接追溯 C1～C6、C16 | 无内容修正；作为 STEP-007 的新增前置 | 通过 |
| STEP-004 | P1 | AC-07/CSTR-04 是匿名 API 响应约束，不应由前端页面呈现反向认领 | 移除该映射；STEP-004 仍按 STEP-001 输出安全处理缺失私有字段 | 通过 |
| STEP-005 | — | Settings 双态、公共 persona 和 401 分叉与 C10/C16 一致 | 无修正 | 通过 |
| STEP-006 | — | 访客壳、零私有请求/模型调用和主动交互门禁符合 C9/C18/UD-03 | 无修正 | 通过 |
| STEP-007 | P1 | 无 STEP-003 时目标首页仍强制跳登录；Memory 的门禁实际位于外部脚本 | 增加 STEP-003 依赖、`memory-nebula.js` 与静态测试引用，并要求门禁后中止初始化 | 通过 |
| STEP-008 | P1 | 漏处理 PRD 明示的 TD-HOME-08 / N1-B 了结口径 | 七项 AC 全通过后只形成 PRD 本地了结证据；任何全局索引写入均保持停止门 | 通过 |

P1 表示进入验证版前必须修正的确定性问题；P2 表示不影响业务语义但会扩大或固化无来源实现要求的问题。

## 4. 需求与验收覆盖

| 集合 | 覆盖 | 结果 |
|---|---|---|
| C1～C18 | 18/18 | 全部至少映射一个 STEP |
| CSTR-01～CSTR-06 | 6/6 | 全部至少映射一个 STEP |
| UD-01～UD-03 | 3/3 | 全部至少映射一个 STEP |
| 合计 | 27/27 | 无遗漏、无未知 ID |

| 验收 | 直接责任 STEP | 总门禁 | 可观察证据 |
|---|---|---|---|
| AC-01 | STEP-003 | STEP-008 | 首页 DOM、精确文案、点击分叉、Network 私有请求为零 |
| AC-02 | STEP-004 | STEP-008 | Feed 公共读取、写请求为零、弹窗、SSE/已读资源未建立 |
| AC-03 | STEP-005 | STEP-008 | Settings DOM 分层、公共 persona 请求与 401 降级 |
| AC-04 | STEP-006 | STEP-008 | Chat 页面壳、私有/LLM 请求为零、发送门禁 |
| AC-05 | STEP-007 | STEP-008 | 三页直访/并发 401 导航矩阵与单次弹窗 |
| AC-06 | STEP-002 | STEP-008 | 三面板正常/失败、弹窗注册分叉、成功回调一次 |
| AC-07 | STEP-001 | STEP-008 | 路由/服务响应字段、匿名查询隔离、坏 token 401 |

七项验收均由直接观察目标对象的 STEP 覆盖；UI 呈现不再反向认领 AC-07 的服务端响应责任。

## 5. 技术债与排除项

| 项目 | 来源 | 验证版处置 |
|---|---|---|
| TD-HOME-08 / N1-B | PRD 第 8 章 | 仅在七项 AC 全通过后记录本 PRD 本地了结证据；不自动修改全局索引 |
| TD-AUTH-01 | PRD 第 8 章 | 保留 PRD 本地编号和 R-01；本轮不加固找回密码 |
| TD-AUTH-02 | PRD 第 8 章 | 保留 PRD 本地编号；游客试聊/预注册另立项 |
| TD-025 | 当前权威技术债文档 | 只识别潜在重叠，不归档、不改判、不映射为 PRD 新债务 |
| OUT-01 | C18 | 不实现游客身份、试聊、预注册或数据继承 |
| OUT-02 | C13 | 不加固找回密码，不接第三方登录 |
| OUT-03 | PRD 第 6 章 | 不新增数据库表或字段 |
| OUT-04 | C12 | 保留独立 `login.html` 入口和既有整页注册行为 |

## 6. 依赖与代码事实核查

验证版依赖为：

```text
STEP-001 → STEP-003、STEP-004、STEP-005
STEP-002 → STEP-003、STEP-004、STEP-005、STEP-006、STEP-007
STEP-003 → STEP-007
STEP-001～STEP-007 → STEP-008
```

- 无循环、无缺失 STEP；STEP-001/002 可并行，STEP-007 必须等待可停留的首页访客态。
- `frontend/static/js/memory-nebula.js` 实际包含 Memory 的 `checkLogin()` 和 `/api/memory/list` 请求，已绑定 `repo-memory-nebula-js`。
- FastAPI 运行时文件已绑定 `runtime-fastapi-http-security`；错误 scheme 与缺头不可用同一 `None` 分支解释。
- 其余 `existing` 路径均存在并由 `source_id`/`locator` 严格绑定；正式验证版无关键 `UNVERIFIED`。
- 新函数名仅保留 PRD 明示的 `get_current_user_optional`；共享弹窗内部命名继续标为实现期普通 `PLANNED` 细节。

## 7. 首次审查结论

首次输入不能直接进入执行计划：存在确定性认证边界、依赖、代码定位、验收归属和技术债遗漏。由于答案均可由 PRD、用户决定或仓库/运行时唯一确定，`orchestrated` 模式进入修正而不向用户新增业务确认。

Phase 2 早期发现 STEP-001 的认证边界会影响上游台账，已按 Harness 允许的唯一一次上游重建重新执行 Phase 0 和 Phase 1。其后新增的 Memory 脚本只补充 Phase 2 代码事实证据，没有改变 Phase 0 需求语义；旧阶段已对新来源摘要重新校验。

## 8. 修正 Diff

| 编号 | 原内容 | 修正内容 | 唯一来源 | 影响 |
|---|---|---|---|---|
| D-01 | optional Bearer 的 `None` 可直接代表匿名 | 只有完全无 Authorization 头匿名；空 Bearer、错误 scheme、伪造/过期/封禁 token 均 401 | FastAPI 运行时、C16、CSTR-03、现有强鉴权 | STEP-001 测试/定义 |
| D-02 | STEP-007 只引用 `memory.html`，泛称三页入口 | 增加 `memory-nebula.js` 和静态测试入口，精确定位三处门禁 | `memory.html` 脚本装载、`memory-nebula.js::checkLogin` | STEP-007 引用/任务 |
| D-03 | STEP-007 仅依赖 STEP-002 | 增加 STEP-003；否则目标首页仍会执行旧 `checkLogin()` | `index.html::checkLogin/initHomePage`、C14 | 依赖图/排程 |
| D-04 | STEP-004 映射 AC-07/CSTR-04 | 服务端响应责任收口 STEP-001/008；STEP-004 只负责 AC-02 | AC-07 的 API 响应对象、审查维度 6 | 需求/验收映射 |
| D-05 | 仅处置 TD-AUTH-01/02 | 增加 TD-HOME-08 / N1-B 的条件式 PRD 本地了结证据 | PRD 第 8 章 | STEP-008 |
| D-06 | 要求焦点/遮罩行为并命名 `login_modal_api` | 删除无来源要求和虚构精确名；不改变三面板业务语义 | PRD C11/CSTR-02 未规定这些细节 | STEP-002/索引 |

审查轨迹：最早 Phase 1 草稿 SHA-256 为 `ea0e2e7f0dee33d22dc7f2c2c6a9701947e3db1f1b76ad2264e1c054e237dfaa`；认证边界上游重建后为 `53df8079af651705143bce8175eb41e42ee398b82c4edce664159bbaf654edcb`。纳入 Memory Phase 2 证据后，保留草稿只更新来源元数据，当前 SHA-256 为 `ba26e17b4568dd2d9168a4988b34563752ca6f3fa2d7b8f0dd81e53c089576e8`；修正版另存为 `steps-verified.md`，没有覆盖保留草稿。

## 9. 完整复审结论

- 九维完整复审：9/9 通过。
- 需求/决定覆盖：27/27；验收覆盖：7/7；STEP：8/8 均有非空需求、验收和显式依赖。
- 阻断项：无。
- 非阻断风险：R-01 找回密码入口扩散、R-02 匿名 Feed GET 懒惰写回/负载、R-03 正式契约待实施同步、R-04 旧测试断言待迁移、R-05 尚无浏览器/线上证据、R-06 PRD 技术债本地编号与全局编号体系不兼容。
- 阶段结果：`PASS_WITH_RISKS`；状态：`STEPS_VERIFIED`。
- 正式 STEP：`steps-verified.md`；后续只能由里程碑阶段重排与分批，不得修改 STEP 内容。

