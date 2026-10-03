---
mode: standalone
review_mode: review-repair
phase_result: PASS_WITH_RISKS
handoff_state: STEPS_VERIFIED
implementation_status: NOT_STARTED
updated: 2026-10-02
source_digest: 32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c
original_step: steps-draft.md
candidate_step: steps-candidate-r1.md
verified_step: steps-verified.md
---

# step-audit

两项文档发现均已修复并完成完整复审：**PASS_WITH_RISKS，状态 STEPS_VERIFIED**。当前权威版为 [steps-verified.md](steps-verified.md)，第 1 轮修复输入快照为 [steps-candidate-r1.md](steps-candidate-r1.md)。18 个 STEP、71 个有效 ID 与 74 条依赖边已核对，原需求、业务范围和权限语义保持。

本轮延续用户直接调用 `$step-doc-review`，并根据明确回复“两项都补齐（推荐）”进入 `standalone / review-repair`。`execute-approved-work` 统一写候选，仅交付 STEP_REVIEW_READY；本 Skill 完整复审后签发验证版。本审计为唯一当前记录，保留首次发现、修复授权、逐项 Diff 和复审依据。

原 [steps-draft.md](steps-draft.md)、[v2 PRD](PRD-林小梦主页改版-v2.md)、代码及素材未改，功能实施仍 **NOT_STARTED（0/18）**。Q201—Q203 和运行环境仍按停止门处理；文档通过不表示功能、真机性能、素材质量、声音链路或部署验收完成。

## 1. 有效来源与新鲜度

事实优先级为 `USER_DECISION → PRD → CONTRACT → REPO_BASELINE → 项目规范 → 派生 STEP/报告`。六项既有产品选择继续有效，未新增或重新打开业务决定。最新 `USER_DECISION` 为用户对“补齐2”的范围澄清回答：**“两项都补齐（推荐）”**，授权 SDR-V2-R1-001、SDR-V2-R1-002 的已限定文档修复，不授权业务实施或发布。

首次 review-only 审查已读取原 PRD、完整 18 个 STEP 及必要契约／代码；登记时间 `2026-10-02T07:31:32.042632+00:00`，写初审前 `2026-10-02T07:40:41.457192+00:00` 全部摘要不变。首次结论 FAILED_VALIDATION／REPAIR_REQUIRED 保留在 §2 与 §4。首次 28 个来源摘要为 `25200936558d518ec81078c4466749c8f3712ad470b10d60a52f1a31efa13af5`，输入审计快照 SHA-256 为 `a69155a8bd3569b0b3a69cac71adfa31f2e98dd30098cfb5d215d22ca30f8b8a`。

本轮完整复审从当前原始来源重新核对全部候选的来源／依赖／输入输出／定义／任务／排除项／用例／完成标志及追踪区，不只检查 Diff。候选独立校验时间 `2026-10-02T08:04:58.270911+00:00` 至 `2026-10-02T08:04:58.293140+00:00`；生成验证版前于 `2026-10-02T08:21:08.475611+00:00` 逐文件重算，下表全部 29 个来源与复审输入一致，原有 28 个来源未变化。

当前 `source_digest = 32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c`；它包含原 28 个来源和本轮候选，摘要变化来自增加候选输入，不能解释为 PRD／契约／代码换版。算法：SHA256(UTF-8，按绝对路径排序，每行 absolute_path + TAB + sha256 + LF)。审计与验证版是输出，不纳入自身输入摘要；验证版摘要在 §8 单独记录。下表是唯一来源清单，引用 source_id 即引用完整摘要，符号／标题／ID 为稳定定位，行号仅辅助。

