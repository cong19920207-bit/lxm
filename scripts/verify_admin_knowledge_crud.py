# -*- coding: utf-8 -*-
"""
管理后台角色知识库 CRUD 真实联调（Docker 本地）。

用法：
  python3 scripts/verify_admin_knowledge_crud.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse

import httpx

BASE = "http://127.0.0.1:8000"
ADMIN_USER = "superadmin"
ADMIN_PASS = "Admin@123456"

SAMPLE_KEY = "外貌-体态-细节"
SAMPLE_TYPE = "character_global"
CREATE_VALUE = "联调测试：长发，说话温柔，喜欢浅色穿搭"
UPDATE_VALUE = "联调测试：已更新描述，气质更活泼"


def ok(name: str, cond: bool, detail: str = "") -> bool:
    mark = "✅" if cond else "❌"
    line = f"{mark} {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return cond


def admin_login(client: httpx.Client) -> str:
    r = client.post(
        f"{BASE}/api/admin/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"管理员登录失败: {body}")
    return body["data"]["token"]


def dv_fetch(doc_id: str) -> dict:
    py = f"""
import asyncio, json
from backend.utils.dashvector_client import dashvector_client
async def main():
    found = await dashvector_client.fetch_by_ids([{json.dumps(doc_id)}])
    print(json.dumps(found, ensure_ascii=False))
asyncio.run(main())
"""
    r = subprocess.run(
        ["docker", "exec", "lxm_backend", "python", "-c", py],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return {}
    try:
        return json.loads((r.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return {}


def main() -> int:
    print("=== 管理后台角色知识库 CRUD 联调 ===\n")
    print(f"BASE: {BASE}")
    print(f"管理员: {ADMIN_USER}\n")

    passed = True
    doc_id: str | None = None

    with httpx.Client(timeout=60.0) as client:
        token = admin_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        passed &= ok("登录", True, "token 已获取")

        # 查：列表（改前）
        r = client.get(
            f"{BASE}/api/admin/character-knowledge",
            params={"type": SAMPLE_TYPE, "keyword": SAMPLE_KEY},
            headers=headers,
        )
        before = r.json()
        passed &= ok("GET 列表", before.get("code") == 0, f"code={before.get('code')}")

        # 增
        r = client.post(
            f"{BASE}/api/admin/character-knowledge",
            headers=headers,
            json={
                "type": SAMPLE_TYPE,
                "key": SAMPLE_KEY,
                "value": CREATE_VALUE,
            },
        )
        create_body = r.json()
        if create_body.get("code") == 0:
            doc_id = create_body["data"]["doc_id"]
            passed &= ok(
                "POST 新增",
                True,
                f"doc_id={doc_id}, key={create_body['data'].get('key')}",
            )
            passed &= ok(
                "doc_id 新格式",
                doc_id.startswith(f"{SAMPLE_TYPE}_") and doc_id.endswith("_0"),
                doc_id,
            )
        else:
            passed &= ok("POST 新增", False, str(create_body))
            print("\n后续改/删跳过（新增失败）")
            return 1 if not passed else 0

        # 查：DashVector 真实存在
        found = dv_fetch(doc_id)
        passed &= ok(
            "DashVector fetch",
            doc_id in found,
            (found.get(doc_id) or {}).get("content", "")[:60],
        )
        fields = (found.get(doc_id) or {}).get("fields") or {}
        passed &= ok(
            "stable_key 字段",
            fields.get("stable_key") == SAMPLE_KEY,
            fields.get("stable_key", ""),
        )

        # 查：列表命中
        r = client.get(
            f"{BASE}/api/admin/character-knowledge",
            params={"type": SAMPLE_TYPE, "keyword": SAMPLE_KEY},
            headers=headers,
        )
        lst = r.json()
        ids = [x["doc_id"] for x in (lst.get("data") or {}).get("list") or []]
        passed &= ok("GET 列表含新条目", doc_id in ids, f"total={lst.get('data', {}).get('total')}")

        # 改
        enc_id = urllib.parse.quote(doc_id, safe="")
        r = client.put(
            f"{BASE}/api/admin/character-knowledge/{enc_id}",
            headers=headers,
            json={"value": UPDATE_VALUE},
        )
        upd = r.json()
        passed &= ok("PUT 更新", upd.get("code") == 0, upd.get("message", ""))
        if upd.get("code") == 0:
            passed &= ok(
                "更新后 content",
                UPDATE_VALUE in (upd.get("data") or {}).get("content", ""),
                (upd.get("data") or {}).get("content", "")[:50],
            )

        found2 = dv_fetch(doc_id)
        passed &= ok(
            "DashVector 更新后",
            UPDATE_VALUE in ((found2.get(doc_id) or {}).get("content") or ""),
            ((found2.get(doc_id) or {}).get("content") or "")[:50],
        )

        # 删
        r = client.delete(
            f"{BASE}/api/admin/character-knowledge/{enc_id}",
            headers=headers,
        )
        del_body = r.json()
        passed &= ok("DELETE 删除", del_body.get("code") == 0, del_body.get("message", ""))

        found3 = dv_fetch(doc_id)
        passed &= ok("DashVector 删除后", doc_id not in found3, "应不存在")

        r = client.get(
            f"{BASE}/api/admin/character-knowledge",
            params={"type": SAMPLE_TYPE, "keyword": SAMPLE_KEY},
            headers=headers,
        )
        ids_after = [x["doc_id"] for x in (r.json().get("data") or {}).get("list") or []]
        passed &= ok("GET 列表已移除", doc_id not in ids_after, f"remaining={len(ids_after)}")

        # 边界：两层 key 拒绝
        r = client.post(
            f"{BASE}/api/admin/character-knowledge",
            headers=headers,
            json={
                "type": SAMPLE_TYPE,
                "key": "外貌-体态",
                "value": "应被拒绝",
            },
        )
        bad = r.json()
        passed &= ok(
            "POST 两层 key 拒绝",
            bad.get("code") != 0,
            f"code={bad.get('code')} msg={bad.get('message')}",
        )

    print("\n" + "=" * 50)
    if passed:
        print("=== 结论：CRUD 全流程通过 ✅ ===")
        return 0
    print("=== 结论：存在失败项 ❌ ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
