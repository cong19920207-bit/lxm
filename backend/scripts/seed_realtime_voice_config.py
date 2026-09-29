# -*- coding: utf-8 -*-
"""幂等发布实时语音两套规范首版本（STEP-005）。

用法：
    PYTHONPATH=. python -m backend.scripts.seed_realtime_voice_config --operator admin

仅对尚无生效版本的 key 发布；任何已有运营版本都原样跳过。
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import select

from backend.database import async_session_maker
from backend.models.admin_user import AdminUser
from backend.services.realtime_voice_config_service import (
    realtime_voice_config_service,
)


async def seed(operator: str) -> dict:
    async with async_session_maker() as db:
        admin_user = (
            await db.execute(
                select(AdminUser).where(
                    AdminUser.username == operator,
                    AdminUser.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()
        if admin_user is None:
            raise RuntimeError(f"找不到可用管理员账号: {operator}")
        return await realtime_voice_config_service.initialize_defaults(
            db,
            admin_user=admin_user,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等发布实时语音规范首版本")
    parser.add_argument("--operator", required=True, help="写入初始化审计的管理员用户名")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(seed(args.operator)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
