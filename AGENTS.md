# 仓库文档读取边界

- 普通文档整理、需求分析、代码实现和 LLM 检索任务不得扫描 `.doc-migration-baseline/`。
- 仅当用户明确要求进行迁移核验、恢复、生成新快照或删除基线时，才允许按精确路径读取该目录。
- 默认文档入口为 `docs/INDEX.md` 与 `docs/llm-manifest.json`；只读取 manifest 白名单中的当前权威文档。
- `docs/contract/history/`、`docs/design/realtime_voice/P1/history/`、`docs/contract/drafts/`、`docs/tech-debt/archive/` 和迁移基线均不是默认权威来源。
- 普通文档整理、需求分析、代码实现和 LLM 检索任务不得读取 `docs/design/realtime_voice/P1/history/`；仅当用户明确要求历史核验、版本对比或恢复时，才允许按精确路径读取。
- 未经用户明确指令，禁止删除、覆盖或重写任何既有迁移快照。
