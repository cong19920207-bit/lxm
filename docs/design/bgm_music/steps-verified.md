# steps-verified

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> 日期：2026-10-19；模式：`standalone / review-repair`；文档状态：`STEPS_VERIFIED`；完整复审结果：`PASS_WITH_RISKS`。
> 已按 step-audit.md 修复 SDR-20261019-001～004，并对完整当前计划与 PRD、demo、当前代码完成九维复审。原 steps-draft.md 及两轮候选只读保留；本文件为本轮签发的 STEP 文档。
> 本轮仅修复、复审和签发文档，未开始开发、部署或功能测试。21 个 STEP 均 `NOT_STARTED`；文档通过不表示 100 项功能验收通过。本文§9是后续获准实施时唯一进度区块，原稿及候选§9仅为历史快照。

## 1. 输入、事实与范围

- `PRD`：P01，V1.3、2026-10-19，正文已做文档级对照与一致性检查（L11/848），并声明核心功能无待用户选择的阻断问题（L772–776）。本次按已明确规则拆解，不宣称已经过人工终审或实施验收。
- `USER_DECISION`：原拆解要求“文档和拆解开发步骤”“要结合demo进去”；本次新增授权是按step-audit.md修复4项文档问题、保留原稿，随后由审核方完整复审并在通过后生成验证版，本轮不开发。PRD中的D-01～18仍标PRD，不冒充本次对话另行取得的用户决定。
- `CONTRACT`：只使用R03白名单中的当前权威契约C01～C07。T01/T02仅为只读台账背景（REFERENCE_ONLY），不作本期需求、验收或技术债承接来源。指定PRD和demo作为本次明确输入读取；它们当前不在manifest中，不能据此宣称为既有运行契约。
- `REPO_BASELINE`：本地分支`codex/deploy-memory-v32-20261015`，HEAD `445996f1ed19b8025a2a789357506f61fb335f6c`。工作区已有大量未提交改动，来源SHA256以本轮实际文件为准，HEAD不能替代工作区摘要。
- `RUNTIME`：本轮没有。已有demo验证文件只作为仓库中的历史声明读取，本轮只查看源码和现有截图，没有重跑、真机输出、实际通话、接口联调、OSS/CDN写入或容量测量。
- `PLANNED`：未来BGM模型、API、模块、迁移、静态资源及专项测试均未存在；具体名称按已核实的项目约定确定，记录在STEP-001的采用记录。PRD建议接口/字段/Key不当作现有符号。
- `UNVERIFIED`：真实部署Bucket/CDN/权限、浏览器音频能力、处理器实际参数及HTTP缓存效果；由后续STEP-020/021取证。这些不是缺失需求，不阻断本次文档签发；仍须在后续实施验收中取证。

### 1.1 功能清单（原优先级不改写）

| 需求ID | 本期目标 | 原优先级 | 直接负责STEP |
| --- | --- | --- | --- |
| F-001 | 第五格/面板/极简歌单/控制 | P0 必须交付 | STEP-014、STEP-021 |
| F-002 | 六类内容与设置页气泡 | P0 必须交付 | STEP-015、STEP-021 |
| F-003 | 本地五项偏好/设置公开区 | P0 必须交付 | STEP-009、STEP-013、STEP-014、STEP-021 |
| F-004 | 意图/顺序/增益/渐变/降级 | P0 必须交付 | STEP-010、STEP-011、STEP-012、STEP-017、STEP-019、STEP-021 |
| F-005 | 跨页/可见性/登录/真实通话与其他声音 | P0 必须交付 | STEP-013、STEP-016、STEP-017、STEP-018、STEP-019、STEP-021 |
| F-006 | 匿名目录/事件缓存/Redis | P0 必须交付 | STEP-007、STEP-012、STEP-019、STEP-021 |
| F-007 | 单一管理页/角色/运营/审计 | P0 必须交付 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-008、STEP-021 |
| F-008 | 真实音频/受限处理/OSS/手动清理 | P0 必须交付 | STEP-001、STEP-003、STEP-006、STEP-020、STEP-021 |
| F-009 | 可选静态封面/默认图/独立版本 | P0 必须交付 | STEP-002、STEP-005、STEP-006、STEP-007、STEP-012、STEP-014、STEP-015、STEP-020、STEP-021 |
| F-010 | 单候选轻量准备/HTTP缓存 | P0 必须交付，允许规定条件下跳过预加载 | STEP-001、STEP-019、STEP-020、STEP-021 |

编号清单：PRD含P-001～009背景问题、OBJ-001～005目标、F-001～010功能、BR-001～055业务规则、E-001～030异常、AC-001～100验收、D-01～18确认、SUG-001～021建议及RISK-001～012风险。F/BR是本文档需求映射的有效ID；不新增RQ或新优先级。下文逐项列出全部F/BR/AC/E/D/SUG及排除约束；P/OBJ/RISK保留为来源背景/目标/风险，不改造成新需求。

OBJ-001由播放/主页/气泡及最终闭环承担；OBJ-002由本地偏好/控制器/会话/通话承担；OBJ-003由生命周期/声音互斥承担；OBJ-004由后台音频/目录/封面/删除/审计承担；OBJ-005由目录缓存/有限处理/准备及真实HTTP缓存验证承担。最终完整目标核对由STEP-021负责。

### 1.2 排除项与未编号约束

| 约束ID | 内容（准确归并PRD未编号条款） | 负责STEP | 来源 |
| --- | --- | --- | --- |
| CSTR-001 | 同文档最多一首输出；音乐软依赖，不重写导航/通话业务 | STEP-010、STEP-013、STEP-016 | P01 L46/220–252 |
| CSTR-002 | 本期排除歌词/歌手/搜索/收藏/上一首/拖动进度/随机/均衡器/睡眠及多场景音轨 | STEP-010、STEP-011、STEP-014 | P01 L50–65 |
| CSTR-003 | 排除账号偏好接口/数据库/隔离/合并/跨设备同步及用户行为采集管线 | STEP-009、STEP-014、STEP-019、STEP-021 | P01 L153–177/L615–630 |
| CSTR-004 | 排除SPA/AppShell/iframe/跨窗接力/后台锁屏持续播放；不新建TTS/通话 | STEP-013、STEP-016、STEP-017、STEP-018 | P01 L61/220–252 |
| CSTR-005 | 排除目录轮询/实时推送、专用缓存/任务平台、审批/回收站/到期自动删 | STEP-003、STEP-006、STEP-007、STEP-012 | P01 L57–65/L254–340 |
| CSTR-006 | 排除封面库/动态图/编辑器/音频内嵌图提取/个人封面/后台全局默认图 | STEP-005、STEP-014 | P01 L342–374 |
| CSTR-007 | 排除完整媒体本地库/离线/全歌单预取/SW/Cache API/IndexedDB缓存链 | STEP-019、STEP-020 | P01 L376–410 |
| CSTR-008 | 服务端UTC保存、管理页明确时区，等待按服务端时间；秒/字节单位 | STEP-003、STEP-006、STEP-008 | P01 L607–613 |
| CSTR-009 | 真实设备/浏览器/API/DEP按PRD矩阵，SIM不代替，未测不宣称容量 | STEP-020、STEP-021 | P01 L634–645/L744–748 |
| CSTR-010 | 建议接口/字段/Key只是能力示例，实际名称按已核实约定确定 | STEP-001、STEP-002、STEP-003、STEP-005、STEP-007 | P01 L311–324/L412–428 |
| CSTR-011 | demo用于交互/视觉参考；本次用户额外要求“要结合demo进去” | STEP-003、STEP-004、STEP-005、STEP-006、STEP-014、STEP-015、STEP-017、STEP-019 | USER_DECISION：本次任务；D01 L3/29–41 |
| CSTR-012 | 保留现有改动；禁扫基线与历史，本轮仅文档修复、完整复审与签发，不开始开发 | STEP-001、STEP-021 | USER_DECISION：本次任务与协作约束；R01 L1–8 |

### 1.3 本期技术债准入与基线回归风险

本期合法技术债承接集合为 `∅`：P01与本次用户决定均未指定承接任何TD。T01/T02中的既有编号仅保留背景定位，不构成本期需求、验收、清偿任务或新的用户决定；不修改台账、不新增TD。

| 基线回归风险（非技术债承接项） | 现有代码/PRD锚点 | 本期边界 |
| --- | --- | --- |
| 图片全屏返回与手势兼容 | H08 `openPreview()` L1411–1479；P01 F-002/BR-006、AC-013 | STEP-015保留原手势并适配气泡；原有兼容说明只作背景，不能当新故障或扩大修复范围 |
| 朋友圈隐藏型DELETE | B23 `delete_post()` L209–224；C06 L213；P01 BR-034/035/050、AC-065/090 | BGM实现自己的等期手动真清理；不能复用`is_visible=0`冒充对象删除，不改朋友圈删除语义 |
| 无可直接复用的后台本地图上传链 | B23 `create_post()`/`PostCreateBody` L253–312的upload模式接收已有image_urls；B03 `FeedImageService`；P01 BR-044～046、AC-086/087 | 可复用OSS连接；不能把图片生成/已有URL录入当通用本地封面上传，BGM封面能力按STEP-005实现 |
| 语音结束、结算与占用边界 | H06 `close()`/`renderResult()`/`resolveTerminalResult()`；H17 `close()`；C04结束/终态规则；P01 BR-023、AC-037～039 | STEP-016等待可信清理边界；不以busy/界面消失冒充终态，不改结算方案 |
| 真实通话与配置/能力测试证据范围 | H06 `begin()`/`prepareCall()`及H17 `start()`；P01 F-005、AC-037～039；T02仅作既有延期背景参考 | 选定实际可用配置验证BGM互斥；通话接通或模拟不代表配置预检/所有能力通过，不增加配置预检或强制测试能力贯通任务 |
| 固定测试断言与当前基线差异 | H14/H15/H16仍断言旧more；B12/B13/B14写死不同页面/路由数量 | 新需求定点更新断言并保留原权限；先记隔离基线，不宣称本轮全量测试健康 |

上述护栏来自本期PRD行为约束及真实代码基线；它们不将背景台账转为BGM清偿义务。

## 2. Demo如何进入开发步骤

目录名称保留`bgm-v1.2`，但D01/D02/D12正文已升级V1.3。需求以P01为准，demo提供界面与交互参考；二者没有已发现的阻断性业务冲突。

| 交付面 | 可参考的现有demo证据 | 必须补足的生产能力 | 负责STEP |
| --- | --- | --- | --- |
| 主页/面板 | D02；D03 L224/273–362/413–425；D07/D08/D09；D14截图 | 正式第五格移出私有门禁；共享控制器/真实目录/输出；保留同一唱片过渡/焦点/长名/减少动态效果；demo默认开面板只是审阅便利 | STEP-010～014 |
| 六页气泡 | D02 L77；D03 L348–361/413–418 | demo内部页面切换不证明跨HTML；逐页键盘/底栏/覆盖层/安全区及关闭一致性 | STEP-013/015 |
| 后台音频与目录 | D04；D05 L39–60/81–148/232–305；D11/D15 | 本地角色/version++/约3秒模拟处理/本机等待钟/振荡器试听改为服务端授权、真实音频、原子目录、服务器时间和可恢复操作 | STEP-002～004/007/008 |
| 封面 | D03 L59–83；D05 L163–217；D06 L131–243；D10 | 真实图像/OSS/独立版本/并发/持久结果查询；不得把DataURL/localStorage图资产和内存unknown变量移入生产 | STEP-005/012/014/015 |
| 删除和旧图回收 | D05 L132–148/192–194/332–334 | 真实音频/专属封面逐对象清理，归属/剩余结果/墓碑及补偿；不能用数组移除代替OSS删除 | STEP-006 |
| 下一首准备 | D03 L85–139/437–438；D06；D12 | 至多一个无声候选与目录资格/版本/预算/最新意图接线；metadata准备不等于全曲缓存，实际Range/CDN/取消/弱网取证 | STEP-019/020 |
| 通话/短TTS | D03 L366–368/435模拟入口 | 真实VoiceEntry准备/清理hook；短TTS只做明确允许的控制接口模拟，不新增业务 | STEP-016/017 |

demo采用0.5秒渐变、名称60码点、删除24小时、封面5 MiB/4096px/512px、准备8秒、本地HTTP缓存1小时等，仅是demo采用值。PRD中的准备20秒、HTTP约30天也仅为建议；本次均不转成硬性验收阈值。D12区分V1.3增量/helper模拟/旧V1.2结果，不将历史40项视为本轮重跑。

## 3. 来源登记与发现门

### 3.1 已核实来源

所有下表路径均`existing`。`source_id`是本文档证据ID，`locator`绑定同一文件的行号/符号/章节，SHA256为2026-10-19本地工作区完整文件摘要；与git HEAD记录不同。后续执行前仅复核本STEP所用文件；如有变化，定向重读并更新，不重扫全仓。

| source_id | 路径（状态均existing） | 来源标签 / locator | SHA256 |
| --- | --- | --- | --- |
| P01 | `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `PRD` / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | `f035f197266bb8fa936bbc33ca658762a99a3efef9fd321b7bbb24a64a029c04` |
| R01 | `AGENTS.md` | `REPO_BASELINE` / L1–8 文档读取边界 | `9594e52f3ec3c8bab990fa973c3ff8a854467081df2369971800330666e642c3` |
| R02 | `docs/INDEX.md` | `REPO_BASELINE` / 默认读取边界；功能/任务→必读契约 | `6cc42dea7c09387c3f56f9c258d30eea56a747b51e843d318cec75c9b3122dfa` |
| R03 | `docs/llm-manifest.json` | `REPO_BASELINE` / documents[] current/canonical 条目及 exclude_roots | `fa6dfed1f9ac0b5ce2b13de628c2c1a66340a198ab88623000956c2ae94d8b29` |
| C01 | `docs/contract/current/_shared/conventions.md` | `CONTRACT` / L10–31 响应/字段/错误码；L112–118 匿名例外 | `9ae6b47a846bbcdbb74a1ff5133900ebf794bf4acff4638c74f1d8d82ae4e388` |
| C02 | `docs/contract/current/_shared/auth-rbac.md` | `CONTRACT` / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | `f85772798d804f65bd159fd2c81dd0c531d90cb306c5fb383f030fd263205f40` |
| C03 | `docs/contract/current/h5-app/api.md` | `CONTRACT` / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | `86ba323599c97ae7dad91b2d67a6cc8d7dd073d341baa3694351e255a2b0cb06` |
| C04 | `docs/contract/current/realtime-voice/api.md` | `CONTRACT` / L13–25 强鉴权；L39–47 结束；L62–66 终态/占用查询 | `6d710ad2ab9117df69431f5431ca0f89a12b24b5b4ae1292c50481bfb0c5218c` |
| C05 | `docs/contract/current/admin-security-accounts/api.md` | `CONTRACT` / L9–26 日志接口/角色/筛选 | `4e538534500bef89de959fa507daca5d3ba6faeea8808649b9e4a28ff971157b` |
| C06 | `docs/contract/current/life-feed/api.md` | `CONTRACT` / L114–122 现有OSS图片Key与业务边界 | `d276b074794c21de5a13c10892389d043e6494464349e5912e23f4cd09c86491` |
| C07 | `docs/contract/current/life-feed/data.md` | `CONTRACT` / L60–83 Feed图片URL/现有业务 | `8c7e5d622b6605b77ef814c79f1efda9fdd3f6d3fe719e91536ce52c4adc5f62` |
| T01 | `docs/tech-debt/active/life-feed.md` | `CONTRACT`（REFERENCE_ONLY背景，非本期义务） / L11 TD-032；L42 TD-035；L52 TD-036 | `58b088159e34d5b478d65ac79ad35de49e886fc0ac1368d13e6343aeaec31dfb` |
| T02 | `docs/tech-debt/active/realtime-voice.md` | `CONTRACT`（REFERENCE_ONLY背景，非本期义务） / L11 TD-038；L56/72 TD-041/042 | `7e330dc366d622655ee52fb55c34375d8d28f855b03a0d66df1478bdabb17289` |
| D01 | `demos/bgm-v1.2/README.md` | `REPO_BASELINE` / L1–41 V1.3 范围、参数、模拟边界 | `a3bf9e6d35513601a506874e70d40088e469490ff43c39f14eb87b9bcaae4eb7` |
| D02 | `demos/bgm-v1.2/index.html` | `REPO_BASELINE` / L64–77 唱片/面板/两项气泡；L90–92 演示入口 | `d11d35604e0d4e63cfdfb197c787327666bf0c488e8ddb85e76f47e8caae35be` |
| D03 | `demos/bgm-v1.2/demo.js` | `REPO_BASELINE` / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | `cac3b6e021bcc4459c65761b15b042d772b9fd8f12782de82393cbcf439a1d03` |
| D04 | `demos/bgm-v1.2/admin.html` | `REPO_BASELINE` / L56 角色；L66–86 列表/上传/封面 | `3c9c1b0354d9749b03bc2dcce8029c9e71133a15cd2c463037b64d8fd50e7462` |
| D05 | `demos/bgm-v1.2/admin.js` | `REPO_BASELINE` / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | `320efb44697386bd241b0eff7d2f4091fc61115ed3f7001298813dfff6f4dcac` |
| D06 | `demos/bgm-v1.2/shared-catalog.js` | `REPO_BASELINE` / L4–10 参数；L82–126 本地目录；L131–243 图像预览 | `40f9b540736a161762d7d052cc03eb34cd6bb17c426493b0ad039d9c80707391` |
| D07 | `demos/bgm-v1.2/demo.css` | `REPO_BASELINE` / L7–19 第五格/面板/气泡/响应式/减少动态效果 | `6af8765a004b7702436515bb93400198626034aeed2717998729d14ab40d2436` |
| D08 | `demos/bgm-v1.2/record.css` | `REPO_BASELINE` / L32–99 通用黑胶；L171–200 长名/减少动态效果 | `7ae0b3e3d5db060b90ec72746b1fdd7b0445c64e6e63dcbd1efcd5878662949e` |
| D09 | `demos/bgm-v1.2/music-glass.css` | `REPO_BASELINE` / L10–22 磨砂；L75–205 控件/滤镜降级 | `0277f8a47a52152cbf5dab4c33a0210c99d49c012db181ccd90b53d98b6a01b3` |
| D10 | `demos/bgm-v1.2/v13.css` | `REPO_BASELINE` / L1–23 整图居中裁圆 | `c36655b2b6cd329b5ecee29f7805827a06abfc2363d1c8b033f8513318826406` |
| D11 | `demos/bgm-v1.2/admin.css` | `REPO_BASELINE` / L1–9 后台样式/响应式/分项反馈 | `4a64e624fc10da6ca8340f26afd51a355d2e4562e24127016929bf33aa5c02dc` |
| D12 | `demos/bgm-v1.2/verification.json` | `REPO_BASELINE` / L123–180 V1.3 增量与未验证范围 | `cb7f96865524a7e4e28cf5ae4cb263874dfc16f2ee596499ce83f489c1e415c1` |
| D13 | `demos/bgm-v1.2/preview.py` | `REPO_BASELINE` / 本地静态预览入口 | `677560a7edf74b3203841a19869b5b14cbf9894497c02c0b309c7fe2104bb9e2` |
| D14 | `demos/bgm-v1.2/preview-music-v13.png` | `REPO_BASELINE` / 已查看现有音乐面板截图；仅静态视觉证据 | `19a382b54b2634be96fd1317ffc3a29a14d41b73d56f1eaa6e51ac19fb5ad9a8` |
| D15 | `demos/bgm-v1.2/preview-admin-v13.png` | `REPO_BASELINE` / 已查看现有后台截图；仅静态视觉证据 | `94b923bdb38a3b4f9abd7ac318c8c243b5d765c1e49672896ea3e2e289074b0e` |
| B01 | `backend/utils/admin_auth.py` | `REPO_BASELINE` / L93–197 get_current_admin/require_role；L212–250 log_operation | `abc610225e389343c580e27787c925536f49b9c18626543fa0c852132a86ed6f` |
| B02 | `admin/static/js/admin-api.js` | `REPO_BASELINE` / adminRequest；MENU_CONFIG；observer 菜单派生 | `edd975154e650cf71c32ff9a5f85bdae60f547a296c2d56105a45883dbe26c9e` |
| B03 | `backend/services/feed_image_service.py` | `REPO_BASELINE` / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | `3548fb456467d6aaf2997bb13516f34864eed02fb4a56a10a97b221940785919` |
| B04 | `backend/config.py` | `REPO_BASELINE` / L224–242 OSS 配置名称；未读取真实凭证 | `105ef17583703a4925623ebdb237d3b3335837505c1dfdd75b4337cbf56e99f9` |
| B05 | `backend/redis_client.py` | `REPO_BASELINE` / L15–33 init_redis/get_redis：复用连接池，未有BGM缓存/超时/限流 | `59ada21a3d9648753be22ec5d10fe69d90104b5d6d4f933bfc24ac0b836b393a` |
| B06 | `backend/database.py` | `REPO_BASELINE` / L37–50 get_db：yield 后提交 | `7e9f08358358d7916875b279537042a3f9fd6dfc227b9bd102cd5c71fbc5b562` |
| B07 | `backend/main.py` | `REPO_BASELINE` / 路由注册；L268–273 admin_page 静态响应 | `e2749aec80f082baaee483fb07af4b9efcd69dffe1110766f6d7ee53e3f62dee` |
| B08 | `admin/pages/operation-logs.html` | `REPO_BASELINE` / 模块/动作筛选及操作日志渲染 | `429a0b71f4d2a0718dafda714cabc7c3c954e355373b6da668a07c897c5375b0` |
| B09 | `backend/routers/admin/operation_logs.py` | `REPO_BASELINE` / 操作日志查询 | `bb543dc2f931dc582a398562d811cba55d3574046b1e804d9bb33013584efc8d` |
| B10 | `Dockerfile` | `REPO_BASELINE` / L10–15 apt 依赖，无 FFmpeg | `b096b78c28678cbb3a68560e88eede2c44f0bbf1b2cbc32722703e70250856e2` |
| B11 | `nginx/nginx.conf` | `REPO_BASELINE` / 通用 API proxy_read_timeout 300s；无显式请求体大小/接收配置 | `0c467948f1d7b8d422b949ecf34af630a61fca5c6cd1b97db8ce91c1299b25c4` |
| B12 | `tests/test_step040_admin_page_inventory.py` | `REPO_BASELINE` / L10–23 EXPECTED_PAGES；L36–39 页数断言 | `4e78d94a5fccb8aeac2001312769f3f9307a706e09a8cd50bd1ef08e7ce364fb` |
| B13 | `tests/test_step028_admin_route_audit.py` | `REPO_BASELINE` / L163 固定路由数 | `f4b54dc1815a16e00e7f855710ef68961923795b1ee223a547c46af1ab54f8b1` |
| B14 | `tests/test_step039_observer_backend_gate.py` | `REPO_BASELINE` / L136–138 固定路由计数 | `386c63edd0262ebb200ae396b674cd102cc79d803409fb8f88f1776201578d95` |
| H01 | `frontend/pages/index.html` | `REPO_BASELINE` / L9–87 HomeStartup；L1468–1498/L1577–1585 more；L2092–2105 VoiceEntry.begin | `bf69846b016c14d2aecc1e32ebb5a307bf97dc17676410157b9d1508e82174fe` |
| H02 | `frontend/pages/settings.html` | `REPO_BASELINE` / L531–652 私有区；L654–688/707–749 设置；L1027–1055 退出 | `2409a7fb20f4428e57746c49641d12ec0105fa20a5dc4aae6b0ca99842fceea4` |
| H03 | `frontend/static/js/api.js` | `REPO_BASELINE` / L95–126 request默认Token；L171–185 clearToken；L294–426登录弹窗 | `2139ee79129bcdefd7c86d9dd44cc07f20d12a44a87906466731df241ed242c8` |
| H04 | `frontend/static/js/home-preferences.js` | `REPO_BASELINE` / L4–37/L40–114 motion本地/会话/内存降级及倾斜独立能力 | `8f3c4dd1cf101b9811a666c210b11b39915e6f5b74b6fdf59edfe4aa2d380052` |
| H05 | `frontend/static/js/home-scene.js` | `REPO_BASELINE` / L79–140/L411–434 场景可见性/bfcache/motion，非BGM生命周期 | `c6e164f1ba811978b43884f2411cd893767d7622221397d3439907f636c0fa1f` |
| H06 | `frontend/static/js/voice-entry.js` | `REPO_BASELINE` / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | `ac355a96679f3263020f2e06da9997ad6c0359949ef02f342f7f68a2817baf22` |
| H07 | `frontend/static/js/voice-playback.js` | `REPO_BASELINE` / VoicePlayback：通话输出所有权 | `ce9f6a7ae33729ba880c79ada7e042b887c568ecb5ae9ce215fb4281f688df54` |
| H08 | `frontend/pages/feed.html` | `REPO_BASELINE` / L443–471/555 图片预览；L1416–1479/1751 评论与页面接入 | `5b1b8d80892465836521f7992c876cdd37e0194cb7742dc8b7c075101e4150be` |
| H09 | `frontend/pages/diary.html` | `REPO_BASELINE` / L55–62/273/314–339 返回安全区及requireProtectedPage | `5334d28f473e1929b3029042cdce4d0b8b4ee28c03908385990df505c8960f0f` |
| H10 | `frontend/pages/memory.html` | `REPO_BASELINE` / L263–264/559–606 nebula底栏/抽屉；鉴权在H18 | `00f1f3ed522fe88a79b33c08dc69a33610e8f19c32aeae252a7b8e445d0ea8e5` |
| H11 | `frontend/pages/relationship.html` | `REPO_BASELINE` / L58–65/708–720/923–948/1342–1375 门禁/返回/levelup覆盖层 | `bd9a5c6fe49dfe1200ec398842706917bfdf40dd6b8537ed727c2da4d95c7de1` |
| H12 | `frontend/pages/chat.html` | `REPO_BASELINE` / L466–479/687–690/1647–1657/1861–1869 输入区/visualViewport/门禁 | `a00c5a2bb13396aab7b9f03b451b0b5206cace1d27bf877e1e1a10ca05265c61` |
| H13 | `frontend/pages/login.html` | `REPO_BASELINE` / L244 独立登录页共享api脚本 | `5f82f55d3a93522ac8e7de78cfd1aa00287fc7e5dc045fad4af47e0ff3e6b9be` |
| H14 | `tests/test_h5_static_contract.py` | `REPO_BASELINE` / L484–510 test_index_guest_mode_contract 旧 more 断言 | `59017bea27def6e7989672b3db2ea2ea424a1ce44592ab085ab690bba263e649` |
| H15 | `tests/test_home_preferences.cjs` | `REPO_BASELINE` / L88–93 旧更多互动断言 | `e75d272688c17a55e7e771b166d801a6763b0a81a73b82418480a6b9b39bbb87` |
| H16 | `tests/test_home_scene_boundaries.cjs` | `REPO_BASELINE` / L10 旧 more 访客门禁断言 | `5f53f16d80125705498f58b64d9782827ac6f98b76df0c54a3320b1f27d58d68` |
| B15 | `backend/models/__init__.py` | `REPO_BASELINE` / L4–104 全模型注册，当前无BGM | `b665d9d2dae74a8e559a35afd2cc789c0db5f83aa64c465f55db08e0a0e72cd3` |
| B16 | `alembic/env.py` | `REPO_BASELINE` / L9–24 metadata与模型导入；L41–49 online入口 | `a6d279aedd2b7678598f4afb185109d594ee07b325ffd73a83e5439ce9c21a41` |
| B17 | `alembic/versions/v9g_memory_diagnostic.py` | `REPO_BASELINE` / L3–4 revision/down_revision；静态唯一head | `b8b45947fc138b2a4d47c2e4c44ace0ef44bf9ad8d086cf0b938a4c51d629108` |
| B18 | `docker-compose.yml` | `REPO_BASELINE` / L44–68 backend环境与挂载；L7 迁移约定 | `f97eb1f59a8ecd769cb55f3b8f8a5e50190be41fe6d78dc4b0acf6a8a0aae076` |
| B19 | `requirements.txt` | `REPO_BASELINE` / multipart/Alembic/Redis/Pillow/oss2/pytest声明 | `af29a8d466e638e430c0c095b185cc316921873ab13b2417421e1bb064da8e2a` |
| B20 | `backend/models/admin_operation_log.py` | `REPO_BASELINE` / L13–42 字段长度、UTC及留存 | `6e44c510356bc347ca2397561b2d9b4eeaa1ac8c5bb20e1de5be74d8028dfc23` |
| B21 | `admin/static/js/life-feed-admin.js` | `REPO_BASELINE` / L46–61 默认S/A页面门禁不可照搬BGM | `6855db8023aa3c7c6a5a0bf86ad4fa235176c9b14ae3454a5981fed16d85419f` |
| H17 | `frontend/static/js/voice-audio-transport.js` | `REPO_BASELINE` / L9–24、L53–74 通话媒体所有权与close | `fbf7e4c6fdab16371e76d27d2eb8ca18d2961340602cb001623d46d7c0bc43b9` |
| H18 | `frontend/static/js/memory-nebula.js` | `REPO_BASELINE` / L53–54 requireProtectedPage；L800–815 抽屉；L1073 pagehide | `17e7ed6eed222aa8fc47063bf6934fe0649f3db184a3076ba659f9fa0cca075c` |
| H19 | `frontend/static/css/h5-theme.css` | `REPO_BASELINE` / L531–585 登录遮罩层级与安全区 | `5c9da523ef003d9d676c509c38c1d9591c617deff255f92df5a6a60dd242c4f9` |
| V01 | `tests/test_admin_auth.py` | `REPO_BASELINE` / 现有Admin授权专项入口；未运行 | `5aa4d92f2192472ca1353d7c7d28778799afcbc47aeb9d36a0c489decf82a49f` |
| V02 | `tests/test_step012_feed_image.py` | `REPO_BASELINE` / 现有图片服务回归入口；未运行 | `417a5c5508909738431e11d0d444e85b2d1605273fb9309362aaa9b739df7cfa` |
| V03 | `tests/test_step012_operation_log_redaction.py` | `REPO_BASELINE` / 现有日志脱敏回归入口；未运行 | `bb2732024ffec9974ee47aca08f403e6d78e4dc5ab7efc4caa5e7d6ccd710475` |
| V04 | `tests/test_step029_observer_frontend_common.py` | `REPO_BASELINE` / observer前端共用权限回归入口；未运行 | `9a899708a1cd5abf3afebdd3f7e9a20adf352504a6c93894e802f0d1203e3c81` |
| V05 | `tests/test_realtime_voice_step001_admin_config_migration.py` | `REPO_BASELINE` / L25–31/L119–123 静态迁移与隔离库开关范式 | `4d098741dd3cfde0fe4f9230f70f52cc9d729b60df73e53ea280603e8fc80e2b` |
| V06 | `tests/test_realtime_voice_nginx_runtime.py` | `REPO_BASELINE` / L13/L65–80 opt-in隔离Nginx探针范式 | `ce50969dc9e68d3fa814f0165236fcec6917487683fb7d2801274271dae2e601` |
| V07 | `tests/test_home_preference_failures.cjs` | `REPO_BASELINE` / 浏览器存储失败回归；未运行 | `0b356d431623cc23f0c3dc0201d2c322abb8044f6bdc555ed0e7e6caf8ea892f` |
| V08 | `tests/test_home_panels.cjs` | `REPO_BASELINE` / 现有面板回归；未运行 | `5dc7ba1ea9b5c7e02f8f7e88e095139af0449b64250241f4ac81662055633d68` |
| V09 | `tests/test_realtime_voice_step036_permission.cjs` | `REPO_BASELINE` / 权限流程回归；未运行 | `6c96d4fe0e7dc31e9fea4d23428df6bac811aac3b5ef4919be5bca6a3f5c1d80` |
| V10 | `tests/test_realtime_voice_terminal_result.cjs` | `REPO_BASELINE` / 终态结果回归；未运行 | `21ff733b8f196cdb897f8a887d2823c637cc1ab2c603e482f25e44cf2afaafc2` |
| V11 | `tests/test_realtime_voice_replay_lifecycle.cjs` | `REPO_BASELINE` / 重放生命周期回归；未运行 | `3ea3eaef6ae73fd7be29cdef7de9535c6173791da2ee744f34a18af994a191da` |
| V12 | `tests/test_realtime_voice_step038_duplicate_actions.cjs` | `REPO_BASELINE` / 重复操作回归；未运行 | `1739f2d4cf9a5ce3e585b19f86a318bb5900ca51800e2308b55df70276dcbbf7` |
| V13 | `tests/home_browser_helpers.cjs` | `REPO_BASELINE` / 浏览器脚本/Playwright入口 | `83dcfcd1fcfbfb0a6a7bd492687229630ae2a9c115f6650e4d505646333c1110` |
| V14 | `tests/conftest.py` | `REPO_BASELINE` / 测试环境与隔离前提；未执行 | `9781490592df0caf76a6f76bbd8a758fb982c393057b00f438c1052238705fdb` |
| B22 | `.env.example` | `REPO_BASELINE` / L93–99 OSS空模板；只核实名称，不证明真实配置 | `00d7cf80fab4df1b00c740058167b0e1aa0a611d467c3e32ddb5c16497a88937` |
| H20 | `backend/utils/auth_middleware.py` | `REPO_BASELINE` / L44–64 get_current_user/get_current_user_optional 为路由依赖，无全局BGM白名单 | `c0a4962340a603345fc53c7ae947a9b5c751af21f86768a674089863f1544e5c` |
| B23 | `backend/routers/admin/feed_mgmt.py` | `REPO_BASELINE` / delete_post L209–224隐藏型DELETE；PostCreateBody/create_post L253–312已有image_urls录入，非本地文件上传 | `e3bed0161e3eecba0393b00da3bfa059df246d545e1a9b8e1b368a65fd97c911` |

### 3.2 planned / unverified发现门

| 对象 | 状态/来源 | 发现与退出条件 |
| --- | --- | --- |
| BGM表/字段/错误码/API/新增文件和测试名 | `planned` / `PLANNED` | STEP-001按C01/B01/B06/B15/B16/B17核实并登记；禁止把建议路由或数值直接当契约。采用Alembic时处理create_all排除/缺迁移检查 |
| BGM匿名请求方式 | `planned` / `PLANNED` | STEP-007/012显式无用户Token；H03默认自动附Token，不能无条件沿用 |
| BGM管理页/菜单及直接访问守卫 | `planned` / `PLANNED` | STEP-002按B02/B07增加BGM专属角色矩阵；现有HTML静态返回不等于已有服务端页面权限 |
| 语音准备/清理hook | `planned` / `PLANNED` | STEP-016补真实归属化生命周期，不能引用尚不存在的voice lifecycle事件名 |
| 实际Bucket/CDN/权限/资源头/处理运行依赖 | `unverified` / `UNVERIFIED` | STEP-020在授权验收环境实测；B04只证明配置名，不证明值/资源可用 |
| 实际终端输出/降级/准备及缓存效果 | `unverified` / `UNVERIFIED` | STEP-020/021按H5-M/H5-D矩阵取证；demo/源码不能豁免 |
| 新BGM专项测试/浏览器网络证据 | `planned` / `PLANNED` | 各STEP新增必要用例与证据；不得声称已有专测或本轮运行通过 |

关键的新能力仍是计划实现对象，不是既有运行能力。本文由只读原稿`steps-draft.md`经两轮候选修复与完整复审签发，最终候选为`steps-candidate-r2.md`，SHA256：`af4197246f60b00e20b41445846c1518ae81b97665866f20131caaaedfbbe35b`。85项来源与候选绑定的source_digest为`297226ae68589312c7c12f5319827f2c106c3266ee4a541fa8e851f95be748a8`；算法及原稿/候选/签发摘要记录在`step-audit.md`。B23仅补代码回归风险锚点，没有新增需求或技术债承接。当前文档状态`STEPS_VERIFIED`；实际能力仍须按各STEP完成门验证。

## 4. STEP总览与显式依赖

本文档已完成本轮完整复审；后续实施须有相应用户授权。编号仅供定位，依赖以下表为准。前置产物没有完成证据时停止相应STEP，可推进不受影响的分支；不以“已经有文件”代替前置完成。

| STEP | 单一目标 | 前置STEP | 直接验收ID |
| --- | --- | --- | --- |
| STEP-001 | 确定技术接入与参数验证记录 | 无 | AC-100 |
| STEP-002 | 建立 BGM 管理访问与只读查询边界 | STEP-001 | AC-054、AC-055 |
| STEP-003 | 完成音频上传到就绪及失败恢复 | STEP-001、STEP-002 | AC-054、AC-055、AC-056、AC-057、AC-062、AC-066、AC-067、AC-068、AC-069、AC-070、AC-071、AC-072、AC-073、AC-074、AC-086 |
| STEP-004 | 维护唯一默认和原子有序歌单 | STEP-002、STEP-003 | AC-054、AC-056、AC-058、AC-059、AC-060、AC-061、AC-066 |
| STEP-005 | 维护每曲可选封面并隔离音频版本 | STEP-001、STEP-002、STEP-003、STEP-004 | AC-054、AC-062、AC-073、AC-079、AC-083、AC-084、AC-085、AC-086、AC-087、AC-088、AC-089 |
| STEP-006 | 完成等期手动删除与专属资产清理 | STEP-003、STEP-004、STEP-005 | AC-054、AC-063、AC-064、AC-065、AC-072、AC-073、AC-089、AC-090、AC-091 |
| STEP-007 | 提供匿名一致目录与受控服务端缓存 | STEP-002、STEP-004、STEP-005、STEP-006 | AC-045、AC-053、AC-060 |
| STEP-008 | 接通 BGM 审计及既有日志筛选 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007 | AC-060、AC-077、AC-083、AC-089 |
| STEP-009 | 实现五项本地偏好与公开设置 | STEP-001 | AC-014、AC-015、AC-016、AC-017、AC-018、AC-019、AC-077 |
| STEP-010 | 实现单文档播放意图和顺序控制 | STEP-009 | AC-006、AC-007、AC-008、AC-020、AC-025 |
| STEP-011 | 实现真实增益、淡入淡出和能力降级 | STEP-009、STEP-010 | AC-023、AC-024、AC-026、AC-027 |
| STEP-012 | 接入事件目录与统一有限故障链 | STEP-007、STEP-010、STEP-011 | AC-009、AC-028、AC-029、AC-030、AC-046、AC-047、AC-048、AC-050、AC-051、AC-052、AC-059 |
| STEP-013 | 实现独立页面生命周期和会话恢复 | STEP-009、STEP-010、STEP-011、STEP-012 | AC-021、AC-022、AC-031、AC-032、AC-033、AC-034、AC-035、AC-036、AC-040、AC-044 |
| STEP-014 | 接入主页唱片、面板和统一封面显示 | STEP-010、STEP-011、STEP-012、STEP-013 | AC-001、AC-002、AC-003、AC-004、AC-005、AC-006、AC-007、AC-008、AC-009、AC-015、AC-017、AC-019、AC-079、AC-080、AC-081、AC-082、AC-084、AC-085 |
| STEP-015 | 接入六类页面右侧悬浮唱片 | STEP-013、STEP-014 | AC-001、AC-010、AC-011、AC-012、AC-013、AC-080 |
| STEP-016 | 在真实通话准备和清理边界互斥 BGM | STEP-010、STEP-011、STEP-013、STEP-014、STEP-015 | AC-037、AC-038、AC-039 |
| STEP-017 | 提供短 TTS 活动衰减与可控模拟 | STEP-010、STEP-011、STEP-013、STEP-016 | AC-041、AC-042 |
| STEP-018 | 接入普通带声媒体和录音临时互斥 | STEP-013、STEP-015、STEP-016 | AC-043 |
| STEP-019 | 实现至多一个无声下一首准备 | STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017、STEP-018 | AC-049、AC-077、AC-085、AC-092、AC-093、AC-094、AC-095、AC-096、AC-099 |
| STEP-020 | 核验实际部署媒体与 HTTP 缓存链路 | STEP-003、STEP-005、STEP-006、STEP-007、STEP-011、STEP-013、STEP-016、STEP-019 | AC-070、AC-074、AC-075、AC-076、AC-086、AC-097、AC-098 |
| STEP-021 | 执行完整业务验收并交付证据 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017、STEP-018、STEP-019、STEP-020 | AC-078、AC-100 |

可独立推进的分支：STEP-002后台访问与STEP-009本地设置都只依赖STEP-001；STEP-003～008逐步形成后台全链，STEP-010/011可先用可注入有效目录验证控制。STEP-012起接入真实公开目录。该说明不改变表中的依赖，也不授权本轮并行开发。

## 5. 需求与验收覆盖映射

### 5.1 业务规则 → STEP

下表每行保留一个BR。对应STEP只承担正文中明确的条款/子条款；共同涉及同一BR时以正文范围分工为准，不能据映射扩大任务。

| 需求ID | PRD规则准确摘要 | 直接负责STEP | 来源定位 |
| --- | --- | --- | --- |
| BR-001 | 公共音乐对访客开放；原页面权限照常执行 | STEP-007、STEP-014、STEP-015 | P01 L488 |
| BR-002 | 替换第五格；实际播放显示曲名和播放态；主页无重复气泡 | STEP-014 | P01 L489 |
| BR-003 | 只改变界面；控制状态一致，手势和焦点正确 | STEP-014 | P01 L490 |
| BR-004 | 按有效顺序；暂停时下一首只选择；仅手动行为更新最后手选 | STEP-010 | P01 L491 |
| BR-005 | 同款气泡提供播放／暂停、本次关闭；临时失败保留恢复入口 | STEP-015 | P01 L492 |
| BR-006 | 右侧吸附，位置归一化及安全区约束；覆盖层按最新状态恢复控件 | STEP-015 | P01 L493 |
| BR-007 | 两个 BGM 开关在公开区；原主页动效沿用原权限 | STEP-009 | P01 L494 |
| BR-008 | 五项偏好仅同源浏览器本地，共用本机值 | STEP-009、STEP-014 | P01 L495 |
| BR-009 | 使用字段默认与校验；本地→会话→内存逐级降级并说明范围 | STEP-009 | P01 L496 |
| BR-010 | 复用现有持久化键和人物／场景语义 | STEP-009、STEP-014 | P01 L497 |
| BR-011 | 开关只决定无会话时的初始意图，任一允许页均适用 | STEP-009、STEP-013、STEP-014 | P01 L498 |
| BR-012 | 初始化按有效会话→有效最后手选→默认→第一首→空态；运行中目录更新发现当前失效按 BR-028 回退默认／第一首 | STEP-010、STEP-012 | P01 L499 |
| BR-013 | 意图、实际状态、关闭及阻断分离，出声前重检 | STEP-010、STEP-013 | P01 L500 |
| BR-014 | 立即停止并记会话关闭；仅主页明确播放／列表选曲重开 | STEP-010、STEP-013、STEP-016 | P01 L501 |
| BR-015 | 默认按开关渐变；暂停意图立即生效，切歌先停旧再播新 | STEP-011、STEP-014 | P01 L502 |
| BR-016 | 增益真实有效；零值可靠静音；设备音量降级保留明确取消静音入口，用户操作后才将零值改为默认非零值 | STEP-011、STEP-017 | P01 L503 |
| BR-017 | 最新有效操作胜出，旧任务及动画回调失效 | STEP-010、STEP-013、STEP-016 | P01 L504 |
| BR-018 | 区分权限与资源故障，按总预算有限尝试，保留人工恢复 | STEP-012 | P01 L505 |
| BR-019 | BGM 软依赖；加载层及正文共用控制器，已发声可暂停 | STEP-013 | P01 L506 |
| BR-020 | 可用会话存储保留意图、关闭和合法检查点；初始化检查读写可靠性，同页单实例，跨文档恢复 | STEP-013 | P01 L507 |
| BR-021 | 隐藏立即暂停，返回先对账再条件恢复 | STEP-013 | P01 L508 |
| BR-022 | 登录页临时暂停，普通弹窗不改意图；回允许页重检 | STEP-013 | P01 L509 |
| BR-023 | 麦克风与通话输出前停止 BGM、关闭本次并阻断；结束只清阻断 | STEP-016 | P01 L510 |
| BR-024 | 临时衰减，按活动 ID 去重释放；最后一路结束才条件恢复 | STEP-017 | P01 L511 |
| BR-025 | 显式媒体互斥临时暂停；系统异常保守等待真实许可 | STEP-018 | P01 L512 |
| BR-026 | 只返启用且就绪内容与完整版本，匿名且无用户 Token | STEP-007 | P01 L513 |
| BR-027 | 事件触发、新鲜复用、在途合并，失败不更新成功时间 | STEP-012 | P01 L514 |
| BR-028 | 失效当前曲按意图回退；空目录允许静默；排序仅影响后续 | STEP-012 | P01 L515 |
| BR-029 | 缓存失效／更新并保留有限 TTL；回源受控，快照一致 | STEP-007 | P01 L516 |
| BR-030 | 两个管理角色全权、观察者只读试听，另两个角色无管理访问 | STEP-002 | P01 L517 |
| BR-031 | 就绪仍未启用，人工试听后主动启用；后台试听独立 | STEP-003、STEP-004 | P01 L518 |
| BR-032 | 非空有效歌单恰好一个默认，空则默认空；目录变更保持完整一致的版本 | STEP-004、STEP-005 | P01 L519 |
| BR-033 | 原操作可定位和查询，重复提交去重；同标识同内容复用、异内容冲突；处理重试关联原曲目 | STEP-003、STEP-004、STEP-005 | P01 L520 |
| BR-034 | 当前隐藏且满服务器等待期才删；重隐藏重计；未发布且无活动处理可直接清理 | STEP-006 | P01 L521 |
| BR-035 | 删除期间不可发布；音频和专属封面分别可定位，部分失败保持删除未完成并支持手动重试 | STEP-006 | P01 L522 |
| BR-036 | 服务端校验真实类型、解码、体积、时长和字段 | STEP-003 | P01 L523 |
| BR-037 | AAC-LC／M4A、目标 96 kbps、完整发布文件 ≤4 MiB；采样／声道／编码器按经验证的实现检查 | STEP-003 | P01 L524 |
| BR-038 | 并发、接收、处理与资源占用有明确有限边界，不影响主业务；子步骤服从实际采用的总预算 | STEP-003、STEP-020 | P01 L525 |
| BR-039 | 操作结果及执行资格可核对；旧结果失效，过期工作有收尾；只清理本模块无有效执行者的临时资源 | STEP-003、STEP-005 | P01 L526 |
| BR-040 | 唯一版本路径，实际写入及远端读取验证后才就绪，音频与图像处理独立 | STEP-003、STEP-020 | P01 L527 |
| BR-041 | 记录操作者、音频／封面动作、对象、结果、操作关联与版本；BGM 筛选含封面新增／替换／移除与清理 | STEP-008 | P01 L528 |
| BR-042 | 本期仅预留事件与本地调试，不新建采集管线 | STEP-008、STEP-009、STEP-014 | P01 L529 |
| BR-043 | 区分已确认规则与建议；研发／测试记录实际采用参数、方式、适用环境和证据，验收按已确认结果及实际配置执行 | STEP-001、STEP-020、STEP-021 | P01 L530 |
| BR-044 | 复用现有朋友圈 Bucket；音频／封面分目录归属；优先复用并验证 CDN | STEP-003、STEP-005、STEP-020 | P01 L531 |
| BR-045 | 服务端自动生成 Key 与访问 URL，保存可清理定位；新资源不覆盖旧地址；音频与封面各自版本化 | STEP-003、STEP-005、STEP-020 | P01 L532 |
| BR-046 | 每曲最多一张静态封面，非必填；两个管理角色可维护，观察者只读；无图用默认图 | STEP-005 | P01 L533 |
| BR-047 | 整图居中圆形显示，播放旋转、暂停停止；首页／面板／气泡统一当前封面，异常回退内置通用黑胶 | STEP-014、STEP-015 | P01 L534 |
| BR-048 | 直接保存无需先隐藏；成功后按原目录更新时机生效，图像更新不影响音频运行 | STEP-005 | P01 L535 |
| BR-049 | 新图保存成功才替代旧关联；失败留旧图，无图或加载失败用默认；版本／权限／曲目状态核对 | STEP-005、STEP-014 | P01 L536 |
| BR-050 | 隐藏保留图；替换／移除保留旧对象清理依据；删曲清理所有仍归属该曲且需清理的专属资产，部分失败可重试 | STEP-006 | P01 L537 |
| BR-051 | 当前曲按需缓冲；当前确在播放时至多轻量准备一个有效下一首候选，不抢占当前播放 | STEP-019 | P01 L538 |
| BR-052 | 预加载不发声、不改用户设置／意图；实际播放前重检资格、目录与阻断 | STEP-019 | P01 L539 |
| BR-053 | 停止新准备、尽力取消并忽略旧结果；不支持／不合适可跳过，失败不影响当前曲，实际切歌走普通流程 | STEP-019 | P01 L540 |
| BR-054 | 使用浏览器 HTTP 缓存并核对真实表现；未命中时正常请求；缓存头与期限按验证后的配置 | STEP-019、STEP-020 | P01 L541 |
| BR-055 | 当前资源与准备候选按版本和目录资格分别核对；只换封面不使音频缓存无故失效 | STEP-019、STEP-020 | P01 L542 |

### 5.2 验收 → STEP

每条AC至少有一个直接负责人。重复映射只分割可以独立验证的子条款，下列范围标注与各STEP正文共同构成职责边界；完整验收仍须满足PRD原句和环境。STEP-021仅负责AC-078/100的最终闭环及总核对，不把其他98项再次泛映射到“集成”。

| 验收ID | PRD输入/动作 | 负责STEP及实际条款范围 | 来源/环境 |
| --- | --- | --- | --- |
| AC-001 | 访客在公开页面手动播放，并尝试访问原受保护页 | STEP-014：主页公共播放与原四格/私有门禁; STEP-015：六类内容/设置页公共音乐与原页面/私有数据门禁 | P01 L648；H5-M、H5-D、API |
| AC-002 | 查看主页快捷入口及关系入口 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L649；H5-M、H5-D |
| AC-003 | 播放、暂停、缓冲、拦截及音量置零 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L650；H5-M、H5-D |
| AC-004 | 播放或关闭后反复打开／收起面板、点遮罩、返回 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L651；H5-M、H5-D |
| AC-005 | 小屏、横屏、长列表、键盘操作及系统减少动态效果 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L652；H5-M、H5-D |
| AC-006 | 点击新曲、正在播放当前行、暂停当前行 | STEP-010：控制核心的选行语义; STEP-014：真实主页列表点击接线 | P01 L653；H5-M、SIM |
| AC-007 | 播放与暂停中分别手动下一首，跨列表末尾 | STEP-010：控制核心播放/暂停下一首与回首; STEP-014：面板下一首实际接线 | P01 L654；H5-M、SIM |
| AC-008 | 仅一首，点击下一首并等待自然播完 | STEP-010：单曲禁用与自然曲终复核入口; STEP-014：主页单曲控件及真实目录接线 | P01 L655；H5-M、SIM |
| AC-009 | 分别返回有效空目录、目录暂时失败、所有音频失败 | STEP-012：有效空/暂时目录故障/全部音频失败三类与有界恢复; STEP-014：三种状态主页空态/失败反馈与控制可用性 | P01 L656；H5-M、SIM |
| AC-010 | 进入朋友圈、日记、记忆、关系、聊天、设置 | STEP-015：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L657；H5-M、H5-D |
| AC-011 | 气泡点空白收起、暂停、关闭本次，随后进设置 | STEP-015：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L658；H5-M、SIM |
| AC-012 | 拖动、切页、旋转、聊天弹键盘、不同底栏 | STEP-015：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L659；H5-M |
| AC-013 | 打开图片／登录覆盖层，期间关闭后再关覆盖层 | STEP-015：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L660；H5-M、SIM |
| AC-014 | 访客进入设置并修改两个 BGM 开关 | STEP-009：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L661；H5-M、H5-D |
| AC-015 | 修改五项，登录 A、退出、登录 B、同浏览器再访问 | STEP-009：五项本地字段读写/持久化无账号分区、公开设置、模块不请求偏好API或上报；STEP-014：正式音量/手选/开关/motion逐项修改后登录A→退出→登录B→同浏览器再访问，核对五项值及实际音量/选曲不被账号操作重置，网络无偏好上报 | P01 L662；H5-M、H5-D、API 网络检查 |
| AC-016 | 清站点数据、新浏览器及不同设备同账号进入 | STEP-009：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L663；H5-M、H5-D |
| AC-017 | 正在播放时关自动播放，暂停／关闭时开渐变和自动播放 | STEP-009：设置读写仅改偏好，模块不主动发播放/暂停/关闭命令；STEP-014：正式播放器播放中关自动播放不停播，暂停/关闭时开渐变与自动播放不出声，后续无旧会话新访问采用设置；可复用STEP-013新访问证据，014仍负责正式接线 | P01 L664；H5-M、SIM |
| AC-018 | 单字段损坏、未知版本、local 失败、session 也失败 | STEP-009：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L665；SIM、H5-M |
| AC-019 | 修改主页动效，检查原键和倾斜权限，播放 BGM | STEP-009：原motion键/原权限/人物场景范围/倾斜独立性兼容，模块不改BGM偏好或发播放命令；STEP-014：正式页面改motion时真实BGM不中断，音乐渐变开关和值保持，仍核对原键/原权限/倾斜独立性 | P01 L666；H5-M、静态核对 |
| AC-020 | 手选、暂停下一首、自然切歌、后台使历史曲失效 | STEP-010：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L667；SIM、存储检查 |
| AC-021 | 没有旧会话，直接进入每个允许页，分别开／关自动播放 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L668；H5-M、H5-D |
| AC-022 | 已暂停或关闭，刷新／跳页／改开关／换账号 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L669；H5-M、SIM |
| AC-023 | 正常能力环境渐变开，开始、暂停、继续 | STEP-011：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L670；H5-M、音频输出检查 |
| AC-024 | 渐变开／关分别切歌；暂停中下一首；过渡中改开关 | STEP-011：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L671；H5-M、SIM |
| AC-025 | 快速播放／暂停／多次切歌，延迟旧请求，再关闭 | STEP-010：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L672；SIM、H5-M |
| AC-026 | 注入渐变不可用并验证各实际浏览器降级路径 | STEP-011：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L673；H5-M、SIM |
| AC-027 | 增益有效和仅设备音量两种路径，测试已保存零音量后明确取消静音 | STEP-011：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L674；H5-M |
| AC-028 | 自动播放／AudioContext 被阻止，点击页面非音乐区域，再明确播放 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L675；H5-M、H5-D |
| AC-029 | 自动候选失败、手选新曲失败后暂停／关闭 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L676；SIM、网络故障注入 |
| AC-030 | 播放中持续缓冲或输出上下文挂起，期间暂停／关闭 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L677；H5-M、SIM |
| AC-031 | 加载层音乐先好、页面先好、目录失败、音频超时各一次 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L678；H5-M、H5-D |
| AC-032 | 正在播放跳转独立页面，浏览器分别允许／拦截恢复 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L679；H5-M |
| AC-033 | 负数／越界／非数进度、媒体版本变更、离开一段时间 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L680；SIM |
| AC-034 | 关闭后刷新、后退缓存恢复，触发旧媒体及动画回调 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L681；H5-M、SIM |
| AC-035 | sessionStorage 不可读，或可读旧状态但新状态不可写，跳页或刷新 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L682；SIM、H5-M |
| AC-036 | 播放／暂停／关闭时分别切后台、锁屏后返回 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L683；H5-M |
| AC-037 | 使用目标分支真实语音入口进入准备和麦克风申请 | STEP-016：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L684；DEP、实际语音与时序记录 |
| AC-038 | 未登录、不支持的微信语音能力、占位视频入口分别触发 | STEP-016：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L685；H5-M、DEP |
| AC-039 | 准备取消、拒绝权限、连接失败、重连、单轮回复结束、挂断 | STEP-016：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L686；DEP、SIM |
| AC-040 | 播放中进入独立登录页／登录弹窗，账号改变后返回 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L687；H5-M、H5-D |
| AC-041 | 模拟短 TTS 开始，期间调音量并结束；无衰减能力再测 | STEP-017：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L688；SIM、H5-M 输出能力验证 |
| AC-042 | 模拟两路短 TTS、重复结束、取消、销毁、超时及用户关闭 | STEP-017：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L689；SIM，非独立 TTS 业务验收 |
| AC-043 | 显式带声媒体／录音互斥、无声视频、系统音频中断 | STEP-018：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L690；SIM、H5-M |
| AC-044 | 两个标签页、复制已关闭标签页、浏览器会话恢复 | STEP-013：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L691；H5-D、H5-M |
| AC-045 | 访客／登录请求目录，包含有图／无图曲目 | STEP-007：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L692；API、H5 网络检查 |
| AC-046 | 页面静置，越过实际采用的目录 TTL／新鲜期，未发生曲终等触发 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L693；网络记录、SIM |
| AC-047 | 有播放需要跳页，缓存内／过期分别初始化，多事件同时触发 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L694；SIM、H5 网络检查 |
| AC-048 | 暂停／关闭／隐藏后缓存过期，再主动打开面板 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L695；SIM、网络检查 |
| AC-049 | 当前播放及符合条件的下一首准备，检查网络 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L696；H5-M、网络检查 |
| AC-050 | 改默认、名称、排序、封面及隐藏当前曲，客户端取得新目录 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L697；API、H5-M、SIM |
| AC-051 | 隐藏最后一首，客户端下次事件取得空目录 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L698；API、H5-M |
| AC-052 | 以实际采用预算／候选上限注入失败、目录超龄，再触发冷却后自然事件、跳页或手动恢复 | STEP-012：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L699；SIM、网络与计时记录 |
| AC-053 | Redis 不可用、失效失败、缓存到 TTL 后读取 | STEP-007：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L700；API、DEP |
| AC-054 | 五角色访问菜单、页面、读取、音频／封面写入及试听／预览 | STEP-002：菜单、直链页面、管理只读及共用授权；具体写操作在其负责STEP; STEP-003：音频上传/处理重试的写权限与observer试听读取; STEP-004：改名/启用/隐藏/默认/排序写权限; STEP-005：封面读取/预览和写权限; STEP-006：删除及删除失败重试写权限 | P01 L701；API、Admin UI |
| AC-055 | 只读 GET、观察者请求状态、处理中角色被撤销后写入 | STEP-002：所有已接入只读GET及共用提交鉴权；处理接口见STEP-003; STEP-003：音频接纳/重试/完成提交重新授权，状态GET不写恢复 | P01 L702；API、记录副作用检查 |
| AC-056 | 按实际验证的名称上限 N 测试空白、1／N／N+1、重名与控制字符及伪造字段 | STEP-003：上传名称边界与客户端伪造音频状态/路径拒绝; STEP-004：改名边界与目录字段/伪造状态拒绝 | P01 L703；API、Admin UI |
| AC-057 | 观察者及管理员试听两首，离开管理页；同时检查用户端 | STEP-003：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L704；Admin UI、存储检查 |
| AC-058 | 空库首次启用、非空时启用、隐藏默认或最后一首，再重新启用 | STEP-004：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L705；API |
| AC-059 | 合法排序以及重复、缺失、未知、未启用 ID 排列 | STEP-004：API完整排列原子提交及重复/缺失/未知/未启用ID拒绝; STEP-012：取得新排序后有效当前曲不重启，后续按新顺序切歌 | P01 L706；API、H5-M |
| AC-060 | 管理修改已提交，注入缓存失效错误或响应丢失 | STEP-004：目录事务/操作/必要审计可核对，响应丢失不重建; STEP-007：目录提交后的Redis失效失败返回真实已提交结果; STEP-008：缓存失败/丢响应的日志结果关联与筛选核对 | P01 L707；API、日志核对 |
| AC-061 | 两管理员用同一旧版本并发设默认、排序、隐藏 | STEP-004：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L708；API 并发验证 |
| AC-062 | 对音频上传／封面写入重复提交，同标识异内容，首响应丢失后查询重试 | STEP-003：音频上传/重试稳定操作查询、去重及异内容冲突; STEP-005：封面操作稳定查询、去重及异内容冲突 | P01 L709；API、Admin UI |
| AC-063 | 按实际等待期 T 测试启用中、隐藏不足 T、恰好 T、超过 T | STEP-006：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L710；API、时钟控制测试 |
| AC-064 | 隐藏满期不点击；重启用再隐藏；清理未发布失败素材 | STEP-006：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L711；API、DEP |
| AC-065 | 音频／专属封面删除部分失败、对象不存在、CDN 有副本，期间尝试启用 | STEP-006：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L712；API、OSS 验证 |
| AC-066 | 四类允许源文件完成处理，尝试自动／手动发布未就绪资源 | STEP-003：四类源文件处理、成功就绪仍未启用、无自动发布；STEP-004：真实手动启用入口拒绝处理中/失败/未验证资源，合法就绪仅明确人工动作后启用 | P01 L713；API、Admin UI |
| AC-067 | 空文件、非音频改后缀、MIME／内容不符、损坏、超体积 | STEP-003：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L714；API |
| AC-068 | 源体积恰限／超限，时长 0／300s／超限，输出恰限／超限 | STEP-003：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L715；API、媒体样本 |
| AC-069 | 核对允许源文件转码结果，含内嵌图／视频源，检查实际技术参数 | STEP-003：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L716；媒体探测、样本试听 |
| AC-070 | 多实例并发超过实际采用的处理上限，包含音乐与封面操作 | STEP-003：采用处理器的全部署并发限制及故障注入; STEP-020：真实多实例部署含封面操作的总资源边界 | P01 L717；API、DEP |
| AC-071 | 上传响应丢失／刷新、服务进程退出、查询处理中记录 | STEP-003：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L718；API、DEP、Admin UI |
| AC-072 | 失败后带新源重试，旧 attempt 在新尝试或删除后迟到 | STEP-003：带新源关联原曲目重试及旧attempt在新尝试后迟到隔离; STEP-006：删除后迟到旧attempt不得就绪或发布 | P01 L719；API、故障注入 |
| AC-073 | 对音频／封面注入 OSS 与数据库单侧成功、操作定位失败或删除部分成功 | STEP-003：音频对象/操作/数据库单侧成功与补偿定位; STEP-005：封面对象/关联/数据库单侧成功与补偿定位; STEP-006：音频及封面删除部分成功的剩余定位与恢复 | P01 L720；API、OSS、数据库核对 |
| AC-074 | 慢接收、转码挂起、OSS 挂起、异常中止或多实例启动恢复 | STEP-003：处理器绝对预算/执行资格/终止回收/受控恢复逻辑; STEP-020：实际慢接收/转码/OSS/进程退出与多实例恢复实证 | P01 L721；DEP |
| AC-075 | 实际 CDN 播放、跨域音频图、Range 恢复，注入错误 MIME／CORS | STEP-020：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L722；H5-M、API、DEP |
| AC-076 | 按选定实现检查依赖、慢上传、解析、内存、代理等待与磁盘不足 | STEP-020：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L723；DEP |
| AC-077 | 音频和封面全部管理动作／部分清理失败，查看日志筛选与 H5 网络 | STEP-008：音频/封面/清理及拒绝写入的后台审计、筛选和脱敏; STEP-009：本地偏好/设置诊断不发服务端，不带五项偏好; STEP-019：新增准备/图片等H5诊断只在本地，网络不上传用户偏好 | P01 L724；API、日志、网络检查 |
| AC-078 | 用实际验证配置从无图／有图上传、试听、启用、三类浏览器播放及下一首准备，到换图、隐藏与手动删除 | STEP-021：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L725；H5-M、H5-D、API、DEP |
| AC-079 | 上传音乐不带封面、后续补传，以及无图曲目启用 | STEP-005：无封面音频就绪/启用合法，关联可空且不复制默认对象; STEP-014：H5无图使用唯一内置通用黑胶，不要求每曲上传默认图 | P01 L726；Admin UI、API、H5-M |
| AC-080 | 有图／无图曲目在首页、面板、内容页及设置页播放、暂停、减少动态效果 | STEP-014：主页/面板及共享唱片渲染规则; STEP-015：内容页/设置页共享唱片实例与状态 | P01 L727；H5-M、H5-D |
| AC-081 | 封面 404、超时／损坏，默认图也异常 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L728；SIM、H5-M |
| AC-082 | 快速切 A→B，延迟 A 图；同曲封面旧版本晚到 | STEP-014：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L729；SIM |
| AC-083 | 五角色直调上传／替换／移除封面，观察者预览，写入前撤权 | STEP-005：封面角色/预览/撤权的服务端授权; STEP-008：封面授权/越权动作审计结果 | P01 L730；API、Admin UI |
| AC-084 | 对已启用、未启用及隐藏曲目补图、换图、移除图 | STEP-005：启用中可直接改图，隐藏/未启用不因此启用，目录数据版本正确; STEP-014：H5按既有目录事件更新后显示封面，不新增推送/重启音乐 | P01 L731；API、Admin UI、H5-M |
| AC-085 | 正在播放或已准备下一首时修改其封面，检查媒体及图片版本 | STEP-005：服务端仅图片/目录版本变化，音频URL/版本不变; STEP-014：前台只更新图，不重建音频/进度/音量/手选; STEP-019：封面更新不使有效音频准备/检查点失效 | P01 L732；API、H5 网络、SIM |
| AC-086 | 在配置好的既有 Bucket 上传音频和封面，并检查 URL／对象归属 | STEP-003：既有Bucket下音频自动Key/HTTPS地址与图片业务隔离; STEP-005：同Bucket封面独立目录/新Key/配置地址且不影响朋友圈; STEP-020：真实配置、对象/URL/权限及原业务的部署环境实证 | P01 L733；API、OSS、DEP |
| AC-087 | 按实际采用的封面白名单和体积／像素阈值测试合法、伪格式、损坏、超限、动态图 | STEP-005：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L734；API、Admin UI、图片样本 |
| AC-088 | 初次音频成功封面失败；替换封面写入／保存失败；响应丢失后核对 | STEP-005：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L735；API、Admin UI、故障注入 |
| AC-089 | 并发封面保存、改图与删曲重叠、旧上传迟到 | STEP-005：并发封面保存/旧上传及删除状态守卫、对象可定位; STEP-006：真实删除与封面保存交错时不复活，残留仍可定位清理; STEP-008：封面并发与资产结果审计可核对 | P01 L736；API 并发、OSS、审计 |
| AC-090 | 隐藏歌曲，再满足实际等待期后删曲；令一个封面对象删除失败 | STEP-006：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L737；API、OSS、DEP |
| AC-091 | 多次替换／移除封面，执行实际采用的旧资源回收方式，再删除曲目 | STEP-006：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L738；API、OSS、清理记录 |
| AC-092 | 当前曲成功播放并达到实际验证的准备条件，观察长歌单请求 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L739；H5-M、H5-D、网络检查 |
| AC-093 | 下一首准备成功，检查声音、UI、存储和调用，随后实际切歌 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L740；SIM、H5-M、存储及输出检查 |
| AC-094 | 准备中暂停、关闭、隐藏、跳页或进入真实通话，注入旧完成回调 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L741；H5-M、SIM、真实语音回归 |
| AC-095 | 弱网、省流量／不支持、候选失败、只有一首、未知时长分别测试 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L742；H5-M、SIM |
| AC-096 | 准备后目录重排／候选隐藏、用户改选、新媒体版本、旧目录超龄 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L743；API、SIM、网络检查 |
| AC-097 | 同 URL 重复访问，改名／换封面再请求，新音频／新封面版本分别测试 | STEP-020：HTTP缓存与音频/封面版本URL的完整真实网络核对 | P01 L744；H5-M、H5-D、CDN／网络记录 |
| AC-098 | 有限带宽启动、Range 续播、缓存片段不足、浏览器回收缓存 | STEP-020：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L745；H5-M、CDN、网络检查 |
| AC-099 | 检查 localStorage、会话、网络及本次新增缓存能力，清理浏览器缓存再访问 | STEP-019：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L746；存储、静态及网络检查 |
| AC-100 | 对照建议表、开发配置、测试记录和已确认规则 | STEP-001：技术采用/建议性质和验证记录结构；实际配置/证据总核对见STEP-021; STEP-021：本STEP直接承担整条；按本STEP断言及PRD指定环境取证 | P01 L747；文档与配置审阅、测试记录 |

### 5.3 异常、确认与建议采用追踪

异常ID不改造成新需求；对应STEP须覆盖原AC中的反馈、数据副作用及恢复边界。

| 异常ID | PRD异常 | 直接处理STEP | 来源 |
| --- | --- | --- | --- |
| E-001 | 浏览器拦截自动播放 | STEP-012 | P01 L548 |
| E-002 | 目录为空 | STEP-012、STEP-014、STEP-015 | P01 L549 |
| E-003 | 目录失败、有旧缓存 | STEP-012 | P01 L550 |
| E-004 | 单曲坏链、404、格式或解码失败 | STEP-012 | P01 L551 |
| E-005 | 所有候选失败／弱网持续缓冲 | STEP-012 | P01 L552 |
| E-006 | Web Audio／渐变或精细音量不可用 | STEP-011 | P01 L553 |
| E-007 | 本地存储损坏／拒绝写入 | STEP-009 | P01 L554 |
| E-008 | 会话状态无法可靠读取或写入 | STEP-013 | P01 L555 |
| E-009 | 快速连点、关闭后旧请求完成 | STEP-010 | P01 L556 |
| E-010 | 检查点非法、媒体版本不符、后退旧页面 | STEP-013 | P01 L557 |
| E-011 | 通话取消、拒绝权限、连接失败、挂断 | STEP-016 | P01 L558 |
| E-012 | 短 TTS 重叠、超时或结束迟到 | STEP-017 | P01 L559 |
| E-013 | 音频／封面输入非法、伪格式或超限 | STEP-003、STEP-005 | P01 L560 |
| E-014 | Admin 登录失效／角色变化 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006 | P01 L561 |
| E-015 | 默认、排序或记录版本冲突 | STEP-004、STEP-005 | P01 L562 |
| E-016 | 上传／管理请求响应丢失 | STEP-003、STEP-005 | P01 L563 |
| E-017 | 处理忙、磁盘不足、依赖缺失 | STEP-003、STEP-020 | P01 L564 |
| E-018 | 转码超时、进程退出、旧任务迟到 | STEP-003 | P01 L565 |
| E-019 | OSS 上传成功、数据库确认失败 | STEP-003、STEP-005 | P01 L566 |
| E-020 | 音频／封面部分删除失败、对象不存在或缓存残留 | STEP-006 | P01 L567 |
| E-021 | Redis 故障／变更失效失败 | STEP-007 | P01 L568 |
| E-022 | 音频跨域无声／代理过早超时 | STEP-020 | P01 L569 |
| E-023 | 未上传／移除封面 | STEP-005、STEP-014 | P01 L570 |
| E-024 | 封面替换上传、图像处理或保存失败 | STEP-005 | P01 L571 |
| E-025 | 前台封面坏链、默认图失败或旧图迟到 | STEP-014 | P01 L572 |
| E-026 | 多人改图、改图与删曲并发、权限被撤 | STEP-005 | P01 L573 |
| E-027 | 封面业务已移除／替换，但旧对象清理失败 | STEP-005、STEP-006 | P01 L574 |
| E-028 | 下一首预加载失败、不支持、弱网或省流量 | STEP-019 | P01 L575 |
| E-029 | 准备期间暂停、通话、隐藏、换曲或候选失效 | STEP-019 | P01 L576 |
| E-030 | HTTP 缓存未命中、被清理或 Range 未覆盖 | STEP-020 | P01 L577 |

| 确认ID | PRD最终规则 | 负责STEP | 来源 |
| --- | --- | --- | --- |
| D-01 | 本期接入优先、可运行为主，Chrome、Safari、微信列入正式 BGM 范围 | STEP-020、STEP-021 | P01 L788 |
| D-02 | 用户设置页有“音乐淡入淡出”开关，默认开启；正常暂停、播放／恢复和切歌体现渐变 | STEP-009、STEP-011、STEP-014 | P01 L789 |
| D-03 | 渐变不稳定／不可用时允许基本播放降级，保留用户开关 | STEP-011 | P01 L790 |
| D-04 | 主页动效、渐变、音量、自动播放、最后手选五项仅浏览器本地；服务端不记录 | STEP-009、STEP-014 | P01 L791 |
| D-05 | 设置页和普通内容页使用同款悬浮唱片 | STEP-015 | P01 L792 |
| D-06 | 新访问直接进入任一允许页时，按本地自动播放设置尝试 | STEP-013 | P01 L793 |
| D-07 | 保留真实通话关闭本次、结束不恢复的规则，接入当前已存在的真实语音流程 | STEP-016 | P01 L794 |
| D-08 | `super_admin`／`ops_admin` 全权；`observer` 只读试听；`ai_trainer`／`tech_ops` 无管理访问 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006 | P01 L795 |
| D-09 | 保留单歌单、事件触发更新、隐藏后等期手动删除的低运营成本路径 | STEP-004、STEP-006、STEP-007、STEP-012 | P01 L796 |
| D-10 | 音频和封面复用现有朋友圈 OSS Bucket，分目录；优先复用现有 CDN | STEP-003、STEP-005、STEP-020 | P01 L797 |
| D-11 | 服务端自动生成路径和版本，保存对象定位，不覆盖旧文件，运营无需手填 URL | STEP-003、STEP-005、STEP-020 | P01 L798 |
| D-12 | 每曲一张可选静态封面，后台可添加、补传、替换、移除，隐藏保留、删曲清专属资产 | STEP-005、STEP-006 | P01 L799 |
| D-13 | 整张封面居中圆形展示，随唱片旋转；前台各唱片位置一致 | STEP-014、STEP-015 | P01 L800 |
| D-14 | 内置统一通用黑胶默认图，无图／移除／加载失败时使用 | STEP-005、STEP-006、STEP-014、STEP-015 | P01 L801 |
| D-15 | 已启用音乐封面可直接修改，保存后按既有目录更新生效，不影响音频 | STEP-005、STEP-012、STEP-014、STEP-019 | P01 L802 |
| D-16 | 保持 AAC-LC／M4A、96 kbps、音频发布上限 4 MiB；上传上限 100 MiB、单曲最长 5 分钟继续保留 | STEP-003、STEP-020 | P01 L803 |
| D-17 | 本期轻量准备下一首，最多一个候选；使用浏览器 HTTP 缓存，不做完整本地音频缓存 | STEP-019、STEP-020 | P01 L804 |
| D-18 | 所有未确认建议保留为建议参数／建议实现，由研发和测试验证、微调 | STEP-001、STEP-021 | P01 L805 |

下表是采用记录的起点，不是参数定稿。实际采用值/方式、环境、验证证据、影响AC、调整原因及日期由负责STEP在实施时填写；当前全部“未采用/待验证”。不得将缺少候选值当作新的用户产品决策。

| SUG ID | 项目 | PRD建议（非固定要求） | 负责STEP | 当前实际采用/证据 |
| --- | --- | --- | --- | --- |
| SUG-001 | 渐入／渐出时长 | 每段约 0.5 秒，不含加载 | STEP-011 | 未采用 / 待验证 |
| SUG-002 | 唱片／缩放／面板过渡 | 12 秒一圈／250 毫秒／400 毫秒；面板常规高度参考视口 40%～50% | STEP-014、STEP-015 | 未采用 / 待验证 |
| SUG-003 | 长名滚动 | 约 20 像素／秒，首尾停留约 1 秒 | STEP-014 | 未采用 / 待验证 |
| SUG-004 | 短 TTS 衰减 | 用户增益乘以 25% | STEP-017 | 未采用 / 待验证 |
| SUG-005 | 进度检查点 | 约每 2 秒，关键动作及时记录 | STEP-013 | 未采用 / 待验证 |
| SUG-006 | 客户端目录缓存 | 新鲜期参考 5 分钟，故障旧目录最长参考 30 分钟 | STEP-012 | 未采用 / 待验证 |
| SUG-007 | 服务端目录缓存 | TTL 参考 60 秒，管理变更主动失效／更新 | STEP-007 | 未采用 / 待验证 |
| SUG-008 | 一轮自动故障链 | 总预算参考 30 秒、最多 3 个不同候选；单曲等待参考 15 秒 | STEP-012 | 未采用 / 待验证 |
| SUG-009 | 目录请求与冷却 | 单次参考 8 秒、自动重试 1 次、退避 1 秒、强制刷新 1 次、失败冷却 30 秒 | STEP-012 | 未采用 / 待验证 |
| SUG-010 | 音频接收／处理方式 | 可参考受限长请求＋可查询操作记录，或复用现有等价处理能力 | STEP-003、STEP-020 | 未采用 / 待验证 |
| SUG-011 | 音频处理并发与时限 | 全部署并发参考 1；接收／处理参考 120／180 秒，总计参考 300 秒，转码子步骤参考 120 秒 | STEP-003、STEP-020 | 未采用 / 待验证 |
| SUG-012 | 外层等待时间 | 若采用上述长请求，代理／前端可参考 310／330 秒 | STEP-003、STEP-020 | 未采用 / 待验证 |
| SUG-013 | 名称长度 | 去空白后参考 1～60 个 Unicode 码点 | STEP-003、STEP-004 | 未采用 / 待验证 |
| SUG-014 | 采样、声道和首播结构 | 44.1 kHz、最多双声道、保留单声道、faststart；转码可参考 FFmpeg／ffprobe | STEP-003、STEP-020 | 未采用 / 待验证 |
| SUG-015 | 曾发布歌曲删除等待 | 最近隐藏后参考 24 小时 | STEP-006 | 未采用 / 待验证 |
| SUG-016 | 封面上传 | 建议静态 JPG/JPEG、PNG、WebP；单图参考 ≤5 MiB、长边 ≤4096 像素 | STEP-005 | 未采用 / 待验证 |
| SUG-017 | 封面输出 | 可参考 512×512 WebP，体积目标 ≤200 KiB；后端标准化处理 | STEP-005 | 未采用 / 待验证 |
| SUG-018 | 下一首准备时机 | 可参考剩余约 20 秒时尝试，当前播放与页面资源优先 | STEP-019 | 未采用 / 待验证 |
| SUG-019 | 音频／封面 HTTP 缓存 | 版本化 URL 的成功资源可参考约 30 天缓存及适当不可变标记 | STEP-020 | 未采用 / 待验证 |
| SUG-020 | OSS 命名与接口字段 | 可参考 F-008 的 `bgm/tracks/`、`bgm/covers/` 和曲目／版本 Key；接口、版本字段见建议能力表 | STEP-001、STEP-003、STEP-005、STEP-007 | 未采用 / 待验证 |
| SUG-021 | 旧封面／残留回收 | 可复用既有受控清理路径，结合目录及 HTTP 缓存确定回收时点 | STEP-005、STEP-006 | 未采用 / 待验证 |

## 6. 完整STEP提示词

每个STEP可单独交给后续执行器。共有约定随提示词生效：来源P01是本次PRD，R01是仓库边界；现有路径/符号在本STEP参考表中为existing，新增能力为planned，实际环境未验证为UNVERIFIED；不读取禁读目录。只改本STEP必要范围，保留其他工作区改动。正常/异常/边界用例以PRD与本STEP明示子条款为预期，模拟不能替代PRD要求的真实环境。

### [STEP-001] 确定技术接入与参数验证记录

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：形成保持已确认业务语义的技术接入方案，并为待验证参数逐项指定采用记录与验证门。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-008 | 音频校验、转码、复用 OSS 发布及手动清理资产 | PRD / P01 L59 |
| 需求ID | F-010 | 当前曲按需缓冲、下一首轻量准备、浏览器 HTTP 缓存 | PRD / P01 L61 |
| 需求ID | BR-043 | 区分已确认规则与建议；研发／测试记录实际采用参数、方式、适用环境和证据，验收按已确认结果及实际配置执行 | PRD / P01 L530 |
| 验收ID | AC-100 | 建议值／方案均有“建议”性质；实际采用值由研发／测试验证记录，不能直接当强制阈值；96 kbps／4 MiB 等未被擅改，不伪报兼容或容量通过〔本STEP范围：技术采用/建议性质和验证记录结构；实际配置/证据总核对见STEP-021〕 | PRD / P01 L747 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| 无 | 本STEP只读取本次PRD/demo/当前代码与契约 | 输入清单/摘要与当前来源一致 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C02 / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `backend/services/feed_image_service.py` | `existing` | `REPO_BASELINE` | B03 / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `Dockerfile` | `existing` | `REPO_BASELINE` | B10 / L10–15 apt 依赖，无 FFmpeg | 对应需求、复用点或需保留的基线 |
| `nginx/nginx.conf` | `existing` | `REPO_BASELINE` | B11 / 通用 API proxy_read_timeout 300s；无显式请求体大小/接收配置 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-entry.js` | `existing` | `REPO_BASELINE` | H06 / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/README.md` | `existing` | `REPO_BASELINE` | D01 / L1–41 V1.3 范围、参数、模拟边界 | 对应需求、复用点或需保留的基线 |
| `backend/models/__init__.py` | `existing` | `REPO_BASELINE` | B15 / L4–104 全模型注册，当前无BGM | 对应需求、复用点或需保留的基线 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B16 / L9–24 metadata与模型导入；L41–49 online入口 | 对应需求、复用点或需保留的基线 |
| `alembic/versions/v9g_memory_diagnostic.py` | `existing` | `REPO_BASELINE` | B17 / L3–4 revision/down_revision；静态唯一head | 对应需求、复用点或需保留的基线 |
| `docker-compose.yml` | `existing` | `REPO_BASELINE` | B18 / L44–68 backend环境与挂载；L7 迁移约定 | 对应需求、复用点或需保留的基线 |
| `requirements.txt` | `existing` | `REPO_BASELINE` | B19 / multipart/Alembic/Redis/Pillow/oss2/pytest声明 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 技术采用记录与新增文件/接口清单，名称按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：一份随主文档维护的技术采用记录：接口/模型/事务边界、资源归属、受限处理方案、音频能力策略与 SUG 验证分工。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 96 kbps、4 MiB、100 MiB、0＜时长≤300 秒、五项只在本地、一个下一首候选均为 PRD 确认规格。 | PRD / F-008、F-010、BR-043 |
| 本STEP规则2 | SUG-001～021 的值与实现是建议；先记录候选和待验证状态，再由负责 STEP 用证据确定实际采用结果。 | PRD / F-008、F-010、BR-043 |

**开发任务**：

1. 按既有响应/鉴权/模型与迁移约定定位并登记 BGM 的新增表、字段、路由、错误类别及内部模块；本文档不预先分配错误码或把建议路由当现有入口。
2. 定稿操作提交前可持久恢复的稳定标识、同内容去重/异内容冲突、音频/封面摘要、attempt 失效、DB/OSS 补偿及旧封面归属方案。
3. 比较受限长请求与复用既有执行能力的等价方案，明确全部署接纳/并发、绝对预算、超时终止与清理的验证方法；不建设专用任务平台。
4. 登记 SUG 的负责 STEP、候选、实际采用值/方式、环境、证据、影响 AC、日期；真实 Bucket/CDN、浏览器输出和部署容量仍待实施验证，不能填造。
5. 明确BGM写请求被get_current_admin/require_role提前拒绝时的审计接点与独立持久化边界：业务事务失败会rollback，不能仅靠业务handler的log_operation；保持拒绝与无业务副作用，不为审计放宽权限。

**不在本STEP范围内**：

- 不开始业务代码开发；不修改全局协作规则或生产配置；不要求用户再次选择已确认业务。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 逐条对照 D-01～18 和 SUG-001～021 | 已确认与建议分栏；每条建议有负责人及验证位置 | AC-100 |
| 异常 | 发现候选参数间预算/体积边界冲突 | 调整技术候选并记录，不改已确认业务值 | AC-100 |
| 边界 | 某环境/参数尚无实验结果 | 明确待验证；不能写成采用成功或兼容通过 | AC-100 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-002] 建立 BGM 管理访问与只读查询边界

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：让五个后台角色在菜单、直接页面、管理查询和服务端依赖层得到一致的访问结果。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-030 | 两个管理角色全权、观察者只读试听，另两个角色无管理访问 | PRD / P01 L517 |
| 验收ID | AC-054 | 两管理角色全权，观察者只读试听／预览，另两角色无管理访问；直接 API 同样限制〔本STEP范围：菜单、直链页面、管理只读及共用授权；具体写操作在其负责STEP〕 | PRD / P01 L701 |
| 验收ID | AC-055 | GET 不启动处理／清理／写记录；提交重新授权，无权写入被拒绝〔本STEP范围：所有已接入只读GET及共用提交鉴权；处理接口见STEP-003〕 | PRD / P01 L702 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-001 | 一份随主文档维护的技术采用记录：接口/模型/事务边界、资源归属、受限处理方案、音频能力策略与 SUG 验证分工。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C02 / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/admin-security-accounts/api.md` | `existing` | `CONTRACT` | C05 / L9–26 日志接口/角色/筛选 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `admin/static/js/admin-api.js` | `existing` | `REPO_BASELINE` | B02 / adminRequest；MENU_CONFIG；observer 菜单派生 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `backend/main.py` | `existing` | `REPO_BASELINE` | B07 / 路由注册；L268–273 admin_page 静态响应 | 对应需求、复用点或需保留的基线 |
| `tests/test_step040_admin_page_inventory.py` | `existing` | `REPO_BASELINE` | B12 / L10–23 EXPECTED_PAGES；L36–39 页数断言 | 对应需求、复用点或需保留的基线 |
| `tests/test_step028_admin_route_audit.py` | `existing` | `REPO_BASELINE` | B13 / L163 固定路由数 | 对应需求、复用点或需保留的基线 |
| `tests/test_step039_observer_backend_gate.py` | `existing` | `REPO_BASELINE` | B14 / L136–138 固定路由计数 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.html` | `existing` | `REPO_BASELINE` | D04 / L56 角色；L66–86 列表/上传/封面 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.css` | `existing` | `REPO_BASELINE` | D11 / L1–9 后台样式/响应式/分项反馈 | 对应需求、复用点或需保留的基线 |
| `backend/models/__init__.py` | `existing` | `REPO_BASELINE` | B15 / L4–104 全模型注册，当前无BGM | 对应需求、复用点或需保留的基线 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B16 / L9–24 metadata与模型导入；L41–49 online入口 | 对应需求、复用点或需保留的基线 |
| `alembic/versions/v9g_memory_diagnostic.py` | `existing` | `REPO_BASELINE` | B17 / L3–4 revision/down_revision；静态唯一head | 对应需求、复用点或需保留的基线 |
| `admin/static/js/life-feed-admin.js` | `existing` | `REPO_BASELINE` | B21 / L46–61 默认S/A页面门禁不可照搬BGM | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM 管理页、查询路由、schema/model/迁移及角色测试，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | super_admin/ops_admin 全权；observer 只读、预览和试听；ai_trainer/tech_ops 无 BGM 管理访问。 | PRD / F-007、F-009、BR-030 |
| 本STEP规则2 | GET 只查询，不启动转码/恢复/清理，不修改业务记录；列表有界分页。 | PRD / F-007、F-009、BR-030 |

**开发任务**：

1. 接入既有 Admin JWT、实时数据库角色检查及 observer 写总闸，新增 BGM 专属 allowlist；不可复用生活流的 super_admin/ai_trainer 默认权限。
2. 新增菜单和页面入口守卫；当前 admin_page 是静态 FileResponse，直接页面访问须验证既有 JS 拒绝策略实际生效，敏感数据/写操作始终由 API 鉴权。
3. 按已核实模型/迁移约定建立列表/操作查询所必需的 BGM 数据基座；本 STEP 不伪造就绪音乐。保留独立处理状态、启用标记、目录版本和资产/操作定位。
4. 列表用现行 list/total/page/page_size 和 id 约定；状态查询不回传源文件路径、凭证或二进制。
5. 先记录现有页面/路由 inventory 的实际基线，再按新增范围更新断言；不得为凑固定数量移除有效权限断言。
6. 实现BGM范围的越权写入拒绝审计接点，覆盖observer写总闸、ai_trainer/tech_ops角色拒绝及提交前撤权；与鉴权拒绝响应配合独立持久化，业务数据仍零写入。GET无业务副作用约束继续有效。
7. 新增BGM模型须注册现有metadata；采用Alembic时同步create_all排除与缺迁移启动检查，先静态核对当前唯一head，不在本轮连接库或执行迁移。

**不在本STEP范围内**：

- 本 STEP 只负责 AC-054 的菜单/页面/读取及共用鉴权；音频、目录、封面、删除写入口分别在对应 STEP 实测。
- 不在此实现发布、上传处理、试听或为 H5 公共音乐加登录要求。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 两管理者与 observer 打开菜单/直链/列表/详情/状态 | 可访问；只读查询无业务副作用 | AC-054、AC-055 |
| 异常 | ai_trainer/tech_ops 或失效身份访问直链/API | 页面与 API 按现行 401/403 策略拒绝；不返回管理内容 | AC-054 |
| 边界 | observer 直接调拟接入写路径、查询过期处理中记录 | 写入被服务端拒绝；GET 不触发写恢复 | AC-054、AC-055 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-003] 完成音频上传到就绪及失败恢复

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：运营可真实上传一首音乐，得到可核对、可试听、未自动启用的就绪结果，失败可关联原曲目恢复。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | F-008 | 音频校验、转码、复用 OSS 发布及手动清理资产 | PRD / P01 L59 |
| 需求ID | BR-031 | 就绪仍未启用，人工试听后主动启用；后台试听独立 | PRD / P01 L518 |
| 需求ID | BR-033 | 原操作可定位和查询，重复提交去重；同标识同内容复用、异内容冲突；处理重试关联原曲目 | PRD / P01 L520 |
| 需求ID | BR-036 | 服务端校验真实类型、解码、体积、时长和字段 | PRD / P01 L523 |
| 需求ID | BR-037 | AAC-LC／M4A、目标 96 kbps、完整发布文件 ≤4 MiB；采样／声道／编码器按经验证的实现检查 | PRD / P01 L524 |
| 需求ID | BR-038 | 并发、接收、处理与资源占用有明确有限边界，不影响主业务；子步骤服从实际采用的总预算 | PRD / P01 L525 |
| 需求ID | BR-039 | 操作结果及执行资格可核对；旧结果失效，过期工作有收尾；只清理本模块无有效执行者的临时资源 | PRD / P01 L526 |
| 需求ID | BR-040 | 唯一版本路径，实际写入及远端读取验证后才就绪，音频与图像处理独立 | PRD / P01 L527 |
| 需求ID | BR-044 | 复用现有朋友圈 Bucket；音频／封面分目录归属；优先复用并验证 CDN | PRD / P01 L531 |
| 需求ID | BR-045 | 服务端自动生成 Key 与访问 URL，保存可清理定位；新资源不覆盖旧地址；音频与封面各自版本化 | PRD / P01 L532 |
| 验收ID | AC-054 | 两管理角色全权，观察者只读试听／预览，另两角色无管理访问；直接 API 同样限制〔本STEP范围：音频上传/处理重试的写权限与observer试听读取〕 | PRD / P01 L701 |
| 验收ID | AC-055 | GET 不启动处理／清理／写记录；提交重新授权，无权写入被拒绝〔本STEP范围：音频接纳/重试/完成提交重新授权，状态GET不写恢复〕 | PRD / P01 L702 |
| 验收ID | AC-056 | 前后端边界一致；重名以 ID 区分，非法状态／路径不能由客户端指定；60 码点不是本轮定案〔本STEP范围：上传名称边界与客户端伪造音频状态/路径拒绝〕 | PRD / P01 L703 |
| 验收ID | AC-057 | 后台单首试听，切换先停，离页停；不改 H5 本地音量、选曲或会话 | PRD / P01 L704 |
| 验收ID | AC-062 | 原操作可恢复查询，同内容去重、异内容冲突；未知结果不自动创建重复对象；标识与请求拆分按经验证方案〔本STEP范围：音频上传/重试稳定操作查询、去重及异内容冲突〕 | PRD / P01 L709 |
| 验收ID | AC-066 | 成功先就绪未启用；失败／处理中不可启用，只有人工动作进入公开目录〔本STEP范围：四类源处理、就绪仍未启用及无自动发布；真实手动启用门禁由STEP-004验证〕 | PRD / P01 L713 |
| 验收ID | AC-067 | 服务端拒绝或明确处理失败，无可发布记录及失联临时资产 | PRD / P01 L714 |
| 验收ID | AC-068 | 按表中闭区间及开区间执行；不因前端绕过或输出超限仍发布 | PRD / P01 L715 |
| 验收ID | AC-069 | AAC-LC／M4A、目标 96 kbps、完整音频 ≤4 MiB；采样／声道／首播结构按验证配置，非机械要求建议命令；不影响独立封面 | PRD / P01 L716 |
| 验收ID | AC-070 | 总资源占用有界，忙碌／限流明确；不按进程无界放大，不影响公开读或当前播放；并发 1 仅为建议〔本STEP范围：采用处理器的全部署并发限制及故障注入〕 | PRD / P01 L717 |
| 验收ID | AC-071 | 原操作可核对，到期可识别失败；不重复建曲、不永久处理中，GET 不写恢复 | PRD / P01 L718 |
| 验收ID | AC-072 | 原曲目 ID 保留，新尝试受限；旧结果不能就绪／发布；源已清理需重选〔本STEP范围：带新源关联原曲目重试及旧attempt在新尝试后迟到隔离〕 | PRD / P01 L719 |
| 验收ID | AC-073 | 所有已生成对象可关联核对及补偿，结果未知不换键盲重传；当前有效图／音乐不误删；具体记录时序按验证方案〔本STEP范围：音频对象/操作/数据库单侧成功与补偿定位〕 | PRD / P01 L720 |
| 验收ID | AC-074 | 预算不重置；超时终止回收旧子进程后再释放名额；仅清已确认无执行者的过期文件，不误删活动素材〔本STEP范围：处理器绝对预算/执行资格/终止回收/受控恢复逻辑〕 | PRD / P01 L721 |
| 验收ID | AC-086 | 路径自动生成、音频封面分目录、CDN 地址来自真实配置；新图新 Key；不要求运营填 URL，不更改朋友圈目录／资源／权限〔本STEP范围：既有Bucket下音频自动Key/HTTPS地址与图片业务隔离〕 | PRD / P01 L733 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-001 | 一份随主文档维护的技术采用记录：接口/模型/事务边界、资源归属、受限处理方案、音频能力策略与 SUG 验证分工。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C02 / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `admin/static/js/admin-api.js` | `existing` | `REPO_BASELINE` | B02 / adminRequest；MENU_CONFIG；observer 菜单派生 | 对应需求、复用点或需保留的基线 |
| `backend/services/feed_image_service.py` | `existing` | `REPO_BASELINE` | B03 / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | 对应需求、复用点或需保留的基线 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B04 / L224–242 OSS 配置名称；未读取真实凭证 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `backend/main.py` | `existing` | `REPO_BASELINE` | B07 / 路由注册；L268–273 admin_page 静态响应 | 对应需求、复用点或需保留的基线 |
| `Dockerfile` | `existing` | `REPO_BASELINE` | B10 / L10–15 apt 依赖，无 FFmpeg | 对应需求、复用点或需保留的基线 |
| `nginx/nginx.conf` | `existing` | `REPO_BASELINE` | B11 / 通用 API proxy_read_timeout 300s；无显式请求体大小/接收配置 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.html` | `existing` | `REPO_BASELINE` | D04 / L56 角色；L66–86 列表/上传/封面 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.js` | `existing` | `REPO_BASELINE` | D05 / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | 对应需求、复用点或需保留的基线 |
| `backend/models/__init__.py` | `existing` | `REPO_BASELINE` | B15 / L4–104 全模型注册，当前无BGM | 对应需求、复用点或需保留的基线 |
| `alembic/env.py` | `existing` | `REPO_BASELINE` | B16 / L9–24 metadata与模型导入；L41–49 online入口 | 对应需求、复用点或需保留的基线 |
| `docker-compose.yml` | `existing` | `REPO_BASELINE` | B18 / L44–68 backend环境与挂载；L7 迁移约定 | 对应需求、复用点或需保留的基线 |
| `requirements.txt` | `existing` | `REPO_BASELINE` | B19 / multipart/Alembic/Redis/Pillow/oss2/pytest声明 | 对应需求、复用点或需保留的基线 |
| `tests/test_step012_feed_image.py` | `existing` | `REPO_BASELINE` | V02 / 现有图片服务回归入口；未运行 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 音频处理/操作恢复/资产服务及上传试听 UI、必要依赖/测试，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 允许源 MP3、M4A/AAC、WAV；源≤100 MiB，时长>0且≤300秒；产物 AAC-LC/M4A、目标96 kbps、完整文件≤4 MiB。 | PRD / F-007、F-008、BR-031、BR-033、BR-036、BR-037、BR-038、BR-039、BR-040、BR-044、BR-045 |
| 本STEP规则2 | 就绪与启用分离；只有探测、产物检查、对象写入和远端读取检查通过才就绪。无封面合法。 | PRD / F-007、F-008、BR-031、BR-033、BR-036、BR-037、BR-038、BR-039、BR-040、BR-044、BR-045 |
| 本STEP规则3 | 处理有全部署有限接纳/资源/绝对时间边界；旧尝试不能发布；源在收尾后清理。 | PRD / F-007、F-008、BR-031、BR-033、BR-036、BR-037、BR-038、BR-039、BR-040、BR-044、BR-045 |

**开发任务**：

1. 按 demo 上传抽屉/处理状态/失败重选交互接入真实 API；名称去首尾空白、非空、有上限、拒绝控制字符，重复名称按 ID 区分，纯文本渲染。
2. 提交前保存可恢复操作标识及实际请求摘要；刷新、断网和结果未知查原操作，不据一次未查到就重新建曲。同键同内容复用，异内容冲突；重试保留原曲目 ID。
3. 流式或等价有界接收并真实解码探测，校验源/产物边界；处理成功只标就绪且仍未启用，不自动进入公开集合；清除音频内嵌封面、视频轨和无关元数据，独立封面另由 STEP-005 负责。采样/声道/首播结构按采用记录验证。
4. 复用现有 OSS 连接配置，使用 BGM 独立音频归属和不可变版本 Key；写入前后保持操作/对象可定位，DB 单侧失败先核对再补偿；绝不套用 lxm/posts 图片转换路径。
5. 处理并发/总预算跨实例有效；超时先安全终止回收执行资源再释放名额，过期/崩溃收尾不由 GET 启动，不清理活动素材；旧 attempt/已删除对象迟到不可就绪。
6. 后台用真实就绪音频单首试听，换曲/离页先停旧试听；observer 可试听但不能上传/重试；不读写 H5 音量/选曲/会话。
7. 同次附封面的提交可按采用方案拆分；STEP-005 完成后分别反馈音频与封面结果。各自合法文件不得因代理总大小配置冲突必然失败。写入时接入既有审计 helper，完整动作筛选在 STEP-008 验证。
8. adminRequest异常/超时及401/403目前均可能返回null；上传页不得把null直接当已确认失败重建。需保留操作标识并区分权限中断/结果未知，调整只限本次必要能力。

**不在本STEP范围内**：

- AC-066只承担源处理、就绪未启用与无自动发布；真实手动启用入口及未就绪拒绝在STEP-004，本STEP不依赖其尚未实现的接口。AC-073/086只承担音频对象与DB/OSS侧，封面侧由STEP-005/006承担。
- 不自动发布、不原位替换音频、不永久保留源文件、不用本地合成样本代替上传产物；真实部署资源/CORS总体验证在 STEP-020。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 四类合法音频，重名及合法名称边界，两个授权角色上传 | 真实处理后就绪仍未启用，公开集合未因处理自动加入该曲；可独立试听且试听不启用；查询可追踪；对应音频权限有效 | AC-054、AC-056、AC-057、AC-066、AC-086 |
| 异常 | 空文件/伪后缀/MIME不符/损坏/非法字段/超限、依赖缺失或资源不足 | 明确拒绝或失败、无可发布产物/失联对象；GET及撤权后写入无副作用 | AC-055、AC-056、AC-067、AC-070 |
| 边界 | 100 MiB及+1字节、0/300秒/超过300秒、4 MiB及+1字节产物 | 按确认边界检查；内嵌附件清除；实际采样与目标码率可探测并试听 | AC-068、AC-069 |
| 异常 | 响应丢失、服务退出、OSS成功DB失败、旧attempt迟到 | 原操作可查/可补偿；明确失败后带新源重试仍关联原曲目，无重复发布 | AC-062、AC-071、AC-072、AC-073 |
| 边界 | 多实例超并发、慢接收/转码/OSS挂起及恢复重入 | 共用有限预算、不重复放大名额；安全回收且不误删活动文件 | AC-070、AC-074 |

**完成标志**：

- [ ] AC-066本STEP子条款可凭处理/记录/公开集合证据独立完成，不依赖STEP-004；真实手动启用子条款待STEP-004取证，两部分齐备前整条AC-066不计完成。
- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-004] 维护唯一默认和原子有序歌单

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：管理员能改名、启用、隐藏、设默认和排序，所有成功结果形成一份完整一致的目录版本。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | BR-031 | 就绪仍未启用，人工试听后主动启用；后台试听独立 | PRD / P01 L518 |
| 需求ID | BR-032 | 非空有效歌单恰好一个默认，空则默认空；目录变更保持完整一致的版本 | PRD / P01 L519 |
| 需求ID | BR-033 | 原操作可定位和查询，重复提交去重；同标识同内容复用、异内容冲突；处理重试关联原曲目 | PRD / P01 L520 |
| 验收ID | AC-054 | 两管理角色全权，观察者只读试听／预览，另两角色无管理访问；直接 API 同样限制〔本STEP范围：改名/启用/隐藏/默认/排序写权限〕 | PRD / P01 L701 |
| 验收ID | AC-056 | 前后端边界一致；重名以 ID 区分，非法状态／路径不能由客户端指定；60 码点不是本轮定案〔本STEP范围：改名边界与目录字段/伪造状态拒绝〕 | PRD / P01 L703 |
| 验收ID | AC-058 | 非空唯一有效默认；空目录重新启用也自动设默认，非空保留原默认；启用置末尾，清空默认空 | PRD / P01 L705 |
| 验收ID | AC-059 | 合法原子更新，不合法拒绝；当前曲不因排序被重启〔本STEP范围：API完整排列原子提交及重复/缺失/未知/未启用ID拒绝〕 | PRD / P01 L706 |
| 验收ID | AC-060 | 数据库真实状态、版本和日志可核对；不误报完全失败引导重复操作〔本STEP范围：目录事务/操作/必要审计可核对，响应丢失不重建〕 | PRD / P01 L707 |
| 验收ID | AC-061 | 一份一致结果，冲突明确；无双默认、无非空缺默认或混合排序 | PRD / P01 L708 |
| 验收ID | AC-066 | 成功先就绪未启用；失败／处理中不可启用，只有人工动作进入公开目录〔本STEP范围：真实API/Admin UI手动启用门禁与合法就绪的明确人工启用；源处理及不自动发布由STEP-003验证〕 | PRD / P01 L713 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `admin/static/js/admin-api.js` | `existing` | `REPO_BASELINE` | B02 / adminRequest；MENU_CONFIG；observer 菜单派生 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.html` | `existing` | `REPO_BASELINE` | D04 / L56 角色；L66–86 列表/上传/封面 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.js` | `existing` | `REPO_BASELINE` | D05 / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 歌单变更事务与页面运营控件，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 非空有效目录恰有一个默认；空目录默认空；首次/重新启用置末尾。 | PRD / F-007、BR-031、BR-032、BR-033 |
| 本STEP规则2 | 隐藏默认且仍有其他曲目时，同次指定替代默认并提交；已启用曲目不能删除。 | PRD / F-007、BR-031、BR-032、BR-033 |
| 本STEP规则3 | 排序必须为完整有效启用ID排列；旧版本拒绝且由管理员刷新后重新决定。 | PRD / F-007、BR-031、BR-032、BR-033 |

**开发任务**：

1. 复用demo的默认标记、启用/隐藏、改名与排序交互，真实启用API与Admin UI须拒绝处理中/失败/未验证资源；合法就绪素材仍保持未启用，只有明确人工启用动作才提交公开集合，且校验非删除态；不把UI乐观值当已提交结果。
2. 按数据库行锁/等价既有事务约定原子维护启用集合、完整排序、默认和目录版本；重启用、清空再启用按空/非空规则处理。
3. 名称编辑沿用 STEP-003 已验证上限与纯文本规则；拒绝伪造状态/OSS路径/时间，非法排列整体拒绝。
4. 管理动作提交前有可核对标识；响应丢失查原结果。操作记录、目录变更与必要审计保持可追踪；提交后缓存失效失败不能误报 DB 回滚。STEP-007 补实际缓存接线。

**不在本STEP范围内**：

- 不改动仍有效的 H5 当前播放；不新增多歌单、场景、作者、标签或自定义 URL；封面维护在 STEP-005。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 合法就绪且未启用素材，经真实Admin UI/启用API明确人工启用；空库/非空、隐藏后重启用 | 动作前仍未启用，动作成功后才进入公开集合；唯一默认、置末尾和默认空正确，响应与数据库同版本 | AC-058、AC-066 |
| 异常 | 对真实processing/failed/未验证素材分别从Admin UI和直调启用API操作；无权限写、控制字符改名及非法排序 | 未就绪启用明确拒绝，不能进入公开集合且目录/默认不变；其余非法写整体拒绝，名称边界一致 | AC-054、AC-056、AC-059、AC-066 |
| 边界 | 两管理员同版本并发设默认/隐藏/排序 | 只提交一致结果，另一方明确冲突；无双默认或混合排序 | AC-061 |
| 异常 | 提交成功后丢响应/缓存失败 | 原 DB、版本和审计可核对，不诱导重造记录 | AC-060 |

**完成标志**：

- [ ] AC-066有真实处理中/失败/未验证资源启用拒绝与合法就绪仅经明确人工动作启用的API/Admin UI证据；结合STEP-003子条款后才能将整条AC-066计完成。
- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-005] 维护每曲可选封面并隔离音频版本

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：一首音乐可在任意可编辑发布状态补传、替换或移除静态封面，音频与已保存旧图保持可靠。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-032 | 非空有效歌单恰好一个默认，空则默认空；目录变更保持完整一致的版本 | PRD / P01 L519 |
| 需求ID | BR-033 | 原操作可定位和查询，重复提交去重；同标识同内容复用、异内容冲突；处理重试关联原曲目 | PRD / P01 L520 |
| 需求ID | BR-039 | 操作结果及执行资格可核对；旧结果失效，过期工作有收尾；只清理本模块无有效执行者的临时资源 | PRD / P01 L526 |
| 需求ID | BR-044 | 复用现有朋友圈 Bucket；音频／封面分目录归属；优先复用并验证 CDN | PRD / P01 L531 |
| 需求ID | BR-045 | 服务端自动生成 Key 与访问 URL，保存可清理定位；新资源不覆盖旧地址；音频与封面各自版本化 | PRD / P01 L532 |
| 需求ID | BR-046 | 每曲最多一张静态封面，非必填；两个管理角色可维护，观察者只读；无图用默认图 | PRD / P01 L533 |
| 需求ID | BR-048 | 直接保存无需先隐藏；成功后按原目录更新时机生效，图像更新不影响音频运行 | PRD / P01 L535 |
| 需求ID | BR-049 | 新图保存成功才替代旧关联；失败留旧图，无图或加载失败用默认；版本／权限／曲目状态核对 | PRD / P01 L536 |
| 验收ID | AC-054 | 两管理角色全权，观察者只读试听／预览，另两角色无管理访问；直接 API 同样限制〔本STEP范围：封面读取/预览和写权限〕 | PRD / P01 L701 |
| 验收ID | AC-062 | 原操作可恢复查询，同内容去重、异内容冲突；未知结果不自动创建重复对象；标识与请求拆分按经验证方案〔本STEP范围：封面操作稳定查询、去重及异内容冲突〕 | PRD / P01 L709 |
| 验收ID | AC-073 | 所有已生成对象可关联核对及补偿，结果未知不换键盲重传；当前有效图／音乐不误删；具体记录时序按验证方案〔本STEP范围：封面对象/关联/数据库单侧成功与补偿定位〕 | PRD / P01 L720 |
| 验收ID | AC-079 | 无封面合法，音频就绪／启用不受阻；使用唯一内置通用黑胶，不为每曲要求上传默认图〔本STEP范围：无封面音频就绪/启用合法，关联可空且不复制默认对象〕 | PRD / P01 L726 |
| 验收ID | AC-083 | 权限与音乐管理一致，观察者只能看；服务端拒绝越权并可审计，不仅前端隐藏按钮〔本STEP范围：封面角色/预览/撤权的服务端授权〕 | PRD / P01 L730 |
| 验收ID | AC-084 | 已启用无需先隐藏；未启用／隐藏不会自动启用；保存后按既有目录时机显示，不新增实时推送〔本STEP范围：启用中可直接改图，隐藏/未启用不因此启用，目录数据版本正确〕 | PRD / P01 L731 |
| 验收ID | AC-085 | 只改封面／目录版本，音频 URL 与版本不变，不转码、不重建／重置进度／改音量或最后手选；音频准备可继续按规则使用〔本STEP范围：服务端仅图片/目录版本变化，音频URL/版本不变〕 | PRD / P01 L732 |
| 验收ID | AC-086 | 路径自动生成、音频封面分目录、CDN 地址来自真实配置；新图新 Key；不要求运营填 URL，不更改朋友圈目录／资源／权限〔本STEP范围：同Bucket封面独立目录/新Key/配置地址且不影响朋友圈〕 | PRD / P01 L733 |
| 验收ID | AC-087 | 合法静态图可预览保存，其他明确拒绝；本期无裁剪编辑器或自动提取；不以建议 5 MiB／512px 当未经确认的硬阈值 | PRD / P01 L734 |
| 验收ID | AC-088 | 成功音频保留且可无图继续；替换失败保留旧图，未知结果先查；不强迫重传音频或将未保存图当已发布 | PRD / P01 L735 |
| 验收ID | AC-089 | 冲突明确、旧结果不覆盖新值；删除中／已删除不复活；已写入对象可定位清理，日志记录真实结果〔本STEP范围：并发封面保存/旧上传及删除状态守卫、对象可定位〕 | PRD / P01 L736 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-001 | 一份随主文档维护的技术采用记录：接口/模型/事务边界、资源归属、受限处理方案、音频能力策略与 SUG 验证分工。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-004 | BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C02 / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `admin/static/js/admin-api.js` | `existing` | `REPO_BASELINE` | B02 / adminRequest；MENU_CONFIG；observer 菜单派生 | 对应需求、复用点或需保留的基线 |
| `backend/services/feed_image_service.py` | `existing` | `REPO_BASELINE` | B03 / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | 对应需求、复用点或需保留的基线 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B04 / L224–242 OSS 配置名称；未读取真实凭证 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.html` | `existing` | `REPO_BASELINE` | D04 / L56 角色；L66–86 列表/上传/封面 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.js` | `existing` | `REPO_BASELINE` | D05 / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/shared-catalog.js` | `existing` | `REPO_BASELINE` | D06 / L4–10 参数；L82–126 本地目录；L131–243 图像预览 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/v13.css` | `existing` | `REPO_BASELINE` | D10 / L1–23 整图居中裁圆 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.css` | `existing` | `REPO_BASELINE` | D11 / L1–9 后台样式/响应式/分项反馈 | 对应需求、复用点或需保留的基线 |
| `tests/test_step012_feed_image.py` | `existing` | `REPO_BASELINE` | V02 / 现有图片服务回归入口；未运行 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 独立封面上传/关联服务、管理预览与必要迁移/测试，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 每曲最多关联一张静态封面、非必填；已启用可直接修改，无图不影响音频就绪/启用。 | PRD / F-007、F-009、BR-032、BR-033、BR-039、BR-044、BR-045、BR-046、BR-048、BR-049 |
| 本STEP规则2 | 新图成功保存才切关联；失败保留旧图；音频成功封面失败分别反馈，音频不重传。 | PRD / F-007、F-009、BR-032、BR-033、BR-039、BR-044、BR-045、BR-046、BR-048、BR-049 |
| 本STEP规则3 | 封面变化不转码、不改音频URL/版本/进度/意图；未启用/隐藏不会因此启用。 | PRD / F-007、F-009、BR-032、BR-033、BR-039、BR-044、BR-045、BR-046、BR-048、BR-049 |

**开发任务**：

1. 把 demo 的可选封面、补传/换图/移除、圆形预览、保存失败留旧图和未知结果核对接到真实 API；临时选择预览与已保存结果清楚区分。
2. 真实校验静态图像/解码/体积/像素/动态图；格式和阈值用验证后的采用记录，不直接照搬 demo 的5 MiB/4096px/512px。
3. 复用 Bucket 连接但用 BGM 独立封面归属与不可变 Key；服务端生成地址，不保存 demo 的 Data URL/localStorage 资产方案。
4. 补传/替换/移除共用角色/稳定操作标识/摘要/期望版本；并发改图冲突、删曲/旧attempt迟到不得复活；所有已生成对象及旧图版本有可清理定位。
5. 成功关联与已启用目录版本保持一致；移除是业务关联成功与旧文件清理分别反馈，清理失败不回滚当前图。旧图回收时点按采用记录验证，清理闭环由 STEP-006 完成。
6. 音频与可选封面结果分别返回；音频就绪封面失败允许无图继续。保持唯一内置默认图约定，前台资源及渲染在 STEP-014。

**不在本STEP范围内**：

- AC-073/086 只承担封面一侧，AC-085 只承担服务端图片/目录版本独立；前台与准备状态分别在 STEP-012/014/019 验证。
- 不建独立封面库、动态图、裁剪/焦点编辑器或自动提取内嵌图；不增加全局默认图配置。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 不带图上传/启用、之后补图，对启用/隐藏/未启用分别换图/移除 | 无图合法；预览保存成功；发布资格不被图改变；音频版本不变 | AC-079、AC-084、AC-085、AC-086 |
| 异常 | 五角色直调封面API、提交前撤权、伪格式/坏图/超限/动态图 | 只两管理角色可写、observer只看；非法图片拒绝且旧图/音乐仍可用 | AC-054、AC-083、AC-087 |
| 异常 | 音频成功图失败、换图失败、响应丢失、同标识异内容 | 保留成功音频和旧图；先查原操作，同内容去重/异内容冲突 | AC-062、AC-088 |
| 边界 | 并发换图、注入删除中/已删除状态、OSS与DB单侧成功、旧上传迟到 | 一致版本，曲目不复活；所有新旧对象可追踪并补偿；日志真实 | AC-073、AC-089 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-006] 完成等期手动删除与专属资产清理

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：符合条件的素材可经一次确认手动清理，音频及所有归属封面/残留逐项可核对并可重试。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | F-008 | 音频校验、转码、复用 OSS 发布及手动清理资产 | PRD / P01 L59 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-034 | 当前隐藏且满服务器等待期才删；重隐藏重计；未发布且无活动处理可直接清理 | PRD / P01 L521 |
| 需求ID | BR-035 | 删除期间不可发布；音频和专属封面分别可定位，部分失败保持删除未完成并支持手动重试 | PRD / P01 L522 |
| 需求ID | BR-050 | 隐藏保留图；替换／移除保留旧对象清理依据；删曲清理所有仍归属该曲且需清理的专属资产，部分失败可重试 | PRD / P01 L537 |
| 验收ID | AC-054 | 两管理角色全权，观察者只读试听／预览，另两角色无管理访问；直接 API 同样限制〔本STEP范围：删除及删除失败重试写权限〕 | PRD / P01 L701 |
| 验收ID | AC-063 | 启用／不足期拒绝，达到期且仍隐藏允许；服务端判断；24 小时只是建议，测试用实际配置 | PRD / P01 L710 |
| 验收ID | AC-064 | 到期无自动删除；再次隐藏重计；未发布无活动处理可清理，无在线／审批门槛 | PRD / P01 L711 |
| 验收ID | AC-065 | 保持不可发布，逐项结果可查和手动重试；已不存在幂等成功，部分成功不能报全部成功；不删除默认图／朋友圈资产 | PRD / P01 L712 |
| 验收ID | AC-072 | 原曲目 ID 保留，新尝试受限；旧结果不能就绪／发布；源已清理需重选〔本STEP范围：删除后迟到旧attempt不得就绪或发布〕 | PRD / P01 L719 |
| 验收ID | AC-073 | 所有已生成对象可关联核对及补偿，结果未知不换键盲重传；当前有效图／音乐不误删；具体记录时序按验证方案〔本STEP范围：音频及封面删除部分成功的剩余定位与恢复〕 | PRD / P01 L720 |
| 验收ID | AC-089 | 冲突明确、旧结果不覆盖新值；删除中／已删除不复活；已写入对象可定位清理，日志记录真实结果〔本STEP范围：真实删除与封面保存交错时不复活，残留仍可定位清理〕 | PRD / P01 L736 |
| 验收ID | AC-090 | 隐藏保留图；删曲清理音频及专属封面，部分失败定位保留且可重试；默认黑胶与朋友圈图片不受影响 | PRD / P01 L737 |
| 验收ID | AC-091 | 新关联不回滚；当前有效图不误删；旧版本／残留归属可追踪，最终清理不遗漏；不强制具体回收时点或新增任务平台 | PRD / P01 L738 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-004 | BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-005 | 管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `backend/services/feed_image_service.py` | `existing` | `REPO_BASELINE` | B03 / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | 对应需求、复用点或需保留的基线 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B04 / L224–242 OSS 配置名称；未读取真实凭证 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.html` | `existing` | `REPO_BASELINE` | D04 / L56 角色；L66–86 列表/上传/封面 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.js` | `existing` | `REPO_BASELINE` | D05 / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | 对应需求、复用点或需保留的基线 |
| `docs/tech-debt/active/life-feed.md` | `existing` | `CONTRACT`（REFERENCE_ONLY） | T01 / L11 TD-032；L42 TD-035；L52 TD-036 | 仅只读背景参考，不作本期需求、验收或技术债承接来源 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM 删除/回收服务、逐对象清理记录、页面确认/重试与墓碑，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：删除资格判断、不可发布删除态、逐对象清理、剩余失败手动重试及最小审计/幂等墓碑。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 曾发布：当前隐藏且满足最近隐藏后的实际等待期，服务端时间判断；重启用后再隐藏重新计时。 | PRD / F-007、F-008、F-009、BR-034、BR-035、BR-050 |
| 本STEP规则2 | 从未发布，且处于未启用或处理失败状态，且无活动处理，才可立即清理；曾发布者均按隐藏等待期判断。已启用不可删；到期不自动执行。 | PRD / F-007、F-008、F-009、BR-034、BR-035、BR-050 |
| 本STEP规则3 | 清理该曲目音频、当前及旧封面和已定位残留；不触碰内置默认图/朋友圈资产。 | PRD / F-007、F-008、F-009、BR-034、BR-035、BR-050 |

**开发任务**：

1. 沿用 demo 普通确认和分项音频/封面结果，展示服务器计算的最近隐藏/可删除时间并明确时区；24小时只是候选。
2. 先持久化不可发布的删除处理中及完整资源定位，再逐对象清理；对象已不存在计该对象成功，部分失败保持删除未完成、保留剩余定位。
3. 替换/移除封面后的受控回收与最终删曲都按归属检查，旧图清理失败不回滚新关联；重复请求、旧上传完成和重启用不能复活删除态。
4. 成功保留最小墓碑/原操作去重映射，普通列表排除；恢复查询与手动重试不重造素材，接入审计；禁止把朋友圈隐藏型 DELETE 当真实对象删除实现。
5. 把删除与处理重试/封面保存交错做真实接口并发回归：删除态提交后旧attempt/迟到封面不能就绪、重关联或发布，已生成残留仍可查询归属和清理。

**不在本STEP范围内**：

- 不新增到期自动删除队列、在线人数判断、审批、回收站；不承诺清除 CDN/终端缓存副本；不改变朋友圈隐藏型DELETE与现有内容管理范围；T01仅作背景。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 隐藏满实际等待T并手动确认，或未发布无活动素材 | 只清本曲目专属对象，成功留墓碑，普通列表不显示 | AC-063、AC-064、AC-090 |
| 异常 | 启用中/不足T/越权/仍有活动处理时删除；音频或一张图删除失败 | 拒绝无资格操作；部分失败不可发布、可查可重试，不报全成功 | AC-054、AC-063、AC-065、AC-073、AC-090 |
| 边界 | 恰好T、隐藏满期不点击、重新启用再隐藏、对象已不存在 | 服务端边界正确；不自动删；重新计时；不存在幂等成功 | AC-063、AC-064、AC-065 |
| 边界 | 多次换图/移除产生旧图与残留，回收后最终删曲 | 当前有效图不误删，旧对象无遗漏；默认图和朋友圈对象保持不变 | AC-090、AC-091 |
| 异常 | 删除已提交后旧音频attempt/封面上传完成 | 曲目不复活，残留保持定位并可清理 | AC-072、AC-089 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-007] 提供匿名一致目录与受控服务端缓存

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：访客和登录用户可匿名读取相同完整有序快照，Redis 异常时也不会泄露信息或无限回源。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-006 | 公开歌单、事件触发更新与目录缓存 | PRD / P01 L57 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-001 | 公共音乐对访客开放；原页面权限照常执行 | PRD / P01 L488 |
| 需求ID | BR-026 | 只返启用且就绪内容与完整版本，匿名且无用户 Token | PRD / P01 L513 |
| 需求ID | BR-029 | 缓存失效／更新并保留有限 TTL；回源受控，快照一致 | PRD / P01 L516 |
| 验收ID | AC-045 | 同一公开快照，无用户 Token、偏好、源文件、内部 Key／凭证；空封面合法，音频与封面版本独立 | PRD / P01 L692 |
| 验收ID | AC-053 | 有界回源或明确失败，版本快照完整，无无限旧缓存和音频全表解析 | PRD / P01 L700 |
| 验收ID | AC-060 | 数据库真实状态、版本和日志可核对；不误报完全失败引导重复操作〔本STEP范围：目录提交后的Redis失效失败返回真实已提交结果〕 | PRD / P01 L707 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-004 | BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-005 | 管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-006 | 删除资格判断、不可发布删除态、逐对象清理、剩余失败手动重试及最小审计/幂等墓碑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/life-feed/api.md` | `existing` | `CONTRACT` | C06 / L114–122 现有OSS图片Key与业务边界 | 对应需求、复用点或需保留的基线 |
| `backend/redis_client.py` | `existing` | `REPO_BASELINE` | B05 / L15–33 init_redis/get_redis：复用连接池，未有BGM缓存/超时/限流 | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `backend/main.py` | `existing` | `REPO_BASELINE` | B07 / 路由注册；L268–273 admin_page 静态响应 | 对应需求、复用点或需保留的基线 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B04 / L224–242 OSS 配置名称；未读取真实凭证 | 对应需求、复用点或需保留的基线 |
| `backend/utils/auth_middleware.py` | `existing` | `REPO_BASELINE` | H20 / L44–64 get_current_user/get_current_user_optional 为路由依赖，无全局BGM白名单 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 公开 BGM 路由/DTO/目录缓存与契约增量，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：公开目录读取能力、启用且就绪过滤、唯一默认/独立封面元数据及管理变更缓存接线。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 公开目录无用户Token/个人偏好/源文件/内部Key/凭证；无封面合法。 | PRD / F-006、F-009、BR-001、BR-026、BR-029 |
| 本STEP规则2 | 列表、默认与目录版本来自同一完整快照；有限TTL及管理变更更新/失效。 | PRD / F-006、F-009、BR-001、BR-026、BR-029 |
| 本STEP规则3 | Redis 故障有界回源或明确不可用；提交后失效失败不伪报DB失败。 | PRD / F-006、F-009、BR-001、BR-026、BR-029 |

**开发任务**：

1. 按 STEP-001 核实后登记的入口提供匿名读，使用现行响应信封；补充共享匿名约定/H5契约，不能把 PRD 建议 /api/bgm/catalog 当已存在事实。
2. 从同一数据库快照构建启用且音频就绪的有序目录与唯一默认，空目录默认空；只暴露必要 HTTPS 音频/可空图片URL及独立版本。
3. 复用现有 Redis 客户端；实现有限TTL、管理提交后的版本缓存接线、失效失败后的有限过期路径，故障时限流/在途合并受控回源，不在读目录时解析或下载音频。
4. 故障响应与有效空目录区分；缓存不能拼接两个版本；将实际TTL和故障回源参数验证记录，不新增缓存服务。

**不在本STEP范围内**：

- 客户端事件/缓存/失败预算由 STEP-012 负责；目录读不处理音频/封面或修改记录；不新增用户偏好服务。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 匿名及登录浏览器读有图/无图/空目录 | 响应完全相同、无 Authorization依赖与管理信息，快照完整 | AC-045 |
| 异常 | Redis不可用、缓存变更失效失败后读取 | 有界回源或明确失败；管理真实提交可核对，不全表解析媒体 | AC-053、AC-060 |
| 边界 | TTL到期与并发目录变更交错 | 返回完整单一版本；不会无限旧缓存或混用默认 | AC-053 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-008] 接通 BGM 审计及既有日志筛选

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：音频、目录、封面与资源清理的真实操作结果能在现有日志中按 BGM 动作查询。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | BR-041 | 记录操作者、音频／封面动作、对象、结果、操作关联与版本；BGM 筛选含封面新增／替换／移除与清理 | PRD / P01 L528 |
| 需求ID | BR-042 | 本期仅预留事件与本地调试，不新建采集管线 | PRD / P01 L529 |
| 验收ID | AC-060 | 数据库真实状态、版本和日志可核对；不误报完全失败引导重复操作〔本STEP范围：缓存失败/丢响应的日志结果关联与筛选核对〕 | PRD / P01 L707 |
| 验收ID | AC-077 | 审计可区分音频、封面与清理结果，不泄露敏感载荷；新增诊断仅本地，五项偏好不服务端保存〔本STEP范围：音频/封面/清理及拒绝写入的后台审计、筛选和脱敏〕 | PRD / P01 L724 |
| 验收ID | AC-083 | 权限与音乐管理一致，观察者只能看；服务端拒绝越权并可审计，不仅前端隐藏按钮〔本STEP范围：封面授权/越权动作审计结果〕 | PRD / P01 L730 |
| 验收ID | AC-089 | 冲突明确、旧结果不覆盖新值；删除中／已删除不复活；已写入对象可定位清理，日志记录真实结果〔本STEP范围：封面并发与资产结果审计可核对〕 | PRD / P01 L736 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-004 | BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-005 | 管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-006 | 删除资格判断、不可发布删除态、逐对象清理、剩余失败手动重试及最小审计/幂等墓碑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-007 | 公开目录读取能力、启用且就绪过滤、唯一默认/独立封面元数据及管理变更缓存接线。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/admin-security-accounts/api.md` | `existing` | `CONTRACT` | C05 / L9–26 日志接口/角色/筛选 | 对应需求、复用点或需保留的基线 |
| `backend/utils/admin_auth.py` | `existing` | `REPO_BASELINE` | B01 / L93–197 get_current_admin/require_role；L212–250 log_operation | 对应需求、复用点或需保留的基线 |
| `backend/database.py` | `existing` | `REPO_BASELINE` | B06 / L37–50 get_db：yield 后提交 | 对应需求、复用点或需保留的基线 |
| `admin/pages/operation-logs.html` | `existing` | `REPO_BASELINE` | B08 / 模块/动作筛选及操作日志渲染 | 对应需求、复用点或需保留的基线 |
| `backend/routers/admin/operation_logs.py` | `existing` | `REPO_BASELINE` | B09 / 操作日志查询 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/admin.js` | `existing` | `REPO_BASELINE` | D05 / L39–60 权限/本地提交；L115–217 运营/封面；L266–305 模拟上传 | 对应需求、复用点或需保留的基线 |
| `backend/models/admin_operation_log.py` | `existing` | `REPO_BASELINE` | B20 / L13–42 字段长度、UTC及留存 | 对应需求、复用点或需保留的基线 |
| `tests/test_step012_operation_log_redaction.py` | `existing` | `REPO_BASELINE` | V03 / 现有日志脱敏回归入口；未运行 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 日志模块/动作筛选和审计验证增量，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：既有操作日志的 BGM 模块/动作筛选与全管理链路审计核对证据。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 记录操作者/角色、动作、对象、结果、操作关联、版本及时间；部分清理失败不能计全成功。 | PRD / F-007、BR-041、BR-042 |
| 本STEP规则2 | 不记录Token/密钥/文件二进制/五项偏好；用户端诊断默认仅本地。 | PRD / F-007、BR-041、BR-042 |

**开发任务**：

1. 复用既有日志能力并分别核对事务边界：成功管理写入的目录/操作/必要审计同事务可追踪；鉴权层提前403或业务失败rollback时，拒绝/失败审计用STEP-001/002确定的独立持久化接点保留。不能只在业务handler中flush，也不得放宽observer写权限换取日志。
2. 在既有操作日志页/API筛选接入 BGM 模块及音频、封面新增/替换/移除、删除/清理等动作，不另建日志系统。
3. 对已提交后缓存失败、封面并发拒绝及越权写入核对实际结果；只保留脱敏且可定位的必要证据。
4. 检查后台日志载荷脱敏及失败/拒绝结果持久化，不记录文件正文/密钥/Token/五项偏好。H5新增诊断/网络的子条款分别由STEP-009/019负责。

**不在本STEP范围内**：

- 本 STEP 只承担 AC-083/089 的审计子条款；权限与并发实际业务分别由 STEP-002/005 负责。
- 不改变现有日志留存政策、不新增用户行为报表/上报平台。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 逐一执行各类授权管理动作，再按模块/动作筛选 | 对象/操作者/结果/版本/操作可对应，日志权限沿用现行约定 | AC-077 |
| 异常 | 越权、封面冲突、部分清理失败、DB提交后丢响应/缓存失效 | 记录真实结果、无伪报全成全败、无重复成功 | AC-060、AC-083、AC-089 |
| 边界 | 检查后台日志载荷及拒绝403后重新查询日志 | 拒绝/失败审计已独立持久化，业务数据无变更，无文件正文/凭证/Token/五项偏好 | AC-077、AC-083 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-009] 实现五项本地偏好与公开设置

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：提供五项本地偏好读写/降级与公开设置，原motion保持权限和作用范围；模块不因保存设置而主动产生播放命令。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-003 | 本地偏好与现有设置页接入 | PRD / P01 L54 |
| 需求ID | BR-007 | 两个 BGM 开关在公开区；原主页动效沿用原权限 | PRD / P01 L494 |
| 需求ID | BR-008 | 五项偏好仅同源浏览器本地，共用本机值 | PRD / P01 L495 |
| 需求ID | BR-009 | 使用字段默认与校验；本地→会话→内存逐级降级并说明范围 | PRD / P01 L496 |
| 需求ID | BR-010 | 复用现有持久化键和人物／场景语义 | PRD / P01 L497 |
| 需求ID | BR-011 | 开关只决定无会话时的初始意图，任一允许页均适用 | PRD / P01 L498 |
| 需求ID | BR-042 | 本期仅预留事件与本地调试，不新建采集管线 | PRD / P01 L529 |
| 验收ID | AC-014 | 开关公开且生效，不弹登录；原主页动效仍遵循原门禁 | PRD / P01 L661 |
| 验收ID | AC-015 | 本机值保留，无账号分区、偏好接口／服务端落库／偏好事件上报〔本STEP范围：五项字段及本地读写/无账号分区/模块网络边界；正式控件修改五项与账号往返的声音/选曲闭环由STEP-014负责〕 | PRD / P01 L662 |
| 验收ID | AC-016 | 渐变、自动播放、主页动效默认开，音量 30%、手选为空；设备间独立 | PRD / P01 L663 |
| 验收ID | AC-017 | 当前播放意图不被开关改变；后续新访问采用设置，当前不误出声〔本STEP范围：设置读写只改偏好，模块不主动发播放/暂停/关闭命令；正式播放/暂停/关闭及新访问闭环由STEP-014负责〕 | PRD / P01 L664 |
| 验收ID | AC-018 | 逐级降级，合法字段保留；即时操作有效，提示真实保存范围，不上报偏好 | PRD / P01 L665 |
| 验收ID | AC-019 | 原动效范围／本地值保留；不改倾斜授权、音乐或渐变开关〔本STEP范围：原键/权限/人物场景语义/倾斜独立性，模块不改BGM偏好或主动发播放命令；真实BGM不中断由STEP-014负责〕 | PRD / P01 L666 |
| 验收ID | AC-077 | 审计可区分音频、封面与清理结果，不泄露敏感载荷；新增诊断仅本地，五项偏好不服务端保存〔本STEP范围：本地偏好/设置诊断不发服务端，不带五项偏好〕 | PRD / P01 L724 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-001 | 一份随主文档维护的技术采用记录：接口/模型/事务边界、资源归属、受限处理方案、音频能力策略与 SUG 验证分工。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/settings.html` | `existing` | `REPO_BASELINE` | H02 / L531–652 私有区；L654–688/707–749 设置；L1027–1055 退出 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | H03 / L95–126 request默认Token；L171–185 clearToken；L294–426登录弹窗 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/home-preferences.js` | `existing` | `REPO_BASELINE` | H04 / L4–37/L40–114 motion本地/会话/内存降级及倾斜独立能力 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/home-scene.js` | `existing` | `REPO_BASELINE` | H05 / L79–140/L411–434 场景可见性/bfcache/motion，非BGM生命周期 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/README.md` | `existing` | `REPO_BASELINE` | D01 / L1–41 V1.3 范围、参数、模拟边界 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM本地偏好模块及设置页公开区增量，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：偏好字段校验/降级模块，既有设置页的两个公开开关，以及原主页动效能力的兼容接入。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 主页动效/音乐渐变/自动播放默认开，应用音量0.30，最后手选空；音量范围0～1。 | PRD / F-003、BR-007、BR-008、BR-009、BR-010、BR-011、BR-042 |
| 本STEP规则2 | motion 沿用 lxm_home_motion_enabled 的0/1和原 lxm_home_motion_session降级；倾斜授权不属于五项。 | PRD / F-003、BR-007、BR-008、BR-009、BR-010、BR-011、BR-042 |
| 本STEP规则3 | 自动播放只决定无既有会话的新访问意图；改开关不自动改变当前播放/暂停/关闭。 | PRD / F-003、BR-007、BR-008、BR-009、BR-010、BR-011、BR-042 |

**开发任务**：

1. 在 settings-private-sections 外增加公开BGM开关及“仅影响新访问”说明；原motion仍在既有权限范围，不另建设置页。
2. 五项不带账号ID、不调偏好API、不上报；登录/退出/换账号只沿用必要账号清理，禁止全站存储清空。
3. BGM新增键/版本/字段名按已核实约定在采用记录中确定，不照搬 demo 的 lxm_bgm_demo_*；字段级校验，未知版本不按旧结构强解或清空合法数据。
4. local→session→memory逐级兜底，修改即时生效，提示实际保留范围；成功持久化后清相应临时覆盖，正常保存不额外弹成功窗。
5. 提供音量/手选的本地读写接口供播放器调用；保存开关或motion只改相应偏好，模块不主动发播放/暂停/关闭命令。正式音量拖动即时应用、结束合并写入、列表/手动下一首记手选及账号往返的实际音量/曲目反馈由STEP-014接线和验收。
6. 新增设置/偏好诊断默认仅本地，检查模块和设置页网络无偏好上报；后续准备/封面诊断由STEP-019核对，合起来满足AC-077的H5子条款。

**不在本STEP范围内**：

- AC-015/017/019的正式播放器/控件与账号往返闭环由STEP-014负责，本STEP不依赖STEP-010/013/014的后置产物。STEP-013新访问证据可由014复用，不形成009反向依赖。
- 不修改倾斜传感器授权、不把motion变为声音总开关、不引入账号同步或多标签页实时遥控。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 在正式设置页修改两个公开开关/按权限修改motion；通过本模块读写接口写音量与手选字段，再读取存储 | 开关不弹登录；五项仅本地且不含账号ID，模块不请求偏好API/上报；原motion键/权限/人物场景语义及倾斜独立性保持；不把接口写字段当正式音量/选曲闭环 | AC-014、AC-015、AC-019 |
| 异常 | 单字段损坏/未知版本/local拒写/session也拒写 | 合法字段保留、逐级降级、提示真实保存范围，无偏好上传 | AC-018 |
| 边界 | 清站点数据、新浏览器/不同设备同账号；仅调用偏好模块及设置开关读写，观察模块调用/事件 | 默认值与设备独立正确；开关只改偏好，不主动发播放/暂停/关闭命令。真实播放/暂停/关闭与新访问子项留给STEP-014 | AC-016、AC-017 |
| 异常 | 打开偏好诊断并模拟保存失败、登录/退出 | 只本地反馈，不向服务端发送偏好/诊断载荷 | AC-077 |

**完成标志**：

- [ ] AC-015/017/019仅结算本地模块/公开设置子条款，有自身字段/调用/网络及原motion兼容证据即可；未测的STEP-014正式接线子项不得据此标成整条AC完成，不为等待后置播放器增加反向依赖。
- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-010] 实现单文档播放意图和顺序控制

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：同一文档只有一个共享控制器，手动/自然切歌及暂停关闭都服从最后有效意图。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | BR-004 | 按有效顺序；暂停时下一首只选择；仅手动行为更新最后手选 | PRD / P01 L491 |
| 需求ID | BR-012 | 初始化按有效会话→有效最后手选→默认→第一首→空态；运行中目录更新发现当前失效按 BR-028 回退默认／第一首 | PRD / P01 L499 |
| 需求ID | BR-013 | 意图、实际状态、关闭及阻断分离，出声前重检 | PRD / P01 L500 |
| 需求ID | BR-014 | 立即停止并记会话关闭；仅主页明确播放／列表选曲重开 | PRD / P01 L501 |
| 需求ID | BR-017 | 最新有效操作胜出，旧任务及动画回调失效 | PRD / P01 L504 |
| 验收ID | AC-006 | 分别从头选播、不重启、续播；状态与选择区分〔本STEP范围：控制核心的选行语义〕 | PRD / P01 L653 |
| 验收ID | AC-007 | 播放中换曲继续；暂停中仅选择、进度归零；按顺序回首曲〔本STEP范围：控制核心播放/暂停下一首与回首〕 | PRD / P01 L654 |
| 验收ID | AC-008 | 下一首禁用；自然从头循环，并在曲终检查过期目录〔本STEP范围：单曲禁用与自然曲终复核入口〕 | PRD / P01 L655 |
| 验收ID | AC-020 | 前两者记最后手选，后两者不改写；新访问有效历史优先于默认 | PRD / P01 L667 |
| 验收ID | AC-025 | 最后有效操作胜出，旧回调无声、无旧进度覆盖、无多曲并播 | PRD / P01 L672 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-009 | 偏好字段校验/降级模块，既有设置页的两个公开开关，以及原主页动效能力的兼容接入。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/home-preferences.js` | `existing` | `REPO_BASELINE` | H04 / L4–37/L40–114 motion本地/会话/内存降级及倾斜独立能力 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/shared-catalog.js` | `existing` | `REPO_BASELINE` | D06 / L4–10 参数；L82–126 本地目录；L131–243 图像预览 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM共享控制器、操作代次和媒体适配核心及专项测试，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 不同列表行从头播放；正在播放当前行不重启；暂停当前行续播。 | PRD / F-004、BR-004、BR-012、BR-013、BR-014、BR-017 |
| 本STEP规则2 | 手动下一首：播放中换曲继续，暂停中只选且进度归零；末尾回首；单曲禁用手动下一首。 | PRD / F-004、BR-004、BR-012、BR-013、BR-014、BR-017 |
| 本STEP规则3 | 只有手动列表/下一首写最后手选，自然切歌/失效回退不写；关闭只由主页明确播放/列表选曲重开。 | PRD / F-004、BR-004、BR-012、BR-013、BR-014、BR-017 |

**开发任务**：

1. 将意图、会话关闭、实际媒体/输出状态、临时阻断分开；pause事件不能一律当手动暂停，canplay或play兑现不能单独代表有效输出。
2. 使用按需媒体、共享操作代次/取消机制，pause/close立即提交意图，旧请求/旧进度/旧过渡完成不能复活；同文档最多一首输出。
3. 实现初始化选择优先级：有效会话及合法检查点→有效最后手选→默认→第一首→空；运行中新目录失效回退由STEP-012接线。
4. 关闭入口保留动作来源限制：开面板/下一首/气泡/跳页/自然结束不得解除关闭。阻断中即使主页明确操作也不能出声。
5. 用可注入有效目录和媒体事件验证核心；实际匿名获取/有限故障链由STEP-012实现，渐变/能力由STEP-011实现。

**不在本STEP范围内**：

- 不实现UI、网络目录缓存、页面恢复或自动播放绕过；不新增上一首、随机、进度拖动。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 新行/当前播放行/暂停当前行，播放和暂停分别下一首 | 结果符合选择/续播/归零语义，手动才写最后手选 | AC-006、AC-007、AC-020 |
| 异常 | 延迟旧媒体请求，快速播放暂停/多次选曲后关闭 | 仅最后有效操作生效；旧回调无声、无旧检查点覆盖 | AC-025 |
| 边界 | 单曲与列表末尾、自然ended、历史曲失效 | 下一首禁用/回首正确；自然事件保留目录复核接口，不改手选 | AC-007、AC-008、AC-020 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-011] 实现真实增益、淡入淡出和能力降级

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：正常能力环境的播放/暂停/切歌有可听渐变，能力不足时保留可用基本播放和可靠静音。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | BR-015 | 默认按开关渐变；暂停意图立即生效，切歌先停旧再播新 | PRD / P01 L502 |
| 需求ID | BR-016 | 增益真实有效；零值可靠静音；设备音量降级保留明确取消静音入口，用户操作后才将零值改为默认非零值 | PRD / P01 L503 |
| 验收ID | AC-023 | 开始／继续渐入、暂停渐出；暂停意图即时生效；时长按实际验证配置检查，0.5 秒仅建议 | PRD / P01 L670 |
| 验收ID | AC-024 | 开时先淡出后渐入，无重叠；关时直接操作；暂停下一首无声，后续采用新开关 | PRD / P01 L671 |
| 验收ID | AC-026 | 基本播放仍可用；说明能力，保留用户渐变开关；恢复能力后继续采用原偏好 | PRD / P01 L673 |
| 验收ID | AC-027 | 有效滑杆真实控制；降级有取消静音入口，操作后保存默认非零值并可出声；不自动解除零值，不假称修改系统音量 | PRD / P01 L674 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-009 | 偏好字段校验/降级模块，既有设置页的两个公开开关，以及原主页动效能力的兼容接入。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-playback.js` | `existing` | `REPO_BASELINE` | H07 / VoicePlayback：通话输出所有权 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/music-glass.css` | `existing` | `REPO_BASELINE` | D09 / L10–22 磨砂；L75–205 控件/滤镜降级 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM输出能力检测/增益/过渡适配与降级控件协议，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 渐变默认开；紧急关闭/隐藏/通话立即阻断，不等待渐变；不重叠两首。 | PRD / F-004、BR-015、BR-016 |
| 本STEP规则2 | 降级顺序是可用增益→经验证有效媒体音量→基本播放/设备音量；无效滑杆隐藏。 | PRD / F-004、BR-015、BR-016 |
| 本STEP规则3 | 已存音量零值始终静音；设备音量降级仅明确取消静音后将本地值改为默认0.30。 | PRD / F-004、BR-015、BR-016 |

**开发任务**：

1. BGM持有独立媒体/输出上下文，不借用或销毁通话对象；检查媒体与实际上下文均可用才报播放态。
2. 播放就绪后从零渐入，暂停先写意图再淡出并物理暂停/保存实际进度；播放中换曲旧曲淡出停止后新曲渐入，允许加载空隙。
3. 渐变关闭直接操作；过渡中改开关安全收敛、下一次采用新值；最新操作使旧渐变完成失效。0.5秒等用实际验证记录。
4. 实测相对音量与静音；设备音量降级提供可靠静音/取消静音与提示，保留渐变开关/非零本地值供能力恢复使用；基本播放失败进入错误而非成功降级。

**不在本STEP范围内**：

- 不实现均衡器、无缝跨曲、系统物理音量设置或锁屏后台播放。本STEP负责的真实浏览器输出/静音/降级证据在本STEP完成前取得，可在已有隔离媒体验收环境验证；STEP-020/021只做完整资源链和闭环复核。缺少相应环境时本STEP保持BLOCKED，不能提前标DONE。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 渐变开/关开始继续暂停切歌，暂停中下一首 | 正常开时可听渐变、先停旧再播新；暂停下一首无声 | AC-023、AC-024 |
| 异常 | 注入不可用增益/无效媒体音量/基本播放失败 | 只采用验证有效路径；说明降级、保留偏好，基本播放失败不假报成功 | AC-026、AC-027 |
| 边界 | 音量零后降级，未点击/明确取消静音，过渡中改开关 | 未授权不解除静音；明确操作后才存0.30，开关不改变意图 | AC-024、AC-027 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-012] 接入事件目录与统一有限故障链

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：播放器按事件读取匿名目录并在真实故障中有限尝试，耗尽后等待明确BGM操作恢复。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | F-006 | 公开歌单、事件触发更新与目录缓存 | PRD / P01 L57 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-012 | 初始化按有效会话→有效最后手选→默认→第一首→空态；运行中目录更新发现当前失效按 BR-028 回退默认／第一首 | PRD / P01 L499 |
| 需求ID | BR-018 | 区分权限与资源故障，按总预算有限尝试，保留人工恢复 | PRD / P01 L505 |
| 需求ID | BR-027 | 事件触发、新鲜复用、在途合并，失败不更新成功时间 | PRD / P01 L514 |
| 需求ID | BR-028 | 失效当前曲按意图回退；空目录允许静默；排序仅影响后续 | PRD / P01 L515 |
| 验收ID | AC-009 | 三种情况明确区分；空态不阻塞页面，暂时失败有手动恢复，无无限等待〔本STEP范围：有效空/暂时目录故障/全部音频失败三类与有界恢复〕 | PRD / P01 L656 |
| 验收ID | AC-028 | 无假旋转、无任意点击重试；明确播放可重试媒体及上下文，不换歌绕过权限 | PRD / P01 L675 |
| 验收ID | AC-029 | 候选、时长和重试受限；旧曲仅在最新意图许可时恢复，不覆写手选 | PRD / P01 L676 |
| 验收ID | AC-030 | 加载不假装正常播放；操作立即记录，预算后人工恢复；无迟到复播 | PRD / P01 L677 |
| 验收ID | AC-046 | 无周期目录请求／推送；若触发轻量预加载，不得额外变成目录定时轮询 | PRD / P01 L693 |
| 验收ID | AC-047 | 新鲜复用、过期按需请求，单个在途请求共用，不逐页冷启动 | PRD / P01 L694 |
| 验收ID | AC-048 | 不为自动续播请求；主动操作可读取；失败不刷新成功缓存时间 | PRD / P01 L695 |
| 验收ID | AC-050 | 有效音频不重启；只换封面只刷新图；失效按意图回退，暂停／关闭不被后台变更复活 | PRD / P01 L697 |
| 验收ID | AC-051 | 默认空，停播空态，主页入口可用，其他页面业务照常 | PRD / P01 L698 |
| 验收ID | AC-052 | 有限预算和次数有效；耗尽标记不被冷却／跳页清除；手动也不能绕过旧目录上限；不固定为建议的 3 首／30 秒 | PRD / P01 L699 |
| 验收ID | AC-059 | 合法原子更新，不合法拒绝；当前曲不因排序被重启〔本STEP范围：取得新排序后有效当前曲不重启，后续按新顺序切歌〕 | PRD / P01 L706 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-007 | 公开目录读取能力、启用且就绪过滤、唯一默认/独立封面元数据及管理变更缓存接线。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | H03 / L95–126 request默认Token；L171–185 clearToken；L294–426登录弹窗 | 对应需求、复用点或需保留的基线 |
| `backend/redis_client.py` | `existing` | `REPO_BASELINE` | B05 / L15–33 init_redis/get_redis：复用连接池，未有BGM缓存/超时/限流 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/shared-catalog.js` | `existing` | `REPO_BASELINE` | D06 / L4–10 参数；L82–126 本地目录；L131–243 图像预览 | 对应需求、复用点或需保留的基线 |
| `backend/utils/auth_middleware.py` | `existing` | `REPO_BASELINE` | H20 / L44–64 get_current_user/get_current_user_optional 为路由依赖，无全局BGM白名单 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 匿名目录客户端、缓存/有限故障预算与人工恢复会话字段，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：匿名目录客户端、跨文档可复用完整缓存、在途合并、目录更新对账及统一失败预算。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 无事件无目录请求；新鲜复用、过期按需，失败不刷新成功时间；超龄旧目录不能新开/切歌/循环。 | PRD / F-004、F-006、F-009、BR-012、BR-018、BR-027、BR-028 |
| 本STEP规则2 | 播放/暂停/关闭/隐藏分别约束自动取资源；主动开面板或重试可查目录但不自动出声。 | PRD / F-004、F-006、F-009、BR-012、BR-018、BR-027、BR-028 |
| 本STEP规则3 | 故障链统一总预算/有限候选/限次；同一失败曲不循环重试；权限被拦不换歌绕过。 | PRD / F-004、F-006、F-009、BR-012、BR-018、BR-027、BR-028 |
| 本STEP规则4 | 耗尽人工恢复标记跨页保存；冷却到期、自然事件或目录刷新成功都不能自动获得新预算/复播。 | PRD / F-004、F-006、F-009、BR-012、BR-018、BR-027、BR-028 |

**开发任务**：

1. 新增显式不附Token的读取路径或严格受限选项；现 request 自动带Token，不能直接照搬，也不能改变其他API默认鉴权。
2. 实现初始化有播放需要/可见返回/明确播放/开面板/手动切歌/曲终/重试的缓存判断及在途合并，复用同标签页完整快照和校验时间；不定时轮询或推送。
3. 区分有效空目录、目录失败和所有媒体失败；有限旧目录故障回退保留成功时间，时钟倒退/非法年龄视过期；到期允许当前已播放媒体完成但不凭旧目录新循环。
4. 新目录只修正失效当前曲及候选，按最新意图回退默认/第一首或空；改名/排序/默认/封面不重启有效音频，封面数据更新独立。
5. 将目录和音频等待/重试/候选回退合入同一剩余预算；故障预算/SUG缓存建议在采用记录确认后测边界；手选失败仅最新意图许可时恢复有效旧曲进度。
6. 自动播放/AudioContext被拦只等明确音乐播放，不借任意点击重试；持续缓冲/输出挂起不假旋转，所有等待仍允许暂停/关闭，耗尽保存人工恢复资格。
7. 对AC-059的H5子条款注入新排序目录：有效当前媒体/进度不重建，之后切歌采用新顺序。此处使用当前控制器真实接线，不等待STEP-004去证明尚未建立的前台。

**不在本STEP范围内**：

- 不实现音频持久库/全歌单预取；预加载不是额外目录定时器；不将公开目录空态当网络失败。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 新鲜/过期跨页初始化，多事件并发，静置越过TTL | 缓存复用/单个在途请求正确；无事件无周期请求 | AC-046、AC-047 |
| 异常 | 权限拦截、坏曲、手选失败、持续缓冲，期间暂停/关闭 | 明确操作才恢复；权限不换曲；不迟到复播，人工恢复有界 | AC-028、AC-029、AC-030 |
| 异常 | 有效空目录、暂时目录失败、所有媒体失败 | 三者可区分，保留人工恢复而不阻塞页面/无限等待 | AC-009、AC-051 |
| 边界 | 暂停/关闭/隐藏后过期，主动开面板；改名默认排序封面或隐藏当前 | 只有允许事件取目录；失败不续期；有效音频不重启、失效按意图回退 | AC-048、AC-050 |
| 边界 | 耗尽后冷却到期/自然事件/跳页/超龄缓存/明确重试 | 无自动新预算；手动也不绕过旧目录上限，采用参数可证明有限 | AC-052 |
| 边界 | 播放中取得原子新排序并观察当前媒体，再执行后续切歌 | 当前有效曲不重启，随后使用新顺序 | AC-059 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-013] 实现独立页面生命周期和会话恢复

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：任一允许页面可独立进入，跨HTML导航/刷新/后退恢复合法状态且不会复活暂停或关闭。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-003 | 本地偏好与现有设置页接入 | PRD / P01 L54 |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | BR-011 | 开关只决定无会话时的初始意图，任一允许页均适用 | PRD / P01 L498 |
| 需求ID | BR-013 | 意图、实际状态、关闭及阻断分离，出声前重检 | PRD / P01 L500 |
| 需求ID | BR-014 | 立即停止并记会话关闭；仅主页明确播放／列表选曲重开 | PRD / P01 L501 |
| 需求ID | BR-017 | 最新有效操作胜出，旧任务及动画回调失效 | PRD / P01 L504 |
| 需求ID | BR-019 | BGM 软依赖；加载层及正文共用控制器，已发声可暂停 | PRD / P01 L506 |
| 需求ID | BR-020 | 可用会话存储保留意图、关闭和合法检查点；初始化检查读写可靠性，同页单实例，跨文档恢复 | PRD / P01 L507 |
| 需求ID | BR-021 | 隐藏立即暂停，返回先对账再条件恢复 | PRD / P01 L508 |
| 需求ID | BR-022 | 登录页临时暂停，普通弹窗不改意图；回允许页重检 | PRD / P01 L509 |
| 验收ID | AC-021 | 开则按条件尝试，关则静止待操作；不依赖先访问主页 | PRD / P01 L668 |
| 验收ID | AC-022 | 原暂停或关闭优先；不因视为新文档而自动出声 | PRD / P01 L669 |
| 验收ID | AC-031 | 原页面加载照常；音乐先发声可暂停；正文沿用同一控制器，无二次开播 | PRD / P01 L678 |
| 验收ID | AC-032 | 同曲合法进度恢复；允许声音间断；拦截保留手动续播，不无条件从头 | PRD / P01 L679 |
| 验收ID | AC-033 | 非法值归零，不套旧媒体检查点，不按离开墙钟补进度 | PRD / P01 L680 |
| 验收ID | AC-034 | 始终保持关闭，读取最新会话；只有主页明确播放／选曲可重开 | PRD / P01 L681 |
| 验收ID | AC-035 | 本页暂停／关闭即时；初始化检测不可靠存储后不按旧状态自播；提示跨页受限，无法保存标记时不伪称可保证恢复 | PRD / P01 L682 |
| 验收ID | AC-036 | 隐藏立即暂停；只原意图有效者尝试恢复，仍受浏览器许可；无后台续播承诺 | PRD / P01 L683 |
| 验收ID | AC-040 | 独立登录页临时暂停，弹窗默认不改意图；返回重检，五项偏好不清除 | PRD / P01 L687 |
| 验收ID | AC-044 | 无跨窗遥控或播放接力；复制的关闭状态保守保留，可见性规则仍生效 | PRD / P01 L691 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-009 | 偏好字段校验/降级模块，既有设置页的两个公开开关，以及原主页动效能力的兼容接入。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-012 | 匿名目录客户端、跨文档可复用完整缓存、在途合并、目录更新对账及统一失败预算。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/index.html` | `existing` | `REPO_BASELINE` | H01 / L9–87 HomeStartup；L1468–1498/L1577–1585 more；L2092–2105 VoiceEntry.begin | 对应需求、复用点或需保留的基线 |
| `frontend/pages/settings.html` | `existing` | `REPO_BASELINE` | H02 / L531–652 私有区；L654–688/707–749 设置；L1027–1055 退出 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | H03 / L95–126 request默认Token；L171–185 clearToken；L294–426登录弹窗 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/home-scene.js` | `existing` | `REPO_BASELINE` | H05 / L79–140/L411–434 场景可见性/bfcache/motion，非BGM生命周期 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/feed.html` | `existing` | `REPO_BASELINE` | H08 / L443–471/555 图片预览；L1416–1479/1751 评论与页面接入 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/diary.html` | `existing` | `REPO_BASELINE` | H09 / L55–62/273/314–339 返回安全区及requireProtectedPage | 对应需求、复用点或需保留的基线 |
| `frontend/pages/memory.html` | `existing` | `REPO_BASELINE` | H10 / L263–264/559–606 nebula底栏/抽屉；鉴权在H18 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/relationship.html` | `existing` | `REPO_BASELINE` | H11 / L58–65/708–720/923–948/1342–1375 门禁/返回/levelup覆盖层 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/chat.html` | `existing` | `REPO_BASELINE` | H12 / L466–479/687–690/1647–1657/1861–1869 输入区/visualViewport/门禁 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/login.html` | `existing` | `REPO_BASELINE` | H13 / L244 独立登录页共享api脚本 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/memory-nebula.js` | `existing` | `REPO_BASELINE` | H18 / L53–54 requireProtectedPage；L800–815 抽屉；L1073 pagehide | 对应需求、复用点或需保留的基线 |
| `frontend/static/css/h5-theme.css` | `existing` | `REPO_BASELINE` | H19 / L531–585 登录遮罩层级与安全区 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM页面生命周期/会话/检查点模块及各HTML页面模式接线，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 同标签页会话优先于自动播放偏好；新访问从头，不按离开墙钟补进度；跨页允许声音间断。 | PRD / F-003、F-005、BR-011、BR-013、BR-014、BR-017、BR-019、BR-020、BR-021、BR-022 |
| 本STEP规则2 | 初始化校验会话可读可写；已检测不可靠不能据旧快照自动发声。 | PRD / F-003、F-005、BR-011、BR-013、BR-014、BR-017、BR-019、BR-020、BR-021、BR-022 |
| 本STEP规则3 | 隐藏立即暂停；可见/bfcache返回先对账再条件恢复；独立登录页临时暂停不关闭，普通登录弹窗不改意图。 | PRD / F-003、F-005、BR-011、BR-013、BR-014、BR-017、BR-019、BR-020、BR-021、BR-022 |

**开发任务**：

1. 各页在自身合法访问状态成立后接入共用模块；主页加载层和正文持有同一控制器，BGM不纳入HomeStartup原截止/就绪条件，已出声提供低存在感暂停。
2. 会话保存曲目/媒体版本/合法进度/意图/关闭/人工恢复/气泡比例等小型状态，不带账号；关键动作及时记录，不只依赖卸载，定期检查点按验证配置。
3. 按媒体时长/有限数值/版本验证检查点，非法或媒体版本变归零；封面变化不归零。pagehide停止旧页输出和准备，pageshow/可见返回先读取最新会话。
4. 暂停/关闭写失败本页立即生效并提示跨页受限；能读旧值但不能写同样判不可靠；无法保存任何标记时不承诺跨页一定保留。
5. 独立登录页不新启/无气泡，返回允许页条件恢复；登录弹窗/普通图片覆盖层默认仅让位控件，不使用原scene恢复事件启动BGM。
6. 两个标签页独立，无播放接力/唯一播放器选举/广播遥控；复制和会话恢复继承关闭则保守保留。

**不在本STEP范围内**：

- 不改SPA/AppShell/iframe、不承诺跨页不断音或后台锁屏持续播；通话真实接点由STEP-016负责。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 无旧会话直接进每个允许页、自动播放开/关；加载层音乐/页面先好两种顺序 | 条件尝试或静止；不依赖主页，不阻塞页面，控制器不重建 | AC-021、AC-031 |
| 异常 | 目录/音频超时，session不可读或可读不可写，再跳页 | 原页面完成；本页操作有效、提示受限，不按不可靠旧态自播 | AC-031、AC-035 |
| 边界 | 非法进度/媒体版本变、跳页被拦、已暂停/关闭刷新或bfcache恢复 | 合法进度有条件续播，否则归零/手动；旧回调不解除关闭 | AC-022、AC-032、AC-033、AC-034 |
| 边界 | 播放/暂停/关闭时隐藏锁屏返回；独立登录/登录弹窗/账号切换 | 隐藏立即停，返回重检；独立登录临停，弹窗不改意图，偏好保留 | AC-036、AC-040 |
| 边界 | 双标签、复制关闭标签页、恢复浏览器会话 | 独立控制、继承关闭保守处理，可见性规则继续有效 | AC-044 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-014] 接入主页唱片、面板和统一封面显示

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：正式主页第五格可公开打开BGM面板，视觉/可访问性与demo一致且真实状态、封面和控制结果可靠。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-001 | 主页第五格唱片、Bottom Sheet、极简歌单及控制 | PRD / P01 L52 |
| 需求ID | F-003 | 五项本地偏好接入正式控件与账号往返，保持实际声音/选曲反馈 | PRD / P01 L54/157–177 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-001 | 公共音乐对访客开放；原页面权限照常执行 | PRD / P01 L488 |
| 需求ID | BR-002 | 替换第五格；实际播放显示曲名和播放态；主页无重复气泡 | PRD / P01 L489 |
| 需求ID | BR-003 | 只改变界面；控制状态一致，手势和焦点正确 | PRD / P01 L490 |
| 需求ID | BR-008 | 正式五项操作与登录/退出/换账号往返共用本机值，不重置音量或曲目 | PRD / P01 L495 |
| 需求ID | BR-010 | 原motion键/权限/人物场景语义与倾斜独立性在正式播放中保持 | PRD / P01 L497 |
| 需求ID | BR-011 | 正式切开关不改当前播放/暂停/关闭；后续无旧会话访问采用设置 | PRD / P01 L498 |
| 需求ID | BR-015 | 正式渐变开关接线与播放意图分离；具体渐变输出由STEP-011负责 | PRD / P01 L502 |
| 需求ID | BR-042 | 正式五项设置与账号往返检查不发送偏好或新增采集 | PRD / P01 L529 |
| 需求ID | BR-047 | 整图居中圆形显示，播放旋转、暂停停止；首页／面板／气泡统一当前封面，异常回退内置通用黑胶 | PRD / P01 L534 |
| 需求ID | BR-049 | 新图保存成功才替代旧关联；失败留旧图，无图或加载失败用默认；版本／权限／曲目状态核对 | PRD / P01 L536 |
| 验收ID | AC-001 | 公共音乐不要求登录；原私有数据及页面门禁有效〔本STEP范围：主页公共播放与原四格/私有门禁〕 | PRD / P01 L648 |
| 验收ID | AC-002 | 第五格替换 more，其他入口位置保留，无额外主页气泡 | PRD / P01 L649 |
| 验收ID | AC-003 | 曲名与唱片状态对应实际媒体；零音量显示静音且不假装暂停；长名完整可读 | PRD / P01 L650 |
| 验收ID | AC-004 | 收起不中断；打开不重开关闭会话；视觉唱片连续无双份 | PRD / P01 L651 |
| 验收ID | AC-005 | 控件可触达，滚动／滑杆／收起不混淆；焦点合理，无强制持续动画 | PRD / P01 L652 |
| 验收ID | AC-006 | 分别从头选播、不重启、续播；状态与选择区分〔本STEP范围：真实主页列表点击接线〕 | PRD / P01 L653 |
| 验收ID | AC-007 | 播放中换曲继续；暂停中仅选择、进度归零；按顺序回首曲〔本STEP范围：面板下一首实际接线〕 | PRD / P01 L654 |
| 验收ID | AC-008 | 下一首禁用；自然从头循环，并在曲终检查过期目录〔本STEP范围：主页单曲控件及真实目录接线〕 | PRD / P01 L655 |
| 验收ID | AC-009 | 三种情况明确区分；空态不阻塞页面，暂时失败有手动恢复，无无限等待〔本STEP范围：三种状态主页空态/失败反馈与控制可用性〕 | PRD / P01 L656 |
| 验收ID | AC-015 | 本机值保留，无账号分区、偏好接口／服务端落库／偏好事件上报〔本STEP范围：正式音量/手选/开关/motion修改五项后登录A→退出→登录B→同浏览器再访问，核对五项及实际音量/曲目不被账号操作重置；模块子条款在STEP-009〕 | PRD / P01 L662；H5-M、H5-D、API网络检查 |
| 验收ID | AC-017 | 当前播放意图不被开关改变；后续新访问采用设置，当前不误出声〔本STEP范围：正式播放中关自动播放不停播，暂停/关闭时开渐变与自动播放不出声，后续无旧会话新访问采用设置；可复用STEP-013有效证据，正式接线仍由本STEP验证〕 | PRD / P01 L664；H5-M、SIM |
| 验收ID | AC-019 | 原动效范围／本地值保留；不改倾斜授权、音乐或渐变开关〔本STEP范围：正式页面改motion不停止真实BGM、不改渐变开关，并核对原键/权限/人物场景语义与倾斜独立性；模块兼容在STEP-009〕 | PRD / P01 L666；H5-M、静态核对 |
| 验收ID | AC-079 | 无封面合法，音频就绪／启用不受阻；使用唯一内置通用黑胶，不为每曲要求上传默认图〔本STEP范围：H5无图使用唯一内置通用黑胶，不要求每曲上传默认图〕 | PRD / P01 L726 |
| 验收ID | AC-080 | 整图居中圆形展示，播放旋转／暂停停止；非中央小图；默认图一致；歌单行仍仅名称和状态〔本STEP范围：主页/面板及共享唱片渲染规则〕 | PRD / P01 L727 |
| 验收ID | AC-081 | 先回退内置黑胶；极端情况下仍可辨认和操作播放器；音乐不被图片错误阻断或重启，无无限图请求 | PRD / P01 L728 |
| 验收ID | AC-082 | 始终匹配当前曲与有效封面版本，不串图、不覆盖新图，不误改变播放状态 | PRD / P01 L729 |
| 验收ID | AC-084 | 已启用无需先隐藏；未启用／隐藏不会自动启用；保存后按既有目录时机显示，不新增实时推送〔本STEP范围：H5按既有目录事件更新后显示封面，不新增推送/重启音乐〕 | PRD / P01 L731 |
| 验收ID | AC-085 | 只改封面／目录版本，音频 URL 与版本不变，不转码、不重建／重置进度／改音量或最后手选；音频准备可继续按规则使用〔本STEP范围：前台只更新图，不重建音频/进度/音量/手选〕 | PRD / P01 L732 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-012 | 匿名目录客户端、跨文档可复用完整缓存、在途合并、目录更新对账及统一失败预算。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/index.html` | `existing` | `REPO_BASELINE` | H01 / L9–87 HomeStartup；L1468–1498/L1577–1585 more；L2092–2105 VoiceEntry.begin | 对应需求、复用点或需保留的基线 |
| `tests/test_h5_static_contract.py` | `existing` | `REPO_BASELINE` | H14 / L484–510 test_index_guest_mode_contract 旧 more 断言 | 对应需求、复用点或需保留的基线 |
| `tests/test_home_preferences.cjs` | `existing` | `REPO_BASELINE` | H15 / L88–93 旧更多互动断言 | 对应需求、复用点或需保留的基线 |
| `tests/test_home_scene_boundaries.cjs` | `existing` | `REPO_BASELINE` | H16 / L10 旧 more 访客门禁断言 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/index.html` | `existing` | `REPO_BASELINE` | D02 / L64–77 唱片/面板/两项气泡；L90–92 演示入口 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.css` | `existing` | `REPO_BASELINE` | D07 / L7–19 第五格/面板/气泡/响应式/减少动态效果 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/record.css` | `existing` | `REPO_BASELINE` | D08 / L32–99 通用黑胶；L171–200 长名/减少动态效果 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/music-glass.css` | `existing` | `REPO_BASELINE` | D09 / L10–22 磨砂；L75–205 控件/滤镜降级 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/v13.css` | `existing` | `REPO_BASELINE` | D10 / L1–23 整图居中裁圆 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/preview-music-v13.png` | `existing` | `REPO_BASELINE` | D14 / 已查看现有音乐面板截图；仅静态视觉证据 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 主页BGM UI、共用唱片/封面资源和必要CSS/可访问性测试，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：主页第五格、Bottom Sheet、加载层暂停控件和各前台位置共用的唱片/封面渲染组件；正式音量/手选与设置、账号往返的本地偏好接线及实际播放反馈。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 替换第五格more，前四格与关系入口保持位置及原门禁；主页无额外气泡。 | PRD / F-001、F-009、BR-001、BR-002、BR-003、BR-047、BR-049 |
| 本STEP规则2 | 入口打开/收起仅改界面，收起不断音，打开不解除关闭；单个可交互唱片连续过渡并保持旋转相位。 | PRD / F-001、F-009、BR-001、BR-002、BR-003、BR-047、BR-049 |
| 本STEP规则3 | 播放缩放在1.15～1.2；封面整图居中裁圆，播放转暂停停；无图/坏图用同一内置通用黑胶。 | PRD / F-001、F-009、BR-001、BR-002、BR-003、BR-047、BR-049 |
| 本STEP规则4 | 面板只有曲名/状态歌单、播放暂停、下一首、弱化音量与本次关闭；无作者/歌词/时长/进度拖动/歌单行封面。 | PRD / F-001、F-009、BR-001、BR-002、BR-003、BR-047、BR-049 |
| 本STEP规则5 | 五项偏好经正式控件修改后仍仅本地；账号操作不重置实际音量/曲目。自动播放/渐变开关不改当前播放/暂停/关闭，motion不改变声音或渐变；新访问规则可复用STEP-013有效证据。 | PRD / F-003、BR-008、BR-010、BR-011、BR-015、BR-042 |

**开发任务**：

1. 参考demo样式与同一唱片移动交互迁入现有主页布局，不移植原型外壳/侧边演示区/默认自动开面板。第五格从handleHomeQuickAction统一私有门禁中独立公开，其他入口保持规则。
2. 所有按钮只调用共享控制器；控制状态来自实际媒体与输出链，加载/暂停/被拦/关闭静止；静音运行仍是播放且明确静音。
3. 实现面板收起/遮罩/返回/Escape、焦点回入口、列表/滑杆/下拉手势区分，小屏横屏内部滚动，连续开合以最后操作收敛，无双唱片/残留遮罩/穿透。
4. 提供长名慢滚和完整名阅读，短名不滚；隐藏/暂停/减少动态效果停止相应持续动画，静态提示不改变音乐渐变设置。
5. 提供一份内置通用黑胶；图片按曲目和有效封面版本核对异步结果，失败只回退图，不重建音频/改进度，极端默认图异常仍可识别和操作。
6. 定点替换旧more/敬请期待相关测试断言为公开BGM行为，保留前四格门禁/motion有效断言；demo参数只作建议参考。
7. 负责AC-079/084的前台子条款：无图显示同一内置默认黑胶；后端已保存封面在既有目录事件取得新版本后更新，不轮询推送/重建播放器。
8. 将STEP-009五项偏好接入正式UI/播放器：音量拖动即时应用、结束合并写入；列表手选/手动下一首才更新最后手选；两个BGM开关与原motion遵循各自权限/作用范围。逐项修改五项后执行登录A→退出→登录B→同浏览器再访问，核对值、实际音量与曲目以及网络不上传偏好；不将demo账号模拟或模块读写等同此闭环。
9. 逐一验证真实播放中关自动播放仍继续；真实暂停/关闭时开启渐变或自动播放均不出声，后续无旧会话新访问按设置初始化。核对改motion不打断声音、不改变渐变开关，原持久化键/权限及倾斜独立性保持。STEP-013新访问/会话证据可在前提未变时复用，014仍对三条AC的正式接线负责。

**不在本STEP范围内**：

- 本 STEP 的AC-080只承担主页/面板和公共渲染组件，内容/设置气泡实例在STEP-015；AC-085承担前台换图不重播部分。
- 不加第六格、不增加复杂唱机/搜索/收藏/上一首/拖动进度；不直接复制demo模拟目录。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 访客打开主页播放，逐一选曲/下一首/暂停/收起，检查原私有入口 | 第五格/关系位置正确，公共播放无登录，核心控制按原AC语义 | AC-001、AC-002、AC-006、AC-007、AC-008 |
| 异常 | 空目录/失败/缓冲/被拦及零音量、封面和默认图均异常 | 状态真实、空态/人工重试可辨；图错不影响音乐/控制 | AC-003、AC-009、AC-081 |
| 边界 | 连续开合、关闭后只开面板、小屏横屏键盘/减少动态效果 | 不复播/不双份，可触达/焦点正确/无强制动画 | AC-004、AC-005 |
| 边界 | A图晚于B、同曲旧封面晚到，播放中只换图 | 始终当前有效封面，整图圆形/默认一致，不改音频/进度 | AC-080、AC-082、AC-085 |
| 正常 | 无图启用后播放，已启用换图并等既有目录读取事件 | 无图显示唯一通用黑胶；新目录后显示新图，音乐不重启 | AC-079、AC-084 |
| 正常 | H5-M/H5-D正式主页音量拖动/列表手选或手动下一首、设置页两个BGM开关及原motion逐项修改五项；登录A→退出→登录B→同浏览器再访问；检查API网络 | 五项值共用本机存储且保留，账号操作不重置实际音量/曲目；无账号分区、偏好API/服务端落库/偏好事件上报；保留实际声音/曲目与存储/网络证据 | AC-015 |
| 边界 | H5-M真实播放时关自动播放；真实暂停及本次关闭时，分别开启渐变和自动播放；随后无旧会话新访问，SIM仅补边界注入 | 当前播放继续，暂停/关闭均不误出声且不解除关闭；新访问采用设置。可复用STEP-013有效新访问证据，正式控件/播放反馈须在本STEP验证 | AC-017 |
| 正常 | H5-M真实BGM播放中在原权限范围改motion；静态核对原键/权限/倾斜能力 | 原人物与场景动效语义及本地值保持，倾斜授权仍独立；BGM不被停止，音乐渐变开关和值均不变 | AC-019 |

**完成标志**：

- [ ] AC-015/017/019的五项正式操作/账号往返、真实播放/暂停/关闭切开关与无旧会话新访问、motion与声音/渐变独立三组子条款，均按各自PRD指定环境逐项留证；SIM/demo不代替真实环境。结合STEP-009子条款完整后才可标整条AC完成，复用STEP-013须核对证据前提且不形成009反向依赖。
- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-015] 接入六类页面右侧悬浮唱片

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：朋友圈、日记、记忆、关系、文字聊天和设置使用同款可拖动气泡且不遮挡页面主操作。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-002 | 其他内容页及设置页的悬浮唱片 | PRD / P01 L53 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | BR-001 | 公共音乐对访客开放；原页面权限照常执行 | PRD / P01 L488 |
| 需求ID | BR-005 | 同款气泡提供播放／暂停、本次关闭；临时失败保留恢复入口 | PRD / P01 L492 |
| 需求ID | BR-006 | 右侧吸附，位置归一化及安全区约束；覆盖层按最新状态恢复控件 | PRD / P01 L493 |
| 需求ID | BR-047 | 整图居中圆形显示，播放旋转、暂停停止；首页／面板／气泡统一当前封面，异常回退内置通用黑胶 | PRD / P01 L534 |
| 验收ID | AC-001 | 公共音乐不要求登录；原私有数据及页面门禁有效〔本STEP范围：六类内容/设置页公共音乐与原页面/私有数据门禁〕 | PRD / P01 L648 |
| 验收ID | AC-010 | 在页面允许条件下复用同款气泡；设置页无静态暂停替代；后台无用户 BGM | PRD / P01 L657 |
| 验收ID | AC-011 | 收起操作区不停止；暂停保留；关闭立即无声且气泡消失，设置不能绕过重开 | PRD / P01 L658 |
| 验收ID | AC-012 | 右侧吸附、相对位置恢复且在安全区；拖动不误播，不遮输入／发送 | PRD / P01 L659 |
| 验收ID | AC-013 | 控件让位，返回按最新状态；无点击残留或旧气泡复活 | PRD / P01 L660 |
| 验收ID | AC-080 | 整图居中圆形展示，播放旋转／暂停停止；非中央小图；默认图一致；歌单行仍仅名称和状态〔本STEP范围：内容页/设置页共享唱片实例与状态〕 | PRD / P01 L727 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-014 | 主页第五格、Bottom Sheet、加载层暂停控件和各前台位置共用的唱片/封面渲染组件。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/settings.html` | `existing` | `REPO_BASELINE` | H02 / L531–652 私有区；L654–688/707–749 设置；L1027–1055 退出 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/api.js` | `existing` | `REPO_BASELINE` | H03 / L95–126 request默认Token；L171–185 clearToken；L294–426登录弹窗 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/feed.html` | `existing` | `REPO_BASELINE` | H08 / L443–471/555 图片预览；L1416–1479/1751 评论与页面接入 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/diary.html` | `existing` | `REPO_BASELINE` | H09 / L55–62/273/314–339 返回安全区及requireProtectedPage | 对应需求、复用点或需保留的基线 |
| `frontend/pages/memory.html` | `existing` | `REPO_BASELINE` | H10 / L263–264/559–606 nebula底栏/抽屉；鉴权在H18 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/relationship.html` | `existing` | `REPO_BASELINE` | H11 / L58–65/708–720/923–948/1342–1375 门禁/返回/levelup覆盖层 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/chat.html` | `existing` | `REPO_BASELINE` | H12 / L466–479/687–690/1647–1657/1861–1869 输入区/visualViewport/门禁 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/index.html` | `existing` | `REPO_BASELINE` | D02 / L64–77 唱片/面板/两项气泡；L90–92 演示入口 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.css` | `existing` | `REPO_BASELINE` | D07 / L7–19 第五格/面板/气泡/响应式/减少动态效果 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/v13.css` | `existing` | `REPO_BASELINE` | D10 / L1–23 整图居中裁圆 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/memory-nebula.js` | `existing` | `REPO_BASELINE` | H18 / L53–54 requireProtectedPage；L800–815 抽屉；L1073 pagehide | 对应需求、复用点或需保留的基线 |
| `frontend/static/css/h5-theme.css` | `existing` | `REPO_BASELINE` | H19 / L531–585 登录遮罩层级与安全区 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 共享气泡与六页安全区/覆盖层接线及专项验证，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：共享气泡组件、各页明确安全区/覆盖层适配及会话相对位置恢复。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 展开只有播放/暂停与关闭本次；点空白仅收起；无选曲/下一首/音量。 | PRD / F-002、F-009、BR-001、BR-005、BR-006、BR-047 |
| 本STEP规则2 | 只右侧上下拖动、松手吸附，按可用高度比例保存于本标签会话；拖动不误点。 | PRD / F-002、F-009、BR-001、BR-005、BR-006、BR-047 |
| 本STEP规则3 | 暂停/被拦/临时失败保留可恢复入口；确为空目录或本次关闭不留无用点击区域；气泡不能重开关闭。 | PRD / F-002、F-009、BR-001、BR-005、BR-006、BR-047 |

**开发任务**：

1. 六页使用同一组件和STEP-014唱片/封面渲染，不在主页/Admin/独立登录页重复挂载；受保护页先按原合法访问状态决定初始化。
2. 逐页登记安全区：feed图片预览/评论层；diary返回与inset；memory抽屉/底栏/recenter；relationship返回与levelup层；chat可见视口/键盘/输入发送；settings原内容/退出区。
3. 基于预定义区域、visualViewport和resize/旋转重算比例位置并夹入安全区，不自由横向拖拽、不自动识别任意内容。
4. 覆盖层暂时隐藏仅改变控件，结束按最新状态显示；关闭后移除元素/命中区，旧overlay回调不能复活。

**不在本STEP范围内**：

- 不将设置页改为静态暂停控件；不改变私有数据门禁或页面主交互，不在气泡中重开本次关闭。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 合法访问六页，在播放/暂停/被拦/临时失败下展开收起 | 同款气泡/封面，两个操作且可人工恢复，后台无用户BGM | AC-001、AC-010、AC-080 |
| 异常 | 关闭后去设置/关图片或登录覆盖层，强制触发旧回调 | 立即无声且无点击残留，关闭不能被设置/覆盖层绕过 | AC-011、AC-013 |
| 边界 | 竖拖后跳页/旋转，聊天弹键盘，打开抽屉/全屏/底栏 | 相对位置恢复夹入安全区，拖动不误播且不遮输入发送 | AC-012、AC-013 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-016] 在真实通话准备和清理边界互斥 BGM

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：全部既有浏览器能力检查通过、实际进入获准准备时关闭BGM，早于首次音频上下文恢复/麦克风申请/通话输出；准备后的取消、拒绝、失败、重连和结束均不自动复播。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | BR-014 | 立即停止并记会话关闭；仅主页明确播放／列表选曲重开 | PRD / P01 L501 |
| 需求ID | BR-017 | 最新有效操作胜出，旧任务及动画回调失效 | PRD / P01 L504 |
| 需求ID | BR-023 | 麦克风与通话输出前停止 BGM、关闭本次并阻断；结束只清阻断 | PRD / P01 L510 |
| 验收ID | AC-037 | 首个麦克风／通话输出前 BGM 已停且会话已关闭；不是等连接成功才停 | PRD / P01 L684 |
| 验收ID | AC-038 | 沿用已有检查和提示，未实际进入通话不关闭 BGM；微信 BGM 正常独立验收 | PRD / P01 L685 |
| 验收ID | AC-039 | 均不自动恢复 BGM；通话结束清理后仅解除阻断；通话期间主页也不可重开 | PRD / P01 L686 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-014 | 主页第五格、Bottom Sheet、加载层暂停控件和各前台位置共用的唱片/封面渲染组件。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-015 | 共享气泡组件、各页明确安全区/覆盖层适配及会话相对位置恢复。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/realtime-voice/api.md` | `existing` | `CONTRACT` | C04 / L13–25 强鉴权；L39–47 结束；L62–66 终态/占用查询 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/index.html` | `existing` | `REPO_BASELINE` | H01 / L9–87 HomeStartup；L1468–1498/L1577–1585 more；L2092–2105 VoiceEntry.begin | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-entry.js` | `existing` | `REPO_BASELINE` | H06 / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-playback.js` | `existing` | `REPO_BASELINE` | H07 / VoicePlayback：通话输出所有权 | 对应需求、复用点或需保留的基线 |
| `docs/tech-debt/active/realtime-voice.md` | `existing` | `CONTRACT`（REFERENCE_ONLY） | T02 / L11 TD-038；L56/72 TD-041/042 | 仅只读背景参考，不作本期需求、验收或技术债承接来源 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-audio-transport.js` | `existing` | `REPO_BASELINE` | H17 / L9–24、L53–74 通话媒体所有权与close | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step036_permission.cjs` | `existing` | `REPO_BASELINE` | V09 / 权限流程回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_terminal_result.cjs` | `existing` | `REPO_BASELINE` | V10 / 终态结果回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_replay_lifecycle.cjs` | `existing` | `REPO_BASELINE` | V11 / 重放生命周期回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step038_duplicate_actions.cjs` | `existing` | `REPO_BASELINE` | V12 / 重复操作回归；未运行 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| VoiceEntry最小准备/清理hook与BGM互斥适配，具体内部接口按已核实约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 登录/忙碌/全部既有浏览器能力拒绝（含prepareCall中的context.audioWorklet缺失）不算实际进入准备；全部能力检查通过并进入实际准备才关闭本次。 | PRD / F-005、BR-014、BR-017、BR-023 |
| 本STEP规则2 | 进入准备先立即停BGM、记录关闭并持有通话阻断；只有本次真实清理完成释放阻断，关闭标记继续保留。 | PRD / F-005、BR-014、BR-017、BR-023 |
| 本STEP规则3 | listening/单轮回复结束不是挂断；BGM对象与通话对象所有权分离。 | PRD / F-005、BR-014、BR-017、BR-023 |

**开发任务**：

1. 以全部既有浏览器能力拒绝检查通过为实际准备边界，包含begin静态检查及prepareCall的context.audioWorklet/VoiceAudioTransport/AudioWorkletNode动态检查；这些拒绝均不得改变BGM意图、关闭标记或阻断。必要的无声能力预检/检查顺序由研发验证，以便实际用途说明、权限拒绝/取消属于获准准备后的关闭阶段；不将接点硬定在静态行号或要求早于AudioContext构造，也不擅自把构造异常重分类为能力拒绝。获准进入准备即停BGM、记录关闭并持有通话阻断，必须早于首次context.resume、getUserMedia与通话输出；不要放在begin第一行或等voice:connected才停。
2. 新增最小生命周期接点，按准备代次/通话归属配对持有与幂等释放，覆盖用途说明取消、权限拒绝、创建/连接失败、重连与挂断；旧回调不能释放新通话占用。
3. 当前只暴露begin、close远端end未等待，需核实并接入既有可信终态/清理确认路径；不能用面板隐藏、busy=false或releaseMic调用完成代替清理完成。未知清理保持保守阻断/关闭并沿用原错误处理。
4. 通话阻断期间主页也不可播放；结束后只允许之后主页明确播放/选曲重开，既有微信语音限制不变，占位视频入口不触发关闭。
5. 同步实际新增的语音前端生命周期契约；不改变配额/结算/远端结束语义。本STEP在已有真实通话验收环境完成AC-037～039时序/输出证据后才能DONE，不等待后续STEP-020提供前置环境；缺环境则保留BLOCKED。STEP-019再接准备取消，STEP-020/021做完整链路复核。

**不在本STEP范围内**：

- 不新建通话功能、不放宽微信语音、不改既有结束结算/配置发布预检/强制测试能力链（台账仅为背景，非本期承接项）、不靠无依据终态/清账解除原占用。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 目标分支通过全部既有能力检查（含context.audioWorklet），实际进入获准用途说明/麦克风准备 | 进入准备时BGM已停、会话关闭且持有阻断；早于首次context.resume/getUserMedia/通话输出，行为时序可记录，不以constructor前或某行号作为判定 | AC-037 |
| 异常 | 未登录/忙碌/微信限制/占位视频入口；逐一缺失安全上下文、getUserMedia、WebSocket、randomUUID、AudioContext、VoiceAudioTransport、AudioWorkletNode，以及静态检查通过但context.audioWorklet缺失 | 沿用各既有拒绝；全部实际能力拒绝均不改BGM意图/关闭标记且不新增通话阻断；audioWorklet缺失显式断言不关闭，不混同麦克风权限拒绝 | AC-038 |
| 边界 | 已通过全部能力检查并进入获准准备后，用途说明取消、麦克风权限已拒绝/申请被拒、创建或连接失败、重连、单轮结束、挂断及迟到旧清理 | 持续关闭；取消/拒麦/失败均不恢复；真实清理仅释放本归属阻断，通话中主页不能重开，旧回调不得影响新归属 | AC-039 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-017] 提供短 TTS 活动衰减与可控模拟

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：带活动ID的短音频接口可临时衰减BGM，重叠/取消/超时后只在最新意图允许时恢复。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | BR-016 | 增益真实有效；零值可靠静音；设备音量降级保留明确取消静音入口，用户操作后才将零值改为默认非零值 | PRD / P01 L503 |
| 需求ID | BR-024 | 临时衰减，按活动 ID 去重释放；最后一路结束才条件恢复 | PRD / P01 L511 |
| 验收ID | AC-041 | 临时乘衰减比例，结束按新音量恢复；降级临时暂停，不写持久音量 | PRD / P01 L688 |
| 验收ID | AC-042 | 最后活动释放才条件恢复，计数不负、不永远衰减，迟到结束不复播 | PRD / P01 L689 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-016 | VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-entry.js` | `existing` | `REPO_BASELINE` | H06 / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-playback.js` | `existing` | `REPO_BASELINE` | H07 / VoicePlayback：通话输出所有权 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 短音频活动控制接口与模拟/能力验证用例，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：短TTS开始/结束/取消/销毁接口及活动集合模拟验收，不新增独立TTS业务链。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 临时目标增益=用户当前音量×采用的衰减比例，不修改长期音量。 | PRD / F-004、F-005、BR-016、BR-024 |
| 本STEP规则2 | 同ID重复结束幂等，最后活动释放才解除衰减；取消/超时/销毁释放；不能让旧结束复播。 | PRD / F-004、F-005、BR-016、BR-024 |
| 本STEP规则3 | 无可靠衰减能力则临时暂停，不改变用户暂停/本次关闭。 | PRD / F-004、F-005、BR-016、BR-024 |

**开发任务**：

1. 用活动ID集合/等价机制管理重叠与失效，接口名按项目约定确定；比例/超时策略按采用记录验证，不把25%固定为产品阈值。
2. 衰减期间用户改音量，最终按新音量及当前渐变能力条件恢复；暂停/关闭/通话优先，重复回调无额外播放。
3. 以可控模拟和实际输出能力验证增益/暂停路径；独立短TTS产品链在当前范围未发现，报告明确模拟边界。

**不在本STEP范围内**：

- 不接入新的TTS提供商、账号音频设置或服务端用户行为采集。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 开始短TTS、用户主动调音量、结束 | TTS衰减/恢复不改写长期音量；用户调音量仍按STEP-009/014保存新值，结束按新值恢复 | AC-041 |
| 异常 | 无衰减能力、销毁/超时/取消、关闭后旧结束 | 临时暂停/释放活动，迟到回调不复播 | AC-041、AC-042 |
| 边界 | 两路重叠、重复结束和新旧ID交错 | 最后活动释放才条件恢复，不负计数/不永久衰减 | AC-042 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-018] 接入普通带声媒体和录音临时互斥

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：显式接入的普通带声媒体/录音可临时暂停BGM，释放时保守核对意图与真实许可。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | BR-025 | 显式媒体互斥临时暂停；系统异常保守等待真实许可 | PRD / P01 L512 |
| 验收ID | AC-043 | 普通互斥临时暂停，无声不影响；无法确认恢复许可时等明确操作 | PRD / P01 L690 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-015 | 共享气泡组件、各页明确安全区/覆盖层适配及会话相对位置恢复。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-016 | VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-playback.js` | `existing` | `REPO_BASELINE` | H07 / VoicePlayback：通话输出所有权 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/feed.html` | `existing` | `REPO_BASELINE` | H08 / L443–471/555 图片预览；L1416–1479/1751 评论与页面接入 | 对应需求、复用点或需保留的基线 |
| `frontend/pages/chat.html` | `existing` | `REPO_BASELINE` | H12 / L466–479/687–690/1647–1657/1861–1869 输入区/visualViewport/门禁 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 普通媒体/录音互斥适配及实际接入清单，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：普通媒体阻断适配与无声装饰/系统中断的明确边界。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 带声媒体或录音显式持有临时暂停；结束只解除对应阻断；无声装饰视频不影响BGM。 | PRD / F-005、BR-025 |
| 本STEP规则2 | 系统中断依据可见性/实际媒体状态处理，无法确认许可则等待明确播放。 | PRD / F-005、BR-025 |

**开发任务**：

1. 定向盘点实际启用的普通媒体/录音入口；若仅有真实通话，则不重复包装成普通媒体，提供受控适配模拟并记录当前接入清单。
2. 接入开始/结束/取消/销毁的归属化阻断，重叠媒体不互相误释放，恢复仍重检用户暂停/关闭/通话/人工恢复状态。
3. 系统电话/其他应用中断按现有可见性/实际输出保守处理，不宣称控制全站声音或系统音频焦点。

**不在本STEP范围内**：

- 不新建录音/媒体功能、不自动发现任意全站声音、不承诺后台/锁屏持续播放。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 显式带声媒体/录音开始结束 | 临时暂停，结束仅解除对应阻断并条件恢复 | AC-043 |
| 异常 | 系统中断或结束时无法确认许可、用户已关闭 | 保留手动入口，无非授权恢复 | AC-043 |
| 边界 | 无声装饰、多个临时阻断交错 | 无声不影响BGM，不能释放他人阻断 | AC-043 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-019] 实现至多一个无声下一首准备

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：当前实际播放且条件允许时轻量准备一个有效下一首，任何过时准备都不能发声或改变用户状态。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | F-006 | 公开歌单、事件触发更新与目录缓存 | PRD / P01 L57 |
| 需求ID | F-010 | 当前曲按需缓冲、下一首轻量准备、浏览器 HTTP 缓存 | PRD / P01 L61 |
| 需求ID | BR-051 | 当前曲按需缓冲；当前确在播放时至多轻量准备一个有效下一首候选，不抢占当前播放 | PRD / P01 L538 |
| 需求ID | BR-052 | 预加载不发声、不改用户设置／意图；实际播放前重检资格、目录与阻断 | PRD / P01 L539 |
| 需求ID | BR-053 | 停止新准备、尽力取消并忽略旧结果；不支持／不合适可跳过，失败不影响当前曲，实际切歌走普通流程 | PRD / P01 L540 |
| 需求ID | BR-054 | 使用浏览器 HTTP 缓存并核对真实表现；未命中时正常请求；缓存头与期限按验证后的配置 | PRD / P01 L541 |
| 需求ID | BR-055 | 当前资源与准备候选按版本和目录资格分别核对；只换封面不使音频缓存无故失效 | PRD / P01 L542 |
| 验收ID | AC-049 | 只允许当前曲按需请求和最多一个有效下一首准备，不全歌单预取，不以整首解码为启动门槛；曲终仍检查目录 | PRD / P01 L696 |
| 验收ID | AC-077 | 审计可区分音频、封面与清理结果，不泄露敏感载荷；新增诊断仅本地，五项偏好不服务端保存〔本STEP范围：新增准备/图片等H5诊断只在本地，网络不上传用户偏好〕 | PRD / P01 L724 |
| 验收ID | AC-085 | 只改封面／目录版本，音频 URL 与版本不变，不转码、不重建／重置进度／改音量或最后手选；音频准备可继续按规则使用〔本STEP范围：封面更新不使有效音频准备/检查点失效〕 | PRD / P01 L732 |
| 验收ID | AC-092 | 至多一个下一首候选，当前播放／主页面优先；不全歌单下载，准备触发时间按实际配置而非强制 20 秒 | PRD / P01 L739 |
| 验收ID | AC-093 | 准备不发声／不调用候选播放绕许可、不写最后手选／意图；实际切歌仍校验并按渐变开关执行 | PRD / P01 L740 |
| 验收ID | AC-094 | 不再发新非必要准备，尽力取消／释放；旧回调无声，关闭／通话优先；不要求已经发出的请求瞬间零字节 | PRD / P01 L741 |
| 验收ID | AC-095 | 可跳过准备，当前曲不报错；正常切歌仍可按需加载，不批量试遍歌单；不假定所有环境有同一网络识别 API | PRD / P01 L742 |
| 验收ID | AC-096 | 实際选播遵循新目录／意图与音频版本；已缓存文件不能绕过资格；过时准备不抢回当前曲目 | PRD / P01 L743 |
| 验收ID | AC-099 | 五项仍仅本地设置；无音频 Base64／二进制写入偏好，无自建完整音频库／离线下载／缓存账号同步，未命中正常加载 | PRD / P01 L746 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-012 | 匿名目录客户端、跨文档可复用完整缓存、在途合并、目录更新对账及统一失败预算。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-014 | 主页第五格、Bottom Sheet、加载层暂停控件和各前台位置共用的唱片/封面渲染组件。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-015 | 共享气泡组件、各页明确安全区/覆盖层适配及会话相对位置恢复。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-016 | VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-017 | 短TTS开始/结束/取消/销毁接口及活动集合模拟验收，不新增独立TTS业务链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-018 | 普通媒体阻断适配与无声装饰/系统中断的明确边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/README.md` | `existing` | `REPO_BASELINE` | D01 / L1–41 V1.3 范围、参数、模拟边界 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/demo.js` | `existing` | `REPO_BASELINE` | D03 / L59–139 封面/准备/目录；L193–220 选曲；L273–362 UI；L413–446 交互 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/shared-catalog.js` | `existing` | `REPO_BASELINE` | D06 / L4–10 参数；L82–126 本地目录；L131–243 图像预览 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/verification.json` | `existing` | `REPO_BASELINE` | D12 / L123–180 V1.3 增量与未验证范围 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-entry.js` | `existing` | `REPO_BASELINE` | H06 / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM单候选轻量准备模块、取消适配和本地诊断用例，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：受目录/音频版本/用户意图约束的单候选准备器与取消/跳过/失效逻辑。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 当前曲按需边加载边播，接近曲终至多一个下一首候选；不全歌单、不等整首解码。 | PRD / F-004、F-005、F-006、F-010、BR-051、BR-052、BR-053、BR-054、BR-055 |
| 本STEP规则2 | 准备不调用候选play绕许可、不改当前曲/最后手选/检查点/意图/关闭/UI播放态。 | PRD / F-004、F-005、F-006、F-010、BR-051、BR-052、BR-053、BR-054、BR-055 |
| 本STEP规则3 | 暂停/关闭/通话/隐藏/离开停止新非必要准备、尽力取消旧任务，迟到结果无副作用。 | PRD / F-004、F-005、F-006、F-010、BR-051、BR-052、BR-053、BR-054、BR-055 |

**开发任务**：

1. 参考 demo 单候选/metadata机制但按目标浏览器验证等价方案；触发阈值/弱网判断属于采用记录，不能固定照搬8秒或20秒。
2. 仅当前真播放、可见、未关闭且无通话/媒体阻断、有有效候选才准备；单曲/未知时长/弱网省流量/不支持可跳过，不假设存在同一网络API。
3. 实际切歌重新走目录缓存/资格/预算与最新意图检查；重排/隐藏/改选/新音频版本使旧准备失效，只换封面不使音频准备/检查点无故失效。
4. 候选失败只影响准备，不记当前坏链/不触发当前故障预算，不批量换候选；明确选播/当前曲和页面资源优先。
5. 不自建媒体本地库/SW/Cache API/IndexedDB，不把音频二进制/Base64放偏好存储；只利用普通媒体与HTTP缓存，实际缓存证据在STEP-020。
6. 核对已形成的H5新增诊断和网络：准备/图片回退事件默认仅本地，新增载荷不含五项偏好/账号标识/文件正文，不建服务端采集。

**不在本STEP范围内**：

- 不保证候选完整下载、固定预取字节/立即零流量/无缝；不宣称demo的metadata准备等同生产缓存命中。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 当前播放达到采用条件，长歌单中准备再实际切歌 | 最多一个候选，准备无声/不写偏好/不改状态，切歌仍重检 | AC-049、AC-092、AC-093 |
| 异常 | 弱网/省流量/不支持/准备失败 | 可跳过，当前不报错、不批量试遍歌单，实际切歌仍按需加载 | AC-095 |
| 边界 | 准备中暂停关闭隐藏跳页真实通话，旧回调晚到 | 停止新准备、尽力释放，无迟到复播，不要求在途瞬时零字节 | AC-094 |
| 边界 | 重排/隐藏候选/改选/新媒体/目录超龄；只换封面 | 服从目录资格和新意图；音频版本不变时图片单独更新 | AC-085、AC-096 |
| 边界 | 单曲/未知时长、检查存储与新增缓存能力并清缓存 | 可跳过，无完整媒体持久库/账号同步，未命中正常加载 | AC-095、AC-099 |
| 边界 | 触发准备/取消/图片回退等诊断并检查H5网络 | 仅本地诊断，无五项偏好和新增用户行为采集请求 | AC-077 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-020] 核验实际部署媒体与 HTTP 缓存链路

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：在实际验收环境证明已采用处理方案、OSS/CDN输出及浏览器缓存能支撑BGM而不影响原业务。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-008 | 音频校验、转码、复用 OSS 发布及手动清理资产 | PRD / P01 L59 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | F-010 | 当前曲按需缓冲、下一首轻量准备、浏览器 HTTP 缓存 | PRD / P01 L61 |
| 需求ID | BR-038 | 并发、接收、处理与资源占用有明确有限边界，不影响主业务；子步骤服从实际采用的总预算 | PRD / P01 L525 |
| 需求ID | BR-040 | 唯一版本路径，实际写入及远端读取验证后才就绪，音频与图像处理独立 | PRD / P01 L527 |
| 需求ID | BR-043 | 区分已确认规则与建议；研发／测试记录实际采用参数、方式、适用环境和证据，验收按已确认结果及实际配置执行 | PRD / P01 L530 |
| 需求ID | BR-044 | 复用现有朋友圈 Bucket；音频／封面分目录归属；优先复用并验证 CDN | PRD / P01 L531 |
| 需求ID | BR-045 | 服务端自动生成 Key 与访问 URL，保存可清理定位；新资源不覆盖旧地址；音频与封面各自版本化 | PRD / P01 L532 |
| 需求ID | BR-054 | 使用浏览器 HTTP 缓存并核对真实表现；未命中时正常请求；缓存头与期限按验证后的配置 | PRD / P01 L541 |
| 需求ID | BR-055 | 当前资源与准备候选按版本和目录资格分别核对；只换封面不使音频缓存无故失效 | PRD / P01 L542 |
| 验收ID | AC-070 | 总资源占用有界，忙碌／限流明确；不按进程无界放大，不影响公开读或当前播放；并发 1 仅为建议〔本STEP范围：真实多实例部署含封面操作的总资源边界〕 | PRD / P01 L717 |
| 验收ID | AC-074 | 预算不重置；超时终止回收旧子进程后再释放名额；仅清已确认无执行者的过期文件，不误删活动素材〔本STEP范围：实际慢接收/转码/OSS/进程退出与多实例恢复实证〕 | PRD / P01 L721 |
| 验收ID | AC-075 | 正确配置能播放／恢复；错误不可标就绪／正常播放；资源 URL 唯一且无 Token | PRD / P01 L722 |
| 验收ID | AC-076 | 实际资源／绝对时间边界有效，前后端与代理协调，失败可核对；不强制长请求或原稿 120／300／330 秒 | PRD / P01 L723 |
| 验收ID | AC-086 | 路径自动生成、音频封面分目录、CDN 地址来自真实配置；新图新 Key；不要求运营填 URL，不更改朋友圈目录／资源／权限〔本STEP范围：真实配置、对象/URL/权限及原业务的部署环境实证〕 | PRD / P01 L733 |
| 验收ID | AC-097 | 验证实际 HTTP 缓存与请求行为，未命中可重新请求；只换封面不使音频 URL 无故变化；不承诺每次零下载〔本STEP范围：HTTP缓存与音频/封面版本URL的完整真实网络核对〕 | PRD / P01 L744 |
| 验收ID | AC-098 | 不人为等待整首解码才播放；缺少片段可按需请求；记录真实缓冲／缓存能力，不把渐变降级当格式失败的替代 | PRD / P01 L745 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-005 | 管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-006 | 删除资格判断、不可发布删除态、逐对象清理、剩余失败手动重试及最小审计/幂等墓碑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-007 | 公开目录读取能力、启用且就绪过滤、唯一默认/独立封面元数据及管理变更缓存接线。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-016 | VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-019 | 受目录/音频版本/用户意图约束的单候选准备器与取消/跳过/失效逻辑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `backend/services/feed_image_service.py` | `existing` | `REPO_BASELINE` | B03 / FeedImageService；lxm/posts/{post_id}/{seq:02d}.webp；put_object | 对应需求、复用点或需保留的基线 |
| `backend/config.py` | `existing` | `REPO_BASELINE` | B04 / L224–242 OSS 配置名称；未读取真实凭证 | 对应需求、复用点或需保留的基线 |
| `backend/redis_client.py` | `existing` | `REPO_BASELINE` | B05 / L15–33 init_redis/get_redis：复用连接池，未有BGM缓存/超时/限流 | 对应需求、复用点或需保留的基线 |
| `backend/main.py` | `existing` | `REPO_BASELINE` | B07 / 路由注册；L268–273 admin_page 静态响应 | 对应需求、复用点或需保留的基线 |
| `Dockerfile` | `existing` | `REPO_BASELINE` | B10 / L10–15 apt 依赖，无 FFmpeg | 对应需求、复用点或需保留的基线 |
| `nginx/nginx.conf` | `existing` | `REPO_BASELINE` | B11 / 通用 API proxy_read_timeout 300s；无显式请求体大小/接收配置 | 对应需求、复用点或需保留的基线 |
| `frontend/static/js/voice-entry.js` | `existing` | `REPO_BASELINE` | H06 / L401–434 begin/能力/permissionRun/prepareCall；L54/128–160/303–398/473–491 清理与导出 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/README.md` | `existing` | `REPO_BASELINE` | D01 / L1–41 V1.3 范围、参数、模拟边界 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/verification.json` | `existing` | `REPO_BASELINE` | D12 / L123–180 V1.3 增量与未验证范围 | 对应需求、复用点或需保留的基线 |
| `docker-compose.yml` | `existing` | `REPO_BASELINE` | B18 / L44–68 backend环境与挂载；L7 迁移约定 | 对应需求、复用点或需保留的基线 |
| `requirements.txt` | `existing` | `REPO_BASELINE` | B19 / multipart/Alembic/Redis/Pillow/oss2/pytest声明 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step001_admin_config_migration.py` | `existing` | `REPO_BASELINE` | V05 / L25–31/L119–123 静态迁移与隔离库开关范式 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_nginx_runtime.py` | `existing` | `REPO_BASELINE` | V06 / L13/L65–80 opt-in隔离Nginx探针范式 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| 实际依赖/代理/缓存配置和环境证据记录，按已核实项目约定确定；真实值验证前标UNVERIFIED | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：部署依赖/代理/临时资源配置增量及H5-M/H5-D/API/DEP的媒体与缓存证据。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | 复用既有Bucket/优先既有CDN，音频/封面分归属且自动地址；不扩大Bucket整体公开权限。 | PRD / F-008、F-009、F-010、BR-038、BR-040、BR-043、BR-044、BR-045、BR-054、BR-055 |
| 本STEP规则2 | HTTPS、真实音频MIME、恢复所需Range和实际跨域音频图CORS均须验证。 | PRD / F-008、F-009、F-010、BR-038、BR-040、BR-043、BR-044、BR-045、BR-054、BR-055 |
| 本STEP规则3 | 采用HTTP缓存；版本内容变更换URL，改名/排序/只换封面不无故改变音频URL；缓存未命中允许重新请求。 | PRD / F-008、F-009、F-010、BR-038、BR-040、BR-043、BR-044、BR-045、BR-054、BR-055 |

**开发任务**：

1. 在授权的隔离/预发布环境核实真实Bucket/CDN配置和最小权限，仅记录脱敏定位；不得凭.env.example断言真实环境已配置。
2. 按已采用方案补转码依赖及代理/应用/前端大小与等待协调，验证multipart、合法音频加合法封面、慢接收/解析、内存/磁盘不足、跨实例并发与绝对总预算。
3. 验证处理挂起/崩溃后执行资源终止、临时文件清理/名额释放和状态可查；运行环境迁移只在后续相应授权环境进行，不默认运行生产迁移。
4. 实测OSS/CDN远端可读、MIME/Range/跨域输出，注入错误配置确认不能假就绪/假播放；原朋友圈图片与权限回归。
5. 核实音频/封面成功响应缓存头、实际CDN和Range复用行为；分别记录同URL复访/缓存清理/缺片段/新版本/只换图的网络证据，不把二次有请求判失败。
6. 用有限带宽确认当前曲不人为等待整首下载/解码，预加载不抢当前曲/主页；记录实际能力/降级及采用参数依据，不宣称未测容量。

**不在本STEP范围内**：

- 这是后续环境验证STEP，不是本轮已运行证据或部署授权；不新增Bucket/离线缓存系统或使用生产资产做破坏性故障注入。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 实际配置上传/播放/Range续播与同URL复访，有图无图均测 | 可发布/可输出/可恢复，音频封面分目录且地址自动生成，缓存行为有实证 | AC-075、AC-086、AC-097、AC-098 |
| 异常 | 错MIME/CORS、磁盘不足、慢上传/OSS挂起/处理依赖缺失 | 不得假就绪，边界有效、结果可核对，主业务保持可用 | AC-074、AC-075、AC-076 |
| 边界 | 跨实例超并发、合法音频+封面请求、缓存回收/片段不足/版本更新 | 占用有界/超时协调，正常按需再请求，图片变更不使音频URL失效 | AC-070、AC-076、AC-097、AC-098 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

### [STEP-021] 执行完整业务验收并交付证据

**阶段状态**：`verified`（文档）；实施进度：`NOT_STARTED`。

**目标**：依据100项验收逐项归档完整链路结果与实际参数记录，明确通过、失败、未测和发布阻断。

**来源映射**：

| 类型 | ID | 原文短引或准确摘要/责任范围 | 来源 |
| --- | --- | --- | --- |
| 需求ID | F-001 | 主页第五格唱片、Bottom Sheet、极简歌单及控制 | PRD / P01 L52 |
| 需求ID | F-002 | 其他内容页及设置页的悬浮唱片 | PRD / P01 L53 |
| 需求ID | F-003 | 本地偏好与现有设置页接入 | PRD / P01 L54 |
| 需求ID | F-004 | 播放控制、顺序循环、淡入淡出及兼容降级 | PRD / P01 L55 |
| 需求ID | F-005 | 页面生命周期、跨页恢复、真实通话互斥 | PRD / P01 L56 |
| 需求ID | F-006 | 公开歌单、事件触发更新与目录缓存 | PRD / P01 L57 |
| 需求ID | F-007 | 一个 BGM 管理页、角色权限、音频／封面维护与审计 | PRD / P01 L58 |
| 需求ID | F-008 | 音频校验、转码、复用 OSS 发布及手动清理资产 | PRD / P01 L59 |
| 需求ID | F-009 | 每曲可选静态封面、统一圆形展示、默认图及失败回退 | PRD / P01 L60 |
| 需求ID | F-010 | 当前曲按需缓冲、下一首轻量准备、浏览器 HTTP 缓存 | PRD / P01 L61 |
| 需求ID | BR-043 | 区分已确认规则与建议；研发／测试记录实际采用参数、方式、适用环境和证据，验收按已确认结果及实际配置执行 | PRD / P01 L530 |
| 验收ID | AC-078 | 完整业务闭环、参数与用例记录一致；执行已确认需求，建议实现经验证后采用；文档检查不冒充真机／容量通过 | PRD / P01 L725 |
| 验收ID | AC-100 | 建议值／方案均有“建议”性质；实际采用值由研发／测试验证记录，不能直接当强制阈值；96 kbps／4 MiB 等未被擅改，不伪报兼容或容量通过 | PRD / P01 L747 |

**前置依赖**：

| STEP | 所需产物 | 验证方式 |
| --- | --- | --- |
| STEP-002 | 一个 BGM 管理页外壳、受限列表/详情/操作只读查询及后续写接口共用的授权边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-003 | 后台上传/处理/查询/失败重选 UI 与服务端音频接收、校验、转码、OSS 发布、试听和受控恢复链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-004 | BGM 管理页歌单运营动作及对应事务、期望版本冲突与操作结果核对能力。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-005 | 管理页可选封面/圆形预览/已保存结果对照、真实图像处理和独立封面关联/版本/残留定位。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-006 | 删除资格判断、不可发布删除态、逐对象清理、剩余失败手动重试及最小审计/幂等墓碑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-007 | 公开目录读取能力、启用且就绪过滤、唯一默认/独立封面元数据及管理变更缓存接线。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-008 | 既有操作日志的 BGM 模块/动作筛选与全管理链路审计核对证据。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-009 | 偏好字段校验/降级模块，既有设置页的两个公开开关，以及原主页动效能力的兼容接入。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-010 | 可独立用有效目录样本验证的播放器控制核心、检查点和操作失效机制。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-011 | 独立于通话的音频输出/增益链、可取消渐变及经验证的降级控件状态。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-012 | 匿名目录客户端、跨文档可复用完整缓存、在途合并、目录更新对账及统一失败预算。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-013 | 页面模式接入、可靠会话读写检查、检查点/版本验证及可见性/登录页/bfcache恢复规则。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-014 | 主页第五格、Bottom Sheet、加载层暂停控件和各前台位置共用的唱片/封面渲染组件。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-015 | 共享气泡组件、各页明确安全区/覆盖层适配及会话相对位置恢复。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-016 | VoiceEntry实际准备/终态清理的归属化接点及BGM通话阻断，附真实时序验证要求。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-017 | 短TTS开始/结束/取消/销毁接口及活动集合模拟验收，不新增独立TTS业务链。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-018 | 普通媒体阻断适配与无声装饰/系统中断的明确边界。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-019 | 受目录/音频版本/用户意图约束的单候选准备器与取消/跳过/失效逻辑。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |
| STEP-020 | 部署依赖/代理/临时资源配置增量及H5-M/H5-D/API/DEP的媒体与缓存证据。 | 该STEP完成标志/对应AC证据已登记；版本/参数前提仍成立 |

**参考路径与符号**：

| 路径/符号 | 状态 | 来源 | source_id / locator | 用途 |
| --- | --- | --- | --- | --- |
| `docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md` | `existing` | `PRD` | P01 / L48–65 范围；L117–429 功能；L482–742 BR/AC；L784–807 确认 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/conventions.md` | `existing` | `CONTRACT` | C01 / L10–31 响应/字段/错误码；L112–118 匿名例外 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/_shared/auth-rbac.md` | `existing` | `CONTRACT` | C02 / L91–110 实时账号授权/observer写总闸/脱敏/GET无写副作用 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/h5-app/api.md` | `existing` | `CONTRACT` | C03 / L28–80 页面策略；L97–108 主页加载；L130–136 motion键与降级 | 对应需求、复用点或需保留的基线 |
| `docs/contract/current/realtime-voice/api.md` | `existing` | `CONTRACT` | C04 / L13–25 强鉴权；L39–47 结束；L62–66 终态/占用查询 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/README.md` | `existing` | `REPO_BASELINE` | D01 / L1–41 V1.3 范围、参数、模拟边界 | 对应需求、复用点或需保留的基线 |
| `demos/bgm-v1.2/verification.json` | `existing` | `REPO_BASELINE` | D12 / L123–180 V1.3 增量与未验证范围 | 对应需求、复用点或需保留的基线 |
| `docs/tech-debt/active/life-feed.md` | `existing` | `CONTRACT`（REFERENCE_ONLY） | T01 / L11 TD-032；L42 TD-035；L52 TD-036 | 仅只读背景参考，不作本期需求、验收或技术债承接来源 |
| `docs/tech-debt/active/realtime-voice.md` | `existing` | `CONTRACT`（REFERENCE_ONLY） | T02 / L11 TD-038；L56/72 TD-041/042 | 仅只读背景参考，不作本期需求、验收或技术债承接来源 |
| `tests/test_admin_auth.py` | `existing` | `REPO_BASELINE` | V01 / 现有Admin授权专项入口；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_step012_feed_image.py` | `existing` | `REPO_BASELINE` | V02 / 现有图片服务回归入口；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_step012_operation_log_redaction.py` | `existing` | `REPO_BASELINE` | V03 / 现有日志脱敏回归入口；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_step029_observer_frontend_common.py` | `existing` | `REPO_BASELINE` | V04 / observer前端共用权限回归入口；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step001_admin_config_migration.py` | `existing` | `REPO_BASELINE` | V05 / L25–31/L119–123 静态迁移与隔离库开关范式 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_nginx_runtime.py` | `existing` | `REPO_BASELINE` | V06 / L13/L65–80 opt-in隔离Nginx探针范式 | 对应需求、复用点或需保留的基线 |
| `tests/test_home_preference_failures.cjs` | `existing` | `REPO_BASELINE` | V07 / 浏览器存储失败回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_home_panels.cjs` | `existing` | `REPO_BASELINE` | V08 / 现有面板回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step036_permission.cjs` | `existing` | `REPO_BASELINE` | V09 / 权限流程回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_terminal_result.cjs` | `existing` | `REPO_BASELINE` | V10 / 终态结果回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_replay_lifecycle.cjs` | `existing` | `REPO_BASELINE` | V11 / 重放生命周期回归；未运行 | 对应需求、复用点或需保留的基线 |
| `tests/test_realtime_voice_step038_duplicate_actions.cjs` | `existing` | `REPO_BASELINE` | V12 / 重复操作回归；未运行 | 对应需求、复用点或需保留的基线 |

| 新增或待验证对象 | 状态 | 来源 | 定位 | 用途 |
| --- | --- | --- | --- | --- |
| BGM完整验收证据与实际契约同步记录，按已核实的项目约定确定 | `planned` | `PLANNED` | 不适用；名称由采用记录按已核实约定确定 | 本STEP拟新增产物 |

**输入**：上述前置产物、本STEP映射的PRD规则/验收、参考表中的当前代码/契约与demo。先核对使用来源摘要；变化只定向扩大读取。

**输出**：无图/有图完整业务闭环、100项验收的环境/证据索引、实际参数与契约同步检查、完成范围结论。

**业务定义**：

| 规则 | 定义 | 来源 |
| --- | --- | --- |
| 本STEP规则1 | H5-M必须实际iPhone Safari/Chrome/微信及Android Chrome/微信；H5-D为桌面Chrome/macOS Safari。 | PRD / F-001、F-002、F-003、F-004、F-005、F-006、F-007、F-008、F-009、F-010、BR-043 |
| 本STEP规则2 | SIM不替代真机输出/真实通话/API/DEP；没有容量数据不得声称支持在线人数。 | PRD / F-001、F-002、F-003、F-004、F-005、F-006、F-007、F-008、F-009、F-010、BR-043 |
| 本STEP规则3 | 非授权复播、泄露、越权写、默认不一致、失联资产及正常能力缺渐变阻断对应发布范围。 | PRD / F-001、F-002、F-003、F-004、F-005、F-006、F-007、F-008、F-009、F-010、BR-043 |

**开发任务**：

1. 核对所有前置STEP完成标志和证据有效性，对100项AC逐项登记环境/参数/结果/定位；有效历史证据可复用，但前提变化或覆盖不足的部分必须补验。
2. 用真实无图/有图音频上传→处理→试听→启用→五浏览器播放/准备→已启用换图→隐藏→等期手动删除走闭环，补权限/故障/跨页/真实通话关键分支。
3. 对照D-01～18、SUG-001～021及实际配置/测试，确认采用结果/环境/原因有据，不把建议值写成用户决定；复核96kbps/4MiB等规格未变。
4. 同步实际接口/数据/页面/语音hook/配置的必要当前契约、索引与manifest增量；本文档不预写未来实现为既有事实。
5. 保留失败/未测及限制，只有对应必测项全部通过才能按范围交付。更新本文件唯一进度区块，不以demo verification或静态文档自检替代功能验收。

**不在本STEP范围内**：

- 本 STEP 只把 AC-078/100 的跨功能闭环和参数总核对列为直接职责；其余AC实际断言仍归各负责STEP，不泛映射为新增实现范围。
- 不自动发布、修改生产数据或宣布容量达标；若需要新授权，先准备可审阅证据和具体动作。

**测试与验收**：

环境使用映射AC在P01指定的H5-M/H5-D/SIM/API/DEP；同条AC的其他子条款不由本STEP冒领。

| 场景 | 输入/前提 | 预期结果 | 对应验收ID |
| --- | --- | --- | --- |
| 正常 | 所有前置证据可复用，走有图/无图完整闭环 | AC映射与实际行为一致，参数/环境/契约可追踪 | AC-078、AC-100 |
| 异常 | 任一必测失败/未测、模拟替真机或建议硬化 | 明确阻断相应交付范围，不以局部通过宣布整体完成 | AC-078、AC-100 |
| 边界 | 某环境采用允许降级或容量尚未量测 | 注明实际环境/降级并证明基本播放/静音/暂停关闭/恢复；不外推容量 | AC-078、AC-100 |

**完成标志**：

- [ ] 本STEP负责的全部AC/子条款有对应环境证据；正常、异常和边界断言均满足，未测不计完成。
- [ ] 没有改变PRD确认规格、其他STEP范围或原有效门禁；建议采用值有环境/依据记录。
- [ ] 实际新增路径/符号/接口与必要契约已同步，planned/unverified按证据更新；未验证限制保留。
- [ ] 本文§9唯一进度区块已回填状态、证据、变更文件、来源变化与恢复位置。

**完成回传**：

> 返回本STEP ID、完成/阻断状态、对应AC/子条款的证据及环境、变更文件、采用参数、实际契约增量、来源变化和下一可执行STEP。不得自动启动下一STEP；前置未满足时返回受影响项并停止该STEP。

## 7. 风险、验证入口与实施发现门

### 7.1 本阶段非阻断风险

| 风险 | 已有证据与影响 | 后续退出条件 |
| --- | --- | --- |
| demo与生产差距 | D01/D03/D05/D06/D12仅本地与模拟，无法证明服务端鉴权、转码、OSS、跨HTML或故障恢复 | 按§2及对应STEP实现，最后真实环境闭环 |
| 未确认实现参数与运行环境 | SUG均建议；真实资源/设备尚UNVERIFIED | STEP-001建立采用记录，各STEP验证后填实际值，STEP-020/021取证；不阻断本次文档 |
| 语音缺可直接复用的BGM准备/清理hook | H06 begin静态检查后，prepareCall还会拒绝context.audioWorklet缺失；close远端end异步；H17媒体清理与C04终态边界须区分 | STEP-016在全部能力检查通过后、首次resume/采麦/输出前关闭BGM；能力拒绝不关闭，准备后取消/拒麦/失败保持关闭；清理仍按真实归属证据，不借界面/busy推断 |
| 旧主页及inventory断言漂移 | H14/H15/H16旧more；B12固定37页而本轮静态盘点45页；B13/B14路由184与183计数不一致 | 先记隔离基线，再定点维护新需求相关断言，不把既有失败算BGM回归、不删除有效权限测试 |
| 旧图回收需有归属和残留闭环 | 当前FeedImageService只有图片写入，无BGM删除/补偿服务 | STEP-005/006持久定位新旧图并分项恢复，STEP-020验证不碰朋友圈 |
| 运行容量和素材 | PRD RISK-007/011/012：授权素材、96kbps听感、预加载和缓存收益均待验证 | 运营准备可用素材；STEP-020/021记录真实能力；没有容量测量不宣称容量 |
| 文档入口尚未登记 | 本次指定PRD与新STEP在现有manifest中无条目，现有索引含用户改动 | 本轮从用户指定路径交付验证版及审计，保留索引/manifest；实际契约整合时再按现有入口约定登记，不据此冒充既有运行契约 |

PRD RISK-001～012均保留为后续发布门槛：001→STEP-011/020，002→013，003→016/019，004→003/020，005→003/005/006，006→006/007/012，007→020/021，008→001/021，009→003/005/006/020，010→005/006/014，011→019/020，012→012/019/020。这里只承接原风险，不声称已消除。

### 7.2 已核实测试入口（本轮未执行）

以下引用均existing，已在§3按source_id登记；仅供后续执行器按变更范围选择，不是要求无差别全跑。现有测试环境解释器/pytest安装及运行服务是否就绪仍须在执行时核实，业务/迁移/故障测试使用隔离环境。

| 目的 | existing入口与来源 | 执行发现门 |
| --- | --- | --- |
| Admin鉴权/图片/日志/observer回归 | V01～V04 | 项目pytest解释器可用后运行`PYTHONPATH=. python3 -m pytest -q tests/test_admin_auth.py tests/test_step012_feed_image.py tests/test_step012_operation_log_redaction.py tests/test_step029_observer_frontend_common.py`；测试是否受本地改动影响需先记录基线 |
| 页面/路由inventory | B12/B13/B14 | 先静态盘点/隔离基线，再按有效需求更新；不以固定计数自动归因；需跑时使用项目pytest解释器精确选择这三文件 |
| 主页静态门禁及新第五格 | H14/H15/H16、V07/V08 | H14用项目pytest精确选文件；cjs用已核实Node/Playwright运行时。当前系统PATH没有node，运行前解析实际Node与包路径，按各脚本需要设置HOME_PLAYWRIGHT_PATH |
| 真实语音准备/重复操作/终态 | V09～V12、H06/H07/H17 | V10使用Node的`--test`入口；V11为直接脚本；V09/V12按脚本配置VOICE_PLAYWRIGHT_PATH。实际BGM互斥新用例另属planned，不能以旧语音测试替代 |
| 迁移/Nginx隔离验证范式 | V05/V06/V14 | 只借鉴显式隔离库/opt-in容器probe；不得直接在当前运行环境执行迁移或故障注入 |
| 新BGM专项断言及真机/API/DEP | `planned` / `PLANNED`，文件/命令按已核实约定确定 | 各STEP按实际实现新增有意义的用例与证据，方法不能镜像实现；目标终端与资源链按PRD环境矩阵执行 |

本轮未执行上述命令、未安装依赖、未变更运行环境。测试入口存在不等于可运行或已通过。

## 8. 完整复审与文档签发

| 自检项 | 结果及证据 |
| --- | --- |
| 输入覆盖 | 10/10 F、55/55 BR、100/100 AC已逐项映射；30/30 E、18/18 D、21/21 SUG已追踪；12项CSTR保留排除/未编号约束 |
| STEP结构 | 21/21均有单一目标、需求/验收短引、显式依赖/验证方式、参考状态/来源、输入输出、业务定义、任务/不做、正常异常边界、完成标志/回传 |
| 依赖 | 所有前置ID存在，无自依赖/循环；编号不替代依赖，后端/本地设置分支显式列出 |
| 映射边界 | 重复AC在§5.2注明可独立子条款；不是把同一AC映射到所有相邻层。AC-078仅STEP-021，AC-100仅STEP-001设计记录+STEP-021最终总核对 |
| 来源事实 | existing逐文件source_id/locator/SHA256；新增能力planned；实际部署/设备unverified，不当作现有事实或RUNTIME |
| 建议与确认 | 不新增业务字段/状态/错误码数值/权限值/优先级；保留原F优先级；SUG采用结果全部未填；无自定义补造占位 |
| demo结合 | §2逐项落STEP并区分真实本地交互与模拟；正文注明原型代码/样式参考和生产缺口 |
| 验证声明 | 对完整当前候选及PRD/demo/当前代码完成九维复审；轮1全稿审查证据经轮2内容等价与来源新鲜度核对后覆盖当前全稿，未仅检查四项Diff。九维均PASS；无业务/真机/联调/容量通过声明，现有demo结果不当本轮RUNTIME |
| 输出边界 | 审核方维护唯一step-audit.md并签发steps-verified.md；steps-draft.md与两轮candidate只读保留。仅变更文档，未修改PRD/demo/台账/业务代码/运行环境，未开始开发或另建执行记录 |

**文档状态：`STEPS_VERIFIED`；完整复审结果：`PASS_WITH_RISKS`。** SDR-20261019-001～004均已复审通过；九维结果、逐项修复证据及来源绑定见`step-audit.md`。§7保留真实环境、浏览器、素材与既有测试基线等明确非阻断风险，各项后续停止门继续有效。全部STEP仍为NOT_STARTED；本次签发不授权自动开发，也不代表100项AC功能验收通过。

## 9. 林小梦 BGM V1.3 STEP进度

> **本版交付已完结（2026-10-21，验收有保留）**：用户在人工测试后明确要求版本完结并整理契约。当前结论与后续待办唯一见[§9.28](#bgm-v13-closure)；下文历次阻塞／恢复描述保留为过程事实，未验证项不改记通过。

> 路径：`docs/design/bgm_music/steps-verified.md`§9，实施唯一进度区块；原稿与候选§9随只读快照保留，不双写，不另建执行记录。2026-10-19 用户提供本 STEP 与 PRD 并调用 `execute-approved-work`，开始执行 STEP-001。§1～8 的“本轮不开发／NOT_STARTED”是签发时快照；当前实施事实以本区为准。
> PRD来源：P01，`docs/design/bgm_music/PRD-LXM-BGM-V1.3-20261019.md`（existing/PRD）。
> STEP来源：`steps-verified.md`，由`steps-candidate-r2.md`完整复审通过后签发；原`steps-draft.md`和两轮候选保留。当前文档状态：`STEPS_VERIFIED`；实施进度以§9.1与§9.2当前状态为准。

### 9.1 进度总览

| 完成数 | 总数 | 当前状态 |
| --- | --- | --- |
| 7 | 21 | STEP-001～006/008 VERIFIED；STEP-007 IMPLEMENTED（预发布待验）；STEP-009 IMPLEMENTED（真机待验）；STEP-010 IMPLEMENTED（核心SIM通过）；STEP-011 IMPLEMENTED（Chrome实测/真机待验）；STEP-012 IMPLEMENTED（Chrome/SIM通过、终端待验）；STEP-013 IMPLEMENTED（页面/会话本地通过、终端待验）；STEP-014 IMPLEMENTED（正式主页本地通过、终端待验）；STEP-015 IMPLEMENTED（本地通过、终端待验）；STEP-016 IMPLEMENTED（Chrome真实采麦/输出/挂断/取消通过，其他分支待验）；STEP-017 IMPLEMENTED（SIM/Chrome通过、手机输出待验）；STEP-018 IMPLEMENTED（SIM/Chrome通过、系统中断待验）；STEP-019 IMPLEMENTED（SIM/Chrome通过、终端待验）；STEP-020 IMPLEMENTED（本地部署／实际链路有局部证据，按用户决定保留余项）；STEP-021 IMPLEMENTED（证据与契约已汇总，本版交付完结，全量验收保留） |

### 9.2 STEP明细

| STEP | 功能名称 | 需求ID | 验收ID | 前置STEP | 状态 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| STEP-001 | 确定技术接入与参数验证记录 | F-008、F-010、BR-043 | AC-100 | 无 | VERIFIED | §9.5技术采用记录；E001-SOURCE/NORMAL/BOUNDARY/BUDGET/SCOPE均PASS；仅AC-100技术记录子条款，无业务运行验收 |
| STEP-002 | 建立 BGM 管理访问与只读查询边界 | F-007、F-009、BR-030 | AC-054、AC-055 | STEP-001 | VERIFIED | §9.6；21项领域/静态测试、80项相关回归、五角色真实Chrome交互通过；9项历史清单失败保留 |
| STEP-003 | 完成音频上传到就绪及失败恢复 | F-007、F-008、BR-031、BR-033、BR-036、BR-037、BR-038、BR-039、BR-040、BR-044、BR-045 | AC-054、AC-055、AC-056、AC-057、AC-062、AC-066、AC-067、AC-068、AC-069、AC-070、AC-071、AC-072、AC-073、AC-074、AC-086 | STEP-001、STEP-002 | VERIFIED | §9.7；隔离API/MySQL/FFmpeg/Chrome及获准OSS单对象验证通过；未迁移业务库或部署 |
| STEP-004 | 维护唯一默认和原子有序歌单 | F-007、BR-031、BR-032、BR-033 | AC-054、AC-056、AC-058、AC-059、AC-060、AC-061、AC-066 | STEP-002、STEP-003 | VERIFIED | §9.8；真实API/Chrome、隔离MySQL并发及相关回归通过 |
| STEP-005 | 维护每曲可选封面并隔离音频版本 | F-007、F-009、BR-032、BR-033、BR-039、BR-044、BR-045、BR-046、BR-048、BR-049 | AC-054、AC-062、AC-073、AC-079、AC-083、AC-084、AC-085、AC-086、AC-087、AC-088、AC-089 | STEP-001、STEP-002、STEP-003、STEP-004 | VERIFIED | §9.9；本地API/图片/浏览器/并发及获准真实封面OSS读回/精确删除通过 |
| STEP-006 | 完成等期手动删除与专属资产清理 | F-007、F-008、F-009、BR-034、BR-035、BR-050 | AC-054、AC-063、AC-064、AC-065、AC-072、AC-073、AC-089、AC-090、AC-091 | STEP-003、STEP-004、STEP-005 | VERIFIED | §9.12；等待期/资格/角色/逐对象/幂等/部分失败/崩溃恢复/API/Chrome及MySQL并发通过 |
| STEP-007 | 提供匿名一致目录与受控服务端缓存 | F-006、F-009、BR-001、BR-026、BR-029 | AC-045、AC-053、AC-060 | STEP-002、STEP-004、STEP-005、STEP-006 | IMPLEMENTED | §9.13；匿名API、实际Redis/隔离MySQL及Chrome网络验证通过；AC-053预发布DEP证据待STEP-020补齐 |
| STEP-008 | 接通 BGM 审计及既有日志筛选 | F-007、BR-041、BR-042 | AC-060、AC-077、AC-083、AC-089 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007 | VERIFIED | §9.14；112项相关测试、10项MySQL、7项Redis、真实Chrome日志筛选/详情/observer权限通过；不代结算007部署子条款 |
| STEP-009 | 实现五项本地偏好与公开设置 | F-003、BR-007、BR-008、BR-009、BR-010、BR-011、BR-042 | AC-014、AC-015、AC-016、AC-017、AC-018、AC-019、AC-077 | STEP-001 | IMPLEMENTED | §9.10；模块与公开设置本地验证通过，实际手机验收未完成，用户允许继续开发，真机仍是交付前必验项 |
| STEP-010 | 实现单文档播放意图和顺序控制 | F-004、BR-004、BR-012、BR-013、BR-014、BR-017 | AC-006、AC-007、AC-008、AC-020、AC-025 | STEP-009 | IMPLEMENTED | §9.15；控制核心SIM通过；真实输出/页面与终端分别由后续步骤取证 |
| STEP-011 | 实现真实增益、淡入淡出和能力降级 | F-004、BR-015、BR-016 | AC-023、AC-024、AC-026、AC-027 | STEP-009、STEP-010 | IMPLEMENTED | §9.16；真实Chrome AAC波形、增益/渐变/静音/故障降级通过；Safari及H5-M待验 |
| STEP-012 | 接入事件目录与统一有限故障链 | F-004、F-006、F-009、BR-012、BR-018、BR-027、BR-028 | AC-009、AC-028、AC-029、AC-030、AC-046、AC-047、AC-048、AC-050、AC-051、AC-052、AC-059 | STEP-007、STEP-010、STEP-011 | IMPLEMENTED | §9.17；事件缓存/统一预算SIM与真实Chrome+公共API/隔离SQL/AAC验证通过；H5-M/Safari待验 |
| STEP-013 | 实现独立页面生命周期和会话恢复 | F-003、F-005、BR-011、BR-013、BR-014、BR-017、BR-019、BR-020、BR-021、BR-022 | AC-021、AC-022、AC-031、AC-032、AC-033、AC-034、AC-035、AC-036、AC-040、AC-044 | STEP-009、STEP-010、STEP-011、STEP-012 | IMPLEMENTED | §9.18；八页接线、会话可靠性/检查点SIM、真实Chrome导航/加载层/BFCache/复制标签及回归通过；原生隐藏未观测，受控注入通过，H5-M/Safari待验 |
| STEP-014 | 接入主页唱片、面板和统一封面显示 | F-001、F-003、F-009、BR-001、BR-002、BR-003、BR-008、BR-010、BR-011、BR-015、BR-042、BR-047、BR-049 | AC-001、AC-002、AC-003、AC-004、AC-005、AC-006、AC-007、AC-008、AC-009、AC-015、AC-017、AC-019、AC-079、AC-080、AC-081、AC-082、AC-084、AC-085 | STEP-010、STEP-011、STEP-012、STEP-013 | IMPLEMENTED | §9.19；正式主页/Chrome真实AAC增益、封面竞态、账号界面与异常验证通过；H5-M/Safari/软键盘待验 |
| STEP-015 | 接入六类页面右侧悬浮唱片 | F-002、F-009、BR-001、BR-005、BR-006、BR-047 | AC-001、AC-010、AC-011、AC-012、AC-013、AC-080 | STEP-013、STEP-014 | IMPLEMENTED | §9.20；六页Chrome及回归通过，键盘/抽屉状态注入，实际终端待验 |
| STEP-016 | 在真实通话准备和清理边界互斥 BGM | F-005、BR-014、BR-017、BR-023 | AC-037、AC-038、AC-039 | STEP-010、STEP-011、STEP-013、STEP-014、STEP-015 | IMPLEMENTED | §9.21；原生BGM/受控语音15组、入口3组、清理7组及原语音回归通过；本地Docker/Chrome真实采麦与输出前停播、挂断/准备取消保持关闭已证；其余真实分支/目标终端待补 |
| STEP-017 | 提供短 TTS 活动衰减与可控模拟 | F-004、F-005、BR-016、BR-024 | AC-041、AC-042 | STEP-010、STEP-011、STEP-013、STEP-016 | IMPLEMENTED | §9.22；重叠/换代/超时/取消/销毁SIM、原生Chrome增益与降级暂停通过；H5-M输出能力待验 |
| STEP-018 | 接入普通带声媒体和录音临时互斥 | F-005、BR-025 | AC-043 | STEP-013、STEP-015、STEP-016 | IMPLEMENTED | §9.23；实际入口盘点、归属SIM、原生Chrome其他Audio/中断及明确恢复通过；H5-M系统中断待验 |
| STEP-019 | 实现至多一个无声下一首准备 | F-004、F-005、F-006、F-010、BR-051、BR-052、BR-053、BR-054、BR-055 | AC-049、AC-077、AC-085、AC-092、AC-093、AC-094、AC-095、AC-096、AC-099 | STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017、STEP-018 | IMPLEMENTED | §9.24；SIM/真实Chrome单候选、封面刷新保留、目录切歌、可选失败/省流量/取消通过；目标终端及实际缓存待验 |
| STEP-020 | 核验实际部署媒体与 HTTP 缓存链路 | F-008、F-009、F-010、BR-038、BR-040、BR-043、BR-044、BR-045、BR-054、BR-055 | AC-070、AC-074、AC-075、AC-076、AC-086、AC-097、AC-098 | STEP-003、STEP-005、STEP-006、STEP-007、STEP-011、STEP-013、STEP-016、STEP-019 | IMPLEMENTED | §9.25；本地更新/跨实例/时限故障、真实CORS和播放、Safari局部、2音频2封面及换图已有证据；完整媒体/缓存和手机仍待验 |
| STEP-021 | 执行完整业务验收并交付证据 | F-001、F-002、F-003、F-004、F-005、F-006、F-007、F-008、F-009、F-010、BR-043 | AC-078、AC-100 | STEP-002、STEP-003、STEP-004、STEP-005、STEP-006、STEP-007、STEP-008、STEP-009、STEP-010、STEP-011、STEP-012、STEP-013、STEP-014、STEP-015、STEP-016、STEP-017、STEP-018、STEP-019、STEP-020 | IMPLEMENTED | §9.26；100项AC已建立要求/责任/证据索引，实际闭环及最终全部环境仍未完成 |

### 9.3 阻断与来源变化

| 日期 | STEP | 类型 | 证据或变化 | 处理结果 |
| --- | --- | --- | --- | --- |
| 2026-10-19 | 全部 | 草稿建立 | 结合V1.3 PRD、当前工作区及V1.3 demo建立来源摘要与映射 | 未开始实施；无新增产品阻断决定，保留§7风险 |
| 2026-10-19 | STEP-003/004/009/014/016及相关展示 | 授权文档修复轮1 | step-audit.md中SDR-20261019-001～004；原稿与PRD/原84来源摘要保持；仅新增B23代码风险锚点 | 新候选STEP_REVIEW_READY，完整复审交回审核方；全部STEP仍NOT_STARTED |
| 2026-10-19 | SDR-20261019-004来源锚点 | 授权文档修复轮2 | 仅更正§1.3与§3.1 B23的PostCreateBody；85来源摘要保持，draft/r1只读保留 | steps-candidate-r2.md为STEP_REVIEW_READY；完整复审交回审核方，全部STEP仍NOT_STARTED |
| 2026-10-19 | 全部 | 完整复审与文档签发 | 当前85来源摘要匹配；21STEP/246覆盖项/85依赖完整复核，四项修复通过；审计见step-audit.md | PASS_WITH_RISKS / STEPS_VERIFIED；仅文档通过，实施仍0/21 |
| 2026-10-19 | STEP-001 | 本次实施与来源复核 | 用户提供STEP/PRD并调用执行器；24个本项原依赖摘要匹配，新增定向源码X01～05；§9.5完成命名/事务/去重/受限处理/审计/能力方向及18项D、21项SUG登记；15:16 CST静态核验PASS | VERIFIED，仅技术采用记录；其他20项未开始。当前契约增量为零；实际媒体/部署/终端/容量仍UNVERIFIED |

执行状态沿用本次调用的执行器：NOT_STARTED、IN_PROGRESS、IMPLEMENTED、VERIFIED、BLOCKED、NO_CHANGE_NEEDED。VERIFIED 对应原进度表 DONE 的全部完成标志有证据这一口径；不改变任何 STEP 验收条件。§6 的实施进度为签发快照，不再双写。

### 9.4 后续恢复位置

用户最新明确目标“按照文档完成开发”授权连续推进全部21项；本轮沿用本执行器、依赖和完成标准，覆盖签发文档各STEP旧有的“不得自动启动下一STEP”单项回传边界，不重复请求阶段授权。新增关键取舍、生产数据/对外发布等仍按实际授权处理。

当前7/21项VERIFIED（001～006/008），007与009～019为IMPLEMENTED，020/021当前IN_PROGRESS（原前台恢复依赖已解除，实际手机和完整媒体闭环仍待）。019已完成单候选准备及本地SIM/Chrome验证，详见§9.24。用户2026-10-20已批准本地v9g→v9h迁移、backend替换和Nginx重载，三项已完成，详见§9.25；当时真实目录200且空歌单；此后用户完成一条验收音频上传，当前已隐藏，详见本节恢复补充。旧运行配置/迁移位置已保存到私有临时路径，保留旧镜像及原环境/卷/回环端口。原两次单对象OSS测试均已精确清理，其授权不扩展至新发布。

用户指定Chrome/Safari及本地Docker验收，允许普通测试账号自行新建；已通过正式register创建独立user_id=2并在Chrome正常登录，既有user_id=1未改。不得把账号ID当凭据或签发冒用JWT。Safari原生连接、实际音频增益核心及首页/朋友圈局部流程已通过（其他页面和完整场景仍待验），实际通话/BGM、手机、缓存/资源故障与完整闭环仍待补。用户2026-10-20已明确批准020四对象真实媒体闭环及满24小时后精确清理，且已自行登录后台和id=1客户端。后台刷新后superadmin有效；id=1页面为localhost:8000，127.0.0.1仍是独立测试账号。文件桥原阻塞现已由用户手动上传解除；已核对曲目A及来源摘要，不重复上传。实际CORS规则已获准应用且两来源HTTP验证通过；原地址缓存故障随后定位并解除，正式首页播放和真实10秒语音冒烟通过，详见下方14:56恢复记录。原两音频/两封面及等待清理授权继续有效。runtime loader已确认id=1语音门禁允许、id=2拒绝（voice-eligibility.json）；不能扩大白名单代替授权登录。无依赖的代理/资源故障及021索引/契约核对已经完成本轮可验证部分。保留用户已批准的手机延期：可以继续开发，但H5-M是交付前必验，相关项不得提前VERIFIED。原专属MySQL/Redis临时容器已不存在，旧端口不可使用，历史有效证据保留；当前独立浏览器夹具结束即清理。原始PRD及§1～8只读，不覆盖用户既有改动。


历史阻塞审计（2026-10-20，用户手动上传后已解除）：Chrome文件选择桥失败及空文件控件这一条件连续三轮仍存在，本轮再次读取files得到空数组；期间已独立补齐实际120秒接收/编码、远端MIME/读取超时及MySQL两API进程音频/封面恢复证据，相关测试均已终态且临时服务已清理，没有运行中的任务等待。当前剩余关键路径是获准真实媒体上传、CDN/Range/CORS/缓存、真实BGM与通话和Safari/手机完整验收；再重复隔离测试不能替代这些环境证据。目标按阻塞状态交接，未完成、未降低验收标准；恢复动作是在保留的后台上传窗口正常选择准备好的tone.m4a后继续，同一上传/清理授权与合法登录继续有效。021索引中六处旧“未授权”描述已纠正为已授权但尚未执行。

恢复补充（2026-10-20 14:06 CST）：用户“已经上传”后核实实际操作4076666d-dc05-4506-9b3b-531978c63c81成功，曲目eaac96d8-782c-44ab-807a-3ec3d0d11fd4来源摘要与获准tone.m4a一致。后台原生试听有时间推进；真实OSS音频MIME/完整摘要/206 Range/304验证通过，但localhost:8000 Origin响应没有ACAO，正式前台明确播放失败。13:57:30 CST已隐藏，歌单空；最早清理2026-10-21 13:57:30 CST，未删除。当前1音频/0封面，第二曲尚未提交。源码补齐实际来源CORS/Range发布校验，24项定向及36项容器链路通过，修复镜像已在获准本地Docker生效；未操作线上、Bucket规则或ACL。GetBucketCORS只读403；用户随后明确当前无CORS规则，已准备两本地来源GET/HEAD规则并单独询问配置授权，尚未修改。实际媒体/通话/手机/Safari完整验收仍未完成，目标恢复active，不把原文件桥失败继续当作当前阻塞。

历史阻塞审计（2026-10-20 14:17 CST，随后授权及HTTP缺头条件已解除）：实际OSS对本地前台缺少CORS许可这一条件，自用户手动上传后的首次实测、下一轮原生跨域/朋友圈核对、到本轮当前响应复核连续三轮仍成立。上一轮属于进展（原生跨域测试通过、用户确认无规则、朋友圈只读核对和具体配置方案完成），本轮未重复测试制造进度。`cors-blocker-audit.json`确认206内容正确但ACAO仍缺失，正式本地目录版本2且空，运行镜像仍为已验证的cors-gate修复版本。已有原生测试session34152明确exit0，无活任务可等待；当前时间距原曲目24小时清理资格尚不足。用户提供“无规则”及允许查看朋友圈不构成Bucket变更授权，具体规则审批问题保持待答复。独立可验证代码/受控故障工作已完成当前范围，剩余真实媒体/通话依赖实际CORS修复，Safari/实际手机及等期清理也不可用模拟代替。目标转blocked，未完成，不降低PRD/STEP标准；获准后从控制台核对空规则并应用oss-cors-change-plan.json恢复，不再请求同一对象上传许可。

恢复记录（2026-10-20 14:31 CST）：用户明确“允许按此方案配置”后，OSS控制台核对无规则，新增且保存所批两来源GET/HEAD、Range、三暴露头、600秒及Vary Origin规则。实际两来源完整GET200、Range206、HEAD200、预检200及条件GET304均带对应ACAO/Vary，文件摘要保持；所查朋友圈图片HEAD200。原CORS缺头阻塞已解除，不能继续沿用该三轮阻塞计数。按原测试授权，14:23:23 CST重新启用A，操作2a834dbd-ec0e-4903-88ac-343705369b3d成功，目录版本3。实际Chrome两个来源重试仍显示播放失败，原因未定，不能归因为缓存或宣称输出通过；旧标签输入超时，新标签可操作，随后原生Chrome操作超时导致浏览器连接中断，管理页无法继续收回曲目。14:31:30 CST只读数据库确认A仍enabled=1、record_version=5、hidden_at为空，已请求用户在正常后台隐藏。旧2026-10-21 13:57:30 CST清理资格因重新启用失效，必须按下一次成功隐藏重计24小时；不得提前删除。未新增音频/封面对象、未改源码/ACL/RAM/朋友圈资源。恢复位置：先核实隐藏结果与新等待期，再恢复浏览器连接获取实际播放失败依据；证据见020/oss-cors-after-http.json、oss-cors-configured.png、cors-after-browser.json。当前未完成，不重复询问已批准规则或媒体批次。

恢复记录（2026-10-20 14:56 CST）：用户“已隐藏”后只读确认A record6/catalog4、14:41:23隐藏；随后恢复新Chrome标签控制。原地址原生audio报code4，同对象仅加诊断参数后原生及生产BgmPlayer/gain链成功；对原地址做一次正常CORS fetch(cache=reload)，200/366438字节/SHA一致，再用原地址原生与生产模块播放成功，gain峰值RMS=0.026925814054040462。确认此前原地址浏览器缓存导致故障，没有改媒体URL/对象/产品源码或关闭CORS/证书校验。临时诊断页已删除，测试夹具及证据保留。用户重新登录新后台superadmin后，按原授权正常启用A，目录5；正式localhost:8000 id=1首页显示播放、暂停、手动继续正常。真实语音接通10秒并正常挂断；准备时BGM关闭，结束仍关闭，手动重新播放成功。该冒烟不替代全部准备顺序、异常清理或手机验收。封面filechooser再次被扩展文件桥拒绝，未传字节；不重复要求修改扩展权限。已正常隐藏A，record8/catalog6空目录，hidden_at=2026-10-20 06:54:55.518855 UTC，最早清理2026-10-21 14:54:55.518855 CST；重启用仍需重计。当前1音频/0封面。恢复位置为保留的新后台A封面对话框，等待用户选择已批准的cover-a.webp，然后继续两音频/两封面上限内流程；Safari/真机及24小时清理仍待完成。依据020/browser-media-cache-diagnosis.json、home-real-media-retest.json、real-media-hidden.json。CORS及原地址播放阻塞已解除，不沿用旧三轮计数。

历史阻塞审计（2026-10-20 15:27 CST，已由用户上传封面A解除）：封面文件桥拒绝代选后，原执行轮与后续两次自动续轮均未取得用户文件选择；当前保留后台1849770074仍显示封面版本“无”、“保存封面”禁用，见020/cover-selection-pending.png及runtime-followup.json。上一续轮只读DB确认A record8/enabled0、目录6且默认空、处理槽free、活动通话0；没有可轮询的活动上传或处理任务。本轮无实现/验收增量，既有有效结果继续复用。CORS及原地址缓存故障已经解除，不能作为当前阻塞。剩余实际封面/第二曲/完整缓存闭环需要先选择已批准cover-a.webp；Safari原生连接与真实手机环境仍缺，24小时清理资格尚未到达；不以重复隔离测试替代实际证据。相同输入阻塞已连续三轮，目标标为blocked，未完成。恢复时从保留封面表单继续，同批次两音频/两封面及正常隐藏、满期精确清理授权继续有效，不重复确认权限。

恢复记录（2026-10-20 16:03 CST）：用户“已经上传”后核对正式后台已保存封面A，操作0a6c31ac-2507-439d-ba4f-f39074539858成功，asset=525e3f78-fd1a-4a13-8d37-57102c89f7f2、cover_version=03ba189d-49d3-468e-845d-373a60fbc222，542字节与批准cover-a.webp摘要一致、512×512 WebP。隐藏状态补图未启用、目录仍6且音频版本未变；实际HTTPS两来源GET200/CORS/Vary/完整摘要及条件GET304通过。按原授权启用到目录7，正式localhost:8000首页实际图片complete且naturalWidth/Height为512，页面显示正在播放。Chrome原生界面另显示该页标签音频已静音，故不把播放指示当设备扬声器可闻性证明。扩展文件桥此前拒绝代选；本轮尝试文档允许的原生选择器降级，成功定位BGM窗口，但点击前发生用户窗口切换，未选择或上传第二图；没有更改扩展权限。完成本段后正常隐藏A，record11/catalog8空目录，hidden_at=2026-10-20 08:00:32.727249 UTC，最早清理2026-10-21 16:00:32.727249 CST。当前1音频/1封面；后续仍限再新增1音频/1封面。旧cover-a输入阻塞由用户操作解除，目标恢复active。恢复位置为保留后台1849770074的A封面对话框：用户用cover-b.webp替换保存，随后通过“上传音乐”上传tone.m4a并命名BGM 验收 B 20261020、保持未启用；再核对操作与摘要后继续正式双曲/换图/缓存和终端验收。已批准批次和清理规则继续有效。证据为020/real-cover-a.json、cover-a-browser.json、cover-a-admin-saved.png、cover-a-home-playing.png、cover-a-hidden.png及更新后的精确归属/隐藏记录。产品源码和运行镜像本轮未修改，未完成的Safari/手机/Range缓存/换图不中断/满期删除不能提前判通过。

恢复记录（2026-10-20 16:14 CST）：Safari原生连接恢复后，使用现有音频原HTTPS URL及生产BgmPlayer/Controller/Output模块完成实际核心验证。macOS 26.5.1、Safari 26.5（21624.2.5.11.4）；版本来自本机应用Info.plist。30%播放时gain输出RMS约0.0265；设零后actual仍playing、paused=false且媒体时间由7.37推进至21.91秒，RMS为0；恢复30%后RMS约0.02649且无媒体错误。停止后paused=true/time0，诊断标签已关闭，临时静态副本已删除，测试夹具保留。截图/原生AX可见JSON采样及针对性断言见020/safari-real-output.json、safari-output-check.txt、safari-gain-recovered.png。一次界面采集瞬时失败后同句柄恢复，未当作终态或重启Safari；初版AX文本截断仅调整诊断摘要显示。该结果证明实际Safari音频增益核心，目录/偏好仅本页内存，不能当作正式首页/其他页面、默认零值持久化、降级路径、真实语音、手机或完整Range缓存验收。未新增OSS对象、未改业务库或产品源码/运行镜像。保留后台1849770074当前仍是封面A、保存禁用；cover-b替换与第二条tone音频仍待用户按上轮说明操作。现有等待期及对象预算继续沿用，不重新上传A或扩展授权。

恢复记录（2026-10-20 16:17 CST）：准备进入Safari正式前台时，原生工具明确报告Mac锁定且自动解锁不可用，须用户手动解锁；没有尝试绕过锁屏或输入凭据。Safari诊断测试此前已经停止并关闭、临时静态文件已清理，原生连接恢复和核心输出证据继续有效，不能把当前锁屏当成原Safari音频失败。锁屏后只读核对A仍record11/enabled0/cover版本03ba189d-49d3-468e-845d-373a60fbc222，公共目录8且默认空；仍1音频/1封面，第二曲未创建，处理槽free，无可轮询的活动BGM上传。没有修改业务数据或重复运行已有测试。Chrome后台1849770074的A封面表单已标记保留；Safari正式新标签未能打开。恢复位置：用户手动解锁Mac后继续Safari正式页面，并核对cover-b替换及第二条tone上传结果；原批次和24小时清理授权继续有效。目标保持active、未完成；新的锁屏阻塞从本轮重新审计，不沿用已解除的旧阻塞计数。

恢复记录（2026-10-20 16:48 CST）：Mac手动解锁后原生输入恢复；用户重新打开Safari投影并将窗口置前，正式页面从document.hidden=true/hidden blocker变为visible且无blocker。该条件下手动恢复播放成功，未绕过可见性保护或改产品逻辑。按原授权使用A完成实际Safari正式首页的手动恢复、暂停/继续、真实滑杆拖至0时静音播放、恢复30%、播放中收起面板、关闭后收起/重开仍关闭；正常刷新已恢复的原始源码页面后，诊断显示消失，关闭状态与30%保持，手动播放正常。公开朋友圈页跳转后等待手动恢复，点击恢复显示播放；该页关闭后返回首页仍关闭。此为首页/朋友圈局部正式流程，不替代其他五类页面、渐变时长/降级、真实Safari通话、设备扬声器可闻性、完整Range缓存或手机验收。原生AX setter/键盘/单点滑杆操作未可靠达到请求值，仅实际拖动且可见值吻合的0/30计证据，最终音量恢复30%。临时首页诊断已撤回且源码字节一致，测试夹具保留；见020/safari-formal-flow.json、safari-formal-visibility.json、safari-formal-probe-receipt.json及相应截图。

本轮另完成实际后台改名/恢复：目录9→10→11，音频/封面URL及版本保持，两者真实OSS条件GET均304、空响应体、ETag与CORS保持。仅证明元数据改名和服务端条件响应，不冒领浏览器缓存命中或Range复用；见020/metadata-cache-rename.json。改名恢复后正常隐藏至目录12，随后Safari验收启用至13，最终正常隐藏至14；只读DB确认A record17/enabled0、hidden_at=2026-10-20 08:47:16.343166 UTC，最早普通清理2026-10-21 16:47:16.343166 CST，旧等待时点失效，未提前删除。仍1音频/1封面、无第二曲，处理槽free；未新增OSS对象、未改运行镜像或业务源码。后台1849770074保留A封面表单，cover-b替换及第二条tone上传仍待文件选择；原生Chrome降级再次遇到用户切换窗口，未选文件，不抢占用户当前窗口。当前有实际验收进展，目标保持active，整体未完成；后续先完成已批准的剩余1音频/1封面，再补双曲/换图/缓存与剩余终端验收，等期后按原授权精确清理。

恢复顺序：先由用户在保留表单选择cover-b.webp，暂不保存；随后在原授权内重新启用A并建立真实播放，再提交这唯一剩余封面对象，以保留播放中换图的验收机会。第二条tone.m4a待此段核对后按正常上传流程创建，不能用重复上传消耗对象预算。

恢复记录（2026-10-20 17:06 CST）：本轮补齐实际Safari访客设置：两个BGM开关从on改off，正常刷新仍off，再恢复原on/on；未弹登录窗，访客私有设置区仍不显示。因音乐会话已关闭且目录为空，不能从无声推定“开关不改变有效播放意图”，仅计设置可操作/保存证据。实际访客记忆、日记、关系入口均显示既有登录弹窗，随后正常关闭，未提交凭据；证据中的自动填充账号已脱敏。复用已获准且正常注册的id=2现有凭据，通过正式登录进入Safari记忆页（0颗记忆）；未冒用id=1、未改语音名单，Safari保存密码提示选“以后”，凭据未输出或写入证据。当前仅证明合法登录和页面进入，私有页实际播放未执行。证据为020/safari-settings-guest.json、safari-guest-entry-gates.json、safari-private-pages-probe.json及设置截图。

准备一次启用A以验收已登录页面时，原后台会话失效跳转login，原生工具又报告Mac锁定。只读DB于2026-10-20 09:05:28 UTC确认A仍record17/enabled0、catalog14/默认空、处理槽free，最后操作仍16:47隐藏；没有成功启用或新增对象，既有最早清理2026-10-21 16:47:16.343166 CST保持。Safari测试账号2仍登录在记忆页，音乐未播放；正常退出待用户解锁后完成，不冒充已清理。Chrome后台登录页已保留，已请求用户手动解锁并重新登录，无需提供密码；恢复后先核对合法后台会话，再继续真实私有页/换图和第二音频，最后正常退出Safari测试账号。前一goal轮和本轮均有实际验收进展；新的锁屏/后台登录条件从本次发生重新记录，不沿用已解除的历史阻塞计数，整体保持active且未完成。

历史锁屏/登录阻塞审计（2026-10-20 17:12 CST，后由用户正常解锁登录解除）：连续第3个goal轮仍为同一外部条件。前一轮NO_PROGRESS；本轮重新观察后台1849770074仍在登录页，Safari原生读取仍明确报告Mac锁定。无活动上传/编码/测试进程可等待；实际媒体、私有页、Safari测试账号退出、手机与满期清理均需用户输入或外部状态改变，独立实现及可执行受控验证已有有效证据，不重复测试代替。六条AC索引旧状态已按现有证据纠正，不是新增功能验收，也不解除当前阻塞。目标转blocked，未完成，不降低验收范围；原手动解锁/后台正常登录请求继续有效。恢复后核对正常会话，先完成Safari测试账号2的待退出/后续验收安排，再按原2+2预算继续真实私有页、cover-b选择后播放中保存和第二音频；保留手机交付前必验、满24小时普通精确清理规则，不新增自动化。

历史阻塞记录（2026-10-19，已由§9.11用户决定解除）：同一授权/验收依赖连续三轮未解除，现有本地证据摘要无变化；封面receipt仍prepared且ownership_claimed=false，无新手机证据。目标转为blocked，未宣称全部完成。已发送的问题保持有效，不重复请求：①允许已登记封面单对象OSS测试并精确清理后恢复STEP-005；②允许先继续开发但保留H5-M为交付前必验项，或提供实际手机证据后恢复STEP-009/010。收到对应决定后仅恢复满足条件的分支，其他验收仍保留。
恢复记录（2026-10-20 18:26 CST）：用户正常解锁/登录后，后台superadmin有效；对原未确认启用87397508-fbf4-4a4b-b1cb-cbe96ed8409a先核对，再用同标识原内容重发成功catalog15，没有另建素材。Safari记忆页只读诊断直接证明auth=true、挂载成功，唯一阻断为document.hidden；用户先回复再切到实际Safari后hidden=false、气泡显示，明确恢复到playing。关系页恢复播放/暂停、回首页及聊天页保留暂停、聊天关闭移除气泡/回首页保持关闭，设置播放中关闭自动播放和渐变不打断、恢复on/on，最后正常退出测试账号2。日记对该账号未解锁、记忆为空，不能据此冒领日记内容/抽屉。临时两HTML诊断已逐字节恢复并删除静态探针，NO_CHANGE_NEEDED仅针对隐藏保护，非产品修复；证据020/safari-private-pages-visible.json、safari-private-page-diagnosis.json及safari-private-probe-receipt.json。

同轮真实媒体继续：首次收尾隐藏record19/catalog16；用户恢复Chrome后，正常浏览器复制管理标签保留原未保存封面，不提取/转传Token；副本启用A到catalog17，原表单刷新版本仍保留cover-b预览。正式Chrome实际playing、generation3时保存封面B，操作f47982f0-a07a-4abc-b3c7-3e66da749c9f成功，保存前后时间约19→28秒、音频URL/版本/音量/最后手选保持；旧图pending且not_before=2026-10-21 10:18:41.298326 UTC。新图版本8bf94824-6114-44d2-b150-d49c160c8ebd在正常曲终目录刷新到18后解码512×512；本证据不是播放中途目录刷新无重启的完整证明。正常原生选择tone.m4a并上传第二曲B（操作4570e218-24fd-4ba0-998d-23ceea46902c），来源摘要一致、ready且先未启用；后台实际试听7秒推进后暂停，再正常启用目录19。两个新对象的真实两来源HTTPS全摘要/Range206/条件304/CORS检查通过，不冒称浏览器缓存命中。现共2音频/2封面，授权额度已用满，不再新增；前台双曲准备/切换继续，最终隐藏及清理资格以本轮收尾回执为准，旧18:07隐藏资格已因再次启用失效。没有改Bucket/ACL/朋友圈或运行镜像。

收尾与中断恢复（2026-10-21 09:56 CST）：前轮真实Chrome自然取得目录19并完成A/B曲终切换；无图B实际播放且使用内置黑胶；暂停B后下一首回A、进度0且保持暂停，明确播放A后下一首B正常playing。页面complete/加载层移除/接近曲终时，实际连接effectiveType=3g，按规则跳过准备；不计正常网络准备成功。10项断言及原始事件见020/two-track-live-check.json、two-track-live-first.json、two-track-live-eligibility.json、two-track-live-controls.json。跨域ResourceTiming零transferSize不能当缓存命中。Chrome正常下一首更新最后手选为测试曲B，音量30%/渐变/自动播放保持；无服务端偏好或鉴权变更。

前轮前台正常关闭，后台隐藏B至目录20、再隐藏A至21，副本关闭、原后台刷新保留；前台正常reload清掉存活诊断，两探针均恢复原字节并删除静态副本。新正常Chrome标签显示0首和播放/下一首禁用；继承合法本地账号，不冒称访客测试。最终回执two-track-final-hidden-runtime.json；本轮只读two-track-resume-20261021.json确认镜像未变、A record22/B record4隐藏、catalog21/default空、槽free，仍2音频/2封面、上传预算0。A最早普通清理2026-10-21 18:32:56.551807 CST，B为18:32:40.112927，旧封面A not_before为18:18:41.298326；整批取较晚时点并重检服务端资格后精确清理。尚未到期、未删除或建自动化，任何重启用再隐藏均重计。无活动上传/测试句柄等待；旧锁屏/登录/选文件条件已解除。本轮补齐中断记录及索引；手机、正常网络准备、实际浏览器缓存/Range/有限带宽和完整异常分支仍待。

本轮缓存观察补充（2026-10-21）：创建独立只读诊断页，仅读取已批准保留的媒体；音频A原生metadata/30秒/无错误已观察，但Network面板经正常刷新仍没有可核对请求明细，缓存来源、浏览器206及节流行为不判通过。当前HEAD确认ACAO正确、无Timing-Allow-Origin；Chromium/W3C计时资料仅解释跨域零值不能单独证明缓存，未增加Bucket头或规则。诊断静态副本已精确删除、夹具语法通过、页面最后No media loaded；原有设备工具栏为开启/iPhone16ProMax/Fit to window，临时关闭后因Chrome被切到其他工作窗口，恢复尚未确认，诊断标签保留待正常前台恢复。未操作其他工作页、没有新业务/OSS写入，也未重启用曲目。当前两个本地端口仍只绑定127.0.0.1；实际手机/可访问测试地址已询问，未改变网络开放。证据020/http-cache-observation-attempt.json、http-cache-devtools-initial.json、http-cache-probe-receipt.json。此为新的观察/恢复输入依赖第1轮，不沿用已解除的旧锁屏计数；整批18:32:56.551807 CST清理门保持，当前不足期。

当前恢复阻塞审计（2026-10-21，连续第3轮）：前轮NO_PROGRESS，本轮原生读取仍是其他Chrome工作页，保留诊断DOM仍为No media loaded；原设备工具栏开启状态的恢复尚未确认。当前前台恢复及真机/可访问测试地址问题均未收到用户答复，没有活动上传、编码或测试句柄可等待；当前时钟仍不足整批24小时清理门。上一个有进展轮已完成中断记录同步、双曲断言/索引及缓存观察限制调查，当前不能用重复测试或状态整理冒充功能进展。原Mac锁屏/登录/文件选择阻塞已经解除，不沿用旧计数；本项新的恢复输入条件现连续3轮，STEP-020/021与目标转BLOCKED，未完成。恢复后先正常还原诊断标签原设备工具栏并关闭，再按已有授权继续可靠缓存/Range和真实手机验收；清理仍需18:32:56.551807 CST后重检资格且只涉及已登记4对象，无新上传预算、不建自动化、不改对外端口。

恢复完成（2026-10-21 10:45 CST）：用户提供精确诊断地址并保持前台后，已定位同一Chrome标签1849772445，原生界面确认设备工具栏恢复开启、iPhone 16 Pro Max、Fit to window；Disable cache仍未勾选、No throttling，页面无已载入媒体。已保存http-cache-devtools-restored.txt/.png，并精确关闭该诊断标签，浏览器标签清单确认已不存在。此时Network可见本地诊断文档304及扩展资源行，但没有媒体请求，不能据此判定音乐缓存、Range或有限带宽通过。原前台恢复阻塞已解除，旧连续3轮审计仅作历史，STEP-020/021恢复IN_PROGRESS；实际手机与可访问地址、媒体缓存/Range、正常网络准备和完整分支仍待，整批18:32:56.551807 CST前不得普通清理。本轮没有业务、OSS、对外端口或产品源码变更。

媒体缓存与Range实证补充（2026-10-21 10:58 CST）：已用同一批准批次的四个保留对象在实际Chrome155原生媒体诊断中取证。A两次重建各有206磁盘缓存行，B载入亦见206磁盘缓存；B同URL重建和新旧封面重建均实际完成，未将无新增请求行单独推定为某类缓存。两版封面首次在本轮各出现304条件请求并512px解码。临时Disable cache及3G预设仅用于独立页：30秒B在缓冲约2.71秒、networkState=2时进入playing；再从首段不足状态请求24秒，实际GET Range bytes=262144-，206 Content-Range bytes 262144-366437/366438，随后24秒seeked/playing，缓冲分为首段与21.461～26.876秒。证据http-cache-live-check.json、live-events、a-repeat、cover-b-repeat、range-headers及截图。明确只是实际OSS/桌面Chrome原生媒体与HTTP子范围，未替代正式播放器完整流程或手机、Safari、真实缓存回收。已释放媒体、还原缓存启用/No throttling/设备工具栏开启及原iPhone16ProMax/Fit、关闭精确诊断标签并删除同摘要静态副本；无产品源码、业务、OSS或端口变更。旧Network无行阻塞已解除；AC-097/098仍NOT_RUN_FULL_FLOW，尚缺目标终端与全部规定子场景。

Safari媒体网络实证补充（2026-10-21 11:16 CST）：用户单独批准临时开启“显示网页开发者功能”后，实际Safari26.5/Web Inspector记录同一四对象测试。A、B各首次及重建均发0～1和0～366437 Range请求；重访标头来源为网络、206、Content-Range bytes 0-366437/366438、audio/mp4、正确ACAO及30天immutable缓存。两版封面各网络200/image-webp、对应542/546字节与独立URL/SHA，重建未增可见网络行；释放媒体后分别确认实际512×512解码。B播放、在已完整缓冲情况下定位24秒继续、暂停/释放正常，不把本次定位冒充未缓冲补段或Safari有限带宽证据。重复音频重新下载符合PRD允许未命中重请求，没有为零下载改URL或缓存配置。中途Mac锁定由用户手动解除；已释放媒体、关闭本轮检查器及精确诊断标签、恢复开发者功能关闭，静态副本已按摘要精确删除。HAR导出按钮不可用，保存原生网络行/标头和截图，不声称有HAR；本轮没有缓存清空、限速、业务、OSS或产品源码写入。证据safari-cache-live-check.json、safari-cache-*-headers.txt、safari-cache-developer-pref-restored.txt/.png；目标手机、正式完整流程、Safari有限带宽/缺段和真实缓存回收仍待，原锁屏条件已解除，无待还原全局设置。

正常网络准备验收恢复点（2026-10-21）：本轮拟继续正式主页单候选准备，尚未执行功能试验。03:23 UTC只读本地Docker确认A record22/B record4均隐藏、catalog21、4对象及槽free；未启用曲目、未改原隐藏时点或上传预算。按既有方式临时接入只读观察器并打开正式/pages/index.html；初始摘要只是interactive阶段4g/downlink0.4，不作为当前成熟网络判定。Chrome原生输入出现无可用窗口及屏幕捕获间歇失败，浏览器输入也超时；重复读取同一句柄确认页面仍存活，没有因此重启服务或测试。Fast4G菜单未实际设置成功，未采集下一首准备通过证据。当前已先按摘要恢复index.html原字节并精确移除观察脚本；保留的1849772466标签内仍有已载入观察器，等待用户将该Chrome分组显示在当前桌面。最新原生状态为设备工具栏临时关闭、No throttling、缓存启用，原工具栏开启/iPhone16ProMax/Fit尚待恢复；该恢复义务记入preparation-formal-probe-receipt.json。前台请求已提交，暂无活动音频/处理任务可等。此轮NO_PROGRESS（新输入依赖第1轮），020/021仍IN_PROGRESS，前轮Safari功能证据有效；不以诊断准备或记录整理冒充功能完成。原整批最早18:32:56.551807 CST清理时点尚未变化；任何后续启用再隐藏需重算。

正常网络准备实测与收尾（2026-10-21 11:49 CST）：用户将精确Chrome主页置前后，原输入依赖解除。仅复用已批准两曲四对象，后台正常启用A到目录22、B到23；原空目录快照在300秒有效期内继续使用属既定行为，过期后正常刷新取得23。实际桌面Chrome155临时Fast4G预设，页面complete/加载层移除/online、4g/downlink8.2/省流量关闭；30秒A在22.845533秒出现唯一B候选ready，8次采样至29.219961秒仍playing、generation14不变、已记录的四项偏好快照不变（本轮未新采样动效项）；随后A曲终30秒、B自然playing至6秒。暂停发生在切B后且候选已idle，因此本轮不计“ready候选暂停取消”；不把状态日志当候选声学静音或play调用计数证据。两曲正式正常准备子范围通过，不冒领长歌单/实际手机/完整AC。原生Network附有A206磁盘缓存、B两条206及封面304行；跨域ResourceTiming零值仍不单独推定缓存来源。

正式页面已暂停后关闭，后台先隐藏B到目录24、再隐藏A到25；只读SQL确认A record24/B6均隐藏、默认空、4资产未变、槽free。A新hidden_at=2026-10-21 03:47:52.612573 UTC，B=03:47:41.187719；整批最早普通精确清理改为2026-10-22 11:47:52.612573 CST，旧21日18:32截止已因重启用失效。旧封面not_before不变，未删除、未建自动化；到期仍需重检普通服务端资格。index.html已恢复原摘要、静态观察器删除；Chrome还原设备工具栏开启/iPhone16ProMax/Fit to window/No throttling/Disable cache=false并留证，只关闭本轮主页1849772466和后台副本1849772469，原AI测试工具标签保留。无新上传/产品源码/运行镜像/Bucket或端口变更。证据020/preparation-formal-live-check.json、ready/paused/closed、final-hidden-runtime、admin-hidden及devtools-restored截图与回执；唯一归属/等待记录和索引同步新时点。本轮PROGRESS、新输入阻塞计数归零，020/021保持IN_PROGRESS；目标未完成，真机/完整分支/满期清理继续保留。

代理串联绝对接收实证（2026-10-21）：本轮新增tests/test_bgm_nginx_deadline.py，用当前业务镜像同digest及已运行Nginx逐字一致配置，在新internal网络内串联真实ASGI/API（lifespan off）和隔离SQLite，无宿主公开端口或业务/OSS/Provider连接。声明8字节，首次2字节后每20秒给1字节，100秒共发7字节；接纳后120.088秒经Nginx返回HTTP200、持久failed/receive_timeout，不是代理408/504。原120/300秒deadline未变，同键重放不延时，新操作429/20205；同代理查询结果一致、槽free、work目录空、资产0。最终1 passed in121.27s；仅本轮容器/网络移除且absent确认。证据020/nginx-deadline-live-check.json及runtime/results/原始日志，运行器字节快照保留，未改产品源码、业务库或运行配置。

首轮新测试于1秒附近错误要求目录始终200，实际隔离夹具刻意拒绝Redis，本地1秒缓存过期后处于2秒回源冷却返回503/20207/Retry-After2。对照未修改PRD AC-053“有界回源或明确失败”和BR-029及实际cache代码确认原预期过强；保留assertion-red日志和精确清理回执，仅修正为3.5秒内成功或明确503（本轮0.004秒），绝对计时/终态/回收断言未弱化。不是产品缺陷修复或实际业务Redis故障演练。按systematic-debugging定位、verification-before-completion核对当次原始结果与源码摘要；历史隔离MySQL/资源/单独接收与编码证据按有效范围复用。新增证据覆盖AC-074/076的代理串联慢接收子项，不替代完整300秒处理/前端330秒、手机或整体DEP，STEP020/021仍IN_PROGRESS。

真实语音时序验收恢复点（2026-10-21 12:13 CST）：前轮代理串联测试为PROGRESS且已终态/精确清理。本轮继续AC-037/039首次采麦/输出边界，后台正常复制原AI测试工具标签，副本1849772483访问BGM后因原会话过期回到login；未提取/重签Token或重置密码，未改原用户标签。正常表单未提供可用自动填充，已请求用户在新登录页自行登录，问题仍待答复。正式主页1849772480继承原前台合法会话，未操作账号。此时未启用曲目、未发起真实采麦或Provider通话，不把准备工作算功能通过。

新增tests/bgm_voice_timing_live_probe.js记录原生getUserMedia、context.resume、AudioBufferSourceNode.start及BGM媒体play/pause入口；同this/同参数委托原函数，直接返回原结果/Promise，不伪造权限、媒体或调用结果。仅记录时点、BGM状态、原生paused/位置及本地五项快照，不记录录音、正文、凭据或设备标识。所有钩子在当前Chrome可用，observer-ready且nativeMicCalls0/voiceOccupied=false。index.html临时接入后已恢复原摘要aa6c491992a28d7468ce0e2bfea25e919f3429060791556bb4d648b831e55acd并删除静态副本，钩子仅留在该已加载验收页，pagehide自动还原；不可误刷新该页丢失观察器。源码夹具语法核对通过，只是准备证据。前轮正常准备日志实际采样音量/手选/渐变/自动播放四项，未采样动效；相应“全部五项快照”措辞已纠正，不改变既有局部结果。

只读Docker于04:12:55 UTC确认A24/B6隐藏、catalog25/default空、4资产逐项与前轮相同、槽free、活动通话0；新清理门仍为2026-10-22 11:47:52.612573 CST，未重计/删除或新上传。证据020/voice-timing-probe-receipt.json、observer-ready、runtime-pending、input-audit及登录页截图。主页与管理副本均保留为未完成流程交接；未改浏览器全局设置，无待恢复DevTools偏好。当前NO_PROGRESS（新登录依赖第1轮），没有活动上传/编码/通话句柄可验证等待；旧锁屏/文件桥/网络准备阻塞均不沿用。020/021与目标保持进行中且未完成。登录后复用原批次验实际麦克风/输出顺序，结束后正常隐藏并按新时点重算等待门；手机与其他必验分支仍保留。

真实采麦/输出时序与取消实证（2026-10-21 12:23 CST）：正常UI已显示superadmin数据看板，旧登录依赖解除。仅原A启用到目录26，B继续隐藏；旧页复用有效空快照，匿名API确认26后改用新正常主页1849772487（未清用户缓存），实际A playing/原生paused=false。观察器同参数/this/结果委托原生方法，不模拟权限、音频或Provider。两次VoiceEntry原生context.resume及getUserMedia调用入口前，BGM均已blocked(call)/closed=true/intent=pause，既有BGM原生音频paused=true；首次getUserMedia为04:19:19.982 UTC。首通04:19:25.296收到真实connected，随后15次原生AudioBufferSourceNode.start入口BGM仍保持停止；同一context归属可核对。32秒正常挂断后占用解除但仍关闭，38秒后媒体位置仍28.618594，明确播放按钮才重开。再进入通话，UI处于等待接听并提供“取消”时即正常取消，实际记录cancelled/user_cancel、connected_at空/时长0；59秒后仍paused/closed且位置12.824953不变，未自动复播。实际五项偏好均有快照且相同。

只读SQL确认首通81b3b0ac-2fd0-4312-901e-5765bab534b6为用户1 ended/user_hangup/32秒、provider session/dialog存在；第二通1cdbd846-01ae-4c00-8fd2-1f81c1ee7320为用户1 cancelled/user_cancel/未接通。两条call01_fallback=1如实保留，它表示既有CALL-01决策兜底（现行语音API契约），不是runtime technical_fallback同一概念；不冒称所有通话业务决策主路径正常或ASR/听感通过。未读取录音、正文、Provider标识明文或凭据，未改权限、放量、决策/语音配置。真实拒绝权限/连接失败/重连/单轮回复结束及其他目标终端仍待；本轮只给AC-037/039本地Chrome子范围，不将SIM或局部扩大为整条环境通过。

结束后正常隐藏A到catalog27，SQL为A record26/B6均隐藏/default空、4资产与开始前逐项相同、槽free、活动通话0。A新hidden_at=2026-10-21 04:22:12.154660 UTC，B仍03:47:41.187719；整批最早普通精确清理更新为2026-10-22 12:22:12.154660 CST，旧A时间失效，旧封面not_before未变，未删除/上传或建自动化。主页源码恢复原aa6c491992a28d7468ce0e2bfea25e919f3429060791556bb4d648b831e55acd、静态观察脚本移除，关闭本轮2480/2487/2483三个自有标签（钩子随页释放），原AI测试工具用户标签保留；没有全局浏览器设置待还原。原生时序/挂断/取消日志及截图、最终runtime、精确归属/等待记录见020/voice-timing-live-check.json及同前缀证据。旧pending与首空目录文件为历史，不当作当前阻塞。本轮PROGRESS、新阻塞计数归零；7/21 VERIFIED、020/021仍IN_PROGRESS，整体未完成。

两阶段原预算串联实证（2026-10-21）：新增tests/test_bgm_staged_budget_runtime.py，在当前部署同digest候选与逐字一致Nginx的internal网络内使用真实ASGI/HTTP、隔离SQLite及lifespan off。六段合法WAV慢传最后一段为110.101秒，110.893秒已完成真实AAC-LC转码（1秒/44.1kHz/目标96kbps、13483字节），之后仅将worker内存储函数替换为无限本地挂起，原SIGALRM/父等待/组终止/锁/所有deadline均未修改。原处理看门狗剩169.231秒；请求总280.165秒经Nginx返回HTTP200持久failed/processing_timeout，120秒接收、180秒处理、300秒原总截止和10秒收尾保留，阶段转换/重放不重置。挂起期间四次核对原结果/公开读/新请求429忙碌，均通过；PID及进程组消失后才见槽free/work空，未发布资产尝试unknown/pending定位保留，远端写0。最终1 passed in282.18s，全部本次容器/网络精确移除并确认absent。证据020/staged-budget-live-check.json、runtime/results/原始日志及运行器快照。

本结果证明实际慢接收→真实AAC→处理看门狗的组合上限/回收子范围；存储挂起为本地故障函数，不能当真实OSS服务挂起、业务库、实际浏览器330秒耗尽、手机或容量通过。实际运行280.165秒，不能写成“已等待完整300秒超时”。既有单独120秒接收/编码、MySQL跨实例、资源/代理大小和浏览器缓存结果按有效范围复用，未因阶段切换重跑；产品代码与运行环境未修改，原测试2+2对象/隐藏门均未操作。SUG-011/012实际采用列同步新范围，其余未验证门保留；020/021仍IN_PROGRESS。

浏览器异常分支恢复点（同轮）：原生站点信息只读确认Chrome localhost:8000麦克风允许/on、剪贴板on，保存voice-failure-permission-before.txt/.png及具体voice-failure-permission-plan.json。拟临时禁止该来源麦克风并在正式拒绝分支后恢复原允许；它跨该来源标签页持续生效，按AGENTS.md配置边界单独请求具体确认，目前未收到决定、未修改任何权限/剪贴板或系统设置。恢复刚关闭自有管理副本的正常菜单操作遇Mac锁定；随后只读标签清单证明副本未恢复，原AI测试工具用户标签保持。最新原生读取再次明确锁屏，手动解锁请求仍待答复；未尝试绕过系统锁。新主页1849772492保留为交接，未接入观察器/启用曲目/发起通话或修改DevTools。Chrome官方Network参考仅用于准备Offline/WebSocket测试方式，没有借文档宣称真实重连通过。

本轮独立长时测试已终态exit0并清理，没有活动测试句柄可继续等；voice-failure-input-audit.json及runtime-followup.json明确已完成的部署证据与仍待输入的浏览器分支。当前整批普通清理门仍2026-10-22 12:22:12.154660 CST，未到期、未删除/上传、未新建自动化或开放网络。原生权限/网络失败、真机与其他必验项仍未完成；本轮PROGRESS不沿用旧阻塞轮数，目标保持active而非完成。

当前恢复依赖复核（2026-10-21，连续第1个无进展goal轮）：前轮真实两阶段预算为PROGRESS并已exit0/精确清理。本轮同一句柄原生读取仍明确Mac锁定，既有麦克风临时禁止/恢复问题未收到决定；标签清单确认仅新主页1849772492保留、原AI测试工具用户标签保持，没有新管理副本。未修改权限/DevTools、启用曲目或发起通话。无活动上传/编码/通话/测试句柄可验证等待，已完成的staged-budget不能当作仍运行；现有有效测试不重复。最后已核业务回执仍A26/B6隐藏/catalog27/4资产，整批2026-10-22 12:22:12.154660 CST门未到，未清理。原已解除的登录、旧锁屏计数不沿用；本项新依赖NO_PROGRESS1，020/021与目标保持active/IN_PROGRESS、未完成。按voice-failure-input-audit.json保留恢复位置；等待原手动解锁、精确权限问题及真机环境答复，不重复提问或新增自动化。

恢复依赖复核（2026-10-21，连续第2个无进展goal轮）：同一句柄最新原生状态仍明确Mac锁定，原麦克风保存权限问题仍无答复；主页2492继续保留，没有更改权限/DevTools或运行新通话。前轮NO_PROGRESS1，本轮NO_PROGRESS2；已终态的长时测试没有重启，无活跃任务句柄可等，24小时清理门未到。原测试与207项引用摘要验证沿用，未以状态整理冒充进展；只更新本次依赖审计及其已知引用摘要，PRD/只读前缀不变。当前仍低于阻塞阈值，目标active、020/021 IN_PROGRESS且未完成，原请求保持待答复，不重复提问。

当前阻塞结算（2026-10-21，连续第3个无进展goal轮）：前两轮均NO_PROGRESS，同一句柄本轮再次明确报告Mac锁定，既有麦克风临时禁止/恢复问题仍未收到答复。主页2492及原AI测试工具用户页仍在；没有恢复新管理副本、启用曲目、修改权限/DevTools或发起通话。已完成长时测试为终态exit0且全部本次资源移除，无活跃上传/编码/测试/通话句柄可验证等待；其余独立实现及可执行受控验证已有有效结果，不重跑制造进展。真实浏览器分支需手动解锁与相应权限决定，手机需实际设备/可访问地址，普通清理尚不足最近隐藏24小时；当前确需用户或外部状态改变。新输入条件已连续3轮，目标及STEP020/021标BLOCKED、未完成；不沿用此前已解除的旧锁屏/登录/文件桥计数。

恢复位置以020/voice-failure-input-audit.json、runtime-followup.json及permission-plan为准：收到用户恢复输入后从新计数0核对原生解锁/明确权限决定，继续尚缺真实权限拒绝/连接失败重连等分支；不把预选项、计划或重复目标消息当作批准。所有有效历史测试与207项索引保留，AC不升格。当前最后业务证据A26/B6隐藏/catalog27/default空/4资产及槽free，整批普通精确清理门2026-10-22 12:22:12.154660 CST仍未到；未删对象、未扩上传额度、未改Bucket/网络开放/语音配置或新增自动化。目标未达成，不以阻塞结算代替完成。


恢复与收尾评估（2026-10-21）：用户手动解锁、正常重登id=1后，取得真实语音两次回复结束保持BGM关闭、Offline/恢复网络后的短暂reconnecting及silence_timeout终态局部证据，详见voice-network-live-check.json（本地留存，未随本次提交；原引用：`execution/evidence/step020/voice-network-live-check.json`）。不能据此宣称成功重连或完整连接失败分支通过；第二次离线创建停留未知结果提示后被中断。用户随后明确要求评估尽快收尾，已停止新测试。只读库确认活动通话0、两曲隐藏、catalog29；A最新隐藏为2026-10-21 13:47:47.997572 CST，整批普通清理门重算至2026-10-22 13:47:47.997572 CST。临时主页源码精确恢复、served脚本已移除；测试前台标签已关闭，最后DevTools设置恢复因工具超时未确认，保留环境收尾项。旧锁屏三轮审计解除并归零；手机/微信、其他未验分支及最终交付取舍尚未获延期决定，保持原要求和未验证状态。

### 9.5 STEP-001 技术采用记录（2026-10-19）

本节是 STEP-001 的交付物，随唯一进度维护；不是第二份实施计划或现行运行契约。`PLANNED` 表示已选技术接入方向、尚无实现；`UNVERIFIED` 表示实际配置、运行或兼容结果未验证。后续负责 STEP 在本节相应行补实际值、环境、证据及日期，不回写 PRD 的建议为用户确认值。

#### 9.5.1 输入复核与现状

- 输入 STEP 文件修改前 SHA256：`cde08acb570f24372c8ba40adfe3c42d4659f4ee269921e7077f33150144ceab`。仅编辑§9；PRD、§1～8、候选、审计与历史文件保持原文。
- 已复核来源：P01、R01～R03、C01～C03、D01、B01～B07、B10～B11、B15～B19、H04、H06；各自摘要与§3.1相同。只复用这些未变化来源对应的原审查结论；没有重验全体85来源，也没有复用 demo 测试为生产证据。
- 静态 AST 读取 `alembic/versions/*.py` 的 revision/down_revision，唯一 head 为 `v9g_memory_diagnostic_001`；没有导入应用或连接数据库。后续新迁移候选 `alembic/versions/v9h_bgm.py` / `v9h_bgm_001`，实施前再次核对 head，不能覆盖其他开发新迁移。
- 当前 `backend/database.py:create_all_tables()` 对受迁移管理表做排除和缺表启动检查。BGM 必须进入相同集合，避免应用启动绕过迁移；模型注册在 `backend/models/__init__.py`，Alembic 使用同一 metadata。
- 已核实真实响应入口为 `backend/schemas/common.py:ApiResponse`、错误常量包为 `backend/constants/__init__.py`；C01 所称 `backend/constants.py` 是旧定位。本轮只记录定位差异，不修改共享契约或现有错误码。
- 现有 `get_db()` 在依赖退出后提交，异常回滚；`log_operation()` 只 flush，不独立提交。BGM 不得依赖“返回成功后才提交”，也不能让拒绝／失败审计跟随业务回滚。
- 现有 Admin 请求工具支持 `Idempotency-Key`、`timeoutMs` 和直接文件 body（既有用途为 FormData）。BGM 原始文件流须定点支持 Blob 与明确 MIME，保留原 401/403、observer 拦截和其他调用；不假定现有文件分支已经完成 BGM 流式上传。
- 现有 OSS 由 `get_oss_access_key_id/secret/endpoint/bucket/cdn_domain()` 提供；朋友圈对象为 `lxm/posts/{post_id}/{seq:02d}.webp`。只复用配置及 SDK 连接方式，不复用图片生成或固定帖子 Key。
- `Dockerfile` 未安装 FFmpeg；Nginx 当前无 BGM 请求体配置，`proxy_buffering off` 是响应缓冲控制。依赖文件只声明版本范围，不证明实际版本。没有读取 `.env`，真实 Bucket、CDN、权限、终端和吞吐均 `UNVERIFIED`。

新增定向核实来源（均现有代码，非新增契约）：

| ID | 路径／用途 | SHA256 |
| --- | --- | --- |
| X01 | `backend/schemas/common.py`／响应包装 | `ed2dd0ae70e041eb3cc410c2a5eb8dad99386fb4fa52d5318344c75d6d703768` |
| X02 | `backend/constants/__init__.py`／错误码真实定义位置 | `54a23a85a808c0b4b1970bd2707cd8e30d1a62da6c5513064cf630e343b2af97` |
| X03 | `backend/models/admin_operation_log.py`／既有审计字段与留存 | `6e44c510356bc347ca2397561b2d9b4eeaa1ac8c5bb20e1de5be74d8028dfc23` |
| X04 | `backend/services/realtime_voice_record_metric_service.py:VoiceRecordMetricRoute/_audit_failure`／路由外层捕获、独立事务参考；不照搬其跳过401的策略 | `37ea053b89e197e1523ca3a91312d4a2e05a75611fd1abe8de1381f4566ed54a` |
| X05 | `backend/tasks/scheduler.py`／现有调度为领域任务，不是可直接投递任意媒体任务的可靠队列 | `d22d13a7550117d6f70bb0548ecafa1d285a6dea21df26dc1341521ef756b32c` |

#### 9.5.2 已确认规则落实检查

下表复核的是技术方向未偏离 P01，不表示运行验收已通过；没有从历史文档继承额外授权。

| PRD决定 | 技术落点及后续证据门 |
| --- | --- |
| D-01 | 独立 HTML 增量接入；桌面 Chrome/macOS Safari 和真实 iPhone Safari/Chrome/微信、Android Chrome/微信均保留；STEP-011/020/021 实测 |
| D-02 | 本地渐变开关默认开，正常播放、恢复、暂停、切歌均经增益层；STEP-009/011 |
| D-03 | 渐变故障允许基本播放降级；音量真实性与零音量静音单独验证，不能用“支持 play”证明增益；STEP-011 |
| D-04 | 五项仅浏览器本地；复用 `lxm_home_motion_enabled`，其余 BGM 偏好单独命名；不建账号偏好表／API；STEP-009/013/014 |
| D-05 | 六类内容／设置页面用共享气泡，主页不重复；STEP-015 |
| D-06 | 允许页无会话时才以自动播放偏好建立意图；暂停／关闭优先；STEP-013 |
| D-07 | `VoiceEntry.prepareCall()` 内完整能力检查之后、首次 `context.resume()` 之前接关闭 hook；可信清理后只解除阻断；STEP-016 |
| D-08 | 管理读 S/O/V，写 S/O，A/T 无访问；沿用实时 Admin JWT/角色与 observer 总闸；STEP-002～008 |
| D-09 | 单目录、事件触发、隐藏等期手动删；不轮询公开目录、不自动到期删；STEP-004/006/007/012 |
| D-10 | 同一现有 Bucket 的 BGM 独立前缀；不扩 Bucket 公共权限、不遍历朋友圈资源；STEP-003/005/006/020 |
| D-11 | Key/资源版本服务端生成；每个产物不可变 Key，内存 URL 不能替代 DB 资源定位；STEP-003/005 |
| D-12 | 当前封面零或一张，静态可选；旧图仅保留为可清理专属资产；STEP-005/006 |
| D-13 | 整图居中裁圆、整体旋转；歌单仅名称和状态；STEP-014/015 |
| D-14 | 内置共用通用黑胶；不在任何曲目资产删除集合中；STEP-014/015/006 |
| D-15 | 封面独立事务与版本；换图不改音频 URL、media_version、检查点或播放意图；STEP-005/012 |
| D-16 | MP3/M4A/AAC/WAV 真解码；源 ≤104857600 字节，0＜时长≤300秒；AAC-LC/M4A 目标96000 bit/s，完整产物≤4194304字节；STEP-003/020 |
| D-17 | 一首当前输出、至多一个无声准备候选；HTTP缓存，不建完整本地媒体库；STEP-010/019/020 |
| D-18 | §9.5.7逐项登记候选、负责STEP、环境、证据；运行结果未取得前不写“已采用并验证” |

#### 9.5.3 文件、数据与事务接入（均 PLANNED）

| 位置／符号 | 职责与最小字段／约束 | 负责STEP |
| --- | --- | --- |
| `backend/models/bgm.py:BgmTrack` / `bgm_track` | `id`、规范化名称、`record_version`、`audio_state`、`enabled`、`sort_position`、`ever_published`、`hidden_at`、`audio_asset_id`、`cover_asset_id`、`media_version`、`cover_version`、时长／大小、UTC时间；删除状态不可发布，处理状态与启用分离 | 002建基座；003～006落行为 |
| `BgmCatalog` / `bgm_catalog` | 单行 `id=1`、单调 `catalog_version`、可空 `default_track_id`；事务锁顺序：catalog → track（多曲按ID排序）→ operation/asset；排序、默认、启用和公开封面变更原子提交 | 002/004/005/007 |
| `BgmOperation` / `bgm_operation` | 客户端预生成 `operation_id` 为唯一键；操作者、动作、曲目、规范化请求摘要、文件SHA256/长度、期望版本、attempt、owner、截止时间、状态、结果快照／安全错误类别；同ID不得换内容或操作者；保留去重墓碑 | 002/003/005/006 |
| `BgmAsset` / `bgm_asset` | `id`、track/op/attempt归属、audio/cover类别、bucket/key、独立version、SHA256、MIME/大小、校验／关联／清理状态、`retired_at/not_before`；Key唯一，当前图与旧图分开定位 | 002/003/005/006 |
| `BgmProcessingSlot` / `bgm_processing_slot` | 固定数量接纳槽；owner实例／代次、operation、attempt、租约／deadline、排空状态。接收、解码、OSS写入和清理占用有界；不创建等待队列 | 002基座/003执行 |
| `backend/schemas/bgm.py`；`backend/routers/admin/bgm.py`；`backend/routers/bgm.py` | 管理／公开 DTO 分开；公开仅白名单字段，管理不回传临时路径或凭据；沿用 ApiResponse，管理分页 `list/total/page/page_size`，资源标识 `id` | 002～007 |
| `backend/services/bgm_service.py`；`bgm_operation_service.py`；`bgm_media_service.py`；`bgm_asset_service.py`；`bgm_runtime.py` | 分别负责原子目录、持久操作、受限媒体、精确归属资产、进程及过期恢复；重活隔离执行，主事件循环不做同步转码／OSS调用 | 003～007 |
| `backend/services/bgm_audit_service.py:BgmAuditRoute`；`backend/utils/admin_auth.py`限定接点 | 依赖前外围捕获与安全身份快照；复用现有日志表，不改全局授权结果 | 002/008 |
| `backend/constants/bgm.py`；`backend/constants/__init__.py` | 确认规格与候选配置分别定义；`ADMIN_ERR_BGM_*`登记输入、版本冲突、幂等冲突、过大、忙碌、未找到、处理失败、暂不可用、结果待核对类别；数字在实施时查重分配，本轮不占号 | 002/003/007 |
| `admin/pages/bgm.html`；`admin/static/js/bgm-admin.js`；`admin/static/css/bgm-admin.css` | 单管理页；菜单/直链先做S/O/V守卫，再请求授权数据；复用既有observer标记和请求处理；后续才接写操作、试听 | 002～008 |
| `frontend/static/js/bgm-{preferences,controller,audio,catalog,lifecycle,ui,preload}.js`；`frontend/static/css/bgm.css`；`frontend/static/images/bgm/default-record.svg` | 按后续STEP分离本地设置、意图、输出、目录、页面/声音生命周期、展示、单候选准备；默认图为静态通用黑胶，非每曲复制 | 009～019 |
| `tests/test_bgm_*.py`、`tests/test_bgm_*.cjs`（具体文件随负责STEP） | 依据BR/AC写定点测试；模拟与真实MySQL/API/媒体/终端证据分开 | 002～021 |

表字段、类型和索引由负责 STEP 在既定语义内具体化；不在 STEP-001 建空表／占位 API。ID 用服务端曲目 UUID 和客户端操作 UUID，业务版本用整数；对外 id 为字符串，UTC时间按现有响应规范。操作结果保存原提交版本，重放不伪装为最新目录。

目录写入在同一事务中锁 catalog、校验期望目录/记录版本和完整有效ID集合、更新曲目/顺序/默认、递增版本、保存操作结果和成功审计，再显式 commit。就绪未启用、隐藏、删除中不出现在公开目录；非空目录恰好一个有效默认。读取一份一致数据库快照后整体缓存，不能拼接不同版本。提交后失效 Redis 失败仅标记缓存待过期，不把已提交操作返回为未写入。

后台读取与公共目录各用最小DTO。GET/HEAD 不修复逾期任务、不插入幂等记录、不转码、不清理；仅公共目录允许从权威读结果派生有限TTL缓存。后续实际增加接口/模型时同步必要当前契约及 manifest；本轮无运行契约增量。

#### 9.5.4 路由与提交协议（PLANNED）

| 方法与路径 | 采用协议／权限 |
| --- | --- |
| `GET /api/bgm/catalog` | 不使用用户鉴权依赖，客户端显式不附 Authorization；完整 `catalog_version/default_track_id/tracks`，每曲 `id/name/media_version/audio_url/duration_seconds/cover_url/cover_version` |
| `GET /api/admin/bgm/tracks`、`/tracks/{id}`、`/operations/{operation_id}` | S/O/V可读；有界分页／状态快照；不存在与处理中/结果待核对明确区分，不把一次未找到当作可另建素材 |
| `POST /api/admin/bgm/operations` | S/O先提交小型JSON操作清单，支持音频新建/已知失败重试/封面上传准备；含操作ID、动作、规范化名称、文件摘要/长度、目标及期望版本；持久接纳成功后才允许传字节 |
| `PUT /api/admin/bgm/operations/{operation_id}/content` | 同一操作者重新授权；原始文件body流式接收，按清单计数并复算摘要；不经过自动 multipart 全包解析；音频和封面各有独立操作和限制 |
| `PATCH /api/admin/bgm/tracks/{id}` | 显式 rename/enable/hide/set_default 动作，必要替代默认ID、期望版本和幂等ID；拒绝客户端指定Key/处理成功/时间 |
| `PUT /api/admin/bgm/order` | 完整有效启用ID排列＋目录版本＋幂等ID；不接受局部覆盖 |
| `DELETE /api/admin/bgm/tracks/{id}/cover` | 保存空关联，再按归属/等待条件处理旧图；返回关联已移除与旧图清理状态两部分 |
| `DELETE /api/admin/bgm/tracks/{id}` | 复核等待期及无活动执行，先提交不可发布态，再逐对象清理；失败重试仍引用同曲目和原资产集合 |
| `POST /api/admin/bgm/tracks/{id}/cleanup-retry` | 仅手动重试已明确失败或已到可清理时点的专属残留；重新授权与校验；不能用它绕过删曲等待期 |

管理业务失败使用现行 `ApiResponse`（正常业务HTTP 200）；鉴权401/403保持，422/代理413/网络中断由现有请求层兼容。公开目录不可用给可识别错误，不触发登录弹窗；数值错误码待实施查重。轮询操作状态限于用户发起的后台操作跟踪，不变成用户端目录轮询。

客户端先生成操作 UUID、计算文件SHA256和规范化请求清单，将ID及清单保存至管理端 sessionStorage（不保存文件内容），再提交准备请求；保存失败明确阻止可恢复上传，保留输入提示重试。服务端以唯一ID和请求摘要原子去重：同操作者同内容返回原结果/状态，不再次建曲或处理；异内容冲突。提交响应丢失先查同ID，允许原ID同清单重放准备；不能生成新ID猜测原请求未发生。

content 一次被某 attempt 接纳后，重复传输只返回原状态，不启动第二执行；中断先核对操作，明确失败后才允许管理员发起新操作并关联原 track，递增 attempt。新文件重试更新清单摘要；不是篡改旧操作。所有重放／重试重新验证当前角色。新音频操作先完成，选填封面随后独立提交；界面分别反馈音频就绪与封面失败，成功音频无需重传。音频原位替换仍不支持。

#### 9.5.5 有界处理、资产归属与补偿（PLANNED）

方案比较：单个自动解析 multipart 的长请求易把大体积接收放到业务接纳之前；现有 APScheduler 和内存 create_task 也不等于可靠上传队列。采用“小清单持久接纳＋独立原始流接收＋受监督隔离执行”的受限请求方案，复用现有应用 lifespan 管理和 MySQL，不增加队列服务或任务平台。HTTP连接断开后已接收完成的执行仍在原期限内收尾；未收完只能失败并核对，不能假装字节已收到。

1. **全部署接纳**：数据库预建固定槽，候选并发1；清单接纳事务先抢槽再分配 track/attempt。无槽立即返回忙碌，不排队；音频、封面及有外部I/O的清理共用有界接纳。只读和轻量目录写入不占转码槽。Redis故障不放大并发，DB不可用不接纳重活。
2. **一个期限**：候选从服务端接纳时起总300秒、接收最多120秒、接收后处理最多180秒、其中转码最多120秒。各阶段 deadline 取自身上限与原总期限的较小者；探测、校验、OSS写读、提交和收尾均扣剩余预算。处理阶段预留至少10秒收尾，转码不可吃满剩余预算；不足则明确失败。源音频最长300秒是另一项业务规格。
3. **接收与执行**：只在 BGM content 路由关闭 Nginx 请求缓冲，使用HTTP/1.1、明确请求大小和应用流式读取的绝对deadline；客户端从准备至结果等待也有总限。原始音频body上限100 MiB，封面候选5 MiB，JSON清单另设小上限；没有“合法音频＋封面被100 MiB总限挡住”的合并冲突。Content-Length仅辅助，实际字节计数和摘要最终权威；超限立即停止接收。
4. **终止与占用**：媒体/同步SDK在受监督子进程执行，限制CPU/内存/临时空间，父进程记录owner及进程组。deadline或取消先使attempt不可提交，再终止并确认子进程组退出、回收临时文件，最后释放槽。只取消 async task／线程不算终止。owner死亡后由启动恢复核对；租约到期不等于旧进程已死，无法证明停止时槽保持不可接纳并给“清理待核对”，不能冒险让新实例超并发。具体资源上限由STEP-003/020测量后登记。
5. **失效与恢复**：提交必须同时满足当前track/attempt/owner/未到deadline/非删除态；旧执行迟到最多留下已登记资产，不能变ready。lifespan的有界恢复只扫描BGM过期操作/槽，终结为失败或待核对，不自动重转码、不处理正常到期可删歌曲。仍活跃的另一实例不能被本机清理；未知owner要先确认死亡或由运维核对，GET始终只读。
6. **音频验证**：受限本地文件输入，ffprobe真实容器/音轨检查＋完整解码；拒绝伪格式、损坏、0/超长/超大。FFmpeg候选使用AAC-LC、96k、单声道保留/多声道最多2、44.1kHz、faststart，只映射音频，去内嵌图/视频/无关metadata。产物重新探测、解码和计数；不得截断至4 MiB或裁掉超长部分来伪造合规。300秒×96000/8=3600000字节只是音频载荷估算，封装后实际文件仍要≤4194304字节。
7. **资源先登记后外写**：候选Key `bgm/tracks/{track_id}/{media_version}.m4a`、`bgm/covers/{track_id}/{cover_version}.webp`。上传前独立提交asset归属/目标Key/摘要；OSS成功而DB提交失败时可按原Key核对，禁止换Key盲重传。远端检查成功才原子关联为就绪，仍未启用；访问URL仅由现有HTTPS CDN配置构造。
8. **封面与旧图**：真实静态图片解码、有限像素/字节；新图写读验证后锁曲目与必要catalog并校验版本，切换成功才退役旧关联。冲突/失败保留旧图，已写新对象进入同曲目残留。候选旧图回收时点为退役后采用的隐藏等待期（暂24小时）；下一次管理员封面维护、明确cleanup-retry或删曲时只清理到期且不再引用的精确Key，无到期自动删除。HTTP缓存可继续存在，不承诺召回；未被后续操作触发的旧图保留可查询的归属与待清理状态。
9. **删除闭环**：先锁曲目核当前服务端UTC资格，置删除中使全部旧attempt不能发布，再按asset表精确删除该曲全部专属音频/当前旧封面/残留；不存在算成功，失败逐项留原因与Key定位。全部完成后最小操作/曲目墓碑继续去重，普通列表排除。共享默认图、`lxm/posts/`及非本曲归属对象永不加入清理集合；不调用Bucket全量遍历删除。

真实多进程/跨实例接纳、慢上传、合法边界文件、断连/崩溃、旧attempt迟到、子进程难退出、OSS先成功与DB失败、删除部分失败均由STEP-003/005/006验证，STEP-020在实际部署配置复核。候选10秒收尾、1并发、300秒预算均未实测；若不能安全终止或有合法边界必然失败，调整技术候选并记录，不放宽已确认媒体规格。

依据：Nginx 请求缓冲默认先接收完整body；`client_body_timeout`只限制相邻读取间隔，不能代替绝对期限。见[请求缓冲](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_request_buffering)、[请求体超时](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_body_timeout)。FFmpeg的AAC码率选项以bit/s设置，见[AAC参数](https://ffmpeg.org/ffmpeg-codecs.html#aac)。2026-10-19查阅的官方资料只支撑设计判断，不代表本项目安装版本或运行通过。

#### 9.5.6 鉴权拒绝审计与音频能力策略（PLANNED）

**审计**：BGM专用 `BgmAuditRoute` 在依赖求解前开启范围标记，捕获401/403/422及业务失败，不先读文件body。`get_current_admin()` 在JWT签名/类型校验并查到真实账号后，为BGM标记请求保存最小身份快照；可记录被禁用、锁定或token_version已撤销的真实账号，但绝不因此授权；observer总闸仍在业务处理器之前拒绝。`require_role()` 的A/T拒绝由同一外围捕获。无可信身份时审计 `admin_user_id=NULL`、固定未认证名称，不信任客户端角色、未验证sub或伪造用户名。

成功变更的审计与业务事务一起提交；明确失败/拒绝在业务回滚之后用独立 `async_session_maker` 写现有 `admin_operation_logs` 并commit。使用 `module=bgm`，action控制在既有20字符长度，结果载荷仅角色/actor、动作、对象/操作ID、版本、安全失败类别、时间；复用脱敏，不记录Token、文件二进制、源临时路径、凭据或原始异常SQL。相同操作业务结果不重复写成功副作用，重复HTTP拒绝可用服务端request_id追踪。日志库不可用时仍拒绝权限，不放宽、不伪报已留审计；通过既有应用日志输出无敏感信息的故障标记，测试必须暴露缺证据。正常GET不新增操作记录或触发恢复。STEP-002覆盖observer/A/T/撤权等独立落库，STEP-008接完整动作与过滤。

**输出与生命周期**：BGM自己拥有HTMLAudioElement与AudioContext，不借用VoiceAudioTransport；同文档仅一个可输出当前曲。优先MediaElementSource→GainNode处理相对音量/渐变/短TTS衰减，真实CORS和输出测试通过才认定此路径可用；无法可靠增益时按PRD降级为基本播放及设备音量提示，零音量仍需硬静音。所有异步play/seek/目录/封面/预加载结果核对当前意图代次；暂停、关闭、隐藏、通话优先取消过期动作。

通话hook放在已核实的 `prepareCall()` 能力检查之后、`context.resume()`和`getUserMedia()`之前；登录/忙碌/能力检查拒绝不关闭音乐。开始真实准备后置本次关闭；拒麦/取消/失败仍关闭。结束须结合本次媒体资源释放与可信远端终态/清理确认，不能用 `busy=false`、弹窗消失或listening事件解除阻断。短TTS只提供活动token接口和允许的受控模拟，不新增业务。下一首准备使用独立无声媒体候选、候选不调用play，切歌仍重新核资格；只换封面不重建音频。

#### 9.5.7 建议参数登记

候选列保留2026-10-19的建议与来源，不作为强制规格。实际采用列按负责STEP的证据持续回填，2026-10-20汇总如下；局部采用/通过不代表全部目标终端或DEP验收完成。AC列仅列受该参数直接影响的条款，最终完整核对仍归STEP-021。

| SUG | 候选值／方式及依据 | 负责STEP | 验证环境及所需证据 | 影响AC | 实际采用值／证据状态 |
| --- | --- | --- | --- | --- | --- |
| SUG-001 | 0.5秒/段，P01建议；紧急阻断不等待渐变 | 011/021 | H5-M/H5-D真实输出及快速反向意图；SIM时序 | 023/024/026/100 | 2026-10-20采用每段0.5秒；§9.16/22/23的SIM及Chrome真实增益验证通过；H5-M/Safari待验 |
| SUG-002 | 12秒/圈、250ms缩放、400ms面板、40%～50%视口；唱片倍率候选1.18（保持确认区间） | 014/015/021 | 小屏/键盘/减少动态/焦点/遮挡实际UI | 003/004/005/010/011/013/080/082/100 | 2026-10-20采用12秒圈、250ms缩放、400ms面板、倍率1.18；§9.19/20本地Chrome验证；真机键盘/安全区待补 |
| SUG-003 | 20px/s、端点停1秒，P01建议 | 014/021 | 长中文/emoji/组合字符、动态关闭可读性 | 005/100 | 2026-10-20采用20px/s、两端1秒；§9.19实际长名/减少动态验证；目标终端待验 |
| SUG-004 | 用户增益×0.25，不修改长期音量 | 017/021 | SIM重叠活动token；真实输出可控短TTS衰减 | 041/042/100 | §9.22采用0.25，SIM/Chrome客观输出通过；H5-M能力和主观听感待验 |
| SUG-005 | 每2秒检查点＋关键动作即时保存 | 013/021 | H5-M/H5-D跨HTML、BFCache、存储失败与合法进度恢复 | 031/032/033/034/044/100 | 2026-10-20采用2000ms，SIM/真实Chrome导航检查点通过；§9.18；H5-M/Safari待验 |
| SUG-006 | 新鲜300秒／故障旧目录最长1800秒 | 012/021 | SIM时钟倒退/失败不续期；API事件请求/跨文档时间 | 046/047/048/050/051/052/100 | 2026-10-20采用并通过SIM/Chrome边界；§9.17；H5-M/Safari待验 |
| SUG-007 | Redis TTL60秒；写后失效、回源在途合并/有限并发 | 007/020/021 | API真实Redis失败/提交失效失败/一致快照/回源计数 | 045/053/060/100 | 2026-10-20采用Redis60秒、本地1秒及在途合并；§9.13隔离Redis/MySQL/Chrome通过；实际DEP故障待020 |
| SUG-008 | 总30秒、最多3个不同候选、单曲最多15秒 | 012/021 | SIM共享截止时间/失败链耗尽与人工恢复 | 028/029/030/050/051/052/100 | 2026-10-20采用并通过SIM/Chrome边界；§9.17；H5-M/Safari待验 |
| SUG-009 | 目录8秒、自动重试1次、退避1秒、强刷1次、失败冷却30秒 | 012/021 | SIM慢请求/同时触发/权限拦截不换歌；冷却结束不请求 | 046/048/050/051/052/100 | 2026-10-20采用并通过SIM/Chrome边界；§9.17；H5-M/Safari待验 |
| SUG-010 | §9.5.4～5分阶段受限请求；持久操作＋隔离执行，不新增任务平台 | 003/020/021 | API/DEP断连刷新查原操作、收尾和受限接纳 | 055/066/067/071/072/073/074/100 | 2026-10-20采用持久JSON清单+raw字节请求+隔离worker；§9.7/9.9/9.12受控链及020正式2音频/2封面上传处理已证；整条目标终端/等期清理闭环仍待。 |
| SUG-011 | 全部署并发1；接收120/处理180/总300秒，转码≤120；处理内预留10秒收尾（研发候选） | 003/020/021 | DEP多实例、慢流、杀进程、旧owner迟到、峰值资源 | 069/071/072/073/074/100 | 采用全库1槽、接收120/处理180/总300秒、转码≤120、预留10秒；既有Linux资源/120秒接收编码/MySQL多实例通过，020新增真实慢接收110秒→AAC→本地存储挂起，原169秒worker看门狗下总280.165秒失败回收；真实OSS/完整目标DEP仍待。 |
| SUG-012 | 代理310秒、前端330秒；适用分阶段请求，前端统一剩余预算 | 003/020/021 | DEP实际代理计时、无缓冲、100MiB合法边界及异常中断 | 069/071/072/074/100 | 采用proxy_read310秒、前端330秒；020真实Nginx100MiB/分块、120秒接收及两阶段110秒慢传+原处理看门狗280.165秒响应已证；原deadline未重置。真实浏览器330秒耗尽/OSS真实挂起仍待。 |
| SUG-013 | trim后1～60 Unicode码点；拒控制字符、重复名合法 | 003/004/021 | API/前端同边界，emoji/组合字符/空白/纯文本输出 | 056/057/066/100 | 2026-10-20采用trim后1～60 Unicode码点，拒控制字符；003/004 API与Chrome边界通过 |
| SUG-014 | FFmpeg/ffprobe；44.1kHz、保留mono/最多stereo、faststart | 003/011/020/021 | 真实产物probe、完整解码/4MiB检查、听感与目标浏览器 | 068/069/070/074/075/100 | 2026-10-20采用AAC-LC目标96000bps、44.1kHz、保留mono/最多stereo、faststart；003真实媒体与020候选FFmpeg7.1.5通过；目标终端/听感待补 |
| SUG-015 | 最近隐藏后24小时；旧封面回收候选复用24小时 | 006/020/021 | API服务端UTC边界、重启再隐藏、当前引用保护 | 063/064/065/090/091/100 | 采用服务器UTC86400秒；§9.12受控边界/重启用/引用保护及020实际重隐藏记录齐全；本轮真实语音后A26/B6隐藏/catalog27，整批最早2026-10-22 12:22:12.154660 CST；到期普通删除待执行。 |
| SUG-016 | 静态JPG/PNG/WebP，≤5MiB、长边≤4096px；动图拒绝 | 005/020/021 | 真图/伪图/截断/多帧/解码像素预算、分离上传 | 086/087/088/100 | 2026-10-20采用静态JPG/PNG/WebP、≤5MiB/4096px；§9.9真图/伪图/多帧/完整SDK链通过 |
| SUG-017 | 标准化512×512 WebP，≤200KiB仅优化目标，不作固定拒绝门 | 005/014/021 | 真实图片产物、圆形居中展示、失败保旧图 | 080/081/087/088/100 | 2026-10-20采用512×512 WebP、质量85→75→65；200KiB只优化目标；005/014真实产物/Chrome通过，目标终端待验 |
| SUG-018 | 剩余20秒考虑单候选metadata准备；demo8秒不自动继承 | 019/020/021 | H5-M/H5-D真实网络、弱网/省流量跳过、取消、当前播放优先 | 092/093/094/095/096/098/100 | 采用剩余≤min(20秒,曲长四分之一)、单metadata候选、5秒预算；§9.24 SIM/Chrome通过，020正式Chrome/Fast4G实际A22.85秒准备唯一B且自然切歌、3g跳过已证；长歌单/H5-M/Safari准备完整范围待验。 |
| SUG-019 | 版本URL成功资源30天＋候选immutable；目录不得长缓存 | 020/021 | CDN/HTTP实际MIME/Range/CORS/缓存头、重复URL/错误响应 | 075/076/085/097/098/099/100 | 配置采用版本资源30天immutable；020真实两来源HTTP200/206/304/CORS及Chrome磁盘缓存/封面304、Safari重复网络206/封面200均已留证。允许未命中重新请求；手机/真实缓存回收/正式完整流程仍待，不承诺零下载。 |
| SUG-020 | §9.5.3～4实际选定命名方向；`bgm/tracks/`与`bgm/covers/` | 002/003/005/007/020/021 | schema/API查重、隔离Bucket前缀/真实域名核验 | 045/054/066/073/085/086/100 | 已采用数据/API命名及bgm/tracks、bgm/covers；002～007和两次获准单对象精确测试通过；020正式2音频/2封面Key/真实域名/版本与归属齐全，上传预算0；目标终端及满期清理仍待。 |
| SUG-021 | §9.5.5第8～9项：退役时间＋等待门、管理员显式触发、精确归属/残留 | 005/006/020/021 | API/OSS已换图/移除/部分失败/重复清理与默认图保护 | 088/089/090/091/100 | 采用退役后86400秒、显式清理、精确归属/剩余手动重试；005/006受控SDK/API通过；实际发布后等待清理待020/021 |

#### 9.5.8 STEP-001 验证记录与交付边界

本STEP的AC-100子条款以文档/配置审阅为环境，不要求提前取得STEP-011/020/021的真实运行证据；那些门槛仍有效。候选时限、依赖版本及可终止隔离执行必须在后续实测；此处不标功能AC通过。

| 证据ID | 要求—实现—核验 | 结果 |
| --- | --- | --- |
| E001-SOURCE | 当前依赖不漂移：按§3.1精确路径计算本次来源SHA256；AST核唯一迁移head；新增来源X01～05有独立摘要 | PASS：24/24原依赖＋5/5新增来源匹配；静态唯一head仍为v9g，无DB连接 |
| E001-NORMAL | AC-100正常：§9.5.2有D-01～18逐条落点；§9.5.7有SUG-001～021逐条候选、负责STEP、环境、影响AC与待验证状态 | PASS：D 18/18、SUG 21/21完整且无重复；各行六列非空，实际状态均UNVERIFIED |
| E001-BOUNDARY | AC-100边界：确认值不变；部署/CDN/设备/容量均UNVERIFIED；仅完成技术记录，接口/代码仍PLANNED | PASS：PRD摘要不变，确认媒体规格逐项保留；所有运行验证明确归后续STEP |
| E001-BUDGET | AC-100异常：120+180=300；后续阶段取剩余预算，转码保留收尾；8+1+8+15=32＞30说明必须共享deadline；100MiB音频与5MiB候选封面分离；96000×300/8=3600000＜4194304只是估算 | PASS：Python算术与人工路径核对；不是转码产物／上传容量实测 |
| E001-SCOPE | 仅§9变更；保留§1～8、PRD、既有代码及用户改动；无迁移、部署、OSS写入、业务功能测试；现行契约增量为零 | PASS：与修改前内存/临时副本逐字比对§1～8一致，21项进度保留；只写本文件§9 |

核验时间：2026-10-19 15:16 CST；环境：当前macOS工作区、系统 `python3` 标准库，无应用导入/服务调用。实际操作为 `python3 - <<'PY'` 临时脚本：从§3.1提取本项24路径并计算SHA256，与登记值逐项assert；新增5路径同样assert；分别提取§9.5.2/9.5.7首列比对完整D/SUG序列，校验SUG六列非空和UNVERIFIED；比对修改前§1～8与PRD摘要，核对21进度行及上述算术，全部assert通过。唯一head另以AST读取所有当前迁移声明计算差集核验。临时副本不是新进度源；后续复核以本文件登记的来源摘要和记录为准。

实施时不将 `UNVERIFIED` 自动改成通过；后续新增路径、字段或候选调整按原STEP的实际实现证据更新。未运行全量pytest和浏览器套件，因为本STEP没有业务代码变更；这不代表它们通过。没有里程碑计划，本次不生成GATE交接状态。

### 9.6 STEP-002 实施与验证（2026-10-19）

**结果：VERIFIED，仅本STEP的AC-054/055子条款。** 一个管理页、三个只读GET、五表数据基座及共用拒绝审计已实现；没有上传、发布、封面维护、删除或试听功能结论。模型/迁移和界面存在于工作区，不代表运行环境生效。

| 证据 | 要求—实现—实际验证 | 结论 |
|---|---|---|
| E002-API | AC-054菜单/页面/读取权限：三个GET均复用真实JWT、DB实时角色；隔离SQLite+ASGI对S/O/V成功、A/T拒绝、匿名/撤权拒绝逐项断言 | PASS |
| E002-READ | AC-055读取无副作用：过期processing操作只返回状态；未创建catalog；无业务版本或日志变化；23条真实隔离记录分页、字面搜索及deleted隐藏，非法分页/枚举422；DTO不泄漏内部快照 | PASS |
| E002-AUDIT | AC-054/055共用提交边界：隔离测试路由复用生产BgmAuditRoute/require_role，observer总闸、A/T和禁用/锁定/token撤销/降级拒绝；处理器flush后409回滚，拒绝日志独立保留；无可信token不认输入身份 | PASS；测试路由不注册生产，实际业务写入口在后续STEP验证 |
| E002-SCHEMA | 五模型已注册，当前唯一静态迁移head为v9h_bgm_001；冻结MySQL DDL与模型匹配、只seed两单例；create_all排除并缺表报迁移 | PASS；静态检查及隔离SQLite建表，未执行MySQL迁移 |
| E002-UI | Chrome 155.0.8059.80加载实际HTML/JS/CSS，受控读取API；五角色直访/菜单、详情/操作查询、XSS名称作为文本、observer筛选可用；390px侧栏/内容和Escape复验，桌面/小屏截图人工检查 | PASS；非真实手机/部署API/音频/OSS验收 |
| E002-REGRESSION | 原认证、日志脱敏、前端observer共用逻辑，当前代码运行80项 | PASS，80 passed，34.35s；98个既有JWT短测试密钥告警 |
| E002-INVENTORY | 改动前记录45页面、229 Admin路由（105读/124写），原三套清单9失败/3通过；本轮只加BGM一页面、三GET对应断言，保留权限断言，改动后仍同9失败/3通过，实际46页面、232路由（108读/124写） | 无新增失败；既有页数/路由数/语音角色与导出清单漂移未修，不能称全仓通过 |
| E002-CONTRACT | 新增BGM api/data/admin-ui现行契约，索引/manifest、共享权限与20200错误增量、代码面3路由/5模型/1页面归属；定向现行链接及BGM/main覆盖核对；PRD SHA及§1～8逐字保持 | PASS；全局覆盖检查另发现既有system_monitor/memory_mgmt行号及带Mixin模型扫描差异，未修无关范围、未读迁移基线 |

运行命令：

- `.venv-step001/bin/python -m pytest -q -p no:cacheprovider tests/test_bgm_admin_access.py tests/test_bgm_schema.py`：21 passed；最终与三套inventory同跑24 passed/9 failed，其中BGM 21项全部通过，失败ID与实施前相同。
- `MEMORY_RUNTIME_ENVIRONMENT_ID='' .venv-step001/bin/python -m pytest -q -p no:cacheprovider tests/test_admin_auth.py tests/test_step012_operation_log_redaction.py tests/test_step029_observer_frontend_common.py`：80 passed。隔离用例不继承本地部署memory epoch；未改业务环境门禁。
- `HOME_PLAYWRIGHT_PATH=<bundled-node_modules>/playwright <bundled-node>/node tests/test_bgm_admin_browser.cjs`：五角色PASS；本地Chrome/localhost因沙箱网络限制在自动审查允许后执行，未连接外部业务服务。
- 定向Python调用文档检查器的代码面/链接函数并限制比较BGM+main；未运行会读取迁移基线的完整文档迁移核验。PRD摘要仍为`f035f197266bb8fa936bbc33ca658762a99a3efef9fd321b7bbb24a64a029c04`。

证据在step002（本地留存，未随本次提交；原引用：`execution/evidence/step002/`）：`browser-results.json`、`observer-desktop.png`、`observer-small.png`、`regression.txt`、`inventory-before.txt`、`tests-and-inventory-after.txt`、`source-sha256.json`。摘要文件列出本STEP所有实际变更路径及当时SHA256，是证据而非第二进度源。先红测试已确认新路由404，随后实现转绿；首次小屏检查发现侧栏挤压，局部修正后重新截图与断言通过。

实际变更：新增`backend/{models,schemas,constants}/bgm.py`、`backend/routers/admin/bgm.py`、`backend/services/bgm_service.py`/`bgm_audit_service.py`、`alembic/versions/v9h_bgm.py`；接入模型注册、启动缺表检查、路由、错误码、鉴权可信actor快照；新增`admin/pages/bgm.html`与专用JS/CSS，菜单按S/O/V；新增三项测试文件并只更新旧清单的BGM增量；正式契约与路由文件按上表同步。未覆盖用户既有修改。

来源变化：开始时17项直接来源摘要一致；B01/B02/B06/B07/B12/B13/B14/B15/C01/C02/R02/R03由本轮实现发生有据变化，见摘要证据。新增表/路由/页面从PLANNED转IMPLEMENTED并有本项验证，媒体与部署参数仍UNVERIFIED。SUG-020仅数据/API命名部分采用；任何24小时显示值仍为待STEP-006验证候选，不代表删除入口已实现。

### 9.7 STEP-003 实施与验证（2026-10-19）

**结果：VERIFIED，限本STEP各AC子条款。** 音频接纳、真实媒体处理、持久操作恢复、受限跨进程执行及管理端试听已实现。就绪始终未启用；STEP-004尚未完成，不能据此将整条AC-066或整个BGM功能计完成。工作区代码未部署、业务库未迁移。

| 证据 | 要求—实现—实际验证 | 结果 |
|---|---|---|
| E003-API | AC-054/055/056/062/066：真实JWT+隔离SQLite/ASGI，新POST/PUT使用S/O写权限，V/A/T拒绝；非法额外状态/路径、名称、大小/摘要拒绝；同操作重放不建新曲，异内容冲突；准备、接收及完成重核实时权限；就绪未启用/catalog不变 | PASS；backend.txt 45 passed（含STEP-002相关21项），后增recovery-final.txt 8 passed |
| E003-MEDIA | AC-067/068/069：隔离Linux FFmpeg 7.1.5真实MP3/M4A/AAC/WAV处理；真实格式/损坏/类型、0/300/>300秒与产物4MiB边界；清除附件；探测AAC-LC/44.1kHz/mono或stereo、完整解码及faststart；完整100MiB合法WAV流经API/worker/OSS SDK成功，100MiB+1拒绝 | PASS；media-integration.txt 27 passed，包含18媒体、6全链及当时3进程用例；本地HTTPS对象夹具不等于真实OSS |
| E003-CONCURRENCY | AC-070：专属临时MySQL8执行冻结迁移；独立连接、两个engine、四个独立OS进程共享一行锁，恰一接纳其余明确忙碌；同id并发只一曲/操作 | PASS；mysql.txt 4 passed；未连接业务库，实际部署主业务容量仍归STEP-020 |
| E003-RECOVERY | AC-071/072/073/074：原操作可查；慢流按原deadline失败；处理扣已用时间及10秒收尾；原失败重选关联原曲；旧attempt迟到不能覆盖/损坏新尝试；GET不恢复，生命周期按原memory epoch恢复；活锁不删，异机无死亡证明隔离名额 | PASS；recovery-final.txt 8 passed；真实时间缩短故障注入，不声称已做生产300秒慢网实验 |
| E003-PROCESS | AC-070/074：真实隔离子进程deadline、worker SIGKILL、Linux API父进程SIGKILL；decoder退出后才能取得继承锁；数据库结果未知时保留无源owner凭据；CPU/内存/文件/FD上限与独立墙钟定时器 | PASS；parent-death.txt 4 passed；最严进程故障在Linux容器验证，不以async取消代替进程死亡 |
| E003-PARTIAL | AC-062/073：SDK PUT失败、公开GET失败、远端成功后SQL提交丢响应；同Key核对、对象先登记、持久成功不改失败；失败资产留原track/op/attempt定位。浏览器透明PUT重发同文件复用终态、异文件冲突 | PASS；pipeline全链6项及recovery相关项；实际删除补偿入口留STEP-006 |
| E003-OSS | AC-086及音频写读：用户明确允许一个50,023字节/4秒测试对象上传、HTTPS读回及精确清理。使用真实现有Bucket/CDN配置和生产put_and_verify；完整摘要一致后删除，源站object_exists=false | PASS；oss-smoke-plan.json状态verified_and_cleaned、remote_verified=true、cleanup_confirmed=true；仅登记的bgm/tracks/147bd9f2-de51-4014-9d1c-acec748df429/前缀，未改权限、朋友圈对象或业务库 |
| E003-UI | AC-054/056/057/062/066：实际HTML/JS/CSS、Chrome155与实际转码AAC，真实play/currentTime；一audio切换/离页停；observer可试听无写入口；60码点边界、存储失败不提交、发送前已存凭据、504后刷新查询原id、403保留待核对；390px弹窗边界和控件可达 | PASS；upload-browser-results.json、upload-confirmed.png、upload-small.png；read-ui复验五角色。API/媒体URL为受控夹具；不冒称真实手机/部署浏览器通过 |
| E003-REGRESSION | 朋友圈图片、observer前端共用请求、日志脱敏25项；旧三套inventory只增加本轮2写路由和1写页面对应预期，仍与原基线相同9失败/3通过，实际234 Admin路由（108读/126写）和46页 | 25 passed，无新增inventory失败；既有清单漂移仍存在，不能称全仓通过 |
| E003-CONTRACT | 三项BGM当前契约、共享认证、manifest路径及5路由/5模型/页面覆盖同步；Nginx语法、Compose解析通过；PRD SHA和STEP§1～8保持 | PASS；contract-check.txt及source-sha256.json；没有运行会读取迁移基线的全量文档核验 |

实际变更：新增`backend/services/bgm_{upload_service,media,worker,process,runtime,asset_service,errors}.py`；扩展原BGM schema/router/service/audit、main生命周期；新增`admin/static/js/bgm-upload-admin.js`并扩展原管理页/样式/试听；`admin-api.js`只增Blob类型和可选授权错误返回，默认行为保持；Docker安装FFmpeg、Compose专属持久运行卷、Nginx仅content路径关闭缓冲/设上限；新增上传、媒体、恢复、进程、隔离MySQL、全链及浏览器用例，新增精确单对象存储验证脚本。具体当前源码摘要见证据，不覆盖用户既有非BGM改动。

采用参数/实现差异：SUG-010使用两阶段持久接纳+隔离进程；SUG-011采用全库并发1、接收120/处理180/总300秒、编码≤120秒及10秒收尾；SUG-012源配置310秒/页面330秒；SUG-013采用trim后1～60 Unicode码点；SUG-014采用FFmpeg/AAC-LC目标96000bps、44.1kHz、mono保留/最多stereo、faststart。参数在上述本地/隔离测试中验证，生产代理计时/峰值/手机/CORS仍归STEP-020/021。SUG-019已写30天immutable并通过真实对象内容读回，但缓存/Range/CORS整体未验收；SUG-020音频命名和真实域名已有证据，封面留STEP-005。§9.5的PLANNED/UNVERIFIED是STEP-001当时快照，后续实际采用以本段及证据为准。

相对候选的局部实现决定：恢复凭据改为独立Admin localStorage（仅UUID/快照/摘要，最多50条），使刷新和重新登录后仍可核对，不复用H5偏好、不保存源；不改变操作去重语义。浏览器实测发现PUT可能透明重发，因此终态重放必须占同一全库名额复算真实字节再返回原结果，不能只看URL就认同内容。业务失败使用现行ApiResponse载荷，并明确采用409冲突/429忙碌/503暂不可用等HTTP状态；401/403/422既有处理保留。资源未知不盲换Key。上述为既定恢复/并发要求的实现具体化，未改变确认规格。

运行命令与环境：

- 宿主隔离虚拟环境 `.venv-step001/bin/python -m pytest -q -p no:cacheprovider tests/test_bgm_admin_access.py tests/test_bgm_upload.py tests/test_bgm_recovery.py tests/test_bgm_schema.py tests/test_bgm_process.py`：当时45 passed；新增最后3项恢复边界后单跑recovery为8 passed。host无FFmpeg，真实媒体测试由容器运行。
- `docker run --rm --platform linux/amd64 --network none --cpus 2 --memory 1g -v <repo>/backend:/app/backend:ro -v <repo>/tests:/app/tests:ro lxm-bgm-test:20261019 python -m pytest -q -p no:cacheprovider tests/test_bgm_media.py tests/test_bgm_upload_pipeline.py tests/test_bgm_process.py`：27 passed；追加父进程死亡用例后同环境单跑process为4 passed。
- 专属本机临时MySQL容器、非3306端口、显式BGM_TEST_MYSQL_URL及独立库名前缀保护下运行`tests/test_bgm_mysql.py`：4 passed。未使用业务配置的MySQL地址。
- bundled Node/Playwright＋本地Chrome运行`tests/test_bgm_upload_browser.cjs`与`tests/test_bgm_admin_browser.cjs`：PASS；后一项证据另存step003/read-ui，未覆盖STEP-002历史证据。
- `tests/test_step012_feed_image.py`、`tests/test_step029_observer_frontend_common.py`、`tests/test_step012_operation_log_redaction.py`相关回归：25 passed；具体输出regression.txt。Nginx以独立nginx:alpine、无网络、只读配置挂载执行`nginx -t`通过，Compose仅config --quiet，没有启动业务服务。
- 获准的OSS脚本使用项目虚拟环境SDK oss2 2.19.1执行`--execute --receipt .../step003/oss-smoke-plan.json`，输出verified_and_cleaned。最初缺本地SDK在任何外写之前失败，补齐后成功；没有遗留未确认清理对象。完整产物SHA256为`6ba6b0642fa26f0b30904e8016643ce613660c57eb47e451bfbd7eafaba96b1d`。

测试证据在step003（本地留存，未随本次提交；原引用：`execution/evidence/step003/`）。已验证结果按代码/测试/环境前提复用；先红缺模块/路由404记录保留。采用参数仍需后续部署证据，不用本STEP替代STEP-020/021。下一可执行项STEP-004，已按用户连续开发授权进入，不新增审批点。

### 9.8 STEP-004 实施与验证（2026-10-19）

**结果：VERIFIED，限本STEP的AC-054/056/058/059/060/061/066子条款。** 管理页已连接真实目录维护API；非空唯一有效默认、完整原子排序、版本冲突和原操作恢复均有证据。与STEP-003共同覆盖AC-066的音频就绪未启用及人工启用门禁；H5播放、公开缓存与部署仍未完成。

| 证据 | 要求—实现—实际验证 | 结果 |
|---|---|---|
| E004-API | AC-054/056/058/059/060/066：实际JWT/ASGI+隔离SQL，S/O写、V/A/T拒绝；名称码点/纯文本及伪造字段；首次/重新启用末尾、空目录自动默认、隐藏替代默认/清空默认；processing/failed/deleting/delete_failed/未验证/归属错误均拒绝启用；完整排序缺失/重复/未知/未启用整体拒绝 | PASS；18项目录专项，连同上传/读取/恢复回归共60 passed，api.txt |
| E004-IDEMPOTENCY | AC-060：同id同内容返回原版本和顺序快照，异内容20203；成功后更新其他目录再重放仍返回原结果；GET查询一致，审计只一条；真实SQL commit成功后注入异常仍核对并保留成功 | PASS；包含于api.txt；目录内部无缓存I/O，缓存失效失败留STEP-007验证 |
| E004-MYSQL | AC-061：独立MySQL8、两个engine/不同管理员，同版本并发设默认vs隐藏、排序vs隐藏、设默认vs排序；各轮一提交/一20202，读取版本/默认/完整顺序对应同一结果 | PASS；3 passed、4 deselected，mysql.txt；复用STEP-003专属临时库，未接业务库 |
| E004-UI | AC-054/056/058/059/066：实际Chrome155页面+真实BGM路由+隔离SQLite；真实AAC试听后明确启用，三种不合格素材按钮禁用；改名边界/XSS纯文本；完整排序、选择替代默认、设默认、隐藏到空再启用；observer无写控件 | PASS；browser-results.json，12类实际场景；桌面/390px截图已核对，不冒称真实手机 |
| E004-UI-RECOVERY | AC-060/061：真实API先commit再人为504，刷新后原id查询成功且无重复；弹窗打开后另次修改，旧版本明确未保存且不覆盖新名；Admin存储失败不发提交 | PASS；同一实际浏览器链。首轮发现缺returnErrorResponse导致409显示未知，启用既有选项后复验通过 |
| E004-REGRESSION | 同页上传/持久凭据/403/真实单首AAC与五角色读取/小屏再次通过；操作GET继续隐藏上传内部result/凭据；旧inventory仅增3路由（1读/2写），仍同9失败/3通过，实际237 Admin路由（109读/128写） | PASS限定相关回归；upload-regression/read-regression证据独立保存，未覆盖前STEP；不称全仓测试通过 |
| E004-CONTRACT | 3新路由、目录服务/JS、操作结果白名单、版本语义及当前数据/UI契约同步；manifest覆盖/路径/链接、PRD摘要和§1～8保持 | PASS；contract-check.txt/source-sha256.json；无新表/迁移、部署或外部存储操作 |

实现及采用：新增`bgm_directory_service.py`，目录行锁→实时管理员授权→按ID锁曲目，提交目录/操作/成功审计。完整顺序GET使用一个SQL读头和成员，避免混合版本。PATCH要求目录及记录两种期望版本；PUT要求目录版本和完整集合。各目录动作成功递增catalog_version；PATCH直接目标递增record_version，排序和其他曲目位置压紧受目录版本保护。名称复用STEP-003的1～60码点边界，原媒体版本和资产不变。原操作白名单结果只含目录版本、默认、有序ID及直接目标/版本，上传内部result仍不公开。

管理页新增独立目录操作JS、行内动作及统一dialog；操作前仅保存一个Admin localStorage元数据凭据；未知结果和权限中断保留标识，手动查询或原id原内容重发，不自动新建。HTTP409明确提示刷新重新决定，30秒等待后为待核对。顺序通过完整GET/order获取，不使用分页列表拼接。未引入新审批或多歌单。

运行：宿主`MEMORY_RUNTIME_ENVIRONMENT_ID='' .venv-step001/bin/python -m pytest -q -p no:cacheprovider tests/test_bgm_directory.py tests/test_bgm_upload.py tests/test_bgm_admin_access.py tests/test_bgm_recovery.py`为60 passed；隔离MySQL显式URL运行`tests/test_bgm_mysql.py -k directory`为3 passed；bundled Node/Playwright运行`tests/test_bgm_directory_browser.cjs`为12场景PASS，后复验原上传与读取浏览器两脚本均PASS。真实API浏览器fixture只挂BGM路由及本地Admin静态文件，使用临时SQLite，关闭应用业务lifespan；测试JWT不写证据。先红17项404/405后实现转绿，新增commit丢响应故障注入后共18专项。

证据在step004（本地留存，未随本次提交；原引用：`execution/evidence/step004/`），源码摘要19项；所有本项变更是已授权功能的具体实现，未改PRD或§1～8。前STEP媒体/OSS证据相关代码未改，按前提复用。下一项STEP-005：独立封面上传、替换、移除及音频隔离，已按依赖继续。

### 9.9 STEP-005 本地实施与验证（2026-10-19）

**当前结果：VERIFIED。** 用户明确授权后，已对登记的592字节封面对象完成真实OSS/HTTPS全摘要读回与精确删除，receipt为verified_and_cleaned，remote_verified=true、cleanup_confirmed=true。以下本地证据有效，已进入STEP-006；没有扩大音频对象原授权。

| 证据 | 要求—实现—实际验证 | 状态 |
|---|---|---|
| E005-API | AC-054/062/073/079/083/084/085/088/089：真实JWT/ASGI+隔离SQL；未发布/已启用/隐藏三状态补图、换图、移除，音频资产/版本/启用/隐藏时间/曾发布均保持；目录仅对已启用封面变更递增；新图/移除版本独立、旧图退役待清理；撤权、旧版本、删除态、处理失败保留旧图；五项非法字段/边界及V/A/T写拒绝 | PASS；封面专项15项，连同目录/上传/读取/恢复/朋友圈/observer/日志回归共100 passed，api-final.txt |
| E005-MEDIA | AC-087：真实JPEG/PNG/WebP→512方形WebP；居中、EXIF方向、透明度、无源元数据；动态图/损坏/伪类型/MIME拒绝；0/5MiB/+1、4096/+1px边界，200KiB仅质量目标 | PASS；6项真实Pillow，包含于pipeline.txt；建议参数已在此环境验证，不改为PRD确认阈值 |
| E005-PIPELINE | AC-073/085/086/088：真实图片→受限worker→OSS SDK→本地HTTPS→SQL关联；三格式成功、终态原文件重放无第二PUT；对象写成但公开读失败留下原操作资产；SQL成功后丢响应保留成功；同时回归音频完整链和Linux进程终止 | PASS；隔离无外网容器21 passed，pipeline.txt；不能替代真实封面Bucket/CDN证据 |
| E005-MYSQL | AC-073/089及全部署有界：音频和封面跨engine并发争同一槽，一接纳一明确忙碌，没有按类型倍增名额 | PASS；专属临时MySQL 1 passed/7 deselected，mysql.txt；既有目录跨管理员锁证据按未变逻辑复用 |
| E005-UI | AC-079/083/084/087/088：Chrome155+实际API/隔离SQL/真实Pillow13 worker/SDK/本地HTTPS，当前已保存与未保存候选分列；JPEG/PNG、动画失败、公开读失败、SQL成功后504并刷新原id查询、移除/旧图待清理、observer仅预览、390px布局；音频标识和启用保持 | PASS；browser-results.json及cover-comparison-{desktop,small}.png。真实手机/真实封面OSS仍未验证 |
| E005-REGRESSION | 原音频上传/未知结果/凭据/实际AAC试听、五角色读取/小屏浏览器复验；文件content只接受已登记上传动作，不允许目录操作借此重放文件；旧inventory只增1DELETE仍同9失败/3通过，实际238 Admin路由（109读/129写） | PASS限定相关范围；upload-regression/read-regression及inventory.txt；不称全仓通过 |
| E005-CONTRACT | 新增封面服务/媒体/JS/DELETE路由，POST改判别联合但原音频清单不变；结果白名单、媒体参数/关联/退役语义及共享RBAC、manifest同步；定向代码面/当前链接/PRD摘要/§1～8保持 | PASS；contract-check.txt/source-sha256.json；无新迁移或业务部署 |
| E005-OSS | 已生成512×512、592字节WebP，原SHA256=`6f18fbaf94fb89346978b6f328a5f570372cee7ee7aef7102c94ff58578e3c41`；精确新Key `bgm/covers/87a5c44a-2fb6-4507-b0b7-3ecbcb5765e2/a7976e29-9e15-415e-9397-49878d373f42.webp`；计划为上传/HTTPS全摘要核对/精确删除 | PASS；用户明确授权后执行原receipt，remote_verified=true、cleanup_confirmed=true，state=verified_and_cleaned；仅该新对象外写并已清理 |

实际采用SUG-016静态JPG/PNG/WebP、5MiB/4096px，SUG-017居中512×512 WebP及85→75→65质量优化；没有把200KiB当拒绝门。封面与音频共用原300秒绝对总预算和单槽/受监督worker。新增`bgm_cover_media.py`/`bgm_cover_service.py`、schema判别分支及BgmCoverResult；扩展worker的cover分支、临时收尾移除output.webp；处理资格和catalog/slot锁确保迟到不覆盖。track的音频attempt和active_operation_id不被封面占用，失败不会破坏正常音频。移除只改关联，旧资产retired_at/not_before与pending状态交STEP-006手动清理，音频及当前图不误清。

UI新增独立封面dialog与Admin localStorage凭据，不存二进制；已保存/候选各一圆形预览，临时objectURL会释放。音频成功后提供“选填封面”，封面失败可继续保留音频；原操作未知不能换源盲重传。所有名字/状态纯文本。首轮浏览器故障是测试夹具state变量被循环覆盖，修复夹具后真实链路通过；未因此修改业务预期。最终浏览器脚本另改了进程已退出时的teardown保护，仅测试清理变化，场景断言结果有效。

证据在step005（本地留存，未随本次提交；原引用：`execution/evidence/step005/`）。命令：宿主隔离pytest运行封面/目录/上传/读取/恢复与三项相关回归为100 passed；`lxm-bgm-test:20261019` Linux amd64、无网络/2CPU/1GiB运行cover_media+cover_pipeline+upload_pipeline+process为21 passed；专属MySQL执行`test_bgm_mysql.py -k cover`为1 passed；bundled Node/Playwright实际封面、上传、读取三个浏览器脚本均PASS。本机虚拟环境为此次真实浏览器验证补齐requirements已有Pillow13.0.0，不改系统或部署环境。

恢复动作：E005-OSS授权已收到并执行成功。该STEP已结算VERIFIED，后续状态见§9.4/9.11/9.12。


### 9.10 STEP-009 本地实施与验证（2026-10-19）

**当前结果：IMPLEMENTED；本地模块、设置页及既有motion回归通过，PRD指定H5-M实际手机验收未完成。** 用户已明确允许继续后续代码开发，保留真机为交付前必验项、不提前标VERIFIED（§9.11）。PRD实际iPhone/Android/微信要求保持，桌面390px不替代；未改PRD或§1～8。

| 证据 | 要求—实现—实际验证 | 状态 |
|---|---|---|
| E009-LOCAL | AC-015/016/018/019/077本项子条款：五默认值、严格字段边界、原motion键、单字段损坏隔离、未知版本保留、local→session→memory、内存即时生效及真实范围说明、成功清临时值、临时删除失败时旧值不覆盖新持久值、独立浏览器默认值 | PASS；unit.txt。Node VM执行真实模块，受控Storage故障；先缺模块红测见red.txt |
| E009-SETTINGS | AC-014/015/016/017：真实settings.html及JS、Chrome155、受控业务API，访客两个公开开关/键盘/不弹登录，原私有区隐藏；经实际退出确认清理再换账号，五项仍保留；无偏好API或媒体play/pause调用；正常保存无成功窗 | PASS限定H5-D/SIM；browser-results.json第一/二组；登录令牌使用隔离fixture，不冒称真实账号认证 |
| E009-FALLBACK | AC-018/077：local拒写可跨刷新保留，session也拒写仅本页，pageshow不丢内存值，后续保存成功清覆盖；全部读写拒绝时原私有区隐藏且公开开关可操作、无请求；1280px与390px布局 | PASS限定桌面Chrome/SIM；browser-results.json第三/四组、settings-{desktop,small}.png已查看。原DPR3全页截图出现重复拼块，改DPR1目标区域重拍；最终证据不含异常截图 |
| E009-MOTION | AC-019本项子条款：复验旧真实主页/设置四组，原0/1键、访客门禁、后退缓存/刷新/换账号/跨标签motion同步、减少动态、倾斜独立及存储异常 | PASS；motion-regression.txt及motion-regression/results.json；home-preferences/home-scene/api源码未改，不把原motion跨标签行为扩大到BGM遥控 |
| E009-CONTRACT | 五字段本地协议、公开UI、降级/未知版本、不主动播放和网络边界同步当前H5契约/manifest；两新无版本JS沿用设置页no-cache规则，独立无网络Nginx语法检查 | PASS；contract-check.txt/nginx.txt/source-sha256.json；未部署，未修改后端API/数据模型 |
| E009-MOBILE | AC-014～019指定H5-M子条款、设备间独立及真实手机设置效果 | NOT_VERIFIED；无实际iPhone/Android或微信运行证据，不能凭桌面模拟标通过 |

实际实现：新增`frontend/static/js/bgm-preferences.js`与`bgm-settings.js`，修改原settings.html公开区；motion沿用HomePreferences，倾斜不入五项。四新键为`lxm_bgm_fade_enabled`、`lxm_bgm_autoplay_enabled`、`lxm_bgm_volume`、`lxm_bgm_last_selected_track_id`，独立version=1/value/revision，临时键追加_session；不含账号、不使用demo键。字段接口read/write返回value/scope/note，get返回五项。严格布尔、音量有限0～1、手选null或1～128字母/数字/下划线/连字符ID。未知版本原记录不可覆盖；受阻保存改用可用临时层。普通保存无toast，不监听BGM storage事件遥控，不发网络/诊断/媒体命令。

设置页仅新增安全读取token用于初始化/私有可用性，存储全部拒读时按访客展示，保留账号数据且不发私有请求；共享api.js未修改。正常登入/退出仅原有清理。新增JS在Nginx现有精确静态规则中加no-cache，不声称已生效到部署。

运行：bundled Node执行test_bgm_preferences.cjs通过；Node/Playwright运行test_bgm_preferences_browser.cjs为4组PASS，既有test_home_preferences.cjs为4组PASS；临时nginx:alpine无网络/只读挂载nginx -t通过。最后补正motion读取失败的scope为default，仅说明范围变化，新增单元断言通过；浏览器原行为不变。证据在step009（本地留存，未随本次提交；原引用：`execution/evidence/step009/`），相关源码摘要13项。实施前H02/H03/H04/H05/C03摘要与既有来源相同；现有用户文档修改保留。

范围限制：AC-015/017/019只完成本STEP模块/设置本地子条款，正式音量拖动/选曲、播放暂停关闭、跨账号声音反馈属于STEP-014；不反向等待播放器，不把API写值当正式UI闭环。H5-M仍属本项未验证范围，需要真实设备证据。恢复位置：依据§9.11授权继续后续开发，相关真机证据交付前收齐；不需逐项重复询问同一开发顺序决定。

### 9.11 用户授权恢复（2026-10-19）

用户已明确允许①执行已登记封面单对象OSS测试并精确清理；②继续后续开发，保留真机验收待完成。此前§9.4/9.9/9.10等待事项及goal blocked记录为历史，当前恢复实施。第①项已执行成功，STEP-005结算VERIFIED；第②项仅调整开发顺序，不降低验收、不把缺手机证据的STEP-009及后续相关项标VERIFIED，不需逐STEP重复确认同一顺序决定。先进入STEP-006；后续按已有依赖推进，设备验收留交付前收齐。


### 9.12 STEP-006 实施与验证（2026-10-19）

**当前结果：VERIFIED。** 手动删曲、旧版本/失败残留清理、逐对象结果、原操作恢复与剩余重试已在工作区完成；未自动到期删、未迁移业务库或删除业务对象。真实Bucket仅核验获准封面测试对象的精确清理/不存在幂等路径；其余实际SDK/API/并发使用隔离环境。

| 证据 | 要求—实现—实际验证 | 状态 |
|---|---|---|
| E006-ELIGIBILITY | AC-054/063/064：S/O可写，V只读、A/T无管理访问；启用/不足期/接收/处理/活动封面/旧版本拒绝；恰好服务器等待期接受；真实启用→隐藏重计；满期只读及恢复不自动删 | PASS；19项清理专项并入api-final.txt（119 passed） |
| E006-RESULT | AC-065/073/090/091：音频、当前/旧封面及残留逐对象登记；删除态先提交，部分失败不可发布、只重试剩余；原id同内容复用、成功墓碑/普通列表排除；旧图not_before与当前关联保护；批次上限不报全完成 | PASS；隔离真实API/SQL+受控执行器断言；真实SDK结果另见PIPELINE |
| E006-PIPELINE | AC-065/073/090/091：真实worker+OSS SDK+本机HTTPS，正常、部分失败/只重试剩余、DELETE成功后丢响应、原对象不存在、foreign key/bucket拒绝；朋友圈与默认静态图哨兵保留 | PASS；宿主6 passed，pipeline.txt；首次普通sandbox不能绑定本机端口，仅夹具启动失败，获得工具执行权限后原断言通过 |
| E006-RECOVERY | AC-072/089：独立MySQL8两个engine、不同管理员；删除态commit后新封面忙碌、enable拒绝、迟到旧音频/封面finish拒绝，最终墓碑；本地进程锁证明中断后仅标delete_failed/资产失败并释放，无自动删除；撤权记录已完成对象且停止余项；SQL成功后丢响应保留成功 | PASS；mysql.txt（1 passed/8 deselected）及api-final.txt |
| E006-UI | AC-054/063/065/090：Chrome155实际管理页/API/隔离SQL/worker/SDK/本机HTTPS；只读打开/取消零删除，一次确认；逐项失败、剩余手动重试；真实SQL成功后504，刷新原id查询无重复删除；observer只看；1280与390截图已查看 | PASS；browser-results.json、cleanup-partial-{desktop,small}.png；不冒充真实手机 |
| E006-REGRESSION | 同一页原上传凭据/未知结果/403/真实AAC与五角色读取小屏；共享worker/process改变后Linux无外网容器回归音频/封面pipeline、清理、进程终止 | PASS；read-regression/upload-regression；linux.txt 21 passed；API含朋友圈/observer/日志回归共119 passed |
| E006-OSS | 新精确清理函数对已获准且已删除的同一封面测试Key执行幂等删除并源站确认不存在；无新上传，不访问其他Key | PASS；oss-absent-cleanup.json，关联step005原receipt；不声明真实业务曲目的生命周期已执行 |
| E006-CONTRACT | 新增3路由（1读/2写）、cleanup服务/JS、结果白名单/恢复分支；BGM数据/API/UI/RBAC及manifest和覆盖表同步。清单预期仅增BGM差额；实际241 Admin路由，110读/131写；全仓旧清单仍同9失败/3通过 | PASS限定增量；contract.txt；inventory.txt为7失败/1通过、inventory-pages.txt为2失败/2通过，均同既有失败项，不称全仓通过 |

实现：新增bgm_cleanup_service.py、bgm-cleanup-admin.js、BgmCleanupRequest/Result与资源分页GET；DELETE曲目与cleanup-retry复用现行操作ID/摘要/实时角色及catalog→slot锁。先保存deleting与资产定位；每对象经精确UUID/类型/Key/Bucket验证再交独立worker删除，SDK确认不存在后落deleted；异常不丢定位。OwnedWork支持同一owner下顺序处理多个对象，启动前清旧result且重新标执行态，结束需回收进程锁；runtime对清理操作只恢复失败状态，不自动重试外部删除。原GET仍只查，不写审计/业务。

采用值：原隐藏等待86400秒（服务器UTC）；旧图not_before仍沿用STEP-005。清理总180秒、每对象25秒、10秒收尾、每请求最多100对象，均与上传共用唯一全库slot，不增加队列。超过预算或批次的剩余对象仍需手动新操作；原操作重放返回原结果。SQL/进程/受控失败证据覆盖这些上限语义；不承诺CDN及终端缓存同步清空。

UI：沿用页面对话框，显示北京时间及服务器判定；逐对象中文结果，S/O才有确认按钮。独立localStorage键lxm_admin_bgm_cleanup_operation只存原标识与元数据，无法保存不提交；200秒请求等待，网络/权限中断后先GET原id，明确未查到才显式原快照重发。部分失败清凭据后重新打开获取当前版本再手动重试；没有静默换版本或自动重删。首次截图发现新dialog未继承既有专属样式，补齐与原页面一致的窄屏/滚动/边距并重验截图。

证据在step006（本地留存，未随本次提交；原引用：`execution/evidence/step006/`），源码摘要29项。最后只修正不存在资源GET返回20200信封并补断言、撤权测试，相关API最终119 passed；其余真实清理与MySQL已验证路径未受影响，复用相应结果。PRD摘要及§1～8保持、未读迁移基线。后续进入STEP-007匿名目录与受控缓存。

### 9.13 STEP-007 实施与本地验证（2026-10-19）

**状态：IMPLEMENTED。** 匿名公共目录、有限缓存及提交后失效均已完成，以下本地证据通过；AC-053要求的预发布DEP环境尚未取得，留STEP-020复核，不将隔离Redis/MySQL代称预发布环境。依用户连续开发授权继续STEP-008，验收范围不降低。

| 证据 | 要求—实现—结果 | 环境与范围 |
|---|---|---|
| E007-PUBLIC | AC-045：无头/无效头/Admin头同一安全快照；enabled+ready过滤、空目录、独立可空封面、异常503区分空；PASS | api.txt 5 passed；redis.txt含有图/移除版本分离；browser.txt真实Chrome显式匿名fetch，local/session有Token亦不附头；正式H5客户端留012 |
| E007-CACHE | AC-053：缓存60秒生成时间及真实TTL；实际过期回源、坏JSON/类型/超龄拒绝，40并发共用一次回源、真实本机Redis连接失败、SQL超时小于3秒、失败冷却；PASS | redis.txt 7 passed 3.44秒；独立Redis7、随机本机64760，无持久化；加速过期用PEXPIRE 10ms，60秒上限另查真实TTL和61秒龄包拒绝，未声称等待整60秒 |
| E007-COMMIT | AC-060：隔离Redis真实ACL拒绝EVAL，隐藏仍成功、原操作查询一致；旧缓存到期取得新空目录；封面提交/移除正确失效且音频不变；PASS | redis.txt；只创建并最终删除该隔离Redis临时只读用户；未连接业务Redis |
| E007-RACE | AC-053：跨实例旧回源不能覆盖新缓存，迟到旧失效不降水位；同进程失效废止旧任务缓存写入；取消单个等待者不取消共享SQL；PASS | redis.txt；已启动读允许原完整快照，有限旧缓存不是实时广播 |
| E007-SNAPSHOT | AC-045/053：MySQL独立连接在16次事务中交错修改版本/默认/顺序，40次读取均属于同一完整版本；PASS | mysql.txt 1 passed/9 deselected 0.75秒，专属bgm_isolated_01a152fd |
| E007-REGRESSION | 目录/封面提交后接线与音频/清理/鉴权/恢复回归；PASS | regression.txt 99 passed 3.17秒；未重跑未变媒体编码/OSS读回，不扩大外部写授权 |

采用参数：Redis0.25秒/次、SQL回源1.5秒、请求等待3秒；每进程一个在途回源，Redis异常下2秒回源间隔，失败2秒冷却；内存1秒并核原生成时间，Redis最大60秒；全部为技术采用值。GET只写派生缓存，无业务/审计写或媒体下载。新增路由与PublicCatalog/PublicTrack白名单；单SQL明确select_from消除开发初次连接歧义，修正后测试通过。

变更：新增backend/routers/bgm.py、bgm_catalog_service.py；main挂载，directory/cover服务提交后失效；定向测试隔离禁止使用配置Redis。当前BGM/API、共享匿名约定、H5例外及manifest/代码面已同步，HTTP路由由290增至291；Admin计数不变，未改既有三可选Bearer规则、权限、DB模型或迁移。证据位于step007（本地留存，未随本次提交；原引用：`execution/evidence/step007/`），contract.txt及source-sha256.json留核对依据；PRD/§1～8未变，未读迁移基线。

恢复：STEP-008接日志筛选及完整审计证据；007的DEP与009的真机均保持待验，工作区代码不代表运行环境发布。临时Redis容器lxm-bgm-step007-redis-01a152fd仅用于本任务，localhost:64760，测试仅删两个bgm缓存Key和本次临时ACL用户。

定向文档检查发现既有代码面表已441行超过manifest的400行上限，本次新增一条必要路由后442行；阈值未放宽，列为文档容量遗留项，路径/路由/链接核对通过，不影响运行验收。

### 9.14 STEP-008 实施与验证（2026-10-19）

**状态：VERIFIED。** 依有效本地后台链完成本项审计及既有日志UI范围，未将STEP-007预发布部署待验转为通过。

| 证据 | 要求—实现—结果 | 环境 |
|---|---|---|
| E008-ACTIONS | AC-077：音频接纳/失败/原曲重试，封面新增/替换/替换失败/移除，改名/启用/默认/排序/隐藏及删除/清理重试均经真实API执行并按既有日志API逐动作筛选；role/ID/版本/结果可核对；PASS | api.txt 6 passed；媒体worker在规则用例中受控，真实处理沿用既有证据与browser真实封面链 |
| E008-FAILURE | AC-060/083/089：回滚冲突、observer403独立持久化且曲目不变；部分清理日志保留audio/cover分类、1个失败及剩余数，重试只剩余且不伪报成功；重放无重复成功；PASS | api.txt及regression.txt；拒绝载荷只提取合法UUID目标，不读取/记录文件正文 |
| E008-COMMIT | AC-060：提交丢响应保留同事务唯一成功审计，Redis实际ACL拒绝失效仍保留成功；PASS | regression.txt包含原commit-loss断言；redis.txt 7 passed 3.61秒，隔离Redis |
| E008-UI | AC-077：已有日志页选择BGM及新增/替换/移除封面动作，查看真实操作详情；observer能看拒绝记录、不可写及导出；PASS | browser.txt/browser-results.json，Chrome155+真实API/SQLite/worker/SDK+本机HTTPS；audit-detail.png动画结束后已查看 |
| E008-REGRESSION | 共用审计flush/版本读取、权限/脱敏及业务链回归；PASS | regression.txt 112 passed 5.03秒；mysql.txt 10 passed 2.48秒，覆盖多进程名额、目录并发、封面/删除及公共一致快照；媒体编码/OSS外部写未变，复用已有验证 |

实现补齐实际发现的缺口：通用日志补当前角色及record/media/cover/catalog版本；清理安全结果含逐对象分类与剩余数；封面接纳保存服务端派生add_cover/replace_cover并用于后续日志，API action仍upload_cover，旧操作兼容；目录日志补角色。日志页只加模块/动作选项，沿原查询和导出权限。无新表、路由、日志平台或留存变更；无敏感正文/存储位置/偏好。

变更文件与摘要见step008（本地留存，未随本次提交；原引用：`execution/evidence/step008/`），BGM的api/data/admin-ui及现有日志契约已同步。六项新增测试先红（缺角色/版本/动作/目标和UI筛选）后绿。原PRD与§1～8保持；007、009未验范围不变。下一项STEP-010核心，正式播放器UI、浏览器输出能力、目录与跨页生命周期按010～019各自范围推进。

### 9.15 STEP-010 核心实现与SIM证据（2026-10-20恢复核对）

**状态：IMPLEMENTED。** 新增bgm-controller.js与test_bgm_controller.cjs。本轮核对源码仍在、临时日志已丢失，因此重跑Node控制测试，结果保存在step010/core.txt（本地留存，未随本次提交；原引用：`execution/evidence/step010/core.txt`），语法检查通过。先前未归档的开发红/绿日志不作为现存证据。

AC-006/007/008/020核心子条款：注入有效目录和媒体，验证会话→手选→默认→首曲/空、非法进度及版本变化归零、当前播放行不重启、暂停行续播、暂停下一首不创建新媒体、顺序回首、单曲自然结束仍复核目录、手动才写最后手选。AC-025核心子条款：延迟play兑现、快速多次选择、关闭、旧progress/playing/ended、失效默认回退及旧异步复核均服从最新意图，不出现两首输出；输出上下文未运行不标播放；原生pause不冒充手动暂停。

边界修正：解除不存在的阻断不能把播放态改暂停；失败后废止输出代次，迟到playing不能复活；自动play/选择不覆盖用户暂停，手动下一首不清除故障耗尽标记，明确选播可恢复。所有测试为SIM，未冒充真实媒体/手机通过。脚本尚未接入页面，输出适配/渐变、目录、会话和UI均归后续STEP。

本STEP独立核心采用同文档单例、AbortController+代次、注入输出与曲终钩子，不新增请求或持久字段。契约与manifest已登记；source-sha256.json保存当前源码/测试前提。§1～8未编辑；原临时prefix比较文件当前已不存在，因此不新增声称本轮与原临时文件复比通过。后续进入011，沿既有授权继续，所有实际终端待验项保留。

### 9.16 STEP-011 本地输出实现与真实Chrome证据（2026-10-20）

**状态：IMPLEMENTED。** 真实Chrome桌面输出与受控降级已取得下述证据，macOS Safari及H5-M仍未验证，不能标VERIFIED；依§9.11用户允许继续开发，保持交付前必验。

| 证据 | 要求—实现—结果 | 环境/限制 |
|---|---|---|
| E011-GAIN | AC-023/024/027：真实AAC开始渐入、暂停先提交意图再渐出/停止，后增益波形0.3→0.6幅度比2.013，音量零波形为零且媒体仍运行；PASS | 有界面Chrome155.0.8059.85、本机HTTPS、30秒AAC-LC96kbps/44.1kHz mono，非真实CDN或手机；output-measurements.json |
| E011-ORDER | AC-024/025核心：切歌事件证明旧曲pause早于新曲playing，暂停下一首不创建媒体；关闭取消渐变，过渡关开关保持暂停意图并从检查点续播；PASS | 同真实浏览器；controller.txt另覆盖延迟旧play/渐变失败/阻断/单例/目录更新 |
| E011-FALLBACK | AC-026/027：注入BGM增益不可用、已验证媒体音量幅度比2.020；默认未知音量能力降设备控件协议，零值仍静音，明确取消静音才存0.30；自动化不可用仍直接增益播放；PASS | 故障为SIM注入，AAC及波形真实；设备分支用单独测试测量图观测，不能声称真实无WebAudio手机已通过 |
| E011-FAILURE | AC-026/027：真实404音乐不标播放；模拟NotAllowed/晚play、零值降级、运行时乘数不改偏好；PASS | output-browser.txt、output-unit.txt；原偏好模块未改 |

关键修正：不以未渲染AudioParam.value作渐入起点（实际可能仍为1），维护已设置增益并补回归；重复解除无关阻断不改播放态，错误代次废止，暂停渐变终点记实际进度；过渡失败仍停止旧输出后继续基本播放。使用同一引擎自己的AudioContext，旧对象停止/销毁不影响通话。

采用参数：线性0.5音频秒，媒体就绪后开始；真实浏览器采样按AudioContext时钟累计，最多3秒墙钟避免停滞误报。无头首次出现时钟停滞、连续夹具曾有无样本失败，相关失败日志保留；改正起点并清理场景输出、按实际渲染时钟采样后最新完整有界面运行通过，未删除原有效断言、未将无头失败改为通过。首次报告与最终报告分开，最终结果以output-browser.txt和含时钟样本的output-measurements.json为准。

证据在step011（本地留存，未随本次提交；原引用：`execution/evidence/step011/`）；当前源码摘要与核心/输出单测均归档。AAC夹具在无网络、2CPU/1GiB既有FFmpeg镜像生成，366824字节，SHA256=7f0b0eb62bce8c4822f0713906980f8a19c7219762bd6930da2d060edef4acaa；仅本机临时文件，未外部上传。恢复时原临时MySQL/Redis容器已不存在，Docker已启动，未重建或连接业务服务。

契约已登记BgmOutput能力/设置接口、输出fadeOut与控制器过渡行为，manifest登记输出脚本，Nginx源码无缓存白名单加入两个新脚本；无页面UI或生产配置生效声明。原0010受影响核心断言在本轮重跑通过，其余已验证后台不重跑。下一项012接公开目录与有限故障链，所有前置真实环境待验保持。

Safari实测补充（2026-10-20 16:14 CST）：参见020/safari-real-output.json和safari-output-check.txt，实际Safari 26.5已验证增益、零音量不暂停和人工恢复输出。只补核心证据，不替代正式面板/降级/持久化/手机验收，STEP状态不提前VERIFIED。

### 9.17 STEP-012 事件目录与统一故障链（2026-10-20）

**状态：IMPLEMENTED。** 当前客户端/控制器接线及下列本地证据通过；PRD指定H5-M与Safari尚未实测，不标VERIFIED。依§9.11用户授权继续013；不降低验收或将测试夹具当成产品UI交付。

实际新增`frontend/static/js/bgm-catalog.js`、`bgm-player.js`，前者显式匿名固定URL且不使用API.request，后者统一协调目录与媒体，保留控制器为输出唯一所有者。控制器新增延后输出的播放意图、首次目录会话选择、halt、onEnded接管接口；setCatalog仍不自动播放。单文档客户端/播放器均提供singleton工厂。Nginx无缓存脚本源码名单加入新模块，当前BGM API契约和manifest同步；无后端路由/模型/迁移/业务库变化，无生产部署生效声明。

采用SUG-006/008/009当前建议值：新鲜300000ms、最长1800000ms，边界不含；总30000ms、单目录8000ms、全链重试1次/退避1000ms、媒体最多15000ms、3个不同候选、故障强刷1次、冷却30000ms。子阶段共用单调截止时间。完整目录与成功/失败时间分别保存在`lxm_bgm_catalog_v1`；内存降级不冒称跨页成功。人工恢复资格独立保存在`lxm_bgm_recovery_v1`并与传入session合并，完整会话可靠性/检查点与页面事件归013。手选失败回退有效旧曲时保留手选偏好和可见notice。

| 证据 | AC/实际覆盖 | 结果与范围 |
| --- | --- | --- |
| E012-SIM | AC-009/028/029/030/046/047/048/050/051/052/059：新鲜/超龄/倒退、完整跨文档缓存、并发读取/单等待者取消、正文超时与迟到禁止续期、有效空/目录错误/媒体错误、元数据与新排序、权限不换曲、手选回退/保留偏好、暂停关闭取消、持续缓冲恢复与单曲曲终 | player-sim.txt PASS；真实生产模块+虚拟时钟/输出/请求，非终端音频证据 |
| E012-BUDGET | AC-029/030/052：8秒目录超时+1秒退避后两段等待共用30秒；最多3个不同失败ID/一强刷；全链目录重试不按阶段重置；耗尽后冷却/自然事件/新文档不重新发声；恰300秒过期、恰1800秒禁止新候选 | 同SIM PASS；含时钟数值、次数和无遗留计时器断言；不是实际等待30分钟 |
| E012-CHROME | AC-028/046/047/048/050/051/052/059本地桌面子条款及AC-045客户端补证：真实公共API/隔离SQLite、生成AAC/回环HTTPS；Token及Cookie均未携带；元数据/排序不重建当前音频、下一首采用新顺序、暂停失败刷新不续期、跨HTML复用完整快照/时间、有效空目录、真实404仅3候选、跳页保留人工恢复、明确播放恢复 | browser.txt/browser-results.json PASS；Chrome155.0.8059.85有界面；TTL跨越采用客户端墙钟偏移注入，API/媒体/原生事件真实 |
| E012-PERMISSION | AC-028：独立无手势Chrome上下文原生play被拦，普通按钮不重试；明确BGM播放后同一媒体/上下文恢复，无换曲绕过 | 同真实Chrome PASS；实际iPhone/Android/微信/Safari未验证 |
| E012-REGRESSION | 受影响核心、输出适配器、本地偏好 | controller.txt/output.txt/preferences.txt均PASS；后台源码未变，既有API/MySQL/Redis证据沿用，不重复连接已消失的临时服务 |
| E012-CONTRACT | 当前BGM契约、manifest两新模块、Nginx源码无缓存名单；PRD与本文§1～8保持 | contract.txt/source-sha256.json；未运行会读取迁移基线的完整文档检查主程序 |

证据目录：step012（本地留存，未随本次提交；原引用：`execution/evidence/step012/`）。首次SIM在模块缺失时失败，实施后通过；补充测试曾用跨VM的instanceof Error导致测试断言错误，改为核对实际错误消息后通过，没有放宽超时/候选/最新意图断言。首次浏览器运行因沙箱禁止回环端口失败，经既有验证授权和工具提权运行通过；没有自动审批拒绝或新的外部写入。最终Chrome在源码收敛后重跑并归档，所有启动的测试服务/浏览器已关闭。

剩余：H5-M/Safari仍待交付前验收；当前仅测试夹具接线，实际主页/六类页面由013～015接入。后台实际DEP缓存/媒体部署证据仍归020，历史9项非BGM清单失败与code-surface文档超过既有max_lines的范围外问题保留。下一恢复位置013。

### 9.18 STEP-013 页面生命周期、会话与检查点（2026-10-20）

**状态：IMPLEMENTED。** 八个实际HTML已增量接线；以下本地证据通过，真实H5-M/Safari仍未完成，继续保持交付前必验、不标VERIFIED。完整主页面板/六类页面气泡尚未由本STEP交付，分别继续014/015。

实际新增`bgm-session.js`（可读可写探测、记录校验、不可靠标记）和`bgm-page.js`（同文档实例、页面模式、检查点、可见性/pagehide/pageshow、加载层暂停）。Index/Feed/Chat/Settings开放接入，Diary/Memory/Relationship沿原门禁接入，Login临时阻断且保留意图/检查点；Admin未接入。api.js仅在受保护页面实际导航前调用suspendAccess，同页登录弹窗不阻断音乐；HomeStartup条件/期限没有增加BGM依赖。

会话键`lxm_bgm_session_v1`记录v1/revision、曲目/媒体版本/进度、意图/关闭/人工恢复与气泡比例；初始化验证读写/读回/删除能力，失败保守暂停并显示跨页受限。关键动作和实际状态变化即时保存，播放中每2000ms检查点，不产生目录请求。隐藏/pagehide先同步停播，已冻结旧文档不覆盖新记录；返回先读取最新会话/目录再解除对应阻断，关闭与人工恢复优先。未知版本保留原文；不可保存时不承诺跨页一定保存关闭。没有账号命名空间/广播遥控/按墙钟补进度。

| 证据 | AC/实际覆盖 | 结果及限制 |
| --- | --- | --- |
| E013-SIM | AC-021/022/032/033/034/035/036/040/044：真实模块+注入事件/输出，2000ms检查点、关键动作、非法进度/媒体版本、冷目录待校验检查点、读可写不可/全不可用/unsafe标记/未知版本、隐藏即时停、可见条件恢复、旧BFCache会话对账、独立登录、复制关闭与独立标签 | session-sim.txt PASS；非真实设备/锁屏证明 |
| E013-PAGES | AC-021/022：真实七个允许HTML分别自动播放开/关，共14组合；访客开放页与已过门禁私有页；三个无Token私有页实际回主页弹窗且无BGM请求 | browser-results.json directEntry/privatePageGatePreserved PASS；BGM公共API/隔离SQLite真实，其他业务响应受控 |
| E013-LOADER | AC-031：真实首页加载层，测试专用明确音乐手势开始真实AAC、页面自带暂停按钮可真实点击、正文沿用实例/暂停意图；目录挂起时HomeStartup仍正常释放一次 | browser.txt/browser-results.json PASS；测试音乐手势不冒充尚未完成的014唱片入口，挂起目录不参与主页就绪 |
| E013-NAV | AC-032/034/040：真实跨HTML导航，登录页无声并保留合法进度/播放意图，返回设置有条件恢复，关闭后刷新保持；同页登录弹窗维持播放 | browser-results.json PASS；允许跨页间断，浏览器拒绝时保持待恢复检查点 |
| E013-BFCACHE | AC-034：实际Chrome后退缓存恢复原设置文档，原identity保持、真实pageshow.persisted=true，读取后来在聊天页保存的关闭 | browser-results.json nativeBfcacheReadsNewerClose PASS；该实际BFCache用无活动音频图页面，播放中旧页对账另有SIM |
| E013-TABS | AC-044：真实window.open复制已关闭会话，随后明确操作原页不改变副本；实际媒体/会话的隐藏/返回处理 | copiedClosedTabIndependent PASS；窗口切换一直报告document.hidden=false，即使关闭Playwright焦点覆盖也未观测原生隐藏；visibility项明确记为SIM hidden属性+事件注入，不能当真实隐藏/锁屏验收 |
| E013-STORAGE | AC-035：真实Settings页面可读旧play但写session失败，零目录请求、暂停意图和可见跨页受限提示 | browser-results.json readableButUnwritableSuppressesAutoplay PASS |
| E013-REGRESSION | 受影响控制核心/输出/012故障链、原本地设置与共享API/静态H5 | controller.txt/output.txt/player-regression.txt/session-sim.txt PASS；原偏好真实Chrome4组通过（预置暂停会话，仍断言零偏好网络/零播放命令）；共享request-context 8组通过，含同页登录不误加access阻断；h5-static.txt 19 passed |
| E013-CONTRACT | BGM/H5当前契约、manifest、新脚本Nginx源码名单；PRD及本文§1～8保持 | contract.txt/source-sha256.json；无新路由/表/部署/外部写入 |

发现并修复的当前范围问题：①无目录的登录页保存会抹去原曲目/检查点，Player.checkpoint现保留待目录校验字段；②加载层原页脚遮挡暂停按钮，移到顶部安全区/正确层级，保留真实点击失败日志loader-pause-red.txt；③元数据未就绪时currentTime=0覆写待执行seek，输出现在报告seekTo，pending-seek-red.txt先复现失败再通过，实际导航也通过。其余测试修正：业务夹具补关系growth-log.list；BFCache按既有项目用commit+真实pageshow而非不重复触发的load；原生隐藏预条件缺失明确标注，未修改产品可见性判断或把该项列为原生通过。

证据在step013（本地留存，未随本次提交；原引用：`execution/evidence/step013/`）；真实Chrome155.0.8059.85有界面，本机HTTPS合成AAC，测试服务/浏览器均已关闭。源代码与证据摘要登记当前版本，012已变的controller/catalog/player及011输出按本节回归证据更新，不用旧摘要冒充当前源码。其余后台代码未改，既有隔离API/MySQL/Redis结果沿用；业务库/真实OSS未再次访问。

恢复位置：STEP-014主页正式唱片、歌单面板与封面显示。前置终端/部署待验和历史范围外9项清单失败、code-surface max_lines问题保持；仍无整体功能完成声明。

### 9.19 STEP-014 主页正式唱片、面板与封面（2026-10-20）

**状态：IMPLEMENTED。** 正式控件与以下本地证据已完成；H5-M/Safari/微信、实际软键盘与生产账号环境未验证，依§9.11继续开发，不将本项或整条跨环境AC标VERIFIED。

新增bgm-home.js、bgm-record.js、bgm.css与唯一默认record.svg；Index第五格独立公开，前四格与关系/日记入口保持。面板只有曲名/状态、播放暂停、下一首、弱化音量与关闭本次；同一唱片节点移动并保持旋转相位。采用缩放1.18、12秒一圈、开合400ms、正常高度48dvh/上限460px，实际溢出长名20px/s往返/两端停1秒。小屏/横屏内部滚动，安全区/可视视口参与限位；遮罩/Escape/返回/收起/头部下拉、背景inert及滚动锁、焦点循环/恢复和最新开合优先。减少动态效果/可选动画或观察器失败保留静态控件。

封面按ID/版本/URL+代次隔离，整图居中裁圆；5秒上限、最多64个失败版本记忆，坏图回唯一默认资源，默认也坏仍有CSS黑胶/音乐符号。输出增加previewVolume/commitVolume/cancelVolumePreview，拖动即时作用输出、结束合并本地保存；设备降级仅静音/取消静音。设置渐变开关经输出适配器即时收敛，自动播放仅影响后续访问，原motion/倾斜权限与值保持。

| 证据 | AC/实际覆盖 | 结果及边界 |
| --- | --- | --- |
| E014-HOME | AC-001/002/004/005/006/007/008：访客第五格、单唱片移动/旋转相位、暂停/缩放、选曲/下一首、关闭后开面板不复播、收起方式/焦点/连续开合/长短名/减少动态效果 | browser.txt/browser-results.json PASS；Chrome155.0.8059.85，home-panel.png/home-small.png/home-landscape.png已查看；390×844、320×500、667×320为桌面视口，不是手机 |
| E014-OUTPUT | AC-003/015/017/019：真实AAC/增益、正式鼠标range拖动即时预览/结束一次写入、0音量仍播放并标静音、5项正式偏好、登录A/退出/登录B/再访问、实际音量/手选保持、播放关自动播放不停、暂停/关闭开两项不出声、motion不改音乐/渐变 | 同Chrome PASS；BGM API/SQLite/AAC真实，认证与其他业务响应为本地夹具；产品实际登录弹窗/login/logout/saveToken路径，不冒充生产认证。无旧会话新访问设置矩阵沿用013有效证据 |
| E014-COVER | AC-079/080/081/082/084/085：无图唯一默认、整图裁圆、同曲旧封面晚到不覆盖新版本、坏图/默认也坏仍可控制、改图不重建音频/进度/音量/手选、不轮询 | 同Chrome PASS；HTTPS图片/媒体真实，TTL由墙钟偏移注入；六页气泡实例归015，异曲晚到在后续共享组件验收继续覆盖 |
| E014-FAILURE | AC-003/009及012衔接：真实503与有效空目录区别、真实404有限失败/重试入口、原生无手势play拒绝/明确重试恢复；目录下架当前曲按已有播放意图回退，暂停只改选择 | 同Chrome PASS；catalog-reconcile-red.txt先复现缺口，player.txt修复后SIM PASS；回退沿用面板读取剩余预算/重试计数，无重置30秒 |
| E014-REGRESSION | 输出预览/核心/会话/故障链，原主页业务数据、motion/倾斜、场景可选API失败与前四格门禁、H5静态契约 | output.txt/controller.txt/session.txt/player.txt PASS；home-preferences.txt 4组、home-data.txt 8组、scene-boundaries-results.json 7组PASS；h5-static.txt 19 passed。旧more断言定点替换；原业务数量排除新增公共BGM，原6项计数未削弱 |
| E014-CONTRACT | BGM/H5当前契约、manifest路径、Nginx脚本/CSS源码名单，PRD及本文§1～8保持 | contract.txt/source-sha256.json；无部署/新后端路由/表/真实OSS操作 |

测试修正：WAAPI暂停在ready后采相位，AudioParam在有限250ms窗口核对最新值，保留初始采样失败日志。一次程序导航至设置被Chrome拒播，按要求保持人工恢复并留programmatic-navigation-permission.txt；改为产品头像真实点击导航后，正式设置/账号流程通过，没有给普通登录点击隐式恢复权。下架回退修复的是既有F-006明确规则，迟到目录仍服从最新暂停/关闭。

证据：step014（本地留存，未随本次提交；原引用：`execution/evidence/step014/`）。后台未改，001～008有效证据沿用；011输出预览和012面板对账由当前SIM/Chrome补证；013生命周期未改、会话SIM回归通过。所有本地测试服务/Chrome已结束，旧MySQL/Redis端口未使用。历史9项清单失败、code-surface max_lines与部署/终端待验继续保留。恢复位置STEP-015六页共享气泡、安全区与覆盖层；014剩余异曲封面竞态与终端项在相关后续验收收齐。

### 9.20 STEP-015 六页悬浮唱片与安全区（2026-10-20）

**状态：IMPLEMENTED。** 六页接线和本地证据通过；实际手机/Safari/微信、软键盘与记忆抽屉真实打开仍待验，不以注入状态代替原生交互，不标VERIFIED。

新增bgm-bubble.js并复用bgm-record.js/bgm.css，Feed/Diary/Memory/Relationship/Chat/Settings共同接入；前三类私有页面沿原门禁。只展开播放暂停/重试与关闭本次两项；空白/Escape收起不断音，关闭/确认空目录移除节点，临时失败保留恢复入口。主页/独立登录/Admin无气泡，bubble来源不能解除关闭。

采用48px、右侧16px+安全区、竖拖6px阈值、拖后400ms指针误点抑制、键盘上下每次0.1比例；以实际显示位置开始拖动，按可用高度归一化保存至既有会话（x=1）。可视视口/旋转/滚动重新夹入预定义区域；空间不足隐藏控件。Feed图片/评论/加载层，Memory抽屉/底栏/recenter，Relationship升级层，Chat输入发送/可视视口，Settings开关/可点行/展开表单/退出区，以及公共登录/确认/全屏层均有明确适配；覆盖层结束读最新关闭状态。MutationObserver只观察命名根的属性及body直接子节点，ResizeObserver限定区域，不扫描画布后代或网络轮询。

| 证据 | AC/实际覆盖 | 结果及限制 |
| --- | --- | --- |
| E015-SIX | AC-001/010/011/080：六实际HTML、匿名/已过门禁私有页、共享封面、原生AAC播放/暂停、仅2项、空白/Escape、关闭移除/跨页设置不复活、气泡没有重开权限 | browser.txt/bubble-results.json PASS；Chrome155.0.8059.85；公共BGM API/隔离SQLite/HTTPS AAC真实，其他业务响应受控 |
| E015-POSITION | AC-012：真实鼠标右侧竖拖/不误播、会话比例、旋转/跨页、设置开关不被遮挡并实际可点 | 同Chrome PASS；settings-overlap-red.txt先复现遮挡，drag-clamped-anchor-red.txt再复现避让后拖动起点问题，settings-avoidance.txt与最终全套PASS；截图settings-bubble.png/chat-landscape.png已查看 |
| E015-OVERLAY | AC-013：原Feed图片预览/评论函数、原Relationship升级弹窗、公共登录/确认、关闭后迟到resize/overlay回调不能复活 | 同Chrome PASS；Memory实际DOM抽屉/遮罩的开关状态注入验证，不声称原生打开；键盘采用visualViewport.height/resize注入，真实输入栏布局与气泡限位通过，chat-keyboard-sim.png已查看；真机键盘/抽屉动作待补 |
| E015-RECOVERY | AC-010/011：权限/资源失败可恢复，确为空目录无命中区，三私有页回首页、Login/Index无气泡 | 同Chrome PASS；真实媒体404/空目录；本次Chrome默认及新profile均允许自动播放，拒播前提未成立，气泡NotAllowedError受控注入后明确点击使用原生AAC恢复。原生拒播核心/主页证据沿用014，不把此注入记为原生拒播 |
| E015-COVER | AC-080/082与014补证：A图延迟、正式主页选B后A迟到不覆盖B，不改变当前音频 | 同Chrome PASS；补齐014异曲竞态本地证据；封面本体规则未改，014同曲版本/失败/默认图证据沿用 |
| E015-REGRESSION | 气泡接入后原motion/倾斜/账号与本地设置边界、静态H5 | home-preferences.txt 4组、bgm-preferences.txt/preferences-results.json 4组、h5-static.txt 19 passed；偏好专项仍是受控媒体调用，不冒领真实输出 |
| E015-CONTRACT | BGM/H5当前契约、manifest、Nginx新脚本名单；PRD与§1～8保持 | contract.txt/source-sha256.json；未部署或访问业务库/OSS |

证据：step015（本地留存，未随本次提交；原引用：`execution/evidence/step015/`）。两专项结果原先同名，现独立保存bubble-results.json与preferences-results.json，并补取气泡详细结果。一轮补证在Memory第一次目录请求出现暂时不可用并停在人工恢复，日志catalog-request-interruption.txt；根因未确认，未扩大预算或弱化断言，同版本增加HTTP诊断后完整通过，实际部署稳定性仍归020/021。设置遮挡与拖动起点为本范围实际修复；图/音频共用模块逻辑未改，014 CSS新增均限定气泡选择器。

测试服务/浏览器已结束；后台及控制核心未改，既有相关结果复用。真实终端/键盘/记忆抽屉、预发布媒体缓存、历史9项清单失败与code-surface max_lines仍保留。恢复位置STEP-016：完整动态能力预检后、用途说明/麦克风准备前关闭BGM；基于准备代次/通话归属与可信清理确认释放阻断，未知清理保守保持，不能只依靠面板隐藏或releaseMic调用完成。

### 9.21 STEP-016 通话准备与归属清理（2026-10-20）

状态`IMPLEMENTED`；本地Docker/Chrome实际采麦/输出前时序及挂断/准备取消已补证，其余实际语音分支、AC-038目标终端/DEP仍待验，不计VERIFIED。用户已指定先使用Chrome、Safari、本地Docker，优先账号id=1；允许必要时新建测试账号，但本条不等于已登录或验收通过。代码实现完成与真实环境门禁分开记录。

- `voice-entry.js`先完成静态及无声context.audioWorklet动态预检，再建立准备归属；在用途说明/权限查询及首次resume/getUserMedia/输出前同步通知BGM关闭。动态能力拒绝不改变音乐；constructor异常维持原microphone_denied分类。
- 每次准备持有独立context/transport/stream及pending采麦；关闭Promise成功、迟到采麦收尾、远端无需清理或可信终态/cleanup_pending=false确认后，才释放本归属。未知创建、清理拒绝保持阻断；同幂等键恢复原call，旧清理不能释放新准备。监听/回复结束/重连不释放占用。
- `bgm-page.js`挂载及事件读取VoiceEntry最新聚合占用；立即block(call)+close，释放只unblock，保持本次关闭。晚挂载同样关闭；旧事件detail不能清当前占用。后台语音协议/配额/结算未变。

| 证据 | 范围与结果 |
| --- | --- |
| `permission.txt`、`permission-results.json` | 实际首页/公共BGM API/隔离SQL/HTTPS AAC输出，VoiceEntry真实模块，语音context/权限/采麦受控；15组能力、用途取消、拒麦、迟到采麦、旧清理隔离通过。原始缺hook红测保留preparation-red.txt。 |
| `guards.txt`、`guards-results.json` | 实际主页访客登录门禁、视频占位不关闭音乐；已忙准备重复进入不创建第二归属。3组通过。最初测试误用登录弹窗selector导致超时，修正为实际auth-modal-overlay后通过，错误记录保留，未改变产品。 |
| `ownership.txt`、`ownership-results.json` | 实际VoiceEntry，受控DOM/transport/HTTP/socket；7组覆盖挂断pending/最终确认、旧新call隔离、本地关闭迟到/拒绝、创建中取消、丢失响应同键重放、明确预检拒绝、终态读取失败再确认。不是真实Provider证据。 |
| `session.txt` | 原页面/会话SIM回归及晚挂载占用、聚合读取、旧事件、释放后仅主页明确重开通过。 |
| `voice-permission-regression.txt`/`step036-permission.json` | 原036权限9场景Chrome回归通过。新增VOICE_EVIDENCE_DIR仅隔离输出，不覆盖历史语音证据。 |
| `voice-terminal-regression.txt`、`voice-replay-regression.txt` | 原终态21测试与重放生命周期脚本通过。 |
| `voice-duplicate-regression.txt` | 原038实际Chrome/AudioContext受控建通API，重复重试/取消只2次创建、同键、1次精确end，通过。 |

必要契约同步BGM/H5/实时语音API及manifest；Nginx源码no-cache规则新增voice-entry，尚未reload，不声明运行缓存已生效。新增两个BGM语音专项脚本；修改会话测试与036证据路径。

本地Docker只读核对：正在运行voice-quota-20261016镜像，前端挂载与本轮index/voice-entry/bgm-page字节匹配；`GET /api/bgm/catalog`返回404。证据docker-readonly-probe.json与docker-chrome-catalog-unavailable.png；真实Chrome面板显示目录暂不可用。Safari通过原生自动化getApp连接超时，未实际完成页面验收。后端5个共享文件与运行版仅有BGM差异，25个BGM源码/迁移文件叠加旧镜像准备候选，见local-candidate-manifest.json；构建不等于部署或真实通话通过。

恢复：完成候选与迁移范围核验后，按本地运行变更边界执行必要确认；真实通话、Safari与H5-M仍不得冒领。继续不依赖该环境的已授权开发时保留上述验收门禁；没有用模拟替代AC-037或提前标VERIFIED。

本地真实时序补证（2026-10-21）：020/voice-timing-live-check.json记录两次原生采麦/voice context.resume前BGM已停且关闭、真实通话输出15次入口保持阻断，32秒挂断及等待接听取消后只解除阻断且不复播；人工按钮恢复有效。CALL-01决策兜底事实、严格范围与仍待分支见§9.4最新条目；STEP-016不因此提前VERIFIED。

### 9.22 STEP-017 短TTS活动衰减（2026-10-20）

状态`IMPLEMENTED`；AC-042活动生命周期SIM通过，AC-041本地Chrome输出通过、H5-M能力仍待验。不新增TTS Provider或业务链。新增bgm-ducking.js与BgmPage.ducking，允许页面同一实例接入；句柄end/cancel/destroy按ID+当前归属释放，重复begin/结束幂等，旧句柄不误清重用ID。默认30秒、单活动最多60秒保护，避免遗失结束后永远衰减；比例采用SUG-004的0.25，本地客观增益已测，主观听感/目标终端待验。

有精细增益时当前音量×比例，并按当前渐变能力收敛；用户调整音量按原持久化语义保存，活动结束按新音量恢复。无能力/能力未明时临时阻断short-audio；最后一路释放且最新状态允许才调用BgmPlayer.resume。恢复不设置播放意图、不清人工恢复、不穿透暂停/关闭/通话/隐藏；晚结束只操作自身。BgmOutput.setMultiplier的可选fade参数复用现有渐变及取消能力，关闭渐变直接收敛、0音量不被恢复解除。

| 证据 | 结果与边界 |
| --- | --- |
| `step017/red.txt`、`sim.txt` | 缺模块红测后实现通过；真实player/controller/output+受控clock/media，覆盖重叠/ID换代/重复结束/超时/取消/销毁/新音量/设备暂停/初始化前活动与所有高优先级状态。首次夹具重复pause也同步发pause事件造成递归，修正为原生“已暂停不再发pause”的前提；产品未为测试弱化。 |
| `step017/browser.txt`、`browser-results.json` | 实际首页/BgmPage/公共API/隔离SQL/HTTPS AAC/Chrome；短TTS以活动调用模拟；post-gain Analyser RMS验证25%衰减、调音量与恢复、0.5秒渐变；受控关闭增益能力后原生媒体临时暂停/条件恢复。未冒领真实短TTS或手机能力。 |
| `output-regression.txt` | 真实输出模块单测回归及新增level渐变取消收敛、0音量恢复不解除静音通过。 |
| `player-regression.txt`、`session-regression.txt` | 原统一预算/事件目录与会话/通话占用回归通过。 |
| `h5-static.txt` | 19项原H5静态契约通过。 |

变更：新增bgm-ducking.js及两个专项测试；bgm-output/player/page、八HTML脚本接线、Nginx新脚本no-cache源码、BGM契约/manifest；没有偏好字段/API/上报增加。016语音源码未再变，原权限/归属/终态回归复用；新空活动实例下实际主页输出由本次Chrome补证。真实Docker更新仍在准备，Nginx未reload；017不宣称实际Docker/目标终端已通过。恢复继续018显式媒体/录音互斥，同时收齐016实际通话与目标浏览器条件。

### 9.23 STEP-018 普通媒体、录音与未知中断（2026-10-20）

状态`IMPLEMENTED`；AC-043本地SIM/Chrome通过，真实系统电话/其他应用及H5-M仍待验。定向盘点八类页面及自有非vendor前端脚本，没有独立普通带声媒体/录音产品入口；真实采麦/播放只在VoiceEntry/VoiceAudioTransport/VoicePlayback，不重复包装成普通媒体。bgm-media.js提供显式活动接口，八页通过BgmPage.mediaActivities接入，无新增业务录音/播放器或全站自动检测。

同ID当前活动去重，句柄按归属end/cancel/destroy；无声装饰不阻断，recording即使无声仍暂停。重叠最后一路才解除ordinary-media，不改用户意图/关闭；只有调用方明确resumeAllowed:true且当前所有条件允许才尝试恢复，未知许可保留手动入口，后来的允许不能覆盖早先未知结果。模块销毁释放但不复播；用户暂停、关闭、通话和其他阻断优先。

真实Chrome测出context.suspend后首个明确重试失败：native playing发生于suspended，随后context才running，被旧输出逻辑误判permission。context-resume-events-red.txt记录真实事件先后，resume-order-red.txt复现单测失败。bgm-output增加本次starting标记，等待同次resume/play完成后判定，不在该窗口把早到事件当新中断；真实外部中断仍要求手动恢复，旧pause已实际重新播放时忽略。该修复属AC-043当前恢复链，没有降低真实许可要求。

| 证据 | 结果与边界 |
| --- | --- |
| `step018/sim.txt`、`red.txt` | 实际controller+显式活动适配；静音排除、录音、重叠、同ID换代、未知许可、延迟结束、暂停/关闭/通话与销毁通过。 |
| `step018/browser.txt`、`browser-results.json` | 实际首页/公共API/隔离SQL/HTTPS AAC；另一原生Audio播放前BGM已停，多归属最后释放恢复；未知释放、原生pause、context.suspend均等待明确按钮恢复；关闭后不复播，偏好不改。普通活动是受控模拟，不是真实业务或OS电话。 |
| `resume-order.txt` | 早到playing与statechange、两次明确resume及之后实际中断通过；原单测与原生红测均保留。 |
| `controller.txt`、`output.txt`、`player.txt`、`session.txt`、`ducking.txt` | 受影响核心/输出/有限预算/会话/短TTS回归通过。 |
| `ducking-browser.txt` | 输出变化后重跑017原生增益/渐变/设备暂停，两模式通过；最新JSON仍在step017/browser-results.json，以本次输出版本解释，原017初次PASS日志保留。 |
| `h5-static.txt` | 19项原H5静态契约通过。 |

变更bgm-media.js、bgm-controller/output/player/page、八页脚本和Nginx源码规则、专项测试、契约/manifest；不改变业务API/账号偏好/通话协议。所有本地隔离浏览器服务已结束；016本地候选镜像构建、13接口导入、实际AAC转码均通过，迁移SQL/私有启动配置已准备，待用户对本地迁移与服务替换问题答复；当前没有业务库迁移或新OSS对象。恢复019单候选无声准备，保留016真实通话、Safari/手机及020/021部署完整证据。

### 9.24 STEP-019 单候选元数据准备（2026-10-20）

状态`IMPLEMENTED`；AC-049/077/085/092～096/099本项本地SIM/Chrome子条款通过，H5-M/Safari及真实部署缓存未计通过。新增bgm-preparation.js，八页由BgmPage建立并销毁。当前实际播放且主页面完成/可见/无阻断/目录有效时，采用剩余≤min(20秒,曲长四分之一)准备一个有效顺序下一首；省流量、离线、已知2G/3G或<1Mbps跳过，网络API不存在可尝试。SUG-018为本地采用值，5秒metadata预算；无候选play/整首解码/自建媒体库或偏好写入。

| 证据（execution/evidence/step019） | 结果与边界 |
| --- | --- |
| `red.txt`、`sim.txt`、`test_bgm_preparation.txt` | 缺模块红测后实现；实际模块+受控时钟/媒体验证单候选、页面优先、超时不循环、所有阻断/隐藏/关闭、网络跳过、目录/音频失效、迟到隔离及销毁。最终加入刷新期间不新发请求竞态断言。 |
| `browser-first.txt` | 原生测试发现catalogStatus=loading无条件取消有效准备，导致仅换封面也失效；原始失败保留，产品修正为有效旧目录保留原候选、刷新期间不新建。 |
| `browser.txt`、`browser-results.json` | 实际首页/匿名公共API/隔离SQLite/HTTPS AAC/Chrome155；只有当前+下一首请求，候选未play/无偏好改变；封面/改名刷新同对象，隐藏重排后真实下一首使用新目录；准备404不影响当前且正常按需下一首成功；saveData跳过；关闭在途metadata后无迟到播放。TTL/seek/rate/故障受控，不冒领手机或OSS缓存。 |
| `test_bgm_session.txt`、`test_bgm_player.txt`、`test_bgm_controller.txt`、`h5-static.txt` | 会话/目录预算/核心及19项H5静态回归通过；页面接线无新增偏好/业务接口。 |

变更：新增准备模块、SIM/原生测试，BgmPage/八HTML/Nginx脚本no-cache、BGM当前契约和manifest。准备对象不授权实际播放，不绕开目录/普通故障链；同一候选失败不批量尝试。真实缓存验证交020；所有新增诊断只在本地，实际匿名请求未附认证或cookie。参数与来源未改PRD；恢复020部署媒体链。

正常网络补证（2026-10-21）：020/preparation-formal-live-check.json记录实际正式Chrome/Fast4G两曲目录唯一候选ready、A同generation连续播放与自然切B，偏好快照不变；不是实际手机、长歌单或ready阶段取消/声学静音新证据。既有受控与隔离浏览器断言继续按原范围复用，STEP-019仍IMPLEMENTED、终端待验。

### 9.25 STEP-020 本地部署与实际环境核对（2026-10-21，继续验收）

状态`IMPLEMENTED`（2026-10-21最新：按用户决定完成本版开发交付，本地运行及局部真实链路证据保留；未验项见§9.28）。仅下列已完成部分计证据。用户明确批准“允许本地迁移和服务更新”；动作限本地v9g→v9h、backend替换和Nginx重载，不含新OSS上传。迁移前查询active voice=0、Redis voice lease=0，版本v9g且无BGM表；25文件候选摘要匹配，全部旧环境变量/挂载/回环8000端口核对保持。旧Docker inspect（含凭据）仅保存在0600私有`/private/tmp/bgm-local-candidate-ip6osmys/before-update.private.json`，不得加入仓库或输出。

| 证据（execution/evidence/step020，除注明） | 已验证结果 |
| --- | --- |
| `deployment-before.json`、`migration.txt` | 备份迁移位置后，候选容器执行`alembic upgrade v9h_bgm_001`成功；只新增五BGM表与两条初始化。MySQL DDL非事务，未执行downgrade。 |
| `backend-update.txt`、`deployment-after.json` | backend替换为`lxm_for-backend:bgm-candidate-20261020`；Nginx语法通过并reload。实际版本v9h，asset/operation/track为0、catalog/slot各1；原环境和挂载保持；/api/bgm/catalog为200有效empty/no-store，BGM/voice-entry脚本与工作区匹配且no-cache，原/api/feed/list公开读取code0。 |
| `../step016/local-candidate-manifest.json`、`local-candidate-import.txt`、`local-candidate-media.json`、`local-migration.sql` | 复用构建前25文件最小叠加、13接口导入、FFmpeg7.1.5真实AAC转换与迁移SQL审核；源文件摘要未变，候选产物未重建。 |
| `docker-chrome-empty-catalog.png` | 实际现有Chrome访问本地Docker，空歌单文案和禁用播放/下一首正确；原目录404已解除。Chrome扩展鼠标输入两次超时，键盘操作成功，不计产品失败。 |
| `test-account.json`、`docker-chrome-logged-in.png` | 按用户许可通过正式register创建普通验收账号user_id=2，并通过正式弹窗登录；未改user_id=1/未签发冒用Token。首个测试用户名含保留词test被拒后改bgmqa；凭据只在私有文件，不在证据中。 |

仍待：新OSS实际媒体发布/有图无图及版本更新/真实HTTP与Range缓存、跨域输出与弱网按需起播、跨实例绝对预算与资源故障、真实BGM/通话及Safari/手机。当前实际库无BGM素材，不能据空目录通过声明媒体或通话验收完成。没有新的OSS写入/ACL变化/朋友圈资源修改，也没有容量通过声明。真实闭环的操作方案准备好后单独取得必要授权；管理登录仍须合法凭据或用户自行登录。上述源配置已实际生效，历史017/018“未部署”陈述仅是当时记录。

补充环境证据（STEP-020，2026-10-20）：`nginx-runtime.txt`为新建internal网络内实际仓库Nginx+ASGI探针，100MiB完整body通过、100MiB+1声明长度413、真实chunked首块在上传结束前到后端，延迟期间目录GET可响应，独立5MiB封面请求通过。只证明传输层，未冒领媒体内容校验或实际120/300秒耗时。

`resource-runtime.txt`在实际候选镜像、network=none、1CPU/768MiB、1MiB受限tmpfs中7项通过：接收磁盘满导致明确失败且槽释放/无资产尝试；真实缺ffprobe失败；替代解码子进程继承1GiB RLIMIT_AS，2GiB申请触发MemoryError后失败回收；超时/worker崩溃/API owner SIGKILL均证明子进程停止后才回收锁。SQLite/路径均临时隔离，不含真实OSS。首次4项失败来自Docker默认tmpfs noexec使故障注入脚本无法启动，原日志`resource-runtime-noexec-red.txt`保留（省略合成Token）；只修正临时测试挂载为exec后原断言通过，未改产品/业务容器权限或测试标准。测试临时容器及网络结束均精确移除，原业务继续运行。

`media-acceptance-plan.json`授权仍为两条30秒音频、两张512×512 WebP，最多4个对象，正式后台上传/启用/换图/隐藏及满24小时精确清理。用户已手动完成A上传；后台试听成功，正式H5因实际CORS缺失报错，已隐藏。1个音频对象精确归属、摘要、操作及等待时间记录于`real-media-ownership.json`、`real-media-hidden.json`；尚未创建第二音频或封面。原Chrome文件桥和扩展设置页策略失败保留为历史，不绕过扩展策略；当前关键依赖为实际Bucket CORS，读取规则403；用户已确认无规则，具体配置方案待单独授权。

本轮新增实测：`absolute-receive.txt`为候选镜像中实际Uvicorn/socket慢请求，保留120秒接收和300秒总预算，120.082秒后明确`failed/receive_timeout`；同操作重放不延长期限、新操作明确busy、接收期间公开目录可读，槽释放且临时文件清理，1 passed。此处是隔离SQLite环境的真实计时，不声称已验证实际业务库跨实例或完整300秒处理链。

`storage-faults.txt`在同一候选镜像通过真实SDK PUT/HEAD和本地HTTPS GET注入错误MIME及12秒无响应：分别1.208秒`remote_mime`、11.078秒`storage_unknown`，2 passed。均未发布曲目，原deadline保持、槽释放，已写入对象留有精确归属及pending清理；使用本地对象服务，不是现有OSS故障演练。

跨域新增测试暂未通过：`cors-browser-headers-red.txt`保留原请求头采样断言失败；此前播放及增益RMS断言成功不代表整条通过。脚本采样由headers改为allHeaders，尚未复跑，仅语法核对。临时HTTP夹具被产品HTTPS地址校验拒绝，没有放宽产品约束；临时HTTP/页面探针改动已撤回、进程结束。仍待真实HTTPS媒体/CORS、缓存及目标终端验收。新增测试源码和夹具摘要见020/source-sha256.json。

两实例恢复实证（2026-10-20）：`multi-instance-runtime.txt`在候选镜像内运行两个独立Uvicorn/API进程及各自真实5秒恢复循环，共用专属MySQL8和同一临时目录。音乐/封面并发仅一接纳、另一429/20205；活动源跨另一恢复周期仍保留，公开目录读保持一致；真实SIGKILL接收进程后重启，原操作转`failed/worker_interrupted`，截止时间不变，持锁进程退出后才删除目录并释放槽。另明确接纳一次封面，证明占用期间新音频忙碌，封面进程崩溃恢复不改变已发布音频及公开目录。内部用例1 passed，外层运行与清理检查1 passed；主机跳过的内部用例不是漏验，由容器实际运行。初次夹具使用未安装aiomysql导致失败，保留`multi-instance-driver-red.txt`；修正为部署实际asyncmy后通过，没有增加生产依赖或放宽断言。`multi-instance-audio-only.txt`是补充封面接纳断言前的有效局部记录，最终以完整runtime文件为准。

上述MySQL、网络、runner均为本测试新建且已精确移除，无业务库/OSS写入。就绪曲目只是隔离库夹具，未声称其远端播放或容量通过。覆盖AC-070/074/076的两进程接纳、活动文件保护、接收进程死亡与恢复子范围；真实媒体、跨主机卷不可达、HTTP缓存、终端/通话及完整代理长链仍保留待验。

原定编码时限实证：`absolute-process.txt`在无网络Linux候选容器中用真实ffprobe解析合成WAV，将ffmpeg可执行文件替换为真实休眠子进程作为挂起注入；产品worker、父子进程锁、120秒编码上限、180秒处理/300秒操作预算和持久结果均保持原值。120.282秒后返回`failed/processing_timeout`，PID已不存在、槽释放、临时目录为空、曲目未发布；处理期间重放不改deadline、新操作429且公开目录可读，1 passed。资产尝试保留pending精确归属，没有实际OSS写入。该结果证明原定编码上限和收尾，不宣称真实高复杂度音频容量、完整代理300秒长链或现有OSS挂起已验收。

实际媒体与修复（2026-10-20）：`real-media-http.json`记录200全文件366438字节、SHA256与已登记asset一致、audio/mp4、206前1024字节一致、304空响应及30天immutable缓存头；没有ACAO。Chrome后台试听currentTime=14.86269/30且未暂停；正式localhost:8000前台显示“音乐播放失败，请重试”，见`real-media-cors-failure.png`。这证明实际跨域发布条件未通过，不能把后台试听作为H5成功。`oss-cors-before.json`只读GetBucketCORS返回403，未更改规则。

发布校验修复：新增BGM_MEDIA_ORIGINS显式实际前台Origin配置；音频全文件读取带首个Origin，再对全部来源核对真实206/Content-Range/MIME/前1024字节及ACAO，仍在原worker预算内；配置缺失在PUT前失败，CORS/Range错误留精确资产pending清理并禁止启用。图片路径保持原验证。`remote-contract-red.txt`19失败复现旧缺口，`remote-contract.txt`最终24 passed；`remote-contract-pipeline.txt`真实FFmpeg/SDK/本地HTTPS音频与封面链36 passed，含错误CORS/Range不就绪、不启用、槽释放和原deadline保持；不是实际Bucket正确配置证据。`cors-gate-image-test.txt`最终镜像24 passed。已部署单文件修复镜像lxm_for-backend:bgm-cors-gate-20261020，新增本地来源localhost:8000和127.0.0.1，其他环境/卷/端口保持，未迁移数据库；Nginx检查及重载完成，运行摘要/静态脚本一致，两入口目录空，见`cors-gate-deployment.json`。首次构建缺amd64参数失败，按原镜像架构修正后完成。历史ready记录未追溯改写；测试A保持隐藏直到真实配置和H5输出复验，下一次重启应沿用新私有compose路径。

CORS与朋友圈核对补充（2026-10-20）：原`cors-browser`用例已修正请求头采样并实际重跑，`cors-browser-final.txt`及`cors-browser-results.json`证明Chrome155跨localhost/127.0.0.1 HTTPS AAC在正确CORS下gain输出RMS=0.0263178518111713；缺CORS时resource错误、全部暂停且playing事件0。测试进程终态0且脚本正常关闭独立浏览器及HTTPS夹具；不替代现有Bucket的正确配置证据。`cors-current-check.json`当前两个本地来源都返回206正确片段但无ACAO。用户明确“无规则”并允许查看朋友圈相关链：`feed-cors-readonly.json`记录运行后端图片服务摘要与工作区一致，SDK服务端上传、普通img展示；实际3张图片成功解码，所查一张HEAD200/image-webp且无ACAO，未生成/上传或更改任何朋友圈资源。已准备`oss-cors-change-plan.json`：仅localhost:8000与127.0.0.1两个Origin，GET/HEAD，Range请求头，ETag/Content-Range/Accept-Ranges暴露头，600秒预检缓存及Vary Origin。Bucket级规则不能限定bgm前缀，匹配来源下已有可读图片也适用，但不改ACL/对象/后端上传/账号权限。由于原授权排除Bucket设置变更，具体配置授权问题已提交；收到前不修改。规则确认后先匿名读取核对，再按原测试授权短暂启用A复验，失败隐藏，继续剩余对象上限内流程。

授权配置与正式复测（2026-10-20 14:31 CST）：用户明确批准后通过OSS控制台新增精确规则，保存前核对所有字段、保存后列表核对；`oss-cors-configured.png`留存配置，`oss-cors-after-http.json`验证两个来源200/206/304/HEAD/OPTIONS、ACAO/Vary及原音频摘要，朋友圈已有图片HEAD正常。本轮没有新增OSS对象或源码修改。实际H5显式重试仍报播放失败，尚不能区分缓存或其他输出问题；后续浏览器工具中断，未取得成功播放证据，AC-075保持FAILED_DEPLOYMENT但剩余原因描述更新。A已重新启用，最后只读确认仍在公共目录版本3；请求用户正常隐藏，尚未获结果，旧隐藏资格不再适用。详见`cors-after-browser.json`与§9.4；后台试听、HTTP读取与实际Web Audio输出分别计证据。

原地址缓存与正式闭环补充（2026-10-20 14:56 CST）：详见§9.4最新恢复记录及`browser-media-cache-diagnosis.json`、`home-real-media-retest.json`。正式首页播放/暂停/继续和真实10秒通话后的保持关闭/人工重开已通过本地Chrome冒烟；未改产品源码或新建OSS对象。A已正常隐藏至目录6，最早清理2026-10-21 14:54:55.518855 CST。封面选择仍受扩展文件桥阻塞，已保留后台表单；临时诊断静态文件与标签已清理，实际终端/两曲换图/Range缓存完整验收仍未完成。

封面A实际验收补充（2026-10-20 16:03 CST）：详见§9.4最新恢复记录、`real-cover-a.json`及`cover-a-browser.json`。批准的542字节、512×512 WebP通过两个来源CORS/条件缓存及正式首页解码显示；隐藏补图未启用或改变音频版本。A已正常隐藏至record11/catalog8，最早清理2026-10-21 16:00:32.727249 CST。当前1音频/1封面；第二张封面替换、第二曲、完整缓存与目标终端仍待完成。未修改产品源码或运行镜像。

Safari实测补充（2026-10-20 16:14 CST）：参见020/safari-real-output.json和safari-output-check.txt，实际Safari 26.5已验证增益、零音量不暂停和人工恢复输出。只补核心证据，不替代正式面板/降级/持久化/手机验收，STEP状态不提前VERIFIED。

本轮补充（2026-10-20 16:48 CST）：`metadata-cache-rename.json`为实际改名/恢复后的URL/版本/ETag/304证据；`safari-formal-flow.json`为真实Safari首页/朋友圈局部正式流程，截图`safari-formal-original-playing.png`、`safari-formal-zero.png`、`safari-formal-final-closed.png`、`safari-feed-playing.png`均在本节证据目录内。初始document.hidden及Mac锁屏由用户恢复，不能归为媒体格式失败；没有绕过保护。临时只读诊断源码已恢复且正常刷新移除存活显示。最终A record17/catalog14隐藏、仍1音频/1封面；`real-media-hidden.json`、`real-media-ownership.json`更新最终时点，最早清理2026-10-21 16:47:16.343166 CST。原环境/受控测试仍有效复用；双曲/替换图、浏览器缓存/Range、其他页面/真实语音分支/手机及满期清理仍待，STEP-020保持IN_PROGRESS。

补充（2026-10-20 17:06 CST）：实际Safari访客设置和原三个登录入口检查通过，正常登录测试账号2已进入记忆页；私有页播放未执行。具体范围、后台会话失效及再次锁屏、尚待退出账号见§9.4最新记录与020/safari-settings-guest.json、safari-guest-entry-gates.json、safari-private-pages-probe.json。只读核对启用未生效，A仍隐藏record17/catalog14，当前无活动处理，等待期不变。

补充（2026-10-20 18:26 CST）：§9.4本轮恢复新增实际Safari记忆/关系/聊天/设置局部流程与正常退出，见safari-private-pages-visible.json及截图；临时探针恢复回执保留。新增真实封面B替换和第二音频：real-cover-b-second-audio.json、second-audio-cover-b-runtime.json、second-audio-cover-b-http.json、second-audio-admin-preview.json；cover-b-live-observations.json区分保存时连续播放、人工暂停/恢复以及曲终自然刷新，cover-b-home-image.json与cover-b-home-playing.png证明新图实际512px解码。当前2音频/2封面，预算0；旧图等期retired，未清理。双曲准备/切换、真实浏览器缓存/Range、手机和满期普通删除尚不能计完成；沿用历史有效单元/受控/真实输出结果，不重复重跑。

中断后收尾补记（2026-10-21）：实际双曲播放/暂停下一首/默认唱片/3g跳过见two-track-live-check.json及三个live原始记录；最终关闭、普通隐藏及新标签空态见two-track-final-hidden-runtime.json、two-track-final-empty-home.json和截图。只读恢复回执two-track-resume-20261021.json确认前提不变；real-media-hidden.json、real-media-ownership.json、media-acceptance-plan.json同步当前2+2归属及等待期，旧时点仅作历史。两探针恢复并移除，夹具保留tests；产品代码和运行镜像未改。当时手机/缓存/Range/正常准备/满期清理未完成，STEP为IN_PROGRESS；现以本节最新状态为准。

代理串联绝对接收实证（2026-10-21）：本轮新增tests/test_bgm_nginx_deadline.py，用当前业务镜像同digest及已运行Nginx逐字一致配置，在新internal网络内串联真实ASGI/API（lifespan off）和隔离SQLite，无宿主公开端口或业务/OSS/Provider连接。声明8字节，首次2字节后每20秒给1字节，100秒共发7字节；接纳后120.088秒经Nginx返回HTTP200、持久failed/receive_timeout，不是代理408/504。原120/300秒deadline未变，同键重放不延时，新操作429/20205；同代理查询结果一致、槽free、work目录空、资产0。最终1 passed in121.27s；仅本轮容器/网络移除且absent确认。证据020/nginx-deadline-live-check.json及runtime/results/原始日志，运行器字节快照保留，未改产品源码、业务库或运行配置。

首轮新测试于1秒附近错误要求目录始终200，实际隔离夹具刻意拒绝Redis，本地1秒缓存过期后处于2秒回源冷却返回503/20207/Retry-After2。对照未修改PRD AC-053“有界回源或明确失败”和BR-029及实际cache代码确认原预期过强；保留assertion-red日志和精确清理回执，仅修正为3.5秒内成功或明确503（本轮0.004秒），绝对计时/终态/回收断言未弱化。不是产品缺陷修复或实际业务Redis故障演练。按systematic-debugging定位、verification-before-completion核对当次原始结果与源码摘要；历史隔离MySQL/资源/单独接收与编码证据按有效范围复用。新增证据覆盖AC-074/076的代理串联慢接收子项，不替代完整300秒处理/前端330秒、手机或整体DEP，STEP020/021仍IN_PROGRESS。

### 9.26 STEP-021 验收证据索引与参数核对（2026-10-21，继续验收）

状态`IMPLEMENTED`（本版证据／契约整理完成，按用户决定交付完结；完整跨环境验收保留，100项结果不提升）；持续整理既有证据并回填实际媒体/语音验收结果，前置未完成项保持原状态，不跳过最终验收。`execution/evidence/step021/acceptance-index.json`从未修改的PRD逐行提取100项AC及§5.2责任范围，关联当前唯一进度节、已有证据文件和摘要，逐项列出尚缺环境/范围；不是第二进度文档。`index-check.txt`只证明100/100索引完整，不证明100项功能通过。AC-042按其明确的SIM范围记PASS_SIM；AC-075原FAILED_DEPLOYMENT已由原地址缓存诊断及正式首页播放复测解除，改为PARTIAL_EVIDENCE，保留目标终端/Range缓存/异常分支待验；现96项PARTIAL_EVIDENCE、3项NOT_RUN_FULL_FLOW，未将历史STEP局部VERIFIED泛化到整条跨环境AC。

§9.5.7已按实际代码和各STEP记录回填21项建议采用状态：保持96kbps目标、M4A/AAC-LC、300秒/4MiB硬限制；渐变0.5秒、活动衰减0.25、检查点2秒、目录300/1800秒、Redis60秒、统一30秒失败链、处理1槽/300秒总预算、隐藏24小时、图片512px及单候选准备均标明依据和未验证环境。没有把参数建议变为新的PRD硬要求，也没有将图片200KiB优化目标当拒绝门。

完整无图/有图上传→试听→启用→目标终端播放/准备→换图→隐藏→等期清理仍未执行；当前源实现与本地Docker生效已区分，A已完成上传/试听/启用/原地址播放/暂停继续/10秒真实语音/挂断保持关闭/人工重开/再次隐藏；CORS HTTP与原地址缓存故障已解除。封面文件选择、第二曲、Safari/手机、浏览器Range缓存复用、完整真实语音异常场景与部分DEP故障仍未验。未新增上线发布或容量承诺，不能标完成。

恢复补充（2026-10-20）：实际语音runtime loader仅做配置核对，未采麦/发起Provider通话：master enabled，id=1允许、id=2被门禁阻断，无technical fallback，见020/voice-eligibility.json。该登录与四对象OSS方案问题随后已获用户答复并授权，详见§9.25当前恢复说明。未更改开放名单，未重置账号；文件桥旧阻塞已由手动上传解除；此为历史恢复补充；CORS与后台登录现已解决，当前依赖以§9.4的14:56记录为准，同一媒体批次授权保持有效。shell自动审批没有拒绝本轮测试；浏览器URL策略另行拒绝扩展设置页访问，未绕过。

021/contract-check.json：BGM 19项路由/模型/管理页surface映射及相关链接/行数/源码路径核对通过，PRD与§1～8摘要不变。全仓正则扫描另发现非BGM memory/system_monitor行号差异、混入docstring示例及漏掉混合基类模型，记录原差异且未重写无关manifest；没有宣称全仓文档检查通过。既有442/400行数告警和历史inventory失败仍保留。必要BGM数据契约/部署说明已同步实际本地迁移和最小镜像状态。

本轮索引补充（2026-10-20 16:48 CST）：加入实际Safari首页/朋友圈播放、零音量及关闭/刷新局部流程、可见性恢复和实际元数据改名条件GET证据；AC结果不因局部证据整体提升，仍96项PARTIAL_EVIDENCE、1项PASS_SIM、3项NOT_RUN_FULL_FLOW（078/097/098）。AC-097已有改名URL/ETag/304这一子项，完整浏览器请求/换图/新版本仍未执行。最终隐藏期限及对象归属索引同步最新回执；不以索引完整冒充验收完成。

阻塞时点索引修正（2026-10-20 17:12 CST）：AC-065/086/090/091/097/098的旧“0封面、CORS后仍失败、待用户隐藏”描述已按现有实际证据更新为1音频/1封面、CORS/原地址故障已解除、A record17/catalog14隐藏及最新等待期；分别保留删除故障、换图版本、实际浏览器缓存/Range等尚缺范围。无AC结果提升，无新功能验收或业务变更。

索引恢复补记（2026-10-21）：补入真实封面B/第二曲、双曲/弱网和最终隐藏的AC子范围；六条旧1音频1封面及旧隐藏期已更新为2+2和当前门。摘要/目标链接只证明索引完整，不代验收；仍96项PARTIAL_EVIDENCE、1项PASS_SIM、3项NOT_RUN_FULL_FLOW。旧三轮锁屏审计已解除，本轮有记录恢复进展，不沿用旧阻塞计数。

本轮正式准备索引补充（2026-10-21 11:49 CST）：加入020/preparation-formal-live-check.json及原始事件/网络与收尾证据。AC-092正常网络两曲准备子项已有实际Chrome证据；长歌单、Safari/手机和其余规定分支未推广。AC-093仅新增偏好快照不变/自然切歌，不宣称新声学/调用检查；AC-094未在ready时暂停，不新增取消结论。新隐藏门为2026-10-22 11:47:52.612573 CST、catalog25/A24/B6/2+2。100项状态仍96 PARTIAL_EVIDENCE、1 PASS_SIM、3 NOT_RUN_FULL_FLOW；原生设置/临时源码/本轮标签均已收尾。详情以§9.4本轮和证据回执为准。

本轮索引补证（2026-10-21）：020/nginx-deadline-live-check.json加入真实Nginx/应用慢接收120.088秒子范围及首轮测试预期错误记录；原有效断言及失败证据保留，100项状态不提升。§9.5.7按已取得实际证据同步SUG-010/012/015/018/019/020的采用与待验范围，未修改候选或PRD阈值。没有新业务、OSS或端口变更，目标未完成。

文档写入守卫补记（2026-10-21）：同步SUG实际采用列的脚本曾误匹配§1～8同编号表格的六行末列；只读前缀SHA断言立即发现，未据此更新通过结论。仅按签发前驱中对应六行恢复，并以既定只读前缀SHA=6ff8adc315012b40bcee7073c83535191d343ba73ec740d5fa855c1b6a7814e7逐字节核验恢复精确。该前驱仅用于六行恢复，不作为新需求来源；未读迁移基线或受禁历史目录。实际采用结果仅保留§9.5.7，本次交付的PRD及§1～8最终字节均与已知摘要相同。后续此类更新须先分割只读前缀，再只在§9操作。

本轮语音索引补证（2026-10-21 12:23 CST）：AC-037/039及完整闭环AC-078关联020/voice-timing-live-check.json；首次实际采麦/输出前停止、32秒挂断/人工重开、等待接听取消已取得，旧“完整采麦时序/取消待测”描述按实测更新。其余真实拒绝权限/失败重连/单轮结束、手机与完整DEP/闭环保留。100项结果仍96 PARTIAL_EVIDENCE、1 PASS_SIM、3 NOT_RUN_FULL_FLOW；新精确清理门与所有已知引用摘要同步，不凭局部证据提升全项结果。

本轮两阶段预算索引补证（2026-10-21）：AC-074/076关联020/staged-budget-live-check.json，实际Nginx/慢传/AAC/原处理计时及回收子范围通过；本地故障存储函数、SQLite、未实际耗尽300/330秒等限制明确保留。AC-039新增权限方案原状态和未执行/手动解锁依赖证据，仅PREPARED_NOT_RUN，不据准备工作提升结果。100项状态保持96 PARTIAL_EVIDENCE、1 PASS_SIM、3 NOT_RUN_FULL_FLOW；当前业务资产及清理门未变。


### 9.27 已确认UI对齐（2026-10-21，C01–C07 / A01–A13）

用户已明确批准按链接会话“制作背景音乐 UI Demo”及本轮差异清单实施：设置页保留浅色、只改BGM区域；后台按demo对齐，同时保留人工试听确认、完整歌单提交和版本冲突处理。本节复用唯一进度记录；不修改PRD或§1～8，不提升原STEP-020/021全环境验收状态。

- C01–C07：共用SVG；播放音柱角标/呼吸光晕；玻璃面板反光与星光；歌单序号/当前播放音柱与完整长名称；细轨音量；横向气泡操作及真实联合边界避让；浅色设置中自动播放在前、音乐淡入淡出在后，并说明本机保存与已知能力降级。播放核心、偏好键、权限和原页面生命周期保持原机制。
- A01–A07/A10/A12：概览、全局汇总/默认曲、实时搜索/四类筛选、开关/星标/完整歌单行内箭头、紧凑试听/更多菜单、状态与清理分类、共享默认record.svg、底部真实媒体试听条。observer仍可查看状态，相关控件禁用且不被共享write-action隐藏器抹掉。发现并修复主动暂停未完成play造成误报、错误后需两次点击重试的竞态。
- A08–A09/A11/A13：右侧上传抽屉、拖入/文件卡/名称计数/实际阶段、可选封面先选后独立提交；失败保留候选、版本冲突须刷新核对；清理失败保留分项，原弹窗GET刷新后明确重试剩余。未知结果仍沿用原操作ID，不自动重建曲目或删除。
- 读取接口增加filter/sort、全库summary/default_track、有限安全failure_category与audio/cover分项cleanup_summary，旧参数兼容、GET无写。同步当前BGM接口/管理页及H5界面契约；manifest和surface只更新本次BGM路由行号，没有重写非BGM差异。

本轮验证：pytest读取20项、目录/封面/清理/schema55项、H5静态19项通过；新增/定向Node测试35项通过（主列表9、媒体流程10、完整排序15、客户端状态1），客户端原偏好/输出测试及相关语法检查通过。原5份后台浏览器脚本仅更新选择器与语法检查，本轮未独立重跑。27首跨页排序、版本不匹配不PUT、未知原ID恢复、封面冲突/失败保留及observer由定向测试覆盖。

CUA实际浏览器使用正式HTML/JS、真实BGM路由、隔离SQLite与本机对象存储：客户端390px播放/暂停/切歌/音量拖动、320px设置/横向气泡/拖动/刷新保留、667×320横屏底部可达；后台1440px概览/筛选/试听，默认替换、试听后启用、22首完整歌单行内移动、封面remote_unreadable失败保留并成功重试、清理3成功1失败后只重试剩余1项、390pxobserver菜单与只读状态。截图和结构化结果见本轮证据（本地留存，未随本次提交；原引用：`execution/evidence/ui-alignment-20261021/results.json`）。

限制：此机缺FFmpeg，音频上传实际返回dependency_unavailable，已补准确环境提示；本轮不计音频转码成功证据。原生试听用合成60秒WAV，仅夹具媒体URL转同源HTTP，不代表生产HTTPS/CDN/CORS。音频成功后自动接续封面、未知回执与冲突等分支使用受控状态/API测试；不冒充全部浏览器实测。减少动态/隐藏停止使用状态测试，本轮未修改系统偏好。未部署、未触及真实业务库或OSS，真实手机/Safari与原完整环境验收仍沿用原进度。已保存源码和验收证据，不产生Git提交。


2026-10-21 15:52 CST 本地Docker生效补记：用户明确要求“更新现有 Docker 让更新生效”。以当前bgm-cors-gate镜像为基础，仅叠加本轮3个BGM后端文件，构建 `lxm_for-backend:bgm-ui-alignment-20261021` 并替换现有backend；实际新容器69c7d9fb06ea已启动。原私有compose临时文件已不存在，依据运行容器重建私有运行配置，完整保留环境变量、127.0.0.1:8000端口、网络和BGM运行卷；未修改仓库compose/.env或进行迁移。MySQL/Redis/Nginx仍为原容器且运行，重启前无活动BGM操作。

实际验证：3个新文件容器SHA与源码一致；环境指纹/端口保持；无网络临时容器路由导入通过；8000与Nginx公开目录均HTTP200/code0；实际OpenAPI出现filter/sort。复用用户当前登录标签刷新，汇总由“—”恢复为总数2/启用1/未启用1/失败0、默认曲B、catalog30；点击“已启用”仅1行、全局总数仍2，返回全部2行。仅GET及页面读取，无曲目状态变更。证据：Docker更新（本地留存，未随本次提交；原引用：`execution/evidence/ui-alignment-20261021/docker-update.json`）；截图见同目录docker-update/live-admin.png。本次确认本地部署已生效，不提升原完整媒体/手机验收结论。后台结构核对：46个后台HTML均加载admin-common.css；BGM额外bgm-admin.css覆盖头部/侧栏色调，仍使用同一renderHeader/renderSidebar与权限代码，不是独立插件。

<a id="bgm-v13-closure"></a>
### 9.28 BGM V1.3 版本完结与契约汇总（2026-10-21）

**交付结论：本版开发交付完成，验收有保留。** 用户在人工测试后先表示“我认为可以完结这个版本了”，随后明确要求“那你做版本完结，别忘了契约文档进行汇总整理”。该决定接受按当前可用范围收口及未验项延期，本轮不再扩展功能测试。人工测试只登记为用户反馈和结项决定；未提供的设备、浏览器版本及场景不补写为逐项通过。PRD 与§1～8保持原字节和要求。

版本交付状态与严格验收状态分别记录：STEP-001～006/008共7项VERIFIED，其他项已实现或完成本地证据整理，尚缺范围继续保留；100项AC仍为96 PARTIAL_EVIDENCE、1 PASS_SIM、3 NOT_RUN_FULL_FLOW。本版完结不重写这些证据结果，也不要求为同一已有结果反复执行测试。

#### 本版实现与权威契约

| 范围 | 现行事实与契约 |
| --- | --- |
| 管理库／权限／审计 | 音频上传与原操作恢复、试听、名称／启用／默认／完整排序、独立封面、专属资产手动清理、S/O写与V只读；[接口与播放器契约](../../contract/current/bgm/api.md)、[管理页契约](../../contract/current/bgm/admin-ui.md) |
| 数据／处理与存储 | 五表、v9h迁移、全库单槽与绝对预算、不可变对象归属、隐藏等待和逐对象结果；[数据契约](../../contract/current/bgm/data.md)、[本地部署说明](../../ops/docker-admin-deploy.md) |
| H5音乐与设置 | 公开主页唱片／歌单面板、内容页气泡、五项本地偏好、跨HTML会话、有限目录缓存、输出降级、渐变与活动衰减、单候选准备；[BGM契约](../../contract/current/bgm/api.md)、[H5接入](../../contract/current/h5-app/api.md) |
| 真实语音互斥 | 准备先停播并关闭，采麦／输出前生效；归属清理仅解除阻断，取消／挂断／回复结束不自动重开；[语音接入契约](../../contract/current/realtime-voice/api.md#bgm-audio-ownership) |
| UI对齐与运行生效 | 本节保留§9.27 C01–C07/A01–A13及其定向测试／隔离浏览器证据；UI证据（本地留存，未随本次提交；原引用：`execution/evidence/ui-alignment-20261021/results.json`）与实际Docker更新（本地留存，未随本次提交；原引用：`execution/evidence/ui-alignment-20261021/docker-update.json`）明确各自边界 |

本轮契约整理集中更新上述5份现行正文和部署说明，清除把历史局部验证当当前全部状态的过时表述；保留接口、状态、权限、偏好键及原等待规则。`docs/INDEX.md`、`docs/design/README.md`与manifest补齐BGM检索／关联入口，不新建第二份进度文档，不移动／覆盖历史资料和迁移快照。

#### 验证复用与当前运行版本

已有有效证据包括真实OSS音频／封面与换图、Chrome及Safari的播放／音量／局部页面／HTTP缓存／Range、Chrome真实采麦及输出前停播、32秒挂断／等待取消和实际回复结束；另有真实Nginx 120秒接收、慢接收加处理原预算、MySQL／Redis／FFmpeg及跨实例隔离结果。各自限制与命令沿用100项AC证据索引（本地留存，未随本次提交；原引用：`execution/evidence/step021/acceptance-index.json`），不合并冒称完整端到端或容量通过。UI对齐后改变的页面／列表以§9.27的新证据补充；旧功能证据保留原来源版本与适用范围。

结项只读核对当前运行快照（本地留存，未随本次提交；原引用：`execution/evidence/step021/closure-runtime.json`）：本地backend为`lxm_for-backend:bgm-ui-alignment-20261021`，摘要`sha256:16ca91cbb5bbe50ec10e379c98f82fb5f0727924d9df41ef11e2905cc2437039`，与§9.27部署证据及三份后端源码摘要一致；backend/nginx运行，仍仅回环8000/80端口；活动通话0、处理槽free。当前catalog39含用户歌单及默认曲，原两条验收曲目仍隐藏。没有重启、迁移、对外发布或操作后来添加的业务曲目。本轮只做文档、摘要、关联及运行状态核对，没有重跑功能测试或新增OSS对象。

#### 明确保留的验收范围

| 保留项 | 本版处理 |
| --- | --- |
| 实际iPhone／Android／微信与软键盘、安全区、系统中断 | 延期保留；桌面窄视口和本次未说明设备的人工反馈不替代指定终端证据 |
| 真实拒绝麦克风、成功重连恢复、完整连接失败／未知创建清理 | 延期保留；已记录的短暂reconnecting后silence_timeout不作为成功重连，第二次离线创建被中断不计完整通过；未执行保存麦克风权限更改 |
| 其他实际普通媒体／录音／短TTS、长歌单与准备取消边界 | 按100项索引remaining逐条保留；已有受控／局部证据可复用，未覆盖部分后续按实际问题补验 |
| 预发布／生产与主业务容量、完整业务闭环 | 未在本轮执行；本地和隔离环境结果保持其限定 |

这些是用户接受延期的验收保留，不是新增产品功能、删除PRD要求或确认已知产品缺陷；不因此建立后台监控、定时任务或新的持续测试流程。

#### 环境收尾与精确资源待办

临时主页源码已精确恢复（SHA256 `aa6c491992a28d7468ce0e2bfea25e919f3429060791556bb4d648b831e55acd`），served观察脚本已移除，原测试页面不再存活。最后中断留下的DevTools收尾本轮已完成：仅在新建about:blank页确认No throttling、Disable cache=false，并将设备工具栏恢复原ON；随后关闭DevTools及该空白页。只读状态与截图见恢复回执（本地留存，未随本次提交；原引用：`execution/evidence/step021/browser-settings-restored.json`），没有更改保存的麦克风权限。Safari临时开发者功能此前已恢复关闭。

原授权批次仍为2音频＋2封面、无剩余上传预算、未执行整批删除。结项只读快照中A record30，最近隐藏为2026-10-21 16:29:02.654475 CST；B record8，最近隐藏为16:28:57.118395 CST。后续重新启用／隐藏使旧13:48等截止失效，**整批普通清理最早为2026-10-22 16:29:02.654475 CST（可按16:30后操作）**。到时仍需走正式后台重新核对服务端资格及原曲目／四资产归属；只精确处理原批次定位（本地留存，未随本次提交；原引用：`execution/evidence/step020/real-media-ownership.json`），不扩大至用户当前歌单。未到期先保留，未创建定时清理或自动提醒。后续再启用再隐藏仍须重新计时。

**本版结项完成；剩余验收与满期资源清理按本节保留，不登记为已通过或已删除。** 结项证据、当前源码／契约摘要与文档核对见版本收尾回执（本地留存，未随本次提交；原引用：`execution/evidence/step021/version-closure.json`）。

用户最后补充：“直接收尾吧，删除这个问题记录下就可以了”。测试资源删除据此仅登记为后续待办，本轮不等待满期、不启动删除或新测试；本版交付结项完成。
