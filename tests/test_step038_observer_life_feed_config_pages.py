"""STEP-038 observer read-only contracts for the three life-feed config pages."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "admin" / "pages"


def _page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_step038_three_pages_allow_observer_read_access():
    global_page = _page("life-feed-global.html")
    prompts = _page("life-feed-prompts.html")
    system = _page("life-feed-system.html")

    assert "var ALLOWED_ROLES = ['super_admin', 'ai_trainer', 'ops_admin', 'observer'];" in global_page
    assert "['super_admin', 'ai_trainer', 'observer']" in prompts
    assert "['super_admin', 'ai_trainer', 'tech_ops', 'observer']" in system
    for source in (global_page, prompts, system):
        assert "adminRequest('GET'" in source


def test_step038_global_static_and_dynamic_editors_use_readonly_markers():
    source = _page("life-feed-global.html")
    for element_id in (
        "input-categories_vocab",
        "input-emotion_vocab",
        "cfg-feed_page_header_bg_url",
        "cfg-feed_page_header_avatar_url",
        "cfg-feed_page_signature",
        "cfg-home_city",
    ):
        assert f'id="{element_id}" data-write-action' in source
    assert 'data-add-tag="categories_vocab" data-write-action' in source
    assert 'data-add-tag="emotion_vocab" data-write-action' in source
    assert 'data-del-tag="' in source and 'data-write-action' in source
    assert "'<textarea data-write-action class=\"form-control\"" in source
    assert source.count('data-edit-only data-write-action') >= 5
    assert "window.location.href='/admin/pages/persona.html'" in source


def test_step038_prompt_dynamic_fields_and_actions_are_marked_but_tabs_remain():
    source = _page("life-feed-prompts.html")
    assert 'id="main-tabs" data-write-action' not in source
    assert "'<input data-write-action type=\"'" in source
    assert "'<textarea data-write-action class=\"form-control'" in source
    assert source.count('data-edit-only data-write-action') >= 5
    assert "initTabs('main-tabs')" in source


def test_step038_system_controls_are_marked_and_status_table_remains_readable():
    source = _page("life-feed-system.html")
    assert 'id="auto-publish-enabled" data-write-action' in source
    assert '<div class="lf-grid-3" data-write-action' in source
    assert source.count('<div class="lf-grid-2" data-write-action') >= 2
    assert source.count('data-edit-only data-write-action') >= 3
    assert 'id="liblib-summary" data-write-action' not in source
    assert 'id="liblib-tbody"' in source
    assert "loadLiblibStats();" in source
