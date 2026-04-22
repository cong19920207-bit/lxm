#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证测试脚本的 LLM 调用路径是否正常。
与 verify_volc_llm.py 的区别：使用 backend.utils.llm_client（与 test_chat_e2e 相同）。

从项目根目录执行: python3 scripts/verify_test_llm_path.py
"""

import asyncio
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
os.chdir(_root)

from dotenv import load_dotenv

load_dotenv(_root / ".env", override=True)


async def main():
    print("=" * 50)
    print("验证 test_chat_e2e 使用的 LLM 调用路径")
    print("=" * 50)

    # 与 config 对比：打印实际读取到的值（不打印完整 key）
    from backend.config import get_volc_api_key, get_volc_endpoint, get_volc_model

    key = get_volc_api_key()
    endpoint = get_volc_endpoint()
    model = get_volc_model()
    print(f"\nVOLC_ACCESS_KEY: {'已配置' if key else '空'}")
    print(f"VOLC_ENDPOINT: {endpoint}")
    print(f"VOLC_MODEL: {model}")

    print("\n调用 llm_client.chat_sync（与 test_chat_e2e 完全相同）...")
    try:
        from backend.utils.llm_client import llm_client

        raw = await llm_client.chat_sync("回复一个字：好")
        print(f"  ✓ 成功，回复: {raw[:80]}...")
    except Exception as e:
        print(f"  ✗ 失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 50)
    print("LLM 调用路径正常，可排除 backend 层问题。")
    print("若 test_chat_e2e 仍失败，可能是 Cursor 运行环境的网络限制。")
    print("建议：在本地终端直接执行 python3 scripts/test_chat_e2e.py")


if __name__ == "__main__":
    asyncio.run(main())
