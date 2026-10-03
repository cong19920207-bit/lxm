---
title: "steps-verified"
mode: "standalone"
phase_status: "verified"
phase_result: "PASS_WITH_RISKS"
handoff_state: "STEPS_VERIFIED"
review_status: "VERIFIED"
authority_skill: "step-doc-review"
candidate_step: "steps-candidate-r1.md"
candidate_sha256: "c73cc056bbf824536979a386b7439fd88384838042baba938cf9c02dcc6e9378"
repair_writer: "execute-approved-work"
input_step: "steps-draft.md"
input_step_sha256: "e3dccbf514175800344fbfb3504cf0b7ebfdebcd20a84b8c710230d737928cab"
input_audit_snapshot_sha256: "a69155a8bd3569b0b3a69cac71adfa31f2e98dd30098cfb5d215d22ca30f8b8a"
input_source_digest: "25200936558d518ec81078c4466749c8f3712ad470b10d60a52f1a31efa13af5"
source_digest: "32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c"
implementation_status: "NOT_STARTED"
updated: "2026-10-02"
prd: "PRD-林小梦主页改版-v2.md"
---

# steps-verified

本文件为林小梦主页改版 v2 的 STEP 验证版。用户授权补齐两项文档发现后，`execute-approved-work` 统一生成 [第 1 轮候选](steps-candidate-r1.md)，`step-doc-review` 已从当前 PRD、契约、代码与完整候选完成九维复审，结果 **PASS_WITH_RISKS**，权威状态 **STEPS_VERIFIED**；完整依据见 [当前审计](step-audit.md)。

验证输入为 [当前 v2 PRD](PRD-林小梦主页改版-v2.md)、只读 [原 STEP](steps-draft.md) 与修复候选。生成前于 `2026-10-02T08:21:08.475611+00:00` 重算 29 个定向来源，全部 SHA-256 与复审输入一致；候选完整摘要及当前来源摘要见元数据，首次审计快照摘要用于保留交接历史，不代表当前审计内容的摘要。

共 18 个 STEP，功能实施仍为 **NOT_STARTED（0/18）**。条目中的 `draft`／`provisional` 保留原拆解阶段标签，不表示本验证版尚未审查；STEP-014/015/016 的 `provisional` 继续表示部署或真机事实门尚待关闭。Q201—Q203、测试运行入口和改造前基线须按 §5／§7 落实。文档通过不表示新主页、素材优化、真机性能或部署验收已完成，也不新增发布授权。当前功能进度只在本文件 §9 维护。

## 1. 来源摘要与事实边界

来源标签只使用 `USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`、`PLANNED`、`UNVERIFIED`。PRD 中已记录的用户选择仍标 `PRD`；原拆解的用户指令是“使用 prd-to-steps 拆解此 v2 PRD”，当前文档修复新增的 `USER_DECISION` 是“两项都补齐（推荐）”，仅授权两个审计项的文档修改，未新增业务决定。当前没有 `RUNTIME` 浏览器、真机或部署证据。

| source_id | 路径（状态） | 来源 | 实际 locator | SHA256 前 12 位 | 用途 |
|---|---|---|---|---|---|
| SRC-01 | `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` · `existing` | PRD | §3—§9；F201—F212、AC201—AC217 | 165e84076e14 | 已确认需求、验收、排除项及待核验项 |
| SRC-02 | `docs/contract/current/h5-app/api.md` · `existing` | CONTRACT | §H5 认证与页面访问策略（26—81 行） | bf727722686b | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| SRC-03 | `docs/contract/current/_shared/conventions.md` · `existing` | CONTRACT | §统一说明／字段命名规范（10—26 行） | 9ae6b47a846b | H5 响应 code=0；日记 items 等既有例外 |
| SRC-04 | `frontend/pages/index.html` · `existing` | REPO_BASELINE | DOM 1250—1477；加载 1481—1787；渲染 1791—2004；取数 2098—2273 | 7009f8fa634b | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| SRC-05 | `frontend/static/js/api.js` · `existing` | REPO_BASELINE | request@83；handleUnauthorized@111；openLoginModal@353；updateAvatarEmotion@615 | 6bf271e53a7b | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| SRC-06 | `frontend/static/js/voice-entry.js` · `existing` | REPO_BASELINE | elements@60；show@119；begin@401；close@473；pageshow@467 | ac355a96679f | 面板实际可见状态；微信语音保持不支持的当前策略 |
| SRC-07 | `frontend/static/css/voice-entry.css` · `existing` | REPO_BASELINE | 旧背景 URL 第 2、21 行 | a4d106cfd863 | 语音使用 Index/Index.png；保留旧图 |
| SRC-08 | `nginx/nginx.conf` · `existing` | REPO_BASELINE | server／location（27—81 行） | 1f53e0b85c09 | 仓库配置监听 80，根路径跳 /pages/index.html；不是外层 HTTPS 证据 |
| SRC-09 | `tests/test_h5_static_contract.py` · `existing` | REPO_BASELINE | 文件说明@1；test_index_html_home_surface_contract@407；test_index_guest_mode_contract@483 | 21dec126aab8 | 已有 pytest 静态入口；子串断言不等于浏览器集成验收 |
| SRC-10 | `requirements.txt` · `existing` | REPO_BASELINE | Pillow@48；pytest@52；pytest-asyncio@53 | 79d5196a84c6 | 已有依赖声明，不能据此推定执行环境可用 |
| SRC-11 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` · `existing` | REPO_BASELINE | renderParallax@89；enableTilt@130；scheduleBlink@182；acknowledge@227；启动循环@416—437 | a6bb07bfc2be | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| SRC-12 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js` · `existing` | REPO_BASELINE | normalizeOrientation@48；createBlinkPlan@58；createAcknowledgePlan@80 | d9eb388f8ce1 | 参考计算与动效计划；参数不是新的业务决定 |
| SRC-13 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css` · `existing` | REPO_BASELINE | scene@4；hair-front/side/back@22—24；blink@26 | 959a10405861 | 参考坐标与锚点；全场景 touch-action:none 不能照搬 |
| SRC-14 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/index.html` · `existing` | REPO_BASELINE | 分层素材 DOM | c59d82c2f5da | 七图图层和参考结构 |
| SRC-15 | `tests/test_realtime_voice_step036_states.cjs` · `existing` | REPO_BASELINE | Playwright 导入@3；setup@38；page.route@50 | bb93e2b1b10e | 已有受控浏览器测试写法，含模拟传输；不证明真实音频或设备通过 |
| SRC-16 | `docs/INDEX.md` · `existing` | REPO_BASELINE | §产品需求与设计 | 179cf230fc39 | 当前 v2 入口及读取边界 |
| SRC-17 | `docs/llm-manifest.json` · `existing` | REPO_BASELINE | documents 中 contract-h5-app-api／contract-shared-conventions | 15819acc2ae0 | 本轮读取的当前契约在白名单内 |
| ASSET-01 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/background.webp` · `existing` | REPO_BASELINE | 文件头／元数据：853×1844、RGB、165630 字节 | c094490a4d8e | 场景原素材及画布／alpha 基线 |
| ASSET-02 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/character.webp` · `existing` | REPO_BASELINE | 文件头／元数据：853×1844、RGBA、284604 字节 | 2816096f87aa | 场景原素材及画布／alpha 基线 |
| ASSET-03 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_front_physics.png` · `existing` | REPO_BASELINE | 文件头／元数据：456×417、RGBA、358769 字节 | b1e1d3d8534d | 场景原素材及画布／alpha 基线 |
| ASSET-04 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_side_physics.png` · `existing` | REPO_BASELINE | 文件头／元数据：220×512、RGBA、120267 字节 | c1aa3d65e058 | 场景原素材及画布／alpha 基线 |
| ASSET-05 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_back_physics.png` · `existing` | REPO_BASELINE | 文件头／元数据：168×445、RGBA、146555 字节 | cb856237a6f6 | 场景原素材及画布／alpha 基线 |
| ASSET-06 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/blink_crop.png` · `existing` | REPO_BASELINE | 文件头／元数据：263×134、RGBA、70797 字节 | 3365f66905d3 | 场景原素材及画布／alpha 基线 |
| ASSET-07 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/lamp_glow.webp` · `existing` | REPO_BASELINE | 文件头／元数据：853×1844、RGBA、140176 字节 | a1425ca6fb0a | 场景原素材及画布／alpha 基线 |
| ASSET-08 | `frontend/static/images/Index/Index.png` · `existing` | REPO_BASELINE | 精确目录名 Index.png；550814 字节 | 0b072904c320 | 语音和首页回退使用的原背景 |

PRD 完整 SHA256：`165e84076e14016073e92b4c2284a0ada52321fe8c6d753061ceda81e4ce9ed6`。源码证据定位对应本轮读取，实施或复审前如源码变化，复核受影响的定位与结论；不能把旧读取状态当本轮运行通过。

### 1.1 新增产物与未核实环境

| 引用 ID | 路径或对象 | 状态 | 来源／发现门 |
|---|---|---|---|
| PLAN-01 | `frontend/static/css/home-scene.css` | planned | PLANNED；PRD §9.1；限定场景作用域的样式 |
| PLAN-02 | `frontend/static/js/home-scene-core.js` | planned | PLANNED；PRD §9.1；可独立验证的坐标、时间与动效规则 |
| PLAN-03 | `frontend/static/js/home-scene.js` | planned | PLANNED；PRD §9.1；场景资源、调度、生命周期与传感器 |
| PLAN-04 | `frontend/static/images/home-scene/v4/` | planned | PLANNED；PRD §9.1；新场景版本化导出资源 |
| PLAN-05 | `首页头像和日记派生资源` | planned | PLANNED；PRD §7；具体文件名与路径按已核实的项目约定确定 |
| PLAN-06 | `主页行为测试及本地验收记录` | planned | PLANNED；具体文件名、测试入口及保存位置按已核实的项目约定确定；不沿用语音测试的默认输出目录 |
| ENV-01 | 实际设备、系统／浏览器／微信版本、网络与统计口径 | unverified | UNVERIFIED；Q201：验收前列明，不能先填具体版本、像素上限或掉帧窗口 |
| ENV-02 | 真实部署 URL、外层 HTTPS、缓存响应头及运行配置 | unverified | UNVERIFIED；Q203：先发现部署目标再读取响应；仓库 Nginx 不是外层运行事实 |

原拆解输出 `docs/design/home-redesign/steps-draft.md` 为只读 `existing` 输入；`steps-candidate-r1.md` 是已复审的输入快照，本文件 `steps-verified.md` 为当前验证版。完整来源及候选 SHA-256 见审计；产物路径与 H1 按审查技能约定确定。新增行为测试位置／运行环境等未在 PRD 指定的实现细节只标 `PLANNED`，按已核实的项目约定确定，不补造内部 API、业务字段、错误码或存储键。

### 1.2 本轮核实的代码事实

| 证据 | 本轮事实 | 拆解含义 |
|---|---|---|
| SRC-04::runHomeLoader@1687 | 静态图、API、情绪头像和最短时间共同进入当前门闩；preloadImage 仅 onload/onerror，没有挂起截止 | STEP-004 拆开有截止加载，STEP-006 管业务数据，不能只提前移除遮罩 |
| SRC-05::request@83／handleUnauthorized@111 | fetch 未透传取消信号；401 处理会先 clearToken；异步解析后无请求上下文检查 | STEP-005 先建立共享保护，STEP-006 再接入首页批次和 UI 代次 |
| SRC-04::loadPage@2098／loadFeedHomeCard@2181 | 当前私人批次收齐后才渲染，再等待 Feed；失败可能用空值／level=0 呈现；已有前台 Feed 刷新 | STEP-006 必须覆盖模块状态、未知关系、整个批次截止和刷新去重 |
| SRC-06::show@119／begin@401／close@473 | 准备面板先显示，voice:connected 发生在后；实际状态为 .voice-entry 的 hidden；微信由现代码阻止语音 | STEP-012 按实际面板可见暂停；首版微信主页验收不扩展语音兼容 |
| SRC-11::启动@416—437／SRC-13::scene@4 | demo 独立启动视差、雨、星光循环及计时器；全场景禁止默认 touch-action | STEP-007／008／013 重组调度和资源治理，STEP-003／009 保留正式页手势 |
| SRC-04 旧 URL／SRC-07 旧 URL；本轮精确目录枚举 | 磁盘实际名称仅 Index.png；主页写 index.png，语音 CSS 写 Index.png；macOS 的 exists() 对两者都成功 | STEP-014 核对所有引用与真实服务响应，不能仅“修正语音 CSS”或以本机文件存在证明 |
| SRC-09 文件说明与测试函数 | 现静态 pytest 只查子串；包含旧背景 URL／旧 DOM 断言 | 各实施 STEP 同步相关有效断言；静态通过不能推定交互、权限和性能通过 |

### 1.3 素材基线（元数据读取，非视觉验收）

| source_id | 实际素材（均 existing／REPO_BASELINE） | 像素 | 模式 | 字节 |
|---|---|---|---|---|
| ASSET-01 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/background.webp | 853×1844 | RGB | 165630 |
| ASSET-02 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/character.webp | 853×1844 | RGBA | 284604 |
| ASSET-03 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_front_physics.png | 456×417 | RGBA | 358769 |
| ASSET-04 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_side_physics.png | 220×512 | RGBA | 120267 |
| ASSET-05 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_back_physics.png | 168×445 | RGBA | 146555 |
| ASSET-06 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/blink_crop.png | 263×134 | RGBA | 70797 |
| ASSET-07 | /Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/lamp_glow.webp | 853×1844 | RGBA | 140176 |

本轮元数据读取合计 1,286,798 字节，核心两图 450,234 字节，与 PRD 基线一致。这里没有压缩输出，也没有检查新导出图的脸部、透明边缘或真机内存；这些仍由 Q202 对应验收完成。

## 2. 固化功能、决策与排除项

以下保留全部有效 F／RQ／G／V2-D 编号。旧 C／N／R／K 编号只依据当前 v2 的保留／替代记录追踪，不复用为本版新编号，不读取历史正文作为当前事实。表内顺序是索引，不定义新的业务优先级。

| 功能需求 ID | 触发／输入（PRD） | 行为摘要（PRD） |
|---|---|---|
| F201 | 打开主页 | 背景＋完整人物构成静态底图；随后增强呼吸、眨眼、发丝、待机回应、灯光、雨与星光；任一可选层失败保留基础画面 |
| F202 | 小屏、短屏、桌面、旋转或卡片高度变化 | 所有贴片共用坐标变换；根据实际 UI 位置调整人物，脸部与入口可见；桌面采用居中竖向场景和暗色延展 |
| F203 | 首访、刷新、会话内返回 | 按 §5.1 显示或跳过加载页，核心图片、API 和可选特效按不同职责加载；异常有截止 |
| F204 | 初始取数、登录变化、局部重试 | 主页结构和入口独立显示，数据按模块更新；8 秒请求批次截止，支持取消、去重、代次与登录快照保护 |
| F205 | 动态允许时点击或键盘激活人物有效区域 | 轻微本地回应，重复触发合并；不触发页面跳转、聊天、关系写入；UI 按钮和覆盖层优先 |
| F206 | 已登录打开更多互动或再次进入主页 | 提供主页动态、倾斜视差的开关及实际状态；无已保存选择时动态默认开启，之后长期沿用当前浏览器选择；系统减少动态效果优先 |
| F207 | 主动开启或关闭倾斜 | 倾斜初始关闭；用户操作中申请权限；检查支持、安全环境、授权结果与实际数据；关闭移除监听，旋转后重新校准 |
| F208 | 加载、后台、弹窗、通话、关闭动态、减少动态效果、页面离开恢复 | 统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积 |
| F209 | 场景持续运行或掉帧 | 单一主调度，按时间差运动；环境特效优先 30fps；DPR 默认至多 1.5，另设像素上限；按 §6 降级，同一页面实例不自动升档 |
| F210 | 素材导出与替换 | 按 §7 预算优化，保持透明通道、画布比例与锚点；小图使用首页派生资源，原资源保留 |
| F211 | 资源发布、请求缓存、场景故障 | 使用版本化资源；检查真实缓存头与 HTTPS；旧图保留且路径大小写正确；首页可切回旧背景 |
| F212 | 新旧功能集成 | 保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约 |

| 确认 ID | 主题（PRD） | 确认状态 | 直接承担 STEP |
|---|---|---|---|
| RQ-01 | 保留布局与入口，接入 demo 场景 | 已确认 | STEP-003、STEP-008、STEP-009、STEP-017 |
| RQ-02 | 加载截止、内容独立显示与旧请求保护 | 已确认 | STEP-004、STEP-005、STEP-006 |
| RQ-03 | 互动入口、访客门禁与倾斜主动授权 | 已确认 | STEP-009、STEP-010、STEP-011 |
| RQ-04 | 动态偏好的保存范围 | 已确认 | STEP-010 |
| RQ-05 | 首版设备与浏览器验收范围 | 已确认 | STEP-011、STEP-014、STEP-015、STEP-016、STEP-017 |
| RQ-06 | 自动降级后的恢复策略 | 已确认 | STEP-013 |

| 目标 ID | 目标／原成功标准（PRD） | 承担 STEP |
|---|---|---|
| G201 | 保留主页使用路径；现有入口、卡片、数据与权限行为保持；背景和人物交互符合 demo 的视觉方向 | STEP-003、STEP-008、STEP-009、STEP-017 |
| G202 | 加载可结束；接口或特效失败不永久遮挡页面，入口可以独立显示 | STEP-004、STEP-006 |
| G203 | 动态可控；更多互动提供开关，传感器可关闭，弹窗、通话与后台状态能正确暂停恢复 | STEP-007、STEP-010、STEP-011、STEP-012 |
| G204 | 降低素材传输；核心两图争取 ≤350 KiB，全套七图争取 800～900 KiB，同时通过清晰度与贴片对齐检查 | STEP-001、STEP-002、STEP-016 |
| G205 | 控制持续运行成本；普通手机目标接近 60fps，低档模式目标至少 30fps；持续掉帧按规则降级 | STEP-013、STEP-015 |

| 决策 ID | 主题／现结论（PRD） | 承担 STEP |
|---|---|---|
| V2-D01 | 布局与入口基线；保留当前生产项目主页布局、卡片和入口，以 §4 为准 | STEP-003、STEP-017 |
| V2-D02 | 背景与人物；替换为 demo v4 分层场景；完整静态画面优先，特效渐进增强 | STEP-003、STEP-008、STEP-009 |
| V2-D03 | 更多互动；增加“主页动态”和“倾斜视差”开关；沿用现有登录门禁 | STEP-010、STEP-011 |
| V2-D04 | 加载时序；保留正常 3000ms 最短展示、500ms 停留、550ms 退出；核心图片等待最多 5 秒，遮罩 8 秒兜底 | STEP-004 |
| V2-D05 | 业务数据；与遮罩完成解耦，首页请求批次 8 秒截止；区分未完成、失败、真实空态与访客态 | STEP-006 |
| V2-D06 | 并发保护；取消过期请求；写 UI 与处理 401 前检查请求代次及登录快照 | STEP-005、STEP-006 |
| V2-D07 | 性能与生命周期；单一主调度、环境特效优先 30fps、Canvas 有效 DPR 默认至多 1.5；统一暂停与降级 | STEP-007、STEP-008、STEP-012、STEP-013 |
| V2-D08 | 素材优化；优先头发和眨眼 PNG，保护透明边缘；导出首页小图，不覆盖其他页面原图 | STEP-001、STEP-002 |
| V2-D09 | 权限与业务；保留公共首页和交互登录；人物反馈本地执行；不增加后端接口、数据库或模型调用 | STEP-006、STEP-009、STEP-017 |
| V2-D10 | 发布与回退；新资源版本化，核对实际缓存与 HTTPS；保留旧背景及首页回退开关 | STEP-014 |
| V2-D11 | 文档与实现状态；新建 v2，保留 v1；本轮只记录，功能状态为待实施 | STEP-018 |
| V2-D12 | 动态偏好保存；当前浏览器长期保存主页动态选择，刷新、再次访问及登录切换均保留；不同设备分别设置，系统减少动态效果优先 | STEP-010 |
| V2-D13 | 首版验收范围；包含 iOS Safari、Android Chrome、iOS 微信和 Android 微信内置浏览器；具体机型与版本在验收前列明，语音沿用现有兼容策略 | STEP-011、STEP-014、STEP-015、STEP-016、STEP-017 |
| V2-D14 | 降级后恢复；同一页面实例保持降级档位；后台、弹窗和浏览器后退恢复不升档；刷新或全新打开主页时重新评估 | STEP-013 |

### 2.1 未编号约束与排除项

`CSTR-*` 仅为当前 PRD 未编号条款提供追踪，不是新增 `RQ-*` 或优先级。包含排除项与保留行为；每项来源均为 SRC-01／`PRD`。

| 约束 ID | 条款 | PRD 定位 | 承担／核对 STEP |
|---|---|---|---|
| CSTR-01 | 保留当前布局、朋友圈＋日记卡、顶栏关系、快捷栏与 CTA；不恢复旧三卡、横卡、装饰球或新增关怀位。 | §3.2、§4.1—§4.2 | STEP-003、STEP-017 |
| CSTR-02 | 关系等级、成长进度／满级算法与 milestones.known_days 沿用；失败不能当成真实 Lv0。 | §4.1、§5.2 | STEP-006、STEP-017 |
| CSTR-03 | 状态语使用 resolveStatusText；头像情绪更新与加载专用头像职责分离；首页小图不改变其他页映射。 | §4.1、§5.1、§7.1 | STEP-002、STEP-004、STEP-006、STEP-017 |
| CSTR-04 | 北京时间 HH:mm 与七时段保持；Good night 仅 hour<5 或 hour>=20；装饰波形语义保持。 | §4.1 | STEP-017 |
| CSTR-05 | 日记固定句、formatTime 四档、is_read===false 的 NEW 与真实 Lv0 锁保持，点击仍走登录门禁。 | §4.1、§5.2 | STEP-006、STEP-017 |
| CSTR-06 | Feed 公共预览、更新时间、配图、登录角标与 goFeed 未读定位保持；协调已有 visibilitychange 刷新，不额外轮询。 | §4.1、§5.2 | STEP-006、STEP-017 |
| CSTR-07 | 不重排业务卡片，不开发视频／入睡，不新增模型调用、后台 API、聚合接口或数据库迁移，不改变子页业务与语音协议、音频链路、计费。 | §4.2、§9.2 | STEP-003、STEP-005、STEP-006、STEP-009、STEP-012、STEP-017、STEP-018 |
| CSTR-08 | 装饰层不抢事件；业务按钮、卡片、弹窗和语音面板优先；保持正常手势、缩放与键盘，不照搬全场景 touch-action:none。 | §5.3 | STEP-003、STEP-009、STEP-010、STEP-011、STEP-012、STEP-017 |
| CSTR-09 | 保留 lxm_home_loader_done：同标签非刷新跳过，刷新及 clearToken 既有语义保持；跳过仍初始化场景和数据。 | §5.1 | STEP-004、STEP-005、STEP-006、STEP-007 |
| CSTR-10 | 保留加载品牌文案及完成提示；移除进度驱动的大面积模糊，用透明度过渡；减少动态时取消对应过渡，压缩不等于缩短固定展示。 | §5.1、§7.2 | STEP-004、STEP-016 |
| CSTR-11 | 未完成、失败、真实空态、访客态分开；超时不清登录；未知关系不渲染为 Lv0 锁；旧结果不能覆盖已知数据或新 token。 | §5.2 | STEP-005、STEP-006 |
| CSTR-12 | 新资源版本化，HTML 不长期不可变缓存；旧图保留并核对大小写；语音旧图不重新加入首页关键预热链，加载修复可随场景回退保留。 | §9.2 | STEP-001、STEP-002、STEP-004、STEP-014 |
| CSTR-13 | 减少雨和星光，再停止发丝物理，仍不稳则静态；同页保持降级，刷新／新实例重评，不覆盖动态关闭或系统减少动态偏好。 | §6；RQ-06 | STEP-013、STEP-015 |
| CSTR-14 | 多暂停原因互不覆盖；清理场景 CSS／WAAPI／RAF／计时器／传感器／观察器；bfcache 暂停，幂等恢复，真正销毁释放。 | §6 | STEP-007、STEP-008、STEP-011、STEP-012、STEP-013 |
| CSTR-15 | 首版场景、交互、加载含 iOS Safari、Android Chrome、iOS 微信、Android 微信；记录实际机型／版本／网络，个别通过不推定全体。 | §8；RQ-05 | STEP-001、STEP-002、STEP-003、STEP-004、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 |
| CSTR-16 | 倾斜只作为本地视觉输入；不上传或新增采集，不加埋点平台，不记录 token 或传感器原始数据；节约测算不当作账单或模型费用收益。 | §7.2、§9.2 | STEP-011、STEP-015、STEP-016 |
| CSTR-17 | 文档只记录真实实现与证据；历史 K1—K7、TD-HOME-08 等不在本轮重结算，不新增技术债编号，不把 demo／静态壳／模拟结果当整体验收。 | §3.2、§8、§9.2、§9.5 | STEP-015、STEP-016、STEP-017、STEP-018 |

技术债边界：本期不新增技术债编号。PRD §3.2 中 K1—K7 与旧技术债状态只保留历史含义；TD-HOME-08 的远期访客假设已不作为当前首页要求，不能据此宣称该历史债整体关闭。后端聚合、关系字段合并、视频／入睡与语音协议改造不纳入 STEP。

## 3. STEP 总览与显式依赖

PRD §9.3 的五个工作包被细分为可验证单元：素材／静态为 STEP-001—003；加载／请求为 STEP-004—006；生命周期／动效／交互为 STEP-007—012；性能策略与实测为 STEP-013、015，加载／素材传输实测为 STEP-016；缓存回退／保留能力／契约收口为 STEP-014、017、018。依赖表决定前置关系，不靠编号暗示；未标前置的 STEP 仍须核对同一代码基线。多个 STEP 修改同一主页／公共文件时不能据此推定可以同时写入。

| STEP | 唯一目标 | 阶段状态 | 前置 STEP | 直接需求 | 直接验收 |
|---|---|---|---|---|---|
| STEP-001 | 导出场景七图素材 | draft | 无 | F210 | AC212 |
| STEP-002 | 接入首页专用小图 | draft | 无 | F210 | AC212、AC213 |
| STEP-003 | 建立适配主页的静态场景 | draft | STEP-001 | F201、F202、RQ-01 | AC201、AC203、AC209、AC211 |
| STEP-004 | 实现有截止的加载遮罩 | draft | STEP-003 | F203、F201、RQ-02 | AC202、AC203、AC213 |
| STEP-005 | 给共享请求增加可选取消和失效保护 | draft | 无 | F204、F212、RQ-02 | AC205 |
| STEP-006 | 实现主页独立显示和有界数据批次 | draft | STEP-004、STEP-005 | F204、F203、RQ-02 | AC204、AC205、AC202 |
| STEP-007 | 建立场景统一生命周期 | draft | STEP-004 | F208、F209 | AC208、AC209、AC202 |
| STEP-008 | 接入渐进场景动效 | draft | STEP-001、STEP-003、STEP-007 | F201、F208、RQ-01 | AC201、AC208、AC209 |
| STEP-009 | 实现人物本地回应 | draft | STEP-003、STEP-007、STEP-008 | F205、RQ-01、RQ-03 | AC201、AC206 |
| STEP-010 | 在更多互动保存主页动态偏好 | draft | STEP-007、STEP-008 | F206、RQ-03、RQ-04 | AC206、AC217、AC208 |
| STEP-011 | 实现主动授权的倾斜视差 | draft | STEP-003、STEP-007、STEP-008、STEP-010 | F207、F206、F208、RQ-03、RQ-05 | AC207、AC217、AC208 |
| STEP-012 | 适配登录和语音面板暂停 | draft | STEP-007、STEP-008、STEP-011 | F208、F212 | AC208、AC214 |
| STEP-013 | 优化调度并保持自动降级档位 | draft | STEP-003、STEP-007、STEP-008、STEP-010、STEP-011、STEP-012 | F209、F208、RQ-06 | AC210、AC208 |
| STEP-014 | 验证版本化缓存与旧场景回退 | provisional | STEP-002、STEP-004、STEP-006、STEP-008、STEP-013 | F211、RQ-05 | AC215、AC213 |
| STEP-015 | 实测持续运行性能 | provisional | STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | F209、RQ-05 | AC210 |
| STEP-016 | 实测加载与素材传输 | provisional | STEP-001、STEP-002、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | F203、F210、F211、RQ-05 | AC212、AC213 |
| STEP-017 | 回归保留的主页能力 | draft | STEP-002、STEP-003、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | F212、F202、RQ-01、RQ-05 | AC214、AC206、AC211 |
| STEP-018 | 同步真实契约并收口追踪记录 | draft | STEP-001、STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 | F212 | AC216 |

## 4. 需求与验收覆盖映射

映射只列直接实现、独立子条款或直接验收责任。共享 AC 在正文中明确拆分，任何一个子 STEP 的完成都不等于整个原 AC 完成；全部子条款及要求的环境证据齐备后才可汇总。

| 需求 ID | 直接承担 STEP／子条款 |
|---|---|
| F201 | STEP-003：背景＋完整人物的基础画面及可选层缺失时的静态保底；STEP-004：核心图失败／挂起后的有界等待；STEP-008：全部可选场景动效与失败保留基础画面 |
| F202 | STEP-003：共用坐标变换、小屏／短屏／桌面与旋转适配；STEP-017：最终动效、倾斜与数据状态接入后的布局、贴片和手势集成验收 |
| F203 | STEP-004：首访、刷新、会话跳过及完整加载截止规则；STEP-006：会话跳过／正常启动仍只初始化一次数据；STEP-016：真实环境下的时序与截止达成 |
| F204 | STEP-005：请求可取消与 401 前上下文保护的共享请求部分；STEP-006：模块更新、批次截止、真实状态、去重与 UI 代次的首页部分 |
| F205 | STEP-009：人物有效区域、重复合并、本地回应与输入优先级 |
| F206 | STEP-010：更多入口门禁、主页动态总开关与长期偏好；倾斜实际状态由 STEP-011 接入；STEP-011：倾斜开关实际状态子条款 |
| F207 | STEP-011：倾斜权限、实际数据、关闭和旋转全部条款 |
| F208 | STEP-007：实例、暂停原因、资源登记、bfcache 与销毁基础条款；STEP-008：具体动作的 CSS／WAAPI／RAF／计时器清理子条款；STEP-011：倾斜监听暂停／恢复／销毁子条款；STEP-012：登录／语音覆盖层的暂停原因接入；STEP-013：暂停恢复不重置质量档位子条款 |
| F209 | STEP-007：单一主 RAF 与恢复时间差的调度基础条款；STEP-013：环境 30fps、DPR／像素上限、缓存纹理与按序持久降级；STEP-015：真实设备帧率、交互响应、长任务和内存趋势及低档目标 |
| F210 | STEP-001：场景七图导出；保持比例、透明通道、锚点及原资源；STEP-002：首页头像和日记派生图的完整接入链路；STEP-016：最终集成素材质量、体积与下载链路 |
| F211 | STEP-014：资源版本、实际缓存／HTTPS、背景大小写与回退全部条款；STEP-016：版本和缓存行为的传输实测部分 |
| F212 | STEP-005：共享 request 的默认调用与原有效 401 策略兼容；STEP-012：场景暂停不影响既有语音入口／音频链路的兼容子条款；STEP-017：§4 全部入口、数据与权限的用户可观察回归；STEP-018：实施完成后同步当前 H5 契约、静态回归及整体验收证据 |

| 验收 ID | PRD 原操作／预期 | 直接承担 STEP／子条款 |
|---|---|---|
| AC201 | 静态层与可选层依次就绪，观察并触碰人物；基础画面完整、贴片对齐；有预期动态与本地回应；可选层缺失不破坏人物 | STEP-003：基础画面与贴片对齐子条款；STEP-008：呼吸、眨眼、发丝、待机及环境层的可观察动态子条款；STEP-009：触碰人物的本地回应子条款 |
| AC202 | 首访、刷新、会话跳过，模拟模块晚加载及存储不可用；启动状态正确；普通模式遵守确认时序；跳过不漏挂载；异常存储不阻塞页面 | STEP-004：正常时序、跳过、模块晚加载与异常存储；跳过数据初始化由 STEP-006 联合负责；STEP-006：跳过加载仍初始化数据子条款；STEP-007：晚加载模块读取当前状态、跳过不漏场景初始化子条款 |
| AC203 | 阻断或损坏单张图片、使核心图一直挂起；核心等待 5 秒截止；前台可执行情况下遮罩最迟 8 秒兜底释放；入口可操作；迟到结果不盖回加载层 | STEP-003：图片失败时的已完成图层／底色呈现子条款；截止时序由 STEP-004 负责；STEP-004：核心 5 秒等待、遮罩 8 秒释放及迟到结果防护 |
| AC204 | 使业务请求一直挂起、离线或局部失败；页面结构独立显示；请求批次 8 秒截止并取消；显示对应失败状态，可局部重试；不假冒访客、Lv0 或真实空列表 | STEP-006：超时、局部失败、离线与真实空态 |
| AC205 | 慢请求期间登录、退出、重试，并让旧请求晚返回成功或 401；旧结果不覆盖新 UI、不清新 token；当前有效 401 仍执行既有策略；无重复刷新批次 | STEP-005：失效 401 不清新 token、有效 401 仍保持原策略；UI 代次由 STEP-006 联合负责；STEP-006：旧结果不写 UI，登录／退出／重试去重 |
| AC206 | 访客/已登录用户分别点击人物、更多、卡片和 CTA，并使用键盘；人物只做本地反馈，业务入口优先；访客门禁正确；登录后不自动重放或请求传感器权限 | STEP-009：人物反馈、业务控件优先及键盘子条款；更多门禁由 STEP-010 负责；STEP-010：更多访客门禁、登录不重放／不自动请求权限子条款；STEP-017：业务卡片／CTA／更多的点击及键盘、UI 优先、门禁与登录不重放／不自动授权集成子条款 |
| AC207 | 真机允许/拒绝倾斜，模拟无数据、不支持、非安全环境，关闭并旋转屏幕；实际状态与开关一致；关闭移除监听；无重复授权；有效恢复后方向正确 | STEP-011：真机允许／拒绝／无数据／不支持／不安全环境／关闭／旋转 |
| AC208 | 切后台、往返页面、开关登录/语音面板、切换动态及系统减少动态效果；多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位 | STEP-007：页面隐藏／返回、原因集合与幂等恢复子条款；具体动作／面板／传感器由对应 STEP 接入；STEP-008：动作暂停恢复、无跳变／闭眼残留子条款；STEP-010：动态开关与系统减少动态暂停子条款；STEP-011：暂停期间无传感器监听，合法恢复子条款；STEP-012：登录／语音面板组合暂停、恢复与无重复实例子条款；STEP-013：后台／面板／bfcache 恢复不重置质量子条款 |
| AC209 | 禁用 Canvas 或可选 API，制造特效初始化错误；静态画面与业务入口可用；不存在异常引发的整页中断 | STEP-003：场景能力缺失时的静态保底子条款；STEP-007：可选 API 与初始化异常隔离子条款；STEP-008：动效初始化／可选能力故障隔离子条款 |
| AC210 | 在列明的设备上记录新旧主页持续运行与低档表现，制造掉帧并恢复、刷新或全新打开；记录帧率、长任务、点击响应和内存趋势；掉帧按顺序降级，同一页面不自动升档；刷新或全新打开重新评估；达到经 Q201 确定环境下的目标 | STEP-013：质量策略、调度指标与同页保持／新实例重评子条款；真机目标测量由 STEP-015 联合负责；STEP-015：帧率、长任务、点击、内存和 Q201 目标的真实测量；策略由 STEP-013 联合负责 |
| AC211 | 在 375×667、390×844、430×932、1280×720 及横竖屏下检查；人脸与入口可见、贴片一致，底部内容可操作，安全区和正常页面手势可用 | STEP-003：指定尺寸、旋转、安全区和卡片变化时的构图／手势；STEP-017：同一最终集成快照的指定视口、旋转、动态／倾斜贴片和业务高度变化验收 |
| AC212 | 对比原始与优化素材，在实际尺寸及高像素密度设备显示；输出字节清单；确认预算达成情况、透明边缘、脸部清晰度和眨眼/发丝对齐；无重复大图下载 | STEP-001：场景七图的预算、清晰度与贴片对齐子条款；首页小图与最终集成下载由 STEP-002、STEP-016 负责；STEP-002：首页派生图质量及无重复原图下载子条款；STEP-016：最终实际尺寸／高像素密度质量、体积与无重复下载 |
| AC213 | 同设备同网络分别测冷加载、缓存访问及刷新；记录遮罩退出、入口可操作时间与传输量；可选特效不延长门闩，不把固定展示时间算成压缩收益 | STEP-002：首页小图请求清单与传输量记录子条款；完整新旧加载测量由 STEP-016 负责；STEP-004：API／可选特效不延长门闩；真实新旧测量由 STEP-016 负责；STEP-014：缓存／资源版本请求行为子条款；完整时序对比由 STEP-016 负责；STEP-016：完整新旧加载时序、缓存和传输测量 |
| AC214 | 访客及已登录用户逐一操作 §4 入口；设置、关系、记忆、Feed、日记、聊天和真实语音入口符合当前规则；声音链路不被场景占用影响 | STEP-012：声音链路不被场景占用影响子条款；完整入口回归由 STEP-017 负责；STEP-017：完整主页保留能力与真实语音入口／声音链路 |
| AC215 | 检查实际部署资源响应并更新资源版本、切回旧背景；HTTPS/权限行为、资源缓存及大小写引用正确；新版本可获取，回退可用，语音旧背景仍可访问 | STEP-014：实际响应、版本更新、场景回退与语音旧图 |
| AC216 | 实施后核对源码、回归测试与当前 H5 契约；同步本次真实行为；不把只测 demo、静态壳或模拟时钟的结果作为整体通过 | STEP-018：源码、相关回归与当前契约对账，不用局部模拟代替整体通过 |
| AC217 | 修改动态开关后刷新、再次访问、切换登录账号，并在另一设备访问或开启系统减少动态效果；当前浏览器保留选择；不同设备分别设置；登录切换不重置；系统减少动态效果优先；倾斜仍遵守新页面初始关闭与主动授权规则 | STEP-010：动态偏好刷新／再次访问／账号切换／设备与系统覆盖子条款；STEP-011：新页面倾斜初始关闭、主动授权子条款 |

RQ、G 和 V2-D 的覆盖见 §2 的独立表；CSTR 覆盖见 §2.1。它们不被改写为新 F、也不把相邻实现细节泛化映射为整条功能完成。

## 5. 共用发现门与验证规则

| 发现门 | 实施／验收前需要核实 | 负责位置 | 缺失时处理 |
|---|---|---|---|
| Q201／ENV-01 | 真实设备、系统／浏览器／微信版本和网络；帧率统计窗口、Canvas 总像素预算、降级检测窗口 | 需要该环境的 STEP 验收前列明；STEP-013 选参，STEP-015 性能、STEP-016 加载实测 | 保留已确认性能目标；参数或实际设备未定不宣称 AC210／相关真机 AC 完成 |
| Q202 | 导出工具实际能力、文件字节和透明质量；实际尺寸／高像素密度显示 | STEP-001／002、016 | 不以预算取代质量，不把“争取”改成绝对成功保证 |
| Q203／ENV-02 | 实际验证 URL、部署方式、外层 HTTPS、缓存头与浏览器行为 | STEP-014；STEP-011 权限，STEP-016 加载 | 先发现再验证，不能用 Nginx 80、localhost 或模拟作为线上支持证据 |
| 行为测试运行入口 | 可用 Python／pytest、Node／浏览器自动化依赖、启动方法及新增用例位置 | 每个产生对应行为的 STEP；源 SRC-09／10／15 | 已有文件与依赖已核实，但实际安装／命令未运行；若不可用保留待验证，不补造已存在构建命令 |
| 改造前对照基线 | 在任何主页源码改动前采集或保留同设备／同网络基线与源码标识 | 涉及源码修改的首个 STEP 前；STEP-015／016 使用 | 无真实对照不能报告相对性能／加载收益，前序模拟只作有限证据 |

每个功能 STEP 都要核对自己实际改变的用户行为，并随实现更新相关测试。`tests/test_h5_static_contract.py` 为 `existing`／SRC-09；基于该 pytest 文件选择的运行命令属于未来 `PLANNED` 调用，执行解释器与依赖可用性仍需发现，不把命令示例当已有 CI。现浏览器测试 `tests/test_realtime_voice_step036_states.cjs` 为 `existing`／SRC-15，可参考隔离写法，但其环境变量、测试 URL、Python 依赖和默认语音证据路径不能当首页已确认约定。

正常／异常／边界断言来自 PRD 和现契约，不能照抄实现作为预期；共享函数兼容需要覆盖旧调用。真机、受控浏览器、模拟时钟、静态子串、素材元数据和部署响应分别记录。四类首版浏览器按 CSTR-15 核对场景、交互和加载；运行环境仍成立时复用先前有效证据，仅对变化或缺口补测，不要求无依据地重复全量测试。

## 6. 完整 STEP 提示词

### [STEP-001] 导出场景七图素材

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：获得可用于正式主页的场景素材包和可核对的质量、尺寸、字节清单。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F210 | 原文：按 §7 预算优化，保持透明通道、画布比例与锚点；小图使用首页派生资源，原资源保留；本 STEP：场景七图导出；保持比例、透明通道、锚点及原资源 | PRD／SRC-01 |
| 验收 ID | AC212 | 原预期：输出字节清单；确认预算达成情况、透明边缘、脸部清晰度和眨眼/发丝对齐；无重复大图下载；本 STEP：场景七图的预算、清晰度与贴片对齐子条款；首页小图与最终集成下载由 STEP-002、STEP-016 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| 无 | 本 STEP 的实际代码／PRD 基线 | 按下表路径／符号核对输入，未改变前提才复用本轮读取 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css` | existing | REPO_BASELINE | SRC-13／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css::hair-front/side/back@22—24；blink@26 | 参考坐标与锚点；全场景 touch-action:none 不能照搬 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/index.html` | existing | REPO_BASELINE | SRC-14／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/index.html::素材分层 DOM | 七图图层和参考结构 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/background.webp` | existing | REPO_BASELINE | ASSET-01／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/background.webp::文件头／元数据：853×1844、RGB、165630 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/character.webp` | existing | REPO_BASELINE | ASSET-02／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/character.webp::文件头／元数据：853×1844、RGBA、284604 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_front_physics.png` | existing | REPO_BASELINE | ASSET-03／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_front_physics.png::文件头／元数据：456×417、RGBA、358769 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_side_physics.png` | existing | REPO_BASELINE | ASSET-04／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_side_physics.png::文件头／元数据：220×512、RGBA、120267 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_back_physics.png` | existing | REPO_BASELINE | ASSET-05／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_back_physics.png::文件头／元数据：168×445、RGBA、146555 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/blink_crop.png` | existing | REPO_BASELINE | ASSET-06／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/blink_crop.png::文件头／元数据：263×134、RGBA、70797 字节 | 场景原素材及画布／alpha 基线 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/lamp_glow.webp` | existing | REPO_BASELINE | ASSET-07／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/lamp_glow.webp::文件头／元数据：853×1844、RGBA、140176 字节 | 场景原素材及画布／alpha 基线 |
| `frontend/static/images/home-scene/v4/` | planned | PLANNED | 不适用 | PRD §9.1；新场景版本化导出资源 |
| `requirements.txt` | existing | REPO_BASELINE | SRC-10／requirements.txt::Pillow@48 | 已有依赖声明，不能据此推定执行环境可用 |

