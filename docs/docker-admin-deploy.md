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
| `backend/`、`admin/`、`requirements.txt`、`Dockerfile` | `docker compose build backend && docker compose up -d backend`；若含**库结构变更**，按「四、库结构迁移」执行 `alembic upgrade head` 后再或同时重建 backend（一般先迁移再发版更稳；新表可先迁移再起服务）。 |
| 仅 `frontend/`（用户经 **http://localhost** 访问） | `./frontend` 为 **挂载**，保存文件后强刷浏览器即可，**不必**重建 backend。 |
| 直连 **:8000** 且依赖镜像内静态 | 与改 `frontend/` 进镜像一致，需 **build backend**。 |
| `nginx/nginx.conf` | `docker compose restart nginx`。 |
| `.env` | `docker compose up -d backend`（必要时相关服务）使容器载入新环境变量。 |
| MySQL / Redis | **不必**为常规业务发版重建；数据在命名卷中。仅调整 compose 中 MySQL 配置或换大版本时再处理，且须备份。 |

查看当前栈：`docker compose ps`；看后端日志：`docker compose logs -f backend`。