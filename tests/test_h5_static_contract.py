# -*- coding: utf-8 -*-
"""
H5 静态页契约快照：防止样式迭代时误删已约定 DOM/属性（与 docs/contract.md 对齐）。
仅断言文件内子串存在，不启动浏览器。
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FRONTEND_PAGES = REPO / "frontend" / "pages"
FRONTEND_JS = REPO / "frontend" / "static" / "js"


def _read(name: str) -> str:
    p = FRONTEND_PAGES / name
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def _read_js(name: str) -> str:
    p = FRONTEND_JS / name
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
    api_js = _read_js("api.js")
    for fragment in (
        "EMOTION_STATUS_MAP",
        "resolveStatusText",
        "DEFAULT_STATUS_TEXT",
    ):
        assert fragment in api_js, fragment
    for fragment in (
        'id="password-form"',
        'id="old-password"',
        'id="new-password"',
        'id="confirm-password"',
        "/api/auth/reset-password",
        "h5-theme.css",
        "settings-soft-page",
        'id="profile-status"',
        "profile-status-text",
        "profile-online",
        "profile-wave",
        'id="linxiaomeng-avatar"',
        "/api/app/persona-background",
        "/api/relationship/status",
        "resolveStatusText",
        "toggleAbout",
        "handleChangePassword",
        "toggleSetting",
        "handleLogout",
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
    # body 可能为 class="h5-skin" 或 class="h5-skin diary-page" 等多类名
    assert (
        'class="h5-skin"' in html
        or "class='h5-skin'" in html
        or 'class="h5-skin ' in html
        or "class='h5-skin " in html
    )


def test_h5_theme_css_exists():
    p = REPO / "frontend" / "static" / "css" / "h5-theme.css"
    text = p.read_text(encoding="utf-8")
    assert "h5-neo-border" in text
    assert "prefers-reduced-motion" in text


def test_relationship_html_surface_contract():
    """关系页：暗黑皮、Hero 主图、拍立得情绪头像、亲密值文案、接口路径（与 contract 摘要一致）。"""
    html = _read("relationship.html")
    for fragment in (
        "relationship-page",
        "/static/images/relationship/Relationship_Lxm.png",
        'id="linxiaomeng-avatar"',
        "updateAvatarEmotion",
        "/api/relationship/detail",
        "/api/relationship/growth-log",
        "亲密值",
        "rel-hero-bar",
        "bottom: 50px",
        "margin-top: -50px",
        "translateX(-50px)",
        "想和你去看海。",
        "rotate(-8deg)",
        "translateY(-8px)",
        "padding: 4px 4px 5px",
        "rel-today-grid",
        "flex-direction: row",
        "tc-done",
        "回复消息",
        "还差获得 ",
        "rel-progress-wrap",
    ):
        assert fragment in html, fragment
    assert "grid-template-columns: 1fr 1fr" not in html
    assert "回复林小梦的消息" not in html


def test_index_html_home_surface_contract():
    """首页深色改版：一屏布局、Hero、顶栏亲密度、五接口并行、预览卡 DOM 与 CTA（与 contract 2026-06-10 摘要一致）。"""
    html = _read("index.html")
    api_js = _read_js("api.js")
    for fragment in (
        'id="unread-badge"',
        "unread-badge--active",
        "home-chat-btn-wrap",
        'id="status-text"',
        "home-status-bubble",
        "/api/agent/unread-count",
        "/api/relationship/detail",
        "/api/memory/list",
        "/api/diary/list",
        "classList.add('unread-badge--active')",
        "home-hero",
        "/static/images/Index/index.png",
        'id="linxiaomeng-avatar"',
        "updateAvatarEmotion",
        "resolveStatusText",
        "和她说说话吧",
        "她在等你哦",
        "home-quick-actions",
        "home-quick-actions-wrap",
        "home-memory-card",
        "home-diary-card",
        "home-relationship-card",
        "home-card-meta-row",
        "home-card-right--rel",
        "home-card-chevron",
        'id="relationship-level-name"',
        "记录她的心情和生活",
        "home-cta-btn",
        "home-cta-arrow",
        'id="known-days"',
        "getBeijingDate",
        "max-height: 100vh",
        "overflow: hidden",
    ):
        assert fragment in html, fragment
    assert "resolveStatusText" in api_js
    assert "home-rel-card" not in html
    assert "home-feature-grid" not in html
    assert "h5-home-decor" not in html
    assert "overflow-y: auto" not in html.split(".home-cards-scroll")[1].split("}")[0]