| source_id | 路径 | 来源 | 本轮定位／读取范围 | 完整 SHA-256 |
|---|---|---|---|---|
| SRC-01 | `docs/design/home-redesign/PRD-林小梦主页改版-v2.md` | PRD | §3—§9；F201—F212、AC201—AC217 | `165e84076e14016073e92b4c2284a0ada52321fe8c6d753061ceda81e4ce9ed6` |
| SRC-02 | `docs/contract/current/h5-app/api.md` | CONTRACT | §H5 认证与页面访问策略（26—81 行） | `bf727722686bf983fb2e36d4976ae98f5aa3f723327f7787bcbc121c9b0c0fef` |
| SRC-03 | `docs/contract/current/_shared/conventions.md` | CONTRACT | §统一说明／字段命名规范（10—26 行） | `9ae6b47a846bbcdbb74a1ff5133900ebf794bf4acff4638c74f1d8d82ae4e388` |
| SRC-04 | `frontend/pages/index.html` | REPO_BASELINE | DOM 1250—1477；加载 1481—1787；渲染 1791—2004；取数 2098—2273 | `7009f8fa634bcc085aeaed9885c53677f7ea5cb9a00569158c237968576afa7a` |
| SRC-05 | `frontend/static/js/api.js` | REPO_BASELINE | request@83；handleUnauthorized@111；openLoginModal@353；updateAvatarEmotion@615 | `6bf271e53a7b1911d7cdc45c3ec7e96d21711a91f1803e392740b882f495118e` |
| SRC-06 | `frontend/static/js/voice-entry.js` | REPO_BASELINE | elements@60；show@119；begin@401；close@473；pageshow@467 | `ac355a96679f3263020f2e06da9997ad6c0359949ef02f342f7f68a2817baf22` |
| SRC-07 | `frontend/static/css/voice-entry.css` | REPO_BASELINE | 旧背景 URL 第 2、21 行 | `a4d106cfd86368f32884ae1d9d078e24ae23895415df76bc27d3c22e63b8ee0b` |
| SRC-08 | `nginx/nginx.conf` | REPO_BASELINE | server／location（27—81 行） | `1f53e0b85c09bc01f90ac17d93a9683ddf24454f808d2bd5eea74ef3b98b23b5` |
| SRC-09 | `tests/test_h5_static_contract.py` | REPO_BASELINE | 文件说明@1；test_index_html_home_surface_contract@407；test_index_guest_mode_contract@483 | `21dec126aab8a46377c7c99c8a828fdb924110de59746437689b1b6512c59c56` |
| SRC-10 | `requirements.txt` | REPO_BASELINE | Pillow@48；pytest@52；pytest-asyncio@53 | `79d5196a84c651e963e24065cd17547244bd72dc8a6a69147ee41c0ba5720238` |
| SRC-11 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/app.js` | REPO_BASELINE | renderParallax@89；enableTilt@130；scheduleBlink@182；acknowledge@227；启动循环@416—437 | `a6bb07bfc2be6a3011741912c8b293b2d03701b4819ab86cad27679c40c4900d` |
| SRC-12 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/idle-core.js` | REPO_BASELINE | normalizeOrientation@48；createBlinkPlan@58；createAcknowledgePlan@80 | `d9eb388f8ce10250f8aa6d0a241d191043870d18b0d1d5ccfd580c302d480d8e` |
| SRC-13 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/styles.css` | REPO_BASELINE | scene@4；hair-front/side/back@22—24；blink@26 | `959a10405861a7e81130d19a38673248e0cc03fe191016b86ba8dbf3c253142a` |
| SRC-14 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/index.html` | REPO_BASELINE | 分层素材 DOM | `c59d82c2f5da6ac0e8c37dcad79d7db06fc6a05b40f7ecf88f890b108efdf348` |
| SRC-15 | `tests/test_realtime_voice_step036_states.cjs` | REPO_BASELINE | Playwright 导入@3；setup@38；page.route@50 | `bb93e2b1b10e3f43fd8b4b99bb3c81990b011d2e0f5e74f100f8bd27483a1b8d` |
| SRC-16 | `docs/INDEX.md` | REPO_BASELINE | §产品需求与设计 | `179cf230fc39f73ac8cb58b7d21181f8a91fc8ec1c61c9af39491e38569ccafa` |
| SRC-17 | `docs/llm-manifest.json` | REPO_BASELINE | documents 中 contract-h5-app-api／contract-shared-conventions | `15819acc2ae0300566e6d633c521c412395dd8ac8e5bb946e1e714439d32b362` |
| ASSET-01 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/background.webp` | REPO_BASELINE | 文件头／元数据：853×1844、RGB、165630 字节 | `c094490a4d8eb789299af8d04ddce8eed7454f9c43c9d2e28a8bb40b500ad1aa` |
| ASSET-02 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/character.webp` | REPO_BASELINE | 文件头／元数据：853×1844、RGBA、284604 字节 | `2816096f87aaae6cd49b80065186eeadea240b2b2ab12482ee4879ad44a0dfb4` |
| ASSET-03 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_front_physics.png` | REPO_BASELINE | 文件头／元数据：456×417、RGBA、358769 字节 | `b1e1d3d8534d6ad77a6960949c07097a8b20765e558977abfdb4ae5140790db2` |
| ASSET-04 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_side_physics.png` | REPO_BASELINE | 文件头／元数据：220×512、RGBA、120267 字节 | `c1aa3d65e058f37a93c0cb8d897c07ac3ca85d17f5907e8019270acb8eed4c0a` |
| ASSET-05 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/hair_back_physics.png` | REPO_BASELINE | 文件头／元数据：168×445、RGBA、146555 字节 | `cb856237a6f68ee69e52d1b7c26dbe1c0cfd1eec8ab317f51588dcc3eac3fdab` |
| ASSET-06 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/blink_crop.png` | REPO_BASELINE | 文件头／元数据：263×134、RGBA、70797 字节 | `3365f66905d34fe4a9d1e5beb038525c1cfcf18b2e1e40d90cdaac5207f6c75a` |
| ASSET-07 | `/Users/umark/Desktop/lxm-tm/lxm-4/主页改版/lxm_idle_demo_v4/assets/lamp_glow.webp` | REPO_BASELINE | 文件头／元数据：853×1844、RGBA、140176 字节 | `a1425ca6fb0adbcf0bd6128f0dc5f3d376b91e0cb0fe8da0d58d940cd027bf1f` |
| ASSET-08 | `frontend/static/images/Index/Index.png` | REPO_BASELINE | 精确目录名 Index.png；550814 字节 | `0b072904c320b7f93e6472c851db621e6f3cadf8235ebd465f47695ad48bd2c0` |
| IN-STEP | `docs/design/home-redesign/steps-draft.md` | PLANNED | STEP-001—018；§2—§9 原草稿 | `e3dccbf514175800344fbfb3504cf0b7ebfdebcd20a84b8c710230d737928cab` |
| A-RULE | `AGENTS.md` | REPO_BASELINE | 协作习惯；仓库文档读取边界 | `9594e52f3ec3c8bab990fa973c3ff8a854467081df2369971800330666e642c3` |
| A-FEED | `docs/contract/current/life-feed/api.md` | CONTRACT | GET /api/feed/list、badge；当前口径：Feed 可选鉴权与访客只读态 | `d276b074794c21de5a13c10892389d043e6494464349e5912e23f4cd09c86491` |
| IN-CANDIDATE-R1 | `docs/design/home-redesign/steps-candidate-r1.md` | PLANNED | 修复候选全文；STEP-001—018，§2—§9 | `c73cc056bbf824536979a386b7439fd88384838042baba938cf9c02dcc6e9378` |

## 2. 九维首次审查（原稿历史结论）

以下为原稿首次 review-only 结果，保留发现形成的依据，不代表当前候选状态。完整候选的当前九维结果见 §8.2。

| 维度 | 状态 | 依据与结论 |
|---|---|---|
| 1. 幻觉 | PASS | 数值与顺序来自 PRD：3000/500/550ms、核心 5 秒、遮罩/批次各 8 秒、环境优先 30fps、DPR≤1.5、素材争取目标。新增模块/测试位置/设备参数有 planned/unverified 标识；未宣称新功能已完成。SRC-01、SRC-04—15。 |
| 2. 遗漏 | FAIL | 顶层 ID 齐全，已保留禁止项和契约同步；最终动效/倾斜集成后的完整视口与业务键盘验收缺明确承接，见 SDR-V2-R1-001。 |
| 3. 冲突 | PASS | 用户选择与 PRD 一致。新有效上下文判断优先于旧契约无条件清 token，STEP-005 默认兼容、STEP-018 实施后同步。四浏览器主页验收未扩大微信语音支持。未发现可测试的产品/权限矛盾。 |
| 4. 清晰度 | FAIL | 一般实现字段与测量参数可在已限定范围中确定，Q201—203 有发现门；“存储抛错”未限定存储类型、注入阶段和真实启动入口，见 SDR-V2-R1-002。 |
| 5. 依赖 | PASS | 18 节点、74 条显式边，无环/悬空/自依赖；总览、正文和进度一致。最终回归已依赖动效、倾斜、批次等集成产物，001 只需补责任与验收映射，无须添边或拆节点。 |
| 6. 可测性 | FAIL | 每 STEP 均有正常/异常/边界与 AC，加载/失效 401/暂停/真实声音等主要断言具体；001、002 尚允许局部或晚阶段用例替代完整目标检查。 |
| 7. 覆盖率 | FAIL | 71 个有效顶层 ID 均有归属，正反向集合一致；编号齐全不等于所有子条款和集成前提覆盖，缺口见 §3 与两项发现。 |
| 8. 技术债 | PASS | PRD 明示本期不新增债编号、不重结算历史；STEP 按同一边界排除，未将代码缺口升级为技术债。TD-HOME-08 只按 v2 的历史替代说明处理，不宣称旧债关闭。 |
| 9. 代码事实 | PASS | 本轮已重读 existing 路径/符号、接口使用、面板可见状态、测试性质；25 个原稿来源前缀与当前完整摘要一致。重新读取七图和旧图元数据，精确枚举只有 Index.png；未用 exists() 证明线上大小写或 HTTPS。 |

