"""Cross-module pytest isolation for the shared FastAPI application."""

import pytest

from backend.database import get_db


_MISSING = object()


@pytest.fixture(autouse=True)
def _isolate_module_db_override(request):
    """Use the current test module's SQLite dependency override.

    Several legacy test modules import the same ``backend.main.app`` and set
    ``get_db`` during collection.  Without resetting it per test, the last
    collected module routes every request to its own SQLite engine.
    """

    module_override = getattr(request.module, "override_get_db", None)
    if module_override is None:
        yield
        return

    from backend.main import app

    previous_override = app.dependency_overrides.get(get_db, _MISSING)
    app.dependency_overrides[get_db] = module_override
    try:
        yield
    finally:
        if previous_override is _MISSING:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
