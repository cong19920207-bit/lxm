# -*- coding: utf-8 -*-
"""STEP-032: 系统、第三方、AI 测试与看板四页 observer 只读契约。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "admin/pages"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_observer_can_enter_four_pages_and_keep_get_refreshes():
    system = _read("system-monitor.html")
    third_party = _read("third-party.html")
    test_tool = _read("test-tool.html")
    dashboard = _read("dashboard.html")

    assert "'observer'" in system.split("var ALLOWED_ROLES", 1)[1].split(";", 1)[0]
    assert "'observer'" in third_party.split("var ALLOWED_ROLES", 1)[1].split(";", 1)[0]
    assert "'observer'" in test_tool.split("var ALLOWED_ROLES", 1)[1].split(";", 1)[0]
    assert "renderSidebar('dashboard')" in dashboard

    assert "adminRequest('GET', '/api/admin/system/status')" in system
    assert "adminRequest('GET', '/api/admin/third-party/status')" in third_party
    assert "adminRequest('GET', '/api/admin/stats/dashboard')" in dashboard
    assert "setInterval" in system


def test_third_party_dynamic_config_and_test_controls_are_marked():
    page = _read("third-party.html")
    assert page.count("tp-config-btn\" data-write-action") == 2
    for control_id in [
        "modal-test-redis-btn",
        "modal-endpoint",
        "modal-apikey",
        "modal-test-btn",
        "modal-save-btn",
    ]:
        assert f'id="{control_id}" data-write-action' in page

    assert "observerView" in page
    assert "credential_configured" in page
    assert "凭据状态" in page
    assert "s.credential_configured ? '已配置' : '未配置'" in page


def test_ai_test_inputs_run_clear_save_and_dynamic_modal_are_marked():
    page = _read("test-tool.html")
    for control_id in [
        "tt-level",
        "tt-emotion",
        "tt-memories",
        "tt-input",
        "tt-run",
        "tt-history-clear",
        "tt-save-case",
        "tt-sc-criteria",
        "tt-sc-ok",
    ]:
        assert f'id="{control_id}" data-write-action' in page
    assert page.count('name="tt-use-draft" data-write-action') == 2

    # 结果/历史和完整 Prompt 展开属于读取交互，不得隐藏。
    assert 'id="tt-history-list"' in page
    assert 'id="tt-prompt-toggle"' in page
    assert 'id="tt-prompt-toggle" data-write-action' not in page


def test_dashboard_has_no_write_request_or_coarse_observer_disable():
    page = _read("dashboard.html")
    assert "adminRequest('POST'" not in page
    assert "adminRequest('PUT'" not in page
    assert "adminRequest('DELETE'" not in page
    assert "data-write-action" not in page
    assert "role === 'observer'" not in page
