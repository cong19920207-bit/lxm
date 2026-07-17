# PRD-管理后台观察者与安全加固-v1 开发进度追踪

> 文档路径：`docs/progress/PRD-管理后台观察者与安全加固-v1_progress.md`  
> 创建时间：2026-07-15  
> PRD 来源：`docs/design/PRD-管理后台观察者与安全加固-v1.md`（v2.3）
> 项目配置：`docs/design/PROJECT_CONFIG_林小梦.md`  
> 漏洞专档：`docs/security/admin-backend-vulns-2026-07.md`  
> 契约文档：`docs/contract.md`
> 实施计划：`docs/design/PRD-管理后台观察者与安全加固-v1_实施计划.md`
> 契约草案：`docs/contract/drafts/管理后台观察者与安全加固/`
> 当前里程碑：✅ M1/M2/M3 全部完成；本计划已收尾

## 阶段门禁

| 阶段 | 进入条件 | 当前状态 | 确认人 | 确认日期 |
|------|---------|---------|-------|---------|
| 阶段 A：安全加固 | 无 | ✅ 已独立部署、机器烟测、稳定性观察及两名实际管理员重登确认 | 用户（项目所有者） | 2026-07-16 |
| 阶段 B：观察者 | STEP-001～017 全部 ✅；阶段 A 已独立部署并完成运行稳定性人工确认 | ✅ STEP-018～040 开发、自动化、35 页五角色浏览器验收、Docker 独立部署、项目所有者稳定性确认与正式契约同步全部完成 | 用户（项目所有者） | 2026-07-17 |

> 禁止合并阶段 A/B 开发或部署。阶段 B 已在阶段 A 独立部署和人工确认后开放，后续仍须严格按 STEP-018～040 顺序执行。

## 进度总览

| 完成数 | 总环节数 | 完成率 |
|-------|---------|-------|
| 40 | 40 | 100% |

> 每完成一个 STEP，手动更新完成数和完成率。

## 环节进度明细

| 环节编号 | 阶段 | 功能名称 | 前置环节 | 状态 | 完成日期 | 备注 |
|---------|------|---------|---------|------|---------|------|
| STEP-001 | A | ADMIN_JWT_SECRET 统一校验与启动双守卫 | 无 | ✅ | 2026-07-15 | 专项 12 通过；全量 777 通过、0 失败、3 跳过 |
| STEP-002 | A | token_version 数据库字段与迁移 | 无 | ✅ | 2026-07-16 | MySQL 8.0 升级、字段检查、回滚、再次升级全部通过；全量 780 通过 |
| STEP-003 | A | Admin JWT 携带并校验 token_version | STEP-002 | ✅ | 2026-07-16 | 专项 32 通过；相关回归 67 通过；全量 787 通过 |
| STEP-004 | A | 登录行锁事务与第五次锁定撤销 | STEP-002 | ✅ | 2026-07-16 | MySQL SQL 含 FOR UPDATE；专项 33、相关 68、全量 788 通过；并发实证留待 STEP-015 |
| STEP-005 | A | 登录失败统一响应、伪哈希与安全日志 | STEP-004 | ✅ | 2026-07-16 | 四类失败统一 20001；伪 bcrypt 与脱敏安全日志覆盖；全量 791 通过 |
| STEP-006 | A | 自助改密撤销全部旧会话 | STEP-003 | ✅ | 2026-07-16 | 双旧 Token 撤销、新版本重登及前端清会话验证通过；全量 796 通过 |
| STEP-007 | A | 登出执行账号级全会话撤销 | STEP-003 | ✅ | 2026-07-16 | 同账号全 Token 撤销、其他账号隔离、重登及前端清理验证通过；全量 798 通过 |
| STEP-008 | A | 账号安全操作的版本递增矩阵 | STEP-002 | ✅ | 2026-07-16 | 重置/实际角色变化递增；备注/相同角色/解锁不递增；全量 800 通过 |
| STEP-009 | A | life-config 发布服务端 CONFIRM 校验 | 无 | ✅ | 2026-07-16 | 5 类非法值 20021、精确 CONFIRM 与 403 权限边界通过；全量 807 通过 |
| STEP-010 | A | 7 个 life-config 前端发布入口传递 CONFIRM | STEP-009 | ✅ | 2026-07-16 | 7/7 调用点与共享确认交互验证通过；全量 809 通过 |
| STEP-011 | A | 共享递归凭据脱敏工具 | 无 | ✅ | 2026-07-16 | 专项 9、相关 59、全量 818 通过；无状态、幂等、失败关闭 |
| STEP-012 | A | 操作日志写入、列表、详情与导出双层脱敏 | STEP-011 | ✅ | 2026-07-16 | 专项 3、相关 57、全量 821 通过；历史行未改写 |
| STEP-013 | A | 系统日志列表与导出统一脱敏 | STEP-011 | ✅ | 2026-07-16 | 专项 6、相关 63、全量 823 通过；列表与导出统一脱敏 |
| STEP-014 | A | 阶段 A 自动化安全回归 | STEP-001~STEP-013 | ✅ | 2026-07-16 | 阶段门禁 107、全量 823 通过；0 失败 |
| STEP-015 | A | 真实 MySQL 8 并发登录验证 | STEP-004,STEP-005 | ✅ | 2026-07-16 | MySQL 8.0.46 并发矩阵 1 通过；全量 823 通过 |
| STEP-016 | A | 阶段 A 四角色回归与真实验证记录 | STEP-014,STEP-015 | ✅ | 2026-07-16 | 四角色矩阵 1、阶段门禁 108、全量 824 通过 |
| STEP-017 | A | 阶段 A 契约同步、独立部署与人工门禁 | STEP-016 | ✅ | 2026-07-16 | 独立部署、旧 Token/四角色烟测、54 分钟稳定性观察、super/ops 实际重登及正式契约同步完成 |
| STEP-018 | B | observer 角色与账号管理最小扩展 | STEP-017 | ✅ | 2026-07-16 | 五角色 schema/UI 标签与 observer 生命周期通过；非 super 五类账号 API 均 403；全量 835 通过 |
| STEP-019 | B | 观察者后端方法级集中总闸 | STEP-018 | ✅ | 2026-07-16 | 完整身份校验后统一拒绝四类写方法；仅精确放行登出/自助改密 POST；全量 843 通过 |
| STEP-020 | B | CORS OPTIONS 匿名预检边界 | STEP-019 | ✅ | 2026-07-16 | 匿名预检由 CORS 在业务依赖前返回纯文本 OK；GET/HEAD/写请求仍鉴权；全量 846 通过 |
| STEP-021 | B | 3 个内建导出接口显式拒绝观察者 | STEP-019 | ✅ | 2026-07-16 | 三端点挂载方法无关专用依赖；路由清单门禁、合法角色导出通过；全量 849 通过 |
| STEP-022 | B | 用户、统计与日志读取角色拆分 | STEP-019,STEP-012 | ✅ | 2026-07-16 | 用户业务/统计/脱敏日志读集合纳入 observer，写与导出不扩权；全量 852 通过 |
| STEP-023 | B | AI 配置与测试模块读取角色拆分 | STEP-019 | ✅ | 2026-07-16 | 5 模块全路由 READ/WRITE 拆分，observer 仅 GET；全量 856 通过 |
| STEP-024 | B | 记忆、向量、知识、Agent、关系与情绪读取角色拆分 | STEP-019 | ✅ | 2026-07-16 | 7 模块及用户向量读写角色拆分，observer 仅 GET；全量 858 通过 |
| STEP-025 | B | 系统监控、系统日志与第三方状态读取角色拆分 | STEP-019,STEP-013 | ✅ | 2026-07-16 | observer 可读系统/第三方状态及脱敏日志，测试/保存/导出仍拒绝；全量 861 通过 |
| STEP-026 | B | 生活流全模块读取角色拆分 | STEP-019 | ✅ | 2026-07-16 | 六模块所有读取集合纳入 observer，写集合不变；全量 863 通过 |
| STEP-027 | B | 第三方凭据与用户 Open API Key 状态化展示 | STEP-022,STEP-025 | ✅ | 2026-07-16 | observer 仅收已/未配置，不含原文、片段、掩码或哈希；全量 867 通过 |
| STEP-028 | B | 全量 Admin 路由鉴权与 GET/HEAD 副作用审计 | STEP-019~STEP-027 | ✅ | 2026-07-16 | 自动审计 159 路由、69 读、90 写、3 导出，鉴权/副作用门禁通过；全量 870 通过 |
| STEP-029 | B | 前端 observer 公共菜单、Header、只读助手与请求兜底 | STEP-018,STEP-019 | ✅ | 2026-07-16 | 菜单/Header、静态+动态只读助手、两个精确 POST 例外与非读请求兜底通过；全量 875 通过 |
| STEP-030 | B | 观察者账号管理页与 API 专项验证 | STEP-029 | ✅ | 2026-07-16 | 直访先跳 403、菜单无账号管理、6 API 全 403；super_admin 生命周期正常；全量 878 通过 |
| STEP-031 | B | 用户、报表与日志页面观察者只读改造 | STEP-022,STEP-021,STEP-027,STEP-029 | ✅ | 2026-07-16 | 5 页可读，静态/动态写控件和 3 导出已标记，读取交互保留；全量 882 通过 |
| STEP-032 | B | 系统监控、第三方、AI 测试与看板页面只读改造 | STEP-023,STEP-025,STEP-027,STEP-029 | ✅ | 2026-07-16 | 4 页可读；第三方仅凭据状态，保存/测试与 AI 生成/保存受控；全量 886 通过 |
| STEP-033 | B | 人格、Prompt、安全规则与对话流 Prompt 页面只读改造 | STEP-023,STEP-029 | ✅ | 2026-07-16 | 8 页 observer 可读；草稿/测试/发布/回滚/删除/导入及动态提交受控；全量 890 通过 |
| STEP-034 | B | 记忆、向量与知识页面只读改造 | STEP-024,STEP-027,STEP-029 | ✅ | 2026-07-16 | 3 页可读，全部静态/动态写控件受控；DashVector 仅凭据状态；全量 894 通过 |
| STEP-035 | B | Agent、关系、日记规则与日记历史页面只读改造 | STEP-024,STEP-029 | ✅ | 2026-07-16 | 4 页可读；静态/动态规则写控件受控，Tab、历史筛选与分页保留；全量 898 通过 |
| STEP-036 | B | 生活计划与世界观页面只读改造 | STEP-026,STEP-029 | ✅ | 2026-07-16 | 2 页可读；生成、增删改与配置保存受控，日期、分页、Tab、详情保留；全量 902 通过 |
| STEP-037 | B | 朋友圈内容、评论与感知页面只读改造 | STEP-026,STEP-029 | ✅ | 2026-07-16 | 3 页可读；发帖/编辑/显隐/补发/重试/删除/重置受控，列表筛选分页详情保留；全量 906 通过 |
| STEP-038 | B | 生活流人格拓展、Prompt 与系统参数页面只读改造 | STEP-026,STEP-029 | ✅ | 2026-07-16 | 3 页可读；草稿/发布/保存及动态配置控件受控，Tab/状态/统计保留；全量 910 通过 |
| STEP-039 | B | 阶段 B 后端权限与敏感读取自动化门禁 | STEP-018~STEP-028 | ✅ | 2026-07-16 | 159 路由、69 读、90 写、2 例外、3 导出与五角色组合门禁 98 通过；全量 913 通过 |
| STEP-040 | B | 35 页面五角色验收、文档同步与阶段 B 独立部署 | STEP-030~STEP-039 | ✅ | 2026-07-17 | 35/35 页浏览器验收、收尾全量 918 通过、17:02 CST 独立部署、项目所有者稳定性确认、临时账号清理及正式五角色契约同步完成 |

> 状态说明：⬜ 未开始；🔄 进行中；✅ 已完成；❌ 阻塞中。  
> STEP-017 与 STEP-040 人工门禁均已通过；阶段 A/B 仍保留独立部署证据，正式 observer/RBAC 契约已同步。

## 契约更新记录

