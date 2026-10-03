---
title: "林小梦主页改版 v2 STEP 草稿"
mode: "standalone"
phase_status: "draft"
phase_result: "PASS_WITH_RISKS"
implementation_status: "NOT_STARTED"
updated: "2026-10-02"
prd: "PRD-林小梦主页改版-v2.md"
---

# 林小梦主页改版 v2 STEP 草稿

输入为 [当前 v2 PRD](PRD-林小梦主页改版-v2.md)（`existing`、`PRD`、SRC-01），六项确认已闭合。本轮实际读取了必要主页代码、共享请求、语音接点、测试和当前契约；阶段结果为 **PASS_WITH_RISKS**。本文件只供文档级拆解和后续复审，尚未通过 `step-doc-review`，不是正式执行计划；没有实施功能、压缩素材、运行功能验收或发布。

共 18 个 STEP：15 个 `draft`，STEP-014／STEP-015／STEP-016 因实际部署环境与真机测量口径尚未核实保持 `provisional`。Q201—Q203 是事实和实测门，不是重新打开已确认的产品选择。`provisional` 项的关键环境事实未补齐前不得作为正式可执行计划；其余草稿同样须经过完整 STEP 复审。

进度保留在本文件内。拆解前 home-redesign 的当前记录是 v2 PRD 和已结束的确认过程草案，旧 STEP／进度已归档；本轮没有建立第二份当前进度记录，也没有读取旧稿或迁移基线。

## 1. 来源摘要与事实边界

来源标签只使用 `USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`、`PLANNED`、`UNVERIFIED`。PRD 中已记录的用户选择仍标 `PRD`；本轮唯一新增的 `USER_DECISION` 是“使用 prd-to-steps 拆解此 v2 PRD”，未新增业务决定。本轮没有 `RUNTIME` 浏览器、真机或部署证据。

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

本文件输出路径 `docs/design/home-redesign/steps-draft.md` 为本阶段 `planned` 文档产物，保存后成为 `existing` 输出；路径来自该技能约定和当前 PRD 所在目录。新增行为测试位置／运行环境等未在 PRD 指定的实现细节只标 `PLANNED`，按已核实的项目约定确定，不补造内部 API、业务字段、错误码或存储键。

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
| CSTR-08 | 装饰层不抢事件；业务按钮、卡片、弹窗和语音面板优先；保持正常手势、缩放与键盘，不照搬全场景 touch-action:none。 | §5.3 | STEP-003、STEP-009、STEP-010、STEP-011、STEP-012 |
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
| STEP-017 | 回归保留的主页能力 | draft | STEP-002、STEP-003、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | F212、RQ-01、RQ-05 | AC214 |
| STEP-018 | 同步真实契约并收口追踪记录 | draft | STEP-001、STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 | F212 | AC216 |

## 4. 需求与验收覆盖映射

映射只列直接实现、独立子条款或直接验收责任。共享 AC 在正文中明确拆分，任何一个子 STEP 的完成都不等于整个原 AC 完成；全部子条款及要求的环境证据齐备后才可汇总。

