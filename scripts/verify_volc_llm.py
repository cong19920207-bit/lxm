#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证火山引擎豆包 LLM 配置是否可以跑通。
从项目根目录执行: python3 scripts/verify_volc_llm.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 确保项目根目录在路径中
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
os.chdir(_root)

from dotenv import load_dotenv

load_dotenv(_root / ".env")


async def test_volc_llm() -> tuple[bool, str]:
    """测试火山引擎豆包 LLM API"""
    api_key = os.getenv("VOLC_ACCESS_KEY", "")
    endpoint = os.getenv("VOLC_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("VOLC_MODEL", "doubao-seed-1-8-251228")

    if not api_key:
        return False, "VOLC_ACCESS_KEY 未配置"

    # endpoint 应为 base URL，不含 /chat/completions；若已包含则不再拼接
    chat_url = (
        endpoint
        if endpoint.rstrip("/").endswith("/chat/completions")
        else f"{endpoint.rstrip('/')}/chat/completions"
    )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                chat_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "回复一个字：好"}],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return True, f"豆包 LLM 调用成功，回复: {content[:50]}..."
        return False, f"响应格式异常: {data}"

    except httpx.HTTPStatusError as e:
        try:
            err_body = e.response.json()
            msg = err_body.get("error", {}).get("message", err_body.get("message", str(e)))
        except Exception:
            msg = e.response.text or str(e)
        return False, f"豆包 API 请求失败: {msg}"
    except Exception as e:
        return False, f"豆包 LLM 异常: {e}"


async def main():
    print("=" * 50)
    print("火山引擎豆包 LLM 配置验证")
    print("=" * 50)

    print("\n测试 LLM 调用...")
    ok, msg = await test_volc_llm()
    print("  ✓ 通过" if ok else f"  ✗ 失败: {msg}")

    print("\n" + "=" * 50)
    if ok:
        print("豆包 LLM 配置正常，Key 可用。")
    else:
        print("验证失败，请检查 .env 中 VOLC_ACCESS_KEY、VOLC_ENDPOINT、VOLC_MODEL。")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
