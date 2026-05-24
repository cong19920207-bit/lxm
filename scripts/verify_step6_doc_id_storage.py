# -*- coding: utf-8 -*-
"""
Step6 字段落库验证：MySQL 标量 vs DashVector 四路向量，并检测 doc_id 非法导致的误报成功。

用法（仓库根目录）：
  export SMOKE_BASE_URL=http://127.0.0.1:8000
  python3 scripts/verify_step6_doc_id_storage.py

依赖：backend  if 容器已 up；.env 中 LLM / Embedding / DashVector 有效。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = os.environ.get("VERIFY_USERNAME", "step6e2ev2")
PASSWORD = os.environ.get("VERIFY_PASSWORD", "pass1234")
CHAT_MSG = os.environ.get(
    "VERIFY_CHAT_MSG",
    "我叫张明，你可以叫我小明。我最喜欢吃火锅，最近工作压力很大经常加班到凌晨。",
)

SCALAR_COLUMNS = [
    "user_real_name",
    "user_hobby_name",
    "user_description",
    "character_purpose",
    "character_attitude",
    "relation_description",
]

_VEC_SUCCESS_RE = re.compile(
    r"Step6 向量写入成功: doc_id=([^,]+), type=([^\s]+)"
)
_VEC_FAIL_RE = re.compile(
    r"Step6 向量写入失败: doc_id=([^,]+), type=([^\s]+)"
)
_VEC_SKIP_RE = re.compile(r"Step6 向量写入跳过: field=([^\s,]+)")
_STEP6_DONE_RE = re.compile(
    r"Step6 完成: user_id=(\d+), round_id=([^,]+)"
)
_STEP6_GIVEUP_RE = re.compile(
    r"Step6 重试后仍失败\(放弃\): user_id=(\d+)"
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


def docker_logs_tail(tail: int = 1500) -> str:
    try:
        out = subprocess.run(
            ["docker", "logs", "lxm_backend", "--tail", str(tail)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception as e:
        return f"(读取日志失败: {e})"


def _mysql_exec_args() -> list[str]:
    """从 backend 容器环境读取 MySQL 连接参数。"""
    try:
        r = subprocess.run(
            ["docker", "exec", "lxm_backend", "printenv", "MYSQL_USER",
             "MYSQL_PASSWORD", "MYSQL_DATABASE"],
            capture_output=True, text=True, timeout=10,
        )
        lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
        user = lines[0] if len(lines) > 0 else "lxm"
        pwd = lines[1] if len(lines) > 1 else "lxm123456"
        db = lines[2] if len(lines) > 2 else "lxm"
    except Exception:
        user, pwd, db = "lxm", "lxm123456", "lxm"
    return ["docker", "exec", "lxm_mysql", "mysql", f"-u{user}", f"-p{pwd}", db]


def mysql_query(sql: str) -> str:
    cmd = _mysql_exec_args() + ["--default-character-set=utf8mb4", "-N", "-e", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return f"SQL 错误: {r.stderr.strip()}"
        return (r.stdout or "").strip() or "(空结果)"
    except Exception as e:
        return f"MySQL 查询失败: {e}"


def read_relationship_scalars(user_id: int) -> dict[str, str | None]:
    cols = ", ".join(SCALAR_COLUMNS)
    raw = mysql_query(
        f"SELECT {cols} FROM relationship WHERE user_id={user_id};"
    )
    if raw.startswith("SQL 错误") or raw.startswith("MySQL") or raw == "(空结果)":
        return {c: None for c in SCALAR_COLUMNS}

    parts = raw.split("\t")
    result: dict[str, str | None] = {}
    for i, col in enumerate(SCALAR_COLUMNS):
        val = parts[i] if i < len(parts) else None
        if val in (None, "NULL", "(空结果)"):
            result[col] = None
        else:
            result[col] = val
    return result


def parse_step6_logs(log_text: str, user_id: int) -> dict:
    vec_success: list[tuple[str, str]] = []
    vec_fail: list[tuple[str, str]] = []
    vec_skip: list[str] = []
    step6_done: list[str] = []
    step6_giveup = False

    for line in log_text.splitlines():
        m = _VEC_SUCCESS_RE.search(line)
        if m:
            vec_success.append((m.group(1), m.group(2)))
            continue
        m = _VEC_FAIL_RE.search(line)
        if m:
            vec_fail.append((m.group(1), m.group(2)))
            continue
        m = _VEC_SKIP_RE.search(line)
        if m:
            vec_skip.append(m.group(1))
            continue
        m = _STEP6_DONE_RE.search(line)
        if m and int(m.group(1)) == user_id:
            step6_done.append(m.group(2))
            continue
        m = _STEP6_GIVEUP_RE.search(line)
        if m and int(m.group(1)) == user_id:
            step6_giveup = True

    return {
        "vec_success": vec_success,
        "vec_fail": vec_fail,
        "vec_skip": vec_skip,
        "step6_done_rounds": step6_done,
        "step6_giveup": step6_giveup,
    }


def run_container_dv_check(user_id: int, doc_ids: list[str]) -> str:
    """容器内 fetch_by_ids + 原始 upsert 探测 DashVector 响应体。"""
    py_check = r"""