| 日期 | STEP | 更新内容 | 契约文档位置 |
|------|------|---------|------------|
| 2026-07-15 | 开工准备 | 建立 M1/M2/M3 分阶段草案格式与正式同步闸门 | `docs/contract/drafts/管理后台观察者与安全加固/README.md` |
| 2026-07-15 | STEP-001 | 草案条目 `M1-STEP-001-01`：后台 JWT 密钥必须显式配置；缺失、空值、纯空白及两个公开占位值在配置读取和应用启动入口均被拒绝；合法自定义值可用；不增加长度、复杂度或轮换规则 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-002 | 草案条目 `M1-STEP-002-01`：`admin_users.token_version` 为 `INTEGER NOT NULL DEFAULT 0`；迁移对既有行回填 0，新行默认 0，并支持回滚和再次升级 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-003 | 草案条目 `M1-STEP-003-01`：新签发 Admin JWT 携带整数 `token_version`；统一鉴权校验 Token 类型、签名、过期、账号存在/启用/未锁定及数据库实时版本；无版本、非整数或版本不匹配均返回 401 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-004 | 草案条目 `M1-STEP-004-01`：存在账号的登录查询使用 `SELECT ... FOR UPDATE`；同一事务内处理锁定检查、密码校验、失败计数和成功清零；第五次错误将计数保持 5、锁定账号并仅递增一次 `token_version` | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-005 | 草案条目 `M1-STEP-005-01`：不存在账号、密码错误、锁定和停用统一返回 HTTP 200、业务码 `20001`、`data: null`、消息“账号或密码错误”；不存在账号执行固定伪 bcrypt；真实原因仅进入不含提交凭据的安全日志 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-006 | 草案条目 `M1-STEP-006-01`：管理员自助改密成功后 `token_version` 递增一次，使同账号当前及其他设备旧 Token 全部失效；失败分支不修改密码或版本；前端成功后清除本地会话并跳转登录页 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-007 | 草案条目 `M1-STEP-007-01`：管理员登出在同一事务中把当前账号 `token_version` 递增一次，使同账号全部旧 Token 失效；其他账号会话不受影响；保留登出操作日志与成功响应 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-008 | 草案条目 `M1-STEP-008-01`：超级管理员重置他人密码或把他人角色实际改为不同值时各递增一次目标账号 `token_version`；仅修改备注、提交相同角色或手动解锁不递增，解锁不恢复锁定前旧 Token | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-009 | 草案条目 `M1-STEP-009-01`：`POST /api/admin/life-config/publish` 请求体可缺省 `confirm_text`，但进入发布逻辑前必须精确等于 `CONFIRM`；缺失、`null`、空值、纯空白或错误值统一返回 `20021`，且不替代角色鉴权 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-010 | 草案条目 `M1-STEP-010-01`：现有 7 个 life-config 前端发布调用全部位于共享 `showConfirmInput` 确认回调内，并显式发送 `confirm_text: "CONFIRM"`；取消或错误文本不会触发发布回调 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-011 | 草案条目 `M1-STEP-011-01`：共享 `redact_credentials()` 对 dict/list 递归、对 JSON 字符串解析后递归、对非 JSON 字符串精确遮蔽已知凭据赋值及 Authorization/Bearer；统一替换为 `[REDACTED]`，无状态、幂等且单字段异常失败关闭 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-012 | 草案条目 `M1-STEP-012-01`：`log_operation` 在写入 `target_description`、`before_value`、`after_value` 前调用共享脱敏工具；操作日志列表、详情及 Excel 导出读取历史数据时再次脱敏；异常按字段失败关闭且不批量改写历史行 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-013 | 草案条目 `M1-STEP-013-01`：系统日志列表分页结果及 Excel 导出行在返回前统一调用共享凭据脱敏工具；所有获准角色获得一致结果，普通日志、Prompt、描述和 `max_tokens` 保持原样，异常消息失败关闭 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-014 | 草案条目 `M1-STEP-014-01`：阶段 A 自动化门禁必须覆盖 JWT 密钥、迁移、Token 版本与撤销、登录统一响应、CONFIRM 七入口、操作/系统日志脱敏及既有后台权限回归；任一失败即不得发布 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-015 | 草案条目 `M1-STEP-015-01`：管理员登录的 `SELECT ... FOR UPDATE` 必须在独立非生产 MySQL 8 验证；同账号第 5 次并发错密后保持 `login_fail_count=5`、`is_locked=true`、`token_version` 仅递增一次；锁定后状态不再变化，不同账号不共享行锁等待 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-016 | 草案条目 `M1-STEP-016-01`：阶段 A 发布前必须通过四角色登录、读取、写入、发布、账号管理和操作/系统日志导出矩阵；VULN-002/003/004/005/006/008 响应部分/009 仅据真实证据更新，VULN-001/007 与恶意锁号风险保持未修 | 待 M1 收口时写入 `M1_契约草案.md`，STEP-017 前不修改正式契约 |
| 2026-07-16 | STEP-017 部署前草案 | 汇总 `M1-STEP-001-01`～`M1-STEP-016-01` 及 STEP-017 部署门禁，明确四角色和未修风险边界 | `docs/contract/drafts/管理后台观察者与安全加固/M1_契约草案.md`；正式契约待部署后人工确认才同步 |
| 2026-07-16 | STEP-017 正式同步 | 仅同步已部署的阶段 A 安全事实：密钥守卫、`token_version`、登录行锁/统一响应、会话撤销矩阵、life-config CONFIRM、操作/系统日志脱敏；角色仍为四角色，未写入 observer 已上线事实 | `docs/contract.md`、`.cursorrules`、`docs/security/admin-backend-vulns-2026-07.md` |
| 2026-07-16 | STEP-018 | 草案条目 `M2-STEP-018-01`：账号角色值新增 `observer`、账号页展示“观察者”；五类账号管理 API 继续仅 `super_admin` 可用；公共菜单与 Header 留待 STEP-029 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-019 | 草案条目 `M2-STEP-019-01`：统一管理员鉴权完成 Token、实时账号状态和版本校验后，对数据库实时角色为 observer 的 POST/PUT/PATCH/DELETE 默认返回 403；仅精确放行 `POST /api/admin/auth/logout` 与 `POST /api/admin/auth/change-password`；GET/HEAD 继续进入路由既有权限依赖 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-020 | 草案条目 `M2-STEP-020-01`：带 Origin 与预检头的匿名 OPTIONS 由 CORS 中间件在业务依赖前返回纯文本 `OK` 和 CORS 响应头，不返回业务信封且不进入业务函数；业务 GET、显式 HEAD 与写方法仍进入统一 Admin 鉴权 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-021 | 草案条目 `M2-STEP-021-01`：操作日志、数据报表、系统日志三个现有内建导出路由除保留原角色依赖外，均直接挂载可复用 `deny_observer_export`；该依赖基于数据库实时角色且不依赖 HTTP 方法，observer 不获得文件响应 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-022 | 草案条目 `M2-STEP-022-01`：observer 可读取用户列表、详情、对话、情绪轮次、日记，全部统计 GET，以及经共享工具脱敏后的操作日志列表/详情；账号、用户向量记忆、用户 Open API Key 仍未在本 STEP 开放，用户写操作和日志/报表导出继续 403；原四角色矩阵不变 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-023 | 草案条目 `M2-STEP-023-01`：人格、Step5/Step5.5 Prompt、只读对话流 Prompt、测试用例与安全规则均使用明确 READ/WRITE 角色集合；observer 仅加入全部 GET/HEAD 读取集合，保存草稿、测试、发布、回滚、导入、删除和用例写入仍由原 `super_admin/ai_trainer` 写集合控制并受总闸拒绝 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-024 | 草案条目 `M2-STEP-024-01`：记忆、向量数值、知识、Agent、关系/日记、情绪、世界状态七模块及用户向量记忆均拆分读取/写入集合；observer 可访问现有 GET 读取和分页端点，但测试连接、保存、生成、重置、新增、编辑、删除等写操作继续由原角色集合控制并由总闸 403 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-025 | 草案条目 `M2-STEP-025-01`：system_monitor 明确拆分系统 READ/WRITE/EXPORT 角色集合；observer 可读系统状态、第三方运行状态和经共享工具脱敏的系统日志列表，不能更新第三方配置、发起连接测试或导出系统日志；原 super_admin/tech_ops 能力不变 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-026 | 草案条目 `M2-STEP-026-01`：life-config、生活计划、朋友圈内容、评论、感知队列和世界观六模块的全部 GET 读取集合包含 observer；生成、草稿、发布、回滚、新增、编辑、显隐、重试、删除、重置等写集合不含 observer，原 ops 只读与合法写角色保持 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-027 | 草案条目 `M2-STEP-027-01`：observer 的第三方状态响应仅为有凭据服务附加布尔 `credential_configured`，用户 Open API Key GET 仅返回 `enabled`；不得包含原文、prefix/suffix、掩码片段、哈希或时间元数据；原 ops Open API Key 元数据响应不变，写入与测试继续 403 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-028 | 草案条目 `M2-STEP-028-01`：自动枚举当前 159 个 `/api/admin/*` 路由；除单一登录 POST 外全部依赖统一 Admin 鉴权，90 个写路由均受统一身份入口保护，3 个 export/download 路由均具专用 observer 拒绝依赖；69 个 GET/HEAD 处理器无数据库/业务写调用，仅系统状态与第三方状态直接执行允许的有限 TTL 缓存写 | 待 M2 收口时写入 `M2_契约草案.md`；本 STEP 不修改正式契约或 `.cursorrules` |
| 2026-07-16 | STEP-029 | 草案条目 `M2-STEP-029-01`：公共 `isObserver()`、`applyObserverReadOnly()` 与 `data-write-action` 标记支持首屏和动态节点；observer 菜单不含账号管理，Header 显示“观察者”；`adminRequest()` 仅允许 GET/HEAD 与精确登出/自助改密 POST，未标记的读取交互不受统一禁用 | `docs/contract/drafts/管理后台观察者与安全加固/M2_契约草案.md`；不修改正式契约或 `.cursorrules` |
| 2026-07-16 | M2 收口 | 汇总 `M2-STEP-018-01`～`M2-STEP-029-01` 已验证事实，明确 35 页闭环、正式五角色契约与阶段 B 部署仍待 STEP-030～040 | `docs/contract/drafts/管理后台观察者与安全加固/M2_契约草案.md`；正式同步门禁为 STEP-040 |
| 2026-07-16 | STEP-030 | 草案条目 `M3-STEP-030-01`：observer 直访 `accounts.html` 时在渲染和请求账号数据前跳转 403 页；菜单无账号管理；列表、创建、编辑、重置密码、解锁、删除 6 类 API 对 observer 均 403 且无数据变更，`super_admin` 能力不变 | 待 STEP-040 生成 `M3_契约草案.md` 并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-031 | 草案条目 `M3-STEP-031-01`：observer 可进入用户列表、用户详情、数据报表、操作日志和系统日志 5 页；用户状态、记忆/私有设定增删改、重置密码、Key 生成及 3 个导出控件按静态/动态标记受控；搜索、筛选、分页、Tab、详情、复制和 GET 刷新保留 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-032 | 草案条目 `M3-STEP-032-01`：observer 可进入系统监控、第三方、AI 测试和数据看板；第三方仅显示凭据已/未配置，配置、保存和连接测试受控；AI 测试参数、生成、清空历史、保存用例及动态弹窗提交受控；看板和系统 GET 刷新保留 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-033 | 草案条目 `M3-STEP-033-01`：observer 可读人格、Step5/Step5.5、Step5.5 开关、安全规则及 Step1.5/3/8/Agent 四个只读 Prompt 页；编辑字段、草稿、测试、发布、回滚、删除、导入、动态草稿按钮/文本框受控；Tab、历史、查看、完整 Prompt 展开保留 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-034 | 草案条目 `M3-STEP-034-01`：observer 可读 Step6 Prompt、全局记忆、DashVector 非敏感参数、召回/Token 数值和知识库；所有保存、测试、凭据修改、删除、新增、编辑及动态行控件受控；DashVector 对 observer 仅返回 `credential_configured`，不返回原文或掩码片段 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-035 | 草案条目 `M3-STEP-035-01`：observer 可读 Agent、关系、日记规则与日记历史 4 页；规则保存、影响确认、关键词和动态消息/等级字段受控；Tab、日记历史筛选、分页与纯 GET 读取保留 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-036 | 草案条目 `M3-STEP-036-01`：observer 可读生活计划和世界观 2 页；配置字段、生成、新增、编辑、删除、草稿/发布及弹窗提交的静态/动态入口受控；日期切换、分页、Tab、描述展开和 GET 刷新保留，ops_admin 原只读语义不变 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-037 | 草案条目 `M3-STEP-037-01`：observer 可读朋友圈内容、评论和感知队列 3 页；发帖/AI 生成、编辑、显隐、评论补发/软删、感知重试/删除和特殊档重置的静态/动态入口受控；列表、筛选、分页、帖子/感知详情和刷新保留 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-038 | 草案条目 `M3-STEP-038-01`：observer 可读生活流人格拓展、Prompt 和系统参数 3 页；文本、数值、选择、开关、标签增删及静态/动态草稿、发布、保存控件受控；Tab、配置展示、状态、Liblib 统计和 GET 刷新保留，7 个既有发布调用继续携带精确 `CONFIRM` | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-039 | 草案条目 `M3-STEP-039-01`：阶段 B 自动化门禁枚举 159 个 Admin 路由，覆盖 69 个 GET/HEAD、90 个写方法、精确登出/自助改密两个 POST 例外、匿名 CORS OPTIONS、账号 API、三个导出、第三方/Open API Key 状态化读取及五角色组合回归；任一失败不得发布 | 待 STEP-040 汇总 M3 草案并通过部署/人工门禁后正式同步 |
| 2026-07-16 | STEP-040 部署前草案 | 汇总 `M3-STEP-030-01`～`M3-STEP-039-01`；记录 35/35 页五角色浏览器验收、全量 917 通过、阶段 B Docker 独立部署与机器烟测证据 | `docs/contract/drafts/管理后台观察者与安全加固/M3_契约草案.md`；项目所有者人工门禁前不同步正式契约 |
| 2026-07-17 | STEP-040 正式同步 | 项目所有者确认稳定并允许收尾后，同步五角色、observer 读写/导出/凭据/前端只读边界、发布证据和延期风险 | `docs/contract.md`、`.cursorrules`、PRD、`docs/security/admin-backend-vulns-2026-07.md`；M3 草案保留为里程碑快照 |

## 阻塞记录

| 日期 | STEP | 阻塞原因 | 解决方案 | 解决日期 |
|------|------|---------|---------|---------|
| 2026-07-16 | STEP-017 | 阶段 A 已部署并通过机器烟测，等待实际管理员重新登录并明确确认运行稳定 | 用户使用 `super_admin`、`ops_admin` 两个实际账号重新登录并确认均正常；随后同步正式契约与长期规则 | 2026-07-16 |
| 2026-07-16 | STEP-040 | 项目所有者首次人工验收时，当前 Chrome 账号页的新建/编辑角色下拉框没有“观察者” | 逐层比对确认源码和 Docker 实际 GET 均含 observer；用户当前标签页仍是 2026-04-22 旧文档且公共资源未带版本参数。刷新后加载新文档，新建/编辑均显示 observer 并实测可选；用户后续确认暂无问题 | 2026-07-17 |

## 测试与验收记录

