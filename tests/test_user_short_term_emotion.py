# -*- coding: utf-8 -*-
# TD-020 V3-A：用户短期情绪 Redis/DB 服务单测

import json
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.emotion_log import EmotionLog
from backend.models.user import User
from backend.models.user_short_term_emotion import UserShortTermEmotion
from backend.services import user_short_term_emotion_service as uste_svc

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


class FakeRedis:
    """模拟 Redis：记录 ex 供 TTL 断言；del 键模拟过期。"""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ex: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = str(value)
        self._ex[key] = ex

    def clear(self):
        self._store.clear()
        self._ex.clear()


@pytest_asyncio.fixture
async def db_session(monkeypatch):
    monkeypatch.setattr(uste_svc, "async_session_maker", async_session_test)
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_test() as session:
        u = User(
            username="emotest",
            password_hash="x",
            created_at=datetime.utcnow(),
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
        uid = u.id

    async with async_session_test() as session:
        yield session, uid

    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_write_user_emotion(db_session, monkeypatch):
    """写入后可经 read_for_prompt 读到（Redis 优先）。"""
    session, uid = db_session
    fake = FakeRedis()
    monkeypatch.setenv("REDIS_USER_EMOTION_TTL", "7200")

    from backend import config

    monkeypatch.setattr(
        config,
        "get_redis_user_emotion_ttl_seconds",
        lambda: int(__import__("os").environ.get("REDIS_USER_EMOTION_TTL", "3600")),
    )

    await uste_svc.persist_after_round(
        uid, {"label": "开心", "confidence": 0.88, "extra": 1}, fake
    )
    key = uste_svc.build_redis_key(uid)
    assert key == f"user_emotion:{uid}"
    raw = await fake.get(key)
    assert raw is not None
    assert json.loads(raw)["label"] == "开心"

    got = await uste_svc.read_for_prompt(uid, session, fake)
    assert got == {"label": "开心", "confidence": 0.88}


@pytest.mark.asyncio
async def test_ttl_expiry_config(db_session, monkeypatch):
    """SET 时 ex 与配置一致；键删除后读 DB 行。"""
    session, uid = db_session
    fake = FakeRedis()
    monkeypatch.setenv("REDIS_USER_EMOTION_TTL", "123")

    from backend import config

    monkeypatch.setattr(
        config,
        "get_redis_user_emotion_ttl_seconds",
        lambda: int(__import__("os").environ.get("REDIS_USER_EMOTION_TTL", "3600")),
    )

    await uste_svc.persist_after_round(uid, {"label": "焦虑", "confidence": 0.7}, fake)
    k = uste_svc.build_redis_key(uid)
    assert fake._ex.get(k) == 123

    del fake._store[k]
    del fake._ex[k]

    got = await uste_svc.read_for_prompt(uid, session, fake)
    assert got == {"label": "焦虑", "confidence": pytest.approx(0.7)}


@pytest.mark.asyncio
async def test_read_fallback_emotion_log(db_session, monkeypatch):
    """无 Redis、无 user_short_term_emotion 行时回退 emotion_log 最新一条。"""
    session, uid = db_session
    fake = FakeRedis()
    monkeypatch.setattr(uste_svc, "async_session_maker", async_session_test)

    # 需 conversation_id FK：SQLite 测试下插入最小 conversation_log 行
    from backend.models.conversation_log import ConversationLog

    async with async_session_test() as s2:
        log = ConversationLog(
            user_id=uid,
            role="user",
            content="hi",
            sort_seq=1,
            delivery_status="delivered",
            skipped_in_prompt=False,
        )
        s2.add(log)
        await s2.commit()
        await s2.refresh(log)
        cid = log.id
        s2.add(
            EmotionLog(
                user_id=uid,
                emotion_label="悲伤",
                confidence=0.6,
                conversation_id=cid,
            )
        )
        await s2.commit()

    got = await uste_svc.read_for_prompt(uid, session, fake)
    assert got == {"label": "悲伤", "confidence": pytest.approx(0.6)}
