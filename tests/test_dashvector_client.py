# -*- coding: utf-8 -*-
# STEP-001 / 记忆检索：build_filter 单元测试

from backend.utils.dashvector_client import build_filter


def test_build_filter_type_only():
    """仅 type，无 user_id、无 candidate_keys"""
    assert build_filter("character_knowledge", None, []) == 'type = "character_knowledge"'


def test_build_filter_with_user_id():
    """type + user_id"""
    assert (
        build_filter("user", 42, [])
        == 'type = "user" AND user_id = 42'
    )


def test_build_filter_candidate_keys_to_key_l2_in():
    """candidate_keys 推导 key_l2 IN，去重保序"""
    result = build_filter(
        "user",
        1,
        ["经历-出行-自驾", "偏好-饮食", "经历-出行-重复"],
    )
    assert result == (
        'type = "user" AND user_id = 1'
        ' AND key_l2 IN ("经历-出行", "偏好-饮食")'
    )


def test_build_filter_discards_single_segment_keys_and_escapes_quotes():
    """单层 Key 丢弃；key_l2 值内双引号转义"""
    result = build_filter(
        "user",
        None,
        ["偏好", "经历-出行-自驾", '外貌-体"态-备注'],
    )
    assert "偏好" not in result
    assert '"经历-出行"' in result
    assert '外貌-体\\"态' in result
