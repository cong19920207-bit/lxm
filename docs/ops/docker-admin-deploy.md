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

### 代理自动发现与总开关页连接诊断（2026-10-16）

本次源码将代理信任交给应用自动管理，不需要在 `.env` 保存 nginx 容器IP。前提是 nginx 与 backend 共享 Docker 网络，代理服务可用固定服务名 `nginx` 解析；后端服务名保持 `backend`。应用每5秒解析 nginx，新来源可提前刷新；失败时清空信任，成功后自动恢复。正常容器重启并不一定改变IP；重建导致IP变化也无需人工粘贴。已经断开的通话仍按既有重连规则处理。

部署此版本必须一起保留以下源码配置（本轮只做本地验证，尚未应用线上）：

- 新后端镜像及 Dockerfile 的 `--no-proxy-headers`。若发布文件覆盖了 `command`，也要带此参数；不能让外层Uvicorn提前按旧环境变量修改连接来源，再交应用校验。旧 `FORWARDED_ALLOW_IPS` 在此启动方式下不再使用，可在后续授权部署中移除。
- Nginx使用 `resolver 127.0.0.11 valid=5s ipv6=off`、`resolver_timeout 2s` 和变量形式的 `proxy_pass $backend_endpoint`，其中 `$backend_endpoint` 为 `http://backend:8000`，不附加URI；保留浏览器Host端口、原始Origin、Upgrade/Connection和正确的 `X-Forwarded-Proto`。这同时解决独立重建backend后的旧IP缓存问题。
- 线上外部挂载的HTTPS配置需要同步以上代理段，并覆盖整个 `/api/voice/`，包含 `/api/voice/diagnostics/stream`；不能仅更新仓库的HTTP配置后声称线上已生效。生产backend仍只允许内网/回环访问。
- 发布时打包新的总开关HTML及 `voice-transport-admin.js`。本轮没有数据库迁移，不需要为此修改MySQL数据。

检查入口是 **语音通话 → 总开关 → 语音连接诊断**。五角色可读；超管/运维可“重新检测”。检测使用独立30秒单次票据和Redis临时结果，校验浏览器到语音入口的握手及消息往返，不消耗通话额度或访问模型。结果超过60秒、进程或信任版本变化后需重测；DNS成功不等于真实通话成功。解析失败检查共享网络及nginx服务；来源/协议失败检查Host、HTTPS与代理转发；无完整结果检查Upgrade及Redis。

验证命令（只创建临时测试容器并清理，不操作现有业务容器；临时容器不注入项目 `.env`，不使用真实凭据）：

```bash
MEMORY_RUNTIME_ENVIRONMENT_ID='' .venv-step001/bin/python -m pytest -q tests/test_proxy_discovery.py tests/test_voice_transport_diagnostics.py tests/test_realtime_voice_master_switch.py
RUN_VOICE_NGINX_RUNTIME=1 MEMORY_RUNTIME_ENVIRONMENT_ID='' .venv-step001/bin/python -m pytest -q -s tests/test_voice_transport_discovery_runtime.py tests/test_realtime_voice_nginx_runtime.py tests/test_realtime_voice_transport_proxy_runtime.py
```

第一条中的空环境标记只隔离历史SQLite开关测试与本机记忆维护围栏，不用于业务容器。Docker验收强制占用旧IP再重建nginx/backend，验证地址确实变化、旧信任撤销、新连接恢复、伪造转发/错误Origin拒绝，并用独立Chrome测试真实TLS诊断及失败路径。测试使用本机生成的证书；真实云端证书、Provider、麦克风及实际语音会话不属于这组验证。

本地交付记录（2026-10-16）：

- 自动发现及诊断单元/API共15项通过；原Origin与网关回归81项、独立总开关17项通过。最初开关SQLite夹具受本机环境中的记忆维护标记影响，在测试进程隔离该标记后17项通过；业务容器的标记始终保留。
- 3项隔离Docker运行测试通过：既有HTTP Upgrade/TLS守卫回归，以及新增真实IP变化、Redis单次票据与浏览器诊断。新增测试实测Nginx各worker在5秒TTL内可能暂时保留旧地址，因此等待该明确窗口后验证恢复，不声称重建全程无断线。
- Chrome验证真实TLS握手及消息往返、故障注入后的非绿色结果、DNS/Redis失败及过期提示、五角色权限；原总开关浏览器回归通过。隔离环境测试资源已清理。
- 首次交付时本地 `lxm_backend` 更新为 `lxm_for-backend:voice-transport-20261016-1f6a0d46c27d`，当时 `lxm_for-backend:latest` 同步指向该版本。仅在原运行镜像上加入本次入口与两个模块；核对修改前main与原容器一致，环境变量逐项一致，端口/网络/挂载不变。Nginx已reload，日志确认 `proxy.discovery state=ready`，新鉴权路由返回预期401，新页面已加载。更新前无活跃通话。后续本地版本见下方F1/F2修复记录。
- 原运行镜像 `lxm_for-backend:bm25-status-20261015-a5fdb205592f` 保留；本次临时本地部署和回退配置位于 `/private/tmp/lxm-voice-transport-deploy/`（含凭据的配置权限600，不入库、不输出）。常规重新构建仍使用仓库Dockerfile及本机语音Compose叠加配置。
- 初次交付时用户浏览器未登录本地后台，未借用或生成真实管理员凭据；完整诊断UI流程在隔离Chrome环境验证，真实接通证据于下述用户验收补齐。没有修改线上；后续线上部署需单独授权，并同步外部挂载的HTTPS配置、后端启动参数和静态资源。

