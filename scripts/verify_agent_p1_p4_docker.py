# -*- coding: utf-8 -*-
"""
Docker 本地验证：P1–P4 主动消息 Step5 生成链路（完整打印版）。

打印内容：
  1. 生成流程步骤说明
  2. 各 HTTP 接口鉴权/请求/响应字段说明
  3. 每轮：上下文 → 记忆检索 → 完整 Prompt（分模块）→ 落库 → 接口数据预览
  4. 可选：真实 HTTP 调用（需账号密码）

用法（容器内）：
  docker compose exec backend python scripts/verify_agent_p1_p4_docker.py \\
    --user-id 1 --triggers P1,P2,P3,P4 --print-prompt full --http-base http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import desc, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import async_session_maker
from backend.models.agent_message import AgentMessage
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.redis_client import get_redis
from backend.services.agent_service import AGENT_FALLBACK_REPLIES, AgentService
from backend.services.open_agent_service import get_unread_count, list_unread_messages
from backend.services.prompt_builder import MODULE_SEPARATOR, PromptBuilder, count_tokens
from backend.services.timeline_read_service import get_timeline


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def _print_generation_flow() -> None:
    print("\n" + "#" * 60)
    print("# 主动消息生成流程（P0–P4 定时扫描路径）")
    print("#" * 60)
    steps = [
        "1. AgentService.check_and_trigger(user_id) — 按 P0→P4 优先级匹配触发",
        "2. 频控：agent:count 每日≤8、间隔≥30min、黑名单（P0 豁免）",
        "3. calculate_action_score ≥ 6 才继续",
        "4. generate_and_save_message:",
        "   4a. 读 emotion_log(近5) + relationship",
        "   4b. 向量检索 Top3 记忆（query=最近情绪）",
        "   4c. PromptBuilder.build_active_message_prompt(trigger_type)",
        "   4d. llm_service.chat_with_step5_parse → messages[] 合并为 content",
        "   4e. 人格风险扫描 → 命中则用 AGENT_FALLBACK_REPLIES",
        "   4f. 写入 agent_message + Redis 计数 + proactive_times",
        "5. H5 拉取：GET /api/agent/messages、GET /api/chat/timeline 合并展示",
    ]
    for s in steps:
        print(s)


def _print_api_reference() -> None:
    print("\n" + "#" * 60)
    print("# 相关 HTTP 接口（契约级字段说明）")
    print("#" * 60)
    apis = [
        {
            "name": "POST /api/auth/login",
            "auth": "无",
            "request": {"username": "str", "password": "str", "remember_me": "bool"},
            "response_data": {"token": "JWT Bearer"},
        },
        {
            "name": "GET /api/agent/unread-count",
            "auth": "Bearer JWT（当前用户）",
            "request": "无 Query",
            "response_data": {"count": "int"},
        },
        {
            "name": "GET /api/agent/messages",
            "auth": "Bearer JWT",
            "request": "无 Query",
            "response_data": "[{id, trigger_type, content, action_score, created_at}]（仅未读）",
        },
        {
            "name": "POST /api/agent/messages/{message_id}/read",
            "auth": "Bearer JWT",
            "request": "Path: message_id",
            "response_data": "ApiResponse code=0",
        },
        {
            "name": "GET /api/chat/timeline",
            "auth": "Bearer JWT",
            "request": "Query: cursor?, limit?",
            "response_data": "items[] 含 source=agent 行：trigger_type, content, sort_seq, is_read",
        },
        {
            "name": "GET /api/open/v1/agent/messages（Open API）",
            "auth": "X-API-Key",
            "request": "无",
            "response_data": "与 H5 /api/agent/messages 同结构",
        },
    ]
    for api in apis:
        print(f"\n▶ {api['name']}")
        print(f"  鉴权: {api['auth']}")
        print(f"  请求: {json.dumps(api['request'], ensure_ascii=False) if isinstance(api['request'], dict) else api['request']}")
        print(f"  响应 data: {api['response_data']}")


def _print_prompt_sections(prompt: str, mode: str) -> None:
    if mode == "none":
        return
    chars = len(prompt)
    tokens = count_tokens(prompt)
    print(f"\n[Prompt 元信息] chars={chars}, tokens≈{tokens}")
    print("[Prompt 完整文本]")
    if mode == "full":
        parts = prompt.split(MODULE_SEPARATOR)
        for i, part in enumerate(parts, 1):
            print(f"\n--- 模块 {i}/{len(parts)} ---")
            print(part.strip())
    else:
        print(prompt[:3000] + ("..." if len(prompt) > 3000 else ""))


async def _print_freq_control_state(user_id: int) -> None:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = await get_redis()
    count_key = f"agent:count:{user_id}:{today}"
    blacklist_key = f"agent:blacklist:{user_id}"
    daily = await r.get(count_key)
    blacklisted = await r.exists(blacklist_key)
    print(
        f"[频控 Redis] {count_key}={daily or 0}, "
        f"{blacklist_key}={'存在' if blacklisted else '无'}"
    )


async def _clear_freq_control(user_id: int) -> None:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = await get_redis()
    await r.delete(f"agent:count:{user_id}:{today}")
    await r.delete(f"agent:blacklist:{user_id}")

    async with async_session_maker() as db:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.user_id == user_id)
            .order_by(desc(AgentMessage.created_at))
            .limit(1)
        )
        latest = (await db.execute(stmt)).scalar_one_or_none()
        if latest is not None:
            latest.created_at = datetime.utcnow() - timedelta(hours=1)
            await db.commit()


async def _print_context_snapshot(user_id: int) -> None:
    async with async_session_maker() as db:
        user = await db.get(User, user_id)
        rel = (
            await db.execute(
                select(Relationship).where(Relationship.user_id == user_id)
            )
        ).scalar_one_or_none()
        emotions = list(
            (
                await db.execute(
                    select(EmotionLog)
                    .where(EmotionLog.user_id == user_id)
                    .order_by(desc(EmotionLog.created_at))
                    .limit(5)
                )
            ).scalars().all()
        )

    print("\n[上下文快照]")
    print(json.dumps(
        {
            "user_id": user.id if user else None,
            "username": user.username if user else None,
            "relationship": {
                "level": rel.level if rel else None,
                "growth_value": rel.growth_value if rel else None,
                "last_interaction_at": (
                    rel.last_interaction_at.isoformat() if rel and rel.last_interaction_at else None
                ),
                "proactive_times": rel.proactive_times if rel else None,
            },
            "emotion_history": [
                {"label": e.emotion_label, "created_at": e.created_at.isoformat()}
                for e in emotions
            ],
        },
        ensure_ascii=False,
        indent=2,
    ))


async def _build_prompt(user_id: int, trigger_type: str) -> str:
    svc = AgentService()
    async with async_session_maker() as db:
        emotion_stmt = (
            select(EmotionLog)
            .where(EmotionLog.user_id == user_id)
            .order_by(desc(EmotionLog.created_at))
            .limit(5)
        )
        emotion_history = list((await db.execute(emotion_stmt)).scalars().all())
        rel = (
            await db.execute(
                select(Relationship).where(Relationship.user_id == user_id)
            )
        ).scalar_one_or_none()

    query_text = "用户的近期状态"
    if emotion_history:
        query_text = f"用户最近的情绪是{emotion_history[0].emotion_label}"

    print(f"\n[记忆检索] query_text={query_text!r}")
    memories = await svc._search_memories_for_agent(user_id, query_text, top_k=3)
    print(f"[记忆检索] hits={len(memories)}")
    for i, mem in enumerate(memories, 1):
        preview = (mem.content or "")[:80]
        print(f"  memory[{i}]: {preview}{'...' if len(mem.content or '') > 80 else ''}")

    async with async_session_maker() as db:
        builder = PromptBuilder(db)
        return await builder.build_active_message_prompt(
            user_id=user_id,
            trigger_type=trigger_type,
            user_memories=memories,
            emotion_history=emotion_history,
            relationship_info=rel,
        )


async def _latest_agent_message(user_id: int) -> AgentMessage | None:
    async with async_session_maker() as db:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.user_id == user_id)
            .order_by(desc(AgentMessage.created_at))
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()


async def _print_api_data_preview(user_id: int, msg: AgentMessage) -> None:
    """与服务层同源，打印各接口将返回的数据（无需 HTTP）。"""
    async with async_session_maker() as db:
        unread_count = await get_unread_count(user_id, db)
        unread_list = await list_unread_messages(user_id, db)
        timeline = await get_timeline(user_id, db, cursor=None, limit=30)

    agent_items = [
        x for x in (timeline.get("items") or [])
        if x.get("source") == "agent"
    ]
    latest_agent_tl = agent_items[-1] if agent_items else None

    print("\n[接口数据预览 — 与服务层一致]")
    print("GET /api/agent/unread-count →")
    print(json.dumps({"code": 0, "data": {"count": unread_count}, "message": "success"}, ensure_ascii=False, indent=2))

    print("\nGET /api/agent/messages → data（未读列表，最新一条高亮）→")
    print(json.dumps({"code": 0, "data": unread_list, "message": "success"}, ensure_ascii=False, indent=2))

    print(f"\n本条落库 agent_message 行（DB 真相源）→")
    print(json.dumps({
        "id": msg.id,
        "user_id": msg.user_id,
        "trigger_type": msg.trigger_type,
        "content": msg.content,
        "action_score": msg.action_score,
        "is_read": msg.is_read,
        "sort_seq": msg.sort_seq,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }, ensure_ascii=False, indent=2))

    if latest_agent_tl:
        print("\nGET /api/chat/timeline → 最近一条 source=agent 行 →")
        print(json.dumps(latest_agent_tl, ensure_ascii=False, indent=2))


async def _http_verify(base: str, username: str, password: str) -> None:
    print("\n" + "#" * 60)
    print("# 真实 HTTP 调用")
    print("#" * 60)
    async with httpx.AsyncClient(timeout=90.0) as client:
        print(f"\n▶ POST {base}/api/auth/login")
        print(f"  Body: {{\"username\": \"{username}\", \"password\": \"***\", \"remember_me\": false}}")
        login = await client.post(
            f"{base}/api/auth/login",
            json={"username": username, "password": password, "remember_me": False},
        )
        body = login.json()
        print(f"  Status: {login.status_code}")
        print(f"  Response: {json.dumps(body, ensure_ascii=False, indent=2)}")
        if login.status_code != 200 or body.get("code") != 0:
            return
        token = (body.get("data") or {}).get("token")
        headers = {"Authorization": f"Bearer {token[:20]}..."}
        real_headers = {"Authorization": f"Bearer {token}"}

        print(f"\n▶ GET {base}/api/agent/unread-count")
        print(f"  Headers: {headers}")
        unread = await client.get(f"{base}/api/agent/unread-count", headers=real_headers)
        print(f"  Response: {json.dumps(unread.json(), ensure_ascii=False, indent=2)}")

        print(f"\n▶ GET {base}/api/agent/messages")
        messages = await client.get(f"{base}/api/agent/messages", headers=real_headers)
        print(f"  Response: {json.dumps(messages.json(), ensure_ascii=False, indent=2)}")

        print(f"\n▶ GET {base}/api/chat/timeline?limit=20")
        timeline = await client.get(
            f"{base}/api/chat/timeline",
            headers=real_headers,
            params={"limit": 20},
        )
        tl_json = timeline.json()
        agent_rows = [
            x for x in (tl_json.get("data") or {}).get("items", [])
            if x.get("source") == "agent"
        ]
        print(f"  agent 行数: {len(agent_rows)}")
        for row in agent_rows[-3:]:
            print("  ", json.dumps(row, ensure_ascii=False))


async def _run_one(
    user_id: int,
    trigger_type: str,
    *,
    print_prompt: str,
    skip_llm: bool,
) -> AgentMessage | None:
    print("\n" + "=" * 60)
    print(f"[{trigger_type}] user_id={user_id}")
    print("=" * 60)

    await _clear_freq_control(user_id)
    await _print_freq_control_state(user_id)
    await _print_context_snapshot(user_id)

    print(f"\n[任务指令类型] trigger_type={trigger_type}")
    print(f"[类型兜底文案] {AGENT_FALLBACK_REPLIES.get(trigger_type, '')!r}")

    prompt = await _build_prompt(user_id, trigger_type)
    _print_prompt_sections(prompt, print_prompt)

    if skip_llm:
        print("\n[跳过] AGENT_VERIFY_SKIP_LLM=1，不调 LLM、不落库")
        return None

    svc = AgentService()
    score_before = await svc.calculate_action_score(user_id, trigger_type)
    print(f"\n[行动评分] calculate_action_score={score_before}")

    ok = await svc.generate_and_save_message(user_id, trigger_type)
    print(f"[生成] generate_and_save_message → {ok}")

    msg = await _latest_agent_message(user_id)
    if not msg:
        print("[落库] 未找到 agent_message")
        return None

    fallback = AGENT_FALLBACK_REPLIES.get(trigger_type, "")
    is_fallback = msg.content.strip() == fallback.strip()
    print(
        f"\n[落库结果] id={msg.id} trigger={msg.trigger_type} "
        f"score={msg.action_score} sort_seq={msg.sort_seq} "
        f"is_type_fallback={is_fallback}"
    )
    print("[落库 content]")
    print(msg.content)
    if "走神" in msg.content or "你刚才说什么" in msg.content:
        print("⚠️  警告：仍出现对话走神占位文案")

    await _print_api_data_preview(user_id, msg)
    await _print_freq_control_state(user_id)
    return msg


async def main() -> None:
    parser = argparse.ArgumentParser(description="验证 P1–P4 主动消息 Step5 链路（完整打印）")
    parser.add_argument("--user-id", type=int, default=_env_int("AGENT_VERIFY_USER_ID", 1))
    parser.add_argument("--triggers", default="P1,P2,P3,P4")
    parser.add_argument(
        "--print-prompt",
        choices=["full", "head", "none"],
        default="full" if os.environ.get("AGENT_VERIFY_PRINT_PROMPT", "1") == "1" else "none",
    )
    parser.add_argument(
        "--http-base",
        default=os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--username", default=os.environ.get("AGENT_VERIFY_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("AGENT_VERIFY_PASSWORD", ""))
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        default=os.environ.get("AGENT_VERIFY_SKIP_LLM", "0") == "1",
    )
    parser.add_argument("--skip-http", action="store_true")
    args = parser.parse_args()

    _print_generation_flow()
    _print_api_reference()

    triggers = [t.strip().upper() for t in args.triggers.split(",") if t.strip()]

    username = args.username
    if not username:
        async with async_session_maker() as db:
            u = await db.get(User, args.user_id)
            if u:
                username = u.username

    for trigger in triggers:
        await _run_one(
            args.user_id,
            trigger,
            print_prompt=args.print_prompt,
            skip_llm=args.skip_llm,
        )

    if not args.skip_llm and not args.skip_http and args.http_base:
        if args.password and username:
            await _http_verify(args.http_base.rstrip("/"), username, args.password)
        else:
            print("\n[HTTP] 跳过真实调用：请传 --password 或设置 AGENT_VERIFY_PASSWORD")
            print(f"      检测到 username={username!r}，可执行：")
            print(
                f"      AGENT_VERIFY_PASSWORD=你的密码 docker exec lxm_backend "
                f"python /app/scripts/verify_agent_p1_p4_docker.py --user-id {args.user_id}"
            )


if __name__ == "__main__":
    asyncio.run(main())