**输入**：
- demo 七图原素材及其画布、透明边界、贴片坐标；Q202 当前未有压缩结果。

**输出**：
- 新场景导出资源；逐图原始／导出字节、像素尺寸、透明能力及视觉对照记录。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 预算 | 核心两图争取 ≤350 KiB；全套七图争取 800～900 KiB，不是整页预算。 | F210、§7.1 |
| 保真 | 保留比例、透明留白、位置与旋转锚点；改变裁切／坐标时同步变换并复核。 | F210、§7.1 |

**开发任务**：
1. 复核七图清单，优先比较头发、眨眼的保留 alpha 导出，灯光可比较较小尺寸；不覆盖原件。
2. 按真实展示尺度比较脸部、发丝边缘、眼睛开合与贴片对齐；记录目标达成或未达成，不为体积牺牲质量。
3. 按 PRD 的版本化方向放置输出；导出参数及普通内部命名按已核实的项目约定确定。

**不在本 STEP 范围内**：
- 主页布局和加载代码；人物动效实现；不声称素材压缩比例就是内存或账单节约。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 逐图原图与导出图对照 | 字节清单可复算，脸部和贴片视觉合格；如未达到争取目标，保留差额与原因，不伪造通过。 | AC212 |
| 异常 | 透明边缘白边、糊脸或眨眼错位 | 淘汰该导出候选，原资源可恢复；不以预算单独判定合格。 | AC212 |
| 边界 | 实际尺寸及高像素密度显示；改变画布或裁切 | 记录设备／显示尺度；所有贴片坐标同步，未检查设备明确保留待验。 | AC212 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-001、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-002] 接入首页专用小图

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：首页初始头像、情绪切换、失败回退和日记图使用同内容的小尺寸派生资源。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F210 | 原文：按 §7 预算优化，保持透明通道、画布比例与锚点；小图使用首页派生资源，原资源保留；本 STEP：首页头像和日记派生图的完整接入链路 | PRD／SRC-01 |
| 验收 ID | AC212 | 原预期：输出字节清单；确认预算达成情况、透明边缘、脸部清晰度和眨眼/发丝对齐；无重复大图下载；本 STEP：首页派生图质量及无重复原图下载子条款 | PRD／SRC-01 |
| 验收 ID | AC213 | 原预期：记录遮罩退出、入口可操作时间与传输量；可选特效不延长门闩，不把固定展示时间算成压缩收益；本 STEP：首页小图请求清单与传输量记录子条款；完整新旧加载测量由 STEP-016 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| 无 | 本 STEP 的实际代码／PRD 基线 | 按下表路径／符号核对输入，未改变前提才复用本轮读取 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::handleAvatarError@1506；handleLoaderAvatarError@1511；emotionAvatarSrc@1543；头像 DOM@1289；日记图@1446；STATIC_ASSETS@1490 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::AVATAR_MAP@9；updateAvatarEmotion@615 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `首页头像和日记派生资源` | planned | PLANNED | 不适用 | PRD §7；具体文件名与路径按已核实的项目约定确定 |

**输入**：
- 现有默认／情绪头像、加载头像回退和日记占位图引用；F210 的原资源保留要求。

**输出**：
- 同内容的首页派生图；初始、情绪更新、错误回退与预载引用一致的首页接入。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 资源范围 | 只改变首页使用的派生路径；其他页原资源、映射和默认调用方式兼容。 | F210、§7.1 |
| 请求一致 | 相同素材使用一致 URL，避免不同查询参数导致重复下载。 | §7.1 |

**开发任务**：
1. 导出与实际展示尺寸匹配的默认／情绪头像及日记同内容缩略图；文件名、尺寸与导出参数按已核实的项目约定确定。
2. 覆盖顶部初始头像、情绪预加载、情绪失败、加载头像失败回退；不要先小图后又被公共映射换回大图。
3. 取消日记原图等非必需首页预载；保留加载专用头像的内容职责，不把它强制同步为顶栏情绪头像。
4. 使用正式首页请求记录证明派生链路和公共 API 兼容，保留优化前后清单。

