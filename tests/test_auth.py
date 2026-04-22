# -*- coding: utf-8 -*-
# 认证模块单元测试

import sys
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db

# 使用 SQLite 内存数据库进行测试
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with async_session_test() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# mock 掉 scheduler 模块，避免导入 main.py 时因定时任务模块缺失而报错
if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.main import app  # noqa: E402
from backend.routers.auth import (  # noqa: E402
    _get_time_period,
    _hash_password,
    _validate_password,
    _validate_username,
    _verify_password,
)

app.dependency_overrides[get_db] = override_get_db

# 默认用户名/密码（不含敏感词）
_DEFAULT_USER = "player0001"
_DEFAULT_PASS = "pass1234"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前创建表，测试后销毁"""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register(client: AsyncClient, username=_DEFAULT_USER, password=_DEFAULT_PASS):
    """辅助：注册用户并返回响应 JSON"""
    resp = await client.post("/api/auth/register", json={
        "username": username,
        "password": password,
        "confirm_password": password,
    })
    return resp.json()


async def _login(client: AsyncClient, username=_DEFAULT_USER, password=_DEFAULT_PASS, remember_me=False):
    """辅助：登录并返回响应 JSON"""
    resp = await client.post("/api/auth/login", json={
        "username": username,
        "password": password,
        "remember_me": remember_me,
    })
    return resp.json()


# ==================== 注册接口测试 ====================


class TestRegister:
    """POST /api/auth/register"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """正常注册：返回Token和用户信息"""
        data = await _register(client)
        assert data["code"] == 0
        assert data["data"]["username"] == _DEFAULT_USER
        assert "token" in data["data"]
        assert data["data"]["user_id"] > 0

    @pytest.mark.asyncio
    async def test_register_token_usable(self, client: AsyncClient):
        """注册返回的Token可用于鉴权接口"""
        data = await _register(client)
        token = data["data"]["token"]
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_register_initializes_relationship(self, client: AsyncClient):
        """注册成功后 relationship 表有对应记录"""
        data = await _register(client)
        user_id = data["data"]["user_id"]

        from backend.models.relationship import Relationship
        async with async_session_test() as session:
            stmt = select(Relationship).where(Relationship.user_id == user_id)
            result = await session.execute(stmt)
            rel = result.scalars().first()
            assert rel is not None
            assert rel.level == 0
            assert rel.growth_value == 0

    @pytest.mark.asyncio
    async def test_register_username_too_short(self, client: AsyncClient):
        """用户名过短 → Pydantic 422"""
        resp = await client.post("/api/auth/register", json={
            "username": "ab",
            "password": "pass1234",
            "confirm_password": "pass1234",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_username_too_long(self, client: AsyncClient):
        """用户名过长 → Pydantic 422"""
        resp = await client.post("/api/auth/register", json={
            "username": "a" * 21,
            "password": "pass1234",
            "confirm_password": "pass1234",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_username_special_chars(self, client: AsyncClient):
        """用户名含特殊字符 → ERR_USERNAME_FORMAT"""
        data = await _register(client, username="play_er01")
        assert data["code"] == 10002

    @pytest.mark.asyncio
    async def test_register_username_with_underscore(self, client: AsyncClient):
        """用户名含下划线 → ERR_USERNAME_FORMAT"""
        data = await _register(client, username="play_001")
        assert data["code"] == 10002

    @pytest.mark.asyncio
    async def test_register_username_with_chinese(self, client: AsyncClient):
        """用户名含中文 → ERR_USERNAME_FORMAT"""
        data = await _register(client, username="用户名abcde01")
        assert data["code"] == 10002

    @pytest.mark.asyncio
    async def test_register_username_sensitive_admin(self, client: AsyncClient):
        """用户名含敏感词 admin → ERR_USERNAME_SENSITIVE"""
        data = await _register(client, username="admin12345")
        assert data["code"] == 10003

    @pytest.mark.asyncio
    async def test_register_username_sensitive_root(self, client: AsyncClient):
        """用户名含敏感词 root → ERR_USERNAME_SENSITIVE"""
        data = await _register(client, username="rootuser01")
        assert data["code"] == 10003

    @pytest.mark.asyncio
    async def test_register_username_sensitive_system(self, client: AsyncClient):
        """用户名含敏感词 system → ERR_USERNAME_SENSITIVE"""
        data = await _register(client, username="system0001")
        assert data["code"] == 10003

    @pytest.mark.asyncio
    async def test_register_username_sensitive_case_insensitive(self, client: AsyncClient):
        """敏感词检测不区分大小写"""
        data = await _register(client, username="ADMIN12345")
        assert data["code"] == 10003

    @pytest.mark.asyncio
    async def test_register_password_too_short(self, client: AsyncClient):
        """密码过短 → Pydantic 422"""
        resp = await client.post("/api/auth/register", json={
            "username": _DEFAULT_USER,
            "password": "ab1",
            "confirm_password": "ab1",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_password_no_letter(self, client: AsyncClient):
        """密码全数字 → ERR_PASSWORD_FORMAT"""
        data = await _register(client, password="12345678")
        assert data["code"] == 10005

    @pytest.mark.asyncio
    async def test_register_password_no_digit(self, client: AsyncClient):
        """密码全字母 → ERR_PASSWORD_FORMAT"""
        data = await _register(client, password="abcdefgh")
        assert data["code"] == 10005

    @pytest.mark.asyncio
    async def test_register_password_same_as_username(self, client: AsyncClient):
        """密码与用户名相同 → ERR_PASSWORD_SAME_AS_USERNAME"""
        resp = await client.post("/api/auth/register", json={
            "username": "user12ab01",
            "password": "user12ab01",
            "confirm_password": "user12ab01",
        })
        assert resp.json()["code"] == 10007

    @pytest.mark.asyncio
    async def test_register_password_same_as_username_case_insensitive(self, client: AsyncClient):
        """密码与用户名大小写不同但实际相同 → ERR_PASSWORD_SAME_AS_USERNAME"""
        resp = await client.post("/api/auth/register", json={
            "username": "User12Ab01",
            "password": "user12ab01",
            "confirm_password": "user12ab01",
        })
        assert resp.json()["code"] == 10007

    @pytest.mark.asyncio
    async def test_register_password_mismatch(self, client: AsyncClient):
        """两次密码不一致 → ERR_PASSWORD_MISMATCH"""
        resp = await client.post("/api/auth/register", json={
            "username": _DEFAULT_USER,
            "password": "pass1234",
            "confirm_password": "pass5678",
        })
        assert resp.json()["code"] == 10006

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """用户名重复 → ERR_USERNAME_EXISTS"""
        await _register(client)
        data = await _register(client)
        assert data["code"] == 10004

    @pytest.mark.asyncio
    async def test_register_duplicate_username_case_insensitive(self, client: AsyncClient):
        """用户名重复（不区分大小写） → ERR_USERNAME_EXISTS"""
        await _register(client, username="GoodUser01")
        data = await _register(client, username="gooduser01")
        assert data["code"] == 10004

    @pytest.mark.asyncio
    async def test_register_multiple_users(self, client: AsyncClient):
        """可以注册多个不同用户"""
        d1 = await _register(client, username="player0001")
        d2 = await _register(client, username="player0002")
        assert d1["code"] == 0
        assert d2["code"] == 0
        assert d1["data"]["user_id"] != d2["data"]["user_id"]

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """缺少必填字段 → Pydantic 422"""
        resp = await client.post("/api/auth/register", json={
            "username": _DEFAULT_USER,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_empty_body(self, client: AsyncClient):
        """空请求体 → 422"""
        resp = await client.post("/api/auth/register", json={})
        assert resp.status_code == 422


# ==================== 登录接口测试 ====================


class TestLogin:
    """POST /api/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """正常登录"""
        await _register(client)
        data = await _login(client)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert data["data"]["username"] == _DEFAULT_USER
        assert data["data"]["user_id"] > 0

    @pytest.mark.asyncio
    async def test_login_token_usable(self, client: AsyncClient):
        """登录返回的Token可用于鉴权接口"""
        await _register(client)
        data = await _login(client)
        token = data["data"]["token"]
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_login_case_insensitive(self, client: AsyncClient):
        """大写注册、小写登录"""
        await _register(client, username="PlayUser01")
        data = await _login(client, username="playuser01")
        assert data["code"] == 0

    @pytest.mark.asyncio
    async def test_login_case_insensitive_reverse(self, client: AsyncClient):
        """小写注册、大写登录"""
        await _register(client, username="playuser01")
        data = await _login(client, username="PLAYUSER01")
        assert data["code"] == 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """密码错误 → ERR_PASSWORD_WRONG"""
        await _register(client)
        data = await _login(client, password="wrongpass1")
        assert data["code"] == 10009
        assert "还可尝试" in data["message"]

    @pytest.mark.asyncio
    async def test_login_wrong_password_remaining_attempts(self, client: AsyncClient):
        """密码错误次数递增，提示剩余次数递减"""
        await _register(client)
        d1 = await _login(client, password="wrongpass1")
        assert d1["code"] == 10009
        assert "4" in d1["message"]

        d2 = await _login(client, password="wrongpass1")
        assert d2["code"] == 10009
        assert "3" in d2["message"]

        d3 = await _login(client, password="wrongpass1")
        assert d3["code"] == 10009
        assert "2" in d3["message"]

        d4 = await _login(client, password="wrongpass1")
        assert d4["code"] == 10009
        assert "1" in d4["message"]

    @pytest.mark.asyncio
    async def test_login_correct_after_failures_resets_count(self, client: AsyncClient):
        """错误几次后正确登录，重置失败计数"""
        await _register(client)
        for _ in range(3):
            await _login(client, password="wrongpass1")

        data = await _login(client)
        assert data["code"] == 0

        # 再次错误应从头计数
        d2 = await _login(client, password="wrongpass1")
        assert d2["code"] == 10009
        assert "4" in d2["message"]

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, client: AsyncClient):
        """用户不存在 → ERR_USER_NOT_FOUND"""
        data = await _login(client, username="nonexist01")
        assert data["code"] == 10008

    @pytest.mark.asyncio
    async def test_login_account_locked_after_5_failures(self, client: AsyncClient):
        """连续5次错误后锁定 → ERR_ACCOUNT_LOCKED"""
        await _register(client)
        for i in range(4):
            resp = await _login(client, password="wrongpass1")
            assert resp["code"] == 10009

        # 第5次触发锁定
        resp5 = await _login(client, password="wrongpass1")
        assert resp5["code"] == 10010
        assert "锁定" in resp5["message"]

    @pytest.mark.asyncio
    async def test_login_locked_account_rejects_correct_password(self, client: AsyncClient):
        """锁定后即使密码正确也拒绝"""
        await _register(client)
        for _ in range(5):
            await _login(client, password="wrongpass1")

        data = await _login(client)
        assert data["code"] == 10010

    @pytest.mark.asyncio
    async def test_login_locked_shows_remaining_time(self, client: AsyncClient):
        """锁定后返回的消息包含剩余时间"""
        await _register(client)
        for _ in range(5):
            await _login(client, password="wrongpass1")

        data = await _login(client)
        assert data["code"] == 10010
        assert "分钟" in data["message"]

    @pytest.mark.asyncio
    async def test_login_remember_me_false(self, client: AsyncClient):
        """remember_me=False 正常返回Token"""
        await _register(client)
        data = await _login(client, remember_me=False)
        assert data["code"] == 0
        assert "token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_remember_me_true(self, client: AsyncClient):
        """remember_me=True 正常返回Token"""
        await _register(client)
        data = await _login(client, remember_me=True)
        assert data["code"] == 0
        assert "token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_writes_login_log(self, client: AsyncClient):
        """登录成功后写入 login_log 表"""
        reg = await _register(client)
        user_id = reg["data"]["user_id"]
        await _login(client)

        from backend.models.login_log import LoginLog
        async with async_session_test() as session:
            stmt = select(LoginLog).where(LoginLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()
            assert len(logs) == 1
            assert logs[0].time_period in ("morning", "evening", "other")

    @pytest.mark.asyncio
    async def test_login_multiple_writes_multiple_logs(self, client: AsyncClient):
        """多次登录写入多条 login_log"""
        reg = await _register(client)
        user_id = reg["data"]["user_id"]
        await _login(client)
        await _login(client)
        await _login(client)

        from backend.models.login_log import LoginLog
        async with async_session_test() as session:
            stmt = select(LoginLog).where(LoginLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()
            assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_login_updates_last_login_at(self, client: AsyncClient):
        """登录成功后更新 last_login_at"""
        reg = await _register(client)
        user_id = reg["data"]["user_id"]
        await _login(client)

        from backend.models.user import User
        async with async_session_test() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalars().first()
            assert user.last_login_at is not None

    @pytest.mark.asyncio
    async def test_login_banned_account(self, client: AsyncClient):
        """被封禁的账号 → ERR_ACCOUNT_BANNED"""
        reg = await _register(client)
        user_id = reg["data"]["user_id"]

        from backend.models.user import User
        async with async_session_test() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalars().first()
            user.is_banned = True
            await session.commit()

        data = await _login(client)
        assert data["code"] == 10011

    @pytest.mark.asyncio
    async def test_login_missing_password(self, client: AsyncClient):
        """缺少密码字段 → 422"""
        resp = await client.post("/api/auth/login", json={
            "username": _DEFAULT_USER,
        })
        assert resp.status_code == 422


# ==================== 重置密码测试 ====================


class TestResetPassword:
    """POST /api/auth/reset-password"""

    @pytest.mark.asyncio
    async def test_reset_password_success(self, client: AsyncClient):
        """正常重置密码"""
        await _register(client)
        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "newpass12",
            "confirm_password": "newpass12",
        })
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_reset_password_then_login_with_new(self, client: AsyncClient):
        """重置后可以用新密码登录"""
        await _register(client)
        await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "newpass12",
            "confirm_password": "newpass12",
        })
        data = await _login(client, password="newpass12")
        assert data["code"] == 0

    @pytest.mark.asyncio
    async def test_reset_password_old_password_invalid(self, client: AsyncClient):
        """重置后旧密码不可用"""
        await _register(client)
        await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "newpass12",
            "confirm_password": "newpass12",
        })
        data = await _login(client, password=_DEFAULT_PASS)
        assert data["code"] == 10009

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, client: AsyncClient):
        """用户不存在 → ERR_USER_NOT_FOUND"""
        resp = await client.post("/api/auth/reset-password", json={
            "username": "nonexist01",
            "new_password": "newpass12",
            "confirm_password": "newpass12",
        })
        assert resp.json()["code"] == 10008

    @pytest.mark.asyncio
    async def test_reset_password_mismatch(self, client: AsyncClient):
        """两次密码不一致 → ERR_PASSWORD_MISMATCH"""
        await _register(client)
        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "newpass12",
            "confirm_password": "newpass99",
        })
        assert resp.json()["code"] == 10006

    @pytest.mark.asyncio
    async def test_reset_password_invalid_format_no_letter(self, client: AsyncClient):
        """新密码全数字 → ERR_PASSWORD_FORMAT"""
        await _register(client)
        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "12345678",
            "confirm_password": "12345678",
        })
        assert resp.json()["code"] == 10005

    @pytest.mark.asyncio
    async def test_reset_password_invalid_format_no_digit(self, client: AsyncClient):
        """新密码全字母 → ERR_PASSWORD_FORMAT"""
        await _register(client)
        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "abcdefgh",
            "confirm_password": "abcdefgh",
        })
        assert resp.json()["code"] == 10005

    @pytest.mark.asyncio
    async def test_reset_password_case_insensitive_username(self, client: AsyncClient):
        """用户名不区分大小写"""
        await _register(client, username="GoodUser01")
        resp = await client.post("/api/auth/reset-password", json={
            "username": "gooduser01",
            "new_password": "newpass12",
            "confirm_password": "newpass12",
        })
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_reset_password_same_as_username(self, client: AsyncClient):
        """新密码与用户名相同 → ERR_PASSWORD_SAME_AS_USERNAME"""
        await _register(client)
        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": _DEFAULT_USER,
            "confirm_password": _DEFAULT_USER,
        })
        assert resp.json()["code"] == 10007


