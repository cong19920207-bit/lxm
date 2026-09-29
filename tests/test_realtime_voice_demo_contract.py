# -*- coding: utf-8 -*-
"""实时语音逐态 Demo 的产品表面契约。"""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEMO = (
    REPO
    / "docs"
    / "design"
    / "realtime_voice"
    / "P1"
    / "demo"
    / "demo-voice-call-states.html"
)


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str], parent: "_Node | None"):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node] = []

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()


class _TreeParser(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {}, None)
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in self._VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.current = self.current.parent or self.root

    def handle_endtag(self, tag):
        cursor = self.current
        while cursor is not self.root and cursor.tag != tag:
            cursor = cursor.parent or self.root
        if cursor is not self.root:
            self.current = cursor.parent or self.root


def _load() -> tuple[str, _Node]:
    assert DEMO.is_file(), f"missing {DEMO}"
    html = DEMO.read_text(encoding="utf-8")
    parser = _TreeParser()
    parser.feed(html)
    return html, parser.root


def _find(root: _Node, *, node_id: str | None = None, class_name: str | None = None):
    nodes = [root, *root.descendants()]
    for node in nodes:
        if node_id is not None and node.attrs.get("id") != node_id:
            continue
        if class_name is not None and class_name not in node.classes:
            continue
        return node
    raise AssertionError(f"node not found: id={node_id!r}, class={class_name!r}")


def _css_rule(html: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", html, re.S)
    assert match, f"missing CSS rule: {selector}"
    return match.group(1)


class RealtimeVoiceDemoContractTest(unittest.TestCase):
    def test_demo_uses_iphone_16_pro_screen_size(self):
        """防止设备框退回其他 iPhone 尺寸或把边框算进屏幕内容。"""
        html, _ = _load()
        shell = _css_rule(html, ".phone-shell")
        phone = _css_rule(html, ".phone")
        self.assertIn("width: 422px", shell)
        self.assertIn("height: 894px", shell)
        self.assertIn("width: 402px", phone)
        self.assertIn("height: 874px", phone)

    def test_demo_variant_switches_stay_outside_product_screen(self):
        """防止评审用的原因切换标签重新混入用户可见通话界面。"""
        _, root = _load()
        phone = _find(root, node_id="phone")
        self.assertFalse(
            [node for node in phone.descendants() if "demo-chips" in node.classes]
        )

        inspector = _find(root, class_name="inspector")
        binds = {
            node.attrs.get("data-bind")
            for node in inspector.descendants()
            if "demo-chips" in node.classes
        }
        self.assertEqual(binds, {"preflight", "ending", "card"})

    def test_incall_controls_are_accessible_buttons_with_state(self):
        """防止静音/扬声器退化为不可操作图标或丢失选中态语义。"""
        _, root = _load()
        phone = _find(root, node_id="phone")
        controls = [
            node
            for node in phone.descendants()
            if node.attrs.get("data-control") in {"mute", "speaker"}
        ]
        self.assertTrue(controls)
        self.assertTrue(all(node.tag == "button" for node in controls))
        self.assertTrue(all(node.attrs.get("aria-pressed") == "false" for node in controls))

    def test_end_screen_separates_status_record_and_async_summary(self):
        """防止结束页把通话卡片、摘要和长期记忆混写成“已经记住”。"""
        html, root = _load()
        _find(root, node_id="end-status")
        _find(root, node_id="end-duration-label")
        self.assertIn("聊天里已经留下一张通话记录", html)
        self.assertIn("摘要正在整理", html)
        self.assertNotIn("这次我会记在聊天里", html)

    def test_speaking_state_explains_existing_barge_in_behavior(self):
        """防止 PRD 已要求的自然打断在界面上完全不可发现。"""
        html, _ = _load()
        self.assertIn("直接开口就能打断她", html)

    def test_demo_respects_reduced_motion_preference(self):
        """防止通话光环和加载动画忽略系统的减少动态效果设置。"""
        html, _ = _load()
        self.assertIn("@media (prefers-reduced-motion: reduce)", html)
        self.assertIn("animation-duration: 0.01ms", html)

    def test_missed_call_keeps_calling_layout_without_double_portrait(self):
        """防止未接页把全屏人物和圆头像叠在同一视觉焦点。"""
        _, root = _load()
        scene = next(
            node for node in root.descendants() if node.attrs.get("data-id") == "s8"
        )
        background = next(node for node in scene.descendants() if "bg" in node.classes)
        self.assertNotIn("sharp", background.classes)
        self.assertIn("avatar/character-ref/base.png", background.attrs.get("style", ""))

    def test_chat_back_control_keeps_default_ios_hit_size(self):
        """防止聊天返回按钮再次缩小到 iOS 默认触控尺寸以下。"""
        html, _ = _load()
        back = _css_rule(html, ".chat-head .back")
        self.assertIn("width: 44px", back)
        self.assertIn("height: 44px", back)


if __name__ == "__main__":
    unittest.main()
