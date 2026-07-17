"""STEP-036 observer read-only contracts for life-plan and worldview pages."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "admin" / "pages"


def _page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_step036_both_pages_allow_observer_and_keep_read_controls_available():
    life_plan = _page("life-plan.html")
    worldview = _page("worldview.html")

    assert "['super_admin', 'ai_trainer', 'ops_admin', 'observer']" in life_plan
    assert "['super_admin', 'ai_trainer', 'ops_admin', 'observer']" in worldview

    for source, read_ids in (
        (life_plan, ("main-tabs", "week_start_date", "btn-load-outline", "plan_date", "btn-load-daily")),
        (worldview, ("main-tabs", "snapshot-plan-date", "btn-load-snapshots", "btn-clear-date", "event-keyword", "btn-search-events")),
    ):
        for element_id in read_ids:
            assert f'id="{element_id}" data-write-action' not in source


def test_step036_life_plan_static_and_dynamic_writes_are_marked():
    source = _page("life-plan.html")
    assert '<div class="settings-grid" data-write-action>' in source
    for element_id in ("btn-gen-outline", "btn-add-outline", "btn-gen-daily", "btn-add-scene"):
        assert f'data-write-action id="{element_id}"' in source
    for element_id in ("outline-modal-submit", "scene-modal-submit"):
        assert f'id="{element_id}" data-write-action' in source
    assert source.count('<div class="modal-body" data-write-action>') >= 2
    assert "if (!readonly)" in source
    assert source.count("data-write-action onclick=\"") >= 4


def test_step036_worldview_static_and_dynamic_writes_are_marked():
    source = _page("worldview.html")
    assert 'data-write-action id="btn-add-event"' in source
    for element_id in ("snapshot-modal-submit", "event-modal-submit"):
        assert f'id="{element_id}" data-write-action' in source
    assert source.count('<div class="modal-body" data-write-action>') >= 2
    assert source.count("data-write-action onclick=\"") >= 4
    assert "renderPagination('snapshots-pagination'" in source
    assert "renderPagination('events-pagination'" in source


def test_step036_write_requests_remain_guarded_by_backend_and_readonly_rendering():
    for page in ("life-plan.html", "worldview.html"):
        source = _page(page)
        assert "function isReadonly() { return isLifeFeedReadOnly(PAGE_KEY); }" in source
        assert "adminRequest('GET'" in source
        assert "adminRequest('PUT'" in source
        assert "adminRequest('POST'" in source or page == "worldview.html"
        assert "adminRequest('DELETE'" in source