import asyncio
import httpx
from backend.config import get_dashvector_api_key, get_dashvector_collection, get_dashvector_endpoint
from backend.services.embedding_service import embedding_service
from backend.utils.dashvector_client import dashvector_client

USER_ID = """ + str(user_id) + r"""
DOC_IDS = """ + json.dumps(doc_ids, ensure_ascii=False) + r"""


async def raw_upsert_probe(doc_id, vector, fields, memory_type):
    endpoint = get_dashvector_endpoint()
    collection = get_dashvector_collection()
    headers = {
        "Content-Type": "application/json",
        "dashvector-auth-token": get_dashvector_api_key(),
    }
    merged_fields = {**fields, "type": memory_type}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{endpoint}/v1/collections/{collection}/docs",
            headers=headers,
            json={"docs": [{"id": doc_id, "vector": vector, "fields": merged_fields}]},
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:500]}
        return {
            "http_status": resp.status_code,
            "body_code": data.get("code"),
            "body_message": str(data.get("message", ""))[:200],
            "body": data,
        }


async def main():
    print("=== [A] fetch_by_ids：对照日志声称成功的 doc_id ===")
    if DOC_IDS:
        found = await dashvector_client.fetch_by_ids(DOC_IDS)
        print(f"待查={len(DOC_IDS)}  命中={len(found)}")
        for did in DOC_IDS:
            hit = found.get(did)
            tag = "存在" if hit else "缺失"
            content = (hit or {}).get("content", "")[:60] if hit else ""
            print(f"  [{tag}] {did}")
            if content:
                print(f"         content={content}")
    else:
        print("  (日志无 Step6 向量写入成功记录)")

    print("\n=== [B] 新 doc_id 格式抽样（hash + 下划线）===")
    from backend.utils.character_knowledge_validate import build_doc_id
    sample_key = "喜好-饮食-偏好"
    new_id = build_doc_id("user", sample_key, USER_ID)
    emb = await embedding_service.get_embedding("火锅")
    if emb:
        ok = await dashvector_client.upsert(
            new_id, emb,
            {"content": f"{sample_key}：火锅", "stable_key": sample_key, "user_id": USER_ID},
            "user",
        )
        fetched = await dashvector_client.fetch_by_ids([new_id])
        print(f"  新格式 doc_id={new_id}")
        print(f"  upsert={ok}  fetch={'存在' if new_id in fetched else '缺失'}")
        if new_id in fetched:
            sk = (fetched[new_id].get("fields") or {}).get("stable_key", "")
            print(f"  stable_key={sk}")

    print(f"\n=== [C] list_by_filter user_id={USER_ID} type=user topk=20 ===")
    rows = await dashvector_client.list_by_filter(
        f"type = 'user' AND user_id = {USER_ID}", top_k=20
    )
    print(f"  共 {len(rows)} 条")
    for row in rows[:10]:
        print(f"    id={row.get('id')}  content={str(row.get('content', ''))[:50]}")

