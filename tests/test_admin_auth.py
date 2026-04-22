# -*- coding: utf-8 -*-
# 后台认证模块测试

import sys
from datetime import datetime, timedelta, timezone

import bcrypt
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


# mock 掉 scheduler 模块
if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.main import app  # noqa: E402
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
) -> None:
    """在数据库中直接创建管理员账号"""
    async with async_session_test() as session:
        admin = AdminUser(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()


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


async def _get_token(
    client: AsyncClient,
    username: str = _SUPER_ADMIN_USER,
    password: str = _SUPER_ADMIN_PASS,
) -> str:
    """辅助：后台登录并返回Token"""
    data = await _admin_login(client, username, password)
    return data["data"]["token"]


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
        """密码错误，返回剩余次数"""
        await _create_admin()
        data = await _admin_login(client, password="WrongPass123!")
        assert data["code"] == 1
        assert "还可尝试" in data["message"]
        assert "4" in data["message"]

    @pytest.mark.asyncio
    async def test_login_wrong_password_decreasing(self, client: AsyncClient):
        """密码错误次数递增，提示剩余次数递减"""
        await _create_admin()
        d1 = await _admin_login(client, password="WrongPass123!")
        assert "4" in d1["message"]
        d2 = await _admin_login(client, password="WrongPass123!")
        assert "3" in d2["message"]
        d3 = await _admin_login(client, password="WrongPass123!")
        assert "2" in d3["message"]
        d4 = await _admin_login(client, password="WrongPass123!")
        assert "1" in d4["message"]

    @pytest.mark.asyncio
    async def test_login_lock_after_5_failures(self, client: AsyncClient):
        """5次错误后账号锁定"""
        await _create_admin()
        for i in range(4):
            d = await _admin_login(client, password="WrongPass123!")
            assert d["code"] == 1
            assert "还可尝试" in d["message"]

        # 第5次触发锁定
        d5 = await _admin_login(client, password="WrongPass123!")
        assert d5["code"] == 1
        assert "锁定" in d5["message"]

    @pytest.mark.asyncio
    async def test_login_locked_account(self, client: AsyncClient):
        """锁定后无法登录（即使密码正确）"""
        await _create_admin()
        # 触发锁定
        for _ in range(5):
            await _admin_login(client, password="WrongPass123!")

        # 正确密码也无法登录
        data = await _admin_login(client)
        assert data["code"] == 1
        assert "锁定" in data["message"]

    @pytest.mark.asyncio
    async def test_login_locked_no_count_update(self, client: AsyncClient):
        """锁定后不验证密码、不更新login_fail_count"""
        await _create_admin()
        for _ in range(5):
            await _admin_login(client, password="WrongPass123!")

        # 锁定后再尝试，消息应稳定为"已锁定"
        d1 = await _admin_login(client, password="WrongPass123!")
        assert "锁定" in d1["message"]
        d2 = await _admin_login(client, password="WrongPass123!")
        assert "锁定" in d2["message"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """不存在的用户名"""
        data = await _admin_login(client, username="nobody", password="Whatever123!")
        assert data["code"] == 1
        assert "账号或密码错误" in data["message"]

    @pytest.mark.asyncio
    async def test_login_correct_after_failures_resets_count(self, client: AsyncClient):
        """错误几次后正确登录，重置失败计数"""
        await _create_admin()
        for _ in range(3):
            await _admin_login(client, password="WrongPass123!")

        data = await _admin_login(client)
        assert data["code"] == 0

        # 再次错误应从头计数
        d = await _admin_login(client, password="WrongPass123!")
        assert "4" in d["message"]

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
        assert "锁定" in d["message"]

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


# ==================== 修改密码测试 ====================


class TestChangePassword:
    """POST /api/admin/auth/change-password"""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client: AsyncClient):
        """正常修改密码"""
        await _create_admin()
        token = await _get_token(client)

        new_pass = "NewSuper@Pass1!"
        resp = await client.post(
            "/api/admin/auth/change-password",
            json={
                "old_password": _SUPER_ADMIN_PASS,
                "new_password": new_pass,
                "confirm_password": new_pass,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["code"] == 0

        # 用新密码可以登录
        data = await _admin_login(client, password=new_pass)
        assert data["code"] == 0

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
        assert resp.json()["code"] == 1
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
        assert resp.json()["code"] == 1

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
        assert resp.json()["code"] == 1

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
        assert resp.json()["code"] == 1


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
        assert resp.json()["code"] == 1
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
        assert resp.json()["code"] == 1

    @pytest.mark.asyncio
    async def test_reset_password_returns_new_password(self, client: AsyncClient):
        """重置密码返回新密码"""
        await _create_admin()
        await _create_admin(
            username=_OPS_ADMIN_USER,
            password=_OPS_ADMIN_PASS,
            role="ops_admin",
        )
        token = await _get_token(client)

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

        # 用新密码可以登录
        data = await _admin_login(client, username=_OPS_ADMIN_USER, password=new_pass)
        assert data["code"] == 0
