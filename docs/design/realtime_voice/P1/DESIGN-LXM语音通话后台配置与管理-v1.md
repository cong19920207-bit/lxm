---
title: "LXM语音通话后台配置与管理设计"
version: "v1.3"
status: "方案已确认（Phase A 待开发）"
updated: "2026-08-30"
parent_prd: "PRD-LXM语音通话仿真交互设计-v2.md"
requirement_confirmation: "需求确认记录-LXM语音通话-v1.md"
authority_scope: "语音通话后台页面、配置 Schema、发布流程、权限、审计与管理 API"
deployment_assumption: "单实例部署（CS-V-03）"
---

# LXM语音通话后台配置与管理设计

## 1. 文档定位

本文是《[LXM语音通话-仿真人交互、实时转写与独立记忆链路设计 PRD](PRD-LXM语音通话仿真交互设计-v2.md)》的后台专项设计，覆盖语音通话配置中心、S2S Provider 管理、能力矩阵、通话记录、逐轮转写、权限和审计。

本文不替代父 PRD 的通话业务规则。两份文档的权威边界如下：

| 内容 | 权威来源 |
|---|---|
| 通话行为、状态机、记忆语义、计费、删除边界、产品验收 | 父 PRD |
| 后台页面、配置字段、API、校验、发布、回滚、权限映射 | 本文 |
| 跨域冲突 | 先满足父 PRD 的产品与数据语义，再修正本文实现 |

父 PRD 保留后台产品能力概要和不可迁移的数据语义；本文承接详细字段与后台实现，不在两处维护两份相互独立的默认值。

### 1.1 部署前提与运行时约束（v1.1 新增）

以下三条是本文全部设计的前提，实现时不得默认具备更强的能力。

| 编号 | 前提 | 影响 |
|---|---|---|
| CS-V-03 | **单实例部署**。与文字链路现状一致：`chat_service._generation_futures` 为进程内字典，`asyncio.Future` 无法跨实例共享 | 通话租约、全局并发计数器、进行中通话遍历（硬停）均按单实例设计。本期不具备水平扩展能力，多实例部署会直接产生双通与并发计数漂移 |
| CS-V-01 | S2S 凭据**只走环境变量**，改凭据需改 env 并重启 | 后台不提供凭据编辑入口，只展示环境变量名与已/未配置状态 |
| — | 语音配置必须**第一天接入运行时** | 「后台可保存可发布但运行时不读取」是仓库已有的四类同型技术债（TD-004 / TD-005 / TD-007 / TD-012）的共同成因。Phase A 的验收包含运行时确实读取到新值 |

本文 v1.1 的全部修改来自《[需求确认记录-LXM语音通话-v1](需求确认记录-LXM语音通话-v1.md)》，覆盖父 PRD v2.2 的 C94–C104、C114–C116 等相关决策；v1.2 再对齐父 PRD v2.3 的最终收口口径，v1.3 对齐需求确认记录 v1.2 与父 PRD v2.4，冻结能力证据记录、missed 默认文案和窗口预览契约。全局当前仅 O-01（能力取证）与 O-04（Open API 真实消费者）未关闭；O-03 已由父 PRD C122 收口，创建通话 API 在对应业务 STEP 承接。

v1.2 在此基础上关闭 O-02 / O-05 / O-06，并定稿正文读取、`reasoning`、危机原文与 P1 账号注销边界。

---

## 2. 已确认决策

| 编号 | 主题 | 决策 |
|---|---|---|
| ADM-C1 | 文档拆分 | 父 PRD 保留后台概要、权限边界、删除语义和端到端验收；本文承接详细设计 |
| ADM-C2 | 首批范围 | 先建设 S2S Provider、模型、音色、连接测试、能力配置、发布和快照底座 |
| ADM-C3 | 凭据 | S2S 密钥保存在部署 Secret/环境配置；后台配置只保存 `credential_ref` 与凭据版本引用 |
| ADM-C4 | 配置聚合 | **已被 ADM-C12 修正**：早期单一 `voice_call_config` 方案不再作为开发口径；跨渠道共享人格按已发布版本引用、不复制正文的边界仍有效 |
| ADM-C5 | 编辑发布 | 分区保存草稿；两个语音 `config_key` 分别做整 key 验证、测试、发布和回滚 |
| ADM-C6 | 通话冻结 | 新通话同时读取两个语音 key 的已发布版本并锁定解析快照；进行中通话继续使用创建时快照 |
| ADM-C7 | 未验证能力 | 未验证能力允许配置，但默认关闭；强制启用只能进入审计 `test`，必须显著标记、确认、审计并保存到快照 |
| ADM-C8 | 未验证范围 | **已被 ADM-C21 修正**：只允许审计 `test`，不再存在能力位 `gray`；验证通过后才允许 `all` |
| ADM-C9 | P0 边界 | P0 分支只作为事件、参数和 Provider 能力取证来源，不直接视为生产后台实现 |
| ADM-C10 | 固定记忆 ID | 不迁移 P0 的 `preamble_memory_doc_ids`，正式链路自动选择高价值记忆 |
| ADM-C11 | 测试字段 | `mock_s2s`、弱网档位等只保留在测试工具，不进入生产配置与通话快照 |

### 2.1 v1.1 新增决策（ADM-C12 ~ ADM-C24）

| 编号 | 主题 | 决策 | 父 PRD |
|---|---|---|---|
| ADM-C12 | 配置拆分 | ADM-C4 的单一配置拆为 `voice_call_config`（阈值/配额/能力位/总开关与用户白名单，`tech_ops` 写）与 `voice_call_script`（模板与话术，`ai_trainer` 写） | C100 |
| ADM-C13 | 版本锚定 | `base_version` 复用生效行的 `version`；`draft_revision` 为 `admin_config` **新增可空列**（草稿行 `version` 恒为 0 且原地覆盖，无法承担此职责） | C94 |
| ADM-C14 | 草稿保存 | 走语音专用保存方法并带乐观锁；**不复用**既有 `save_draft`（无条件 last-write-wins） | C94 |
| ADM-C15 | 人格引用 | `persona_ref` 存 `version` + 人格正文 `sha256`；因 `_MAX_HISTORY_VERSIONS = 20`，纯指针在人格发布超 20 次后会静默断链 | C95 |
| ADM-C16 | 发布卡点一 | 改为**参数取值范围校验**，不套用 `run_standard_tests`；卡点二 CONFIRM 与卡点三 5 分钟监控窗口保留 | C97 |
| ADM-C17 | 运行时接入 | 语音配置第一天接入运行时；缺配置或解析失败回退代码默认值并记指标 | C96 |
| ADM-C18 | 快照锁定 | 配置在**通话开始时快照锁定**，通话期间不重读 | AC11 / V7-6 |
| ADM-C19 | 凭据 | 只走环境变量；`credential_ref` = 环境变量名 + 已/未配置状态；不支持后台热切 | C102 |
| ADM-C20 | 灰度 | 总开关 + 用户白名单，**移除百分比 rollout** | C114 |
| ADM-C21 | 能力位灰度 | **移除 `capability_gray` 的按用户维度**；能力位是全局客观事实，`effective_scope` 不含按用户分桶 | C116 |
| ADM-C22 | 能力位默认值 | 六项默认全 `false`（`enabled=false` + `verification_status=unverified`） | C98 |
| ADM-C23 | 紧急停用 | 软停（只拦新拨打）与硬停（断开全部进行中通话）两级，权限 `tech_ops`，均写操作日志 | C115 |
| ADM-C24 | 权限口径 | 不引入权限点框架，按仓库惯例在语音 router 内定义角色元组；通话文本对 `ai_trainer` 不可见；导出显式挂 `deny_observer_export` | C101 / C103 / C104 |

### 2.2 v1.2 新增决策（ADM-C25 ~ ADM-C29）

| 编号 | 主题 | 决策 | 父 PRD |
|---|---|---|---|
| ADM-C25 | 证据失效 | 能力证据使用不可变 `evidence_fingerprint`；指纹不一致立即 `stale`，时间有效期默认 30 天，可在 `voice_call_config` 发布为 7–90 天 | C98 / AC57 |
| ADM-C26 | 追加消息时段 | O-05 是 `voice_call_config` 的可发布/可回滚配置；四档初始窗口、`Asia/Shanghai`、左闭右开、0–20 分钟抖动、24 小时最大延迟均随任务快照锁定；初始发布值与读取失败回退值共用一份规范默认常量，禁止在业务分支散落硬编码 | C59 / C96 |
| ADM-C27 | 危机 UI 与数据 | P1 默认中国大陆资源（12356、110 / 120）；通话中使用非红色低干扰提示条，挂断后使用独立系统卡；危机原文保留 30 天，任务日志保留 90 天 | C29 / C121 |
| ADM-C28 | 正文与 `reasoning` | `observer` 可在后台逐条查看未到期有效正文，导出必须 403；`ai_trainer` 正文页与接口均 403；`reasoning` 仅 `super_admin` 用于后台调优，保留 30 天，不进用户端、timeline 或导出 | C29 / C35 / C101 / C104 |
| ADM-C29 | 账号注销 | 账号注销不在 P1 范围；以 P1 本地技术债 `TD-V-07` 记录未来接入项目级注销流程，不新增用户入口、语音专项 API 或 orchestrator | AC50 延期 / TD-V-07 |

### 2.3 v1.3 新增决策（ADM-C30 ~ ADM-C32）

| 编号 | 主题 | 决策 | 父 PRD |
|---|---|---|---|
| ADM-C30 | 能力证据 owner | 生产能力证据独立持久化到 MySQL `voice_capability_evidence`；每轮每能力位一条，以 `evidence_report_id` 稳定 UUID 唯一、`evidence_run_id` 分组；记录只追加、不更新、不做业务删除，配置只保存只读投影/引用 | C98 / AC57 |
| ADM-C31 | missed 默认文案 | `voice_call_script.followup.missed_explanation_template` 首发逐字值为「刚刚没接到你的电话，晚一点我们再聊呀。」，无变量；随 script 发布/回滚，读取失败回退同一规范默认值并告警 | C112 |
| ADM-C32 | 窗口校验/预览 | 每阶段使用非空多窗口数组；同阶段不重叠、可相邻，不同阶段可重叠，窗口不跨日且时长大于 jitter 上限。复用 `POST /api/admin/voice/config/config/validate` 做无副作用预览；窗内不加 jitter，窗外顺延后加 jitter，恰好 24h 允许、超过取消 | C59 / AC40 |

---

## 3. 功能范围与阶段

独立后台文档覆盖完整目标，但开发按阶段交付：

| 阶段 | 范围 | 当前状态 |
|---|---|---|
| Phase A | S2S Provider、模型、音色、凭据引用、连接测试、能力矩阵、草稿/发布/回滚、配置快照 | 首批开发范围 |
| Phase B | CALL-01、会前小包、动态召回、逐轮记忆、打断、静音与退出 | 后续 |
| Phase C | 时长、成长值、并发、追加消息、保留策略 | 后续 |
| Phase D | 通话记录、逐轮转写、任务状态、导出、补跑、删除 | 后续 |

