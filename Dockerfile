# -*- coding: utf-8 -*-
# 林小梦 AI 虚拟人 - 后端 Docker 镜像

FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（.env 由 docker-compose 通过 env_file 注入，不打包进镜像）
COPY backend/ ./backend/
# 管理后台与用户端静态：与 main.py 中 FileResponse / StaticFiles 路径一致（供直连 :8000 或 nginx 反代 /admin）
COPY admin/ ./admin/
COPY frontend/ ./frontend/

# Alembic：与宿主机相同，可在容器内执行迁移（compose 已注入 MYSQL_HOST=mysql）
COPY alembic.ini .
COPY alembic/ ./alembic/

# 启动命令（docker-compose 会覆盖 MYSQL_HOST/REDIS_HOST）
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