**不在本 STEP 范围内**：
- 场景七图导出；关系／情绪业务语义改动；不替换其他页面图片。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 初始打开并切换各已存在情绪 | 首页使用对应派生图，状态语不变；其他页面调用仍使用既有默认映射。 | AC212 |
| 异常 | 派生图或情绪图失败 | 回退链路仍落到首页可用小图，不反复请求同一失败图、不把大图重加进门闩。 | AC212 |
| 边界 | 冷访问、缓存访问、刷新；检查所有 fallback 和预载 | 保留传输清单与视觉证据，同资源无不必要重复大图下载，不宣称固定加载节奏因此缩短。 | AC212、AC213 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-002、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-003] 建立适配主页的静态场景

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：现有主页布局上显示完整静态背景和人物，并在指定尺寸下保持人脸及业务入口可见。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F201 | 原文：背景＋完整人物构成静态底图；随后增强呼吸、眨眼、发丝、待机回应、灯光、雨与星光；任一可选层失败保留基础画面；本 STEP：背景＋完整人物的基础画面及可选层缺失时的静态保底 | PRD／SRC-01 |
| 需求 ID | F202 | 原文：所有贴片共用坐标变换；根据实际 UI 位置调整人物，脸部与入口可见；桌面采用居中竖向场景和暗色延展；本 STEP：共用坐标变换、小屏／短屏／桌面与旋转适配 | PRD／SRC-01 |
| 需求 ID | RQ-01 | 原文：保留布局与入口，接入 demo 场景；本 STEP：保留布局、入口并接入 demo 场景的静态部分 | PRD／SRC-01 |
| 验收 ID | AC201 | 原预期：基础画面完整、贴片对齐；有预期动态与本地回应；可选层缺失不破坏人物；本 STEP：基础画面与贴片对齐子条款 | PRD／SRC-01 |
| 验收 ID | AC203 | 原预期：核心等待 5 秒截止；前台可执行情况下遮罩最迟 8 秒兜底释放；入口可操作；迟到结果不盖回加载层；本 STEP：图片失败时的已完成图层／底色呈现子条款；截止时序由 STEP-004 负责 | PRD／SRC-01 |
| 验收 ID | AC209 | 原预期：静态画面与业务入口可用；不存在异常引发的整页中断；本 STEP：场景能力缺失时的静态保底子条款 | PRD／SRC-01 |
| 验收 ID | AC211 | 原预期：人脸与入口可见、贴片一致，底部内容可操作，安全区和正常页面手势可用；本 STEP：指定尺寸、旋转、安全区和卡片变化时的构图／手势 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 新场景导出资源；逐图原始／导出字节、像素尺寸、透明能力及视觉对照记录。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::主页 DOM@1283—1468 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css` | existing | REPO_BASELINE | SRC-13／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css::scene@4；贴片@22—26 | 参考坐标与锚点；全场景 touch-action:none 不能照搬 |
| `frontend/static/css/home-scene.css` | planned | PLANNED | 不适用 | PRD §9.1；限定场景作用域的样式 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |
| `frontend/static/images/home-scene/v4/` | planned | PLANNED | 不适用 | PRD §9.1；新场景版本化导出资源 |

**输入**：
- STEP-001 素材清单与对齐证据；当前主页的顶栏、Hero、快捷栏、Feed、日记、CTA DOM。

**输出**：
- 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 构图 | 根据实际 UI 位置调整人物；桌面居中竖向场景与暗色延展，避免整屏 cover 裁脸。 | F202 |
| 输入 | 装饰层不抢事件，保持正常手势／缩放／键盘，不搬 demo 全局样式。 | §5.3 |

**开发任务**：
1. 只在主页作用域接入背景和完整人物；先保证无需可选特效即可完整显示。
2. 让人物、头发、眨眼等贴片复用同一坐标变换；按卡片实际遮挡与视口变化重新校对，内部字段按已核实的项目约定确定。
3. 检查 PRD 四种视口及横竖屏、安全区、底部可操作性；保留业务卡片顺序和现有页面手势。
4. 坏图／缺少可选图／场景脚本或 Canvas 能力不可用时保留已完成图层或底色，并隔离场景错误。

**不在本 STEP 范围内**：
- 动态动作、开关与传感器；加载等待时间和主页取数；不把全页 JS 被禁用当作业务 JS 仍可运行的测试。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 375×667、390×844、430×932、1280×720，使用正式主页布局 | 背景与完整人物可见，脸部和所有入口可见，贴片对齐，桌面有暗色延展。 | AC201、AC211 |
| 异常 | 单张核心／可选图失败，或禁用场景可选能力 | 使用完成图层或底色，不出现破碎人物或整页异常；等待截止由 STEP-004 验证。 | AC203、AC209 |
| 边界 | 旋转、卡片高度变化、安全区及键盘／缩放 | 构图重新适配且贴片一致；业务控件和正常手势可用。 | AC211 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-003、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-004] 实现有截止的加载遮罩

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：核心图和正常展示节奏决定加载退出，业务数据与可选特效不会无限阻塞主页入口。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F203 | 原文：按 §5.1 显示或跳过加载页，核心图片、API 和可选特效按不同职责加载；异常有截止；本 STEP：首访、刷新、会话跳过及完整加载截止规则 | PRD／SRC-01 |
| 需求 ID | F201 | 原文：背景＋完整人物构成静态底图；随后增强呼吸、眨眼、发丝、待机回应、灯光、雨与星光；任一可选层失败保留基础画面；本 STEP：核心图失败／挂起后的有界等待 | PRD／SRC-01 |
| 需求 ID | RQ-02 | 原文：加载截止、内容独立显示与旧请求保护；本 STEP：加载截止与内容独立显示中的遮罩部分 | PRD／SRC-01 |
| 验收 ID | AC202 | 原预期：启动状态正确；普通模式遵守确认时序；跳过不漏挂载；异常存储不阻塞页面；本 STEP：正常时序、跳过、模块晚加载与异常存储；跳过数据初始化由 STEP-006 联合负责 | PRD／SRC-01 |
| 验收 ID | AC203 | 原预期：核心等待 5 秒截止；前台可执行情况下遮罩最迟 8 秒兜底释放；入口可操作；迟到结果不盖回加载层；本 STEP：核心 5 秒等待、遮罩 8 秒释放及迟到结果防护 | PRD／SRC-01 |
| 验收 ID | AC213 | 原预期：记录遮罩退出、入口可操作时间与传输量；可选特效不延长门闩，不把固定展示时间算成压缩收益；本 STEP：API／可选特效不延长门闩；真实新旧测量由 STEP-016 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::HOME_LOADER_KEY@1481；homeAuthMode／token 读取@1503；preloadImage@1534；dismissHomeLoader@1646；runHomeLoader@1687；initHomePage@1769／调用@2272；renderVisitorHome@1941；loadPage@2098 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::request／try 前 token 读取@83—84；clearToken@146 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-003 可用静态场景；当前加载文案、Session 语义及 PRD 的精确时序；实际 index.html 的内联启动入口、初始化前 token 读取和启动中必要存储操作；可在页面脚本执行前按存储对象／键／操作注入故障的受控测试。

**输出**：
- 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 正常时序 | 最短 3000ms、完成后停留 500ms、退出 550ms；即时就绪约 4.05 秒。 | §5.1、V2-D04 |
| 截止 | 核心下载及可用解码最多等待 5 秒；本次启动遮罩 8 秒兜底，恢复前台先检查绝对截止。 | §5.1、AC203 |
| Session | 同标签非刷新跳过；刷新／clearToken 保持原语义，跳过也初始化场景和数据；标记不可读写时按可用能力退化，不伪造标记成功。 | §5.1、§6 |
| 存储故障 | Session 标记、启动前 localStorage 访问／token 读取、启动途中必要写入分别注入；不得因异常让基础启动和加载截止无法建立。动态偏好故障仍由 STEP-010 直接验证。 | §5.3、§6、AC202 |
| 认证边界 | 存储异常不是服务端有效 401，不自行清除当前已知登录态或用失败冒充访客／真实 Lv0／空数据；本 STEP 保证结构、静态及入口启动可用，业务状态和请求保护仍按 STEP-005／006 的既有职责接入。 | §5.2、F204 |

**开发任务**：
1. 以背景＋人物为核心准备，不把 API、情绪头像或可选特效纳入完成门闩；加载页复用核心资源，不另下载大海报。
2. 记录启动与截止时刻，正常退出和异常兜底均幂等；pagehide 后恢复能检查过期时刻，迟到结果不会重建遮罩。
3. 让页面结构／入口可独立显示；后加载的场景模块读取当前阶段，不只订阅一次事件。
4. 保留品牌文案、完成提示与 Session key；去除进度驱动的持续大面积滤镜，减少动态时取消对应过渡。
5. 协调当前数据入口保持初始化一次；模块级数据失败／并发保护由 STEP-006 接入。
6. 从真实 index.html 的最早启动读取检查存储异常，不能只给 loader 函数或偏好读写加捕获。至少覆盖 sessionStorage.getItem/setItem/removeItem、页面脚本执行前 localStorage 访问／getItem('token')、启动途中关系缓存等必要写入失败；以现有异常及权限规则保持启动、静态保底和入口可用，不增加私有匿名请求或改变公共请求默认鉴权行为。
7. 直接加载正式主页，在首次／刷新／同标签非刷新返回路径按下表独立注入，记录故障对象、键、操作、发生阶段、加载释放与入口操作证据；不记录 token 内容。新动态偏好读写故障由 STEP-010 验证并复用其职责，不靠该偏好用例替代启动前 token 读取故障。

**不在本 STEP 范围内**：
- 修改展示节奏以追求测速；场景动作实现；不把进度 100% 当成所有业务数据成功。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 所有核心资源即时可用，API 与可选层仍在等待 | 遵守 3000/500/550ms 节奏，约 4.05 秒退出；API 与可选层不延长等待。 | AC202、AC213 |
| 异常 | 核心坏图／解码不完成／请求挂起，前台计时正常执行 | 核心 5 秒截止，遮罩最迟 8 秒直接释放；入口可用，迟到结果不再遮挡。 | AC203 |
| 边界 | 刷新、同标签返回、模块晚加载、隐藏后超过截止再返回 | 跳过仍初始化基础场景和数据；恢复按截止处理，无重复退出／挂载。 | AC202、AC203 |
| 异常（Session 标记） | 实际 index.html 首次／刷新／同标签返回，分别使 lxm_home_loader_done 的 getItem、setItem、removeItem 抛错；读取故障在脚本执行前注入，写入／移除在对应退出／刷新／clearToken 分支触发 | 读不到标记时按可用能力走加载；写入／移除失败不终止启动或遮罩释放，不伪造持久化成功；可读取合法完成标记的非刷新返回仍按原规则跳过，基础场景和数据不漏初始化。 | AC202 |
| 异常（启动前本地读取） | 在任何主页脚本执行前分别使 localStorage 属性访问或 getItem('token') 抛错；直接打开／刷新正式 index.html，并重复已保存 Session 标记的非刷新返回情形 | 启动状态和截止仍能建立，静态保底与业务入口可用；普通加载按确认时序，前台计时正常时遮罩最迟 8 秒退出；有合法可读 Session 标记时仍走原跳过路径；没有未捕获异常造成整页启动中断，存储异常不当有效 401。 | AC202 |
| 异常（启动途中写入） | 初始读取可用，在主页实际访问到的 setItem/removeItem 上注入异常，例如关系缓存写入／移除；分别保留已知数据与未完成占位观察 | 失败不阻塞结构、静态或入口，遮罩仍按原截止退出；不清当前已知登录态、不把失败覆盖为访客／真实 Lv0／空列表；具体模块请求和数据状态证据由 STEP-005／006 按原职责联合回传。 | AC202 |

**完成标志**：

- [ ] 本 STEP 全部直接验收子条款有证据，包括真实页面启动前本地读取、Session get/set/remove 与启动途中写入故障；偏好、模块状态及请求保护仍按对应 STEP 联合追踪。
- [ ] 存储故障记录含对象／键／操作／注入阶段、首次／刷新／非刷新返回路径、入口操作与遮罩释放时刻；测试加载实际 index.html，不用抽出函数或晚阶段偏好桩代替整页，未测／受控故障／真机范围分开。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-004、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-005] 给共享请求增加可选取消和失效保护

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：首页过期请求在共享请求层失去清 token 等副作用，原调用方式继续兼容。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F204 | 原文：主页结构和入口独立显示，数据按模块更新；8 秒请求批次截止，支持取消、去重、代次与登录快照保护；本 STEP：请求可取消与 401 前上下文保护的共享请求部分 | PRD／SRC-01 |
| 需求 ID | F212 | 原文：保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约；本 STEP：共享 request 的默认调用与原有效 401 策略兼容 | PRD／SRC-01 |
| 需求 ID | RQ-02 | 原文：加载截止、内容独立显示与旧请求保护；本 STEP：旧请求保护的共享层部分 | PRD／SRC-01 |
| 验收 ID | AC205 | 原预期：旧结果不覆盖新 UI、不清新 token；当前有效 401 仍执行既有策略；无重复刷新批次；本 STEP：失效 401 不清新 token、有效 401 仍保持原策略；UI 代次由 STEP-006 联合负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| 无 | 本 STEP 的实际代码／PRD 基线 | 按下表路径／符号核对输入，未改变前提才复用本轮读取 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `docs/contract/current/h5-app/api.md` | existing | CONTRACT | SRC-02／docs/contract/current/h5-app/api.md::§HTTP 401 处理策略 | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| `docs/contract/current/_shared/conventions.md` | existing | CONTRACT | SRC-03／docs/contract/current/_shared/conventions.md::H5 信封@12 | H5 响应 code=0；日记 items 等既有例外 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::request@83；handleUnauthorized@111；clearToken@146；AUTH_401_POLICIES@47 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `tests/test_h5_static_contract.py` | existing | REPO_BASELINE | SRC-09／tests/test_h5_static_contract.py::test_shared_login_modal_and_auth_policy_contract@266；test_protected_pages_redirect_to_home_login_once_contract@590 | 已有 pytest 静态入口；子串断言不等于浏览器集成验收 |

**输入**：
- 共享 request 及四种已有策略；首页登录快照／请求代次的 PRD 要求。

**输出**：
- 首页显式使用、默认兼容的取消和失效上下文保护能力。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 有效性 | 在 401 副作用前、响应解析后重新判断有效上下文；失效结果不得清新 token。 | §5.2 |
| 兼容 | 其他调用点原默认行为保持；不另造鉴权请求函数或服务端错误码。 | §5.2、§9.2 |
| 有效 401 | 仅当前有效请求进入既有四类策略；现契约无条件“先清 token”的增量前置条件在 STEP-018 同步。 | F212、CONTRACT SRC-02 |

**开发任务**：
1. 在共享请求流程提供可选取消信号／有效性检查，并在 fetch 中实际透传；具体选项名按已核实的项目约定确定。
2. 在 401 处理前以及异步解析后检查上下文，取消与失效结果交给首页已确认的生命周期处理，不伪装正常业务成功。
3. 核对取消、网络失败、无选项旧调用以及四种有效 401 行为；保留 clearToken 对原 Session key 的语义。
4. 基于真实共享函数编写行为验证，测试预期来自 PRD 与现契约；不以仅结束 Promise 等待证明请求已取消。

**不在本 STEP 范围内**：
- 首页批次、数据 UI 与重试按钮由 STEP-006 负责；不修改其他页权限、注册登录流程、后端或错误码。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 原 request 调用不传新选项，并分别返回当前有效 401 | 默认兼容；四类原策略执行且真实私有状态清理／导航符合现契约。 | AC205 |
| 异常 | 旧请求在新登录后晚返回 401；或被取消后晚返回 | 不清新 token，不交付过期数据；取消信号确实进入 fetch。 | AC205 |
| 边界 | 401 到达前、JSON 解析中登录上下文改变；并发有效／失效请求 | 保护覆盖异步边界，只当前有效 401 可执行副作用，无重复业务处理。 | AC205 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-005、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-006] 实现主页独立显示和有界数据批次

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：主页入口和各数据模块独立显示，取数在 8 秒批次截止内结束并抵御登录切换与旧响应。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F204 | 原文：主页结构和入口独立显示，数据按模块更新；8 秒请求批次截止，支持取消、去重、代次与登录快照保护；本 STEP：模块更新、批次截止、真实状态、去重与 UI 代次的首页部分 | PRD／SRC-01 |
| 需求 ID | F203 | 原文：按 §5.1 显示或跳过加载页，核心图片、API 和可选特效按不同职责加载；异常有截止；本 STEP：会话跳过／正常启动仍只初始化一次数据 | PRD／SRC-01 |
| 需求 ID | RQ-02 | 原文：加载截止、内容独立显示与旧请求保护；本 STEP：内容独立显示与请求保护的首页集成部分 | PRD／SRC-01 |
| 验收 ID | AC204 | 原预期：页面结构独立显示；请求批次 8 秒截止并取消；显示对应失败状态，可局部重试；不假冒访客、Lv0 或真实空列表；本 STEP：超时、局部失败、离线与真实空态 | PRD／SRC-01 |
| 验收 ID | AC205 | 原预期：旧结果不覆盖新 UI、不清新 token；当前有效 401 仍执行既有策略；无重复刷新批次；本 STEP：旧结果不写 UI，登录／退出／重试去重 | PRD／SRC-01 |
| 验收 ID | AC202 | 原预期：启动状态正确；普通模式遵守确认时序；跳过不漏挂载；异常存储不阻塞页面；本 STEP：跳过加载仍初始化数据子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-005 | 首页显式使用、默认兼容的取消和失效上下文保护能力。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `docs/contract/current/h5-app/api.md` | existing | CONTRACT | SRC-02／docs/contract/current/h5-app/api.md::§开放页访客态 | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::loadPage@2098；loadFeedHomeCard@2181；refreshHomeAfterLogin@1967；renderVisitorHome@1941；visibilitychange@2268 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::STEP-005 的 request 可选保护；finishAuthModal@509 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |

**输入**：
- STEP-004 独立入口和启动状态；STEP-005 共享取消／有效性能力；当前关系、日记、未读和 Feed 请求路径。

**输出**：
- 模块级未完成／成功／失败／真实空态／访客呈现；8 秒截止且可取消、去重的首页批次。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 批次 | 从本批次发起记录截止，8 秒后取消未结束请求；不能每个串行子请求重新获得 8 秒。 | F204、§5.2 |
| 访客 | 只读现契约允许的公共 Feed；不初始化关系、私有日记、未读等。 | §5.2、CONTRACT SRC-02 |
| 状态 | 未知关系不按 level=0 锁日记，超时不清登录，失败与空列表分开。 | §5.2 |

**开发任务**：
1. 入口和页面结构不等待 loadPage 最后添加 content-loaded；按模块更新占位与真实结果，保留 §4 的数据语义。
2. 把当前 loadPage、Feed 预览、登录恢复和局部重试纳入有效批次管理；关联代次／登录快照／取消控制器，内部字段按已核实的项目约定确定。
3. 新批次、登录变更、退出、重试取代旧批次时取消失效请求；UI 写入前再检查有效性。
4. 为失败模块提供有界局部重试并去重；协调 Feed 可见性刷新，场景恢复不额外发完整 loadPage。
5. 保留有效 401 的访客降级；不得用失败默认值覆盖已知关系、日记锁、角标或 Feed 数据。

**不在本 STEP 范围内**：
- 新聚合 API、新字段或私有匿名开放；加载展示时长；后台轮询。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 访客和已登录分别进入，模块按不同时间返回 | 结构／入口独立可用；访客只请求公共 Feed，登录用户各模块按真实结果更新。 | AC204、AC202 |
| 异常 | 全部挂起、局部失败、离线、失败后重试 | 批次 8 秒结束且未完成请求被取消；模块显示可区分失败，真实空态不混用，不清登录。 | AC204 |
| 边界 | 请求中登录／退出／重试，旧成功或旧 401 晚到，切前台时已有 Feed 刷新 | 旧结果不写 UI、不清新 token；有效 401 正常降级；刷新和重试无重复批次，未知关系不是 Lv0。 | AC205、AC204 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-006、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-007] 建立场景统一生命周期

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：场景只有一个幂等实例和主调度，暂停原因叠加、恢复及销毁都能独立验证。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F208 | 原文：统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积；本 STEP：实例、暂停原因、资源登记、bfcache 与销毁基础条款 | PRD／SRC-01 |
| 需求 ID | F209 | 原文：单一主调度，按时间差运动；环境特效优先 30fps；DPR 默认至多 1.5，另设像素上限；按 §6 降级，同一页面实例不自动升档；本 STEP：单一主 RAF 与恢复时间差的调度基础条款 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：页面隐藏／返回、原因集合与幂等恢复子条款；具体动作／面板／传感器由对应 STEP 接入 | PRD／SRC-01 |
| 验收 ID | AC209 | 原预期：静态画面与业务入口可用；不存在异常引发的整页中断；本 STEP：可选 API 与初始化异常隔离子条款 | PRD／SRC-01 |
| 验收 ID | AC202 | 原预期：启动状态正确；普通模式遵守确认时序；跳过不漏挂载；异常存储不阻塞页面；本 STEP：晚加载模块读取当前状态、跳过不漏场景初始化子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::runHomeLoader@1687；initHomePage@1769 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | existing | REPO_BASELINE | SRC-11／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js::启动循环@416—437 | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| `frontend/static/js/home-scene-core.js` | planned | PLANNED | 不适用 | PRD §9.1；可独立验证的坐标、时间与动效规则 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-004 当前启动／遮罩状态与 STEP-003 静态场景；PRD 暂停原因和清理范围。

**输出**：
- 单实例场景生命周期、原因集合、受控主调度与资源清理基础。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 暂停原因 | 加载、页面隐藏、登录弹窗、语音面板、用户关动态、系统减少动态效果；任一原因存在即暂停。 | §6 |
| 恢复 | 移除一个原因不覆盖其他原因；恢复重置时间差、不追赶后台时间；pageshow 幂等。 | §6 |
| 清理 | 场景 CSS／WAAPI／RAF／动作计时器／传感器／布局观察器一并管理；bfcache 保留走暂停，真正销毁释放。 | F208、§6 |

**开发任务**：
1. 实现幂等挂载和可读取的当前生命周期；主调度按时间差运行，约束异常大步长，字段与函数名按已核实的项目约定确定。
2. 统一登记动作、帧回调、计时器、事件监听与观察器；后续 STEP 接入时使用同一资源治理，不追加独立常驻循环。
3. 接入遮罩、visibility、pagehide/pageshow 与系统减少动态；外部面板适配由 STEP-012 完成。
4. 为可选 API 增加能力检测及异常隔离，静态层与业务脚本保持可用；测试只判定本 STEP 基础条款，不冒充全部 AC208 已通过。

**不在本 STEP 范围内**：
- 具体人物／环境动作、真实倾斜权限和面板适配；不暂停或修改语音音频链路。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 遮罩退出且无原因，重复调用挂载／恢复 | 仅一个场景实例与主调度；晚模块读取已有状态后正确接入。 | AC202、AC208 |
| 异常 | 多暂停原因同时存在，移除其中一个；初始化故障／无可选 API | 所有原因解除前不恢复；错误限于特效，静态主页可用。 | AC208、AC209 |
| 边界 | bfcache 后退恢复／真正 pagehide 销毁，反复进入离开 | 恢复不追赶时间；销毁后无循环／监听／观察器残留，重复操作不累积实例。 | AC208 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-007、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-008] 接入渐进场景动效

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：呼吸、眨眼、发丝、待机、灯光、雨和星光在静态画面后渐进增强，并受统一生命周期控制。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F201 | 原文：背景＋完整人物构成静态底图；随后增强呼吸、眨眼、发丝、待机回应、灯光、雨与星光；任一可选层失败保留基础画面；本 STEP：全部可选场景动效与失败保留基础画面 | PRD／SRC-01 |
| 需求 ID | F208 | 原文：统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积；本 STEP：具体动作的 CSS／WAAPI／RAF／计时器清理子条款 | PRD／SRC-01 |
| 需求 ID | RQ-01 | 原文：保留布局与入口，接入 demo 场景；本 STEP：demo 动态场景的渐进增强部分 | PRD／SRC-01 |
| 验收 ID | AC201 | 原预期：基础画面完整、贴片对齐；有预期动态与本地回应；可选层缺失不破坏人物；本 STEP：呼吸、眨眼、发丝、待机及环境层的可观察动态子条款 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：动作暂停恢复、无跳变／闭眼残留子条款 | PRD／SRC-01 |
| 验收 ID | AC209 | 原预期：静态画面与业务入口可用；不存在异常引发的整页中断；本 STEP：动效初始化／可选能力故障隔离子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 新场景导出资源；逐图原始／导出字节、像素尺寸、透明能力及视觉对照记录。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | existing | REPO_BASELINE | SRC-11／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js::scheduleBlink@182；idleAction@199；启动循环@416—437 | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js` | existing | REPO_BASELINE | SRC-12／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js::createBlinkPlan@58；createIdleDelay@76；createTwinklePlan@93 | 参考计算与动效计划；参数不是新的业务决定 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css` | existing | REPO_BASELINE | SRC-13／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css::呼吸及贴片样式 | 参考坐标与锚点；全场景 touch-action:none 不能照搬 |
| `frontend/static/css/home-scene.css` | planned | PLANNED | 不适用 | PRD §9.1；限定场景作用域的样式 |
| `frontend/static/js/home-scene-core.js` | planned | PLANNED | 不适用 | PRD §9.1；可独立验证的坐标、时间与动效规则 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-001／STEP-003 素材和共用坐标；STEP-007 运行／暂停及资源登记能力。

**输出**：
- 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 启动 | 遮罩已退出、相关素材可用且无暂停原因才启动；静态／减少动态模式不抢加载不用的可选资源。 | §5.1 |
| 失败 | 任一可选层失败保留完整人物和背景，不能因局部初始化异常中断主页。 | F201、AC209 |
| 动作 | 使用 demo 作为视觉参考，不新增业务语义。 | F201 |

**开发任务**：
1. 把参考呼吸、眨眼、发丝、待机和环境层接到主调度与注册资源；不复制 demo 的多条常驻 RAF。
2. 逐层检查资源与能力后渐进启用，隔离错误；动作停止时复位自然静态姿态，眨眼和延迟动作可取消。
3. 暂停／恢复覆盖 CSS、WAAPI、JS、待机与双眨眼的延迟，不让已排队动作越过暂停边界。
4. 环境绘制与纹理缓存、最终质量档位由 STEP-013 调整；本 STEP 输出功能动效及资源治理证据。

**不在本 STEP 范围内**：
- 人物主动点击／键盘输入、更多开关、倾斜与自动降级；不带入 demo 控制面板。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 静态层就绪后逐个可选层成功，动态运行条件满足 | 七类预期动效可观察，人物与贴片一致；入口保持可用。 | AC201 |
| 异常 | 头发／眨眼／灯光坏图或 Canvas／WAAPI 初始化异常 | 仅失败层不展示，基础完整；场景异常不终止主页业务。 | AC201、AC209 |
| 边界 | 眨眼半途或待机／延迟动作中隐藏并恢复；反复挂载 | 停止后自然姿态、无闭眼残留；恢复无跳变、不追赶或重复调度。 | AC208 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-008、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-009] 实现人物本地回应

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：人物有效区域的点击和键盘激活只产生轻微本地回应，并让业务 UI 优先接收输入。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F205 | 原文：轻微本地回应，重复触发合并；不触发页面跳转、聊天、关系写入；UI 按钮和覆盖层优先；本 STEP：人物有效区域、重复合并、本地回应与输入优先级 | PRD／SRC-01 |
| 需求 ID | RQ-01 | 原文：保留布局与入口，接入 demo 场景；本 STEP：demo 人物本地交互部分 | PRD／SRC-01 |
| 需求 ID | RQ-03 | 原文：互动入口、访客门禁与倾斜主动授权；本 STEP：访客人物反馈与业务入口隔离子条款 | PRD／SRC-01 |
| 验收 ID | AC201 | 原预期：基础画面完整、贴片对齐；有预期动态与本地回应；可选层缺失不破坏人物；本 STEP：触碰人物的本地回应子条款 | PRD／SRC-01 |
| 验收 ID | AC206 | 原预期：人物只做本地反馈，业务入口优先；访客门禁正确；登录后不自动重放或请求传感器权限；本 STEP：人物反馈、业务控件优先及键盘子条款；更多门禁由 STEP-010 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | existing | REPO_BASELINE | SRC-11／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js::acknowledge@227；characterRig click@265 | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js` | existing | REPO_BASELINE | SRC-12／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js::createAcknowledgePlan@80 | 参考计算与动效计划；参数不是新的业务决定 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::业务按钮／卡片 DOM@1283—1468 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/css/home-scene.css` | planned | PLANNED | 不适用 | PRD §9.1；限定场景作用域的样式 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-003 构图／可操作区域；STEP-007 暂停状态；STEP-008 可管理动作。

**输出**：
- 可点击、可键盘激活、重复合并且不穿透业务 UI 的人物本地反馈。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 本地边界 | 不跳页、不请求聊天／模型、不写关系；访客反馈不初始化私有数据。 | F205、§5.3 |
| 允许条件 | 动态允许且无暂停原因才启动，减少动态／关闭动态时点击不启动动作。 | §5.3 |
| 重复输入 | 重复触发合并，业务按钮、卡片、弹窗、语音面板优先。 | F205 |

**开发任务**：
1. 根据正式场景有效人物区域接入点击与键盘；动作以 demo 轻微回应为参考，不添加业务操作。
2. 复用统一动作控制避免连点堆叠；暂停条件阻止触发，具体内部命名按已核实的项目约定确定。
3. 核对控件、卡片及覆盖层的命中，不取消页面正常缩放／手势；记录网络请求证明纯本地反馈。

**不在本 STEP 范围内**：
- 更多登录门禁、倾斜、关系写入及新模型能力；不改变已有入口点击路径。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 访客／登录用户点击人物或用 Enter／Space 激活 | 出现轻微本地回应；无聊天／关系请求和跳转，访客无私有初始化。 | AC201、AC206 |
| 异常 | 动态关闭、系统减少动态或任一暂停原因存在 | 不启动动作；已经暂停的动作不会被点击重新激活。 | AC206 |
| 边界 | 高频点击、键盘连发、点击覆盖人物的卡片／弹窗 | 重复反馈合并；控件执行自身操作，人物不抢事件，正常手势可用。 | AC206 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-009、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-010] 在更多互动保存主页动态偏好

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：已登录用户通过现有更多入口控制主页动态，选择在当前浏览器长期保留并服从系统减少动态效果。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F206 | 原文：提供主页动态、倾斜视差的开关及实际状态；无已保存选择时动态默认开启，之后长期沿用当前浏览器选择；系统减少动态效果优先；本 STEP：更多入口门禁、主页动态总开关与长期偏好；倾斜实际状态由 STEP-011 接入 | PRD／SRC-01 |
| 需求 ID | RQ-03 | 原文：互动入口、访客门禁与倾斜主动授权；本 STEP：更多入口及访客登录规则子条款 | PRD／SRC-01 |
| 需求 ID | RQ-04 | 原文：动态偏好的保存范围；本 STEP：动态偏好完整保存范围 | PRD／SRC-01 |
| 验收 ID | AC206 | 原预期：人物只做本地反馈，业务入口优先；访客门禁正确；登录后不自动重放或请求传感器权限；本 STEP：更多访客门禁、登录不重放／不自动请求权限子条款 | PRD／SRC-01 |
| 验收 ID | AC217 | 原预期：当前浏览器保留选择；不同设备分别设置；登录切换不重置；系统减少动态效果优先；倾斜仍遵守新页面初始关闭与主动授权规则；本 STEP：动态偏好刷新／再次访问／账号切换／设备与系统覆盖子条款 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：动态开关与系统减少动态暂停子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `docs/contract/current/h5-app/api.md` | existing | CONTRACT | SRC-02／docs/contract/current/h5-app/api.md::§共享登录弹窗／开放页访客态 | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::handleHomeQuickAction@1990；openHomeLoginModal@1963；refreshHomeAfterLogin@1967 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::openLoginModal@353；finishAuthModal@509 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `frontend/static/css/home-scene.css` | planned | PLANNED | 不适用 | PRD §9.1；限定场景作用域的样式 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-007／STEP-008 的动态运行和暂停能力；现有更多入口及登录恢复行为。

**输出**：
- 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 默认与保存 | 无已存选择默认开启；当前浏览器长期保留，刷新、重访和登录切换不重置，不同步账号／设备。 | F206、RQ-04 |
| 系统优先 | 系统减少动态始终优先；动态重新开启不自动申请传感器权限。 | §5.3 |
| 登录门禁 | 访客先共享登录窗，登录只恢复登录数据，不自动执行原操作。 | §5.3、CONTRACT SRC-02 |

**开发任务**：
1. 扩展当前 more 分支并沿用登录门禁；提供主页动态与倾斜入口，倾斜权限和真实运行由 STEP-011 完成。
2. 在动态首次可能启动前读取已存主页动态选择，并通过统一暂停状态应用，避免已关闭偏好仍短暂启动。
3. 长期保存当前浏览器选择；具体存储键和 UI 内部命名按已核实的项目约定确定，不更改现有 Session key。
4. 处理系统减少动态变化与动态偏好存储读写抛错；在正式主页首次可能运行动态之前及用户切换时注入偏好故障，UI 分开表达用户选择和实际允许运行状态，不把系统抑制显示为动态已运行。首页启动前 token 读取及 Session 标记故障的直接证据归 STEP-004，本 STEP 用例不能替代。

**不在本 STEP 范围内**：
- 账号同步、设备同步、记住倾斜开启意图跨新页面；不重放触发登录的原操作。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 登录用户修改动态并刷新、再次访问、切换账号 | 当前浏览器保留选择，新页面初始化即遵守；不同设备独立，无账号同步。 | AC217 |
| 异常 | 访客点击更多，登录／取消；在真实主页首次启动动态前、用户切换偏好时分别使动态偏好读／写抛错 | 沿用共享弹窗；登录不自动打开原动作或申请权限，偏好存储异常不阻断页面，仍服从系统减少动态；启动前 token／Session 故障证据由 STEP-004 负责，不据本行宣称已覆盖。 | AC206、AC217 |
| 边界 | 系统减少动态切换，多暂停原因叠加，关闭后再开启动态 | 系统优先；其他原因仍存在不恢复；开启动态不自动弹传感器授权。 | AC208、AC217 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-010、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-011] 实现主动授权的倾斜视差

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：倾斜从新页面初始关闭，经用户主动授权及有效数据检查后运行，并可可靠关闭和旋转校准。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F207 | 原文：倾斜初始关闭；用户操作中申请权限；检查支持、安全环境、授权结果与实际数据；关闭移除监听，旋转后重新校准；本 STEP：倾斜权限、实际数据、关闭和旋转全部条款 | PRD／SRC-01 |
| 需求 ID | F206 | 原文：提供主页动态、倾斜视差的开关及实际状态；无已保存选择时动态默认开启，之后长期沿用当前浏览器选择；系统减少动态效果优先；本 STEP：倾斜开关实际状态子条款 | PRD／SRC-01 |
| 需求 ID | F208 | 原文：统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积；本 STEP：倾斜监听暂停／恢复／销毁子条款 | PRD／SRC-01 |
| 需求 ID | RQ-03 | 原文：互动入口、访客门禁与倾斜主动授权；本 STEP：倾斜主动授权 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：四类首版浏览器中的权限／不支持路径 | PRD／SRC-01 |
| 验收 ID | AC207 | 原预期：实际状态与开关一致；关闭移除监听；无重复授权；有效恢复后方向正确；本 STEP：真机允许／拒绝／无数据／不支持／不安全环境／关闭／旋转 | PRD／SRC-01 |
| 验收 ID | AC217 | 原预期：当前浏览器保留选择；不同设备分别设置；登录切换不重置；系统减少动态效果优先；倾斜仍遵守新页面初始关闭与主动授权规则；本 STEP：新页面倾斜初始关闭、主动授权子条款 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：暂停期间无传感器监听，合法恢复子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | existing | REPO_BASELINE | SRC-11／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js::onOrientation@119；enableTilt@130 | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js` | existing | REPO_BASELINE | SRC-12／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js::normalizeOrientation@48 | 参考计算与动效计划；参数不是新的业务决定 |
| `frontend/static/js/home-scene-core.js` | planned | PLANNED | 不适用 | PRD §9.1；可独立验证的坐标、时间与动效规则 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-010 更多控制和动态偏好；STEP-003 共用坐标；STEP-007 生命周期；四浏览器验收范围。

