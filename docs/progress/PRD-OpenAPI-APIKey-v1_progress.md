# PRD-OpenAPI-APIKey-v1 开发进度追踪

> 文档路径：`docs/progress/PRD-OpenAPI-APIKey-v1_progress.md`
> 创建时间：2026-06-04
> PRD 来源：`docs/design/PRD-OpenAPI-APIKey-v1.md`（v1.9）
> 契约文档：`docs/contract.md`

---

## 进度总览

| 完成数 | 总环节数 | 完成率 |
|-------|---------|-------|
| 16 | 16 | 100% |

---

## 环节进度明细

| 环节编号 | 功能名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| STEP-000 | 开发前依赖梳理 | ✅ | 2026-06-04 | prompt_mgmt、tests 依赖 chat._build_round_context |
| STEP-001 | OPEN_API_PEPPER | ✅ | 2026-06-04 | config + lifespan |
| STEP-002 | user_api_keys ORM | ✅ | 2026-06-04 | |
| STEP-003 | open_api_auth | ✅ | 2026-06-04 | 401 三场景 |
| STEP-004 | 10108 | ✅ | 2026-06-04 | |
| STEP-005 | check_* 抽取 | ✅ | 2026-06-04 | chat_service |
| STEP-006 | 写路径搬迁 | ✅ | 2026-06-04 | Future/enqueue/await |
| STEP-007 | timeline_read_service | ✅ | 2026-06-04 | |
| STEP-008 | H5 回归接入 | ✅ | 2026-06-04 | _sse_chat_wait_bundle 保留 |
| STEP-009 | open_chat_service | ✅ | 2026-06-04 | |
| STEP-010 | Open chat 路由 | ✅ | 2026-06-04 | |
| STEP-011 | open_agent | ✅ | 2026-06-04 | |
| STEP-012 | Admin Key API | ✅ | 2026-06-04 | |
| STEP-013 | Admin UI | ✅ | 2026-06-04 | user-detail 账号管理 Tab |
| STEP-014 | open-api-v1.md | ✅ | 2026-06-04 | |
| STEP-015 | contract/tech-debt/nginx | ✅ | 2026-06-04 | |

---

## STEP-000 依赖清单

| 引用方 | 符号 |
|--------|------|
| `backend/routers/admin/prompt_mgmt.py` | `_build_round_context`（本期不迁） |
| `tests/test_step018_round_context.py` | `_build_round_context`、`chat_send` 静态检查 |
| `tests/test_chat.py` 等 | `_detect_persona_risk`、`_persist_bundle_success` 等（不迁） |
| `backend/main.py` | `router` |

**禁止**：`chat_service` → `routers.chat`（已满足；bundle 通过 `run_bundle` 回调注入）。

---

## 契约更新记录

| 日期 | STEP | 更新内容 | 契约文档位置 |
|------|------|---------|------------|
| 2026-06-04 | STEP-015 | Open API v1 模块 + user_api_keys 表 | `docs/contract.md` |