| 日期 | STEP/阶段 | 实际命令或人工清单 | 通过/失败数量 | 失败原因 | 结论 |
|------|-----------|-------------------|--------------|---------|------|
| 2026-07-15 | 开工基线 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 765 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；另有既存 warning | 基线通过，可进入 STEP-001 |
| 2026-07-15 | STEP-001 专项 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step001_admin_jwt_secret.py -q --tb=short` | 12 通过 / 0 失败 | — | 五种非法输入与合法自定义值在配置读取、lifespan 双入口结论一致 |
| 2026-07-15 | STEP-001 相关回归 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py tests/test_diary.py tests/test_step001_admin_jwt_secret.py -q --tb=short` | 58 通过 / 0 失败 | — | 后台鉴权与原 lifespan 相关用例通过 |
| 2026-07-15 | STEP-001 全量回归 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 777 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；97 条既存 warning | 通过 |
| 2026-07-16 | STEP-002 专项与相关回归 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_admin_auth.py -q --tb=short` | 40 通过 / 0 失败 | — | ORM、迁移定义、STEP-001 与后台鉴权相关回归通过 |
| 2026-07-16 | STEP-002 MySQL 8.0 首次升级 | 独立库 `lxm_step002_codex_019f6545`：`env MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_DATABASE=lxm_step002_codex_019f6545 ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m alembic upgrade head`，随后查询列定义、旧行、新行、NULL 计数和版本 | 5 项检查通过 / 0 失败 | — | `INT NOT NULL DEFAULT 0`；既有行 0、新行 0、NULL 计数 0；版本为 `v7a_admin_token_ver_001` |
| 2026-07-16 | STEP-002 MySQL 8.0 回滚与再升级 | 同一独立库依次执行 `.venv-step001/bin/python -m alembic downgrade -1`、列与版本检查、`.venv-step001/bin/python -m alembic upgrade head`、最终列/数据/版本检查 | 7 项检查通过 / 0 失败 | — | 回滚后列不存在且版本为 `v6e_display_comments_001`；再次升级后两条既有数据均为 0、NULL 计数 0、版本回到 head；验证后已删除独立测试库 |
| 2026-07-16 | STEP-002 首次全量回归 | `env PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 752 通过 / 28 失败 / 3 跳过 | 本机重启后 `tiktoken` 编码缓存丢失，沙箱内无法联网下载；28 项均为该环境依赖错误 | 未通过，不据此完成 STEP；恢复独立缓存后重跑 |
| 2026-07-16 | STEP-002 最终全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 780 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；97 条既存 warning | 通过 |
| 2026-07-16 | STEP-003 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 32 通过 / 0 失败 | — | JWT 版本、账号状态和原有 Token 类型隔离全部通过 |
| 2026-07-16 | STEP-003 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 67 通过 / 0 失败 | — | 后台模块与 STEP-001/002 回归通过 |
| 2026-07-16 | STEP-003 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 787 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；111 条既存 warning | 通过 |
| 2026-07-16 | STEP-004 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 33 通过 / 0 失败 | — | MySQL 方言编译含 `FOR UPDATE`；1～4 次失败后正确登录清零；第五次锁定及锁后幂等状态通过 |
| 2026-07-16 | STEP-004 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 68 通过 / 0 失败 | — | 后台模块与 STEP-001～003 回归通过 |
| 2026-07-16 | STEP-004 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 788 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；111 条既存 warning | 通过；真实 MySQL 8 并发争用按步骤文档在 STEP-015 专项验证 |
| 2026-07-16 | STEP-005 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 36 通过 / 0 失败 | — | 四类失败完整 JSON、内部计数、伪 bcrypt、安全日志原因与凭据不落日志全部通过 |
| 2026-07-16 | STEP-005 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 71 通过 / 0 失败 | — | 后台模块与 STEP-001～004 回归通过 |
| 2026-07-16 | STEP-005 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 791 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；111 条既存 warning | 通过 |
| 2026-07-16 | STEP-006 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 41 通过 / 0 失败 | — | 双旧 Token 撤销、失败分支版本不变、新版本 Token 访问和前端清会话顺序通过 |
| 2026-07-16 | STEP-006 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 76 通过 / 0 失败 | — | 后台模块与 STEP-001～005 回归通过 |
| 2026-07-16 | STEP-006 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 796 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；119 条既存 warning | 通过 |
| 2026-07-16 | STEP-007 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 43 通过 / 0 失败 | — | 同账号双 Token 撤销、其他管理员隔离、重登、登出日志与前端清会话顺序通过 |
| 2026-07-16 | STEP-007 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 78 通过 / 0 失败 | — | 后台模块与 STEP-001～006 回归通过 |
| 2026-07-16 | STEP-007 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 798 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；121 条既存 warning | 通过 |
| 2026-07-16 | STEP-008 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 45 通过 / 0 失败 | — | 重置密码、实际角色变化、备注、相同角色、锁定/解锁与旧 Token 矩阵通过 |
| 2026-07-16 | STEP-008 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py -q --tb=short` | 80 通过 / 0 失败 | — | 后台模块与 STEP-001～007 回归通过 |
| 2026-07-16 | STEP-008 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 800 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；125 条既存 warning | 通过 |
| 2026-07-16 | STEP-009 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step009_life_config_publish_confirm.py -q --tb=short` | 7 通过 / 0 失败 | — | 缺失、null、空值、纯空白、错误值、精确 CONFIRM 和无权限角色全部通过 |
| 2026-07-16 | STEP-009 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_step009_life_config_publish_confirm.py -q --tb=short` | 87 通过 / 0 失败 | — | 后台模块与 STEP-001～008 回归通过 |
| 2026-07-16 | STEP-009 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 807 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；138 条既存 warning | 通过 |
| 2026-07-16 | STEP-010 静态与接口专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step009_life_config_publish_confirm.py tests/test_step010_life_config_publish_frontend.py -q --tb=short` | 9 通过 / 0 失败 | — | 精确 7 个调用点、每处共享确认组件与显式 CONFIRM 字段、服务端接口契约全部通过 |
| 2026-07-16 | STEP-010 浏览器交互 | 本地临时验收页加载生产 `admin/static/js/admin-api.js` 的 `showConfirmInput`：依次执行取消、输入 `confirm`、输入 `CONFIRM` 并点击确认 | 3 场景通过 / 0 失败 | — | 取消后回调状态保持 `idle`；错误值确认按钮禁用；精确值按钮启用并把回调状态置为 `submitted`；临时验收页及本地服务器已清理 |
| 2026-07-16 | STEP-010 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin*.py tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_step009_life_config_publish_confirm.py tests/test_step010_life_config_publish_frontend.py -q --tb=short` | 89 通过 / 0 失败 | — | 后台模块与 STEP-001～009 回归通过 |
| 2026-07-16 | STEP-010 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 809 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；139 条既存 warning | 通过 |
| 2026-07-16 | STEP-011 RED | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py -q --tb=short` | 0 通过 / 9 失败 | 共享模块尚不存在，9 项均按预期因 `ModuleNotFoundError` 失败 | TDD 红灯成立 |
| 2026-07-16 | STEP-011 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py -q --tb=short` | 9 通过 / 0 失败 | — | 嵌套结构、JSON 字符串、非 JSON 精确匹配、幂等、非凭据边界和单字段失败关闭全部通过 |
| 2026-07-16 | STEP-011 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py tests/test_admin_auth.py tests/test_admin_user_conversations.py -q --tb=short` | 59 通过 / 0 失败 | — | 共享工具与后台认证、会话读取相关能力无回归 |
| 2026-07-16 | STEP-011 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 818 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；139 条既存 warning | 通过 |
| 2026-07-16 | STEP-012 RED | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step012_operation_log_redaction.py -q --tb=short` | 0 通过 / 3 失败 | 写入、历史读取与异常失败关闭尚未接入共享脱敏工具 | TDD 红灯成立 |
| 2026-07-16 | STEP-012 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step012_operation_log_redaction.py -q --tb=short` | 3 通过 / 0 失败 | — | 写入、列表、详情、Excel 导出、历史行不改写及异常写入均通过 |
| 2026-07-16 | STEP-012 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_admin_auth.py -q --tb=short` | 57 通过 / 0 失败 | — | 共享脱敏、操作日志和原后台认证权限回归通过 |
| 2026-07-16 | STEP-012 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 821 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；139 条既存 warning | 通过 |
| 2026-07-16 | STEP-013 RED | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_system_monitor_logs.py -q --tb=short` | 4 通过 / 2 失败 | 系统日志列表和导出尚未接入共享脱敏工具 | TDD 红灯成立 |
| 2026-07-16 | STEP-013 专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_system_monitor_logs.py -q --tb=short` | 6 通过 / 0 失败 | — | 凭据列表/导出、非凭据边界、失败关闭以及既有解析排序过滤全部通过 |
| 2026-07-16 | STEP-013 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_system_monitor_logs.py tests/test_admin_auth.py -q --tb=short` | 63 通过 / 0 失败 | — | 共享工具、操作日志、系统日志和原后台认证权限回归通过 |
| 2026-07-16 | STEP-013 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 823 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；139 条既存 warning | 通过 |
| 2026-07-16 | STEP-014 阶段 A 自动化门禁 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_admin_auth.py tests/test_admin_character_knowledge.py tests/test_admin_date_filter.py tests/test_admin_user_conversations.py tests/test_admin_vector_token_config.py tests/test_step009_life_config_publish_confirm.py tests/test_step010_life_config_publish_frontend.py tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_system_monitor_logs.py -q --tb=short` | 107 通过 / 0 失败 | — | STEP-001～013 安全规则及后台认证、账号、日志、配置、角色权限相关门禁通过 |
| 2026-07-16 | STEP-014 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 823 通过 / 0 失败 / 3 跳过 | 3 项为需显式开启的外部阿里云集成测试；139 条既存 warning | 通过 |
| 2026-07-16 | STEP-015 环境确认 | `docker exec lxm_mysql sh -lc 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "... SELECT VERSION() AS mysql_version;"'`，创建独立库 `lxm_step015_codex_019f6545` | MySQL 8.0.46 / 1 个独立测试库创建成功 | — | 真实非生产 MySQL 8 环境成立 |
| 2026-07-16 | STEP-015 首次沙箱执行 | `env MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_DATABASE=lxm_step015_codex_019f6545 RUN_STEP015_MYSQL8=1 ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step015_mysql_login_concurrency.py -q -s --tb=short` | 0 通过 / 1 环境错误 | 沙箱禁止连接本机 `127.0.0.1:3306`，`PermissionError: Operation not permitted` | 未作为验证结果；获授权后在沙箱外重跑 |
| 2026-07-16 | STEP-015 首次沙箱外执行 | 同一 MySQL 8 专项命令在授权环境执行 | 0 通过 / 1 失败 | 模块级异步夹具与测试函数使用不同事件循环，连接 Future 绑定错误；非业务并发失败 | 改为函数级夹具后重跑 |
| 2026-07-16 | STEP-015 MySQL 8 最终并发验证 | `env MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_DATABASE=lxm_step015_codex_019f6545 RUN_STEP015_MYSQL8=1 ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step015_mysql_login_concurrency.py -q -s --tb=short`（授权环境） | 1 通过 / 0 失败；并发规模 5+4+1 | — | 5 次并发错密后状态 `(5,true,1)`；锁定后 4 次并发不变；持有账号 A 行锁时账号 B 在 3 秒门限内完成并变为 `(1,false,0)` |
| 2026-07-16 | STEP-015 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 45 通过 / 0 失败 | — | SQLite 单元回归仅用于原行为检查，不替代上述 MySQL 8 证据 |
| 2026-07-16 | STEP-015 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 823 通过 / 0 失败 / 4 跳过 | 新增 1 项跳过为必须显式指定独立 MySQL 8 的 STEP-015 测试；原 3 项为外部阿里云集成测试；139 条既存 warning | 通过；一次性测试库随后删除并查询确认不存在 |
| 2026-07-16 | STEP-016 四角色专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step016_four_role_regression.py -q --tb=short` | 1 通过 / 0 失败；4 角色 × 6 类能力 | — | 四角色登录、life-config 读取/草稿写/发布、账号读取、操作日志导出、系统日志导出权限矩阵通过 |
| 2026-07-16 | STEP-016 阶段安全门禁 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_admin_auth.py tests/test_admin_character_knowledge.py tests/test_admin_date_filter.py tests/test_admin_user_conversations.py tests/test_admin_vector_token_config.py tests/test_step009_life_config_publish_confirm.py tests/test_step010_life_config_publish_frontend.py tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_system_monitor_logs.py tests/test_step016_four_role_regression.py -q --tb=short` | 108 通过 / 0 失败 | — | 阶段 A 自动化与四角色权限矩阵统一通过 |
| 2026-07-16 | STEP-016 漏洞专项复核 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step001_admin_jwt_secret.py tests/test_step002_admin_token_version_migration.py tests/test_step009_life_config_publish_confirm.py tests/test_step010_life_config_publish_frontend.py tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_system_monitor_logs.py -q --tb=short` | 42 通过 / 0 失败 | — | 与 `tests/test_admin_auth.py` 45 通过及 STEP-015 MySQL 8 专项 1 通过共同支撑漏洞专档真实结果 |
| 2026-07-16 | STEP-016 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 824 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in，3 项为外部阿里云集成；141 条既存 warning | 通过 |
| 2026-07-16 | STEP-017 部署前检查 | `docker compose ps`；容器内密钥仅判定合法性、不输出原文；`docker exec lxm_backend alembic current` | 3 项通过 / 0 失败 | — | MySQL 8 健康，`ADMIN_JWT_SECRET` 合法，迁移为 `v7a_admin_token_ver_001 (head)` |
| 2026-07-16 | STEP-017 构建与部署 | `docker compose build backend`；`docker compose run --rm backend alembic upgrade head`；`docker compose up -d backend` | 3 条命令通过 / 0 失败 | — | 阶段 A backend 镜像构建成功，迁移幂等成功，容器重建启动；admin 静态目录由同一 compose 挂载同步生效 |
| 2026-07-16 | STEP-017 首次烟测启动 | `docker exec lxm_backend python /tmp/step017_deploy_smoke.py` | 0 通过 / 1 环境错误 | 脚本位于 `/tmp`，Python 搜索路径未包含应用目录 `/app`，在导入业务模块前失败 | 未作为部署功能失败；显式工作目录和 `PYTHONPATH=/app` 后重跑 |
| 2026-07-16 | STEP-017 部署烟测 | `docker exec -w /app -e PYTHONPATH=/app lxm_backend python /tmp/step017_deploy_smoke.py` | 6 项通过 / 0 失败 | — | `token_version NOT NULL DEFAULT 0`；历史无版本 Token=401；super/ops/ai/tech 四角色新 Token 代表接口均=200；临时账号最终计数 0 |
| 2026-07-16 | STEP-017 机器稳定性观察 | 12:07:56 CST 执行 `docker inspect lxm_backend`、`docker compose logs --since=3m backend`，并核对实际管理员角色计数 | 容器运行、0 次重启、周期任务持续成功；实际管理员 1 人（super_admin） | 仅有既存 JWT 测试密钥长度 warning；未见 Traceback 或任务失败 | 机器观察通过；真实管理员重登和人工稳定性确认仍待完成 |
| 2026-07-16 | STEP-017 人工门禁收口 | `docker compose ps`；`docker inspect lxm_backend`；MySQL `SELECT role, COUNT(*) FROM admin_users GROUP BY role`；用户分别登录两个实际账号 | 机器 3 项通过 / 0 失败；实际账号 2/2 登录正常 | — | backend 连续运行约 54 分钟、0 重启；数据库为 `super_admin=1`、`ops_admin=1`；用户确认可继续下一 STEP |
| 2026-07-16 | STEP-017 最终全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 824 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；141 条既存 warning | 正式契约同步后最终回归通过，STEP-017 可关闭 |
| 2026-07-16 | STEP-018 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py::TestStep018ObserverRole -q --tb=short` | 10 通过 / 3 预期失败 | observer 被 Pydantic 角色正则拒绝、模型注释缺少 observer、创建 API 返回 422 | 红灯原因均为 STEP-018 功能缺失；更早一次测试编排 NameError 已先修正，未作为功能证据 |
| 2026-07-16 | STEP-018 专项与账号回归 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py::TestStep018ObserverRole tests/test_admin_auth.py::TestAccountVersionMatrix -q --tb=short`；随后运行整个 `tests/test_admin_auth.py` | 专项/相关 13 通过；账号文件 56 通过；0 失败 | — | 五角色校验、账号页两个下拉与列表标签、observer 完整生命周期、四个非 super 角色 × 6 个账号 API 403、阶段 A 会话版本矩阵均通过 |
| 2026-07-16 | STEP-018 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 835 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；151 条既存 warning | 通过 |
| 2026-07-16 | STEP-019 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py::TestStep019ObserverMethodGate -q --tb=short` | 3 通过 / 5 预期失败 | observer 的 POST/PUT/PATCH/DELETE 均进入探针端点并返回 200；相似路径和错误方法也未被统一拒绝 | 红灯原因均为方法总闸缺失；测试编排中的 1 个既有断言位置问题先修正后才记录本结果 |
| 2026-07-16 | STEP-019 专项与相关回归 | 同一专项命令；`env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short`；四角色专项命令 | 专项 8 通过；账号鉴权 64 通过；四角色 1 通过；0 失败 | — | 四写方法在端点前 403；两个精确 POST 例外进入原业务；相似路径/错误方法 403；六类无效身份先 401；GET/HEAD 与非 observer 行为不变 |
| 2026-07-16 | STEP-019 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 843 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；167 条既存 warning | 通过 |
| 2026-07-16 | STEP-020 首次专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -k Step020 -q --tb=short` | 3 通过 / 1 失败 | 测试基础设施误用当前 httpx 不支持的 `AsyncClient.options(json=...)`；改用通用 `request("OPTIONS", ..., json=...)`，非产品行为失败 | 修正测试调用后重跑 |
| 2026-07-16 | STEP-020 专项与相关回归 | 同一专项命令；`env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py -q --tb=short` | 专项 3 通过；后台认证相关 67 通过；0 失败 | — | 匿名预检只返回 CORS `OK`，账号数量与版本不变；匿名业务 GET、显式 HEAD 探针和 POST 均 401 |
| 2026-07-16 | STEP-020 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 846 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；167 条既存 warning | 通过 |
| 2026-07-16 | STEP-021 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step021_observer_exports.py -q --tb=short` | 0 通过 / 1 收集错误 | `deny_observer_export` 尚不存在，测试按预期因 ImportError 终止收集 | 红灯成立 |
| 2026-07-16 | STEP-021 测试编排修正 | 同一专项命令及相关组合命令 | 两轮均 2 通过 / 1 失败；相关组合 21 通过 / 1 失败 | 当前 FastAPI 使用惰性 `_IncludedRouter`，首次路由审计误读 `path`，第二次未合成 include prefix；修正为展开原 APIRouter 并拼接 include prefix，非产品行为失败 | 修正后重跑通过 |
| 2026-07-16 | STEP-021 专项与相关回归 | 同一专项命令；`env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step011_credential_redaction.py tests/test_step012_operation_log_redaction.py tests/test_system_monitor_logs.py tests/test_step016_four_role_regression.py tests/test_step021_observer_exports.py -q --tb=short` | 专项 3 通过；相关 22 通过；0 失败 | — | 三导出 observer 403 且无文件头；原合法角色返回 Excel；未来 GET 导出探针也被专用依赖拒绝；清单精确覆盖 3 个现有端点 |
| 2026-07-16 | STEP-021 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 849 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；171 条 warning | 通过 |
| 2026-07-16 | STEP-022 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step022_observer_user_stats_logs.py -q --tb=short` | 2 通过 / 1 预期失败 | observer 首个批准读取 `GET /api/admin/users` 返回 403，证明读取角色尚未扩展 | 红灯成立 |
| 2026-07-16 | STEP-022 实现后首次专项 | 同一专项命令 | 2 通过 / 1 失败 | 测试直接取日志列表第一项，实际登录新增日志排序在历史脱敏样本之前；改为使用模块筛选定位样本，非产品行为失败 | 修正测试后重跑 |
| 2026-07-16 | STEP-022 专项与相关回归 | 同一专项命令；`env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_user_conversations.py tests/test_admin_date_filter.py tests/test_step012_operation_log_redaction.py tests/test_step016_four_role_regression.py tests/test_step021_observer_exports.py tests/test_step022_observer_user_stats_logs.py -q --tb=short` | 专项 3 通过；相关 18 通过；0 失败 | — | 批准的用户/统计/日志读取可用且日志凭据脱敏；账号、Open API Key、用户向量读取未提前开放；写与导出 403 且数据不变；四角色矩阵保持 |
| 2026-07-16 | STEP-022 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 852 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；177 条 warning | 通过 |
| 2026-07-16 | STEP-023 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step023_observer_ai_read_roles.py -q --tb=short` | 2 通过 / 2 预期失败 | 五模块仍只有共用 `_ALLOWED_ROLES`；observer 首个人格 GET 返回 403 | 红灯成立 |
| 2026-07-16 | STEP-023 相关回归首次 | 未设置缓存目录运行 4 个相关文件组合 | 24 通过 / 2 环境失败 | 两项 Prompt 构建测试尝试联网下载 tiktoken 编码，沙箱 DNS 拒绝；非产品行为失败 | 补充既有 `TIKTOKEN_CACHE_DIR` 后原命令重跑 |
| 2026-07-16 | STEP-023 专项与相关回归 | 同一专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_chat_prompt_view.py tests/test_step012_content_safety.py tests/test_step026_prompt_config.py tests/test_step023_observer_ai_read_roles.py -q --tb=short` | 专项 4 通过；相关 26 通过；0 失败 | — | 5 文件全部路由经 AST 清单确认 GET/HEAD 使用 READ、写方法使用 WRITE；代表性读取 200，13 个写入口 403，原 AI 两角色读取正常 |
| 2026-07-16 | STEP-023 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 856 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；183 条 warning | 通过 |
| 2026-07-16 | STEP-024 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step024_observer_domain_read_roles.py -q --tb=short` | 0 通过 / 2 预期失败 | 七模块尚无 READ/WRITE 集合；observer 首个 Step6 读取返回 403 | 红灯成立 |
| 2026-07-16 | STEP-024 实现编排修正 | 同一专项命令 | 两轮均 0 通过 / 2 失败 | 首轮发现 Agent/日记历史保留特殊原角色集合且测试路径漏 `/configs` 前缀；修正为特殊 HISTORY_READ 集合并使用真实路由前缀，非最终产品失败 | 修正后专项通过 |
| 2026-07-16 | STEP-024 专项与相关回归 | 同一专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_character_knowledge.py tests/test_admin_vector_token_config.py tests/test_admin_user_conversations.py tests/test_diary.py tests/test_step024_observer_domain_read_roles.py -q --tb=short` | 专项 2 通过；相关 40 通过；0 失败 | — | AST 清单覆盖 7 文件全部路由；14 个代表性 GET 200，8 个写入口 403；原 ops 历史读取权限通过专用集合保留 |
| 2026-07-16 | STEP-024 首次全量回归 | 全量标准命令 | 857 通过 / 1 失败 / 4 跳过 | STEP-022 的阶段性测试仍断言用户向量读取 403，与 STEP-024 按序开放后的最终状态冲突；删除该过时阶段断言，STEP-024 已含正向与写拒绝覆盖 | 修正后重跑 |
| 2026-07-16 | STEP-024 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 858 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；185 条 warning | 通过 |
| 2026-07-16 | STEP-025 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step025_observer_system_monitor.py -q --tb=short` | 2 通过 / 1 预期失败 | observer 的系统状态 GET 返回 403，读取集合尚未扩展 | 红灯成立 |
| 2026-07-16 | STEP-025 实现后首次相关 | 专项、系统日志及 STEP-021 导出组合命令 | 11 通过 / 1 失败 | 测试样本误写为 `app.log`，生产映射实际读取 `system.log`；根因经 `_LOG_TYPE_FILE_MAP` 定位后仅修正测试文件名 | 修正后重跑 |
| 2026-07-16 | STEP-025 专项与相关回归 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step025_observer_system_monitor.py tests/test_system_monitor_logs.py tests/test_step021_observer_exports.py -q --tb=short` | 12 通过 / 0 失败 | — | 三类 observer GET 200，系统日志凭据脱敏；更新、连接测试、导出 403 且测试函数未调用；super/tech 读取和导出正常 |
| 2026-07-16 | STEP-025 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 861 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；191 条 warning | 通过 |
| 2026-07-16 | STEP-026 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step026_observer_life_stream_reads.py -q --tb=short` | 0 通过 / 2 预期失败 | 六文件读取集合均不含 observer；首个 life-config GET 返回 403 | 红灯成立 |
| 2026-07-16 | STEP-026 实现后首次专项 | 同一专项命令 | 1 通过 / 1 环境失败 | life-plan settings 读取通过 admin_config_service 连接真实本地 Redis，被沙箱拒绝；按依赖链确认后在测试夹具模拟只读配置服务，非产品行为失败 | 修正后重跑 |
| 2026-07-16 | STEP-026 专项与相关回归 | 同一专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step003_life_feed_config.py tests/test_step009_life_config_publish_confirm.py tests/test_step011_feed_content.py tests/test_step013_feed_publish.py tests/test_step015_feed_service.py tests/test_step018_comment_reply.py tests/test_step019_agent_aware.py tests/test_step026_observer_life_stream_reads.py -q --tb=short` | 专项 2 通过；相关 86 通过；0 失败 | — | observer 与原 ops 对 10 个代表性读取均 200，8 类写入口均 403；静态清单确认六模块 observer 只在 READ 集合 |
| 2026-07-16 | STEP-026 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 863 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；193 条 warning | 通过 |
| 2026-07-16 | STEP-027 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step027_observer_credential_status.py -q --tb=short` | 1 通过 / 3 预期失败 | observer Open API Key GET 仍 403，第三方状态无凭据配置布尔，前端无 observer 状态分支 | 红灯成立 |
| 2026-07-16 | STEP-027 专项与相关回归 | 同一专项命令；`env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step022_observer_user_stats_logs.py tests/test_step025_observer_system_monitor.py tests/test_step027_observer_credential_status.py -q --tb=short` | 专项 4 通过；相关 10 通过；0 失败 | — | 已配置/未配置双分支、序列化敏感片段扫描、写拒绝、原 ops 元数据及两个前端状态分支全部通过 |
| 2026-07-16 | STEP-027 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 867 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；199 条 warning | 通过 |
| 2026-07-16 | STEP-028 首次专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step028_admin_route_audit.py -q --tb=short` | 1 通过 / 2 测试规则失败 | 审计规则未排除唯一匿名登录 POST，并把本地 `seen.add` 误判为数据库 add；路由实况本身无鉴权或副作用缺口 | 按精确匿名清单及 db/session 接收者收敛规则后重跑 |
| 2026-07-16 | STEP-028 专项与阶段相关回归 | 同一专项命令；STEP-019/020 过滤命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step021_observer_exports.py tests/test_step022_observer_user_stats_logs.py tests/test_step023_observer_ai_read_roles.py tests/test_step024_observer_domain_read_roles.py tests/test_step025_observer_system_monitor.py tests/test_step026_observer_life_stream_reads.py tests/test_step027_observer_credential_status.py tests/test_step028_admin_route_audit.py -q --tb=short` | 专项 3 通过；019/020 11 通过；021～028 24 通过；0 失败 | — | 159 路由鉴权、90 写、69 读、3 导出清单和直接缓存白名单全部通过 |
| 2026-07-16 | STEP-028 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short` | 870 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（已独立真实执行通过），3 项为外部阿里云集成；199 条 warning | 通过 |

| 2026-07-16 | STEP-029 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step029_observer_frontend_common.py -q --tb=short` | 0 通过 / 5 预期失败 | 公共 observer 菜单/Header、请求兜底、只读助手、动态观察和样式均尚未存在 | 红灯成立 |
| 2026-07-16 | STEP-029 静态与 JavaScript 运行时专项 | 上述 pytest 命令；`PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin node --check admin/static/js/admin-api.js`；Node VM 内联运行时断言 | pytest 5 通过；语法 1 通过；运行时 22 断言通过；0 失败 | — | 菜单/Header、GET/HEAD、两个精确 POST、普通写阻止、五类控件及动态节点全部通过 |
| 2026-07-16 | STEP-029 首次相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py tests/test_step010_life_config_publish_frontend.py tests/test_step027_observer_credential_status.py tests/test_step029_observer_frontend_common.py -x -vv --tb=long` | 59 通过 / 1 失败 | STEP-018 阶段性测试仍断言公共 Header 不得包含 observer，与 STEP-029 按序新增展示名的最终状态冲突 | 移除过时负向断言，保留 STEP-018 账号 UI 边界并由 STEP-029 专项验证 Header |
| 2026-07-16 | STEP-029 相关回归 | 同上四文件组合命令 | 78 通过 / 0 失败 | — | STEP-018/019、改密/登出、CONFIRM 入口、凭据状态与公共前端回归通过 |
| 2026-07-16 | STEP-029 / M2 收口全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 875 通过 / 0 失败 / 4 跳过 | 1 项为显式 MySQL 8 opt-in（M1 已真实执行通过），3 项为外部阿里云集成；199 条 warning | 通过，M2 可收口并进入 STEP-030 |

| 2026-07-16 | STEP-030 首次专项 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step030_observer_accounts_guard.py -q --tb=short` | 1 通过 / 2 测试基础设施错误 | 新测试复用 STEP-018 客户端却未导入其 pytest 夹具，业务断言未执行 | 导入既有 client/setup_db 夹具后重跑 |
| 2026-07-16 | STEP-030 专项与相关回归 | 上述专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_admin_auth.py tests/test_step029_observer_frontend_common.py tests/test_step030_observer_accounts_guard.py -q --tb=short --disable-warnings` | 专项 3 通过；相关 75 通过；0 失败 | — | observer 直访顺序、6 API 403/无变更、菜单过滤与 super_admin 生命周期通过 |
| 2026-07-16 | STEP-030 首次全量回归 | 全量标准命令 | 876 通过 / 2 失败 / 4 跳过 | 新测试模块未暴露 `override_get_db`，整套收集后被其他模块的全局 FastAPI 依赖覆写污染；独立和相关组合均通过 | 按 `tests/conftest.py` 模块隔离约定导入 `override_get_db`，未改业务代码 |
| 2026-07-16 | STEP-030 最终全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 878 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已在 M1 真实通过，3 项为外部阿里云集成；203 条 warning | 通过 |

| 2026-07-16 | STEP-031 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step031_observer_user_reports_logs_pages.py -q --tb=short` | 0 通过 / 4 预期失败 | 报表/系统日志页守卫未放行 observer，用户和详情动态写控件、3 个导出均未标记 | 红灯成立 |
| 2026-07-16 | STEP-031 实现后专项 | 同上专项命令 | 4 通过 / 0 失败 | 首次实现后 3 通过 / 1 测试编排失败：系统日志详情 onclick 为转义后动态字符串，测试误按静态字面量匹配 | 改为验证 `showLogDetail` 函数与安全转义 onclick 拼接后通过 |
| 2026-07-16 | STEP-031 相关回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step021_observer_exports.py tests/test_step022_observer_user_stats_logs.py tests/test_step027_observer_credential_status.py tests/test_step029_observer_frontend_common.py tests/test_step031_observer_user_reports_logs_pages.py -q --tb=short --disable-warnings` | 19 通过 / 0 失败 | — | 5 页静态契约、observer 读取/写拒绝、凭据状态、3 导出和公共动态助手回归通过 |
| 2026-07-16 | STEP-031 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 882 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项为外部阿里云集成；203 条 warning | 通过 |

| 2026-07-16 | STEP-032 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step032_observer_system_third_party_test_dashboard_pages.py -q --tb=short` | 1 通过 / 3 预期失败 | 系统监控/AI 测试未放行 observer，第三方和 AI 测试静态/动态写控件未标记 | 红灯成立 |
| 2026-07-16 | STEP-032 专项与相关回归 | 上述专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step023_observer_ai_read_roles.py tests/test_step025_observer_system_monitor.py tests/test_step027_observer_credential_status.py tests/test_step029_observer_frontend_common.py tests/test_step032_observer_system_third_party_test_dashboard_pages.py -q --tb=short --disable-warnings` | 专项 4 通过；相关 20 通过；0 失败 | 专项实现后首跑 1 项测试文案过度约束，改为对实际“凭据状态/已配置/未配置”分支断言 | 四页可读、写控件、凭据状态和后端读写边界通过 |
| 2026-07-16 | STEP-032 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 886 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；203 条 warning | 通过 |

| 2026-07-16 | STEP-033 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step033_observer_persona_prompt_safety_pages.py -q --tb=short` | 0 通过 / 4 预期失败 | 8 页角色未包含 observer，人格/Prompt/开关/安全规则静态与动态写控件未标记 | 红灯成立 |
| 2026-07-16 | STEP-033 专项与相关回归 | 上述专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step023_observer_ai_read_roles.py tests/test_step029_observer_frontend_common.py tests/test_step033_observer_persona_prompt_safety_pages.py tests/test_step012_content_safety.py tests/test_step026_prompt_config.py tests/test_chat_prompt_view.py -q --tb=short --disable-warnings` | 专项 4 通过；相关 35 通过；0 失败 | — | 8 页访问、静态/动态写控件、后端读写边界与既有 Prompt/安全回归通过 |
| 2026-07-16 | STEP-033 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 890 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；203 条 warning | 通过 |

| 2026-07-16 | STEP-034 TDD 红灯 | `env ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step034_observer_memory_vector_knowledge_pages.py -q --tb=short` | 0 通过 / 4 预期失败 | 3 页未放行 observer、写控件未标记，DashVector 仍返回掩码 Key 而无配置状态 | 红灯成立 |
| 2026-07-16 | STEP-034 专项与相关回归 | 上述专项命令；`env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest tests/test_step024_observer_domain_read_roles.py tests/test_step027_observer_credential_status.py tests/test_step029_observer_frontend_common.py tests/test_step034_observer_memory_vector_knowledge_pages.py tests/test_admin_vector_token_config.py tests/test_admin_character_knowledge.py -q --tb=short --disable-warnings` | 专项 4 通过；相关 27 通过；0 失败 | — | 三页、动态写控件、DashVector 敏感读取与既有向量/知识回归通过 |
| 2026-07-16 | STEP-034 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 894 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；205 条 warning | 通过 |

| 2026-07-16 | STEP-035 TDD 红灯 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step035_observer_agent_relationship_diary_pages.py --tb=short` | 1 通过 / 3 预期失败 | 4 页角色未包含 observer，Agent/关系/日记规则写控件未标记 | 红灯成立 |
| 2026-07-16 | STEP-035 专项与相关回归 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step035_observer_agent_relationship_diary_pages.py tests/test_step024_observer_domain_read_roles.py tests/test_step029_observer_frontend_common.py tests/test_diary.py --tb=short` | 32 通过 / 0 失败 | 32 条既有短密钥 warning | 4 页访问、静态/动态写控件、Tab、历史筛选分页及后端读写边界通过 |
| 2026-07-16 | STEP-035 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 898 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；205 条 warning | 通过 |

| 2026-07-16 | STEP-036 TDD 红灯 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step036_observer_life_plan_worldview_pages.py --tb=short` | 1 通过 / 3 预期失败 | 两页访问集合未包含 observer，静态/动态写入口未使用统一标记 | 红灯成立 |
| 2026-07-16 | STEP-036 专项与相关回归 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step036_observer_life_plan_worldview_pages.py tests/test_step026_observer_life_stream_reads.py tests/test_step029_observer_frontend_common.py tests/test_step001_life_feed_tables.py tests/test_step003_life_feed_config.py --tb=short` | 37 通过 / 0 失败 | 首次命令误引用 2 个不存在测试文件，未执行用例；修正为仓库现有测试后通过；3 条既有短密钥 warning | 两页访问、静态/动态写入口、读取交互、observer/ops 后端边界通过 |
| 2026-07-16 | STEP-036 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 902 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；205 条 warning | 通过 |

| 2026-07-16 | STEP-037 TDD 红灯 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step037_observer_feed_and_aware_pages.py --tb=short` | 1 通过 / 3 预期失败 | 三页访问集合未包含 observer，静态/动态写入口未使用统一标记 | 红灯成立 |
| 2026-07-16 | STEP-037 专项与相关回归 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step037_observer_feed_and_aware_pages.py tests/test_step026_observer_life_stream_reads.py tests/test_step029_observer_frontend_common.py tests/test_step011_feed_content.py tests/test_step013_feed_publish.py tests/test_step018_comment_reply.py tests/test_step019_agent_aware.py --tb=short` | 47 通过 / 0 失败 | 首次命令误引用 2 个不存在测试文件，未执行用例；修正为仓库现有测试后通过；3 条既有短密钥 warning | 三页访问、静态/动态写入口、列表详情与 observer/ops 后端边界通过 |
| 2026-07-16 | STEP-037 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 906 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；205 条 warning | 通过 |

| 2026-07-16 | STEP-038 TDD 红灯 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step038_observer_life_feed_config_pages.py --tb=short` | 0 通过 / 4 预期失败 | 三页访问集合未包含 observer，静态/动态配置控件未使用统一标记 | 红灯成立 |
| 2026-07-16 | STEP-038 专项与相关回归 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step038_observer_life_feed_config_pages.py tests/test_step010_life_config_publish_frontend.py tests/test_step026_observer_life_stream_reads.py tests/test_step029_observer_frontend_common.py tests/test_step003_life_feed_config.py tests/test_step004_life_prompt.py --tb=short` | 41 通过 / 0 失败 | 3 条既有短密钥 warning | 三页访问、静态/动态配置控件、7 个 CONFIRM 调用、observer 后端边界通过 |
| 2026-07-16 | STEP-038 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 910 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；204 条 warning；另有既有 AsyncMock 未 await RuntimeWarning | 通过 |

| 2026-07-16 | STEP-039 专用门禁 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step039_observer_backend_gate.py tests/test_admin_auth.py tests/test_step016_four_role_regression.py tests/test_step021_observer_exports.py tests/test_step022_observer_user_stats_logs.py tests/test_step023_observer_ai_read_roles.py tests/test_step024_observer_domain_read_roles.py tests/test_step025_observer_system_monitor.py tests/test_step026_observer_life_stream_reads.py tests/test_step027_observer_credential_status.py tests/test_step028_admin_route_audit.py tests/test_step030_observer_accounts_guard.py --tb=short --disable-warnings` | 98 通过 / 0 失败 | 首次长命令输出会话未保留最终摘要，使用相同测试集合和尾部摘要重新执行取得证据 | 159 路由、69 读、90 写、两个精确 POST 例外、匿名 OPTIONS、账号、三个导出、敏感状态与五角色组合门禁通过 |
| 2026-07-16 | STEP-039 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 913 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；204 条 warning；另有既有 AsyncMock 未 await RuntimeWarning | 通过 |
| 2026-07-16 | STEP-040 页面清单与组合门禁 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step040_admin_page_inventory.py tests/test_step030_observer_accounts_guard.py tests/test_step031_observer_user_reports_logs_pages.py tests/test_step032_observer_system_third_party_test_dashboard_pages.py tests/test_step033_observer_persona_prompt_safety_pages.py tests/test_step034_observer_memory_vector_knowledge_pages.py tests/test_step035_observer_agent_relationship_diary_pages.py tests/test_step036_observer_life_plan_worldview_pages.py tests/test_step037_observer_feed_and_aware_pages.py tests/test_step038_observer_life_feed_config_pages.py --tb=short` | 39 通过 / 0 失败 | 首次新增清单测试对两项页面细节做了超出文档的假设，出现 2 失败；校正测试边界后通过。收口复核曾误记为 42，按本行精确命令重跑并更正为真实 39 | 精确 35 页、26 个非 GET 页、25 个业务写页，STEP-030～038 页面证据完整，无 Playwright/CI |
| 2026-07-16 | STEP-040 浏览器缺陷回归 | `PYTHONPATH=. .venv-step001/bin/python -m pytest -q tests/test_step029_observer_frontend_common.py tests/test_step035_observer_agent_relationship_diary_pages.py tests/test_step040_admin_page_inventory.py --tb=short` 并对改动 JS 执行 `node --check` | 13 通过 / 0 失败 | 真实浏览器发现 `input[type=range]` 仅 `readOnly` 仍可拖动；先增加回归断言得到 1 预期失败，再把 range 纳入禁用型控件 | 修复后浏览器确认滑块为 `[disabled]`；35 页引用的公共静态资源统一增加阶段 B 版本参数避免旧缓存 |
| 2026-07-16 | STEP-040 全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 917 通过 / 0 失败 / 4 跳过 | 1 项 MySQL 8 opt-in 已真实通过，3 项外部阿里云集成；204 条 warning；另有既有 AsyncMock 未 await RuntimeWarning | 通过 |
| 2026-07-16 | STEP-040 35 页五角色浏览器验收 | `docs/progress/STEP-040_35页面五角色验收记录.md` 逐页清单 | 35 页通过 / 0 失败 | 无；对原角色无权且页面未前置守卫的直访，后端按原权限返回 403，未泄露业务数据 | observer 33 个鉴权页与 2 个公共页、原四角色合法页面及写控件无误伤；详见独立记录 |
| 2026-07-16 | STEP-040 项目所有者账号页复核 | 对比工作区 `accounts.html`、Docker 实际 GET 与用户当前 Chrome DOM；刷新后打开“新建账号”并将角色选为 `observer`（不提交） | 3 层对比及 1 项选择操作通过 / 0 失败 | 用户原标签页是 2026-04-22 旧 HTML，仅四角色；非 Docker 内容缺失或后端 schema 拒绝 | 刷新后为 2026-07-16 页面，新建/编辑下拉框均有未禁用的“观察者”，已选中并留给用户复核 |

| 2026-07-17 | STEP-040 最终人工门禁与账号清理 | 项目所有者确认“暂时没有问题，计划可以收尾”；Docker MySQL 按精确用户名且 `role=observer` 删除 `codex-step040-observer` | 人工门禁 1 通过 / 0 失败；账号 `before_count=1` / `after_count=0` | 首次清理脚本在导入不存在的同步 `SessionLocal` 时失败，未执行数据库写操作；改用容器 MySQL 精确条件后成功 | 门禁通过，临时账号清理完成 |
| 2026-07-17 | STEP-040 收尾首次全量回归 | `env TIKTOKEN_CACHE_DIR=/private/tmp/lxm-tiktoken-cache PATH=/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin ADMIN_JWT_SECRET=codex_test_admin_secret_20260715 PYTHONPATH=. .venv-step001/bin/python -m pytest -q --tb=short --disable-warnings` | 890 通过 / 28 失败 / 4 跳过 | 本机重启后 `tiktoken` 缓存目录丢失，沙箱 DNS 无法访问官方编码资源；28 项均为同一缓存缺失根因 | 未作为功能通过证据，恢复官方编码缓存后重跑 |
| 2026-07-17 | STEP-040 收尾最终全量回归 | 同上全量标准命令 | 918 通过 / 0 失败 / 4 跳过 | 204 条 warning；另有既有 AsyncMock 未 await RuntimeWarning | 缓存恢复后全量通过，收尾证据有效 |

## 部署与人工确认记录

| 日期 | 阶段 | 部署范围 | 全员重登/页面验收 | 稳定性结论 | 确认人 |
|------|------|---------|------------------|-----------|-------|
| 2026-07-16 12:04 CST | 阶段 A | backend 新镜像 + admin 挂载静态文件；Alembic head | 临时四角色烟测通过；实际 `super_admin`、`ops_admin` 2/2 重新登录正常 | 收口复核时连续运行约 54 分钟、0 重启；用户确认页面及登录正常，可继续下一 STEP | 用户（项目所有者） |
| 2026-07-16 17:02 CST | 阶段 B | backend 最终镜像 + 已版本化 admin 静态资源；Alembic head 已核对 | 五临时角色登录 5/5；observer 代表读取 200、写入/导出 403、凭据仅状态；35/35 页浏览器验收通过 | 17:11 CST 复核已连续运行约 8 分钟，`running=true`、`restart_count=0`、无 OOM/启动错误，13 个调度任务正常；存在既有 30-byte JWT HMAC 建议性 warning，不违反本 PRD 明确不增加密钥长度规则的边界；首轮烟测 422/404 由探测命令缺参/路径错误导致，修正后均为 200；项目所有者于 2026-07-17 完成最终人工确认 | Codex 机器证据 + 用户（项目所有者） |

| 2026-07-17 09:42 CST | 阶段 B 收口复核 | 不重建镜像；复核已部署 backend 容器、调度任务和临时账号清理 | 项目所有者确认暂无问题；临时 observer 账号删除后计数 0 | 复核时 `running=true`、`restart_count=0`、`oom_killed=false`；容器于 09:42 由外部启动/重建后连续运行，日志无 startup failed/traceback/fatal，周期调度任务持续成功 | 用户（项目所有者） + Codex 机器证据 |

## 变更记录

| 日期 | 变更描述 | 影响 STEP | 处理方式 |
|------|---------|---------|---------|
| 2026-07-15 | 按步骤文档审查确认修正职责、引用、验证要求和阶段文档同步边界 | STEP-002、017、018、022、029、030、040；全部 STEP 验证表 | 采用确认的 1A～5A；未修改原始 PRD、项目配置或业务代码 |
| 2026-07-15 | 完成 ADMIN_JWT_SECRET 统一校验与启动双守卫；保留不可运行的 `.env.example` 占位示例 | STEP-001 | 改动 `backend/config.py`、`backend/main.py`、`.env.example`、`tests/test_step001_admin_jwt_secret.py`；无阻塞，未更新正式契约 |
| 2026-07-16 | 为管理员增加会话版本字段及可回滚 Alembic 迁移，完成独立 MySQL 8.0 真实迁移闭环 | STEP-002 | 改动 `backend/models/admin_user.py`、`alembic/versions/v7a_admin_user_token_version.py`、`tests/test_step002_admin_token_version_migration.py`；未修改 `scripts/schema_ddl.sql`，无阻塞，未更新正式契约 |
| 2026-07-16 | Admin JWT 增加实时会话版本并在统一鉴权入口校验账号状态与版本 | STEP-003 | 改动 `backend/utils/admin_auth.py`、`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；无阻塞，未更新正式契约 |
| 2026-07-16 | 管理员登录查询增加行锁，第五次错误原子锁定并撤销旧会话 | STEP-004 | 改动 `backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；不自动解锁；真实 MySQL 8 并发实证由 STEP-015 执行；无阻塞，未更新正式契约 |
| 2026-07-16 | 收敛后台登录失败响应，增加不存在账号的伪哈希耗时保护和内部安全日志 | STEP-005 | 改动 `backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；未增加 IP＋账号限流；无阻塞，未更新正式契约 |
| 2026-07-16 | 自助改密成功时递增会话版本，使同账号全部旧 Token 失效 | STEP-006 | 改动 `backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；`admin/static/js/admin-api.js` 已符合清会话后跳转要求，仅验证未修改；未增加 90 天后端强制门禁；无阻塞，未更新正式契约 |
| 2026-07-16 | 管理员登出时递增会话版本，执行账号级全会话撤销 | STEP-007 | 改动 `backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；`admin/static/js/admin-api.js` 已符合请求后清会话要求，仅验证未修改；未实现单设备黑名单；无阻塞，未更新正式契约 |
| 2026-07-16 | 补齐账号重置密码与实际角色变化的会话撤销矩阵 | STEP-008 | 改动 `backend/routers/admin/accounts.py`、`tests/test_admin_auth.py`；备注、相同角色和解锁保持版本不变；未新增停用/启用接口；无阻塞，未更新正式契约 |
| 2026-07-16 | life-config 发布端点增加服务端精确 CONFIRM 校验 | STEP-009 | 改动 `backend/routers/admin/life_config_mgmt.py`、`tests/test_step009_life_config_publish_confirm.py`；未改变草稿、版本、历史、回滚或数据库结构；无阻塞，未更新正式契约 |
| 2026-07-16 | 现有 7 个 life-config 前端发布调用全部显式传递 CONFIRM | STEP-010 | 改动 4 个页面、`admin/static/js/life-feed-admin.js`、`tests/test_step010_life_config_publish_frontend.py`；未新增第 8 个入口；无阻塞，未更新正式契约 |
| 2026-07-16 | 新增共享、递归、幂等且失败关闭的凭据脱敏工具 | STEP-011 | 新增 `backend/utils/credential_redaction.py`、`tests/test_step011_credential_redaction.py`；不遮蔽 Prompt、对话、记忆、描述、版本或 `max_tokens`；无阻塞，未更新正式契约 |
| 2026-07-16 | 操作日志写入与列表、详情、Excel 导出统一执行双层凭据脱敏 | STEP-012 | 改动 `backend/utils/admin_auth.py`、`backend/routers/admin/operation_logs.py`，新增 `tests/test_step012_operation_log_redaction.py`；未改写历史行、未改变筛选分页或导出格式；无阻塞，未更新正式契约 |
| 2026-07-16 | 系统日志列表与 Excel 导出统一使用共享凭据脱敏工具 | STEP-013 | 改动 `backend/routers/admin/system_monitor.py`、`tests/test_system_monitor_logs.py`；未改变日志收集、级别筛选、排序或日期范围；无阻塞，未更新正式契约 |
| 2026-07-16 | 完成阶段 A 配置、会话、登录、CONFIRM、日志脱敏及后台相关权限 pytest 门禁 | STEP-014 | 未新增业务代码、CI/CD 或 Playwright；阶段门禁 107 通过，全量 823 通过；无阻塞，未更新正式契约 |
| 2026-07-16 | 在独立非生产 MySQL 8.0.46 完成登录行锁并发矩阵 | STEP-015 | 新增 opt-in `tests/test_step015_mysql_login_concurrency.py`；验证 5 次阈值、锁定后 4 次及不同账号行锁隔离；记录并修复测试事件循环问题；一次性数据库已删除；无业务代码改动，未更新正式契约 |
| 2026-07-16 | 完成阶段 A 四角色接口矩阵并据真实证据更新漏洞专档 | STEP-016 | 新增 `tests/test_step016_four_role_regression.py`，更新 `docs/security/admin-backend-vulns-2026-07.md`；已修项目标为已验证待部署，VULN-001/007、恶意锁号与部署门禁保持未修/未完成；正式契约仍未更新 |
| 2026-07-16 | 生成 M1 契约草案并完成阶段 A 本地 Docker 独立部署与机器烟测 | STEP-017（部分） | 新增 `M1_契约草案.md`；构建新 backend、幂等迁移并重建容器；历史 Token、四角色新登录、迁移和稳定性机器证据通过；正式契约与 `.cursorrules` 等待人工确认，阶段 B 未开放 |
| 2026-07-16 | 完成阶段 A 人工门禁并同步正式契约与长期规则 | STEP-017 | 两个实际管理员重新登录正常，用户确认稳定；`docs/contract.md` 与 `.cursorrules` 仅同步阶段 A 已生效事实，四角色不变；阶段 B 进入条件成立 |
| 2026-07-16 | 扩展 observer 合法账号角色与账号页展示 | STEP-018 | Pydantic 创建/编辑校验、ORM 注释、账号页创建/编辑选项与列表标签增加 observer；账号路由仍全部仅 `super_admin`；未改公共菜单、Header、正式契约或 `.cursorrules` |
| 2026-07-16 | 增加 observer 后端方法级集中总闸 | STEP-019 | `get_current_admin` 注入 Request，在完整身份校验后按数据库实时角色执行四写方法默认 403；仅精确放行登出和自助改密 POST；未替代路由 `require_role`，未处理 OPTIONS 或导出专项 |
| 2026-07-16 | 验证 CORS OPTIONS 匿名预检边界 | STEP-020 | 生产 CORS 中间件已满足需求；新增匿名预检、业务鉴权对比及账号无副作用测试；未修改生产代码或放宽业务读取鉴权 |
| 2026-07-16 | 三个内建导出路由增加 observer 专用拒绝依赖 | STEP-021 | 新增方法无关 `deny_observer_export`，分别挂到操作日志、数据报表、系统日志导出并保留原角色依赖；新增未来 export/download 路由清单门禁 |
| 2026-07-16 | 拆分用户、统计与操作日志读写角色集合 | STEP-022 | observer 仅加入确认的用户业务读取、统计读取和操作日志读取集合；日志导出使用独立原角色集合；用户记忆与 Open API Key 留待后续 STEP，写集合不变 |
| 2026-07-16 | 拆分 AI 配置与测试模块读写角色集合 | STEP-023 | 人格、Prompt、只读对话流 Prompt、测试用例、安全规则五模块全部路由按方法使用 READ/WRITE 集合；observer 仅加入 READ，不修改测试/发布状态机 |
| 2026-07-16 | 拆分记忆、向量、知识等七模块读写角色集合 | STEP-024 | 七个路由模块及 users 中两类用户向量路由按 GET 与写方法拆分集合；特殊 Agent/日记历史保留原 ops 权限并加入 observer；数据结构不变 |
| 2026-07-16 | 拆分系统监控读取、写入与导出角色集合 | STEP-025 | observer 加入系统状态、第三方状态和系统日志读取集合；第三方保存/测试与日志导出保持原 super/tech 边界，日志继续共享脱敏 |
| 2026-07-16 | 开放生活流六模块 observer 读取 | STEP-026 | 六文件 `_READ_ROLES` 纳入 observer，朋友圈自动发布配置 GET 从写集合切到读集合；所有业务写方法继续原角色与总闸 |
| 2026-07-16 | 实现 observer 凭据状态化读取 | STEP-027 | 第三方状态按实时角色仅附加配置布尔，Open API Key 对 observer 仅返回 enabled；两个页面只显示已/未配置且隐藏配置/生成入口，其他角色响应保持 |
| 2026-07-16 | 建立全量 Admin 路由安全审计门禁 | STEP-028 | 新增惰性路由展开审计，固定当前 159 路由规模并检查鉴权、写入口、导出标记、GET/HEAD 禁止调用和直接缓存写白名单；未改生产代码 |
| 2026-07-16 | 完成 observer 公共前端只读底座并收口 M2 | STEP-029 | `admin-api.js` 新增菜单/Header、静态+动态只读助手与非读请求兜底；`admin-common.css` 仅定向作用于标记控件；新增 STEP-029 测试和 `M2_契约草案.md`，正式契约与 `.cursorrules` 不变 |
| 2026-07-16 | 完成 observer 账号页与 API 专项验证 | STEP-030 | 现有 `accounts.html` 守卫和后端 super-only 依赖已满足，业务代码无需修改；新增直访顺序、6 API 拒绝、无变更和 super_admin 回归测试，并补齐全套夹具隔离 |
| 2026-07-16 | 完成用户、报表与日志 5 页 observer 只读改造 | STEP-031 | 报表/系统日志放行 observer；用户列表状态、用户详情静态/动态行操作与弹窗提交、报表/操作日志/系统日志 3 导出统一标记；读取交互不标记 |
| 2026-07-16 | 完成系统、第三方、AI 测试与看板 4 页 observer 只读改造 | STEP-032 | 系统监控和 AI 测试放行 observer；第三方配置/凭据/测试/保存与 AI 测试参数/生成/清空/用例保存及动态弹窗提交统一标记；看板无写请求 |