依赖的额外核对：STEP-007 可传递取得 STEP-003 静态场景；STEP-006 在 STEP-005 的共享保护后接 UI 代次；STEP-011 在 STEP-010 的控制后接权限；STEP-013 在动作、倾斜和覆盖层接入后选参；STEP-015/016 是最终测量，不把它们的未来证据当 STEP-013 已完成选参。多处传递前置被重复列出，是显式使用上游产物和最终对账的门，不构成循环，也不需要为了减少边数重写。首个主页源码改动前采集基线的门已在原稿 §5 写明，不能等到 STEP-015/016 才补。

## 3. 唯一规范化覆盖视图

本视图以当前候选为处置依据，按当前 PRD 的有效编号和未编号约束生成，每个 ID 只有一行；同一 ID 可按不同直接子条款由多个 STEP 承担，不把共同责任误算为重复需求。旧 C/N/R/K、历史 TD 与已替代项不纳入当前有效 ID 集。

| ID | 当前直接承担 STEP | 责任范围／审查结果 |
|---|---|---|
| RQ-01 | STEP-003、STEP-008、STEP-009、STEP-017 | 保留布局与入口，接入 demo 场景 |
| RQ-02 | STEP-004、STEP-005、STEP-006 | 加载截止、内容独立显示与旧请求保护 |
| RQ-03 | STEP-009、STEP-010、STEP-011 | 互动入口、访客门禁与倾斜主动授权 |
| RQ-04 | STEP-010 | 动态偏好的保存范围 |
| RQ-05 | STEP-011、STEP-014、STEP-015、STEP-016、STEP-017 | 首版设备与浏览器验收范围 |
| RQ-06 | STEP-013 | 自动降级后的恢复策略 |
| G201 | STEP-003、STEP-008、STEP-009、STEP-017 | 保留主页使用路径；现有入口、卡片、数据与权限行为保持；背景和人物交互符合 demo 的视觉方向 |
| G202 | STEP-004、STEP-006 | 加载可结束；接口或特效失败不永久遮挡页面，入口可以独立显示 |
| G203 | STEP-007、STEP-010、STEP-011、STEP-012 | 动态可控；更多互动提供开关，传感器可关闭，弹窗、通话与后台状态能正确暂停恢复 |
| G204 | STEP-001、STEP-002、STEP-016 | 降低素材传输；核心两图争取 ≤350 KiB，全套七图争取 800～900 KiB，同时通过清晰度与贴片对齐检查 |
| G205 | STEP-013、STEP-015 | 控制持续运行成本；普通手机目标接近 60fps，低档模式目标至少 30fps；持续掉帧按规则降级 |
| V2-D01 | STEP-003、STEP-017 | 布局与入口基线；保留当前生产项目主页布局、卡片和入口，以 §4 为准 |
| V2-D02 | STEP-003、STEP-008、STEP-009 | 背景与人物；替换为 demo v4 分层场景；完整静态画面优先，特效渐进增强 |
| V2-D03 | STEP-010、STEP-011 | 更多互动；增加“主页动态”和“倾斜视差”开关；沿用现有登录门禁 |
| V2-D04 | STEP-004 | 加载时序；保留正常 3000ms 最短展示、500ms 停留、550ms 退出；核心图片等待最多 5 秒，遮罩 8 秒兜底 |
| V2-D05 | STEP-006 | 业务数据；与遮罩完成解耦，首页请求批次 8 秒截止；区分未完成、失败、真实空态与访客态 |
| V2-D06 | STEP-005、STEP-006 | 并发保护；取消过期请求；写 UI 与处理 401 前检查请求代次及登录快照 |
| V2-D07 | STEP-007、STEP-008、STEP-012、STEP-013 | 性能与生命周期；单一主调度、环境特效优先 30fps、Canvas 有效 DPR 默认至多 1.5；统一暂停与降级 |
| V2-D08 | STEP-001、STEP-002 | 素材优化；优先头发和眨眼 PNG，保护透明边缘；导出首页小图，不覆盖其他页面原图 |
| V2-D09 | STEP-006、STEP-009、STEP-017 | 权限与业务；保留公共首页和交互登录；人物反馈本地执行；不增加后端接口、数据库或模型调用 |
| V2-D10 | STEP-014 | 发布与回退；新资源版本化，核对实际缓存与 HTTPS；保留旧背景及首页回退开关 |
| V2-D11 | STEP-018 | 文档与实现状态；新建 v2，保留 v1；本轮只记录，功能状态为待实施 |
| V2-D12 | STEP-010 | 动态偏好保存；当前浏览器长期保存主页动态选择，刷新、再次访问及登录切换均保留；不同设备分别设置，系统减少动态效果优先 |
| V2-D13 | STEP-011、STEP-014、STEP-015、STEP-016、STEP-017 | 首版验收范围；包含 iOS Safari、Android Chrome、iOS 微信和 Android 微信内置浏览器；具体机型与版本在验收前列明，语音沿用现有兼容策略 |
| V2-D14 | STEP-013 | 降级后恢复；同一页面实例保持降级档位；后台、弹窗和浏览器后退恢复不升档；刷新或全新打开主页时重新评估 |
| CSTR-01 | STEP-003、STEP-017 | 保留当前布局、朋友圈＋日记卡、顶栏关系、快捷栏与 CTA；不恢复旧三卡、横卡、装饰球或新增关怀位。 |
| CSTR-02 | STEP-006、STEP-017 | 关系等级、成长进度／满级算法与 milestones.known_days 沿用；失败不能当成真实 Lv0。 |
| CSTR-03 | STEP-002、STEP-004、STEP-006、STEP-017 | 状态语使用 resolveStatusText；头像情绪更新与加载专用头像职责分离；首页小图不改变其他页映射。 |
| CSTR-04 | STEP-017 | 北京时间 HH:mm 与七时段保持；Good night 仅 hour<5 或 hour>=20；装饰波形语义保持。 |
| CSTR-05 | STEP-006、STEP-017 | 日记固定句、formatTime 四档、is_read===false 的 NEW 与真实 Lv0 锁保持，点击仍走登录门禁。 |
| CSTR-06 | STEP-006、STEP-017 | Feed 公共预览、更新时间、配图、登录角标与 goFeed 未读定位保持；协调已有 visibilitychange 刷新，不额外轮询。 |
| CSTR-07 | STEP-003、STEP-005、STEP-006、STEP-009、STEP-012、STEP-017、STEP-018 | 不重排业务卡片，不开发视频／入睡，不新增模型调用、后台 API、聚合接口或数据库迁移，不改变子页业务与语音协议、音频链路、计费。 |
| CSTR-08 | STEP-003、STEP-009、STEP-010、STEP-011、STEP-012、STEP-017 | 装饰层不抢事件，保留正常手势、缩放与键盘；STEP-017 承接最终业务入口集成证据。 |
| CSTR-09 | STEP-004、STEP-005、STEP-006、STEP-007 | 保留 lxm_home_loader_done：同标签非刷新跳过，刷新及 clearToken 既有语义保持；跳过仍初始化场景和数据。 |
| CSTR-10 | STEP-004、STEP-016 | 保留加载品牌文案及完成提示；移除进度驱动的大面积模糊，用透明度过渡；减少动态时取消对应过渡，压缩不等于缩短固定展示。 |
| CSTR-11 | STEP-005、STEP-006 | 未完成、失败、真实空态、访客态分开；超时不清登录；未知关系不渲染为 Lv0 锁；旧结果不能覆盖已知数据或新 token。 |
| CSTR-12 | STEP-001、STEP-002、STEP-004、STEP-014 | 新资源版本化，HTML 不长期不可变缓存；旧图保留并核对大小写；语音旧图不重新加入首页关键预热链，加载修复可随场景回退保留。 |
| CSTR-13 | STEP-013、STEP-015 | 减少雨和星光，再停止发丝物理，仍不稳则静态；同页保持降级，刷新／新实例重评，不覆盖动态关闭或系统减少动态偏好。 |
| CSTR-14 | STEP-007、STEP-008、STEP-011、STEP-012、STEP-013 | 多暂停原因互不覆盖；清理场景 CSS／WAAPI／RAF／计时器／传感器／观察器；bfcache 暂停，幂等恢复，真正销毁释放。 |
| CSTR-15 | STEP-001、STEP-002、STEP-003、STEP-004、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017 | 首版场景、交互、加载含 iOS Safari、Android Chrome、iOS 微信、Android 微信；记录实际机型／版本／网络，个别通过不推定全体。 |
| CSTR-16 | STEP-011、STEP-015、STEP-016 | 倾斜只作为本地视觉输入；不上传或新增采集，不加埋点平台，不记录 token 或传感器原始数据；节约测算不当作账单或模型费用收益。 |
| CSTR-17 | STEP-015、STEP-016、STEP-017、STEP-018 | 文档只记录真实实现与证据；历史 K1—K7、TD-HOME-08 等不在本轮重结算，不新增技术债编号，不把 demo／静态壳／模拟结果当整体验收。 |
| F201 | STEP-003、STEP-004、STEP-008 | 静态底图、有界核心准备、可选动效与故障隔离。 |
| F202 | STEP-003、STEP-017 | 静态共用坐标与适配；最终动效／实际可用倾斜／数据高度变化后的视口、贴片与手势直接验收。 |
| F203 | STEP-004、STEP-006、STEP-016 | 正常／跳过／截止、一次初始化与真实加载测量；STEP-004 区分最早启动、Session 与启动途中存储故障。 |
| F204 | STEP-005、STEP-006 | 共享取消/401 保护与模块批次/UI 有效性。 |
| F205 | STEP-009 | 人物命中、纯本地反馈、输入合并与 UI 优先。 |
| F206 | STEP-010、STEP-011 | 更多门禁、长期动态偏好、实际倾斜状态。 |
| F207 | STEP-011 | 主动授权、有效数据、关闭与方向校准。 |
| F208 | STEP-007、STEP-008、STEP-011、STEP-012、STEP-013 | 单实例、原因集合、动作/监听/观察器、覆盖层、质量保持。 |
| F209 | STEP-007、STEP-013、STEP-015 | 主调度、成本约束、按序降级与真实持续性能。 |
| F210 | STEP-001、STEP-002、STEP-016 | 七图导出、首页派生图、最终质量/下载证据。 |
| F211 | STEP-014、STEP-016 | 版本/实际缓存/HTTPS/旧图回退及传输测量。 |
| F212 | STEP-005、STEP-012、STEP-017、STEP-018 | 默认请求兼容、语音影响、保留入口、最终点击／键盘及真实契约同步。 |
| AC201 | STEP-003、STEP-008、STEP-009 | 静态完整、动态与回应、可选失败。 |
| AC202 | STEP-004、STEP-006、STEP-007 | 确认时序、跳过与晚加载；真实 index.html 最早读取、Session get/set/remove 和途中写入故障分别注入。 |
| AC203 | STEP-003、STEP-004 | 图层保底、5 秒核心截止、前台 8 秒遮罩与迟到保护。 |
| AC204 | STEP-006 | 结构独立、真实取消、失败/空态/未知/访客区分与重试。 |
| AC205 | STEP-005、STEP-006 | 401 副作用前保护与最终 UI 代次/登录/重试去重。 |
| AC206 | STEP-009、STEP-010、STEP-017 | 人物本地与键盘、更多登录门禁；最终更多／Feed／日记卡／CTA 点击及键盘、UI 优先、登录不重放／不自动授权。 |
| AC207 | STEP-011 | 真机允许/拒绝，模拟无数据/无能力/非安全环境，关闭/旋转。 |
| AC208 | STEP-007、STEP-008、STEP-010、STEP-011、STEP-012、STEP-013 | 原因叠加、动作/传感器/面板暂停，幂等恢复和档位保持。 |
| AC209 | STEP-003、STEP-007、STEP-008 | 能力缺失/初始化故障仅影响特效，静态及入口可用。 |
| AC210 | STEP-013、STEP-015 | 策略与同页保持/新实例重评；真实指标按 Q201 达成。 |
| AC211 | STEP-003、STEP-017 | 静态适配与同一最终快照的四视口、旋转、卡片高度、动态／可用倾斜、贴片、安全区和正常手势。 |
| AC212 | STEP-001、STEP-002、STEP-016 | 逐图字节/alpha/清晰度/贴片、派生路径和最终无重复下载。 |
| AC213 | STEP-002、STEP-004、STEP-014、STEP-016 | 独立门闩、缓存/版本与同条件新旧冷/缓存/刷新测量。 |
| AC214 | STEP-012、STEP-017 | 场景对真实语音影响和 §4 全部既有业务用户流程。 |
| AC215 | STEP-014 | 实际响应、精确大小写、版本获取与旧背景回退。 |
| AC216 | STEP-018 | 最终源码/相关回归/当前契约一致，模拟与真机分开。 |
| AC217 | STEP-010、STEP-011 | 偏好跨刷新/访问/账号与设备隔离、系统优先；倾斜新页面关闭。 |

