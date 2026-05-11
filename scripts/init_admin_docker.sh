#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# 在宿主机执行：通过 Docker 网络直连 compose 中的 MySQL 服务名「mysql」，
# 避免本机 127.0.0.1:3306 连到「本机安装的 MySQL」而非容器内的库。
#
# 用法（在项目根目录）：
#   bash scripts/init_admin_docker.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker ps --format '{{.Names}}' | grep -qx 'lxm_mysql'; then
  echo "❌ 未找到运行中的容器 lxm_mysql，请先: docker compose up -d mysql"
  exit 1
fi

NET="$(docker inspect lxm_mysql --format '{{json .NetworkSettings.Networks}}' | python3 -c 'import sys,json; print(list(json.load(sys.stdin).keys())[0])')"
if [[ -z "${NET}" ]]; then
  echo "❌ 无法解析 lxm_mysql 所在 Docker 网络"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "❌ 项目根目录缺少 .env"
  exit 1
fi

echo "ℹ️  使用网络「${NET}」，主机 mysql:3306（与 backend 容器一致）"

# pip 使用清华镜像，避免国内 ECS 访问 files.pythonhosted.org 超时（与 Dockerfile 策略一致）
docker run --rm \
  --network "${NET}" \
  -v "${ROOT}:/work" \
  -w /work \
  --env-file "${ROOT}/.env" \
  -e MYSQL_HOST=mysql \
  -e DATABASE_URL= \
  -e PIP_DEFAULT_TIMEOUT=120 \
  python:3.11-slim bash -c \
  'pip install -q --upgrade pip && \
   pip install -q \
     -i https://pypi.tuna.tsinghua.edu.cn/simple \
     --trusted-host pypi.tuna.tsinghua.edu.cn \
     pymysql bcrypt python-dotenv sqlalchemy && \
   python scripts/init_admin.py'
