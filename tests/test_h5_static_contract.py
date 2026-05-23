# -*- coding: utf-8 -*-
"""
H5 静态页契约快照：防止样式迭代时误删已约定 DOM/属性（与 docs/contract.md 对齐）。
仅断言文件内子串存在，不启动浏览器。
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FRONTEND_PAGES = REPO / "frontend" / "pages"


def _read(name: str) -> str:
    p = FRONTEND_PAGES / name
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_chat_html_send_contract():
    html = _read("chat.html")
    assert 'id="msg-input"' in html
    assert 'enterkeyhint="send"' in html
    assert 'id="send-btn"' in html
    assert 'type="button"' in html
    assert "class=\"send-btn" in html or "class='send-btn" in html
    assert "CHAT_SEND_DEBOUNCE_MS" in html
    assert "updateSendBtn" in html
    assert "addEventListener('mousedown'" in html
    assert "addEventListener('touchstart'" in html
    assert "preventDefault()" in html
    assert "h5-theme.css" in html


def test_chat_html_immersive_surface_contract():
    """聊天页：沉浸布局锚点（与 docs/contract.md 2026-05-23 聊天摘要一致）。"""
    html = _read("chat.html")
    theme = (REPO / "frontend" / "static" / "css" / "h5-theme.css").read_text(encoding="utf-8")
    for fragment in (
        "chat-immersive",
        'id="chat-bg-image"',
        'id="chat-header-avatar"',
        "updateChatBackgroundEmotion",
        'placeholder="想和我吐槽什么…"',
        'class="more-btn"',
        'aria-label="更多"',
        "msg-content",
        "msg-time-divider",
        "chat-time.js",
        "formatChatTime",
        "shouldShowTimeStamp",
        "data-created-at",
        "input-area-inner",
        "#D8D8DC",
        "#8E8E93",
        "#A6FF7B",
    ):
        assert fragment in html, fragment
    assert "msg-bubble .msg-time" not in html
    assert "body.h5-skin:not(.chat-immersive) .chat-top-bar" in theme
    assert "updateAvatarEmotion" not in html


def test_login_html_auth_ids():
    html = _read("login.html")
    for fragment in (
        'id="panel-login"',
        'id="panel-register"',
        'id="panel-reset"',
        'id="login-username"',
        'id="login-password"',
        'id="btn-login"',
        'id="reg-username"',
        'id="reg-password"',
        'id="reg-password2"',
        'id="btn-register"',
        'id="reset-username"',
        'id="btn-reset"',
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/reset-password",
        "h5-theme.css",
    ):
        assert fragment in html, fragment


def test_settings_change_password_ids():
    html = _read("settings.html")
    for fragment in (
        'id="password-form"',
        'id="old-password"',
        'id="new-password"',
        'id="confirm-password"',
        "/api/auth/reset-password",
        "h5-theme.css",
    ):
        assert fragment in html, fragment


@pytest.mark.parametrize(
    "fname",
    [
        "index.html",
        "diary.html",
        "relationship.html",
        "memory.html",
    ],
)
def test_core_pages_link_theme(fname: str):
    html = _read(fname)
    assert "h5-theme.css" in html
    assert 'class="h5-skin"' in html or "class='h5-skin'" in html


def test_h5_theme_css_exists():
    p = REPO / "frontend" / "static" / "css" / "h5-theme.css"
    text = p.read_text(encoding="utf-8")
    assert "h5-neo-border" in text
    assert "prefers-reduced-motion" in text


def test_index_html_home_surface_contract():
    """首页：未读角标 DOM、气泡文案容器、Hero 背景、主题进度条覆盖、未读呼吸类名（与 contract 摘要一致）。"""
    html = _read("index.html")
    theme = (REPO / "frontend" / "static" / "css" / "h5-theme.css").read_text(encoding="utf-8")
    for fragment in (
        'id="unread-badge"',
        "unread-badge--active",
        "home-chat-btn-wrap",
        'id="status-text"',
        "home-status-bubble",
        "/api/agent/unread-count",
        "classList.add('unread-badge--active')",
        "home-hero",
        "/static/images/Index/index.png",
        'id="linxiaomeng-avatar"',
        "home-rel-card",
        "home-feature-grid",
    ):
        assert fragment in html, fragment
    assert "body.h5-skin .h5-home-main .home-rel-card .progress-bar" in theme
    assert "linear-gradient(90deg, #3b82f6 0%, #ec4899 100%)" in theme
    assert "home-hero .h5-home-decor::before" in theme
