# LXM 语音通话 P1 STEP 首次正式审查

> 审查日期：2026-08-30  
> 模式：`step-doc-review / standalone / review-repair`  
> 被审原文：`docs/design/realtime_voice/P1/steps-draft.md`  
> 原文 SHA-256：`2fa9ec024674fe986818724e82530781c658cbacc589d6ec340ee0cd3bc92c4d`  
> 首次阶段结果：`FAILED_VALIDATION`  
> 修正授权：用户已明确要求修复并重新验证；原文必须保留

## 1. 证据边界

本轮从当前原始来源重新审查，不把历史审计结论当作产品事实。事实优先级为 `USER_DECISION > PRD > CONTRACT > REPO_BASELINE > 项目规范 > 派生 STEP`。

完整审查来源：

- `需求确认记录-LXM语音通话-v1.md` v1.1；
- `PRD-LXM语音通话仿真交互设计-v2.md` v2.3；
- `DESIGN-LXM语音通话后台配置与管理-v1.md` v1.2；
- `LXM语音通话交互规格与PRD映射-v1.md` v1.10；
- `docs/contract/current/` 中被 STEP 直接引用的 current 契约；
- STEP 登记为 `existing` 的仓库路径与符号。

未读取 `.doc-migration-baseline/`，未读取未获授权的 `P1/history/` 文件，未用过期合同或归档材料裁决当前语义。没有 Provider/线上运行证据的事项继续标为 `RUNTIME` 或 `UNVERIFIED`。

## 2. 九维首次评分

评分只表示原草稿质量，5 为通过、0 为不可用；阶段结果由硬门槛决定。

| 维度 | 评分 | 首次结论 | 关键证据 |
|---|---:|---|---|
| 1. 幻觉检查 | 2/5 | 未通过 | 把注释占位的 `agent_message_task.py` 当成现有发送任务；把会拒绝重复 Stable Key 的 `create_entry` 当作 upsert；使用来源中不存在的 `evidence_version` 等字段名 |
| 2. 遗漏检查 | 2/5 | 未通过 | C3 同一路径首通/后续语义、C11 grace 不开新话题、C15 不自动转文字、C26 跨渠道同权重、C37 配额域隔离、账号注销非目标未完整落到直接 STEP |
| 3. 冲突检查 | 2/5 | 未通过 | 多个 AC 被基础设施/UI/相邻链路错误认领；后台和 UI 补充验收编号与原文逐条顺序不一致 |
| 4. 不清晰检查 | 2/5 | 未通过 | STEP-032 没有真实 consumer/claim/retry owner；STEP-004 与 STEP-006 的证据完成职责互相回指；窗口 preview 与能力证据持久化写成可做但没有来源契约 |
| 5. 依赖顺序 | 3/5 | 未通过 | 无显式 DAG 环，但存在 STEP-004↔006 的隐式完成闭环、STEP-032 的隐式调度依赖和若干被错误 AC 掩盖的职责依赖 |
| 6. 验收可测性 | 2/5 | 未通过 | 多处只比较数量、笼统“一致”或页面隐藏；缺少稳定 ID/规范字段投影多重集、缓存边界和精确时间边界 |
| 7. 决策覆盖率 | 2/5 | 未通过 | 名义覆盖不等于语义覆盖；C15/C26 等映射遗漏，AC/CSTR 正反索引与详情/进度不对称 |
| 8. 技术债完整性 | 4/5 | 基本通过 | TD-V 来源总体可追溯；但账号注销必须明确为 P1 非目标/TD-V-07，不能扩成当前版本功能或 AC50 |
| 9. 代码事实核查 | 2/5 | 未通过 | 实际 follow-up 消费入口是 scheduler/agent service；内容安全现有入口有共享指标副作用；Stable Key 真正底层 upsert 在 `DashVectorClient.upsert` |
| **总分** | **21/45** | **FAILED_VALIDATION** | 存在可由来源唯一修复的结构/映射/验收问题，同时存在三项来源级阻断 |

## 3. 首次发现清单

