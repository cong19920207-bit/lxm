# -*- coding: utf-8 -*-
# STEP-015 单元测试：Step6 标量写回 + 历史 + Future 槽

import time
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.relationship import Relationship
from backend.models.relationship_change_history import RelationshipChangeHistory
from backend.services.memory_llm_service import Step6MemoryOutput
from backend.services.relationship_history_service import RelationshipHistoryService
from backend.services.relationship_service import RelationshipService

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


async def _create_user_and_relationship(
    db: AsyncSession,
    user_id: int = 1,
    *,
    future_timestamp: int | None = None,
    future_action: str | None = None,
    proactive_times: int = 0,
) -> Relationship:
    """创建测试用 users 行 + relationship 行"""
    from backend.models.user import User

    user = User(id=user_id, username=f"test_user_{user_id}", password_hash="fake_hash")
    db.add(user)
    await db.flush()

    rel = Relationship(
        user_id=user_id,
        level=1,
        growth_value=300,
        user_real_name="旧真名",
        user_hobby_name="旧昵称",
        user_description="旧描述",
        character_purpose="旧策略",
        character_attitude="旧态度",
        relation_description="旧关系",
        future_timestamp=future_timestamp,
        future_action=future_action,
        proactive_times=proactive_times,
    )
    db.add(rel)
    await db.flush()
    return rel


def _make_step6_output(**overrides) -> Step6MemoryOutput:
    """构造 Step6MemoryOutput，未提供的标量默认为非「无」的测试值"""
    defaults = {
        "UserRealName": "新真名",
        "UserHobbyName": "新昵称",
        "UserDescription": "新描述",
        "CharacterPurpose": "新策略",
        "CharacterAttitude": "新态度",
        "RelationDescription": "新关系",
    }
    defaults.update(overrides)
    return Step6MemoryOutput(**defaults)


# ============ 场景 1：6 字段全非「无」→ 全部 UPDATE + 6 条历史 ============


class TestAllFieldsUpdated:
    """6 个标量字段全非「无」时应全部写入并产生 6 条历史"""

    @pytest.mark.asyncio
    async def test_all_six_fields_updated(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-001",
        )

        assert len(result["updated_fields"]) == 6
        assert result["history_count"] == 6
        assert result["future_status"] == "no_future"

        # 验证 relationship 列已更新
        assert rel.user_real_name == "新真名"
        assert rel.user_hobby_name == "新昵称"
        assert rel.user_description == "新描述"
        assert rel.character_purpose == "新策略"
        assert rel.character_attitude == "新态度"
        assert rel.relation_description == "新关系"

        # 验证历史记录
        history_svc = RelationshipHistoryService(db_session)
        records = await history_svc.get_history_by_relationship(rel.id)
        assert len(records) == 6
        assert all(r.trigger_source == "step6" for r in records)
        assert all(r.round_id == "round-001" for r in records)

    @pytest.mark.asyncio
    async def test_old_values_recorded_in_history(self, db_session: AsyncSession):
        """历史记录应正确保存旧值"""
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        await svc.update_relationship_from_step6(
            relationship=rel, step6_output=output, round_id="round-002",
        )

        history_svc = RelationshipHistoryService(db_session)
        records = await history_svc.get_history_by_relationship(rel.id)
        old_values_map = {r.field_name: r.old_value for r in records}

        assert old_values_map["user_real_name"] == "旧真名"
        assert old_values_map["user_hobby_name"] == "旧昵称"
        assert old_values_map["user_description"] == "旧描述"
        assert old_values_map["character_purpose"] == "旧策略"
        assert old_values_map["character_attitude"] == "旧态度"
        assert old_values_map["relation_description"] == "旧关系"


# ============ 场景 2：UserRealName 为「无」→ 该列不赋值，保留旧值 ============


