# -*- coding: utf-8 -*-
# 生活流 STEP-001 数据层迁移单元测试
#
# 覆盖 STEP 文档「单元测试要求」全部场景：
#   - 迁移 upgrade：8 张表 + 扩展列存在；agent_message.trigger_type 长度 16
#   - feed_like 唯一约束：同 user_id+post_id 插入两次抛 IntegrityError
#   - feed_comment.due_at 允许为 NULL
#   - life_plan_outline.plan_date UNIQUE
#   - worldview_event.event_name UNIQUE
#   - relationship 扩展列默认值：新用户插入 3 个新列均为 0
#   - TriggerType 常量：新增 LIKE_AWARE / READ_AWARE
#   - downgrade 通过 alembic 命令验证（本文件仅覆盖 ORM 层 + 约束）
#
# 说明：SQLite 内存库无法验证 MySQL VARCHAR 长度，agent_message.trigger_type
#   16 字符长度由迁移文件的 alter_column 保证，此处验证 TriggerType 常量类。

from datetime import datetime, date

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models import (
    AgentAwareQueue,
    AgentMessage,
    FeedComment,
    FeedLike,
    FeedPost,
    LifePlan,
    LifePlanOutline,
    Relationship,
    TriggerType,
    User,
    WorldviewEvent,
    WorldviewSnapshot,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前 create_all 全表；测试后 drop_all"""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with async_session_test() as session:
        yield session


# ============ 场景 1：8 张新表 + 扩展列存在 ============


class TestTablesCreated:
    """验证 create_all 后 8 张新表 + users/relationship 扩展列存在"""

    @pytest.mark.asyncio
    async def test_all_life_feed_tables_created(self):
        """8 张新表全部在 metadata 中注册"""
        expected_tables = {
            "life_plan_outline",
            "life_plan",
            "worldview_snapshot",
            "worldview_event",
            "feed_post",
            "feed_like",
            "feed_comment",
            "agent_aware_queue",
        }

        def _get_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())

        async with engine_test.begin() as conn:
            existing = await conn.run_sync(_get_tables)

        missing = expected_tables - existing
        assert not missing, f"缺失表：{missing}"

    @pytest.mark.asyncio
    async def test_users_last_feed_entered_at_column(self):
        """users 表含 last_feed_entered_at 列"""
        def _get_cols(sync_conn):
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("users")}

        async with engine_test.begin() as conn:
            cols = await conn.run_sync(_get_cols)

        assert "last_feed_entered_at" in cols

    @pytest.mark.asyncio
    async def test_relationship_new_columns(self):
        """relationship 表含 3 个新列"""
        def _get_cols(sync_conn):
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("relationship")}

        async with engine_test.begin() as conn:
            cols = await conn.run_sync(_get_cols)

        for col in (
            "like_aware_special_used_count",
            "read_aware_special_used_count",
            "has_ever_commented_feed",
        ):
            assert col in cols, f"relationship 缺列：{col}"

    @pytest.mark.asyncio
    async def test_feed_comment_due_at_column(self):
        """feed_comment 表含 due_at 列（本 STEP 补齐；§0.5 二选一定案）"""
        def _get_cols(sync_conn):
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("feed_comment")}

        async with engine_test.begin() as conn:
            cols = await conn.run_sync(_get_cols)

        assert "due_at" in cols


# ============ 场景 2：feed_like 唯一约束 ============


async def _mk_user(db: AsyncSession, uid_hint: int = 1) -> int:
    user = User(username=f"u{uid_hint}", password_hash="x")
    db.add(user)
    await db.flush()
    return user.id


async def _mk_feed_post(db: AsyncSession) -> int:
    post = FeedPost(
        scheduled_publish_time=datetime.utcnow(),
        generation_status="ready",
        content_text="test post",
        emotion="平静",
        city="杭州",
        season="秋",
        base_likes=3,
        like_multiplier=2,
        real_likes=0,
        is_visible=1,
        dedup_hash="hash_test_001",
    )
    db.add(post)
    await db.flush()
    return post.id


class TestFeedLikeUnique:
    """feed_like (user_id, post_id) 唯一约束"""

    @pytest.mark.asyncio
    async def test_duplicate_like_raises_integrity_error(self, db_session: AsyncSession):
        uid = await _mk_user(db_session)
        pid = await _mk_feed_post(db_session)

        db_session.add(FeedLike(user_id=uid, post_id=pid))
        await db_session.commit()

        # 第二次插入同 user_id+post_id 应抛 IntegrityError
        db_session.add(FeedLike(user_id=uid, post_id=pid))
        with pytest.raises(IntegrityError):
            await db_session.commit()


# ============ 场景 3：feed_comment.due_at 允许为 NULL ============


class TestFeedCommentDueAt:
    @pytest.mark.asyncio
    async def test_due_at_can_be_null(self, db_session: AsyncSession):
        uid = await _mk_user(db_session)
        pid = await _mk_feed_post(db_session)

        cm = FeedComment(post_id=pid, user_id=uid, content="hi", gen_status="pending")
        db_session.add(cm)
        await db_session.commit()

        await db_session.refresh(cm)
        assert cm.due_at is None


# ============ 场景 4：life_plan_outline.plan_date UNIQUE ============


class TestLifePlanOutlineUnique:
    @pytest.mark.asyncio
    async def test_duplicate_plan_date_raises_integrity_error(self, db_session: AsyncSession):
        d = date(2026, 6, 1)
        db_session.add(
            LifePlanOutline(
                week_start_date=date(2026, 6, 1),
                plan_date=d,
                city="杭州",
                categories="日常\n工作",
                gen_status="auto",
            )
        )
        await db_session.commit()

        db_session.add(
            LifePlanOutline(
                week_start_date=date(2026, 6, 1),
                plan_date=d,
                city="上海",
                categories="旅游",
                gen_status="manual",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()


# ============ 场景 5：worldview_event.event_name UNIQUE ============


class TestWorldviewEventUnique:
    @pytest.mark.asyncio
    async def test_duplicate_event_name_raises_integrity_error(self, db_session: AsyncSession):
        name = "在人多景区的感受与应对方式"
        db_session.add(
            WorldviewEvent(event_name=name, event_view="观点 A" * 30)
        )
        await db_session.commit()

        db_session.add(
            WorldviewEvent(event_name=name, event_view="观点 B" * 30)
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()


# ============ 场景 6：relationship 扩展列默认值 ============


class TestRelationshipDefaults:
    @pytest.mark.asyncio
    async def test_new_relationship_extension_defaults_are_zero(self, db_session: AsyncSession):
        uid = await _mk_user(db_session, uid_hint=99)

        rel = Relationship(
            user_id=uid,
            level=0,
            growth_value=0,
        )
        db_session.add(rel)
        await db_session.commit()

        result = await db_session.execute(select(Relationship).where(Relationship.user_id == uid))
        rel = result.scalar_one()
        assert rel.like_aware_special_used_count == 0
        assert rel.read_aware_special_used_count == 0
        assert rel.has_ever_commented_feed == 0


# ============ 场景 7：TriggerType 常量新增 LIKE_AWARE / READ_AWARE ============


class TestTriggerTypeConstants:
    def test_like_aware_constant(self):
        assert TriggerType.LIKE_AWARE == "LIKE_AWARE"

    def test_read_aware_constant(self):
        assert TriggerType.READ_AWARE == "READ_AWARE"

    def test_existing_constants_intact(self):
        """回归：现有 P0~P4 / FUTURE 6 项常量保持不变"""
        assert TriggerType.P0 == "P0"
        assert TriggerType.P1 == "P1"
        assert TriggerType.P2 == "P2"
        assert TriggerType.P3 == "P3"
        assert TriggerType.P4 == "P4"
        assert TriggerType.FUTURE == "FUTURE"


# ============ 场景 8：agent_aware_queue 基础插入 ============


class TestAgentAwareQueueBasic:
    """M1 建表保留结构，插入一条 LIKE_AWARE 记录，验证字段可用"""

    @pytest.mark.asyncio
    async def test_insert_like_aware_row(self, db_session: AsyncSession):
        uid = await _mk_user(db_session)
        pid = await _mk_feed_post(db_session)

        row = AgentAwareQueue(
            user_id=uid,
            trigger_type=TriggerType.LIKE_AWARE,
            post_id=pid,
            relationship_stage="friend",
            due_at=datetime.utcnow(),
            status="pending",
        )
        db_session.add(row)
        await db_session.commit()

        await db_session.refresh(row)
        assert row.status == "pending"
        assert row.trigger_type == "LIKE_AWARE"
        assert row.agent_message_id is None


# ============ 场景 9：agent_message.trigger_type 可存 16 字符 ============


class TestAgentMessageTriggerType:
    """LIKE_AWARE / READ_AWARE 各 10 字符，String(16) 顶格能存"""

    @pytest.mark.asyncio
    async def test_insert_like_aware_agent_message(self, db_session: AsyncSession):
        uid = await _mk_user(db_session)
        msg = AgentMessage(
            user_id=uid,
            trigger_type=TriggerType.LIKE_AWARE,
            content="test content",
            action_score=0.0,
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)
        assert msg.trigger_type == "LIKE_AWARE"
