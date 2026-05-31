# Docker 下验证 Step5.5 / Step6 与 LLM 真实交互

## 思路

项目**没有**单独暴露「只调用 Step5.5」或「只调用 Step6」的 HTTP 接口。与用户端一致的路径是：

`POST /api/chat/send` → 入队 → 防抖打包 → Step1.5 → Step2 → Step5 →（可选）Step5.5 → 落库 / SSE → **异步** `execute_step6`。

因此「接口级」验证 = **对正在跑的 Docker Backend 发对话请求**，再在 **`lxm_backend` 容器日志**里 grep 关键词。

## 前置条件

1. `docker compose up -d`（或等价命令），`lxm_backend` 监听 **`8000`**（见 `docker-compose.yml`）。
2. **账号**：脚本通过 **`/api/auth/register` + `/api/auth/login`** 与 Docker 使用**同一数据库**，无需在宿主机用本地 Python 连 MySQL 建用户。

**（若你坚持用 ORM 在宿主机建用户，则 `.env` 的 `MYSQL_HOST=127.0.0.1` 与 compose 中库一致；否则请直接用本脚本。）**
3. LLM / Embedding 等密钥在容器环境中有效（`.env` 经 `env_file` 注入 backend）。

## 一键发对话（宿主机）

```bash
cd /path/to/lxm_for
export SMOKE_BASE_URL=http://127.0.0.1:8000
python3 scripts/docker_step55_step6_smoke.py --rounds 3
```

（默认会注册/登录用户 **`e2esmoke1` / `pass1234`**，须符合注册规则：用户名为 6～20 位**纯字母数字**，无下划线。）

## 看日志（宿主机）

```bash
docker logs lxm_backend 2>&1 | tail -400 \
  | grep -E 'Step5\.5|Step6 |Step6 完成|Step6 首次失败|重试后仍失败|Step5\.5 执行成功|Step5\.5 LLM|chat/completions|非流式调用'
```

- **Step6**：对话 SSE 正常结束后，一般会看到异步记忆链路相关日志或火山 `chat/completions`（具体文案以当前日志为准）。
- **Step5.5**：只有「总开关打开 + 双门闩命中」才会走润色 LLM；未命中时**不会有** Step5.5 成功类日志，这是产品设计，不是「没连上 LLM」。

## 提高 Step5.5 出现概率（任选）

1. **打开总开关**（`admin_config`，key=`step5_5_enabled`，生效行 `is_active=true`、`is_draft=false`，值可为 `true`）。  
   - 若你们用后台「发布配置」，应以发布为准；若仅改 MySQL，可能还需同步 Redis 热键 `active_config:step5_5_enabled`，或重启 backend 让其按你们实现的加载逻辑回源。
2. **多跑几轮** `docker_step55_step6_smoke.py`（门闩含随机）。
3. **开发期临时调大门闩概率**：仅本地改 `backend/services/step5_5_service.py` 中 `GATE_A_PROBABILITY`（验证完还原）。

## Step6 仍无日志时排查

- 本轮是否 **SSE 失败**（Step5 未成功则通常不入队 Step6）。
- **异步任务尚未执行**：立刻 grep 可能为空，可再加 `sleep 3` 后重试 `docker logs`。
- LLM 超时：日志里多为 `非流式调用失败` / Step6 重试失败。

---

脚本路径：`scripts/docker_step55_step6_smoke.py`。
