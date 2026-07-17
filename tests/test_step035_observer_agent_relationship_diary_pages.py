"""STEP-035 observer read-only contracts for Agent, relationship and diary pages."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "admin" / "pages"


def _page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_step035_all_four_pages_allow_observer_read_access():
    for page in (
        "agent-rules.html",
        "relationship-rules.html",
        "diary-rules.html",
        "diary-history.html",
    ):
        source = _page(page)
        assert "'observer'" in source, page
        assert "adminRequest('GET'" in source, page


def test_step035_agent_dynamic_and_static_write_controls_are_read_only():
    source = _page("agent-rules.html")
    assert '<div id="tab-triggers" class="tab-pane active agent-disable-while-load" data-write-action>' in source
    assert '<div id="tab-decision" class="tab-pane agent-disable-while-load" data-write-action>' in source
    assert "applyObserverReadOnly(document.getElementById('tab-triggers'));" in source
    assert "applyObserverReadOnly(document.getElementById('tab-decision'));" in source
    assert 'id="main-tabs" data-write-action' not in source


def test_step035_relationship_and_diary_rule_writes_are_marked():
    relationship = _page("relationship-rules.html")
    assert '<div id="tab-levels" class="tab-pane active" data-write-action>' in relationship
    assert '<div id="tab-growth" class="tab-pane" data-write-action>' in relationship
    assert 'id="modal-impact-confirm" data-write-action' in relationship
    assert "applyObserverReadOnly(document.getElementById('tab-levels'));" in relationship
    assert 'id="main-tabs" data-write-action' not in relationship

    diary = _page("diary-rules.html")
    for element_id in (
        "gen-prompt-with",
        "gen-prompt-without",
        "max-length",
        "gen-hour",
        "gen-minute",
        "btn-save-diary-rules",
    ):
        assert f'id="{element_id}" data-write-action' in diary
    assert 'href="/admin/pages/diary-history.html" data-write-action' not in diary


def test_step035_diary_history_filters_and_pagination_remain_read_only_interactions():
    source = _page("diary-history.html")
    assert "adminRequest('GET', url)" in source
    assert "adminRequest('PUT'" not in source
    assert "adminRequest('POST'" not in source
    assert "adminRequest('DELETE'" not in source
    assert 'id="dhQuery">查询</button>' in source
    assert "renderPagination" in source
    assert "data-write-action" not in source
