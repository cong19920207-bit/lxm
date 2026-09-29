# Docker 环境部署与管理后台访问（增量说明）

本文档描述在**不改动业务代码**前提下，通过 Dockerfile / nginx / compose 增量配置后，如何在 Docker 上跑全栈并访问管理后台。

## 一、架构说明


| 入口                               | 用途                                                                |
| -------------------------------- | ----------------------------------------------------------------- |
| `http://localhost`（nginx **80**） | 用户端 H5 静态（`./frontend`），`/api/` 与 `**/admin`** 反代到 `backend:8000` |
| `http://localhost:8000`（backend） | 直连 FastAPI：管理后台 `/admin`、OpenAPI `/docs` 等                        |


镜像内已包含 `backend/`、`admin/`、`frontend/`、`alembic/` 与 `alembic.ini`，与 `main.py` 中静态路径一致；迁移可在**宿主机**或 **backend 容器内**执行（见下文）。

## 二、一次性准备

1. 复制环境变量：`cp .env.example .env`，按说明填写 **MySQL/Redis/JWT/各云厂商 Key**（`.env` 勿提交仓库）。
2. 确保本机 **3306、6379、80、8000** 未被占用（或与 compose 中端口映射调整一致）。

## 三、启动

```bash
cd /path/to/lxm_for
docker compose build --no-cache backend
docker compose up -d
```

等待 `mysql` 健康后，`backend` 启动时会自动 `create_all_tables()`。**已有库或需要与仓库 DDL 完全一致时**，请在启动业务流量前执行一次 **Alembic**（见「四、库结构迁移」）。

## 四、库结构迁移（Alembic，推荐）

业务迭代中的表结构变更以 **Alembic** 为准（见根目录 `alembic/README.md`）。**MySQL 容器与 `mysql_data` 卷一般无需重建**；在现有库上升级即可。

**方式 A：在 backend 容器内执行**（`MYSQL_HOST=mysql` 已由 compose 注入，无需改 `.env`）

```bash
cd /path/to/lxm_for
# 需已重新构建镜像（Dockerfile 已包含 alembic）
docker compose build backend && docker compose up -d backend
docker compose exec backend alembic upgrade head
```

**方式 B：在宿主机项目根目录执行**

```bash
cd /path/to/lxm_for
# .env 中 MYSQL_HOST 须能连到库：本机映射一般用 127.0.0.1，勿写 mysql（该主机名仅在 compose 网络内有效）
alembic upgrade head
```

若曾用手工 SQL 加过列，按 `alembic/README.md` 使用 `alembic stamp …` 对齐版本，避免重复执行。

## 五、首次初始化数据（每个新库只做一次）

`docker-compose` 会从项目根目录 `**.env**` 读取 `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE` 注入 MySQL 容器，下面命令中的 **用户名、密码、库名请与你的 `.env` 一致**。

在**宿主机**执行：

```bash
# 0）若执行 init_data 报错 Unknown column 'is_draft'：说明库是旧结构，先补列再导入
docker exec -i lxm_mysql mysql -u你的用户 -p'你的密码' 你的库名 < scripts/migrate_admin_config_add_is_draft.sql

# 1）admin_config 等种子数据
docker exec -i lxm_mysql mysql -u你的用户 -p'你的密码' 你的库名 < scripts/init_data.sql

# 2）超级管理员（推荐：走 Docker 网络连「mysql」服务，避免本机 3306 连错库）
bash scripts/init_admin_docker.sh
```

若本机 **未装其它 MySQL**、确定 `127.0.0.1:3306` 就是 Docker 映射端口，也可用：

```bash
pip3 install pymysql bcrypt python-dotenv sqlalchemy
export DATABASE_URL="mysql+pymysql://你的用户:你的密码@127.0.0.1:3306/你的库名"
python3 scripts/init_admin.py
```

（若 `docker exec` 能查到 `admin_users`，但本机 `python3 scripts/init_admin.py` 报表不存在，几乎一定是 **本机 MySQL 占用了 3306**，请用上面的 `init_admin_docker.sh`。）

## 六、验证