**输出**：
- 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 初始 | 每个全新页面初始关闭，主动操作链内申请权限；授权获准不代表实际数据可用。 | F207、§5.3 |
| 实际状态 | 至少区分关闭、等待授权／数据、已开启、不可用；拒绝／不支持／非安全环境／无数据给简短原因。 | §5.3 |
| 暂停恢复 | 关闭动态停止监听，重新开动态不自动申请权限；暂停可保留意图，仅恢复条件满足才继续已允许监听。 | §5.3 |

**开发任务**：
1. 接入能力、安全环境、授权及有效方向数据检查；状态和简短反馈以 PRD 为依据，内部字段／无数据检测细节按已核实的项目约定确定。
2. 传感器事件只更新输入，由统一主调度应用；关闭、隐藏、覆盖层暂停、销毁移除监听，不重复注册。
3. 处理横竖屏校准、主动再次尝试和权限晚返回的生命周期有效性，不能重复自动弹权限请求。
4. 在列明的 iOS Safari、Android Chrome、iOS 微信、Android 微信真实环境记录允许／拒绝／不可用路径；模拟故障单列，不替代真机授权证据。

**不在本 STEP 范围内**：
- 传感器数据上传、新采集、账号同步、新页面自动开启；不改变微信语音兼容策略。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 新页面初始关闭，用户主动点击并在真机允许，方向数据有效 | 开关与实际状态一致，视差由主调度应用；关闭立即停止监听。 | AC207、AC217 |
| 异常 | 拒绝、无有效数据、不支持或非安全环境 | 给出原因并保持关闭／不可用，不误显示为已开启、不反复自动弹权限。 | AC207 |
| 边界 | 授权处理中关闭／隐藏，横竖屏旋转，弹窗／动态暂停后恢复 | 失效授权结果不重启场景；重新校准；仅全部原因解除且许可有效时恢复，无重复监听。 | AC207、AC208 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-011、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-012] 适配登录和语音面板暂停

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：登录弹窗或语音面板实际可见时暂停场景，关闭后只在全部暂停原因解除时恢复。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F208 | 原文：统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积；本 STEP：登录／语音覆盖层的暂停原因接入 | PRD／SRC-01 |
| 需求 ID | F212 | 原文：保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约；本 STEP：场景暂停不影响既有语音入口／音频链路的兼容子条款 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：登录／语音面板组合暂停、恢复与无重复实例子条款 | PRD／SRC-01 |
| 验收 ID | AC214 | 原预期：设置、关系、记忆、Feed、日记、聊天和真实语音入口符合当前规则；声音链路不被场景占用影响；本 STEP：声音链路不被场景占用影响子条款；完整入口回归由 STEP-017 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::openLoginModal@353；closeLoginModal@385；auth-modal-open@370 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `frontend/static/js/voice-entry.js` | existing | REPO_BASELINE | SRC-06／frontend/static/js/voice-entry.js::show@119；begin@401；close@473；voice:connected@263；returnToChat@456 | 面板实际可见状态；微信语音保持不支持的当前策略 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-007 原因集合与 STEP-008／STEP-011 已登记的动作和传感器；当前登录与语音面板实际显示行为。

**输出**：
- 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 暂停触发 | 按面板实际打开／关闭，不等语音连接成功才暂停；准备、权限说明、呼叫、结果、错误面板均包含。 | §6、§9.1 |
| 范围 | 优先主页适配，不修改语音协议、麦克风、传输、结算或公共登录语义。 | §4.2、§9.1 |
| 组合 | 面板关闭仅移除该原因；用户关闭、后台或系统减少动态仍有效。 | F208 |

**开发任务**：
1. 依据已核实的 DOM／可见状态接入主页适配，具体实现按已核实的项目约定确定；发现必须修改公共文件时限于可见状态兼容接点。
2. 覆盖登录成功、取消、Escape、遮罩关闭及语音准备／未接通／通话／终态／返回聊天路径；面板可见期间停止场景动作和方向监听。
3. 按原因集合恢复，重复打开／关闭不创建新实例；适配观察资源由统一销毁处理。
4. 保留受控面板测试与真实可用语音环境中的场景暂停／声音证据，分别标明模拟和真实部分。

**不在本 STEP 范围内**：
- 语音协议、音频链路、计费和登录流程改版；不将 voice:connected 当作面板开启的唯一来源。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 打开登录窗或语音准备面板，再正常关闭 | 面板出现即暂停场景与传感器，关闭且无其他原因才恢复。 | AC208 |
| 异常 | 授权拒绝、无法接通、语音结果页，登录中取消或失败 | 面板可见期间持续暂停；错误路径关闭不会留下暂停原因或提前恢复。 | AC208 |
| 边界 | 隐藏页面＋开面板＋关闭动态叠加，重复开关，真实语音可用环境 | 移除单原因不能恢复；无重复实例；语音声音链路和既有控制可用，未真测部分明确待验。 | AC208、AC214 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-012、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-013] 优化调度并保持自动降级档位

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：场景按已确认顺序降低运行成本，同页恢复不自动升档，刷新或全新实例才重新评估。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F209 | 原文：单一主调度，按时间差运动；环境特效优先 30fps；DPR 默认至多 1.5，另设像素上限；按 §6 降级，同一页面实例不自动升档；本 STEP：环境 30fps、DPR／像素上限、缓存纹理与按序持久降级 | PRD／SRC-01 |
| 需求 ID | F208 | 原文：统一管理多种暂停原因、计时器、CSS/WAAPI/RAF、传感器和观察器；不存在重复挂载和资源累积；本 STEP：暂停恢复不重置质量档位子条款 | PRD／SRC-01 |
| 需求 ID | RQ-06 | 原文：自动降级后的恢复策略；本 STEP：同页面保持降级与新页面重评的全部规则 | PRD／SRC-01 |
| 验收 ID | AC210 | 原预期：记录帧率、长任务、点击响应和内存趋势；掉帧按顺序降级，同一页面不自动升档；刷新或全新打开重新评估；达到经 Q201 确定环境下的目标；本 STEP：质量策略、调度指标与同页保持／新实例重评子条款；真机目标测量由 STEP-015 联合负责 | PRD／SRC-01 |
| 验收 ID | AC208 | 原预期：多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位；本 STEP：后台／面板／bfcache 恢复不重置质量子条款 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-012 | 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | existing | REPO_BASELINE | SRC-11／/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js::renderParallax@89；独立绘制循环启动@425—427；ResizeObserver@416 | demo 动效参考；独立循环、计时器和传感器接入需重组 |
| `frontend/static/js/home-scene-core.js` | planned | PLANNED | 不适用 | PRD §9.1；可独立验证的坐标、时间与动效规则 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |
| `frontend/static/css/home-scene.css` | planned | PLANNED | 不适用 | PRD §9.1；限定场景作用域的样式 |

**输入**：
- STEP-007 主调度与 STEP-008 动效；STEP-010／STEP-011／STEP-012 偏好、传感器和恢复行为；Q201 参数测量门。

**输出**：
- 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 频率及像素 | 一条场景主 RAF；环境特效优先 30fps；有效 DPR 默认至多 1.5，再受总像素预算约束。 | F209、§6 |
| 顺序 | 先减少雨／星光，再停止发丝物理，仍不稳定则静态。 | §6 |
| 恢复 | 后台、弹窗、浏览器后退保留当前档位；刷新／全新主页重新评估，不强制最高档或覆盖偏好。 | V2-D14、RQ-06 |
| 未定参数 | 总像素上限、降级统计窗口以 Q201 真机量测确定；不补造新的掉帧阈值或降低已确认目标。 | Q201 |

**开发任务**：
1. 缓存光点／雨纹理，避免逐帧渐变创建与 pointermove 布局测量；尺寸变化才更新布局，减少持续大面积 filter、叠加毛玻璃及不必要 will-change。
2. 将环境绘制节奏、DPR 与像素预算约束接入主调度；像素上限、统计窗口及内部字段按已核实的项目约定确定，并记录测量依据。
3. 实现持续掉帧后的按序降级及同实例保持，不做循环自动升档；新实例重新评估时保留动态关闭和系统覆盖。
4. 用当前真实恢复路径检查质量状态，在验收环境确定后交 STEP-015 量测目标；参数未定时仅保留局部验证，不能声称 AC210 全部通过。

**不在本 STEP 范围内**：
- 新增业务优先级或设备枚举；不修改近 60fps／低档至少 30fps 的已确认目标。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 列明环境的正常运行，观察主调度与环境绘制／Canvas 尺寸 | 单一场景主 RAF，环境优先 30fps；DPR≤1.5 且遵守记录的像素上限，指标可复查。 | AC210 |
| 异常 | 按记录窗口制造持续掉帧，依次回到可用运行状态 | 按雨／星光→发丝→静态顺序降级；同实例不自动提高质量。 | AC210 |
| 边界 | 降级后切后台、关弹窗、bfcache 返回；刷新／全新打开且保存动态关闭或系统减少动态 | 恢复保留档位；新实例重评，不强制升至最高、不覆盖用户或系统抑制。 | AC208、AC210 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-013、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-014] 验证版本化缓存与旧场景回退

**阶段状态**：`provisional`；实施状态 `NOT_STARTED`。

