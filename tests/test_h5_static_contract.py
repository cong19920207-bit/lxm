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
    assert "getOpenWindowUserRows" in html
    assert "markOpenWindowUsersDelivered" in html
    assert "updateSendBtn" in html
    assert "addEventListener('mousedown'" in html
    assert "addEventListener('touchstart'" in html
    assert "preventDefault()" in html
    assert "h5-theme.css" in html


def test_chat_html_immersive_surface_contract():
    """聊天页：沉浸布局锚点（顶栏三块胶囊 + 朋友圈/记忆星云 + 北京时间戳）。"""
    html = _read("chat.html")
    theme = (REPO / "frontend" / "static" / "css" / "h5-theme.css").read_text(encoding="utf-8")
    for fragment in (
        "chat-immersive",
        'id="chat-bg-image"',
        'id="chat-header-avatar"',
        "updateChatBackgroundEmotion",
        'placeholder="想和我吐槽什么…"',
        'class="bar-profile"',
        'class="bar-actions"',
        'aria-label="朋友圈"',
        'aria-label="记忆星云"',
        "goChatFeed",
        "loadChatFeedBadge",
        "/api/feed/badge",
        "icon-memory-nebula.png",
        "icon-feed.png",
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
        "#7C5CFF",
    ):
        assert fragment in html, fragment
    assert 'class="more-btn"' not in html
    assert 'aria-label="更多"' not in html
    assert "msg-bubble .msg-time" not in html
    assert "body.h5-skin:not(.chat-immersive) .chat-top-bar" in theme