## STEP 交付记录

### STEP-001（2026-07-15）

- 改动文件：`backend/config.py`、`backend/main.py`、`.env.example`、`tests/test_step001_admin_jwt_secret.py`。
- 实现结果：唯一 `validate_admin_jwt_secret()` 由配置读取与 lifespan 复用；五类非法值启动前失败；合法自定义密钥不附加长度、复杂度或轮换限制；用户端 `JWT_SECRET` 未修改。
- 验证：专项 12 通过、相关回归 58 通过、全量回归 777 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-001-01`，见“契约更新记录”；遵守 M1 收口规则，正式 `docs/contract.md` 未修改。
- 阻塞项：无。
- 完成标志：五项全部满足，STEP-001 已更新为 ✅；下一环节为 STEP-002。

### STEP-002（2026-07-16）

- 改动文件：`backend/models/admin_user.py`、`alembic/versions/v7a_admin_user_token_version.py`、`tests/test_step002_admin_token_version_migration.py`。
- 实现结果：ORM 与数据库迁移均定义 `token_version INTEGER NOT NULL DEFAULT 0`；迁移 head 正确衔接 `v6e_display_comments_001`，支持 `downgrade -1`；未修改 `scripts/schema_ddl.sql`，未增加 observer 或其他表。
- 验证：专项与相关回归 40 通过；独立 MySQL 8.0 完成首次升级、旧行/新行/NULL/列定义检查、回滚和再次升级；最终全量回归 780 通过 / 0 失败 / 3 跳过。首次全量因本机 `tiktoken` 缓存丢失出现 28 个环境失败，恢复独立缓存后全部通过，记录未省略。
- 契约条目草稿：`M1-STEP-002-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；临时 MySQL 测试库已在验证后删除。
- 完成标志：五项全部满足，STEP-002 已更新为 ✅；下一环节为 STEP-003。

