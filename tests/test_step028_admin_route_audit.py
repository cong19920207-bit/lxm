# -*- coding: utf-8 -*-
"""STEP-028：全量 Admin 路由鉴权、写总闸与 GET 副作用静态门禁。"""

import ast
import inspect
import textwrap

from backend.main import app
from backend.utils.admin_auth import deny_observer_export, get_current_admin


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXPORT_PATHS = {
    "/api/admin/operation-logs/export",
    "/api/admin/stats/report/export",
    "/api/admin/system/logs/export",
}
ANONYMOUS_ADMIN_ROUTES = {("POST", "/api/admin/auth/login")}
FORBIDDEN_GET_CALLS = {
    "publish_config",
    "save_draft",
    "discard_draft",
    "rollback_config",
    "create_entry",
    "update_entry",
    "delete_entry",
    "upsert_api_key",
    "_do_test_connection",
    "add_task",
    "generate",
    "retry",
    "reset",
}
FORBIDDEN_DB_METHODS = {"add", "add_all", "delete", "commit", "flush", "merge"}
DIRECT_CACHE_WRITE_ALLOWLIST = {
    ("GET", "/api/admin/system/status"),
    ("GET", "/api/admin/third-party/status"),
}


def _admin_routes():
    routes = []
    for root_route in app.routes:
        original_router = getattr(root_route, "original_router", None)
        if original_router is None:
            continue
        prefix = root_route.include_context.prefix
        for route in original_router.routes:
            path = f"{prefix}{route.path}"
            if path.startswith("/api/admin/"):
                routes.append((path, route))
    return routes


def _dependency_calls(dependant) -> set:
    calls = {dependant.call}
    for child in dependant.dependencies:
        calls.update(_dependency_calls(child))
    return calls


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_all_admin_routes_except_login_have_complete_admin_authentication():
    routes = _admin_routes()
    assert len(routes) == 159

    seen = set()
    for path, route in routes:
        for method in route.methods:
            key = (method, path)
            assert key not in seen, key
            seen.add(key)
            calls = _dependency_calls(route.dependant)
            if key in ANONYMOUS_ADMIN_ROUTES:
                assert get_current_admin not in calls
            else:
                assert get_current_admin in calls, key


def test_every_admin_write_uses_the_observer_method_gate_and_exports_are_marked():
    marked_exports = set()
    for path, route in _admin_routes():
        calls = _dependency_calls(route.dependant)
        for method in route.methods & WRITE_METHODS:
            if (method, path) in ANONYMOUS_ADMIN_ROUTES:
                continue
            assert get_current_admin in calls, (method, path)
        if deny_observer_export in calls:
            marked_exports.add(path)

    assert marked_exports == EXPORT_PATHS
    discovered_exports = {
        path
        for path, _route in _admin_routes()
        if any(marker in path.lower() for marker in ("export", "download"))
    }
    assert discovered_exports == EXPORT_PATHS


def test_all_admin_get_head_handlers_have_no_forbidden_business_side_effects():
    audited = set()
    direct_cache_writers = set()
    for path, route in _admin_routes():
        for method in route.methods & {"GET", "HEAD"}:
            source = textwrap.dedent(inspect.getsource(route.endpoint))
            tree = ast.parse(source)
            audited.add((method, path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    call_name = _call_name(node)
                    if call_name == "_set_cached":
                        direct_cache_writers.add((method, path))
                        continue
                    assert call_name not in FORBIDDEN_GET_CALLS, (
                        method,
                        path,
                        call_name,
                    )
                    if (
                        isinstance(node.func, ast.Attribute)
                        and call_name in FORBIDDEN_DB_METHODS
                        and isinstance(node.func.value, ast.Name)
                    ):
                        assert node.func.value.id not in {"db", "session"}, (
                            method,
                            path,
                            ast.unparse(node.func),
                        )
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    assert not any(isinstance(target, ast.Attribute) for target in targets), (
                        method,
                        path,
                        "attribute assignment",
                    )

    assert len(audited) == 69
    assert direct_cache_writers == DIRECT_CACHE_WRITE_ALLOWLIST
