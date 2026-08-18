# 未登录可用功能开放与登录弹窗改造 v1 · 开发进度

> 创建/更新：2026-08-02  
> 唯一 STEP 来源：`docs/design/open_login/prd-delivery-runs/20260802T095138Z-open-login/steps-verified.md`  
> 实施计划：`docs/design/open_login/prd-delivery-runs/20260802T095138Z-open-login/execution-plan.md`  
> 用户决定：UD-01～UD-03 全部采用方案 A  
> 正式契约：`docs/contract/current/life-feed/api.md`、`docs/contract/current/h5-app/api.md`  
> 历史增量快照：`docs/contract/drafts/open_login/`（非权威）

## 总览

| 完成 STEP | 总 STEP | 当前状态 |
|---|---|---|
| 7 | 8 | `USER_ACCEPTED / FORMAL_CONTRACT_SYNCED / STEP-008_REPO_GATE_PARTIAL` |

功能 STEP-001～007 已完成，用户已于 2026-08-02 验收通过。用户随后授权正式契约收口，Life Feed 与 H5 App 当前契约已与本轮实现同步。STEP-008 仅因仓库全量门禁仍有两项经隔离确认的范围外失败，不满足“全量 pytest 退出码 0”的完成标志。

## STEP 状态与证据

| STEP | 状态 | 主要实现/验收证据 |
|---|---|---|
| STEP-001 | DONE | 仅三个白名单 GET 可选鉴权；缺头/坏头矩阵、匿名 Feed 字段和查询隔离、写接口强鉴权测试通过 |
| STEP-002 | DONE | 共享三面板弹窗、UD-01 注册分叉、四类 401 策略；静态契约与浏览器交互通过 |
| STEP-003 | DONE | Index 无 token/有效/过期 token、主动弹窗、登录恢复的 DOM/Network 矩阵通过 |
| STEP-004 | DONE | Feed 匿名只读、focus 边界、SSE/观察器幂等、写门禁/401 回滚和登录恢复通过；自审发现并修复私有评论 DOM 残留及匿名恢复重复请求 |
| STEP-005 | DONE | Settings 私有区隐藏、About 公共读取、401 静默降级与登录恢复通过 |
| STEP-006 | DONE | Chat 访客零私有/模型请求；发送/Enter/重试门禁、401 回滚、登录后不自动发送通过 |
| STEP-007 | DONE | Diary/Memory/Relationship 无 token 与中途 401 单次回首页弹窗；强鉴权接口回归通过 |
| STEP-008 | `PARTIAL / KNOWN_REPOSITORY_BLOCKERS` | 针对性测试、浏览器矩阵、用户验收与正式契约同步已完成；仓库全量测试仍有两项范围外失败 |

## 自动化验证记录

| 范围 | 命令 | 结果 |
|---|---|---|
| 本 PRD 针对性 | `PYTHONPATH=. .venv-step001/bin/pytest tests/test_app_persona_background.py tests/test_step015_feed_service.py tests/test_h5_static_contract.py -q` | 契约收口后最终复验：`64 passed in 2.45s` |
| H5 依赖脚本语法 | bundled Node 分别执行 `--check frontend/static/js/api.js` 与 `--check frontend/static/js/memory-nebula.js` | 退出码 0，无输出 |
| 正式契约与 manifest | `jq empty docs/llm-manifest.json`；`PYTHONPATH=. .venv-step001/bin/pytest tests/test_docs_structure.py -q --tb=short` | JSON 退出码 0；契约迁移锚点 C-021/C-028 通过，文档测试为 `1 failed, 4 passed in 0.12s`，只剩既有 Phase0 voice code surface 映射失败 |
| 全量首次运行 | `PYTHONPATH=. .venv-step001/bin/pytest tests/` | `37 failed, 952 passed, 3 skipped`；见“范围外失败归因” |
| 分词缓存隔离复跑 | 使用 `/tmp` 的 `cl100k_base` 缓存复跑 prompt/Step8 相关四个文件 | `56 passed in 4.57s` |
| Node PATH 隔离复跑 | 将 bundled Node 目录加入 PATH 后复跑 `tests/test_chat_time.py` | `7 passed in 0.36s` |
| 全量环境归一化复跑 | bundled Node PATH + `/tmp` 分词缓存，执行 `PYTHONPATH=. .venv-step001/bin/pytest tests/ -q --tb=short` | 契约收口后最终快照：`2 failed, 987 passed, 3 skipped, 205 warnings in 98.65s`；只剩两项范围外失败 |

逐 STEP 最终独立复验：STEP-001 `45 passed in 2.45s`；STEP-002～005 分别 `1 passed in 0.02s`；STEP-006 `1 passed in 0.01s`；STEP-007 `2 passed in 0.49s`。STEP-004 在请求幂等修复后再次单独复验为 `1 passed in 0.02s`。