阶段只控制开发顺序，不改变最终配置 Schema 的统一版本与快照语义。尚未开发的分区在后台不展示可编辑入口，不能用空值覆盖已发布默认值。

### 3.1 本文不包含

- H5 通话页面视觉和音频采集实现；
- Provider Adapter 实时代码；
- 通话、转写和任务表的具体 ORM/Alembic 实现；
- 原始音频保存；
- 用户侧记忆查看、纠正或删除；
- 账号注销入口与全域清理 orchestrator；P1 只以本地技术债 `TD-V-07` 说明未来独立接入；
- P0 Mock、弱网实验页面；
- S2S 密钥明文展示、导出或写入配置历史。

---

## 4. 当前后台基础与复用边界

### 4.1 可复用

- `admin_config` 的生效、草稿、历史版本数据范式；
- `AdminConfigService` 的读取、发布、Redis 热配置、历史和回滚能力；
- 人格页的草稿、测试、发布、历史和回滚交互；
- 第三方页的连接测试和凭据状态化展示思路；
- `admin-common.css`、`admin-api.js`、公共确认弹窗、操作日志；
- 现有管理员 JWT、角色判断和 observer 写总闸。

### 4.2 不能直接复用

- 当前“豆包”第三方配置测试的是文本 Chat Completions，不是 S2S WebSocket；
- 当前文字向量召回配置属于文字业务链路，不能直接成为 VOICE-RECALL-01 配置；
- 当前 Step6 Prompt 不能直接作为 VOICE-MEM-01 Prompt；
- 通用 `run_standard_tests` 面向文字人格测试，不满足 S2S 握手和能力测试；
- `AdminConfigService.save_draft` 是无条件 last-write-wins，两个管理员同时编辑后保存者静默覆盖且无冲突提示，语音必须另写带乐观锁的保存方法（ADM-C14）；
- 草稿行的 `version` 恒为 0 且后续保存原地覆盖，不能当作 `draft_revision` 使用（ADM-C13）；
- `try_acquire_bundle_lock` 是无 owner token 的裸 NX 锁、释放时不校验持有者，不适用于最长持有 1 小时的通话租约（第 6.10 节）；
- `admin_config.third_party:doubao` 里存 Endpoint 与 API Key 并同步 Redis，而运行时实际读环境变量（TD-012），该做法不作为语音凭据范式；
- P0 的内存 Session、环境变量读取和测试页参数不能直接作为生产配置中心。

### 4.3 需要增加的语音专项服务

建议新增语音专项配置服务，复用底层 `admin_config`，但独立负责：

- 强类型 Schema；
- 分区 PATCH；
- `base_version` / `draft_revision` 并发保护；
- 跨分区联动校验；
- S2S 连接测试；
- Provider 能力测试结果；
- 未验证能力仅审计 `test` 的限制；
- 整包发布和快照生成；
- 凭据引用解析，但不返回密钥。

---

## 5. 后台信息架构

侧栏新增一级分组“☎️ 语音通话”：

| 页面 | 主要内容 | 阶段 |
|---|---|---|
| 语音设置 | 配置分区、草稿差异、测试、发布、历史、回滚 | Phase A 起 |
| 通话记录 | 通话列表、逐轮转写、任务、快照、导出、删除 | Phase D |

### 5.1 语音设置页面

建议使用现有后台卡片、Tab、表单、状态条和弹窗规范：

1. Provider 与模型；
2. 音色；
3. Provider 能力；
4. CALL-01；
5. 人设与会前小包；
6. 动态召回；
7. 逐轮记忆；
8. 打断与静音；
9. 时长、成长与并发；
10. 摘要、追加消息与保留；
11. 发布记录。

页面顶部固定显示：

```text
当前生效：V12
草稿基于：V12
草稿修订：R7
状态：有 3 项未发布变更
最后发布：2026-08-25 18:30 / admin
```

底部固定操作区：

- 保存当前分区；
- 丢弃当前分区修改；
- 查看整包差异；
- 验证配置；
- 测试连接/能力；
- 发布；
- 丢弃全部草稿。

“保存当前分区”不改变运行时；只有整包发布产生新生效版本。

### 5.2 通话记录页面

列表、详情、导出、补跑和删除遵循父 PRD 第 17、19、20 节的产品与数据边界。本文第 12 节定义具体后台结构。

---

## 6. 聚合配置模型

### 6.1 存储约定

语音专项配置按性质拆为**两个 `config_key`**（ADM-C12），避免话术编辑与阈值调整互相覆盖草稿；另在既有内容安全规则域新增独立的 `crisis_keywords`，它不并入语音整包发布：

| `config_key` | 承载分区 | 写权限 |
|---|---|---|
| `voice_call_config` | `global` / `s2s` / `voice` / `capabilities` / `quota` / `growth` / `concurrency` / `followup.schedule` / `retention` | `super_admin` / `tech_ops` |
| `voice_call_script` | `context_pack` 模板、`call_answer` Prompt、`recall` Prompt、`memory` Prompt、`barge_in` 词表、`silence_and_exit` 话术、`followup` 模板（含 `missed_explanation_template`）、`end_reason` 结束文案、重连衔接话术、危机提示条/资源卡文案 | `super_admin` / `ai_trainer` |
| `crisis_keywords` | 仅自伤/自杀倾向关键词的**非空**数组（规范化后 `minItems: 1`）；沿用内容安全规则的独立发布、历史/回滚与 Redis 缓存范式 | `super_admin` / `ai_trainer` |

两个语音 `config_key` 共用下列约定：

| 项目 | 约定 |
|---|---|
| `config_value` | 各自一份完整的非敏感运行配置 JSON |
| 生效版本 | `admin_config.is_active=true, is_draft=false` |
| 草稿 | 同 key 唯一草稿行 |
| Redis | `active_config:voice_call_config` / `active_config:voice_call_script` |
| 历史 | 沿用配置中心版本历史，通话自身另存完整快照 |
| 密钥 | 不进入 `config_value`、Redis、历史、审计 before/after 或通话快照 |
| 快照 | 通话开始时同时锁定两个 key 的生效版本，通话期间不重读（ADM-C18） |

`crisis_keywords` 单独沿用内容安全规则的 `admin_config` 发布与 `active_config:crisis_keywords` 缓存，不参与上述两个语音 key 的草稿合并、整包校验或通话快照。生产发布和回滚都必须在去空白、去重后满足 `minItems: 1`；空数组不能作为“关闭检测”的手段。运行时读取缺失、非法、空数组或异常时，统一按“疑似命中”处理并告警。

`base_version`、`draft_revision` 等编辑元数据属于 API/存储元数据，不属于运行配置正文。`base_version` 复用生效行的 `version`（由 `publish_config` 递增）；`draft_revision` 是 `admin_config` 新增的可空列（ADM-C13）。后台读取时的响应结构为：

```json
{
  "_meta": {
    "config_key": "voice_call_config",
    "base_version": 12,
    "draft_revision": 7
  },
  "config": {
    "schema_version": 1,
    "global": {},
    "s2s": {},
    "voice": {},
    "capabilities": {},
    "quota": {},
    "growth": {},
    "concurrency": {},
    "followup": {},
    "retention": {}
  }
}
```

当 `config_key=voice_call_script` 时，响应保持相同外层结构，但 `config` 只包含脚本自身的 `schema_version`、`context_pack`、`call_answer`、`recall`、`memory`、`barge_in`、`silence_and_exit`、`followup`、`end_reason`、`reconnect_bridge` 与危机文案分区。两个 key 不共享一份混合 Schema、版本号或草稿 revision。

2026-09-09 用户确认的 M2 兼容补充：`voice_call_config.concurrency` 保留必填 `global_limit`，增加下列可选参数（单位毫秒）。继续使用现有分区编辑、权限、草稿、校验及发布流程，不新增绕过发布的写入口。

| 参数 | 测试阶段默认 | 范围 |
|---|---:|---|
| heartbeat_interval_ms | 5000 | 1000～10000 |
| user_lock_ttl_ms | 15000 | 10000～60000，且至少为有效心跳间隔的 3 倍 |
| reconnect_timeout_ms | 15000 | 1000～60000 |
| call_ticket_ttl_ms | 30000 | 5000～60000 |

旧配置缺省时使用上述确定值；校验不补写原对象，快照在核验原发布内容/hash 后解析默认值。配置历史、原 hash、active 行和 Redis 不因升级被改写；只为新通话保存实际解析参数，进行中的通话不热切。这些值不是生产压测结论。Origin、TLS 和受管代理继续由部署配置管理。

以下内容不放入该聚合 JSON：

- Secret 明文；
- 凭据健康检查的执行记录；
- Provider 能力测试的原始证据与报告；
- 管理操作审计；
- 每通电话的配置快照。

能力测试状态、证据编号以及 Provider Profile、模型、协议 Profile、Adapter、SDK、取证用例集版本这六维由服务端从独立证据记录投影到草稿，并在发布时固化到配置版本；它们是只读字段，不允许管理员手工改成“已验证”。执行测试本身不会直接改变运行态。

现有跨渠道共享人格仍由 `admin_config:persona` 管理。`voice_call_config` 只引用一个明确的已发布人格版本，并同时保存该版本正文的 `sha256`（ADM-C15）；发布和创建通话时解析该版本并固化到快照，不复制一份可独立编辑的人格正文。这样既保留一个语音发布单元，也避免文字和语音出现两份无人知道谁是权威的人格配置。

存 `sha256` 的原因：`AdminConfigService._MAX_HISTORY_VERSIONS = 20`，超出即物理删除最早历史版本。纯版本号指针在人格发布超 20 次后会静默断链，而 `sha256` 体积恒定，且在版本行被清理后仍能判定「与当前生效版本是否相同」。

### 6.2 全局、灰度与紧急停用

| 字段 | 类型 | 说明 | 初始口径 |
|---|---|---|---|
| `global.enabled` | bool | 语音通话总开关 | 默认关闭，正式联调后开启 |
| `global.maintenance_mode` | bool | 维护门禁 | 默认关闭 |
| `global.maintenance_message` | string | 维护时用户提示 | 使用统一可用性文案，不暴露技术细节 |
| `global.rollout.mode` | enum | `off` / `allowlist` / `all` | Phase A 默认 `allowlist` |
| `global.rollout.user_ids` | int[] | 白名单用户 | 按内测规模配置 |
| `global.test_user_ids` | int[] | 内部测试用户 | 仅测试环境/测试入口使用 |
| `global.soft_stop` | bool | 软停：只拦新拨打，进行中通话自然结束 | 默认关闭 |

**移除的两组字段**（ADM-C20 / ADM-C21）：

| 已移除 | 原因 |
|---|---|
| `global.rollout.percentage` 与 `percentage` 模式 | 仓库无任何 feature flag / rollout 基建（唯一按用户门禁是 `User.is_banned` + Redis `user_banned:{user_id}`）。50 人规模下百分比无统计意义（10% = 5 人）；灰度的真实价值是「出问题时只影响 3 个人而不是 50 个」，白名单已足够 |
| `global.capability_gray.*`（按用户维度） | 能力位描述的是**上游是否支持某项行为**，是客观事实而非策略。按用户灰度等于允许「对 A 用户上游支持句级映射、对 B 用户不支持」，逻辑上不成立，且会导致同版本同时跑两套交互逻辑、故障无法复现 |

