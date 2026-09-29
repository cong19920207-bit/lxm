# LXM 语音通话 P1 STEP 正式复审报告

> 复审日期：2026-08-30  
> 模式：`step-doc-review / standalone / review-repair / round-4-targeted`  
> 原文：`docs/design/realtime_voice/P1/steps-draft.md`（保持不变）  
> 修正版：`docs/design/realtime_voice/P1/steps-revised.md`  
> 修正版 SHA-256：`58b65e08d3cd1a88dd90085479245a7c35a7040a34bbf471d828d2bb531cc2c3`  
> 验证版：`docs/design/realtime_voice/P1/steps-verified.md`  
> 验证版 SHA-256：`0651ec039872dfa02dc7691656cea125a6bf7fed2870f000a75074e5bcfc1763`  
> 最终结果：`PASS_WITH_RISKS`

## 0. 执行结论

三项来源缺口已按用户确认方案回写权威文档；两轮完整修正后，第三轮完成契约生命周期、直接验收锚点、两项依赖和 UI 证据分层的定向修复，第四轮按用户授权、依据 PRD C99 补齐 STEP-026→019 依赖并复核。当前没有遗留的确定性 STEP 文档缺陷，可以使用 `steps-verified.md` 进入开发。

`PASS_WITH_RISKS` 不是“全部实施条件已完成”：O-01 仍要求真实 Provider/真机完成六项能力取证，O-04 仍要求核查 Open API v1 真实消费者。它们是实施/发布证据门禁，不再是 PRD 或 STEP 文档缺口。

## 1. 复审范围与边界

本轮只复审并修改：

- `需求确认记录-LXM语音通话-v1.md` v1.3；
- `PRD-LXM语音通话仿真交互设计-v2.md` v2.5；
- `DESIGN-LXM语音通话后台配置与管理-v1.md` v1.3；
- `steps-revised.md`、`step-review-diff.md`、`step-audit.md`、执行记录与最终验证版。

未修改代码、current contract、交互规格、其他功能文档或其他历史资料。未读取 `.doc-migration-baseline/`，也未扫描未获授权的 history/归档/草案目录。账号注销仍明确移出 P1：不创建注销 STEP，不验收 AC50，只保留 `TD-V-07`。

## 2. 三项来源契约闭环

| 项目 | 权威结果 | STEP 验证结果 |
|---|---|---|
| missed 解释文案 | 首发/规范回退逐字为「刚刚没接到你的电话，晚一点我们再聊呀。」；无变量；随 script 发布/回滚；读取/解析失败同值回退并告警；空串/占位拒绝 | 005/032/037/038 均有 seed、发布/回滚、故障回退和逐字反例，`PASS` |
| 能力证据事实源 | MySQL `voice_capability_evidence` 只追加；完整 Schema；`UNIQUE(evidence_report_id)` 与 `UNIQUE(evidence_run_id,capability_key)`；整轮事务；PII/Secret/音频/转写拒绝；长期保留；分权读取 | 003/004/006/037/038 均有精确对象投影、唯一键冲突、半轮回滚、发布重查和五角色反例，`PASS` |
| follow-up 多窗口/preview | 四阶段非空多窗口；同阶段不重叠、可相邻；窗口时长大于 jitter；复用 config validate；四错误码；0–20 确定性 jitter；`==24h` 允许、`>24h` 取消；仅 super_admin/tech_ops；零副作用 | 005/006/032/037/038 均有非法输入、时间边界、权限和配置行/Redis/job 完整持久投影反例，`PASS` |

## 3. 九维完整复审

