# -*- coding: utf-8 -*-
# 关系扩展字段变更历史表 单元测试（STEP-002 / R-L1L3-05）

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.relationship import Relationship
from backend.models.relationship_change_history import RelationshipChangeHistory
from backend.services.relationship_history_service import RelationshipHistoryService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前创建全部表，测试后销毁"""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """获取测试数据库会话"""
    async with async_session_test() as session:
        yield session
        await session.commit()


async def _create_user_and_relationship(db: AsyncSession, user_id: int = 1) -> Relationship:
    """创建测试用 users 行 + relationship 行，返回 Relationship 实例"""
    from backend.models.user import User
    user = User(
        id=user_id,
        username=f"test_user_{user_id}",
        password_hash="fake_hash_for_test",
    )
    db.add(user)
    await db.flush()

    rel = Relationship(user_id=user_id, level=1, growth_value=300)
    db.add(rel)
    await db.flush()
    return rel


# ============ 场景1：写入一条历史记录，查询验证字段完整 ============


class TestAppendSingleHistory:
    """测试写入单条变更历史记录后字段完整性"""

    @pytest.mark.asyncio
    async def test_append_and_verify_fields(self, db_session: AsyncSession):
        """写入一条历史记录 → 查询验证所有字段"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        record = await svc.append_history(
            relationship_id=rel.id,
            user_id=1,
            field_name="relation_description",
            old_value="之前的关系描述",
            new_value="更新后的关系描述",
            trigger_source="step6",
            round_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert record.id is not None
        assert record.relationship_id == rel.id
        assert record.user_id == 1
        assert record.field_name == "relation_description"
        assert record.old_value == "之前的关系描述"
        assert record.new_value == "更新后的关系描述"
        assert record.trigger_source == "step6"
        assert record.round_id == "550e8400-e29b-41d4-a716-446655440000"
        assert isinstance(record.created_at, datetime)

    @pytest.mark.asyncio
    async def test_default_trigger_source(self, db_session: AsyncSession):
        """不传 trigger_source 时默认为 step6"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        record = await svc.append_history(
            relationship_id=rel.id,
            user_id=1,
            field_name="user_real_name",
            old_value=None,
            new_value="小明",
        )

        assert record.trigger_source == "step6"


# ============ 场景2：连续写入 3 条，按 created_at 排序验证顺序 ============


class TestAppendMultipleHistory:
    """测试同一 relationship 连续写入多条记录的顺序"""

    @pytest.mark.asyncio
    async def test_three_records_ordered_by_created_at(self, db_session: AsyncSession):
        """同一 relationship 连续写入 3 条 → 按 created_at 排序验证顺序"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        fields = ["user_real_name", "user_hobby_name", "relation_description"]
        for field in fields:
            await svc.append_history(
                relationship_id=rel.id,
                user_id=1,
                field_name=field,
                old_value=None,
                new_value=f"新的{field}值",
                round_id="round-001",
            )

        records = await svc.get_history_by_relationship(rel.id)
        assert len(records) == 3

        for i in range(len(records) - 1):
            assert records[i].created_at <= records[i + 1].created_at

        assert records[0].field_name == "user_real_name"
        assert records[1].field_name == "user_hobby_name"
        assert records[2].field_name == "relation_description"


# ============ 边界测试：old_value 为 NULL ============


class TestOldValueNull:
    """测试 old_value 为 NULL 的边界场景"""

    @pytest.mark.asyncio
    async def test_old_value_none(self, db_session: AsyncSession):
        """old_value 为 None 时应正常写入"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        record = await svc.append_history(
            relationship_id=rel.id,
            user_id=1,
            field_name="character_purpose",
            old_value=None,
            new_value="温柔回应，多关心用户今天的状态",
            trigger_source="step6",
        )

        assert record.id is not None
        assert record.old_value is None
        assert record.new_value == "温柔回应，多关心用户今天的状态"

        records = await svc.get_history_by_relationship(rel.id)
        assert len(records) == 1
        assert records[0].old_value is None

    @pytest.mark.asyncio
    async def test_round_id_none(self, db_session: AsyncSession):
        """round_id 为 None 时应正常写入"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        record = await svc.append_history(
            relationship_id=rel.id,
            user_id=1,
            field_name="character_attitude",
            old_value="友善",
            new_value="亲近且关心",
            round_id=None,
        )

        assert record.id is not None
        assert record.round_id is None


# ============ 查询方法测试 ============


class TestQueryMethods:
    """测试按 user_id 查询历史"""

    @pytest.mark.asyncio
    async def test_get_history_by_user(self, db_session: AsyncSession):
        """按 user_id 查询变更历史"""
        rel = await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        await svc.append_history(
            relationship_id=rel.id, user_id=1,
            field_name="user_description", old_value=None, new_value="喜欢画画的女孩",
        )
        await svc.append_history(
            relationship_id=rel.id, user_id=1,
            field_name="user_real_name", old_value=None, new_value="小红",
        )

        records = await svc.get_history_by_user(user_id=1)
        assert len(records) == 2
        assert all(r.user_id == 1 for r in records)

    @pytest.mark.asyncio
    async def test_empty_history(self, db_session: AsyncSession):
        """无历史记录时返回空列表"""
        await _create_user_and_relationship(db_session, user_id=1)
        svc = RelationshipHistoryService(db_session)

        records = await svc.get_history_by_user(user_id=1)
        assert records == []
