# -*- coding: utf-8 -*-
"""
PRD「记忆检索与 Prompt 优化」Docker 联调 + Prompt 全量追踪。

- 对话验证：HTTP → http://localhost（Nginx → Docker backend），与线上一致。
- Prompt 追踪：宿主机 ASGI 同进程（与 Docker 镜像同套 backend 代码），捕获 Step1.5/5/5.5/6/MemoryExtract 全文。
- 产出：docs/testing/reports/test_report_MEMPROBE_<id>.md

用法（仓库根目录）：
  PYTHONPATH=. python3 scripts/mem_prd_docker_e2e.py
  PYTHONPATH=. python3 scripts/mem_prd_docker_e2e.py --probe-id 20260530A --buffer-rounds 12
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

def _resolve_proj_root() -> Path:
    """脚本在 scripts/ 或复制到 /app/ 根时均能定位仓库根。"""
    p = Path(__file__).resolve().parent
    if (p / "backend").is_dir():
        return p
    return p.parent


_proj_root = _resolve_proj_root()
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from dotenv import load_dotenv

load_dotenv(_proj_root / ".env", override=True)

import httpx

# scheduler 桩（仅 ASGI 追踪段需要）
import types

_sched_mod = types.ModuleType("backend.tasks.scheduler")
_sched_mod.start_scheduler = lambda *a, **k: None
_sched_mod.shutdown_scheduler = lambda *a, **k: None
sys.modules["backend.tasks.scheduler"] = _sched_mod

# 直连 backend:8000，避免 nginx 偶发 502；与 Docker 内 uvicorn 为同一实例
BASE_URL_HTTP = "http://127.0.0.1:8000"
E2E_USER = "e2emem20260530"
E2E_PASS = "pass12345678"
BUFFER_NEUTRAL = [
    "嗯",
    "好的",
    "哈哈",
    "今天还行",
    "有点困",
    "刚吃完饭",
    "在发呆",
    "随便聊聊",
    "天气一般",
    "还行吧",
    "嗯嗯",
    "知道了",
]


def _docker_mysql_query(sql: str) -> str:
    """通过 lxm_mysql 容器执行只读 SQL（凭据来自 compose/.env）。"""
    import os

    user = os.getenv("MYSQL_USER", "lxm")
    pwd = os.getenv("MYSQL_PASSWORD", "")
    db = os.getenv("MYSQL_DATABASE", "lxm")
    cmd = [
        "docker",
        "exec",
        "lxm_mysql",
        "mysql",
        f"-u{user}",
        f"-p{pwd}",
        db,
        "--default-character-set=utf8mb4",
        "-N",
        "-e",
        sql,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return f"[mysql error] {r.stderr.strip()}"
        return r.stdout.strip()
    except Exception as e:
        return f"[mysql exec failed] {e}"


def _docker_backend_logs_grep(pattern: str, tail: int = 400) -> str:
    cmd = ["docker", "compose", "logs", "backend", f"--tail={tail}"]
    try:
        r = subprocess.run(
            cmd,
            cwd=str(_proj_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if pattern in ln]
        return "\n".join(lines[-80:]) if lines else "(无匹配日志)"
    except Exception as e:
        return f"(logs failed: {e})"


class ChatRound:
    def __init__(
        self,
        phase: str,
        user_text: str,
        sse_ok: bool,
        events: list[dict],
        assistant_text: str,
        http_status: int,
        error: str | None = None,
    ):
        self.phase = phase
        self.user_text = user_text
        self.sse_ok = sse_ok
        self.events = events
        self.assistant_text = assistant_text
        self.http_status = http_status
        self.error = error


async def _http_send_chat(
    client: httpx.AsyncClient,
    token: str,
    content: str,
    phase: str,
) -> ChatRound:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    body = {"content": content, "client_message_id": str(uuid.uuid4())}
    events: list[dict] = []
    reply_parts: list[str] = []
    sse_ok = False
    http_status = 0
    err: str | None = None
    try:
        async with client.stream(
            "POST",
            f"{BASE_URL_HTTP}/api/chat/send",
            json=body,
            headers=headers,
            timeout=httpx.Timeout(180.0, connect=30.0, read=180.0),
        ) as resp:
            http_status = resp.status_code
            if resp.status_code != 200:
                raw = (await resp.aread()).decode("utf-8", errors="replace")
                err = f"HTTP {resp.status_code}: {raw[:800]}"
                return ChatRound(phase, content, False, events, "", http_status, err)
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
                    events.append(ev)
                    et = ev.get("type")
                    if et == "delta":
                        reply_parts.append(ev.get("content") or "")
                    elif et == "done":
                        sse_ok = True
                        msgs = ev.get("messages") or []
                        if msgs:
                            reply_parts = [m.get("content", "") for m in msgs if m.get("content")]
                    elif et == "failed":
                        sse_ok = False
                        err = json.dumps(ev, ensure_ascii=False)
    except Exception as e:
        err = str(e)
    assistant = "".join(reply_parts)
    return ChatRound(phase, content, sse_ok, events, assistant, http_status, err)


async def _register_or_login(client: httpx.AsyncClient) -> tuple[str, int]:
    reg = await client.post(
        f"{BASE_URL_HTTP}/api/auth/register",
        json={
            "username": E2E_USER,
            "password": E2E_PASS,
            "confirm_password": E2E_PASS,
        },
    )
    if reg.status_code == 200:
        b = reg.json()
        if b.get("code") == 0:
            d = b.get("data") or {}
            return d["token"], int(d["user_id"])
        # 10004 等：用户已存在，继续登录

    last_err: Exception | None = None
    for attempt in range(5):
        login = await client.post(
            f"{BASE_URL_HTTP}/api/auth/login",
            json={"username": E2E_USER, "password": E2E_PASS, "remember_me": False},
        )
        if login.status_code in (502, 503, 504):
            last_err = RuntimeError(f"HTTP {login.status_code}")
            await asyncio.sleep(2.0 * (attempt + 1))
            continue
        login.raise_for_status()
        b = login.json()
        if b.get("code") != 0:
            raise RuntimeError(f"登录失败: {b}")
        d = b.get("data") or {}
        return d["token"], int(d["user_id"])
    raise RuntimeError(f"登录重试耗尽: {last_err}")


def _check_nickname(probe_id: str, text: str) -> bool:
    return f"探针昵称{probe_id}" in text or f"昵称{probe_id}" in text


def _check_fruit(probe_id: str, text: str) -> bool:
    return f"山竹探针_{probe_id}" in text or "山竹" in text


def _check_allergy(text: str) -> bool:
    return "菠萝" in text or "过敏" in text


def _check_future(probe_id: str, text: str) -> bool:
    """约定召回：须体现已记住约定（含探针片名或明确承认约过），仅出现「电影」不算通过。"""
    if f"探针电影_{probe_id}" in text:
        return True
    deny = ("还没约", "没约过", "才刚认识", "不记得约", "没有约")
    if any(d in text for d in deny):
        return False
    return "后天" in text and "电影" in text


# ─── ASGI Prompt 追踪（复用 chat_steps_trace 思路）───

import contextvars

STEP_CTX: contextvars.ContextVar[str] = contextvars.ContextVar("step_ctx", default="")


class TraceRecorder:
    def __init__(self) -> None:
        self.llm_calls: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def add_llm(self, **kw) -> None:
        self.llm_calls.append(kw)

    def add_event(self, kind: str, payload: dict) -> None:
        self.events.append({"kind": kind, **payload})


async def _run_prompt_trace_rounds(
    messages: list[tuple[str, str]],
    out_sections: list[str],
) -> None:
    """messages: [(phase, text), ...]"""
    from httpx import ASGITransport

    from backend.main import app
    from backend.services import multi_vector_retrieval_service as mv_svc
    from backend.services import query_rewrite_service as qr_svc
    from backend.services import step5_5_service as s55_svc
    from backend.services import step6_orchestrator as s6_svc
    from backend.services.llm_service import llm_service
    from backend.services.memory_service import MemoryService
    from backend.utils import llm_client as lc_mod

    store: dict[str, Any] = {}

    async def _get(k):
        return store.get(k)

    async def _set(k, v, ex=None, **_kw):
        store[k] = v
        return True

    mock_r = AsyncMock()
    mock_r.get = AsyncMock(side_effect=_get)
    mock_r.set = AsyncMock(side_effect=_set)
    mock_r.delete = AsyncMock(side_effect=lambda k: store.pop(k, None))
    mock_r.decr = AsyncMock(return_value=0)
    mock_r.incr = AsyncMock(return_value=1)
    mock_r.lpush = AsyncMock(return_value=1)
    mock_r.ltrim = AsyncMock(return_value=True)
    mock_r.setex = AsyncMock(side_effect=_set)
    mock_r.setnx = AsyncMock(return_value=True)

    async def _instant_debounce(_uid, coro):
        await coro()

    orig_chat_sync_holder: list[Any] = [None]

    async def tracing_chat_sync(prompt: str, timeout_sec: float | None = None):
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
            rec: TraceRecorder | None = getattr(lc_mod, "_trace_recorder", None)
            if rec is not None:
                rec.add_llm(
                    step=step,
                    prompt=prompt,
                    raw_out=raw,
                    ok=ok,
                    err=err,
                    timeout_sec=timeout_sec,
                    elapsed_sec=time.monotonic() - t0,
                )

    _orig_mvr = mv_svc.execute_multi_vector_retrieval
    _orig_qr = qr_svc.execute_query_rewrite
    _orig_s5 = llm_service.chat_with_step5_parse
    _orig_s55 = s55_svc.execute_step5_5
    _orig_s6 = s6_svc.execute_step6
    _orig_mem = MemoryService._extract_memories_from_llm

    def _wrap_step2(orig_fn):
        async def _inner(**kw):
            r = await orig_fn(**kw)
            rec = getattr(mv_svc, "_trace_recorder", None)
            if rec is not None:
                skipped = getattr(r, "skipped_routes", []) or []
                um = len(r.user_memory_results)
                rec.add_event(
                    "step2_retrieval",
                    {
                        "summary": (
                            f"user_hits={um} is_fallback={r.is_fallback} "
                            f"skipped_routes={skipped}"
                        ),
                        "user_results": r.user_memory_results[:5],
                    },
                )
            return r

        return _inner

    def _wrap_tag(orig, tag: str):
        async def _inner(*a, **kw):
            tok = STEP_CTX.set(tag)
            try:
                return await orig(*a, **kw)
            finally:
                STEP_CTX.reset(tok)

        return _inner

    transport = ASGITransport(app=app)
    timeout = httpx.Timeout(180.0, connect=30.0, read=180.0)

    # 使用 Docker backend HTTP 登录（与 HTTP 联调同一库），避免宿主机 .env 连到另一套 MySQL
    async with httpx.AsyncClient(
        base_url=BASE_URL_HTTP, timeout=timeout, trust_env=False
    ) as http_client:
        try:
            token, _uid = await _register_or_login(http_client)
        except Exception as e:
            out_sections.append(f"### Prompt 追踪登录失败\n\n`{e}`\n")
            return

    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        orig_chat_sync_holder[0] = lc_mod.llm_client.chat_sync
        mv_svc.execute_multi_vector_retrieval = _wrap_step2(_orig_mvr)
        qr_svc.execute_query_rewrite = _wrap_tag(_orig_qr, "Step1.5")
        llm_service.chat_with_step5_parse = _wrap_tag(_orig_s5, "Step5")
        s55_svc.execute_step5_5 = _wrap_tag(_orig_s55, "Step5.5")
        s6_svc.execute_step6 = _wrap_tag(_orig_s6, "Step6")

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
                                with patch("backend.services.llm_service.get_redis", AsyncMock(return_value=mock_r)):
                                    with patch(
                                        "backend.services.chat_queue_service.schedule_debounced",
                                        side_effect=_instant_debounce,
                                    ):
                                        with patch(
                                            "backend.routers.chat.schedule_debounced",
                                            side_effect=_instant_debounce,
                                        ):
                                            for phase, user_text in messages:
                                                tr = TraceRecorder()
                                                lc_mod._trace_recorder = tr
                                                mv_svc._trace_recorder = tr
                                                headers = {
                                                    "Authorization": f"Bearer {token}",
                                                    "Content-Type": "application/json",
                                                    "Idempotency-Key": str(uuid.uuid4()),
                                                }
                                                sse_ok = False
                                                assistant = ""
                                                try:
                                                    async with client.stream(
                                                        "POST",
                                                        "/api/chat/send",
                                                        json={
                                                            "content": user_text,
                                                            "client_message_id": str(uuid.uuid4()),
                                                        },
                                                        headers=headers,
                                                    ) as resp:
                                                        if resp.status_code != 200:
                                                            out_sections.append(
                                                                f"#### [{phase}] HTTP {resp.status_code}\n\n"
                                                            )
                                                            continue
                                                        buf = ""
                                                        async for chunk in resp.aiter_bytes():
                                                            buf += chunk.decode("utf-8", errors="replace")
                                                            while "\n" in buf:
                                                                line, buf = buf.split("\n", 1)
                                                                if not line.strip().startswith("data: "):
                                                                    continue
                                                                try:
                                                                    ev = json.loads(line.strip()[6:])
                                                                except json.JSONDecodeError:
                                                                    continue
                                                                if ev.get("type") == "done":
                                                                    sse_ok = True
                                                                    msgs = ev.get("messages") or []
                                                                    assistant = "\n".join(
                                                                        m.get("content", "") for m in msgs
                                                                    )
                                                except Exception as e:
                                                    out_sections.append(f"#### [{phase}] 异常: {e}\n\n")
                                                    continue

                                                out_sections.append(f"#### Prompt 追踪 · {phase}\n\n")
                                                out_sections.append(f"- 用户输入：{user_text}\n")
                                                out_sections.append(
                                                    f"- SSE：{'成功' if sse_ok else '失败'}\n"
                                                )
                                                out_sections.append(
                                                    f"- AI 回复：\n\n```\n{assistant}\n```\n\n"
                                                )
                                                for ev in tr.events:
                                                    if ev.get("kind") == "step2_retrieval":
                                                        out_sections.append(
                                                            f"**Step2**：{ev.get('summary')}\n\n"
                                                        )
                                                        if ev.get("user_results"):
                                                            out_sections.append(
                                                                "```json\n"
                                                                + json.dumps(
                                                                    ev["user_results"],
                                                                    ensure_ascii=False,
                                                                    indent=2,
                                                                )
                                                                + "\n```\n\n"
                                                            )
                                                by_step: dict[str, list] = defaultdict(list)
                                                for c in tr.llm_calls:
                                                    by_step[c["step"]].append(c)
                                                for step_name in [
                                                    "Step1.5",
                                                    "Step5",
                                                    "Step5.5",
                                                    "Step6",
                                                    "MemoryExtract",
                                                    "其它",
                                                ]:
                                                    for c in by_step.get(step_name) or []:
                                                        st = "成功" if c["ok"] else "失败"
                                                        out_sections.append(
                                                            f"##### {step_name} ({st})\n\n"
                                                        )
                                                        if c.get("err"):
                                                            out_sections.append(f"error: `{c['err'][:300]}`\n\n")
                                                        out_sections.append(
                                                            "<details><summary>Prompt</summary>\n\n```\n"
                                                            + (c.get("prompt") or "")
                                                            + "\n```\n</details>\n\n"
                                                        )
                                                        out_sections.append(
                                                            "<details><summary>LLM 原始输出</summary>\n\n```\n"
                                                            + (c.get("raw_out") or "")
                                                            + "\n```\n</details>\n\n"
                                                        )
                                                await asyncio.sleep(8.0)
        finally:
            lc_mod.llm_client.chat_sync = orig_chat_sync_holder[0]
            mv_svc.execute_multi_vector_retrieval = _orig_mvr
            qr_svc.execute_query_rewrite = _orig_qr
            llm_service.chat_with_step5_parse = _orig_s5
            s55_svc.execute_step5_5 = _orig_s55
            s6_svc.execute_step6 = _orig_s6
            MemoryService._extract_memories_from_llm = _orig_mem


def _md_round(r: ChatRound, checks: dict[str, bool] | None = None) -> str:
    lines = [
        f"### [{r.phase}] 对话轮次\n",
        f"- **用户输入**：{r.user_text}",
        f"- **HTTP**：{r.http_status}",
        f"- **SSE 闭环**：{'成功' if r.sse_ok else '失败'}",
    ]
    if r.error:
        lines.append(f"- **错误**：{r.error}")
    lines.append(f"- **AI 回复**：\n\n```\n{r.assistant_text}\n```\n")
    lines.append("<details><summary>SSE 事件 JSON</summary>\n\n```json\n")
    lines.append(json.dumps(r.events, ensure_ascii=False, indent=2))
    lines.append("\n```\n</details>\n")
    if checks:
        lines.append("**断言**：\n")
        for k, v in checks.items():
            lines.append(f"- {k}: {'通过' if v else '未通过'}")
        lines.append("")
    return "\n".join(lines)


async def main_async(args: argparse.Namespace) -> None:
    probe_id = args.probe_id
    nick = f"探针昵称{probe_id}"
    real = f"探针真名{probe_id}"
    fruit = f"山竹探针_{probe_id}"
    movie = f"探针电影_{probe_id}"

    report_path = _proj_root / "docs" / "testing" / "reports" / f"test_report_MEMPROBE_{probe_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    rounds_http: list[ChatRound] = []
    md_parts: list[str] = [
        "# 记忆检索与 Prompt 优化 · Docker 联调报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 探针 ID：`{probe_id}`",
        f"- 测试账号：`{E2E_USER}`（HTTP 注册/登录）",
        "- 对话路径：`POST http://127.0.0.1:8000/api/chat/send`（Docker backend 直连）",
        "- Prompt 路径：宿主机 ASGI 同代码 + 真实 LLM/DB（与镜像 backend 同源）",
        "",
        "---",
        "",
        "## 一、Docker HTTP 对话测试",
        "",
    ]

    limits = httpx.Limits(max_connections=5)
    timeout = httpx.Timeout(180.0, connect=30.0, read=180.0)

    trace_msgs_prebuilt = [
        ("用例1-写入称呼", f"你可以叫我【{nick}】，我的真名是【{real}】。"),
        ("用例2-写入饮食记忆", f"记住一下，我最爱吃的水果是【{fruit}】，别的水果我基本不吃。"),
        ("用例3-写入过敏bundled", "我对菠萝过敏\n以后推荐吃的要记住这点"),
        (
            "用例4-写入约定",
            f"我们约定一下：后天晚上八点我要去看电影《{movie}》，到时候记得问我看得怎么样。",
        ),
        ("用例1-召回称呼", "你还记得平时怎么叫我吗？"),
        ("用例2-召回水果", "我喜欢吃什么水果？"),
        ("用例3-召回过敏", "我有什么不能吃或要忌口的？"),
        ("用例4-召回约定", "我们之前约过什么事？看电影那事你还记得吗？"),
    ]

    if args.prompt_trace_only:
        md_parts.append("**模式**：仅 Prompt ASGI 追踪\n")
        prompt_sections: list[str] = []
        print("[ASGI] Prompt 追踪（8 轮）…")
        await _run_prompt_trace_rounds(trace_msgs_prebuilt, prompt_sections)
        md_parts.extend(prompt_sections)
        report_path.write_text("\n".join(md_parts), encoding="utf-8")
        print(f"\n报告已写入: {report_path}")
        return

    async with httpx.AsyncClient(limits=limits, timeout=timeout, trust_env=False) as client:
        token, user_id = await _register_or_login(client)
        md_parts.append(f"**user_id** = `{user_id}`\n")

        if args.resume_recalls_only:
            md_parts.append(
                "\n> 续跑模式：跳过写入与缓冲（沿用库内已有对话历史）。\n"
            )
            row_final = _docker_mysql_query(
                f"SELECT user_hobby_name, user_real_name, future_action, future_timestamp "
                f"FROM relationship WHERE user_id={user_id}"
            )
            md_parts.append(f"### 续跑前 relationship\n\n```\n{row_final}\n```\n")
            hist_probe = _docker_mysql_query(
                f"SELECT id, role, LEFT(content,300), created_at FROM conversation_log "
                f"WHERE user_id={user_id} AND (content LIKE '%探针%' OR content LIKE '%山竹探针%') "
                f"ORDER BY id ASC LIMIT 40"
            )
            md_parts.append(
                f"### 库内探针相关对话（HTTP 阶段已落库）\n\n```\n{hist_probe}\n```\n"
            )
            hist_recent = _docker_mysql_query(
                f"SELECT id, role, LEFT(content,120), created_at FROM conversation_log "
                f"WHERE user_id={user_id} ORDER BY id DESC LIMIT 30"
            )
            md_parts.append(f"### 最近 30 条 conversation_log\n\n```\n{hist_recent}\n```\n")
        else:
            await _run_http_write_and_buffer(
                client, token, user_id, probe_id, nick, real, fruit, movie,
                args, md_parts, rounds_http, report_path,
            )

        # ── 召回（写入+缓冲已在 _run_http_write_and_buffer 或续跑跳过）──
        recalls = [
            ("用例1-召回称呼", "你还记得平时怎么叫我吗？", None),
            ("用例2-召回水果", "我喜欢吃什么水果？", None),
            ("用例3-召回过敏", "我有什么不能吃或要忌口的？", None),
            ("用例4-召回约定", "我们之前约过什么事？看电影那事你还记得吗？", None),
        ]
        md_parts.append("\n## 召回轮（recent_chat 已推开探针写入轮）\n\n")
        for phase, q, _fn in recalls:
            print(f"[HTTP] {phase} …")
            r = await _http_send_chat(client, token, q, phase)
            rounds_http.append(r)
            if "称呼" in phase:
                ok = _check_nickname(probe_id, r.assistant_text)
            elif "水果" in phase:
                ok = _check_fruit(probe_id, r.assistant_text)
            elif "过敏" in phase:
                ok = _check_allergy(r.assistant_text)
            else:
                ok = _check_future(probe_id, r.assistant_text)
            checks = {"内容断言": ok}
            md_parts.append(_md_round(r, checks))
            report_path.write_text("\n".join(md_parts), encoding="utf-8")

        row_final = _docker_mysql_query(
            f"SELECT user_hobby_name, user_real_name, future_action, future_timestamp "
            f"FROM relationship WHERE user_id={user_id}"
        )
        md_parts.append(f"\n### 最终 relationship\n\n```\n{row_final}\n```\n")

        # 续跑时补拉本轮已完成的召回 1-2 对话（若存在）
        if args.resume_recalls_only:
            hist = _docker_mysql_query(
                f"SELECT role, LEFT(content,200) FROM conversation_log "
                f"WHERE user_id={user_id} ORDER BY id DESC LIMIT 6"
            )
            md_parts.append(f"### 最近 conversation_log\n\n```\n{hist}\n```\n")

    # ── Prompt 全量追踪（关键 8 轮，ASGI）───
    trace_msgs = trace_msgs_prebuilt
    md_parts.extend(["\n---\n", "## 二、对话/记忆链路 Prompt 全量追踪（ASGI）\n", ""])
    prompt_sections: list[str] = []
    print("[ASGI] Prompt 追踪开始（8 轮）…")
    await _run_prompt_trace_rounds(trace_msgs, prompt_sections)
    md_parts.extend(prompt_sections)

    # 汇总
    md_parts.extend(
        [
            "\n---\n",
            "## 三、汇总\n",
            "",
            "| 阶段 | SSE | 备注 |",
            "|------|-----|------|",
        ]
    )
    for r in rounds_http:
        note = ""
        if "召回" in r.phase:
            if "称呼" in r.phase:
                note = "含昵称" if _check_nickname(probe_id, r.assistant_text) else "未含昵称"
            elif "水果" in r.phase:
                note = "含水果探针" if _check_fruit(probe_id, r.assistant_text) else "未含"
            elif "过敏" in r.phase:
                note = "含过敏" if _check_allergy(r.assistant_text) else "未含"
            elif "约定" in r.phase:
                note = "含约定" if _check_future(probe_id, r.assistant_text) else "未含"
        md_parts.append(f"| {r.phase} | {'OK' if r.sse_ok else 'FAIL'} | {note} |")

    report_path.write_text("\n".join(md_parts), encoding="utf-8")
    print(f"\n报告已写入: {report_path}")


async def _run_http_write_and_buffer(
    client,
    token,
    user_id,
    probe_id,
    nick,
    real,
    fruit,
    movie,
    args,
    md_parts,
    rounds_http,
    report_path,
) -> None:
        writes = [
            (
                "用例1-写入称呼",
                f"你可以叫我【{nick}】，我的真名是【{real}】。",
            ),
            (
                "用例2-写入饮食记忆",
                f"记住一下，我最爱吃的水果是【{fruit}】，别的水果我基本不吃。",
            ),
            (
                "用例3-写入过敏bundled",
                "我对菠萝过敏\n以后推荐吃的要记住这点",
            ),
            (
                "用例4-写入约定",
                f"我们约定一下：后天晚上八点我要去看电影《{movie}》，到时候记得问我看得怎么样。",
            ),
        ]
        for phase, text in writes:
            print(f"[HTTP] {phase} …")
            r = await _http_send_chat(client, token, text, phase)
            rounds_http.append(r)
            md_parts.append(_md_round(r))

        md_parts.append("### Step6 等待（写入后轮询 relationship）\n")
        rel_ok = False
        for i in range(18):
            await asyncio.sleep(5)
            row = _docker_mysql_query(
                f"SELECT user_hobby_name, user_real_name, future_action "
                f"FROM relationship WHERE user_id={user_id}"
            )
            md_parts.append(f"- 轮询 {i+1}: `{row}`\n")
            if nick in (row or "") and fruit not in (row or ""):
                pass
            if nick in (row or ""):
                rel_ok = True
            if movie in (row or "") or "电影" in (row or ""):
                rel_ok = True
            if rel_ok and i >= 5:
                break
        md_parts.append(f"\nStep6 日志片段（Step6 向量）：\n\n```\n{_docker_backend_logs_grep('Step6')}\n```\n")

        mem_list = _docker_mysql_query(
            f"SELECT id, LEFT(content,120), source, created_at FROM memory "
            f"WHERE user_id={user_id} ORDER BY id DESC LIMIT 8"
        )
        md_parts.append(f"### MySQL memory 最近 8 条\n\n```\n{mem_list}\n```\n")

        # ── 缓冲 ──
        md_parts.append(f"\n## 缓冲轮（{args.buffer_rounds} 轮，与探针无关）\n\n")
        for i in range(args.buffer_rounds):
            msg = BUFFER_NEUTRAL[i % len(BUFFER_NEUTRAL)]
            phase = f"缓冲-{i+1}"
            print(f"[HTTP] {phase} …")
            r = await _http_send_chat(client, token, msg, phase)
            rounds_http.append(r)
            if i < 3 or i >= args.buffer_rounds - 2:
                md_parts.append(_md_round(r))
            else:
                md_parts.append(
                    f"- {phase}: SSE={'OK' if r.sse_ok else 'FAIL'} "
                    f"回复={r.assistant_text[:40]}…\n"
                )
            await asyncio.sleep(1.5)
        report_path.write_text("\n".join(md_parts), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--probe-id", default=datetime.now().strftime("%Y%m%d%H%M"))
    p.add_argument("--buffer-rounds", type=int, default=12)
    p.add_argument(
        "--resume-recalls-only",
        action="store_true",
        help="跳过写入/缓冲，仅跑 4 条召回 + Prompt ASGI 追踪（续跑用）",
    )
    p.add_argument(
        "--prompt-trace-only",
        action="store_true",
        help="仅跑 8 轮 Prompt ASGI 追踪（写入4+召回4），不写 HTTP 报告主体",
    )
    return p.parse_args()


if __name__ == "__main__":
    import os

    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    asyncio.run(main_async(parse_args()))
