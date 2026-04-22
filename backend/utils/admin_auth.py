# -*- coding: utf-8 -*-
# 后台JWT认证和权限工具

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_admin_jwt_secret, get_jwt_algorithm
from backend.database import get_db
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# Token有效期：2小时
_ADMIN_TOKEN_EXPIRE_HOURS = 2


def create_admin_token(admin_user_id: int, role: str) -> str:
    """
    生成后台专用JWT Token。
    payload中包含type="admin"以区分用户端Token。
    sub 必须为字符串：PyJWT 2.8+ 默认校验要求 sub 为 str，整型会导致 decode 失败（InvalidSubjectError）。
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_user_id),
        "role": role,
        "type": "admin",
        "exp": now + timedelta(hours=_ADMIN_TOKEN_EXPIRE_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, get_admin_jwt_secret(), algorithm=get_jwt_algorithm())


def verify_admin_token(token: str) -> dict:
    """
    验证后台JWT Token。
    必须校验type=="admin"以防止用户端Token冒用。
    """
    try:
        payload = jwt.decode(
            token,
            get_admin_jwt_secret(),
            algorithms=[get_jwt_algorithm()],
        )
        if payload.get("type") != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的后台Token",
            )
        sub = payload.get("sub")
        if sub is None or sub == "":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token缺少身份信息",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已过期，请重新登录",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效，请重新登录",
        )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    FastAPI依赖注入：验证Token并返回当前管理员用户对象。
    is_active=False时返回401。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_admin_token(credentials.credentials)
    try:
        admin_user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token身份信息无效",
        )

    stmt = select(AdminUser).where(AdminUser.id == admin_user_id)
    result = await db.execute(stmt)
    admin_user = result.scalars().first()

    if admin_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员账号不存在",
        )
    if not admin_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用",
        )
    return admin_user


def require_role(*roles: str) -> Callable:
    """
    角色权限检查依赖。
    用法：@router.get("/xxx", dependencies=[Depends(require_role("super_admin","ops_admin"))])
    """
    async def _role_checker(
        admin_user: AdminUser = Depends(get_current_admin),
    ) -> AdminUser:
        if admin_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return admin_user
    return Depends(_role_checker)


async def log_operation(
    db: AsyncSession,
    admin_user: AdminUser,
    module: str,
    action: str,
    target_description: str,
    before_value: str = None,
    after_value: str = None,
    request: Request = None,
) -> None:
    """
    写入操作日志的统一工具函数。
    ip_address从request.client.host获取，request为None时ip_address=None。
    """
    ip_address = None
    if request and request.client:
        ip_address = request.client.host

    log_entry = AdminOperationLog(
        admin_user_id=admin_user.id,
        admin_username=admin_user.username,
        module=module,
        action=action,
        target_description=target_description,
        before_value=before_value,
        after_value=after_value,
        ip_address=ip_address,
    )
    db.add(log_entry)
    await db.flush()
