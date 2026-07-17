# -*- coding: utf-8 -*-
# 关系成长系统单元测试

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.relationship import Relationship
from backend.services.relationship_service import (
    GROWTH_ACTIONS,
    LEVEL_CONFIG,
    RelationshipService,
)

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


app.dependency_overrides[get_db] = override_get_db


class FakeRedis:
    """模拟 Redis 客户端，用于测试"""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = str(value)
        if ex:
            self._ttls[key] = ex

    async def incrby(self, key: str, amount: int) -> int:
        current = int(self._store.get(key, "0"))
        new_val = current + amount
        self._store[key] = str(new_val)
        return new_val

    async def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = seconds

    def clear(self):
        self._store.clear()
        self._ttls.clear()


fake_redis = FakeRedis()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前创建表并清理 Redis，测试后销毁"""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    fake_redis.clear()
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """获取测试数据库会话"""
    async with async_session_test() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _patch_redis():
    """统一 patch Redis，返回 FakeRedis 实例"""
    async def _get_fake_redis():
        return fake_redis

    return patch(
        "backend.services.relationship_service.get_redis",
        new=_get_fake_redis,
    )


async def _create_relationship(db: AsyncSession, user_id: int = 1, **kwargs) -> Relationship:
    """创建测试用关系记录"""
    defaults = {
        "user_id": user_id,
        "level": 0,
        "growth_value": 0,
        "consecutive_login_days": 0,
        "last_interaction_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    rel = Relationship(**defaults)
    db.add(rel)
    await db.flush()
    return rel


# ============ 成长值每日上限测试 ============


class TestGrowthDailyLimit:
    """测试成长值每日上限是否生效"""

    @pytest.mark.asyncio
    async def test_dialog_daily_limit(self, db_session: AsyncSession):
        """dialog 行为每日上限 50 分"""
        await _create_relationship(db_session, user_id=1)

        with _patch_redis():
            svc = RelationshipService(db_session)

            # dialog 每次 +2，连续调用 26 次应达到上限 50（实际 52 > 50，第 26 次不满额）
            total_earned = 0
            for i in range(30):
                result = await svc.add_growth(1, "dialog")
                if i < 25:
                    total_earned += 2

            # 确认不超过每日上限
            assert result["current_growth"] <= 50

    @pytest.mark.asyncio
    async def test_long_session_daily_limit(self, db_session: AsyncSession):
        """long_session 行为每日上限 20 分"""
        await _create_relationship(db_session, user_id=1)

        with _patch_redis():
            svc = RelationshipService(db_session)

            # long_session 每次 +20，第 1 次达到上限，第 2 次不再累加
            r1 = await svc.add_growth(1, "long_session")
            assert r1["current_growth"] == 20

            r2 = await svc.add_growth(1, "long_session")
            assert r2["current_growth"] == 20  # 不再增长

    @pytest.mark.asyncio
    async def test_reply_agent_daily_limit(self, db_session: AsyncSession):
        """reply_agent 行为每日上限 20 分"""
        await _create_relationship(db_session, user_id=1)

        with _patch_redis():
            svc = RelationshipService(db_session)

            r1 = await svc.add_growth(1, "reply_agent")
            assert r1["current_growth"] == 10

            r2 = await svc.add_growth(1, "reply_agent")
            assert r2["current_growth"] == 20

            r3 = await svc.add_growth(1, "reply_agent")
            assert r3["current_growth"] == 20  # 达到上限


# ============ 升级逻辑测试 ============


class TestLevelUp:
    """测试升级逻辑是否正确触发"""

    @pytest.mark.asyncio
    async def test_level_up_to_friend(self, db_session: AsyncSession):
        """从 0 级陌生升到 1 级朋友（200 分）"""
        await _create_relationship(db_session, user_id=1, growth_value=198)

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "dialog")

            assert result["leveled_up"] is True
            assert result["new_level"] == 1
            assert result["new_level_name"] == "朋友"
            assert result["next_threshold"] == 800

    @pytest.mark.asyncio
    async def test_level_up_to_close(self, db_session: AsyncSession):
        """从 1 级朋友升到 2 级亲密（800 分）"""
        await _create_relationship(db_session, user_id=1, level=1, growth_value=790)

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "reply_agent")

            assert result["leveled_up"] is True
            assert result["new_level"] == 2
            assert result["new_level_name"] == "亲密"
            assert result["next_threshold"] == 2000

    @pytest.mark.asyncio
    async def test_no_level_up_when_not_reached(self, db_session: AsyncSession):
        """成长值未达阈值时不升级"""
        await _create_relationship(db_session, user_id=1, growth_value=100)

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "dialog")

            assert result["leveled_up"] is False
            assert result["new_level"] == 0
            assert result["new_level_name"] == "陌生"

    @pytest.mark.asyncio
    async def test_level_up_to_soulmate(self, db_session: AsyncSession):
        """从 2 级亲密升到 3 级知己（2000 分）"""
        await _create_relationship(db_session, user_id=1, level=2, growth_value=1998)

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "dialog")

            assert result["leveled_up"] is True
            assert result["new_level"] == 3
            assert result["new_level_name"] == "知己"
            assert result["next_threshold"] is None


# ============ AI 情绪默认值测试 ============


class TestAiEmotion:
    """测试 ai_current_emotion 无缓存时默认返回「平静」"""

    @pytest.mark.asyncio
    async def test_default_emotion_when_no_cache(self, db_session: AsyncSession):
        """Redis 中无 ai_emotion 缓存时，默认返回平静"""
        await _create_relationship(db_session, user_id=1)

        with _patch_redis():
            svc = RelationshipService(db_session)
            info = await svc.get_relationship_info(1)

            assert info["ai_current_emotion"] == "平静"

    @pytest.mark.asyncio
    async def test_cached_emotion_returned(self, db_session: AsyncSession):
        """Redis 中有 ai_emotion 缓存时，返回缓存值"""
        await _create_relationship(db_session, user_id=1)
        fake_redis._store["ai_emotion:1"] = "开心"

        with _patch_redis():
            svc = RelationshipService(db_session)
            info = await svc.get_relationship_info(1)

            assert info["ai_current_emotion"] == "开心"


# ============ 进度百分比测试 ============


class TestProgressPercent:
    """测试 progress_percent 计算"""

    @pytest.mark.asyncio
    async def test_progress_at_level_start(self, db_session: AsyncSession):
        """刚升到 2 级（800 分）时进度为 0%"""
        await _create_relationship(db_session, user_id=1, level=2, growth_value=800)

        with _patch_redis():
            svc = RelationshipService(db_session)
            info = await svc.get_relationship_info(1)
            assert info["progress_percent"] == 0

    @pytest.mark.asyncio
    async def test_progress_mid_level(self, db_session: AsyncSession):
        """2 级中间值的进度计算"""
        await _create_relationship(db_session, user_id=1, level=2, growth_value=1400)

        with _patch_redis():
            svc = RelationshipService(db_session)
            info = await svc.get_relationship_info(1)
            # (1400-800) / (2000-800) * 100 = 50%
            assert info["progress_percent"] == 50

    @pytest.mark.asyncio
    async def test_progress_max_level(self, db_session: AsyncSession):
        """3 级知己进度为 100%"""
        await _create_relationship(db_session, user_id=1, level=3, growth_value=2500)

        with _patch_redis():
            svc = RelationshipService(db_session)
            info = await svc.get_relationship_info(1)
            assert info["progress_percent"] == 100


# ============ 沉默天数测试 ============


class TestSilenceDays:
    """测试沉默天数计算"""

    @pytest.mark.asyncio
    async def test_silence_days_no_interaction(self, db_session: AsyncSession):
        """无互动记录返回 999"""
        await _create_relationship(db_session, user_id=1, last_interaction_at=None)

        with _patch_redis():
            svc = RelationshipService(db_session)
            days = await svc.get_silence_days(1)
            assert days == 999

    @pytest.mark.asyncio
    async def test_silence_days_recent(self, db_session: AsyncSession):
        """最近互动，沉默天数为 0"""
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=datetime.utcnow(),
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            days = await svc.get_silence_days(1)
            assert days == 0

    @pytest.mark.asyncio
    async def test_silence_days_past(self, db_session: AsyncSession):
        """5 天前互动，沉默天数为 5"""
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=datetime.utcnow() - timedelta(days=5),
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            days = await svc.get_silence_days(1)
            assert days == 5


# ============ 连续登录测试 ============


class TestConsecutiveLogin:
    """测试连续登录天数更新逻辑"""

    @pytest.mark.asyncio
    async def test_first_login(self, db_session: AsyncSession):
        """首次登录，连续天数设为 1"""
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=None,
            consecutive_login_days=0,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            await svc.update_consecutive_login(1)

            rel = await svc._get_or_create_relationship(1)
            assert rel.consecutive_login_days == 1

    @pytest.mark.asyncio
    async def test_consecutive_login(self, db_session: AsyncSession):
        """连续登录，天数 +1"""
        yesterday = datetime.utcnow().replace(hour=12, minute=0, second=0) - timedelta(days=1)
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=yesterday,
            consecutive_login_days=5,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            await svc.update_consecutive_login(1)

            rel = await svc._get_or_create_relationship(1)
            assert rel.consecutive_login_days == 6

    @pytest.mark.asyncio
    async def test_login_gap_resets(self, db_session: AsyncSession):
        """中断登录，天数重置为 1"""
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=three_days_ago,
            consecutive_login_days=10,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            await svc.update_consecutive_login(1)

            rel = await svc._get_or_create_relationship(1)
            assert rel.consecutive_login_days == 1

    @pytest.mark.asyncio
    async def test_same_day_login_no_change(self, db_session: AsyncSession):
        """同一天多次登录，天数不变"""
        now = datetime.utcnow()
        today_morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
        await _create_relationship(
            db_session, user_id=1,
            last_interaction_at=today_morning,
            consecutive_login_days=3,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            await svc.update_consecutive_login(1)

            rel = await svc._get_or_create_relationship(1)
            assert rel.consecutive_login_days == 3


# ============ 连续登录加成测试 ============


class TestLoginBonus:
    """测试连续登录 7 天以上的加成"""

    @pytest.mark.asyncio
    async def test_daily_login_bonus_after_7_days(self, db_session: AsyncSession):
        """连续登录超过 7 天，daily_login 加 10 分"""
        await _create_relationship(
            db_session, user_id=1,
            consecutive_login_days=8,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "daily_login")

            assert result["current_growth"] == 10

    @pytest.mark.asyncio
    async def test_daily_login_normal_within_7_days(self, db_session: AsyncSession):
        """连续登录 7 天以内，daily_login 加 5 分"""
        await _create_relationship(
            db_session, user_id=1,
            consecutive_login_days=5,
        )

        with _patch_redis():
            svc = RelationshipService(db_session)
            result = await svc.add_growth(1, "daily_login")

            assert result["current_growth"] == 5