### STEP-003（2026-07-16）

- 改动文件：`backend/utils/admin_auth.py`、`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`。
- 实现结果：登录签发的 Admin JWT 携带整数 `token_version`；`get_current_admin` 以数据库账号为最终事实，校验账号存在、启用、未锁定和实时版本匹配；历史无版本、非整数版本、版本错误继续统一返回 HTTP 401；原有 `type=admin` 隔离保留。
- 验证：专项 32 通过、相关回归 67 通过、全量回归 787 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-003-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无。
- 完成标志：五项全部满足，STEP-003 已更新为 ✅；下一环节为 STEP-004。

### STEP-004（2026-07-16）

- 改动文件：`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`。
- 实现结果：存在账号的登录查询使用 MySQL `SELECT ... FOR UPDATE`；同一请求事务内执行锁定检查、密码校验、计数递增、第五次锁定、版本递增和成功清零；第五次错误后 `login_fail_count=5`、`is_locked=True`、`token_version` 仅递增一次，锁定后正确或错误密码均不重复改变状态。
- 验证：专项 33 通过、相关回归 68 通过、全量回归 788 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。真实 MySQL 8 并发争用不以 SQLite 替代，依步骤文档留在 STEP-015 执行。
- 契约条目草稿：`M1-STEP-004-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无。
- 完成标志：五项全部满足，STEP-004 已更新为 ✅；下一环节为 STEP-005。

### STEP-005（2026-07-16）

- 改动文件：`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`。
- 实现结果：不存在账号、密码错误、已锁定和已停用账号的登录响应完全一致，均为 HTTP 200、`code=20001`、`data=null`、消息“账号或密码错误”；删除对外剩余次数、锁定和停用信息；不存在账号执行固定伪 bcrypt；安全日志以 `account_not_found`、`password_wrong`、`account_locked`、`account_inactive` 区分真实原因，且不记录提交密码、Token 或 Secret。
- 验证：专项 36 通过、相关回归 71 通过、全量回归 791 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-005-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未实施 IP＋账号限流。
- 完成标志：五项全部满足，STEP-005 已更新为 ✅；下一环节为 STEP-006。

### STEP-006（2026-07-16）

- 改动文件：`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；验证但未修改 `admin/static/js/admin-api.js`。
- 实现结果：密码校验全部通过后更新密码与修改时间，并把 `token_version` 精确递增一次；同账号两个旧 Token 随后访问均为 401，新密码重新登录获得携带新版本的 Token 并可访问；旧密码错误、新旧相同、确认不一致和强度不足均保持原错误码，密码哈希与版本不变；前端改密成功后先清除 sessionStorage 再跳转登录页。
- 验证：专项 41 通过、相关回归 76 通过、全量回归 796 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-006-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未增加 90 天后端强制改密门禁。
- 完成标志：五项全部满足，STEP-006 已更新为 ✅；下一环节为 STEP-007。

