# -*- coding: utf-8 -*-
"""STEP-010: 7 个 life-config 前端发布入口必须传递 CONFIRM。"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CALLS = {
    "admin/pages/life-feed-global.html": 2,
    "admin/pages/life-feed-prompts.html": 1,
    "admin/pages/life-feed-system.html": 2,
    "admin/pages/life-plan.html": 1,
    "admin/static/js/life-feed-admin.js": 1,
}
PUBLISH_CALL = re.compile(
    r"adminRequest\(\s*['\"]POST['\"]\s*,\s*"
    r"['\"]/api/admin/life-config/publish['\"]\s*,\s*\{(?P<body>.*?)\}\s*\)",
    re.DOTALL,
)


def test_exactly_seven_publish_calls_all_send_confirm():
    total = 0
    for relative_path, expected_count in EXPECTED_CALLS.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        calls = list(PUBLISH_CALL.finditer(source))
        assert len(calls) == expected_count, relative_path
        total += len(calls)
        for call in calls:
            preceding_confirmation = source[max(0, call.start() - 400):call.start()]
            assert "showConfirmInput(" in preceding_confirmation, relative_path
            assert re.search(
                r"\bconfirm_text\s*:\s*['\"]CONFIRM['\"]",
                call.group("body"),
            ), relative_path

    assert total == 7


def test_no_additional_life_config_publish_entry_exists():
    all_sources = list((ROOT / "admin/pages").glob("*.html")) + list(
        (ROOT / "admin/static/js").glob("*.js")
    )
    occurrences = sum(
        path.read_text(encoding="utf-8").count("/api/admin/life-config/publish")
        for path in all_sources
    )
    assert occurrences == 7