#### 紧急停用两级（ADM-C23）

| 级别 | 行为 | 触发方式 |
|---|---|---|
| 软停 | 只拦新拨打，进行中通话自然结束 | `global.soft_stop = true`，走正常发布或专用开关接口 |
| 硬停 | 断开全部进行中通话（`end_reason=system_error`） | 专用运维接口，不走配置发布 |

两者权限均归 `tech_ops`（含 `super_admin`），均必须写操作日志。

硬停的实现成本很小——遍历进行中通话逐个结束，第 6.10 节的并发对账机制本就需要这个能力。但它是必需的：语音依赖外部付费服务，异常计费场景下「最坏等 1 小时排空」不可接受。

### 6.3 S2S Provider 与模型

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `s2s.provider` | enum/string | Provider 标识 | PRD |
| `s2s.endpoint` | URL | S2S WebSocket Endpoint | P0 迁移 |
| `s2s.resource_id` | string | Provider 资源标识 | P0 迁移 |
| `s2s.model_version` | string | 实时语音模型版本 | PRD/P0 |
| `s2s.adapter_version` | string | LXM Adapter 版本 | 新增 |
| `s2s.protocol_profile` | string | Adapter 维护的协议 Profile | 新增 |
| `s2s.credential_ref` | string | 环境变量名（不含值） | 已确认 |
| `s2s.credential_revision_ref` | string/null | 可选的 Secret 版本/轮换引用 | 已确认；不可包含凭据值 |
| `s2s.connect_timeout_ms` | int | 建连超时 | 待技术定值 |
| `s2s.start_session_timeout_ms` | int | StartSession 超时 | 待技术定值 |
| `s2s.max_retries` | int | 建连重试次数 | 待技术定值 |
| `s2s.retry_backoff_ms` | int[] | 退避序列 | 待技术定值 |

`app_id`、`access_key`、`app_key` 等认证字段不属于该对象，由 `credential_ref` 指向的 Secret 提供。若部署系统支持 Secret 版本，使用不透明的 `credential_revision_ref` 固定或追踪轮换版本；纯环境变量模式由服务端在连接测试和通话快照中记录部署提供的非敏感 revision，后台不得自行计算或展示密钥哈希。
`s2s.endpoint` 不得包含 Token、签名或其他认证查询参数；发现疑似凭据时拒绝保存。

`protocol_profile` 收敛 Provider 特有的输入模式、审计开关、上/下行编码、采样率、声道和位深等协议参数。后台只能选择 Adapter 已声明并通过基础连接测试的 Profile，不开放任意 JSON 透传；Profile 变化会使相关能力证据转为 `stale`。

### 6.4 音色

| 字段 | 类型 | 约束 | 初始口径 |
|---|---|---|---|
| `voice.voice_id` | string | 必填 | P0 默认 speaker 作为种子 |
| `voice.voice_version` | string | 必填 | 新增 |
| `voice.candidates` | object[] | voice_id 唯一、可启停 | P0 `voice_candidates` 迁移 |
| `voice.persona_mapping` | object | persona → voice profile | PRD |
| `voice.speech_rate` | int | -50～100 | 默认 0 |
| `voice.loudness_rate` | int | -50～100 | 默认 0 |
| `voice.expressive` | bool | Provider 支持时可用 | 默认 false |
| `voice.tone_instruction` | string | 长度受人格预算约束 | P0 `tone_hint` 生产化 |

音频格式、采样率、声道、bit depth 属于 Adapter 协议配置，默认不向运营后台开放；需要变更时走 Provider Profile 与能力验证。

### 6.5 CALL-01

| 字段 | 初始口径 |
|---|---|
| Prompt / Prompt 版本 | 独立维护 |
| 模型 / 模型版本 | 可与 S2S 不同 |
| 超时、重试 | 待技术定值 |
| 最短响铃 | 4 秒，已确认 |
| 最大等待 | 12 秒，已确认 |
| 兜底延迟 | 4–8 秒，已确认 |
| 失败兜底 | 默认接听，但不绕过额度、锁、容量和 Provider 门禁 |
| 告警、熔断阈值 | 待技术定值 |

### 6.6 会前小包

| 字段 | 初始口径 |
|---|---|
| `persona_ref.config_key` | 固定为现有 `persona` |
| `persona_ref.version` | 必须引用明确的已发布版本，不允许引用草稿或漂移的 `latest` |
| `persona_ref.content_sha256` | 该版本人格正文的 `sha256`，与 `version` 同时保存（ADM-C15） |
| `voice_call_script.context_pack.voice_instruction_template` | 语音通话专用角色/表达/电话行为约束，随 `voice_call_script` 版本化 |
| `persona_max_chars` | 5000，已确认 |
| `dynamic_max_chars` | 2000，已确认 |
| `recent_dialog_max_chars` | 800，已确认 |
| `memory_max_items` | 5，已确认 |
| `memory_lookback_days` | 30，已确认 |
| `build_budget_ms` | 3000，已确认 |
| `fallback_template` | 最小包：人格、关系、称呼、当前时间 |
| `ready_barrier_enabled` | true |
| `source_priority` | 按父 PRD 第 7.2 节 |

禁止提供固定 DashVector 文档 ID 编辑器。

S2S 实际 system prompt/character manifest 由“已发布人格版本 + 语音专用指令模板 + 本通动态上下文”编译生成，不提供绕开该链路的任意 Provider Prompt 覆盖字段。共享人格发布后不会自动改变语音运行态；管理员需在语音草稿中切换 `persona_ref.version` 并整包发布，新通话才采用新版本。

### 6.7 动态召回

| 字段 | 初始口径 |
|---|---|
| Prompt / 模型 / pipeline_version | 语音独立维护 |
| 触发词、实体和纠正规则 | P0 词表作为种子，需真实样本校准 |
| `max_query_chars` | P0 种子 200，待验证 |
| `top_k` | P0 种子 3，待验证 |
| `score_threshold` | P0 种子 0.7，待验证 |
| `timeout_ms` | P0 种子 1000，待验证 |
| `embedding_timeout_ms` | P0 种子 800，待验证 |
| `vector_timeout_ms` | P0 种子 800，待验证 |
| `cache_ttl_seconds` | 待技术定值 |
| `max_result_items` | 1–3，父 PRD确认 |
| `max_result_chars` | 待技术定值 |
| `injection_mode` | `current_turn/next_turn/auto` |
| `late_result_mode` | 下一回合，不追加第二段回复 |

文字链路的 `vector_retrieval_config` 不直接覆盖本分区。

### 6.8 逐轮记忆

| 字段 | 初始口径 |
|---|---|
| Prompt / 模型 / pipeline_version | VOICE-MEM-01 独立维护 |
| `min_text_chars` | 待技术定值 |
| `asr_confidence_threshold` | 待 Provider 证据 |
| `max_items_per_turn` | 5，已确认 |
| 跳过附和词和敏感规则 | 按父 PRD 第 11、19 节 |
| `memory.max_retries` | 2026-09-13确认默认2，范围0～5，不含首次执行 |
| `memory.retry_backoff_ms` | 默认[1000,5000]毫秒；与次数等长、非递减，每项100～60000；定时任务领取到期记忆任务 |

旧配置缺少上述两字段时，在新通话运行快照中补兼容默认，不改写旧配置或hash。记忆重试复用持久化首次抽取结果，任务状态/审计不返回该快照正文；修改配置发布后仅影响新通话。

### 6.9 打断、静音与退出

| 字段 | 初始口径 |
|---|---|
| VAD 阈值 | M3 测试默认 RMS 0.015，可配 0.001～0.2，仍待真机校准 |
| 候选持续时间 | 180–250ms 范围，M3 测试默认 200ms，仍待真机校准 |
| 弱附和词、强打断词、升级连接词 | 使用父 PRD 默认词表 |
| 升级规则 | 有效表达、连接词或强词命中；组合纯附和不因持续时间单独升级为打断 |
| truncate 开关 | 由能力配置约束 |
| 静音确认 | 6 秒，已确认 |
| 静音挂断 | 12 秒，已确认 |
| 告别播放硬超时 | M3 测试默认 10000ms，可配 1000～30000ms |
| 告别播放后缓冲 | interaction.post_playback_buffer_ms，默认800ms，可配0～3000ms；实际播放完成后计时，受服务端调度影响 |
| 用户续说取消 | 默认启用，播放后缓冲期间仍有效 |

2026-09-12 用户确认：技术角色通过 `voice_call_config.interaction` 管理上述参数；持续表达升级 `sustained_ms` 默认 600ms（250～2000 且大于候选窗口），软收尾 `time_low_seconds` 默认剩余 60 秒（1～300 秒）。缺少该分区的旧配置保持有效；先校验原发布 hash，再仅向新通话快照补默认。草稿不自动发布，已开始通话保留原快照，版本可回滚。

### 6.10 时长、成长值与并发

| 分组 | 字段与初始口径 |
|---|---|
| 时长 | 每日免费 300 秒；免费池与额外池均归零时进入每通一次、最多 30 秒的免费 grace；硬顶 3600 秒；不预扣 |
| 成长值 | 每 30 秒 5 点、每日上限 100 点，`Asia/Shanghai` 自然日 |
| 并发 | 全局并发、用户锁 TTL、租约续租间隔、心跳间隔/超时、重连窗口、连接重试，数值待压测 |

#### 时区必须统一

时长配额重置与成长值日上限**必须都用 `Asia/Shanghai`**，否则出现「额度已重置但成长值没重置」的错位。仓库现存三套时区口径（`Asia/Shanghai`、服务器本地日 + UTC 午夜 TTL、UTC 日），语音只用第一套，且不改动既有文字行为。

#### 通话租约（不复用既有裸锁范式）

| 项 | 规则 |
|---|---|
| 锁值 | 存 `call_id` 而非 `"1"`，释放前校验持有者（owner token） |
| TTL | 设较短值，在通话心跳中续租 |
| 续租失败 | **立即结束通话**（`end_reason=system_error`），不放任锁自然过期 |
| 全局并发 | Redis 计数器 + 定期扫描「进行中但超过硬顶时长」的 `voice_call` 行做归零对账 |
| grace 期 | 30 秒 grace 期间仍计入并发容量 |

既有 `try_acquire_bundle_lock` 释放时直接 `delete` 不校验持有者。对 bundle 场景可接受（TTL 90 秒、同用户天然串行），但语音锁最长持有 1 小时，误删与续租风险被放大。锁自然过期意味着系统认为通话已结束而音频流仍在走，此时用户可从另一设备拨入形成双通。

**连接池提示**：语音占用 Redis 与数据库连接的时长远超既有任何链路（1 小时 vs 数十秒），Phase A 压测需一并评估连接池容量。

### 6.11 摘要、追加消息与保留