**目标**：新资源可更新、旧图可访问，场景回退可用且不撤销加载修复。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F211 | 原文：使用版本化资源；检查真实缓存头与 HTTPS；旧图保留且路径大小写正确；首页可切回旧背景；本 STEP：资源版本、实际缓存／HTTPS、背景大小写与回退全部条款 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：四类首版验收环境的部署／HTTPS 行为检查部分 | PRD／SRC-01 |
| 验收 ID | AC215 | 原预期：HTTPS/权限行为、资源缓存及大小写引用正确；新版本可获取，回退可用，语音旧背景仍可访问；本 STEP：实际响应、版本更新、场景回退与语音旧图 | PRD／SRC-01 |
| 验收 ID | AC213 | 原预期：记录遮罩退出、入口可操作时间与传输量；可选特效不延长门闩，不把固定展示时间算成压缩收益；本 STEP：缓存／资源版本请求行为子条款；完整时序对比由 STEP-016 负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-002 | 同内容的首页派生图；初始、情绪更新、错误回退与预载引用一致的首页接入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-006 | 模块级未完成／成功／失败／真实空态／访客呈现；8 秒截止且可取消、去重的首页批次。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-013 | 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::旧背景引用@32、1252、1491 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/css/voice-entry.css` | existing | REPO_BASELINE | SRC-07／frontend/static/css/voice-entry.css::旧背景 URL@2、21 | 语音使用 Index/Index.png；保留旧图 |
| `nginx/nginx.conf` | existing | REPO_BASELINE | SRC-08／nginx/nginx.conf::server／location@27—81 | 仓库配置监听 80，根路径跳 /pages/index.html；不是外层 HTTPS 证据 |
| `frontend/static/images/Index/Index.png` | existing | REPO_BASELINE | ASSET-08／frontend/static/images/Index/Index.png::精确目录名 Index.png；550814 字节 | 语音和首页回退使用的原背景 |
| `frontend/static/images/home-scene/v4/` | planned | PLANNED | 不适用 | PRD §9.1；新场景版本化导出资源 |
| 实际部署 URL、外层 HTTPS 和缓存响应头 | unverified | UNVERIFIED | 不适用 | ENV-02；见 §5 发现门，核实后登记环境定位和证据 |

**输入**：
- 已接入场景、派生资源和有截止加载；Q203 的真实环境发现结果。

**输出**：
- 版本化资源／缓存与大小写兼容配置，回退方案及对应环境响应证据。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 更新 | 版本化 URL；不能以不可变缓存覆盖同 URL 内容，HTML 不长期不可变。 | F211、§9.2 |
| 旧背景 | 旧图保留供语音和首页回退，不把旧大图预热加回首页关键链。 | §9.2 |
| 事实门 | 磁盘实际文件名为 Index.png，主页现为 index.png；以精确名字及实际服务响应核对，不以 macOS exists() 作部署证据。 | REPO_BASELINE SRC-04／SRC-07、本轮目录枚举 |

**开发任务**：
1. 先发现并记录实际验证环境、部署方式与外层配置；Nginx 80 端口不能推断外层无 HTTPS，真实 URL／响应未知时不把本 STEP 当可执行部署计划。
2. 核对所有旧背景引用与实际大小写，确保正式部署和语音旧图可访问；只改相关兼容引用。
3. 核对版本资源、缓存响应、HTML 策略与版本升级获取行为；配置变更按实际服务方式确定，不臆造 CDN 或缓存命中数据。
4. 准备主页切回旧背景的可审查配置／行为，具体开关字段按已核实的项目约定确定；验证回退保留加载／请求修复和业务入口。
5. 本文件不授权生产发布；先准备测试环境配置与证据，真实发布在有相应授权的执行阶段完成。

**不在本 STEP 范围内**：
- 删除旧图或原小图源；全局修改其他静态资源缓存；没有证据时宣称 HTTPS／微信倾斜支持。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 在已列明环境读取新场景和语音旧图实际响应 | 精确大小写返回正确图片，记录状态／缓存头／安全环境；原语音入口仍可用。 | AC215 |
| 异常 | 场景故障或切换回退开关 | 回到旧背景，入口可用；加载截止与数据保护仍保留。 | AC215 |
| 边界 | 更新资源版本，复用旧缓存后刷新，再复核 HTML 响应 | 新版本可获取，旧版缓存不污染；HTML 不长期不可变，不以本地文件存在代替响应证据。 | AC215、AC213 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-014、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-015] 实测持续运行性能

**阶段状态**：`provisional`；实施状态 `NOT_STARTED`。

**目标**：在列明的真机条件下得到新旧主页持续运行对比，核对普通与低档目标及降级策略。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F209 | 原文：单一主调度，按时间差运动；环境特效优先 30fps；DPR 默认至多 1.5，另设像素上限；按 §6 降级，同一页面实例不自动升档；本 STEP：真实设备帧率、交互响应、长任务和内存趋势及低档目标 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：四类首版浏览器的运行性能验收范围 | PRD／SRC-01 |
| 验收 ID | AC210 | 原预期：记录帧率、长任务、点击响应和内存趋势；掉帧按顺序降级，同一页面不自动升档；刷新或全新打开重新评估；达到经 Q201 确定环境下的目标；本 STEP：帧率、长任务、点击、内存和 Q201 目标的真实测量；策略由 STEP-013 联合负责 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-009 | 可点击、可键盘激活、重复合并且不穿透业务 UI 的人物本地反馈。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-012 | 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-013 | 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-014 | 版本化资源／缓存与大小写兼容配置，回退方案及对应环境响应证据。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::改造前主页源码基线 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |
| `主页行为测试及本地验收记录` | planned | PLANNED | 不适用 | 具体文件名、测试入口及保存位置按已核实的项目约定确定；不沿用语音测试的默认输出目录 |
| 实际机型、系统／浏览器／微信版本与统计口径 | unverified | UNVERIFIED | 不适用 | ENV-01；见 §5 发现门，核实后登记环境定位和证据 |

**输入**：
- 前置 STEP 的正式主页动效、交互和暂停恢复；同设备同网络改造前基线；Q201 测量记录。

**输出**：
- 可追溯的新旧持续运行／低档性能记录；目标实际达成范围与未测／未达成清单。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 目标 | 普通手机目标接近 60fps，低档至少 30fps；具体机型与统计窗口按 Q201 量测列明，不补造统计门槛。 | G205、Q201 |
| 恢复 | 持续掉帧按序降级，同页不自动升档，刷新／新实例才重评，不覆盖动态关闭或系统偏好。 | F209、RQ-06 |
| 口径 | 记录帧率、长任务、点击响应和内存趋势；像素内存估算不当成浏览器实测峰值。 | AC210、§7.2 |

**开发任务**：
1. 执行前锁定真实设备、系统／浏览器／微信版本、网络和统计窗口，保存同条件改造前／后基线；缺基线不得声称相对收益。
2. 量测普通、低档、持续掉帧、动态关闭以及暂停恢复后的运行成本，核对主调度、Canvas 预算和已确认目标。
3. 记录同页保持降级及新实例重评，分开受控掉帧与真实自然运行；目标未达标追踪原因，不倒改目标或弱化断言。
4. 输出范围、测量方法与缺口；本地模拟、受控浏览器和真机证据分开，不新增埋点平台。

**不在本 STEP 范围内**：
- 素材字节、加载时序与缓存传输由 STEP-016 负责；不记录 token／传感器原始数据，不把 demo 帧率推定为正式主页。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 列明四类浏览器的真实环境，同设备同网络对照持续运行 | 输出帧率／长任务／点击／内存证据，核对普通近 60fps、低档至少 30fps 的目标达成范围。 | AC210 |
| 异常 | 持续掉帧、低档和运行环境不足 | 按记录口径验证降级，目标未达或测试缺席明确待验，不作为全部通过。 | AC210 |
| 边界 | 长时间运行、后台／面板／bfcache 恢复及刷新／新实例 | 记录无资源累积趋势和恢复状态，保持同页质量，新实例重评不覆盖偏好；估算不当实测峰值。 | AC210 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-015、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-016] 实测加载与素材传输

**阶段状态**：`provisional`；实施状态 `NOT_STARTED`。

**目标**：在同设备同网络条件下得到新旧主页冷加载、缓存访问和刷新对比，核对素材质量与传输收益。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F203 | 原文：按 §5.1 显示或跳过加载页，核心图片、API 和可选特效按不同职责加载；异常有截止；本 STEP：真实环境下的时序与截止达成 | PRD／SRC-01 |
| 需求 ID | F210 | 原文：按 §7 预算优化，保持透明通道、画布比例与锚点；小图使用首页派生资源，原资源保留；本 STEP：最终集成素材质量、体积与下载链路 | PRD／SRC-01 |
| 需求 ID | F211 | 原文：使用版本化资源；检查真实缓存头与 HTTPS；旧图保留且路径大小写正确；首页可切回旧背景；本 STEP：版本和缓存行为的传输实测部分 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：四类首版浏览器的加载验收范围 | PRD／SRC-01 |
| 验收 ID | AC212 | 原预期：输出字节清单；确认预算达成情况、透明边缘、脸部清晰度和眨眼/发丝对齐；无重复大图下载；本 STEP：最终实际尺寸／高像素密度质量、体积与无重复下载 | PRD／SRC-01 |
| 验收 ID | AC213 | 原预期：记录遮罩退出、入口可操作时间与传输量；可选特效不延长门闩，不把固定展示时间算成压缩收益；本 STEP：完整新旧加载时序、缓存和传输测量 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 新场景导出资源；逐图原始／导出字节、像素尺寸、透明能力及视觉对照记录。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-002 | 同内容的首页派生图；初始、情绪更新、错误回退与预载引用一致的首页接入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-006 | 模块级未完成／成功／失败／真实空态／访客呈现；8 秒截止且可取消、去重的首页批次。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-009 | 可点击、可键盘激活、重复合并且不穿透业务 UI 的人物本地反馈。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-012 | 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-013 | 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-014 | 版本化资源／缓存与大小写兼容配置，回退方案及对应环境响应证据。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::改造前加载／数据源码基线 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |
| `frontend/static/images/home-scene/v4/` | planned | PLANNED | 不适用 | PRD §9.1；新场景版本化导出资源 |
| `首页头像和日记派生资源` | planned | PLANNED | 不适用 | PRD §7；具体文件名与路径按已核实的项目约定确定 |
| `主页行为测试及本地验收记录` | planned | PLANNED | 不适用 | 具体文件名、测试入口及保存位置按已核实的项目约定确定；不沿用语音测试的默认输出目录 |
| 实际机型、系统／浏览器／微信版本与网络配置 | unverified | UNVERIFIED | 不适用 | ENV-01；见 §5 发现门，核实后登记环境定位和证据 |

**输入**：
- 前置 STEP 的完整主页集成和实际缓存证据；同设备同网络改造前加载基线；最终导出图清单。

**输出**：
- 冷加载／缓存／刷新下的遮罩退出、入口可操作时间、传输字节及实际显示质量记录。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 加载 | 正常保留约 4.05 秒展示节奏；核心等待最多 5 秒，前台遮罩 8 秒兜底；API 与可选层不延长门闩。 | §5.1、AC213 |
| 素材 | 核心两图争取 ≤350 KiB、七图争取 800～900 KiB；七图预算和整页字节分开，质量优先。 | F210、§7.1 |
| 收益 | 压缩不改变已保留的最短展示，不等比例降低内存；传输测算不是 CDN 账单或模型费用。 | §7.2 |

**开发任务**：
1. 锁定真实设备、版本和网络，同条件比较改造前／后冷加载、缓存访问与刷新，记录响应和缓存状态。
2. 量测遮罩退出和入口可操作时刻、请求字节；包含弱网／坏图／挂起、静态偏好和可选层晚到，不把业务数据未完成伪装成加载成功。
3. 在实际展示尺寸及高像素密度设备复核脸部、透明边缘、眨眼／发丝位置与各 fallback 下载，检查无重复大图传输。
4. 报告目标达成、绝对时刻、传输差额和有限假设；未测环境或质量未检查保留待验，不依据文件大小推定真实加载提速。

**不在本 STEP 范围内**：
- 持续运行帧率由 STEP-015 负责；不改变正常展示节奏，不把十万次完整冷加载估算当真实账单。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 四类首版浏览器中，同设备同网络的冷／缓存／刷新 | 输出遮罩退出、可操作时刻和传输；素材清单与质量可复核，可选层不延长门闩。 | AC212、AC213 |
| 异常 | 坏图、挂起、弱网、可选资源失败／晚到 | 等待有界、入口可操作、静态保底；未达目标或缺少环境证据明确列出。 | AC213 |
| 边界 | 静态／减少动态、缓存版本更新、实际尺寸及高像素密度 | 不抢先下载不用的可选层，无不必要重复大图；透明边缘与贴片合格，固定展示不算压缩收益。 | AC212、AC213 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-016、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-017] 回归保留的主页能力

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：在同一最终集成快照上证明新场景的布局、贴片、点击与键盘以及当前主页入口、权限和数据语义满足首版验收。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F212 | 原文：保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约；本 STEP：§4 全部入口、数据与权限的用户可观察回归 | PRD／SRC-01 |
| 需求 ID | F202 | 原文：所有贴片共用坐标变换；实际 UI 与视口变化时脸部和入口可见；本 STEP：最终动效、倾斜、数据占位／结果／失败高度变化下的布局和贴片集成验收；静态适配仍由 STEP-003 负责 | PRD／SRC-01 |
| 需求 ID | RQ-01 | 原文：保留布局与入口，接入 demo 场景；本 STEP：当前主页布局与入口保留的回归部分 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：首版设备与浏览器的保留能力验收 | PRD／SRC-01 |
| 验收 ID | AC214 | 原预期：设置、关系、记忆、Feed、日记、聊天和真实语音入口符合当前规则；声音链路不被场景占用影响；本 STEP：完整主页保留能力与真实语音入口／声音链路 | PRD／SRC-01 |
| 验收 ID | AC206 | 原预期：访客／登录点击人物、更多、卡片、CTA 并使用键盘；本 STEP：更多、业务卡片和 CTA 的点击／键盘、UI 优先、门禁、不重放及不自动授权；人物反馈仍归 STEP-009、更多功能门禁仍归 STEP-010 | PRD／SRC-01 |
| 验收 ID | AC211 | 原预期：指定四视口及横竖屏，人脸／入口可见、贴片一致、底部可操作、安全区和正常手势可用；本 STEP：最终场景集成条件下直接验收；可复用仍成立的 STEP-003 静态证据 | PRD／SRC-01 |


**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-002 | 同内容的首页派生图；初始、情绪更新、错误回退与预载引用一致的首页接入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-006 | 模块级未完成／成功／失败／真实空态／访客呈现；8 秒截止且可取消、去重的首页批次。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-009 | 可点击、可键盘激活、重复合并且不穿透业务 UI 的人物本地反馈。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-012 | 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-013 | 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-014 | 版本化资源／缓存与大小写兼容配置，回退方案及对应环境响应证据。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `docs/contract/current/h5-app/api.md` | existing | CONTRACT | SRC-02／docs/contract/current/h5-app/api.md::§开放页访客态／受保护页统一回退 | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::goHomeRelationship@1974；goHomeDiary@1982；handleHomeQuickAction@1990；goFeed@2258；时钟@1791—1835；渲染@1838—1955 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::resolveStatusText@69；formatTime@594；goToRelationship@712 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `frontend/static/js/voice-entry.js` | existing | REPO_BASELINE | SRC-06／frontend/static/js/voice-entry.js::begin@401；微信 browser_unsupported@409 | 面板实际可见状态；微信语音保持不支持的当前策略 |
| `tests/test_h5_static_contract.py` | existing | REPO_BASELINE | SRC-09／tests/test_h5_static_contract.py::现有首页／访客／共享登录／受保护页面测试 | 已有 pytest 静态入口；子串断言不等于浏览器集成验收 |

**输入**：
- 前置功能 STEP 的同一最终集成源码／资源快照与可复核标识；当前契约和 §4 规则；已列明四类浏览器环境、可用测试账号／语音条件；STEP-003 静态布局证据及其仍成立的前提。

**输出**：
- 最终集成的视口／贴片／业务点击和键盘证据、当前入口及保留语义的用户流程证据，以及明确未验证的环境／链路清单。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 入口 | 头像→设置；关系／日记走门禁；记忆→memory；Feed 保留未读定位；CTA→chat；视频／入睡仍为原占位。 | §4.1 |
| 数据 | 四级关系、进度／满级、known_days、状态语、日记固定句／相对时间／NEW／真实 Lv0 锁保持。 | §4.1 |
| 时段 | 北京时间七时段与 Good night 条件不变；原 Hero 装饰语义保持。 | §4.1 |
| 集成布局／输入 | 验收同一快照的正式主页；动效和实际可用倾斜运行时、身份和卡片高度变化后，贴片仍对齐，脸部／入口／安全区和正常手势可用。更多、卡片和 CTA 的键盘激活沿用当前路径／门禁，不让场景抢事件。 | F202、§5.3、AC206、AC211 |
| 语音 | VoiceEntry.begin 与原兼容策略保持；微信仍按当前策略提示不可用，不新增语音支持承诺。 | §4.1、§8、REPO_BASELINE SRC-06 |

**开发任务**：
1. 访客／登录各执行设置、关系、更多、记忆、Feed、日记、CTA 与语音入口；核对公共 Feed、私有门禁及单次登录恢复、不重放。
2. 按 §4 检查关系数值、陪伴天数、头像／状态语、日记 NEW／锁与相对时间、Feed 更新时间和未读定位；未知／失败不假装真实 Lv0 或空态。
3. 检查七时段、24 小时时钟、Good night 和 CTA 文案；不通过代码重排卡片规避新场景遮脸问题。
4. 在原支持且实际可用的语音测试环境确认场景暂停与声音链路；微信核对原不可用提示。受控传输和真实声音分开记录。
5. 完成有影响的静态及真实用户流程回归；未有真机／语音条件时记录缺口，不以静态字符串通过推定完整 AC214。
6. 在同一最终快照下检查 375×667、390×844、430×932、1280×720、横竖屏及卡片占位→结果／失败的高度变化；记录静态、动效允许运行和实际可用倾斜状态的人脸／入口／底部操作、安全区、缩放／正常手势及所有贴片。四浏览器范围不变，不把不支持倾斜标成已运行；复用前提仍成立的静态证据，补测新增动效／倾斜／数据高度造成的影响。
7. 访客／登录分别通过点击及 Tab 聚焦、Enter／Space 激活更多、Feed／日记卡和 CTA，观察控件自身路径／反馈、场景未抢输入、访客门禁和登录只恢复一次。登录后不重放或申请传感器权限；人物本地回应仍按 STEP-009 的直接证据汇总。记录网络／导航和键盘操作，不新增业务行为或重排卡片。

**不在本 STEP 范围内**：
- 关系算法、视频／入睡、子页权限、微信语音新支持；不重结算历史技术债。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 四浏览器中分别访客／登录逐一操作 §4 入口和数据场景 | 当前路径、数据、门禁及文案保持；登录恢复一次，不重放原操作。 | AC214 |
| 异常 | 有效 401、数据失败／未知、语音不支持或无法接通 | 按当前策略降级／提示；不会误锁为真实 Lv0，不改变语音兼容承诺。 | AC214 |
| 边界 | 满级、真实 Lv0、NEW、七时段边界、Feed 未读定位、真实可用语音 | 各既有语义及声音链路可观察正确；缺少声音或设备证据不能报整体通过。 | AC214 |
| 正常（最终布局） | 同一最终快照，四个指定视口、横竖屏；动效运行及实际可用倾斜；访客／登录卡片占位、结果与失败高度 | 人脸／入口可见，所有贴片一致，桌面构图、底部操作、安全区、缩放与正常手势满足原标准；静态证据不能代替新增动态条件。 | AC211 |
| 边界（业务键盘） | 访客／登录逐一点击及 Tab/Enter/Space 操作更多、Feed／日记卡、CTA，且控件与人物区域重叠；登录成功或取消 | 控件按 §4 原路径／门禁反馈；场景不抢事件，登录只恢复数据一次，不重放操作／申请传感器权限；可用键盘和正常手势保持。 | AC206 |


**完成标志**：

- [ ] AC214 原保留能力、AC206 业务点击／键盘子条款和 AC211 最终集成布局均有同一快照的直接证据；共享 AC 原责任保持，未测的动态／倾斜／设备条件不算完成。
- [ ] 已记录视口／方向、浏览器环境、身份／卡片状态、实际动态／倾斜条件及原静态证据复用依据；未测／模拟／真实范围分开，个别设备结果不推定全部环境。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-017、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

### [STEP-018] 同步真实契约并收口追踪记录

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：当前 H5 契约、实际源码、测试和 STEP 验收证据一致，所有未测项保留真实状态。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F212 | 原文：保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约；本 STEP：实施完成后同步当前 H5 契约、静态回归及整体验收证据 | PRD／SRC-01 |
| 验收 ID | AC216 | 原预期：同步本次真实行为；不把只测 demo、静态壳或模拟时钟的结果作为整体通过；本 STEP：源码、相关回归与当前契约对账，不用局部模拟代替整体通过 | PRD／SRC-01 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
|---|---|---|
| STEP-001 | 新场景导出资源；逐图原始／导出字节、像素尺寸、透明能力及视觉对照记录。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-002 | 同内容的首页派生图；初始、情绪更新、错误回退与预载引用一致的首页接入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-003 | 背景／人物静态层和统一贴片坐标；正式主页场景尺寸适配。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-004 | 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-005 | 首页显式使用、默认兼容的取消和失效上下文保护能力。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-006 | 模块级未完成／成功／失败／真实空态／访客呈现；8 秒截止且可取消、去重的首页批次。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-007 | 单实例场景生命周期、原因集合、受控主调度与资源清理基础。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-008 | 正式主页全部可选动效层及其受控启动、暂停、恢复和失败降级。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-009 | 可点击、可键盘激活、重复合并且不穿透业务 UI 的人物本地反馈。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-010 | 更多互动的动态控制 UI、真实开关状态、当前浏览器偏好读写及系统覆盖。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-011 | 与实际运行一致的倾斜开关、权限／有效数据反馈及可清理的方向输入。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-012 | 主页范围内的登录／语音可见状态适配，以及组合暂停的场景行为。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-013 | 带实际选参证据的场景成本优化和同页面单向降级／新实例重评策略。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-014 | 版本化资源／缓存与大小写兼容配置，回退方案及对应环境响应证据。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-015 | 可追溯的新旧持续运行／低档性能记录；目标实际达成范围与未测／未达成清单。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-016 | 冷加载／缓存／刷新下的遮罩退出、入口可操作时间、传输字节及实际显示质量记录。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |
| STEP-017 | 当前业务入口和保留语义的用户流程证据，以及明确未验证的环境／链路清单。 | 核对该 STEP 完成回传、产物及对应子条款证据；阶段草稿状态不算前置完成 |

依赖未满足时停止当前 STEP；编号不替代依赖。Q201／Q202／Q203 及测试环境发现门按本 STEP 验收需要落实；关键未核实项不能冒充执行事实。

**参考路径与符号**：

| 路径或符号 | 状态 | 来源证据 | source_id／locator | 用途 |
|---|---|---|---|---|
| `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | existing | PRD | SRC-01／docs/design/home-redesign/PRD-林小梦主页改版-v2.md::本 STEP 所列需求／验收 | 已确认需求、验收、排除项及待核验项 |
| `docs/contract/current/h5-app/api.md` | existing | CONTRACT | SRC-02／docs/contract/current/h5-app/api.md::§HTTP 401 处理策略及主页访客规则 | 公共首页、访客门禁、登录恢复与四种有效 401 策略 |
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::主页实际增量实现 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::共享请求实际增量实现 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `tests/test_h5_static_contract.py` | existing | REPO_BASELINE | SRC-09／tests/test_h5_static_contract.py::首页及公共兼容静态用例 | 已有 pytest 静态入口；子串断言不等于浏览器集成验收 |
| `docs/INDEX.md` | existing | REPO_BASELINE | SRC-16／docs/INDEX.md::当前文档入口 | 当前 v2 入口及读取边界 |
| `主页行为测试及本地验收记录` | planned | PLANNED | 不适用 | 具体文件名、测试入口及保存位置按已核实的项目约定确定；不沿用语音测试的默认输出目录 |

**输入**：
- STEP-001—STEP-017 的真实完成／阻断状态、变更文件、环境和验收证据；实现后实际源码。

**输出**：
- 同步实际主页行为的当前 H5 契约和同一 STEP 文档内的完整回传／剩余工作记录。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 契约 | 仅实施后写真实加载、交互、暂停与失效请求保护；将“仅有效上下文 401 执行原策略”前置条件写清。 | F212、§9.2 |
| 证据 | 分开需求已确认、草稿审查和功能实施／验收；共享 AC 全部子条款有证据后才能完成。 | §8、AC216 |
| 历史 | 不改写历史 K／TD 结论、不新增债编号，不扫描或修改迁移快照。 | §3.2、§9.2；项目 AGENTS.md |

**开发任务**：
1. 按实际最终实现同步当前 H5 契约，不把拟新增字段／API 当成已实现；保留未受影响的现契约条款。
2. 核对各 STEP 已随实施更新的相关测试与最后源码，复用仍适用结果；存在代码／环境变化时只补具体受影响验证。
3. 对照本文件映射确认全部 F、RQ、约束与 AC 子条款都有归属和证据；未有真实设备／部署／声音证据的项目保留待验。
4. 更新本文件内进度、证据和恢复位置，必要时同步当前文档入口；不新建重复进度文档，不自动开始发布。

**不在本 STEP 范围内**：
- 本拆解阶段提前改写运行契约；历史技术债审计、迁移快照操作及生产发布。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 所有前置完成标志有证据，最终源码与记录一致 | 当前 H5 契约准确反映本次真实行为；回归和需求／验收映射一致。 | AC216 |
| 异常 | 有未测环境、模拟冒充真机、契约与源码不一致 | 不能标记整体完成，指出受影响 AC、缺证据和恢复 STEP；不倒改需求。 | AC216 |
| 边界 | 前置证据仍有效但文件／环境局部变化，多个 STEP 共享 AC | 仅复查受影响范围；共享 AC 每个子条款均有证据后才完成，历史记录不被重结算。 | AC216 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-018、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，本文件已通过文档复审，功能完成仍须上述验收证据。

## 7. 非阻断风险与处理

| 风险 | 证据／影响 | 处理和验证位置 |
|---|---|---|
| Q201 真机与统计口径 | PRD 已确认目标，实际设备／版本、Canvas 像素预算与降级窗口未指定 | STEP-013 量测选参，STEP-015 记录目标达成；环境未核实的 STEP-015／016 保持 provisional |
| Q202 素材优化结果 | 元数据已核实，尚无导出图／最终字节／边缘质量结果 | STEP-001／002 产生文件与质量清单，STEP-016 实机复核；保留预算是争取目标的含义 |
| Q203 实际部署事实 | 没有真实部署 URL、外层 HTTPS 与缓存响应证据 | STEP-014 先发现环境并保持 provisional；不把本地配置声明当实际支持 |
| 背景大小写兼容 | 本轮精确枚举 Index.png，与主页 index.png 引用不同；本机文件系统可能隐藏问题 | STEP-014 对全部相关引用和实际服务响应核对；新增场景与语音旧背景都保留回退能力 |
| 共享请求兼容影响 | api.js 被多个页面使用，现 401 无条件先清 token；当前契约需增加有效上下文前置条件 | STEP-005 默认兼容／行为验证，STEP-006 UI 保护，STEP-018 同步真实契约 |
| 行为测试和真机资源 | 已有 pytest 静态文件和受控浏览器示例，新增主页测试运行入口／环境未执行发现 | 各 STEP 先核实运行能力，真机／真实声音证据按对应 AC 收集，不把受控模拟当整体完成 |

上述为本阶段非阻断风险，故不能返回无风险的 PASS。它们不改变已确认产品范围；若实施中发现会改变业务结果的新冲突，再只返回受影响的最小决定。当前没有未决／延期产品决策，无需重复 RQ-01—RQ-06。

## 8. 文档修复、完整复审与权威状态

- [x] SDR-V2-R1-001：STEP-017 已补最终集成快照、视口／旋转／卡片高度、动态／可用倾斜及业务点击／键盘用例；必要映射同步，原责任与依赖保留。
- [x] SDR-V2-R1-002：STEP-004 已分开真实脚本执行前 token 读取、Session 标记和启动途中写入故障；STEP-010 保留偏好故障责任并限定证据用途。
- [x] 修复轮由 execute-approved-work 单一写入；原稿、PRD、代码与素材保持原样，执行器只交付 STEP_REVIEW_READY。
- [x] step-doc-review 已从原始权威来源重新检查完整 18 个 STEP；九维均 PASS，71 个有效 ID 的覆盖与正反向映射一致，74 条依赖边无环且保持原样。
- [x] 生成前全部 29 个来源摘要复核一致；候选 SHA-256 为 `c73cc056bbf824536979a386b7439fd88384838042baba938cf9c02dcc6e9378`，当前来源摘要为 `32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c`。
- [x] Q201—Q203 与运行入口的非阻断风险保留；功能仍 0/18，未执行真机、真实声音或部署验收。

阶段结果 **PASS_WITH_RISKS**，权威状态 **STEPS_VERIFIED**。本阶段完成文档修复与完整复审，后续实施只按用户指定范围、依赖与事实门进行。详情和首次发现保留在唯一 [step-audit.md](step-audit.md)。

## 9. 林小梦主页改版 v2 STEP 进度

> 路径：本文件内嵌进度区块。
> PRD 来源：`PRD-林小梦主页改版-v2.md`（existing／PRD／SRC-01）。
> STEP 来源：`steps-verified.md`（当前验证版；候选快照为 steps-candidate-r1.md，只读原稿为 steps-draft.md）。
> 当前文档状态：`STEPS_VERIFIED`；完整复审结果 `PASS_WITH_RISKS`；原 STEP 验收完成数仍为 10/18。主要本地实现、M5 文档同步及 Docker 交付已完成；设置页偏好和人物稳定性后续变更已补充证据。本轮按开发交付收口，发布候选已生成但尚未上传；用户最新决定暂不需要代推线上，发布另行安排。Q201 正式配置及真实环境完整验收仍待补，不将开发交付收口写成原计划全部 DONE。当前状态以 §9.20 为准，之前执行回传保留历史边界。

### 9.1 进度总览

| 完成数 | 总数 | 当前状态 |
|---|---|---|
| 10 | 18 | M4 缓存／回退和本地回归已落地；M3—M4 真机／HTTPS／声音／Q201 选参待补 |

### 9.2 STEP 明细

| STEP | 功能名称 | 需求 ID | 验收 ID | 前置 STEP | 状态 | 证据 |
|---|---|---|---|---|---|---|
| STEP-001 | 导出场景七图素材 | F210 | AC212 | 无 | DONE | 见 §9.6、§9.7；本地验证及用户手机／微信资源质量确认 |
| STEP-002 | 接入首页专用小图 | F210 | AC212、AC213 | 无 | DONE | 见 §9.8；7 情绪、错误回退、其他页兼容与 6 次请求清单通过 |
| STEP-003 | 建立适配主页的静态场景 | F201、F202、RQ-01 | AC201、AC203、AC209、AC211 | STEP-001 | DONE | 见 §9.9；四尺寸／坐标／旋转／安全区模拟及 5 类故障通过 |
| STEP-004 | 实现有截止的加载遮罩 | F203、F201、RQ-02 | AC202、AC203、AC213 | STEP-003 | DONE | VERIFIED；home-m2/step-004-results.json、19 项静态回归 |
| STEP-005 | 给共享请求增加可选取消和失效保护 | F204、F212、RQ-02 | AC205 | 无 | DONE | VERIFIED；home-m2/step-005-results.json，8 项共享 request 行为 |
| STEP-006 | 实现主页独立显示和有界数据批次 | F204、F203、RQ-02 | AC204、AC205、AC202 | STEP-004、STEP-005 | DONE | VERIFIED；home-m2/step-006-results.json，8 组首页行为；19 项静态回归 |
| STEP-007 | 建立场景统一生命周期 | F208、F209 | AC208、AC209、AC202 | STEP-004 | DONE | VERIFIED；home-m3/step-007-results.json、native-bfcache-results.json、scene-boundaries-results.json；单实例／原因集合／真实 bfcache／销毁 |
| STEP-008 | 接入渐进场景动效 | F201、F208、RQ-01 | AC201、AC208、AC209 | STEP-001、STEP-003、STEP-007 | DONE | VERIFIED；home-m3/step-008-results.json、step-008-motion.png，6 组实际主页验证 |
| STEP-009 | 实现人物本地回应 | F205、RQ-01、RQ-03 | AC201、AC206 | STEP-003、STEP-007、STEP-008 | DONE | VERIFIED；home-m3/step-009-results.json，访客／登录点击和键盘行为 |
| STEP-010 | 在更多互动保存主页动态偏好 | F206、RQ-03、RQ-04 | AC206、AC217、AC208 | STEP-007、STEP-008 | DONE | VERIFIED；home-m3/step-010-results.json，5 组偏好行为 |
| STEP-011 | 实现主动授权的倾斜视差 | F207、F206、F208、RQ-03、RQ-05 | AC207、AC217、AC208 | STEP-003、STEP-007、STEP-008、STEP-010 | IN_PROGRESS | 实现＋受控 VERIFIED；home-m3/step-011-controlled-results.json；四类真机权限待验 |
| STEP-012 | 适配登录和语音面板暂停 | F208、F212 | AC208、AC214 | STEP-007、STEP-008、STEP-011 | IN_PROGRESS | 本地面板 VERIFIED；home-m3/step-012-controlled-results.json；真实声音待验 |
| STEP-013 | 优化调度并保持自动降级档位 | F209、F208、RQ-06 | AC210、AC208 | STEP-003、STEP-007、STEP-008、STEP-010、STEP-011、STEP-012 | IN_PROGRESS | 局部实现＋受控 VERIFIED；home-m3/step-013-controlled-results.json、native-bfcache-results.json；Q201 真机选参及正式配置待补 |
| STEP-014 | 验证版本化缓存与旧场景回退 | F211、RQ-05 | AC215、AC213 | STEP-002、STEP-004、STEP-006、STEP-008、STEP-013 | IN_PROGRESS | 本地 IMPLEMENTED／VERIFIED；home-m4/step-014-cache-results.json、step-014-fallback-results.json、local-nginx-runtime.json；真实 HTTPS／四类设备及 M3 选参待验 |
| STEP-015 | 实测持续运行性能 | F209、RQ-05 | AC210 | STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | IN_PROGRESS | 桌面补充采样及工具已就绪；home-m4/step-015-016-desktop-measurements.json；真机新旧对照、低档及 Q201 待验，未结算依赖 |
| STEP-016 | 实测加载与素材传输 | F203、F210、F211、RQ-05 | AC212、AC213 | STEP-001、STEP-002、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | IN_PROGRESS | 实际 Nginx＋Chrome 六次冷／缓存／刷新量测通过；home-m4/step-015-016-desktop-measurements.json；四类真机同条件新旧对照／弱网／最终质量待验 |
| STEP-017 | 回归保留的主页能力 | F212、F202、RQ-01、RQ-05 | AC214、AC206、AC211 | STEP-002、STEP-003、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | IN_PROGRESS | 同一生产快照 17 项浏览器复验＋53 项保留业务／输入场景通过；home-m4/step-017-preserved-results.json、regression/；真机实际倾斜／手势／键盘／声音待验 |
| STEP-018 | 同步真实契约并收口追踪记录 | F212 | AC216 | STEP-001、STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 | IN_PROGRESS | 本轮文档工作 VERIFIED，CONTRACT_VERIFICATION_READY；完整原前置／最终验收待补，见 §9.17 与 home-m5/contract-verification.json |

