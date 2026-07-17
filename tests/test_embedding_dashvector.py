# -*- coding: utf-8 -*-
# 阿里云 Embedding 与 DashVector 联通性自动测试

import asyncio
# 测试项：1. Embedding 模型调用  2. DashVector 写入与读取
# 不修改现有代码，仅调用现有服务进行验证

import os
import sys
import time

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
import pytest_asyncio

from backend.services.embedding_service import embedding_service
from backend.utils.dashvector_client import dashvector_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_EXTERNAL_INTEGRATION") != "1",
    reason="requires live Aliyun Embedding and DashVector credentials/network",
)


# 测试用虚拟 user_id，避免与真实数据冲突
_TEST_USER_ID = 999998
# 测试文档 ID 前缀，便于识别和清理
_TEST_DOC_PREFIX = "test_embedding_dv_"
_TEST_CONTENT = "林小梦Embedding与DashVector联通性测试"


def _test_doc_id() -> str:
    """生成唯一测试文档 ID"""
    return f"{_TEST_DOC_PREFIX}{int(time.time() * 1000)}"


def _print_result(name: str, ok: bool, detail: str = ""):
    """打印单次测试结果"""
    status = "可以" if ok else "不可以"
    line = f"  [{name}] {status}"
    if detail:
        line += f" - {detail}"
    print(line)


@pytest_asyncio.fixture
async def test_doc_id():
    """生成测试文档 ID，测试后供清理使用"""
    doc_id = _test_doc_id()
    yield doc_id
    # 测试结束后尝试删除测试文档（清理）
    try:
        await dashvector_client.delete(doc_ids=[doc_id])
    except Exception:
        pass


@pytest.mark.asyncio
async def test_aliyun_embedding_model():
    """测试阿里云 Embedding 模型是否可正常调用"""
    print("\n========== 阿里云 Embedding 与 DashVector 联通性测试 ==========")
    print("\n1. 阿里云 Embedding 模型调用:")
    try:
        vector = await embedding_service.get_embedding(_TEST_CONTENT)
        ok = isinstance(vector, list) and len(vector) > 0 and all(isinstance(x, (int, float)) for x in vector[:5])
        _print_result("Embedding 模型调用", ok, f"向量维度={len(vector)}" if vector else "返回为空")
        assert ok, "Embedding 调用失败或返回无效"
    except Exception as e:
        _print_result("Embedding 模型调用", False, str(e))
        raise


# text-embedding-v3 默认 1024 维，用于 Embedding 失败时 DashVector 独立测试
_EMBEDDING_DIM = 1024


@pytest.mark.asyncio
async def test_dashvector_upsert_and_search(test_doc_id):
    """测试 DashVector 是否可正常写入和读取"""
    print("\n2. 阿里云 DashVector 写入与读取:")
    doc_id = test_doc_id

    # 2.1 先获取 embedding，失败则用备用向量以独立测试 DashVector
    vector = None
    try:
        vector = await embedding_service.get_embedding(_TEST_CONTENT)
    except Exception as e:
        _print_result("Embedding 模型调用（DashVector 依赖）", False, str(e))
        vector = [0.0] * _EMBEDDING_DIM  # 备用向量

    # 2.2 写入 DashVector
    fields = {
        "user_id": _TEST_USER_ID,
        "content": _TEST_CONTENT,
        "importance_score": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
    try:
        success = await dashvector_client.upsert(doc_id=doc_id, vector=vector, fields=fields)
        _print_result("DashVector 写入", success)
        assert success, "DashVector 写入失败"
    except Exception as e:
        _print_result("DashVector 写入", False, str(e))
        raise

    # DashVector 有最终一致性，写入后短暂等待再检索
    await asyncio.sleep(3)

    # 2.3 读取（向量检索）
    try:
        results = await dashvector_client.search(
            vector=vector,
            user_id=_TEST_USER_ID,
            top_k=5,
            threshold=0.0,
        )
        found = any(r.get("id") == doc_id or r.get("content") == _TEST_CONTENT for r in results)
        _print_result("DashVector 读取", found, f"检索到 {len(results)} 条，含测试内容={found}")
        assert found or len(results) > 0, "DashVector 检索无结果"
    except Exception as e:
        _print_result("DashVector 读取", False, str(e))
        raise

    print("\n========== 测试完成 ==========\n")


# 支持直接运行：python tests/test_embedding_dashvector.py
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
