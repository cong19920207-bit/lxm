# -*- coding: utf-8 -*-
# 认证相关 API：注册、登录、重置密码、登出

import asyncio
import logging
import re
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ERR_ACCOUNT_BANNED,
    ERR_ACCOUNT_LOCKED,
    ERR_PASSWORD_FORMAT,
    ERR_PASSWORD_MISMATCH,
    ERR_PASSWORD_SAME_AS_USERNAME,
    ERR_PASSWORD_WRONG,
    ERR_USERNAME_EXISTS,
    ERR_USERNAME_FORMAT,
    ERR_USERNAME_SENSITIVE,
    ERR_USER_NOT_FOUND,
    LOCK_MINUTES,
    MAX_LOGIN_FAIL_COUNT,
    SENSITIVE_WORDS,
    TOKEN_EXPIRE_DAYS_LONG,
    TOKEN_EXPIRE_DAYS_SHORT,
)
from backend.database import async_session_maker, get_db
from backend.models.login_log import LoginLog
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services.relationship_service import RelationshipService
from backend.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenData,
)
from backend.schemas.common import ApiResponse
from backend.utils.auth_middleware import get_current_user
from backend.utils.jwt_handler import create_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

# ============ 校验工具函数 ============

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]{6,20}$")
_PASSWORD_LETTER = re.compile(r"[a-zA-Z]")
_PASSWORD_DIGIT = re.compile(r"[0-9]")


def _validate_username(username: str) -> int | None:
    """校验用户名格式，返回错误码或 None（通过）"""
    if not _USERNAME_PATTERN.match(username):
        return ERR_USERNAME_FORMAT
    lower = username.lower()
    for word in SENSITIVE_WORDS:
        if word.lower() in lower:
            return ERR_USERNAME_SENSITIVE
    return None


def _validate_password(password: str, username: str) -> int | None:
    """校验密码格式，返回错误码或 None（通过）"""
    if len(password) < 8 or len(password) > 20:
        return ERR_PASSWORD_FORMAT
    if not _PASSWORD_LETTER.search(password):
        return ERR_PASSWORD_FORMAT
    if not _PASSWORD_DIGIT.search(password):
        return ERR_PASSWORD_FORMAT
    if password.lower() == username.lower():
        return ERR_PASSWORD_SAME_AS_USERNAME
    return None


def _hash_password(password: str) -> str:
    """bcrypt 加盐哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """验证密码与哈希是否匹配"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _get_time_period(hour: int) -> str:
    """根据小时判断时段：morning(7-9) / evening(20-22) / other"""
    if 7 <= hour <= 9:
        return "morning"
    if 20 <= hour <= 22:
        return "evening"
    return "other"


# ============ API 接口 ============