集合差异核对：

- 有效 PRD ID − 已映射 ID = ∅；已映射 ID − 有效 PRD/约束 ID = ∅。有效集为 F×12、RQ×6、G×5、V2-D×14、CSTR×17、AC×17，共 71 个。
- F/RQ/AC 的规范化归属与正文逐 STEP 反向归属差异 = ∅；总览/正文/进度的需求、AC 与依赖差异 = ∅；测试表出现的 AC 集与该 STEP 声明 AC 集差异 = ∅。
- 完整子条款人工复核：SDR-V2-R1-001 的最终布局／贴片与业务键盘承接已补入 STEP-017；SDR-V2-R1-002 的真实启动存储输入已在 STEP-004 明确，STEP-010 不再可被用作其替代证据。当前未处置的有效子条款集合 = ∅；这表示文档责任与验收已覆盖，实际功能证据仍待实施。
- CSTR-07、08、11、14、15、16、17 的业务范围、输入优先、鉴权真实状态、资源清理、四浏览器、本地数据与证据禁止项均保留；CSTR-08 增加 STEP-017 最终承接，原责任不变。

## 4. 发现与修复路由

发现 ID 固定为 SDR-V2-R1-001、SDR-V2-R1-002。首次审查时两项均仅有 review-only 授权，结构分类只限定目标与边界；随后用户明确授权“两项都补齐（推荐）”。本轮两项由 execute-approved-work 单一写入候选，并已返回本 Skill 完成全量复审。以下保留首次证据、分类和边界，补充当前责任与状态。