| ID | 严重度 | 问题 | 证据 | 处理分类 |
|---|---|---|---|---|
| F-01 | 高 | 直接验收过映射/错映射，AC 与 CSTR 的正向、反向、详情、进度不对称 | PRD AC1–AC80；后台 §16；UI §10 | 可确定修正 |
| F-02 | 高 | C3、C11、C15、C26、C37 等关键语义没有落到能直接观察该对象的 STEP | PRD C3/C11/C15/C26/C37 | 可确定修正 |
| F-03 | 高 | 仓库 locator/既有行为错误：占位 agent task、`create_entry` upsert、内容安全共享副作用 | `backend/tasks/scheduler.py`、`backend/services/agent_service.py`、`backend/services/user_vector_memory_service.py`、`backend/utils/dashvector_client.py`、`backend/services/content_safety_service.py` | 可确定修正 |
| F-04 | 高 | STEP-004/006 证据职责形成隐式完成闭环；STEP-032 缺 scheduler/consumer/claim/retry/idempotency 闭环；3 秒防误触 owner 不清 | PRD C13/C112；仓库 scheduler/agent service/`try_consume_resend_quota` | 可确定修正 |
| F-05 | 高 | 对象一致性验收不足，数量或笼统一致可能漏掉对象替换、重复和字段漂移 | `step-doc-review` 维度 6；PRD 对幂等、快照、保留、导出的对象要求 | 可确定修正 |
| F-06 | 中 | 把 API 403 推导成前端隐藏；缺少 DOM/CacheStorage/local/sessionStorage/IndexedDB 的敏感缓存边界 | PRD/后台权限矩阵；UI 危机验收 | 可确定修正 |
| F-07 | 中 | 字段/状态字面量漂移：`evidence_version`、句级证据名、导出到期字段等与权威 Schema 不一致 | PRD/后台 Schema；当前修订源字段 | 可确定修正 |
| F-08 | 中 | 账号注销边界容易被单通删除 STEP 扩散；本期不应实现 AC50 | 用户决定；PRD 非目标；后台 D15；TD-V-07 | 可确定修正 |
| B-01 | 阻断 | `missed_explanation_template` 只有字段和消费方式，没有首发逐字默认值 | PRD §12.5；后台 §6.11 | `USER_DECISION_REQUIRED` |
| B-02 | 阻断 | “独立能力证据记录”要求投影、`evidence_report_id` 和只追加，但没有生产介质、Schema、ID/不可变/导入事务 owner | 后台 §4.2、能力 evidence payload、§8.2 | `DESIGN_REQUIRED` |
| B-03 | 阻断 | PRD 要求窗口范围/重叠校验和测试预览，但后台设计没有预览输入/输出、重叠定义和 owner | PRD §12.5；后台通用 validate API | `DESIGN_REQUIRED` |

## 4. 逐 STEP 首次问题

