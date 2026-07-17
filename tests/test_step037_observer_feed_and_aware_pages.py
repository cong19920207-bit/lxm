"""STEP-037 observer read-only contracts for feed posts/comments and awareness."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "admin" / "pages"


def _page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_step037_all_pages_allow_observer_and_keep_read_interactions():
    pages = {
        "feed-posts.html": ("filter-status", "btn-search", "posts-pagination", "detail-modal"),
        "feed-comments.html": ("filter-post-id", "filter-user-id", "filter-gen-status", "btn-search", "comments-pagination"),
        "agent-aware.html": ("filter-user-id", "filter-trigger", "filter-status", "btn-search", "aware-pagination", "detail-modal"),
    }
    for page, read_ids in pages.items():
        source = _page(page)
        assert "['super_admin', 'ai_trainer', 'ops_admin', 'observer']" in source, page
        assert "adminRequest('GET'" in source, page
        for element_id in read_ids:
            assert f'id="{element_id}" data-write-action' not in source, (page, element_id)


def test_step037_post_static_dynamic_and_modal_writes_are_marked():
    source = _page("feed-posts.html")
    assert 'data-write-action id="btn-add-text"' in source
    assert 'data-write-action id="btn-add-ai"' in source
    assert source.count('<div class="modal-body" data-write-action>') == 3
    for element_id in ("edit-modal-submit", "upload-modal-submit", "ai-modal-submit"):
        assert f'id="{element_id}" data-write-action' in source
    for handler in ("openEdit(", "toggleVisibility("):
        assert f'data-write-action onclick="{handler}' in source
    assert 'data-write-action onclick="showDetail(' not in source


def test_step037_comment_and_aware_dynamic_writes_are_marked_but_details_remain():
    comments = _page("feed-comments.html")
    assert '<div class="modal-body" data-write-action>' in comments
    assert 'id="edit-modal-submit" data-write-action' in comments
    for handler in ("openEditComment(", "regenerateComment(", "deleteComment("):
        assert f'data-write-action onclick="{handler}' in comments

    aware = _page("agent-aware.html")
    assert 'id="btn-reset-counters" data-write-action' in aware
    for handler in ("retryAware(", "deleteAware("):
        assert f'data-write-action onclick="{handler}' in aware
    assert 'data-write-action onclick="showAwareDetail(' not in aware


def test_step037_existing_readonly_rendering_and_backend_write_methods_remain():
    for page in ("feed-posts.html", "feed-comments.html", "agent-aware.html"):
        source = _page(page)
        assert "function isReadonly() { return isLifeFeedReadOnly(PAGE_KEY); }" in source
        assert "if (!readonly)" in source
        assert "renderPagination(" in source
    assert "adminRequest('PATCH'" in _page("feed-posts.html")
    assert "adminRequest('PUT'" in _page("feed-comments.html")
    assert "adminRequest('DELETE'" in _page("agent-aware.html")
