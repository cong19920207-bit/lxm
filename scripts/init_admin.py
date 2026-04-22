#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超级管理员账号初始化脚本
首次部署时运行一次：python scripts/init_admin.py
已存在账号时自动跳过，不会覆盖。
"""
import sys
import os
from pathlib import Path
from urllib.parse import quote_plus, urlparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from datetime import datetime
from dotenv import load_dotenv
import sqlalchemy as sa

# 始终从项目根目录加载 .env，避免「未 cd 到仓库根」时读到错误库（默认 lxm）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip().replace("mysql+asyncmy", "mysql+pymysql")

if not DATABASE_URL:
    _host = os.getenv("MYSQL_HOST", "127.0.0.1")
    _port = os.getenv("MYSQL_PORT", "3306")
    _user = os.getenv("MYSQL_USER", "lxm")
    _password = os.getenv("MYSQL_PASSWORD", "lxm123456")
    _database = os.getenv("MYSQL_DATABASE", "lxm")
    # 密码中若含 @、: 等需编码，否则 URL 解析错误
    DATABASE_URL = (
        f"mysql+pymysql://{quote_plus(_user)}:{quote_plus(_password)}"
        f"@{_host}:{_port}/{_database}"
    )

DEFAULT_USERNAME = "superadmin"
DEFAULT_PASSWORD = "Admin@123456"


def _log_target_db() -> None:
    """打印即将连接的库（不含密码），便于排查连错库"""
    try:
        u = urlparse(DATABASE_URL.replace("mysql+pymysql", "mysql", 1))
        db = (u.path or "/").lstrip("/") or "(未指定库名)"
        host = u.hostname or "?"
        port = u.port or 3306
        user = u.username or "?"
        print(f"ℹ️  连接 MySQL：{user}@{host}:{port} / 库名 {db}")
    except Exception:
        print("ℹ️  使用环境变量中的 DATABASE_URL 或 .env 中的 MYSQL_* 连接数据库")


def main():
    _log_target_db()
    engine = sa.create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # 检查表是否存在（当前连接到的 schema）
        if not conn.execute(sa.text("SHOW TABLES LIKE 'admin_users'")).fetchone():
            print("❌ admin_users 表不存在，请先启动 FastAPI（backend）完成建表。")
            print("   若你在 docker exec 里能查到该表，但本脚本不行：")
            print("   多半是 127.0.0.1:3306 连到了「本机 MySQL」而不是 Docker 里的库。")
            print("   请改用：bash scripts/init_admin_docker.sh")
            print("   或停掉本机 MySQL / 改 Docker 端口映射后再用本脚本。")
            return

        # 检查是否已有super_admin
        if conn.execute(sa.text(
            "SELECT id FROM admin_users WHERE role='super_admin' LIMIT 1"
        )).fetchone():
            print("ℹ️  已存在超级管理员账号，跳过创建")
            return

    # 使用 begin() 保证 INSERT 提交（兼容 SQLAlchemy 2.x）
    password_hash = bcrypt.hashpw(
        DEFAULT_PASSWORD.encode(), bcrypt.gensalt()
    ).decode()
    now = datetime.now()
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
            INSERT INTO admin_users
            (username, password_hash, role, is_active, login_fail_count,
             is_locked, last_password_change_at, created_at)
            VALUES (:u, :p, 'super_admin', True, 0, False, :now, :now)
            """),
            {"u": DEFAULT_USERNAME, "p": password_hash, "now": now},
        )

    print("✅ 超级管理员账号创建成功")
    print(f"   账号：{DEFAULT_USERNAME}")
    print(f"   密码：{DEFAULT_PASSWORD}")
    print("   ⚠️  请登录后台后立即修改密码！")


if __name__ == "__main__":
    main()