| 维度 | 结果 | 结论 |
|---|---:|---|
| 1. 幻觉检查 | 5/5 | planned/existing/unverified 分离；代码 locator 与真实职责一致；未把 O-01/O-04 写成已完成 |
| 2. 遗漏检查 | 5/5 | 有效 C/ADM、AC、后台/交互 CSTR、CS-V、TD-V、非目标均有处置 |
| 3. 冲突检查 | 5/5 | PRD 管产品语义、DESIGN 管后台细节、STEP 管执行与验收；无重复权威或相互冲突 |
| 4. 清晰度 | 5/5 | owner、输入/输出、停止门、错误码、稳定对象投影和回传均明确 |
| 5. 依赖顺序 | 5/5 | 总览/详情/进度依赖一致，187 条边（183 条无条件、4 条条件），DAG 无环、无自依赖；条件门禁单独表达 |
| 6. 验收可测性 | 5/5 | 每个 STEP 均有本系统层直接可观察锚点；直接 AC/CSTR 落到同对象测试行，迁移/结构前置不伪认领下游业务 AC |
| 7. 决策覆盖率 | 5/5 | §3.1–3.4、详情和 §7.2 的直接映射一致 |
| 8. 技术债完整性 | 5/5 | TD-V-01–07 边界保留；账号注销只在 TD-V-07，不扩散到 P1 |
| 9. 代码事实核查 | 5/5 | scheduler/agent consumer、内容安全副作用、RBAC、配置、timeline、DashVector upsert 与 UI 三层证据 locator 已定向核实 |
| **总分** | **45/45** | 文档质量通过；O-01/O-04 作为实施/发布风险保留 |

## 4. 结构、映射与状态验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 原始草稿完整性 | `PASS` | `steps-draft.md` SHA-256 仍为 `2fa9ec024674fe986818724e82530781c658cbacc589d6ec340ee0cd3bc92c4d` |
| STEP 数量/模板 | `PASS` | STEP-001～038 连续唯一；38 个详情块各含 13 个必需章节 |
| 需求映射 | `PASS` | C/ADM/CS/TD 在 §3.1、§3.3、详情、§7.2 一致；ADM-C31 已同步到 005/032/037 |
| 验收映射 | `PASS` | AC1–49、AC51–80 与 A01–A28、D01–D15、V01–V05、S01–S09、E01–E11、C01–C08 均有直接 owner；AC50 仅延期 |
| 直接测试闭环 | `PASS` | 来源映射中的每个 AC/CSTR 均在同 STEP 测试表直接绑定；无多领或只名义覆盖 |
| 依赖/DAG | `PASS` | 总览、详情、进度依赖集合一致，共 187 条边（183 条无条件、4 条条件）；38/38 拓扑完成，无环/自依赖 |
| 阶段状态 | `PASS` | 38 个总览/详情状态一致；实施进度为 28 `NOT_STARTED` + 10 `BLOCKED` |
| Schema | `PASS` | 12 张新表、5 个 `ON DELETE RESTRICT` FK、零 DB CHECK/native ENUM、全部必需唯一键/索引已冻结 |
| 对象级断言 | `PASS` | 迁移、配置、证据、幂等、turn、任务、导出、保留、删除和 preview 均比较稳定键+完整规范投影 |
| 契约生命周期 | `PASS` | STEP-021/033 同期产出并验证临时契约增量且 current 只读；STEP-038 只提交 `CONTRACT_INTEGRATION_READY`；全部里程碑后再统一整合 current |
| UI 证据分层 | `PASS` | 18 个 hifi 页面仅作视觉参照；现有自动测试限定为 12 状态聚合 Demo 的 8 项共享断言；生产自动化/真机/人工截图由 STEP-036 交付 |
| Markdown | `PASS` | 代码围栏平衡；STEP 标题连续；无重复详情块 |

当前 10 个 `BLOCKED` 实施 STEP 为：006、007、016、017、019、021、030、035、037、038。它们全部能追溯到 O-01、O-04 或两者；不受相应门禁影响的子任务仍按 STEP 中的条件边界推进。

## 5. 关键第二轮修正验证

- STEP-013/020/025/034/036 的 UI/后台直接 CSTR 已收窄到实际可观察对象。
- STEP-017/021/024/029/033/034/036 已补直接验收 ID，不再依赖相邻 STEP 的间接覆盖。
- STEP-006 已补参数越界 UI、A27 preview UI、证据完整稳定投影；STEP-037 已补 missed、危机词异常和能力证据对抗。
- preview 的 job 零副作用断言以 `id/(call_id,content_type)` 为稳定键，比较所有持久字段，包括阶段、配置版本、时区、窗口、内容、取消原因、重试/租约和时间戳。
- STEP-035 已增加同周期/币种真实 Provider 账单 fixture、差异金额/差异率、零分母和公式版本；O-01 未关闭时不得伪 DONE。
- STEP-038 已增加全部 CSTR 逐 ID evidence locator 和三项来源契约的稳定投影复核。