### SDR-V2-R1-001：最终集成回归未承接完整布局与业务键盘验收

1. **ID**：`SDR-V2-R1-001`。
2. **证据**：义务来自 `PRD / SRC-01`（摘要见 §1）`F202、F212、§5.3、AC206、AC211`；原稿 `PLANNED / IN-STEP` `§4 F202/AC206/AC211、STEP-003/008/009/011/017 的测试与验收`（当前约 199、224、229、394—469、802—853、941—943、1103—1105、1598—1606 行）。STEP-003 只建立静态场景，明确不含动态/传感器，却独占 AC211；STEP-008 一般地检查贴片一致，STEP-011 检查方向恢复，均未承接 AC211 的完整尺寸集。STEP-009 的 Enter/Space 只明确检查人物，STEP-010 检查更多门禁；STEP-017 的完整业务流程只声明 AC214，未明确卡片/CTA 键盘用例。`REPO_BASELINE / SRC-04` 的 `feed-entry-card、home-diary-card、home-cta-btn、handleHomeQuickAction` 证明已有卡片 Enter/Space 与原生按钮键盘入口（约 1407、1431、1455 行）；因此是保留既有能力的集成验证，不是新增无障碍范围。
3. **类型与理由**：`APPROVED_STRUCTURAL_REPAIR`；严重度 `P2`（文档验收缺口）；`obligation_source = PRD:F202/F212/AC206/AC211/§5.3`；`scope_class = IN_SCOPE_ACCEPTANCE_MAPPING`。必须补最终责任和同步映射，不能只补一个 AC 名称。唯一目标是现有 STEP-017 的最终主页用户回归，它已依赖全部相关功能。反证检查：STEP-003 确实有完整静态尺寸测试、STEP-009 确有 UI 优先检查、原稿 §5 确有受影响补测原则；它们可复用未变前提下的证据，但不能直接证明尚未接入的动效/倾斜在全尺寸和两种身份下保持原结果。这里不认定布局实现已出错，也不要求无依据重复全部测试。
4. **目标与边界**：唯一目标：在 STEP-017 增加最终集成的 F202/AC211 与 AC206 业务入口子条款，保留 STEP-003 的静态适配和 STEP-009/010 的原责任。允许范围：STEP-017 的来源/输入/任务/测试/完成标志；以及必要的 §2 CSTR-08、§3 总览、§4 覆盖和 §9 进度同步。不改变 18 个节点和依赖边，因为 STEP-017 的现有前置已覆盖场景、动作、控制、倾斜和数据；不新建重复回归步骤。禁止：重排布局、改视口值、扩大权限/语音支持、增加新业务、减少已有断言或改变 PRD。
5. **责任与授权**：`repair_owner = execute-approved-work`，完整复审／权威 owner 为 step-doc-review。首次仅 review-only；当前文档授权来自用户“两项都补齐（推荐）”，已按 finding 的唯一边界写入独立候选。未授权业务代码或发布。
6. **验证**：候选应在同一最终集成快照中列出 375×667、390×844、430×932、1280×720、横竖屏、卡片由占位到结果/失败高度变化，检查脸部/入口/底部可操作、安全区/缩放/手势与动效/倾斜贴片一致；四浏览器范围保持。访客/登录分别用点击与 Tab/Enter/Space 操作更多、Feed/日记卡和 CTA，断言既有路径/门禁、UI 优先和登录不重放、不自动请求倾斜；人物的完整责任仍由 STEP-009 承担。测试应允许复用仍成立的静态证据，新增动态/输入影响部分必须有直接证据。修复后规范化 F202/AC211、AC206 业务子条款与所有正反向视图一致，依赖仍无环；不得仅靠 §18 的一般对账句算覆盖。
7. **状态**：**复审通过（文档）**。首次状态为待修复；本轮 STEP-017 与必要映射已修，执行器 item_status = VERIFIED／交接 STEP_REVIEW_READY，当前完整复审已通过。改动、证据与候选摘要见 §7／§8；实际布局、键盘和真机功能验收尚未执行。

### SDR-V2-R1-002：存储异常用例没有覆盖真实启动前的失败位置

