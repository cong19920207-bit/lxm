#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生活流全局 admin_config 种子脚本（STEP-003）。

用途：把第零章全局配置项 + 互动/发布/图片/延迟等默认值幂等写入 admin_config。
  - 幂等：同一 config_key 已存在「生效版本」（is_draft=False AND is_active=True）则跳过，不覆盖。
  - 种子直接生效：写入时 is_draft=False, is_active=True, version=1（不走三道卡点；
    后续 STEP-030~036 通过后台修改配置必须走草稿→测试集→CONFIRM→5min 监控流程）。

运行：python -m backend.scripts.seed_life_feed_config
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

# 允许以脚本方式运行时导入 backend.*
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

import sqlalchemy as sa  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from backend.constants.life_feed_config import build_seed_config_items  # noqa: E402

load_dotenv(_PROJECT_ROOT / ".env")

SEED_UPDATED_BY = "system_seed"


def _build_database_url() -> str:
    """构造同步 pymysql 连接串（种子脚本用同步引擎，参照 init_admin.py）。"""
    url = os.getenv("DATABASE_URL", "").strip().replace("mysql+asyncmy", "mysql+pymysql")
    if url:
        return url
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "lxm")
    password = os.getenv("MYSQL_PASSWORD", "lxm123456")
    database = os.getenv("MYSQL_DATABASE", "lxm")
    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


def _serialize(value) -> str:
    """统一 JSON 序列化写入（含标量），读取端 admin_config_service 会尝试 json.loads 还原。"""
    return json.dumps(value, ensure_ascii=False)


def seed(engine) -> dict:
    """执行幂等种子；返回 {'inserted': n, 'skipped': m}。"""
    items = build_seed_config_items()
    inserted = 0
    skipped = 0
    now = datetime.utcnow()

    if not sa.inspect(engine).has_table("admin_config"):
        raise RuntimeError("admin_config 表不存在，请先完成建表/迁移后再执行种子脚本。")

    with engine.begin() as conn:
        for item in items:
            key = item["config_key"]
            # 幂等：已存在生效版本则跳过
            exists = conn.execute(
                sa.text(
                    "SELECT id FROM admin_config "
                    "WHERE config_key = :k AND is_draft = 0 AND is_active = 1 LIMIT 1"
                ),
                {"k": key},
            ).fetchone()
            if exists:
                skipped += 1
                continue

            conn.execute(
                sa.text(
                    "INSERT INTO admin_config "
                    "(config_key, config_value, version, is_active, is_draft, updated_by, updated_at) "
                    "VALUES (:k, :v, 1, 1, 0, :by, :now)"
                ),
                {
                    "k": key,
                    "v": _serialize(item["config_value"]),
                    "by": SEED_UPDATED_BY,
                    "now": now,
                },
            )
            inserted += 1

    return {"inserted": inserted, "skipped": skipped}


def main() -> None:
    url = _build_database_url()
    engine = sa.create_engine(url)
    result = seed(engine)
    print(
        f"✅ 生活流配置种子完成：新增 {result['inserted']} 项，"
        f"跳过 {result['skipped']} 项（已存在生效版本）"
    )


if __name__ == "__main__":
    main()
