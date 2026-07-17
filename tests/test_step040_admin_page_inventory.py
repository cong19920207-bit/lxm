"""STEP-040 static inventory gate for all 35 admin pages."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "admin" / "pages"

EXPECTED_PAGES = {
    "accounts.html", "agent-aware.html", "agent-rules.html",
    "chat-prompt-agent.html", "chat-prompt-step15.html",
    "chat-prompt-step3.html", "chat-prompt-step8.html", "dashboard.html",
    "data-report.html", "diary-history.html", "diary-rules.html",
    "error.html", "feed-comments.html", "feed-posts.html", "knowledge.html",
    "life-feed-global.html", "life-feed-prompts.html", "life-feed-system.html",
    "life-plan.html", "login.html", "memory-rules.html", "operation-logs.html",
    "persona.html", "prompt.html", "relationship-rules.html",
    "safety-rules.html", "step5-5-switch.html", "system-logs.html",
    "system-monitor.html", "test-tool.html", "third-party.html",
    "user-detail.html", "users.html", "vector-token-config.html",
    "worldview.html",
}
PUBLIC_PAGES = {"login.html", "error.html"}


def _source(page: str) -> str:
    return (PAGES_DIR / page).read_text(encoding="utf-8")


def test_step040_exact_35_page_inventory_and_public_page_boundary():
    actual = {path.name for path in PAGES_DIR.glob("*.html")}
    assert actual == EXPECTED_PAGES
    assert len(actual) == 35

    for page in actual - PUBLIC_PAGES:
        source = _source(page)
        assert "/admin/static/js/admin-api.js" in source, page
        assert "checkAdminLogin" in source or "initLifeFeedPage" in source, page

    assert "adminRequest(" not in _source("login.html")
    assert "adminRequest(" not in _source("error.html")


def test_step040_observer_accounts_denied_and_other_business_pages_readable():
    accounts = _source("accounts.html")
    assert "if (getAdminRole() !== 'super_admin')" in accounts
    assert "error.html?type=403" in accounts

    for page in EXPECTED_PAGES - PUBLIC_PAGES - {"accounts.html"}:
        source = _source(page)
        assert "adminRequest('GET'" in source or page in {"dashboard.html", "test-tool.html"}, page
        restrictive_roles = re.findall(r"ALLOWED_ROLES\s*=\s*\[([^]]+)\]", source)
        for roles in restrictive_roles:
            assert "'observer'" in roles, page
        init_calls = re.findall(r"initLifeFeedPage\([^;]+\)", source)
        for call in init_calls:
            assert "'observer'" in call, page


def test_step040_all_25_non_account_write_pages_have_observer_markers():
    write_pages = set()
    for page in EXPECTED_PAGES - PUBLIC_PAGES:
        if re.search(r"adminRequest\('(POST|PUT|PATCH|DELETE)'", _source(page)):
            write_pages.add(page)

    assert len(write_pages) == 26
    assert "accounts.html" in write_pages
    business_write_pages = write_pages - {"accounts.html"}
    assert len(business_write_pages) == 25
    for page in business_write_pages:
        assert "data-write-action" in _source(page), page


def test_step040_page_contract_suite_covers_steps_030_through_038_without_playwright():
    for step in range(30, 39):
        matches = list((ROOT / "tests").glob(f"test_step{step:03d}_*.py"))
        assert matches, step
    for path in (ROOT / "tests").glob("test_step0*.py"):
        if path.name == Path(__file__).name:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        assert "from playwright" not in source, path.name
        assert "import playwright" not in source, path.name