| 需求 ID | 直接承担 STEP／子条款 |
|---|---|
| F201 | STEP-003：背景＋完整人物的基础画面及可选层缺失时的静态保底；STEP-004：核心图失败／挂起后的有界等待；STEP-008：全部可选场景动效与失败保留基础画面 |
| F202 | STEP-003：共用坐标变换、小屏／短屏／桌面与旋转适配 |
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
| AC206 | 访客/已登录用户分别点击人物、更多、卡片和 CTA，并使用键盘；人物只做本地反馈，业务入口优先；访客门禁正确；登录后不自动重放或请求传感器权限 | STEP-009：人物反馈、业务控件优先及键盘子条款；更多门禁由 STEP-010 负责；STEP-010：更多访客门禁、登录不重放／不自动请求权限子条款 |
| AC207 | 真机允许/拒绝倾斜，模拟无数据、不支持、非安全环境，关闭并旋转屏幕；实际状态与开关一致；关闭移除监听；无重复授权；有效恢复后方向正确 | STEP-011：真机允许／拒绝／无数据／不支持／不安全环境／关闭／旋转 |
| AC208 | 切后台、往返页面、开关登录/语音面板、切换动态及系统减少动态效果；多个暂停原因互不覆盖；无后台场景循环与传感器监听；恢复无跳变、闭眼残留或重复实例；同一页面暂停恢复不重置降级档位 | STEP-007：页面隐藏／返回、原因集合与幂等恢复子条款；具体动作／面板／传感器由对应 STEP 接入；STEP-008：动作暂停恢复、无跳变／闭眼残留子条款；STEP-010：动态开关与系统减少动态暂停子条款；STEP-011：暂停期间无传感器监听，合法恢复子条款；STEP-012：登录／语音面板组合暂停、恢复与无重复实例子条款；STEP-013：后台／面板／bfcache 恢复不重置质量子条款 |
| AC209 | 禁用 Canvas 或可选 API，制造特效初始化错误；静态画面与业务入口可用；不存在异常引发的整页中断 | STEP-003：场景能力缺失时的静态保底子条款；STEP-007：可选 API 与初始化异常隔离子条款；STEP-008：动效初始化／可选能力故障隔离子条款 |
| AC210 | 在列明的设备上记录新旧主页持续运行与低档表现，制造掉帧并恢复、刷新或全新打开；记录帧率、长任务、点击响应和内存趋势；掉帧按顺序降级，同一页面不自动升档；刷新或全新打开重新评估；达到经 Q201 确定环境下的目标 | STEP-013：质量策略、调度指标与同页保持／新实例重评子条款；真机目标测量由 STEP-015 联合负责；STEP-015：帧率、长任务、点击、内存和 Q201 目标的真实测量；策略由 STEP-013 联合负责 |
| AC211 | 在 375×667、390×844、430×932、1280×720 及横竖屏下检查；人脸与入口可见、贴片一致，底部内容可操作，安全区和正常页面手势可用 | STEP-003：指定尺寸、旋转、安全区和卡片变化时的构图／手势 |
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

> 返回 STEP-001、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-002、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-003、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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
| `frontend/pages/index.html` | existing | REPO_BASELINE | SRC-04／frontend/pages/index.html::HOME_LOADER_KEY@1481；preloadImage@1534；dismissHomeLoader@1646；runHomeLoader@1687；initHomePage@1769 | 主页结构、加载门闩、权限入口、页面取数与 Feed 刷新 |
| `frontend/static/js/api.js` | existing | REPO_BASELINE | SRC-05／frontend/static/js/api.js::clearToken@146 | 共享请求、鉴权、登录弹窗、情绪头像与格式化 |
| `frontend/static/js/home-scene.js` | planned | PLANNED | 不适用 | PRD §9.1；场景资源、调度、生命周期与传感器 |

**输入**：
- STEP-003 可用静态场景；当前加载文案、Session 语义及 PRD 的精确时序。

**输出**：
- 有截止、幂等、可恢复的加载流程和可由晚加载模块读取的启动状态。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 正常时序 | 最短 3000ms、完成后停留 500ms、退出 550ms；即时就绪约 4.05 秒。 | §5.1、V2-D04 |
| 截止 | 核心下载及可用解码最多等待 5 秒；本次启动遮罩 8 秒兜底，恢复前台先检查绝对截止。 | §5.1、AC203 |
| Session | 同标签非刷新跳过；刷新／clearToken 保持原语义，跳过也初始化场景和数据。 | §5.1 |

**开发任务**：
1. 以背景＋人物为核心准备，不把 API、情绪头像或可选特效纳入完成门闩；加载页复用核心资源，不另下载大海报。
2. 记录启动与截止时刻，正常退出和异常兜底均幂等；pagehide 后恢复能检查过期时刻，迟到结果不会重建遮罩。
3. 让页面结构／入口可独立显示；后加载的场景模块读取当前阶段，不只订阅一次事件。
4. 保留品牌文案、完成提示与 Session key；去除进度驱动的持续大面积滤镜，减少动态时取消对应过渡。
5. 协调当前数据入口保持初始化一次；模块级数据失败／并发保护由 STEP-006 接入。

