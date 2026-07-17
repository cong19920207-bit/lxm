"""STEP-039 aggregate backend permission gate for the five admin roles."""

from pathlib import Path

from backend.main import app
from backend.utils.admin_auth import (
    _OBSERVER_BLOCKED_METHODS,
    _OBSERVER_SELF_SERVICE_EXCEPTIONS,
    deny_observer_export,
    get_current_admin,
)


ROOT = Path(__file__).resolve().parents[1]
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXPORT_PATHS = {
    "/api/admin/operation-logs/export",
    "/api/admin/stats/report/export",
    "/api/admin/system/logs/export",
}


def _admin_routes():
    for root_route in app.routes:
        original_router = getattr(root_route, "original_router", None)
        if original_router is None:
            continue
        prefix = root_route.include_context.prefix
        for route in original_router.routes:
            path = f"{prefix}{route.path}"
            if path.startswith("/api/admin/"):
                yield path, route


def _dependency_calls(dependant) -> set:
    calls = {dependant.call}
    for child in dependant.dependencies:
        calls.update(_dependency_calls(child))
    return calls


def test_step039_route_inventory_auth_write_gate_and_exact_exceptions():
    routes = list(_admin_routes())
    methods = {
        (method, path)
        for path, route in routes
        for method in route.methods
    }
    assert len(routes) == 159
    assert len(methods & {(method, path) for method, path in methods if method in {"GET", "HEAD"}}) == 69
    assert len(methods & {(method, path) for method, path in methods if method in WRITE_METHODS}) == 90
    assert _OBSERVER_BLOCKED_METHODS == frozenset(WRITE_METHODS)
    assert _OBSERVER_SELF_SERVICE_EXCEPTIONS == frozenset(
        {
            ("POST", "/api/admin/auth/logout"),
            ("POST", "/api/admin/auth/change-password"),
        }
    )

    for path, route in routes:
        calls = _dependency_calls(route.dependant)
        for method in route.methods:
            if (method, path) == ("POST", "/api/admin/auth/login"):
                continue
            assert get_current_admin in calls, (method, path)


def test_step039_all_and_only_builtin_exports_have_observer_denial():
    marked = set()
    discovered = set()
    for path, route in _admin_routes():
        calls = _dependency_calls(route.dependant)
        if deny_observer_export in calls:
            marked.add(path)
        if any(marker in path.lower() for marker in ("export", "download")):
            discovered.add(path)
    assert discovered == EXPORT_PATHS
    assert marked == EXPORT_PATHS


def test_step039_executable_gate_suite_covers_all_required_boundaries():
    required_evidence = {
        "tests/test_admin_auth.py": (
            "test_observer_write_methods_are_blocked_before_endpoint",
            "test_only_exact_auth_post_paths_are_exempt",
            "test_anonymous_preflight_returns_only_cors_response",
        ),
        "tests/test_step016_four_role_regression.py": (
            "super_admin",
            "ops_admin",
            "ai_trainer",
            "tech_ops",
        ),
        "tests/test_step021_observer_exports.py": tuple(EXPORT_PATHS),
        "tests/test_step027_observer_credential_status.py": (
            "credential_configured",
            '"enabled": True',
            "USER_KEY_HASH",
        ),
        "tests/test_step030_observer_accounts_guard.py": (
            "test_observer_all_six_account_apis_are_403_without_data_or_mutation",
            "test_super_admin_account_management_lifecycle_remains_available",
        ),
    }
    for relative_path, markers in required_evidence.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in source, (relative_path, marker)
