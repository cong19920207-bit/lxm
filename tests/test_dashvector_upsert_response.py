# -*- coding: utf-8 -*-
# DashVector upsert 响应体校验单元测试

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils.dashvector_client import DashVectorClient


@pytest.mark.asyncio
async def test_upsert_returns_false_on_invalid_doc_in_message():
    client = DashVectorClient()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "message": (
            "The first failed operation is [op:insert, id:user:姓名:5, "
            "message:Doc id is invalid]"
        ),
    }

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_response)
    mock_http.aclose = AsyncMock()

    with patch.object(client, "_get_client", AsyncMock(return_value=mock_http)):
        ok = await client.upsert(
            doc_id="user_bad_id",
            vector=[0.1] * 8,
            fields={"content": "test"},
            memory_type="user",
        )

    assert ok is False


@pytest.mark.asyncio
async def test_upsert_returns_true_on_success_message():
    client = DashVectorClient()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"code": 0, "message": "Success"}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_get_client", AsyncMock(return_value=mock_http)):
        ok = await client.upsert(
            doc_id="mem_test_123",
            vector=[0.1] * 8,
            fields={"content": "test", "user_id": 1},
            memory_type="user",
        )

    assert ok is True