1. **ID**：`SDR-V2-R1-002`。
2. **证据**：`PRD / SRC-01` `§5.3、§6“本地存储不可用”、AC202` 明确存储失败不得中断首页。`PLANNED / IN-STEP` `STEP-004::输入/Session 定义/边界测试` 仅笼统写“存储抛错”（约 520—555 行）；`STEP-010::开发任务4/异常用例` 处理动态偏好读写（约 1012、1022 行）。`REPO_BASELINE / SRC-04` `homeAuthMode = localStorage.getItem('token')`（1503 行）处于 `initHomePage()`（2272 行）调用前，没有 try/catch；`loadPage`（2098）、`renderVisitorHome`（1941）及入口还使用本地存储。`REPO_BASELINE / SRC-05::request`（83—84 行）在 try 前读取 token。以上是读到的源码；“同步读 token 抛错可导致启动流程未建立”是据此作出的控制流推断，本轮未运行浏览器复现。
3. **类型与理由**：`DETERMINISTIC_DOC_ERROR`；严重度 `P1`（启动可用性验收缺口，非声称新实现已有故障）；`obligation_source = PRD:AC202/§5.3/§6`；`scope_class = IN_SCOPE_TEST_INPUT_CLARITY`。存储异常已分配给 STEP-004，但没有明确是 session 标记、偏好还是 token，也未要求在真实内联启动前注入。只让 session 标记或新偏好抛错即可匹配现文字，仍漏过启动前失败点，5000/8000ms 兜底根本未建立。反证检查：当前 shouldSkipHomeLoader/dismiss/刷新移除 Session 标记已有 try/catch；STEP-010 也有偏好故障测试，不能因此认为问题未安排，但这些保护并不覆盖早于它们的 homeAuthMode。代码现状只定位风险，修复义务直接来自 PRD，不扩大为全站存储重构。
4. **目标与边界**：唯一目标：细化 STEP-004 已有 AC202 存储子条款，列明真实主页加载/跳过入口、故障存储及注入时刻，要求检查启动前读取，不能只测试抽出的 Loader 函数。允许范围：STEP-004 的必要代码定位、任务、测试输入/预期与完成标志；STEP-010 既有偏好用例继续有效并注明证据职责，无需新增 ID 或依赖。禁止：改变持久化范围、Session key、鉴权/登录/401 策略，发明 token/新账号同步方案，改公共请求默认行为，重构其他页面或将存储异常改判有效 401。
5. **责任与授权**：本机械项独立时默认 owner 为 step-doc-review；因本轮与 001 结构项一起获批，实际 `repair_owner = execute-approved-work`，两项统一写同一候选，step-doc-review 仅完整复审与签发。用户“两项都补齐（推荐）”已授权本 finding 的限定文档修改；首次 review-only 未授权修复的状态仅作为历史保留。
6. **验证**：STEP-004 用例至少区分：Session get/set/remove 失败；首次脚本执行前 localStorage 访问或 token getItem 失败；首页启动途中必要存储写入失败；新偏好读写失败仍归 STEP-010。前台首次/刷新/跳过均直接加载实际 index.html，保持业务入口与静态保底可用、遮罩按已确认截止退出，无未捕获异常导致整体启动中断。不得用“函数桩正常”证明整页通过；认证状态继续遵守 §5.2，不把无法读取/网络失败冒充有效 401。候选明确这些输入、阶段和可观察断言，即视为此文档问题已修正；实际功能验收仍在实施时执行。来源摘要不变、完整九维复审通过后才能关闭发现。
7. **状态**：**复审通过（文档）**。首次状态为待修复；本轮 STEP-004 故障输入与 STEP-010 偏好证据职责已修，执行器 item_status = VERIFIED／交接 STEP_REVIEW_READY，当前完整复审已通过。改动、证据与候选摘要见 §7／§8；实际首页存储故障运行验收尚未执行。

## 5. 关键链路与反证检查

| 链路 | 审查结论 |
|---|---|
| 进入主页 → 静态资源/解码 → 加载遮罩 → 可用入口 → 坏图/挂起/恢复 | STEP-003/004/007/016 分开核心 5 秒、正常 3/0.5/0.55 秒、遮罩 8 秒及恢复检查；API/头像/可选层不入门闩。Session 跳过和晚模块也有承担。002 已补保护建立前的真实页面存储注入，用例不依赖晚阶段偏好证明。 |
| 数据占位 → 允许的公共/私有请求 → 批次截止 → 解析/写 UI → 登录/退出/重试 | STEP-005/006 直接处理真实 fetch 取消、代次/登录快照、401 前与解析后检查、未知关系/失败/空态区分和 Feed 刷新去重；未另造 API，保留现策略。 |
| 人物/更多/业务控件 → 动态意图 → 本地反馈或登录门禁 → 页面反馈 | STEP-009/010/011 的人物本地/门禁/主动权限明确；001 已在 STEP-017 直接承接旧 cards/CTA 的键盘路径与最终动态／倾斜场景布局验收，原责任不变。 |
| 倾斜用户操作 → 支持/安全/授权/有效数据 → 输入 → 主调度 → 关闭/拒绝/旋转 | STEP-011 区分等待和真实开启；权限晚回需要生命周期检查，事件只更新输入；关闭/隐藏/销毁移除监听，恢复不重新弹权限。真机事实另列。 |
| 登录窗/语音准备/后台/用户关闭/系统减少动态 → 原因集合 → 暂停 → 恢复/销毁 | STEP-007/008/011/012/013 覆盖 CSS/WAAPI/RAF/计时器/监听/观察器；实际 .voice-entry hidden 和登录窗 class/aria 为依据，不只等 voice:connected。场景治理不接管音频链路。 |
| 持续运行 → 测量 → 降级 → 同实例恢复/新实例 → 实际性能反馈 | STEP-013/015 保持顺序、同页不升档和新页重评，偏好/系统覆盖仍优先；Q201 不用编造阈值替代。 |
| 资源版本/缓存 → 实际响应 → 更新/回退 → 语音旧图 | STEP-014/016 检查精确文件名和 HTTPS/缓存，保留旧图且不放入关键预热。回退必须沿用 STEP-007 的场景暂停/销毁治理；不能只隐藏画面而保留场景循环/监听，既有 F208 边界继续适用。 |

未将现契约“所有 401 都先清 token”与新失效保护错误判为需重新确认：PRD 更高优先级已确认增加有效上下文前置，且要求默认调用兼容和最终契约同步。未把本机 Nginx 80、文件大小写或 Python 依赖声明推断为部署/真机/已安装运行事实。未读取历史技术债正文；没有旧债已关闭断言。

## 6. 非阻断风险与停止门

| 风险／来源 | 当前事实与负责位置 | 后续关闭方式 |
|---|---|---|
| Q201／PRD | 设备、版本、网络、像素上限与统计/降级窗口未定；STEP-013 选参，STEP-015 持续运行，STEP-016 加载，相关 STEP 验收前列明环境。 | 保留普通近 60fps/低档至少 30fps 目标；无设备/统计/基线不宣称相对收益或对应真机 AC 完成。需要改已确认目标才构成新决定。 |
| Q202／PRD、ASSET-01—07 | 七图 1,286,798 字节、核心 450,234 字节与 PRD 一致；没有导出优化结果或新图视觉检查。 | STEP-001/002 导出及质量对照，STEP-016 实际尺寸/高 DPR/下载链路；争取预算与质量保持原口径。 |
| Q203／PRD、SRC-08 | 本轮没有真实部署 URL/外层 HTTPS/缓存响应；旧图只有精确 Index.png，主页旧引用为 index.png。 | STEP-014 先定位验证环境/实际服务方式，再检查响应和回退；STEP-011/016 复用所需事实；真实部署/发布仍须有相应授权。 |
| 运行入口／SRC-09/10/15 | 静态 pytest 和受控 Playwright 示例存在，但本轮没有发现安装/执行新主页测试或真实声音条件。 | 功能 STEP 先发现可用运行入口；不得使用语音示例默认输出目录作为新主页约定，不以静态/受控传输替代真实设备/声音。 |

