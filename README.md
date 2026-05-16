# 林小梦 AI 虚拟人

陪伴型 AI 虚拟人 H5 产品，包含用户端 H5 和管理后台。

**AI 日记运维**（上海日界与统计窗、手动补跑、门禁）：见 [docs/ops-diary.md](docs/ops-diary.md)。手动批跑与 APScheduler 同源：`PYTHONPATH=. python -m scripts.run_diary_batch`（详见该文档 §3）。

## 开发与测试

- **自动化测试（推荐门禁）**：在项目根执行 `PYTHONPATH=. pytest tests/`，对话与 SSE 契约覆盖见 `tests/test_chat.py` 等。
- **长链路手工脚本（可选）**：`scripts/test_chat_e2e.py` 通过 **HTTP + SSE** 调用已启动的后端（默认 `http://127.0.0.1:8000`，可用环境变量 `CHAT_E2E_BASE_URL` 覆盖），**依赖真实 LLM/Redis/MySQL**，耗时长；**不**作为默认 CI 门禁，仅供本地或运维冒烟。
- **Docker Compose 与本脚本**：`docker-compose.yml` 中 **backend** 使用 `MYSQL_HOST=mysql`（仅容器内有效）。在**宿主机**跑 `pytest scripts/test_chat_e2e.py` 时，请保证根目录 `.env` 里 **`MYSQL_HOST=127.0.0.1`**（及与 compose 中 mysql 一致的端口、库名、账号），使脚本直连的 MySQL 与容器内后端为**同一数据**；否则 `_get_or_create_test_user` 与 `POST /api/auth/login` 会各连各库，表现为登录「用户不存在」。详见脚本文件头注释。
- **多 Tab 行为**：同账号多 Tab 各自独立流式会话，与服务端 timeline 对齐口径见 `**docs/tech-debt.md` → [TD-019]**。

## 文档与契约维护（贡献约定）

- 变更 **接口、数据库字段、SSE/错误码** 等与 `**docs/contract.md`** 相关时，请在同一 PR（或紧随其后的 PR）内更新 `**docs/contract.md`** 对应章节，并将文首 **「最后更新」** 日期改为**合并日或文档修订日**，避免契约与实现长期漂移。

## 技术栈

- **后端**：Python 3.11 + FastAPI + SQLAlchemy（异步）
- **数据库**：MySQL 8.0 + Redis + 阿里云 DashVector
- **核心 LLM**：doubao-seed-1-8-251228（火山引擎）
- **Embedding**：text-embedding-v3（阿里云）
- **前端**：原生 HTML + CSS + JS，移动端 H5
- **定时任务**：APScheduler
- **部署**：阿里云 ECS + Docker + Nginx

## 管理后台初始化步骤

### 步骤 1：启动数据库

```bash
docker-compose up -d
```

### 步骤 2：安装 Python 依赖

确认 `requirements.txt` 中包含 `pymysql`、`python-dotenv`、`bcrypt`、`psutil`、`openpyxl`。

```bash
pip install -r requirements.txt
```

### 步骤 3：启动 FastAPI（自动建表）

启动后等待建表完成，然后 `Ctrl+C` 停止。

```bash
cd backend && python main.py
```

### 步骤 4：写入初始配置数据

```bash
mysql -u root -p你的密码 数据库名 < scripts/init_data.sql
```

### 步骤 5：创建超级管理员账号

```bash
python scripts/init_admin.py
```

### 步骤 6：重新启动服务

```bash
cd backend && python main.py
```

### 步骤 7：访问后台

打开浏览器访问：

```
http://localhost:8000/admin
```

- 账号：`superadmin`
- 密码：`Admin@123456`
- ⚠️ **首次登录后请立即修改密码！**

## 项目结构

```
├── backend/                  # 后端代码
│   ├── main.py              # FastAPI 入口
│   ├── database.py          # 数据库连接
│   ├── config.py            # 配置管理
│   ├── models/              # SQLAlchemy 模型
│   ├── routers/             # API 路由
│   │   ├── admin/           # 管理后台路由
│   │   └── ...              # 用户端路由
│   ├── schemas/             # Pydantic 模型
│   ├── services/            # 业务逻辑
│   ├── utils/               # 工具函数
│   └── tasks/               # 定时任务
├── frontend/                 # 用户端 H5 前端
│   ├── pages/               # 页面
│   └── static/              # 静态资源
├── admin/                    # 管理后台前端
│   ├── pages/               # 页面
│   └── static/              # 静态资源
├── scripts/                  # 运维脚本
│   ├── init_admin.py        # 初始化超级管理员
│   └── init_data.sql        # 初始配置数据
└── requirements.txt          # Python 依赖
```

