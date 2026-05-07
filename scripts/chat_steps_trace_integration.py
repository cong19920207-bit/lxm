# -*- coding: utf-8 -*-
"""
林小梦对话链路 Step 追踪集成脚本（5 轮串行，样式对齐 test_output.log）

在同进程内通过 ASGITransport 调用真实 FastAPI 路由，真实 MySQL（.env），并对 LLM 调用打标，
记录：Step1.5 / Step5 / Step5.5 / Step6 / 记忆提取等非流式 chat_sync 的提示词与原始输出摘要。

运行前：
  1. 配置可用 .env（MySQL、Redis 可用；火山 Ark / DashScope 等密钥正确）
  2. 建议使用独占测试库；脚本使用用户 e2e_test_user（不存在则创建）

用法：
  cd 仓库根目录
  PYTHONPATH=. python3 scripts/chat_steps_trace_integration.py
  PYTHONPATH=. python3 scripts/chat_steps_trace_integration.py --output-log tests/chat_steps_trace_run.log --output-md tests/chat_steps_trace_report.md

说明文档：tests/chat_steps_trace_使用说明.md

说明：
  - 使用 unittest.mock 将防抖改为「立即执行打包」，避免等待防抖延迟。
  - Redis 使用内存桩（AsyncMock），仅满足 chat:gen / debounce 等键读写。
  - 每轮结束后 sleep 数秒，便于 Step6 异步任务与记忆提取中的 LLM 尽量落在当前轮记录内。
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

# ============ 必须在导入 backend.main 之前桩掉 scheduler，避免 lifespan 挂真实定时任务 ============
import types

_sched_mod = types.ModuleType("backend.tasks.scheduler")
_sched_mod.start_scheduler = lambda *a, **k: None
_sched_mod.shutdown_scheduler = lambda *a, **k: None
sys.modules["backend.tasks.scheduler"] = _sched_mod

_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from dotenv import load_dotenv

load_dotenv(_proj_root / ".env", override=True)

import httpx
from httpx import ASGITransport

# 当前 LLM 调用归属步骤（供 chat_sync 包装器写入）
STEP_CTX: contextvars.ContextVar[str] = contextvars.ContextVar("step_ctx", default="")


class TraceRecorder:
    """收集一轮对话内所有 LLM 调用与其它结构化事件。"""

    def __init__(self) -> None:
        self.llm_calls: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def add_llm(
        self,
        *,
        step: str,
        prompt: str,
        raw_out: str | None,
        ok: bool,
        err: str | None,
        timeout_sec: float | None,
        elapsed_sec: float | None,
    ) -> None:
        self.llm_calls.append(
            {
                "step": step,
                "prompt_len": len(prompt),
                "prompt": prompt,
                "raw_out_len": len(raw_out or ""),
                "raw_out": raw_out,
                "ok": ok,
                "error": err,
                "timeout_sec": timeout_sec,
                "elapsed_sec": elapsed_sec,
            }
        )

    def add_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, **payload})


def _mock_redis_store() -> tuple[AsyncMock, dict]:
    """简易 Redis 桩：支持 get/set/decr 等 chat 所需操作。"""
    store: dict[str, Any] = {}

    async def _get(k):
        return store.get(k)

    async def _set(k, v, ex=None, px=None, nx=False, **_kw):
        store[k] = v
        return True

    async def _delete(k):
        store.pop(k, None)

    r = AsyncMock()
    r.get = AsyncMock(side_effect=_get)
    r.set = AsyncMock(side_effect=_set)
    r.delete = AsyncMock(side_effect=_delete)
    r.decr = AsyncMock(return_value=0)
    r.incr = AsyncMock(return_value=1)
    r.lpush = AsyncMock(return_value=1)
    r.ltrim = AsyncMock(return_value=True)
    r.setex = AsyncMock(side_effect=_set)
    r.setnx = AsyncMock(return_value=True)
    return r, store


async def _instant_debounce(user_id: int, coro) -> None:
    """立即执行打包任务，等价于防抖延迟为 0。"""
    await coro()


def _fmt_prompt_box(title: str, text: str, max_chars: int = 12000) -> str:
    body = text if len(text) <= max_chars else text[:max_chars] + "\n... [截断] ..."
    return f"      --- {title} ---\n" + "\n".join(f"      {ln}" for ln in body.split("\n"))


def _print_round_trace(tr: TraceRecorder, round_idx: int, user_text: str, sse_ok: bool, assistant_text: str) -> None:
    print(f"\n{'=' * 26} 第 {round_idx} 轮对话 {'=' * 26}")
    print(f"【用户输入】{user_text}")
    print(f"【SSE 闭环】{'成功' if sse_ok else '失败/超时'}")
    if assistant_text:
        print(f"【AI 回复摘要】{assistant_text[:500]}{'...' if len(assistant_text) > 500 else ''}")

    # 按步骤分组打印 LLM
    by_step: dict[str, list] = defaultdict(list)
    for c in tr.llm_calls:
        by_step[c["step"]].append(c)

    # 按流水线顺序输出：Step1.5 → Step2（检索摘要）→ Step5 → …
    def _emit_block(name: str, calls: list) -> None:
        if not calls:
            return
        print(f"\n------------------------------ [{name}] LLM ------------------------------")
        for i, c in enumerate(calls, 1):
            ok = c["ok"]
            status = "[成功]" if ok else "[失败]"
            ext = ""
            if c.get("elapsed_sec") is not None:
                ext += f" elapsed={c['elapsed_sec']:.2f}s"
            if c.get("timeout_sec"):
                ext += f" timeout={c['timeout_sec']}s"
            print(f"  {status} 第{i}次调用{ext}")
            if c.get("error"):
                print(f"       error={c['error'][:300]}")
            print(_fmt_prompt_box("Prompt", c.get("prompt") or ""))
            raw = c.get("raw_out") or ""
            print(f"      --- LLM 原始输出 (len={len(raw)}) ---")
            for ln in (raw[:8000] + ("..." if len(raw) > 8000 else "")).split("\n"):
                print(f"      {ln}")

    _emit_block("Step1.5", by_step.get("Step1.5") or [])

    for ev in tr.events:
        if ev.get("kind") == "step2_retrieval":
            print("\n------------------------------ [Step2] 多路向量检索 ------------------------------")
            print(f"  [摘要] {ev.get('summary', '')}")

    for step_name in ["Step5", "Step5.5", "Step6", "MemoryExtract", "其它"]:
        _emit_block(step_name, by_step.get(step_name) or [])

    if not tr.llm_calls and not tr.events:
        print("\n  （本轮未捕获到 LLM 调用，可能主链在并行步骤已失败或未发起打包）")


def _build_markdown(
    rounds: list[dict[str, Any]],
    out_path: Path,
) -> None:
    lines = [
        "# 对话 Step 追踪报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 说明：LLM 调用来自同进程包装器；Step6/记忆提取与下一轮之间可能存在交错，请以时间戳与步骤标签为准。",
        "",
        "## 汇总",
        "",
        "| 轮次 | 用户摘要 | SSE | Step1.5 | Step5 | Step5.5 | Step6 | MemoryExtract |",
        "|------|----------|-----|---------|-------|---------|-------|---------------|",
    ]
    for r in rounds:
        def cnt(step: str, ok_only: bool = False) -> str:
            cs = [x for x in r["llm_calls"] if x["step"] == step]
            if ok_only:
                cs = [x for x in cs if x["ok"]]
            good = sum(1 for x in cs if x["ok"])
            bad = sum(1 for x in cs if not x["ok"])
            if not cs:
                return "—"
            return f"成功{good}/失败{bad}"

        lines.append(
            "| {idx} | {utext} | {sse} | {s15} | {s5} | {s55} | {s6} | {mem} |".format(
                idx=r["round"],
                utext=(r["user_text"][:40] + "…") if len(r["user_text"]) > 40 else r["user_text"],
                sse="✓" if r["sse_ok"] else "✗",
                s15=cnt("Step1.5"),
                s5=cnt("Step5"),
                s55=cnt("Step5.5"),
                s6=cnt("Step6"),
                mem=cnt("MemoryExtract"),
            )
        )
    lines.extend(["", "## 逐轮详情", ""])
    for r in rounds:
        lines.append(f"### 第 {r['round']} 轮")
        lines.append("")
        lines.append(f"- 用户输入：`{r['user_text']}`")
        lines.append(f"- SSE：{'成功' if r['sse_ok'] else '失败'}")
        lines.append("")
        for c in r["llm_calls"]:
            st = "成功" if c["ok"] else "失败"
            lines.append(f"- **{c['step']}** ({st}) prompt_len={c['prompt_len']} raw_len={c['raw_out_len']}")
            if c.get("error"):
                lines.append(f"  - error: `{c['error'][:200]}`")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


DEFAULT_MESSAGES = [
    "你好呀，我刚下班，今天有点累。",
    "对了，我周末想去爬山，你有什么放松的小建议吗？",
    "哈哈换个话题——如果我让你一分钟后提醒我喝水，你能做到吗？",
    "那你记住：我平时喝温水，不喝冰水。",
    "今天就聊到这儿吧，我得去洗漱了，晚安～",
]


async def _trace_get_or_create_test_user() -> int:
    """与 scripts/test_chat_e2e 一致：确保存在 e2e_test_user。"""
    import bcrypt
    from sqlalchemy import select

    from backend.database import async_session_maker
    from backend.models.relationship import Relationship
    from backend.models.user import User

    E2E_USERNAME = "e2e_test_user"
    E2E_PASSWORD = "pass1234"

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


async def _trace_login_get_token(client: httpx.AsyncClient, base_url: str = "http://test") -> str:
    resp = await client.post(
        f"{base_url}/api/auth/login",
        json={"username": "e2e_test_user", "password": "pass1234", "remember_me": False},
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


def _wrap_step2_mvr(orig_fn):
    async def _inner(**kw):
        from backend.services import multi_vector_retrieval_service as m

        r = await orig_fn(**kw)
        rec = getattr(m, "_trace_recorder", None)
        if rec is not None:
            try:
                um = len(r.user_memory_results)
                summary = f"user_memory_hits={um} is_fallback={r.is_fallback}"
                rec.add_event("step2_retrieval", {"summary": summary})
            except Exception:
                rec.add_event("step2_retrieval", {"summary": "(摘要失败)"})
        return r

    return _inner


def _wrap_qr(orig):
    async def _inner(**kw):
        tok = STEP_CTX.set("Step1.5")
        try:
            return await orig(**kw)
        finally:
            STEP_CTX.reset(tok)

    return _inner


def _wrap_llm_parse(orig_bound):
    async def _inner(*a, **kw):
        tok = STEP_CTX.set("Step5")
        try:
            return await orig_bound(*a, **kw)
        finally:
            STEP_CTX.reset(tok)

    return _inner


def _wrap_module_async_fn(orig, tag: str):
    async def _inner(*a, **kw):
        tok = STEP_CTX.set(tag)
        try:
            return await orig(*a, **kw)
        finally:
            STEP_CTX.reset(tok)

    return _inner


async def main_async(args: argparse.Namespace) -> None:
    messages = DEFAULT_MESSAGES[: args.rounds]

    # 延迟导入应用（scheduler 已桩）
    from backend.main import app

    mock_r, _store = _mock_redis_store()

    orig_chat_sync_holder: list[Any] = [None]

    async def tracing_chat_sync(prompt: str, timeout_sec: float | None = None):
        import time

        from backend.utils import llm_client as lc_mod

        t0 = time.monotonic()
        step = STEP_CTX.get() or "其它"
        err = None
        raw = None
        ok = False
        try:
            raw = await orig_chat_sync_holder[0](prompt, timeout_sec=timeout_sec)
            ok = True
            return raw
        except Exception as e:
            err = str(e)
            raise
        finally:
            elapsed = time.monotonic() - t0
            rec: TraceRecorder | None = getattr(lc_mod, "_trace_recorder", None)
            if rec is not None:
                rec.add_llm(
                    step=step,
                    prompt=prompt,
                    raw_out=raw,
                    ok=ok,
                    err=err,
                    timeout_sec=timeout_sec,
                    elapsed_sec=elapsed,
                )

    from backend.services import multi_vector_retrieval_service as mv_svc
    from backend.services import query_rewrite_service as qr_svc
    from backend.services import step5_5_service as s55_svc
    from backend.services import step6_orchestrator as s6_svc
    from backend.services.llm_service import llm_service
    from backend.services.memory_service import MemoryService
    from backend.utils import llm_client as lc_mod

    _orig_mvr = mv_svc.execute_multi_vector_retrieval
    _orig_qr = qr_svc.execute_query_rewrite
    _orig_s5 = llm_service.chat_with_step5_parse
    _orig_s55 = s55_svc.execute_step5_5
    _orig_s6 = s6_svc.execute_step6
    _orig_mem = MemoryService._extract_memories_from_llm

    rounds_report: list[dict[str, Any]] = []

    transport = ASGITransport(app=app)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(180.0, connect=30.0, read=180.0)

    async with httpx.AsyncClient(transport=transport, base_url="http://test", limits=limits, timeout=timeout) as client:
        await _trace_get_or_create_test_user()
        token = await _trace_login_get_token(client)

        orig_chat_sync_holder[0] = lc_mod.llm_client.chat_sync

        mv_svc.execute_multi_vector_retrieval = _wrap_step2_mvr(_orig_mvr)
        qr_svc.execute_query_rewrite = _wrap_qr(_orig_qr)
        llm_service.chat_with_step5_parse = _wrap_llm_parse(_orig_s5)
        s55_svc.execute_step5_5 = _wrap_module_async_fn(_orig_s55, "Step5.5")
        s6_svc.execute_step6 = _wrap_module_async_fn(_orig_s6, "Step6")

        async def _mem_wrap(self, *a, **kw):
            tok = STEP_CTX.set("MemoryExtract")
            try:
                return await _orig_mem(self, *a, **kw)
            finally:
                STEP_CTX.reset(tok)

        MemoryService._extract_memories_from_llm = _mem_wrap

        try:
            lc_mod.llm_client.chat_sync = tracing_chat_sync

            with patch("backend.redis_client.get_redis", AsyncMock(return_value=mock_r)):
                with patch("backend.utils.auth_middleware.get_redis", AsyncMock(return_value=mock_r)):
                    with patch("backend.services.prompt_builder.get_redis", AsyncMock(return_value=mock_r)):
                        with patch("backend.services.chat_queue_service.get_redis", AsyncMock(return_value=mock_r)):
                            with patch("backend.routers.chat.get_redis", AsyncMock(return_value=mock_r)):
                                with patch(
                                    "backend.services.llm_service.get_redis",
                                    AsyncMock(return_value=mock_r),
                                ):
                                    with patch(
                                        "backend.services.chat_queue_service.schedule_debounced",
                                        side_effect=_instant_debounce,
                                    ):
                                        with patch(
                                            "backend.routers.chat.schedule_debounced",
                                            side_effect=_instant_debounce,
                                        ):
                                            print("=" * 70)
                                            print("林小梦 对话 Step 追踪（ASGI 同进程，真实 DB + 真实 LLM）")
                                            print(f"轮次={len(messages)}，用户=e2e_test_user")
                                            print("=" * 70)

                                            for idx, user_text in enumerate(messages, start=1):
                                                tr = TraceRecorder()
                                                lc_mod._trace_recorder = tr
                                                mv_svc._trace_recorder = tr

                                                reply_accum: list[str] = []
                                                sse_ok = False

                                                headers = {
                                                    "Authorization": f"Bearer {token}",
                                                    "Content-Type": "application/json",
                                                    "Idempotency-Key": str(uuid.uuid4()),
                                                }
                                                body = {
                                                    "content": user_text,
                                                    "client_message_id": str(uuid.uuid4()),
                                                }

                                                try:
                                                    async with client.stream(
                                                        "POST",
                                                        "/api/chat/send",
                                                        json=body,
                                                        headers=headers,
                                                    ) as resp:
                                                        if resp.status_code != 200:
                                                            raw = (await resp.aread()).decode(
                                                                "utf-8", errors="replace"
                                                            )
                                                            print(f"\n!!! HTTP {resp.status_code}: {raw[:600]}")
                                                            sse_ok = False
                                                        else:
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
                                                                    et = ev.get("type")
                                                                    if et == "delta":
                                                                        reply_accum.append(ev.get("content") or "")
                                                                    elif et == "done":
                                                                        sse_ok = True
                                                                    elif et == "failed":
                                                                        sse_ok = False
                                                                        print(f"\n!!! SSE failed: {ev}")
                                                except Exception as e:
                                                    print(f"\n!!! 第 {idx} 轮请求异常: {e}")
                                                    import traceback

                                                    traceback.print_exc()
                                                    sse_ok = False

                                                assistant_text = "".join(reply_accum)
                                                _print_round_trace(tr, idx, user_text, sse_ok, assistant_text)

                                                rounds_report.append(
                                                    {
                                                        "round": idx,
                                                        "user_text": user_text,
                                                        "sse_ok": sse_ok,
                                                        "assistant_preview": assistant_text[:200],
                                                        "llm_calls": list(tr.llm_calls),
                                                    }
                                                )

                                                await asyncio.sleep(max(2.0, args.post_round_sleep))

            _build_markdown(rounds_report, Path(args.output_md))
            print("\n" + "=" * 70)
            print(f"已生成 Markdown 报告: {args.output_md}")
            print("=" * 70)

        finally:
            lc_mod.llm_client.chat_sync = orig_chat_sync_holder[0]
            mv_svc.execute_multi_vector_retrieval = _orig_mvr
            qr_svc.execute_query_rewrite = _orig_qr
            llm_service.chat_with_step5_parse = _orig_s5
            s55_svc.execute_step5_5 = _orig_s55
            s6_svc.execute_step6 = _orig_s6
            MemoryService._extract_memories_from_llm = _orig_mem


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="对话 Step 追踪集成脚本")
    p.add_argument("--rounds", type=int, default=5, help="对话轮数（默认 5）")
    p.add_argument(
        "--post-round-sleep",
        type=float,
        default=4.0,
        dest="post_round_sleep",
        help="每轮 SSE 结束后等待秒数，便于异步 Step6/记忆提取完成（默认 4）",
    )
    p.add_argument(
        "--output-log",
        default="",
        help="若指定，将 stdout 同步写入该文件（需自行 tee 或后续改为脚本内 tee）",
    )
    p.add_argument(
        "--output-md",
        default=str(_proj_root / "tests" / "chat_steps_trace_report.md"),
        help="Markdown 报告输出路径",
    )
    return p.parse_args()


if __name__ == "__main__":
    _args = parse_args()
    _tee_fp = None
    _orig_stdout = sys.stdout

    class _TeeOut:
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                s.write(data)

        def flush(self):
            for s in self.streams:
                s.flush()

    if _args.output_log:
        _p = Path(_args.output_log)
        _p.parent.mkdir(parents=True, exist_ok=True)
        _tee_fp = _p.open("w", encoding="utf-8")
        sys.stdout = _TeeOut(_orig_stdout, _tee_fp)

    try:
        asyncio.run(main_async(_args))
    finally:
        if _tee_fp is not None:
            _tee_fp.close()
            sys.stdout = _orig_stdout
