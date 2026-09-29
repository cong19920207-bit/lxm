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
VOICE_CONFIG_ROUTE_ROLES = {
    ('POST', '/api/admin/voice/jobs/{job_id}/retry'): frozenset({'super_admin', 'tech_ops'}),
    ('GET', '/api/admin/voice/crisis-records'): frozenset({'super_admin'}),
    ('GET', '/api/admin/voice/crisis-records/{record_id}'): frozenset({'super_admin'}),
    ("PUT", "/api/admin/safety-rules/crisis-keywords"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("GET", "/api/admin/safety-rules/crisis-keywords/history"): frozenset(
        {"super_admin", "ai_trainer", "observer"}
    ),
    ("POST", "/api/admin/safety-rules/crisis-keywords/rollback"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("GET", "/api/admin/voice/config/{key}"): frozenset(
        {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
    ),
    ("GET", "/api/admin/voice/capability-evidence/{evidence_report_id}"): frozenset(
        {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
    ),
    ("PATCH", "/api/admin/voice/config/config/draft/{section}"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("PATCH", "/api/admin/voice/config/script/draft/{section}"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("DELETE", "/api/admin/voice/config/config/draft/{section}"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("DELETE", "/api/admin/voice/config/script/draft/{section}"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("DELETE", "/api/admin/voice/config/config/draft"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("DELETE", "/api/admin/voice/config/script/draft"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("POST", "/api/admin/voice/config/config/validate"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("POST", "/api/admin/voice/config/script/validate"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("POST", "/api/admin/voice/config/config/publish"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("POST", "/api/admin/voice/config/script/publish"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("GET", "/api/admin/voice/config/{key}/history"): frozenset(
        {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
    ),
    ("GET", "/api/admin/voice/config/{key}/history/{version}"): frozenset(
        {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
    ),
    ("POST", "/api/admin/voice/config/config/rollback"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("POST", "/api/admin/voice/config/script/rollback"): frozenset(
        {"super_admin", "ai_trainer"}
    ),
    ("POST", "/api/admin/voice/config/test-connection"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    ("POST", "/api/admin/voice/config/test-capability"): frozenset(
        {"super_admin", "tech_ops"}
    ),
    (
        "POST",
        "/api/admin/voice/config/capabilities/{capability_key}/force-test",
    ): frozenset(
        {"super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"}
    ),
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


def _declared_role_sets(dependant) -> set[frozenset[str]]:
    role_sets = set()
    for child in dependant.dependencies:
        call = child.call
        if getattr(call, "__name__", None) == "_role_checker":
            roles = inspect.getclosurevars(call).nonlocals.get("roles")
            if roles is not None:
                role_sets.add(frozenset(roles))
        role_sets.update(_declared_role_sets(child))
    return role_sets


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_all_admin_routes_except_login_have_complete_admin_authentication():
    routes = _admin_routes()
    methods = {
        (method, path)
        for path, route in routes
        for method in route.methods
    }
    assert len(routes) == 184
    assert sum(method in {"GET", "HEAD"} for method, _ in methods) == 74
    assert sum(method in WRITE_METHODS for method, _ in methods) == 108

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


def test_voice_and_crisis_routes_have_exact_methods_and_roles():
    actual = {}
    for path, route in _admin_routes():
        if not (
            path.startswith("/api/admin/voice/")
            or path.startswith("/api/admin/safety-rules/crisis-keywords")
        ):
            continue
        for method in route.methods:
            actual[(method, path)] = _declared_role_sets(route.dependant)

    assert set(actual) == set(VOICE_CONFIG_ROUTE_ROLES)
    assert actual == {
        route: {roles}
        for route, roles in VOICE_CONFIG_ROUTE_ROLES.items()
    }


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

    assert len(audited) == 77
    assert direct_cache_writers == DIRECT_CACHE_WRITE_ALLOWLIST
