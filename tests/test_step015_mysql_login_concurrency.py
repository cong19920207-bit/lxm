# -*- coding: utf-8 -*-
"""Opt-in STEP-015 verification; never substitutes SQLite for MySQL row locks."""

import asyncio
import os
from datetime import datetime

import bcrypt
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import Request

from backend.config import get_mysql_url
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.routers.admin.auth import admin_login
from backend.schemas.admin_auth import AdminLoginRequest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_STEP015_MYSQL8") != "1",
    reason="requires an explicit isolated non-production MySQL 8 database",
)

engine = create_async_engine(
    get_mysql_url(),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def mysql_schema():
    async with engine.begin() as connection:
        version = (await connection.execute(text("SELECT VERSION()"))).scalar_one()
        assert str(version).startswith("8.")
        await connection.run_sync(
            lambda sync_connection: AdminUser.__table__.create(
                sync_connection, checkfirst=False
            )
        )
        await connection.run_sync(
            lambda sync_connection: AdminOperationLog.__table__.create(
                sync_connection, checkfirst=False
            )
        )
    yield
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AdminOperationLog.__table__.drop(
                sync_connection, checkfirst=True
            )
        )
        await connection.run_sync(
            lambda sync_connection: AdminUser.__table__.drop(
                sync_connection, checkfirst=True
            )
        )
    await engine.dispose()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def _create_admin(username: str, password: str) -> int:
    async with session_factory() as session:
        admin = AdminUser(
            username=username,
            password_hash=_hash_password(password),
            role="ops_admin",
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            token_version=0,
            last_password_change_at=datetime.utcnow(),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin.id


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/auth/login",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


async def _wrong_login(username: str):
    async with session_factory() as session:
        response = await admin_login(
            AdminLoginRequest(username=username, password="WrongPassword123!"),
            _request(),
            session,
        )
        await session.commit()
        return response


async def _state(admin_id: int) -> tuple[int, bool, int]:
    async with session_factory() as session:
        admin = await session.get(AdminUser, admin_id)
        return admin.login_fail_count, admin.is_locked, admin.token_version


@pytest.mark.asyncio
async def test_mysql8_concurrent_wrong_login_row_lock_matrix():
    locked_id = await _create_admin("step015-locked", "CorrectPassword123!")

    first_wave = await asyncio.gather(
        *[_wrong_login("step015-locked") for _ in range(5)]
    )
    assert [response.code for response in first_wave] == [20001] * 5
    assert await _state(locked_id) == (5, True, 1)

    locked_wave = await asyncio.gather(
        *[_wrong_login("step015-locked") for _ in range(4)]
    )
    assert [response.code for response in locked_wave] == [20001] * 4
    assert await _state(locked_id) == (5, True, 1)

    held_id = await _create_admin("step015-held", "CorrectPassword123!")
    other_id = await _create_admin("step015-other", "CorrectPassword123!")
    async with session_factory() as holding_session:
        await holding_session.execute(
            select(AdminUser).where(AdminUser.id == held_id).with_for_update()
        )
        other_response = await asyncio.wait_for(
            _wrong_login("step015-other"),
            timeout=3.0,
        )
        assert other_response.code == 20001
        assert await _state(other_id) == (1, False, 0)
        await holding_session.rollback()