用户真实接通验收补记（2026-10-16，核验起始时间北京时间15:42）：

- **状态：本地修复完成，真实接通冒烟验收通过；线上待部署、待验收。** 用户反馈刚刚尝试可以接通，已只读核对本地Docker日志及通话表元数据，与本轮运行版本一致。
- 通话 `3a72182e-8500-4a97-9ac0-2e33266a7c7f`：数据库UTC时间转换为北京时间，14:57:31创建，14:57:38接通，14:57:42结束；`status=ended`、`duration_seconds=4`、`end_reason=user_hangup`，存在Provider会话标识（未读取或记录标识值）。
- Docker日志确认该call的WebSocket `[accepted]`，并出现 `voice.call01.ringing_result.connected=1`、`voice.call01.provider_ready_order.before_target=1`、`ringing → connected → ended`、`voice.ws.close_reason.user_hangup=1`。这补齐了真实接通及主动挂断证据，不只是诊断握手通过。
- 核验时backend仍为上述 `voice-transport-20261016-1f6a0d46c27d` 镜像，backend/nginx均running，容器RestartCount均为0；代理发现日志为ready。
- 本次只读核验、更新本记录，没有修改业务数据或线上配置。4秒短通话只支持接通与主动挂断验收，不扩展为长通话、完整双向音频质量或线上HTTPS实服验收。

契约门禁F1/F2修复与复查（2026-10-16）：

- F1已修复：三个诊断HTTP接口统一使用 `ApiResponse.ok(data)`，返回 `code/data/message`，保留 `Cache-Control: no-store`；权限、状态码和WebSocket帧格式保持。新增三类响应的回归断言，修复前均因缺少message失败，修复后通过。
- F2已修复：manifest补入 `voice_transport.py`、`proxy_discovery.py`、`voice-transport-admin.js` 的权威归属；新增三条HTTP路由覆盖登记，HTTP登记计数为278；说明业务首连、重连与诊断共3条WebSocket，不计入HTTP。同步main.py中五个既有路由的当前行号，未更改这些路由实现。
- 本轮命令 `PYTHON_DOTENV_DISABLED=1 MEMORY_RUNTIME_ENVIRONMENT_ID='' .venv-step001/bin/python -m pytest -q tests/test_voice_transport_diagnostics.py tests/test_proxy_discovery.py --tb=short`：18通过，1条Starlette既有弃用警告。测试不读取项目.env，不访问真实数据库、Provider或线上。
- 定向覆盖验证：本次涉及的8条HTTP源码位置与登记完全一致；登记计数、覆盖表、接口正文及三个代码归属一致，已证明其他既有manifest数据未被覆盖。只调用既有扫描器的源码扫描函数，没有调用读取迁移基线的全量文档检查。
- 全仓旧源码扫描仍报告范围外9个缺项和27个失效位置；对照本轮修改前manifest，已确认这些差异预先存在且不由F1/F2修复引入。本轮不扩修、不宣称全仓文档校验通过。
- 已同步到本地 `lxm_for-backend:voice-response-20261016-c37ba43e28d6`，`lxm_for-backend:latest` 指向该版本。只在原本地镜像上替换诊断路由模块，确认环境逐项不变、更新前无活跃通话、鉴权路由就绪，并在运行容器中核实标准响应。未重启Nginx；回退镜像仍保留，权限600的本地部署/回退配置位于 `/private/tmp/lxm-voice-response-deploy/`，不入库。
- 最后以 `contract-change-review` 只读复查上述修复范围：七项通过，必须修0、待验证0、建议项0，门禁通过。未受本轮影响的TLS/容器IP变更/浏览器及用户真实接通证据复用前述结果；未重新发起真实通话，线上未改动、仍待单独部署验收。

GitHub提交范围说明（2026-10-16）：本次语音修复沿用 `codex/deploy-memory-v32-20261015`，基于其既有提交 `1f3b028` 合入。其他本地未提交工作保留。上文278条HTTP登记及旧扫描差异是完整本地工作区的验证事实；本次提交不一并推送其他待整理契约，本分支新增3条HTTP诊断路由后登记为261条，以本分支manifest与覆盖表为准。推送源码不代表线上部署。
