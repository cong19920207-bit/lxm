# -*- coding: utf-8 -*-
# Open API Key 鉴权（仅用于 /api/open/v1/*）

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_open_api_pepper
from backend.database import get_db
from backend.models.user_api_key import UserApiKey
from backend.redis_client import get_redis

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "sk-lxm-"
_bearer_scheme = HTTPBearer(auto_error=False)
_LAST_USED_THROTTLE_SEC = 60


def _hash_api_key(api_key: str) -> str:
    pepper = get_open_api_pepper()
    return hashlib.sha256((api_key + pepper).encode("utf-8")).hexdigest()


async def get_current_user_by_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> int:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw = credentials.credentials.strip()
    if not raw.startswith(_API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效或已吊销",
        )

    key_hash = _hash_api_key(raw)
    stmt = select(UserApiKey).where(UserApiKey.key_hash == key_hash)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效或已吊销",
        )

    user_id = row.user_id
    redis = await get_redis()
    banned = await redis.get(f"user_banned:{user_id}")
    if banned:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用",
        )

    now = datetime.utcnow()
    should_touch = row.last_used_at is None or (now - row.last_used_at) >= timedelta(
        seconds=_LAST_USED_THROTTLE_SEC
    )
    if should_touch:
        row.last_used_at = now
        await db.commit()

    return user_id


def verify_key_hash(api_key: str, stored_hash: str) -> bool:
    """恒定时间比较 Key 哈希。"""
    computed = _hash_api_key(api_key)
    return hmac.compare_digest(computed, stored_hash)
