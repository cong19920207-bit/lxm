# -*- coding: utf-8 -*-
# 初始化 MySQL 表结构：根据 .env 中的 MySQL 配置创建数据库和所有数据表

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
_proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_proj_root))

# 最先加载 .env，确保后续导入 backend 时读到最新配置
from dotenv import load_dotenv

load_dotenv(_proj_root / ".env", override=True)


async def ensure_database():
    """若数据库不存在则创建"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.config import get_mysql_database, get_mysql_url_no_db

    db_name = get_mysql_database()
    url_no_db = get_mysql_url_no_db()
    engine = create_async_engine(url_no_db)
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    await engine.dispose()


async def main():
    from backend.config import get_mysql_database, get_mysql_url

    url = get_mysql_url()
    db_name = get_mysql_database()
    safe_url = url.replace("//", "//***:***@").split("@")[-1] if "@" in url else url
    print(f"连接 MySQL: {safe_url}")
    print(f"确保数据库 {db_name} 存在...")
    await ensure_database()
    print("正在创建表结构...")

    from backend.database import create_all_tables

    await create_all_tables()
    print("表结构创建完成。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("\n连接失败，请检查：")
        print("  1. MySQL 服务是否已启动（docker-compose up -d）")
        print("  2. .env 中的 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE 是否正确")
        print("  3. 用户是否有 CREATE DATABASE 权限")
        print(f"\n错误详情: {e}")
        sys.exit(1)