2026-09-13用户确认：CALL-SUM使用现有env DeepSeek（DEEPSEEK_API_KEY/DEEPSEEK_BASE_URL），`voice_call_config.summary.model`默认复用当前DeepSeek规范模型；`voice_call_script.summary.prompt_template`支持后台多行编辑，默认词覆盖本通卡片与追加候选规则。两个summary分区为旧配置兼容可选字段；新通话冻结解析后的模型和Prompt，旧配置正文/hash不改。新规范种子包含两字段；不得把密钥或地址写入model。服务使用DeepSeek现有超时/传输策略，不额外引入摘要任务自动重试策略，failed可按权限人工补跑。

| 分组 | 字段与初始口径 |
|---|---|
| 摘要 | CALL-SUM-01 Prompt/模型；有效时长至少 15 秒且存在有意义闭环回合 |
| 追加消息 | 四档关系阶段窗口、`Asia/Shanghai`、左闭右开、0–20 分钟抖动、24 小时最大延迟、取消规则；均来自已发布 `voice_call_config` |
| 保留 | 有效转写 180 天、完整生成调试文本 30 天、`reasoning` 30 天、危机原文 30 天、任务日志 90 天 |

O-05 已定稿为 `followup.schedule` 的**初始已发布配置**：

| 关系阶段 | 配置 key | 允许窗口（`Asia/Shanghai`） |
|---|---|---|
| 陌生 | `stranger` | `[10:00, 21:00)` |
| 朋友 | `friend` | `[09:30, 22:00)` |
| 亲密 | `intimate` | `[09:00, 22:30)` |
| 知己 | `soulmate` | `[09:00, 23:00)` |

规范 Schema 为每个关系阶段一个非空 `windows` 数组：

```json
{
  "timezone": "Asia/Shanghai",
  "jitter_min_minutes": 0,
  "jitter_max_minutes": 20,
  "max_delay_hours": 24,
  "stages": {
    "stranger": {"windows": [{"start": "10:00", "end": "21:00"}]},
    "friend": {"windows": [{"start": "09:30", "end": "22:00"}]},
    "intimate": {"windows": [{"start": "09:00", "end": "22:30"}]},
    "soulmate": {"windows": [{"start": "09:00", "end": "23:00"}]}
  }
}
```

窗口时间只接受 `HH:mm` 分钟精度，统一为左闭右开，必须 `start < end` 且不允许跨日。同一关系阶段的窗口不得重叠，但 `[09:00,10:00)` 与 `[10:00,11:00)` 这类首尾相邻合法；不同关系阶段的窗口可以重叠。每个窗口时长必须严格大于 `jitter_max_minutes`，避免顺延后的抖动越出当前允许窗口。

候选时间已在窗口内时直接标记 `in_window=true`，并以候选时间为 `resolved_due_at`，不加抖动。窗外候选时间顺延到下一个窗口起点后，再叠加 0–20 分钟抖动。从未调整的候选发送时间起计，最终发送时间恰好延迟 24 小时合法；超过 24 小时则取消任务，不跨日无限顺延。

这些默认值只允许维护为一份规范默认常量：首次部署用它生成 `voice_call_config` 的初始生效版本，运行时缺配置或解析失败时也用同一份默认值回退并告警；不得在调度业务分支复制同值。后台可走标准发布和回滚。`voice_followup_job` 创建时必须保存 `schedule_config_version`、`relationship_stage_snapshot`、时区、窗口、抖动值、候选时间和最晚发送时间；若使用回退值，版本明确记为 `code-default`。已入队任务按快照执行，新发布/回滚只影响之后创建的任务。

`missed` 终态不调用 CALL-SUM LLM，直接使用已发布 `voice_call_script.followup.missed_explanation_template` 生成确定性解释消息，任务 `content_type=missed_explanation`；该模板随 script 独立发布/回滚，发送窗口仍使用上述 `voice_call_config` 快照。首发逐字值必须为「刚刚没接到你的电话，晚一点我们再聊呀。」，不带任何变量。运行时缺少 script、该字段缺失或解析失败时，必须回退到生成首个 script 生效版本的同一份规范默认常量并告警，不得发送空串、占位文案或在业务分支复制文案。

`voice_call_script.end_reason` 与重连衔接语的初始发布值必须逐字为：

| 场景 / `end_reason` | 初始默认行为或文案 |
|---|---|
| `user_hangup` | 就先聊到这 |
| `user_cancel` | 无结束页，直接返回聊天 |
| `exit_intent` | 好，那我们先聊到这 |
| `silence_timeout` | 好像暂时听不到你，我们下次再聊 |
| `quota_exhausted` | 今天能聊的时间用完啦，我们下次再聊 |
| `hard_limit` | 这次聊得有点久，我们先休息一下 |
| `reconnect_timeout` | 网络没有恢复，我们下次再接着聊 |
| `provider_error` / `system_error`（接通前） | 暂时无法接通 |
| `provider_error` / `system_error`（接通后） | 通话暂时中断，请稍后再试 |
| 重连成功衔接 | 刚刚好像断了一下。你刚才说到哪儿了？ |

以上均可由后台发布覆盖；`user_cancel` 的“无结束页”是行为规则，不得被配置成额外页面。前端不得自行拼接未确认副文案。

### 6.12 内容安全与危机关键词（v1.1 新增）

| 配置项 | 归属 | 说明 |
|---|---|---|
| `banned_keywords` | 既有 `config_key`，**不改** | 语音复用其读取范式与词表，但计数走独立 Redis 键，不递增 `content_block_count:{date}` |
| `crisis_keywords` | **新建独立 `config_key`** + Redis `active_config:crisis_keywords` | 仅自伤/自杀倾向词表；扩展既有内容安全规则页与接口，沿用 `banned_keywords` 的 `super_admin` / `ai_trainer` 写、`observer` 只读、发布/缓存/历史/回滚范式，不并入两个语音配置 key 的整包发布 |
| 危机提示条/资源卡 | `voice_call_script` | O-06 已定稿；P1 默认中国大陆资源，文案和资源号码随配置发布/回滚 |

两条实现约束：

1. 语音内容安全是**出口止损**（检测 + 记录，Phase 1 不干预播放），与文字链路的入口拦截是不同语义，后台指标必须分开呈现；
2. 危机检测**不 fail-open**：Redis 故障或检测异常时按「疑似命中」处理并告警。这与常规内容安全的 fail-open 策略相反，实现时不能共用同一段兜底逻辑。

O-06 的初始发布内容如下，精确交互规格以《LXM语音通话交互规格与PRD映射-v1》第 5.9 节为准：

- 通话中提示条：“如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。”
- 挂断后系统卡正文：“如果你可能马上伤害自己，请立即拨打 110/120，并请一位可信任的人来到你身边；也可以拨打 12356 心理援助热线。”
- P1 不另行定义系统卡标题或拨号按钮，避免在已确认文案之外扩展交互。
- 初始地区为 `CN-mainland`，不通过定位或用户文本推断地区；P1 未配置其他地区号码。
- 产品级视觉约束仅冻结为**低干扰、非红色、非弹窗**；挂断后为无 AI 头像、无角色口吻的独立系统卡。具体色值、边框与图标由交互实现阶段在该约束内确定，不作为新增产品决策。

### 6.13 运行时接入与降级（v1.1 新增）

| 项 | 要求 |
|---|---|
| 读取时机 | 创建通话时读取两个语音 `config_key` 的生效版本并写入快照，通话期间不重读；`crisis_keywords` 由安全检测 loader 独立读取其生效缓存 |
| 读取失败 | 回退代码默认值，记指标，**不阻断通话** |
| 缺字段 | 只有 Schema 明确声明向后兼容的新增可选字段可按字段级默认值补齐；必填字段缺失按解析失败处理 |
| Schema 版本 | 仅对 Schema 明确声明向后兼容的新增可选字段做字段级默认补齐；未知或不兼容 `schema_version` 视为解析失败，整 key 回退规范代码默认值并告警，不猜测“最近兼容版本” |
| 验收 | 「管理员调整并发上限或日配额并发布 → 下一通通话立即按新值执行」是 Phase A 的显式验收项（父 PRD AC76） |

显式发布的 `global.enabled=false` 或软停状态优先于代码默认值，必须阻断新拨打；“读取失败不阻断通话”只适用于配置源不可用/内容非法时的技术回退，不得用来绕过已经成功读取的停用配置。

这一节存在的唯一原因是仓库已有四条同型技术债（TD-004 Agent 规则、TD-005 关系规则、TD-007、TD-012 第三方配置）：后台配置页已交付、可保存可发布，但运行时不读取。语音配置里的并发上限与时长配额直接决定成本，若不接入运行时，运营调低配额控成本时不会生效，问题要到账单出来才发现。

`followup.schedule` 同样遵循上表“读取失败”规则：缺失或解析失败时使用生成初始发布配置的同一份规范默认值，并记指标和告警；不得在业务分支另写一套窗口兜底。

---

## 7. Provider 能力矩阵

### 7.1 六项核心能力

| Key | 能力 |
|---|---|
| `supports_current_turn_rag_gate` | 当前回复开始前完成 RAG 注入并避免双回复 |
| `supports_reply_cancel` | 取消已经开始或待开始的默认回复 |
| `supports_context_truncate` | 打断后截断未播放内容的 Provider 上下文 |
| `supports_playback_text_mapping` | 音频播放位置精确映射到文字 |
| `supports_sentence_playback_ack` | 客户端确认完整句已播放 |
| `supports_session_reconnect` | 同一通电话恢复 Provider Session |

### 7.2 单项结构

**六项默认值全部为「未验证 + 关闭」**（ADM-C22）。2026-08-26 核对结论：六项中**零项有完整证据**，一项（`supports_current_turn_rag_gate`）有部分采集基础，因此 Phase A 交付时六项都必须落在下面这个初始态：

```json
{
  "verification_status": "unverified",
  "enabled": false,
  "forced_enabled": false,
  "effective_scope": "off",
  "fallback_mode": "next_turn",
  "provider_profile": null,
  "model_version": null,
  "protocol_profile": null,
  "adapter_version": null,
  "sdk_version": null,
  "evidence_suite_version": null,
  "evidence_fingerprint": null,
  "evidence_ttl_days": 30,
  "verified_at": null,
  "expires_at": null,
  "evidence_report_id": null,
  "last_test_result": "not_run"
}
```

强制启用后的示例结构：

```json
{
  "verification_status": "unverified",
  "enabled": true,
  "forced_enabled": true,
  "effective_scope": "test",
  "fallback_mode": "next_turn",
  "provider_profile": "doubao_prod_profile@sha256:...",
  "model_version": "2.2.0.0",
  "protocol_profile": "doubao_dialog_v3_pcm",
  "adapter_version": "voice_adapter_v1",
  "sdk_version": "doubao_sdk_x.y.z",
  "evidence_suite_version": "voice_capability_suite_v1",
  "evidence_fingerprint": null,
  "evidence_ttl_days": 30,
  "verified_at": null,
  "expires_at": null,
  "evidence_report_id": null,
  "last_test_result": "not_run"
}
```

`verification_status` 取值：