状态只使用 `NOT_STARTED`、`IN_PROGRESS`、`DONE`、`BLOCKED`；阶段状态 draft／provisional 与实施状态分开。只有本 STEP 全部完成标志有证据才能标 DONE，当前文档级风险不等于已开始执行或实施阻断。

### 9.3 阻断与来源变化

| 日期 | STEP | 类型 | 证据或变化 | 处理结果 |
|---|---|---|---|---|
| 2026-10-02 | STEP-014 | REPO_BASELINE 补充 | 实际文件名 Index.png 与主页 index.png 引用大小写不一致 | 已加入兼容核对；没有修改 PRD 或代码 |
| 2026-10-02 | STEP-014／STEP-015／STEP-016 | UNVERIFIED 环境 | 真实部署／真机口径仍需发现 | 阶段 provisional，实施仍 NOT_STARTED；不是产品未决项 |
| 2026-10-02 | STEP-001 | 历史真机验收缺口 | 用户后续明确手机／微信资源质量正常，见 §9.7 | 资源质量已验收，现为 DONE；详细设备版本仍不能用于推定后续权限／性能通过 |
| 2026-10-02 | STEP-011—013 | 当前真实环境缺口 | HTTPS 测试地址、四类机型／版本、真实声音、Q201 量测未提供 | 局部实现及受控验证完成，保留 IN_PROGRESS；生产自动降级正式参数未配置，见 §9.12 |
| 2026-10-02 | STEP-014—017 | USER_DECISION／RUNTIME | 用户授权继续 M4；本地 Linux Nginx／Chrome 缓存、回退、桌面采样和业务回归已执行，见 §9.14 | 旧大小写兼容已落地；前两行的 NOT_STARTED 为规划历史。014—017 当前 IN_PROGRESS，不替代真实 HTTPS／设备／声音／Q201 事实门 |

当前恢复位置：用户已明确“完成 M5，M6—8 是我记错了”，并接受当前缺少可信 HTTPS 时先继续开发、延期倾斜真机验收。M5 契约同步、文档一致性验证和记录收口已完成；011—017 的未测范围保留，具体恢复清单见 §9.17。M4 与完整功能闸门仍 NOT_REACHED，不能以继续开发授权代替验收结果。


### 9.4 已确认实施计划与里程碑

> **计划状态**：IMPLEMENTATION_PLAN_READY。  
> **规划结果**：PASS_WITH_RISKS；Q201—Q203、测试运行及真实声音等原风险保留。  
> **计划路径**：[林小梦主页改版 v2开发里程碑文档.md](execution/林小梦主页改版%20v2开发里程碑文档.md)。  
> **唯一共享进度**：本文件 §9，继续复用；不另建执行记录。  
> **当前执行**：STEP-001—010 已验证；10/18。M5 文档收口已完成并提交 CONTRACT_VERIFICATION_READY，见 §9.17；M3—M4 真机和 Q201 证据待补，整体完成条件未满足。没有对外发布授权。

USER_DECISION（2026-10-02）：确认 M1—M5 分组、每次一个 STEP 串行，以及 M1—M4 业务总验收通过后在 M5 内完成 STEP-018 的正式契约整合、验证和最终闸门。该顺序仅为本阶段已确认的局部例外，不修改源 STEP、验收口径或长期技能规则。milestone-step-execution 负责整合与判定，execute-approved-work 在整合后提交 CONTRACT_VERIFICATION_READY；只有最终判定 CONTRACT_MERGED_VERIFIED 才结算整个功能完成。

| 里程碑 | 名称 | STEP 与顺序 | 状态 | 闸门状态／证据 |
|---|---|---|---|---|
| M1 | 素材与静态主页 | STEP-001 → STEP-002 → STEP-003 | IN_PROGRESS | GATE_EVIDENCE_READY；见 §9.10；未作闸门判定 |
| M2 | 有界加载与数据 | STEP-004 → STEP-005 → STEP-006 | IN_PROGRESS | GATE_EVIDENCE_READY；004—006 DONE，最终源码验证通过；未冒称正式闸门 PASS |
| M3 | 完整动态交互 | STEP-007 → STEP-008 → STEP-009 → STEP-010 → STEP-011 → STEP-012 → STEP-013 | IN_PROGRESS | 007—010 DONE，011—013 局部实现／受控通过；真机及正式选参待补，闸门 NOT_REACHED |
| M4 | 真实环境总验收 | STEP-014 → STEP-015 → STEP-016 → STEP-017 | IN_PROGRESS | 014 本地配置／回退生效；015—017 桌面补充证据就绪，真实前置／事实门保留，闸门 NOT_REACHED；见 §9.14 |
| M5 | 契约与记录收口 | STEP-018 | IN_PROGRESS | 本轮文档收口及一致性验证完成，CONTRACT_VERIFICATION_READY；等待补齐延期证据及最终契约闸门判定，见 §9.17 |

规划阶段历史回传：当时只新增上述计划并更新 §9，业务源码尚未实施，29 个输入与复审来源一致，来源摘要为 32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c。该摘要不代表本轮实施后的源码；最新运行与来源快照见 §9.14。

### 9.5 本轮规划验证证据

2026-10-02，本轮落盘后执行定向文档结构核对，退出码 0：185 项检查通过、0 项失败；18 个 STEP 唯一归属，原 74 条依赖及执行顺序一致；59 条原验收场景、前提、预期与 AC 完整引用且逐项一致；5 个里程碑均有完整前置、排除项、验收、产物和闸门；计划与进度文档链接可解析。全部 29 个上游输入摘要及源正文 SHA256 保持不变，原 STEP §9.2 状态／证据未改。git diff --check 退出码 0。

以上只证明实施计划及来源／状态一致，不是功能测试结果；没有运行新主页、素材导出、真机、声音或部署验收。规划结论 PASS_WITH_RISKS，计划 IMPLEMENTATION_PLAN_READY，业务代码、全部里程碑与正式契约仍 NOT_STARTED。


### 9.6 STEP-001：七图导出与验收证据（2026-10-02）

> 执行来源：已确认实施计划 M1／STEP-001；本轮用户引用该计划并调用 execute-approved-work，按“每次一个 STEP”启动。  
> 工作项状态：BLOCKED（验收证据缺口）；素材产物 IMPLEMENTED，本地验证通过，真机结果待回传，尚未 VERIFIED／DONE。  
> 闸门交接：NOT_REACHED；本轮不结算 M1，不启动 STEP-002。正式契约 NOT_STARTED。  
> 当前用户配合：已回复“有设备，可配合验收”；四类环境的机型、版本、DPR 和观察结果仍未收到。

**来源复核与变更边界**

- 29 个定向来源 SHA256 全部与 step-audit.md §1 相同；来源摘要仍为 `32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c`。
- 本轮前验证版完整 SHA256 为 `cddf7fc944d14985f5dbf85136ffcf980b4b297eee8851dcb78e5a4ecc43c0ed`（含此前已确认规划进度）；§9 之前源正文摘要仍为 `4677826738a9439f60b343e26fce8a1ba0ee081b235e053cfae3f6ddd0c43bd4`。
- 产物：[七图清单](../../../frontend/static/images/home-scene/v4/manifest.json)；可复现导出入口 `scripts/export_home_scene_assets.py`。资源使用 `原名.内容SHA256前12位.webp`，目录 `frontend/static/images/home-scene/v4/`；相同 URL 已存在不同字节时拒绝覆盖。
- 保留七图原件、原画布、透明留白、比例及 demo CSS 贴片百分比／旋转锚点。未修改主页、公共 API、语音、Nginx、PRD、STEP §1—§8、里程碑文档或正式契约；未发布。
- 本 STEP 只产生素材，尚无接入正式首页的 H5 行为契约增量；不创建空契约草稿。后续集成以 manifest 中实际路径为输入。

**字节与几何清单**

| 素材角色 | 原始字节 | 导出字节 | 画布 | 处理 |
|---|---:|---:|---|---|
| background | 165,630 | 165,630 | 853×1844 | 原 WebP 字节保留 |
| character | 284,604 | 284,604 | 853×1844 | 原 WebP 字节保留 |
| hair_front | 358,769 | 122,426 | 456×417 | 无损 WebP，保留 alpha／可见 RGB |
| hair_side | 120,267 | 72,036 | 220×512 | 无损 WebP，保留 alpha／可见 RGB |
| hair_back | 146,555 | 90,110 | 168×445 | 无损 WebP，保留 alpha／可见 RGB |
| blink | 70,797 | 20,540 | 263×134 | 无损 WebP，保留 alpha／可见 RGB |
| lamp | 140,176 | 140,176 | 853×1844 | 原 WebP 字节保留 |

- 全套：1,286,798 → 895,522 字节（874.5 KiB），减少 391,276 字节／30.4%；达到全套 800～900 KiB 的争取目标。
- 核心两图：450,234 字节（439.7 KiB），未达 ≤350 KiB，超出 91,834 字节（89.7 KiB）；该目标仍保留。未将争取预算改为硬门槛或声称全部预算通过。
- 候选比较：三张头发和眨眼以 Pillow 12.3.0／libwebp 无损导出，`quality=100, method=6, exact=False`。只允许舍弃 alpha=0 下不可见 RGB；全部 alpha、alpha>0 的 RGB 和黑／白底合成逐像素复核一致。
- `exact=True` 的四张贴片共 485,498 字节，`exact=False` 共 305,112 字节；透明度和可见像素均不变。原 WebP 的无损重编码反而增大（背景 853,674，人物 846,476，灯光 415,040 字节），未选。
- 背景／人物也比较了 q95／90／85／80 的同尺寸有损候选；背景 84,856～190,322，人物 184,480～282,710 字节，出现可见 RGB 改变（人物最大通道差 51～60）。本轮选择保留原核心两图和灯光，优先避免人物与原贴片经过不同有损再编码；不把未选候选写入版本化目录。
- 以上是文件传输字节统计，不是浏览器峰值内存、加载时延或账单收益。

**要求—实现—证据**

| 原验收／完成标志 | 实现／验证 | 实际结果与范围 |
|---|---|---|
| F210／AC212：原件保留、比例／alpha／锚点 | 导出脚本；manifest 记录源／输出完整摘要、画布、alpha 摘要与百分比位置 | 7/7 Pillow 解码验证通过；源文件摘要未改变；未裁切／缩放，无坐标增量 |
| AC212 正常：字节可复算，预算和差额真实 | manifest 逐文件大小／完整 SHA256 复算 | 全套达标；核心未达争取目标，差额如上；预算未替代质量判断 |
| AC212 异常：损坏候选淘汰 | 对真实像素检查函数分别输入改画布、改 alpha、改可见 RGB 的候选 | 3/3 均抛 ValueError，被拒绝；不允许用预算接受坏图 |
| AC212 正常／边界：真实展示尺度与高 DPR | 桌面 Chrome 154.0.8037.97，375×667 DPR1、390×844 DPR3、430×932 DPR3、1280×720 DPR1 | 28/28 素材尺寸／解码／合成检查通过，8 张睁／闭眼截图；这是桌面控制视口和 DPR，不是四类真机 |
| AC212：透明边缘、脸部与贴片 | 保留核心原图；复核桌面截图中的脸部、发丝、睁闭眼 | 未见新增白边／错位；原图 alpha 和可见 RGB 一致，正式 UI 构图仍由 STEP-003／017 验证 |
| AC212：目标设备显示质量；所需环境与实际行为 | 局域网素材对照页，原图／导出及睁闭眼切换，七图检查 | iOS Safari、Android Chrome、iOS 微信、Android 微信结果待用户回传；未据桌面结果结算真机 |
| 全部原完成标志／共享 AC | 本节与 §9.2 回传；共享 AC 的小图／最终下载由 002／016 负责 | 当前产物已实施，真实设备质量证据未齐；不标 VERIFIED／DONE，不整体结算 AC212 |

**浏览器差异诊断（保留首次失败）**

首次用“PNG 与 WebP 的浏览器合成像素必须零差异”检查，四张透明贴片失败。随后实测：alpha 变化 0、不透明／全透明区域变化 0；差异仅在半透明区域，黑／白底的每通道最大差均为 1/255。对同一头发素材仅将 alpha 改为完全不透明作单变量对照，PNG／无损 WebP 合成差异归零。诊断支持不同格式半透明解码／合成的整数舍入原因，详见 [decoder-diagnostic.json](execution/evidence/step-001-assets/decoder-diagnostic.json)。

浏览器检查因此区分原始像素保真和合成舍入：Pillow 仍严格要求 alpha／可见 RGB／黑白合成零差异；浏览器仍严格要求尺寸、alpha、不透明和全透明区域一致，只对已量测的半透明合成报告 ≤1/255 的舍入边界，并保留所有变化像素数。没有删除脸部／发丝／贴片的人工质量验收要求。最终浏览器结果见 [browser-results.json](execution/evidence/step-001-assets/browser-results.json)。

**运行方式与证据范围**

```sh
/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/export_home_scene_assets.py --source '/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets'
/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 docs/design/home-redesign/execution/evidence/step-001-assets/serve_preview.py --host 0.0.0.0
HOME_PLAYWRIGHT_PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright /Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node docs/design/home-redesign/execution/evidence/step-001-assets/verify_browser.cjs
```

- 系统 Python 缺 Pillow／pytest，项目 `.venv-step001` 有 pytest、无 Pillow；本轮使用桌面捆绑 Python 3.12.14／Pillow 12.3.0。未安装依赖或改变全局配置。
- Playwright 默认浏览器二进制缺失；改用本机 Chrome 独立无头实例，未复用用户浏览器账号。素材不是应用行为改动，未机械运行无关后端或语音全量测试。
- 素材对照页：[preview.html](execution/evidence/step-001-assets/preview.html)，本轮临时同 Wi-Fi 地址 `http://192.168.1.3:54322/`；服务只允许对照页、manifest 和明确列出的原／导出图片，不暴露仓库目录。
- 本地 RUNTIME 证据仅覆盖素材浏览器解码与显示；对照页采用 demo 参考静态构图，未接生产主页、未运行人物动态、未核验线上 HTTPS／缓存／加载性能／声音。
- 用户已确认设备可配合，已发送四类浏览器验收操作；版本、DPR、检查结果及人工观察尚待回传，缺项不记通过。

**剩余项与恢复点**

1. 在四类目标浏览器回传机型／系统／浏览器或微信版本、页面 DPR、七图检查及脸部／发丝／睁闭眼观察，失败时只处理 STEP-001 素材边界。
2. 汇齐本 STEP 原完成标志后，才结算 VERIFIED（项目 §9.2 显示为 DONE）；共享 AC212 仍保留 002／016 的责任。
3. 本轮执行边界为 STEP-001；不自动进入 STEP-002。M1 闸门仍 NOT_REACHED，正式契约整合验证不适用，尚未提交 GATE_EVIDENCE_READY／CONTRACT_VERIFICATION_READY。


**历史阻塞（已由 §9.7 用户资源质量确认解除）**

| 工作项 | 问题证据 | 原执行边界／影响 | 已完成处理 | 继续所需信息 |
|---|---|---|---|---|
| STEP-001 | 四类目标手机浏览器尚无机型、系统／浏览器版本、DPR、检查与视觉回传 | F210／AC212 素材质量及本 STEP 完成标志；不影响现有主页运行，不允许标 DONE | 七图导出、像素／摘要验证、缺陷候选拒绝、桌面高 DPR 检查与截图、临时验收页均已准备 | 用户按已发送操作回传四类环境的真实结果；未测项须明确保留 |

本轮最终检查：导出重跑退出码 0，既有内容哈希文件及 manifest 保持相同；7 个源／输出摘要一致，源正文摘要不变，证据链接可解析，28 项浏览器检查和 8 张截图完整；Python 源文件语法、浏览器验证脚本语法和新增源文件尾随空白检查通过，git diff --check 退出码 0。没有正式主页 RUNTIME 或真机通过结论。临时手机验收服务本轮保持运行，用户回传前不重跑无变化的本地证据。


**续验检查（2026-10-02，用户“继续任务”）**

- 重新核对 7 个原图和导出文件的 SHA256，以及 §9 前源正文摘要，均未变化；上轮 28 项桌面素材检查继续有效，本轮未重复运行。
- 临时对照服务实测 HTTP 200／Cache-Control: no-store；本机局域网地址仍为 `192.168.1.3`，手机入口仍为 `http://192.168.1.3:54322/`。
- 当前没有新增手机验收文件或用户真机结果回传，已请求回传已测环境和未测项。STEP-001 保持 BLOCKED（验收证据缺口），不把“继续任务”视为真实验收通过或验收范围变更。
- 本轮仅复核并更新同一进度记录，素材、应用源码、源 STEP、实施计划和正式契约未改变。恢复位置仍为 STEP-001 的四类真机显示质量证据收集。


### 9.7 用户验收回传与继续授权（2026-10-02）

- USER_DECISION／实际人工观察：用户回复“我在手机和微信上已确认资源正常请完成后续里程碑”。作为 STEP-001 素材展示质量的用户验收结果接收，结算该 STEP VERIFIED（§9.2 显示 DONE）；§9.6 及此前 BLOCKED 是历史过程，不再是当前阻塞。
- 用户未逐项提供 iOS／Android、Safari／Chrome／微信版本、DPR 和截图；这些详细环境仍 UNVERIFIED。本轮不编造四类环境覆盖，不把资源质量确认当成正式首页构图、传感器、性能、缓存、加载或真实声音的验收证据。
- 继续授权覆盖已确认后续里程碑，仍按原 STEP 串行和有效依赖推进；不包含对外发布、生产数据变更或长期规则修改。
- STEP-002 前保存原 index.html、api.js 的精确源码及本地 Chrome 冷访问／缓存／刷新基线于 execution/evidence/home-m1/baseline/ 与 baseline-results.json。API 为受控响应，不能代替 M4 同设备同网络真机对照，也不能据此宣称性能收益。
- 当前 STEP-002 IN_PROGRESS；正式契约未开始，M1 闸门未到达。


### 9.8 STEP-002：首页小图接入（2026-10-02）

工作项 VERIFIED（§9.2 DONE）；M1 继续 STEP-003，正式契约未开始。

- 实现：scripts/export_home_thumbnails.py、frontend/static/images/home-thumbnails/v2/manifest.json、index.html 的 HOME_AVATAR_MAP／updateHomeAvatar／homeAvatarFallback，以及 api.js::updateAvatarEmotion 的可选 avatarMap／onError。未提供可选参数的设置页等继续原 AVATAR_MAP；关系与状态文字未改变。
- 保留原素材；比例缩放、保留透明度，默认／情绪宽 126px（顶栏 42px 的 DPR3），日记 168px（56px 的 DPR3）。加载专用头像保留原 256px JPEG 字节，仅版本化文件名，不同步情绪。
- 默认头像 683,856 → 18,394 字节；日记 612,551 → 36,924 字节；7 个情绪各约 29～30KB。十图总字节见 manifest，可复现导出；预算未用来替代视觉核对。
- 删除已由 DOM 请求的头像重复预载及日记原图预载。预载复用 DOM 图片；首页失败 URL 按本页集合记录，默认／加载头像互为回退，全部失败时隐藏图像避免破图，不请求原大图。
- 实际故障测试曾发现旧加载器在默认图片失败后再次预载；根因为 DOM、静态预载和情绪预载重复链路，局部修复后通过。没有改加载退出时序／数据规则（仍属 004／006）。

| 要求 | 实现与证据 | 结果／范围 |
|---|---|---|
| AC212 初始／7 情绪、文字不变 | tests/test_home_assets.cjs；step-002-results.json | 通过，实际首页 DOM／资源；API 受控 |
| AC212 其他页默认调用兼容 | 打开 settings.html 调用原 updateAvatarEmotion('开心') | 通过，仍请求原 emotion_happy.png |
| AC212 情绪／默认／加载／全部回退失败 | 浏览器阻断指定小图，记录请求、回退 URL 和页面异常 | 四类故障通过；失败默认不重复，无原大图、无未捕获异常 |
| AC212／213 冷访问／缓存／刷新 | tests/capture_home_resources.cjs；step-002-requests.json；访客／登录各 3 次 | 首页小图冷访问访客 74,996、登录 104,558 字节；缓存及刷新服务器图片字节均 0，native HTTP cache 实际生效；不是总页传输量 |
| AC212 同内容／真实显示尺寸质量 | step-002-quality.png、step-002-visitor.png、step-002-authenticated.png | 桌面 Chrome DPR3 的 42／56／96px 原图／派生图对照已核对；内容、比例及脸部一致，缩小有预期重采样；未真测新小图于四类手机 |
| 相关既有回归 | .venv-step001/bin/python -m pytest tests/test_h5_static_contract.py -q | 19 passed；只证明静态约束，浏览器行为由上列补充 |

证据目录 execution/evidence/home-m1/。改造前 baseline-results.json 保存原始受控运行；其路由拦截会禁用 HTTP cache，因此其中 cached 标签只是重复访问，不能据此宣称旧缓存有效或比较缓存收益。本轮改为 Chrome CDP 只阻断外部字体，保留原生缓存，改造后缓存记录明确区分；M4 真机基线仍待实际采集。

源码发生已授权实现变化，原 29 输入摘要不再整体适用；PRD、源 STEP §1—§8、实施计划和原素材未改。来源新摘要由最终快照重新核对，不能把源代码变化标成上游版本冲突。没有加载时间收益、真实接口、真机性能或声音的通过结论。


### 9.9 STEP-003：正式首页静态场景（2026-10-02）

工作项 VERIFIED（§9.2 DONE）。来源 F201／F202／RQ-01，负责 AC201／203／209／211 的静态子条款；动态、等待截止和数据仍按原 STEP 追踪。

- 实现 index.html 的两张完整核心图和四张 data-src 可选贴片；home-scene.css 只限定首页；home-scene.js 只调整布局，不实现动态／偏好／传感器。静态两图为 HTML 固有内容，场景脚本缺失仍能展示。
- 人物画布固定 853×1844 比例，所有贴片共用位置／视差／动作／呼吸容器坐标。贴片百分比和锚点来自七图 manifest；未裁图或拉伸。可选贴片当前不下载、不展示，后续 008 才增强。
- 根据实际顶栏和 Hero 矩形调整人物画布的宽、左、上，避免脸部被时钟／状态和首层业务卡遮挡。ResizeObserver／resize／visualViewport 变化重新计算；布局能力异常隔离到场景，保留 CSS 构图。
- 桌面 560px 竖向居中，外侧暗色延展；背景只在竖向场景内 cover。保留顶栏、快捷栏、朋友圈、日记、CTA 的原顺序、登录策略和事件。
- 允许页面缩放，viewport-fit=cover；短横屏和卡片增长用页面自然滚动保持底部可达，没有全局 touch-action:none。使用 100dvh 并有 100vh 回退，安全区沿用 env()、可通过受控变量验证。
- 核心失败隐藏失败图片，人物失败时全部贴片停留隐藏；另一张已完成核心图和底色保留。测试中的 Canvas 故障不影响当前静态场景；不把它声称为动态 Canvas 实现通过。

| 要求 | 实际行为证据 | 结果／范围 |
|---|---|---|
| AC201／211 正式首页四种视口 | tests/test_home_scene.cjs；step-003-results.json；4 张睁眼截图 | 375×667、390×844、430×932 DPR3，1280×720 DPR1；脸部框避开顶栏／Hero 文字和下方入口；入口有可见几何范围 |
| AC201 共用贴片坐标 | 加载 4 张贴片，用真实布局矩形对照 manifest 百分比；4 张闭眼截图 | 全部百分比误差 <0.02 个百分点，睁闭眼截图已核对；检查改变只在浏览器测试实例中，不开启产品动态 |
| AC211 旋转／卡片增长／短空间 | 各视口旋转后，日记卡增至 210px，375×450 模拟短空间 | 页面可滚动至 CTA 和日记；日记／快捷入口实际打开共享登录窗，输入可聚焦；无未捕获异常 |
| AC211 安全区／缩放 | 顶／底插入 34px 受控安全区变量，检查真实 computedStyle；viewport 不再禁用缩放 | 受控安全区通过，底部 padding≥34px；CSS 未禁止正常手势。未冒充 iOS 真键盘、真实 env() 或手指缩放测量 |
| AC203／209 单张核心图、可选图缺失、脚本缺失、Canvas 不可用 | 浏览器请求阻断／能力故障注入，保留真实业务 JS，实际点击共享登录入口 | 5 类通过，失败单图时只剩另一完整层；当前可选图尚不请求，不受其缺失影响；场景脚本缺失仍有 HTML 静态核心；业务无整页异常 |

