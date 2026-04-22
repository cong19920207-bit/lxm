# -*- coding: utf-8 -*-
# JWT Token 生成与解析

from datetime import datetime, timedelta, timezone

import jwt

from backend.config import get_jwt_algorithm, get_jwt_secret
from backend.constants import ERR_TOKEN_EXPIRED, ERR_TOKEN_INVALID


def create_token(user_id: int, expire_days: int = 30) -> str:
    """
    生成 JWT Token。
    :param user_id: 用户ID
    :param expire_days: 过期天数，默认30天
    :return: JWT字符串
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "exp": now + timedelta(days=expire_days),
        "iat": now,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())


def verify_token(token: str) -> dict:
    """
    验证并解析 JWT Token。
    :param token: JWT字符串
    :return: {"user_id": int} 或抛出异常
    :raises ValueError: Token无效或已过期，附带错误码
    """
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[get_jwt_algorithm()],
        )
        user_id = payload.get("user_id")
        if user_id is None:
            raise ValueError(ERR_TOKEN_INVALID)
        return {"user_id": user_id}
    except jwt.ExpiredSignatureError:
        raise ValueError(ERR_TOKEN_EXPIRED)
    except jwt.PyJWTError:
        raise ValueError(ERR_TOKEN_INVALID)