@router.post("/register", response_model=ApiResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 校验用户名格式
    err = _validate_username(req.username)
    if err:
        return ApiResponse.fail(err)

    # 校验密码格式
    err = _validate_password(req.password, req.username)
    if err:
        return ApiResponse.fail(err)

    # 校验两次密码一致
    if req.password != req.confirm_password:
        return ApiResponse.fail(ERR_PASSWORD_MISMATCH)

    # 校验用户名唯一性（不区分大小写）
    stmt = select(User).where(func.lower(User.username) == req.username.lower())
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        return ApiResponse.fail(ERR_USERNAME_EXISTS)

    # 创建用户
    user = User(
        username=req.username,
        password_hash=_hash_password(req.password),
    )
    db.add(user)
    await db.flush()

    # 初始化关系表记录
    rel = Relationship(
        user_id=user.id,
        level=0,
        growth_value=0,
    )
    db.add(rel)

    # 生成 Token（30天有效期）
    token = create_token(user.id, expire_days=TOKEN_EXPIRE_DAYS_LONG)

    return ApiResponse.ok(
        data=TokenData(token=token, user_id=user.id, username=user.username).model_dump()
    )


@router.post("/login", response_model=ApiResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    # 不区分大小写查找用户
    stmt = select(User).where(func.lower(User.username) == req.username.lower())
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        return ApiResponse.fail(ERR_USER_NOT_FOUND)

    # 检查封禁
    if user.is_banned:
        return ApiResponse.fail(ERR_ACCOUNT_BANNED)

    # 检查锁定
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        remaining = int((user.locked_until.replace(tzinfo=timezone.utc) - now).total_seconds())
        remaining_min = remaining // 60 + (1 if remaining % 60 > 0 else 0)
        return ApiResponse.fail(
            ERR_ACCOUNT_LOCKED,
            message=f"账号已被锁定，请{remaining_min}分钟后重试",
        )

    # 验证密码
    if not _verify_password(req.password, user.password_hash):
        user.login_fail_count += 1
        if user.login_fail_count >= MAX_LOGIN_FAIL_COUNT:
            from datetime import timedelta
            user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=LOCK_MINUTES)
            user.login_fail_count = 0
            await db.flush()
            return ApiResponse.fail(
                ERR_ACCOUNT_LOCKED,
                message=f"密码连续错误{MAX_LOGIN_FAIL_COUNT}次，账号已锁定{LOCK_MINUTES}分钟",
            )
        await db.flush()
        remaining_attempts = MAX_LOGIN_FAIL_COUNT - user.login_fail_count
        return ApiResponse.fail(
            ERR_PASSWORD_WRONG,
            message=f"密码错误，还可尝试{remaining_attempts}次",
        )

    # 登录成功：重置失败计数，更新最后登录时间
    user.login_fail_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    # 写入登录日志
    now_local = datetime.now()
    login_log = LoginLog(
        user_id=user.id,
        login_at=now_local,
        time_period=_get_time_period(now_local.hour),
    )
    db.add(login_log)

    # 生成 Token
    expire_days = TOKEN_EXPIRE_DAYS_LONG if req.remember_me else TOKEN_EXPIRE_DAYS_SHORT
    token = create_token(user.id, expire_days=expire_days)

    # 异步触发登录后续任务（不阻塞登录响应）
    asyncio.create_task(_post_login_tasks(user.id))

    return ApiResponse.ok(
        data=TokenData(token=token, user_id=user.id, username=user.username).model_dump()
    )


@router.post("/reset-password", response_model=ApiResponse)
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """重置密码（简化版：仅验证用户名存在即可重置）"""
    # 校验密码格式
    err = _validate_password(req.new_password, req.username)
    if err:
        return ApiResponse.fail(err)

    # 校验两次密码一致
    if req.new_password != req.confirm_password:
        return ApiResponse.fail(ERR_PASSWORD_MISMATCH)

    # 查找用户（不区分大小写）
    stmt = select(User).where(func.lower(User.username) == req.username.lower())
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        return ApiResponse.fail(ERR_USER_NOT_FOUND)

    # 更新密码
    user.password_hash = _hash_password(req.new_password)
    await db.flush()

    return ApiResponse.ok(message="密码重置成功")


@router.post("/logout", response_model=ApiResponse)
async def logout(user_id: int = Depends(get_current_user)):
    """登出（清除客户端Token，服务端无状态JWT无需额外清除）"""
    logger.info("用户 %d 登出", user_id)
    return ApiResponse.ok(message="登出成功")


# ============ 内部辅助 ============


async def _post_login_tasks(user_id: int) -> None:
    """
    登录后异步后台任务（不阻塞登录响应）：
    1. 更新连续登录天数
    2. 增加每日登录成长值
    3. 触发主动消息检查
    """
    # 1. 更新连续登录天数 + 增加 daily_login 成长值
    try:
        async with async_session_maker() as db:
            svc = RelationshipService(db)
            await svc.update_consecutive_login(user_id)
            await svc.add_growth(user_id, "daily_login")
            await db.commit()
        logger.info("登录成长值已更新: user_id=%d", user_id)
    except Exception:
        logger.exception("登录成长值更新失败: user_id=%d", user_id)

    # 2. 触发主动消息检查
    try:
        from backend.services.agent_service import agent_service
        await agent_service.check_and_trigger(user_id)
    except Exception:
        logger.exception("主动消息检查失败: user_id=%d", user_id)