# ==================== 登出测试 ====================


class TestLogout:
    """POST /api/auth/logout"""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """正常登出"""
        reg = await _register(client)
        token = reg["data"]["token"]
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0
        assert resp.json()["message"] == "登出成功"

    @pytest.mark.asyncio
    async def test_logout_no_token(self, client: AsyncClient):
        """未携带Token → 401"""
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_invalid_token(self, client: AsyncClient):
        """携带无效Token → 401"""
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_expired_token(self, client: AsyncClient):
        """携带过期Token → 401"""
        import jwt as pyjwt
        from backend.config import get_jwt_algorithm, get_jwt_secret
        payload = {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=25),
        }
        expired_token = pyjwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401


# ==================== JWT 工具函数测试 ====================


class TestJwtHandler:
    """JWT 生成与验证"""

    def test_create_and_verify_token(self):
        """生成并验证Token"""
        from backend.utils.jwt_handler import create_token, verify_token
        token = create_token(user_id=42, expire_days=1)
        result = verify_token(token)
        assert result["user_id"] == 42

    def test_create_token_different_users(self):
        """不同用户生成不同Token"""
        from backend.utils.jwt_handler import create_token
        t1 = create_token(user_id=1, expire_days=1)
        t2 = create_token(user_id=2, expire_days=1)
        assert t1 != t2

    def test_create_token_default_expire(self):
        """默认30天有效期"""
        from backend.utils.jwt_handler import create_token, verify_token
        token = create_token(user_id=99)
        result = verify_token(token)
        assert result["user_id"] == 99

    def test_verify_invalid_token(self):
        """无效Token → ValueError"""
        from backend.utils.jwt_handler import verify_token
        with pytest.raises(ValueError):
            verify_token("invalid.token.string")

    def test_verify_empty_token(self):
        """空Token → ValueError"""
        from backend.utils.jwt_handler import verify_token
        with pytest.raises(ValueError):
            verify_token("")

    def test_verify_expired_token(self):
        """过期Token → ValueError"""
        import jwt as pyjwt
        from backend.config import get_jwt_algorithm, get_jwt_secret
        payload = {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = pyjwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())
        from backend.utils.jwt_handler import verify_token
        with pytest.raises(ValueError):
            verify_token(token)

    def test_verify_token_missing_user_id(self):
        """Token payload 缺少 user_id → ValueError"""
        import jwt as pyjwt
        from backend.config import get_jwt_algorithm, get_jwt_secret
        payload = {
            "some_field": "value",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())
        from backend.utils.jwt_handler import verify_token
        with pytest.raises(ValueError):
            verify_token(token)

    def test_verify_token_wrong_secret(self):
        """用错误的密钥签名 → ValueError"""
        import jwt as pyjwt
        payload = {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        from backend.utils.jwt_handler import verify_token
        with pytest.raises(ValueError):
            verify_token(token)


# ==================== 内部校验函数单元测试 ====================


class TestValidateUsername:
    """_validate_username 用户名校验"""

    def test_valid_alphanumeric(self):
        assert _validate_username("player0001") is None

    def test_valid_all_letters(self):
        assert _validate_username("abcdef") is None

    def test_valid_all_digits(self):
        assert _validate_username("123456") is None

    def test_valid_mixed(self):
        assert _validate_username("abc123def456") is None

    def test_valid_uppercase(self):
        assert _validate_username("ABCDEF") is None

    def test_valid_exactly_6_chars(self):
        assert _validate_username("abcdef") is None

    def test_valid_exactly_20_chars(self):
        assert _validate_username("a" * 20) is None

    def test_too_short(self):
        assert _validate_username("abc") == 10002

    def test_too_long(self):
        assert _validate_username("a" * 21) == 10002

    def test_special_chars_underscore(self):
        assert _validate_username("user_01") == 10002

    def test_special_chars_space(self):
        assert _validate_username("user 01") == 10002

    def test_special_chars_at(self):
        assert _validate_username("user@001") == 10002

    def test_sensitive_admin(self):
        assert _validate_username("admin12345") == 10003

    def test_sensitive_root(self):
        assert _validate_username("rootuser01") == 10003

    def test_sensitive_case_insensitive(self):
        assert _validate_username("ADMIN12345") == 10003

    def test_empty_string(self):
        assert _validate_username("") == 10002


class TestValidatePassword:
    """_validate_password 密码校验"""

    def test_valid_password(self):
        assert _validate_password("pass1234", "player0001") is None

    def test_valid_password_complex(self):
        assert _validate_password("Aa1Bb2Cc3", "player0001") is None

    def test_valid_exactly_8_chars(self):
        assert _validate_password("abcdef12", "player0001") is None

    def test_valid_exactly_20_chars(self):
        assert _validate_password("a1b2c3d4e5f6g7h8i9j0", "player0001") is None

    def test_too_short(self):
        assert _validate_password("pass1", "player0001") == 10005

    def test_too_long(self):
        assert _validate_password("a1" * 11, "player0001") == 10005

    def test_no_letter(self):
        assert _validate_password("12345678", "player0001") == 10005

    def test_no_digit(self):
        assert _validate_password("abcdefgh", "player0001") == 10005

    def test_same_as_username(self):
        assert _validate_password("player0001", "player0001") == 10007

    def test_same_as_username_case_insensitive(self):
        assert _validate_password("PLAYER0001", "player0001") == 10007


class TestGetTimePeriod:
    """_get_time_period 时段判断"""

    def test_morning_7(self):
        assert _get_time_period(7) == "morning"

    def test_morning_8(self):
        assert _get_time_period(8) == "morning"

    def test_morning_9(self):
        assert _get_time_period(9) == "morning"

    def test_evening_20(self):
        assert _get_time_period(20) == "evening"

    def test_evening_21(self):
        assert _get_time_period(21) == "evening"

    def test_evening_22(self):
        assert _get_time_period(22) == "evening"

    def test_other_0(self):
        assert _get_time_period(0) == "other"

    def test_other_6(self):
        assert _get_time_period(6) == "other"

    def test_other_10(self):
        assert _get_time_period(10) == "other"

    def test_other_12(self):
        assert _get_time_period(12) == "other"

    def test_other_19(self):
        assert _get_time_period(19) == "other"

    def test_other_23(self):
        assert _get_time_period(23) == "other"


class TestPasswordHashing:
    """_hash_password / _verify_password 密码哈希"""

    def test_hash_and_verify(self):
        hashed = _hash_password("mypassword1")
        assert _verify_password("mypassword1", hashed) is True

    def test_wrong_password_fails(self):
        hashed = _hash_password("mypassword1")
        assert _verify_password("wrongpasswd", hashed) is False

    def test_hash_is_different_each_time(self):
        """bcrypt 每次生成不同盐值"""
        h1 = _hash_password("samepassword1")
        h2 = _hash_password("samepassword1")
        assert h1 != h2

    def test_hash_not_plaintext(self):
        hashed = _hash_password("mypassword1")
        assert hashed != "mypassword1"
        assert len(hashed) > 20


# ==================== 完整流程集成测试 ====================


class TestIntegrationFlow:
    """端到端业务流程"""

    @pytest.mark.asyncio
    async def test_register_login_logout_flow(self, client: AsyncClient):
        """注册 → 登录 → 登出 完整流程"""
        reg = await _register(client)
        assert reg["code"] == 0

        login_data = await _login(client)
        assert login_data["code"] == 0
        token = login_data["data"]["token"]

        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_register_reset_login_flow(self, client: AsyncClient):
        """注册 → 重置密码 → 用新密码登录"""
        await _register(client)

        resp = await client.post("/api/auth/reset-password", json={
            "username": _DEFAULT_USER,
            "new_password": "newpass99",
            "confirm_password": "newpass99",
        })
        assert resp.json()["code"] == 0

        old_login = await _login(client, password=_DEFAULT_PASS)
        assert old_login["code"] == 10009

        new_login = await _login(client, password="newpass99")
        assert new_login["code"] == 0

    @pytest.mark.asyncio
    async def test_lock_does_not_affect_other_users(self, client: AsyncClient):
        """A用户被锁不影响B用户登录"""
        await _register(client, username="player0001")
        await _register(client, username="player0002")

        for _ in range(5):
            await _login(client, username="player0001", password="wrongpass1")

        d1 = await _login(client, username="player0001")
        assert d1["code"] == 10010

        d2 = await _login(client, username="player0002")
        assert d2["code"] == 0

    @pytest.mark.asyncio
    async def test_multiple_users_independent_login_logs(self, client: AsyncClient):
        """不同用户的登录日志互不影响"""
        r1 = await _register(client, username="player0001")
        r2 = await _register(client, username="player0002")
        uid1 = r1["data"]["user_id"]
        uid2 = r2["data"]["user_id"]

        await _login(client, username="player0001")
        await _login(client, username="player0001")
        await _login(client, username="player0002")

        from backend.models.login_log import LoginLog
        async with async_session_test() as session:
            result1 = await session.execute(
                select(LoginLog).where(LoginLog.user_id == uid1)
            )
            result2 = await session.execute(
                select(LoginLog).where(LoginLog.user_id == uid2)
            )
            assert len(result1.scalars().all()) == 2
            assert len(result2.scalars().all()) == 1
