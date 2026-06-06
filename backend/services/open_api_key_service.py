# -*- coding: utf-8 -*-
# Admin 签发 Open API Key

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User
from backend.models.user_api_key import UserApiKey
from backend.utils.open_api_auth import _hash_api_key

_KEY_PREFIX = "sk-lxm-"
_RANDOM_BYTES = 32


def _build_key_prefix(random_part: str) -> str:
    if len(random_part) < 8:
        return f"{_KEY_PREFIX}{random_part[:4]}…{random_part[-4:]}"
    return f"{_KEY_PREFIX}{random_part[:4]}…{random_part[-4:]}"


def generate_api_key_material() -> tuple[str, str, str]:
    """返回 (完整 api_key, key_hash, key_prefix)。"""
    random_part = secrets.token_urlsafe(_RANDOM_BYTES)
    api_key = f"{_KEY_PREFIX}{random_part}"
    key_hash = _hash_api_key(api_key)
    key_prefix = _build_key_prefix(random_part)
    return api_key, key_hash, key_prefix


async def get_key_status(db: AsyncSession, user_id: int) -> dict | None:
    stmt = select(UserApiKey).where(UserApiKey.user_id == user_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "enabled": True,
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


async def upsert_api_key(
    db: AsyncSession,
    user_id: int,
    admin_id: int,
) -> tuple[str, bool, str | None]:
    """
    生成或重新生成 Key。
    返回 (明文 api_key, is_create, old_key_prefix)。
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise ValueError("user_not_found")

    api_key, key_hash, key_prefix = generate_api_key_material()
    stmt = select(UserApiKey).where(UserApiKey.user_id == user_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is None:
        row = UserApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_by_admin_id=admin_id,
        )
        db.add(row)
        await db.flush()
        return api_key, True, None

    old_prefix = existing.key_prefix
    existing.key_hash = key_hash
    existing.key_prefix = key_prefix
    existing.last_used_at = None
    existing.created_by_admin_id = admin_id
    await db.flush()
    return api_key, False, old_prefix