## 浏览器证据索引

| AC | 本地证据摘要 |
|---|---|
| AC-01 | Index 访客仅公共 Feed 请求；精确文案/隐藏区/入口门禁；登录后私有请求各一次；过期 token 静默访客化 |
| AC-02 | Feed 访客仅 Header/List；无 enter/badge/SSE/read；登录恢复资源一次；主动 401 后清除私有评论 DOM，并仅发 `POST like` + 匿名 Header/List 各一次 |
| AC-03 | Settings 访客私有区隐藏、About 可用；登录恢复；设置 401 静默降级且 About 保留 |
| AC-04 | Chat 访客初始化零私有请求；门禁不生成幽灵消息；登录不自动发送；主动 401 保留输入并清空临时消息 |
| AC-05 | 三受保护页直访和中途 401 均只回首页/弹窗一次；刷新无循环；登录后停留首页 |
| AC-06 | 弹窗登录/注册回调一次；注册直接建会话；重置回登录面板；独立登录页注册仍要求登录 |
| AC-07 | 三个匿名 GET、坏 token 401、Feed 条件字段与匿名查询隔离均由自动化覆盖 |

浏览器使用本地静态页与确定性 mock API，核对 DOM、URL、请求次数、SSE/观察器和交互；未声称线上行为已验证。

## 范围外失败归因

- prompt/Step8 共 28 项：沙箱禁止首次下载 `cl100k_base`；下载到 `/tmp` 临时缓存后同组 `56 passed`，不是本轮代码回归。
- `tests/test_chat_time.py` 7 项：测试子进程 PATH 找不到 Node；显式加入 bundled Node 后 `7 passed`，不是页面逻辑失败。
- `tests/test_docs_structure.py` 1 项：既有未提交 Phase0 voice 页面/路由造成 25 个未映射、5 个陈旧 code surface；这些是开始前就存在的无关用户改动，本轮未覆盖。
- `tests/test_step025_observer_system_monitor.py` 1 项：夹具写入固定日期 `2026-07-16`，默认查询窗口按当前日期 `2026-08-02` 最近 7 天，返回空列表；与本轮代码无关。

## 契约与技术债记录

| 里程碑 | 临时增量 | 状态 |
|---|---|---|
| M1 | `docs/contract/drafts/open_login/M1_契约草案.md` | 已记录 |
| M2 | `docs/contract/drafts/open_login/M2_契约草案.md` | 已记录 |
| M3 | `docs/contract/drafts/open_login/M3_契约草案.md` | 已记录 |
| M4 | `docs/contract/drafts/open_login/M4_契约草案.md` | 用户验收；正式契约已收口；保留已知仓库门禁记录 |

- 本地证据足以说明本轮实现覆盖 `TD-HOME-08 / N1-B` 所述访客浏览缺口，但不改变任何全局技术债状态。
- TD-AUTH-01/02 继续只作为 PRD 本地标识；未写全局编号、别名或归档结论。
- 本轮只修改 `docs/contract/current/life-feed/api.md`、`docs/contract/current/h5-app/api.md` 及其在 `docs/llm-manifest.json` 中的检索元数据；未修改汇总入口 `docs/contract.md`、`docs/tech-debt.md` 或 `docs/tech-debt/active/`。

## 风险与后续门禁

1. R-01：找回密码安全模型保持原状，入口随共享弹窗可见；没有在本轮伪装为已加固。
2. R-02：匿名 Feed 读取继续沿用 `actual_publish_time` 懒写回及既有公共负载，未自行增加限流值。
3. 正式 Life Feed/H5 App 契约已与本轮实现同步；临时增量目录已转为历史快照，不再作为当前权威来源。
4. 若要求 STEP-008 在 `steps-verified.md` 自动化总门禁口径下标记为 DONE，仍需先处理两项范围外仓库失败，再以最终同一快照重跑全量门禁。
5. 开始前 `docs/contract/current/`、`docs/llm-manifest.json` 及本 PRD 文档即处于 Git 未跟踪的整体文档迁移工作区中；本轮未擅自 stage/commit，后续发布或合并时必须将这些正式文档与 manifest 一并纳入版本库。

## 偏差记录

| 日期 | 来源 | 偏差 | 处理 |
|---|---|---|---|
| 2026-08-02 | 用户本轮要求 | STEP-008 原文要求同步正式 Contract；用户明确要求本阶段不修改 | 用户要求优先，只写临时契约；STEP-008 保持 PARTIAL |
| 2026-08-02 | 用户验收结论 | 用户验收通过并明确授权完整更新本模块正式契约 | 同步 Life Feed/H5 App 正式契约，临时契约转历史快照；不掩盖全量门禁范围外失败 |