## 6. 第三、四轮定向修复验证

- PRD v2.5、需求确认记录 v1.3 与 STEP 已统一契约写入时点：实现 STEP 只产出并验证增量，STEP-038 提交整合准备，current 由全部里程碑后的统一阶段写入并复核。
- STEP-021 的 O-04 兼容策略、契约增量子任务与整步 DONE 门禁保持不变；STEP-033 已补齐 `POST /api/admin/voice/calls/export` 契约增量产物、验证和完成门禁。
- 直接验收锚点规则已改为“本系统层可直接观察”：31 个 STEP 绑定业务 AC、2 个仅绑定直接 CSTR、5 个使用迁移/结构/基础设施技术验收，未补造下游业务 AC。
- STEP-023 已补 STEP-016 依赖；STEP-025 已补 STEP-034 对 CSTR-UI-C08 E2E/DONE 的条件依赖，三处镜像一致且 DAG 保持无环。
- STEP-019 已依据 PRD C99 补充 STEP-026 无条件前置，正式 VOICE-CTX-PACK owner 已在详情中精确回指 STEP-026；总览、详情、进度与关键依赖图一致，STEP-026 范围与验收未改。
- UI 证据已拆为 `RB-UI-REF-18`、`RB-UI-DEMO-CONTRACT-12` 与 `PLANNED-UI-PROD-REGRESSION`，不再把聚合 Demo 测试描述成 18 页逐页自动覆盖。

## 7. 实际验证

| 验证 | 结果 |
|---|---|
| `python3 tests/test_realtime_voice_demo_contract.py -q` | 12 状态聚合 Demo 的 8 项共享断言通过；不代表 18 个 hifi 页面逐页自动覆盖 |
| 自定义结构检查 | 38 STEP 连续、38×13 模板完整、Markdown 围栏平衡 |
| 自定义 Schema 检查 | 12 张表、5 个 FK、两个能力证据唯一键通过 |
| 独立映射/依赖复核 | 映射一致；187 条边（183 条无条件、4 条条件）；DAG 无环；阶段状态一致 |
| 独立契约生命周期复核 | PRD/确认记录/STEP 三方一致；STEP-021/033 增量闭环；O-04 未削弱；current 未提前写入 |
| 独立 UI 证据复核 | 18 页视觉参照、12 状态/8 断言聚合测试、计划生产回归三层 locator 一致 |
| 独立语义/可测性复核 | 来源验收 ID→测试表零缺项、零多领；结果 `PASS_WITH_RISKS` |
| `tests/test_docs_structure.py` | `NOT_RUN`：该检查会读取 `.doc-migration-baseline/`，不在本任务授权边界内 |

## 8. 剩余风险

| ID | 类型 | 影响 | 关闭条件 |
|---|---|---|---|
| O-01 | `RUNTIME` | 六能力真实证据、相关 STEP DONE、账单/指标真实性与最终 Go | 真实 Provider + 真机逐能力事件证据、六维指纹、未过期 MySQL 证据记录 |
| O-04 | `UNVERIFIED` | Open API 对外契约子任务、STEP-021 DONE 与发布 | 核查真实消费者；如存在，形成兼容说明和版本策略 |

## 9. 最终阶段结果

最终结果：`PASS_WITH_RISKS`。

- `steps-draft.md` 未修改；
- `steps-revised.md` 已完成两轮完整修正、第三轮用户确认范围内的定向修复与第四轮 STEP-026→019 依赖定向修复；
- `steps-verified.md` 已生成，可作为 P1 开发基线；
- GAP-SRC-01..03 已关闭；
- O-01/O-04 必须在对应 STEP/发布门禁处真实关闭，不能因文档通过而视为完成。
