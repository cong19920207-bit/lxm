# -*- coding: utf-8 -*-
# 林小梦 AI 虚拟人 - 后端 Docker 镜像

FROM python:3.11-slim

WORKDIR /app

# asyncmy 在部分架构（如 Apple Silicon）无预编译 wheel，需 gcc 编译
# 国内构建：apt 走阿里云 Debian 镜像，避免 deb.debian.org 超时/极慢
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖（国内构建常用清华 PyPI 镜像，避免访问 pypi.org / files.pythonhosted.org 超时）
COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=120
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

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
