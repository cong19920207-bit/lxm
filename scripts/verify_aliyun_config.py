#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证阿里云配置（Embedding + DashVector）是否可以跑通。
从项目根目录执行: python scripts/verify_aliyun_config.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 确保项目根目录在路径中
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
os.chdir(_root)

# 加载 .env
from dotenv import load_dotenv

load_dotenv(_root / ".env")


async def test_embedding() -> tuple[bool, str]:
    """测试阿里云 Embedding API（text-embedding-v4 使用 compatible-mode）"""
    api_key = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
    model = os.getenv("ALIYUN_EMBEDDING_MODEL", "text-embedding-v4")
    endpoint = (
        os.getenv("ALIYUN_EMBEDDING_ENDPOINT")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    )

    if not api_key:
        return False, "ALIYUN_ACCESS_KEY_ID 未配置"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            # text-embedding-v4 使用 OpenAI 兼容格式
            payload = {
                "model": model,
                "input": "验证配置的测试文本",
                "dimensions": 1024,
                "encoding_format": "float",
            }
            response = await client.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # 兼容两种响应格式：OpenAI 格式(data) 和 DashScope 原生格式(output.embeddings)
        embedding = None
        if "data" in data and data["data"]:
            embedding = data["data"][0].get("embedding", [])
        elif "output" in data and "embeddings" in data["output"]:
            embs = data["output"]["embeddings"]
            embedding = embs[0].get("embedding", []) if embs else None

        if embedding and len(embedding) > 0:
            return True, f"Embedding 成功，向量维度: {len(embedding)}"
        return False, f"Embedding 返回异常: {data}"

    except httpx.HTTPStatusError as e:
        try:
            err_body = e.response.json()
            msg = err_body.get("message", str(e))
        except Exception:
            msg = str(e)
        return False, f"Embedding API 请求失败: {msg}"
    except Exception as e:
        return False, f"Embedding 异常: {e}"


async def test_dashvector() -> tuple[bool, str]:
    """测试 DashVector 连接（需先获取 embedding 向量）"""
    api_key = os.getenv("DASHVECTOR_API_KEY", "")
    endpoint = os.getenv("DASHVECTOR_ENDPOINT", "")
    collection = os.getenv("DASHVECTOR_COLLECTION_NAME", "lxm_memory")

    if not api_key:
        return False, "DASHVECTOR_API_KEY 未配置"
    if not endpoint:
        return False, "DASHVECTOR_ENDPOINT 未配置"

    # 确保 endpoint 带 https
    if not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"

    # 先获取一个测试向量
    emb_ok, emb_msg = await test_embedding()
    if not emb_ok:
        return False, f"无法获取测试向量（Embedding 失败）: {emb_msg}"

    # 从 embedding 测试中获取向量（避免重复调用，这里再调一次简化逻辑）
    try:
        import httpx

        api_key_aliyun = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
        model = os.getenv("ALIYUN_EMBEDDING_MODEL", "text-embedding-v4")
        emb_endpoint = (
            os.getenv("ALIYUN_EMBEDDING_ENDPOINT")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                emb_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key_aliyun}",
                },
                json={
                    "model": model,
                    "input": "test",
                    "dimensions": 1024,
                    "encoding_format": "float",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if "data" in data and data["data"]:
            vector = data["data"][0].get("embedding", [])
        elif "output" in data and data["output"].get("embeddings"):
            vector = data["output"]["embeddings"][0].get("embedding", [])
        else:
            return False, "无法解析 Embedding 响应"

        # 调用 DashVector query
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{endpoint}/v1/collections/{collection}/query",
                headers={
                    "Content-Type": "application/json",
                    "dashvector-auth-token": api_key,
                },
                json={
                    "vector": vector,
                    "topk": 1,
                    "filter": "user_id = 0",  # 仅测试连通性，可能无数据
                    "include_vector": False,
                },
            )
            r.raise_for_status()
        return True, "DashVector 连接成功"

    except httpx.HTTPStatusError as e:
        try:
            err = e.response.json()
            msg = err.get("message", err.get("Message", str(e)))
        except Exception:
            msg = str(e)
        return False, f"DashVector 请求失败: {msg}"
    except Exception as e:
        return False, f"DashVector 异常: {e}"


async def main():
    print("=" * 50)
    print("阿里云配置验证")
    print("=" * 50)

    print("\n[1/2] 测试 Embedding API...")
    emb_ok, emb_msg = await test_embedding()
    print("  ✓ 通过" if emb_ok else f"  ✗ 失败: {emb_msg}")

    print("\n[2/2] 测试 DashVector...")
    dv_ok, dv_msg = await test_dashvector()
    print("  ✓ 通过" if dv_ok else f"  ✗ 失败: {dv_msg}")

    print("\n" + "=" * 50)
    if emb_ok and dv_ok:
        print("全部验证通过，配置正常。")
    else:
        print("存在失败项，请检查 .env 配置。")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