**不在本 STEP 范围内**：
- 修改展示节奏以追求测速；场景动作实现；不把进度 100% 当成所有业务数据成功。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 所有核心资源即时可用，API 与可选层仍在等待 | 遵守 3000/500/550ms 节奏，约 4.05 秒退出；API 与可选层不延长等待。 | AC202、AC213 |
| 异常 | 核心坏图／解码不完成／请求挂起，前台计时正常执行 | 核心 5 秒截止，遮罩最迟 8 秒直接释放；入口可用，迟到结果不再遮挡。 | AC203 |
| 边界 | 刷新、同标签返回、存储抛错、模块晚加载、隐藏后超过截止再返回 | 跳过仍初始化基础场景和数据；恢复按截止处理，无重复退出／挂载，存储错误不阻断。 | AC202、AC203 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-004、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-005、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-006、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-007、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-008、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-009、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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
4. 处理系统减少动态变化与存储抛错；UI 分开表达用户选择和实际允许运行状态，不把系统抑制显示为动态已运行。

**不在本 STEP 范围内**：
- 账号同步、设备同步、记住倾斜开启意图跨新页面；不重放触发登录的原操作。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 登录用户修改动态并刷新、再次访问、切换账号 | 当前浏览器保留选择，新页面初始化即遵守；不同设备独立，无账号同步。 | AC217 |
| 异常 | 访客点击更多，登录／取消；存储读写抛错 | 沿用共享弹窗；登录不自动打开原动作或申请权限，存储异常不阻断页面。 | AC206、AC217 |
| 边界 | 系统减少动态切换，多暂停原因叠加，关闭后再开启动态 | 系统优先；其他原因仍存在不恢复；开启动态不自动弹传感器授权。 | AC208、AC217 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-010、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-011、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-012、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-013、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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
5. 本草稿不授权生产发布；先准备测试环境配置与证据，真实发布在有相应授权的执行阶段完成。

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

> 返回 STEP-014、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-015、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-016、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

### [STEP-017] 回归保留的主页能力

**阶段状态**：`draft`；实施状态 `NOT_STARTED`。

**目标**：在首版验收环境内证明当前主页入口、权限和数据语义在新场景上保持。

**来源映射**：

| 类型 | ID | 原文短引／本 STEP 准确责任 | 来源 |
|---|---|---|---|
| 需求 ID | F212 | 原文：保留 §4 全部入口、数据及权限语义，复核静态契约与真实用户流程，实施完成时同步当前 H5 契约；本 STEP：§4 全部入口、数据与权限的用户可观察回归 | PRD／SRC-01 |
| 需求 ID | RQ-01 | 原文：保留布局与入口，接入 demo 场景；本 STEP：当前主页布局与入口保留的回归部分 | PRD／SRC-01 |
| 需求 ID | RQ-05 | 原文：首版设备与浏览器验收范围；本 STEP：首版设备与浏览器的保留能力验收 | PRD／SRC-01 |
| 验收 ID | AC214 | 原预期：设置、关系、记忆、Feed、日记、聊天和真实语音入口符合当前规则；声音链路不被场景占用影响；本 STEP：完整主页保留能力与真实语音入口／声音链路 | PRD／SRC-01 |

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
- 前置功能 STEP 的集成产物；当前契约和 §4 规则；已列明四类浏览器环境、可用测试账号／语音条件。

**输出**：
- 当前业务入口和保留语义的用户流程证据，以及明确未验证的环境／链路清单。

**业务定义**：

| 名称 | 定义 | 来源 |
|---|---|---|
| 入口 | 头像→设置；关系／日记走门禁；记忆→memory；Feed 保留未读定位；CTA→chat；视频／入睡仍为原占位。 | §4.1 |
| 数据 | 四级关系、进度／满级、known_days、状态语、日记固定句／相对时间／NEW／真实 Lv0 锁保持。 | §4.1 |
| 时段 | 北京时间七时段与 Good night 条件不变；原 Hero 装饰语义保持。 | §4.1 |
| 语音 | VoiceEntry.begin 与原兼容策略保持；微信仍按当前策略提示不可用，不新增语音支持承诺。 | §4.1、§8、REPO_BASELINE SRC-06 |