### STEP-007（2026-07-16）

- 改动文件：`backend/routers/admin/auth.py`、`tests/test_admin_auth.py`；验证但未修改 `admin/static/js/admin-api.js`。
- 实现结果：有效 Admin JWT 登出时把当前账号 `token_version` 精确递增一次并保留登出操作日志、成功响应；同账号多个旧 Token 全部失效，其他管理员 Token 不受影响，原密码重新登录获得新版本 Token 并正常访问；前端完成请求后清除 sessionStorage 再跳转登录页。
- 验证：专项 43 通过、相关回归 78 通过、全量回归 798 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-007-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未实现单设备 Token 黑名单。
- 完成标志：五项全部满足，STEP-007 已更新为 ✅；下一环节为 STEP-008。

### STEP-008（2026-07-16）

- 改动文件：`backend/routers/admin/accounts.py`、`tests/test_admin_auth.py`。
- 实现结果：超级管理员重置他人密码时目标版本递增一次并撤销旧 Token；把他人角色实际改为不同合法角色时递增一次；仅改备注、提交与原值相同角色、手动解锁均不递增；账号锁定导致的旧 Token 在解锁后仍为 401，重新登录的新 Token 正常。
- 验证：专项 45 通过、相关回归 80 通过、全量回归 800 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-008-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未新增管理员停用/启用接口或 UI。
- 完成标志：五项全部满足，STEP-008 已更新为 ✅；下一环节为 STEP-009。

### STEP-009（2026-07-16）

- 改动文件：`backend/routers/admin/life_config_mgmt.py`、`tests/test_step009_life_config_publish_confirm.py`。
- 实现结果：`PublishBody.confirm_text` 允许缺省或 `null` 进入端点；发布逻辑最前端严格校验值必须等于 `CONFIRM`；缺失、空值、纯空白和错误文本统一返回业务码 `20021`，且在失败时不读取生效配置、不调用发布服务；精确值进入原发布流程，无权限角色即使提交正确值仍为 403。
- 验证：专项 7 通过、相关回归 87 通过、全量回归 807 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-009-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；CONFIRM 未被实现为二次认证。
- 完成标志：五项全部满足，STEP-009 已更新为 ✅；下一环节为 STEP-010。

### STEP-010（2026-07-16）

- 改动文件：`admin/pages/life-feed-global.html`、`admin/pages/life-feed-prompts.html`、`admin/pages/life-feed-system.html`、`admin/pages/life-plan.html`、`admin/static/js/life-feed-admin.js`、`tests/test_step010_life_config_publish_frontend.py`。
- 实现结果：精确扫描到现有 7 个 `/api/admin/life-config/publish` 调用，7/7 请求体均保留原 `config_key`、`config_value` 并新增 `confirm_text: 'CONFIRM'`；每个调用点均位于生产共享 `showConfirmInput` 确认回调内，没有新增第 8 个入口。
- 验证：STEP-009/010 专项 9 通过、相关回归 89 通过、全量回归 809 通过 / 0 失败 / 3 跳过；浏览器使用生产共享确认组件验证取消、错误文本和精确文本三种交互均符合预期；真实命令和交互证据见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-010-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未修改人格、Step5/Step5.5 发布逻辑。
- 完成标志：五项全部满足，STEP-010 已更新为 ✅；下一环节为 STEP-011。

### STEP-011（2026-07-16）

- 改动文件：`backend/utils/credential_redaction.py`、`tests/test_step011_credential_redaction.py`。
- 实现结果：新增共享 `redact_credentials()`；dict/list 递归复制，JSON 字符串解析后递归并保持字符串契约，非 JSON 仅精确匹配 PRD 指定的凭据赋值、Authorization 与具有凭据形态的 Bearer；大小写不敏感，统一输出 `[REDACTED]`；单字段异常失败关闭且不向调用方抛出。
- 验证：TDD 红灯 9 项预期失败；实现后专项 9 通过、相关回归 59 通过、全量回归 818 通过 / 0 失败 / 3 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M1-STEP-011-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未批量改写历史数据，未遮蔽 Prompt、对话、记忆、描述、版本或 `max_tokens`。
- 完成标志：五项全部满足，STEP-011 已更新为 ✅；下一环节为 STEP-012。

### STEP-012（2026-07-16）

- 改动文件：`backend/utils/admin_auth.py`、`backend/routers/admin/operation_logs.py`、`tests/test_step012_operation_log_redaction.py`。
- 实现结果：`log_operation` 对目标描述、修改前和修改后字段入库前逐字段脱敏；列表目标描述、详情三个审计字段及 Excel 导出三个字段返回前再次调用同一共享工具；异常字段统一失败关闭为 `[REDACTED]`，审计写入和读取不因脱敏异常中断。
- 验证：TDD 红灯 3 项预期失败；实现后专项 3 通过、相关回归 57 通过、全量回归 821 通过 / 0 失败 / 3 跳过；测试直接插入历史明文并确认三类读取出口不泄露，同时原数据库行保持明文以证明未执行批量改写。
- 契约条目草稿：`M1-STEP-012-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；列表分页、筛选和 Excel 格式未改变，历史数据库记录未批量改写。
- 完成标志：五项全部满足，STEP-012 已更新为 ✅；下一环节为 STEP-013。

### STEP-013（2026-07-16）

- 改动文件：`backend/routers/admin/system_monitor.py`、`tests/test_system_monitor_logs.py`。
- 实现结果：系统日志列表仅在分页结果返回前逐条调用共享脱敏工具；Excel 导出在生成单元格前调用同一入口；凭据赋值及 Authorization/Bearer 被遮蔽，普通消息、Prompt、描述和 `max_tokens` 保持原样；异常时仅将消息失败关闭并保留时间、级别、模块结构。
- 验证：TDD 红灯 2 项预期失败；实现后专项 6 通过、相关回归 63 通过、全量回归 823 通过 / 0 失败 / 3 跳过；既有解析、跨文件排序、级别过滤与日期范围测试继续通过。
- 契约条目草稿：`M1-STEP-013-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未改变日志文件收集、级别筛选、排序和日期范围，也未按角色区分脱敏结果。
- 完成标志：五项全部满足，STEP-013 已更新为 ✅；下一环节为 STEP-014。

### STEP-014（2026-07-16）

- 改动文件：无业务代码改动；复用 STEP-001～013 已新增/调整的 pytest 与现有后台测试。
- 实现结果：以显式独立 `ADMIN_JWT_SECRET` 运行阶段 A 自动化门禁，覆盖密钥双守卫、迁移与会话版本、登录锁定和统一响应、会话撤销矩阵、CONFIRM 后端及 7 个静态入口、共享脱敏、操作日志双层脱敏、系统日志列表/导出，以及后台认证、账号、配置和既有角色权限相关回归。
- 验证：阶段 A 专项门禁 107 通过 / 0 失败；随后全量回归 823 通过 / 0 失败 / 3 跳过；跳过项均为需显式开启的外部阿里云集成测试，未把跳过项计作阶段 A 安全通过证据。
- 契约条目草稿：`M1-STEP-014-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；未新增 CI/CD 或 Playwright。
- 完成标志：五项全部满足，STEP-014 已更新为 ✅；下一环节为 STEP-015。

### STEP-015（2026-07-16）

- 改动文件：新增 `tests/test_step015_mysql_login_concurrency.py`；更新本进度文档。业务代码未改动。
- 实现结果：测试仅在显式 `RUN_STEP015_MYSQL8=1` 且指向独立数据库时执行，并在连接后断言版本为 MySQL 8；真实环境为 `lxm_mysql` MySQL 8.0.46、一次性数据库 `lxm_step015_codex_019f6545`。
- 验证：同账号并发规模 5，最终 `login_fail_count=5`、`is_locked=true`、`token_version=1`；锁定后再并发 4 次状态不变；持有账号 A 行锁时，账号 B 的错密登录在 3 秒门限内完成且状态为 `(1,false,0)`。专项最终 1 通过 / 0 失败，相关回归 45 通过，全量回归 823 通过 / 0 失败 / 4 跳过。
- 失败记录：沙箱内首次连接因本地网络权限产生 1 个环境错误；授权环境首次执行因模块级异步夹具跨事件循环产生 1 个测试基础设施失败。改为函数级夹具后同命令通过；两次失败均未被当作业务通过证据。
- 契约条目草稿：`M1-STEP-015-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；一次性数据库已删除并查询确认不存在，SQLite 结果未替代 MySQL 8 验证。
- 完成标志：五项全部满足，STEP-015 已更新为 ✅；下一环节为 STEP-016。

