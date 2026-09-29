"""STEP-039 aggregate backend permission gate for the five admin roles."""

import inspect
from pathlib import Path

from backend.main import app
from backend.utils import admin_auth
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
VOICE_CONFIG_ROUTE_ROLES = {
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


def test_step039_route_inventory_auth_write_gate_and_exact_exceptions():
    routes = list(_admin_routes())
    methods = {
        (method, path)
        for path, route in routes
        for method in route.methods
    }
    assert len(routes) == 183
    assert sum(method in {"GET", "HEAD"} for method, _ in methods) == 74
    assert sum(method in WRITE_METHODS for method, _ in methods) == 107
    assert _OBSERVER_BLOCKED_METHODS == frozenset(WRITE_METHODS)
    assert _OBSERVER_SELF_SERVICE_EXCEPTIONS == frozenset(
        {
            ("POST", "/api/admin/auth/logout"),
            ("POST", "/api/admin/auth/change-password"),
        }
    )
    assert getattr(
        admin_auth,
        "_OBSERVER_AUDITED_DENIAL_EXCEPTIONS",
        None,
    ) == frozenset(
        {
            (
                "POST",
                "/api/admin/voice/config/capabilities/{capability_key}/force-test",
            )
        }
    )

    for path, route in routes:
        calls = _dependency_calls(route.dependant)
        for method in route.methods:
            if (method, path) == ("POST", "/api/admin/auth/login"):
                continue
            assert get_current_admin in calls, (method, path)


def test_step039_voice_routes_have_exact_methods_and_role_boundaries():
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
