# AI 日记 — 自动化测试方案

本文说明 **H5 客户端（契约层）** 与 **管理后台（API 层）** 的自动化测试范围、分层策略与运行方式。实现代码见仓库 **`tests/test_diary.py`**。

---

## 1. 测试分层

| 层级 | 目标 | 工具 | 说明 |
|------|------|------|------|
| **L1 纯函数** | `diary_rules_loader` 解析/回退 | `pytest` | 不启动 HTTP、不连真实 MySQL/Redis |
| **L2 API（推荐 CI）** | `/api/diary/*`、`/api/admin/diary-*` | `pytest` + `httpx.AsyncClient` + SQLite 内存库 | 与 `tests/test_auth.py` 同构：`get_db` 覆盖 + 启动期依赖打桩 |
| **L3 浏览器 E2E（可选）** | `diary.html`、`diary-rules.html`、`diary-history.html` 真实交互 | Playwright / Cypress | 需起后端 + 静态资源 + 测试账号；本仓库**未默认引入**，可在有前端 CI 时补 |

当前交付：**L1 + L2**（`tests/test_diary.py`）+ 下文 **手工/脚本冒烟**。

---

## 2. L2 环境说明（必读）

- **SQLite 内存库**：仅路由里 `Depends(get_db)` 的请求走测试库；`admin_config_service.get_active_config(use_cache=True)` 在缓存未命中时会走**全局** `async_session_maker`（生产库）。**`tests/test_diary.py`** 在 **`autouse` fixture** 里将 **`admin_config_service.get_active_config` 默认打桩为 `None`**，避免误连生产库；单测 **`test_get_rules_with_stub_config`** 再覆盖为固定字典。
- **用户 JWT**：`get_current_user` 会 **`await get_redis().get("user_banned:…")`**，无 Redis 时测试失败。同一 **`autouse`** 内对 **`backend.utils.auth_middleware.get_redis`** 与 **`backend.services.admin_config_service.get_redis`** 返回 **内存 AsyncMock**（`get` → `None`，`setex` → 成功）。
- **启动生命周期**：`main.lifespan` 会执行 `create_all_tables`、`get_scheduled_diary_cron_times`、`start_scheduler(...)`。测试中 **`monkeypatch`**：`create_all_tables` → **AsyncMock**，`get_scheduled_diary_cron_times` → 固定 **`(0, 30)`**；**`backend.tasks.scheduler.start_scheduler` 接受 `*a, **k`**，与现网 `lifespan` 关键字参数一致。
- **Python 依赖**：运行全量 `pytest` 需 **`pip install -r requirements.txt`**（含 **`psutil`** 等，`main` 导入监控路由时会用到）。

---

## 3. L2 用例清单（与契约对齐）

### H5（用户 JWT）

- `GET /api/diary/list`：`code==0` 时 `data` 含 **`items` / `total` / `page` / `page_size`**，且 **无 `diaries` 键**。
- 插入 `ai_diary` 后列表字段与分页基本行为。
- `POST /api/diary/{id}/read`：成功；错误 id 返回 **`ERR_DIARY_NOT_FOUND`（10300）**。

### 管理端（Admin JWT）

- `GET /api/admin/diary-history`：**`super_admin` / `ops_admin`** 可访问，返回 **`data.list` / `total` / `page` / `page_size`**。
- **`ai_trainer`** 访问日记历史 → **HTTP 403**（与 `require_role` 一致）。
- `PUT /api/admin/diary-rules`：缺少 Prompt 时 **`ADMIN_ERR_DIARY_RULE_PARAM_INVALID`（20034）**；合法 Body + Mock Redis 时 **`code==0`**。

### L1 `diary_rules_loader`

- 仅 `generation_prompt` 时两套模板一致；非法 `generation_hour` 回退 **0:30（UTC 语义由调度层消费）**。

---

## 4. 运行方式

```bash
cd /path/to/lxm_for
pip install -r requirements.txt   # 含 pytest、pytest-asyncio、httpx、aiosqlite 等
PYTHONPATH=. pytest tests/test_diary.py -v
```

仅跑某一类：

```bash
PYTHONPATH=. pytest tests/test_diary.py -v -k "DiaryH5"
PYTHONPATH=. pytest tests/test_diary.py -v -k "DiaryRulesLoader"
```

---

## 5. 手工 / 脚本冒烟（联调、预发）

适合 **真实 MySQL + Redis** 环境，验证 JWT 与网关路径（与自动化互补）。

1. 用户登录取 `token`，请求 `GET /api/diary/list?page=1&page_size=20`，检查 JSON 中 **`items`**。
2. 管理员登录取 `admin_token`，请求 `GET /api/admin/diary-history?page=1&page_size=20`。
3. `PUT /api/admin/diary-rules` 提交双 Prompt（见 `docs/contract.md` `DiaryRulesRequest`），然后 **重启 backend**，看日志中 **每日日记下次执行（UTC）** 是否与配置一致。

可将上述步骤写成 `curl` 序列，使用环境变量 `BASE_URL`、`USER_TOKEN`、`ADMIN_TOKEN`；若需要可再增加 `scripts/smoke_diary.sh`（按需自行拷贝 env 模板）。

---

## 6. 可选扩展（L3）

- **Playwright**：打开 `/pages/diary.html`（需先注入登录态或走完整登录页），断言列表容器、触底加载、`no-more` 文案；后台 `diary-rules.html` 双文本域保存 Toast。
- **生成链路**：`generate_diary_for_user` 依赖 LLM，不适合默认放进 CI；可在 **预发** 用运维文档 **`docs/ops-diary.md`** 中的手动批跑做验收。

---

## 7. 与产品/契约的追溯

- H5 列表字段：`docs/contract.md` → **模块：H5 日记** → `GET /api/diary/list`。
- 管理端：`DiaryRulesRequest`、`GET /api/admin/diary-history`、页面 **`diary-rules.html` / `diary-history.html`** 见同一契约文档。
