# 林小梦 AI 虚拟人 - Docker 部署说明

## 一、本地 Docker 启动

### 1. 准备环境变量

复制 `.env.example` 为 `.env` 并填写实际值：

- MySQL / Redis：Docker 部署时 `MYSQL_HOST`、`REDIS_HOST` 会被 compose 自动覆盖为 `mysql`、`redis`，无需在 `.env` 中填写
- JWT、火山引擎、阿里云等：按 `.env.example` 说明配置

### 2. 启动服务

```bash
docker-compose up -d --build
```

### 3. 访问

- 前端：[http://localhost](http://localhost)
- 首次启动时，Backend 会自动执行 `create_all_tables` 建表

---

## 二、云端部署

1. 将项目上传至云服务器
2. 按生产环境修改 `.env`：
  - 若使用 compose 内的 MySQL/Redis，`MYSQL_HOST`、`REDIS_HOST` 会被覆盖，可不改
  - 若使用云数据库 RDS，需在 compose 的 `backend` 服务中覆盖 `environment`，或在 `.env` 中填写 RDS 地址
  - `CORS_ORIGINS` 建议改为实际前端域名，如 `https://your-domain.com`
3. 执行：`docker-compose up -d --build`
4. **HTTPS**：当前为 HTTP。生产环境需在 Nginx 中配置 SSL 证书（如 Let's Encrypt），或通过前置负载均衡/网关启用 HTTPS

---

## 三、80 端口占用

若本地 80 端口已被占用，可修改 `docker-compose.yml` 中 nginx 的 `ports`，例如：

```yaml
ports:
  - "8080:80"
```

访问时使用 [http://localhost:8080](http://localhost:8080)