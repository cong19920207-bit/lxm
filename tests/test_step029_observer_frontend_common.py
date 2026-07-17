# -*- coding: utf-8 -*-
"""STEP-029: observer 前端公共菜单、只读助手与请求兜底。"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_JS = (ROOT / "admin/static/js/admin-api.js").read_text(encoding="utf-8")
COMMON_CSS = (ROOT / "admin/static/css/admin-common.css").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    match = re.search(rf"function\s+{name}\s*\([^)]*\)\s*\{{", API_JS)
    assert match, f"missing function {name}"
    depth = 1
    cursor = match.end()
    while cursor < len(API_JS) and depth:
        if API_JS[cursor] == "{":
            depth += 1
        elif API_JS[cursor] == "}":
            depth -= 1
        cursor += 1
    assert depth == 0, f"unclosed function {name}"
    return API_JS[match.end():cursor - 1]


def test_observer_menu_excludes_accounts_and_header_uses_display_name():
    assert re.search(
        r"MENU_CONFIG\.observer\s*=\s*MENU_CONFIG\.super_admin\.filter\([^;]+accounts",
        API_JS,
        re.DOTALL,
    )
    assert "CHAT_PROMPT_MENU.observer" in API_JS
    assert "LIFE_FEED_MENU.observer" in API_JS
    header = _function_body("renderHeader")
    assert re.search(r"observer\s*:\s*['\"]观察者['\"]", header)


def test_admin_request_blocks_observer_writes_with_only_two_exact_post_exceptions():
    guard = _function_body("isObserverRequestAllowed")
    assert "GET" in guard and "HEAD" in guard
    assert guard.count("/api/admin/auth/logout") == 1
    assert guard.count("/api/admin/auth/change-password") == 1
    assert re.search(r"method\s*!==\s*['\"]POST['\"]", guard)

    request = _function_body("adminRequest")
    assert "isObserverRequestAllowed" in request
    assert re.search(r"if\s*\(\s*!isObserverRequestAllowed", request)
    assert "return null" in request


def test_readonly_helper_only_targets_standard_write_markers_by_control_type():
    helper = _function_body("applyObserverReadOnly")
    assert "[data-write-action]" in helper
    assert "observer-write-hidden" in helper
    assert ".readOnly = true" in helper
    assert ".disabled = true" in helper
    assert "['checkbox', 'radio', 'file', 'range']" in helper
    assert "var controlSelector = 'button, a, input, textarea, select, [role=\"button\"], [role=\"switch\"]'" in helper
    assert "marker.querySelectorAll(controlSelector)" in helper
    assert "querySelectorAll('button')" not in helper
    assert "querySelectorAll('input')" not in helper


def test_dynamic_insertions_reapply_readonly_helper_for_observer_only():
    initializer = _function_body("initObserverReadOnly")
    assert "if (!isObserver()) return" in initializer
    assert "new MutationObserver" in initializer
    assert "addedNodes" in initializer
    assert "applyObserverReadOnly" in initializer
    assert re.search(r"observe\([^;]+childList\s*:\s*true[^;]+subtree\s*:\s*true", initializer, re.DOTALL)


def test_common_css_has_targeted_observer_states_not_global_form_disabling():
    assert ".observer-write-hidden" in COMMON_CSS
    assert ".observer-control-readonly" in COMMON_CSS
    assert ".observer-control-disabled" in COMMON_CSS
    assert "body.observer" not in COMMON_CSS
