# -*- coding: utf-8 -*-
"""STEP-030: observer 账号页直访守卫与六类账号 API 专项。"""

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.models.admin_user import AdminUser
from tests.test_admin_auth import (
    _create_admin,
    _get_admin_state,
    _get_token,
    async_session_test,
    client,
    override_get_db,
    setup_db,
)


ROOT = Path(__file__).resolve().parents[1]


def test_accounts_page_redirects_observer_before_render_or_data_request():
    page = (ROOT / "admin/pages/accounts.html").read_text(encoding="utf-8")
    common = (ROOT / "admin/static/js/admin-api.js").read_text(encoding="utf-8")
    boot = re.search(
        r"document\.addEventListener\('DOMContentLoaded',\s*function\s*\(\)\s*\{(?P<body>.*?)\n\}\)",
        page,
        re.DOTALL,
    )
    assert boot
    body = boot.group("body")

    role_guard = "if (getAdminRole() !== 'super_admin')"
    redirect = "window.location.href = '/admin/pages/error.html?type=403'"
    assert body.index(role_guard) < body.index(redirect) < body.index("renderHeader(")
    assert body.index(redirect) < body.index("renderSidebar(") < body.index("loadAccountList()")
    assert "adminRequest('GET', '/api/admin/accounts'" not in body[:body.index("loadAccountList()")]

    assert re.search(
        r"MENU_CONFIG\.observer\s*=\s*MENU_CONFIG\.super_admin\.filter\([^;]+item\.key\s*!==\s*'accounts'",
        common,
        re.DOTALL,
    )


@pytest.mark.asyncio
async def test_observer_all_six_account_apis_are_403_without_data_or_mutation(client):
    target_id = await _create_admin(
        username="step030-target",
        password="Target@Step0301",
        role="ops_admin",
    )
    await _create_admin(
        username="step030-observer",
        password="Observer@Step030",
        role="observer",
    )
    token = await _get_token(
        client,
        username="step030-observer",
        password="Observer@Step030",
    )
    headers = {"Authorization": f"Bearer {token}"}
    before = await _get_admin_state("step030-target")
    before_state = (before.role, before.remark, before.token_version, before.is_locked)

    responses = [
        await client.get("/api/admin/accounts", headers=headers),
        await client.post(
            "/api/admin/accounts",
            json={
                "username": "step030-forbidden",
                "password": "Forbidden@Step030",
                "role": "observer",
            },
            headers=headers,
        ),
        await client.put(
            f"/api/admin/accounts/{target_id}",
            json={"role": "observer", "remark": "forbidden"},
            headers=headers,
        ),
        await client.post(
            f"/api/admin/accounts/{target_id}/reset-password",
            headers=headers,
        ),
        await client.post(
            f"/api/admin/accounts/{target_id}/unlock",
            headers=headers,
        ),
        await client.delete(f"/api/admin/accounts/{target_id}", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403] * 6
    assert all("data" not in response.json() for response in responses)
    after = await _get_admin_state("step030-target")
    assert (after.role, after.remark, after.token_version, after.is_locked) == before_state
    async with async_session_test() as session:
        forbidden = await session.execute(
            select(AdminUser).where(AdminUser.username == "step030-forbidden")
        )
        assert forbidden.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_super_admin_account_management_lifecycle_remains_available(client):
    await _create_admin()
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    listed = await client.get("/api/admin/accounts", headers=headers)
    assert listed.status_code == 200 and listed.json()["code"] == 0
    created = await client.post(
        "/api/admin/accounts",
        json={
            "username": "step030-managed",
            "password": "Managed@Step0301",
            "role": "observer",
            "remark": "created",
        },
        headers=headers,
    )
    assert created.json()["code"] == 0
    account_id = created.json()["data"]["id"]

    edited = await client.put(
        f"/api/admin/accounts/{account_id}",
        json={"role": "ops_admin", "remark": "edited"},
        headers=headers,
    )
    assert edited.json()["data"]["role"] == "ops_admin"
    reset = await client.post(
        f"/api/admin/accounts/{account_id}/reset-password",
        headers=headers,
    )
    assert reset.json()["code"] == 0
    assert reset.json()["data"]["new_password"]

    async with async_session_test() as session:
        target = await session.get(AdminUser, account_id)
        target.is_locked = True
        target.login_fail_count = 5
        await session.commit()
    unlocked = await client.post(
        f"/api/admin/accounts/{account_id}/unlock",
        headers=headers,
    )
    assert unlocked.json()["code"] == 0
    deleted = await client.delete(
        f"/api/admin/accounts/{account_id}",
        headers=headers,
    )
    assert deleted.json()["code"] == 0