上述均在原稿和当前候选保留明确实施／验收前门，属于事实采集和未来执行风险，不升级为未决产品项或 SOURCE_OR_EVIDENCE_BLOCKED。首次 FAILED_VALIDATION 来自两项文档缺口；本轮缺口修复并完整复审通过后，剩余明确非阻断风险使结果为 PASS_WITH_RISKS。事实门未关闭时，相应功能／部署步骤不能宣称完成。

## 7. 文档校验与证据限度

`RUNTIME` 只适用于实际运行的文档／来源校验，不适用于新主页功能。以下先保留首次审查的历史命令，再记录本轮候选校验。

### 7.1 首次 review-only 校验（历史证据）

| 字段 | 证据 |
|---|---|
| 命令 | `/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /private/tmp/audit_home_redesign_v2_steps.py` |
| 工作目录 | `/Users/umark/Desktop/lxm-tm/lxm-4/lxm_for` |
| 执行时间（UTC） | 2026-10-02T07:31:32.042632+00:00 至 2026-10-02T07:31:32.059761+00:00 |
| 退出码 | 0 |
| 关键输出 | `step_count=18`；`obligation_count=71`；总览/正文/进度、编号集合和测试 AC 集差异均 `[]`；原稿来源摘要前缀不匹配 `[]`；依赖循环 `[]`；七图元数据及精确旧背景文件名断言通过。 |

首次校验器定向解析当时实际 Markdown 和来源，不使用此前生成器 JSON 代替原稿；临时结果位于 `/private/tmp/home_redesign_v2_step_audit_checks.json`。编号/图校验不能识别所有语义缺口，001/002 来自 PRD、完整步骤和代码控制流的人工核对，不能因机器结果为空而忽略。

本轮未运行业务测试：任务为方案文档审查，未改实现。新主页真机、GPU、声音、加载时间、压缩文件和实际部署均未验证；没有将源码推断写成浏览器实测。

### 7.2 本轮候选独立校验

| 字段 | 本轮 RUNTIME 证据 |
|---|---|
| 命令 | `/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /private/tmp/check_home_redesign_v2_candidate_r1.py` |
| 工作目录 | `/Users/umark/Desktop/lxm-tm/lxm-4/lxm_for` |
| 执行时间（UTC） | 2026-10-02T08:04:58.270911+00:00 至 2026-10-02T08:04:58.293140+00:00 |
| 退出码 | 0 |
| 关键输出 | `steps=18`；`obligations=71`；`edges=74`；改动 STEP 为 004／010／017；映射差异／依赖变化／循环／未授权 STEP 改动均 `[]`；两项均 VERIFIED_DOCUMENT_CHANGE；功能完成数 0。 |

独立校验器重新解析实际 PRD、原稿和完整候选，重读当前代码控制流与素材元数据，核对原 28 个来源摘要、逐项修复判据、映射／依赖／正常异常边界表及未完成状态。结果保存于 `/private/tmp/home_redesign_v2_candidate_r1_checks.json`，执行器返回保存于 `/private/tmp/home_redesign_v2_r1_repair_result.json`；本审计保留关键证据，不把临时 JSON 当原始权威来源。

生成验证版前于 `2026-10-02T08:21:08.475611+00:00` 重算 29 个来源，全部一致。最终产物校验记录在下节；文档结构检查与完整语义复审分开，空集合机器结果不能代替九维完整判断。

### 7.3 最终产物校验

| 字段 | 本轮 RUNTIME 证据 |
|---|---|
| 命令 | `/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /private/tmp/verify_home_redesign_v2_review_artifacts.py` |
| 工作目录 | `/Users/umark/Desktop/lxm-tm/lxm-4/lxm_for` |
| 执行时间（UTC） | 2026-10-02T08:23:27.029722+00:00 至 2026-10-02T08:23:27.038950+00:00 |
| 退出码 | 0 |
| 关键输出 | 三份产物 H1／链接检查 PASS；29 个来源摘要不变；71 ID 的审计映射与候选一致；验证版业务正文等于复审候选，只有文档身份／交接提示变化；74 条依赖边保持；首次发现与九维历史状态保留，当前九维均 PASS；两项问题契约关闭；功能完成数 0。 |

临时结果为 `/private/tmp/home_redesign_v2_final_artifact_checks.json`。此校验验证文档复制、记录和来源一致性，没有运行主页交互、故障注入、真机性能或部署测试；本节在命令退出后回填，候选与验证版内容未再变化。

## 8. 修复与完整复审记录

### 8.1 授权、单一写入与逐项 Diff

| 项目 | 当前记录 |
|---|---|
| 首次审查 | 原稿完整九维结果 FAILED_VALIDATION／REPAIR_REQUIRED，见 §2；发现固定为 001、002。 |
| 用户新增授权 | 用户明确回答“两项都补齐（推荐）”；只修两个 finding 的限定文档目标，不改业务决定、PRD、代码或素材。 |
| 唯一候选写入方 | execute-approved-work 统一执行两个授权项，执行阶段输入原稿与审计只读；step-doc-review 未交替修改该候选。 |
| 执行命令／环境 | `/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /private/tmp/repair_home_redesign_v2_steps_r1.py`；cwd `/Users/umark/Desktop/lxm-tm/lxm-4/lxm_for`；UTC 2026-10-02T08:00:47.003572+00:00 至 2026-10-02T08:00:47.014744+00:00；退出码 0。候选身份／授权元数据在执行交接前一并核对；最终摘要以独立校验为准。 |
| 执行器交接 | 两项 item_status = VERIFIED（仅文档判据）；handoff_state = STEP_REVIEW_READY。该结果没有 STEP 权威效力。 |
| 候选完整 SHA-256 | `c73cc056bbf824536979a386b7439fd88384838042baba938cf9c02dcc6e9378`；后续完整复审与签发均使用该快照，未再次改写候选。 |
| 原稿完整 SHA-256 | `e3dccbf514175800344fbfb3504cf0b7ebfdebcd20a84b8c710230d737928cab`；PRD 和原 28 个来源保持不变。 |
| 当前来源摘要 | `32fdc66cb4051b95865256d4860d610776dc5b7716f571a96cd24d01df0ea35c`；唯一来源清单见 §1。 |

