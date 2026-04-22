# -*- coding: utf-8 -*-
"""
林小梦 20 轮对话集成测试脚本（HTTP + SSE，与线上一致）

通过已运行的 FastAPI 调用 POST /api/auth/login、POST /api/chat/send（流式），
避免依赖已删除的路由内部函数。

# 运行方式：pytest scripts/test_chat_e2e.py -v
# 依赖：requests, sseclient-py（pip install sseclient-py）
# 说明：本文件实际用 httpx 解析 SSE（与仓库 requirements.txt 一致）；请在仓库根目录执行并设置 PYTHONPATH=.

运行前：
  1. 启动后端（默认 http://127.0.0.1:8000）
  2. MySQL 可连（用于创建/确认 e2e_test_user）
  3. 可选：export CHAT_E2E_BASE_URL=http://127.0.0.1:8000

Docker（docker-compose）与本脚本对齐要点：
  - compose 里 **backend** 会强制 `MYSQL_HOST=mysql`（仅容器内 DNS 有效），连的是 **lxm_mysql** 里的数据。
  - 你在**宿主机**跑本脚本/pytest 时，`.env` 里 **MYSQL_HOST 须为 127.0.0.1**（或宿主能连到的那台 MySQL 的 IP），**端口/库名/用户密码**与 compose 中 mysql 服务一致（默认映射 `3306:3306`），这样 `_get_or_create_test_user` 写入的库与容器内 API 登录查询的库才是**同一套**。
  - 若 `.env` 仍写 `MYSQL_HOST=mysql`，宿主机通常解析不到或连错库，易出现登录「用户不存在」。
  - 默认镜像未 COPY `scripts/`，一般不在 **lxm_backend 容器内**跑本文件；除非 compose 挂载了项目根。

用法：
    cd /path/to/lxm_for
    PYTHONPATH=. python scripts/test_chat_e2e.py
    PYTHONPATH=. pytest scripts/test_chat_e2e.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中，并加载 .env
_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from dotenv import load_dotenv

load_dotenv(_proj_root / ".env", override=True)

# 避免导入 ORM 链时触发 scheduler
def _mock_scheduler():
    import types

    mod = types.ModuleType("backend.tasks.scheduler")
    mod.start_scheduler = lambda: None
    mod.shutdown_scheduler = lambda: None
    return mod


if "backend.tasks.scheduler" not in sys.modules:
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler()

import httpx

# ============ 配置 ============
BASE_URL = os.environ.get("CHAT_E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
E2E_USERNAME = "e2e_test_user"
E2E_PASSWORD = "pass1234"

# ============ 测试消息列表（20 轮） ============
TEST_MESSAGES = [
    "你好呀，在吗？",
    "今天天气不错，心情很好",
    "在干嘛呢？",
    "我叫小明，以后可以这么叫我",
    "我最爱的小说是《三体》，看了好几遍",
    "我对芒果过敏，不能吃",
    "今天加班到很晚，有点累",
    "周末想去爬山放松一下",
    "你有没有推荐的运动方式？",
    "最近工作压力挺大的",
    "你还记得我喜欢什么小说吗？",
    "我上次说我过敏的是啥水果来着？",
    "你记性真好呀",
    "今天心情不太好，有点郁闷",
    "可能是因为工作不顺心吧",
    "谢谢你愿意听我说话",
    "和你聊完感觉好多了",
    "以后有空常找你聊",
    "晚安，早点休息",
    "拜拜，明天见",
]


def _sep(title: str = "", char: str = "="):
    w = 70
    if title:
        half = (w - len(title) - 2) // 2
        print(f"\n{char * half} {title} {char * (w - half - len(title) - 2)}")
    else:
        print(char * w)


def _log_step(name: str, success: bool, detail: str = ""):
    status = "[成功]" if success else "[失败]"
    print(f"  {status} {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"       {line}")


def _e2e_fail_log(scenario: str, actual: object, expected: object) -> None:
    """pytest 断言失败时补充可读日志（场景名 + 实际值 + 预期值）。"""
    print(f"\n[E2E 断言失败] 场景: {scenario}")
    print(f"  实际值: {actual!r}")
    print(f"  预期值: {expected!r}")


async def _require_chat_server(client: httpx.AsyncClient) -> None:
    """未启动后端时跳过用例，避免 CI 无服务时误报失败。"""
    try:
        r = await client.get(f"{BASE_URL}/openapi.json", timeout=3.0)
        if r.status_code >= 500:
            pytest.skip(f"E2E 服务异常 HTTP {r.status_code}: {BASE_URL}")
    except Exception as e:
        pytest.skip(f"E2E 服务不可用 {BASE_URL}: {e}")


async def _iter_sse_events(resp: httpx.Response) -> AsyncIterator[dict]:
    """从已打开的 SSE 响应流中迭代解析后的 data JSON 对象。"""
    buf = ""
    async for chunk in resp.aiter_bytes():
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            yield ev


async def _get_or_create_test_user() -> int:
    """获取或创建测试用户，返回 user_id"""
    import bcrypt
    from sqlalchemy import select

    from backend.database import async_session_maker
    from backend.models.relationship import Relationship
    from backend.models.user import User

    async with async_session_maker() as db:
        stmt = select(User).where(User.username == E2E_USERNAME)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            return user.id

        pw_hash = bcrypt.hashpw(E2E_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(username=E2E_USERNAME, password_hash=pw_hash)
        db.add(user)
        await db.flush()
        rel = Relationship(user_id=user.id, level=0, growth_value=0)
        db.add(rel)
        await db.commit()
        return user.id


async def _login_get_token(client: httpx.AsyncClient) -> str:
    """POST /api/auth/login，返回 Bearer token"""
    resp = await client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": E2E_USERNAME, "password": E2E_PASSWORD, "remember_me": False},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise RuntimeError(f"登录失败: {body}")
    data = body.get("data") or {}
    token = data.get("token")
    if not token:
        raise RuntimeError(f"登录响应无 token: {body}")
    return token


async def _send_one_round_sse(client: httpx.AsyncClient, token: str, user_content: str, round_num: int) -> str:
    """POST /api/chat/send，解析 SSE，返回拼接后的 AI 正文"""
    _sep(f"第 {round_num} 轮对话", "=")
    print(f"【用户输入】{user_content}")

    client_msg_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": client_msg_id,
    }
    body = {"content": user_content, "client_message_id": client_msg_id}

    reply_parts: list[str] = []
    generation_id: str | None = None
    timeout = httpx.Timeout(120.0, connect=30.0, read=120.0)

    async with client.stream(
        "POST",
        f"{BASE_URL}/api/chat/send",
        json=body,
        headers=headers,
        timeout=timeout,
    ) as resp:
        if resp.status_code == 401:
            raise RuntimeError("401 未授权，请检查 e2e_test_user 密码或 token")
        if resp.status_code != 200:
            err_body = (await resp.aread()).decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"HTTP {resp.status_code}: {err_body}")

        ct = (resp.headers.get("content-type") or "").lower()
        if "text/event-stream" not in ct and "application/x-ndjson" not in ct:
            raw = (await resp.aread()).decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"期望 SSE，Content-Type={ct!r} body={raw!r}")

        async for ev in _iter_sse_events(resp):
            et = ev.get("type")
            if et == "meta":
                generation_id = ev.get("generation_id")
                _log_step("SSE meta", True, f"generation_id={generation_id}")
            elif et == "delta":
                reply_parts.append(ev.get("content") or "")
            elif et == "done":
                emo = ev.get("emotion") or {}
                _log_step("SSE done", True, f"emotion={emo.get('label')}")
                return "".join(reply_parts)
            elif et == "failed":
                msg = ev.get("message") or "failed"
                _log_step("SSE failed", False, msg)
                return "".join(reply_parts)
            elif et == "obsolete":
                _log_step("SSE obsolete", False, "本代已作废")
                return "".join(reply_parts)

    return "".join(reply_parts)


def _send_headers(token: str, client_msg_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": client_msg_id,
    }


@pytest.mark.asyncio
async def test_meta_unlocks_second_send():
    """收到 SSE meta 后可发第二条（场景：N3 解锁，接口层连发）。"""
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(120.0, connect=30.0, read=120.0)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        await _require_chat_server(client)
        await _get_or_create_test_user()
        token = await _login_get_token(client)

        msg1 = f"[e2e-meta1]{uuid.uuid4().hex[:12]}"
        msg2 = f"[e2e-meta2]{uuid.uuid4().hex[:12]}"
        meta_ready = asyncio.Event()

        async def first_stream():
            body1 = {"content": msg1, "client_message_id": str(uuid.uuid4())}
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/chat/send",
                json=body1,
                headers=_send_headers(token, str(uuid.uuid4())),
            ) as r1:
                if r1.status_code != 200:
                    t = await r1.aread()
                    _e2e_fail_log("首条 HTTP", r1.status_code, 200)
                    assert r1.status_code == 200, (r1.status_code, t[:500])
                ct = (r1.headers.get("content-type") or "").lower()
                assert "text/event-stream" in ct or "application/x-ndjson" in ct, ct
                async for ev in _iter_sse_events(r1):
                    if ev.get("type") == "meta":
                        meta_ready.set()
                    if ev.get("type") in ("done", "failed", "obsolete"):
                        break

        t_first = asyncio.create_task(first_stream())
        try:
            await asyncio.wait_for(meta_ready.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            await t_first
            _e2e_fail_log("首条 SSE meta", "timeout", "收到 type=meta")
            raise

        body2 = {"content": msg2, "client_message_id": str(uuid.uuid4())}
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat/send",
            json=body2,
            headers=_send_headers(token, str(uuid.uuid4())),
        ) as r2:
            if r2.status_code != 200:
                err_body = (await r2.aread()).decode("utf-8", errors="replace")[:800]
                _e2e_fail_log("第二条 HTTP", (r2.status_code, err_body), 200)
                assert False, (r2.status_code, err_body)
            ct2 = (r2.headers.get("content-type") or "").lower()
            assert "text/event-stream" in ct2 or "application/x-ndjson" in ct2, ct2
            saw_meta = False
            async for ev in _iter_sse_events(r2):
                if ev.get("type") == "meta":
                    saw_meta = True
                    break
            if not saw_meta:
                _e2e_fail_log("第二条 SSE", saw_meta, "首帧含 type=meta")
            assert saw_meta

        await t_first


@pytest.mark.asyncio
async def test_sse_failed_marks_user_row(monkeypatch: pytest.MonkeyPatch):
    """
    SSE failed 事件后 user 行应含 failed_* 标记。

    说明：monkeypatch 仅作用于本进程；远程 HTTP 无法桩 LLM，故本用例走 ASGITransport
    + 内存 SQLite（与 tests/test_chat.py 同构），只替换 chat_with_parse_strict，不 mock 路由入队/打包语义。
    """
    from unittest.mock import AsyncMock, patch

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.database import Base, get_db
    from backend.main import app
    import backend.routers.chat as chat_router

    async def _fake_llm_strict(*_a, **_k):
        raise RuntimeError("e2e 强制 LLM 失败")

    monkeypatch.setattr(chat_router.llm_service, "chat_with_parse_strict", _fake_llm_strict)

    TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
    engine_test = create_async_engine(TEST_DB_URL, echo=False)
    async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

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

    prev_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with engine_test.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        mock_redis = AsyncMock()
        store: dict = {}

        async def redis_get(k):
            return store.get(k)

        async def redis_set(k, v, ex=None, px=None, **_kw):
            store[k] = v
            return True

        mock_redis.get = AsyncMock(side_effect=redis_get)
        mock_redis.set = AsyncMock(side_effect=redis_set)

        async def instant_debounce(_uid, coro):
            await coro()

        # 用户名 6–20 位字母或数字（无下划线）
        uname = f"u{uuid.uuid4().hex[:15]}"
        unique = f"[e2e-fail]{uuid.uuid4()}"

        with (
            patch("backend.utils.auth_middleware.get_redis", return_value=mock_redis),
            patch("backend.routers.chat.embedding_service.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 1536),
            patch("backend.routers.chat.dashvector_client.search", new_callable=AsyncMock, return_value=[]),
            patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": True, "reason": ""}),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
            patch("backend.routers.chat.schedule_debounced", side_effect=instant_debounce),
            patch("backend.routers.chat.async_session_maker", async_session_test),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
                reg = await client.post(
                    "/api/auth/register",
                    json={
                        "username": uname,
                        "password": "pass1234",
                        "confirm_password": "pass1234",
                    },
                )
                reg_body = reg.json()
                if reg_body.get("code") != 0:
                    _e2e_fail_log("注册", reg_body, "code=0")
                assert reg_body.get("code") == 0, reg_body
                data = reg_body.get("data") or {}
                token = data.get("token")
                user_id = data.get("user_id")
                assert token and user_id

                body = {"content": unique, "client_message_id": str(uuid.uuid4())}
                saw_failed = False
                last_ev: dict | None = None
                async with client.stream(
                    "POST",
                    "/api/chat/send",
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                ) as resp:
                    assert resp.status_code == 200, (await resp.aread()).decode("utf-8", errors="replace")[:800]
                    ct = (resp.headers.get("content-type") or "").lower()
                    assert "text/event-stream" in ct or "application/x-ndjson" in ct, ct
                    async for ev in _iter_sse_events(resp):
                        last_ev = ev
                        if ev.get("type") == "failed":
                            saw_failed = True
                            break
                if not saw_failed:
                    _e2e_fail_log("SSE 流", last_ev, "type=failed")
                assert saw_failed, "未收到 SSE failed 事件"

        async with async_session_test() as db:
            from sqlalchemy import desc, select

            from backend.models.conversation_log import ConversationLog

            stmt = (
                select(ConversationLog)
                .where(
                    ConversationLog.user_id == user_id,
                    ConversationLog.role == "user",
                    ConversationLog.content == unique,
                )
                .order_by(desc(ConversationLog.id))
                .limit(1)
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
        ds = row.delivery_status if row else None
        ok = (ds or "").startswith("failed_")
        if not ok:
            _e2e_fail_log("user 行 delivery_status", ds, "以 failed_ 前缀开头（failed_timeout / failed_error）")
        assert ok, ds
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prev_overrides)
        await engine_test.dispose()


async def main():
    print("=" * 70)
    print("林小梦 20 轮对话集成测试（HTTP + SSE，需已启动后端）")
    print(f"BASE_URL={BASE_URL}")
    print("=" * 70)

    user_id = await _get_or_create_test_user()
    print(f"\n测试用户 user_id={user_id} (username={E2E_USERNAME})\n")

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits) as client:
        token = await _login_get_token(client)
        _log_step("登录", True, "已获取 JWT")

        for i, msg in enumerate(TEST_MESSAGES, 1):
            try:
                reply = await _send_one_round_sse(client, token, msg, i)
                print(f"【AI 回复】{reply}")
            except Exception as e:
                print(f"\n!!! 第 {i} 轮异常: {e}")
                import traceback

                traceback.print_exc()
            if i < len(TEST_MESSAGES):
                print("\n" + "-" * 70)

    _sep("测试完成", "=")
    print("20 轮已跑完；失败时请确认后端、LLM、Redis、MySQL 可用。")


if __name__ == "__main__":
    asyncio.run(main())