### STEP-016（2026-07-16）

- 改动文件：新增 `tests/test_step016_four_role_regression.py`；更新 `docs/security/admin-backend-vulns-2026-07.md` 与本进度文档。
- 实现结果：四个现有角色均完成真实登录；life-config 读取对四角色保持可达，草稿写与发布权限保持 `super_admin/ai_trainer`，账号管理保持仅 `super_admin`，操作日志导出保持 `super_admin/ops_admin/tech_ops`，系统日志导出保持 `super_admin/tech_ops`。测试使用非法配置键只验证角色路径，不产生有效业务配置或发布副作用。
- 验证：四角色专项 1 通过（4 角色 × 登录、读取、写入、发布、账号、两类导出）；阶段 A 安全门禁 108 通过 / 0 失败；漏洞专项组合 42 通过、后台认证 45 通过、MySQL 8 专项 1 通过；最终全量 824 通过 / 0 失败 / 4 跳过。
- 文档结果：漏洞专档仅把 VULN-002/003/004/005/006/008 响应统一部分/009 更新为“已验证，待部署确认”；VULN-001、VULN-007、VULN-008 恶意锁号风险仍明确未修；阶段 A 部署与人工确认仍未勾选。
- 契约条目草稿：`M1-STEP-016-01`，见“契约更新记录”；正式 `docs/contract.md` 未修改。
- 阻塞项：无；STEP-017 的独立部署环境、全员重登通知、运行稳定性观察和人工确认尚未执行。
- 完成标志：五项全部满足，STEP-016 已更新为 ✅；下一环节为 STEP-017。

### STEP-017（2026-07-16）

- 改动文件：新增 `docs/contract/drafts/管理后台观察者与安全加固/M1_契约草案.md`；更新 `docs/contract.md`、`.cursorrules`、漏洞专档与本进度文档。
- 已完成：部署前密钥与迁移检查；backend 镜像构建；Alembic `upgrade head`；阶段 A backend 重建；admin 挂载静态文件同步；历史无版本 Token 401；临时四角色新登录和代表性合法接口 200；临时账号清理；机器稳定性观察；两个实际管理员重新登录；阶段 A 正式契约与长期规则同步。
- 部署证据：2026-07-16 12:04 CST 启动；收口复核时 `running=true`、`restart_count=0`、连续运行约 54 分钟。数据库实际管理员为 `super_admin=1`、`ops_admin=1`，用户确认两个账号均可正常登录并允许继续下一 STEP。
- 契约条目：正式同步 `M1-STEP-001-01`～`M1-STEP-016-01` 及部署门禁事实；角色体系仍为四角色，未把 `observer` 写成已上线。
- 阻塞项：无；原人工门禁已于 2026-07-16 解决。
- 完成标志：五项全部满足，STEP-017 已更新为 ✅；阶段 A 完成，总完成数 17/40；下一环节为 STEP-018。

### STEP-018（2026-07-16）

- 改动文件：`backend/schemas/admin_auth.py`、`backend/models/admin_user.py`、`admin/pages/accounts.html`、`tests/test_admin_auth.py`、本进度文档。
- 实现结果：创建/编辑账号 schema 接受 `observer` 且保留原四角色；ORM 角色注释扩展 observer；账号页创建/编辑两个下拉及列表标签展示“观察者”。账号管理 GET/POST/PUT/DELETE、重置、解锁继续全部使用 `require_role("super_admin")`，未修改公共菜单或 Header。
- 验证：TDD 修正测试编排后红灯为 3 个预期失败；实现后专项/相关 13 通过、账号文件 56 通过、全量 835 通过 / 0 失败 / 4 跳过。超级管理员完成 observer 创建、实际角色往返变化、重置、锁定后解锁、重新登录和删除；ops/ai/tech/observer 对 6 类账号 API 共 24 次调用均 403 且不返回账号数据。
- 契约条目草稿：`M2-STEP-018-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未新增数据库迁移、停用/启用、公共菜单、Header 或观察者通用读写权限。
- 完成标志：五项全部满足，STEP-018 已更新为 ✅；总完成数 18/40；下一环节为 STEP-019。

### STEP-019（2026-07-16）

- 改动文件：`backend/utils/admin_auth.py`、`tests/test_admin_auth.py`、本进度文档。
- 实现结果：统一 `get_current_admin` 注入 Request，完成 JWT 类型/签名/过期、`token_version`、数据库实时账号存在/启用/未锁定/实时角色检查后，再对 observer 的 POST/PUT/PATCH/DELETE 执行默认 403。例外集合仅含完整二元组 `POST /api/admin/auth/logout`、`POST /api/admin/auth/change-password`；查询串不改变路径，前缀/相似路径和错误方法不放行。GET/HEAD 仅通过本方法规则，仍由路由已有 `require_role` 决定业务访问。
- 验证：TDD 红灯 5 项预期失败；实现后专项 8 通过、账号鉴权相关 64 通过、原四角色矩阵 1 通过、全量 843 通过 / 0 失败 / 4 跳过。探针确认四写方法未进入端点且数据库备注不变化；两个真实自助端点进入既有业务校验；伪造、过期、锁定、停用、无版本、版本不匹配 Token 均先返回 401。
- 契约条目草稿：`M2-STEP-019-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未使用路径前缀白名单，未替代已有 `require_role`，未提前实现 STEP-020 OPTIONS 或 STEP-021 导出专项。
- 完成标志：五项全部满足，STEP-019 已更新为 ✅；总完成数 19/40；下一环节为 STEP-020。

### STEP-020（2026-07-16）

- 改动文件：`tests/test_admin_auth.py`、本进度文档；生产代码无需调整，现有 `backend/main.py` 的 CORS 中间件顺序和 `backend/utils/admin_auth.py` 的方法总闸已满足原文边界。
- 实现/验证结果：匿名带 Origin 与预检头的 OPTIONS 在账号写端点前返回纯文本 `OK` 和 CORS 头，不含后台业务数据；携带写请求体也不会创建账号或改变账号会话版本。匿名业务 GET、POST 均返回 401；显式 HEAD 探针使用同一统一依赖并返回 401。
- 验证：首次专项因测试客户端 API 误用出现 1 个基础设施失败，修正后专项 3 通过、后台认证相关 67 通过、全量回归 846 通过 / 0 失败 / 4 跳过；真实命令见“测试与验收记录”。
- 契约条目草稿：`M2-STEP-020-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未为 OPTIONS 增加业务响应，未放宽 GET/HEAD 或写方法鉴权。
- 完成标志：五项全部满足，STEP-020 已更新为 ✅；总完成数 20/40；下一环节为 STEP-021。

### STEP-021（2026-07-16）

- 改动文件：`backend/utils/admin_auth.py`、`backend/routers/admin/operation_logs.py`、`backend/routers/admin/stats.py`、`backend/routers/admin/system_monitor.py`、新增 `tests/test_step021_observer_exports.py`、本进度文档。
- 实现结果：新增 `deny_observer_export` 专用依赖，在统一身份校验后按数据库实时角色拒绝 observer，不读取 HTTP 方法；三个现有导出路由均直接挂载该依赖并保留原 `require_role`。清单测试自动枚举 Admin 路径中的 export/download 标记，当前精确覆盖三个端点，未来新增但漏挂依赖会失败。
- 验证：TDD 红灯为缺少依赖的 1 个收集错误；实现后两次路由清单测试因 FastAPI 惰性路由包装的测试编排问题失败并已修正；最终专项 3 通过、相关回归 22 通过、全量 849 通过 / 0 失败 / 4 跳过。observer 三端点均 403 且无文件响应头，tech/ops 原合法路径仍返回 Excel，GET 导出探针证明规则与方法无关。
- 契约条目草稿：`M2-STEP-021-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；不承诺阻止截图、复制或分页聚合，未删除原有角色依赖。
- 完成标志：五项全部满足，STEP-021 已更新为 ✅；总完成数 21/40；下一环节为 STEP-022。

### STEP-022（2026-07-16）

- 改动文件：`backend/routers/admin/users.py`、`backend/routers/admin/stats.py`、`backend/routers/admin/operation_logs.py`、新增 `tests/test_step022_observer_user_stats_logs.py`、本进度文档。
- 实现结果：建立用户业务读取、报表读取、Liblib 统计读取、操作日志读取与操作日志导出五组明确角色集合；observer 仅加入用户列表/详情/对话/情绪/日记、四类统计 GET、脱敏操作日志列表/详情。操作日志导出仍使用原三角色集合；用户向量记忆和 Open API Key 未提前开放，用户状态、重置密码、生成 Key 等写权限不变。
- 验证：TDD 红灯 1 项预期失败；实现后专项曾因样本定位的测试编排问题失败 1 项并已修正；最终专项 3 通过、相关 18 通过、全量 852 通过 / 0 失败 / 4 跳过。observer 日志响应不含历史明文凭据，六类写/导出请求均 403 且用户密码/状态不变；原四角色逐项矩阵保持。
- 契约条目草稿：`M2-STEP-022-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；账号、用户向量记忆与 Open API Key 状态读取分别保持由既定后续 STEP 处理。
- 完成标志：五项全部满足，STEP-022 已更新为 ✅；总完成数 22/40；下一环节为 STEP-023。

### STEP-023（2026-07-16）

- 改动文件：`backend/routers/admin/persona.py`、`backend/routers/admin/prompt_mgmt.py`、`backend/routers/admin/chat_prompt_view.py`、`backend/routers/admin/test_cases.py`、`backend/routers/admin/safety_rules.py`、新增 `tests/test_step023_observer_ai_read_roles.py`、本进度文档。
- 实现结果：五个模块均以 `_READ_ROLES=(super_admin, ai_trainer, observer)` 和 `_WRITE_ROLES=(super_admin, ai_trainer)` 明确区分；全部 GET/HEAD 使用读取集合，PUT/POST/DELETE 使用写集合。observer 可读人格、Step5/Step5.5、历史、只读对话流 Prompt、测试用例和安全规则，不能保存、测试、发布、回滚、导入或删除。
- 验证：TDD 红灯 2 项预期失败；相关回归首次因漏设本地 tiktoken 缓存目录出现 2 个网络环境失败，补充既有缓存变量后通过；最终专项 4 通过、相关 26 通过、全量 856 通过 / 0 失败 / 4 跳过。AST 门禁逐路由覆盖五文件，13 个代表性写调用均 403。
- 契约条目草稿：`M2-STEP-023-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；VULN-001 测试/发布可信状态机仍保持未修，未被本 STEP 扩展。
- 完成标志：五项全部满足，STEP-023 已更新为 ✅；总完成数 23/40；下一环节为 STEP-024。

### STEP-024（2026-07-16）

- 改动文件：`backend/routers/admin/memory_mgmt.py`、`vector_config.py`、`knowledge_mgmt.py`、`agent_mgmt.py`、`relationship_mgmt.py`、`emotion_config.py`、`world_state_mgmt.py`、`users.py`、新增 `tests/test_step024_observer_domain_read_roles.py`、调整 STEP-022 阶段性测试、本进度文档。
- 实现结果：七模块全路由建立 READ/WRITE 集合，observer 只加入 READ；Agent 消息与日记历史使用包含原 ops 权限的专用 HISTORY_READ 集合。用户记忆和私有设定的 GET 使用新增读取集合，三类写方法继续原集合。Step6、DashVector 非敏感参数、召回/Token 数值、知识、Agent、关系/日记、情绪和世界状态可读。
- 验证：TDD 红灯 2 项预期失败；两轮测试编排修正后专项 2 通过、相关 40 通过。首次全量仅因 STEP-022 的阶段性“用户向量尚未开放”断言与本 STEP 最终状态冲突而失败，移除过时断言后全量 858 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M2-STEP-024-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未改变页面归属、数据结构或 Embedding 配置定位，所有测试连接/保存/生成/删除仍为写权限。
- 完成标志：五项全部满足，STEP-024 已更新为 ✅；总完成数 24/40；下一环节为 STEP-025。

### STEP-025（2026-07-16）

- 改动文件：`backend/routers/admin/system_monitor.py`、新增 `tests/test_step025_observer_system_monitor.py`、本进度文档。
- 实现结果：新增 `_SYSTEM_READ_ROLES`、`_SYSTEM_WRITE_ROLES`、`_SYSTEM_EXPORT_ROLES`；observer 只加入系统状态、第三方运行状态、系统日志 GET。第三方配置 PUT、连接测试 POST 和系统日志导出 POST 保持原 super/tech 角色，并继续使用导出专用 observer 拒绝依赖。
- 验证：TDD 红灯 1 项预期失败；实现后首次相关组合因测试日志文件名与生产映射不一致失败 1 项，按实际 `_LOG_TYPE_FILE_MAP` 修正后专项/相关 12 通过；全量 861 通过 / 0 失败 / 4 跳过。observer 日志响应不含样本密钥，外部测试函数未执行；原 super/tech 读取和导出通过。
- 契约条目草稿：`M2-STEP-025-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未新增凭据片段读取，未改变系统监控缓存语义。
- 完成标志：五项全部满足，STEP-025 已更新为 ✅；总完成数 25/40；下一环节为 STEP-026。

### STEP-026（2026-07-16）

- 改动文件：`backend/routers/admin/life_config_mgmt.py`、`life_plan_mgmt.py`、`feed_mgmt.py`、`feed_comment_mgmt.py`、`agent_aware_mgmt.py`、`worldview_mgmt.py`、新增 `tests/test_step026_observer_life_stream_reads.py`、本进度文档。
- 实现结果：六个生活流模块的读取集合全部加入 observer；原先误用写集合的朋友圈自动发布配置 GET 改为读取集合。life-config、计划、内容/详情、评论/详情、感知队列/详情、世界观快照/事件均可读，所有生成、草稿、发布、编辑、显隐、重试、删除和重置写方法仍不含 observer。
- 验证：TDD 红灯 2 项预期失败；实现后首次专项因测试触发真实 Redis 连接出现 1 个环境失败，沿调用链定位并模拟只读配置服务后通过；最终专项 2 通过、相关 86 通过、全量 863 通过 / 0 失败 / 4 跳过。observer 与既有 ops 读取正常，8 类写调用 403。
- 契约条目草稿：`M2-STEP-026-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未改变草稿/版本/回滚/发布一致性或新增生活流功能。
- 完成标志：五项全部满足，STEP-026 已更新为 ✅；总完成数 26/40；下一环节为 STEP-027。

### STEP-027（2026-07-16）

