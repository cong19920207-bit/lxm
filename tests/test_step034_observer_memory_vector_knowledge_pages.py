# -*- coding: utf-8 -*-
"""STEP-034: 记忆、向量与知识页面及 DashVector 凭据状态。"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_admin_auth import (
    _create_admin, _get_token, client, override_get_db, setup_db,
)


PAGES = Path(__file__).resolve().parents[1] / "admin/pages"


def _read(name):
    return (PAGES / name).read_text(encoding="utf-8")


def test_three_pages_allow_observer_and_preserve_read_controls():
    for name in ["memory-rules.html", "vector-token-config.html", "knowledge.html"]:
        page = _read(name)
        assert "'observer'" in page.split("ALLOWED_ROLES =", 1)[1].split(";", 1)[0]
        assert "adminRequest('GET'" in page
    assert 'id="btn-global-search"' in _read("memory-rules.html")
    assert 'id="btn-ck-search"' in _read("knowledge.html")
    assert 'id="btn-ck-prev" data-write-action' not in _read("knowledge.html")


def test_memory_page_marks_prompt_vector_credentials_and_dynamic_deletes():
    page = _read("memory-rules.html")
    for cid in ["s6-system_instruction", "s6-output_format_rules", "s6-kv_field_rules", "s6-merge_rules", "s6-few_shot_example", "btn-save-step6-prompt", "vector-endpoint", "vector-collection", "vector-top-k", "btn-toggle-api-key", "vector-api-key-plain", "btn-vector-test", "btn-vector-save", "btn-global-batch-delete", "global-check-all"]:
        assert f'id="{cid}" data-write-action' in page, cid
    assert "data-write-action class=\"global-row-check\"" in page
    assert "data-write-action onclick=\"globalDeleteOne(this)\"" in page
    assert "data-write-action class=\"form-control step6-prompt-textarea\"" in page


def test_vector_and_knowledge_static_dynamic_writes_are_marked():
    vector = _read("vector-token-config.html")
    for cid in ["vt-top-k", "vt-threshold", "btn-save-vector", "vt-max-total", "btn-save-token"]:
        assert f'id="{cid}" data-write-action' in vector
    assert "data-write-action class=\"form-control\" id=\"vt-tok-" in vector

    knowledge = _read("knowledge.html")
    for cid in ["btn-ck-add", "ck-modal-type", "ck-modal-key", "ck-modal-value", "ck-modal-save"]:
        assert f'id="{cid}" data-write-action' in knowledge
    assert 'data-write-action data-action="edit"' in knowledge
    assert 'data-write-action data-action="del"' in knowledge


@pytest.mark.asyncio
async def test_observer_dashvector_read_has_status_but_no_credential_fragment(client):
    await _create_admin(username="step034-observer", password="Observer@Step034", role="observer")
    token = await _get_token(client, username="step034-observer", password="Observer@Step034")
    with patch(
        "backend.routers.admin.memory_mgmt.admin_config_service.get_active_config",
        new=AsyncMock(return_value={
            "endpoint": "https://dashvector.example",
            "collection_name": "memory",
            "top_k": 5,
            "api_key": "dash-secret-12345678",
        }),
    ):
        response = await client.get(
            "/api/admin/vector-db-config",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["credential_configured"] is True
    assert "api_key" not in data and "api_key_masked" not in data
    assert "dash" not in str(data).lower().replace("dashvector", "")