def test_memory_html_nebula_surface_contract():
    """记忆页：Three.js 3D 星云 + 金色中心恒星 + 图片星点 + 悬浮详情卡片。"""
    html = _read("memory.html")
    js = _read_js("memory-nebula.js")
    vendor = FRONTEND_JS / "vendor" / "three.min.js"
    assert vendor.is_file(), f"missing {vendor}"
    assets = REPO / "frontend" / "static" / "images" / "memory-nebula"
    for name in (
        "nebula-bg.jpg",
        "core-star.png",
        "star-teal.png",
        "star-green.png",
        "star-purple.png",
        "star-pink.png",
        "star-gold.png",
        "card-sheet-bg.png",
        "icon-cat-star.png",
        "icon-gesture.png",
    ):
        assert (assets / name).is_file(), f"missing {assets / name}"
    for fragment in (
        "memory-nebula-page",
        'id="nebula-canvas"',
        'id="nebula-stage"',
        'id="nebula-loading"',
        'id="nebula-empty"',
        'id="nebula-sheet"',
        'id="nebula-sheet-category"',
        'id="nebula-sheet-title"',
        'id="nebula-sheet-value"',
        'id="nebula-tip"',
        'id="nebula-count-num"',
        'id="nebula-recenter"',
        'id="nebula-gesture-hint"',
        'id="nebula-bottom-bar"',
        'class="nebula-top-fade"',
        'class="bar-title">记忆星云</div>',
        'id="nebula-count-subtitle"',
        'aria-label="记忆说明"',
        "memory-nebula.js",
        "memory-connection-layer.js",
        "/static/js/vendor/three.min.js",
        "/static/js/vendor/three-line2.js",
        "/static/js/vendor/three-line2.js?v=20260712-2",
        "/static/images/memory-nebula/nebula-bg.jpg",
        "/static/images/memory-nebula/card-sheet-bg.png",
        "count-num",
        "去和她聊聊",
        "拖动探索 · 点击查看记忆",
        "backdrop-filter: blur(18px)",
        ".nebula-top-bar .back-btn:active .back-btn-inner",
        "长期记忆",
    ):
        assert fragment in html, fragment
    # 已废止卡片列表 DOM / 旧只读大胶囊 / 中心「林小梦」字
    assert "memory-card" not in html
    assert "枚记忆" not in html
    assert "拖动可探索星云" not in html
    assert 'id="memory-list"' not in html
    assert "对话自动整理 · 只读" not in html
    assert 'id="nebula-sheet-key"' not in html
    assert 'id="nebula-core-label"' not in html
    for fragment in (
        "/api/memory/list",
        "fetchAllMemories",
        "buildMemoryNodes",
        "addCenterStar",
        "addOrbitRings",
        "styleForKeyL1",
        "buildSelectLinks",
        "clearSelectLines",
        "MemoryConnectionLayer",
        "assignRelatedIds",
        "syncConnectionLayer",
        "onPointerDown",
        "onPointerMove",
        "onWheel",
        "MIN_RADIUS",
        "MAX_RADIUS",
        "openSheet",
        "closeSheet",
        "hitTest",
        "AUTO_YAW_SPEED",
        "WebGLRenderer",
        "SpriteMaterial",
        "AdditiveBlending",
        "core-star.png",
        "她记得 ·",
        "titleFromValue",
        "makeSpriteMaterial",
        "core-memory",
        "TAP_MAX_MS",
        "nebula-count-subtitle",
        "updateMemoryCount",
        "颗记忆星体",
        "DIM_OPACITY = 0.58",
        "DIM_SCALE = 0.92",
    ):
        assert fragment in js, fragment
    conn_js = _read_js("memory-connection-layer.js")
    for fragment in (
        "CONNECTION_CONFIG",
        "setActivePlanet",
        "refreshConnections",
        "CubicBezierCurve3",
        "Line2",
        "LineMaterial",
        "idle",
        "maxVisible",
        "glowWidth",
        "drawDuration",
        "dispose",
        "getArrivalBoost",
        "_buildClusters",
        "updateFlowBand",
        "mobileMaxVisible: 14",
        "wideMaxVisible: 18",
        "wideBreakpoint: 600",
        "depthMin: 0.52",
        "getVisibleLimit",
        "selectAmbientConnections",
        "getDepthFactor",
        "typeOpacity",
        "ringOpacity: 0.72",
        "ringEndScale: 1.34",
    ):
        assert fragment in conn_js, fragment
    assert "idle.maxVisible" not in conn_js
    line2 = FRONTEND_JS / "vendor" / "three-line2.js"
    assert line2.is_file(), f"missing {line2}"
    line2_text = line2.read_text(encoding="utf-8")
    assert "THREE.Line2" in line2_text
    assert "const _segmentsBox = new Box3();" in line2_text
    assert "const _rayBox = new Box3();" in line2_text
    assert "const _box = new Box3();" not in line2_text
    assert "updateAvatarEmotion" not in html
    assert "buildEdges" not in js
    assert "nebula-core-label" not in js

    time_js = _read_js("chat-time.js")
    assert "Asia/Shanghai" in time_js
    assert "getBeijingParts" in time_js
    assert "isSameBeijingDay" in time_js


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
    """首页改版：一屏布局、头像进设置、右上等级进关系、朋友圈富预览、日记卡、CTA。"""
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
        "/api/diary/list",
        "/api/feed/badge",
        "/api/feed/list",
        "classList.add('unread-badge--active')",
        "home-hero",
        "/static/images/Index/index.png",
        'id="linxiaomeng-avatar"',
        "/pages/settings.html",
        "goToRelationship()",
        "updateAvatarEmotion",
        "resolveStatusText",
        "和她说说话吧",
        "她在等你哦",
        "home-quick-actions",
        "home-quick-actions-wrap",
        "记忆星云",
        "/static/images/chat/icon-memory-nebula.png",
        "/pages/memory.html",
        "home-feed-card--rich",
        "home-feed-main",
        "home-feed-reply-pill",
        "NEW · ",
        "条新回复",
        "home-feed-body",
        "line-height: 1.7",
        "home-feed-footer",
        "快来看看她分享了什么吧",
        "home-diary-card",
        "home-card-meta-row",
        "home-card-chevron",
        'id="relationship-level-name"',
        "记录她的心情和生活",
        "看看她的日常分享",
        "home-cta-btn",
        "home-cta-arrow",
        'id="known-days"',
        "getBeijingDate",
        "max-height: 100vh",
        "overflow: hidden",
        'id="home-loading-screen"',
        'id="loading-avatar"',
        "lxm_home_loader_done",
        "我在。别急。",
        "马上就见面了。",
        "正在靠近你的世界",
        "loading-avatar-ring",
        "home-enter-item",
        "is-enter-reveal",
        "Promise.allSettled",
        "loadFeedHomeCard",
        "home-feed-icon.png",
        "home-diary-icon.png",
    ):
        assert fragment in html, fragment
    assert "resolveStatusText" in api_js
    assert "home-rel-card" not in html
    assert "home-feature-grid" not in html
    assert "home-relationship-card" not in html
    assert "home-memory-card" not in html
    assert "/api/memory/list" not in html
    assert "h5-home-decor" not in html
    assert "overflow-y: auto" not in html.split(".home-cards-scroll")[1].split("}")[0]
