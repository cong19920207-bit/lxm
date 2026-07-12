# 文档索引

> 仓库文档地图（2026-05-31）。目录整理后，**部分旧文档内的相对链接仍指向迁移前路径**，以本索引为准查找文件。  
> **线上运行时**不依赖本目录；契约与实现以代码 + `contract.md` 为准。

## 锚点（优先阅读）


| 文档                             | 说明                                |
| ------------------------------ | --------------------------------- |
| [VERSIONS.md](VERSIONS.md)     | 产品版本记录（发布切片 / 版本号 / 概述与运维备注）     |
| [contract.md](contract.md)     | 接口 / 库表 / H5·Admin 行为契约（变更功能时必同步） |
| [tech-debt.md](tech-debt.md)   | 技术债 TD-xxx 登记与清偿状态                |
| [ops-diary.md](ops-diary.md)   | AI 日记运维：时区、手动批跑、发布注意              |
| [progress/](progress/)         | 专项迭代进度（记忆检索、长记忆下线等）               |


## `docs/` — 工程协作文档

### 运维 `ops/`


| 文档                                                       | 说明                            |
| -------------------------------------------------------- | ----------------------------- |
| [ops/docker-admin-deploy.md](ops/docker-admin-deploy.md) | Docker / Admin 部署与 alembic 升级 |


### 测试 `testing/`


| 子目录                                        | 内容                                                               |
| ------------------------------------------ | ---------------------------------------------------------------- |
| [testing/reports/](testing/reports/)       | 验收 / E2E 报告（`test_report_MEMPROBE_`*、`test_report_MEMOFFLINE_*`） |
| [testing/checklists/](testing/checklists/) | 手工回归清单                                                           |
| [testing/guides/](testing/guides/)         | 测试说明、trace、Docker 冒烟、日记测试、聊天排障                                   |
| [testing/logs/](testing/logs/)             | 探针 / Prompt trace 运行日志（`.log`，非 Markdown）                        |


报告由 `scripts/mem_prd_docker_e2e.py` 写入 `testing/reports/test_report_MEMPROBE_<id>.md`。

### 改造专项 `refactor/`

**对话 / H5** — [refactor/chat/](refactor/chat/)

- [chat-refactor-implementation-plan.md](refactor/chat/chat-refactor-implementation-plan.md)
- [chat-refactor-agent-tasks.md](refactor/chat/chat-refactor-agent-tasks.md)
- [chat-refactor-vibe-coding-plan.md](refactor/chat/chat-refactor-vibe-coding-plan.md)
- [admin-conversations-extension-analysis.md](refactor/chat/admin-conversations-extension-analysis.md)

**AI 日记** — [refactor/diary/](refactor/diary/)

- [diary-refactor-decisions.md](refactor/diary/diary-refactor-decisions.md)
- [diary-refactor-plan.md](refactor/diary/diary-refactor-plan.md)
- [diary-refactor-decision-vs-plan.md](refactor/diary/diary-refactor-decision-vs-plan.md)

手工回归清单见 [testing/checklists/chat-refactor-s4-manual-regression-checklist.md](testing/checklists/chat-refactor-s4-manual-regression-checklist.md)。

### 产品与体验 `design/`


| 文档                                                                                       | 说明          |
| ---------------------------------------------------------------------------------------- | ----------- |
| [design/product-development-plan-h5-chat.md](design/product-development-plan-h5-chat.md) | H5 对话产品开发方案 |
| [design/chat-message-pipeline.md](design/chat-message-pipeline.md)                       | 消息管线说明      |
| [design/DESIGN_SYSTEM.md](design/DESIGN_SYSTEM.md)                                       | 设计系统        |


### 进度 `progress/`