证据在 execution/evidence/home-m1/step-003-*.png、step-003-results.json。所列均为桌面 Chrome 控制视口／故障、受控业务 API；新布局的四类真机、真实键盘、部署、倾斜和声音仍未测，本次用户手机确认只覆盖 §9.7 的资源质量。

相关静态测试的旧图 URL 断言按 F201 的新素材引用更新，保留全部原业务／鉴权断言；19 passed。原场景 Index.png 和语音背景仍保留，未修改语音文件、后端、Nginx 或正式契约。当前共 3/18；M1 集成复核及闸门证据交接随后写回本节，不能据本 STEP 宣称整功能完成。


### 9.10 M1 闸门证据交接（2026-10-02）

handoff_state = **GATE_EVIDENCE_READY**。这是执行器证据交接，**不是 M1 闸门通过**；3/18。M2—M5 未启动，正式契约未修改，未汇总闸门通过后的 M1 临时契约。

| 计划验收 | 证据 | 结果与边界 |
|---|---|---|
| M1 #1—3／001 素材 | §9.6 原导出／桌面证据＋§9.7 用户手机／微信资源质量确认 | STEP VERIFIED；核心预算差额保留；详细真机版本仍未提供 |
| M1 #4—6／002 小图、回退、清单 | §9.8、step-002-results.json、step-002-requests.json、原／派生对照和请求基线 | STEP VERIFIED；最终 M1 首页快照重新运行 test_home_assets.cjs 退出 0，全部 7 情绪／4 故障／兼容行为通过；真实缓存清单已有单独证据 |
| M1 #7—9／003 静态构图、故障、边界 | §9.9、step-003-results.json、4 视口睁／闭眼截图 | STEP VERIFIED；四种尺寸、共同坐标、旋转、卡片增长、安全区模拟、可点击与 5 类故障通过；真实设备键盘／env／手势证据单独保留未测 |
| M1 相关回归／来源稳定性 | test_h5_static_contract.py，Node syntax，git diff --check，source-snapshot.json | 19 passed，JS／HTML 内联脚本语法和差异检查退出 0；17 个导出文件字节／摘要一致，STEP §1—§8 正文摘要不变 |
| 真实本地运行预览 | local-preview-results.json、local-preview.png；http://127.0.0.1:54323/pages/index.html | 实际静态服务可开，两核心层及结构可用，零未捕获异常；本地 API 404，未接真实业务接口，不冒充业务回归或部署验收 |
| 契约增量 | STEP-002-契约增量.md、STEP-003-契约增量.md | 可复核 STEP 草稿已落盘；001 无业务增量，未创建空稿；正式契约保持原文 |

29 个审核来源的本轮复核：只有 SRC-04（index.html）、SRC-05（api.js）、SRC-09（静态契约测试）因已授权实现改变，其余 26 项含 PRD／正式契约／原图／Nginx／语音原文均保持摘要一致。完整实际摘要见 source-snapshot.json；不把历史 source_digest 当成本轮最终源码摘要。

恢复点：接收上述完整 M1 证据并判定阶段闸门；用户已收到一次异步确认，询问是否本轮明确调用 milestone-step-execution 以覆盖所有后续闸门并按既有顺序推进。调用确认未到时，不擅自判定通过或进入 M2／STEP-004。具体依据：execute-approved-work 的“到达里程碑边界时提交 GATE_EVIDENCE_READY 和闸门证据并停止，只有 milestone-step-execution 判定闸门通过后才能进入下一里程碑”；该闸门技能“仅在用户显式调用或明确点名技能时使用”。这是调用边界，不是新增产品／每 STEP 的确认，也不修改长期规则。

临时预览继续运行：素材对照端口 54322；静态首页端口 54323（同 Wi-Fi 可用 http://192.168.1.3:54323/pages/index.html）。后续真实部署、四类真机动态／倾斜、性能和加载／声音仍按各原 STEP 收集，不由本轮资源质量确认替代。未使用全量后端测试推定首页运行通过，未发布。


### 9.11 本轮范围与恢复决定（2026-10-02）

USER_DECISION：用户在已知 M1 证据和闸门调用说明后明确要求“完成后续 M2-M3 里程碑”。本轮以该最新动作范围作为连续实施授权，按 STEP-004—013 串行推进，不重复要求同一调用确认，不修改长期技能规则或源 STEP。M1 技术证据继续有效；台灯遮挡按前述讨论作为视觉延期项，在 M3 末尾／进入 M4 真机总验收前统一修正，脸部和业务入口可用仍是当前硬约束。未把 M1 记录为技能已作出 PASS 判定。

本轮启动时 STEP-004 IN_PROGRESS；M2—M3 的技术实施与本地验收在授权内推进，真实设备权限／声音／选参仍按原验收收集。缺少真实证据的子条款不标通过；M4—M5、部署发布和正式契约不在本轮范围。已异步请求可用 HTTPS 测试地址和真机版本，继续不依赖该信息的工作。最终状态见 §9.12。

### 执行回传 STEP-004：有截止的加载与存储故障隔离（2026-10-02）

实现：index.html 最早 head 脚本 HomeStartup、核心图片可用解码等待和幂等遮罩退出；api.js 的首页专用存储退化入口，其他页默认访问方式保留。背景／人物是唯一门闩，API、头像、可选素材独立；5 秒核心截止后仍按 500ms 停留＋550ms 退出，8 秒绝对兜底；暴露 phase／startedAt／deadlines 供晚模块读取。

实际 index.html 的桌面 Chrome 受控测试：API 挂起约 4082ms 退出；核心下载／decode 挂起约 6070ms；坏图约 4089ms；localStorage 属性／token 读取、Session get/set/remove（含刷新）、关系缓存 set/remove 故障均无未捕获异常，入口能响应；合法 Session＋本地读取失败约 32～38ms 跳过，同标签再次进入跳过、刷新恢复普通节奏。证据包含注入对象、键、操作、启动路径与实测退出时刻；不记录 token 内容。19 passed 静态回归。

初始存储不可读保持 unknown／占位，不假造访客或真实 Lv0；已知登录快照在后续读取失败时保留，关系写入失败不终止启动。页面结构立即显示；遮罩移除时强制可见入口，取消随进度持续更新大面积 filter。真实手机环境不由这些受控故障推定。后续有界模块状态由 006、请求保护由 005 联合完成；M2 尚未结算。下一位置 STEP-005。

### 执行回传 STEP-005：共享请求取消和失效隔离已验证（2026-10-02）

实现 api.js request 可选 signal／isCurrent，覆盖 fetch 前、响应副作用前和 JSON 解析后；默认调用仍保留原网络失败结果和四类有效 401 策略。正式首页＋实际共享脚本的桌面 Chrome 测试 8 项通过，包含真实 fetch 取消、旧 401 不清新登录、解析途中上下文变化及四类有效 401 的导航／弹窗／清理。测试夹具改为首次播种，避免导航后重新伪造 token。无服务端或正式契约修改；下一恢复位置 STEP-006。

### 执行回传 STEP-006：独立模块及有界批次已验证（2026-10-02）

新增 home-data.js 首页协调器，六模块并发独立显示；访客仅公共 Feed；模块具有 pending／success／error／visitor／unknown 状态，失败保留已知数据并提供局部重试。所有请求共享批次绝对 8 秒截止和真实 AbortController，代次、登录快照及头像异步加载均有有效性检查；同批次 load／Feed／重试去重，登录变化取消旧请求。桌面 Chrome 实际首页 7 组行为通过：公共请求白名单、日记先到＋未知锁、全部挂起取消六请求、保留数据＋局部重试、账号切换旧 401、当前有效 401、启动 token 读取异常。19 项静态契约回归通过；结构测试跟随模块抽取读取跨文件源码，独立行为以浏览器证据判定。M2 技术证据就绪，未冒称正式里程碑闸门 PASS；依最新 M2—M3 连续执行授权继续 STEP-007。

### 执行回传 STEP-007：统一生命周期已建立（2026-10-02）

重组 home-scene.js，场景资源由唯一实例登记；加载、隐藏、系统减少动态与 bfcache 原因集合共同控制单一主 RAF；帧时间差限制在 0—40ms，恢复不追赶后台时间。布局观察器、事件与受管计时器统一销毁，晚挂载直接读取 HomeStartup。实际首页桌面 Chrome 单实例 20 次重复挂载、组合原因、停帧、恢复及 true pagehide 清理通过；persisted PageTransitionEvent 是受控路径验证，不冒充浏览器真实 bfcache 入缓存资格。home-scene-core.js 复用原 demo 纯规则并增补时间差／旋转计算，无业务协议变更；下一恢复 STEP-008。

### 执行回传 STEP-008：七类渐进动效已接入（2026-10-02）

呼吸、眨眼（含双眨眼）、三组发丝弹性、待机、灯光、雨与城市窗星光全部接入唯一主调度。可选图仅无暂停原因且静态人物有效后请求；贴片坐标与源图一致；环境使用缓存雨／光点纹理，时间差驱动。暂停复位自然人物、清闭眼与双眨眼／待机排队，无独立动作计时器和 RAF。桌面 Chrome 实际主页观察全部动效，分别注入侧发、眨眼、灯光坏图及 Canvas 抛错并验证登录入口，初始减少动态不下载可选图；6 组通过。Canvas 当前仅应用 DPR≤1.5，Q201 像素预算和降级窗口仍待真机量测，未把本 STEP 局部功能证据当作 AC210 完整性能验收。下一恢复 STEP-009。

### 执行回传 STEP-009：人物本地回应与输入优先级已验证（2026-10-02）

在统一人物容器内增加可访问轻触按钮，命中限于人物头脸与上身；业务顶栏、卡片与覆盖层保持更高命中优先级。Enter／Space 使用原生 button 激活，同一回应中的 30 次连点合并，暂停／减少动态抑制新动作。实际访客及登录首页验证点击、两类键盘、连点、暂停和入口命中；回应期间 API 数量及 URL 均未变化。原生移动缩放手势未在桌面假装实测，留待 M4。下一恢复 STEP-010。

### 执行回传 STEP-010：更多互动与动态偏好已验证（2026-10-02）

更多入口沿用首页共享登录门禁，登录不重放原操作。新增主页动态控制面板，启动首次可能运行之前读取 localStorage lxm_home_motion_enabled；无选择默认开，0 为关闭；浏览器内刷新／重访／账号切换沿用，独立浏览器分别设置。系统减少动态始终覆盖，UI 区分用户选择与实际运行；真实偏好 getItem／setItem 抛错只影响保存，显示无法读取或仅本次生效，不阻断首页。实际桌面 Chrome 5 组通过；记录新存储键供 M5 契约收口，不修改原 Session key。下一恢复 STEP-011，四类真机 HTTPS／版本与声音环境仍待用户提供，本轮继续其可独立实施与受控验证部分，不伪造真机通过。

### 执行回传 STEP-011：主动倾斜实现，真实环境验收未完成（2026-10-02）

实现点击链内同步调用 requestPermission，区分关闭／等待授权／等待有效数据／已开启／暂停／不可用；授权不当作数据有效，null／NaN 方向值忽略，5 秒无数据关闭并反馈。方向事件只更新主调度输入；旋转重新校准；关闭、隐藏和其他暂停移除监听，晚授权失效，已允许恢复不重复弹权限。桌面实际首页 6 组受控 DeviceOrientation 故障／方向／组合暂停／资源无增长通过。此证据不替代 iOS Safari／Android Chrome／iOS 微信／Android 微信真实允许、拒绝、方向与 HTTPS 验收。已向用户请求真实 URL／机型／版本，本项保留 IN_PROGRESS；依 M2—M3 连续实施授权推进 STEP-012 的本地接点，不宣称依赖真机子条款或 M3 闸门已完成。

### 执行回传 STEP-012：实际面板暂停适配，声音验收未完成（2026-10-02）

仅主页适配真实 auth-login-modal.is-open 与 voice-entry.hidden／可见状态；根观察器仅观察 body 的直接节点及各面板 class／hidden／style，不订阅场景逐帧 style；由场景统一登记并销毁。真实共享登录打开／Escape／重复开关、VoiceEntry.begin 准备／权限说明及关闭、组合隐藏＋关闭动态均通过；未接通／结果页仅使用实际语音 DOM 的受控状态变化，已明确区分。语音脚本、音频传输和协议未修改。真实麦克风、接听声音与已有通话控制未验，依原完成条件保留 IN_PROGRESS；Q201／Q203 和设备回传待补。继续 STEP-013 可独立局部优化及参数接点，不能结算 M3 全部通过。

### 执行回传 STEP-013：质量策略与调度接点完成，真机选参未完成（2026-10-02）

单一主 RAF 驱动全场景，环境优先 30fps，纹理缓存和 DPR≤1.5；支持带来源的像素预算、统计窗口及最低帧率配置。降级顺序为减少雨和星光、停止发丝、退为静态；同实例隐藏／弹窗／偏好切换和真实 Chrome bfcache 往返均保留档位，新页面重新评估并尊重关闭／系统减少动态。记录原始帧间隔、帧率、长任务、人物回应首帧延迟及可用内存指标。实际主页本地运行与受控低帧测试通过；测试用 200000px／300ms／30fps 明确仅属夹具，不是 Q201 正式参数。按源 STEP 的 Q201 真机量测门，生产默认未启用自动降级判定；不能把参数接点或桌面约 60fps 当成手机目标通过。等待 HTTPS URL、四类环境版本及实测后配置并复验，本项保持 IN_PROGRESS；M3 未达到全部完成条件，M4—M5 未启动。

### 9.12 M2—M3 本轮最终回传与恢复（2026-10-02）

**本轮结果**：M2／STEP-004—006 实现及本地验收完成，技术证据 `GATE_EVIDENCE_READY`。M3／STEP-007—010 已验证，STEP-011—013 局部实现和受控验证通过；四类真机倾斜、真实声音和 Q201 正式选参未完成，M3 闸门 `NOT_REACHED`。共 10/18 DONE。用户的 M2—M3 连续实施授权已执行，没有再次请求同一技能调用确认；未伪造正式闸门判定。

**实际变更**：frontend/pages/index.html、frontend/static/js/api.js、home-data.js、home-scene-core.js、home-scene.js、frontend/static/css/home-scene.css；新增相应浏览器行为验证与 tests/verify_home_m2_m3.cjs，更新 tests/test_h5_static_contract.py 的跨模块读取。仅修改本文件 §9 并生成 STEP 契约增量草稿；PRD、源 STEP §1—§8、语音／音频、后端、Nginx、正式契约及 M4—M5 均未改动。

| 验收范围 | 本轮最终源码证据 | 结果及边界 |
|---|---|---|
| 004 加载／存储／最迟释放 | home-m2/step-004-results.json、step-004-boundaries-results.json | 14 个启动场景及 5 个补充边界通过；API 挂起约 4.1 秒释放，核心／decode 挂起约 6.1 秒；普通流程停滞时真实 8 秒兜底；会话跳过、刷新、属性／token／Session／关系缓存读写异常、绝对截止恢复及释放后监听清理通过 |
| 005 请求上下文／兼容 | home-m2/step-005-results.json | 8 项通过；实际 fetch 取消、旧 401／解析迟到隔离、四类当前有效 401 既有行为及默认网络失败结果保留 |
| 006 独立数据／有界批次 | home-m2/step-006-results.json | 8 组通过；访客只取公共 Feed、模块先到先显示、未知日记锁、8 秒取消全部挂起请求、局部重试保留旧数据、账号代次／迟到头像、当前有效 401、存储未知及成功包缺字段校验；API 为受控响应 |
| 007 生命周期／降级边界 | home-m3/step-007-results.json、scene-boundaries-results.json、native-bfcache-results.json | 单实例重复挂载、唯一 RAF、组合原因、后台停帧、自然恢复／销毁通过；场景脚本晚到超过 8 秒、观察器／可选能力抛错、脚本／核心图失败仍保留入口；实际 Chrome 导航后退的 pageshow.persisted=true，保留原实例并恢复 |
| 008 七类渐进动态 | home-m3/step-008-results.json、step-008-motion.png | 呼吸、眨眼、三组发丝、待机、灯光、雨、星光实际运行；坏可选图／Canvas 和系统减少动态共 6 组通过；不证明手机性能 |
| 009 人物回应 | home-m3/step-009-results.json | 访客／登录两组通过；点击、Enter／Space、连点合并、系统／偏好暂停抑制、业务入口优先；不增加 API 或导航 |
| 010 动态偏好 | home-m3/step-010-results.json | 5 组通过；初始关闭不短暂启动；刷新／重访／换号／独立浏览器、存储读写抛错、系统覆盖及更多入口登录门禁；保留本次选择并准确显示未持久化 |
| 011 倾斜 | home-m3/step-011-controlled-results.json | 6 组受控方向／权限／无有效数据／旋转／组合暂停／监听治理通过；未替代四类 HTTPS 真机权限、方向及拒绝行为 |
| 012 面板暂停 | home-m3/step-012-controlled-results.json | 实际共享登录、VoiceEntry 准备／关闭及组合原因通过；部分错误／终态为受控 DOM；真实麦克风、接听声音与原通话控制仍未验 |
| 013 质量策略 | home-m3/step-013-controlled-results.json、native-bfcache-results.json | 未选参时采集指标；受控参数下像素预算与雨／星光→发丝→静态顺序通过，暂停和真实 bfcache 保留档位，新页面重新评估；测试选参不是 Q201，正式默认未启动自动降级 |
| 延期构图修正 | home-m3/final-layout-results.json、final-375x667.png、final-390x844.png、final-430x932.png、final-1280x720.png | 人物共同坐标的宽度上限 64%、横向锚点 64%；四尺寸脸部避开顶栏／卡片，台灯右侧留可见区域，最大倾斜位移下仍有余量；贴片误差 <0.02 个百分点；旋转、卡片增长、短空间滚动及人物／入口命中通过 |
| 其他页小图兼容 | home-m3/compatibility/step-002-results.json | 最终源码复跑 7 情绪／4 类失败回退／设置页默认原图路径均通过；保留 home-m1 的原始历史证据 |

**最终验证入口和来源**

- tests/verify_home_m2_m3.cjs 按串行方式执行 15 组实际浏览器脚本，全部退出 0；完整名称、时长和最终源码 SHA256 见 [final-browser-verification.json](execution/evidence/home-m3/final-browser-verification.json)。环境为桌面 Chrome 154.0.8037.97，Playwright 受控 API／存储／传感器场景分别记录；真实 Chrome bfcache 独立验证，不把合成事件当成原生缓存证明。
- .venv-step001/bin/python -m pytest tests/test_h5_static_contract.py -q：19 passed；JS／HTML 内联语法及 git diff --check 退出 0。静态和受控通过均不替代未测的真实环境子条款。
- [source-snapshot.json](execution/evidence/home-m3/source-snapshot.json) 复核 29 个定向输入：仅 SRC-04／05／09 因本轮实施改变，其余 26 项不变；源正文 SHA256 仍为 4677826738a9439f60b343e26fce8a1ba0ee081b235e053cfae3f6ddd0c43bd4。保持既有用户改动，不扫描迁移基线或非权威历史。
- STEP-004—013 的 [契约增量草稿目录](execution/contract-drafts/) 已保存实际变化和未验边界；未生成冒称已过闸门的里程碑契约，也未开始 STEP-018 正式整合。

**运行环境生效**：本地静态预览 http://127.0.0.1:54323/pages/index.html 已重新启动并在应用浏览器新标签核对，HTTP 200、加载遮罩移除、7 张场景图全部加载、Canvas 存在、人物按钮启用、业务入口可见。该服务只提供 frontend；API 404 时公共模块显示失败及重试，未接真实业务服务，也不是 HTTPS 部署或真机授权环境。四尺寸截图为实际前端配受控接口，不冒充线上数据。

**唯一恢复位置**

1. 接收可用 HTTPS 测试 URL，并列明 iPhone／Android 的机型、系统、Safari／Chrome／微信版本；之前用户“手机和微信资源正常”只结算资源质量，不能推定倾斜、声音和性能通过。
2. STEP-011：四类环境分别验证主动允许／拒绝、没有有效数据反馈、倾斜方向／旋转、关闭／后台／动态关闭／系统减少动态与恢复；微信能力不足按实际反馈核对。
3. STEP-012：在既有支持的语音环境验证准备、麦克风权限、通话、错误／结果、关闭时场景暂停与组合原因；检查真实声音、静音／结束等既有控制。保持当前微信语音支持策略。
4. STEP-013：按 Q201 同设备量测帧率、长任务、回应首帧、内存及 Canvas 总像素，确定正式像素预算／统计及降级窗口／阈值后接入并复验同页保档及新页重评；受控 200000px／300ms／30fps 不直接转为产品配置。

这些真实证据补齐前，011—013 不标 DONE，M3 不结算完成。M4—M5、部署发布和生产数据变化仍需各自既定范围与授权，不因本轮局部通过自动启动。

### 9.13 M4 继续开发的范围（2026-10-02）

USER_DECISION：用户明确要求“继续m4开发”。本轮按原 014—017 顺序推进可独立完成的代码、测试工具与本地验证；不重复请求阶段调用确认。M3／011—013 的真机、真实声音和 Q201 正式选参尚未补齐，不把继续开发授权当成这些验收已通过；M4 的真实环境总验收仍须满足原条件，M5 和对外发布不在本轮范围。已请求 HTTPS 首页／API 地址、设备／系统／客户端版本。

本轮先实施 STEP-014 的首页旧背景开关、双核心失败回退，以及仅首页版本图片的缓存与首页／场景模块重验证配置；使用独立临时前端副本、受控 API 和一次性 Nginx 容器，不接现有数据库。所有实测区分本地 Linux／桌面 Chrome、受控注入和真实手机；历史 M1—M3 证据保持，新增复验写 home-m4/。PRD 和原 STEP 验收口径不改写，当前状态以本节后续最终回传为准。

### 9.14 M4 本地开发与验证回传（2026-10-02）

**执行结论**：014 的代码与本地配置已落地，015—016 的补充桌面采样工具、017 的保留业务和输入回归已完成。014—017 仍为 IN_PROGRESS：原验收要求的外层 HTTPS、四类真机、同设备新旧对照、真实语音及 Q201 正式参数没有完整证据。M4 闸门 NOT_REACHED，未提交 GATE_EVIDENCE_READY；M5／正式契约整合 NOT_STARTED。本轮未发布到外网或变更生产数据。

| STEP／原验收点 | 本次实现／证据 | 本地结果与剩余边界 |
|---|---|---|
| 014／AC215 缓存、版本与精确旧图路径 | nginx/nginx.conf；[step-014-cache-results.json](execution/evidence/home-m4/step-014-cache-results.json) | 一次性 Linux 文件系统中的真实 Nginx 校验：首页／专用 JS／CSS 每次获取，摘要图片一年 immutable，manifest／其他资源原策略不变；精确 Index.png 返回 200、错误小写与缺失摘要图返回 404；404 不带长期缓存；同大小、同 mtime 的 HTML 更新也能获取新图片 URL；缓存访问和刷新实测。原 API／语音／后台路由仍转发。外层 HTTPS／CDN 未验 |
| 014／AC215 回退保留加载／请求修复 | index.html::HomeStartup／mountScene／runHomeLoader；home-scene.js／CSS；[step-014-fallback-results.json](execution/evidence/home-m4/step-014-fallback-results.json) | 7 类通过。根属性 dynamic 默认；改 legacy 并刷新只下载旧背景，不下载新七图。双核心失败切旧图，单核心／可选失败保留可用基础层。存储抛错、API 挂起、坏旧图均有界释放，业务门禁可用；保留动态偏好，旧模式不运行动态或申请倾斜权限。正常新模式不预热旧大图 |
| 015／AC210 量测工具与持续运行 | tests/capture_home_m4_desktop.cjs；[step-015-016-desktop-measurements.json](execution/evidence/home-m4/step-015-016-desktop-measurements.json) | 实际 Chrome 30.03 秒、1802 帧，主调度平均 60.00fps；量测窗口内 0 长任务，5 次真实指针命中后的回应首帧 9.6—12.6ms。7 个 JS 堆样本约 2.82—5.19MB，仅 JS heap、不当全浏览器内存峰值或无泄漏结论。10 次面板开关后 id／effects=3／subscriptions=35／timers=0 不增长。Canvas 585×1266、740610px、DPR1.5；正式校准仍 false。桌面结果不作为手机目标或 Q201 选参 |
| 016／AC212—213 冷／缓存／刷新传输与时刻 | 同上量测脚本及 JSON；regression/step-002-results.json、step-004-results.json、step-004-boundaries-results.json | 两个独立浏览器上下文，访客／登录各三次。冷访问遮罩约 4085／4089ms、入口命中约 4086／4090ms；会话缓存导航约 18／15ms；刷新约 4068／4070ms。CDP 整页收到的编码字节：访客 1244446／43683／41872，登录 1275128／44882／43076；该口径含协议记账，Resource Timing transferSize 和 bodySize 另列。七图各请求一次，默认无旧图预热，缓存／刷新使用浏览器原生缓存；固定约 4.05 秒节奏保留。没有同机改造前真机基线，不声称相对提速、手机质量或账单收益 |
| 017／AC214 保留数据与时段 | tests/test_home_preserved.cjs；[step-017-preserved-results.json](execution/evidence/home-m4/step-017-preserved-results.json) | 53 项实际首页场景通过：四级标签／growth_value 回退／current_growth 优先／满级 100%、known_days、状态语三层优先、固定日记句／四档相对时间／严格 NEW／真实 Lv0 锁、Feed 更新时间／角标；14 个七时段边界和 Good night。时间、数据为明确受控夹具 |
| 017／AC206 入口、键盘与单次登录恢复 | 同上＋regression/step-005-results.json、step-006-results.json、step-009-results.json、step-010-results.json | 访客／登录分别点击以及真实 Tab→Enter／Space 操作设置、关系、记忆、Feed、日记、CTA、更多；核对当前导航／门禁和未读 focus。视频／入睡仍“敬请期待”；实际共享登录表单配受控 POST，六模块各只恢复一次，不重放更多操作或申请倾斜。微信能力夹具调用实际 VoiceEntry，保留“换个浏览器”提示；不等于真机微信或真实声音。目的页为受控接收壳，只证明首页导航目标 |
| 017／AC211 同一快照布局、动态、降级与恢复 | regression/final-layout-results.json、四尺寸 final-*.png、step-008-results.json、step-011-controlled-results.json、native-bfcache-results.json、scene-boundaries-results.json | 最终生产快照下四尺寸、台灯与脸部余量、贴片、动态／受控倾斜、旋转／卡片高度／短空间滚动、输入优先及真实 Chrome bfcache 复验通过。原 003 静态素材与坐标前提未变化；不把桌面尺寸、传感器夹具或安全区 CSS 当手机原生缩放／键盘／方向验收 |

