# -*- coding: utf-8 -*-
# 认证中间件：get_current_user 依赖注入

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.redis_client import get_redis
from backend.utils.jwt_handler import verify_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def _authenticate_credentials(
    credentials: HTTPAuthorizationCredentials | None,
) -> int:
    """复用强鉴权与可选鉴权的 Token、封禁校验。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        result = verify_token(credentials.credentials)
        user_id = result["user_id"]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户是否被管理员禁用
    redis = await get_redis()
    banned = await redis.get(f"user_banned:{user_id}")
    if banned:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用",
        )

    return user_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> int:
    """
    FastAPI 依赖注入函数，从请求头 Authorization: Bearer <token> 中提取并校验 Token。
    Token验证通过后额外检查用户是否被禁用（Redis key: user_banned:{user_id}）。
    :return: user_id
    :raises HTTPException: 401 验证失败或账号被禁用
    """
    return await _authenticate_credentials(credentials)


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> int | None:
    """完全缺少 Authorization 时返回 None；出现认证头后仍严格校验。"""
    if "authorization" not in request.headers:
        return None
    return await _authenticate_credentials(credentials)
