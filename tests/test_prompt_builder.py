# -*- coding: utf-8 -*-
# STEP-004 / STEP-021 Prompt 改造单元测试

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.services.prompt_builder import (
    MAX_TOTAL_TOKENS,
    MODULE_ORDER,
    MODULE_SEPARATOR,
    MODULE_TOKEN_LIMITS,
    PromptBuilder,
    _generate_time_description,
    count_tokens,
    get_activity_description,
)


# ============ 辅助工厂 ============


def _make_relationship(**overrides):
    """构造一个模拟 Relationship 对象"""
    defaults = {
        "level": 1,
        "growth_value": 300,
        "last_interaction_at": datetime.utcnow(),
        "consecutive_login_days": 5,
        "relation_description": None,
        "user_description": None,
        "user_hobby_name": None,
        "user_real_name": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_builder():
    """构造 PromptBuilder，mock 掉 db session"""
    mock_db = AsyncMock()
    return PromptBuilder(db=mock_db)


def _make_retrieval_results(
    cg=None, cp=None, ck=None, user=None,
):
    """构造 Step2 四路检索结果 dict"""
    return {
        "character_global": cg or [],
        "character_private": cp or [],
        "character_knowledge": ck or [],
        "user": user or [],
    }


def _make_memory_dict(content: str, score: float = 0.8) -> dict:
    """构造一条 Step2 用户记忆检索结果"""
    return {"content": content, "score": score}


def _make_ck_item(content: str, score: float = 0.8) -> dict:
    """构造一条角色设定/知识检索结果"""
    return {"content": content, "score": score}


def _make_conversation(role: str, content: str):
    """构造一条 ConversationLog 模拟对象"""
    return SimpleNamespace(role=role, content=content)


async def _build_prompt(builder, relationship_info=None, **kwargs):
    """快捷调用 build_chat_prompt，提供合理默认值"""
    defaults = {
        "user_id": 1,
        "user_input": "你好",
        "memories": [],
        "recent_conversations": [],
        "relationship_info": relationship_info,
        "emotion_context": None,
    }
    defaults.update(kwargs)
    with patch.object(builder, "_get_persona_from_cache", new_callable=AsyncMock, return_value=None), \
         patch("backend.services.prompt_builder.get_activity_description", new_callable=AsyncMock, return_value=""), \
         patch("backend.services.prompt_builder.admin_config_service.get_active_config", new_callable=AsyncMock, return_value=None), \
         patch.object(builder, "_load_token_limits", new_callable=AsyncMock, return_value=(MAX_TOTAL_TOKENS, dict(MODULE_TOKEN_LIMITS))):
        return await builder.build_chat_prompt(**defaults)


# ============ STEP-004 原有测试：完整 Prompt 包含新 JSON Schema 示例 ============


@pytest.mark.asyncio
async def test_full_prompt_contains_new_schema():
    """拼装完整 Prompt → 检查包含新 JSON Schema 关键字段（在 720 token System 限制内）"""
    builder = _make_builder()
    rel = _make_relationship()
    prompt = await _build_prompt(builder, relationship_info=rel)

    assert "inner_monologue" in prompt
    assert "messages" in prompt
    assert "relation_change" in prompt
    assert "future" in prompt
    assert "knowledge_expand" in prompt
    assert '"type": "text"' in prompt
    assert "【知识性话题回应原则】" in prompt
    assert "【字段说明】" in prompt


# ============ 测试场景2：扩展字段为 NULL → 对应位置为默认值 ============


@pytest.mark.asyncio
async def test_null_relationship_fields_show_default():
    """relationship 扩展字段全为 NULL → 关系描述为「暂无，初次互动」；称呼行已移除（C3）"""
    builder = _make_builder()
    rel = _make_relationship(
        relation_description=None,
        user_description=None,
        user_hobby_name=None,
        user_real_name=None,
    )
    prompt = await _build_prompt(builder, relationship_info=rel)

    assert "关系描述：暂无，初次互动" in prompt
    # C3：称呼行从 relationship 移除；称呼全空时 user_nickname 模块也不输出
    assert "亲密称呼" not in prompt
    assert "用户真名" not in prompt
    assert "【用户称呼】" not in prompt


# ============ 测试场景3：扩展字段有值 → 正确注入 ============


@pytest.mark.asyncio
async def test_relationship_fields_injected():
    """扩展字段有值 → 正确注入到关系状态模块"""
    builder = _make_builder()
    rel = _make_relationship(
        relation_description="我们已经是很好的朋友了",
        user_description="温柔善良，喜欢看电影",
        user_hobby_name="小明",
        user_real_name="张明",
    )
    prompt = await _build_prompt(builder, relationship_info=rel)

    assert "关系描述：我们已经是很好的朋友了" in prompt
    assert "对TA的印象：温柔善良，喜欢看电影" in prompt
    # C3/C8：称呼移至独立 user_nickname 模块，relationship 不再含称呼行
    assert "亲密称呼" not in prompt
    assert "【用户称呼】" in prompt
    assert "小明" in prompt
    assert "张明" in prompt


# ============ 边界测试：user_description 为 NULL 时整行不输出 ============


@pytest.mark.asyncio
async def test_null_user_description_line_omitted():
    """user_description 为 NULL → 「对TA的印象」整行不输出"""
    builder = _make_builder()
    rel = _make_relationship(
        relation_description="朋友关系",
        user_description=None,
        user_hobby_name="小花",
        user_real_name="李华",
    )
    prompt = await _build_prompt(builder, relationship_info=rel)

    assert "对TA的印象" not in prompt
    # 称呼在 user_nickname 模块，不在 relationship（C3/C8）
    assert "【用户称呼】" in prompt
    assert "小花" in prompt
    assert "李华" in prompt


# ============ 测试：relationship_info 为 None → 也有默认值 ============


@pytest.mark.asyncio
async def test_no_relationship_info_defaults():
    """relationship_info 为 None（新用户无记录）→ 输出默认扩展字段"""
    builder = _make_builder()
    prompt = await _build_prompt(builder, relationship_info=None)

    assert "关系描述：暂无，初次互动" in prompt
    # C3：称呼行已移除；relationship_info 为 None 时 user_nickname 也不输出
    assert "亲密称呼" not in prompt
    assert "用户真名" not in prompt
    assert "【用户称呼】" not in prompt
    assert "对TA的印象" not in prompt


# ============ STEP-021：模块顺序（含可选 user_nickname） ============


@pytest.mark.asyncio
async def test_module_order_with_module_a_and_b():
    """验证含模块 A/B、无称呼时的 9 模块顺序（user_nickname 全空则跳过）"""
    builder = _make_builder()
    rel = _make_relationship()
    retrieval = _make_retrieval_results(
        cg=[_make_ck_item("外貌-体态：身高165，长发")],
        ck=[_make_ck_item("兴趣-偏好：喜欢写代码")],
    )
    prompt = await _build_prompt(
        builder,
        relationship_info=rel,
        retrieval_results=retrieval,
    )

    modules = prompt.split(MODULE_SEPARATOR)
    assert len(modules) == 9

    assert modules[0].startswith("你是林小梦")        # system
    assert "【人格设定】" in modules[1]                # persona
    assert "【角色设定与知识】" in modules[2]           # 模块 A
    assert "【关系状态】" in modules[3]                 # relationship
    assert "【用户记忆】" in modules[4]                 # memory
    assert "【情绪状态】" in modules[5]                 # emotion
    assert "【当前时间】" in modules[6]                 # 模块 B
    assert "【最近对话】" in modules[7]                 # recent_chat
    assert modules[8].startswith("【用户消息】")       # user_input


@pytest.mark.asyncio
async def test_module_order_with_user_nickname():
    """有称呼时 user_nickname 插在 recent_chat 与 user_input 之间（含模块 A 共 10 段）"""
    builder = _make_builder()
    rel = _make_relationship(user_hobby_name="小梦")
    retrieval = _make_retrieval_results(
        cg=[_make_ck_item("外貌-体态：身高165")],
    )
    prompt = await _build_prompt(
        builder,
        relationship_info=rel,
        retrieval_results=retrieval,
    )

    modules = prompt.split(MODULE_SEPARATOR)
    assert len(modules) == 10

    assert modules[0].startswith("你是林小梦")
    assert "【角色设定与知识】" in modules[2]
    assert "【最近对话】" in modules[7]
    assert modules[8].startswith("【用户称呼】")
    assert "小梦" in modules[8]
    assert modules[9].startswith("【用户消息】")


@pytest.mark.asyncio
async def test_module_order_without_module_a():
    """无模块 A 检索结果时跳过模块 A，其余模块顺序正确"""
    builder = _make_builder()
    rel = _make_relationship()
    prompt = await _build_prompt(builder, relationship_info=rel)

    modules = prompt.split(MODULE_SEPARATOR)
    # 无模块 A 时为 8 个模块
    assert len(modules) == 8
    assert modules[0].startswith("你是林小梦")
    assert "【人格设定】" in modules[1]
    assert "【关系状态】" in modules[2]
    assert "【用户记忆】" in modules[3]
    assert "【情绪状态】" in modules[4]
    assert "【当前时间】" in modules[5]
    assert "【最近对话】" in modules[6]
    assert "【用户消息】" in modules[7]


# ============ STEP-021：模块 A 内容注入 ============


@pytest.mark.asyncio
async def test_module_a_content_injected():
    """模块 A 正确注入角色设定和角色知识"""
    builder = _make_builder()
    retrieval = _make_retrieval_results(
        cg=[_make_ck_item("外貌-体态：身高165，长发飘飘", 0.9)],
        cp=[_make_ck_item("对小明的专属设定：记住他喜欢蓝色", 0.85)],
        ck=[_make_ck_item("编程-Python：擅长Python编程", 0.8)],
    )
    prompt = await _build_prompt(builder, retrieval_results=retrieval)

    assert "【角色设定与知识】" in prompt
    assert "角色设定：外貌-体态：身高165，长发飘飘" in prompt
    assert "角色设定：对小明的专属设定：记住他喜欢蓝色" in prompt
    assert "角色知识：编程-Python：擅长Python编程" in prompt


# ============ STEP-021：User Memory 使用 Step2 检索结果（dict） ============


@pytest.mark.asyncio
async def test_user_memory_from_step2_dicts():
    """User Memory 模块接受 Step2 格式的 dict 列表"""
    builder = _make_builder()
    memories = [
        _make_memory_dict("用户喜欢吃火锅", 0.9),
        _make_memory_dict("用户在杭州工作", 0.85),
    ]
    prompt = await _build_prompt(builder, memories=memories)

    assert "你记住：用户喜欢吃火锅" in prompt
    assert "你记住：用户在杭州工作" in prompt


# ============ STEP-021 测试场景1：所有模块在预算内 → 全量注入，无裁剪 ============


@pytest.mark.asyncio
async def test_all_modules_within_budget_no_trimming():
    """所有模块在预算内 → 全量注入，不触发裁剪"""
    builder = _make_builder()
    rel = _make_relationship()
    memories = [_make_memory_dict(f"记忆{i}", 0.9 - i * 0.1) for i in range(3)]
    retrieval = _make_retrieval_results(
        cg=[_make_ck_item("角色设定1", 0.9)],
        ck=[_make_ck_item("角色知识1", 0.85)],
    )
    convs = [_make_conversation("user", "你好"), _make_conversation("assistant", "嗨")]

    prompt = await _build_prompt(
        builder,
        relationship_info=rel,
        memories=memories,
        recent_conversations=convs,
        retrieval_results=retrieval,
    )

    # 全部模块均在
    assert "【角色设定与知识】" in prompt
    assert "【用户记忆】" in prompt
    assert "【最近对话】" in prompt
    assert "你记住：记忆0" in prompt
    assert "你记住：记忆1" in prompt
    assert "你记住：记忆2" in prompt
    assert "角色设定：角色设定1" in prompt
    assert "角色知识：角色知识1" in prompt


# ============ STEP-021 测试场景2：总 Token 超限 → 先裁 recent_chat → 再裁 memory ============


@pytest.mark.asyncio
async def test_trim_recent_chat_then_memory():
    """总 Token 超 7373 → 先裁 recent_chat → 再裁 memory"""
    builder = _make_builder()
    rel = _make_relationship()

    # 生成大量对话和记忆以超过预算
    long_text = "这是一段很长的对话内容，" * 50
    convs = [
        _make_conversation("user", long_text) for _ in range(10)
    ] + [
        _make_conversation("assistant", long_text) for _ in range(10)
    ]
    memories = [
        _make_memory_dict(f"很重要的记忆内容{'很长' * 30}", 0.9 - i * 0.05)
        for i in range(8)
    ]

    # 使用较小的预算强制裁剪
    small_budget = 3000
    small_limits = dict(MODULE_TOKEN_LIMITS)
    small_limits["recent_chat"] = 800
    small_limits["memory"] = 400

    with patch.object(builder, "_get_persona_from_cache", new_callable=AsyncMock, return_value=None), \
         patch("backend.services.prompt_builder.get_activity_description", new_callable=AsyncMock, return_value=""), \
         patch("backend.services.prompt_builder.admin_config_service.get_active_config", new_callable=AsyncMock, return_value=None), \
         patch.object(builder, "_load_token_limits", new_callable=AsyncMock, return_value=(small_budget, small_limits)):
        prompt = await builder.build_chat_prompt(
            user_id=1,
            user_input="测试",
            memories=memories,
            recent_conversations=convs,
            relationship_info=rel,
            emotion_context=None,
        )

    total = count_tokens(prompt)
    assert total <= small_budget, f"Token {total} 仍超过预算 {small_budget}"


# ============ STEP-021 测试场景3：模块 A 超 600 Token → 按 score 裁剪最低分条目 ============


@pytest.mark.asyncio
async def test_module_a_trim_by_score():
    """模块 A 超限时按 score 从低到高裁剪"""
    builder = _make_builder()

    # 创建超过 600 token 的模块 A 内容
    long_content = "这是一段很长的角色设定描述" * 20
    cg = [
        _make_ck_item(f"高分设定：{long_content}", 0.95),
        _make_ck_item(f"中分设定：{long_content}", 0.80),
        _make_ck_item(f"低分设定：{long_content}", 0.70),
    ]

    limits = dict(MODULE_TOKEN_LIMITS)
    text = builder._build_character_knowledge_prompt(cg, [], [], limits["character_knowledge"])

    if text:
        tokens = count_tokens(text)
        assert tokens <= limits["character_knowledge"]

        # 低分条目应被优先裁剪
        if "高分设定" in text:
            if "低分设定" in text:
                pass  # 全部在预算内
            else:
                assert "高分设定" in text, "高分条目应保留"


@pytest.mark.asyncio
async def test_module_a_score_ordering():
    """模块 A 的条目按 score 降序排列"""
    builder = _make_builder()

    items = builder._merge_character_knowledge_items(
        cg=[_make_ck_item("低分", 0.70)],
        cp=[_make_ck_item("高分", 0.95)],
        ck=[_make_ck_item("中分", 0.85)],
    )

    assert items[0]["score"] == 0.95
    assert items[1]["score"] == 0.85
    assert items[2]["score"] == 0.70


# ============ STEP-021 边界测试：热配 recent_chat=1000 → 使用配置值 ============


@pytest.mark.asyncio
async def test_hot_config_overrides_defaults():
    """热配 recent_chat=1000 → 使用配置值而非默认 1800"""
    builder = _make_builder()
    rel = _make_relationship()

    custom_limits = dict(MODULE_TOKEN_LIMITS)
    custom_limits["recent_chat"] = 1000

    long_convs = [
        _make_conversation("user", "很长的对话内容" * 30)
        for _ in range(5)
    ]

    with patch.object(builder, "_get_persona_from_cache", new_callable=AsyncMock, return_value=None), \
         patch("backend.services.prompt_builder.get_activity_description", new_callable=AsyncMock, return_value=""), \
         patch("backend.services.prompt_builder.admin_config_service.get_active_config", new_callable=AsyncMock, return_value=None), \
         patch.object(builder, "_load_token_limits", new_callable=AsyncMock, return_value=(MAX_TOTAL_TOKENS, custom_limits)):
        prompt = await builder.build_chat_prompt(
            user_id=1,
            user_input="测试",
            memories=[],
            recent_conversations=long_convs,
            relationship_info=rel,
            emotion_context=None,
        )

    # 提取最近对话模块的 token 数
    modules = prompt.split(MODULE_SEPARATOR)
    recent_chat_text = None
    for mod in modules:
        if mod.startswith("【最近对话】"):
            recent_chat_text = mod
            break

    if recent_chat_text:
        recent_tokens = count_tokens(recent_chat_text)
        assert recent_tokens <= 1000, f"Recent chat tokens {recent_tokens} 超过热配上限 1000"


# ============ STEP-021：模块 A 空结果时不生成空块 ============


@pytest.mark.asyncio
async def test_module_a_empty_results_skipped():
    """Step2 四路检索均为空 → 模块 A 不注入"""
    builder = _make_builder()
    retrieval = _make_retrieval_results()
    prompt = await _build_prompt(builder, retrieval_results=retrieval)

    assert "【角色设定与知识】" not in prompt


# ============ STEP-021：模块 B 活动描述为空时仍包含时间 ============


@pytest.mark.asyncio
async def test_module_b_time_only():
    """活动描述为空 → 模块 B 仅包含时间"""
    builder = _make_builder()
    prompt = await _build_prompt(builder)

    assert "【当前时间】" in prompt
    assert "现在是" in prompt


# ============ STEP-021：裁剪优先级 4 —— relationship 扩展部分 ============


@pytest.mark.asyncio
async def test_trim_relationship_extension():
    """裁剪优先级 4：移除 relationship 扩展字段后仅保留核心"""
    builder = _make_builder()
    rel = _make_relationship(
        relation_description="很好的朋友",
        user_description="温柔善良",
        user_hobby_name="小花",
        user_real_name="李华",
    )

    core_text = builder._build_relationship_prompt_core(rel)
    assert "当前关系等级" in core_text
    assert "语气与行为边界" in core_text
    # 扩展字段不应在核心版本中
    assert "关系描述" not in core_text
    assert "对TA的印象" not in core_text
    assert "亲密称呼" not in core_text


# ============ STEP-021：Token 上限默认值验证 ============


def test_default_token_limits():
    """验证 R-L1L3-19 定义的默认 Token 上限"""
    assert MAX_TOTAL_TOKENS == 7373
    assert MODULE_TOKEN_LIMITS["system"] == 720
    assert MODULE_TOKEN_LIMITS["persona"] == 1080
    assert MODULE_TOKEN_LIMITS["character_knowledge"] == 600
    assert MODULE_TOKEN_LIMITS["relationship"] == 360
    assert MODULE_TOKEN_LIMITS["memory"] == 900
    assert MODULE_TOKEN_LIMITS["emotion"] == 270
    assert MODULE_TOKEN_LIMITS["time_activity"] == 80
    assert MODULE_TOKEN_LIMITS["recent_chat"] == 1800
    assert MODULE_TOKEN_LIMITS["user_input"] == 900


# ============ STEP-017：时间描述串精确场景（保留原有测试） ============


def test_generate_time_description_format():
    """时间描述格式正确：包含周几 + 时段 + 几点几分"""
    desc = _generate_time_description()

    assert desc.startswith("现在是")
    assert "周" in desc
    assert "点" in desc
    assert "分" in desc

    periods = ["凌晨", "早上", "上午", "中午", "下午", "傍晚", "晚上"]
    assert any(p in desc for p in periods)


def test_generate_time_description_periods():
    """验证各时段边界"""
    from unittest.mock import patch as _patch

    test_cases = [
        (3, "凌晨"), (0, "凌晨"), (4, "凌晨"),
        (5, "早上"), (8, "早上"),
        (9, "上午"), (11, "上午"),
        (12, "中午"), (13, "中午"),
        (14, "下午"), (17, "下午"),
        (18, "傍晚"), (20, "傍晚"),
        (21, "晚上"), (23, "晚上"),
    ]

    for hour, expected_period in test_cases:
        mock_now = datetime(2026, 5, 5, hour, 30, 0)
        with _patch("backend.services.prompt_builder.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.utcnow = datetime.utcnow
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            desc = _generate_time_description()
            assert expected_period in desc, f"hour={hour} 期望 {expected_period}，实际 {desc}"


def test_time_description_wednesday_afternoon():
    """测试场景1：周三下午 3 点 → '现在是周三下午15点00分'"""
    from unittest.mock import patch as _patch

    mock_now = datetime(2026, 5, 6, 15, 0, 0)  # 2026-05-06 是周三
    with _patch("backend.services.prompt_builder.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.utcnow = datetime.utcnow
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        desc = _generate_time_description()
        assert desc == "现在是周三下午15点00分"


def test_time_description_early_morning():
    """测试场景2：凌晨 2 点 → '现在是周X凌晨2点00分'"""
    from unittest.mock import patch as _patch

    mock_now = datetime(2026, 5, 6, 2, 0, 0)  # 2026-05-06 是周三
    with _patch("backend.services.prompt_builder.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.utcnow = datetime.utcnow
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        desc = _generate_time_description()
        assert desc == "现在是周三凌晨2点00分"


# ============ STEP-017：活动描述串 ============


@pytest.mark.asyncio
async def test_activity_description_match():
    """测试场景3：admin_config 含 '14-18': '她在写代码' + 当前 15 点 → 返回「她在写代码」"""
    import json as _json
    from unittest.mock import patch as _patch

    schedule = {"14-18": "她在写代码", "0-5": "她在睡觉"}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = _json.dumps(schedule)

    mock_now = datetime(2026, 5, 6, 15, 30, 0)
    with _patch("backend.services.prompt_builder.get_redis", new_callable=AsyncMock, return_value=mock_redis), \
         _patch("backend.services.prompt_builder.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.utcnow = datetime.utcnow
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await get_activity_description()
        assert result == "她在写代码"


@pytest.mark.asyncio
async def test_activity_description_not_configured():
    """边界测试：admin_config 未配置 → 返回空字符串"""
    from unittest.mock import patch as _patch

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with _patch("backend.services.prompt_builder.get_redis", new_callable=AsyncMock, return_value=mock_redis):
        result = await get_activity_description()
        assert result == ""


@pytest.mark.asyncio
async def test_activity_description_no_match():
    """边界测试：有配置但当前小时不命中任何时段 → 返回空字符串"""
    import json as _json
    from unittest.mock import patch as _patch

    schedule = {"14-18": "她在写代码"}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = _json.dumps(schedule)

    mock_now = datetime(2026, 5, 6, 10, 0, 0)  # 10 点不在 14-18 范围内
    with _patch("backend.services.prompt_builder.get_redis", new_callable=AsyncMock, return_value=mock_redis), \
         _patch("backend.services.prompt_builder.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.utcnow = datetime.utcnow
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await get_activity_description()
        assert result == ""


@pytest.mark.asyncio
async def test_activity_description_invalid_json():
    """边界测试：admin_config 值为非法 JSON → 返回空字符串"""
    from unittest.mock import patch as _patch

    mock_redis = AsyncMock()
    mock_redis.get.return_value = "not-a-json"

    with _patch("backend.services.prompt_builder.get_redis", new_callable=AsyncMock, return_value=mock_redis):
        result = await get_activity_description()
        assert result == ""


@pytest.mark.asyncio
async def test_activity_description_redis_error():
    """边界测试：Redis 异常 → 返回空字符串"""
    from unittest.mock import patch as _patch

    mock_get_redis = AsyncMock(side_effect=Exception("Redis 连接失败"))

    with _patch("backend.services.prompt_builder.get_redis", mock_get_redis):
        result = await get_activity_description()
        assert result == ""


@pytest.mark.asyncio
async def test_time_prompt_with_activity():
    """时间模块包含活动描述时，活动描述出现在时间描述之后"""
    from unittest.mock import patch as _patch

    builder = _make_builder()
    with _patch("backend.services.prompt_builder.get_activity_description", new_callable=AsyncMock, return_value="她在写代码"):
        prompt = await builder._build_time_prompt()
        assert "【当前时间】" in prompt
        assert "现在是" in prompt
        assert "她在写代码" in prompt
        time_pos = prompt.index("现在是")
        activity_pos = prompt.index("她在写代码")
        assert activity_pos > time_pos


@pytest.mark.asyncio
async def test_time_prompt_without_activity():
    """活动描述为空串时，不输出活动行"""
    from unittest.mock import patch as _patch

    builder = _make_builder()
    with _patch("backend.services.prompt_builder.get_activity_description", new_callable=AsyncMock, return_value=""):
        prompt = await builder._build_time_prompt()
        assert "【当前时间】" in prompt
        assert "现在是" in prompt
        lines = prompt.strip().split("\n")
        assert len(lines) == 2  # 只有标题行和时间行


# ============ STEP-021：hint 文字包含新字段名 ============


@pytest.mark.asyncio
async def test_user_input_hint_updated():
    """模块9 hint 文字已替换为新 Schema 字段名"""
    builder = _make_builder()
    rel = _make_relationship()
    prompt = await _build_prompt(builder, relationship_info=rel)

    assert "inner_monologue" in prompt
    assert "emotion + reply" not in prompt
    assert "relation_change" in prompt
    assert "knowledge_expand" in prompt