**最终验证与运行环境**

- `tests/verify_home_m4.cjs` 串行执行 17 项浏览器脚本，全部退出 0；[final-browser-verification.json](execution/evidence/home-m4/final-browser-verification.json) 保存名称、时长及 8 个最终源码摘要。新增保留能力脚本单独执行，53 项通过；截图收起弹层的等待修正后，7 类回退再次通过。生产源码在这些验证后未改变。
- `.venv-step001/bin/python -m pytest tests/test_h5_static_contract.py -q`：19 passed；`RUN_VOICE_NGINX_RUNTIME=1 .venv-step001/bin/python -m pytest tests/test_realtime_voice_nginx_runtime.py -q`：1 passed，验证一次性服务中的 HTTP／SSE／初次及恢复 WebSocket，未使用真实麦克风或声音。JS／三个 HTML 内联脚本语法及 `git diff --check` 通过。
- 所有缓存／性能容器采用临时前端副本与受控 API，不连接既有数据库；测试结束清除自己的容器／网络。实际机是 macOS 桌面 Chrome 154.0.8037.97，390×844 DPR3 等仅为测试视口。字体请求由 CDP 阻断，测试 API 为本地，网络无节流；量测方法及未验范围保存于 JSON。
- 本项目既有 `lxm_nginx` 挂载的是当前仓库 frontend／nginx.conf，只绑定 `127.0.0.1:80`。`nginx -t` 成功后平滑 reload，六个实际静态 HEAD 均 200；首页／模块 no-cache、摘要图 immutable、旧背景／语音样式保留原策略，见 [local-nginx-runtime.json](execution/evidence/home-m4/local-nginx-runtime.json)。这是本地 HTTP 配置生效，不是外层 HTTPS 或生产发布。
- 静态预览仍为 http://127.0.0.1:54323/pages/index.html，仅提供 frontend；在应用浏览器新标签核对根模式 dynamic、遮罩不存在、七图全部 naturalWidth>0、主内容可见。无 API 的 Feed 失败／重试是该预览环境的实际状态。受控业务截图与本地预览分开，不冒充真实业务数据。
- [source-snapshot.json](execution/evidence/home-m4/source-snapshot.json) 定向复核 29 个输入：相对原审计只有 SRC-04／05／08／09 改变，25 项不变；相对 M3 仅新增首页与 Nginx 两项来源变化。原 STEP §1—§8 摘要仍为 `4677826738a9439f60b343e26fce8a1ba0ee081b235e053cfae3f6ddd0c43bd4`。原 M1—M3 证据保留，新复验写 home-m4/regression/；用户其他文档改动保留，未扫描迁移基线或非权威历史。
- 本次生产变更仅 index.html、home-scene.js、home-scene.css 和 nginx.conf。api.js／home-data.js／home-scene-core.js／静态契约测试保持 M3 最终源码。新增测试：home_nginx_helpers、cache、fallback、preserved、desktop capture、verify_home_m4；原回归脚本只增加可指定证据目录以保留历史。实际增量见 [STEP-014-契约增量.md](execution/contract-drafts/STEP-014-契约增量.md)，无新增业务端点、存储键或数据库迁移。
- [final-verification-audit.json](execution/evidence/home-m4/final-verification-audit.json) 汇总最终证据核对：8 个源码摘要仍匹配；30 个 JS 文件和 3 个内联脚本可解析；18 条 STEP 唯一、10 条 DONE，执行证据链接可解析；一次性首页测试容器无残留。原完成标志与未验边界保持，不以此局部审计结算 M4。

**下一恢复位置与待验条件**

1. 等待已请求的 HTTPS 首页／API 测试地址、iPhone／Android 机型、系统及 Safari／Chrome／微信版本；同时列明网络、可用测试账号和原支持环境中的语音条件。用户此前“手机和微信资源正常”继续作为资源质量证据，不能扩展为倾斜、声音或性能通过。
2. 按 §9.12 的 011→012→013 顺序补真实允许／拒绝／无数据／旋转和暂停恢复、真实麦克风／通话声音／原控制，以及同设备持续运行量测；据 Q201 确定像素预算、统计／降级窗口和最低帧率后接入正式配置，复验同页保持及新实例重评。当前正式自动降级未配置，不转用桌面或受控阈值。
3. 然后按 014→015→016→017 原顺序结算：核对实际 HTTPS 和外层缓存／旧图响应及版本切换；保存同机同网络旧版／新版持续运行、低档、冷／缓存／刷新和弱网记录；四类设备验证最终素材、倾斜／卡片变化下布局、真实键盘／手势及全部入口和语音。没有真机旧版基线时只报告绝对指标，不声称相对收益。
4. 每项原完成标志有证据后才标 DONE 并准备 M4 闸门证据。当前完成数仍 10/18；不自动进入 M5、整合正式契约或发布。恢复先核对最终源码 SHA、设备／网络和配置生效条件，只补变化或未验范围，复用有效本地证据。

### 9.15 真机连接条件排查（2026-10-03）

USER_DECISION：用户反馈手机通过 IP 无法连接，明确手机与电脑处于同一 Wi-Fi。本次只读排查连接条件，未更改 Docker 端口、防火墙、网络、信任证书或对外发布。

RUNTIME：静态 Python 预览监听 `*:54323`；本项目 Docker 主入口实际监听 `127.0.0.1:80`，与 docker-compose.voice-local.yml 的显式本机覆盖一致。电脑当前 Wi-Fi 接口 en0、局域网地址 `192.168.1.3`、网关 `192.168.1.1`；macOS 应用防火墙当前关闭，未操作它。地址可能随网络变化，不能长期写成固定部署配置。

从电脑通过 `http://192.168.1.3:54323` 对首页及背景／人物两个核心图执行实际 HTTP HEAD，三项均 200，Content-Type 正确。已提供手机访问地址 `http://192.168.1.3:54323/pages/index.html`；尚未获得手机端连接成功证据。若手机此前使用不带端口的 IP，访问的是 80，本机限定入口不能接受该连接；其他访问失败原因仍需按实际手机结果核对，不能仅凭本机回环测试排除 Wi-Fi 隔离或客户端网络条件。

该入口只服务前端静态文件，不提供真实 API，也不是可信 HTTPS。可用于先检查画面／普通动效；真实倾斜／麦克风／业务流程仍需适当 HTTPS 和同域 API 环境。下一恢复动作：用户在同 Wi-Fi 手机打开上述精确地址并反馈结果，再据证据准备真实验收入口；§9.14 的真实环境待验项、10/18 和 M4 NOT_REACHED 保持。

### 9.16 手机反馈与两图／账号状态模拟预览（2026-10-03）

USER_DECISION：用户回传手机上微信和 Chrome 均有眨眼、点击有互动，倾斜均无反应。这补充了手机连接成功及两类客户端上述普通互动的可观察证据；设备、系统和客户端版本尚未提供，不扩展为四类环境、倾斜、声音或性能通过。用户要求朋友圈模拟两张图，并明确选择“提供访客／模拟登录切换”；本次完成独立预览环境补充，不改变真实业务登录或 Feed 规则。

**实际变更与运行生效**：新增 `scripts/serve_home_preview.cjs` 与 `tests/test_home_preview.cjs`。前者仅为临时首页预览：使用现有海边／日记图片返回一条带 `image_urls` 两图的模拟 Feed；默认访客，显式选择模拟登录后提供首页私有模块夹具和更多互动面板。首页左上角标明“模拟预览”与当前状态，并链接切换页。模拟 token 仅被本服务识别，不连接真实后端、数据库或账号；原登录表单提交被预览脚本拦截，所有非 GET／HEAD 请求返回 405。正式首页文件、业务 API、Nginx、正式契约没有本轮修改，无新增产品存储键。模拟入口脚本只注入本服务返回的首页响应，未写入生产 HTML。

已核对并停止本任务旧 Python 静态预览 PID 27589，以 Node 模拟预览接替原端口；当前 PID 71444，监听 `*:54323`。启动命令：`node scripts/serve_home_preview.cjs --host 0.0.0.0 --port 54323`。从电脑通过 LAN 实际请求 Feed 与切换页均 200；应用浏览器新标签核对两张图片加载成功、模拟登录显示“亲密／陪伴你的第 12 天”，更多互动面板可打开，倾斜初始关闭。手机刷新原地址即可使用新预览，新的两图／状态切换尚未收到手机端回传。

- 切换入口：`http://192.168.1.3:54323/__home_preview`。
- 访客：`http://192.168.1.3:54323/pages/index.html?__home_preview=visitor`。
- 模拟登录：`http://192.168.1.3:54323/pages/index.html?__home_preview=authenticated`。

**验证与倾斜结论**：新增真实桌面前端集成验证通过，见 [preview-results.json](execution/evidence/home-m4/preview-results.json) 及 [模拟登录两图截图](execution/evidence/home-m4/preview-authenticated-two-images.png)、[访客两图截图](execution/evidence/home-m4/preview-visitor-two-images.png)：公共 Feed 两图及图片 200、匿名无私有字段／私有请求、无效 token 返回 401、原更多入口登录门禁、登录表单不发送凭据、切换后模拟私有展示／返回访客清 token、无页面异常。模拟界面证据不能代替真实账号验收。

另以隔离桌面 Chrome 直接访问上述 LAN IP，未注入传感器或权限，实测 `isSecureContext=false`；模拟登录后点击倾斜开关，显示“当前页面连接不支持倾斜”并恢复关闭，两张图仍加载成功，见 [preview-lan-tilt-diagnostic.json](execution/evidence/home-m4/preview-lan-tilt-diagnostic.json) 与 [HTTP 倾斜提示截图](execution/evidence/home-m4/preview-http-tilt.png)。最初测试调用 `check()` 错把开关保持开启作为动作完成条件；改为实际点击后核对有效要求“不可用时回到关闭”，未修改实现或弱化断言。代码规定倾斜每次新页面默认关闭，并需在登录后的更多面板主动开启；HTTP 阻断发生在传感器权限申请之前。该复现证实当前预览的连接前提不满足，不能据此判定手机传感器兼容性或宣称倾斜已修复。

两个新增 CJS 可解析；相对 §9.14 最终验证记录的八个生产／静态测试源码 SHA 全部相同，复用原有效回归结果，不因开发预览另跑无关业务检查。源 STEP §1—§8 摘要仍为 `4677826738a9439f60b343e26fce8a1ba0ee081b235e053cfae3f6ddd0c43bd4`；`git diff --check` 通过。未改 Docker 本机绑定、防火墙、证书信任、网络配置或对外发布。

**恢复位置**：先用切换入口完成手机两图和访客／模拟登录界面复核。真实倾斜仍需可信 HTTPS，登录后主动开启，再按 §9.14 补设备／版本、允许／拒绝／无有效数据、旋转与暂停恢复；真实声音和 Q201 同设备量测仍待完成。本次只补预览可验条件与用户反馈，STEP-011—017 保持 IN_PROGRESS，10/18 DONE、M4 NOT_REACHED、M5 NOT_STARTED，不结算整体里程碑。

### 9.17 M5 契约同步与记录收口（2026-10-03）

**USER_DECISION**：用户明确当前没有测试 HTTPS，仅正式服有证书，接受倾斜真机验收延期、功能按正常要求开发；随后要求继续后续阶段，并澄清“完成 M5，M6—8 是我记错了”。本轮据此提前完成 M5 的实际行为同步和记录核对，不再等待缺失的测试地址来开展文档工作。这个决定只调整本轮推进顺序；原功能、验收标准、未测状态和生产发布边界不变，不修改 PRD、源 STEP §1—§8 或里程碑计划，也不新增 M6—M8。

**本轮结果**：STEP-018／F212／AC216 的契约同步、源码一致性核对与追踪记录工作已完成并验证，文档工作状态 VERIFIED；提交 `CONTRACT_VERIFICATION_READY`。原 STEP-001—017 中真机、部署、真实声音和 Q201 完成条件尚未全部满足，因此 §9.2 的 STEP-018 仍 IN_PROGRESS，M5 保留待最终闸门判定。10/18 DONE 不变；未记录 `CONTRACT_MERGED_VERIFIED`，未结算整体功能完成。

**实际修改**：当前 [H5 契约](../../contract/current/h5-app/api.md) 同步本次已实现加载、图片、模块取数、共享请求、场景、交互、偏好、倾斜、暂停、质量与回退规则；既有 401 条款增加“仅当前有效请求”前置条件。`docs/INDEX.md` 和 `docs/design/README.md` 将“待实施”更新为本地实现／契约已同步并链接本文件的当前状态。本文件仅更新 §9；未改运行代码、预览服务、Nginx 配置或生产环境。

| 来源 | 当前契约唯一对应内容 | 核对结论 |
|---|---|---|
| STEP-001—003 | 静态场景与首页图片 | 资源产物、首页派生图、共享头像可选参数和静态保底一致；001 无新增 API 增量。003 的“可选层不运行”为当时静态阶段事实，最终行为按 008 的后续渐进加载合并 |
| STEP-004 | 加载时序与恢复 | 正常 3000／500／550ms、核心 5 秒、遮罩 8 秒、Session 与存储异常一致 |
| STEP-005 | HTTP 401 处理策略；共享请求上下文 | 可选 signal／isCurrent、解析及副作用前保护与默认四类策略兼容一致；不会让旧 401 清新 token |
| STEP-006／017 | 首页模块取数与保留内容 | 六模块、访客公共 Feed、8 秒取消／去重、未知／失败／真实空态、保留业务入口与内容一致；受控 API 不记作真实业务验收 |
| STEP-007／012 | 统一暂停与清理 | 单实例、原因集合、真实登录／语音面板可见性、bfcache 与销毁一致；真实声音仍待验 |
| STEP-008—009 | 渐进动效与人物回应 | 可选效果、本地回应、键盘、重复合并及业务输入优先一致 |
| STEP-010 | 更多互动与偏好 | 浏览器本地 key、默认／保存失败、系统覆盖与登录不重放一致 |
| STEP-011 | 主动倾斜 | 主动授权、安全上下文、有效数据、5 秒无数据提示、旋转及清理一致；真机验收按用户决定延期 |
| STEP-013／015 | 质量策略与当前配置 | 明确机制已实现、Q201 参数未定、正式自动降级尚未启用；桌面帧率及夹具不能代替真机选参 |
| STEP-014／016 | 资源缓存与回退 | 精确旧图路径、内容摘要缓存、HTML／模块重验证、双核心回退与加载／数据修复保留一致；外层部署仍待验 |
| STEP-015—018 | 验收边界及本文件 | 015—017 为既有机制的量测／回归，无新增业务契约；018 为同步，不新建空 M5 临时契约或第二份进度文档 |

十三份原 STEP 增量草稿保留为历史实施快照，未冒称它们已获得此前里程碑闸门通过。最终映射、对应源码位置及每个原需求／验收行保存于 [contract-verification.json](execution/evidence/home-m5/contract-verification.json)。当前 H5 契约保持原 `canonical` 文档 ID、位置和匿名白名单；文档同步状态不代表线上版本已更新。

**验证证据**：

- 本轮逐项复核源码与当前契约；原认证／页面策略除同步日期与必要的 401 有效性前置外逐字保留。13 份增量均有落点；12 个 F、6 个 RQ、5 个 G、14 个 V2-D、17 个 CSTR、17 个 AC 共 71 个编号均保留原归属、原行和证据映射。映射完成不等于相应 AC 全环境通过。
- 8 个生产／静态测试源码摘要与 M4 最终验证记录一致。复用同快照已有 17 项浏览器脚本、53 项保留能力场景、19 项静态 pytest、1 项隔离语音传输 pytest；本轮没有将这些历史结果改写为新运行，也没有复跑无关全量测试。真实声音不由传输检查替代。
- 本轮为文档载体变更，无 schema、生成或构建消费链路变更。执行增量／编号／文件映射、原认证条款保留、源码摘要和 Markdown 引用核对；检查结果见上述 JSON 与 [document-checks.json](execution/evidence/home-m5/document-checks.json)。PRD SHA 和源 STEP §1—§8 SHA 保持不变；里程碑计划保留原文，最新执行决定由本节承接。

**延期验收与唯一恢复位置**：

1. STEP-011／AC207、AC208、AC217：有可用可信 HTTPS 后，在列明机型、系统和客户端版本的四类目标环境检查允许／拒绝、无有效数据、方向、旋转、关闭和暂停恢复。无需因当前 HTTP 继续重复倾斜测试。
2. STEP-012／017／AC208、AC214：在原支持环境核对真实麦克风、接通声音、静音／结束等控制及场景组合暂停；微信语音支持范围沿用原规则。
3. STEP-013／015／AC210：真机量测后确定像素预算、统计／降级窗口及最低帧率，接入正式配置，再验证同页保持和新页重评；现有机制和量测工具可直接使用。
4. STEP-014／016／017／AC215、AC211—213、AC206：核对实际 HTTPS／外层缓存、四类真机的最终素材／键盘／手势／布局，以及同设备新旧性能和冷／缓存／刷新记录。没有旧版基线时只报告绝对数据。
5. 补齐受影响证据或修改代码后，按实际影响更新契约／回归和本节状态，再进行最终契约闸门判定；不重做仍有效的 M5 文档工作。当前交接为 `CONTRACT_VERIFICATION_READY`，最终闸门 `NOT_REACHED`，没有生产发布。

### 9.18 本地 Docker 更新生效（2026-10-03）

USER_DECISION：用户要求“更新一下项目在本地 docker 上”。定位现有 Compose 项目 `lxm_for`，实际使用 `docker-compose.yml` 与 `docker-compose.voice-local.yml`。Nginx 和后端均只读挂载当前工作区 frontend，Nginx 同时挂载当前 nginx.conf；本轮变更无需重建后端镜像。对 `lxm_nginx` 执行 `nginx -t` 成功后平滑 reload，前端源码和最新配置在本地 Docker 生效。数据库、Redis、其他项目容器及原本机端口绑定未修改。

RUNTIME：从 `http://127.0.0.1` 读取首页、共享 API JS、首页专用模块及图片共 23 项，全部 HTTP 200 且响应字节与工作区完全一致；首页／专用模块 no-cache、内容摘要图片 immutable 符合配置。经同一 Nginx 入口只读验证公共 persona 与 Feed 返回 HTTP 200／code=0，未登录请求关系状态返回预期 401，见 [local-docker-update.json](execution/evidence/home-m5/local-docker-update.json)。

应用浏览器打开 `http://127.0.0.1/pages/index.html`，核对遮罩已移除、主内容可见、dynamic 场景七图加载、人物按钮可用，并实际显示本地后端公共 Feed；未登录为真实访客态，没有模拟登录标识。未执行账号登录、写请求或真实通话。原 `54323` 独立模拟预览仍供界面验收使用，不是 Docker 业务入口。本次仅本地生效，不改变 §9.17 的延期验收及最终闸门状态。

### 9.19 Docker 同 Wi-Fi 手机入口（2026-10-03）

USER_DECISION：用户希望同一网络下用手机访问 Docker 并登录，同时要求不要占用其他项目端口。新增独立本地覆盖文件 `docker-compose.lan-local.yml`，叠加在现有基础与 voice-local 配置之后；仅重建 `lxm_nginx`。电脑原 `127.0.0.1:80` 保留，最终手机入口为 `http://192.168.1.3:54324/pages/index.html`，反向代理现有本地真实后端，使用本地环境账号登录。

端口核对：新增前宿主机和已发布 Docker 端口均未使用 54324；另核对两个其他运行 Compose 项目的端口配置，未发现 54324 配置。临时测试用过的 8080 已从本项目释放。最终 Docker 实际仅绑定 `127.0.0.1:80` 与 `192.168.1.3:54324` 到 Nginx 80；后端直连仍为 `127.0.0.1:8000`，其他容器、数据库和项目配置未修改。

RUNTIME：通过最终 LAN 地址核对首页、登录页和三个脚本，5 项均 200 且响应字节与当前源码一致；公共 Feed／persona 为 200／code=0，未登录私有关系接口为预期 401。以 GET 只读探测登录路由，收到预期 405／Allow POST，确认请求到达真实登录接口，未提交凭据或代用户登录。电脑原入口仍 200。见 [local-docker-lan.json](execution/evidence/home-m5/local-docker-lan.json)。这是电脑经实际 LAN 地址访问的证据，手机端结果仍待用户操作，未推定路由器客户端隔离不存在。

启动时显式设置当前 Wi-Fi IP：`LXM_LAN_IP=192.168.1.3 docker compose -f docker-compose.yml -f docker-compose.voice-local.yml -f docker-compose.lan-local.yml up -d --no-deps --no-build nginx`。IP 变化后以新值重建；覆盖文件包含恢复仅本机入口的命令。HTTP 可访问页面和普通账号登录；倾斜和手机麦克风仍按安全上下文要求待 HTTPS 验收，§9.17 未测项保持。`54323` 继续是独立模拟预览，不与 Docker 新入口混用。

### 9.20 本轮开发交付与正式服发布准备（2026-10-03）

**USER_DECISION**：用户说明只有正式服具备 SSL 证书，最初要求发布线上，并询问本版本是否可以收口；收到部署入口问题后，最新明确“暂时不需要你来推”。本次已准备主页前端增量候选，随后停止代推范围，发布另行安排。本轮按主要功能开发交付收口，Q201 正式参数配置和真实环境验收继续列为剩余项。用户没有撤销原验收标准，本节不将 STEP-011—018 或最终闸门改为通过。

**后续实现与证据归并**：当前实现和 H5 契约已将主页动效、倾斜开关移至设置页，主页“更多互动”恢复登录后的“敬请期待”；倾斜选择在当前标签页 Session 内保持，并有存储异常、迟到授权及 bfcache 恢复保护。相关既有验证见 [偏好设置](../../../reports/home-motion-settings/results.json)、[倾斜设置](../../../reports/home-motion-settings/tilt-settings-results.json)、[组合存储异常](../../../reports/home-motion-settings/preference-failure-results.json) 和 [人物稳定性](../../../reports/home-motion-settings/character-stability-results.json)。本次核对后两份证据中的 5 个、3 个生产文件摘要均与当前源码一致；复用其受控桌面结果，不改写为本轮重新执行或真机通过。§9.17 原增量映射中的“更多面板”和每页默认关闭是当时快照，最新行为以当前 H5 契约的设置页偏好／主动倾斜条款为准。

**本次发布前验证**：19 项静态契约 pytest 通过；对当前源码重新执行 53 项主页保留数据／入口场景，全部通过，见 [release-preserved-results.json](execution/evidence/home-m5/release-preserved-results.json)。5 个 JS 文件及首页／设置页共 4 个内联脚本语法通过，`git diff --check` 通过。这些是本地桌面及受控 API 验证，不代替真实账号、手机传感器、声音或部署验收。

**发布候选**：已在本机生成包含 25 个前端文件的增量包，附发布清单、缓存配置片段及备份／回滚说明；包内逐文件摘要和 17 张内容摘要图片校验通过。完整清单与临时包位置见 [production-release-candidate.json](execution/evidence/home-m5/production-release-candidate.json)。不包含后端、数据库、密钥、本地 Compose／端口覆盖、模拟预览或含本机源路径的素材构建 manifest。Nginx 仅提供缓存片段供核对现网后合并，不以本地 HTTP 配置覆盖正式 SSL、端口或既有代理路由。

**运行事实与恢复点**：状态 `PREPARED_NOT_DEPLOYED`，本轮代推已按用户最新决定停止，不再等待部署入口或自动发布。用户随后提供正式域名 `cllxm.com`，并再次明确不需要代为上传；本轮未访问验证该域名、没有连接或修改正式服，也未改变本地及其他项目端口。后续重新安排发布时，需核对该域名的正式 HTTPS 页面路径、发布入口、目标目录、线上基础版本与共享 api.js 兼容性、备份及回滚目标；验证 HTTPS 响应／缓存／文件摘要后，再补真实手机倾斜、语音、布局／输入和性能量测。自动降级机制仍未配置 Q201 正式参数，不把这一配置缺口写成单纯待验。最终契约闸门仍 `NOT_REACHED`。
