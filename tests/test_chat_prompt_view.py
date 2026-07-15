# -*- coding: utf-8 -*-
# 对话流 Prompt 只读展示：服务层 + API 注册冒烟；并回归既有 Prompt 拼装行为

from backend.main import app
from backend.services.chat_prompt_view_service import (
    get_agent_prompt_view,
    get_step3_prompt_view,
    get_step8_prompt_view,
    get_step15_prompt_view,
)
from backend.services.prompt_builder import (
    ACTIVE_TRIGGER_INSTRUCTIONS,
    AGENT_TASK_OUTPUT_SUFFIX,
    EMPATHY_RULES,
    SILENCE_CORRECTION_8_14,
    SILENCE_CORRECTION_15_PLUS,
    STEP8_PROACTIVE_INPUT_TEMPLATE,
    PromptBuilder,
)
from backend.services.query_rewrite_service import _build_step1_5_prompt


class TestChatPromptViewService:
    """只读视图与运行时同源常量一致。"""

    def test_step15_has_main_and_step8_variants(self):
        data = get_step15_prompt_view()
        assert data["readonly"] is True
        keys = {v["key"] for v in data["variants"]}
        assert keys == {"main", "step8"}
        main = next(v["content"] for v in data["variants"] if v["key"] == "main")
        step8 = next(v["content"] for v in data["variants"] if v["key"] == "step8")
        assert "{{persona}}" in main
        assert "{{rewrite_input}}" in main
        assert "【系统指令】" in main
        assert "{{future_action}}" in step8
        # 与直接调用拼装函数一致
        expected_main = _build_step1_5_prompt(
            persona_text="{{persona}}",
            round_context={
                "time_description": "{{time_description}}",
                "activity_description": "{{activity_description}}",
                "level_name": "{{level_name}}",
                "relation_description": "{{relation_description}}",
                "user_real_name": "{{user_real_name}}",
                "user_hobby_name": "{{user_hobby_name}}",
            },
            recent_conversations=[{"role": "user", "content": "{{recent_chat_line}}"}],
            rewrite_input="{{rewrite_input}}",
            source="main",
        )
        assert main == expected_main

    def test_step3_exposes_hardcoded_rules(self):
        data = get_step3_prompt_view()
        assert data["readonly"] is True
        assert data["empathy_rules"] == EMPATHY_RULES
        assert data["silence_corrections"][0]["text"] == SILENCE_CORRECTION_8_14
        assert data["silence_corrections"][1]["text"] == SILENCE_CORRECTION_15_PLUS
        keys = [m["key"] for m in data["module_order"]]
        assert keys[0] == "system"
        assert "user_input" in keys

    def test_step8_template_matches_builder(self):
        data = get_step8_prompt_view()
        assert data["proactive_input_template"] == STEP8_PROACTIVE_INPUT_TEMPLATE
        # 运行时替换占位符后与 _build_proactive_input 一致
        builder = PromptBuilder(db=None)  # type: ignore[arg-type]
        rendered = builder._build_proactive_input("下午三点提醒你喝水")
        expected = STEP8_PROACTIVE_INPUT_TEMPLATE.replace(
            "{{future_action}}", "下午三点提醒你喝水",
        )
        assert rendered == expected

    def test_agent_triggers_p0_to_p4(self):
        data = get_agent_prompt_view()
        keys = [t["key"] for t in data["triggers"]]
        assert keys == ["P0", "P1", "P2", "P3", "P4"]
        for t in data["triggers"]:
            assert t["task_instruction"] == ACTIVE_TRIGGER_INSTRUCTIONS[t["key"]]
            assert t["full_task_block"] == (
                ACTIVE_TRIGGER_INSTRUCTIONS[t["key"]] + AGENT_TASK_OUTPUT_SUFFIX
            )
        builder = PromptBuilder(db=None)  # type: ignore[arg-type]
        for key in keys:
            assert builder._build_active_task_instruction(key) == (
                ACTIVE_TRIGGER_INSTRUCTIONS[key] + AGENT_TASK_OUTPUT_SUFFIX
            )


class TestChatPromptViewRoutesRegistered:
    """确认只读路由已挂载，且不覆盖既有 Prompt 管理路径。"""

    def test_chat_prompt_view_paths_exist(self):
        # FastAPI 新版本 include_router 以 _IncludedRouter 包裹，改走 OpenAPI paths
        paths = set(app.openapi().get("paths", {}).keys())
        assert "/api/admin/chat-prompt-view/step15" in paths
        assert "/api/admin/chat-prompt-view/step3" in paths
        assert "/api/admin/chat-prompt-view/step8" in paths
        assert "/api/admin/chat-prompt-view/agent" in paths
        # 既有可编辑接口仍在
        assert "/api/admin/prompt/step5" in paths
        assert "/api/admin/prompt/step5-5/fragments" in paths
        assert "/api/admin/step6-memory-prompt" in paths