**开发任务**：
1. 访客／登录各执行设置、关系、更多、记忆、Feed、日记、CTA 与语音入口；核对公共 Feed、私有门禁及单次登录恢复、不重放。
2. 按 §4 检查关系数值、陪伴天数、头像／状态语、日记 NEW／锁与相对时间、Feed 更新时间和未读定位；未知／失败不假装真实 Lv0 或空态。
3. 检查七时段、24 小时时钟、Good night 和 CTA 文案；不通过代码重排卡片规避新场景遮脸问题。
4. 在原支持且实际可用的语音测试环境确认场景暂停与声音链路；微信核对原不可用提示。受控传输和真实声音分开记录。
5. 完成有影响的静态及真实用户流程回归；未有真机／语音条件时记录缺口，不以静态字符串通过推定完整 AC214。

**不在本 STEP 范围内**：
- 关系算法、视频／入睡、子页权限、微信语音新支持；不重结算历史技术债。

**测试与验收**：

| 场景 | 输入／前提 | 预期结果 | 对应验收 ID |
|---|---|---|---|
| 正常 | 四浏览器中分别访客／登录逐一操作 §4 入口和数据场景 | 当前路径、数据、门禁及文案保持；登录恢复一次，不重放原操作。 | AC214 |
| 异常 | 有效 401、数据失败／未知、语音不支持或无法接通 | 按当前策略降级／提示；不会误锁为真实 Lv0，不改变语音兼容承诺。 | AC214 |
| 边界 | 满级、真实 Lv0、NEW、七时段边界、Feed 未读定位、真实可用语音 | 各既有语义及声音链路可观察正确；缺少声音或设备证据不能报整体通过。 | AC214 |

**完成标志**：

- [ ] 本 STEP 直接负责的全部验收子条款有证据；共享 AC 的其他部分仍按映射追踪。
- [ ] 已核对实际用户行为及所需环境，未测／模拟／真实范围分开记录。
- [ ] 未改变其他 STEP 的范围或有效需求，相关测试以 PRD／契约为预期。
- [ ] 新发现的路径、符号、环境与契约事实已更新状态；关键未核实项已关闭或明确阻断。
- [ ] 本文件 §9 进度已回传变更文件、证据与下一恢复位置。

**完成回传**：

> 返回 STEP-017、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

> 返回 STEP-018、完成／阻断状态、对应需求／验收子条款、验证环境和证据、变更文件、来源变化、未测项及按依赖下一可执行 STEP。不得自动启动下一 STEP，不得把本草稿当已审查执行计划。

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

## 8. 自检与阶段结果

- [x] 12 个 F、6 个 RQ、5 个 G、14 个 V2-D、17 个 CSTR 和 17 个 AC 全部有映射。
- [x] 18 个 STEP 均有单一目标、至少一项直接需求／验收、显式依赖及正常／异常／边界场景。
- [x] 依赖图无环，未依赖不存在的 STEP；共享 AC 子条款及共同完成规则已写明。
- [x] 没有新增业务字段、错误码、权限值、优先级或存储键；未使用自定义标签补造需求。
- [x] 路径／符号分为 existing、planned、unverified；existing 绑定本轮实际文件与 locator。
- [x] 当前代码和契约已实际读取；关键环境未核实项留在 provisional／发现门，没有表述为可执行事实。
- [x] 功能、压缩文件、真机、部署和发布均未实施，本文件不宣称 STEP 已复审或功能已验收。
- [x] 没有生成里程碑计划、已复审 STEP 文档或自动进入下一技能阶段。

**阶段结果：`PASS_WITH_RISKS`**。本结果只说明拆解草稿的结构、来源和覆盖自检通过，不能替代 `step-doc-review`。本 standalone 阶段在保存此文档后结束。

## 9. 林小梦主页改版 v2 STEP 进度

> 路径：本文件内嵌进度区块。
> PRD 来源：`PRD-林小梦主页改版-v2.md`（existing／PRD／SRC-01）。
> STEP 来源：`steps-draft.md`（本阶段输出）。
> 当前阶段结果：`PASS_WITH_RISKS`。

### 9.1 进度总览

| 完成数 | 总数 | 当前状态 |
|---|---|---|
| 0 | 18 | NOT_STARTED |

### 9.2 STEP 明细