| finding_id | changed_location（候选稳定定位，行号辅助） | 原稿 → 候选的实际 Diff | verification_evidence／item_status |
|---|---|---|---|
| SDR-V2-R1-001 | STEP-017（约 1545—1640 行）的来源／输入输出／定义／任务／测试／完成标志；§2 CSTR-08、§3 总览、§4 F202／AC206／AC211、§9 明细 | 最终回归只声明 AC214 → 增加 F202、AC206、AC211 直接责任，列出同一最终快照、四视口／旋转／卡片高度、动态／实际可用倾斜及访客／登录的业务点击／键盘断言。静态证据按未变前提复用；只给 F202／AC206／AC211／CSTR-08 增加 STEP-017，节点／边不变。 | §7.2 当前校验退出码 0；§8.2 完整九维 PASS；执行器 VERIFIED，当前状态复审通过（文档）。 |
| SDR-V2-R1-002 | STEP-004（约 492—574 行）的定位／输入／定义／任务／测试／完成标志；STEP-010（约 970—1047 行）的偏好故障职责 | 泛称存储抛错 → 分列 Session get/set/remove、任何脚本执行前 localStorage 属性／token getItem、途中必要写入。实际加载 index.html、区分首次／刷新／非刷新跳过并记录阶段／时刻／入口；认证错误不冒充有效 401，偏好用例不能替代启动证据。需求 ID、鉴权／持久化及默认 request 语义不变。 | §7.2 当前校验退出码 0；§8.2 完整九维 PASS；执行器 VERIFIED，当前状态复审通过（文档）。 |

候选的功能 STEP 正文只变 004／010／017；其他 15 个正文与只读原稿一致，必要身份／授权／自检与映射记录更新。没有新增节点或依赖，没有削弱原断言，没有将任何功能标 DONE。验证版从该候选复制，只更新文档身份、权威交接、审查回传和已验证文件中的提示文案，业务目标／用例／映射保持。

### 8.2 完整候选九维复审

以下为对**完整候选**从当前 PRD、用户决定、必要契约与代码基线重新检查的结论；并非继承首次 PASS 项，也不只审阅 Diff。已核对全部 18 个 STEP、71 个有效 ID、未编号硬约束及排除项、输入输出／任务／用例／完成标志和共用发现门。九维 PASS 表示文档合格，非功能验收通过。

| 维度 | 状态 | 当前完整复审依据与结论 |
|---|---|---|
| 1. 幻觉 | PASS | 全部时间／视口／预算／状态来源仍为 SRC-01；未编造设备、像素阈值、存储键或新接口。004 新注入点来自 SRC-04/05，017 键盘来自 PRD 与既有 DOM。planned／unverified 保留，0/18 功能完成。 |
| 2. 遗漏 | PASS | 001 在最终 STEP-017 直接承接动态／倾斜集成布局和业务键盘；002 在 STEP-004 分开最早脚本故障，010 限定偏好责任。全部原加载／数据／生命周期／材料／回退／保留行为／禁止项与契约动作都有 STEP 处置。 |
| 3. 冲突 | PASS | 保持 RQ-01—06、公共首页、访客门禁、登录不重放和主动倾斜规则。存储异常不当服务端 401；STEP-005 有效上下文前置符合更高优先 PRD，默认调用兼容，实施后由 018 同步契约；四浏览器主页范围不扩大微信语音支持。 |
| 4. 清晰度 | PASS | 004 规定对象／键／操作／脚本前或途中／真实入口及可观察截止；017 规定同一最终快照、状态和直接证据，不能只添 AC 名。Q201—203／测试运行／基线的发现目标、owner 和缺失处理保留，无笼统待查代替核心可行性。 |
| 5. 依赖 | PASS | 总览／正文／进度均为 18 节点、74 条原边，无循环／断链／自依赖。017 已具备最终集成前置；004 负责基础启动，005／006 联合回传请求及数据证据，不暗增反向依赖；007 可传递取得静态场景。 |
| 6. 可测性 | PASS | 每 STEP 正常／异常／边界都给输入、行为断言和可观察输出，测试 AC 集与声明一致。新增两项有正式页启动与最终输入链路，资源、时序、状态、声音、设备和部署的直接证据限度明确；共享 AC 只在子条款齐备时汇总。 |
| 7. 覆盖率 | PASS | 唯一规范化视图共 71 ID，正向／反向／总览／逐 STEP／进度差异均空；F202／AC206／AC211／CSTR-08 必要 owner 同步，原责任保留。子条款人工核对无未处置项，不以编号数量替代实际对象与链路验证。 |
| 8. 技术债 | PASS | 全文保持 PRD 本期不新增债编号、不重结算旧 K／TD 的边界；TD-HOME-08 仅作 v2 替代说明。未将读取到的代码缺口升级为新技术债或声称历史关闭。 |
| 9. 代码事实 | PASS | 完整来源清单与本轮必要定位一致，existing 路径／符号与接口实际已读；004 读取点早于 init 与 request try、卡片 Enter／Space、原生 CTA、语音 hidden／先准备、demo 多 RAF 和真实 Index.png 均核对。原 28 个来源与候选摘要在签发前保持不变；未以源码证明运行支持。 |

关键链路与反证检查见 §5；同一最终输入快照、旧静态证据复用条件及身份／卡片状态已直接写入 017，没有凭“数量相同”认定对象／入口一致。所有必要现有入口可定位；真实环境的未定位事实有明确停止门，作为 §6 非阻断风险保留，故阶段结果不能是无风险 PASS。

### 8.3 权威签发

`REPAIR_REQUIRED → STEP_REVIEW_READY → STEPS_VERIFIED`。首次原稿仍有历史缺口并保持只读；修复候选完整复审通过，当前验证版为 [steps-verified.md](steps-verified.md)。

验证版 SHA-256：`f84701e11e838926ba1610b19f59ca54d99a386627f32f5e5f406ab6b7e99ae5`；候选 SHA-256：`c73cc056bbf824536979a386b7439fd88384838042baba938cf9c02dcc6e9378`。原候选保留作为复审输入快照，不在其中回填新权威或重复维护实施状态；后续实施进度只维护验证版 §9。来源变更时按受影响范围重新核对，不能用当前文档结论代替后续源码版本的功能验收。

## 9. 阶段结果与恢复位置

阶段结果：**PASS_WITH_RISKS**。权威状态：**STEPS_VERIFIED**。两项文档发现均复审通过；当前产物为 step-audit.md、steps-candidate-r1.md、steps-verified.md，原稿／PRD／代码／素材保持原样，功能仍 NOT_STARTED（0/18）。

本阶段到此完成文档修复与完整复审，不自动实施功能。后续按用户指定范围从相应 STEP 恢复，先复核来源与共用发现门；在首个主页源码改动前保留真实对照基线。Q201 真机／统计口径、Q202 素材导出与质量、Q203 部署／缓存和运行入口在对应步骤关闭，缺少证据不宣称相应 AC 完成；真实生产发布另须已有相应授权。