- 管理后台（经 nginx）：**[http://localhost/admin](http://localhost/admin)**
- 管理后台（直连后端）：**[http://localhost:8000/admin](http://localhost:8000/admin)**
- 默认超管（`scripts/init_admin.py`）：用户名 `superadmin`，密码 `Admin@123456`（登录后请修改密码）
- **角色知识库（STEP-027）**：登录 `super_admin` 或 `ai_trainer` → 侧栏 **📚 角色知识库**，或 **[http://localhost/admin/pages/knowledge.html](http://localhost/admin/pages/knowledge.html)**。须已在 `.env` 配置 **`DASHVECTOR_API_KEY` / `DASHVECTOR_ENDPOINT` / `DASHVECTOR_COLLECTION_NAME`** 及 Embedding 相关变量，否则列表/写入会失败。

用户端 H5：**[http://localhost/](http://localhost/)**（静态由 nginx 的 `./frontend` 挂载提供；若用户端在**另一容器**，只需把该容器内页面的 API 基地址指到能访问本机的 `http://<宿主机IP>/api` 即可。）

## 七、常见问题

- **502 /admin**：确认 `lxm_backend` 已启动且无报错；`docker compose logs -f backend`。
- **登录 401 / 无超管**：是否已执行 `init_admin.py` 且库为当前 compose 使用的 `lxm`。
- **人格/配置为空**：是否已执行 `init_data.sql`。

## 八、与联调测试的关系

完成「五、首次初始化」后，再按联调清单测登录锁定、人格发布、统计等；Redis 缓存键、端口与清单中 `localhost:8000` 在暴露 `8000:8000` 后保持一致。

## 九、日常更新（本机改代码后）

| 改动范围 | 建议操作 |
| -------- | -------- |
| `backend/`、`requirements.txt`、`Dockerfile` | `docker compose build backend && docker compose up -d backend`；若含**库结构变更**，按「四、库结构迁移」执行 `alembic upgrade head` 后再或同时重建 backend（一般先迁移再发版更稳；新表可先迁移再起服务）。 |
| 仅 `admin/`（页面/菜单/静态，经 **/admin** 访问） | compose 已将 **`./admin` 挂载到 backend `/app/admin`**，保存后 **刷新浏览器** 即可；若未挂载或生产镜像无卷，则须 **build backend**。 |
| 仅 `frontend/`（用户经 **http://localhost** 访问） | `./frontend` 为 **挂载**，保存文件后强刷浏览器即可，**不必**重建 backend。 |
| 直连 **:8000** 且依赖镜像内静态 | 改 `frontend/` 进镜像须 **build backend**；`admin/` 在本地 compose 下通常已挂载。 |
| STEP-027 角色知识库等新 API | **无 Alembic**；确保 `.env` 中 DashVector/Embedding 已填，**build backend** 一次即可。 |
| `nginx/nginx.conf` | `docker compose restart nginx`。 |
| `.env` | `docker compose up -d backend`（必要时相关服务）使容器载入新环境变量。 |
| MySQL / Redis | **不必**为常规业务发版重建；数据在命名卷中。仅调整 compose 中 MySQL 配置或换大版本时再处理，且须备份。 |

查看当前栈：`docker compose ps`；看后端日志：`docker compose logs -f backend`。

## 十、P1 实时语音在本地 Docker 的凭据与后台入口

P1 后端从容器环境读取 `DOUBAO_S2S_APP_ID` 和 `DOUBAO_S2S_ACCESS_KEY`；`DOUBAO_S2S_APP_KEY` 可留空，代码会使用协议默认值。将实际值填写到项目 `.env`，不要写入后台语音配置、文档或仓库。`.env.example` 只是模板，不会自行向已运行容器注入新值；其他文本 LLM 凭据变量也不能替代这两个 P1 变量。

仅修改 `.env` 后，重建后端容器使环境变量生效：

```bash
docker compose up -d --no-deps --force-recreate backend
docker compose exec -T backend sh -c 'test -n "$DOUBAO_S2S_APP_ID" && test -n "$DOUBAO_S2S_ACCESS_KEY"'
```

第二条命令只检查非空，不打印密钥。若还修改了 `backend/` 代码，先按「九、日常更新」构建后端镜像；单纯补凭据不需要数据库迁移。

语音总开关的后台入口为 **语音通话 → 总开关**。开关独立生效，不发布“语音设置”中的其他草稿；开启前会检查已发布语音设置及其 `credential_ref` 指向的环境变量。开启后仍按已发布的维护、软停止、开放范围配置决定是否接受新通话。相关已完成行为记录在 [P1 人工验收临时契约增量](../design/realtime_voice/P1/execution/contract-drafts/P1-本地Docker人工验收已完成变更增量-20260927.md)。

### 本机语音 WebSocket 联调

仅在开发机本机人工验收语音时，叠加 `docker-compose.voice-local.yml` 启动；该文件要求 Docker Compose **2.24.4 或更新版本**，使用 `ports: !override` 将 **nginx 的 80 端口和 backend 的 8000 端口**绑定到 `127.0.0.1`，并为 backend 设置 `VOICE_ALLOW_INSECURE_LOCAL=1`。MySQL、Redis 的端口映射不受此叠加文件影响。页面从 `http://127.0.0.1/` 访问；`nginx/nginx.conf` 的 `/api/voice/` 入口将语音 HTTP、首次连接与重连的 WebSocket 一并转发到同一个 backend，并保留浏览器访问的 Host 及 WebSocket Upgrade 头。

```bash
docker compose -f docker-compose.yml -f docker-compose.voice-local.yml up -d --build backend nginx
docker compose -f docker-compose.yml -f docker-compose.voice-local.yml ps
```

本机同源访问时，未设置 `VOICE_ALLOWED_ORIGINS` 也会按浏览器 Origin 与请求 Host 校验；若显式设置该白名单，则以白名单为准。改动叠加文件、端口映射或 `VOICE_ALLOW_INSECURE_LOCAL` 后，仍须同时指定两个 compose 文件并重建对应容器，例如 `docker compose -f docker-compose.yml -f docker-compose.voice-local.yml up -d --force-recreate backend nginx`；`docker compose start` 不会应用新配置。上文单文件 compose 命令只适用于未启用本机语音叠加文件的部署。

`VOICE_ALLOW_INSECURE_LOCAL=1` 只供回环地址上的本机联调，不适用于云服务器。云端入口需由 HTTPS/WSS 反向代理提供，并让后端从可信代理正确识别 WebSocket 协议；当前仓库内的 nginx 配置只监听 HTTP 80，不能直接作为云端 TLS 入口。不要将本机叠加文件用于线上部署。
