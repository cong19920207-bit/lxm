# -*- coding: utf-8 -*-
"""
对比验证：旧 memory_service 提取 vs Step6 向量写入（Docker 本地）。

用法（仓库根目录）：
  export SMOKE_BASE_URL=http://127.0.0.1:8000
  python3 scripts/verify_step6_vs_old_memory.py

依赖：backend 容器已 up；.env 中 LLM / Embedding / DashVector 有效。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = os.environ.get("VERIFY_USERNAME", "e2esmoke1")
PASSWORD = os.environ.get("VERIFY_PASSWORD", "pass1234")
# 含高重要性关键词，提高旧记忆 extract 入库概率（>=3 分）
CHAT_MSG = os.environ.get(
    "VERIFY_CHAT_MSG",
    "我叫张明，最喜欢吃火锅，最近工作压力很大经常加班到凌晨一点才睡。",
)


async def _iter_sse(resp: httpx.Response) -> AsyncIterator[dict]:
    buf = ""
    async for chunk in resp.aiter_bytes():
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if line.startswith("data: "):
                try:
                    yield json.loads(line[6:])
                except json.JSONDecodeError:
                    pass


async def login_or_register(client: httpx.AsyncClient) -> tuple[str, int | None]:
    r = await client.post(
        f"{BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD, "remember_me": False},
    )
    b = r.json()
    if b.get("code") == 0:
        d = b.get("data") or {}
        return d["token"], d.get("user_id")

    reg = await client.post(
        f"{BASE}/api/auth/register",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    rb = reg.json()
    if rb.get("code") != 0:
        raise RuntimeError(f"注册/登录失败: {rb}")
    d = rb.get("data") or {}
    return d["token"], d.get("user_id")


async def send_one_round(client: httpx.AsyncClient, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Client-Message-Id": str(uuid.uuid4()),
    }
    body = {"content": CHAT_MSG, "client_message_id": str(uuid.uuid4())}
    done = None
    failed = None
    async with client.stream(
        "POST",
        f"{BASE}/api/chat/send",
        json=body,
        headers=headers,
        timeout=180.0,
    ) as resp:
        if resp.status_code != 200:
            t = await resp.aread()
            raise RuntimeError(f"HTTP {resp.status_code}: {t[:500]}")
        async for ev in _iter_sse(resp):
            t = ev.get("type")
            if t == "done":
                done = ev
            elif t in ("failed", "obsolete"):
                failed = ev
    return {"done": done, "failed": failed}


def docker_logs_grep(pattern: str, tail: int = 800) -> str:
    cmd = [
        "docker", "logs", "lxm_backend", "--tail", str(tail), "2>&1",
    ]
    try:
        out = subprocess.run(
            ["docker", "logs", "lxm_backend", "--tail", str(tail)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (out.stdout or "") + (out.stderr or "")
    except Exception as e:
        return f"(读取日志失败: {e})"
    lines = [ln for ln in text.splitlines() if pattern in ln]
    return "\n".join(lines[-40:]) if lines else "(无匹配行)"


def mysql_query(sql: str) -> str:
    cmd = [
        "docker", "exec", "lxm_mysql",
        "mysql", "-ulxm", "-plxm123456", "lxm", "-N", "-e", sql,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return f"SQL 错误: {r.stderr.strip()}"
        return (r.stdout or "").strip() or "(空结果)"
    except Exception as e:
        return f"MySQL 查询失败: {e}"


async def main() -> int:
    print("=== Step6 vs 旧记忆 本地验证 ===\n")
    print(f"BASE_URL: {BASE}")
    print(f"用户: {USERNAME}")
    print(f"消息: {CHAT_MSG[:80]}...\n")

    async with httpx.AsyncClient() as client:
        token, user_id_from_api = await login_or_register(client)
        uid_row = mysql_query(
            f"SELECT id FROM users WHERE username='{USERNAME}' LIMIT 1;"
        )
        try:
            user_id = int(uid_row.split()[0])
        except (ValueError, IndexError):
            user_id = user_id_from_api
        print(f"user_id = {user_id}\n")

        # 写入前快照
        mem_before = mysql_query(
            f"SELECT COUNT(*) FROM memory WHERE user_id={user_id} AND is_deleted=0;"
        )
        print(f"[写入前] memory 表有效条数: {mem_before}")

        print("\n--- 发送一轮对话（等待 SSE done）---")
        result = await send_one_round(client, token)
        if result["failed"]:
            print(f"SSE 失败: {json.dumps(result['failed'], ensure_ascii=False)[:500]}")
            return 1
        if not result["done"]:
            print("未收到 done 事件")
            return 1
        print("SSE done 已收到")

    print("\n等待后台任务（旧记忆 extract + Step6）… sleep 25s")
    time.sleep(25)

    mem_after = mysql_query(
        f"SELECT COUNT(*) FROM memory WHERE user_id={user_id} AND is_deleted=0;"
    )
    print(f"\n[写入后] memory 表有效条数: {mem_after}")

    recent_mem = mysql_query(
        f"SELECT id, LEFT(content,60), source, importance_score, dashvector_id "
        f"FROM memory WHERE user_id={user_id} AND is_deleted=0 "
        f"ORDER BY id DESC LIMIT 5;"
    )
    print(f"\n[最近 memory 行]\n{recent_mem}")

    rel = mysql_query(
        f"SELECT user_real_name, user_hobby_name, LEFT(user_description,40), "
        f"LEFT(relation_description,40) FROM relationship WHERE user_id={user_id};"
    )
    print(f"\n[relationship 标量]\n{rel}")

    hist = mysql_query(
        f"SELECT COUNT(*) FROM relationship_change_history "
        f"WHERE user_id={user_id} AND trigger_source='step6';"
    )
    print(f"\n[step6 关系变更历史条数] {hist}")

    print("\n--- backend 日志：Step6 ---")
    print(docker_logs_grep("Step6"))

    print("\n--- backend 日志：旧记忆提取 ---")
    print(docker_logs_grep("提取到") + "\n" + docker_logs_grep("记忆提取") + "\n" + docker_logs_grep("用户 %d 本轮" % user_id if False else "候选记忆"))

    print("\n--- backend 日志：DashVector Step6 写入 ---")
    s6_vec = docker_logs_grep("Step6 向量")
    print(s6_vec)

    print("\n--- backend 日志：Step6 失败/跳过 ---")
    print(
        docker_logs_grep("Step6 首次失败")
        + "\n"
        + docker_logs_grep("重试后仍失败")
        + "\n"
        + docker_logs_grep("向量写入跳过")
    )

    # 容器内用 Python 查 DashVector user 型文档（若配置了密钥）
    print("\n--- 容器内 DashVector user 路抽样（doc_id 前缀）---")
    py_check = r"""