asyncio.run(main())
"""
    r = subprocess.run(
        ["docker", "exec", "lxm_backend", "python", "-c", py_check],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (r.stdout or "").strip()
    if r.stderr:
        out += f"\n(stderr)\n{r.stderr[:1000]}"
    return out


def print_scalar_report(before: dict, after: dict) -> list[dict]:
    print("\n=== MySQL relationship 标量字段（Step6 应写入 6 列）===")
    changes = []
    for col in SCALAR_COLUMNS:
        b, a = before.get(col), after.get(col)
        changed = b != a
        b_show = (b or "(空)")[:50]
        a_show = (a or "(空)")[:50]
        mark = " [已变更]" if changed else ""
        print(f"  {col}: {b_show} -> {a_show}{mark}")
        if changed and a:
            changes.append({"column": col, "before": b, "after": a})
    return changes

async def main() -> int:
    print("=== Step6 doc_id / 落库验证 ===\n")
    print(f"BASE_URL: {BASE}")
    print(f"用户: {USERNAME}")
    print(f"消息: {CHAT_MSG}\n")

    async with httpx.AsyncClient() as client:
        token, user_id_from_api = await login_or_register(client)
        uid_row = mysql_query(
            f"SELECT id FROM users WHERE username='{USERNAME}' LIMIT 1;"
        )
        try:
            user_id = int(uid_row.split()[0])
        except (ValueError, IndexError):
            user_id = user_id_from_api or 0
        print(f"user_id = {user_id}\n")

        rel_before = read_relationship_scalars(user_id)
        hist_before = mysql_query(
            f"SELECT COUNT(*) FROM relationship_change_history "
            f"WHERE user_id={user_id} AND trigger_source='step6';"
        )

        print("--- 发送一轮对话 ---")
        result = await send_one_round(client, token)
        if result["failed"]:
            print(f"SSE 失败: {json.dumps(result['failed'], ensure_ascii=False)[:500]}")
            return 1
        if not result["done"]:
            print("未收到 done 事件")
            return 1
        print("SSE done 已收到")

    print("\n等待 Step6 后台任务… sleep 30s")
    time.sleep(30)

    rel_after = read_relationship_scalars(user_id)
    hist_after = mysql_query(
        f"SELECT COUNT(*) FROM relationship_change_history "
        f"WHERE user_id={user_id} AND trigger_source='step6';"
    )
    scalar_changes = print_scalar_report(rel_before, rel_after)

    print(f"\n  step6 变更历史: {hist_before} -> {hist_after}")
    recent_hist = mysql_query(
        f"SELECT field_name, LEFT(COALESCE(new_value,''),40), round_id "
        f"FROM relationship_change_history "
        f"WHERE user_id={user_id} AND trigger_source='step6' "
        f"ORDER BY id DESC LIMIT 8;"
    )
    print(f"  最近历史:\n{recent_hist}")

    logs = docker_logs_tail()
    parsed = parse_step6_logs(logs, user_id)

    print("\n=== 日志解析：Step6 向量写入 ===")
    print(f"  Step6 完成轮次: {parsed['step6_done_rounds'] or '(无)'}")
    print(f"  Step6 放弃: {parsed['step6_giveup']}")
    print(f"  向量写入成功(日志): {len(parsed['vec_success'])} 条")
    for doc_id, mtype in parsed["vec_success"]:
        print(f"    [日志成功] {doc_id}  type={mtype}")
    print(f"  向量写入失败(日志): {len(parsed['vec_fail'])} 条")
    for doc_id, mtype in parsed["vec_fail"]:
        print(f"    [日志失败] {doc_id}  type={mtype}")
    if parsed["vec_skip"]:
        print(f"  向量整路跳过: {parsed['vec_skip']}")

    doc_ids = [d for d, _ in parsed["vec_success"]]
    print("\n--- 容器内 DashVector 对照 ---")
    dv_out = run_container_dv_check(user_id, doc_ids)
    print(dv_out)

    # 汇总结论
    print("\n" + "=" * 60)
    print("=== 验证结论 ===")
    print("=" * 60)

    mysql_ok = len(scalar_changes) > 0 or int(hist_after or "0") > int(hist_before or "0")
    print(f"1. MySQL 标量/历史: {'有 Step6 写入迹象' if mysql_ok else '未见明显变更（可能 LLM 输出均为「无」）'}")

    log_claims = len(parsed["vec_success"])
    user_vec_logs = [
        (d, t) for d, t in parsed["vec_success"]
        if d.startswith("user_") and d.endswith(f"_{user_id}")
    ]
    print(f"2. 日志声称向量成功: {log_claims} 条（本用户 user 路 {len(user_vec_logs)} 条）")

    section_a = dv_out.split("[B]")[0] if "[B]" in dv_out else dv_out
    missing_in_fetch = "[缺失]" in section_a and "待查=" in section_a
    all_hit = "待查=" in section_a and "命中=" in section_a and not missing_in_fetch
    new_format_ok = "fetch=存在" in dv_out or ("命中=" in section_a and "[存在]" in section_a)

    if log_claims > 0 and missing_in_fetch:
        print("3. DashVector: 日志成功但 fetch 缺失 —— 仍有问题")
    elif log_claims == 0:
        print("3. DashVector: 本轮无向量成功日志（LLM 可能未产出三层 key）")
    elif new_format_ok or all_hit:
        print("3. DashVector: 新 doc_id 写入后可 fetch 命中 ✅")
    else:
        print("3. DashVector: 见上方 [A]/[B] 详细输出")

    if user_vec_logs:
        print("4. 新 doc_id 样例:", user_vec_logs[0][0])
    else:
        print("4. doc_id: 见 [B] 段抽样")

    print("\n字段落库对照（设计预期）:")
    print("  向量(DashVector): CharacterPublicSettings/Private/Knowledges/UserSettings → 4 路")
    print("  标量(MySQL relationship): UserRealName/HobbyName/Description/Purpose/Attitude/RelationDescription")
    print("  不落库: InnerMonologue")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
