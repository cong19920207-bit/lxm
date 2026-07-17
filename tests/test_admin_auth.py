# -*- coding: utf-8 -*-
# 后台认证模块测试

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import bcrypt
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import mysql
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


# mock 掉 scheduler 模块
if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.main import app  # noqa: E402
from backend.constants import (  # noqa: E402
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF,
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER,
    ADMIN_ERR_AUTH_LOGIN_FAILED,
    ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH,
    ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD,
    ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG,
    ADMIN_ERR_AUTH_PASSWORD_POLICY,
)
from backend.models.admin_user import AdminUser  # noqa: E402

app.dependency_overrides[get_db] = override_get_db

# 测试用管理员账号信息
_SUPER_ADMIN_USER = "superadmin"
_SUPER_ADMIN_PASS = "Super@Admin123!"
_OPS_ADMIN_USER = "opsadmin01"
_OPS_ADMIN_PASS = "Ops@Admin12345"
_AI_TRAINER_USER = "aitrainer01"
_AI_TRAINER_PASS = "Ai@Trainer1234"


def _hash_password(password: str) -> str:
    """bcrypt 加盐哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def _create_admin(
    username: str = _SUPER_ADMIN_USER,
    password: str = _SUPER_ADMIN_PASS,
    role: str = "super_admin",
    *,
    is_active: bool = True,
    is_locked: bool = False,
    token_version: int = 0,
) -> int:
    """在数据库中直接创建管理员账号"""
    async with async_session_test() as session:
        admin = AdminUser(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            is_active=is_active,
            is_locked=is_locked,
            login_fail_count=0,
            token_version=token_version,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin.id


async def _admin_login(
    client: AsyncClient,
    username: str = _SUPER_ADMIN_USER,
    password: str = _SUPER_ADMIN_PASS,
) -> dict:
    """辅助：后台登录并返回响应JSON"""
    resp = await client.post("/api/admin/auth/login", json={
        "username": username,
        "password": password,
    })
    return resp.json()


def _assert_uniform_login_failure(response_json: dict) -> None:
    assert response_json == {
        "code": ADMIN_ERR_AUTH_LOGIN_FAILED,
        "data": None,
        "message": "账号或密码错误",
    }


async def _get_token(
    client: AsyncClient,
    username: str = _SUPER_ADMIN_USER,
    password: str = _SUPER_ADMIN_PASS,
) -> str:
    """辅助：后台登录并返回Token"""
    data = await _admin_login(client, username, password)
    return data["data"]["token"]


async def _get_admin_state(username: str = _SUPER_ADMIN_USER) -> AdminUser:
    async with async_session_test() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one()


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


# ==================== 登录测试 ====================


class TestAdminLogin:
    """POST /api/admin/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """正确账号密码登录成功"""
        await _create_admin()
        data = await _admin_login(client)
        assert data["code"] == 0
        assert data["data"]["username"] == _SUPER_ADMIN_USER
        assert data["data"]["role"] == "super_admin"
        assert "token" in data["data"]
        assert isinstance(data["data"]["need_change_password"], bool)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """密码错误仅返回统一失败信封。"""
        await _create_admin()
        data = await _admin_login(client, password="WrongPass123!")
        _assert_uniform_login_failure(data)

    @pytest.mark.asyncio
    async def test_login_wrong_password_count_is_internal_only(self, client: AsyncClient):
        """密码错误次数内部递增，但响应不暴露剩余次数。"""
        await _create_admin()
        for _ in range(4):
            data = await _admin_login(client, password="WrongPass123!")
            _assert_uniform_login_failure(data)

        state = await _get_admin_state()
        assert state.login_fail_count == 4
        assert state.is_locked is False

    @pytest.mark.asyncio
    async def test_login_lock_after_5_failures(self, client: AsyncClient):
        """5次错误后账号锁定"""
        await _create_admin()
        for i in range(4):
            d = await _admin_login(client, password="WrongPass123!")
            _assert_uniform_login_failure(d)

        # 第5次触发锁定
        d5 = await _admin_login(client, password="WrongPass123!")
        _assert_uniform_login_failure(d5)

        state = await _get_admin_state()
        assert state.is_locked is True
        assert state.login_fail_count == 5
        assert state.token_version == 1

    @pytest.mark.asyncio
    async def test_login_locked_account(self, client: AsyncClient):
        """锁定后无法登录（即使密码正确）"""
        await _create_admin()
        # 触发锁定
        for _ in range(5):
            await _admin_login(client, password="WrongPass123!")

        # 正确密码也无法登录
        data = await _admin_login(client)
        _assert_uniform_login_failure(data)

    @pytest.mark.asyncio
    async def test_login_locked_no_count_update(self, client: AsyncClient):
        """锁定后不验证密码、不更新login_fail_count"""
        await _create_admin()
        for _ in range(5):
            await _admin_login(client, password="WrongPass123!")

        # 锁定后再尝试，响应仍保持统一。
        d1 = await _admin_login(client, password="WrongPass123!")
        _assert_uniform_login_failure(d1)
        d2 = await _admin_login(client, password="WrongPass123!")
        _assert_uniform_login_failure(d2)

        # 正确密码同样不得再次改变锁定状态。
        d3 = await _admin_login(client)
        _assert_uniform_login_failure(d3)

        state = await _get_admin_state()
        assert state.is_locked is True
        assert state.login_fail_count == 5
        assert state.token_version == 1

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """不存在的用户名"""
        data = await _admin_login(client, username="nobody", password="Whatever123!")
        _assert_uniform_login_failure(data)

    @pytest.mark.asyncio
    async def test_inactive_account_uses_uniform_failure(self, client: AsyncClient):
        await _create_admin(is_active=False)

        data = await _admin_login(client)

        _assert_uniform_login_failure(data)

    @pytest.mark.asyncio
    async def test_nonexistent_account_runs_dummy_bcrypt_check(self, client: AsyncClient):
        from backend.routers.admin import auth as auth_router

        with patch.object(
            auth_router,
            "_verify_password",
            wraps=auth_router._verify_password,
        ) as verify:
            data = await _admin_login(
                client,
                username="nobody",
                password="SubmittedCredential123!",
            )

        _assert_uniform_login_failure(data)
        verify.assert_called_once_with(
            "SubmittedCredential123!",
            auth_router._DUMMY_PASSWORD_HASH,
        )

    @pytest.mark.asyncio
    async def test_failure_security_logs_distinguish_reason_without_credentials(
        self, client: AsyncClient, caplog
    ):
        caplog.set_level("WARNING", logger="security.admin_auth")
        await _create_admin(
            username="wrongpass01",
            password="Wrong@Target123!",
        )
        await _create_admin(
            username="lockeduser01",
            password="Locked@Target123!",
            is_locked=True,
        )
        await _create_admin(
            username="inactive01",
            password="Inactive@Target123!",
            is_active=False,
        )

        submitted_password = "CredentialMustNeverAppear123!"
        cases = [
            ("missing01", submitted_password),
            ("wrongpass01", submitted_password),
            ("lockeduser01", "Locked@Target123!"),
            ("inactive01", "Inactive@Target123!"),
        ]
        for username, password in cases:
            data = await _admin_login(client, username=username, password=password)
            _assert_uniform_login_failure(data)

        assert "reason=account_not_found" in caplog.text
        assert "reason=password_wrong" in caplog.text
        assert "reason=account_locked" in caplog.text
        assert "reason=account_inactive" in caplog.text
        for _, password in cases:
            assert password not in caplog.text

    @pytest.mark.asyncio
    async def test_login_correct_after_failures_resets_count(self, client: AsyncClient):
        """错误几次后正确登录，重置失败计数"""
        await _create_admin()
        for _ in range(4):
            await _admin_login(client, password="WrongPass123!")

        data = await _admin_login(client)
        assert data["code"] == 0

        state = await _get_admin_state()
        assert state.login_fail_count == 0
        assert state.is_locked is False
        assert state.token_version == 0

        # 再次错误应从头计数
        d = await _admin_login(client, password="WrongPass123!")
        _assert_uniform_login_failure(d)

    def test_login_query_uses_mysql_for_update(self):
        from backend.routers.admin import auth as auth_router

        stmt = auth_router._build_admin_login_query(_SUPER_ADMIN_USER)
        sql = str(stmt.compile(dialect=mysql.dialect()))

        assert "FOR UPDATE" in sql

    @pytest.mark.asyncio
    async def test_login_writes_operation_log(self, client: AsyncClient):
        """登录成功后写入操作日志"""
        await _create_admin()
        await _admin_login(client)

        from backend.models.admin_operation_log import AdminOperationLog
        async with async_session_test() as session:
            stmt = select(AdminOperationLog).where(
                AdminOperationLog.action == "login"
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()
            assert len(logs) == 1
            assert logs[0].admin_username == _SUPER_ADMIN_USER
            assert logs[0].module == "系统"


# ==================== 解锁测试 ====================


class TestUnlockAccount:
    """POST /api/admin/accounts/{id}/unlock"""

    @pytest.mark.asyncio
    async def test_unlock_account(self, client: AsyncClient):
        """super_admin可以解锁账号"""
        await _create_admin()
        await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )

        # 锁定ops_admin
        for _ in range(5):
            await _admin_login(client, username=_OPS_ADMIN_USER, password="WrongPass!")

        # 确认被锁定
        d = await _admin_login(client, username=_OPS_ADMIN_USER, password=_OPS_ADMIN_PASS)
        _assert_uniform_login_failure(d)

        # super_admin解锁
        token = await _get_token(client)
        # 先获取账号列表找到ops_admin的id
        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        accounts = resp.json()["data"]
        ops_id = None
        for acc in accounts:
            if acc["username"] == _OPS_ADMIN_USER:
                ops_id = acc["id"]
                break
        assert ops_id is not None

        resp = await client.post(
            f"/api/admin/accounts/{ops_id}/unlock",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

        # 解锁后可以登录
        d2 = await _admin_login(client, username=_OPS_ADMIN_USER, password=_OPS_ADMIN_PASS)
        assert d2["code"] == 0


# ==================== 角色权限测试 ====================


class TestRequireRole:
    """角色权限校验"""

    @pytest.mark.asyncio
    async def test_require_role_403(self, client: AsyncClient):
        """无权限角色访问返回403"""
        await _create_admin(
            username=_AI_TRAINER_USER,
            password=_AI_TRAINER_PASS,
            role="ai_trainer",
        )

        token = await _get_token(client, _AI_TRAINER_USER, _AI_TRAINER_PASS)

        # ai_trainer 无权访问账号管理接口（需要super_admin）
        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_can_access_accounts(self, client: AsyncClient):
        """super_admin可以访问账号管理接口"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_ai_trainer_no_logs_access(self, client: AsyncClient):
        """ai_trainer无操作日志查看权限"""
        await _create_admin(
            username=_AI_TRAINER_USER,
            password=_AI_TRAINER_PASS,
            role="ai_trainer",
        )
        token = await _get_token(client, _AI_TRAINER_USER, _AI_TRAINER_PASS)

        resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_ops_admin_can_view_logs(self, client: AsyncClient):
        """ops_admin可以查看操作日志"""
        await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        token = await _get_token(client, _OPS_ADMIN_USER, _OPS_ADMIN_PASS)

        resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0


# ==================== Token隔离测试 ====================


class TestTokenIsolation:
    """后台Token与用户端Token隔离"""

    @pytest.mark.asyncio
    async def test_admin_token_not_accepted_as_user(self, client: AsyncClient):
        """后台Token不能用于用户端接口"""
        await _create_admin()
        token = await _get_token(client)

        # 用后台Token访问用户端需鉴权接口（如登出）
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        # 用户端verify_token不认后台Token，应返回401
        assert resp.status_code == 401


class TestAdminTokenVersion:
    """Admin JWT 必须与数据库实时 token_version 一致。"""

    @staticmethod
    def _raw_token(admin_id: int, token_version=...):
        from backend.config import get_admin_jwt_secret, get_jwt_algorithm

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(admin_id),
            "role": "super_admin",
            "type": "admin",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        if token_version is not ...:
            payload["token_version"] = token_version
        return jwt.encode(payload, get_admin_jwt_secret(), algorithm=get_jwt_algorithm())

    @pytest.mark.asyncio
    async def test_login_token_contains_integer_version_and_is_accepted(self, client):
        await _create_admin(token_version=0)

        token = await _get_token(client)
        from backend.config import get_admin_jwt_secret, get_jwt_algorithm
        payload = jwt.decode(
            token,
            get_admin_jwt_secret(),
            algorithms=[get_jwt_algorithm()],
        )
        assert payload["token_version"] == 0
        assert type(payload["token_version"]) is int

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_version", [..., "0", 1])
    async def test_missing_non_integer_or_mismatched_version_returns_401(
        self, client, token_version
    ):
        admin_id = await _create_admin(token_version=0)
        token = self._raw_token(admin_id, token_version)

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("admin_id", "is_active", "is_locked"),
        [(999999, True, False), (None, False, False), (None, True, True)],
    )
    async def test_missing_inactive_or_locked_account_returns_401(
        self, client, admin_id, is_active, is_locked
    ):
        if admin_id is None:
            admin_id = await _create_admin(
                is_active=is_active,
                is_locked=is_locked,
                token_version=0,
            )
        token = self._raw_token(admin_id, 0)

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_user_token_not_accepted_as_admin(self, client: AsyncClient):
        """用户端Token不能用于后台接口"""
        from backend.utils.jwt_handler import create_token

        user_token = create_token(user_id=1, expire_days=1)

        resp = await client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        # 后台verify_admin_token不认用户端Token，应返回401
        assert resp.status_code == 401


# ==================== 登出撤销测试 ====================


class TestAdminLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_all_same_account_tokens_only(self, client: AsyncClient):
        await _create_admin()
        await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        token_one = await _get_token(client)
        token_two = await _get_token(client)
        other_admin_token = await _get_token(
            client,
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
        )

        logout = await client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": f"Bearer {token_one}"},
        )

        assert logout.status_code == 200
        assert logout.json() == {"code": 0, "data": None, "message": "已退出登录"}
        state = await _get_admin_state()
        assert state.token_version == 1

        for old_token in (token_one, token_two):
            old_resp = await client.get(
                "/api/admin/accounts",
                headers={"Authorization": f"Bearer {old_token}"},
            )
            assert old_resp.status_code == 401

        other_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {other_admin_token}"},
        )
        assert other_resp.status_code == 200
        assert other_resp.json()["code"] == 0

        new_token = await _get_token(client)
        new_resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert new_resp.status_code == 200
        assert new_resp.json()["code"] == 0

        from backend.models.admin_operation_log import AdminOperationLog
        async with async_session_test() as session:
            result = await session.execute(
                select(AdminOperationLog).where(AdminOperationLog.action == "logout")
            )
            logout_logs = result.scalars().all()
        assert len(logout_logs) == 1
        assert logout_logs[0].admin_username == _SUPER_ADMIN_USER

    def test_logout_ui_clears_session_after_request_then_redirects(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "admin/static/js/admin-api.js"
        ).read_text(encoding="utf-8")
        start = script.index("async function handleAdminLogout()")
        section = script[start:script.index("// ─── 分页器渲染", start)]

        assert section.index("await adminRequest('POST', '/api/admin/auth/logout');") < section.index(
            "clearAdminToken();"
        ) < section.index("window.location.href = '/admin/pages/login.html';")


class TestStep020CorsOptionsBoundary:
    """STEP-020：匿名 OPTIONS 仅由 CORS 中间件处理。"""

    @staticmethod
    def _preflight_headers(method: str = "POST") -> dict[str, str]:
        return {
            "Origin": "https://admin.example.test",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        }

    @pytest.mark.asyncio
    async def test_anonymous_preflight_returns_only_cors_response(self, client):
        response = await client.options(
            "/api/admin/accounts",
            headers=self._preflight_headers(),
        )

        assert response.status_code == 200
        assert response.text == "OK"
        assert response.headers["access-control-allow-origin"] == (
            "https://admin.example.test"
        )
        assert "POST" in response.headers["access-control-allow-methods"]
        assert response.headers["content-type"].startswith("text/plain")
        assert "data" not in response.text.lower()

    @pytest.mark.asyncio
    async def test_business_methods_still_require_admin_authentication(self, client):
        get_response = await client.get("/api/admin/accounts")
        post_response = await client.post("/api/admin/accounts", json={})

        assert get_response.status_code == 401
        assert post_response.status_code == 401

        # 当前生产路由没有显式 HEAD 端点；用同一统一依赖验证未来
        # HEAD 端点不会因为 OPTIONS 的匿名边界而跳过 Admin JWT。
        from fastapi import Depends, FastAPI

        from backend.utils.admin_auth import get_current_admin

        probe_app = FastAPI()

        @probe_app.head("/api/admin/probe")
        async def _head_probe(_admin=Depends(get_current_admin)):
            return None

        async with AsyncClient(
            transport=ASGITransport(app=probe_app),
            base_url="http://step020",
        ) as probe_client:
            head_response = await probe_client.head("/api/admin/probe")

        assert head_response.status_code == 401

    @pytest.mark.asyncio
    async def test_preflight_does_not_enter_write_endpoint_or_change_accounts(
        self,
        client,
    ):
        await _create_admin()
        before = await _get_admin_state()

        response = await client.request(
            "OPTIONS",
            "/api/admin/accounts",
            headers=self._preflight_headers(),
            json={
                "username": "must-not-be-created",
                "password": "NeverCreated123!",
                "role": "observer",
            },
        )

        after = await _get_admin_state()
        async with async_session_test() as session:
            all_admins = (await session.execute(select(AdminUser))).scalars().all()

        assert response.status_code == 200
        assert response.text == "OK"
        assert len(all_admins) == 1
        assert after.id == before.id
        assert after.token_version == before.token_version


# ==================== 修改密码测试 ====================


class TestChangePassword:
    """POST /api/admin/auth/change-password"""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client: AsyncClient):
        """改密递增版本并撤销同账号全部旧 Token，新密码新 Token 可用。"""
        await _create_admin()
        token_one = await _get_token(client)
        token_two = await _get_token(client)

        new_pass = "NewSuper@Pass1!"
        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": _SUPER_ADMIN_PASS,
                "new_password": new_pass,
                "confirm_password": new_pass,
            },
            headers={"Authorization": f"Bearer {token_one}"},
        )
        assert resp.json()["code"] == 0

        state = await _get_admin_state()
        assert state.token_version == 1

        for old_token in (token_one, token_two):
            old_resp = await client.get(
                "/api/admin/accounts",
                headers={"Authorization": f"Bearer {old_token}"},
            )
            assert old_resp.status_code == 401

        # 用新密码可以登录
        new_token = await _get_token(client, password=new_pass)
        protected = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert protected.status_code == 200
        assert protected.json()["code"] == 0

        from backend.config import get_admin_jwt_secret, get_jwt_algorithm
        payload = jwt.decode(
            new_token,
            get_admin_jwt_secret(),
            algorithms=[get_jwt_algorithm()],
        )
        assert payload["token_version"] == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("request_json", "expected_code"),
        [
            (
                {
                    "old_password": "WrongOldPass1!",
                    "new_password": "NewSuper@Pass1!",
                    "confirm_password": "NewSuper@Pass1!",
                },
                ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG,
            ),
            (
                {
                    "old_password": _SUPER_ADMIN_PASS,
                    "new_password": _SUPER_ADMIN_PASS,
                    "confirm_password": _SUPER_ADMIN_PASS,
                },
                ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD,
            ),
            (
                {
                    "old_password": _SUPER_ADMIN_PASS,
                    "new_password": "NewSuper@Pass1!",
                    "confirm_password": "DiffSuper@Pass1!",
                },
                ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH,
            ),
            (
                {
                    "old_password": _SUPER_ADMIN_PASS,
                    "new_password": "weak",
                    "confirm_password": "weak",
                },
                ADMIN_ERR_AUTH_PASSWORD_POLICY,
            ),
        ],
    )
    async def test_change_password_failures_leave_password_and_version_unchanged(
        self, client: AsyncClient, request_json, expected_code
    ):
        await _create_admin(token_version=7)
        token = await _get_token(client)
        before = await _get_admin_state()
        before_hash = before.password_hash

        resp = await client.post(
            "/api/admin/auth/change-password",
            json=request_json,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.json()["code"] == expected_code
        after = await _get_admin_state()
        assert after.password_hash == before_hash
        assert after.token_version == 7

    def test_change_password_ui_clears_session_before_login_redirect(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "admin/static/js/admin-api.js"
        ).read_text(encoding="utf-8")
        success_block_start = script.index("if (result && result.code === 0)")
        logout_section_start = script.index("// ─── 退出登录", success_block_start)
        success_block = script[success_block_start:logout_section_start]

        assert success_block.index("clearAdminToken();") < success_block.index(
            "window.location.href = '/admin/pages/login.html';"
        )

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, client: AsyncClient):
        """旧密码错误"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": "WrongOldPass1!",
                "new_password": "NewSuper@Pass1!",
                "confirm_password": "NewSuper@Pass1!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG
        assert "旧密码" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_change_password_same_as_old(self, client: AsyncClient):
        """新密码与旧密码相同"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": _SUPER_ADMIN_PASS,
                "new_password": _SUPER_ADMIN_PASS,
                "confirm_password": _SUPER_ADMIN_PASS,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD

    @pytest.mark.asyncio
    async def test_change_password_mismatch(self, client: AsyncClient):
        """两次新密码不一致"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": _SUPER_ADMIN_PASS,
                "new_password": "NewSuper@Pass1!",
                "confirm_password": "DiffSuper@Pass1!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH

    @pytest.mark.asyncio
    async def test_change_password_too_weak(self, client: AsyncClient):
        """新密码强度不够"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": _SUPER_ADMIN_PASS,
                "new_password": "weak",
                "confirm_password": "weak",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_AUTH_PASSWORD_POLICY


# ==================== 账号管理测试 ====================


class TestAccountManagement:
    """账号管理接口"""

    @pytest.mark.asyncio
    async def test_create_account(self, client: AsyncClient):
        """创建新账号"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.post(
            "/api/admin/accounts",
            json={
                "username": "newadmin01",
                "password": "NewAdmin@12345",
                "role": "ops_admin",
                "remark": "测试账号",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["username"] == "newadmin01"

    @pytest.mark.asyncio
    async def test_delete_super_admin_forbidden(self, client: AsyncClient):
        """不可删除super_admin"""
        await _create_admin()
        await _create_admin(username="super2", password="Super@Admin222!", role="super_admin")
        token = await _get_token(client)

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        accounts = resp.json()["data"]
        target_id = None
        for acc in accounts:
            if acc["username"] == "super2":
                target_id = acc["id"]
                break

        resp = await client.delete(
            f"/api/admin/accounts/{target_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER
        assert "不可删除" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_cannot_delete_self(self, client: AsyncClient):
        """不可删除自己"""
        await _create_admin()
        token = await _get_token(client)

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        accounts = resp.json()["data"]
        self_id = None
        for acc in accounts:
            if acc["username"] == _SUPER_ADMIN_USER:
                self_id = acc["id"]
                break

        resp = await client.delete(
            f"/api/admin/accounts/{self_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF

    @pytest.mark.asyncio
    async def test_reset_password_returns_new_password(self, client: AsyncClient):
        """重置密码递增目标版本并撤销旧会话。"""
        await _create_admin()
        await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        token = await _get_token(client)
        old_target_token = await _get_token(
            client,
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
        )

        resp = await client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        accounts = resp.json()["data"]
        ops_id = None
        for acc in accounts:
            if acc["username"] == _OPS_ADMIN_USER:
                ops_id = acc["id"]
                break

        resp = await client.post(
            f"/api/admin/accounts/{ops_id}/reset-password",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0
        new_pass = resp.json()["data"]["new_password"]
        assert len(new_pass) == 16

        target_state = await _get_admin_state(_OPS_ADMIN_USER)
        assert target_state.token_version == 1
        old_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {old_target_token}"},
        )
        assert old_resp.status_code == 401

        # 用新密码可以登录
        new_token = await _get_token(client, username=_OPS_ADMIN_USER, password=new_pass)
        new_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert new_resp.status_code == 200
        assert new_resp.json()["code"] == 0


class TestStep019ObserverMethodGate:
    """STEP-019：observer 写方法总闸与两个精确自助 POST 例外。"""

    @staticmethod
    def _build_probe_app():
        from fastapi import Depends, FastAPI, Request

        from backend.utils.admin_auth import get_current_admin

        probe_app = FastAPI()
        probe_app.dependency_overrides[get_db] = override_get_db
        entered = {
            "GET": 0,
            "HEAD": 0,
            "POST": 0,
            "PUT": 0,
            "PATCH": 0,
            "DELETE": 0,
            "logout": 0,
            "change-password": 0,
            "similar": 0,
            "logout-put": 0,
        }

        @probe_app.api_route(
            "/api/admin/gate-probe",
            methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
        )
        async def gate_probe(
            request: Request,
            admin_user: AdminUser = Depends(get_current_admin),
        ):
            entered[request.method] += 1
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                admin_user.remark = f"entered-{request.method}"
            return {"role": admin_user.role}

        @probe_app.post("/api/admin/auth/logout")
        async def logout_probe(
            admin_user: AdminUser = Depends(get_current_admin),
        ):
            entered["logout"] += 1
            return {"role": admin_user.role}

        @probe_app.put("/api/admin/auth/logout")
        async def logout_wrong_method_probe(
            admin_user: AdminUser = Depends(get_current_admin),
        ):
            entered["logout-put"] += 1
            return {"role": admin_user.role}

        @probe_app.post("/api/admin/auth/change-password")
        async def change_password_probe(
            admin_user: AdminUser = Depends(get_current_admin),
        ):
            entered["change-password"] += 1
            return {"role": admin_user.role}

        @probe_app.post("/api/admin/auth/logout/extra")
        async def similar_path_probe(
            admin_user: AdminUser = Depends(get_current_admin),
        ):
            entered["similar"] += 1
            return {"role": admin_user.role}

        return probe_app, entered

    @staticmethod
    def _raw_observer_token(
        admin_id: int,
        *,
        token_version=0,
        expires_delta: timedelta = timedelta(hours=1),
        secret: str | None = None,
    ) -> str:
        from backend.config import get_admin_jwt_secret, get_jwt_algorithm

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(admin_id),
            "role": "observer",
            "type": "admin",
            "iat": now,
            "exp": now + expires_delta,
        }
        if token_version is not ...:
            payload["token_version"] = token_version
        return jwt.encode(
            payload,
            secret or get_admin_jwt_secret(),
            algorithm=get_jwt_algorithm(),
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    async def test_observer_write_methods_are_blocked_before_endpoint(
        self, client, method
    ):
        await _create_admin(
            username="observer-gate",
            password="Observer@Gate123",
            role="observer",
        )
        token = await _get_token(
            client,
            username="observer-gate",
            password="Observer@Gate123",
        )
        probe_app, entered = self._build_probe_app()

        async with AsyncClient(
            transport=ASGITransport(app=probe_app),
            base_url="http://probe",
        ) as probe:
            response = await probe.request(
                method,
                "/api/admin/gate-probe",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        assert entered[method] == 0
        state = await _get_admin_state("observer-gate")
        assert state.remark is None

    @pytest.mark.asyncio
    async def test_only_exact_auth_post_paths_are_exempt(self, client):
        await _create_admin(
            username="observer-exact",
            password="Observer@Exact123",
            role="observer",
        )
        token = await _get_token(
            client,
            username="observer-exact",
            password="Observer@Exact123",
        )
        probe_app, entered = self._build_probe_app()
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=probe_app),
            base_url="http://probe",
        ) as probe:
            logout = await probe.post("/api/admin/auth/logout?source=test", headers=headers)
            change = await probe.post("/api/admin/auth/change-password", headers=headers)
            similar = await probe.post("/api/admin/auth/logout/extra", headers=headers)
            wrong_method = await probe.put("/api/admin/auth/logout", headers=headers)

        assert logout.status_code == 200
        assert change.status_code == 200
        assert similar.status_code == 403
        assert wrong_method.status_code == 403
        assert entered == {
            **{key: 0 for key in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")},
            "logout": 1,
            "change-password": 1,
            "similar": 0,
            "logout-put": 0,
        }

    @pytest.mark.asyncio
    async def test_real_self_service_endpoints_enter_existing_business_validation(
        self, client
    ):
        await _create_admin(
            username="observer-self",
            password="Observer@Self123",
            role="observer",
        )
        token = await _get_token(
            client,
            username="observer-self",
            password="Observer@Self123",
        )
        headers = {"Authorization": f"Bearer {token}"}

        change = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": "Wrong@Password123",
                "new_password": "NewObserver@123",
                "confirm_password": "NewObserver@123",
            },
            headers=headers,
        )
        logout = await client.post("/api/admin/auth/logout", headers=headers)

        assert change.status_code == 200
        assert change.json()["code"] == ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG
        assert logout.status_code == 200
        assert logout.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_invalid_identity_returns_401_before_observer_method_rule(self):
        active_id = await _create_admin(
            username="observer-active",
            password="Observer@Active123",
            role="observer",
        )
        locked_id = await _create_admin(
            username="observer-locked",
            password="Observer@Locked123",
            role="observer",
            is_locked=True,
        )
        inactive_id = await _create_admin(
            username="observer-inactive",
            password="Observer@Inactive123",
            role="observer",
            is_active=False,
        )
        probe_app, entered = self._build_probe_app()
        invalid_tokens = [
            self._raw_observer_token(
                active_id,
                secret="forged-admin-secret-that-is-long-enough-20260716",
            ),
            self._raw_observer_token(
                active_id,
                expires_delta=timedelta(seconds=-1),
            ),
            self._raw_observer_token(active_id, token_version=...),
            self._raw_observer_token(active_id, token_version=1),
            self._raw_observer_token(locked_id),
            self._raw_observer_token(inactive_id),
        ]

        async with AsyncClient(
            transport=ASGITransport(app=probe_app),
            base_url="http://probe",
        ) as probe:
            responses = [
                await probe.post(
                    "/api/admin/gate-probe",
                    headers={"Authorization": f"Bearer {token}"},
                )
                for token in invalid_tokens
            ]

        assert [response.status_code for response in responses] == [401] * 6
        assert entered["POST"] == 0

    @pytest.mark.asyncio
    async def test_observer_get_head_continue_and_non_observer_write_is_unchanged(
        self, client
    ):
        await _create_admin(
            username="observer-read",
            password="Observer@Read123",
            role="observer",
        )
        await _create_admin(
            username="ops-write",
            password="Ops@Write12345",
            role="ops_admin",
        )
        observer_token = await _get_token(
            client,
            username="observer-read",
            password="Observer@Read123",
        )
        ops_token = await _get_token(
            client,
            username="ops-write",
            password="Ops@Write12345",
        )
        probe_app, entered = self._build_probe_app()

        async with AsyncClient(
            transport=ASGITransport(app=probe_app),
            base_url="http://probe",
        ) as probe:
            get_response = await probe.get(
                "/api/admin/gate-probe",
                headers={"Authorization": f"Bearer {observer_token}"},
            )
            head_response = await probe.head(
                "/api/admin/gate-probe",
                headers={"Authorization": f"Bearer {observer_token}"},
            )
            ops_write = await probe.post(
                "/api/admin/gate-probe",
                headers={"Authorization": f"Bearer {ops_token}"},
            )

        assert get_response.status_code == 200
        assert head_response.status_code == 200
        assert ops_write.status_code == 200
        assert entered["GET"] == 1
        assert entered["HEAD"] == 1
        assert entered["POST"] == 1
        ops_state = await _get_admin_state("ops-write")
        assert ops_state.remark == "entered-POST"


class TestStep018ObserverRole:
    """STEP-018：observer 仅扩展为合法账号角色，账号管理仍仅 super_admin。"""

    @pytest.mark.parametrize(
        "role",
        ["super_admin", "ops_admin", "ai_trainer", "tech_ops", "observer"],
    )
    def test_account_schemas_accept_five_roles(self, role):
        from backend.schemas.admin_auth import (
            AdminCreateAccountRequest,
            AdminUpdateAccountRequest,
        )

        created = AdminCreateAccountRequest(
            username="schema-admin",
            password="Schema@Admin123",
            role=role,
        )
        updated = AdminUpdateAccountRequest(role=role)

        assert created.role == role
        assert updated.role == role

    def test_model_comment_and_accounts_page_expose_observer_only_in_account_ui(self):
        page = (
            Path(__file__).resolve().parents[1]
            / "admin/pages/accounts.html"
        ).read_text(encoding="utf-8")
        common_admin_script = (
            Path(__file__).resolve().parents[1]
            / "admin/static/js/admin-api.js"
        ).read_text(encoding="utf-8")

        assert "observer" in (AdminUser.__table__.c.role.comment or "")
        assert page.count('<option value="observer">观察者</option>') == 2
        assert "observer: { cls: 'tag tag-default', text: '观察者' }" in page
        # STEP-029 按既定顺序在公共 Header 加入 observer 展示名；
        # 本 STEP-018 回归只约束账号管理页的角色选项与标签。
        assert "MENU_CONFIG.observer" in common_admin_script

    @pytest.mark.asyncio
    async def test_super_admin_can_manage_full_observer_account_lifecycle(self, client):
        await _create_admin()
        token = await _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/admin/accounts",
            json={
                "username": "observer01",
                "password": "Observer@Admin123",
                "role": "observer",
                "remark": "观察者账号",
            },
            headers=headers,
        )
        assert created.status_code == 200
        assert created.json()["code"] == 0
        observer_id = created.json()["data"]["id"]
        assert created.json()["data"]["role"] == "observer"

        changed = await client.put(
            f"/api/admin/accounts/{observer_id}",
            json={"role": "ops_admin"},
            headers=headers,
        )
        assert changed.json()["data"]["role"] == "ops_admin"
        changed_back = await client.put(
            f"/api/admin/accounts/{observer_id}",
            json={"role": "observer"},
            headers=headers,
        )
        assert changed_back.json()["data"]["role"] == "observer"

        reset = await client.post(
            f"/api/admin/accounts/{observer_id}/reset-password",
            headers=headers,
        )
        assert reset.json()["code"] == 0
        new_password = reset.json()["data"]["new_password"]

        async with async_session_test() as session:
            target = await session.get(AdminUser, observer_id)
            target.is_locked = True
            target.login_fail_count = 5
            await session.commit()

        unlocked = await client.post(
            f"/api/admin/accounts/{observer_id}/unlock",
            headers=headers,
        )
        assert unlocked.json()["code"] == 0
        observer_login = await _admin_login(
            client,
            username="observer01",
            password=new_password,
        )
        assert observer_login["code"] == 0
        assert observer_login["data"]["role"] == "observer"

        deleted = await client.delete(
            f"/api/admin/accounts/{observer_id}",
            headers=headers,
        )
        assert deleted.json()["code"] == 0
        async with async_session_test() as session:
            assert await session.get(AdminUser, observer_id) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("username", "password", "role"),
        [
            ("ops-step018", "Ops@Step018123", "ops_admin"),
            ("ai-step018", "Ai@Step0181234", "ai_trainer"),
            ("tech-step018", "Tech@Step01812", "tech_ops"),
            ("observer-step018", "Observer@Step018", "observer"),
        ],
    )
    async def test_non_super_roles_are_forbidden_from_every_account_api(
        self, client, username, password, role
    ):
        import asyncio

        account_id = await _create_admin(
            username=username,
            password=password,
            role=role,
        )
        token = await _get_token(client, username=username, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        requests = [
            client.get("/api/admin/accounts", headers=headers),
            client.post(
                "/api/admin/accounts",
                json={
                    "username": "forbidden-new",
                    "password": "Forbidden@Admin123",
                    "role": "observer",
                },
                headers=headers,
            ),
            client.put(
                f"/api/admin/accounts/{account_id}",
                json={"role": "observer"},
                headers=headers,
            ),
            client.post(
                f"/api/admin/accounts/{account_id}/reset-password",
                headers=headers,
            ),
            client.post(
                f"/api/admin/accounts/{account_id}/unlock",
                headers=headers,
            ),
            client.delete(
                f"/api/admin/accounts/{account_id}",
                headers=headers,
            ),
        ]

        responses = await asyncio.gather(*requests)
        assert [response.status_code for response in responses] == [403] * 6
        for response in responses:
            assert "data" not in response.json()


class TestAccountVersionMatrix:
    @pytest.mark.asyncio
    async def test_actual_role_change_increments_once_and_revokes_old_token(self, client):
        await _create_admin()
        target_id = await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        super_token = await _get_token(client)
        old_target_token = await _get_token(
            client,
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
        )

        resp = await client.put(
            f"/api/admin/accounts/{target_id}",
            json={"role": "ai_trainer", "remark": "实际角色变化"},
            headers={"Authorization": f"Bearer {super_token}"},
        )

        assert resp.json()["code"] == 0
        state = await _get_admin_state(_OPS_ADMIN_USER)
        assert state.role == "ai_trainer"
        assert state.remark == "实际角色变化"
        assert state.token_version == 1
        old_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {old_target_token}"},
        )
        assert old_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_remark_same_role_and_unlock_do_not_increment_or_revive_token(self, client):
        await _create_admin()
        target_id = await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        super_token = await _get_token(client)
        old_target_token = await _get_token(
            client,
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
        )

        remark_resp = await client.put(
            f"/api/admin/accounts/{target_id}",
            json={"remark": "只改备注"},
            headers={"Authorization": f"Bearer {super_token}"},
        )
        same_role_resp = await client.put(
            f"/api/admin/accounts/{target_id}",
            json={"role": "ops_admin"},
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert remark_resp.json()["code"] == 0
        assert same_role_resp.json()["code"] == 0
        state = await _get_admin_state(_OPS_ADMIN_USER)
        assert state.token_version == 0

        for _ in range(5):
            await _admin_login(
                client,
                username=_OPS_ADMIN_USER,
                password="WrongPass123!",
            )
        locked = await _get_admin_state(_OPS_ADMIN_USER)
        assert locked.is_locked is True
        assert locked.login_fail_count == 5
        assert locked.token_version == 1

        unlock = await client.post(
            f"/api/admin/accounts/{target_id}/unlock",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert unlock.json()["code"] == 0
        unlocked = await _get_admin_state(_OPS_ADMIN_USER)
        assert unlocked.is_locked is False
        assert unlocked.login_fail_count == 0
        assert unlocked.token_version == 1

        old_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {old_target_token}"},
        )
        assert old_resp.status_code == 401
        new_token = await _get_token(
            client,
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
        )
        new_resp = await client.get(
            "/api/admin/operation-logs",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert new_resp.status_code == 200