- `verified`：指定证据指纹已通过证据门槛，且尚未超过 `expires_at`；
- `unverified`：尚未完成验证；
- `failed`：已验证但未通过；
- `stale`：当前证据指纹与已验证指纹不一致，或已超过 `expires_at`，旧证据失效。

`effective_scope` 取值收敛为 **`off` / `test` / `all`**，**不含按用户分桶的 `gray`**（ADM-C21）。`test` 指仅对 `global.test_user_ids` 的测试入口生效，用途是取证而非分批放量。

O-02 已定稿。每份通过门槛的证据报告固化不可变指纹：

```text
evidence_fingerprint = sha256(canonical_json({
  provider_profile,
  model_version,
  protocol_profile,
  adapter_version,
  sdk_version,
  evidence_suite_version
}))
```

六维严格定义为 Provider Profile、模型、协议 Profile、Adapter、SDK、取证用例集版本；`provider_profile` 是包含 Provider 身份与 Profile 内容哈希的稳定标识，因此指纹中不再重复加入 `provider` 第七维。`evidence_suite_version` 是取证用例集/门槛的版本，防止测试口径改了但仍复用旧结论。当前运行配置的指纹与报告指纹不一致时立即转为 `stale`。`evidence_ttl_days` 属于 `voice_call_config.capabilities`，默认 30 天，可发布范围为 7–90 天；`expires_at = verified_at + evidence_ttl_days`，到期后即使指纹未变也转为 `stale`。指纹变化解决显式升级，时间失效解决无法感知的上游静默升级；两条任一命中都不得继续 `all`。证据报告原记录不覆盖，只追加新一轮取证。

#### 7.2.1 独立证据记录 `voice_capability_evidence`（ADM-C30）

`voice_capability_evidence` 是生产能力证据的唯一持久化事实源。Phase0 报告文件是导入输入/审计附件，不能代替该记录；`voice_call_config.capabilities` 只保存服务端从该表生成的只读投影和 `evidence_report_id` 引用。

| 字段 | 类型/约束 | 语义 |
|---|---|---|
| `id` | BIGINT 主键 | 内部主键，不对外作报告编号 |
| `evidence_report_id` | UUID/string，UNIQUE，非空 | 每个能力位证据的稳定唯一编号 |
| `evidence_run_id` | UUID/string，索引，非空 | 同一次测试运行的分组编号；一轮每个被测能力位各一条 |
| `capability_key` | string，非空 | 仅允许第 7.1 节六个应用层枚举值 |
| `verification_result` | string，非空 | `passed` / `failed` / `error` |
| `source_type` | string，非空 | `phase0_import` / `admin_capability_test` |
| `provider_profile` / `model_version` / `protocol_profile` / `adapter_version` / `sdk_version` / `evidence_suite_version` | string，非空 | 六维指纹输入 |
| `evidence_fingerprint` | string，索引，非空 | 按本节 canonical JSON 规则计算的不可变指纹 |
| `evidence_payload` | JSON，非空 | 已脱敏的事件/门槛/结果证据；不存原始音频、用户转写、密钥、上游敏感原文及明文、可逆或可反推个人信息 |
| `report_sha256` | string，非空 | 脱敏且 canonical 化后的报告内容哈希 |
| `tested_at` | datetime，非空 | 实际测试时间 |
| `verified_at` | datetime，可空 | 达到通过门槛的确认时间；非 `passed` 为空 |
| `evidence_ttl_days_snapshot` | int，非空 | 生成记录时的 7–90 天有效期快照 |
| `expires_at` | datetime，可空 | `passed` 记录的 `verified_at + evidence_ttl_days_snapshot` |
| `operator_id` | BIGINT，可空 | 后台测试操作人；Phase0 导入可空，不设置阻断删除的强外键 |
| `created_at` | datetime，非空 | 追加时间 |

数据库只承担主键、唯一键与索引，不使用 native ENUM 或 DB CHECK；六能力位、结果和来源枚举由应用层强校验。至少建立 `UNIQUE(evidence_report_id)`、`UNIQUE(evidence_run_id,capability_key)`、`INDEX(evidence_run_id)`、`INDEX(capability_key,created_at)` 和 `INDEX(evidence_fingerprint,verification_result,expires_at)`；复合唯一键直接保证同一轮同一能力位只能追加一条，即使重放使用了不同 `evidence_report_id` 也不能形成重复证据。

追加事务顺序固定为：

1. 校验能力位、六维、测试门槛和结果；
2. 对证据 payload 执行 allowlist 投影与脱敏，拒绝明文、可逆或可反推个人信息，再计算 canonical `report_sha256` 和 `evidence_fingerprint`；
3. 在同一 MySQL 事务内，按每个能力位追加记录，并把只读投影/引用写入当前 `voice_call_config` 草稿；`evidence_report_id` 或 `(evidence_run_id,capability_key)` 任一唯一键冲突均视为本轮失败；
4. 任一记录、唯一键、allowlist/脱敏（含个人信息拒绝）或草稿投影失败时整轮回滚，既有草稿与生效版本均不变。

发布时不信任草稿内的投影，必须以 `evidence_report_id` 重查原记录存在、`capability_key` 匹配、`verification_result=passed`、六维指纹与当前配置一致且未过期；任一不满足时禁止发布到 `all`。表不提供 UPDATE 或业务 DELETE 路由，不跟随配置历史裁剪，按长期审计证据保留。

完整 `evidence_payload` 仅 `super_admin` / `tech_ops` 可读；`ai_trainer` / `ops_admin` / `observer` 与其他配置读取者只能取得不含 payload/operator 的非敏感投影。普通日志、操作日志 before/after 与配置历史均不记录完整 payload。

### 7.3 强制启用规则

1. `verified` 能力可配置 `off/test/all`；
2. `unverified/stale` 能力可以配置并强制启用，但只允许 `test`；
3. `failed` 表示已经取得“不满足门槛”的证据，不允许强制启用，只能关闭并使用降级模式；
4. 强制启用要求：
   - 仅 `super_admin` 可执行；
   - 输入 `CONFIRM`；
   - 填写原因；
   - 对应的 `global.test_user_ids` 非空；
   - 配置快照记录状态和操作来源；
   - 普通操作日志不记录转写正文或密钥；
5. 运行失败必须进入该能力的 `fallback_mode`；
6. 未验证能力不得因 Provider 名称或事件编号自动升级为已验证；
7. 验证通过后可发布全量；指纹不一致或证据到期后自动转为 `stale`。

### 7.4 UI 展示

Phase A 交付时的真实初始态（六项全未验证、全关闭）：

```text
当前回合 RAG       未验证   已关闭   下一回合降级
回复取消           未验证   已关闭   不追加第二段回复
上下文截断         未验证   已关闭   截断失败按空有效文本
精确文本映射       未验证   已关闭   完整句确认
完整句播放确认     未验证   已关闭   无确认则空文本
同通断线重连       未验证   已关闭   新 Session + 补注入会前小包
```

取证与强制启用后的展示形态示例：

```text
当前回合 RAG       未验证   测试强制启用   下一回合降级
上下文截断         已验证   已启用         截断失败按空有效文本
精确文本映射       验证失败 已关闭         完整句确认
同通断线重连       已过期   已关闭         新 Session + 补注入会前小包
```

页面必须同时呈现「六项中已取证几项」的汇总，使能力矩阵本身在提醒还有多少能力未验证。

---

## 8. 凭据与安全边界

### 8.1 承载方式：只走环境变量（ADM-C19）

本期凭据**只有一种存法：环境变量**。

| 内容 | 位置 |
|---|---|
| S2S `app_id` / `access_key` / `app_key`、Provider Secret 与 Token | `.env`，由 `config.py` 读取 |
| `credential_ref` | 配置 JSON 中保存**环境变量名**（如 `DOUBAO_S2S_ACCESS_KEY`），不含值 |
| 已/未配置状态 | 服务端运行时探测，只返回布尔与最后一次连接测试结果 |

**已知约束 CS-V-01：改凭据需改 env 并重启，不支持后台热切。** 这是本期设计选择而非缺陷。

选择 env 的理由：既有 `admin_config.third_party:doubao` 里存着 Endpoint 与 API Key 并同步到 Redis，而运行时实际读的是环境变量与 `config.py`（TD-012）。语音要用的是同一厂商的同一套凭据，若再引入第三种存法，运维会搞不清「豆包 key 到底改哪里」。走 env 同时满足「密钥零落地」与 observer 脱敏两个要求。

### 8.2 聚合配置中保存

- `credential_ref`（环境变量名）；
- 可选的 `credential_revision_ref`（部署系统提供的不透明版本标识，纯 env 模式下可为空）；
- 不含密钥的 Provider、Endpoint、资源、模型和 Adapter 信息。

后台页面还可展示“是否已配置、最后一次连接测试时间与结果”等只读状态，但这些来自独立健康检查记录，不写入配置 JSON，也不会因为一次测试自动产生运行配置变更。

凭据响应按角色投影：只有 `super_admin` / `tech_ops` 可读取非敏感环境变量名与配置状态；`ai_trainer` / `ops_admin` / `observer` **只返回已/未配置状态**，不返回 `credential_ref`、revision、原文、首尾、掩码、哈希或任何可推断元数据（如长度、字符集、创建时间）。

### 8.3 禁止

- 将密钥写入 `admin_config.config_value`；
- 将密钥写入 Redis、通话快照、历史版本或导出文件；
- 在 API 响应、普通日志、操作日志 before/after 中返回明文或可逆内容；
- 允许浏览器直接使用 S2S 长期凭据；
- 将凭据值作为 `credential_ref`。

连接测试由服务端解析 `credential_ref`，响应只返回状态、延迟、失败类别和测试版本，不返回上游原始敏感响应。

---

## 9. 草稿、验证、测试、发布与回滚

### 9.1 分区保存

客户端只提交当前分区：

```json
{
  "base_version": 12,
  "draft_revision": 7,
  "section": "voice",
  "content": {
    "voice_id": "voice_x",
    "voice_version": "v3",
    "speech_rate": 10,
    "loudness_rate": 0,
    "expressive": false
  }
}
```

服务端必须：

1. 锁定同一 `config_key` 草稿；
2. 校验 `base_version` 与当前生效版本；
3. 校验 `draft_revision`；
4. 只替换目标分区；
5. 执行该分区和跨分区校验；
6. `draft_revision + 1`；
7. 返回整包差异摘要。

**实现约束（ADM-C13 / ADM-C14）**

| 项 | 规则 |
|---|---|
| 保存入口 | 语音专用保存方法，**不复用** `AdminConfigService.save_draft`（后者是无条件 last-write-wins，两人同时编辑后保存者静默覆盖且无冲突提示） |
| `base_version` 来源 | 生效行的 `version`，由 `publish_config` 递增（`new_version = current_version + 1`），可直接作乐观锁基准 |
| `draft_revision` 来源 | `admin_config` **新增可空列**。草稿行的 `version` 恒为 0 且后续保存原地覆盖，不能承担此职责 |
| 冲突返回 | 专用错误码 + 差异展示，不静默覆盖 |
| 并发缓解 | 配置拆两个 `config_key`（ADM-C12）后，话术编辑与阈值调整由不同角色在不同 key 上进行，天然减少同 key 并发 |
| 发布 / 回滚 | 直接复用既有 `publish_config` / `rollback_config`；回滚语义是「把旧内容作为新版本重新发布」，版本号单调递增不复用，适用于语音 |