| STEP | 严重度 | 首次审查结果 |
|---|---|---|
| 001 | 中 | 迁移前置错误认领 AC58/CSTR 业务验收；应只证明存量对象投影不变 |
| 002 | 中 | 迁移前置错误认领成长业务 AC；应以主键+既有字段投影验证无损 |
| 003 | 阻断 | 11 张已知表可枚举，但独立能力证据记录没有生产 Schema；同时错误认领多项业务 AC（B-02/F-01） |
| 004 | 高 | 证据报告和运行状态更新职责混合，形成与 006 的隐式完成闭环；错误认领能力消费 AC |
| 005 | 阻断 | 把未给出的 missed 首发模板当作“完整默认脚本”；窗口 preview 没有契约；配置/Redis/历史只写笼统一致（B-01/B-03/F-05） |
| 006 | 阻断 | 证据导入/不可变记录和窗口 preview 均缺来源；存在从 403 推导 UI、字段名漂移和精确投影不足（B-02/B-03/F-06/F-07） |
| 007 | 高 | 认领有效文本/打断/召回 AC，超出 Adapter 可直接观察对象；真实测试 locator 不完整 |
| 008 | 中 | AC35 不属于配额账本直接验收；C37 需要明确时长与点数/支付域隔离 |
| 009 | 高 | 3 秒关系阶段追加消息防误触没有唯一 owner；AC1/AC73 错映射，时间边界不精确 |
| 010 | 中 | 应消费而非重新定义防误触原子规则；无能力 percentage 的负向边界需与 C122 幂等分离 |
| 011 | 高 | 缺 C3 首通/后续同一 CALL-01 路径且无固定分支的直接反例 |
| 012 | 低 | 核心 WSS/ticket 职责可保留；需要与幂等对象和部署断言保持直接边界 |
| 013 | 高 | C15“不自动转文字”错误落到预检页；S09 编号和阻断对象零新增断言需修正 |
| 014 | 高 | 错误认领 AC12/AC15 等下游 turn/effective 验收；重复终态应作为内部合同而非扩张 AC |
| 015 | 中 | 直接 AC 范围过宽；应收敛到 turn/final flush 可观察对象 |
| 016 | 高 | 挂断 final flush 的有效文本投影与 `confirmed_sentences` 边界不完整 |
| 017 | 中 | 打断后 exact-played 投影需要按字符/句边界断言，不能只断言“未播不保存” |
| 018 | 高 | C11 的 grace 只允许收尾且不得新开话题没有直接反例；AC33 归属过宽 |
| 019 | 中 | 未取证重连逐字衔接语、同 call 和不重播开场的直接验收编号不完整 |
| 020 | 高 | C15 服务故障不自动转文字应由本 STEP 以文字对象多重集零变化直接验收 |
| 021 | 高 | 卡片必须先插静态 pending 再 UPDATE，同一 call/sort_seq 的对象级断言不足 |
| 022 | 高 | 跨模态止损需证明既有成长/情绪对象稳定键和值集合零变化 |
| 023 | 高 | 直接复用 `check_content` 会递增文字共享指标；需要无共享副作用的 seam，保持文字默认行为 |
| 024 | 高 | 错误认领 AC68 用户 UI；危机只应直接认领隔离/审计/故障后端对象 |
| 025 | 高 | 危机前端缓存、到期/删除后离线恢复反证不足；不能从后端 403 推导页面隐藏 |
| 026 | 高 | 漏掉 C26：会前记忆选择不得因 voice/text 渠道加权或降权 |
| 027 | 中 | 缓冲是 AC28–31 前置，不应直接认领召回业务 AC |
| 028 | 高 | `create_entry` 不是 full upsert；Stable Key 应落到真正 upsert helper，并验证 C26 同权重 |
| 029 | 高 | 错误认领 AC22/AC27；重试/补偿/围栏需要 turn/job/trace 稳定键多重集 |
| 030 | 高 | 漏掉 C26 在召回重排阶段的渠道同权重反例 |
| 031 | 高 | reasoning 用户面零字段、旧情绪三域零变化和精确字段名未形成完整直接断言 |
| 032 | 阻断 | 只有任务表描述，没有真实 scheduler/consumer/claim/lease/retry/崩溃恢复；同时受 B-01/B-03 阻断，且错误认领 AC59 |
| 033 | 高 | 导出/正文权限需比较固定快照下的字段投影多重集；reasoning/危机不能靠前端隐藏；到期字段名漂移 |
| 034 | 高 | AC47 不属于清理直接验收；到期和删除要按 `(table,primary_key)` 比较；账号注销必须保持延期 |
| 035 | 高 | 只能直接验收看板 AC80；必须消费稳定 metric key，不能重新实现 producer |
| 036 | 高 | 视觉回归不得认领服务端业务 AC；只直接映射逐项 UI CSTR |
| 037 | 高 | 安全/故障演练需要稳定对象投影、缓存恢复反证和 CS-V 全约束；原映射缺失/过宽 |
| 038 | 阻断 | 证据包缺逐项 locator/对象投影 manifest；三项来源门禁未出现，不能给 Go 或生成验证版 |

## 5. 覆盖、技术债与排除项结论

- 原稿虽名义覆盖有效 C/ADM/AC，但 C15、C26 等语义和多项直接 owner 不正确，不能计为语义覆盖通过。
- 后台验收应逐条编号为 A01–A28、D01–D15；UI 应逐条编号为 V01–V05、S01–S09、E01–E11、C01–C08，不能用错位压缩编号掩盖遗漏。
- AC50 不进入本期验收；账号注销仅作为 `TD-V-07`/非目标记录，不新增注销 STEP。
- 其他 TD-V 与 CS-V 均可追溯到 PRD；未发现应新增的无来源技术债。

## 6. 首次结论

原始 `steps-draft.md` 结构外形完整，但存在来源可唯一确定的映射、依赖、代码事实和可测性错误，因此首次阶段结果是 `FAILED_VALIDATION`。根据用户授权，下一步只修上述确定性问题并保留原稿；B-01～B-03 不得用“推荐值”或工程惯例代填，最终复审仍可能为 `BLOCKED`。