| 文档                                                                                 | 关联 PRD                                     |
| ---------------------------------------------------------------------------------- | ------------------------------------------ |
| [progress/记忆检索与Prompt优化_progress.md](progress/记忆检索与Prompt优化_progress.md)           | `doc/memory/prd/PRD-记忆检索与Prompt优化.md`      |
| [progress/长记忆第一套下线与Step6运营收敛_progress.md](progress/长记忆第一套下线与Step6运营收敛_progress.md) | `doc/memory/prd/PRD-长记忆第一套下线与Step6运营收敛.md` |


## `doc/` — 需求与 Prompt 定稿

### 对话链路 `doc/chat/`


| 文档                                                                     | 说明            |
| ---------------------------------------------------------------------- | ------------- |
| [../doc/chat/对话链路改造-需求确认记录.md](../doc/chat/对话链路改造-需求确认记录.md)           | 已拍板需求（单一维护入口） |
| [../doc/chat/对话链路改造需求文档.md](../doc/chat/对话链路改造需求文档.md)                 | 计划稿 / 讨论底稿    |
| [../doc/chat/INPUT_PROCESS_FLOW.md](../doc/chat/INPUT_PROCESS_FLOW.md) | 输入处理流程        |


### Prompt 定稿 `doc/prompts/`


| 文档                                                                         | 说明                    |
| -------------------------------------------------------------------------- | --------------------- |
| [../doc/prompts/step5_5_prompt.md](../doc/prompts/step5_5_prompt.md)       | Step5.5 输入侧 Prompt 全文 |
| [../doc/prompts/Step5-prompt提示词改造.md](../doc/prompts/Step5-prompt提示词改造.md) | Step5 最小化改造清单         |


运行时 Prompt 以 `admin_config` + 代码默认为准；上表为定稿对照文档。

### 记忆专项 `doc/memory/`

**PRD** — [../doc/memory/prd/](../doc/memory/prd/)

- [PRD-记忆检索与Prompt优化.md](../doc/memory/prd/PRD-记忆检索与Prompt优化.md)
- [PRD-长记忆第一套下线与Step6运营收敛.md](../doc/memory/prd/PRD-长记忆第一套下线与Step6运营收敛.md)

**开发步骤拆解** — [../doc/memory/steps/](../doc/memory/steps/)

- [记忆检索与Prompt优化_开发步骤拆解.md](../doc/memory/steps/记忆检索与Prompt优化_开发步骤拆解.md)
- [长记忆第一套下线与Step6运营收敛_开发步骤拆解.md](../doc/memory/steps/长记忆第一套下线与Step6运营收敛_开发步骤拆解.md)

### 其他（`doc/` 根目录）

- `林小梦_H5产品_PRD_V1.2_修订版.docx`、`林小梦_管理员后台_PRD_V1.3_修订版.docx` — 早期 Word PRD，未纳入上表子目录。

## 仓库根目录


| 文档                           | 说明                 |
| ---------------------------- | ------------------ |
| [../README.md](../README.md) | 项目入口、pytest、E2E 说明 |
| [../DEPLOY.md](../DEPLOY.md) | 部署要点               |


## 目录对照（迁移前 → 现路径）


| 旧路径                                    | 现路径                               |
| -------------------------------------- | --------------------------------- |
| `doc/mem_doc/PRD-*.md`                 | `doc/memory/prd/`                 |
| `doc/mem_doc/*_开发步骤拆解.md`              | `doc/memory/steps/`               |
| `doc/mem_doc/test_report_*.md`         | `docs/testing/reports/`           |
| `doc/mem_doc/*.log`                    | `docs/testing/logs/`              |
| `doc/step5_5_prompt.md` 等              | `doc/prompts/`                    |
| `doc/对话链路*.md`、`INPUT_PROCESS_FLOW.md` | `doc/chat/`                       |
| `docs/chat-refactor-*.md`（除 S4 清单）     | `docs/refactor/chat/`             |
| `docs/diary-refactor-*.md`             | `docs/refactor/diary/`            |
| `docs/test-diary.md`、`tests/*说明*.md`   | `docs/testing/guides/`            |
| `docs/docker-admin-deploy.md`          | `docs/ops/docker-admin-deploy.md` |