### 9.2 冲突

- 生效版本变化且草稿仍基于旧版本：拒绝继续保存，提示重建草稿；
- 草稿已被他人更新：返回冲突，不做最后写入覆盖；
- 不自动把旧草稿静默合并到新 Provider/模型版本；
- 重新加载后可按分区人工选择保留或放弃修改。

### 9.3 发布前门禁

语音发布沿用仓库既有的三道卡点，但**卡点一的内容改为参数取值范围校验**（ADM-C16）：

| 卡点 | 语音口径 |
|---|---|
| 卡点一 | **参数取值范围校验**（如连接超时 5–30 秒、并发上限 ≥1、日配额 ≥0、静音阈值 6 < 12、字符预算 > 0、follow-up 窗口范围/同阶段不重叠/时长大于 jitter 上限）。**不套用** `run_standard_tests`——它面向文字人格测试，与 S2S 握手/能力测试无关 |
| 卡点二 | 确认弹窗需手动输入 `CONFIRM`，后端精确校验 `confirm_text == "CONFIRM"` |
| 卡点三 | 发布后 5 分钟监控窗口 |

完整门禁顺序：

1. Schema 与**参数取值范围**校验；
2. 跨字段校验（如静音确认必须小于静音挂断；每个关系阶段 `windows` 非空，区间 `start < end`、不跨日、同阶段不重叠且每个时长大于 `jitter_max_minutes`）；
3. `credential_ref` 指向的环境变量存在性检查；
4. S2S 连接测试；
5. 已启用能力的状态与 `effective_scope` 检查；对任一将进入 `all` 的能力，以 `evidence_report_id` 重查追加记录存在、能力位一致、结果通过、六维指纹相等且未过期；
6. 未验证强制启用的权限、原因和 `CONFIRM`；
7. 展示完整差异；
8. 发布说明必填。

连接测试成功不代表六项能力已验证。能力验证必须单独记录证据。

### 9.4 发布

- 发布整份非敏感配置；
- 被发布的 `config_key` 各自生成单调递增的新版本；`voice_call_config` 与 `voice_call_script` 不共用单一版本号；
- 删除草稿；
- 更新 Redis；
- 写入脱敏操作日志；
- 新通话使用新版本；
- 已建立通话不热切换；
- 发布失败不得留下数据库与 Redis 对外不一致的生效版本。

最后一项需要语音专项发布服务明确处理事务后缓存更新失败的补偿；不能只依赖当前通用流程的最佳努力。

### 9.5 回滚

- 回滚以目标历史版本的完整配置内容发布一个新版本；
- 不修改进行中通话快照；
- 回滚前重新校验 Secret 引用是否仍存在；
- 若目标版本包含 `unverified/stale` 能力，仍只能进入审计 `test`；若能力已经 `failed`，必须关闭后才能回滚发布；
- 回滚操作要求 `CONFIRM` 并审计。

---

## 10. 配置快照

创建 `voice_call` 时保存解析后的完整非敏感快照：

```json
{
  "config_version": 13,
  "script_version": 8,
  "config_schema_version": 1,
  "script_schema_version": 1,
  "config_content_sha256": "sha256:...",
  "script_content_sha256": "sha256:...",
  "config_published_at": "2026-08-25T18:30:00+08:00",
  "script_published_at": "2026-08-25T18:20:00+08:00",
  "credential_ref": "DOUBAO_S2S_ACCESS_KEY",
  "credential_revision_ref": null,
  "provider_profile": "doubao_prod_profile@sha256:...",
  "model_version": "2.2.0.0",
  "adapter_version": "voice_adapter_v1",
  "protocol_profile": "doubao_dialog_v3_pcm",
  "sdk_version": "doubao_sdk_x.y.z",
  "evidence_suite_version": "voice_capability_suite_v1",
  "persona_ref": {"config_key": "persona", "version": 8, "content_sha256": "sha256:..."},
  "capability_snapshot": {},
  "resolved_config": {},
  "resolved_script": {}
}
```

要求：

- 不保存任何密钥；
- 保存本通采用的验证状态、强制启用、降级模式、`evidence_fingerprint` 和 `expires_at`；
- 保存 Prompt/词表/时序/保留期等实际内容或稳定版本及可审计解析结果；
- 管理员修改配置不改变旧快照；
- 通话详情按角色投影快照：`super_admin` / `tech_ops` 可看非敏感环境变量名与配置状态；`ai_trainer` / `ops_admin` / `observer` 只返回“已配置/未配置”，不返回 `credential_ref`、revision 或其他可推断元数据；
- 配置历史被清理后，通话快照仍能还原本通行为。

---

## 11. 后台权限

**实现方式（ADM-C24）**：不引入权限点框架。按仓库既有惯例在语音 router 模块内定义角色元组（`_READ_ROLES` / `_WRITE_ROLES`），逐端点挂 `require_role(*roles)`。下表的权限点名称仅作能力语义标识，不落地为独立权限模型。

| 能力 | 语义标识 | 实际角色 |
|---|---|---|
| 查看两个 key 的非敏感配置、版本和差异 | `voice_config.read` | `super_admin` / `ai_trainer` / `tech_ops` / `ops_admin` / `observer` |
| 保存/丢弃 `voice_call_config` 草稿、发布、回滚 | `voice_config.edit/publish/rollback` | `super_admin` / `tech_ops` |
| 保存/丢弃 `voice_call_script` 草稿、发布、回滚 | `voice_config.edit/publish/rollback` | `super_admin` / `ai_trainer` |
| 执行连接与能力测试 | `voice_config.test` | `super_admin` / `tech_ops` |
| 查看能力证据 | — | `super_admin` / `tech_ops` 可读已脱敏完整证据；其他拥有 `voice_config.read` 的角色只读非敏感投影 |
| 强制启用未验证或已过期能力 | `voice_capability.force_enable` | 仅 `super_admin` |
| 软停 / 硬停 / 强制挂断进行中通话 | — | `super_admin` / `tech_ops` |
| 查看通话逐轮有效转写 | `voice_transcript.read` | `super_admin` / `ops_admin` / `observer`；**`ai_trainer` 不可见** |
| 导出有效转写 | `voice_transcript.export` | `super_admin` / `ops_admin`；必须显式挂 `deny_observer_export` |
| 查看受限调试文本（AI 完整生成文本 / `reasoning`） | `voice_debug_generated.read` | 仅 `super_admin` |
| 删除通话并设置删除围栏 | `voice_call.delete` | 仅 `super_admin` |
| 补跑允许重试的失败任务 | `voice_job.retry` | `super_admin` / `tech_ops` |
| 查看危机记录 | — | 仅 `super_admin`，每次查看写审计 |

五条必须遵守的边界：

1. **`ai_trainer` 看不到通话逐轮文本**。仓库既有 `_USER_BUSINESS_READ_ROLES` 不含 `ai_trainer`，这是一条既有隐私边界（`ai_trainer` 看不到用户历史对话），语音应对齐而非打破。`ai_trainer` 调话术走在线测试工具，不通过读真实用户通话内容来调优。
2. **`observer` 可读、不可导出有效正文**。它可在通话详情中逐条查看未到期的用户 final 与 AI effective；不得查看 AI 完整生成文本、`reasoning` 或危机原文。
3. **导出必须单独拒绝 `observer`**。导出固定为 `POST /api/admin/voice/calls/export`；除方法级写总闸外仍须显式挂 `deny_observer_export`，把“observer 永不允许导出”固化为接口契约，后端返回 403。
4. **`reasoning` 仅供 `super_admin` 后台调优**，每次读取写审计，30 天到期清空；不进用户端响应、聊天 timeline、摘要卡或任何导出。`ai_trainer`、`ops_admin` 和 `observer` 均返回 403。
5. **凭据对 `observer` 只返回已/未配置状态**，禁止原文、首尾、掩码、哈希或可推断元数据。

后端角色校验是安全边界，前端 `isObserver()` / `applyObserverReadOnly()` / `data-write-action` 只改善体验。

---

## 12. 通话记录与转写后台

### 12.1 列表

**页面可见范围**：`super_admin` / `ops_admin` / `observer`。`ai_trainer` 无入口（ADM-C24）。

后台「历史对话 Tab」本期**不纳入**通话记录——它是独立的 SQL `union_all` 实现，与用户端 `timeline_read_service` 是两份代码。该页面需加提示指向本页。

默认列：

- 用户；
- 开始时间；
- 接听状态（`ended` / `missed` / `failed` / `cancelled` 四分）；
- 有效时长；
- 结束原因（九项之一）；
- 免费/额外/缓冲消耗；
- Provider、模型、音色和配置版本；
- 摘要状态（`pending` / `ready` / `failed` / `not_applicable`）；
- 回合数；
- 记忆任务成功/失败数（取自 `voice_memory_trace` 台账与 `voice_memory_job`）；
- 记忆条目丢弃数（Stable Key / value 校验不通过）；
- 内容安全命中数；
- 打断；
- 追加消息；
- 整通情绪（`user_emotion` / `assistant_emotion`）；
- 有效转写到期时间、剩余天数和清理状态。

筛选：

- 时间范围；
- 用户；
- 状态/结束原因；
- Provider/模型/配置版本；
- 有无打断；
- 摘要/记忆/后处理状态；
- 到期或已清理；
- 是否已删除仅限审计视图。

### 12.2 详情

建议标签页：

1. 概览；
2. 逐轮转写；
3. 任务；
4. 配置快照；
5. 用量与成长；
6. 审计。

逐轮转写只读，不提供改写正文能力。普通视图只展示用户 final 与 AI effective，`observer` 在此范围内可读；`ai_trainer` 无页面入口且直接调接口返回 403。完整生成文本与 `reasoning` 只对 `super_admin` 的受限调优视图开放，独立权限、逐次读取审计且受 30 天保留约束；`reasoning` 不进用户端、timeline 或导出。

### 12.3 操作

- 通过 `POST /api/admin/voice/calls/export` 导出未到期有效文本（必须显式挂 `deny_observer_export`）；
- 补跑允许重试的失败任务；
- 删除通话；
- 查看受限调试文本；
- 强制挂断进行中通话（`tech_ops`，写操作日志）。

删除确认框必须说明：

```text
将删除通话卡片、摘要和逐轮文字，并取消未完成任务。
已经成功写入的长期记忆、用量账本、成长值和无正文审计不会删除或回滚。
```

服务端删除顺序和数据边界以父 PRD 第 17.5、19.4 节为准。

单通删除不等于账号注销。账号注销已从 P1 移出，以本地技术债 `TD-V-07` 记录：未来由项目级注销流程调用语音清理能力。P1 不新增账号注销入口、不定义语音专项注销 API，也不实现全域注销 orchestrator。

### 12.4 危机记录页（v1.1 新增，Phase D）

