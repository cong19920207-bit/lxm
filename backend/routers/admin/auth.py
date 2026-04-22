# -*- coding: utf-8 -*-
# 后台登录、登出、修改密码接口

import logging
import re
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_AUTH_ACCOUNT_LOCKED,
    ADMIN_ERR_AUTH_LOGIN_FAILED,
    ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH,
    ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD,
    ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG,
    ADMIN_ERR_AUTH_PASSWORD_POLICY,
    ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.admin_auth import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
)
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import (
    create_admin_token,
    get_current_admin,
    log_operation,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 密码强度校验：≥12位，同时含大小写字母+数字+特殊字符
_HAS_UPPER = re.compile(r"[A-Z]")
_HAS_LOWER = re.compile(r"[a-z]")
_HAS_DIGIT = re.compile(r"[0-9]")
_HAS_SPECIAL = re.compile(r"[^a-zA-Z0-9]")


def _validate_admin_password(password: str) -> str | None:
    """校验管理员密码强度，返回错误描述或None（通过）"""
    if len(password) < 12:
        return "密码长度不能少于12位"
    if not _HAS_UPPER.search(password):
        return "密码必须包含大写字母"
    if not _HAS_LOWER.search(password):
        return "密码必须包含小写字母"
    if not _HAS_DIGIT.search(password):
        return "密码必须包含数字"
    if not _HAS_SPECIAL.search(password):
        return "密码必须包含特殊字符"
    return None


def _verify_password(password: str, password_hash: str) -> bool:
    """验证密码与哈希是否匹配"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _hash_password(password: str) -> str:
    """bcrypt 加盐哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


@router.post("/login")
async def admin_login(
    req: AdminLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """后台管理员登录"""
    # a. 查询管理员账号
    stmt = select(AdminUser).where(AdminUser.username == req.username)
    result = await db.execute(stmt)
    admin_user = result.scalars().first()

    if admin_user is None:
        return ApiResponse.fail(ADMIN_ERR_AUTH_LOGIN_FAILED)

    # b. 检查锁定状态（锁定时不验证密码，不更新login_fail_count）
    if admin_user.is_locked:
        return ApiResponse.fail(ADMIN_ERR_AUTH_ACCOUNT_LOCKED)

    # c+d. 验证密码
    if not _verify_password(req.password, admin_user.password_hash):
        admin_user.login_fail_count += 1
        if admin_user.login_fail_count >= 5:
            # 锁定账号
            admin_user.is_locked = True
            admin_user.login_fail_count = 0
            await db.flush()
            return ApiResponse.fail(ADMIN_ERR_AUTH_ACCOUNT_LOCKED)
        await db.flush()
        remaining = 5 - admin_user.login_fail_count
        return ApiResponse.fail(
            ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING,
            message=f"账号或密码错误，还可尝试{remaining}次",
        )

    # e. 密码正确
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    admin_user.login_fail_count = 0
    admin_user.last_login_at = now

    # 检查密码是否超过90天未修改
    need_change_password = False
    if admin_user.last_password_change_at:
        days_since = (now - admin_user.last_password_change_at).days
        if days_since > 90:
            need_change_password = True
    else:
        # 从未修改过密码，建议修改
        need_change_password = True

    # 生成Token
    token = create_admin_token(admin_user.id, admin_user.role)

    # 写入登录日志
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="系统",
        action="login",
        target_description=f"管理员{admin_user.username}登录",
        request=request,
    )

    await db.flush()

    login_data = AdminLoginResponse(
        token=token,
        username=admin_user.username,
        role=admin_user.role,
        need_change_password=need_change_password,
    )
    return ApiResponse.ok(data=login_data.model_dump())


@router.post("/logout")
async def admin_logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """后台管理员登出"""
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="系统",
        action="logout",
        target_description=f"管理员{admin_user.username}登出",
        request=request,
    )
    return ApiResponse.ok(data=None, message="已退出登录")


@router.post("/change-password")
async def admin_change_password(
    req: AdminChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """后台管理员修改密码"""
    # 验证旧密码
    if not _verify_password(req.old_password, admin_user.password_hash):
        return ApiResponse.fail(ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG)

    # 新密码不能与旧密码相同
    if req.old_password == req.new_password:
        return ApiResponse.fail(ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD)

    # 两次新密码一致
    if req.new_password != req.confirm_password:
        return ApiResponse.fail(ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH)

    # 新密码强度校验
    err = _validate_admin_password(req.new_password)
    if err:
        return ApiResponse.fail(ADMIN_ERR_AUTH_PASSWORD_POLICY, message=err)

    # 更新密码
    admin_user.password_hash = _hash_password(req.new_password)
    admin_user.last_password_change_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="系统",
        action="edit",
        target_description=f"管理员{admin_user.username}修改密码",
        request=request,
    )

    return ApiResponse.ok(message="密码修改成功")
