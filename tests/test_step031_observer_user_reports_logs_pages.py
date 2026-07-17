# -*- coding: utf-8 -*-
"""STEP-031: 用户、报表与日志五页 observer 只读静态契约。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "admin/pages"


def _read(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_observer_can_enter_all_five_pages_and_read_controls_stay_available():
    report = _read("data-report.html")
    system_logs = _read("system-logs.html")
    assert "role !== 'observer'" in report
    assert "'observer'" in system_logs.split("var ALLOWED_ROLES", 1)[1].split(";", 1)[0]

    for page in [
        _read("users.html"),
        _read("user-detail.html"),
        report,
        _read("operation-logs.html"),
        system_logs,
    ]:
        assert "renderSidebar(" in page
        assert "adminRequest('GET'" in page

    assert 'id="btnSearch"' in _read("users.html")
    assert 'onclick="goDetail(' in _read("users.html")
    assert 'id="btn-query"' in report
    assert 'onclick="openOperationLogDetail(' in _read("operation-logs.html")
    assert "window.showLogDetail = function" in system_logs
    assert "onclick=\"' + onEsc + '\"" in system_logs


def test_users_page_marks_only_dynamic_status_write_action():
    page = _read("users.html")
    assert "data-write-action onclick=\"toggleStatus(" in page
    assert "data-write-action onclick=\"goDetail(" not in page
    assert '<button class="btn btn-primary" id="btnSearch">搜索</button>' in page
    assert '<button class="btn btn-default" id="btnReset">重置</button>' in page


def test_user_detail_marks_static_dynamic_row_and_modal_writes():
    page = _read("user-detail.html")
    required_marked_calls = [
        "addUserMemory()",
        "addPrivateSetting()",
        "editKvEntry(this)",
        "deleteKvEntry(this)",
        "saveKvEntry(this)",
        "toggleUserStatus()",
        "resetUserPassword()",
        "generateOpenApiKey(",
    ]
    for call in required_marked_calls:
        window = page[max(0, page.index(call) - 180):page.index(call)]
        assert "data-write-action" in window, call

    assert page.count('id="__kv_key" data-write-action') == 1
    assert page.count('id="__kv_value" data-write-action') == 1
    assert page.count('id="__kv_ok" data-write-action') == 1
    assert 'onclick="searchUserMemories()">搜索</button>' in page
    assert 'onclick="searchPrivateSettings()">搜索</button>' in page
    assert 'onclick="loadEarlierConversations()">加载更早</button>' in page


def test_three_builtin_export_buttons_use_standard_write_marker():
    expectations = {
        "data-report.html": 'id="btn-export" data-write-action',
        "operation-logs.html": 'id="btnExport" data-write-action',
        "system-logs.html": 'data-write-action onclick="exportLogs(',
    }
    for name, marker in expectations.items():
        page = _read(name)
        assert marker in page, name