独立页面，与通话记录页分离。

| 项 | 规则 |
|---|---|
| 可见范围 | **仅 `super_admin`**。其他角色（含 `ops_admin`、`observer`）无入口、无接口权限 |
| 审计 | **每次查看**（列表与详情）都写审计日志，记录操作人、`call_id`、时间 |
| 内容 | 逐字原文、命中词、命中方（用户 / AI）、`call_id`、`turn_index`、时间 |
| 保留期 | **30 天**，不随转写 180 天规则；到期清空原文，可保留无正文审计元数据 |
| 导出 | 本期**不提供导出** |
| AI 侧命中 | 单独标记为人格事故并置顶告警 |

危机原文只存在于该独立表，**不进**向量库、`voice_call_turn`、摘要与会前小包。这是唯一能保证「不被角色感知」的做法：若存进 `voice_call_turn`，会被会前小包与 CALL-SUM-01 读到，违反 P0 C16 的原始约束。

P1 **不增加应用层字段加密**。保护措施固定为独立表隔离、后端 RBAC（仅 `super_admin`）、列表与详情的逐次读取审计、30 天到期清理，以及不导出。不得因“未做应用层加密”而放宽上述任一边界。

因此通话记录页的逐轮转写视图**不展示**危机原文，只展示该回合被标记为 `memory_status=skipped`。

---

## 13. 审计

必须审计：

- 保存/丢弃草稿；
- 验证、连接测试、能力测试；
- 发布、回滚；
- 强制启用未验证能力；
- 查看转写；
- 查看完整生成文本；
- 导出；
- 任务补跑；
- 删除通话；
- 软停、硬停与强制挂断进行中通话；
- 查看危机记录（列表与详情均记）。

配置审计字段至少包括：

```text
operator
permission
config_version
base_version
draft_revision
changed_sections
change_note
verification_status
forced_enabled
effective_scope
result
failure_category
created_at
```

转写和通话操作审计字段以父 PRD 第 17.4 节为准。普通审计只保存字段名、差异摘要、内部 ID、哈希或脱敏值，不保存密钥和完整转写正文。

---

## 14. 管理 API

### 14.1 配置

配置接口均带 `config_key` 路径段，两个 key（`config` / `script`）复用同一套语义、各自独立鉴权：

| 接口 | 用途 |
|---|---|
| `GET /api/admin/voice/config/{key}` | 生效配置、草稿状态和差异摘要（`key` ∈ `config` / `script`） |
| `PATCH /api/admin/voice/config/{key}/draft/{section}` | 保存一个分区草稿，须带 `base_version` + `draft_revision` |
| `DELETE /api/admin/voice/config/{key}/draft/{section}` | 放弃一个分区修改 |
| `DELETE /api/admin/voice/config/{key}/draft` | 丢弃全部草稿 |
| `POST /api/admin/voice/config/{key}/validate` | 整包 Schema、参数取值范围与联动校验；`key=config` 时可选执行 follow-up 无副作用预览 |
| `POST /api/admin/voice/config/test-connection` | 使用草稿执行 S2S 连接测试 |
| `POST /api/admin/voice/config/test-capability` | 执行指定能力测试；按每轮每能力位追加 `voice_capability_evidence` 并向草稿写只读投影/引用 |
| `GET /api/admin/voice/capability-evidence/{evidence_report_id}` | 读取能力证据；`super_admin` / `tech_ops` 返回已脱敏完整证据，其他配置读角色只返回非敏感投影 |
| `POST /api/admin/voice/config/{key}/publish` | 整包发布，须带 `confirm_text` |
| `GET /api/admin/voice/config/{key}/history` | 版本历史 |
| `GET /api/admin/voice/config/{key}/history/{version}` | 历史详情 |
| `POST /api/admin/voice/config/{key}/rollback` | 整包回滚 |

#### 14.1.1 follow-up 窗口校验与预览（ADM-C32）

预览不新增端点，固定复用 `POST /api/admin/voice/config/config/validate`。该端点对 `voice_call_config` 的校验/预览权限为 `super_admin` / `tech_ops`；`ai_trainer` / `ops_admin` / `observer` 请求返回 403。请求可以只做常规整包校验，也可带一个预览输入：

```json
{
  "followup_preview": {
    "stage": "friend",
    "candidate_at": "2026-08-30T23:10:00+08:00",
    "jitter_minutes": 20
  }
}
```

- `stage` 只允许 `stranger` / `friend` / `intimate` / `soulmate`；
- `candidate_at` 必须是带时区偏移的 ISO-8601 时间，服务端统一转为本期 `Asia/Shanghai`；
- `jitter_minutes` 是确定性预览值，必须为 0–20 的整数；仅在候选时间不在窗口内时应用；
- 服务端使用本次待校验的整包草稿；无草稿时使用当前生效版本。

成功响应中的预览结果固定为：

```json
{
  "valid": true,
  "errors": [],
  "followup_preview": {
    "stage": "friend",
    "candidate_at": "2026-08-30T23:10:00+08:00",
    "resolution": "next_window",
    "in_window": false,
    "resolved_window": {
      "start_at": "2026-08-31T09:30:00+08:00",
      "end_at": "2026-08-31T22:00:00+08:00"
    },
    "jitter_applied_minutes": 20,
    "resolved_due_at": "2026-08-31T09:50:00+08:00",
    "delay_seconds": 38400,
    "cancel_reason": null
  }
}
```

`resolution` 只取 `in_window` / `next_window` / `cancelled`。候选时间在左闭右开窗口内时，`resolution=in_window`、`jitter_applied_minutes=0`、`resolved_due_at=candidate_at`；窗外则定位下一窗口起点后加输入 jitter。`resolved_due_at - candidate_at == 24h` 合法；大于 24h 时返回 `resolution=cancelled`、`resolved_due_at=null`、`cancel_reason=max_delay_exceeded`。

窗口数组顺序不被信任；校验时先按分钟规范化并排序，再检查同阶段重叠。相邻合法，跨阶段重叠不报错。错误码只使用：

| 错误码 | 触发条件 |
|---|---|
| `FOLLOWUP_WINDOW_RANGE_INVALID` | 阶段缺失/窗口空、时间格式错误、`start >= end`、跨日或非分钟精度 |
| `FOLLOWUP_WINDOW_OVERLAP` | 同一关系阶段的规范化区间真正重叠；相邻不报错 |
| `FOLLOWUP_WINDOW_TOO_SHORT_FOR_JITTER` | 任一窗口时长 `<= jitter_max_minutes` |
| `FOLLOWUP_PREVIEW_INPUT_INVALID` | 预览 stage、带时区候选时间或 0–20 整数 jitter 不合法 |

预览是纯计算：不修改草稿/生效版本、不发布、不更新 Redis、不创建 `voice_followup_job`，也不改变既有 job 快照。

`crisis_keywords` 不使用上表的语音整包草稿接口，而是在既有内容安全规则域做最小扩展：

| 接口 | 用途与权限 |
|---|---|
| `GET /api/admin/safety-rules` | 响应新增 `crisis_keywords`；沿用 `super_admin` / `ai_trainer` / `observer` 读取角色 |
| `PUT /api/admin/safety-rules/crisis-keywords` | 全量规范化与校验关键词数组；规范化后空集直接拒绝（`minItems: 1`），通过后发布并原子更新 `active_config:crisis_keywords`；仅 `super_admin` / `ai_trainer` |
| `GET /api/admin/safety-rules/crisis-keywords/history` | 查看版本历史；沿用安全规则读取角色 |
| `POST /api/admin/safety-rules/crisis-keywords/rollback` | 回滚目标规范化后为空时拒绝；其余回滚生成新发布版本并原子恢复 Redis；仅 `super_admin` / `ai_trainer` |

### 14.2 通话记录

沿用父 PRD 定义：

- `GET /api/admin/voice/calls`
- `GET /api/admin/voice/calls/{call_id}`
- `GET /api/admin/voice/calls/{call_id}/turns`
- `POST /api/admin/voice/calls/export`
- `DELETE /api/admin/voice/calls/{call_id}`

建议补充：

- `GET /api/admin/voice/calls/{call_id}/jobs`
- `POST /api/admin/voice/jobs/{job_id}/retry`
- `GET /api/admin/voice/calls/{call_id}/audit`

通话导出接口固定为 `POST /api/admin/voice/calls/export`，必须显式挂 `deny_observer_export`。

### 14.3 运维动作（v1.1 新增）

| 接口 | 用途 | 权限 |
|---|---|---|
| `POST /api/admin/voice/ops/soft-stop` | 软停：只拦新拨打 | `super_admin` / `tech_ops` |
| `POST /api/admin/voice/ops/hard-stop` | 硬停：断开全部进行中通话 | `super_admin` / `tech_ops` |
| `POST /api/admin/voice/calls/{call_id}/force-end` | 强制挂断单通 | `super_admin` / `tech_ops` |
| `GET /api/admin/voice/ops/active-calls` | 查看进行中通话与并发计数对账结果 | `super_admin` / `tech_ops` / `observer` |

三个写接口均要求 `CONFIRM` 并写操作日志。

### 14.4 危机记录（v1.1 新增）

| 接口 | 用途 | 权限 |
|---|---|---|
| `GET /api/admin/voice/crisis-records` | 危机记录列表 | 仅 `super_admin` |
| `GET /api/admin/voice/crisis-records/{record_id}` | 危机记录详情（含逐字原文） | 仅 `super_admin` |

两个接口均为 GET，但**每次调用都写审计**；本期不提供导出接口。

所有写接口都必须执行后端权限校验并按既有规范审计，不能只依赖前端按钮状态；`CONFIRM` 与幂等只用于本文逐端点明确要求的发布、回滚、停用、删除等动作，不给普通草稿保存或既有安全规则写接口追加未定义门槛。

---

## 15. P0 配置迁移映射

| P0 配置 | 正式归属 | 处理 |
|---|---|---|
| `PHASE0_DOUBAO_S2S_APP_ID` | Secret | 不进 JSON |
| `PHASE0_DOUBAO_S2S_ACCESS_KEY` | Secret | 不进 JSON |
| `PHASE0_DOUBAO_S2S_APP_KEY` | Secret | 不进 JSON |
| S2S Endpoint | `s2s.endpoint` | 迁移 |
| Resource ID | `s2s.resource_id` | 迁移 |
| Model | `s2s.model_version` | 迁移 |
| StartSession `dialog.extra` 与上下行音频参数 | `s2s.protocol_profile` | 收敛为 Adapter 维护的可选 Profile，不开放任意 JSON |
| Speaker | `voice.voice_id` | 迁移 |
| `voice_candidates` | `voice.candidates` | 迁移并增加版本/启停 |
| `speech_rate/loudness_rate/expressive` | `voice.*` | 迁移 |
| `tone_hint` | `voice.tone_instruction` | 生产化并纳入预算 |
| `trigger_keywords` | `recall.trigger_rules` | 作为种子 |
| `max_recent_dialog_chars` | `context_pack.recent_dialog_max_chars` | 迁移 |
| `max_query_chars` | `recall.max_query_chars` | 作为 P0 种子 |
| `PHASE0_EMBEDDING_TIMEOUT` | `recall.embedding_timeout_ms` | 秒转毫秒后作为 P0 种子 |
| `PHASE0_DASHVECTOR_TIMEOUT` | `recall.vector_timeout_ms` | 秒转毫秒后作为 P0 种子 |
| `preamble_memory_doc_ids` | 无 | 废弃 |
| `whitelist_user_ids` | `global.rollout.user_ids` | 改为白名单（无百分比模式） |
| `persona_version_label` | `context_pack.persona_ref` | 改为明确的已发布 `persona` 版本，不保留 `active/draft_snapshot` 手工标签语义 |
| `character_manifest` / `_system_prompt` | 编译产物 | 由人格版本、语音指令和动态小包生成，不作为独立手工配置源 |
| `mock_s2s` | 测试工具 | 不进生产配置 |
| `net_profile` | 测试工具 | 不进生产配置 |

