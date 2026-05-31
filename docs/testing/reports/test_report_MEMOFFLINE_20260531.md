# 长记忆第一套下线与 Step6 运营收敛 · 上线验收报告（STEP-016）

- **生成时间**：2026-05-31
- **范围**：STEP-016 上线前/后运维清理与验收 checklist
- **PRD 来源**：`doc/mem_doc/PRD-长记忆第一套下线与Step6运营收敛.md`（§11 上线与运维检查项）
- **步骤拆解**：`doc/mem_doc/长记忆第一套下线与Step6运营收敛_开发步骤拆解.md`（[STEP-016]）
- **契约文档**：`docs/contract.md`
- **进度文档**：`docs/progress/长记忆第一套下线与Step6运营收敛_progress.md`

> 说明：本环节为「运维执行，非代码改动」。§11.1 数据清理与 §11.2 发布后验收
> 需生产环境 DashVector / MySQL 运维权限及运行实例，须由发布负责人在发布窗口内手动执行并回填本报告；
> §11.3 中可自动化的回归测试已由本仓库测试集实跑验证，证据见下文「三」。

---

## 一、发布前清理 checklist（§11.1，人工执行）

> 前提：发布窗口已确定，DashVector / MySQL 运维权限就绪。**清理前必须先导出备份。**

- [ ] **备份**：导出 MySQL `memory` 表全量数据（业务行）到归档文件
- [ ] **备份**：导出 DashVector 中全部 `doc_id` 以 `mem_` 开头的文档（id 列表 + 内容）到归档文件
- [ ] **清空**：清空 MySQL `memory` 表业务数据（**保留表结构**，禁止 `DROP TABLE` / 删列）
- [ ] **删除**：删除 DashVector 全部 `mem_*` 前缀文档
- [ ] **抽样验证**：任取一个测试用户执行 `list user`，确认结果中无任何 `mem_` 前缀文档

**关键约束（P1）**：列表与召回侧一律**不过滤** `mem_*`。清理完成前可能短暂展示脏数据属已知风险，
靠本环节人工清理收敛，**严禁**在运行时代码中自作主张添加 `mem_*` 过滤（见步骤拆解 §5）。

**不在范围内**：不做代码迁移脚本（M2）；不删 `memory` 表结构（M8）。

---

## 二、发布后验收 checklist（§11.2 八项，人工执行）

| # | 验收项 | 操作 | 预期 | 结果 |
|---|--------|------|------|------|
| 1 | Step6 → Admin 可见 | 真人走一轮对话 | Admin「用户记忆 / 私有状态」Tab 出现本轮新 KV | ☐ |
| 2 | H5 只读 | 打开 H5 `memory.html` | 仅展示只读 KV 列表，无增删改入口；空态文案正确 | ☐ |
| 3 | Prompt 模块5 召回 | 对话含可召回记忆 | Prompt 模块5（用户记忆）注入 Top 命中 | ☐ |
| 4 | Admin 手改同步 | Admin 改某条 value 后再对话 | 改动即时对召回/展示生效 | ☐ |
| 5 | 全局检索 R-01 | Admin「全局用户记忆」按 user_id / 关键词检索 | 返回结果正确；未指定用户时命中上限与 `truncated` 提示正确 | ☐ |
| 6 | Step6 Prompt 保存免重启 | Admin 保存并发布 Step6 Prompt | 免重启，新对话即用新 Prompt（Redis 命中） | ☐ |
| 7 | 新 user 行 `memory_injected=null` | 发新消息后查 `conversation_log` | 新 user 行 `memory_injected` 恒为 `null` | ☐ |
| 8 | Agent 不依赖 `mem_*` | 触发 Agent 主动消息检索 | 仅走 DashVector 向量检索，不依赖 MySQL `memory` 校验、不过滤 `mem_*` | ☐ |

---

## 三、§11.3 回归验证（自动化，已实跑）

执行命令：

```bash
python3 -m pytest \
  tests/test_query_rewrite_service.py \
  tests/test_multi_vector_retrieval_service.py \
  tests/test_step6_vector_upsert.py \
  tests/test_dashvector_upsert_response.py \
  tests/test_dashvector_client.py \
  tests/test_admin_character_knowledge.py \
  tests/test_character_knowledge_validate.py \
  tests/test_prompt_builder.py \
  tests/test_memory_llm_service.py \
  tests/test_step016_step6_orchestrator.py \
  tests/test_h5_static_contract.py -q
```

结果：**130 passed**（2026-05-31，12 条 warning 均为 JWT 测试密钥长度提示，无功能影响）。

| §11.3 回归项 | 覆盖测试 | 结果 |
|--------------|----------|------|
| Step1.5 / Step2 单测 | `test_query_rewrite_service`、`test_multi_vector_retrieval_service` | ✅ |
| Step6 upsert 单测 | `test_step6_vector_upsert`、`test_dashvector_upsert_response`、`test_dashvector_client` | ✅ |
| 角色知识库不受影响 | `test_admin_character_knowledge`、`test_character_knowledge_validate` | ✅ |
| Step6 Prompt 拼装（含异步热配置回退 DEFAULT） | `test_memory_llm_service`（30 项）、`test_step016_step6_orchestrator` | ✅ |
| H5 只读契约 / Prompt 构建 | `test_h5_static_contract`、`test_prompt_builder` | ✅ |

> 「Step1.5/Step2 冒烟」「Admin 发布 Step6 Prompt 后 Redis 命中」需在运行实例上人工冒烟，
> 已并入「二、发布后验收」第 3/5/6 项，由发布负责人执行后回填。

---

## 四、验收结论

- 代码与文档侧（STEP-001~015）已全部落地，契约（`docs/contract.md`）与技术债（`docs/tech-debt.md`）已同步。
- §11.3 可自动化回归 **130 项全部通过**。
- §11.1 数据清理、§11.2 发布后八项验收 **待发布负责人在发布窗口执行并回填本报告对应勾选项**。

---

## 五、待办（发布负责人）

1. 按「一」完成发布前备份 + 清理，逐项打勾。
2. 发布后按「二」逐项验收，逐项回填结果。
3. 全部通过后将本报告状态更新为「已验收」，并归档备份文件路径。