| STEP | 功能名称 | 需求 ID | 验收 ID | 前置 STEP | 状态 | 证据 |
|---|---|---|---|---|---|---|
| STEP-001 | 导出场景七图素材 | F210 | AC212 | 无 | NOT_STARTED | — |
| STEP-002 | 接入首页专用小图 | F210 | AC212、AC213 | 无 | NOT_STARTED | — |
| STEP-003 | 建立适配主页的静态场景 | F201、F202、RQ-01 | AC201、AC203、AC209、AC211 | STEP-001 | NOT_STARTED | — |
| STEP-004 | 实现有截止的加载遮罩 | F203、F201、RQ-02 | AC202、AC203、AC213 | STEP-003 | NOT_STARTED | — |
| STEP-005 | 给共享请求增加可选取消和失效保护 | F204、F212、RQ-02 | AC205 | 无 | NOT_STARTED | — |
| STEP-006 | 实现主页独立显示和有界数据批次 | F204、F203、RQ-02 | AC204、AC205、AC202 | STEP-004、STEP-005 | NOT_STARTED | — |
| STEP-007 | 建立场景统一生命周期 | F208、F209 | AC208、AC209、AC202 | STEP-004 | NOT_STARTED | — |
| STEP-008 | 接入渐进场景动效 | F201、F208、RQ-01 | AC201、AC208、AC209 | STEP-001、STEP-003、STEP-007 | NOT_STARTED | — |
| STEP-009 | 实现人物本地回应 | F205、RQ-01、RQ-03 | AC201、AC206 | STEP-003、STEP-007、STEP-008 | NOT_STARTED | — |
| STEP-010 | 在更多互动保存主页动态偏好 | F206、RQ-03、RQ-04 | AC206、AC217、AC208 | STEP-007、STEP-008 | NOT_STARTED | — |
| STEP-011 | 实现主动授权的倾斜视差 | F207、F206、F208、RQ-03、RQ-05 | AC207、AC217、AC208 | STEP-003、STEP-007、STEP-008、STEP-010 | NOT_STARTED | — |
| STEP-012 | 适配登录和语音面板暂停 | F208、F212 | AC208、AC214 | STEP-007、STEP-008、STEP-011 | NOT_STARTED | — |
| STEP-013 | 优化调度并保持自动降级档位 | F209、F208、RQ-06 | AC210、AC208 | STEP-003、STEP-007、STEP-008、STEP-010、STEP-011、STEP-012 | NOT_STARTED | — |
| STEP-014 | 验证版本化缓存与旧场景回退 | F211、RQ-05 | AC215、AC213 | STEP-002、STEP-004、STEP-006、STEP-008、STEP-013 | NOT_STARTED | — |
| STEP-015 | 实测持续运行性能 | F209、RQ-05 | AC210 | STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | NOT_STARTED | — |
| STEP-016 | 实测加载与素材传输 | F203、F210、F211、RQ-05 | AC212、AC213 | STEP-001、STEP-002、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | NOT_STARTED | — |
| STEP-017 | 回归保留的主页能力 | F212、RQ-01、RQ-05 | AC214 | STEP-002、STEP-003、STEP-004、STEP-006、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014 | NOT_STARTED | — |
| STEP-018 | 同步真实契约并收口追踪记录 | F212 | AC216 | STEP-001、STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 | NOT_STARTED | — |

状态只使用 `NOT_STARTED`、`IN_PROGRESS`、`DONE`、`BLOCKED`；阶段状态 draft／provisional 与实施状态分开。只有本 STEP 全部完成标志有证据才能标 DONE，当前文档级风险不等于已开始执行或实施阻断。

### 9.3 阻断与来源变化

| 日期 | STEP | 类型 | 证据或变化 | 处理结果 |
|---|---|---|---|---|
| 2026-10-02 | STEP-014 | REPO_BASELINE 补充 | 实际文件名 Index.png 与主页 index.png 引用大小写不一致 | 已加入兼容核对；没有修改 PRD 或代码 |
| 2026-10-02 | STEP-014／STEP-015／STEP-016 | UNVERIFIED 环境 | 真实部署／真机口径仍需发现 | 阶段 provisional，实施仍 NOT_STARTED；不是产品未决项 |

当前恢复位置：本阶段草稿拆解已完成，等待完整 STEP 文档复审；尚未进入任何实施 STEP。若后续获准执行已复审计划，按显式依赖检查输入及 Q201—Q203 门，不能直接按本文件编号自动开发。