P0 硬编码的 TopK、阈值、超时等只作为初始测试种子；未经过本轮确认或 P0 证据的值不得描述为正式产品默认值。

---

## 16. 验收

### 16.1 Phase A

- 可分区保存草稿，保存不影响生效配置；
- 整包发布生成唯一新版本；
- 进行中通话不发生热切换；
- 新通话保存完整非敏感配置快照；
- 密钥不进入配置、Redis、历史、日志、API 响应和通话快照；
- S2S 连接测试使用服务端 Secret，响应不泄露凭据；
- Provider、模型、协议 Profile、音色和 Adapter 变更可追溯；
- 未验证能力显著标记；
- 未验证能力只能在审计 `test` 中强制启用，不能全量；
- 强制启用要求权限、`CONFIRM`、原因和审计；
- Provider Profile/模型/协议 Profile/Adapter/SDK/取证用例集版本任一变化使旧能力证据变为 `stale`；
- 证据指纹覆盖 Provider Profile、模型、协议 Profile、Adapter、SDK 与取证用例集版本；指纹变化立即 `stale`，证据有效期默认 30 天且只允许发布 7–90 天；能力证据每轮每能力位只追加一条 MySQL 独立记录，配置只保存只读投影/引用并在发布时重新核验，完整脱敏证据只对 `super_admin` / `tech_ops` 开放，证据不允许更新或业务删除；
- `persona_ref` 只能引用已发布人格版本，发布记录和通话快照均能还原实际人格与语音指令；
- `stale/unverified` 能力仍只能进入审计 `test`，`failed` 能力不能强制启用；
- 回滚整包发布新版本，不修改旧通话快照；
- `base_version` 和 `draft_revision` 阻止静默覆盖。

v1.1–v1.3 新增验收项：

- 两个 `config_key` 各自独立鉴权：`tech_ops` 不能改话术，`ai_trainer` 不能改阈值与能力位；
- **运行时确实读取配置**：调整并发上限或日配额并发布后，下一通通话立即按新值执行（父 PRD AC76）；
- 配置缺失或 JSON 解析失败时回退代码默认值并记指标，通话不被阻断（AC77）；
- 六项能力位的初始态为「未验证 + 关闭 + `effective_scope=off`」，页面无法通过任何操作把 `verification_status` 手工改成 `verified`；
- `effective_scope` 选项中不存在按用户分桶的灰度；`global.rollout` 中不存在 `percentage`；
- 卡点一执行参数取值范围校验，越界值被拒绝并给出具体字段与允许区间；
- 发布需后端精确校验 `confirm_text == "CONFIRM"`；
- 凭据页只显示环境变量名与已/未配置状态；observer 视图不含任何可推断元数据；
- 软停生效后新拨打被拒绝而进行中通话不受影响；硬停生效后进行中通话全部结束；两者均产生操作日志；
- `persona_ref` 同时保存 `version` 与 `content_sha256`，人格历史版本被清理后仍可判定通话使用的人格是否与当前生效版本一致。
- O-05 四关系阶段以非空多窗口配置随 `voice_call_config` 初始生效版本交付，可发布/回滚；同阶段范围/重叠/窗口时长校验、无副作用预览、左闭右开、窗内不抖动、窗外顺延加抖动及 24 小时边界均符合 ADM-C32；初始发布与读取失败共用一份规范默认常量，既有追加任务不因新版本漂移。`missed_explanation_template` 使用 ADM-C31 的无变量逐字默认值并随 script 发布/回滚，异常时同值回退并告警。
- `crisis_keywords` 发布/回滚均拒绝规范化后空集；缓存缺失、非法、空集或读取异常时均按疑似命中并告警，不得静默停用危机检测。

### 16.2 Phase D

- 按权限查看逐轮有效转写、到期时间和清理状态；
- 普通导出不包含完整生成文本；
- `observer` 可逐条查看未到期有效正文，但导出返回 403；
- 查看、导出、补跑和删除均审计；
- 删除先设置围栏再取消任务；
- 删除不回滚成功记忆、账本和成长值；
- 到期或删除正文不可恢复、不可导出；
- 后台不保存或展示原始音频；
- `ai_trainer` 无通话记录页入口，直接调接口返回 403；
- `POST /api/admin/voice/calls/export` 对 observer 返回 403（`deny_observer_export` 生效）；
- `reasoning` 仅 `super_admin` 后台调优可读，逐次读取审计，30 天到期清空，用户端、timeline 和导出均无该字段；
- 危机记录页仅 `super_admin` 可访问，每次查看产生审计记录；
- 危机原文 30 天、任务日志 90 天到期清理；危机原文依靠独立表/RBAC/逐次读取审计保护，P1 不增应用层加密；
- 通话逐轮转写视图不展示危机原文，只展示该回合 `memory_status=skipped`。
- P1 无账号注销入口/API/orchestrator；未来接入只记为本地技术债 `TD-V-07`。

---

## 17. 文档同步与后续拆解

本文建立后：

1. 父 PRD 第 17 节保留产品级概要并链接本文；
2. 父 PRD 同步未验证能力强制启用、凭据边界、聚合发布和快照决策；
3. `docs/design/README.md` 增加本文入口说明；
4. 不读取或修改历史、草案、归档与 `.doc-migration-baseline/`；
5. 本文确认不等于代码已经实现；
6. 开发前应基于本文另行拆解 Phase A 的数据、API、后台 UI、测试与迁移步骤。

### 17.1 Phase A STEP 拆解注意事项（v1.1 新增）

父 PRD 第 22.2 节是全量拆解清单，本节只列后台侧最易漏掉的项。

| # | 事项 |
|---|---|
| 1 | `admin_config` 增加 `draft_revision` 可空列是**既有表 ALTER**，必须单独成一个可回滚的迁移 STEP，不能混在语音新建表里 |
| 2 | 配置页 STEP 与运行时读取 STEP **必须同期交付**，不得拆成「先做页面后接运行时」（否则成为第四条同型技术债） |
| 3 | 语音草稿保存方法是新写的，**不要复用** `save_draft`；评审时确认乐观锁分支有测试覆盖 |
| 4 | 两个 `config_key` 的鉴权要分别写测试：`tech_ops` 改话术应 403，`ai_trainer` 改阈值应 403 |
| 5 | 通话导出的 `deny_observer_export` 要有专门用例，仅靠方法级写总闸会漏 |
| 6 | 能力位初始值必须由迁移或首次发布显式写入「全 false」，不能依赖代码默认值兜底 |
| 7 | 硬停需要「遍历进行中通话」的能力，与第 6.10 节的并发对账共用同一段实现，两者应在同一 STEP |
| 8 | 危机记录页的审计是「读也要审计」，与其他页面的「写才审计」不同，容易漏 |
| 9 | `ACTION_LABELS`、`get_relationship_detail.today_growth` 属于既有后台展示，语音成长值 STEP 必须一并处理，否则后台显示空标签与错数值 |
| 10 | O-02 / O-05 已定稿：能力矩阵 STEP 必须同时落地指纹 + 30 天默认/7–90 天可配失效，以及 MySQL 追加式证据记录/只读投影/发布重校验；追加消息 STEP 必须用同一份规范默认值完成多窗口种子发布和读取失败回退、保存任务快照版本，并实现 ADM-C32 的校验/预览契约；missed 分支必须消费 ADM-C31 的精确 script 文案，不在业务分支散落窗口或文案值 |
| 11 | P1 账号注销只记 `TD-V-07`；不得在语音 STEP 中新建注销入口或全域 orchestrator |

---

## 18. 版本记录

| 版本 | 日期 | 变化 |
|---|---|---|
| v1 | 2026-08-25 | 从父 PRD 后台章节拆出详细设计；确认聚合配置、分区草稿/整包发布、Secret 引用和能力矩阵；未验证能力范围后由 ADM-C21 收口为仅审计 `test` |
| v1.1 | 2026-08-26 | 按《需求确认记录 v1》代码对齐：新增 ADM-C12 ~ ADM-C24；配置拆为 `voice_call_config` / `voice_call_script` 并分权；明确 `base_version` 复用生效行 `version`、`draft_revision` 为新增可空列、草稿保存不复用 `save_draft`；`persona_ref` 增 `content_sha256`；凭据改为只走环境变量并声明不支持热切；移除百分比 rollout 与 `capability_gray` 按用户维度；能力位默认全 `false`；卡点一改为参数取值范围校验；新增单实例部署前提、软停/硬停两级停用、通话租约 owner token 与并发对账、内容安全与危机关键词配置、运行时接入与降级、危机记录页、运维与危机 API、Phase A STEP 注意事项 |
| v1.2 | 2026-08-29 | 关闭 O-02 / O-05 / O-06：定稿证据指纹和默认 30 天（7–90 天可发布）失效；追加消息四档初始窗口改为 `voice_call_config` 可发布/回滚配置并锁定任务快照；定稿中国大陆危机文案与非红色系统卡；明确危机原文 30 天、任务日志 90 天、不增应用层加密；对齐 `observer` 正文可读/导出 403、`ai_trainer` 正文 403 及 `reasoning` 只对 `super_admin`、30 天、不进用户端/timeline/导出；账号注销移出 P1 并记为 `TD-V-07` |
| v1.3 | 2026-08-30 | 对齐需求确认记录 v1.2 与父 PRD v2.4：新增 ADM-C30～C32；冻结 MySQL `voice_capability_evidence` 表的追加式 Schema、脱敏、事务、发布重校验、保留与权限；冻结 missed 首发逐字文案和同值回退；将 follow-up 时段改为非空多窗口 Schema，复用 config validate 定稿无副作用预览请求/响应、边界规则和四个专用错误码 |

2026-09-13 已确认迁入P0附和方案：复用voice_call_script.barge_in中的词表，组合匹配纯附和；以近期实际播放进度绑定原问题，过滤对应额外输出并异步删除远端问答、核对回执。过滤事件保留无文本序号占位，不进入有效对话或记忆。缺结束事件暂不删除远端，作为后续优化。post_playback_buffer_ms缺省按800ms读入新通话快照，不补写历史发布配置；正在运行的旧通话保持原策略。联网搜索不纳入本轮。