- 改动文件：`backend/routers/admin/system_monitor.py`、`backend/routers/admin/users.py`、`admin/pages/third-party.html`、`admin/pages/user-detail.html`、新增 `tests/test_step027_observer_credential_status.py`、调整 STEP-022 阶段性测试、本进度文档。
- 实现结果：第三方状态公共缓存继续只保存运行指标，observer 响应在缓存读取后按数据库实时配置附加 `credential_configured`，不污染其他角色缓存；用户 Open API Key 对 observer 仅返回 `enabled`。第三方页对 observer 显示凭据状态且不渲染配置入口，用户详情只显示已/未配置并隐藏 Key 元数据和生成按钮。
- 验证：TDD 红灯 3 项预期失败；实现后专项 4 通过、相关 10 通过、全量 867 通过 / 0 失败 / 4 跳过。响应扫描确认不含第三方原文、首尾/掩码片段、用户 prefix 或 hash；未配置分支与写/测试 403 通过；原 ops 仍获得既有 prefix 元数据。
- 契约条目草稿：`M2-STEP-027-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未改变其他角色接口权限或统一日志脱敏。
- 完成标志：五项全部满足，STEP-027 已更新为 ✅；总完成数 27/40；下一环节为 STEP-028。

### STEP-028（2026-07-16）

- 改动文件：新增 `tests/test_step028_admin_route_audit.py`、本进度文档；生产代码无需调整。
- 实现/审计结果：兼容当前 FastAPI 惰性 `_IncludedRouter`，展开并审计 159 个 Admin 路由。除 `POST /auth/login` 外全部含递归统一鉴权依赖；90 个写方法全部进入统一 observer 总闸；3 个 export/download 精确命中专用拒绝；69 个 GET/HEAD 处理器禁止数据库和业务写调用，直接 `_set_cached` 仅允许系统/第三方状态两个有限 TTL 缓存端点。
- 验证：首次专项的 2 个失败均为审计规则误报（匿名登录未排除、本地 set.add 被误判），按调用接收者收敛后专项 3 通过；STEP-019/020 11 通过、STEP-021～028 24 通过、全量 870 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M2-STEP-028-01`，见“契约更新记录”；按 M2 规则不修改正式 `docs/contract.md` 与 `.cursorrules`。
- 阻塞项：无；未把缓存回填误判为业务写入，未借审计重构业务路由。
- 完成标志：五项全部满足，STEP-028 已更新为 ✅；总完成数 28/40；下一环节为 STEP-029。

### STEP-029（2026-07-16）

- 改动文件：`admin/static/js/admin-api.js`、`admin/static/css/admin-common.css`、新增 `tests/test_step029_observer_frontend_common.py`、调整 `tests/test_admin_auth.py` 的 STEP-018 过时阶段性断言，新增 `docs/contract/drafts/管理后台观察者与安全加固/M2_契约草案.md`，更新本进度文档。
- 实现结果：新增 `isObserver()`和精确请求允许判断；observer 菜单复用 super_admin 业务导航但过滤账号管理，Header 显示“观察者”。`applyObserverReadOnly()` 只处理 `data-write-action` 标记的静态/动态节点：写按钮和链接隐藏，文本控件只读，选择、开关和文件控件禁用；未标记的搜索、筛选、分页、Tab、详情、复制和 GET 刷新不会被统一禁用。`adminRequest()` 对 observer 仅允许 GET/HEAD 与精确登出/自助改密 POST。
- 验证：TDD 红灯 5 项预期失败；实现后静态专项 5 通过、JavaScript 语法 1 通过、Node VM 运行时 22 断言通过、相关回归 78 通过；最终全量 875 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M2-STEP-029-01`，并已汇总 `M2-STEP-018-01`～`M2-STEP-029-01` 到 `M2_契约草案.md`；正式 `docs/contract.md` 与 `.cursorrules` 未修改。
- 阻塞项：无；M2 未提前修改 35 个页面的专项写控件，未部署阶段 B，页面闭环与人工验收仍由 STEP-030～040 严格按序执行。
- 完成标志：五项全部满足，STEP-029 已更新为 ✅；M2 完成，总完成数 29/40；下一环节为 STEP-030。

### STEP-030（2026-07-16）

- 改动文件：新增 `tests/test_step030_observer_accounts_guard.py`，更新本进度文档；`admin/pages/accounts.html`、`admin/static/js/admin-api.js`和 `backend/routers/admin/accounts.py` 现状已满足，未修改业务代码。
- 实现/验证结果：accounts 的 DOMContentLoaded 守卫在渲染 Header/菜单和调用 `loadAccountList()` 前对任何非 super_admin 跳转 403；observer 菜单动态过滤 accounts。observer 对列表、创建、编辑、重置密码、解锁、删除 6 类 API 均为 403，响应不包账号数据且数据库无变更；super_admin 全生命周期保持正常。
- 验证：首次专项 1 通过 / 2 夹具错误，修正夹具导入后专项 3 通过、相关回归 75 通过。首次全量 876 通过 / 2 失败，根因为模块未暴露 `override_get_db` 导致全局依赖污染；按既有 conftest 约定修正后最终全量 878 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-030-01`，见“契约更新记录”；待 STEP-040 生成 M3 草案并通过部署/人工门禁后才同步正式契约。
- 阻塞项：无；静态 HTML 未被当作数据安全边界，后端 403 仍是最终保护。
- 完成标志：五项全部满足，STEP-030 已更新为 ✅；总完成数 30/40；下一环节为 STEP-031。

### STEP-031（2026-07-16）

- 改动文件：`admin/pages/users.html`、`user-detail.html`、`data-report.html`、`operation-logs.html`、`system-logs.html`，新增 `tests/test_step031_observer_user_reports_logs_pages.py`，更新本进度文档。
- 实现结果：数据报表和系统日志页守卫加入 observer；用户列表的禁用/启用行按钮，用户详情的状态、重置、记忆/私有设定新增/编辑/删除/保存、Key 生成及动态弹窗表单均使用 `data-write-action`；数据报表、操作日志、系统日志 3 个导出按钮已标记。搜索、筛选、分页、Tab、详情、复制、加载更多和 GET 查询均不标记，原四角色行为不变。
- 验证：TDD 红灯 4 预期失败；实现后首跑仅 1 项测试对动态转义 onclick 的编排误判，修正后专项 4 通过、相关 19 通过、全量 882 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-031-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；不阻止普通复制或分页查看，前端只读仍不替代后端写入/导出 403。
- 完成标志：五项全部满足，STEP-031 已更新为 ✅；总完成数 31/40；下一环节为 STEP-032。

### STEP-032（2026-07-16）

- 改动文件：`admin/pages/system-monitor.html`、`third-party.html`、`test-tool.html`，新增 `tests/test_step032_observer_system_third_party_test_dashboard_pages.py`，更新本进度文档；`dashboard.html` 仅验证无需修改。
- 实现结果：系统监控、第三方、AI 测试和看板均可为 observer 加载 GET 数据；第三方配置入口、endpoint/凭据、Redis/外部连接测试与保存动态控件全部标记，observer 卡片仅显示 `credential_configured` 已/未配置。AI 测试参数、开始测试、清空历史、保存用例和动态标准弹窗已标记，历史结果与 Prompt 展开保留。
- 验证：TDD 1 通过 / 3 预期失败；实现后修正 1 项过度约束的页面文案测试，最终专项 4 通过、相关 20 通过、全量 886 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-032-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未显示凭据首尾或掩码片段，未引入浏览器自动化基础设施。
- 完成标志：五项全部满足，STEP-032 已更新为 ✅；总完成数 32/40；下一环节为 STEP-033。

### STEP-033（2026-07-16）

- 改动文件：`admin/pages/persona.html`、`prompt.html`、`step5-5-switch.html`、`safety-rules.html`、`chat-prompt-step15.html`、`chat-prompt-step3.html`、`chat-prompt-step8.html`、`chat-prompt-agent.html`，新增 `tests/test_step033_observer_persona_prompt_safety_pages.py`，更新本进度文档。
- 实现结果：8 页角色守卫加入 observer；人格与 Step5/Step5.5 编辑字段、草稿、测试、发布、回滚、删除，Step5.5 开关，安全关键词增删/保存/导入，以及动态产生的草稿、回滚、标签删除控件均使用统一标记。四个对话流页继续只有 GET、Tab 与展示。
- 验证：TDD 4 项预期失败；实现后专项 4 通过、相关 35 通过、全量 890 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-033-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未修复 VULN-001，未改变 Step5/Step5.5 发布业务逻辑。
- 完成标志：五项全部满足，STEP-033 已更新为 ✅；总完成数 33/40；下一环节为 STEP-034。

### STEP-034（2026-07-16）

- 改动文件：`backend/routers/admin/memory_mgmt.py`、`admin/pages/memory-rules.html`、`vector-token-config.html`、`knowledge.html`，新增 `tests/test_step034_observer_memory_vector_knowledge_pages.py`，更新本进度文档。
- 实现结果：3 页放行 observer；Step6 全部文本块与动态任务字段、DashVector 参数/凭据/测试/保存、全局记忆勾选/批删/行删除、召回/Token 数值与动态输入、知识新增/编辑/删除/弹窗提交全部标记；查询、筛选、分页和 Tab 保留。DashVector API 对 observer 改为布尔 `credential_configured`，不返回 `api_key_masked`。
- 验证：TDD 4 预期失败；实现后专项 4 通过、相关 27 通过、全量 894 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-034-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未把 memory-rules 改为 Embedding 页，未在 vector-token-config 引入凭据。
- 完成标志：五项全部满足，STEP-034 已更新为 ✅；总完成数 34/40；下一环节为 STEP-035。

### STEP-035（2026-07-16）

- 改动文件：`admin/pages/agent-rules.html`、`relationship-rules.html`、`diary-rules.html`、`diary-history.html`，新增 `tests/test_step035_observer_agent_relationship_diary_pages.py`，更新本进度文档。
- 实现结果：4 页角色守卫加入 observer；Agent 两个配置 Tab 和关系等级/成长 Tab 使用统一写标记，动态关键词、消息示例和等级字段在渲染后重应用只读助手；关系影响确认及日记 Prompt、长度、生成时间、保存入口受控。Tab、日记历史筛选、分页和 GET 加载不标记。
- 验证：TDD 1 通过 / 3 预期失败；实现后专项及相关回归 32 通过、全量 898 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-035-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未修改运行时技术债，未改变原四角色权限矩阵。
- 完成标志：五项全部满足，STEP-035 已更新为 ✅；总完成数 35/40；下一环节为 STEP-036。

### STEP-036（2026-07-16）

- 改动文件：`admin/pages/life-plan.html`、`worldview.html`，新增 `tests/test_step036_observer_life_plan_worldview_pages.py`，更新本进度文档。
- 实现结果：两页显式允许 observer 直访；生活计划设置、生成/新增、草稿/发布、两类弹窗和动态大纲/场景行操作，以及世界观新增事件、两类编辑弹窗和动态快照/事件行操作均使用统一标记并保留既有 `isReadonly()` 不渲染防线。日期、查询、分页、Tab、描述展开及 GET 刷新不标记。
- 验证：TDD 1 通过 / 3 预期失败；实现后专项及相关回归 37 通过；全量 902 通过 / 0 失败 / 4 跳过。首次相关命令误引用两个不存在测试文件，修正后真实执行通过。
- 契约条目草稿：`M3-STEP-036-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未改变 ops_admin 只读语义，未修改生活流数据模型。
- 完成标志：五项全部满足，STEP-036 已更新为 ✅；总完成数 36/40；下一环节为 STEP-037。

### STEP-037（2026-07-16）

- 改动文件：`admin/pages/feed-posts.html`、`feed-comments.html`、`agent-aware.html`，新增 `tests/test_step037_observer_feed_and_aware_pages.py`，更新本进度文档。
- 实现结果：三页显式允许 observer 直访；发帖/AI 生成、帖子编辑/显隐、评论编辑/补发/软删、感知重试/删除及超级管理员重置按钮的静态、动态和弹窗控件均使用统一标记，同时保留既有 `isReadonly()` 不渲染写入口。帖子与感知详情、筛选、分页和 GET 刷新不标记。
- 验证：TDD 1 通过 / 3 预期失败；实现后专项及相关回归 47 通过；全量 906 通过 / 0 失败 / 4 跳过。首次相关命令误引用两个不存在测试文件，修正后真实执行通过。
- 契约条目草稿：`M3-STEP-037-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未新增真删除或其他生活流功能，未改变 ops_admin 读取范围。
- 完成标志：五项全部满足，STEP-037 已更新为 ✅；总完成数 37/40；下一环节为 STEP-038。

### STEP-038（2026-07-16）

- 改动文件：`admin/pages/life-feed-global.html`、`life-feed-prompts.html`、`life-feed-system.html`，新增 `tests/test_step038_observer_life_feed_config_pages.py`，更新本进度文档。
- 实现结果：三页显式允许 observer 读取；生活流人格/标签/Header/城市，动态 Prompt/互动参数/图像映射，以及自动发布、发布窗口、历史范围、点赞和 Liblib 参数的文本、数值、选择、开关及静态/动态操作均使用统一标记。Tab、人格页导航、配置展示、状态和 Liblib 统计不标记。
- 验证：TDD 4 项预期失败；实现后专项及相关回归 41 通过；7 个既有发布调用继续显式携带精确 `CONFIRM`；全量 910 通过 / 0 失败 / 4 跳过。
- 契约条目草稿：`M3-STEP-038-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未改变合法角色发布流程，未重构数据库/Redis 发布一致性。
- 完成标志：五项全部满足，STEP-038 已更新为 ✅；总完成数 38/40；下一环节为 STEP-039。

### STEP-039（2026-07-16）

- 改动文件：新增 `tests/test_step039_observer_backend_gate.py`，更新本进度文档；生产代码无需调整。
- 实现/验证结果：聚合门禁固定 159 个 Admin 路由、69 个 GET/HEAD、90 个写方法、四类默认阻断方法、精确两个自助 POST 例外及三个导出依赖，并把匿名 OPTIONS、账号 6 API、第三方/Open API Key 状态和原四角色回归纳入可执行证据集合。observer 与四个原角色组合形成五角色后端矩阵，UI 隐藏不作为边界。
- 验证：专用总门禁 98 通过 / 0 失败；全量 913 通过 / 0 失败 / 4 跳过。首次长命令未保留最终摘要，已用完全相同集合重新执行并取得真实结果。
- 契约条目草稿：`M3-STEP-039-01`；正式契约与 `.cursorrules` 未修改。
- 阻塞项：无；未新增 CI/CD，未以 UI 隐藏替代 API 测试。
- 完成标志：五项全部满足，STEP-039 已更新为 ✅；总完成数 39/40；下一环节为 STEP-040。

### STEP-040（已完成，2026-07-17）

- 改动文件：新增 `tests/test_step040_admin_page_inventory.py`、`docs/progress/STEP-040_35页面五角色验收记录.md`、`docs/contract/drafts/管理后台观察者与安全加固/M3_契约草案.md`；修改 `admin/static/js/admin-api.js`、`tests/test_step029_observer_frontend_common.py` 及 35 个 `admin/pages/*.html` 对各自公共静态资源的版本参数；更新本进度文档。
- 实现/验收结果：精确 35 页、26 个非 GET 页和 25 个业务写页清单门禁通过；五角色逐页浏览器验收 35/35 通过。真实浏览器发现并修复 range 滑块可拖动问题，并通过资源版本参数避免阶段 A 缓存误用。
- 验证：页面组合 39 通过 / 0 失败；range 修复后相关回归 13 通过 / 0 失败且 JS 语法检查通过；收尾最终全量 pytest 918 通过 / 0 失败 / 4 跳过。首次收尾全量回归曾因本机重启后 `tiktoken` 缓存丢失产生 28 个同源环境失败，恢复官方编码缓存后重跑全绿；两次真实结果均已记录。浏览器人工清单及异常边界详见独立验收记录。
- 部署：阶段 B backend 最终镜像已重建，Alembic head 已核对，2026-07-16 17:02 CST 重建容器；五角色登录、observer 读/写/导出/凭据状态及原四角色代表读取烟测通过。
- 契约同步：`M3_契约草案.md` 保留为里程碑快照；已把五角色、observer 后端读写/导出/凭据边界、35 页前端只读契约、验证/部署事实及延期风险同步到 `docs/contract.md`、`.cursorrules`、PRD 和漏洞专档。
- 人工门禁与清理：2026-07-17 项目所有者确认暂无问题、计划可收尾；临时 `codex-step040-observer` 账号已删除（`before_count=1`、`after_count=0`）。
- 阻塞项：无。首次人工验收的旧 HTML 缓存问题已经逐层确认并通过刷新解决；没有放宽后端写权限。
- 完成标志：五项全部满足，STEP-040 已更新为 ✅；总完成数 40/40，本计划完成。