import asyncio
from backend.constants import MEMORY_TYPE_USER
from backend.services.embedding_service import embedding_service
from backend.utils.dashvector_client import dashvector_client

async def main():
    uid = """ + str(user_id) + r"""
    emb = await embedding_service.get_embedding("用户喜欢吃什么习惯")
    if not emb:
        print("embedding 为空，无法检索")
        return
    rows = await dashvector_client.search(
        vector=emb, memory_type=MEMORY_TYPE_USER, user_id=uid, top_k=10, threshold=0.0
    )
    mem_old = [r for r in rows if (r.get("id") or "").startswith("mem_")]
    mem_s6 = [r for r in rows if (r.get("id") or "").startswith("user:")]
    print(f"检索命中 total={len(rows)} mem_*={len(mem_old)} user:*={len(mem_s6)}")
    for r in rows[:8]:
        print(f"  id={r.get('id')} score={r.get('score',0):.4f} content={str(r.get('content',''))[:50]}")

asyncio.run(main())
"""
    r = subprocess.run(
        ["docker", "exec", "lxm_backend", "python", "-c", py_check],
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(r.stdout or "")
    if r.stderr:
        print("stderr:", r.stderr[:800])

    print("\n=== 结论提示 ===")
    print("- 旧记忆：看 memory 表是否 +1、日志「提取到 N 条候选记忆」、DashVector mem_*")
    print("- Step6：看日志「Step6 完成」/「向量写入成功 user:」、DashVector user:* 前缀")
    print("- 二者 doc_id 不同，正常不会互相覆盖；旧去重≥0.92 可能 delete 掉 Step6 的 user:* 向量")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
