# 页面「小梦暂时无法回复」问题诊断报告

## 一、问题现象

- **脚本** `test_chat_e2e.py`：可正常跑通 20 轮对话
- **页面** `127.0.0.1/pages/chat.html`：持续提示「小梦暂时无法回复，请稍后再试」

## 二、结论概述

「小梦暂时无法回复」对应后端返回 `ERR_LLM_FAILED`，说明**请求已到达后端**，且后端在 **步骤1** 或 **步骤3** 抛出了异常。

脚本与页面的差异在于：

- 脚本：直接调用 Python 函数，使用 `e2e_test_user`，不走 HTTP
- 页面：通过 HTTP 调用 `/api/chat/send`，使用当前登录用户的 JWT

## 三、错误产生位置（backend/routers/chat.py）


| 位置     | 行号      | 触发条件                     | 日志关键字                               |
| ------ | ------- | ------------------------ | ----------------------------------- |
| 步骤1 失败 | 338-340 | `asyncio.gather` 中任一步抛异常 | `步骤1并行任务失败: user_id=%d, error=%s`   |
| 步骤3 失败 | 371-373 | `build_chat_prompt` 抛异常  | `Prompt 拼装失败: user_id=%d, error=%s` |


## 四、步骤1 可能失败的子任务

1. `_get_recent_conversations`：查 MySQL `conversation_log`
2. `_get_relationship`：查 MySQL `relationship`
3. `_get_latest_emotion`：查 MySQL `emotion_log`
4. `_get_embedding`：调阿里云 Embedding API

## 五、步骤3 可能失败的原因

- `_build_persona_prompt`：Redis 或 MySQL 查 `admin_config`
- `_build_relationship_prompt`：处理 `relationship_info`（正常可处理 None）
- `_build_memory_prompt` / `_build_recent_chat` 等：Token 裁剪逻辑
- `tiktoken` 加载：`cl100k_base` 编码器首次加载

## 六、API_BASE 与 127.0.0.1 的关系（frontend/static/js/api.js）

```javascript
API_BASE = (hostname === 'localhost' && port not in ['80','443',''])
  ? 'http://localhost:8000'
  : ''
```

- 访问 **127.0.0.1** 时：`hostname !== 'localhost'` → `API_BASE = ''` → 请求发往**当前页面同源**
- 访问 **localhost:8000** 等非 80/443 端口：`API_BASE = 'http://localhost:8000'` → 请求发往 `localhost:8000`

若访问 127.0.0.1，需保证当前页面的服务（如 Nginx）已将 `/api/` 代理到后端，否则会 404，但会显示「回复失败，请重试」而非「小梦暂时无法回复」。

## 七、脚本与页面执行路径差异


| 维度          | 脚本                  | 页面                           |
| ----------- | ------------------- | ---------------------------- |
| 用户          | 固定 `e2e_test_user`  | JWT 解析的当前用户                  |
| 运行环境        | 本机 Python 进程        | 后端服务（可能为 Docker）             |
| DB/Redis 连接 | `.env` 中的 127.0.0.1 | 若用 Docker，为 mysql / redis 容器 |
| 外部 API      | 本机出网                | 容器出网（可能受网络策略影响）              |
| Scheduler   | 被 Mock，不启动          | 正常启动                         |


## 八、建议排查步骤

### 1. 查看后端日志（最重要）

```bash
# 若用 Docker Compose
docker logs lxm_backend 2>&1 | tail -100

# 若直接运行 uvicorn
# 在终端中查看 uvicorn 输出
```

在页面发送消息后，查找：

- `步骤1并行任务失败`
- `Prompt 拼装失败`

根据日志中的 `error=%s` 可确定具体异常。

### 2. 确认请求是否到达正确后端

在页面打开开发者工具 (F12) → Network → 发送消息，检查：

- 请求 URL：是否为 `/api/chat/send` 且目标正确
- 状态码：200 表示后端返回了 JSON 错误
- Response：是否为 `{"code": 10102, "message": "小梦暂时无法回复，请稍后再试"}`

### 3. 对比访问方式

- 用 `http://localhost/pages/chat.html` 或 `http://localhost:8000/...`（若后端提供静态）再试一次
- 确认登录账号：是否为 `e2e_test_user`，或换成该账号测试

### 4. 确认运行环境

- 若使用 Docker：检查 backend 容器对阿里云、火山引擎、DashVector 的出网是否正常
- 环境变量：`.env` 中的 `VOLC_SECRET_KEY`、`ALIYUN_ACCESS_KEY_SECRET` 等是否在容器内正确生效

## 九、总结

后端在处理页面请求时，在步骤1 或 步骤3 抛出了异常并返回 `ERR_LLM_FAILED`，前端据此展示「小梦暂时无法回复」。  
**需要根据后端日志中的具体异常信息继续定位。**