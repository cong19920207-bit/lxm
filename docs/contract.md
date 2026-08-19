# 契约文档兼容入口

- 文档 ID：`contract-index`
- 权威状态：`canonical`（只负责路由；规则正文以 `contract/current/` 为准）
- 最后迁移：2026-07-19
- 最后更新：2026-08-19（以代码为准勘误：错误码 20053–20070、Liblib 看板含 observer、覆盖表 199 路由、known-gaps 过时条目）
- 机器入口：[llm-manifest.json](llm-manifest.json)

原单文件正文已无损保存在 `.doc-migration-baseline/snapshots/2026-07-19/contract.original.md`。该基线不参与默认扫描，未经用户明确要求不得读取、覆盖或删除。

## 按功能路由

| 功能 | 当前权威文档 |
|---|---|
| `shared-conventions` | [conventions.md](contract/current/_shared/conventions.md) |
| `shared-auth-rbac` | [auth-rbac.md](contract/current/_shared/auth-rbac.md) |
| `core-user-auth` | [data.md](contract/current/core-user-auth/data.md)、[api.md](contract/current/core-user-auth/api.md) |
| `h5-app` | [api.md](contract/current/h5-app/api.md) |
| `chat-emotion` | [data.md](contract/current/chat-emotion/data.md)、[api.md](contract/current/chat-emotion/api.md) |
| `memory-knowledge` | [data.md](contract/current/memory-knowledge/data.md)、[api.md](contract/current/memory-knowledge/api.md)、[admin-ui.md](contract/current/memory-knowledge/admin-ui.md) |
| `diary` | [data.md](contract/current/diary/data.md)、[api.md](contract/current/diary/api.md)、[admin-ui.md](contract/current/diary/admin-ui.md) |
| `relationship` | [data.md](contract/current/relationship/data.md)、[api.md](contract/current/relationship/api.md)、[admin-ui.md](contract/current/relationship/admin-ui.md) |
| `agent-future` | [data.md](contract/current/agent-future/data.md)、[api.md](contract/current/agent-future/api.md)、[admin-ui.md](contract/current/agent-future/admin-ui.md) |
| `persona-prompt-world-state` | [data.md](contract/current/persona-prompt-world-state/data.md)、[api.md](contract/current/persona-prompt-world-state/api.md)、[admin-ui.md](contract/current/persona-prompt-world-state/admin-ui.md) |
| `life-feed` | [data.md](contract/current/life-feed/data.md)、[api.md](contract/current/life-feed/api.md)、[admin-ui.md](contract/current/life-feed/admin-ui.md) |
| `admin-security-accounts` | [data.md](contract/current/admin-security-accounts/data.md)、[api.md](contract/current/admin-security-accounts/api.md) |
| `observability-third-party` | [api.md](contract/current/observability-third-party/api.md)、[admin-ui.md](contract/current/observability-third-party/admin-ui.md) |
| `openapi` | [data.md](contract/current/openapi/data.md)、[api.md](contract/current/openapi/api.md) |

## 非默认来源

- [已知缺口](contract/known-gaps.md)：代码与契约差异、待确认项。
- `contract/history/`：历史发布摘要与实施日志，`authority=false`。
- `contract/drafts/`：草案，`authority=false`。
- [技术债索引](tech-debt.md)：37 个编号的状态与详情路由。

## 维护规则

当前功能变更只更新 `contract/current/`、`tech-debt/active/` 与 manifest。历史文件只有在用户明确要求时才人工勘误；生成旧版单文件时必须创建新日期快照，不能覆盖旧快照。
