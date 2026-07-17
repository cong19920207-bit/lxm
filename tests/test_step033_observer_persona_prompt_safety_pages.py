# -*- coding: utf-8 -*-
"""STEP-033: 人格、Prompt、安全规则与四个只读 Prompt 页面。"""

from pathlib import Path


PAGES = Path(__file__).resolve().parents[1] / "admin/pages"
NAMES = [
    "persona.html", "prompt.html", "step5-5-switch.html", "safety-rules.html",
    "chat-prompt-step15.html", "chat-prompt-step3.html",
    "chat-prompt-step8.html", "chat-prompt-agent.html",
]


def _read(name):
    return (PAGES / name).read_text(encoding="utf-8")


def test_all_eight_pages_allow_observer_and_readonly_pages_stay_get_only():
    for name in NAMES:
        page = _read(name)
        role_decl = page.split("ROLES =", 1)[1].split(";", 1)[0]
        assert "'observer'" in role_decl, name
        assert "adminRequest('GET'" in page, name

    for name in NAMES[-4:]:
        page = _read(name)
        assert "adminRequest('POST'" not in page
        assert "adminRequest('PUT'" not in page
        assert "adminRequest('DELETE'" not in page


def test_persona_marks_fields_save_test_publish_discard_and_rollback():
    page = _read("persona.html")
    for cid in ["persona-background", "persona-personality", "persona-emotion", "persona-language", "persona-behavior", "btn-save-draft", "btn-test", "btn-publish"]:
        assert f'id="{cid}" data-write-action' in page
    assert "btn.setAttribute('data-write-action', '')" in page
    assert 'data-rollback-v="' in page and 'data-write-action data-rollback-v="' in page
    assert 'id="btn-history-toggle" data-write-action' not in page
    assert 'data-view-v="' in page and 'data-write-action data-view-v="' not in page


def test_prompt_and_switch_mark_all_draft_test_publish_and_dynamic_controls():
    prompt = _read("prompt.html")
    for cid in ["btn-test-open", "ta-step5", "btn-save-step5", "btn-discard-step5", "btn-pub-step5", "btn-save-f55", "btn-discard-f55", "btn-pub-f55", "prompt-test-level", "prompt-test-emotion", "prompt-test-memories", "prompt-test-input", "btn-run-test"]:
        assert f'id="{cid}" data-write-action' in prompt, cid
    assert "ta.setAttribute('data-write-action', '')" in prompt
    assert prompt.count("b.setAttribute('data-write-action', '')") == 2
    assert 'data-write-action data-rollback="' in prompt
    assert 'id="btn-toggle-fp" data-write-action' not in prompt

    switch = _read("step5-5-switch.html")
    for cid in ["sw-enabled", "btn-save", "btn-discard", "btn-pub"]:
        assert f'id="{cid}" data-write-action' in switch
    assert "b.setAttribute('data-write-action', '')" in switch


def test_safety_marks_inputs_file_import_save_and_dynamic_delete():
    page = _read("safety-rules.html")
    for cid in ["input-banned", "btn-save-banned", "btn-import-excel", "file-import-excel", "input-persona", "btn-save-persona", "input-style", "btn-save-style"]:
        assert f'id="{cid}" data-write-action' in page
    assert "btn.setAttribute('data-write-action', '')" in page