class TestSkipFieldWithNone:
    """值为「无」的字段应跳过赋值"""

    @pytest.mark.asyncio
    async def test_user_real_name_none_skipped(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output(UserRealName="无")

        result = await svc.update_relationship_from_step6(
            relationship=rel, step6_output=output, round_id="round-003",
        )

        # user_real_name 应保留旧值
        assert rel.user_real_name == "旧真名"
        # 仅 5 个字段更新
        assert len(result["updated_fields"]) == 5
        assert "user_real_name" not in result["updated_fields"]
        assert result["history_count"] == 5

    @pytest.mark.asyncio
    async def test_multiple_fields_none_skipped(self, db_session: AsyncSession):
        """多个字段为「无」时均跳过"""
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output(
            UserRealName="无",
            UserHobbyName="无",
            CharacterAttitude="无",
        )

        result = await svc.update_relationship_from_step6(
            relationship=rel, step6_output=output, round_id="round-004",
        )

        assert rel.user_real_name == "旧真名"
        assert rel.user_hobby_name == "旧昵称"
        assert rel.character_attitude == "旧态度"
        assert len(result["updated_fields"]) == 3
        assert result["history_count"] == 3


# ============ 场景 3：future.time_natural = "30分钟后" → future_timestamp 正确写入 ============


class TestFutureSlotWrite:
    """Future 槽解析成功时正确写入"""

    @pytest.mark.asyncio
    async def test_future_30_min_later(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        now_ts = int(time.time())

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-005",
            future_time_natural="30分钟后",
            future_action="问问用户今天工作累不累",
        )

        assert result["future_status"] == "written"
        assert rel.future_timestamp is not None
        # 30 分钟 = 1800 秒，允许 5 秒误差
        assert abs(rel.future_timestamp - (now_ts + 1800)) < 5
        assert rel.future_action == "问问用户今天工作累不累"
        # 6 个标量 + 2 个 future 字段 = 8 条历史
        assert result["history_count"] == 8

    @pytest.mark.asyncio
    async def test_future_overwrites_existing(self, db_session: AsyncSession):
        """已有 future 槽时，新的解析结果应覆盖旧值"""
        rel = await _create_user_and_relationship(
            db_session,
            future_timestamp=1000000,
            future_action="旧的行动",
        )
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-006",
            future_time_natural="2小时后",
            future_action="新的行动",
        )

        assert result["future_status"] == "written"
        assert rel.future_action == "新的行动"
        assert rel.future_timestamp != 1000000

        # 验证历史中记录了旧值
        history_svc = RelationshipHistoryService(db_session)
        records = await history_svc.get_history_by_relationship(rel.id)
        ts_records = [r for r in records if r.field_name == "future_timestamp"]
        assert len(ts_records) == 1
        assert ts_records[0].old_value == "1000000"


# ============ 场景 4：future.action = "无" → future 字段清空 ============


class TestFutureActionNone:
    """action 为「无」时应清空 future 字段"""

    @pytest.mark.asyncio
    async def test_action_none_clears_future(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(
            db_session,
            future_timestamp=9999999,
            future_action="之前的行动",
            proactive_times=3,
        )
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-007",
            future_time_natural="30分钟后",
            future_action="无",
        )

        assert result["future_status"] == "cleared_by_action_none"
        assert rel.future_timestamp is None
        assert rel.future_action is None
        # proactive_times 不受影响
        assert rel.proactive_times == 3

    @pytest.mark.asyncio
    async def test_action_none_no_existing_future(self, db_session: AsyncSession):
        """无已有 future 时，action='无' 不产生 future 历史"""
        rel = await _create_user_and_relationship(db_session)
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-008",
            future_action="无",
        )

        assert result["future_status"] == "cleared_by_action_none"
        # 仅 6 条标量历史，无 future 历史（因旧值为 None 跳过）
        assert result["history_count"] == 6


# ============ 边界测试：future.time_natural = "明天上午" → 解析失败 ============


class TestFutureParseFailure:
    """time_natural 解析失败时清空槽位，保留 proactive_times"""

    @pytest.mark.asyncio
    async def test_invalid_time_natural_clears_slot(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(
            db_session,
            future_timestamp=8888888,
            future_action="之前的行动",
            proactive_times=5,
        )
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-009",
            future_time_natural="明天上午",
            future_action="某个行动",
        )

        assert result["future_status"] == "cleared_parse_failed"
        assert rel.future_timestamp is None
        assert rel.future_action is None
        # proactive_times 必须保留
        assert rel.proactive_times == 5

        # 验证清空操作写入了历史
        history_svc = RelationshipHistoryService(db_session)
        records = await history_svc.get_history_by_relationship(rel.id)
        future_records = [r for r in records if r.field_name.startswith("future_")]
        assert len(future_records) == 2  # future_timestamp + future_action
        ts_rec = [r for r in future_records if r.field_name == "future_timestamp"][0]
        assert ts_rec.old_value == "8888888"
        assert ts_rec.new_value is None

    @pytest.mark.asyncio
    async def test_parse_fail_no_existing_future(self, db_session: AsyncSession):
        """无已有 future 时，解析失败不产生 future 历史"""
        rel = await _create_user_and_relationship(db_session, proactive_times=2)
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel,
            step6_output=output,
            round_id="round-010",
            future_time_natural="下周三",
            future_action="某个行动",
        )

        assert result["future_status"] == "cleared_parse_failed"
        assert rel.proactive_times == 2
        # 仅 6 条标量历史
        assert result["history_count"] == 6


# ============ 补充：无 future 参数时不触发 future 处理 ============


class TestNoFutureParams:
    """不传 future 参数时应跳过 future 处理"""

    @pytest.mark.asyncio
    async def test_no_future_params(self, db_session: AsyncSession):
        rel = await _create_user_and_relationship(
            db_session,
            future_timestamp=7777777,
            future_action="保留的行动",
        )
        svc = RelationshipService(db_session)
        output = _make_step6_output()

        result = await svc.update_relationship_from_step6(
            relationship=rel, step6_output=output, round_id="round-011",
        )

        assert result["future_status"] == "no_future"
        # 现有 future 不受影响
        assert rel.future_timestamp == 7777777
        assert rel.future_action == "保留的行动"
