# -*- coding: utf-8 -*-
# 管理员账号管理接口（仅super_admin可操作）

import json
import logging
import re
import secrets
import string
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE,
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF,
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER,
    ADMIN_ERR_ACCOUNT_NOT_FOUND,
    ADMIN_ERR_ACCOUNT_USERNAME_EXISTS,
    ADMIN_ERR_AUTH_PASSWORD_POLICY,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.admin_auth import (
    AdminCreateAccountRequest,
    AdminUpdateAccountRequest,
)
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import (
    get_current_admin,
    log_operation,
    require_role,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_HAS_UPPER = re.compile(r"[A-Z]")
_HAS_LOWER = re.compile(r"[a-z]")
_HAS_DIGIT = re.compile(r"[0-9]")
_HAS_SPECIAL = re.compile(r"[^a-zA-Z0-9]")


def _validate_admin_password(password: str) -> str | None:
    """校验管理员密码强度"""
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


def _hash_password(password: str) -> str:
    """bcrypt 加盐哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _generate_random_password(length: int = 16) -> str:
    """生成随机强密码：包含大写、小写、数字、特殊字符"""
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
    remaining_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    rest = "".join(secrets.choice(remaining_chars) for _ in range(length - 4))
    password_list = list(upper + lower + digit + special + rest)
    # 打乱顺序
    for i in range(len(password_list) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_list[i], password_list[j] = password_list[j], password_list[i]
    return "".join(password_list)


def _admin_to_dict(admin: AdminUser) -> dict:
    """将AdminUser转为前端展示字典"""
    return {
        "id": admin.id,
        "username": admin.username,
        "role": admin.role,
        "remark": admin.remark,
        "is_active": admin.is_active,
        "is_locked": admin.is_locked,
        "last_login_at": admin.last_login_at.isoformat() if admin.last_login_at else None,
        "created_at": admin.created_at.isoformat() if admin.created_at else None,
    }


@router.get("/accounts", dependencies=[require_role("super_admin")])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取所有管理员账号列表"""
    stmt = select(AdminUser).order_by(AdminUser.created_at.asc())
    result = await db.execute(stmt)
    admins = result.scalars().all()
    data = [_admin_to_dict(a) for a in admins]
    return ApiResponse.ok(data=data)


@router.post("/accounts", dependencies=[require_role("super_admin")])
async def create_account(
    req: AdminCreateAccountRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """创建新管理员账号"""
    # 密码强度校验
    err = _validate_admin_password(req.password)
    if err:
        return ApiResponse.fail(ADMIN_ERR_AUTH_PASSWORD_POLICY, message=err)

    # 检查用户名唯一性
    stmt = select(AdminUser).where(AdminUser.username == req.username)
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_USERNAME_EXISTS)

    new_admin = AdminUser(
        username=req.username,
        password_hash=_hash_password(req.password),
        role=req.role,
        remark=req.remark,
        is_active=True,
        is_locked=False,
        login_fail_count=0,
        created_by=admin_user.username,
    )
    db.add(new_admin)
    await db.flush()

    after_info = json.dumps({
        "id": new_admin.id,
        "username": new_admin.username,
        "role": new_admin.role,
        "remark": new_admin.remark,
    }, ensure_ascii=False)

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="账号管理",
        action="create",
        target_description=f"创建管理员账号{req.username}",
        after_value=after_info,
        request=request,
    )

    return ApiResponse.ok(data=_admin_to_dict(new_admin), message="创建成功")


@router.put("/accounts/{account_id}", dependencies=[require_role("super_admin")])
async def update_account(
    account_id: int,
    req: AdminUpdateAccountRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑管理员账号（只可改role和remark）"""
    stmt = select(AdminUser).where(AdminUser.id == account_id)
    result = await db.execute(stmt)
    target = result.scalars().first()

    if target is None:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_NOT_FOUND)

    # 不可修改自己的role
    if target.id == admin_user.id and req.role is not None and req.role != admin_user.role:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE)

    before_info = json.dumps({
        "role": target.role,
        "remark": target.remark,
    }, ensure_ascii=False)

    if req.role is not None and req.role != target.role:
        target.role = req.role
        target.token_version += 1
    if req.remark is not None:
        target.remark = req.remark

    after_info = json.dumps({
        "role": target.role,
        "remark": target.remark,
    }, ensure_ascii=False)

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="账号管理",
        action="edit",
        target_description=f"编辑管理员账号{target.username}",
        before_value=before_info,
        after_value=after_info,
        request=request,
    )

    return ApiResponse.ok(data=_admin_to_dict(target), message="修改成功")


@router.delete("/accounts/{account_id}", dependencies=[require_role("super_admin")])
async def delete_account(
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除管理员账号"""
    stmt = select(AdminUser).where(AdminUser.id == account_id)
    result = await db.execute(stmt)
    target = result.scalars().first()

    if target is None:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_NOT_FOUND)

    # 不可删除自己
    if target.id == admin_user.id:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF)

    # super_admin角色账号不可删除
    if target.role == "super_admin":
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER)

    deleted_username = target.username

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="账号管理",
        action="delete",
        target_description=f"删除管理员账号{deleted_username}",
        before_value=json.dumps(_admin_to_dict(target), ensure_ascii=False),
        request=request,
    )

    await db.delete(target)
    await db.flush()

    return ApiResponse.ok(message="删除成功")


@router.post("/accounts/{account_id}/reset-password", dependencies=[require_role("super_admin")])
async def reset_password(
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """重置管理员密码，返回系统生成的随机强密码"""
    stmt = select(AdminUser).where(AdminUser.id == account_id)
    result = await db.execute(stmt)
    target = result.scalars().first()

    if target is None:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_NOT_FOUND)

    new_password = _generate_random_password(16)
    target.password_hash = _hash_password(new_password)
    target.last_password_change_at = datetime.now(timezone.utc).replace(tzinfo=None)
    target.token_version += 1

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="账号管理",
        action="edit",
        target_description=f"重置管理员账号{target.username}的密码",
        request=request,
    )

    return ApiResponse.ok(
        data={"new_password": new_password},
        message="密码已重置，请妥善保管新密码",
    )


@router.post("/accounts/{account_id}/unlock", dependencies=[require_role("super_admin")])
async def unlock_account(
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """解锁被锁定的管理员账号"""
    stmt = select(AdminUser).where(AdminUser.id == account_id)
    result = await db.execute(stmt)
    target = result.scalars().first()

    if target is None:
        return ApiResponse.fail(ADMIN_ERR_ACCOUNT_NOT_FOUND)

    if not target.is_locked:
        return ApiResponse.ok(message="该账号未被锁定")

    target.is_locked = False
    target.login_fail_count = 0

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="账号管理",
        action="unlock",
        target_description=f"解锁管理员账号{target.username}",
        request=request,
    )

    return ApiResponse.ok(message="账号已解锁")
