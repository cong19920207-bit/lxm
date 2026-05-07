# -*- coding: utf-8 -*-
"""
Docker 本地后端：通过真实 HTTP（与用户端一致）触发对话打包链路，便于你 tail 日志验证 Step5.5 / Step6 是否与 LLM 交互。

说明：
  - 项目**没有**单独的「只跑 Step5.5」或「只跑 Step6」接口；二者均在 POST /api/chat/send → 防抖打包 → Step5 成功后执行。
  - Step6：每轮对话闭环成功后会 asyncio.create_task(execute_step6)，应在 backend 日志里能看到 Volces 请求或 Step6 完成/失败。
  - Step5.5：受 admin_config「step5_5_enabled」与双门闩随机控制；开关关闭则整轮不会调用 Step5.5 的 LLM。

用法（宿主机，指向 Docker 映射端口，默认 8000）：
  cd 仓库根目录
  export SMOKE_BASE_URL=http://127.0.0.1:8000
  python3 scripts/docker_step55_step6_smoke.py

测试账号：e2esmoke1 / pass1234（与注册规则一致：6～20 位字母数字；首次运行会自动注册）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
import httpx


def _base_url() -> str:
    return os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


async def _iter_sse_events(resp: httpx.Response) -> AsyncIterator[dict]:
    buf = ""
    async for chunk in resp.aiter_bytes():
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                continue


SMOKE_USERNAME = "e2esmoke1"
SMOKE_PASSWORD = "pass1234"


async def _ensure_user_session(client: httpx.AsyncClient, base: str) -> str:
    """优先登录；失败则注册（注册成功响应内已含 token，直接使用以避免紧接着登录偶发「用户不存在」）。"""
    login_resp = await client.post(
        f"{base}/api/auth/login",
        json={"username": SMOKE_USERNAME, "password": SMOKE_PASSWORD, "remember_me": False},
    )
    body = login_resp.json()
    if login_resp.status_code == 200 and body.get("code") == 0:
        tok = (body.get("data") or {}).get("token")
        if tok:
            return tok

    reg = await client.post(
        f"{base}/api/auth/register",
        json={
            "username": SMOKE_USERNAME,
            "password": SMOKE_PASSWORD,
            "confirm_password": SMOKE_PASSWORD,
        },
    )
    reg_body = reg.json()
    if reg.status_code == 200 and reg_body.get("code") == 0:
        tok = (reg_body.get("data") or {}).get("token")
        if tok:
            print("已自动注册测试账号（此前库中不存在），使用注册返回的 token。")
            return tok

    if reg_body.get("code") not in (0, None):
        print(f"注册响应: {reg_body.get('message')}")

    login_resp2 = await client.post(
        f"{base}/api/auth/login",
        json={"username": SMOKE_USERNAME, "password": SMOKE_PASSWORD, "remember_me": False},
    )
    login_resp2.raise_for_status()
    body2 = login_resp2.json()
    if body2.get("code") != 0:
        raise RuntimeError(f"登录失败: {body2}")
    tok = (body2.get("data") or {}).get("token")
    if not tok:
        raise RuntimeError("登录响应无 token")
    return tok


# 多轮略长输入，略提高 Step5 输出 knowledge_expand=「是」的机会（仍不保证 Step5.5 门闩命中）
DEFAULT_MESSAGES = [
    "我想顺便了解下星空和大海的一些冷知识，可以展开讲讲吗？",
    "刚才说的里哪一条最适合讲给小朋友听？帮我压缩成一两句。",
    "今天先聊到这，我去吃饭了，谢谢～",
]


async def _one_round(
    client: httpx.AsyncClient, base: str, token: str, text: str, idx: int
) -> tuple[bool, str]:
    """返回 (sse_done是否成功, 拼接回复)"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    body = {"content": text, "client_message_id": str(uuid.uuid4())}
    parts: list[str] = []
    ok = False
    async with client.stream("POST", f"{base}/api/chat/send", json=body, headers=headers) as resp:
        if resp.status_code != 200:
            err = (await resp.aread()).decode("utf-8", errors="replace")[:600]
            print(f"  [HTTP {resp.status_code}] {err}")
            return False, ""
        async for ev in _iter_sse_events(resp):
            t = ev.get("type")
            if t == "delta":
                parts.append(ev.get("content") or "")
            elif t == "done":
                ok = True
            elif t == "failed":
                print(f"  [SSE failed] {ev}")
    reply = "".join(parts)
    print(f"\n--- 第 {idx} 轮 ---\n用户: {text[:80]}...\nSSE 成功: {ok}\n回复摘要: {reply[:120]}...")
    return ok, reply


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None, help="默认 env SMOKE_BASE_URL 或 http://127.0.0.1:8000")
    ap.add_argument("--rounds", type=int, default=3, help="对话轮数")
    args = ap.parse_args()
    base = (args.base_url or _base_url()).rstrip("/")

    print("=" * 60)
    print("Docker Step5.5 / Step6 烟囱测试（HTTP → 与 H5 同接口）")
    print(f"BASE_URL={base}")
    print("用户: e2esmoke1 / pass1234")
    print("=" * 60)

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(120.0, connect=15.0, read=120.0)
    msgs = DEFAULT_MESSAGES[: max(1, args.rounds)]

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        try:
            r = await client.get(f"{base}/openapi.json", timeout=5.0)
            if r.status_code >= 500:
                print(f"警告: 服务返回 {r.status_code}")
        except Exception as e:
            print(f"错误: 无法连接 {base} — {e}")
            print("请确认 docker compose 已启动且 backend 映射了 8000:8000。")
            sys.exit(1)

        token = await _ensure_user_session(client, base)
        print("登录成功。\n")

        for i, m in enumerate(msgs, 1):
            await _one_round(client, base, token, m, i)

    print("\n" + "=" * 60)
    print("接下来在宿主机另开终端，查看 backend 容器日志中与 LLM / Step 相关的行：")
    print()
    print("  docker logs lxm_backend 2>&1 | tail -300 \\")
    print("    | grep -E 'Step5\\.5|Step6 |Step6 完成|Step6 首次失败|重试后仍失败|"
          "Step5\\.5 执行成功|Step5\\.5 LLM|chat/completions|非流式调用'")
    print()
    print("说明：")
    print("  - Step6：只要本轮 SSE 成功，一般会发起记忆 LLM（异步），日志里应有 ark/volces 或非流式调用。")
    print("  - Step5.5：需 admin_config 中 step5_5_enabled 开启，且双门闩命中（约 12% 或 knowledge_expand 为「是」时 50%）；")
    print("    未命中则不会出现 Step5.5 专用日志，属预期。")
    print("  - 开启开关方式见：tests/docker_step55_step6_验证说明.md")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
